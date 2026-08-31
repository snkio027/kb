# 总体设计判断

这两篇文档不应被做成两个彼此无关的“漂亮 PDF”，而应设计成一套具有统一身份、明确层级和不同阅读模式的**双卷工程标准文档体系**：

```text
优秀系统设计与工程保证标准 · v1.1.0

卷一 ESD-METHOD-001
《优秀系统设计与工程保证方法论》
规范性基础 / Normative Foundation

卷二 ESD-REFERENCE-001
《优秀系统设计：从约束、不变量到证据》
工程操作手册 / Operational Reference
```

两份 PDF 应共享同一套：

- 字体系统；
- 页面网格；
- 元数据结构；
- 颜色语义；
- 标题层级；
- 表格、代码、提示框和图表组件；
- 构建与质量保证机制。

但两者不应使用完全相同的正文排版。文档 1 是需要连续阅读的规范性专著，文档 2 是需要快速定位和反复查阅的工程手册。

Markdown 继续作为唯一事实来源：

```text
Markdown = authoritative source
LaTeX    = rendering and publication layer
PDF      = immutable release view
```

不得在生成的 LaTeX 中手工维护第二份内容副本。

---

# 一、采用的现代 LaTeX 技术基线

## 1. 固定“最新稳定版”，而不是每次构建滚动升级

截至 2026 年 8 月 31 日，适合本项目的稳定基线是：

| 组件          | 建议基线                                         |
| ------------- | ------------------------------------------------ |
| TeX 发行版    | TeX Live 2026，固定到明确 snapshot 或容器 digest |
| LaTeX kernel  | 2026-06-01 stable release                        |
| PDF 引擎      | LuaHBTeX，通过 `lualatex` 调用                   |
| Markdown 转换 | Pandoc 3.11                                      |
| 构建调度      | `latexmk`                                        |
| 字体接口      | `fontspec`                                       |
| 中文排版      | 主发布版本优先使用 `ctex`                        |
| PDF 管理      | LaTeX `\DocumentMetadata` / PDF management layer |

TeX Live 2026 是当前正式发行版；LaTeX 当前稳定内核为 2026-06-01；Pandoc 3.11 于 2026-08-28 发布。工程上应使用这些当前版本建立一次经过验证的 lock，而不是在每次 CI 构建时自动拉取“当天最新包”。([TeX Users Group][1])

推荐流水线：

```text
Markdown
   ↓
Pandoc AST
   ↓
project-specific Lua filters
   ↓
custom LaTeX template
   ↓
esdbook.cls + esd-theme.sty
   ↓
latexmk + LuaLaTeX
   ↓
PDF preflight
   ↓
rendered-page verification
   ↓
release PDF
```

Pandoc 的 Lua Filter 在 AST 层工作，适合完成标题规范化、语义块映射、表格分类和跨文档引用处理，比在 Markdown 上执行正则替换更可靠。([Pandoc][2])

## 2. 不使用以下方案作为主基线

不建议：

- 直接使用 Pandoc 默认 LaTeX 模板；
- 套用 `ElegantBook` 等成品模板；
- 使用 HTML/CSS 打印成 PDF；
- 在 Markdown 中大量嵌入 Raw LaTeX；
- 使用 XeLaTeX 作为默认引擎；
- 使用未固定版本的在线 LaTeX 服务；
- 为了语法高亮默认开启 unrestricted `shell-escape`；
- 把字体文件、主题和正文耦合在一个巨大 `.tex` 中。

原因不是这些方案一定无法工作，而是它们难以同时满足：

- 双文档统一设计；
- 中文长文排版；
- 多页表格；
- 大量代码和文本图；
- 可复现构建；
- 长期版本演进；
- 自动化视觉验证；
- 文档级工程保证。

---

# 二、关于 PDF/UA-2 的关键校准

2026 年的 LaTeX 已经具备生成 PDF/UA-2 和可访问数学内容的正式能力，LaTeX 2026 的 tagging 支持也持续完善。([LaTeX Project][3])

但这里不能直接得出：

```text
最新版 LaTeX
+
\DocumentMetadata{pdfstandard=ua-2}
=
这两份中文 PDF 已符合 PDF/UA-2
```

