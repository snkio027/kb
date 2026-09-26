# C++ Systems Track · G5 Generic Programming & Compile-time Abstraction

**Version:** 1.0  
**Status:** Frozen Review Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0 Compiler / Linker Model, G1 Object Model, G2 RAII & Ownership, G3 Value Semantics  
**Scope:** Templates / Deduction / Forwarding / Class Templates / Concepts Core / `constexpr` / Instantiation / Compile-time vs Runtime Design  
**Deferred:** Advanced SFINAE / Constraint Subsumption / Heavy Template Metaprogramming

---

# 0. G5 到底解决什么问题？

G1 问：

> 一个 C++ object 是什么，它什么时候存在，怎样访问才合法？

G2 问：

> 谁拥有 resource，谁负责 lifetime？

G3 问：

> value 怎样 copy / move / return，成本是什么？

G5 开始问：

> **哪些程序结构可以由 compiler 根据类型和值在编译期生成？**

核心链路：

```text
Generic Source
    ↓
Template Arguments
    ↓
Deduction
    ↓
Constraint Checking
    ↓
Instantiation
    ↓
Concrete Type / Function
    ↓
Optimization
    ↓
Machine Code
```

最重要的思想不是：

> “会写 `template<typename T>`。”

而是：

> **能够判断什么信息值得进入 compile time，什么应该继续作为普通 runtime data。**

---

# 1. Template 的本质

## 1.1 Function Template 不是普通函数

```cpp
template <typename T>
T max_value(T a, T b) {
    return a > b ? a : b;
}
```

这不是一个 runtime 再检查 `T` 的“万能函数”。

更准确的模型：

```text
             max_value<T>
                  │
       ┌──────────┼──────────┐
       │          │          │
    T = int    T = float  T = Robot
       │          │          │
       ▼          ▼          ▼
max_value<int> ...
```

即：

> **Template 是生成 concrete program entities 的 compile-time parameterized source。**

---

## 1.2 Instantiation

调用：

```cpp
max_value(1, 2);
```

compiler 推导：

```text
T = int
```

并在需要时形成：

```text
max_value<int>
```

这个过程叫：

> **Template Instantiation — 模板实例化**

必须区分：

```text
template definition
≠
concrete specialization
≠
final binary symbol
```

因为 optimizer 还可能：

```text
inline
constant-fold
dead-code-eliminate
merge
```

具体 specialization。

---

# 2. Type Template Parameter

```cpp
template <typename T>
```

这里：

```text
T
```

是：

> **Type Template Parameter**

不是：

```text
runtime variable
runtime type descriptor
object
```

实例化：

```text
T = int
```

以后：

```cpp
T value;
```

就是：

```cpp
int value;
```

---

# 3. Template Argument Deduction

这是 G5 最重要的机制之一。

以后分析 template，始终分开：

```text
① deduced template argument

② parameter type after substitution

③ expression value category
```

这三者不是一个东西。

---

# 4. By-value Deduction：`T`

```cpp
template <typename T>
void inspect(T value);
```

如果：

```cpp
const int x = 42;
inspect(x);
```

通常：

```text
T = int
parameter type = int
```

原因：

> 函数获得自己的新 object。

caller object 的 top-level `const` 不需要传递给这个 copy。

---

## 4.1 Top-level `const`

```cpp
const int x;
```

这里 const 直接修饰整个 int object：

```text
top-level const
```

而：

```cpp
const int* p;
```

这里 pointer 本身不是 const。

const 修饰的是：

```text
pointee
```

因此：

```cpp
inspect(p);
```

会保留：

```text
T = const int*
```

不能随意把 pointee constness 丢掉。

---

# 5. Reference Deduction：`T&`

```cpp
template <typename T>
void inspect(T& value);
```

如果：

```cpp
const int x = 42;
inspect(x);
```

则：

```text
T = const int
parameter = const int&
```

因为 reference 直接绑定 caller object。

必须保留合法访问所需的 constness。

---

# 6. `const T&`

```cpp
template <typename T>
void inspect(const T& value);
```

对于：

```cpp
const int x = 42;
inspect(x);
```

