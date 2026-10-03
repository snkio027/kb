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

### 2.1 Satisfaction 不等于 modeling

标准库的 concept 往往同时含有可检查的语法要求与语义要求。constraint satisfaction 判断给定模板实参下约束表达式是否成立；说某类型 models 一个 concept，还涉及它的操作是否满足该 concept 的语义。编译器能检查一次比较表达式能否形成，却通常不能证明任意比较器在所有输入上建立 strict weak ordering；G4 的关系推导因此仍是 caller 的义务。[N4950：标准库约束与语义要求](https://timsong-cpp.github.io/cppwp/n4950/structure.requirements)

这给泛型 API 留下三层合同：declaration 暴露可检查能力，implementation 实际使用这些能力，semantic contract 规定它们应怎样相互一致。只放宽 requires、不检查实现，会放入不能编译的类型；只验证函数体能编译、不检查语义关系，会放入运行上不成立的类型。反过来，把无关能力写进约束，又会无理由排除合法输入。

对 sorted_snapshot，input_range 对应一次读取，结果元素构造对应实际解引用表达式，输出排序依赖 Reading 的既定关系。它不需要输入可随机访问，更不需要输入整个 range 对象可复制。好的约束应当来自实现所需操作和公开的语义承诺，而不是把调用方常用类型的全部能力打包成前置条件。

### 2.2 requires 子句与表达式的职责

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

四种要求可以按所提的问题区分，而不是按标点记忆。下表是语法回查；其中类型要求和附加 noexcept 的复合要求没有另增运行用例。

| 要求种类 | 形式示意 | 判断的命题 |
| --- | --- | --- |
| 简单要求（simple requirement） | `expression;` | 表达式能否合法形成，不要求结果为真 |
| 类型要求（type requirement） | `typename T::value_type;` | 名字是否表示类型，不单独要求该类型完整 |
| 复合要求（compound requirement） | `{ expression } noexcept -> C;` | 表达式合法，并检查所写的异常与结果类型要求；后两项可省略 |
| 嵌套要求（nested requirement） | `requires condition;` | 对应约束在替换后是否满足 |

复合要求中的 noexcept 问整个表达式是否为潜在抛出表达式，不只看最外层函数声明；箭头把 decltype((expression)) 交给指定的类型约束，并不是给表达式声明返回类型。这些检查不会把被列出的业务操作作为运行时调用执行，也不由此证明事务保证。需要哪种要求取决于函数实际执行什么，不应只为了让 concept 看起来完整而堆满四种语法。

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

这里的“直接上下文”是对推导替换位置内错误的范围限制，不是离调用行有多近。函数类型中除 noexcept 说明符以外的部分、explicit 说明符及模板参数声明属于推导替换位置；直接在其中形成无效类型或表达式，与为了检查它们而另外实例化一个类或函数体，是不同的错误来源。后者不因此获得 SFINAE 保护。本例的 missing_value 位于被实例化的函数体，所以不能让编译器静默撤回选择、再试下一个重载。约束不满足可以排除候选，也不等于所有约束相关错误都能温和失败。[推导替换位置与副作用边界](https://timsong-cpp.github.io/cppwp/n4950/temp.deduct.general#7)

typename 在这里也有具体职责：T::value_type 依赖 T，使用 typename 表明这个依赖名字在该位置按类型解析。它不证明 T 真有此成员，后续替换仍要核实。模板定义中的非依赖名字通常在定义处查找，依赖名字及调用另有后续规则；本章不借此展开 ADL、自定义点与完整两阶段查找。

### 3.1 从找到声明到选中实现

为了把诊断放回同一张模型里，需要区分候选函数（candidate function）、可行函数（viable function）和最终选中的重载。候选集合回答本次重载决议考虑哪些函数；可行集合进一步满足实参数量、关联约束及各实参到形参的隐式转换等要求；选择阶段才比较可行函数，寻找唯一最佳者。函数模板通过推导与检查得到的函数特化参与这个集合，不应把每一个查找到的模板声明都视为已经形成了可行函数。[候选与可行函数](https://timsong-cpp.github.io/cppwp/n4950/over.match)

对本章案例，回查顺序可以压缩为：

1. **查找与候选形成：** 从调用上下文找到相关声明，函数模板需要取得模板实参并完成相应替换与约束检查。
2. **可行性判断：** 对形成的候选检查能否接受这次实参；某一个候选被排除，不一定使整个调用失败。
3. **排序与选择：** 比较转换序列；在相应条件下结合函数模板偏序及约束关系，选出唯一最佳函数。没有可行者与存在歧义是两种失败。
4. **所需定义的检查：** 当使用要求定义时，实例化并检查所选特化的实现。选中了一个声明，不保证它的定义成立、可访问或未被删除。

这些是解释职责，不是互不相交的编译器通道。第一步的约束检查已经影响候选能否形成，返回类型推导等还可能提前需要函数体。可行性也不是“concept 为真”的同义词：实参转换与绑定仍须成立。反过来，选中删除函数或不可访问函数不会自动退回次优函数。[可行性与最佳函数](https://timsong-cpp.github.io/cppwp/n4950/over.match.viable)及[选择后的合法性](https://timsong-cpp.github.io/cppwp/n4950/over.match#general)

据此看前面两次失败：`vector<int>` 无法满足 ReadingInput，sorted_snapshot 的相应模板路径不能提供可行选择；unchecked_first 的声明却允许形成调用，错误随后发生在所需定义中。接下来 selected_path 的实验则专门研究第三步，不再把“被允许参与”与“最终获选”混成同一个结论。

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

### 4.1 满足约束与比较约束是两个问题

约束表达式（constraint expression）是源码中表达要求的形式；约束归一化（constraint normalization）按规则把它转换成由合取、析取和原子约束组成的结构。命名 concept 的使用会引入其定义的归一化结构与参数映射。原子约束不只是一个最终布尔值，还保留源表达式身份及模板参数如何对应的信息。[约束声明与归一化](https://timsong-cpp.github.io/cppwp/n4950/temp.constr#normal)

约束满足（constraint satisfaction）回答“这一组模板实参是否符合要求”：对原子约束作规定的替换，合法时要求表达式具有 bool 类型且是常量表达式，并以 true 为满足；合取和析取按规定顺序短路检查。归一化负责建立结构，满足性负责对具体实参作判断，两者都不检查运行中每个对象是否始终遵守业务不变量。[原子约束的满足性](https://timsong-cpp.github.io/cppwp/n4950/temp.constr.atomic#3)

约束包含（subsumption）则比较两套约束之间的关系，不只问它们对当前实参是否恰好都为真。其形式规则比较一方的析取范式与另一方的合取范式，并以相同原子约束建立对应。最小模型是：若 A、B 表示确定身份的原子约束，A ∧ B 包含 A，A 包含 A ∨ B；反方向通常不成立。不能把 A 换成“数学含义相同但身份不同”的另一个表达式，再沿用这个判断。[约束包含与偏序](https://timsong-cpp.github.io/cppwp/n4950/temp.constr.order)

selected_path 的两个候选复用 ReadingInput，增加 random_access_range 的版本因而能在本例形成更受约束的关系。select_integer 的两次 trait 表达式却各有出现位置，当前 int 同时令它们为真也不足以消除歧义。这说明 satisfaction 不是 subsumption，subsumption 也不是全局优先级：它只在重载及模板偏序规则规定的比较位置起作用，不能越过其他转换条件任意指定赢家。

### 4.2 逻辑蕴含与 subsumption 为什么不能互换

人的推理可以利用任意已知定理判断两个命题的蕴含，编译器的约束排序只按规定的归一化结构和 atomic constraint identity 比较。这个限制让接口结构本身成为重载设计的一部分：复用同一个命名 concept，不只是减少重复字数，也保留共同要求的身份。

例如一个实现同时支持 A 与 B，并不单凭当前输入让两者都为 true 就确定哪个重载更专门；需要检查参与偏序的共同原子约束怎样对应。因此把 requires 拆入 helper 或在另一个位置重写等价 trait，不应被当作纯视觉整理。它可能改变候选之间的可比较关系，而无需改变任一布尔条件在当前样本上的结果。本章的歧义负例正是用来把“当前输入满足”与“接口之间有序”分开。

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

这里的特化（specialization）与实例化（instantiation）需要分开。特化是针对特定模板实参的类、函数等实体；它可以由模板实例化而来，也可以由程序员显式特化。实例化是依据模板形成相应声明或定义的过程，不等于为每个名字立即生成一段机器代码。`Inspector<std::vector<Reading>>` 指定一个类特化；需要它的完整类型，与需要 size 或 unavailable 的定义，是不同要求。[实例化与特化的定义](https://timsong-cpp.github.io/cppwp/n4950/temp.spec#general)

| 机制 | 触发或作用 | 不能直接推出的结论 |
| --- | --- | --- |
| 隐式实例化 | 使用要求完整类型、定义或相关语义时，按规则实例化 | 提到模板名字就检查所有成员 |
| 显式实例化声明 | 用 extern template 对指定实体声明实例化安排，抑制相应隐式实例化；存在规则例外 | 已经提供定义，或再也不需要任何实例化 |
| 显式实例化定义 | 明确要求从可用模板定义实例化指定实体 | 为所有可能模板实参供应实现 |
| 成员按需实例化 | 类的声明与成员定义各有需求条件 | 建立对象成功就证明全部成员可用 |

这张表并不把类的显式实例化定义当作“只检查被调用成员”：它还涉及满足条件的非模板成员及在该位置已有定义的成员，范围不同于刚才的隐式实例化案例。显式实例化也不是显式特化；前者使用模板提供实现，后者为特定实参另行规定特化。下一单元会用 extern template 与提供方文件直接观察前者，不展开后者的技巧。[显式实例化及成员范围](https://timsong-cpp.github.io/cppwp/n4950/temp.explicit)

到这里，可以把泛型接口的审查拆开：约束是否足以描述实现使用的能力；所有声明的支持类型是否真的走过所需成员；运行时的关系语义是否另有判据。一个只建立对象但不调用关键成员的测试，不能代表整个模板类型的支持矩阵。下一单元会进一步观察，实例化出来的实体如何进入目标文件，以及什么情况下只是声明通过而链接失败。

### 5.1 Instantiation demand 是一张依赖图

“延迟实例化”不是把整个类统一拖到最后检查。名字查找、类布局、成员声明、返回类型推导、常量求值和函数体分别可能产生对其他实体的需求；某个需求又可能触发下一层实例化。用 dependency graph 理解它，比设想一个固定的“模板展开时刻”更准确。

例如声明中的显式返回类型可能让调用可行性先被检查，而 auto 返回类型需要从定义取得结果，可能使 body 更早参与。指向某类特化的指针通常不要求了解完整布局，真正建立该类对象则会引入完整性需求。要验证一个泛型组件，测试矩阵应覆盖公开承诺的操作，不只是让若干 `Type<T>` 名字出现在程序中；本章仅执行已经列明的成员与调用，不把未实例化路径算入 PASS。

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