当前 `ctex` 2.6.5 在 CTAN 上明确标记为 **Tagged PDF incompatible**；`luatexja` 则仅标记为 **partially compatible**。这意味着主发布版本若使用 `ctex`，不得仅因为编译成功就在元数据中宣称 PDF/UA-2 合规。([CTAN][4])

因此建议建立两个构建 Profile。

## Profile A：Professional Release

这是正式交付基线：

```text
LuaLaTeX
+ ctex
+ custom class
+ embedded fonts
+ PDF bookmarks
+ correct metadata
+ reliable text extraction
+ visual and structural preflight
```

目标是：

- 专业视觉；
- 正确中文断行和标点；
- 良好复制与搜索；
- 字体完整嵌入；
- 清晰阅读顺序；
- 可靠跨平台显示。

但不声明未经验证的 PDF/UA-2 合规。

## Profile B：Accessible Experimental

作为独立验证分支：

```text
standard/KOMA book class
+ luatexja
+ ChineseJFM
+ fontspec
+ DocumentMetadata
+ PDF 2.0
+ PDF/UA-2 validation
```

`ChineseJFM` 可为 LuaTeX-ja 提供更适合中文的全角、半角和开明式标点度量，但这条路径需要单独完成中文排版和 tagging 验证。([CTAN][5])

只有通过以下检查后，才可以在发布说明中写入 PDF/UA-2：

- 自动验证器通过；
- 结构树人工抽查；
- 标题层级正确；
- 表头和数据单元关系正确；
- 图表存在替代文本；
- 代码块阅读顺序正确；
- 中英文复制顺序正确；
- 至少一种屏幕阅读器完成 smoke test。

专业设计的正确做法是**保留真实的 `UNKNOWN`**，而不是把可访问性标签当作装饰性元数据。这与两篇文档本身的认识论原则完全一致。

---

# 三、双卷文档的视觉定位

## 1. 统一品牌层

两篇 PDF 共享：

- 套系名：`优秀系统设计与工程保证标准`；
- 套系版本：`1.1.0`；
- 文档编号；
- 作者或 Owner；
- 发布日期；
- 状态；
- 规范优先级；
- 一致的封面网格；
- 一致的字体和基础色；
- 一致的页眉页脚；
- 一致的组件视觉语言。

## 2. 文档 1：规范性专著风格

`ESD-METHOD-001` 的视觉关键词：

```text
严谨
克制
稳定
权威
连续阅读
思想密度
```

设计特征：

- 深蓝作为主强调色；
- 更大的章节留白；
- 正文采用适合长时间阅读的宋体/衬线字体；
- 段落使用约 `2em` 首行缩进；
- 段间距较小；
- 核心定义和原则使用细左边线，而不是大面积彩色盒子；
- “十条总纲”“严格定义”“认识论边界”等内容形成视觉锚点；
- 章节首页允许出现一段短的 chapter thesis；
- 图表数量少而精，突出推导关系而不是操作步骤。

它应更像：

> 一份成熟的工程理论标准或专业技术专著。

## 3. 文档 2：工程操作手册风格

`ESD-REFERENCE-001` 的视觉关键词：

```text
可扫描
可定位
可复制
可执行
高信息密度
强导航
```

设计特征：

- 深青绿色作为主强调色；
- `Stage 0–9` 和 `Gate 0–9` 成为强导航元素；
- 正文不使用首行缩进；
- 段落之间保留适度间距；
- 表格、模板和 Checklist 的层级更突出；
- 页眉中展示当前 Stage 或章节；
- Gate 条件、阻断条件和裁决状态使用一致的语义组件；
- 工程模板采用可复制、可识别的专用版式；
- CAN 案例中的数据流、提交协议和资源边界使用矢量图；
- 章节开头提供“输入 / 产出 / Gate”的三段式摘要。

它应更像：

> 一份能够放在 Architecture Review 会议中直接使用的专业 Reference Manual。

---

# 四、页面规格与版心

## 1. 纸张和阅读目标

默认采用：

```text
A4
210 × 297 mm
oneside
digital-first
office-print friendly
openany
```

不使用传统书籍的强制奇数页开章，也不产生无意义的空白页。

建议页面尺寸：

