# C++ Systems Track · G3 Value Semantics & Performance

- **Version:** 1.0 · Frozen Review Baseline
- **Prerequisite:** G1 Object Model & Lifetime, G2 RAII & Ownership Architecture
- **Language Baseline:** C++23
- **Comparison Languages:** Zig / Rust
- **Scope:** Value Semantics / Copy / Move / Copy Elision / RVO / NRVO / Parameter Passing / Container Relocation / SSO / SBO / Representation / Performance Architecture
- **Purpose:** 作为进入 G4 STL & Abstraction 前的长期 C++ Value / Cost Model 复习与 Code Review 基线

---

# Part 0 · G3 的根本问题

G1：

> **这个 access 合法吗？**

G2：

> **谁负责让 object/resource 活够久？**

G3：

> **为了让 value 在程序里流动，我们到底支付了什么？**

统一：

```text
                    C++ SYSTEM VALUE

             ┌──────────┼──────────┐
             │          │          │
          G1 Validity  G2 Lifetime G3 Cost
             │          │          │
             ▼          ▼          ▼
         Can access?  Who owns?  What moves?
```

G3 研究的不是：

> “`std::move` 怎么写。”

而是：

> **Logical value 如何映射到底层 storage/resource representation，以及 copy、move、return、parameter passing、container relocation 对这个 representation 产生什么机器成本。**

---

# Part 1 · Logical Value 与 Representation

## 1.1 第一个问题永远是：这个 Type 的 Logical Value 是什么？

例如：

### `std::vector<int>`

Representation 近似：

```text
pointer
size
capacity
```

Logical value：

```text
sequence of ints
```

---

### `std::span<int>`

Representation 通常近似：

```text
pointer
size
```

Logical value：

```text
bounded view over contiguous ints
```

---

### `std::unique_ptr<T>`

Representation：

```text
pointer
possibly deleter
```

Logical value：

```text
empty
or
unique ownership of resource
```

---

### `std::shared_ptr<T>`

Logical value包含：

```text
stored pointer
+
shared ownership stake
```

它的 logical value不是：

> pointee本身。

---

## 1.2 Representation ≠ Logical Value

必须长期保持：

```text
Object Representation
≠
Logical Value
```

例如：

```cpp
std::vector<float> values(1'000'000);
```

vector object本体可能只有：

```text
~几个 machine words
```

但 logical value：

```text
1,000,000 floats
```

所以：

```cpp
auto copy = values;
```

成本取决于：

> logical sequence。

不是：

```cpp
sizeof(std::vector<float>)
```

---

# Part 2 · Value Semantics

## 2.1 Value Semantics 的核心

```cpp
T b = a;
```

若 T 是 copyable value-like type，通常希望：

> `b` 表示和 `a` 等价的 logical value，并成为一个新的 object。

但“等价 logical value”并不意味着：

> same object / same storage。

例如：

```cpp
std::string a{"hello"};
std::string b = a;
```

通常：

```text
a == b
```

但：

```text
a object identity
≠
b object identity
```

---

## 2.2 Value Semantics ≠ Bitwise Copy

错误：

```text
value semantics
=
memcpy(sizeof(T))
```

正确：

> copy operation 必须保持 type 的 semantic contract。

可能实现为：

```text
scalar copy
memberwise copy
allocation + deep copy
reference-count update
view metadata copy
```

取决于 logical value。

---

## 2.3 Value Semantics ≠ Deep Copy

`std::span<T>`：

```cpp
auto b = a;
```

复制的是：

```text
view value
```

不是：

```text
backing elements
```

所以两个 span会 alias同一段 data。

这不违反 span自己的 value semantics，因为：

> span 的 logical value 本来就是一个 view。

---

## 2.4 Shared Owner Copy 也是 Value Operation

```cpp
auto a = std::make_shared<Model>();
auto b = a;
```

复制：

```text
shared ownership handle
```

而不是：

```text
Model logical value
```

因此：

```text
a
b
```

是两个独立 `shared_ptr` objects，却共同参与同一个 Model lifetime。

---

## 2.5 Move-only 也可以是 Value Abstraction

例如：

```text
unique_ptr<T>
FrameLease
FileDescriptor
```

它们都有明确 state：

```text
empty
or
owns some resource/right
```

只是：

```text
copy
→ semantic illegal

move
→ state transfer
```

所以：

> **Value abstraction 不等于 copyable。**

---

# Part 3 · Copy Cost Model

## 3.1 同一语法可以是完全不同成本

```cpp
T b = a;
```

可能是：

```text
int
→ few scalar operations

std::array<int, 1024>
→ copy 1024 ints

std::vector<int>
→ allocation + copy N elements

std::span<int>
→ copy pointer + extent

shared_ptr<T>
→ copy handle + refcount bookkeeping
```

因此：

> **Syntax does not reveal cost. Type semantics do.**

---

## 3.2 Copy Cost ≠ `sizeof(T)`

对于 inline type：

```text
copy cost
往往和 sizeof(T) 有较强关系
```

例如：

```cpp
std::array<float, 1024>
```

