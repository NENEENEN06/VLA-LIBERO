# 当前进度与接续

文档整理日期：2026-10-10（Asia/Shanghai）；原SmolVLA N/A与各模型的新核查分开登记。工作目录：C:\VLA-LIBERO；WSL：/mnt/c/VLA-LIBERO。

## 2026-10-10 接续诊断已完成，现已暂停

用户先授权按证据继续，5小时剩余额度小于10%时完成当轮后暂停、汇总提交并推送；随后明确要求“跑完这轮就停”。三初始化N/A已结束，按该指示暂停。用户又确认前置无关提示已经试过，不重复、不补测。见[接续汇总](EXPERIMENT_CONTINUATION_20261010.md)。没有后台定时任务；本机控制状态在`.runtime/experiment-continuation-20261010.json`，账户快照保持本地。未过正常门槛不开展正式冲突。

16:03完成[同长度中性追加v1](OPENVLA_NATIVE_NEUTRAL_V1_20261010.md)：两个原生任务init0各一条U，ramekin第111步正确独占成功，plate满300步neither，新增411次查询、零额外策略诊断。与旧N/A同状态、同图像、同评价，A/U分别52／50有效token，无截断；来源、输入与逐条轨迹复核通过。ramekin这一个初始化的U成功、A失败，纯长度或换行不足以解释差别，事实内容与表达结构还未分离。plate U接触正确碗但只抬升3.2厘米，最终高度和XY距离未过原生判据。正式矩阵新增0，A门槛保持未通过。

[主问题／事实包装v1](OPENVLA_QUESTION_CONTEXT_V1_20261010.md)完整重跑结束：两N第114／107步成功；ramekin A满300步未完成，plate A第133步成功；ramekin U第120步成功，plate U满300步未完成、终点中心距4.72厘米超限。新增1074次查询，逐条复核通过。首轮因状态文件写入错误中止的112次成本保留，重跑头112步动作、状态及实际输入完全相同，见[中止与重跑核验](OPENVLA_QUESTION_CONTEXT_V1_RETRY_20261010.md)。总成本至少6422次OpenVLA／7652次近期研究，未知旧中止另列。

[事实先行v1](OPENVLA_FACT_FIRST_V1_20261010.md)已完成：两个任务init0的N/A/U六条全部正确独占成功，步数分别114／107、113／108、132／91，共665次新查询，零额外策略诊断，独立复核通过。同一事实先给出、原动作问题紧邻Out；原句、字符／token多重集及长度保持，模型仍为FP4／SDPA，3厘米判据不改。至此OpenVLA至少7087次、近期至少8317次，未知旧中止另列。

[三初始化事实先行N/A](PHASE1_OPENVLA_FACT_FIRST_NA_RESULTS_20261010.md)已完成，退出码0、独立复核通过：ramekin N3/3、A1/3；plate N2/3、A1/3，正常门槛未通过。六条N／两条init0 A来源的1062次旧成本只计一次；新跑init1、2四条A全部满300步neither，新增1200次查询。六个实际状态／输入与六幅图核验通过，plate init1目标左缘部分裁剪的限制保留；没有放宽原生3厘米判据。

前置正确无关事实U沿用事实先行v1的init0结果：ramekin第132步、plate第91步成功，共223次查询已经包含在665次内。U只测过这两个init0，未补齐init1、2，也不替代A资格。连续接续新增3462次，18条新完整rollout及1条112步I/O中止；OpenVLA累计至少8287次、近期至少9517次，未知旧中止另列。实验进程已退出，当前暂停，后续需用户明确恢复。

## 2026-10-10 原生任务内配对v1已完成

用户同意新候选路线，已冻结[任务内配对v1协议](PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md)和[配置](../configs/phase1-openvla-native-pairs-v1.json)。task1使用原生ramekin原句和自己的场景，task8使用原生plate原句和自己的场景，目标均为各场景的碗1；只在每个任务／初始化内部配对条件。旧task8同场景换目标资格结果保留，新候选另计。

