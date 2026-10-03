# G8 动态加载、版本协商与兼容演进

上一单元的 C consumer 在链接时已经指定 reading 库。现在让同一个应用在运行时选择 provider 路径：这次用最小实现，下次用缓存中间结果的实现，但应用不重新编译。怎样知道找到了正确入口、拿到了理解的合同，而且在使用完之前没有卸载它？

这个问题把 G0 的符号与加载、G2 的资源释放、G7 的退出协议接到同一条依赖链上。运行时找到地址只解决“在哪里”，版本协商解决“双方承诺哪一种接口”，module lifetime 则决定“这段代码还能不能被调用”。本单元不构建通用插件框架，而是把这些义务落实到 [前一单元](g08-c-boundary-and-ownership.md)的同一套值与失败测试。

## 1 link-time binding 与 runtime lookup

### 1.1 静态归档、共享库和主动加载

静态库通常是目标文件归档，最终链接器从中取出需要的成员；应用仍须与这些预编译对象的调用约定兼容。共享库的代码由 loader 映射到进程并处理依赖和绑定。它既可以是可执行文件声明的启动依赖，也可以由程序显式请求加载。“共享库”不等同于“只有 dlopen 才能使用”。

上一单元的 `-L. -lreading` 帮助 linker 在构建时找到库；`@rpath/libreading.dylib` 是库记录的 install name，运行时由 dyld 结合加载映像的 run-path 信息定位。`@loader_path` 表示相应加载映像所在目录，不是 shell 的当前目录。构建时 `-L` 找到了库，不代表将程序移到别处后运行时也能找到。[Apple Run-Path Dependent Libraries](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/RunpathDependentLibraries.html)

ELF 的 DT_NEEDED／RPATH／RUNPATH、Windows 的 DLL 查找规则是各自平台合同，不能把上述参数当成通用命令。本批实际执行 macOS Mach-O 路线；后续 G9 再处理安装树、依赖传播和可搬迁部署，不在这里搭建构建框架。

### 1.2 显式加载把部分失败移到应用控制流

本实验用绝对路径调用 dlopen，然后从返回的 module handle 查找一个约定入口。host 不在链接命令中依赖 reading，所以“指定 provider 不存在”可以由应用收到失败、报告并退出，而不必假定 main 一定已经因启动依赖错误而无法进入。

`RTLD_NOW` 请求立即处理相应符号绑定，`RTLD_LOCAL` 限制此加载方式的全局符号暴露。两者不是兼容性验证器：加载成功仍不知道所查函数的真实签名，更不知道输出或 ownership 合同。dlopen 还可能执行模块初始化代码；必须先信任来源，不能把“先加载、再检查版本”当作运行不可信插件的安全沙箱。[Apple dlopen 手册](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dlopen.3.html)

## 2 用一个稳定入口取得明确的函数表

### 2.1 表由协议定义，不由编译器替我们设计

函数表 re_api_v1 保存 create、destroy、process 三个函数指针，以及 ABI 版本和表大小。host 通过固定入口请求 version 1；provider 可以拒绝未知版本。它与 C++ vtable 的区别在于字段顺序、版本和错误行为由接口设计者明确规定，而不是依赖某种类继承 lowering。

函数表本身也有 ABI：指针类型、字段布局、大小与调用约定仍需一致。给表增加一个指针并期待旧 host 自动获得空间，和给普通公开 struct 增加字段是同一类问题。本例要求完整 v1 表大小恰好匹配，未知大小或版本在写表之前拒绝，不宣称实现了 append-only 协商。

**完整实验 G8-D1 插件声明 `reading-plugin.h`**

```c
#ifndef G8_READING_PLUGIN_H
#define G8_READING_PLUGIN_H
#include "reading-api.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct re_api_v1 {
    uint32_t abi_version;
    uint32_t struct_size;
    re_create_ptr create;
    re_destroy_ptr destroy;
    re_process_ptr process;
} re_api_v1;
typedef re_status (*re_get_api_ptr)(uint32_t, size_t, re_api_v1*) RE_NOEXCEPT;
RE_API re_status re_get_api(uint32_t, size_t, re_api_v1*) RE_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#endif
```

