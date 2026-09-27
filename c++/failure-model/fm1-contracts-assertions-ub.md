<a id="fm-1--contracts--preconditions--assertions--undefined-behavior"></a>
# FM-1 · 契约与可信边界

> C++23 失败语义工程手册 · 系列整理候选

[返回 FM 导航](README.md) · [上一章：FM-0](fm0-failure-model.md) · [下一章：FM-2](fm2-value-based-failure.md) · [术语与审查约定](series-guide.md)

## 阅读入口

明确前置条件、成功／失败后置条件、不变量、validation 与 assertion 的责任。UB 和终止不能混成一种错误通道。

**主阅读线。** §1–8 → §12–18 → §19–26 → §33–40；具体反例按需回查。

**失败契约。** 从未经验证输入进入可信表示后，仍须维护生命周期、别名与同步条件。失败可以是合法运行结果；违约的具体后果要逐个接口判断。

**证据边界。** T01/T02、T04/T05 定向检查异常构造、枚举与 unreachable；不证明所有前置条件或 UB 都会被诊断。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、合同与责任](#fm1-part-1)
- [二、验证边界与断言](#fm1-part-2)
- [三、检查访问与未定义行为](#fm1-part-3)
- [四、终止与不可达承诺](#fm1-part-4)
- [五、可信表示与类型设计](#fm1-part-5)
- [六、反例与回查](#fm1-part-6)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm1-part-1"></a>

## 一、合同与责任

### 0. 文档定位

本文解决现代 C++ Failure Model 中一个基础问题：

> 什么情况应该被建模为“可恢复失败”，什么情况应该被视为“程序违反了自身契约”？

如果这个边界不清楚，工程中很容易出现以下问题：

- 用 `assert` 检查不可信输入；
- 把程序 bug 包装成 `std::expected` 一路传播；
- 把 UB 当作一种“性能更高的错误处理”；
- release 构建中因为 `assert` 消失而暴露安全问题；
- 在 trusted core 中重复进行大量无意义检查；
- 在 validation boundary 之后仍然传播“半可信”数据。

FM-1 的目标是建立：

```text
external uncertainty
    ↓
validation
    ↓
trusted representation
    ↓
contract-based core
```

并明确区分：

```text
runtime failure
contract violation
undefined behavior
fail-fast
```

### 1. Contract 是什么

一个函数的完整接口不只是：

```cpp
R f(A a);
```

真正的 contract 至少包含：

```text
preconditions
postconditions
invariants
failure semantics
```

### 2. Preconditions

Precondition 表示：

> 调用者在调用函数之前必须保证的条件。

例如：

```cpp
int front(std::span<const int> values) {
    return values.front();
}
```

一个关键 precondition 是：`!values.empty()`

如果调用者违反这个条件，含义不是：`front() 正常尝试工作但失败`

而是：`调用本身违反 API contract`

因此：`recoverable runtime failure`

和：`precondition violation`

必须严格区分。

### 3. Postconditions

后置条件（postcondition）描述指定完成分支之后应成立的条件。**正常返回不一定表示业务成功**：返回错误值也是正常返回，必须区分成功后置条件与失败后置条件。

例如：

```cpp
void sort_values(std::span<int> values);
```

成功返回后，`values` 应满足约定排序。又例如：

```cpp
File open_file(...);
```

若该接口约定“正常返回即成功”，返回的 File 应拥有有效资源；若采用 `expected`，则成功与错误分支各有自己的后置条件。实现没有满足适用分支的合同才属于被调方缺陷，不能把正常返回的错误值误判为违约。

### 4. Invariants

Invariant 表示：

> 一个类型或组件在所有公开可观察的合法状态中都必须成立的条件。

例如：

```cpp
class Buffer {
private:
    std::byte* data_;
    std::size_t size_;
};
```

可能定义：

```text
size_ == 0
    ⇔
data_ == nullptr
```

或者：

```text
size_ > 0
    ⇒
data_ != nullptr
```

对于：

```cpp
class RingBuffer
```

可能有：

```text
size_ <= capacity_

head_ < capacity_

tail_ < capacity_
```

Invariant 是：`valid object state`

的定义。

### 5. Contract 的责任方向

对于：

```cpp
R f(A a);
```

责任可以理解为：

```text
caller
  │
  │ establishes preconditions
  ▼
callee
  │
  │ performs operation
  ▼
postconditions
  │
  ▼
object/component invariants remain valid
```

因此：

```text
Precondition
    → caller responsibility

Postcondition
    → callee responsibility

Invariant
    → type/component responsibility
```

### 6. Runtime Failure 与 Contract Violation

这是 FM-1 最重要的分界。

<a id="runtime-failure"></a>

**Runtime Failure**

环境本来就可能不满足要求。

例如：

```text
network packet truncated
file missing
permission denied
invalid configuration
remote timeout
malformed user input
```

程序必须正常面对这些情况。

典型处理：

```text
validate
→ structured failure
→ propagate / recover
```

<a id="contract-violation"></a>

**Contract Violation**

根据 API 或程序设计：`这个条件本来必须成立`

但调用者或内部实现破坏了它。

例如：

```text
invalid internal index
illegal state transition
dangling reference
double ownership
impossible enum/state combination
```

这属于：`programmer error`

而不是普通业务失败。违约后是否 UB、显式终止或定义良好的错误报告，由具体合同与语言规则决定；“契约违反”本身不是一个统一的运行时机制。

### 7. 判断标准

不要只看错误表面形式。

例如：`index out of range`

可能属于完全不同的失败模型。

<a id="外部输入"></a>

**外部输入**

```cpp
index = request.index;
```

如果来自 HTTP、文件、网络或数据库：`runtime data`

必须先判断其可信度。

如果可能非法：`validation`

<a id="内部已验证状态"></a>

**内部已验证状态**

如果：

```cpp
index = validated_table[id];
```

并且程序 invariant 已保证：`index < size`

那么越界说明：`program bug`

### 8. 核心问题

判断一个条件属于 precondition 还是 runtime validation 时，优先问：

> 谁有责任保证这个条件成立？

如果调用者根据 API contract 必须保证：`precondition`

如果外部环境天然可能违反：`runtime validation`

<a id="fm1-part-2"></a>

## 二、验证边界与断言

### 9. Validation

Validation 用于处理：`untrusted or runtime-controlled data`

包括：

```text
network packets
files
user input
RPC requests
database records
configuration
external service responses
serialized state
```

典型流程：

```text
untrusted data
      ↓
validation
      ↓
valid internal representation
```

失败应该产生：`structured recoverable failure`

例如：

```cpp
std::expected<Frame, ParseError>
parse_frame(std::span<const std::byte> bytes);
```

### 10. Assertion

Assertion 的用途不同：

> 检查程序自己已经推理为“必须成立”的条件。

例如：

```cpp
assert(index < messages.size());

return messages[index];
```

含义是：

```text
如果这里失败，
说明程序内部推理或 invariant 被破坏。
```

不是：`用户给了坏数据，请优雅处理。`

### 11. Validation 与 Assertion 的工程区分

可以压缩为：

```text
validation
    protects the program from external uncertainty

assertion
    checks the program against its own assumptions
```

这是本节最重要的工程规则之一。

### 12. `assert`

C++：

```cpp
#include <cassert>

assert(condition);
```

主要用于开发阶段检查内部条件。

如果 assertion enabled 且条件为 false：

```text
diagnostic
→ abort
```

具体输出形式由实现决定。

### 13. `NDEBUG`

是否启用标准断言取决于包含 `<cassert>` 时的 `NDEBUG`，而不是语言认识某个 Debug／Release 构建名称：

```cpp
#define NDEBUG
```

在禁用断言的配置下：

```cpp
assert(expr);
```

其表达式不会求值。因此下例不能承担必要输入验证：

```cpp
assert(validate_input());
```

Release 常定义 NDEBUG，但这是构建配置约定；Debug 也可能禁用断言。需要一直执行的验证必须写在断言之外。

### 14. Assertion 不得承载必要副作用

错误：

```cpp
assert(++index < size);
```

debug：`index incremented`

release：`index unchanged`

导致程序语义依赖 build mode。

同样：

```cpp
assert(initialize_resource());
```

也是危险设计。

原则：

> `assert` 中的表达式应当主要用于观察和验证，而不是承担程序正确运行所依赖的副作用。

### 15. `assert` 不适合处理外部输入

错误：

```cpp
void decode_packet(std::span<const std::byte> packet) {
    assert(packet.size() >= kHeaderSize);

    ...
}
```

如果 packet 来自网络：`packet too short`

属于：`runtime input failure`

而不是：`programmer bug`

正确模型：

```cpp
std::expected<Packet, ParseError>
decode_packet(std::span<const std::byte> packet) {
    if (packet.size() < kHeaderSize) {
        return std::unexpected(ParseError::truncated);
    }

    ...
}
```

### 16. Validation Boundary

成熟系统应该明确：

```text
untrusted world
      ↓
validation boundary
      ↓
trusted domain object
      ↓
trusted core
```

例如：

```text
raw bytes
    ↓
parse + validate
    ↓
Frame
```

成功得到：

```cpp
Frame frame;
```

最好已经意味着：

```text
length valid
version valid
fields consistent
checksum validated
required ranges valid
```

### 17. Validate Once，Trust Afterwards

一种高质量设计模式：

```text
external representation
        ↓
checked boundary
        ↓
validated type
        ↓
trusted core
```

不要让：

```cpp
RawPacket
```

贯穿整个程序，并在每一层重复：

```cpp
if (!packet.valid()) {
    ...
}
```

更好的设计：

```cpp
class Frame {
public:
    static std::expected<Frame, ParseError>
    parse(std::span<const std::byte> bytes);

private:
    Frame(...);
};
```

成功构造 `Frame` 本身就表达：`Frame invariant holds`

该工程模式的前提是校验结果在整个使用期内持续有效。若 Frame 借用外部内存，必须保证生命周期、别名修改和线程同步不会使已验证条件失效；包装成 validated 类型本身不能替代这些责任。发生相关变更后应重新建立不变量或重新验证。

### 18. Checked Boundary + Trusted Core

高性能系统中非常常见：

```text
external bytes
      ↓
checked parser
      ↓
validated representation
      ↓
unchecked hot path
```

例如：

```cpp
std::expected<Message, ParseError>
parse_message(std::span<const std::byte> bytes);
```

负责：

```text
length validation
version validation
field range checks
header validation
```

而内部：

```cpp
decode(const Message& message);
```

直接依赖：`Message invariant`

这可以同时获得：

```text
correctness
performance
clear ownership of validation
```

<a id="fm1-part-3"></a>

## 三、检查访问与未定义行为

### 19. `operator[]` 与 `at()`

这是 contract-based API 与 checked API 的经典对比。

```cpp
std::vector<int> values{1, 2, 3};
```

<a id="operator"></a>

**`operator[]`**

```cpp
values[index];
```

调用者负责保证：`index < values.size()`

在 C++23 语义基线下，如果越界：`undefined behavior`

它不是一个正常错误返回通道。

<a id="at"></a>

**`at()`**

```cpp
values.at(index);
```

由容器主动检查：`index < size()`

越界：

```cpp
throw std::out_of_range
```

因此：

```text
operator[]
    caller establishes precondition

at()
    callee validates index
```

### 20. Checked 与 Unchecked API 都有合理用途

如果：

```cpp
if (index >= values.size()) {
    return std::unexpected(Error::invalid_index);
}

auto& value = values[index];
```

那么检查已经发生。

这里：

```cpp
operator[]
```

是合理的 trusted-core 操作。

如果：

```cpp
return values[request.index];
```

而 index 直接来自外部，则不合理。

因此问题不是：`at() 永远比 [] 好`

而是：`check 在哪个 boundary 完成？`

### 21. Undefined Behavior

UB 不是错误处理机制。

它表示：

> 程序已经执行了 C++ 标准不再规定语义的操作。

例如：

```cpp
std::vector<int> values{1, 2, 3};

int x = values[100];
```

这里不是：`C++ 返回一个随机值`

而是：`language guarantees have ended`

### 22. UB 可能产生什么结果

UB 以后可能：

```text
看起来正常
crash
读垃圾值
写坏内存
删除某些代码路径
产生违反直觉的优化结果
```

不能依赖其中任何一种。

### 23. UB 与 Runtime Error 的根本区别

定义良好的失败报告仍处于 C++ 语义规则之内。例如下面是抛出语句片段，需要 `<stdexcept>` 和外围函数：

```cpp
throw std::out_of_range{"index out of range"};
```

`std::out_of_range` 需要错误描述参数，不能写成 `std::out_of_range{}`。这里“运行时失败”指运行期间被显式报告的失败，不是说该类型继承自 `std::runtime_error`；它实际属于 `std::logic_error` 分支。[N4950：out.of.range](https://timsong-cpp.github.io/cppwp/n4950/diagnostics#out.of.range)

调用者可依据明确的抛出、捕获和状态契约继续推理。UB 则没有这种可移植的恢复保证。

完整正例和原式的预期编译失败反例见 [T01 / T02](review/fm-verification-samples.md#t01)。

### 24. UB 会影响优化推理

例如：

```cpp
int f(int* p) {
    int x = *p;

    if (p == nullptr) {
        return 0;
    }

    return x;
}
```

`*p` 已经要求：

`p != nullptr`

所以在任何定义良好的执行中：`p cannot be null`

编译器可以据此优化后面的：

```cpp
if (p == nullptr)
```

这说明：

> UB 不只是“运行时出了问题”，它还改变了编译器对程序合法路径的推理。

### 25. `assert` 与 UB

在断言启用且条件求值本身有定义时：

```cpp
assert(index < size);
```

假条件走诊断与终止路径。若断言被禁用，条件不求值，也没有这道保护；随后执行：

```cpp
array[index]
```

仍须满足实际访问的前置条件。断言能辅助在 UB 前发现某些违约，但不使非法访问变成错误值，也不保证所有缺陷都被检查。

### 26. Assertion 不会改变 API Contract

例如：

```cpp
T& get(std::size_t index) {
    assert(index < size_);
    return data_[index];
}
```

真实 contract 仍然是：

```text
Precondition:
    index < size_
```

`assert` 只是：

`debug-time checking of that contract`

它不是：`runtime validation API`

因为 release 构建可能没有这个检查。

### 27. 常见 UB 来源

<a id="memory"></a>

**Memory**

```text
out-of-bounds access
use-after-free
dangling pointer/reference
invalid pointer arithmetic
misaligned access
```

<a id="lifetime"></a>

**Lifetime**

```text
use outside object lifetime
use destroyed object
incorrect manual lifetime management
```

<a id="arithmetic"></a>

**Arithmetic**

例如：

```cpp
int x = INT_MAX;
++x;
```

signed integer overflow：`UB`

而无符号整数：`modulo arithmetic`

不是 UB。

<a id="object-model"></a>

**Object Model**

可能包括：

```text
invalid type punning
alignment violations
incorrect object representation assumptions
```

<a id="concurrency"></a>

**Concurrency**

未同步的数据竞争：`data race`

通常就是：`UB`

不能把它理解为：`偶尔读取旧数据`

### 28. 为什么 C++ 允许 Contract-Based Unchecked Operations

Unchecked 操作允许调用者建立前提后由被调方依赖它。例如：

```cpp
values[index];
```

不规定必须执行如下检查：

```cpp
if (index >= values.size())
```

这给实现和调用者控制成本的空间，但不证明 checked API 必然更慢；优化器可能消除冗余检查，性能仍须测量。本章关注的是证明与验证责任，不能以“零开销”口号允许未经验证的数据进入前置条件接口。

<a id="fm1-part-4"></a>

## 四、终止与不可达承诺

### 29. Fail-Fast

当内部 invariant 被破坏时，继续运行有时比终止更危险。

例如：

```text
ownership corrupted
state machine impossible state
critical accounting invariant broken
heap corruption suspected
```

此时合理策略可能是：

```text
detect
→ record diagnostics
→ terminate affected failure domain
```

这叫：`fail-fast`

### 30. Fail-Fast 不等于 UB

应优先区分：`explicit termination`

和：`undefined behavior`

一个系统发现 impossible state 后：

```cpp
std::terminate();
```

比故意继续执行直到 UB 更有定义、更容易诊断。

### 31. Debug Assertion 与 Production Check

标准：

```cpp
assert(condition);
```

可能在 release 消失。

但有些 invariant：`即使 production 也必须验证`

例如继续运行可能造成：

```text
persistent data corruption
security violation
irreversible external side effect
```

那么项目通常需要：`always-on fatal check`

概念上：

```cpp
CHECK(condition);
```

其行为：

```text
debug:
    check

release:
    still check

failure:
    diagnostic + terminate
```

`CHECK` 不是标准 C++ API，通常属于项目基础设施。

### 32. Assertion 与 Production Invariant Check

推荐区分：

```text
assert
    development correctness aid

always-on fatal check
    production invariant enforcement
```

不要因为：`这是内部 invariant`

就自动认为：`release 可以不检查`

是否需要 always-on 检查取决于 violation 的后果。

### 33. `std::terminate`

`std::terminate()` 表示：

`program cannot continue through normal C++ execution`

它具有定义明确的终止语义。

典型触发包括：

```text
exception escapes noexcept function
uncaught exception escapes std::thread entry
explicit fail-fast decision
```

它属于：`terminal behavior`

而不是普通错误 transport。

### 34. `std::unreachable` — C++23

`std::unreachable()` 承诺合法执行不会到达此处；到达它是 UB，不是受控拒绝。[N4950：utility.unreachable](https://timsong-cpp.github.io/cppwp/n4950/utility#utility.unreachable)

以下是带前置条件的函数片段：

```cpp
#include <utility>

enum class State { idle, running };

// Preconditions: state == State::idle || state == State::running.
int value(State state) {
    switch (state) {
    case State::idle:    return 0;
    case State::running: return 1;
    }
    std::unreachable();
}
```

该 scoped enum 的固定底层类型是 `int`；`static_cast<State>(2)` 本身可以有定义，却不是两个命名值之一。若不能在调用前证明前置条件，就应在边界验证，或将最后一行替换为明确的拒绝／终止路径，而不是保留不可达假设。[N4950：expr.static.cast/10](https://timsong-cpp.github.io/cppwp/n4950/expr.static.cast#10)

[T04 / T05](review/fm-verification-samples.md#t04) 分别检查未命名值与隔离的 UBSan 反例；sanitizer 的一次诊断不构成 UB 的可移植行为保证。

### 35. `std::unreachable` 不是 Fail-Fast

它不是：

```text
abort
terminate
panic
throw
```

它是在向编译器声明：`this control-flow path is impossible`

如果真实执行到：

```cpp
std::unreachable();
```

行为是：`undefined behavior`

因此：

> `std::unreachable` 是语义/优化承诺，不是运行时保护机制。

### 36. 三种机制对比

| 机制 | 条件违反时 |
|---|---|
| `assert(false)` | assert enabled 时终止；可能被禁用 |
| `std::terminate()` | 明确定义为程序终止 |
| `std::unreachable()` | 执行到即 UB |

不要互相替代。

### 37. `std::unreachable` 的使用原则

只有当你可以证明：`合法程序状态下绝不可能到达`

才考虑使用。

不要习惯性写：

```cpp
default:
    std::unreachable();
```

尤其当：

```text
enum may receive corrupted value
ABI compatibility exists
serialized state may be stale
external input may participate
```

时更要谨慎。

在很多高可靠系统中：`diagnostic fail-fast`

比极小的潜在优化价值更重要。

<a id="fm1-part-5"></a>

## 五、可信表示与类型设计

### 38. Internal 不等于 Trusted

这一点非常重要。

数据来自：

```text
database
cache
disk
old process version
IPC
shared memory
another service
```

即使这些组件属于“自己的系统”，数据也未必可信。

例如：`数据库字段由旧版本写入`

当前程序仍然应该把它视作：`runtime externalized state`

而不是：`guaranteed internal invariant`

因此：

> “来自内部系统”不等于“满足当前进程 invariant”。

### 39. 信任应该建立在 Boundary 上

推荐：

```text
raw persisted/external state
       ↓
validation
       ↓
current-version validated representation
       ↓
trusted core
```

而不是根据：`数据是不是我们自己写的`

决定是否信任。

### 40. Type as Invariant

最好的 invariant 往往不是：

```cpp
assert(valid());
```

而是：`非法状态根本无法通过类型表达`

例如不要设计：

```cpp
struct Connection {
    Socket socket;
    bool connected;
};
```

因为存在：

```text
socket invalid
connected == true
```

这种矛盾组合。

可以考虑：

```text
DisconnectedConnection
ConnectedConnection
```

让状态转换通过类型发生。

### 41. Invalid States Should Be Hard to Represent

现代 C++ 类型设计应尽量：`encode invariants into construction and type structure`

利用：

```text
private constructors
factory functions
strong types
enum class
variant
RAII
ownership types
validated domain types
```

将错误从：`runtime checking problem`

提升为：`construction/type-system problem`

### 42. 优先级

如果一个非法状态能够：`编译期消除`

优先编译期。

否则：`构造阶段消除`

再否则：`validation boundary 消除`

最后才是：`trusted core assertion`

可以理解成：

```text
compile-time
    ↓
construction-time
    ↓
boundary validation
    ↓
internal invariant check
```

越早消除越好。

### 43. Engineering Decision Model

面对：

```cpp
if (!condition) {
    ...
}
```

首先判断 condition 为什么可能失败。

<a id="case-a--外部世界可能不满足"></a>

**Case A — 外部世界可能不满足**

```text
validation
→ recoverable failure
```

<a id="case-b--api-明确允许任意输入"></a>

**Case B — API 明确允许任意输入**

```text
checked API
→ recoverable failure
```

<a id="case-c--调用者必须保证"></a>

**Case C — 调用者必须保证**

```text
precondition
→ contract
```

<a id="case-d--内部逻辑保证成立"></a>

**Case D — 内部逻辑保证成立**

```text
invariant
→ assertion / fatal check
```

<a id="case-e--无法恢复且状态可信度已经丢失"></a>

**Case E — 无法恢复且状态可信度已经丢失**

`fail-fast`

### 44. API Design Pattern

推荐形成两层 API：

```text
checked public/external boundary
        ↓
validated representation
        ↓
fast internal API with clear preconditions
```

例如：

```cpp
std::expected<Message, ParseError>
parse_message(std::span<const std::byte> bytes);
```

然后：

```cpp
void decode(const Message& message);
```

而不是：

```cpp
void decode(std::span<const std::byte> bytes);
```

并在所有深层函数里重复检查原始字节。

<a id="fm1-part-6"></a>

## 六、反例与回查

### 45. Anti-Patterns

<a id="451-assert-untrusted-input"></a>

**45.1 Assert Untrusted Input**

错误：

```cpp
assert(packet.size() >= 32);
```

如果 packet 来自外部。

<a id="452-depend-on-assert-side-effects"></a>

**45.2 Depend on Assert Side Effects**

错误：

```cpp
assert(initialize());
```

<a id="453-convert-every-programmer-bug-to-expected"></a>

**45.3 Convert Every Programmer Bug to `expected`**

错误倾向：

```cpp
std::expected<T, InternalImpossibleState>
```

如果这个状态按设计根本不应该发生。

结果可能只是：`bug 被隐藏并传播`

<a id="454-treat-ub-as-fast-error-handling"></a>

**45.4 Treat UB as Fast Error Handling**

错误思维：`我们不检查，错了反正 UB，这样最快。`

UB 不是 failure policy。

合理模型应该是：

```text
validated boundary
+
trusted precondition
```

而不是：`unchecked untrusted input`

<a id="455-revalidate-everywhere"></a>

**45.5 Revalidate Everywhere**

如果：`ValidFrame`

已经保证 invariant，

不要所有内部函数都再次验证：

```text
header valid?
length valid?
version valid?
```

这会：

```text
增加复杂性
模糊 trust boundary
增加重复成本
削弱类型语义
```

<a id="456-blind-stdunreachable"></a>

**45.6 Blind `std::unreachable`**

不要用：

```cpp
std::unreachable();
```

掩盖：`其实没有证明 impossible`

### 46. Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

设计或 Review API 时：

```text
[ ] Preconditions 是否明确？
[ ] Preconditions 由谁负责建立？
[ ] Postconditions 是否明确？
[ ] 类型 invariants 是否明确？
[ ] 外部数据是否经过 validation boundary？
[ ] Internal data 是否真的值得信任？
[ ] 是否错误使用 assert 处理外部 failure？
[ ] assert 是否包含必要副作用？
[ ] release 构建是否会失去必要检查？
[ ] 是否需要 production fatal check？
[ ] UB 是否可能由未验证输入触发？
[ ] checked API 与 trusted API 是否职责明确？
[ ] validated representation 是否尽早建立？
[ ] 是否存在可以由类型系统消除的非法状态？
[ ] std::unreachable 是否有严格证明？
[ ] contract violation 是否被错误地当作业务失败传播？
```

### 47. FM-1 核心不变量

<a id="fm1-i1"></a>

**FM1-I1**

> External uncertainty 必须通过 validation 进入系统。

<a id="fm1-i2"></a>

**FM1-I2**

> Assertion 用来检查内部推理，而不是验证不可信输入。

<a id="fm1-i3"></a>

**FM1-I3**

> Precondition violation 与普通 runtime failure 是不同类别。

<a id="fm1-i4"></a>

**FM1-I4**

> `assert` 由 NDEBUG 控制，是可禁用的合同检查，不是可靠的常开输入验证。

<a id="fm1-i5"></a>

**FM1-I5**

> 不得让程序正确性依赖 assert 中的副作用。

<a id="fm1-i6"></a>

**FM1-I6**

> UB 不是 error transport，也不存在通用 recovery contract。

<a id="fm1-i7"></a>

**FM1-I7**

> 应在 UB 发生之前检测重要 contract violation。

<a id="fm1-i8"></a>

**FM1-I8**

> `std::unreachable` 是“不可到达”的语义承诺，不是 fail-fast API。

<a id="fm1-i9"></a>

**FM1-I9**

> 数据是否可信由 validation boundary 决定，不由“是不是自己的系统产生”决定。

<a id="fm1-i10"></a>

**FM1-I10**

> Checked boundary 和 trusted core 应明确分层。

<a id="fm1-i11"></a>

**FM1-I11**

> 高价值 invariant 应尽可能编码进类型和构造过程。

<a id="fm1-i12"></a>

**FM1-I12**

> 如果继续运行已经无法保证系统语义，应显式 fail-fast，而不是进入 UB 后期待恢复。

### 48. 最终心智模型

从输入到操作结果，应始终区分合法运行时失败与契约违反：

```text
输入 → 证据足以建立前提？
          ├─ 否 → validation → 拒绝／建立可信表示
          └─ 是 → 依赖且维护已建立的前提
                           ↓
                         操作
          ┌────────────────┼────────────────┐
        成功          合同内运行时失败      契约违反
     成功后置条件      失败后置条件／传播    依具体合同处理
          └────────────────┴→ 仍可依赖哪些不变量？
```

UB 不是图中的恢复分支。即使某次系统调用失败、分配失败或抛出异常，也不意味着调用方前提被破坏；反过来，某个前提被破坏后是否 UB、诊断或定义良好的拒绝，取决于具体规则。目标是在非法操作发生前建立必要条件，而不是为 UB 设计通用 catch。

### 49. FM-1 最终压缩

FM-1 可以压成四句话：

> **外部不确定性用 validation 处理。**

> **内部必然条件用 contract/invariant 描述。**

> **违反 contract 是程序缺陷，不应伪装成普通业务失败。**

> **UB 不是失败机制；高质量系统应该在 UB 之前建立 validation、assertion 或 fail-fast boundary。**

这构成 FM-2 讨论 `optional`、`expected`、error type 和 value-based failure 的前提。
