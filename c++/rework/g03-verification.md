# G3 新稿的实验与验证边界

本记录对应[值的复制、赋值与移动](g03-value-copy-and-move.md)和[参数、返回值与表达式类别](g03-expressions-and-return.md)。G3 在 `852545e45475aa14cef876936a29136927978522` 获得精读接受，完成文字收口后为 **ACCEPTED / FROZEN**，见 §7。§1～6 保留该提交的本机编译、运行及观察记录，原批次起点为 `9276e3e6054366cf1dc82367d0892c588aedd579`；G0～G2 及历史执行证据保持原字节。这些不是 GitHub CI，也不表示整章语言命题已经获得自动证明；本次文字收口未重新执行实验。

## 1 输入与复现方式

[执行器](verify_g3.py)从正文提取十四份完整文件：三个头文件、八个正常结果程序、一个构造观察程序和两个编译负例。每套编译器使用新临时目录，每个程序独立运行；源码、正文、执行器与复用进程辅助文件的 SHA-256，以及完整命令、stdout、stderr 和退出码保存在 [g03-results.json](g03-results.json)。不从旧 G3 或 FM 提取代码，也不重写它们的证据。

在仓库根目录执行以下命令。再次运行应选择尚不存在的输出路径，不能覆盖本次结果：

```sh
python3 c++/rework/verify_g3.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --output /tmp/g3-rework-results-new.json
```

执行器复用 `c++/learning/verify_g.py` 的进程、超时与取消辅助函数，不改该文件，也不执行其中的 v1 实验。编译负例要求正的失败退出码且匹配目标类型的已删除构造诊断，不能以链接失败、缺文件、信号退出或超时替代。普通运行要求精确输出、退出码与空 stderr；构造观察用完整输出匹配，允许普通 NRVO 计数为 0 或 1，禁用可选的复制/移动省略时则要求为 1。

## 2 环境与构建模式

| 项目 | 本机身份或选项 |
| --- | --- |
| 平台 | macOS 26.7，arm64；Python 3.12.14 |
| 编译器 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++，`_LIBCPP_VERSION=220106` |
| 编译器 B | Homebrew Clang 23.1.2；libc++，`_LIBCPP_VERSION=230102` |
| 语言与诊断 | `-std=c++23 -Wall -Wextra -Wpedantic`；两者 `__cplusplus=202302L` |
| 正常运行与构造观察 | 分别 `-O0 -g`、`-O2` |
| 禁用可选的复制/移动省略 | `-O0 -g -fno-elide-constructors -DEXPECT_NO_ELISION` |
| ASan/UBSan 正例 | `-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer` |
| 错误变体 | `-O0 -g`；必须先编译成功，再以指定退出码拒绝 |

两套工具链都是 Clang 与 libc++，不是两个操作系统或两类标准库。动态检查设置 `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0` 和 `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=0`；泄漏检测及外部符号化关闭。两个能力探测仅说明正常插桩程序能编译运行，本次没有 ASan 阳性对照，不沿用 G1 的阳性结果冒充本次执行。

## 3 分项结果与构造观察

| 证据类型 | 本次结果 | 结论边界 |
| --- | --- | --- |
| 正常编译与运行 | 八个程序 × O0/O2 × 两套编译器，32 项 PASS | 完整值、独立性、失败状态、交接及静态查询符合判据 |
| 编译负例 | 两个负例 × 两套编译器，4 项 PASS | 显式删除移动、返回不可移动命名局部对象均得到目标诊断 |
| 构造观察 | O0/O2 及禁用可选的复制/移动省略，各两套编译器，共 6 项 OBSERVED | 普通构建的 named move 为 0，禁用后为 1；不是耗时测试 |
| 直接结果对照 | 不可复制／不可移动类型，禁用可选的复制/移动省略后 2 项 PASS | 两套工具链仍接受同类型纯右值结果初始化 |
| ASan/UBSan 正例 | 九个运行程序 × 两套编译器，18 项 CLEAN_OBSERVED | 本次插桩运行未报告错误，不是完整生命、别名或泄漏证明 |
| 错误变体 | 四种变体 × 两套编译器，8 项 REJECTED_AS_EXPECTED | 编译成功后，判据拒绝四种具体错误 |
| 判据自检 | 13 项符合预期 | 正常输出、诊断、观察范围及失败分类的局部自检，不是额外 C++ 实验 |