**完整实验 G8-D1 协商入口 `reading-plugin.cpp`**

```cpp
#include "reading-plugin.h"
#include <type_traits>
static_assert(std::is_same_v<decltype(re_api_v1::create), decltype(&re_create)>);
static_assert(std::is_same_v<decltype(re_api_v1::destroy), decltype(&re_destroy)>);
static_assert(std::is_same_v<decltype(re_api_v1::process), decltype(&re_process)>);
#if !defined(RE_OMIT_ENTRY)
extern "C" re_status re_get_api(uint32_t requested, size_t size,
                                re_api_v1* out) noexcept {
    if (!out || size != sizeof(re_api_v1)) return RE_INVALID;
    if (requested != 1) return RE_VERSION;
    *out = re_api_v1{1, sizeof(re_api_v1), &re_create, &re_destroy, &re_process};
    return RE_OK;
}
#endif
```

入口的 out 非空时必须指向完整、正确对齐且可写的 re_api_v1 对象，不能与其他被使用的对象重叠。拒绝时不改它。size 是 caller 传递的协议信息，不是操作系统验证过的缓冲区长度。这里的 type assertions 检查当前 C++ 编译单元中的指针类型一致，不证明历史 host 或其他平台使用了同样布局。

同一头文件能被两种编译器解析，还应与“实际布局一致”区分。下面的 G8-D2 探针分别按 C11 与 C++23 编译，打印所有公开记录的 size、alignment 和字段 offset。对本次支持配置，两个输出必须完全相同；数值本身仍是平台观察，不被固定为所有平台都应满足的常量。

**完整实验 G8-D2 双语言布局探针 `boundary-layout.c`**

```c
#include "reading-plugin.h"
#include <stdio.h>
#ifdef __cplusplus
#define RE_ALIGNOF(T) alignof(T)
#else
#define RE_ALIGNOF(T) _Alignof(T)
#endif
#define TYPE(T) printf(#T " size=%zu align=%zu\n", sizeof(T), RE_ALIGNOF(T))
#define FIELD(T, M) printf(#T "." #M "=%zu\n", offsetof(T, M))
int main(void) {
    TYPE(re_config);
    FIELD(re_config, struct_size); FIELD(re_config, abi_version); FIELD(re_config, bias);
    TYPE(re_input); FIELD(re_input, id); FIELD(re_input, value);
    TYPE(re_output); FIELD(re_output, id); FIELD(re_output, adjusted);
    TYPE(re_api_v1);
    FIELD(re_api_v1, abi_version); FIELD(re_api_v1, struct_size);
    FIELD(re_api_v1, create); FIELD(re_api_v1, destroy); FIELD(re_api_v1, process);
}
```

保存各单元公开头文件后，运行 `clang -std=c11 boundary-layout.c -o layout-c` 与 `clang++ -std=c++23 -x c++ boundary-layout.c -o layout-cpp`，再比较两程序的输出。它们分别使用 `_Alignof` 与 `alignof`，没有通过将 C 代码全部交给 C++ 编译器来掩盖差异。布局一致仍不能证明函数指针的调用约定或每个值都正确；后面的真实调用负责检验另一层。

### 2.2 查找地址不能恢复函数类型

dlsym 返回的是一个未经 C 类型系统证明的地址。host 必须使用双方预先约定的函数指针类型；“转型成功”并没有动态检查参数或返回值。本例的转换依赖 macOS 的 dlsym 平台接口，不是任意 ISO C／C++ 环境中对象指针与函数指针都可互换的保证。[Apple dlsym 手册](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dlsym.3.html)

查找前先清理 dlerror，查找后立即读取错误，避免将旧错误错归给本次操作。发现错误或入口为空时，不通过它调用。机器符号在 nm 中可以带前导下划线，但 dlsym 使用平台 API 规定的名称；本例传 `re_get_api`，不把工具输出的 `_re_get_api` 机械复制过来。

