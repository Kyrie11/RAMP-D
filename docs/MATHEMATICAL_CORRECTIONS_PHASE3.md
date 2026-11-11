# Phase 3 数学审阅与修正说明

## 1. 审阅基准与结论

本次以用户**单独上传**的 `AnonymousSubmission2027.tex` 全文为论文基准，原始文件 SHA-256 为 `b59c7ad825e51c6b1de99a30ed73f6b96420b2d67251f4af35a37ba1a60cfa42`。修订稿是工程根目录的 `AnonymousSubmission2027_Phase3.tex`。没有修改上传原件，也没有把代码包内较早的 Phase 2 tex 当作新稿。

研究路线保持为：公共观测历史 → 联合信念支持 → 公共恢复策略 → 经外包围验证的连续物理约束 → 观测后的后验路由 → 终端支持。Phase 3 补公共控制器与执行接口；协议完整分支、资源监视器与完整支持集认证仍属 Phase 4。

已阅读 Python interval/model/reachability/footprint/belief/invariant/certificate/refinement 及 C++ MPFR/Picard 内核。针对所审阅实现，未发现 MPFR 定向舍入、Picard 严格包含、支撑投影分离或 Phase 2 同步固定点剔除中的确定数学错误。这是代码和论证审阅的结论，不是实现无误的形式化证明。必须继续保持 `VALIDATED`、`SEPARATED`、有限抽象固定点、全系统 `CERTIFIED` 四种证明范围的区分。

## 2. 终端不变集应包含单个保留支持的子集

### 原问题

原稿写

\[
\mathcal S_\infty=\{\gamma(B):B\in\mathcal S_{\rm in}\}.
\]

这个集合只包含与保留单元**完全相等**的支持；实现和其余论证却使用“真实后验被一个保留单元包含”。例如已验证的支持是区间 `[0,1]`，实际后验缩小为 `[0.2,0.3]`。同一控制策略在更大支持上适用，自然也适用于其非空子集，但后者不属于上面的字面集合。

### 修正

在同一个已验证公共上下文内，定义向下闭包：

\[
\mathcal S_\infty=
\{\mathcal B\ne\varnothing:\exists B\in\mathcal S_{\rm in},\;
\mathcal B\subseteq\gamma(B)\}.
\]

公共上下文包括证据依赖的时间、协议时钟或相位、已观测信息以及模型适用条件。不能把某一绝对时间生效的入口许可无条件挪到另一时刻。时间依赖必须进入验证过的增广状态或明确的证据上下文。

若两个初始支持满足 `B_actual ⊆ B_cover`，对同一公共控制律和同一观测 `Y`，采用完整的同一转移关系时有 `Post(B_actual, κ, Y) ⊆ Post(B_cover, κ, Y)`；因此一个包含单元的公共控制和观测子节点能保护更小的真实支持。这个推理要求控制器与转移上下文一致。

代码中的 `support_subset_cell` 已采用“一个目标信息单元内的支持包含”语义。本次修正使论文集合定义与其一致。

## 3. 后验支持必须整体落入一个目标信息单元

### 原问题

原稿 `eq:backup-synthesis` 的最后约束为

