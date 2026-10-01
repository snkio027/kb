# G3 参数、返回值与表达式类别

[上一单元](g03-value-copy-and-move.md)让 Batch 的复制和移动具有明确后置条件。现在把它放进校准流程：函数接收一个批次，替换第一项读数，再把结果交回调用方。调用方有时需要保留原值，有时愿意交出原存储。函数应该借用、复制，还是接管？返回一个大对象又是否必然很贵？

这些问题不能只看函数签名里有没有 `&` 或 `&&`。还要看参数怎样初始化、函数体怎样使用有名字的参数、结果对象怎样建立。本单元沿同一个 Batch 跟踪这些步骤，再回头整理值类别的术语。正文文件复用上一单元的两个头文件；独立定义的观察类型只用于各自实验，不替换前一单元实现。执行证据见[验证说明](g03-verification.md)。

## 1 按值接收让函数拥有一份可以修改的参数

假设校准结果无论如何都要保存为一个独立值。接收 `const Batch&` 后在函数内部复制可以做到，但调用方即使已经不需要原批次，也不能直接把存储交给这份参数。按值接收则允许参数从一个仍需保留的对象复制构造，也允许从一个可以交出的对象移动构造。函数体获得自己的 Batch 对象，可以统一处理。

下面的 `calibrated` 只把第一项设为 99，没有引入通用数值运算的溢出问题。`return input` 仍然按值返回，不返回参数引用。`inspect` 则故意接收右值引用但只读长度，用来观察“绑定引用”和“实际取走值”的区别。

**文件 `parameter-value.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <utility>

Batch calibrated(Batch input) {
    if (input.size() != 0) input.values()[0] = 99;
    return input;
}

std::size_t inspect(Batch&& input) noexcept { return input.size(); }

int main() {
    const int original[] = {10, 20, 30};
    const int changed[] = {99, 20, 30};
    Batch source(7, original);
    auto address = source.values().data();
    auto allocations = BatchStorage::allocations;
    Batch result = calibrated(source);
    if (!has_value(result, 7, changed) || !has_value(source, 7, original))
        return 1;
    if (result.values().data() == address ||
        BatchStorage::allocations != allocations + 1) return 2;

    allocations = BatchStorage::allocations;
    if (inspect(std::move(source)) != 3 || !has_value(source, 7, original) ||
        source.values().data() != address) return 3;
    Batch transferred = calibrated(std::move(source));
    if (!has_value(transferred, 7, changed) ||
        transferred.values().data() != address ||
        BatchStorage::allocations != allocations) return 4;
    if (!has_value(source, 0, {}) || source.values().data()) return 5;
    std::cout << "value parameter copies or takes storage; reference alone does not\n";
}
```

用上一单元的 C++23 编译选项构建 `parameter-value.cpp`，正常输出为 `value parameter copies or takes storage; reference alone does not`。第一次调用为参数复制数组，结果与 source 独立；第二次先经过只绑定引用的 inspect，source 没变，随后校准调用的参数才真正移动它。

`return input` 中的参数不满足命名返回值优化的对象条件，但在 C++23 的这个返回上下文中符合隐式移动条件，因而可以调用 Batch 的移动构造来建立结果。调用方的 `result` 从函数产生的同类型结果初始化，也不要求再复制一份数组。后面会拆开这两条规则，不能把“数组只分配一次”解释成“没有任何对象构造”。

按值接口适合确实要形成拥有值的路径，不是所有输入参数的默认最优解。一个只检查批次号的函数用 `const&` 就够；一个常常在第一步拒绝输入的接口，按值参数可能已经付出复制成本，或已经取走调用方存储。还可以设计“先借用验证，再明确接管”的协议，但它的失败和同步边界必须另行说明。不要只依据参数对象的大小选择接口。

## 2 std::move 改变的是表达式，不是源对象本身

