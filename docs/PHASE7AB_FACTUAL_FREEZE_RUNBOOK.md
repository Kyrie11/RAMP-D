# RAMP-D 1.0.0.dev0：事实基础冻结 / 动态资源监督续阶段

## 1. 部署和依赖

解压到新目录，不覆盖历史结果。PyTorch 环境继续使用 mfrp；`--strict-route` 和二维投影检查需要 Shapely。Native 需要真正的 MPFR/GMP 开发依赖；不能替代为普通浮点。

```bash
conda activate mfrp
python scripts/verify_release.py
bash scripts/validate_learning_pilot.sh
bash scripts/validate_cleanup_regression.sh
```

## 2. 冻结基础事实模型（不需要重复本轮六组训练）

保留 `--motion-context --local-history --objective radial_laplace --modes 3 --selection nll`。CV 初始化、20 epochs、batch size 4、seed 7/17/27。六组原报告同 manifest 和 summary hash；本次未上传新缓存，需在服务器重新核验。报告的原 99 场景已成为开发集，不是最终测试。三种子完整报告全部保留，不以 seed 17 代替其他种子。

```bash
C=/actual/path/to/factual_500_freshdev
for seed in 7 17 27; do
  python scripts/audit_factual_checkpoint.py --cache "$C" --run /actual/path/to/local_radial_${seed} --output reports/local_${seed}_extended_audit.json
done
python scripts/diagnose_motion_state.py --cache "$C" --output reports/motion_state_fresh_recheck.json
```

新 audit 额外报告 DCA、模式均值启动/减速投票（非完整密度事件概率），不能把未来真值或未来有效性作为模型输入。需要上传 manifest.json、summary.json（无需上传全部缓存）、以上 audit。保留原训练/开发记录并在未查看的新官方验证 shard 上冻结最终测试家族；单独检查旧诊断/开发/测试的原始记录哈希、ID、位置、道路家族；如无法证明驾驶片段和地图完全隔离，缩小论文主张。当前 `prepare_factual_dataset.py --fresh-validation` 只排除 base manifest 当前 validation；**不能反复调用它就声称排除了所有历史诊断集**。先比较所有历史清单后方可作为正式测试。正式测试不得用于参数/模型选择。

## 3. 可选的最后一组模式评分消融（不是后续动态监督阻塞项）

同一开发缓存、固定 architecture/seed/epoch；先运行 seed 17，只有真实改善再扩展其余种子。

```bash
for w in 0.1 0.5; do
  python scripts/train_factual.py --cache "$C" --output "reports/local_modeq_${w}" \
    --motion-context --local-history --objective radial_laplace --selection nll \
    --modes 3 --epochs 20 --batch-size 4 --seed 17 --mode-quality-weight "$w" \
    --mode-quality-temperature 0.2 --device cuda
  python scripts/audit_factual_checkpoint.py --cache "$C" --run "reports/local_modeq_${w}" --output "reports/local_modeq_${w}_audit.json"
done
```

已有 seed17、w=0 报告可对照；最好同环境复验。质量损失脱离轨迹目标梯度，但 logits 的共享 Encoder 梯度依然存在；近似相同模式不学习伪分类。新损失是研究消融，不是原联合 NLL 的替换，也不宣称概率校准。检查 mode_quality_active_batches，若为0不能称已比较有效辅助监督。

冻结轨迹生成器的独立几何排序可用新的配置：

```bash
python scripts/train_mode_ranker.py --cache "$C" --output reports/ranker_factual_local \
  --base-local-factual --rank-features motion --base-epochs 20 --rank-epochs 60 --calibration-families 80
```

这个命令重新从训练划分拆分互斥 base / inner selection / calibration；不能直接比较全量493模型的几何性能（训练量不同），只在相同冻结候选集合内比较原排序与新排序。原上传 ranker_motion 是旧 10 场景实验。若无明显提升，冻结排序器为可选诊断。