14:40完成，退出码0；六状态N/A/X/U真值、输入、U桌面接触和画面预检通过。**task1 N3/3（旧N核验复用），task8 N2/3（新N），两个任务A均0/3，正常门槛未通过。** 9条新rollout共2312次查询：task8 N512次，六条A1800次；零额外策略诊断。三条旧N与329次旧成本只计一次，X/U只有零查询预检，正式冲突和扩样没有启动。

见[结果与失败环节](PHASE1_OPENVLA_NATIVE_NA_20261010.md)。六条A均neither，三条终点接触／高度成立但中心距3.56／3.22／3.95厘米超原生3厘米上限；另有未建立黑碗接触及接触后未搬运完成。错误碗无上盘子和双侧接触事件，不能把失败统一解释为ramekin没理解。全部新查询无截断，输入／状态／源配置／轨迹与成本复核通过，原生成功判据未放宽。

接续建议：另立两个原生任务init0的同长度中性追加诊断，最多600次新增查询；先冻结独立预算与来源核对，判断一般追加敏感与当前关系事实内容的影响。本轮未运行该探针，正式X/U仍需A正常条件门槛。OpenVLA累计已登记至少4825次，近期口径至少6055次；未知断电尾部及旧Goal中止另列。

运行器：`scripts/check_openvla_native_pairs.py`；产物：`outputs/openvla-spatial-4bit/native-pairs-v1-20261010/`；日志：`logs/openvla-native-pairs-v1-20261010.log`。本轮进程已结束。以下2513／3743及更早数值保留对应历史阶段口径。

## 2026-10-10 原生ramekin对照已完成

13:32，OpenVLA Spatial 4-bit官方task1自己的双碗场景和初始化0、1、2，保留原版ramekin指令，**3/3正确碗独占成功，第114／99／116步**。新增329次rollout查询，零额外策略诊断、零旧策略查询复用；原生On及终止逻辑保留。模型、FP4／SDPA、相机和动作接口与运行核查一致，实际图像、输入、状态与逐条轨迹独立复核通过，退出码0。

见[结果报告](OPENVLA_NATIVE_RAMEKIN_20261010.md)及[冻结规则](OPENVLA_NATIVE_RAMEKIN_ENTRY_20261010.md)。该结果支持所测原生任务可执行；task1正确目标为碗1，task8换目标正确目标为碗2，布局和初始化不同，不是跨场景严格配对，也不证明普遍理解ramekin。原task8 N盘子2/3、ramekin0/3的资格失败记录不改写，A与正式冲突仍未运行。

当时的接续建议为准备“原生任务内配对”的新候选协议，后来v1已冻结并完成，结果见上节。两任务各自保持场景／初始化／目标，跨任务不宣称同一画面；v1的A仍未通过，未替代旧同场景双向资格。当前原生对照已结束，没有本轮实验进程。

OpenVLA已登记至少2513次查询，近期口径至少3743次；未知断电尾部与旧Goal中止仍另列。产物：`outputs/openvla-spatial-4bit/native-ramekin-20261010/`；日志：`logs/openvla-spatial-4bit-native-ramekin-20261010.log`；运行器：`scripts/check_openvla_native_ramekin.py`。以下保留各历史统计范围。

## 2026-10-10 OpenVLA Spatial 4-bit核查已完成

用户选择新增OpenVLA原版Spatial 4-bit候选。独立环境、权重完整性、GPU-only FP4／SDPA加载和真实闭环已通过：官方task 8原目标基线第101步成功，另2次重置诊断一致；PyTorch峰值分配／保留约4.73／4.84 GiB，见[运行核查](OPENVLA_SPATIAL_4BIT_READINESS_20261009.md)。

断电导致10月9日的能力轮未完成，按用户要求删除该目录和日志，10月10日从头重跑。**六条N全部完成：盘子方向2/3，ramekin方向0/3，正常能力门槛未通过，A未运行，X/U与扩样未启动。** 每条300步／300次查询，本轮新增1800次查询、零诊断、零旧结果复用。init0 ramekin条接触并抬升正确碗2但未放置成功，其余三条失败无双侧指垫接触任一黑碗；不能统一归为ramekin不理解。

