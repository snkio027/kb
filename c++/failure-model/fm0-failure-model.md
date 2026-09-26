# FM-0 — Modern C++ Failure Model

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [下一章：FM-1](fm1-contracts-assertions-ub.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. 核心原则](#1-核心原则)
- [2. Failure 不等于 Exception](#2-failure-不等于-exception)
- [3. Fault / Error / Failure](#3-fault--error--failure)
- [4. 第一维：失败责任分类](#4-第一维失败责任分类)
- [5. Domain Outcome](#5-domain-outcome)
- [6. Environmental Failure](#6-environmental-failure)
- [7. Programmer Error](#7-programmer-error)
- [8. 表面相同的错误可能属于不同类别](#8-表面相同的错误可能属于不同类别)
- [9. Detection / Representation / Translation / Propagation](#9-detection--representation--translation--propagation)
- [10. Detection](#10-detection)
- [11. Representation](#11-representation)
- [12. Error Translation](#12-error-translation)
- [13. Propagation](#13-propagation)
- [14. Handling 不等于 Recovery](#14-handling-不等于-recovery)
- [15. Handling](#15-handling)
- [16. Recovery](#16-recovery)
- [17. Recovery Boundary](#17-recovery-boundary)
- [18. Recovery Boundary 原则](#18-recovery-boundary-原则)
- [19. 不要让底层擅自决定 Retry](#19-不要让底层擅自决定-retry)
- [20. Failure Domain](#20-failure-domain)
- [21. Request-Level Failure Domain](#21-request-level-failure-domain)
- [22. Task-Level Failure Domain](#22-task-level-failure-domain)
- [23. Subsystem-Level Failure Domain](#23-subsystem-level-failure-domain)
- [24. Process-Level Failure Domain](#24-process-level-failure-domain)
- [25. Recovery Boundary 与 Failure Boundary](#25-recovery-boundary-与-failure-boundary)
- [26. C ABI Boundary](#26-c-abi-boundary)
- [27. Thread Boundary](#27-thread-boundary)
- [28. 第二维：Failure Representation](#28-第二维failure-representation)
- [29. 第三维：State Guarantee](#29-第三维state-guarantee)
- [30. Strong Guarantee](#30-strong-guarantee)
- [31. Basic Guarantee](#31-basic-guarantee)
- [32. No Useful Guarantee](#32-no-useful-guarantee)
- [33. State Guarantee 与 Error Transport 正交](#33-state-guarantee-与-error-transport-正交)
- [34. 第四维：Failure Frequency](#34-第四维failure-frequency)
- [35. Common Outcome](#35-common-outcome)
- [36. Rare Failure](#36-rare-failure)
- [37. Catastrophic Failure](#37-catastrophic-failure)
- [38. 第五维：Resource Guarantee](#38-第五维resource-guarantee)
- [39. RAII 的 Failure Model 含义](#39-raii-的-failure-model-含义)
- [40. Complete Failure Pipeline](#40-complete-failure-pipeline)
- [41. 示例：文件读取](#41-示例文件读取)
- [42. 示例：Binary Parser](#42-示例binary-parser)
- [43. 示例：内部 Decode Table](#43-示例内部-decode-table)
- [44. 示例：数据处理 Pipeline](#44-示例数据处理-pipeline)
- [45. Failure Model 的二维底图](#45-failure-model-的二维底图)
- [46. API Failure Contract](#46-api-failure-contract)
- [47. API Review Template](#47-api-review-template)
- [48. Decision Baseline](#48-decision-baseline)
- [49. Anti-Patterns](#49-anti-patterns)
- [50. Failure Model 与 Logging](#50-failure-model-与-logging)
- [51. Failure Model 与 Observability](#51-failure-model-与-observability)
- [52. Failure Model 与 Context](#52-failure-model-与-context)
- [53. Failure Model 与 Shutdown](#53-failure-model-与-shutdown)
- [54. Failure Model 与 Cancellation](#54-failure-model-与-cancellation)
- [55. Failure Model 与 Idempotency](#55-failure-model-与-idempotency)
- [56. Failure Model 与 Partial Commit](#56-failure-model-与-partial-commit)
- [57. Failure Model 与 Ownership](#57-failure-model-与-ownership)
- [58. Failure Model 与 Move](#58-failure-model-与-move)
- [59. 设计层次](#59-设计层次)
- [60. 项目级 Failure Profile](#60-项目级-failure-profile)
- [61. Failure Model 的核心不变量](#61-failure-model-的核心不变量)
- [62. 最终心智模型](#62-最终心智模型)
- [63. FM-0 Review Checklist](#63-fm-0-review-checklist)
- [64. FM-0 压缩版](#64-fm-0-压缩版)
- [65. 后续学习位置](#65-后续学习位置)

---

## 0. 文档定位

本文建立一套适用于现代 C++ 系统工程的统一失败模型，用于回答：

- 什么是失败？
- 哪些情况属于正常结果，哪些是真正错误？
- 失败由谁检测？
- 应该如何表示和传播？
- 哪一层有资格决定如何恢复？
- 失败以后对象和系统处于什么状态？
- 一个失败应该影响多大范围？
- 什么情况下应该继续运行，什么情况下应该终止？

本文不试图直接回答：

> 应该使用 exception 还是 `std::expected`？

因为这不是失败设计的第一问题。

正确顺序是：

```text
理解 failure
    ↓
明确责任
    ↓
明确状态保证
    ↓
明确恢复边界
    ↓
明确 failure domain
    ↓
最后选择 transport mechanism
```

因此：

```text
exception
std::expected
std::optional
std::error_code
assert
std::terminate
```

都只是更大 Failure Model 中的不同工具。

---

## 1. 核心原则

现代 C++ 不存在单一错误处理机制。

一个完整 Failure Model 至少需要描述：

```text
Preconditions
Success semantics
Failure taxonomy
Detection
Representation
Translation
Propagation
Handling
Recovery
State guarantee
Resource guarantee
Recovery boundary
Failure domain
Terminal behavior
```

因此一个函数的真实接口绝不只是：

```cpp
Result operation(Input input);
```

而是：

```text
operation contract
=
input contract
+ success contract
+ failure contract
+ state contract
+ resource contract
```

---

## 2. Failure 不等于 Exception

这是整个模型最重要的概念分离之一。

### 2.1 Failure

failure 描述：

> 一个组件无法履行其当前抽象层承诺的行为。

例如：

```cpp
parse_frame(bytes)
```

如果输入格式非法而无法产生 `Frame`：

```text
parse failure
```

这是 failure。

---

### 2.2 Exception

exception 是 C++ 的一种：

```text
control-flow + failure propagation mechanism
```

例如：

```cpp
throw ParseError{};
```

其中：

```text
ParseError
```

描述失败，

而：

```cpp
throw
```

描述失败如何传播。

因此：

```text
failure ≠ exception
```

同一个 failure 可以表示成：

```cpp
bool
enum
std::optional<T>
std::expected<T, E>
std::error_code
exception
```

甚至最终：

```cpp
std::terminate()
```

---

## 3. Fault / Error / Failure

在工程讨论中建议区分三个层次。

### 3.1 Fault

导致错误的原因。

例如：

```text
错误的长度计算
错误的状态转换
磁盘损坏
网络链路中断
```

---

### 3.2 Error

系统内部状态已经偏离正确状态。

例如设计要求：

```text
0 <= index < 16
```

但内部产生：

```text
index = 27
```

这是错误状态。

---

### 3.3 Failure

错误最终影响到组件对外承诺。

例如：

```cpp
decode_message()
```

无法返回合法结果。

可以粗略理解：

```text
fault
  ↓
error state
  ↓
failure
```

但不要假设三者必然一一对应。

错误可能被内部纠正而永远不会发展为 failure。

---

## 4. 第一维：失败责任分类

在选择错误机制之前，首先判断：

> 这个结果为什么会发生？

推荐将运行时情况首先分为三类：

```text
                 operation outcome
                        │
        ┌───────────────┼────────────────┐
        │               │                │
 domain outcome   environmental      programmer
                     failure            error
```

---

## 5. Domain Outcome

有些“没有得到值”的情况并不是错误。

例如：

```cpp
std::optional<User> find_user(UserId id);
```

可能存在：

```text
user exists
    → User

user does not exist
    → no value
```

用户不存在可能完全属于领域模型正常状态。

其他典型例子：

```text
cache miss
map lookup miss
queue empty
EOF
pattern not found
try_lock failed
```

这些情况通常：

- 是预期的；
- 可能频繁发生；
- 调用者自然需要分支处理。

因此：

> 不要把正常领域状态强行建模成异常。

---

### 5.1 `optional` 的语义

一个良好的第一近似是：

```text
std::optional<T>
≈
T or absence
```

例如：

```cpp
std::optional<User> find_user(UserId id);
```

表达：

```text
存在 User
或者
不存在 User
```

它通常不应该同时承担：

```text
数据库断开
权限失败
数据损坏
```

否则：

```text
absence
```

和：

```text
failure
```

会被压缩为同一个状态。

---

## 6. Environmental Failure

环境失败是程序本身逻辑正确，但外部世界无法满足操作要求。

例如：

```text
file not found
disk full
permission denied
connection reset
timeout
invalid packet
database unavailable
broker unavailable
remote service rejected request
```

这些属于：

```text
runtime operational failure
```

而不是：

```text
program bug
```

例如：

```cpp
std::expected<File, OpenError>
open_file(std::string_view path);
```

可能产生：

```cpp
enum class OpenError {
    not_found,
    permission_denied,
    too_many_open_files,
    io_error,
};
```

调用者可以根据错误采取：

```text
retry
fallback
skip
create
report
shutdown
```

---

## 7. Programmer Error

第三类完全不同。

例如：

```cpp
Message& message_at(std::size_t index) {
    assert(index < messages_.size());
    return messages_[index];
}
```

如果系统设计已经保证：

```text
index 必须来自合法 message table
```

那么越界意味着：

```text
internal invariant violation
```

而不是普通运行时失败。

典型 programmer error 包括：

```text
违反 API 前置条件
内部索引越界
非法状态机转换
double ownership
double free
使用失效引用
破坏类不变量
到达逻辑上不可能的状态
```

这类问题一般不应该被包装成普通业务错误然后继续运行。

---

## 8. 表面相同的错误可能属于不同类别

例如：

```text
index out of range
```

本身无法决定应该如何处理。

### 外部输入

```cpp
parse_packet(untrusted_bytes);
```

packet 内声明：

```text
index = 1000
```

但 packet 实际只有 10 个元素。

这是：

```text
invalid external input
```

应该：

```text
validate
→ report failure
```

---

### 内部索引

```cpp
auto index = generated_table[id];

assert(index < messages.size());
```

如果生成表保证 index 合法，那么失败说明：

```text
program invariant broken
```

因此可能：

```text
assert / fail-fast
```

---

### 原则

不要问：

> 这个错误看起来严重吗？

而应该问：

> 调用者是否有责任保证这种情况永远不会出现？

这是判断：

```text
recoverable error
vs
contract violation
```

的重要标准。

---

## 9. Detection / Representation / Translation / Propagation

失败处理不是一个动作，而是一条生命周期。

推荐显式拆分：

```text
detect
  ↓
represent
  ↓
translate
  ↓
propagate
  ↓
handle
  ↓
recover
```

---

## 10. Detection

Detection 回答：

> 谁最先知道操作无法继续？

可能是：

```text
CPU
kernel
system call
allocator
runtime
third-party library
parser
domain logic
invariant check
```

例如：

```cpp
::open(...)
```

打开不存在的文件。

最早发现问题的是：

```text
OS / system-call layer
```

---

## 11. Representation

失败被某种值或机制表示。

例如 POSIX：

```text
ENOENT
```

进入 C++ 层以后可能成为：

```cpp
std::error_code
```

再进入配置领域：

```cpp
enum class ConfigError {
    missing,
    permission_denied,
    malformed,
};
```

所以同一失败可能经历：

```text
ENOENT
  ↓
std::errc::no_such_file_or_directory
  ↓
ConfigError::missing
```

---

## 12. Error Translation

translation 是：

> 从一个抽象层的错误语言，转换成另一个抽象层真正理解的错误语言。

例如：

```text
TCP ECONNRESET
    ↓
DatabaseError::connection_lost
    ↓
RepositoryError::unavailable
```

业务逻辑通常不应该依赖：

```text
ECONNRESET
```

因为：

```text
TCP
```

可能只是 repository 当前实现细节。

---

### 12.1 Translation 原则

只有当：

> 抽象层发生变化，并且错误语义也随之变化

才值得 translation。

不要机械制造：

```text
ErrorA
 ↓
ErrorB
 ↓
ErrorC
 ↓
ErrorD
 ↓
ErrorE
```

否则错误模型本身会成为新的复杂系统。

---

## 13. Propagation

发现失败的层不一定知道如何处理。

例如：

```cpp
std::expected<std::string, FileError>
read_file(std::string_view path);
```

底层知道：

```text
file missing
```

但不知道：

```text
应该创建文件吗？
应该使用默认值吗？
应该退出程序吗？
这是 production 还是 development？
```

因此它的职责可能只是：

```text
propagate failure
```

即：

```text
我告诉上一层发生了什么，
但不替上一层决定策略。
```

---

## 14. Handling 不等于 Recovery

这是大型系统中非常重要的区别。

考虑：

```cpp
try {
    update_state();
} catch (const std::exception& e) {
    log(e.what());
}

continue_processing();
```

这里只能确定：

```text
exception was observed
```

不能确定：

```text
system recovered
```

因为 `update_state()` 可能已经：

```text
update A
update B
fail while updating C
```

形成：

```text
partial state
```

---

## 15. Handling

Handling 表示：

> 当前层接受了这个 failure，不再继续按原样向上传播。

例如：

```cpp
auto result = load_config();

if (!result) {
    log(result.error());
    return EXIT_FAILURE;
}
```

这里 `main` 处理了这个错误。

但它没有恢复。

---

## 16. Recovery

Recovery 的标准更高：

> 系统重新进入一个定义良好、可以继续履行职责的状态。

例如：

```cpp
auto config = load_config();

if (!config && config.error() == ConfigError::missing) {
    config = make_default_config();
}
```

如果成功：

```text
missing config
    ↓
fallback
    ↓
valid configuration
    ↓
normal execution
```

这才是真正恢复。

---

### 16.1 Recovery 必须知道状态

一个层如果不知道：

```text
哪些修改已经发生
哪些资源已经获得
哪些对象仍然有效
哪些操作可以 rollback
当前 invariant 是否仍成立
```

它通常没有资格声称自己已经恢复。

---

## 17. Recovery Boundary

这是 Failure Model 最重要的工程概念之一。

假设：

```text
main
 └─ Application
     └─ ConfigService
         └─ ConfigRepository
             └─ FileReader
                 └─ OS
```

最底层得到：

```text
ENOENT
```

---

### FileReader

知道：

```text
file does not exist
```

不知道：

```text
这个文件是否必须存在
```

---

### ConfigRepository

知道：

```text
这是 configuration
```

但可能仍不知道：

```text
production 和 development 是否策略不同
```

---

### Application

可能知道：

```text
production:
    missing config → startup failure

development:
    missing config → generate default
```

因此：

```text
Application
```

才是真正的：

```text
recovery boundary
```

---

## 18. Recovery Boundary 原则

一个极其重要的工程原则：

> **Detect failure as low as necessary; recover as high as necessary.**

中文可以理解为：

> 失败应该在最接近事实的位置检测，在最接近策略的位置恢复。

因此通常：

```text
who detects
≠
who decides
```

---

## 19. 不要让底层擅自决定 Retry

例如：

```cpp
fetch_from_server();
```

底层发生：

```text
timeout
```

网络层可能不知道：

```text
请求是否幂等
整体 deadline 是多少
是否已经在 retry
是否正在 shutdown
重复发送是否危险
业务是否允许 fallback
```

因此：

```text
retry
```

不是单纯错误处理。

它是：

```text
recovery policy
```

应该由拥有足够上下文的一层决定。

---

## 20. Failure Domain

Recovery Boundary 回答：

> 谁负责决定怎么办？

Failure Domain 回答另一个问题：

> 这次失败最多应该影响多大的范围？

例如：

```text
process
 ├─ request A
 ├─ request B
 ├─ request C
 └─ background worker
```

发生一个错误，不一定意味着整个进程都应该失败。

---

## 21. Request-Level Failure Domain

例如：

```text
malformed HTTP request
```

合理影响范围可能只是：

```text
one request
```

因此：

```text
request fails
service continues
```

---

## 22. Task-Level Failure Domain

线程池：

```text
worker
 ├─ task A
 ├─ task B
 └─ task C
```

task B 失败：

```text
task B failed
```

如果任务彼此隔离，则：

```text
worker continues
```

---

## 23. Subsystem-Level Failure Domain

例如：

```text
telemetry subsystem
```

可能允许：

```text
subsystem restart
```

而核心服务继续运行。

---

## 24. Process-Level Failure Domain

如果发生：

```text
heap corruption
global invariant violation
ownership corruption
impossible global state
```

继续执行可能已经没有可靠语义。

此时：

```text
process termination
```

可能比：

```text
catch(...)
continue
```

更正确。

---

## 25. Recovery Boundary 与 Failure Boundary

这两个概念不要混淆。

### Recovery Boundary

回答：

```text
谁有足够上下文选择恢复策略？
```

---

### Failure Boundary

回答：

```text
失败传播不能以当前形式越过哪里？
```

典型 failure boundary：

```text
thread entry
C ABI
plugin ABI
RPC
process
service
IPC
```

---

## 26. C ABI Boundary

例如：

```cpp
extern "C" int plugin_entry() {
    try {
        run_plugin();
        return 0;
    } catch (...) {
        return -1;
    }
}
```

这里 exception 必须被转换：

```text
C++ exception
    ↓
boundary
    ↓
C-compatible error representation
```

因为另一侧没有 C++ exception model。

---

## 27. Thread Boundary

异常逃出线程初始函数会调用 `std::terminate()`。若工程目标是把 worker 失败限制在线程任务内，边界必须覆盖工作路径和错误报告路径；仅有 `catch (...)` 还不够。[N4950：except.terminate](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)

以下是契约片段：只在线程内保存异常，正常 `join()` 返回后由协调者观察。这里省略了 `run_worker` 的实现以及线程创建、join 和协调者报告失败的上层策略。

```cpp
std::exception_ptr failure;
std::thread worker([&failure] {
    try {
        run_worker();
    } catch (...) {
        failure = std::current_exception();
    }
});
worker.join(); // 正常返回后，协调者才能读取 failure。
```

不要在这个 catch 内调用契约未知的 `report_failure()`：格式化、日志分配或报告动作若再次抛出，仍可能造成进程终止。只给它加 `noexcept` 也不是恢复方案。

完整样例、异常捕获可能分配的限制和报告失败后备策略，见 [FM-8 §2](fm8-failure-boundaries.md#2-stdthread)。

---

## 28. 第二维：Failure Representation

常见 failure transport 包括：

```text
bool
sentinel
enum
std::optional<T>
std::expected<T, E>
std::error_code
exception
termination
```

重要的是：

> failure representation 只说明错误如何被携带。

它不自动说明失败后的状态。

例如：

```cpp
std::expected<void, Error> update();
```

不能自动推出：

```text
failure → state unchanged
```

---

## 29. 第三维：State Guarantee

失败后的状态应与异常传播、终止策略分别说明：

| 分析维度 | 应回答的问题 |
| --- | --- |
| 失败后状态 | strong（可观察状态不变）、basic（不变量成立但值可变）、明确的部分进度，还是没有可依赖的状态保证？ |
| 异常传播 | 是否允许异常越过 API 边界？`noexcept` 只约束这一项。 |
| 终局处置 | 是否拒绝当前操作、升级处理、重启或终止进程？ |

这些不是一条从弱到强的等级序列。一个返回错误码的 `noexcept` 操作仍可能失败；终止也不等于“成功完成清理”。术语和提交条件统一见 [FM-4 §4～§5](fm4-raii-exception-safety.md#4-exception-safety-guarantees)。

---

## 30. Strong Guarantee

失败以后：

```text
externally observable state
=
state before operation
```

即：

```text
success → commit
failure → as if operation never happened
```

常见模型：

```text
prepare
   ↓
may fail
   ↓
commit
   ↓
must not fail
```

---

## 31. Basic Guarantee

失败以后：

```text
state may have changed
```

但是：

```text
invariants still hold
resources are owned correctly
objects remain destructible
program may continue according to contract
```

---

## 32. No Useful Guarantee

失败以后：

```text
state unknown
invariants may be broken
```

此时继续使用对象可能已经没有可靠语义。

高质量基础组件应尽量避免这种设计。

---

## 33. State Guarantee 与 Error Transport 正交

例如：

```cpp
std::expected<void, Error> update();
```

可能提供：

```text
strong guarantee
```

也可能只提供：

```text
basic guarantee
```

甚至可能糟糕到：

```text
partial invalid state
```

同样：

```cpp
void update();
```

虽然通过 exception 失败，也可以提供：

```text
strong guarantee
```

因此不要建立错误对应：

```text
expected = safe
exception = unsafe
```

真正应该分析的是：

```text
transport mechanism
×
state guarantee
```

---

## 34. 第四维：Failure Frequency

常见、少见等发生频率会影响机制成本，但应根据实际工作负载判断，不能由错误名称推断。

频率与严重性独立：高频失败也可能严重，罕见结果也可能只是普通拒绝。§35～§36 讨论频率；§37 的 catastrophic 是严重性与处置问题，不是第三档发生频率。

---

## 35. Common Outcome

例如：

```text
lookup miss
queue empty
EOF
cache miss
try_lock failure
```

通常应该具有：

```text
low control-flow cost
explicit semantics
easy branch handling
```

常见表示：

```text
bool
enum
optional
expected
```

---

## 36. Rare Failure

例如：

```text
configuration unavailable
rare I/O failure
deep initialization failure
```

如果失败确实稀有，并且需要跨多层传播：

```text
exception
```

可能成为合理设计。

但频率只是决策输入之一，不是唯一标准。

---

## 37. Catastrophic Failure

这里切换到严重性与终局处置维度，不继续给发生频率分档。

堆损坏、中心不变量失效、重复所有权等问题，可能使进程状态不再可信。工程上通常应考虑 fail-fast，而不是假装通过普通错误值恢复；适用范围仍取决于损坏的失败域和系统隔离能力。

这是工程处置建议，不是说所有严重错误都由同一种语言机制报告，也不是说 `terminate` 会执行完整资源清理。

---

## 38. 第五维：Resource Guarantee

状态正确不只是业务字段正确。

还必须保证：

```text
memory
file handles
locks
sockets
transactions
temporary files
GPU resources
OS handles
```

在失败路径中受到正确管理。

这就是 RAII 对 C++ Failure Model 的基础意义。

Failure contract 应明确：

```text
失败以后：
是否存在资源泄漏？
锁是否释放？
所有权是否清晰？
temporary resource 是否清理？
```

---

## 39. RAII 的 Failure Model 含义

RAII 将资源所有权绑定到对象生命周期，使正常作用域退出与**确实发生的栈展开**共用析构清理。

```text
acquire → owner → work → normal exit / unwinding → destructor
```

不能把这条路径扩展到所有终止：无匹配 handler 或触及 `noexcept` 边界时，不能依赖完整栈展开。清理规则与终止边界的主说明见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

工程上还要审查析构的可失败操作；RAII 不自动提供持久化提交、业务回滚或“资源关闭一定成功”的保证。

---

## 40. Complete Failure Pipeline

综合起来，一个 failure 可以经历：

```text
source / fault
      ↓
detection
      ↓
representation
      ↓
translation
      ↓
propagation
      ↓
recovery boundary
      ↓
recovery policy
      ↓
state transition
      ↓
failure domain containment
```

任何复杂系统错误处理设计，都应该能够映射回这条链。

---

## 41. 示例：文件读取

契约片段：

```cpp
std::expected<Config, ConfigError>
load_config(std::string_view path);
```

以 POSIX `open` 打开已有配置文件为例，返回值与错误指示必须分开：

```text
open(path, O_RDONLY) returns -1
    ↓
capture errno immediately
    ↓
missing-path error: saved errno == ENOENT
    ↓
translate to ConfigError::missing
```

不是 `open()` “返回 ENOENT”。成功返回文件描述符；失败返回 `-1` 并设置 `errno`。`O_CREAT` 等选项会改变语义，不能把“目标文件不存在”无条件等同于打开失败。[open(2)：返回值与错误](https://man7.org/linux/man-pages/man2/open.2.html)

工程模型仍为：

```text
Detection             OS
Representation        saved errno / error_code
Translation           ConfigError::missing
Propagation           load_config returns unexpected
Recovery boundary     Application startup
Recovery              development → default config
                      production  → fail startup
Failure domain        application startup
State guarantee       existing configuration remains unchanged
```

最后一项依赖先完整读取、解析和验证，再提交新配置，不能仅由返回 `expected` 推出。相关错误转换见 [FM-7 §1](fm7-error-code-system-error.md#1-errno)。

---

## 42. 示例：Binary Parser

```cpp
std::expected<Frame, ParseError>
parse_frame(std::span<const std::byte> input);
```

可能失败：

```text
truncated input
invalid length
checksum mismatch
unknown version
```

模型：

```text
Responsibility
    external input

Frequency
    depends on data quality;
    invalid input is expected operationally

Detection
    parser

Representation
    ParseError

Propagation
    expected

Recovery boundary
    message processor

Recovery
    drop / count / quarantine / report

Failure domain
    one frame

State guarantee
    input unchanged
    no externally visible partial Frame
```

这是非常适合 value-based error handling 的类型。

---

## 43. 示例：内部 Decode Table

```cpp
const DecodePlan& plan_for(std::size_t index) {
    assert(index < plans.size());
    return plans[index];
}
```

假设 `index` 来源完全受内部控制。

模型：

```text
Responsibility
    programmer

Failure type
    invariant violation

Recovery
    usually none locally

Representation
    assertion / fatal check

Failure domain
    process or subsystem

Reason
    continuing would hide a programming defect
```

---

## 44. 示例：数据处理 Pipeline

```text
Kafka
 ↓
download
 ↓
decompress
 ↓
parse
 ↓
decode
 ↓
produce
```

假设 gzip 数据损坏。

### Detection

```text
decompression library
```

### Low-level representation

```text
DecompressError::invalid_stream
```

### Translation

```text
ProcessError::corrupted_capture
```

### Propagation

```text
worker processing result
```

### Recovery boundary

worker / job coordinator 知道：

```text
是否 retry
是否 dead-letter
是否标记失败
是否 ACK
```

### Failure domain

通常：

```text
one input object
```

而不是：

```text
entire process
```

这就是 error containment。

---

## 45. Failure Model 的二维底图

至少先建立：

```text
                  Representation
                        ↑
                        │
                        │
State Guarantee ────────┼────────── Responsibility
                        │
                        │
                  Failure Frequency
```

实际工程中还需要再加入：

```text
Recovery Boundary
Failure Domain
```

因此它不是简单的一维：

```text
expected vs exception
```

问题。

---

## 46. API Failure Contract

一个高质量 API 应能够回答以下内容。

### Preconditions

调用者必须保证：

```text
什么条件成立？
```

---

### Success Postconditions

成功以后：

```text
什么一定成立？
```

---

### Failure Set

可能有哪些 failure？

```text
absence
invalid input
resource exhaustion
external service unavailable
invariant violation
...
```

---

### Representation

每种 failure：

```text
如何表示？
```

---

### State Guarantee

失败后：

```text
哪些状态保持不变？
哪些允许改变？
对象是否仍然有效？
```

---

### Resource Guarantee

失败后：

```text
是否存在泄漏？
锁是否释放？
temporary resource 是否回收？
```

---

### Recovery Responsibility

当前层：

```text
负责恢复
还是
只负责传播？
```

---

## 47. API Review Template

以后评审任何：

```cpp
R operation(A input);
```

建议逐项回答：

### 1. Success

```text
什么叫成功？
```

### 2. Preconditions

```text
调用者必须保证什么？
```

### 3. Domain Outcomes

```text
哪些“没有结果”属于正常业务状态？
```

### 4. Environmental Failures

```text
哪些外部条件可能阻止操作完成？
```

### 5. Programmer Errors

```text
哪些情况代表 contract / invariant 被破坏？
```

### 6. Detection

```text
谁最先发现？
```

### 7. Representation

```text
如何表示？
```

### 8. Translation

```text
是否需要改变错误抽象？
```

### 9. Propagation

```text
传播到哪里？
```

### 10. Recovery Boundary

```text
哪一层真正知道怎么办？
```

### 11. Recovery Policy

```text
retry / fallback / skip / rollback / shutdown？
```

### 12. State Guarantee

```text
失败后 state 是什么？
```

### 13. Resource Guarantee

```text
资源是否全部处于明确 ownership 下？
```

### 14. Failure Domain

```text
一个 object？
一个 request？
一个 task？
一个 thread？
一个 subsystem？
一个 process？
```

### 15. Frequency

```text
common / uncommon？（依据具体工作负载）
严重性与终局处置另行记录，不混入频率。
```

### 16. Terminal Behavior

```text
最终无人恢复时怎么办？
```

---

## 48. Decision Baseline

以下不是绝对规则，而是工程默认值。

| 场景 | 默认考虑 |
|---|---|
| 正常 absence | `std::optional<T>` |
| 可预期且需要原因的失败 | `std::expected<T, E>` |
| OS / system API 错误 | `std::error_code` 或封装后的领域错误 |
| 稀有、需要跨多层传播的失败 | exception |
| 外部不可信输入 | validate + structured failure |
| 调用者违反前置条件 | contract/assert/fail-fast |
| 内部不变量损坏 | fail-fast / terminate |
| 高频普通分支 | value-based result |
| ABI / thread / process 边界 | 捕获、转换、隔离 |
| 无法确定程序状态 | 不应假装恢复 |

---

## 49. Anti-Patterns

### 49.1 Catch and Continue

```cpp
try {
    mutate_state();
} catch (...) {
    log();
}

continue_running();
```

如果不知道：

```text
state after failure
```

这不是 recovery。

---

### 49.2 Catch All Too Low

```cpp
std::string read_file(...) {
    try {
        ...
    } catch (...) {
        return {};
    }
}
```

这把：

```text
empty file
```

和：

```text
file read failed
```

混在一起。

同时丢失恢复上下文。

---

### 49.3 Assert External Input

错误：

```cpp
assert(packet.size() >= header_size);
```

如果 packet 来自网络，这是：

```text
untrusted runtime input
```

应该验证并报告 failure。

---

### 49.4 Expected for Impossible Internal State

如果某件事根据程序 invariant：

```text
must never happen
```

把它变成：

```cpp
std::expected<T, ImpossibleError>
```

然后一路传播，可能只是在隐藏 bug。

---

### 49.5 Low-Level Retry Without Context

底层擅自：

```text
retry forever
```

可能破坏：

```text
deadline
shutdown
idempotency
backpressure
retry budget
```

---

### 49.6 Translate Every Layer

不要构造：

```text
SocketError
 → ClientError
 → StorageError
 → RepositoryError
 → ServiceError
 → ApplicationError
```

除非每次 translation 都真的产生新的抽象语义。

---

### 49.7 Error String as Error Model

不要把：

```cpp
std::string error;
```

当成主要机器可判定错误模型。

字符串适合：

```text
diagnostics
logging
human context
```

结构化类型适合：

```text
control flow
policy
recovery
```

---

## 50. Failure Model 与 Logging

Logging 不是 failure transport。

不要设计成：

```text
底层 log error
上层 log error
再上层 log error
```

导致同一个 failure 被记录五次。

一个良好原则：

```text
lower layers:
    enrich / propagate

recovery or terminal boundary:
    log
```

即：

> 通常在真正决定错误命运的层记录最终诊断。

---

## 51. Failure Model 与 Observability

一个失败可能需要同时产生：

```text
structured error
metric
trace event
log
```

但这些职责不同：

```text
error object
    → program control flow

metric
    → aggregated operational state

trace
    → request causality

log
    → human diagnosis
```

不要让 logging string 取代结构化错误。

---

## 52. Failure Model 与 Context

错误向上传播时可能需要增加 context：

```text
ENOENT
```

单独看价值有限。

更有诊断价值的是：

```text
failed to load project configuration
path=/etc/app/project.toml
cause=no such file or directory
```

但应区分：

```text
machine-readable category
```

和：

```text
human-readable context
```

理想错误模型通常保留两者。

---

## 53. Failure Model 与 Shutdown

shutdown 本身应该视为一种特殊控制状态。

例如：

```text
network read interrupted because system is shutting down
```

不一定应该被统计为：

```text
network failure
```

因此成熟系统通常需要区分：

```text
operation failed
operation cancelled
operation timed out
system shutting down
```

否则 observability 会产生错误信号。

---

## 54. Failure Model 与 Cancellation

Cancellation 不应该自动等同于 error。

例如：

```text
user cancelled
deadline expired
shutdown requested
superseded operation
```

这些可能属于：

```text
control outcome
```

而不是：

```text
component defect
```

因此 cancellation 应在 Failure Model 中拥有明确语义。

---

## 55. Failure Model 与 Idempotency

恢复策略尤其是 retry 之前，必须回答：

```text
operation 是否幂等？
```

例如：

```text
GET resource
```

通常可以安全 retry。

而：

```text
charge_credit_card()
```

如果没有 idempotency key：

```text
retry
```

可能产生重复副作用。

因此：

```text
retry policy
```

不能脱离 operation semantics 设计。

---

## 56. Failure Model 与 Partial Commit

对状态修改操作必须明确：

```text
失败可能发生在 commit 前还是 commit 后？
```

例如：

```text
write file
publish message
update database
send network request
```

可能出现：

```text
operation actually succeeded
but acknowledgment was lost
```

此时调用者观察到：

```text
failure
```

但现实世界可能已经发生副作用。

这是：

```text
ambiguous completion
```

分布式和 I/O API 必须特别注意。

---

## 57. Failure Model 与 Ownership

一个 operation 失败时必须知道：

```text
谁还拥有资源？
```

例如：

```cpp
send(std::unique_ptr<Job> job);
```

失败以后：

```text
job ownership transferred?
or retained by caller?
```

必须明确。

这也是为什么现代 C++ 的 ownership 类型对 Failure Model 很重要。

---

## 58. Failure Model 与 Move

移动操作尤其需要明确：

```text
failure before ownership transfer
failure during ownership transfer
source state after failure
```

这直接影响：

```text
strong guarantee
rollback
container relocation
```

后续在 FM-5 专门展开。

---

## 59. 设计层次

推荐将大型系统 failure strategy 分成三层。

### Layer 1 — Local API Contract

每个函数描述：

```text
local failure semantics
```

---

### Layer 2 — Subsystem Failure Policy

例如：

```text
storage subsystem
network subsystem
parser subsystem
worker subsystem
```

定义：

```text
error taxonomy
retry
fallback
failure boundary
```

---

### Layer 3 — Application Failure Policy

统一决定：

```text
logging
metrics
shutdown
restart
process termination
operator alerts
```

这样避免每个函数各自发明策略。

---

## 60. 项目级 Failure Profile

成熟 C++ 项目应该最终形成自己的 Failure Profile。

至少定义：

```text
哪些 API 使用 expected
哪些 API 可以抛 exception
哪些层禁止 exception 越界
哪些情况属于 programmer error
哪些 invariant violation 必须 fail-fast
哪些组件允许 retry
retry budget 如何管理
哪些 operation 保证 strong/basic guarantee
哪些 thread entry 必须捕获所有 exception
哪些 ABI boundary 必须进行 error translation
顶层 fatal handler 如何工作
```

---

## 61. Failure Model 的核心不变量

以下原则建议作为长期工程基线。

### FM-I1

> Failure 与 exception 必须分离讨论。

---

### FM-I2

> Normal absence 不应伪装成 exceptional failure。

---

### FM-I3

> External invalid input 不应使用 assertion 代替 validation。

---

### FM-I4

> Programmer error 不应轻易降级成普通业务错误继续运行。

---

### FM-I5

> Detection point 不等于 recovery point。

---

### FM-I6

> Recovery policy 必须由拥有足够上下文的层决定。

---

### FM-I7

> Handling 不等于 recovery。

---

### FM-I8

> Error representation 与 state guarantee 是两个独立维度。

---

### FM-I9

> 一个错误机制的好坏必须结合 failure frequency 判断。

---

### FM-I10

> Failure 必须被限制在明确的 failure domain。

---

### FM-I11

> 跨 thread / ABI / process boundary 时必须明确 error conversion。

---

### FM-I12

> 如果无法证明系统已经恢复到定义良好的状态，就不要假装 recovery 已经完成。

---

### FM-I13

> Retry 是业务恢复策略，不是底层错误处理默认动作。

---

### FM-I14

> Error translation 只应发生在抽象语义真正变化的地方。

---

### FM-I15

> Resource ownership 必须在所有 failure path 上保持明确。

---

## 62. 最终心智模型

分析任何 operation 时，不要先想：

```text
throw?
expected?
```

先建立：

```text
                         Operation
                             │
                    what can happen?
                             │
          ┌──────────────────┼─────────────────┐
          │                  │                 │
    domain outcome      external failure   programmer error
          │                  │                 │
          └──────────────────┼─────────────────┘
                             │
                         detection
                             │
                      representation
                             │
                       translation?
                             │
                        propagation
                             │
                    recovery boundary
                             │
                      recovery policy
                             │
             ┌───────────────┴────────────────┐
             │                                │
          recovered                     unrecoverable
             │                                │
      defined valid state              failure boundary
                                              │
                                       terminate/escalate
```

同时沿另一条轴检查：

```text
before operation
      ↓
operation starts
      ↓
failure occurs
      ↓
what state remains?
      │
      ├─ unchanged
      ├─ valid but modified
      ├─ partially committed
      ├─ invalid
      └─ process terminated
```

图中的 process terminated 是终局处置，不是存活对象的状态保证等级。

只有这两个模型都清楚之后，才讨论：

```text
optional
expected
error_code
exception
assert
terminate
```

---

## 63. FM-0 Review Checklist

设计或 Code Review 一个 API 时，可以直接使用以下清单：

```text
[ ] 成功语义是否明确？
[ ] Preconditions 是否明确？
[ ] 正常 absence 与 failure 是否区分？
[ ] 外部错误与 programmer error 是否区分？
[ ] Detection point 是否合理？
[ ] Error representation 是否结构化？
[ ] 是否存在不必要的 error translation？
[ ] Propagation 是否保留足够上下文？
[ ] Recovery boundary 是否位于拥有策略上下文的层？
[ ] Recovery 是否真正恢复了 valid state？
[ ] Failure domain 是否明确？
[ ] State guarantee 是否明确？
[ ] Resource guarantee 是否明确？
[ ] Ownership 在失败路径上是否明确？
[ ] Retry 是否考虑 idempotency、deadline 与 shutdown？
[ ] Cancellation 是否与 failure 正确区分？
[ ] Thread / ABI / process boundary 是否正确转换失败？
[ ] Fatal programmer error 是否会被错误地吞掉？
[ ] Logging 是否发生在正确的决策边界？
[ ] API 是否让调用者能够做出正确恢复决策？
```

---

## 64. FM-0 压缩版

最终可以把整个 FM-0 压成六个问题：

```text
1. What happened?
   发生了什么？

2. Whose responsibility is it?
   属于正常结果、环境失败还是程序缺陷？

3. What remains valid?
   失败以后还有哪些状态保证？

4. Who knows what to do?
   哪一层拥有恢复所需上下文？

5. How far should the failure spread?
   failure domain 到哪里？

6. How should it travel?
   最后才选择 expected / exception / error_code / terminate。
```

如果这六个问题能够准确回答，一个 C++ Failure Model 通常已经具备正确的骨架。

---

## 65. 后续学习位置

FM-0 只建立统一模型。

后续章节分别解决具体机制：

```text
FM-1
Contracts / Preconditions / Assertions / UB

FM-2
Value-based Failure
bool / optional / expected / error types

FM-3
C++ Exception Semantics
throw / catch / stack unwinding

FM-4
RAII & Exception Safety
basic / strong / transactional design

FM-5
noexcept / Move / Copy
container guarantees / move_if_noexcept

FM-6
Construction / Destruction / Allocation Failure

FM-7
error_code / system_error / OS Failure

FM-8
Thread / Coroutine / ABI / RPC Failure Boundaries

FM-9
Project-Level Failure Profile
```

FM-0 的职责到这里结束：

> **先建立正确的 failure vocabulary、responsibility model、state model、recovery boundary 和 failure domain，再选择具体语言机制。**

这套顺序将作为后续现代 C++ Failure Model 的统一分析框架。
