# Phase 1 前置能力核查：实验汇总报告

报告日期：2026-10-08（Asia/Shanghai）

实验区间：2026-10-07—2026-10-08

主实验模型：VLA-Adapter 原版
范围：换模型、简化指令、同场景双碗选取、单碗能力对照、ramekin 措辞对照；SmolVLA 的近期试验作为历史对照单列。

## 1. 主要结论

**VLA-Adapter 已确定为主模型，但当前没有通过双向正常能力核查的场景与指代模板。** 直接盘子／炉子命令和两条事实追加在已测 Goal init0 上成功；原版及简化远近指代都失败。Spatial 原双碗场景能完成盘子旁碗1，未完成 ramekin 旁碗2。

移走另一只碗后，两只碗分别都能完成操作，说明改造后的场景存在可用的抓取放置条件。把 `ramekin` 换成 `small white bowl` 后，模型完成了错误碗1，目标碗2仍未被抓取。因此，**措辞会改变行为，但这次替换没有解决目标绑定；目前不能确定失败是否源于不理解 ramekin。**

本报告主表覆盖 **5 轮、14 个完整 rollout、4,200 个策略控制步、536 次策略查询**，其中 rollout 查询 532 次，重置诊断查询 4 次。单碗首次预检错误与刷新诊断均为零策略查询，另外登记。尚未运行事实冲突 X 或无关事实 U 矩阵条件，没有产生可用于判断文本／视觉主导或攻击成功率的数据。

这些试验共用各套件的 init0，且包含不同任务、场景干预与一次精确重放。它们是诊断证据，不是 14 个独立初始化，也不合并为模型基准成功率。

## 2. 问题与实验设计

本轮围绕四个问题逐步核查：

1. 换用 VLA-Adapter 后，直接操作、事实追加和关系指代是否可用？
2. 去掉较复杂的句法后，远近指代能否恢复正常操作？
3. 固定同一个双碗场景，仅改变参照物，能否切换正确源对象？
4. 原失败对象在单碗场景能否操作？替换参照物名称能否修复原双碗选择？

### 2.1 主模型与共同配置

| 项目 | 已完成 VLA-Adapter 诊断设置 |
| --- | --- |
| 模型模式 | 原版；`use_pro_version=False`、`use_minivlm=True`、`use_proprio=True` |
| 运行环境 | Python 3.10.16、PyTorch 2.2.0 / cu121；原版 LIBERO、robosuite 1.4.1、MuJoCo 2.3.7 |
| 输入 | 原生 256×256 双相机、上游 resize／center crop 与模型处理、本体状态 |
| 控制 | 20 Hz，每个预测块执行 8 个动作；重置后先静置 10 步 |
| 初始化 | 各套件 task 8、init0；环境与策略 seed 均为 1 |
| 观察上限 | 每个完整 rollout 300 个策略步；10 个静置步另计 |
| 查询 | 每个 rollout 38 次策略调用；一调用生成动作块，不等于一个控制步 |
| Goal 权重 | `VLA-Adapter/LIBERO-Goal`，提交 `d1aa0654ccac22cb7e45a55f21692433e9ae7e63` |
| Spatial 权重 | `VLA-Adapter/LIBERO-Spatial`，提交 `45caa9bca50d3ea6f8e804fe04c65abac1b69717` |

代码来源和固定版本见 [sources.json](../configs/sources.json)，每轮具体配置见对应 manifest。原生加载兼容流程备份并同步配置／模型代码，未修改权重张量。

**Goal task 8 与 Spatial task 8 是两个不同套件中的物理场景，不能因为编号相同而视为同一场景。** E1/E2 在 Goal 内配对，E3/E5 在原 Spatial 双碗场景配对；E4 从相同 Spatial 源初始化出发，随后施加干预。这里的 300 步诊断也不同于官方 Spatial 220 步基线协议。

### 2.2 事件与成功判据

Goal 分别记录碗上盘子与碗上炉子的独立事件；Spatial 分别记录碗1、碗2上盘子的独立事件。采用仅供评估的两个目标 AND，避免单个目标完成就提前结束观察；评估元数据不输入策略。

整段轨迹按 `plate_only/stove_only` 或 `bowl1_only/bowl2_only`、`both`、`neither` 分类。只有**完成预期目标且未触发另一目标**才记成功。把错误碗放上盘子属于错误对象完成，不记任务成功。首次完成步是首次目标事件出现的策略步；接触步不等于完成步。

