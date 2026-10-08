# 当前进度与接续

更新时间：2026-10-08（Asia/Shanghai）。工作目录：C:\VLA-LIBERO；WSL：/mnt/c/VLA-LIBERO。

## 当前决定与进度

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
