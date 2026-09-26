# KB Publication System v2

状态：**READING EDITION / VISUAL PROFILE CANDIDATE**。v2 架构保持稳定；当前批次仅优化阅读层的排版、分页与导航，视觉 profile 尚未冻结，正式 `publish` 关闭。

最新制品、受控密度样张、语义样页及证据见[阅读版集中审核入口](reviews/reading-edition/README.md)。[v2 架构交付记录](reviews/v2-pilot/README.md)作为历史证据保持原字节。两者均不是 release 或可维护的正文源。

## 分层与权威

| 层 | 责任 | 不承担的责任 |
| --- | --- | --- |
| Markdown / Git source | 权威字节、路径、版本与冻结提交 | 不为排版改正文、代码或 Gate |
| `engine/` | 快照、隔离、编译、通用结构与保真检查、渲染、终态、候选 | 不识别 ESD、G6/G7 或某条业务条款 |
| `profiles/<id>/` | 源适配、产品视图、元数据、模板、主题、导航与审计策略 | 不绕过引擎的输入或输出边界 |
| `latex/` | 共享字体和排版机械、代码/表格续页、链接与标题机制 | 不定义产品权威或接受状态 |
| `build/` | 独立尝试、预览、渲染和已检查字节的候选副本 | 不等于发布目录；全部本地忽略 |

产品配置采用 `profile.json`（包含 source catalog 与 views），避免为两个产品引入配置语言或插件发现框架。`adapter.py` 只在受限 worker 中从冻结输入加载；产品模板与 theme 可以覆盖共享默认样式。可信仓库 profile 仍是执行输入，不承诺运行任意不可信 Python 插件。

当前 ESD profile 读取六篇工作树 Markdown 的 Front Matter。C++ profile 固定读取 `8f479deaf660533b2ad82e1f721eb41a363112b6` 下 G6/G7，解析书名式 H1、正文版本与稳定锚点；不把当前 HEAD 当作 C++ 内容版本。没有把 C++ 文件复制到 `design/` 充当新来源。

## 运行

依赖：macOS `sandbox-exec`、Git、Python 3.9+、Pandoc、LuaLaTeX、Poppler `pdftoppm` 和 [pypdf](requirements.txt)。缺少隔离后端时失败，不回退到无沙箱编译。不提供 Linux/CI 或 PDF/UA 保证。

从仓库根目录执行（Python 须已安装依赖）：

```sh
python3 -B publication/engine/pub.py preview --profile esd
python3 -B publication/engine/pub.py preview --profile cpp-handbook

# 仅选择一个逻辑视图；省略 --view 时构建该 profile 的全部视图。
python3 -B publication/engine/pub.py preview --profile cpp-handbook --view G6
python3 -B publication/engine/pub.py preview --profile cpp-handbook --view CPP-PILOT-G6-G7

# 只准备，不编译。
python3 -B publication/engine/pub.py preview --profile cpp-handbook --prepare-only
```

主制品为 ESD 六份独立版与一份合订版，以及 C++ G6、G7 与 G6+G7 三份 PDF。默认构建还包含两份 Compact 对照样张：`ESD-REFERENCE-001-COMPACT` 和 `CPP-PILOT-G6-G7-COMPACT`；两个 profile 合计 12 份。Compact 只改变留白、目录和表格行距，不缩小正文或代码字号。合订版由多源 AST 组成一个逻辑视图后编译，不拼接独立 PDF。

输出路径固定为 `publication/build/preview/<preparation-id>/<attempt-id>/`。`inputs/sources/<repository-path>` 保留嵌套源身份；`work/output/pdf/` 是 PDF，`work/output/source/` 为同路径原始源码，`work/renders/<view>/` 为所有页面 PNG。本次尝试入口为 `work/output/README.md`。

## 身份与链接

准备身份绑定 Git 实现上下文、Python 身份、源 revision/path/bytes、profile、视图选择及引擎/LaTeX 输入。实际执行身份另外绑定准备 ID、工具可执行文件与版本、pypdf 文件及 `.fls` 所列 TeX/字体依赖。制品摘要由预览终态绑定；准备 ID 单独不是完整工具链执行身份。

源与实现可能来自不同提交：C++ 内容固定于 `8f479de`，引擎来自后续实现或明确记录的工作树输入。运行期间读取的是输入副本，profile/renderer 或 WORKTREE 源在准备后漂移会拒绝成功；固定 Git 源不因工作树或 HEAD 漂移切换 revision。

