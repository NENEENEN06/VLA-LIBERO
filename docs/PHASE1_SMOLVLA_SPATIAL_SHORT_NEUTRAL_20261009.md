# Spatial：简短中性句对照

2026-10-09，14:19（Asia/Shanghai）完成，退出码0。SmolVLA、Spatial task 8原双碗、init0、环境／策略seed=1；保留原版plate／ramekin指代。

**结果：追加 `The table is flat.` 后，两方向都未完成上盘子。简化这条追加句没有恢复操作，不能据此断定模型没理解ramekin。**

| init0方向 | 原版N（复用） | 长中性句＋空格（复用） | 短中性句＋空格（本次） |
| --- | --- | --- | --- |
| 盘子旁碗1 | 成功，第91步 | neither | neither |
| ramekin旁碗2 | 成功，第150步 | neither | neither |

`neither`表示300步内两只碗都没有触发独立的上盘子事件；不是“选错碗”的同义词。每条30次查询，完整保存300个动作和301个状态。

原指令逐字保留：

- `pick up the black bowl next to the plate and place it on the plate`
- `pick up the black bowl next to the ramekin and place it on the plate`

仅将长中性句 `Initially, the plate and the ramekin are both resting on the table surface.` 换为 `The table is flat.`，仍以一个ASCII空格拼接，保留原生末尾换行。有效token从33／35降为21／23，均无截断。桌面碰撞几何为水平薄盒，半尺寸0.5、0.6、0.025米，支持短句真值；这些模拟器信息只用于核查，没有输入策略。

盘子方向第64步短暂接触正确碗1，5个采样状态满足双侧指垫接触，最大抬升约3.0厘米、位移4.5厘米，但未完成放置。ramekin方向两碗均无双侧指垫接触，目标碗2最大抬升约1.2厘米、位移1.5厘米。接触指标不单独证明稳定抓握；本轮也没有出现上一轮ramekin方向接触并抬升非目标碗1的行为。

起始观测、模拟器状态和初始化SHA-256匹配旧对照；冻结运行器及四条复用episode哈希核验通过。两条各30批实际输入审计一致，目标事件已从逐步轨迹重新核验。保持原生360×360双相机／本体处理、20 Hz、每次执行10个动作、10步静置、硬重置及独立目标评估。

**新增60次策略查询、零新增诊断；旧N与长空格条件的120次查询只作复用。** 三轮中性句／拼接诊断合计新增180次，近期已知查询由1170增至1230；旧Goal中止成本未知，另列。本轮没有运行A/X/U正式矩阵或扩样。

缩短表达同时改变词汇、内容、时间限定，并移除了plate／ramekin名称重复，因此这不是纯长度消融，也不能单独归因于名称重复。它只说明本初始化下这条短追加句仍失败。A资格门槛仍未通过，当前结果不能作为正式Phase1冲突矩阵的放行依据。没有自动追加其他模板或初始化。

依据：[结果与旧对照](assets/phase1/smolvla-spatial-short-neutral-summary-20261009.json)、[冻结配置](assets/phase1/smolvla-spatial-short-neutral-manifest-20261009.json)、[真值／实际输入／状态预检](assets/phase1/smolvla-spatial-short-neutral-preflight-20261009.json)、[运行脚本](../scripts/check_phase1_smolvla_spatial_short_neutral.py)、[上一轮空格对照](PHASE1_SMOLVLA_SPATIAL_SEPARATOR_20261009.md)。末帧：[盘子方向](assets/phase1/smolvla-spatial-short-neutral-plate-end-20261009.png)、[ramekin方向](assets/phase1/smolvla-spatial-short-neutral-ramekin-end-20261009.png)。

完整视频、动作及事件位于本地 `outputs/phase1/smolvla-spatial-short-neutral-20261009/`；日志 `logs/phase1-smolvla-spatial-short-neutral-20261009.log`。
