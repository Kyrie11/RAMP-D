# RAMP-D Phase 6C-A59/1b-0K — 实际控制实验复核与证据拒收门槛

## 1. 严格的阶段边界

输入：用户提供的 `AnonymousSubmission2027(7).tex`、A59/1b-0J 完整源包和 `town06_5ms_brake_raw.json` / `town06_5ms_brake_review.json`。

**本阶段完成：** 真实的 CARLA 0.9.16 Town06 Tesla Model3 5m/s 单组制动采集；独立的速度差分、加速度、轮制动扭矩量级、离线采样车道边界复核；修复 smoke 缺少 isolated-world 声明的安全保护；输出可复算图像；新增 8 个纯 Python 回归用例。

**本阶段未完成：** CARLA 连续转向/联合控制占道验证、真实制动力标定、执行器延迟包络、真实轮胎附着标定、摩擦圆保证、分段 Native Picard、一般资源拓扑、SC 认证、八个正式训练标签源。

## 2. 实际日志结果

- 原始单组采集 `CAPTURED`，独立 A64 审计 `DESCRIPTIVE_SINGLE_CONTROL_SMOKE_CAPTURED_NOT_CALIBRATED`。
- 触发水平速度约 4.892842 m/s；首次制动时速度仍短暂提高，之后发生剧烈减速。
- CARLA 纵向加速度峰值约 -26.934569 m/s²，逐帧水平速度差分约 -26.934568 m/s²；二者同源于 CARLA 物理求解，不能视为两个独立实验。
- 四轮最大制动扭矩 700 N·m，半径 0.37 m，质量 1845 kg，对应**简化平路扭矩量级比较**约 4.101663 m/s²。比例约 6.567。
- 比较模型未包括物理引擎所有力、轮胎/路面响应及车辆状态，因此**不是有效保证减速度上界**。差异只触发 REVIEW；必须先排查物理参数的语义与执行器映射，并在多速度、多摩擦工况重试。
- 原始日志的 66 个离散瞬时包围盒都位于声明式单车道范围内；并未计算两帧之间的连续扫掠，不能用于 M5 最终证明。

## 3. 设计修复与独立测试

`python/rampd_core/a65_carla_conformance.py`：`audit_brake_conformance` 既检查 A64 描述性采集状态，又按记录轮位的单位（半径厘米）建立量纲合理的**参考比较**；独立计算前后相邻车速差分，检查每帧有限性、轮位、质量、单帧传感器与速度不一致、车道数值裕度和潜在不可解释的减速度；输出 `physical_certified=false, actuator_calibrated=false, safe_training_labels_allowed=false`。未发现大偏差时同样不授予认证。

`--mode smoke` 必须同时具备 `--confirm-isolated-world` 和 `--confirm-exclusive-tick`。此为运行保护，不自动证明远程不存在其他 tick 客户端。

`a65_plot_carla_smoke.py` 与 `a65_plot_carla_lane.py`：分别绘制命令、速度、加速度、瞬时车道裕度，以及真实 CARLA 位姿和车辆矩形叠加的**近似直线车道图**。后者不是 OpenDRIVE 真实道路面，也不是全时间扫掠。

## 4. 下轮 CARLA 严格顺序与预期结果

1. **保持原始 5m/s brake 数据**，先复核 CARLA `VehiclePhysicsControl` 的制动扭矩、手刹、ABS/物理效果、天气/摩擦、速度差分、刹车命令和引擎实际制动语义。构造 torque-only 与 CARLA 物理差异的解释，不能通过改大扭矩上界或者忽略 26.9 的尖峰伪造通过。
2. **5m/s steer 短脉冲单组**：使用 `steer-fraction=0.03`、`steer-pulse-s=0.15`，独立记录 40 帧、实际双前轮角/横摆角速度、采样边界与 2D 车身轨迹。如实际离开车道，保留 `REVIEW_OFF_DRIVABLE_LANE`，不得放宽规则；应先调整试验场地/安全方案，不能降低标签验收标准。
3. **5m/s combined 单组**：与 steer 使用相同短脉冲，记录制动与转向相互作用，并保留同一 CARLA world settings、asset、step 的物理配置 hash。
4. **9 种工况 × 1，继而 27 种 × 3**：前提是所有单组完整采集且物理模型异常得到解释或明确隔离，不得把弱短脉冲与旧 0.08/0.8 s 试验混为同一实验分布。
5. 必须分出 calibration、held-out conformance 集；有限运行次数下的无反例覆盖不能构成无条件保证界。

