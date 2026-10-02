# G7 新稿的协议论证与实验边界

本批从 `c1e8ab7a33f450ef5663085ecdd00ce41ce1692a` 启动，对应[共享状态、条件等待与退出协议](g07-shared-state-and-shutdown.md)和[原子操作、数据发布与槽位复用](g07-atomics-and-publication.md)。两单元按 Content v2 的定义、关系、规则和边界组织，当前为 **PENDING READER REVIEW / NOT FROZEN**。人工协议论证、普通运行、有限 stress、错误变体和动态竞争检测分别登记，不汇总为“并发已经证明正确”。

## 1 输入、命令与复现

[执行器](verify_g7.py)只从正文七个具名 C++ 围栏块提取源码：一个通道头文件、五个正常实验程序，以及一个仅用于 TSan 的危险对照。正文是这些文件的唯一维护入口。任何未绑定 C++ 块、重名或文件集变化都会拒绝运行；工具身份程序和安全探针属于验证设施，完整源码另存于 [g07-results.json](g07-results.json)。

从仓库根目录运行，输出路径必须尚不存在：

```sh
python3 c++/rework/verify_g7.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --output /tmp/g7-rework-results-new.json
```

本批实际使用 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`，最终运行的 `--output` 为 `/tmp/kb-g7-final-results.json`，完成后原字节移入 `c++/rework/g07-results.json`。复用 `c++/learning/verify_g.py` 的进程超时及取消辅助函数，未修改它，也没有运行它的旧实验。单个编译／执行最多 45 秒，超时不算通过；失败与取消保留不同终态。

首轮结果为 `/tmp/kb-g7-initial-results.json`，完成全部同类实验。校准两处理论措辞并增加二进制摘要后进行了第二次运行，该中间结果移存 `/tmp/kb-g7-pre-selfcheck-results.json`。自查又将 stress 主线程失败路径收紧为 abort 后显式 join，再返回错误，而不依赖未捕获异常路径的栈展开；同时补齐直接使用的头文件。第三次运行重新提取最终正文并执行完整矩阵，才形成仓库中的结果。本记录只统计最后一次，不累加中间执行。

最终 JSON 绑定两篇正文、七份提取源码、runner、helper 与各次编译输出的 SHA-256，并保存命令、cwd、stdout、stderr、返回码、timeout 和运行环境选项；它不承诺跨机器字节级可复现。三个批内 attempt 都完成了当时的矩阵；中间通过不能替代最后修改后的源码证据。

## 2 工具链与实验配置

| 项目 | 本次身份与范围 |
| --- | --- |
| 主机环境 | macOS 26.7，arm64；Python 3.12.14 |
| 编译器 A | Apple Clang 21.0.0，`clang-2100.3.34.2`；libc++ `220106` |
| 编译器 B | Homebrew Clang 23.1.2；libc++ `230102` |
| 通用选项 | `-std=c++23 -Wall -Wextra -Wpedantic -pthread`；`__cplusplus=202302L` |
| 合同实验 | O0／O2；每配置独立编译运行 |
| stress | O2；每工具链 3 个独立进程，每进程 24 轮、24000 条记录 |
| TSan | `-O1 -g -fsanitize=thread -fno-omit-frame-pointer`；不混用 ASan |
| 调度条件 | 未设置线程亲和、优先级、实时调度或调度公平性假设的实测证明 |

TSan 环境为 `halt_on_error=1:abort_on_error=0:exitcode=66:symbolize=0`。执行前清除继承的 ASAN／UBSAN／TSAN／LSAN options，避免其他 common option 改变指定退出行为。阳性对照必须同时具有 data race 诊断和退出码 66；禁用符号化不等于忽略诊断，原始地址、访问记录及线程信息仍保留。

两套编译器都使用 libc++，不代表 GCC、libstdc++ 或两个操作系统。编译无警告；没有借编译选项制造另一套语言语义。全部是本地执行证据，不声明 GitHub CI。

## 3 理论与协议论证的身份

主要语言依据固定为 C++23 草案 N4950。正文就近链接内存位置、SB／HB、mutex、condition variable、join、jthread、原子顺序及 CAS 操作条款。HB 的简化推导明确限于本章不使用 consume 的范围；算法进展术语与操作系统调度、实时截止期分开。

| 论证对象 | 正文给出的论证 | 不由它推出的结论 |
| --- | --- | --- |
| 通道发布与复用 | 同一 mutex 下访问槽位；解锁／加锁连接写入、复制与下一次覆盖 | 外部任务成功、同步设施故障可恢复 |
| 容量与计数 | 逐项状态变化保持容量边界和 accepted 等式 | 无限运行计数不溢出、所有业务副作用恰好一次 |
| close／abort | 两类等待谓词均包含终态，通知覆盖两类等待者 | 公平调度、固定退出延迟、已交付工作自动撤销 |
| 单槽交接 | release／acquire 双向连接发布与复用；单对象一致性排除旧轮标志 | 多生产者安全、完整无锁队列或异常退出协议 |
| CAS 计数 | 失败更新 expected，重新计算 desired；成功 RMW 作为生效点 | 任意 CAS 重试有界完成、复杂副作用可重试 |

这些是带前提的人工协议推导，**没有运行证明器或模型检查器**。逐步说明比仅贴一个 HB 图更强，但仍不是经过机器校验的形式证明。普通运行和 TSan 也不能反过来补全缺失的逻辑前提。

## 4 实际执行结果分项报告

### 4.1 C++ 合同运行与反例

| 检查 | 最终结果 | 判据 |
| --- | --- | --- |
| Q1、Q3、A1、A2 × O0/O2 × 两工具链 | 16 项 PASS | 编译成功、退出 0、精确结果文本、stderr 为空 |
| A1 原子 load/store 逻辑反例 × 两工具链 | 2 项 REJECTED_AS_EXPECTED | 编译成功，`--broken` 返回 21 并输出目标拒绝文本 |
| 三个实现变体 × 两工具链 | 6 项 REJECTED_AS_EXPECTED | 编译成功，返回指定失败码；不是 crash 或 timeout |
| 执行器局部判据自检 | 13 项符合预期 | 拒绝错误输出、退出码、超时、崩溃、错误工具或缺失诊断 |
| 专门编译负例 | NOT RUN | 数据竞争和一般协议错误不能靠编译失败作通用判据 |

Q1 先观察真实等待路径，再分别执行满通道生产者、空通道消费者的 close／abort；另外检查 FIFO、关闭后拒绝、重复调用、close 升级 abort 及守恒计数。Q3 的工作失败是程序主动抛出的 runtime_error，不是操作系统资源耗尽实验。A2 每次正常运行交接 20000 代并比较编号和对应值，发现坏值后仍完成剩余交接，避免 oracle 自身提前退出导致死锁。

三个实现变体分别是：允许 closing 状态继续提交（返回 3），abort 遗漏 discarded 计数（返回 12），单槽写入错误 value（返回 31）。变体只生成在临时目录，未改正文正确实现。A1 的 `--broken` 是正文中显式标识的逻辑反例，不是偷偷替换实现；barrier 保证两个初始 load 都读到零，错误结果具有确定判据。

这些反例检验本批 oracle 的区分能力，不说明所有错误变体都会被拒绝。没有为获得检测结果而放宽为“任意非零即通过”。

### 4.2 有限 stress 与性能边界

Q2 在两个生产者、两个消费者、容量 1～8 的条件下执行，每个独立进程有 24 轮，每轮 1000 条完整记录。每套工具链跑 3 个非插桩进程，合计 **6 个进程、144 轮、144000 条记录**，均满足退出与逐项集合／字段核对。它不是 144000 个独立测试，也不是穷举 144 种线程交错。

yield 仅提供额外调度机会，不建立 HB，也不保证其他线程立即执行；源码没有靠 sleep 猜测等待已经发生。结果不固定不同消费者各取得多少条数据，不要求跨生产者按生成编号全局排序。完整值汇总发生在 join 后，不能只用 checksum 充当去重和遗漏检查。

没有计时性能数据；吞吐、延迟、尾延迟、缓存争用、上下文切换和公平性均为 **NOT RUN／未建立**。从本批耗时或“无 mutex”字样推导速度结论都超出证据。

### 4.3 并发动态检测

两套 TSan 安全探针均可用；两个已知 data race 对照均返回 66 并产生目标诊断，记为 **2 项 DETECTED_AS_EXPECTED**。危险反例没有在非插桩模式执行。探针只是工具通道检查，不混入正文实验数量。

五个正常程序 × 两工具链共 **10 项 CLEAN_OBSERVED**，每项同时满足程序自身不变量、预期输出、退出 0 和无 TSan 诊断。这里包括额外两个插桩 stress 进程，各 24 轮、24000 条记录；不把它们并入上述六个非插桩进程。

原子 load/store 的错误模式另外在两套 TSan 下执行，均仍被业务判据以退出码 21 拒绝，同时没有 TSan 诊断，记为 **2 项 LOGIC_REJECTED_CLEAN_OBSERVED**。它直接展示了“没有 data race”与“算法结果正确”的区别，不把错误算法称为通过。

最终实验 **SKIP 为 0、FAIL 为 0**；执行器保留工具不可用时的 SKIP 和阳性对照不合格时的 FAIL／依赖项 SKIP 路径，但本批没有实际制造这些平台故障。ASan/UBSan 本批 **NOT RUN**，没有继承 G6 的 sanitizer 结果。

## 5 结构检查、输入保护与未验证事项

Markdown 检查验证 GFM 解析及本地文件／锚点链接；新稿另查 H1～H3、标题连续性、锚点唯一、围栏、具名代码、无 details、迁移题与答案配对。它不验证联网 URL 的未来可用性，也不证明语言规则或中文论述已获读者接受。长代码的出版分页风险保留到以后，不为了尚未启动的 PDF 删改完整实验。

执行前后对 **64 份保护文件**与 Base 的 Git 字节比较，全部 UNCHANGED：G0～G6 新稿、验证记录和执行器，复用 helper，v1 十三章、FM 十章及两本正式 PDF。提交范围另检查出版系统、历史 dist 和其他既有文件未变；这不是重算整个仓库所有未跟踪文件的摘要。

未验证：模型检查、全部调度、真实弱内存 litmus、线程创建故障注入、mutex／condition variable 故障、无限运行计数边界、通用 payload 的移动异常、CAS 外部副作用、完整 SPSC／MPMC 队列、ABA 回绕与安全回收、跨平台或实时保证。线程启动失败的控制路径有正文讨论，但没有动态故障注入结果。

本批没有改 G0～G6、v1、FM、出版实现或已发布 PDF，不启动 G8。**PDF NOT BUILT / NOT VALIDATED**；新稿的中文阅读质量和章节组织仍等待精读审核。

## 6 本批检查记录

2026-10-02 实际执行以下检查。临时只读检查没有新增常驻测试框架，不追写历史证据，也不把前一章的通过数量合并到 G7。

| 命令／检查 | 实际结果 |
| --- | --- |
| §1 的执行器命令（使用上述实际 Python 路径） | 最终返回 0／COMPLETED；分项数量见 §4，无 FAIL 或 SKIP |
| `python3 c++/learning/check_docs.py` | 67 份 Markdown、962 处本地链接，无错误；保留 16 个旧 v1 分页风险信号 |
| 临时只读 `python3 -` + `pandoc -f gfm -t json` | 27 份 rework Markdown 层级／锚点／围栏／details 检查通过；G7 两篇各 6 题及 6 答 |
| 临时只读 `python3 -` 导入 runner，调用 `extract()`、`protected_binding()`、`selftests()` | 两篇正文、七份源码、runner／helper 摘要 MATCH；64 份保护文件 UNCHANGED；13 项判据自检符合预期 |
| 同一检查递归读取编译记录并重算临时输出 | 40 个不同编译输出与记录的二进制 SHA-256 相符；不是 40 个正文实验 |
| 同一检查比较 `git diff --name-only` 与 `git ls-files --others --exclude-standard` | 严格为本批 7 个文件，无范围外变更 |
| `git diff --check` | 通过；提交前再次检查暂存差异 |
| `git ls-remote --heads origin main` | 推送前为 Base `c1e8ab7a33f450ef5663085ecdd00ce41ce1692a` |

最终正文 SHA-256：

```text
g07-shared-state-and-shutdown.md
062837653443d1e2fcf37c6aded774bf56bb0253890bdd1990118dac27c4c5c3

g07-atomics-and-publication.md
1f200fb1347a85dee7edb2c98b4e07fee063039180a3f13f5a810c90bd00af21
```

检查只建立上述来源、结构和有限执行证据。G7 的最终精读接受、跨平台验证和出版均未由这些结果自动完成。
