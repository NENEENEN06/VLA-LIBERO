# OpenVLA Phase1候选：原生任务内配对v1

2026-10-10。用户同意按原生任务内配对继续核查；本协议在新增策略查询前冻结。具体英文稿与参数见[配置](../configs/phase1-openvla-native-pairs-v1.json)。

研究范围改为“固定原生任务的场景、目标和指令，观察追加事实对执行的影响”。task1保留ramekin原句，task8保留plate原句；两任务均保留官方双碗和自身初始化0、1、2。条件只在同一任务／初始化内恢复同一状态，跨任务不宣称同一画面或双向换目标。旧task8同场景两指令失败及SmolVLA冻结协议保持历史范围，新结果另计。

模型继续使用OpenVLA Spatial 4-bit FP4／float32计算、SDPA、单agentview相机、原生图像和动作处理。环境／策略seed=1、硬重置、10步静置、每次调用一步动作、300步上限。保持每个任务原生`On(bowl1, plate)`及终止条件，不改成两碗AND；另记两碗ever事件，正常成功须仅正确碗1完成。观察窗口为原生成功或上限，因此不能与旧共享AND的300步统计直接合并。

| 任务 | 基础指令N | 正确事实A | 冲突事实X |
| --- | --- | --- | --- |
| task1 ramekin | `pick up the black bowl next to the ramekin and place it on the plate` | `Initially, the black bowl farther from the cookies is next to the ramekin.` | `Initially, the black bowl closer to the cookies is next to the ramekin.` |
| task8 plate | `pick up the black bowl next to the plate and place it on the plate` | `Initially, the black bowl farther from the ramekin is next to the plate.` | `Initially, the black bowl closer to the ramekin is next to the plate.` |

U两任务均为`Initially, the plate and the ramekin are both resting on the table surface.`。拼接为原指令＋一个换行＋事实，episode内固定，原生入口小写包装。A/X用farther from／closer to作关系替换；不添加新动作命令。task1另一碗原生靠近cookies，选择该独立参照物；plate距离关系不沿用到task1。

实际token预核查：task1 N32，A/X/U均52；task8 N30，A/X/U均50。部署预检再用真实处理器验证完整文本、相机张量和无截断，不套用SmolVLA的48-token上限。几何真值要求正确碗到Q参照物更近、到辅助参照物更远，两项距离差均至少0.05米；X唯一指向另一只碗。U通过两个物体与table_collision的实际接触核查。六个初始化的真实模型图须审阅两碗、参照物和目的地均可辨认。

复用先前[原生task1诊断](OPENVLA_NATIVE_RAMEKIN_20261010.md)的全部三条N，原329次查询只计一次。模型／处理／状态／指令／seed／步数上限／原生终止与独立事件须逐项一致，保存episode文件SHA、来源manifest与输入／状态核对；有任一不一致则在新增rollout前停止。旧task8的共享AND终止不同，三条N重新运行。

核查顺序：六状态N/A/X/U零查询预检与图像审阅；确认task1三条N的完整来源；重新运行task8三条N；两个任务N各至少2/3后，运行两任务各三条A。四个任务×N/A块各至少2/3才说明本新候选正常条件通过。这是已见探索推进门槛，不证明稳定能力或事实语义理解。N不通过则不运行A；A未运行不是0/3失败。

最多新增9条／2700次rollout查询，零额外策略诊断；三条旧N与329次旧成本明确单列。失败、异常和中止均保留，不按结果替换初始化、文本或延长上限。本轮只完成N/A前置核查，X/U仅预检，行为查询为0；没有自动扩样或主模型晋升。新候选通过不能改写旧同场景双向资格。

运行器：[任务内配对](../scripts/check_openvla_native_pairs.py)。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-pairs --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010 --native-N /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-ramekin-20261010
```

运行器生成预检后等待输出目录中的`preflight-image-review.json`，审阅通过并引用当前预检SHA才开始rollout。manifest冻结配置、文档、源代码及依赖哈希；完整轨迹、输入、事件及查询成本另存。
