# 事实先行：三初始化N/A结果

2026-10-10完成，退出码0；新增四条A，来源与逐条结果独立复核通过。按用户最新指示，本轮结束后暂停，不启动下一轮。

| 原生任务 | 条件 | init0 | init1 | init2 | 正确独占成功 |
| --- | --- | --- | --- | --- | --- |
| ramekin | N | 成功114步 | 成功99步 | 成功116步 | 3/3 |
| ramekin | A | 成功113步 | neither 300步 | neither 300步 | 1/3 |
| plate | N | 成功107步 | 成功105步 | neither 300步 | 2/3 |
| plate | A | 成功108步 | neither 300步 | neither 300步 | 1/3 |

**本候选正常门槛未通过。** 原问题和ramekin指代、事实句文字、FP4／SDPA模型、图像／动作及原生3厘米判据均保留；事实先行在init0有改善，三初始化没有稳定复现。正式冲突、扩样、CoVLA及攻击搜索均未启动，旧资格结果不改写。

ramekin init1 A：首次双侧接触正确碗无，最大抬升0.00厘米；终点盘子接触未成立、高度未成立、中心距25.02厘米。

ramekin init2 A：首次双侧接触正确碗无，最大抬升0.00厘米；终点盘子接触未成立、高度未成立、中心距23.98厘米。

plate init1 A：首次双侧接触正确碗第129步，最大抬升8.83厘米；终点盘子接触成立、高度成立、中心距8.60厘米。

plate init2 A：首次双侧接触正确碗无，最大抬升0.82厘米；终点盘子接触未成立、高度未成立、中心距13.29厘米。

新增1200次查询，零额外策略诊断；六条N的841次、两条init0 A的221次，共1062次来源成本仅复用、不重计。四条新A均预先固定，未按中途结果删掉失败。plate init1目标在实际图左缘部分裁剪但仍可辨认，该限制保留。

本次连续接续新增3462次：中性追加411、包装重跑1074、I/O中止112、事实先行665及本轮1200；共18条新完整rollout，另1条112步中止。OpenVLA累计至少8287次，近期口径至少9517次，旧断电／Goal未知中止成本另列。

当前已暂停，后续试验需用户明确恢复；正常门槛未通过时不进入正式X/U。保留当前事实前置载体作为探索记录，后续模型／精度／载体改动须另冻结N/A核查，不能把单初始化成功当作已通过能力。

依据：[冻结规则](PHASE1_OPENVLA_FACT_FIRST_NA_V1_20261010.md)、[结果](assets/phase1/openvla-fact-first-na-v1-summary-20261010.json)、[配置](assets/phase1/openvla-fact-first-na-v1-manifest-20261010.json)、[预检](assets/phase1/openvla-fact-first-na-v1-preflight-20261010.json)、[来源复用核验](assets/phase1/openvla-fact-first-na-v1-control-reuse-audit-20261010.json)、[六图审阅](assets/phase1/openvla-fact-first-na-v1-visual-review-20261010.json)、[逐条结果复核](assets/phase1/openvla-fact-first-na-v1-result-audit-20261010.json)。完整输出：`outputs/openvla-spatial-4bit/fact-first-na-v1-20261010/`；日志：`logs/openvla-fact-first-na-v1-20261010.log`。