但 indirect owner：

```cpp
std::vector<float>
```

则：

```text
sizeof(vector)
很小

logical payload
可能很大
```

所以：

> `sizeof(T)` 只说明 object representation size。

---

## 3.3 Inline vs Indirect

### Inline

```text
object
┌────────────────────┐
│ payload itself     │
└────────────────────┘
```

例如：

```text
int
Vec3
std::array<T,N>
```

Copy：

```text
copy inline state
```

---

### Indirect

```text
object
┌─────────┐
│ ptr ────┼────▶ payload
│ size    │
└─────────┘
```

例如：

```text
vector
heap-owning buffer
```

Copy：

```text
allocate new payload
+
copy logical payload
```

---

## 3.4 Recursive Cost Composition

如果：

```cpp
struct RobotState {
    std::string name;
    std::vector<float> joints;
    Pose pose;
};
```

则：

```text
CopyCost(RobotState)
≈
CopyCost(string)
+
CopyCost(vector<float>)
+
CopyCost(Pose)
```

更一般：

```text
C(T)
≈ Σ C(member_i)
```

Container：

```text
C(vector<T>)
≈ allocation + N × C(T)
```

```text
C(array<T,N>)
≈ N × C(T)
```

---

## 3.5 Copy Construction 与 Copy Assignment 不同

Copy construction：

```cpp
T b = a;
```

destination没有旧 state。

Copy assignment：

```cpp
b = a;
```

destination已有 state。

因此 assignment必须处理：

```text
old storage
old resource
capacity
allocator
existing elements
```

所以 copy assignment成本可能：

> 依赖 destination当前 state。

---

## 3.6 O(1) ≠ Cheap

例如：

```text
raw pointer copy
shared_ptr copy
large fixed-size struct copy
```

都可能被粗略称为 O(1)。

但：

```text
register move
vs
atomic refcount
vs
64/128 bytes memory traffic
```

差别巨大。

因此性能描述至少要包含：

```text
asymptotic complexity
constant factor
bytes moved
allocation count
synchronization
cache behavior
```

---

# Part 4 · Triviality

## 4.1 Trivial Copy

例如：

```cpp
struct Sample {
    std::uint64_t timestamp;
    float value;
    std::uint32_t signal_id;
};
```

可以检查：

```cpp
static_assert(std::is_trivially_copyable_v<Sample>);
```

这种类型非常适合：

```text
dense arrays
bulk data movement
telemetry
sensor samples
```

---

## 4.2 `trivially copyable` 不等于 Wire Format

仍然要考虑：

```text
endianness
padding
ABI
alignment
schema version
floating representation
```

所以：

```cpp
send(fd, &sample, sizeof(sample), ...);
```

不自动成为正确跨系统 serialization。

---

# Part 5 · Move Semantics

## 5.1 Copy 与 Move 的根本区别

Copy：

```cpp
T b = a;
```

要求：

```text
a logical value preserved
b obtains equivalent logical value
```

Move：

```cpp
T b = std::move(a);
```

允许：

```text
a logical state changes
b reuses/transfers a's existing state/resource
```

所以 move 的性能潜力来自：

> **Source value no longer needs to be preserved.**

---

## 5.2 `std::move` 不移动

`std::move(x)`：

> 将 expression转换为 xvalue。

概念近似：

```cpp
static_cast<T&&>(x)
```

真正 state/resource transfer发生在：

```text
move constructor
move assignment
consumer operation
```

所以：

```text
std::move
= permission / cast

move operation
= actual transition
```

---

## 5.3 Why Vector Move Is Often Cheap

vector representation：

```text
pointer
size
capacity
```

payload：

```text
external allocation
```

Move construction可：

```text
transfer pointer/size/capacity
↓
source becomes valid moved-from state
```

因此通常：

```text
Copy: O(N)
Move: O(1)
```

---

## 5.4 为什么 Array Move 仍可能 O(N)

```cpp
std::array<T, N>
```

elements inline。

没有：

```text
allocation handle
```

可以直接 transfer。

所以：

```text
move array
≈ move N elements
```

对于 scalar T：

```text
move ≈ copy
```

因此：

> **Move syntax does not imply O(1).**

---

## 5.5 Move Cost 来自 Representation

```text
Indirect owner
→ transfer handle
→ often cheap

Inline payload
→ transfer payload itself
→ often similar to copy
```

---

## 5.6 Moved-from ≠ Dead

```cpp
T b = std::move(a);
```

之后：

```text
a lifetime still active
```

a仍然需要：

```text
safe destruction
safe assignment
```

以及其 type contract明确允许的其它操作。

一般：

> valid but unspecified。

某些 type给更强保证。

例如：

```cpp
unique_ptr
```

move后 source为空。

---

## 5.7 `const` 与 Move

```cpp
const T value;
T copy = std::move(value);
```

`std::move(value)`产生：

```text
const T&&
```

而普通 move constructor：

```cpp
T(T&&)
```

通常无法接受 const source。

因为 move经常需要：

> 修改 source state。

所以经常回退：

```text
copy via const T&
```

