# Phase 2 服务器验收复核与本轮修正

## 1. 结论与证据范围

已复核用户上传的 `RAMP-D_Phase2_server_report.zip`，报告目录为
`phase2_20261111T034131Z`（目录时间为 UTC）。**Phase 2 在其声明的有限抽象
信息状态固定点范围内，通过服务器验收。** 原有固定点递推、同一 belief 内
共享当前控制、按同一观测聚合 posterior、同步删除和保守支持集包含检查，
在本次审阅中未发现需要改变的算法语义。

它仍不是完整车辆安全验收。报告明确保留
`assurance_scope=FINITE_ABSTRACTION_ONLY`、`concrete_safety_certified=false`。
Phase 3 继续综合公共 backup controller；协议、资源监视器与完整观测支持的
联合安全证据，依旧归入 Phase 4。

本轮发现并修正的重点是：旧的证据回放 API 无法把证据绑定到当前待验证的
源支持、公共控制和后继分支。该接口必须在接入真实 tube 证据前修正。

## 2. 已核对的服务器结果

以下数值均来自上传报告，不是本轮在当前执行环境测得的结果。

| 项目 | 服务器证据 |
|---|---|
| 编译器与 MPFR | GCC 9.4.0；MPFR runtime 4.0.2；官方 4.0.2 头文件；192-bit directed MPFR；ABI 3 |
| Native CTest | 3/3 通过 |
| Python pytest | 129 通过，0 失败、0 错误、0 跳过 |
| Phase 2 专项测试 | `tests.test_belief_invariant` 17 项 |
| Phase 2 演示 | 保留 `A,L`；固定点 1 轮、删除 0；候选证书回放通过 |
| Phase 2 微基准 | 50、100、250、500、1000、2000 cells 均保留全部 cells，均 1 轮收敛 |
| 2000-cell 微基准耗时 | 0.029051855206489563 s，单次计时 |
| Phase 1C 回归 | 三种方法均 `VALIDATED` 且回放通过；adaptive 最大已接受宽度比 0.9886314837100184 |
| Phase 1D 回归 | AABB 重叠为 `UNKNOWN`；oriented 与 dense axes 为 `SEPARATED`，回放通过 |
| 连续状态抽样反证检查 | 64 rollouts、20,480 state vectors，0 containment misses |
| 几何高精度抽样反证检查 | 2,000 samples、40,000 projections，0 misses |

原始证据文件：`acceptance_summary.json`、`pytest.xml`、`environment.json`、
`phase2_demo.json`、`phase2_benchmark.json`、`phase1c_benchmark.json`、
`phase1d_benchmark.json`、`empirical_audit_phase1b.json` 与 `footprint_audit.json`。

两项抽样检查只能用于寻找反例；“0 misses”不能升级成独立的数学安全证明。
数值包含性的依据仍是 directed-rounding 运算和 Picard 见证回放。

### 2.1 代码来源一致性

逐项比较服务器 `source_sha256.json` 与本次上传代码 ZIP：

- 70 项 SHA-256 完全一致，包含上传包中所有被报告覆盖的代码、脚本、测试与配置。
- 2 项不同：`AnonymousSubmission2027_Phase2.tex` 与 `aaai2027_Phase2.bib`。
- 服务器额外记录 5 项安装生成的 `python/rampd_phase1a.egg-info/*`，以及
  `docs/PHASE1A_ACCEPTANCE.md`；这些文件不在本次 ZIP 中。
- 服务器报告中的 tex 哈希 `b59c7ad825e51c6b1de99a30ed73f6b96420b2d67251f4af35a37ba1a60cfa42`
  与本次单独上传的 `AnonymousSubmission2027.tex` 完全相同。

因此，服务器执行的算法源代码与上传工程一致；论文理解以用户单独上传的
tex 为准。论文文件差异不应阻断代码的数值验证。

## 3. 缺陷、失败案例与修正

### 3.1 证据仅按字符串引用回放，无法验证当前义务

旧代码只执行 `evidence_verifier(transition.evidence_ref)`。即使外部验证器能
证明该引用对应的旧 tube 正确，也无法得知调用方当前的 source box、control、
posterior branches 是否仍与旧证据一致。

最小反例是：先为静止点支持和 `(jerk, steering_rate)=(0,0)` 准备一个合法
hold 证据引用；保留相同引用与自环后继，把当前 action 改成 `(1000,1000)`。
旧的 ref-only 接口仍会接受该 action。它没有验证新控制下物理运动还是自环。
若同时更新证书中的 claimed control，旧回放也无法识别证据被迁移。

这不否定原固定点算法对“输入抽象图”的递推正确性，但否定了“引用回放成功
就足以证明当前 transition”的接口假设。

**修正：** 引入 `EvidenceContext(cell, source_atom, action, transition)`，验证器
只接受上下文接口。`evidence_context_digest()` 绑定：

