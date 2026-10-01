# G6 新稿的实验与验证边界

本批从 `baeeadf58a75f68555c587f317f382f49b0ba2fc` 启动，正文为[布局与访问成本](g06-layout-and-access.md)、[分配策略与性能测量](g06-allocation-and-measurement.md)。G6 Content v2 当前为 **PENDING READER REVIEW / NOT FROZEN**。编译运行、生成物观察与性能记录不能替代精读接受，也不沿用 v1 的接受状态。

## 1 输入与复现

[执行器](verify_g6.py)从两篇正文的八个具名 C++ 围栏块提取八份文件：两个头文件、一个扫描内核和五个 main 程序。五个实验分别是布局观察、完整表示／扫描合同、容量复用、arena 生命周期和成对扫描计时。没有另存可能漂移的手写 C++ 副本；[g06-results.json](g06-results.json)记录正文、提取文件、执行器、复用进程辅助函数以及实际可执行文件的 SHA-256。

从仓库根目录运行，目标结果文件必须尚不存在：

```sh
python3 c++/rework/verify_g6.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --nm /opt/homebrew/opt/llvm/bin/llvm-nm \
  --output /tmp/g6-rework-results-new.json
```

本批实际使用的 Python 为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。最终运行将 `--output` 指向当时尚不存在的 `c++/rework/g06-results.json`。执行器沿用 `c++/learning/verify_g.py` 的进程、超时及取消辅助函数，不改变该文件、不运行其旧实验；输出完整命令、stdout、stderr、退出码及 timeout 字段。取消或异常不登记 COMPLETE。

初稿在 `/tmp/g6-first-results-20261002.json` 执行；补入反向性能观察后又作了一次中间执行，结果保存在 `/tmp/g6-pre-final-results-20261002.json`。最后补明生成器对 int 范围的静态要求，重新提取全部文件并运行。本记录只统计最终提交的 JSON，不累加中间批次，也不把中间正文摘要冒充最终输入。

## 2 平台与配置

| 项目 | 本次身份或限制 |
| --- | --- |
| 主机 | Apple M5；macOS 26.7（25G229），arm64；Python 3.12.14 |
| 编译器 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++ `_LIBCPP_VERSION=220106` |
| 编译器 B | Homebrew Clang 23.1.2；libc++ `_LIBCPP_VERSION=230102` |
| 语言与诊断 | `-std=c++23 -Wall -Wextra -Wpedantic`；两者 `__cplusplus=202302L` |
| 正常运行 | `-O0 -g` 与 `-O2`，不启用 LTO |
| 性能构建 | `-O3 -fno-lto`；scan／benchmark 分别编译再链接；无 fast-math、sanitizer |
| 生成物 | LLVM 23.1.2 的 `llvm-nm --demangle`；内核优化备注、完整 `-S` 汇编、对象及二进制摘要 |
| ASan/UBSan | `-O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer` |
| 系统控制 | 未绑定核心、未锁频、未隔离后台负载、未证明热稳态 |

执行器内的 `sysctl -n machdep.cpu.brand_string` 被沙箱拒绝，原退出码 1 和 stderr 原样保留。另一次获准的只读查询以相同命令返回 `Apple M5`，`/usr/bin/sw_vers` 返回上述系统版本；CPU 型号来自该独立查询，不把 JSON 中失败的查询改写为成功。没有由芯片名称推断缓存尺寸、行宽、核心驻留或运行频率。

两套工具链均为 Clang／libc++，不是 GCC、两种标准库或跨平台验证。执行环境变量固定 ASan 失败行为并禁用 LeakSanitizer，详见 JSON；这不是泄漏全面检查。所有记录都是本地证据，不声明 GitHub CI。

## 3 四类证据分别报告

### 3.1 文档结构与来源

两篇正文仅用 H1～H3，每篇六道迁移题与普通章节中的参考推理；重要结论不藏在 HTML 折叠块。具名 C++ 块必须与提取集完全对应，任何未绑定块、重名文件或文件集变化都会拒绝执行。

Markdown 检查覆盖 GFM 解析、本地文件与锚点链接；新稿另作 H1～H3、标题连续性、重复锚点、围栏、details 和 Gate 检查。它们不证明技术论述正确、不验证在线 URL，更不是 PDF 分页验收。具体检查结果登记于本记录末节。

