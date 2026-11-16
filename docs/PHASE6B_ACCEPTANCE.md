# Phase 6B 验收报告模板

## 验收门

- [ ] WOMD validation 至少 1 个真实 Scenario 被解析，`scenario_id`、时间轴、current boundary、Track.id/index、SDC 和 tracks-to-predict 可重放。
- [ ] AV2 Validation 至少 1 个真实 parquet 被解析，scenario/track/timestep/observed/category 和同目录 map archive 已绑定。
- [ ] AV2 `track_id == "AV"` ego convention（若存在）与 `focal_track_id` 分别报告；不得把 focal 自动标为 SDC。
- [ ] 所有缺失状态保留 `valid`/`observed` mask；在线前缀没有 current index 之后的状态。
- [ ] source shard/file SHA-256、WOMD record SHA-256、canonical scenario digest、schema version、parser version 已分别写入 summary。
- [ ] 四时钟只能通过 `FourClockInjection` 注入，未从轨迹或 dynamic map 状态推断。
- [ ] 参考点转换的偏移来源和几何不确定度显式记录；没有可靠偏移时保持 `bounding_box_center`。
- [ ] `simulators_used=false`；CARLA/SUMO 留到 Phase 6C-B。

## 当前本地结果

本轮纯 Python adapter/Phase 6C-A dependency-free harness 结果为 **47 passed**；它不代替 native interval/backend 测试，也不代表真实数据已通过。服务器报告中 WOMD 为 PASS、AV2 因缺少 `pyarrow` 为 SKIP，故 Phase 6B 整体验收仍未通过。安装 `.[datasets]` 后重跑真实数据脚本。未获得 WOMD 与 AV2 双 PASS 前，不得将 Phase 6B 标记为 `real_scene_verified` 或 `full_support_certified`。

## 失败分流

- `SKIP`：数据路径或可选 parser 缺失，安装/修正路径后重跑；新脚本返回 exit code 3，避免被 shell pipeline 当作通过。
- `ERROR`：记录 schema、时间轴、ID、map pairing 或 mask 违反合同；先修 parser 或数据 manifest。
- `PASS`：真实样本和所有验收门均满足，才可接受 Phase 6C-B 的真实 simulator bridge/smoke。Phase 6C-A 纯合同可以先做，但不代表数据门已经通过。
