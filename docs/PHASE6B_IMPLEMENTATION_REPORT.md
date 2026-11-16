# Phase 6B 工程实现报告

## 新增实现

| 文件 | 内容 |
|---|---|
| `python/rampd_core/record_adapters.py` | WOMD Scenario 和 AV2 Motion 的可选依赖 reader、统一 `ParsedScene`、内容 hash、map 解析、local frame 工具、中心到后轴转换、四时钟注入 |
| `tests/test_phase6b_record_adapters.py` | synthetic protobuf-like fixture、AV2 dense 补齐、future boundary、clock non-inference、参考点数学和缺失 mask 回归 |
| `scripts/validate_phase6b.sh` | 本地单元测试、服务器 validation 抽样、显式 PASS/SKIP/ERROR 报告 |
| `scripts/package_report_phase6b.py` | 将本轮 summary、pytest log 和 XML 打包为可重放报告 |
| `docs/PHASE6B_PLAN.md` | 本轮目标和语义边界 |

## 关键语义

WOMD parser 把 `Track.id` 转成稳定字符串身份，把来源数组下标存入 track metadata；无效状态保留时间槽但 `valid=False`，不做零填充。AV2 parser 按场景全局 `timestep` 补齐每条 track，缺失状态使用 `valid=False, observed=None`。AV2 的 `current_time_index` 优先由 focal track 的 observed prefix 决定；没有 focal track 时才回退到全局 observed 最大 timestep。

中心到后轴转换要求调用者显式提供 body-frame `offset_body`（定义为“后轴到框中心”的向量）。位置按照论文中的旋转公式转换；速度只有在每个需要转换的状态都提供角速度时才标记为 rear-axle velocity，否则保留 center-frame provenance。现在还支持按 `track_ids` 只转换几何适用的车辆，并显式报告 mixed reference。

Phase 6B 后续审计修正见 `PHASE6B_AUDIT_AND_FIXES.md`：AV2 focal/SDC 分离、严格 bool 解码、官方场景时间轴校验、WOMD shard/record/scenario digest 分离，以及 SKIP 状态退出码修正。

`parse_av2_parquet` 默认要求在 scenario 同目录找到精确匹配的 `log_map_archive_<scenario_id>.json`；无法无歧义配对时显式报错，调用者可传入已经核对过的 `map_file`。`localize_scene` 只对轨迹状态应用刚体 world→local 变换，并在 map metadata 中记录同一个精确变换。AV2 map JSON 的异构 lane/polygon 几何不被未知 schema 静默改写；后续 map adapter 必须使用该 metadata 对每个点应用相同变换。

## 验收命令

```bash
cd /home/senzeyu2/code/RAMP-D
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
bash scripts/validate_phase6b.sh
```

默认读取：

```text
/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
/data0/senzeyu2/dataset/Argoverse2/motion
```

可用 `WOMD_ROOT=... AV2_ROOT=... MAX_RECORDS=1` 覆盖路径和抽样量。若可选 reader 或 split 不存在，summary 对相应数据集写 `SKIP`，而不是伪造 `PASS`。

## 本地可复现结果

当前容器没有官方 MPFR development headers/native interval ABI，也没有服务器数据路径和 AV2 parquet engine。Phase 6B/6C-A dependency-free harness 执行 47 个纯 Python 回归测试全部通过；`compileall` 和 `bash -n scripts/validate_phase6b.sh` 通过。服务器仍必须安装 `.[datasets]` 并运行上面的真实数据脚本。
