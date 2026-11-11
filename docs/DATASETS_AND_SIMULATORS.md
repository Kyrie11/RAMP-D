# 数据集、模拟器与后续接入约定

资料核对日期：2026-11-10（用户所在时区日期）。

本文依据用户上传的《自动驾驶规划实现分析.md》、本轮论文和下列官方资料整理。**本轮没有访问用户服务器，没有读取服务器数据集，也没有运行 SUMO/CARLA。** 路径来自用户历史消息，不是本轮目录探测结果。

## 1. 本轮与后续阶段的边界

继续采用既定顺序：

`0 → 1A → 1B → 1C → 1D → 2 → 3 → 4 → 5 → 6`。

| 阶段 | 需要完成的工作 | 数据与模拟器要求 |
|---|---|---|
| Phase 3 | 公共 backup law 的综合、区间验证、恢复策略图和执行 | 使用显式 benchmark 配置和合成信息 cells；不要求下载数据或启动模拟器 |
| Phase 4 | 协议分支、完整支持、规则/资源/连续碰撞和终端成员验证 | 先用可穷尽的合成协议实例建立证据链；准备真实场景适配合同 |
| Phase 5 | 真实/伪反例区分、CEGAR 和完整验证队列 | 回归同一协议和动力学合同 |
| Phase 6 | 预测训练、场景筛选、联合仿真、闭环实验和论文表格 | 正式接入 WOMD/AV2，按实验需要启动 SUMO/CARLA |

原设计记录在第 4249–4273 行列出 Phase 3 的四种模板、公共偏置与反馈增益、图和执行接口；第 4275–4287 行规定 Phase 4 才连接完整协议证据；第 4300–4316 行安排正式数据和仿真工作。本文没有把这些工作提前作为 Phase 3 的运行依赖。

`configs/data_sources.example.json` 仅保存后续数据路径和建议，不被 Phase 3 测试或验证器读取，亦不代表数据适配器已经实现。

## 2. 用户已指定的位置和环境

历史来源为上述设计记录中的“## 用户”，尤其第 11、755 行。

| 项目 | 用户指定值 |
|---|---|
| 工程 | `/home/senzeyu2/code/RAMP-D` |
| AV2 Motion Forecasting | `/data0/senzeyu2/dataset/Argoverse2/motion` |
| AV2 Map Change | `/data0/senzeyu2/dataset/Argoverse2/map` |
| WOMD 1.3.1 | `/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed` |
| WOMD 主分支 | 上述目录中的 `scenario/` |
| Python | 3.10；历史运行环境名为 `mfrp` |
| CARLA server / Python API | 0.9.16 |
| SUMO | 1.20 |
| 仿真运行方式 | 无头 |

WOMD 预期目录为 `scenario/{training,training_20s,validation,validation_interactive,testing}`。用户此前说 AV2 按下载名称建立目录，所以 `Train/Validation/Test` 与压缩包中的 `train/val/test` 都可能出现。后续适配器必须按真实 manifest 或显式配置解析，不能不经检查自动猜测并选错 split。

## 3. WOMD：以 Scenario protobuf 为主

### 3.1 格式与时间轴

WOMD 以 TFRecord 分片存储记录；一个分片中有多个 Scenario。标准训练/验证预测窗口以 10 Hz 提供 10 个历史点、1 个当前点、80 个未来点，共 91 点；测试隐藏未来真值。原始片段为约 20 秒，标准预测样本来自重叠的约 9 秒窗口。[W1]

Scenario 与 `tf_example` 是相关数据的不同表示，不能当作互不重复的额外训练集。Scenario 保留结构化轨迹、矢量地图和动态地图状态，适合本项目统一场景结构；后续确有吞吐需求时再生成训练 tensor cache。1.3.1 的新增 `sdc_paths` 是候选可行路线信息，不能解释为道路权限或规则消息。[W1, W3]

### 3.2 按官方 proto 定义字段

| 字段 | 适配含义 |
|---|---|
| `scenario_id` | 场景身份；仍需保存数据版本、split 和分片来源 |
| `timestamps_seconds` | 场景时间轴，不假设所有文件具有相同长度 |
| `current_time_index` | 区分历史、当前和未来；不得把未来字段作为在线可观测输入 |
| `tracks[i].states[j]` | 第 i 条轨迹在时间索引 j 的状态 |
| `ObjectState.valid` | 测量有效性；false 不能补为零位置/零速度 |
| `center_x/center_y` | 目标框中心位置，非后轴中心 |
| `length/width/height` | 目标框尺寸，需保留数据与估计误差来源 |
| `heading` | 框前向航向；不能用速度方向无条件替代 |
| `velocity_x/velocity_y` | 速度向量 |
| `sdc_track_index` | `tracks` 的数组索引 |
| `tracks_to_predict[].track_index` | 预测目标的数组索引 |
| `objects_of_interest` | **`Track.id` 标识符，不是数组索引** |
| `dynamic_map_states[j]` | 同一时间索引的动态地图状态 |