执行前后均将 59 份保护文件与 Base 的 Git 字节比较：G0～G5 新稿、验证记录和执行器，复用进程辅助文件，v1 的十三章、FM 十章及两本正式 PDF。结果均为 UNCHANGED。提交范围再排除其他历史记录、出版实现与 dist 的改动；不把有限保护清单声称为重算仓库所有文件。

### 3.2 C++ 编译、运行与判据反例

| 检查 | 最终结果 | 所支持的命题 |
| --- | --- | --- |
| 三个正确性程序 × O0/O2 × 两工具链 | 12 项 PASS | 表示／求和、批次复用及资源清理符合程序内判据 |
| 三个错误变体 × 两工具链 | 6 项 REJECTED_AS_EXPECTED | 编译成功后返回目标失败码；不是编译失败或崩溃 |
| 执行器局部判据自检 | 14 项符合预期 | 能拒绝计时缺行、重复、错误校验和、错误 pass 数、零区间、类型错误等 |
| 专门的编译负例矩阵 | NOT RUN | G6 没有为了复用 G5 形态增加模板诊断实验 |

正常程序要求退出码 0、stderr 为空以及目标文本／JSON 满足判据。布局和资源数字不固定为某个 ABI 值或容量增长序列；计数器观察不称为性能加速。实际正常编译没有警告，性能构建的优化备注属于有意保留的诊断。

三个变体分别是：SoA 循环遗漏最后一个值（返回 3），转换时把编号加一（返回 2），复用时遗漏 clear（返回 2）。编号变体不会改变求和结果，所以能够专门检查“仅有正确 checksum 仍不足以证明完整记录对应”。这些错误只存在于临时目录，不修改正文中的正确实现。

### 3.3 布局、资源、生成物与性能观察

布局观察为四项 OBSERVED（两种优化 × 两工具链），本机均看到 Reading 大小 12、对齐 4、三个偏移 0/4/8。资源实验以 O0/O2 分别在两工具链运行：每批重建请求 16 次、累计 98,304 字节；容量复用请求 1 次、累计 6,144 字节；两者包装层峰值均为 6,144 字节。arena 经 upstream 保留 2,080 字节直至 release，16 个 Entry 已先行析构；这些块大小是本机观察，不是标准规定。

两个工具链各保留一组代码生成观察。AoS 的备注为四次交错处理，并说明向量化在成本模型下无收益；SoA 也没有获得 SIMD 向量化备注。汇编中 AoS 使用多个部分和及 `csel`，SoA 保留有效性条件跳转。两组 benchmark 对象中可见对外部扫描函数的未定义引用，scan 对象提供定义；没有把循环展开／交错解释成 SIMD，也没有把静态汇编分析称为 CPU sampling profile。

性能为 **6 个独立进程、504 条原始计时记录，均为 OBSERVED**：每工具链 3 进程 × 3 规模 × 2 顺序 × 7 对 × 2 布局。记录完整矩阵、passes、checksum 和正的 elapsed time，分析按单次扫描时间计算每进程七次观察的 min／median／max／Q1／Q3。没有速度阈值，也没有把 504 条记录算成 504 个独立正确性实验。

每个进程顺序运行；转换、分配和输出不计入区间，循环及外部调用计入。预热不等于工作集全部驻留，交替先后不等于消除频率／调度偏差。正文保留 SoA 未普遍获胜的结果，以实际生成代码限制归因；没有对 branch miss、cache miss 或 DRAM 流量作数值结论。

以下仅摘录最终运行中各工具链第一个进程、1,048,576 条记录的七次单扫描时间中位数，单位 μs；全部三个进程的原始值和分位值留在 JSON，不合并成总体置信区间：

| 工具链 | 记录顺序 | AoS | SoA |
| --- | --- | --- | --- |
| Apple Clang 21 | 成段 | 268.40 | 394.98 |
| Apple Clang 21 | 打乱 | 190.29 | 2,188.42 |
| Homebrew Clang 23 | 成段 | 305.08 | 425.69 |
| Homebrew Clang 23 | 打乱 | 189.85 | 2,277.10 |

