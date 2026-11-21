# Phase 6C-A5/3b-8 — 服务器验收、后续顺序和输入请求

## A. 安全安装（不要覆盖上一轮工程）

```bash
conda activate mfrp
mkdir -p /home/senzeyu2/code/RAMP-D_A58
unzip -q RAMP-D_Phase6C_A5_3b8.zip -d /home/senzeyu2/code/RAMP-D_A58
cd /home/senzeyu2/code/RAMP-D_A58
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b8.sh
```

生成完整报告目录在 `reports/phase6c_a5_3b8_...`；A57 子门禁将全部重新运行，不依赖旧编译缓存。`CMake` 需要 MPFR/GMP 和原有 Python 3.10。新的 679 项最低阈值包含19项纯参考和6项原生门禁及1项 interlock 反例修复。若完整数值门禁失败，停止向下生成正式标签。

## B. 验证新 SUMO Guard 的鲁棒性（无头）

```bash
mkdir -p reports/a58
for profile in baseline dense slow_reaction lower_friction_proxy; do
  for seed in 17 23 41; do
    python scripts/probe_sumo_alternating.py \
      --traffic-profile "$profile" \
      --work "reports/a58/sumo_${profile}_${seed}" \
      --steps 9000 --seed "$seed" \
      --stop-reserve-guard --reaction-s 0.5 --extra-stop-m 1.0 \
      --max-green-extension-s 20 --require-drain --require-comfort \
      --output "reports/a58/sumo_${profile}_${seed}.json" \
      --plot "reports/a58/sumo_${profile}_${seed}.png" || true
  done
done
```

`|| true` 只用于保证失败结果不丢失；**不代表验收通过**。密集流/长反应/低附着等模型参数为压力设定，不是真实参数标定。“仅改随机种子”在 sigma=speedDev=0 的 baseline 中不产生不同驾驶行为。对于资源通行检验，保持进入、车尾清空、到达的车辆ID一一对应，检查红灯侵入、强制动以及下游车道是否排满。多档失败后优先引入黄灯 dilemma zone 的 stop/go 允许集合和真实出口阻塞模型，而不是延长绿灯至任意时间。

分组审计命令（逐 profile）：

```bash
PYTHONPATH=python python - <<'PY'
import json
from pathlib import Path
from rampd_core.a58_sumo_audit import audit_runs
for p in ('baseline','dense','slow_reaction','lower_friction_proxy'):
 paths=[Path(f'reports/a58/sumo_{p}_{s}.json') for s in (17,23,41)]
 try:r=audit_runs(paths)
 except Exception as ex:r={'status':'REVIEW','error':str(ex)}
 out=Path(f'reports/a58/audit_{p}.json');out.write_text(json.dumps(r,indent=2)+'\n')
 print(p,r['status'])
PY
```

若原生 MPFR 动态库尚未编译，可以临时运行纯审计脚本，不能运行数学验证门禁的假通过。

## C. Waymax / 验证模型误差

在 A57 30/60/120 实测的基础上，新增建议（不把代码中已有直线定值实验当作全覆盖）：

1. 固定每个干预初始条件，采样 120/240/480 点检查 gap 收敛是否足以控制期望加速度偏差；检查官方内部 `lead_distance` 的不同 leader、路点和 lane context。
2. 用从 WOMD Scenario 转换的曲线路线比较离散投影与弧长投影，再用真正有方向的多车 footprint 生成独立接触区间。
3. 分别进行步长0.1/0.05/0.025的“同一个加速度函数下积分”对照；禁止把优化行为模型参数造成的响应改变归结为积分误差。
4. 区分行为模型参数标定误差、路线/净间距估计误差、真实司机间干预响应分布不确定性。尚没有证明 IDM 对真实未观测反事实的统计覆盖，应从多次风格参数、WOMD observed hold-out 和额外模型族中建立外包络。

## D. ROADWork 场景模板（无需 MPFR）

```bash
python scripts/export_a58_roadwork_templates.py \
  --annotations /path/to/annotations.zip \
  --split train --max-templates 1000 \
  --output reports/a58/roadwork_train_templates.jsonl
```

字段保留原图完整对象清单、属性和多标签场景类别、来源组；不填充虚构米制位置、信号权限、开始/结束时间。先用 CARLA/SUMO 地图和施工事件管理机构机制生成3D场景及规则，再提供形式化Teacher证书。

## E. CARLA/SUMO 只读准备；不执行 actor 同步与部署

```bash
# 仅当你的 CARLA 0.9.16 server 在同步模式已启动，且 SUMO 网络/路由文件存在：
python scripts/probe_a58_cosim_readonly.py \
  --carla-host 127.0.0.1 --carla-port 2000 \
  --sumo-network reports/a58/sumo_baseline_17/network.xml \
  --sumo-routes reports/a58/sumo_baseline_17/routes.xml \
  --step 0.1 --output reports/a58/cosim_preflight.json || true

# 读取 CARLA actor 几何和物理信息：不设置 throttle/steer/brake：
python scripts/dump_a58_carla_vehicle_params.py \
  --carla-host 127.0.0.1 --carla-port 2000 \
  --output reports/a58/carla_vehicle_params_raw.json
```

上面的文件名对应当前 SUMO 构建约定，若实际 `--work` 目录生成名不同，先用 `find reports/a58/sumo_baseline_17 -maxdepth 2 -type f` 核对，不能推测道路参考坐标正确。只读采集中的 wheel position/半径量纲、bounding box 和 actor origin 需要对照 CARLA 0.9.16 官方/实际 API 再用于标定。不得将 bounding-box 中心直接视作 CG 或后轴中心。

## F. 需要的验收产物

上传 `reports/phase6c_a5_3b8_*/` 验收 ZIP、`reports/a58` SUMO12组 JSON + Work/trace/警告日志、Waymax 若做曲线路线试验则带官方内部诊断 JSON、CARLA/SUMO preflight JSON 和只读车辆参数 JSON。**只在实验新数据完成后**对那些模块升级状态。

## G. 之后阶段顺序

1. A58 本轮核对完整数学安全检查，仅能条件性 `EGO_AVOIDANCE_PASS`。
2. A59：将 Native Physical Post 加入非预见性 SC + rank/终端尾策略、资源入口/停留/出口可行性及观测消息覆盖，并做小规模精确 oracle 独立对照。
3. A5/3c-1：CARLA0.9.16/SUMO1.20 同步、坐标和朝向、车辆身份及控制权；物理共享车道/出口可用性。
4. A5/3c-2：封闭实际 actor 部署/撤除、管理授权、障碍物碰撞盒/监控盲区与保守故障处理。
5. A5/3c-3：四类突发事件，ROADWork场景模板/511NY报告生命周期机制、观测和受控反事实。
6. A5/4：完整联合支持、稳定任务终端证书和形式化Teacher，再进入REA/RuleNet与ICAPS系统性实验。

理论资料优先：CARLA目标车辆 blueprint 与 WheelPhysicsControl API 用例/后轴测量、SUMO Krauss/IDM 和黄灯决策官方参数、IDM/MOBIL原论文、FHWA 交通信号黄灯及 all-red 指南。没有要求额外下载 National Highways。
