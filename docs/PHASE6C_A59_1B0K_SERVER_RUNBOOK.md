# A59/1b-0K 服务端复测指令

## 1. 全新发布包、本地 + native 回归

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0K
unzip -q RAMP-D_Phase6C_A59_1b0K.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0K
cd /home/senzeyu2/code/RAMP-D_A59_1b0K
cmake -S . -B build_a59_1b0k -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0k -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0k"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
bash scripts/validate_phase6c_a59_1b0k.sh
```

严格预期 784 个 pytest 至少通过，原生 CTest 3/3、0 skip/failed/errors。若服务器依赖版本导致多用例失败，保留 stdout/JUnit；不能删除或忽略用例。

## 2. 在原始 5m/s 制动记录上作独立一致性检查

```bash
mkdir -p reports/a65_carla
python scripts/a65_review_carla_conformance.py \
  --input /path/to/town06_5ms_brake_raw.json \
  --output reports/a65_carla/brake_conformance_review.json
# 这里返回代码 4 / REVIEW 是 **正确发现**，不是脚本软件损坏。
python scripts/a65_plot_carla_smoke.py \
  --input /path/to/town06_5ms_brake_raw.json \
  --output reports/a65_carla/brake_response.png
python scripts/a65_plot_carla_lane.py \
  --input /path/to/town06_5ms_brake_raw.json \
  --output reports/a65_carla/brake_lane_topdown.png
```

## 3. CARLA 0.9.16 Town06，限定环境小幅转向实验

**仅在 CARLA 服务器无其他 tick 客户端、无 Traffic Manager 或其他同时仿真任务，确认独占后运行。**

```bash
python scripts/a60_carla_actor_trials.py \
  --mode smoke --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --smoke-speed 5 --smoke-maneuver steer \
  --steer-fraction 0.03 --steer-pulse-s 0.15 \
  --output reports/a65_carla/town06_5ms_steer_shortpulse_raw.json
python scripts/a64_review_carla_smoke.py \
  --input reports/a65_carla/town06_5ms_steer_shortpulse_raw.json \
  --output reports/a65_carla/town06_5ms_steer_shortpulse_review.json
python scripts/a65_plot_carla_lane.py \
  --input reports/a65_carla/town06_5ms_steer_shortpulse_raw.json \
  --output reports/a65_carla/town06_5ms_steer_shortpulse_lane.png
```

若 `CAPTURED`，再同参数、独立文件执行 `--smoke-maneuver combined`。若 `REVIEW_OFF_DRIVABLE_LANE`，勿覆盖日志，也不要放松车道裕度，先分析图像与完整时钟。旧激励 `0.08/0.8s` 与新激励 `0.03/0.15s` 不可合并统计。

## 4. 需归档与提交

完整服务器验收目录及 JUnit、5m/s 制动 JSON + A65 REVIEW、短脉冲 steer/combined 的原始 JSON/独立 REVIEW/俯视 PNG。若存在道路异常，建议加同步鸟瞰视频及 OpenDRIVE/actor wheel 接触或碰撞日志。SUMO 9 条缺失报告及 map `.net.xml` / CARLA `.xodr` 同样需保留。实测或专家判断不可替代原始证据。
