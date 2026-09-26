# C++ Systems Track · G12 C++ × Zig × Rust Unified Systems Model

**Version:** 1.0  
**Status:** Complete / Final Unified Baseline  
**C++ Baseline:** C++23  
**Rust Baseline:** Rust 2024 Edition  
**Zig Baseline:** Modern Zig systems model  
**Prerequisites:** G0–G11  
**Scope:** Object / Storage / Lifetime / Ownership / Borrowing / Aliasing / Value Semantics / Allocation / Error Model / Genericity / ABI / Concurrency / Build / Performance / Real-Time / Systems Architecture  
**Purpose:** 将整个 Modern C++ Systems Track 压缩到一套**语言无关的系统工程模型**，明确 C++、Rust、Zig 分别替程序员表达、约束和证明什么，以及哪些问题最终仍必须由架构与工程纪律解决。

---

# 0. G12 的定位

前面 G0–G11 表面上是在学习 C++：

```text
compiler
object
lifetime
RAII
move
STL
templates
cache
atomics
ABI
CMake
runtime
robotics
```

但真正形成的知识并不属于 C++。

例如：

```text
Object Lifetime
Ownership
Aliasing
Cache Locality
Memory Reclamation
Backpressure
ABI
Real-Time
```

这些首先是：

> **Systems Problems**

语言只是选择不同机制表达这些问题。

因此 G12 不再问：

> Rust 有没有 `std::vector`？

> Zig 有没有 move constructor？

> C++ 有没有 borrow checker？

而是把问题反过来：

```text
系统约束是什么？
       ↓
谁拥有资源？
       ↓
谁可以访问？
       ↓
什么时候失效？
       ↓
是否需要动态分配？
       ↓
失败怎样传播？
       ↓
并发修改怎样协调？
       ↓
binary boundary 是什么？
       ↓
timing requirement 是什么？
       ↓
应该让语言证明哪些东西？
```

然后再比较：

```text
C++ 怎么表达？
Rust 怎么约束？
Zig 怎么显式控制？
```

---

# Part I · 三门语言不是同一个问题的三个“版本”

# 1. 一个非常重要的定位

把三门语言简单排成：

```text
C++
↓
Rust
↓
Zig
```

或者：

```text
旧 → 新
```

是错误模型。

它们更像三个不同设计点：

```text
                  More static proof
                        ▲
                        │
                       Rust
                        │
                        │
C++ ────────────────────┼──────── Zig
rich abstraction        │         explicit mechanism
large ecosystem         │         explicit control
                        │
                        ▼
                programmer discipline
```

这只是概念图，不是严格坐标。

真正区别在于：

> **哪类系统约束由语言负责，哪类约束留给程序员。**

---

# 2. C++ 的核心选择

C++ 大体选择：

```text
high-level abstraction
+
direct machine representation
+
backward compatibility
+
programmer-controlled lifetime
```

它提供：

```text
RAII
templates
value semantics
STL
exceptions
virtual dispatch
atomics
manual low-level control
```

但允许程序员做：

```text
dangling pointer
use-after-free
data race
invalid aliasing
lifetime violation
```

并把许多错误归入：

> Undefined Behavior

因此：

> **C++ 给了极大的表达空间，也把很大的 proof burden 留给程序员。**

---

# 3. Rust 的核心选择

Rust 选择：

```text
ownership
+
borrowing
+
lifetimes
+
type-driven concurrency constraints
```

把大量 C/C++ 常见错误变成：

> compile-time rejection

典型：

```text
use after free
double free
many aliasing violations
non-Send type sent across threads
ordinary unsynchronized data races
```

但代价是：

```text
stronger type constraints
lifetime architecture visible in APIs
unsafe boundary must be audited
some designs need restructuring
```

Rust的核心价值不是：

> “内存管理自动化”。

而是：

> **把 ownership / aliasing / lifetime 的大量 proof obligation交给编译器。**

---

# 4. Zig 的核心选择

Zig更强调：

```text
explicit allocation
explicit errors
explicit cleanup
explicit comptime
minimal hidden runtime behavior
```

例如：

```zig
const buffer = try allocator.alloc(u8, count);
defer allocator.free(buffer);
```

你能非常直接看到：

```text
where allocation happens
which allocator is used
where cleanup happens
```

但 Zig 没有 Rust borrow checker。

所以：

```text
dangling pointer
aliasing mistakes
lifetime mistakes
concurrent races
```

仍主要依赖：

> programmer architecture + testing + safety checks。

因此 Zig 的核心不是：

> “Rust without borrow checker”。

更准确是：

> **一种强调机制显式性和低层可控性的现代 systems language。**

---

# Part II · Unified Layer Model

以后无论使用哪门语言，都可以按以下层次推理：

```text
┌───────────────────────────────┐
│ Domain Semantics              │
├───────────────────────────────┤
│ Ownership / Lifetime          │
├───────────────────────────────┤
│ Type / Value / Aliasing       │
├───────────────────────────────┤
│ Storage / Allocation          │
├───────────────────────────────┤
│ Concurrency / Synchronization │
├───────────────────────────────┤
│ Representation / Layout       │
├───────────────────────────────┤
│ ABI / Binary Boundary         │
├───────────────────────────────┤
│ Compiler / Build              │
├───────────────────────────────┤
│ CPU / Memory / Hardware       │
└───────────────────────────────┘
```

语言改变的是中间若干层的表达方式。

最底层：

```text
cache
TLB
pages
branch predictor
CPU memory hierarchy
```

完全不关心你使用的是：

```text
C++
Rust
Zig
```

---

# Part III · Object

# 5. C++ Object Model

C++ 中：

> object 是一段具有 type、lifetime、storage 和 value/state 的语言实体。

必须区分：

```text
storage
≠
object
≠
value
```

例如：

```cpp
void* storage =
    ::operator new(sizeof(T));

T* object =
    std::construct_at(
        static_cast<T*>(storage),
        args...);
```

先有 storage，

然后：

> T object lifetime begins。

---

# 6. Rust 的 Object-like 模型

Rust不使用完全相同的标准术语体系。

但系统上仍然有：

```text
value
storage
place
lifetime
type
```

例如：

```rust
let value = Foo { ... };
```

`value` 必须存放于某处。

Rust最大的不同不是：

> 没有 object。

而是：

> ownership/lifetime规则更加进入语言静态语义。

---

# 7. Zig Value / Storage 模型

Zig通常更加直接：

```zig
var foo: Foo = .{ ... };
```

有：

```text
typed storage
value
address if taken
```

没有 C++：

```text
constructor
destructor
copy constructor
move constructor
```

这一套隐式生命周期 hook。

初始化和 cleanup通常显式表达。

---

# 8. Unified Principle

三门语言都逃不开：

```text
Storage exists
    ↓
Value/Object is initialized
    ↓
Program accesses it
    ↓
Lifetime ends
    ↓
Storage may be reused/released
```

真正区别是：

> **谁负责证明每一步合法。**

---

# Part IV · Lifetime

# 9. C++

C++ lifetime高度灵活：

```text
automatic
dynamic
static
thread-local
placement construction
manual destruction
```

RAII提供非常强的结构化 lifetime管理，

但语言仍允许：

```cpp
T* p = owner.get();

owner.reset();

use(*p); // UB
```

编译器通常无法阻止。

---

# 10. Rust

Rust把：

```text
ownership
borrowing
lifetime relationship
```

放入 static analysis。

例如：

```rust
let r = &value;
drop(value);
use_ref(r);
```

安全 Rust 中无法合法通过 borrow checker。

因此很多：

```text
G1 lifetime reasoning
```

在 Rust 中：

> 编译器可以替程序员证明。

---

# 11. Zig

Zig不会静态证明：

```text
borrow lifetime <= owner lifetime
```

例如 slice/pointer是否 dangling：

> 仍由程序员负责。

Zig可以通过：

```text
defer
errdefer
allocator discipline
```

让 lifetime代码非常显式，

但：

> **显式 ≠ 静态证明。**

---

# 12. 三种哲学

```text
C++
lifetime expressed through scopes + RAII + conventions

Rust
lifetime partly encoded/proven through ownership/borrows

Zig
lifetime explicitly managed with lexical cleanup + discipline
```

---

# Part V · Resource Cleanup

# 13. C++ — RAII

```cpp
class File {
public:
    explicit File(int fd)
        : fd_{fd} {}

    ~File() {
        ::close(fd_);
    }

private:
    int fd_;
};
```

Scope exit：

```text
destructor automatically runs
```

因此：

```text
resource lifetime
=
object lifetime
```

是 C++ 最强大的架构之一。

---

# 14. Rust — `Drop`

Rust：

```rust
struct File {
    fd: RawFd,
}

impl Drop for File {
    fn drop(&mut self) {
        // close
    }
}
```

同样：

> lexical lifetime → deterministic cleanup。

因此：

```text
C++ RAII
≈
Rust ownership + Drop
```

在资源管理思路上很接近。

---

# 15. Zig — `defer`

Zig：

```zig
const file = try openFile(...);
defer file.close();
```

cleanup与 acquisition：

> 在源码局部显式配对。

没有 hidden destructor invocation。

因此：

```text
C++ / Rust
resource cleanup encoded in type

Zig
resource cleanup frequently encoded in control-flow scope
```

这是一个非常深的差异。

---

# 16. Type-driven vs Scope-driven Cleanup

### C++ / Rust

```text
Type says:
"I own a resource"

destroy/drop
→ cleanup
```

### Zig

通常：

```text
Acquire resource
↓
immediately write defer
```

所以 Zig的优势之一：

> cleanup behavior非常可见。

代价：

> 类型本身可能没有完整表达 ownership policy。

---

# Part VI · Ownership

# 17. C++ Ownership 不主要存在于语言核心

C++ 用类型和约定表达：

```text
T
unique_ptr<T>
shared_ptr<T>
T*
T&
span<T>
```

但：

```cpp
T* p;
```

语言不能告诉你：

```text
owner?
borrower?
nullable?
lifetime?
```

必须靠 API contract。

---

# 18. Rust Ownership 是语言核心

```rust
let a = value;
let b = a;
```

对于非-`Copy` type：

```text
ownership:
a → b
```

之后 `a` 不再可用。

因此：

> move 是语言级 ownership transfer。

---

# 19. Zig 没有 Rust式 Ownership Move

Zig中赋值/传值不会形成：

> “source 自动进入 moved-from / unusable 状态”

