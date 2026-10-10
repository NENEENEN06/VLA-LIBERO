# OpenVLA Spatial 4-bit：原生ramekin任务对照

2026-10-10，13:32（Asia/Shanghai）完成，退出码0。**原生task1三个初始化均成功，新增329次查询。**

| 初始化 | 原生放置结果／查询数 | 首次正确碗双侧接触 | 正确碗最大抬升 |
| --- | --- | --- | --- |
| init0 | 碗1独占成功，第114步／114次 | 第67步 | 19.4厘米 |
| init1 | 碗1独占成功，第99步／99次 | 第57步 | 14.6厘米 |
| init2 | 碗1独占成功，第116步／116次 | 第68步 | 15.5厘米 |

本轮使用task1自己的官方双碗场景、初始状态和原版句子：`pick up the black bowl next to the ramekin and place it on the plate`。task1的正确目标是碗1；此前task8场景换成该指令时的正确目标是碗2。两个场景与初始化不同，同编号init不构成跨场景状态配对。

模型、FP4／SDPA、单相机图像处理和逐步动作配置与已通过的运行核查一致。环境／策略seed=1、硬重置、10步静置、每条300步上限，原生成功提前结束；三条成功均早于220步，但本轮并非官方完整套件评测。初始几何、实际224输入图、完整32-token原指令、重置状态和每次查询输入审计均通过。

成功沿用原生On判据：碗与盘子接触、高度条件成立、XY中心距离小于3厘米；三条终点距离分别2.77、1.04、0.37厘米。没有放宽判据。另一只碗全程没有双侧指垫接触或上盘子事件，仅有数值量级运动。接触／抬升作动作诊断，不单独证明语言理解。

**当前配置具备所测原生ramekin任务的执行能力。** 与task8换目标0/3对照后，接下来优先核查任务／场景迁移，而不能把失败简单归为没理解ramekin。布局、初始化和目标身份均不同，本轮不是只改变一个视觉因素的因果实验，也不能证明普遍指代理解或量化无影响。

建议下一版Phase1候选先采用原生任务内配对：task1保留ramekin原句，task8保留plate原句，各自固定场景／初始化／目标，只比较N与追加事实；新A/X/U须分别核查真值并另立冻结协议。跨任务不要求同一画面，原同场景双向切换问题保留为另一项能力边界。此建议尚未替代现有冻结资格，当前task8 N盘子2/3、ramekin0/3及A未运行保持不变，正式冲突未启动。

本轮3条均为新rollout，**329次rollout查询、零额外策略诊断、零旧策略查询复用**。零查询预检与独立结果复核另记。OpenVLA累计已登记至少2513次：运行核查103、已删除断电轮至少281、task8新N 1800、本轮329；断电尾部未知仍单列。近期研究口径至少3743次，更早环境／套件基线不在此范围内，不合并为一个成功率分母。

依据：[冻结规则](OPENVLA_NATIVE_RAMEKIN_ENTRY_20261010.md)、[结果](assets/phase1/openvla-native-ramekin-summary-20261010.json)、[运行配置](assets/phase1/openvla-native-ramekin-manifest-20261010.json)、[预检](assets/phase1/openvla-native-ramekin-preflight-20261010.json)、[画面审阅](assets/phase1/openvla-native-ramekin-visual-review-20261010.json)、[独立轨迹复核](assets/phase1/openvla-native-ramekin-result-audit-20261010.json)、[task8失败记录](OPENVLA_SPATIAL_4BIT_SCREEN_20261010.md)。

完整轨迹、动作和视频：`outputs/openvla-spatial-4bit/native-ramekin-20261010/`；日志：`logs/openvla-spatial-4bit-native-ramekin-20261010.log`。运行器：[原生诊断脚本](../scripts/check_openvla_native_ramekin.py)。