必须记：

> **`std::move(const T)` 经常不会真正 move。**

---

# Part 6 · `noexcept` Move

## 6.1 `noexcept` 不只是 Optimization Hint

```cpp
T(T&&) noexcept;
```

表达：

> move不会让 exception逃出。

这会直接影响：

```text
generic algorithms
containers
vector relocation
```

---

## 6.2 为什么 Vector 会关心？

reallocation：

```text
allocate new storage
↓
construct old elements in new storage
```

若 move：

```text
可能修改 source
并可能 throw
```

做到一半失败：

> rollback困难。

若 copy：

```text
source unchanged
```

新 storage失败：

> 可以直接丢弃 partial copies。

所以：

```text
noexcept move
```

通常让 container更安全地选择 cheap move path。

---

## 6.3 Move-only + Throwing Move

这是非常棘手组合：

```text
copy impossible
move may throw
```

container不能 fallback copy。

因此对 resource owner：

```text
move-only
O(1)
noexcept
simple empty state
```

是很好的设计目标。

---

# Part 7 · Copy Elision / RVO / NRVO

## 7.1 最好的 Move 是没有 Move

现代性能层级经常是：

```text
Copy
↓
Move
↓
Direct Construction / Elision
```

---

## 7.2 C++17+ Same-type Prvalue

```cpp
T make() {
    return T{};
}
```

现代模型：

```text
result object
↓
T constructed directly there
```

不是：

```text
temporary T
↓ move
result T
```

因此：

> move constructor甚至可以不存在。

---

## 7.3 Guaranteed Case

```cpp
class Immovable {
public:
    Immovable() = default;
    Immovable(const Immovable&) = delete;
    Immovable(Immovable&&) = delete;
};

Immovable make() {
    return Immovable{};
}
```

C++17+ 可以成立。

这证明：

> guaranteed copy elision不是“更快的 move”。

---

## 7.4 NRVO

```cpp
T make() {
    T value;
    return value;
}
```

`value` 是 named local。

这是：

> Named Return Value Optimization。

NRVO成功：

```text
local value
和
function result
实际上对应同一个最终 object
```

---

## 7.5 Guaranteed Prvalue Case ≠ NRVO

必须区分：

```cpp
return T{};
```

和：

```cpp
T value;
return value;
```

前者 C++17+ same-type result construction有更强语义保证。

后者：

> NRVO仍是 permitted/expected，但不是同等级 guaranteed case。

---

## 7.6 NRVO Failure → Implicit Move

```cpp
T make() {
    T value;
    return value;
}
```

如果 NRVO不发生，eligible local可走：

```text
implicit move
```

所以通常不需要：

```cpp
return std::move(value);
```

---

## 7.7 `return std::move(local)` 是典型 Smell

```cpp
T make() {
    T value;
    return std::move(value);
}
```

`std::move(value)` 是 xvalue。

通常：

> 不再保持简单 NRVO candidate形式。

因此可能从：

```text
0 transfers
```

退化成：

```text
1 move
```

所以 ordinary local return默认：

```cpp
return value;
```

---

# Part 8 · Return-by-Value Cost Model

看到：

```cpp
T result = make_t();
```

不要问：

> “复制几次？”

而应该拆成：

```text
1. ConstructCost(T)
2. Result placement
3. Transfer cost
4. Dynamic resource work
5. ABI lowering
```

现代理想：

```text
TransferCost = 0
```

但：

```text
construct payload
allocate
I/O
decode
```

这些真实工作不会因为 elision消失。

---

# Part 9 · Parameter Passing

## 9.1 参数类型首先是 Semantic Contract

不是：

```text
哪个写法最快？
```

而是：

```text
callee要：
borrow?
own?
consume?
mutate?
view?
share?
```

---

## 9.2 `T`

```cpp
void f(T value);
```

表示：

> callee获得自己的 T value。

caller lvalue：

```text
copy
```

caller rvalue/xvalue：

```text
move
```

same-type prvalue：

```text
direct parameter construction可能消除不必要 transfer
```

---

## 9.3 `const T&`

```cpp
void f(const T& value);
```

表示：

> required read-only borrow。

适合：

```text
large expensive-to-copy value
callee只同步读取
```

---

## 9.4 `T&`

```cpp
void f(T& value);
```

表示：

> required mutable borrow。

函数修改：

> caller-visible object。

---

## 9.5 `T&&`

非模板：

```cpp
void consume(T&& value);
```

表示：

> rvalue reference to a consumable object。

但：

> reference本身不是 ownership transfer。

真正 transfer通常发生在：

```cpp
store(std::move(value));
```

---

## 9.6 Named `T&&` 仍然是 Lvalue Expression

```cpp
void consume(T&& value) {
    sink(value);             // lvalue
    sink(std::move(value));  // xvalue
}
```

类型：

```text
T&&
```

与表达式 category：

```text
lvalue
```

必须分开。

---

# Part 10 · Sink Parameters

如果函数最终需要：

> 保存自己的 value。

典型：