这些数字用于读懂本次反向观察，不是性能门槛或未来主机的预期值。布局、条件处理和编译器成本选择共同变化，不能把表中差值全部分配给一个硬件原因。即使后续数字或排名改变，只要记录与语义判据完整，仍应如实保留。

### 3.4 动态安全检测与并发边界

三个正确性程序 × 两工具链共 **6 项 ASan/UBSan CLEAN_OBSERVED**。两个运行时探测均可用，实验 SKIP 为 0；没有新增 ASan 阳性对照。没有诊断只说明这些路径未被本次仪器报告，不证明全部对象生命、资源传播或访问情况安全。

TSan、并发 stress、完整同步／停机协议 **NOT RUN**。本章解释伪共享与数据竞争的区别，但未执行并发实验；不得将单线程 sanitizer 结果登记为并发正确性。

## 4 没有完成的验证

CPU sampling、硬件计数器、动态 branch／cache／TLB 归因、RSS／系统分配追踪、真实流量、端到端耗时、尾延迟、转换成本和 allocator 耗时均未测。PMR 的有界 `bad_alloc` 是真实 null upstream 拒绝扩展，不是操作系统 OOM，也不是磁盘／网络故障注入。

未比较 GCC、libstdc++、Linux、Windows、不同 CPU 或编译目标；未测 LTO、冷启动、异构核心驻留及稳定频率条件。程序使用有限输入，不是全部整数范围、分配失败序列或所有 allocator 传播操作的穷举。

本批仅完成 G6 Content v2 候选，不启动 G7，不修改已冻结章节或历史结果，不构建 PDF，不改变出版系统或正式发布载荷。理论模型与中文阅读质量仍等待用户精读反馈。

## 5 本批检查记录

2026-10-02 在本机执行以下检查。该节不参与两篇正文实验输入的摘要，也不回写任何历史 JSON。

| 命令／检查 | 实际结果 |
| --- | --- |
| `python3 c++/learning/check_docs.py`（使用 §1 的实际 Python 路径） | 64 份 Markdown，946 处本地链接，errors 为空；保留 16 个旧 v1 分页风险信号 |
| 临时只读 `python3 -` + `pandoc -f gfm -t json` | 24 份 rework Markdown 的 H1～H3／层级连续／标题锚点唯一／围栏／无 details 检查通过；G6 两篇各 6 题及 6 答 |
| 临时只读 `python3 -` 导入 `verify_g6.py`，调用 `extract()`、`protected_binding()` 并比对结果 JSON | 两篇正文、八份源码、runner、helper 摘要 MATCH；59 份保护文件前后 UNCHANGED |
| 同一临时检查读取 `git diff --name-only` 与 `git ls-files --others --exclude-standard` | 严格为本批 7 文件，无范围外文件 |
| `git diff --check` | 通过；提交前再次检查暂存差异 |
| `git ls-remote --heads origin main` | 推送前远端仍为 Base `baeeadf58a75f68555c587f317f382f49b0ba2fc` |

临时检查是本地一次性审计，不登记成新增常驻测试框架或 CI。正文 SHA-256 为：

```text
g06-layout-and-access.md
3247c87ffc24dcd2c478033c4238e5d68700dc876388ad6efe7c33bc43ed67ae

g06-allocation-and-measurement.md
99c040faf1215c4a99c21b748889d6c0d95ff2d354c45a4777fba51e00584393
```

新稿另检查了全部八个代码块的长度与显示宽度：readings.hpp 69 行、reuse.cpp 56 行、arena.cpp 55 行、benchmark.cpp 52 行，需未来出版层处理续页；benchmark 最宽一行为 96 显示列。保留完整实验，不为尚未启动的 PDF 拆坏源码。这些是源稿分页风险登记，不是已发生的 PDF 裁切，也不宣称 Visual Profile 已对新稿验收。

内容规则以固定的 C++23/N4950 为依据，系统机制引用 Arm、LLVM、Google Benchmark 与 Linux 内核的原始技术资料；在线页面不等于本地不可变归档，结构检查不把它们计入本地链接通过数。缓存层级与依赖载入资料只用于一般机制，不作为 Apple M5 的规格证据。
