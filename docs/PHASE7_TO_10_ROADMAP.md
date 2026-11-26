# RAMP-D 研究工程路线（清洁版起点）

本路线以当前论文的 Appendix Network Architecture and Training Supervision（typed tokens、sparse typed attention、agent-specific awareness、time-unrolled joint-mode factorization、八项 masked losses）及 E1–E5 为合同。历史文件 `DEVELOPMENT_ROADMAP.md`、`A74_PHASE6C_EXIT.md` 和 `A75_SUPERVISION_CONTRACT.md` 保留历史意义。这里的 Phase7–10 是建议的冻结路线，不是宣称旧阶段已验收。禁止为进度降低证明门槛。

## 1. 数据输入决策：结构化 log + vector map 为主，视觉是独立观测来源

主模型不吃原始 RGB。每个 planning cycle 的输入仅使用当前时刻公共信息支持和已收到观测。构造七类 typed tokens：

| Token | 输入 | 时间/来源边界 |
|---|---|---|
| Ego | 状态估计、尺寸/参考点、定位界、已执行控制 | history ≤ t；候选控制单独 query |
| Agent | 历史位置、速度、航向、尺寸、类别、valid/visibility/感知规则 | history ≤ t；没有观测用 mask，不以全知模拟状态替代 |
| Map | 车道中心线/边界、拓扑、connector、信号位置 | 地图版本和坐标系；静态特征可缓存 |
| Resource | 几何、容量/冲突、当前可知 permission summaries | 不泄漏隐藏真实规则；保留未来可能开放资源 |
| Rule/event | 事件来源、范围、权威、已知生效区间、issue/receipt status | 已收到消息与可信本地检测；未收到不是已知 |
| Information/task | joint support、观测等价类、任务自动机与当前承诺 | 公共信息；不向模型提供隐藏 world ID |
| Commitment | 仍有效的缓存证书或粗界 | 禁止同周期精炼 ICG 回流候选生成 |

推荐 WOMD Scenario 为统一事实主源；TFExample 为 Waymax 仿真适配格式，不重复计入训练。AV2-MF 作为独立数据补充/跨数据集验证；AV2 Map Change 测试地图变化鲁棒性，不当作权威消息时间。511NY / ROADWork / WZDx 分别提供真实事件类型、视觉语义及经验证的施工时空字段；禁止推断缺失的四时钟。用 SUMO 产生大规模 log，用 CARLA 产生小规模真实视觉形态、遮挡、ray casting / detection、执行和传感器时钟。两者均映射到同一 token contract。视觉模型只输出带不确定性、时间戳、来源的 observation token，默认不与主规划器端到端联合训练。可做 oracle-observation 与感知噪声的闭环对照，单列检测误差/模型外失败。ICAPS 主贡献是条件规划和证书，不是视觉识别。若论文新增 RGB 端到端贡献须另改方法、数据、基线，当前不建议。

## 2. 固定工程依赖，禁止新增 A76 式全局探针版本

```text
shared scene/clock/map/actor/schema + split/provenance
    ├── factual log adapter ──> Phase7A training smoke
    ├── incident spec ──> SUMO/CARLA/Waymax ──> event/occ/obs/causal/joint adapters
    └── declared joint model ──> Native Post/SafeTube/Succ/Rank/SC ──> independent Teacher
                                         ↓
                      per-field supervision contract + masked loader
                                         ↓
                        REA-Encoder / causal joint decoder / heads
                                         ↓
                        CCG / SCO / optimizer / full verifier / CEGAR
                                         ↓
                                E1–E5 + release freeze
```

两个分支可并行：Phase7A 只依赖真实事实数据入口和独立 split；数学/共享场景仍须通过 Phase6C G1–G4。阶段退出不要求实车级全车型扰动外包络或所有标签已大规模产生。

## 3. 工作包及执行顺序（目标、实现、测试、反例、验收）

