# C++ Systems Track · G8 ABI / Libraries / C Interop

**Version:** 1.0  
**Status:** Complete / Frozen Review Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0–G7  
**Scope:** API / ABI / Linkage / Name Mangling / Calling Convention / Object Layout / VTable / RTTI / Exceptions / Symbol Visibility / Static & Shared Libraries / Versioning / PImpl / C ABI / Opaque Handle / Allocator Boundary / Callbacks / Plugins / Rust & Zig FFI  
**Purpose:** 建立从 **C++ source-level interface** 到 **binary component boundary** 的完整模型，并学会设计能够长期演进、跨编译器/语言使用的 native library interface。

---

# 0. G8 的定位

到 G7 为止，我们已经能够回答：

```text
G1
这个 object 是否存在、能否合法访问？

G2
谁拥有它、什么时候销毁？

G3
它怎样 copy / move，成本是什么？

G4
怎样用 container / view / algorithm 表达数据结构？

G5
哪些差异属于 compile-time specialization？

G6
representation 怎样影响机器性能？

G7
多个线程怎样合法访问和修改状态？
```

G8 增加一个新的问题：

> **如果代码不再处于同一个 compilation universe 中，而是跨越 `.o`、`.a`、`.so`、`.dylib`、插件、语言甚至编译器边界，会发生什么？**

统一链路：

```text
Source Code
    ↓
Declaration
    ↓
Compiler-specific type/function representation
    ↓
Symbol
    ↓
Calling Convention
    ↓
Object Layout
    ↓
ABI
    ↓
Linker / Loader
    ↓
Binary Component
```

最重要的思想：

> **Source compatibility 和 binary compatibility 是两个不同问题。**

---

# Part I · API 与 ABI

# 1. API 是什么？

> **API — Application Programming Interface**

是 source level contract。

例如：

```cpp
class Decoder {
public:
    void decode(
        std::span<const std::byte> input,
        std::span<float> output);
};
```

API 描述：

```text
type names
function names
parameter types
return types
semantics
ownership expectations
exceptions
preconditions
```

Caller 需要重新编译时，只要源码仍能通过：

> source API 可能仍然兼容。

---

# 2. ABI 是什么？

> **ABI — Application Binary Interface**

描述已经编译好的两个 binary components 怎样彼此理解。

至少涉及：

```text
symbol naming
calling convention
parameter passing
return-value convention
register usage
stack alignment
object layout
vtable layout
RTTI
exception unwinding
name mangling
standard-library ABI
data-model widths
alignment
```

所以：

```text
API
=
source contract

ABI
=
binary contract
```

---

# 3. 一个 Source-compatible 但 ABI-breaking 的例子

原版：

```cpp
struct Config {
    int mode;
};
```

Library v1 和 application 分别编译。

后来改为：

```cpp
struct Config {
    int mode;
    int flags;
};
```

Application 不重新编译。

新的 library 认为：

```text
sizeof(Config) = 8
```

旧 application 可能仍按：

```text
sizeof(Config) = 4
```

构造/传递。

源码上：

```cpp
Config config;
```

仍然完全合理。

但 binary contract 已经变了。

---

# 4. ABI Compatibility 的本质

如果两个 binary independently compile：

```text
Component A
Component B
```

双方必须对跨 boundary 的东西有一致理解：

```text
Function symbol
Parameter layout
Register assignment
Stack layout
Object representation
Ownership
Error mechanism
```

只要其中一个不一致：

> 源码看起来再合理也没有意义。

---

# Part II · Linkage 与 Symbol

# 5. 一个 Function 编译后必须成为 Symbol

例如：

```cpp
int add(int a, int b) {
    return a + b;
}
```

Compiler/assembler 会生成某种 symbol。

Linker最终解决：

```text
caller relocation
        ↓
which binary address is add?
```

这是 G0 中：

```text
symbol table
relocation
linker
```

的继续。

---

# 6. C++ 为什么不能简单把 Symbol 叫 `add`？

因为 C++ 支持 overload：

```cpp
int add(int, int);
double add(double, double);
```

如果两个都只生成：

```text
add
```

linker 无法区分。

所以需要：

> **Name Mangling — 名字改编**

概念：

```text
add(int,int)
→ encoded symbol A

add(double,double)
→ encoded symbol B
```

---

# 7. Mangled Name 编码什么？

实现通常需要编码足够的信息来区分：

```text
namespace
class
function name
parameter types
template arguments
cv/ref qualifiers
```

例如：

```cpp
namespace math {

int add(int, int);

}
```

binary symbol不会简单是：

```text
add
```

---

# 8. Name Mangling 不是 C++ 标准统一的 Binary Format

C++ 标准主要规定：

> 语言语义。

它并不定义一个跨所有 compiler/platform 统一的：

```text
C++ symbol mangling ABI
```

因此：

```text
Compiler A
Compiler B
```

即使都实现 C++23，

也不自动意味着：

> 任意 C++ binary ABI 可以互操作。

某些平台生态确实共享特定 ABI conventions，但这是平台/compiler ABI 层面的约定。

---

# Part III · Language Linkage 与 `extern "C"`

# 9. `extern "C"`

```cpp
extern "C" int decoder_create();
```

核心意义：

> 使用 C language linkage。

最常见效果之一：

> 避免 C++ overload-style name mangling，使 symbol 能按照 C ABI 方式暴露。

例如：

```cpp
extern "C" int add(int a, int b);
```

symbol 可以对应：

```text
add
```

而不是 C++ mangled name。

---

# 10. `extern "C"` 不会把 C++ Function “变成 C”

例如：

```cpp
extern "C" std::string foo();
```

从语言上某些实现环境也许允许你声明出各种形式，

但：

> 这不意味着 `std::string` 突然获得稳定 C ABI。

`extern "C"` 主要影响：

```text
language linkage / symbol conventions
```

它不会自动解决：

```text
std::string layout
allocator compatibility
exception ABI
lifetime
```

---

# 11. C ABI 为什么如此重要？

因为 C ABI 相对简单：

```text
primitive scalars
pointers
plain structs
function pointers
explicit ownership
```

而且大量语言都能调用 C：

```text
C++
Rust
Zig
Python native layer
Go cgo
Swift
...
```

所以 native systems 中常见：

> **内部用 C++，稳定外部边界用 C ABI。**

---

# Part IV · Calling Convention

# 12. Function Call 不是抽象魔法

源码：

```cpp
int f(int a, int b);
```

binary双方必须约定：

```text
a 放哪里？
b 放哪里？
return value 放哪里？
谁保存哪些 registers？
stack 怎样对齐？
```

这就是：

> **Calling Convention**

---

# 13. 参数可能放在哪里？

依据 target ABI，参数可能进入：

```text
general-purpose registers
floating-point/vector registers
stack
indirect memory
```

例如小 scalar：

```cpp
int
pointer
float
```

通常很适合 registers。

大 aggregate：

```cpp
LargeStruct
```

可能：

```text
split across registers
passed indirectly
copied into caller-provided storage
```

具体属于 ABI。

---

# 14. Return Value 也有 ABI

```cpp
int f();
```

一般很容易。

但：

```cpp
HugeObject make();
```

binary-level implementation 可能等价于：

```text
caller allocates result storage
↓
passes hidden pointer
↓
callee constructs result there
```

这常被称为类似：

> **sret — structure return**

机制。

注意：

> 这是 ABI lowering。

它和 C++ source-level：

```text
RVO / guaranteed copy elision
```

相关，但不是同一个概念。

---

# 15. Hidden Parameters

成员函数：

```cpp
class A {
public:
    void f(int x);
};
```

机器层通常还需要：

```text
this pointer
```

也就是类似：

```cpp
f(A* this, int x);
```

但这是 conceptual lowering，不是 C++ source signature。

Virtual dispatch 又可能需要通过 object representation 找到 target。

---

# Part V · Data Model

# 16. `int`、`long`、Pointer 宽度不是语言里全部固定死的

不同 ABI/data model 可能定义：

```text
sizeof(int)
sizeof(long)
sizeof(void*)
```

不同关系。

常见 data models包括：

```text
LP64
LLP64
```

等。

所以 wire ABI 不应随便假设：

```cpp
long
```

永远 64-bit。

---

# 17. Boundary 上优先 Fixed-width Types

例如：

```cpp
std::uint32_t
std::int64_t
```

比：

```cpp
unsigned long
```

更容易表达 binary intent。

但也要注意：

> fixed-width integer只解决数值宽度，不自动解决 alignment、endianness、packing、semantic versioning。

---

