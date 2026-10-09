# Spatial 中性句：换行与空格拼接对照

2026-10-09，13:59（Asia/Shanghai）完成，退出码0。SmolVLA、Spatial task 8原双碗、init0、原版plate／ramekin指代；独立诊断两条空格版条件，未运行正式冲突矩阵。

**结果：改为空格后，两方向仍为neither。仅替换这个换行没有恢复操作，不能把先前失败只归于该换行；追加内容、长度和名称重复等因素仍未隔离。**

| init0方向 | 原版N（复用） | 换行中性句（复用） | 空格中性句（本次） |
| --- | --- | --- | --- |
| 盘子旁碗1 | 成功，第91步 | neither | neither |
| ramekin旁碗2 | 成功，第150步 | neither，操作了非目标碗1 | neither，仍操作了非目标碗1 |

## 唯一文本编辑与实际输入

原指令和中性句逐字不变，只将二者之间的一个换行字符替换为空格；不添加句号或新词。中性句仍为：

`Initially, the plate and the ramekin are both resting on the table surface.`

原生处理器添加的末尾换行继续保留，episode内文本不变。

| 有效token | 盘子方向 | ramekin方向 |
| --- | ---: | ---: |
| 原版N | 16 | 18 |
| 换行追加 | 34 | 36 |
| 空格追加 | 33 | 35 |

两条都少了1个有效token，完整解码一致、无截断，因此这不是等token的纯排版消融。报告的是分隔字符及相应编码变化。

起始观测、模拟器状态与初始化SHA-256均匹配旧N和换行条件，旧输入审计也完全匹配。初始中性事实的桌面支撑为真；原双相机观测匹配已有画面审阅记录。冻结脚本与模型来源核对通过，没有修改旧运行器文件；新进程仅为新条件替换文本构造函数，动作生成、预处理和评估保持原路径。

## 行为与边界

两条均观察300策略步、调用30次策略。盘子方向两只碗均没有双侧指垫接触；ramekin方向第104步接触非目标碗1，80个采样状态满足双侧接触，最大抬升约16.2厘米。目标碗2没有双侧指垫接触，但有约3.6厘米位移，不能说完全未动。两条都没有触发任何上盘子事件；接触指标不单独证明稳定抓握。

保持hf-libero／MuJoCo 3.3.2、原生360×360双相机及本体处理、20 Hz、10步动作执行、10步静置、硬重置、环境／策略seed=1和原独立目标事件。

本轮只说明这个初始化、这组中性句的空格替换未修复失败，不证明所有拼接方式都无效，也不能判断文本／视觉主导。A门槛仍未通过，正式X/U、扩样和其他模板没有启动。后续可先测试更简短的中性追加；缩短表达也会改变词汇和内容，应另立诊断并冻结，不当作纯长度消融。本轮没有自动运行该后续步骤。

**新增2条完整rollout、60次策略查询、零新增诊断。** 旧N与换行条件四条的120次查询仅作复用，不重复计费。两轮中性／拼接诊断共新增120次；已知近期查询由1110增至1170，旧Goal中止成本未知，另列。

依据：[结果与旧对照](assets/phase1/smolvla-spatial-separator-summary-20261009.json)、[冻结配置](assets/phase1/smolvla-spatial-separator-manifest-20261009.json)、[字符编辑／实际输入／状态预检](assets/phase1/smolvla-spatial-separator-preflight-20261009.json)、[脚本](../scripts/check_phase1_smolvla_spatial_separator.py)、[上一轮中性追加](PHASE1_SMOLVLA_SPATIAL_NEUTRAL_20261009.md)。末帧：[盘子方向](assets/phase1/smolvla-spatial-separator-plate-end-20261009.png)、[ramekin方向](assets/phase1/smolvla-spatial-separator-ramekin-end-20261009.png)。

完整视频、动作和逐步事件保存在本地 `outputs/phase1/smolvla-spatial-separator-20261009/`；日志 `logs/phase1-smolvla-spatial-separator-20261009.log`。本轮独立计费，不加入正式12→24→80矩阵的样本数。
