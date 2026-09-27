# FM 全书出版候选 · v1.0.0

状态：**PUBLICATION_CANDIDATE / STRUCTURAL_PASS / VISUAL_REVIEWED（自查）**。等待集中审核与最终 publish 授权；不是 `RELEASED`。本批不进入真实 API 应用，不重新编辑 FM，也不重新设计出版系统。

## 固定身份

| 对象 | 身份 |
| --- | --- |
| 内容源 / 本批 Base | `45b305eace0f057420587d685cb3f962f3f0552c` |
| Publication ID / Version | `CPP-FAILURE-MODEL / 1.0.0` |
| 中文 / 英文书名 | C++23 失败语义工程手册 / Modern C++ Failure Semantics Handbook |
| 冻结 Visual Profile | `v1.0 / 1c11c5940c05fe29c46c4500935d5efb673d46a7`；接受登记 `ea2e613` |
| 候选 ID | `d4ef80eb65a20e3048c9814b40b733bbb9c509c38303d19438ed9d422636d83d` |
| PDF | 158 页；`Modern-Cpp-Failure-Semantics-Handbook-v1.0.0.pdf` |
| PDF SHA-256 | `2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c` |

交付入口：[候选载荷与发布记录](../../releases/cpp-failure-model/v1.0.0/README.md)。准备身份、实际工具及工作树输入分别保存在原始 `run.json` 与 `preview-audit.json`，不能用 Base commit 单独代表本次构建实现。

## 内容范围与保真

阅读正文为 `series-guide.md` 与 FM-0～FM-9，顺序固定。11 份 Markdown 与 `45b305e` Git blobs 逐字节相同；原稿、实验、Gate／checklist、历史证据未改。README 保持仓库导航角色；`review/` 只以历史证据清单和固定 Git 身份进入发布记录，不混入书中。

| 本次实际核验 | 结果与边界 |
| --- | --- |
| 11 份正文源字节 | 与冻结 commit、本机文件、构建快照一致 |
| 527 个 fenced payload | 逐块一致，含 215 个 C++ 块；不是 527 个可运行实验 |
| 五个正文 `fm-test` 标记 | T12、T14、T17、T18、T19 保持；其余 T01～T20 证据在原 review 中，不额外印入正文 |
| 189 个显式 HTML anchors | 中文、数字和重名按章节命名空间处理；目标内容开头核对，不向上模糊归到祖先标题 |
| 383 个源标题区间 | 标题／归属／顺序／书签检查通过 |
| 2,628 个有序内容单元 | 按标题区域消费对应内容，避免把别处的同文当作保真 |
| 560 处 inline literals | 使用独立的空白敏感检查 |
| 77 条表格关系 | 列名、记录与值对应检查通过 |
| 146 处正文内部引用 | 按所属章节、目的地和出现次数核对实际 annotations；其中 94 处跨章 |
| 全页渲染 | 158 / 158；未发现 missing glyph 或 overfull hbox |

FM-9 的两份填写模板原本是 fenced Markdown，不是空表格。本批保留其完整字面内容、顺序、空占位与具名续页，不捏造表格数据，也不把模板内容转成额外正文标题。`sample.cpp` 是五个单代码块的生成文件标签，其角色在 adapter ledger 登记，不改源文件名。

机器检查不等于视觉审查：全文均渲染；实际视觉检查覆盖 38 个代表页总览，其中 9、53、108、109、132、153、154、155 页另作单页详查。范围、页图摘要及观察见 [visual-inspection.json](visual-inspection.json)。第 158 页短尾、长模板跨页和少数代码软折行保留为已冻结规则下的非阻塞限制，不触发 Typography Pass。

## 真实通用缺陷与限定修复

新增产品仅位于 [cpp-failure-model profile](../../profiles/cpp-failure-model/profile.json)。共享 LaTeX 尺寸、字体、主色与分页规则不改；engine 没有产品 ID 分支。

本次整书实际遇到三类兼容问题，按既有授权在批内修复：

1. **解析合同不匹配。** 原稿按 GFM 维护，锚点紧接 H1 在旧 `markdown-smart` 下可能被当成一个段落。增加显式 `source_format: gfm`，默认旧解析器保持不变，非支持选项拒绝。选择参与准备身份。
2. **块级目标不等于标题别名。** 旧 § 目标可能在加粗段落，而不是 Header。新增通用空 Span 目标，按文档 ID＋源 ID 摘要命名；书签仍只检查真实标题。链接必须直接指向该块，不能继承前一 section 的 `currentHref`。
3. **源警告标签的绑定。** Adapter 只声明原文紧邻代码且精确匹配的显式标签，通用编排验证相邻文本后将原文放入首代码标题；不凭代码行为推断“危险”。`⇔` 缺字仅在 FM theme 中沿用现有数学箭头 fallback。