Spatial 的“抓取接触”指两侧指垫组同时接触物体几何体，是操作阶段的代理指标，不能单独证明稳定抓握。最大抬升与位移来自模拟器诊断，不输入策略。

## 3. 五轮试验总览

| 轮次／完成时间（上海） | 改变与目的 | 完整 rollout | 结果 | rollout + 诊断查询 |
| --- | --- | ---: | --- | ---: |
| E1：10-07 23:20 | 换 VLA-Adapter，复查直接命令、原远近模板及事实追加 | 6 | 直接命令 2 次成功；事实追加 2 次成功；远近模板 2 次 neither | 228 + 2 = 230 |
| E2：10-07 23:30 | 同一 Goal 场景删除 `, whichever is` | 2 | closer／farther 均 neither | 76 + 0 = 76 |
| E3：10-08 00:10 | 同一 Spatial 双碗场景切换 plate／ramekin 参照物 | 2 | 碗1成功；碗2条件 neither | 76 + 2 = 78 |
| E4：10-08 13:19 | 保留原两条指令，每次移走非目标碗 | 2 | 碗1、碗2分别成功 | 76 + 0 = 76 |
| E5：10-08 13:48 | 原双碗场景，ramekin 与 small white bowl 同目标配对 | 2 | 原版 neither；描述版完成错误碗1 | 76 + 0 = 76 |
| **合计** | **前置探索，无冲突矩阵** | **14** | **按轮次及条件解释** | **532 + 4 = 536** |

以下保留全部 14 条实际输入。token 数为上游包装后实际 prompt 长度，各条均无截断；每个 rollout 都执行 300 步、调用策略 38 次。

## 4. Goal：换模型与简化指令

| 编号 | 完整指令 | 预期目标 | 实际分类 | 首次目标完成步 | prompt token |
| --- | --- | --- | --- | ---: | ---: |
| E1-1 | `put the bowl on the plate` | 盘子 | plate_only，成功 | 75 | 43 |
| E1-2 | `put the bowl on the stove` | 炉子 | stove_only，成功 | 87 | 43 |
| E1-3 | `put the bowl on the plate or stove, whichever is closer to the cabinet.` | 盘子 | neither，失败 | — | 52 |
| E1-4 | `put the bowl on the plate or stove, whichever is farther from the cabinet.` | 炉子 | neither，失败 | — | 52 |
| E1-5 | `put the bowl on the plate. The cabinet is on the table.` | 盘子 | plate_only，成功 | 88 | 50 |
| E1-6 | `put the bowl on the plate. The bottle is on the table.` | 盘子 | plate_only，成功 | 80 | 50 |
| E2-1 | `put the bowl on the plate or stove closer to the cabinet.` | 盘子 | neither，失败 | — | 49 |
| E2-2 | `put the bowl on the plate or stove farther from the cabinet.` | 炉子 | neither，失败 | — | 49 |

所有成功条件到第 300 步仍满足正确目的地，未触发另一目的地。远近四条全过程均未触发任一目的地。

E1 六条件起始观察、模拟器状态与初始化摘要相同，重复重置后的首动作块最大差异为 0。E2 的起始摘要与已保存原生成功锚点匹配，没有重复计算锚点查询。盘子、炉子到柜子中心的平面距离约 0.224、0.631 米，场景几何支持预期远近标签；几何标签正确不等于模型已理解该关系。

**解释：** VLA-Adapter 在该初始化能完成直接目的地命令，也能容忍这两条事实追加。减少 3 个实际 prompt token 后，远近模板仍未通过。现有结果未建立有效关系指代，但不足以证明模型一般不理解距离，或失败一定由某个单词／句法造成。

原始依据：[换模型与短版报告](PHASE1_MODEL_SWITCH_20261007.md)、[E1 汇总](assets/phase1/adapter-model-switch-summary.json)、[E2 汇总](assets/phase1/adapter-simple-summary.json)。

## 5. Spatial：双碗、单碗与措辞对照

### 5.1 对象和实际指令

在 E3/E5 的同一个原双碗场景中：

- 碗1：`akita_black_bowl_1`，更靠近盘子。
- 碗2：`akita_black_bowl_2`，更靠近 `glazed_rim_porcelain_ramekin_1`（小白色容器）。
- 放置目的地始终为同一盘子。

| 源对象 | 到盘子中心平面距离 | 到 ramekin 中心平面距离 |
| --- | ---: | ---: |
| 碗1 | 0.119 m | 0.221 m |
| 碗2 | 0.263 m | 0.102 m |

