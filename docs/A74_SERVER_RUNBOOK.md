# A74 / Phase6C-A59/1b-0T 服务器运行手册

按顺序执行，每个输出目录均为新目录；不要改旧日志。以下命令未在本地实际 simulator 环境运行。

## 1. fresh Native gate（优先）
```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0T
cd /home/senzeyu2/code/RAMP-D_A59_1b0T
unzip -q /path/to/RAMP-D_Phase6C_A59_1b0T.zip
python scripts/verify_release.py
cmake -S . -B build_a74 -DCMAKE_BUILD_TYPE=Release
cmake --build build_a74 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a74"
export RAMPD_INTERVAL_LIB="$PWD/build_a74/librampd_interval.so"
bash scripts/validate_phase6c_a59_1b0t.sh
```
预期：继承 gate、55 targeted（41+14）；Native multi 8片，positive CONDITIONAL，closed_guard UNKNOWN，public_post CONDITIONAL_DECLARED_NATIVE_POST_SUPPORT，missing_posterior_atom UNKNOWN。`full_sc_certified=false`。

## 2. WOMD 先查实际文件格式，再读 Scenario
```bash
W=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1
find "$W" -type f -path '*/scenario/*validation*' | head -10
# 将 SC 替换为上面实际 Scenario validation shard，不能选 tf_example
SC=/actual/path/to/scenario_validation_shard
python scripts/a74_womd_format_probe.py --file "$SC" --max-records 5 --output reports/a74_scenario_format.json
python scripts/a73_womd_scenario_inventory.py --scenario-file "$SC" --split validation --max-records 5 --output reports/a74_scenario_inventory.json
TF="$W/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00149-of-00150"
python scripts/a74_waymax_real_pair.py --tf-example-file "$TF" --max-scenarios 5 --steps 10 --output reports/a74_waymax_pair.json
```
格式错误时保留 REVIEW，停止该分支；若实际 gzip 文件需确认原 adapter 的解压支持。模型对照非真实反事实；未来路线仅离线模型用。AA一致、其他车首步不受未来动作影响、有效 actor 未消失，逐场景分析 ADE 和 AB。

## 3. 离线证据重放（可不启动仿真）
```bash
python scripts/a74_carla_reaudit.py --root /path/to/a73_carla_dt005_20261125T004319Z --dt .05 --output reports/a74_carla_review.json
python scripts/a74_sumo_replay.py --work /path/to/a73_sumo_metric_work --output-dir reports/a74_sumo_replay
python scripts/a74_roadwork_bind_split.py --strict /path/to/a73_roadwork_strict_site --templates /path/to/a73_roadwork_visual_retry/roadwork_templates.jsonl --output-dir reports/a74_roadwork_bound
```
预期 18/17、9000 ticks 两方向覆盖且 A-only 负例被拒、65/4 visual。不是正式授权。

## 4. CARLA 下一组最小辨识
在独占 Town06_Opt 同一车辆/天气/位置/设置，先补一次 .15 pure，复现 readback 异常；再 .18/.21/.24/.27 分辨阈值；对 .15/.30 两档做 0.025s 对照。示例：
```bash
export RAMPD_CARLA_TELEMETRY=1
for b in 0.15 0.18 0.21 0.24 0.27 0.30; do
 python scripts/a60_carla_actor_trials.py --mode smoke --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 --confirm-isolated-world --confirm-exclusive-tick --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 --smoke-speed 5 --smoke-maneuver brake --brake-only-fraction "$b" --output "reports/a74_carla/pure_${b}_dt005_run01.json"
done
for b in 0.15 0.30; do
 python scripts/a60_carla_actor_trials.py --mode smoke --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 --confirm-isolated-world --confirm-exclusive-tick --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.025 --smoke-speed 5 --smoke-maneuver brake --brake-only-fraction "$b" --output "reports/a74_carla/pure_${b}_dt0025_run01.json"
done
```
先确认 telemetry 字段/单位、实际 substeps、控制/速度差分、接触；若 telemetry API 不可用保留错误。不得由这些样本直接设置保证制动下界。后续才变更单因素：子步、速度、附着、转向。共享资源 co-sim 需提供实际 OpenDRIVE+SUMO net，当前双strip实验不能替代。

## 5. 回传
完整 gate report、Scenario format+inventory、Waymax pair、CARLA 新原始日志及 build/physics 配置、共享路网文件（如有）。ROADWork 与 SUMO A73 离线重放本轮已完成，无需重复上传同一源。
