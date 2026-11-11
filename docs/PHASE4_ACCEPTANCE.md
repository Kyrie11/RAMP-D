# Phase 4 验收报告

## 验收顺序

本轮按以下顺序完成：

1. 明确协议、资源、他车、观测和终端支持的完整义务；
2. 实现显式合同与 fail-closed 三值验证器；
3. 执行 native、全量 Python、专项失败案例和示例测试；
4. 对失败输入逐项分析，确认返回 UNKNOWN 的原因；
5. 形成本报告和机器可读的 `phase4_acceptance_summary.json`。

## 最后一次本地结果

```text
CTest native: 3 passed
all Python tests: 318 passed
Phase 4 + forecast tests: 23 passed
failures: 0
errors: 0
skipped: 0
```

入口：

```bash
PATH=/workspace/scratch/a5e017d913a8/.deps/bin:$PATH \
PYTHONPATH=/workspace/scratch/a5e017d913a8/.deps:$PWD/python \
RAMPD_INTERVAL_LIB=$PWD/build_phase3/librampd_interval.so \
PYTHON_BIN=python REPORT_DIR=$PWD/reports/local_phase4_final \
bash scripts/validate_phase4.sh
```

`validate_phase4.sh` 会运行全部 Phase 0–3 回归和 Phase 4 专项，不要求 `.tex` / `.bib`，也不要求 WOMD、AV2、CARLA 或 SUMO。

## 通过项

- `ClockTrace` 保持 change、issue、receipt、local 四个独立窗口；消息包含版本、内容摘要和半开有效区间。
- 协议自动机 coverage 缺口、未证明 guard、未证明 clock order 都不能进入 `CERTIFIED`。
- silence 分支保留；没有显式 publication/delivery deadline 时，不得删除隐藏 mode。
- 完整 swept footprint 的严格 AABB 分离才返回 `PROVED_FREE`；边界接触和 overlap 保留为可能占用。
- 资源状态检查 `alpha/beta/direction/capacity`，容量单位不一致、冲突资源可能同时占用、already-inside 与几何不一致均返回 `UNKNOWN`。
- OtherAgentModel 的 ego response gain、扰动、dynamics、Picard options 和 digest 进入模型合同；未提供模型 digest 时固定返回 `UNKNOWN`。
- 相同 observation 的所有后验先聚合，再检查一个目标 cell；目标 cell 的 `policy_node_id` 必须匹配后继协议状态。
- 非点事件时间不压到下界；当前首版把它作为 Phase 5 refinement obligation。
- branch/terminal `COUNTEREXAMPLE` 只有独立 replay 验证后才保留；否则降级 `UNKNOWN`。
- MTR proposal adapter 保留所有模式和 provenance；NMS/top-k 只标记完整性，不改变安全结论；有限 scale 不转换为 hard support。

## 合成三值示例

| 示例 | 结果 | 关键证据 |
|---|---|---|
| certified | `CERTIFIED` | `always` guard、点事件、资源 SAFE、4 段 validated tube、终端支持和上下文 digest |
| counterexample | `COUNTEREXAMPLE` | branch witness 与独立 replay callback 均通过 |
| unknown | `UNKNOWN` | guard 未证明 |

`full_support_certified=false` 和 `current_scene_verified=false` 在脚本摘要中保持不变。当前 `CERTIFIED` 只针对有限合成合同，不能解释为真实交通安全证书。

## 失败案例

| 输入 | 返回 | 原因 |
|---|---|---|
| silence 后继删掉隐藏 mode | `UNKNOWN` | `SILENCE_REMOVES_HIDDEN_HISTORY_WITHOUT_PROOF` |
| `[1,2]` 事件时间窗口 | `UNKNOWN` | `EVENT_TIME_INTERVAL_REQUIRES_REFINEMENT` |
| `guard_tag=unknown` | `UNKNOWN` | `GUARD_NOT_PROVED` |
| AABB overlap + 错误方向/关闭 entry | `UNKNOWN` | 可能占用不能升级为具体违规 |
| actor 声明已在资源内但 footprint 分离 | `UNKNOWN` | `DECLARED_INSIDE_GEOMETRY_INCONSISTENT` |
| 反例无独立 replay | `UNKNOWN` | `COUNTEREXAMPLE_REPLAY_MISSING` |
| learned Gaussian/Laplace proposal | `UNKNOWN` | unbounded/uncalibrated residual tail |

这些结果是预期的安全保守行为，不能通过放宽测试断言来消除。

## 不能宣称的内容

本轮没有接入真实协议日志、WOMD Scenario、Argoverse 2 Motion Forecasting、MTR++/QCNet/QCNeXt inference、CARLA 0.9.16 或 SUMO 1.20。因此不能宣称真实场景的全支持安全、真实车辆参数校准、消息观测关系完整、或学习模型已经提供硬安全包络。

## 下一阶段

Phase 5 继续实现 concrete/spurious counterexample 分流、时间和连续 cell refinement、master problem 更新、证据失效管理和可恢复队列。真实数据与仿真接入仍按 Phase 6 计划执行。
