---
document_id: "KB-PUB-PREVIEW-001"
version: "0.1.0"
title: "可用 PDF 预览出版系统实施与验证记录"
status: "IMPLEMENTATION RECORD / NOT RELEASE APPROVAL"
date: "2026-09-21"
base_commit: "5da6c18be530925e942ef70efccc3ab53c77b95b"
---

# 可用 PDF 预览出版系统实施与验证记录

## 1. 本批能力与边界

本批按用户批准的“完整能力增量＋批内自主修复＋集中验收”组织，将身份修正、真实内容试件、六篇独立全文和合订编排及必要检查合并交付。以上位 [出版设计](publication-design.md) 为依据，不再逐补丁申请授权，也不修改设计稿的版本或批准身份。

目标是一次命令产生六篇完整草案 PDF 和一份合订工作版。Markdown 仍是权威内容；六篇业务语义及文件字节、历史 `dist/`、历史归档、计划与上位设计均不改动。只开放本地 PREVIEW，不把 DRAFT 改为 BASELINE，不实现 candidate/publish，不宣告完整 WP-02、KB-P0 或正式规范发布完成。

此前 [B1-A v0.1.1](publication-b1a.md) 是输入准备与 P1/P2 修复的历史记录，保留原始范围。其“普通预览未开放”描述不再代表本批之后的当前能力；准备安全协议与六个旧入口关闭方式继续沿用。

## 2. 实现合同

| 领域 | 当前行为 |
| --- | --- |
| 输入与选择 | `publication/source-catalog.json` 选择源文件；元数据从源读取，生成冻结输入，不从漂移工作树编译 |
| 身份 | 独立版封面、控制页、页眉页脚和 PDF 元数据保留各自 ID、版本、DRAFT；合订版是独立阅读视图，正文进入各篇时切换该篇身份 |
| 标题与引用 | 不重新编号源标题；标题锚点按文档 ID＋原 Pandoc 标识精确映射，不模糊匹配；合订内跨篇跳转，独立版链接固定 commit 源字节或随附未提交快照 |
| 内容编排 | 原标题、段落、列表、条款、代码及表格字段保留；宽/长表转记录时复制原单元格块并保留行列和值关系，空表也保留全部字段 |
| 阅读版式 | A4、11 pt 正文、9.5 pt 矩阵、9 pt 代码；章节不强制独占新页，文档边界另起页；长代码框与字段记录有身份和续页标签，空间流程不折行 |
| 导航 | 每份含目录和 PDF 书签；合订版追加条款定位索引。源正文中的属性表与重复条件不因合订而删除 |
| 构建 | Pandoc → LuaLaTeX 三遍 → pypdf 结构/文本检查 → Poppler 全页渲染；仅使用新的 preview 模板、主题与过滤器，不调用旧写入后端 |

新增或调整源文档不需到处更新硬编码文件名。ID 必须是合法、安全且唯一的标识；重复锚点、缺失链接目标、不支持的跨单元格结构、源 RawBlock/RawInline 或过宽空间图均明确失败，不猜测转换。

## 3. 写入隔离、终态与复核身份

父进程延续 no-follow、目录句柄、排他写入、Git filter/gitlink 执行前拒绝等准备协议。真实编译与渲染的完整子进程树进入 macOS Seatbelt：仅允许写本次 `work/` 和 `/dev/null`，禁止网络，不允许写冻结输入、终态、仓库正文、历史 `dist/` 或其他输出目录。工作进程启动时查询实际策略，确认 work 可写且受保护位置不可写；不支持的系统关闭失败，不降级执行。

TeX 禁用 shell escape；缓存与临时目录位于本次 work。父进程取消时清理独立进程组；父进程遭 SIGKILL 时工作进程的父死亡监视器终止同组后端。失败文件保留诊断，不自动覆盖或删除旧运行。此模型不防同账号恶意修改解释器、脚本或并发替换权限对象，也不是不受信任 TeX 的全面保密沙箱；系统文件仍可读。

| 记录 | 可推出的结论 |
| --- | --- |
| `run.json` / `result.json` | 输入及准备身份，PREPARED 只代表准备，不代表 PDF 成功 |
| `work/preview-audit.json` | 实际执行身份、工具版本/摘要、pypdf 源码身份、实际 TeX 输入/字体摘要及逐制品检查 |
| `preview-result.json` | 仅 PREVIEW_READY 表示 PDF 自动检查及渲染通过；绑定审计文件和七份 PDF 摘要，不代表视觉或发布批准 |
| `.result-*.pending` | 未提交暂存记录；即使内容写着成功也不能被接受为终态 |

两层完成记录均复用“临时文件写入、flush、文件 fsync → 同目录不覆盖 hard link”提交点。提交前失败/取消不得留下已提交成功；提交后通过 inode 见证保留已提交事实，不生成矛盾终态。SIGKILL 前没有终态则视为未完成；不声称提供目录树断电持久性或正式发布事务。

