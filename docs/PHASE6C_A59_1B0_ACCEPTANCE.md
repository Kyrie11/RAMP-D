# Phase 6C-A59/1b-0 — CARLA/Waymax/Traffic clock/Guard/SUMO 联合审计和增量实现

日期：2026-11-23。基线：用户本次 `RAMP-D(1).zip`、论文 `AnonymousSubmission2027(2).tex`、`a59_1a_carla.zip`、`phase6c_a59_1a_20261122T133521Z.zip`。本版不覆盖用户上一轮原始日志，不修改论文模型与声明的安全定理。

## 0. 本轮工程目标与范围

先根据本次**真实** CARLA 证据纠正 A59/1a 的参数提取和车辆测试可信度，再为 A59/1b 的真正混合协议/物理 Post 建立显式、保守的 event/hidden-support/资源冲突前置门槛。保持并行的 SUMO Guard、Waymax 响应、511NY 与 ROADWork 证据级别审计。未做没有 CARLA/SUMO 环境支撑的伪闭环实验；不生成 L_viability、L_margin、L_deadline 等有安全保证语义的标签。

## 1. 上一轮服务器结果与 CARLA 事实

- 服务器 A59/1a：用户上传接受报告的 `718/718` pytest、A59/1a 专项 `19/19` 纯、`4/4` 原生集成、原生 CTest `3/3` 为条件测试通过，不是完整 SC 证书。
- 读取 `model3_actor_metadata.json`：Town10HD_Opt 曾经成功生成 actor `vehicle.tesla.model3`，CARLA 0.9.16，actor id 24；读取 `model3_town06_27.json`：Town06_Opt actor id 129、`RAW_CARLA_TRIALS_CAPTURED_NOT_CERTIFIED`，27 组中 18 组 CAPTURED、9 组 `REVIEW_OFF_DRIVABLE_LANE`。
- 三项不完整：10 m/s steer ×3，15 m/s steer ×3，15 m/s combined ×3。现有 `model3_town06_27_review.json` 正确为 REVIEW，原始顶层捕获状态并非所有 trial 都成功。
- Town06 场地：436 spawn points，13,394 位置候选，2,164 满足原 110m/5°/无路口筛选；Town10HD 155 spawn points，3,221 候选，0 满足。Town06 更适合几何直线标定，不等于车辆在主动转向 2s 内会保持于单车道。
- 独立 A61 诊断（从原始轮位推导，**非正式参数证书**）：两个独立 Town06/Town10 actor 的轴距约 3.0046 m，前后轮距约 1.6668 m，车身 bbox 4.7918×2.16345 m，后轴到 bbox 中心 X 偏移约 1.4156 m，前悬约 0.8069 m，后悬约 0.9803 m。仿真轮位 raw 以世界厘米为解释时与 spawn/actor 位姿吻合；直接把 raw 当米或把首次同步生成时未更新的 (0,0,0) pose 当真会产生严重错误。
- actor `mass_kg_raw=1845`，四轮各 `max_brake_torque_nm_raw=700`、轮胎参数 3.5、半径 37cm，前轮配置 `max_steer_angle≈70°`。这些是 CARLA 仿真配置，不是实车保证界。强制动部分记录约 -27 m/s² 瞬态，必须解释 CARLA 力学/数值/轮胎与实车物理偏差，不能直接用作保守停止能力。
- 原 A59/1a 实际前轮角全部 null：`carla.VehicleWheelLocation.FL/FR` 与 0.9.16 的 `FL_Wheel/FR_Wheel` 不符，原来捕捉 AttributeError 后静默设置 None，造成证据缺失。新版保留明确 `wheel_steer_query_error`。
- 同配置三次试验绝大多数响应近乎完全重复；这能做**数值重现性**，不能估计扰动上下界。原试验低速/中高速产生的响应不同，纯 steer 阶段 throttle=0.17 并非恒速、CARLA normalized steer=0.08 不是 δ=0.08rad。

## 2. 工程实改内容