| 项目           |         建议值 |
| -------------- | -------------: |
| 左边距         |          22 mm |
| 右边距         |          22 mm |
| 上边距         |          20 mm |
| 下边距         |          24 mm |
| 正文宽度       |      约 166 mm |
| 正文有效高度   |  约 238–244 mm |
| 页眉与正文间距 |        约 7 mm |
| 页脚基线       | 距底部约 12 mm |

该版心在 A4 上可以同时容纳：

- 约 42–46 个中文字符宽度；
- 多列工程表格；
- 80–95 字符宽的代码块；
- 不低于 8.5 pt 的表格字体。

## 2. 正文字号

建议基线：

| 元素         | 字号与行距                 |
| ------------ | -------------------------- |
| 中文正文     | 10.5 pt，基线约 16.5–17 pt |
| 英文正文     | 与中文视觉等高             |
| 表格正文     | 9–9.5 pt                   |
| 代码块       | 8.8–9.2 pt                 |
| 脚注         | 8.5–9 pt                   |
| 一级章节标题 | 26–30 pt                   |
| 二级标题     | 15.5–17 pt                 |
| 三级标题     | 12–13 pt                   |
| 封面主标题   | 32–38 pt                   |

任何内容都不得为了塞进页面而缩小到难以阅读。

明确禁止：

```text
\resizebox{\textwidth}{!}{整个复杂表格}
```

宽表应依次采用：

1. 改写列内容；
2. 调整列宽；
3. 允许单元格自然换行；
4. 使用较小但可读的表格字号；
5. 必要时单页横置；
6. 最后才考虑拆分表格。

---

# 五、字体系统

## 1. 推荐字体角色

建议使用开源、可固定版本的字体组合：

| 角色         | 推荐字体                                      |
| ------------ | --------------------------------------------- |
| 中文正文     | Source Han Serif SC / 思源宋体                |
| 中文标题     | Source Han Sans SC / 思源黑体                 |
| 拉丁正文     | Source Serif 4                                |
| 拉丁标题     | Source Sans 3                                 |
| 代码与文本图 | Sarasa Mono SC 或 Noto Sans Mono CJK SC       |
| 数学         | 与 Source Serif 风格相容的 OpenType Math 字体 |

`fontspec` 是 LuaLaTeX 和 XeLaTeX 的现代 OpenType 字体接口，当前版本支持最新 LaTeX 字体体系。([CTAN][6])

## 2. 字体规则

Codex 实现时应遵守：

- 明确配置 Regular、Medium、Semibold、Bold；
- 不允许 LaTeX 人工合成中文斜体；
- 中文强调优先使用字重、颜色或结构，不使用伪斜体；
- 正文拉丁字符使用衬线字体；
- 标题、标签和元数据使用无衬线字体；
- 代码禁用连字；
- 表格数字启用 tabular numerals；
- 字体必须嵌入或子集嵌入；
- CI 构建使用固定字体版本和校验和；
- 不把商业字体作为可复现构建的必要依赖。

可以提供本地“高级字体覆盖 Profile”，但正式 CI 仍应使用开源字体。

---

# 六、颜色与视觉语言

建议采用低饱和、印刷友好的颜色系统。

## 1. 基础颜色

```text
Ink             #18212B
Secondary Ink   #596672
Paper           #FBFBFA
Soft Panel      #F3F5F7
Rule            #D4DAE0
```

## 2. 文档强调色

```text
Methodology     #204A74  深蓝
Reference       #0F6B63  深青绿
```

## 3. 状态颜色

```text
GO               深绿
CONDITIONAL_GO   琥珀
NO_GO            暗红
UNKNOWN          紫灰
NOT_APPLICABLE   中性灰
```

颜色不得单独承担语义。每种状态必须同时包含：

- 完整文本；
- 不同边框或标签形状；
- 可在黑白打印中区分的明度。

大面积纯色背景应只出现在封面和章节起始页。正文主要依靠字体层级、留白和细线，而不是不断堆叠彩色框。

---

# 七、封面设计

## 1. 统一封面网格

建议封面由四个区域组成：

```text
┌──────────────────────────────────────┐
│ 优秀系统设计与工程保证标准            │
│ Engineering System Design Suite      │
│                                      │
│                                      │
│ 主要标题                              │
│ 副标题                                │
│                                      │
│              抽象结构图形             │
│                                      │
│ ESD-METHOD-001 / v1.1.0              │
│ BASELINE / NORMATIVE FOUNDATION      │
│ Elliott Bai · 2026-08-31             │
└──────────────────────────────────────┘
```

