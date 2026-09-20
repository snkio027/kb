---
document_id: "KB-PUB-B1A-001"
version: "0.1.1"
title: "B1-A 出版入口隔离实施合同与验证记录"
status: "IMPLEMENTATION RECORD / NOT RELEASE APPROVAL"
date: "2026-09-21"
base_commit: "c827efcd918bd36c11efb84ee0671b0f2f936fcf"
revision_base: "61cd8ba8c3455ab57c6b6c9f612a4ef5a50e363c"
---

# B1-A 出版入口隔离实施合同与验证记录

## 1. 授权与修改范围

初始实施依据出版设计复审后的独立授权，落实 [设计 §10](publication-design.md) 的 B1-A 安全切片。下表保留 61cd8ba 的初始修改范围；本次 v0.1.1 仅修正 `pub.py`、对应测试和本文，处置复审发现的 P1/P2，检查、提交、推送后停止。设计稿 v0.1.0、计划 v0.2.0、六篇规范、历史来源、PDF、出版模板/配置、字体锁及六个已关闭的旧入口均不改动；不启动 B1-B、B2 或正式发布。

| 文件范围 | 本轮处理 |
| --- | --- |
| `scripts/pub.py` | 新增预览输入准备入口、有效输入身份、封闭输出路径及执行记录 |
| `scripts/test-publication-isolation.py` | 新增临时仓库中的隔离与失败场景测试 |
| `scripts/build.sh`、`preflight.sh`、`render-verify.sh` | 旧入口直接拒绝，无安全转发、无写入或第三方工具执行 |
| `scripts/write-manifest.py`、`render-pdfium.py`、`compare-renders.sh` | 关闭直接清单/渲染旁路，拒绝任意输出位置 |
| 本文及 `design/README.md` | 记录实施合同、命令、实际验证和未覆盖边界 |

`content-audit.py` 与 `pdf-structure-audit.py` 是只读诊断入口，本轮不修改或执行；前者仍依赖旧编译输出，不能作为新预览的验收入口。未增加候选或发布实现，也不宣告整个 WP-02 或 KB-P0 完成。

## 2. 操作与身份合同

本批只开放 `python3 design/scripts/pub.py preview --prepare-only`，产物是输入快照和 JSON 记录，**不是 PDF 预览**。普通 `preview`、`build`、`check`、`render`、`candidate` 和 `publish` 均非零退出且不写文件。六个旧入口也直接拒绝全部调用方式，包括带旧参数的调用。

暂不运行 Pandoc、TeX、字体探测或 PDF 工具。这样在 B1-B 身份渲染尚未修正时，不会产生误标“基线”的新阅读件。B1-B 之后重新开放编译/渲染，需要补充真实子进程的写入约束及失败/取消验证；本批准备成功不能替代该验收。

### 2.1 输入集合与构建标识

准备入口读取六篇 Markdown、`publication/` 全部普通文件、三个锁/工具配置文件，以及 `scripts/` 的 Python/Shell 源码；拒绝符号链接和非普通文件，缺失必需输入时失败。记录每个相对路径、原始字节数和 SHA-256，并复制所读取的相同字节。准备结束前重新核对输入集合及摘要，检测期间的源漂移。

准备身份由规范化 JSON 的 SHA-256 决定，覆盖有效输入、准备策略、实际 Python 解释器字节摘要/版本/平台，以及源 commit 和工作区 dirty 事实。相同 commit 下的正文、配置、锁文件、入口源码或解释器变化均不能沿用原身份。Git commit 仅是身份字段之一，不是完整标识。

这是 **PREPARATION 身份**，不冒充 PDF 构建身份：Pandoc/TeX 及实际字体尚未执行或解析，其身份标为未核验；后续编译必须扩展身份并另行验收，不可将当前锁文件文本摘要当成实际安装依赖验证。快照和清单含源内容，默认仅本地保留，不自动公开。

### 2.2 路径与状态

