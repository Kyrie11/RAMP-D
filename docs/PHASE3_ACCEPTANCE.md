# Phase 3 验收记录与服务器验收要求

## 1. 状态与范围

Phase 3（0.6.0）已完成公共采样反馈律、局部连续时间证据、闭合 backup graph
和执行接口的实现，并进行本地验证。最终测试总数及机器环境由本轮生成的
`acceptance_summary.json`、`pytest.xml` 与 `environment.json` 给出，本文件不
用硬编码总数代替实际测试发现。

**用户目标服务器的 Phase 3 复核仍待新的服务器报告。** 已上传的旧报告仅
验收 Phase 2；本轮本地运行结果不能自动升级成用户服务器验收通过。

保证范围为 `LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS`。
`full_support_certified`、`concrete_safety_certified` 和
`current_scene_verified` 都必须为 `false`。这三个字段不是失败标记，而是
当前阶段的准确边界：Phase 4 的完整协议、资源、移动他车及真实观测关系
尚未接入。

## 2. 本轮实现目标

| 目标 | 实现与验收依据 |
|---|---|
| 公共控制参数与反馈增益 | `SampledFeedbackLaw` 的 bias、2×6 gain、reference、显式饱和；不接受隐藏 mode 作为控制输入 |
| 四类恢复模板 | `recovery_candidates` 生成候选，`synthesize_backup` 对每个完整 belief 的全部源 atom 检查 |
| 连续时间局部安全证据 | Picard inclusion witness 回放、解析外包求交、状态/摩擦/footprint/道路/gate/静态障碍检查 |
| 不提前利用观测 | 同一个 observation label 的全部源后继合并后，必须由一个 target belief 覆盖 |
| 证据内容绑定 | `EvidenceContext`、law/contract 摘要和实际 tube 回放；更改当前义务不能复用旧引用 |
| 公共 backup graph | Phase 2 固定点产生闭合 retained graph；移除节点后不能留下指向已删除节点的边 |
| 控制执行与更新 | 精确决策时间、实际测量计算命令、观测后才更新节点、支持包含与运行时证据检查 |
| 回归兼容 | Phase 1A–2 测试和基准继续执行，原生 ABI 保持 3，tex/bib 变成可选来源记录 |

搜索是在给定有限参数库中比较候选，不宣称连续参数空间的全局最优。
空间余量下界用于排序，不替代完整协议/资源鲁棒裕量。时间预算为非抢占式
离线软预算，不能解释为实时控制截止时间保证。

## 3. 已观察到的本地演示

本节依据 `reports/local_phase3_full/phase3_demo.json` 的本地结果。

### 3.1 17 节点制动/驻停闭图

| 项目 | 结果 |
|---|---|
| 演示状态 | `PHASE3_LOCAL_DEMO_PASS` |
| retained nodes | 17 |
| 每个节点隐藏模式 | `rule=open`、`rule=closed` 两种，保持在同一个 belief 中 |
| 观测 label | `silence` |
| 图独立回放 | 通过 |
| 源速度、加速度 | 4 m/s、0 m/s² |
| 控制轮廓 | 前 2 s jerk −1，后 2 s jerk +1；随后终端 hold |
| 决策周期 | 0.25 s |
| 达到精确停止 | 第 16 步，4 s，位移 8 m，`v=a=0` |
| 执行审计 | 20 步，共 5 s；包含停止后的 4 步、1 s hold |
| 连续演化交叉检查 | 独立 exact-rational 直线动力学计算并核对每次 posterior |

该闭图采用**零过程扰动**的合成模型，保留位置区间和配置的测量误差。
终端非零反馈增益只作用于静止支持上精确为零的速度、加速度、航向与转角
偏差。它证明该声明模型中的闭合续接，不能推广成任意非零过程扰动下的
无限时间驻停。

### 3.2 四类非零扰动局部模板

四个问题均包含非零导数扰动和非零测量误差，检查一次决策区间的完整连续
tube，并要求后继进入给定的局部目标支持。

| 模板 | 本地状态 | 可接受候选 | 选中反馈增益是否非零 | 实际覆盖目标 |
|---|---|---:|---|---|
| brake-to-stop | `SYNTHESIZED_LOCAL` | 2 | 是 | 单步受约束减速 |
| hold-before-gate | `SYNTHESIZED_LOCAL` | 2 | 否 | 单步近零运动、保持 gate 前的局部支持 |
| yield | `SYNTHESIZED_LOCAL` | 1 | 是 | 单步减速并进入较低速度目标支持 |
| clear/merge | `SYNTHESIZED_LOCAL` | 1 | 是 | 单步受约束横向推进 |

这里不要求每个最优候选都具有非零 K：候选库包含零增益，当其验证余量及
排序规则更优时可以选中。非零 K 的区间传播、噪声处理与执行另有专项回归。
clear/merge 行不意味着已经完成整个车道合流，也不意味着取得道路资源或
通行协议许可。

### 3.3 预期拒绝案例

演示中的四个反例全部被保守拒绝：

