# RAMP-D A5/3b-5 — 验收与失败分析

## 1. 输入与基线
基于用户上传 RAMP-D(4).zip（含 ROADWork 自行修复），保留最新版 TeX，不改变原生 MPFR 后端。3b-4 上传服务器报告：3 CTest、29 有限、166 标签协议、155 数学专项、597 全量 Python；无失败或跳过。用户后续修改 ROADWork 的真实运行报告为 BOUNDED_ROADWORK_ALIGNMENT_PASS（5318/2098 图像，60757/21261 原标注，1 个 val 零宽 Fence）。Waymax 8 个离散动力学测试通过，最大标量误差约 1.12e-6，制动过零出现负速度；不代表响应已验证。

## 2. 实现内容与范围
- a55_motion.py：前向恒加速度/恒曲率连续参考解，停车事件切分，稳定 sinc 位置公式。不是 jerk/steering-rate 证书。
- resources.py / a53b_occupancy.py：区间 SAT 的四组轴，带车身参考点偏移，严格重叠、严格分离；可证明部分旋转车体持续占用；alpha 与 beta 分离。边界接触不算分离，不以外 AABB 重叠当实际碰撞。新增原生测试尚待执行。
- audit_roadwork.py：保留用户零面积框策略，限制 split 路径候选，区分原始与几何有效实例、图像数及共现，抽样 mask 标量直方图校验；不将 16-bit 标签误当错误，不假定 class ID 含义。
- audit_511ny.py：数据字典驱动的有界/全量流式行级审计，纽约路政代理筛选、时间格式、DST、缺失/负/零/异常寿命、地理范围、分组直方图。不是唯一事故统计、不是 RCT/ICT，也不是训练标签。CSV 本地未提供。
- probe_waymax_response.py：官方 IDMRoutePolicy + StateDynamics，双车固定直线 fixture，以 WOMD TFExample 形状模板创建合成轨迹，A/A、A/B 同步干预、逐步输出与数值检查。仅首次运行验收，不是现实反事实数据。
- probe_sumo_alternating.py：netconvert 生成双向逻辑走廊，TraCI 读车辆路线与车头/长度、完整 roster、实际队列、红灯入区与 swept occupancy，执行/读回相位，记录日志、车辆轨迹、图。两条物理独立 SUMO 方向车道共同占用一个逻辑互斥资源，不是 CARLA 物理单车道。信号时长为明确实验参数，非现场工程设计值。
- validate_phase6c_a5_3b5.sh：保持严格原生门禁；新独立/原生回归，≥597 全量测试且无跳过。实际模拟器须单独运行，数学报告不会自动声称其通过。

## 3. 本地测试与失败分析
- 与本轮 gate 同一独立回归集合：190 passed；有限/精确时间门禁：29 passed。
- 开发中发现新增 8-bit mask 上限错误拒绝合法 scalar 16-bit PNG，原有回归暴露后已删除该假设，保留范围报告且不推断类别。修复后独立回归通过。
- 当前运行环境无 MPFR 开发头、Waymax、SUMO/TraCI；新增原生 SAT、全量 pytest、实际 IDM/SUMO、真实 ROADWork 新版/511 CSV 均待服务器。未使用替代浮点证明后端。
- 逻辑走廊 sweep 依赖单调 route coordinate 与完整参与者 roster；SUMO 离散车辆坐标不提供真实连续物理证书。命令回读不等于真实执行机构故障覆盖。

## 4. 验收顺序
1. 新目录解压，`python scripts/verify_release.py`，`bash scripts/validate_phase6c_a5_3b5.sh`。
2. `export RAMPD_INTERVAL_LIB="$PWD/build_phase6c_a5_3b5/librampd_interval.so"`，运行 Waymax 双车响应与 SUMO 逻辑走廊。两者 JSON 必须独立分析；若 ERROR/REVIEW_REQUIRED 不产生标签。保存 stderr、SUMO netconvert.log / sumo.log 与 vehicle_trace.jsonl。
3. 重新执行 ROADWork audit，运行 511NY audit；确认实际文件、时间假设与分组数据。无需下载新大数据集。
4. 上传数学报告 ZIP、Waymax 响应 JSON/PNG、SUMO JSON/PNG 与 work 子目录、ROADWork JSON、511NY JSON。若脚本报错保留原报错。
