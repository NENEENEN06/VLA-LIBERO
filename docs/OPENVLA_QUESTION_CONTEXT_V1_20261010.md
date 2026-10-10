# OpenVLA诊断：原问题先结束、事实置后v1

2026-10-10完成；独立结果复核通过。原版Q和事实句保留，只将问号移回原问题末尾，再给出事实行；模型／FP4／SDPA、图像／动作、起始状态和原生3厘米判据不变。字符及token多重集和长度核对相同，N实际输入完全不变，A/U分别52／50有效token，无截断。

| 原生任务init0 | 本轮新N | 本轮新A | 本轮新U |
| --- | --- | --- | --- |
| ramekin task1 | 第114步正确独占成功 | 300步neither | 第120步正确独占成功 |
| plate task8 | 第107步正确独占成功 | 第133步正确独占成功 | 300步neither |

plate A由旧包装下300步未完成变为本轮第133步成功，是这一个初始化的改善；ramekin A仍未完成，且没有双侧指垫接触任一黑碗。ramekin U第120步成功，A/U内容差别依然存在。**本轮没有让两任务A同时通过，正式Phase 1仍停在正常条件门槛。** 单初始化不能替代三初始化资格，不将结果推广为普遍语义能力或纯顺序机制。

ramekin A：无正确碗双侧接触，最大抬升3.06厘米；终点无盘子接触、高度未成立、中心距31.81厘米。

ramekin U：第71步首次正确碗双侧接触，最大抬升16.67厘米；终点盘子接触和高度成立，中心距1.38厘米。

plate A：第95步首次正确碗双侧接触，最大抬升10.60厘米；终点盘子接触和高度成立，中心距2.62厘米。

plate U：第101步首次正确碗双侧接触，最大抬升7.14厘米；终点盘子接触和高度成立，中心距4.72厘米，超出原生3厘米阈值。

首轮因状态文件原子替换错误在112次查询后中止，未完成样本；按同科学条件重跑。头112步动作、状态及实际输入与中止轮完全相同，见[重跑说明](OPENVLA_QUESTION_CONTEXT_V1_RETRY_20261010.md)。运行中改用WSL读取状态，错误没有再发生。

重跑新增1074次查询，零额外策略诊断；加首轮中止112次，本轮两次启动合计1186次。旧N/A/U只作已见参考，不重计。OpenVLA累计至少6422次，近期口径至少7652次，旧断电／Goal未知中止另列。正式矩阵新增0，冲突行为0，正常N/A门槛与主模型角色不改。

下一步候选是将同一句事实放在动作问题之前，使原问题紧邻Out；保留原Q和事实句，另立配置／规则和N/A/U诊断，仍核对字符／token及状态控制，不按单例选择混合载体。不放宽放置判据。

依据：[冻结条件](OPENVLA_QUESTION_CONTEXT_V1_ENTRY_20261010.md)、[结果](assets/phase1/openvla-question-context-v1-summary-20261010.json)、[运行配置](assets/phase1/openvla-question-context-v1-manifest-20261010.json)、[预检](assets/phase1/openvla-question-context-v1-preflight-20261010.json)、[输入／来源核验](assets/phase1/openvla-question-context-v1-reference-audit-20261010.json)、[实际图审阅](assets/phase1/openvla-question-context-v1-visual-review-20261010.json)、[逐条结果复核](assets/phase1/openvla-question-context-v1-result-audit-20261010.json)。完整输出在`outputs/openvla-spatial-4bit/question-context-v1-retry1-20261010/`，日志在`logs/openvla-question-context-v1-retry1-20261010.log`。
