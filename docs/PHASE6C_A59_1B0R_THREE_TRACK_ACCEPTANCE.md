# Phase 6C A59/1b-0R / A72：数学、物理、证据监督及并行模拟器独立验收

2026-11-24。代码基线是用户上传的完整 `A59/1b-0Q`；本轮继续修改和实际读取新上传 `a71_sumo_campaign.zip`、`a71.zip`、CARLA 纯制动、两份 ROADWork 论文和 511NY 数据字典。**局部软件验证 PASS 不等于实体物理或完整 SC 认证**。

## 1. 一眼看懂的验收边界

| 目标 | 当前实证结果 | 尚缺结果 | 合法结论 |
|---|---|---|---|
| M1 原生 6D | 2 隐藏世界 × 2 精确切片，4 份 MPFR 证书；本轮旧 Native SO 重放证书 | 所有他车轨迹、真实误差外包络、多控制策略 | 声明模型内的 Native tube 条件验证 |
| M2/8 时钟、公共历史 | 本轮从隐藏事件声明重建切片，再核对所有 Native `world/start/end` 与事件 digest | 实际完整合法来源/观测关系 | 模型支持集身份审计 |
| M5/6 资源/Guard | 多边形自交/自触碰拒绝；远端资源保守排除，近端 UNKNOWN | 来源权威地图、多参与者进入—占用—退出完整证明 | 不授权法律资源进入 |
| M3 CARLA | 0.15、0.30 纯制动与联合控制各一份完整配对；0.45 联合有记录 | 0.45 纯制动，6 格至少 3 次，物理异常解释 | 分工况对比，不发布保证制动力 |
| M4 Waymax | 30/60/120 三档实际官方 IDM 合成双车输出 | 真实 WOMD actor 动力学响应支持、道路曲线、反事实稳健验证 | IDM 超参数敏感性，非实车 |
| M7/12 SUMO | 四种配置×三个种子 12/12，9000 ticks/run，36002 信号记录/run | 物理一车道与 CARLA/SUMO 同步，真实物理 ACK | TraCI 信号时序和逻辑资源状态 |
| M11/13 数据 | 511NY 1522 标准化报告，1521 有效辅助，1 缺事件类别隔离；ROADWork 原始图像转换入口修复 | ROADWork 官方 COCO 批量执行，真实摄像头时空配准；独立 Teacher | 可训练**受限辅助任务**，全部正式 SC 标签仍 masked |

## 2. 数学主线，安全集与真正缺失的定理义务

论文中的实体安全集合应当同时检查 **碰撞/道路资源、动力学与摩擦、Guard 入内许可 α/内部继续许可 β、方向 d、容量 κ、控制器状态 p、隐藏协议和时钟**。这些约束按世界 ω 与连续时间 t 合取；仅某一时刻的车道中心位置安全不够。

SafeTube(B,u) 需要任意隐藏世界 ω、任意容许扰动、整个连续区间 [t_i,t_{i+1}] 的外包络均在 X_safe 中，包括所有他车可达管与时变资源。后继 Succ_P 必须先在同公共观察历史下合并各世界支持再选公共控制。Goal-conditional winning 的 W0^SC=Kterm^SC 只有有真实任务接受尾策略才可加入；每个非终端公共动作对全部观测后继必须使继承的 rank 严格下降。安全不变集 S∞ 与 goal-winning W_H^SC 不可混淆；UNKNOWN/SAFE_ONLY 不能变正负 viability 监督。

**本轮数学代码：** `a72_native_world_resource.py` 用独立 `partition_clock_worlds` 重算所需所有世界切片；检查报告/证书集合、事件声明完整摘要、公共历史、时间范围，再调用实际 `replay_certificate`（没有从摘要代替数学重放）。修复 `a71_native_polygon_geometry.polygon_vertices`：此前自交资源边界未拒绝，现用 Fraction 的非相邻线段交叉/触碰测试拒绝无效道路资源几何。离线上传四份 Native 微型证书远端多边形条件排除，近端 UNKNOWN；不对资源进入规则、其余车辆或 SC 尾策略作结论。

**必须做的下一阶段：** 独立生成包含实际地图资源、完整 actor roster 与他车响应外包络的多车分段物理 Post；路径穿越资源边界时将该边界隐含于精确事件细分或连续监视器；对 α/β/d/κ/p 与命令 issue、controller state readback、physical effective ACK 分开记录。对每一可能公共观测先合并支持再计算后继，最后验收终端任务接受、所有 rank 下降。反例：两个不可区分世界规则切换、迟到 ACK、最初已有对向占用、容量超限、两帧间资源进入、同一观察下使用不同控制、rank 不降与停车但不达目标。所有门槛必须从单个完整管线审计，不得各模块 PASS 拼接为 SC PASS。

