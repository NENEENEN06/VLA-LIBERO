# 当前进度与接续

更新时间：2026-10-07（Asia/Shanghai）。工作目录：C:\VLA-LIBERO；WSL：/mnt/c/VLA-LIBERO。

## 最新结论

用户随后确认的柜子提及对照已完成：直接盘子命令后分别追加 `The cabinet is on the table.` 与同句式 `The bottle is on the table.`，各 init0 一次，均未完成任一目的地。柜子条件第 32 步首次出现手指与柜子接触，301 个采样状态中有 118 个接触；瓶子条件没有柜子接触，但也失败。两条件都是 15 个有效 token，与原生对照初始画面、模拟状态和初始化摘要一致。新增 60 次策略调用，进程退出码 0。见 [柜子提及对照](PHASE1_CABINET_MENTION_20261007.md)。柜子接触有实测支持，但不能独自解释所有附加事实条件的失败；当前辅助文本可用性尚未建立，不进入事实冲突。此前六次指代计划保持停止。

新 Phase 1 的 N-only baseline 已按用户要求停止。已完成 init0 的 Q_A（较近）与 Q_B（较远），两次均为 neither、300 步未完成任一目的地；init1 Q_A 中途停止，不计完成样本，未保存部分查询数。用户随后要求试 `put the bowl on the plate`，同一 init0 的一次原生指令对照已成功：第 69 步首次到盘子，第 300 步仍为盘子完成、炉子未完成，进程退出码 0。三次初始观察、模拟状态与初始化摘要一致。报告见 [当前 baseline 对照](PHASE1_BASELINE_20261007.md)。原生指令正常，候选指代尚未通过；后续文字修改须先确认，不能自动恢复原六次试验或进入 A/X/U。

十初始化场景核查已完成，盘子距柜子中心约 0.20–0.22 米，炉子约 0.63 米；仅是指代真值核查，不证明模型理解。文本见 [模板草案](PHASE1_TEMPLATE_DRAFT_20261007.md)。指代试验数据 outputs/phase1/smolvla-baseline-N-20261007/，日志 logs/phase1-baseline-N-20261007.log；原生对照数据 outputs/phase1/smolvla-native-plate-20261007/，日志 logs/phase1-native-plate-20261007.log。新增脚本不更改前期冻结脚本。

Goal 共享场景核查已完成二十次，正常退出：碗放盘子 10/10、碗放炉子 10/10；十组配对初始观察和模拟状态一致，文本和判据正确，无错误目的地完成事件。重置复核观察与首动作差异为 0。

可以继续使用 SmolVLA，在该共享 Goal 场景进入 Phase 1 小规模行为刻画。该结论限于物理 task 8、原生盘子／炉子指令、十个初始化和策略 seed=1。Object 目标切换失败仍保留为条件边界。

报告：[Goal 核查](SMOLVLA_GOAL_CHECK_20261007.md)。数据 outputs/readiness/smolvla-goal-20261007/，summary.json、readiness-assessment.json、episodes/、videos/；日志 logs/smolvla-goal-language-20261007.log。

## 下一步（2026-10-07 计划调整）

此前旧 Phase 1 已按用户要求暂停并删除，不再恢复该轮任务。当前新方案仅执行随后明确授权的 N-only baseline、单次原生对照与柜子提及小诊断。

前期环境、权重、Spatial 基线、SmolVLA 前置核查及 Goal 两目标核查全部保留。用户将当前优先级调整为先探究文本与视觉主导关系，并要求参考 VLM 论文。新 [Phase 1 方案](PHASE1_ENTRY.md) 先核查自然属性／关系指代，固定图像做无辅助、正确事实、最小冲突、等长无关四条件 × 两个互补指代，按 12→24→80 次推进；对称视觉线索矩阵后续另计。原文核对见 [VLM 设置参考](../plans/黑盒跨模态攻击/08_VLM主导关系实验设置参考.md)。

计划调整时未实施实验；随后用户确认设置，要求模板先确认，并进一步授权先试 baseline。故当前仅测试草案中的两条基础指令，不自动启动 A/X/U，也不更换模板。不能拿原生命令 10/10 替代新指代基线。攻击搜索在主导诊断后按证据决定。

## 保留的前期结果

- 三模型环境与 CUDA、双相机、策略输出和闭环已通过。[配置状态](SETUP_STATUS.md)。
- 三模型 Spatial 单次基线：SmolVLA 8/10、VLA-Adapter 10/10、PulseVLA 9/10。[基线记录](SPATIAL_BASELINE_20261006.md)。
- SmolVLA 前置 49 次：Spatial 0 为 7/10、Spatial 3 为 5/10、Spatial 4 为 8/10、Object 0 为 10/10；同义改写 2/3，Object 身份切换 0/3。固定 seed 完整重放逐动作一致；额外 seed=7 失败、seed=11 成功。[前期核查](SMOLVLA_READINESS_20261006.md)。
- 指令 Goal task 1、8 已登记为已见探索数据；两个条件共用一个物理场景，不能视为两个独立场景的确认。
- 旧暂停记录仅为历史。当前 Goal current-status.json 为 completed。全部冻结脚本与旧结果保留。