# 18. `size_t` 也不是 Portable Wire Type

```cpp
std::size_t
```

非常适合：

> 当前 process 的 object size/index。

但它的宽度属于 target data model。

所以持久格式/跨架构 protocol 不应该因为方便就直接定义成：

```cpp
size_t count;
```

更适合选择明确宽度。

---

# Part VI · Object Layout 与 ABI

# 19. C++ Object 跨 ABI Boundary 是高风险区域

例如：

```cpp
class Decoder {
private:
    int mode_;
    std::vector<float> buffer_;
};
```

如果 object 跨 shared-library boundary：

双方必须一致理解：

```text
member offsets
alignment
sizeof
base classes
vptr
padding
stdlib representation
```

这些都可能形成 ABI coupling。

---

# 20. 改 Private Member 也可能 Break ABI

这是 C++ ABI 最容易让人惊讶的一点。

API：

```cpp
class Foo {
public:
    void run();

private:
    int x_;
};
```

改成：

```cpp
private:
    int x_;
    int y_;
```

对 caller 源码：

```text
完全不影响 public API
```

但如果 caller 需要：

```cpp
Foo foo;
```

它在编译时必须知道：

```text
sizeof(Foo)
alignment
```

所以：

> private representation 仍然进入 ABI。

---

# 21. 为什么 PImpl 存在？

> **PImpl — Pointer to Implementation**

例如：

```cpp
class Decoder {
public:
    Decoder();
    ~Decoder();

    Decoder(Decoder&&) noexcept;
    Decoder& operator=(Decoder&&) noexcept;

    void decode();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};
```

Header中：

```text
Decoder
≈
one pointer-like representation
```

真实 implementation：

```cpp
class Decoder::Impl {
    std::vector<float> buffer_;
    Config config_;
    ...
};
```

藏在 `.cpp`。

---

# 22. PImpl 的主要价值

### ABI Stability

增加：

```cpp
Impl::new_member_
```

不改变 public `Decoder` object layout。

### Compile-time Isolation

caller header 不需要知道所有 implementation types。

### Dependency Firewall

减少 header dependency传播。

---

# 23. PImpl 的代价

```text
heap allocation
pointer indirection
out-of-line calls
more boilerplate
less optimization visibility
```

所以：

> PImpl 不是“高级 C++ 默认模式”。

它是一种：

> **ABI / dependency boundary tool。**

---

# Part VII · Standard-layout / Trivial / POD

# 24. “POD” 已经不是现代 C++ 最好的思维单位

历史 C++ 常讲：

> POD — Plain Old Data。

现代语言更精确拆成：

```text
standard-layout
trivially copyable
trivial special members
implicit-lifetime related properties
```

不同 property 服务不同问题。

---

# 25. `trivially_copyable`

表示：

> 对这类 object representation 的 byte-level copy 有特定语言保证。

这对：

```text
memcpy
binary relocation-like operations
```

非常重要。

但仍然：

```text
trivially copyable
≠
portable serialized format
```

---

# 26. `standard-layout`

它主要约束：

> object/member layout 具有较规则的语言保证。

与：

```text
C-compatible-like layout reasoning
offsetof
```

等相关。

但：

> `standard-layout` 也不等于跨所有 compiler/architecture 的永恒 ABI。

---

# Part VIII · Inheritance 与 ABI

# 27. Inheritance 会让 Object Layout 更复杂

例如：

```cpp
class Base {
public:
    virtual void f();
};

class Derived : public Base {
    int x_;
};
```

可能涉及：

```text
base subobject
vptr
derived members
padding
```

多个 inheritance：

```text
multiple inheritance
virtual inheritance
```

进一步复杂。

---

# 28. Virtual Function 一般需要 Runtime Dispatch Metadata

典型 ABI implementation：

```text
object
┌────────────┐
│ vptr ─────────▶ vtable
│ members    │
└────────────┘
```

调用：

```cpp
base->f();
```

可能：

```text
load vptr
↓
load function pointer from vtable
↓
indirect call
```

G6 已经从性能角度看过。

现在 G8 关心：

> vtable layout 本身属于 ABI。

---

# 29. 增加/重排 Virtual Functions 可能 Break ABI

例如 v1：

```cpp
virtual void a();
virtual void b();
```

调用者可能按某个 vtable slot contract 调用。

如果 v2：

```cpp
virtual void x();
virtual void a();
virtual void b();
```

binary slot layout可能改变。

所以：

> public polymorphic class 是一个很强的 ABI commitment。

---

# 30. Base Class Layout 变化也可能传播

如果：

```cpp
Base
```

增加 data member，

Derived layout也可能改变。

所以 inheritance-rich public library API：

> ABI evolution 成本通常很高。

---

# Part IX · RTTI

# 31. RTTI

C++ runtime type information 支持：

```cpp
dynamic_cast
typeid
```

通常依赖：

```text
type metadata
vtable-related structures
runtime type descriptors
```

这些同样属于 compiler/runtime ABI ecosystem。

---

# 32. RTTI 跨 Binary Boundary 需要一致 Runtime Universe

如果：

```text
plugin
host
```

分别由不兼容 runtime/compiler options构建，

可能在：

```text
type identity
dynamic_cast
type_info comparison
```

上出现问题。

因此 plugin boundary 最稳健的设计通常不会把：

> arbitrary C++ RTTI assumptions

作为核心协议。

---

# Part X · Exceptions Across ABI Boundary

# 33. Exception 不只是一个 C++ Object

```cpp
throw Error{};
```

跨 function calls 传播需要：

```text
exception object allocation/storage
unwind metadata
stack unwinding
personality routines
RTTI/type matching
destructor execution
runtime library support
```

所以 exception system 深度依赖：

> compiler/runtime ABI。

---

# 34. 不要让 C++ Exception 穿过 C ABI

例如：

```cpp
extern "C"
int decoder_run(...) {
    throw std::runtime_error{"bad"};
}
```

然后 exception 穿出到 C caller：

> 这是完全错误的 interface design。

C caller 没有 C++ exception semantics。

所以 C ABI boundary 必须捕获：

```cpp
extern "C"
int decoder_run(...) noexcept {
    try {
        // C++ implementation
        return DECODER_OK;
    } catch (...) {
        return DECODER_INTERNAL_ERROR;
    }
}
```

---

# 35. Public Binary Library 是否应该让 Exception 穿过去？

如果整个 ecosystem：

```text
same compiler family
same runtime ABI
same build control
```

有时可以。

但这形成非常强 coupling。

如果目标是：

```text
stable SDK
plugins
cross-language FFI
long-lived binary compatibility
```

更稳健：

> **exception stops at boundary。**

---

# 36. `noexcept` 作为 Boundary Contract

例如：

```cpp
extern "C"
decoder_status decoder_process(...) noexcept;
```

很好地表达：

> C++ exception 不得逃逸。

内部：

```text
exception
↓
catch
↓
error code
```

转换为 boundary error model。

---

# Part XI · Allocator Boundary

# 37. 谁 Allocate，谁 Free？

这是 binary library 最重要的 ownership rule 之一。

错误：

Library：

```cpp
char* library_create_string();
```

Caller：

```cpp
std::free(ptr);
```

如果 library 使用：

```text
different allocator
different runtime
custom arena
```

则完全可能错误。

---

# 38. Robust Rule

> **Memory should normally be released by the same allocation domain that created it.**

例如：

```c
decoder_buffer* decoder_buffer_create(...);
void decoder_buffer_destroy(decoder_buffer*);
```

或者：

```c
char* decoder_make_string(...);
void decoder_free_string(char*);
```

明确把 deallocation交回 library。

---

# 39. 更好的方式：Caller Provides Buffer

对于高性能接口：

```c
decoder_status decoder_process(
    decoder_handle* handle,
    const uint8_t* input,
    size_t input_len,
    float* output,
    size_t output_capacity,
    size_t* output_count);
```

这里：

```text
caller owns input
caller owns output
library borrows
```

没有：

```text
cross-library allocation ownership
```

非常清楚。

---

# 40. Caller-provided Allocator

某些 C ABI 还会定义：

```c
typedef void* (*alloc_fn)(
    void* context,
    size_t size,
    size_t alignment);

typedef void (*free_fn)(
    void* context,
    void* ptr,
    size_t size,
    size_t alignment);
```

然后 library 使用 caller allocator。

适合：

```text
embedded
games
real-time systems
allocator governance
```

但 ABI contract显著变复杂。

---

# Part XII · STL Across Binary Boundaries

# 41. 为什么 `std::vector<T>` 是强 ABI Coupling？

假设：

