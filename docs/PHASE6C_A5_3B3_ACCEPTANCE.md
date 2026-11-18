# Phase 6C-A5/3b-3 · 审计、实现与验收

## 1. 输入和基线

- 用户上传 A5/3b-2 release 0.9.7，服务器报告 `phase6c_a5_3b2_20261118T022421Z.zip`：3 native、29 finite、141 data/protocol、149 math、566 all pytest，无失败或跳过。范围为显式分支时间表和声明有界 actor 的任务图。
- 最新 TeX 与包内 manuscript SHA256 完全相同：`0d9b8e50fd8c0f8aaa89f9979b33c6905211b9f16ed5caa6e388be1d3ca76621`。本轮不修改论文。
- AV2 单个真实双精度端点场景 PASS，current index 49，0–10.9 s。全部四个 split 各 60 个场景通过。240 场景、391244 有效 actor-time knots，全部 factual path surrogate；AV2 车型尺寸与信号监督缺失。报告中无抽样跨 split ID/hash 重复。这不是全量验收。
- 旧 Waymax 报告 10→11 通过，仅日志回放（128×91，924 个有效点，SDC ID 666）。本轮未运行真实 Waymax/WOSAC。WZDx 43 feed / 2373 flattened Texas rows，四类验证标志全部 false，无 Feature ID，不生成正式事件真值。

## 2. 实现目标和数学审计

| 范围 | 结果 |
|---|---|
| E1 exact endpoint/subslab | 保留已验收 MPFR 公式，连续时间切换边界不可遗漏 |
| E2 absolute time/actor inheritance | 保留源 atom 传播和后验覆盖；消息有限 partition 单独准备，未接入 A53Mission |
| E3 resource | 新增 incumbent/no-new-entry 充分条件；容量必须是严格整数；其余仍保守 |
| E4 data | 服务器已验证 double 修复；加固抽样 gate 每条可用，独立审计图不再把 AV2 signal 缺失画成 0 |

`a53b_occupancy.py`: 对静态闭矩形资源，若整个 swept AABB 严格在内，则没有新进入；或者起始 AABB 严格在内、航向恒定且参考点的两个坐标分别单调时，对每个刚体物质点，其两个坐标处于矩形范围的时刻是初始时间前缀，交集仍是前缀；所有点的并仍是前缀，故无 exit/re-entry。仅在原生回放后的共同 subslab 使用；不会依据两个采样端点推断 occupancy history。起点是严格内部时，相对本规划时域是 incumbent，不声称验证了此前历史。所有可能占用都继续要求 beta、方向、容量和冲突条件。无法证实（包括边界接触、部分重叠、非单调或转弯）时 UNKNOWN 或更保守的 alpha/beta 检查。当前方案尚不是任意 polygon、连续 entry/exit 根隔离或完整 protected exit 定理。

`a53b_event_clock.py`: 单次连续未知切换 q∈[l,h]：t<l 用旧规则，l≤t<h 取旧/新权限交集、最小容量及共同方向，t≥h 用新规则。可构造既有 PermissionSchedule；对每个 admissible q 逐点保守，不假设 ego 获得该时钟。仅单资源单次切换，不推导 guard 或相关联合分支。有限消息 hypotheses 的明确观测 partition 按公开 receipt 及 payload，不在 silence 泄露隐藏 issue/未来 receipt。未发布、丢包、未送达可能共存；公开精确 receipt 时间为模型假设。未集成完整协议/观测/在线 SC。

`a53b_interlock.py`: 原来同 event/version/resource 可替换 effective window/authority/condition 而不重新对账；现绑定外生请求完整 signature，命令 ID 也包含资源。真实部署、清空和 settled ACK 仍需 simulator registry/独立 evidence adapter；BLOCKED 表示已确认过部署，不保证障碍永远存在。`a53b_alternating.py`: 新的 reference controller 需要作用域一致的覆盖闭区间 clearance，不用连续两个 zero counts 代替。其 DRAIN 是保守 gate，未实现黄灯、dilemma zone、报警、冲突监控及 Part 4 完整规定。旧 reference 保留用于回归，不能给真值证明。

