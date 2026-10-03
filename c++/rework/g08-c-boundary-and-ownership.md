# G8 不透明句柄、C 边界与资源合同

现在为读数处理建立真正的库接口。应用提供若干带编号的 int32_t 读数，库给每个数值加一个配置偏移，输出保留编号的 int64_t 结果。我们希望库内部以后可以缓存中间结果、改变容器，而不要求应用知道实现对象的大小。

这不是把所有 C++ 都改写成 C。内部仍使用 vector、异常与 RAII，边界只暴露能够明确描述的类型和操作。[第一单元](g08-binary-contracts.md)已经解释为什么 C 链接不能自动保证兼容；本单元要回答它没有解决的部分：谁释放对象，失败改动什么，回调何时执行，以及哪些错误根本不在库的检测能力内。

## 1 先确定谁拥有存储与释放责任

### 1.1 opaque pointer 隐藏表示，不隐藏义务

公开头文件只前置声明 re_engine，caller 保存 re_engine*，不对其使用 sizeof，不直接构造或 delete。re_create 成功后交付一项释放责任，re_destroy 在同一 provider 中结束对象生命并释放存储。这个 create/destroy 配对同时隔离实现大小与 allocation domain（分配域）。

G2 的 [owner 与 borrow](g02-ownership-and-handoff.md)在此继续适用。传入 re_process 的句柄是调用期间借用，不转移所有权；输入、输出与回调 context 也只借用到函数返回。指针类型没有替我们登记这些责任，调用者仍须保证 engine 比全部调用活得久。

由 provider 销毁的理由不是“跨库 delete 在任何情况下都非法”。同一受控 C++ runtime 可以约定匹配分配；问题是独立升级时不能悄悄把 allocator、对象析构和运行时匹配交给消费者猜测。让 release responsibility 留在创建域，会减少需要跨边界保持的假设。

### 1.2 caller-provided output 也有完整合同

caller 提供输出数组，拥有其存储；provider 只写前 written 个结果。capacity 和 count 的单位都是元素，不是字节。编号与数值必须逐项对应，不能只用 checksum 或首元素代表完整值。两个 int32_t 值先扩宽再相加，结果可由 int64_t 表示；不能先在较窄类型里溢出，再把结果转宽。

这个接口不保留输入地址，不启动后台任务，也不把输出变成长期借用。它刻意不实现 G7 的异步队列：先让同步边界的对象关系成立，后续若要异步化，必须重新规定 payload 的 owner 与完成通知，而不是只改变实现线程。

## 2 把失败后置条件写在签名之外

本例将 count 限为 4096，配置只支持 ABI version 1 的完整结构。所有非空指针必须满足相应对象的类型、对齐、存活及可读写范围；输入、输出、written、配置、输出句柄槽和回调 context 所用对象范围按对应调用保持互不重叠，也不与 engine 重叠。这是 caller precondition，库不尝试比较任意地址来证明它们合法。

re_create 的 out 必须指向可写且不承担旧句柄 ownership 的槽位。有效 out 在创建失败时置空，成功时取得一个新句柄；这不是替换旧 owner 的事务接口。re_destroy 接受 null；非空时只能传入本 provider 创建且尚未销毁的句柄，不允许在途调用与销毁并发。

re_process 的 written 若非空，须指向有效 size_t，入口先置零；若它本身为空，则返回 RE_INVALID，没有可以写入的计数位置。count 非零要求 input 非空，capacity 非零要求 output 非空。零 count／零 capacity 可以使用空指针；这不意味着任何“非空但悬挂”的指针也合法。

| 结果 | written 与输出 | 回调 |
| --- | --- | --- |
| RE_OK | written = count；前 count 个结果完整，其后不改 | 非空回调同步调用一次，count 可为零 |
| RE_SMALL | 有效 written = 0；全部输出保持 | 不调用 |
| RE_INVALID／RE_VERSION | 适用的有效输出位置按入口合同处理；处理输出数组保持 | 不调用 |
| RE_NOMEM／RE_INTERNAL | 有效 written = 0；全部处理输出保持 | 不调用 |

