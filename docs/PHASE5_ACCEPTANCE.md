# Phase 5 验收报告

## 验收顺序

本轮按“明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告”执行。专项 gate 为 `scripts/validate_phase5.sh`，它先运行 Phase 4 全量回归，再运行 `tests/test_phase5_cegar.py` 和 Phase 5 机器示例。

## 专项结果

本地临时 bootstrap native backend 下，Phase 5 专项测试为：

```text
Phase 5 tests: 10 passed, 0 failed, 0 skipped
Phase 4 protocol/full verifier tests: 27 passed, 0 failed, 0 skipped
native interval/Picard/ABI smoke: 3 passed
```

Phase 4 上传服务器报告的正式结果仍为 318 Python + 3 native 全部通过；本轮没有伪造新的服务器结果。由于当前容器没有 CMake 和官方 MPFR development header，本地临时 backend 的全量数值回归出现 18 个定向舍入相关失败，属于 backend 构建条件差异，必须在服务器官方 MPFR 环境复核后再作为工程 gate。

## 已验收义务

| 义务 | 结果 |
|---|---|
| concrete / spurious / unknown 分流 | 通过；严格依赖独立 replay 的 boolean `True/False` |
| event-time refinement | 通过；闭子窗共享有理中点，消息 ClockTrace 同步更新 |
| public observation timing | 通过；收到消息不能在 receipt/local 之前路由，非点时间保持 UNKNOWN |
| support-cell refinement | 通过；清空旧 actions，保留 policy node 和 nonanticipativity |
| observation refinement | 通过；无可观测区分证明时不创建新 policy node |
| master update | 通过；细化后 revision 增长并清空旧 action blocking 状态 |
| evidence invalidation | 通过；contract/protocol/resource/observation/model digest 任一变化即失效 |
| resumable queue | 通过；checkpoint 绑定 digest/generation，in-flight 任务可恢复 |
| 三值 fail-closed | 通过；缺证据、异常、预算耗尽均不升级为安全或具体反例 |

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
