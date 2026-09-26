# FM-2 — Value-Based Failure

> C++23 · Engineering Guide

[返回 C++ 目录](README.md) · [上一章：FM-1](fm1-contracts-assertions-ub.md) · [下一章：FM-3](fm3-exception-semantics.md)

## 本章目录

- [0. 文档定位](#0-文档定位)
- [1. bool](#1-bool)
- [2. Sentinel](#2-sentinel)
- [3. std::optional<T>](#3-stdoptionalt)
- [4. std::expected<T, E>](#4-stdexpectedt-e)
- [5. std::expected<void, E>](#5-stdexpectedvoid-e)
- [6. Error Type 设计](#6-error-type-设计)
- [7. Error Identity 与 Diagnostics 分离](#7-error-identity-与-diagnostics-分离)
- [8. Error Type 应位于正确抽象层](#8-error-type-应位于正确抽象层)
- [9. 返回 std::unexpected](#9-返回-stdunexpected)
- [10. 手动传播](#10-手动传播)
- [11. Monadic Composition](#11-monadic-composition)
- [12. .value() 与 operator*](#12-value-与-operator)
- [13. expected 不是引用容器](#13-expected-不是引用容器)
- [14. expected 不自动意味着 noexcept](#14-expected-不自动意味着-noexcept)
- [15. expected 不自动提供 Strong Guarantee](#15-expected-不自动提供-strong-guarantee)
- [16. Ownership 必须随失败语义明确](#16-ownership-必须随失败语义明确)
- [17. Value-Based Failure 的成本模型](#17-value-based-failure-的成本模型)
- [18. Value-Based Failure 的适用区域](#18-value-based-failure-的适用区域)
- [19. Anti-Patterns](#19-anti-patterns)
- [20. FM-2 Review Checklist](#20-fm-2-review-checklist)
- [21. FM-2 核心不变量](#21-fm-2-核心不变量)

---

## 0. 文档定位

FM-2 解决：

> 当失败属于正常、可恢复的运行时结果时，如何把它设计成一个高质量的 C++ 值？

Value-based failure 的基本形式：

```text
Result
=
SuccessValue | FailureValue
```

其特点是：

```text
失败沿普通 return path 传播
```

而不是通过异常控制流传播。

主要工具：

```text
bool
sentinel
enum/status
std::optional<T>
std::expected<T, E>
std::error_code
```

其中 C++23 的核心抽象是：

```cpp
std::expected<T, E>
```

---

## 1. `bool`

最简单的失败接口：

```cpp
bool try_push(Item item);
```

表达：

```text
true  → success
false → failure
```

当失败原因对调用者没有决策价值时，`bool` 可以是非常优秀的设计。

例如：

```cpp
bool try_lock() noexcept;
bool contains(Key key) const;
```

不要形成：

```text
现代 C++ = 所有错误都必须 expected
```

这种机械规则。

### `bool` 不适合

如果调用者需要区分：

```text
not_found
permission_denied
timeout
invalid_data
resource_exhausted
```

那么：

```cpp
bool open();
```

已经丢失必要语义。

---

## 2. Sentinel

传统接口经常：

```cpp
std::size_t find(...);
```

约定：

```text
normal index → success
npos         → not found
```

sentinel 的根本问题是：

```text
success domain
和
failure domain

共享同一个值空间
```

调用者必须额外知道：

```text
哪些值不是普通值
```

现代 API 如果能够表达为：

```cpp
std::optional<std::size_t>
```

通常具有更明确的类型语义。

但已有标准接口中的 sentinel，例如：

```cpp
std::string::npos
```

仍然是完全合法并广泛使用的设计。

---

## 3. `std::optional<T>`

`std::optional<T>` 表达：

```text
T | absence
```

例如：

```cpp
std::optional<User> find_user(UserId id);
```

表示：

```text
User exists
or
User does not exist
```

它特别适合：

```text
lookup miss
optional configuration
optional field
search result
cache miss
```

### 核心规则

> `optional` 应表达 absence，而不是把多个 failure reason 压缩成“没有值”。

例如：

```cpp
std::optional<Config> load_config();
```

如果空值可能代表：

```text
file missing
permission denied
parse failure
I/O failure
```

那么信息模型通常过弱。

---

## 4. `std::expected<T, E>`

C++23：

```cpp
std::expected<T, E>
```

直接表示：

```text
T | E
```

即：

```text
success value
or
structured failure
```

`std::expected` 本身始终处于 value 或 error 两种状态之一，不存在第三种 valueless 状态；C++23 同时提供 `and_then`、`transform`、`or_else`、`transform_error` 等 monadic operations。

例如：

```cpp
enum class ParseError {
    truncated,
    invalid_version,
    invalid_checksum,
};

std::expected<Frame, ParseError>
parse_frame(std::span<const std::byte> input);
```

接口直接表达：

```text
Frame
or
ParseError
```

---

## 5. `std::expected<void, E>`

并非所有成功操作都有返回值。

例如：

```cpp
std::expected<void, SaveError>
save(const Document& document);
```

表达：

```text
success
or
SaveError
```

比：

```cpp
bool save(...);
```

提供更丰富的失败语义。

---

## 6. Error Type 设计

`expected` 的质量主要取决于：

```text
E 的设计
```

而不是 `expected` 本身。

最简单：

```cpp
enum class ParseError {
    truncated,
    invalid_header,
    unsupported_version,
};
```

适合：

```text
错误类别有限
不需要额外 context
错误对象需要非常轻量
```

---

### 6.1 带结构化 Context

如果 recovery 或 diagnostics 需要更多信息：

```cpp
struct ParseError {
    enum class Code {
        truncated,
        invalid_field,
        unsupported_version,
    };

    Code code;
    std::size_t offset;
};
```

这比：

```cpp
std::string error;
```

更适合机器决策。

---

## 7. Error Identity 与 Diagnostics 分离

推荐：

```text
structured code
+
optional diagnostic context
```

例如：

```cpp
struct FileError {
    FileErrorCode code;
    std::filesystem::path path;
};
```

其中：

```text
code
```

用于：

```text
branching
recovery
metrics
```

而：

```text
path / message
```

用于：

```text
diagnostics
logging
```

不要让：

```cpp
if (error.message == "file not found")
```

成为程序控制流。

---

## 8. Error Type 应位于正确抽象层

底层可能产生：

```text
ECONNRESET
```

业务层真正关心：

```text
RepositoryError::unavailable
```

因此：

```text
OS error
    ↓
transport error
    ↓
repository error
```

可以发生 translation。

但只有：

> 抽象语义真正变化时才翻译。

不要每一层机械包装一次错误。

---

## 9. 返回 `std::unexpected`

典型模式：

```cpp
std::expected<Frame, ParseError> parse_frame(...) {
    if (input.empty()) {
        return std::unexpected(ParseError::truncated);
    }

    return Frame{...};
}
```

成功值：

```cpp
return Frame{...};
```

错误：

```cpp
return std::unexpected(error);
```

让两个通道在类型上明确区分。

---

## 10. 手动传播

C++23 没有 Rust `?` 一样的语言级传播操作符。

典型：

```cpp
auto header = parse_header(input);

if (!header) {
    return std::unexpected(header.error());
}

return decode(*header);
```

重要的是：

> 不要在每一层为了传播而重新创造无意义错误。

如果错误类型相同，直接传播即可。

---

## 11. Monadic Composition

`and_then` 的回调返回 `expected`，而且其 `error_type` 必须与当前对象相同；`or_else` 则须保留 `value_type`。还要根据对象的 cv/ref 类别检查回调参数以及成功值、错误值的构造要求。它们不是任意类型或错误域的自动连接器。[N4950：expected.object.monadic](https://timsong-cpp.github.io/cppwp/n4950/expected.object.monadic)

| 操作 | 用途 | 不应忽略的条件 |
| --- | --- | --- |
| `transform` | 转换成功值 | 错误传播及结果类型必须可构造 |
| `and_then` | 下一步也返回 `expected` | 保持 `error_type` |
| `transform_error` | 显式转换错误域 | 转换后的错误类型及成功值传播必须有效 |
| `or_else` | 失败分支返回另一个 `expected` | 保持 `value_type`；是否恢复成功仍由策略决定 |

完整正例 T18 使用纯内存替身展示 read → parse → validate，**不测试文件 I/O**。只有 read 的低层错误在边界转换，后续两步统一使用 `ConfigError`：

<!-- fm-test {"id":"T18","mode":"run","feature":"expected-monadic"} -->
```cpp
#include <expected>
#include <string_view>

enum class FileError { missing };
enum class ConfigError { input, parse, invalid };
struct Config { int port; };

std::expected<std::string_view, FileError> read_file(std::string_view path) {
    if (path == "missing") return std::unexpected(FileError::missing);
    if (path == "bad") return "not-a-number";
    if (path == "zero") return "0";
    return "8080";
}
std::expected<Config, ConfigError> parse_config(std::string_view data) {
    if (data == "8080") return Config{8080};
    if (data == "0") return Config{0};
    return std::unexpected(ConfigError::parse);
}
std::expected<Config, ConfigError> validate_config(Config value) {
    if (value.port == 0) return std::unexpected(ConfigError::invalid);
    return value;
}
std::expected<Config, ConfigError> load_config(std::string_view path) {
    return read_file(path)
        .transform_error([](FileError) { return ConfigError::input; })
        .and_then(parse_config)
        .and_then(validate_config);
}
int main() {
    auto good = load_config("good");
    auto missing = load_config("missing");
    auto bad = load_config("bad");
    auto zero = load_config("zero");
    return good && good->port == 8080
        && !missing && missing.error() == ConfigError::input
        && !bad && bad.error() == ConfigError::parse
        && !zero && zero.error() == ConfigError::invalid ? 0 : 1;
}
```

若用 `or_else` 选择备用配置，当前层必须有资格决定 fallback，并检查备用操作本身的失败。不同 E 直接串联的编译失败反例与最小转换正例见 [T08 / T09](review/fm-verification-samples.md#t08)。

---

## 12. `.value()` 与 `operator*`

本节按 C++23 最终草案 N4950 的 `expected<T, E>`（非 void）重载说明：

| 访问 | 条件与失败行为 |
| --- | --- |
| `value() &` / `value() const &` | Mandates 要求 E 可复制构造；无值时构造并抛出 `bad_expected_access<E>` |
| `value() &&` / `value() const &&` | 同样要求 E 可复制，另须能从该重载的 `std::move(error())` 构造 E |
| `operator*` / `operator->` | 使用前须已确立 `has_value() == true`；不是带运行时错误报告的检查访问 |
| `error()` | 使用前须已确立 `has_value() == false` |

这些类型要求不因当前对象恰好含值而消失。构造异常对象时复制／移动 E 本身也可能抛异常，因此不能把可观察异常集合概括为只有 `bad_expected_access<E>`。[N4950：expected.object.obs](https://timsong-cpp.github.io/cppwp/n4950/expected.object.obs)、[LWG 3843](https://cplusplus.github.io/LWG/issue3843)

对于 §16 的 move-only 错误对象，先检查状态再访问相应分支，不靠 `std::move(result).value()` 绕过规范要求。完整正反例为 [T06～T10](review/fm-verification-samples.md#t06) 和 [T16](review/fm-verification-samples.md#t16)。

附件报告观察到 libstdc++ 14 接受 T16；这是相对于所选 N4950 基线的实现差异，不是可移植许可。本机结果另记在[修订与验证记录](review/fm-review-7869082.md)，不覆盖历史观测。

---

## 13. `expected` 不是引用容器

C++23 不允许：

```cpp
std::expected<T&, E>
```

实例化 `expected` 的 value type 不能是引用类型。

如果需要表达：

```text
reference or error
```

可以考虑：

```cpp
std::expected<std::reference_wrapper<T>, E>
```

或者根据 ownership/lifetime 语义使用：

```cpp
T*
```

但必须明确：

```text
nullability
lifetime
ownership
```

---

## 14. `expected` 不自动意味着 `noexcept`

例如：

```cpp
std::expected<std::string, Error> load();
```

内部仍然可能因为：

```text
allocation
copy
move
error construction
```

抛异常。

甚至 `expected` 自己的某些操作也依赖 `T` 和 `E` 的构造/移动属性。

因此：

```text
value-based failure
```

和：

```text
exception-free implementation
```

不是同义词。

---

## 15. `expected` 不自动提供 Strong Guarantee

```cpp
std::expected<void, Error> update(State& state);
```

只说明：

```text
failure transport = expected
```

并没有说明：

```text
state after failure
```

可能是：

```text
unchanged
valid but modified
partial commit
```

必须单独写入 API contract。

---

## 16. Ownership 必须随失败语义明确

按值接收 `std::unique_ptr<Job>` 意味着调用时所有权进入参数。失败后是销毁、保留在队列，还是返还调用者，必须属于 API 契约。

若失败时要同时返还原因与任务，可把任务放进错误对象。完整正例 T19 只模拟拒绝入队，不实现真实队列：

<!-- fm-test {"id":"T19","mode":"run","feature":"expected"} -->
```cpp
#include <expected>
#include <memory>
#include <utility>

struct Job { int id; };
enum class SendError { queue_full };
struct SendFailure {
    SendError error;
    std::unique_ptr<Job> job;
};
std::expected<void, SendFailure> reject(std::unique_ptr<Job> job) {
    return std::unexpected(SendFailure{SendError::queue_full, std::move(job)});
}
int main() {
    auto job = std::make_unique<Job>(Job{7});
    auto* identity = job.get();
    auto result = reject(std::move(job));
    if (job || result) return 1;
    auto failure = std::move(result.error()); // 已知当前是错误分支。
    job = std::move(failure.job);
    return failure.error == SendError::queue_full
        && job.get() == identity && job->id == 7 ? 0 : 2;
}
```

错误对象因此是 move-only。继续组合时也必须检查所选重载能否移动／复制错误；`value()` 的特殊要求见 [§12](#12-value-与-operator)。这里的所有权保证来自具体实现，不是 `expected` 自动提供的。

---

## 17. Value-Based Failure 的成本模型

通常：

```text
success/error discriminator
+
max(sizeof(T), sizeof(E))
```

构成主要对象存储模型。

`std::expected` 自身将 value/error 存储在对象内部；但 `T` 和 `E` 自己当然仍可能动态分配。

因此热路径 error type 应避免无理由携带：

```text
large strings
large containers
heavy diagnostic objects
```

更常见：

```text
small enum/code
+
offset/id
```

详细 context 可以在边界层附加。

---

## 18. Value-Based Failure 的适用区域

优先考虑：

```text
high-frequency failure
parsing
validation
lookup
network protocol outcomes
storage operations
explicit business failures
```

尤其适合：

> 调用者自然需要立即根据失败类别分支。

---

## 19. Anti-Patterns

### 所有东西都返回 `expected`

错误：

```text
programmer invariant violation
→ expected<..., InternalBug>
```

这可能隐藏 bug。

### `optional` 吞掉错误原因

```text
network timeout
→ nullopt
```

丢失重要语义。

### `string` 作为错误身份

```cpp
std::expected<T, std::string>
```

可以用于小型应用，但不应默认成为大型系统错误协议。

### Error Type 绑定底层实现

业务 API：

```cpp
std::expected<User, int /* errno */>
```

泄漏系统实现。

### `.value()` 到处使用

如果逻辑已经围绕 `expected` 设计，应正常分支或组合，而不是：

```cpp
auto x = result.value();
```

把 value-based failure 再偷偷转换成 exception。

---

## 20. FM-2 Review Checklist

```text
[ ] absence 与 failure 是否区分？
[ ] bool 是否足够表达调用者所需信息？
[ ] sentinel 是否有更清晰的类型替代？
[ ] expected 的 E 是否结构化？
[ ] error identity 与 diagnostic text 是否分离？
[ ] error type 是否位于正确抽象层？
[ ] error translation 是否真正改变语义？
[ ] expected 是否被误认为 noexcept？
[ ] failure state guarantee 是否单独定义？
[ ] failure 后 ownership 是否明确？
[ ] 高频路径 error object 是否足够轻量？
[ ] monadic chain 的 cv/ref、值／错误类型与构造要求是否满足？
[ ] move-only 错误对象是否避免了不满足 Mandates 的 value() 调用？
[ ] monadic chain 是否保持了清晰的 recovery boundary？
```

---

## 21. FM-2 核心不变量

> `optional` 表达 absence，`expected` 表达 success-or-failure。

> Value-based failure 只定义 transport，不自动定义状态保证。

> Error 应该首先是结构化机器语义，字符串主要用于 diagnostics。

> Failure type 必须与 abstraction boundary 对齐。

> Error transport 与 ownership 必须一起设计。

---

---