```cpp
class Robot {
public:
    explicit Robot(std::string name)
        : name_(std::move(name)) {}

private:
    std::string name_;
};
```

这里：

```text
T by value
+
move into member
```

常适合：

```text
copy expensive
move cheap
```

的 type。

例如：

```text
string
vector
Frame
```

---

## 10.1 Lvalue Caller

```text
copy into parameter
+
cheap move into member
```

---

## 10.2 Rvalue Caller

```text
move/direct construct parameter
+
cheap move into member
```

所以：

> by-value sink 是 API simplicity 与性能之间很好的折中。

---

# Part 11 · Small Values

例如：

```cpp
struct RobotId {
    std::uint64_t value{};
};
```

通常：

```cpp
Robot* find_robot(RobotId id);
```

优于：

```cpp
Robot* find_robot(const RobotId& id);
```

原因：

```text
small
cheap copy
register-friendly
no aliasing relation
no lifetime dependency
```

---

## 11.1 Strong Small Types

包装：

```text
uint64_t → RobotId
int64_t → Timestamp
```

通常不产生有意义性能损失。

却带来：

```text
type safety
API clarity
semantic distinction
```

这是典型 zero-overhead abstraction。

---

# Part 12 · Views

## 12.1 `std::span<T>`

```cpp
void process(std::span<const Sample> samples);
```

表达：

```text
non-owning
contiguous
bounded
read-only sequence view
```

它不要求 caller是：

```text
vector
```

所以 API表达的是：

> data shape

而不是：

> owner/container representation。

---

## 12.2 为什么 Span By Value

span本身通常只是：

```text
pointer
+
extent
```

cheap to copy。

所以：

```cpp
void process(std::span<const T> values);
```

而不是：

```cpp
void process(const std::span<const T>& values);
```

---

## 12.3 `std::string_view`

同样：

```cpp
void parse(std::string_view text);
```

适合：

> character-sequence borrow。

但如果函数/class需要长期保存：

> string_view并不拥有 characters。

需要重新做 ownership decision。

---

# Part 13 · Borrow vs Ownership Boundary

同步：

```cpp
void inspect(const Frame& frame);
```

owner在 caller，borrow只覆盖 call。

异步：

```cpp
submit(...)
```

调用返回后 task继续运行。

因此：

> **Async boundary often becomes ownership boundary。**

不能把：

```cpp
const Frame&
span
T*
```

随便保存进 async callback。

必须选择：

```text
copy
move
shared ownership
lease
```

之一。

---

# Part 14 · Aliasing 与 Parameter Performance

Reference：

```cpp
void f(const Vec3& a, const Vec3& b);
```

允许潜在：

```text
a and b alias
```

Value：

```cpp
void f(Vec3 a, Vec3 b);
```

parameters是独立 local values。

对 small scalar/aggregate，by value可能：

```text
更容易 registerize
减少 aliasing constraints
减少 lifetime relationships
```

所以：

> reference不只是“省 copy”。

它也改变 optimizer的 memory model。

---

# Part 15 · Container Relocation

## 15.1 `size` vs `capacity`

```text
size
=
live T object count

capacity
=
storage capacity for up to N T objects
```

所以：

```cpp
values.reserve(100);
```

不是：

> 构造100个 T。

而是：

> 확보 storage。

---

## 15.2 Reallocation

capacity不足：

```text
old storage
[T][T][T][T]

↓ allocate bigger storage

new raw storage

↓ construct new T objects from old values

↓ destroy old T objects

↓ deallocate old storage
```

重点：

> **这是 object lifetime migration，不只是 bytes copy。**

---

## 15.3 Move Constructor ≠ Object Teleportation

```cpp
T b = std::move(a);
```

是：

```text
new T object b begins lifetime
a remains alive
```

不是：

> 同一个 object直接改地址。

所以：

```text
Move
≠
Relocation
```

---

## 15.4 Reallocation Invalidation

old element lifetimes结束。

所以：

```text
T*
T&
iterator
```

若指向旧 vector elements：

> reallocation后失效。

pointer object自己并没改变。

是：

> backing object relationship失效。

---

# Part 16 · `reserve()`

`reserve()` 价值不仅是：

```text
reduce allocations
```

还可以：

```text
reduce element moves/copies
reduce address invalidation
move latency out of hot path
improve tail-latency predictability
```

但：

```cpp
values.reserve(n);
```

本身如果 capacity不足，也会：

> reallocate并立即invalidate旧 element references。

---

# Part 17 · Amortized Complexity

vector几何增长使：

```text
push_back
→ amortized O(1)
```

但单次 expansion：

```text
O(N)
```

所以：

> amortized O(1) ≠ every operation O(1)。

对于 realtime：

```text
average latency
```

可能不重要。

更关心：

```text
worst-case / bounded latency
```

因此：

```text
reserve
fixed-capacity storage
ring buffer
pool
```

经常重要。

---

# Part 18 · `vector<T>` vs `vector<unique_ptr<T>>`

## Dense Value Storage

```cpp
std::vector<Detection>
```

布局：

```text
[D][D][D][D]
```

优点：

