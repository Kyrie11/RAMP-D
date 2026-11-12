# Phase 5 开发计划：CEGAR 与可恢复细化

Phase 5 严格承接 Phase 4 的三值全支持接口。目标是把 `UNKNOWN` 中可以继续分析的抽象义务记录为责任位置，区分具体反例和抽象伪反例，细化抽象后重新验证；它不把任何外包围相交或 learned prediction 失败升级为真实反例。

## 本轮目标

1. 对同一任务、协议转移、公共动作和源支持执行独立 concrete replay；replay 成功才返回 `CONCRETE`，replay 拒绝返回 `SPURIOUS`，缺失或异常返回 `UNKNOWN`。
2. 将非点事件时间窗口按精确有理中点拆成两个闭子窗。两个子窗共享边界，因此不会丢失边界事件；不能把子窗下界当作实际事件时间。对收到消息的分支，公共决策时钟由 receipt/local 决定；selector 必须根据未决义务中的 clock 名称细化对应时钟，不能把 change 区间冒充 receipt。
3. 对连续 support atom 按指定坐标细化。细化后清空旧 action/evidence，并保持同一 `policy_node_id`，因细化本身不创造观测。
4. 对 observation cell 只有在显式证明可观测区间不相交时才允许创建不同 policy node；没有该证明时保留同一节点并只细化 support。
5. 用版本绑定的 evidence registry、master problem 和队列调度骨架记录契约变更、责任轴、细化代数和重新验证结果。
6. 保持 `CERTIFIED / COUNTEREXAMPLE / UNKNOWN` 语义和 `full_support_certified=false` 边界。

## 细化与可证性边界

`TimeWindow` 使用闭区间。支持坐标使用工程已有的 binary64 interval midpoint；因此文档不把 support split 称作精确有理算术。事件时间 split 是有理时间，连续 branch 仍需 whole-window evidence 或进一步处理，不能靠无限二分把一个真正连续区间变成点。

Phase 5 的 `ResumableVerificationQueue` 保存契约 digest、generation、待处理任务、in-flight 任务和已确认任务。它是版本绑定的重验证调度骨架：当前 `CegarEngine` 每次 refinement 后从新的 contract root 重建 Phase 4 verifier。它不会伪装成把 `FullSupportVerifier` 内部队列节点序列化成了完整检查点。

任何 protocol、resource、observation、model 或 support contract digest 变化都会使旧 evidence 失效。资源 digest 由调用方显式传给 Phase 5 版本对象；没有 resource digest 时，调用方不能声称资源语义未变。

## 不在本轮范围内

WOMD、Argoverse 2、MTR/QCNet/QCNeXt、CARLA 0.9.16、SUMO 1.20、真实消息日志和闭环实验全部留在 Phase 6。Phase 5 仍只使用合成显式协议和已有动力学/资源合同。