```cpp
API_EXPORT
std::vector<Record> get_records();
```

这把 boundary 与以下东西耦合：

```text
std::vector representation
allocator model
standard library ABI
exception behavior
template instantiation
Record ABI
compiler flags
```

因此长期稳定 SDK：

> 通常避免在 public C ABI 中暴露 STL types。

---

# 42. `std::string` 同样如此

```cpp
std::string name();
```

在“整个工程完全统一 toolchain”的内部 library 中可能没有问题。

但对：

```text
plugins
third-party SDK
cross-language
long-lived ABI
```

它通常不是最稳健 contract。

---

# 43. `std::span` 是不是就稳定？

源码层它非常优秀。

但：

```cpp
std::span<const std::byte>
```

仍然是一个 C++ library type。

如果目标是稳定 C ABI，

应该展开：

```c
const uint8_t* data,
size_t length
```

而不是直接向 C boundary暴露 `std::span`。

---

# 44. Source API 与 C ABI 可以同时优秀

C++ wrapper：

```cpp
class Decoder {
public:
    DecodeResult decode(
        std::span<const std::byte> input,
        std::span<float> output);
};
```

底层 C ABI：

```c
decoder_status decoder_process(
    decoder_handle*,
    const uint8_t* input,
    size_t input_len,
    float* output,
    size_t output_capacity,
    size_t* output_count);
```

C++ wrapper负责：

```text
span → pointer/length
status → expected/error
RAII → create/destroy
```

这是一种非常成熟的设计。

---

# Part XIII · Opaque Handle

# 45. C ABI 如何隐藏 C++ Object？

不要：

```c
struct decoder {
    ...
};
```

把内部 layout 暴露出去。

而是：

```c
typedef struct decoder decoder;
```

只做 forward declaration。

Caller 只能持：

```c
decoder* handle;
```

不知道内部 layout。

这就是：

> **Opaque Handle — 不透明句柄**

---

# 46. Create / Destroy

```c
decoder* decoder_create(
    const decoder_config* config);

void decoder_destroy(
    decoder* handle);
```

C++ implementation：

```cpp
struct decoder {
    Decoder impl;
};
```

或者 handle直接 reinterpret 到内部私有 implementation，取决于设计。

外部 C code完全不需要知道。

---

# 47. 为什么 Opaque Handle 很强？

内部可以从：

```text
vector
```

改成：

```text
flat_map
arena
thread pool
PImpl-like implementation
```

而：

```text
sizeof(decoder)
```

对 caller根本不存在。

因此 public ABI 没有被内部 representation绑死。

---

# 48. Handle Pointer 是不是 Ownership？

API必须明确。

例如：

```c
decoder* decoder_create();
void decoder_destroy(decoder*);
```

自然表达：

```text
create
→ caller owns handle

destroy
→ relinquish ownership
```

而：

```c
const decoder* decoder_get_global();
```

可能是 borrowed。

不能只靠：

```text
pointer syntax
```

猜 ownership。

C ABI 文档必须明确。

---

# Part XIV · C Struct ABI

# 49. C Struct 可以跨 ABI，但仍需严格版本设计

例如：

```c
typedef struct decoder_config {
    uint32_t mode;
    uint32_t flags;
} decoder_config;
```

这比 C++ class简单得多。

但修改：

```c
add field
```

仍然可能改变：

```text
sizeof
offsets
alignment
```

所以 ABI versioning仍需设计。

---

# 50. Size-prefixed Struct

一种常见策略：

```c
typedef struct decoder_config {
    uint32_t struct_size;
    uint32_t api_version;

    uint32_t mode;
    uint32_t flags;
} decoder_config;
```

Caller：

```c
config.struct_size = sizeof(config);
```

Library可以判断：

> Caller认识的 struct 版本有多大。

---

# 51. Append-only Evolution

如果必须扩展 ABI struct，

一种较稳健约束是：

```text
existing fields never reorder
existing field meanings never change
new optional fields append at end
```

配合：

```text
struct_size
```

支持旧 caller。

但：

> 是否真的安全还取决于所有 ABI/platform assumptions。

---

# 52. Reserved Fields

有些 long-lived ABI 预留：

```c
void* reserved[4];
```

或：

```c
uint64_t reserved[8];
```

为未来扩展留空间。

代价：

```text
larger structs
less elegant API
```

它是一种 ABI budget。

---

# Part XV · Enum ABI

# 53. C++ `enum class` 在内部非常好

```cpp
enum class Error {
    None,
    InvalidInput,
    Internal,
};
```

但 boundary 上最好显式 underlying type：

```cpp
enum class Error : std::uint32_t {
    None = 0,
    InvalidInput = 1,
    Internal = 2,
};
```

对于 C ABI 则更常见：

```c
typedef uint32_t decoder_status;
```

配 constants：

```c
#define DECODER_OK 0u
#define DECODER_INVALID_INPUT 1u
```

或 C enum，视 ABI/profile要求。

---

# 54. 不要随便重用 Enum 数值

ABI/API发布后：

```text
1 = INVALID_INPUT
```

下一版不要变成：

```text
1 = INTERNAL_ERROR
```

Binary protocol里的 numeric value：

> 本身就是 contract。

---

# 55. Unknown Enum Values

跨版本 caller/library可能遇到：

> 新版本增加的 enum case。

Consumer应该避免假设：

```cpp
switch (status) {
case A:
case B:
}
unreachable();
```

除非 ABI 明确保证 closed universe 且版本完全锁定。

稳定 ABI要考虑：

> forward compatibility。

---

# Part XVI · `bool`、`char`、Bit-field

# 56. Binary Boundary 不要过度依赖 C++ `bool`

内部：

```cpp
bool enabled;
```

非常好。

C ABI long-lived struct 中可以考虑：

```c
uint8_t enabled;
```

或明确 integer convention：

```text
0 = false
nonzero = true
```

降低跨语言 representation ambiguity。

---

# 57. Bit-field 不适合 Portable ABI

例如：

```cpp
struct Flags {
    unsigned a : 1;
    unsigned b : 3;
};
```

bit-field allocation/layout高度依赖 implementation/ABI。

不要把它直接当：

> portable protocol struct。

---

# Part XVII · Packing

# 58. `#pragma pack(1)` 不是“让 Struct 可以传网络”

例如：

```cpp
#pragma pack(push, 1)
struct Packet {
    std::uint8_t type;
    std::uint32_t length;
};
#pragma pack(pop)
```

它可能改变：

```text
member alignment
struct layout
```

但并没有解决：

```text
endianness
versioning
object lifetime
unaligned access
platform/compiler compatibility
```

---

# 59. Wire Format 应显式 Parse

更稳健：

```text
byte 0      → type
bytes 1..4  → little-endian length
```

代码：

```cpp
auto type = bytes[0];
auto length = decode_le_u32(bytes.subspan(1, 4));
```

而不是：

```cpp
auto* packet =
    reinterpret_cast<const Packet*>(bytes.data());
```

后者可能触碰：

```text
alignment
lifetime
strict aliasing
endianness
padding
```

等问题。

---

# Part XVIII · Endianness

# 60. ABI 与 Wire Format 是不同层

同一 process 的 C/C++ ABI 通常约定 native representation。

但网络/文件：

> 应明确 endianness。

例如：

```text
little endian
big endian
```

不能因为当前机器是某种 endian，就把 raw struct bytes永久写入文件当 portable format。

---

# 61. Stable Storage Format 应独立于 In-memory Layout

正确层次：

```text
Domain Object
    ↓ encode
Stable Wire/Storage Schema
    ↓ decode
Domain Object
```

不要：

```text
memcpy(struct)
↓
file
```

把 compiler ABI 当 storage schema。

---

# Part XIX · Symbol Visibility

# 62. Shared Library 不应该 Export 所有 Symbols

一个大型 C++ library可能有：

```text
10,000 internal functions
templates
helpers
RTTI
```

如果全部对外可见：

```text
dynamic symbol table ↑
load/link work ↑
accidental ABI surface ↑
name collisions ↑
interposition complexity ↑
```

所以：

> **Default Hidden, Explicit Export**

通常是优秀策略。

---

# 63. Export Macro

跨平台 library常有类似：

```cpp
#if defined(_WIN32)
#  if defined(MYLIB_BUILD)
#    define MYLIB_API __declspec(dllexport)
#  else
#    define MYLIB_API __declspec(dllimport)
#  endif
#else
#  define MYLIB_API __attribute__((visibility("default")))
#endif
```

然后：

```cpp
MYLIB_API
int decoder_create(...);
```