的 Rust ownership语义。

所以一个含资源 handle 的 struct：

```zig
var a = Resource{ ... };
var b = a;
```

如果你把这种 value copy 当 ownership transfer，

可能产生：

```text
double cleanup
aliasing ownership
```

因此 Zig资源类型设计必须自己约束：

> 哪些值可复制、哪些操作形成 logical transfer。

---

# 20. 最重要区别

```text
C++
ownership is a library/API convention strongly supported by RAII

Rust
ownership is a core language rule

Zig
ownership is explicit engineering discipline
```

---

# Part VII · Borrowing

# 21. C++

Borrow：

```cpp
const T&
T&
std::span<const T>
std::span<T>
T*
```

编译器主要保证：

```text
type correctness
```

而：

```text
borrow lifetime
aliasing discipline
```

大量由程序员保证。

---

# 22. Rust

```rust
&T
&mut T
```

具有强 aliasing模型。

粗略：

```text
&T
→ shared immutable access

&mut T
→ exclusive mutable access
```

安全 Rust 会限制：

> 同时存在不兼容 borrow。

这是其优化和 data-race safety 的核心基础之一。

---

# 23. Zig

```zig
[]const T
[]T
*T
*const T
```

可以非常清晰表达：

```text
extent
mutability
pointer shape
```

但不会像 Rust：

> 静态验证整个 borrow graph。

---

# 24. 对照

```text
C++ span<const T>
Zig []const T
Rust &[T]
```

机器表示都大体可能类似：

```text
pointer
+
length
```

但语言 guarantee完全不同。

这是非常重要的原则：

> **相同 machine representation，不代表相同 language semantics。**

---

# Part VIII · Aliasing

# 25. 为什么 Aliasing 这么重要？

编译器看到：

```text
pointer A
pointer B
```

需要判断：

> 它们可能指向同一 storage 吗？

这直接影响：

```text
load reuse
store reordering
vectorization
optimization
```

---

# 26. C++

C++ 有复杂：

```text
type-based aliasing
lifetime
object representation
```

规则。

错误的：

```cpp
reinterpret_cast<T*>
```

很容易触碰 UB。

---

# 27. Rust

Rust尤其通过：

```text
&mut T
```

表达强 exclusive access语义。

这给 compiler更多优化信息。

但：

```rust
unsafe
raw pointers
UnsafeCell
```

可以进入更低层模型。

---

# 28. Zig

Zig提供直接 pointer/slice 操作，

但 aliasing proof主要靠：

> programmer。

某些函数/API可根据语义设计避免 alias。

---

# 29. Unified Rule

性能敏感系统应该尽量让：

```text
ownership
+
mutation authority
+
aliasing
```

保持简单。

无论语言如何。

因为：

> 复杂 alias graph 同时伤 correctness 和 optimization。

---

# Part IX · Value Semantics

# 30. C++

C++有：

```text
copy constructor
move constructor
copy assignment
move assignment
```

并且：

```cpp
std::move
```

只是：

> value-category cast。

实际是否 move由 overload resolution和type behavior决定。

---

# 31. Rust

Rust默认：

```text
move semantics
```

对于非 `Copy` type。

这里的 move更接近：

> ownership transfer at language level。

并不是：

```text
invoke user-defined move constructor
```

Rust没有 C++ 那种 move-constructor protocol。

---

# 32. `Copy`

Rust type如果实现：

```rust
Copy
```

赋值可以继续使用 source。

适合：

```text
small plain values
```

这更接近 C++：

```text
trivially / cheaply copyable value
```

但语言机制完全不同。

---

# 33. Zig

Zig也没有 C++式 move constructor。

Value assignment的语义更直接。

这意味着：

> “move-only resource type”

不像 C++ `unique_ptr` 或 Rust owner那样由语言机制天然表达。

需要 API / type discipline设计。

---

# 34. 三种 Move 的区别

```text
C++
move = overload-based resource transfer optimization

Rust
move = ownership transfer semantic

Zig
no dedicated ownership-move semantic;
resource transfer is an engineering convention
```

这一点必须严格区分。

---

# Part X · Allocation

# 35. C++

通常：

```cpp
std::vector<T> values;
```

默认 allocator隐含在 container abstraction内。

也可以：

```text
custom allocator
std::pmr
arena
pool
```

但普通 API常不显式传 allocator。

---

# 36. Rust

普通：

```rust
Vec<T>
Box<T>
String
```

通常也使用 allocator infrastructure，

allocation strategy一般不像 Zig那样成为每个函数签名中的显式 dependency。

---

# 37. Zig

典型 API：

```zig
fn parse(
    allocator: std.mem.Allocator,
    input: []const u8,
) !Result
```

allocation capability直接进入函数参数。

这是 Zig 极具代表性的设计。

---

# 38. Zig Allocator = Explicit Dependency Injection

函数需要 dynamic memory：

```text
必须由 caller提供 allocator
```

于是 caller决定：

```text
general heap?
arena?
fixed buffer?
testing allocator?
```

这不仅是 memory management。

还是：

> **architecture-level resource dependency。**

---

# 39. 三种 Allocation Philosophy

```text
C++
container/object often owns allocation policy implicitly

Rust
ownership strongly modeled,
allocator often abstracted behind owning containers

Zig
allocator frequently explicit in API
```

---

# 40. 谁更快？

这个问题本身错误。

最终：

```text
malloc
arena
pool
stack
fixed buffer
```

的机器成本不取决于：

> language logo。

区别主要是：

> 语言让 allocation topology 多容易被看见和控制。

---

# Part XI · Error Model

# 41. C++

主要工具：

```text
exceptions
expected<T,E>
error codes
optional
```

它允许项目自行定义：

> domain error model。

---

# 42. Exception

优点：

```text
separate success path from failure propagation
automatic unwinding
RAII cleanup
```

代价/约束：

```text
exception ABI
throw-path cost
control-flow invisibility
real-time concerns
FFI boundary
```

---

# 43. Rust

主要：

```rust
Result<T, E>
Option<T>
?
```

失败是：

> normal value/control-flow semantics。

Panic是：

> 另一层 failure mechanism，

不应该等同 `Result::Err`。

---

# 44. Zig

核心：

```zig
!T
```

error union。

传播：

```zig
try operation();
```

处理：

```zig
catch
```

cleanup：

```zig
errdefer
```

语言层非常直接。

---

# 45. 对照

```text
C++
exceptions or expected

Rust
Result<T,E>

Zig
error union !T
```

Rust/Zig 默认更倾向：

> error as explicit type flow。

C++则同时支持：

> exception channel

和：

> value channel。

---

# 46. 但所有语言都还有一个共同问题

假设：

```text
modify state A
modify state B
then error
```

即使返回：

```text
Err
unexpected
error union
```

都不会自动让：

> A/B rollback。

所以：

> **Error Representation ≠ Transaction Safety**

G2 的：

```text
prepare
↓
commit
```

在三门语言都成立。

---

# Part XII · Panic / Abort / Fatal Errors

# 47. Rust Panic

通常表达：

> 当前执行路径遇到不应该按普通 domain error 处理的失败。

具体可能：

```text
unwind
or
abort
```

取决于编译策略/环境。

---

# 48. Zig Panic

安全检查失败等情况可能：

> panic。

它不是普通 error union。

---

# 49. C++ `terminate`

例如：

```text
uncaught exception from noexcept
thread entry exception
```

可能：

> terminate process。

---

# 50. Unified Failure Taxonomy

任何语言都应该区分：

```text
Domain Error
Expected operational failure

Cancellation
Normal control outcome

Bug / Invariant Failure
Programming defect

Fatal Infrastructure Failure
Process/runtime cannot safely continue
```

不要全变成：

```text
bool false
```

---

# Part XIII · Generic Programming

# 51. C++

```cpp
template <typename T>
requires SomeConcept<T>
void process(T&& value);
```

特点：

```text
template instantiation
concept constraints
overload resolution
compile-time structural specialization
```

---

# 52. Rust

```rust
fn process<T: Trait>(value: T) {
    ...
}
```

泛型通常结合：

```text
traits
monomorphization
```

表达 static polymorphism。

也可以：

```rust
dyn Trait
```

使用 dynamic dispatch。

---

# 53. Zig

常见：

```zig
fn process(
    comptime T: type,
    value: T,
) void
```

或者：

```zig
fn process(value: anytype) void
```

通过：

```text
comptime evaluation
```

直接生成具体代码。

---

# 54. 三种 Compile-time Genericity

机器层最终经常都是：

```text
generic source
↓
concrete type known
↓
specialized machine code
```

所以：

```text
C++ templates
Rust generics
Zig comptime
```

在很多场景共享：

> static specialization

这一机器成本模型。

---

# 55. 主要差异

### C++

系统非常强大但历史复杂：

```text
deduction
SFINAE
concepts
specialization
overload resolution
```

### Rust

generic constraints主要通过：

```text
Trait
```

统一表达。

### Zig

更多直接使用：

```text
comptime values/types
compile-time reflection
```

构建泛型。

---

# 56. Genericity Cost 三门语言都一样

```text
compile time
code bloat
I-cache footprint
debug complexity
```

不会因为使用 Rust/Zig自动消失。

G5/G6 的：

> **Genericity Budget**

是语言无关原则。

---

# Part XIV · Static vs Dynamic Polymorphism

# 57. C++

Static：

```cpp
template <typename T>
```

Dynamic：

```cpp
virtual
function pointer
type erasure
```

---

# 58. Rust

Static：

```rust
T: Trait
```

Dynamic：

```rust
dyn Trait
```

---

# 59. Zig

Zig没有 C++/Rust 完全对应的 built-in OOP trait-object体系。

可以通过：

```text
comptime
function pointers
explicit vtable structs
tagged unions
```

设计 static/dynamic dispatch。

---

# 60. Unified Machine Model

最终：

### Static

```text
target compile-time known
→ inline/specialize easier
→ potential code bloat
```

### Dynamic

```text
target runtime selected
→ compact shared code
→ indirect dispatch
```

三门语言完全共享这个 trade-off。

---

# Part XV · Containers

# 61. Dynamic Contiguous Owner

C++：

```cpp
std::vector<T>
```

Rust：

```rust
Vec<T>
```

Zig：

```text
allocator-backed dynamic array/list abstraction
```

共同机器模型：

```text
pointer
size
capacity
+
contiguous T storage
```

具体 representation不应当跨 ABI 假设。