这些保证依赖合法地址与回调合同。catch (...) 不是内存隔离机制，不能把无效指针、data race 或任意 UB 翻译成可靠状态码。

## 3 用同一个头文件约束两侧

实验 G8-C1 的公开头文件同时由 C11 consumer 和 C++23 provider 编译。RE_API 是本章 Clang／GCC 风格 visibility 约定，不是完整的 Windows 导入导出适配层。RE_NOEXCEPT 在 C 侧展开为空，在 C++ 侧同时约束声明和函数指针类型。

**完整实验 G8-C1 公开头文件 `reading-api.h`**

```c
#ifndef G8_READING_API_H
#define G8_READING_API_H
#include <stddef.h>
#include <stdint.h>
#define RE_API __attribute__((visibility("default")))
#ifdef __cplusplus
#define RE_NOEXCEPT noexcept
extern "C" {
#else
#define RE_NOEXCEPT
#endif
typedef struct re_engine re_engine;
typedef uint32_t re_status;
enum { RE_OK = 0, RE_INVALID = 1, RE_VERSION = 2,
       RE_SMALL = 3, RE_NOMEM = 4, RE_INTERNAL = 5 };
enum { RE_MAX_BATCH = 4096 };
typedef struct re_config {
    uint32_t struct_size;
    uint32_t abi_version;
    int32_t bias;
} re_config;
typedef struct re_input { uint32_t id; int32_t value; } re_input;
typedef struct re_output { uint32_t id; int64_t adjusted; } re_output;
typedef void (*re_notify)(void* context, size_t count);
typedef re_status (*re_create_ptr)(const re_config*, re_engine**) RE_NOEXCEPT;
typedef void (*re_destroy_ptr)(re_engine*) RE_NOEXCEPT;
typedef re_status (*re_process_ptr)(re_engine*, const re_input*, size_t,
    re_output*, size_t, size_t*, re_notify, void*) RE_NOEXCEPT;
RE_API re_status re_create(const re_config*, re_engine**) RE_NOEXCEPT;
RE_API void re_destroy(re_engine*) RE_NOEXCEPT;
RE_API re_status re_process(re_engine*, const re_input*, size_t,
    re_output*, size_t, size_t*, re_notify, void*) RE_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#endif
```

状态的传递类型明确为 uint32_t；enum 这里只提供具名数值常量，不把 C enum 对象作为函数结果传递。精确宽度整数以目标实现提供为前提。size_t 表达同进程数组范围，不是一个承诺跨位宽的网络字段。

头文件仍然暴露了 re_config、re_input、re_output 的布局。因此 opaque engine 只能保护内部表示，不能掩盖公开数据结构变化。我们没有给结构加 packing：应遵守目标 ABI 的自然布局，而不是为了看起来紧凑制造未对齐访问或不同编译参数的隐患。

### 3.1 struct_size 声明能力，不能证明内存有效

本例要求 struct_size 恰好等于当前 re_config 的 sizeof，abi_version 恰好为 1。它不实现任意历史结构的前缀读取协议；传入指针必须本来就指向完整有效的 re_config，即使为了负例故意把 size 字段改小。先给一个短字节数组强转成 re_config*，再期待 size 检查救场，会绕过 G1 的对象与访问前提。

若未来真要支持尾部扩展，需要另外定义共同前缀的合法对象／字节访问方式、每个字段的可读范围、缺省语义和对齐；输出表还需要限定可写范围。尾部追加也可能改变数组步长及按值传递，所以“带 size 就自动兼容”不是完整协议。当前版本选择明确拒绝，而不提供一个只在常见布局上碰巧成立的泛化实现。

## 4 在 provider 内建立准备与提交边界

