# Phase 3：公共 Backup Controller 设计与验收合同

## 1. 本轮实现目标与阶段定位

本轮继续原路线的 **Phase 3：Public Backup Controller**。Phase 2 已提供联合信念支持、公共候选动作、按观测聚合后验以及有限固定点；Phase 3 负责产生可以执行的公共控制律，给每条局部物理转移生成可回放证据，并把保留信息单元组织成执行图。

开发顺序仍是：**明确目标 → 实现代码 → 执行测试 → 分析失败案例 → 形成验收报告**。本文件定义目标、实现接口、数学合同与验收条件；实际运行结果和机器环境由验收报告记录，不把设计预期写成已经完成的实验结果。

本阶段需实现：

1. `brake_to_stop`、`hold_before_gate`、`yield`、`clear_merge` 四类恢复控制模板。
2. 同一信息支持上的公共偏置 `u_B`、公共反馈增益 `K_B`、参考状态与输入限幅。
3. 对完整采样周期的状态、摩擦、静态道路/入口和障碍物连续约束验证。
4. 真实 Picard 证据、控制律、源支持和观测后验之间的上下文绑定。
5. 所有观测子节点均保留的 backup policy graph，以及带失效守卫的执行/状态更新。
6. 一键回归、正向物理演示、负向案例、证据回放与报告打包。

本阶段的证明范围固定为：

```text
LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS
full_support_certified = false
```

具体含义是：使用已声明的六状态自行车 ODE、导数扰动/测量误差盒、静态道路与障碍物、冻结的离散模式、显式提供的有限观测覆盖。真实协议自动机、动态资源许可/容量、其他智能体动态响应、消息时钟及实际观测可区分性，留到 Phase 4 接入。预测器、数据训练、SUMO/CARLA 不作为本阶段的依赖。

## 2. 模块与输入输出

| 模块/接口 | 主要输入 | 主要输出与用途 |
|---|---|---|
| `control.SampledFeedbackLaw` | 模板类型、`bias`、`gain(2×6)`、参考状态、输入限幅 | 一个只读取公开 ego 测量的饱和仿射控制律；`command()` 产生二进制浮点命令，`image()` 产生经过定向舍入的控制像 |
| `control.recovery_candidates()` | 模板、参考状态、偏置网格、增益尺度 | 有限公共控制律库；包含零增益候选与模板反馈候选 |
| `backup.BackupContract` | 状态/输入限制、车辆/摩擦参数、几何、步长、扰动、测量误差、道路/入口/障碍物、Picard 选项 | 一个可序列化且有摘要的局部验证合同 |
| `backup.validate_feedback_step()` | 一个源 `SupportAtom`、公共 law、合同 | `StepCheck`：`VALIDATED_LOCAL` 或 `UNKNOWN`，以及端点、控制像、空间裕度、Picard proof |
| `backup.inspect_step_proof()` | 同一源、law、合同与已有 proof | 不重新搜索候选，回放不等式并重新检查局部硬约束 |
| `analytic_bounds.sound_tightening()` | 本次起点、控制/扰动盒、准确时长、原端点外包围 | 独立解析外包围与 Picard 端点的交集 |
| `analytic_bounds.analytic_tube()` | 本次起点、控制/扰动盒、覆盖时长、原 tube | 覆盖完整时间区间的解析界与 Picard tube 的交集 |
| `backup.LocalEvidenceStore` | 合同、law、每个源 atom 的真实检查结果、观测覆盖 | 按内容寻址且绑定上下文的证据记录；`verify(EvidenceContext)` 回放当前义务 |
| `backup.synthesize_backup()` | 完整源 `BeliefCell`、有限候选库、目标支持族、store、观测覆盖、预算 | `BackupSynthesis`：所有通过候选、确定性排序、每次尝试的原因与搜索状态 |
| `backup_graph.build_backup_graph()` | 带候选动作的完整单元族、evidence store | 经 Phase 2 固定点选择的闭合图及公共 law/观测子节点 |
| `save_backup_graph()` / `load_backup_graph()` | 图或 JSON 文件、可选调用方合同摘要 | 序列化/独立回放图；加载会重新计算固定点并比较节点声明 |
| `backup_graph.BackupExecutor` | 图、起始节点、sound 初始支持、调用方可信合同摘要 | `command()` 发出一次控制；`advance()` 在真实观测和新后验到来后更新图节点 |
| `phase3_examples` | benchmark 合同与模板类别 | 17 节点制动/驻车图、准确有理执行审计、四模板单步目标案例和预期拒绝案例 |

