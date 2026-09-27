<a id="fm-6--construction-destruction--allocation-failure"></a>
# FM-6 · 生命周期与资源失败

> C++23 失败语义工程手册

[返回 FM 导航](README.md) · [上一章：FM-5](fm5-noexcept-move-copy.md) · [下一章：FM-7](fm7-error-code-system-error.md) · [术语与审查约定](series-guide.md)

## 阅读入口

主讲对象何时建立不变量、部分构造清理、分配与初始化失败，以及显式完成和析构后备的分工。

**主阅读线。** §1–5 → §7–13 → §14–17；RAII 的一般保证与提交分析回查 FM-4。

**失败契约。** 构造成功不变量成立；失败时哪些子对象已完成、谁拥有资源必须清楚。finish/flush 的业务完成与析构释放分开，nothrow 分配不等于整个 new-expression 不抛。

**证据边界。** T13 只检查普通与委托构造路径的计数；没有穷举 allocator/new-handler、资源耗尽与实际关闭失败。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、构造与对象有效性](#fm6-part-1)
- [二、分配与资源压力](#fm6-part-2)
- [三、显式完成和清理](#fm6-part-3)
- [四、审查与回查](#fm6-part-4)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm6-part-1"></a>

## 一、构造与对象有效性

### 0. 文档定位

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

### 1. Constructor 是 Invariant Boundary

理想构造：

```cpp
Connection connection{options};
```

正常返回意味着：`Connection invariant established`

如果无法建立：`constructor must not successfully return`

### 2. Constructor Throw

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

### 3. Partial Construction

在完整对象的非委托构造中，若成员 A、B 已完成，而成员 C 的非委托初始化尚未完成就抛异常，已完成的 B、A 按逆序析构；此时不会调用 C 或完整对象自身的析构函数。C 内已经完成构造的子对象仍按相应规则清理。已取得资源必须由完成构造的成员或局部 owner 管理，不能寄望于完整对象的析构函数。

委托构造是不同情况：目标构造已成功，随后委托构造函数体抛异常，会调用该对象的析构函数。[N4950：except.ctor/3～4](https://timsong-cpp.github.io/cppwp/n4950/except.ctor)

对照片段：

```cpp
Object() : Object(0) {
    throw Failure{}; // 目标构造已成功：随后调用 ~Object()。
}
```

完整析构计数例见 [T13](review/fm-verification-samples.md#t13)。这些规则描述构造失败转向 handler 的路径；不能推广为所有进程终止都会完成栈展开，见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

### 4. Factory + `expected`

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

### 5. Throwing Constructor vs Factory

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

### 6. Two-Phase Initialization 应谨慎

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

并迫使每个方法问：`is_initialized?`

这通常扩大 state space。

优先：

```text
construct valid object
or
do not produce object
```

<a id="fm6-part-2"></a>

## 二、分配与资源压力

### 7. `operator new`

普通分配：

```cpp
auto* p = new T;
```

无法分配时：`通常通过 std::bad_alloc 报告`

这是 exception-based allocation failure model。

### 8. Nothrow Allocation

下述讨论限定标准非抛出分配形式；类特定分配函数和对象初始化应分别审查，不能从 `new (std::nothrow)` 的字面形式推出整个表达式不抛。

可以：

```cpp
auto* p = new (std::nothrow) T;
```

分配失败时：`nullptr`

但这并不自动意味着：`T construction cannot throw`

分配成功后，初始化失败仍可传播异常；new-expression 会按其规则寻找匹配的释放函数。资源回收与对象是否构造完成是两件事，不能把返回空指针和构造抛异常合成同一种失败路径。[N4950：expr.new](https://timsong-cpp.github.io/cppwp/n4950/expr.new)

同时也不要为了“禁用异常”机械使用 nothrow new。

现代工程更推荐：

```text
RAII owner
+
明确 allocation policy
```

而不是 raw `new`。

### 9. `std::bad_alloc`

对于普通通用软件：`system is out of memory`

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

### 10. Memory Failure Policy

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

### 11. Allocation 与 API Guarantee

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

<a id="fm6-part-3"></a>

## 三、显式完成和清理

### 12. Destructor 的职责

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

### 13. Explicit Close Pattern

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

这能区分：`business completion`

和：`resource destruction`

### 14. Resource Owner 优先使用 Rule of Zero

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

从而业务类型通常无需手写 Rule of Five。但成员各自安全不自动证明跨成员不变量，默认移动后的源状态、复制是否被删除以及字段之间的关系仍须核对；主讲见 [FM-5](fm5-noexcept-move-copy.md)。

这就是：`Rule of Zero`

在 Failure Model 中的巨大价值。

### 15. Rule of Five 适用于真正 Ownership Primitive

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

<a id="fm6-part-4"></a>

## 四、审查与回查

### 16. FM-6 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

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

### 17. FM-6 核心不变量

> 成功构造的对象必须满足 invariant。

> Constructor failure 必须依靠 member-level RAII 自动清理。

> 可恢复 construction failure 可以使用 factory + expected。

> Destructor 是 cleanup boundary，不应承担可失败业务 commit。

> 资源受限问题应通过资源策略设计解决，而不是依赖 OOM 后临时恢复。
