# RAMP-D 1.0.0.dev0 清洁版验收报告

## 范围和输入

基线：用户上传的 `RAMP-D_Phase6C_A59_1b0U(1).zip`，完整 512 个清单文件、361 个 source files，通过原始 `verify_release.py`。论文 `AnonymousSubmission2027(3).tex` 与工程中的 manuscript SHA-256 完全相同（0d9b8e50fd8c0f8aaa89f9979b33c6905211b9f16ed5caa6e388be1d3ca76621）。历史 Markdown 最后为 A72；A73–75 的后续工作以当前工程原始 docs/PROGRESS 和本次上传证据核对。此版本不改论文、C++、动力学、验证算法、控制执行、label mask 和 schema；只做命名、依赖、归档和清晰入口，版本号改为 1.0.0.dev0（不是正式 1.0 发布）。

## 迁移和保留原则

- 43 个核心/辅助/参考模块迁移到无阶段编号的语义名；11 个 CLI 迁移为语义名；54 个旧名称保留薄 alias（无重复算法实现）。模块 alias 使用同一 `sys.modules` 对象，避免双份 class 和 monkeypatch 状态。旧 CLI 委托原参数和退出码。6 个额外语义 CLI 委托旧实现（动态路径读取或有历史回归依赖的文件不重命名）。
- 17 个无活动源码静态引用的历史取证、绘图、早期辅助导出脚本从活跃源码移除，原始 bytes/SHA 单独归档，不永久删除。恢复只在原 A75 checkout，历史 README/文档中的旧命令可能指向归档内容。`docs/CLEANUP_MIGRATION.json` 逐项说明，`docs/MODULE_CATALOG.tsv` 给出每个模块/脚本分类、范围和静态引用计数。
- 仍保留 45 个带编号的实际模块：存在历史依赖、范围受限、直接文件加载或作为回归/取证基线。不能从版本号推断无效，也不能将语义化后的 scoped checker 升级成通用 SC。所有旧测试、fixtures、完整 Native gate 的链式脚本保留。原始 README 移至 docs/history/README_A75.md，新 README 只指向当前入口；历史 docs/PROGRESS 继续保留。
- 例：`a73_native_context` → `native_certificate_context`；`a73_native_multi_actor` → `native_multi_actor_screen`；`a74_successor` → `public_successor_binding`；`a75_resource` → `affine_resource_monitor`；`a75_wait_game` → `finite_wait_reference`；`a75_rank` → `rank_budget`；`a75_contract` → `scoped_factual_labels`。前四项是联合集成基础，有限参考模型不得冒充 6D 连续 proof，scope 不变。
- `a75_reaudit.py` 保留编号作为历史混合审计（其 pair 仍用 argmax 推测 ego，且字段名 valid_samples_including_root 不适配新版；不提升为正式标签工具）。本轮独立复核已用新 JSON 的 ego_controlled_column 核对，未改旧审计算法。`a60_carla_actor_trials.py` 由多项动态直接加载测试使用，保留真实文件并提供 `carla_actor_trials.py` CLI 委托。`a5_finite_contract.py` 和 `a61_carla_calibration.py` 等直接文件路径依赖的模块也未改名。

## 实际 A75 证据复核