`std::move(source)` 提供一种表达式形式，使重载可以选择允许接手的操作。它自身不分配、不关闭、不复制数组，也不会把 source 标记成不能再使用。返回的引用仍涉及同一个源对象；直到某个构造、赋值或函数实现真正采用它，对象状态才可能改变。[move 的返回规则](https://timsong-cpp.github.io/cppwp/n4950/utility#forward)

有名字的右值引用变量也是一个重要关口：在普通表达式里直接写它的名字，得到的是左值。否则每次提到参数都可能悄悄允许资源被取走，函数体将很难连续使用同一个参数。若确实要把它继续交出，应在那个位置明确使用 `std::move`；返回语句的隐式移动是另外规定的特殊上下文，不能把规则混在一起。

**文件 `move-selection.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <type_traits>
#include <utility>

struct CopyOnly {
    static inline int copies = 0;
    CopyOnly() = default;
    CopyOnly(const CopyOnly&) noexcept { ++copies; }
};

int main() {
    const int input[] = {10, 20, 30};
    Batch source(7, input);
    auto allocations = BatchStorage::allocations;
    auto address = source.values().data();
    auto&& path = std::move(source);
    if (&path != &source || !has_value(source, 7, input) ||
        BatchStorage::allocations != allocations) return 1;
    Batch copied(path);
    if (!has_value(copied, 7, input) || !has_value(source, 7, input) ||
        copied.values().data() == address) return 2;
    Batch consumed(std::move(path));
    if (!has_value(consumed, 7, input) || consumed.values().data() != address ||
        !has_value(source, 0, {})) return 3;

    const Batch frozen(8, input);
    Batch from_const(std::move(frozen));
    if (!has_value(from_const, 8, input) || !has_value(frozen, 8, input) ||
        from_const.values().data() == frozen.values().data()) return 4;
    static_assert(std::is_move_constructible_v<CopyOnly>);
    static_assert(std::is_nothrow_move_constructible_v<CopyOnly>);
    CopyOnly first;
    CopyOnly second(std::move(first));
    (void)second;
    if (CopyOnly::copies != 1) return 5;
    std::cout << "cast does not transfer; named reference and const can copy\n";
}
```

预期输出为 `cast does not transfer; named reference and const can copy`。`path` 绑定以后 source 没变；以名字 path 构造 copied 时选择复制；再次显式转换以后，consumed 才取得数组。对 const Batch 做 move 不会去掉 const，不能绑定到要求可修改源的 `Batch&&`，于是本例选择可接受该输入的 `const Batch&` 复制构造。

CopyOnly 没有移动构造，但仍可以从右值初始化，因为 const 左值引用也能绑定这种输入。两个 trait 在这里都为真，计数器却明确记录一次复制。因此“可从右值构造”与“有资源转移实现”不是同一命题；trait 也不审查用户定义的复制是否满足值语义。[类型性质查询](https://timsong-cpp.github.io/cppwp/n4950/meta.unary.prop)

再只改变一个条件：不是省略移动构造，而是显式删除它。下面是**预期编译失败的完整负例，不运行**。

**文件 `deleted-move.cpp`**

```cpp
#include <utility>

struct Copyable {
    Copyable() = default;
    Copyable(const Copyable&) = default;
    Copyable(Copyable&&) = delete;
};

int main() {
    Copyable source;
    Copyable target(std::move(source));
    (void)target;
}
```

编译器应诊断选择了已删除的 Copyable 构造函数，不能因为复制存在就退回复制。显式删除的候选仍参与重载决议；它匹配得更好，却不能被调用。这里还要与默认移动构造函数被定义为删除的特殊规则区别：后者会被重载决议忽略。不要将 `= delete`、`= default` 后不可用和完全未声明三种状态混称为“没有 move”。

负例只运行编译阶段，不进入链接或执行：

```sh
clang++ -std=c++23 -Wall -Wextra -Wpedantic -c deleted-move.cpp
```

## 3 返回一个结果不必先制造一个可移动的临时对象

先看最直接的工厂：`return PinnedBatch(7, input)`。返回类型就是 PinnedBatch，返回表达式是同类型的纯右值。从 C++17 起，这种初始化按目标结果对象直接完成，不需要先构造一个独立临时对象，再调用移动把它送出去。这不是恰好开启优化才成立的假设。

下面故意删除复制和移动。如果按值返回必然依赖它们，程序就不可能成立。`value` 成员仍采用上一单元的 Batch，只让外层类型不能被复制或移动，隔离出结果对象的初始化规则。

**文件 `pinned-batch.hpp`**

```cpp
#ifndef G3_PINNED_BATCH_HPP
#define G3_PINNED_BATCH_HPP
#include "value-batch.hpp"
#include <span>

struct PinnedBatch {
    Batch value;
    PinnedBatch(int sequence, std::span<const int> values)
        : value(sequence, values) {}
    PinnedBatch(const PinnedBatch&) = delete;
    PinnedBatch(PinnedBatch&&) = delete;
    ~PinnedBatch() = default;
};
#endif
```

**文件 `direct-result.cpp`**

```cpp
#include "pinned-batch.hpp"
#include <iostream>

PinnedBatch make_batch() {
    const int input[] = {10, 20, 30};
    return PinnedBatch(7, input);
}

int main() {
    auto allocations = BatchStorage::allocations;
    PinnedBatch result = make_batch();
    const int expected[] = {10, 20, 30};
    if (!has_value(result.value, 7, expected) ||
        BatchStorage::allocations != allocations + 1) return 1;
    std::cout << "same-type prvalue constructs result without copy or move\n";
}
```

正常输出为 `same-type prvalue constructs result without copy or move`。这里在工厂返回以前已经复制了局部整数数组，结果不借用 input。直接构造免掉的是 Batch 外层对象之间不必要的交接，不会免掉存储创建、读数处理等真正工作。析构函数仍必须可访问且未删除，返回规则不允许借“不需要移动”绕过对象的其他语义要求。[同类型纯右值初始化](https://timsong-cpp.github.io/cppwp/n4950/dcl.init#16.6.1)、[返回对象与析构](https://timsong-cpp.github.io/cppwp/n4950/stmt.return)

这条结论限于这里的同类型完整结果对象情形，不能扩成任意基类子对象、任意转换或对一个已存在对象的赋值。例如 `existing = make_batch()` 仍要找到可用赋值操作，不能把 existing 当成一个尚未初始化的结果变量。

## 4 命名局部对象的返回多了一项实现选择

把工厂改成先声明 `PinnedBatch local(7, input)`，再 `return local`，读起来几乎一样，却触及另一条规则。命名返回值优化（named return value optimization，NRVO）允许实现把符合条件的局部对象直接建立在结果位置；它不是所有实现、所有控制流都必须采用的行为。程序不能依赖这个选择来绕过不可用的构造操作。

以下是第二个**预期编译失败的完整负例，不运行**。

**文件 `named-result-invalid.cpp`**

```cpp
#include "pinned-batch.hpp"

PinnedBatch make_named() {
    const int input[] = {10, 20, 30};
    PinnedBatch local(7, input);
    return local;
}

int main() { auto result = make_named(); (void)result; }
```

本例即使在会实施 NRVO 的编译器上也应被拒绝：返回时选中的 PinnedBatch 移动构造已删除。上一节的工厂没有这个要求，因为它不先产生一个独立命名的 PinnedBatch。不要只用“RVO”这个统称解释两者，更不要把一次没打印 move 日志当成程序不需要可用移动的证明。[允许省略复制或移动的条件](https://timsong-cpp.github.io/cppwp/n4950/class.copy.elision)

沿用上一负例的命令，把文件名替换为 `named-result-invalid.cpp`；预期诊断对象改为 PinnedBatch。缺头文件、链接失败或任意编译错误都不能算作这项命题通过。

对可移动的 Batch，在 C++23 规定的返回上下文中，符合条件的局部名或参数名会作为将亡值参与初始化，这通常称为隐式移动（implicit move）。因此一般直接写 `return local;`，不必为“确保移动”加 `std::move(local)`。后者改变返回表达式的形式，失去这里的 NRVO 资格。C++23 将 move-eligible 表达式视为将亡值的规则，也不应与较早标准版本的重载处理步骤混写。[C++23 隐式移动的上下文](https://timsong-cpp.github.io/cppwp/n4950/expr.prim.id.unqual#4)

## 5 用构造观察区分规则，不用日志猜性能

下面用 TraceBatch 包装同一份值，并在复制与移动构造中计数。三个工厂分别直接返回纯右值、返回命名局部对象，以及故意在返回局部对象时加 move。计数器只用于这个实验，不是生产 Batch 的一部分。即使构造函数存在这些可观察副作用，标准允许的复制省略仍可能省去相应调用。

**文件 `return-observation.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <span>
#include <utility>

struct TraceBatch {
    static inline int copies = 0;
    static inline int moves = 0;
    Batch value;
    TraceBatch(int sequence, std::span<const int> values) : value(sequence, values) {}
    TraceBatch(const TraceBatch& other) : value(other.value) { ++copies; }
    TraceBatch(TraceBatch&& other) noexcept : value(std::move(other.value)) { ++moves; }
};

TraceBatch direct(std::span<const int> values) { return TraceBatch(7, values); }
TraceBatch named(std::span<const int> values) {
    TraceBatch local(7, values);
    return local;
}
TraceBatch forced(std::span<const int> values) {
    TraceBatch local(7, values);
    return std::move(local); // Deliberate pessimization for comparison.
}

int main() {
    const int input[] = {10, 20, 30};
    auto a = direct(input);
    if (!has_value(a.value, 7, input) || TraceBatch::copies || TraceBatch::moves)
        return 1;
    auto b = named(input);
    const int named_moves = TraceBatch::moves;
    if (!has_value(b.value, 7, input) || TraceBatch::copies ||
        (named_moves != 0 && named_moves != 1)) return 2;
#ifdef EXPECT_NO_ELISION
    if (named_moves != 1) return 3;
#endif
    TraceBatch::copies = TraceBatch::moves = 0;
    auto c = forced(input);
    if (!has_value(c.value, 7, input) || TraceBatch::copies || TraceBatch::moves != 1)
        return 4;
    std::cout << "direct_moves=0; named_moves=" << named_moves << "; forced_moves=1\n";
}
```

普通构建允许 `named_moves` 为 0 或 1，不固定优化开关必然对应哪个数；其他两项分别要求 0 与 1，并检查所有结果的完整值。`forced` 可能得到编译器关于阻碍复制省略的警告，这是对照代码故意暴露的问题，不推荐用于普通返回路径。完整 stderr 保存在验证记录。

在 Clang 中还可以作以下定向观察：

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic -fno-elide-constructors \
  -DEXPECT_NO_ELISION return-observation.cpp -o return-observation
./return-observation
clang++ -std=c++23 -O0 -fno-elide-constructors direct-result.cpp -o direct-result
./direct-result
```

第一条运行预期得到 `direct_moves=0; named_moves=1; forced_moves=1`；第二个程序仍应编译并得到上一节的正常结果。这个工具选项禁用可选的复制/移动省略，不能撤销语言要求的同类型纯右值初始化语义。[Clang 选项入口](https://clang.llvm.org/docs/ClangCommandLineReference.html#cmdoption-clang-felide-constructors)是工具资料，不是跨编译器选项合同。

实验没有计时、profile 或生成汇编审阅。一次构造调用可能只处理几个成员，也可能复制大量数据；返回值优化减少调用，不直接给出应用耗时。应先确保结果合同，再在 G6 的测量框架中研究实际热点，不能由这几个数字推出“按值总比引用快”。

## 6 现在再用表达式类别解释已经看到的选择

值类别（value category）描述表达式，不是给一个对象贴上永久标签。相同的 Batch 对象，通过名字 source 表达时通常是左值，通过 `std::move(source)` 表达时是将亡值；这两个表达式没有因此指向两个不同对象。声明类型为 `Batch&&` 的变量，在普通表达式中被名字引用时仍是左值。

左值（lvalue）和将亡值（xvalue）都属于泛左值（glvalue）；泛左值用于确定对象或函数的身份。将亡值进一步表示一个对象或位域，其资源可以在相应语境中被复用。纯右值（prvalue）用于初始化对象或计算操作数的值，将亡值与纯右值合称右值（rvalue）。这些分类不等于“在赋值号左边或右边”，也不等于“有没有名字”或“是不是马上析构”。[表达式分类](https://timsong-cpp.github.io/cppwp/n4950/basic.lval)

| 本章表达式 | 类别 | 在这里的意义 |
| --- | --- | --- |
| `source` | 左值 | 命名一个仍可能继续使用的 Batch |
| `path`，即使声明为 `Batch&&` | 左值 | 引用变量的名字不自动再次交出目标 |
| `std::move(source)` | 将亡值 | 同一个对象以允许相应右值重载的方式出现 |
| `std::move(frozen)` | const Batch 的将亡值 | const 没有被去掉，不能绑定普通 `Batch&&` |
| `Batch(7, input)` | 纯右值 | 可直接初始化 Batch 结果对象 |

这张表只描述普通求值上下文，命名变量在 C++23 返回语句中符合隐式移动条件时另按前面规则判断。要选中实际操作，还必须结合 cv 限定、可用重载、约束及上下文；将亡值本身并不保证发生资源转移。

下面用 `decltype` 与几个非模板重载检查模型。未加括号的变量名在 decltype 中有特殊规则，直接给出声明类型；加括号以后按表达式类别得到 `T&`、`T&&` 或 T。它是观察工具，不应根据某次编译器报出的类型字符串反推所有语言规则。[decltype 的规则](https://timsong-cpp.github.io/cppwp/n4950/dcl.type.decltype)

**文件 `expression-model.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <type_traits>
#include <utility>

int route(Batch&) { return 1; }
int route(const Batch&) { return 2; }
int route(Batch&&) { return 3; }

struct Risky {
    Risky(const Risky&) = default;
    Risky(Risky&&) noexcept(false);
};
struct MoveOnlyRisky {
    MoveOnlyRisky(const MoveOnlyRisky&) = delete;
    MoveOnlyRisky(MoveOnlyRisky&&) noexcept(false);
};

int main() {
    Batch source;
    const Batch frozen;
    Batch&& path = std::move(source);
    static_assert(std::is_same_v<decltype(source), Batch>);
    static_assert(std::is_same_v<decltype((source)), Batch&>);
    static_assert(std::is_same_v<decltype(path), Batch&&>);
    static_assert(std::is_same_v<decltype((path)), Batch&>);
    static_assert(std::is_same_v<decltype(std::move(source)), Batch&&>);
    static_assert(std::is_same_v<decltype(std::move(frozen)), const Batch&&>);
    static_assert(std::is_same_v<decltype(Batch{}), Batch>);
    static_assert(std::is_same_v<decltype(std::move_if_noexcept(source)), Batch&&>);
    static_assert(std::is_same_v<
        decltype(std::move_if_noexcept(std::declval<Risky&>())), const Risky&>);
    static_assert(std::is_same_v<
        decltype(std::move_if_noexcept(std::declval<MoveOnlyRisky&>())), MoveOnlyRisky&&>);
    if (route(source) != 1 || route(path) != 1 || route(std::move(source)) != 3 ||
        route(std::move(frozen)) != 2 || route(Batch{}) != 3) return 1;
    auto&& selected = std::move_if_noexcept(source);
    if (&selected != &source) return 2;
    std::cout << "expression category selects references; traits do not prove semantics\n";
}
```

正常输出为 `expression category selects references; traits do not prove semantics`。这些 route 函数不创建新的 Batch，也不移动它们；调用只观察引用参数重载。Risky 的操作只有声明，出现在不求值的类型查询中，不声称其运行实现已验证。`declval` 同样只用于不求值上下文。

`move_if_noexcept` 在移动构造可能抛且可以复制时返回 const 左值引用，否则返回右值引用；它本身不进行任何一次复制或移动。因此 MoveOnlyRisky 即使移动可能抛，也没有自动获得一条复制后备路径。本例检查返回类型，不把它说成已经验证了 vector 的全部迁移策略。[工具函数的返回类型](https://timsong-cpp.github.io/cppwp/n4950/utility#forward)

上表的纯右值也不等于“没有对象”。例如把一个临时 Batch 绑定到引用时，会通过临时量实质化产生相应临时对象，再让引用绑定它；直接初始化同类型完整结果对象则可以使用目标本身。两者应按上下文区分。[临时量实质化](https://timsong-cpp.github.io/cppwp/n4950/conv.rval)与 G1 的生命延长规则共同约束后续访问，值类别不负责延长任意借用。

## 7 接口返回的是值还是一条仍需别人维持的路径

返回 `Batch` 可以把结果生命交给调用方，但返回 `span<const int>` 仍只是范围借用。即使 span 很小、按值返回、完全没有复制元素，它指向的读数也必须另有 owner。如果函数把局部 Batch 的 `values()` 返回出去，返回对象 span 本身可以活得很好，被借用的数组却已销毁。复制一个视图不能把它变成快照。

同理，返回局部 Batch 的引用是生命错误；给返回表达式加 `std::move` 不会让引用变成拥有值，也不会让局部对象活过函数。`auto` 与 `decltype(auto)` 的返回类型推导还会影响到底返回对象还是引用，后者不是通用的“零拷贝开关”。本章有意使用明确返回类型；完整推导和转发规则由 G5 展开，不靠省略返回类型掩盖合同。

值返回解决了对象层面的拥有与初始化，依旧不保证整个数据图独立。若 Batch 以后加入外部指针、共享字典或回调，就要重新确认复制出的对象是否仍依赖原环境。这也是前一个单元先定义逻辑值，再谈特殊成员的原因。

在工程决策上，应分别估计三件事：是否需要一份独立值；取得它要复制哪些数据、申请哪些存储；后续借用会因哪些操作失效。能省略一次外层移动，不会替代这三项判断。[旧 G3](../g03-value-semantics-and-performance.md) 的 SSO、容器迁移、池租约与成本图仍可回查，详细成本与容器规则由 G4/G6 承接，本次不把它们重新塞回这条调用主线。

## 8 用变化后的条件检验模型

### 8.1 迁移问题

1. `calibrated(source)` 与 `calibrated(std::move(source))` 都成功返回独立的 Batch 对象。两次调用对 source 的承诺有何不同？若函数体抛异常，调用方能否一律保留输入？
2. `Batch&& path = std::move(source)` 后，用 path 构造另一个 Batch，为什么仍可能复制？如果 source 是 const，move 又改变了什么？
3. CopyOnly 的 `is_move_constructible` 为真，能否据此声称“移动代价为常数”？显式删除移动又为何不等价于不声明移动？
4. PinnedBatch 不能复制也不能移动，为什么直接返回纯右值可以，先声明 local 再返回却不可以？可选优化能否修复后者的语义错误？
5. 将 `return local` 改成 `return std::move(local)`，怎样影响本例的 NRVO？`-fno-elide-constructors` 为什么没有破坏 direct-result？
6. 函数返回 span，构建没有发生复制，ASan 某次也没报错。这些事实能否证明局部 Batch 的数据可在返回后继续使用？

### 8.2 推理与修正

**第一题。** 普通源表达式让按值参数复制，源值保留；显式交出源时，参数移动构造取走本例数组，源变成约定空值。业务失败不回滚已经发生的参数构造，不能把“函数抛出”理解为“输入仍在”。需要失败时不接管，应重新设计协议，而不是依赖调用者观察结果后猜责任。

**第二题。** 声明中的右值引用与使用名字时的表达式类别是两层；普通上下文里的 path 是左值，所以复制可被选中。`std::move` 不移除 const，const 源无法绑定到本例会修改源的移动构造参数，仍可经 const 引用复制。

**第三题。** trait 检查能否从相应表达式构造，CopyOnly 正好通过 const 引用复制做到。它不证明有移动构造、资源转移或复杂度。显式删除的移动仍可能是最佳候选，选择后调用被禁止；没有这个候选时，复制才可能成为可用的选择。

**第四题。** 同类型纯右值直接初始化结果，不需要选中复制或移动；命名局部对象则依赖另一组规则，NRVO 只是允许实施的省略。本例未省略时所需移动已删除，程序本身不合法，不能借优化掩盖。析构可用性等要求仍需满足。

**第五题。** std::move 调用使返回表达式不再符合本例命名局部对象直接返回的 NRVO 形式，通常只增加一次可观察移动。工具选项可以阻止可选省略，不能改变同类型纯右值直接初始化的语言规则，所以删除复制／移动的 direct-result 仍成立。

**第六题。** 不可以。span 不拥有数组，局部 Batch 销毁后借用失效；代码是否偶然能读、某次检测有没有发现问题都不改变生命规则。应返回拥有值，或明确由调用方提供持续存活的存储。修改表达式类别不能修复缺失的 owner。

G3 到此把逻辑值、资源表示、操作后置条件和调用表达式接了起来。进入 G4 后，再研究一组值由容器持有时，增长、重排、删除与视图组合怎样改变这些关系；不重新从容器名称表开始。
