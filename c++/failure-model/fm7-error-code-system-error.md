<a id="fm-7--error_code-system_error--os-failure"></a>
# FM-7 · 系统错误与领域转换

> C++23 失败语义工程手册 · 系列整理候选

[返回 FM 导航](README.md) · [上一章：FM-6](fm6-construction-destruction-allocation.md) · [下一章：FM-8](fm8-failure-boundaries.md) · [术语与审查约定](series-guide.md)

## 阅读入口

主讲 errno、error_code/error_condition、system_error 与领域错误的身份转换；不由原生错误名称直接决定业务恢复。

**主阅读线。** §1–7 → §10–14 → §15–16；值通道组合回查 FM-2，重试协议回查 FM-8。

**失败契约。** 先确认原接口失败再保存错误，保留 category 与必要 cause；错误翻译可能分配，error_code 参数也不自动封闭全部异常通道。

**证据边界。** T15 只查询具体库签名；T20 检查 open 的返回值与选项。它们不穷举平台错误映射、路径分配或恢复策略。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、原生错误身份](#fm7-part-1)
- [二、通道、领域与上下文](#fm7-part-2)
- [三、审查与回查](#fm7-part-3)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm7-part-1"></a>

## 一、原生错误身份

### 0. 文档定位

FM-7 解决系统编程中的底层失败表示：

```text
errno
OS error
std::error_code
std::error_condition
std::system_error
domain translation
```

目标不是把整个程序都改成 `error_code`，而是：

> 正确把 OS failure 引入现代 C++ Failure Model。

### 1. `errno`

POSIX API 常见：

```cpp
int fd = ::open(...);

if (fd == -1) {
    int error = errno;
}
```

关键规则：

> 只有在 API 明确定义失败并设置 `errno` 后，才读取它。

并且应尽快保存：

```cpp
const int error = errno;
```

因为后续 library/system calls 可能改变它。

### 2. 不要把 `errno` 当全局 Error Object

错误：

```text
call A
call B
...
later read errno
```

无法保证它仍对应 A。

正确模型：

```text
detect failure
↓
capture errno immediately
↓
translate
```

### 3. `std::error_code`

核心结构可以理解为：

```text
integer value
+
error category identity
```

因此：`value = 2`

本身没有足够语义。

需要：`category`

一起解释。

### 4. `error_code` 的价值

它非常适合：

```text
OS failure
library error domains
non-throwing system APIs
cross-layer low-level error transport
```

并具有：`small value-like object`

的工程性质。

### 5. `std::errc`

标准提供一组可移植的错误条件：

```cpp
std::errc::permission_denied
std::errc::timed_out
std::errc::no_such_file_or_directory
```

它们让代码可以表达：`portable condition`

而不是绑定某个平台整数。

### 6. `error_code` vs `error_condition`

`error_code` 保存具体值及 category 身份；`error_condition` 表达一般化条件，是否等价由 category 的映射／比较语义决定。一个平台 socket 错误可以对应 connection_refused，但不能只比整数，也不能把任意 category 的同值错误视为同一种情况。

这是错误表示层的关系，不决定是否恢复或重试。错误对象有效，不代表被操作的文件、事务或远端状态也仍满足成功不变量。

<a id="fm7-part-2"></a>

## 二、通道、领域与上下文

### 7. `std::system_error`

当项目选择 exception propagation：

```cpp
throw std::system_error{ec, "open socket"};
```

可以把：`std::error_code`

带入 exception channel。

于是：

```text
representation
    error_code

transport
    exception
```

再次说明：

> Error identity 和 transport mechanism 是两个不同维度。

### 8. Value-Based 系统 API

另一种：

```cpp
std::expected<File, std::error_code>
open_file(const Path& path);
```

非常适合作为：`low-level infrastructure API`

但更高层可能应翻译：

```cpp
std::expected<Config, ConfigError>
load_config(...);
```

而不是一路暴露 native error。

### 9. Error Domain

每个 library/subsystem 可以拥有自己的：`error category/domain`

例如：

```text
filesystem
network
database client
protocol decoder
```

但不要因为技术上能建立 custom `error_category` 就全部使用。

简单领域错误：

```cpp
enum class ParseError
```

可能更加清晰。

### 10. 底层错误不能直接决定业务策略

例如：`ETIMEDOUT`

不自动等于：`retry`

上层还要知道：

```text
idempotent?
deadline?
retry budget?
shutdown?
operation already committed?
```

所以：`system error`

只是事实，

不是：`recovery policy`

### 11. Error Translation 示例

```text
ECONNRESET
    ↓
HttpClientError::connection_lost
    ↓
RepositoryError::unavailable
```

到业务层：`Repository unavailable`

通常比：`ECONNRESET`

具有更稳定的抽象意义。

### 12. Preserve Cause

Translation 不应完全摧毁 diagnostics。

可以：

```cpp
struct RepositoryError {
    RepositoryErrorCode code;
    std::error_code cause;
};
```

或者在 logging/tracing context 中保留：`native cause`

这样兼顾：

```text
business semantics
+
low-level diagnosis
```

### 13. Error Context

错误对象可以包含：

```text
operation
resource identity
offset
endpoint
path
partition
```

但需注意：

```text
PII
secret
credential
large allocation
```

不要无控制将敏感或巨大 context 塞进 error。

### 14. API 双版本模式

带 `error_code&` 的重载可按具体契约报告指定的操作错误，**不自动保证整个调用不抛异常**。文件系统接口的底层错误通道与其他异常条件应分别查看。[N4950：fs.err.report](https://timsong-cpp.github.io/cppwp/n4950/fs.err.report)

例如，N4950 的 `current_path(error_code&)` 查询重载返回 path，未声明 `noexcept`；设置重载 `current_path(const path&, error_code&)` 则声明了 `noexcept`。还须区别函数本身与构造实参、返回后使用结果的完整表达式。[N4950：fs.op.current.path](https://timsong-cpp.github.io/cppwp/n4950/fs.op.current.path)

[T15](review/fm-verification-samples.md#t15) 只用 `noexcept` 查询签名，不实际改变工作目录。查询版的负向结果是当前库观测；不将其强制为所有实现的要求。

项目是否提供双版本，应权衡接口面积、测试与文档成本，不必机械模仿标准库。

<a id="fm7-part-3"></a>

## 三、审查与回查

### 15. FM-7 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

```text
[ ] errno 是否在失败后立即保存？
[ ] 是否只在文档规定设置 errno 的失败后读取？
[ ] native error 是否泄漏到不该知道它的业务层？
[ ] error_code 是否比简单 enum 真有价值？
[ ] error translation 是否改变了 abstraction semantics？
[ ] low-level cause 是否保留用于 diagnostics？
[ ] timeout 是否被错误地自动等价成 retry？
[ ] system_error exception 是否符合当前 exception policy？
[ ] error context 是否包含敏感信息？
```

### 16. FM-7 核心不变量

> OS error 首先是事实，不是 recovery policy。

> `error_code` 表示错误身份，exception/expected 决定传播方式。

> Native errors 应在适当 abstraction boundary 翻译。

> Error translation 应提升语义，同时尽量保留诊断 cause。
