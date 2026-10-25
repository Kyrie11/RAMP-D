# RAPID-AD v3：阶段 1-3 工程包

**工程名：** RAPID-AD — Recoverability-Aware Plan Invalidation Diagnostics for Autonomous Driving

**本版本目标：** 建立可靠的 MARSHAL/CARLA 运行环境，构建可配对的最小因果场景，区分策略失败与仿真/场景无效，并为 RQ1/RQ2 收集可解释的闭环证据。

> 重要：我在当前环境中只能对代码做静态检查和合成测试，不能连接你服务器上的 CARLA 0.9.15。因此，v3 的 live CARLA 兼容性仍须按下列步骤验证。不要把静态自检通过理解为 CARLA 端到端已经通过。

## 1. 工程路径

- RAPID-AD 代码：`/home/senzeyu2/code/RAPID-AD`
- MARSHAL：`/home/senzeyu2/code/MARSHAL`
- CARLA：`/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15`
- 输出：`/data0/senzeyu2/dataset/RAPID-AD`

先把 ZIP 解压到 `/home/senzeyu2/code`，使目录成为 `/home/senzeyu2/code/RAPID-AD`。不要把代码放在数据目录中。

## 2. v1 运行结果与 v2 审计暴露的问题

请先阅读 [`docs/ENGINEERING_AUDIT.md`](docs/ENGINEERING_AUDIT.md) 和 [`docs/V3_CHANGES_CN.md`](docs/V3_CHANGES_CN.md)。v3 在 v2 基础上又修复了时间窗、缓存有效性和右删失问题。

- v3 `core` 是完整 32-cell/seed 因子设计，覆盖 `none/pre/overlap/post` 四种证据窗口。
- 批量执行默认 fail-fast；每个 episode 保存 stdout/stderr，并在前后检查 CARLA RPC、同步模式、actor 数量及 ego spawn station 是否清空。
- 静态 STOP 不会因为没有 release 而被记为 `stale_retention`；未观察完整 release 后响应窗口的 episode 会被标记为右删失。
- GO->STOP 的 `pre/overlap/post` mask 按事件时间调度并验证实际时间戳，不再把空间距离跨度误当成固定时间延迟。
- `input_mask_realized` 需要真实的缓存替换、无 cache miss、有效时长与正确事件顺序。
- 阶段锚点误差超过阈值的 episode 不进入因果分母；schema-v1/v2 不会进入 v3 交互估计。
- “可恢复”是经过车辆/条件标定后的模型估计，不是物理证明。`core/all` 默认要求 `recoverability_calibrated=true`。
- 新增视觉审计清单与 run-health 汇总；最终因果分析应使用 `--require-visual-audit`。

## 3. 环境变量与 CARLA PythonAPI

在运行 RAPID-AD 的 shell 中设置：

```bash
export CARLA_ROOT=/data0/senzeyu2/dataset/CRADrive/CARLA0.9.15
export MARSHAL_ROOT=/home/senzeyu2/code/MARSHAL
export RAPID_ROOT=/home/senzeyu2/code/RAPID-AD
export RAPID_DATA=/data0/senzeyu2/dataset/RAPID-AD
export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:$RAPID_ROOT:$MARSHAL_ROOT:${PYTHONPATH:-}"
mkdir -p "$RAPID_DATA"
```

确认 Python 版本与 wheel 匹配：

```bash
python --version
ls -lh "$CARLA_ROOT/PythonAPI/carla/dist"
python -c 'import sys; print("cp%d%d" % sys.version_info[:2])'
```

如果 `dist` 中有与 Python ABI 匹配的 `carla-0.9.15-*.egg`，v3 会自动加入导入路径；如果只有不匹配的 egg，则应切换到兼容的 Python 版本，或安装与当前 Python ABI 匹配的 CARLA 0.9.15 wheel。不要安装任意版本的 PyPI `carla` 包来替代服务器对应的 PythonAPI。

安装工程所需的诊断帧/测试依赖：

```bash
python -m pip install -r "$RAPID_ROOT/requirements.txt"
```

CARLA 和 MARSHAL 不通过该 requirements 文件安装；继续使用你已有的 CARLA 0.9.15 与 MARSHAL clone。

### 特别检查 CARLA 路径不一致

v1 日志显示 MARSHAL 从 `/data0/senzeyu2/dataset/CRADrive/CARLA_0.9.15/PythonAPI/carla`（有下划线）加载 agents，但你指定的根目录是 `CARLA0.9.15`（无下划线）。这可能是另一套安装路径，**目前还不能断定它是 RPC 超时根因**。先检查：

