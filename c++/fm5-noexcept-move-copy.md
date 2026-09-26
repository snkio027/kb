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

完全合法。

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

是一项非常强的 runtime contract。

---

## 3. `noexcept(expr)`

C++ 可以查询：

```cpp
noexcept(expression)
```

得到 compile-time `bool`。

例如：

```cpp
static_assert(noexcept(std::declval<T&>().swap(std::declval<T&>())));
```

注意：

```text
noexcept operator
```

不会执行 expression。

它只是查询异常规格。

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

```cpp
std::move(x)
```

本质上进行 value-category cast。

真正资源移动发生于：

```cpp
T y{std::move(x)};
```

选择的：

```cpp
T::T(T&&)
```

因此：

```text
std::move itself
≠
resource transfer
```

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

Copy 往往意味着：

```text
allocate new resource
copy content
```

例如：

```cpp
Buffer(const Buffer& other)
    : data_{new std::byte[other.size_]},
      size_{other.size_} {}
```

`new` 可能：

```text
throw std::bad_alloc
```

所以 copy 常常天然 potentially-throwing。

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

标准库提供：

```cpp
std::move_if_noexcept(value)
```

其核心策略可以理解为：

```text
move is noexcept
    → move

move may throw + copy available
    → prefer copy

move may throw + no copy
    → must move
```

目的是让泛型代码尽可能保持较强异常保证。

---

## 11. Move-Only + Throwing Move

例如：

```cpp
class T {
public:
    T(const T&) = delete;
    T(T&&); // may throw
};
```

泛型容器没有 copy fallback。

于是：

```text
relocation failure
```

可能导致操作只能提供较弱 guarantee。

这也是为什么类型的：

```text
nothrow move constructibility
```

是重要 API capability。

---

## 12. Traits

常见：

```cpp
std::is_nothrow_move_constructible_v<T>
std::is_nothrow_move_assignable_v<T>
std::is_nothrow_copy_constructible_v<T>
std::is_nothrow_copy_assignable_v<T>
```

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
high-level noexcept
=
all required low-level operations are non-throwing
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

这就是 C++ generic failure model 的核心。

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
