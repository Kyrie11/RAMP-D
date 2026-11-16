# Phase 6C-A2：WOMD/AV2 地图几何、信号语义与 Phase 4 silence 审计

日期：2026-11-16。**规范依据为本轮上传的 `AnonymousSubmission2027.tex`。** 这是一轮增量开发：延续 Phase 6C-A 预测提案/RuleNet 软排序/共仿真时间合同，不替换原有规划路线。

## 1. 目标/验收合同

| 合同 | 必须满足 | 不能由本轮推出 |
|---|---|---|
| WOMD Scenario vector map | 每个 MapFeature.id/oneof 的 type/geometry/topology 逐条保留；没有几何数据时标记 missing；stop sign 和 signal stop_point 需检查 protobuf presence | 交通权限或形式化可行占用 |
| WOMD dynamic_map_states | 与 timestamps_seconds 同轴，保留精确的 `LANE_STATE_*` 信号 enum、lane ID、时间索引 | 规则 change/issue/receipt/local-observation 四时钟；自车已看到信号 |
| AV2 Motion map archive | `log_map_archive_<scenario_id>.json` 的 lane boundaries + polygon、drivable_area、pedestrian_crossing、connectivity | AV2 Map Change 的真实改变时间、临时封闭规则、通信过程 |
| 坐标参照 | map point、signal stop_point、track 共同使用世界到局部的刚体变换，记录 frame/reference | 原生区间认证/车辆后轴偏移未声明的覆盖保证 |
| train/online 数据隔离 | `encoder_inputs` 不含 future tracks 或 future signal、也不含未证实可感知的信号状态 | 可在离线日志中自动还原真实 ego 传感器观测 |
| Phase 4 silence 安全修复 | 裸布尔 `silence_exclusion_proved` 不足以排除隐藏模式；需要带协议版本、消息身份、保证合同 digest、deadline 和 excluded modes 的证据 | 调用方填写的 SHA、publication/delivery 布尔本身可证明真实通信系统正确 |
| Phase 6B validation | 必须运行 Python 3.10+ 下实际 local tests 和真实 WOMD/AV2 validation；PASS/SKIP/ERROR 明确分离 | 无真实用户数据访问也能声称 data verified |

## 2. 语义来源

WOMD official `scenario.proto`: `Scenario.map_features`, `Scenario.dynamic_map_states`, `Scenario.timestamps_seconds`; official `map.proto`: `MapFeature.feature_data`, `DynamicMapState.lane_states`, `TrafficSignalLaneState`. AV2 scenario-local vector map JSON 按官方 `av2.map` schema 解码，而非把 AV2 Motion 的 lane IDs 当成已解决的规则资源状态。

**数据策略**：Phase 6C-A2 只要求 WOMD `scenario/validation` 和 AV2 Motion `Validation` 少量样本；正式训练再接 training。AV2 Motion 场景自带 vector map，不需要下载单独 1TB Map Change。`training_20s` 先检查场景重叠/窗口来源，不与 standard training 按随机划分混用。两者都不提供完整四时钟因果协议标签。

## 3. 数学不可变条件

论文 Eq. `sc-inner-iteration` 明确：认证 task-winning inner set 需要公共动作、完整支持下的 SafeTube、每类观测的 full posterior union、可重放 terminal completion tail。静态地图 polygon 与 logged signal 仅提供**描述性数据**，不能替代这些证据；抽象观测细分也不能凭空给策略增加观察能力。

Phase 4 允许 silence 观察，但从未收到消息中推断某模式已被排除，须外部可信的 publication + delivery guarantee，并在 latest issue + max delay <= observation cutoff <= local observation 下成立。新 evidence 对每个被排除的 mode 指定 scope。若缺少/不匹配，返回 UNKNOWN，不删模式。

## 4. 完成顺序

1. 修补 Phase 6B 运行和 schema/字段解析问题，保留原回归。
2. 解码 WOMD/AV2 地图几何/动态信号；限制 encoder 只读静态 geometry。
3. 修正 Phase 4 的 silence 缺少独立 deadline evidence 的漏洞。
4. 运行 synthetic adapters、未知/缺失字段、未来泄漏、时间边界和 local map transform 回归。
5. 检查真实 WOMD+AV2；只有两个数据集都 PASS，A2 才获得 server real-data acceptance。

**后续**：先针对最新论文实现 `W_H^{SC}` finite rank/terminal-tail 和 `V_H^{SC}`/CCG 的独立证据与完整测试，再在 Phase 6C-B 真实连接 CARLA 0.9.16/SUMO 1.20。先不启动模拟器。