---

# 62. Borrowed Slice

C++：

```cpp
std::span<const T>
```

Rust：

```rust
&[T]
```

Zig：

```zig
[]const T
```

共同能力：

```text
pointer
extent
non-owning sequence view
```

核心差异仍是：

> borrow/lifetime guarantees。

---

# 63. Stable Address

所有语言都必须理解：

```text
vector/Vec/dynamic array growth
↓
storage relocation
↓
old pointers/views invalid
```

Rust借用规则会阻止很多同时持有 borrow + mutable growth 的错误。

C++/Zig更多依赖 programmer discipline。

---

# Part XVI · Layout / Cache / Performance

# 64. `sizeof` 不属于语言哲学

无论：

```text
C++
Rust
Zig
```

object/value最终都需要进入：

```text
bytes
alignment
cache lines
pages
```

---

# 65. AoS vs SoA

完全语言无关：

```text
AoS:
[x y z][x y z][x y z]

SoA:
[x x x]
[y y y]
[z z z]
```

选择由：

> hot access pattern

决定。

---

# 66. Pointer Chasing

```text
Box<T>
unique_ptr<T>
heap pointer
Zig pointer
```

最终如果是：

```text
pointer → scattered allocation
```

都会带来：

```text
cache miss
TLB pressure
dependent loads
```

语言不会取消物理定律。

---

# 67. “Zero-cost Abstraction”的真正含义

不是：

> abstraction没有成本。

而是理想情况下：

> 不需要为未使用的抽象能力付额外运行时成本。

但如果 abstraction本身选择：

```text
shared_ptr / Arc
virtual dispatch / dyn Trait
heap allocation
```

它当然有真实机器成本。

---

# Part XVII · Shared Ownership

# 68. C++

```cpp
std::shared_ptr<T>
```

通常：

```text
strong refcount
weak refcount
control block
```

---

# 69. Rust

```rust
Rc<T>
Arc<T>
```

分别用于：

```text
single-thread reference counting
atomic thread-safe reference counting
```

Rust类型系统进一步限制：

> 哪些值可跨线程。

---

# 70. Zig

没有一个必须使用的语言级 shared-owner abstraction。

可以自己设计：

```text
reference count
arena lifetime
owner registry
handles
```

---

# 71. 共同成本

Reference counting在机器层仍是：

```text
counter updates
possible atomics
cache-line sharing
indirection
```

Rust的 `Arc`：

> memory-safe

并不意味着：

> contention-free。

---

# Part XVIII · Concurrency

# 72. C++

普通 non-atomic data race：

> UB。

程序员必须正确构建：

```text
mutex
atomic
happens-before
```

关系。

---

# 73. Rust

Safe Rust通过：

```text
ownership
Send
Sync
borrow rules
```

防止大量普通 data races。

例如：

> 无法随便把 non-thread-safe reference送给另一个 thread。

---

# 74. 但 Rust 不能阻止

```text
deadlock
livelock
race condition
wrong atomic protocol
priority inversion
queue overload
false sharing
```

因此：

> **Data-race safety ≠ Concurrency correctness。**

---

# 75. Zig

线程和 atomics更加直接。

程序员负责：

```text
synchronization
data races
lifetime
```

类似 C/C++ lower-level discipline。

---

# 76. 三种 Concurrency Safety

```text
C++
language gives atomics/mutex model;
programmer proves protocol

Rust
safe type system proves a significant subset
of sharing/lifetime legality;
programmer still proves protocol

Zig
mechanisms explicit;
programmer proves most sharing/lifetime protocol
```

---

# Part XIX · Single Writer Principle

# 77. 这是最重要的跨语言规律之一

无论哪门语言：

```text
multiple writers
→ synchronization complexity
```

如果改成：

```text
single writer
```

就可以大量减少：

```text
mutex
atomic
borrow conflict
cache-line ping-pong
```

因此：

> **Architecture beats language safety.**

Rust可以让错误 shared mutation更难写，

但优秀架构仍然应该：

```text
thread-local
single-writer
shard
immutable snapshot
```

---

# Part XX · Message Passing

# 78. Rust 的 slogan 经常强调 message passing

但底层本质仍是：

```text
ownership handoff
+
queue synchronization
```

C++：

```cpp
queue.push(std::move(job));
```

Rust：

```rust
sender.send(job);
```

Zig：

> explicit channel/queue implementation。

系统模型完全一样：

```text
Producer owns
↓
Channel/Queue owns
↓
Consumer owns
```

---

# 79. Language Difference

Rust编译器能更强地确保：

> moved value不再被 producer使用。

C++依靠：

```text
move semantics + programmer discipline
```

Zig依靠：

> API convention / logical ownership discipline。

---

# Part XXI · Atomics

# 80. Hardware Atomics 是共同底层

最终：

```text
fetch_add
CAS
acquire
release
```

要映射到：

> CPU atomic/memory-ordering mechanisms。

语言只是给它们不同 API和memory model表达。

---

# 81. Acquire / Release 的概念也不是 C++ 独有

Rust atomics同样有：

```text
Relaxed
Acquire
Release
AcqRel
SeqCst
```

背后来自：

> 同类 memory-ordering模型。

Zig atomics同样需要表达对应的 ordering semantics。

因此 G7 的核心：

```text
publication
HB-like ordering reasoning
atomic state transition
```

是通用 systems knowledge。

---

# 82. Rust 不是“不需要学 Memory Order”

Safe Rust可以阻止很多 ordinary data races。

但如果你写：

```text
lock-free queue
atomic state machine
```

仍然必须理解：

```text
acquire
release
CAS
ABA
reclamation
```

Rust不会自动替你证明 lock-free algorithm正确。

---

# Part XXII · Lock-free

# 83. Lock-free 在三门语言中都是算法属性

不是：

```text
C++ keyword
Rust safety feature
Zig optimization
```

它是：

> Progress Guarantee。

---

# 84. Reclamation 仍然存在

即使 Rust拥有 borrow checker，

真正 lock-free linked structure内部常需：

```text
unsafe
hazard pointer
epoch
Arc
```

因为 ordinary lexical borrowing无法直接描述：

> concurrent node reclamation algorithm的全部动态生命周期。

这说明：

> 某些 systems problem天然会穿过安全抽象层。

---

# Part XXIII · Unsafe

# 85. C++

可以说：

> 大量 C++ 本身就是“需要程序员维持 unsafe-like invariants”。

C++没有一个统一：

```cpp
unsafe { ... }
```

边界。

---

# 86. Rust

Rust显式：

```rust
unsafe {
    ...
}
```

表示：

> compiler不再替你证明某些 safety obligations，但你仍必须维护 Rust要求的 invariants。

它的价值在于：

> **把 proof boundary 显式局部化。**

---

# 87. Zig

Zig也没有 Rust同类型的语言级：

```text
safe world / unsafe block
```

二分。

安全检查、低层操作与 programmer discipline形成另一种模型。

---

# 88. Rust `unsafe` 的真正优势

不是：

> unsafe code不会出错。

而是：

```text
99% safe code
        │
        ▼
small unsafe boundary
        │
        ▼
manually audited invariant
```

这使 review surface变小。

---

# Part XXIV · ABI

# 89. C++ ABI

C++ native ABI：

> 不是语言标准统一的稳定跨工具链 ABI。

涉及：

```text
mangling
vtable
layout
exceptions
stdlib
```

---

# 90. Rust ABI

Rust-native ABI也不是用于长期跨 compiler/version稳定互操作的通用 binary contract。

稳定 FFI通常：

```rust
extern "C"
#[repr(C)]
```

降到 C ABI。

---

# 91. Zig ABI

Zig与 C interop非常直接，

但长期稳定 interoperability仍应优先使用：

> 明确 C ABI contract

而不是依赖 Zig-native representation。

---

# 92. 三语言共同黄金边界

```text
C++ Core
    │
Rust Component
    │
Zig Component
    │
    ▼
Stable C ABI
```

类型：

```text
fixed-width integers
pointer + length
opaque handles
function pointers
plain versioned structs
```

---

# Part XXV · FFI 会削弱语言 Guarantees

# 93. Rust Example

Rust：

```rust
unsafe extern "C" {
    fn get_buffer(
        ptr: *mut *const u8,
        len: *mut usize,
    );
}
```

一旦进入 raw pointer FFI：

borrow checker无法知道：

```text
who owns?
how long valid?
thread safe?
aligned?
```

这些重新变成：

> manual contract。

---

# 94. C++ / Zig 也一样

FFI boundary是：

> language guarantee 的最低公共层。

所以：

> **FFI design quality比内部语言选择更重要。**

---

# Part XXVI · Build Model

# 95. C++

典型：

```text
CMake
+
Ninja
+
Conan/vcpkg/system packages
```

多个工具协作。

优势：

> 巨大的 native ecosystem compatibility。

代价：

> configuration complexity。

---

# 96. Rust

Cargo高度整合：

```text
package
dependency
build
test
publish
```

开发体验统一得多。

---

# 97. Zig

`std.Build` 属于 toolchain-native build model。

可以直接操作：

```text
artifacts
targets
modules
C/C++ compilation
```

这也是 Zig非常有特色的一点。

---

# 98. 语言集成程度

粗略：

```text
Rust
most integrated package/build experience

Zig
strong integrated build/toolchain model

C++
most heterogeneous ecosystem
but widest legacy/native integration
```

---

# 99. 但 Build Graph 思想完全相同

无论：

```text
CMake target
Cargo crate/package
Zig build artifact
```

本质还是：

```text
Artifact Nodes
+
Dependency Edges
```

G9知识完全可迁移。

---

# Part XXVII · Compilation Model

# 100. C++

经典：

```text
translation units
headers
separate compilation
linking
```

Modules正在逐步改变 source dependency模型。

---

# 101. Rust

crate/module system更统一进入 compiler/package model。

编译单元模型与 C++ TU历史结构差异很大。

---

# 102. Zig

module/import与 build system结合更直接，

没有 C/C++ preprocessor header inclusion同样的历史包袱。

---

# 103. 为什么 C++ Build 特别复杂？

很大一部分来自：

```text
textual inclusion
separate compilation
macro configuration
ABI ecosystem
30+ years compatibility
```

这不是：

> CMake单独造成的。

---

# Part XXVIII · Preprocessor

# 104. C++

Preprocessor仍然是核心现实：

```cpp
#include
#define
#if
```

优点：

