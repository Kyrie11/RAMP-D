# RAMP-D Phase 2 复核与 Phase 3 开发验收报告

日期：2026-11-10（用户时区）；版本：0.6.0。日志、报告目录使用 UTC 时钟。

## 1. 本轮结论

Phase 2 上传服务器报告通过其声明的**有限信息状态抽象与固定点**验收；本轮发现并修复
证据只按名称验证、不能绑定当前动作与后继的接口缺口，并移除了 tex/bib 强依赖。

Phase 3 已按既定路线完成公共恢复控制器、有限偏置/增益综合、局部物理证据验证与
回放、闭合策略图、执行与状态更新接口。一键完整验收实际得到：

- C++：3/3 通过。
- Python：295/295 通过，0 failures、0 errors、0 skipped。
- 旧 Phase 1A–2 回归全部通过。
- 4 类恢复模板均有经过独立物理回放的候选。
- 17 节点、每节点 2 个未区分隐藏模式的制动/停驻图闭合，独立文件回放成功。
- 精确有理动力学执行 20 步：4 s、8 m 后达到 v=a=0，再保持 1 s。
- 全部预期失败案例保守拒绝。

这些结果的范围是 `LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS`。
**它们不等于完整交通系统的 CERTIFIED，不等于已经完成动态规则下合法合流，也不等于
目标服务器已经运行 Phase 3。** 全支持协议验证是紧接着的 Phase 4；服务器仍需执行
本报告第 7 节命令。没有使用用户未提供的远程服务器、真实数据集或模拟器进程。

## 2. 对论文与既定工程路线的理解

论文要解决的是：交通规则可能已经物理改变，但自车尚未收到相关消息时，当前动作
是否仍给所有协议允许的隐藏历史保留合法且可执行的继续策略。

与实现直接有关的五个原则保持不变：

1. 外部事件、流量触发事件和交互让行有不同因果含义，不能全部当成普通 learned label。
2. 规则改变道路资源的 entry/stay/direction/capacity/controller 状态；资源是否被占用
   来自完整车身几何，不能直接用神经概率当 hard occupancy。
3. 同一实际观测历史只有一个公共控制 law；hidden change time 不是合法分支时刻。
4. 预测概率影响排序与效率；低概率但协议允许的危险历史不能从安全域中删除。
5. 安全结果必须来自外包围、hard predicates、完整后验和闭合 backup graph 的证据。

十阶段顺序继续为：0、1A、1B、1C、1D、2、3、4、5、6。
本轮没有先跳去训练 RRA/REA，也没有把仿真成功率冒充数学证书。

## 3. Phase 2 服务器报告审计

### 3.1 证据与结果

审阅对象是 `RAMP-D_Phase2_server_report.zip` 内的真实日志、XML、哈希、环境、demo
证书和 benchmark，并非只读取 acceptance_summary 的成功标签。

| 项目 | 上传服务器结果 | 本轮判断 |
|---|---:|---|
| native tests | 3 | 通过 |
| pytest | 129，零失败/错误/跳过 | 通过 |
| 数值库 | MPFR 4.0.2 官方头文件 | 无需升级 |
| Phase2 demo | FIXPOINT_CONVERGED；保留 A、L | 正确有限抽象结果 |
| Phase2 certificate replay | true | 有限博弈层面通过 |
| footprint audit | 40,000 projections，0 misses | 数值反证审计通过，不是系统证明 |
| 2000-cell benchmark | 约 0.02905 s | 单 atom/单 action/单 observation 自环微基准 |
| assurance | FINITE_ABSTRACTION_ONLY，certified=false | 范围声明正确 |

服务器 source_sha256 中 70 项与上传工程一致，覆盖核心源码、测试、脚本和配置。
两项论文材料不同，另有 6 项服务器生成/历史文件未随工程 ZIP 附带。
服务器 tex 哈希与**单独上传的 AnonymousSubmission2027.tex** 一致，因此本轮论文
修订以单独上传文件为准，不以 ZIP 内旧稿替代。

未发现需要推翻 Phase2 同步固定点、同观测后验聚合或单目标 cell 覆盖原则的错误。
没有将其微基准时间解释为真实自动驾驶规划器的延迟。

### 3.2 已确认并修复的接口缺口