见[完整结果及复核](OPENVLA_SPATIAL_4BIT_SCREEN_20261010.md)、[独立配置及执行规则](OPENVLA_SPATIAL_4BIT_ENTRY.md)。OpenVLA已登记至少2184次查询：本轮1800、已完成运行核查103、断电保存记录至少281；断电尾部未知另记，不充作完成样本。运行器：`scripts/check_openvla_spatial_4bit.py`；产物：`outputs/openvla-spatial-4bit/screen-20261010/`；日志：`logs/openvla-spatial-4bit-screen-20261010.log`。本轮进程已结束，退出码0。

OpenVLA候选未通过当前双向任务资格，不自动更换正式发现／搜索主模型。其后原生task1对照已完成，结果及新的接续建议见上节；新的模型／精度／任务改动另立核查，正式Phase 1仍暂停在正常能力门槛。以下保留SmolVLA与Adapter各历史记录的原统计范围。

## 研究方案与文档入口

[完整研究方案](../plans/研究方案.md)按 CoVLA 形式集中呈现背景、问题、权限、形式化、方法、实验及风险。[项目主页](../README.md)提供概览，[专题索引](../plans/README.md)提供细节，[环境与运行](RUNNING.md)保留安装和评测命令。

既定四阶段保持：Phase 1 行为刻画 → Phase 2 脆弱性 → Phase 3 范围确认 → Phase 4 方法设计。CoVLA 等义协同属于 Phase 2，分别使用 E00/E10/E01/E11 与 Γ，不混入当前事实冲突矩阵。本次整理未新增实验结果；以下已完成数据、当前门槛与历史边界保持原记录。

## 2026-10-09 独立中性追加诊断

[诊断报告](PHASE1_SMOLVLA_SPATIAL_NEUTRAL_20261009.md)记录：SmolVLA Spatial task 8、init0、原双碗两方向各一条 U 中性追加，均 neither；每条 300 步／30 次查询，共新增 2 条／60 次查询，零新策略诊断调用。原 N/A 仅引用作已见参考，正式矩阵新增为 0、冲突 rollout 为 0。

两次输入完整、有效 token 为 34／36，初始观察与状态配对。单个中性句不能单独隔离长度、换行或参照物提及因素，不证明普遍语言失效或图文主导。原 A 门槛仍未通过，正式 X/U 矩阵、扩样及 CoVLA 未启动；近期已知成本由原 N/A 完成时 1050 增至 1110 次，未知中止成本仍单列。

最新诊断建议优先固定中性句与原指令，核查换行／空格拼接效应，再依据证据修辅助事实载体并重新验证 A。具体条件及预算先冻结；当前只完成诊断，不自动开展拼接试验。以下保留原 N/A 与历史记录的统计范围。

## 当前模型与 2026-10-08 N/A 核查

主模型为**SmolVLA**，Phase 1采用Spatial task 8原双碗和plate／ramekin原版指代。VLA-Adapter原版、PulseVLA-LIBERO为验证候选；现有Adapter双碗第二方向失败，须自行核查后才比较。

2026-10-08 16:06，三初始化N/A全部完成，退出码0：**两个方向N均2/3，A均0/3，门槛未通过**。新增10条完整rollout、300次查询；复用旧init0 N两条及原2次重置诊断，零新增诊断。共12条正常核查结果、360次rollout查询＋2次旧诊断。X/U仅零查询预检，未运行行为，未扩样。见[最新记录](PHASE1_SMOLVLA_SPATIAL_NA_20261008.md)。

三初始化关系、实际画面与完整等长文本预检通过，A/X/U[英文模板](PHASE1_SPATIAL_TEMPLATES_20261008.md)已冻结；实际N为16／18 token、A/X/U为34／36。初始哈希配对及旧N复用来源已核对。首次预检把窄出生区域On当成自然next to判据，零策略查询时停止；修正保留原0.05米距离门槛，错误和快照未覆盖。

当前停在正常能力核查：N达到探索门槛但存在自然失败，A行为不通过；先重新设计辅助事实载体，新稿再冻结并检验A。未达到四块各至少2/3前不进入X/U。失败并不都等于指代不理解：init1 ramekin-N及init2 plate-N都接触、抬升了正确目标而未完成放置。

