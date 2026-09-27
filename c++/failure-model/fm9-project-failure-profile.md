<a id="fm-9--project-level-failure-profile"></a>
# FM-9 · 项目失败契约与验证

> C++23 失败语义工程手册 · 系列整理候选

[返回 FM 导航](README.md) · [上一章：FM-8](fm8-failure-boundaries.md) · [术语与审查约定](series-guide.md)

## 阅读入口

把 FM-0～FM-8 的机制压缩为项目可以选择、填写和验证的合同。这里的 must/default 是待采纳政策，不是 C++ 的统一语言要求。

**主阅读线。** §1–3 → §9–17 → §21–30；需要时回查各机制政策及最后总图。

**失败契约。** 项目逐项采纳错误通道、状态、所有权和恢复权限；模板要包含提交前后及完成未知，并给每个重要主张配对应判据和未测项。

**证据边界。** 故障注入清单是待项目执行的验证设计；FM 样例通过不等于某项目已验证，也不表示已部署 CI 或获得正式基线批准。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、项目选择与责任](#fm9-part-1)
- [二、通道与错误域政策](#fm9-part-2)
- [三、状态、所有权与边界政策](#fm9-part-3)
- [四、恢复与可观测性政策](#fm9-part-4)
- [五、验证工具与证据](#fm9-part-5)
- [六、可裁剪模板与回查](#fm9-part-6)
- [最终总图](#modern-c-failure-model--最终总图)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm9-part-1"></a>

## 一、项目选择与责任

### 0. 文档定位

FM-0 ～ FM-8 描述语言与系统机制。

本章是**待采纳的工程 profile 模板**，不是已批准项目基线。下文“必须／不得／默认”等政策措辞仅约束明确采纳该 profile 的项目；语言与库规则另有标准依据。解析拒绝倾向 expected、析构不传播异常等默认策略，不能冒充所有 C++ 程序统一适用的规范事实。

FM-9 的目标是：

> 将这些规则压缩成一个项目真正可以执行的 Failure Profile。

如果没有统一 profile，工程最终容易变成：

```text
模块 A 用 exception
模块 B 用 bool
模块 C 用 expected<string>
模块 D 用 errno
模块 E catch(...)
模块 F abort()
```

每种单独看可能合理，

组合后却没有一致系统语义。

### 1. Failure Profile 应解决什么

项目必须统一回答：

```text
什么是 domain outcome？
什么是 recoverable failure？
什么是 programmer error？
哪些 API 可以 throw？
哪些 API 使用 expected？
哪些 boundary 禁止 exception？
哪些 invariant release 也必须检查？
哪些操作提供 strong/basic guarantee？
哪些 failure 可以 retry？
何时 terminate？
```

### 2. 推荐项目分类

以下是项目的处置标签，不是互斥且完整的原因分类。P 描述责任，F 描述严重性／终局处置；同一事件可能同时是 P 与 F。选定恢复／终止策略时应保留来源、频率和状态等独立信息。

```text
D — Domain Outcome
R — Recoverable Operational Failure
P — Programmer / Contract Failure
F — Fatal System Failure
```

<a id="d--domain-outcome"></a>

**D — Domain Outcome**

例如：

```text
not found
queue empty
optional field missing
EOF
```

默认：

```text
optional
bool
enum
```

<a id="r--recoverable-failure"></a>

**R — Recoverable Failure**

例如：

```text
invalid external input
I/O failure
network timeout
configuration rejection
resource unavailable
```

默认：

```text
expected<T, E>
error_code
exception where project policy allows
```

<a id="p--programmer-error"></a>

**P — Programmer Error**

例如：

```text
precondition violation
invalid internal index
broken state-machine invariant
double ownership
```

默认：

```text
assert
production fatal check where necessary
```

不应默认：`expected<..., Bug>`

<a id="f--fatal-failure"></a>

**F — Fatal Failure**

例如：

```text
central invariant corruption
unrecoverable process state
exception escaping noexcept
critical runtime corruption
```

默认：

```text
terminate
abort
process-level fail-fast policy
```

### 3. 推荐 Layer Policy

可以定义：

| Layer | 默认 Failure Style |
|---|---|
| Parser / Validation | `std::expected<T, E>` |
| Domain lookup | `std::optional<T>` / `expected` |
| Core trusted algorithms | Preconditions + assertions |
| Resource wrappers | RAII + constructor/factory |
| OS abstraction | `error_code` / `expected` |
| Application orchestration | `expected` 或 exception，根据项目统一政策 |
| Thread entry | Catch/contain unexpected exception |
| C/plugin ABI | Explicit status/error object |
| RPC boundary | Serialized structured errors |
| Fatal invariant boundary | Fail-fast |

<a id="fm9-part-2"></a>

## 二、通道与错误域政策

### 4. Exception Policy

项目必须明确选择。

例如：

```text
Exceptions:
    enabled

Allowed:
    construction failure
    rare infrastructure failure
    orchestration propagation

Not allowed:
    parser rejection
    normal lookup miss
    hot-path control flow

Must not cross:
    thread entry
    C ABI
    plugin ABI
    RPC
```

或者：

```text
Application code:
    exception-free by policy

Third-party exceptions:
    caught and translated at adapter boundary
```

关键不是哪一种绝对最好，

而是：

> policy 必须一致。

### 5. `expected` Policy

推荐规定：

```text
Use expected when:
    failure is expected at runtime
    caller can meaningfully branch/recover
    failure belongs to API result domain
```

避免：`every function returns expected`

特别是：`private helper whose preconditions are already established`

不需要重新包装 internal impossible state。

### 6. Error Type Policy

推荐：

```text
error identity:
    enum / structured code

diagnostic context:
    structured fields

human text:
    produced at diagnostic boundary
```

避免默认：

```cpp
std::expected<T, std::string>
```

成为跨大型系统统一协议。

### 7. Error Namespace

可以：

```cpp
namespace parser {

enum class ErrorCode {
    truncated,
    invalid_header,
};

struct Error {
    ErrorCode code;
    std::size_t offset;
};

}
```

不同 subsystem：

```text
parser::Error
storage::Error
network::Error
```

不要创建一个无限膨胀：

```cpp
enum class GlobalError {
    ...
};
```

### 8. Error Translation Policy

规定：

> 只有跨越 abstraction boundary 时翻译。

例如：

```text
socket error
↓
HTTP client error
↓
repository unavailable
```

不要：

```text
每一个函数层次
↓
创建新 Error wrapper
```

<a id="fm9-part-3"></a>

## 三、状态、所有权与边界政策

### 9. State Guarantee Policy

本节是待项目采纳的 profile 建议，不是所有 C++ API 的语言要求。建议每个重要的 mutating API 分别声明：

| 维度 | 合同内容 |
| --- | --- |
| 失败后状态 | strong、basic、明确部分进度或其他具体语义 |
| 异常传播 | 是否允许异常越界；是否具有 `noexcept` 规格 |
| 资源与所有权 | 失败后资源属于谁，哪些清理动作有保证 |
| 终局策略 | 无法继续时升级、重启或终止的范围 |

例如 `update(Config)` 返回 `expected<void, UpdateError>` 时，仍须单独说明“失败时旧配置不变”，或者“保留哪些部分进度且哪些不变量继续成立”。不从返回类型推出 strong，不从 `noexcept` 推出 no-fail，也不把 termination 排为状态保证的一级。

精确定义及 commit 条件见 [FM-4 §4～§5](fm4-raii-exception-safety.md#4-exception-safety-guarantees)。

### 10. Ownership Failure Policy

任何 transferring API 都必须说明：

```text
ownership before call
ownership after success
ownership after failure
```

例如：`enqueue(Job job)`

和：`try_enqueue(Job& job)`

具有完全不同的 failure ownership semantics。

### 11. `noexcept` Policy

推荐：

```text
Destructors:
    must not propagate exceptions

Move operations:
    noexcept when semantically true

Swap:
    non-throwing and truly non-failing under commit preconditions

Cleanup:
    noexcept

Leaf arithmetic / trivial accessors:
    noexcept where contract truly permits

Do not:
    add noexcept merely for performance
```

### 12. Assertion Policy

项目可以定义两种检查；这里的 development/production 是部署政策，不是语言按构建名称自动切换的行为。标准 `assert` 是否启用取决于包含头文件时的 `NDEBUG`，见 [FM-1 §13](fm1-contracts-assertions-ub.md#13-ndebug)。

<a id="development-assertion"></a>

**Development Assertion**

```text
enabled in the project's chosen development configuration
internal reasoning
cheap diagnostics
```

例如：

```cpp
assert(index < size);
```

<a id="production-fatal-check"></a>

**Production Fatal Check**

用于：

```text
release must enforce
continuing could corrupt persistent/external state
security-sensitive invariant
central internal invariant
```

应由项目统一宏/函数提供：

```text
CHECK
ENSURE
FATAL_IF
```

具体名字不是重点。

### 13. UB Policy

项目原则：`UB is never a failure-handling strategy.`

应该：

```text
validate untrusted input
assert trusted preconditions
use sanitizers
use static analysis
use ownership/lifetime discipline
```

目标是：`prevent UB`

而不是：`recover from UB`

### 14. Boundary Policy

必须列出所有重要边界：

```text
thread
coroutine task
event loop
C ABI
plugin ABI
IPC
RPC
process main
```

每个边界写明：

```text
incoming failure forms
outgoing failure forms
exception policy
logging responsibility
failure domain
```

<a id="fm9-part-4"></a>

## 四、恢复与可观测性政策

### 15. Retry Policy

项目统一规定：`retry only when category is retryable`

同时检查：

```text
idempotency
deadline
attempt count
backoff
jitter
shutdown
system load
```

禁止基础库：`while (!success) retry();`

### 16. Timeout Policy

Timeout 应明确：`deadline expired`

但不能自动断言：`remote operation failed before commit`

对于有外部副作用的操作：`timeout semantics`

必须说明：

```text
definitely not committed
possibly committed
definitely committed
```

如果无法知道：`ambiguous`

应直接建模。

### 17. Cancellation Policy

推荐作为独立 outcome：

```text
success
failure
cancelled
```

尤其：

```text
worker shutdown
async operation
coroutine
RPC
```

避免把正常 shutdown 变成错误风暴。

### 18. Logging Policy

基本原则：

```text
errors are propagated many times
but usually logged once
```

通常：

```text
detection layer:
    produce structured error

intermediate layer:
    enrich context

recovery/terminal boundary:
    log
```

### 19. Metrics Policy

Metrics 应按：

```text
error category
operation
component
recovery action
```

聚合。

避免使用：`raw error message`

作为 metric label，

否则容易产生：`unbounded cardinality`

### 20. Diagnostics Policy

最终 diagnostics 可以组合：

```text
error code
cause chain
operation
resource identity
request/job ID
location
context
```

但要明确：

```text
secret redaction
PII policy
size limits
```

<a id="fm9-part-5"></a>

## 五、验证工具与证据

### 21. Testing Failure Paths

Failure path 必须是：`first-class test target`

而不是只测试 success path。

至少包括：

```text
invalid input
allocation/resource failure where injectable
I/O error
timeout
cancellation
partial progress
throwing T in generic code
thread exception
shutdown race
```

### 22. Fault Injection

高质量组件应允许测试：

```text
fail allocation N
fail write N
timeout operation N
disconnect after commit
throw during element move
```

这样才能验证：

```text
strong/basic guarantee
cleanup
retry
failure domain
```

### 23. Sanitizers

Failure Model 无法替代：

```text
ASan
UBSan
TSan
```

这些主要帮助发现：

```text
memory safety
UB
data race
```

它们属于：`defect detection infrastructure`

而不是 runtime recovery system。

### 24. Static Analysis

推荐结合：

```text
clang-tidy
compiler warnings
lifetime-oriented checks
nodiscard
concepts
type system
```

尽可能将：

```text
failure handling omission
invalid state
ownership bug
```

提前到开发阶段。

### 25. `[[nodiscard]]`

对必须观察的结果可使用 `[[nodiscard]]`：

```cpp
[[nodiscard]]
std::expected<void, Error> save();
```

若写成：

```cpp
save();
```

C++23 的规定是建议实现对这类被丢弃的结果发出警告，不是必须拒绝编译，也不是结果一定会被处理的静态证明。显式转换为 void 又属于不同情况。项目可通过告警选项和评审加强执行，但必须另外说明，不能归到语言强制保证。[N4950：dcl.attr.nodiscard](https://timsong-cpp.github.io/cppwp/n4950/dcl.attr.nodiscard)

<a id="fm9-part-6"></a>

## 六、可裁剪模板与回查

### 26. Public API Failure Documentation Template

本模板是[公共 C1–C8](series-guide.md#review-contract)的唯一可填写版本；按 API 风险裁剪，不机械要求所有局部函数都有 RPC 或重试字段。

```markdown
### Failure Contract

Operation / observation scope:
- API、版本、受保护状态及外部副作用范围。

C1 — Inputs and success:
- 前置条件及建立者；合法领域结果；成功后置条件。

C2 — Failure set and channels:
- 每个失败来源、检测点、返回错误／异常／终止。
- 错误转换及诊断路径自身能否失败。

C3 — State transitions and failure postconditions:
- 准备阶段、提交点、返回／清理阶段。
- 每个失败分支的状态、不变量、部分进度。
- 明确未提交／已提交／完成未知；调用者如何得知。

C4 — Ownership and cleanup:
- 调用前、成功、失败、取消之后资源各属谁。
- 析构后备与需要显式观察的 finish/close/commit。

C5 — Composition:
- T/E、allocator、参数、回调、临时对象、返回与清理的前提。
- 异常传播保证与 no-fail/状态保证分别声明。

C6 — Recovery and containment:
- 恢复／补偿／升级／终止权限、failure domain。
- 线程安全、同步与错误观察点、报告失败后备。

C7 — Retry and control outcomes:
- 幂等／去重／确认依据、截止期、预算、关闭状态。
- 取消请求与确认、超时、完成未知的处置。

C8 — Verification:
- 命题、判据、注入点、错误变体、预期与实际结果。
- 工具链、平台、SKIP、不适用项、未覆盖边界。
```

### 27. Subsystem Failure Profile Template

```markdown
## Failure Profile

### Error Types

- ...

### Exception Policy

- ...

### Validation Boundary

- ...

### Recovery Boundary

- ...

### Failure Domain

- ...

### State Guarantees

- ...

### Retry / Timeout

- ...

### Logging / Metrics

- ...

### Fatal Invariants

- ...
```

### 28. Project-Wide Baseline

推荐默认：

```text
External input
    → validate

Normal absence
    → optional

Expected recoverable failure
    → expected

OS/native failure
    → error_code at low layer
    → translate when abstraction changes

Rare deep failure
    → exception only if project profile permits

Programmer error
    → assert / fatal check

Unrecoverable invariant loss
    → fail-fast

Resources
    → RAII

Mutating operations
    → document strong/basic guarantee

Move/swap/cleanup
    → noexcept where semantically true

Threads/ABI/RPC
    → explicit failure boundaries
```

### 29. Project Anti-Patterns

禁止形成：`exceptions everywhere`

或者：`expected everywhere`

或者：`no exceptions at all costs`

这些都是机制驱动设计。

正确顺序：

```text
failure semantics
↓
responsibility
↓
state guarantee
↓
boundary
↓
frequency
↓
transport mechanism
```

### 30. Project Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

```text
[ ] 项目是否有统一 failure taxonomy？
[ ] domain outcome / operational failure / programmer error 是否分离？
[ ] exception policy 是否明确？
[ ] expected 使用边界是否明确？
[ ] errors 是否结构化？
[ ] error translation 是否按 abstraction boundary？
[ ] public mutating APIs 是否定义 state guarantee？
[ ] ownership failure semantics 是否明确？
[ ] noexcept policy 是否明确，且未与 no-fail 或 strong/basic 混为一谈？
[ ] assert 与 production fatal check 是否区分？
[ ] UB 是否被明确视为 defect 而非 failure channel？
[ ] thread / ABI / RPC boundary 是否明确，并覆盖错误报告自身的失败？
[ ] cancellation / timeout / shutdown 是否单独建模？
[ ] retry 是否有 idempotency + deadline + budget？
[ ] logging 是否集中在 recovery/terminal boundary？
[ ] error metrics 是否避免高 cardinality？
[ ] failure paths 是否有测试？
[ ] 是否支持关键 fault injection？
[ ] sanitizer/static analysis 是否进入 CI？
```

### 31. FM-9 核心不变量

项目采纳 profile 时，应固定错误通道、状态保证、所有权、恢复权限和验证责任。选择机制在理解失败语义之后，不能从 `expected` 或 `noexcept` 倒推保证。

责任、可恢复性和终局处置分别记录：程序缺陷可能同时需要致命处置，运行时失败也未必可恢复。它们不是互斥的三个错误类别。线程、ABI、RPC 的转换以及 retry、timeout、cancellation、shutdown 均要按系统合同分析，而不是留给底层自行猜测。

## Modern C++ Failure Model — 最终总图

把一次操作沿同一条链审查；状态、传播和处置分轴记录，不把不可恢复放进 strong/basic 的等级中：

```text
Operation + Preconditions + Success Postcondition
                 ↓
Possible outcomes / detection
                 ↓
Representation → translation → propagation
                 ↓
State transition audit
    ├─ protected state: unchanged / valid-but-changed / partial / unspecified
    ├─ resources: ownership / cleanup / outstanding obligation
    ├─ commit: before / after / observer cannot determine
    └─ exception channel: allowed / non-propagating boundary
                 ↓
Recovery authority + failure domain
    ├─ reject / recover / compensate / retry under protocol
    └─ escalate / terminate if continued execution is not trustworthy
                 ↓
Observable evidence + limits
```

责任、发生频率、严重性和恢复权限分别作为决策输入。错误传播只是把事实带到决策点；资源清理不代替回滚，捕获不代替恢复，终止不代替 no-fail 提交。

全系列最终回查顺序是：FM-0 定义模型，FM-1 建立输入前提，FM-2/FM-3 选择值或异常通道，FM-4 分析状态，FM-5/FM-6 核查泛型与生命周期，FM-7 转换错误域，FM-8 限定传播与恢复，最后在本章记录项目选择和证据。具体问题入口见 [FM 总导航](README.md)，共同词义见[系列阅读约定](series-guide.md)。

这是待项目选择和验证的工程框架，不是对全部代码的技术认证，也不因本轮系列整理而成为已批准项目规范。
