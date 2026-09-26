# FM-8 — Thread, Coroutine, ABI & Distributed Failure Boundaries

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-7](fm7-error-code-system-error.md) · [下一章：FM-9](fm9-project-failure-profile.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. Boundary 的本质](#1-boundary-的本质)
- [2. std::thread](#2-stdthread)
- [3. std::jthread](#3-stdjthread)
- [4. std::promise / std::future](#4-stdpromise--stdfuture)
- [5. std::async](#5-stdasync)
- [6. std::exception_ptr](#6-stdexception_ptr)
- [7. Coroutine Failure](#7-coroutine-failure)
- [8. Coroutine 不是自动 Result Type](#8-coroutine-不是自动-result-type)
- [9. Cancellation ≠ Failure](#9-cancellation--failure)
- [10. Timeout ≠ Cancellation ≠ Failure](#10-timeout--cancellation--failure)
- [11. Shutdown 不是 Error Storm](#11-shutdown-不是-error-storm)
- [12. Callback Boundary](#12-callback-boundary)
- [13. C ABI](#13-c-abi)
- [14. Plugin ABI](#14-plugin-abi)
- [15. Process Boundary](#15-process-boundary)
- [16. RPC Error Model](#16-rpc-error-model)
- [17. Ambiguous Remote Completion](#17-ambiguous-remote-completion)
- [18. Idempotency](#18-idempotency)
- [19. Retry Budget](#19-retry-budget)
- [20. Supervisor](#20-supervisor)
- [21. Failure Domain Hierarchy](#21-failure-domain-hierarchy)
- [22. Logging Boundary](#22-logging-boundary)
- [23. FM-8 Review Checklist](#23-fm-8-review-checklist)
- [24. FM-8 核心不变量](#24-fm-8-核心不变量)

---

## 0. 文档定位

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

这些位置必须建立：

```text
failure containment
```

而不是让失败无控制扩散。

---

## 1. Boundary 的本质

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

---

## 2. `std::thread`

如果 exception 逃出 thread entry function：

```text
std::terminate()
```

因此：

```cpp
std::thread worker([] {
    try {
        run_worker();
    } catch (...) {
        report_failure(std::current_exception());
    }
});
```

如果架构要求：

```text
worker failure
≠
process failure
```

就必须建立 thread failure boundary。

---

## 3. `std::jthread`

`std::jthread` 改善：

```text
join
cooperative stop
```

但并不会自动把 thread exception 转回 caller。

thread function 中异常逃出：

```text
同样不能依赖自动传播到创建者
```

应显式 containment。

---

## 4. `std::promise` / `std::future`

Future channel 能够保存：

```text
value
or
exception
```

producer：

```cpp
try {
    promise.set_value(work());
} catch (...) {
    promise.set_exception(std::current_exception());
}
```

consumer：

```cpp
auto value = future.get();
```

`get()` 会重新观察 producer failure。

这是标准：

```text
cross-thread exception transport
```

模型。

---

## 5. `std::async`

如果 asynchronous operation 通过 exception 失败，其 associated future 可以保存该异常，并在：

```cpp
future.get()
```

时重新抛出。

因此：

```text
execution boundary
```

和：

```text
observation boundary
```

可能不在同一线程。

---

## 6. `std::exception_ptr`

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

---

## 7. Coroutine Failure

C++ coroutine 中，coroutine body 内未被用户代码捕获的 exception 会进入 coroutine promise 的：

```cpp
promise_type::unhandled_exception()
```

因此：

> coroutine type 的 `promise_type` 本身定义了重要 failure policy。

一个 task abstraction 可以选择：

```text
store exception_ptr
store expected-like result
terminate
translate error
```

---

## 8. Coroutine 不是自动 Result Type

`co_await` / `co_return`：

```text
不自动规定 failure semantics
```

failure 行为由：

```text
awaiter
promise type
task abstraction
scheduler
```

共同决定。

因此不能说：

```text
coroutine 使用 exception
```

或者：

```text
coroutine 使用 expected
```

它取决于 coroutine abstraction。

---

## 9. Cancellation ≠ Failure

例如：

```text
shutdown requested
user cancelled
deadline cancelled
task superseded
```

可能不是：

```text
component error
```

而是：

```text
control outcome
```

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

---

## 10. Timeout ≠ Cancellation ≠ Failure

这三个概念也应区分：

```text
timeout:
    operation did not complete before deadline

cancellation:
    caller requested stop

failure:
    operation cannot fulfill contract
```

timeout 后尤其可能出现：

```text
ambiguous completion
```

---

## 11. Shutdown 不是 Error Storm

关闭过程中：

```text
socket closed
queue rejected
operation cancelled
```

很多都可能是：

```text
expected shutdown outcomes
```

如果全部记录成 ERROR：

```text
observability signal distorted
```

成熟系统应区分：

```text
failure during normal operation
vs
expected shutdown cancellation
```

---

## 12. Callback Boundary

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

---

## 13. C ABI

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

---

## 14. Plugin ABI

插件环境还存在：

```text
compiler mismatch
runtime mismatch
standard library mismatch
allocator mismatch
exception ABI mismatch
```

因此稳定 plugin ABI 通常应该拥有：

```text
explicit C-compatible boundary
```

或者严格控制整个 toolchain/runtime。

---

## 15. Process Boundary

Exception 无法跨 process 直接传播。

必须：

```text
serialize failure
```

因此错误协议需要：

```text
stable error identity
versioning
context
retry semantics
```

这就是为什么：

```text
internal C++ type hierarchy
```

不能直接成为 RPC error protocol。

---

## 16. RPC Error Model

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

不要压成：

```text
RPC failed
```

否则上层无法制定 recovery policy。

---

## 17. Ambiguous Remote Completion

最重要的分布式错误之一：

```text
request sent
remote side commits
response lost
caller times out
```

现在：

```text
caller sees failure
```

但：

```text
side effect may have happened
```

因此：

```text
retry
```

可能产生重复副作用。

---

## 18. Idempotency

任何自动 retry 之前必须回答：

```text
operation idempotent?
```

如果不是：

```text
idempotency key
request ID
deduplication
transaction token
```

通常是必要协议组成部分。

---

## 19. Retry Budget

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

这些都属于：

```text
recovery policy
```

而不是底层 transport 自动行为。

---

## 20. Supervisor

并发系统中：

```text
worker
```

应尽量只：

```text
detect/report local failure
```

更高层 supervisor：

```text
restart?
drop task?
stop subsystem?
stop process?
```

这样 recovery authority 清晰。

---

## 21. Failure Domain Hierarchy

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

每种 error 必须知道：

```text
maximum blast radius
```

例如：

```text
malformed packet
    → packet

worker unexpected exception
    → worker/task

central invariant corruption
    → process
```

---

## 22. Logging Boundary

一个 failure 如果沿五层传播：

```text
不要每层都 ERROR log
```

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

---

## 23. FM-8 Review Checklist

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

---

## 24. FM-8 核心不变量

> Thread、ABI、process、RPC 都是 failure boundaries。

> Cancellation、timeout 和 failure 应分别建模。

> Retry 属于 policy，必须建立在 idempotency 和 deadline 之上。

> Remote timeout 不能证明 remote operation 没有执行。

> 并发系统应明确 supervisor 和 failure domain。

---

---
