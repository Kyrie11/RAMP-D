# Phase 6A 验收报告

## 目标与边界

Phase 6A 只验收数据目录和统一场景合同。它不声称已解析真实场景、不训练预测模型、不生成安全证书，也不启动 CARLA/SUMO。

## 本地结果

```text
Phase 4 protocol/full regression + Phase 5 CEGAR + Phase 6A tests: 35 passed
Full historical-plus-new Python suite with temporary local MPFR bootstrap: 318 passed, 18 pre-existing directed-rounding/backend failures
```

35 项专项测试覆盖：

- 统一场景 canonical digest 可重复；
- `online_view()` 截断 current index 之后的状态并保留 mask；
- 非递增时间轴、重复 track ID 等输入 fail-closed；
- WOMD `.tfrecord` 和 `.tfrecord-*` 分片识别；
- AV2 `Train/Validation/Test` 大小写目录识别和 parquet/map JSON 不配对报告；
- 缺少数据路径或可选 reader 时明确 `SKIP`，不伪造 PASS；
- 只读审计不会修改数据目录；
- Phase 5 registry/queue/旧 verifier digest 不匹配时拒绝继续；
- 没有 receipt/local clock 的 silence 分支保持 `UNKNOWN`。

Phase 6A 的 manifest digest 只绑定路径、文件类型和大小，不能替代源文件内容 hash；对无效轨迹状态允许使用 `None` 保留缺失 mask，不能以零填充制造观测。6B 会用服务器实际 AV2 manifest 核对 map archive 是否被多个场景共享，并对抽样记录增加内容 hash。

历史全量的 18 个 interval/MPFR 失败与本轮无关，均来自本地没有官方 MPFR development headers、使用临时 declaration-only bootstrap 的环境差异；目标服务器必须重新运行官方 native CTest 和 Python gate。

## 服务器命令

将工程放在服务器后，在 `mfrp` 环境中执行：

```bash
cd /home/senzeyu2/code/RAMP-D
export PYTHONPATH="$PWD/python${PYTHONPATH:+:$PYTHONPATH}"
python scripts/audit_phase6_data.py \
  --config configs/data_sources.example.json \
  --output reports/phase6a_dataset_audit.json
```

确认报告中的 WOMD `validation` 和 AV2 `Validation` 均已找到候选文件；由于本轮配置仍是文档示例，若目录大小写或根路径不同，应先修改 config 中的路径并重跑。`--strict` 只在确认 optional reader 依赖已经安装后使用：

```bash
python scripts/audit_phase6_data.py \
  --config configs/data_sources.example.json --strict
```

这一步不需要重新下载用户已经准备好的 WOMD Scenario train/validation/testing 和 AV2 Motion Train/Validation/Test，也不需要启动 CARLA 0.9.16 或 SUMO 1.20。