第一版 engine 只保存 bias，处理时创建局部 vector。第二版在隐藏对象中保留 scratch vector，复用容量；公开类型和操作不变。RE_IMPLEMENTATION 是本实验的提供者实现版本，不是 ABI version。下一单元会用同一个旧 consumer 分别加载这两个二进制。

**完整实验 G8-C1 提供者 `reading-engine.cpp`**

```cpp
#include "reading-api.h"
#include <new>
#include <stdexcept>
#include <vector>

#ifndef RE_IMPLEMENTATION
#define RE_IMPLEMENTATION 1
#endif
struct re_engine {
    int32_t bias;
#if RE_IMPLEMENTATION == 2
    std::vector<re_output> scratch;
#endif
    explicit re_engine(int32_t n) : bias{n} {}
};

extern "C" re_status re_create(const re_config* config,
                                re_engine** out) noexcept {
    if (!out) return RE_INVALID;
    *out = nullptr;
    if (!config) return RE_INVALID;
    if (config->struct_size != sizeof(re_config)) return RE_INVALID;
    if (config->abi_version != 1) return RE_VERSION;
    try {
#if defined(RE_FAIL_CREATE)
        throw std::bad_alloc{};
#endif
        *out = new re_engine{config->bias};
        return RE_OK;
    } catch (const std::bad_alloc&) {
        return RE_NOMEM;
    } catch (...) {
        return RE_INTERNAL;
    }
}

extern "C" void re_destroy(re_engine* engine) noexcept { delete engine; }

extern "C" re_status re_process(re_engine* engine, const re_input* input,
    size_t count, re_output* output, size_t capacity, size_t* written,
    re_notify notify, void* context) noexcept {
    if (!written) return RE_INVALID;
    *written = 0;
    if (!engine || count > RE_MAX_BATCH || (!input && count) ||
        (!output && capacity)) return RE_INVALID;
    if (capacity < count) return RE_SMALL;

#if RE_IMPLEMENTATION == 2
    auto& prepared = engine->scratch;
    prepared.clear();
#else
    std::vector<re_output> prepared;
#endif
    try {
        prepared.reserve(count);
        for (size_t i = 0; i < count; ++i) {
            prepared.push_back({input[i].id, int64_t{input[i].value} + engine->bias});
#if defined(RE_FAIL_PREPARE)
            if (i == 0) throw std::runtime_error{"controlled preparation fault"};
#endif
        }
        for (size_t i = 0; i < count; ++i) output[i] = prepared[i];
        *written = count;
    } catch (const std::bad_alloc&) {
        return RE_NOMEM;
    } catch (...) {
        return RE_INTERNAL;
    }
    if (notify) notify(context, *written);
    return RE_OK;
}
```

### 4.1 为什么错误时输出可以保持

reserve 与 push_back 都发生在 provider 自有存储中。只要准备尚未完成，caller 的 output 就没有被触碰。准备成功后，提交阶段仅给合法输出数组赋值平凡记录并设置计数；这里没有用户定义的抛异常赋值。这个具体结构支撑了失败不写部分结果，不能推广成“用了 vector／try 就有强保证”。

第二版准备失败时，scratch 的内容或容量可能已经改变，但它们不是公开可观察的业务状态，下次操作从 clear 开始。这里的状态保证是输出值与公开语义，不承诺失败后所有内部字节、分配次数都不变。G3 的[准备与提交](g03-value-copy-and-move.md)因此在跨模块接口中仍是同一模型。

RE_FAIL_CREATE 在分配表达式前主动抛 bad_alloc；RE_FAIL_PREPARE 在放入第一条中间记录后主动抛 runtime_error。它们是测试构建开关，不是公开配置字段，更不是让系统真正耗尽内存。本批用它们检验异常到状态码的翻译和提交边界；真实 allocator 故障矩阵另属未验证范围。

### 4.2 callback 在提交之后，不属于可回滚准备