```text
powerful compatibility/configuration
```

代价：

```text
textual model
macro hygiene
compile dependency
ODR/config mismatch
```

---

# 105. Rust

没有 C-style textual preprocessor作为日常 compilation model。

Conditional compilation：

```rust
#[cfg(...)]
```

属于语言/toolchain系统。

---

# 106. Zig

也没有传统 C preprocessor作为 Zig代码核心机制。

更多使用：

```text
comptime
build options
normal language constructs
```

因此 Zig/Rust把很多 C++：

```text
preprocessor metaprogramming/config
```

问题移动到了：

> language-aware mechanisms。

---

# Part XXIX · Reflection / Compile-time Evaluation

# 107. C++

C++23 compile-time能力：

```text
templates
constexpr
consteval
concepts
```

非常强，

但结构来源复杂。

---

# 108. Zig

`comptime` 是语言设计中心之一。

例如：

```zig
fn Buffer(
    comptime T: type,
    comptime N: usize,
) type {
    ...
}
```

Compile-time与ordinary language syntax高度统一。

---

# 109. Rust

主要通过：

```text
generics
traits
const generics
const evaluation
macros
procedural macros
```

多个机制完成不同层次的 compile-time programming。

---

# 110. Zig 的独特价值

在：

```text
code generation
protocol decoding
static configuration
C integration
```

场景中，

`comptime` 能非常直接地：

```text
consume static metadata
↓
generate specialized program structure
```

这与你之前多车型 decoder / build-time decode plan 的方向非常契合。

---

# Part XXX · Code Generation

# 111. 三种策略

假设有：

```text
6000 signals
static DBC metadata
```

可以：

### C++

```text
external codegen
templates
constexpr tables
```

### Rust

```text
build.rs
proc macros
generated Rust
const generics
```

### Zig

```text
comptime
build system codegen
generated Zig
```

---

# 112. 什么时候 External Codegen 更好？

如果 metadata来自：

```text
CSV
DBC
schema
external specification
```

外部 codegen通常有优势：

```text
generated output inspectable
generation errors separate
compile-time complexity controlled
```

不要为了“语言可以 comptime”就把所有 generator塞进 type system。

---

# Part XXXI · Real-Time

# 113. 语言不会自动给你 Real-Time

这条必须明确：

```text
Rust memory-safe
≠
real-time

Zig explicit allocation
≠
real-time

C++ no GC
≠
real-time
```

Real-time来自：

```text
bounded execution
scheduling
allocation discipline
OS
hardware
I/O
architecture
```

---

# 114. C++ 在 RT 中的优势

```text
mature embedded/robotics ecosystem
deterministic destruction
fine allocation control
fixed-size abstractions
hardware/vendor integration
```

但需审查：

```text
exceptions
allocation
STL growth
locking
```

---

# 115. Rust 在 RT 中的优势

```text
ownership safety
data-race safety
strong state modeling
no GC
```

但仍需处理：

```text
allocation
panic policy
executor behavior
OS scheduling
unsafe drivers/FFI
```

---

# 116. Zig 在 RT 中的优势

显式 allocator：

```text
makes allocation points obvious
```

`defer`：

```text
cleanup explicit
```

较少 hidden control mechanisms。

但仍无自动：

```text
deadline proof
lifetime proof
race proof
```

---

# Part XXXII · Embedded

# 117. Bare-metal / Firmware

选择通常受：

```text
toolchain
vendor SDK
target support
certification
runtime footprint
ecosystem
```

强烈影响。

不能只比较：

> 语言语法。

---

# 118. C++

优势：

```text
very mature MCU ecosystem
vendor SDK compatibility
decades of embedded tooling
```

---

# 119. Rust

优势：

```text
memory safety
strong embedded community
no_std model
```

但 target/vendor ecosystem仍需具体评估。

---

# 120. Zig

优势：

```text
cross-compilation design
C integration
explicit runtime control
```

非常适合 low-level experimentation和 C ecosystem modernisation。

---

# Part XXXIII · Performance

# 121. 最重要的一句话

在优化良好的代码中：

```text
C++
Rust
Zig
```

理论上都能够生成非常接近硬件极限的 machine code。

所以：

> **语言名字通常不是第一性能变量。**

更重要：

```text
algorithm
layout
allocation
access pattern
vectorization
concurrency topology
compiler quality
```

---

# 122. Rust 安全检查会不会慢？

很多：

```text
bounds checks
abstractions
iterators
```

可以被 optimizer消除。

但不是：

> “Rust 永远零开销。”

和 C++一样：

> 看最终 codegen。

---

# 123. Zig 显式是不是自动更快？

不是。

你完全可以写出：

```text
bad cache locality
N allocations
pointer chasing
```

的 Zig。

显式只让：

> 成本更容易被看到。

---

# 124. C++ 抽象是不是自动有开销？

也不是。

```text
span
templates
ranges
RAII
```

大量 abstraction可被完全优化掉。

这就是为什么：

> Assembly / Profiling 比语言刻板印象更可靠。

---

# Part XXXIV · Compile-time vs Runtime Cost

# 125. C++ 典型 Trade-off

大量 templates：

```text
runtime specialization ↑
compile time ↑
binary size ↑
```

---

# 126. Rust 同样存在 Monomorphization Cost

大量 generic instantiations：

```text
compile time
binary size
I-cache
```

同样可能增加。

---

# 127. Zig `comptime` 同样不是免费

过多 compile-time specialization：

```text
compiler work ↑
generated code ↑
binary size ↑
```

所以三门语言都需要：

> **Specialization Budget**

---

# Part XXXV · Binary Size

# 128. 高层语言 Feature 最终都可以增加 Code Footprint

例如：

```text
C++ template instantiations
Rust monomorphized generics
Zig comptime specialization
```

全都可能：

```text
duplicate similar machine code
```

于是伤：

```text
I-cache
binary size
compile time
```

---

# Part XXXVI · Safety

# 129. Memory Safety

粗略比较：

| Problem                | C++                  | Rust safe code                                     | Zig                          |
| ---------------------- | -------------------- | -------------------------------------------------- | ---------------------------- |
| UAF static prevention  | 弱                   | 强                                                 | 弱                           |
| Double free prevention | 主要靠 RAII          | 强                                                 | 主要靠纪律                   |
| Borrow lifetime        | 手动                 | 编译器                                             | 手动                         |
| Ordinary data race     | programmer proof     | safe code强约束                                    | programmer proof             |
| Bounds checks          | API/config dependent | generally language/runtime checks where applicable | safety-mode dependent checks |
| Raw pointer access     | 普遍                 | `unsafe`                                           | 普遍可表达                   |

这个表不是：

> “安全分数”。

而是说明：

> proof responsibility在哪里。

---

# 130. Rust最大的结构优势

不是：

> 不会写 bug。

而是把：

```text
large class of invalid programs
```

直接从可编译程序集合中排除。

---

# 131. C++的结构优势

它可以：

> 非常容易表达几乎任何 legacy/hardware/ABI shape。

并且拥有：

```text
massive library ecosystem
mature compiler ecosystem
high-performance numerics
native interoperability
```

代价：

> 需要更强工程纪律。

---

# 132. Zig的结构优势

它倾向让：

```text
allocation
cleanup
errors
compile-time behavior
C interop
```

非常显式。

适合：

> 想直接掌控系统机制的工程师。

---

# Part XXXVII · Unsafe Boundaries

# 133. 一个成熟系统不应该追求“没有 Unsafe”

而是：

> **让 unsafe / low-level invariant boundary 小、明确、可测试。**

C++可以人为建立：

```text
safe-ish core
↓
low-level detail namespace
```

Rust自然有：

```text
safe API
↓
unsafe implementation
```

Zig可以通过：

```text
module boundary
explicit pointer/allocator APIs
```

实现类似工程纪律。

---

# Part XXXVIII · State Modeling

# 134. C++

```cpp
enum class State {
    Idle,
    Running,
    Fault,
};
```

非常好。

但非法组合仍可通过复杂对象状态产生。

---

# 135. Rust

Rust enum：

```rust
enum State {
    Idle,
    Running(RunningState),
    Fault(Error),
}
```

非常适合：

> 把状态相关 payload绑定到 variant。

这是其 algebraic data type 的强项。

---

# 136. Zig

Zig：

```zig
const State = union(enum) {
    idle,
    running: RunningState,
    fault: Error,
};
```

同样非常自然。

---

# 137. C++ `std::variant`

可以实现相同思想：

```cpp
using State = std::variant<
    Idle,
    Running,
    Fault>;
```

因此这个差距不是：

> C++ 做不到。

而是：

> Rust/Zig 在语言习惯上更自然地围绕 sum types设计状态。

---

# Part XXXIX · Nullability

# 138. C++

```cpp
T*
```

同时可能表示：

```text
nullable pointer
borrow
owner?
```

语义模糊。

现代 API用：

```text
reference
optional
unique_ptr
span
```

减少歧义。

---

# 139. Rust

```rust
Option<&T>
Option<Box<T>>
```

把：

> nullable

显式进入 type。

---

# 140. Zig

```zig
?*T
?T
```

optional也是语言核心组合。

---

# 141. Lesson

> **Make invalid/optional state explicit in the type whenever practical.**

这不是某一门语言的专属原则。

---

# Part XL · Reflection of Ownership in APIs

# 142. 一个 Buffer API

## C++

```cpp
void process(
    std::span<const std::byte> input);

std::vector<std::byte> make_output();
```

---

## Rust

```rust
fn process(input: &[u8]);

fn make_output() -> Vec<u8>;
```

---

## Zig

```zig
fn process(
    input: []const u8,
) void;

fn makeOutput(
    allocator: Allocator,
) ![]u8;
```

这里差异极其有意义。

Zig API直接告诉你：

> 创建 output需要 allocator。

C++/Rust普通 API则把 allocator隐藏在 owning container里。

---

# Part XLI · Who Pays for Allocation?

# 143. C++

Caller：

```cpp
auto output = make_output();
```

allocation cost隐藏在 function/container内部。

---

# 144. Rust

类似：

```rust
let output = make_output();
```

allocation由 `Vec`内部承担。

---

# 145. Zig

通常：

```zig
const output =
    try makeOutput(allocator);
defer allocator.free(output);
```

allocation capability显式。

---

# 146. 哪个更好？

如果：

> allocation policy是 architecture关键部分，

Zig显式设计非常强。

如果：

> 只希望普通高层 API易用，

