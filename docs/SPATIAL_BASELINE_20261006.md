# Spatial 基线检查

日期：2026-10-06（Asia/Shanghai）。三个模型均完成评测，退出码均为 0。

参数：libero_spatial，10 个任务，每任务 1 个 episode，seed=1，CUDA，逐模型运行。

| 模型 | 成功 / episode | 成功率 | 运行状态 |
|---|---|---|---|
| SmolVLA | 8 / 10 | 80% | 完成 |
| VLA-Adapter | 10 / 10 | 100% | 完成 |
| PulseVLA | 9 / 10 | 90% | 完成 |

本轮证明三个模型均能完成完整任务评测。每任务只有一次采样，结果不代表稳定成功率；各模型保留各自上游评测器、仿真版本、随机种子和初始状态处理方式，不能据此确定统一条件下的模型排名。

## 逐任务结果

| task_id | 任务 | SmolVLA | VLA-Adapter | PulseVLA |
|---|---|---|---|---|
| 0 | pick up the black bowl between the plate and the ramekin and place it on the plate | 成功 | 成功 | 成功 |
| 1 | pick up the black bowl next to the ramekin and place it on the plate | 成功 | 成功 | 成功 |
| 2 | pick up the black bowl from table center and place it on the plate | 成功 | 成功 | 成功 |
| 3 | pick up the black bowl on the cookie box and place it on the plate | 失败 | 成功 | 成功 |
| 4 | pick up the black bowl in the top drawer of the wooden cabinet and place it on the plate | 成功 | 成功 | 成功 |
| 5 | pick up the black bowl on the ramekin and place it on the plate | 成功 | 成功 | 成功 |
| 6 | pick up the black bowl next to the cookie box and place it on the plate | 成功 | 成功 | 失败 |
| 7 | pick up the black bowl on the stove and place it on the plate | 成功 | 成功 | 成功 |
| 8 | pick up the black bowl next to the plate and place it on the plate | 成功 | 成功 | 成功 |
| 9 | pick up the black bowl on the wooden cabinet and place it on the plate | 失败 | 成功 | 成功 |

SmolVLA 的 task 3、9 达到 280 步上限仍未成功；PulseVLA 的 task 6 未成功。三个模型的评测进程均正常完成，VLA-Adapter 日志未发现 Episode error。

## 结果文件

- SmolVLA：[eval_info.json](assets/readiness/spatial-smolvla-eval-info.json)
- VLA-Adapter：[评测记录](assets/readiness/spatial-vla-adapter-eval.txt)
- PulseVLA：[results.json](assets/readiness/spatial-pulsevla-results.json)
- 机器可读汇总：[spatial-baseline-20261006.json](assets/readiness/spatial-baseline-summary.json)
- 每组参数、权重提交和依赖记录保存在各输出目录的 run-manifest.json。

## 日志和回放

- 日志：logs/smolvla-spatial-baseline-20261006.log、logs/adapter-spatial-baseline-20261006.log、logs/pulsevla-spatial-baseline-20261006.log。
- SmolVLA：十段视频，位于输出目录的 videos/libero_spatial_<task_id>/eval_episode_0.mp4。
- VLA-Adapter：十段视频，位于 third_party/vla-adapter/rollouts/vla-adapter/2026_10_06/，文件前缀为 2026_10_06-21_01_30。
- PulseVLA：当前上游评测入口输出 JSON 和日志，不保存回放。

下一步：增加每任务 episode 数，验证稳定基线；正式横向比较前明确统一评测协议。
