# RAPID-AD

**RAPID-AD = Recoverability-Aware Plan Invalidation Diagnostics for Autonomous Driving**

工程目标：围绕“交通控制约束变化后，现有驾驶计划是否仍然有效、何时需要撤销，以及车辆是否仍有安全恢复能力”建立一个可复现的 CARLA 闭环诊断基准。第一版使用 MARSHAL 的场景执行、交通指挥者 actor、控制器接口、同步传感器和日志设施；不修改 MARSHAL 原始场景与 runner 注册表。

> 重要边界：第一版的 `frame_hold` 是对交给控制器的 RGB 图像做时间窗口内的帧保持，只改变视觉证据可用性，不改变 CARLA 世界真值。它用于因果诊断，不等于物理遮挡。物理遮挡是独立的外部有效性测试。所有“失败机制存在”“超加性”结论必须等待重复实验。

## 1. 目录约定

- 代码：`/home/senzeyu2/code/RAPID-AD`
- MARSHAL：`/home/senzeyu2/code/MARSHAL`
- CARLA：`/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15`
- 输出与场景清单：`/data0/senzeyu2/dataset/RAPID-AD`

## 2. 环境检查

先激活你运行 MARSHAL 的 Python 环境。不要在没有检查版本的情况下安装另一个 `carla` PyPI 包；CARLA PythonAPI wheel 必须与服务器版本匹配。

```bash
export CARLA_ROOT=/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15
export MARSHAL_ROOT=/home/senzeyu2/code/MARSHAL
export RAPID_ROOT=/home/senzeyu2/code/RAPID-AD
export RAPID_DATA=/data0/senzeyu2/dataset/RAPID-AD

python --version
find "$CARLA_ROOT/PythonAPI/carla/dist" -maxdepth 1 -name 'carla*0.9.15*.whl' -print
python "$RAPID_ROOT/scripts/preflight.py" \
  --carla-root "$CARLA_ROOT" \
  --marshal-root "$MARSHAL_ROOT" \
  --roadwork-root /home/senzeyu2/code/roadwork-dataset \
  --bench2drive-root /home/senzeyu2/code/Bench2Drive \
  --skip-server
```

如果 `import carla` 失败，先找出与当前 Python 版本匹配的 wheel。例如当前环境是 Python 3.10 且目录中存在 `carla-0.9.15-cp310-...whl` 时：

```bash
python -m pip install "$CARLA_ROOT"/PythonAPI/carla/dist/carla-0.9.15-cp310-*.whl
```

不要把示例中的 `cp310` 直接用于其他 Python 版本。若没有匹配 wheel，建议建立独立 Python 3.10 环境或按 CARLA 0.9.15 的安装说明编译/安装匹配的 PythonAPI。MARSHAL 当前仓库文档主要验证的是 CARLA 0.9.16；0.9.15 需要先通过现有场景冒烟测试，不能假定完全兼容。

如果 MARSHAL 依赖尚未安装，先阅读其 requirements / README，再在同一环境安装。RAPID-AD 的设计生成、汇总和静态测试仅使用 Python 标准库；视觉模型仍需要 MARSHAL 对应的 PyTorch / Transformers 等依赖。

## 3. 启动 CARLA

在单独终端启动服务器（按你的机器 GPU/显示配置调整质量选项）：

```bash
cd "$CARLA_ROOT"
./CarlaUE4.sh -quality-level=Epic -RenderOffScreen -carla-rpc-port=2000
```

确认没有其他实验正在使用 RPC port 2000。CARLA 服务器与 PythonAPI 必须版本一致。RAPID-AD 的首个场景使用 Town03；CARLA 包必须包含 Town03。

另一个终端执行：

```bash
python "$RAPID_ROOT/scripts/preflight.py" \
  --carla-root "$CARLA_ROOT" \
  --marshal-root "$MARSHAL_ROOT" \
  --host 127.0.0.1 --port 2000
```

## 4. 阶段 1：先复现 MARSHAL 原有基线

在 MARSHAL 仓库中，先只跑已有的代表场景和 oracle / baseline。具体参数以当前 clone 的 `--help` 为准：