旧接口只调用 `evidence_verifier(evidence_ref)`。在真实 MPFR 后端下可复现：把静止
动作从 `(0,0)` 改成 `(1000,1000)`，保留同一 ref 和后继，旧有限抽象仍保留该 cell，
旧回放仍成功。这不意味着旧项目曾给真实车辆发出安全认证——其 certified 本来就是 false；
但该接口不足以直接接入 Phase3/4 物理证据。

新接口为 `evidence_verifier(EvidenceContext)`，绑定完整 cell、源 atom、action_id、
control、controller_ref 及当前 transition 的全部观测后继。反馈引用继续绑定 bias、
gain、reference 和 saturation limits。Phase3 store 再绑定 h、W、E、车辆、场景和
Picard 参数，并实际重新计算证据。

13 项新增回归覆盖内容篡改、旧字符串接口、异常、非布尔 truthy 值及证书版本边界。
新证书保存为 v2；无反馈字段的旧 v1 仍可通过新 context verifier 回放。

### 3.3 tex/bib 与脚本修复

强依赖实际位于 `validate_phase1d.sh` 的源文件哈希循环，Phase2 调用它时被连带阻断。
现改成存在时附加记录，缺失时不会失败；同时修复 Phase2 不转发 CMake 参数、相对
BUILD_DIR 进入后续 Python 时可能不一致的问题。

独立的无任何根目录 tex/bib 源码副本已端到端执行 Phase2 脚本成功：3 native + 当时
142 Python tests 通过，参数转发、相对路径、回放和 ZIP 生成均通过。该专项只缩减
benchmark 重复与几何抽样，没有减少测试。最终 Phase3 全量恢复了默认 40,000 几何检查。

## 4. 数学修正与实现方法

### 4.1 信息状态量词必须一致

旧 backup-synthesis 公式将后验包含于多个目标信息 cell 的物理并集。这会允许同一个
实际观测的不同隐藏后继分别借用不同控制器，不能保证存在一个公共后续动作。

修正为：

\[
\forall Y:\operatorname{Post}(B,\kappa_B,Y)\ne\varnothing,
\quad \exists B_Y\in\mathcal S:
\operatorname{Post}(B,\kappa_B,Y)\subseteq\gamma(B_Y).
\]

同一 Y 下先聚合所有源 atom，再检查一个 B_Y。代码和修订稿现在一致。

### 4.2 终端集合采用匹配上下文的向下闭包

实际后验可能比保留盒更小；只把恰好等于保留盒的 supports 写成 S∞ 与代码包含判断不一致。
修正为：

\[
\mathcal S_\infty=
\{\mathcal B\ne\varnothing:\exists B\in\mathcal S_{in},
\mathcal B\subseteq\gamma(B)\},
\]

并要求共同的已观测时间/信息/协议上下文与证据相符。不能跨多个不同 cell 拼后验，
也不能在不同事件时段盲目复用证书。

### 4.3 外包围未包含不是已验证具体反例

若终端外包围不落入目标，可能只是包围太宽。修订 full-verifier 伪代码，要求原模型
下可实现的违反见证才返回 COUNTEREXAMPLE；否则细化或 UNKNOWN。此处对终端集合的
“miss”还必须尊重信息支持语义，不能拿单个真实隐藏状态替代完整 posterior。

### 4.4 不确定占用时长与退出保护

只检查 `t+T_max` 获准退出，不能保证较早发生的实际退出也受保护。修订使用
`D_mu=[T_min,T_max]`；stay/gap 对完整 `[0,T_max]` 检查，exit 需要
`t+D_mu ⊆ I_out`。该条件是保守调度筛选；通过后仍需轨迹验证，失败也不证明所有
其他 duration envelope 或其他轨迹都不可能可行。

### 4.5 公共采样反馈与完整 input image

采用

\[
u_k=\operatorname{sat}_{\mathcal U}
\big(u_B+K_B(\hat x_k-\bar x_B)\big),\quad
\hat x_k=x_k+e_k,\ e_k\in E,
\]

采样后在整个 h 内零阶保持。每个源 box 用 outward-rounded image
`sat(u_B+K_B(X+E-x_bar))` 传播；不是只验证名义中心命令。实现舍入也被 point-image
包围。同一节点的参数共同，law API 不接受 hidden mode。

