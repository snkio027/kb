---
document_id: "KB-PUB-B1A-001"
version: "0.1.0"
title: "B1-A 出版入口隔离实施合同与验证记录"
status: "IMPLEMENTATION RECORD / NOT RELEASE APPROVAL"
date: "2026-09-21"
base_commit: "c827efcd918bd36c11efb84ee0671b0f2f936fcf"
---

# B1-A 出版入口隔离实施合同与验证记录

## 1. 授权与修改范围

本轮依据出版设计复审后的独立授权，实施 [设计 §10](publication-design.md) 的 B1-A 安全切片，检查、提交、推送后停止。不修改设计稿 v0.1.0、计划 v0.2.0、六篇规范、历史来源、PDF、出版模板/配置或字体锁；不启动 B1-B、B2 或正式发布。

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

准备目录包含 `run.json`、`inputs/` 和完成时的 `result.json`。`run.json` 标明 PREVIEW / PREPARATION、输入身份及实际开始时间；`result.json` 分别记录 PREPARED、FAILED 或 CANCELLED。PREPARED 只表示输入准备完成，PDF/保真/视觉/阅读检查均为 NOT_RUN，不写发布成功清单或授权记录。

准备产物只允许写入固定的 build/preview 子树，不接受 `--output`、`--root` 或环境变量重定向；不使用 `TMPDIR`。Git 元数据探测会清除继承的 Git、Xcrun 及临时目录重定向变量，禁用配置的 fsmonitor hook；系统工具自身仍可能在默认系统目录维护缓存，不宣称进程在操作系统级只能写 build。输出各级目录通过目录句柄及 no-follow 打开，文件只以排他创建方式写入。预先存在的符号链接、文件占据目录、输入路径逃逸均拒绝。失败后仅保留本次未完成目录供诊断，不自动删除、不尝试恢复或覆盖历史制品。

SIGINT / SIGTERM 尽可能记录 CANCELLED 并非零退出；SIGKILL、掉电或诊断写入失败可能没有 result，此时缺少有效 PREPARED 结果就是未完成，不能推定成功。目录权限和路径检查不是针对同一账号恶意并发重命名、修改解释器或源码的操作系统沙箱；后续运行外部编译器必须单独评估其写入权限，不继承本批未提供的隔离保证。

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

## 4. 实际执行记录

环境为 macOS / Python 3.9.6。以下均在本轮执行；源工作区包含本批未提交修改，测试结果不是独立复审或发布批准。

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

未执行：PDF 构建/渲染/视觉验收、旧内容或结构审计、真实编译器及字体兼容性、B1-B 身份渲染、候选冻结、发布事务/恢复或批准绑定。B1-A 当前可确认的是旧入口封闭和输入准备隔离；**不得据此宣告真实 PDF 构建隔离、完整 WP-02 或 KB-P0 已验收**。本轮提交推送后停止。
