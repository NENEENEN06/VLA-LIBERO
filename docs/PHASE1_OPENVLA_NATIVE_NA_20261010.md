# OpenVLA原生任务内配对：N/A核查

2026-10-10，14:40（Asia/Shanghai）完成，退出码0。**两个原生任务N通过探索门槛，A均0/3，正常条件仍未通过；X/U仅预检，没有运行行为。**

| 原生任务 | N 原指令 | A 正确事实追加 |
| --- | --- | --- |
| task1 ramekin | 3/3成功，复用已核验的三条N | 0/3，全部neither |
| task8 plate | 2/3成功，三条重新运行 | 0/3，全部neither |

两任务各用自己的官方双碗场景、初始化0、1、2和原版指令，目标均为各自碗1。同一任务／初始化内，N与A的起始观察、状态、实际图像和评价规则一致；跨任务不宣称同一画面。沿用300步上限、原生On判据及原生成功终止，正确碗独占完成才计正常成功。旧task8同场景换目标资格不改写。

| 任务／初始化 | N结果 | A失败环节 |
| --- | --- | --- |
| ramekin init0 | 第114步成功，旧N | 正确碗接触并抬升16.8厘米；终点接触盘子且高度成立，中心距3.56厘米超过3厘米上限 |
| ramekin init1 | 第99步成功，旧N | 两只黑碗均无双侧指垫接触或明显运动 |
| ramekin init2 | 第116步成功，旧N | 正确碗第77步接触、抬升5.5厘米，未完成搬运和放置 |
| plate init0 | 第107步成功，新N | 正确碗抬升9.2厘米但无双侧接触记录；终点接触盘子且高度成立，中心距3.22厘米超限 |
| plate init1 | 第105步成功，新N | 正确碗接触并抬升12.9厘米；终点接触盘子且高度成立，中心距3.95厘米超限 |
| plate init2 | neither，新N | 两只黑碗均无双侧指垫接触或明显运动 |

六条A均没有错误碗上盘子或错误碗双侧接触事件。接触指标不单独证明稳定抓握，也不能把无黑碗接触解读为已选择正确目标。三条靠近盘子的失败仍按原生3厘米判据记录，没有事后放宽标准。

事实真值、唯一替代对象、U桌面接触及六张真实224输入图均通过预检；task8 init1目标在裁剪左边缘部分被截但可辨认，该限制保留。N有效token为32／30，A/X/U分别52／50且任务内等长；全部新查询完整、无截断。模型继续为同一OpenVLA Spatial FP4／SDPA配置；输入、状态、源配置、事件、轨迹和成本已独立复核。

**原生场景能执行原指令，但当前正确事实追加载体仍不可用。** 失败包含未建立黑碗接触、接触后搬运失败及放置位置偏差，不能统一归因于ramekin理解、关系词理解或模型尺寸。本轮没有中性追加行为对照，还不能区分一般文本追加敏感与当前关系事实内容的影响。

下一步建议另立同长度中性追加诊断：两个原生任务各用init0一条U，与本轮N/A作已见参考，最多新增600次查询。先冻结独立诊断预算和来源核对，再运行；这不是正式X/U矩阵，不绕过A门槛。当前所有新rollout已结束。

**本轮新增9条完整rollout、2312次查询：task8 N为107＋105＋300＝512次，六条A各300次＝1800次；零额外策略诊断。** 三条旧task1 N与329次旧成本只复用一次，不重复计费；12个正常条件记录对应2641次来源查询，实际新增仅2312次。OpenVLA已登记至少4825次，近期研究口径至少6055次，旧断电尾部及旧Goal中止未知成本仍单列，更早环境／套件基线不在此口径内。

依据：[冻结协议](PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md)、[结果](assets/phase1/openvla-native-pairs-v1-summary-20261010.json)、[配置与版本](assets/phase1/openvla-native-pairs-v1-manifest-20261010.json)、[预检](assets/phase1/openvla-native-pairs-v1-preflight-20261010.json)、[画面核查](assets/phase1/openvla-native-pairs-v1-visual-review-20261010.json)、[旧N复用核验](assets/phase1/openvla-native-pairs-v1-N-reuse-audit-20261010.json)、[独立结果复核](assets/phase1/openvla-native-pairs-v1-result-audit-20261010.json)、[task8起始状态对照](assets/phase1/openvla-native-pairs-v1-plate-N-start-comparison-20261010.json)。

完整轨迹、动作、视频：`outputs/openvla-spatial-4bit/native-pairs-v1-20261010/`；日志：`logs/openvla-native-pairs-v1-20261010.log`；运行器：[N/A脚本](../scripts/check_openvla_native_pairs.py)。
