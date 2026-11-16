# Phase 6C-A2 实现与验收报告（本地条件验收）

日期 2026-11-16；论文版本 `AnonymousSubmission2027.tex`（本轮上传的最新版本）。

## 1. 本轮交付与错误修复

| 文件 | 变更 |
|---|---|
| `python/rampd_core/map_context.py`（新增） | `MapVertex/MapPrimitive/SignalRecord/MapContext`；WOMD map feature/逐帧 signals、AV2 lane segment/crosswalk/drivable areas、静态 geometry 和动态 label 区分、protobuf optional message presence 检查 |
| `python/rampd_core/record_adapters.py` | 将解析后的 MapContext 绑定统一 scene；localize 时轨迹、地图点、stop_point 同步变换；AV2 archive digest 保存 |
| `python/rampd_core/scene_schema.py` | 加入完整场景的 map contract/时间轴；`online_view` 裁掉未来 signals/未来 time metadata |
| `python/rampd_core/phase6c.py` | `SceneForecastSample.map_context_history` 只保留当前及过去的 logged signals；`future_signal_targets` 仅用于监督；`encoder_inputs.static_map` 只输出静态几何 |
| `python/rampd_core/protocol.py` | 新增 versioned `SilenceExclusionEvidence` (exact `Fraction` deadlines + message/version/contract digest/modes)，legacy bare bool 不再被当作可复核 exclusion proof |
| `python/rampd_core/full_verifier.py` | silence 分支若删除任一原始 hidden mode，必须提供经 deadline/version 检查且显式覆盖该 mode 的 evidence，否则 UNKNOWN |
| `scripts/validate_phase6b.sh` / `validate_phase6b_real.py`（新增） | 补全输入工程缺失的主脚本，增加数据检查、SHA-256 provenance、严格 EXIT=0/3/4 和 zip report |
| `scripts/validate_phase6c_a2.sh`（新增） | 独立纯 Python 数值/合同测试与 compile/shell syntax gate |
| `tests/test_phase6c_a2_map.py`, `tests/test_phase6c_silence_evidence.py`（新增） | 实际 schema 形状、坐标一致性、mask、在线/未来信号分离、无 protobuf presence 的默认坐标、精确 deadline、协议版本、evidence digest 回放 |
| `tests/test_phase4_protocol.py` | legacy 裸布尔由旧“PROVED”期望修订为正确的 UNKNOWN，加有明确 deadline evidence 的 positive case |

## 2. 本地实际验证

```text
$ python3 scripts/validate_phase6c_a_dependency_free.py
67 passed
$ bash scripts/validate_phase6c_a2.sh
67 passed
PHASE6C_A2_LOCAL_STATUS=PASS; native=false; real_data=false; formal_certificate=false
```

并执行了源代码 `compileall` 与 bash 语法检查，完成额外的缺失数据路径 fail-closed gate（退出 3）。数据 adapter 的单测保留之前 25 通过 1 失败中的真实逻辑；对 parquet mock 的 pandas 污染通过独立的 pandas 替身隔离，在 67 条定向测试中没有重现。

**本轮容器没有**用户服务器 `/data0/...` 的真实 WOMD/AV2；也没有目标 MPFR 4.x development headers，无法执行 C++/Python Native full-suite，因此 Phase 6C-A2 是 `LOCAL_CONTRACT_PASS` / `SERVER_REAL_DATA_PENDING`，并非整个 Phase 6C 已验收。完整 native CTest/Phase 4–5 proof checker 本轮新增逻辑仍待服务器回归。

## 3. 未能严格证明之处

- `MapContext.complete_geometry` 是 parser coverage 标记，非车身/road/resource 不确定性下的 interval geometry certificate。构造的 AV2 lane polygon 是两侧边界拼接的名义形状，未经区间 outward rounding。
- 所有 `SignalRecord` 是数据集**记录的状态**，包括过去状态也并未被证明由自车传感器看到；在线 encoder 默认不喂入任何 signals。四时钟必须另行从 simulator/protocol 注入。
- `SilenceExclusionEvidence.guarantee_contract_sha256` 是**绑定外部可信协议文档的指纹**，不是由代码自动验证的通信硬件/协议公理。其 `PROVED` 是在可信 publication/delivery 假设成立时的条件证明；缺少真实 guarantee source 或无法重放系统执行时，不能将其作为车规级安全结论。
- `S_infinity` 的 forever-safe invariant 不等于论文新增 `W_H^{SC}` 的 finite task winning set。当前未实现带 terminal completion certificate 的 inner recursion/rank/physical margin DP 和 CCG 三层 product/refinement；保留 TODO，不编造输出。
- 未得到真实 PARQUET/TFRecord 验收，不能宣称 AV2/WOMD 数据 pipeline 已通过；未训练 prediction 或启动 simulator。

## 4. 服务器正式验收命令

```bash
cd /home/senzeyu2/code/RAMP-D
# 先进入 Python 3.10 的正式环境，例如 conda activate mfrp
python -m pip install -e '.[test,datasets]'
export WOMD_ROOT=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
export AV2_ROOT=/data0/senzeyu2/dataset/Argoverse2/motion
export MAX_RECORDS=1
bash scripts/validate_phase6c_a2.sh
bash scripts/validate_phase6b.sh
# 检查 reports/phase6b_*/phase6b_acceptance_summary.json 的双 PASS + SHA
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
(cd build && ctest --output-on-failure)
PYTHONPATH=python python -m pytest -q tests/test_phase4_protocol.py tests/test_phase4_full.py tests/test_phase5_cegar.py
```

若无原生库，先按 README 和 `docs/NUMERICS_AND_SCOPE.md` 构建/设置路径；不能因 native tests import fail 就跳过并标记 PASS。

## 5. 失败诊断/验收标准

| 条件 | 输出/动作 |
|---|---|
| Python 版本低于 3.10 | 4 ERROR；退出 Python 2.7 环境重进项目 env |
| 缺数据目录/缺 pyarrow/protobuf | 3 SKIP；依赖和目录恢复再跑，不可归为 PASS |
| 错误地图归属、signal 时间错位、未来输入泄漏、未解析 map feature | 4 ERROR；存报错和 scene ID，按 adapter 修复 |
| 67 dependency-free tests + 双数据集真实 smoke | 0 PASS；仍需完整 native suites 才能声明 Phase4/5 回归通过 |
| 单个候选失败、solver timeout、模型预测高风险 | UNKNOWN；都不能当作 supervised negative 或物理碰撞证明 |

**下一轮建议**：用户提供本轮 `RAMP-D_Phase6B_server_report.zip` 和 Phase4/5 native CTest 输出后先关闭真实数据和协议证据回归；再为最新论文 `W_H^{SC}`, rank, tail contract, `V_H^{SC}` 补独立可验证算法和测试，随后才进行 6C-B CARLA/SUMO 双无头最小闭环。