回调必须正常返回，不抛异常、不重入或销毁同一 engine、不修改本次输入输出范围；context 指向独立有效存储。它同步发生在结果提交之后，返回前不保存任何回调地址。本例可以先完成整个结果，再通知 caller，因为通知本身不参与计算成功与否。

不能把回调也随意放进同一个 catch，然后在回调抛异常时返回“输出未变”的错误码：输出已经提交，外部副作用也未必能回滚。当前代码将回调放在转换区之外，违反 no-throw 合同的 C++ 回调会触及外层 noexcept 终止边界，不会被伪装成 RE_INTERNAL 回滚成功。[N4950 except.spec](https://timsong-cpp.github.io/cppwp/n4950/except.spec)

这也是工程 policy 与语言机制的区别。extern "C" 不自动捕获异常，noexcept 不自动产生状态码。若产品需要“回调可以拒绝”，应定义回调状态与已提交输出的组合结果；若需要异步回调，应定义注销、等待在途回调与 context 销毁次序。当前同步例子不声称已经验证这些协议。

### 4.3 线程合同不能从 const 或 opaque 推出

同一 engine 的操作由 caller 串行化，包括 destroy；不同 engine 没有本例共享的业务状态。第二版在处理时修改 scratch，因此不能把“只读取输入”解释成“同一 handle 可并发”。即使第一版恰好没有可变 scratch，公开合同也没有授予这个并发用法。

这里选择了一个允许内部演进的较窄合同：如果 v1 明确承诺同句柄并行处理，v2 增加未同步 scratch 就是语义与线程合同破坏，opaque handle 无法遮盖它。G7 的 [invariant 与访问协议](g07-shared-state-and-shutdown.md)在模块边界不会失效。

## 5 用真正的 C consumer 检查完整合同

测试逻辑接受三个函数指针。现在传入直接链接的入口；下一单元传入动态协商得到的函数表，从而复用同一套值与失败判据，而不是另写一个只调用成功路径的插件 demo。

**完整实验 G8-C1 共用判据 `contract-suite.h`**

```c
#ifndef G8_CONTRACT_SUITE_H
#define G8_CONTRACT_SUITE_H
#include "reading-api.h"
typedef struct callback_state { size_t calls; size_t items; } callback_state;
static void counted(void* context, size_t count) {
    callback_state* state = (callback_state*)context;
    ++state->calls;
    state->items += count;
}
static int untouched(const re_output* output) {
    for (size_t i = 0; i < 3; ++i)
        if (output[i].id != 900 || output[i].adjusted != -900) return 0;
    return 1;
}
static int check_contract(re_create_ptr create, re_destroy_ptr destroy,
                          re_process_ptr process) {
    re_config config = {sizeof(re_config), 2, 7};
    re_engine* engine = NULL;
    re_status status = create(&config, &engine);
    if (status != RE_VERSION || engine) { destroy(engine); return 2; }
    config.abi_version = 1;
    config.struct_size = sizeof(re_config) - 1;
    status = create(&config, &engine);
    if (status != RE_INVALID || engine) { destroy(engine); return 3; }
    config.struct_size = sizeof(re_config);
    if (create(&config, NULL) != RE_INVALID) return 4;
    if (create(&config, &engine) != RE_OK || !engine) {
        destroy(engine); return 5;
    }
#define REQUIRE(c, n) do { if (!(c)) { destroy(engine); return (n); } } while (0)
    const re_input input[] = {{11, INT32_MIN}, {22, 0}, {33, INT32_MAX}};
    re_output output[] = {{900, -900}, {900, -900}, {900, -900}};
    size_t written = 99;
    callback_state observed = {0, 0};
    REQUIRE(process(engine, input, 3, output, 2, &written, counted, &observed)
            == RE_SMALL && written == 0 && untouched(output) && !observed.calls, 12);
    REQUIRE(process(engine, NULL, 3, output, 3, &written, counted, &observed)
            == RE_INVALID && written == 0 && untouched(output) && !observed.calls, 13);
    REQUIRE(process(engine, input, 3, output, 3, &written, counted, &observed)
            == RE_OK && written == 3 && observed.calls == 1 && observed.items == 3, 14);
    for (size_t i = 0; i < 3; ++i)
        REQUIRE(output[i].id == input[i].id &&
                output[i].adjusted == (int64_t)input[i].value + 7, 15);
    const re_input next[] = {{44, -10}, {55, 20}};
    REQUIRE(process(engine, next, 2, output, 3, &written, counted, &observed)
            == RE_OK && written == 2 && observed.calls == 2 && observed.items == 5, 19);
    REQUIRE(output[0].id == 44 && output[0].adjusted == -3 &&
            output[1].id == 55 && output[1].adjusted == 27 &&
            output[2].id == 33 && output[2].adjusted == (int64_t)INT32_MAX + 7, 20);
    REQUIRE(process(engine, NULL, 0, NULL, 0, &written, counted, &observed)
            == RE_OK && written == 0 && observed.calls == 3 && observed.items == 5, 16);
    REQUIRE(process(engine, input, 3, NULL, 3, &written, NULL, NULL)
            == RE_INVALID && written == 0, 17);
    REQUIRE(process(engine, input, 3, output, 3, NULL, NULL, NULL) == RE_INVALID, 18);
    destroy(engine);
    destroy(NULL);
#undef REQUIRE
    return 0;
}
#endif
```

**完整实验 G8-C1 C 消费者 `contract-consumer.c`**

```c
#include "contract-suite.h"
#include <stdio.h>
#include <string.h>
int main(int argc, char** argv) {
    if (argc == 1) {
        int result = check_contract(re_create, re_destroy, re_process);
        if (result) return result;
        puts("C consumer checked complete values and boundary contracts");
        return 0;
    }
    re_config config = {sizeof(re_config), 1, 7};
    re_engine* engine = NULL;
    re_status status = re_create(&config, &engine);
    if (strcmp(argv[1], "--create-fails") == 0) {
        int ok = status == RE_NOMEM && engine == NULL;
        re_destroy(engine);
        if (!ok) return 31;
        puts("controlled create failure left no owned handle");
        return 0;
    }
    if (status != RE_OK || !engine) { re_destroy(engine); return 32; }
    const re_input input[] = {{1, 10}, {2, 20}, {3, 30}};
    re_output output[] = {{900, -900}, {900, -900}, {900, -900}};
    size_t written = 99;
    callback_state observed = {0, 0};
    status = re_process(engine, input, 3, output, 3, &written, counted, &observed);
    re_destroy(engine);
    if (strcmp(argv[1], "--prepare-fails") != 0 || status != RE_INTERNAL ||
        written != 0 || !untouched(output) || observed.calls) return 33;
    puts("controlled preparation failure preserved every output field");
}
```

以下命令把 C consumer 的编译与最终链接明确分开。最后用 C++ driver 链接，是为了让它选择相应 C++ runtime；这不会把已经按 C11 编译的 consumer.o 重新变成 C++ 源文件。

```sh
clang -std=c11 -O2 -Wall -Wextra -Wpedantic -c contract-consumer.c -o consumer.o
clang++ -std=c++23 -O2 -fvisibility=hidden -dynamiclib reading-engine.cpp -o libreading.dylib -Wl,-install_name,@rpath/libreading.dylib
clang++ consumer.o -L. -lreading -Wl,-rpath,@loader_path -o consumer
./consumer
```

正常结果为退出 0，并输出 `C consumer checked complete values and boundary contracts`。capacity 负例保留三个真实可写元素，只把声明容量降为 2，因此即使测试错误变体擅自写了第三项，也仍是可确定判定的合同违反，不依靠越界崩溃充当 oracle。

同一个 engine 随后接收编号和数值都不同的较短批次：前两条必须更新，第三条必须保持。这同时检查缓存复用没有返回上一批记录、written 不沿用旧长度，以及 count 以外的输出未被清空。只创建一次、处理一次的 smoke test 看不到这些状态转换。

完整执行器另建测试库，用 RE_FAIL_CREATE 与 RE_FAIL_PREPARE 分别编译，然后向 consumer 传入对应参数。它还运行三个错误变体：接受未知配置版本、忽略 capacity、遗漏 written 更新。每个变体必须编译成功，再以指定业务失败码被拒绝；超时和 crash 不算拒绝证据。实际命令和结果见 [G8 验证说明](g08-verification.md)。

## 6 边界越小，越需要精确说明被省略的能力

这个接口没有向 caller 交付 STL 对象、异常对象或 allocator，也没有提供通用反射来恢复这些东西。换来的好处是：消费者能只依赖 C 数据与几个函数类型，provider 的内部 vector 可以独立变化。代价包括复制输出、临时准备存储、状态映射，以及比直接 C++ 调用更显式的合同。

若所有模块始终同步重编译，直接使用 span、expected 和具体 C++ 类型可能更合适。C façade 是针对独立边界的策略，不是“越接近 C 就越专业”。同理，Rust／Zig 包装可以恢复各自惯用的 owner 与 slice，但仍须证明外部指针有效、释放配对、错误映射及线程使用满足本合同；本批没有运行这些语言。

我们现在已有可直接链接的边界。第三单元再改变“何时找到入口”：不让 linker 固定依赖，而让 host 运行时加载指定模块。值、错误和 ownership 不应随这个变化悄悄改义。

## 7 用变化后的条件检验模型

1. 用户把一个仍拥有旧 engine 的槽位传给 re_create，期待失败后仍保留旧句柄。当前接口支持吗？
2. struct_size 足够大，但地址来自只有四字节的缓冲区。版本检查能防止后面的非法读取吗？
3. 第二版 scratch 分配失败后保留了更大 capacity。是否违反“失败不改输出”的保证？
4. callback 抛异常时，如果 catch 后返回 RE_INTERNAL，为什么不能声称实现了回滚？
5. v1 恰好允许两个线程并行调用，v2 使用 scratch 后不行。怎样区分“不受支持的旧用法”与兼容性破坏？
6. C consumer 正常运行与两个受控故障分支通过，是否足以说明此 API 对任意不可信调用者安全？

## 8 迁移题参考推理

1. 不支持。out 必须不承担旧句柄释放责任，入口会置空；违反前提可能丢失旧 owner。需要替换语义时，应先创建临时 owner，成功后再由调用者提交替换并销毁旧对象。
2. 不能。size 字段是声明，不是内存探测，读取这个字段本身也有对象与范围前提。当前合同要求完整 re_config；通用前缀协商必须另外设计合法访问方式，不能靠强转和谎报长度建立对象。
3. 不违反当前公开保证。scratch 是内部准备状态，capacity 没有暴露；有效输出、written 和回调行为才是这里的后置条件。若接口另承诺分配次数或资源占用不变，就需要更强实现和单独证据。
4. 输出已提交，回调可能已产生外部副作用，返回一个失败码并不能撤销它们。当前合同要求回调不抛，并把它放在提交之后；若允许拒绝，就须描述已提交状态，而不能套用准备失败的保证。
5. 先查已发布合同。若从一开始要求同 handle 串行化，偶然可并行不是受支持能力；若明确承诺并发，则新实现必须同步 scratch 或使用独立工作区。opaque 只隐藏表示，不隐藏语义承诺。
6. 不能。有效指针、非重叠、存活对象、串行使用及合法回调仍由 caller 保证。受控 throw 不是所有 allocator 故障；未做跨平台、恶意地址隔离、异步回调或并发销毁验证。
