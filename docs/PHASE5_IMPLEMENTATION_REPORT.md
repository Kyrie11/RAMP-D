# Phase 5 工程实现报告

## 1. 实现目标

本轮实现了 CEGAR 编排所需的工程语义接口：具体/伪反例分流、事件时间细化、support/observation 细化、master 更新、证据失效和版本绑定的可恢复重验证调度。Phase 4 的 verifier 仍负责三值物理和协议证据检查，Phase 5 不改变其 fail-closed 规则。`CegarEngine` 接收调用方选择的责任位置并编排重验证；它不会从一个聚合 `VerificationResult` 猜测 support 轴，也不会把抽象 branch checker 的返回值代替独立 concrete replay。

## 2. 代码变更

| 文件 | 变更 |
|---|---|
| `python/rampd_core/cegar.py` | 新增 `classify_counterexample`、`split_time_window`、协议 transition split、support/observation refinement、`EvidenceRegistry`、`ResumableVerificationQueue`、`MasterProblem`、`CegarEngine` 和 refinement log。 |
| `python/rampd_core/full_verifier.py` | 新增 whole-window `interval_branch_checker`；消息分支的公共后继时间由 change/receipt/local 的已证明可用时间共同决定，非点可用时间返回 `UNKNOWN`。 |
| `python/rampd_core/__init__.py` | 导出 Phase 5 API，版本更新为 `0.8.0`。 |
| `tests/test_phase5_cegar.py` | 覆盖 concrete/spurious/unknown、时间窗口和消息时钟绑定、support/observation nonanticipativity、证据失效、队列恢复和 CEGAR 重验证。 |
| `scripts/validate_phase5.sh` | 保留 Phase 4 gate，增加 Phase 5 专项测试、示例和机器可读验收摘要。 |

## 3. 关键语义修正

Phase 4 原先把后继时间取为 `change.lo`。对收到消息的分支，这可能在 receipt 或 local first observation 之前切换 public policy node。现在 `_public_observation_time` 至少要求 change、receipt（有消息时）和已声明 local 窗口的可用点时间一致，并取其中最大值；任何非点窗口或缺失 receipt 都是未决义务。

事件时间细化同步替换消息中的 `ClockTrace`，保持 message/transition clock identity。闭子窗共享中点，边界事件不会被漏掉。Phase 5 提供的 `interval_branch_checker` 只能由调用方用覆盖整个时间窗的独立证据实现，不能把某个采样时刻当作全窗证明。

本轮回归又发现并修正了两个边界。首先，`change` 是物理时钟，不是信息时钟；没有 message receipt 或显式 local observation 时，silence 分支不再在 `change` 时刻路由。其次，CEGAR 启动与每次重验证都检查完整的 protocol/resource/observation/model digest、queue generation 以及 verifier/result contract digest，避免缓存旧验证器或旧证据被当成当前合同的结果。

## 4. 失败案例和预期结果

- replay 返回 `True` 的同一候选得到 `CONCRETE`；返回 `False` 得到 `SPURIOUS`；缺失 callback、异常或非 boolean 得到 `UNKNOWN`。
- support split 清空旧 actions，保持 cell/policy node，避免细化创造隐藏状态可用的新控制分支。
- 没有可观测性证明的 observation split 只产生一个保留原 policy node 的 refined cell；显式 distinguishability split 只对单 atom 结构产生两个新节点，协议 router 的更新必须由调用方同步提供。
- receipt/local 非点窗口不会被压到端点；队列 checkpoint 的 contract digest 或 generation 不匹配会被拒绝；in-flight task 在 checkpoint 恢复时回到 pending。
- `full_support_certified`、`current_scene_verified` 和 `concrete_safety_certified` 继续为 `false`。

## 5. 验收边界

本地环境没有官方 MPFR development header 和 CMake；为验证 Python/Phase 5 逻辑，使用临时 bootstrap header 编译了当前 system MPFR runtime 的 native library，native 三项测试通过，Phase 5 专项测试通过。该临时 backend 不替代目标服务器的官方 MPFR 4.0.2 build，因此本地全量 interval 回归中出现的定向舍入差异不能作为 Phase 5 数学失败或服务器验收结果。用户服务器应使用官方头文件运行 `scripts/validate_phase5.sh`。

本轮不下载数据集，不启动 SUMO/CARLA。真实 WOMD/AV2 接入和四时钟仿真日志仍属于 Phase 6。
