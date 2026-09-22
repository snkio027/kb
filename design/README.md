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
| [出版系统设计 · KB-PUB-DESIGN-001 v0.1.0](project/publication-design.md) | 阅读产品、保真/引用/分页合同及分批边界；保持设计提案身份 |
| [B1-A 入口隔离实施记录](project/publication-b1a.md) | 预览输入准备、旧入口关闭及验证边界；不代表 PDF 或发布验收 |
| [可用 PDF 预览实施记录](project/publication-preview.md) | 六篇独立草案与合订工作版、沙箱编译、保真/导航/视觉检查及使用边界 |
| [资产接收登记](project/asset-register.md) | 区分实际可用资产、历史提及但未接收的材料及待核验证据 |
| [审阅闭合记录](reviews/a67fb25-review-status.md) | 保存限定范围的 P1/P2 闭合结论及验证边界，不代替正式批准 |

此前 `KB-WP-01` 的原稿接收与维护稿补齐已通过限定范围复审。原始附件 v0.1.0 作为不可变来源归档，旧维护稿 v0.1.0 由 Git 保存，来源与摘要见 [资产登记 §7](project/asset-register.md)。项目计划仍为 v0.2.0 草案，不改变 ESD/ECD 或出版工具版本，不代表整套路线已采纳。

出版设计已通过限定范围复审，版本仍为 v0.1.0 / DRAFT。后续按完整能力增量交付，不再逐内部步骤审批。当前提供隔离的草案 PDF 预览，并完成阅读完善、保真回归和本地复审候选冻结；六个旧写入入口与正式发布继续关闭，不据此把完整 WP-02 或 P0 标为完成。ECD 源码、报告和原始日志仍待接收。

已有 [Atlas 抽样记录](examples/pilots/README.md) 保留为非规范性示例：两个 mock 契约测试、单评审者初评，不等于完整采用试点或生产验证。本轮不继续推进 Atlas 实施；kb 构建流程与真实 CAN 系统是计划中的候选，尚待确认对象和风险等级。

## 已发布 PDF

- [方法论卷 · v1.1.0](dist/01-优秀系统设计与工程保证方法论-v1.1.0.pdf)
- [工程参考卷 · v1.1.0](dist/02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf)
- [构建清单](dist/build-manifest.json) · [SHA-256 校验和](dist/sha256sums.txt)

以上 PDF 保留 v1.1.0 历史内容，未被本批改写，不是当前 Markdown 草案的同步视图。新版草案预览位于隔离的本地构建目录；后续正式发布需另行授权与验证。

历史发布 PDF 保存在 `dist/`；预览不得写入该目录。两类制品均不声明 PDF/UA 合规；历史字体替代记录见 [fonts.lock](fonts.lock)，新预览记录实际使用的字体与 TeX 输入摘要。

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
| `build/preview/<preparation-id>/<attempt-id>/` | 本地输入快照、准备/PDF 分层终态及 `work/` 中的七份预览、检查与渲染，已忽略 |
| `build/candidate/<candidate-id>/<attempt-id>/` | 复制已检查原字节形成的本地复审候选及清单、终态；不是正式发布，已忽略 |
| `tmp/` | 历史本地渲染预览与缓存，已忽略；旧写入入口已关闭 |

## 构建与检查

> **当前开放完整草案预览及本地候选冻结，不开放正式发布。** 一次调用生成六篇独立 PDF 与一份合订工作版，自动执行内容/结构检查并渲染所有页。候选只复制已检查字节，不重新编译。旧 build、preflight、render、compare 和 manifest 入口仍拒绝执行。

完整预览当前要求 **macOS + sandbox-exec**、Python 3.9+、[pypdf](publication/requirements-preview.txt)、Git、Pandoc、LuaLaTeX 与 Poppler `pdftoppm`。工具须在 PATH 中；TeX Live 需含 ctex、Fandol、Source Serif/Sans/Code 字体及模板所用宏包。缺少依赖或隔离后端时失败，不回退到无沙箱编译。实际验证版本见 [实施记录](project/publication-preview.md)。

如需独立 Python 环境，可自行创建 venv 并安装锁定的检查依赖（不修改系统 Python）：

```sh
python3 -m venv design/build/preview-tools
design/build/preview-tools/bin/python -m pip install -r design/publication/requirements-preview.txt
PDF_PYTHON=design/build/preview-tools/bin/python sh design/scripts/preview.sh
```

已有依赖时，整套构建只需：

```sh
python3 -B design/scripts/pub.py preview
```

