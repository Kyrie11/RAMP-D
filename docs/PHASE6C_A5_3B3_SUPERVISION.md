# A5/3b-3 · 监督来源及真实性计划

## 来源必须分层

1. WOMD/AV2 真实事实轨迹; logged ego path surrogate 不等同控制输入/干预。240 sampled scenes 已通过 inventory；无全量去重、占用标签生产、完整统计代表性。
2. WZDx 真实报告的类型、范围和版本; 43 feeds / 2373 flattened rows，未认证 start/end/location、无 Feature ID，不能精确监督 authority effectivity 或 ego receipt。可作为模板候选集，不作事件独立频率。
3. MUTCD 11th ed Part 6 6A.01/02、6B.01–08、6L.01、6O、6P：标准、指导、选项分别保存，特别是 6L.01 明确临时信号需符合 Part 4/4O.02。使用 TA-10/11/12 等具体模板时先核对施工条件。表值不是安全保证；临时规则不能消除实际障碍。
4. ROADWork ICCV2025 Sec.2 Fig.2/3：15 类对象、360 类施工标志、9,650 丰富标注图像、4,375 30s clips、1,936 reconstruction sequences/129,017 pathway frames。提供真实可见标志、对象、图像场景描述、COLMAP observed driven path。单次实际通行路径不是全部可行路径或安全证书；图像相对面积/共现不等于世界坐标实际距离或交通流。官方 GPS split train/val 保留；只用 train 校准生成器，val 做 held-out 检验；避免 alternate split 混合。已有三份 archive 足够进行视觉模板 audit，不必立即下载 70GB 视频。稀疏 pathway 后续再下载 traj_images.zip/traj_annotations.zip，并读 Supplement B.3 确认尺度/坐标。

## Incident 真值时钟

FHWA TIM T0–T7（https://ops.fhwa.dot.gov/tim/preparedness/tim/performance_measures.htm）用于事后管理，而非规划 deadline。物理 hazard onset、管理方 first recordable awareness、verification、dispatch、arrival、lane clearance、rule authority effectivity、issue、public receipt、local detection 需独立来源。参考机制可明确顺序但真实事件可能并发/先派遣后确认；不要用一个不变总顺序代替其他事件机制。长时间 incident 通过多个短时局部规划窗口采样，不人为把分钟压缩成秒。

仿真 canonical clock：统一同步 tick k，名义精确 q=k*Delta；CARLA 每 world frame/timestamp，SUMO 每 step/time/actor 状态，Waymax 轨迹 index；实际物理 onset 发生在相邻采样间，只能给区间，除非是明确模型内部的原子命令时刻。逐条记录时间源、frame、责任方、范围、消息/规则 version 和 evidence id。可编程模拟发布时刻精确，物理部署和传感器检测不自动精确。固定 exogenous draw 不固定实际受交通影响的 deployment、queue 和恢复时刻。通信先记录 issue，独立 keyed delay/drop，日志中未观察到 receipt 且覆盖连续时可右删失；如果明确模拟永久丢包则保留 drop 类或 survival mass at infinity。仅实际 receipt 更新知识。

FHWA 数据建议：`Analysis, Modeling, and Simulation for Traffic Incident Management Applications — Incident Data Required` https://ops.fhwa.dot.gov/publications/fhwahop12045/4_incdnt.htm；`Process for Establishing... TIM Performance Measurement Program — Step 1` https://ops.fhwa.dot.gov/publications/fhwahop15028/step1.htm。优先收集一个 TMC/CAD anonymized historical sample（incident ID/类型/道路/阻断车道/T1/T2/T3/T4/T5/T6/缺失标志/时区），用于估计分层持续时间分布，不能据此直接识别 t_effective/t_receive。没有实证参数时按 declared sensitivity intervals 生成机制实验，不声称已校准现实概率。V2X 延迟可优先校准通信日志和实测；不以固定常数冒充现实分布。

## Eight losses: implementation sequence

| Loss | Correct target and status |
|---|---|
| Event | SUMO/CARLA controller/action log, WZDx template priors, MUTCD/TIM process; current clock contracts and interval fixture only |
| Joint | factual WOMD/AV2 391244 valid knots, paired responsive simulation later. Full labeling/training not complete. |
| Occupancy | verified map-aligned footprint intersections; WOMD dimension availability 100% within sampled target knots, AV2 no dims; classify sampled labels separately from continuous proof. |
| Observation | ROADWork human visible objects/signs as auxiliary perception labels, CARLA visibility/distinct detector logs/receipt; not ego awareness or authority labels. Current archive audit fixture only. |
| Viability | Certified successful candidate or independent finite complete oracle; negative only within defined class; unknown mask. |
| Margin | conservative verified lower bound on continuous constraints, same initial support; not true optimal margin. |
| Deadline | exact same-prefix D_defer, latest-start and T_sep,+ (paper notation T_obs+ to reconcile); use bounds and exact oracle; TIM durations not deadline. |
| Causal | model-based intervention with common external source, responsive actors and controller mediators; A/A, A/B; CausalAgents only human relevance/robustness validation, not new ego action outcomes. |

## Data request next round

ROADWork JSON audit + contact sheet (actual archives on server), Supplement B/C or actual small annotation record if schema unexpected, not full images zip. MUTCD Part 4 relevant Chap 4O/4F when implementing actual temporary signals. Existing WZDx data sufficient for templates; optional 1–3 full GeoJSON snapshots with header/Feature ID and retrieval date. FHWA TIM referenced docs and small incident timing record if available. CausalAgents original labels + protobuf + mapping scripts when robustness phase begins, use validation only unless a clean training source is established. Already installed Waymax and WOMD validation TFExample; WOSAC tool only external evaluation, no need new big dataset. Later sparse ROADWork pathway, no dense/video until required. No new datasets required for current mathematical gate.
