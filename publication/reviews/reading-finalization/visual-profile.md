# Publication Visual Profile v1.0 — FROZEN

2026-09-27 用户确认接受最新视觉实现 `1c11c5940c05fe29c46c4500935d5efb673d46a7`。本文件登记冻结状态，不修改该实现、制品或原始检查记录；接受范围与已知非阻塞限制见[接受登记](README.md)。

适用：ESD 六篇及合订阅读版；C++ G6/G7 独立版及合订试件。Balanced 与 Compact 共用字体、页边距和语义组件，只保留既有密度差异。Markdown 是事实源，出版标记不写回冻结正文。

## 硬约束

| 合同 | 当前检查 | 边界 |
| --- | --- | --- |
| 明确危险／反例标签与首段代码同页 | 源标签和第一源码行目的地；源标签内容仍通过顺序保真检查 | 只绑定源中明确、相邻、枚举的角色标签，不从程序内容推断危险性 |
| 完整实验续页重复实验 ID＋文件名；反例同时保留角色 | 每个源码分页的可提取身份 | 不能证明代码逻辑正确 |
| 短表整体；短 record 不留单字段尾页 | 短表起止目的地、record 字段页分布 | 长比较矩阵保留横向扫描，不一律转换成 record |
| Empty Template 有稳定名称和有序字段 | 独立 `empty-template` ledger；空 `row_text`，无虚构数据行 | 可手写空值线是出版视图，不是交互式 AcroForm 或填表完成证据 |
| 短空模板整体；长空模板续页重复名称 | 起止页与续页标题；38 字段真实编译回归 | 单个字段超出可排版高度不属于自动布局保证 |
| Record label/value 首行对齐 | PDF 目的地同页且垂直差不超过 0.8 pt；实际页图 | 容差用于浮点坐标比较，不是以压缩行距遮掩错位 |
| 代码源码换行与视觉续行可区分 | 保留源行号目的地；hanging indent＋非文本矢量续行提示 | 文本提取不等于各阅读器复制缩进认证 |
| ASCII／flow 不静默折行 | `PreviewFlow` 不启用折行；宽度／overfull 阻断 | 不通过删行、重画边或缩小字号改变图语义 |
| 极短纯闭合／主要闭合代码尾页阻断 | 源行分页分组；少量非空行以闭合符号为主时触发 | 当前阈值是候选信号，不是永久“每页至少 N 行”的美学定律 |
| 冻结内容与受保护制品不变 | 精确 Git 字节／SHA-256 与 `design/dist/` 完整文件集合 | 不把重新排版称为重新完成技术验收 |

硬约束失败时不登记视觉冻结。`PREVIEW_READY`、`STRUCTURAL_PASS`、实际视觉审阅、独立接受是不同阶段。

## Code 与标签

首段显示源中原有的完整角色说明，包括危险条件；实验 ID、文件名不再额外重复一层 Cxx 标签。后续页采用“角色 · 实验 ID · 文件名 · continued”。普通 literal／snippet 不打印无导航作用的内部块 ID；仍保留细边界和必要续页标签。

源标签从相邻普通段落移入代码框标题，只改变排版位置，不删字、不缩短警告。源 AST 和原始代码仍独立保留；内容审计只排除可枚举的生成续页标签，不排除首次源警告。

## Soft-wrap

优先级依次为：源空格；语义边界 `| , ; : ! ? =`；identifier 边界 `_ / . -`；最后才是任意字符应急断点。使用不同 penalty，保持原始 verbatim 字符串，不在源字节中插入标记。普通单词和 `OPERATIONAL` 不应为了接近行末而被拆开。

矢量续行标记不进入文本提取；无分隔的极长 token 允许应急折行。下划线用 verbatim 相同的字符类别比较，避免 TeX 的下标类别误使该边界失效。此实现依赖已绑定版本的 fvextra 扫描器；工具链升级必须重跑对应真实回归，不宣称跨版本私有宏兼容。

## 收尾分页与自然留白

仅对 profile 中精确绑定的短收尾组应用 keep 与局部 spacing：Ops §30；G6 §18–19。无物理页码条件。收尾容器结束后重新提交 running mark，避免页眉仍显示前一节。

不以填满页为目标。章节开场、Final Gate 分界及完整过渡／参考单元可以留白；不得缩字号、压代码行距、删掉结语或拆散完整实验来提高占满率。Compact 不再让一个短参考入口单独成页，但允许“过渡＋参考”作为完整退出单元。

## 人工判据与语义 corpus

实际页图分别确认：标题层级、自然密度、连续阅读节奏、矩阵横向扫描、record 紧凑度、Gate 问题单元、页眉定位、辅助标签克制。自动检查不替代这些判断。

活动 [corpus](../../tools/reading-corpus.json) 以语义目的和精确源对象绑定，不把第 N 页当作永久身份。覆盖 danger-role-binding、short-tail-page、empty-template-continuation、record-baseline-alignment、semantic-soft-wrap、experiment-continuation、comparison-matrix、chapter-navigation、heading-hierarchy 与 reader-facing-code-identity。实际页码和 PNG 摘要是每次渲染的观察结果。

## 状态转换

```text
STRUCTURAL_PASS
        +
VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL
        ↓
Publication Visual Profile v1.0 Freeze Candidate
        ↓ 用户于 2026-09-27 接受最新 1c11c59
VISUAL_PROFILE_FROZEN v1.0
```

组件政策和两个产品的 profile 作为同一视觉基线接受，不把系统架构稳定、正文冻结、视觉冻结、正式发布混为一种状态。原 `STRUCTURAL_PASS` 与自查标签不改写为独立验证；普通留白、偶发短尾和局部折行不触发再设计，真正 blocker 仍须处理。正式发布仍为 `NOT RELEASED`；全 G0–G12 出版另行启动。
