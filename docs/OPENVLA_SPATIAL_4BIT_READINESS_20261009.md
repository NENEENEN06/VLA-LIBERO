# OpenVLA Spatial 4-bit：运行核查

2026-10-09，22:44（Asia/Shanghai）完成，退出码0。**本机RTX 3070 Laptop 8GB已能加载模型并完成一条真实仿真任务，全模型驻留GPU，无CPU卸载。**

| 核查 | 结果 |
| --- | --- |
| 官方Spatial task 8，init0，原指令／原目标 | 成功，第101步将正确碗1放上盘子，101次查询 |
| 同一初始化两次真实观察预测 | 动作完全相同，最大差0；单列2次诊断 |
| 实际4-bit | 436个Linear4bit模块，全部参数位于cuda:0 |
| 加载后PyTorch分配／保留显存 | 4.40／4.50 GiB |
| 本轮PyTorch峰值分配／保留显存 | 4.73／4.84 GiB |

显存数为PyTorch统计，不包含桌面及全部渲染占用。原任务基线按220步上限、10步静置、环境seed=0、策略seed=1运行；达到原目标后第101步结束。**新增101次rollout查询＋2次诊断＝103次策略查询。** 单条成功只验证接口与这个初始化，不能作为套件成功率或主模型资格结论。

四个BF16磁盘权重分片的大小及SHA-256均与官方一致，加载时按官方4-bit默认设置量化为FP4。使用独立Python环境和原版LIBERO栈，单相机、官方JPEG/Lanczos缩放与90%面积中心裁剪、Spatial动作反归一化、夹爪二值化和反号；注意力使用PyTorch SDPA。与官方未量化／Flash Attention 2成绩的差异保留，不能直接引用论文成绩作为本配置结果。

三个初始化的双碗指代及正确A事实均通过零查询真值预检，N有效token为30／32、A为50／52，完整无截断。三个实际224裁剪画面与12份N/A输入审计的图像哈希一致，画面已审阅。init1的盘子侧碗靠近左边界、部分裁剪，但仍可辨认，此限制保留。

两次前置错误均发生在零策略查询：第一次缺LIBERO的matplotlib依赖，第二次为Windows／WSL Git行尾规则导致源码被判改动；补齐依赖及固定本地行尾规则后重试成功。错误目录和日志没有覆盖，不作为模型行为失败。

下一阶段按[冻结入口](OPENVLA_SPATIAL_4BIT_ENTRY.md)核查三初始化、两方向N；N块各至少2/3后才进入A。尚不能凭本运行核查放行正式Phase1冲突矩阵。

依据：[结果](assets/phase1/openvla-spatial-4bit-readiness-summary-20261009.json)、[实际配置及依赖](assets/phase1/openvla-spatial-4bit-readiness-manifest-20261009.json)、[预检](assets/phase1/openvla-spatial-4bit-readiness-preflight-20261009.json)、[重置预测](assets/phase1/openvla-spatial-4bit-readiness-reset-audit-20261009.json)、[画面审阅](assets/phase1/openvla-spatial-4bit-readiness-visual-review-20261009.json)、[裁剪图像核验](assets/phase1/openvla-spatial-4bit-readiness-policy-image-audit-20261009.json)、[权重完整性](assets/phase1/openvla-spatial-4bit-weight-verification-20261009.json)。

画面：[init0](assets/phase1/openvla-spatial-4bit-init0-policy224-20261009.png)、[init1](assets/phase1/openvla-spatial-4bit-init1-policy224-20261009.png)、[init2](assets/phase1/openvla-spatial-4bit-init2-policy224-20261009.png)、[原任务末帧](assets/phase1/openvla-spatial-4bit-official-end-20261009.png)。原始错误状态：[缺依赖](assets/phase1/openvla-spatial-4bit-readiness-20261009-status.json)、[行尾检查](assets/phase1/openvla-spatial-4bit-readiness-retry1-20261009-status.json)。

完整动作、轨迹、视频：`outputs/openvla-spatial-4bit/readiness-retry2-20261009/`；日志：`logs/openvla-spatial-4bit-readiness-retry2-20261009.log`。
