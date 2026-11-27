# 本轮验收（真实开发结果 + 实际本地代码）

## 输入复核

- 六份上传报告共享相同 manifest/summary SHA256，六份 weights 哈希一致；报告记录 checkpoint replay 一致。本地无新的 493/99 原始缓存，未独立重新推理六组权重。已上传的 local seed17 审计的 99 个场景 ID 与旧 10 个无重合，82/99 胜 CV；按场景配对 Bootstrap 95% 区间 [-0.26446,-0.14636] m，未做地理聚类。开发验证不是正式测试。
- CV 0.49933，CA 0.57199，DCA 0.45892 m。普通 Radial 三种子平均 ADE 0.41127；Actor-local Radial 平均 0.35012，全部优于 CV/DCA/匹配种子普通 Radial。主事实架构冻结，仍保留可选消融；不修改原论文。没有新规模下 Gaussian 同配置对照，Laplace 选择是基于累计开发证据。
- local seed17 低速 0.09488 vs CV 0.09079，运动 0.97619 vs CV 1.51623；弱启动代理 53/1630 正例，AP .29119 vs speed-only .28587、recall@.5 4/53；减速 AP .81558 vs .39606。代理独立模型，不是 learned latent intent，不证明联合网络可预测启动。真实驾驶意图不可直接辨识。
- 99 场景 top 2=93、top0=5、top1=1；Oracle 0=34,1=22,2=43；几何 top1 42/99，固定2 43/99。先验/后验熵1.06919/.09144；macro oracle gap .02719 m。旧 ranker hash 2/2 一致，但仍仅旧 10 场景；不能声称新泛化。
- 新模式质量算子 detached trajectory / scene mean，梯度测试通过。旧 50/10 三轮 w=0/.1/.5 都选 epoch0，全部辅助有效批次0（近似相同模式）；不能声称辅助取得增益。保留默认0，下一轮最多一个有限对照。新 audit 在旧匹配缓存真实重放通过；对新数据待服务器。

## 规则复核与修复

五类各20接受/30拒绝，共100对（20个共同原始家族），各13完整时域、7提前终止；76建模/702排除当前参与者。100/100 audit_pair 和同核 paired 重运行完全一致。原 nominal 120证据及20份2D记录逐条一致。59 joins 均零 gap，新增 polyline ledger 20/20通过；未读取新原始 map 拓扑。长度40.54–777.60m，全部在分支/无后继终止。19/20 centerline straight proposal。20376采样=3034 interior+17234 separated+108 ambiguous，明确样本一维/二维0差异；3.5m假设道路带，不是实测边界。

nominal/early/delayed_effect/late_receipt/no_ego_delivery A closed entry=2/2/0/2/2；所有20有至少一个其他 projected recipient；A rule other >=.1m 完整时域8/13各类。delayed_effect同时改变20/20物理窗口，只有6/20 A轨迹相同；新严格固定物理窗口，仅改法律时钟，20/20全部六分支轨迹一致。route_equipped 声明设备 cohort 20对重算审计通过：其他接收者总33，4个无其他接收者，13完整，7/13实质他车响应，2次违规。非真实概率。Notice 更新/取消/过期、乱序与按类型 payload；没有连接实际控制器，取消不等于物理清空。

Evidence v2 将180个 nominal 声明不送达 actor-run 字段的条件 clock mask 关闭；保留送达存在性；NO_EVENT 不产生条件时钟。所有旧投影正式 masks=false。真实局部 detection、实际物理 ACK、完整 roster、2D扫掠仍待真实环境。

## 共享资源与模型域监督

新增精确2D仿射矩形、真实相同中央区域（模型几何，不是真实道路），控制器版本ACK、全红、完整连续空区间、保护退出。8个间距家族×3变体（A, ego wait B, delayed ACK）=24 runs，A/AA 重复，所有通过日志审计并四车进入/清空、到达声明任务终端。每个变体160×0.5s tick，3,816 next-tick samples；6 train families/2 validation。动作0或1m/tick，非六维连续车辆，理想确认许可，非真实信号显示。模拟ACK读回时序可审计；原始模型执行完固定时域，包含任务结束后的重复相位，不宜当作正式数据分布。事件是下一步 traffic-actuated command class；occupancy是下一帧；observation是下一步已确认许可。model_training_allowed 只对独立头内部训练，所有正式/真实世界 masks=false。

| head | constant acc | public persistence acc | learned acc | learned loss | persistence loss |
|---|---:|---:|---:|---:|---:|
| Event phase | .39518 | .86583 | .86583 | .41585 | .57266 |
| Occupancy | .81761 | .98742 | .85587 | .29264 | .06846 |
| Observation permission | .45807 | .92872 | .92872 | .29080 | .32109 |

Event/Observation在公共持久状态错误的128/68样本中学习正确率0；Occupancy在48变化点正确约79.17%，但总体和正例召回差于几何持久；不能将学到持续性称为通过。Occupancy应优先几何派生；学习仅预测未知未来。采用多步、变化条件/删失、公共协议时序，再进入全REA。监督使用四层：真实事实、派生/代理、少量声明干预、独立数学证书。三头只在声明模型域训练，不开放其他五头。

## 软件与限制

85项专项实际通过，历史纯回归及发布完整性另见本轮日志。Native CMake缺MPFR/GMP开发文件，未运行完整Native，CARLA/SUMO/Waymax未实际启动。论文与上传TeX字节相同；历史C++/SC模块未改。论文CMR“已发现子集召回是总体下界”仍需按先前建议修正，不能用来认证SC-critical覆盖。新样本及模型不可直接用于论文真实反事实或形式化Teacher。
