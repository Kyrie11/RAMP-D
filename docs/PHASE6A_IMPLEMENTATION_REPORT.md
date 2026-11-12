# Phase 6A 工程实现报告

## 目标

本轮先建立真实数据接入前不可绕过的基础合同：统一场景模式、只读 split/文件审计、未来信息隔离、稳定 digest 和缺依赖时的显式 `SKIP`。

## 实现

| 文件 | 内容 |
|---|---|
| `python/rampd_core/scene_schema.py` | `SceneManifest`、`TrackState`、`SceneTrack`、`UnifiedScene` 及严格时间轴/ID/mask 校验；`online_view()` 删除未来状态；canonical SHA-256 digest。 |
| `python/rampd_core/dataset_audit.py` | WOMD TFRecord shard 与 AV2 parquet/map JSON 的大小写不敏感 split 发现、候选文件统计、元数据 manifest digest、地图配对检查、可选依赖探测和 `SKIP`/`ERROR` 状态。 |
| `scripts/audit_phase6_data.py` | JSON 配置驱动的只读审计命令；默认打印报告，可用 `--output` 保存报告，`--strict` 将非 PASS 作为失败。 |
| `tests/test_phase6_data_audit.py` | schema digest、future leakage、WOMD shard glob、AV2 split/map pairing、缺路径 skip 和只读不写回归。 |
| `docs/PHASE6_PLAN.md` | 6A/6B/6C 边界、数据顺序、时钟和 RuleNet 约束。 |

这轮没有引入 TensorFlow、Waymo、AV2、CARLA 或 SUMO 作为核心依赖；真实记录解析将在 6B 以可选 adapter 进入。Phase 6A 的 `manifest_digest` 是相对路径、文件大小和类型的元数据摘要，不冒充源文件内容 SHA-256；6B 对实际抽样记录读取时再补内容 hash。