```bash
ls -ld "$CARLA_ROOT" /data0/senzeyu2/dataset/CRADrive/CARLA_0.9.15 2>/dev/null || true
python - <<'PY'
import carla, sys
print("carla module:", getattr(carla, "__file__", None))
print("CARLA-related sys.path:")
for p in sys.path:
    if "CARLA" in p or "carla" in p:
        print(" ", p)
PY
grep -RniE 'CARLA_0\.9\.15|CARLA0\.9\.15|PythonAPI/carla' "$MARSHAL_ROOT/marshal_bench/utils/carla_api_compat.py"
```

如果 `carla_api_compat.py` 中有硬编码的另一条 agents 路径，请确认两个目录是同一版本；若不是，应把该路径改为从 `CARLA_ROOT` 环境变量派生。不要盲目替换路径，先确认目录存在且版本匹配。

## 4. 启动干净的 CARLA 服务端

先确认没有其他 CARLA server 正在占用 2000 端口，也没有其他客户端同时 tick 世界。若上一次实验异常退出，建议先正常关闭并重新启动 CARLA，避免残留同步模式或 actor。

```bash
cd "$CARLA_ROOT"
./CarlaUE4.sh -quality-level=Low -RenderOffScreen -nosound -carla-rpc-port=2000
```

服务端先正常启动即可；由 MARSHAL/RAPID-AD 的场景配置加载目标地图。若你已有经过验证的 CARLA 启动命令，可以继续使用它。早期调试用 `Low`，不要先用 `Epic`。

## 5. 阶段 1：复现 MARSHAL 基准并检查 spawn

先查看你本地 clone 实际提供的入口，避免使用不在该版本中的脚本名：

```bash
cd "$MARSHAL_ROOT"
find . -maxdepth 3 -type f \( -name 'start.py' -o -name 'run_marshal_officer_demo.py' -o -name 'run_marshal_sweep.py' \) -print
```

如果存在 `scripts/run_marshal_officer_demo.py`，先运行：

```bash
python scripts/run_marshal_officer_demo.py --help
python scripts/run_marshal_officer_demo.py --scenario flagger_control
```

如果存在 `start.py`，查看帮助后再运行其 Oracle/baseline 入口：

```bash
python start.py --help
```

完整 MARSHAL 场景集可能耗时较长；若当前 clone 提供单场景选项，优先复现 `flagger_control` 的 Oracle/baseline。不要直接执行一个未经 `find` 和 `--help` 确认存在的脚本名。

## 6. 阶段 1：RAPID-AD 预检查

```bash
python "$RAPID_ROOT/scripts/selftest.py"
python "$RAPID_ROOT/scripts/preflight.py" \
  --carla-root "$CARLA_ROOT" \
  --marshal-root "$MARSHAL_ROOT" \
  --host 127.0.0.1 --port 2000
```

预检查会检查：

- CARLA client/server 版本是否一致；
- 当前 world 是否仍遗留 synchronous mode；
- MARSHAL import 是否可用；
- Town03 的配置 spawn station 是否有驾驶 waypoint；
- ego spawn station 附近是否存在残留车辆、walker 或 sensor。

若 `check_spawn.py` 报告附近有动态 actor，先查看其 actor id/type/location。不要直接继续 batch。清理残留 actor 或重启 CARLA，再重新跑 preflight。

## 7. 制动标定：确认“晚期但仍可恢复”确实可恢复

当前早期/晚期动作阶段分别以估计停车余量 5.0 m / 1.5 m 触发。默认减速度 4.5 m/s² 只是占位假设。为了避免把物理不可恢复误判为规划失败，必须先在相同车辆、速度、天气和地图条件下做标定。

确保 spawn station 清空后执行：

```bash
python "$RAPID_ROOT/scripts/calibrate_braking.py" \
  --base-config "$RAPID_ROOT/configs/base_episode.json" \
  --host 127.0.0.1 --port 2000 \
  --target-speed-kmh 12 --repeats 3 --conservatism 0.8 \
  --out "$RAPID_DATA/calibration/braking_calibration.json" \
  --apply-config
```

该脚本会临时切换同步模式、用配置 spawn station 上的车辆加速到目标速度后全制动，测量停止距离，最后尝试恢复原 world settings。上传的 MARSHAL `_common.py` 优先选择 `vehicle.tesla.model3`，标定脚本默认同样使用它；如果你的本地 clone 修改过车辆选择逻辑，必须用 `--vehicle-blueprint` 指定实际使用的 blueprint，并确保 MARSHAL 与标定使用同一车型。检查 JSON 中每次重复的停止距离是否稳定；若三次有效减速度的相对极差超过 20%，脚本会拒绝执行 `--apply-config`，应增加重复次数或排查场景。它是实测的直线全制动估计，不是形式化可达性证明。若脚本无法在固定 spawn station 生成车辆，先修复 spawn/环境问题，不要继续实验。