```text
contiguous
few allocations
prefetch-friendly
cache-friendly
```

缺点：

```text
element addresses can change on reallocation
```

---

## Pointerized Storage

```cpp
std::vector<std::unique_ptr<Detection>>
```

布局：

```text
[p][p][p][p]
 │  │  │  │
 ▼  ▼  ▼  ▼
 D  D  D  D
```

优点：

```text
pointee address stable across outer vector growth
dynamic polymorphism friendly
```

代价：

```text
N allocations
N indirections
fragmentation
poor locality
```

因此：

> 不要仅为地址稳定就 pointerize small value types。

---

# Part 19 · Stable ID vs Stable Address

如果 domain identity是：

```cpp
TrackId{42}
```

那么 Track object storage可以：

```text
move
compact
reallocate
```

只要 TrackId不变。

因此：

> **Address is a storage property, not necessarily domain identity。**

许多系统更适合：

```text
stable ID
+
central owner
```

而不是：

```text
heap everything to get stable addresses
```

---

# Part 20 · Representation Strategies

## Inline

```text
payload inside object
```

例如：

```text
int
Vec3
array<T,N>
```

优点：

```text
no allocation
good locality
simple lifetime
```

缺点：

```text
object large
move may be same as copy
```

---

## Indirect

```text
small wrapper
→ external payload
```

例如：

```text
vector
PImpl
heap buffer
```

优点：

```text
small object
stable payload address possible
cheap move
```

代价：

```text
allocation
indirection
cache miss
```

---

## Hybrid

```text
small runtime value
→ inline

large runtime value
→ indirect
```

例如常见：

```text
std::string SSO
small-function/SBO wrappers
small-vector abstractions
```

---

# Part 21 · SSO / SBO

## 21.1 Small String Optimization

常见 std::string实现：

```text
short string
→ characters inline

long string
→ heap storage
```

因此：

```text
short copy
→ maybe no allocation

long copy
→ allocation + O(N)

short move
→ small inline transfer

long move
→ handle transfer
```

---

## 21.2 SSO Threshold 不是 Portable Guarantee

不要依赖：

```text
<= 15 / 22 / 23 chars
```

这种具体值。

它属于：

```text
stdlib implementation
ABI
toolchain
```

---

## 21.3 SBO Trade-off

```text
larger wrapper
↕
fewer small-object allocations
```

如果 inline buffer太大：

```text
cache density ↓
vector relocation bytes ↑
object footprint ↑
ABI constraints ↑
```

所以：

> SBO不是越大越好。

---

# Part 22 · Performance Cliff

Hybrid representation存在 threshold：

```text
size <= N
→ inline

size > N
→ heap
```

因此 runtime cost可能：

```text
N
→ no allocation

N+1
→ allocation + migration
```

产生：

> performance cliff。

所以 benchmark不能只测：

```text
one tiny string
```

应看真实：

```text
value-size distribution
histogram
percentiles
```

---

# Part 23 · `optional<T>`

`std::optional<T>` 概念：

```text
storage for T
+
engaged state
```

empty：

```text
T storage exists
T lifetime inactive
```

engaged：

```text
T object lifetime active
```

再次体现：

> Storage exists ≠ object alive。

---

## 23.1 `optional<Large>` Empty 仍可能很大

因为 wrapper必须：

> 随时能够 inline容纳一个 Large。

所以：

```text
empty optional
≠
pointer-sized
```

大量 sparse large optionals可能并不适合 inline representation。

---

# Part 24 · `variant`

```cpp
std::variant<A, B, C>
```

需要：

```text
storage for largest alternative
+
active tag
```

因此 size通常主要由：

```text
max(sizeof(A), sizeof(B), sizeof(C))
```

决定。

运行时 operation cost：

> 取决于当前 active alternative。

所以：

```text
same static type
different runtime state
different operation cost
```

---

# Part 25 · Value-oriented Architecture

高性能 C++ 不等于：

```text
everything inline
everything by value
```

真正目标：

```text
small metadata
→ value

large unique payload
→ movable owner

synchronous algorithm input
→ borrow/view

independent immutable generations
→ narrow shared ownership

pooled resource
→ lease

hot collections
→ dense value containers

identity
→ stable ID when possible
```

---

# Part 26 · Large Logical Value 可以仍然是 Small Movable Object

例如：

```cpp
struct InferenceRequest {
    RequestId id;
    Timestamp timestamp;
    std::shared_ptr<const Model> model;
    FrameLease frame;
};
```

它代表：

```text
large model
large frame
```

但 object representation可能只有：

```text
small values + small handles
```

Move：

```text
RequestId
→ cheap

Timestamp
→ cheap

shared_ptr
→ handle transfer

FrameLease
→ lease transfer
```

所以：

> **Logical payload size ≠ object size ≠ move cost。**

---

# Part 27 · Copy as Decoupling

Copy 不只是：

> data movement。

它还可以购买：

```text
lifetime independence
thread independence
storage abstraction
generation independence
```

例如 small metadata：

```cpp
FrameMetadata metadata = frame.metadata();
```

几十 bytes copy。