| WP | 阶段/依赖 | 实现模块（建议新文件名，尚未创建） | 退出条件 |
|---|---|---|---|
| C0 | 本轮清洁 | 语义命名、alias、归档、回归 | 清洁前后回归一致；Native gate 服务器待回传 |
| D1 | 7A，立即；C0 | `dataset_registry`, `scene_stream`, `split_manifest`, `feature_contract`, `factual_dataset` | 源记录 ID/hash、独立全局 split；少量 train/val；future leakage、重复、坏时间和未观测 actor 负例；禁止整库大 JSON |
| L1 | 7A；D1 | `tokenizer`, `rea_encoder`, `joint_decoder`, `masked_losses`, `train`, `evaluate` | 事实单头最小训练；小集过拟合测试、val 独立、mask 与梯度正确、可复现 checkpoint；不声称完整八头 |
| M1 | 6C G1；C0 Native | `joint_post`, `joint_safe_tube`, `protocol_successor`, `terminal_policy`, `sc_pipeline` | 同一个代表性 6D 声明场景从 Native 重放到 `compute_sc_inner` 和独立重放；正、完备有限负、UNKNOWN、漏分支、等观测公共动作、真实目标、rank 延续 |
| S1 | 6C G3；C0 同源地图 | `incident_spec`, `map_alignment`, `actor_registry`, `cosim_bridge`, `resource_monitor`, `event_trace` | 一个真正共享物理区域；统一时钟/状态权威；进入/停留/清场/冲突、ACK/读回分离；重放和漏 actor/错地图/提前放行负例 |
| S2 | 7B；S1 | `event_labels`, `occupancy_labels`, `observation_labels`, `paired_intervention_labels` | 仿真源域逐字段精确或删失；A/AA/B 相同外生条件；无效干预不当负效应；视觉/协议各自时间对齐 |
| L2 | 7B；D1,L1 | `learned_response`, `waymax_response_adapter`, `response_evaluation` | 仅 history/地图/可知规则在线输入；log replay、IDM 基线；独立闭环 kinematic/map/interaction 指标；匹配干预和 actor identity；模型反事实不升格真值 |
| T1 | 7C；M1 | `viability_teacher`, `margin_teacher`, `deadline_teacher`, `proof_replay` | 可重放正证书；完备有限负证明；连续 margin 下界；同 prefix 的时间界和 ICG；预算超时/未知不赋负标签 |
| D2 | 7D；D1,S2,L2,T1 | `supervision_registry`, `multihead_dataset`, `batch_collator`, `multitask_training` | 八头字段合同，每头有效样本数、split/source 域、mask/gradient 检查；缺字段保持 UNKNOWN；先分别验收再联合训练 |
| P1 | 8；M1,D2 | `ccg`, `sco`, `candidate_optimizer`, `mode_selection`, `full_support_verifier`, `replanning_executor`, `cegar_driver` | 端到端控制候选→完整声明 support 验证→执行；候选概率不裁剪支持；错误候选拒绝；rank 预算单调；失败时 scoped fallback |
| E1–E5 | 9；P1 | `benchmark_scenarios`, `baselines`, `ablation_runner`, `metrics`, `statistical_report` | 固定实验/划分/随机种子/预算，论文主表、消融和失败分类；不得以采样无碰撞替代证明 |
| R1 | 10；E1–E5 | 复现包、锁定配置、模型权重/哈希、论文表格和证书重放 | 定理假设/实际模型/实验范围一致，数据许可、匿名和复现检查 |

### 3.1 D1：从已有 55 条候选启动，而不是 170MB inventory

当前 `export_factual_labels.py` 是批量 inventory 入口，**不是**流式训练 loader。下一步从 WOMD protobuf 逐条读取并立即转换轻量场景/样本，manifest 只保存 dataset/version、官方 ID、record SHA、shard/record index、split、parent family、timestamp 范围和目标 mask 统计。大文件按 shard 写 JSONL/Arrow/Parquet，训练按需读；原始地图矢量单独缓存（哈希绑定），不生成整个库的嵌套 JSON。探针默认 3–5 条、1–2 shard；先比较上传的候选和 validation 文件，不要求上传 170MB 中间件。全局 split 在任何 normalization、训练/调参之前建立；官方 train/val 不混用，同一 20s parent 或重复窗口不能跨 split；当前 55 条 ID/hash 不冲突只是局部证据。候选文件训练授权为 0，不能直接解锁。构建独立全局来源清单，不从候选自身生成授权。在线 encoder 输入不包含 labels、births_unmodelled、hidden state 或完整 future map signals；logged ego future path 仅为离线条件 surrogate，在线 candidate 由规划器生成，不能视为实测控制。模型和标签接口均保存坐标参考点（WOMD box-center 与论文 rear axle 不混用）。

