# FM-4 — RAII & Exception Safety

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-3](fm3-exception-semantics.md) · [下一章：FM-5](fm5-noexcept-move-copy.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. RAII 的真正含义](#1-raii-的真正含义)
- [2. Owner Object](#2-owner-object)
- [3. RAII 与 Control Flow 解耦](#3-raii-与-control-flow-解耦)
- [4. Exception Safety Guarantees](#4-exception-safety-guarantees)
- [5. Strong Guarantee 的核心模式](#5-strong-guarantee-的核心模式)
- [6. Transactional Thinking](#6-transactional-thinking)
- [7. Commit Point](#7-commit-point)
- [8. Partial Construction](#8-partial-construction)
- [9. Two-Phase Initialization](#9-two-phase-initialization)
- [10. Rollback 不是免费操作](#10-rollback-不是免费操作)
- [11. Copy-and-Swap](#11-copy-and-swap)
- [12. Resource Acquisition 顺序](#12-resource-acquisition-顺序)
- [13. Destruction 是 Cleanup Infrastructure](#13-destruction-是-cleanup-infrastructure)
- [14. State Guarantee 必须组合分析](#14-state-guarantee-必须组合分析)
- [15. Failure 与 Partial Side Effects](#15-failure-与-partial-side-effects)
- [16. Ambiguous Completion](#16-ambiguous-completion)
- [17. RAII 不等于 Transaction](#17-raii-不等于-transaction)
- [18. FM-4 Review Checklist](#18-fm-4-review-checklist)
- [19. FM-4 核心不变量](#19-fm-4-核心不变量)

---

## 0. 文档定位

FM-4 解决：

> 一个操作失败以后，资源和状态如何仍然保持正确？

核心关系：

```text
RAII
+
ownership
+
state guarantees
+
transactional update
```

共同构成 C++ failure safety。

---

## 1. RAII 的真正含义

RAII 不是：

```text
智能指针
```

也不只是：

```text
自动释放内存
```

而是：

> 将资源的所有权和有效期绑定到对象生命周期。

资源可以是：

```text
memory
file descriptor
socket
mutex
transaction
temporary file
GPU buffer
mapped memory
subscription
```

---

## 2. Owner Object

理想结构：

```text
acquire resource
      ↓
owner object constructed
      ↓
resource lifetime
      ↓
owner destructor
      ↓
release
```

因此：

```text
normal return
early return
exception
```

都经过相同 cleanup path。

---

## 3. RAII 与 Control Flow 解耦

错误：

```cpp
auto* resource = acquire();

step_a();
step_b();  // may throw

release(resource);
```

如果：

```text
step_b throws
```

release 被绕过。

正确：

```cpp
Resource resource = acquire();

step_a();
step_b();
```

cleanup 成为：

```text
lifetime semantics
```

而不是：

```text
control-flow bookkeeping
```

这里以正常作用域退出或实际进行的栈展开为前提，不是所有终止路径的清理承诺；详见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

---

## 4. Exception Safety Guarantees

以下是工程保证的术语，不应混成一个包含“终止”的线性等级。声明保证时应明确所覆盖的可观察状态、失败通道与前置条件。

### No-throw Guarantee

本系列用 no-throw 描述**不向调用者传播异常**的保证；它不等于 no-fail。`noexcept` 也不证明操作成功、正常返回或完成清理。

若一个 commit 要求 no-fail，必须额外证明：合法前置条件下可正常完成，没有未处理的错误返回、异常或部分提交，后续返回与清理不会推翻声明的事务结果。终止进程不算完成这样的 commit。

### Strong Guarantee

所约定的失败发生时，可观察状态与操作前一致。典型实现先准备临时状态再提交；外部副作用不因内存中的 swap 自动回滚。

### Basic Guarantee

失败后不变量和资源管理仍成立，但值可能已改变。具体可继续执行哪些操作仍须由契约说明。

### No Useful Guarantee

对于关注的失败路径，缺少可依赖的状态保证，不能自行升级成 basic。某条标准写 effects unspecified 也不能简单改称 UB，见 [FM-5 §11](fm5-noexcept-move-copy.md#11-move-only--throwing-move)。

终止是另一维度的处置策略；其清理限制见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

---

## 5. Strong Guarantee 的核心模式

```text
prepare (may fail, original observable state unchanged)
    ↓
commit (normal completion assured under its preconditions)
    ↓
return / cleanup (compatible with the promised guarantee)
```

契约片段：

```cpp
void update(State& state, const Input& input) {
    State next = build_state(state, input);
    state.swap(next);
}
```

此结构只有在以下条件成立时才支持所声称的 strong guarantee：

- `build_state` 的失败不修改纳入保证的原状态，也没有无法撤销的外部副作用。
- `swap` 的前置条件满足；它真正完成提交，不能只是声明 `noexcept` 却在内部失败、终止或错误返回。
- `next` 的析构、返回路径及其他收尾与保证兼容；不能在提交后又向调用者报告一个声称“状态未变”的失败。

因此 `noexcept swap` 是有用线索，不是独立的事务证明。

---

## 6. Transactional Thinking

状态修改操作应思考：

```text
Prepare
Validate
Commit
Cleanup
```

而不是：

```text
边修改
边验证
边申请资源
边做不可逆副作用
```

后者极难提供 strong guarantee。

---

## 7. Commit Point

每一个重要状态变更最好能够回答：

> commit point 在哪里？

在 commit point 之前：

```text
failure → discard temporary state
```

之后：

```text
operation considered committed
```

尤其重要于：

```text
persistent storage
message publish
database mutation
network protocol
```

---

## 8. Partial Construction

RAII 的强大之处在于：

```text
subobjects constructed one by one
```

某一步失败后：

```text
already-constructed objects unwind automatically
```

委托构造体失败与普通成员构造失败的区别见 [FM-6 §3](fm6-construction-destruction-allocation.md#3-partial-construction)。

因此应优先：

```cpp
class Session {
    File file_;
    Socket socket_;
    Buffer buffer_;
};
```

而不是：

```cpp
class Session {
    FileHandle file_{invalid};
    SocketHandle socket_{invalid};

    bool init();
};
```

后者创造大量：

```text
partially initialized states
```

---

## 9. Two-Phase Initialization

反模式：

```cpp
Widget widget;
if (!widget.init()) {
    ...
}
```

现在 `Widget` 存在：

```text
before init
after init
init partially failed
```

多个合法/非法状态。

如果可行，更推荐：

```cpp
auto widget = Widget::create(...);
```

或者 throwing constructor。

目标：

> 一个普通对象一旦存在，就满足其 invariant。

---

## 10. Rollback 不是免费操作

不要简单设计：

```text
do A
do B
do C

C failed

undo B
undo A
```

因为：

```text
undo B 也可能失败
```

高质量 strong guarantee 更偏向：

```text
build isolated new state
+
non-failing commit
```

而不是依赖复杂 rollback。

---

## 11. Copy-and-Swap

经典形式：

```cpp
Buffer& operator=(Buffer other) {
    swap(other);
    return *this;
}
```

模型：

```text
construct temporary
    ↓ may fail
old object unchanged

swap
    ↓ noexcept
commit

temporary destroys old state
```

这是非常清晰的 strong-guarantee 教学模型。

但不是所有类型都应该机械使用：

```text
temporary allocation
capacity reuse lost
performance tradeoff
```

需要实际评估。

---

## 12. Resource Acquisition 顺序

多个资源：

```cpp
File file = open_file();
Socket socket = open_socket();
Buffer buffer = allocate_buffer();
```

每一步成功后立刻进入 owner。

那么：

```text
buffer acquisition fails
```

之前的：

```text
socket
file
```

都会由 RAII 自动清理。

不要：

```text
先获取三个 raw handle
再统一包装
```

这样会扩大 failure window。

---

## 13. Destruction 是 Cleanup Infrastructure

Destructor 应：

```text
restore resource ownership balance
```

而不是承担复杂可能失败的业务事务。

如果：

```text
flush
commit
network close handshake
database commit
```

的失败需要调用者知道，应提供：

```cpp
std::expected<void, CloseError> close();
```

析构函数只做：

```text
non-throwing fallback cleanup
```

---

## 14. State Guarantee 必须组合分析

高层操作的保证依赖：

```text
sub-operation guarantees
```

例如：

```text
Algorithm guarantee
=
allocation guarantee
+
T construction guarantee
+
T move/copy guarantee
+
commit operation guarantee
```

因此 generic code 不能脱离 `T` 的 semantics 宣称 guarantee。

---

## 15. Failure 与 Partial Side Effects

例如：

```text
modify memory
write disk
send packet
```

其可回滚性质不同。

内存临时对象通常：

```text
easy to discard
```

而外部副作用：

```text
email sent
payment submitted
Kafka message acknowledged
```

可能不可撤销。

因此 strong guarantee 对：

```text
external world
```

并不总能实现。

此时必须定义：

```text
partial commit semantics
```

---

## 16. Ambiguous Completion

典型：

```text
request sent
server committed
response lost
```

调用者看到：

```text
timeout
```

但实际：

```text
operation may already have succeeded
```

这不是普通 strong/basic guarantee 能完全表达的。

需要：

```text
idempotency
operation ID
deduplication
query-after-failure
transaction protocol
```

---

## 17. RAII 不等于 Transaction

RAII 可以保证：

```text
resource cleanup
```

但不能自动保证：

```text
business state rollback
```

例如：

```text
File handle successfully closed
```

并不能回滚：

```text
已经写入磁盘的数据
```

两者必须分开。

---

## 18. FM-4 Review Checklist

```text
[ ] 每个 resource 是否立即进入 owner？
[ ] raw ownership window 是否最小？
[ ] 对象是否存在 partially initialized state？
[ ] 异常传播、失败后状态和终局处置是否分别声明？
[ ] guarantee 是否依赖 T 的操作？
[ ] commit point 是否明确？
[ ] prepare 阶段是否修改原状态？
[ ] commit 是否真正 no-fail（含前置条件、错误返回与收尾），而不只是 noexcept？
[ ] rollback 本身是否可能失败？
[ ] destructor 是否承担可失败业务逻辑？
[ ] external side effect 是否存在 ambiguous completion？
[ ] failure 后 resource ownership 是否仍然唯一明确？
```

---

## 19. FM-4 核心不变量

> 所有资源都应该由对象生命周期拥有。

> Strong guarantee 的首选模型是 prepare-then-commit，而不是复杂 rollback。

> Basic guarantee 至少要求 invariant 与 ownership 仍然正确。

> RAII 保证资源安全，不自动保证业务事务原子性。

> External side effect 必须单独定义 commit semantics。

---

---