路径中的 preparation-id 仍是完整输入准备身份；不是仅用源 commit，也不冒充已经解析的执行身份。实际执行身份在全部 TeX 输入解析后由准备身份、工具、检查库及实际依赖摘要计算，PDF 摘要另行记录，不回写制品自摘要。基准 commit 与实际输入不混同；独立版只有源字节匹配时才使用该 commit 的链接。

## 4. 自动检查与人工检查边界

| 层次 | 本实现检查 | 不能单独推出 |
| --- | --- | --- |
| 冻结与编排 | 输入摘要；原单元格结构复制；标题命名空间；源 AST、编排 AST 与表格映射留档 | 规范语义或采用条件已获批准 |
| PDF 内容与关系 | 每个源标题、段落、Plain 和代码块的归一化文本；表格逐行及记录字段关联；所有源标题目标实际存在 | 字体字形完全相同、代码复制后的空白字节完全相同 |
| PDF 结构与排版诊断 | 元数据、字体嵌入、内部链接目标、书签；缺字/重复目标/编译错误；超过 2 pt 的行溢出；逐页成功渲染 | 全面视觉验收、所有阅读器兼容性、PDF/UA 认证 |
| 人工阅读自查 | 全页缩略图概览及代表性页面放大，检查封面、身份、目录、长表记录、代码续页、流程与合订边界 | 独立外部评审、每页逐字人工校对或正式发布许可 |

文本核对使用 NFKC、去除空白/软连字符，并明确容许未选中方框的等价形状；不能据此验证代码缩进。提取只排除物理页眉页脚带及精确列举的生成代码/续页标签，源文中的同名标签冲突会失败。完整原文仍随包提供，空间关系、字形及连续页由视觉抽查补充，不把自动文本匹配当作全部保真证明。

## 5. 使用与本次执行记录

