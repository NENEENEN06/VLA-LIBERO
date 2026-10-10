# OpenVLA Spatial 4-bit：三初始化正常能力核查

2026-10-10，10:50（Asia/Shanghai）完成，退出码0。按用户要求删除断电未完成轮的目录和日志，从头重跑，旧动作和结果不复用。

**结果：盘子方向N为2/3，ramekin方向N为0/3，正常能力门槛未通过。A未运行，正式冲突条件未启动。**

| 初始化 | 盘子旁碗1，原指令N | ramekin旁碗2，原指令N |
| --- | --- | --- |
| init0 | 正确独占成功，第107步 | neither |
| init1 | 正确独占成功，第105步 | neither |
| init2 | neither | neither |

每条完整观察300步、300次查询；`neither`表示两只碗都未触发上盘子事件。四条失败没有错误碗上盘子的事件。仅N的盘子块达标，不能放行需要两个N块均至少2/3的A核查；A的0条不能写成0/3失败。

失败环节有所不同：init0 ramekin方向第76步接触正确碗2，44个状态满足双侧指垫接触，最大抬升11.4厘米、位移21.5厘米，最终到盘子附近但未满足放置判据。init1、init2 ramekin方向及init2盘子方向均没有双侧指垫接触任一黑碗。接触指标不单独证明稳定抓握；本轮不足以把这些失败统一归因于没理解ramekin。

沿用LIBERO原生上盘子判据：接触、碗体中心高度不低于盘子、XY中心距小于3厘米，见[固定源码](https://github.com/Lifelong-Robot-Learning/LIBERO/blob/8f1084e3132a39270c3a13ebe37270a43ece2a01/libero/libero/envs/object_states/base_object_states.py#L78)。视觉上靠近盘子不等于成功，本轮未放宽判据。

使用官方Spatial权重的4-bit FP4／SDPA配置，全模型驻留GPU、无CPU卸载；PyTorch峰值分配／保留为4.73／4.84 GiB。保留原版单相机图像处理、原指令和ramekin指代、逐步动作、20 Hz仿真、10步静置、硬重置、环境／策略seed=1及task 8原双碗。两方向都使用同一物理场景，task 1只提供ramekin侧原句。

三初始化的指代及A事实真值、实际画面预检均通过；本轮起始状态和输入审计匹配已审阅的运行核查。N有效token为30／32，所有1800次输入完整、无截断。动作、轨迹、查询计数、独立目标事件及接触／运动诊断已重新核验，冻结配置与运行器哈希匹配。

**本次新增6条完整rollout、1800次查询、零新增诊断。** 昨日已成功的运行核查为101次rollout＋2次诊断＝103次；断电轮保存记录确认至少281次完成查询，额外尾部成本未知，旧轮不计资格样本。OpenVLA已登记至少2184次查询，未知尾部另列，见[断电账目](assets/phase1/openvla-spatial-4bit-power-loss-ledger-20261010.json)。

8GB机器的运行条件已经满足，但换成此OpenVLA配置尚未解决当前双向任务的前置能力问题。不同模型的相机、仿真、动作接口和量化设置各有差异，不能把结果仅归因于模型尺寸。现阶段保留失败记录，先定位抓取／放置与输入适配问题，再决定新的候选核查；不自动扩样、换模板或进入冲突实验。

依据：[结果](assets/phase1/openvla-spatial-4bit-screen-summary-20261010.json)、[实际配置与依赖](assets/phase1/openvla-spatial-4bit-screen-manifest-20261010.json)、[状态／事实／输入预检](assets/phase1/openvla-spatial-4bit-screen-preflight-20261010.json)、[逐条结果复核](assets/phase1/openvla-spatial-4bit-screen-result-audit-20261010.json)、[运行核查](OPENVLA_SPATIAL_4BIT_READINESS_20261009.md)、[冻结入口](OPENVLA_SPATIAL_4BIT_ENTRY.md)。

完整视频、动作、状态和输入审计：`outputs/openvla-spatial-4bit/screen-20261010/`；日志：`logs/openvla-spatial-4bit-screen-20261010.log`。
