# 2026-11-16 六份 Phase 6B 实验包复核

来源：用户本轮提供的六个 `phase6b_20261116T*.zip`，每个包实际包含 pytest XML/log，**没有附带真实数据解析 summary/场景审计**。

| 包名时间戳 (UTC) | 观察 | 判定 |
|---|---|---|
| 090428Z | 系统错误地调用 Python 2.7 pytest | 测试收集失败，不是数据失败 |
| 090436Z | C++/MPFR native dynamic library 不能加载 | 测试收集失败 |
| 090501Z | 同一个 native ABI 加载问题 | 测试收集失败 |
| 090535Z | 同一个 native ABI 加载问题 | 测试收集失败 |
| 090612Z | 25 passed / 1 failed，AV2 Parquet mock 使 pandas import 访问缺失的 `pyarrow.__version__` | 单元测试替身隔离失败；真实 reader 未被验证 |
| 090733Z | 25 passed / 1 failed，仍是同一个 mock issue | 同上 |

工程 ZIP 中的 `tests/test_phase6b_record_adapters.py` 已具有不依赖真实 pandas 的 `fake_pandas` unit stub，67 个 dependency-free Phase 6B/6C 合同测试在本地通过。**该成功不代表已读取过任何用户服务器的数据。**

此外，上传工程有大小写包装入口 `scripts/validate_phase6B.sh`，但其调用的小写 `scripts/validate_phase6b.sh` 在输入 ZIP 中缺失（旧 MANIFEST 曾列出该文件）。本轮补了主脚本并以 `0=PASS, 3=SKIP, 4=ERROR` 为约束。可用 `MAX_RECORDS=1` 在服务器验证 WOMD/AV2，`MAX_RECORDS=10` 后再压力验证。报告明确记录场景 ID、源数据 SHA、解析摘要、地图 primitive 和信号 label 数。

WOMD 在旧工程历史文档中被报告过三条服务器样本 PASS，AV2 曾因缺失 parquet engine 为 SKIP；这是**历史记录中的说法**，不属于本轮六个日志包独立证实的结果。两份数据的当前状态都等待服务器这轮重新验证。