若 steer 仍失败：上传 `a65_plot_carla_lane` PNG、原始 JSON；若需排查车体/障碍物/车轮接触，最好补充 frame-synchronized 的 bird's-eye CARLA RGB 视频（带 frame IDs）和 OpenDRIVE 车道多边形导出。简单视频不足以代替米制几何。

## 5. 同步数学主线 A59/1b-1 与并行 M1–M13

| 项 | 当前 | 下一真实工程交付及独立验收 |
|---|---|---|
| M1 区间/Picard | 基础证书与跨片交接检查 | 对每个隐藏世界、分片调用真实原生 MPFR/Picard，验证整个时间片与终点外包络，重放证书 |
| M2 Traffic 时钟 | 有理数分片 | 规则生效/发布/接收、信号命令/ACK 与资源物理时钟按同一片运行，检查片内事件不得遗漏 |
| M3 自车物理 | CARLA actor + grounded + 单组 brake | 轮位、制动、转向、轮胎/路面工况、执行器延迟区间与真实模型残差外包络 |
| M4 其他车 | Waymax IDM/日志基础 | jerk/steering-rate 与 acceleration/curvature 显式适配、轨迹事实与反事实分开、配对 falsification |
| M5 几何资源 | 瞬时矩形/条件扫掠审计 | 一般多边形连续扫掠，入/留/出状态一致，边界反例回放 |
| M6 Guard | 声明式多世界权限 | 权威/管辖/版本/生效/容量/方向、资源冲突图与物理信号 ACK 完整对齐 |
| M7 控制执行 | controller/interlock 状态 | 控制器唯一所有权、实际执行与命令收讫的不同时间和状态 |
| M8 隐藏协议 | 支持分组及有理数片 | 全部世界的协议分支按公共历史聚合，缺失任何分支返回 UNKNOWN |
| M9 真实观测 | 声明 token | 可见性、遮挡、相机/传感器时间戳、消息真实 receipt 与 silence 截尾 |
| M10 SC | 条件 rank/hand-off | 完整公共前缀、观测分支后继、有限接受尾策略与 rank 严格递减 |
| M11 Teacher | 尚无独立全策略类不可行证明 | 小实例穷举 + 对照 verifier，正标签证书/负标签完整 oracle，不可判定掩码 |
| M12 联合仿真 | SUMO 12 条原始轨迹、3 完整控制报告 | 先补齐 9 条控制报告，再在实际共享道路实现单一 master tick 与 ego 唯一控制权 |
| M13 监督 | 来源协议与 inventory | 8 个头逐字段质量门槛、哈希/时钟/地图证据链，UNKNOWN 不产生正负监督 |

### 数据集细分与因果纪律

论文的 8 项损失应区分独立监督来源：`event` (发生/发布/生效区间)，`joint` (日志事实 vs 配对反事实)，`occupancy` (带时间的真实 actor-footprint/资源多边形)，`observation` (遮挡、观测、receipt)，`viability` (完整 finite teacher)，`margin` (validated tube 下界)，`deadline` (同一策略前缀时间上下界)，`causal` (同外生种子配对干预)。511NY/ROADWork 是报告/视觉线索证据，不应当直接作为精确的物理生效/接收时间或封路米制几何。

**结论：** A59/1b-0K 不是 A59/1b-1 完成。CAPTURED 代表记录完整；PHYSICAL CERTIFIED 必须待后续 Native、CARLA/SUMO 与独立 oracle 共同闭合。