1. `scripts/a60_carla_actor_trials.py`：使用 0.9.16 正确轮角枚举及显式查询错误；同步生成第一辆 actor 后先成功 tick 再获取 physics/body pose，并记录 capture_frame、请求 spawn pose；加速预触发阶段也执行道路/路口检查；保留 partial capture 状态及完整试验结果计数；允许显式指定短幅 steering 激励 `--steer-fraction`、`--steer-pulse-s`，**默认保持 A59/1a 原设置 0.08/0.8s**；记录天气、世界物理子步和 OpenDRIVE 内容 SHA-256（若接口可用），严格不自动承诺独占锁。
2. `python/rampd_core/a61_carla_calibration.py` + `scripts/a61_review_physical_evidence.py`：独立解析轮位世界坐标与车身坐标的量纲、源和一致性；统计 27 次完整率、每个模式的 status、加速度异常、重复响应、实际轮角缺失。没有任何 `CERTIFIED` 输出；保持源 JSON 只读。
3. `python/rampd_core/a61_hybrid_partition.py`：将多个隐含世界的 exact-model 事件按所有分支并集时间点细分为右连续原子片；不把隐藏规则生效自动当成公共观测；只有显式的 receipt/public-observation token 才生成分叉；新增按时间片起点建立的公共观测前缀支持组，**绝不使用未来 receipt 提前分叉控制**；在同一公共观测组中聚合全部隐藏世界；检查 command-ACK 与事件时间逻辑；输出的是未来 Native Picard Post 必须覆盖的义务，不是已执行物理传播。
4. 同模块增加跨资源冲突的保守声明式矩形 MAY-occupancy 检查，支持不同车辆占用几何冲突资源时返回 `UNKNOWN`；若资源冲突图或 actor roster 不证明完整也返回 `UNKNOWN`。不冒充真实多边形占用证明、实时 Guard 授权或真实物理路径。
5. `tests/test_a61_carla_geometry_and_gate.py`：引入至少 15 项静态测试（包含伪 actor 轮位量纲、零位姿、wheel API、缺失 ACK、隐藏规则/观测混合、潜在跨资源冲突、闭包不完整），加上既有全量测试回归。

## 3. Waymax 动力学与行为现状

现有 `scripts/probe_waymax_dynamics.py` 是 Waymax `InvertibleBicycleModel(dt=0.1, max_accel=6, max_steering=.3)` 在合成初始态上的离散公式一致性实验，甚至含刹车后有符号速度可能跨零的边界案例；`scripts/probe_waymax_response.py` 是基于 WOMD 模板改写两辆合成车的 IDM 路线响应对照。两者不能证明 Waymax 对真实交互、复杂曲线、遮挡、干预反事实的覆盖，也不能把 Waymax (acceleration, curvature) 控制与论文 jerk/steer-rate 六维模型直接画等号。

必须单独标定/转换：Waymax agent 中心坐标对论文后轴参考点；dt=0.1s 的离散数值更新对连续 ODE 的物理残差；κ 和 δ 的转换 `δ=atan(L_w κ)`，离散 a/δ 差分仅做估计不等于真实可达 jerk/ωδ；轮胎摩擦、执行器死区、最坏制动、异常回放的边界及 WOMD log-vs-sim agent 差异。Waymax 的 IDM 反应是沿日志路径的速度调整模型，不是所有行为的最坏情况证据。

## 4. Traffic 时钟/规则/Guard/SUMO并行复核