具体 G9 会处理 build-system配置。

G8 需要理解：

> export set = ABI surface。

---

# 64. ABI Surface 应尽量小

假设内部有：

```text
200 classes
1000 functions
```

但外部只需要：

```text
create
destroy
process
get_error
```

那 public ABI最好就是这四个。

小 ABI：

```text
easier versioning
easier testing
less accidental coupling
```

---

# Part XX · Static Library

# 65. `.a` / `.lib` 的本质

Static library通常是：

> object files 的 archive。

Linker在最终 executable/shared library 链接时：

```text
select needed object files
↓
copy/link code into final artifact
```

因此：

> Static library 本身通常不是 runtime-loaded component boundary。

---

# 66. Static Library 不等于没有 ABI

即使 static linking：

```text
library object file
+
application object files
```

仍然必须在 link-time binary contract上兼容：

```text
calling convention
symbol mangling
object layout
runtime options
```

只是所有东西最终被链接成一个 image。

---

# 67. Static Link 的一个优势

可以通过：

```text
LTO
whole-program optimization
```

进一步优化跨 translation-unit boundaries。

但：

> 是否可用、效果如何属于 toolchain/build配置。

G9 再深入。

---

# Part XXI · Shared Library

# 68. Shared Library

概念：

```text
Executable
   │
   ├── references Library A
   └── references Library B
```

Loader在 process启动/动态加载时：

```text
map shared library
resolve symbols
apply relocations/bindings
```

G0 已经学习过 loader。

G8 的重点：

> Shared library 创建真正的独立 binary evolution boundary。

---

# 69. Linux / macOS / Windows 名称不同

常见：

```text
ELF shared object  → .so
Mach-O dynamic lib → .dylib
Windows DLL        → .dll
```

底层格式和 loader机制不同。

但架构问题相同：

```text
What is exported?
How are symbols found?
What is ABI?
How are versions loaded?
```

---

# Part XXII · Dynamic Loading / Plugin

# 70. Plugin Architecture

典型：

```text
Host
 ↓
load plugin library
 ↓
find exported entry symbol
 ↓
obtain function table/interface
```

不要让 host：

> 猜一个 C++ class layout。

更稳健：

```c
extern "C"
plugin_api* plugin_get_api(
    uint32_t requested_version);
```

---

# 71. Function Table

例如：

```c
typedef struct decoder_api_v1 {
    uint32_t struct_size;

    decoder_handle* (*create)(
        const decoder_config*);

    void (*destroy)(
        decoder_handle*);

    decoder_status (*process)(
        decoder_handle*,
        const uint8_t*,
        size_t,
        float*,
        size_t,
        size_t*);
} decoder_api_v1;
```

Host得到一张：

> C-compatible function table。

---

# 72. Function Table 的优势

```text
one stable entry symbol
explicit version negotiation
small symbol surface
easy plugin swapping
cross-language friendly
```

而且新版本可以：

```text
decoder_api_v2
```

明确演进。

---

# 73. VTable 与 Function Table 看起来相似，但 Contract 不同

C++ vtable：

```text
compiler-controlled ABI detail
```

手工 function table：

```text
application-designed protocol
```

后者你可以明确控制：

```text
field order
version
optional functions
struct size
```

所以 plugin SDK更容易长期稳定。

---

# Part XXIII · Version Negotiation

# 74. 不要把 Library Version 和 ABI Version 混为一谈

软件版本：

```text
2.7.1
```

可能包含：

```text
bug fixes
features
internal changes
```

ABI version：

> binary contract generation。

一个 software release可以：

```text
new version
same ABI
```

也可以：

```text
new version
new ABI
```

---

# 75. Explicit ABI Version

例如：

```c
#define DECODER_ABI_VERSION 1
```

或者：

```c
decoder_status decoder_get_api(
    uint32_t requested_version,
    decoder_api* out);
```

Host明确说：

> 我理解 ABI v1。

Library：

> 支持 / 不支持。

这比：

> “希望它们碰巧兼容”

强得多。

---

# Part XXIV · ABI Breaks Catalogue

# 76. 修改 Class Data Members

可能 break：

```text
sizeof
offsets
alignment
```

---

# 77. 修改 Base Classes

可能改变：

```text
object layout
pointer adjustment
vtable organization
```

---

# 78. 添加 / 重排 Virtual Functions

可能改变：

```text
vtable ABI
```

---

# 79. 修改 Function Parameter Types

必然影响：

```text
symbol mangling
calling convention
```

---

# 80. 修改 Return Type

有趣的是某些 C++ mangling schemes 对普通非-template function 的 return type处理方式不一定和 parameter一样。

但不要依赖这种细节设计兼容性。

Source/API/ABI都应该明确认为：

> return contract变化是接口变化。

---

# 81. 修改 Exception Specification

`noexcept` 可以影响：

```text
type system
function types
optimization
ABI/toolchain details
```

不要把 public ABI 中的 exception specification 当作无关装饰。

---

# 82. 修改 Enum Underlying Representation

可能改变：

```text
size
alignment
calling convention
```

---

# 83. 修改 Packing / Alignment

显然可能破坏：

```text
struct layout
array stride
parameter ABI
```

---

# 84. 修改 Standard Library / Toolchain ABI

即使你的 public header没有变化，

如果接口暴露：

```text
std::string
std::vector
std::shared_ptr
```

标准库 ABI变化也可能传递到你的 ABI。

---

# Part XXV · Inline Functions

# 85. Public Header 中的 `inline`

例如：

```cpp
inline int version() {
    return 1;
}
```

Caller编译时可能：

```text
embed implementation directly
```

升级 shared library：

```text
version() implementation → 2
```

旧 executable：

> 可能仍然运行已经编进自己的 old code。

所以：

> Header implementation 本身可能成为 distributed binary behavior。

---

# 86. Inline API Evolution 要谨慎

如果 inline function：

```cpp
inline int decode_mode(const Config& c) {
    return c.flags & 7;
}
```

下一版改变 semantics，

旧 caller 不重新编译：

> 新 library无法替换 caller 已经内联的逻辑。

这不是 linker bug。

是 inline ABI/API distribution 的自然结果。

---

# Part XXVI · Templates Across Library Boundary

# 87. Templates 通常要求 Definition 对 Caller 可见

例如：

```cpp
template <typename T>
T add(T a, T b) {
    return a + b;
}
```

Caller会：

```text
instantiate add<int>
```

到自己的 binary。

因此 template implementation：

> 通常不是隐藏在 shared library 里的普通 implementation detail。

---

# 88. Header-only Template Library 的 ABI 特征

大量逻辑最终被：

```text
compiled into caller
```

因此：

```text
library update
```

不自动更新 caller中已经实例化的旧代码。

这更像：

> source library distribution。

而不是传统 opaque binary component。

---

# 89. Thin Template Front-end + Stable Core

一种很好的 architecture：

```text
Template / Concepts API
        ↓
normalize representation
        ↓
non-template binary core
```

例如：

```cpp
template <std::ranges::contiguous_range R>
Result decode(R&& range) {
    auto bytes = std::span{
        std::data(range),
        std::size(range)
    };

    return decode_span(bytes);
}
```

真正 binary implementation：

```cpp
Result decode_span(
    std::span<const std::byte>);
```

进一步跨稳定 ABI：

```text
pointer + length
```

这和 G5 的：

> **Thin generic front-end, concrete core**

完全一致。

---

# Part XXVII · ODR Across Binary Components

# 90. ODR 仍然存在

> **One Definition Rule**

Header中：

```cpp
inline constexpr int limit = ...;
```

或者 template：

```cpp
template <typename T>
...
```

不同 components 如果因为：

```text
macros
compiler flags
different headers
feature flags
```

看到不同 definitions，

可能产生：

> ODR violation。

---

# 91. Shared Library 不会自动隔离 ODR Problems

如果同名 C++ entities在多个 binaries中：

```text
definitions differ
```

linker/loader behavior与语言规则共同作用，

可能出现非常难排查的问题。

所以：

> ABI compatibility 还依赖 header consistency。

---

# Part XXVIII · Debug vs Release ABI

# 92. 不同 Build Modes 也可能不兼容

某些 standard library/toolchain：

```text
debug iterators
checked containers
sanitizer instrumentation
ABI-affecting flags
```

可能改变：

```text
object representation
runtime assumptions
```

因此 native binary packages必须明确：

> supported build ABI profile。

---

# 93. Compiler Flags 也可能成为 ABI Contract

例如：

```text
exception enabled/disabled
RTTI enabled/disabled
packing
ABI-version flags
calling convention
stdlib choice
```