字段解释以官方 `scenario.proto` 为准。[W2] 官方概览页对 `objects_of_interest` 的文字概述与 proto 的 ID 定义不一致，后续必须增加“track ID 不等于数组下标”的回归样例。

建议适配流程是：逐 record 读取 TFRecord → `scenario_pb2.Scenario.ParseFromString` → 验证时间/valid mask/字段身份 → 转换为项目场景对象。TensorFlow 和 Waymo reader 保持为独立可选依赖，不能加入底层 MPFR、belief 或 backup 模块的强依赖。

### 3.3 各 split 的用途

| 数据 | 首次使用时间与用途 |
|---|---|
| `scenario/validation` | Phase 6 先取少量分片验证 adapter，再做固定验证集 |
| `scenario/training` | 正式预测训练 |
| `scenario/validation_interactive` | 交互预测/交互场景筛选；遵守其任务协议 |
| `scenario/training_20s` | 较长时域交互和场景挖掘；核对真实时长、窗口关联、去重和 split 隔离后使用 |
| `scenario/testing` | 最终预测任务；不能当作具有完整未来真值的普通本地评估集 |
| `tf_example/*` | 暂不要求；需要时用于经核对的训练表示 |

不能把 `training_20s`、标准 training 窗口随机混合后再随机切分训练/验证；记录 window-to-source 关联并保持原始 split。现有公开资料不足以替代用户文件清单核查，本文**不承诺** `training_20s` 与其他目录之间不存在重叠。维护者说明了 TFRecord 分片与样本的区别，以及 interactive split 的挑战用途，但其公开讨论未解决所有窗口关联问题。[W4]

## 4. AV2 Motion Forecasting

### 4.1 格式和加载接口

AV2 MF 的场景为约 11 秒、10 Hz 轨迹；常规预测设置使用约 5 秒历史和 6 秒未来。保留 `observed`、`timestep`、轨迹类别、对象类别和场景时间戳，不能假定每条轨迹都在全部时间点存在。其 position 同样是 bounding-box 中心。[A1, A2, A7]

后续可使用官方 API：

```python
from av2.datasets.motion_forecasting.scenario_serialization import (
    load_argoverse_scenario_parquet,
)
from av2.map.map_api import ArgoverseStaticMap

scenario = load_argoverse_scenario_parquet(scenario_path)
static_map = ArgoverseStaticMap.from_json(map_json_path)
```

`scenario_path` 与 `map_json_path` 是未来适配器解析出的路径，这段是接口示意，不是本轮新增的可运行转换脚本。轨迹采用 parquet；地图 API 使用 `log_map_archive_<id>.json`，Motion Forecasting 场景有自身矢量地图，不需要依赖 Map Change 大包才能加载。[A3, A4]

### 4.2 下载计划

| 数据 | 是否需要 |
|---|---|
| Validation | 首先用于少量 adapter 样本和固定验证 |
| Train | 正式训练时需要 |
| Test | 最终预测实验需要 |
| Single-Agent Test Annotations | 进行相应单目标本地测试评分时需要 |
| 页面名为 Multi-World Test Annotations 的文件 | 进行匹配的多目标测试评分前核对其实际 schema 和指标协议 |
| Map Change Part 1–21 | 地图变化实验实际纳入论文时再准备；不作为 MF 或 Phase 3 前提 |
| Sensor / Lidar 大包 | 当前规划路线不要求 |

官网已发布测试标注；多目标入口的实际文件名为 `av2_mf_multi_test_annotations.parquet`，不应仅凭页面标题把它解释成反事实世界标注。[A1] 原历史建议“暂不下载测试标注”可以用于当前阶段；最终本地测试评分则需要匹配任务的真实标签。

Map Change 是地图与传感器不一致检测数据：其变化样本集中于测试部分，不等于现成的交通规则事件/通信数据。[A1] 只有确定地图变化子实验后，才有理由下载全部 Part 或按官方可用 manifest 选择所需场景；不建议现在为了继续控制算法开发而要求完整 1 TB 下载。

### 4.3 缺失尺寸和代理参数