同视图引用变成内部 destination；独立版到其他文档按策略链接到固定仓库源或随附源副本。视图外的仓库链接核对固定提交下的文件/锚点，无法解析时失败；已有网页 URL 保持外链，不把联网可达性当作本轮通过项。C++ 原始 HTML anchor 作为 PDF destination alias 保留，实验注释明确登记为非打印语义对象；未知 raw markup 不静默删除。生成目的地、别名、源路径和链接分类均有审计记录。

## 终态与候选

`result.json: PREPARED` 仅是输入准备；`preview-result.json: PREVIEW_READY` 才表示本次所有声明视图完成自动检查和全页渲染。两者均不是视觉批准、内容重新验收或发布批准。失败、取消、缺少终态或 `.pending` 文件不等于成功；提交点之后保留已提交事实，不生成矛盾终态。

候选只复制已检查原字节，不重新编译：

```sh
python3 -B publication/engine/pub.py candidate --profile cpp-handbook \
  --from-preview publication/build/preview/<preparation-id>/<attempt-id>
```

输出为 `publication/build/candidate/<candidate-id>/<attempt-id>/`；只有 `CANDIDATE_PREPARED_FOR_REVIEW` 表示本地冻结完成。候选仍为 `AWAITING_INDEPENDENT_REVIEW`。其身份保留源 revision/path、视图集合、准备/执行身份和制品摘要，而非通过 basename 找源文件。

可在预览尝试根目录附 `reading-review.json`，用 `artifacts` 与 `audit_sha256` 绑定该次终态，分别记录查看页、观察与未检查项。缺失时记为 `NOT_ATTACHED`，不推定人工检查已经执行。全部流程不写历史 `design/dist/`；本地提交协议不声称断电后的目录树持久性。

## 迁移与验证

原 `design/scripts/pub.py preview` 只转发至 v2 的 ESD profile；旧内部 worker 不再运行。旧六个危险写入入口继续拒绝，正式发布关闭。原 `design/build/` 预览和候选不移动、不重写；v1 记录不自动升级为 v2 合格记录，新候选入口只接收 v2 路径。历史工具可在精确 Git 版本中查阅，不保留第二套可漂移的活动构建器。

```sh
python3 -B publication/tests/test-publication-isolation.py
python3 -B publication/tests/test-candidate.py
python3 -B publication/tests/test-products.py
python3 -B publication/tests/test-preview.py
python3 -B publication/tests/test-reading.py
```

前三组在一次性仓库检查隔离、终态、候选、revision/profile/adapter 契约；第四组真实编译并注入失败、错位、字面量丢失和信号；第五组检查阅读组件、代码头尾反例、Gate 分组和密度比较。旧测试命令转发至迁移后的套件。实际全量产品输出、检查命令与限制见本轮交付记录；测试夹具通过不替代真实 ESD/C++ 构建。

自动提取采用有界的文本、顺序、行内字面量、表格关系和定位检查，不声称逐字形、代码缩进、所有视觉缺陷或可访问性认证。人工阅读必须查看实际渲染，且单独注明范围。视觉定稿、全 G0～G12 构建与正式发布不在本批。

可选视觉辅助命令为 `python3 -B publication/tools/inspect-pages.py <preview-attempt>`，另需 Pillow；它只从已绑定的渲染生成 contact sheets，不自动授予人工阅读通过状态。

阅读回归使用[语义样本目录](tools/reading-corpus.json)，不把物理页码作为样本身份：

```sh
python3 -B publication/tools/reading-review.py <completed-preview-attempt>
python3 -B publication/tools/reading-review.py --density-compare <page-map.json>
python3 -B publication/tools/reading-review.py --compare <old-page-map.json> <new-page-map.json>
```

第一条从绑定的 PDF 生成 `work/reading-regression/`（新目录，拒绝覆盖），输出语义目标、物理页、120 dpi PNG 和摘要。后两条只读比较相同语义目标，不把像素不同判为失败。`STRUCTURAL_PASS` 表示所定义的阅读信号未触发；实际查看图片另记 `VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL`。规则、已知限制及定稿决策见[视觉 Profile 候选](reviews/reading-edition/visual-profile.md)。