当前计划见[总览](../plans/README.md)、[模型准备](../plans/黑盒跨模态攻击/03_模型选择与基线准备.md)、[路线与预算](../plans/黑盒跨模态攻击/07_实施路线与查询预算.md)及[入口](PHASE1_ENTRY.md)。旧SmolVLA Goal试验保持停止；[旧总报告](PHASE1_EXPERIMENT_SUMMARY_20261008.md)及PDF保留原统计范围，下节是历史Adapter证据。

最新脚本：`scripts/check_phase1_smolvla_spatial_na.py`；产物：`outputs/phase1/smolvla-spatial-NA-20261008-retry1/`；日志：`logs/phase1-smolvla-spatial-NA-20261008-retry1.log`。首次零查询错误在不带retry1的目录。没有正在运行的本轮评测。

## VLA-Adapter 已完成的候选核查

用户授权的措辞配对已完成（13:48，退出码 0）：原 Spatial task 8 双碗、init0，`ramekin` 条件仍 neither；换成 `small white bowl` 后完成了错误碗1（首次放置第 92 步），目标碗2仍无抓取接触。两条各 300 步、38 次查询，新增 76 次，零诊断；原始文本均 17 token、实际包装均 54，无截断。初始三类摘要一致，原条件 300 步执行动作与旧轨迹最大差异为 0；不移碗、不加入额外观测刷新。名称替换改变了行为但未解决正确目标绑定，不足以判断是否理解 ramekin，不扩样、不进入冲突。见 [措辞对照](PHASE1_RAMEKIN_WORDING_20261008.md)。脚本 `scripts/check_phase1_ramekin_wording.py`，输出 `outputs/phase1/vla-adapter-ramekin-wording-20261008/`、日志 `logs/phase1-adapter-ramekin-wording-20261008.log`。

用户授权的两次单碗能力对照已完成（13:19，退出码 0）：Spatial task 8、init0、原两条指令及 300 策略步，移走另一只碗后，碗1第 93 步、碗2第 99 步完成放置，均成功；新增 76 次策略查询、零诊断调用。干预前状态匹配旧双碗记录，干预后与仅刷新控制比较，其他 qpos/qvel、物体位置和本体观察均不变；移走碗全程静止且无任务接触。首次零查询预检因派生缓存刷新差异停止，修正及记录保留；原与刷新后观测有微小本体及像素差，旧双碗比较不能独立排除刷新因素。单碗成功只证明改造后操作可行，不证明原双碗指代有效。见 [单碗报告](PHASE1_SINGLE_BOWL_20261008.md)。新输出 `outputs/phase1/vla-adapter-single-bowl-20261008-retry1/`、日志 `logs/phase1-adapter-single-bowl-20261008-retry1.log`；原零查询错误与诊断保留在不带 retry1 的目录。不扩样、不进入冲突。

| 运行 | 结果 | 完整 rollout／查询成本 | 报告 |
| --- | --- | --- | --- |
| Goal task 8、init0：原生命令、远近指代、事实追加 | 盘子／炉子直接命令成功；远近指代失败；柜子／瓶子事实追加成功 | 6 次，228 次 rollout 查询 + 2 次诊断 | [换模型报告](PHASE1_MODEL_SWITCH_20261007.md) |
| 同一 Goal 场景短版指代 | closer／farther 两条均 neither | 2 次，76 次查询，零诊断 | 同上短版追加 |
| Spatial task 8、init0：next to 双向选碗 | 碗1条件第 99 步完成；碗2条件 neither，目标碗2无双侧指垫接触、非目标碗1位移约 14.5 厘米 | 2 次，76 次 rollout 查询 + 2 次诊断 | [Spatial 报告](PHASE1_SPATIAL_REFERENCE_20261008.md) |
| 同一源初始化的单碗能力对照 | 各自移走另一碗后，碗1／碗2条件均成功 | 2 次，76 次查询，零诊断 | [单碗报告](PHASE1_SINGLE_BOWL_20261008.md) |
| 原双碗同目标的参照物措辞对照 | ramekin 条件 neither；small white bowl 条件操作了错误碗1，均未完成碗2 | 2 次，76 次查询，零诊断 | [措辞报告](PHASE1_RAMEKIN_WORDING_20261008.md) |

