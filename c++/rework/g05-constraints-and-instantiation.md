# G5 约束、重载与实例化

上一单元已经能解释为什么一条调用改变了类型信息，但接口设计还没有完成。若每次不支持的调用都要等到标准库实现深处报错，调用者仍不知道自己违背了什么条件。本单元把 G4 的“筛选后生成有序读数”写成一个可复用接口，让它公开所需能力，再区分约束检查、重载选择和实现检查。

先读[调用表达式与类型推导](g05-call-and-deduction.md)，最后接[常量求值与生成代码](g05-constant-evaluation-and-codegen.md)。本单元只建立足够解释当前接口的模板模型，不展开完整约束包含算法、旧式 SFINAE 技巧库或通用 ranges adapter 框架。所有实验共用第一单元的 `reading.hpp`，实际执行见 [G5 验证说明](g05-verification.md)。

## 1 先确定接口到底承诺做什么

我们需要的不是“让任何范围都能原地排序”，而是读取一遍输入，复制每条 Reading，返回按编号排序的独立 vector。输入可以是 vector、list 或 filter_view，因为输出的排序发生在新 vector 上。它只遍历一次，也不需要输入本身可写；因此把 random_access_range 或可复制整个范围对象作为输入要求，都会排除本来可处理的调用。

返回值固定为 `vector<Reading>`，意味着这里并不追求所有元素类型的泛型。变化的是遍历来源，记录值和编号语义不变。这个边界很重要：一个接口可以在输入形态上开放，在业务表示上保持具体，而不需要把每个维度都变成模板参数。

**完整实验共用文件 `reading-snapshot.hpp`**

```cpp
#ifndef G5_READING_SNAPSHOT_HPP
#define G5_READING_SNAPSHOT_HPP

#include "reading.hpp"
#include <algorithm>
#include <concepts>
#include <ranges>
#include <vector>

template<class R>
concept ReadingInput = std::ranges::input_range<R> &&
    std::same_as<std::ranges::range_value_t<R>, Reading> &&
    std::constructible_from<Reading, std::ranges::range_reference_t<R>>;

template<ReadingInput R>
std::vector<Reading> sorted_snapshot(R&& input) {
    std::vector<Reading> result;
    auto it = std::ranges::begin(input);
    const auto last = std::ranges::end(input);
    for (; it != last; ++it) result.emplace_back(*it);
    std::ranges::sort(result, {}, &Reading::id);
    return result;
}

#endif
```

input_range 说明可以取得并推进输入迭代器；range_value_t 限定逻辑元素值为 Reading；range_reference_t 描述实际解引用表达式的类型，constructible_from 再检查这个表达式能否构造结果元素。value type 和 reference type 不一定只是相差一个 &，代理引用是一个原因，所以不能只查前者就推断后者的构造一定成立。