C++/Rust owner container会更加简洁。

所以：

> **Explicitness has an ergonomic cost, abstraction has an observability cost.**

---

# Part XLII · Library Design

# 147. C++ Native Library

内部可以：

```text
classes
RAII
templates
STL
exceptions
```

外部稳定边界：

```text
C ABI
```

---

# 148. Rust Library

内部：

```text
ownership
Result
traits
Arc
```

外部：

```text
C ABI
```

---

# 149. Zig Library

内部：

```text
slices
allocators
error unions
comptime
```

外部：

```text
C ABI
```

---

# 150. Unified Native Architecture

```text
┌──────────────────────────────┐
│ Rich Language-native Core    │
└──────────────┬───────────────┘
               │ adapter
               ▼
┌──────────────────────────────┐
│ Small Stable C ABI           │
└──────────────┬───────────────┘
               │
      ┌────────┼────────┐
      ▼        ▼        ▼
     C++      Rust      Zig
    Wrapper  Wrapper   Wrapper
```

这是整个 G8/G12 最值得保留的架构之一。

---

# Part XLIII · Robotics Language Placement

# 151. C++ 很自然的位置

当前机器人生态中：

```text
ROS 2
Eigen
vendor SDKs
control
planning
numerics
hardware APIs
```

C++拥有极强现实优势。

所以：

```text
Control Core
Hardware Integration
Numerical Robotics
```

通常非常自然。

---

# 152. Rust 很自然的位置

例如：

```text
network services
mission infrastructure
safe concurrent services
data ingestion
robot fleet infrastructure
security-sensitive components
```

尤其当：

```text
memory safety
concurrency safety
```

价值很高时。

---

# 153. Zig 很自然的位置

例如：

```text
device utility
C library modernization
embedded support tooling
small runtime
protocol parser
native glue
cross-compiled system tool
```

尤其当：

```text
explicit allocator
C interop
simple runtime
```

重要。

---

# 154. 但不要按层机械分语言

真正问题：

```text
ecosystem?
team skill?
vendor API?
safety?
latency?
certification?
deployment?
```

语言只是 architecture decision 的一部分。

---

# Part XLIV · When C++ Is the Natural Choice

# 155. 强信号

```text
large existing C++ ecosystem
ROS / Eigen / robotics
vendor C++ SDK
very low-level native ABI
large legacy native codebase
library integration dominates
```

---

# 156. C++ 的风险信号

如果系统：

```text
huge shared mutable graph
many inexperienced developers
security-critical memory safety
complex async ownership
```

而团队无法维持强纪律，

C++风险会明显上升。

---

# Part XLV · When Rust Is the Natural Choice

# 157. 强信号

```text
memory safety is central
complex ownership/concurrency
networked infrastructure
security-sensitive code
greenfield system
```

并且依赖 ecosystem足够成熟。

---

# 158. Rust 的成本信号

```text
heavy C++ SDK integration
FFI dominates architecture
team lacks Rust expertise
very dynamic self-referential structures
specific vendor/toolchain limitations
```

需要认真评估。

---

# Part XLVI · When Zig Is the Natural Choice

# 159. 强信号

```text
C interop central
allocator policy central
small low-level system
cross compilation important
explicit runtime desired
compile-time specialization useful
```

---

# 160. Zig 的风险信号

```text
large enterprise ecosystem requirements
large library dependency needs
heavy robotics/numerical ecosystem
team-wide mature tooling expectations
```

需要对现实生态进行评估。

---

# Part XLVII · Mixed-language Cost

# 161. 多语言不是免费

每增加一种语言：

```text
build toolchain
package ecosystem
debugger integration
FFI
ABI
CI
developer skill
error model translation
ownership translation
```

全部增加。

所以：

> **Use multiple languages only when the boundary value exceeds integration cost.**

---

# 162. FFI Boundary 应该粗

差：

```text
C++ function
↓
Rust function
↓
C++ function
↓
Zig function
```

每几个 micro-operations跨一次。

好：

```text
large subsystem
│
│ coarse C ABI
▼
another subsystem
```

边界最好：

```text
stable
coarse
owned
versioned
```

---

# Part XLVIII · Error Translation Across Languages

# 163. C++ Exception

不能直接进入 Rust/Zig/C。

Boundary：

```text
exception
↓
catch
↓
C status/error
```

---

# 164. Rust `Result`

进入 C ABI：

```text
Result<T,E>
↓
status + output
```

---

# 165. Zig Error Union

```text
!T
↓
C status + output
```

所以稳定 ABI通常统一成：

```text
status code
+
out parameters / owned result handle
```

---

# Part XLIX · Ownership Translation Across Languages

# 166. 最安全原则

> **Creator destroys.**

例如：

```c
foo_handle* foo_create();
void foo_destroy(foo_handle*);
```

不管内部是：

```text
C++
Rust
Zig
```

都成立。

---

# 167. Borrowed Buffer

```c
process(
    const uint8_t* data,
    size_t len);
```

明确：

```text
valid for duration of call
not retained
```

---

# 168. Ownership Transfer Buffer

如果需要跨 boundary retain：

最好：

```text
explicit handle
or
explicit release callback
```

不要：

> “你传 pointer，我以后可能用。”

---

# Part L · Concurrency Translation Across FFI

# 169. Rust `Send/Sync` 不穿 C ABI

C library返回：

```text
void*
```

Rust compiler不知道：

```text
thread-safe?
```

Wrapper必须决定：

> 能否安全实现 `Send` / `Sync`。

如果判断错：

> safe Rust wrapper可以建立在错误 unsafe invariant上。

---

# 170. C++ Thread Safety 也不会穿 ABI 自动表达

C header：

```c
foo_process(foo*);
```

必须文档说明：

```text
same handle concurrent calls?
different handles concurrent?
destroy concurrently?
callback thread?
```

---

# 171. Zig 同样如此

FFI没有自动 thread-safety type proof。

因此：

> **Concurrency semantics必须成为 FFI contract的一部分。**

---

# Part LI · Language Guarantees vs Architecture Guarantees

# 172. Rust 能保证 Memory Safety，所以还需要 Architecture 吗？

当然。

Rust无法自动证明：

```text
queue capacity sufficient
deadline met
deadlock impossible
business invariant correct
correct unit
correct coordinate frame
correct shutdown semantics
```

---

# 173. Zig 显式，所以 Architecture 自动清晰吗？

不会。

你可以显式写出：

> 一个非常糟糕的架构。

显式机制只减少：

> hidden behavior。

---

# 174. C++ 工程规范能替代 Borrow Checker 吗？

不能完全替代。

规范：

```text
owner/borrow rules
RAII
span
sanitizers
reviews
```

能大幅降低风险，

但不能提供 Rust那种 static guarantee。

---

# 175. 所以三个层次必须区分

```text
Language Guarantee
        ↓
Library Abstraction
        ↓
Architecture Invariant
```

例如：

### Rust

```text
Language:
borrow safety

Library:
Arc

Architecture:
single-writer shard
```

### C++

```text
Language:
types/lifetime rules

Library:
unique_ptr

Architecture:
single-writer shard
```

### Zig

```text
Language:
typed pointers/slices/errors

Library:
allocator/container

Architecture:
single-writer shard
```

最高层架构仍然最重要。

---

# Part LII · What the Compiler Can Prove

# 176. C++

Compiler能证明：

```text
type correctness
template constraints
many static semantic rules
```

但很多：

```text
pointer lifetime
resource ownership
alias validity
thread sharing
```

不会完整证明。

---

# 177. Rust

Compiler还能证明更多：

```text
ownership uniqueness constraints
borrow lifetime compatibility
many aliasing rules
Send/Sync constraints
```

但不能证明：

```text
logical correctness
deadlock freedom
bounded latency
performance
```

---

# 178. Zig

Compiler可以提供：

```text
strong type checking
compile-time evaluation
runtime safety checks depending build mode
```

但：

```text
ownership/lifetime graph
data-race freedom
```

主要不是静态语言保证。

---

# Part LIII · What No Compiler Can Prove for You Automatically

# 179. Domain Semantics

```text
Is 30 degrees accidentally treated as 30 radians?
```

---

# 180. Correct Shard Key

```text
Does VehicleId partition the right ownership domain?
```

---

# 181. Backpressure

```text
What happens if producer permanently outruns consumer?
```

---

# 182. Real-Time

```text
Will this loop always finish before 1 ms deadline?
```

---

# 183. Business Transaction

```text
Does this state transition preserve domain invariant?
```

---

# 184. Physical Safety

```text
Will actuator enter safe state after host failure?
```

因此：

> **Language Safety ≠ System Correctness**

这是 G12 必须留下的核心结论。

---

# Part LIV · A Unified Systems Design Procedure

以后面对一个新问题，不先选语言。

按下面顺序。

---

# 185. Step 1 — Define the State

```text
系统真正管理哪些 state？
```

---

# 186. Step 2 — Define Lifetime

```text
什么时候创建？
什么时候结束？
谁能让它失效？
```

---

# 187. Step 3 — Define Ownership

```text
谁负责最终 cleanup？
```

---

# 188. Step 4 — Define Borrowing

```text
谁只临时访问？
borrow能持续多久？
```

---

# 189. Step 5 — Define Mutation Authority

```text
有几个 writer？
能否降为 single writer？
```

---

# 190. Step 6 — Define Representation

```text
inline?
heap?
AoS?
SoA?
stable address?
```

---

# 191. Step 7 — Define Allocation Topology

```text
how often?
which allocator?
bounded?
reuse?
```

---

# 192. Step 8 — Define Failure

```text
domain error?
cancel?
fatal?
bug?
```

---

# 193. Step 9 — Define Concurrency

```text
threads?
queues?
HB edges?
backpressure?
```

---

# 194. Step 10 — Define Binary Boundaries

```text
same binary?
shared library?
plugin?
cross-language?
```

---

# 195. Step 11 — Define Timing

```text
throughput?
latency?
deadline?
jitter?
```

---

# 196. Step 12 — Only Then Choose Language

问：

```text
哪门语言的默认 guarantees
与上述约束最匹配？
```

而不是：

> 我喜欢 Rust，所以全部 Rust。

或者：

> C++ 性能最好，所以全部 C++。

---

# Part LV · Example 1 — Binary Decoder

需求：

```text
large byte buffer
high throughput
static schema
C ABI integration
minimal allocation
```

---

# 197. C++

非常自然：

