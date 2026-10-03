# G8 新稿的二进制合同与验证边界

本批从 `e035f594a19e3e3c2674cfbee1f6d15bf88e0ac4` 启动，形成[二进制合同](g08-binary-contracts.md)、[C 边界与资源合同](g08-c-boundary-and-ownership.md)、[动态加载与兼容演进](g08-loading-and-evolution.md)三个单元。按 Editorial Profile v1.1 保留可独立回查的理论、连续案例和专业英文术语。当前 **PENDING READER REVIEW / NOT FROZEN**；测试结果不自动接受中文论述或整个 ABI 模型。

## 1 输入与复现

[执行器](verify_g8.py)从三篇正文提取 **15 份具名 C／C++／头文件**，拒绝未绑定代码块、重名及文件集合漂移。正常实现、consumer 和 host 只有这一份正文来源；工具身份探针及 sanitizer 安全探针是 harness 输入，单独保存在 [原始执行记录](g08-results.json)的 `harness_sources` 中。

从仓库根目录运行，输出文件必须尚不存在：

```sh
python3 c++/rework/verify_g8.py \
  --toolchain /usr/bin/clang /usr/bin/clang++ \
  --toolchain /opt/homebrew/opt/llvm/bin/clang /opt/homebrew/opt/llvm/bin/clang++ \
  --nm /opt/homebrew/opt/llvm/bin/llvm-nm \
  --output /tmp/g8-rework-results-new.json
```

执行器复用未修改的 `c++/learning/verify_g.py` 进程辅助函数，不运行它的历史实验；新源码和工件仅写入新临时目录，另排他创建指定 JSON。单个子进程上限 60 秒，超时不算预期拒绝。它运行经阅读的本地代码，不是恶意代码沙箱，也不安装或移除系统库。当前主动限制 macOS arm64，不把未实现平台路径算作通过。

JSON 绑定三篇正文、提取源码、runner、helper、公共头文件、host 和编译输出的 SHA-256，保留每条命令、cwd、返回码、stdout、stderr 与 timeout。完整 assembly 也保存在观察项中。记录可追溯不等于跨机器字节级可复现；绝对临时路径不被当作可长期下载的交付工件。

本批先做两次临时矩阵：首轮确认完整路线可用，第二轮加入同 engine 连续批次与双语言公开布局对照，并将专用于布局观察的 private 字段标明 maybe_unused。最后补齐 harness 源码记录、取消终态和全部生成工件的结束时摘要复核，再用上面命令将 `--output` 改为 `c++/rework/g08-results.json`，完整重跑最终矩阵。本节以下只统计这最后一次，不累加两次中间运行。

## 2 理论与证据分别支持什么

| 理论对象 | 本批证据 | 不能由此推出 |
| --- | --- | --- |
| language linkage 与 symbol | 分离 C/C++ 对象、目标链接诊断、原始与 demangled 名称 | 任意签名错误均由 linker 检测 |
| calling convention／lowering | caller 和 callee 的 O0/O2 汇编、结果值检查 | 寄存器或指令在所有目标上固定；sret 等同 RVO |
| layout 与 ABI surface | 合法不同类型的大小／对齐／偏移；公开头文件分别按 C11/C++23 编译对照 | 不兼容对象可强转调用；表示等同持久格式 |
| opaque handle／failure contract | 完整输出、连续批次、错误状态、回调计数与受控 throw | 任意坏指针可恢复、所有分配故障已注入 |
| provider 替换 | 先冻结 host 字节，再消费两种内部表示 | 任意历史 SDK 客户、不同平台或运行时均兼容 |
| module lifetime | 同步调用结束、销毁 engine 后 dlclose 的控制路径 | 并发／异步卸载正确，dlclose 必然立即解除映射 |

语言规则依据固定为 N4950 的 language linkage、ODR 和异常说明；调用约定区分 AAPCS64 2025Q1、Apple 平台补充和本机工件。Itanium C++ ABI 是具体实现资料，不是通用 C++ 标准。Apple archive 文档用于解释本次 dyld、dlopen／dlsym／dlclose 路线，不推定覆盖未来所有系统版本。正文中的兼容关系记法、资源域与 quiescence 推导属于工程分析，不声称经过形式验证器检查。

## 3 平台与配置