通常：

```text
T = int
parameter = const int&
```

`const` 已经来自 parameter pattern：

```cpp
const T&
```

不需要再放进 T。

---

# 7. 三种最重要 Pattern

假设：

```cpp
const int x = 42;
```

## `T`

```cpp
template <typename T>
void f(T);
```

得到：

```text
T = int
parameter = int
```

---

## `T&`

```cpp
template <typename T>
void f(T&);
```

得到：

```text
T = const int
parameter = const int&
```

---

## `const T&`

```cpp
template <typename T>
void f(const T&);
```

得到：

```text
T = int
parameter = const int&
```

---

# 8. 普通 Rvalue Reference

```cpp
void consume(Frame&& frame);
```

这里：

```text
Frame&&
```

是普通：

> **rvalue reference**

普通 lvalue：

```cpp
Frame frame;
consume(frame);
```

不能直接绑定。

需要：

```cpp
consume(std::move(frame));
```

---

# 9. Forwarding Reference

但：

```cpp
template <typename T>
void relay(T&& value);
```

情况不同。

如果 `T` 是这次函数调用中需要推导的 template parameter，则：

```text
T&&
```

可以成为：

> **Forwarding Reference**

---

# 10. Forwarding Reference Deduction

## Lvalue

```cpp
int x = 42;
relay(x);
```

推导：

```text
T = int&
```

于是：

```text
T&&
→ int& &&
→ int&
```

---

## Const Lvalue

```cpp
const int x = 42;
relay(x);
```

：

```text
T = const int&
parameter = const int&
```

---

## Rvalue

```cpp
relay(42);
```

：

```text
T = int
parameter = int&&
```

统一表：

| Argument           | `T`          | Parameter    |
| ------------------ | ------------ | ------------ |
| `int` lvalue       | `int&`       | `int&`       |
| `const int` lvalue | `const int&` | `const int&` |
| `int` rvalue       | `int`        | `int&&`      |

---

# 11. Reference Collapsing

核心规则：

```text
T&  &  → T&
T&  && → T&
T&& &  → T&
T&& && → T&&
```

工程上可以压成：

> **只要组合里出现 `&`，最终基本就是 `&`；只有纯 `&& + &&` 才保持 `&&`。**

---

# 12. `T&&` 不一定是 Forwarding Reference

例如：

```cpp
template <typename T>
class Box {
public:
    void set(T&& value);
};
```

如果：

```cpp
Box<Frame>
```

已经确定：

```text
T = Frame
```

那么：

```cpp
void set(Frame&& value);
```

这里是普通 rvalue reference。

原因：

> `T` 不是由这次 `set()` 调用推导出来的。

---

# 13. Named `T&&` 仍然是 Lvalue Expression

```cpp
void consume(Frame&& frame) {
    use(frame);
}
```

尽管：

```text
declared type = Frame&&
```

但是表达式：

```cpp
frame
```

是：

```text
lvalue
```

因为它有名字和 identity。

这就是为什么：

```cpp
Frame(Frame&& other) noexcept
    : bytes_(std::move(other.bytes_)) {}
```

内部仍然需要：

```cpp
std::move(other.bytes_)
```

---

# 14. `std::move`

`std::move(x)` 不负责真正移动 resource。

它本质上表达：

> **允许后续 operation 把 x 当成可消费 source。**

概念：

```text
std::move(x)
↓
xvalue expression
↓
move overload may be selected
↓
move constructor / assignment performs state transfer
```

所以应该读成：

> **“我从这里开始允许消费 x。”**

不是：

> “优化一下 x。”

---

# 15. `std::forward<T>`

Generic wrapper：

```cpp
template <typename T>
void relay(T&& value) {
    consume(std::forward<T>(value));
}
```

`std::forward<T>` 的作用：

> **恢复 caller 原本传来的 value category。**

如果 caller：

```cpp
relay(frame);
```

则 forward 为 lvalue。

如果：

```cpp
relay(Frame{});
```

则 forward 为 xvalue。

---

# 16. `move` 与 `forward` 的根本区别