```text
span
generated decode functions
vector/lease
templates/constexpr
```

---

# 198. Zig

也非常自然：

```text
slice
explicit allocator
comptime generated decode
C ABI
```

甚至某些 low-level parser场景：

> Zig的显式性非常有吸引力。

---

# 199. Rust

同样能很好完成：

```text
&[u8]
Result
generated code
safe indexing abstractions
```

如果 parser面对 untrusted data：

> memory-safety guarantee价值很高。

---

# 200. 真正决定因素

可能变成：

```text
existing codebase
ecosystem
build integration
team expertise
FFI
```

而不是 raw performance。

---

# Part LVI · Example 2 — Concurrent Network Service

需求：

```text
complex async ownership
untrusted network
high concurrency
memory safety critical
```

Rust通常很有吸引力，

因为：

```text
ownership
safe concurrency
Result
async ecosystem
```

能够减少相当大的 bug surface。

但仍需设计：

```text
backpressure
timeouts
task ownership
shutdown
```

---

# Part LVII · Example 3 — Robotics Control Core

需求：

```text
vendor C++ SDK
Eigen
ROS 2
hard-ish timing path
existing C++ ecosystem
```

C++往往现实优势非常强。

通过：

```text
RAII
fixed-capacity data
single writer
non-RT boundary
```

可以构造高质量 deterministic core。

Rust/Zig可以用于周边子系统，

但不应仅为了语言偏好牺牲生态。

---

# Part LVIII · Example 4 — Small Cross-platform Native Tool

需求：

```text
small binary
C libraries
cross compilation
explicit resource control
little runtime
```

Zig可能非常适合。

尤其：

```text
build system
C interop
allocator explicitness
```

组合得非常自然。

---

# Part LIX · The Wrong Language Question

# 201. 错误问法

> 哪门语言性能最好？

正确：

```text
哪个具体 workload？
什么 representation？
什么 allocator？
什么 algorithm？
```

---

# 202. 错误问法

> 哪门语言最安全？

正确：

```text
哪一类风险？
memory safety?
logic?
concurrency?
physical safety?
```

---

# 203. 错误问法

> 哪门语言最现代？

正确：

> 哪种语言的 abstraction/guarantees 最匹配系统 constraints？

---

# Part LX · Comparative Matrix

| Dimension                    | C++23                                         | Rust 2024                       | Zig                            |
| ---------------------------- | --------------------------------------------- | ------------------------------- | ------------------------------ |
| Deterministic destruction    | RAII                                          | Drop                            | `defer`/explicit               |
| Ownership static enforcement | 部分/库约定                                   | 强                              | 弱/显式纪律                    |
| Borrow lifetime checking     | 弱                                            | 强                              | 弱                             |
| Move semantics               | user-defined move operations/value categories | ownership move                  | 无专门 ownership move          |
| Explicit allocator APIs      | 可选/PMR                                      | 通常抽象于 owners               | 核心风格                       |
| Error-as-value               | `expected`                                    | `Result`                        | error union                    |
| Exceptions                   | 是                                            | panic 不是普通 error            | 无 C++式 exceptions            |
| Static genericity            | templates/concepts                            | generics/traits                 | comptime                       |
| Dynamic polymorphism         | virtual/type erasure                          | trait objects                   | explicit tables/functions      |
| Native ABI stability         | C++ ABI implementation-specific               | native Rust ABI不作稳定 FFI基础 | native ABI不应作长期跨语言契约 |
| C ABI integration            | 强                                            | 强                              | 很强                           |
| Data-race static prevention  | 弱                                            | safe code强                     | 弱                             |
| Build/package integration    | 分散但生态巨大                                | Cargo 高度集成                  | toolchain-integrated build     |
| Robotics ecosystem           | 极强                                          | 发展中/领域依赖                 | 较小                           |
| Low-level explicitness       | 高                                            | 高但受 safety model约束         | 很高                           |
| Legacy native integration    | 极强                                          | C FFI强，C++需边界              | C interop极强                  |

这不是排名表。

它说明：

> **默认 proof responsibility 的分配不同。**

---

# Part LXI · Performance Matrix

在 hot code最终都要回答：

```text
How many bytes?
How many allocations?
How many branches?
How many cache misses?
How many synchronization operations?
```

而不是：

```text
Which language?
```

---

# 204. Contiguous Storage

```text
vector
Vec
Zig dynamic array
```

如果底层一样：

> cache行为也一样。

---

# 205. Shared Refcount

```text
shared_ptr
Arc
custom atomic RC
```

都可能产生：

> cache-line contention。

---

# 206. Hash Map

语言标准/生态实现不同，

性能差异可以很大。

所以：

> benchmark concrete implementation，

不要 benchmark“语言”。

---

# Part LXII · Concurrency Architecture Matrix

| Problem                   | Best first thought         |
| ------------------------- | -------------------------- |
| Per-worker scratch        | thread-local/owned state   |
| Shared immutable config   | snapshot                   |
| One entity mutable state  | single writer              |
| Many independent entities | sharding                   |
| Work handoff              | ownership-transfer queue   |
| Compound shared invariant | mutex                      |
| Independent scalar metric | relaxed atomic candidate   |
| Conditional atomic state  | CAS                        |
| Lock-free node lifetime   | reclamation scheme         |
| Overload                  | bounded queue/backpressure |

注意：

> 这张表与语言几乎无关。

这就是 G12 最重要的迁移成果之一。

---

# Part LXIII · Language Choice as Risk Allocation

# 207. C++

你选择承担更多：

```text
manual lifetime proof
aliasing proof
data-race proof
ABI/build complexity
```

换：

```text
ecosystem
flexibility
integration
performance control
```

---

# 208. Rust

你把更多：

```text
ownership
borrowing
data-race legality
```

交给 compiler证明。

换来：

```text
stronger constraints
unsafe boundary design
potential FFI friction
```

---

# 209. Zig

你选择：

```text
allocation/error/control flow explicitness
```

并保留：

```text
low-level freedom
```

同时自行承担更多：

```text
lifetime/alias/concurrency proof
```

---

# 210. 因此语言选择其实是

> **Where do you want the proof burden to live?**

```text
compiler?
type system?
library abstraction?
code review?
architecture?
runtime checks?
```

这是比：

> “语法哪个好看”

深得多的问题。

---

# Part LXIV · Team Effects

# 211. 语言不是单人工具

一个 100 人项目的真实约束包括：

```text
average engineer skill
review quality
tooling
hiring
debugging
onboarding
libraries
```

某语言对专家非常高效：

> 不代表对组织整体风险最低。

---

# 212. C++ Team

需要非常强：

```text
style profile
ownership conventions
sanitizers
code review
API discipline
build standards
```

才能把语言自由度控制住。

这也是我们为什么前面用了整条 G0–G11 去建立系统规范。

---

# 213. Rust Team

Compiler会承担更多 guardrail。

但团队仍必须学：

```text
ownership architecture
async behavior
unsafe review
performance
FFI
```

---

# 214. Zig Team

语言简洁不代表 architecture自动一致。

尤其需要：

```text
allocator conventions
ownership conventions
resource cleanup conventions
module boundaries
```

这与你之前的 Zig Architecture Manifesto方向是一致的。

---

# Part LXV · Long-lived Systems

# 215. 10 年系统最重要的往往不是今天最快 3%

而是：

```text
API evolution
ABI stability
debuggability
dependency health
team comprehension
migration cost
```

语言生态稳定性成为核心 architecture constraint。

---

# 216. FFI 可以成为 Migration Boundary

例如：

```text
C++ subsystem
↓
stable C ABI
↓
new Rust implementation
```

只要 boundary不变：

> 可以逐步替换 internals。

同样：

```text
C implementation
↓
Zig implementation
```

也可以。

这就是 stable ABI 的战略价值。

---

# Part LXVI · Anti-patterns

# 217. Anti-pattern 1 — Language Nationalism

> “Rust 能解决所有系统问题。”

> “C++ 永远最快。”

> “Zig 是下一代 C，所以全部 Zig。”

都不是工程推理。

---

# 218. Anti-pattern 2 — Safety = Correctness

Memory-safe 程序仍然可以：

```text
deadlock
drop money
miss deadline
send wrong torque
```

---

# 219. Anti-pattern 3 — Explicit = Correct

Zig代码非常显式：

> 仍可以显式写错 lifetime。

---

# 220. Anti-pattern 4 — RAII = Lifetime Safety

RAII正确管理 owner，

但 borrower仍然可以 dangling。

---

# 221. Anti-pattern 5 — Borrow Checker = No Lifetime Problems Anywhere

FFI、unsafe、logical lifetime、external resources仍然需要 architecture。

---

# 222. Anti-pattern 6 — No GC = Real-Time

完全错误。

---

# 223. Anti-pattern 7 — Zero-cost = Free

没有这种普遍规律。

---

# 224. Anti-pattern 8 — C ABI = Safe ABI

C ABI只是：

> stable low-level calling convention。

Ownership、bounds、lifetime仍需 contract。

---

# 225. Anti-pattern 9 — Cross-language Makes Architecture Cleaner

只有 boundary本身高度清晰时才可能。

否则：

> complexity只是被分散到三套工具链。

---

# 226. Anti-pattern 10 — Rewrite for Language Purity

如果现有系统：

```text
correct
maintained
meets SLO
```

仅因为：

> “Rust/Zig 更现代”

而重写，

通常缺乏工程依据。

---

# Part LXVII · Unified Review Protocol

无论代码是 C++、Rust 还是 Zig，进行 systems review 时按以下顺序。

---

## 1. Object / State

```text
What state exists?
```

---

## 2. Ownership

```text
Who owns it?
```

---

## 3. Lifetime

```text
When does it become invalid?
```

---

## 4. Borrowing

```text
Who temporarily accesses it?
```

---

## 5. Mutation

```text
Who may write?
How many writers?
```

---

## 6. Aliasing

```text
Can there be multiple access paths?
```

---

## 7. Allocation

```text
Where?
How often?
Which lifetime topology?
```

---

## 8. Representation

```text
Inline?
Indirect?
AoS?
SoA?
```

---

## 9. Error

```text
Expected?
Cancelled?
Fatal?
Bug?
```

---

## 10. Concurrency

```text
Who synchronizes with whom?
```

---

## 11. Backpressure

```text
What happens under overload?
```

---

## 12. ABI

```text
What crosses binary/language boundary?
```

---

## 13. Timing