## 3. CARLA 物理实测与制动误差来源

A71 的原始纯制动 0.15 与联合 0.15 匹配；本轮额外读取上传的纯制动 0.30，与联合 0.30 进行第二次对照。0.15 的控制后水平速度最大差值 0.3741203 m/s、行驶中 (v≥1m/s) 减速度约 2.286 vs 2.380m/s²；0.30 的控制后水平速度最大差值仅 0.0028458 m/s，二者都有约 -26.93m/s² 的非正常巨大负加速度瞬态。两档都不能认定高峰值是实际纵向制动能力，也不能由差值量化轮胎横纵耦合：可能包含积分步长、低速停车钳制、引擎/变速箱、轮胎接触、物理子步和数值采样。

新增 `a72_physics_factorial.py` 为 2×3 六格设计分别管理实际执行制动与转向，拒绝单格重复原始 JSON、缺失独立重复和错误跨工况混合。**本轮额外修复** `a71_carla_factor_pairs`: 旧审计没有验证制动窗口内油门是零、以及发命令在 tick 之前，可能将额外油门试验错误视为纯制动。

下一步先补 `brake=0.45,steer=0` 一格，完成各格三次独立试验；分车速 v≥1m/s、0<v<1m/s、停车零速统计每阶段加速度、停车时间距离、前轮角、轮转速（若可读）、引擎/实际控制快照及固定 dt。**后续分别改变** dt=0.05 vs 0.025、CARLA 摩擦参数、5/10/15m/s，不与同一 2×3 工况混合。这些数据限定 CARLA 在给定参数/道路条件的描述性动力学残差，不会自动证明真实车辆保障摩擦或最大制动界。

## 4. SUMO / Guard / Waymax 真正的实测

`a71_sumo_campaign.zip`: 12 个 `.json` 汇总、12 个 `.signal_review.json`、12 份完整 TraCI 信号源与 9000 步逻辑资源数据；独立重新调用 `audit_sumo_signal_trace` 检查 12×36002 行、每 tick 命令及读回、无丢帧；额外逐步拒绝相反方向逻辑占用同时出现、错相位进入、实际车辆未全部离开。新逻辑每组均无矛盾；**但两个方向在 SUMO 中仍是不同道路边，未建立物理共享车道**。原探针的 `lower_friction_proxy` 是仿真 decel 和流量变化，不是实测 μ。

Waymax 当前指定的 `/.../uncompressed/tf_example/validation/validation_tfexample.tfrecord-00149-of-00150` 是支持 Waymax loader 的有效验收入口；`probe_waymax_response.py` 实际把模板的两车轨迹覆盖成一个合成直路双车。lookahead=30/60/120 改变 IDM 内部距离与跟驰响应，不同的输出不能当作三种真实 WOMD 场景。新增 `a72_waymax_sensitivity.py` 在同实验协议下比较 3 档，防止误改车长、初始位置或算法源码。**新增** `a72_probe_real_waymax_scenes.py` 使用相同 Waymax dataloader 直接读取原始真实车辆轨迹，而不再覆盖轨迹，限定 1–50 个场景用于事实场景库存；实际服务器运行待用户完成。事实/反事实严格分域，真实场景标签应保留原始 Scenario ID 和 train/validation 归属；如需完整活动地图、交通参与者和更长片段，优先解析 WOMD Scenario protobuf。无需一开始全量读取 validation 150 个 shard 或训练 1000 个 shard。

## 5. 511NY + ROADWork → 两层监督而非伪造交通封闭真值

用户上传的 DOT 数据字典注明 Event Type/Organization/Facility/Direction、Create Time（在 511 系统建立）、Close Time（在系统关闭）、位置和文本；不包含物理封路生效、封闭边界和车上收信时间。A71 的 10000 行输入有 1522 条规范化报告，但第 961 条 event_type 为空导致旧转换全批 REVIEW。新增 `a72_export_auxiliary_v2.py` 流式输出 1521 条有效 + 1 条原样来源 SHA 隔离，不伪造类型/来源时间；本轮同时新增 `a72_auxiliary_pretraining.py`，产出**报告类别分类**的有来源辅助样本，并保守按机构+道路+月份分家族隔离（当前 1521 行、891 个声明家族）。该家族隔离仍是启发式，不能保证同一真实事故在不同月/机构间完全不泄漏。`a72_incident_intervention.py` 可以将真实报告的类别作为模拟事件选择的条件，但 effectivity/issue/receive 必须由仿真协议明确独立提供，绝不复制 511 报告时间。