| 工具                 | 谁决定是否消费 source？ |
| -------------------- | ----------------------- |
| copy                 | source 必须保持         |
| `std::move(x)`       | 当前这层代码            |
| `std::forward<T>(x)` | 原始 caller             |

压缩：

```text
copy
→ preserve source

move
→ consume source

forward
→ preserve caller's choice
```

---

# 17. API Role 决定 `move` / `forward`

## Borrow

```cpp
void inspect(const Frame& frame);
```

无需 move/forward。

---

## Ownership Sink

```cpp
void submit(Frame frame) {
    queue_.push_back(std::move(frame));
}
```

这里函数已经拥有自己的 Frame value。

可以消费：

```cpp
std::move(frame)
```

---

## Generic Forwarding Layer

```cpp
template <typename T>
void relay(T&& value) {
    target(std::forward<T>(value));
}
```

wrapper 不应该擅自改变 caller 的 ownership/value-category 决定。

---

# 18. By-value Sink

非常重要的现代模式：

```cpp
class Robot {
public:
    explicit Robot(std::string name)
        : name_(std::move(name)) {}

private:
    std::string name_;
};
```

caller：

```cpp
Robot a{name};
```

lvalue：

```text
copy into parameter
↓
move into member
```

caller：

```cpp
Robot b{std::move(name)};
```

：

```text
move into parameter
↓
move into member
```

如果 T move 很便宜，这是非常清晰的 ownership API。

不要机械地全部改成 forwarding constructor。

---

# 19. Perfect Forwarding 最自然的场景

Factory / emplacement：

```cpp
template <typename T, typename... Args>
std::unique_ptr<T> make_object(Args&&... args) {
    return std::unique_ptr<T>(
        new T(std::forward<Args>(args)...));
}
```

这里 wrapper：

```text
不知道 T constructor 需要什么
也不应该替 caller 决定 copy/move
```

所以 perfect forwarding 很合理。

---

# 20. Class Template

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

---

# 21. Non-type Template Parameter

```cpp
template <std::size_t N>
```

中的 N 是：

> **compile-time value**

例如：

```cpp
FixedBuffer<float, 16>
```

：

```text
T = float
N = 16
```

---

# 22. Different Arguments → Different Types

```cpp
FixedBuffer<float, 16>
FixedBuffer<float, 32>
FixedBuffer<int, 16>
```

三个都是不同 concrete C++ types。

不是：

```text
一个 Buffer type
+
不同 runtime configuration
```

所以：

```cpp
using A = FixedBuffer<float, 16>;
using B = FixedBuffer<float, 32>;

static_assert(!std::is_same_v<A, B>);
```

---

# 23. Template Argument 可以影响 Object Layout

```cpp
template <typename T, std::size_t N>
struct Buffer {
    std::array<T, N> storage;
};
```

于是：

```text
Buffer<float,16>
```

包含 16 个 float。

而：

```text
Buffer<float,1024>
```

包含 1024 个。

所以：

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

---

# 24. Compile-time Information vs Runtime State

Runtime：

```cpp
class Buffer {
    std::size_t capacity_;
};
```

每个 object 需要保存：

```text
capacity_
```

Template：

```cpp
FixedBuffer<T, 16>
```

capacity 已经由 type 表达。

可能不需要 object 再保存：

```text
capacity = 16
```

这一 runtime field。

所以：

> Template 可以把某些 runtime state 提升为 type-level compile-time information。

---

# 25. 但不要把所有数据都 Template 化

适合 compile time：

```text
type
fixed extent
small finite policy
endianness
algorithm mode
protocol layout
compile-time feature
```

通常不适合：

```text
timestamp
vehicle ID
request ID
user ID
sample value
大量动态 configuration
```

核心判断：

> **它属于 program structure，还是 program data？**

---

# 26. `std::array<T, N>` 与 Reserved Storage 的区别

```cpp
std::array<Frame, 1024> frames;
```

意味着：

```text
1024 Frame objects alive
```

而：

```cpp
std::vector<Frame> frames;
frames.reserve(1024);
```

意味着：

```text
storage capacity >= 1024

but

size == 0
0 Frame objects alive
```

