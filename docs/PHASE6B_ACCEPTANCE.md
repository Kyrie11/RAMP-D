# Phase 6B 验收报告模板

## 验收门

- [ ] WOMD validation 至少 1 个真实 Scenario 被解析，`scenario_id`、时间轴、current boundary、Track.id/index、SDC 和 tracks-to-predict 可重放。
- [ ] AV2 Validation 至少 1 个真实 parquet 被解析，scenario/track/timestep/observed/category 和同目录 map archive 已绑定。
- [ ] 所有缺失状态保留 `valid`/`observed` mask；在线前缀没有 current index 之后的状态。
- [ ] source content SHA-256、schema version、parser version 已写入 summary。
- [ ] 四时钟只能通过 `FourClockInjection` 注入，未从轨迹或 dynamic map 状态推断。
- [ ] 参考点转换的偏移来源和几何不确定度显式记录；没有可靠偏移时保持 `bounding_box_center`。
- [ ] `simulators_used=false`；CARLA/SUMO 留到 Phase 6C。

## 当前本地结果

在没有 pytest、native interval backend、TensorFlow、Waymo protobuf 和 parquet engine 的最小开发环境中，本轮用 synthetic record fixtures 验证 adapter 合同，动态 harness 结果为 **11 passed**；真实数据状态由服务器执行 `scripts/validate_phase6b.sh` 生成。未获得真实抽样前，不得将 Phase 6B 标记为 `real_scene_verified` 或 `full_support_certified`。

## 失败分流

- `SKIP`：数据路径或可选 parser 缺失，安装/修正路径后重跑。
- `ERROR`：记录 schema、时间轴、ID、map pairing 或 mask 违反合同；先修 parser 或数据 manifest。
- `PASS`：真实样本和所有验收门均满足，才可进入 Phase 6C 的 prediction proposal、RuleNet 软排序和同步 smoke test。
