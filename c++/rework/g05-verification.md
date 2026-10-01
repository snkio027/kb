# G5 新稿的实验与验证边界

本记录对应[调用表达式与类型推导](g05-call-and-deduction.md)、[约束、重载与实例化](g05-constraints-and-instantiation.md)、[常量求值与生成代码](g05-constant-evaluation-and-codegen.md)。批次起点为 `c4c74736de7dcfa6cc286f32866aa593384f3744`。G5 Content v2 为 **待精读审核，尚未冻结**；工具输出不能代替讲解深度、中文质量和章节组织的实际阅读接受。

## 1 输入与复现方式

[执行器](verify_g5.py)只从三篇新稿提取二十五份文件：四个头文件、十个单文件正常程序、八个编译负例，以及一个多文件实验的提供方、正常客户端和缺定义客户端。源码来自带文件名的完整围栏块，没有另存一份可能漂移的手工测试副本。历史 G0～G4 及 v1 实验不进入本次执行。

从仓库根目录运行，结果路径必须尚不存在，不覆盖历史 JSON：

```sh
python3 c++/rework/verify_g5.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --nm /opt/homebrew/opt/llvm/bin/llvm-nm \
  --output /tmp/g5-rework-results-new.json
```

[g05-results.json](g05-results.json)绑定正文、提取源码、执行器和复用进程辅助文件的 SHA-256，记录工具链、完整命令、stdout、stderr、退出码、超时状态及临时目录。复用 `c++/learning/verify_g.py` 的进程、超时和取消辅助函数，不修改它，不调用其旧实验入口。编译、链接和运行分别记录；缺定义客户端从不执行。

## 2 工具链与判据

| 项目 | 本机身份或选项 |
| --- | --- |
| 平台 | macOS 26.7，arm64；Python 3.12.14 |
| 编译器 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++，`_LIBCPP_VERSION=220106` |
| 编译器 B | Homebrew Clang 23.1.2；libc++，`_LIBCPP_VERSION=230102` |
| 语言与诊断 | `-std=c++23 -Wall -Wextra -Wpedantic`；两者 `__cplusplus=202302L` |
| 普通与多文件构建 | 分别 `-O0 -g`、`-O2`；未开启 LTO |
| 编译负例 | `-O0 -c`，不进入链接阶段 |
| 工件观察 | Homebrew LLVM 23.1.2 的 `llvm-nm --demangle`；记录三个对象的字节数及摘要 |
| ASan/UBSan 正例 | `-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer` |
| 错误变体 | `-O0 -g`，先编译成功，再核对指定退出码 |

正常程序必须通过自身 static_assert、成功编译和链接，运行退出码为 0、stdout 精确匹配、stderr 为空。返回值、范围比较和重载路径负责各自命题；不能以输出一行“成功”替代内部检查。正常构建的编译诊断也保留并人工检查，不把警告藏掉。

编译负例要求非超时、正失败退出码及目标诊断组合。八类分别是同一 T 推导冲突、固定右值引用绑定失败、ReadingInput 不满足、所需函数体出现缺成员、约束重载歧义、非法常量预设、运行数据进入立即调用，以及普通 if 中非法的 size 调用。函数体负例保留先通过 DeclaredCall 的 static_assert，使“声明可调用”和“定义成立”的区别直接出现在同一源码里。

链接负例只有在三个翻译单元均编译成功后才执行，要求诊断同时指出未定义引用与 `count_positive<float>`；缺头文件、语法错误、崩溃或超时不能替代。工件观察仅要求 nm 能读取对象，不以固定地址、字母、符号数量或对象大小判定通过；实际供给关系还由独立编译、链接、运行结果及原始符号输出共同核对。

14 项局部判据自检覆盖正确输出、错误输出、stderr、目标退出码、崩溃、超时、目标诊断与错误特化诊断。它们是 Python 判据检查，不是额外 C++ 实验，也不是对整个执行框架的证明。

sanitizer 环境固定为 `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0` 与 `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=0`。每套工具链先做合法插桩探测，不可用记 SKIP，不算通过。本批没有 ASan 阳性对照，也没有把 G1 的旧阳性对照继承为新证据；泄漏检测与外部符号化关闭。插桩只覆盖十个单文件正常程序，不覆盖多文件链接实验。

## 3 分项结果

| 证据类型 | 最终本地结果 | 结论边界 |
| --- | --- | --- |
| 正常编译与运行 | 十个程序 × O0/O2 × 两套编译器，40 项 PASS | 静态类型断言与当前运行判据成立 |
| 目标编译负例 | 八个负例 × 两套编译器，16 项 PASS | 得到所声明的目标诊断，不是任意编译失败 |
| 多文件正常链接与运行 | O0/O2 × 两套编译器，4 项 PASS | int 定义由提供方供给并产生正确计数 |
| 缺定义链接负例 | O0/O2 × 两套编译器，4 项 PASS | 在分别编译成功后拒绝缺失 float 定义的程序 |
| 工件观察 | O0/O2 × 两套编译器，4 组 OBSERVED | 记录各组 3 个对象及 nm 输出，不是性能结果 |
| ASan/UBSan 正例 | 十个程序 × 两套编译器，20 项 CLEAN_OBSERVED | 这些执行未报告错误，不证明所有泛型实例安全 |
| 错误变体 | 两个变体 × 两套编译器，4 项 REJECTED_AS_EXPECTED | 编译成功后由运行判据拒绝特定逻辑错误 |
| 判据自检 | 14 项符合预期 | 局部判据，不是新增 C++ 实验 |

