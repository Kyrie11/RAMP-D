# Phase7A pilot 本地验收报告

## 目标与范围
基于用户重新上传的清洁包直接实现 D1/L1，保持 1.0.0.dev0，不新增 A76 版本目录。并行完成 SIM-1 地图清单与配准 preflight，检查 MATH-1 接口和编译依赖。论文原文与 C++ 源码逐字节一致，原有源码没有删除。唯一修改的既有 Python 算法包文件为 `__init__.py`，改用显式公开符号的惰性加载，消除纯数据与 Native 之间的无关硬依赖；不改变 Native 调用的 fail-closed 行为。

## 实际测试
- 新增 30 项 Python 测试：数据原始记录身份/划分、未来泄漏、掩码、共同模式、padding、单场景优化、冻结 encoder、CLI checkpoint 重载、rule sidecar、地图地标及惰性加载。
- 清洁版历史 239 项独立回归 + 6 项发布完整性测试通过。另以正常包导入而非历史 pure harness 的包壳运行 60 项既有数据/预测测试通过（与 239 项重叠，不重复计入总数）。
- 本地 Torch 2.10.0+cpu；无 TensorFlow/waymo_open_dataset，因此真实 TFRecord 读取与真实 training 优化需服务器复核；原始 protobuf 读取逻辑复用已有适配器，unit fixture 用替代 raw reader/decoder 测试，不冒充真实原始数据。
- Native 全新 CMake 配置失败：缺 MPFR 开发文件；无 native 运行/全量 pytest 承诺。数学证书核心未修改，G1 未关闭。

## 实际证据
使用会话中此前上传的 `a74_scenario_inventory.json`（真实 validation 已解析记录，SHA-256 a74047e21a10760ad7b643ae066d8ce59c823a5c0fb9bdfa8061a54c5bec2cca）重新构造 5 个场景，1 秒目标共 1,708 个有效他车坐标点，184 个有有效未来目标的他车-场景实例，15 个未来出现但未建模参与者，0 个当前有效 actor 被 max_agents=128 截断。每个场景选 256 个学习地图 token，地图裁剪不能用于安全证明。未训练模型 seed=7，top1 ADE 0.172595 m，joint minADE 0.168214 m，CV ADE 0.128548 m，top1 last-valid FDE 0.374274 m，joint NLL 1.890264/有效 knot。仅诊断 forward/backward，未对任何真实 validation 更新参数，不能作为模型性能通过。真实 training 场景数 0。原始数据的历史轨迹是有特权日志、不是实测局部可见性。

合成单场景（非真实训练结果），45 epoch，K=2，hidden=16：joint NLL 1.939796 -> 1.841475；top1 ADE 0.355483 -> 0.072190 m。固定 sigma=1m 的 NLL 理论下界 log(2*pi)，因此应看超出下界部分或 ADE 的改善而非期待 NLL 接近零。测试还执行了 CLI 保存和重载。当前尚不能证明真实预测优于 CV 或具有真实反事实响应。

SIM-1：读取会话此前 `a75_map.zip` 内真实同源文件，200 road、23 junction、191 SUMO edge（其中 105 internal）、582 lane、604 connection。OpenDRIVE SHA-256 a90b613175fa837fdc128ddfaf5ddad25797b128fdbd8cd945974bc21a60496e；SUMO net SHA-256 b459a7e23e0cfa2c6292ac336bb6f6abfab0ea169258c00b437d2e5d8bcc6994。没有实际独立匹配地标；配准只通过合成数值测试，不声称物理共享资源/联合仿真成功。

## 失败与修复
首轮地图 holdout 负例恰巧变成共线，正确被更早的几何输入检查拒绝；改成非共线错误对应点后验证 residual 拒绝。真实五场景地图直接截近邻 256 个细边会过度集中，改为约 3m 弧长/角点保留及种类轮转，仍只是神经网络裁剪。增加检查 raw reader 后才能授权训练，不再接受仅凭旧 label JSON 的 split 字符串直接授权。所有限制记录于 PHASE7A_PILOT.md。

## 门槛状态
G1 Native full SC：未通过；G2 WOMD/response：历史真实 Scenario/IDM 已有，本轮真实特征/单损失接口通过，服务器训练及全局源家族划分仍待验；G3：地图清单通过，地标配准/共享资源/联合运行待验；G4：joint 的 bounded pilot 合同已实现，其他七项未授权。Phase6C 不宣布整体退出。

下一轮只需按 PHASE7A_SERVER_RUNBOOK.md 执行小规模数据/训练和并行 Native/map。所有报告保留精确域；后续按 head 独立增加，修复原模块，不增加版本编号实现。详细损失顺序、验收门槛见 PHASE7A_PILOT.md。