换：

> Detection result 不再依赖 Frame lifetime。

这可能是优秀 trade-off。

---

# Part 28 · Zero-copy

Zero-copy通常真正表示：

> 避免主要 large payload duplication。

仍会复制：

```text
metadata
pointer
size
lease
handle
```

所以：

> Zero-copy ≠ zero data movement。

---

## 28.1 Zero-copy 的代价

```text
less memory bandwidth
↓
more lifetime coupling
aliasing
reuse coordination
possibly synchronization
```

必须记：

> **Zero-copy turns bandwidth cost into coordination cost.**

---

## 28.2 Shared Immutable Data

如果多个 consumers共享大 payload，最好：

```text
shared
+
immutable
```

这样主要解决：

```text
lifetime
```

而不是额外解决：

```text
data race
synchronization
consistency
```

---

# Part 29 · Pool + Lease

Pool：

```text
owns backing storage
```

Lease：

```text
owns temporary usage right
```

不是：

```text
lease owns allocation
```

cleanup：

```text
last/use lease ends
→ return slot to pool
```

而不是：

```text
delete buffer
```

---

## 29.1 Pool Stale View

Pool reuse时：

```text
same memory address
new generation
```

旧 span/pointer可能：

```text
address still mapped
but logical data generation changed
```

因此：

> address-valid ≠ lifetime-valid ≠ generation-valid。

ASan也未必能发现。

---

# Part 30 · Cost Graph

高性能代码不要只画 Ownership Graph。

还应该画：

## Value/Copy/Move Graph

```text
where values are:
copied
moved
directly constructed
borrowed
```

---

## Allocation Graph

```text
startup allocations
per-frame allocations
per-item allocations
control blocks
temporary storage
```

---

## Indirection Graph

```text
object
↓
pointer
↓
object
↓
PImpl
↓
payload
```

每个 pointer可能增加：

> cache-miss risk。

---

## Lifetime/Invalidation Graph

```text
who borrows?
what invalidates?
reallocation?
erase?
pool reuse?
generation replacement?
shutdown?
```

---

# Part 31 · Performance Cost Axes

完整 cost model：

```text
1. Bytes moved
2. Allocation count
3. Deallocation count
4. Object construction/destruction
5. Element copy/move
6. Atomic/refcount operations
7. Locks
8. Pointer indirections
9. Cache footprint
10. Reallocation
11. Invalidation
12. Lifetime coordination
13. Tail latency
14. ABI/layout constraints
```

所以：

> **Big-O is necessary but not sufficient。**

---

# Part 32 · Copy Cost Equation

工程近似：

```text
CopyCost(T)
≈
InlineBytesMoved
+
Allocations
+
OwnedPayloadCopy
+
Σ MemberCopyCost
+
Synchronization
+
Cache/MemoryTraffic
+
RepresentationTransition
```

Move：

```text
MoveCost(T)
≈
StateTransfer
+
DestinationOldStateCleanup
+
Σ MemberMoves
+
AllocatorConstraints
+
InvariantRepair
+
Synchronization
```

---

# Part 33 · Parameter Decision Model

先问语义：

```text
Does callee:
borrow?
own?
mutate?
consume?
view?
share?
```

然后才问性能。

默认：

| 语义                                 | C++ 首选起点         |
| ------------------------------------ | -------------------- |
| small independent value              | `T`                  |
| callee needs own value               | `T`                  |
| large read-only borrow               | `const T&`           |
| required mutable borrow              | `T&`                 |
| optional observer                    | `T*`                 |
| contiguous sequence borrow           | `std::span<T>`       |
| text borrow                          | `std::string_view`   |
| unique owner transfer                | `std::unique_ptr<T>` |
| shared lifetime acquisition          | `std::shared_ptr<T>` |
| move-only lease/value transfer       | `T`                  |
| explicit consume-only existing value | sometimes `T&&`      |

---

# Part 34 · Container Review Model

看到：

```cpp
std::vector<T>
```

问：

```text
T copy cost?
T move cost?
T move noexcept?
T address-sensitive?
T value-like?
stable address required?
growth frequency?
reserve possible?
what borrows elements?
what invalidates them?
```

Container performance：

> 是 element semantics 与 storage topology 的组合。

---

# Part 35 · Healthy High-performance Pipeline

典型：

```text
Small control/meta values
        ↓
       T

Large unique payload
        ↓
cheap movable owner / lease

Synchronous stage access
        ↓
span / const& / T&

Independent large immutable generation
        ↓
shared_ptr<const T>

Long-lived identity
        ↓
stable logical ID

Hot collections
        ↓
dense contiguous values
```

---

# Part 36 · C++ vs Zig

## C++

```text
copy/move/destructor
→ heavily encoded in type operations

value syntax
→ can hide expensive semantic work

RVO/NRVO/elision
→ powerful destination construction
```

---

## Zig

```text
ordinary value operations simpler
clone/resource duplication generally explicit
allocator commonly explicit
result-location semantics
```

所以：

```text
C++
more semantic machinery behind ordinary syntax

Zig
more operational cost visible in APIs/control flow
```