命令、依赖安装方式、输出位置和失败判断见 [目录说明](../README.md#构建与检查)。完整预览入口为 `python3 -B design/scripts/pub.py preview`，仅准备则加 `--prepare-only`；便利入口 `sh design/scripts/preview.sh` 接受 `PDF_PYTHON` 指定解释器，不接受任意输出路径。

实际环境：macOS 26.7 / arm64，PDF Python 3.12.14、pypdf 6.10.0、Pandoc 3.11、LuaHBTeX 1.24.0（TeX Live 2026）、Poppler 26.05.0。准备回归另用系统 Python 3.9.6。未安装新系统依赖。最终执行将 PATH 中的 Poppler 指向真实 native 二进制，不只绑定运行时包装脚本。

下表中的 `PREVIEW_PYTHON` 指本机已配置的 bundled Python；`PREVIEW_POPPLER_BIN` 指其 native Poppler bin 目录。它们只是本次命令的路径简称，不是生产入口的配置或绕过开关。

| 实际命令或检查 | 结果与边界 |
| --- | --- |
| `PATH="$PREVIEW_POPPLER_BIN:$PATH" PDF_PYTHON="$PREVIEW_PYTHON" sh design/scripts/preview.sh` | PREVIEW_READY；七份真实 PDF，537 页全部成功渲染 |
| `python3 -B design/scripts/test-publication-isolation.py` | 43 项通过；含 Git filter 拒绝、准备提交点、目录逃逸及旧入口封闭 |
| `"$PREVIEW_PYTHON" -B design/scripts/test-preview.py` | 6 项通过；编排/空表/锚点、PDF 终态 fsync 故障、真实编译失败、真实编译器 SIGINT/SIGTERM/SIGKILL、成功编译时拒绝写临时 dist；测试内全部核对临时历史集合与字节 |
| 源块、表格关系及结构检查 | 七份均无未匹配文本块、无缺失行关系、无缺失源标题目标；567 条源表格行在独立与合订视图分别核对；537 页身份通过，无行溢出诊断 |
| Pandoc `--from=markdown --to=json --fail-if-warnings`、Ruby `YAML.safe_load`、临时本地链接检查 | 两篇变更 Markdown 解析通过；新增记录的 YAML 通过；37 个本地文件链接存在，不声称验证网络目标可用性 |
| `sh -n design/scripts/preview.sh`、Python `ast.parse`、`git diff --check` | Shell/Python 语法与差异空白检查通过 |
| `git ls-tree`＋`git show 5da6c18:<path>` 与工作区逐字节比较 | 原有 72 个受跟踪文件中，除 README、pub.py、原隔离测试这 3 个授权改动外，其余 69 个不变；含六篇核心规范、历史 dist 全部 4 文件、归档和旧出版配置 |
| 在 design 中执行 `shasum -a 256 -c dist/sha256sums.txt` | 两份历史 PDF 校验通过；不重建历史制品 |
| 冻结输入与当前文件摘要复核 | 44 个输入一致；六篇原文均与基准 commit 字节一致，故本次独立版采用固定 commit 源链接 |

最初的真实编译并非一次全绿。批内检查发现并修复了行内代码破折号转换、空表字段遗漏、长标识符/代码溢出、标题目标未准确落到 PDF 锚点、仅含分隔线的页面，以及长记录/代码续页身份问题；失败尝试保留在忽略目录中，不将其改写成通过记录。未运行旧 `content-audit.py`、`pdf-structure-audit.py` 或任一旧构建入口。

### 5.1 最终预览绑定

```text
Base commit     5da6c18be530925e942ef70efccc3ab53c77b95b
Preparation ID  30c6e8c3b554fa896691f5a2b2b20034f4d1880f75e70248ee56b54313cd4b42
Attempt ID      27a5c1bd9ad6468ea06d644c066d8643
Execution ID    6b89174d1bed469a24a37b6f91ce7f7b6fe9d6e072b0ba3f57ea981e44f855ee
Audit SHA-256   f65b5f41ce8558b6a5134eee1e90aa784b8926bf93e7e5f9a4935d870df6fb06
```

根目录为 `design/build/preview/<Preparation ID>/<Attempt ID>/`。七份 PDF 位于 `work/output/pdf/`，源副本与阅读入口位于同级 output 中。完整审计为 `work/preview-audit.json`，最终终态为根目录 `preview-result.json`；记录 260 个实际 TeX 输入文件摘要、工具及检查库身份。源输入包含本批未提交的出版实现，不声称这些 PDF 是基准 commit 自带的历史制品，也不要求把最终制品摘要写回自身。

| 制品文件（均位于本次 output/pdf） | 页数 | SHA-256 |
| --- | --- | --- |
| `ESD-SUITE-000-draft.pdf` | 19 | `29457b90a1c04acc7be716048941a45627d4f56d385dc60f92ac60641082c077` |
| `ESD-METHOD-001-draft.pdf` | 34 | `04bc7e55cc749bb2511f833ff88feefe37abd3eec9c87195a6ac74df3e1b439e` |
| `ESD-REFERENCE-001-draft.pdf` | 65 | `187344ada93863a5596063e5377da06ca86ff78916a49c85e3ec61789607e40c` |
| `ESD-GOV-001-draft.pdf` | 49 | `c18df7914e754575418ff2c117066c730ab030dcb294cec85131721fe8f56c24` |
| `ESD-ASSURANCE-001-draft.pdf` | 48 | `82c942feb423adb1cf8553a400d21d1e0fe8585f58c4b32e7168d1ef00a17957` |
| `ESD-OPS-001-draft.pdf` | 56 | `7a32caf07977db11cead7152c6e65f45757001707ccc40a72117aa0fa22e5730` |
| `ESD-HANDBOOK-draft.pdf` | 266 | `17e9613cbb3caba869f49ea548e519a15119179483498c94139a0d9f6263a117` |

### 5.2 视觉与阅读自查

按 PDF 技能工作流渲染后复核，不只阅读日志：已查看全部 537 页的缩略概览，并放大检查 16 个代表页——SUITE 1/2/10，METHOD 13/14，REFERENCE 47/51，GOV 14/27，ASSURANCE 25/26，以及合订版 1/2/41/172/262。覆盖封面、控制信息、目录、普通矩阵、跨页记录、长代码续页、ASCII 流程、篇章身份切换和生成索引；这些检查中未见明显裁切、重叠、缺字或不可读缩放。

视觉检查先针对同一准备身份的 `a0fa7b79cccd4b259d7d7cde244ac1f6` 尝试完成；最终尝试直接调用相同 Poppler 的 native 二进制。最终全部 537 张 PNG 与已目视检查的对应渲染逐字节一致，故不是将旧版式的检查结果套用到变化页面。PDF 本身因运行元数据可不同，以上摘要只指向最终尝试。

阅读定位抽查包括合订版各篇起始页 26/41/70/129/172/213 及条款索引 262；目标与源标题对应。其余链接进行了 PDF 对象层面的目标存在性检查，不声称在所有阅读器中逐个点击。预览保留在本地忽略目录，通过本次交付附上，不提交到历史 dist，也没有创建正式发布。

## 6. 已知限制与未授权范围

当前是首个可用的 macOS 单引擎草案预览，尚不支持 Linux/Windows 沙箱后端。没有执行候选冻结、正式发布/恢复事务、可访问性认证、打印填写版、任务摘录册或通用缓存/插件系统。未更换六篇正文中的事实或工程约束，也未将现有 mock 抽样升级为完整试点证据。

执行身份记录实际入口、版本、检查库和 TeX 已解析输入，不宣称收集了所有操作系统动态库或提供跨机器逐字节复现保证；运行环境使用包装脚本时，应直接选择实际二进制或另行登记被调用者。本次最终运行已直接选择 native Poppler。

字段记录视图更适合长说明，但不保留宽表的并排比较空间；原始矩阵在随附源文件中。代码的阅读换行不改变字符内容，但从 PDF 复制执行时仍应回到原 Markdown。单件 PDF 脱离随附目录后，未提交源链接可能不可用；跨篇阅读推荐合订版。后续局部审美优化不自动升级为本批阻断项，内容、身份、历史安全及基本可用性问题则在本批内修复。
