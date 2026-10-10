# OpenVLA Spatial 4-bit候选核查

2026-10-09（Asia/Shanghai）。用户选择测试OpenVLA原版Spatial 4-bit，先核查运行条件和正常能力，通过后再确定主模型角色。现有SmolVLA结果及冻结配置保留。

2026-10-10更新：[新N核查已完成](OPENVLA_SPATIAL_4BIT_SCREEN_20261010.md)，盘子方向2/3、ramekin方向0/3，N门槛未通过，A与冲突条件未运行。下面保留本轮冻结规则。

后续原生ramekin任务对照另按[task1诊断规则](OPENVLA_NATIVE_RAMEKIN_ENTRY_20261010.md)冻结，使用task1自己的物理场景，不能充作下面task8资格样本。

使用官方 `openvla/openvla-7b-finetuned-libero-spatial`，revision `962318cec55ac10993ff0f5f43eda9a270b4c873`；官方源码固定为 `c8f03f48af692657d3060c19588038c7220e9af9`。配套HF自定义代码单独固定版本，四个权重分片已核对官方SHA-256。具体配置见[候选配置](../configs/openvla-spatial-4bit.json)。

| 项目 | 本轮配置 |
| --- | --- |
| 环境 | 独立Python 3.10.16、PyTorch 2.2.0/cu121、Transformers 4.40.1、bitsandbytes 0.43.1 |
| 量化 | GPU上加载4-bit FP4，沿用官方`load_in_4bit=True`的默认计算设置；其余模块BF16，无CPU卸载 |
| 注意力 | PyTorch SDPA；与官方Flash Attention 2默认入口不同，独立验证 |
| 仿真 | 原版LIBERO、robosuite 1.4.1、MuJoCo 2.3.7，20 Hz、硬重置 |
| 输入 | 仅agentview单相机，无本体输入；256画面、原生JPEG/Lanczos缩放、90%面积中心裁剪、224模型输入 |
| 文本 | 官方`In: What action should the robot take to {task_label.lower()}?\nOut:`格式，原版指代保留 |
| 动作 | 每次预测一个7维动作；官方Spatial反归一化、夹爪二值化与反号 |

单相机经过两个视觉编码器，输入的6个通道不能解释为两台相机。脚本从固定官方源码加载未修改的图像／动作函数定义，使用固定HF模型类；无需安装训练数据管线。官方权重论文结果来自未量化推理，不直接当作本轮4-bit结果。

核查顺序与上限：

1. 零查询预检三个初始化的原双碗、正确事实真值、完整token和起始状态；两次真实观察的一步预测核查重置一致性，单列2次诊断。
2. 官方task 8原指令／原目标基线，环境seed=0、策略seed=1、10步静置，最多220步／220次查询，成功则提前结束。这是单条接口及原任务检查，不估计总体成功率。
3. 查看原生及实际裁剪画面后，原双碗init0..2、环境／策略seed=1、300步上限，先运行两个方向的6条N。两个N块各至少正确独占完成2/3，才运行6条A。四个Q×N/A块各至少2/3才判资格通过。

配对核查继续使用task 8物理场景，task 1只提供ramekin侧原句。评价器将两碗上盘子的AND作为共享终止条件，并独立记录两碗的ever事件，区分`bowl1_only`、`bowl2_only`、`both`、`neither`。模拟器对象ID、目标事件和事实标签不输入策略。不同模型的原生输入及仿真栈不同，不要求与SmolVLA像素／状态哈希相同；本轮内部须严格配对。

原版指令：

- plate侧：`pick up the black bowl next to the plate and place it on the plate`
- ramekin侧：`pick up the black bowl next to the ramekin and place it on the plate`

A继续使用已冻结的正确事实，Q与A之间一个换行；官方入口将整个task文本转为小写，实际输入单独记录：

- plate侧：`Initially, the black bowl farther from the ramekin is next to the plate.`
- ramekin侧：`Initially, the black bowl farther from the plate is next to the ramekin.`

OpenVLA原版逐步调用策略，因此6条N最多1800次查询，完整12条N/A最多3600次。加上220步原任务基线和2次重置诊断，本轮上限3822次；实际停止数另记。N未达标则不运行A，不启动X/U、扩样或攻击搜索，也不自动更换主模型。

2026-10-10断电接续：10月9日的能力核查首条N未完成，用户要求删除该轮输出和日志、从头重跑。保存记录确认至少281次完成查询，末次记录有1条查询在执行中；断电尾部成本未知，见[中止账目](assets/phase1/openvla-spatial-4bit-power-loss-ledger-20261010.json)。旧轮不计资格样本，不复用动作或结果。已成功的运行核查不删除；10月10日新核查仍以最多12条／3600次新增查询为界，旧中止成本另计。

Windows项目根目录运行（已有系统渲染库及项目uv）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 setup
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 download
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 readiness --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/readiness-new
```

预检错误与重试保留不同目录。通过原任务基线和人工画面核查后，使用已写有`preflight-image-review.json`的readiness目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 screen --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/screen-new --readiness /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/readiness-new
```

依赖锁：[requirements](../requirements/openvla-spatial-4bit.lock)。运行器：[能力核查](../scripts/check_openvla_spatial_4bit.py)、[模型与官方处理](../scripts/openvla_spatial_4bit.py)。官方依据：[模型卡](https://huggingface.co/openvla/openvla-7b-finetuned-libero-spatial)、[评测说明](https://github.com/openvla/openvla#libero-simulation-benchmark-evaluations)。
