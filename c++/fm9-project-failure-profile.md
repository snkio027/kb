# FM-9 — Project-Level Failure Profile

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-8](fm8-failure-boundaries.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. Failure Profile 应解决什么](#1-failure-profile-应解决什么)
- [2. 推荐项目分类](#2-推荐项目分类)
- [3. 推荐 Layer Policy](#3-推荐-layer-policy)
- [4. Exception Policy](#4-exception-policy)
- [5. expected Policy](#5-expected-policy)
- [6. Error Type Policy](#6-error-type-policy)
- [7. Error Namespace](#7-error-namespace)
- [8. Error Translation Policy](#8-error-translation-policy)
- [9. State Guarantee Policy](#9-state-guarantee-policy)
- [10. Ownership Failure Policy](#10-ownership-failure-policy)
- [11. noexcept Policy](#11-noexcept-policy)
- [12. Assertion Policy](#12-assertion-policy)
- [13. UB Policy](#13-ub-policy)
- [14. Boundary Policy](#14-boundary-policy)
- [15. Retry Policy](#15-retry-policy)
- [16. Timeout Policy](#16-timeout-policy)
- [17. Cancellation Policy](#17-cancellation-policy)
- [18. Logging Policy](#18-logging-policy)
- [19. Metrics Policy](#19-metrics-policy)
- [20. Diagnostics Policy](#20-diagnostics-policy)
- [21. Testing Failure Paths](#21-testing-failure-paths)
- [22. Fault Injection](#22-fault-injection)
- [23. Sanitizers](#23-sanitizers)
- [24. Static Analysis](#24-static-analysis)
- [25. \[\[nodiscard\]\]](#25-nodiscard)
- [26. Public API Failure Documentation Template](#26-public-api-failure-documentation-template)
- [27. Subsystem Failure Profile Template](#27-subsystem-failure-profile-template)
- [28. Project-Wide Baseline](#28-project-wide-baseline)
- [29. Project Anti-Patterns](#29-project-anti-patterns)
- [30. Project Review Checklist](#30-project-review-checklist)
- [31. FM-9 核心不变量](#31-fm-9-核心不变量)
- [Modern C++ Failure Model — 最终总图](#modern-c-failure-model--最终总图)

---

## 0. 文档定位

FM-0 ～ FM-8 描述语言与系统机制。

本章是**待采纳的工程 profile 模板**，不是已批准项目基线。下文“必须／不得／默认”等政策措辞仅约束明确采纳该 profile 的项目；语言与库规则另有标准依据。解析拒绝倾向 expected、析构不传播异常等默认策略，不能冒充所有 C++ 程序统一适用的规范事实。

FM-9 的目标是：

> 将这些规则压缩成一个项目真正可以执行的 Failure Profile。

如果没有统一 profile，工程最终容易变成：

```text
模块 A 用 exception
模块 B 用 bool
模块 C 用 expected<string>
模块 D 用 errno
模块 E catch(...)
模块 F abort()
```

每种单独看可能合理，

组合后却没有一致系统语义。

---

## 1. Failure Profile 应解决什么

项目必须统一回答：

```text
什么是 domain outcome？
什么是 recoverable failure？
什么是 programmer error？
哪些 API 可以 throw？
哪些 API 使用 expected？
哪些 boundary 禁止 exception？
哪些 invariant release 也必须检查？
哪些操作提供 strong/basic guarantee？
哪些 failure 可以 retry？
何时 terminate？
```

---

## 2. 推荐项目分类

以下是项目的处置标签，不是互斥且完整的原因分类。P 描述责任，F 描述严重性／终局处置；同一事件可能同时是 P 与 F。选定恢复／终止策略时应保留来源、频率和状态等独立信息。

```text
D — Domain Outcome
R — Recoverable Operational Failure
P — Programmer / Contract Failure
F — Fatal System Failure
```

---

### D — Domain Outcome

例如：

```text
not found
queue empty
optional field missing
EOF
```

默认：

```text
optional
bool
enum
```

---

### R — Recoverable Failure

例如：

```text
invalid external input
I/O failure
network timeout
configuration rejection
resource unavailable
```

默认：

```text
expected<T, E>
error_code
exception where project policy allows
```

---

### P — Programmer Error

例如：

```text
precondition violation
invalid internal index
broken state-machine invariant
double ownership
```

默认：

```text
assert
production fatal check where necessary
```

不应默认：

```text
expected<..., Bug>
```

---

### F — Fatal Failure

例如：

```text
central invariant corruption
unrecoverable process state
exception escaping noexcept
critical runtime corruption
```

默认：

```text
terminate
abort
process-level fail-fast policy
```

---

## 3. 推荐 Layer Policy

可以定义：

| Layer | 默认 Failure Style |
|---|---|
| Parser / Validation | `std::expected<T, E>` |
| Domain lookup | `std::optional<T>` / `expected` |
| Core trusted algorithms | Preconditions + assertions |
| Resource wrappers | RAII + constructor/factory |
| OS abstraction | `error_code` / `expected` |
| Application orchestration | `expected` 或 exception，根据项目统一政策 |
| Thread entry | Catch/contain unexpected exception |
| C/plugin ABI | Explicit status/error object |
| RPC boundary | Serialized structured errors |
| Fatal invariant boundary | Fail-fast |

---

## 4. Exception Policy

项目必须明确选择。

例如：

```text
Exceptions:
    enabled

Allowed:
    construction failure
    rare infrastructure failure
    orchestration propagation

Not allowed:
    parser rejection
    normal lookup miss
    hot-path control flow

Must not cross:
    thread entry
    C ABI
    plugin ABI
    RPC
```

或者：

```text
Application code:
    exception-free by policy

Third-party exceptions:
    caught and translated at adapter boundary
```

关键不是哪一种绝对最好，

而是：

> policy 必须一致。

---

## 5. `expected` Policy

推荐规定：

```text
Use expected when:
    failure is expected at runtime
    caller can meaningfully branch/recover
    failure belongs to API result domain
```

避免：

```text
every function returns expected
```

特别是：

```text
private helper whose preconditions are already established
```

不需要重新包装 internal impossible state。

---

## 6. Error Type Policy

推荐：

```text
error identity:
    enum / structured code

diagnostic context:
    structured fields

human text:
    produced at diagnostic boundary
```

避免默认：

```cpp
std::expected<T, std::string>
```

成为跨大型系统统一协议。

---

## 7. Error Namespace

可以：

```cpp
namespace parser {

enum class ErrorCode {
    truncated,
    invalid_header,
};

struct Error {
    ErrorCode code;
    std::size_t offset;
};

}
```

不同 subsystem：

```text
parser::Error
storage::Error
network::Error
```

不要创建一个无限膨胀：

```cpp
enum class GlobalError {
    ...
};
```

---

## 8. Error Translation Policy

规定：

> 只有跨越 abstraction boundary 时翻译。

例如：

```text
socket error
↓
HTTP client error
↓
repository unavailable
```

不要：

```text
每一个函数层次
↓
创建新 Error wrapper
```

---

## 9. State Guarantee Policy

本节是待项目采纳的 profile 建议，不是所有 C++ API 的语言要求。建议每个重要的 mutating API 分别声明：

| 维度 | 合同内容 |
| --- | --- |
| 失败后状态 | strong、basic、明确部分进度或其他具体语义 |
| 异常传播 | 是否允许异常越界；是否具有 `noexcept` 规格 |
| 资源与所有权 | 失败后资源属于谁，哪些清理动作有保证 |
| 终局策略 | 无法继续时升级、重启或终止的范围 |

例如 `update(Config)` 返回 `expected<void, UpdateError>` 时，仍须单独说明“失败时旧配置不变”，或者“保留哪些部分进度且哪些不变量继续成立”。不从返回类型推出 strong，不从 `noexcept` 推出 no-fail，也不把 termination 排为状态保证的一级。

精确定义及 commit 条件见 [FM-4 §4～§5](fm4-raii-exception-safety.md#4-exception-safety-guarantees)。

---

## 10. Ownership Failure Policy

任何 transferring API 都必须说明：

```text
ownership before call
ownership after success
ownership after failure
```

例如：

```text
enqueue(Job job)
```

和：

```text
try_enqueue(Job& job)
```

具有完全不同的 failure ownership semantics。

---

## 11. `noexcept` Policy

推荐：

```text
Destructors:
    must not propagate exceptions

Move operations:
    noexcept when semantically true

Swap:
    non-throwing and truly non-failing under commit preconditions

Cleanup:
    noexcept

Leaf arithmetic / trivial accessors:
    noexcept where contract truly permits

Do not:
    add noexcept merely for performance
```

---

## 12. Assertion Policy

定义两种检查。

### Development Assertion

```text
debug-only
internal reasoning
cheap diagnostics
```

例如：

```cpp
assert(index < size);
```

---

### Production Fatal Check

用于：

```text
release must enforce
continuing could corrupt persistent/external state
security-sensitive invariant
central internal invariant
```

应由项目统一宏/函数提供：

```text
CHECK
ENSURE
FATAL_IF
```

具体名字不是重点。

---

## 13. UB Policy

项目原则：

```text
UB is never a failure-handling strategy.
```

应该：

```text
validate untrusted input
assert trusted preconditions
use sanitizers
use static analysis
use ownership/lifetime discipline
```

目标是：

```text
prevent UB
```

而不是：

```text
recover from UB
```

---

## 14. Boundary Policy

必须列出所有重要边界：

```text
thread
coroutine task
event loop
C ABI
plugin ABI
IPC
RPC
process main
```

每个边界写明：

```text
incoming failure forms
outgoing failure forms
exception policy
logging responsibility
failure domain
```

---

## 15. Retry Policy

项目统一规定：

```text
retry only when category is retryable
```

同时检查：

```text
idempotency
deadline
attempt count
backoff
jitter
shutdown
system load
```

禁止基础库：

```text
while (!success) retry();
```

---

## 16. Timeout Policy

Timeout 应明确：

```text
deadline expired
```

但不能自动断言：

```text
remote operation failed before commit
```

对于有外部副作用的操作：

```text
timeout semantics
```

必须说明：

```text
definitely not committed
possibly committed
definitely committed
```

如果无法知道：

```text
ambiguous
```

应直接建模。

---

## 17. Cancellation Policy

推荐作为独立 outcome：

```text
success
failure
cancelled
```

尤其：

```text
worker shutdown
async operation
coroutine
RPC
```

避免把正常 shutdown 变成错误风暴。

---

## 18. Logging Policy

基本原则：

```text
errors are propagated many times
but usually logged once
```

通常：

```text
detection layer:
    produce structured error

intermediate layer:
    enrich context

recovery/terminal boundary:
    log
```

---

## 19. Metrics Policy

Metrics 应按：

```text
error category
operation
component
recovery action
```

聚合。

避免使用：

```text
raw error message
```

作为 metric label，

否则容易产生：

```text
unbounded cardinality
```

---

## 20. Diagnostics Policy

最终 diagnostics 可以组合：

```text
error code
cause chain
operation
resource identity
request/job ID
location
context
```

但要明确：

```text
secret redaction
PII policy
size limits
```

---

## 21. Testing Failure Paths

Failure path 必须是：

```text
first-class test target
```

而不是只测试 success path。

至少包括：

```text
invalid input
allocation/resource failure where injectable
I/O error
timeout
cancellation
partial progress
throwing T in generic code
thread exception
shutdown race
```

---

## 22. Fault Injection

高质量组件应允许测试：

```text
fail allocation N
fail write N
timeout operation N
disconnect after commit
throw during element move
```

这样才能验证：

```text
strong/basic guarantee
cleanup
retry
failure domain
```

---

## 23. Sanitizers

Failure Model 无法替代：

```text
ASan
UBSan
TSan
```

这些主要帮助发现：

```text
memory safety
UB
data race
```

它们属于：

```text
defect detection infrastructure
```

而不是 runtime recovery system。

---

## 24. Static Analysis

推荐结合：

```text
clang-tidy
compiler warnings
lifetime-oriented checks
nodiscard
concepts
type system
```

尽可能将：

```text
failure handling omission
invalid state
ownership bug
```

提前到开发阶段。

---

## 25. `[[nodiscard]]`

对 failure-carrying result：

```cpp
[[nodiscard]]
std::expected<void, Error> save();
```

通常非常有价值。

因为：

```cpp
save();
```

无意丢弃结果会产生编译器诊断。

对于：

```text
must-observe outcome
```

建议采用。

---

## 26. Public API Failure Documentation Template

每个关键 API 可以统一：

```markdown
### Failure Contract

Preconditions:
- ...

Success:
- ...

Recoverable failures:
- ...

Programmer errors:
- ...

Failure representation:
- ...

State guarantee:
- strong/basic/...

Ownership after failure:
- ...

Thread safety:
- ...

Cancellation:
- ...

Retry semantics:
- ...

Failure domain:
- ...
```

---

## 27. Subsystem Failure Profile Template

```markdown
## Failure Profile

### Error Types

- ...

### Exception Policy

- ...

### Validation Boundary

- ...

### Recovery Boundary

- ...

### Failure Domain

- ...

### State Guarantees

- ...

### Retry / Timeout

- ...

### Logging / Metrics

- ...

### Fatal Invariants

- ...
```

---

## 28. Project-Wide Baseline

推荐默认：

```text
External input
    → validate

Normal absence
    → optional

Expected recoverable failure
    → expected

OS/native failure
    → error_code at low layer
    → translate when abstraction changes

Rare deep failure
    → exception only if project profile permits

Programmer error
    → assert / fatal check

Unrecoverable invariant loss
    → fail-fast

Resources
    → RAII

Mutating operations
    → document strong/basic guarantee

Move/swap/cleanup
    → noexcept where semantically true

Threads/ABI/RPC
    → explicit failure boundaries
```

---

## 29. Project Anti-Patterns

禁止形成：

```text
exceptions everywhere
```

或者：

```text
expected everywhere
```

或者：

```text
no exceptions at all costs
```

这些都是机制驱动设计。

正确顺序：

```text
failure semantics
↓
responsibility
↓
state guarantee
↓
boundary
↓
frequency
↓
transport mechanism
```

---

## 30. Project Review Checklist

```text
[ ] 项目是否有统一 failure taxonomy？
[ ] domain outcome / operational failure / programmer error 是否分离？
[ ] exception policy 是否明确？
[ ] expected 使用边界是否明确？
[ ] errors 是否结构化？
[ ] error translation 是否按 abstraction boundary？
[ ] public mutating APIs 是否定义 state guarantee？
[ ] ownership failure semantics 是否明确？
[ ] noexcept policy 是否明确，且未与 no-fail 或 strong/basic 混为一谈？
[ ] assert 与 production fatal check 是否区分？
[ ] UB 是否被明确视为 defect 而非 failure channel？
[ ] thread / ABI / RPC boundary 是否明确，并覆盖错误报告自身的失败？
[ ] cancellation / timeout / shutdown 是否单独建模？
[ ] retry 是否有 idempotency + deadline + budget？
[ ] logging 是否集中在 recovery/terminal boundary？
[ ] error metrics 是否避免高 cardinality？
[ ] failure paths 是否有测试？
[ ] 是否支持关键 fault injection？
[ ] sanitizer/static analysis 是否进入 CI？
```

---

## 31. FM-9 核心不变量

> 项目必须有统一 Failure Profile，而不是每个模块自行发明错误模型。

> Mechanism selection 必须发生在 failure semantics 之后。

> Recoverable failure、programmer error 与 fatal failure 必须严格分离。

> State guarantee 和 ownership guarantee 是 public API contract 的组成部分。

> Thread、ABI、RPC 和 process 都必须具有明确 failure boundary。

> Retry、timeout、cancellation 和 shutdown 都是系统级语义，不能留给底层库随意决定。

---

## Modern C++ Failure Model — 最终总图

FM-0 ～ FM-9 可以最终压缩为：

```text
                           Operation
                               │
                       What can happen?
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
 Domain Outcome       Operational Failure      Programmer Error
        │                      │                      │
 optional/bool             expected              contract
                           error_code             assert
                           exception              fatal check
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               │
                        State Guarantee
                               │
              ┌────────────────┼─────────────────┐
              │                │                 │
            strong           basic          unrecoverable
              │                │                 │
              └────────────────┼─────────────────┘
                               │
                         RAII / Ownership
                               │
                       Recovery Boundary
                               │
                     Recovery Policy
             retry / fallback / rollback / reject
                               │
                         Failure Domain
                               │
       operation → task → worker → subsystem → process
                               │
                        Boundary Crossing
                thread / ABI / RPC / process
                               │
                      translate / contain
```

而贯穿所有章节的最终原则是：

```text
1. Prevent impossible states where possible.

2. Validate uncertainty at boundaries.

3. Represent expected failures explicitly.

4. Preserve invariants and ownership on every exit path.

5. Recover only where enough context exists.

6. Contain failure within the intended failure domain.

7. Terminate explicitly when trustworthy execution can no longer continue.
```

这就是现代 C++ Failure Model 的工程基线。
