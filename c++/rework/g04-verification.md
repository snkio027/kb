# G4 新稿的实验与验证边界

本记录对应[序列修改与记录身份](g04-sequences-and-identity.md)、[算法、遍历能力与惰性视图](g04-algorithms-and-views.md)、[按键查找与索引一致性](g04-lookup-and-indexes.md)。§1～§6 保留以 `c5d3b17cf66fd4bb6f6cfef705d0c7cf95e16af7` 为起点、提交于 `e44219c65455c726a0de9d4204bc9c1b827c8f23` 的历史验证记录。精读接受及文字收口见 §7；G4 Content v2 为 **ACCEPTED / FROZEN**，不把阅读接受等同于重新执行。

## 1 输入与复现方式

[执行器](verify_g4.py)从三篇正文提取十六份文件：两个共用头文件、十一个正常结果程序、一个重新分配构造观察程序，以及两个编译负例。每套编译器使用新的临时目录，每个程序独立编译和运行；不执行旧 G4 或 G0～G3 的实验。

在仓库根目录执行以下命令，输出必须选择尚不存在的路径，不覆盖本次或历史结果：

```sh
python3 c++/rework/verify_g4.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --output /tmp/g4-rework-results-new.json
```

[g04-results.json](g04-results.json)记录正文与提取源码 SHA-256、执行器及进程辅助文件身份、工具链、完整命令、stdout、stderr、退出码和临时目录。执行器复用 `c++/learning/verify_g.py` 的进程、超时及取消辅助函数，不修改该文件，也不执行其中的旧实验。

## 2 环境与判据

| 项目 | 本机身份或选项 |
| --- | --- |
| 平台 | macOS 26.7，arm64；Python 3.12.14 |
| 编译器 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++，`_LIBCPP_VERSION=220106` |
| 编译器 B | Homebrew Clang 23.1.2；libc++，`_LIBCPP_VERSION=230102` |
| 语言与诊断 | `-std=c++23 -Wall -Wextra -Wpedantic`；两者 `__cplusplus=202302L` |
| 正常运行与构造观察 | 分别 `-O0 -g`、`-O2` |
| 编译负例 | `-O0 -c`，不进入链接阶段 |
| ASan/UBSan 正例 | `-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer` |
| 错误变体 | `-O0 -g`，先编译成功，再核对指定运行退出码 |

正常运行要求精确 stdout、退出码 0 和空 stderr。两个编译负例分别要求 dangling 解引用诊断、sort 调用失败及随机访问约束诊断；只有非超时的正失败退出码并匹配目标诊断才接受，不能以崩溃、缺头文件或链接失败替代。

构造观察要求正常退出、空 stderr 及两行可解析的非负计数，程序自身另检查三项完整值、size 和容量增长。判据不固定必须复制或移动几次，也不要求一种异常规格在所有实现中必定选中同一种路径。14 项局部自检检查输出、诊断、观察格式、失败退出码及超时／信号分类，包括“另一组计数允许被记录”和“错误变体崩溃不能算拒绝成功”。它们不是额外 C++ 实验。

