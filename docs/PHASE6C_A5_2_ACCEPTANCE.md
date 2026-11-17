# Phase 6C-A5/2 开发与验收记录

## 1. 基线及目标

用户上传 A5/1 Hotfix1 完整包、最新版 TeX 与 `phase6c_a5_20261117T025111Z(1).zip`。论文快照与包内 TeX 逐字节相同。报告中 release integrity 207 项、原生 CTest 3/3、有限专项 18/18、数学回归 121/121、全量 470/470；三个 JUnit XML 均无 failure/error/skip。原报告的范围为有限任务和受限合成物理/协议证据，没有真实场景证书、训练或联合仿真。只接受这一历史范围。

本轮目标：将精确时钟、物理单步、协议分支、公共后验与终端任务接受条件联合回放；建立可直接接入 SC 终端回放接口的受限证据；实现一部分可由真实日志间接生成的标签，修复标签来源语义。本轮不改论文算法、不改 MPFR C++ 内核、不启动模型训练。

## 2. 实现及数学依据

- `exact_time.py`：使用 `Fraction.from_float` 检查舍入方向并用 `math.nextafter` 构造相邻 binary64 `[h-,h+]`，严格包含非负有理时间。非有限时间拒绝。
- `a5_replay_bridge.py`：保持原生积分器的 binary64 权威时域。对精确步长 q 只接受 `ceil64(q)` 的完整验证管。先回放原生证据，再在覆盖 q 的子段内计算 `X_i + [q-t_i]_out * F_i`，与段 tube 相交。这两个集合都包含精确时刻状态，交集仍然包含它。精确边界直接使用经验证的初始/终点 box。物理约束在整个稍长外侧管上验证；协议时钟、后继和 rank 仍用 q。该方法依赖 held constant control、静态资源和验证的向量场外包络，不能用于未验证的时变事件/反馈跨界。
- `A5World.resource_forward_axes`：每个可能占用的静态资源须有独立声明的世界坐标方向轴，并验证导数区间点积下界 >=0；仅 v>=0 不充分。此 toy 的方向语义只证明非负纵向投影，不证明完整道路曲线方向约束。仍须 alpha/beta、capacity、踏面等物理模型假设。世界摘要 schema 更新，旧 A5 物理证据需重生成。新检查：change.hi 不得超过当前步；显式声明的 clock relations 必须被时间区间证明。
- `a5_task_tail.py`：独立 `A5TaskGoal` 绑定 6D 目标 box、接受协议模式、相对 deadline 和 version；每个节点有唯一 public policy node ID、严格时间层、一个公共 action。遍历从独立 root 开始的所有声明的后继。每个源 atom 均审计协议和物理 tube；同一观测对所有源 atom 取完整并集，要求等于同一目标支持；冲突 ID、漏分支、缺管、错误时间、未到目标和超期均 UNKNOWN。最长根到叶路径长度×精确步长为 worst time，必须等于声明值。只接受局部相对钟、无消息/延迟、无动态 monitor、无其他移动 actor 的受限 synthetic world。零步接受根目前 UNKNOWN（尚无单独的瞬时几何/资源证据）；允许未来扩展。声明的观测符号和环境完备性是模型假设，不是外部验证的感知事实。整个世界静态，不能把每步局部时间重置解释为真实绝对时钟。
- `seal_a5_terminal/replay_a5_terminal`：先联合审计再产生原有 `TerminalTailCertificate`；重放时重新计算联合审计、policy digest、证据 ref 和精确持续时间；不接受额外 margin。SC 的整体 prefix+tail 相对持续时间仍需外部任务绝对期限审计；不声称完整 SC 的 prefix 分支/物理 provider 已全面接通。没有修改 SC 核心算法。
- `a5_logged_labels.py`：显式 SDC 当前有效、实际未来 prefix 全部有效、目标参与者至少有历史有效点；产生带 source/frame/ego ID、prefix 时间轴及 digest 的 XY 联合轨迹标签。未来缺失用 None 和 mask，不把 focal 当 ego，不包含未来新生 actor 的 identity-conditioned 监督。ego 未来位置序列仅是 logged path surrogate，并非 measured jerk/steering；不能称因果识别。原 inventory v2 区分普通 factual trajectories 与 ego path-conditioned labels。WOMD 相邻已知信号状态差异生成“至少一个切换”区间；不等于唯一事件时间、规则发布/接收或真实观测。缺失/未知/冲突记录不跨越。
- `a5_sampled_occupancy.py`：明确声明 actor/polygon pairs（调用方必须有同一交通表面依据）；只接受 map 几何 polygon + 实际 box dimensions + 中心参考点。Shapely 2D footprint intersection，边界 buffer 掩盖模糊样本；只输出 sampled occupancy 和相邻有效点 sampled entry/stay/exit，不能作为连续事件或法律许可/容量/硬证明。无自动 resource 或架空道路匹配。
- `validate_a5_logged_labels.py`：有界 train/validation 四组日志记录可用性检查，检查抽样 scenario ID/record SHA 跨 split 重复；输出缺失原因及覆盖统计，无数据/依赖时明确不通过。未做全量重叠证明，不自动选资源、不生成全部监督。

