# 当前进度与接续

更新时间：2026-10-08（Asia/Shanghai）。工作目录：C:\VLA-LIBERO；WSL：/mnt/c/VLA-LIBERO。

## 当前已确定的决策

用户已确定将主实验模型从 SmolVLA 改为 **VLA-Adapter 原版**。能力核查、Phase 1 行为诊断及后续发现／搜索原型均以 VLA-Adapter 为主；SmolVLA 的已完成资料保留，SmolVLA 与 PulseVLA-LIBERO 为后续验证候选，具体顺序和任务范围待各自能力核查后确定。

目前确定的是模型角色，**尚无通过双向正常能力核查的 Phase 1 场景和指代模板**。原研究框架和黑盒权限保持；有效场景、Q_A/Q_B、辅助事实及最终样本范围仍待核查与冻结。本次仅改写计划，不新增试验，也不恢复此前停止的候选。

当前计划见 [总览](../plans/README.md)、[主模型与能力核查](../plans/黑盒跨模态攻击/03_模型选择与基线准备.md)、[路线与预算](../plans/黑盒跨模态攻击/07_实施路线与查询预算.md)及 [Phase 1 入口](PHASE1_ENTRY.md)。

## VLA-Adapter 已完成的候选核查

| 运行 | 结果 | 完整 rollout／查询成本 | 报告 |
| --- | --- | --- | --- |
| Goal task 8、init0：原生命令、远近指代、事实追加 | 盘子／炉子直接命令成功；远近指代失败；柜子／瓶子事实追加成功 | 6 次，228 次 rollout 查询 + 2 次诊断 | [换模型报告](PHASE1_MODEL_SWITCH_20261007.md) |
| 同一 Goal 场景短版指代 | closer／farther 两条均 neither | 2 次，76 次查询，零诊断 | 同上短版追加 |
| Spatial task 8、init0：next to 双向选碗 | 碗1条件第 99 步完成；碗2条件 neither，目标碗2无双侧指垫接触、非目标碗1位移约 14.5 厘米 | 2 次，76 次 rollout 查询 + 2 次诊断 | [Spatial 报告](PHASE1_SPATIAL_REFERENCE_20261008.md) |

合计 10 个完整 rollout、380 次 rollout 策略查询及 4 次诊断，总查询 384；均正常退出、无本轮中止。初始状态配对、重置重现和文本输入核查均通过。现有失败结果限于已测初始化与模板，不证明模型一般不理解距离或具有普遍对象偏好，也不能解释为图文主导。

Spatial 选碗按预定规则停在 init0，未补 init1／init2；第二条只借用了官方 task 1 的文字，物理场景仍是 task 8。官方不同场景的任务成功不能替代共享场景换目标。当前尚未运行四条件冲突矩阵。

本地输出和日志：

- Goal 六次：`outputs/phase1/vla-adapter-model-switch-20261007/`、`logs/phase1-adapter-model-switch-20261007.log`。
- Goal 短版：`outputs/phase1/vla-adapter-simple-N-20261007/`、`logs/phase1-adapter-simple-N-20261007.log`。
- Spatial 选碗：`outputs/phase1/vla-adapter-spatial-reference-N-20261008/`、`logs/phase1-adapter-spatial-reference-N-20261008.log`。

## 下一步与推进边界

在 VLA-Adapter 上继续核查新候选的任务语义、正常操作与同场景目标绑定，先明确有效的候选对象／目的地、自然指代和独立事件。具体场景与英文模板确定后，冻结小规模范围与停止规则；无效候选保留数据并停止扩样，不直接重跑旧候选以凑成功样本。

通过前置核查后，再冻结 N 无辅助、A 正确事实、X 最小冲突和 U 等长无关四条件。12→24→80 是合格候选的条件性矩阵预算，候选尝试及诊断另计；N/A 各块达到预定探索门槛后才加入 X/U。不能把直接命令成功、另一模型的基线或另一物理场景的成功填作当前指代对照。

主模型使用对应套件固定权重、原版 LIBERO、原生双相机及本体处理、8 步动作执行和 10 步静置；当前 Spatial、Goal 权重已配置。相机、随机种子、终止上限和独立事件按每次运行 manifest 冻结。正式基线遵循官方套件协议，已有配对 300 步诊断与官方 Spatial 220 步基线分开报告。

## 保留的历史与已见探索

- 三模型环境、CUDA、双相机、策略输出及短程闭环均已验证；[配置状态](SETUP_STATUS.md)。
- 三模型 Spatial 每任务一次：SmolVLA 8/10、VLA-Adapter 10/10、PulseVLA 9/10；[Spatial 基线](SPATIAL_BASELINE_20261006.md)。
- SmolVLA 前期 49 次及 Object 身份切换 0/3；[前期核查](SMOLVLA_READINESS_20261006.md)。
- SmolVLA 共享 Goal 原生盘子／炉子各 10/10 是该模型原生目标锚点，不能证明新指代或 VLA-Adapter 能力；[Goal 核查](SMOLVLA_GOAL_CHECK_20261007.md)。
- SmolVLA N-only 的 init0 两条失败，随后 init1 Q_A 被用户要求停止，部分查询成本未知，不补跑也不计完成样本；原生盘子对照成功；[baseline 对照](PHASE1_BASELINE_20261007.md)。
- SmolVLA 柜子／瓶子事实追加均失败；[提及核查](PHASE1_CABINET_MENTION_20261007.md)。

旧暂停与原生成功的推进判断仅属历史，当前主模型与前置状态以上述决策为准。原脚本、日志和结果保留，全部已试任务、初始化、模板及中止尝试登记为已见探索，不冒充独立留出数据。