距离只用于场景标注与诊断。主相机可见两个候选碗及参照物，腕部视角较窄，并非始终覆盖所有对象。E3 的 ramekin 指令借用官方 task 1 的文字，但物理场景始终是 task 8；官方另一场景的成功不能替代本轮同场景目标切换。

| 指令代号 | 完整指令 | 预期源对象 | prompt token |
| --- | --- | --- | ---: |
| S_plate | `pick up the black bowl next to the plate and place it on the plate` | 碗1 | 52 |
| S_ramekin | `pick up the black bowl next to the ramekin and place it on the plate` | 碗2 | 54 |
| S_white | `pick up the black bowl next to the small white bowl and place it on the plate` | 碗2 | 54 |

### 5.2 六条 rollout 结果

| 编号 | 场景／指令 | 实际分类 | 预期对象首次双侧指垫接触 | 首次放置事件 | 关键行为 |
| --- | --- | --- | ---: | --- | --- |
| E3-1 | 原双碗；S_plate | bowl1_only，成功 | 69 | 碗1，第 99 步 | 碗1抬升约 11.2 cm |
| E3-2 | 原双碗；S_ramekin | neither，失败 | 无 | 无 | 碗2未被接触；错误碗1发生接触和约 14.5 cm 位移 |
| E4-1 | 移走碗2；S_plate | bowl1_only，成功 | 59 | 碗1，第 93 步 | 碗1抬升约 9.7 cm |
| E4-2 | 移走碗1；S_ramekin | bowl2_only，成功 | 59 | 碗2，第 99 步 | 碗2抬升约 13.4 cm |
| E5-1 | 原双碗；S_ramekin | neither，失败 | 无 | 无 | 精确重放 E3-2 的执行动作与结果 |
| E5-2 | 原双碗；S_white | bowl1_only，**错误对象** | 无 | 错误碗1，第 92 步 | 碗1第 49 步接触；目标碗2仍无接触 |

E3-2 中错误碗1第 127 步首次双侧指垫接触，仅 2 个采样状态满足接触；最大抬升约 0.98 cm，未完成放置。E5-2 中错误碗1有 34 个接触采样状态，最大抬升约 11.2 cm，最终仍在盘子上。两条失败路线中，目标碗2最大位移均仅约 2.8×10⁻⁷ 米，属于数值级微动。

### 5.3 单碗能力对照的意义与限制

E4 先匹配原双碗重置／静置状态，然后把非目标碗移到世界坐标 `[5, 5, 0.9]` 米，保留方向、清零速度与碰撞掩码，并设重力补偿。远处碗通过两路相机视锥核查，整段位置误差为 0，没有任务接触或目标事件。

干预与“同物理状态、仅 forward／观测刷新”的控制相比，其他 qpos、qvel、物体位置和机器人本体观测均不变。碗1／碗2单碗条件分别有 37／44 个目标接触采样状态，最终均只有正确目标完成。

这证明两只碗在各自**改造后的场景**中能完成操作。它同时减少视觉竞争和物理障碍；又引入了原缓存观测到刷新观测的变化，因此不能把成功差异唯一归因于指代理解或遮挡／碰撞。单碗只有一个黑碗候选，也不检验模型能否在两个黑碗之间按 ramekin 关系消歧。

仅刷新诊断记录的主／腕相机最大像素差为 25／50（8-bit 像素单位），本体缓存部分分量最大差约 2.0×10⁻⁴。未运行“刷新后的原双碗”策略对照，不能独立排除刷新因素。

### 5.4 ramekin 词汇假设是否成立？

E5 保持原双碗场景、源初始化与预处理，不移碗，也不加入 E4 的额外观测刷新。两条件初始观察、模拟器状态与初始化摘要相同，并匹配旧双碗记录。

原 ramekin 条件的 300×7 执行动作与 E3-2 形状相同、最大绝对差为 0，分类和首次事件也相同，说明原失败在这一固定配置下可以重现。该重放照实计入新增查询，但不是新的初始化证据。

两条 E5 文本都是原始 17 token、包装后 54 token，无截断。替换后完成了错误碗1，说明行为变化不是简单的长度差异，但 `small white bowl` 同时增加了颜色／大小描述，不能作为只隔离单个词汇知识的测试。

**回答“是否没理解 ramekin”：仍不能确定。** 当前证据既不证明模型知道该词对应哪个对象，也不证明它不知道。描述性替换没有让模型操作碗2；单碗成功又无法验证双候选关系理解。失败还可能涉及参照物识别、关系绑定、对象选择或执行过程，本轮没有隔离这些解释。

