# Phase 6B 性能审计与无损优化

## 1. 审计范围

本轮只优化数据验证脚本和数据读取路径，不改变 WOMD/AV2 的状态、时间轴、track identity、focal/SDC 语义、future leakage guard、地图配对规则或坐标参考点定义。

入口命令仍为：

```bash
bash scripts/validate_phase6b.sh
```

`validate_phase6B.sh`（大写 B）是兼容包装脚本；`validation_phase6B.sh` 并不是本工程中的文件名。

## 2. 定位到的性能问题

### 2.1 WOMD：抽样前对整个 TFRecord shard 做 SHA-256

旧实现先执行 `sha256_file(path)`，之后才读取 `max_records` 条 protobuf。即使 `MAX_RECORDS=1`，也会先顺序读取完整 TFRecord shard。对大分片而言，这个行为使抽样验证退化为全分片 I/O。

修正后：
- `HASH_SOURCE_FILES=0`（默认快速抽样）：不扫描完整 shard；仍对每条实际读取的 Scenario protobuf payload 计算精确 SHA-256，并计算 canonical scene digest。
- `HASH_SOURCE_FILES=1`：计算整个 shard 的完整 SHA-256，保持严格来源文件指纹模式。

`source_file_sha256` 在快速抽样模式下明确为 `null`，不会把 record digest 冒充 shard digest。

### 2.2 AV2：Parquet 文件 SHA-256 重复计算

旧实现对同一个 Parquet 路径分别计算 `content_sha256` 和 `source_file_sha256`，导致同一文件被完整读取两遍。

修正后只计算一次，并将同一 digest 传入两个兼容字段。快速抽样模式不扫描完整 Parquet 文件，使用规范化解析行 digest，并独立记录 canonical scene digest。

### 2.3 AV2：无差别读取 Parquet 所有列

`parse_av2_rows` 实际只消费轨迹、身份、类别、时间轴和 observed/focal 字段。修正后的 reader 先检查 Parquet schema，再只读取所有被 parser 使用的字段（包括可选别名）。没有删掉任何参与语义计算的字段。

### 2.4 AV2：验证地图 JSON 时重复读盘

旧实现先 `read_text()` 解析 JSON，再通过 `sha256_file()` 第二次读取文件。修正后一次读取原始 bytes，同时执行 JSON 解析和 SHA-256 计算。

### 2.5 AV2：大 split 的全量路径排序

旧实现将所有 `scenario_*.parquet` 路径物化并完整排序，再取前 N 个。修正后使用 `heapq.nsmallest(N, iterator)`，保持“字典序最小的 N 个文件”这一确定性抽样语义，但降低路径列表的峰值内存和排序工作量。目录项仍需遍历，避免使用不可复现的文件系统枚举顺序。

## 3. 哈希语义（必须区分）

| 字段 | 含义 | 快速抽样 | 完整来源校验 |
|---|---|---:|---:|
| `record_sha256` | 单条 WOMD protobuf 序列化 payload | 计算 | 计算 |
| `content_sha256` | 兼容字段；快速模式表示 record/parsed-row digest，完整模式表示 source file digest | 计算 | 计算 |
| `source_file_sha256` | 整个 TFRecord/Parquet 文件的 SHA-256 | 不计算，值为 null | 计算 |
| `scenario_content_sha256` | 规范化解析场景的 digest | 计算 | 计算 |
| `map_content_sha256` | AV2 map JSON 原始 bytes 的 SHA-256 | 计算 | 计算 |

AV2 没有独立的 protobuf record；快速模式的 `content_sha256` 是从读取的 AV2 行构造的 canonical parsed-row digest，不是 Parquet 原始字节哈希。

为了保证 `scenario_content_sha256` 不因哈希策略不同而变化，canonical digest 会排除来源文件哈希策略元数据和源路径/源 digest。WOMD dynamic map state digest 改为基于 deterministic protobuf serialization（或递归 canonical value），不再依赖 Python 对象的 `str()`，避免对象地址进入 digest。`scenario_content_sha256` 同时排除 map archive 的本地路径，但保留 map 内容 digest，因此同一地图内容复制到不同目录不会改变场景语义哈希。

## 4. 执行方式

### 快速抽样（推荐先运行）

```bash
WOMD_ROOT=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario \
AV2_ROOT=/data0/senzeyu2/dataset/Argoverse2/motion \
MAX_RECORDS=1 \
HASH_SOURCE_FILES=0 \
bash scripts/validate_phase6b.sh
```

该模式验证真实 parser、场景合同和单场景内容 digest，不扫描整个 WOMD shard/AV2 Parquet 文件来计算文件级哈希。

### 完整来源文件指纹

```bash
WOMD_ROOT=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario \
AV2_ROOT=/data0/senzeyu2/dataset/Argoverse2/motion \
MAX_RECORDS=10 \
HASH_SOURCE_FILES=1 \
bash scripts/validate_phase6b.sh
```

此模式会对实际抽到的每个源文件计算完整 SHA-256。WOMD 同一 shard 中抽取多条 Scenario 时，shard 只哈希一次。

## 5. 报告新增字段

`phase6b_acceptance_summary.json` 新增：
- `hash_policy`
- `source_file_hashes_requested`
- `full_source_file_hashes_computed`
- `integrity_status`
- `phase_timings.pytest_elapsed_seconds`
- `phase_timings.womd_elapsed_seconds`
- `phase_timings.av2_elapsed_seconds`
- 每个 sample 的 `source_file_size_bytes`、`source_file_mtime_ns`、`source_file_hash_status` 和 `content_sha256_semantics`

文件 size/mtime 仅为来源元数据，不是密码学哈希。只有 `source_file_sha256` 非空时，才代表源文件完整 SHA-256 已实际计算。

## 6. 回归验证

本轮增加测试：
- 快速 AV2 解析不会调用全文件 SHA-256；
- 快速 WOMD 抽样仍精确计算 record payload SHA-256，但不会哈希整个 shard；
- AV2 Parquet reader 只读取 parser 使用的列；
- AV2 完整来源哈希只计算一次；
- 同一场景在 fast/full source-hash policy 下的 `scenario_content_sha256` 保持一致；
- WOMD dynamic map digest 使用稳定序列化，不受 Python 对象地址影响。

当前可用环境缺少 Phase 1D native MPFR backend，因此不能在此容器中运行普通完整 pytest 收集流程。使用工程内 dependency-free harness 执行：

```bash
python scripts/validate_phase6c_a_dependency_free.py
```

结果：**51 passed**。这覆盖纯 Python 数据适配与 Phase 6C 合同测试，不替代服务器上的 Phase 6B 真实数据读取和 native CTest。

## 7. 不在本轮做的优化

- 不跳过 WOMD/AV2 必需字段校验；
- 不截断轨迹时间轴；
- 不删除 map pairing；
- 不将 `valid` 与 `observed` 合并；
- 不减少 `MAX_RECORDS` 之外的隐式采样；
- 不把 record digest 冒充 source file digest；
- 不并行化多个数据 reader，以免在尚未 profile 前引入 I/O 争用和不可控内存峰值。

下一步应先用快速模式取得真实服务器 timing，再决定是否需要并行 I/O、Arrow batch parsing 或 hash sidecar cache。
