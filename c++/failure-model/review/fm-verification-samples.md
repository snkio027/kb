# FM 定向验证样例

仅服务 FM-0～FM-9 的关键命题，不是全部代码块的验证集。负例不能当作生产实现执行；运行方式和隔离边界见[修订与验证记录](fm-review-7869082.md)。

T01～T16 来自用户提供的 `FM-Verification-Evidence-7869082.md`，原始 16 段源码已逐一核对附件所列 SHA-256。本文件接收的是测试源码，不把附件的 Linux 结果当成本机结果。T12 的单一维护源在 [FM-8 §2](../fm8-failure-boundaries.md#2-stdthread)，T14 在 [FM-5 §3](../fm5-noexcept-move-copy.md#3-noexceptexpr)。

T17～T19 分别在 [FM-5 §7](../fm5-noexcept-move-copy.md#7-copy-与-failure)、[FM-2 §11](../fm2-value-based-failure.md#11-monadic-composition)、[FM-2 §16](../fm2-value-based-failure.md#16-ownership-必须随失败语义明确)，直接从正文提取，不维护另一份手写副本。T20 是本轮新增的 POSIX 验证。

## T01

原 out_of_range 表达式：预期编译失败。来源性质：`source-derived`；关联位置：FM-1 section 23。

<!-- fm-test {"id":"T01","mode":"compile_fail","diagnostics":["out_of_range","no matching|no viable|requires.*argument"]} -->
```cpp
#include <stdexcept>
void example() { throw std::out_of_range{}; }
```

## T02

修正后的 out_of_range：完整正例。来源性质：`proposed-fix`；关联位置：FM-1 section 23。

<!-- fm-test {"id":"T02","mode":"run"} -->
```cpp
#include <stdexcept>
#include <string_view>
int main() {
    try { throw std::out_of_range{"index out of range"}; }
    catch (const std::out_of_range& e) {
        return std::string_view{e.what()} == "index out of range" ? 0 : 1;
    }
    return 2;
}
```

## T03

std::move 的复制回退：完整反例。来源性质：`counterexample`；关联位置：FM-5 sections 5 and 12。

<!-- fm-test {"id":"T03","mode":"run"} -->
```cpp
#include <type_traits>
#include <utility>
struct CopyOnly {
    static inline int copies = 0;
    CopyOnly() = default;
    CopyOnly(const CopyOnly&) noexcept { ++copies; }
};
struct CopyAndMove {
    static inline int copies = 0;
    static inline int moves = 0;
    CopyAndMove() = default;
    CopyAndMove(const CopyAndMove&) noexcept { ++copies; }
    CopyAndMove(CopyAndMove&&) noexcept { ++moves; }
};
static_assert(std::is_nothrow_move_constructible_v<CopyOnly>);
int main() {
    CopyOnly a;
    CopyOnly b{std::move(a)};
    const CopyAndMove c;
    CopyAndMove d{std::move(c)};
    return CopyOnly::copies == 1 && CopyAndMove::copies == 1 &&
           CopyAndMove::moves == 0 ? 0 : 1;
}
```

## T04

未命名枚举值：完整正例。来源性质：`counterexample`；关联位置：FM-1 section 34。

<!-- fm-test {"id":"T04","mode":"run"} -->
```cpp
#include <type_traits>
enum class State { idle, running };
constexpr State other = static_cast<State>(2);
static_assert(std::is_same_v<std::underlying_type_t<State>, int>);
static_assert(other != State::idle && other != State::running);
static_assert(static_cast<int>(other) == 2);
int main() { return 0; }
```

## T05

违反 unreachable 前置条件：隔离 UBSan 反例。来源性质：`source-derived-with-adversarial-input`；关联位置：FM-1 section 34。

<!-- fm-test {"id":"T05","mode":"sanitizer_negative","feature":"ubsan","diagnostics":["unreachable","runtime error"]} -->
```cpp
#include <utility>
enum class State { idle, running };
int value(State state) {
    switch (state) {
    case State::idle: return 0;
    case State::running: return 1;
    }
    std::unreachable();
}
int main() { return value(static_cast<State>(2)); }
```

## T06

move-only E 的左值 value()：预期编译失败。来源性质：`counterexample`；关联位置：FM-2 sections 12 and 16。

<!-- fm-test {"id":"T06","mode":"compile_fail","feature":"expected","diagnostics":["is_copy_constructible|deleted.*copy|copy.*deleted|deleted function","Error"]} -->
```cpp
#include <expected>
#include <memory>
struct Error { std::unique_ptr<int> resource; };
int main() {
    std::expected<int, Error> result{7};
    return result.value();
}
```

## T07

先判状态再解引用：完整正例。来源性质：`valid-alternative`；关联位置：FM-2 sections 12 and 16。

<!-- fm-test {"id":"T07","mode":"run","feature":"expected"} -->
```cpp
#include <expected>
#include <memory>
struct Error { std::unique_ptr<int> resource; };
int main() {
    std::expected<int, Error> result{7};
    if (!result) { return 1; }
    return *result == 7 ? 0 : 2;
}
```

## T08

and_then 不同错误域：预期编译失败。来源性质：`counterexample`；关联位置：FM-2 section 11。

<!-- fm-test {"id":"T08","mode":"compile_fail","feature":"expected-monadic","diagnostics":["same error_type|is_same_v|same_as","FileError|ParseError"]} -->
```cpp
#include <expected>
enum class FileError { failed };
enum class ParseError { invalid };
int main() {
    auto result = std::expected<int, FileError>{1}.and_then([](int value) {
        return std::expected<int, ParseError>{value};
    });
    return *result;
}
```

## T09

显式统一错误域：完整正例。来源性质：`proposed-complete-example`；关联位置：FM-2 section 11。

<!-- fm-test {"id":"T09","mode":"run","feature":"expected-monadic"} -->
```cpp
#include <expected>
enum class FileError { failed };
enum class ConfigError { input, parse };
int main() {
    auto result = std::expected<int, FileError>{1}
        .transform_error([](FileError) { return ConfigError::input; })
        .and_then([](int value) -> std::expected<int, ConfigError> {
            return value + 1;
        });
    return result && *result == 2 ? 0 : 1;
}
```

## T10

错误对象复制抛异常：完整边界例。来源性质：`boundary-counterexample`；关联位置：FM-2 section 12。

<!-- fm-test {"id":"T10","mode":"run","feature":"expected"} -->
```cpp
#include <expected>
struct CopyFailure {};
struct Error {
    Error() = default;
    Error(const Error&) { throw CopyFailure{}; }
    Error(Error&&) noexcept = default;
};
int main() {
    std::expected<int, Error> result{std::unexpect};
    try { (void)result.value(); }
    catch (const CopyFailure&) { return 0; }
    catch (...) { return 1; }
    return 2;
}
```

## T11

报告函数再次抛异常：受控终止反例。来源性质：`synthetic-helper-counterexample`；关联位置：FM-0 section 27; FM-8 section 2。

`report_failure` 是人为构造的抛异常 helper；测试进程将 terminate 转为退出码 86，不测试生产报告实现。

<!-- fm-test {"id":"T11","mode":"death","exit_code":86} -->
```cpp
#include <cstdlib>
#include <exception>
#include <new>
#include <thread>
void run_worker() { throw 1; }
// Synthetic implementation: the original document does not define this helper.
void report_failure(std::exception_ptr) { throw std::bad_alloc{}; }
int main() {
    std::set_terminate([] { std::_Exit(86); });
    std::thread worker([] {
        try { run_worker(); }
        catch (...) { report_failure(std::current_exception()); }
    });
    worker.join();
    return 1;
}
```

## T13

委托构造体抛异常：完整边界例。来源性质：`boundary-supplement`；关联位置：FM-3 section 6; FM-6 section 3。

<!-- fm-test {"id":"T13","mode":"run"} -->
```cpp
struct Object {
    static inline int destroyed = 0;
    explicit Object(int) {}
    Object() : Object(0) { throw 7; }
    ~Object() noexcept { ++destroyed; }
};
int main() {
    try { Object object; }
    catch (int) { return Object::destroyed == 1 ? 0 : 1; }
    return 2;
}
```

## T15

error_code 重载：实现观测。来源性质：`local-implementation-probe`；关联位置：FM-7 section 14。

本机变体：保留查询结果输出，只以设置重载的 `noexcept` 为成功条件，避免把实现允许的规格强化判为规范失败。其余 T01～T16 源码保持附件字节。

<!-- fm-test {"id":"T15","mode":"run"} -->
```cpp
#include <filesystem>
#include <iostream>
#include <system_error>
#include <utility>
int main() {
    constexpr bool query = noexcept(std::filesystem::current_path(
        std::declval<std::error_code&>()));
    constexpr bool change = noexcept(std::filesystem::current_path(
        std::declval<const std::filesystem::path&>(), std::declval<std::error_code&>()));
    std::cout << "query_noexcept=" << query << " change_noexcept=" << change << '\n';
    // The query result is an observation; only the setter must be noexcept.
    return change ? 0 : 1;
}
```

## T16

move-only E 的右值 value()：规范与实现对照。来源性质：`counterexample`；关联位置：FM-2 section 12。

以 N4950 observers/11 与 LWG 3843 为基线，若实现接受该程序，记为 `DIVERGENCE`，不能改写为标准允许。

<!-- fm-test {"id":"T16","mode":"compile_fail","feature":"expected","diagnostics":["is_copy_constructible|deleted.*copy|copy.*deleted|deleted function","Error"]} -->
```cpp
#include <expected>
#include <memory>
#include <utility>
struct Error { std::unique_ptr<int> resource; };
int main() {
    std::expected<int, Error> result{7};
    return std::move(result).value();
}
```

## T20

POSIX open 的返回值、errno 与 O_CREAT。完整正例；由本轮编写。仅在 runner 分配的全新用例工作目录创建测试文件，不读写仓库制品。此例不测试配置加载事务。

<!-- fm-test {"id":"T20","mode":"run","feature":"posix"} -->
```cpp
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>

int main() {
    const int missing = ::open("fm20-missing.txt", O_RDONLY);
    const int saved_error = errno; // 下一次库调用之前保存。
    if (missing >= 0) {
        ::close(missing);
        return 1;
    }
    if (saved_error != ENOENT) return 2;
    const int created = ::open("fm20-created.txt", O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (created == -1) return 3;
    return ::close(created) == 0 ? 0 : 4;
}
```
