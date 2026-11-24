# A73 / Phase6C-A59/1b-0S 服务器执行与回传手册

所有路径以新目录为准，原始日志不可覆盖。A73 为数学声明模型、物理响应和证据隔离三个独立门槛，非 SC CERTIFIED。下面实验可以分别完成，但正式监督必须等待依赖齐备。软件门槛失败先修复，不允许绕过。

## 0. 新部署与 Native / Python 全回归

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A59_1b0S
cd /home/senzeyu2/code/RAMP-D_A59_1b0S
unzip -q /path/to/RAMP-D_Phase6C_A59_1b0S.zip
python scripts/verify_release.py
cmake -S . -B build_a73 -DCMAKE_BUILD_TYPE=Release
cmake --build build_a73 -j 4
export A5_NATIVE_BUILD_DIR="$PWD/build_a73"
export RAMPD_INTERVAL_LIB="$PWD/build_a73/librampd_interval.so"
export REPORT_DIR="$PWD/reports/a73_gate_$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/validate_phase6c_a59_1b0s.sh
```

预期：继承 A72 的全部 gate，41+ A73 针对性测试；2 actors × 2 worlds × 2 slabs=8 Native tubes；正例 `CONDITIONAL_DECLARED_NATIVE_MULTI_ACTOR_GEOMETRY_GUARD_SCREEN`，关闭 Guard 反例 `UNKNOWN`。本地缺 MPFR/GMP 开发头文件，以上 Native gate 未在交付环境实际运行。若服务器 configure 失败，使用系统 libmpfr-dev/libgmp-dev 或已有用户安装 prefix，禁止绕过 native backend。回传整个 REPORT_DIR（CTest/JUnit、证书和验收 JSON）。

## 1. 独立复核上传 A72 证据

将三个 A72 zip 内容解压合并到同一新目录（根目录包含 `a72_511ny_auxiliary.jsonl`、`a72_carla/`、`a72_roadwork_real_100/`）。

```bash
python scripts/a73_reaudit_sources.py --results-root /path/to/a72_extracted \
  --output-dir reports/a73_offline_recheck
```

预期 1569 弱记录、21 新隔离（原 1 条缺类型在 A72 隔离文件）；所有 formal masks=0。

## 2. Waymax / WOMD 真实场景门槛（先 5 个）

```bash
WOMD=/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1
python scripts/a72_probe_real_waymax_scenes.py \
 --tf-example-file "$WOMD/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00149-of-00150" \
 --max-scenarios 5 --output reports/a73_waymax_real_5.json
# 先查看实际原始 Scenario shard 路径；手动将 SCENARIO_FILE 设为一个真实 validation 文件
find "$WOMD" -type f -path '*/scenario/*validation*' | head -5
SCENARIO_FILE=/actual/path/to/validation_scenario.tfrecord
python scripts/a73_womd_scenario_inventory.py --scenario-file "$SCENARIO_FILE" \
 --split validation --max-records 5 --output reports/a73_womd_scenario_5.json
```

成功要求 5 个可用记录（若不足 5 则 REVIEW 人工确认），SDC 唯一、有效坐标有限、连续有效状态对存在；Scenario ID/record SHA 无重复，事实数据不得改写。TFExample 128 actor slot 是受限库存，不是完整 roster；local ID 不等于 official Scenario ID。回传两个 JSON（若 REVIEW 也回传），Waymax/JAX/TensorFlow 版本和错误栈。通过后再做 W2 factual model residual、W3 paired intervention、W4 bounded responses；暂不全量 150/1000 shard，不开放 formal joint。

## 3. CARLA 受控 2×3×3 试验

只在你确认的独立 Town06_Opt CARLA 0.9.16 world 中执行，保持独占 tick，禁止其他客户端和 Traffic Manager 干预。所有六格使用新采样，不将历史 fixture 混入三重复；每次重新创建 actor。先验证 dt=.05；随后独立 dt=.025 campaign（不混合）。如果安全门槛或捕获失败，停止检查 raw，不调整参数凑通过。

```bash
RUN=reports/a73_carla_dt005_$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$RUN"
for b in 015 030 045; do
  case "$b" in 015) brake=0.15;; 030) brake=0.30;; 045) brake=0.45;; esac
  for mode in pure combined; do
    mkdir -p "$RUN/${mode}_b${b}"
    for n in 01 02 03; do
      if [ "$mode" = pure ]; then
        opt=(--smoke-maneuver brake --brake-only-fraction "$brake")
      else
        opt=(--smoke-maneuver combined --steer-fraction 0.03 --steer-pulse-s 0.15 --combined-brake-fraction "$brake")
      fi
      python scripts/a60_carla_actor_trials.py --mode smoke --host 127.0.0.1 --port 2000 \
        --blueprint vehicle.tesla.model3 --confirm-isolated-world --confirm-exclusive-tick \
        --site-spacing 2.0 --site-prefer-longest --fixed-delta 0.05 --smoke-speed 5 \
        "${opt[@]}" --output "$RUN/${mode}_b${b}/run${n}.json" || exit 4
    done
  done