常规 AV2 MF object-state schema 没有逐车长度、宽度、轴距或后轴偏移。[A2, A5] 后续允许采用显式的类别尺寸包络和偏移不确定集合，但必须记录：来源、适用类别、覆盖假设及校准方法。不能把名义 BMW benchmark 的精确数值套给全部交通参与者。

WOMD 虽然提供框尺寸，也不能把每一帧的估计尺寸当成无误差车身真值。建议建立包含测量误差的尺寸区间或按轨迹计算保守包络；若缺少可信覆盖假设，输出用于经验评估的几何结果，不能升级为无条件实车证书。

## 5. 统一参考点、速度与时间合同

### 5.1 中心位置到后轴状态

项目自行车动力学的 `px, py` 是后轴中心；公开数据中的中心不能直接填入该状态。令固定车身偏移 o 从后轴指向目标框中心，R 为车身旋转矩阵：

\[
p_{\rm rear}=p_{\rm center}-R(\psi)o.
\]

若中心速度及航向角速度可用，刚体关系进一步给出：

\[
\dot p_{\rm rear}
=\dot p_{\rm center}-\dot\psi R(\psi)Jo,
\qquad
J=\begin{bmatrix}0&-1\\1&0\end{bmatrix}.
\]

这些关系是直接运动学推导：只平移位置、仍把中心速度直接当成后轴速度，在转弯时通常不一致。后轴有符号纵向速度取车身纵向投影；残余横向速度作为模型适用性检查或模型误差，不能静默删除。

偏移未知时使用包含真实偏移的集合或保持对象为“中心参考的几何预测对象”；不是所有他车都必须拟合为同一自行车。航向角差先 unwrap，再估计导数；低速时由速度或 yaw rate 反推转向的公式可能病态，应扩大不确定集或拒绝该拟合。加速度、jerk、转向角和转向速度由有限差分得到时属于估计量，不能把点估计作为严格物理边界。

### 5.2 时间和数据泄漏

10 Hz 只说明采样频率，不证明 0.1 秒之间的连续行为。安全模块需要连续外包络和显式扰动/agent-response 假设；不能以相邻 log 点线性插值代替安全证书。

统一场景对象至少保留数据版本、原始场景 ID、split、源文件、原始时间戳、当前预测时刻、valid mask、坐标变换、参考点/几何来源和采样间隔。模型输入严格按当前时刻截断，未来轨迹只作为监督/评估；未来 traffic signal ground truth 也不能作为当下已收到的信息。

### 5.3 两数据集不提供完整四时钟

RAMP-D 需要分别表达：

\[
t_{\rm activation},\quad
t_{\rm issue},\quad
t_{\rm receipt},\quad
t_{\rm first\ local\ observation}.
\]

当前所核对的标准轨迹/地图 schema 没有完整标注这套事件、通信、观察链。[W2, A2, A5] WOMD 的动态信号状态是场景上下文，不等于 ego 收到的消息；AV2 Map Change 的可见变化标注不等于真实改变发生时刻或消息发布时间。四时钟和可能延迟必须通过协议模型及可控仿真实验记录，不应从公开数据中编造。

统计预测用于候选排序与效率。数据经验分布、模型置信度或训练集覆盖均不能裁掉 Phase 4 协议允许的低概率分支。

## 6. Phase 4 前应准备的协议合同

下一阶段先定义并单独验收以下内容，再连接真实场景：

1. **规则事件与资源**：资源几何、方向、容量、冲突关系、入口/占用/清空义务、monitor 离散状态。
2. **因果与时序**：物理生效、消息生成/发出、收到和首次本地观察的独立时钟，允许延迟范围以及时间边界上的先后顺序。
3. **观测**：当前可测 ego 状态、噪声/误差集合、消息内容与身份、观测单元边界；实际不可区分的隐藏状态继续共用控制节点。
4. **环境支持**：外部规则、交通触发事件和交互响应分别建模；显式列全允许 successors，不以预测网络 likelihood 代替。
5. **连续证据**：agent tube、扰动、几何/参考点、摩擦与参数界；把证据绑定到来源 cell、控制、时段和场景假设。
6. **观测后路由**：对同一观测聚合所有源隐藏状态的 successors，再验证整个 posterior 被一个 retained information cell 覆盖。
7. **结果合同**：完整支持检查通过才是 `CERTIFIED`；有经过验证的具体违例才是 `COUNTEREXAMPLE`；超时、包络重叠、分支覆盖不明或缺证据为 `UNKNOWN`。

先使用可穷尽的小协议例子验证分支覆盖、迟到消息、隐藏变化、非预见性和终端路由。真实场景 adapter 不负责“创造”缺失协议证据。

## 7. SUMO / CARLA 的后续使用

