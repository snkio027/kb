---
document_id: "KB-PUB-PREVIEW-001"
version: "0.2.0"
title: "可用 PDF 预览出版系统实施与验证记录"
status: "IMPLEMENTATION RECORD / NOT RELEASE APPROVAL"
date: "2026-09-22"
base_commit: "6b73bc89a177cd36dea2bb4e718e946026878bcc"
---

# 可用 PDF 预览出版系统实施与验证记录

## 1. 本批能力与边界

本批交付“阅读定稿化＋保真回归＋发布候选准备”，依据 [出版设计](publication-design.md) 和实际制品复审，在同一批内修复机制、检查七份真实 PDF，并冻结同一组已检查字节供集中复审。没有再扩写上位方案。

Markdown 仍是权威内容。六篇正文、版本 `2.0.0-draft.1`、历史 `dist/`、历史归档、项目计划和上位设计均未改变。合订版 `preview.2` 只标识生成阅读视图，不提升规范状态。正式发布入口仍关闭；候选准备不等于定稿、公开授权、ESD BASELINE 或完整 WP-02 / KB-P0 验收。

本记录 v0.1.0 及上一组 537 页 PDF 的实施身份保留在精确提交 `6b73bc89a177cd36dea2bb4e718e946026878bcc` 的本路径和既有本地构建目录中；旧制品及旧复审 ZIP 均未覆盖。此前 [B1-A](publication-b1a.md) 是历史准备安全切片的记录，其旧能力限制不代表当前入口状态。

## 2. 阅读修正与实现合同

| 领域 | 当前行为及本批变化 |
| --- | --- |
| 输入与身份 | 源目录选择文件；标题、ID、版本和 DRAFT 状态从原 Front Matter 读取，编译冻结输入；独立版与合订内各篇保留自己的身份 |
| 行内字面量 | 移除会吞空格的 seqsplit；输出实际空格字符，保留字符与连续空格；优先在空格、下划线、斜杠等受控位置断行，无分隔符长 token 才采用 28 字符后的应急断行 |
| 前言导航 | 标题、书签、目录文字链接共用明确的 `generated-preface`；核对目标区域以“阅读与版本说明”开头，不只检查目标存在 |
| 标题保持 | 对连续标题链按实际字体、行宽测量并统一预留首段空间；不强制每章另页，不靠缩字号或负间距修补；真实 PDF 检查首个有意义内容的位置 |
| 合订导航 | 保留源文可见编号；书签按文档→章节→条款分组；第 2 页组成信息为六条链接，第 3 页为简短目录，正文从第 4 页开始 |
| 条款索引 | 160 个条目同时提供链接和最终纸面页码；无条款的文档不生成空索引分组；页码逐项对照实际目标 |
| 比较与长记录 | 14 项显式布局选择（13 项矩阵、1 项记录）绑定文档 ID、准确标题、表序和表头；RACI、风险等级、状态及方案比较保留横向关系，长对象说明继续采用记录；漂移或未消费的选择失败 |
| 表格跨页 | 重复表头；续页尾与末页尾保持等高，末行不脱离数据单独产生表头/横线页；字段与所属记录不变 |
| 引用 | 先区分 URI scheme/host，再解析精确相对路径；外部同名 Markdown 不改成内部跳转；非核心相对链接保留 fragment；跨出仓库的相对路径拒绝 |
| 构建 | Pandoc → LuaLaTeX 三遍 → PDF 检查 → Poppler 全页渲染；仍采用 A4、11 pt 正文及既有字体配色，没有另起多引擎框架 |

布局配置见 [table-layouts.json](../publication/table-layouts.json)。关键比较件现在分别位于 GOV 第 12 页（RACI）、第 14 页（风险制品矩阵）、第 19 页（对象级状态），以及 ASSURANCE 第 30 页、OPS 第 45 页。页数减少来自导航和布局选择，不是删除规范条件或压缩正文字号。

## 3. 隔离、完成记录与候选边界

父进程继续采用 no-follow、目录句柄、排他创建和 Git filter/gitlink 执行前拒绝。真实编译及渲染子进程树进入 macOS Seatbelt：仅允许写本次 `work/` 和 `/dev/null`，禁止网络及对冻结输入、终态、正文和历史制品写入；不支持隔离后端时关闭失败，不降级执行。TeX 禁用 shell escape，缓存和临时目录在 work 内。

取消时清理进程组；父进程 SIGKILL 后由父死亡监视器终止后端。此模型不防同账号恶意修改解释器或并发替换权限对象，也不是不受信任 TeX 的全面保密沙箱；系统文件仍可读。

