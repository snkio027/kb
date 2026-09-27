<a id="fm-8--thread-coroutine-abi--distributed-failure-boundaries"></a>
# FM-8 · 执行边界与恢复协议

> C++23 失败语义工程手册

[返回 FM 导航](README.md) · [上一章：FM-7](fm7-error-code-system-error.md) · [下一章：FM-9](fm9-project-failure-profile.md) · [术语与审查约定](series-guide.md)

## 阅读入口

把局部失败放回线程、协程、回调、ABI、进程与远端操作中，明确观察点、报告后备、完成认知和恢复权限。

**主阅读线。** §1–8 → §9–11 → §17–22；按实际集成边界回查 §12–16。

**失败契约。** 异常被捕获或存入 future 不代表业务已恢复。超时、取消请求、实际停止与提交是不同事实；确认丢失时不能假定未提交后盲重试。

**证据边界。** T12 是 join 后观察的最小例，T11 是报告再失败的受控终止；未做 TSan、完整协程、ABI 兼容或分布式故障实验。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、线程与异步观察](#fm8-part-1)
- [二、取消、超时与关闭](#fm8-part-2)
- [三、集成和远端边界](#fm8-part-3)
- [四、恢复协议与影响范围](#fm8-part-4)
- [五、审查与回查](#fm8-part-5)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm8-part-1"></a>

## 一、线程与异步观察

### 0. 文档定位

FM-8 研究 failure 跨越执行边界时会发生什么：

```text
thread
future
coroutine
callback
event loop
C ABI
plugin ABI
process
RPC
distributed side effect
```

这些位置必须建立：`failure containment`

而不是让失败无控制扩散。

### 1. Boundary 的本质

Boundary 表示：

> 当前 failure representation 不能或不应该原样继续传播的位置。

典型：

```text
exception
↓
thread boundary
↓
must capture/translate
```

或者：

```text
internal enum
↓
RPC
↓
serialized protocol error
```

### 2. `std::thread`

异常逃出线程初始函数会终止进程；线程入口的 catch 内若再次抛出，同样可能越界。因此隔离必须包括报告路径。[N4950：except.terminate](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)

完整正例 T12 只在线程内保存异常，在正常 join 后由协调者读取、重新抛出并处理：

<!-- fm-test {"id":"T12","mode":"run"} -->
```cpp
#include <exception>
#include <thread>
int main() {
    std::exception_ptr failure;
    std::thread worker([&failure] {
        try { throw 7; }
        catch (...) { failure = std::current_exception(); }
    });
    worker.join(); // Synchronizes before the read of failure.
    if (!failure) { return 1; }
    try { std::rethrow_exception(failure); }
    catch (int value) { return value == 7 ? 0 : 2; }
    catch (...) { return 3; }
}
```

这是单生产者、join 后观察的最小例子；整数异常只是测试标记，不是推荐的生产错误类型。线程创建和 join 自身的失败政策不在本例内。

`current_exception()` 不传播异常，但可能在内部尝试分配或复制异常；失败时可能改为保存 `bad_alloc`、复制失败的异常或 `bad_exception`，不能承诺它永不分配或始终保留原始错误。[N4950：propagation](https://timsong-cpp.github.io/cppwp/n4950/propagation)

工程上把可能分配的格式化、日志、上报推迟到协调者，并给这些动作定义后备路径：例如保留已有失败标记、设置预分配的简单计数／状态，或者按事先批准的策略终止；后备路径也不得再次依赖失败的报告设施。给未知报告函数加 `noexcept` 只会把逃逸异常变成终止，不会证明恢复成立。

[T11](review/fm-verification-samples.md#t11) 用人为编写的抛异常报告函数作受控终止反例，不是仓库生产实现的 bug 复现。

### 3. `std::jthread`

`std::jthread` 改善：

```text
join
cooperative stop
```

`std::jthread` 不会把 worker exception 自动传播给创建线程。如果新线程中的 invoke expression 经异常退出，标准要求调用 `std::terminate()`；因此需要隔离 worker failure 时，仍必须在线程入口显式捕获并转换／保存失败。报告动作自身的失败也须按 §2 处理。[N4950：thread.jthread.cons/5](https://timsong-cpp.github.io/cppwp/n4950/thread.jthread.cons#5)

### 4. `std::promise` / `std::future`

Future channel 保存值或异常；下面只说明通道使用方式，**不是完整的线程入口隔离实现**。

生产端片段：

```cpp
try {
    promise.set_value(work());
} catch (...) {
    promise.set_exception(std::current_exception());
}
```

前提是 promise 有有效共享状态，且结果只被完成一次。catch 中的 `set_exception` 也可能因状态已就绪而抛出 `future_error`；它不是无条件可靠的报告后备。若工作在独立线程中执行，还须按 §2 把报告失败纳入边界。参见 [N4950：futures.promise](https://timsong-cpp.github.io/cppwp/n4950/futures.promise)。

消费端：

```cpp
auto value = future.get();
```

`get()` 观察共享状态并可能重新抛出已保存异常；其使用也要满足 future 自身的有效性前提。把异常存进通道不等于恢复了工作对象，更不免除共享状态和所有权的生命周期管理。

### 5. `std::async`

如果 asynchronous operation 通过 exception 失败，其 associated future 可以保存该异常，并在：

```cpp
future.get()
```

时重新抛出。

因此：`execution boundary`

和：`observation boundary`

可能不在同一线程。

### 6. `std::exception_ptr`

通用模型：

```text
catch exception
↓
current_exception()
↓
transport exception_ptr
↓
rethrow_exception()
```

适用于：

```text
worker → coordinator
callback → event loop
background operation → observer
```

### 7. Coroutine Failure

协程函数体内逃出用户 handler 的异常，由协程变换中的对应处理路径调用：

```cpp
promise_type::unhandled_exception()
```

task 的 promise 可选择保存异常、转换结果或终止，因此 task 类型本身必须声明传播与观察政策。

这不覆盖协程建立过程的一切失败：帧分配、参数副本或 promise 构造等不能统称为“都交给 unhandled_exception”。初始 await 的异常也有单独规则；是否采用 allocation-failure hook 要看 promise 定义。主张仅限定函数体路径，依据 [N4950：dcl.fct.def.coroutine](https://timsong-cpp.github.io/cppwp/n4950/dcl.fct.def.coroutine)。本章不增加 task runtime 实现，也不声称已验证这些路径的执行矩阵。

### 8. Coroutine 不是自动 Result Type

`co_await` / `co_return`：

`不自动规定 failure semantics`

failure 行为由：

```text
awaiter
promise type
task abstraction
scheduler
```

共同决定。

因此不能说：`coroutine 使用 exception`

或者：`coroutine 使用 expected`

它取决于 coroutine abstraction。

<a id="fm8-part-2"></a>

## 二、取消、超时与关闭

### 9. Cancellation ≠ Failure

例如：

```text
shutdown requested
user cancelled
deadline cancelled
task superseded
```

可能不是：`component error`

而是：`control outcome`

因此应尽量区分：

```text
success
failure
cancelled
```

而不是：

```text
success
error
```

两状态模型覆盖所有情况。

### 10. Timeout ≠ Cancellation ≠ Failure

三个概念描述不同观察，不是天然互斥的错误码：

| 概念 | 当前能知道什么 | 不能据此推断什么 |
| --- | --- | --- |
| Timeout | 在约定截止期内没有观察到所需完成结果 | 操作没有执行、没有提交或之后不会完成 |
| Cancellation request | 请求停止／撤回后续工作 | 对方已停止、清理已完成或副作用已撤销 |
| Failure | 没有达到所要求的成功结果，或观察到具体失败 | 不变量必然已坏，或一定可以原样重试 |

取消确认、工作终态和外部提交应另外建模。一个远端操作可能先提交、再丢失响应，调用者超时后又请求取消；这些事实可以同时成立。恢复权限与完成不确定性继续见 §17–19。

### 11. Shutdown 不是 Error Storm

关闭过程中：

```text
socket closed
queue rejected
operation cancelled
```

很多都可能是：`expected shutdown outcomes`

如果全部记录成 ERROR：`observability signal distorted`

成熟系统应区分：

```text
failure during normal operation
vs
expected shutdown cancellation
```

<a id="fm8-part-3"></a>

## 三、集成和远端边界

### 12. Callback Boundary

框架调用：

```cpp
callback(event);
```

如果 callback exception 逃入：

```text
C library
GUI runtime
event loop
unknown framework
```

后果可能不可接受。

因此框架 boundary 应规定：

```text
callback may throw?
callback must be noexcept?
framework catches?
```

不能留成隐式假设。

### 13. C ABI

对外：

```cpp
extern "C" int process(...) {
    try {
        return run();
    } catch (...) {
        return kInternalError;
    }
}
```

核心规则：

> 不要让 C++ exception 穿越不受统一 C++ runtime/ABI 控制的 foreign boundary。

应转换为：

```text
integer status
error struct
opaque error handle
```

### 14. Plugin ABI

插件环境还存在：

```text
compiler mismatch
runtime mismatch
standard library mismatch
allocator mismatch
exception ABI mismatch
```

因此稳定 plugin ABI 通常应该拥有：`explicit C-compatible boundary`

或者严格控制整个 toolchain/runtime。

### 15. Process Boundary

Exception 无法跨 process 直接传播。

必须：`serialize failure`

因此错误协议需要：

```text
stable error identity
versioning
context
retry semantics
```

这就是为什么：`internal C++ type hierarchy`

不能直接成为 RPC error protocol。

### 16. RPC Error Model

远程调用至少可能产生：

```text
domain rejection
transport failure
timeout
cancellation
remote overload
remote internal failure
protocol incompatibility
```

不要压成：`RPC failed`

否则上层无法制定 recovery policy。

<a id="fm8-part-4"></a>

## 四、恢复协议与影响范围

### 17. Ambiguous Remote Completion

最重要的分布式错误之一：

```text
request sent
remote side commits
response lost
caller times out
```

现在：`caller sees failure`

但：`side effect may have happened`

因此：`retry`

可能产生重复副作用。

### 18. Idempotency

自动重试要先证明“重复执行不会产生不允许的额外效果”，或有可靠证据证明前次未提交。否则需要协议层去重、状态查询或补偿，不能只凭 timeout 再发一次。

Idempotency key、request ID 和 transaction token 只是协议材料：接收方如何绑定请求与副作用、保留记录多久、如何处理并发重复及确认丢失，才决定它们能保证什么。即使操作幂等，仍须检查 §19 的截止期、预算和关闭状态。

### 19. Retry Budget

Retry 不能无限：

```text
retry
→ overload
→ more timeout
→ more retry
```

形成 retry storm。

成熟系统通常定义：

```text
deadline
max attempts
backoff
jitter
retryable categories
shutdown awareness
```

这些都属于：`recovery policy`

而不是底层 transport 自动行为。

### 20. Supervisor

并发系统中：`worker`

应尽量只：`detect/report local failure`

更高层 supervisor：

```text
restart?
drop task?
stop subsystem?
stop process?
```

这样 recovery authority 清晰。

### 21. Failure Domain Hierarchy

一个服务可以定义：

```text
operation
↓
task
↓
worker
↓
subsystem
↓
process
↓
service
```

每种 error 必须知道：`maximum blast radius`

例如：

```text
malformed packet
    → packet

worker unexpected exception
    → worker/task

central invariant corruption
    → process
```

### 22. Logging Boundary

一个 failure 如果沿五层传播：`不要每层都 ERROR log`

否则：

```text
one failure → five error records
```

建议：

```text
lower layers:
    preserve/enrich context

decision boundary:
    emit final log/metric
```

<a id="fm8-part-5"></a>

## 五、审查与回查

### 23. FM-8 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

```text
[ ] exception 是否可能逃出 thread entry？
[ ] async failure 是否有明确 observation point？
[ ] exception_ptr ownership/lifetime 是否明确？
[ ] coroutine promise 的 unhandled_exception policy 是否明确？
[ ] cancellation 是否与 failure 分离？
[ ] timeout 是否可能存在 ambiguous completion？
[ ] shutdown cancellation 是否错误计为系统 failure？
[ ] callbacks 是否有 exception contract？
[ ] C/plugin ABI 是否 containment exception？
[ ] RPC error taxonomy 是否稳定？
[ ] retry 是否验证 idempotency？
[ ] retry 是否有 deadline/budget/backoff？
[ ] failure domain 是否限定？
[ ] supervisor 是否拥有正确 recovery authority？
[ ] log 是否集中在 decision boundary？
```

### 24. FM-8 核心不变量

> Thread、ABI、process、RPC 都是 failure boundaries。

> Cancellation、timeout 和 failure 应分别建模。

> Retry 属于 policy，必须建立在 idempotency 和 deadline 之上。

> Remote timeout 不能证明 remote operation 没有执行。

> 并发系统应明确 supervisor 和 failure domain。