源支持保持 Phase 2 语义：`BeliefCell` 是一个完整信息状态，由多个连续盒和离散 mode 的 `SupportAtom` 组成。它不能被拆成多个可自由选动作的隐藏状态。`ActionWitness.control` 在引用公共反馈 law 时记录其偏置；实际控制必须通过 `controller_ref` 解析完整 law，而不是把偏置当作整个反馈器。

## 3. 公共控制律与四类模板

### 3.1 采样保持与测量误差

状态及输入顺序固定为：

\[
x=(p_x,p_y,\psi,v,a,\delta),\qquad u=(j,\omega_\delta).
\]

控制器只在决策时刻读取可用的 ego 测量，采用 zero-order hold：

\[
\hat x_k=x_k+e_k,\quad e_k\in E_x,
\]

\[
u_k=\operatorname{sat}_{\mathcal U_B}
 \bigl(u_B+K_B(\hat x_k-\bar x_B)\bigr),
\qquad u(t)=u_k,\quad t\in[t_k,t_k+h).
\]

同一信息节点内，`u_B`、`K_B`、参考点、限幅和周期相同。隐藏的 open/closed 标签、未收到的消息和未来观测不进入 law 的参数选择或执行输入。不同历史只有在实际公开观测不同之后才可走向不同图节点。公共控制律相同，允许它针对不同的公开 ego 测量产生不同数值命令。

对每个源 ego 盒，计算：

\[
U_B\supseteq\{\operatorname{sat}_{\mathcal U_B}
 (u_B+K_B(x+e-\bar x_B)):x\in X_B,e\in E_x\}.
\]

饱和是单调映射，代码分别对区间上下端点施加相同限幅，而不是只裁一端。所有仿射区间运算使用 MPFR。执行命令选在该测量点的定向区间计算结果内，并检查属于验证过的源控制像，避免把普通浮点点积的误差隐藏在证据之外。

Picard 后端可以包围 `U_B` 内任意可测时变控制，因此也覆盖实际固定保持控制。这会丢失状态—控制相关性，带来保守性，但不会因为使用反馈而自动使 tube 不可靠。

### 3.2 有限候选综合

本阶段枚举偏置网格、零增益及有限增益尺度；每一个候选都需要后续物理验证。没有引入新的 MPC、神经策略或全局连续优化器。

| 模板 | 候选结构与局部目标 | 本轮验证边界 |
|---|---|---|
| `brake_to_stop` | 速度/加速度反馈以及可配置 jerk 偏置；目标是减速或接入已验证终端支持 | 单步带扰动例证明减速目标；另外的零过程扰动图证明完整名义制动接驻车 |
| `hold_before_gate` | 可包含位置、速度、加速度反馈，横向包含航向/转角反馈 | 入口前的有限局部维持；非零扰动下不能把有限目标盒直接叫作无限驻车不变集 |
| `yield` | 面向较低目标速度的速度/加速度反馈 | 证明局部减速/让行准备，尚不证明多车交互的正式让行协议 |
| `clear_merge` | 速度/加速度反馈加横向位置、航向、转角反馈 | 当前单步例证明开始横向运动并到达明确目标盒，不证明已完成整段合法合流 |

`recovery_candidates()` 中对尺度 `s>0` 的纵向候选分别为：hold 的 `(-s³,0,0,-3s²,-3s,0)`，其他模板的 `(0,0,0,-s²,-2s,0)`；clear/merge 的横向候选读取 `p_y/psi/delta`，其他模板读取 `psi/delta`。这些是可搜索模板的参数化，不是未经验证的稳定性结论。

一个候选只有在**每个**源 atom 的物理步都通过，且**每个**非空观测后验都由一个目标信息单元覆盖时才能保留。任何一个隐藏源失败，都拒绝该公共候选。