- **事件时钟 M2/M8**：论文区分物理 onset、规则生效 `τon/off`、issue、publication、receipt、local first observation、controller command 与实际 ACK。511NY 报告时间不等于物理生效，ROADWork 图像不带真实时钟。A61 显式 split 与公共观测分组仅是模型级前置处理，Native ODE 仍未分片传播，不可认为 M2/M8 已闭合。
- **权限与权威 M6/M7**：规则须保留 jurisdiction/scope/version/effectivity/authority 关系；强制干预交通设施还需要部署回执与物理阻挡事实，不能由一次 SUMO signal setter 直接推断。
- **资源冲突 M5/M6**：论文 `G¹` 几何图、`G²` guard（alpha entry，beta occupancy/clearance、direction、capacity）、`G^CC` 任务接受 continuation 图必须同时一致。仅处理一个逻辑 corridor 不等于多边形资源和城市路网中的真实拓扑。车辆完整 swept footprint 入、持续停留、退出以及不同资源冲突对需要在所有时间片证明。A61 新增了跨资源 MAY screen，但 Native 仍对可能合法进入保持 UNKNOWN。
- **SUMO M12**：此前 A58 十二组原始路径经历限定复核，但原始汇总只完整 3/12，9/12 因工作目录复用被写成 ERROR；当前新上传包没有补齐九组报告。原 `probe_sumo_alternating.py` 使用**两条有向 SUMO 车道对应同一个逻辑容量资源**；低摩擦档是速度/制动参数 proxy，不是轮胎—路面实测 μ；车辆侧全路径、物理共享单车道、信号相位实际 ACK、车辆退出和路口排队阻塞仍待在 CARLA/SUMO 联合环境验证。
- **联合时钟 M2/M12**：当前 `a58_cosim_contract.py` 只验证 tick 两端一致，无法自动验证 sensor 采样延迟、事件在步内切换及多 simulator 地图坐标/road-id 对齐。A61 仍**没有真实 co-simulation bridge**。

## 5. M1–M13 长期矩阵（累计状态，不允许虚报）

| 矩阵 | 当前状态 | 未闭合条款 |
|---|---|---|
| M1 区间/MPFR/Picard | 既有单元、原生测试通过（模型条件） | 真实物理误差扰动仍待标定 |
| M2 精确事件时钟 | 新增全世界分割前置编译器 | Native 时步分段传播、事件不确定边界和物理时钟 |
| M3 自车车辆动力学 | 已取得真实 Model3 actor、描述性几何、18/27完整控制 | 实际轮角缺失/执行器边界/摩擦/延迟/残差外包络 |
| M4 其他车辆响应 | Waymax 合成动力学/IDM 历史工具和声明式 envelope | 真实曲线路线/反事实/场景覆盖与角色外包络 |
| M5 资源几何和拓扑 | 单资源 Native 矩形 tube gate + 新多资源冲突筛查 | 多边形图与一般进入/停留/退出连续验证 |
| M6 动态规则权限 | 声明式 alpha/beta/方向/容量 guard | 规则权限版本/权威范围和完整冲突资源模型 |
| M7 控制和执行 Guard | 信号控制状态/候选 Guard 现有实现 | 真实物理阻挡、执行 ACK 和 flow 信号合法性 |
| M8 隐藏协议/消息 | A61 显式同公共观测世界聚合预处理 | 真实 full-support hybrid protocol Post |
| M9 可见性和观测 | 数据接口及候选抽象 | CARLA 遮挡、感知 timestamp、有限支持完整性 |
| M10 非预见 SC/终端 | Native 局部 rank + A61 时间/冲突前置义务 | 完整任务到达策略 + 严格下降 rank + 全分支 |
| M11 独立 Teacher | 合成有限 oracle 存在 | 与真实物理/协议证书绑定、不可行性穷尽证据 |
| M12 仿真可信度 | CARLA 18/27样本、历史 SUMO 轨迹 | 9 个 CARLA 提前终止，9 组 SUMO 报告、联合实时校时、车辆物理标定 |
| M13 八项监督 | 来源、掩码原则在论文/旧实现存在 | 真正符合证据合同的训练标签生产 |

**本轮进展**：M3 的 actor 存在和几何被纠正；M2/M5/M8 新增正式的*前置模型义务*；M1、M10–M13 不得因为回归通过而升级为完整认证。所有 M1–M13 均在真实环境保证口径下有未闭合条件。

## 6. 八项监督的可信程度（本轮不能直接授权完整训练）