`a53b_ttc.py`: 核对上传 MUTCD 6B-2/3/4。新增 table sight distance，1-lane-2-way/downstream taper 50–100 ft=15.24–30.48m；merging/shifting/shoulder guidance 区分，不将规范建议变成 universally legal/safe。无表值则拒绝插值。工程设计仍需 speed source, ODD, jurisdiction 与具体 TA。

`probe_waymax.py`: valid mask、有效历史字段 x/y/yaw/vel_x/vel_y/length/width 的复制等值检查，以及 sim future mask 检查。真实 API 已按官方文档对照，仍待服务器运行。`audit_supervision_quality.py`: 要求真实 PASS status + scope + flags；空记录拒绝。图不再标 AV2 missing；信号缺失不画零。

`audit_roadwork.py`: 不解压 9GB 图像，ZIP central-directory 唯一索引；选官方 train/val gps_split，检查 COCO-like IDs、图名存在、bbox extent、类别与共现计数、相对 bbox 面积、抽样图像/labelIds 尺寸及原图 bbox 可视化；不推断 metric geometry 或 formal rule clocks。所有全量元数据只按单个 split family 统计；按图像文件名检测直接交集，不保证地理 100m。仅合成 ZIP fixture 已运行，真实三份 ZIP 待服务器。本轮不修改/借用真实训练验证分割。

## 3. 实际测试结果

- 154 isolated dataset/protocol/controller/quality/fixture tests PASS；包括新增 ROADWork 合成 ZIP 和 Waymax NumPy replay fixture。首次运行 1 fail: 测试错用字符串而非单元素 tuple `('SILENCE',)` 查字典；已修复测试并重跑。
- 29 finite/gate/exact time tests PASS。
- 13 discrete SC tests PASS（无连续数学保证）。
- 240 uploaded scenario inventory quality audit = BOUNDED_INVENTORY_PASS；新真实报告图、JSON 在交付外部文件中。未生成 proof/simulator labels。
- C++/MPFR native 回归在本地不可执行：系统只有 libmpfr6 4.2.2 runtime，无 dev header/library symlink，官方 Debian 包尝试下载因 DNS/访问限制失败。不用替代/伪造头文件或 float 后端。新增 4 个 native occupancy 测试保留在必跑 gate 中；服务器全量回归最低 566，不可有失败或 skip。

## 4. 服务器命令

```bash
conda activate mfrp
python -m pip install -r requirements-test.txt
python scripts/verify_release.py
bash scripts/validate_phase6c_a5_3b3.sh
```

ROADWork 不需解压：
```bash
python scripts/audit_roadwork.py --root /data0/senzeyu2/dataset/ROADWork --samples-per-split 6 --output reports/a5_3b3_roadwork.json --plot reports/a5_3b3_roadwork.png
```
真实 Waymax：
```bash
python scripts/probe_waymax.py --tf-example-file /data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00000-of-00150 --output reports/waymax_a5_3b3_probe.json --plot reports/waymax_a5_3b3_logged.png
```
若脚本报告 ERROR/REVIEW_REQUIRED，请上传 JSON，真实 API/数据路径不能通过忽略错误或修改证书门禁解决。本轮不需要运行 CARLA/SUMO。AV2 基线数据接口未改，不必重跑全量数据；新增 inventory gate 可用以前的 report 复现。

## 5. 保证界限及下一阶段

本轮完成受限 occupancy 证明、单次不确定规则时钟、有限消息分组、施工报告绑定、新交替通行 reference、真实数据 inventory 和 ROADWork probe。新连续物理回放尚未原生验收；未证明真实模型支持完备、真实任务尾、完整消息/观测 support、完整 SC 在线策略、真实标签生成或训练。下一步：验证 native，独立物理 clearance provider，跨 slab incumbent/exit 继承及 protected exit，真实 guard/消息 queue/观测关系接入 A53Mission，随后独立 finite teacher 与 simulator event logging。不要把证书 UNKNOWN 标为负样本。