## 3 host 持有的是代码使用权，不只是一个地址

**完整实验 G8-D1 C host `plugin-host.c`**

```c
#include "reading-plugin.h"
#include "contract-suite.h"
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

int main(int argc, char** argv) {
    if (argc < 2 || argc > 3) return 64;
    void* module = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!module) {
        const char* error = dlerror();
        fprintf(stderr, "OPEN_REJECTED: %s\n", error ? error : "no diagnostic");
        return 10;
    }
    dlerror();
    void* symbol = dlsym(module, "re_get_api");
    const char* error = dlerror();
    if (error || !symbol) {
        fprintf(stderr, "LOOKUP_REJECTED: re_get_api: %s\n",
                error ? error : "null entry");
        dlclose(module);
        return 11;
    }
    re_get_api_ptr get_api = (re_get_api_ptr)symbol;
    re_api_v1 api = {0};
    int result = 0;
    if (argc == 3) {
        int wrong_version = strcmp(argv[2], "--wrong-version") == 0;
        if (!wrong_version && strcmp(argv[2], "--wrong-size") != 0) {
            dlclose(module); return 64;
        }
        re_status status = get_api(wrong_version ? 99 : 1,
            wrong_version ? sizeof(api) : sizeof(api) - 1, &api);
        re_status expected = wrong_version ? RE_VERSION : RE_INVALID;
        if (status != expected || api.abi_version || api.struct_size ||
            api.create || api.destroy || api.process) result = wrong_version ? 21 : 22;
        if (!result) puts("unsupported negotiation rejected without publishing a table");
    } else {
        if (get_api(1, sizeof(api), &api) != RE_OK || api.abi_version != 1 ||
            api.struct_size != sizeof(api) || !api.create || !api.destroy || !api.process)
            result = 23;
        else
            result = check_contract(api.create, api.destroy, api.process);
        if (!result) puts("unchanged host consumed the provider and destroyed every handle");
    }
    api = (re_api_v1){0};
    get_api = NULL;
    symbol = NULL;
    if (dlclose(module) != 0) return 24;
    return result;
}
```

host 使用上一单元的同一 contract-suite，成功路径和测试拒绝路径都先销毁其中创建的 engine，然后才关闭 module。局部表置零只避免误用本地副本，不能让外部已经复制出去的指针自动失效。因此本例不把表或对象交给后台线程，也不注册延迟回调。

### 3.1 两种资源生命区间要嵌套

engine 的存储属于 provider；调用 destroy 需要 provider 的代码仍然可用。callback、虚析构、函数表和未完成栈帧也可能依赖模块。因此，模块引用必须覆盖所有依赖它的对象和在途调用，而不只是覆盖 dlsym 这一瞬间。

```text
取得 module 引用
    取得 API → create engine → process / callback → destroy engine
    所有依赖模块的调用与对象结束
释放 module 引用
```

这不是通过 `dlclose` 返回 0 就能反向证明的条件。dlclose 释放的是 loader 的加载引用；是否立即解除映射受平台、其他引用等条件影响。即使错误的“先关模块、后调用”在某次运行中碰巧没崩溃，也不授予继续使用旧指针的权利。[Apple dlclose 手册](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dlclose.3.html)

### 3.2 异步插件需要真正的 quiescence

如果以后让 worker 持有函数表，安全关闭必须先停止接收新任务，再等待在途调用与回调结束，销毁对象和其他代码依赖，最后释放模块。quiescence（静止状态）在这里指已经没有可能继续进入模块的工作，不等于“队列此刻为空”。消费者可能已经取走任务，但尚未执行完。

这个推导直接来自 G7 的 accepted／delivered／completed 区分及 [shutdown 依赖](g07-shared-state-and-shutdown.md)。只把 module 指针设为 null，或者原子地写一个 closed 标志，不能撤销其他线程已复制的函数指针。本批没有异步 host，不用同步 smoke test 冒充并发卸载证明。

## 4 保留旧消费者再替换 provider

