# G 系列学习版与目录整理记录

日期：2026-09-26。用途：个人长期学习、实验与回查，不是项目规范批准或全系列技术验收。

## 1. 基线、范围与来源

- 修改前受控基线：`be61a1d96ae0dbf6d5fbabfde6648c6a582a4420`。
- 本地完整的 G2～G12 原稿先以原始字节接收：`2dbaa9512906b452403b330645f01db329ec3ed3`（11 文件，+46750 行）。此提交是来源保存，不是审校通过。
- 本批：全系列导航、G0～G4 学习修订稿 1.1、合理重命名、FM 整体入子目录、定向实验与必要链接同步。
- G5～G12 只改路径，不改正文。FM-0～FM-9 不重开 R01 或其他技术结论。已有 30 天提醒不在本批变更范围。

旧 G0/G1 在基线提交保留；旧 G2～G12 在原稿接收提交保留。新的学习版不再使用 Frozen/Complete 作为未经验证的当前状态。

## 2. 名称与入口

编号补零用于目录排序，`and` 替代文件名中的 `&`，C++ 主题在文件名写为 `cpp`。正文中的 G 编号不变。

| 原文件名（均位于 c++） | 当前文件名 |
| --- | --- |
| `g0-native-toolchain.md` | [`g00-native-toolchain.md`](../g00-native-toolchain.md) |
| `g1-object-model.md` | [`g01-object-model.md`](../g01-object-model.md) |
| `g2-raii&ownership.md` | [`g02-raii-and-ownership.md`](../g02-raii-and-ownership.md) |
| `g3-value&performance.md` | [`g03-value-semantics-and-performance.md`](../g03-value-semantics-and-performance.md) |
| `g4-stl.md` | [`g04-stl-and-ranges.md`](../g04-stl-and-ranges.md) |
| `g5-generic&comptime.md` | [`g05-generics-and-compile-time.md`](../g05-generics-and-compile-time.md) |
| `g6-memory.md` | [`g06-memory-and-performance.md`](../g06-memory-and-performance.md) |
| `g7-concurrency.md` | [`g07-concurrency-and-memory-model.md`](../g07-concurrency-and-memory-model.md) |
| `g8-abi.md` | [`g08-abi-and-c-interop.md`](../g08-abi-and-c-interop.md) |
| `g9-dx.md` | [`g09-build-and-native-ecosystem.md`](../g09-build-and-native-ecosystem.md) |
| `g10-runtime.md` | [`g10-systems-runtime-project.md`](../g10-systems-runtime-project.md) |
| `g11-robotic.md` | [`g11-robotics.md`](../g11-robotics.md) |
| `g12-c++&zig&rust.md` | [`g12-cpp-zig-rust.md`](../g12-cpp-zig-rust.md) |

FM 十篇及整个 `review/` 迁至 [failure-model/](../failure-model/README.md)。十篇正文、历史结果 JSON、样例、命题表和执行器保持字节不变；历史修订记录只增加迁移说明并更新可重跑命令的脚本定位。旧 JSON 的原始执行路径不改写。

[根入口](../../README.md)与 [C++ 导航](../README.md)同步。为避免既有引用断开，`design/project/asset-register.md` **仅替换 G0/G1 两个链接目标**；其接收状态、ECD 边界和其他说明不变。不是整个 design 目录零变更。

## 3. 学习内容怎么改变

| 文档 | 主线改善 | 定向实验 |
| --- | --- | --- |
| G0 | 从三文件分离编译讲起，再区分五层错误；ABI 数值注明平台范围 | 缺失定义链接失败 → 补齐定义运行 |
| G1 | 从对象/存储/访问关系解释生命周期，修正值类别与借用有效期 | reserve/clear 的活对象数；独立 ASan UAF 反例 |
| G2 | 压缩所有权、手工清理与 RAII 的碎片化表述；补独占复制、提交点及委托构造边界 | 正常/return/throw/部分构造清理；weak lock 保活 |
| G3 | 用类型合同区分值、表示和成本；补重载选择、allocator 与 moved-from 条件 | 完整值复制与别名；const/copy-only；prvalue 正例/NRVO 负例 |
| G4 | 先学 owner → range → algorithm；给出构造后只读的 SignalBatch，明确排序、缺失、重复与空输入 | 组件完整判据；容量增长；拥有型 view；list 排序约束负例 |

