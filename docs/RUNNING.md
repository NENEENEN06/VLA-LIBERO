# 环境配置与运行说明

本文件保留项目原有安装、模型配置和评测命令。命令均从项目根目录 C:\VLA-LIBERO（WSL 中为 /mnt/c/VLA-LIBERO）执行。

[返回项目主页](../README.md) · [配置状态](SETUP_STATUS.md) · [研究方案](../plans/VLA黑盒跨模态攻击研究计划_细化版.md)

## 固定版本

| 模型 | Python | PyTorch / CUDA wheel | 仿真 | 权重 |
|---|---|---|---|---|
| SmolVLA | 3.12.14 | 2.11.0 / cu128 | LeRobot 0.6.1、hf-libero 0.1.4、MuJoCo 3.3.2 | `HuggingFaceVLA/smolvla_libero` |
| VLA-Adapter 原版 | 3.10.16 | 2.2.0 / cu121 | 原版 LIBERO、robosuite 1.4.1、MuJoCo 2.3.7 | Spatial、Goal 已下载；其他套件按需下载 |
| PulseVLA-LIBERO 0.5B | 3.12.14 | 2.11.0 / cu128 | 发布者指定的 LeRobot 提交、hf-libero 0.1.3、MuJoCo 3.3.2 | `verapulse/pulsevla-libero-0.5b` |
| OpenVLA Spatial 4-bit候选 | 3.10.16 | 2.2.0 / cu121 | 原版 LIBERO、robosuite 1.4.1、MuJoCo 2.3.7 | `openvla/openvla-7b-finetuned-libero-spatial`，bitsandbytes 0.43.1／FP4 |

完整依赖版本在 `requirements/*.lock`，源代码和权重提交在 [sources.json](../configs/sources.json)。VLA-Adapter 使用原版权重配合 `use_pro_version=False`，保持版本一致。Flash Attention 不是当前上游评测入口的必需依赖；训练所需的 Flash Attention 和 CUDA 编译工具链另行安装。

OpenVLA使用[独立固定配置](../configs/openvla-spatial-4bit.json)、[依赖锁](../requirements/openvla-spatial-4bit.lock)和`openvla.ps1`入口。原版单相机、JPEG/Lanczos缩放与90%面积裁剪、Spatial动作反归一化及夹爪转换保留，注意力使用PyTorch SDPA。4-bit加载与一条真实任务已在本机8GB GPU通过，见[运行核查](OPENVLA_SPATIAL_4BIT_READINESS_20261009.md)；双向指代与A资格按[候选核查入口](OPENVLA_SPATIAL_4BIT_ENTRY.md)另测。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 setup
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 download
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 readiness --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/readiness-new
```

2026-10-10新增[原生ramekin任务对照](OPENVLA_NATIVE_RAMEKIN_ENTRY_20261010.md)：task1使用自己的场景、初始化和目标，三条最多900次查询，独立于task8双向资格。命令中的readiness须指向已通过运行核查的目录；运行器在开始rollout前等待三个实际模型输入图的审阅记录。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-ramekin --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-ramekin-new --readiness /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/readiness-retry2-20261009
```

后续[原生任务内配对v1](PHASE1_OPENVLA_NATIVE_PAIRS_V1_20261010.md)在task1／task8各自场景核查N/A，完整核对后复用三条task1原生N、重跑task8 N，最多2700次新增查询；实际图像审阅后继续，X/U仅预检。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-pairs --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-new --native-N /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-ramekin-20261010
```

正常A未通过后，可按各自冻结规则运行[同长度中性追加诊断](OPENVLA_NATIVE_NEUTRAL_V1_ENTRY_20261010.md)或[问题／事实包装诊断](OPENVLA_QUESTION_CONTEXT_V1_ENTRY_20261010.md)。它们引用已完成原生N/A作为来源核验，不增加正式冲突矩阵；实际224图像审阅通过后才开始查询。输出目录必须是新目录，避免覆盖历史记录。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 native-neutral --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-neutral-new --reference /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 question-context --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/question-context-new --reference /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 fact-first --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/fact-first-new --reference /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010
```

事实先行pilot完成后，按[三初始化N/A规则](PHASE1_OPENVLA_FACT_FIRST_NA_V1_20261010.md)核验复用六N／两A，再新增四条A。运行器等待六幅实际224图像的审阅记录，不放宽原生成功判据。

```powershell
powershell -ExecutionPolicy Bypass -File scripts/openvla.ps1 fact-first-na --output /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/fact-first-na-new --normal-N /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/native-pairs-v1-20261010 --pilot /mnt/c/VLA-LIBERO/outputs/openvla-spatial-4bit/fact-first-v1-20261010
```

下面的`vla.ps1`／`vla.py all`命令管理SmolVLA、VLA-Adapter、PulseVLA三个既有环境；OpenVLA候选按独立入口运行。

## 在 Windows 项目目录中运行

本机安装使用 Ubuntu 的 root 用户，无需等待 Linux 用户初始化。在 `C:\VLA-LIBERO` 的 PowerShell 中可以直接调用项目启动脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\vla.ps1 doctor all --policy
powershell -ExecutionPolicy Bypass -File .\scripts\vla.ps1 eval vla-adapter --suite libero_spatial --episodes 1
```

启动脚本将参数传给 WSL 中的 `scripts/vla.py`。下面的步骤保留了从头安装和 Ubuntu 终端使用方式。

## 1. 重启后完成 WSL / Ubuntu 安装

在仓库目录的 PowerShell 中运行；脚本会请求 Windows UAC 管理员权限，且不会自动重启：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap_wsl.ps1
```