如果更改车辆 blueprint、天气/摩擦、CARLA 版本或目标速度，重新标定。不要把这次标定推广到所有车辆/天气。

## 8. 安装 RAPID-AD overlay

```bash
python "$RAPID_ROOT/scripts/install_overlay.py" \
  --marshal-root "$MARSHAL_ROOT" \
  --project-root "$RAPID_ROOT"
```

该命令只把 `rapid_ad_factorial_demo.py` 复制到 MARSHAL 场景目录；原始 MARSHAL 场景文件不会被改写。

## 9. 阶段 2/3：先跑一个 Oracle episode

**不要直接跑完整矩阵。** 先只运行第一个场景，确认环境能完整启动、执行和清理：

```bash
export PYTHONPATH="$CARLA_ROOT/PythonAPI/carla:$RAPID_ROOT:$MARSHAL_ROOT:${PYTHONPATH:-}"
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite smoke --seeds 0 \
  --controllers rapid_ad_oracle \
  --max-cases 1 \
  --carla-root "$CARLA_ROOT" \
  --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" \
  --host 127.0.0.1 --port 2000
```

检查输出目录中的：

- `batch_status.json`；
- `health_before.txt`、`health_after.txt`；
- `spawn_before.txt`、`spawn_after.txt`；
- `episode_stdout.log`、`episode_stderr.log`；
- `<episode_id>/rapid_ad_metrics.json`；
- `<episode_id>/rapid_ad_trace.json`；
- `<episode_id>/diagnostic_frames/*.jpg`（少量关键帧（压缩 JPEG），而不是整段图像序列）。

如果出现任何非零返回码、RPC health failure、actor-count drift、spawn 不清空或缺失 metrics，runner 会默认停止。先处理当前失败，再重跑；不要把剩余 cases 的连锁错误混进结果。

### 解释 Oracle 结果

- GO->STOP 动态条件：Oracle 必须在 STOP 有效时不越过控制线，并满足安全余量。
- STOP->GO 动态条件：Oracle 应在合法 release 后恢复行驶。
- 静态 GO/STOP 是 placebo controls；它们不应该被赋予不适用的 stop/resume failure。
- Oracle 读取特权的真实 directive，帧保持不会限制 Oracle 的规则输入；它用于验证场景/物理上界，不是视觉基线。

如果 Oracle 在 late 条件中无法安全停车，先检查制动标定、控制线位置和 transition margin。该场景不能用于证明普通模型的可避免计划撤销失败。

## 10. 阶段 2/3：完整 smoke（单 controller）

一个 controller 一次，便于定位故障：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite smoke --seeds 0 \
  --controllers rapid_ad_oracle \
  --carla-root "$CARLA_ROOT" --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" --host 127.0.0.1 --port 2000
```

Oracle smoke 全部通过后，再分别运行 baseline/PID 参考控制器（它们不理解视觉指挥者，预期不是强模型）：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" --suite smoke --seeds 0 \
  --controllers baseline \
  --carla-root "$CARLA_ROOT" --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" --host 127.0.0.1 --port 2000

# Then run PID in a separate batch so a failure in one controller cannot contaminate the other.
python "$RAPID_ROOT/scripts/run_batch.py" --suite smoke --seeds 0 \
  --controllers pid \
  --carla-root "$CARLA_ROOT" --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" --host 127.0.0.1 --port 2000
```

然后选择 MARSHAL 支持、输入模态已明确的视觉/闭环策略。示例仅适用于本地 Hugging Face 模型：

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite smoke --seeds 0 \
  --controllers vlm --model /path/to/your/local-vlm \
  --query-period-s 0.5 \
  --carla-root "$CARLA_ROOT" --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" --host 127.0.0.1 --port 2000
```

若 MARSHAL VLM 需要远程 API 或自定义 backend，请按其实际 controller API 配置；不要假设本地 Hugging Face 路径能直接使用远程服务。

### 先做视觉审计，不要跳过

每次 smoke 批次完成后，从输出中复制 `RUN_TAG`，生成人工审计清单：

```bash
python "$RAPID_ROOT/scripts/make_visual_audit_manifest.py" \
  --data-root "$RAPID_DATA" --run-tag <RUN_TAG>