采用 `design/build/preview/<build-id>/<attempt-id>/`。`build-id` 是上述完整摘要；随机 `attempt-id` 区分重试，不覆盖或复用旧执行结果。它把计划中的 source-snapshot 建议落实为清单里的输入字段；后续候选和发布目录尚未实现。

准备目录包含 `run.json`、`inputs/`、未提交的 `.result-*.pending` 和完成时的 `result.json`。`run.json` 标明 PREVIEW / PREPARATION、输入身份及实际开始时间；最终 `result.json` 分别记录 PREPARED、FAILED 或 CANCELLED。PREPARED 只表示输入准备完成，PDF/保真/视觉/阅读检查均为 NOT_RUN，不写发布成功清单或授权记录。

准备产物只允许写入固定的 build/preview 子树，不接受 `--output`、`--root` 或环境变量重定向；不使用 `TMPDIR`。Git 元数据探测清除继承的 Git、Xcrun 及临时目录重定向变量，禁用 fsmonitor hook 和 pager；在任何 status 探测之前，读取所有有效配置作用域及 include/includeIf，发现 `filter.*.clean/smudge/process` 即拒绝，空值和未使用的定义也不放行。只报告配置键，不输出 helper 命令值；配置读取错误不得当作“未发现”。这些限制是保守的不支持判定，不会改写用户 Git 配置。

另读取全仓库索引，拒绝 gitlink 子模块条目，避免进入具有独立 helper 配置的仓库；status 强制 `--ignore-submodules=all`。dirty 仍来自受限上下文中的 Git porcelain 状态，不改成自行推测的字节差异，也不宣称覆盖子模块工作树；策略写入 `source.status_policy` 和准备身份。系统工具自身仍可能在默认系统目录维护缓存，不宣称进程在操作系统级只能写 build。

输出各级目录通过目录句柄及 no-follow 打开，文件只以排他创建方式写入。预先存在的符号链接、文件占据目录、输入路径逃逸均拒绝。失败后仅保留本次未完成目录供诊断，不自动删除、不尝试恢复或覆盖历史制品。

### 2.3 完成记录提交点

终态统一采用：排他创建随机 `.result-*.pending` → 写入、flush、文件 fsync 成功 → 同目录 hard link 到 `result.json`。链接成功是本地完成记录提交点；目标已存在即失败，不使用覆盖式 rename/replace。需要文件系统支持该链接操作，不支持时关闭失败，不回退到直接写最终文件。

| 故障或终止位置 | 终态规则 |
| --- | --- |
| 提交前写入、flush、fsync 或 link 失败 | 不留下已提交的 PREPARED；可另行提交 FAILED，诊断也失败则无最终记录 |
| 提交前 SIGINT / SIGTERM | 尽可能提交 CANCELLED，非零退出；暂存成功 JSON 不算成功 |
| 提交前 SIGKILL | 可能留有完整暂存文件，但没有已提交终态，视为未完成 |
| link 成功后出现异常或可捕获中断 | 用暂存/最终文件的 device＋inode 确认提交事实，保留 PREPARED，不再生成矛盾终态 |
| 提交后 SIGKILL 或回报通道失败 | 进程可能非零退出或无法回报；已提交记录仍是该尝试的终态，不据进程退出码倒推准备失败 |

仅最终名称 `result.json` 的有效记录可作为终态；当前记录带 `schema_version: 2` 和 `commit_protocol`，准备策略也升为 schema 2。`.pending` 内容无论是否可解析、是否写着 PREPARED，都不是终态，保留用于诊断。历史 schema 1 记录不因本次代码修正自动获得新协议保证。

约定的同步步骤是提交前的文件 fsync；不在提交后增加一个可能将既成终态改判失败的同步步骤。这里保证的是本地可见性的完成记录原子性，**不是整个目录树的掉电持久化保证**，也不是 B5 发布事务。SIGKILL 测试不等于断电或真实磁盘故障实验。

目录权限和路径检查不是针对同一账号恶意并发重命名、修改 Git 配置、解释器或源码的操作系统沙箱；已配置 filter 的普通执行不是该排除项，必须在探测前拒绝。后续外部编译器仍须单独评估写入权限，不继承本批未提供的隔离保证。

