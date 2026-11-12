# Phase 5 验收报告

## 验收顺序

本轮按“明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告”执行。专项 gate 为 `scripts/validate_phase5.sh`，它先运行 Phase 4 全量回归，再运行 `tests/test_phase5_cegar.py` 和 Phase 5 机器示例。

## 专项结果

上传服务器归档的 Phase 5 基线专项测试为：

```text
Phase 5 tests: 10 passed, 0 failed, 0 skipped（上传基线）
Phase 4 protocol/full verifier tests: 27 passed, 0 failed, 0 skipped（上传基线）
native interval/Picard/ABI smoke: 3 passed（上传基线）
```

此前 Phase 4 文档中的 318 项是旧基线；本轮上传的服务器归档以外层回归 328 项为准，上传的 Phase 5 基线为 10 项。本修订后的专项 gate 现在要求 20 项；当前容器没有 CMake 和官方 MPFR development header，因此必须在用户服务器的官方 MPFR 4.0.2/Python 3.10 环境重新运行 `scripts/validate_phase5.sh`。


## 已验收义务

| 义务 | 结果 |
|---|---|
| concrete / spurious / unknown 分流 | 通过；严格依赖独立 replay 的 boolean `True/False` |
| event-time refinement | 通过；闭子窗共享有理中点，消息 ClockTrace 同步更新 |
| public observation timing | 通过；收到消息不能在 receipt/local 之前路由；非点 clock obligation 标明具体 transition/clock 并可由 selector 细化 |
| support-cell refinement | 通过；清空旧 actions，保留 policy node 和 nonanticipativity |
| observation refinement | 通过；无可观测区分证明时不创建新 policy node |
| master update | 通过；细化后 revision 增长并清空旧 action blocking 状态 |
| evidence invalidation | 通过；contract/protocol/resource/observation/model digest 任一变化即失效 |
| resumable queue | 通过；checkpoint 绑定 digest/generation，in-flight 任务可恢复 |
| 三值 fail-closed | 通过；缺证据、异常、预算耗尽均不升级为安全或具体反例 |

本轮修订进一步把 branch/terminal/whole-window evidence callback、concrete replay callback 和 CEGAR verifier factory 的异常或非法返回映射为 `UNKNOWN`；异常期间的外层 in-flight task 会回到 pending。`FullVerifierContract.digest` 同时包含 `max_tasks` 与 `max_path_length`，避免改变验证预算后复用旧证据。

## 保证边界

```text
assurance_scope = PHASE5_CEGAR_EXPLICIT_PROTOCOL_SUPPORT
full_support_certified = false
concrete_safety_certified = false
current_scene_verified = false
real_datasets_used = false
simulators_used = false
```

Phase 5 的 CEGAR 只是在显式合成协议和已有动力学合同上细化并重验证。它不证明真实交通场景，不生成实车可执行安全许可，也不接入 WOMD、AV2、MTR/QCNet/QCNeXt、CARLA 或 SUMO。

当前 `ResumableVerificationQueue` 是**版本绑定的外层重验证调度骨架**：它可以恢复 root/refinement 任务、generation 和 in-flight 状态，但不会序列化 `FullSupportVerifier` 内部的 `VerificationTask`、`seen` 集合或未决证据。因此不能把 该 checkpoint 描述成任意中断点的完整 verifier 工作队列恢复；这部分留待后续工程化。
