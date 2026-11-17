# RAMP-D 八项训练信号：来源、可信度与可执行方案

依据用户最新版 TeX Appendix Network（Eight training signals and their sources），并与物理约束、SC、ICG、实验定义保持一致。公开数据、仿真数据、有限 oracle/形式化证据是三种不同证据域。不把弱标签/预测输出作为 hard verifier 输入，不要求每个样本都有八项标签。所有目标均记录 dataset/domain、scenario/group/split、source_record_sha、ego prefix/action surrogate digest、帧/车体参考点、时间/协议/operator/模型版本、算法版本、mask/unknown/censoring、单位以及证据来源。监督 loss 按有效标注数归一化；零有效项不回传，单独报告占比；正负分布及 domain 权重预注册，不能靠选择性 mask 提高实验结果。

## 1. L_event
- 主来源：SUMO TraCI 交通信号控制器、车道资源权限、外部事件脚本，CARLA 对齐渲染观测。TraCI 并不自带论文的 V2X 消息发布/接收语义；建立独立协议 logger，记录 source/scope、event class、activation/effectivity、rule version/resolution、change/issue/receipt/local 四个时钟。固定时序与 actuated controller 分开；外部事件不受 ego 干预，actuated 受 detector/flow/controller 中介。
- WOMD 动态地图 signal lane state 可监督灯态类别。相邻同一信号已知状态改变仅证明至少一次记录语义的切换，不能推断唯一 activation 时刻或 event cause。由 A5/2 `sampled_signal_changes` 实现。AV2 MF 本身不提供完整动态信号时钟。真实控制器 log/SPaT 数据可标定分布、与模拟时序对照，但未和 WOMD/AV2 独立场景对齐，不得当同一场景真值。
- 精确 event 类别用 CE；已独立确认同一 event 的时间在 [l,u]，用 -log(F(u)-F(l^-))；右删失用 survival；相邻多次切换未知时只用 auxiliary categorical/switch-count/switch-existence loss，不把 bracket 当某个事件的唯一 onset。事件路径的生效/失效规则由协议检查，不从预测概率构造权限。
- 外部校准候选：US DOT CV Pilot BSM/TIM/SPaT/MAP（部分需申请）、Utah SPaT Change and Clearance Interval、Real-Time Traffic Signal Applications Communications study (pcap)。实际读取前核查 timestamp semantics、clock offset、packet loss、许可与样本选择，不能自动推出全局时延上界。

## 2. L_joint
- 主来源 WOMD Scenario training/validation、AV2 MF Train/Validation，真实 ego 身份（WOMD sdc_track_index，AV2 明确 AV track，不用 focal/scored 代替），共同场景下所有目标轨迹。记录实际 ego path prefix 作为 action surrogate，若希望精确 jerk/steer，需要测量控制或经过单独验证的重建/逆动力学（导数噪声、转向角、轴距、参考点）。真实 path-conditioned likelihood 是 observational P(Y|X,pi_logged)，不是 P(Y|X,do(pi))。A5/2 `factual_joint_labels` 实现 XY mask 与 prefix hash。未实现完整模型张量及控制序列重建。对于未来超过 prefix 的部分，其响应仍受已记录后续驾驶策略分布影响；训练时显式定义 prefix 和预测时间长度。
- 推荐一个 joint mode k 对应所有 actor 的联合未来。若条件于 k 后采用独立 residual，负 log likelihood = -logsumexp_k(log p_k + sum_{i,t} mask_itt * log p(y_it|k,X,pi))，禁止为每个 actor 分别选 oracle mode 后冒充 joint NLL。残差相关性可以通过联合生成/自回归表达。分别报告 WOMD/AV2 官方 metrics 与额外联合指标、mask coverage、校准。
- 未执行动作使用 SUMO/CARLA paired re-rollout、Waymax IDM 或已校准 learned reactive sim agents 辅助；log playback 只作不响应 baseline。WOSAC 是闭环生成多智能体轨迹和 realism 评测，不提供真实反事实 ground truth。AV2 Multi-World annotations/evaluation 不应被自动视为真实因果干预结果。