## 3. 验证合同

自动化测试只在临时 Git 仓库中复制入口脚本和使用文本 fixture，不调用真实 PDF 编译、检查或渲染工具。每个场景结束核对历史 dist 的完整文件集合和字节摘要；不只比较 PDF 文件，也包括清单和校验记录。

| 场景 | 预期结果 |
| --- | --- |
| 成功准备、重复准备、未提交输入 | 正确记录输入；不同尝试不覆盖；dist 不变 |
| 相同 commit 下改变正文、配置或锁文件 | build-id 改变；不误复用旧记录 |
| 解释器身份变化 | build-id 改变；不只按源 commit 定位 |
| 缺失输入、符号链接输入、准备期间输入变化 | 非零退出，无 PREPARED 假成功 |
| build/preview/标识目录符号链接或普通文件冲突 | 拒绝写入，链接目标不变 |
| 文件写入异常、取消、强制中断 | 失败/取消或不完整记录，不产生发布成功 |
| 六个旧入口、未开放操作及路径重定向参数 | 非零退出，未执行后端，不产生新输出 |

## 4. 初始实施记录：61cd8ba

环境为 macOS / Python 3.9.6。以下是初始实施时的历史执行记录，保留实际结果，不是本次修复后的验证声明。其 25 项通过不覆盖后续复现的 filter 执行与最终记录同步失败窗口；初始准备阶段安全验收未关闭。

| 命令或检查 | 实际结果与边界 |
| --- | --- |
| `python3 -B design/scripts/test-publication-isolation.py` | 修正后 25 项 unittest 通过；各用例核对临时仓库历史 dist 文件集合和字节不变 |
| `python3 -B design/scripts/pub.py preview --prepare-only` | 真实工作区准备成功；36 个输入文件，dirty=true；仅生成输入快照和记录 |
| `bash -n design/scripts/{build,preflight,render-verify,compare-renders}.sh` | 四个 Shell 入口语法检查通过 |
| `python3 -B -c '…ast.parse…'` | 以标准库 AST 解析全部六个 Python 脚本，语法通过，不执行 PDF 诊断 |
| `pandoc --from=markdown --to=json --fail-if-warnings` | README 和本文解析通过，标题层级检查通过；仅 Markdown → JSON |
| 临时 Node 检查器＋Ruby `YAML.safe_load` | 九个当前维护文档 ID 无重复，YAML 通过；归档来源不在唯一性集合中；33 个本地链接可定位 |
| 临时 Node 检查器＋`git ls-tree` / `git show c827efc:<path>` | 62 个其他受跟踪文件逐字节不变，包括历史 dist、六篇规范、设计/计划、出版配置和锁文件；工作区仅十个授权文件变化 |
| `git diff --check` | 通过 |

真实准备记录的 build-id 为 `b2a26d89a475e3421ca99ee99b262bfb8b64b9cc5014c9d36a2adc9eb927e039`，attempt-id 为 `6be931e52926487683c9d0121e5f7002`，位于已忽略的本地 build/preview 子树，不提交这些副本。逐文件摘要复核通过；PDF、保真、视觉、阅读检查均明确为 NOT_RUN。该标识绑定验证时的未提交输入，不声称是提交后的重建结果。

首轮测试并非全绿：环境重定向用例发现 macOS Git 启动器会在继承的 TMPDIR 内产生 `xcrun_db`，另有临时路径 `/var` 与 `/private/var` 的断言差异。已清除 Git 子进程的相关重定向变量并修正测试的规范路径比较，随后重跑通过。该发现仅发生在临时 fixture 的 dist，真实历史 dist 未被改写。

中断用例在测试子进程写入 run.json 后暂停并发送真实 SIGINT / SIGTERM / SIGKILL；写入异常和输入漂移通过测试侧注入，生产入口没有测试后门。它们验证的是准备阶段，不是外部编译器的取消行为。