把前两单元的公共头文件和实现与本单元文件放在同一临时目录。以下命令只编译一次 host；它没有链接 reading 库。两个 provider 使用不同的隐藏 engine 表示，但共用同一 v1 公开合同。

```sh
clang -std=c11 -O2 -Wall -Wextra -Wpedantic plugin-host.c -o plugin-host
clang++ -std=c++23 -O2 -fvisibility=hidden -DRE_IMPLEMENTATION=1 -dynamiclib reading-engine.cpp reading-plugin.cpp -o libreading-impl1.dylib
clang++ -std=c++23 -O2 -fvisibility=hidden -DRE_IMPLEMENTATION=2 -dynamiclib reading-engine.cpp reading-plugin.cpp -o libreading-impl2.dylib
shasum -a 256 plugin-host
./plugin-host "$PWD/libreading-impl1.dylib"
./plugin-host "$PWD/libreading-impl2.dylib"
shasum -a 256 plugin-host
```

两个正常执行都应退出 0，输出 `unchanged host consumed the provider and destroyed every handle`；host 两次摘要相同。执行器还记录公共头文件、两个 provider 和 host 的摘要，保留编译与执行顺序。不是每换一个库就重新编译一次 host，再称为兼容测试。

这里的“旧 host”指实验中先编译并固定下来的消费者，不是某个已发布 SDK 的历史客户二进制。证明方向成立需要保留字节；把本实验推广到真实历史版本，还需要取得那些版本各自的消费者与支持配置。

### 4.1 几种失败应该停在不同位置

```sh
./plugin-host "$PWD/not-present.dylib"
./plugin-host "$PWD/libreading-impl1.dylib" --wrong-version
./plugin-host "$PWD/libreading-impl1.dylib" --wrong-size
```

第一条要求文件确实不存在，应返回 10 并带有 OPEN_REJECTED 与目标路径的 loader 诊断。后两条是 host 主动测试拒绝合同：provider 拒绝且表未改，host 才返回 0，并输出 `unsupported negotiation rejected without publishing a table`。这里的进程 0 表示“拒绝行为符合预期”，不是“未知版本被接受”。

再将 reading-plugin.cpp 用 RE_OMIT_ENTRY 编译成没有协商入口的库，host 应以 11 和 LOOKUP_REJECTED 诊断结束，不调用任意猜测地址。执行器另生成一个错误 provider，删除 requested version 检查；同一个 host 必须在编译成功后以 21 拒绝它。这个变体检验协商 oracle，不改变正文中的正确实现。

以上失败都由 host 控制流明确返回，不把无关 crash、timeout 或任意 stderr 当作成功反例。对应文件路径均位于新建的实验目录，不删除系统库或修改正式发布制品。

### 4.2 这个实验能证明到哪里

它证明本次旧 host、两份 provider、固定公开头文件和有限合同矩阵可以协同工作，并且旧 host 的字节确实没有改变。第二版增加内部 scratch，不影响 caller 计算布局；但其资源占用、分配频率和延迟可能变化，本批没有承诺或测量性能兼容。

它没有证明任意旧版本都兼容，没有验证不同 CPU、不同标准库、其他操作系统、不同异常／RTTI 配置，也没有跨语言重写同一结构布局。两套 Clang 测试仍共享本机目标平台与 libc++，不能只看编译器品牌不同就称为跨平台 ABI 验证。

此外，这不是同时加载两个定义同名内部 C++ 类的版本并让对象混用的实验。每次进程只消费指定的一个 provider；engine 不在两个实现之间转交。opaque 指针能隐藏布局，但不能让 impl1 创建的对象自动成为 impl2 的合法对象。

## 5 兼容演进是保留合同，不是保留几个名字

### 5.1 明确哪些东西由旧机器代码决定

如果只改变 engine 私有 vector 的策略，caller 的大小和偏移假设没有增加；若改变 re_output 的字段次序，旧 host 的结果检查和 provider 的写入位置就可能分歧。若只把 bias 的单位改了，机器表示也许完全没变，业务结果仍会错。审查应分别看表示、调用与语义，而非找一个“ABI compatible”标签覆盖全部。

