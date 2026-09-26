# G8 · ABI、原生库与 C 互操作

**版本：** 1.1 · Professional Handbook Edition

**状态：** 待集中审核；PDF NOT BUILT / NOT VALIDATED

**语言基线：** C++23；C 接口实验使用 C11。

**编辑基线：** [Editorial Profile v1.0](editorial-profile.md)

## 阅读入口

本章的问题是：库升级了，而调用者没有重新编译，原有调用还能成立吗？先读 §1～8 建立二进制模型，再读 §10～14 设计接口，最后以 §20 的实验检验符号、错误与输出合同。兼容审查可直接查 §9、§15～16；FFI、插件与版本演进保留为深入回查，不要求一次全部读完。

首次出现的核心术语在主线中解释；代码标为机制片段时不承诺独立编译。只有完整实验标记纳入执行器。原稿的编号主题通过 `g8-topic-N` 锚点映射到对应主题组；新章节按工程问题组织，不再逐项复制数十个 Part。原稿的 Complete / Frozen 不沿用为技术验收。

- [1. API 与二进制合同](#g8-section-1)
- [2. 符号、链接属性与 C 入口](#g8-section-2)
- [3. 调用约定与数据模型](#g8-section-3)
- [4. 对象布局、PImpl 与继承](#g8-section-4)
- [5. RTTI 与异常边界](#g8-section-5)
- [6. 分配域、标准库与不透明句柄](#g8-section-6)
- [7. 结构版本与存储表示](#g8-section-7)
- [8. 可见性、库与插件协商](#g8-section-8)
- [9. 兼容性变更与构建配置](#g8-section-9)
- [10. C 接口设计规则与错误输出](#g8-section-10)
- [11. 回调、并发与销毁](#g8-section-11)
- [12. 包装层、跨语言与借用](#g8-section-12)
- [13. 二进制检查与语义合同](#g8-section-13)
- [14. 库接口的分层实现](#g8-section-14)
- [15. 兼容策略与边界分级](#g8-section-15)
- [16. 接口审查清单](#g8-section-16)
- [17. 实践路线与验证选择](#g8-section-17)
- [18. 常见误判](#g8-section-18)
- [19. C++、Zig 与 Rust 对照](#g8-section-19)
- [20. 完整实验：符号与 C 二进制接口](#g8-section-20)
- [21. 边界复核协议](#g8-section-21)
- [22. Final Gate](#g8-section-22)
- [23. Final Gate · 参考答案与常见误判](#g8-section-23)
- [24. 工程原则与全链回查](#g8-section-24)
- [25. 参考资料与验证边界](#g8-section-25)

<a id="g8-section-1"></a>

<a id="g8-topic-0"></a>
<a id="g8-topic-1"></a>
<a id="g8-topic-2"></a>
<a id="g8-topic-3"></a>
<a id="g8-topic-4"></a>

## 1. API 与二进制合同

### 1.1 两种兼容性要分别验证

API 规定源码如何使用组件，包括名称、类型、前置条件、错误与所有权；ABI 规定独立编译组件对符号、传参、返回、布局和运行时的共同理解。源码重新编译后仍成立，不代表旧机器代码能消费新库。

例如 `Config` 从一个 `int mode` 变成再含一个 `int flags`，旧调用者已经按原大小分配对象。新库若直接读取新增字段，即使函数名完全未变，也可能越过旧对象。具体大小不能无条件写死为 4/8；那只是特定数据模型下的常见观察。正确审查比较的是双方真实的大小、对齐、偏移和传递方式，而非只看头文件是否还能编译。

### 1.2 从语言模型追到二进制合同

G1～G7 的问题没有在库边界消失：对象是否存活、谁负责清理、指针借用多久、异常如何处理、线程能否并发使用，都继续约束调用。所有权和线程规则不全属于狭义机器 ABI，但属于完整接口合同。二进制兼容、源码兼容和语义兼容应分别陈述。

首次阅读先建立“声明 → 类型/表示 → 符号 → 调用约定 → 链接/加载”的链路；审查现有 SDK 时则从边界暴露的类型逆向检查承诺。C++23 是语言基线，不是统一的跨编译器 ABI 证书。

**机制示意。** 一个 Source-compatible 但 ABI-breaking 的例子；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cpp
struct Config {
    int mode;
};
```

[机制片段 · 不承诺独立编译]

```cpp
struct Config {
    int mode;
    int flags;
};
```

<a id="g8-section-2"></a>

<a id="g8-topic-5"></a>
<a id="g8-topic-6"></a>
<a id="g8-topic-7"></a>
<a id="g8-topic-8"></a>
<a id="g8-topic-9"></a>
<a id="g8-topic-10"></a>
<a id="g8-topic-11"></a>

## 2. 符号、链接属性与 C 入口

### 2.1 函数实体、符号与名字改编

有跨翻译单元引用的普通非内联函数通常需要可链接定义，但“每个源函数必定成为最终符号”不成立：内联、未使用实体消除和 LTO 都可能改变结果。模板特化、源码函数与最终机器代码也不是一一对应。

C++ 重载、命名空间、类、模板实参和成员 cv/ref 限定需要区分实体，具体 ABI 常用名字改编（name mangling）编码必要信息。不是所有信息都以直观方式进入名称，例如一些 ABI 的普通非模板函数名不编码返回类型。G8-B1 以分离编译观察 `add(int,int)`、`add(double,double)` 和 C 函数，而不规定所有平台必须采用相同拼写。

### 2.2 C 语言链接属性的实际边界

语言链接属性（language linkage）作用于相应函数类型及具有外部链接的名称。C++ 中的 `extern "C"` 不是导出宏、动态加载指令或表示转换器；C 头文件须在 `__cplusplus` 条件下才出现这段语法。实现通常按目标平台 C 约定处理名称，但 Mach-O 目标文件可能带前导下划线，其他平台也可能有装饰。

把返回类型写成 `std::string`，不会因入口是 C 名字就消除标准库布局、分配器、异常和生命周期要求。稳定跨语言接口常选择标量、指针、显式长度、简单结构和函数指针；优势是可描述、易绑定，不是“C ABI 在所有体系结构上都相同”。[N4950 dcl.link](https://timsong-cpp.github.io/cppwp/n4950/dcl.link)。

**机制示意。** C++ 为什么不能简单把 Symbol 叫 `add`。以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cpp
int add(int, int);
double add(double, double);
```

<a id="g8-section-3"></a>

<a id="g8-topic-12"></a>
<a id="g8-topic-13"></a>
<a id="g8-topic-14"></a>
<a id="g8-topic-15"></a>
<a id="g8-topic-16"></a>
<a id="g8-topic-17"></a>
<a id="g8-topic-18"></a>

## 3. 调用约定与数据模型

### 3.1 调用约定与隐藏参数

调用约定（calling convention）至少涉及参数/结果所在的寄存器或栈位置、聚合体分类、保存寄存器责任、栈对齐及间接传递。大对象可能拆分传参，也可能通过调用者准备的存储传递；不能仅凭源码类型推断所有目标机器的指令序列。

一些返回约定让调用者分配结果存储，再传入隐藏地址，常称结构返回（sret）。这是 ABI lowering，不等于语言层 RVO 或保证复制消除。非静态成员调用还常有对象地址及子对象调整；概念上的 `f(object_address, x)` 不应伪装成合法显式 this 参数签名。虚调用涉及运行时分派元数据，优化器也可能消除实际间接调用。

### 3.2 数据模型与明确宽度

LP64、LLP64 等数据模型使 `long` 与指针宽度关系不同。边界字段采用 `uint32_t`、`int64_t` 可明确数值宽度，但这些精确宽度类型以目标实现提供为前提；它们不同时保证结构对齐、端序、填充或语义兼容。

`size_t` 适合当前进程的对象大小和索引，在同一目标 ABI 的指针＋长度接口中很自然；它不是跨架构的固定宽度线格式。持久文件和网络协议应另定整数宽度、字节序与范围检查，不把机器 ABI 当作存储模式。

<a id="g8-section-4"></a>

<a id="g8-topic-19"></a>
<a id="g8-topic-20"></a>
<a id="g8-topic-21"></a>
<a id="g8-topic-22"></a>
<a id="g8-topic-23"></a>
<a id="g8-topic-24"></a>
<a id="g8-topic-25"></a>
<a id="g8-topic-26"></a>
<a id="g8-topic-27"></a>
<a id="g8-topic-28"></a>
<a id="g8-topic-29"></a>
<a id="g8-topic-30"></a>

## 4. 对象布局、PImpl 与继承

### 4.1 公开类的私有表示仍可能暴露

调用者按值构造公开类时，必须知道大小与对齐；内联函数可能进一步固化成员偏移。给 private 区域增加字段、替换容器或改变基类，都可能影响旧调用者。private 是源码访问控制，不是二进制隔离。

指向实现（pointer to implementation，PImpl）把真实表示和依赖藏进实现文件。公开类只保留稳定约定的指针成员及非内联操作，可降低布局变化和头文件传播，但公开类自身仍有 ABI。`unique_ptr<Impl>` 并非由语言保证永远等于一个裸指针大小；涉及删除 Impl 的操作要在类型完整可见处定义。

### 4.2 PImpl 的收益与成本

PImpl 同时服务布局稳定、编译隔离和依赖隔离。其代价可能包括分配、间接访问、非内联调用、优化可见性下降与特殊成员函数维护。它不是所有类的默认高级写法：一起重编译的内部数据类型可能更适合直接表示，独立演进的 SDK 则更值得付出隔离成本。

### 4.3 布局性质、继承与虚表

现代 C++ 应区分标准布局（standard-layout）、平凡可复制（trivially copyable）、特殊成员平凡性及隐式生命周期相关性质，而非仅用历史 POD 一词概括。标准布局提供特定布局与 offsetof 等推理条件，不保证任意平台上的相同表示。平凡可复制给出满足条件的对象表示复制保证，不授予任意资源对象按字节搬迁和遗忘源对象的权限，也不保证可移植序列化。[N4950 basic.types](https://timsong-cpp.github.io/cppwp/n4950/basic.types)。

继承可能引入基类子对象、虚基类、指针调整与虚表结构。常见实现通过对象中的虚表指针找到函数槽位，但那是实现 ABI，不是 C++ 标准规定的物理图。插入/重排虚函数或改变基类布局可能破坏旧槽位、偏移和转换；公开多态类因此形成较强承诺。

**机制示意。** 为什么 PImpl 存在。以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

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

[机制片段 · 不承诺独立编译]

```cpp
class Decoder::Impl {
    std::vector<float> buffer_;
    Config config_;
    // 其他实现成员省略。
};
```

<a id="g8-section-5"></a>

<a id="g8-topic-31"></a>
<a id="g8-topic-32"></a>
<a id="g8-topic-33"></a>
<a id="g8-topic-34"></a>
<a id="g8-topic-35"></a>
<a id="g8-topic-36"></a>

## 5. RTTI 与异常边界

### 5.1 RTTI 与异常需要兼容的运行时

dynamic_cast、typeid 和类型身份比较依赖相应实现的类型元数据；插件与宿主若使用不兼容编译器、标准库或选项，不能假定类型信息互通。禁用 RTTI、隐藏符号和混用运行时也要纳入支持配置，而非只检查类名相同。

异常传播不仅传递一个 Error 对象，还依赖异常存储、展开表、personality routine、类型匹配及析构执行。统一受控的 C++ 组件可以选择支持跨库异常，但须维护该运行时合同；第三方 SDK、长期插件和跨语言边界不宜隐含依赖它。

### 5.2 异常翻译和 noexcept 各负其责

本章的 C 接口合同禁止 C++ 异常逸出，入口负责捕获并转换成显式状态。写 extern "C" 不会自动插入 catch；写 noexcept 也不自动生成错误码。异常试图离开 noexcept 函数会终止，转换和诊断路径本身也应避免再次抛出。

头文件和定义的异常说明必须一致。G8-B2 用条件宏给 C++ 声明与定义均加 noexcept，而 C 编译端看不到 C++ 专有语法。受控异常只验证翻译路径，不代表分配失败、损坏指针或所有终止路径都经过实验。

<a id="g8-section-6"></a>

<a id="g8-topic-37"></a>
<a id="g8-topic-38"></a>
<a id="g8-topic-39"></a>
<a id="g8-topic-40"></a>
<a id="g8-topic-41"></a>
<a id="g8-topic-42"></a>
<a id="g8-topic-43"></a>
<a id="g8-topic-44"></a>
<a id="g8-topic-45"></a>
<a id="g8-topic-46"></a>
<a id="g8-topic-47"></a>
<a id="g8-topic-48"></a>

## 6. 分配域、标准库与不透明句柄

### 6.1 分配域与调用者缓冲区

创建方若使用不同运行时、自定义 arena 或专门分配器，消费者的 free/delete 未必匹配。稳健默认是由同一分配域释放：create/destroy、make_buffer/free_buffer 成对，明确句柄和缓冲区的拥有者。虚析构能够帮助选择析构逻辑，却不自动修复所有分配来源和运行时不匹配。

调用者提供输入和输出缓冲区，库只在调用期间借用，可避免跨库转移分配所有权。接口仍要说明元素单位、容量、零长度、空指针、重叠以及失败后计数。自定义分配器回调还须规定 context 生命周期、大小/对齐、失败值、线程安全和释放匹配，不能仅传一对函数指针就算完整协议。

### 6.2 标准库接口与源代码包装层

vector、string、shared_ptr 等类型会把表示、模板实例化、分配器、异常和标准库 ABI 带到边界。同一产品统一工具链、同步重编译时可以接受；独立升级的 SDK 要显式控制。span 不分配，但仍是 C++ 库类型，不因此成为通用 C 参数。

C++ 源接口可以使用 span、expected 和 RAII，底层二进制接口使用指针＋长度、状态码及成对创建销毁。包装层负责相互转换；“二进制接口简单”不要求 C++ 用户体验也退化为手工管理。

### 6.3 不透明句柄隐藏布局，不自动赋予所有权

公开头文件只声明 `typedef struct decoder decoder;`，消费者持有 decoder* 而不知道大小，库实现定义真正结构。内部可更换容器、arena 或调度器，不必把变化直接暴露给消费者。

拥有还是借用必须由函数合同规定：create 返回拥有型句柄，destroy 结束其生命周期，get_global 可能只借用。任意地址 reinterpret_cast 成指针不会创造对象；空检查也不能识别悬挂、类型混淆或重复销毁。销毁前无在途调用是常见且必要的前提。

<a id="g8-section-7"></a>

<a id="g8-topic-49"></a>
<a id="g8-topic-50"></a>
<a id="g8-topic-51"></a>
<a id="g8-topic-52"></a>
<a id="g8-topic-53"></a>
<a id="g8-topic-54"></a>
<a id="g8-topic-55"></a>
<a id="g8-topic-56"></a>
<a id="g8-topic-57"></a>
<a id="g8-topic-58"></a>
<a id="g8-topic-59"></a>
<a id="g8-topic-60"></a>
<a id="g8-topic-61"></a>

## 7. 结构版本与存储表示

### 7.1 结构版本、前缀和保留字段

C 结构体比复杂 C++ 类容易约定，但增加字段仍可能改变大小、对齐、步长和传参。结构中携带 struct_size 与 abi_version，可声明调用者理解的版本和范围；库仍须先确认公共前缀可读，再逐项检查新增字段的完整字节范围，不能先按新版 sizeof 复制再检查旧大小。

尾部追加可选字段比重排旧字段更容易兼容，但安全性取决于指针/按值传递、默认值、数组步长和目标 ABI。保留字段可提前预算扩展空间，同时应规定零初始化、禁止使用位及未来协商规则。G8-B2 仅执行 v1 的大小/版本拒绝，不声称完成 v1/v2 升级验证。

### 7.2 枚举、布尔与位域

内部 enum class 很适合类型安全。公开二进制字段应明确底层宽度和数值含义；C 接口也可用固定宽度状态类型加常量。已经发布的数值不能随意复用，消费者对未来未知值要有明确处理，不能无条件落入 unreachable。

bool、char 的语义与表示应按目标 ABI 或接口规则约定；长期跨语言字段可使用规定了 0/非零规则的整数。位域分配和布局依赖实现，不应直接用作可移植协议布局。明确整数宽度仍不等于明确结构布局。

### 7.3 内存布局、packing 与线格式

pragma pack 可能改变对齐/填充，却不能解决端序、生命周期、未对齐访问、版本或语义。将字节缓冲区强转为结构体指针可能同时违反多个访问前提；“本机恰好能读”不是格式定义。

持久与网络格式应规定字节范围和端序，显式编码/解析并检查长度。领域对象和稳定模式之间建立转换，不把含指针、填充或实现布局的内存直接当长期文件。ABI 常用于同进程目标平台约定，wire/storage schema 面向更长时效和更宽环境，二者需要独立设计。

**机制示意。** Size-prefixed Struct；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```c
typedef struct decoder_config {
    uint32_t struct_size;
    uint32_t api_version;

    uint32_t mode;
    uint32_t flags;
} decoder_config;
```

**机制示意。** `#pragma pack(1)` 不是“让 Struct 可以传网络”；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cpp
#pragma pack(push, 1)
struct Packet {
    std::uint8_t type;
    std::uint32_t length;
};
#pragma pack(pop)
```

<a id="g8-section-8"></a>

<a id="g8-topic-62"></a>
<a id="g8-topic-63"></a>
<a id="g8-topic-64"></a>
<a id="g8-topic-65"></a>
<a id="g8-topic-66"></a>
<a id="g8-topic-67"></a>
<a id="g8-topic-68"></a>
<a id="g8-topic-69"></a>
<a id="g8-topic-70"></a>
<a id="g8-topic-71"></a>
<a id="g8-topic-72"></a>
<a id="g8-topic-73"></a>
<a id="g8-topic-74"></a>
<a id="g8-topic-75"></a>

## 8. 可见性、库与插件协商

### 8.1 控制导出面与静态/共享库边界

共享库通常宜默认隐藏内部符号，显式导出稳定入口。暴露大量辅助函数、模板和运行时类型信息，会增加偶然耦合、冲突与演进成本。Windows 常用 dllexport/dllimport，Clang/GCC 系平台常用 visibility 属性；具体宏须考虑静态构建和平台支持，不能把示意宏当作所有编译器通用代码。

静态库通常是对象文件归档，最终链接器按需要选择成员；它本身不是运行时独立加载组件，但对象的调用/布局和运行时仍须兼容。LTO 可能进一步跨翻译单元优化，不保证每个静态链接都有收益。共享库则由加载器映射、绑定和定位依赖，形成更明显的独立升级边界。ELF .so、Mach-O .dylib 和 Windows DLL 的加载细节不同。

### 8.2 插件函数表与显式协商

常见插件流程是加载库、查找单一稳定入口、请求版本化函数表。函数表由应用协议规定字段顺序、大小、可选函数和调用类型，不同于编译器控制的 C++ 虚表。只把工厂名字改成 extern "C"，却返回多态 Base*，仍会暴露 C++ 对象、析构、RTTI 和运行时。

软件版本描述产品演进，ABI 版本描述二进制合同代际。入口可以明确接受或拒绝 requested_version，而不依赖版本号“看起来接近”。函数表、回调、对象及线程都可能引用插件代码；卸载前应停止新调用、等待在途工作、销毁对象并解除回调。加载成功不能证明卸载安全。

**机制示意。** Export Macro；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

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

[机制片段 · 不承诺独立编译]

```cpp
MYLIB_API
int decoder_create(...);
```

**机制示意。** Function Table；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

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

<a id="g8-section-9"></a>

<a id="g8-topic-76"></a>
<a id="g8-topic-77"></a>
<a id="g8-topic-78"></a>
<a id="g8-topic-79"></a>
<a id="g8-topic-80"></a>
<a id="g8-topic-81"></a>
<a id="g8-topic-82"></a>
<a id="g8-topic-83"></a>
<a id="g8-topic-84"></a>
<a id="g8-topic-85"></a>
<a id="g8-topic-86"></a>
<a id="g8-topic-87"></a>
<a id="g8-topic-88"></a>
<a id="g8-topic-89"></a>
<a id="g8-topic-90"></a>
<a id="g8-topic-91"></a>
<a id="g8-topic-92"></a>
<a id="g8-topic-93"></a>

## 9. 兼容性变更与构建配置

### 9.1 哪些变化需要兼容性复核

字段、基类、虚函数、对齐/packing、枚举表示、参数或返回类型、异常说明以及标准库/编译器 ABI 配置，都可能影响边界。参数类型变化不必然改变每个 ABI 的链接名；C 名字通常不编码类型，反而可能在错误签名下仍链接成功。某些普通 C++ 返回类型也不进入名字改编，所以“符号没变”远远不够。

noexcept 同时涉及类型系统和失败语义，不能当无关装饰。Debug/Release 标签本身不决定兼容性；真正需要记录的是调试迭代器、运行时选择、RTTI/异常开关、调用约定、packing、标准库 ABI 选项和插桩配置。不是所有选项都会改变布局，但都应在支持配置中有去向。

### 9.2 头文件逻辑也会分发行为

inline 函数和模板实例化可能已编进调用者，更新共享库不能自动更新旧指令。公共头文件改变语义，即使新的库符号兼容，也可能让新旧消费者保留不同逻辑。模板定义通常需在实例化点可达，集中显式实例化是受控选择，不意味着任意组合都由二进制库提供。

薄泛型前端可以校验约束、规范化输入，再进入非模板核心；稳定外部边界继续降为明确的 C 类型。这样保留类型友好的源码接口，同时控制实例化传播与二进制变化面。

### 9.3 ODR 与配置一致性

不同组件因宏、不同头文件或选项而看到不同 inline、模板或类定义，可能违反单一定义规则（ODR）。共享库不是语言规则的自动隔离层；加载器符号绑定行为还会增加诊断难度。

升级审查应同时记录头文件身份、导出符号、类型表示、依赖运行时与消费者构建配置。只保留 -std=c++23 不能重建 ABI 上下文；一起重编译与保留旧消费者的验证是不同命题。

<a id="g8-section-10"></a>

<a id="g8-topic-94"></a>
<a id="g8-topic-95"></a>
<a id="g8-topic-96"></a>
<a id="g8-topic-97"></a>
<a id="g8-topic-98"></a>
<a id="g8-topic-99"></a>
<a id="g8-topic-100"></a>
<a id="g8-topic-101"></a>
<a id="g8-topic-102"></a>
<a id="g8-topic-103"></a>
<a id="g8-topic-104"></a>
<a id="g8-topic-105"></a>
<a id="g8-topic-106"></a>
<a id="g8-topic-107"></a>
<a id="g8-topic-108"></a>
<a id="g8-topic-109"></a>
<a id="g8-topic-110"></a>

## 10. C 接口设计规则与错误输出

### 10.1 十二条 C 接口约束的用途

本章的外部接口 profile 包括：C 链接入口；异常止于边界；状态对象采用不透明句柄；显式拥有/借用；输入用指针＋长度；适用时由调用者拥有输出；稳定字段使用明确宽度；版本与范围协商；不暴露 STL；不使用 C++ 引用参数；明确线程安全；明确生命周期。

这些规则缩小外部合同，不要求整个产品内部都用 C 风格。实现内部仍可使用容器、泛型、span、expected 和 RAII。每条规则都应有对应前提，例如指针＋长度须说明空范围是否允许空地址，以及库是否会在返回后保留输入。

### 10.2 错误状态要可独立解释

状态码应有稳定数值与明确成功/失败含义。last_error 可以提供详细消息，但必须规定是线程局部、句柄局部还是全局状态，何时覆盖以及并发读取是否安全。把错误对象或消息缓冲区作为调用者提供的输出，能减少隐式状态，却仍需要说明截断、所需长度和终止字符。

创建接口采用状态＋out_handle 时，失败将有效输出位置清空，成功转移一个可销毁句柄。不能把一个仍拥有旧对象的槽位交给 create 后期待自动替换；没有声明的清理和事务语义不会由输出参数形式自动产生。

### 10.3 两次调用不自动形成快照

先用空缓冲区查询 required，再分配并读取，是可变长度输出的常见模式。两次调用之间数据可能增长或改变，因此需定义容量不足重试、版本号、快照句柄或锁定协议。

还要规定 required 与 written 的单位、查询是否有副作用、失败是否部分写入。消费者不能把第一次查询到的长度当成第二次必然足够的永久保证。

<a id="g8-section-11"></a>

<a id="g8-topic-111"></a>
<a id="g8-topic-112"></a>
<a id="g8-topic-113"></a>
<a id="g8-topic-114"></a>
<a id="g8-topic-115"></a>
<a id="g8-topic-116"></a>

## 11. 回调、并发与销毁

### 11.1 函数指针与 context 构成回调协议

C 回调通常组合 function pointer 与 void* context，C++ 包装层再经静态 trampoline 恢复对象。协议须说明回调是只在当前调用中借用，还是保存到未来；由哪些线程执行；能否并发；数据指针有效多久；注销是否等待已开始的回调结束。

若 context 已销毁而库稍后调用，仍是生命周期错误，类型签名不能保护它。回调应遵守不抛异常的边界约定；如果支持回调错误返回，必须定义它如何影响当前操作的输出和状态。

### 11.2 重入、锁与销毁

持有内部锁调用不可控用户代码，可能因回调重入而死锁，也可能放大锁持有时间。接口需明确允许的重入集合；避免在热锁内调用外部代码是稳健默认，而不是单靠“回调很短”的假设。

线程合同至少区分同一句柄是否可并发、不同句柄是否独立、读者/写者规则和销毁前提。内部 mutex 不能让“另一线程已销毁的对象”重新合法；destroy 通常要求没有在途操作。异步接口还应定义 close/cancel/join 与销毁次序。G8-B2 故意采用同步回调，未验证异步注销协议。

**机制示意。** C Callback；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```c
typedef void (*decoder_log_fn)(
    void* context,
    uint32_t level,
    const char* message,
    size_t message_len);
```

[机制片段 · 不承诺独立编译]

```c
decoder_set_log_callback(
    decoder*,
    decoder_log_fn,
    void* context);
```

<a id="g8-section-12"></a>

<a id="g8-topic-117"></a>
<a id="g8-topic-118"></a>
<a id="g8-topic-119"></a>
<a id="g8-topic-120"></a>
<a id="g8-topic-121"></a>
<a id="g8-topic-122"></a>
<a id="g8-topic-123"></a>
<a id="g8-topic-124"></a>
<a id="g8-topic-125"></a>
<a id="g8-topic-126"></a>
<a id="g8-topic-127"></a>
<a id="g8-topic-128"></a>
<a id="g8-topic-129"></a>

## 12. 包装层、跨语言与借用

### 12.1 RAII 包装不改变底层合同

C++ 包装器可以持有 decoder*，析构调用 destroy，禁用复制并在移动时转移句柄；返回 expected，将 span 转为指针＋长度。包装层仍要定义创建失败、移动后状态和自移动/替换行为，不能因为类有析构就假定所有权完整。

丰富的 C++ 源接口与小而稳定的 C 二进制接口可同时存在。包装器通常随消费者编译，因此其模板、inline 语义和所需标准库仍属于源码分发合同。

### 12.2 Rust 与 Zig 的表示约定仍有边界

Rust 默认布局不是通用 C ABI。repr(C) 请求相应 C 表示规则，但嵌套成员的表示、枚举有效值和调用约定仍要单独审查；borrow checker 不会替外部原始指针证明有效期或线程安全。

Zig 能导入和导出 C 接口，但 slice、error union、allocator 和 comptime 类型也不能未经设计直接当 C 类型。C++ span、Rust/Zig slice 通常展开为地址＋长度，并在语言包装层恢复检查。分配器抽象不会自动跨语言互通；由哪侧分配、哪侧释放仍需明确。

### 12.3 拥有、借用和 const 是不同维度

create 返回拥有型句柄；只在调用期间使用输入是短借用；保存输入指针到返回之后则是长期借用，必须额外约束寿命、可变性和并发。若不能建立这些约束，应复制数据或显式转移所有权，不能暗中延长借用。

const T* 限制经该访问路径修改，不说明其他别名或线程不能改动。const decoder* 可以表达逻辑只读，但实现仍可能更新缓存、指标或同步状态；const 不是完整线程安全协议。

**机制示意。** C ABI 不意味着 C++ 用户体验差；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```c
decoder* decoder_create(...);
void decoder_destroy(decoder*);
```

[机制片段 · 不承诺独立编译]

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

<a id="g8-section-13"></a>

<a id="g8-topic-130"></a>
<a id="g8-topic-131"></a>
<a id="g8-topic-132"></a>
<a id="g8-topic-133"></a>
<a id="g8-topic-134"></a>
<a id="g8-topic-135"></a>
<a id="g8-topic-136"></a>
<a id="g8-topic-137"></a>
<a id="g8-topic-138"></a>

## 13. 二进制检查与语义合同

### 13.1 从二进制中读取证据

使用 nm、反改编工具、objdump/readelf、otool 或 dumpbin，分别观察目标符号、动态导出和依赖。ELF 的完整符号表与动态符号表要区分；本批 Mach-O 实验记录原始/反改编符号与 otool 依赖，不把其中一个工具当成所有 ABI 属性的验证器。

升级前比较导出集合、函数合同、类型大小/对齐/偏移、虚接口、枚举数值、版本协商和依赖 ABI。自动 ABI 比较工具可以辅助，但语义、生命周期和性能合同仍需有针对性的审查与实验。

### 13.2 语义、有效期与运行约束

同一个签名若把米改成厘米，二进制布局可能未变而调用语义已破坏。返回 const char* 还必须说明是静态存储、句柄内借用、下次调用失效还是调用者负责释放。同步入口若改为保存输入供异步处理，也改变了关键合同。

同样的函数名可以对应不同的线程安全和实时行为。无动态分配、不阻塞或有界执行若是产品承诺，就应单独版本化并测试；不能由固定签名或“C ABI 简单”推导。本批不做实时性和性能验收。

<a id="g8-section-14"></a>

<a id="g8-topic-139"></a>
<a id="g8-topic-140"></a>
<a id="g8-topic-141"></a>
<a id="g8-topic-142"></a>
<a id="g8-topic-143"></a>
<a id="g8-topic-144"></a>
<a id="g8-topic-145"></a>
<a id="g8-topic-146"></a>
<a id="g8-topic-147"></a>

## 14. 库接口的分层实现

### 14.1 头文件、实现与包装分工

公开 C 头文件只保留不透明类型、状态常量、配置、条件链接属性、导出声明及回调类型。实现文件定义对象，转换配置、检查调用前提并捕获可恢复异常；C++ 源包装提供 RAII、span 和 expected。本章完整可编译接口集中维护在 G8-B2，不让多份签名不同的示例成为并行事实源。

创建时先清空有效的输出槽，再检查配置版本/大小并分配；处理时先置零有效计数位置，检查空范围和容量，再写数据。示例要求容量不足与受控异常发生时输出不变，成功时输出长度和全部元素正确。span 本身并不会验证外部指针的可读写性。

### 14.2 插件与跨模块析构

extern "C" BasePlugin* create_plugin() 只稳定入口名字，宿主仍需理解对象的虚表、析构和运行时。更强隔离可采用版本化 C 函数表和不透明句柄，显式约定 create/destroy/process。

由创建域提供 destroy 可减少释放不匹配；虚析构的正确分派不等于任意自定义内存都能交给宿主 delete。无论采用哪种方案，都必须让对象先于提供析构代码的模块卸载。

<a id="g8-section-15"></a>

<a id="g8-topic-148"></a>
<a id="g8-topic-149"></a>
<a id="g8-topic-150"></a>
<a id="g8-topic-151"></a>
<a id="g8-topic-152"></a>
<a id="g8-topic-153"></a>
<a id="g8-topic-154"></a>
<a id="g8-topic-155"></a>
<a id="g8-topic-156"></a>
<a id="g8-topic-157"></a>

## 15. 兼容策略与边界分级

### 15.1 三种策略按边界选择

一起重编译全部组件的内部产品，可接受较丰富的 C++ 类、模板和容器接口，独立 ABI 演进压力较小。稳定 C++ ABI 则需要受控工具链、PImpl、可见性策略、谨慎虚接口和兼容检查。长期 SDK、插件及跨语言边界常采用稳定 C 接口加语言包装，但仍须控制平台 ABI 和语义版本。

不能把最后一种策略机械推广到所有内部模块。边界越独立，显式合同越重要；本地算法和容器不必为想象中的跨语言需求退化为 void*。

### 15.2 六类边界及审查强度

同一翻译单元主要由单次编译控制；分离翻译单元增加声明、定义与 ODR 一致性；静态库增加预编译对象和最终链接兼容要求。同一产品中的共享库可以统一版本，但仍应理解加载和运行时耦合。

第三方二进制 SDK/插件需要明确旧消费者与新提供者的支持矩阵；跨语言接口再增加表示、错误和生命周期映射。分级服务风险识别，不意味着前几类没有 ABI，也不意味着 C 接口可以跨不同位宽直接互调。

<a id="g8-section-16"></a>

<a id="g8-topic-158"></a>
<a id="g8-topic-159"></a>
<a id="g8-topic-160"></a>
<a id="g8-topic-161"></a>
<a id="g8-topic-162"></a>
<a id="g8-topic-163"></a>
<a id="g8-topic-164"></a>
<a id="g8-topic-165"></a>
<a id="g8-topic-166"></a>

## 16. 接口审查清单

### 16.1 从签名到生命周期的审查顺序

先标明哪些类型穿过边界、是否含编译器或标准库特有表示；再逐项列拥有者、分配域、释放入口、借用期和是否保存指针。错误模型要区分状态、异常、部分输出及终止路径，不能只写“出错返回非零”。

接着检查线程安全、回调线程、重入和销毁并发；核对版本协商、结构范围、未知值和保留位。最后检查异步句柄的停止、取消、等待与销毁顺序。没有这些文字合同的 pointer signature 不算完整接口设计。

<a id="g8-section-17"></a>

<a id="g8-topic-167"></a>
<a id="g8-topic-168"></a>
<a id="g8-topic-169"></a>
<a id="g8-topic-170"></a>
<a id="g8-topic-171"></a>
<a id="g8-topic-172"></a>
<a id="g8-topic-173"></a>

## 17. 实践路线与验证选择

### 17.1 本批验证与可选深化

原有七条实践路线保留：名字改编、布局变化、PImpl、C 包装、跨语言调用、回调和版本演进。G8-B1 落实符号与链接负例；G8-B2 落实 C11 调用者、C++ 共享提供者、同步回调和 v1 拒绝合同。二者的完整代码和命令在后文集中提供。

布局深化应分别在合法的 v1/v2 翻译单元观察表示，不把不兼容旧对象交给新代码执行并期待固定崩溃。PImpl 深化可比较实现字段变化前后的公开布局，但需固定工具链。Rust/Zig 调用、异步回调与 v1/v2 前缀协商仍是可选、未执行路线；不要把练习题列出等同于已经验证。

<a id="g8-section-18"></a>

<a id="g8-topic-174"></a>
<a id="g8-topic-175"></a>
<a id="g8-topic-176"></a>
<a id="g8-topic-177"></a>
<a id="g8-topic-178"></a>
<a id="g8-topic-179"></a>
<a id="g8-topic-180"></a>
<a id="g8-topic-181"></a>
<a id="g8-topic-182"></a>
<a id="g8-topic-183"></a>
<a id="g8-topic-184"></a>
<a id="g8-topic-185"></a>
<a id="g8-topic-186"></a>
<a id="g8-topic-187"></a>

## 18. 常见误判

### 18.1 兼容性误判

“public API 没变，所以 ABI 没变”遗漏私有布局；“都用 C++23”遗漏实现 ABI；“平凡可复制可以直接永久存盘”遗漏指针、填充、端序和版本；“pack(1) 就是网络格式”混淆布局和编码。

“extern C 让 vector 变成 C 类型”以及“无分配的 span 适合直接跨所有 C ABI”都混淆名称/成本与表示。factory 返回 Base* 仍暴露 C++ 多态对象；exception 跨 DLL 总是安全也不是可支持的普遍结论。

### 18.2 生命周期与演进误判

“库分配、调用者 free 就行”遗漏分配域；“opaque 只是保密实现”遗漏布局隔离；“inline 或模板逻辑随共享库更新”遗漏消费者已编译代码。

“符号仍兼容所以语义兼容”遗漏单位、所有权、借用与线程合同。狭义 ABI 主要约束机器交互，但工程接口审查必须覆盖这些非位级条件，不能借术语边界把责任删掉。

<a id="g8-section-19"></a>

<a id="g8-topic-188"></a>
<a id="g8-topic-189"></a>
<a id="g8-topic-190"></a>
<a id="g8-topic-191"></a>

## 19. C++、Zig 与 Rust 对照

### 19.1 语言内部丰富，边界保持明确

C++ 的类、模板、STL、异常和 RAII 适合内部建模，但在独立边界上需要评估运行时耦合。Zig 的显式布局、分配和 C 互操作便于集成，却仍有不直接等于 C 表示的 slice 和 error union。Rust 的所有权、枚举、trait 与 Result 也需通过受约束的 FFI 包装连接外部世界。

共同结构是语言原生 API → 薄适配层 → 小而明确的 C 接口。它是常见工程策略，不是所有项目必须采用的唯一架构。学习时比较的是合同在哪里表达、哪些条件由语言检查、哪些只能由跨边界协议和测试承担。

<a id="g8-section-20"></a>

## 20. 完整实验：符号与 C 二进制接口

这些实验由正文提取到新临时目录，完整文件是唯一维护来源。执行器只运行已审阅的本地代码，不是安全沙箱；不修改历史 PDF、FM 或出版系统。

```sh
python3 c++/learning/verify_native.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

### 20.1 G8-B1 · 语言链接、符号与目标链接诊断

**待验证命题。** 分别编译 C 定义、C++ 重载与调用者；观察 C/C++ 名称差异。缺少 C 链接声明的调用者可以编译，但必须因目标符号未解析而链接失败。

**范围与前提。** 只观察本次 Clang/Mach-O 符号，不规定所有平台名字；不执行不匹配布局，不把每个源函数等同于最终符号。

<!-- n-lab {"id":"G8-B1","mode":"symbols"} -->

[完整实验 · G8-B1 · sum.c]

<!-- n-file {"path":"sum.c"} -->
```c
int native_sum(int a, int b) { return a + b; }
```

[完整实验 · G8-B1 · overloads.cpp]

<!-- n-file {"path":"overloads.cpp"} -->
```cpp
int add(int a, int b) { return a + b; }
double add(double a, double b) { return a + b; }
```

[完整实验 · G8-B1 · main.cpp]

<!-- n-file {"path":"main.cpp"} -->
```cpp
extern "C" int native_sum(int, int);
int add(int, int);
double add(double, double);
int main() {
    return native_sum(2, 3) == 5 && add(4, 5) == 9 &&
           add(1.25, 2.5) == 3.75 ? 0 : 1;
}
```

[完整实验 · G8-B1 · missing.cpp]

<!-- n-file {"path":"missing.cpp"} -->
```cpp
// Intentional link-negative: declaration has C++ linkage.
int native_sum(int, int);
int main() { return native_sum(2, 3) == 5 ? 0 : 1; }
```

**运行与解释。** 本节开头的统一命令按 `G8-B1` 提取全部文件；具体编译、链接、运行及负例命令保存在 `results.json`。先预测结果，再用完整诊断核对，不能把任意构建失败或超时当作预期反例。

### 20.2 G8-B2 · 真正的 C 消费者与共享库接口

**待验证命题。** 头文件以 C11 编译，库以 C++23 编译，C 调用端链接并加载共享库。检验配置大小/版本、拥有句柄、完整输出、容量失败不写入、同步回调与异常到状态码的转换。

**范围与前提。** 非空配置指针必须指向完整可读 config 对象；struct_size 只是声明，不是内存验证。其他非空地址也必须有效。输入/输出/计数地址不重叠；同一句柄调用与销毁不并发；回调只在本次调用中同步借用，不抛异常、不销毁或重入该句柄。未测试分配失败、历史 v1/v2 混用、插件 dlopen/卸载或 Rust/Zig 调用。

<!-- n-lab {"id":"G8-B2","mode":"c_shared"} -->

[完整实验 · G8-B2 · decoder.h]

<!-- n-file {"path":"decoder.h"} -->
```c
#ifndef NATIVE_DECODER_H
#define NATIVE_DECODER_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
#define DEC_NOEXCEPT noexcept
extern "C" {
#else
#define DEC_NOEXCEPT
#endif
#define DEC_API __attribute__((visibility("default")))
typedef struct decoder decoder;
typedef uint32_t dec_status;
enum { DEC_OK, DEC_INVALID, DEC_SMALL, DEC_INTERNAL };
typedef struct dec_config {
    uint32_t struct_size;
    uint32_t abi_version;
    uint32_t model;
} dec_config;
typedef void (*dec_callback)(void* context, size_t count);
DEC_API dec_status dec_create(const dec_config*, decoder**) DEC_NOEXCEPT;
DEC_API void dec_destroy(decoder*) DEC_NOEXCEPT;
DEC_API dec_status dec_decode(decoder*, const uint8_t*, size_t,
    float*, size_t, size_t*, dec_callback, void*) DEC_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#endif
```

[完整实验 · G8-B2 · decoder.cpp]

<!-- n-file {"path":"decoder.cpp"} -->
```cpp
#include "decoder.h"
#include <stdexcept>
struct decoder { uint32_t model; };
extern "C" dec_status dec_create(const dec_config* config,
                                  decoder** out) noexcept {
    if (!out) return DEC_INVALID;
    *out = nullptr;
    if (!config || config->struct_size < sizeof(dec_config) ||
        config->abi_version != 1 || config->model > 1) return DEC_INVALID;
    try {
        *out = new decoder{config->model};
        return DEC_OK;
    } catch (...) { return DEC_INTERNAL; }
}
extern "C" void dec_destroy(decoder* value) noexcept { delete value; }
extern "C" dec_status dec_decode(decoder* value, const uint8_t* input,
    size_t size, float* output, size_t capacity, size_t* count,
    dec_callback callback, void* context) noexcept {
    if (!count) return DEC_INVALID;
    *count = 0;
    if (!value || (!input && size) || (!output && capacity)) return DEC_INVALID;
    if (capacity < size) return DEC_SMALL;
    try {
        if (value->model == 1) throw std::runtime_error{"controlled fault"};
        for (size_t i = 0; i < size; ++i) output[i] = input[i] * 2.0f;
        *count = size;
        if (callback) callback(context, *count);
        return DEC_OK;
    } catch (...) { return DEC_INTERNAL; }
}
```

[完整实验 · G8-B2 · consumer.c]

<!-- n-file {"path":"consumer.c"} -->
```c
#include "decoder.h"
#include <stdio.h>
static void counted(void* context, size_t count) { *(size_t*)context += count; }
int main(void) {
    dec_config config = {sizeof(dec_config), 1, 0};
    decoder* handle = NULL;
    if (dec_create(&config, &handle) != DEC_OK || !handle) return 1;
    decoder* rejected = handle; /* borrowed alias used only as an output sentinel */
    config.abi_version = 2;
    if (dec_create(&config, &rejected) != DEC_INVALID || rejected) return 2;
    config.abi_version = 1;
    config.struct_size = sizeof(dec_config) - 1;
    if (dec_create(&config, &rejected) != DEC_INVALID || rejected) return 3;
    const uint8_t input[] = {1, 7, 255};
    float output[] = {-1, -1, -1};
    size_t count = 99, callbacks = 0;
    if (dec_decode(handle, input, 3, output, 3, &count, counted, &callbacks) ||
        count != 3 || output[0] != 2 || output[1] != 14 || output[2] != 510 ||
        callbacks != 3) return 4;
    output[0] = output[1] = output[2] = -1;
    if (dec_decode(handle, input, 3, output, 2, &count, counted, &callbacks) != DEC_SMALL ||
        count != 0 || output[0] != -1 || output[1] != -1 || output[2] != -1 ||
        callbacks != 3) return 5;
    if (dec_decode(handle, NULL, 0, NULL, 0, &count, NULL, NULL) != DEC_OK ||
        count != 0) return 6;
    if (dec_decode(handle, NULL, 3, output, 3, &count, NULL, NULL) != DEC_INVALID ||
        count != 0) return 7;
    dec_destroy(handle);
    dec_destroy(NULL);
    config.struct_size = sizeof(dec_config);
    config.model = 1;
    if (dec_create(&config, &handle) || !handle) return 8;
    if (dec_decode(handle, input, 3, output, 3, &count, NULL, NULL) != DEC_INTERNAL ||
        count != 0 || output[0] != -1 || output[1] != -1 || output[2] != -1) return 9;
    dec_destroy(handle);
    puts("c-abi-contract-ok");
    return 0;
}
```

**运行与解释。** 本节开头的统一命令按 `G8-B2` 提取全部文件；具体编译、链接、运行及负例命令保存在 `results.json`。先预测结果，再用完整诊断核对，不能把任意构建失败或超时当作预期反例。

**未执行路线。** 前面列出的扩展练习仍可用于学习，但不自动计入本批通过项。执行记录按文档检查、编译/链接/消费、性能观察、并发检测分别说明；后两类在本批不运行。


<a id="g8-section-21"></a>

## 21. 边界复核协议

从边界类型开始，依次追到消费者实际行为。这里的清单服务审查，不是全部已有自动化证据。

| 审查层次 | 核心问题 | 证据入口 |
| --- | --- | --- |
| 边界 / API / ABI | 独立升级还是一起重编译？ | 支持配置与消费者身份 |
| 符号 / 调用 | 名称、类型、参数约定是否一致？ | 目标文件、诊断、平台 ABI |
| 布局 / 版本 | 大小、偏移、范围如何协商？ | 布局观察与版本矩阵 |
| 所有权 / 分配 | 谁创建，谁释放，在哪个域？ | 成对入口与失败路径 |
| 错误 / 生命周期 | 失败输出是什么，借用到何时？ | 状态测试与文字合同 |
| 并发 / 回调 | 可否重入，谁等待在途工作？ | 同步/销毁协议 |
| 跨语言 | 表示及语义由哪一层恢复？ | 真正的异语言消费者 |

<a id="g8-section-22"></a>

## 22. Final Gate

应该能闭卷回答：

### 22.1 API / ABI

1. API 与 ABI 的区别是什么？
2. 为什么 private member 变化也可能 ABI break？
3. 为什么 source-compatible 不等于 binary-compatible？

### 22.2 Symbol

1. C++ 为什么需要 name mangling？
2. `extern "C"` 真正改变什么？
3. 为什么它不能让 `std::string` 获得稳定 C ABI？

### 22.3 Calling Convention

1. Calling convention 至少规定哪些东西？
2. 为什么大型 return object 可能需要 hidden result pointer？

### 22.4 Layout

1. 为什么 class inheritance/vtable 会扩大 ABI surface？
2. `trivially_copyable` 为什么不等于 portable serialization？
3. 为什么 packing 不能解决 endianness？

### 22.5 Ownership

1. 为什么 library allocate / caller free 可能错误？
2. caller-provided output buffer 有什么优势？
3. opaque handle 如何表达 owning stateful object？

### 22.6 Error

1. 为什么 exception 不应穿过 C ABI？
2. `noexcept` 在 FFI boundary 有什么作用？

### 22.7 STL / Templates

1. 为什么 `vector` / `string` 会扩大 binary coupling？
2. 为什么 template implementation 经常实际编进 caller？
3. 为什么 inline implementation 会让旧 caller保留旧逻辑？

### 22.8 Versioning

1. `struct_size` 有什么价值？
2. 为什么 append-only field evolution 比 reorder field 更容易兼容？
3. Software version 与 ABI version 为什么不是一回事？

### 22.9 Plugins

1. 为什么 `extern "C" Base* create()` 仍然不是纯 C ABI？
2. versioned function table为什么适合插件？

### 22.10 Cross-language

1. 为什么 Rust `repr(C)` / Zig C interoperability仍然不能取消 ownership/lifetime contract？
2. 为什么 pointer + length 是 span/slice 跨 FFI 的自然降级形式？

<a id="g8-section-23"></a>

## 23. Final Gate · 参考答案与常见误判

### 23.1 API / ABI

1. API 约束源码可见名称、类型和语义；ABI 约束独立编译组件对名称、调用与表示的共同理解。相同源码语言版本不保证相同 ABI。

2. 调用者若按值构造公开类，编译时已把大小、对齐甚至内联成员访问写入机器代码。private 只控制源码访问，不消除布局承诺；PImpl 减少这一承诺，但仍保留指针成员及运行时合同。

3. 改动后重新编译可能成功，而旧机器代码仍按旧偏移读写。常见误判是拿“新头文件＋新库一起构建通过”证明旧调用者兼容；那其实没有测试旧调用者。

### 23.2 Symbol

1. C++ 重载、命名空间和模板需要区分实体，具体 ABI 常用名字改编编码必要信息。并非所有函数都在优化后的制品中保留独立符号。

2. extern "C" 指定相应名称/函数类型的语言链接属性；实现按平台 C 约定处理，不是统一跨平台符号拼写，也不是自动导出。

3. std::string 的布局、分配、异常和生命周期不因链接名改变。G8-B1 的链接负例只说明名字约定不匹配，不证明任意 C 链接签名都适合 C 调用。

### 23.3 Calling Convention

1. 参数和返回值位置、寄存器保存责任、栈对齐、聚合体分类及隐藏参数都可能属于约定。不能仅检查双方函数名一致。

2. 返回大对象时，某些 ABI 让调用者提供结果存储地址；是否采用该方式取决于类型和目标 ABI。它不是语言层 RVO 的同义词，优化后的汇编也不反向定义语言保证。

### 23.4 Layout

1. 继承会引入子对象、指针调整、可能的虚表与运行时类型信息。虚函数槽位和基类偏移改变可能破坏旧调用者，不能只审查显式字段。

2. 平凡可复制只提供有条件的表示复制保证，不能把指针、填充、端序和目标布局固定成长期文件格式。

3. packing 影响布局/对齐，端序决定多字节数值的字节次序。二者独立；压紧布局也不解决任意字节地址的生命周期和合法访问。

### 23.5 Ownership

1. 创建方可能使用不同运行时或自定义分配器，调用者的 free/delete 未必匹配。让同一分配域提供 destroy，或明确协商分配器。

2. 调用者拥有输出缓冲区可以避免跨域转移，但还必须定义容量不足、部分输出、重叠和计数规则。指针＋长度不是内存安全认证。

3. create/destroy 及文字合同赋予句柄所有权，不透明类型本身只隐藏布局。G8-B2 检查成功非空、失败清空和同步借用；不验证悬挂地址或重复销毁。

### 23.6 Error

1. C 调用者不理解任意 C++ 异常运行时；跨语言接口应把异常止于边界，输出可解释的状态。统一受控 C++ 运行时下跨库异常是另一种可选合同，不能和纯 C 接口混同。

2. noexcept 限制传播而不自动 catch；异常离开会终止。声明/定义必须匹配，转换路径也不能再次失败。G8-B2 的 model=1 只注入受控异常，不代表实际分配失败已测试。

### 23.7 STL / Templates

1. vector/string 暴露标准库布局、分配器和运行时要求；同一产品统一构建可接受，不等于第三方 SDK 长期稳定。

2. 模板定义通常在调用者可达处实例化，显式实例化是受控例外。3. inline 逻辑也可能编入旧调用者；只换共享库无法更新这些机器指令。常见误判是把头文件实现当成库端可随时替换的细节。

### 23.8 Versioning

1. struct_size 让库知道调用者声明的可读/可写范围，但不能验证任意指针或谎报大小；先检查公共前缀，再读可选字段。

2. 尾部追加可能保留已有偏移，但仍需检查传递方式、大小、对齐、默认值及数组步长，不自动兼容。3. 软件版本记录产品演进，ABI 版本记录特定二进制合同；二者可以独立变化。

G8-B2 仅拒绝未知版本与过小声明尺寸，没有执行 v1 调用者对 v2 实现的兼容实验。把版本检查成功写成全面 ABI 演进验收，是最需要避免的误判。

### 23.9 Plugins

1. 返回 Base* 仍暴露 C++ 多态对象、析构、类型信息和运行时，C 名称仅稳定了入口名字。

2. 版本化函数表让字段顺序、可选能力和协商显式化，但宿主仍要核对函数类型和可用范围。表和函数指针在插件卸载后不可继续使用；必须先停止调用、等待回调并销毁对象。动态加载成功不证明卸载协议安全。

### 23.10 Cross-language

1. Rust repr(C) 或 Zig C 互操作约定表示/调用的一部分，不替外部原始指针证明有效期、别名规则、线程访问或分配域。各语言的安全包装必须从同一文字合同恢复这些限制。

2. pointer＋length 显式表达连续缓冲区地址和元素数，便于不同语言重建视图；还需规定元素单位、空范围、可写性及借用时长。本批 C11 消费者是跨语言的有限实例，不能替代未运行的 Rust/Zig FFI 检查。

<a id="g8-section-24"></a>

## 24. 工程原则与全链回查

如果半年以后只能记十五条：

1. API 是 source-level contract，ABI 是 independently compiled binaries 之间的 machine-level contract。

2. 相同 C++ 标准版本不自动意味着相同 binary ABI；mangling、calling convention、layout 和 runtime属于 implementation/platform ABI。

3. C++ public class 的 private representation 也可能进入 ABI，因为 caller 需要知道 `sizeof`、alignment 和 layout。

4. PImpl 的核心价值之一是把 private representation 从 public binary layout 中移除。

5. `extern "C"` 主要建立 C language linkage；它不会让 C++ object、STL、exception突然变成 C ABI。

6. 稳定跨语言/native SDK boundary 的默认最小公分母是：C linkage + opaque handles + primitive scalars + pointer/length + explicit ownership。

7. 谁 allocate，通常就应该由同一 allocation domain负责 free；allocator ownership 是 ABI contract。

8. C++ exception 不应穿过 C ABI；boundary 应将异常转换为显式 error representation。

9. 不要把 in-memory C++ layout 当 wire/storage schema；packing、endianness、versioning、lifetime 是不同问题。

10. STL types 在同一受控 toolchain 内可以很好用，但暴露它们会显著扩大 stable binary ABI coupling。

11. Opaque Handle 能把内部 class layout、allocator、container 与实现演进隐藏在 stable ABI 后面。

12. Plugin 边界优先使用 versioned C function table，而不是依赖 compiler-controlled C++ vtable/RTTI ABI。

13. ABI versioning必须显式考虑 struct size、field order、enum values、symbol set 与 semantic behavior。

14. Ownership、lifetime、thread safety、callback threading 和 shutdown 虽然不全是 bit-level ABI，却都是完整 binary interface contract 的一部分。

15. 优秀 native library architecture 通常是 Rich C++ Internals + Small Stable Binary Boundary + Idiomatic Language Wrappers。

从 G0 的符号/重定位/加载到 G1～G7 的对象、所有权和同步，最终都落实到接口合同。内部返回 `std::vector<std::shared_ptr<Foo>>` 可以合理；若作为第三方 SDK 边界，则同时承诺容器、标准库、引用计数、分配域、对象表示与线程行为。

<a id="g8-section-25"></a>

## 25. 参考资料与验证边界

语言规则采用 [N4950 链接属性](https://timsong-cpp.github.io/cppwp/n4950/dcl.link)、[对象表示](https://timsong-cpp.github.io/cppwp/n4950/basic.types) 和 [异常终止](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)。[Itanium C++ ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html) 是具体 ABI 资料，不是 C++ 标准或所有平台通用实现；[Apple run-path 文档](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/DynamicLibraries/100-Articles/RunpathDependentLibraries.html) 用于理解本次 @rpath/@loader_path 配置。

跨语言表示参见 [Rust Reference](https://doc.rust-lang.org/reference/type-layout.html#the-c-representation) 和 [Zig C 互操作文档](https://ziglang.org/documentation/master/#C)。这些链接支持概念回查，不代表本批运行了对应编译器。

[本批验证与限制](learning/native-revision.md)区分实际编译/链接/消费结果、未运行项及源稿风险。只有完整实验源码经过相应执行器验证，其余片段仅用于解释机制。PDF 未构建、未渲染、未验收；本章源稿状态不能代替出版或跨平台批准。