都可能影响 binary interoperability。

所以 library build不是只有：

```text
-std=c++23
```

一个维度。

---

# Part XXIX · C ABI Design Profile

现在建立一套我们自己的稳定 native boundary profile。

---

# 94. Rule 1 — Export C Linkage Entry Points

```cpp
extern "C"
DECODER_API
decoder_status decoder_process(...);
```

---

# 95. Rule 2 — No Exceptions Escape

```cpp
extern "C"
decoder_status decoder_process(...) noexcept;
```

boundary内部：

```text
catch C++ exceptions
↓
convert to error code
```

---

# 96. Rule 3 — Opaque Handles for Stateful Objects

```c
typedef struct decoder decoder;
```

---

# 97. Rule 4 — Explicit Ownership

```c
decoder* decoder_create(...);
void decoder_destroy(decoder*);
```

文档明确：

```text
create transfers ownership to caller
destroy consumes/releases handle
```

---

# 98. Rule 5 — Pointer + Length for Borrowed Buffers

```c
const uint8_t* input,
size_t input_len
```

不要：

```text
NUL termination assumptions
hidden size
```

---

# 99. Rule 6 — Caller-owned Output Where Practical

```c
float* output,
size_t output_capacity,
size_t* output_count
```

避免 allocator crossover。

---

# 100. Rule 7 — Fixed-width Types for Stable Fields

```c
uint32_t
uint64_t
```

而不是把 platform-dependent integral width当 protocol。

---

# 101. Rule 8 — Explicit Versioning

```c
uint32_t abi_version;
uint32_t struct_size;
```

---

# 102. Rule 9 — No STL Types in C ABI

不要：

```text
std::vector
std::string
std::span
std::expected
```

跨 C ABI。

Wrapper可以使用。

---

# 103. Rule 10 — No C++ References in C ABI

不要：

```cpp
extern "C"
void process(const Config& config);
```

稳定 C interface使用：

```c
const decoder_config*
```

---

# 104. Rule 11 — Explicit Thread-safety Contract

文档必须说明：

```text
Can one handle be called concurrently?
Can different handles be used concurrently?
Does destroy require no concurrent calls?
Are callbacks concurrent?
```

ABI 类型本身无法表达这些。

---

# 105. Rule 12 — Explicit Lifetime Contract

例如：

```text
input only borrowed during call
output written before return
callback context must outlive registration
handle must not be used after destroy
```

这是 FFI correctness 的核心。

---

# Part XXX · Error Model

# 106. Error Code

例如：

```c
typedef uint32_t decoder_status;

enum {
    DECODER_OK = 0,
    DECODER_INVALID_ARGUMENT = 1,
    DECODER_BUFFER_TOO_SMALL = 2,
    DECODER_INTERNAL_ERROR = 3,
};
```

简单、跨语言。

---

# 107. Detailed Error Message

一种方式：

```c
decoder_status decoder_last_error(
    decoder*,
    char* buffer,
    size_t capacity,
    size_t* required);
```

但要明确：

```text
thread safety
lifetime
whether error state is per-handle
```

---

# 108. Better: Error as Output

如果错误消息重要：

```c
typedef struct decoder_error {
    uint32_t code;
    char message[256];
} decoder_error;
```

或 caller-owned buffer。

减少：

```text
thread-local hidden state
last-error races
```

---

# Part XXXI · Two-call Buffer Pattern

# 109. Variable-size Output

一种经典 C ABI：

第一次：

```c
decoder_get_names(
    handle,
    NULL,
    0,
    &required);
```

得到：

```text
required size
```

Caller allocate：

```text
buffer
```

第二次：

```c
decoder_get_names(
    handle,
    buffer,
    capacity,
    &written);
```

---

# 110. Race Consideration

如果两次 call之间数据会变化：

```text
required size
↓
state changes
↓
second call size no longer sufficient
```

必须定义：

```text
retry
snapshot handle
version
locking
```

所以这种 API 不是自动正确。

---

# Part XXXII · Callback ABI

# 111. C Callback

典型：

```c
typedef void (*decoder_log_fn)(
    void* context,
    uint32_t level,
    const char* message,
    size_t message_len);
```

registration：

```c
decoder_set_log_callback(
    decoder*,
    decoder_log_fn,
    void* context);
```

---

# 112. `void* context`

C 没有 lambda capture object。

所以：

```text
function pointer
+
void* user context
```

组合出 closure-like interface。

C++ wrapper可以：

```text
context → object pointer
callback trampoline
```

---

# 113. Callback Lifetime

Caller注册：

```text
fn
context
```

Library必须明确：

```text
callback only during registration call?
stored for future?
which thread invokes it?
can callback unregister itself?
```

否则：

```text
context dies
↓
library later callback
↓
UAF
```

---

# 114. Callback Reentrancy

如果 library持内部 mutex：

```text
lock
↓
invoke user callback
```

Callback又：

```text
calls library API
↓
tries same lock
```

可能死锁。

所以与 G7 一样：

> **避免在内部 hot lock 下调用 uncontrolled external code。**

ABI callback boundary尤其危险。

---

# Part XXXIII · Thread Boundary Across ABI

# 115. ABI 还必须规定 Concurrency

例如：

```c
decoder_process(handle, ...)
```

可能是：

### Not thread-safe per handle

```text
one handle
one caller at a time
```

### Thread-safe per handle

内部 synchronization。

### Independent handles thread-safe

```text
different handles may be called concurrently
```

这些都属于 API/ABI semantic contract。

---

# 116. Destroy 与 Concurrent Calls

必须明确：

```text
decoder_destroy(handle)
```

要求：

> no other concurrent operation on handle。

不要试图靠：

```text
internal mutex
```

让“调用已经被销毁对象”合法。

和 G7 thread object destruction完全相同。

---

# Part XXXIV · C++ Wrapper

# 117. C ABI 不意味着 C++ 用户体验差

底层：

```c
decoder* decoder_create(...);
void decoder_destroy(decoder*);
```

C++ wrapper：

```cpp
class Decoder {
public:
    explicit Decoder(const Config& config);

    ~Decoder() {
        decoder_destroy(handle_);
    }

    Decoder(const Decoder&) = delete;
    Decoder& operator=(const Decoder&) = delete;

    Decoder(Decoder&& other) noexcept
        : handle_{
              std::exchange(
                  other.handle_,
                  nullptr)} {}

private:
    decoder* handle_{};
};
```

这把：

```text
C ABI
```

包装成：

```text
RAII C++ API
```

---

# 118. Wrapper 可以用 `expected`

底层：

```c
decoder_status decoder_process(...);
```

上层：

```cpp
std::expected<std::size_t, DecoderError>
Decoder::decode(
    std::span<const std::byte> input,
    std::span<float> output);
```

这样：

```text
stable binary core
+
idiomatic C++23 source API
```

可以同时获得。

---

# Part XXXV · Rust FFI

# 119. Rust 与 C++ 最稳健的边界通常也是 C ABI

Rust：

```rust
#[repr(C)]
pub struct DecoderConfig {
    pub mode: u32,
    pub flags: u32,
}
```

extern declarations调用：

```text
decoder_create
decoder_process
decoder_destroy
```

---

# 120. `repr(C)`

Rust默认 layout不承诺：

> C ABI compatible representation。

`#[repr(C)]`：

> 请求按 C-compatible representation 规则布局该 type。

这和 C++ 的：

```text
“不要假设默认 complex class layout跨语言”
```

完全同源。

---

# 121. Rust Ownership 不穿过 C ABI 自动保留

Rust borrow checker只保护：

> Rust language universe 中能够建模的 lifetime。

一旦：

```text
raw pointer crosses FFI
```

你必须靠 ABI contract保证：

```text
pointer valid
lifetime active
threading correct
alignment correct
```

FFI 会把很多安全责任重新暴露出来。

---

# Part XXXVI · Zig FFI

# 122. Zig 与 C ABI 非常自然

Zig可以：

```text
import C declarations
call C functions
expose export functions
```

所以：

```text
C ABI
```

也是连接：

```text
C++ core
↔
Zig system layer
```

非常自然的最小公分母。

---

# 123. Zig Slice 不能直接当 C ABI Type

Zig：

```zig
[]const u8
```

是语言级 slice abstraction。

C boundary仍然更自然展开：

```text
pointer
+
length
```

和 C++ span 一样。

---

# 124. Allocator 不能偷偷跨 FFI

Zig可能明确传：

```text
Allocator
```

但 C++ library内部可能使用自己的 allocator。

如果一边 allocate、另一边 free：

