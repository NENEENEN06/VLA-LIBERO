# 问题／事实包装v1：文件写入中止与重跑

2026-10-10，首轮在ramekin N完成112次查询后中止。错误为WSL原子替换`current-status.json.tmp`到`current-status.json`时`PermissionError(13)`；此时Windows端正在读取运行状态，文件占用是可能原因。没有完整N、没有A/U结果，不登记为模型失败或资格样本。保留原始输出、错误日志与112步轨迹，成本计112次，旧成本不复用。

重跑使用新的`question-context-v1-retry1-20261010`目录和日志，运行器、配置、冻结[科学条件](OPENVLA_QUESTION_CONTEXT_V1_ENTRY_20261010.md)全部不改。两个N及四个A/U从头执行，最多1800次新查询；先过两条N的规则保留。唯一操作变更是运行中通过WSL内部读取状态，避免Windows读取进程占用正在原子替换的文件；结束后才从Windows读取完整JSON。若再次发生同类错误，先修复I/O并另记修复来源，不反复重跑。

重跑ramekin N第114步成功；头112步动作、仿真状态轨迹和实际模型输入与中止轮逐条完全相同，科学配置与运行入口一致，见[重跑对照核验](assets/phase1/openvla-question-context-v1-retry-integrity-20261010.json)。没有复用旧策略调用；中止成本仍计一次。

首轮112次不计完成样本、但计成本；重跑开始前OpenVLA累计至少5348次，近期口径至少6578次。旧断电尾部／Goal中止未知成本继续另列。中止证据见[成本与文件哈希](assets/phase1/openvla-question-context-v1-interruption-ledger-20261010.json)。