## 2. 图形语言

不使用：

- 服务器机房照片；
- 云、齿轮、芯片等通用科技素材；
- 大量渐变；
- 3D 图标；
- 股票模板式封面。

使用抽象的矢量结构：

- 约束线；
- 状态节点；
- 闭环控制箭头；
- `Claim → Property → Verification → Evidence` 链；
- 四平面之间的边界关系。

图形由 TikZ 生成，保持矢量质量。

## 3. 两卷的差异

文档 1：

- 深蓝；
- 更开放的留白；
- 图形较抽象；
- 体现“原则、边界与推导”。

文档 2：

- 深青绿；
- 网格更明确；
- 图形更接近 Stage/Gate 流程；
- 体现“执行、门禁与证据”。

---

# 八、前置页面设计

每篇 PDF 建议依次包含：

```text
封面
文档控制页
规范关系页
版本与变更记录
如何使用本文
目录
正文
附录
封底或版本声明页
```

## 1. 文档控制页

将现有 Markdown 中的属性表转化成专业的 Document Control Panel：

```text
Document ID
Title
Version
Status
Role
Normative precedence
Companion document
Owner
Publication date
Review cycle
Authoritative source
Supersedes
```

其中：

- `BASELINE` 使用状态标签；
- `NORMATIVE FOUNDATION` 和 `OPERATIONAL REFERENCE` 显著区分；
- `Markdown is authoritative` 作为明确声明；
- companion document 可点击跳转到仓库页面或另一 PDF。

## 2. 阅读路径

文档 1 建议增加：

```text
完整阅读
架构师快速阅读
工程保证专题阅读
组织落地专题阅读
```

文档 2 建议增加：

```text
新系统设计路径
重大变更评审路径
Production Readiness 路径
事故后 Assurance Delta 路径
```

## 3. 目录

- 目录深度固定为两级；
- 一级章节突出；
- 二级标题紧凑；
- 不把所有三级标题放入目录；
- PDF Bookmarks 与视觉目录同步；
- 所有条目可点击；
- 附录单独分组。

---

# 九、标题层级处理

两份 Markdown 当前已经包含人工章节编号，例如：

```text
# 6. 从问题、约束与风险开始
## 6.1 问题定义
```

LaTeX 不应再次自动生成重复编号。

推荐在 Pandoc Lua Filter 中：

1. 识别标题前缀；
2. 在 PDF 输出阶段移除显示文本中的人工编号；
3. 保存其逻辑层级和稳定 ID；
4. 由 LaTeX 统一生成编号；
5. 不修改原 Markdown。

即：

```text
Markdown:
# 6. 从问题、约束与风险开始

Rendered:
6  从问题、约束与风险开始
```

而不是：

```text
6  6. 从问题、约束与风险开始
```

编号深度建议：

```text
Chapter / H1       编号
Section / H2       编号
Subsection / H3    不编号，默认不进入 TOC
```

`Stage 0`、`Gate 0`、`R0–R3` 等业务语义编号不得被过滤器当作章节编号删除。

---

# 十、正文组件体系

## 1. 原则与定义

现有块引用应根据语义转换为不同组件，而不是全部使用同一种灰色引用框。

### Principle

适合：

```text
约束先于架构
UNKNOWN 不是较弱的 GO
```

视觉：

- 左侧 2–3 pt 强调线；
- 无大面积背景；
- 标题小型大写或粗体；
- 内容保持正文尺寸。

### Definition

适合严格定义：

- 淡色背景；
- 顶部 `DEFINITION` 标签；
- 可设置稳定编号；
- 允许跨页。

### Warning

适合：

- 不得将验证未执行解释为 PASS；
- 不得先提交 Kafka offset 再提交正式结果。

视觉上使用边框和警告文本，不依赖图标或颜色。

### Example

使用轻灰背景，强调其非规范性。

### Decision / Gate

文档 2 专用：

```text
GATE 4
Failure Semantics Are Closed
```

包含：

- 进入条件；
- `GO` 条件；
- `NO_GO` 条件；
- 必要证据。

## 2. 规范性术语

