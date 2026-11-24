# RAMP-D A73 / Phase6C-A59/1b-0S 三主线阶段验收

## 1. 目标与边界
本轮基于上传的 A72 release、论文 TeX、开发历史、车辆参数、三个 A72 结果 ZIP 和数据集论文。目标：独立证书绑定、多参与者连续占用及公共后继参考模型；物理响应分阶段审核；修复 Waymax 数据入口；区分 SUMO 规则版本/命令/采样占用；提高真实事件辅助数据质量。按照目标→实现→测试→失败案例→验收执行。不是完整 SC 认证，不发布实际车辆安全能力。所有正式监督掩码保持 0。

## 2. A72 结果复核（上传证据与本轮实际复算分离）
- Native：历史报告有 2 worlds×2 slabs 的 MPFR/Picard 声明模型、far exclusion、near UNKNOWN、缺片及非法多边形反例。本轮上传无 fresh native CTest/JUnit/certs，无法重新核验历史证书。
- Waymax：30/60/120 三档合成 IDM，首响应加速度 -3.312616/-3.312616/-3.537388 m/s²，最小采样间隙 7.9321/8.0992/8.1622m。真实 5 场景探针 AttributeError，0 个成功；合成替换轨迹不能代表实车反事实。
- SUMO：上传重放汇总 12/12、108000 ticks、36002 signal records/run、867 departures=arrivals、无逻辑矛盾；本轮未获得 12 组原始全量 TraCI，不能称重新运行。两个方向不同边，逻辑共享不等于物理共享车道，模拟器读回不等于物理 ACK。
- CARLA：新 0.45 纯制动真实 raw，触发速度 4.892842m/s；区间两端≥1m/s 最大减速度 26.93497m/s²；持续≤.01m/s 起点 .35s，采样路径 1.039m。纯制动 .15 fixture 2.28579m/s², 6.597m；联合 .15 2.37960,6.570m；联合 .30 26.92736,1.042m；联合 .45 26.92656,1.039m。纯 .30 raw 未上传，仅历史报告。异常不要求转向且早于停车；不是轮胎纵横耦合证据。历史并非 18 个独立重复。
- CARLA 名义 actor：轴距3.0046165、长4.7917795、宽2.16345、前悬.806899、后悬.980264、后轴到盒中心1.415626m，质量1845kg、配置轮半径.37m、单轮扭矩700Nm、tire_friction3.5、前轮最大转角70°。与厂家/ScenarioRunner/CommonRoad 分域。不是实车可保证制动/转向或附着界。需完整 PhysicsControl、低级轮/接触、子步、传动、真实车辆独立数据与标定误差。
- ROADWork：5318 train/2098 val images；60757/21261 instances；每 split 仅解码3张，1个 val 零尺寸框。194 shared groups、2533 train shared images，旧 gate 后 train2490 val2098；保留 train 缺 GPS2043，已知447；69 train visual templates，travel alteration 多标签（Partially Blocked63、Fully Blocked14、None5、Lane Shift1），计数可重叠。原始 annotations 尚未上传，严格新 site gate 尚未运行。
- 511NY：1522 normalized，1521 A72 auxiliary，缺类1隔离。A73 额外数字 code 531×16、2001×5 隔离；1500 retained，290 路线家族，train1207/val138/test155；2010–2022 样本报告时间，overview 只覆盖2010–2012，需当前数据字典。路线名称规范化不能证明真实事故或地理隔离。与 ROADWork 合计1569 weak rows，359 families，21新隔离。非已训练模型。

## 3. 实现与独立测试
| 模块 | 代码 | 验收范围 |
|---|---|---|
| Math reference | a73_joint_reference.py | Fraction 连续线性矩形交会；多车资源容量、冲突和 Guard；先公共动作后观测并集；有限目标 rank。不是论文 6D 全局验证。 |
| Native context | a73_native_context.py, a72_native_world_resource.py | 独立声明物理参数/控制/扰动/初态、精确时长及跨片交接；仍必须 Native replay。 |
| Native multi | a73_native_multi_actor.py, a73_native_multi_microcase.py | 全时片 hull 与潜在占用，保守容量/Guard；2 actors×2 worlds×2 slabs，真实 native gate 待服务器。 |
| Physics | a73_physics.py, a73_carla_campaign.py, a60_carla_actor_trials.py | 每一重复记录审计、采样 digest、分速度区间、持续停车、gear/handbrake/reverse/物理配置；新实跑待服务器。 |
| Waymax | a72_probe_real_waymax_scenes.py, a73_womd_scenario_inventory.py | dataclasses.replace、真实状态完整性、Scenario ID/record digest；Waymax 实际运行待服务器。 |
| SUMO | a73_guard_trace.py, probe_sumo_alternating.py, a73_review_sumo_metric.py | command epoch、实际 actor sampled geometry、哈希绑定、非空占用；非连续/共享物理路网/物理 ACK。 |
| Evidence | a73_auxiliary.py, a73_roadwork_site_split.py, a73_reaudit_sources.py, a72_roadwork_real_pipeline.py | 数字代码隔离、路线家族、整视频 GPS 隔离、空模板 fail closed；真实上传辅助记录已复算。 |

新增测试 41/41；旧独立 pure regression 29+19+11=59/59；合计100个测试执行成功（不表示仓库全量）。CMake fresh configure 已尝试，因 MPFR/GMP development files missing 失败；无本轮 Native library/CTest/full pytest 数据。纯模块运行器显式不加载 Native package 初始化，不能用于验证 Native；服务器有 Native 时使用正常导入。当前环境未运行 CARLA/SUMO/Waymax/WOMD 全量。报告附 JUnit/编译错误/离线原始输入 hash 与输出。历史 A72 992 项不计入本轮。