五篇均有首读路线、回查边界和 Final Gate 推理答案。G2～G4 保留原 Part 编号及进阶主题，增加折叠索引与稳定锚点；没有把“保留参考内容”写成“所有片段已验证”。跨语言只是辅助对照，不设为首次学习前置。

代码以 Markdown 为单一源，由 [verify_g.py](verify_g.py)提取到临时目录。两个定向错误变体检验判据：G3 的截断复制必须返回 1；G4 将 lower_bound 后继误当命中必须返回 3。它们不是正文实现，也不是泛用 mutation 平台。

## 4. 实际执行与结果

全部命令从仓库根目录执行，只使用本机已有工具。

| 命令 | 实际结果与边界 |
| --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s c++/learning -p 'test_*.py' -v` | 13 项通过：提取、路径限制、负例诊断、错误退出、信号、超时；不是 C++ 语义的 13 次独立证明 |
| `python3 c++/learning/verify_g.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++` | 13 个正文实验 × 2 工具链 = 26 个案例通过；另 2 个错误变体 × 2 = 4 次编译成功后按指定返回码被拒绝；共 30 个案例，无 SKIP |
| `python3 c++/failure-model/review/verify_fm.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++` | 迁移后 20 × 2 通过，无 FAIL / DIVERGENCE / SKIP / HARNESS_ERROR；不替换历史 FM 证据 |
| `python3 c++/learning/check_docs.py` | 32 份 Markdown 解析、629 处本地文件/锚点链接、G0～G4 标题层级检查通过；不包含联网链接可达性或技术正确性证明 |
| `git diff --check`（暂存后另用 `--cached`） | 无空白差异错误；不等于全部 Markdown 风格规则通过 |

[实际实验结果](verification-results.json)绑定五篇最终正文及执行器摘要，保留每个实验的源码摘要、完整命令、stdout/stderr 和返回码。发布记录仅将临时目录前缀统一为 `<TEMP>`；PID、地址等是本次观察，不是期望常量。完整源程序可从正文按相同标记重新提取。

工具链：Apple Clang 21.0.0 / libc++ 220106，以及 Homebrew Clang 23.1.2 / libc++ 230102；两者均在 macOS arm64，使用 C++23。**不是 GCC/libstdc++ 或跨平台验证。**

首轮 ASan 反例已输出正确 UAF 诊断，但 macOS 默认信号终止不满足退出码判据，故当时记录 FAIL。执行器随后显式设置 `abort_on_error=0:exitcode=86:symbolize=0`，最终要求“正常产生指定错误退出码 86＋指定 UAF 诊断”，没有把任意崩溃放宽为通过。未检查符号化栈的源码行。

新 FM 迁移重跑的完整日志保留在本地临时目录 `fm-verification-3znykeg9`；仓库只记录其命令、摘要关系和汇总，不声称历史 JSON 就是这次新运行。其 11 个输入摘要与执行器摘要仍与原提交证据精确匹配。

## 5. 保持不动与未验证项

对本批开始时纳入清单的 112 个文件，按重命名映射重算 SHA-256：103 个保留原始字节，9 个属于申报的正文/入口/记录修改；新增学习资料另计。其中：

- G5～G12 的 8 篇原稿字节不变。
- FM 十篇正文及 4 个验证资产字节不变；修订说明仅作前述定位更新。
- 8 份已跟踪 PDF 字节不变，所有既有出版脚本、配置、模板及六篇核心规范不变。
- design 的 65 个既有文件中，仅资产登记的一行链接改变，其余 64 个字节不变。
- 不构建 PDF，不同步旧 PDF 标题/文件名，不执行正式发布，不修改提醒。

未完成：G5～G12 学习版重构、所有历史 C++ 片段验证、分配失败注入、性能 benchmark、Rust/Zig 编译和完整技术验收。G4 的自主 benchmark 与扩展练习明确未执行。关键主线采用 N4950 固定 C++23 条款及工具官方说明，并在对应正文就近给出参考；链接存在不代表本文获得标准组织认证。

本批完成后按既有授权提交并推送供集中审核；不以实验全绿自动扩大下一批范围。