\[
\operatorname{Post}_{\mathcal P}(B,\kappa_B,Y)
\subseteq\bigcup_{B'\in\mathcal S}B'.
\]

它允许一个不可区分的后验支持被多个各有独立控制的目标单元拼起来覆盖。反例：后验为 `{θ_L, θ_R}`；`B_L={θ_L}` 只允许左转，`B_R={θ_R}` 只允许右转；没有新观测区分两者。后验属于两个物理支持的并集，却不存在可执行的公共下一步控制。

### 修正

对每一个非空后验观测分支，要求

\[
\forall Y,\quad\exists B_Y\in\mathcal S:\quad
\operatorname{Post}_{\mathcal P}(B,\kappa_B,Y)
\subseteq\gamma(B_Y),
\]

且 `B_Y` 的公共上下文兼容。量词是“每个观测一个完整目标支持”，不是“每个隐藏状态一个目标”。不同观测可以选不同子节点；同一观测下所有来源 atom 必须先合并后验再做包含测试。

Phase 2 的 `_evaluate_action` 已按观测聚合所有来源 atom，并要求一个完整目标 `BeliefCell` 覆盖，因而主要问题在论文残留公式。论文离线算法的文字条件同步改成“each observation posterior is covered by one compatible cell”。

`support_subset_cell` 另外要求每个后验连续盒包含于目标的一个 atom 盒；仅由多个部分目标盒的并覆盖时不接受。这会保守地拒绝部分可行支持，但不会因此错误接受。

## 4. 外包围终端失配不是具体反例

### 原问题

原稿 `alg:full-verifier` 看到终端后验未被包含就直接返回 `COUNTEREXAMPLE`。设真实后验为 `{0}`，验证外包围为 `[-1,1]`，目标为 `[-0.5,0.5]`。外包围不包含于目标，真实后验却已在目标中。把前者称为真实失败混淆了集合过近似与可实现轨迹。

### 修正

必须区分：

- 外包围被一个兼容终端单元包含：终端条件通过。
- 没能证明包含：细化外包围，或标记 unresolved，预算结束返回 `UNKNOWN`。
- 通过原动力学、协议及真实观测历史验证了一个具体信息状态的终端条件失配：才可返回 `COUNTEREXAMPLE`。

“终端条件失配”也不自动等于发生碰撞；它表示当前候选没有满足所承诺的终端支持条件。信息状态反例应证明有关观测后验的失配，不能仅挑一个隐藏标签绕过非预见性要求。

## 5. 不确定占用时长下的 exit 窗口

### 原问题

原稿把 `T_μ` 定义成占用时长上界，却只检查 `t+T_μ ∈ I_out`。若真实退出早于上界，不能由上界时刻的许可推出真实退出时刻的许可。例如真实时长 2 s，上界 3 s，出口仅在 `[2.9,3.1]` s 受保护；原 exit 检查通过，但真实 2 s 退出不受保护。反向例子也说明这种筛选失败不证明所有其他较短动作不可行。

### 修正

令候选动作真实占用时长由

\[
\mathcal D_\mu=[T_\mu^{\min},T_\mu^{\max}]
\]

保守包络，使用

\[
\begin{aligned}
I_{r,\mu}^{\rm start}
={}&I_{r,\rm reach}^{\omega,\mu}\cap I_{r,\rm in}^{\omega}\\
&\cap\bigl(I_{r,\rm occ}^{\omega}\ominus[0,T_\mu^{\max}]\bigr)\\
&\cap\bigl(I_{r,\rm gap}^{\omega,\mu}\ominus[0,T_\mu^{\max}]\bigr)\\
&\cap\bigl(I_{r,\rm out}^{\omega}\ominus\mathcal D_\mu\bigr).
\end{aligned}
\]

这里 `A ⊖ D = {t : t+D ⊆ A}`。实际占用期被 `[0,Tmax]` 覆盖，可能的退出时刻全部被 `t+Dμ` 覆盖。固定时长是 `Dμ={Tμ}` 的退化情况。

这被明确称为**保守调度筛选**。筛选通过仍需要完整连续轨迹和资源检查；筛选失败只针对当前时长包络与候选，不等价于全体动作不可行。时长包络本身也必须由候选轨迹管给出，不能任意填写。此改动属于论文语义整理，不宣称 Phase 3 已实现完整动态资源窗口验证。

## 6. 公共 sampled-data 反馈的明确语义

原式 `sat(u_B + K_B(xhat - xbar_B))` 缺少采样周期和保持方式。Phase 3 使用可复现的采样保持定义：

\[
\hat x_k=x_k+e_k,\quad e_k\in E_x,
\]

\[
u_k=\operatorname{sat}_{\mathcal U_B}
\bigl(u_B+K_B(\hat x_k-\bar x_B)\bigr),
\qquad u(t)=u_k,\quad t\in[t_k,t_k+h).
\]

`u_B`、`K_B`、参考点、饱和界和 `h` 对同一信息节点内的隐藏场景相同。控制只能读取当前可用的 ego 测量；隐藏的 closure mode、未收到的消息、未来观测不能参与选增益或选动作。同样的实现观测历史给出同样的控制。公共**控制律**相同，不代表未来在不同公开测量下永远给出相同数值。

对源 ego 盒 `X_B`，验证器计算外包围

\[
U_B\supseteq\{
\operatorname{sat}_{\mathcal U_B}(u_B+K_B(x+e-\bar x_B)):
 x\in X_B,\ e\in E_x\}.
\]

将该 `U_B` 作为整个采样周期的输入盒交给现有 Picard 积分器是保守的：现有积分器连盒中任意可测时变输入都包住，因此也覆盖实际固定保持的控制。代价是丢失状态—控制关联，可能放宽轨迹管、导致 `UNKNOWN`；这不是错误接受的理由。饱和只保证固定输入盒限值，状态相关限值、速度/加速度/转角边界和摩擦约束仍必须沿完整轨迹管检查。

Schäfer、Gruber、Althoff 的论文在 Section II-A 明确给出相同的 sampled-data/zero-order-hold语义；其实际候选综合方法是 zonotope 与 successive convexification。这里仅沿用采样保持及独立验证原则，未声称实现了其算法或继承其全部定理。[S1]

有限模板与有限 `u_B/K_B` 候选搜索可找到经验证的控制见证，但不是连续参数空间的完备搜索；“所有候选未通过”只能说明本次搜索未找到，不能证明控制器不存在。Brown 等人的论文使用另一种离散时间 control-affine 问题与连续控制集合求解；其保证不能直接移植到本工程的有限模板搜索。[S2]

## 7. Brake/hold 的模型边界

当前六状态 ODE 为 `dot(v)=a+w_v`、`dot(a)=j+w_a`，`v` 是有符号速度；没有“车速一到零即截断”的混合驻车模式。

### 零速度不等于可驻车

无扰动时若在某刻 `v=0, a=-b<0`，保持零 jerk 将产生 `v(t)=-bt`，发生倒车。若到达 `v=0,a=0` 后还有 `w_v>0`，也会立即离开精确静止点。因此：

- 不允许把积分结果中的负速度裁剪成零作为安全证明。
- 有限 brake rollout 或进入声明的低速/低加速度目标盒，不等于无限时域驻车。
- 非零扰动下的 hold 必须依靠另外验证过的不变支持与公共后继控制；一个有限时段的 hold 测试不足以证明它。
- 真实车辆静摩擦、制动器保持或 CARLA 的执行机制若改变 ODE，须增加明确混合模式及相应验证，不能静默加入本阶段的自行车模型。

### jerk 受限停止还受加速度状态约束

若 `a0=-b<0`，允许最大正 jerk 为 `J>0`，即使用最快的 `j=+J` 解除制动，仍需 `b/J` 时间把加速度抬到零，期间至少损失速度

\[
\Delta v=\frac{b^2}{2J}.
\]

所以在禁止倒车且无其他改变模型的机制时，`v0 < b²/(2J)` 的初态不能被该 jerk 限制下的控制保持为全程非负速度。这是从 ODE 直接积分所得，不应通过容差或饱和绕过。上述推导仅适用于无扰动的这一子情形，实际验证仍使用完整区间管。

### benchmark 参数不是实车标定

旧 `configs/vehicle.yaml` 的 `wheelbase_m=2.8` 明确是占位测试值；论文和后来的名义 BMW profile 为 `2.5789128` m。Phase 3 应读取统一显式场景配置，不能把不同轮距、几何中心偏置或摩擦参数混用。论文 nominal CG 作为车身矩形中心代理本身仍是近似，CARLA 及真实车辆必须另行标定。

## 8. Phase 2 evidence 接口的修正动机

原 `_evaluate_action` 只调用 `evidence_verifier(evidence_ref)`。同一个被接受的字符串可被复制到不同源盒、不同控制或被改过的后验分支上；回调拿不到这些上下文，无法识别证据错配。这不推翻 Phase 2 的有限固定点算法，也不表示原来的 `certified=False` 演示曾获得真实安全证明；它是 Phase 3 接物理证据前必须收紧的信任边界。

新的证据验证应绑定至少：源完整支持、动作/公共控制律及输入像、每个源 atom、分支/后验、物理模型、步长、扰动及测量误差、硬约束上下文。回放时不仅要重算 Picard 不等式，也要确认所重算证据对应正在审查的这条转移。只对 JSON 求哈希能检测修改，却不能单独证明动力学、分支完整性或资源安全。

## 9. 其余不应过度扩张的结论

摩擦圆的纵向项是 `a`，不是 `j`；代码中该点正确。控制/状态边界与离散容量是硬可行性条件；用于排序的恢复 reserve 应明确选择连续物理裕度和正尺度。原稿正文“约束激活不会使 reserve 为零”过宽：若主动把摩擦裕度等物理 margin 放入 reserve，它在自身边界取零是合理的。本稿收窄措辞，仅说明动态等式、控制限值或整数容量激活不会**自动**令 reserve 为零。

有限观测分支覆盖、上层协议与实际传感可区分性尚未完整接入前，不能把本阶段的物理控制器候选或有限 graph 当作全系统递归安全证书。最终条件性定理仍依赖论文的 A1—A5。

## 10. 核查依据与可复查资料

本文件的单 cell 量词、向下闭包、终端外包围反例、占用时长反例及 jerk 公式均为根据上传论文与代码进行的直接推导，不依赖经验数值或引用替代证明。

- **[S1]** Lukas Schäfer, Felix Gruber, Matthias Althoff. *Scalable Computation of Robust Control Invariant Sets of Nonlinear Systems*. IEEE Transactions on Automatic Control, 69(2), 755–770, 2024. [TUM 作者机构页面](https://portal.fis.tum.de/en/publications/scalable-computation-of-robust-control-invariant-sets-of-nonlinea/)；[TUM 作者论文 PDF](https://mediatum.ub.tum.de/doc/1663416/bwcisj44cgsojpnjjmm8i9ifa.Schaefer%20-%202024%20-%20TAC.pdf)；[DOI](https://doi.org/10.1109/TAC.2023.3275305)。本次核对 Section II-A 的采样保持定义及候选/验证区分，没有照搬其 zonotope 算法。
- **[S2]** Scott Brown, Mohammad Khajenejad, Sze Zheng Yong, Sonia Martínez. *Computing Controlled Invariant Sets of Nonlinear Control-Affine Systems*. CDC 2023, 7830–7836. [NSF 论文原文](https://par.nsf.gov/servlets/purl/10505852)；[作者机构页面](https://asu.elsevierpure.com/en/publications/computing-controlled-invariant-sets-of-nonlinear-control-affine-s/)；[DOI](https://doi.org/10.1109/CDC49753.2023.10383613)。其离散时间模型、连续控制集合求解及完备性假设与本阶段有限模板搜索不同。

本次仅做 tex 内容修订及静态结构核对；没有运行 LaTeX 排版编译。工程验收不依赖 tex、bib 或会议样式文件。


## 11. Phase 3 独立解析界与 Picard 外包围取交

新增模块 `analytic_bounds.py` 不改变 C++、Picard 的搜索过程或原包含见证，而是给当前 ODE 的积分链提供另一组经过区间运算计算的外包围。两个针对同一真实可达集的外包围取交仍是外包围。交集为空意味着模型、起点、时间、输入或证据存在不一致；实现抛错，不进行容差扩张或裁剪。

设 `W=(Wpx,Wpy,Wpsi,Wv,Wa,Wdelta)` 是 additive derivative disturbance，`Uj` 与 `Uω` 分别是已经经过输入限幅的 jerk、转向角速度盒。对从本次调用给定 `initial` 开始的完整时段 `[0,h]`：

\[
\begin{aligned}
A(h)&\subseteq A_0+h(U_j+W_a),\\
V(h)&\subseteq V_0+h(A_0+W_v)+\frac{h^2}{2}(U_j+W_a),\\
\Delta(h)&\subseteq\Delta_0+h(U_\omega+W_\delta).
\end{aligned}
\]

这些式子也适用于盒中**随时间变化**的可测控制和扰动。例如

\[
v(h)=v_0+ha_0+\int_0^h w_v(s)\,ds
 +\int_0^h(h-s)(j(s)+w_a(s))\,ds.
\]

两个积分核均非负，因而分别被 `h Wv` 与 `(h²/2)(Uj+Wa)` 包住，无须假设扰动恒定。

只有下列条件全部精确成立时，才额外使用直行位置解析界：初始 `psi=delta=0`、`Uω=0`、`Wpy=Wpsi=Wdelta=0`。此时有 `delta(t)=psi(t)=0`，故

\[
P_x(h)\subseteq P_{x,0}+h(V_0+W_{px})
 +\frac{h^2}{2}(A_0+W_v)
 +\frac{h^3}{6}(U_j+W_a),
\]

且 `py` 保持初值、`psi=delta=0`。位置中的二次和三次项分别来自 `(h-s)` 与 `(h-s)²/2` 的非负核。只要任何直行前提不成立，即使只偏离一个很小非零量，`px/py/psi` 都保留原 Picard 包络。公式允许有符号速度，不会把倒车误当驻车。

`sound_tightening` 取传入 `duration_s` 的准确 binary64 点，收紧该时刻的 endpoint。`analytic_tube` 用 `[0,h]` 代入同一多项式，覆盖完整时间区间，包括内部极值，不是初末状态的线性插值。所有区间系数、端点及位置公式的加、乘、除和平方使用 MPFR directed interval API；速度 tube 另外采用下述精确有理二次极值再向外转换。先在普通浮点中求 `h*h` 再包装成点是不允许的。

**时间调用约定：** 本模块的时间以传入的 `initial` 为零点，不推断 Picard 子段或全局偏移。逐段可以使用该段 `witness.initial` 与准确的 `witness.duration_s`。若使用最初起点和累计时刻，必须区分 tube 与 endpoint：endpoint 的累计时刻必须与 binary64 输入精确相等，不能随意舍入。对 tube 则可先把累计 `end` 明确向上舍入为 `h_upper >= end`，用同一原始 initial 计算 `[0,h_upper]` 包络，再与 `[start,end]` 的 Picard tube 取交；扩大解析时间域只会保守。这也是 Phase 3 物理证据检查采用的方式，以避免较晚 Picard 子段初态的包装误差破坏精确直行恒等式。全步 endpoint 仍使用原始准确 binary64 决策周期。

**速度管的二次极值修正：** 初版直接把 `t` 替换为 `[0,h]`，会丢失不同次数中 `t` 的关联；例如 `v(t)=2-2t+t²/2` 在 `[0,2]` 内非负，初版自然区间却产生负下界。现在速度坐标改为两条严格的二次包络：

\[
q_-(t)=V_0^-+(A_0+W_v)^-t+\tfrac12(U_j+W_a)^-t^2,
\]

\[
q_+(t)=V_0^++(A_0+W_v)^+t+\tfrac12(U_j+W_a)^+t^2.
\]

由于积分核非负，对每个 `t∈[0,h]` 有 `q_-(t)≤v(t)≤q_+(t)`，即使输入和扰动随时间变化亦成立。实现将区间系数的 binary64 端点转换成准确 `Fraction`，在区间端点以及存在且位于区间内的驻点 `t*=-A/J` 求准确有理值，分别求 `min q_-` 与 `max q_+`。下界只需考虑凸二次的内点最小值，上界只需考虑凹二次的内点最大值；线性/常数情况只查端点。最后通过实际 `Fraction(float_value)` 与准确值比较，必要时用相邻 binary64 数向外转换。因此准确最小速度为零时可以得到严格的零下界，没有使用裁剪、epsilon 或另一种停车模型。

回归反例 `v0=0.125, a0=-1, j=4, h=0.25` 的真解为 `v(t)=2(t-0.25)^2`；现在速度 tube 为 `[0,0.125]`，终端 `v=a=0`，可在 `v_min=0` 的真实物理证据后接零输入驻车自环。若增加非零 `Wv` 使真实最低速度为负，新的包络仍保留负下界。位置的三次项继续使用保守自然区间，没有增加三次极值算法。

测试包括非二进制小数时长的准确有理数对照、负/零/正 jerk、初值与饱和输入盒角点、时变输入和扰动的分段精确积分、全部直行前提逐项失效、曲线运动保留几何包络、零速负加速度倒车、精确静止 self-loop、4 m/s 对称 jerk 制动后 `v=a=0`、中间速度极值、空交集拒绝、非法参数和不可精确表示的累计有理时长拒绝。加上二次内点最小/最大值、区间外驻点、线性退化、非二进制根的准确有理值、subnormal 舍入和真实扰动导致负速等回归后，模块独立测试为 **39 passed**。`test_backup_graph.py` 另有 **39 passed**，涵盖真实物理证据、2 模式 silence 自环、观测后分支、准确制动接驻车的两节点图、持久化/缓存篡改和执行失效守卫。两个文件合跑 **78 passed**；这不替代全工程验收。


## 12. 论文源文件引用一致性

单独上传tex中的 `kochdumper2021verification` 与 `sumo2018` 在附带BibTeX中不存在；对应条目实际键为 `kochdumper2021commonroad` 与 `lopez2018microscopic`。修订稿改用已存在的同一文献条目，没有编造新引用。另复制完整参考库为 `aaai2027_Phase3.bib` 并使新稿 bibliography 指向该文件。论文源文件已核对引用键与内部标签，但未进行LaTeX排版编译；这些文件均非工程构建或验收的强依赖。
