# 服务器执行手册（同一 1.0.0.dev0）
在新目录解压，不覆盖旧 checkpoint。`python scripts/verify_release.py`；`bash scripts/validate_learning_pilot.sh`；`bash scripts/validate_cleanup_regression.sh`。

## 1. 不必重新生成 200 场景
```bash
conda activate mfrp
C=/actual/path/to/factual_200_fixedval
python scripts/audit_motion_baselines.py --cache "$C" --output reports/motion_baselines.json
for seed in 7 17 27; do
  for fam in gaussian radial_laplace; do
    python scripts/train_factual.py --cache "$C" --output "reports/motion_${fam}_${seed}" --motion-context --modes 3 --epochs 20 --batch-size 4 --seed "$seed" --objective "$fam" --selection nll --device cuda
    python scripts/audit_factual_checkpoint.py --cache "$C" --run "reports/motion_${fam}_${seed}" --output "reports/motion_${fam}_${seed}_audit.json"
  done
done
```
若没有 CUDA，改 cpu。按资源先执行 seed7；不要同时改变其他变量。`--soft-gate`、`--query-modes` 为独立消融；不默认启用。Gaussian 的 NLL 不能与 radial NLL 直接比较。保留旧十个场景仅作为诊断集；下一轮增加独立验证规模，并保留所有旧场景身份，正式最终 test 不参与选择。当前 base-manifest 扩展接口固定验证清单，故新 dev split 需独立清单而非把原 test 混入。预注册 500–1000 train、至少 100 dev，多个 seed，重复场景隔离；不要求立刻 SOTA。

## 2. 独立几何排序器（可选，非训练概率头）
```bash
python scripts/train_mode_ranker.py --cache "$C" --output reports/mode_ranker --base-epochs 3 --rank-epochs 60 --calibration-families 40
```
先验概率不变，排序对象为 3 个完整共同模式与一个 CV proposal。训练划分内部按场景隔离；原 10 val 不参与梯度及选择。验收：无泄漏、输出有限、校准训练 loss 下降、报告几何排序/Top1/CV/oracle、绝不跨 actor 选模式。若仍不胜 CV 不必立即加复杂排序器。

## 3. 原始地图拓扑 + 动态规则时钟
```bash
for profile in nominal early delayed_effect late_receipt no_ego_delivery; do
  python scripts/run_rule_response.py --manifest "$C/manifest.json" --extend-route --clock-profile "$profile" --limit 50 --steps 60 --plots --output "reports/route_${profile}"
  # For an accepted run only; no formal training authorization.
  python scripts/export_projected_evidence.py --pairs "reports/route_${profile}/pairs.jsonl" --output "reports/route_${profile}_evidence.jsonl"
done
```
同一 manifest、同一真实初态、不同声明时钟，不是 5 个独立真实样本。先看 nominal 的 summary/pairs 与 BEV/弧长图。接受 0 会退出 4，保留失败记录。候选线路唯一后继，禁止未来 logged route 选择，不允许凭空延长。必须检查 A/AA 同一、A/B 外生一致、完整 6 s、截断、排除 roster、规则违例、实际和计划时钟、无接收/迟到。完整资源 geometry 与物理设施尚待。生成新 sidecar：
```bash
python scripts/prepare_rule_scenarios.py --manifest "$C/manifest.json" --split validation --limit 5 --clock-profile delayed_effect --plots --output reports/rule_delayed
```
缓存方式使用完整提案收件人：`python scripts/run_rule_response.py --cache "$C" --proposals reports/rule_delayed/rule_scenarios.jsonl --limit 5 --steps 60 --plots --output reports/cache_bound`。缺 roster 拒绝，不能填补。旧三收件人提案需要重新生成。仅 raw 支持 `--extend-route`。

## 4. Native 独立 gate
```bash
cmake -S . -B build_native -DCMAKE_BUILD_TYPE=Release
cmake --build build_native -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_native"
export RAMPD_INTERVAL_LIB="$PWD/build_native/librampd_interval.so"
bash scripts/validate_native_regression.sh
ctest --test-dir build_native --output-on-failure
```
上传：学习/历史回归日志、训练报告和 audit、motion_baselines、排序报告（可选）、各 route summary、少量代表性 pairs 和图、native gate。无需大 inventory 或全部视频。下一轮优先扩大事实泛化证据与共享真实资源执行，正式 Event 头仅在可靠的多样 protocol label 及独立数据合同后开启；数学 Teacher 并行。 
