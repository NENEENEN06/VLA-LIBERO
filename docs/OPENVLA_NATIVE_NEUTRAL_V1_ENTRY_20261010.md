# OpenVLA原生任务：同长度中性追加诊断v1

2026-10-10，新增策略查询前冻结。原生任务内N/A的A两块均0/3，正式冲突门槛保持未通过；本轮单独诊断普通文本追加是否也影响原任务执行。

使用[原生任务内配对v1](PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md)同一FP4／SDPA、单相机和动作设置，task1 ramekin及task8 plate各自原场景／原指令、init0、环境／策略seed=1、10步静置、300步上限、原生On及终止规则。正确碗独占完成才记探针成功，原生3厘米判据保留。

两条均追加原冻结U：`Initially, the plate and the ramekin are both resting on the table surface.`。按原指令＋一个换行＋中性句拼接，实际task1为52、task8为50有效token，与各任务A/X等长。U不提供黑碗选择线索，但提及原任务参照物；不能当作纯长度或纯换行测试。

先验证两个init0的图像、状态、输入、U桌面接触与[已完成N/A](PHASE1_OPENVLA_NATIVE_NA_20261010.md)一致，核对N/A原episode及模型／评价版本。旧N/A只作已见参考，不新增或重计它们的策略查询，也不把这两条U补入正式矩阵。

本轮固定2条新rollout，最多600次新增查询、零额外策略诊断。两条均完成，不按首条结果改初始化、文本或放置阈值。查看两个实际模型224图并记录审阅后开始。保存每步接触、抬升、放置分量、实际输入、完整／中止成本和视频；解释区分执行失败阶段，不能将单条失败归为普遍词义理解不足。

用户要求持续按证据试验；5小时额度剩余低于10%时，完成当时已开始的整轮后暂停新实验，再总结、提交并推送。每轮条件和查询上限预先冻结；额度快照只保存于本机运行目录，不发布账户标识。

配置：[neutral v1](../configs/openvla-native-neutral-v1.json)；运行器：[诊断入口](../scripts/check_openvla_native_neutral.py)。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-neutral --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-neutral-v1-20261010 --reference /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010
```