## 3. L_occupancy
- 主来源真实日志中的 actor boxes + 明确选择且同一交通表面的 resource polygon。WOMD 有 bbox center、heading 和 length/width；AV2 MF 标准 ObjectState 缺尺寸，默认 mask，不用统一车辆尺寸作为真值。WOMD lane centerline 不是 lane polygon；只能用可靠边界匹配构成 polygon 或原生 crosswalk 等 polygon。AV2 lane left/right boundaries 可构成地图几何；仍需资源语义绑定，并确保 2D overlap 不把高架与地面相混。不能把完整 map 字段等同于资源覆盖完备性。
- A5/2 `sampled_occupancy_labels` 对显式 actor/polygon pairs：从中心和旋转矩形计算 intersection，遮罩近边界和缺失维度。样本在相邻 valid knots 的 0→1/1→1/1→0 标签只能称 sampled entry/stay/exit；即使两个时间点都不占用也可能在途中占用。连续时域需 validated tube/可验证插值运动边界。模拟器 geometry 可以产生高频 sampled truth，但不是严格连续证明。
- 可用 masked BCE / focal loss、分开 entry/stay/exit 多分类。冲突/容量/许可只由协议、资源模型硬检查器建立；auxiliary consistency loss 不能替代 hard constraints。缺少明确几何或道路表面绑定的标签保留 UNKNOWN。

## 4. L_observation
- 可用 CARLA 0.9.16 同步 fixed delta、cast-ray/depth/instance segmentation、摄像头/雷达等 FOV 和遮挡 ground truth，分开 geometric visibility、sensor detection、delivery、latent awareness。可见不意味着被检测，收到不意味着理解。agent awareness 只使用弱标签（可访问通信/视线、行为变化 cue）和 latent model；不宣称 cognitive state ground truth。
- 真实 WOMD/AV2 track valid/observed 不是 ego 感知标注；如需要真实 detection 监督可另用 AV2 Sensor 或 WOMD Perception graph 对齐数据（不能擅自用它们与 Motion 场景拼接）。当前不追加下载要求。对 V2X 接收，独立 message logger：per-recipient ID、publication, reception, observation frame、版本、超时、drops，接收/发布缺失独立 mask。无消息在 finite cutoff 仅右删失；未证明发布/可靠传递保证时不能用 silence 排除隐藏事件。通信层优先显式有界延迟/丢包实验，必要时用真实 pcap/SPaT 校准分布或独立网络仿真，而非平均时延充当保证。

## 5. L_viability
- 真实数据/仿真中的成功率和碰撞率不足以生成 task winning 的 ground truth。构建独立、可穷尽的小规模有限信息状态转移模型（不能用 hidden modes 当 fully observed state）。明确 action class、time horizon、完整自然分支、任务接受、终端尾策略和 guard；用强规划 AND-OR/逆向 DP 枚举，安全 & all successors winning 才 WIN。强循环策略的 fairness/最终可达不能替代有限最坏 completion bound。可用 UPPAAL TIGA timed-game/另一独立 exact enumerator cross-check（仅适合编码了 observation/information-state 的有限模型）。
- Pos：候选 public prefix+tail 全部硬安全和任务接受证明。Neg：独立 exact finite-model oracle 枚举完定义的 policy class 全部失败（或有 sound complete infeasibility proof），范围只属于该有限模型，不能把 inner abstraction 中未保留的 cell 当负样本。Unknown：单一候选反例、超时、优化失败、精度不足/缺分支；mask。A5/2 仅新增受限合成 tail positive proof provider，当前还未生成实际训练的 viability 数据集或完整 negative oracle。
- CE/BCE over known labels, certificate support/task/model/prefix digest bind. 另报 known/masked ratio 和 false-inclusion (应为零) 对独立 oracle 对照，不可以 unknown-as-negative 让准确率虚高。