## 4. 数学合同：真实物理证据及独立解析交集

### 4.1 继承 Phase 1 数值合同

保持 MPFR 内部计算、向外 binary64 转换、严格 Picard 自包含、准确有理子步时间、整段 swept footprint 与失败关闭语义。原 C++ 和原 Picard 见证格式未被解析公式替换。

每次候选评估先生成真实 Picard tube，再由 `inspect_step_proof()` 回放：起点、控制像、车辆参数、扰动、周期、Picard 选项、全部包含不等式、时间连续性和端点链接都必须匹配当前义务。只写 `VALIDATED_LOCAL` 字样或只计算一个哈希不能代替这些检查。

### 4.2 解析积分链

对于 additive derivative disturbance 的当前 ODE，令

\[
A=A_0+W_v,\qquad J=U_j+W_a.
\]

独立端点界为：

\[
\begin{aligned}
a(h)&\in A_0+hJ,\\
v(h)&\in V_0+hA+\tfrac12h^2J,\\
\delta(h)&\in\Delta_0+h(U_\omega+W_\delta).
\end{aligned}
\]

上式对盒内时变控制/扰动也有效，因为积分核 `1`、`h-s` 非负。仅当初始 `psi=delta=0`、转向角速度盒为零且 `Wpy=Wpsi=Wdelta=0` **全部精确成立**时，进一步使用直行位置三次积分界并保持 `py/psi/delta` 的恒等式。其他情况下保留 Picard 的几何坐标包络。

两个外包围对应同一模型/起点/时间域时，其交集仍为外包围。空交集抛错，不扩大容差，也不裁剪状态值。

### 4.3 速度 tube 的准确二次极值

直接把时间替成 `[0,h]` 会丢失 `t` 和 `t²` 的相关性，在准确停止时制造负速度下界。为避免这一类确定的保守失败，代码对速度使用两条二次包络：

\[
q_-(t)=V_0^-+A^-t+\tfrac12J^-t^2
\le v(t)\le
V_0^++A^+t+\tfrac12J^+t^2=q_+(t).
\]

MPFR 先得到系数区间，随后把系数的 binary64 端点转成准确 `Fraction`。在时间区间端点和可能的内部驻点 `t*=-A/J` 求准确值，计算 `min q_-`、`max q_+`，最后根据准确有理值与实际浮点值的比较向外转换。下界看凸二次内点最小值，上界看凹二次内点最大值；线性退化只检查端点。

这不是速度钳制。若扰动使真实可达速度为负，包络仍保留负值；准确最小值为零时才可能得到严格零下界。位置三次式仍采用保守区间计算，没有扩展为新的三次优化器。

### 4.4 累计子步时间

原 Picard 的子段时间采用准确有理数。累计端点不一定能准确转为 binary64，因此不能直接 `float(end)` 后宣称它就是原端点。

当前局部证据检查对 tube 显式构造 `h_upper >= exact_end`，从原始 source 计算 `[0,h_upper]` 的解析外包围，再与当前 `[start,end]` 的 Picard tube 取交。扩大解析时间域只会保守，并能避免较晚子段的包装误差破坏精确直行恒等式。全步 endpoint 使用原始准确 binary64 决策周期，未对实际端点时间做替换。

完整公式、反例和证明范围见 [MATHEMATICAL_CORRECTIONS_PHASE3.md](MATHEMATICAL_CORRECTIONS_PHASE3.md)。

## 5. 硬约束与当前空间裕度评分

`inspect_step_proof()` 对每个完整连续子段检查：

- 状态盒属于合同中的硬安全域，必需/允许的离散模式字段满足声明。
- 输入 law 的饱和限幅被合同输入限幅包含。
- 摩擦圆使用加速度 `a` 和横向加速度 `v² tan(delta)/Lw`，对整个状态盒的区间上界不超过 1。
- 经后轴参考点偏置变换后的完整 swept footprint 位于静态矩形道路走廊。
- 若设置 gate，整个 swept footprint 的最前端都保留要求的入口前空间余量。
- 静态障碍物与 ego swept footprint 有严格分离，并满足最小 clearance。