1. 当前完整 belief support、cell 与 policy node；
2. 当前 source atom 的全部连续盒与离散模式；
3. action ID、公共控制、公共反馈律 `controller_ref`；
4. 当前 transition 的全部 observation labels 和 successor supports。

证据引用和 verdict 不属于所证明的内容，因此不纳入摘要，以免产生自引用。
摘要只证明内容身份，不能代替 tube、安全约束或完整分支覆盖的数学验证。
Phase 3 的真实证据存储器仍须回放实际连续 tube，并将其与这个上下文逐项绑定。

验证器异常、旧 ref-only API、不正确的返回类型均 fail closed。明确标注的
Phase 2 有限图测试仍可使用 synthetic verifier，但不得被当作物理证明。

新候选证书写入 `rampd.info-invariant-candidate.v2`。旧 v1 常数控制证书仍可
用新上下文验证器回放；v1 不能携带非空 `controller_ref`，防止旧回放器忽略
反馈律而错误接受新证书。

### 3.2 移除 tex / bib 强依赖

问题来自 `scripts/validate_phase1d.sh` 最后生成 `source_sha256.json` 的循环，
该脚本被 `validate_phase2.sh` 调用。旧代码无条件读取两个论文文件，导致
即使所有数值测试已经通过，仅缺少论文副本也会使整条命令失败。

本轮保留 `CMakeLists.txt`、`pyproject.toml`、`PROGRESS.json` 的必需哈希，
仅在根目录存在 `.tex` / `.bib` 文件时附加其哈希。没有论文文件的源码包
可以完整运行验证命令。

### 3.3 验证入口的参数与路径

`validate_phase2.sh` 原先未转发调用者传入的 CMake 参数。本轮向 Phase 1D
入口转发 `"$@"`，并将 `BUILD_DIR` 与 `REPORT_DIR` 都标准化为绝对路径。
例如服务器使用自定义 MPFR prefix 时，可传递 `-DCMAKE_PREFIX_PATH=...`。

## 4. 新增回归目标

`tests/test_evidence_binding.py` 覆盖以下实际回归风险：

- 不变的证据引用不能移植到新的控制、反馈律或 action ID；
- 不能移植到改变后的源支持、同一 belief 中其他源支持或 policy history；
- 不能移植到改变后的 observation label 或 posterior box；
- 修改输入控制并同步修改 claimed result，仍须被可信上下文证据拒绝；
- 旧 ref-only API 与 truthy 非布尔返回值不能被静默接受；
- v1 常数控制兼容、v2 反馈律与禁止降级的语义保持明确。

### 4.1 本轮已执行结果

本轮用官方 MPFR 4.2.2 发布版头文件和系统 MPFR 4.2.2 运行库重新构建；
不是旧文档描述的 declaration-only bootstrap 头。

- 原 Phase 2 代码：129 项 Python 测试通过，0 失败。
- 上述接口修正后、合入后续 Phase 3 新模块之前：142 项 Python 测试通过，
  其中旧 belief/invariant 17 项与新增 evidence-binding 13 项全部通过。
- 旧实现的证据复用反例已在真实 MPFR 后端加载后复现：原 `(0,0)` 与篡改后的
  `(1000,1000)` 均被旧 ref-only 验证器保留并成功回放。新测试拒绝该复用。
- 创建没有任何根目录 `.tex` / `.bib` 文件的独立源码副本，以相对
  `BUILD_DIR=build_validation` 与 `REPORT_DIR=reports/no_paper` 调用
  `validate_phase2.sh`，并从该入口传入 `-DMPFR_INCLUDE_DIR=...` 和
  `-DMPFR_LIBRARY=...`。整条脚本退出码为 0，3 个 CTest 与 142 个 pytest
  全部通过，Phase 2 A/L 候选证书回放通过，自动生成验收 ZIP。

无论文副本回归缩短了计时重复次数，使用 100 个 footprint samples
（2,000 个 projections，0 misses）以及 50/100/250/500 cells 微基准；
它专门验证脚本依赖、参数转发和路径处理，没有缩减 Python 或 native 测试。
完整 Phase 3 测试总数及最终全量默认验收结果以 Phase 3 验收报告为准。

## 5. 现有验收不能支持的推论

现有 Phase 2 扩展性数据使用单 atom、单 action、单 observation 的自环 fixture，
全部只需 1 轮、不删除 cell。它没有测量困难的前驱删除链、多分支 observation
aggregation、多候选控制搜索，或真实连续 tube 的计算量。不能把约 0.029 s
表述成 2000 个真实驾驶 belief cells 的端到端规划耗时。

当前提供的服务器报告也不包含本轮重新运行的 sanitizer 证据，不能凭以前
本地文档中的说明声称此次服务器 sanitizer 已通过。

Phase 3 可继续使用明确标注的合成 benchmark 参数与原有 MPFR/Picard 底层，
本阶段无须启动 CARLA/SUMO 或读取 AV2/WOMD。物理校准和完整协议证据尚未
完成前，所有输出仍须保持阶段限定的 assurance scope。