> 必须由 ABI 明确设计。

语言的 allocator abstraction不会自动互通。

---

# Part XXXVII · C ABI 与 Ownership Model

# 125. Owner Handle

```c
decoder* decoder_create();
```

返回：

> owning handle。

---

# 126. Borrowed Input

```c
decoder_process(
    decoder*,
    const uint8_t* input,
    size_t len);
```

如果文档说：

> input only used during call，

则 caller只需保证：

```text
input lifetime covers function call
```

---

# 127. Stored Borrow

如果 library：

```text
stores input pointer after return
```

contract立刻复杂很多。

Caller必须保证：

```text
buffer lifetime
mutation
thread safety
```

所以稳定 ABI优先：

> copy data or transfer explicit ownership

而不是偷偷保存 borrowed pointer。

---

# Part XXXVIII · C ABI 与 `const`

# 128. `const T*`

```c
const uint8_t* input
```

表示：

> callee不会通过这条 access path 修改 bytes。

但：

```text
const
```

不表示：

> data immutable across all threads / aliases。

和 C++ 内部完全一样。

---

# 129. `const decoder*`

如果 API：

```c
decoder_get_info(
    const decoder* handle);
```

语义上可以表达：

> logical read-only operation。

但 implementation仍可能：

```text
cache lazily
update metrics
lock mutex
```

C/C++ const主要约束 access path/type semantics，

不是完整 concurrency guarantee。

---

# Part XXXIX · Binary Inspection

# 130. ABI 不能只靠猜

G8 必须实际观察 binary。

常见工具：

```text
nm
objdump
readelf
otool
dumpbin
```

具体平台不同。

---

# 131. 看 Symbols

例如：

```bash
nm -C library.o
```

可以观察：

```text
C++ mangled / demangled symbols
undefined references
exported functions
```

---

# 132. 看 Dynamic Symbols

ELF生态中常见：

```bash
readelf -Ws libfoo.so
```

Mach-O 环境可使用对应：

```text
nm
otool
```

等工具。

目的不是记命令，

而是能回答：

```text
What exactly does this library export?
```

---

# 133. 看 Dependencies

需要能观察：

```text
which shared libraries?
rpath?
loader paths?
```

因为“能编译链接”不等于：

> runtime loader一定找到正确 library。

G0 已经覆盖原理。

G9 会把这些变成 build/install workflow。

---

# Part XL · ABI Diff Thinking

# 134. Library Upgrade 前应该比较什么？

至少：

```text
exported symbol set
function signatures
type size/alignment
virtual interface changes
struct field offsets
enum numeric values
ABI version
dependency ABI
```

大型 native libraries常使用专门 ABI compliance tooling。

核心原则：

> ABI compatibility 应该被测试，而不是依赖人工记忆。

---

# Part XLI · Semantic ABI

# 135. Binary-compatible 还不等于真正 Compatible

假设：

```c
decoder_status decoder_process(...);
```

signature完全没变。

v1：

```text
returns output in meters
```

v2：

```text
returns output in centimeters
```

Binary layout完全相同。

但：

> semantic contract 已经 break。

所以完整 compatibility：

```text
Binary ABI
+
Semantic API contract
```

两者都需要稳定。

---

# Part XLII · Lifetime 是 ABI 的一部分

# 136. ABI 不只是 Bits

例如：

```c
const char* decoder_name(
    decoder*);
```

必须说明：

```text
who owns returned pointer?
how long valid?
until next call?
until handle destroy?
forever static?
```

没有 lifetime contract：

> interface仍然不完整。

这就是 G1/G2 进入 ABI 的方式。

---

# Part XLIII · Concurrency 是 ABI 的一部分

# 137. 同样的 Signature 可以有完全不同的 Thread Contract

```c
decoder_process(handle, ...);
```

可以是：

```text
not thread-safe
```

也可以：

```text
thread-safe
```

也可以：

```text
multiple readers allowed
single writer only
```

这些不体现在 function ABI bits中，

但属于：

> **Semantic ABI/API contract。**

---

# Part XLIV · Performance ABI

# 138. 有些边界还需要 Performance Contract

例如 real-time SDK：

```text
decoder_process
```

可能承诺：

```text
no dynamic allocation
no blocking
bounded execution
```

这些不是普通 binary ABI，

但属于非常重要的：

> operational contract。

系统集成中同样要版本化/测试。

---

# Part XLV · Practical Library Design

现在设计一个真正可跨语言的 decoder library。

---

# 139. Public C Header

```c
#ifndef SIGNAL_DECODER_H
#define SIGNAL_DECODER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SIGNAL_DECODER_ABI_VERSION 1u

typedef struct signal_decoder signal_decoder;

typedef uint32_t signal_decoder_status;

enum {
    SIGNAL_DECODER_OK = 0u,
    SIGNAL_DECODER_INVALID_ARGUMENT = 1u,
    SIGNAL_DECODER_BUFFER_TOO_SMALL = 2u,
    SIGNAL_DECODER_INTERNAL_ERROR = 3u,
};

typedef struct signal_decoder_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t model_id;
    uint32_t flags;
} signal_decoder_config;

signal_decoder* signal_decoder_create(
    const signal_decoder_config* config);

void signal_decoder_destroy(
    signal_decoder* decoder);

signal_decoder_status signal_decoder_decode(
    signal_decoder* decoder,
    const uint8_t* input,
    size_t input_size,
    float* output,
    size_t output_capacity,
    size_t* output_count);

#ifdef __cplusplus
}
#endif

#endif
```

这已经形成相当不错的 binary boundary。

---

# 140. Ownership

明确：

```text
signal_decoder_create
→ returns owning handle

signal_decoder_destroy
→ terminates handle lifetime

input
→ borrowed for duration of call

output
→ caller-owned mutable buffer

output_count
→ caller-owned out parameter
```

没有隐藏 allocator transfer。

---

# 141. C++ Implementation Boundary

```cpp
struct signal_decoder {
    Decoder implementation;
};
```

Create：

```cpp
extern "C"
signal_decoder* signal_decoder_create(
    const signal_decoder_config* config) noexcept {

    try {
        if (config == nullptr) {
            return nullptr;
        }

        return new signal_decoder{
            Decoder{convert_config(*config)}
        };
    } catch (...) {
        return nullptr;
    }
}
```

这里还能继续改善：

> `nullptr` 无法表达创建失败原因。

真正 production API 可增加：

```text
status + out_handle
```

形式。

---

# 142. Better Create API

```c
signal_decoder_status
signal_decoder_create(
    const signal_decoder_config* config,
    signal_decoder** out_decoder);
```

成功：

```text
status = OK
*out_decoder = valid handle
```

失败：

```text
status != OK
*out_decoder = NULL
```

错误语义更明确。

---

# 143. Decode Boundary

```cpp
extern "C"
signal_decoder_status signal_decoder_decode(
    signal_decoder* decoder,
    const std::uint8_t* input,
    std::size_t input_size,
    float* output,
    std::size_t output_capacity,
    std::size_t* output_count) noexcept {

    try {
        if (decoder == nullptr ||
            input == nullptr ||
            output_count == nullptr) {
            return SIGNAL_DECODER_INVALID_ARGUMENT;
        }

        auto input_view =
            std::span{
                reinterpret_cast<
                    const std::byte*>(input),
                input_size
            };

        auto output_view =
            std::span{
                output,
                output_capacity
            };

        const auto result =
            decoder->implementation.decode(
                input_view,
                output_view);

        *output_count = result.count;

        return SIGNAL_DECODER_OK;
    } catch (...) {
        return SIGNAL_DECODER_INTERNAL_ERROR;
    }
}
```

C boundary：

```text
pointer + size
```

内部立即提升为：

```text
span
```

这是非常好的 layering。

---

# Part XLVI · C++ Wrapper Layer

# 144. Public C++23 Wrapper

```cpp
class SignalDecoder {
public:
    explicit SignalDecoder(
        const SignalDecoderConfig& config);

    ~SignalDecoder();

    SignalDecoder(
        const SignalDecoder&) = delete;

    SignalDecoder&
    operator=(const SignalDecoder&) = delete;

    SignalDecoder(
        SignalDecoder&& other) noexcept;

    SignalDecoder&
    operator=(SignalDecoder&& other) noexcept;

    std::expected<std::size_t, DecodeError>
    decode(
        std::span<const std::byte> input,
        std::span<float> output);

private:
    signal_decoder* handle_{};
};
```

这让 C++ user 获得：

```text
RAII
span
expected
move semantics
```

而 binary substrate 保持：

