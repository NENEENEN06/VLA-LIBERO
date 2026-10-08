# 历史：Goal 远近指代英文模板草案（已停止）

当前执行计划已改为SmolVLA Spatial原双碗plate／ramekin指代，见[Phase 1入口](PHASE1_ENTRY.md)。以下保留旧Goal方案及当时的确认记录，不作为现行模板或推进要求。

日期：2026-10-07（Asia/Shanghai）。状态：完整四条件模板仍为草案。用户随后授权先测试无辅助 N baseline；init0 的 Q_A/Q_B 两次均未完成任一目的地。用户要求停止，init1 Q_A 中途终止，不计完成样本。不得继续原六次计划；A/X/U 尚未确认。用户随后另行授权的单次原生命令 `put the bowl on the plate` 对照已成功，使用同一 init0，第 69 步首次完成盘子、第 300 步仍为盘子完成。见 [baseline 对照](PHASE1_BASELINE_20261007.md)。候选指代尚未通过，任何修改稿先确认。

以下只使用自然空间关系，固定候选目的地为盘子与炉子；柜子作为不移动的参照物。已完成零策略查询的十初始化场景渲染与资产核查；初始画面支持盘子比炉子更靠近柜子。运行前还需逐次核对中心平面距离并保证不少于 0.1 米差值，记录真值。若不成立，不能按本草案执行。

## 基础操作指令

- Q_A：`put the bowl on the plate or stove, whichever is closer to the cabinet.`
- Q_B：`put the bowl on the plate or stove, whichever is farther from the cabinet.`

## 辅助事实

辅助事实追加在基础操作指令之后，以一个空格分隔，整个 episode 持续使用同一文本。

| 条件 | Q_A 的辅助事实 | Q_B 的辅助事实 |
| --- | --- | --- |
| N | 无 | 无 |
| A | `The plate is closer to the cabinet than the stove.` | `The stove is farther from the cabinet than the plate.` |
| X | `The stove is closer to the cabinet than the plate.` | `The plate is farther from the cabinet than the stove.` |
| U | `The plate and stove are both resting on the countertop.` | 同 Q_A |

Q_A 的视觉目标为盘子，X 的文本目标为炉子；Q_B 的视觉目标为炉子，X 的文本目标为盘子。A/X 仅互换对象名称，不增加新的动作命令。U 只说明共同支撑表面，不提供靠近／远离柜子的选择线索。

## 冻结前要求

1. 用户确认本模板。
2. 真实场景及模型观察支持唯一的远近关系；真值核查元数据不送入策略。
3. 用现有 tokenizer 核查真实 token 数、完整解码和 48 token 上限；U 尽量与 A/X 匹配，记录实际差值。如需修改文字，修改稿再向用户确认。
4. 冻结终止规则和两个目的地事件，避免因评估目标不同造成观察时长差异。
5. 自然指代有效性只能通过随后 12 次 N/A 判断，视觉核查本身不证明模型理解模板。

观察核查属于模拟器诊断：零策略调用、零 rollout。N baseline 完成两次 rollout 共 60 次策略调用，重置核查另 2 次；中途终止的 init1 Q_A 部分查询数未保存，记为未知，不并入完成样本。旧实验和新草案均保留，未覆盖前期结果。
