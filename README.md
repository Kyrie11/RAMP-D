# RAMP-D Phase 5（0.8.1）

本版本在 Phase 3 的公共采样恢复策略之上，增加显式有限协议自动机、四时钟消息语义、资源占用/容量监视、声明式他车响应管、观测后验聚合，以及 `CERTIFIED / COUNTEREXAMPLE / UNKNOWN` 三值全支持验证接口。Phase 1A–1D 的 MPFR/C++ 数值内核保留，**原生 ABI 仍为 3**。

开发顺序保持：明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告。

## 当前完成范围

- `SampledFeedbackLaw`：共享参数的仿射反馈、显式控制饱和、测量误差区间像；
  每个决策时刻由实际 ego 测量计算一次命令，并保持到下一个决策时刻。
- `recovery_candidates` / `synthesize_backup`：对 brake-to-stop、hold-before-gate、
  yield、clear/merge 四类模板作有限候选搜索，按已验证空间余量下界排序并保留备选。
- `validate_feedback_step` / `inspect_step_proof`：生成并回放 Picard tube，结合
  有证明的解析界检查状态边界、摩擦、完整车身 footprint、道路、gate 与静态障碍。
- `LocalEvidenceStore`：将当前完整 belief support、公共律、源 atom、观测后继、
  决策周期、扰动及场景契约与实际证据绑定；哈希不能替代数学回放。
- `build_backup_graph`：复用 Phase 2 的信息状态固定点，获得所有观测续接均闭合的图。
- `BackupExecutor`：按精确时间执行公共律，收到实际 observation 和 posterior 后
  更新节点；证据失效、未知观测、时间错位或支持集越界时停止本执行器并报错。

Phase 2 服务器报告已复核通过其有限抽象范围。本轮同时修复了旧证据接口未绑定
当前验证义务的问题，并移除了验证脚本对 `.tex` / `.bib` 的强依赖。

Phase 4 首版只在可穷举的合成协议与显式连续证据契约上验真；它没有把 MTR++、QCNet、QCNeXt 的概率输出当作安全支持，也没有接入 WOMD、AV2、CARLA 或 SUMO。

## 保证边界

本版本的首版合成保证范围固定为：

```text
PHASE4_EXPLICIT_PROTOCOL_SUPPORT
full_support_certified = false
current_scene_verified = false
```

它覆盖有限协议、声明的六状态 bicycle/他车响应模型、有界导数扰动与测量误差、
动态资源 monitor、完整 footprint 外包围，以及调用方显式提供的有限 observation
cover。历史 Phase 3 的 `LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS` 范围仍保留在回归报告中；真实交通中的完整协议、动态资源、移动他车和观测关系仍需在声明式合同之外逐步接入，当前 Phase 4 的合成验证结果不等同于真实场景安全证书。

四类模板在非零过程扰动和测量误差下验证的是**一次决策区间的局部目标**。
`clear_merge` 示例证明受约束的横向推进，不代表已经完成合法合流；受扰
`hold_before_gate` 示例证明局部近零运动，不代表无限时间鲁棒驻停。

17 节点制动/驻停闭图是单独的零过程扰动合成 fixture：每个节点同时保留
`rule=open/closed` 两种隐藏模式，仅使用 `silence` 观测，不提前区分隐藏状态。
车辆从 4 m/s 出发，前 2 s 使用 jerk −1、后 2 s 使用 jerk +1，在 **4 s、8 m**
处达到 `v=a=0`；20 步、每步 0.25 s 的总执行时长是 **5 s**，包含后续 1 s
驻停执行。其终端闭环不应解释成非零过程扰动下的无限时间驻停保证。

配置 `configs/backup_benchmark.json` 的参数是明确标注的 benchmark 参数，
不是已校准的真实车辆参数。通用局部模板允许小幅有符号速度，具体边界见配置；
没有通过裁剪状态或容差把负速度伪装成精确停止。

## 车辆与数值约定