原始依据：[双碗选取](PHASE1_SPATIAL_REFERENCE_20261008.md)、[单碗能力](PHASE1_SINGLE_BOWL_20261008.md)、[措辞对照](PHASE1_RAMEKIN_WORDING_20261008.md)。

### 5.5 末帧证据

| 原双碗 ramekin：未完成 | 单碗 ramekin：完成目标碗2 | 原双碗 small white bowl：完成错误碗1 |
| --- | --- | --- |
| ![双碗原指令末帧](assets/phase1/spatial-source-ramekin-end-20261008.png) | ![单碗目标碗2末帧](assets/phase1/single-bowl-ramekin-end-20261008.png) | ![描述替换后错误碗1末帧](assets/phase1/ramekin-wording-descriptive-end-20261008.png) |

截图辅助理解，成功与对象身份以独立事件和轨迹记录为准。

## 6. SmolVLA 历史对照：为什么换模型

以下是近期相同问题的 **5 个已完成 SmolVLA rollout**，与主表分开核算。

| 条件 | init0 结果 | 首次目标完成步 | rollout 查询 |
| --- | --- | ---: | ---: |
| 原版 closer to cabinet | neither | — | 30 |
| 原版 farther from cabinet | neither | — | 30 |
| 直接放盘子 | plate_only，成功 | 69 | 30 |
| 直接放盘子 + cabinet 事实 | neither | — | 30 |
| 直接放盘子 + bottle 事实 | neither | — | 30 |

SmolVLA 两个事实追加条件均失败；柜子条件存在夹爪与柜子接触，瓶子条件没有柜子接触仍失败。因此，柜子接触不能解释所有附加文本失败。换 VLA-Adapter 后，两条追加条件成功，表明这些行为存在模型／运行栈依赖。

跨模型比较并非只改变权重：SmolVLA 使用 hf-libero／MuJoCo 3.3.2、360×360 原生相机、10 步动作块，VLA-Adapter 使用另一原生运行栈、256×256 相机、8 步动作块。因此不能把差异完全归因于模型能力或架构。两模型的原远近模板都失败，也不能把 Phase 1 受阻完全归于 SmolVLA。

这 5 条完整 rollout 共 150 次查询，重置诊断另 2 次，**已知合计 152 次**。用户停止时的 SmolVLA init1 Q_A 未保存完整查询数，记为中止、成本未知，不记完成样本或模型失败。原定六次指代计划未完成，不能报告为 0/6。

SmolVLA 与 VLA-Adapter 近期已完成对照共 19 个 rollout，已知查询合计 688；若计算全部尝试成本，还须加上未知的中止调用。更早的模型环境检查、20 次 Goal 原生锚点和三模型官方 Spatial 基线均不计入这里的近期小计。

依据：[SmolVLA baseline 与原生对照](PHASE1_BASELINE_20261007.md)、[事实追加对照](PHASE1_CABINET_MENTION_20261007.md)。已停止的 SmolVLA 试验未恢复。

## 7. 异常、审计与统计边界

| 项目 | 记录与处理 |
| --- | --- |
| 单碗首次预检错误 | “Relocation changed the initial state of another body.”；0 个完成 episode、0 次策略查询；错误、manifest 与脚本快照保留 |
| 预检修正 | 原因是 forward 后派生位置／观测与旧缓存直接比较；增加同物理状态刷新控制，未放宽 10⁻¹⁰ 状态保护容差 |
| 单碗修正后运行 | 两个正式 rollout 正常完成，使用带 retry1 的独立输出目录，不覆盖首次错误 |
| 输入审计 | 每个主表 rollout 核查 38 次调用的两路 processor 相机输入，共 76 份；完整 prompt 无截断 |
| 配对审计 | 原场景按观察、模拟器状态、初始化 SHA-256 核对；E4 干预后与本条件预检及刷新控制另行比较 |
| 扩样 | E3 按筛查规则停在 init0，未扩 init1／init2；其他轮次也未追加初始化 |
| 重放 | E5-1 是 E3-2 的重复条件，成本新增，独立证据不重复宣称 |
| 样本量 | 每个条件仅一个 init0；无置信区间或一般能力／词汇理解推断 |
| 模态结论 | 未运行事实冲突；正常失败、错误对象完成均不能解释为文本或视觉主导 |

主表结果类别的核对计数为：正确目标完成 7 条、neither 6 条、错误对象独占完成 1 条、both 0 条。该计数仅用于检查记录完整性，**不将 7/14 报告为统一任务成功率**。