[九项新增回归](../../tests/test-failure-model.py)包括完整源／payload／anchor 检查、Unicode/数字/重名块目标、未知 raw markup 拒绝、精确警告绑定、解析选项身份及拒绝，以及真实 PDF annotation 正反对照：两者均成功编译，旧 hyperlink 方式留下 destination 但没有正确 annotation，必须被拒绝。

ESD、G 全书与正式版在相同 adapted inputs 上的 `compose` 输出与接受 engine 对照一致。旧 RC 身份测试里的固定摘要改为针对其历史 commit；没有用新摘要冒充旧版本。当前兼容性另由上述对照及实际 preview 回归承担。没有重建或覆盖已发布的 G 手册。

## 执行记录与证据分类

执行环境：macOS 26.7 arm64、Python 3.12、Pandoc 3.11、LuaHBTeX 1.24.0 / TeX Live 2026、Poppler 26.05.0、pypdf 6.10.0；精确版本与工具摘要以原始记录为准。仅本地执行，不是 GitHub CI。

```sh
# 以下 python3 必须是具备 publication/requirements.txt 依赖的解释器。
python3 -B publication/engine/pub.py preview --profile cpp-failure-model
python3 -B publication/reviews/failure-model/audit.py <完整 preview attempt 路径>
python3 -B publication/reviews/failure-model/check.py <新的检查输出目录>
python3 -B publication/reviews/failure-model/assemble.py <已审阅的 preview attempt 路径>
python3 -B publication/reviews/failure-model/verify-delivery.py
```

实际使用解释器的绝对路径、每条命令、返回码和日志摘要见 [checks-final/checks.json](checks-final/checks.json)。`assemble.py` 是一次性候选导出器：严格复制检查过的字节，现有文件拒绝覆盖，不包含编译、网络、tag 或发布动作；随附检查、视觉记录或摘要不匹配则拒绝。

| 证据类别 | 本次结果 |
| --- | --- |
| 出版回归 | 121 项通过，0 SKIP：原 112 项＋FM 9 项；含真实编译、失败／取消隔离与终态检查 |
| 文档结构／链接 | 原有 C++ 检查器：40 份 Markdown、822 个本地链接、0 errors；不是联网检查或技术证明 |
| 原稿与历史资产保护 | 997 个不在修改白名单内的既有 tracked 文件逐字节一致；完整 `design/dist/` 文件集合一致；含所有历史 PDF、六篇 ESD 和 G 正式版 |
| C++ 编译／负例诊断 | **NOT RUN**；保留历史 T01～T20 与 R01 的证据身份 |
| 性能 | **NOT RUN** |
| 并发动态检测 / TSan | **NOT RUN** |
| 阅读器 | Chrome 用户反馈通过；Preview 仅完成部分观测，详见下节 |

本批四次整书尝试均保留，不覆盖失败历史：前两次 `FAILED`（锚点进入标题参数、缺失 `⇔` 字形）；第三次 `PREVIEW_READY` 但被追加正文 annotation 审计拒绝，不能成为候选；第四次通过并成为唯一选定载荷。旧成功终态没有事后改写，新增判据与处置在本记录明确区分。

开发期 `unittest discover` 因连字符文件名未发现测试（0 tests / exit 5），不计通过。改为逐脚本执行。第一份 [checks-01](checks-01/checks.json) 各脚本返回 0，但执行期间输入继续变更，因此整体检查拒绝；最终 `checks-final` 在稳定输入上重跑并通过。最小新 PDF 测试的字体缓存写入路径也已在测试侧限定到临时目录。以上不是 C++ 测试失败或内容修订。

原有 `check_docs.py` 的固定 `pdf: NOT BUILT / NOT VALIDATED` 字段描述其自身不验证 PDF，不能覆盖本批独立出版记录；没有为更改该字段去修改冻结来源或旧检查器。

打包后另运行 `verify-delivery.py`：候选载荷／证据摘要、121 项日志摘要、997 个保护文件及五份新增／更新 Markdown 的 35 个本地链接均通过。新增文本与 JSON 的常见私钥／token 字面扫描未命中；这是有限规则扫描，不是全面秘密检测认证。

## Reader qualification 与停止点

[reader-evidence.json](reader-evidence.json)绑定当前 PDF 摘要：Preview 11.0 / macOS 26.7 已显示准确文件、158 页、中文封面及 guide＋十章书签树。之后目标切换和 UI 查询超时，不能把尝试点击记为通过。

浏览器工具拒绝 `file://`，未绕过策略；用户对精确路径与 SHA-256 的 Chrome smoke card 回复“通过”。按 **USER_REPORTED_PASS** 登记，Chrome/OS 版本和逐项观察未提供。此项不等于自动化 PDFium 测试，也不填补 Preview 未测项。其他阅读器未测。

当前可提交集中复审与发布决策，但不得声称完整多阅读器矩阵已自动化验收。最终发布决策须明确接受上述阅读器证据边界，或补足所需测试。**候选接受不等于发布授权**；本批到最终 publish Gate 停止，tag 与 GitHub Release 未创建。
