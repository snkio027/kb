# 系统设计与工程保证

本目录收录《优秀系统设计与工程保证标准》及其 PDF 出版工具。Markdown 是权威内容来源；文档关系以 [00 文档体系与规范关系](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md) 为准。

## 文档导航

| 编号 | 文档 | 阅读用途 |
| --- | --- | --- |
| 00 | [文档体系与规范关系](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md) | 规范地图、权威边界与阅读路径 |
| 01 | [优秀系统设计与工程保证方法论](01-优秀系统设计与工程保证方法论-v1.1.0.md) | 原则、术语、认识边界与架构推导 |
| 02 | [优秀系统设计：从约束、不变量到证据](02-优秀系统设计-从约束不变量到证据-v1.1.0.md) | Stage/Gate、模板、评审与工程案例 |
| 03 | [治理及符合性规范](03-系统设计与工程保证治理及符合性规范-v1.0.0.md) | 风险分级、角色、例外与符合性 |
| 04 | [论证、证据与裁决规范](04-工程保证论证证据与裁决规范-v1.0.0.md) | 保证论证、证据质量与裁决 |
| 05 | [生产就绪与运行韧性标准](05-生产就绪与运行韧性标准-v1.0.0.md) | SLO、发布、恢复与持续韧性 |

## 当前文档修订

六篇 Markdown 为 `2.0.0-draft.1`。本轮跟踪的文档缺陷已在限定复审范围内关闭，见 [a67fb25 审阅记录](reviews/a67fb25-review-status.md)；这不等于整套批准或实践验证，六篇仍为未获发布批准的草案，尚未完成 R1/R2 采用试点。旧文件名暂作稳定入口，版本以正文元数据为准。批准、校准与试运行状态见 [00 §13](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md)。

## 项目建设入口

当前主任务是完善工程文档体系的可采用性，不继续增加宏观规范，也不以项目实施代替文档建设。

| 入口 | 用途 |
| --- | --- |
| [项目计划 · KB-PLAN-001 v0.2.0](project/plan.md) | 唯一当前维护入口；补齐阶段、工作包及验收边界，仍为 `DRAFT / PROPOSED PLAN` |
| [资产接收登记](project/asset-register.md) | 区分实际可用资产、历史提及但未接收的材料及待核验证据 |
| [审阅闭合记录](reviews/a67fb25-review-status.md) | 保存限定范围的 P1/P2 闭合结论及验证边界，不代替正式批准 |

首次 `KB-WP-01` 收口材料已入库；本次仅接收原始规划并补齐维护稿。原始附件 v0.1.0 作为不可变来源归档，旧维护稿 v0.1.0 由 Git 保存，来源与摘要见 [资产登记 §7](project/asset-register.md)。仅项目计划升为 v0.2.0，不改变 ESD/ECD 或出版工具版本，不代表整套路线已采纳。

`KB-WP-02` 预览与发布隔离尚未实施，完整 PDF 构建系统重设计另列待决，不把整个 P0 标为完成。本次检查、提交及推送后停止，不启动任何后续工作包；ECD 源码、报告和原始日志仍待接收。

已有 [Atlas 抽样记录](examples/pilots/README.md) 保留为非规范性示例：两个 mock 契约测试、单评审者初评，不等于完整采用试点或生产验证。本轮不继续推进 Atlas 实施；kb 构建流程与真实 CAN 系统是计划中的候选，尚待确认对象和风险等级。

## 已发布 PDF

- [方法论卷 · v1.1.0](dist/01-优秀系统设计与工程保证方法论-v1.1.0.pdf)
- [工程参考卷 · v1.1.0](dist/02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf)
- [构建清单](dist/build-manifest.json) · [SHA-256 校验和](dist/sha256sums.txt)

本轮不修改 PDF。以下 PDF 保留 v1.1.0 历史内容，不是当前 Markdown 草案的同步视图；后续正式发布需另行构建与验证。

PDF 统一保存在 `dist/`。发布版本不声明 PDF/UA 合规；字体替代记录见 [fonts.lock](fonts.lock)。

## 目录约定

| 路径 | 用途 |
| --- | --- |
| `00-…md` 至 `05-…md` | 权威文档 |
| [project/](project/) | 非规范性项目计划与资产接收事实 |
| [reviews/](reviews/) | 范围明确的审阅记录，不自动授予发布批准 |
| [examples/pilots/](examples/pilots/) | 非规范性项目试点记录与原始执行证据 |
| [to-pdf.md](to-pdf.md) | PDF 出版设计与实现约束 |
| [publication/](publication/) | LaTeX 模板、主题、过滤器、图表与配置 |
| [scripts/](scripts/) | 构建、预检、渲染与比较工具 |
| [dist/](dist/) | 唯一受版本控制的 PDF 发布目录 |
| `build/` | 本地编译中间产物，可重新生成，已忽略 |
| `tmp/` | 本地渲染预览与缓存，可重新生成，已忽略 |

## 构建与检查

> **当前入口尚未完成发布隔离。** `scripts/build.sh` 会把当前 Markdown 编译结果复制到历史 `dist/*-v1.1.0.pdf` 路径，并更新校验和及清单。当前正文已是新草案，因此不要将下列历史流程当作普通预览命令执行。`KB-WP-02` 将单独修复该边界；本轮不运行构建、不修改 PDF 或构建行为。

依赖 Pandoc、TeX Live / LuaLaTeX、latexmk、Poppler、Python 3，以及预检使用的 ripgrep 和 Perl。Python 检查与渲染依赖 `pypdf`、`pypdfium2`、Pillow；已验证的版本见 [package-lock.txt](package-lock.txt)、[texlive.profile](texlive.profile) 与 [fonts.lock](fonts.lock)。

以下保留现有出版流程供维护核对，**不是本轮执行步骤**：

```sh
bash design/scripts/build.sh
bash design/scripts/preflight.sh
bash design/scripts/render-verify.sh
```

现有预检依赖构建生成的 LaTeX 和日志；不要为运行预检而重建历史 dist。`KB-WP-02` 将一并核对入口与检查对象。现有渲染结果位于 `design/tmp/pdfs/`，用于人工检查版面；检查依赖安装在独立 Python 环境中时，可通过 `PYTHON_BIN` 指定其解释器路径。

比较两个版本的页面：

```sh
bash design/scripts/compare-renders.sh path/to/old.pdf path/to/new.pdf
```

比较发现差异时返回非零退出码，并列出有变化的页码。仅验证已发布文件的校验和时，在 `design/` 中执行 `sha256sum -c dist/sha256sums.txt`。