```text
small stable C ABI
```

---

# Part XLVII · Plugin ABI

# 145. Plugin 不应直接 Export C++ Class Factory

风险较大的：

```cpp
extern "C"
BasePlugin* create_plugin();
```

虽然 symbol是 C linkage，

但返回：

```text
C++ polymorphic object
```

host与plugin仍然共享：

```text
vtable ABI
RTTI
allocator
destructor
exception runtime
```

所以只是：

> symbol名字看起来稳定，

ABI并没有真正变成 C。

---

# 146. 更稳健：Opaque Handle + Function Table

Host只看到：

```text
C-compatible types
```

Plugin内部：

```text
arbitrary C++ implementation
```

这样隔离更彻底。

---

# Part XLVIII · Cross-module Destruction

# 147. Virtual Destructor 也不自动解决 Allocation Domain

假设 host：

```cpp
delete plugin_object;
```

如果 object 是 plugin内：

```text
custom allocator
```

创建，

即使 virtual destructor正确 dispatch：

> deallocation domain仍必须正确。

更稳妥：

```c
plugin_destroy(handle);
```

让 creator负责 destruction。

---

# Part XLIX · ABI Stability Strategies

# 148. Strategy A — Recompile Everything Together

Monorepo/internal app：

```text
all components
same toolchain
same commit
rebuilt together
```

可以接受更富 C++ 的 interface：

```text
vector
string
templates
classes
```

ABI stability pressure较低。

---

# 149. Strategy B — Stable C++ ABI

需要：

```text
strict toolchain ABI policy
PImpl
symbol visibility
careful virtual interfaces
ABI checks
```

复杂但可行。

---

# 150. Strategy C — Stable C ABI + C++ Wrapper

最适合：

```text
SDK
plugins
cross-language
long-lived binary compatibility
```

这是本 Track 默认推荐的 strongest boundary。

---

# 151. 不同 Boundary 用不同策略

不要认为：

> “整个项目所有 module 都要用 C ABI。”

内部：

```text
C++ types
templates
span
vector
expected
```

完全可以大量使用。

只有真正：

```text
binary / language / plugin boundary
```

才需要更严格 profile。

---

# Part L · ABI Boundary Classification

# 152. Level 0 — Same Translation Unit

几乎没有 ABI evolution问题。

---

# 153. Level 1 — Separate Translation Units

需要：

```text
declaration/definition
ODR
link compatibility
```

但通常一起构建。

---

# 154. Level 2 — Static Libraries

binary object boundary，

但最终一起 link。

---

# 155. Level 3 — Shared Libraries Under One Product

较强 ABI coupling可接受，

只要版本一起控制。

---

# 156. Level 4 — Plugin / Third-party Binary SDK

需要明确：

```text
ABI stability
version negotiation
ownership
exception policy
```

---

# 157. Level 5 — Cross-language Boundary

默认：

> C ABI profile。

越往下：

> binary contract应该越小、越显式、越稳定。

---

# Part LI · API Boundary Design Checklist

# 158. Function Signature

问：

```text
Does it expose compiler/library-specific types?
```

---

# 159. Ownership

```text
Who allocates?
Who frees?
Who owns handle?
Who borrows?
```

---

# 160. Lifetime

```text
How long are pointers valid?
Can library retain them?
```

---

# 161. Errors

```text
exceptions?
status codes?
error object?
```

---

# 162. Concurrency

```text
thread-safe?
per-handle serialization?
callbacks on what thread?
```

---

# 163. Versioning

```text
ABI version?
struct size?
feature discovery?
```

---

# 164. Representation

```text
endianness?
packing?
alignment?
fixed widths?
```

---

# 165. Allocation

```text
same allocator domain?
caller-provided output?
```

---

# 166. Shutdown

对于异步 handle：

```text
close?
cancel?
join?
destroy while callbacks running?
```

G7 的 lifecycle模型同样适用。

---

# Part LII · Practical Labs

# 167. Lab 1 — Name Mangling

定义：

```cpp
int add(int, int);
double add(double, double);
```

编译 object file。

使用：

```text
nm
demangling tools
```

观察：

> 两个 overload 对应不同 binary symbols。

然后改：

```cpp
extern "C"
```

观察 symbol变化。

---

# 168. Lab 2 — ABI Break by Struct Layout

Library v1：

```cpp
struct Config {
    int mode;
};
```

Caller编译。

Library v2改成：

```cpp
struct Config {
    int mode;
    int flags;
};
```

只重编 library，不重编 caller。

理解：

> 为什么 source-level合法不代表 binary-compatible。

---

# 169. Lab 3 — PImpl

版本 A：

```cpp
class Decoder {
    std::vector<float> buffer_;
};
```

记录：

```text
sizeof(Decoder)
```

版本 B增加 internal members。

观察 public type layout变化。

然后改成 PImpl：

```cpp
std::unique_ptr<Impl>
```

再增加 Impl members。

Public Decoder layout保持稳定得多。

---

# 170. Lab 4 — C ABI Wrapper

把：

```cpp
class Decoder
```

包装为：

```text
create
destroy
decode
```

三个 C functions。

要求：

```text
no exception escape
explicit ownership
pointer+length
caller-owned output
```

---

# 171. Lab 5 — Cross-language

用 Zig 或 Rust 调：

```c
signal_decoder_create
signal_decoder_decode
signal_decoder_destroy
```

不暴露任何：

```text
std::vector
std::string
C++ class
```

验证：

> C ABI 确实成为共同最小边界。

---

# 172. Lab 6 — Callback

设计：

```c
typedef void (*log_fn)(
    void* context,
    const char* data,
    size_t len);
```

C++ caller传：

```text
object pointer as context
+
static trampoline
```

然后明确：

```text
callback lifetime
threading
reentrancy
```

---

# 173. Lab 7 — ABI Versioning

定义 v1：

```c
struct config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t mode;
};
```

v2 append：

```c
uint32_t flags;
```

让 v2 library：

> 仍能接受 v1 config。

---

# Part LIII · G8 Review Protocol

面对一个 native boundary，按这个顺序问。

## 1. Boundary 类型

```text
same TU?
static lib?
shared lib?
plugin?
cross-language?
```

---

## 2. API vs ABI

```text
什么是源码 contract？
什么进入 binary contract？
```

---

## 3. Symbols

```text
哪些 symbols 对外？
C++ mangling 还是 C linkage？
```

---

## 4. Calling Convention

```text
双方 toolchain/architecture 是否一致？
```

---

## 5. Data Layout

```text
哪些 structs/classes 跨 boundary？
sizeof/alignment/offset 是否稳定？
```

---

## 6. Ownership

```text
谁 create？
谁 destroy？
```

---

## 7. Allocation

```text
allocator domain是否一致？
```

---

## 8. Error

```text
exception能否穿 boundary？
```

---

## 9. Lifetime

```text
borrowed pointer 有效多久？
```

---

## 10. Concurrency

```text
thread safety / callback / destroy race contract是什么？
```

---

## 11. Versioning

```text
old caller + new library
是否有明确兼容策略？
```

---

## 12. Cross-language

```text
是否应该降到 C ABI？
```

---

# Part LIV · 高频错误

# 174. 错误 1

> Public API 没变，所以 ABI 没变。

错。

Private layout也可能改变 `sizeof(class)`。

---

# 175. 错误 2

> `extern "C"` 可以让 `std::vector` 变成 C-compatible。

错。

---

# 176. 错误 3

> C++23 标准相同，所以两个 compiler 的 ABI 必然兼容。

错。

语言标准与 platform/compiler ABI是不同层。

---

# 177. 错误 4

> `trivially_copyable` struct 可以直接存盘作为长期格式。

错。

还有：

```text
endianness
ABI
padding
versioning
```

---

# 178. 错误 5

> `#pragma pack(1)` 就获得 portable network format。

错。

---

# 179. 错误 6

> Library allocate，caller `free` 就行。

不一定。

Allocator domain必须匹配。

---

# 180. 错误 7

> Opaque Handle 只是为了隐藏源码实现。

更重要：

> 隔离 binary object layout。

---

# 181. 错误 8

> `std::span` 没 allocation，所以适合 C ABI。

它仍然是 C++ library type。

C ABI 展开成 pointer + length。

---

# 182. 错误 9

> Exception 跨 DLL/shared library 一定没问题。

只有在严格兼容 runtime ABI下才可能成为可支持 contract；稳定跨语言 boundary不应依赖它。

---

# 183. 错误 10

> Plugin factory 用 `extern "C"` 返回 C++ base pointer，就已经有稳定 C ABI。