障碍物距离使用候选分离轴中最好的**已证明**距离下界。多个有效下界取最大值仍是有效下界；不应仅因第一个分离轴给出很弱的间距而忽略其他轴。没有任何轴能证明分离时返回 `UNKNOWN`，不把外包围重叠直接叫作具体碰撞。

本阶段用于候选排序的量是局部**空间 clearance 下界评分**：

\[
\rho_B=\min\left\{1,\min_{\text{source, segment, spatial margin}}
\frac{m-m_{\min}}{s_{\rm clearance}}\right\}.
\]

`m_min` 与正尺度来自配置。它覆盖道路边缘、gate 与静态障碍物的空间余量；摩擦、状态、输入和目标支持属于硬可行性检查。该评分不是论文完整的 \(\Gamma\)：还没有综合动态资源占用窗口、消息延迟、其他智能体间隙、停止/清空时间储备及全部公共恢复策略。

候选按空间评分降序排列，再按偏置绝对值之和与 law 摘要作确定性排序。偏置项只是排序规则，不宣称是量纲统一的完整驾驶任务代价。所有通过候选都保存下来，供固定点在某个后继被剔除后尝试其他公共动作。穷举完有限候选库只能得到该库内的最好已验证空间下界，不能声称连续参数空间全局最优或控制器存在性判定。

## 6. 后验完整性、证据绑定与闭图

### 6.1 一个观测后验对应一个信息单元

输入 `observation_cover` 必须列出每个源 atom 的所有声明观测标签；未提供时，本地示例使用共同 `silence`。对标签 `Y`，代码先合并所有能够产生它的源 atom 后继，再要求

\[
\forall Y\text{ with nonempty posterior},\quad
\exists B_Y\in\mathcal S:\quad
\operatorname{Post}(B,\kappa_B,Y)\subseteq\gamma(B_Y).
\]

不能把一个 joint posterior 拼到多个只覆盖各自隐藏模式的目标单元。包含测试还要求后验的每个连续盒由目标单元中的一个同 mode atom 盒完整包含；只能通过多个部分盒拼接的情况保守地保持 unresolved。

本阶段观测标签的**物理真实性及完整性**是显式输入假设。代码能检查映射覆盖了每个源 atom，却不能从这些字符串证明现实中一定能收到该消息或区分该模式。这一证明由 Phase 4 的协议和观测模型承担。

### 6.2 证据不再只验证字符串

Phase 2 的 ref-only callback 无法判别旧证据被复制到另一条转移。当前 `EvidenceContext` 把源完整支持、源 atom、动作/公共 law、分支后验等义务绑定到证据；`LocalEvidenceStore` 还绑定物理合同摘要、law 摘要、端点、裕度和完整 Picard proof。

回放必须同时确认：引用的内容摘要、当前义务摘要、合同和 law 一致；用相同输入重新计算控制像和物理检查；后验 atom 与重算端点及冻结 mode 一致。修改哈希本身不能绕过真实物理回放。

### 6.3 固定点与序列化

`build_backup_graph()` 调用 Phase 2 的同步剔除固定点，保留存在公共已验证动作且所有观测子节点均可保留的信息单元。一个源单元只是有一条有限安全步，不意味着它必然属于闭图。

`save_backup_graph()` 保存源单元、动作、节点声明和证据 store。`load_backup_graph()` 重放证据、重新计算固定点、比较节点/动作/law/观测子节点声明。运行方可以传入自己的 `expected_contract_digest`；只接受文件里自述的合同不能证明它就是当前场景。

## 7. 执行与失效行为

执行遵守一条明确时序：

1. 初始化时固定可信合同摘要，重建检查内存中的图，确认起始节点被保留且初始支持被其包含。
2. 在准确决策时刻调用 `command(measured_state, at_time=...)`。重复命令、错误时刻或已丢失状态均拒绝。
3. 命令前重放缓存源转移，检查节点/law/action 引用一致、law 内容摘要一致、源覆盖完整以及合同没有变化。
4. ego 测量必须与当前支持及声明测量误差兼容；输出命令必须落在验证控制像中。
5. 到下一准确决策时刻，调用 `advance(observation, posterior, at_time=...)`。实际观测必须是已有分支，新后验同时被存储传播支持和目标单元包含。
6. 更新节点、支持和内部准确时间，才可发下一次命令。

