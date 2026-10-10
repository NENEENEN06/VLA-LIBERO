# OpenVLA原生任务：同长度中性追加v1

2026-10-10，16:03（Asia/Shanghai）完成，退出码0；两条新U共411次查询，零额外策略诊断，来源和逐条结果复核通过。

| 原生任务init0 | N已见参考 | A已见参考 | 本轮U |
| --- | --- | --- | --- |
| task1 ramekin | 第114步成功 | 300步未完成 | 第111步正确碗独占成功 |
| task8 plate | 第107步成功 | 300步未完成 | 300步neither |

U为原指令后换行追加`Initially, the plate and the ramekin are both resting on the table surface.`，task1有效52 token、task8为50，与各自A/X等长、无截断。模型、原生场景／init0、seed、输入图像、动作、300步上限及原生On评价与N/A参考一致；原N/A只作已见参考，查询成本不重计。两碗及参照物在实际224图中可辨认，U桌面支撑真值通过。

ramekin U第65步首次双侧接触正确碗，抬升17.9厘米，终点与盘子接触、高度成立、中心距2.07厘米，原生成功。plate U第106步接触正确碗，89个状态满足双侧接触，最大抬升3.2厘米；终点与盘子接触，但高度条件不成立、中心距5.89厘米，未满足原生判据。两条均无错误碗接触或上盘子事件。接触记录不单独证明稳定抓握。

**ramekin在相同长度、同换行的U下成功而A失败，纯长度或换行不能解释这一个初始化的差别。** plate的U也失败，包含抓取／放置困难。单条U不能区分全部词汇、事实内容和表达结构因素，也不证明普遍关系词理解或图文主导；结果不能跨模型合并。

下一轮建议只改追加事实与主问题的包装位置：保留基础指令、辅助句和模型，将问题的问号放回原指令末尾，再在问题外加入事实行；单独核查新格式的N/A/U。假设是当前事实被包进“应做何动作”的问题可能影响行为，不预设一定改善。

本轮只有两条独立诊断，正式X/U矩阵新增0，A门槛仍未通过，放置阈值保留3厘米。新增411次（111＋300），OpenVLA累计已登记至少5236次，近期研究口径至少6466次，旧断电／Goal中止未知成本仍单列，更早环境基线不在此口径内。

依据：[冻结规则](OPENVLA_NATIVE_NEUTRAL_V1_ENTRY_20261010.md)、[结果](assets/phase1/openvla-native-neutral-v1-summary-20261010.json)、[运行配置](assets/phase1/openvla-native-neutral-v1-manifest-20261010.json)、[来源核验](assets/phase1/openvla-native-neutral-v1-reference-audit-20261010.json)、[预检](assets/phase1/openvla-native-neutral-v1-preflight-20261010.json)、[画面审阅](assets/phase1/openvla-native-neutral-v1-visual-review-20261010.json)、[独立结果复核](assets/phase1/openvla-native-neutral-v1-result-audit-20261010.json)。完整轨迹和视频在`outputs/openvla-spatial-4bit/native-neutral-v1-20261010/`，日志为`logs/openvla-native-neutral-v1-20261010.log`。
