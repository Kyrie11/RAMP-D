# Phase 6C-A59/1b-0I：Town06 起始车道一致性与失败证据审计

## 本轮目标与实际事实

服务器上传的 `town06_readiness.json` 保留 `REVIEW_INVALID_START_LANE`，在车辆创建之前失败，`trials=[]`；独立 review 返回 `NO_TRIALS`。因此上一轮“先落地稳定再加速”的修复**尚未在实车 actor 试验中得到验证**。早前 shortpulse 的首帧垂直速度（约 -0.49 到 -0.98 m/s）支持下落瞬态假设，但不能把本轮失败当作这一假设的验证。

代码中的原问题：`survey_sites` 在选点时用一条 `Waypoint` 跟踪 22 次 5 m 直线，之后在 `main` 中又对 `pose.location` 重新调用 `Map.get_waypoint(project_to_road=True)`，且没有核对是否是同一个 `(road_id, section_id, lane_id)`。在 CARLA/OpenDRIVE 的接近路口、叠层道路等情形，重投影可能回到另一车道、路口或 None。**这是一种根据代码及错误位置推导的可复现失败机制，不能宣称已确认 Town06 运行时一定是其中哪一种，除非有实际投影回读证据**。

## 实现

- 增加 `a63_carla_site_contract.py`，保持候选拓扑与实际 `Map.get_waypoint` 结果一致；显式拒绝 None、junction、身份不一致、投影差距过大和失败查询。
- 只有在未变更 110 m / 5° 门槛且起始投影身份一致时才选择候选；`site-prefer-longest` 在所有可用候选中选择最长，不再抢先选择一个不满足投影门槛的 300 m 候选。
- 保存被拒绝候选的原因计数和前八条实例；在进入车辆试验前再次查询，不能在不同车道上悄悄开始。
- 只读 `site-audit` 同步报告新的投影一致性门槛（不启动车辆，不持有 CARLA tick）。
- Offline readiness review 将顶层 `REVIEW` 及异常原因与 `NO_TRIALS` 同时保留，防止错误原因丢失。

## 独立验收门槛

1. 仍然拒绝所有被投影成路口/空值/其他车道的候选，不能通过减少安全校验来提高通过率。
2. 只有第二个候选的真实 road/section/lane 一致时才能自动切换到它。
3. 最新失败样本必须得到 `REVIEW`, `NO_TRIALS`, `EXECUTION_ABORT:REVIEW_INVALID_START_LANE`。
4. 所有上轮测试和新增回归必须通过；没有 skipped。离线测试不能声称已连接 CARLA。
5. `site-audit` 的 `projected_start_usable_candidates` > 0 只能说明地图查询一致，还不能声称 footprint 安全；`readiness` 达到接地高度代理/稳定证据后，仍不能推导物理轮胎接触力或验证模型误差界。

## 后续服务器执行顺序

首先验证新包及原生构建（见外部运行手册）；然后在独占的 CARLA 0.9.16 Town06 运行：

1. 只读 `--mode site-audit --site-spacing 2 --site-prefer-longest`；报告需有可用候选、明确投影一致的所选车道。
2. **仅在步骤 1 达标**时运行 `--mode readiness --confirm-isolated-world --confirm-exclusive-tick --site-spacing 2 --site-prefer-longest`，存储原始 `readiness.json`。
3. 用 `a62_review_carla_readiness.py` 独立审查；须包含 1 组真实 `settling`、连续帧、静态高度/轮底与道路高度一致、且车身瞬时 footprint 不越线。
4. **仅在步骤 3 达标**时运行 repeats=1 的 9 组小脉冲试验；先在 5/10/15 m/s 检查速度与真实前轮角、加速阶段和控制阶段时间戳，再扩大到 27 组。任何失败都保留 raw，不可用 best-run 代替保守下界。

注意：被查过的地图 waypoint 不等于一个真实物理接地证书；连续摩擦与执行器误差集合仍需 CARLA 物理日志加独立多工况标定，且本轮只测一个仿真模型，不可解释为实车保证。
