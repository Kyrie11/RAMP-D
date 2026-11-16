# Phase 6C-A：预测提案、RuleNet 软排序与同步合同

## 本轮目标

本轮只建立 Phase 6C 的纯 Python 数据/算法合同，不启动 CARLA/SUMO，不训练神经网络，不生成任何安全证书。把 6C 拆成工程子阶段是为了让每个边界可单独测试，不改变原 Markdown 中 Phase 6C 的总体顺序。

### 输入

- Phase 6B `UnifiedScene`：统一时间轴、track 身份、`valid`/`observed` mask、focal/SDC 区分和 map/source provenance。
- 预测器候选输出：每个 agent 的轨迹候选、一个明确的 joint-mode grouping、与该 joint mode 配对的未来 observation history。
- RuleNet 风险特征：按显式 subject-relative frame 计算的 TTC、纵向间距、横向间距和主体速度。
- CARLA/SUMO 的预期 fixed-step 参数与 actor/sensor frame 记录。

### 输出

- `SceneForecastSample`：encoder 只含 `history_tracks`；future ground truth 单独存放在 `future_targets`。`to_predict` 只标记 benchmark target，不丢弃其他 agent 的有效未来监督。
- `JointModeProposal`：把同一个 joint mode 下的多车轨迹和一个候选 observation history 绑定，避免从独立 marginal modes 做未经定义的笛卡尔积。
- `RuleNetSoftRanker`：输出有界 `[0,1]` 的风险/规则违反启发式分数。
- `rank_policy_branches`：只调整搜索顺序，所有协议分支必须保留。
- `CoSimulationConfig`、`SynchronizedFrameLedger`、`ActorIdentityRegistry`、`SensorDeliveryRecord`：在引入 CARLA/TraCI 依赖前先固定同步合同。

**地图接入限制：**本轮 `encoder_inputs` 仅暴露 map IDs/digest；WOMD 动态信号目前只保留 digest/count，AV2 只记录 scenario-local map archive 的路径/digest。下一子任务必须新增统一 `MapContext`/`MapPrimitive` 和 `DynamicMapTimeline`，将 WOMD `map_features`/`dynamic_map_states` 与 AV2 `log_map_archive_{scenario_id}.json` 的 lane/crosswalk/drivable geometry 解析到统一坐标/拓扑接口后，才允许开展 map-aware 预测训练。

## RuleNet 数学与适用边界

RuleNet 的径向 TTC 代理为

\[
TTC=-\frac{\|p_i-p_j\|^2}{(p_i-p_j)^T(v_i-v_j)}.
\]

该式只在径向距离正在减小时表示正的未来接近时间。若径向闭合速度不大于零，直接把负 TTC 代入 `max(delta-TTC,0)` 会把远离车辆错误地打成高风险。因此实现将不闭合情形定义为 `TTC=+infinity`，重合位置定义为 `TTC=0`。这是一个有明确假设的排序修正，不是碰撞检测；交叉路径仍由预测轨迹/物理 footprint 检查。

归一化违反分数采用 RuleNet 最终 refinement 中的形式：

\[
V=\operatorname{clip}_{[0,1]}\frac{\max(\delta-m,0)}{\delta+\epsilon}.
\]

实现将小量按量纲拆成 `epsilon_ttc_s`（秒）与 `epsilon_distance_m`（米），不复用一个跨单位的 epsilon。

阈值配置默认取论文中的 vehicle-vehicle TTC 1.5 s、vehicle-VRU TTC 1.6 s、VRU lateral gap 1.5 m、longitudinal headway 2 s。纵向阈值为主体速度乘 headway。每个 pair、每个预测步先按 Eq. (19) 取 TTC/纵向/横向三种违反分数的最大值；再按 Eq. (20) 在每个主体的每个时间步对交互对象求平均。为了把时序向量用于 RAMP-D 搜索排序，最后再取主体/时间上的最大值作为 scalar branch score；Eq. (20) 的 per-step 向量仍保留在 report 中。这一步是 RAMP-D 的显式最坏时刻排序适配，不声称复现 RuleNet 完整网络。

纵向/横向间距的坐标轴在 RuleNet 论文中没有给出足以覆盖所有 agent 类别的完整可复现定义。因此本轮 ranker **不自行从速度方向猜测 heading**，而要求几何层显式传入 `geometry_frame` 和距离 trace。几何提取器将在 6C-A2 单独设计和测试。

RuleNet 分数只用于 soft ordering；不允许删除低分模式、删除协议分支、缩小 belief support 或缩小 `U_i^phys`。学习模型输出永远不能替代独立 verifier 的 outer reachable tube。

`interaction_coverage_complete=True` 是调用方对 pair/agent 覆盖完整性的显式声明；ranker 不会因为“收到了至少一条 trace”就自行声称覆盖完整。对于 vehicle-VRU trace，actor_i 必须是 vehicle subject，actor_j 是 VRU。

## 数据监督边界

- WOMD Scenario 和 AV2 Motion 可监督实际记录的 agent history/future trajectory；只有数据实际标注/实际执行的 ego prefix 是观测监督。
- AV2 `focal_track_id` 不是 ego/SDC。官方 AV2 API 以保留 `track_id == "AV"` 标记 ego vehicle；adapter 将其映射为 `is_sdc=True`，并与 `is_focal` 分开。若某个样本缺少 `AV` track，则不从 focal 猜测 ego，只使用 symmetric actor prediction。
- WOMD `tracks_to_predict` 用于 benchmark target mask；`objects_of_interest` 是 Track.id，不是 track array index；`sdc_track_index` 才标记 SDC。
- 只有存在唯一显式 SDC 时，非 SDC future 才能直接标成 ego-conditioned agent-response supervision（`agent_response_targets`）。WOMD 使用 `sdc_track_index`；AV2 使用官方 `track_id == "AV"` 约定。AV2 缺少 `AV` track 的样本才退化为 `symmetric_agent_targets`；任何情况下都不能把 focal track 偷换成 ego。
- `SceneForecastSample` 不把未来标签放进 encoder input。Test/no-future 样本不暴露 future target。
- 公开日志不能监督反事实 agent response、四时钟、消息送达保证、完整 observation support、viability negatives 或 certified margin。后几类标签按论文 Table `supervision` 的 oracle/verifier/simulator 方案产生；失败搜索和单个候选反例不能作为 viability negative。

## 验收标准

1. History/future 输入输出分离，mask 和 target identity 通过测试。
2. Joint mode 保留多 agent 轨迹与 observation history 的相关性。
3. RuleNet score 对无闭合 TTC、零速度、空交互、缺失观测和阈值边界有明确行为。
4. Branch ordering 保留输入的全部协议分支，`support_pruned=false`。
5. 同步配置检查 CARLA/SUMO dt 一致性和 CARLA physics substep budget；ledger 拒绝丢帧/时间错位；actor ID 一一映射；sensor production/delivery 独立记录。
6. 不调用 simulator、不声称真实数据通过、不声称 full-support certification。

## 下一子阶段

先完成 Phase 6C-A2 地图/动态信号 adapter 和 Phase 2–5 数学缺口审计，再实现真实 CARLA 0.9.16 + SUMO 1.20 bridge：单一 orchestrator tick owner、SUMO/CARLA frame 同步、actor ID 对齐、traffic-light 单一 authority、sensor production/delivery timestamps、FourClockInjection 和最小 headless smoke。只有 Phase 6B 两个数据集真实抽样 PASS 且数学 verifier gate 通过后才启动模拟器。