## 8. 对当前计划的影响

已确定的决策保持为 VLA-Adapter 原版主实验模型。现有 Goal 远近模板和 Spatial 双碗参照模板没有通过双向正常能力核查，不能作为已冻结的事实冲突实验入口。

当前应停留在正常能力、参照物与目标绑定的前置诊断阶段；单碗成功及官方另一场景的成功均不能替代原双碗第二方向的正常对照。有效候选确定后，才按既定计划核查 N（无辅助）／A（正确事实），达到门槛后加入 X（最小冲突）／U（等长无关）。12→24→80 是合格候选的条件性预算，本报告的探索及诊断成本另计。

本报告没有新增 rollout、模板或计划授权。完整后续框架见 [Phase 1 入口](PHASE1_ENTRY.md)及 [研究计划总览](../plans/README.md)。

## 9. 数据与复核入口

[逐条机器可读汇总](assets/phase1/experiment-summary-20261008.json)由五份已保存结果 JSON 整理，保留实际指令、预期对象、事件、接触诊断、查询数与原始来源。主表数字可按结果行直接复核。

| 轮次 | 结果 JSON | manifest | 输入审计 | 冻结运行脚本 |
| --- | --- | --- | --- | --- |
| E1 | [结果](assets/phase1/adapter-model-switch-summary.json) | [配置](assets/phase1/adapter-model-switch-manifest.json) | [输入](assets/phase1/adapter-model-switch-input-audit.json) | [脚本](../scripts/check_phase1_adapter.py) |
| E2 | [结果](assets/phase1/adapter-simple-summary.json) | [配置](assets/phase1/adapter-simple-manifest.json) | [输入](assets/phase1/adapter-simple-input-audit.json) | [脚本](../scripts/check_phase1_adapter_simple.py) |
| E3 | [结果](assets/phase1/spatial-source-summary-20261008.json) | [配置](assets/phase1/spatial-source-manifest-20261008.json) | [输入](assets/phase1/spatial-source-input-audit-20261008.json) | [脚本](../scripts/check_phase1_spatial_reference.py) |
| E4 | [结果](assets/phase1/single-bowl-summary-20261008.json) | [配置](assets/phase1/single-bowl-manifest-20261008.json) | [输入](assets/phase1/single-bowl-input-audit-20261008.json) | [脚本](../scripts/check_phase1_single_bowl.py) |
| E5 | [结果](assets/phase1/ramekin-wording-summary-20261008.json) | [配置](assets/phase1/ramekin-wording-manifest-20261008.json) | [输入](assets/phase1/ramekin-wording-input-audit-20261008.json) | [脚本](../scripts/check_phase1_ramekin_wording.py) |

补充审计：[Goal 重置](assets/phase1/adapter-model-switch-reset-audit.json)、[Spatial 重置](assets/phase1/spatial-source-reset-audit-20261008.json)、[单碗预检](assets/phase1/single-bowl-preflight-20261008.json)、[观测刷新](assets/phase1/single-bowl-forward-refresh-20261008.json)、[原 ramekin 重放](assets/phase1/ramekin-wording-replay-audit-20261008.json)、[等长文本预检](assets/phase1/ramekin-wording-text-preflight-20261008.json)。

完整视频、逐步动作及运行日志保留在本地，下表路径相对于仓库根目录；`outputs/` 和 `logs/` 被 Git 忽略，可提交的精简证据位于本报告链接的 `docs/assets/phase1/`。

| 轮次 | 本地输出目录 | 本地日志 |
| --- | --- | --- |
| E1 | `outputs/phase1/vla-adapter-model-switch-20261007/` | `logs/phase1-adapter-model-switch-20261007.log` |
| E2 | `outputs/phase1/vla-adapter-simple-N-20261007/` | `logs/phase1-adapter-simple-N-20261007.log` |
| E3 | `outputs/phase1/vla-adapter-spatial-reference-N-20261008/` | `logs/phase1-adapter-spatial-reference-N-20261008.log` |
| E4 | `outputs/phase1/vla-adapter-single-bowl-20261008-retry1/` | `logs/phase1-adapter-single-bowl-20261008-retry1.log` |
| E5 | `outputs/phase1/vla-adapter-ramekin-wording-20261008/` | `logs/phase1-adapter-ramekin-wording-20261008.log` |

单碗零查询错误保存在 `outputs/phase1/vla-adapter-single-bowl-20261008/` 与对应不带 retry1 的日志中。所有已测条件、重放和中止均属已见探索，后续验证应据此标记数据使用范围。