ROADWork ICCV 2025 提供 4375 个视频、9650 标注图像、129017 个有驱动路径图像、15 类施工区物体及多种 TTC 标牌语义；其 `gtFine` 语义分割标签属于图像像素，物体框/标牌文字/行驶路径不等于米制道路封闭边界。原 `roadwork_files.json` 是**文件清单**而不是 `export_a58_roadwork_templates.py` 产出的 GPS 分组模板，因而 A71 报 0 行。新增 `a72_roadwork_real_pipeline.py` 串接官方 `annotations.zip`+`images.zip`+`gtFine` 对齐、GPS split / 视频分组、视觉模板导出及安全辅助监督。此轮用户未提供可直接检验的 COCO annotation ZIP 的挂载路径，故该真实步骤仍需服务器运行（或上传解析好的结果）。新辅助预训练代码保留 ROADWork 官方 GPS train/val，不允许同一视频仅因注释文件哈希不同而落在两侧；针对真实图像的识别、遮挡、TTC 导向可逐渐开放受限辅助头，但不能把可见交通标志直接当作 legal authority 的真值。

正式八项监督来源推进次序：
1. `L_event` 的仿真权威事件链 + 511NY 弱报告类别先验（严格区分）。
2. `L_joint` 的 AV2/WOMD 事实轨迹 + Waymax 模型内反应，标注真实/合成域。
3. `L_occupancy` 的经校准资源几何 + 完整 actor footprint，ROADWork 视觉辅助。
4. `L_observation` 的 ROADWork 视觉可见性辅助 + CARLA 实际感知/遮挡和 message receipts。
5. `L_causal` 的同外生种子、成对 A/A 与 A/B 干预，对方实际仿真重算。
6. `L_viability` 的完整 SC 正证书或完整有限策略类不可行负证明。
7. `L_margin` 的可信物理不确定性模型与 Native 全时段下界。
8. `L_deadline` 的公共信息时钟、资源窗口及 rank-preserving policy 联合验证。

这里单独给出了从真实数据生成“辅助训练样本”的实际代码，并非宣称 M13 八项正式安全监督都已经有标签。

## 6. M1–M13 当前状态

| M | 当前受限进展 | 下一关 |
|---|---|---|
| M1 | 两世界 6D MPFR/Picard 四片证书已重放 | 多参与者在同事件片连续 Post |
| M2 | 精确世界切片事件 digest 与 TraCI tick | 真实规则生效、消息接收和 controller ACK 四时钟 |
| M3 | CARLA 2 个配对干预档；未标定 | 补齐 2×3、重复、低速/接触模式/数值步长区分 |
| M4 | 官方 Waymax IDM 三档合成结果 | 原始 WOMD 真实 actor 响应、真实地图曲线与 envelope |
| M5 | 精确有理数声明多边形 + 无效拓扑拒绝 | 地图校准、动态资源与所有车辆连续占用 |
| M6 | Guard 入/留/出、容量、初始占用及离散 ACK 屏障 | 所有可能的资源监控转移和权威版本 |
| M7 | SUMO 实际 TraCI 命令/即时与下步读回 | 现场物理执行/屏障/独立互锁 ACK |
| M8 | 两隐藏世界时钟与模型内公共控制一致 | 完整后继、不提前使用未来观测 |
| M9 | ROADWork 视觉语义、消息合同 | 真实传感器遮挡、观测收发时刻及静默支持 |
| M10 | 有限 rank 必要屏幕 | 真正终端任务接受 policy 和不重置 rank |
| M11 | 独立证据语义/有限模型工具 | 完整独立 oracle 正负证明 |
| M12 | 12/12 SUMO 逻辑实跑、三 Waymax 合成 | 真实物理共享路网、CARLA/SUMO 注册与同步 |
| M13 | 1521 条 511NY 辅助数据与标签隔离、ROADWork 实际导出接口 | 各项正式 label factory 与可信 SC / observation / causal 证据 |

**本轮验收**：本地 Python 992/992 无 skip/fail，23 个 A72 新反例全部通过；历史 native SO 的 3 个 C++ 程序直接执行通过。Native SO 未从本轮 C++ 重新编译，用户 CARLA/SUMO 服务端未由本环境启动。各八项 formal masks 仍为 0，全局 SC `CERTIFIED` = false。