| 项目 | 本次身份 |
| --- | --- |
| 主机 | macOS 26.7，arm64；Python 3.9.6 |
| 工具链 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++ `220106` |
| 工具链 B | Homebrew Clang 23.1.2；libc++ `230102` |
| 语言模式 | provider／C++ probe 使用 C++23，`__cplusplus=202302L`；C consumer／host 使用 C11 |
| 普通检查 | O0／O2；显式分离编译；没有 LTO |
| 共享库 | Mach-O；默认隐藏内部符号，显式公开 re_*；dyld 与本机运行时 |
| 工件工具 | LLVM nm 23.1.2、系统 otool、macOS SDK 27.0；完整路径保留在原始命令记录 |
| ASan/UBSan | `-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer` |

sanitizer 环境记录为 `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=0:exitcode=86:symbolize=0` 与 `UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=0`。安全探针只说明运行通道可用，不是阳性检出对照；本批 **ASan 阳性对照 NOT RUN，LeakSanitizer DISABLED**。C consumer 和 C++ provider 都插桩，但插桩实验仅覆盖直接链接的合同与受控失败，不冒充插件并发卸载检测。

两套编译器属于同一主机上的 Clang／libc++ 路线，不是 GCC／libstdc++ 或跨操作系统矩阵。实验未混合两套工具链的任意 host／provider 组合；各套内部独立验证。

最终执行中成功命令的 stderr 均为空，未出现编译警告；预期链接与加载拒绝的诊断另存，不计作成功路径噪声。首轮 SDK 查询曾有本机 xcodebuild cache／event-stream 警告，布局观察也曾有 unused-private-field 警告；没有将这些中间输出隐称为最终运行结果。

## 4 实际结果

最终执行器返回 0，记录为 **COMPLETED**，无 FAIL 或 SKIP。下表按命题分组，不将同一源码的不同构建配置称为不同正文实验。

| 类别 | 结果 | 判据 |
| --- | --- | --- |
| 分离编译调用与直接 C consumer | 8 项 PASS（2 类 × O0/O2 × 2 工具链） | 编译／链接成功，完整值及失败合同成立，指定输出与退出 0 |
| 链接负例 | 4 项 PASS（O0/O2 × 2 工具链） | 对象先编译成功，再获得 native_sum 未解析诊断 |
| 受控 create／prepare 失败 | 4 项 PASS（2 类 × 2 工具链） | RE_NOMEM／RE_INTERNAL、无交付 owner 或无部分输出 |
| 保留 host 的 provider 替换 | 4 项 PASS（2 实现 × 2 工具链） | 两种实现满足相同 contract-suite；2 份 host 的前后摘要各自相同 |
| 未知版本／错误表大小 | 8 项 PASS（2 类 × 2 实现 × 2 工具链） | provider 拒绝且表未写入；host 0 表示拒绝合同正确 |
| 缺失库／缺失入口 | 4 项 PASS（2 类 × 2 工具链） | host 明确返回 10／11，匹配目标诊断；不是 crash |
| 错误实现变体 | 8 项 REJECTED_AS_EXPECTED（4 变体 × 2 工具链） | 编译成功，指定业务失败码拒绝 |
| ASan/UBSan | 6 项 CLEAN_OBSERVED（正常、create 失败、prepare 失败 × 2 工具链） | 同时满足原合同且未观察到工具诊断；2 个运行通道探针另计 |
| 布局／符号／汇编／依赖 | 12 组 OBSERVED | 4 组符号／lowering、2 组类型布局、2 组 C/C++ 公开布局 MATCH、4 组产品导出／依赖 |
| 性能／并发动态检测 | **NOT RUN** | 不把工件大小、成功加载或同步销毁扩张为性能／线程结论 |

四个错误变体分别接受未知配置版本、忽略 capacity、遗漏 written 更新，以及接受未知 API version。相应拒绝码为 2、12、14、21。源码只在临时目录替换，并记录变体摘要；不把原有错误变体的成功拒绝称作全部缺陷都可发现。

执行器的 12 项局部 oracle 自检全部符合预期，涵盖错误输出、stderr、超时、crash、错误退出码、错误 loader 诊断与无关链接失败。这些是判据自检，不算正文 C/C++ 实验。专门的编译期拒绝实验 **NOT RUN**；本章反例重点在分离编译后的链接、加载和运行合同。