### 3.2 M1：明确最小完整数学集成而非无边界改进

现有 `interval`、`model`、`reachability`、`certificate`、`footprint`、`belief`、`invariant`、`backup`、`backup_graph`、`protocol`、`resources`、`observations`、`full_verifier`、`safe_continuation`、`cegar` 是长期内核。`native_certificate_context`、`segmented_native_post`、`native_multi_actor_screen`、`public_successor_binding`、`affine_resource_monitor`、`finite_wait_reference`、`rank_budget` 是有用但适用域不同的集成基础。先通过旧 Native gate；再以一个两车、两隐藏规则、有限等待、同观测合并、目标离开资源的 6D 声明模型，统一控制/扰动/时间/地图/参与者/协议版本、完整联合 atom 和尾策略。外包络 Reach 用于充分安全检查，winning set 为内逼近，模型外或 proof budget 失败返回 UNKNOWN；完整 SafeTube 包括动力学/输入/摩擦/道路/多车碰撞/资源授权/容量/冲突/清场。生成所有协议/观测后继而非只重放人为列出的列表。有限 rank 严格下降；等待消耗绝对时间/剩余 rank；目标 acceptance 与安全停车分离；尾策略和重规划继承 completion bound。独立 verifier 从源合同重算覆盖，负例覆盖错绑定、同观测漏世界、端点规则变化、保护性退出、失联/出生、重规划 rank 放松。一个完整集成通过即结束该工作包，不扩大复杂场景直到有可运行主链。

### 3.3 S1/S2：基于当前同源 Town06_Opt 地图

已上传 OpenDRIVE 与 SUMO net，xodr hash 与两份 CARLA 采集一致。先建立 road/lane/section/connector 匹配、CARLA 左手系与 SUMO 坐标变换（netOffset 358.49,404.45 不是完整变换证明）、多个不共线控制点误差和车辆前端/包围盒中心/后轴转换；检查共享区域几何真正重合而非旧双独立车道逻辑区。最小 S1：单车道双向交替，入口关闭后 incumbent 清场、全车身连续分离、方向互锁；S2 lane closure/taper、S3 STOP/SLOW 遮挡、S4 reroute 后续扩展。固定唯一 tick owner、每 actor 唯一动力学权威；日志含 source/protocol/sim frame/actor/command epoch/rule version/authority & clock；明确模拟器控制读回不等于独立物理 ACK。SUMO 作为 log factory，CARLA 为物理/视觉的独立执行层；允许少量代表性同源 co-sim，其余 SUMO log 不需要 RGB 渲染。控制输入与外部 dt 固定，CARLA 子步敏感性已确认；冻结现有物理辨识，选择声明运行域和经验参数，模型外异常单列。真实物理严格外包络仍缺，不以经验最大值当严格扰动。

## 4. 八项监督的最小验收和正式用途

| Loss | 当前可用 | 生成顺序和验收 |
|---|---|---|
| event | 511NY 1500 文本弱记录、ROADWork 65 视觉模板 | S1/S2；规则状态/权威/影响资源/生效区间/发布时钟，来源/版本可回溯；真实缺时刻用有依据区间删失或 UNKNOWN；仿真时钟单独域 |
| joint | 50 train 候选 + 5 val 的 1s 事实 xy，未授权；5 Waymax 3s IDM 模型配对 | D1/L1 后事实可训，S2/L2 补模型配对；官方 ID/valid masks/未来隔离、history 与 candidate 分离；A/AA 可重复，AB 干预有效和响应身份明确；闭环评估，禁止未来路线特权当在线 |
| occupancy | 9000 双带采样评估记录 | S1/S2；原始轨迹、地图资源、尺寸/参考点、时钟、完整 roster 独立重建；采样与连续分离、MAY/MUST/EMPTY、clearance、capacity/conflict；UNKNOWN 不当空闲 |
| observation | 视觉语义辅助；非接收真值 | S1/S2；visibility、detection、awareness proxy、message issue/receipt/drop/silence 独立字段；帧和消息 ID 对齐、删失合理、未收到不等于不存在 |
| viability | 有限 WAIT/GO reference rank12；horizon11 无解 | M1/T1；same support/model/task/action class；正证书全分支独立重放，负仅完备有限证明，超时/单候选失败 UNKNOWN |
| margin | Native 基础及 conditional screen | M1/T1；完整连续硬约束，物理归一化下界及同 support 排序；不以离散碰撞距离/制动最大值代替 |
| deadline | exact time、有限 rank | M1/T1；同 prefix 的 Ddefer/Dstart/Tobs+ 区间和 ICG sign；时间博弈/调度证明，不能判符号就 unresolved |
| causal | Waymax A/AA/B 模型配对、CARLA 子步诊断 | S1/S2；相同初态/外生变量/协议随机实现，外生事件 invariant，actuated event 经 flow/controller 中介；明确空效应 vs 无效干预，非真实因果真值 |