如果提示需要重启，请保存工作并重启，再运行同一条命令。如需个人 Linux 用户，可打开 Ubuntu 22.04 完成用户名和密码初始化；本机已经使用 root 完成安装，项目启动脚本无需这一步。确认是 WSL2：

```powershell
wsl --list --verbose
wsl -d Ubuntu-22.04 -- nvidia-smi
```

WSL 使用 Windows NVIDIA 驱动，不要在 Ubuntu 中安装 Linux NVIDIA 显卡驱动。`nvidia-smi` 显示的 CUDA 版本是驱动支持上限；脚本安装各模型需要的 CUDA wheel，无需安装完整 CUDA Toolkit。

## 2. 在 Ubuntu 中安装三个环境

以下命令在 Ubuntu 终端中运行。当前仓库的 WSL 路径是：

```bash
cd /mnt/c/VLA-LIBERO
bash scripts/setup_linux.sh all
```

脚本安装系统渲染库、FFmpeg、uv 和托管 Python，随后依次创建 `.venvs/smolvla`、`.venvs/vla-adapter`、`.venvs/pulsevla`，按锁文件安装依赖，并检查依赖一致性。首次执行 `sudo` 需要你输入刚创建的 Linux 密码。单独安装某个环境可将 `all` 替换为模型名称。

安装默认使用当前 checkout，也可以把整个仓库复制到 WSL 的 Linux 文件系统后执行，以改善小文件读写性能。移动已安装环境后需要重新创建 `.venvs`，不要直接移动虚拟环境。模型和 Python 下载需要访问 GitHub、PyPI、PyTorch wheel 源及 Hugging Face。缓存和环境可能占用几十 GB，请预留空间。

## 3. 下载权重和检查

先下载三个模型；VLA-Adapter 默认仅下载 Spatial 权重：

```bash
python3 scripts/vla.py download all
python3 scripts/vla.py doctor all --policy
```

如果要评测四个套件，再下载 VLA-Adapter 的其余权重：

```bash
python3 scripts/vla.py download vla-adapter --suite all
```

`doctor` 逐个检查 CUDA、任务初始状态、两个相机画面和仿真动作执行；`--policy` 额外加载权重并做一次 7 维动作预测。诊断图像和 JSON 写入 `outputs/diagnostics/<model>/`。预测检查使用合成观测。短程闭环检查读取真实仿真观测，使用各模型原有处理和动作执行流程：

```bash
python3 scripts/vla.py rollout all --steps 30
```

该命令只运行 Spatial 的第 0 个任务，用于检查接口衔接；完整行为与成功率通过下面的评测验证。

启动脚本在 WSL 初始设置 `MUJOCO_GL=glfw`；robosuite 可能在导入时切换渲染后端。本机三个环境实测均使用 EGL 渲染成功。如果相机初始化失败，可用 CPU 软件渲染检查，模型仍使用 CUDA：

```bash
MUJOCO_GL=osmesa python3 scripts/vla.py doctor all --policy
```

原生 Linux NVIDIA 环境默认使用 `egl`；也可显式设置 `MUJOCO_GL=egl`。不要在 WSL 中假定 CUDA 可用就表示 NVIDIA EGL 可用。

## 4. 运行评测

先用每任务 1 个 episode 验证三个模型能完整闭环运行（每个套件 10 个任务）：

```bash
python3 scripts/vla.py eval all --suite libero_spatial --episodes 1
```

正式评测四个套件，每任务 10 个 episode：

```bash
python3 scripts/vla.py eval smolvla --suite all --episodes 10 --seed 1
python3 scripts/vla.py eval vla-adapter --suite all --episodes 10 --seed 1
python3 scripts/vla.py eval pulsevla --suite all --episodes 10 --seed 1
```

输出位于 `outputs/<model>/<suite>-<timestamp>/`，包含运行参数、权重版本和实际安装依赖。SmolVLA 使用官方 LeRobot CLI，PulseVLA 使用随权重发布的 `eval_libero.py`，VLA-Adapter 使用官方 `run_libero_eval.py`。VLA-Adapter 上游视频输出在 `third_party/vla-adapter/rollouts/`。

RTX 3070 8GB 默认逐模型运行、单个仿真环境，并配置 TensorFlow 按需分配显存。本机三个模型已通过实际加载和短程闭环检查；运行时仍需为模型预留显存。`--device cpu` 仅供 SmolVLA / PulseVLA 排查，速度会明显降低。

不同模型保留各自的图像处理、归一化和动作转换；默认 SmolVLA / PulseVLA 每次执行 10 个动作，VLA-Adapter 执行上游默认的 8 个动作。它们使用不同评测器及仿真版本，结果不可视作完全统一条件下的排名。当前公共配置不承诺复现论文成功率。

## 来源

- [HF LIBERO 场景资源](https://huggingface.co/datasets/lerobot/libero-assets)
- [LIBERO 官方代码](https://github.com/Lifelong-Robot-Learning/LIBERO)
- [LeRobot LIBERO 文档](https://huggingface.co/docs/lerobot/en/libero)
- [SmolVLA LIBERO 权重](https://huggingface.co/HuggingFaceVLA/smolvla_libero)
- [VLA-Adapter 官方代码和安装说明](https://github.com/OpenHelix-Team/VLA-Adapter)
- [PulseVLA-LIBERO 权重和复现说明](https://huggingface.co/verapulse/pulsevla-libero-0.5b)