```bash
cd "$MARSHAL_ROOT"
python scripts/_run_reference_staging_sweep.py --help
python scripts/_run_reference_staging_sweep.py \
  flagger_control flagger_slow_then_stop sequential_directive stale_directive_residue \
  --controller oracle --controller baseline
```

如果当前 clone 的参数或场景名与示例不一致，以 `--help` 输出为准。目标是确认 CARLA、flagger actor、同步相机、控制器和日志完整工作；不要把这一步的结果当成新研究结果。

## 5. 安装 RAPID-AD 场景入口

安装脚本只向 MARSHAL 新增一个薄入口文件，不修改 MARSHAL 的原始 runner 或已有场景：

```bash
python "$RAPID_ROOT/scripts/install_overlay.py" \
  --marshal-root "$MARSHAL_ROOT" \
  --project-root "$RAPID_ROOT"

export PYTHONPATH="$RAPID_ROOT:$MARSHAL_ROOT:${PYTHONPATH:-}"
python "$RAPID_ROOT/scripts/selftest.py"
```

入口文件为 `marshal_bench/scenarios/rapid_ad_factorial_demo.py`，实际实现留在 RAPID-AD 项目中。若已存在同名文件，安装脚本会先备份。

## 6. 第一版场景设计

### GO -> STOP：安全撤销

- `control_transition=0`：指挥者始终保持 PROCEED，是匹配的静态对照。
- `control_transition=1`：车辆接近控制线时，PROCEED 切换为 STOP。
- `phase=early/late`：目标切换距离分别为 12m / 9m（从自车中心到虚拟控制线）。
- `gap_timing=none/pre/overlap/post`：视觉输入帧保持窗口相对于目标切换距离的位置。
- 车辆目标速度默认 12 km/h；虚拟控制线与指挥者的纵向位置对齐（`control_line_offset_m=0`），避免把合理地停在指挥者前方误判为越线。

### STOP -> GO：合法恢复

- `control_transition=0`：STOP 始终有效，是静态等待对照。
- `control_transition=1`：在 episode 开始后的 3s / 7s 切换为 PROCEED。
- `phase=short_wait/long_wait`：控制状态释放时机。
- `gap_timing=none/pre/overlap/post`：帧保持窗口相对于释放时刻的位置。

`core` 包含 16 个匹配条件（两种任务 × 转换开关 × 两个阶段 × 无 gap/overlap gap）；`all` 包含 32 个条件，加入 pre/post 顺序对照。`smoke` 只有 6 个条件，仅用于确认工程链路，不用于统计结论。

## 7. 阶段 2：生成场景清单并跑 smoke

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite smoke --seeds 0 \
  --controllers rapid_ad_oracle baseline pid \
  --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" \
  --host 127.0.0.1 --port 2000
```

这会在 `RAPID_DATA/design/` 写出 JSON/CSV 场景清单，并把每个 episode 的原始日志和 `rapid_ad_metrics.json` 放到 `RAPID_DATA/runs/`。`rapid_ad_oracle` 是特权参考控制器，只用于证明场景可解，不是待比较算法。`baseline` 通常是只看交通灯的基线，`pid` 是几何跟踪参考，均不能被当作有能力理解临时指令的强视觉模型。

如果 smoke 中 oracle 都不能正确停车/恢复，先调试几何和控制线，不要运行强模型或解释失败率。

## 8. 阶段 3：验证是否存在可重复失败

先跑 core 的 oracle 和基线：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite core --seeds 0,1,2 \
  --controllers rapid_ad_oracle baseline pid mpc \
  --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" \
  --host 127.0.0.1 --port 2000
```

然后单独跑一个视觉模型。示例模型名需要替换成你本机可用、且 MARSHAL `VLMController` 支持的模型：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite smoke --seeds 0,1,2 \
  --controllers vlm --model /path/to/your/local-vlm \
  --query-period-s 0.5 \
  --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" \
  --host 127.0.0.1 --port 2000