```text
Latency?
Throughput?
Deadline?
Jitter?
```

---

## 14. Evidence

```text
What did we measure?
```

---

## 15. Language

最后才问：

```text
Which language most naturally encodes
the constraints above?
```

---

# Part LXVIII · The Three Proofs

一个高水平 systems engineer最终应该同时做三类 proof。

---

# 227. Semantic Proof

```text
Does the program do the right thing?
```

例如：

```text
correct decoder
correct state transition
correct torque
```

---

# 228. Safety Proof

```text
Can execution violate memory/lifetime/concurrency invariants?
```

Rust可以替你做更多。

C++/Zig需要更多人工 proof。

---

# 229. Operational Proof

```text
Does it meet latency/memory/backpressure/failure requirements?
```

任何语言都主要需要：

> architecture + measurement

完成。

---

# Part LXIX · The Four Graphs Expanded

我们在 G3 有四张图。

现在升级为六张。

---

# 230. Ownership Graph

```text
Who owns what?
```

---

# 231. Lifetime Graph

```text
Who must outlive whom?
```

---

# 232. Mutation Graph

```text
Who may write which state?
```

---

# 233. Storage / Cost Graph

```text
Where are allocations, copies, indirections?
```

---

# 234. Synchronization Graph

```text
Where are HB / locks / queues?
```

---

# 235. Binary Boundary Graph

```text
Which components are independently built/versioned?
```

如果这六张图清晰：

> 大多数 systems architecture已经清晰了一半。

---

# Part LXX · C++ Revisited After the Whole Track

# 236. 现在重新看一个简单 Class

```cpp
class Buffer {
public:
    explicit Buffer(std::size_t size);

    std::span<std::byte> bytes();

private:
    std::vector<std::byte> storage_;
};
```

初学者看到：

```text
class
vector
span
```

现在应该看到：

```text
Buffer
→ owner

vector
→ dynamic contiguous storage owner

span
→ non-owning mutable borrow

Buffer move?
→ transfers vector storage ownership

bytes() lifetime
→ <= Buffer storage validity

vector growth
→ invalidates old span

allocation
→ hidden behind vector

ABI
→ vector representation private if class hidden/PImpl boundary

concurrency
→ mutable span requires mutation authority
```

这就是整个 Track 的成果。

---

# Part LXXI · Rust Revisited With C++ Knowledge

# 237. 看

```rust
fn process(
    input: &[u8],
    output: &mut [f32],
) -> Result<usize, Error>
```

现在你能立即映射：

```text
input
→ borrowed immutable span

output
→ exclusive mutable borrowed span

Result
→ explicit error-as-value

usize
→ target-native size type

borrow checker
→ statically constrains alias/lifetime
```

机器世界仍是：

```text
pointer
length
loads
stores
```

Rust type system只是提供更强 proof。

---

# Part LXXII · Zig Revisited With C++ Knowledge

# 238. 看

```zig
fn decode(
    allocator: std.mem.Allocator,
    input: []const u8,
) ![]f32
```

现在你应该看到：

```text
allocator
→ explicit dynamic storage capability

input
→ borrowed immutable slice

![]f32
→ error union containing owned? slice result
```

然后立刻追问：

> 谁负责 free 返回 slice？

因为：

```text
[]f32
```

本身不像 C++ `vector` / Rust `Vec`：

> 自动携带 owning destructor。

这就是 ownership contract必须额外明确的地方。

---

# Part LXXIII · A Better Zig API

可以用 owner type：

```zig
const ResultBuffer = struct {
    allocator: std.mem.Allocator,
    data: []f32,

    pub fn deinit(self: *ResultBuffer) void {
        self.allocator.free(self.data);
    }
};
```

然后：

```zig
fn decode(...) !ResultBuffer;
```

这开始接近：

```text
C++ RAII owner
```

但 cleanup仍需要 caller：

```zig
var result = try decode(...);
defer result.deinit();
```

所以：

> type carries cleanup capability，scope executes it explicitly。

很 Zig。

---

# Part LXXIV · API Design Comparison

需求：

> processing function borrows input and returns owned output。

### C++

```cpp
std::expected<std::vector<float>, Error>
decode(std::span<const std::byte> input);
```

### Rust

```rust
fn decode(
    input: &[u8],
) -> Result<Vec<f32>, Error>;
```

### Zig

```zig
fn decode(
    allocator: Allocator,
    input: []const u8,
) ![]f32;
```

三个 API机器语义可以非常接近。

区别：

```text
C++
owner cleanup through destructor

Rust
owner cleanup through Drop

Zig
allocator + caller cleanup protocol
```

---

# Part LXXV · Thread-safe Shared Config

需求：

```text
rare update
many readers
immutable generation
```

### C++

```cpp
std::atomic<
    std::shared_ptr<const Config>>
current;
```

---

### Rust

概念上：

```text
Arc<Config>
+
atomic/synchronization mechanism for swapping generation
```

---

### Zig

需要显式设计：

```text
generation pointer
ownership/reclamation
mutex/atomic
allocator
```

---

# 239. 关键点

虽然 Rust/C++有成熟 owner types，

最终架构仍然相同：

```text
build new generation privately
↓
publish
↓
old readers finish
↓
reclaim old generation
```

这是语言无关的。

---

# Part LXXVI · Bounded Runtime Comparison

需求：

```text
Producer
↓
bounded queue
↓
N workers
```

---

# 240. C++

使用：

```text
jthread
mutex/CV
move-only task
RAII
```

---

# 241. Rust

可以使用：

```text
threads/channels
ownership transfer
Result
Send/Sync
```

Compiler能帮助保证更多 task ownership约束。

---

# 242. Zig

需要更显式设计：

```text
threads
queue
allocator
shutdown state
cleanup
```

API机制更低层。

---

# 243. 但核心 invariants相同

```text
accepted work has outcome
queue bounded
no UAF
shutdown wakes waiters
threads join before state destroy
```

这就是为什么 G10知识能完全迁移。

---

# Part LXXVII · Robotics Comparison

# 244. Controller Core

三个语言都可以实现：

```text
fixed-size math
bounded memory
single writer
periodic execution
```

---

# 245. C++ 的现实优势

当前机器人 native生态：

```text
ROS
Eigen
hardware SDKs
existing code
```

是非常强的 network effect。

---

# 246. Rust 的理论/工程优势

```text
strong memory safety
safer state ownership
```

对未来机器人 infrastructure具有明显吸引力。

---

# 247. Zig 的潜在位置

```text
device interface
embedded support
protocol/parser
C SDK wrapping
```

尤其适合显式 resource constrained components。

---

# Part LXXVIII · How to Choose a Language

# 248. Scorecard 不应只看语言

对 subsystem逐项问：

| Dimension     | Question                      |
| ------------- | ----------------------------- |
| Ecosystem     | 必须使用哪些 libraries/SDK？  |
| Safety        | memory-safety风险有多大？     |
| ABI           | 需要跟什么语言/二进制互操作？ |
| Performance   | 真正瓶颈是什么？              |
| Timing        | 有 deadline/jitter吗？        |
| Ownership     | state/lifetime有多复杂？      |
| Allocation    | allocator policy是否核心？    |
| Concurrency   | shared-state复杂度如何？      |
| Tooling       | debugging/build/deploy如何？  |
| Team          | 谁维护 5 年？                 |
| Certification | 有行业要求吗？                |
| Evolution     | binary/API寿命多长？          |

然后再选择。

---

# Part LXXIX · A Practical Default

对于你的目标：

```text
high-performance systems
infrastructure
robotics
```

一个非常现实的组合思路是：

```text
C++23
→ robotics / native high-performance core / vendor ecosystem

Rust
→ memory-safe infrastructure / services / concurrent backend

Zig
→ low-level explicit components / C-facing systems tools /
   specialized native utilities
```

但这不是固定“分工表”。

真正项目仍然从约束出发。

---

# Part LXXX · What C++ Taught Us About Rust/Zig

# 249. C++ 的复杂性并不全是历史垃圾

例如：

```text
value category
move
RAII
object lifetime
ABI
```

虽然 C++表达很复杂，

它们背后很多问题：

> 本身是真实 systems problems。

学习 C++后再看 Rust/Zig，

你更容易区分：

```text
language complexity
```

和：

```text
machine/system complexity
```

---

# 250. Rust 消除了哪些“偶然复杂性”？

例如大量：

```text
manual owner/borrow discipline
```

进入 compiler。

但：

```text
ownership itself
```

没有消失。

只是表达不同。

---

# 251. Zig 消除了哪些“偶然复杂性”？

例如：

```text
constructor/destructor overload machinery
exceptions
complex template grammar
```

大幅简化。

但：

```text
resource lifetime
error propagation
generic specialization
```

仍然存在。

变成更显式机制。

---

# Part LXXXI · What Rust Teaches C++ Design

# 252. Make Ownership Visible

C++ API尽量：

```text
unique_ptr
value
span
string_view
```

而不是所有东西：

```cpp
T*
```

---

# 253. Minimize Shared Mutable Aliasing

Rust borrow model提供一个极好的 architecture intuition：

> mutable access越独占，系统越简单。

即使 C++ compiler不强制，

我们也可以主动设计：

```text
single writer
explicit borrow
short mutable scope
```

---

# 254. Model States as Types

用：

```cpp
variant
enum class
expected
```

减少：

```text
boolean soup
invalid combinations
```

---

# Part LXXXII · What Zig Teaches C++ Design

# 255. Make Allocation Visible

C++可以主动问：

```text
Does this API allocate?
Who chooses allocator?
Can caller reuse storage?
```

而不是把所有 allocation当 implementation detail。

---

# 256. Prefer Explicit Mechanisms at Low-level Boundaries

尤其：

```text
buffer
allocator
error
ABI
```

低层 systems API显式往往比魔法更可维护。

---

# 257. Separate Mechanism From Policy

Zig经常鼓励：

```text
allocator passed in
```

调用者选择 policy。

C++也可以通过：

```text
span
pmr
policy objects
explicit owner
```

实现类似架构。

---

# Part LXXXIII · What C++ Teaches Rust/Zig Engineers

# 258. ABI Matters

Language-native elegance一旦跨：

```text
shared library
plugin
FFI
```

都会遇到：

```text
layout
calling convention
versioning
ownership
```

---

# 259. Value Representation Matters

Type系统再漂亮，

最终：

```text
sizeof
alignment
cache line
```

