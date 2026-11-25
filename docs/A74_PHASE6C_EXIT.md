# A74 / Phase6C-A59/1b-0T 验收报告与有限退出合同

本轮基于用户上传 A73 源码、论文和原始实验结果。A73 Native gate/CTest 未随结果上传，当前容器无 MPFR/GMP 开发头文件，未完成 fresh native build；Waymax、CARLA、SUMO 未在本容器重新运行。55 项针对性纯 Python 测试通过（旧41+新14）；非全量回归。实际离线重放和失败证据在独立 ZIP。所有正式授权仍为 false。不是全 SC 认证或 Phase6C 退出。

## 实现与反例
- `a73_joint_reference` 修复边界初触后进入却不检查 entry 的漏洞；严格内部与历史合法占用仍需完整 monitor。`a73_guard_trace` 分离规则版本与命令 epoch；仍非真实 ACK 证明。
- `a74_successor` 将声明的 Native 证书端点绑定到所有观测下的联合后继，独立 roster、单值自车动作、潜态及目标 cell 覆盖。声明 outcomes 的完备性仍为假设；未接入完整 compute_sc_inner。`a74_finite_policy_replay` 独立遍历有限策略树（共享底层几何规则，不是独立实现的物理 oracle）。Native 微例增加遗漏同观测世界负例。
- CARLA 18份原始采集17份严格通过，pure_b015/run03 首个 post tick brake readback=0，第二个匹配；不要删除异常或把 readback 当力学延迟。每格合格响应归一化后完全重复，不能给出统计泛化方差。0.15 纯/联合行驶峰值 -2.285791/-2.379596；0.30 -26.935860/-26.927363；0.45 -26.934974/-26.926565 m/s²。0.15 两秒内持续停车右删失；高档0.35s。新增可选 get_telemetry_data 原始字段记录，实际可用性待服务器确认。PhysX Vehicle 是默认来源假设，需本地构建核实；未定位异常根因。
- Waymax 5/5 TFExample，228 actor-scene occurrence，10332相邻有效对；Scenario DecodeError。新增 TFRecord 格式探针（不自动混用 protobuf）及实际场景初始化 A/AA/B 模型响应脚本（A ego按日志下一状态，B简化制动，其他受控车辆IDM，其他类型回放；未来路线特权，仅离线模型域；未运行）。
- SUMO 9000 tick，70 depart/arrive，A/B actor-tick 3945/2877，最大4，逻辑 swept 多70 actor-tick。中心线间距3.2m，两条 lane strip 无内部重叠。原审计 A-only polygon 零错误，新增双方向非空覆盖检查拒绝；仍非一般完整地图覆盖证明。rule_version仅1，无物理ACK。采样 occupancy JSONL 不授权连续或现实标签。
- ROADWork 447 train、2098 val、2043 quarantine，100m已知 GPS 检查非真实地点隔离证明。69旧模板与严格清单逐项绑定后65保留4隔离。511NY 1500文本报告类别，21数值码隔离；历史一条缺失类别另隔离。不作为法律生效时间。源类型分开。

## 四个有限退出门槛
G1：fresh native 和继承全回归；代表性的声明模型多车/至少两隐藏分支、同观测合并、道路/动力学/资源 SafeTube、完整协议后继、真实任务接受与 rank，经独立重放；至少遗漏世界、错误时钟、禁入、伪终端、不可行负例。不是要求全实车 ODD。
G2：WOMD 原始 source ID 和 split 完整，bounded factual label 不泄漏；至少一组真实初始化反事实模型正负控制，失败按模型域标记。训练/验证分开。
G3：至少一处真正共享物理资源的同地图 SUMO/CARLA 联合运行；唯一 tick owner、唯一 actor 状态权威、坐标配准、command epoch 与 rule version、执行/几何读取和缺失 fail closed；不得用双独立车道替代。
G4：按 head/domain/target mask 证据合同，原始来源和 split 清单、无未来泄漏；正式数学标签仅在 G1 适用域证明时授权。无需八头全部满覆盖才允许 Phase7A。

## 后续阶段（新建议，非历史既有 Phase7–10）
Phase7A 可现在并行：真实事实/弱辅助数据和模型训练接口，保持证据域。7B 在G1/G3后开放可验证的仿真及证明标签，独立 teacher 和验证集。Phase8 将论文 CCG/SCO/完整 verifier、CEGAR、rank-preserving 重规划闭环。Phase9 论文 E1–E5 对照和消融（分布、UNKNOWN率、置信区间、计算量）。Phase10 冻结依赖、配置、数据清单、可重放证书、实验表及论文声明。若 G1–G4 未过，明确局部 blocker，不再以无限增加 A 探针代替集成。

M1 Native pending；M2 版本/时钟 partial；M3 物理17/18且模型边界 unknown；M4 TFExample pass、Scenario及真实初始化响应 pending；M5 多车连续/采样资源 partial；M6 entry/epoch 修复、完整监控 pending；M7 readback != ACK；M8 同观测 Native binding pending native；M9 visual only；M10 finite policy replay、tail待扩展；M11 finite replay、完整独立负证明待集成；M12 双strip非联合共享资源；M13 0/8 formal end-to-end，事实及辅助可按域训练。
