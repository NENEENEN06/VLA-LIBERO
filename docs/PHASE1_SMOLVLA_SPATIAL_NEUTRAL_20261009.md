# Spatial 等长中性文本诊断

2026-10-09，13:30（Asia/Shanghai）完成，退出码0。独立诊断两条init0条件，未启动正式X/U矩阵。

**结果：两条中性句追加都失败，均为neither。A失败不能只归于farther／closer关系描述；一般追加效应、拼接和名称重复等因素尚未隔离。**

| init0方向 | 原版N（复用） | 正确事实A（复用） | 等长中性句（本次） |
| --- | --- | --- | --- |
| 盘子旁碗1 | 成功，第91步 | neither | neither，无放置事件 |
| ramekin旁碗2 | 成功，第150步 | neither | neither，接触并抬升非目标碗1，未完成放置 |

原版基础指令逐字保留。两条均按 `原指令 + 换行 + 以下中性句` 拼接，原生处理器追加末尾换行：

`Initially, the plate and the ramekin are both resting on the table surface.`

这句话只描述初始桌面支撑，不提供黑碗选择线索。实际有效token分别34／36，与对应旧A完全相同，无截断。没有修改分隔符、标点、场景或权重，也没有运行新的正确事实或冲突。

## 行为与核查

两条各观察300策略步、30次策略查询。ramekin方向第104步出现非目标碗1双侧指垫接触，79个采样状态满足接触，最大抬升约12.1厘米；目标碗2没有双侧指垫接触，位移仅数值级微动。盘子方向两只碗都没有双侧指垫接触。两条全程均未触发任一放置事件；接触是代理指标，不单独证明稳定抓握。

checkpoint、原生推理栈和冻结脚本摘要核对通过。初始观测、模拟器状态、初始化摘要与旧N/A完全一致；重置后的图像字节摘要匹配旧init0画面审阅记录。中性事实的桌面接触为真，实际N/A/中性输入审计与旧预检一致。

保持SmolVLA、Spatial task 8原双碗、init0、seed=1、hf-libero／MuJoCo 3.3.2、原生360×360双相机及本体处理、20 Hz、10步动作执行、10步静置、硬重置、300步上限与独立碗1／碗2放置事件。

## 当前结论与下一步

同一个初始化中，原版N成功，正确事实和中性追加均失败，说明本轮不能只用远近描述难度解释A失败。中性句仍提及盘子和ramekin，且与N同时改变了长度、换行和语义；不能据此确定唯一原因，也不判断文本／视觉主导。

下一步优先保持中性句和原指令完全不变，仅比较换行／空格拼接。该变化也会改变一个分隔token，实际长度需重新核查与记录。当前只完成这两条，没有自动启动拼接试验、增加初始化或修改模板；A门槛仍未通过。

**本轮新增2条完整rollout、60次策略查询、零新增诊断。** 旧N/A四条共120次查询只作复用，不重复计费；历史重置诊断亦复用。已知近期查询由1050增至1110，旧Goal中止成本未知，另列。单初始化探索不作总体成功率或普遍语言能力结论。

依据：[结果与旧N/A对照](assets/phase1/smolvla-spatial-neutral-summary-20261009.json)、[配置](assets/phase1/smolvla-spatial-neutral-manifest-20261009.json)、[状态／事实／输入预检](assets/phase1/smolvla-spatial-neutral-preflight-20261009.json)、[脚本](../scripts/check_phase1_smolvla_spatial_neutral.py)、[旧模板](PHASE1_SPATIAL_TEMPLATES_20261008.md)、[三初始化N/A](PHASE1_SMOLVLA_SPATIAL_NA_20261008.md)。

末帧：[盘子方向](assets/phase1/smolvla-spatial-neutral-plate-end-20261009.png)、[ramekin方向](assets/phase1/smolvla-spatial-neutral-ramekin-end-20261009.png)。完整视频、动作和逐步事件保存在本地 `outputs/phase1/smolvla-spatial-neutral-20261009/`；日志 `logs/phase1-smolvla-spatial-neutral-20261009.log`。本轮为正式矩阵之外的追加诊断，旧报告和预算不重复记样本。