以下词应形成统一 Inline Role：

```text
MUST
MUST NOT
SHOULD
MAY
UNKNOWN
GO
CONDITIONAL_GO
NO_GO
NOT_APPLICABLE
```

显示方式：

- 小型无衬线；
- 半粗体；
- 微弱背景或下边框；
- 不在正文中制造过多彩色胶囊。

---

# 十一、表格设计

这两份文档大量使用表格，表格质量将直接决定 PDF 是否专业。

## 1. 基本规则

- 使用 `booktabs` 风格；
- 不使用竖线；
- 表头使用轻背景和半粗体；
- 单元格顶部对齐；
- 中文长文本使用 ragged-right；
- 数字列右对齐；
- 代码、状态值和标识符保持等宽；
- 多页表格自动重复表头；
- 表格可跨页；
- 行内代码不得撑破列宽；
- 长英文标识允许在 `_`、`/`、`.`、`-` 后断行。

## 2. 表格类型

需要至少定义四种语义表：

| 类型            | 用途                                |
| --------------- | ----------------------------------- |
| Metadata Table  | 文档属性、状态、Owner               |
| Decision Table  | 选项、约束、后果、裁决              |
| Register Table  | Invariant、State、Failure、Evidence |
| Checklist Table | 条件、状态、证据、Owner             |

## 3. 宽表策略

Codex 应在 AST 层给表格分类：

```text
normal
wide
landscape
register
checklist
```

不能依靠 LaTeX 在排版失败后自动缩小整个表格。

---

# 十二、代码块与文本图

这两篇文档包含大量：

- 伪代码；
- 状态链；
- 数据流；
- YAML；
- Markdown 模板；
- CLI 示例；
- ASCII 架构图。

## 1. 基线实现

不建议默认使用 `minted`，因为它会增加 shell execution、Python 和 Pygments 依赖。

推荐：

```text
Pandoc native highlighting
+ fvextra
+ breakable custom environment
+ restrained syntax colors
```

代码块要求：

- 支持跨页；
- 支持长行软换行；
- 可关闭换行以保护 ASCII 图；
- 复制文本不插入额外字符；
- 中文注释显示正确；
- 代码字体不使用连字；
- 背景接近纸色；
- 使用细边框或左边线，而不是厚重卡片。

## 2. 区分代码与架构文本图

需要两个不同环境：

```text
ESDCode
ESDFlow
```

`ESDCode`：

- 可换行；
- 可语法高亮；
- 可显示语言标签。

`ESDFlow`：

- 不自动换行；
- 保持空格；
- 使用稍小字号；
- 编译时检测溢出；
- 溢出时失败，而不是静默缩放到不可读。

## 3. 模板章节

文档 2 的 ADR、Exception、Change Envelope 等模板，应使用“模板页”视觉：

- 顶部模板名称和用途；
- 中间保持原始 Markdown 结构；
- 浅灰背景；
- 复制友好；
- 不把模板内的 `#` 误识别为 PDF 章节标题。

Pandoc AST 本身可以正确区分 fenced code 中的标题字符，Codex 不得使用纯文本正则处理全文。

---

# 十三、图表与架构图

不需要把所有 ASCII 流程都重画。

建议只制作 6–8 张具有长期价值的 Canonical Figures：

## 文档 1

1. 完整架构推导链；
2. Desired Claim 到 Evidence-backed Decision 的四层模型；
3. Data / Control / Management / Assurance 四平面；
4. Critical Property 到 Evidence 的工程保证闭环；
5. 变更、运行反馈和 Assurance Delta 的演进闭环。

## 文档 2

1. Stage 0–9 / Gate 0–9 总览；
2. Architecture Review 输入、评审与裁决流程；
3. CAN 数据处理流水线；
4. CAN 正式提交与 Kafka ACK 时序；
5. 资源预算与背压传播图。

图表要求：

- 使用 TikZ/PGF 或预生成的矢量 PDF；
- 不使用位图截图；
- 图中文字与正文字体一致；
- 有图号和标题；
- 有稳定引用 ID；
- 提供 alt text；
- 图中的颜色不是唯一语义载体；
- 图宽不得超过版心；
- 图中最小字号不低于正文脚注字号。

---

# 十四、页眉、页脚与导航