## 6. L_margin
- 根据 TeX Eq. margin，只有硬可行恢复策略上才定义连续物理 reserve。对每个布尔硬谓词独立验真，不把整数容量饱和、active equality 当零连续 margin。每项 g_j 用全支持集连续 reachable tube 下界、物理 separation 和 stopping/time/friction reserve，独立固定的正 scales s_j；g = min(1,min_j lower(g_j)/s_j)。MPFR/连续检查为证明主体，CommonRoad Drivability Checker 可作外部 empirical comparison（不能直接把 checker numerical tolerance 当 validated interval 数学证明）。
- 给某候选的保守 lower value 不等于最优 V_H 或到 viability boundary 的距离。记录 candidate-policy 下界/范围、归一化 scales、证据；训练时回归 lower-bound target 或 interval-aware objective（不是把 neural output 当证书）。不同 prefix 同 support 下只有 interval separation（L_a>U_b）才证明真实值排序；仅比较两个 lower bounds 可用于 teacher-search 排序但不得声称证明 V 排序。UNKNOWN/不可行无 margin label，不能填 0。A5/2 没有冒造 `TerminalTailCertificate.margin_lower`。

## 7. L_deadline
- 根据 TeX D_defer、D_start 和 T_sep,+ 定义，三者必须绑定同一 prefix、同一初始 support、时间/协议/资源窗口，以及决策类或 option ID。候选时间 partition 下 exact finite conditional temporal game 验证动态非预见性 controllability；固定分支简单时可用 STNU dynamic controllability，完整有条件/离散资源选择与 observation 协议需 CSTNUD-style timed game/显式枚举，不应把普通 STN feasible schedule 当 DC。可用 Morris 2014、UPPAAL TIGA 作独立校验。可行 d 为 D_defer 下界；每个更晚时间 cell 都 proved infeasible 才得到有限上界，不使用平均延迟或未经证明二分。
- T_sep,+ 的 upper：完整观测历史集合的 outer envelope disjoint；lower：共同 concrete trace 或独立 exact model，outer sets overlap 本身不够。ICG interval = [T_lo-D_hi, T_hi-D_lo]；正号只在 T_lo>D_hi，非正只在 T_hi<=D_lo，其他 unresolved。D_start 是 option 全路径的可启动时间集合 sup，不能与 D_defer 混用。若时间无界/不可行，单独删失/类别 mask，不填 horizon/max_float。TeX supervision 表使用 T_obs^+，正文用 T_sep,+；最终建议明确 raw event observation-arrival 与 distinct-history separation 的不同定义，如果表意在 ICG 请同步为 T_sep,+（不直接改作者 TeX）。
- interval loss 可使用在可信区间内无惩罚、外侧 hinge；已知单边界使用删失/单边 loss；精确值才可点回归。任何网络输出仅排序，不影响 hard scheduling verifier。

## 8. L_causal
- 神经网络结构优先保证 external-event head 不接 ego prefix，actuated-event head 只通过 aggregate flow/controller mediator 接受 ego influence。配对仿真 hold initial scene、地图、protocol code、external-event schedule/seed、exogenous disturbances/actor keyed RNG innovations（同 seed 不代表分叉后的代码消耗相同随机数）；改变 ego path/control，不把内生 actuation timing 或其他 actor response 固定成同样结果，否则人为消除真实模型中的因果路径。
- 统计 estimand = E_U[Y(do(pi_a),U)-Y(do(pi_b),U)] in declared simulator; external event distribution should invariant; actuated differences允许通过相应中介路径；可用 KL/JS or class/time consistency, paired differences and joint NLL, invariant head ablation。先做同动作 A/A 重复确定性，A/B 配对，独立 seed/route/test scenes，重复多种响应模型；报告实测 policy contrast、paired CI、distribution shift。真实日志只验 factual calibration/realism，不声称识别真实反事实。WOSAC 作为 sim-agent realism challenge，Waymax reactive IDM/learned agents 给辅助模拟器 domain，TrafficSim 作为 closed-loop learned simulation methodology。SUMO/CARLA 生成 explicit protocol interventions，保持一个时间 master，同步控制、重置并复核 snapshot、记录版本和实际执行后的 ego trajectory，不把 nominal action 与实际轨迹混在一起。

