# Phase 6 计划：先固定数据和时钟合同，再做闭环实验

Phase 6 不会把公开数据集的概率覆盖误当成形式化安全支持。本阶段拆成三轮：

| 子阶段 | 目标 | 依赖 |
|---|---|---|
| 6A | 只读目录/分片清单、统一 `UnifiedScene` 模式、future-leakage 和 digest 回归 | WOMD/AV2 路径；可选 parser 依赖 |
| 6B | 解析 validation 少量场景，完成中心参考点/valid mask/局部地图转换，并记录四时钟注入合同 | 6A 通过；不需要训练 |
| 6C | 固定 validation split 后接入 train、预测 proposal、RuleNet 软排序和 SUMO/CARLA 同步 smoke | 6B 通过；需要用户启动模拟器 |

本轮只完成 6A。`audit_phase6_data.py` 只递归读取目录和文件元数据，不写入数据目录；缺少 `waymo_open_dataset`、`av2`、TensorFlow 或 parquet 依赖时返回 `SKIP`，绝不伪造解析通过。

## 统一场景合同

`SceneManifest` 保存 dataset/version/split/scenario ID/source file、完整原始时间轴、当前时间索引、坐标系、位置参考、未来标签可用性和源 digest。`SceneTrack` 保存稳定的字符串 `track_id`、类别、逐时间 `valid`/`observed` mask 和可选尺寸。WOMD 的 `Track.id` 和 tracks 数组下标由 adapter 显式区分；AV2 的中心参考点会保留为 `bounding_box_center`，不能静默转换成后轴。

`UnifiedScene.online_view()` 只复制到当前时刻的状态，保留原始时间轴到 metadata 中用于审计，设置 `future_available=false`。后续预测输入只能接受这个前缀对象；未来轨迹仅作为监督或离线评估。

## 数据顺序

用户已准备好的路径可以直接用于服务器审计：

```text
/data0/senzeyu2/dataset/waymo_open_dataset_motion_v_1_3_1/uncompressed/scenario
/data0/senzeyu2/dataset/Argoverse2/motion
```

Phase 6A 首先审计 WOMD `scenario/validation` 和 AV2 `Validation`，随后再审计 training；testing 只记录“未来标签不可用”。`training_20s`、`validation_interactive`、AV2 Map Change 暂不作为本轮阻塞项，待 split 去重和任务协议核对后接入。当前不要求重新下载数据，也不要求下载 AV2 Map Change 1–21。

## 时钟边界

WOMD/AV2 轨迹和动态地图状态不提供物理变化、消息发出、消息收到、首次本地观测四个完整事件时钟。6A 不从日志反推这些时间。6B 以后通过协议注入记录：

```text
t_activation, t_issue, t_receipt, t_first_local_observation
```

物理变化时刻不能单独产生 public policy branch；Phase 5 verifier 已加入该回归约束。

## RuleNet 的使用边界

RuleNet 仅作为规则/道路图/优先级的软特征和 branch-ordering 参考。TTC、STL robustness、top-k 或 learned likelihood 不裁掉形式化协议允许的低概率分支，也不升级为 `full_support_certified`。RuleNet 的 INTERACTION/lanelet2 坐标假设不能直接套到 WOMD/AV2。

## 6B/6C 的验收门

1. 每个样本的 source/split/scenario ID 唯一且可重放。
2. 时间戳严格递增，10 Hz 只作为采样元数据，不作为连续安全证明。
3. `valid`/`observed` mask 和缺失状态不被零填充。
4. online view 不含 current index 之后的状态。
5. AV2 center reference、WOMD 尺寸来源和后轴偏移/不确定度均显式记录。
6. SUMO/CARLA 使用固定步长和单一 tick owner；传感器生产帧与送达时间独立记录。