这里按 `*it` 的实际表达式直接构造结果，没有把具名中间变量无条件 move 进去。对本章使用的普通容器和视图，它复制 Reading 而不消费原记录；更特殊的迭代器若把解引用定义成破坏性读取，就需要额外语义约束，不能只凭这三个 concept 承诺任意源完全不变。input_range 也允许单遍来源，遍历它可能消费输入游标。[范围访问类型](https://timsong-cpp.github.io/cppwp/n4950/ranges.syn)与[范围概念](https://timsong-cpp.github.io/cppwp/n4950/range.refinements)

### 1.1 独立结果必须用完整值验证

本例选择不同编号，避免把相等键的次序加入合同。sorted_snapshot 不去重，也不筛除 valid 为 false 的记录；筛选是否发生由调用方传入的范围决定。把这些区别写入判据，才能发现实现是否擅自多做或少做一步。

**完整实验 `snapshot.cpp`**

```cpp
#include "reading-snapshot.hpp"
#include <iostream>
#include <list>

int main() {
    const std::vector<Reading> source{
        {103, 30, true}, {101, 10, true}, {102, 20, false}
    };
    const auto original = source;
    const Reading expected[] = {
        {101, 10, true}, {102, 20, false}, {103, 30, true}
    };
    auto result = sorted_snapshot(source);
    if (!std::ranges::equal(result, expected)) return 1;
    result.front().value = 99;
    if (source != original) return 2;
    std::list<Reading> linked(source.begin(), source.end());
    if (!std::ranges::equal(sorted_snapshot(linked), expected)) return 3;
    auto selected = source | std::views::filter([](const Reading& r) {
        return r.valid;
    });
    const Reading kept[] = {{101, 10, true}, {103, 30, true}};
    if (!std::ranges::equal(sorted_snapshot(selected), kept)) return 4;
    auto temporary = sorted_snapshot(std::vector<Reading>{{101, 10, true}});
    if (temporary != std::vector<Reading>{{101, 10, true}}) return 5;
    if (!sorted_snapshot(std::vector<Reading>{}).empty()) return 6;
    std::cout << "one input pass produces an independent sorted snapshot\n";
}
```

按第一单元的命令编译运行 snapshot.cpp，预期输出为 `one input pass produces an independent sorted snapshot`。结果完整性与独立性分别检查；临时输入在调用期间存在，结果持有自己的元素，不返回指向临时范围的迭代器。这与 G4 的 borrowed_range 返回策略是两种不同的设计：一个避免泄漏失效借用，另一个根本不返回输入借用。

实现仍可能因分配或输入访问抛异常。输入若是单遍流，失败前已经消耗的部分不会自动恢复。当前程序对普通非破坏性来源构造新结果，没有建立一般输入事务；此处不重写 FM 的失败合同，也不把正常运行称为分配失败验证。

## 2 requires 写的是可检查条件，不是运行时检查器

模板参数列表中的 `ReadingInput R` 给声明附加约束（constraint）。它不创建接口基类或虚函数表，也不会在每次迭代时动态检查元素类型。R 从调用取得后，编译器判断相关约束是否满足；不满足的模板候选不能成为该次调用的可行选择。[约束声明](https://timsong-cpp.github.io/cppwp/n4950/temp.constr.decl)

requires 子句与 requires 表达式是两层用途。前者把布尔约束附到声明，后者描述一组待检查的要求并形成 bool 结果。命名 concept 让这些要求可以复用。下面故意对比两种看似只差一个词的写法，说明“表达式合法”与“表达式为真”不是同一件事。

**完整实验 `requirement-kinds.cpp`**

```cpp
#include "reading.hpp"
#include <concepts>
#include <iostream>

template<class T>
concept LimitExpression = requires { T::limit > 0; };

template<class T>
concept PositiveLimit = requires { requires (T::limit > 0); };

template<class T>
concept IntegerReading = requires(const T& row) {
    { row.value } -> std::same_as<const int&>;
};

struct Disabled { static constexpr int limit = 0; };
struct Enabled { static constexpr int limit = 8; };
struct NarrowReading { short value; };

int main() {
    static_assert(LimitExpression<Disabled>);
    static_assert(!PositiveLimit<Disabled>);
    static_assert(PositiveLimit<Enabled>);
    static_assert(!LimitExpression<Reading>);
    static_assert(IntegerReading<Reading>);
    static_assert(!IntegerReading<NarrowReading>);
    std::cout << "expression validity and required truth are different checks\n";
}
```

输出为 `expression validity and required truth are different checks`。简单要求 `T::limit > 0;` 只问表达式能否形成；Disabled 的比较完全合法，只是结果为假。嵌套要求 `requires (T::limit > 0);` 才把这个值作为约束。复合要求的箭头检查表达式类型，用到的是 decltype((表达式))，因此 const Reading 左值的 value 对应 const int&，不是 int。[requires 表达式的要求种类](https://timsong-cpp.github.io/cppwp/n4950/expr.prim.req)

复合要求还可以显式加 noexcept 检查异常规格；那也只涉及给定表达式，不自动证明事务保证。类型要求中的 typename 则用来确认一个名字表示类型。需要哪种要求取决于函数实际执行什么，不应只为了让 concept 看起来完整而堆满四种语法。

这些温和失败规则有适用上下文。这里的无效成员都依赖模板参数，在相关替换中使要求不满足；不能把任意非模板代码写进 requires 后就期待所有编译错误都变成 false。概念满足也不验证对象的实时状态：容器是否为空、索引是否对应当前批次、比较器是否满足严格弱序，都不是一个普通成员表达式存在就能回答的。[标准库概念的语法与语义](https://timsong-cpp.github.io/cppwp/n4950/structure.requirements)

## 3 把拒绝放在接口，仍需检查实现

给 sorted_snapshot 传入整数序列时，input_range 本身成立，但 ReadingInput 不成立。这个失败应该发生在接口约束处，而不是直到 emplace_back 深处才说明 int 不能构造 Reading。

**编译负例 `constraint-failure.cpp`：输入元素不符合已声明的业务表示要求。**

```cpp
#include "reading-snapshot.hpp"

int main() {
    auto result = sorted_snapshot(std::vector<int>{10, 20});
    return static_cast<int>(result.size());
}
```

只编译此文件，预期诊断必须包含 sorted_snapshot 以及 ReadingInput 或相应约束未满足的信息。诊断的行号、内部类型名称和展开层数是工具链输出，不作为永久文本合同。

约束写在声明上，并不意味着函数体已经被完整验证。看下面这个故意写坏的访问函数：返回类型明确声明为 T::value_type，所以只检查调用表达式时可以形成声明；真正调用以后，函数体才暴露不存在的成员。

**编译负例 `body-failure.cpp`：调用表达式检查通过，但所需函数体实例化失败。**

```cpp
#include "reading.hpp"
#include <vector>

template<class T>
typename T::value_type unchecked_first(const T& rows) {
    return rows.missing_value();
}

template<class T>
concept DeclaredCall = requires(const T& rows) { unchecked_first(rows); };

static_assert(DeclaredCall<std::vector<Reading>>);

int main() {
    std::vector<Reading> rows{{101, 10, true}};
    return unchecked_first(rows).value;
}
```

预期错误应明确指向 missing_value，并给出 unchecked_first 的实例化关联。这个例子不支持“requires 永远不会检查函数体”：若函数使用 auto 返回类型，推导返回类型本身就可能需要实例化定义，产生不同的检查路径。它支持的具体结论是：对这里具有显式返回类型的声明，调用表达式可形成不足以保证实现成立。

模板替换中的部分无效类型或表达式可以让候选退出，这通常称为替换失败不构成错误（SFINAE）。但该机制受直接上下文（immediate context）限制；替换引发的其他实例化失败未必属于其中。不能把概念、requires 或 SFINAE 当成能捕获一切编译错误的 try/catch。[替换的直接上下文](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.general#8)

typename 在这里也有具体职责：T::value_type 依赖 T，使用 typename 表明这个依赖名字在该位置按类型解析。它不证明 T 真有此成员，后续替换仍要核实。模板定义中的非依赖名字通常在定义处查找，依赖名字及调用另有后续规则；本章不借此展开 ADL、自定义点与完整两阶段查找。

## 4 更具体的重载需要可识别的约束关系

若某个来源支持随机访问，我们可能提供另一条实现路径。不过“它要求更多东西”是人的解释，编译器需要按约束的标准规则判断两个声明之间的关系。最稳妥的写法是复用同一个命名概念，再添加额外条件。

**完整实验 `overload-selection.cpp`**

```cpp
#include "reading-snapshot.hpp"
#include <iostream>
#include <list>

template<ReadingInput R>
int selected_path(R&&) { return 1; }

template<ReadingInput R>
    requires std::ranges::random_access_range<R>
int selected_path(R&&) { return 2; }

int main() {
    std::vector<Reading> rows{{101, 10, true}};
    std::list<Reading> linked(rows.begin(), rows.end());
    auto filtered = rows | std::views::filter([](const Reading& r) {
        return r.valid;
    });
    if (selected_path(rows) != 2) return 1;
    if (selected_path(linked) != 1) return 2;
    if (selected_path(filtered) != 1) return 3;
    std::cout << "shared named constraints order the eligible overloads\n";
}
```

输出为 `shared named constraints order the eligible overloads`。两个函数只返回路径编号，没有声称第 2 条路径更快，也没有复制 sorted_snapshot 的实现。这个实验单独回答哪一个重载会被选择，机器成本仍需 G6 的测量。

约束归一化会形成原子约束（atomic constraint），其同一性涉及源表达式的出现位置和参数映射，不是一个任意数学定理证明器。命名 ReadingInput 的复用让共同条件来自同一处定义。若把一个布尔条件在两个声明里分别重写，虽然人看来第二条是“第一条再加一个条件”，编译器未必把共同部分视作同一个原子约束。[原子约束同一性](https://timsong-cpp.github.io/cppwp/n4950/temp.constr.atomic)与[约束排序](https://timsong-cpp.github.io/cppwp/n4950/temp.constr.order)

**编译负例 `ambiguous-constraints.cpp`：重复书写的条件不能代替共享约束身份。**

```cpp
#include <type_traits>

template<class T> requires std::is_integral_v<T>
int select_integer(T) { return 1; }

template<class T> requires (std::is_integral_v<T> && std::is_signed_v<T>)
int select_integer(T) { return 2; }

int main() {
    return select_integer(1);
}
```

只编译，预期诊断为 select_integer 调用有歧义。这里不要求编译器猜测开发者的偏好；可以把共同判断定义成一个命名 concept 后复用。更复杂的偏序与约束包含留作后续回查，不把本例推广成“多写一个 requires 就必然更优先”。

## 5 形成类模板特化不等于检查了每个成员函数体

函数体可能在需要时才实例化，类模板同样有这种按需性质。使用一个类型建立对象，需要确定相应布局和成员声明；它通常不要求同时实例化所有未使用的非删除成员函数定义。否则很多只在特定操作上有要求的类模板就无法表达。

**完整实验 `member-instantiation.cpp`**

```cpp
#include "reading.hpp"
#include <cstddef>
#include <iostream>
#include <vector>

template<class R>
struct Inspector {
    const R& rows;
    std::size_t size() const { return rows.size(); }
    int unavailable() const { return rows.missing_value(); }
};

int main() {
    const std::vector<Reading> rows{{101, 10, true}, {102, 20, true}};
    Inspector<std::vector<Reading>> inspector{rows};
    if (inspector.size() != 2) return 1;
    std::cout << "using one member does not validate every dependent body\n";
}
```

输出为 `using one member does not validate every dependent body`。unavailable 中的非法成员访问依赖 R，当前不调用它；不能因为类已经成功使用，就对该成员贴上验证通过标签。反过来，这也不是隐藏任意语法错误的办法：源码仍须被解析，非依赖错误以及某些影响类声明的依赖类型错误可能更早失败。若成员调用、常量求值或其他规则要求定义，检查时机也会改变。[隐式实例化的范围](https://timsong-cpp.github.io/cppwp/n4950/temp.inst)

到这里，可以把泛型接口的审查拆开：约束是否足以描述实现使用的能力；所有声明的支持类型是否真的走过所需成员；运行时的关系语义是否另有判据。一个只建立对象但不调用关键成员的测试，不能代表整个模板类型的支持矩阵。下一单元会进一步观察，实例化出来的实体如何进入目标文件，以及什么情况下只是声明通过而链接失败。

## 6 用变化后的条件检验模型

### 6.1 迁移问题

1. sorted_snapshot 接受 list 和 filter_view，是否说明 ranges::sort 现在可以直接接受它们？为什么输入约束不需要随机访问？
2. ReadingInput 既检查 value type 又检查从 reference type 构造，分别防止什么误判？它能证明所有输入在调用后原样不变吗？
3. `requires { T::limit > 0; }` 在 limit 为零时为什么仍可能成立？如何把“正数”真正加入约束？
4. DeclaredCall 检查通过后，调用 unchecked_first 为什么还能编译失败？改用 auto 返回能否保证失败变成 false？
5. 两个重载分别写同样的 trait 条件，为什么不一定建立更具体关系？复用命名 concept 有什么不同？
6. Inspector 成功实例化且 size 可用，是否证明 unavailable 可用？测试怎样才真正覆盖该成员？

### 6.2 推理与修正

**第一题。** sorted_snapshot 先读取输入，再在自己的 vector 上排序。输入只负责产生一串 Reading，排序所需随机访问由输出提供。它没有改变标准 sort 的约束，代价是结果存储与元素构造；返回新值和原地修改是两个合同。

**第二题。** value type 限定逻辑记录表示，reference type 反映实际解引用表达式，两者对代理或带限定访问可能不同。构造检查避免只根据逻辑值类型猜测表达式可用。但 input_range 可能是单遍，特殊读取也可能改变状态；语法检查不能承诺所有源无副作用。

**第三题。** 简单要求只问比较表达式是否合法，不要求其值为真。用嵌套要求把常量布尔表达式作为约束，或在 requires 子句中直接使用该条件。对象运行时的可变 limit 又是另外的问题，不能随意把运行数据搬进模板约束。

**第四题。** 已声明返回类型让编译器能形成调用类型，不必由本例的函数体推导结果。真正调用需要实例化定义，才遇到 missing_value。auto 返回可能迫使函数体更早实例化，但该错误未必属于可温和失败的直接上下文；必须明确表达接口所需操作，不能靠这种改写吞掉实现错误。

**第五题。** 原子约束的同一性不是仅比较最终布尔值或文本含义；两处独立表达式可能不是同一原子约束。共享命名概念使共同条件来自同一处定义，增加的条件才能在本例形成可排序关系。这不是通用的“条件数量越多优先级越高”。

**第六题。** 使用 size 只要求相应定义成立，未使用的依赖成员体不因此获得证明。测试应对声明支持的类型实际触发关键成员定义，并检查行为；若该成员不应支持这种类型，应在接口约束或类型设计中表达，而不是等待用户碰到隐藏错误。
