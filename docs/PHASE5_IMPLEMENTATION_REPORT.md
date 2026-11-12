# Phase 5 工程实现报告

## 1. 实现目标

本轮实现了 CEGAR 编排所需的工程语义接口：具体/伪反例分流、事件时间细化、support/observation 细化、master 更新、证据失效和版本绑定的可恢复重验证调度。Phase 4 的 verifier 仍负责三值物理和协议证据检查，Phase 5 不改变其 fail-closed 规则。`CegarEngine` 接收调用方选择的责任位置并编排重验证；它不会从一个聚合 `VerificationResult` 猜测 support 轴，也不会把抽象 branch checker 的返回值代替独立 concrete replay。

## 2. 代码变更

| 文件 | 变更 |
|---|---|
| `python/rampd_core/cegar.py` | 新增 `classify_counterexample`、`split_time_window`、协议 transition split、support/observation refinement、`EvidenceRegistry`、`ResumableVerificationQueue`、`MasterProblem`、`CegarEngine` 和 refinement log。 |
| `python/rampd_core/full_verifier.py` | 新增 whole-window `interval_branch_checker`；消息分支的公共后继时间由 receipt/local 的已证明可用时间决定，silence 在缺少 local 时使用 change；非点公共时钟返回 `UNKNOWN`；所有外部 evidence/replay callback 的异常、非法返回和非布尔 replay 均 fail-closed 为 `UNKNOWN`。验证预算也纳入 contract digest。 |
| `python/rampd_core/__init__.py` | 导出 Phase 5 API，版本更新为 `0.8.0`。 |
| `tests/test_phase5_cegar.py` | 覆盖 concrete/spurious/unknown、时间窗口和消息时钟绑定、support/observation nonanticipativity、证据失效、队列恢复和 CEGAR 重验证。 |
| `scripts/validate_phase5.sh` | 保留 Phase 4 gate，增加 Phase 5 专项测试、示例和机器可读验收摘要。 |

## 3. 关键语义修正

Phase 4 原先把后继时间取为 `change.lo`。对收到消息的分支，这可能在 receipt 或 local first observation 之前切换 public policy node。现在 `_public_observation_time` 对消息分支只使用 receipt 和已声明的 local 窗口；没有消息且没有 local 窗口的 silence 分支才使用 change 作为保守公共时间。任何非点公共时钟都会把 transition id 和具体 clock（`change`/`receipt`/`local`）写入未决义务，默认 selector 可以细化对应时钟；缺失 receipt 仍保持 `UNKNOWN`。

事件时间细化同步替换消息中的 `ClockTrace`，保持 message/transition clock identity。闭子窗共享中点，边界事件不会被漏掉。Phase 5 提供的 `interval_branch_checker` 只能由调用方用覆盖整个时间窗的独立证据实现，不能把某个采样时刻当作全窗证明。

## 4. 失败案例和预期结果

- replay 返回 `True` 的同一候选得到 `CONCRETE`；返回 `False` 得到 `SPURIOUS`；缺失 callback、异常或非 boolean 得到 `UNKNOWN`。
- support split 清空旧 actions，保持 cell/policy node，避免细化创造隐藏状态可用的新控制分支。
- 没有可观测性证明的 observation split 只产生一个保留原 policy node 的 refined cell；显式 distinguishability split 只对单 atom 结构产生两个新节点，协议 router 的更新必须由调用方同步提供。
- receipt/local 非点窗口不会被压到端点；队列 checkpoint 的 contract digest 或 generation 不匹配会被拒绝；in-flight task 在 checkpoint 恢复时回到 pending。
- verifier factory、branch/terminal evidence callback 或 concrete replay 抛出异常时，结果保持 `UNKNOWN`，外层 in-flight task 被放回 pending；非法 callback 返回不会被解释为安全证据。
- `full_support_certified`、`current_scene_verified` 和 `concrete_safety_certified` 继续为 `false`。

## 5. 验收边界

本地环境没有官方 MPFR development header 和 CMake；上传的目标服务器报告包含 Phase 4 回归 328 项和 Phase 5 专项 10 项测试，均通过。当前修订新增了 10 个 fail-closed/clock/queue 回归（Phase 5 专项共 20 项）；这些新增测试需要在用户服务器的官方 MPFR 4.0.2/Python 3.10 环境重新运行 `scripts/validate_phase5.sh`。该环境门禁仍不能替代真实场景验证。

本轮不下载数据集，不启动 SUMO/CARLA。真实 WOMD/AV2 接入和四时钟仿真日志仍属于 Phase 6。