状态顺序为 `(px, py, psi, v, a, delta)`，控制顺序为 `(jerk, steering_rate)`。
`(px,py)` 使用后轴中心；`VehicleGeometry` 的 `center_offset_x_m/y_m` 明确描述
车身矩形中心相对后轴的位置，gate 和道路检查使用完整 footprint。

附带 CommonRoad BMW 320i nominal profile 可用于可复现合成测试，其车身中心
offset 含几何近似，实际 CARLA/车辆测试须重新校准。摩擦是场景参数。详见
[车辆参考约定](docs/VEHICLE_REFERENCE_CONVENTION.md) 与
[数学更正说明](docs/MATHEMATICAL_CORRECTIONS_PHASE3.md)。

浮点输入表示对应的精确 binary64 常数。MPFR 运算使用有向舍入；Picard
见证回放与解析二次极值外包提供数值依据，采样轨迹只作独立反证审计。

## 服务器环境与一键验收

继续使用你已有的服务器环境，无须为 Phase 4 升级 Python、GCC、CMake 或 MPFR：

| 项目 | 已知目标服务器环境 |
|---|---|
| Conda 环境 | `mfrp` |
| Python | 3.10.20 |
| GCC | 9.4.0 |
| CMake / CTest | 3.18.0 |
| MPFR | 4.0.2，需官方开发头文件及 GMP |
| 原生 ABI | 3，本轮未升级 |

本轮本地测试使用 Python 3.12、GCC 14.2、官方 MPFR 4.2.2 发布版头文件及
4.2.2 运行库，**不是 declaration-only bootstrap**。本地结果不替代你的
目标服务器复核；目标服务器兼容性仍以新报告为准。

把 `RAMP-D_Phase4.zip` 放到 `/home/senzeyu2/code` 后运行：

```bash
cd /home/senzeyu2/code
conda activate mfrp
unzip RAMP-D_Phase4.zip
cd /home/senzeyu2/code/RAMP-D_Phase4
python -m pip install -r requirements-test.txt
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase4.sh
```

压缩包使用新的 `RAMP-D_Phase4/` 顶层目录，原来的 `RAMP-D/` 工程可保留。
首次解压应使用尚不存在的新目录；已有同名测试目录时请先保留旧结果。
命令没有 `--upgrade`，不要求升级已有基础环境。

验证脚本会重新编译到 `build_phase3/`，发现并运行原生测试，执行全部 Python
测试、Phase 1A–2 回归、Phase 3 演示与微基准、图回放和验收门槛检查。
`.tex` / `.bib` 仅在存在时作为可选来源哈希记录，缺失不影响验证。

最终报告位于：

```text
reports/phase4_<UTC时间戳>/
reports/RAMP-D_Phase4_server_report.zip
```

请上传 `reports/RAMP-D_Phase4_server_report.zip`。脚本失败时也会尽力生成
包含失败阶段和日志的报告；不要只上传终端最后几行。

自定义 MPFR 安装可从 Phase 4 入口传入 CMake 参数，例如：

```bash
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase4.sh \
  -DCMAKE_PREFIX_PATH=/your/existing/mpfr/prefix
```

如果单独运行 Python 调试命令，先明确使用本轮生成的库：

```bash
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$PWD/build_phase3/librampd_interval.so"
python -m pytest -q tests/test_backup_synthesis.py tests/test_backup_graph.py
```

## 实际 API 示例

以下例子在完成构建并设置上面的两个环境变量后可直接运行。它使用附带的
合成 bounded-error yield 问题演示真实综合接口：

```python
from rampd_core import RecoveryKind, synthesize_backup
from rampd_core.phase3_examples import template_problem

source, candidates, targets, store = template_problem(RecoveryKind.YIELD)
result = synthesize_backup(source, candidates, targets, store)
print(result.status, len(result.choices))
if result.selected is not None:
    print(result.selected.law.to_dict())
    print(result.selected.observation_children)
```

同一 `BeliefCell` 的全部 source atoms 使用同一个反馈律及参数；同名 observation
对应的所有后继必须合并后被**同一个** target belief 覆盖。`controller_ref`
绑定完整公共律，`ActionWitness.control` 在反馈律存在时表示其 bias，不能被
当成整个控制器。