---

# Part 37 · C++ vs Rust

Rust：

```text
non-Copy T assignment
→ ownership move

source usually becomes statically unusable
```

C++：

```text
lvalue
→ copy if copyable

std::move(x)
→ explicitly expose xvalue
source remains live moved-from object
```

Rust静态保证更多 lifetime规则。

但：

```text
cache
layout
allocation
Vec relocation
Arc refcount
AoS/SoA
```

仍然必须由工程师设计。

---

# Part 38 · G3 Code Review Protocol

对 performance-sensitive code：

## Step 1 — Identify Logical Values

这个 type 到底表示什么？

---

## Step 2 — Classify Representation

```text
inline
indirect
hybrid
```

---

## Step 3 — Locate Large Payloads

```text
vectors
buffers
images
matrices
strings
models
```

---

## Step 4 — Mark Every Copy

判断：

```text
small value copy?
deep payload copy?
view copy?
shared ownership copy?
```

---

## Step 5 — Mark Every Move

问：

```text
who consumes?
what is transferred?
cheap?
O(1)?
noexcept?
```

---

## Step 6 — Review Returns

```cpp
return T{};
return local;
return std::move(local);
```

明确：

```text
guaranteed direct construction
NRVO
pessimizing move
```

---

## Step 7 — Review Parameters

确认接口真正表达：

```text
borrow
own
consume
view
share
```

---

## Step 8 — Review Containers

问：

```text
why this container?
why pointerized?
why not dense values?
reserve?
invalidation?
```

---

## Step 9 — Count Allocations

特别查：

```text
per item
per request
per frame
per callback
```

---

## Step 10 — Count Indirections

每一层 pointer都问：

> why?

---

## Step 11 — Review Lifetime of Views

```text
span
string_view
reference
pointer
iterator
```

谁 backing？

何时 invalid？

---

## Step 12 — Measure

使用：

```text
benchmark
allocation counters
profilers
assembly
hardware counters
```

验证 hot path。

---

# Part 39 · G3 高频 Smells

### 1

```cpp
return std::move(local);
```

普通 local return：

> NRVO pessimation smell。

---

### 2

```cpp
std::vector<std::unique_ptr<SmallValue>>
```

没有 polymorphism/stable address原因：

> pointerization smell。

---

### 3

```cpp
const TinyStruct&
```

机械 const-ref：

> cargo-cult borrow。

---

### 4

```cpp
std::shared_ptr<T>
```

只因为 many users：

> ownership uncertainty。

---

### 5

```cpp
const std::vector<T>&
```

函数实际只需要：

```text
contiguous sequence
```

考虑 span。

---

### 6

保存：

```text
span
string_view
T*
T&
```

却没有 backing lifetime contract。

---

### 7

为了“zero-copy”：

```text
shared_ptr everything
```

可能将简单 memory copy换成更昂贵 lifetime/refcount/cache成本。

---

### 8

已知 batch size，但 hot path vector不 reserve。

---

### 9

为了 stable address而 heap allocate所有 small objects。

---

### 10

使用 copy/move constructor side effects承担业务 correctness。

Elision可能让这些 operations根本不发生。

---

# Part 40 · G3 Core Terminology

| English                 | 中文核心含义                                         |
| ----------------------- | ---------------------------------------------------- |
| Logical Value           | 类型对外表示的语义值                                 |
| Representation          | object在机器中的内部表示                             |
| Value Semantics         | object copy/move所定义的逻辑值关系                   |
| Copy Construction       | 从已有对象创建新对象值                               |
| Copy Assignment         | 用已有值替换已存在对象状态                           |
| Move Construction       | 从可消费source建立新对象                             |
| Move Assignment         | 用可消费source替换已有target状态                     |
| Moved-from State        | move后source仍存活的合法状态                         |
| Copy Elision            | 不建立/不转移某些中间对象                            |
| RVO                     | Return Value Optimization                            |
| NRVO                    | Named Return Value Optimization                      |
| Result Object           | 函数调用返回值最终对应的对象                         |
| Inline Representation   | payload直接存在object内部                            |
| Indirect Representation | object通过handle/pointer管理外部payload              |
| Hybrid Representation   | runtime按状态在inline/indirect之间切换               |
| SSO                     | Small String Optimization                            |
| SBO                     | Small Buffer/Object Optimization                     |
| Relocation              | 将值从一处storage迁移到另一处并结束旧object lifetime |
| Invalidation            | 之前合法的access path变为非法                        |
| Amortized Complexity    | 多次操作平均后的复杂度保证                           |
| Zero-copy               | 避免主要payload duplication                          |
| Stable ID               | 与物理storage address解耦的logical identity          |

---

# Part 41 · G3 最终统一公式

```text
Performance(T, operation)
=
Logical Semantics
×
Representation
×
Runtime State
×
Storage Topology
×
Ownership/Lifetime Contract
```

或者更工程化：

```text
Cost
=
Bytes Moved
+
Allocations
+
Element Operations
+
Indirections
+
Synchronization
+
Cache Effects
+
Lifetime Coordination
```