公开 inline 和模板还可能把逻辑留在 caller。换新库只能替换实际通过边界调用的实现，不能修改旧二进制中已经生成的检查或计算。因此需要修复旧包装层行为时，可能必须升级消费者，而不只是承诺导出集合不变。

| 变更 | 主要需复核的对象 | 本例是否已验证 |
| --- | --- | --- |
| 隐藏 engine 增加 scratch | 公开语义、线程与资源合同 | 有限旧 host 替换实验；无性能结论 |
| re_output 新增／重排字段 | 大小、步长、偏移、调用双方范围 | 未实现此演进，不能沿用本批结论 |
| 新增 API version | 入口协议、拒绝／协商矩阵、版本并存 | 仅验证拒绝未知版本 |
| 同步变为异步 | payload ownership、完成定义、注销与模块 lifetime | 未实现 |

### 5.2 版本号记录承诺，不能制造承诺

软件版本、ABI 代际与功能能力不是同一轴。内部实现可以升级而保留 ABI v1；新增某个可选能力也不必推断所有 v1 host 都理解它。相反，一个字段意义破坏即使只改了 patch version，也不会因为版本号小而重新变得兼容。

稳定接口可以选择保留旧入口、增加新入口，或显式协商多代函数表；每一种都需要定义支持方向及数据转换。继续支持旧消费者，就要保留旧语义及其测试，不能只保存旧头文件。我们当前只建立单代协议的有限替换证据，未实现完整多代 SDK。

### 5.3 工件工具不是语义证明器

本批用 nm 观察公共 re_* 定义，用 otool 查看共享库依赖与 install name；汇编、符号、布局和文件摘要保存在 [验证记录](g08-verification.md)对应的 JSON 中。导出检查针对本产品入口，不把工具链引入的其他运行时符号数量固定成 ABI 真理。

实际发布 SDK 还可能使用 ABI 差异工具、旧消费者集合及平台测试矩阵。那些工具可以发现结构变化，不能替我们判断“重试是否安全”“callback 是否仍在返回前结束”等语义合同。把分析工具读到的事实与人工合同审查组合起来，比重复列一张符号清单更接近完整判断。

## 6 用变化后的条件检验模型

1. 构建时 `-L` 指向了正确目录，为什么部署后仍可能找不到动态库？
2. dlsym 返回非空，为什么还不能证明用 re_get_api_ptr 调用是合法的？
3. impl1 和 impl2 都通过测试，是否可以把 impl1 创建的 handle 交给 impl2 销毁？
4. worker 已取走最后一个任务，队列为空。此时能否卸载保存函数表的模块？
5. 错误版本测试的 host 返回 0，正常 host 返回 0，两者为什么不是同一个成功命题？
6. 新库的导出符号集合完全相同，所有体现在头文件中的检查也未修改。还需要保留什么兼容边界？

## 7 迁移题参考推理

1. `-L` 服务于构建时查找，运行时依赖由二进制中的 install name 和 loader 路径规则决定。要检查实际加载信息与部署布局，不能只复读编译命令。
2. dlsym 只完成按名查找，没有恢复类型和前置条件。host 必须已知提供者的接口合同，且使用平台支持的函数指针转换；类型不匹配的调用不能靠地址非空修复。
3. 不可以。每个对象必须由创建它的 provider 按匹配表示和分配域销毁；实验每次只加载指定提供者，没有建立跨版本对象迁移协议。
4. 不能。任务可能在执行，或者未来回调还持有代码地址。必须先建立 quiescence：无新调用、在途工作结束、回调及对象依赖解除，然后才释放模块引用。
5. 前者的 oracle 是收到 RE_VERSION 且表保持未发布，后者是取得 v1 表并满足完整处理合同。仅汇总退出码会丢掉它们验证的具体命题，因此执行记录还必须保存模式和输出。
6. 仍需核对机器表示、调用约定、运行时、ownership、错误后置条件和线程／时间语义。旧 caller 还可能保留已经内联的旧行为。相同导出名只是这些条件中的一部分，不自动覆盖它们。