未知观测、非法测量/时间、越界支持、被修改的缓存、合同变更等会设置 `lost=True` 并抛出 `BackupExecutionError`。此后不允许继续使用旧证据，也不会自动替换成“紧急制动一定安全”的默认动作。上层应按系统设计报告证据丢失并进入另行定义的处置流程。

运行时 `posterior` 的前提必须保留：它来自 **sound 外部状态估计/协议过滤器**。包含测试允许后验缩小，却不能证明任意删除隐藏模式合理；不能把实际隐藏标签作为已观测信息传入。当前类也不负责驱动实车执行器或实时调度器。

## 8. 两组物理示例承担不同验证任务

### 8.1 零过程扰动的 17 节点 brake/hold 闭图

`build_braking_graph()` 从 `v=4 m/s, a=0` 开始，16 个 `h=0.25 s` 的制动步，加一个终端 hold 节点，共 17 个信息节点。每个节点保留 open/closed 两种隐藏模式，共享 `silence` 与同一控制。

名义 jerk 为：前 2 s 取 `-1 m/s³`，后 2 s 取 `+1 m/s³`。直接积分给出：

\[
v(t)=4-\tfrac12t^2,\quad 0\le t\le2;
\qquad
v(2+s)=2-2s+\tfrac12s^2,\quad0\le s\le2.
\]

因此 4 s 时准确 `v=a=0`，总纵向位移准确为 8 m，全程速度非负。没有把负速裁成零，也没有在 ODE 中加入隐藏驻车模式。末端位置的二进制外包围误差保留下来，零速零加速度 hold law 使其保持。终端 law 的 `K_B` 非零，但只作用于当前终端支持中精确为零且测量误差为零的 `v/a/psi/delta` 坐标。

此示例明确要求过程扰动为零，不能用它证明非零扰动下的精确点驻车不变性。`execute_braking_graph()` 使用独立准确有理数直行积分审计控制与状态更新，并在 16 个制动步之后继续执行驻车步；每次依然通过执行守卫。

候选综合不是仅保存写好的控制序列：每个制动单元还评估较小 jerk 和零 jerk 等候选，必须通过真实 tube/目标支持检查才能选入；终端也包含应被拒绝的继续制动候选。

### 8.2 四模板的非零误差单步目标

`template_problem()` 给四模板加入非零过程扰动和速度/加速度测量误差，设置具体源盒与具体目标盒。默认共同 `silence` 使两个隐藏 mode 保持在一个后验内。

| 模板 | 单步目标的实质 |
|---|---|
| brake | 从约 3 m/s 的速度盒减速，端点速度上界严格降低，并产生受约束的负加速度 |
| hold | 将近零速度/加速度源盒保持在入口前的小位置、低速和低加速度目标盒 |
| yield | 从约 2 m/s 降低速度，为让行准备，而非宣称已完成互动协商 |
| clear/merge | 以约 2 m/s 开始朝 `y=3.5 m` 参考方向转向，目标 `py/psi/delta` 为正；仍只验证一个局部动作 |

这些是有界误差下的**有限一步**目标验证。目标盒在这些示例中没有全部继续综合为不变图；hold 示例允许小的有符号速度，clear/merge 尚无动态车流间隙和资源许可。因此不能把它们改写为完整闭环安全合流或非零扰动下的无限驻车实验。

## 9. 显式 benchmark 配置

主演示通过 `BackupContract.from_dict()` 读取 `configs/backup_benchmark.json`。下表记录该配置，不从旧的 `configs/vehicle.yaml` 占位值读取轮距。