仍决定机器成本。

---

# 260. Destruction Order Matters

即使语言帮你管理资源，

复杂 owner graph：

> 谁先结束 lifetime

仍然是 architecture。

---

# Part LXXXIV · Final Unified Mental Model

面对任何 systems object：

```text
Buffer
Connection
Job
RobotState
Decoder
Queue
```

问 12 个问题。

---

# 261. What Is It?

```text
logical value?
resource?
handle?
view?
```

---

# 262. Where Does It Live?

```text
stack?
heap?
pool?
static?
external memory?
```

---

# 263. Who Owns It?

```text
one owner?
shared?
external?
```

---

# 264. Who Borrows It?

```text
read-only?
mutable?
how long?
```

---

# 265. When Does Lifetime End?

---

# 266. What Invalidates Existing Access Paths?

---

# 267. How Expensive Is Copy/Move?

---

# 268. Where Does Allocation Happen?

---

# 269. Who May Mutate?

---

# 270. How Is Cross-thread Ordering Established?

---

# 271. What Crosses the ABI Boundary?

---

# 272. What Are the Timing Requirements?

如果你能对这十二个问题给出准确答案：

> 语言本身已经只是实现工具。

这就是整个 Track 最终希望达到的状态。

---

# Part LXXXV · Final Anti-patterns

# 273. “Rust 所以不用想 Lifetime”

错。

Compiler帮你想很多，但 architecture仍然决定 lifetime topology。

---

# 274. “Zig 所以没有隐藏成本”

错。

OS、allocator、cache、library implementation仍可能隐藏复杂成本。

---

# 275. “C++ 所以必须手动管理内存”

错。

现代 C++ 默认应依赖：

```text
value
RAII
containers
smart owners
```

而不是裸 `new/delete`。

---

# 276. “Rust 一定比 C++ 慢/快”

没有意义。

比较具体 implementation/workload。

---

# 277. “Zig 是现代 C，所以不需要抽象”

优秀 systems code依然需要：

```text
module
ownership convention
state machine
architecture
```

---

# 278. “跨语言可以选每层最强语言，所以一定更好”

integration cost真实存在。

---

# Part LXXXVI · G12 Final Twenty Axioms

如果整个 Modern C++ Systems Track 最后只能保留二十条：

1. **Object、storage、value、type 和 lifetime 是不同概念；任何 systems language 最终都必须处理它们。**

2. **Ownership 的本质是“谁负责保证资源一直有效并最终结束其 lifetime”，而不是某个特定 smart pointer。**

3. **Borrowing 的本质是临时获得访问能力而不接管 lifetime；Rust 静态证明更多，C++/Zig更多依赖 contract。**

4. **C++ move 是 value-category/overload驱动的资源转移机制；Rust move 是语言级 ownership transfer；Zig没有对应的 ownership-move状态机。**

5. **RAII、Rust `Drop` 和 Zig `defer` 都服务 deterministic cleanup，但分别偏向 type-driven 与 scope-driven cleanup。**

6. **Explicit allocator、hidden allocator 和 global allocator只是 API设计不同；机器最终仍然执行真实 storage management。**

7. **Error representation不能自动保证 state rollback；`prepare → commit` 是跨语言的 failure-safety原则。**

8. **Templates、Rust generics 和 Zig comptime最终都可能通过 specialization换 runtime work，同时付 compile-time/code-size成本。**

9. **Container/layout性能由连续性、allocation、indirection、access pattern和working set决定，而不是语言名字。**

10. **Memory safety、logical correctness、concurrency correctness、real-time correctness和physical safety是五个不同维度。**

11. **Rust能静态排除大量 memory/lifetime/data-race错误，但不能自动证明 deadlock、backpressure、deadline或业务 invariant。**

12. **Zig让 allocation、cleanup、error和compile-time机制高度显式，但显式本身不是 correctness proof。**

13. **C++提供最大的 native生态、representation自由和兼容能力，同时要求最强的 lifetime/alias/concurrency工程纪律。**

14. **Single-writer、sharding、immutable snapshot和ownership transfer通常比更聪明的 atomics更有价值。**

15. **Lock-free是 progress property，不是语言特性，也不是性能排名。**

16. **C++、Rust、Zig都应把长期跨语言 binary boundary尽量缩小到显式、versioned、ownership-clear的 C ABI。**

17. **Build system、ABI、allocator和toolchain都是系统架构的一部分，而不是实现完成后的附属工具。**

18. **Real-time来自 bounded execution和完整硬件/OS architecture，而不是“没有GC”、Rust safety或Zig explicitness。**

19. **性能工程必须 Measure → Explain → Change → Measure Again；任何语言都不能取消这个证据要求。**

20. **语言选择的核心不是“谁最好”，而是：系统有哪些 constraints，以及你希望哪些 proof obligations交给 compiler、type system、library、architecture和工程团队。**

---

# Part LXXXVII · G12 Final Gate

现在应该能闭卷回答。

## Object / Lifetime

1. C++、Rust、Zig 在 lifetime proof responsibility 上最大的区别是什么？
2. 为什么 Zig `defer` 和 C++ RAII不是完全同一种 abstraction？
3. 为什么 Rust borrow checker并没有消除 lifetime这个系统问题？

## Ownership

1. C++ `unique_ptr`、Rust ownership 与 Zig手动 ownership convention 有什么根本差别？
2. Rust move 和 C++ move为什么不能简单翻译成同一概念？
3. 为什么 Zig resource struct普通复制可能需要特别谨慎？

## Borrowing

1. `span<const T>`、`&[T]`、`[]const T` 机器层可能很接近，为什么语言保证却差异巨大？
2. Rust `&mut T` 对 aliasing表达了什么重要思想？

## Allocation

1. Zig allocator-as-parameter 的架构价值是什么？
2. 为什么 allocator显式不自动意味着更高性能？
3. C++/Rust隐藏 allocator有什么 API优势和可观测性代价？

## Error

 1. `expected<T,E>`、`Result<T,E>` 和 Zig error union 的共同系统模型是什么？
 2. 为什么 error-as-value 不能自动提供 strong transactional guarantee？

## Genericity

 1. C++ template、Rust generic、Zig comptime 最终有什么共同机器 trade-off？
 2. 为什么更多 compile-time specialization可能伤 I-cache？

## Concurrency

 1. Rust safe code解决了哪些 C++ concurrency错误？
 2. 为什么 Rust仍然需要理解 acquire/release 和 CAS？
 3. 为什么 single-writer是三门语言共同的重要架构原则？

## ABI

 1. 为什么三门语言之间最稳健的长期 ABI仍然通常是 C ABI？
 2. Rust的安全 guarantees为什么不能自动穿过 FFI？
 3. 为什么 ownership/thread-safety必须写进 ABI contract？

## Build

 1. Cargo、Zig Build、CMake最大的生态模型差异是什么？
 2. 为什么它们底层都仍然可以理解成 artifact graph？

## Real-Time

 1. 为什么 C++、Rust、Zig都不能自动保证 real-time？
 2. 为什么没有 GC不是 sufficient condition？

## Architecture

 1. 什么时候应该选择 C++？
 2. 什么时候 Rust的 static guarantees价值尤其高？
 3. 什么类型的问题特别适合 Zig的显式 allocator/C interop/comptime模型？
 4. 多语言系统的真正成本是什么？
 5. 为什么 language choice 应该是 systems-design procedure 的后半部分，而不是第一步？

---

# Part LXXXVIII · 整个 Track 的最终闭环

现在可以把 G0–G12 压成十三个问题：

```text
G0
程序怎样变成机器可执行物？

G1
一个 object 何时合法存在？

G2
谁负责让资源活着并最终释放？

G3
value 怎样传递，代价是什么？

G4
数据怎样组织、遍历和抽象？

G5
哪些变化应在 compile time 决定？

G6
representation 怎样影响 CPU / memory？

G7
多个执行者怎样合法共享和修改 state？

G8
独立 binary components 怎样互相理解？

G9
这些 artifacts 怎样被可靠地构建和分发？

G10
怎样把这些机制组合成真实 runtime？

G11
当软件进入物理世界和 deadline 后会发生什么？

G12
哪些问题属于语言，哪些问题属于系统本身？
```

最后一问才是整个路线最重要的：

> **哪些复杂性是 C++ 的历史复杂性，哪些复杂性是任何高性能系统都必须面对的真实复杂性？**

现在我们已经能够比较清楚地区分：

```text
C++ value categories
→ largely language-specific machinery

but

ownership transfer
→ real systems problem

C++ allocator syntax
→ language/library-specific

but

allocation topology
→ real systems problem

C++ memory_order API
→ language-specific interface

but

cross-core synchronization
→ real systems problem

CMake
→ ecosystem-specific tool

but

artifact dependency graph
→ real systems problem
```

这就是这条学习路线真正的终点。

---

# Modern C++ Systems Track · Final Status

```text
G0   Native Toolchain & Machine Boundary       COMPLETE
G1   Object Model                              COMPLETE
G2   RAII & Ownership                         COMPLETE
G3   Value Semantics / Copy / Move            COMPLETE
G4   STL & Abstraction                        COMPLETE
G5   Generic Programming                      COMPLETE
G6   Memory & Performance                     COMPLETE
G7   Concurrency & Memory Model               COMPLETE
G8   ABI / Libraries / C Interop              COMPLETE
G9   Build & Native Ecosystem                 COMPLETE
G10  Systems Runtime Project                  ARCHITECTURE COMPLETE
G11  Robotics Systems                         COMPLETE
G12  C++ × Zig × Rust Unified Systems Model   COMPLETE
────────────────────────────────────────────────────────
      MODERN C++ SYSTEMS TRACK                COMPLETE
```

从知识结构上，整条 **Modern C++ Systems Track 已经闭环**。

接下来最有价值的工作已经不再是继续增加 `G13/G14`，而是把其中需要真正形成肌肉记忆的部分变成**代码实践**：

```text
G10 runtime
        ↓
实际实现

        ↓
sanitizers / stress

        ↓
profiling

        ↓
profile-driven refactoring

        ↓
G11 robot-control-core

        ↓
真实 C++23 systems engineering
```

也就是说，从这里开始，学习方式应该从：

> **“继续学习更多 C++ 知识”**

正式转为：

> **“用真实项目不断迫使 G0–G12 的模型发生冲突，然后解决这些冲突。”**

这才是下一阶段真正提升 C++ 系统工程能力的主线。
