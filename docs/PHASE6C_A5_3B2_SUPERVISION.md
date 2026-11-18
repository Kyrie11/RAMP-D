# A5/3b-2 规则事件与监督来源实施计划

## 已核对的真实输入
- FHWA MUTCD Part 6 (uploaded 204p): 6A.01/02 temporary traffic control authority、所有道路使用者、最小干扰与队列；6B.01 speed reduction guidance；6B.02–07 TTC zones four areas: advance warning, transition, activity (buffer/work/traffic spaces), termination；Table 6B-3/4 taper lengths；6O.01–05 incident management and expected duration categories. 参考规范不等于自动合法性或安全证书。美国规则适用于声明的美国式场景，不自动移植到其他司法区域。
- 上传 WZDx registry 43 rows，Texas 4.2 flattened example 2373 report rows，v4.2 schema zip. 42 active; 所有事件行 work-zone；四类 verification flags 全 false；全部 WKT 为基础合法 geographic line，无 feature ID，不得统计为 2373 个真实独立事件。数据源 registry 中 Texas txdot_v4_2 需要 API key，austin 不需要（上传快照所示）。不要公开 URL 凭据。
- Archive: raw 是抓取时完整 feed snapshots; processed 按事件保留主要变化/定期报告；均非 ego V2X receipt ground truth. 官方目录及两 S3 bucket 见 https://github.com/usdot-its-jpo-data-portal/sandbox 。历史网页打不开不阻塞阶段。建议先列出少量 key 再下载，若权限不可用就使用无 key 公开 feed 的重复快照（保存取得时间、URL 去敏、原始 bytes 与 hash）。
- ROADWork: 图像标注和 pathway 用于物理布局、标志类别、可见性弱监督与模板质量核查，不含直接权威时钟、ego 接收时刻、反事实。下一次上传 readme/annotations 小样本及文件清单即可；无需上传巨型图像压缩包。

## Incident mechanism
四种目标：disabled vehicle（触发时改变动力行为、物理连续减速/停驶）、road debris（障碍产生和运动来源、尺寸质量和占用，必要时用模型替代未验证物理）、crash（从接触检测开始的响应、禁止强制将交通依赖撞车作为外生不变事件）、environment obstruction（来源/位置/形成过程独立声明，允许先有物理占用后有权威规则）。
FHWA TIM: https://ops.fhwa.dot.gov/tim/preparedness/tim/performance_measures.htm
T0 trigger/incidence; T1 first recordable awareness; T2 verification; T3 dispatch; T4 response arrives; T5 lanes available; T6 last responder left; T7 normal flow. RCT=T5-T1, ICT=T6-T1. 本实现选定 reactive、明确 scoped blocked-lane 物理清除机制，缺时钟 unknown，不将该 partial order 当成所有现实事件的定理。MUTCD 6O expected incident categories <30min, 30min–2h, >2h 不代表经验概率或 8秒内必须完成。初期评测从长事件窗口切片，使用已发生/仍未完成/censored 标记，时钟不缩放。

仿真下一阶段: authority controller / physical backend / communication channel 三层，统一 world time authoritative tick；CARLA 只承担碰撞几何及传感器、SUMO 交通需求与交通控制，车辆 identity/pose/reference/time 双向映射检查，一个 actor 只有一个动力学所有者。先单后端，再联合；同一事件在多个资源的手工授权映射；感应规则含 detector delay, min-green, yellow, all-red, continuous clearance. A/A 与 A/B 固定外生随机源而非强制固定效应。ScenarioRunner 0.9.16 https://github.com/carla-simulator/scenario_runner/tree/v0.9.16 只作为场景参考；不冒充真实交通事件。

## 八项监督
Event: WZDx reported template + MUTCD/TIM validated mechanism + simulator true/issue/receive clock; WOMD changes only auxiliary. Joint: factual WOMD/AV2 and responsive simulator; Waymax log replay not intervention. Occupancy: exact geometry/resource definitions + masked sampled footprints; continuous proof via verifier only. Observation: CARLA physical visibility and detector/message logs, ROADWork visual auxiliary; valid mask is not knowledge. Viability: verified witness or exact enumerated finite oracle; UNKNOWN masked. Margin: lower bounds from validated envelopes; one-sided bound target, not optimal value without proof. Deadline: exact time oracle, same prefix/support for differences; incident clearance not ego deadline. Causal: paired intervention under explicit simulator model; CausalAgents only held-out relevance/robustness, no safety pruning. All require provenance and split masks; no actual new full training labels from this release.

References: AV2 official serialization https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/scenario_serialization.py ; FHWA MUTCD https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/part6r1.pdf ; WZDx https://github.com/usdot-jpo-ode/wzdx ; FHWA TIM link above. 
