# Spatial 双碗辅助事实模板

2026-10-08。SmolVLA、Spatial task 8、原双碗、init0..2；模板在新增策略查询前冻结。三初始化的几何、事实真值、完整文本及实际画面预检通过。这里只冻结文本与标注，不代表模型已理解附加事实。

## 原版基础指令

| 问题 | 完整指令 | 视觉目标 |
| --- | --- | --- |
| Q_A | `pick up the black bowl next to the plate and place it on the plate` | 碗1上盘子 |
| Q_B | `pick up the black bowl next to the ramekin and place it on the plate` | 碗2上盘子 |

N逐字保留原文；其他条件按 `原指令 + 换行 + 辅助事实` 拼接，原生处理器再追加末尾换行。事实均明确对应初始布局，episode内不变。

## 冻结的辅助事实

| 条件 | Q_A附加文本 | Q_B附加文本 |
| --- | --- | --- |
| A 正确事实 | `Initially, the black bowl farther from the ramekin is next to the plate.` | `Initially, the black bowl farther from the plate is next to the ramekin.` |
| X 最小冲突 | `Initially, the black bowl closer to the ramekin is next to the plate.` | `Initially, the black bowl closer to the plate is next to the ramekin.` |
| U 无关事实 | `Initially, the plate and the ramekin are both resting on the table surface.` | 同Q_A |

A/X只替换farther／closer，没有增加新的动作命令或模型不可理解的内部碗编号。用另一参照物的距离描述提供独立对象标识：Q_A的X文本指向碗2，Q_B的X指向碗1。U只描述两个参照物的共同支撑，不提供黑碗选择线索。

| 实际有效token | N | A | X | U | 上限 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q_A | 16 | 34 | 34 | 34 | 48 |
| Q_B | 18 | 36 | 36 | 36 | 48 |

三个初始化结果一致，完整解码匹配，无截断；长度包括原生末尾换行。等长控制限于各Q内部，两个Q之间不要求等长。原生双相机及本体处理保持不变。

## 真值和画面核查

参照物旁碗按两候选到参照物的XY中心距离及实际画面判定，距离对比至少0.05米；独立farther／closer描述同样要求至少0.05米对比。没有把初始化出生区域的窄矩形边界当作自然语言next to的真值。

| 初始化 | 盘子侧两碗距离差 | ramekin侧两碗距离差 |
| --- | ---: | ---: |
| init0 | 0.144 m | 0.119 m |
| init1 | 0.149 m | 0.126 m |
| init2 | 0.133 m | 0.078 m |

初始A关系成立，X所指另一碗的关系不成立。U的桌面支撑由盘子／ramekin与table_collision的接触核对。主相机中两只黑碗和两个参照物可辨认；腕部视野较窄，未声称覆盖所有候选。真值、接触和内部对象身份只供评估，不输入策略。

首次预检错误是把出生区域On谓词用于自然语言next to，init0碗中心略超窄区域边界导致停止；当时零策略查询、零完成rollout。修正保留原0.05米距离门槛，并将区域谓词仅作诊断，U改用实际桌面接触。英文文本未因观察模型结果而改变。旧错误、manifest及脚本快照保留。

本轮只运行N/A，X/U仅通过零查询预检。A成功只说明该追加条件可用，不单独证明farther／closer语义理解或文本线索独立有效；后续解读冲突结果仍需按证据区分默认偏好与线索作用。

依据：[冻结配置](assets/phase1/smolvla-spatial-na-manifest-20261008.json)、[三初始化预检与输入](assets/phase1/smolvla-spatial-na-preflight-20261008.json)、[画面核对](assets/phase1/smolvla-spatial-na-image-review-20261008.json)、[零查询错误](assets/phase1/smolvla-spatial-na-preflight-error-20261008.json)、[N/A脚本](../scripts/check_phase1_smolvla_spatial_na.py)。完整产物位于本地 `outputs/phase1/smolvla-spatial-NA-20261008-retry1/`。当前推进规则见[Phase 1入口](PHASE1_ENTRY.md)。