| 项目 | 配置值 | 解释 |
|---|---|---|
| 车辆轮距 | `2.5789128 m` | 名义 BMW benchmark；不是旧占位 `2.8 m` |
| 车身长/宽 | `4.508 / 1.610 m` | swept rectangle 尺寸 |
| 后轴到矩形中心偏置 | `(1.4227170936, 0) m` | 该 benchmark 以 CG 作矩形中心代理，实车/CARLA 需另行标定 |
| 摩擦系数与重力 | `mu=0.6`, `g=9.81 m/s²` | 本场景参数；不表示车辆固定的“真实摩擦” |
| jerk 限制 | `[-2, 2] m/s³` | 固定控制饱和盒 |
| 转向角速度限制 | `[-0.35, 0.35] rad/s` | 固定控制饱和盒 |
| 决策周期 | `h=0.25 s` | 当前闭图 fixture 按此周期生成 |
| 状态 x/y 范围 | `px∈[-50,100] m`, `py∈[-4,7] m` | 后轴状态硬界；另有更严格的车身道路约束 |
| 航向/转角范围 | `psi∈[-0.7,0.7] rad`, `delta∈[-0.45,0.45] rad` | 硬界 |
| 速度/加速度范围 | `v∈[-0.25,8] m/s`, `a∈[-3,2] m/s²` | benchmark 支持小有符号速度；要求禁止倒车的实验应设置 `v_min=0` 并重新验证 |
| 静态道路走廊 | `x∈[-60,120] m`, `y∈[-2.5,5.5] m` | 用整个车身外包围检查 |
| gate 前边界 | `x=15 m` | 检查车身最前端，不只检查后轴坐标 |
| 最小空间余量/归一化尺度 | `0.05 m / 1 m` | 硬 clearance 门槛及空间评分尺度 |
| 基础过程扰动 | 六维全零 | 仅为准确制动/驻车闭图提供名义过程合同 |
| 基础测量误差 | `px/py` 各 `±1e-9 m`，其他为零 | 有理执行审计的浮点测量表示误差保留在合同内 |
| Picard 最大子步 | `0.03125 s` | 比决策周期小；属于数值验证设置 |
| Picard 默认预算 | `max_iterations=16`, `max_depth=20`, `max_steps=10000`, `max_attempts=20000` | 超出预算不自动接受 |
| 其他数值设置 | `min_step_s=1e-7`，绝对膨胀各 `1e-9`，相对膨胀 `0.125` | 膨胀是候选包络搜索参数，不是准许违反约束的安全容差 |

四模板的派生合同把 gate 放在 `x=30 m`，加入 `Wpx=±0.005`、`Wv=±0.02`、`Wa=±0.04` 的相应导数单位扰动，其他导数扰动为零，并将速度/加速度测量误差设为各 `±0.01`。派生合同有不同 ID 与摘要，不能替换原闭图合同后继续使用旧证据。

这些均为显式 benchmark 假设。真实数据源的 actor reference point、车辆几何、扰动界、摩擦和执行延迟需要在后续阶段校准。

## 10. 搜索预算与状态解释

`synthesize_backup()` 的候选数上限是硬枚举上限。其时间预算是**非抢占式软预算**：在候选之间检查，并在候选完成后检查是否超时；不会中断正在生成/回放的一条完整候选证据，因此实际耗时可能超过给定值。

| 状态 | 含义 |
|---|---|
| `SYNTHESIZED_LOCAL` | 有通过候选，且本次有限候选枚举完成 |
| `PARTIAL_SEARCH` | 预算到期前已得到通过候选；只完成部分候选搜索 |
| `UNKNOWN_BUDGET` | 预算耗尽且尚无通过候选 |
| `UNKNOWN_NO_VALIDATED_CANDIDATE` | 所枚举候选均未通过；不等于所有可能控制器不存在 |
| `VALIDATED_LOCAL` | 一条物理步已按当前静态局部合同回放通过 |
| `UNKNOWN` | 当前外包围、约束、预算或目标支持未获得证明；不自动等于具体违反 |

采样命令计算与图守卫也有计算成本。当前脚本报告的是离线有限综合/回放时间；少量重复的 nearest-rank p95 不构成自动驾驶在线时延指标或硬实时调度保证。

## 11. 测试、失败案例与验收

### 11.1 验收层次

本轮保留此前数值/几何/有限固定点回归，并增加以下有意义的测试：