### 4.6 停车、积分子链与二次极值

原 bicycle 的速度有正负号。`v=0,a<0` 会继续倒车；不能使用 `max(v,0)` 宣称停车。
本版保留模型，通过真实 jerk 曲线让 v 与 a 同时达到零。

独立解析子链界与已有 Picard 包围取交：

\[
a(h)\in a_0+h(U_j+W_a),\quad
v(h)\in v_0+h(a_0+W_v)+\tfrac12h^2(U_j+W_a).
\]

积分核非负，因此这些界允许时变的有界可测输入/扰动。直线位置公式仅在严格满足
零 heading、零 steering 及相应零扰动条件时使用。

实际开发中发现 `v0=.125,a0=-1,j=4,h=.25` 的真解
`v(t)=2(t-.25)^2≥0` 被自然区间求值误判。现在对两条二次上下包络，以 Fraction
精确计算区间端点和驻点极值，再向外转换 binary64；得到速度管 `[0,.125]` 及
终端 v=a=0。存在真实负速扰动时仍保留负下界，不会裁零。

完整数学说明、修订位置和一手方法参考见 `MATHEMATICAL_CORRECTIONS_PHASE3.md`。
新 tex 引用键和参考库也已核对；两个原有失配键映射到已存在同一文献条目。
没有编译 LaTeX 排版，也没有增加论文构建依赖。

## 5. Phase 3 代码交付

| 模块 | 实现内容 |
|---|---|
| control.py | 公共 affine law、饱和、测量误差 image、四类候选模板、内容摘要 |
| analytic_bounds.py | 同一 ODE 的积分子链收紧、准确二次速度 extrema、严格直行前提 |
| backup.py | 物理合同、独立证据回放、有限综合、完整后验目标覆盖、局部空间余量排序 |
| backup_graph.py | 固定点闭图、保存/加载回放、公共控制执行、观测和后验更新、失效守卫 |
| phase3_examples.py | 零扰动完整制动图、四模板非零误差局部目标、明确失败案例 |
| validate_phase3.sh | 全历史回归、Phase3 demo/benchmark/replay、自动报告和失败打包 |

C++ 数值源码与上传版本逐文件相同，ABI 仍为 3；本轮没有重新写 MPFR 或 Picard 内核。

综合只对有限的 bias/gain 候选搜索，保留通过者并按可证空间净距排序。当前余量是
静态道路/gate/障碍净距的 normalized lower bound，不是论文全部物理恢复裕度的 Gamma*，
也不是全局连续优化。状态、控制与摩擦等仍作为硬条件独立检查。

四模板的动作目标与边界：

- Brake-to-stop：完整零扰动停止图；另有带误差的减速单步。
- Hold-before-gate：有限步停驻目标；只有闭合不变支持才能外推到后续时域。
- Yield：朝低速参考减速的局部物理恢复；真实他车让行规则由 Phase4 接入。
- Clear/merge：开始朝目标车道横向运动的物理恢复；不预先宣称完整合流或合法清空。

运行时需要 sound 外部 posterior，初始化及执行时 pin 合同。未知观测、错时更新、
越界支持、被改动的控制器/证据或缺失源转移都会拒绝并锁存失效。

## 6. 实际验收结果与失败分析

### 6.1 全量结果

完整日志在 `reports/local_phase3_full/`；不是 bootstrap 声明头文件运行。

| 项目 | 本地实际结果 |
|---|---:|
| C++ | 3 passed |
| Python 全套 | 295 passed / 10.27 s |
| 原 Phase2 测试 | 129 保留 |
| 证据绑定新增 | 13 |
| 公共控制 image | 46 |
| 解析收紧 | 39 |
| 控制器综合/物理验证 | 29 |
| 策略图/执行 | 39 |
| Python failures/errors/skipped | 0 / 0 / 0 |
| Picard falsification | 20,480 state vectors，0 containment misses |
| footprint falsification | 40,000 projections，0 misses |
| 四模板 | 4/4 SYNTHESIZED_LOCAL |
| 制动图 | 17 retained nodes；每节点2模式；闭合、回放通过 |
| 合成图执行 | 20 steps / 5 s；4 s时停止；随后1 s停驻 |

