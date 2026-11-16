# Phase 5 验收报告

## 验收顺序

本轮按“明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告”执行。专项 gate 为 `scripts/validate_phase5.sh`，它先运行 Phase 4 全量回归，再运行 `tests/test_phase5_cegar.py` 和 Phase 5 机器示例。

## 上传服务器结果（原始 Phase 5 报告）

原报告的 Python 部分为 Phase 5 专项 10 项通过，Phase 4 专项 23 项通过，
全量 Python 328 项通过。报告中的 `phase4_ctest.log` 只有 `Test project ...`
一行，因此不能把 native CTest 计为已验证；本版本已经把缺少
`CTestTestfile.cmake` 或缺少 passing-test summary 改成硬失败。

## 专项结果（本轮语义修正后）

本地临时 bootstrap native backend 下，修正后的 Phase 5 专项测试为：

```text
Phase 5 tests: 12 passed, 0 failed, 0 skipped
Phase 4 protocol/full verifier tests: 18 passed, 0 failed, 0 skipped
native interval/Picard/ABI smoke: 3 passed
```

Phase 4 上传服务器报告的正式结果仍为 328 Python；native CTest 需按修正后的脚本在服务器重新执行。由于当前容器没有 CMake 和官方 MPFR development header，本地临时 backend 的全量数值回归出现 18 个定向舍入相关失败，属于 backend 构建条件差异，必须在服务器官方 MPFR 环境复核后再作为工程 gate。

## 已验收义务

| 义务 | 结果 |
|---|---|
| concrete / spurious / unknown 分流 | 通过；严格依赖独立 replay 的 boolean `True/False` |
| event-time refinement | 通过；闭子窗共享有理中点，消息 ClockTrace 同步更新 |
| public observation timing | 通过；message branch 在 receipt 可用，local-detection branch 在 local 可用；两种独立通道不强制 receipt→local 顺序，非点时间保持 UNKNOWN |
| support-cell refinement | 通过；清空旧 actions，保留 policy node 和 nonanticipativity |
| observation refinement | 通过；无可观测区分证明时不创建新 policy node |
| master update | 通过；细化后 revision 增长并清空旧 action blocking 状态 |
| evidence invalidation | 通过；contract/protocol/resource/observation/model digest 任一变化即失效 |
| resumable queue | 通过；checkpoint 绑定 digest/generation，in-flight 任务可恢复 |
| 三值 fail-closed | 通过；缺证据、异常、预算耗尽均不升级为安全或具体反例 |
| public observation clock | 修正；物理 `change` 不再单独产生 public branch；无 receipt/local clock 的 silence 保持 `UNKNOWN` |
| CEGAR contract binding | 修正；registry 的 protocol/resource/observation/model digest、queue generation 和 factory/result contract digest 全部绑定 |

## 2026-11-16 跨阶段复核补充

此前实现曾将 message receipt 与 local-first-observation 取 `max`，并要求 `receipt→local`。回溯论文后确认四个时钟是独立的，且报告可能乱序到达；论文没有要求 message branch 必须等待 local observation。因此当前代码已修正为：message branch 使用 receipt，local-detection/silence-with-local branch 使用 local；不再强制 `receipt→local`。如果未来需要“同时具备 message 与 local 两个证据才可区分”的复合观察类，必须在 protocol schema 中显式声明，不能隐式取 max。

另外，`ProtocolAutomaton.enumerate_successors(at_time=...)` 现在按已证明的 public-observation window 过滤已公开分支，不再按物理 `change` 时钟过滤。这样 `change < current_public_time < receipt` 的隐藏规则变化仍保留在 belief support 中，直到 receipt/local observation 真正公开。新增 `test_phase6c_protocol_regression.py` 覆盖该边界。此修正不把任何缺失/非点时钟升级为 PROVED。

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
