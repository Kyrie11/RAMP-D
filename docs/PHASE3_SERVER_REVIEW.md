# Phase 3 服务器结果复核

用户上传的 `RAMP-D_Phase3_server_report.zip` 与 Phase 3 工程源文件的哈希一致。报告环境为 Python 3.10.20、GCC 9.4、CMake 3.18、MPFR 4.0.2；3 项 native、295 项 Python 全部通过，失败、错误和跳过均为 0。

复核结果：

- Phase 3 的 MPFR directed interval、Picard inclusion witness、解析速度极值、signed-speed stop、完整 swept footprint projection、evidence context 绑定、fixed-point 和 backup graph replay 均通过。
- 17 节点 brake/hold 图闭合并回放，20 个执行步骤的 terminal `v=a=0` 精确断言通过；四类模板均找到至少一个局部候选。
- 报告的 assurance scope 仍是 `LOCAL_BICYCLE_STATIC_SCENE_DECLARED_OBSERVATIONS`；`full_support_certified=false`、`current_scene_verified=false`、`concrete_safety_certified=false` 正确，没有把 Phase 3 局部结果写成完整交通安全。
- 服务器脚本生成摘要中的 `target_server_acceptance=PENDING_EXTERNAL_REVIEW` 是旧脚本字段，不能覆盖报告本身已经完成的目标环境测试。工程上将本次结果记为“服务器运行通过，范围仍局部”，而不是全支持交通认证。

Phase 4 的全支持验证器因此复用 Phase 3 的数值内核和回放接口，但不复用 Phase 3 的静态场景/声明 observation 假设作为真实交通证据。
