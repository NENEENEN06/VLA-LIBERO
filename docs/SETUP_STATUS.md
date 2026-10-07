# 配置状态

记录日期：2026-10-01（Asia/Shanghai）。本机配置和运行检查已完成。

项目目录：`C:\VLA-LIBERO`；WSL 路径：`/mnt/c/VLA-LIBERO`。

WSL 3.0.1、Ubuntu 22.04.5、WSLg 1.0.79；RTX 3070 Laptop 8GB，Windows NVIDIA 驱动 616.64。

## 实际验证

三个独立环境均已安装，依赖一致性检查通过。每个模型都验证了 CUDA 张量运算、LIBERO 初始状态、两个相机的有效画面、仿真动作执行、发布权重加载和有限的 7 维动作预测；随后通过原有处理流程执行真实观测闭环。

| 模型 | CUDA / 双相机 | 权重和动作预测 | 短程闭环 | PyTorch 峰值显存 |
|---|---|---|---|---|
| smolvla | 通过 | 通过 | 通过（30 步） | 1.19 GiB |
| vla-adapter | 通过 | 通过 | 通过（30 步） | 3.33 GiB |
| pulsevla | 通过 | 通过 | 通过（30 步） | 2.22 GiB |

检查使用 Spatial 套件的第 0 个任务，固定初始状态，执行 30 个策略动作。这个短程检查验证接口衔接，不是完整 episode 或论文成功率评测。PyTorch 的显存统计不包含 Windows 图形服务及 TensorFlow 等其他组件。

报告和相机图片：`outputs/diagnostics/<model>/simulation.json`、`policy.json`、`rollout.json`、`libero-camera.png`。汇总记录：`.runtime/validation-status.json`。安装日志和检查日志保存在 `logs/`。

## 已安装内容

- `.venvs/smolvla`、`.venvs/vla-adapter`、`.venvs/pulsevla`，各自保留 Python、PyTorch、CUDA wheel 和仿真依赖版本。
- `models/smolvla`、`models/pulsevla`、`models/vla-adapter/libero_spatial`。
- 原版 LIBERO 和 VLA-Adapter 的固定代码提交位于 `third_party/`。
- HF LIBERO 场景资源位于 `data/libero-assets`，SmolVLM2 基础文件位于项目 HF 缓存。
- 实际安装依赖记录：`.runtime/<model>-installed.txt`。

## 安装过程中处理的兼容性

- 在 EGL 探测组件构建前安装 CMake 和图形开发库。
- 为 Windows 目录映射中的项目 Git 仓库配置精确的 safe.directory，配置保存在项目 `.runtime/gitconfig` 中。
- 下载独立发布的 HF LIBERO 场景资源，并将两个新版环境的资源路径指向项目中的共享目录。
- 为原版 LIBERO 的 namespace 添加源代码路径，兼容现代 editable 安装器。
- 显式固定上游漏声明的 `future`、`msgpack` 和 `msgpack-numpy` 运行依赖。
- 降低下载并发，并为 VLA-Adapter 使用清华 PyPI 镜像。包版本仍由锁文件固定。
- VLA-Adapter 的官方入口已备份并同步 checkpoint 的配置和模型代码到固定源码版本；原文件备份位于其权重目录中的 `*.back.<timestamp>`，发布权重保持不变。

本机三个仿真环境均实际使用 EGL 完成渲染。安装使用 Ubuntu root 用户；Windows 启动脚本无需个人 Linux 用户初始化。

## 使用

在项目 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\vla.ps1 doctor all --policy
powershell -ExecutionPolicy Bypass -File .\scripts\vla.ps1 rollout all --steps 30
powershell -ExecutionPolicy Bypass -File .\scripts\vla.ps1 eval smolvla --suite libero_spatial --episodes 1
```

详细评测命令见 README。VLA-Adapter 目前仅下载 Spatial 权重，其余三个套件可用 `download vla-adapter --suite all` 按需下载。2026-10-06 已完成 Spatial 全部十个任务的基线检查，每任务 1 个 episode：SmolVLA 8/10、VLA-Adapter 10/10、PulseVLA 9/10，详见 [Spatial 基线检查](SPATIAL_BASELINE_20261006.md)。尚未运行每任务多 episode 的正式成功率评测，也未配置训练所需的 Flash Attention 编译环境。


## 2026-10-07 研究前置核查

SmolVLA 的 49 次核查已完成，固定种子重放一致；两个任务通过干净筛选，但合法目标切换 0/3，正式跨模态先导需补语言目标绑定验证。见 [核查报告](SMOLVLA_READINESS_20261006.md)。环境可运行与研究前置条件通过分别记录。


## Goal 追加核查

2026-10-07 共享 Goal 场景中盘子、炉子合法目标各 10/10 成功，十组配对状态一致，输入和判据核验通过。支持该场景的 Phase 1 小规模行为刻画；Object 身份切换边界保留。见 [Goal 报告](SMOLVLA_GOAL_CHECK_20261007.md)和 [Phase 1 入口](PHASE1_ENTRY.md)。