必须永久区分：

```text
storage
≠
object lifetime
```

Template 不会改变 G1 的 lifetime rules。

---

# 27. Concepts — 当前阶段只保留 Core

Concept：

> **Template argument 的 compile-time contract。**

例如：

```cpp
template <std::integral T>
T twice(T value) {
    return value + value;
}
```

读成：

> T 必须满足 `std::integral`。

---

# 28. 简单自定义 Concept

```cpp
template <typename T>
concept HasSize = requires(const T& value) {
    value.size();
};
```

表示：

> 对这种 T，`value.size()` 必须是合法表达式。

然后：

```cpp
template <HasSize T>
void print_size(const T& value);
```

---

# 29. Concept 不是什么

Concept 不是：

```text
base class
runtime interface
vtable
runtime type object
```

它工作在：

```text
compile time
```

影响：

```text
candidate eligibility
generic contract
instantiation
overload resolution
```

---

# 30. Concept 的边界

Concept 可以检查：

```text
expression 是否存在
type relationship
compile-time property
部分 noexcept property
```

但一般不能证明：

```text
comparison transitive
hash 和 equality 语义一致
copy 保持 logical value
decoder 实际正确
```

因此 generic contract 仍然包含：

```text
machine-checkable structural requirements
+
human-guaranteed semantic laws
```

---

# 31. 不要 Over-constrain

例如：

```cpp
template <std::copyable T>
void inspect(const T& value);
```

如果函数根本不 copy T：

> `std::copyable` 就可能是多余限制。

原则：

> **Concept 应表达算法真正需要的最小充分 contract。**

---

# 32. Concrete Interface 有时比 Concept 更好

如果 parser 只需要：

> contiguous bytes

那么：

```cpp
void parse(std::span<const std::byte> bytes);
```

可能明显优于：

```cpp
template <ByteBuffer T>
void parse(const T& input);
```

因为 span 已经提供：

```text
明确 data shape
简单 API
少 template instantiation
更小 compile surface
```

所以：

> 会 Concepts 不代表所有接口都应该 generic。

---

# 33. `constexpr`

```cpp
constexpr int square(int x) {
    return x * x;
}
```

不要读成：

> “这是编译期函数。”

应该读成：

> **这个函数可以参与 constant evaluation。**

---

# 34. 同一个 `constexpr` Function 可以两种执行

```cpp
constexpr int a = square(4);
```

这里：

```text
compile-time evaluation required
```

而：

```cpp
int x = runtime_input();
int b = square(x);
```

可以：

```text
runtime evaluation
```

所以：

```text
constexpr
≠
always compile time
```

---

# 35. `const` vs `constexpr`

```cpp
const int x = runtime_input();
```

x 可以是 runtime value。

只是不允许通过 x 修改。

而：

```cpp
constexpr int x = 42;
```

必须拥有 constant-expression value。

压缩：

```text
const
→ mutability constraint

constexpr
→ constant-evaluation constraint/capability
```

---

# 36. `consteval`

```cpp
consteval int square(int x) {
    return x * x;
}
```

调用必须在 compile time 成功求值。

粗略对照：

```text
ordinary function
→ runtime normally

constexpr
→ compile-time or runtime

consteval
→ compile-time required
```

当前阶段认识即可。

---

# 37. `if constexpr`

```cpp
template <typename T>
void process(T value) {
    if constexpr (std::integral<T>) {
        ...
    } else {
        ...
    }
}
```

它不是单纯：

> 更快的 `if`。

核心是：

> **根据 compile-time condition 选择当前 specialization 的代码结构。**

---

# 38. `if constexpr` 可以让分支拥有不同合法表达式

```cpp
template <typename T>
void process(T value) {
    if constexpr (std::integral<T>) {
        value += 1;
    } else {
        value.do_something();
    }
}
```

对于：

```cpp
process(42);
```

T = int。

else 分支是 discarded dependent branch。

不要求：

```cpp
int::do_something()
```

存在。

普通 `if` 不具备相同 template semantic behavior。

---

# 39. Compile-time Specialization

```cpp
template <Endian E>
std::uint16_t decode(...);
```

