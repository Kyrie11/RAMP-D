# Phase 4 工程报告

日期：2026-11-11（UTC）；工程版本：0.7.0。

本轮继续遵守“明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告”的顺序。目标是把 Phase 3 的局部公共恢复策略接到一个语义严格的、可穷举离散分支的全支持验证器上：协议事件和消息时钟、动态资源、完整车身外包围、声明式他车响应管、观测关系和终端支持成员关系必须同时进入同一份验证合同。

## 1. 本轮明确目标

Phase 4 首版必须完成以下义务：

1. 用显式的 `change / issue / receipt / local` 四个时钟表示物理变化、消息发布、消息到达和本地首次可用观测；消息版本、内容摘要和半开 effective interval 进入 digest。
2. 枚举协议自动机允许的全部有限分支。只有显式证明的 guard 和时钟顺序才允许通过；silence 是观测分支，缺少 publication/delivery deadline 不能删除隐藏事件历史。
3. 用完整 swept footprint 做资源占用、entry/stay/exit、direction、capacity 和跨资源冲突检查。严格 AABB 分离才可证明 free；接触或重叠只说明可能占用。
4. 用声明的 bicycle dynamics、控制界、导数扰动和 ego-response gain 生成他车 MPFR/Picard reachable tube，并把模型 digest 绑定到验证合同。
5. 对相同 observation 的所有后验先合并，再要求整个后验落入一个匹配协议上下文的 target cell；不能用多个目标 cell 的并集拼接覆盖。
6. 输出 `CERTIFIED / COUNTEREXAMPLE / UNKNOWN`。`COUNTEREXAMPLE` 必须由同一 task、transition、public action 和 support 上的独立 replay callback 验证；所有外包围失配、非点事件时间、缺失连续证据和预算耗尽均返回 `UNKNOWN`。

本轮不训练或接入预测器，不把 MTR++、QCNet、QCNeXt 的概率密度和有限标准差/scale 带当作 hard support，也不接入 WOMD、AV2、CARLA 或 SUMO。

## 2. 代码实现

| 文件 | 实现内容 |
|---|---|
| `python/rampd_core/protocol.py` | `TimeWindow`、四时钟 `ClockTrace`、`MessageSpec`、`ProtocolState/Transition`、coverage ledger、协议 digest 和 silence 语义。 |
| `python/rampd_core/resources.py` | `ResourceRegion/State`、完整 `SweptFootprint` 的保守占用、容量单位、方向和 entry/stay 监视、跨资源冲突。声明的 already-inside 与几何外包围不一致时固定返回 UNKNOWN。 |
| `python/rampd_core/agents.py` | `OtherAgentModel` 的 bounded response envelope、ego 控制像、MPFR/Picard tube、模型 digest 和证据输入检查。 |
| `python/rampd_core/observations.py` | 观测分支按标签聚合，重复 atom 内容冲突则 UNKNOWN，单一 target cell 覆盖检查。 |
| `python/rampd_core/full_verifier.py` | 有预算的有限支持队列、协议覆盖、终端 checker、事件时间细化门、silence 隐藏模式保留、独立反例回放和 contract digest。 |
| `python/rampd_core/forecast.py` | MTR 7-vector proposal provenance adapter；保留所有模式、scale、rho、速度、valid mask、frame 和 NMS 状态，但禁止从 learned density 推导 hard support。 |
| `python/rampd_core/phase4_examples.py` | 可复现合成 `CERTIFIED`、独立回放 `COUNTEREXAMPLE`、guard 未证明 `UNKNOWN` 以及资源/他车探针。 |

验收入口为 `scripts/validate_phase4.sh`。它先确保 Phase 3 native library 存在，然后运行 CTest、全部 Python 回归、Phase 4 专项测试和三值示例；脚本和测试均不依赖 `.tex` / `.bib`。

## 3. 测试结果

最后一次本地运行：

```text
native CTest: 3 passed
all Python tests: 318 passed
Phase 4 + forecast tests: 23 passed
failures/errors/skips: 0 / 0 / 0
```

执行命令：

```bash
PATH=/workspace/scratch/a5e017d913a8/.deps/bin:$PATH \
PYTHONPATH=/workspace/scratch/a5e017d913a8/.deps:$PWD/python \
RAMPD_INTERVAL_LIB=$PWD/build_phase3/librampd_interval.so \
PYTHON_BIN=python REPORT_DIR=$PWD/reports/local_phase4_final \
bash scripts/validate_phase4.sh
```