错。

C++ object/vtable/RTTI/destructor ABI仍然暴露。

---

# 184. 错误 11

> Inline function在 shared library升级后也自动升级。

旧 caller可能已经编入旧实现。

---

# 185. 错误 12

> Templates 是 shared library 内部 implementation。

很多 template instantiation实际上发生在 caller。

---

# 186. 错误 13

> Binary-compatible 就表示 semantic-compatible。

单位、ownership、lifetime等变化一样可以 break。

---

# 187. 错误 14

> ABI 只跟 bytes有关。

Thread safety、ownership、lifetime虽然不是低层 bit ABI，也同样是完整 boundary contract。

---

# Part LV · C++ / Zig / Rust 对照

# 188. C++

内部 abstraction能力最丰富：

```text
classes
templates
RAII
exceptions
STL
virtual dispatch
```

但这些正是稳定 external ABI最容易产生 coupling 的区域。

因此：

```text
rich inside
small explicit boundary outside
```

通常是优秀设计。

---

# 189. Zig

Zig 强调：

```text
C interoperability
explicit layout
explicit allocation
```

因此 C ABI 是非常自然的 integration boundary。

但 Zig-specific：

```text
slice
error union
allocator
comptime type
```

同样不能未经设计直接假定为 C ABI。

---

# 190. Rust

Rust：

```text
ownership
enums
traits
slices
Result
```

内部非常强。

跨稳定 native FFI 仍经常降为：

```text
#[repr(C)]
raw pointers
fixed-width integers
explicit create/destroy
```

因为：

> Rust language ABI也不是 C ABI。

---

# 191. 三种语言的共同模式

```text
Rich Language-native API
        ↓
Thin FFI Adapter
        ↓
Small Stable C ABI
```

这几乎是：

> C++ / Rust / Zig native interoperability 的通用黄金结构。

---

# Part LVI · G8 Final Fifteen Axioms

如果半年以后只能记十五条：

1. **API 是 source-level contract，ABI 是 independently compiled binaries 之间的 machine-level contract。**

2. **相同 C++ 标准版本不自动意味着相同 binary ABI；mangling、calling convention、layout 和 runtime属于 implementation/platform ABI。**

3. **C++ public class 的 private representation 也可能进入 ABI，因为 caller 需要知道 `sizeof`、alignment 和 layout。**

4. **PImpl 的核心价值之一是把 private representation 从 public binary layout 中移除。**

5. **`extern "C"` 主要建立 C language linkage；它不会让 C++ object、STL、exception突然变成 C ABI。**

6. **稳定跨语言/native SDK boundary 的默认最小公分母是：C linkage + opaque handles + primitive scalars + pointer/length + explicit ownership。**

7. **谁 allocate，通常就应该由同一 allocation domain负责 free；allocator ownership 是 ABI contract。**

8. **C++ exception 不应穿过 C ABI；boundary 应将异常转换为显式 error representation。**

9. **不要把 in-memory C++ layout 当 wire/storage schema；packing、endianness、versioning、lifetime 是不同问题。**

10. **STL types 在同一受控 toolchain 内可以很好用，但暴露它们会显著扩大 stable binary ABI coupling。**

11. **Opaque Handle 能把内部 class layout、allocator、container 与实现演进隐藏在 stable ABI 后面。**

12. **Plugin 边界优先使用 versioned C function table，而不是依赖 compiler-controlled C++ vtable/RTTI ABI。**

13. **ABI versioning必须显式考虑 struct size、field order、enum values、symbol set 与 semantic behavior。**

14. **Ownership、lifetime、thread safety、callback threading 和 shutdown 虽然不全是 bit-level ABI，却都是完整 binary interface contract 的一部分。**

15. **优秀 native library architecture 通常是 Rich C++ Internals + Small Stable Binary Boundary + Idiomatic Language Wrappers。**

---

# Part LVII · G8 Final Gate

应该能闭卷回答：

## API / ABI

1. API 与 ABI 的区别是什么？
2. 为什么 private member 变化也可能 ABI break？
3. 为什么 source-compatible 不等于 binary-compatible？

## Symbol

1. C++ 为什么需要 name mangling？
2. `extern "C"` 真正改变什么？
3. 为什么它不能让 `std::string` 获得稳定 C ABI？

## Calling Convention

1. Calling convention 至少规定哪些东西？
2. 为什么大型 return object 可能需要 hidden result pointer？

## Layout

1. 为什么 class inheritance/vtable 会扩大 ABI surface？
2. `trivially_copyable` 为什么不等于 portable serialization？
3. 为什么 packing 不能解决 endianness？

## Ownership

 1. 为什么 library allocate / caller free 可能错误？
 2. caller-provided output buffer 有什么优势？
 3. opaque handle 如何表达 owning stateful object？

## Error

 1. 为什么 exception 不应穿过 C ABI？
 2. `noexcept` 在 FFI boundary 有什么作用？

## STL / Templates

 1. 为什么 `vector` / `string` 会扩大 binary coupling？
 2. 为什么 template implementation 经常实际编进 caller？
 3. 为什么 inline implementation 会让旧 caller保留旧逻辑？

## Versioning

 1. `struct_size` 有什么价值？
 2. 为什么 append-only field evolution 比 reorder field 更容易兼容？
 3. Software version 与 ABI version 为什么不是一回事？

## Plugins

 1. 为什么 `extern "C" Base* create()` 仍然不是纯 C ABI？
 2. versioned function table为什么适合插件？

## Cross-language

 1. 为什么 Rust `repr(C)` / Zig C interoperability仍然不能取消 ownership/lifetime contract？
 2. 为什么 pointer + length 是 span/slice 跨 FFI 的自然降级形式？

---

# Part LVIII · G0 → G8 的完整闭环

现在 G0 学到的：

```text
source
↓
translation unit
↓
object file
↓
symbols
↓
linker
↓
shared library
↓
loader
↓
process
```

已经和 G1–G8 完整连接：

```text
G1
Object / Lifetime

↓
G2
Ownership

↓
G3
Value / Move

↓
G4
Containers / Views

↓
G5
Templates / Genericity

↓
G6
Representation / Performance

↓
G7
Concurrency / Mutation Authority

↓
G8
Binary Boundary / ABI
```

现在看到：

```cpp
std::vector<std::shared_ptr<Foo>>
get_objects();
```

如果它只是内部 function，

可能完全合理。

如果它是：

> 第三方 plugin SDK 的 binary interface，

你应该立即看到：

```text
std::vector ABI
shared_ptr ABI
Foo layout
allocator domain
exception behavior
stdlib ABI
reference counting runtime
thread safety
ownership
```

全部被推到了 boundary。

这就是 G8 最重要的能力：

> **能看到一个源码 signature 背后的全部 binary commitments。**

---

# G8 完成状态

```text
G8.1   API vs ABI
G8.2   Symbols / Linkage / Name Mangling
G8.3   Calling Convention
G8.4   Data & Object Layout ABI
G8.5   Inheritance / VTable / RTTI
G8.6   Exception ABI
G8.7   Allocator Boundary
G8.8   STL / Templates / Inline ABI
G8.9   Static / Shared Libraries
G8.10  Symbol Visibility
G8.11  PImpl
G8.12  C ABI / Opaque Handle
G8.13  Versioning
G8.14  Callback / Plugin ABI
G8.15  Rust / Zig Interop
G8.16  Binary Inspection / Compatibility Review
──────────────────────────────────────────────
G8      COMPLETE / FROZEN
```

下一份整章文档就是：

# **G9 — Build & Native Ecosystem**

它会把我们从 G0 到 G8 的所有机制真正映射到现代 C++ 工程系统：

```text
Source Files
     ↓
Targets
     ↓
Usage Requirements
     ↓
Compile Commands
     ↓
Object Files
     ↓
Static / Shared Libraries
     ↓
Executables
     ↓
Install / Export
     ↓
Package Discovery
```

核心会系统解决：

```text
现代 CMake 到底在建模什么？
为什么 target 是核心，不应该全局堆 flags？
PUBLIC / PRIVATE / INTERFACE 到底是什么？
CMake Presets 与 toolchain file 分别解决什么？
find_package / package config 是怎么工作的？
FetchContent / system package / package manager 怎么选？
Modules / PCH / Unity / LTO 应该放在哪一层？
Sanitizer / debug / release profile 如何设计？
怎样构建真正可安装、可消费、可跨平台的 C++23 library？
```

G9 完成以后，我们就会结束“知识章节阶段”，正式进入 **G10 Systems Project / Runtime Lab**。