可能形成：

```text
decode<Endian::Little>
decode<Endian::Big>
```

其中：

```text
Endian
```

已经从 runtime state 变成 program structure。

这可以：

```text
remove repeated branch
enable constant propagation
enable inlining
specialize algorithm
```

---

# 40. 但 Template Version 不一定比 Runtime Version 快

Runtime：

```cpp
decode(bytes, Endian::Little);
```

如果 optimizer 看得到：

```text
Endian::Little
```

是 constant，

也可能通过：

```text
inlining
constant propagation
branch elimination
```

生成和 template specialization 几乎一样的 machine code。

所以：

> **不能仅凭源码有 template 就推断性能更好。**

要看：

```text
assembly
benchmark
profile
```

---

# 41. Dynamic Outside, Static Inside

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

核心思想：

> **低频 dynamic decision 移出高频 hot path。**

---

# 42. Template Compilation Model

普通函数：

```cpp
// foo.hpp
int foo(int);

// foo.cpp
int foo(int x) {
    return x;
}
```

调用方编译时只需要 declaration。

最终由 linker 找 concrete definition。

---

Template：

```cpp
template <typename T>
T foo(T x);
```

调用：

```cpp
foo(42);
```

需要：

```text
foo<int>
```

compiler 要生成这个 concrete function，

通常就必须看到：

> Template definition body。

这就是为什么 template definitions 经常位于 header。

---

# 43. Header-only Template

```cpp
template <typename T>
T foo(T value) {
    ...
}
```

定义放 header。

好处：

```text
open genericity
consumer can instantiate required T
optimizer sees body
```

代价：

```text
more parsing
more instantiation
larger dependency surface
rebuild propagation
implementation exposure
```

---

# 44. Zero Runtime Overhead ≠ Zero Engineering Cost

Template 可能拥有非常优秀 runtime performance。

但是可能支付：

```text
compile time
binary size
debug symbol size
diagnostic complexity
dependency complexity
```

所以：

> **zero-overhead abstraction 主要描述 runtime cost model，不等于 template 是免费机制。**

---

# 45. Explicit Instantiation

如果只支持：

```text
int
float
double
```

可以在 `.cpp`：

```cpp
template int foo<int>(int);
template float foo<float>(float);
template double foo<double>(double);
```

明确让这个 translation unit 产生对应 specializations。

这样 generic code 从：

```text
open set of caller-selected T
```

更接近：

```text
controlled supported type set
```

可以改善：

```text
compile-time ownership
binary ownership
header exposure
```

---

# 46. Thin Template Front-end + Concrete Core

这是 G5 很重要的工程模式。

例如：

```cpp
template <typename T>
void process(std::span<const T> values) {
    process_bytes(std::as_bytes(values));
}
```

核心：

```cpp
void process_bytes(
    std::span<const std::byte> bytes);
```

结构：

```text
generic caller types
      ↓
thin type-dependent adapter
      ↓
common representation
      ↓
large non-template core
```

这样可以避免：

```text
500 lines heavy algorithm
× many template specializations
```

---

# 47. Where Should Genericity Stop?

这是 G5 最重要的架构问题。

假设：

```cpp
FixedBuffer<int, 16>
FixedBuffer<int, 32>
FixedBuffer<int, 64>
```

如果算法不关心 N，

不要机械写：

```cpp
template <std::size_t N>
void analyze(const FixedBuffer<int, N>&);
```

更合理的可能是：

```cpp
void analyze(std::span<const int>);
```

这样：

```text
storage detail N
```

在 algorithm boundary 被擦除。

---

# 48. 为什么这很好？

减少：

```text
algorithm<16>
algorithm<32>
algorithm<64>
```

这些几乎相同的 specializations。

同时获得：

```text
simpler API
less compile time
smaller binary
less coupling
```

所以：

> **不要让 compile-time variability 传播得比必要范围更远。**

---

# 49. Template vs Runtime Parameter

Runtime：

```cpp
decode(bytes, endian);
```

优点：

```text
one function
simple API
runtime flexibility
small code size
faster builds
```

Template：