| 模块 | 当前证据 | 结论与限制 |
|---|---|---|
| 数学 | a75_recheck 中 rank 12、first WAIT、horizon 11 无解；重新运行有限回归通过 | 声明有限平移博弈；上传 recheck 无 Native gate、CTest 或完整 SC 证书。G1 未闭合 |
| CARLA | 两个 b=.30, dt=.05 原始采集均通过单次记录诊断；max substep .01: peak -26.9359 m/s², stop .35 s, 1.0428m, 四轮锁止；.005: peak -2.7243, 5.9417m, 未观测到持续停车 | 相同 map/weather/dt，初始速度 4.8933 vs 4.8038m/s，单次样本。明显支持子步敏感及轮胎锁止关联，非严格因果辨识、非实车外包络。冻结物理深入实验，后续专注声明域闭环 |
| Waymax | 5 scenarios ×30 future steps (3s), AA=0 all, initial AB=0; ego index/column 一致，重新算 AB 位移与报告一致 | 3 个有效 ego 激励（>=.1m），其中 1 个明显他车响应（>=.01m）；另外两个 ego <.001m 不代表无因果响应。第3号（从0计）他车 4.64194m；未来 route privileged, 模型反事实，ADE 仅报告值，缺原始真值不能独立复算 |
| WOMD | candidate 55 unique IDs/hashes = 50 train + 5 validation；train 16,930 有效 actor-knots、222 future-born IDs；val 1,708、15；总 18,638/237；55 rows 的 training_allowed=0 | 5 val 和独立 validation JSONL 逐条完全相同，禁止合并后重复计数。1s future XY, 11 history knots; 缺地图、事件、资源 token、实测控制；训练原始 protobuf 未上传，全局 split 未证明；train rows 只是候选 |
| 同源地图 | OpenDRIVE 200 roads, 23 junctions；SUMO 191 edges (105 internal), 582 lanes, 604 connections；xodr hash 与两份 CARLA world provenance 一致 | netconvert 元数据表明由相应 xodr 路径转换；netOffset 358.49,404.45，投影和手性需要配准，未选择共享物理资源，G3 未闭合 |
| SUMO | 继承 9000 tick 双独立车道采样结果；本轮未新运行 SUMO | 不作为连续共享物理安全或 ACK 证据 |
| 511NY/ROADWork | 1500 弱文本、65 严格视觉模板，分别来自历史审计 | 当前无新增原始数据，不重新授权；保持未知类别和划分隔离 |

本轮 A75 `recheck` 中 CARLA 仍是 A74 八份旧采集，不能混淆本轮两份新文件。新结果离线独立计算见单独测试证据 ZIP。没有训练模型，没有启动仿真器。已用语义 CLI 和旧 CLI 分别重新导出已有的5个真实 validation 记录，两份结果与上传的 validation JSONL **字节完全一致**。没有生成新的170MB训练 inventory。

## 本地测试

清洁前后使用相同六个既有隔离 harness（不启用 Native）：A73–A75 80、Phase6C 数据/预测/协议 86、A58 19、A59 11、A71 29、SC 离散参考 14，共 239 项各自通过，0 fail/skip。另运行 release-integrity fixture 6 项通过。所有原有 Python 实现（迁移后目标文件、非归档）AST 比较：253 字节相同，35 仅允许 import 名称及明确版本常量更改，无意外逻辑改动。C++、CMakeLists、manuscript 完全相同。静态 Python 内部依赖检查未发现缺失模块；归档文件无现役源码静态引用；Python compileall、shell bash -n 通过。43 模块 alias 中 33 无 Native 的真实导入身份通过，10 因缺 Native 后端不能检验；并未伪造通过。CLI --help 检查非 Native 可执行，CARLA actor trials 与 Native microcase 仍需原生依赖。

Native CMake 配置失败（缺 MPFR development files，运行库存在并不等于开发头文件）；完整 pytest 在原版即因 Native import 无法收集，不宣称历史全量回归通过。请在真实服务器重新构建并运行 `scripts/validate_native_regression.sh`，同时运行完整 pytest/CTest。旧 gate 是条件子验收，不是 G1。动态加载及模拟器运行环境无法以静态分析完全覆盖；此限制通过保留兼容 alias、原始 A75 ZIP、归档和服务器回归降低风险。

## Phase6C 当前退出状态

- G1：未通过完整 Native SC；M1/M8/M10/M11 集成阻塞。
- G2：真实 Scenario 和 5 个 3s IDM pair 已运行；全局 split/正式配对身份和非特权响应仍需完成。Phase7A 数据/训练器开发可以启动，不等于数据正式授权。
- G3：有地图文件，同源哈希一致，配准、共享物理区域、actor/tick owner、观测/ACK 实跑尚缺。
- G4：已有分头事实/采样合同，统一 registry、逐字段 loader、证据授权未完。完整八项端到端监督仍 0/8，绝不是将已有事实标签废弃。

下一阶段的唯一主线是 `PHASE7_TO_10_ROADMAP.md` 中 D1/L1、M1、S1 并行的工作包，以及对应退出合同；不新建 A76 全局探针版本。
