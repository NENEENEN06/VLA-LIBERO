# OpenVLA语言扰动诊断v1：冻结入口

2026-10-11，用户指示“照这个做”，据[文献审查](LANGUAGE_DISTRACTION_LITERATURE_REVIEW_20261011.md)恢复此轮开发诊断。配置：[openvla-language-robustness-v1.json](../configs/openvla-language-robustness-v1.json)。本入口在新增策略查询前冻结。

## 固定设置

OpenVLA原版Spatial FP4／SDPA及既有FactFirstPolicy；task1／task8各自原生场景，init0、1、2，种子均1，静置10步，单策略调用执行1步，每条上限300步。原生On(bowl1,plate)、3厘米阈值和提前终止保留，两碗事件独立记录。跨任务不称同画面目标切换。

六条N先核验复用：模型、依赖、辅助代码、原始状态和图像、完整文本、动作布局、种子、原生目标及终止时机。来源正常成功为ramekin 3/3、plate 2/3，841次旧调用只登记来源，不重复计费。任何复用核验失败均在零查询时停止，另冻结补N预算后再运行，不静默扩大5400次上限。

## 预先固定的三个条件

| 条件 | ramekin任务文本 | plate任务文本 | 实际token ramekin／plate |
| --- | --- | --- | --- |
| P | lift the black bowl next to the ramekin and put it on the plate | lift the black bowl next to the plate and put it on the plate | 31／29 |
| U0 | Initially, the table has a flat surface, and the wall in the background is gray. | 同左 | 52／50 |
| A0 | Initially, the black bowl next to the ramekin is on the table surface. | Initially, the black bowl next to the plate is resting on the table surface. | 52／50 |

N原句和实际输入逐字保留，token为32／30。P仅替换pick up→lift、place→put，目标／参照物／目的地与动作顺序不变。P使用原生动作问题包装。U0/A0先给事实，原动作问题紧邻Out；与旧fact_first_v1相同。U0不提目标碗、目的地、参照物或旧第二参照物。A0重复一个直接next to关系，并描述初始桌面支撑；不引入farther/closer、第二参照物或新动作指令。

U0与旧U、A0与旧A的有效token分别等长。两任务A0的支撑措辞略有不同，分别固定以实现各任务内长度匹配，不跨任务声称只改变单一词汇。旧U/A来源是已见探索参考；U只有init0，不能当三初始化配对对照。U0同时改变实体提及与事实内容，差异不能唯一归因为实体词。

零查询预检核对唯一next to距离差至少0.05米、碗1桌面接触、桌面水平薄盒和灰色墙材质。六幅实际224模型输入图由本代理逐幅审阅；部分裁剪如实标记，不遮盖旧限制。事实以Initially限定初态，整条闭环持续输入，不声称这是单帧或动态事实条件。

## 固定查询与分析

顺序：P→U0→A0；每条件ramekin→plate，每任务init0→1→2，共18条、最多5400次新策略调用；额外策略诊断0。途中失败保留，不能按成功挑句或追加初始化。未完成／中止调用单列，不充作完整样本，也不自动重新跑突破预算。

主表列N/P/U0/A0每任务的成功、正确双侧指垫接触、错误双侧接触，以及接触与抬升后未完成。抬升2厘米仅用于描述性分层，成功仍用原生3厘米放置判据；接触不是稳定抓握。报告配对的SR(N)-SR(P/U0/A0)及接触率差，既有失败和负差值保留。旧U1／A1仅历史参考，来源与重复复用不当作独立样本。

init0..2及本轮文本均为开发数据，不能作为独立确认。A0未达到每任务至少2/3正确独占完成时，不开展该载体的事实冲突解释。即使达到探索门槛，也必须另冻结留出确认与X/U预算。本轮结束后报告结果与边界，不自动启动CAG、训练、正式冲突或攻击搜索。

运行器：[check_openvla_language_robustness.py](../scripts/check_openvla_language_robustness.py)。每轮保存manifest、零查询预检、六图审阅、N来源审计、完整动作／事件／视频、有效样本与完整／中止成本。

首次预检因环境不存在`mujoco_arena`属性退出，策略调用0。读取墙材质改为环境实际`model.asset`，不改文本、真值要求或预算。失败状态、日志及运行器快照保留在初始目录；修正重跑使用`language-robustness-v1-retry1-20261011`，重新完成所有预检和来源核查。

retry1的纹理文件核验仍使用XML默认名称，忽略了场景初始化按`light-gray-plaster`风格替换为`light-gray-plaster.png`，在零策略查询时退出。按实际场景风格与最终asset文件核验同一灰色墙事实，并保存具体真值检查项；两个失败目录均保留。执行目录改为`language-robustness-v1-retry2-20261011`，文本、几何／视觉真值要求和5400次上限保持。