保留原分工：SUMO 负责交通流、其他车辆、信号和道路事件；CARLA 负责 ego 物理执行、传感器和遮挡；项目 bridge 负责统一时钟、消息队列、protocol state 和独立验证。

CARLA 0.9.16 官方提供 SUMO co-simulation，支持固定 `--step-length`、选择 `--tls-manager`，`--sumo-gui` 是可选 GUI 参数。[C1] 用户已安装的版本保留，**但本轮并未验证 SUMO 1.20 与该 CARLA 安装的实际兼容性**。Phase 6 应先跑最小同步与 actor/信号对应 smoke test，再启动批量实验。

同步仿真使用固定步长，满足：

\[
\texttt{fixed\_delta\_seconds}
\leq
\texttt{max\_substep\_delta\_time}\times\texttt{max\_substeps}.
\]

只设一个仿真 tick owner，按物理帧号/时间戳关联传感器数据，保留传感器产生与送达时间；不能仅按 Python 回调到达顺序绑定。[C2] SUMO TraCI 可用于步进与状态/控制通信。[S1]

“无头”需区分：

| 模式 | 后续实验用途 |
|---|---|
| CARLA `-RenderOffScreen` | 无显示窗口但保留渲染，适用于 camera/GPU sensor 与遮挡观察 |
| CARLA `no_rendering_mode=True` | 可用于纯状态交通实验；camera/GPU sensors 返回空数据 |
| SUMO `sumo`，不传 `--sumo-gui` | 无头交通仿真 |

CARLA 0.9.16 官方明确区分前两种模式。[C3] 需要视觉观察的实验不能用 no-rendering 空观测代替。当前不需要执行任何启动命令。

## 8. 可选服务器目录清单（只读）

这些命令只在进入数据接入阶段或用户方便时运行，本轮验收不需要它们；它们不下载、不修改数据，也不安装依赖。

```bash
python - <<'PY'
from pathlib import Path

roots = {
    'av2_motion': Path('/data0/senzeyu2/dataset/Argoverse2/motion'),
    'av2_map_change': Path('/data0/senzeyu2/dataset/Argoverse2/map'),
    'womd_scenario': Path('/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario'),
}
for name, root in roots.items():
    print(name, str(root), 'exists=', root.is_dir())
    if root.is_dir():
        for child in sorted(root.iterdir()):
            print(' ', child.name, 'dir' if child.is_dir() else 'file')
PY
```

进入 Phase 6 时再提供具体 reader 的依赖锁定、少量样本 schema 审计、数据去重和转换验收指令；本轮不提供未实现的转换器命令。

## 9. 官方来源

以下均于 2026-11-10 核对。源码分支可能更新，正式数据接入时应固定使用的 package/schema commit 并记录到运行 manifest。

- **[W1] WOMD Motion 格式与时间采样**：https://waymo.com/intl/en-ca/open/data/motion/
- **[W2] WOMD authoritative Scenario proto**：https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto
- **[W3] WOMD 1.3.1 下载与版本记录**：https://waymo.com/intl/en-ca/open/download/
- **[W4] WOMD 官方仓库维护者关于 shard 与 interactive split 的说明**：https://github.com/waymo-research/waymo-open-dataset/issues/720
- **[A1] AV2 官方数据集与下载页**：https://www.argoverse.org/av2.html
- **[A2] AV2 Motion Forecasting 用户指南**：https://argoverse.github.io/user-guide/tasks/motion_forecasting.html
- **[A3] AV2 官方 parquet reader**：https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/scenario_serialization.py
- **[A4] AV2 官方 map API**：https://github.com/argoverse/av2-api/blob/main/src/av2/map/map_api.py
- **[A5] AV2 官方 Motion Forecasting schema**：https://github.com/argoverse/av2-api/blob/main/src/av2/datasets/motion_forecasting/data_schema.py
- **[A6] AV2 官方获取数据指南**：https://argoverse.github.io/user-guide/getting_started.html
- **[A7] AV2 数据集作者论文，Section 3.3.1**：https://arxiv.org/pdf/2301.00493
- **[C1] CARLA 0.9.16 SUMO co-simulation**：https://carla.readthedocs.io/en/0.9.16/adv_sumo/
- **[C2] CARLA 0.9.16 同步与时间步**：https://carla.readthedocs.io/en/0.9.16/adv_synchrony_timestep/
- **[C3] CARLA 0.9.16 渲染/无头模式**：https://carla.readthedocs.io/en/0.9.16/adv_rendering_options/
- **[S1] SUMO 官方 TraCI 文档**：https://sumo.dlr.de/docs/TraCI/index.html