每头每字段存 `value`, `valid_mask`, `training_allowed`, `source/domain`, `split`, `scenario/actor/resource ID`, `timestamps`, `schema`, `model/protocol hash`, `proof/evidence reference`, `unknown_reason`。训练损失按本头有效元素归一化，某头无标签不产生梯度（也不将 UNKNOWN 作为 0）。区分真实事实、真实弱辅助、仿真模型事实/反事实、声明数学证明；不同域单独报指标。正式八头合同和 loader 尚未完整实现。

## 5. Phase7/8 模型与完整调用链

L1 先做结构化 tokenizer + ego/agent/map encoder + multimodal joint decoder，在 WOMD/AV2 factual logs 验证历史/候选边界，常速度、IDM、非因果预测作为基线。Phase7D 逐头加入 resource/rule/observation/task/commitment tokens 和稀疏 typed biases；遵照论文的时间因果顺序：external event 独立于 ego prefix；actuated event ← 当前 flow/controller；规则由协议 K_R；agent response 依据区间开始时已知 awareness；footprint 确定 occupancy；endpoint visibility/message 更新下一时刻 awareness/observation。不要将未来 hidden rule 直接作为 agent 输入或形成同一步环路。保留 likelihood/SC-critical/coverage 模式只作候选优先级，严格 verifier 支持独立于选模。

P1 使用当前信息支持与 cache 生成 CCG/SCO、候选 prefix、优化并调用 full-support verifier；CERTIFIED 才能在声明模型内执行相应策略。未通过时 CEGAR 精化或执行既有已验收 fallback，区分 SAFE_ONLY 与 task completion，保留进度 rank。先离线冻结小实例，再联合仿真，再扩展模型/数据规模。

## 6. Phase9/10 论文实验冻结

| E | 场景/基线 | 主指标 |
|---|---|---|
| E1 | exact belief support oracle、hidden-state-specific、independent marginal | false inclusion（要求零）、winning coverage、common action violation、runtime |
| E2 | delay 与 commitment sweep、indefinite delay，information-first/early stop/旧 deadline | ICG sign agreement、unresolved、deadline miss、conditional schedule success |
| E3 | safe-stop 相似但 task continuation 不同，反复等待，safety-only/without rank | lawful completion、rank violations、safe-only、completion time、oracle continuation loss |
| E4 | awareness/causal ordering/critical retention ablation；paired sim only for counterfactual | ADE/FDE、joint likelihood、occupancy/event-time/obs-class recall、critical-mode/resource recall、downstream completion |
| E5 | selected-only / full support / full + CEGAR | cert coverage、UNKNOWN、in-envelope falsification、model-conformance failures、refinement count、p50/p95 latency |

比较同一地图、动力学、声明扰动、观测和算力预算；按原始场景/seed 分组，报告样本数、置信区间、失败分类和覆盖率。ICAPS 主表优先 E1–E3，E4/E5 支持可用性。Phase10 冻结源码、依赖/Native ABI、数据划分、训练配置和权重、协议/地图/证书哈希及实验生成脚本；逐项核对论文定理假设与证据域。当前不改论文正文、不训练模型、不启动新模拟器。
