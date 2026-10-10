# OpenVLA诊断：事实先行、原问题收尾v1

2026-10-10完成，退出码0；六条新rollout全部正确碗独占成功，新增665次查询，零额外策略诊断，来源／输入／逐步判据独立复核通过。

| 原生任务init0 | N | A | U |
| --- | --- | --- | --- |
| ramekin task1 | 第114步成功 | 第113步成功 | 第132步成功 |
| plate task8 | 第107步成功 | 第108步成功 | 第91步成功 |

原指令和事实句文字保持，只将事实放在动作问题之前，使原问题紧邻Out；字符和token多重集、长度与旧入口一致，N实际输入逐字不变。模型仍为OpenVLA Spatial FP4／SDPA，相机、起始状态、动作、种子、评价与300步窗口一致。A/U分别52／50有效token，未截断，原生3厘米判据不改。

| 同一init0的追加包装 | ramekin A | plate A | ramekin U | plate U |
| --- | --- | --- | --- | --- |
| 事实包在动作问题内 | 失败 | 失败 | 成功111步 | 失败 |
| 原问题先结束，事实置后 | 失败 | 成功133步 | 成功120步 | 失败 |
| 事实先行，原问题收尾 | 成功113步 | 成功108步 | 成功132步 | 成功91步 |

本轮两A首次双侧接触正确碗为第85／80步，最大抬升15.00／9.81厘米，终点中心距1.77／2.85厘米；两个U终点0.46／2.68厘米。六条都满足原生接触、高度和中心距判据，没有错误碗双侧接触或上盘事件。接触记录本身不单独当作稳定抓握证明。

**事实与问题的包装位置会影响这两个已见初始化的执行结果。** 这不是换模型后的改善，也不能直接推广为普遍关系词理解；换行和空格位置同属包装变化。每块只有一条初始化，三初始化正常门槛尚未据此放行，正式冲突仍为0。

本轮之后已按[三初始化N/A规则](PHASE1_OPENVLA_FACT_FIRST_NA_V1_20261010.md)补齐init1、2，新增四条A／1200次查询，两个A均仅1/3，门槛未通过，见[后续结果](PHASE1_OPENVLA_FACT_FIRST_NA_RESULTS_20261010.md)。本报告保留init0诊断的原统计范围；前置无关事实U的两条成功沿用，不重复或补测，现已暂停。

本轮成本665＝114＋107＋113＋108＋132＋91；旧参考不重计。OpenVLA累计至少7087次，近期口径至少8317次；旧断电／Goal未知中止成本另列。正式矩阵新增0，主模型角色不自动改变。

依据：[冻结入口](OPENVLA_FACT_FIRST_V1_ENTRY_20261010.md)、[结果](assets/phase1/openvla-fact-first-v1-summary-20261010.json)、[运行配置](assets/phase1/openvla-fact-first-v1-manifest-20261010.json)、[预检](assets/phase1/openvla-fact-first-v1-preflight-20261010.json)、[来源核验](assets/phase1/openvla-fact-first-v1-reference-audit-20261010.json)、[实际图审阅](assets/phase1/openvla-fact-first-v1-visual-review-20261010.json)、[逐条复核](assets/phase1/openvla-fact-first-v1-result-audit-20261010.json)、[零查询token核对](assets/phase1/openvla-fact-first-v1-format-control-20261010.json)。完整轨迹／视频在`outputs/openvla-spatial-4bit/fact-first-v1-20261010/`，日志为`logs/openvla-fact-first-v1-20261010.log`。
