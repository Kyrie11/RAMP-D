# Phase 6C-A 实现报告

## 实现文件

| 文件 | 实现 |
|---|---|
| `python/rampd_core/phase6c.py` | 历史/未来监督拆分、joint mode/observation history、RuleNet Eq. (16)–(20) per-step soft ranker、non-pruning branch ordering、CARLA/SUMO synchrony contract、frame ledger、actor registry、sensor latency record |
| `python/rampd_core/forecast.py` | `ProposalSet` 改为明确记录 `all_emitted_modes_retained`；保留 `complete_modes` 兼容别名；显式 `behavior_support_complete=False` |
| `python/rampd_core/scene_schema.py` | 新增 `SceneTrack.is_focal`，与 `is_sdc` 分离 |
| `python/rampd_core/record_adapters.py` | Phase 6B digest、AV2 bool/time/focal 与官方 `track_id == "AV"` ego 修正、按 track 的中心到后轴转换 |
| `python/rampd_core/protocol.py` / `full_verifier.py` | 修正隐藏 change-before-receipt 分支的保留规则；message receipt 与 local detection 使用独立 public-observation clock |
| `tests/test_phase6c.py` | Phase 6C-A 的数学、数据泄漏、joint-mode、branch ordering 和同步合同测试 |
| `tests/test_phase6c_protocol_regression.py` | 覆盖 change 已发生但 receipt 尚未到达，以及 local detection 早于 message receipt 的边界 |
| `scripts/validate_phase6c_a_dependency_free.py` | 在缺少 native MPFR ABI 的环境下，仅加载纯 Python adapter/Phase 6C 模块做定向测试；不代替完整 native suite |

## 本地验证

执行：

```bash
python scripts/validate_phase6c_a_dependency_free.py
python -m compileall -q python/rampd_core tests
bash -n scripts/validate_phase6b.sh
```

结果：**47 passed**；Python 编译检查通过；Phase 6B shell 脚本语法检查通过。

## 尚未验收

- 当前容器缺少 MPFR development headers/native interval ABI，未运行完整 Phase 0–5 native suite。
- AV2 parquet engine 在用户服务器报告中缺失；未读取服务器真实 AV2 parquet。
- 本轮没有读取服务器上的 WOMD/AV2 数据目录。
- 未启动 SUMO 或 CARLA；未做真实同步 smoke。
- 未训练 QCNet/MTR++/RAMP-D joint predictor。
- RuleNet 模块只实现了明确的软排序数学合同，没有复现 RuleNet 的 GNN/attention 网络，也没有自行推断 longitudinal/lateral frame。
- **地图接入仍不完整：**当前 `SceneForecastSample.encoder_inputs` 只带 map IDs/digest；WOMD adapter 只保存 `map_feature_count` 和 `dynamic_map_states_digest`，AV2 只保存 companion map 文件路径/digest，没有把 lane/crosswalk/road geometry 和 traffic-signal timeline 暴露给模型。因此当前 sample builder 是无泄漏的监督接口，不是可直接训练 QCNet/MTR++ 的完整 map-aware dataset。
- 不产生 `CERTIFIED`、`full_support_certified` 或真实道路安全结论。

因此 Phase 6C-A 的状态是 **local contract tests passed**，不是 Phase 6C 完成，也不覆盖 Phase 6B 的真实数据验收门。
