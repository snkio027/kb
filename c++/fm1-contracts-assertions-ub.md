# FM-1 — Contracts / Preconditions / Assertions / Undefined Behavior

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-0](fm0-failure-model.md) · [下一章：FM-2](fm2-value-based-failure.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. Contract 是什么](#1-contract-是什么)
- [2. Preconditions](#2-preconditions)
- [3. Postconditions](#3-postconditions)
- [4. Invariants](#4-invariants)
- [5. Contract 的责任方向](#5-contract-的责任方向)
- [6. Runtime Failure 与 Contract Violation](#6-runtime-failure-与-contract-violation)
- [7. 判断标准](#7-判断标准)
- [8. 核心问题](#8-核心问题)
- [9. Validation](#9-validation)
- [10. Assertion](#10-assertion)
- [11. Validation 与 Assertion 的工程区分](#11-validation-与-assertion-的工程区分)
- [12. assert](#12-assert)
- [13. NDEBUG](#13-ndebug)
- [14. Assertion 不得承载必要副作用](#14-assertion-不得承载必要副作用)
- [15. assert 不适合处理外部输入](#15-assert-不适合处理外部输入)
- [16. Validation Boundary](#16-validation-boundary)
- [17. Validate Once，Trust Afterwards](#17-validate-oncetrust-afterwards)
- [18. Checked Boundary + Trusted Core](#18-checked-boundary--trusted-core)
- [19. operator\[\] 与 at()](#19-operator-与-at)
- [20. Checked 与 Unchecked API 都有合理用途](#20-checked-与-unchecked-api-都有合理用途)
- [21. Undefined Behavior](#21-undefined-behavior)
- [22. UB 可能产生什么结果](#22-ub-可能产生什么结果)
- [23. UB 与 Runtime Error 的根本区别](#23-ub-与-runtime-error-的根本区别)
- [24. UB 会影响优化推理](#24-ub-会影响优化推理)
- [25. assert 与 UB](#25-assert-与-ub)
- [26. Assertion 不会改变 API Contract](#26-assertion-不会改变-api-contract)
- [27. 常见 UB 来源](#27-常见-ub-来源)
- [28. 为什么 C++ 允许 Contract-Based Unchecked Operations](#28-为什么-c-允许-contract-based-unchecked-operations)
- [29. Fail-Fast](#29-fail-fast)
- [30. Fail-Fast 不等于 UB](#30-fail-fast-不等于-ub)
- [31. Debug Assertion 与 Production Check](#31-debug-assertion-与-production-check)
- [32. Assertion 与 Production Invariant Check](#32-assertion-与-production-invariant-check)
- [33. std::terminate](#33-stdterminate)
- [34. std::unreachable — C++23](#34-stdunreachable--c23)
- [35. std::unreachable 不是 Fail-Fast](#35-stdunreachable-不是-fail-fast)
- [36. 三种机制对比](#36-三种机制对比)
- [37. std::unreachable 的使用原则](#37-stdunreachable-的使用原则)
- [38. Internal 不等于 Trusted](#38-internal-不等于-trusted)
- [39. 信任应该建立在 Boundary 上](#39-信任应该建立在-boundary-上)
- [40. Type as Invariant](#40-type-as-invariant)
- [41. Invalid States Should Be Hard to Represent](#41-invalid-states-should-be-hard-to-represent)
- [42. 优先级](#42-优先级)
- [43. Engineering Decision Model](#43-engineering-decision-model)
- [44. API Design Pattern](#44-api-design-pattern)
- [45. Anti-Patterns](#45-anti-patterns)
- [46. Review Checklist](#46-review-checklist)
- [47. FM-1 核心不变量](#47-fm-1-核心不变量)
- [48. 最终心智模型](#48-最终心智模型)
- [49. FM-1 最终压缩](#49-fm-1-最终压缩)

---

## 0. 文档定位

本文解决现代 C++ Failure Model 中一个基础问题：

> 什么情况应该被建模为“可恢复失败”，什么情况应该被视为“程序违反了自身契约”？

如果这个边界不清楚，工程中很容易出现以下问题：

- 用 `assert` 检查不可信输入；
- 把程序 bug 包装成 `std::expected` 一路传播；
- 把 UB 当作一种“性能更高的错误处理”；
- release 构建中因为 `assert` 消失而暴露安全问题；
- 在 trusted core 中重复进行大量无意义检查；
- 在 validation boundary 之后仍然传播“半可信”数据。

FM-1 的目标是建立：

```text
external uncertainty
    ↓
validation
    ↓
trusted representation
    ↓
contract-based core
```

并明确区分：

```text
runtime failure
contract violation
undefined behavior
fail-fast
```

---

## 1. Contract 是什么

一个函数的完整接口不只是：

```cpp
R f(A a);
```

真正的 contract 至少包含：

```text
preconditions
postconditions
invariants
failure semantics
```

---

## 2. Preconditions

Precondition 表示：

> 调用者在调用函数之前必须保证的条件。

例如：

```cpp
int front(std::span<const int> values) {
    return values.front();
}
```

一个关键 precondition 是：

```text
!values.empty()
```

如果调用者违反这个条件，含义不是：

```text
front() 正常尝试工作但失败
```

而是：

```text
调用本身违反 API contract
```

因此：

```text
recoverable runtime failure
```

和：

```text
precondition violation
```

必须严格区分。

---

## 3. Postconditions

Postcondition 表示：

> 函数正常完成以后，函数必须保证成立的条件。

例如：

```cpp
void sort_values(std::span<int> values);
```

正常返回以后：

```text
values satisfies required ordering
```

又例如：

```cpp
File open_file(...);
```

正常返回以后：

```text
returned File owns a valid resource
```

如果函数正常返回却没有满足 postcondition：

```text
callee bug
```

而不是调用者错误。

---

## 4. Invariants

Invariant 表示：

> 一个类型或组件在所有公开可观察的合法状态中都必须成立的条件。

例如：

```cpp
class Buffer {
private:
    std::byte* data_;
    std::size_t size_;
};
```

可能定义：

```text
size_ == 0
    ⇔
data_ == nullptr
```

或者：

```text
size_ > 0
    ⇒
data_ != nullptr
```

对于：

```cpp
class RingBuffer
```

可能有：

```text
size_ <= capacity_

head_ < capacity_

tail_ < capacity_
```

Invariant 是：

```text
valid object state
```

的定义。

---

## 5. Contract 的责任方向

对于：

```cpp
R f(A a);
```

责任可以理解为：

```text
caller
  │
  │ establishes preconditions
  ▼
callee
  │
  │ performs operation
  ▼
postconditions
  │
  ▼
object/component invariants remain valid
```

因此：

```text
Precondition
    → caller responsibility

Postcondition
    → callee responsibility

Invariant
    → type/component responsibility
```

---

## 6. Runtime Failure 与 Contract Violation

这是 FM-1 最重要的分界。

### Runtime Failure

环境本来就可能不满足要求。

例如：

```text
network packet truncated
file missing
permission denied
invalid configuration
remote timeout
malformed user input
```

程序必须正常面对这些情况。

典型处理：

```text
validate
→ structured failure
→ propagate / recover
```

---

### Contract Violation

根据 API 或程序设计：

```text
这个条件本来必须成立
```

但调用者或内部实现破坏了它。

例如：

```text
invalid internal index
illegal state transition
dangling reference
double ownership
impossible enum/state combination
```

这属于：

```text
programmer error
```

而不是普通业务失败。

---

## 7. 判断标准

不要只看错误表面形式。

例如：

```text
index out of range
```

可能属于完全不同的失败模型。

### 外部输入

```cpp
index = request.index;
```

如果来自 HTTP、文件、网络或数据库：

```text
runtime data
```

必须先判断其可信度。

如果可能非法：

```text
validation
```

---

### 内部已验证状态

如果：

```cpp
index = validated_table[id];
```

并且程序 invariant 已保证：

```text
index < size
```

那么越界说明：

```text
program bug
```

---

## 8. 核心问题

判断一个条件属于 precondition 还是 runtime validation 时，优先问：

> 谁有责任保证这个条件成立？

如果调用者根据 API contract 必须保证：

```text
precondition
```

如果外部环境天然可能违反：

```text
runtime validation
```

---

## 9. Validation

Validation 用于处理：

```text
untrusted or runtime-controlled data
```

包括：

```text
network packets
files
user input
RPC requests
database records
configuration
external service responses
serialized state
```

典型流程：

```text
untrusted data
      ↓
validation
      ↓
valid internal representation
```

失败应该产生：

```text
structured recoverable failure
```

例如：

```cpp
std::expected<Frame, ParseError>
parse_frame(std::span<const std::byte> bytes);
```

---

## 10. Assertion

Assertion 的用途不同：

> 检查程序自己已经推理为“必须成立”的条件。

例如：

```cpp
assert(index < messages.size());

return messages[index];
```

含义是：

```text
如果这里失败，
说明程序内部推理或 invariant 被破坏。
```

不是：

```text
用户给了坏数据，请优雅处理。
```

---

## 11. Validation 与 Assertion 的工程区分

可以压缩为：

```text
validation
    protects the program from external uncertainty

assertion
    checks the program against its own assumptions
```

这是本节最重要的工程规则之一。

---

## 12. `assert`

C++：

```cpp
#include <cassert>

assert(condition);
```

主要用于开发阶段检查内部条件。

如果 assertion enabled 且条件为 false：

```text
diagnostic
→ abort
```

具体输出形式由实现决定。

---

## 13. `NDEBUG`

如果在包含 `<cassert>` 前定义：

```cpp
#define NDEBUG
```

那么：

```cpp
assert(expr);
```

将被禁用。

因此：

```cpp
assert(validate_input());
```

是错误设计。

因为 release 构建中：

```text
validate_input()
```

可能根本不会执行。

---

## 14. Assertion 不得承载必要副作用

错误：

```cpp
assert(++index < size);
```

debug：

```text
index incremented
```

release：

```text
index unchanged
```

导致程序语义依赖 build mode。

同样：

```cpp
assert(initialize_resource());
```

也是危险设计。

原则：

> `assert` 中的表达式应当主要用于观察和验证，而不是承担程序正确运行所依赖的副作用。

---

## 15. `assert` 不适合处理外部输入

错误：

```cpp
void decode_packet(std::span<const std::byte> packet) {
    assert(packet.size() >= kHeaderSize);

    ...
}
```

如果 packet 来自网络：

```text
packet too short
```

属于：

```text
runtime input failure
```

而不是：

```text
programmer bug
```

正确模型：

```cpp
std::expected<Packet, ParseError>
decode_packet(std::span<const std::byte> packet) {
    if (packet.size() < kHeaderSize) {
        return std::unexpected(ParseError::truncated);
    }

    ...
}
```

---

## 16. Validation Boundary

成熟系统应该明确：

```text
untrusted world
      ↓
validation boundary
      ↓
trusted domain object
      ↓
trusted core
```

例如：

```text
raw bytes
    ↓
parse + validate
    ↓
Frame
```

成功得到：

```cpp
Frame frame;
```

最好已经意味着：

```text
length valid
version valid
fields consistent
checksum validated
required ranges valid
```

---

## 17. Validate Once，Trust Afterwards

一种高质量设计模式：

```text
external representation
        ↓
checked boundary
        ↓
validated type
        ↓
trusted core
```

不要让：

```cpp
RawPacket
```

贯穿整个程序，并在每一层重复：

```cpp
if (!packet.valid()) {
    ...
}
```

更好的设计：

```cpp
class Frame {
public:
    static std::expected<Frame, ParseError>
    parse(std::span<const std::byte> bytes);

private:
    Frame(...);
};
```

成功构造 `Frame` 本身就表达：

```text
Frame invariant holds
```

---

## 18. Checked Boundary + Trusted Core

高性能系统中非常常见：

```text
external bytes
      ↓
checked parser
      ↓
validated representation
      ↓
unchecked hot path
```

例如：

```cpp
std::expected<Message, ParseError>
parse_message(std::span<const std::byte> bytes);
```

负责：

```text
length validation
version validation
field range checks
header validation
```

而内部：

```cpp
decode(const Message& message);
```

直接依赖：

```text
Message invariant
```

这可以同时获得：

```text
correctness
performance
clear ownership of validation
```

---

## 19. `operator[]` 与 `at()`

这是 contract-based API 与 checked API 的经典对比。

```cpp
std::vector<int> values{1, 2, 3};
```

---

### `operator[]`

```cpp
values[index];
```

调用者负责保证：

```text
index < values.size()
```

在 C++23 语义基线下，如果越界：

```text
undefined behavior
```

它不是一个正常错误返回通道。

---

### `at()`

```cpp
values.at(index);
```

由容器主动检查：

```text
index < size()
```

越界：

```cpp
throw std::out_of_range
```

因此：

```text
operator[]
    caller establishes precondition

at()
    callee validates index
```

---

## 20. Checked 与 Unchecked API 都有合理用途

如果：

```cpp
if (index >= values.size()) {
    return std::unexpected(Error::invalid_index);
}

auto& value = values[index];
```

那么检查已经发生。

这里：

```cpp
operator[]
```

是合理的 trusted-core 操作。

如果：

```cpp
return values[request.index];
```

而 index 直接来自外部，则不合理。

因此问题不是：

```text
at() 永远比 [] 好
```

而是：

```text
check 在哪个 boundary 完成？
```

---

## 21. Undefined Behavior

UB 不是错误处理机制。

它表示：

> 程序已经执行了 C++ 标准不再规定语义的操作。

例如：

```cpp
std::vector<int> values{1, 2, 3};

int x = values[100];
```

这里不是：

```text
C++ 返回一个随机值
```

而是：

```text
language guarantees have ended
```

---

## 22. UB 可能产生什么结果

UB 以后可能：

```text
看起来正常
crash
读垃圾值
写坏内存
删除某些代码路径
产生违反直觉的优化结果
```

不能依赖其中任何一种。

---

## 23. UB 与 Runtime Error 的根本区别

Runtime failure：

```text
程序仍然处在 C++ 定义的语义世界中
```

例如：

```cpp
throw std::out_of_range{};
```

调用者可以根据标准语义继续推理。

UB：

```text
程序已经离开抽象机保证
```

所以不存在可靠 recovery model。

---

## 24. UB 会影响优化推理

例如：

```cpp
int f(int* p) {
    int x = *p;

    if (p == nullptr) {
        return 0;
    }

    return x;
}
```

`*p` 已经要求：

```text
p != nullptr
```

所以在任何定义良好的执行中：

```text
p cannot be null
```

编译器可以据此优化后面的：

```cpp
if (p == nullptr)
```

这说明：

> UB 不只是“运行时出了问题”，它还改变了编译器对程序合法路径的推理。

---

## 25. `assert` 与 UB

两者完全不同。

```cpp
assert(index < size);
```

失败：

```text
defined termination behavior
```

而：

```cpp
array[index]
```

非法索引：

```text
undefined behavior
```

因此 assertion 常被用来：

```text
detect violation before UB occurs
```

---

## 26. Assertion 不会改变 API Contract

例如：

```cpp
T& get(std::size_t index) {
    assert(index < size_);
    return data_[index];
}
```

真实 contract 仍然是：

```text
Precondition:
    index < size_
```

`assert` 只是：

```text
debug-time checking of that contract
```

它不是：

```text
runtime validation API
```

因为 release 构建可能没有这个检查。

---

## 27. 常见 UB 来源

### Memory

```text
out-of-bounds access
use-after-free
dangling pointer/reference
invalid pointer arithmetic
misaligned access
```

---

### Lifetime

```text
use outside object lifetime
use destroyed object
incorrect manual lifetime management
```

---

### Arithmetic

例如：

```cpp
int x = INT_MAX;
++x;
```

signed integer overflow：

```text
UB
```

而无符号整数：

```text
modulo arithmetic
```

不是 UB。

---

### Object Model

可能包括：

```text
invalid type punning
alignment violations
incorrect object representation assumptions
```

---

### Concurrency

未同步的数据竞争：

```text
data race
```

通常就是：

```text
UB
```

不能把它理解为：

```text
偶尔读取旧数据
```

---

## 28. 为什么 C++ 允许 Contract-Based Unchecked Operations

C++ 的重要目标之一：

```text
zero-overhead abstractions
```

如果：

```cpp
values[index];
```

每次都进行：

```cpp
if (index >= values.size())
```

即使调用者刚刚已经证明 index 合法，也会导致重复检查。

因此允许：

```text
caller proves
callee assumes
```

这本身不是错误设计。

问题在于：

```text
是否把 untrusted data 直接带入这种 API
```

---

## 29. Fail-Fast

当内部 invariant 被破坏时，继续运行有时比终止更危险。

例如：

```text
ownership corrupted
state machine impossible state
critical accounting invariant broken
heap corruption suspected
```

此时合理策略可能是：

```text
detect
→ record diagnostics
→ terminate affected failure domain
```

这叫：

```text
fail-fast
```

---

## 30. Fail-Fast 不等于 UB

应优先区分：

```text
explicit termination
```

和：

```text
undefined behavior
```

一个系统发现 impossible state 后：

```cpp
std::terminate();
```

比故意继续执行直到 UB 更有定义、更容易诊断。

---

## 31. Debug Assertion 与 Production Check

标准：

```cpp
assert(condition);
```

可能在 release 消失。

但有些 invariant：

```text
即使 production 也必须验证
```

例如继续运行可能造成：

```text
persistent data corruption
security violation
irreversible external side effect
```

那么项目通常需要：

```text
always-on fatal check
```

概念上：

```cpp
CHECK(condition);
```

其行为：

```text
debug:
    check

release:
    still check

failure:
    diagnostic + terminate
```

`CHECK` 不是标准 C++ API，通常属于项目基础设施。

---

## 32. Assertion 与 Production Invariant Check

推荐区分：

```text
assert
    development correctness aid

always-on fatal check
    production invariant enforcement
```

不要因为：

```text
这是内部 invariant
```

就自动认为：

```text
release 可以不检查
```

是否需要 always-on 检查取决于 violation 的后果。

---

## 33. `std::terminate`

`std::terminate()` 表示：

```text
program cannot continue through normal C++ execution
```

它具有定义明确的终止语义。

典型触发包括：

```text
exception escapes noexcept function
uncaught exception escapes std::thread entry
explicit fail-fast decision
```

它属于：

```text
terminal behavior
```

而不是普通错误 transport。

---

## 34. `std::unreachable` — C++23

C++23：

```cpp
#include <utility>

std::unreachable();
```

表达：

> 合法程序执行绝不可能到达这里。

例如：

```cpp
enum class State {
    idle,
    running,
};

int value(State state) {
    switch (state) {
    case State::idle:
        return 0;

    case State::running:
        return 1;
    }

    std::unreachable();
}
```

---

## 35. `std::unreachable` 不是 Fail-Fast

它不是：

```text
abort
terminate
panic
throw
```

它是在向编译器声明：

```text
this control-flow path is impossible
```

如果真实执行到：

```cpp
std::unreachable();
```

行为是：

```text
undefined behavior
```

因此：

> `std::unreachable` 是语义/优化承诺，不是运行时保护机制。

---

## 36. 三种机制对比

| 机制 | 条件违反时 |
|---|---|
| `assert(false)` | assert enabled 时终止；可能被禁用 |
| `std::terminate()` | 明确定义为程序终止 |
| `std::unreachable()` | 执行到即 UB |

不要互相替代。

---

## 37. `std::unreachable` 的使用原则

只有当你可以证明：

```text
合法程序状态下绝不可能到达
```

才考虑使用。

不要习惯性写：

```cpp
default:
    std::unreachable();
```

尤其当：

```text
enum may receive corrupted value
ABI compatibility exists
serialized state may be stale
external input may participate
```

时更要谨慎。

在很多高可靠系统中：

```text
diagnostic fail-fast
```

比极小的潜在优化价值更重要。

---

## 38. Internal 不等于 Trusted

这一点非常重要。

数据来自：

```text
database
cache
disk
old process version
IPC
shared memory
another service
```

即使这些组件属于“自己的系统”，数据也未必可信。

例如：

```text
数据库字段由旧版本写入
```

当前程序仍然应该把它视作：

```text
runtime externalized state
```

而不是：

```text
guaranteed internal invariant
```

因此：

> “来自内部系统”不等于“满足当前进程 invariant”。

---

## 39. 信任应该建立在 Boundary 上

推荐：

```text
raw persisted/external state
       ↓
validation
       ↓
current-version validated representation
       ↓
trusted core
```

而不是根据：

```text
数据是不是我们自己写的
```

决定是否信任。

---

## 40. Type as Invariant

最好的 invariant 往往不是：

```cpp
assert(valid());
```

而是：

```text
非法状态根本无法通过类型表达
```

例如不要设计：

```cpp
struct Connection {
    Socket socket;
    bool connected;
};
```

因为存在：

```text
socket invalid
connected == true
```

这种矛盾组合。

可以考虑：

```text
DisconnectedConnection
ConnectedConnection
```

让状态转换通过类型发生。

---

## 41. Invalid States Should Be Hard to Represent

现代 C++ 类型设计应尽量：

```text
encode invariants into construction and type structure
```

利用：

```text
private constructors
factory functions
strong types
enum class
variant
RAII
ownership types
validated domain types
```

将错误从：

```text
runtime checking problem
```

提升为：

```text
construction/type-system problem
```

---

## 42. 优先级

如果一个非法状态能够：

```text
编译期消除
```

优先编译期。

否则：

```text
构造阶段消除
```

再否则：

```text
validation boundary 消除
```

最后才是：

```text
trusted core assertion
```

可以理解成：

```text
compile-time
    ↓
construction-time
    ↓
boundary validation
    ↓
internal invariant check
```

越早消除越好。

---

## 43. Engineering Decision Model

面对：

```cpp
if (!condition) {
    ...
}
```

首先判断 condition 为什么可能失败。

### Case A — 外部世界可能不满足

```text
validation
→ recoverable failure
```

---

### Case B — API 明确允许任意输入

```text
checked API
→ recoverable failure
```

---

### Case C — 调用者必须保证

```text
precondition
→ contract
```

---

### Case D — 内部逻辑保证成立

```text
invariant
→ assertion / fatal check
```

---

### Case E — 无法恢复且状态可信度已经丢失

```text
fail-fast
```

---

## 44. API Design Pattern

推荐形成两层 API：

```text
checked public/external boundary
        ↓
validated representation
        ↓
fast internal API with clear preconditions
```

例如：

```cpp
std::expected<Message, ParseError>
parse_message(std::span<const std::byte> bytes);
```

然后：

```cpp
void decode(const Message& message);
```

而不是：

```cpp
void decode(std::span<const std::byte> bytes);
```

并在所有深层函数里重复检查原始字节。

---

## 45. Anti-Patterns

### 45.1 Assert Untrusted Input

错误：

```cpp
assert(packet.size() >= 32);
```

如果 packet 来自外部。

---

### 45.2 Depend on Assert Side Effects

错误：

```cpp
assert(initialize());
```

---

### 45.3 Convert Every Programmer Bug to `expected`

错误倾向：

```cpp
std::expected<T, InternalImpossibleState>
```

如果这个状态按设计根本不应该发生。

结果可能只是：

```text
bug 被隐藏并传播
```

---

### 45.4 Treat UB as Fast Error Handling

错误思维：

```text
我们不检查，错了反正 UB，这样最快。
```

UB 不是 failure policy。

合理模型应该是：

```text
validated boundary
+
trusted precondition
```

而不是：

```text
unchecked untrusted input
```

---

### 45.5 Revalidate Everywhere

如果：

```text
ValidFrame
```

已经保证 invariant，

不要所有内部函数都再次验证：

```text
header valid?
length valid?
version valid?
```

这会：

```text
增加复杂性
模糊 trust boundary
增加重复成本
削弱类型语义
```

---

### 45.6 Blind `std::unreachable`

不要用：

```cpp
std::unreachable();
```

掩盖：

```text
其实没有证明 impossible
```

---

## 46. Review Checklist

设计或 Review API 时：

```text
[ ] Preconditions 是否明确？
[ ] Preconditions 由谁负责建立？
[ ] Postconditions 是否明确？
[ ] 类型 invariants 是否明确？
[ ] 外部数据是否经过 validation boundary？
[ ] Internal data 是否真的值得信任？
[ ] 是否错误使用 assert 处理外部 failure？
[ ] assert 是否包含必要副作用？
[ ] release 构建是否会失去必要检查？
[ ] 是否需要 production fatal check？
[ ] UB 是否可能由未验证输入触发？
[ ] checked API 与 trusted API 是否职责明确？
[ ] validated representation 是否尽早建立？
[ ] 是否存在可以由类型系统消除的非法状态？
[ ] std::unreachable 是否有严格证明？
[ ] contract violation 是否被错误地当作业务失败传播？
```

---

## 47. FM-1 核心不变量

### FM1-I1

> External uncertainty 必须通过 validation 进入系统。

### FM1-I2

> Assertion 用来检查内部推理，而不是验证不可信输入。

### FM1-I3

> Precondition violation 与普通 runtime failure 是不同类别。

### FM1-I4

> `assert` 是 debug contract check，不是可靠 production validation。

### FM1-I5

> 不得让程序正确性依赖 assert 中的副作用。

### FM1-I6

> UB 不是 error transport，也不存在通用 recovery contract。

### FM1-I7

> 应在 UB 发生之前检测重要 contract violation。

### FM1-I8

> `std::unreachable` 是“不可到达”的语义承诺，不是 fail-fast API。

### FM1-I9

> 数据是否可信由 validation boundary 决定，不由“是不是自己的系统产生”决定。

### FM1-I10

> Checked boundary 和 trusted core 应明确分层。

### FM1-I11

> 高价值 invariant 应尽可能编码进类型和构造过程。

### FM1-I12

> 如果继续运行已经无法保证系统语义，应显式 fail-fast，而不是进入 UB 后期待恢复。

---

## 48. 最终心智模型

```text
                     Incoming State
                           │
                Is it externally trusted?
                     /             \
                   no               yes
                   │                 │
              validation       contract reasoning
                   │                 │
            valid? / \ invalid       │
                 /     \             │
              yes       error        │
               │                     │
               └──────► Trusted Representation
                              │
                         Preconditions
                              │
                           Operation
                              │
                    ┌─────────┴──────────┐
                    │                    │
                 success          invariant violation
                    │                    │
             postconditions       programmer error
                    │                    │
             invariants hold      assert / fail-fast
```

UB 不属于这张错误处理流程：

```text
UB
=
contract / language rule 已经被违反，
程序离开 C++ 抽象机的可靠语义范围。
```

因此我们的目标不是：

```text
处理 UB
```

而是：

```text
prevent UB
```

---

## 49. FM-1 最终压缩

FM-1 可以压成四句话：

> **外部不确定性用 validation 处理。**

> **内部必然条件用 contract/invariant 描述。**

> **违反 contract 是程序缺陷，不应伪装成普通业务失败。**

> **UB 不是失败机制；高质量系统应该在 UB 之前建立 validation、assertion 或 fail-fast boundary。**

这构成 FM-2 讨论 `optional`、`expected`、error type 和 value-based failure 的前提。