```

打开 `analysis/<RUN_TAG>/visual_audit_manifest.csv`，检查 `diagnostic_frames/*.jpg` 并填写 `officer_visible`、`control_line_visible`、`new_directive_visible_in_first_fresh_frame`、`delivered_frame_is_stale_during_mask` 和 `audit_pass`。只有在指挥者/控制线可见、动态切换后的第一张 fresh frame 能辨认新指令、mask 窗口确实传递旧帧时，才把该行的 `audit_pass` 设为 `yes`。若画面不清楚，先修正 actor 位置、手势资产或相机视角，不要继续扩大实验。

另外，可汇总工程故障：

```bash
python "$RAPID_ROOT/scripts/summarize_run_health.py" \
  --data-root "$RAPID_DATA" --run-tag <RUN_TAG>
```

## 11. 阶段 2/3：完整因子矩阵

`core` 是每 seed 32 个条件：GO->STOP 的 16 个条件 + STOP->GO 的 16 个条件。至少先用 1 个 seed 验证工程，再用至少 5 个 seed 做 pilot 分析。

```bash
python "$RAPID_ROOT/scripts/run_batch.py" \
  --suite core --seeds 0,1,2,3,4 \
  --controllers rapid_ad_oracle \
  --base-config "$RAPID_ROOT/configs/base_episode.json" \
  --carla-root "$CARLA_ROOT" --marshal-root "$MARSHAL_ROOT" \
  --data-root "$RAPID_DATA" --host 127.0.0.1 --port 2000
```

`core/all` 默认要求 `scene.recoverability_calibrated=true`。若只是做工程调试，可显式加 `--allow-uncalibrated`，但该批结果不能支持物理可恢复性结论。Oracle 通过后，再分别对 baseline、PID/MPC 和候选视觉模型运行同样矩阵。完整矩阵不要同时启动多个 CARLA client，也不要并行运行多个同步 episode。

## 12. 分析结果

从 `run_batch.py` 的输出中复制实际 `RUN_TAG`：

先生成并填写 `visual_audit_manifest.csv`，再进行最终交互分析：

```bash
python "$RAPID_ROOT/scripts/analyze_results.py" \
  --data-root "$RAPID_DATA" --run-tag <RUN_TAG> \
  --visual-audit-csv "$RAPID_DATA/analysis/<RUN_TAG>/visual_audit_manifest.csv" \
  --require-visual-audit
```

如果还没有完成视觉审计，可以不加上述两个审计参数先看 provisional 汇总，但结果只能用于调试。

输出：

- `analysis/<RUN_TAG>/cell_summary.csv`
- `analysis/<RUN_TAG>/factorial_interactions.csv`
- `analysis/<RUN_TAG>/analysis_metadata.json`

解释规则：

1. 先看 invalid/unexposed episodes；无效 episode 不能作为成功或失败放入分母。
2. 先报告 `unrecoverable_before_evidence`，再报告 evidence 可用且估计仍可恢复时的 `estimated_avoidable_failure`。
3. `decision_action_change_latency_*` 只在 controller 暴露离散决策历史时可用，是外部动作变化代理，不等于内部轨迹缓存真正失效的时间；`speed_drop_latency_*` 与 `command_response_latency_s` 分别代表物理速度响应与控制指令响应。
4. STOP->GO 的 stale retention 只在真实 release 且 release 前 STOP 已成立的 episode 中计算。
5. interaction 表比较每一种 `pre/overlap/post` gap 与 `none` 的配对 seed blocks。少于 5 个完整独立 blocks 会标记 underpowered；这仍是探索性统计，不自动构成因果结论。
6. 运行时推理的 wall-clock 延迟不会在同步 CARLA 中自然转化为 simulation-time 延迟；v3 记录的是模拟时间中的响应/查询间隔。如果论文要研究真实计算延迟，需要后续加入异步动作队列或明确的仿真时间延迟干预。

## 13. 故障处理

### `Failed to spawn ego vehicle at the assigned station`

1. 查看 `episode_stderr.log` 和 `spawn_after.txt`。
2. 如果 spawn station 附近仍有 vehicle/walker/sensor，说明 actor cleanup 或上一次崩溃可能留下残留；清理或重启 CARLA 后重跑 preflight。
3. 如果站点清空仍无法 spawn，检查 Town03、配置坐标/朝向、vehicle blueprint 与 CARLA 版本。不要自动换随机 spawn 点，因为那会改变配对场景几何。

### `time-out ... while waiting for the simulator`

1. 不要继续跑下一批。v3 会 fail-fast。
2. 查看同一 episode 的 stdout/stderr 与 `health_after.txt`。
3. 如果 health check 失败或 world 仍处于 synchronous mode，重启 CARLA server，再从单个 Oracle episode 开始。
4. 若 `returncode=-6`，现在的 stderr 应保存 native/Python abort 前的信息；仍需根据日志判断原因，不能直接归因于算法。

### diagnostic PNG

不需要打包所有 PNG。v3 每个 episode 只保存少量关键帧：首次原始帧、mask 开始时的原始/送入控制器帧、transition 附近的帧、第一张恢复的新帧。调试时优先分享某个 case 的 `diagnostic_frames/`、`rapid_ad_trace.json`、`rapid_ad_metrics.json` 和 stdout/stderr。