## 文档 1

页眉：

```text
左：优秀系统设计与工程保证标准
右：当前章节名
```

页脚：

```text
ESD-METHOD-001 · v1.1.0       27
```

## 文档 2

页眉：

```text
左：当前 Stage / 当前章节
右：ESD-REFERENCE-001
```

页脚：

```text
BASELINE · v1.1.0             42
```

规则：

- 首页和章节起始页使用简化页眉；
- 页码始终处于固定位置；
- 不使用装饰性粗线；
- Header 中的长章节标题必须智能截断；
- PDF Bookmarks 负责电子导航，页眉负责视觉定位；
- 文档 2 可以使用微弱的 Stage 颜色条，但不能设计成复杂的实体书页边标签。

---

# 十五、两篇文档应有的差异化正文节奏

| 维度       | 文档 1         | 文档 2                 |
| ---------- | -------------- | ---------------------- |
| 阅读方式   | 连续阅读       | 查询和执行             |
| 段落       | 2em 首行缩进   | 无缩进、适度段间距     |
| 留白       | 更宽松         | 更紧凑                 |
| 表格密度   | 中             | 高                     |
| Callout    | 原则、定义     | Gate、输入、产出、阻断 |
| 章节首页   | 论点式         | 操作摘要式             |
| 强调色     | 深蓝           | 深青绿                 |
| 导航       | 章节导航       | Stage/Gate 导航        |
| 代码与模板 | 较少           | 大量                   |
| 附录       | 术语、参考资料 | 模板、Checklist、案例  |

这使两篇文档“属于同一标准”，但不会让读者误以为只是换了标题的同一版式。

---

# 十六、Markdown 到 PDF 的工程结构

建议 Codex 创建如下目录：

```text
docs/
├── 01-优秀系统设计与工程保证方法论-v1.1.0.md
└── 02-优秀系统设计-从约束不变量到证据-v1.1.0.md

publication/
├── esdbook.cls
├── esd-theme.sty
├── template.tex
├── metadata/
│   ├── methodology.yaml
│   └── reference.yaml
├── filters/
│   ├── normalize-headings.lua
│   ├── semantic-blocks.lua
│   ├── tables.lua
│   ├── code-blocks.lua
│   ├── cross-references.lua
│   └── pdf-metadata.lua
├── diagrams/
│   ├── derivation-chain.tex
│   ├── assurance-chain.tex
│   ├── four-planes.tex
│   ├── stage-gate.tex
│   ├── can-pipeline.tex
│   └── commit-sequence.tex
├── profiles/
│   ├── release.yaml
│   └── accessible-experimental.yaml
├── fonts.lock
├── texlive.profile
└── package-lock.txt

scripts/
├── build.sh
├── preflight.sh
├── render-verify.sh
└── compare-renders.sh

build/
dist/
```

## 1. `esdbook.cls`

只处理稳定的文档结构：

- 基础 class；
- 页面尺寸；
- 字体基线；
- 章节层级；
- 页眉页脚；
- Front Matter；
- TOC；
- metadata；
- appendix；
- PDF bookmarks。

## 2. `esd-theme.sty`

处理可变化的视觉系统：

- 颜色；
- 文档 Profile；
- 表格样式；
- code block；
- callout；
- status；
- Gate；
- template；
- chapter opening。

## 3. Lua Filters

处理 Markdown 语义与 LaTeX 输出之间的映射。

不要把这些逻辑塞进：

- Bash `sed`；
- 巨大的 Pandoc CLI；
- Markdown 正文；
- 难以测试的 LaTeX 宏。

---

# 十七、Markdown 最小调整原则

原始 Markdown 应尽量保持通用性。

允许增加少量 Pandoc fenced div：

```markdown
::: principle
约束先于架构。
:::

::: definition
优秀的系统是……
:::

::: warning
UNKNOWN 不得被静默解释为 PASS。
:::

::: gate
Gate 4：Failure Semantics Are Closed
:::
```

但不允许为视觉布局写入：

```markdown
\begin{tcolorbox}
...
\end{tcolorbox}
```

也不允许在 Markdown 中加入：

- 页边距；
- 字号；
- 颜色值；
- 强制分页；
- 字体名称；
- 表格列宽；
- 页眉页脚。

