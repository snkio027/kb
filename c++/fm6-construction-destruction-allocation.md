# FM-6 — Construction, Destruction & Allocation Failure

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-5](fm5-noexcept-move-copy.md) · [下一章：FM-7](fm7-error-code-system-error.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. Constructor 是 Invariant Boundary](#1-constructor-是-invariant-boundary)
- [2. Constructor Throw](#2-constructor-throw)
- [3. Partial Construction](#3-partial-construction)
- [4. Factory + expected](#4-factory--expected)
- [5. Throwing Constructor vs Factory](#5-throwing-constructor-vs-factory)
- [6. Two-Phase Initialization 应谨慎](#6-two-phase-initialization-应谨慎)
- [7. operator new](#7-operator-new)
- [8. Nothrow Allocation](#8-nothrow-allocation)
- [9. std::bad_alloc](#9-stdbad_alloc)
- [10. Memory Failure Policy](#10-memory-failure-policy)
- [11. Allocation 与 API Guarantee](#11-allocation-与-api-guarantee)
- [12. Destructor 的职责](#12-destructor-的职责)
- [13. Explicit Close Pattern](#13-explicit-close-pattern)
- [14. Resource Owner 优先使用 Rule of Zero](#14-resource-owner-优先使用-rule-of-zero)
- [15. Rule of Five 适用于真正 Ownership Primitive](#15-rule-of-five-适用于真正-ownership-primitive)
- [16. FM-6 Review Checklist](#16-fm-6-review-checklist)
- [17. FM-6 核心不变量](#17-fm-6-核心不变量)

---

## 0. 文档定位

FM-6 聚焦对象生命周期边界上的失败：

```text
construction
allocation
partial construction
destruction
resource acquisition
factory
```

核心原则：

> 一个普通对象一旦成功存在，就应该满足其 invariant。

---

## 1. Constructor 是 Invariant Boundary

理想构造：

```cpp
Connection connection{options};
```

正常返回意味着：

```text
Connection invariant established
```

如果无法建立：

```text
constructor must not successfully return
```

---

## 2. Constructor Throw

例如：

```cpp
File::File(const Path& path) {
    handle_ = open_native(path);

    if (!handle_.valid()) {
        throw FileOpenError{...};
    }
}
```

这是合法且自然的 C++ construction failure。

---

## 3. Partial Construction

对象成员按构造顺序建立。

假设：

```text
member A success
member B success
member C throws
```

则：

```text
B destroyed
A destroyed
```

完整对象：

```text
never came into existence
```

因此其 destructor 不会执行。

这使成员级 RAII 成为 constructor failure 的基础。

---

## 4. Factory + `expected`

如果项目采用 value-based failure：

```cpp
class Connection {
public:
    static std::expected<Connection, ConnectError>
    connect(const Options& options);

private:
    explicit Connection(Socket socket) noexcept;
};
```

流程：

```text
factory performs fallible setup
    ↓
success
    ↓
construct fully valid object
```

这是非常优秀的 C++23 模式。

---

## 5. Throwing Constructor vs Factory

优先考虑 throwing constructor：

```text
construction failure rare
project uses exceptions
object cannot meaningfully exist invalid
ergonomic direct construction valuable
```

优先考虑 factory：

```text
failure is expected
caller branches on error
project uses expected
failure category is domain-visible
construction requires asynchronous/multi-step workflow
```

不要建立：

```text
throwing constructor = old
factory = modern
```

这种错误二分。

---

## 6. Two-Phase Initialization 应谨慎

```cpp
Connection c;
if (!c.init()) {
    ...
}
```

会产生：

```text
default state
initialized state
partially initialized state
failed state
```

并迫使每个方法问：

```text
is_initialized?
```

这通常扩大 state space。

优先：

```text
construct valid object
or
do not produce object
```

---

## 7. `operator new`

普通分配：

```cpp
auto* p = new T;
```

无法分配时：

```text
通常通过 std::bad_alloc 报告
```

这是 exception-based allocation failure model。

---

## 8. Nothrow Allocation

可以：

```cpp
auto* p = new (std::nothrow) T;
```

分配失败时：

```text
nullptr
```

但这并不自动意味着：

```text
T construction cannot throw
```

同时也不要为了“禁用异常”机械使用 nothrow new。

现代工程更推荐：

```text
RAII owner
+
明确 allocation policy
```

而不是 raw `new`。

---

## 9. `std::bad_alloc`

对于普通通用软件：

```text
system is out of memory
```

通常不是一个容易局部恢复的问题。

因为处理错误本身可能还需要：

```text
allocate strings
log buffers
construct error objects
```

因此不要假设：

```cpp
catch (const std::bad_alloc&) {
    continue_normally();
}
```

一定能够恢复。

---

## 10. Memory Failure Policy

真正需要在内存压力下继续工作的系统，应提前设计：

```text
preallocation
bounded pools
arena allocation
memory_resource
reserved emergency capacity
admission control
backpressure
```

而不是等 `bad_alloc` 发生后才临时思考恢复。

---

## 11. Allocation 与 API Guarantee

如果 API 内部可能：

```text
vector growth
string growth
shared_ptr control block allocation
dynamic polymorphic allocation
```

那么即使函数里没有：

```cpp
throw
```

它也可能传播 allocation exception。

---

## 12. Destructor 的职责

Destructor：

```text
release ownership
restore resource balance
```

典型：

```cpp
~File() noexcept {
    close_native(handle_);
}
```

但现实中：

```text
close
flush
fsync
commit
```

可能失败。

如果失败对业务正确性重要：

```cpp
auto result = file.flush();
auto result = transaction.commit();
```

必须通过显式 operation 观察。

不要依赖 destructor 报告。

---

## 13. Explicit Close Pattern

例如：

```cpp
class Writer {
public:
    std::expected<void, FlushError> finish();

    ~Writer() noexcept {
        cleanup_without_throwing();
    }
};
```

语义：

```text
finish()
    → observable completion/failure

destructor
    → resource cleanup only
```

这能区分：

```text
business completion
```

和：

```text
resource destruction
```

---

## 14. Resource Owner 优先使用 Rule of Zero

理想：

```cpp
class Session {
    std::unique_ptr<Resource> resource_;
    std::vector<std::byte> buffer_;
    std::string name_;
};
```

尽量让成员自己管理：

```text
copy
move
destruction
```

从而业务类型无需手写 Rule of Five。

这就是：

```text
Rule of Zero
```

在 Failure Model 中的巨大价值。

---

## 15. Rule of Five 适用于真正 Ownership Primitive

如果你正在实现：

```text
FileHandle
Socket
MappedMemory
RawBuffer
```

这类基础 ownership abstraction，

才通常需要显式设计：

```text
destructor
copy constructor
copy assignment
move constructor
move assignment
```

并明确每一个操作：

```text
can fail?
noexcept?
source state?
strong/basic guarantee?
```

---

## 16. FM-6 Review Checklist

```text
[ ] 普通对象存在是否意味着 invariant 成立？
[ ] constructor failure 后成员是否由 RAII 自动清理？
[ ] 是否存在不必要 two-phase initialization？
[ ] throwing constructor 与 factory 是否符合项目 Failure Profile？
[ ] allocation failure 是否被遗漏？
[ ] 是否把 bad_alloc 当成容易恢复的普通错误？
[ ] 内存受限系统是否有预分配/池/backpressure？
[ ] destructor 是否可能传播异常？
[ ] 可失败 commit/flush 是否有显式 API？
[ ] ownership primitive 的 Rule of Five 是否完整？
[ ] 业务类型是否尽量使用 Rule of Zero？
```

---

## 17. FM-6 核心不变量

> 成功构造的对象必须满足 invariant。

> Constructor failure 必须依靠 member-level RAII 自动清理。

> 可恢复 construction failure 可以使用 factory + expected。

> Destructor 是 cleanup boundary，不应承担可失败业务 commit。

> 资源受限问题应通过资源策略设计解决，而不是依赖 OOM 后临时恢复。

---

---
