# Phase 6C-A59/1b-0H：CARLA 预控制有效性与混合 Post 义务账本

## 实际实验证据（用户上传的 2026-11-23 Town06 短脉冲）

- `town06_shortpulse_smoke.json`：9 次尝试，0 次触发控制；9 次均为 `REVIEW_APPROACH_OFF_DRIVABLE_LANE`，仅 1 帧、`trigger_frame=-1`。
- 首帧竖直速度 -0.49 或 -0.98 m/s；竖直加速度近似 -9.8 m/s²，车辆尚可能处于物理落地瞬态。
- 第一份 CARLA actor 轮位 z≈0.783 m，半径 0.37 m，基于 Town06 选中道路 z≈0m 的候选轮底高度约 0.413m，不能将其当作贴地有效控制数据。
- 旧试验使用三维速度 `sqrt(vx²+vy²+vz²)` 作为目标速度，现增加 `planar_speed_mps` 用于触发并保留三维速度用于诊断。

## 本轮变更

1. `scripts/a60_carla_actor_trials.py`：`--mode readiness`（显式世界独占确认）预检查；生成后独立同步 tick，不再在出生后立刻驱动；每组 `drive_trial` 先等待至少 5 个稳定高度帧，并检查轮底与道路高程近似关系。
2. `python/rampd_core/a62_carla_readiness.py`：水平速度、矩形路宽约束、轮位单位与道路高度代理检查；所有结果 **仅为描述性**。
3. `scripts/a62_review_carla_readiness.py`：不连接 CARLA 的原始日志独立拒绝入口，绝不生成动力学标定或训练标签。
4. `python/rampd_core/a62_hybrid_obligation_ledger.py`：对隐藏世界×原子时间片构造 Native Tube、权限、资源、观测和 SC 尾策略义务账本；同公共历史下控制必须一致；没有独立重放的证明不得提升为 `CERTIFIED`。
5. `scripts/validate_phase6c_a59_1b0h.sh`：专项/全量/native 回归、旧失败日志负例以及机器可读验收报告。

## 权限/物理边界

- `map.get_waypoint(...,project_to_road=True)` **只是投影**：追加完整 bbox 的道路横向范围判定，不把投影成功等同于实际可驶。
- 轮底高度与道路高度是近似接地代理，不是轮胎接触力传感器、最大制动或摩擦下界。5 连续稳定帧仅排除明显自由落体，不能认证真实长期稳定性。
- CARLA 同步 tick 独占只由用户与本地锁声明，不能发现所有远程客户端；该脚本不能用作共仿真桥接。
- M2/M5/M6/M7/M8/M10 尚需完整分段 Native 物理 Post、版本化动态 Guard、资源拓扑/连续占用、隐藏后继及接受终端策略。
- Waymax 控制 `a,κ` 不直接等同 RAMP-D `j,ωδ`；SUMO 的逻辑资源与真实几何资源分开；511NY/ROADWork 不产生自车收报真值。
- 所有 M13 viability/margin/deadline 标签为禁用；收到完整正式证书并独立验证后才可解除掩码。

## 服务端执行顺序

```bash
conda activate mfrp
cd /home/senzeyu2/code/RAMP-D_A59_1b0H
cmake -S . -B build_a59_1b0h -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0h -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0h"
export A62_PREVIOUS_SMOKE_JSON=/path/to/town06_shortpulse_smoke.json
bash scripts/validate_phase6c_a59_1b0h.sh
```

**先做唯一一次就绪前检查，不执行 27 组：**

```bash
mkdir -p reports/carla_a62
python scripts/a60_carla_actor_trials.py \
  --mode readiness --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --output reports/carla_a62/town06_readiness.json
python scripts/a62_review_carla_readiness.py \
  --input reports/carla_a62/town06_readiness.json \
  --output reports/carla_a62/town06_readiness_review.json
```

只有 `DESCRIPTIVE_PRETRIAL_READY_NOT_CALIBRATED` 且轮底道路高程代理通过，才能进行新 1-repeat 短脉冲 smoke，**不要直接重试 27 组**：

```bash
python scripts/a60_carla_actor_trials.py \
  --mode trials --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --steer-fraction 0.03 --steer-pulse-s 0.15 --repeats 1 \
  --output reports/carla_a62/town06_shortpulse_repeat1.json
python scripts/a62_review_carla_readiness.py \
  --input reports/carla_a62/town06_shortpulse_repeat1.json \
  --output reports/carla_a62/town06_shortpulse_repeat1_review.json
```

每个不同协议的日志必须保存 `steer_fraction`、`steer_pulse_s`、天气、OpenDRIVE SHA、蓝图、physics、actor ID、同步帧和命令响应，不混合训练。

## 下一阶段 A59/1b-1 实现验收范围

1. 原子时间片每个隐藏世界的 Native MPFR/Picard endpoint/tube 可重放；从 `[t_i,t_{i+1}]` 到下一片保证终点外包络包含。
2. 模型时刻处理 rule effective、通信 issue/receipt、signal command/ACK，声明真实发生证据域；禁止未来可知信息影响前片控制。
3. 动态 Guard 应以控制器内存、版本、进入/持续/退出许可、方向/容量、冲突图为具体状态，不只是抽象 bool。
4. 一般多边形资源和全车身连续 swept footprint；不能证明资源分离则 `UNKNOWN`。
5. 汇合后按公共观测同类合并后继；核对终端任务接受集合和 rank 递减，不得将 safety-only 代替任务完成。
6. 数据监督：8 heads 逐个持有来源 ID、作用域、失效 mask、时钟证据及完整验收报告。任何候选策略失败不生成 viability 负标签。