- 公共 law 的饱和、非零增益、测量误差控制像、仅使用公开状态。
- 解析积分链与准确有理真解，时变控制/扰动的非负核包络，非二进制时间、subnormal 舍入和二次内部极值。
- 各源 atom 的真实 Picard proof，源/控制/合同/后验的上下文绑定及篡改拒绝。
- 同一观测后验不能拆到不同目标单元，数值分裂不创造新观测。
- 车身前偏置、低摩擦、子段内部静态碰撞、无法证明分离等负向条件。
- 两模式 silence 自环、观测后分支、真实制动接驻车闭图、文件回放与运行时缓存守卫。
- 预算不足、未知观测、错误时刻、越界测量/支持和证据丢失后拒绝继续执行。

对应主要文件为 `tests/test_public_control.py`、`test_analytic_bounds.py`、`test_evidence_binding.py`、`test_backup_synthesis.py`、`test_backup_graph.py`。实际通过数以本次生成的 `pytest.xml` 和验收摘要为准，本设计文件不预填最终总数。

### 11.2 预期拒绝也属于验收

`phase3_examples.expected_failures()` 构造 gate 穿入 swept body、静态走廊被占据、摩擦不足，以及非零过程扰动下把准确静止点强行作为 self-loop 等案例。这些应当拒绝或返回 `UNKNOWN`。将所有测试都调成成功反而破坏失败关闭语义。

本轮已经定位并修复的类别应在失败分析中保留：ref-only 证据错配、node/action law 引用错配、缓存失效与非法观测/时间未锁存、准确停止时自然区间引入的假负速，以及第一根分离轴距离下界过弱。更完整的数学反例见数学修正说明；验收报告需区分已经修复的实现缺陷与仍然存在的保守拒绝。

### 11.3 可复现运行入口

在目标服务器解压工程后，使用已有 Python 3.10+、CMake、C++ 编译器和官方 MPFR/GMP 开发头文件环境运行：

```bash
python -m pip install -r requirements-test.txt
bash scripts/validate_phase3.sh
```

`validate_phase3.sh` 先执行 Phase 2 验证链，因此会重新构建数值库、运行 native/Python 回归和既有审计，再运行 Phase 3 demo、四模板 benchmark、独立 graph replay 和验收门槛。tex/bib 是可选论文材料，不是运行依赖。

主要产物包括 `acceptance_summary.json`、`phase2_acceptance_summary.json`、`pytest.xml`、`phase3_demo.json`、`phase3_backup_graph.json`、`phase3_trace.json`、`phase3_benchmark.json`、`phase3_replay.json` 与日志。脚本会尝试生成 `reports/RAMP-D_Phase3_server_report.zip`；失败运行也保留诊断并生成失败摘要。

已构建后可以单独复查图：

```bash
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
export RAMPD_INTERVAL_LIB="$PWD/build_phase3/librampd_interval.so"
python scripts/replay_backup_graph.py reports/<本次报告目录>/phase3_backup_graph.json
```

实际执行时应由调用方独立提供可信合同摘要。命令行回放的 `--expected-contract-digest` 可固定该合同；不带该选项的回放只检查文件自述合同内部的一致性。

验收必须满足：此前数值回归不退步；四模板都获得至少一个经验证候选；17 节点图闭合并回放；准确执行审计得到 4 s/8 m 的名义停止并继续 hold；所有预期失败被拒绝；证明范围字段始终明确 `full_support_certified=false`。目标服务器报告仍需检查实际编译环境、官方头文件、完整测试与输出，不能把其他机器通过直接改写成目标服务器验收完成。

## 12. 下一阶段交接

Phase 4 应沿原路线把当前局部边证据升级为协议完整转移证据：实现事件激活/发布/接收时钟、协议分支、资源 entry/stay/exit 状态和 monitor、容量/冲突、其他智能体外包围、真实观测路由及终端支持覆盖。只有全部支持与连续约束被验证后，才可按论文定义实现全系统 `CERTIFIED / COUNTEREXAMPLE / UNKNOWN`。

Phase 3 已为 Phase 4 保留 `EvidenceContext`、公共 law、可回放 tube、统一 contract、完整 posterior 与 graph 执行守卫接口。无需替换研究路线；应替换和补全局部静态环境/声明观测的证据后端。数据集和模拟器接入安排见 [DATASETS_AND_SIMULATORS.md](DATASETS_AND_SIMULATORS.md)。