创建、保存和独立回放闭图：

```python
from rampd_core import save_backup_graph, load_backup_graph
from rampd_core.phase3_examples import (
    benchmark_contract, build_braking_graph, execute_braking_graph,
)

contract = benchmark_contract()
graph, search_reports = build_braking_graph(contract)
save_backup_graph(graph, "backup_graph.json")
verified = load_backup_graph(
    "backup_graph.json", expected_contract_digest=contract.digest,
)
trace, terminal_v_zero, terminal_a_zero = execute_braking_graph(verified, steps=20)
print(len(verified.nodes), terminal_v_zero, terminal_a_zero)
```

生产调用方须从自身已核实的当前场景配置取得 `expected_contract_digest`。
证书自述的 digest 只能标识其假设，不能证明当前真实场景满足这些假设。

## Phase 4 API 示例

```python
from rampd_core.phase4_examples import run_examples
from rampd_core.forecast import PredictionProposal, proposal_only, hard_support_from_prediction

print(run_examples())  # synthetic CERTIFIED / COUNTEREXAMPLE / UNKNOWN
# MTR/QCNet/QCNeXt proposals remain ranking metadata.
```

`OtherAgentModel` 必须绑定完整的动力学、扰动、ego 响应增益和模型 digest；
`FullVerifierContract` 没有 model digest 时固定返回 `UNKNOWN`。

## Phase 5 CEGAR

Phase 5 adds concrete/spurious counterexample classification, event-time and support/observation refinement, version-bound evidence invalidation, master updates, and a resumable re-verification scheduling skeleton. Evidence callbacks, replay callbacks, and verifier failures are fail-closed to `UNKNOWN`; receipt/local public-clock obligations carry the responsible clock so CEGAR can refine the correct clock. Run `PYTHON_BIN="$(command -v python)" bash scripts/validate_phase5.sh` on the target server. The scope remains synthetic explicit protocol support; it does not certify real scenes.

## 文档与下一阶段

- [Phase 3 设计](docs/PHASE3_DESIGN.md)：本轮目标、接口、控制综合和保证边界。
- [Phase 3 验收](docs/PHASE3_ACCEPTANCE.md)：验收要求、结果文件和服务器步骤。
- [Phase 3 失败记录](docs/FAILURE_LOG_PHASE3.md)：反例、修复依据及预期 UNKNOWN。
- [Phase 2 审计与修正](docs/PHASE2_AUDIT_AND_FIXES.md)：上传服务器证据和接口更正。
- [数学更正](docs/MATHEMATICAL_CORRECTIONS_PHASE3.md)：信息状态、数值界与理论边界。
- [综合专项独立测试](docs/PHASE3_SYNTHESIS_TEST_REVIEW.md)：物理与证据绑定的失败分析。
- [数据集及模拟器](docs/DATASETS_AND_SIMULATORS.md)：AV2/WOMD 格式、已有路径和分阶段接入。
- [开发路线](docs/DEVELOPMENT_ROADMAP.md)：0 → 1A → 1B → 1C → 1D → 2 → 3 → 4 → 5 → 6。
- [Phase 4 工程报告](docs/PHASE4_IMPLEMENTATION_REPORT.md)：协议、资源、他车、观测和验证器实现。
- [Phase 4 验收](docs/PHASE4_ACCEPTANCE.md)：23 项专项测试、317 项历史回归及失败案例。
- [Phase 5 计划](docs/PHASE5_PLAN.md)：CEGAR 细化边界和契约。
- [Phase 5 工程报告](docs/PHASE5_IMPLEMENTATION_REPORT.md)：实现、时序修正和本地验证限制。
- [Phase 5 验收](docs/PHASE5_ACCEPTANCE.md)：具体/伪反例、细化、失效和队列 gate。

下一阶段是 Phase 6：接入 AV2/WOMD adapters、四时钟仿真日志和 SUMO/CARLA 闭环实验。Phase 5 的 CEGAR 仍只针对显式合成协议。
**本轮验收不需要下载数据集，也不需要启动 CARLA 0.9.16 或 SUMO 1.20。**
