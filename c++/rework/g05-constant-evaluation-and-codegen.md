# G5 常量求值与生成代码

模板能依据类型选择实现，但并不是所有已知信息都该进入模板参数。一批读数的数目、处理阈值和输入范围类型分别在什么时候确定，会影响接口形式、生成代码和修改成本。本单元继续沿读数处理解释这些选择，再回到 G0 的目标文件，观察定义究竟由谁提供。

前置是[调用与推导](g05-call-and-deduction.md)及[约束与实例化](g05-constraints-and-instantiation.md)。这里的常量求值、运行检查和符号观察分开记录，不以优化器恰好消掉某个符号证明语言规则，也不测性能；复现入口见 [G5 验证说明](g05-verification.md)。

## 1 一套规则可以同时处理预设值与运行输入

假设有效读数还必须落在闭区间 [low, high] 内。部署时有一组写进程序的预设阈值，运行时则不断读入新测量值。希望编译器提前检查预设，不意味着运行数据也要变成模板实参，更不需要把同一个比较算法写两遍。

constexpr 函数允许合适的调用参与常量求值（constant evaluation）；是否必须在常量表达式语境成立，还要看调用位置与实参。constexpr 变量的初始化、static_assert 条件等会提出相应要求；普通运行时输入则仍可调用同一个 constexpr 函数。给函数加这个说明符，不是在源码中给每次调用盖上“没有运行成本”的章。[constexpr 的声明规则](https://timsong-cpp.github.io/cppwp/n4950/dcl.constexpr)

下面把参数校验与业务判断分开。checked_limits 是立即函数（immediate function），本章在普通调用位置使用它，要求相应调用满足常量表达式条件。accepts 则保留运行时可调用性。用 throw 拒绝非法预设是为了让该求值路径不能形成常量表达式，不是希望部署后捕获这次配置异常。

**完整实验共用文件 `reading-limits.hpp`**

```cpp
#ifndef G5_READING_LIMITS_HPP
#define G5_READING_LIMITS_HPP

#include "reading.hpp"
#include <array>
#include <cstddef>

struct Limits { int low; int high; };

constexpr bool valid_limits(Limits limits) {
    return 0 <= limits.low && limits.low < limits.high && limits.high <= 1000;
}

consteval Limits checked_limits(int low, int high) {
    Limits limits{low, high};
    if (!valid_limits(limits)) throw "invalid reading limits";
    return limits;
}

constexpr bool accepts(const Reading& row, Limits limits) {
    return row.valid && limits.low <= row.value && row.value <= limits.high;
}

template<std::size_t N>
constexpr std::array<bool, N> classify(const std::array<Reading, N>& rows,
                                       Limits limits) {
    std::array<bool, N> result{};
    for (std::size_t i = 0; i < N; ++i) result[i] = accepts(rows[i], limits);
    return result;
}

#endif
```

Limits 本身仍是普通值，可以来自运行时输入；constexpr 接受函数也不会自动检验 Limits 是否有效。若将来提供动态配置入口，必须主动调用 valid_limits 并按失败合同处理，不得把一个已经检查过的预设推广为所有 Limits 对象都合法。

**完整实验 `constant-evaluation.cpp`**

```cpp
#include "reading-limits.hpp"
#include <concepts>
#include <iostream>

int main(int argc, char**) {
    constexpr auto limits = checked_limits(10, 30);
    constexpr std::array<Reading, 3> sample{{
        {101, 10, true}, {102, 30, true}, {103, 20, false}
    }};
    constexpr auto mask = classify(sample, limits);
    static_assert(mask == std::array{true, true, false});
    static_assert(!accepts(Reading{104, 31, true}, limits));
    static_assert(!std::same_as<std::array<Reading, 2>, std::array<Reading, 3>>);
    const int runtime_value = argc + 9;
    Reading incoming{201, runtime_value, true};
    if (argc != 1 || !accepts(incoming, limits)) return 1;
    if (valid_limits(Limits{30, 10})) return 2;
    std::cout << "constant configuration and runtime readings share one rule\n";
}
```

沿用第一单元的单文件编译方式，不附加命令行参数运行，预期输出为 `constant configuration and runtime readings share one rule`。静态断言检查闭区间端点、无效标记与超出上界；运行部分用 argc 构成非常量表达式输入。const 修饰 runtime_value 只限制此对象之后的修改，不把来自 argc 的初始化变成常量表达式。有些以常量表达式初始化的 const 整数可以用于常量表达式，因此也不能把 const 简化为“永远只有运行时含义”。

即使语言允许运行时求值，优化器仍可能按可观察行为规则折叠、传播或内联代码。反过来，常量求值成立也不决定结果是否以一份数据出现在目标文件。本章没有通过计时或反汇编断言 accepts 实际执行了几条指令。[常量表达式条件](https://timsong-cpp.github.io/cppwp/n4950/expr.const)

### 1.1 区分非法预设与无法提前知道的实参

下面两个反例都应在编译期拒绝，但原因不同。第一个值完全已知，只是不满足 checked_limits 的业务检查；第二个值要等程序运行后才知道，不能用于这里的普通立即调用。

**编译负例 `invalid-limits.cpp`：已知预设走入抛异常的求值路径。**

```cpp
#include "reading-limits.hpp"

constexpr auto invalid = checked_limits(30, 10);
int main() { return invalid.low; }
```

**编译负例 `runtime-immediate.cpp`：普通立即调用依赖运行时实参。**

```cpp
#include "reading-limits.hpp"

int main(int argc, char**) {
    const auto limits = checked_limits(argc, 30);
    return limits.low;
}
```

分别用 `clang++ -std=c++23 -c 文件名.cpp` 编译，前者要同时定位 checked_limits 与 throw 路径，后者要定位 checked_limits 与 argc 不能参与相应常量表达式。只有出现一般“编译失败”不足以区分这两项命题。立即函数上下文还有进一步调用规则，本例不把“每个中间调用都必须独立在源码位置得出常量值”作为通用说法。

### 1.2 常量求值模型中的不同层次

上述案例同时出现了声明、表达式和求值要求。它们都与“提前知道”有关，却不能合并成一个叫“编译期”的属性。先确定正在讨论哪一层，才能判断一个运行输入是否允许进入。

| 概念 | 所属层次 | 应当回答的问题 |
| --- | --- | --- |
| constexpr | 声明说明符 | 函数是否具备参与常量求值的资格；变量是否满足相应初始化等要求 |
| consteval | 函数声明说明符 | 是否显式声明立即函数，并遵守相应调用限制 |
| 常量表达式（constant expression） | 语言对表达式及其求值的条件 | 求值路径和结果是否符合该语境要求 |
| 常量求值（constant evaluation） | 按常量表达式规则进行的求值 | 此次计算能否在这些规则内得到结果 |
| 常量初始化（constant initialization） | 静态／线程存储持续期的初始化分类 | 初始化是否满足规定条件，从而属于静态初始化 |
| if constexpr | 语句选择机制 | 对当前实例化丢弃哪一个子语句 |
| 模板实参（template argument） | 模板的参数绑定 | 哪个类型、值或模板确定当前特化 |

常量表达式不是“优化器能猜出结果”的简称。判断要沿实际求值路径进行：调用了什么函数、读取了什么对象、是否执行了禁止出现在该常量求值中的操作，以及结果是否满足限制。checked_limits(30, 10) 的输入完全已知，仍因执行 throw 而失败；accepts 则可以在合法常量输入与普通运行输入上分别使用。[常量表达式与声明要求](https://timsong-cpp.github.io/cppwp/n4950/expr.const)及[constexpr 与 consteval](https://timsong-cpp.github.io/cppwp/n4950/dcl.constexpr)

对本章 main 中的 checked_limits 调用，构成普通语境下的立即调用，必须满足相应常量表达式要求；constexpr 函数的普通运行时调用没有这个统一要求。C++23 对立即函数上下文及某些模板函数的立即性传播另有规则，所以不能把 consteval 解释成“任何嵌套调用都在自己的源码位置独立算完”，也不能把 constexpr 与 consteval 仅看成优化强度不同。

常量初始化关心另一件事。具有静态或线程存储持续期的变量或临时对象，满足 constant-initialized 条件时执行常量初始化；它与零初始化共同属于静态初始化，与动态初始化区分。这里的判据依赖初始化的完整表达式，并有构造函数等专门规则。它不要求变量一律声明为 constexpr，也不等于变量以后不可修改。[静态初始化的分类](https://timsong-cpp.github.io/cppwp/n4950/basic.start.static)与[constant-initialized 条件](https://timsong-cpp.github.io/cppwp/n4950/expr.const#2)

因此，main 内的自动 constexpr 变量虽然要求初始化满足常量表达式等条件，却不能据此充当“静态存储变量没有动态初始化”的实验；本章没有测试全局初始化顺序。同样，常量求值在语言规则内成立，不保证某段机器指令或某份数据一定消失。优化器常量折叠属于实现如何保留可观察行为的问题，不能让本来不满足常量表达式要求的调用变合法。

回看 mask：classify 的 constexpr 声明提供资格，sample 与 limits 提供本次可用输入，constexpr 变量初始化与 static_assert 提出所需检查，数组模板实参 N 则另行决定类型。后面 if constexpr 所决定的是实例化语句，不是把整个函数改为常量求值。把这些关系拆开后，就能指出究竟是哪一层条件失败，而不是只说“编译器没算出来”。

## 2 哪些信息值得成为类型的一部分

classify 的 N 由数组类型推导。N 是非类型模板参数（non-type template parameter），因此 `std::array<Reading, 2>` 与 `std::array<Reading, 3>` 是不同类型；固定长度进入了结果数组类型，也决定各自包含多少元素对象。它不代表一次 reserve 请求，更不能把长度为 N 的数组当作尚未构造 N 个元素的原始存储。

同一个 `classify<N>` 却能接收不同的 Limits。阈值没有改变返回类型、对象布局或所需操作，只影响计算结果，让它作为普通参数就足够。把每个阈值也写成模板参数，会让不同阈值组合对应更多特化，却未必改善任何可观察行为。是否需要这种变化，应先由类型与算法合同决定，再由测量判断收益。[非类型模板实参](https://timsong-cpp.github.io/cppwp/n4950/temp.arg.nontype)

运行时容器长度不能任意进入 std::array 的模板实参。对于一批不定长读数，G4 的 vector 或 span 更直接；对于少数固定通道数，可以在外层按运行配置选择已实现的固定 N，再在内层使用数组。这个动态选择本身不会消失，也不能用它向系统承诺任意输入 N 都有一个现成特化。

模板参数形成不同实体，与最终二进制是否保留多份机器代码仍是两回事。实现可以内联、删除不用的实体或做合并；布局还包括实现相关的对齐等条件。本节的 same_as 断言证明类型不同，不把 sizeof 数值或代码体积当作语言常量。

## 3 if constexpr 选择的是当前特化需要的操作

再看一个与常量数据不同的问题：统计范围元素个数。vector 可以直接询问大小，forward_list 不提供这样的成员。我们可以要求多遍范围，优先使用 sized_range 的 size，否则遍历计数。多遍要求使“数过一次之后还要再遍历”的接口意图明确；若允许单遍输入，就应另外说明这次统计可能消耗输入。

**完整实验 `count-elements.cpp`**

```cpp
#include "reading.hpp"
#include <cstddef>
#include <forward_list>
#include <iostream>
#include <ranges>
#include <vector>

template<std::ranges::forward_range R>
std::size_t count_elements(R&& rows) {
    if constexpr (std::ranges::sized_range<R>) {
        return static_cast<std::size_t>(std::ranges::size(rows));
    } else {
        std::size_t count = 0;
        for (auto it = std::ranges::begin(rows); it != std::ranges::end(rows); ++it)
            ++count;
        return count;
    }
}

int main() {
    std::vector<Reading> rows{{101, 10, true}, {102, 20, false}};
    std::forward_list<Reading> linked(rows.begin(), rows.end());
    static_assert(!std::ranges::sized_range<decltype(linked)>);
    if (count_elements(rows) != 2 || count_elements(linked) != 2) return 1;
    if (count_elements(std::forward_list<Reading>{}) != 0) return 2;
    std::cout << "each specialization instantiates its applicable counting branch\n";
}
```

输出为 `each specialization instantiates its applicable counting branch`。在模板实例化时，条件对当前 R 不再是值依赖的，未选中的语句不按该特化实例化。因此 forward_list 分支不必形成 ranges::size(rows) 调用。这与 constexpr 函数“能否在常量表达式中计算值”不是一个问题：本例函数不是 constexpr，仍可用 if constexpr 选择实现。[constexpr if 的实例化规则](https://timsong-cpp.github.io/cppwp/n4950/stmt.if)

更精确地说，if constexpr 的条件按上下文转换为 bool，转换后的表达式必须是常量表达式；在外围模板实体的实例化过程中，若实例化后的条件不再值依赖，丢弃的子语句不实例化。条件与模板依赖性共同决定这项豁免，而不是靠优化器判断某分支“看起来不会执行”。条件在这里静态确定，rows 的内容与遍历计数仍是运行时工作。

**编译负例 `ordinary-if.cpp`：普通 if 不提供模板分支丢弃。**

```cpp
#include <cstddef>
#include <forward_list>
#include <ranges>

template<class R>
std::size_t bad_count(R& rows) {
    if (std::ranges::sized_range<R>) {
        return static_cast<std::size_t>(std::ranges::size(rows));
    } else {
        return 0;
    }
}

int main() {
    std::forward_list<int> rows{1, 2};
    return static_cast<int>(bad_count(rows));
}
```

只编译，预期错误位于 size 调用。即使普通 if 条件最终为 false，类型检查也不能等待优化器删除分支之后再决定程序是否合法。另一方面，if constexpr 的源码仍须被解析；非依赖错误、非模板上下文中的错误，不会因为放进 false 分支就一概消失。这里也没有证明任意自定义 forward_range 的元素数都能装进 size_t，通用计数器仍需定义计数上界和溢出策略。

## 4 模板定义放在哪里决定谁能生成实现

现在回到 G0 的分离编译。声明足以让调用方知道一个具体函数应怎样调用，链接器再寻找定义。模板增加的问题是：谁持有足够信息，负责为一组模板实参形成所需定义？

前面的 sorted_snapshot 把定义放进头文件，允许调用方对不同输入类型实例化。另一种场景是库只支持一个固定集合，例如目前只接收 int 测量值，想把实现放在提供方翻译单元。可以公开模板声明，在提供方显式实例化（explicit instantiation）所支持的类型。下面沿用“统计一批值”的任务，故意保留开放声明，以观察不受支持的类型怎样暴露供应缺口。

**完整多文件实验 `positive-count.hpp`**

```cpp
#ifndef G5_POSITIVE_COUNT_HPP
#define G5_POSITIVE_COUNT_HPP

#include <cstddef>
#include <span>

template<class T>
std::size_t count_positive(std::span<const T> values);

extern template std::size_t count_positive<int>(std::span<const int>);

#endif
```

**完整多文件实验 `positive-count.cpp`**

```cpp
#include "positive-count.hpp"

template<class T>
std::size_t count_positive(std::span<const T> values) {
    std::size_t count = 0;
    for (const auto& value : values) if (value > T{}) ++count;
    return count;
}

template std::size_t count_positive<int>(std::span<const int>);
```

**完整多文件实验 `count-client.cpp`**

```cpp
#include "positive-count.hpp"
#include <array>
#include <iostream>

int main() {
    const std::array values{-1, 0, 5, 7};
    if (count_positive<int>(values) != 2) return 1;
    std::cout << "the provider supplies the requested int specialization\n";
}
```

按以下命令观察每个阶段，不把多个翻译单元编译一次的成功结果当作已经检查了中间工件。

```sh
clang++ -std=c++23 -O0 -Wall -Wextra -Wpedantic -c positive-count.cpp -o positive-count.o
clang++ -std=c++23 -O0 -Wall -Wextra -Wpedantic -c count-client.cpp -o count-client.o
nm -C positive-count.o
nm -C count-client.o
clang++ count-client.o positive-count.o -o count-client
./count-client
```

正常输出为 `the provider supplies the requested int specialization`。`extern template ...;` 是显式实例化声明（explicit instantiation declaration），在这里抑制客户端对所指定函数特化的隐式实例化；提供方中的 `template ...;` 则是显式实例化定义（explicit instantiation definition），明确要求从可见的模板定义实例化这里支持的 int 特化定义。声明本身不提供实现，也不会让链接器从无到有执行 C++ 模板推导。[显式实例化](https://timsong-cpp.github.io/cppwp/n4950/temp.explicit)

nm 用于观察本机目标文件中的定义与未解析引用。我们关心 `count_positive<int>` 如何由提供方供给，不固定其 ABI 拼写、地址、符号类型字母或总数。执行器同时保留 O0/O2 对象大小与摘要，数字属于工件观察，不是编译性能或运行速度结果。[LLVM nm 的观察范围](https://llvm.org/docs/CommandGuide/llvm-nm.html)

### 4.1 声明开放的范围可能大于实现供应的范围

以下客户端在自己的翻译单元中可以形成 float 调用，但提供方只生成了 int 定义。故障应在分别编译成功以后才观察，不能把先前任意编译错误算作验证了链接边界。

**链接负例 `count-missing.cpp`：没有提供 float 特化的定义，不执行运行。**

```cpp
#include "positive-count.hpp"
#include <array>

int main() {
    const std::array values{1.5F, -2.0F};
    return static_cast<int>(count_positive<float>(values));
}
```

先用相同编译参数生成 count-missing.o，再与 positive-count.o 链接，本机预期报告 `count_positive<float>` 未定义。缺定义违反程序要求；不同实现的诊断阶段和格式不作为跨平台承诺。这里记录的是所测工具链的链接行为，而不是把标准定义成“任何情况下必报相同 linker error”。

工程上不必长期保留这样的开放陷阱。如果只支持 int，普通的 `count_positive(std::span<const int>)` 可能更清楚；若支持一组固定类型，可以公开对应重载或约束，及早拒绝不支持的类型；若允许任意满足合同的类型，就通常需要让实例化位置可见定义。显式实例化不是同时获得无限泛型、隐藏全部实现和稳定 ABI 的免费组合。

### 4.2 从语言实体到目标文件

[上一单元](g05-constraints-and-instantiation.md#5-形成类模板特化不等于检查了每个成员函数体)已经区分特化与实例化。现在把这个语言模型接到工件上：count_positive 的模板给出一组实现规则，`count_positive<int>` 指定其中的函数特化，显式实例化定义要求从模板形成相应定义。这里的“特化”不只是一个待送往后端的中间名字，它本身就是语言层的函数实体；声明、定义和引用都需要围绕这个实体建立一致关系。

代码生成（code emission）是实现把所需行为和数据表达为中间表示、指令、符号及重定位等工件的过程。它与语言实例化没有一一对应关系；链接再处理各工件的定义、引用与保留范围，最终制品也不必保留实例化时看见的每一个函数边界。

| 层次 | 本案例的问题 | 不能据此等同的对象 |
| --- | --- | --- |
| 模板与特化 | 哪套规则，以及哪组模板实参所指定的实体？ | 模板名字不是一段已存在的机器代码 |
| 实例化与所需定义 | 谁具备定义，何时需要形成、检查它？ | 形成声明不等于已实例化函数体 |
| 目标文件生成 | 本次选项下留下什么定义、引用与重定位？ | 一个语言实体不保证对应一个可见符号 |
| 链接与最终机器代码 | 供应是否完整，哪些内容最终保留？ | 输入对象的符号数不等于最终函数或特化数量 |

实现可能内联调用、移除不需要的代码，也可能用 COMDAT 或 weak ODR 等机制处理允许重复提供的定义；具体机制依赖对象格式与工具链，并非每个平台都采用同一套。某些链接器还支持代码折叠，LTO 又可能跨翻译单元优化。它们都是“语言身份不等于最终代码份数”的实现例子，不是本批已经观察到这些机制全部发生，更不允许合并违反可观察语义的差异。[LLVM 的链接类别](https://llvm.org/docs/LangRef.html#linkage-types)与[COMDAT 表示](https://llvm.org/docs/LangRef.html#comdats)

所以 nm 中没有独立符号，不能直接推出对应模板从未实例化；多个对象里出现定义，也不直接推出最终有同样多份代码。反方向同样重要：本实验 float 定义确实缺失，不能拿“优化器也许会处理”替代所需实现。这里把声明检查、独立编译、符号观察和链接结果联合起来，才说明这次供应关系；G6/G9 后续若研究成本，还须另取测量证据。

## 5 让泛型停在能解释收益的位置

这一章里，Reading 没有成为模板；sorted_snapshot 的输入形态成为模板；固定数组的 N 进入类型；Limits 的值大部分保持普通数据。这样的分配不是风格偏好，而是由每项变化影响什么来决定：影响合法操作与类型的变化需要静态表达，只改变一次计算结果的变化可以保留为运行参数。

头文件定义增加调用方的解析与实例化工作，也使实现变化进入更大的重建范围；具体核心函数可以缩小这种传播，但可能失去某些跨层优化机会。这些是需要测量的取舍，不能仅从模板数量判断编译时间或二进制大小。完整构建依赖留给 G9，ABI 留给 G8；这里用多文件实验确保读者能说明谁需要声明、谁需要定义、谁最终提供符号。

G5 到这里建立的是从调用到实体的模型，不是承诺“编译期抽象自然零成本”。G6 将在已经合法且语义明确的实现上研究布局、访问和分配代价；不再用一个 constexpr 或 noexcept 标签替代测量。本批不进入新的性能实验，也不展开特化技巧大全、模板元编程库、反射或跨语言重写。

## 6 用变化后的条件检验模型

### 6.1 迁移问题

1. accepts 声明为 constexpr，为什么仍可处理 argc 派生的数据？const runtime_value 又为什么不够？
2. checked_limits(30, 10) 与 checked_limits(argc, 30) 分别在哪个条件上失败？它们都能当作运行时异常处理吗？
3. classify 的 N 进入类型，但 low/high 保持普通值。若每个阈值都变成模板参数，会改变哪些工程条件，能否直接断言更快？
4. 把 count_elements 的 if constexpr 改成普通 if，为什么“反正分支不会执行”仍不能消除编译错误？
5. 头文件只有 extern template，提供方没有显式实例化定义，能否靠客户端的声明完成链接？为什么 float 客户端先编译成功？
6. nm 中的符号数能否等同模板特化数？要决定是否改成具体核心函数，还缺什么证据？

### 6.2 推理与修正

**第一题。** constexpr 提供在合适调用中常量求值的能力，普通运行数据仍可按运行时语义进入函数。argc 不是相应常量表达式来源，给派生对象加 const 不能追溯改变初始化。优化器可能消除某些实际计算，与语言是否要求常量求值分别判断。

**第二题。** 前者的实参已知，但校验使求值进入 throw，不能形成所需常量表达式；后者的普通立即调用依赖运行输入。本例两者都在编译阶段被拒绝，不会生成一个待 catch 的运行事件。动态配置应走普通函数校验，并另设运行时失败通道。

**第三题。** N 决定数组类型和元素数量；阈值在这里不改变操作集合。把阈值静态化会增加实参组合与特化身份，并限制调用时可用的数据来源。是否减少指令、增加代码体积或延长构建都须测量，不能从模板语法直接推导。

**第四题。** 普通 if 不丢弃模板语句的实例化需求，非法的 size 调用必须先通过语义检查，不能等待后续优化删除。if constexpr 在这里允许对具体 R 不实例化另一分支，但不免除解析、非依赖检查和已选中分支的正确性要求。

**第五题。** extern template 不是定义，所需实现仍须在程序中提供。float 的声明足以形成调用与未解析引用，却没有对应的供应定义；本机在链接时报错。支持集合应体现在公开接口或可见定义中，不能只靠发布说明提醒用户哪些模板实参碰巧能链接。

**第六题。** 编译器和链接器可内联、删除或合并实体，符号表只反映特定参数下的工件。还需要有代表性的构建时间、对象及最终制品大小、实际访问工作负载和 profile；本批没有测这些。应先保持接口语义，再以 G6/G9 的证据决定是否调整静态与动态边界。
