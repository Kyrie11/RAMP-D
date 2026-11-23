# Phase 6C A59/1b-0O — 服务器运行手册

## A. 独立新目录部署

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0O
unzip -q RAMP-D_Phase6C_A59_1b0O.zip -d /home/senzeyu2/code/RAMP-D_A59_1b0O
cd /home/senzeyu2/code/RAMP-D_A59_1b0O
cmake -S . -B build_a59_1b0o -DCMAKE_BUILD_TYPE=Release
cmake --build build_a59_1b0o -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a59_1b0o"
export RAMPD_INTERVAL_LIB="$A5_NATIVE_BUILD_DIR/librampd_interval.so"
python scripts/verify_release.py
bash scripts/validate_phase6c_a59_1b0o.sh
```

目标：全仓 >=909 测试，A69 >=34 测试，C++ CTest 3/3，零 skipped/failed/errors；本轮测试不启动 CARLA/SUMO。仅在所有 JUnit 报告明确通过时软件验收有效。

## B. CARLA 原始三次重复数据的独立复算

```bash
python scripts/a69_review_three_tracks.py \
  --repeat '1=/path/to/combined_repeat1.json' \
  --repeat '2=/path/to/combined_repeat2.json' \
  --repeat '3=/path/to/combined_repeat3.json' \
  --output reports/a69_carla_three_repeats.json
```

将输出文件设置为一个从未使用的新路径，脚本拒绝覆盖。现有三次固定 0.45 日志应报告重复性诊断通过，但缺少 0.15、0.30、0.45 三档，故分档必须 REVIEW。

## C. CARLA 5 m/s 三档单因素试验

**只在独立 CARLA 0.9.16 Town06 服务器，没有其他同步 tick 客户端、Traffic Manager 控制或实验时执行；脚本会生成自有车辆并改变世界同步设置。** 每档使用唯一输出文件，不覆盖历史原始日志。

```bash
mkdir -p reports/a69_carla_factor
for level in 0.15 0.30 0.45; do
  python scripts/a60_carla_actor_trials.py \
    --mode smoke --host 127.0.0.1 --port 2000 \
    --blueprint vehicle.tesla.model3 \
    --confirm-isolated-world --confirm-exclusive-tick \
    --site-spacing 2.0 --site-prefer-longest \
    --fixed-delta 0.05 --smoke-speed 5 --smoke-maneuver combined \
    --steer-fraction 0.03 --steer-pulse-s 0.15 \
    --combined-brake-fraction "$level" \
    --output "reports/a69_carla_factor/combined_b${level}.json" || break
done
```

三档完成后（诊断比较，不是标定证书）：

```bash
python scripts/a69_review_three_tracks.py \
 --brake-arm 'b15=reports/a69_carla_factor/combined_b0.15.json' \
 --brake-arm 'b30=reports/a69_carla_factor/combined_b0.30.json' \
 --brake-arm 'b45=reports/a69_carla_factor/combined_b0.45.json' \
 --output reports/a69_carla_factor/brake_sweep_review.json
```

同名文件已存在时必须另用新目录。若一档失败，保留原始错误，不强行重复覆盖。需要进行三个水平下每档三次重复时，所有输出均需新文件名，后续调用 `--brake-arm` 九次；检查物理配置、天气、地图选点完全相同。

重要：仿真天气包括湿度、湿地水膜等参数，不得仅改变轮胎摩擦同时更换地图、天气或激励配置。`brake=0.15` 是新的声明协议，不应与旧 0.45 重复直接混入同水平统计。三档若峰值仍约 27 m/s²，下一步需检查制动轮扭矩、手刹、引擎制动、PhysicsControl 差异、接触力和数值求解参数，不要据峰值宣称真实车制动力。

## D. 其他并行上传

- **数学**：真正 Native Picard 每片输入、完整 tube 输出、MPFR 上下界和任何重放反例；无需等待 CARLA。
- **SUMO/Traffic/Guard**：旧九组覆盖错误在全新目录重跑的控制 JSON、车辆原始轨迹、信号控制器命令/生效/ACK 时间、路网 `.net.xml` 与资源冲突几何。
- **Waymax**：离散状态/动作转换、日志 vs IDM 响应、一致物理参考点与时间步长的测试结果；不得拿合成 IDM 当全行为支持。
- **CARLA/SUMO**：共同地图的配准、唯一控制权、时钟与车辆 ID 映射证明；Town06 标定地图不等于已经存在 co-sim 地图。
- **真实事件**：511NY 报告时钟来源、施工几何数据的可用坐标精度；ROADWork 图片 bbox 仅作辅助，不可作为物理几何证书。
- **监督**：样本的稳定 `scenario_id` 和分割、来源角色、时间戳、原始文件 SHA；当前 **8 项 formal mask 均为零**。