```

`query-period-s=0.5` 是第一轮诊断配置，目的是减少策略查询间隔与物理不可恢复性的混杂；之后应再测试 1.0s / 1.5s，明确区分模型查询节奏导致的延迟。VLM 的视觉证据消费时间只有在 controller 暴露 decision history 时才可直接记录；对黑盒端到端策略只能测外部行为响应，不能声称直接观测到内部 belief update。

确认工程链路稳定后，运行完整 32-cell 顺序矩阵：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite all --seeds 0,1,2 \
  --controllers rapid_ad_oracle baseline pid mpc \
  --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" \
  --host 127.0.0.1 --port 2000
```

然后用 VLM 或已安装 checkpoint 的闭环模型替换/追加 controller。不同架构的配置可以通过 `--controller-config-json path/to/controller_config.json` 传入。不要把缺少 checkpoint、接口不兼容或 setup invalid 的 episode 当成模型失败。

## 9. 评价标准与失败归因

每个 episode 会输出：

- `rapid_ad_metrics.json`：单次运行摘要；
- `rapid_ad_trace.json`：每个同步 tick 的控制线距离、车速、指令真值、恢复余量和 gap 状态；
- MARSHAL 的 `metrics.csv`、`events.json`、camera frames 和 metadata。

关键量：

1. `unsafe_crossing_while_stop`：STOP 有效时车头越过控制线。
2. `recoverability_margin_at_evidence_m`：证据重新可用时，控制线余量减去车长、缓冲、估计制动距离和反应预算。
3. `observable_brake_response_latency_s`：证据可用后，外部可观测到的制动/油门响应延迟；它不是内部 plan invalidation time。
4. `stop_confirmed_before_release` 与 `resume_latency_s`：合法放行前是否确实停车，以及证据可用后多久恢复行驶。
5. `collision_count`、`setup_valid`、`anchor_status`：用于过滤场景搭建失败和未暴露到目标阶段的 episode。

失败标签区分 `unsafe_continuation`、`stop_not_completed`、`unrecoverable_before_evidence`、`decision_after_recovery_deadline`、`initial_stop_not_established` 和 `stale_retention`。请同时报告失败率与不可恢复率；不可恢复样本不能被简单归咎于即时 plan revocation。

制动参数 `max_brake_decel_mps2=4.5` 是初始保守假设，不是实测真值。正式实验前应使用 MARSHAL 已有的 `_brake_calibration.py` 或自建制动标定，更新 `configs/base_episode.json`，并报告敏感性分析。对 CARLA 不同车辆蓝图，不能共用一个未经验证的制动上限。

## 10. 分析结果

```bash
python "$RAPID_ROOT/scripts/analyze_results.py" --data-root "$RAPID_DATA" --run-tag <上一步打印的RUN_TAG>
```

输出位于 `analysis/<RUN_TAG>/`：

- `cell_summary.csv`
- `factorial_interactions.csv`
- `analysis_metadata.json`

交互项是加性风险尺度上的描述性估计。只有每个 cell 有足够重复、setup 有效、场景可解性匹配，并报告置信区间后，才能讨论因果交互；单次 32-cell 运行不能证明超加性失败。

## 11. RoadWork 与 Bench2Drive 的作用

第一版不需要重新训练模型，也不需要从 RoadWork 收集大规模新数据集。RoadWork 用于检查施工区视觉语义的现实性；Bench2Drive 可以后续提供额外闭环模型/评测基线。先把 MARSHAL 的控制器接口跑通，避免在版本不兼容、checkpoint 缺失和场景因果问题之间同时排错。

## 12. 当前限制

- 第一版场景使用 MARSHAL 的 Town03 控制点，控制线由指挥者纵向位置上游 3m 的虚拟线定义；需要通过截图和轨迹检查确认它确实落在正确车道。
- `frame_hold` 只干预 RGB 输入，车辆状态和信号灯字段保持实时；这是一种可控的证据延迟，不是完整传感器失效模型。
- STOP->GO 的 release anchor 是 episode 开始后 3s / 7s；它用于固定事件顺序，`stop_confirmed_before_release` 用于识别模型是否满足释放前停车条件。
- 特权 Oracle 不计入算法比较。它若不能安全执行，说明场景或物理参数需要修正。
- MARSHAL 的静态 expected-action 分数不适合直接评价动态 GO->STOP/STOP->GO 序列；主指标是 `rapid_ad_metrics.json` 中的时序与闭环行为指标。