| 记录 | 含义与边界 |
| --- | --- |
| `run.json` / `result.json` | 实际输入与 PREPARED；不是 PDF 成功 |
| `work/preview-audit.json` | 执行身份、实际工具与 TeX/字体摘要、逐制品检查 |
| `preview-result.json` | PREVIEW_READY 绑定审计与七份 PDF 摘要；不是视觉或发布批准 |
| `reading-review.json` | 执行方阅读自查，按同一审计及制品摘要绑定；不是独立评审 |
| `candidate-manifest.json` | 已检查字节、冻结输入、执行记录和自查的文件集合；始终 AWAITING_INDEPENDENT_REVIEW |
| `candidate-result.json` | CANDIDATE_PREPARED_FOR_REVIEW 仅为本地候选冻结完成事实 |
| `.result-*.pending` | 未提交暂存；即使内容写成功也不能接受为终态 |

完成记录均采用临时写入、flush、文件 fsync 后，以同目录不覆盖 hard link 提交。提交前失败或取消不留下已提交成功；提交后依据 inode 见证保留既成事实，不再制造矛盾终态。没有终态的 SIGKILL 尝试视为未完成。这里不承诺目录树断电持久性，不是正式发布事务。

候选入口只读取指定的既有 PREVIEW_READY，校验准备/执行/审计身份、检查字段、PDF 文件集合、摘要、全部冻结输入及随附源稿，不调用编译器。复制前后复核源字节，逐项复核目标字节；使用新的候选 attempt，不覆盖旧尝试。候选包括 output、inputs、日志、AST、排版输入和检查记录，不包含字体、缓存或全页 PNG；工具/字体按执行身份绑定，不声称打包了整个操作环境。

候选清单是可校验的内容快照，不是签名、防篡改存储或批准记录；后续使用仍须重算摘要。发布入口保持关闭，不能通过候选冻结绕过发布批准。

## 4. 保真检查与阅读自查的边界

| 层次 | 实际检查 | 不能单独推出 |
| --- | --- | --- |
| 输入与编排 | 输入摘要、原单元格块复制、标题命名空间、源 AST/编排 AST/表格映射留档 | 规范正确性或采用批准 |
| 章节归属与顺序 | 源标题对应的 PDF 坐标限定区段，按源顺序消费匹配，每个命中不复用；重复样本登记期望和可用次数；表格行关系在所属区段核对 | 任意多余内容都被排除，或全局精确重复次数已证明 |
| 行内字面量 | 独立于正文策略，逐字符及空格核对，不做 NFKC 或去空白；只容许源空格和受控断行位置的提取换行 | 所有阅读器复制字节、跨行连续空格宽度或代码块缩进认证 |
| 结构与定位 | 元数据、字体嵌入、源目标、书签归属、前言真实区域、索引页码、标题与首块同页；缺字、重复目标及超过 2 pt 溢出拒绝 | 全面视觉验收、所有阅读器兼容或 PDF/UA |
| 阅读自查 | 全页缩略概览、28 页放大检查、关键规则/索引/模板定位阅读 | 484 页逐字人工校对、独立复审或发布许可 |

普通正文仍使用 NFKC 和去空白等归一化规则；不能将它用于证明代码字面量空格正确。多行代码保留源字节供排版，并进行区段文本匹配、续页身份与视觉抽查，但从 PDF 复制执行应回到随附 Markdown。字段和空间图的视觉关系由抽查补充，自动匹配不是全部保真证明。

## 5. 实际执行与检查