结果按不同模式统计，不把同一文件多次执行称为多个独立实验。两个 sanitizer 探测可用，SKIP 为 0；最终记录为 `COMPLETE`。本批先在 `/tmp/g3-first-results-20261001.json` 完成一次初稿验证，随后仅校准解释与使用说明，再对最终正文重新提取执行；表中不累加两次结果。

`return-observation.cpp` 在两套工具链的 O0/O2 构建中均观察到 `direct_moves=0; named_moves=0; forced_moves=1`；禁用可选的复制/移动省略后为 `direct_moves=0; named_moves=1; forced_moves=1`。插桩构建也观察到 named move 为 0，其状态归入 CLEAN_OBSERVED，未重复加到六项构造观察中。判据允许普通 NRVO 不发生，不要求未来编译器也打印 0。

故意写出的 `return std::move(local)` 在本次编译得到 `-Wpessimizing-move` 警告，完整诊断保留在 JSON；它是反面比较对象，没有消音或改成生产建议。禁用可选的复制/移动省略是本次 Clang 的工具观察，不推断其他编译器支持同一命令，也不把构造次数换算成性能收益。

## 4 错误变体与失败注入

| 变体 | 被破坏的命题 | 编译成功后的预期退出码 |
| --- | --- | --- |
| `truncate-copy` | 非空复制只保留第一项，完整值比较必须拒绝 | `copy-value.cpp` 返回 1 |
| `no-op-copy-assignment` | 赋值什么都不做，空目标不能被当成完整副本 | `copy-value.cpp` 返回 4 |
| `commit-before-preparation` | 先改批次号再复制，分配失败后目标不再保留旧值 | `copy-failure.cpp` 返回 4 |
| `leave-moved-length` | 移出指针却保留源长度，破坏长度与存储关系 | `move-state.cpp` 返回 2 |

四种变体都只生成在临时目录；替换范围、完整变体源码摘要及执行结果保存在记录中，正文保持正确实现。每个变体还要求 stdout/stderr 为空，崩溃和超时不是成功拒绝。长度错误先通过 `size()` 检查被拒绝，不依赖构造非法 span 或读取无存储元素触发工具报警。

分配故障是在下一次非空数组分配入口抛出 `bad_alloc`，不是物理内存耗尽。正常路径实际分配并释放数组；计数器只记录入口尝试与成功分配，不统计释放，也不证明整个进程没有泄漏。测试检查复制构造失败后的源、复制赋值失败后的源与目标、目标原存储地址、自赋值不消耗故障开关以及失败后的正常再赋值。这里没有通用元素构造异常、allocator 传播、短写、I/O、设备或分布式故障。

## 5 未验证范围与接受边界

`Risky` 与 `MoveOnlyRisky` 仅用于不求值的类型查询，未实现或运行抛异常的移动；不声称覆盖 throwing-move 的全部矩阵。没有遍历全部空值、长度与特殊成员组合，没有验证任意用户类型的值语义。SANITIZER 的干净观察不能代替语言规则或类不变量论证。

性能基准、profile、汇编分析、并发动态检测、TSan、Linux/Windows、libstdc++、Zig/Rust 均为 **NOT RUN**；PDF 为 **NOT BUILT / NOT VALIDATED**。分配计数和构造计数是机制观察，不升级为性能实验。语言规则以正文链接的 C++23/N4950 为基线，工具选项另查 Clang 官方资料；没有把更新草案的规则自动代入 C++23。

`852545e` 提交时，正文的中文流畅度、讲解深度和章节组织仍待实际精读；后续接受及文字收口见 §7。本地程序符合判据支持本批实验的可用性，不自动冻结 G3，也不改变已出版 v1 的内容与证据身份。

## 6 文档、摘要与范围检查

