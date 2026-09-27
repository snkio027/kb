<a id="fm-3--c-exception-semantics"></a>
# FM-3 · 异常传播语义

> C++23 失败语义工程手册 · 系列整理候选

[返回 FM 导航](README.md) · [上一章：FM-2](fm2-value-based-failure.md) · [下一章：FM-4](fm4-raii-exception-safety.md) · [术语与审查约定](series-guide.md)

## 阅读入口

主讲异常对象、捕获、重抛与实际展开。资源和业务状态是否安全，分别由 FM-4/FM-6 的合同补足。

**主阅读线。** §1–9 → §13–15 → §20–22；对象构造失败细节回查 FM-6。

**失败契约。** 传播路径要标出可匹配 handler、非抛出边界和清理动作；错误翻译与日志本身可能产生新失败。没有 handler 的路径不承诺完整析构。

**证据边界。** 这里主要是语言条款与路径推理；T13 的构造计数及 T11 的受控终止只有各自声明的覆盖。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、抛出对象与匹配](#fm3-part-1)
- [二、展开、重抛与中间层](#fm3-part-2)
- [三、捕获与边界](#fm3-part-3)
- [四、选型、成本与回查](#fm3-part-4)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm3-part-1"></a>

## 一、抛出对象与匹配

### 0. 文档定位

本章主讲 C++ 异常的非局部传播，而不重新定义失败原因或状态保证。沿一条能到达匹配 handler、且展开过程未再失败的路径，可用下图理解：

```text
throw → 初始化异常对象 → 寻找 handler → 展开相应作用域 → catch
```

中间层可以不改写返回类型，由实际展开执行已构造对象的析构。但没有 handler、触及非抛出边界或展开中再失败时，不能套用这条正常清理路径；具体限制在 §5。清理与业务回滚也不是同一件事。

### 1. Exception 是非局部控制流

例如：

```cpp
void c() {
    throw ParseError{};
}

void b() {
    c();
}

void a() {
    b();
}
```

如果 `a()` 外层存在 handler：

```text
c
↓
b skipped
↓
a skipped
↓
handler
```

中间层不需要：

```text
检查返回码
再返回返回码
```

这是 exception 与 value-based failure 最明显的控制流差异。

### 2. Exception Object

执行：

```cpp
throw Error{...};
```

C++ 会建立一个 exception object。

它独立于：`throw expression 中局部对象的普通 lifetime`

并在匹配 handler 处理期间保持存在。

因此通常：

```cpp
catch (const Error& error)
```

是正确方式。

### 3. Catch by Reference

推荐：

```cpp
catch (const std::exception& error) {
    ...
}
```

而不是：

```cpp
catch (std::exception error) {
    ...
}
```

后者可能产生：

```text
copy
+
object slicing
```

丢失动态异常类型信息。

### 4. Handler 顺序

更具体类型必须放在前面：

```cpp
try {
    ...
} catch (const ParseError& error) {
    ...
} catch (const std::exception& error) {
    ...
}
```

如果先：

```cpp
catch (const std::exception&)
```

后面的派生类 handler 可能永远无法匹配。

<a id="fm3-part-2"></a>

## 二、展开、重抛与中间层

### 5. Stack Unwinding

Exception 被抛出后：`当前正常控制流终止`

下面讨论控制流转向匹配 handler 且发生栈展开的路径；不包括所有终止情形。

每个已经完成构造的 automatic object：`按正常作用域逆序析构`

例如：

```cpp
void process() {
    File file;
    Lock lock;
    Buffer buffer;

    decode(); // throws
}
```

展开：

```text
~Buffer
~Lock
~File
```

这就是 exception 与 RAII 能够组合的根本原因。

无匹配 handler 时，是否在终止前展开栈由实现定义；搜索 handler 触及非抛出异常规格函数的最外层时，完整、部分或不展开也由实现定义。不能依靠这些终止路径执行所有自动对象析构，更不能将 terminate 当作安全关机协议。[N4950：except.terminate/2](https://timsong-cpp.github.io/cppwp/n4950/except.terminate#2)

### 6. 未完成构造的对象

例如：

```cpp
class Session {
    File file_;
    Socket socket_;
    Buffer buffer_;
};
```

在 Session 的非委托构造过程中，假定 buffer_ 的非委托初始化未完成就抛异常：

```text
file_   constructed
socket_ constructed
buffer_ throws
```

则：

```text
socket_ destroyed
file_ destroyed
```

但：`Session 本身没有完成构造`

因此不会执行：

```cpp
Session::~Session()
```

上述例子是非委托构造失败。若目标构造已成功，随后委托构造函数体抛异常，则会调用完整对象的析构函数；不要把两种情况混同。[N4950：except.ctor/4](https://timsong-cpp.github.io/cppwp/n4950/except.ctor#4)

详见 [FM-6 §3](fm6-construction-destruction-allocation.md#3-partial-construction) 与 [T13](review/fm-verification-samples.md#t13)。

### 7. Rethrow

当前 handler 中：

```cpp
catch (const Error&) {
    record_context();
    throw;
}
```

表示：`重新抛出当前 exception object`

保留原异常动态类型。该片段还依赖 `record_context()` 不以新异常中断处理；若它抛出，原异常并不会按计划执行到 `throw;`。报告失败政策应与 [FM-8 §2](fm8-failure-boundaries.md#2-stdthread) 一起审查。

不要无意义写：

```cpp
catch (const Error& error) {
    throw error;
}
```

这会构造新的 throw operand，并可能：

```text
copy
slice derived type
```

所以重新传播当前异常：

```cpp
throw;
```

才是标准模式。

### 8. Exception Translation

有时需要：

```text
low-level exception
→ domain exception
```

例如：

```cpp
try {
    storage_.read();
} catch (const StorageError& error) {
    throw ConfigLoadError{...};
}
```

只应在：`abstraction semantics changes`

时进行。

否则保持 exception neutrality：

> 不理解这个错误的层不要捕获它。

### 9. Exception Neutrality

一个高质量中间组件可以：

```text
不 catch
但仍然 exception-safe
```

例如：

```cpp
void process() {
    Buffer buffer;
    transform(buffer);
}
```

即使 `transform()` 抛异常：

```text
RAII handles cleanup
exception propagates upward
```

该函数完全可以做到：

```text
exception-neutral
+
resource-safe
```

这比：

```cpp
catch (...)
```

后不知道如何处理更好。

<a id="fm3-part-3"></a>

## 三、捕获与边界

### 10. `catch (...)`

`catch (...)` 的典型合理位置是：

```text
thread boundary
plugin boundary
event-loop boundary
process top-level boundary
foreign ABI boundary
```

而不是业务代码到处：

```cpp
try {
    ...
} catch (...) {
}
```

特别禁止：

```text
catch all
+
silently continue
```

### 11. `std::exception_ptr`

当 exception 需要跨越：

```text
thread
callback
deferred execution
```

保存时：

```cpp
std::exception_ptr
```

是标准机制。

捕获：

```cpp
auto error = std::current_exception();
```

之后：

```cpp
std::rethrow_exception(error);
```

可以重新进入 exception propagation。

这比尝试：`复制未知动态异常对象`

可靠得多。

### 12. Exception 与 Constructor

构造函数无法通过普通返回类型表达：

```cpp
std::expected<Object, Error>
```

因此：

```cpp
Object::Object(...)
```

无法建立 invariant 时，throw 是自然语言机制之一。

另一种设计：

```cpp
class Object {
public:
    static std::expected<Object, Error> create(...);

private:
    explicit Object(Resource resource) noexcept;
};
```

两种都合理。

选择依据：

```text
project failure policy
failure frequency
construction semantics
API composition
exception policy
```

### 13. Exception 与 Destructor

Destructor 属于 cleanup infrastructure。

基本工程原则：

> **Destructor 不应允许异常逃出。**

特别是在 stack unwinding 中：

```text
已有一个 active exception
+
destructor 再抛一个异常逃出
```

会进入：

```cpp
std::terminate()
```

因此可能失败的资源关闭操作应考虑提供：

```cpp
close()
flush()
commit()
```

显式 API。

析构只做：`best-effort non-throwing cleanup`

### 14. Exception Specification 与 `noexcept`

exception 可能从函数逃出与：

```cpp
noexcept
```

直接相关。

```cpp
void f() noexcept;
```

不是说：`内部绝不会 throw`

而是承诺：`exception cannot escape f()`

若违反：`std::terminate()`

详细模型在 FM-5。

### 15. Exception Boundary

Exception 不应无设计地穿过：

```text
thread entry
C ABI
plugin ABI
shared-library ABI with incompatible runtime
process boundary
RPC boundary
```

在这些位置需要：

```text
catch
→ translate
→ report
```

<a id="fm3-part-4"></a>

## 四、选型、成本与回查

### 16. Exception 适合什么失败

通常更适合：

```text
rare failure
deep propagation
constructor failure
operations where intermediate layers cannot recover
failure path where manual plumbing adds substantial noise
```

### 17. Exception 不适合什么

不推荐用于：

```text
lookup miss
queue empty
normal EOF
frequent parse rejection
try_lock failed
hot-path expected branch
```

因为这些本质是：`ordinary domain control flow`

### 18. Exception 成本模型

不能简单说：`exception 有成本`

或者：`exception zero-cost`

准确模型取决于：

```text
compiler
platform ABI
optimization level
exception frequency
code layout
binary size
unwind tables
```

很多主流 native ABI 会显著偏向：

```text
success path relatively cheap
throw path expensive
```

因此工程策略应是：

> 按 failure semantics 选择机制，对真正性能敏感路径进行测量。

而不是根据口号决定。

### 19. Exception Hierarchy

不要设计几十层 inheritance hierarchy。

典型项目：

```cpp
class ApplicationError : public std::runtime_error {
    ...
};
```

再细分少量真正有语义差异的类型即可。

如果恢复策略实际上依赖：`code`

那么：`single exception type + structured error code`

有时比复杂继承树更合理。

### 20. Anti-Patterns

<a id="catch-and-ignore"></a>

**Catch and ignore**

```cpp
try {
    update();
} catch (...) {
}
```

<a id="catch-too-low"></a>

**Catch too low**

底层没有 recovery context 却捕获所有异常。

<a id="exception-作为普通循环分支"></a>

**Exception 作为普通循环分支**

```cpp
for (...) {
    try {
        lookup();
    } catch (NotFound&) {
    }
}
```

<a id="throw-raw-primitives"></a>

**Throw raw primitives**

```cpp
throw 42;
throw "error";
```

破坏统一 error vocabulary。

<a id="destructor-传播异常"></a>

**Destructor 传播异常**

容易破坏 unwinding。

<a id="每层重新包装-exception"></a>

**每层重新包装 exception**

产生：

```text
ExceptionA
→ ExceptionB
→ ExceptionC
```

却没有新的抽象意义。

### 21. FM-3 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

```text
[ ] failure 是否真正适合 exceptional propagation？
[ ] exception 是否被 catch by reference？
[ ] catch 顺序是否由具体到通用？
[ ] 中间层是否可以保持 exception-neutral？
[ ] rethrow 是否使用 throw;？
[ ] stack unwinding 是否由 RAII 正确清理？
[ ] destructor 是否可能传播异常？
[ ] translation 是否发生在真正 abstraction boundary？
[ ] exception 是否可能逃出 thread / ABI boundary？
[ ] catch(...) 是否位于明确 failure boundary？
[ ] failure frequency 是否适合 exception？
```

### 22. FM-3 核心不变量

> Exception 是传播机制，不是 failure taxonomy。

> Exception safety 不要求 catch exception。

> RAII 是 exception propagation 能够安全组合的基础。

> 不知道如何恢复的中间层通常应该保持 exception-neutral。

> Exception 必须在明确 boundary 内被 containment。