当时未执行：PDF 构建/渲染/视觉验收、旧内容或结构审计、真实编译器及字体兼容性、B1-B 身份渲染、候选冻结、发布事务/恢复或批准绑定。旧入口封闭可保留，输入准备的安全结论以本次修复及后续复审为准；不得据此宣告真实 PDF 构建隔离、完整 WP-02 或 KB-P0 已验收。

## 5. P1/P2 窄范围修复与回归

本次基于 `61cd8ba8c3455ab57c6b6c9f612a4ef5a50e363c`，只修改本文及两个 Python 文件。实施记录升为 v0.1.1；不改变上位设计、计划、ESD 或出版工具依赖版本。

修复前，两个新增反例均在 macOS 临时仓库复现：对已跟踪文件作等字节数修改，clean helper 执行两次、测试 dist 哨兵改变，但旧入口返回 PREPARED；对最终成功记录 flush 后的 fsync 注入 EIO，旧入口非零退出，但 result.json 仍可解析为 PREPARED。只修改临时 fixture，不涉及真实历史制品。

P1 采用执行前的保守拒绝，不是事后发现 dist 改变才报错。配置包含关系和过滤器执行语义依据 [Git config](https://git-scm.com/docs/git-config) 与 [Git attributes](https://git-scm.com/docs/gitattributes) 核对。P2 按 §2.3 实现暂存同步＋不覆盖提交，并覆盖提交点前后的不同终止语义。

本次验证环境为 macOS、Python 3.9.6、Git 2.54.0（Apple Git-157）。修复后的 `python3 -B design/scripts/test-publication-isolation.py` **43 项通过**，包括原有 25 项及新增 18 项：

- clean/process helper 在配置拒绝后均未执行；本地、XDG 全局、include/includeIf 配置、空/未使用/smudge 定义、配置解析错误、全仓库 gitlink 及“探测先于 status”检查。
- 最终成功记录 fsync 注入 EIO、link 失败、已有终态不可覆盖、link 成功后注入错误，以及提交前后真实 SIGINT/SIGTERM/SIGKILL 检查。
- 所有用例核对临时 dist 完整文件集合与字节不变；信号暂停及故障注入只在测试侧，没有生产测试开关。

本次其他实际检查如下；临时检查器不入库，不把检查器退出成功外推为生产能力验收。

| 命令或检查 | 本次结果 |
| --- | --- |
| `python3 -B design/scripts/pub.py preview --prepare-only` | 真实工作区 PREPARED；36 个输入摘要匹配，schema 2；最终记录与暂存记录为同一 inode；PDF 等检查均为 NOT_RUN |
| `python3 -B -c 'import ast,pathlib; [ast.parse(p.read_text(),filename=str(p)) for p in pathlib.Path("design/scripts").glob("*.py")]'` | Python 语法通过 |
| `pandoc --from=markdown --to=json --fail-if-warnings`，临时 Node/Ruby 检查 | 本文及 README 的 Markdown/标题层级通过；33 个本地链接可定位；九个当前文档的 YAML 与 ID 唯一性通过，归档来源排除 |
| 临时 Node 检查器＋`git ls-tree` / `git show 61cd8ba:<path>` | 69 个其他受跟踪文件逐字节不变；只有两个 Python 文件及本文变化，包括 README 和六个旧入口在内的其他文件均未修改 |
| `git diff --check` | 通过 |

真实准备的 build-id 为 `0584fe605800813b6d48f45b0fd45c3775e29e10791dc65807b8f4c36420b696`，attempt-id 为 `22c52940ecd4469bb61a27f1dc4f758a`，仅保留在已忽略的本地准备目录；绑定当时未提交输入，不声称是提交后重建结果。修复开发中曾将 Git 查询的非致命 macOS 临时目录警告误当作失败，已按 `git config` 的无匹配返回码及空输出处理，并重跑全套通过。

没有执行 PDF 编译/渲染、B1-B、候选或发布；没有重跑独立复审的 Linux 环境或真实断电/磁盘故障实验。不以回归通过自行替代复审关闭。提交推送后停止。