## 4. 动态规则对照与分字段证据

```bash
python scripts/run_rule_response.py --manifest "$C/manifest.json" --extend-route --prepend-route --strict-route \
  --recipient-policy route_equipped --clock-profile no_ego_delivery --reaction-delay 0.3 \
  --visual-range 25 --limit 50 --steps 60 --plots --output reports/route_equipped
python scripts/export_projected_evidence.py --pairs reports/route_equipped/pairs.jsonl \
  --output reports/route_equipped_evidence_v2.jsonl --geometry-output reports/route_equipped_geometry.jsonl
```

`route_equipped` 用固定 seed 7、声明概率 .5 的相关路线车辆装备队列；不是现实设备渗透率。可使用 `--pair-input /actual/path/to/response_nominal/pairs.jsonl` 复用同初态，且不能同时指定 extend/prepend/profile 非 nominal。strict-route 核查几何账本而非原始拓扑。`--physical-on`/`--physical-off` 必须成对设置且指定 visual range；做只改变法律时钟的实验时应固定物理窗口，不可自动同步。

Evidence v2 将事件/送达存在性与条件时间分开；明确不送达的条件 receipt mask 关闭。旧 v1 不再当作新时钟监督。所有纵向证据仍 evaluation-only。

## 5. 双向共享资源（本地已实际运行的声明 2D 模型）

```bash
python scripts/run_shared_resource_pilot.py --families 8 --train-heads --output reports/shared_resource_pilot
```

输出 24 条运行、3,816 条时序标签、三个独立权重和 summary；6 train spacing families / 2 validation spacing families。仅 declared affine model，非 SUMO/CARLA/Native，头模型只能在该域训练。当前 Event 是下一步交通驱动命令类，不是完整外生事件；Observation 是下一步已确认通行许可类，None 表示无确认许可，不等于实物红灯。Occupancy 是下一帧矩形接触；连续扫掠另存，不能混成采样标签。对照常数和公共持久状态，报告变化子集，不能只看总体准确率。原始数据不可混入事实 cache。模拟器适配需用真实独立设备读回、完整 roster、唯一 tick owner、实际扫掠或保守区间；不得将 ideal mock ACK 当真实 ACK。

下一步服务器真实 SUMO/CARLA：使用同源 Town06_Opt map，先核对地图 hash/地标/坐标参考；明确实际共享 polygon、两个方向中心路径均落入同一物理区；用适配器给 `SharedResourceController.step` 提供每 actor 真实接触/未知以及上一步连续空区间证据，读取对应 command version 的真实 ACK；记录真值、车辆可见信号和消息分别；无法验证时拒绝放行，不准通过逻辑双车道代替真实共享区域。首个完整交替放行场景通过后再扩展至限速和 STOP/SLOW。`Notice` 已定义类型化 payload、更新和取消的收报逻辑，尚未与旧纵向控制器和真实设备联动。

## 6. Native gate 独立执行

```bash
cmake -S . -B build_native -DCMAKE_BUILD_TYPE=Release
cmake --build build_native -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_native"
export RAMPD_INTERVAL_LIB="$PWD/build_native/librampd_interval.so"
bash scripts/validate_native_regression.sh
ctest --test-dir build_native --output-on-failure
```

本地 CMake 缺 MPFR/GMP 开发文件，Native/SC 未验收。提交输出；学习和有限声明模型测试不能替代。

## 7. 回传最小集合

- P0：新缓存 manifest、summary、3 份扩展 audit；可选模式消融 report/audit。
- P0：shared_resource_pilot/summary.json（只需小报告），如出现失败再上传对应 run。
- P0：新规则 summary、evidence v2、geometry（含拒绝原因），原始 20 组已复核不需重复上传。
- P1：同源地图实际配准、控制器/设施读回和 SUMO/CARLA 运行记录。
- P1：Native CTest 和完整 gate。