合计 14 个完整 rollout、532 次 rollout 策略查询及 4 次诊断，总查询 536；已完成 rollout 均正常退出。另有一次零查询单碗预检错误及其零查询刷新诊断，已单独保留，不计模型失败或完成样本。现有失败结果限于已测初始化与模板，不证明模型一般不理解距离、ramekin 或具有普遍对象偏好，也不能解释为图文主导。

Spatial 选碗按预定规则停在 init0，未补 init1／init2；第二条只借用了官方 task 1 的文字，物理场景仍是 task 8。官方不同场景的任务成功不能替代共享场景换目标。当前尚未运行四条件冲突矩阵。

本地输出和日志：

- Goal 六次：`outputs/phase1/vla-adapter-model-switch-20261007/`、`logs/phase1-adapter-model-switch-20261007.log`。
- Goal 短版：`outputs/phase1/vla-adapter-simple-N-20261007/`、`logs/phase1-adapter-simple-N-20261007.log`。
- Spatial 选碗：`outputs/phase1/vla-adapter-spatial-reference-N-20261008/`、`logs/phase1-adapter-spatial-reference-N-20261008.log`。
- 单碗对照：`outputs/phase1/vla-adapter-single-bowl-20261008-retry1/`、`logs/phase1-adapter-single-bowl-20261008-retry1.log`。
- 措辞对照：`outputs/phase1/vla-adapter-ramekin-wording-20261008/`、`logs/phase1-adapter-ramekin-wording-20261008.log`。

## 下一步与推进边界

1. 保留SmolVLA Spatial原版Q_A/Q_B及已有三初始化N结果；先重新设计辅助事实载体，核对并冻结初始真值、唯一替代目标、拼接与48有效token上限。
2. 新A在同一固定初始化集合重新核查，原N仅完全同配置时复用；新模板尝试与额外诊断另计，不改写旧A六条失败。
3. 四块各至少2/3正确独占完成后，才考虑12条X/U和扩样；本轮按门槛停止，没有启动这些条件。
4. 首轮80条只是合格候选的条件性预算。本轮完整N/A已新增300次查询，已知近期成本由750增至1050；旧Goal中止成本仍未知。

主模型仍用hf-libero／MuJoCo 3.3.2、原生360×360双相机及本体处理、20 Hz、10步动作执行、10步静置、硬重置、seed=1、300策略步。诊断、参考、异常、中止及重放分别记账，失败条件不延长上限来补成功。

## 保留的历史与已见探索

- 三模型环境、CUDA、双相机、策略输出及短程闭环均已验证；[配置状态](SETUP_STATUS.md)。
- 三模型 Spatial 每任务一次：SmolVLA 8/10、VLA-Adapter 10/10、PulseVLA 9/10；[Spatial 基线](SPATIAL_BASELINE_20261006.md)。
- SmolVLA 前期 49 次及 Object 身份切换 0/3；[前期核查](SMOLVLA_READINESS_20261006.md)。
- SmolVLA 共享 Goal 原生盘子／炉子各 10/10 是该模型原生目标锚点，不能证明新指代或 VLA-Adapter 能力；[Goal 核查](SMOLVLA_GOAL_CHECK_20261007.md)。
- SmolVLA N-only 的 init0 两条失败，随后 init1 Q_A 被用户要求停止，部分查询成本未知，不补跑也不计完成样本；原生盘子对照成功；[baseline 对照](PHASE1_BASELINE_20261007.md)。
- SmolVLA 柜子／瓶子事实追加均失败；[提及核查](PHASE1_CABINET_MENTION_20261007.md)。

旧暂停与原生成功的推进判断仅属历史，当前主模型与前置状态以上述决策为准。原脚本、日志和结果保留，全部已试任务、初始化、模板及中止尝试登记为已见探索，不冒充独立留出数据。