## 4. 失败与纠正
- 证书与真实问题绑定不足：时间片、control、disturbance、initial/handoff 必须重新检查，不接受相同报告哈希替代。
- 两端安全但区间内碰撞：使用闭区间 exact intersection；同一观测合并全部后继，不分别求每个世界策略。证据缺失和保守拒绝都只能 UNKNOWN，有限 oracle 的负例范围仅为声明完整的有限模型。
- 旧 CARLA 只对首个配对完整核对：所有重复逐条核验。相同 samples 仅改 metadata 不算新独立证据。高减速度并非零速-only/steering-only；尚缺轮胎、引擎、接触遥测及干预因果辨识。
- Waymax API 错误已经代码修复；实际安装版本、数据加载、场景完整性待跑。
- SUMO 逻辑边非共享物理 lane；采样占用不可作为连续 sweep；规则版本与 command epoch 不同。
- 511NY 数字 code/同一路线跨机构跨月，ROADWork 视频/GPS 泄漏；隔离未知类别、严格家族划分，严禁凭视觉标志推断法律权限。

## 5. M1–M13 长期验收矩阵（继承 A72 定义，不重置门槛）
状态：P=局部已实现/验证；R=真实运行或权威证据待补；U=完整数学/物理义务未闭合。无任何 M 宣布最终收敛。

| M | A73 状态与进展 | 下一道独立门槛/拒绝条件 |
|---|---|---|
| M1 原生6D传播 | P/R，声明绑定+多 actor Native 接口，41 pure 的部分通过 | fresh native 8/8 tubes；完整连续物理/扰动 envelope，缺片或 undercoverage UNKNOWN |
| M2 隐藏时钟 | P，独立时片和命令 epoch | rule effectivity/issue/receipt/ACK 全源时钟、对齐误差及同刻次序 |
| M3 CARLA物理 | P/R，新增纯.45、逐重复审计 | 6×3 每格，dt .05/.025 独立；速度/摩擦/轮胎响应；不保证实车制动 |
| M4 Waymax响应 | P/R，实际读取失败修复，Scenario 原始入口 | 5场景通过、heldout residual、AA/AB与多车响应外包络 |
| M5 资源几何 | P/R，连续平移矩形、Native hull、SUMO采样 | 权威地图、全部 actor 连续 sweep、动态资源；非法多边形/非空占用 gate |
| M6 Guard | P/U，有限 entry/stay/exit/direction/capacity/ACK | 权威规则 α/β/d/κ/p、完整连续监视器，需求量非单位时独立验证 |
| M7 执行ACK | P/R，命令 epoch与读回；仍非 physical ACK | 真实物理信号/挡板、观测与实际执行的独立通道，丢失则 fail closed |
| M8 公共支持 | P/U，有限按公共 observation 并集，非预见性 | 完备协议后继、同公共历史相同控制，未知观测/遗漏分支拒绝 |
| M9 观测 | P/R，ROADWork视觉辅助，未建立接收/遮挡真值 | CARLA实际传感器与FOV/遮挡/收发记录，静默右删失 |
| M10 接受尾与rank | P/U，有限目标参考（声明模型） | 真实任务接受 Kterm^SC、全部后继 rank 降，不能以停车代替目标 |
| M11 独立oracle | P/U，精确有限参考、证书上下文 | 独立完整有限模型及正负证明，CEGAR具体反例分类；保守失败不可标负 |
| M12 共仿真 | P/R，SUMO 12 汇总，新增米制 probe | 同一物理地图、actor registry、唯一 tick owner、坐标/时钟与真实执行 |
| M13 监督 | P/U，1569弱记录/21新增隔离，0/8正式标签 | 各 label factory、来源/域/权限审计、独立 teacher，unknown mask |

## 6. 后续依赖与正式标签
论文 SafeTube(B,u) 是所有隐藏世界和允许扰动的连续安全合取；Succ 必须先按同一公共观测合并，再对所有后继证明 rank 下降。S∞ 安全不变性与 goal-winning W_H^SC 分开；W0=Kterm^SC 只允许接受尾策略确立的终端状态。本轮参考模型只覆盖有限连续平移箱、单位资源需求，Native 模块为保守筛查，不是完整 SafeTube。下一轮：统一多 actor Post+Guard+完整 observation Succ，再接真正任务接受尾与 SC verifier/CEGAR；数据与物理 parallel gate 提供模型输入，而不是各 PASS 拼成 SC。

| Loss | 正式证据前提 | 当前 |
|---|---|---|
| event | 权威事件协议、生效与消息时钟；511NY仅报告先验 | mask 0 |
| joint | 完整 WOMD/AV2事实、响应模型、独立支持验证 | mask 0 |
| occupancy | 校准地图与连续全部车辆 footprint | mask 0 |
| observation | 可见性与真实 message receipt/静默 | mask 0 |
| causal | 成对AA/AB固定外生条件、他车重算 | mask 0 |
| viability | 完整SC证书正；完备有限策略类负；其余 UNKNOWN | mask 0 |
| margin | Native 连续保守下界、有效物理/资源不确定性 | mask 0 |
| deadline | 同公共前缀、协议时间窗、接受尾及rank | mask 0 |

实际执行顺序参见同目录 RUNBOOK：先全 Native gate→独立 Waymax事实、CARLA响应、SUMO metric与 ROADWork严格 split→物理共享路网及多actor响应集→完整 protocol/SC→正式 label factories→训练及论文结果。当前允许受限辅助分类/视觉预训练，不能训练八项正式标签。论文中勿将这些调试结果写成真实安全保证或完整闭环 benchmark。
