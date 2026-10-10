# OpenVLA Spatial 4-bit：原生ramekin任务诊断规则

2026-10-10，用户同意补原生ramekin任务对照。以下在策略查询前冻结，历史task8核查不改写。

使用同一官方Spatial权重、FP4／float32计算、SDPA、单agentview相机、原生图像和动作转换。复用已通过的运行配置，不复用任何策略动作或任务结果。模型固定版本及依赖见[候选入口](OPENVLA_SPATIAL_4BIT_ENTRY.md)。

本轮用官方`libero_spatial` task1自己的BDDL场景和初始化0、1、2，指令仍为`pick up the black bowl next to the ramekin and place it on the plate`。这里ramekin旁的原生目标为`akita_black_bowl_1`；之前task8换指令的目标为`akita_black_bowl_2`。两个场景与物体布局不同，同编号初始化不构成跨场景状态配对。

环境／策略seed=1、硬重置、10步静置，每次预测一步动作，每条最多300步，原生目标成功则结束。三条均运行，最多900次新增rollout查询，零额外策略诊断。300步沿用当前核查上限，区别于官方Spatial评测的220步；同时报告成功步数，避免混淆官方评测口径。

查询前验证原生目标、ramekin最近碗为碗1且与另一碗的XY距离差至少0.05米、目标初始未满足、原生完整文本与实际裁剪图像；查看三个真实224模型输入图后才开始。每条重置须与本轮已审阅预检的初始状态、观察及模型输入一致。

主要成功指标沿用task1原生`On(bowl1, plate)`及原生终止条件，保留接触、高度和XY中心距小于3厘米三个条件。另记两碗独立ever事件、是否正确独占、首次双侧指垫接触、抬升／位移及每步放置分量。接触和抬升仅作动作诊断，不等于理解指代或完成任务。

三条至少2/3原生成功，只支持本配置在所测原生任务具备执行能力。若通过而task8换目标仍失败，优先核查任务／场景迁移；若失败，再考虑单独的量化配置对照。本轮不是Phase1资格样本，不自动启动A、X/U、扩样或模型晋升。旧task8 N盘子2/3、ramekin0/3继续保留。

运行器：[原生诊断](../scripts/check_openvla_native_ramekin.py)，共享原生后端与轨迹接触记录。启动：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-ramekin --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-ramekin-20261010 --readiness /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/readiness-retry2-20261009
```

运行器先停在`awaiting_visual_review`，审阅者在输出目录写入包含预检文件SHA-256、三个初始化记录及`passed`字段的`preflight-image-review.json`后继续。此步骤是内部画面核查，无策略查询。