done
python scripts/a73_carla_campaign.py --root "$RUN" --dt 0.05 --output "$RUN/review.json"
```

审核每次 control/readback、固定步长/子步设置、道路、初速、原始采样 digest、物理上下文。要求每格≥3有效记录、同一上下文且全组初速范围≤.02 m/s；保守上下文比较可能因原始 wheel pose 或配置变化返回 REVIEW，需查看差异而非直接放宽。行驶中区间两端均≥1m/s，近停/跨阈值、两端≤.01m/s分别统计。即便 18/18 通过也不授权保证制动或真实轮胎耦合。随后复制以上循环到新目录，把 fixed-delta 和审核 dt 改为 .025；不要同时改变摩擦/速度。新增实际 gear、handbrake/reverse、pitch/roll、发动机和变速箱配置；需要独立轮速、接触力/滑移等遥测或明确不可用状态。上传 raw 全矩阵与 review。

## 4. SUMO 逻辑 → 米制抽样（不是共享车道证明）

历史 12-run 继续使用 A72 重放手册。新增单个 baseline smoke；完整旧运行保持不变。

```bash
python scripts/probe_sumo_alternating.py --traffic-profile baseline --seed 17 --steps 9000 \
 --work reports/a73_sumo_metric_work --output reports/a73_sumo_metric_summary.json \
 --metric-samples --require-drain
sha256sum reports/a73_sumo_metric_work/network.xml
```

新产物 metric_actor_trace.jsonl, metric_source.json, network.xml, routes.xml。准备 `resource.json`：`{"network_sha256":"实际 net SHA256","polygon":[[x0,y0],[x1,y1],[x2,y2],[x3,y3]]}`，坐标使用 SUMO net 坐标；顶点必须来自独立地图资源定义，不从测试结果反推。没有权威共享资源多边形时不要编造。仅对声明的可解释区域可作诊断：

```bash
python scripts/a73_review_sumo_metric.py --work reports/a73_sumo_metric_work \
 --resource-json /actual/path/resource.json --output reports/a73_sumo_metric_review.json
```

允许 REVIEW（几何不一致、无非空占用等）。必须回传 work 目录和 resource JSON；下一轮提供同一地理坐标的 OpenDRIVE/SUMO net 对、地图变换、actor registry、固定 tick owner 与真实信号/挡板状态来源。不能以 TraCI getter 作为物理 ACK。

## 5. ROADWork 严格地理分组与 511NY

```bash
python scripts/a73_roadwork_site_split.py \
 --annotations /data0/senzeyu2/dataset/ROADWork/annotations.zip \
 --output-dir reports/a73_roadwork_strict_site
python scripts/a72_roadwork_real_pipeline.py \
 --dataset-root /data0/senzeyu2/dataset/ROADWork --max-templates 100 \
 --output-dir reports/a73_roadwork_visual_retry
```

要求验证图片 GPS 完整；训练缺 GPS 或距验证地点≤100 m 的家族整体隔离；官方 benchmark 不改。回传 audit.json 和少量 manifest、每分割图像/视频/类覆盖率；空结果或 GPS 缺失应 fail closed。严格 split 不是新的官方基准。A73 辅助记录是弱类别训练素材，非已训练模型。511NY 需上传当前 CSV 的字段字典与年份范围、`531`/`2001` codebook、事件稳定 ID（如果存在）。不要再使用 2010–2012 overview 解释所有年份。

## 6. 下一次上传顺序

1. 完整 A73 gate（失败的 stderr / raw 同样保留）。
2. Waymax 两份 5-scene JSON，版本信息。
3. CARLA 18 个 raw + review，以及独立 .025 campaign（若完成），轮速/接触/引擎可用性说明。
4. SUMO metric work 与资源定义、实际共用道路地图文件。
5. ROADWork strict audit、少量原始 manifests、511NY 字段及数字事件码映射。

禁止声明八个正式监督完成。只有完整多车 Post→Guard→公共观察 Succ→接受尾策略/rank→独立验证闭合后，才能开放相关 formal masks。