```cpp
decode<Endian::Little>(bytes);
```

优点：

```text
static policy
compile-time structural specialization
more optimization knowledge
possibly no runtime branch
```

没有永远正确的一边。

---

# 50. 如何决定 Static / Dynamic Boundary

问四个问题：

## 1. 信息变化频率？

```text
每次 sample
→ runtime

程序启动后不再变化
→ specialization candidate
```

---

## 2. 它改变算法结构吗？

```text
endianness
→ may change operations

timestamp
→ ordinary data
```

---

## 3. Hot path 会不会重复检查它？

如果每秒数百万次重复同一 decision：

> 提前 bind/specialize 更有吸引力。

---

## 4. 会产生多少 Specializations？

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

---

# 51. Combinatorial Instantiation Explosion

例如：

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

参数组合可能爆炸。

你可能只是为了消除：

```text
一个 branch
几个 metadata loads
```

却换来了：

```text
huge build time
huge code
large debug information
complex diagnostics
```

所以：

> **compile-time 越多不等于越优秀。**

---

# 52. Template vs External Code Generation

二者都能：

```text
known metadata
↓
specialized executable structure
```

Template 更适合：

```text
small policy set
type-oriented variation
compile-time dimensions
generic reusable components
```

External codegen 更适合：

```text
DBC
IDL
schema
CSV
hundreds/thousands of definitions
large generated registries
```

语言无关核心：

> **稳定 metadata 可以从 runtime data 转化为 generated program structure。**

---

# 53. Genericity Budget

任何 template abstraction 都应该做一次成本核算。

## 收益

```text
static checking
compile-time specialization
inlining opportunities
generic reuse
type-level invariants
```

## 成本

```text
compile time
code size
dependency propagation
diagnostic complexity
API complexity
ABI/binary-boundary complexity
```

所以：

> **Genericity 是 architecture budget。**

---

# 54. G5 设计 Ladder

遇到一个问题，不要直接 template。

从最具体开始：

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

每向下一层增加能力，也增加复杂度。

选择：

> 能表达真实需求的最简单 abstraction。

---

# 55. Concrete Type vs `span` vs Template

假设算法只需要：

> 连续只读 samples。

可以：

```cpp
void process(
    const std::vector<Sample>& samples);
```

但暴露了 vector。

更窄：

```cpp
void process(
    std::span<const Sample> samples);
```

如果所有类型都能统一成这种 runtime view：

> 没必要 template。

只有当算法真正需要保留：

```text
different static types
different operations
different compile-time policies
```

时，template 才更自然。

---

# 56. Static Polymorphism vs Dynamic Polymorphism

## Virtual

```cpp
class Sensor {
public:
    virtual ~Sensor() = default;
    virtual float read() = 0;
};
```

：

```text
runtime type selection
virtual dispatch
heterogeneous collection easy
stable runtime interface
```

---

## Template

```cpp
template <typename T>
float read_sensor(T& sensor) {
    return sensor.read();
}
```

：

```text
concrete T known at compile time
static dispatch
inlining/specialization possible
more instantiations
```

不是：

> static 一定比 dynamic 好。

而是：

> boundary 的 variability 在 compile time 还是 runtime？

---

# 57. C++ / Zig / Rust 对照

## C++

```cpp
template <typename T, std::size_t N>
```

特点：

```text
template subsystem
deduction
specialization
reference collapsing
Concepts
constexpr
```

能力极强，但历史层次很多。

---

## Zig

```zig
fn foo(comptime T: type, comptime N: usize) type
```

倾向：

```text
compile-time execution integrated with normal language model
```

没有 C++：

```text
forwarding reference
reference collapsing
std::forward
```

整套机制。

---

## Rust

```rust
struct Buffer<T, const N: usize>
```

和：

```rust
fn foo<T: Trait>(...)
```

分别提供：

```text
generics
const generics
trait bounds
monomorphization
```

Rust ownership/reference model和 C++ 不同，因此无需复制 C++ forwarding machinery。

---

# 58. 三种语言共同的机器级事实

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

---

# 59. G5 Code Review Protocol

以后看到：