本地工具版本：Python 3.12.14、GCC 14.2.0、CMake 4.4.4、MPFR runtime/header 4.2.2、
pytest 9.2.0。MPFR 头文件来自官方 4.2.2 发布源码，与运行库版本一致。目标服务器原有
Python 3.10、GCC 9.4、CMake 3.18 和 MPFR 4.0.2 不需要因本轮而升级。

### 6.2 四模板局部 benchmark

每类 3 次重复；这是开发期局部有限搜索，包含候选 tube 与回放开销。

| 模板 | 候选数 | 接受数 | 中位耗时 ms | 三次样本的nearest-rank p95 ms |
|---|---:|---:|---:|---:|
| Brake-to-stop | 3 | 2 | 76.18 | 87.46 |
| Hold-before-gate | 2 | 2 | 49.27 | 54.10 |
| Yield | 3 | 1 | 79.67 | 87.16 |
| Clear/merge | 2 | 1 | 53.20 | 53.44 |

三次样本不构成论文级延迟统计，不是完整 planner p95，也不能据此声称硬实时。
17节点制动图本次候选搜索耗时总和约1.145 s，未将其冒充包括所有图回放/执行在内的总耗时。
后续应在用户服务器同一预算与场景分布上重新测量。

### 6.3 开发失败与纠正

本轮实际发现并修复的内容包括：旧证据复用、论文强依赖、静止点积分松弛误拒、
累计时间隐式舍入风险、停车二次依赖过宽、首个分离轴余量过弱、最后候选超时未标记、
手工 graph 证据覆盖缺失、节点与动作 law 引用不一致、非法观测未进入 lost。
每项均有针对性回归；详见 `FAILURE_LOG_PHASE3.md` 和 `PHASE3_SYNTHESIS_TEST_REVIEW.md`。

故意不可行/未证明的输入保持拒绝：gate 位于车身内、静态通道被堵、极低摩擦、非零扰动
精确停驻点未闭合、无共同控制、相同观测后验需跨目标拼接、未经实现的动态他车状态。
这些失败不被记作假造的具体 COUNTEREXAMPLE，也不通过放宽状态裁剪来消失。

## 7. 用户服务器复现

建议新目录运行，保留原 `/home/senzeyu2/code/RAMP-D`：

```bash
cd /home/senzeyu2/code
conda activate mfrp
unzip -q RAMP-D_Phase3.zip -d .
cd /home/senzeyu2/code/RAMP-D_Phase3
python -m pip install -r requirements-test.txt
PYTHON_BIN="$(command -v python)" bash scripts/validate_phase3.sh
```

如果同名 Phase3 目录已存在，先保留或改名后再解压，避免旧构建混入。
结束后上传：

```text
/home/senzeyu2/code/RAMP-D_Phase3/reports/RAMP-D_Phase3_server_report.zip
```

若以后仍想执行旧阶段：`bash scripts/validate_phase2.sh` 可独立使用，不需要 tex/bib。
非默认 MPFR 目录通过 `-DCMAKE_PREFIX_PATH=/实际路径` 传给任何对应入口即可。

## 8. 数据集与模拟器接入安排

### 8.1 使用用户已给路径

| 内容 | 历史用户给出的服务器路径 |
|---|---|
| AV2 Motion | /data0/senzeyu2/dataset/Argoverse2/motion |
| AV2 Map Change | /data0/senzeyu2/dataset/Argoverse2/map |
| WOMD 1.3.1 解压根 | /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed |
| WOMD 主分支 | 上述根目录下 scenario/ |

这些是对上传对话中 `## 用户` 的提取，不是实际访问后确认的服务器文件清单。
路径示例保存为 `configs/data_sources.example.json`，不构成运行依赖。

### 8.2 WOMD Scenario

继续使用 Scenario 分支。官方说明其 TFRecord shard 内包含多条 Scenario protobuf；
常规预测窗口为10历史点+1当前点+80未来点，共91点；原始场景为20秒，二者不能混淆。
训练/验证具有未来标签，官方 motion 测试输入隐藏未来。