内容语义属于 Markdown，视觉策略属于 LaTeX。

---

# 十八、构建可复现性

“使用最新版本”和“构建可复现”并不冲突。

正确流程：

```text
选择当前最新稳定基线
→ 完成兼容性验证
→ 固定版本与 digest
→ 只通过受控升级 PR 更新
```

应记录：

```text
TeX Live release
TeX Live snapshot date
LaTeX kernel version
LuaHBTeX version
Pandoc version
latexmk version
ctex version
fontspec version
font names and versions
Lua filter hashes
class/style hashes
SOURCE_DATE_EPOCH
```

构建结果附带：

```text
build-manifest.json
sha256sums.txt
```

PDF 元数据中的发布日期来自 Markdown，不使用构建机器当前时间覆盖文档发布日期。

---

# 十九、质量门禁

Codex 的 Definition of Done 不应是“成功生成 PDF”，而应包含以下门禁。

## Gate A：内容完整性

- 两篇 Markdown 均被完整转换；
- 标题数量一致；
- 表格数量一致；
- 代码块数量一致；
- 无段落静默丢失；
- Front Matter 字段完整；
- companion document 引用正确；
- 无重复文档主标题。

## Gate B：LaTeX 正确性

- 编译退出码为 0；
- 无 undefined reference；
- 无 missing glyph；
- 无 duplicate destination；
- 无未处理 citation；
- 无严重 LaTeX warning；
- overfull box 超过 1 pt 时失败；
- 不允许依靠 emergency stretch 掩盖结构问题。

## Gate C：PDF 结构

- 页面全部为 A4；
- 字体全部嵌入或子集嵌入；
- PDF Metadata 正确；
- `lang=zh-CN`；
- 目录和 Bookmarks 可点击；
- 文档 ID、版本、状态正确；
- 无 JavaScript；
- 无意外附件；
- 外部链接协议符合白名单；
- 文本可搜索、可复制。

## Gate D：视觉验证

将 PDF 按 180–200 DPI 渲染为 PNG，检查：

- 封面；
- 文档控制页；
- TOC；
- 每个章节首页；
- 每种表格；
- 每种 callout；
- 最长代码块；
- 最宽 ASCII 图；
- 多页表格；
- 横置表格；
- 附录；
- 最后一页。

必须满足：

- 无裁切；
- 无文字重叠；
- 无孤立标题；
- 无黑方块；
- 无字体替换；
- 无表格断裂；
- 无不可读缩放；
- 页眉页脚不与正文冲突。

## Gate E：视觉回归

首次定稿后保存关键页面 reference renders。

后续变更执行：

```text
old PDF render
vs
new PDF render
```

差异必须被：

- 预期接受；
- 或解释；
- 或阻断。

## Gate F：跨阅读器 Smoke Test

至少检查：

- macOS Preview；
- Chrome PDF Viewer；
- Acrobat Reader；
- 一种基于 PDFium 的渲染器；
- 一种基于 Poppler 的渲染器。

## Gate G：可访问性 Profile

仅 Accessible Experimental Profile 执行：

- PDF/UA-2 validator；
- 结构树；
- reading order；
- table headers；
- alt text；
- code/verbatim；
- 中英文混排；
- 屏幕阅读器 smoke。

失败时输出：

```text
ACCESSIBILITY STATUS: UNKNOWN / NOT RELEASE-QUALIFIED
```

而不是从构建结果中删除失败信息。

---

# 二十、先做排版试件，不直接排完整文档

Codex 不应一开始就对 3000 多行 Markdown 反复调样式。

先建立一个 `specimen.md`，覆盖最危险的页面元素：

```text
封面
Document Control
TOC
中文长段落
中英文混排
一级、二级、三级标题
嵌套列表
长 blockquote
两列表格
六列表格
多页表格
长 URL
inline code
YAML code block
C++/Rust code block
ASCII pipeline
Gate callout
UNKNOWN / NO_GO 状态
脚注
交叉引用
附录
```

实现顺序：

```text
1. 生成 specimen
2. 固定字体与版心
3. 固定标题层级
4. 固定表格和代码组件
5. 固定封面与 Front Matter
6. 通过视觉门禁
7. 再接入完整文档
8. 修复真实内容暴露的极端情况
9. 建立视觉回归基线
```