```cpp
template <typename T>
```

按下面检查。

### 1. 为什么需要 Generic？

普通 concrete API 不够吗？

### 2. 什么东西在变化？

```text
type?
layout?
algorithm?
policy?
```

### 3. 变化真的需要发生在 Compile Time 吗？

还是 runtime data 更合适？

### 4. 会有多少 Specializations？

### 5. 每个 Specialization 机器代码真的不同吗？

### 6. 是否在不必要地传播 Template Parameter？

### 7. 是否能在某层收敛成

```text
span
view
function pointer
ordinary function
```

？

### 8. 是否应该用 by-value sink，而不是 forwarding reference？

### 9. `std::move` 是否真的代表一次合理的 consumption boundary？

### 10. `std::forward` 是否真的位于 generic forwarding layer？

### 11. Template 定义是否必须全部暴露在 Header？

### 12. 实际性能收益是否被 benchmark / assembly 验证？

---

# 60. 高频 Anti-patterns

## Anti-pattern 1：Everything is Generic

```cpp
template <typename T>
void parse(T&& input);
```

实际上：

```cpp
void parse(std::span<const std::byte>);
```

已经足够。

---

## Anti-pattern 2：Cargo-cult Forwarding

```cpp
template <typename T>
void set_model(T&& model);
```

只因为：

> “perfect forwarding 最快”。

而实际上 API 就是：

```cpp
void set_model(Model model);
```

---

## Anti-pattern 3：Cargo-cult `std::move`

```cpp
consume(std::move(value));
```

却没搞清：

> source 之后是否还需要保持原 value。

---

## Anti-pattern 4：Template Every Runtime Constant

```text
Vehicle<123>
Message<456>
Request<789>
```

导致 type proliferation。

---

## Anti-pattern 5：Specialize Thousands of Equivalent Paths

为了一点微小 runtime branch 成本产生大量 machine code。

---

## Anti-pattern 6：Heavy Template Core

```cpp
template <typename T>
void process(...) {
    // 500 lines
}
```

而真正 type-dependent 部分只有几行。

考虑：

```text
thin template adapter
+
ordinary implementation core
```

---

## Anti-pattern 7：Compile-time Knowledge Leakage

底层只因为：

```text
N = 16
```

整个上层 call graph 都变成：

```text
template<N>
```

导致无意义 specialization 扩散。

---

# 61. G5 Final Mental Model

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

---

# 62. G5 最终术语表

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
| Perfect Forwarding          | 尽可能保持 caller cv/ref/value category 的转发       |
| `std::move`                 | 无条件将表达式转换为可消费的 xvalue                  |
| `std::forward`              | 根据模板参数恢复原始 value category                  |
| Concept                     | 对 template arguments 的命名 compile-time constraint |
| `constexpr`                 | 可参与 constant evaluation 的语言机制                |
| `consteval`                 | 要求 immediate compile-time evaluation               |
| `if constexpr`              | compile-time structural branching                    |
| Explicit Instantiation      | 显式要求生成特定 specialization                      |
| Header-only                 | 模板实现对 consumer TU 可见的常见组织方式            |
| Code Bloat                  | 多 specializations 导致的代码体积增长                |
| Static Polymorphism         | compile-time 根据 concrete type 生成/选择行为        |

---

# 63. G5 Final Gate

复习时至少能够闭卷解释这些问题：

### Template

1. Function template 和普通 function 最大的编译模型区别是什么？
2. 为什么一个 template 可以形成多个 concrete functions？
3. Instantiation 和 specialization 分别是什么？

### Deduction

1. `T`、`T&`、`const T&` 的 deduction 有什么区别？
2. top-level `const` 为什么在 by-value deduction 中通常消失？
3. 为什么 pointer-to-const 中的 const 不能随意消失？

### Forwarding

1. 普通 `Frame&&` 与 `template<typename T> T&&` 有什么不同？
2. 什么条件下 `T&&` 才是 forwarding reference？
3. Reference collapsing 是什么？
4. 为什么 named `T&&` expression 仍然是 lvalue？
5. `std::move` 和 `std::forward` 的语义区别是什么？

