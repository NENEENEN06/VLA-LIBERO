# SmolVLA Phase 1 前置核查

开始日期：2026-10-06（Asia/Shanghai）。完整核查输出：outputs/readiness/smolvla-20261006-identity/。首次重置报告保留于 outputs/readiness/smolvla-20261006/reset-audit.json。

## 当前进度

- 重置核查通过：相同 init_id=0、policy_seed=1，两次观察及首动作差异为 0。
- 已按用户要求暂停。Spatial task 0 的 init_id=0..9 全部完成：7/10 成功，失败初始化为 1、2、5。十份 JSON 与十段视频已保存。其余 30 个干净 episode 尚未运行。
- 待继续：Object task 0 的 init_id=0、1、2 同义改写与合法目标切换，共 6 次。
- 待继续：Object task 0 的相同 seed 完整重放一次及 policy_seed=7、11 各一次，共 3 次。
- 代表任务覆盖位置关系、物体支撑、抽屉与物体身份。任务在重复实验结果产生前固定。

## 协议

- 每个 episode 使用明确初始化编号；环境 seed=1，主策略 seed=1。
- 360×360 双相机，上游预处理、相对动作、20 Hz、每次执行 10 个动作、上限 280 步、硬重置。
- 本轮使用单进程 SyncVectorEnv，冻结本轮配置；旧的 Spatial 全任务结果仅作参考。
- 每次重置清空策略动作队列和处理器状态，保存有效 token 与原始文本。
- 合法目标切换保留 Object task 0 场景，从 alphabet_soup_1 改为 cream_cheese_1；同时把完成谓词改为 In cream_cheese_1 basket_1_contain_region。
- 模拟状态和对象谓词仅供评估、真值核查；策略输入沿用原生图像、机器人状态和文本。
- 每个完成的 episode 独立保存 JSON 和视频。只有协议及脚本摘要一致时允许复用；不能把中断片段计为完整 episode。

## 文件

- 脚本：scripts/check_smolvla_readiness.py
- 输出目录内：run-manifest.json、installed-dependencies.txt、reset-audit.json、episodes/*.json、videos/*.mp4。
- 完成时生成 summary.json。
- 日志：logs/smolvla-readiness-identity-20261006.log。

每任务至少 8/10 成功只作为先导筛选阈值；语言与重复性通过后才能对相应任务进入 Phase 1。



## 场景核查记录

首次 Spatial 语言候选在 init_id=1 未通过预定几何判别，未进入语言测试。改用 Object 场景中身份明确的字母汤罐与奶油奶酪。原 screening 目录的一个已完成 Spatial episode 保留为诊断记录，不计入本轮 40 个干净 episode。序列化校验问题已修正。


## 暂停结果

当前 task 0 的 7/10 未达到先导工作阈值 8/10，先保留为能力边界记录；其余任务与语言证据尚不完整，暂不宣告 Phase 1 前置条件全部通过。主统计共 143 次策略预测。机器可读结果：partial-summary.json 与 pause-status.json。准备阶段另有 14 次诊断预测，未混入主统计。停止发生在当前任务结束后的环境关闭阶段，后续任务未产生 episode。

### 接续命令

```powershell
wsl -d Ubuntu-22.04 -u root --cd /mnt/c/VLA-LIBERO --exec python3 -c "from scripts.vla import model_env, python_for, run, ROOT; run([python_for('smolvla'), ROOT / 'scripts/check_smolvla_readiness.py', '--mode', 'all', '--output', ROOT / 'outputs/readiness/smolvla-20261006-identity'], env=model_env('smolvla'))"
```

该命令会复核重置并复用已完成的十个 episode，然后接着其余任务。保持脚本和协议不变；若修改配置，应使用新输出目录。日志中的 SIGINT / KeyboardInterrupt 是用户要求的暂停，不代表本轮 episode 运行错误。等待用户说“继续核查”后再启动。

## 2026-10-07 接续

用户已要求继续核查。脚本摘要与冻结协议一致，当前复用已完成的十个 Spatial task 0 episode，执行剩余 39 次。最新日志：logs/smolvla-readiness-resume-20261007.log；实时状态：输出目录的 resume-status.json。上一节为历史暂停记录。