这比在完整文档上边改内容边调样式更确定。

---

# 二十一、给 Codex 的实施契约

下面这段可以直接作为 Codex 的任务定义。

---

## Objective

基于两份权威 Markdown，构建一套专业、统一、可复现、可验证的双卷 PDF 出版系统：

```text
ESD-METHOD-001
ESD-REFERENCE-001
```

Markdown 必须保持唯一事实来源。生成的 LaTeX 不是人工维护的内容副本。

## Required Stack

```text
TeX Live 2026 pinned snapshot
LaTeX kernel 2026-06-01
LuaLaTeX / LuaHBTeX
Pandoc 3.11
latexmk
custom LaTeX class and theme
Pandoc Lua filters
```

## Required Outputs

```text
dist/
├── 01-优秀系统设计与工程保证方法论-v1.1.0.pdf
├── 02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf
├── build-manifest.json
└── sha256sums.txt
```

不生成 DOCX，不修改权威 Markdown 的语义内容。

## Required Design

- A4；
- 中文专业技术出版物风格；
- 双文档统一视觉系统；
- 文档 1 使用规范性专著 Profile；
- 文档 2 使用工程参考手册 Profile；
- Source Han / Source 系列字体；
- restrained color system；
- 可点击目录和 Bookmarks；
- 多页表格；
- breakable code blocks；
- Canonical TikZ figures；
- 稳定页眉页脚；
- 文档 ID、版本、状态和规范优先级明确。

## Required Filters

- 消除封面标题与正文 H1 重复；
- 处理人工章节编号；
- 保持 Stage/Gate 等语义编号；
- 映射 semantic fenced div；
- 分类表格；
- 分类 code/flow block；
- 建立稳定 heading IDs；
- 处理 companion-document references；
- 生成 PDF metadata；
- 不使用全文正则替换模拟 Markdown parser。

## Required Validation

- zero missing glyph；
- zero undefined reference；
- zero clipped or overlapping content；
- fonts embedded；
- A4 page size；
- valid metadata；
- clickable TOC/bookmarks；
- content parity；
- PDF preflight；
- PDFium + Poppler rendering；
- visual regression；
- no false PDF/UA claim。

## Accessibility Rule

主发布 Profile 可以使用 `ctex`，但不得声明 PDF/UA-2。

另建 `accessible-experimental` Profile，对 LuaTeX-ja 路径进行验证。只有自动验证和人工抽查全部通过时，才允许写入 PDF/UA-2 conformance metadata。

## Reproducibility Rule

所有工具、LaTeX 包、字体和容器必须固定版本或 digest。构建默认无网络运行。任何升级必须通过单独 PR 更新 lock，并重新执行完整视觉回归。

---

# 最终建议

最佳方案不是“找一个好看的 LaTeX 模板”，而是构建一个小型、受控的**文档出版系统**：

```text
两份权威 Markdown
+
一套共享 LaTeX 设计系统
+
两个文档 Profile
+
AST 级转换
+
固定工具链
+
PDF 结构与视觉门禁
```

最终效果应当表现为：

- 文档 1 有专业标准和技术专著的权威感；
- 文档 2 有工程手册的定位效率和执行感；
- 两者一眼可识别为同一套标准；
- 内容更新不需要手工同步 LaTeX；
- PDF 的每项重要性质都有明确验证；
- 当前中文 LaTeX tagging 的限制被诚实保留，而不是用虚假的合规标签掩盖。

[1]: https://www.tug.org/texlive/?utm_source=chatgpt.com "TeX Live"
[2]: https://pandoc.org/MANUAL.html?utm_source=chatgpt.com "Pandoc User's Guide"
[3]: https://www.latex-project.org/news/2026/03/05/PDFA-press/?utm_source=chatgpt.com "PDF Association's press release: Accessible math in PDF"
[4]: https://ctan.org/pkg/ctex?utm_source=chatgpt.com "ctex: LaTeX classes and packages for Chinese typesetting"
[5]: https://ctan.org/pkg/chinese-jfm?utm_source=chatgpt.com "CTAN: Package ChineseJFM - Comprehensive TeX Archive Network"
[6]: https://ctan.org/pkg/fontspec?utm_source=chatgpt.com "Package fontspec - CTAN"