命令输出本次目录。七份 PDF 位于 `work/output/pdf/`，入口为 `work/output/README.md`；原文副本在 `work/output/source/`，全页 PNG 在 `work/renders/`。目录中的标识是准备身份；包含实际工具、检查库与 TeX 输入的执行身份另记在 `work/preview-audit.json`。新增文档只需更新 [源目录](publication/source-catalog.json)，标题、ID、版本、状态从源 Front Matter 读取，不维护第二份标题表。

准备当前实际输入，可包含未提交修改；不接受自定义输出路径：

```sh
python3 -B design/scripts/pub.py preview --prepare-only
```

`result.json: PREPARED` 仅表示输入准备完成；只有独立的 `preview-result.json: PREVIEW_READY` 才表示本次七份 PDF 通过实现中的自动检查与渲染。两者都不等于视觉批准、规范批准或正式发布。`.pending`、孤立 PDF、缺失或失败的最终记录不得当作成功。每次尝试独立保留，失败/取消不覆盖旧尝试及历史 `dist/`。准备协议见 [B1-A 记录](project/publication-b1a.md)，完整预览合同见 [本批记录](project/publication-preview.md)。

### 阅读布局与保真

合订版按“文档 → 章节 → 条款”组织书签，前部仅保留六篇入口，条款索引同时提供页码与链接；不改变源编号。比较矩阵与长记录通过 [布局选择](publication/table-layouts.json) 区分。显式选择绑定文档 ID、准确标题、表序及表头；漂移时失败，不猜测相近表。未指定的表仍采用保守默认。

行内代码保留原字符与空格，优先在空格、下划线、斜杠等位置断行；无分隔符的超长 token 才允许 28 字符后的应急断行。标题链与首块共同预留空间。新增检查以真实 PDF 目标限定章节，按源顺序消耗匹配、不得复用重复块；行内字面量不采用正文的去空白或 NFKC 策略。说明页书签/目录目标、文档分组和索引纸面页码也检查实际位置。不把这些检查等同于全页逐字校对或代码块缩进认证。

### 准备集中复审候选

先完成整套预览与阅读自查，再将命令输出中的本次路径换成 **design 相对路径**：

```sh
python3 -B design/scripts/pub.py candidate --from-preview build/preview/<preparation-id>/<attempt-id>
```

仅接受已有 `PREVIEW_READY` 及完整新增检查；摘要、输入、源稿附件或文件集合不匹配时拒绝。输出位于 `build/candidate/<candidate-id>/<attempt-id>/`，包括原字节 `output/`、输入快照、执行/检查记录及 `candidate-manifest.json`。不包含字体、缓存或全页 PNG。工具和字体的实际身份由执行审计绑定，不声称已打包整个运行环境。

如需随候选保留人工自查，在预览尝试根目录提供 `reading-review.json`，至少以 `artifacts` 和 `audit_sha256` 绑定 `preview-result.json` 的同名字段；正文分别写明检查范围、结果及限制，不写成独立批准。缺少此记录会明确登记 `NOT_ATTACHED`，不得推定视觉检查已执行。

只有 `candidate-result.json: CANDIDATE_PREPARED_FOR_REVIEW` 是本地冻结完成事实。它不意味着定稿批准、公开授权或 ESD BASELINE；候选清单始终为 `AWAITING_INDEPENDENT_REVIEW`。每次冻结使用新的尝试目录，不覆盖旧候选。暂存、失败或缺少终态的目录不能当作候选成功；本地文件同步与不覆盖提交不构成断电持久性承诺。`publish` 仍拒绝执行。

运行临时仓库中的隔离测试，不编译或渲染 PDF：

```sh
python3 -B design/scripts/test-publication-isolation.py
```

运行真实编译、沙箱拒绝写入及取消回归（需要完整依赖；全部使用一次性仓库）：

```sh
python3 -B design/scripts/test-preview.py
```

候选目录、失败/取消、输入漂移和提交点回归（不编译 PDF）：

```sh
python3 -B design/scripts/test-candidate.py
```

`content-audit.py` 仍依赖旧编译输出；新预览使用 `preview.py` 内置的源块、表格行关系及 PDF 检查。`pdf-structure-audit.py` 保留为旧只读诊断，本批未以其结果授予资格。仅核对历史文件校验和时，可在 `design/` 中执行 `shasum -a 256 -c dist/sha256sums.txt`，无需重建。

当前限制：仅验证 macOS 单一引擎；不提供可访问性认证、填写表单或正式发布事务。代码自动换行属于阅读视图，复制执行请使用随附的权威 Markdown；ASCII 空间图不静默折行。合订版提供内部跨篇定位，独立版的外部源链接依赖阅读器与网络，未提交源变更则使用随附快照。视觉/阅读自查范围及未验证项分别记录，不把全自动检查通过扩大为全面正确性保证。
