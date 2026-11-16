# Phase6C 0.9.3-p1: 发布完整性和 Phase6B 脚本大小写修复

## 复现与根因

本轮收到的 `RAMP-D_Phase6C_integrated_fix_20261116(1).zip` ZIP 在全新目录中可验证：

```text
RELEASE_INTEGRITY_PASS: 188 files hashed, 113 source files present
```

因此**不能仅根据服务器上的 `RELEASE_INTEGRITY_ERROR` 认定 ZIP 损坏**。该错误意味着服务器目录中的某个已列入清单的文件缺失、内容改变，或者残留了未跟踪的源码。报告中 `MISSING scripts/validate_phase6B.sh` 表明旧版 manifest 仍要求大写兼容入口，但本工程真正的执行入口为 `scripts/validate_phase6b.sh`。重命名或删除大写文件但不更新发布清单，就会得到这一错误。旧版 README 和 Phase6C-A2 验收脚本也包含大小写混用。

## 修复内容

- 唯一支持的执行入口：`scripts/validate_phase6b.sh`。彻底移除 `scripts/validate_phase6B.sh`。
- 修正 README、A2 验收脚本以及相关文档中错误的执行命令。
- 重新生成哈希清单以匹配代码，不接受把修改文件当作完整发布版。
- 改善 `verify_release.py` 的文件级诊断：`MISSING` 缺失、`MISMATCH` 内容不符、`UNTRACKED` 额外源码、`INVALID` 清单格式问题。
- 对发布检查新增六项无需 MPFR 的自动化回归。
- Phase6B 在扫描真实数据前执行同一个发布完整性检查。

严格校验是有意的：不能为使实验呈现 PASS 而跳过校验、删掉不匹配的测试或自动重写运行目录里的清单。发布清单只在构建正式修复包时重新生成。

## 安全的服务器迁移

在服务器 `/home/senzeyu2/code/` 下使用**尚不存在的新目录**，完整解压补丁 ZIP。保留旧 `/home/senzeyu2/code/RAMP-D/`；暂不删除任何源码目录。

```bash
cd /home/senzeyu2/code
unzip -q RAMP-D_Phase6C_filename_fix_20261116.zip
cd RAMP-D_Phase6C_filename_fix_20261116
conda activate mfrp
python scripts/verify_release.py
bash scripts/validate_phase6c_pure.sh
bash scripts/validate_phase4.sh
MAX_RECORDS=3 bash scripts/validate_phase6b.sh
MAX_RECORDS=3 bash scripts/validate_phase6c.sh
```

如果该新目录已经存在，**不要直接覆盖解压**；把它另行重命名后再解压，或改用全新的父目录。不同阶段的 `build_phase3/` 不会与旧目录共享，Phase4 会在需要时重新构建原生后端。真实数据与 CARLA/SUMO 的验收仍取决于服务器环境和配置。

若要调查旧目录中的单个错误：

```bash
cd /home/senzeyu2/code/RAMP-D
python scripts/verify_release.py 2>&1 | tee /tmp/rampd_release_integrity.log
```

新的校验器会逐条列出问题路径；**不要直接删除 `scripts/`、`tests/`、`python/` 或修改 `MANIFEST.sha256` 强行通过**。

## 已执行本地测试

- 原始压缩包无损、干净解压原始发布版校验通过。
- 修复后的 `test_release_integrity.py` 六项通过。
- `validate_phase6c_pure.sh` 84 项合成/接口测试通过。
- Bash 脚本语法检查通过。
- 最终压缩包重新解压后再校验（独立验收）。

没有在本轮执行真实 WOMD/AV2 服务器数据实验、MPFR 原生全量测试或 CARLA/SUMO；此前这些部分的结论不变。