实际工程路径应替换为解压后的工程根目录；上面的 `PYTHONPATH` 中 `/workspace/scratch/RAMP-D_Phase3/python` 只是示意，脚本自身会优先加入当前根目录的 `python`。

三值合成示例结果为：

| fixture | 结果 | 含义 |
|---|---|---|
| certified | `CERTIFIED` | 有显式 `always` guard、有限点事件时间、资源 SAFE、他车 tube VALIDATED、终端 checker 和目标上下文。 |
| counterexample | `COUNTEREXAMPLE` | branch checker 提供 witness，独立 replay callback 返回 true。 |
| unknown | `UNKNOWN` | guard 为 `unknown`，没有把未知协议条件当作安全证据。 |

资源探针返回 `SAFE`。声明的他车模型返回 `MODEL_DECLARED`，实际调用 MPFR/Picard 0.125 s tube，得到 4 个 validated segments。该探针是接口和数值回放测试，不是现实交通安全实验。

## 4. 失败案例与修正

- **silence 错误删除隐藏模式**：故意让 silence 后继只保留一个 mode；验证器检测到源 mode 集合没有包含于后继集合，返回 `UNKNOWN`。
- **非点事件时间被压到下界**：故意使用 `[1,2]` 的 change window 并伪造反例；验证器在 branch checker 之前返回 `EVENT_TIME_INTERVAL_REQUIRES_REFINEMENT`，不会在 1 s 下制造反例。
- **未证明 guard**：`guard_tag=unknown` 保留为协议分支，但结果为 `UNKNOWN`。
- **可能资源占用被冒充具体违规**：AABB overlap、错误方向、关闭 entry/stay 和 capacity 超限均只产生 unresolved obligation；没有把可能占用升级为 `VIOLATION`。
- **already-inside 与 footprint 不一致**：声明 actor 已在资源内但 swept AABB 分离时，结果为 `UNKNOWN`，避免把不一致证据错误解释成 `PROVED_FREE`。
- **没有独立反例 replay**：branch checker 返回 `COUNTEREXAMPLE` 但没有 replay callback 时，结果降级为 `UNKNOWN`。
- **学习预测尾部**：MTR/QCNet/QCNeXt 的 density/scale、top-k 和 NMS 只进入 proposal metadata；`hard_support_from_prediction` 固定返回 `UNKNOWN_UNBOUNDED_TAIL`。

这些失败不是测试缺陷，而是 fail-closed 语义的预期结果：外包围不足以证明具体违规，缺少完整协议/连续证据不足以证明安全。

## 5. Phase 3 复核结论

上传的 Phase 3 服务器报告与工程哈希一致，目标环境为 Python 3.10.20、GCC 9.4、CMake 3.18、MPFR 4.0.2；3 项 native 和 295 项 Python 全部通过。Phase 3 的 MPFR directed interval、Picard inclusion replay、速度二次极值、signed-speed stop、完整 footprint projection、evidence binding 和 graph replay 未发现确定数学安全错误。

在 Phase 4 之前同步修正了论文中的四处严谨性问题：使用 duration interval `D_mu` 的 Pontryagin scheduling screen；将终端支持写为同一 public context 下的 downward closure；backup synthesis 要求每个非空 posterior 由一个目标 cell 单独覆盖；外包围 terminal miss 只有经过具体动力学/协议 replay 才能返回 `COUNTEREXAMPLE`，否则只能 `UNKNOWN`。论文还把当前实现准确称为 validated directed-interval Picard，zonotope 仅作为未来可替换后端。

## 6. 保证边界

当前工程结果的 scope 是：

```text
PHASE4_EXPLICIT_PROTOCOL_SUPPORT
full_support_certified = false
current_scene_verified = false
```

`CERTIFIED` 只表示给定的有限合成协议、显式支持、模型和观察合同以及已提供的 branch/terminal checker 已清空验证队列。它不证明真实 WOMD/AV2 场景、真实通信延迟、动态地图状态、未知交通参与者或真实车辆的安全。Phase 3 的 `LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS` 也仍保留为历史局部范围。

## 7. 下一阶段

Phase 5 实现 concrete/spurious counterexample 分流、事件时间和连续 cell refinement、master problem 更新、旧证据失效和可恢复验证队列。WOMD Scenario、Argoverse 2 Motion Forecasting、MTR/QCNet/QCNeXt inference 以及 CARLA 0.9.16/SUMO 1.20 闭环在 Phase 6 处理；接入真实数据前需要用户在服务器准备数据路径，并先把消息发布/到达/本地观测时间作为独立字段记录。
