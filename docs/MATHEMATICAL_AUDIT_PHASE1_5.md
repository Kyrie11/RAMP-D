# Phase 1–5 数学一致性复核（进行中）

日期：2026-11-16。本文是逐模块复核记录，不代表 Phase 1–5 已完成最终审计。依据是当前 `AnonymousSubmission2027(1).tex`，而不是旧版论文摘要。

## 已核实的核心公式/实现对应

### Phase 1：连续动力学与 validated reachable tube

- 论文自行车模型状态顺序为 `(p_x,p_y,psi,v,a,delta)`，控制为 `(j,omega_delta)`。当前 Python/C++ RHS 对应
  \[
  \dot p_x=v\cos\psi,\;\dot p_y=v\sin\psi,\;
  \dot\psi=v\tan\delta/L_w,\;\dot v=a,\;\dot a=j,\;\dot\delta=\omega_\delta.
  \]
- 轮胎摩擦椭圆使用纵向加速度 `a`，不是 jerk `j`；当前 `friction_value_enclosure` 使用 `a/(mu*g)` 和 `v^2 tan(delta)/(L_w mu*g)`，与论文一致。
- C++ Picard step 的核心包含 `X + [0,h]F(Z,U,W) ⊂ int(Z)`，并用 `X+hF(Z,U,W)` 外包端点；这是对论文 Picard inclusion 的保守实现。它允许区间输入/扰动在步内变化，因此对常值/可测输入的集合包含是保守的。
- footprint 的区间投影和固定分离轴只有在投影间隙严格为正时才返回 separated；无法证明时返回 UNKNOWN，不将“未证明碰撞”误报为安全。

**仍待核查：** MPFR 原生 ABI 在用户服务器上的完整重放、C++ trig/rounding 边界、state/control/disturbance bounds 与论文物理域的逐项映射，以及每个 backup tube 的全步 friction/geometry coverage。

### Phase 2–3：信息不变集与公共 backup

- `compute_information_invariant` 是有限 belief-cell 抽象上的 greatest-fixed-point pruning：只保留每个 observation class 都有后继覆盖到当前候选集的 cells。它使用同一个 action witness 并按 observation 聚合 successor support，符合非预见性要求。
- `support_subset_cell` 要求每个后继 atom 的连续状态盒被目标 cell 的某个 atom 包含，并且离散 mode 一致；这是有限抽象下的充分包含检查，不是连续支持空间的精确枚举。
- `SampledFeedbackLaw` 实现 `sat(bias + K(xhat-xbar))` 的区间像，measurement error 被纳入区间；backup 候选的成功状态仍标记为 `SYNTHESIZED_LOCAL`，没有冒充全局/完整 synthesis。

**已发现的实现覆盖缺口：** 当前代码有 `S_infinity` 有限 cell 固定点和有限候选 backup synthesis，但尚未看到与最新论文完全对应的有限时域 `W_H^{SC}` 递推、rank `d_H`、`V_H^{SC}` 的完整动态规划实现，也未看到论文中 CCG 三层 product/refinement 的完整可运行实现。现有 Phase 2/3 代码不能被描述为已经复现这些最新新增算法段落；后续需要补齐并增加独立测试。

### Phase 4–5：协议时钟、观测和 CEGAR

- **已修正的关键时间语义：** `change` 是物理生效时钟，不是 public observation。若 `change < t_current < receipt`，该隐藏规则变化必须仍在 support 中。后继过滤现在基于已证明的 public-observation time，而不是 `change`。
- message-receipt 和 local-detection 是独立观察通道：message branch 在 receipt 可用；local branch 在 local clock 可用；不强制 `receipt→local`。论文明确允许报告乱序到达，故先前的 max(receipt,local) 是未声明的额外假设，已移除。
- `ProtocolTransition` 现在允许无 message 的正向 local-detection branch（要求 local clock），不再把所有非-silence branch 强制解释为 message receipt。
- silence 本身不排除隐藏事件；缺少 local observation 或 publication+delivery deadline proof 时保持 UNKNOWN。

**仍待核查/补强：** `silence_exclusion_proved` 当前是布尔标记，尚需核对是否绑定可重放的 publication deadline、delivery deadline、expected-message identity 和 protocol digest；否则仅靠调用方布尔值不足以形成独立可审计的证明。`guard_tag="false"` 的禁用边与 coverage ledger 的关系也需要更明确的 schema/状态语义。

## 最高优先级后续审计项

1. 补齐论文新增的有限时域 SC 递推、rank 和值函数，并确认 reserve 的量纲/截断/terminal value 与公式完全一致。
2. 对 `silence_exclusion_proved` 建立可重放 deadline evidence，而非裸 bool。
3. 完整审计 `FullSupportVerifier` 的 support completeness、observation aggregation、resource state、terminal invariant 和 branch coverage 是否与 `Omega_cert` 定义一致。
4. 逐项审计 CCG coarse/refine 的 must/may graph、候选条件预测不得缩小 verifier outer envelope 的约束。
5. 在 MPFR 官方 ABI 环境重跑所有 Phase 1–5 native tests 和 CTest；当前本地没有 MPFR headers，不能声称完成此 gate。

## 当前状态

Phase 1 的 ODE/Picard/friction 公式对应关系已做静态复核；Phase 4 的 change-vs-public-time 错误已修复并新增回归测试。Phase 2–3 的有限时域值函数/CCG 覆盖缺口、Phase 4 silence deadline evidence、完整 native replay 仍未完成审计。任何阶段均未获得 `full_support_certified=true`。