2026-10-01 实际运行 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 c++/learning/check_docs.py`：解析 53 份 Markdown、检查 881 处本地链接，错误为 0。临时只读 Python 检查另核对十三份重编 Markdown 的单一 H1、连续 H1–H3 层级、标题锚点唯一、围栏闭合及无 HTML 折叠依赖；两份新正文各有六道迁移题与参考答案。GFM 解析与链接检查不证明所有语言命题，也没有逐项验证外部网页的长期可用性。

同一次只读检查重新提取十四份文件，逐项匹配最终 JSON 的源码和正文 SHA-256，并核对执行器及复用辅助文件摘要。`protected_binding` 按精确起点逐字节确认 42 个受保护文件不变：v1 的 13 篇 G、10 篇 FM、两份正式 PDF，以及 G0～G2 正文、记录、执行器和复用进程辅助文件。没有重跑旧实验或把旧记录重新绑定到 G3。

旧检查器仍报告 v1 的 16 项代码／图形分页风险；它不覆盖新稿分页。另以超过 40 行或超过 100 字符的代码行为新稿复核信号，得到 `value-batch.hpp` 61 行、`copy-failure.cpp` 42 行、`return-observation.cpp` 42 行，最长行分别为 81、78、88 字符。保留完整文件，将续页处理留给未来出版层，不以拆坏源码消除提示。没有执行 PDF 构建、渲染或视觉验收。

`git diff --check` 无错误；差异只涉及两份新正文、验证说明、执行器、结果 JSON 和两个 README。FM、v1 正文、已冻结 G0～G2、出版系统和历史制品均未修改。G4 未启动。

## 7 精读接受与文字收口

2026-10-01，读者对 `852545e45475aa14cef876936a29136927978522` 的两单元正文、验证说明及差异完成精读，接受讲解深度、中文论述、章节组织和证据整合，未发现阻断性技术问题。本次按意见完成两处精度校准：第一单元 §5 改为要求定义移动后源对象的后置状态，避免把“可用”误读为仍保留原值；第二单元 §6 区分 glvalue 确定对象或函数身份与 xvalue 所表示的对象。此外，将编译选项说明校准为“禁用可选的复制/移动省略”，不改变命令或判据。

G3 Content v2 据此登记为 **ACCEPTED / FROZEN**。冻结的是文字校准后的正文，摘要如下；历史 JSON 仍记录 `852545e` 的正文摘要，不追写成当前字节，也不把精读接受称为重新执行。

| 当前冻结正文 | SHA-256 |
| --- | --- |
| `g03-value-copy-and-move.md` | `17252f214ffe89e13c1915ee53a37d1d7b1ae339b5ee771ada4f587a72fa14c5` |
| `g03-expressions-and-return.md` | `4b86c508377a2651e57fd49a7615cb8d03f33e0a21de05887807a7d3ff7108b1` |

本次用临时只读 Python 检查重新提取十四份文件，其 SHA-256 全部匹配历史 JSON；另用 `git show 852545e:<path>` 核对旧正文摘要仍匹配该 JSON。两单元共 17 个完整围栏块、四个迁移问题／答案区域逐字节未变，执行器、进程辅助文件和结果 JSON 也未变。调用执行器的只读 `protected_binding()`，确认原先登记的 42 个受保护文件保持原字节；没有调用实验入口或判据自检。

文档检查命令仍为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 c++/learning/check_docs.py`。本次最终检查解析 53 份 Markdown、核对 882 处本地链接，错误为 0；原有 16 项 v1 代码／图形分页风险继续保留。初次检查曾在本节尚未追加时报告新导航缺少目标锚点，补齐本节后重新检查。`git diff --check` 无错误，差异限定为两份 G3 正文、本说明及两个 README，共五份 Markdown。

本次 C++ 编译与运行、负例诊断、构造观察、ASan/UBSan、错误变体及判据自检均为 **NOT RUN**；§3 的 32／4／6／2／18／8 项及 13 项自检仍是 `852545e` 的历史本地证据。性能、并发、跨平台等未验证边界不变。G4 只登记后续方向，未启动；PDF 未构建，出版系统及已发布制品未修改。
