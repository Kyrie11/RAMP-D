# Phase 6C-A59/1b-0 — 服务器指令与需上传的证据

**不能覆盖原来的 RAMP-D、A59/1a 或上传的 Town06 原始 27 次数据**。

## A. 编译/回归验证（无现场 CARLA 运行）

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0
unzip -q RAMP-D_Phase6C_A59_1b0.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0
cd /home/senzeyu2/code/RAMP-D_A59_1b0
python scripts/verify_release.py
# 始终使用新构建目录；不要复制原 RAMP-D 中含绝对路径的 CMakeCache.txt
cmake -S . -B build_phase6c_a59_1b0 -DCMAKE_BUILD_TYPE=Release
cmake --build build_phase6c_a59_1b0 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_phase6c_a59_1b0"
bash scripts/validate_phase6c_a59_1b0.sh
```

依赖旧阶段验收、A61 15 项专项（包含未来接收消息不能提前区分控制、异步 actor 位姿不滞后的回归）、至少 740 项全量 pytest，不能出现 skipped/failed；当前新工程未在你服务器上运行过，门槛是预期，不是现存服务器结论。报告目录在 `reports/phase6c_a59_1b0_*`。

## B. 对旧的 27 组 CARLA 原始日志直接审计（无需启动 CARLA）

```bash
python scripts/a61_review_physical_evidence.py \
  --input /path/to/a59_1a_carla/model3_town06_27.json \
  --output reports/carla_a61/town06_original_a61_review.json \
  --repeats 3
python scripts/a61_review_physical_evidence.py \
  --input /path/to/a59_1a_carla/model3_actor_metadata.json \
  --output reports/carla_a61/town10_actor_geometry_review.json
```

两条命令只读原始文件，不改变车辆元数据或已有报告。检查 `status`、`actor_geometry`、`groups`、`reasons`。18/27 完整数据仍只算部分样本。不能拿 `max_brake_torque` 和 27m/s² 峰值作保证减速度。

## C. 可选：同 Town06 另起一个明确标注的低幅转向试验

只有独立 CARLA 服务端、无其他 actor/Traffic Manager/sensor、确认只有本进程 tick 时才运行。保留 **原大幅激励** 的 REVIEW 日志，不要覆盖。

```bash
python scripts/a60_carla_actor_trials.py \
  --mode trials --host 127.0.0.1 --port 2000 \
  --blueprint vehicle.tesla.model3 \
  --confirm-isolated-world --confirm-exclusive-tick \
  --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 \
  --steer-fraction 0.03 --steer-pulse-s 0.15 \
  --repeats 1 \
  --output reports/carla_a61/model3_town06_shortpulse_smoke.json
```

`0.03` 是 CARLA 归一化转向指令而非 0.03 rad；这与原始 0.08/0.8s 是**不同激励协议**，不能混合做相同工况 6 次重现，也不能声称测量最大转角边界。离开行车道仍然保留 REVIEW；不通过时请停止重复大幅转向并检查地图边界/试验场地设计，勿直接忽略车辆离路状态。

如果 9 组 smoke 都是 CAPTURED，才在不同文件中用相同短脉冲参数作 `--repeats 3`，之后分别执行两个 review 脚本：

```bash
python scripts/a60_review_carla_logs.py \
  --input reports/carla_a61/model3_town06_shortpulse_27.json \
  --output reports/carla_a61/model3_town06_shortpulse_review.json --repeats 3
python scripts/a61_review_physical_evidence.py \
  --input reports/carla_a61/model3_town06_shortpulse_27.json \
  --output reports/carla_a61/model3_town06_shortpulse_a61_diagnostics.json --repeats 3
```

注意第二阶段命令的输入必须是用 `--repeats 3` 实际生成的新日志；上面只是审核命令，不会自动发起试验。

## D. 优先补充材料（最少三类）

1. **本轮正式验收目录** `reports/phase6c_a59_1b0_*/`；其次，新版 `model3_town06_shortpulse*.json` 及 review，尤其要包含实际 wheel angles、map SHA、weather、同步 actor 元数据和 control histories。
2. **真实物理参数标定所需**：车型 blueprint 是否修改、车辆 physicsControl 快照、路面摩擦触发器/湿干路面配置、测量方差工况/seed、如能获得轮胎侧偏/滑移与 brake actuator command-to-response 记录。没有路面独立物理来源则只能声明 simulator-specific nominal model。
3. **继续并行模块**：SUMO A58 九份新工作目录产生的全套 `*.json`、`vehicle_trace.jsonl`、`roster_trace.jsonl`、`sumo.log`；Waymax 官方真实 WOMD（非合成）弯道路段/sim-agent 诊断输出；若有准备真实 co-sim，再给同源 OpenDRIVE 校验值、地图坐标对应表和 actor/tls 控制权记录。

无需再重复上传标准车型尺寸或整套 AV2/WOMD 大体量数据。511NY/ROADWork 只需提供可靠的事件发布/实际生效/设备部署原始记录（如已有），不能凭外部事件报表反推物理生效时刻。
