# RAPID-AD v1 实验结果与工程缺陷审计

## 1. 当前结果能说明什么？

本审计基于你上传的 `RAPID-AD.zip` 中的 v1 源码、manifest、metrics、trace、batch error 文件。由于 v1 没有保存每个子进程的 stdout/stderr，`returncode=-6` 的精确根因无法从现有归档确定。

| 运行批次 | 计划规模 | 实际写出的 metrics | 错误记录 | 判断 |
|---|---:|---:|---:|---|
| `20261025_090445` | 6 个 smoke 条件/控制器 | Oracle、baseline、PID 各 6 个，共 18 个 | 有 1 个子进程 `returncode=-6` | 只能作为冒烟诊断，不是正式实验 |
| `20261025_091220` | core 计划 48 个条件 | 29 个 Oracle metrics | 5 | 没有完成计划矩阵，也未完整跑到其他控制器 |
| `20261025_092022` | core 计划 48 个条件 | 7 个 Oracle metrics | 19 | 大量后续场景在写 metrics 前就失败；不能用于因果统计 |

六条件 smoke 的行为大致如下：

- 特权 `rapid_ad_oracle` 在两个 GO→STOP 动态条件中成功停车，在两个 STOP→GO 动态条件中恢复行驶。这只能说明已测的少量实例对特权控制器可运行。
- `baseline` 和 `pid` 在 GO→STOP 动态条件中越过虚拟控制线。这些控制器并不理解指挥者的视觉手势，因此它们是预期的弱下界，不是“强视觉模型失败”的证据。
- baseline 在某个 GO→STOP 条件下的估计恢复余量已为负；PID 则在估计余量为正时仍越线。由于动作阶段按固定距离触发、制动减速度未标定，这个对比只能作为诊断线索。
- STOP→GO 中有些 baseline/PID 条件在 release 之前就没有建立 STOP。它们属于初始 STOP 合规失败，而不是“合法放行后仍过度等待”。

**目前没有足够证据确认 RQ1 或 RQ2 成立。** 当前归档没有完整因子矩阵，也没有测试多个强视觉/端到端闭环策略。

## 2. 已确认的工程问题

1. **仿真失败后 batch 继续运行。** 后续出现 ego spawn 失败和 CARLA RPC timeout，可能受到前一 episode 的残留状态影响。基础设施错误不能计入策略失败。
2. **没有保存 child stdout/stderr。** `returncode=-6` 无法定位到具体的 Python 异常、CARLA 原生崩溃或服务端卡死。
3. **缺少每个 episode 前后的 CARLA health、同步模式、actor 数量和 spawn 清理检查。**
4. **v1 的 core 只覆盖 `none/overlap`，没有完整测试 `pre/overlap/post` 事件顺序。**
5. **静态控制条件出现了不适用的指标。** 例如没有发生 STOP→GO release 的静态 STOP 条件仍可能得到 `resume_within_allowance=false`；静态 GO 条件也可能得到 `stop_success=false`。v2 将这些指标改为 null。
6. **恢复余量被错误地按整个 episode 取最小值。** 车辆在合法 GO 状态下正常越线，也会使全程最小余量变成负数。v2 只在 GO→STOP 的响应窗口内统计。
7. **late 阶段按固定 9 m 距离定义。** 在已记录的速度下，9 m 对应的估计停车余量仍约为 4 m，不能称为“接近恢复边界”。v2 改为目标估计余量 5.0 m 和 1.5 m。
8. **减速度常数未经标定。** v1 的 `physically_recoverable` 名称过度声称；v2 分开报告 `estimated_recoverable_at_evidence` 和经过标定后才允许报告的 `physically_recoverable_at_evidence`。
9. **STOP→GO 分支从静止状态开始。** 这适合测释放后的 liveness，但不测车辆在运动中如何响应 STOP。该分支不能代替 GO→STOP 主安全任务。
10. **静态 placebo 的 anchor 被混同为证据时间。** v2 对无真实控制变化的条件保留 anchor 时间，但实际 `evidence_available_time_s` 为空。
11. **帧保持只作用于 `observation['image']`。** 它是 front-RGB stale-frame 干预，不等于真实物理遮挡，也不会自动屏蔽其他相机、LiDAR 或特权状态。
12. **CARLA 路径有不一致迹象。** v1 日志显示 agents 从 `CARLA_0.9.15/PythonAPI/carla` 加载，而你指定的根目录是 `CARLA0.9.15`。这只是风险信号，尚不能认定为 RPC timeout 根因。v2 preflight 会打印实际 import 路径并检查兼容代码中的硬编码路径。

## 3. v2 做了哪些修正？

- `core` 每个 seed 为 32 个完整条件：两个任务 × 两种 transition 状态 × 两个任务内阶段 × 四种证据窗口（none/pre/overlap/post）。
- GO→STOP 阶段按目标估计停车余量触发，而不是按固定距离触发。
- 静态 placebo、真实状态转换、证据窗口和实际输入 mask 的时间戳分别记录。
- 区分 `setup_valid`、`exposure_valid`、`valid_for_safety_analysis`、`valid_for_liveness_analysis` 和 `valid_for_causal_analysis`。
- 将危险继续执行、证据到达时已不可恢复、合法 release 后的 stale retention、未建立初始 STOP 分开统计。
- 每个子进程保存 stdout/stderr；批次默认 fail-fast；每个 episode 前后检查 CARLA RPC、同步模式、actor 数量和 spawn station 清理。
- 只保存少量 transition/mask 前后的诊断 PNG，不需要保存全程 PNG。
- 因子交互只使用完整配对 seed block；少于 5 个独立 block 时明确标记样本不足。

## 4. 仍需在你的服务器上确认

- CARLA 0.9.15 与本地 MARSHAL clone 是否稳定兼容。
- Town03 的 spawn station 是否清洁、每个 episode 结束后 actor 是否完整清理。
- 指挥者手势是否在关键帧中可见，虚拟控制线与指挥者位置是否合理。
- 5.0 m 和 1.5 m 余量是否在实际车辆、天气与摩擦条件下可恢复；需先运行 `scripts/calibrate_braking.py`，再检查特权 Oracle 是否通过。
- 至少若干不同架构的强闭环视觉策略是否出现可重复失败。当前 v1 结果没有证明这一点。


## 5. v3 对 v2 的进一步修正

v2 的 GO->STOP `pre/overlap/post` mask 仍主要按 stopping-margin 空间范围调度，实际时长会随控制器速度变化；cache miss 也可能被误计为已实现的干预；STOP->GO 观察窗口不足时可能被错误判为 stale retention；因子分析还可能混入不同 schema 的结果。

v3 改为事件相对的 simulation-time mask 调度，并用实际时间戳验证时序、持续时间、缓存替换次数和 phase-anchor 误差；release 后观察不完整的 episode 标记为 `right_censored_after_release`；交互分析只使用 schema v3。新增 `make_visual_audit_manifest.py` 与 `summarize_run_health.py`。

这些修复仍是静态代码修正。没有在构建环境中连接用户服务器的 CARLA 0.9.15，因此必须先运行 Oracle smoke、检查诊断 JPEG、确认 STOP/PROCEED 手势确实可见后，才可解释 RQ1/RQ2。