## 9. 开发验收与 reviewer 可复现性
- 先保留官方 train/validation split；测试集隐藏标签仅官方评测。按原始 20s segment/scene/family 和 paired seed group split，防止 overlapping window / intervention twins 泄漏。真实与仿真域 separate metrics，不能把不同 domain sample budget 当相同 iid 样本，置信区间按 scenario group cluster/配对配对。
- 四类训练域：real observed logs; same-surface derived weak geometry; simulator paired/intervention/protocol; independent exact/validated proof labels。训练清单公布 source masks、未知比例、有限 oracle class/horizon、solver timeout 和 negative proof coverage、模拟器行为模型与参数/版本、随机种子、split hash、label-generation code。报告 per-loss calibration/accuracy/coverage、模糊/删失比例、无效 gate 率。真实预测用 official benchmark，与仿真反事实结果独立展示；对比 no causal / no awareness / no capability ranking ablation；不以神经预测缩小 hard support。域偏移、真实世界无反事实 ground truth 为明确限制。
- 首次运行：用现有 WOMD/AV2 的小样本 smoke 测 factual prefix、signal bracket、box availability；接着定义资源 geometry 和 surface association 再做 occupancy。其他五类标签逐步由明确模拟协议与独立验证器生成。无需额外下载全部 AV2 Map Change 或现在开启 CARLA/SUMO；后续干预阶段才启动。对真实 SPaT / CV Pilot 先核查可用范围再决定是否下载，不能假称已有完整标签。

## 参考资料（本轮实际查阅的公开说明）
- WOMD motion guide: https://waymo.com/open/data/motion/ ; official Scenario protobuf: https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto
- AV2 motion guide: https://argoverse.github.io/user-guide/tasks/motion_forecasting.html ; schema: https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/data_schema.py
- Montali et al., WOSAC, NeurIPS 2023: https://arxiv.org/abs/2305.12032 ; Waymax: https://waymo.com/research/waymax/ ; reactive multi-agent example: https://waymo-research.github.io/waymax/docs/notebooks/multi_actors_demo.html
- Suo et al., TrafficSim, CVPR 2021: https://openaccess.thecvf.com/content/CVPR2021/html/Suo_TrafficSim_Learning_To_Simulate_Realistic_Multi-Agent_Behaviors_CVPR_2021_paper.html
- SUMO Traffic Lights: https://eclipse.dev/sumo/docs/Simulation/Traffic_Lights.html ; TraCI Lane State: https://sumo.dlr.de/docs/TraCI/Change_Lane_State.html ; CARLA 0.9.16 synchronous settings: https://carla.readthedocs.io/en/0.9.16/foundations/ ; deterministic TM: https://carla.readthedocs.io/en/latest/adv_traffic_manager/
- US DOT Connected Vehicle Pilot (CVP) Open Data: https://data.transportation.gov/stories/s/Connected-Vehicle-Pilot-CVP-Open-Data/hr8h-ufhq/ ; Utah SPaT: https://catalog.data.gov/dataset/traffic-signal-change-and-clearance-interval-pooled-fund-study-utah-spat-data ; raw communication study: https://catalog.data.gov/dataset/feasibility-study-and-assessment-of-communications-approaches-for-real-time-traffic-signal
- Cimatti et al., Weak, Strong, and Strong Cyclic Planning via Symbolic Model Checking (2003): https://www.sciencedirect.com/science/article/pii/S0004370202003740 ; UPPAAL Tiga: https://docs.uppaal.org/extensions/tiga/ ; Morris, Dynamic Controllability and Dispatchability Relationships (2014): https://ntrs.nasa.gov/citations/20140008604
- CommonRoad Drivability Checker: https://commonroad.in.tum.de/tools/drivability-checker
