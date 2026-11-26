# A75 服务器指令（新目录，不覆盖旧证据）

## 1. 先执行未回传的 Native gate
```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A75
cd /home/senzeyu2/code/RAMP-D_A75
unzip -q /path/to/RAMP-D_Phase6C_A59_1b0U.zip
python scripts/verify_release.py
cmake -S . -B build_a75 -DCMAKE_BUILD_TYPE=Release
cmake --build build_a75 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a75"
export RAMPD_INTERVAL_LIB="$PWD/build_a75/librampd_interval.so"
bash scripts/validate_phase6c_a75.sh
```
预期继承A74 gate、80 targeted、SC rank regression；`a75_acceptance.json` 仍 full_sc_certified=false。必须回传完整 reports 目录/失败日志，不只是PASS截图。若 native 缺依赖按 CMake 提示安装 libmpfr-dev libgmp-dev 或设置可信自建 prefix。

## 2. Phase7A 事实监督小批量（先 validation，再独立 train）
```bash
python scripts/a75_export_factual.py --inventory /path/to/a74_scenario_inventory.json --output reports/a75_factual_validation.jsonl
W=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1
find "$W/uncompressed/scenario/training" -type f | head -5
# 指向真实 training shard，不能使用 validation 或 tf_example；每次先限制5-50。
SC_TRAIN=/actual/training/scenario_shard
python scripts/a73_womd_scenario_inventory.py --scenario-file "$SC_TRAIN" --split training --max-records 50 --output reports/a75_train_inventory.json
python scripts/a75_export_factual.py --inventory reports/a75_train_inventory.json /path/to/a74_scenario_inventory.json --output reports/a75_factual_candidate.jsonl
```
若缺 independent split manifest，training_allowed=false（候选导出不是训练授权）。独立从原始 train/val shards 审计生成按 scenario_id 映射 `{source_digest, split}` 的全局 manifest，另查同原始场景重叠窗口；通过后使用 `--split-manifest /path/to/manifest.json`。当前仅 factual path surrogate，未实现完整地图 encoder/训练器。验证本轮已有1708 future knots。

## 3. Waymax 真实配对（仅小规模，修改报告身份与ADE）
```bash
TF="$W/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00149-of-00150"
python scripts/a74_waymax_real_pair.py --tf-example-file "$TF" --max-scenarios 5 --steps 30 --output reports/a75_waymax_pair_30.json
```
不要把无效静止干预判为真正因果零。若出现 actor invalid，保留 REVIEW；之后筛选真实交互风险而非只筛选响应大的结果；为学习响应记录官方 scenario/track IDs、路由先验和每tick action，训练/验证分开。当前 baseline future route privileged。

## 4. CARLA 最小步长辨识（而非继续阈值扫描）
固定 dt=.05、速度5m/s、brake=.30，独立改变 max_substep_delta=.01/.005，固定道路、天气、actor配置，记录相同触发速度/轮速/gear、真实 substep 计数（如可用）；再 .025 外部dt对照。现有API仅记录设置，不自动知道实际子步数。不要在真实道路做这些试验。
```bash
export RAMPD_CARLA_TELEMETRY=1
for sub in 0.01 0.005; do
 python scripts/a60_carla_actor_trials.py --mode smoke --host 127.0.0.1 --port 2000 --blueprint vehicle.tesla.model3 --confirm-isolated-world --confirm-exclusive-tick --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 --max-substep-delta "$sub" --max-substeps 10 --smoke-speed 5 --smoke-maneuver brake --brake-only-fraction .30 --output "reports/a75_carla/b030_sub${sub}.json"
done
```
不能宣称较小dt一定物理正确；若仍不稳定，冻结论文的声明模型，CARLA作为 stress-test/观测生成域，不再把根因研究当Phase7门槛。下一批需转向阶跃、速度/附着和有限独立验证；并非本轮必做全量。

## 5. 共享资源所需地图证据（只读导出）
在独占 CARLA 服务器：
```bash
mkdir -p reports/a75_map
python - <<'PY'
from pathlib import Path
import carla,hashlib
c=carla.Client('127.0.0.1',2000);c.set_timeout(10)
w=c.get_world();m=w.get_map();x=m.to_opendrive();p=Path('reports/a75_map/town.xodr')
with p.open('x') as f:f.write(x)
print(m.name,c.get_server_version(),hashlib.sha256(p.read_bytes()).hexdigest())
PY
netconvert --opendrive-files reports/a75_map/town.xodr --output-file reports/a75_map/town.net.xml
```
这是同源地图起点，不是共享施工区已完成。后续选择具体施工资源，检查参考点、lane mapping、镜像/offset、实际路径和独占 tick owner。提供 map pair 和期望资源 lane IDs，不需重复当前9000 tick双strip。

## 6. 离线复验（可选，不重启模拟器）
```bash
python scripts/a75_reaudit.py --carla-zip /path/to/a74_carla.zip --waymax-pair /path/to/a74_waymax_pair.json --inventory /path/to/a74_scenario_inventory.json --format /path/to/a74_scenario_format.json --output-dir reports/a75_recheck
python scripts/a75_sumo_sampled_labels.py --work /path/to/a73_sumo_metric_work --prior-rows /path/to/a74_sumo_replay/sampled_occupancy.jsonl --output-dir reports/a75_sumo_sampled
```
回传优先：完整 Native gate、train/val split manifest smoke、Waymax 新配对身份和有效性、XODR/net；物理只需最小substep对照和源码/遥测单位说明。其他ROADWork/511NY本轮不用重跑。
