# A5/3b-5 后续推进计划与监督契约

## 数学长期矩阵
| 编号 | 目前证据 | 后续验收 |
|---|---|---|
| M1 区间算术/Picard | 3b4 已验收；3b5 原生 SAT 待验收 | 新原生回归、连续回放 |
| M2 精确时间 | 有限声明任务 | 多源时钟区间、事件边界 |
| M3 动力学/参考点 | Waymax 离散实测；新增连续停车参考 | 跨模型误差、局部坐标、摩擦/jerk/曲率约束 |
| M4 多参与者支持 | 声明外包络 | ODD 模型覆盖、动态出生/消失 |
| M5 碰撞几何 | 矩形 | 区间 SAT、复杂地图凸分解/根隔离 |
| M6 资源许可/容量 | 矩形占用与分支关联 | 独立进入/退出 gate、联合 occupancy 时序 |
| M7 权威规则 | 版本/有限时序 | 交通状态 guard、重叠事件、故障/ack |
| M8 协议信息时钟 | 有限消息历史 | 动态队列、不确定接收和 guard 联合传播 |
| M9 观测 | 有限划分 | 传感器遮挡、漏检/误检、可观测历史 |
| M10 任务尾/SC | 有限供给候选回放 | 在线 rank、尾策略、模型相关完备性 |
| M11 teacher | 未完整实现 | 独立 viability/margin/deadline oracle |
| M12 反事实 | 日志回放及离散接口通过；双车和 SUMO 待实际执行 | A/A、A/B 多种子/步长、WOSAC、失败分层 |
| M13 监督一致性 | bounded 数据接入与来源设计 | source/mask/clock/model/ID/evidence/split 绑定 |

## 阶段顺序
1. 3b5（本轮）审计 + 仿真闭环探针，原生 SAT，511NY 统计；不生产训练标签。
2. 3b6：交通驱动 guard 在支持集传播中形式化，包括 detector 误差区间、混合转换、消息排队及观测分区；连续几何自适应细分；有限 oracle 结果与原生检查。
3. 首个物理闭环：SUMO 单共享资源逻辑试验通过后接 CARLA headless，车辆/信号/障碍物 ID 映射、步进所有权、ACK、连续清空证据，计划施工；后续 breakdown。Part 4/6 场景模板、旗手、临时信号、换道绕行。先单个事件，再多事件仲裁。
4. Waymax真实 WOMD 场景配对干预：先受控 IDM，后 route-change/MOBIL 及学习模型；不以回放未来作为部署观测。不同 ego 动作保持外生随机源固定，内生响应不固定。WOSAC 评估、场景级数据分离；CausalAgents 暂缓。
5. SC/形式化 teacher：真实地图 gate/资源绑定、公共策略、任务尾、连续证据和独立 oracle；UNKNOWN 单独掩码。
6. 八项监督生产及 RuleNet：事实与模拟分别标记；统一坐标、物理/规则/消息/局部观察时钟、候选控制、模型版本和证书；不把 511NY 生命周期当作物理事件时钟。

## 数据来源决策
- WOMD/AV2: factual joint, 尺寸缺失掩码。ROADWork: 视觉线索及对象共现；不把可见标志直接变为权威规则，校准只使用 train，val 留出。511NY: 报告生命周期及事件类型，混合交通/公交须过滤；不把 Create/Close 当作 TIM 的 T1/T5/T6，不恢复不存在的 ID。
- 511NY 原始元数据、字典、FHWA TIM Handbook 2010 (FHWA-HOP-10-013)、MUTCD 4/6 为独立理论参考。NCHRP 指标在线指南 https://www.timnetwork.org/nchrptimpm-sub/index_php/ 。
- 用户截图的英国 DfT 数据是道路交通计数，不是事故持续时间；本轮无需下载。需校准交通流时少量 Count points/Raw counts（年份地点分层），AADF 仅粗尺度先验；英国方向规则与美国场景区分。National Highways 事件持续时间另见 https://www.data.gov.uk/dataset/d7a7ff49-57e0-4d36-bba1-320daaf30670/ha-command-and-control-carriageway-impact-incidents ，聚合统计非逐事故真值；可选。
- Incident 时钟：物理触发/形成、管理发现/确认/派遣/到场、权威规则、发布/接收、局部观察；并行流程可选。无真实精确时钟时采用声明参数范围与敏感性实验，不伪造经验分布。
