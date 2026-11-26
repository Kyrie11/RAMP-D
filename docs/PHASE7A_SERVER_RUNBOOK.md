# Phase7A 服务器执行手册（1.0.0.dev0 同一开发分支）

建议每次发布解压到新目录避免覆盖历史日志；后续修改同名模块，不增 A76/A77 实现。下面命令使用现有 mfrp 环境。需要 PyTorch、NumPy、TensorFlow、waymo_open_dataset（保留目前已能解析 Scenario 的版本）。不建议为本轮升级 JAX/TensorFlow/Waymax。若 Torch 缺失，按服务器 CUDA/CPU 情况安装匹配版本；`pip install -e '.[learning,test]'` 仅在确认依赖方案后使用。训练不要求 MPFR。

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_v1_pilot
cd /home/senzeyu2/code/RAMP-D_v1_pilot
unzip -q /path/to/RAMP-D_v1.0.0-dev_phase7a.zip
python scripts/verify_release.py
python -c 'import torch,numpy,tensorflow; from waymo_open_dataset.protos import scenario_pb2; print(torch.__version__,numpy.__version__,tensorflow.__version__)'
bash scripts/validate_learning_pilot.sh
bash scripts/validate_cleanup_regression.sh
```

## A. 数据 5+5（只生成紧凑 cache）
```bash
W=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
python scripts/prepare_factual_dataset.py --scenario-root "$W" --train-limit 5 --validation-limit 5 --max-shards 2 --horizon 10 --output reports/factual_pilot
```
读取两次原始记录是为了身份绑定；默认 5+5，输出每场景一行，无需 170 MB inventory。首次请回传 `manifest.json` 和 `summary.json`，不要求回传 cache 的全部 JSONL。缺乏真实训练原始数据本地未实跑此命令。验收两个划分均非空、身份不重叠、拒绝原因可解释；如果出错上传完整 traceback 和路径目录列表（不用上传整个数据）。

## B. 单场景过拟合与解耦检查
```bash
python scripts/train_factual.py --cache reports/factual_pilot --output reports/factual_overfit --overfit-one --modes 1 --epochs 50 --lr 0.003 --device cpu
python scripts/train_factual.py --cache reports/factual_pilot --output reports/factual_frozen --freeze-encoder --modes 1 --epochs 15 --device cpu
python scripts/train_factual.py --cache reports/factual_pilot --output reports/factual_k1 --modes 1 --epochs 20 --device cpu
python scripts/train_factual.py --cache reports/factual_pilot --output reports/factual_k3 --modes 3 --epochs 20 --device cpu
```
先单场景能学习，再冻结 encoder 与正常 K1 对比，最后 K3；失败先检查梯度、目标数量、CV 及 mask，不要求 5 个 validation 上 SOTA。每次 output 必须不存在。回传四份 `training_report.json`（包含所有 epoch、校验/梯度和重载结果），权重先留服务器。没有训练数据时不要复用 validation 训练。

## C. 扩展真实训练 pilot（A/B 通过后）
```bash
python scripts/prepare_factual_dataset.py --scenario-root "$W" --train-limit 50 --validation-limit 10 --max-shards 5 --horizon 30 --output reports/factual_3s
python scripts/train_factual.py --cache reports/factual_3s --output reports/factual_3s_k3 --modes 3 --epochs 20 --batch-size 4 --device cpu
```
GPU 可显式 `--device cuda`；保留相同种子，GPU 数值复现不承诺严格逐位一致。以上仅是 pilot，1000/split 限制；正式大规模 DataLoader/sharding 后续实现，不要生成巨大 inventory。

## D. 动态规则 sidecar
查看 `reports/factual_pilot/summary.json` 中 accepted 的 scenario_id、decision_time_s、lane_candidates。下面示例使用第一个训练场景及 lane 候选，时钟是 scenario 秒。假设 decision time 约 1 s，实际时间以 summary 为准，确保 effectivity 与日志时间窗相交。
```bash
read SID LANE < <(python - <<'PY'
import json
s=json.load(open('reports/factual_pilot/summary.json'))
r=next(r for r in s['accepted'] if r['split']=='training' and r['lane_candidates'])
print(r['scenario_id'],r['lane_candidates'][0])
PY
)
python scripts/check_rule_overlay.py --manifest reports/factual_pilot/manifest.json --scenario-id "$SID" --lane-id "$LANE" --kind LANE_CLOSURE --generation 0.4 --on 0.8 --off 10 --issue 0.6 --receipt 1.5 --announce-window --output reports/rule_overlay_example.json
```
预计当前时刻未收到消息，public_at_cutoff 空，teacher_active 可能为真，all_training_masks=false。off=10 超过典型 9s 窗口，保留而非截断。这里不是执行施工仿真，不能拿未改变的 WOMD 真值作为干预后响应监督。第二个示例把 receipt 改成 0.7（提前通知），第三个省略 receipt（无送达记录）；分别使用不同输出文件。

## E. 并行 Native gate（不阻塞 A/B）
```bash
cmake -S . -B build_native -DCMAKE_BUILD_TYPE=Release
cmake --build build_native -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_native"
export RAMPD_INTERVAL_LIB="$PWD/build_native/librampd_interval.so"
bash scripts/validate_native_regression.sh
ctest --test-dir build_native --output-on-failure
```
缺开发包则按系统安装 libmpfr-dev libgmp-dev 或使用用户 prefix `-DCMAKE_PREFIX_PATH=...`，绝不使用普通浮点替代。回传 gate 的完整输出目录及 CTest，当前条件性 gate 通过也不代表 G1 完整 SC。

## F. 并行同源地图
用上轮 Town06_Opt 的 xodr 和 net XML 路径（无需重新导出）。
```bash
python scripts/check_cosim_map.py --xodr /actual/town.xodr --net /actual/town.net.xml --output reports/cosim_map_inventory.json
```
如可人工/程序匹配真实路段锚点，准备 JSON 包含 `xodr_sha256`, `sumo_net_sha256`, `points`: [{"id":"unique","split":"fit" or "holdout","carla_xy":[x,y],"sumo_xy":[x,y]}, ...]。至少各三点非共线，不能复用地点；同一实际物理点，不是两侧车道的任意最近点。然后使用 `--landmarks /path/landmarks.json --tolerance-m 0.5`，输出另一个新文件。只验收坐标配准残差，不认证共享资源。下一轮完成真实 lane matching/资源几何以及联合步进。无需再做 CARLA 制动阈值扫描。

## 最小回传
P0: 两份测试日志/JUnit、factual_pilot/manifest.json 和 summary.json、overfit/frozen/K1/K3 的 training_report.json、rule_overlay_example.json；如果 C 已执行，另附 3 秒 summary 和训练报告。P1: Native gate 全目录、CTest、cosim map inventory 和可用的独立 landmark JSON/结果。不要上传全量 WOMD 或大 inventory；训练 checkpoint 暂存服务器。没有实际场景训练结果前不解锁其余七项损失。