### Class Templates

 1. 为什么 `Buffer<float,16>` 与 `Buffer<float,32>` 是不同类型？
 2. Non-type template parameter 如何影响 object layout？
 3. 为什么不应该把普通 runtime identity 全部变成 NTTP？

### Lifetime

 1. 为什么 `array<T,N>` 与 `vector<T>::reserve(N)` 的 object lifetime 完全不同？

### Concepts

 1. Concept 解决什么问题？
 2. Concept 是 runtime interface 吗？
 3. 为什么 Concept 不能保证 semantic laws？

### Constant Evaluation

 1. 为什么 `constexpr function` 不等于“永远编译期执行”？
 2. `const` 和 `constexpr` 有什么根本区别？
 3. `if constexpr` 与普通 `if` 的核心区别是什么？

### Compilation

 1. 为什么 template definitions 通常放 header？
 2. Explicit instantiation 解决什么问题？
 3. Header-only generic library 的主要工程成本是什么？

### Architecture

 1. 什么叫 `Dynamic Outside, Static Inside`？
 2. 哪些信息适合 compile time，哪些更适合 runtime？
 3. 为什么 template specialization 不一定比 runtime parameter 快？
 4. 什么情况下应该用 external codegen 而不是 template？
 5. 为什么要限制 genericity 的传播范围？
 6. Thin template front-end + concrete core 有什么价值？

---

# 64. 如果半年后只记住十五条

1. **Template 是 compile-time parameterization，不是 runtime dynamic genericity。**

2. **Template 会根据 arguments 形成 concrete functions/types。**

3. **始终分开 deduced `T`、最终 parameter type 和 expression value category。**

4. **By-value deduction 通常丢弃 top-level cv；reference deduction必须保留合法 alias 所需的信息。**

5. **Forwarding reference 是 deduction context 中特殊的 `T&&`，不是所有 `T&&`。**

6. **Named rvalue-reference variable 仍然产生 lvalue expression。**

7. **`std::move` 表示当前代码允许消费 source；`std::forward` 表示 generic wrapper 保留 caller 的决定。**

8. **Class template arguments 可以进入类型和 layout；`Buffer<T,16>` 与 `Buffer<T,32>` 是不同类型。**

9. **`std::array<T,N>` 包含 N 个 live T objects；reserve 只提供 storage capacity。**

10. **Concept 是 compile-time generic contract，不是 runtime interface。**

11. **`constexpr` 表示 constant-evaluation 能力；`if constexpr` 表示 compile-time structural selection。**

12. **Template definitions 通常需要在 instantiation point 可见，因此直接影响 header/TU/build architecture。**

13. **Static specialization 可以减少 runtime work，但会增加 compile-time/code-size complexity。**

14. **不要让 compile-time variability 比真正需要的范围传播得更远。**

15. **优秀 Generic Programming 的标志不是 template 多，而是清楚知道 genericity 应该在哪里停止。**

---

# 65. G5 → G6

G5 到此可以正式冻结。

我们已经学会从：

```text
source abstraction
```

一路追到：

```text
concrete type/function
↓
compiler
↓
machine code
```

G6 会换一个视角：

> **即使 C++ abstraction 在语言层完全正确，它落到 CPU 和 memory hierarchy 上到底贵不贵？**

下一阶段：

```text
G6 Memory & Performance
│
├── sizeof / alignment / padding
├── object layout
├── cache line
├── spatial / temporal locality
├── AoS / SoA
├── indirection
├── allocation cost
├── arena / pool
├── working set
├── branch behavior
├── false sharing
└── profiling / measurement
```

G1–G5 到这里实际上已经组成了一个完整前半程：

```text
G1  Object 是否合法存在？
G2  谁拥有它？
G3  Value 怎样流动、成本多少？
G5  哪些差异应该在编译期生成？

                    ↓

G6
这些选择最终如何作用到 CPU / Cache / Memory？
```

**这份文档可以作为 G5 的长期 Frozen Review Baseline。**下一步进入 G6 时，我们会重新明显偏向底层、实验和机器直觉，而不是继续增加 template 语法。