准备失败注入发生在第一条临时结果已产生、caller 输出尚未提交时。create 注入在分配表达式前主动抛 bad_alloc，不是物理内存耗尽。capacity 负例的实际数组仍有三个合法元素，故错误实现写第三项会违反声明容量，但不依赖内存越界来获得失败码。

## 5 工件观察与人工核对

本机 abi_make 的 caller 在调用前把结果地址放入 x8，callee 通过保存的地址写三项 int64_t。abi_scale 的整型输入和 double 分别使用 w0 与 d0，本次返回 double 使用 d0。这是对具体 assembly 的人工解释，程序只自动检验返回值与工件提取，不声称汇编文本匹配已经证明全部 lowering。

独立布局观察中，ReadingV1 为 size 8／align 4，ReadingV2 为 size 16／align 8；OwnerV1 为 size 4／align 4，OwnerV2 为 size 16／align 8。它们说明本机尾部字段与 private 表示变化可以改变步长和存储要求，不固定成语言常量。公开 C／C++ 记录另由 G8-D2 比较全部列出的 size、alignment 与 offset。

两份 provider 的 re_* 产品导出应为 create、destroy、process、get_api。这个检查只约束本产品入口，不宣称所有 runtime 导出集合完全相同。旧 host 在实验期间不重编译，分别运行于两个单 provider 进程；不是同时混装两个实现，也没有跨版本转移 engine。

## 6 结构检查、保护范围与未验证事项

G0～G7 的 18 篇冻结正文、全部历史实验与 JSON、Editorial Profile、v1、FM、出版系统及已发布 PDF 保持 Base 原字节。执行器在前后比较 Base 的 **1,172 份已跟踪文件**，仅排除需要同步的两份导航 README；新 G8 文件另由提取摘要绑定。这个检查不声称核验机器上所有未跟踪文件。

本批实际检查如下，均为本地记录，不声称 GitHub CI：

| 命令／检查 | 实际结果 |
| --- | --- |
| §1 最终执行器命令，输出为 `c++/rework/g08-results.json` | 返回 0，COMPLETED；分项结果见 §4 |
| `python3 c++/learning/check_docs.py` | 72 份 Markdown／981 处本地链接，0 errors；保留 16 项历史 v1 分页风险 |
| 临时只读 `python3 -` 调用既有 `structure()` 与 Pandoc | 新增四份 Markdown 的 H1～H3、锚点、围栏和无 details 检查通过；三篇正文各 6 题／6 答 |
| 临时只读 `python3 -` 导入 runner，重算 `extract()`、`selftests()`、`protected_binding()` | 3 篇正文、15 份源码、runner／helper 摘要 MATCH；12 项自检成立；1,172 份保护文件 UNCHANGED |
| 同一检查重读本地生成文件 | 106 份编译工件（含汇编）、8 份变体源码摘要 MATCH；不是 106 个实验；host 未变 |
| 同一检查核对 Git diff 与未跟踪文件列表 | 范围严格为本批 8 个文件：3 正文、1 验证说明、1 runner、1 JSON、2 README |
| `git diff --check` | 通过 |

检查只验证解析、层级、定位与文件对应，不证明语言规则已被穷举，也不代表 PDF 分页已验收。每篇六道迁移题与六项推理答案保持普通章节，未用 HTML 折叠隐藏。

最终三篇正文 SHA-256（同时保存在 JSON 中）：

```text
g08-binary-contracts.md
3b05e280fa2c8095426ec7012f718929e1f706b4790240d970a038b45cc2d2d4

g08-c-boundary-and-ownership.md
0ecbb2e4e03cf1009b154fbb9143d7831e1a44e0fb30d95bb7bcfe7acad22d81

g08-loading-and-evolution.md
17bf60250198aa590de332a7a47b55a2fbe8707b775af34dc2720283336eb008
```

未验证：任意不匹配 ABI 的执行、所有调用约定分类、完整继承／RTTI／异常跨库矩阵、真实 OOM、无效指针隔离、泄漏检测、异步回调注销、并发卸载、完整多代前缀扩展、跨工具链混装、Linux／Windows／Rust／Zig、性能与实时保证。取消路径复用既有进程组清理并保留 CANCELLED，但本批没有主动中断实验来声称取消注入已测。

**Content v2 PDF: NOT BUILT / NOT VALIDATED。** G8 等待集中精读；G0～G7 不重开，G9 不启动，既有出版制品不改。