使用命令和依赖见 [目录说明](../README.md#构建与检查)。本机环境为 macOS 26.7 / arm64；PDF Python 3.12.14、pypdf 6.10.0、Pandoc 3.11、LuaHBTeX 1.24.0（TeX Live 2026）、Poppler 26.05.0；隔离与候选测试另用系统 Python 3.9.6。未安装新系统依赖。

以下 `PREVIEW_PYTHON` 为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`；`PREVIEW_POPPLER_BIN` 为同 dependencies 下的 `native/poppler/bin`。这些是实际命令路径的简称，不是绕过隔离的开关。

| 实际命令或检查 | 结果与范围 |
| --- | --- |
| `PATH="$PREVIEW_POPPLER_BIN:$PATH" PDF_PYTHON="$PREVIEW_PYTHON" sh design/scripts/preview.sh` | PREVIEW_READY；七份真实 PDF，共 484 页全部渲染 |
| `python3 -B design/scripts/test-publication-isolation.py` | 43 项通过：Git filter 拒绝、准备提交点、目录逃逸、旧入口封闭等 |
| `"$PREVIEW_PYTHON" -B design/scripts/test-preview.py` | 12 项通过：真实成功/编译失败/SIGINT/SIGTERM/SIGKILL、临时 dist 写入拒绝、行内空格删除与前言错链负例、标题/矩阵/URI/区段重复顺序、PDF 终态 fsync、真实 PDF 候选冻结及后续源漂移拒绝 |
| `python3 -B design/scripts/test-candidate.py` | 8 项通过：源/目标目录链接、路径限制、重复独立尝试、复制漂移、取消、终态同步失败、提交后异常；未编译 PDF |
| 全文内容与关系检查 | 1,478 个源标题区段、7,492 个有序单元、988 个行内字面量，均含独立和合订两个视图；错误列表为空；无 overfull hbox；160 个索引页码对应 |
| `python3 -B design/scripts/pub.py candidate --from-preview build/preview/<本次准备 ID>/<本次 attempt>` | CANDIDATE_PREPARED_FOR_REVIEW；未重新编译，复制 215 个载荷文件 |
| 临时候选打包检查器 | 清单内全部字节数/摘要、候选 ID、终态绑定通过；ZIP 217 文件含清单和终态，CRC 与逐项解包字节核对通过 |
| `git ls-tree -rz --name-only 6b73bc8`＋逐项 `git show <完整 Base>:<path>` 比较 | Base 的 81 个受跟踪文件中，排除 8 个授权修改，其余 73 个字节不变；包括六篇正文和 dist 全部 4 文件 |
| 在 design 中执行 `shasum -a 256 -c dist/sha256sums.txt` | 两份历史 PDF 均 OK；未调用旧构建入口 |
| 冻结输入与当前文件/源 commit 核对 | 48 个输入摘要一致；六篇源副本与 Base 精确字节一致，故源链接使用固定 Base commit |
| Pandoc `--from=markdown --to=json --fail-if-warnings`、Ruby `YAML.safe_load`、临时本地链接检查 | 两篇修改 Markdown 及本记录 YAML 通过；39 个本地文件/目录链接存在，未验证网络或 fragment 目标 |
| Python `ast.parse`、布局 JSON 解析、`git diff --check` | 6 个修改/新增 Python 文件、布局配置及差异空白检查通过；未把未运行的旧检查登记为 PASS |

63 项回归均在一次性仓库中执行，成功、失败及取消路径核对临时历史文件集合与字节，不操作真实历史 PDF。初次受外层工具沙箱限制的编译返回 sandbox_apply 错误，未记为通过；获准运行项目自身 Seatbelt 后完成真实检查。批内还修复了 Unicode 字面量、矩阵溢出及表尾空延续页等失败，失败尝试保留，不改写为成功。未运行旧 content-audit、pdf-structure-audit 或正式发布入口。

### 5.1 最终预览与候选绑定

```text
Base commit     6b73bc89a177cd36dea2bb4e718e946026878bcc
Preparation ID  7c055e489bef5db31ed3a8a2a8da52475203d3969c8ed66ae56cfbc220842ba1
Preview attempt 89e22066ef97499bba087123a7d49fb0
Execution ID    64839efe9d644cd33c5009d8739de780423f81fae8f18e635c94e0cd07085bf0
Audit SHA-256   2eb5a2efd757b4d6ada8e4f403389bc85215af810155f3d5bb9c47efdfd083f5
Candidate ID    dba16b9050b5139bd41df83e3fab558c3299ba74cbdea042e7622622aefbdeb9
Candidate try   7928b345ba7f4534b98ee54498e61232
Manifest SHA256 ebc507d3f51b448bd30b11492595ec57580b443f7f2fdf1cb3e7a70051606181
```

预览根为 `design/build/preview/<Preparation ID>/<Preview attempt>/`；候选根为 `design/build/candidate/<Candidate ID>/<Candidate try>/`。PDF 原件位于前者 `work/output/pdf/`，逐字节副本位于后者 `output/pdf/`。审计记录 259 个实际 TeX 输入文件摘要。

本次源输入包含 Base 上未提交的出版实现，不声称 PDF 由干净 Base 编译。冻结输入、执行身份及最终制品摘要分别绑定，不能用随后提交的 HEAD 替换原始构建上下文。实施说明与本记录更新不参与 PDF 编译输入。

| 制品文件 | 页数 | SHA-256 |
| --- | --- | --- |
| `ESD-SUITE-000-draft.pdf` | 18 | `bffa6fa86cfaffc61fbb6743e0600f866ea8616ac425b70c593a07eca1782e41` |
| `ESD-METHOD-001-draft.pdf` | 32 | `fcd54743affa57f2bf57a07c8c7871f9163dfeca697b955bcdbfdb2436b80fe0` |
| `ESD-REFERENCE-001-draft.pdf` | 63 | `c0b4968eabfe61a4b68367bf1776ff97b6748a3bfd03db3019da46e340f91675` |
| `ESD-GOV-001-draft.pdf` | 42 | `2d42f42c7aef10b047d17b59f3abe38e01ff9b5959d55e55e3d294e5d6b4b6e6` |
| `ESD-ASSURANCE-001-draft.pdf` | 44 | `125e785e6374c25a7bfba582057d06639b820ab7e64d783060d6bfdb1e37f500` |
| `ESD-OPS-001-draft.pdf` | 50 | `29f291695792f4e1c2860c149bd3cd6bfb33c484726caecd35b9b475ab386287` |
| `ESD-HANDBOOK-draft.pdf` | 235 | `7f5f9c78489538f0136356d3b4926b851576e44062a8c97b3cd543c5d655e7de` |

复审 ZIP 为 `design/build/review-packages/kb-reading-candidate-dba16b9050b5.zip`，7,905,763 字节，SHA-256 为 `3d2b82e52305181446b0014ddbb5a5eba08ef32b13f909568ac4016724ef54ed`。它包含候选 215 个载荷及清单、终态共 217 个文件；并非正式发布包，不提交到历史 dist。

### 5.2 最终字节的视觉与阅读自查

按照 PDF 技能的渲染后复核流程，查看最终 484 页的 25 张缩略总览，并以 160 dpi 放大查看下列 28 页；不是只看构建日志，也不是把旧 PDF 的视觉结论套到新字节。

| 视图 | 放大查看页 |
| --- | --- |
| SUITE | 2、12、15 |
| METHOD | 14、18、20 |
| REFERENCE | 49、51、52、53 |
| GOV | 11、12、14、19、33 |
| ASSURANCE | 30、31 |
| OPS | 17、30、45 |
| HANDBOOK | 2、3、95、96、121、170、231、234 |

这些页面中未见明显裁切、重叠、缺字或不可读缩放；已看到角色名、delivery 短语和 Recovery Capacity 的空格，状态值在下划线处续行，关键矩阵保留可比较列。标题链及后续正文没有再出现所报页尾分离。总览只覆盖宏观排版，不冒充每页逐字阅读。

阅读路径采用 PDF 对象导航＋页面图像/提取文本阅读，不是人工阅读器 UI 点击测试，也未测量点击数或任务耗时：

| 任务 | 实际路径与观察 |
| --- | --- |
| 区分例外、Claim 与符合性 | 合订书签 → ASSURANCE §19.1（170）与 GOV §10.1/10.2（121）；例外不增加事实支持，各维状态边界与有序规则可读 |
| 通过索引找共享重试预算 | 合订 234 页 OPS-REQ-023 索引标 197；实际链接指向 197，读取八项预算字段及无限/统一重试禁止项；独立版对应 17 页 |
| 未知结果与前缀推进 | REFERENCE 分组 → §16.11.2/16.11.3，合订 95/96，独立 52/53；超时、责任、GC、100/101/102 及 epoch 条件可连续阅读 |
| 找到模板与对应源字节 | REFERENCE §13.1 书签 → 合订 70 页；Decision Brief 与 Design Dossier 区别保留；随附六篇源稿均与固定 Base 字节一致，未验证远端网页可用性 |

完整自查保存在候选 `reading-review.json`，绑定上述审计与七份 PDF 摘要。候选还保留逐视图 section-audit.json，供复审者检查具体区段、计数和页码；自查不是独立复审结论。

## 6. 已知限制与停止边界

当前仅验证 macOS 单引擎，不包括 Linux/Windows、PDF/UA、打印填写版、网站、任务摘录册、通用缓存/插件系统、正式发布/恢复事务。字体与工具按实际摘要登记，但没有收集所有系统动态库或承诺跨机器逐字节复现。

普通正文的有序归一化匹配与行内字面量检查有各自边界，不能替代全文语义审阅。长记录保留对象关系，但不保证每张表都最适合每类任务；剩余局部审美选择不自动阻断本批。

本批止于可阅读七件、候选冻结、检查记录与提交供审。不提升 DRAFT，不执行 publish，不将现有 mock 抽样解释成项目采用或生产批准。正式公开 DRAFT 阅读件与批准规范基线仍须分别确定授权及验收。
