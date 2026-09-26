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

## 目录与当前构建入口

出版实现已迁移到仓库级 [KB Publication System v2](../publication/README.md)，本轮为 **IMPLEMENTED / REVIEW CANDIDATE**。六篇 Markdown 和历史 `dist/` 不变；ESD 是共享引擎的一种 profile，不再充当整个仓库的隐式出版根。

| 路径 | 当前作用 |
| --- | --- |
| `00-…md` 至 `05-…md` | ESD 权威内容，未改业务语义 |
| [project/](project/) / [reviews/](reviews/) / [examples/](examples/) | 既有项目、复审和试点记录 |
| [dist/](dist/) | 不可覆盖的历史发布制品 |
| [../publication/engine/](../publication/engine/) | v2 准备、编译、审计、渲染与候选 |
| [../publication/profiles/esd/](../publication/profiles/esd/) | 当前 ESD catalog、适配、模板和主题 |
| [publication/](publication/) | v1 出版资产保留；不再作为活动配置入口 |
| [scripts/](scripts/) | 公共命令兼容转发、旧只读工具及关闭的危险入口 |
| `build/` | 原 v1 本地运行记录，原样保留，不自动转换 |
| `../publication/build/` | 当前 v2 预览和候选尝试，Git 忽略 |

## 构建与检查

依赖、输入与执行身份、输出、候选及限制统一以 [v2 使用说明](../publication/README.md)为准。macOS `sandbox-exec` 仍是必需隔离后端，没有无沙箱回退。一次命令生成六份独立预览和一份合订版：

```sh
python3 -B publication/engine/pub.py preview --profile esd
```

兼容命令 `python3 -B design/scripts/pub.py preview` 转发到同一引擎，不保留第二套实现。新增 ESD 源和产品配置在 [ESD profile](../publication/profiles/esd/profile.json)维护；标题、版本和内容状态仍由 Front Matter 校验。正式 publish 及旧六个危险写入入口继续关闭。

新运行位于 `publication/build/preview/<preparation-id>/<attempt-id>/`，PDF 在 `work/output/pdf/`，完整原文在 `work/output/source/design/`，全页 PNG 在 `work/renders/`。输入和 profile 均冻结，`PREVIEW_READY` 不等于视觉、规范或发布批准。

候选从已检查的新预览复制原字节，使用仓库相对路径：

```sh
python3 -B publication/engine/pub.py candidate --profile esd \
  --from-preview publication/build/preview/<preparation-id>/<attempt-id>
```

旧 `design/build/` 的预览与候选不重写、不迁移，也不被当前入口冒充 v2 验收记录。v1 的历史执行方法见 Git 中的旧版本和[历史实施记录](project/publication-preview.md)；本轮不追写这些历史记录。

旧测试命令仍可使用，实际执行迁移后的 v2 套件：

```sh
python3 -B design/scripts/test-publication-isolation.py
python3 -B design/scripts/test-candidate.py
python3 -B design/scripts/test-preview.py
python3 -B publication/tests/test-products.py
```

历史 `content-audit.py`、`pdf-structure-audit.py` 仅供旧输出诊断，不授予当前资格。核对历史校验和可在 `design/` 内运行 `shasum -a 256 -c dist/sha256sums.txt`，无需重建。

本轮不开放正式发布、不替换历史 PDF，也不宣称 PDF/UA、跨平台或完整视觉定稿。内容接受状态、预览自动检查和人工阅读记录分别保留。