sanitizer 环境为 `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0` 和 `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=0`。每套工具链先运行合法插桩探测；不可用则记 SKIP，不算通过。本批没有 ASan 阳性对照，不把 G1 的旧阳性实验继承为本次执行；泄漏检测及外部符号化关闭。[ASan](https://clang.llvm.org/docs/AddressSanitizer.html) 与 [UBSan](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) 的文档只说明工具能力，不把一次干净运行外推为语言或容器合同证明。

## 3 分项执行结果

| 证据类型 | 最终本地结果 | 结论边界 |
| --- | --- | --- |
| 正常编译与运行 | 十一个程序 × O0/O2 × 两套编译器，44 项 PASS | 完整值、位置关系、查询及替换结果符合当前判据 |
| 编译负例 | 两个负例 × 两套编译器，4 项 PASS | 目标调用在本机得到预期的类型／能力诊断 |
| 重新分配构造观察 | O0/O2 × 两套编译器，4 项 OBSERVED | 记录本机复制／移动选择，不是性能实验 |
| ASan/UBSan 正例 | 十二个运行程序 × 两套编译器，24 项 CLEAN_OBSERVED | 这些执行未报告错误，不证明不存在其他失效路径 |
| 错误变体 | 四种变体 × 两套编译器，8 项 REJECTED_AS_EXPECTED | 在编译成功后拒绝四种具体逻辑错误 |
| 判据自检 | 14 项符合预期 | 执行器局部判据自检，不是完整框架验证 |

两套工具链均为 Clang 与 libc++，不是两类标准库或两个操作系统。两个 sanitizer 探测可用，SKIP 为 0，最终记录为 `COMPLETE`。没有将同一源码的多种编译模式累计成不同实验，也没有把这些结果称为 GitHub CI。

`relocation-observation.cpp` 的两套工具链在 O0/O2 中都观察到：不抛移动类型为 `copies=0; moves=3`，可能抛移动类型为 `copies=3; moves=0`。插桩构建观察到同样数字，归入 CLEAN_OBSERVED，不重复加入四项普通构造观察。两种移动实现实际上都不抛；没有执行真实 throwing-move 失败恢复。

本批先在 `/tmp/g4-first-results-20261001.json` 完成初稿验证，再校准说明并补齐显式头文件包含，对最终正文重新提取和执行；本表只统计最终结果，不累加两次运行。最终源码、正文及执行器身份均绑定仓库 JSON，不把初稿正文摘要冒充当前摘要。

## 4 用错误变体验证判据

| 变体 | 故意破坏的合同 | 运行时预期拒绝 |
| --- | --- | --- |
| `omit-tail-erasure` | 压缩以后不擦除尾部，容器仍有多余项 | `compact-records.cpp` 返回 3 |
| `accept-next-key` | lower_bound 后遗漏编号相等检查 | `ordered-lookup.cpp` 返回 3 |
| `omit-last-index-entry` | 建索引时漏掉最后一条记录 | `indexed-replacement.cpp` 返回 2 |
| `accept-duplicate-key` | 重复键插入失败却不拒绝整批输入 | `indexed-replacement.cpp` 返回 3 |

所有变体只生成在新临时目录，正文保留正确实现。记录保存替换前后文本、变体源码摘要、编译诊断及运行结果。变体需要编译成功、非超时、指定退出码及空 stdout/stderr；编译不通过、崩溃或 sanitizer 报警均不是这些逻辑错误被正确拒绝的替代证据。

IndexedBatch 的失败实验通过真实的重复键检查抛出 `invalid_argument`，验证旧状态、旧借用和已有查询结果仍保持；它不是分配器故障注入。没有注入 State 分配、vector 分配或哈希表节点分配失败，未将机制分析写成这些失败路径已经动态覆盖。

## 5 未验证范围

没有运行失效迭代器、悬挂捕获、非法 filter 元素修改或不满足严格弱序的排序。它们在正文按合同分析，不假定 ASan/UBSan 能诊断所有这些错误。没有遍历全部空输入、全无效输入、比较器、allocator、哈希碰撞和元素异常组合，也未验证通用字符串归一化规则。

flat_map、mdspan、PMR、代理引用的完整矩阵仍未实验；未执行 Linux/Windows、libstdc++、Zig/Rust。**性能、profile、汇编分析、并发动态检测和 TSan 均为 NOT RUN**。构造计数是实现机制观察，不是性能基准。输入流实验也不是格式错误及 I/O 故障处理验收。

**PDF 为 NOT BUILT / NOT VALIDATED**。旧稿、已发布手册和出版系统不因 G4 新稿而升级状态。`e44219c` 提交时，内容深度与中文质量仍待精读接受，没有以本地结果自动冻结 G4；后续接受登记见 §7。该批未启动 G5。

## 6 文档与保护范围检查

2026-10-01 实际运行 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 c++/learning/check_docs.py`：解析 57 份 Markdown，核对 905 处本地链接，错误为 0。检查器继续报告旧 v1 的 16 项代码／图形分页风险，不把它们算作新稿缺陷，也不宣称验证了新稿分页或全部外部链接。

临时只读 Python 检查通过 Pandoc GFM AST 核对十七份重编 Markdown 的单一 H1、连续 H1～H3 层级、标题锚点唯一、围栏闭合及无 HTML 折叠依赖；三个新单元各有六道迁移题及六份推理答案。重新提取十六份文件，其摘要及三篇正文摘要均匹配最终 JSON；执行器及复用辅助文件摘要也匹配。

同次检查调用只读 `protected_binding()`，逐字节确认起点登记的 47 个受保护文件不变：v1 的 13 篇 G、10 篇 FM、两份正式 PDF，以及 G0～G3 正文、验证记录、JSON、执行器和进程辅助文件。旧实验没有重跑，旧 JSON 未追写。本批差异限定为三篇 G4 正文、验证说明、执行器、结果 JSON 和两个 README，共八个文件；`git diff --check` 无错误。

另以超过 40 行或超过 100 字符的代码行为新稿分页复核信号，得到 `indexed-batch.hpp` 为 50 行、最长 84 字符；保持整份类型定义完整，续页交给未来出版层。该信号不是已经出现的 PDF 裁切问题。本次未执行 PDF 编译、渲染或视觉验收，G5 未启动。

## 7 精读接受与文字收口

2026-10-01，读者对 `e44219c65455c726a0de9d4204bc9c1b827c8f23` 的三单元正文与验证记录完成精读，接受中文论述、章节组织及证据整合，未发现阻断性技术问题。本次仅完成冻结前的精度校准：第一单元改题为“序列修改与记录身份”，在 §1 区分 C++ 对象身份与业务编号所表达的记录身份；§3 明确不可 CopyInsertable 元素的移动构造抛异常时，reserve 不再提供原无效果保证。采用“失去保证”的表述，不将该情形称为未定义行为，也不声称已动态验证真实 throwing-move 路径。

第二单元 §5 同时采纳可选校准，说明 borrowed_range 所关心的是迭代器有效性与范围变量生命的关系，不把它解释为底层元素永久有效，也不扩张为对任意关联状态的生存保证。原有 `Rows&`、临时 span 与 filter_view 的条件说明保留；第三单元正文未修改。

G4 Content v2 据此登记为 **ACCEPTED / FROZEN**。冻结正文摘要如下；历史 JSON 仍绑定 `e44219c` 的正文，不追写为新字节，也不把本次接受登记称为重新执行。

| 当前冻结正文 | SHA-256 |
| --- | --- |
| `g04-sequences-and-identity.md` | `39806b718373c2b9f2ae25b1b4ba74464d3f68f133b591165882d65cdff037ee` |
| `g04-algorithms-and-views.md` | `57b897c8c438925fd7d1ee99bf9687de59ac8f3acc0b71b89e9b1da873ac0994` |
| `g04-lookup-and-indexes.md` | `e6c25ada6aaecbffd27ac638f16cddb9a136f3f168681643d1b7050e7e9b7039` |

本次用临时只读 Python 检查调用 `extract()`，重新提取十六份文件，SHA-256 全部匹配历史 JSON；用 `git show e44219c:<path>` 独立核对该 JSON 中的旧正文摘要。三单元的 17 个完整围栏块、六个迁移问题／答案区域逐字节未变；执行器、进程辅助文件、结果 JSON 和第三单元也与该提交逐字节相同。调用只读 `protected_binding()` 确认原先登记的 47 个受保护文件不变，没有调用实验入口或判据自检。

文档检查命令仍为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 c++/learning/check_docs.py`。本次解析 57 份 Markdown、核对 906 处本地链接，错误为 0；原有 16 项 v1 代码／图形分页风险保留。另用临时只读 Python 与 Pandoc GFM AST 核对十七份重编 Markdown 的单一 H1、连续 H1～H3 层级、标题锚点唯一、围栏闭合及无 HTML 折叠依赖。`git diff --check` 无错误，差异限定为两份 G4 正文、本说明与两个 README，共五份 Markdown。

本次 C++ 编译与运行、负例诊断、构造观察、ASan/UBSan、错误变体及判据自检均为 **NOT RUN**；§3 的 44／4／4／24／8 项及 14 项自检仍是 `e44219c` 的历史本地证据，不是本次结果或 CI 结论。性能、并发、跨平台等未验证边界不变。G5 只登记后续方向，未启动；PDF 未构建，出版系统及已发布制品未修改。