| 头 | 本轮数据是否可用 | 缺失证据 |
|---|---|---|
| `L_event` | 合成时钟中某些 EXACT_MODEL 事件可产生**仅仿真**源标签 | 规则权威/生效与 issuance/receipt 真值分开，511NY 不提供真实 onset |
| `L_joint` | AV2/WOMD 的实际行动轨迹可监督事实分支 | ego-prefix 配对干预、agent awareness 和行为外包络 |
| `L_occupancy` | 已有指定几何/轨迹能派生**采样或声明外包络** | 完整动态多边形资源、统一坐标及连续真实占用 |
| `L_observation` | 名义接收/观测模型可产生合成 token | CARLA 真传感器遮挡和生产/投递 timestamp |
| `L_viability` | 正式正/负标签**不可生产** | 完整 SC/任务尾和负样本有限策略类穷尽 |
| `L_margin` | 仅 toy/tube 条件数值，不得当实车 margin | 真实物理扰动内含和连续安全余量 |
| `L_deadline` | 仅声明时钟的区间候选值 | 同候选前缀信息时刻、最晚可启动时刻及 hold 实物保证 |
| `L_causal` | 目前不能生产真实 paired response | 同一外生种子与真实仿真世界恢复、不同 ego 控制、共同日志 |

**下游政策**：任何缺项使用 `UNKNOWN` 和 mask；`CAPTURED`、`PASS` 数值脚本或 `NO_COLLISION_SAMPLED` 都不等价于 `CERTIFIED`；一次不成功的候选策略不是 `L_viability` 负标签。

## 7. 本轮测试证据 / 严格限定

- 本地使用用户旧服务器提供的 `build_phase6c_a59_0/librampd_interval.so` 执行完整 Python 回归：**740/740 PASS**（修改后的上传仓库包含已有新增加的 `test_a60_site_audit.py`；最新服务器历史报告 `718/718` 仍为独立上一轮数据）。
- A61 新增专测：**15/15 PASS**；A60 选点脚本既有专项：**7/7 PASS**。
- 本地原生二进制沿用用户之前发布的构建库：`test_interval`、`test_picard`、`test_abi` 三个可执行程序直接运行均 PASS，Python Native 扩展加载成功；本轮未修改 C++，也未重编译 C++。
- 尝试在本地运行整个嵌套 A59/1b-0 验收脚本时，原生 `cmake` 在用户上传的旧 `CMakeCache.txt` 报告**旧服务器绝对路径**与当前本地路径不符。此故障不影响上述已独立执行的三个原生程序，但**不能声称本地端到端验收脚本通过**。本发布包不包含此旧构建目录，服务器手册改为新建独立 build 目录并全量重新编译。
- 对上传 `model3_town06_27.json` 的描述性脱机审计已通过，输出 `DESCRIPTIVE_PARTIAL_CARLA_RESPONSE_CAPTURED`（不是 27/27、不是安全认证）。
- 本地无远程 CARLA RPC/实际 Waymax/WOMD 数据目录，**没有进行新的现场采集、SUMO/CARLA 同步或真实图物理验证**。

## 8. 下一阶段（不更改长期顺序）

**A59/1b-1**：将编译出的原子片**真正交给 Native MPFR/Picard**，逐片应用右连续 resolved permissions 和 Guard/controller memory，依照完整资源冲突图与连续 actor tubes 检查，支持 observation-equivalence 后继 union；验证每个隐藏世界的时间片总覆盖，重放真实 accepting tail 与下降 rank。只有完整任务接受与所有硬安全义务闭合后，才允许模型条件 SC 证书。

**A5/3c-1/2 并行**：带物理共享单车道与实际出口阻塞的 CARLA/SUMO 独占时钟和车辆控制权；Waymax/WOMD 弯道 leader 路径距离及 agent response；CARLA 显式激励、不同湿/干路面和物理步长，分别标定信号时钟和车辆执行器模型偏差，再填八项监督。
