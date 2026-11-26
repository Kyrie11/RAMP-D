# A75 / Phase6C-A59/1b-0U 验收报告

## 本轮范围和证据
以 A74 上传源码、论文和新日志为基准。先分析目标，再修改代码、测试、重放及失败报告。目标：退出门槛 G1-G4 的集成，不以全实车标定作为 Phase7A 前置。服务器 Native 完整 gate 未上传；本地 fresh CMake 缺 MPFR 开发头文件，实际 Native 传播和全量 regression 未运行。无 CARLA/SUMO/Waymax 在线运行，本轮为原始文件复核。未声称 Phase6C 已退出或八项正式标签完整。

## 实际结果
- 80 targeted Python tests PASS（A73 41 + A74 14 + A75 25），另有 `test_sc_inner.py` 一项真实执行器回归待 native server。首次测试出现一项测试写法错误（duplicate 分支在 raises 内 return），修复后通过；保留最终 JUnit。Native configure 失败日志见证据包。
- A74 CARLA review=0 captures 因旧 glob 只读 `*_b*/run*.json`；新工具直接从 ZIP 重放8/8。0.05s 的 .15/.18/.21/.24/.27/.30 峰值减速度 2.286/26.956/11.844/2.549/26.956/26.936；.025s 的 .15/.30 为 2.296/3.289。高减速 .18/.27/.30 时四轮 omega=0、slip≈-.967、sum raw Fx≈-45.1k、sum load≈18.8k，ratio≈2.40，telemetry friction 2.45；与 m*a≈-49.7k 同量级但非逐子步精确力平衡。非单调阈值；dt/初态差异，不能归因唯一子步机制。没有实车保证包络。新增独立 substep CLI。
- Scenario 5/5 官方记录结构与 inventory 声明 ID/hash 一致（原始 shard 不在本地，不能重算原始 protobuf hash）。338 tracks（320 vehicles, 13 pedestrians, 5 cyclists）；5个 validation factual rows、1708有效他车未来 knots、15 future birth IDs未建模；无 train rows。新合同不把 future 路径作为历史，候选条件是离线 logged path surrogate；数据还非完整训练器。
- Waymax 5/5 pair A/AA 完全一致，A/B初态一致；3个自车干预有明显变化（诊断阈值0.1m）；仅index3他车位移约0.1067m；2个静止/近零干预非有效正控制。未来路线特权、其他类型回放、无官方场景ID和明确自车索引的报告不能成为完整因果标签。修正未来 ADE 排除初始点、新增 ego column 输出，服务器重跑待验。
- SUMO A74 sampled rows 与 A73 原始 net、actor trace 重新计算完全一致；9000 evaluation-only，70 vehicles，A/B actor-tick3945/2877，最大4；双strip间距3.2m，非共享车道，连续/ACK mask false。
- ROADWork 65/4；511NY 1500文本类别，未知代码21和缺失1继续隔离。未将报告时钟/图像映射到法律生效和物理资源。

## 代码与数学
- `a73_native_context.contains` 增加维数一致性，`a73_native_multi_actor` ACK/version 类型加强。A74 后继仍仅对声明协议完全，不自动穷尽所有分支，也不是单恒定控制的完整 witness。Native 完整 SafeTube 仍缺独立道路/物理限值/监控/尾策略的联合调用；不要把 conditional screen 接成 `PROVED`。
- `a75_resource` 精确仿射矩形接触监控，绑定准入历史、方向、保护退出、容量、连续清空及右端点新 guard。声明模型；真实动态资源和多边形/旋转还未统一。
- `a75_wait_game` 生成有限联合后继：隐藏开放5/7，receipt延1步，另一actor穿过资源；公共 WAIT/GO、实际接受目标。rank12, horizon11无策略；长期未开放无有限任务完成；遗漏obs、伪终端、rank增大均拒绝。重放共享转移模型，不是独立实现的六维oracle。
- `safe_continuation` 真实执行器接受短rank后立即收紧继承rank/时间，防止用旧松弛预算扩大；纯算术 helper已测，实际 Native-backed SC regression待服务器。
- `a75_contract`, `a75_export_factual`, `a75_sumo_sampled_labels`: 分域、分头、split和缺失mask；尚非完整训练器或全部head启用。详细门槛见A75_SUPERVISION_CONTRACT。

## G1-G4退出及 M1-M13
G1 未通过：先服务器Native gate，随后统一 Native multi Post + SafeTube + 完整协议 + resource monitor + task tail + compute_sc_inner + independent replay。有限等待 oracle 通过不代替该门槛。G2 部分：真实Scenario已过，配对有一个响应但要绑定身份、选择交互样本和闭环评估。G3 未过：仍缺实际同物理共享资源地图与跨模拟器 trace。G4 部分：事实/采样分域合同已工作，训练全局split、全部head adapter和完整loader待补。Phase7A可并行开发，不等G3实车物理；不得宣称正式Phase6C整体退出。

M1 Native pending；M2右端时钟/延迟消息有限实现；M3锁止与步长敏感、未标定；M4真实Scenario/IDM pair已实跑、学习响应未训练；M5采样和有限连续监控；M6历史/准入/清空改进；M7物理ACK未取得；M8声明后继/公共观测合并；M9视觉辅助/消息模型；M10有限等待rank与执行器修复；M11有限重放，完整独立teacher未闭合；M12双strip非共享；M13 factual 1项子目标和 sampled occupancy子目标可评估，完整8/8均未验收。

## 未来有限工作包
1) G1 真正集成，冻结条件声明域，完整 SC positive/negative/unknown 及真实任务尾；不是继续扩大局部实例。2) G3 权威OpenDRIVE/SUMO映射及至少一个共享施工资源、唯一tick/actor source；MUTCD Part 6、WZDx作为场景模板/时间来源，而非自动法律真值。3) G2 train/val全局身份和闭环响应（IDM、学习模型、外生seed，WOSAC realism，严格未来隔离）。4) G4 逐头监督合同和训练器，弱辅助单独；Phase7A已可开始。Phase7B/C联合/证明标签；Phase8 RAMP-D/CCG/SCO/CEGAR/Rank集成；Phase9 E1-E5对照；Phase10复现冻结。必要时缩小声明模型，不放宽 soundness。