## 3. 实际本地测试、失败及限制

- 数据/协议独立回归加新增实际时间及 factual/signal/occupancy 单元测试：99 passed（含 11 时间测试）。
- `pytest -q tests/test_a5_native_discovery.py tests/test_phase6c_a5_finite.py tests/test_a5_exact_time.py`：29 passed；native discovery 使用真实 CMake 测试门禁 dummy fixtures，不代表 MPFR 验证。
- `python scripts/validate_sc_discrete_only.py`：13 passed（载体仅 SC 结构）。
- `python -m compileall -q python tests scripts`、`bash -n scripts/validate_phase6c_a5_2.sh`：通过。
- `validate_a5_logged_labels.py` 对故意不存在的路径返回 3/NOT_PASSED，验证不会把无数据当作成功；没有实际服务器数据可用。
- 已实际 CMake configure；环境缺少 MPFR/GMP development files（MPFR header/library dev link），失败。尝试获取官方依赖也受网络限制。未替换/模拟 native backend，未执行新增真实 MPFR `test_phase6c_a5_task_tail.py` 与 `test_phase6c_a5_bridge.py`。所有新增 native 专项必须在服务器成功后才能接受 A5/2。没有任何“本轮全量测试通过”声明。
- 上述测试集合重叠，不应相加。旧服务器 470 是 A5/1 基线而非 A5/2 结果。

## 4. 服务器门禁（独立目录）

```
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D-A5-2
unzip -q RAMP-D_Phase6C_A5_2.zip -d /home/senzeyu2/code/RAMP-D-A5-2
cd /home/senzeyu2/code/RAMP-D-A5-2
python -m pip install -r requirements-test.txt
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_2.sh
```

脚本保存 native CTest、各项 JUnit、全量 pytest 与失败/成功摘要。任何 error、fail、skip、无测试/测试数下降均拒绝；预期终态 `A5_2_SCOPED_GATE_PASS`，scope 仅 step-relative static synthetic tail and logged label fixtures。请上传 `reports/phase6c_a5_2_*` 目录 ZIP。本轮数学 gate 不启动模拟器或读取真实数据。

另外可独立运行有界数据 smoke（需要已有 WOMD TensorFlow/protobuf reader，AV2 pandas/pyarrow）：
```
python -m pip install -r requirements-data.txt
python scripts/validate_a5_logged_labels.py \
  --womd-root /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario \
  --av2-root /data0/senzeyu2/dataset/Argoverse2/motion \
  --max-records 20 --max-files 3 --prefix-steps 10 \
  --output reports/a5_2_logged_labels.json
```
只有四个 split 均产生所请求数目的独立记录、至少一个可用 factual ego-path 样本、抽样 ID/record hash 无交集才 PASS；这仍不是完整训练集验收。真实数据路径和依赖未在本机测试。下一轮需要检查实际可用率，而不是人为填补缺失。

## 5. 后续路线

A5/2 验收之后：A5/3 多步绝对时钟与动态资源/消息协议、观测关系的独立 cover 证明、外部 actor 多步时间连接、多段验证与任务 automaton 接受，接入 SC 前缀；同时独立完整有限 oracle + margin/deadline 标签。A5/2 的条件性成功不得替代真实场景 full-support。随后构造模拟器日志与配对干预数据、完成八损失 provenance/offline teacher 验收，再进入 RuleNet 训练。详见 `PHASE6C_A5_2_SUPERVISION_PLAN.md`。
