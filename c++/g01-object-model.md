# G1 · 对象模型与生命周期

Modern C++ Systems Engineering · [Editorial Profile v1.0](editorial-profile.md)

编辑状态：Professional presentation refresh。PDF：NOT BUILT / NOT VALIDATED。

呈现修订稿 1.2 · C++23。前置：能用 G0 的语言层/机器层区分法解释“源码变量不一定有独立栈槽”。

[上一章：G0](g00-native-toolchain.md) · [全系列导航](README.md) · [下一章：G2](g02-raii-and-ownership.md)

## 阅读入口

本章的问题是：**指针非空、地址可读，为什么还可能不能合法访问？**

首次按第 1～5 节阅读，完成两个实验，再做 Gate。第 6 节的跨语言对照只作回查，不要求先学 Zig 或 Rust。本章先建立合法访问模型；谁负责清理留给 G2，复制和移动的成本留给 G3。

- [1. 同一个地址，不等于同一个活对象](#g1-object)
- [2. 指针、引用与别名](#g1-access)
- [3. 数组、退化与借用](#g1-array)
- [4. 实验：对象可以先于存储结束](#g1-labs)
- [5. 表达式值类别](#g1-category)
- [6. 跨语言回查与检查工具](#g1-tools)
- [7. Final Gate](#g1-gate)

<a id="g1-object"></a>

<a id="g1-section-1"></a>

## 1. 同一个地址，不等于同一个活对象

### 1.1 问题与例子

[机制片段 · 不承诺独立编译]

```cpp
int a = 42;
int b = a;
```

值相同不代表对象相同。上例中两个独立的普通 int 对象有各自身份；修改 `b` 不改变 `a`。但若第二行改成 `int& b = a;`，`b` 就是另一个名字访问同一对象。

| 概念 | 用 `int a = 42;` 解释 | 常见混淆 |
| --- | --- | --- |
| 类型 type | int 规定可用操作与表示约束 | 类型不是地址 |
| 名称 name | a 是源码标识符 | 没有名字也可以有对象 |
| 对象 object | 本次初始化形成的 int 实体 | object 不只指 class 实例 |
| 值 value | 当前为 42 | 相等的值可属于不同对象 |
| 存储 storage | 对象表示占用的字节空间 | 字节仍在不证明对象存活 |
| 生命周期 lifetime | 对象存在的运行时区间 | 不等于名字可见的文本范围 |

这些概念需要区分，但并非互不相关的“六个正交公理”。类型、初始化和存储等一起决定对象语义；编译器仍可按 as-if 规则省去不影响可观察行为的物理操作。

### 1.2 生命周期与存储期

通常要有足够大小和正确对齐的存储，并完成相应初始化，生命周期才开始。对 class，析构调用**开始时**生命周期结束，构造/析构期间的访问另有专门规则。释放或复用存储也可能结束原对象的生命周期。精确边界见 [N4950：basic.life](https://timsong-cpp.github.io/cppwp/n4950/basic.life)。

存储期有 automatic、static、thread、dynamic 四类；作用域描述名字可见范围。静态存储并不意味着对象从程序第一条指令前到最后一条指令后都已完成初始化且可任意访问。

把资源操作拆成“取得存储 → 初始化 → 清理 → 归还存储”有助于推理，但**分配一定不创建对象**不是普遍规则：C++23 有 implicit-lifetime 对象的隐式创建机制。本章不尝试用四步图代替全部低层对象规则。

### 1.3 表示不是访问许可

`00 00 80 3F` 在常见小端、32 位 IEEE 754 float 表示下可对应 1.0；这不是所有平台的字节约定，更不允许把任意 `int*` 强转为 `float*` 后读取。需要位级转换时，检查类型与表示条件，使用合适的 `std::bit_cast` 等机制；“bits 看起来正确”不能绕过类型可访问性和生命周期要求。

<a id="g1-access"></a>

<a id="g1-section-2"></a>

## 2. 指针、引用与别名

[机制片段 · 不承诺独立编译]

```cpp
int x = 1;
int y = 2;
int* p = &x;
int& r = x;
r = y;       // 给 x 赋值；r 没有改绑到 y。
p = &y;      // p 这个指针对象改存另一指针值。
```

`p` 自己是对象，有地址 `&p` 和生命周期；`r` 是引用，不是独立的对象，`&r` 得到的是 `&x`。引用不提供“自动追踪存活”的能力，一样可能悬挂。

| 声明 | 可以重定向 p | 可以通过 p 修改目标 |
| --- | --- | --- |
| `T* p` | 是 | 是 |
| `T* const p` | 否 | 是 |
| `const T* p` | 是 | 否 |
| `const T* const p` | 否 | 否 |

`const T*` 限制这条访问路径，不证明其他别名不能修改同一对象。裸指针类型也不编码“由我 delete”还是“只是借用”；接口必须说明。

### 2.1 临时对象延寿不是传染性能力

[机制片段 · 不承诺独立编译]

```cpp
const std::string& text = std::string{"hello"};
```

这种直接绑定可延长临时对象的生命周期；把引用传过函数、再保存函数返回的引用，不会一概获得同样延寿。遇到引用返回值，必须追到真正的对象及其结束时间，而不是看到 `const&` 就判安全。

### 2.2 每次访问前问什么？

有有效存储吗？目标对象是否活着？类型访问、对齐、边界、可修改性是否满足？并发访问是否有必要的同步？这些是审查问题，不是编译器会替你验证的乘法公式。`p != nullptr` 只排除空指针值；若指针自身都未初始化，连读取它也不能拿来做安全证明。

<a id="g1-array"></a>

<a id="g1-section-3"></a>

## 3. 数组、退化与借用

`int values[4]{};` 是四个 int 子对象组成的数组对象，大小是 `4 * sizeof(int)`，不是由语言固定为 16 字节。

多数需要指针的表达式中，数组可转换为首元素指针；数组没有“变成指针对象”。`values + 1` 前进一个 int，`&values + 1` 前进整个数组。尾后指针可作区间终点，不能当作可读取的元素。

函数形参 `void f(int a[100])` 会调整为指针形参，不强制调用方提供 100 个元素。若要保留数组长度，使用合适的数组引用、模板或带长度的接口。

[机制片段 · 不承诺独立编译]

```cpp
// 接口片段：同步读取，不保存借用。
int sum(std::span<const int> values);
```

`std::span` 携带范围信息，不拥有元素，也不会阻止 vector 扩容或销毁。正确约束是：**每次使用借用访问元素时，目标元素必须存活，且期间没有使该访问路径失效的操作。**

不是“view 对象的生命周期必须小于 owner”的机械时间比较：一个已失效但不再被用于访问的 span 对象可以仍然存在；反过来，owner 还活着，扩容或 erase 也可能已经使借用失效。G4 再逐项解释失效规则。

<a id="g1-labs"></a>

<a id="g1-section-4"></a>

## 4. 实验：对象可以先于存储结束

### 4.1 G1-L1：reserve 没有构造元素

**预测：**reserve 后、emplace 后、clear 后，活对象数分别是多少？clear 后 capacity 会不会变为 0？

完整运行例：

<!-- g-lab {"id":"G1-L1","mode":"run","stdout":"live=0,1,0; capacity-preserved\n"} -->
[完整实验 · G1-L1 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <iostream>
#include <type_traits>
#include <vector>

struct Probe {
    static inline int live = 0;
    Probe() noexcept { ++live; }
    Probe(const Probe&) noexcept { ++live; }
    Probe(Probe&&) noexcept { ++live; }
    ~Probe() { --live; }
};

int main() {
    int values[4]{};
    static_assert(sizeof(values) == 4 * sizeof(int));
    static_assert(std::is_same_v<decltype(values), int[4]>);
    static_assert(std::is_same_v<decltype(&values), int (*)[4]>);
    int& alias = values[0];
    alias = 9;
    if (values[0] != 9 || &alias != &values[0]) return 1;

    std::vector<Probe> items;
    items.reserve(4);
    const auto capacity = items.capacity();
    if (items.size() != 0 || Probe::live != 0 || capacity < 4) return 2;
    items.emplace_back();
    if (items.size() != 1 || Probe::live != 1) return 3;
    items.clear();
    if (!items.empty() || Probe::live != 0 ||
        items.capacity() != capacity) return 4;
    std::cout << "live=0,1,0; capacity-preserved\n";
}
```

**原因：**capacity 表示可容纳元素的空间，size 表示现有元素数。reserve 不增加 size；clear 销毁元素但保留 capacity。由此可以看到“还有存储”和“还有元素”是两回事。

**改变条件：**把 `emplace_back()` 改成 `resize(3)`，先写出需要改变的判据；不要只改预期输出让测试变绿。此扩展没有包含在固定实验的结果中。

**边界：**实验只证明本例中的构造/析构与容量关系，不证明所有分配操作都不创建任何对象，也不验证自定义 allocator 或分配失败。

### 4.2 G1-L2：一个明确的错误读取

这是**必须被拒绝的 UB 反例**，不是建议写法。只在新建临时目录的独立进程中运行，并启用 AddressSanitizer。

<!-- g-lab {"id":"G1-L2","mode":"asan_negative","diagnostic":"AddressSanitizer: heap-use-after-free"} -->
[反例 · 未定义行为；仅限隔离检测 · G1-L2 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
int main() {
    int* p = new int{42};
    delete p;
    return *p; // 故意读取已释放对象，验证工具能否指出这个具体错误。
}
```

预期是 ASan 报告 `heap-use-after-free`。执行器先检查 ASan 的编译/正常运行能力，再要求反例出现这个诊断并以指定的 86 退出；普通编译失败、超时或任意崩溃都不计通过。测试配置关闭外部符号化，不校验源码行栈；诊断中的地址和栈偏移不固定。

**为什么不能用“退出码是 42”验收？**因为发生 UB 后语言不保证任何结果。ASan 提供的是本工具在本次执行中检测到错误的证据；未报告不代表没有 UB。[ASan 官方说明](https://clang.llvm.org/docs/AddressSanitizer.html)

### 4.3 手工存储复用只作进阶回查

[机制片段 · 不承诺独立编译]

```cpp
// 示意片段：需要 <cstddef>、<new> 以及实际 T 定义。
alignas(T) std::byte storage[sizeof(T)];
T* p = ::new (storage) T(/* arguments */);
p->~T(); // storage 仍在，不能再按原来的活 T 访问。
```

普通 `new T(...)` 把取得存储和初始化组合起来；`delete` 通常组合析构与释放。不要用手写 placement new 代替本来能由 value member、vector 或智能指针表达的所有权。

<a id="g1-category"></a>

<a id="g1-section-5"></a>

## 5. 表达式值类别：先看表达式，不给对象贴标签

| 基本类别 | 含义与常见例子 |
| --- | --- |
| lvalue | glvalue 中非 xvalue 的类别；普通表达式 `x`、`*p` |
| xvalue | 标识可被复用资源的对象；对象表达式 `std::move(x)` |
| prvalue | 初始化结果对象或计算操作数的值；`42`、返回 T 的普通调用 |

`glvalue = lvalue 或 xvalue`；`rvalue = prvalue 或 xvalue`。xvalue 同时在两组里，不要画成互不相交的两棵树。精确定义见 [N4950：basic.lval](https://timsong-cpp.github.io/cppwp/n4950/basic.lval)。

[机制片段 · 不承诺独立编译]

```cpp
void use(T&& r) {
    consume(r);            // 通常的这个参数表达式 r 是 lvalue。
    consume(std::move(r)); // 对象表达式转换成 xvalue，供重载决议使用。
}
```

这里 T 是已知对象类型，不是推导中的 forwarding reference。C++23 的 move-eligible return 等特定上下文另有隐式移动规则，不能把“具名就永远是 lvalue”当作无例外规则。

`std::move` 本身是转换，不执行资源搬运。后续可能选移动、复制或因没有可行重载而失败；const 对象通常不能绑定到普通 `T&&` 移动构造参数。一个对象可以仍在生命周期内、但已被移走资源；其可用操作由类型合同决定，不能等同悬挂，也不能保证“什么都能做”。G3 有完整对照实验。

返回 T、T&、对象类型 T&& 的函数调用分别通常得到 prvalue、lvalue、xvalue；这决定表达式类别，**不证明返回引用指向的对象活着**。

<a id="g1-tools"></a>

<a id="g1-section-6"></a>

## 6. 跨语言回查与检查工具

C++ 的 `std::span<T>`、Zig 的 `[]T` 与 Rust 的 `&[T]` 都可表达连续元素的借用，但检查机制不同。Rust 的普通引用受借用检查和安全接口约束；Rust 原始指针不是非空或自动安全引用。Zig `*T` 与可空 `?*T` 区分非空性，但不能据此消除悬挂。C++ 的裸指针同样不能证明生命周期。

以下为 **Zig 0.15.2 语法与清理顺序示意，未在本批编译**；T 的 init/deinit 是用户约定，不是语言级构造/析构：

```zig
const p = try allocator.create(T);
defer allocator.destroy(p); // 先登记，最后执行。
p.* = try T.init();
defer p.deinit();           // 后登记，先执行逻辑清理。
```

defer 按逆序执行，不能把 destroy 登记在 deinit 之后而让存储先释放。若 init 返回错误，上面只执行 destroy；若 init 自身取得多个资源，它还须自行处理部分失败。[Zig 0.15.2：defer](https://ziglang.org/documentation/0.15.2/#defer)

Zig 类型对照回查：`[N]T` 数组、`*[N]T` 数组指针、`[*]T` 未携带长度的多项指针、`[]T` 切片。Zig 不采用 C++ 的引用声明机制，但也不要从这个差异推出所有调用成本都能从语法直接读出。

建议的诊断起点：

```sh
clang++ -std=c++23 -O1 -g -Wall -Wextra -Wpedantic \
  -fsanitize=address,undefined -fno-omit-frame-pointer program.cpp -o program
```

Warnings、ASan、UBSan、测试和语言规则互相补充。UBSan 不是完整的 lifetime/aliasing 检查器；Sanitizer 不能证明未执行路径安全。并发问题还需适合的同步推理与工具。

<a id="g1-gate"></a>

<a id="g1-section-7"></a>

## 7. Final Gate

1. `int a = 1; int b = a; int& c = a;` 有几个 int 对象？修改谁会影响谁？
2. G1-L1 在 reserve 后、clear 后各说明了什么？可以用 `items[0]` 查看旧内容吗？
3. `p != nullptr` 能证明什么，不能证明什么？
4. `int a[4]` 与函数形参 `int a[100]` 中的长度含义一样吗？
5. vector 活着时，指向它的 span 为什么仍可能失效？
6. `T&& r` 的类型和表达式 `r` 的类别为什么不矛盾？move 是否保证转移？
7. 把 Zig 两个 defer 的登记顺序倒过来，会发生什么？
8. ASan 没有报告，能否关闭整个生命周期正确性问题？

<a id="g1-section-8"></a>

## 8. Final Gate · 参考答案与常见误判

1. 两个 int 对象；c 是 a 的引用。b 独立，c 写入 a。误判：把每个变量声明都数成一个独立对象。
2. reserve 不创建元素，clear 销毁元素但保留容量。size 为 0 时下标读取不合法。误判：capacity 是可读取的元素数。
3. 对已正确初始化的指针值，只排除空值；目标可能已释放、越界或不满足类型/同步条件。误判：加一次 if 就“修复悬挂”。
4. 实际数组有四个元素；普通数组形参调整为指针，100 不强制长度。误判：把形参写得长就获得边界检查。
5. 扩容、erase、clear 等可能让存储或元素身份失效。需要验证每次使用时的有效性，而不只是比较两个对象的寿命长短。
6. 类型描述声明，值类别描述表达式；普通具名参数表达式是 lvalue，转换后可参与不同重载决议。move 本身不搬运。误判：T&& 是“对象已经被移动”的状态。
7. 逆序执行会先释放存储，再通过 p 清理，顺序错误。误判：defer 按书写顺序执行。
8. 不能。只覆盖工具能检测且此次执行走到的行为。误判：把工具证据提升为全程序证明。

**完成标准：**能画出“owner → 存储/元素 ← 借用”的关系，指出何时失效；对每个实验先给预测，后解释结果。下一步用 G2 的类型设计把清理责任固定下来。
