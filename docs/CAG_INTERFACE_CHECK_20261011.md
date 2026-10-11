# CAG官方代码与当前接口核对

2026-10-11，只读检查，新增策略查询0；未修改当前受害策略。本核对落实[文献审查](LANGUAGE_DISTRACTION_LITERATURE_REVIEW_20261011.md)中的方法可行性检查。

[官方项目](https://vla-cf.github.io/)链接至[yuffish/LIBERO-CF](https://github.com/yuffish/LIBERO-CF)。核对其免训练OpenVLA-OFT服务端[serve_openvla_oft_TF.py](https://github.com/yuffish/LIBERO-CF/blob/main/openvla-oft-cf/serving/serve_openvla_oft_TF.py)与[openvla_oft_policy.py](https://github.com/yuffish/LIBERO-CF/blob/main/openvla-oft-cf/serving/openvla_oft_policy.py)。本次读取main，后续复现仍须固定具体提交和代码校验值。

官方实现区分两种输出：L1回归分支混合动作；离散token分支混合条件／空文本的logits，再解码和反归一化。两次前向共用观察。服务入口的guidance_scale默认1，此时公式退化为条件分支，不能仅启用包装就宣称产生引导收益。

当前[OpenVLA原版接口](../scripts/openvla_spatial_4bit.py)生成离散动作token，仅返回反归一化动作及输入审计，不提供logits。按官方离散分支复现需要新增分数接口，超出当前严格黑盒访问。直接混合两个已解码动作仅能定义为另一种动作后处理方法，不能视为官方离散CAG复现；夹爪离散处理、动作范围及闭环性能都需独立验证。

如果后续允许更换为可用的连续回归策略，动作空间版本可能与可见动作接口兼容，但模型、相机、本体输入、动作块及基础能力须重新冻结。每控制决策至少两个策略调用，预算按分支调用计；基线策略和缓解系统分别报告。当前18条P/U0/A0诊断保持原策略。

另外，官方LIBERO-CF的选物指标采用夹爪接触对象检测；本项目现有轨迹记录的是双侧指垫接触代理。因此本轮借鉴“选物／执行分离”的设计，不把代理比例当作其touch rate的数值复现。