| 案例 | 结果与原因 |
|---|---|
| gate 落在扫掠车身内部 | `UNKNOWN`，`SPATIAL_CLEARANCE_NOT_PROVED` |
| 静态走廊被堵塞 | `UNKNOWN`，`STATIC_OBSTACLE_SEPARATION_UNKNOWN:blocked` |
| 场景摩擦过低 | `UNKNOWN`，摩擦可行性未能证明 |
| 把受扰精确静止点强行当作自环 | `UNKNOWN_NO_VALIDATED_CANDIDATE`，后继不能被同一个静止点 target 覆盖 |

上述 UNKNOWN 是预期结果。外包络重叠或候选未验证不等于已经获得具体
物理反例；本轮不把它们误写成 Phase 4 的 `COUNTEREXAMPLE`。

## 4. 回归与独立复核要求

一键脚本必须发现并通过原生 CTest，以及所有 Python 测试，不能有失败、
错误或跳过。Phase 3 必需测试模块包括：

- `test_public_control`：公共参数化、控制饱和、测量误差和执行命令区间。
- `test_analytic_bounds`：有向解析外包、二次速度极值、输入合法性和边界情况。
- `test_evidence_binding`：当前支持、控制、反馈律与观测后继的证据绑定。
- `test_backup_synthesis`：真实 tube 检查、完整源/观测支持、空间约束及预算。
- `test_backup_graph`：闭图、独立回放、执行时序、观测后更新与篡改拒绝。

保留 Phase 1B 动力学见证回放、Phase 1C adaptive-width 回归、Phase 1D
footprint/separation 回放与抽样反证审计、Phase 2 固定点和候选证书回放。
样本零漏包只能作为反证审计记录，不能代替数值包含证明。

已单独执行无 tex/bib 源码副本的 Phase 2 入口回归，验证论文文件缺失不再
阻断数值验收，也验证相对路径和 CMake 参数转发生效；详见
[Phase 2 审计](PHASE2_AUDIT_AND_FIXES.md)。

## 5. 环境边界

本轮本地使用 Python 3.12、GCC 14.2、官方 MPFR 4.2.2 发布版头文件和
MPFR 4.2.2 运行库。它不是早期文档中的 declaration-only bootstrap 测试。

用户目标环境仍为 Conda `mfrp`、Python 3.10.20、GCC 9.4.0、CMake/CTest
3.18.0、MPFR 4.0.2。**无需为本轮升级这些组件。** 正式源码继续要求官方
MPFR/GMP 开发文件，没有浮点替代或 Boost fallback。所有版本及实际链接库
由 `environment.json` 记录。

## 6. 目标服务器操作

把新压缩包放到 `/home/senzeyu2/code`，在新目录解压，保留原 `RAMP-D/`：

```bash
cd /home/senzeyu2/code
conda activate mfrp
unzip RAMP-D_Phase3.zip
cd /home/senzeyu2/code/RAMP-D_Phase3
python -m pip install -r requirements-test.txt
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase3.sh
```

原生代码编译到本轮 `build_phase3/`。请勿手工指定旧 Phase 1A/1B/1C 的共享库。
无需 `.tex`、`.bib`、AV2/WOMD、GPU、CARLA 或 SUMO 进程。

运行后上传：

```text
/home/senzeyu2/code/RAMP-D_Phase3/reports/RAMP-D_Phase3_server_report.zip
```

成功报告应包括下列文件；脚本失败时会尽力保留 `phase3_failure.json` 和日志，
同样应上传生成的 ZIP：

| 文件 | 用途 |
|---|---|
| `acceptance_summary.json` | 本次机器的阶段、测试和验收门槛结果 |
| `phase2_acceptance_summary.json` | 被保留的前置回归结果 |
| `environment.json`、`source_sha256.json` | 实际编译运行环境和来源身份 |
| `pytest.xml`、`pytest.log`、`ctest.log` | 实际测试发现与失败详情 |
| `phase3_demo.json` | 四模板、闭图和预期拒绝结果 |
| `phase3_backup_graph.json` | 可独立回放的公共策略图及其局部证据 |
| `phase3_trace.json` | exact-rational 执行审计 |
| `phase3_benchmark.json` | 有限模板离线综合微基准 |
| `phase3_replay.json` | 图及固定点的独立回放结果 |
| `phase3_validation.log` | 全程阶段日志 |

`target_server_acceptance=PENDING_EXTERNAL_REVIEW` 是脚本生成的复核状态。
待用户上传报告并检查其环境、哈希和失败案例后，才能记录目标服务器的正式
Phase 3 验收。图回放即使固定了调用方 contract digest，也不能证明该物理
契约在当前真实道路上成立。

## 7. 后续阶段

通过本轮服务器复核后进入 Phase 4：协议自动机、资源监视器、移动 agent
连续 tube、真实 observation relation、完整 posterior 覆盖、连续碰撞和
终端不变成员检查。随后 Phase 5 接 CEGAR，Phase 6 接 AV2/WOMD 与无头
SUMO/CARLA 闭环实验。此顺序与原设计记录保持一致。
