# Phase 6B 计划：真实 validation 记录解析与四时钟注入

Phase 6B 把 Phase 6A 的目录清单推进到少量真实记录，但仍然不训练预测网络、不把数据集概率当作形式化支持，也不启动 CARLA/SUMO。输入只取 WOMD Scenario `validation` 和 AV2 Motion `Validation`，每次最多抽取 1–10 个场景。

## 本轮目标

1. 用可选依赖解析 WOMD Scenario protobuf，验证 `scenario_id`、严格递增 `timestamps_seconds`、`current_time_index`、`Track.id`、`sdc_track_index`、`tracks_to_predict`、`dynamic_map_states` 和 10 Hz 元数据。`Track.id` 与 tracks 数组索引始终分开保存。
2. 解析 AV2 Motion 的 scenario parquet 和同目录 map archive。把稀疏的 per-track rows 补成全局 dense timestep 轴，保留 `valid=False` 和 `observed=None` 的缺失槽位，不以零填充。
3. 保留中心参考点；只有调用者提供显式的后轴偏移时才应用
   \(p_r=p_c-R(\psi)o\)，并且只有提供角速度时才应用
   \(v_r=v_c-\dot\psi R(\psi)J o\)。缺少几何或角速度时在 metadata 中明确标记，不静默套用车型尺寸。
4. 用 `FourClockInjection` 显式记录 `t_activation`、`t_issue`、`t_receipt`、`t_first_local_observation` 以及 simulator/sensor frame 和 production/delivery time。任何 clock ordering 只有在 `declared_relations` 中声明后才能进入 `ClockTrace`。
5. 对抽样源文件记录完整 `content_sha256`、parser version 和 schema version，支持之后的场景重放。

## 明确边界

WOMD/AV2 的 10 Hz 采样和 `observed` mask 只描述数据记录边界，不提供物理规则生效、消息发布、消息送达和首次局部感知四个协议时钟。`dynamic_map_states` 也不能被解释为 receipt。`online_view()` 仍是唯一可以交给在线预测/规划模块的前缀视图。

无 TensorFlow、Waymo protobuf、parquet engine 或 AV2 包时，reader 报告显式 `SKIP`；不能用目录存在或合成轨迹冒充真实解析通过。
