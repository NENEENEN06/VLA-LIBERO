# OpenVLA诊断：事实先行、原问题收尾v1

2026-10-10，新增查询前冻结。本轮是独立文字顺序诊断，不改变模型、原版ramekin指代、原任务或成功判据。

N逐字保留原生格式。A/U从`In: What action should the robot take to Q?\n事实\nOut:`改为`In:\n事实 What action should the robot take to Q?\nOut:`；原版Q和事实句文字、大小写转换、字符及token多重集和长度不变。把事实放在动作问题前面，并让原问题紧邻Out；换行与空格位置属于声明的包装变化，不将结果单独归因于关系理解或纯顺序机制。

先核查同一原生task1／task8 init0、原N输入、起始状态、像素和事实真值；实际224图像审阅后重新跑两条N，均成功再固定执行两个A、两个U，不因A结果挑选U。最多6条／1800次新查询，额外策略诊断0。权重／FP4／SDPA、图像与动作接口、环境及策略seed=1、10步静置、300步上限、原生On终止及正确碗独占判据保持一致，3厘米阈值不改。

task1 A/X/U为52有效token，task8为50，N为32／30。旧原生N/A与两轮U／包装数据都是已见参考，不重计来源成本。本轮每块仅一个初始化，不替代三初始化正常门槛；正式X/U矩阵新增0，主模型不自动升级。按用户额度规则，剩余额度小于10%时结束已开始整轮，再暂停总结提交推送。运行中用WSL内部读取状态，避免Windows占用原子替换文件。

配置：[事实先行v1](../configs/openvla-fact-first-v1.json)；处理器：[包装变化](../scripts/openvla_fact_first.py)；运行器：[诊断](../scripts/check_openvla_fact_first.py)。
