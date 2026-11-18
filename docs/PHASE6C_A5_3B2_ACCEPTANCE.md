# Phase 6C-A5/3b-2 验收说明

## 基线与范围
输入为用户本次上传的 A5/3b 第一增量完整源码和 20261117T143514Z 服务器报告；论文快照与本次 TeX 完全一致。服务器基线：3 native CTest，29 finite，128 data/rules，146 math，550 full Python（有重叠）；限定声明模型通过，不是现实完整证书。真实 AV2 两 split 均因 double 列拒绝失败。Waymax 日志 10→11 对齐通过；没有反事实或 WOSAC 指标证明。

## 变更与数学依据
- AV2 官方端点 double (ns) 与 exact integer/timestamp 分离。以存储值的精确整数差构造相对有理时间；记录 float hex、条件单次 nearest rounding cell，绝不宣称恢复原始 ns。接受 double 仅限官方端点，不接受 float per-row timestamp_ns。缺一端点、倒序、不合法值拒绝。真实 Arrow 单文件测试增加 double 与秒 fixture。数据时钟不是证书时钟。
- 保留 E1 原生 Picard validated tube、E2 绝对任务时钟、E3 event slab 与所有声明分支权限交集。新增 ActorEnvelope: Cartesian p,v 和 unwrapped heading，固定几何、加速度和 yaw-rate 有界。p(t)=p0+v0*t+integral_0^t (t-s)a(s) ds，非负积分核给出 t^2 A/2 外包络；各 actor 可任意相关，笛卡尔积不假设独立性。全程使用 MPFR 区间运算。
- 在每个协议 atom 声明独立 actor 初态；子区间传播始终从该控制步初态出发。所有可能的后继 atom 均覆盖完整传播的其他车辆状态；禁止丢弃/重置/新建未声明 actor。禁止复用未绑定到 source atom 的历史全局 actor tube。逐规则段与 Picard 段交集检查两两 footprint 分离、全部可能占用的容量、方向投影、冲突与 safe_domain。
- 这是充分条件的内近似：对可能占用要求 alpha 与 beta，尚未支持 entry/stay/exit 的计时证明；未建模参与者新增、消失、几何高度、非矩形静态障碍、动态 guard、pending message、连续事件时间分支、完整观测关系及 actor 模型覆盖。声明的加速度/yaw-rate 界必须由独立模型域提供；不能将神经预测区间或有限仿真样本当成普适包络。
- 计划施工 interlock 的 clearance 区间证据新增 event/version/resource identity 检查，避免将其他区域的空闲证据误用于部署。ACK 仍是外部证据接口，本轮不是仿真实验。旧交替通行参考控制器尚不具备持续清空/黄灯全红证明。
- IncidentEvent/TIM timeline 与 reactive rule record 分离。未观测时间为 None，不凭空生成 0；不假设本地检测与消息到达的固定顺序；外生 trigger signature 不等于部署或事故结果在干预下不变。MUTCD merging taper 指导公式按英里/小时与米转换计算，拒绝表未规定的速度区间。
- WZDx registry+Texas flattened CSV 基础审计：枚举来自用户提供 v4.2 schema，WKT 使用 Shapely 检查。无 Feature ID、feed header 与完整 lanes，不能做 full GeoJSON validation 或数独立事件。报告只记录必要统计与文件哈希，不暴露 registry 中 URL/token。规范引用的外部 GeoJSON schema 需要后续离线缓存才能完成全 schema 校验。

## 本地实际测试
- 141 项 dependency-free tests passed（包括既有数据/协议、13 个新增纯 Python 测试）。
- 29 项 finite/exact-time/门禁 tests passed。
- 13 项 SC 离散数学 tests passed，集合与其他测试可能重叠。
- 3 个新 native-only moving-actor 测试函数已编写，待服务器执行；包括解析极值包络、多步隐藏后验连续性与缺失状态、碰撞/容量/方向/错误终点的独立拒绝。
- 上传 WZDx: 43 registry rows（42 active），2373 event projection rows；全部枚举通过、2373 geographic lines 基础检查通过；四个时空确认旗标全 false，不产生 formal event labels。独立 JSON 包含哈希。
- Native CMake 在本机因 MPFR/GMP 开发文件缺失而失败；PyArrow 在本机缺失。未模拟/替代原生 ABI、未有新 native/full regression PASS。没有服务器数据、没有运行 CARLA/SUMO/Waymax 响应/WOSAC 指标。

## 服务器门禁
新目录解压后 `python scripts/verify_release.py`，`bash scripts/validate_phase6c_a5_3b2.sh`。需重建原生库，3 CTest 必须通过，全量不得有失败/跳过，至少 550 个基线测试并包含全部新增测试。`A5_3B2_SCOPED_GATE_PASS` 仍限定于声明模型。真实数据独立检查见 README。
