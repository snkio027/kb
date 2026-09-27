<a id="fm-2--value-based-failure"></a>
# FM-2 · 值通道与错误类型

> C++23 失败语义工程手册 · 系列整理候选

[返回 FM 导航](README.md) · [上一章：FM-1](fm1-contracts-assertions-ub.md) · [下一章：FM-3](fm3-exception-semantics.md) · [术语与审查约定](series-guide.md)

## 阅读入口

主讲合法 absence、失败值、错误对象和组合条件。是否恢复由策略决定；是否 strong 或 no-throw 要回到状态与完整表达式。

**主阅读线。** §1–8 → §10–16 → §19–21；先理解调用者要做什么决策，再选类型。

**失败契约。** 错误返回同样是正常返回分支；记录 T/E 构造能否抛出、错误时受保护状态是否变化，以及按值资源能否返还。

**证据边界。** 正文 T18/T19 分别检查纯内存管道与所有权返还；T06–T10/T16 在附录。它们不验证真实 I/O 或所有 monadic 重载。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、结果空间与表示](#fm2-part-1)
- [二、错误类型与传播](#fm2-part-2)
- [三、组合条件与状态责任](#fm2-part-3)
- [四、成本、反例与回查](#fm2-part-4)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm2-part-1"></a>

## 一、结果空间与表示

### 0. 文档定位

本章主讲如何把操作结果设计成值：成功值、合法 absence 和结构化错误分别携带调用者需要的信息。值通道并不要求每种失败都能就地恢复；它也可以把事实交给更高层决定拒绝或终止。

核心形式是 `SuccessValue | FailureValue`，主要通过普通 return path 传播。C++23 的主要工具之一是：

```cpp
std::expected<T, E>
```

`bool`、sentinel、enum/status、`optional` 与 `error_code` 仍有各自用途。选型依据是结果语义、调用者决策与边界，不是“越新的类型越好”。

### 1. `bool`

<a id="bool-不适合"></a>

接口片段：

```cpp
bool try_push(Item item);
```

只有该接口明确约定时，true／false 才分别表示入队成功／拒绝；失败后的 item 所有权还要单独说明。下列两个 bool 接口表达的又是不同结果：

```cpp
bool try_lock() noexcept;
bool contains(Key key) const;
```

`contains` 的 false 通常是合法的否定答案，不是一次查询失败；`try_lock` 未取得锁也可以是正常竞争结果。返回类型本身不定义 failure taxonomy。

当调用者只需要二分决策时，bool 足够；如果还需要区分不存在、权限、超时或资源耗尽，则：

```cpp
bool open();
```

会丢掉必要语义，应选择能携带原因的接口。

### 2. Sentinel

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

调用者必须额外知道：`哪些值不是普通值`

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

### 3. `std::optional<T>`

`std::optional<T>` 表达：

`T | absence`

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

<a id="核心规则"></a>

**核心规则**

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

### 4. `std::expected<T, E>`

C++23：

```cpp
std::expected<T, E>
```

直接表示：`T | E`

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

### 5. `std::expected<void, E>`

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

<a id="fm2-part-2"></a>

## 二、错误类型与传播

### 6. Error Type 设计

`expected` 的质量主要取决于：

`E 的设计`

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

<a id="61-带结构化-context"></a>

**6.1 带结构化 Context**

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

### 7. Error Identity 与 Diagnostics 分离

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

其中：`code`

用于：

```text
branching
recovery
metrics
```

而：`path / message`

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

### 8. Error Type 应位于正确抽象层

底层可能产生：`ECONNRESET`

业务层真正关心：`RepositoryError::unavailable`

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

### 9. 返回 `std::unexpected`

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

### 10. 手动传播

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

<a id="fm2-part-3"></a>

## 三、组合条件与状态责任

### 11. Monadic Composition

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

### 12. `.value()` 与 `operator*`

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

### 13. `expected` 不是引用容器

C++23 不允许：

```cpp
std::expected<T&, E>
```

实例化 `expected` 的 value type 不能是引用类型。

如果需要表达：`reference or error`

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

### 14. `expected` 不自动意味着 `noexcept`

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

因此：`value-based failure`

和：`exception-free implementation`

不是同义词。

### 15. `expected` 不自动提供 Strong Guarantee

```cpp
std::expected<void, Error> update(State& state);
```

只说明：`failure transport = expected`

并没有说明：`state after failure`

可能是：

```text
unchanged
valid but modified
partial commit
```

必须单独写入 API contract。

### 16. Ownership 必须随失败语义明确

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

<a id="fm2-part-4"></a>

## 四、成本、反例与回查

### 17. Value-Based Failure 的成本模型

值通道的对象成本可以用“分支判别信息＋T/E 的内部存储”理解，但不是标准布局公式：大小还受对齐、填充、空类型及实现策略影响，不能直接用 `tag + max(sizeof(T), sizeof(E))` 推算 ABI。

`expected` 在自身对象中保存值或错误；T/E 的构造、复制和诊断字段仍可能分配或抛出。热路径可考虑小 enum/code 与 offset/id，在边界附加详细上下文。这里是成本分析方法，没有 benchmark 结果，也不以值通道必然快于异常作为结论。

### 18. Value-Based Failure 的适用区域

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

### 19. Anti-Patterns

<a id="所有东西都返回-expected"></a>

**所有东西都返回 `expected`**

错误：

```text
programmer invariant violation
→ expected<..., InternalBug>
```

这可能隐藏 bug。

<a id="optional-吞掉错误原因"></a>

**`optional` 吞掉错误原因**

```text
network timeout
→ nullopt
```

丢失重要语义。

<a id="string-作为错误身份"></a>

**`string` 作为错误身份**

```cpp
std::expected<T, std::string>
```

可以用于小型应用，但不应默认成为大型系统错误协议。

<a id="error-type-绑定底层实现"></a>

**Error Type 绑定底层实现**

业务 API：

```cpp
std::expected<User, int /* errno */>
```

泄漏系统实现。

<a id="value-到处使用"></a>

**`.value()` 到处使用**

如果逻辑已经围绕 `expected` 设计，应正常分支或组合，而不是：

```cpp
auto x = result.value();
```

把 value-based failure 再偷偷转换成 exception。

### 20. FM-2 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

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

### 21. FM-2 核心不变量

> `optional` 表达 absence，`expected` 表达 success-or-failure。

> Value-based failure 只定义 transport，不自动定义状态保证。

> Error 应该首先是结构化机器语义，字符串主要用于 diagnostics。

> Failure type 必须与 abstraction boundary 对齐。

> Error transport 与 ownership 必须一起设计。
