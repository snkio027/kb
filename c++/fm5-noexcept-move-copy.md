# FM-5 — `noexcept`, Move, Copy & Generic Guarantees

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-4](fm4-raii-exception-safety.md) · [下一章：FM-6](fm6-construction-destruction-allocation.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. noexcept 的精确含义](#1-noexcept-的精确含义)
- [2. 违反 noexcept](#2-违反-noexcept)
- [3. noexcept(expr)](#3-noexceptexpr)
- [4. Conditional noexcept](#4-conditional-noexcept)
- [5. std::move 不执行移动](#5-stdmove-不执行移动)
- [6. Move 为什么特别适合 noexcept](#6-move-为什么特别适合-noexcept)
- [7. Copy 与 Failure](#7-copy-与-failure)
- [8. Container Relocation](#8-container-relocation)
- [9. Throwing Move 的困难](#9-throwing-move-的困难)
- [10. std::move_if_noexcept](#10-stdmove_if_noexcept)
- [11. Move-Only + Throwing Move](#11-move-only--throwing-move)
- [12. Traits](#12-traits)
- [13. swap](#13-swap)
- [14. Defaulted Move](#14-defaulted-move)
- [15. 不要对 noexcept 撒谎](#15-不要对-noexcept-撒谎)
- [16. Destructor 与 noexcept](#16-destructor-与-noexcept)
- [17. Generic Guarantee Composition](#17-generic-guarantee-composition)
- [18. FM-5 Review Checklist](#18-fm-5-review-checklist)
- [19. FM-5 核心不变量](#19-fm-5-核心不变量)

---

## 0. 文档定位

FM-5 解决：

> C++ 如何把“这个操作不会让异常逃出”的信息编码进类型接口，并让泛型算法据此改变策略？

核心对象：

```text
noexcept
move
copy
swap
type traits
container relocation
```

---

## 1. `noexcept` 的精确含义

```cpp
void f() noexcept;
```

表示：

> exception 不允许逃出 `f()`。

不是：

```text
f 内部绝对没有 throw
```

例如：

```cpp
void f() noexcept {
    try {
        may_throw();
    } catch (...) {
        recover();
    }
}
```

这是契约片段：`may_throw` 和 `recover` 未给出实现。内部抛出再捕获合法，但若 `recover()` 又抛出并越界，仍会终止；此例不证明恢复动作不会失败。

---

## 2. 违反 `noexcept`

如果异常试图逃出：

```cpp
void f() noexcept {
    throw Error{};
}
```

则：

```text
std::terminate()
```

因此：

```text
noexcept
```

是一项非常强的 runtime contract；它不保证正常完成或完整清理。终止与栈展开的边界见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

---

## 3. `noexcept(expr)`

`noexcept(expression)` 是不求值的编译期查询，判断**整个表达式**是否 potentially-throwing，不只是查看最外层被调函数有没有 `noexcept`。实参求值和临时对象等也参与判断。[N4950：expr.unary.noexcept](https://timsong-cpp.github.io/cppwp/n4950/expr.unary.noexcept)

编译语义例 T14：

<!-- fm-test {"id":"T14","mode":"compile"} -->
```cpp
int argument();
void operation(int = argument()) noexcept;
static_assert(noexcept(operation(0)));
static_assert(!noexcept(operation()));
```

两次调用的函数相同，默认实参的求值却改变了结果。此例只需语法检查，不需要为未调用的函数补定义或链接入口。

---

## 4. Conditional `noexcept`

泛型代码：

```cpp
template <typename T>
void exchange(T& a, T& b)
    noexcept(noexcept(a.swap(b)))
{
    a.swap(b);
}
```

这让高层 operation 的 exception specification：

```text
由底层 operation 推导
```

---

## 5. `std::move` 不执行移动

`std::move(x)` 执行表达式转换，保留相应 cv 限定，不负责转移资源。对于初始化片段：

```cpp
T y{std::move(x)};
```

完整重载决议才决定使用哪个构造函数：可能移动、可能复制，也可能因为被选函数删除／不可访问等而不合法。即使选中移动构造，资源效果仍由类型实现决定。[N4950：forward](https://timsong-cpp.github.io/cppwp/n4950/utility#forward)

[完整正例 T03](review/fm-verification-samples.md#t03) 对照了没有移动构造的复制回退，以及 `std::move(const_object)` 选择复制。**未声明移动构造**与**显式声明 deleted 移动构造**不同；后者可能在重载决议中胜出后使初始化失败。

---

## 6. Move 为什么特别适合 `noexcept`

典型 ownership type：

```cpp
Buffer(Buffer&& other) noexcept
    : data_{std::exchange(other.data_, nullptr)},
      size_{std::exchange(other.size_, 0)} {}
```

只需要：

```text
transfer handle
clear source
```

往往不需要：

```text
allocate
clone
I/O
```

因此 move 是非常适合 no-throw guarantee 的操作。

---

## 7. Copy 与 Failure

复制拥有型缓冲区通常需要分配独立资源并复制内容。只写 `new std::byte[n]` 而不复制数据，不能实现这里约定的值复制。

完整正例 T17 与 §6 的裸指针片段是两个独立实现。本例用 `unique_ptr` 管理数组；空缓冲区和移出后的对象均为 size 0、空指针。复制赋值通过按值参数和交换实现；参数复制可能在进入函数体前失败。

<!-- fm-test {"id":"T17","mode":"run"} -->
```cpp
#include <algorithm>
#include <cstddef>
#include <memory>
#include <span>
#include <utility>

class Buffer {
    std::unique_ptr<std::byte[]> data_;
    std::size_t size_ = 0;
public:
    Buffer() = default;
    explicit Buffer(std::span<const std::byte> input)
        : data_{input.empty() ? nullptr : std::make_unique<std::byte[]>(input.size())},
          size_{input.size()} {
        if (size_ != 0) std::copy_n(input.data(), size_, data_.get());
    }
    Buffer(const Buffer& other)
        : data_{other.size_ == 0 ? nullptr : std::make_unique<std::byte[]>(other.size_)},
          size_{other.size_} {
        if (size_ != 0) std::copy_n(other.data_.get(), size_, data_.get());
    }
    Buffer(Buffer&& other) noexcept
        : data_{std::move(other.data_)}, size_{std::exchange(other.size_, 0)} {}
    Buffer& operator=(Buffer other) noexcept {
        swap(other);
        return *this;
    }
    void swap(Buffer& other) noexcept {
        data_.swap(other.data_);
        std::swap(size_, other.size_);
    }
    std::span<std::byte> bytes() noexcept { return {data_.get(), size_}; }
};

int main() {
    const std::byte input[]{std::byte{1}, std::byte{2}, std::byte{3}};
    Buffer original{input};
    Buffer copied{original};
    if (copied.bytes().data() == original.bytes().data()
        || !std::ranges::equal(copied.bytes(), input)) return 1;
    copied.bytes()[0] = std::byte{9};
    if (original.bytes()[0] != std::byte{1}) return 2;
    Buffer empty;
    Buffer empty_copy{empty};
    if (!empty_copy.bytes().empty() || empty_copy.bytes().data() != nullptr) return 3;
    Buffer assigned;
    assigned = original;
    if (!std::ranges::equal(assigned.bytes(), input)) return 4;
    if (assigned.bytes().data() == original.bytes().data()) return 6;
    assigned.bytes()[0] = std::byte{8};
    if (original.bytes()[0] != std::byte{1}) return 7;
    Buffer moved{std::move(copied)};
    return copied.bytes().empty() && copied.bytes().data() == nullptr
        && moved.bytes()[0] == std::byte{9} ? 0 : 5;
}
```

分配仍可能抛出 `std::bad_alloc`；本例的字节复制本身不抛异常，已取得的资源由成员管理。T17 对复制构造和复制赋值检查完整长度与内容、存储独立及修改副本不影响源对象，另检查空对象和移出状态；不声称已经注入内存分配失败。这里使用比较两个完整区间的 `std::ranges::equal`，避免三迭代器版本只比较第一区间对应前缀而漏掉空值或截断复制。[N4950：alg.equal](https://timsong-cpp.github.io/cppwp/n4950/algorithms#alg.equal)

---

## 8. Container Relocation

假设：

```text
old vector

[A][B][C]
```

扩容：

```text
new storage
```

需要迁移元素。

如果 copy：

```text
copy A
copy B
copy C throws
```

旧：

```text
[A][B][C]
```

通常仍未改变。

新 storage 可以销毁。

这很有利于：

```text
strong guarantee
```

---

## 9. Throwing Move 的困难

如果：

```text
move A
move B
move C throws
```

旧 storage 可能已经：

```text
[A_moved][B_moved][C]
```

此时：

```text
rollback
```

并不简单。

因为把对象 move 回去：

```text
可能再次 throw
```

---

## 10. `std::move_if_noexcept`

`std::move_if_noexcept(value)` 同样只产生引用，不执行构造或资源转移：

| 类型条件 | 返回类型 |
| --- | --- |
| `!std::is_nothrow_move_constructible_v<T> && std::is_copy_constructible_v<T>` | `const T&` |
| 其他情况 | `T&&` |

后续初始化再通过重载决议选择操作；返回 `T&&` 也不证明存在或调用了移动构造。该工具有利于泛型算法选择复制回退，但不独自证明算法的异常保证。[N4950：forward](https://timsong-cpp.github.io/cppwp/n4950/utility#forward)

---

## 11. Move-Only + Throwing Move

删除复制而允许移动构造抛异常的类型没有复制回退。但“较弱保证”不能代替具体操作契约：

| 操作与条件 | N4950 中可依赖的范围 |
| --- | --- |
| `vector::reserve` | 通常异常时无效果；非 Cpp17CopyInsertable 类型的移动构造抛异常，是该无效果保证的明确例外 |
| `vector` 末尾插入单个元素，T 为 Cpp17CopyInsertable 或可不抛异常地从 `T&&` 构造 | 异常时无效果 |
| 插入条款的其他情形中，非 Cpp17CopyInsertable T 的移动构造抛异常 | effects unspecified，不能自行改写为 basic guarantee |

Cpp17CopyInsertable 是针对容器及其 allocator 的要求，不能只用“有没有复制构造”替代完整判定。上述例外不自动等于 UB，也不授权读取未被保证的旧值来推断恢复策略。[N4950：vector.capacity/4](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity#4)、[vector.modifiers/2](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers#2)

本项是条款核对；定向测试没有穷尽容器异常注入或所有实现的失败后状态。

---

## 12. Traits

常见：

```cpp
std::is_nothrow_move_constructible_v<T>
std::is_nothrow_move_assignable_v<T>
std::is_nothrow_copy_constructible_v<T>
std::is_nothrow_copy_assignable_v<T>
```

这些 traits 检查的是相应构造／赋值表达式的性质。例如 `is_nothrow_move_constructible_v<T>` 为真，也可能因为 `T&&` 绑定到不抛异常的复制构造，不能据此证明 T 存在移动构造。[T03](review/fm-verification-samples.md#t03) 给出反例。

它们不是纯 metaprogramming trivia。

它们描述：

```text
generic algorithm 可以依赖哪些 failure properties
```

---

## 13. `swap`

`swap` 经常作为：

```text
commit primitive
```

因此：

```cpp
void swap(T& other) noexcept;
```

非常有价值。

如果高层 strong guarantee 依赖：

```text
prepare
→ swap commit
```

那么 swap 可抛异常会破坏整个模型。

---

## 14. Defaulted Move

如果类型主要由标准 RAII members 组成：

```cpp
class Record {
public:
    Record(Record&&) = default;

private:
    std::string name_;
    std::vector<int> values_;
};
```

编译器生成 move 的 exception specification 会依据其 bases/members 的对应操作确定。

不要为了“性能”无条件手写：

```cpp
Record(Record&&) noexcept = default;
```

除非成员语义确实支持这一承诺。

---

## 15. 不要对 `noexcept` 撒谎

错误：

```cpp
Object(Object&& other) noexcept {
    resource_ = allocate_resource();
}
```

如果 allocation 抛异常：

```text
terminate
```

不是：

```text
move returned an error
```

因此：

> `noexcept` 是 correctness contract，不是 performance annotation。

---

## 16. Destructor 与 `noexcept`

Destructor 应被设计为：

```text
non-throwing cleanup boundary
```

不要通过：

```text
destructor exception
```

报告：

```text
flush failed
commit failed
close handshake failed
```

这些应在显式操作里报告。

---

## 17. Generic Guarantee Composition

可以形成：

```text
high-level non-propagation proof
=
all expression paths, arguments, temporaries and cleanup checked
+
any internal exceptions handled without new escaping exceptions
```

以及：

```text
high-level strong guarantee
=
algorithm structure
+
element operation properties
+
non-failing commit
```

第二个式子还要求 prepare 不改变受保护状态，以及提交后的返回和清理不违背保证；具体条件见 [FM-4 §5](fm4-raii-exception-safety.md#5-strong-guarantee-的核心模式)。这两个式子是工程证明提纲，不是仅凭 noexcept 或 traits 就能完成的证明。

---

## 18. FM-5 Review Checklist

```text
[ ] noexcept 是否是真实语义承诺？
[ ] move 是否真的只转移 ownership？
[ ] move 是否进行了 allocation/I/O/registration？
[ ] swap 是否能够 noexcept？
[ ] container relocation 是否依赖 nothrow move？
[ ] throwing move 是否还有 copy fallback？
[ ] defaulted special members 是否比手写实现更可靠？
[ ] generic noexcept 是否条件化？
[ ] 是否把 std::move 错解为“执行移动”？
[ ] 是否为了优化错误地扩大 noexcept？
```

---

## 19. FM-5 核心不变量

> `noexcept` 表示 exception 不会逃出函数。

> `std::move` 只改变 value category。

> Nothrow move 是类型提供给泛型算法的重要 capability。

> Throwing move 会限制 generic code 能提供的 strong guarantee。

> `noexcept` 必须源于真实语义，而不是性能愿望。

---

---
