# Phase 6B 数据语义审计与修正

## 结论

服务器原始报告中 WOMD Scenario 抽样为 PASS，AV2 Motion 抽样因缺少 parquet engine 为 SKIP，因此 Phase 6B **尚未整体验收**。本轮在原有 adapter 合同上修正了以下语义问题，并增加回归测试。修正不改变论文中的车辆动力学或 reachability 数学定义。

## 已发现并修正

1. **AV2 focal track 不等于 SDC。** `focal_track_id` 是运动预测任务的 focal/target agent，可能是车辆、行人或骑行者；它不是自动驾驶车身份。`SceneTrack.is_focal` 与 `is_sdc` 分开。进一步核对官方 `av2-api` visualization 后，确认保留 `track_id == "AV"` 表示 ego vehicle；adapter 现在仅在该 track 存在且 object_type 为 VEHICLE 时标记 `is_sdc=True`，focal 仍独立标记。WOMD 从 `sdc_track_index` 标记 SDC。原服务器报告的 AV2 为 SKIP，因此 `AV` track convention 仍需在 pyarrow 安装后的真实样本中复验。
2. **Parquet bool 不能用 Python truthiness 解析。** `bool("False")` 和 `bool(NaN)` 都会得到 True。AV2 `observed` 现在只接受 bool/NumPy bool 或 0/1，其他值报错。
3. **AV2 时间轴必须尊重官方场景级时间字段。** 优先使用一致的 `start_timestamp`、`end_timestamp`、`num_timestamps`，以精确有理数线性插值重建全局轴；可选逐行 `timestamp_ns` 必须与场景轴一致。只有没有场景级时间字段时才接受完整逐行时间戳；否则明确使用 nominal-rate fallback。非均匀采样不再错误标记为固定 10 Hz。
4. **中心到后轴变换不能留下混合状态却声明全局 rear axle。** 每个被转换的有效位置都必须有 heading；缺失时拒绝转换。可按 `track_ids` 选择适用车辆，未转换的行人/其他车辆继续保持中心参考。场景级参考点在部分转换时标记为 `mixed_center_and_rear_axle`，速度也区分 rear-axle、center-unconverted 和 mixed。
5. **WOMD shard hash 与单条 Scenario hash 分开。** `source_file_sha256` 是整个 TFRecord 分片，`record_sha256` 是单条序列化 protobuf，`scenario_content_sha256` 是规范化解析场景内容。保留旧 `content_sha256` 作为兼容字段，但新报告不再把它解释成唯一的场景内容哈希。
6. **WOMD observed 与 valid 不是同一概念。** `observed` 在该 adapter 中表示数据集的历史/当前时间前缀；`valid` 表示该时刻是否有有效状态。输入掩码必须使用二者的交集。无效历史状态仍可位于观测时间窗内，但不能作为有效运动观测。
7. **验收脚本状态标记修正。** 旧脚本在 summary 为 SKIP 时仍打印 `PHASE6B_LOCAL_PASS`。现在打印 `PHASE6B_STATUS=PASS|SKIP|ERROR`，PASS 返回 0，SKIP 返回 3，ERROR 返回 4，避免自动化流水线误把 SKIP 当通过。

## 参考点数学

若 `o` 是从后轴中心指向框中心的 body-frame 向量，且 `R(psi)` 是平面旋转矩阵，则

\[
p_{rear}=p_{center}-R(\psi)o.
\]

由刚体速度关系

\[
v_{center}=v_{rear}+\dot\psi R(\psi)Jo,
\qquad J=\begin{bmatrix}0&-1\\1&0\end{bmatrix},
\]

得到

\[
v_{rear}=v_{center}-\dot\psi R(\psi)Jo.
\]

代码按此符号实现。缺少 yaw rate 时只转换位置，不伪造 rear-axle velocity。

## 服务器下一步

```bash
conda activate mfrp
cd /home/senzeyu2/code/RAMP-D
pip install -e ".[datasets]"
bash scripts/validate_phase6b.sh
```

如果报告仍为 SKIP，先检查报告中的具体 dependency/path reason；只有 WOMD 和 AV2 都为 PASS，Phase 6B 才能验收。当前没有把服务器目录内容或 AV2 解析成功写成既成事实。

## 原始服务器报告的具体证据

原始 `RAMP-D_Phase6B_server_report.zip` 中 WOMD validation 解析了 3 条 Scenario，`current_time_index=10`，track_count 分别为 14、105、83；三个样本的旧 `content_sha256` 完全相同（`272260d9...`），因为旧字段记录的是同一个 TFRecord shard 的 SHA-256，而不是各条 protobuf record 的 SHA-256。这不是场景重复的证据。新报告分别输出 shard hash、record hash 和 canonical scenario digest。

同一报告中 AV2 明确为 `SKIP: AV2 parquet parsing requires pyarrow or fastparquet`，不是 AV2 数据质量 PASS/FAIL。原报告 16 个 Phase 6B unit tests 通过；当前本地纯 Python Phase 6B/6C-A 定向 harness 为 47 个 tests。服务器仍需安装 parquet engine 后重跑。

### WOMD `objects_of_interest` 字段的官方文档歧义

Waymo Motion overview 页面把 `objects_of_interest` 描述为 tracks 数组索引，但其链接的 `scenario.proto` 定义明确写明该字段是 object IDs，且这些 IDs 对应 `tracks` 中各对象的 `Track.id`。同一 proto 明确把 `tracks_to_predict[].track_index` 和 `sdc_track_index` 定义为数组索引。当前 adapter 按 proto 定义解析 `objects_of_interest` 为 Track.id 并校验存在性；`tracks_to_predict`/`sdc_track_index` 按索引解析。另一个 split 细节也有文档差异：overview 说 validation/test 提供 `tracks_to_predict`，proto 注释说仅 training 作为建议。当前代码采取字段存在即使用、不存在不推断的 fail-closed 策略。
