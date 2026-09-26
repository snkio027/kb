# G5 · 泛型、类型推导与编译期抽象

Modern C++ Systems Engineering · [Editorial Profile v1.0](editorial-profile.md) 编辑状态：Professional Handbook Edition。PDF：NOT BUILT / NOT VALIDATED。

- **Version:** 1.1
- **Status:** Professional Handbook Edition · 待集中审核
- **Language Baseline:** C++23
- **Prerequisites:** G0 Compiler / Linker Model, G1 Object Model, G2 RAII & Ownership, G3 Value Semantics
- **Scope:** Templates / Deduction / Forwarding / Class Templates / Concepts Core / `constexpr` / Instantiation / Compile-time vs Runtime Design
- **Deferred:** Advanced SFINAE / Constraint Subsumption / Heavy Template Metaprogramming

## 阅读入口

本章主线为模板实体、推导与转发、约束、常量求值、实例化控制及泛型边界。泛型编程（generic programming）处理可复用源码中的变化；编译期（compile time）与运行时（runtime）是决策发生的阶段，不是性能等级。首次阅读顺序见下列目录；跨语言、审查和术语用于回查。


### 章节目录

- [1. 泛型源代码与实例化模型](#g5-section-1)
- [2. 类型推导：实参与形参](#g5-section-2)
- [3. 引用折叠、转发与消费边界](#g5-section-3)
- [4. 类模板与编译期状态](#g5-section-4)
- [5. 约束与语义合同](#g5-section-5)
- [6. 常量求值与编译期分支](#g5-section-6)
- [7. 特化与运行时分派](#g5-section-7)
- [8. 编译模型与实例化控制](#g5-section-8)
- [9. 泛型边界与工程预算](#g5-section-9)
- [10. 跨语言回查](#g5-section-10)
- [11. 工程审查与反模式](#g5-section-11)
- [12. 统一模型与术语](#g5-section-12)
- [13. 实验与验证](#g5-section-13)
- [14. Final Gate](#g5-section-14)
- [15. Final Gate · 参考答案与常见误判](#g5-section-15)
- [16. 工程原则回查](#g5-section-16)
- [17. 参考与验证入口](#g5-section-17)

<a id="g5-section-1"></a>

## 1. 泛型源代码与实例化模型

<a id="g5-topic-0"></a>

### 1.1 编译期信息的工程边界

本章讨论哪些变化值得成为编译期信息。对象是否合法、谁负责清理以及值如何复制，分别属于 G1～G3；泛型编程（generic programming）则把类型、布局或算法策略的差异交给编译器形成具体实体。工程判断不在于模板写得多，而在于静态差异是否真正改善接口与实现，以及它应在哪一层停止传播。

<a id="g5-topic-1"></a>

### 1.2 Template 的本质

函数模板（function template）是参数化源码，不是运行时根据任意类型解释执行的万能函数。调用 `max_value(1, 2)` 可以推导出 `T = int`；需要定义时，实例化（instantiation）形成相应模板实体。

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
T max_value(T a, T b) {
    return a > b ? a : b;
}
```

这里还隐含比较和返回值构造要求；并不是任意 `T` 都适用。模板定义、某组实参对应的特化（specialization）和最终二进制符号是三个层次。优化可以内联、常量折叠、合并或删除代码，因此不能通过源代码中的特化数直接推断最终函数符号数。

<a id="g5-topic-2"></a>

### 1.3 Type Template Parameter

类型模板参数（type template parameter）占据的是类型位置。例如 `template<class T>` 中的 `T` 不是运行时变量、对象或类型描述符；当实参是 `int` 时，模板中的 `T value;` 按 `int` 的规则解释。类型替换并不取消初始化、对象生命周期或表达式合法性的要求。

<a id="g5-topic-3"></a>

### 1.4 Template Argument Deduction

模板实参推导（template argument deduction）需要分开记录三件事：推导得到的模板实参 `T`、替换并折叠后的形参类型、使用该形参的表达式值类别。三者可能不同：`T` 可以是 `int&`，形参最终也是 `int&`，而源码仍写着 `T&&`。G5-C1 用 `static_assert` 同时观察这些层次，避免只凭变量声明猜结果。

<a id="g5-section-2"></a>

## 2. 类型推导：实参与形参

<a id="g5-topic-4"></a>

### 2.1 By-value Deduction：`T`

按值形参 `T` 建立自己的参数对象。以 `const int x = 42;` 调用 `inspect(x)` 时，推导得到 `T = int`，不会把源对象的顶层 const 传播给新参数。

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
void inspect(T value);
const int x = 42;
// 在函数体中调用 inspect(x)：T 为 int。
```

这里忽略的是顶层 cv 限定，不是删除类型中的所有 const。`const int*` 指向的对象仍受 const 限制；把它推导成 `int*` 会错误地授予修改能力。推导规则与之后发生的参数初始化也应分别分析。

<a id="g5-topic-5"></a>

### 2.2 Reference Deduction：`T&`

`T&` 建立对实参的别名，推导必须保留使引用合法绑定的类型信息。以 const int 左值调用 `inspect_ref`，T 是 const int，最终形参是 const int&；以普通 int 左值调用，T 是 int。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void inspect_ref(T& value);
```

这里讨论函数模板调用推导，不把 T& 理解成“函数必然修改数据”。它说明可绑定的对象与访问能力，实际修改与业务合同还要看函数。

<a id="g5-topic-6"></a>

### 2.3 `const T&`

`const T&` 中的 const 由形参模式提供。以 int 或 const int 左值调用时，T 通常都推导为 int，最终形参都是 const int&。这与 T& 对 const 对象推导出 const int 不同，不能把最终形参类型直接当作 T。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void inspect_const_ref(const T& value);
```

该接口可以只读借用不同值类别的对象，但 const 引用不是生命周期保险；如果函数保存引用或把它交给异步任务，仍要分析对象何时结束。

<a id="g5-topic-7"></a>

### 2.4 三种最重要 Pattern

在普通调用的核心情况中，可用下表区分三个推导模式。表中 const int 是对象本身的 const；指向 const 的指针、数组等情况应继续按完整规则分析，而不是机械套表。

| 形参模式 | int 左值的 T | const int 左值的 T | 接口侧含义 |
| --- | --- | --- | --- |
| T | int | int | 建立独立参数对象 |
| T& | int | const int | 保留引用绑定所需限定 |
| const T& | int | int | 形参模式提供只读访问 |

推导后还要看参数初始化、重载决议及函数体。G5-C1 对表中的关键类型做静态断言，这与运行时打印一个编译器私有类型名相比，更直接地验证目标命题。

<a id="g5-section-3"></a>

## 3. 引用折叠、转发与消费边界

<a id="g5-topic-8"></a>

### 3.1 普通 Rvalue Reference

普通右值引用（rvalue reference）形参使用已经确定的类型，例如 `Frame&&`。它通常用于接收调用方显式交出的对象，但引用绑定本身不完成资源移动；函数体可以移动、读取，甚至完全不消费。

[机制片段 · 不承诺独立编译]

```cpp
void consume(Frame&& frame);
```

Frame 左值不能直接绑定到这个形参。调用方写 `std::move(frame)` 只提供右值绑定选择；资源是否被转移、转移后的状态是什么，仍由选中的操作和 Frame 合同决定。

<a id="g5-topic-9"></a>

### 3.2 Forwarding Reference

转发引用是待推导类型模板参数上的特定形式：函数调用推导中的无 cv 限定 T&& 可以同时接收左值和右值，并把调用方的绑定选择编码到 T 中。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void relay(T&& value);
```

这个规则不是“&& 能绑定任何东西”的通用规则。`const T&&` 和类模板中已经固定的 T 所构成的 T&&，都不满足上述条件；应先定位 T 在哪里被推导，再谈转发。

<a id="g5-topic-10"></a>

### 3.3 Forwarding Reference Deduction

下面以 int 为例逐层展开推导。表达式 `value` 是函数体内普通的具名参数使用；转发后的表达式类别由 T 与引用折叠共同决定。

| 调用实参 | 推导的 T | 最终形参类型 | std::forward<T>(value) |
| --- | --- | --- | --- |
| int 左值 | int& | int& | lvalue |
| const int 左值 | const int& | const int& | const lvalue |
| int 右值 | int | int&& | xvalue |

右值实参可能原来是 prvalue，也可能是 xvalue；转发参数并不重建原来的 prvalue 求值过程。这是“保留绑定选择”比“恢复一切原始值类别”更准确的原因。

<a id="g5-topic-11"></a>

### 3.4 Reference Collapsing

引用折叠（reference collapsing）在通过模板替换、类型别名等形成引用组合时生效。只要组合中有一个左值引用，结果就是左值引用；只有两个右值引用组合才得到右值引用。

| 组合 | 结果 |
| --- | --- |
| T& 与 & | T& |
| T& 与 && | T& |
| T&& 与 & | T& |
| T&& 与 && | T&& |

这是类型形成规则，不表示运行时存在一个可嵌套的“引用对象”。转发引用把左值实参推导进 T，再通过折叠使最终形参保持左值引用，G5-C1 对这一结果直接断言。

<a id="g5-topic-12"></a>

### 3.5 `T&&` 不一定是 Forwarding Reference

例如：

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
class Box {
public:
    void set(T&& value);
};
```

如果：

`Box<Frame>`

已经确定：`T = Frame` 那么：

`void set(Frame&& value);`

这里是普通 rvalue reference。 原因：`T` 不是由这次 `set()` 调用推导出来的。

<a id="g5-topic-13"></a>

### 3.6 Named `T&&` 仍然是 Lvalue Expression

普通表达式中的具名右值引用参数是左值。即使形参类型为 `Frame&&` 或推导得到 `T&&`，在函数体中直接写 `value` 通常仍按左值参与重载决议；需要消费或转发时，再明确转换。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void relay(T&& value) {
    consume(value);                  // 普通具名表达式是 lvalue。
    consume(std::forward<T>(value)); // 按推导结果转发。
}
```

两次调用只是对照片段，不建议实际消费同一参数两次。C++23 的 move-eligible return 等上下文另有隐式移动规则，不能把“具名就永远是 lvalue”当作无例外命题。

<a id="g5-topic-14"></a>

### 3.7 `std::move`

`std::move` 对对象表达式提供相应的 xvalue 转换，为后续重载决议开放右值路径。它自身不执行资源搬运，也不删除 const；结果可能选择移动、选择复制，或因没有可行操作而编译失败。

在接口设计中，显式 move 应对应当前代码允许消费源值的边界，而不是用于保证 O(1) 的优化咒语。消费后还想依赖原来的逻辑值，通常意味着合同没有想清楚；类型允许的移出状态操作仍可继续使用。

<a id="g5-topic-15"></a>

### 3.8 `std::forward<T>`

`std::forward<T>(value)` 使用推导信息恢复调用方的左值或右值绑定选择：左值实参仍以左值转发，右值实参以 xvalue 转发。它不会把已经具名的参数表达式重新变成 prvalue，也不负责移动资源、延长生命周期或验证所有权。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void relay(T&& value) {
    consume(std::forward<T>(value));
}
```

转发引用（forwarding reference）要求相应推导上下文中的无 cv 限定类型模板参数右值引用。已经固定的类模板参数 `T` 所形成的成员函数 `T&&` 不是新的转发引用；G5-C2 用编译负例区分这两种模型。[规则：N4950 temp.deduct.call](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call)

<a id="g5-topic-16"></a>

### 3.9 `move` 与 `forward` 的根本区别

move 与 forward 的差别在于绑定选择来自谁。move 由当前函数决定开放右值路径，forward 使用模板推导记录的调用方选择。两者都不直接执行移动构造。

在普通业务函数中，是否消费由当前层的合同决定；在泛型包装层中，通常应把选择传递给下游。不能因为 forward 看起来更通用，就用它掩盖 owner、borrower 或 sink 的职责。

<a id="g5-topic-17"></a>

### 3.10 API Role 决定 `move` / `forward`

**Borrow**

`void inspect(const Frame& frame);`

无需 move/forward。

**Ownership Sink**

[机制片段 · 不承诺独立编译]

```cpp
void submit(Frame frame) {
    queue_.push_back(std::move(frame));
}
```

这里函数已经拥有自己的 Frame value。 可以消费：

`std::move(frame)`

**Generic Forwarding Layer**

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
void relay(T&& value) {
    target(std::forward<T>(value));
}
```

wrapper 不应该擅自改变 caller 的 ownership/value-category 决定。

<a id="g5-topic-18"></a>

### 3.11 By-value Sink

按值 sink 先取得自己的参数对象，再将其移入成员，可以用一个明确接口同时处理复制调用方和允许被消费的调用方。

[机制片段 · 不承诺独立编译]

```cpp
void set_name(std::string name) {
    name_ = std::move(name);
}
```

左值实参通常复制构造参数，再执行成员移动赋值；右值实参的参数初始化可能移动，某些 prvalue 情况直接形成参数对象。这里的收益取决于 string 等具体表示及赋值状态，不应把它解释为永远少一次操作。它适合合同就是“取得一个值”的接口，不必为每个 setter 引入转发引用。

<a id="g5-topic-19"></a>

### 3.12 Perfect Forwarding 最自然的场景

Factory / emplacement：

[机制片段 · 不承诺独立编译]

```cpp
template <typename T, typename... Args>
std::unique_ptr<T> make_object(Args&&... args) {
    return std::unique_ptr<T>(
        new T(std::forward<Args>(args)...));
}
```

这里 wrapper：

不知道 T constructor 需要什么、也不应该替 caller 决定 copy/move。

所以 perfect forwarding 很合理。

<a id="g5-section-4"></a>

## 4. 类模板与编译期状态

<a id="g5-topic-20"></a>

### 4.1 Class Template

[机制片段 · 不承诺独立编译]

```cpp
template <typename T, std::size_t N>
class FixedBuffer;
```

这里：

```text
T
→ type template parameter

N
→ non-type template parameter
```

<a id="g5-topic-21"></a>

### 4.2 Non-type Template Parameter

`template <std::size_t N>`

中的 N 是：**compile-time value** 例如：

`FixedBuffer<float, 16>`

：

T = float、N = 16。

<a id="g5-topic-22"></a>

### 4.3 Different Arguments → Different Types

[机制片段 · 不承诺独立编译]

```cpp
FixedBuffer<float, 16>
FixedBuffer<float, 32>
FixedBuffer<int, 16>
```

三个都是不同 concrete C++ types。 不是：

`一个 Buffer type + 不同 runtime configuration`

所以：

[机制片段 · 不承诺独立编译]

```cpp
using A = FixedBuffer<float, 16>;
using B = FixedBuffer<float, 32>;

static_assert(!std::is_same_v<A, B>);
```

<a id="g5-topic-23"></a>

### 4.4 Template Argument 可以影响 Object Layout

[机制片段 · 不承诺独立编译]

```cpp
template <typename T, std::size_t N>
struct Buffer {
    std::array<T, N> storage;
};
```

于是：`Buffer<float,16>` 包含 16 个 float。 而：`Buffer<float,1024>` 包含 1024 个。 所以：

```text
compile-time parameter
↓
concrete type
↓
object layout
↓
sizeof / alignment / generated operations
```

都可能发生变化。

<a id="g5-topic-24"></a>

### 4.5 Compile-time Information vs Runtime State

Runtime：

[机制片段 · 不承诺独立编译]

```cpp
class Buffer {
    std::size_t capacity_;
};
```

每个 object 需要保存：`capacity_` Template：

`FixedBuffer<T, 16>`

capacity 已经由 type 表达。 可能不需要 object 再保存：`capacity = 16` 这一 runtime field。 所以：Template 可以把某些 runtime state 提升为 type-level compile-time information。

<a id="g5-topic-25"></a>

### 4.6 但不要把所有数据都 Template 化

适合 compile time：

type、fixed extent、small finite policy、endianness、algorithm mode、protocol layout、compile-time feature。

通常不适合：

timestamp、vehicle ID、request ID、user ID、sample value、大量动态 configuration。

核心判断：**它属于 program structure，还是 program data？**

<a id="g5-topic-26"></a>

### 4.7 `std::array<T, N>` 与 Reserved Storage 的区别

`std::array<T, N>` 将元素存储嵌入对象；成功构造的数组包含相应的 N 个元素对象（N 为零时没有元素）。`vector<T>::reserve(N)` 只保证容量下界，不把 size 增至 N，也不构造 N 个元素。固定长度既可进入类型和布局，也会影响构造、析构及移动成本；它不是可任意拿来按活对象访问的未初始化缓冲区。

<a id="g5-section-5"></a>

## 5. 约束与语义合同

<a id="g5-topic-27"></a>

### 5.1 Concepts — 当前阶段只保留 Core

Concept：**Template argument 的 compile-time contract。** 例如：

[机制片段 · 不承诺独立编译]

```cpp
template <std::integral T>
T twice(T value) {
    return value + value;
}
```

读成：T 必须满足 `std::integral`。

<a id="g5-topic-28"></a>

### 5.2 简单自定义 Concept

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
concept HasSize = requires(const T& value) {
    value.size();
};
```

表示：对这种 T，`value.size()` 必须是合法表达式。 然后：

[机制片段 · 不承诺独立编译]

```cpp
template <HasSize T>
void print_size(const T& value);
```

<a id="g5-topic-29"></a>

### 5.3 Concept 不是什么

Concept 不是：

base class、runtime interface、vtable、runtime type object。

它工作在：`compile time` 影响：

candidate eligibility、generic contract、instantiation、overload resolution。

<a id="g5-topic-30"></a>

### 5.4 Concept 的边界

Concept 可以检查表达式是否有效、结果类型是否符合限制，以及被编入约束的常量条件。它不能从一个比较表达式可调用就推导出严格弱序，也不能验证未编码的业务守恒关系。语法满足和语义建模应分别验收：编译负例可检验接口拒绝了不具备能力的类型，性质测试和论证才触及语义规律。

<a id="g5-topic-31"></a>

### 5.5 不要 Over-constrain

例如：

[机制片段 · 不承诺独立编译]

```cpp
template <std::copyable T>
void inspect(const T& value);
```

如果函数根本不 copy T：`std::copyable` 就可能是多余限制。 原则：**Concept 应表达算法真正需要的最小充分 contract。**

<a id="g5-topic-32"></a>

### 5.6 Concrete Interface 有时比 Concept 更好

如果 parser 只需要：contiguous bytes 那么：

`void parse(std::span<const std::byte> bytes);`

可能明显优于：

[机制片段 · 不承诺独立编译]

```cpp
template <ByteBuffer T>
void parse(const T& input);
```

因为 span 已经提供：

明确 data shape、简单 API、少 template instantiation、更小 compile surface。

所以：会 Concepts 不代表所有接口都应该 generic。

<a id="g5-section-6"></a>

## 6. 常量求值与编译期分支

<a id="g5-topic-33"></a>

### 6.1 `constexpr`

[机制片段 · 不承诺独立编译]

```cpp
constexpr int square(int x) {
    return x * x;
}
```

不要读成：“这是编译期函数。” 应该读成：**这个函数可以参与 constant evaluation。**

<a id="g5-topic-34"></a>

### 6.2 同一个 `constexpr` Function 可以两种执行

`constexpr int a = square(4);`

这里：`compile-time evaluation required` 而：

[机制片段 · 不承诺独立编译]

```cpp
int x = runtime_input();
int b = square(x);
```

可以：`runtime evaluation` 所以：

`constexpr ≠ always compile time`

<a id="g5-topic-35"></a>

### 6.3 `const` vs `constexpr`

`const int x = runtime_input();`

x 可以是 runtime value。 只是不允许通过 x 修改。 而：

`constexpr int x = 42;`

必须拥有 constant-expression value。 压缩：

```text
const
→ mutability constraint

constexpr
→ constant-evaluation constraint/capability
```

<a id="g5-topic-36"></a>

### 6.4 `consteval`

`consteval` 声明立即函数（immediate function）。普通调用上下文中的立即调用必须满足常量表达式要求；将运行时输入传入这种调用应诊断失败。立即函数上下文有进一步规则，因此这里不把它简化成“函数体中的每个中间调用都能独立在源码位置求值”。G5-C4 用 `argc` 制造明确不满足条件的普通调用。

<a id="g5-topic-37"></a>

### 6.5 `if constexpr`

`if constexpr` 根据常量条件选择结构分支。在模板实例化中，当条件不再依赖模板参数时，被丢弃分支不会按该特化继续实例化，所以类型相关的不同操作可以分别存在。但整个源码仍须被解析，非依赖错误不会因为位于 discarded statement 中就一概消失。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
constexpr auto scalar(T value) {
    if constexpr (std::is_pointer_v<T>) {
        return *value;
    } else {
        return value;
    }
}
```

指针分支的调用还要求指针指向可合法读取的对象；编译期选择不证明运行时生命周期。普通 `if` 不提供这种模板分支丢弃机制。[规则：N4950 stmt.if](https://timsong-cpp.github.io/cppwp/n4950/stmt.if)

<a id="g5-topic-38"></a>

### 6.6 `if constexpr` 可以让分支拥有不同合法表达式

模板分支可以使用不同类型能力，因为选中的条件和实例化规则决定哪些依赖表达式需要成立。

[机制片段 · 不承诺独立编译]

```cpp
template<class T>
void process(T value) {
    if constexpr (std::integral<T>) {
        value += 1;
    } else {
        value.do_something();
    }
}
```

对 `process(42)`，未选的依赖分支不要求 int 拥有 do_something。若改为普通 if，不能以运行时条件为由跳过该特化中的类型检查。对其他 T，被选中的 do_something 仍必须有效；constexpr 分支不是隐藏任意坏代码的容器。

<a id="g5-section-7"></a>

## 7. 特化与运行时分派

<a id="g5-topic-39"></a>

### 7.1 Compile-time Specialization

[机制片段 · 不承诺独立编译]

```cpp
template <Endian E>
std::uint16_t decode(...);
```

可能形成：

- decode<Endian::Little>
- decode<Endian::Big>

其中：`Endian` 已经从 runtime state 变成 program structure。 这可以：

remove repeated branch、enable constant propagation、enable inlining、specialize algorithm。

<a id="g5-topic-40"></a>

### 7.2 但 Template Version 不一定比 Runtime Version 快

Runtime：

`decode(bytes, Endian::Little);`

如果 optimizer 看得到：`Endian::Little` 是 constant，也可能通过：

inlining、constant propagation、branch elimination。

生成和 template specialization 几乎一样的 machine code。 所以：**不能仅凭源码有 template 就推断性能更好。** 要看：

assembly、benchmark、profile。

<a id="g5-topic-41"></a>

### 7.3 Dynamic Outside, Static Inside

很多系统现实是：

```text
startup/configuration
→ dynamic

steady-state processing
→ stable
```

因此很好的模式：

```text
runtime choice once
      ↓
enter specialized implementation
      ↓
hot loop many times
```

例如：

[机制片段 · 不承诺独立编译]

```cpp
switch (config.endian) {
case Endian::Little:
    process_stream<Endian::Little>(stream);
    break;

case Endian::Big:
    process_stream<Endian::Big>(stream);
    break;
}
```

核心思想：**低频 dynamic decision 移出高频 hot path。**

<a id="g5-section-8"></a>

## 8. 编译模型与实例化控制

<a id="g5-topic-42"></a>

### 8.1 Template Compilation Model

普通函数：

[机制片段 · 不承诺独立编译]

```cpp
// foo.hpp
int foo(int);

// foo.cpp
int foo(int x) {
    return x;
}
```

调用方编译时只需要 declaration。 最终由 linker 找 concrete definition。 Template：

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
T foo(T x);
```

调用：

`foo(42);`

需要：`foo<int>` compiler 要生成这个 concrete function，通常就必须看到：Template definition body。 这就是为什么 template definitions 经常位于 header。

<a id="g5-topic-43"></a>

### 8.2 Header-only Template

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
T foo(T value) {
    ...
}
```

定义放 header。 好处：

open genericity、consumer can instantiate required T、optimizer sees body。

代价：

more parsing、more instantiation、larger dependency surface、rebuild propagation、implementation exposure。

<a id="g5-topic-44"></a>

### 8.3 Zero Runtime Overhead ≠ Zero Engineering Cost

Template 可能拥有非常优秀 runtime performance。 但是可能支付：

compile time、binary size、debug symbol size、diagnostic complexity、dependency complexity。

所以：**zero-overhead abstraction 主要描述 runtime cost model，不等于 template 是免费机制。**

<a id="g5-topic-45"></a>

### 8.4 Explicit Instantiation

显式实例化（explicit instantiation）用于集中提供一组已知模板实参的实现。公共头文件给出声明和适当的 `extern template` 声明，提供方翻译单元持有定义并显式实例化所支持的类型；调用方链接到这些定义。 这不是让任意新类型都能在看不到定义时自动实例化。若公共接口允许写出 `scale<double>`，但提供方只生成 `scale<int>`，类型检查可能通过而链接失败。G5-C5 分别检查这种失败和提供 int 实现后的运行，并记录 `nm` 观察。符号拼写和优化后的实体数量不是可移植保证。

<a id="g5-section-9"></a>

## 9. 泛型边界与工程预算

<a id="g5-topic-46"></a>

### 9.1 Thin Template Front-end + Concrete Core

薄模板前端负责真正依赖类型的检查、适配或策略选择，具体核心实现接收 `span`、视图或普通参数，避免把相同工作按每种类型重新实例化。例如序列化前端可以检查输入类型，但核心只能在明确表示合同后处理字节。

[机制片段 · 不承诺独立编译]

```cpp
void consume_bytes(std::span<const std::byte> bytes);
template<class T>
void inspect_representation(std::span<const T> values) {
    consume_bytes(std::as_bytes(values));
}
```

这里观察的是对象表示，不是通用序列化或逻辑值相等算法；padding、端序、指针及 ABI 条件仍存在。具体核心减少重复实例化，但不能以丢弃类型为代价掩盖必要的语义合同。

<a id="g5-topic-47"></a>

### 9.2 Where Should Genericity Stop?

这是 G5 最重要的架构问题。 假设：

[机制片段 · 不承诺独立编译]

```cpp
FixedBuffer<int, 16>
FixedBuffer<int, 32>
FixedBuffer<int, 64>
```

如果算法不关心 N，不要机械写：

[机制片段 · 不承诺独立编译]

```cpp
template <std::size_t N>
void analyze(const FixedBuffer<int, N>&);
```

更合理的可能是：

`void analyze(std::span<const int>);`

这样：`storage detail N` 在 algorithm boundary 被擦除。

<a id="g5-topic-48"></a>

### 9.3 为什么这很好？

减少：

algorithm<16>、algorithm<32>、algorithm<64>。

这些几乎相同的 specializations。 同时获得：

simpler API、less compile time、smaller binary、less coupling。

所以：**不要让 compile-time variability 传播得比必要范围更远。**

<a id="g5-topic-49"></a>

### 9.4 Template vs Runtime Parameter

Runtime：

`decode(bytes, endian);`

优点：

one function、simple API、runtime flexibility、small code size、faster builds。

Template：

`decode<Endian::Little>(bytes);`

优点：

static policy、compile-time structural specialization、more optimization knowledge、possibly no runtime branch。

没有永远正确的一边。

<a id="g5-topic-50"></a>

### 9.5 如何决定 Static / Dynamic Boundary

问四个问题：

**1. 信息变化频率？**

```text
每次 sample
→ runtime

程序启动后不再变化
→ specialization candidate
```

**2. 它改变算法结构吗？**

```text
endianness
→ may change operations

timestamp
→ ordinary data
```

**3. Hot path 会不会重复检查它？**

如果每秒数百万次重复同一 decision：提前 bind/specialize 更有吸引力。

**4. 会产生多少 Specializations？**

```text
2
→ 很轻

8
→ 常常合理

6000
→ 要认真评估

combinatorial explosion
→ 危险
```

<a id="g5-topic-51"></a>

### 9.6 Combinatorial Instantiation Explosion

例如：

[机制片段 · 不承诺独立编译]

```cpp
template <
    Endian E,
    unsigned StartBit,
    unsigned Size,
    bool Signed,
    int ScaleNumerator,
    int ScaleDenominator>
struct Decoder;
```

参数组合可能爆炸。 你可能只是为了消除：

一个 branch、几个 metadata loads。

却换来了：

huge build time、huge code、large debug information、complex diagnostics。

所以：**compile-time 越多不等于越优秀。**

<a id="g5-topic-52"></a>

### 9.7 Template vs External Code Generation

二者都能：

```text
known metadata
↓
specialized executable structure
```

Template 更适合：

small policy set、type-oriented variation、compile-time dimensions、generic reusable components。

External codegen 更适合：

DBC、IDL、schema、CSV、hundreds/thousands of definitions、large generated registries。

语言无关核心：**稳定 metadata 可以从 runtime data 转化为 generated program structure。**

<a id="g5-topic-53"></a>

### 9.8 Genericity Budget

任何 template abstraction 都应该做一次成本核算。

**收益**

static checking、compile-time specialization、inlining opportunities、generic reuse、type-level invariants。

**成本**

compile time、code size、dependency propagation、diagnostic complexity、API complexity、ABI/binary-boundary complexity。

所以：**Genericity 是 architecture budget。**

<a id="g5-topic-54"></a>

### 9.9 设计 Ladder

遇到一个问题，不要直接 template。 从最具体开始：

```text
Concrete Function
      ↓
Concrete View / span
      ↓
Runtime Polymorphism
      ↓
Generic Template
      ↓
Compile-time Specialized Template
```

每向下一层增加能力，也增加复杂度。 选择：能表达真实需求的最简单 abstraction。

<a id="g5-topic-55"></a>

### 9.10 Concrete Type vs `span` vs Template

假设算法只需要：连续只读 samples。 可以：

[机制片段 · 不承诺独立编译]

```cpp
void process(
    const std::vector<Sample>& samples);
```

但暴露了 vector。 更窄：

[机制片段 · 不承诺独立编译]

```cpp
void process(
    std::span<const Sample> samples);
```

如果所有类型都能统一成这种 runtime view：没必要 template。 只有当算法真正需要保留：

different static types、different operations、different compile-time policies。

时，template 才更自然。

<a id="g5-topic-56"></a>

### 9.11 Static Polymorphism vs Dynamic Polymorphism

静态多态在编译期按具体类型选择行为，可能帮助内联和特化；动态多态通过运行时分派保留实现替换边界。两者应按变化发生的层次选择，而不是按“模板一定更快”排名。

[机制片段 · 不承诺独立编译]

```cpp
struct Processor {
    virtual ~Processor() = default;
    virtual void process() = 0;
};
```

虚函数接口可以隐藏某些实现细节，但不会自动形成跨编译器、跨版本的稳定 ABI。对象布局、调用约定、异常和所有权仍须约定。静态分派同样可能因代码膨胀损害指令工作集，实际成本交给 G6 的测量方法。

<a id="g5-section-10"></a>

## 10. 跨语言回查

<a id="g5-topic-57"></a>

### 10.1 C++ / Zig / Rust 对照

**C++**

`template <typename T, std::size_t N>`

特点：

template subsystem、deduction、specialization、reference collapsing、Concepts、constexpr。

能力极强，但历史层次很多。

**Zig**

```zig
fn foo(comptime T: type, comptime N: usize) type
```

倾向：`compile-time execution integrated with normal language model` 没有 C++：

- forwarding reference
- reference collapsing
- std::forward

整套机制。

**Rust**

```rust
struct Buffer<T, const N: usize>
```

和：

```rust
fn foo<T: Trait>(...)
```

分别提供：

generics、const generics、trait bounds、monomorphization。

Rust ownership/reference model和 C++ 不同，因此无需复制 C++ forwarding machinery。

<a id="g5-topic-58"></a>

### 10.2 三种语言共同的机器级事实

无论语言如何表达：

```text
static type/policy known
↓
compiler may specialize
↓
more optimization opportunities
```

同时：

```text
more concrete specializations
↓
more compile work / code
```

所以真正的 systems trade-off 是共同的。

<a id="g5-section-11"></a>

## 11. 工程审查与反模式

<a id="g5-topic-59"></a>

### 11.1 Code Review Protocol

看到：

`template <typename T>`

按下面检查。

**1. 为什么需要 Generic？**

普通 concrete API 不够吗？

**2. 什么东西在变化？**

- type?
- layout?
- algorithm?
- policy?

**3. 变化真的需要发生在 Compile Time 吗？**

还是 runtime data 更合适？

**4. 会有多少 Specializations？**

**5. 每个 Specialization 机器代码真的不同吗？**

**6. 是否在不必要地传播 Template Parameter？**

**7. 是否能在某层收敛成**

span、view、function pointer、ordinary function。

？

**8. 是否应该用 by-value sink，而不是 forwarding reference？**

**9. `std::move` 是否真的代表一次合理的 consumption boundary？**

**10. `std::forward` 是否真的位于 generic forwarding layer？**

**11. Template 定义是否必须全部暴露在 Header？**

**12. 实际性能收益是否被 benchmark / assembly 验证？**

<a id="g5-topic-60"></a>

### 11.2 高频 Anti-patterns

**Anti-pattern 1：Everything is Generic**

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
void parse(T&& input);
```

实际上：

`void parse(std::span<const std::byte>);`

已经足够。

**Anti-pattern 2：Cargo-cult Forwarding**

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
void set_model(T&& model);
```

只因为：“perfect forwarding 最快”。 而实际上 API 就是：

`void set_model(Model model);`

**Anti-pattern 3：Cargo-cult `std::move`**

`consume(std::move(value));`

却没搞清：source 之后是否还需要保持原 value。

**Anti-pattern 4：Template Every Runtime Constant**

Vehicle<123>、Message<456>、Request<789>。

导致 type proliferation。

**Anti-pattern 5：Specialize Thousands of Equivalent Paths**

为了一点微小 runtime branch 成本产生大量 machine code。

**Anti-pattern 6：Heavy Template Core**

[机制片段 · 不承诺独立编译]

```cpp
template <typename T>
void process(...) {
    // 500 lines
}
```

而真正 type-dependent 部分只有几行。 考虑：

`thin template adapter + ordinary implementation core`

**Anti-pattern 7：Compile-time Knowledge Leakage**

底层只因为：`N = 16` 整个上层 call graph 都变成：`template<N>` 导致无意义 specialization 扩散。

<a id="g5-section-12"></a>

## 12. 统一模型与术语

<a id="g5-topic-61"></a>

### 12.1 Final Mental Model

最终可以压缩为：

```text
                  GENERIC SOURCE
                       │
                       ▼
              template parameters
              ┌────────┴─────────┐
              │                  │
           Type T             Value N
              │                  │
              └────────┬─────────┘
                       ▼
                    Deduction
                       │
                       ▼
                   Constraints
                       │
                       ▼
                  Instantiation
                       │
             ┌─────────┴─────────┐
             │                   │
      concrete function     concrete type
             │                   │
             └─────────┬─────────┘
                       ▼
                 optimization
                       │
                       ▼
                  machine code
```

然后在架构层再问：

```text
Should this information
really be static?

        │
   ┌────┴────┐
  yes       no
   │         │
template   runtime data /
specialize concrete view
```

<a id="g5-topic-62"></a>

### 12.2 最终术语表

| Term                        | 核心含义                                             |
| --------------------------- | ---------------------------------------------------- |
| Template                    | 编译期参数化的源码抽象                               |
| Template Parameter          | 模板声明中的参数，如 `T` / `N`                       |
| Template Argument           | 使用模板时给出的具体参数，如 `int` / `16`            |
| Instantiation               | 根据模板和 arguments 形成具体模板实体的过程          |
| Specialization              | 针对具体 arguments 的模板实体                        |
| Type Parameter              | 类型模板参数，如 `typename T`                        |
| Non-type Template Parameter | 编译期值模板参数，如 `std::size_t N`                 |
| Template Argument Deduction | 从函数调用推导 template arguments                    |
| Reference Collapsing        | `&` / `&&` 组合后的引用折叠规则                      |
| Forwarding Reference        | 推导上下文中的特殊 `T&&`                             |
| Perfect Forwarding          | 保留 cv/ref 约束及左值/右值绑定选择的转发       |
| `std::move`                 | 无条件将表达式转换为可消费的 xvalue                  |
| `std::forward`              | 按推导参数保留左值/右值绑定选择（右值转为 xvalue）                  |
| Concept                     | 对 template arguments 的命名 compile-time constraint |
| `constexpr`                 | 可参与 constant evaluation 的语言机制                |
| `consteval`                 | 要求 immediate compile-time evaluation               |
| `if constexpr`              | compile-time structural branching                    |
| Explicit Instantiation      | 显式要求生成特定 specialization                      |
| Header-only                 | 模板实现对 consumer TU 可见的常见组织方式            |
| Code Bloat                  | 多 specializations 导致的代码体积增长                |
| Static Polymorphism         | compile-time 根据 concrete type 生成/选择行为        |

<a id="g5-section-13"></a>

## 13. 实验与验证

本章完整实验以 Markdown 中的源文件为准；从仓库根目录运行下列命令。执行器提取文件到新建临时目录，完整命令和原始输出写入结果记录，不修改历史制品。

[命令 · 自动提取、编译及分项记录]

```sh
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

只有带 `h-lab/h-file` 标记的完整实验及隔离反例参加本章定向执行；其他机制片段不是已验证的完整实现。改变条件用于理解判据，若未单独运行，不计作新增证据。

### 13.1 G5-C1 · 推导、转发与常量分支

**命题、观察与边界。** 用类型断言区分推导得到的 T、最终引用类型和表达式类别；同时让 constexpr 在常量与运行时输入上工作。运行输入为 argc，不把优化器常量折叠误称为语言要求。

<!-- h-lab {"id":"G5-C1","mode":"run"} -->

[完整实验 · G5-C1 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include <concepts>
#include <type_traits>
#include <utility>

template<class T> auto by_value(T) -> std::type_identity<T>;
template<class T> auto by_ref(T&) -> std::type_identity<T>;
template<class T> auto by_const_ref(const T&) -> std::type_identity<T>;
template<class T> constexpr bool inspect(T&& value) {
    static_assert(std::is_lvalue_reference_v<decltype((value))>);
    static_assert(std::same_as<decltype(std::forward<T>(value)), T&&>);
    return std::is_lvalue_reference_v<T>;
}
template<class T> constexpr auto scalar(T value) {
    if constexpr (std::is_pointer_v<T>) return *value;
    else return value;
}
constexpr int square(int n) { return n * n; }
template<std::integral T> constexpr T twice(T n) { return n + n; }

int main(int argc, char**) {
    int x = 7;
    const int cx = 8;
    const int* p = &cx;
    static_assert(std::same_as<decltype(by_value(cx))::type, int>);
    static_assert(std::same_as<decltype(by_value(p))::type, const int*>);
    static_assert(std::same_as<decltype(by_ref(cx))::type, const int>);
    static_assert(std::same_as<decltype(by_const_ref(cx))::type, int>);
    static_assert(square(4) == 16 && twice(4) == 8);
    static_assert(scalar(4) == 4);
    if (!inspect(x) || !inspect(cx) || inspect(7)) return 1;
    if (scalar(&x) != 7 || scalar(argc) != argc) return 2;
}
```

**运行与判据。** 上述统一命令中的 `G5-C1` 提取并处理本模块。静态断言、编译与运行均须成立；运行不产生输出且返回 0。

### 13.2 G5-C2 · 固定 T 的右值引用不能绑定左值

**命题、观察与边界。** Box<int> 的 T 已固定；成员 set(T&&) 不是转发引用。正例 G5-C1 的推导必须成功，本反例必须因引用绑定失败而被拒绝。

<!-- h-lab {"id":"G5-C2","mode":"compile_fail","diagnostic":"(?:rvalue reference.*cannot bind|cannot bind.*rvalue|expects an rvalue)"} -->

[反例 · 编译失败 · G5-C2 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
template<class T> struct Box { void set(T&&) {} };
int main() {
    Box<int> box;
    int value = 1;
    box.set(value);
}
```

**运行与判据。** 上述统一命令中的 `G5-C2` 提取并处理本模块。只编译不链接，必须匹配指定语义诊断；超时、信号退出和无关错误均不算符合预期。

### 13.3 G5-C3 · Concept 拒绝不满足约束的类型

**命题、观察与边界。** std::integral 约束拒绝 double；测试匹配约束诊断，不把缺少头文件或链接失败算作成功。它不检验比较器等概念的语义规律。

<!-- h-lab {"id":"G5-C3","mode":"compile_fail","diagnostic":"(?:constraints not satisfied|constraint.*not satisfied)"} -->

[反例 · 编译失败 · G5-C3 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include <concepts>
template<std::integral T> constexpr T twice(T x) { return x + x; }
int main() { return static_cast<int>(twice(1.5)); }
```

**运行与判据。** 上述统一命令中的 `G5-C3` 提取并处理本模块。只编译不链接，必须匹配指定语义诊断；超时、信号退出和无关错误均不算符合预期。

### 13.4 G5-C4 · 立即调用不能使用运行时实参

**命题、观察与边界。** 把 argc 传入普通上下文中的 consteval 调用，必须出现常量表达式相关诊断；对应的 constexpr 正例见 G5-C1。

<!-- h-lab {"id":"G5-C4","mode":"compile_fail","diagnostic":"(?:not a constant expression|not usable in a constant expression)"} -->

[反例 · 编译失败 · G5-C4 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
consteval int immediate(int n) { return n + 1; }
int main(int argc, char**) { return immediate(argc); }
```

**运行与判据。** 上述统一命令中的 `G5-C4` 提取并处理本模块。只编译不链接，必须匹配指定语义诊断；超时、信号退出和无关错误均不算符合预期。

### 13.5 G5-C5 · 显式实例化与二进制符号

**命题、观察与边界。** 先分别编译 TU，再观察提供方目标文件。int 的显式实例化可链接并得到 6；调用未提供的 double 特化必须在链接阶段失败。nm 输出只作观察，不固定 ABI 拼写、地址或符号个数。

<!-- h-lab {"id":"G5-C5","mode":"symbols","diagnostic":"(?:undefined|Undefined)[\\s\\S]*scale"} -->

[完整实验 · G5-C5 · scale.hpp]

<!-- h-file {"path":"scale.hpp"} -->
```cpp
#pragma once
template<class T> T scale(T value);
extern template int scale<int>(int);
```

[完整实验 · G5-C5 · scale.cpp]

<!-- h-file {"path":"scale.cpp"} -->
```cpp
#include "scale.hpp"
template<class T> T scale(T value) { return value + value; }
template int scale<int>(int);
```

[完整实验 · G5-C5 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include "scale.hpp"
int main() { return scale(3) == 6 ? 0 : 1; }
```

[完整实验 · G5-C5 · missing.cpp]

<!-- h-file {"path":"missing.cpp"} -->
```cpp
#include "scale.hpp"
int main() { return scale(1.5) == 3.0 ? 0 : 1; }
```

**运行与判据。** 上述统一命令中的 `G5-C5` 提取并处理本模块。分别编译 scale.cpp、main.cpp 与 missing.cpp；先记录符号，再检查正例和缺失特化的链接诊断。

<a id="g5-section-14"></a>

## 14. Final Gate

<a id="g5-topic-63"></a>

复习时至少能够闭卷解释这些问题：

### 14.1 Template

1. Function template 和普通 function 最大的编译模型区别是什么？
2. 为什么一个 template 可以形成多个 concrete functions？
3. Instantiation 和 specialization 分别是什么？

### 14.2 Deduction

1. `T`、`T&`、`const T&` 的 deduction 有什么区别？
2. top-level `const` 为什么在 by-value deduction 中通常消失？
3. 为什么 pointer-to-const 中的 const 不能随意消失？

### 14.3 Forwarding

1. 普通 `Frame&&` 与 `template<typename T> T&&` 有什么不同？
2. 什么条件下 `T&&` 才是 forwarding reference？
3. Reference collapsing 是什么？
4. 为什么 named `T&&` expression 仍然是 lvalue？
5. `std::move` 和 `std::forward` 的语义区别是什么？

### 14.4 Class Templates

 1. 为什么 `Buffer<float,16>` 与 `Buffer<float,32>` 是不同类型？
 2. Non-type template parameter 如何影响 object layout？
 3. 为什么不应该把普通 runtime identity 全部变成 NTTP？

### 14.5 Lifetime

 1. 为什么 `array<T,N>` 与 `vector<T>::reserve(N)` 的 object lifetime 完全不同？

### 14.6 Concepts

 1. Concept 解决什么问题？
 2. Concept 是 runtime interface 吗？
 3. 为什么 Concept 不能保证 semantic laws？

### 14.7 Constant Evaluation

 1. 为什么 `constexpr function` 不等于“永远编译期执行”？
 2. `const` 和 `constexpr` 有什么根本区别？
 3. `if constexpr` 与普通 `if` 的核心区别是什么？

### 14.8 Compilation

 1. 为什么 template definitions 通常放 header？
 2. Explicit instantiation 解决什么问题？
 3. Header-only generic library 的主要工程成本是什么？

### 14.9 Architecture

 1. 什么叫 `Dynamic Outside, Static Inside`？
 2. 哪些信息适合 compile time，哪些更适合 runtime？
 3. 为什么 template specialization 不一定比 runtime parameter 快？
 4. 什么情况下应该用 external codegen 而不是 template？
 5. 为什么要限制 genericity 的传播范围？
 6. Thin template front-end + concrete core 有什么价值？

<a id="g5-section-15"></a>

## 15. Final Gate · 参考答案与常见误判

### 15.1 Template 与 Deduction

Template 1～3：普通非模板函数的调用通常只需声明可见，模板特化需要遵守相应定义可达和实例化规则。同一参数化源码可以形成不同实参的实体；实例化是形成实体的机制，specialization 指对应具体实参的实体，不限于手写显式特化。最终是否保留独立机器符号还取决于优化与链接，不能把三者画成等号。

Deduction 1～3：按值 T 忽略实参的顶层 cv；T& 保留所引用对象的 const；const T& 由形参模式提供 const，不能据最终形参含 const 就断言 T 也含 const。指向 const 对象的指针中的 const 不在顶层，去掉它会授予错误的写权限。G5-C1 分别断言这些类型；编译成功证明的是这些命题在本配置被接受，不是所有推导场景已穷举。

### 15.2 Forwarding、Class Templates 与 Lifetime

Forwarding 1～5：已知 Frame&& 只接受相应右值绑定；无 cv 的待推导类型参数 T&& 才可能是转发引用。左值实参使 T 推导为引用，再按“出现 & 则折叠为 &，仅 && 与 && 得 &&”形成最终类型。普通具名参数表达式是左值，C++23 隐式移动上下文另论。move 无条件产生相应右值引用转换，forward 按推导信息保留左值/右值绑定选择；二者都不搬运资源，也不证明生命周期。

Class Templates 1～3：不同 N 属于不同模板实参组合，因而形成不同类型；N 若决定内嵌数组长度，就会影响表示与对象数。运行时 ID 若只用于比较而不改变结构，进入 NTTP 会扩大类型和特化集合，却不一定增加优化机会。Lifetime 1：成功构造的 array 有 N 个元素；reserve 只预留容量，不增加 vector 的元素数。把 capacity 当作活对象数是原有对象模型错误，不是泛型的特例。

### 15.3 Concepts、Constant Evaluation 与 Compilation

Concepts 1～3：Concept 在编译期表达被编码的约束，不是虚函数式运行时接口。表达式成立不证明严格弱序、复杂度或业务不变量；约束负例与语义测试承担不同责任。 Constant Evaluation 1～3：constexpr 函数允许符合条件的常量求值，也可用运行时输入执行；const 仅限制修改，不保证初始化来自常量表达式。if constexpr 可丢弃模板中的未选依赖分支，普通 if 不能提供同样的实例化选择；非依赖错误和语法仍须合法。不要用“优化后看不到指令”反推语言强制编译期执行。

Compilation 1～3：隐式实例化需要相应定义，所以头文件是常见组织方式，但不是唯一手段。显式实例化可以集中提供已知组合；未提供的组合不会因此获得定义。头文件泛型会增加解析、实例化、诊断、依赖和增量构建成本，运行时零额外开销不等于工程零成本。

### 15.4 Architecture

Architecture 1～6：Dynamic Outside, Static Inside 在外层读取运行时配置，再选有限的静态内核。改变类型、布局或热路径结构且取值集合可控的信息更适合静态化；频繁变化的普通数据应留在运行时。优化器也能常量传播普通参数，特化还可能膨胀指令工作集，因此“模板更快”必须实测。

已有 DBC、IDL 或协议描述适合外部代码生成，尤其当需要多语言产物或独立检查时；这不是再造一个模板元编程框架的理由。限制泛型传播能控制组合数和接口负担；薄前端只保留必要类型信息，具体核心复用真正相同的逻辑。代价是必须写清类型擦除后的表示合同，不能把任意对象字节当作可移植消息。

<a id="g5-section-16"></a>

## 16. 工程原则回查

<a id="g5-topic-64"></a>

### 16.1 如果半年后只记住十五条

1. **Template 是 compile-time parameterization，不是 runtime dynamic genericity。**

2. **Template 会根据 arguments 形成 concrete functions/types。**

3. **始终分开 deduced `T`、最终 parameter type 和 expression value category。**

4. **By-value deduction 通常丢弃 top-level cv；reference deduction必须保留合法 alias 所需的信息。**

5. **Forwarding reference 是 deduction context 中特殊的 `T&&`，不是所有 `T&&`。**

6. **普通具名右值引用参数表达式是 lvalue；C++23 隐式移动上下文另有规则。**

7. **`std::move` 表示当前代码允许消费 source；`std::forward` 表示 generic wrapper 保留 caller 的决定。**

8. **Class template arguments 可以进入类型和 layout；`Buffer<T,16>` 与 `Buffer<T,32>` 是不同类型。**

9. **成功构造的 `std::array<T,N>` 包含 N 个元素对象；reserve 不增加 vector 的 size。**

10. **Concept 是 compile-time generic contract，不是 runtime interface。**

11. **`constexpr` 表示 constant-evaluation 能力；`if constexpr` 表示 compile-time structural selection。**

12. **Template definitions 通常需要在 instantiation point 可见，因此直接影响 header/TU/build architecture。**

13. **Static specialization 可以减少 runtime work，但会增加 compile-time/code-size complexity。**

14. **不要让 compile-time variability 比真正需要的范围传播得更远。**

15. **优秀 Generic Programming 的标志不是 template 多，而是清楚知道 genericity 应该在哪里停止。**

<a id="g5-section-17"></a>

## 17. 参考与验证入口

[全系列导航](README.md) · [实验说明](learning/README.md) · [本批修订与证据](learning/professional-revision.md)

语言规则采用 N4950 的 [模板推导](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call)、[模板实例化](https://timsong-cpp.github.io/cppwp/n4950/temp.inst) 与 [if constexpr](https://timsong-cpp.github.io/cppwp/n4950/stmt.if)；编译器实验不是这些规则的替代定义。
