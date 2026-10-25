# RAPID-AD v3 相对 v2 的修正

## 为什么需要 v3

v2 已经能通过静态自检，但代码审阅发现：GO->STOP 的 `pre/overlap/post` 窗口仍主要按 stopping-margin 的空间变化触发，实际 mask 时长会随着车辆速度/制动行为变化；输入缓存缺失也可能被误计为有效干预；STOP->GO 在观察窗口不足时可能被错误标记为 stale retention；同时黑盒模型的视觉 cue 是否真的可见仍需人工审计。

## v3 变更

1. **事件相对的 mask 调度**：GO->STOP 的 `pre/overlap` 使用最近 margin 斜率估计 time-to-anchor；`post` 使用 anchor 后的固定 simulation-time duration。所有情况均记录实际 start/end 与实际持续时间，且实际窗口不符合时序要求时标记 exposure invalid。
2. **干预缓存验证**：记录 mask substitution 数、cache miss、实际 mask 时长和 `gap_timing_realized`。缓存缺失时不再把 raw frame 通过误记为有效的 frame hold。
3. **阶段锚点有效性**：记录实际 margin 与目标 margin 的误差；偏差超过阈值的 episode 不进入因果分母。
4. **liveness 右删失处理**：STOP->GO 只有在完整观察到 release 后的 response allowance 时才可以判定 stale retention；观察不足的 episode 标记为 `right_censored_after_release`，不进入 liveness causal analysis。静态 STOP placebo 仍可作为匹配对照，但不会被判定为未恢复。
5. **避免过度声称物理可恢复性**：`physically_recoverable_at_evidence` 保留为 null 的兼容字段；改用 `recoverability_model_predicts_recoverable_at_evidence`，并明确它仍是模型估计。
6. **视觉审计工作流**：关键帧改为最多 640x360、JPEG quality 86，降低日志体积；新增 `make_visual_audit_manifest.py`。最终交互分析可通过 `--require-visual-audit` 排除未审核的动态转换 episode。
7. **CARLA 路径一致性**：batch、episode、preflight、health/spawn 检查显式加入配置 CARLA_ROOT 下的 PythonAPI 与匹配的 0.9.15 egg 路径，减少错误加载其他安装版本的风险。
8. **recoverability guard**：`core/all` 默认要求 base config 中 `scene.recoverability_calibrated=true`。仅在明确探索性试验时使用 `--allow-uncalibrated`。
9. **分析隔离**：交互分析只接收 schema v3，避免把 v1/v2 不同语义的指标混合估计。
10. **运维诊断**：新增 `summarize_run_health.py`，将 RPC timeout、spawn failure、native crash、缺失 metrics、无效 setup/exposure 分开汇总。

## 尚未解决、必须诚实保留的限制

- 未在此执行环境连接真实 CARLA 0.9.15，也未 live-run MARSHAL；用户服务器上的 RPC、actor cleanup 和场景可见性仍待验证。
- 视觉帧审计仍需人工确认，自动化的 frame-hold 代码路径并不能证明 STOP/PROCEED 手势在第一张 fresh frame 中清晰可见。
- 黑盒模型的内部 belief update 与 trajectory invalidation 时间不可直接观测。没有内部日志或干预时，只能报告外部决策/动作响应代理。
- `phase` 是运动/可恢复性阶段，不等于显式操纵了模型内部的“trajectory commitment”。论文暂时不应声称已单独识别内在轨迹承诺的因果效应。