官方 schema 特别要区分：`sdc_track_index` 与 `tracks_to_predict.track_index` 是数组索引；
`objects_of_interest` 是 `Track.id`。`valid=false` 不能填零并当作有效 actor；
`dynamic_map_states` 不能直接当作 ego 已收到的交通灯消息。

先做 validation 小样本 adapter，再 training、validation_interactive；training_20s
用于长时域研究前须核对其与标准窗口的来源/去重/split关系。tf_example 暂不需重复下载。

来源：[WOMD 官方格式](https://waymo.com/intl/en-ca/open/data/motion/)、
[官方 Scenario proto](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto)。

### 8.3 AV2 Motion Forecasting

继续使用 MF 的轨迹 parquet 与同场景矢量地图 JSON，先 validation 小样本，再 train/val。
MF 本身有地图，不需要为了接 MF 先下载整个 Map Change。缺少逐车长宽/轴距时，保守
类别包络必须标记来源；不能把全部车辆套上 BMW 的精确几何。

官方目前已发布 test annotations，最终预测评分时再按任务下载相应标注。
Map Change 仅在执行独立地图变化实验时接入；不将其地图差异标注解释为规则消息四时钟。

来源：[AV2 官方下载与标注](https://www.argoverse.org/av2.html)、
[AV2 MF schema说明](https://argoverse.github.io/user-guide/tasks/motion_forecasting.html)。

两数据源位置通常是 bounding-box center；若转入后轴动力学，使用标定 offset 做
`p_rear=p_center-R(psi)o`。速度转换还需考虑 yaw 运动造成的刚体旋转项，不能只平移位置。
完整字段、误差和标注边界见 `DATASETS_AND_SIMULATORS.md`。

### 8.4 何时开模拟器

本轮无需新增下载或启动模拟器。Phase4 先在小型合成协议支撑上验真；Phase6 正式接入
SUMO1.20/CARLA0.9.16。保留 SUMO 负责交通/控制器、CARLA 负责 ego/传感器/遮挡的分工。

需要相机/GPU传感器时，CARLA headless 应使用 offscreen；no_rendering 会返回空GPU
传感器数据。同步固定步长还需满足物理子步约束且只有一个 tick owner。
当前没有宣称用户这两个版本的 co-simulation bridge 已经测试兼容。

来源：[CARLA0.9.16渲染](https://carla.readthedocs.io/en/0.9.16/adv_rendering_options/)、
[同步与步长](https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/)。

## 9. 下一阶段 Phase 4 的明确目标

下一轮继续采用“目标—实现—测试—失败分析—验收报告”，重点是把 Phase3 局部图变成
完整协议合同下可核验的候选策略，而不是提前转去神经模型训练。

1. 版本化有限协议 automaton，区分外部/触发/交互事件，并枚举全部允许离散后继。
2. 明确物理变化、issue、receipt、local-first-observation 四个时钟；effective interval 独立保留。
3. 只有 publication+delivery 等保证足够时，silence 才能排除潜在历史。
4. 动态资源 alpha/beta、方向、容量、冲突及 monitor，与连续 footprint 占用连接。
5. 构造受 ego 影响但保守的他车可达管，覆盖全部声明扰动，禁止用 learned likelihood 截断。
6. 观测分支只在实际可区分后出现；完整 posterior 进入一个兼容终端图节点。
7. 验证器仅在完整工作队列安全出清后返回 CERTIFIED；有原模型可实现违反见证才返回
   COUNTEREXAMPLE；预算/不明确/包围过宽返回 UNKNOWN。
8. 证据绑定完整模型/协议/观测/资源版本，缓存执行只有合同与观测仍匹配时有效。

完整 CEGAR 主循环保留 Phase5；Phase4 只提供正确的具体化/待细化接口，不提前声称完成
全部反例驱动算法。详细接口、16组验收场景和边界见 `PHASE4_PLAN.md`。

## 10. 交付与当前进度

源码包包含完整历史数值内核、新 Phase3 代码与测试、最终本地报告、阶段设计/失败分析、
服务器说明、数据与模拟器说明、下一阶段计划、修订 tex 与匹配 BibTeX。

Phase0–1D 保持原验收；Phase2 服务器基线已审阅，必要修正已回归；Phase3 本地工程验收通过。
等待用户目标服务器回传同一脚本报告后，再按 Phase4 目标继续实现。