两套编译器都属于 Clang 家族，标准库都为 libc++，不是两种标准库或跨操作系统验证。两个 sanitizer 探测可用，SKIP 为 0。正常编译与运行没有警告或 stderr；目标负例的诊断是保留的预期结果。最终状态为 `COMPLETE`，这是本地执行记录，不是 GitHub CI。

四组符号输出中，正常客户端包含 int 特化的未解析引用，缺定义客户端包含 float 特化的未解析引用，提供方包含 int 定义。这里是对实际输出的观察，不固定它们在未来工具链中的拼写及字母。O0 带调试信息、O2 不带，二者对象大小尤其不能直接解读为单纯优化收益；没有测编译耗时、运行耗时或机器指令成本。

初稿先在 `/tmp/g5-first-results-20261002.json` 验证，随后修正引用定位、行内模板类型标记并补齐调用推导说明，再对最终正文重新提取和执行。本表仅统计最终结果，不累加初稿运行，不把初稿正文摘要当作最终摘要。

## 4 错误变体与未覆盖边界

| 变体 | 故意破坏的语义 | 预期拒绝 |
| --- | --- | --- |
| `move-left-input` | 包装层用 move 代替 forward，改变左值调用方的绑定选择 | `forwarding.cpp` 返回 1 |
| `omit-snapshot-sort` | 快照只复制，不执行约定的按编号排序 | `snapshot.cpp` 返回 1 |

两种变体仅在新临时目录生成，正文保留正确实现。每个变体记录替换位置、替换文本、全部源摘要与命令；要求编译成功后以指定非零码、空 stdout/stderr 拒绝。编译失败或 sanitizer 报警不是成功捕获这两种错误的替代条件。

本批没有穷举 cv/ref 组合、花括号列表、重载集合、代理引用、破坏性输入、所有非类型模板参数、类模板实参推导、ADL 或两阶段查找。非模板 requires 失败、auto 返回引发的实例化副作用等边界按标准说明，未各自建立实验矩阵。member-instantiation 的正常运行没有调用 unavailable，也不被记为该成员可用。

sorted_snapshot 未注入分配、迭代或构造失败；动态用例覆盖 vector、list、filter_view、临时及空输入，没有运行单遍流或代理引用来源，更未验证一般单遍来源的回滚。没有测试并发修改输入。count_elements 的运行输入很小，不覆盖自定义巨大范围的计数溢出。常量求值不使用非法内存访问作实验；没有执行故意的未定义行为。

**性能、profile、汇编分析、并发动态检测与 TSan：NOT RUN。** Linux、Windows、libstdc++、Zig、Rust 均未执行。**PDF：NOT BUILT / NOT VALIDATED。** 编译诊断、符号观察或读者接受都不扩大这些结论；本批不启动 G6。

## 5 文档与保护范围检查

2026-10-02 实际运行 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 c++/learning/check_docs.py`，解析 61 份 Markdown、核对 928 处本地链接，错误为 0。检查器继续报告 v1 的 16 项代码／图形分页风险，没有把它们当作本次新稿缺陷；本地链接检查不核验全部外部 URL。

临时只读 Python 检查用 Pandoc GFM AST 核对二十一份重编 Markdown 的单一 H1、连续 H1～H3 层级、标题锚点唯一、围栏闭合及无 HTML 折叠依赖。四份 G5 Markdown 没有原始 HTML 节点，模板类型名没有被误解为标签；三个正文单元分别保留六道迁移问题与六份推理答案。以代码块超过 40 行或单行超过 100 字符为源稿分页复核信号，本次 G5 未触发；这不等于 PDF 分页或视觉验收。

同次只读检查调用 `extract()`，重算三篇正文及二十五份源码摘要，与最终 JSON 全部匹配；执行器和辅助文件摘要也匹配。进一步读取最终临时目录中的十二个被观察对象，逐项核对字节数与 SHA-256；正常构建、运行的原始诊断为空。初稿与最终稿提取的 C++ 字节及执行器相同，但正文摘要不同，因此保留两次结果身份，不追写初稿 JSON。

调用只读 `protected_binding()`，确认起点登记的 53 个受保护文件逐字节不变：G0～G4 新稿、验证说明、执行器及历史 JSON，v1 的 13 篇 G、10 篇 FM，两份正式 PDF，以及进程辅助文件。仓库差异限定为三篇 G5 正文、验证说明、执行器、结果 JSON 和两个 README，共八个文件；`git diff --check` 无错误。没有修改出版系统、历史制品或 G0～G4 技术基线，也没有将这次本地检查记为外部精读通过。
