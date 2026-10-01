# G5 调用表达式与类型推导

G4 留下了一次有意义的编译失败：vector 中的读数可以排序，在它上面建立的 filter_view 却不能直接交给 ranges::sort。元素依旧是 Reading，也仍然可以逐个读写，为什么一次看似只加了筛选条件的改变，会使调用不再成立？

本单元从这个调用进入模板实参推导（template argument deduction），追踪编译器怎样取得类型信息，以及包装函数怎样保留或改变调用方的选择。[第二单元](g05-constraints-and-instantiation.md)继续解释约束、重载与实例化，[第三单元](g05-constant-evaluation-and-codegen.md)讨论常量求值和实际生成的工件。完整实验使用 C++23，复现入口与证据边界见 [G5 验证说明](g05-verification.md)。G3 的[表达式类别](g03-expressions-and-return.md#6-现在再用表达式类别解释已经看到的选择)是本单元前提，这里不重新讲一遍移动构造。

## 1 先确定编译器正在判断哪一个调用

继续使用 G4 的读数表示。这个头文件在本批独立提取，Reading 定义与 G4 相同；它不是一个为模板实验另造的复杂类。

**完整实验共用文件 `reading.hpp`**

```cpp
#ifndef G5_READING_HPP
#define G5_READING_HPP

struct Reading {
    int id;
    int value;
    bool valid;
    bool operator==(const Reading&) const = default;
};

#endif
```

ranges::sort 的范围重载要求随机访问范围，并要求对应迭代器在比较器和投影下满足 sortable。随机访问解决定位方式，sortable 还涉及元素重排及间接比较。即使能用下标读取一个范围，如果它只暴露 const 元素，也不能因此原地排序。[范围排序的接口要求](https://timsong-cpp.github.io/cppwp/n4950/alg.sort#sort)

先把“能不能形成调用”放到一个依赖类型参数的 requires 表达式中。这里的 CanSortReadings 是命名的概念（concept），稍后再展开它的写法；现在只观察它对具体类型的回答。它不会运行排序，也不会检查每一组比较器行为。

**完整实验 `sort-capabilities.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <concepts>
#include <iostream>
#include <ranges>
#include <span>
#include <vector>

template<class R>
concept CanSortReadings = requires(R& rows) {
    std::ranges::sort(rows, {}, &Reading::id);
};

int main() {
    std::vector<Reading> rows{{103, 30, true}, {101, 10, true}};
    auto selected = rows | std::views::filter([](const Reading& r) {
        return r.valid;
    });
    static_assert(CanSortReadings<decltype(rows)>);
    static_assert(CanSortReadings<std::span<Reading>>);
    static_assert(!CanSortReadings<const std::vector<Reading>>);
    static_assert(std::ranges::bidirectional_range<decltype(selected)>);
    static_assert(!std::ranges::random_access_range<decltype(selected)>);
    static_assert(!CanSortReadings<decltype(selected)>);
    std::ranges::sort(rows, {}, &Reading::id);
    const Reading expected[] = {{101, 10, true}, {103, 30, true}};
    if (!std::ranges::equal(rows, expected)) return 1;
    std::cout << "sort requires traversal and writable ordering capabilities\n";
}
```

把本单元的文件放在同一目录，用下面的命令编译这个程序；其余正常程序分别替换文件名，各自生成可执行文件。

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic sort-capabilities.cpp -o sort-capabilities
./sort-capabilities
```

正常输出为 `sort requires traversal and writable ordering capabilities`。静态断言分别检验随机访问、可修改性与调用可行性，运行检查才确认实际排序得到完整的预期值。filter 的失败不是“编译器不知道怎样排序 Reading”，而是筛选后从一个有效元素跳到第 k 个有效元素不再具有该算法要求的随机访问合同。先物化到 vector 可以重新获得这个合同，但需要付出新结果存储与复制的代价。

面对这种诊断，适合按四个问题阅读：调用表达式是什么；模板参数从哪里取得；替换后的声明及其约束是否允许参与选择；需要定义时，所选特化的实现是否成立。这是理解诊断的顺序，不是声称编译器内部只有四趟流水线。重载集合里可能同时存在普通函数、多个模板和默认模板实参，返回类型推导也可能迫使函数体更早参与检查。

## 2 推导得到的 T 不等于最终形参类型

考虑一个只观察读数的函数。写成 `T value`，函数取得自己的参数对象；写成 `T& value`，函数建立别名。两者对同一个 const Reading 左值得到不同的 T，是因为形参模式提出了不同问题：前者需要知道复制出来的值是什么类型，后者必须保留引用绑定所需的限定。

下面的探针只声明函数，不提供定义。它们返回 `type_identity<T>`，把推导结果交给 static_assert；调用表达式位于 decltype 中，不会真的创建参数或调用函数。这样我们检验的是类型规则，不把复制次数、编译器私有类型名和推导混在一起。

**完整实验 `deduction.cpp`**

```cpp
#include "reading.hpp"
#include <concepts>
#include <iostream>
#include <type_traits>

template<class T> auto by_value(T) -> std::type_identity<T>;
template<class T> auto by_ref(T&) -> std::type_identity<T>;
template<class T> auto by_const_ref(const T&) -> std::type_identity<T>;

int main() {
    Reading row{101, 10, true};
    const Reading fixed = row;
    const Reading* const pointer = &fixed;
    Reading array[2] = {row, fixed};
    static_assert(std::same_as<decltype(by_value(fixed))::type, Reading>);
    static_assert(std::same_as<decltype(by_ref(fixed))::type, const Reading>);
    static_assert(std::same_as<decltype(by_const_ref(fixed))::type, Reading>);
    static_assert(std::same_as<decltype(by_value(pointer))::type, const Reading*>);
    static_assert(std::same_as<decltype(by_value(array))::type, Reading*>);
    static_assert(std::same_as<decltype(by_ref(array))::type, Reading[2]>);
    if (row != fixed) return 1;
    std::cout << "deduction preserves information according to the parameter pattern\n";
}
```

对 fixed，按值推导得到 Reading，普通引用推导得到 const Reading，而 const T& 又得到 Reading，因为形参模式已经写入 const。后两者最终形参都可成为 const Reading&，但不能因此认定其 T 相同。模板内部若再用 T 建立容器或作类型比较，这个差别就会显现。

pointer 则区分了两层 const：指针本身不能重新赋值，是顶层 const；它指向 const Reading，是所指类型的限定。按值推导丢掉前者，不能丢掉后者。数组也有对应的信息变化：非引用形参推导采用数组到指针的调整，数组长度不再进入 T；引用形参可以保留 Reading[2]。[调用推导中的类型调整](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call#2)

这些规则不保证参数初始化一定成功。若按值 T 最终对应不可复制的类型，左值调用仍可能在之后失败；写出 const T& 也不代表函数可以无限期保存这条借用。推导只决定类型与可行操作的一部分，G1/G2 的生命周期和责任分析仍然有效。

回到 `std::ranges::sort(rows, {}, &Reading::id)`：范围重载的 R&& 从 rows 这个左值取得 `R = std::vector<Reading>&`；第三个实参提供投影类型 `int Reading::*`；空花括号本身不为比较器类型提供推导信息，这里使用其默认模板实参 `std::ranges::less`。下一步再按这些实际类型检查范围能力与 sortable。换成 selected 后，R 变为对应 filter_view 的左值引用，引用绑定仍成立，但随机访问要求不成立。类型推导成功和约束满足由此成为可以分别定位的两件事。

### 2.1 推导不会替你选择一个共同数值类型

设一个简化函数要求两个实参使用同一个 T。调用方给出 int 和 double 时，不能因为 int 可以转成 double，就认为编译器会先统一成 double 再推导。

**编译负例 `deduction-conflict.cpp`：同一个模板参数得到冲突的推导结果。**

```cpp
template<class T>
T choose_value(T first, T second) {
    return first < second ? second : first;
}

int main() {
    return static_cast<int>(choose_value(10, 20.5));
}
```

用 `clang++ -std=c++23 -c deduction-conflict.cpp` 只编译、不链接，预期诊断应指向 choose_value 的 T 推导冲突。显式指定 `choose_value<double>` 会把问题改成已有形参类型下的转换；声明两个模板参数再计算结果类型则是另一种接口。前者是否容许精度变化、后者如何处理混合类型，都应由合同决定，不能把“让它编译”当作唯一目标。

### 2.2 从形参模式推导到具体声明

现在可以把这些观察收束为一个调用推导模型。模板参数是声明中尚待确定的参数，例如 T；模板实参是本次给它的具体类型、值或模板。推导负责从使用位置取得未确定的实参，替换（substitution）则把已取得的实参代入声明。两者不是同一个动作，也不是各自只发生一次。

对本节的普通函数模板调用，可以依次追问：

1. **比较什么？** 将参与推导的函数形参类型记为 P，对应实参表达式的类型记为 A；引用绑定还需要知道表达式类别。P 是模式，不是最终形参类型。
2. **先作哪些调整？** 根据 P 是否为引用，按调用推导规则调整比较所用的类型，再从允许推导的位置求出模板实参。多个位置推导同一个参数时，结果必须相容。
3. **哪些实参已确定？** 实参可能来自显式指定、推导或默认模板实参。显式实参会先参与替换；推导及默认值取得后还有相应替换，不能把全过程理解为单次“先推导、后替换”。
4. **代入后得到什么？** 把 T 等代入形参、返回类型等规定位置，形成具体声明，并继续检查约束、转换与绑定。声明可形成仍不意味着函数体或运行行为已成立。

这是回查信息来源的模型，不是独立的编译器阶段划分。特别是标准在推导过程中已经规定了部分约束与转换检查；下面讨论重载时再看它们如何影响候选。[模板实参的来源与替换时机](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.general)

前面的类型探针可以归入三类调整。这里“忽略限定”只针对推导，不会修改实参对象，也不解除访问限制。

| P 的形态 | 比较时对 A 的处理 | 当前案例的含义 |
| --- | --- | --- |
| 非引用，例如 T | 数组改用指针类型；函数改用函数指针类型；其余忽略顶层 cv | 数组长度不再进入 T；函数实参使按值 T 取得函数指针类型 |
| 引用，例如 T& 或 const T& | 使用 P 所引用的类型推导，不作上述数组／函数到指针调整 | 可以保留数组长度、函数类型及绑定所需限定 |
| 转发引用 T&& 与左值实参 | 另以 A 的左值引用类型参与推导 | T 本身可以成为引用，代入后须折叠 |

P 自身的顶层 cv 也按规则忽略；`const T&` 中的 const 修饰所引用类型，并非引用类型的顶层限定。因此 by_ref(fixed) 的 T 是 const Reading，而 by_const_ref(fixed) 的 T 是 Reading。对函数类型的调整与数组相似，但“推导使用函数指针类型”不等于已经执行一次函数调用。[P 与 A 的调整规则](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call#2)

**推导上下文与非推导上下文（deduced / non-deduced context）决定了哪些位置能提供信息。** 例如 `typename T::value_type` 中用于限定名字的 T 不从实参反向求出；许多不同类型都可能把同一个类型命名为 value_type。`std::type_identity_t<T>` 也可有意保留一个不参与推导的位置。若把 choose_value 的形参模式改为 `T, std::type_identity_t<T>`，就是让第一个参数确定 T，再检查第二个实参能否用于这个既定类型，而不是让两者竞争推导 T。这是声明形式的规则说明，不是本批新增的已执行实验。

非推导不表示不检查，也不表示模板永远不能调用：这个参数还可能由其他位置、显式模板实参或适用的默认值确定。反之，若没有任何合法来源能确定所需实参，调用推导就失败。本节不枚举全部非推导位置；关键是不能把模板声明当作任意可逆的类型方程。[非推导上下文](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct#type-5)

最后回到 choose_value：原来的两个 T 都参与推导，int 与 double 给出冲突结果；编译器不会任意尝试普通数值转换来替调用方选 T。调用推导确实另有受限的限定转换、指针及派生类匹配规则，因此准确结论是“推导不是一般转换搜索”，而不是“推导绝不考虑任何类型差异”。T 已确定以后，仍须按对应规则判断转换与绑定。[允许的匹配差异](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call#4)

## 3 转发引用记录调用方的绑定选择

现在给读数处理入口加一层包装。下游可能分别接受可修改借用、只读借用和允许接管的右值。包装层如果不想替调用方改变选择，就必须传递两项信息：对象的限定，以及调用方给的是左值还是右值。

在这里的函数模板调用推导中，`T&&` 的 T 是无 cv 限定、需要由本次调用推导的类型参数，因此它是转发引用（forwarding reference）。左值实参会使 T 推导为左值引用类型；把这个 T 代入 T&& 后，引用折叠（reference collapsing）得到左值引用。右值实参通常得到非引用 T，形参则是 T&&。这不是引用对象的嵌套，而是形成类型时的规则。[转发引用推导](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.call#3)与[引用折叠](https://timsong-cpp.github.io/cppwp/n4950/dcl.ref#6)

| 原实参 | 推导出的 T | 形参类型 | forward 后的表达式 |
| --- | --- | --- | --- |
| Reading 左值 | Reading& | Reading& | Reading 左值 |
| const Reading 左值 | const Reading& | const Reading& | const Reading 左值 |
| Reading 右值 | Reading | Reading&& | Reading xvalue |

参数有了名字以后，在普通函数调用表达式中直接写 value 仍是左值。`std::forward<T>(value)` 使用 T 中保存的信息：左值来源继续按左值传递，右值来源按 xvalue 传递。它不会把 prvalue 的原始求值过程重新创建出来，也不会自行复制或移动对象。

**完整实验 `forwarding.cpp`**

```cpp
#include "reading.hpp"
#include <concepts>
#include <iostream>
#include <type_traits>
#include <utility>

enum class Route { writable, readonly, consumable };
Route accept(Reading&) { return Route::writable; }
Route accept(const Reading&) { return Route::readonly; }
Route accept(Reading&&) { return Route::consumable; }

template<class T>
Route relay(T&& value) {
    static_assert(std::is_lvalue_reference_v<decltype((value))>);
    static_assert(std::same_as<decltype(std::forward<T>(value)), T&&>);
    return accept(std::forward<T>(value));
}

int main() {
    Reading row{101, 10, true};
    const Reading fixed{102, 20, true};
    if (relay(row) != Route::writable) return 1;
    if (relay(fixed) != Route::readonly) return 2;
    if (relay(std::move(row)) != Route::consumable) return 3;
    if (relay(Reading{103, 30, true}) != Route::consumable) return 4;
    if (relay(std::move(fixed)) != Route::readonly) return 5;
    if (row != Reading{101, 10, true}) return 6;
    std::cout << "forwarding preserves the caller binding choice\n";
}
```

预期输出为 `forwarding preserves the caller binding choice`。accept 只报告选中了哪个重载，没有消费对象，所以 std::move(row) 后 row 的值仍未改变。最后一次调用说明 forward 不删除 const：const 右值不能绑定到 Reading&&，这里仍会选择 const Reading&。

把 relay 中的 forward 改成 move，会擅自把非 const 左值也送往 consumable 重载；直接传 value，又会使右值来源失去右值路径。验证器对前一种错误生成独立变体，要求编译成功后由左值用例拒绝。这个测试观察重载选择，不把重载名称当成已经发生资源转移的证据。

这里用到的引用折叠可以独立记成下面四种组合。令 U 为非引用类型，表中的“再形成引用”发生在模板替换、类型别名等构造类型的过程中，不是允许在普通声明里直接书写“引用的引用”。

| T 所代表的类型 | 形成 T& | 形成 T&& |
| --- | --- | --- |
| U& | U& | U& |
| U&& | U& | U&& |

只有两层都为右值引用时结果才是右值引用；其余组合都是左值引用。U 的 const 等限定不被这张表删除。折叠也不依赖“完美转发”才存在：它是类型形成规则，转发引用的左值推导规则负责让 T 取得引用类型，forward 再利用这个结果构造表达式。三者分工不同。[引用折叠规则](https://timsong-cpp.github.io/cppwp/n4950/dcl.ref#6)

### 3.1 T 在哪里确定，比源码里有没有两个 & 更重要

类模板先确定 T 后，其普通成员函数的 T&& 不再由该次成员调用推导。以下负例与 relay 的差别就在这里。

**编译负例 `fixed-rvalue.cpp`：固定类模板实参所形成的右值引用不能接收左值。**

```cpp
#include "reading.hpp"

template<class T>
struct Holder {
    void set(T&&) {}
};

int main() {
    Holder<Reading> holder;
    Reading row{101, 10, true};
    holder.set(row);
}
```

负例只编译，预期指向右值引用无法绑定左值。`const T&&` 也不是上述转发引用形式。若确实需要成员模板接受独立推导的 U&&，可以另设 U，但这会扩大接口接受范围，仍须说明约束和持有方式。转发适合不拥有业务决策的包装层；G3 的按值取得、const 引用只读等具体接口，不需要为追求“通用”而全部改写。

完美转发这个惯用名称也有边界。例如单独的花括号初始化列表没有普通表达式的类型，未加专门形参模式的 T&& 不能从它随意推导出 T。引用绑定、重载集合和默认实参还有各自限制，本单元不把转发包装器承诺成原调用的无条件替代。

## 4 返回类型可以改变借用关系

包装层的最后一个选择在返回端。auto 返回类型通常按值推导；decltype(auto) 则使用返回表达式的 decltype 规则。因此同样写 `return rows.front();`，一个可以建立独立的 Reading 值，另一个可以返回原元素引用。后者不是少写几个字符的优化，而是给调用方增加了底层对象必须继续存在的条件。

**完整实验 `return-types.cpp`**

```cpp
#include "reading.hpp"
#include <concepts>
#include <iostream>
#include <vector>

template<class R>
auto first_copy(R& rows) {
    return rows.front();
}

template<class R>
decltype(auto) first_ref(R& rows) {
    return rows.front();
}

int main() {
    std::vector<Reading> rows{{101, 10, true}};
    const auto& readonly = rows;
    static_assert(std::same_as<decltype(first_copy(rows)), Reading>);
    static_assert(std::same_as<decltype(first_ref(rows)), Reading&>);
    static_assert(std::same_as<decltype(first_ref(readonly)), const Reading&>);
    auto copy = first_copy(rows);
    auto& borrowed = first_ref(rows);
    if (&borrowed != &rows.front() || &copy == &rows.front()) return 1;
    copy.value = 20;
    if (rows.front().value != 10) return 2;
    borrowed.value = 30;
    if (rows.front().value != 30 || copy.value != 20) return 3;
    std::cout << "return deduction chooses a value or a borrowed element\n";
}
```

输出为 `return deduction chooses a value or a borrowed element`。本例只对非空的左值容器调用，没有在持有 borrowed 时修改容器结构。R& 拒绝直接传入临时 vector，降低了一种误用机会，但不能保证调用方接下来不清空、扩容或销毁 rows。函数缺少约束及空范围处理是本节刻意保留的教学边界，不能直接充当任意范围的安全 first 接口。

也不要据此归纳“decltype(auto) 总是返回引用”。若返回的是未加括号的名字或成员访问，decltype 有专门规则；其他表达式又按表达式类别处理。即便得到的是正确引用类型，也可能引用已经结束生命的局部对象。接口审查应先决定返回独立值还是借用，再选择推导语法。[占位类型推导](https://timsong-cpp.github.io/cppwp/n4950/dcl.spec.auto)与[decltype](https://timsong-cpp.github.io/cppwp/n4950/dcl.type.decltype)

## 5 用变化后的条件检验模型

### 5.1 迁移问题

1. `vector<Reading>` 能排序，`const vector<Reading>` 也支持随机访问，为什么后者仍不能原地排序？
2. 把 `const Reading* const` 传给按值模板，哪一层 const 消失，哪一层必须保留？若换成 Reading 数组，T 还知道长度吗？
3. relay 用 T&& 接收左值后，T、最终形参类型和函数体内 value 表达式分别是什么？
4. 把 relay 的 forward 改为 move，为什么不是“同样帮助优化”？若传入 const 右值，能强迫选择 Reading&& 吗？
5. choose_value 的两个实参分别是 int 和 double，显式给出 T 与让编译器自由推导有什么不同？
6. first_ref 已经拒绝临时 vector，是否足以承诺返回引用在后续任意操作后都可用？改成 auto 返回解决了什么，又改变了什么？

### 5.2 推理与修正

**第一题。** 随机访问只说明遍历和定位能力，排序还要重排元素。const 元素路径不能提供相应写入能力。应查看排序整体约束，而不是只检查其中一个 concept；复制到可修改结果是另外一个操作合同。

**第二题。** 按值复制指针不需要保留指针对象的顶层 const，但仍只能指向 const Reading。按值模式对数组使用到指针的调整，T 不再保存长度；T& 可以推导出数组类型。两种选择同时影响复制方式和可用信息，不能笼统说“auto 或模板会丢 const”。

**第三题。** 非 const Reading 左值使 T 为 Reading&，代入 T&& 后折叠成 Reading&。具名参数在 accept(value) 这种普通调用里是左值表达式。T 所保存的来源信息要经过 forward 才参与下一层绑定。

**第四题。** move 由当前层主动开放右值路径，会把调用方原本传来的非 const 左值改送给允许消费的重载。它也不删除 const，所以 const 右值仍不能绑定到非 const Reading&&。是否移动必须继续看所选操作，不能从转换表达式直接推出。

**第五题。** 自由推导需要两个形参模式得到一致的 T，普通数值转换不会先替它解决冲突。显式给出 double 后，相关形参已知，再按转换规则处理实参；接口因此接受了精度与表示转换，需要另行判断这种选择是否符合任务。

**第六题。** 拒绝临时对象只挡住一条失效路径，容器后续的失效规则和生命结束仍可能使引用不可用。auto 返回建立值副本，调用方不再借用原元素，但修改结果也不再修改容器，并且需要相应值构造。下一单元会把接口实际接受什么，进一步写成可检查的约束。