因此：

> **C++ performance is semantic.**

---

# Part 42 · G1 + G2 + G3 Unified Mental Model

任何 access/value/resource问题，现在都可以按三层判断：

```text
Layer 1 — Validity

Does the object exist?
Is storage valid?
Is access in bounds?
Has it been invalidated?


Layer 2 — Ownership

Who keeps it alive?
Who cleans it up?
Who borrows?
Who shares?


Layer 3 — Cost

What is copied?
What is moved?
What is allocated?
How many indirections?
What layout reaches the CPU?
```

压缩：

```text
Correct?
↓
Owned correctly?
↓
Efficiently represented and moved?
```

---

# Part 43 · G3 Final Gate

必须能够独立解释：

## Value

1. Logical value和object representation区别是什么？
2. Value semantics为什么不等于deep copy？
3. span/shared_ptr为什么也拥有自己的value semantics？
4. move-only type为什么仍能成为优秀value abstraction？

## Copy

1. 为什么`sizeof(vector)`不能预测copy成本？
2. inline与indirect value copy成本有什么不同？
3. O(1)为什么不等于cheap？
4. copy为什么有时是lifetime-decoupling primitive？

## Move

1. `std::move`真正做什么？
2. 为什么vector move常O(1)而array move O(N)？
3. moved-from object为什么仍然alive？
4. 为什么const常阻止真正move？
5. 为什么cheap resource-owner move应尽量`noexcept`？

## Elision

 1. `return T{};`与`return local;`有什么区别？
 2. guaranteed copy elision与NRVO区别是什么？
 3. 为什么`return std::move(local)`通常是错误？
 4. 为什么return-by-value不等于copy-heavy API？

## Parameters

 1. `T` / `const T&` / `T&` / `T&&`分别是什么semantic contract？
 2. small value为什么常by value？
 3. sink为什么常适合by value？
 4. span/string_view为什么通常by value？
 5. 为什么跨async boundary必须重新做ownership decision？

## Containers

 1. vector size与capacity区别是什么？
 2. reallocation为什么开始新object lifetimes？
 3. 为什么pointer/reference/iterator失效？
 4. 为什么noexcept move影响vector relocation？
 5. reserve为什么同时是performance和lifetime工具？
 6. amortized O(1)为什么不适合直接推断realtime latency？

## Representation

 1. inline / indirect / hybrid分别交换什么？
 2. SSO/SBO为什么能降低allocation？
 3. SBO为什么可能伤cache density？
 4. 为什么hybrid representation会产生performance cliff？
 5. optional/variant如何再次体现storage与object lifetime分离？

## Architecture

 1. zero-copy真正消除了什么？
 2. zero-copy新增什么协调成本？
 3. stable ID为什么有时优于stable address？
 4. 为什么dense small values通常优于pointerized small values？
 5. 如何同时画ownership/cost/allocation/invalidation graph？

---

# Part 44 · 如果几个月后只记住十五条

1. **不要从C++语法猜性能；先理解type的logical value和representation。**

2. **`sizeof(T)`只描述object本体，不一定描述它拥有或代表的数据规模。**

3. **Copy要求保留source logical value；Move允许消费source state；Elision可以完全消除transfer。**

4. **`std::move`只是xvalue cast，真正move由后续operation执行。**

5. **Indirect owner通常copy昂贵、move便宜；inline value的move可能和copy一样贵。**

6. **Moved-from object仍然alive；只能依赖其type明确提供的moved-from contract。**

7. **`noexcept` move是generic performance contract，而不仅是异常声明。**

8. **Modern C++应大胆return-by-value；`return local;`让NRVO和implicit move工作，不要机械`std::move`。**

9. **参数首先表达borrow/own/consume/view/share，然后才讨论性能。**

10. **Small values适合value-flow；large synchronous input适合borrow；large ownership通常适合move。**

11. **vector用growth-time relocation与地址不稳定交换dense contiguous storage和优秀cache locality。**

12. **SSO/SBO用更大的wrapper换取减少small-value allocation，因此同时影响cache、move、ABI和threshold cliffs。**

13. **Zero-copy将memory-bandwidth成本转换成lifetime、aliasing、reuse和synchronization成本。**

14. **Small copy有时是在购买lifetime independence、thread independence和storage abstraction。**

15. **健康的高性能C++系统通常是dense small values + cheap movable owners + narrow borrows + explicit shared islands + measured storage reuse。**

---

# G3 → G4

G3 到此冻结。

我们已经回答：

> **一个C++ value在程序中流动时，它的copy、move、return、parameter passing和container relocation究竟意味着什么成本。**

G4 接下来不再围绕单个 object。

而要扩大到：

```text
Container
    ↓
Storage Topology
    ↓
Iterator
    ↓
Invalidation
    ↓
Algorithm
    ↓
Ranges / Views
    ↓
Abstraction Cost
```

下一阶段的核心问题将变成：

> **怎样选择、遍历和组合一整个value集合，同时仍然保持对memory layout、iterator validity、algorithmic complexity和machine cost的控制。**
