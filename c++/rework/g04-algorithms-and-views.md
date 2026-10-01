# G4 算法、遍历能力与惰性视图

容器负责保存元素，算法通过访问接口处理元素，但这不意味着两者互不相关。排序需要怎样移动元素，筛选是否修改原序列，返回的迭代器还能活多久，都取决于算法合同与底层范围。仅把循环换成一个标准库名字，并没有完成这些判断。

本单元继续使用[上一单元](g04-sequences-and-identity.md)的 `Reading` 和 `reading.hpp`。任务也保持连续：筛掉无效记录，按读数排列，导出一份供显示使用的结果。我们先处理已经执行完的算法，再处理等到遍历时才计算的视图；[下一单元](g04-lookup-and-indexes.md)把结果组织成可按编号查找的数据结构。

## 1 迭代器表达能力，不只是包装一个地址

一个范围（range）提供开始位置和终点。迭代器（iterator）描述当前位置及允许的操作，哨兵（sentinel）用来判断遍历何时结束；二者不必具有相同类型。`[begin, end)` 不包含尾后位置，终点可比较不等于可解引用。

不同算法要求不同能力。输入迭代器只承诺单遍读取；前向迭代器增加多遍保证，复制出的有效位置可以用于独立遍历；双向迭代器允许后退；随机访问迭代器支持常数时间位移与距离操作；连续迭代器再把访问关系约束到连续存储。能力之间有关联，但不是“都叫 iterator，所以都能相减”。[迭代器概念](https://timsong-cpp.github.io/cppwp/n4950/iterator.concepts)

即使一个范围可随机访问，也不一定可重排。只读元素不能被写入；某些迭代器解引用得到代理而非 `T&`。算法的 `sortable`、`permutable` 等约束还检查移动、交换及比较关系。G5 再展开这些概念怎样参与约束求解；这里先把它们当作算法的能力合同，而不是编译器报错中的噪声。[算法共同要求](https://timsong-cpp.github.io/cppwp/n4950/alg.req)

### 1.1 单遍输入不适合先数一遍再重读

流输入能直观解释为什么 range 不必是容器。下面从字符串流中依次读取三个整数，输入尚未转换为可重复遍历的序列。

**完整实验 `single-pass.cpp`**

```cpp
#include <algorithm>
#include <iostream>
#include <iterator>
#include <ranges>
#include <sstream>
#include <vector>

int main() {
    std::istringstream source{"10 -2 30"};
    auto input = std::ranges::istream_view<int>(source);
    static_assert(std::ranges::input_range<decltype(input)>);
    static_assert(!std::ranges::forward_range<decltype(input)>);
    std::vector<int> stored;
    std::ranges::copy(input, std::back_inserter(stored));
    const int expected[]{10, -2, 30};
    if (!std::ranges::equal(stored, expected) || !source.eof()) return 1;
    if (std::ranges::distance(stored) != 3) return 2;
    if (!std::ranges::equal(stored, expected)) return 3;
    std::cout << "input is consumed once; stored values support repeated passes\n";
}
```

程序输出 `input is consumed once; stored values support repeated passes`。重复使用的是新 vector，不是已经消耗的输入。对流先调用 `distance` 再复制，可能已经把输入读完；改成一次遍历追加，或者在第一次读取时明确保存数据，才符合这种来源的能力。

这里的流里只有三个合法整数；真实输入还需要区分结束、格式错误和 I/O 失败。本例仅验证单遍遍历与显式保存的区别，不是一套完整输入解析协议。[istream_view 的读取模型](https://timsong-cpp.github.io/cppwp/n4950/range.istream)

`back_inserter` 把输出赋值转换为末尾插入，容器据此建立元素。它不同于空 vector 的 `begin()`：后者没有可写元素，即使已经 reserve 了足够容量。迭代器接口隐藏了部分操作形式，没有隐藏输出范围必须有效这一前提。

## 2 排序合同包括比较规则和业务身份

需求是“按读数从小到大显示，同读数保持输入顺序”。投影（projection）`&Reading::value` 让算法从整条记录取出比较键，而无需先另建一个数值数组。实际被重排的仍是完整 Reading；如果只排序 value 字段，就会破坏它和 id 的对应关系。

排序使用的比较必须建立严格弱序（strict weak ordering）。直观上，不能把自己排在自己前面，先后关系应能传递，互相都不在对方前面的等价关系也应能传递。`a.value <= b.value` 不满足第一项；随机结果、不断变化的外部阈值也不能形成稳定顺序。若未来换成浮点读数，含 NaN 的输入需要明确处理策略，不能直接把普通 `<` 当作覆盖全部浮点值的合法排序合同。[排序的关系要求](https://timsong-cpp.github.io/cppwp/n4950/alg.sorting)

**完整实验 `sort-identity.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<Reading> rows{
        {103, 30, true}, {101, 10, true}, {102, 10, true}
    };
    const auto original = rows;
    Reading* first_position = &rows.front();
    const int selected_id = first_position->id;
    const auto capacity = rows.capacity();
    std::ranges::stable_sort(rows, {}, &Reading::value);
    const Reading expected[]{
        {101, 10, true}, {102, 10, true}, {103, 30, true}
    };
    if (!std::ranges::equal(rows, expected)) return 1;
    if (first_position != &rows.front() || first_position->id != 101) return 2;
    if (rows.capacity() != capacity || rows.size() != original.size()) return 3;
    auto selected = std::ranges::find(rows, selected_id, &Reading::id);
    if (selected == rows.end() || selected->value != 30) return 4;
    if (original.front().id != 103) return 5;
    std::cout << "stable ordering preserves ties, not selected positions\n";
}
```

预期输出为 `stable ordering preserves ties, not selected positions`。101 与 102 比较等价，稳定排序保留它们的先后；103 则从首位置移到末位置。`first_position` 仍可访问当前位置的对象，却不再定位原来选中的记录。按 ID 重新查找才保留了当前需求中的选择含义。

`ranges::sort` 不保证等价元素保持原有先后；只有确实需要这种语义时才选稳定排序。也不要把算法调用当成事务：比较器或元素操作抛异常时，并没有通用的“自动恢复完整原顺序”承诺。需要保留原值时，可以像 G3 那样在独立副本上完成准备，再明确提交；这还要承担复制、额外内存及最终提交的成本。

## 3 移除算法怎样留下一个需要容器处理的尾部

`ranges::remove_if` 通过迭代器处理元素，不能直接改变所属 vector 的 `size()`。它把保留的值按原有相对顺序集中到前面，返回待处理的尾部范围；传统 `std::remove_if` 则返回新的逻辑终点。尾部仍属于容器，但其中的值处于有效但未指定状态，不能当成“被删除记录的清单”。随后才由容器擦除尾部。[移除算法](https://timsong-cpp.github.io/cppwp/n4950/alg.remove)

**完整实验 `compact-records.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <iostream>
#include <iterator>
#include <vector>

int main() {
    std::vector<Reading> rows{
        {101, 10, true}, {102, 20, false}, {103, 30, true}, {104, 40, false}
    };
    auto other = rows;
    const auto old_size = rows.size();
    const auto capacity = rows.capacity();
    auto tail = std::ranges::remove_if(rows, [](const Reading& r) {
        return !r.valid;
    });
    const Reading expected[]{{101, 10, true}, {103, 30, true}};
    if (rows.size() != old_size) return 1;
    if (!std::ranges::equal(rows.begin(), tail.begin(),
                            std::begin(expected), std::end(expected))) return 2;
    rows.erase(tail.begin(), tail.end());
    if (!std::ranges::equal(rows, expected) || rows.capacity() != capacity) return 3;
    auto removed = std::erase_if(other, [](const Reading& r) { return !r.valid; });
    if (removed != 2 || !std::ranges::equal(other, expected)) return 4;
    std::cout << "compaction selects the prefix; erase changes container size\n";
}
```

输出为 `compaction selects the prefix; erase changes container size`。程序不读取尾部值来猜实现如何搬移，完整结果检查发生在 erase 之后。它还比较 `std::erase_if` 的结果：对 vector，这个组合接口直接完成压缩及擦除，返回移除数量，适合不需要中间阶段的场景。[vector 擦除辅助函数](https://timsong-cpp.github.io/cppwp/n4950/vector.erasure)

和上一单元逐次 erase 相比，一次压缩再擦除避免了反复搬移长后缀；但这里没有做计时，不能据此给出固定加速倍数。若需要把被剔除记录送到审核队列，应在失去它们的值之前另行收集或选择合适的分区方案，而不是事后读取未指定尾部。

## 4 视图保存的是遍历关系，不是结果快照

现在不想删除原始读数，只希望展示有效项，并把显示值加上 10。`filter` 负责跳过不符合谓词的元素，`transform` 在解引用时产生转换结果。组合 view 不会在定义那一行就自动生成完整的输出 vector；转换何时发生，取决于何时真正访问元素。[transform 迭代器](https://timsong-cpp.github.io/cppwp/n4950/range.transform.iterator)

**完整实验 `lazy-and-owned.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <iostream>
#include <iterator>
#include <ranges>
#include <vector>

auto above(std::vector<Reading>& rows, int threshold) {
    return rows | std::views::filter([threshold](const Reading& r) {
        return r.valid && r.value > threshold;
    });
}

auto owned_values() {
    return std::vector<int>{10, 20, 30}
        | std::views::transform([](int value) { return value + 10; });
}

int main() {
    std::vector<Reading> rows{{101, 10, true}, {102, 20, false}, {103, 30, true}};
    int threshold = 0;
    auto selected = above(rows, threshold);
    auto display = selected | std::views::transform([](const Reading& r) {
        return r.value + 10;
    });
    std::vector<int> snapshot;
    std::ranges::copy(display, std::back_inserter(snapshot));
    threshold = 100; // The predicate already holds its own threshold value.
    rows[0].value = 15; // Still satisfies the predicate; no structural edit.
    const int before[]{20, 40};
    const int after[]{25, 40};
    if (!std::ranges::equal(snapshot, before)) return 1;
    if (!std::ranges::equal(display, after) || threshold != 100) return 2;
    auto owned = owned_values();
    const int expected_owned[]{20, 30, 40};
    if (!std::ranges::equal(owned, expected_owned)) return 3;
    std::cout << "view observes source; materialized values form a snapshot\n";
}
```

预期输出为 `view observes source; materialized values form a snapshot`。整数加法的输入在本例范围内，不会溢出；这不是任意传感器数值的校准函数。`snapshot` 已经拥有输出值，后续修改原始记录不影响它；`display` 再次读取时则看到 15，经转换得到 25。

### 4.1 拥有底层范围与拥有全部依赖是两回事

`above` 收到 vector 左值，视图借用这个外部容器；阈值则按值捕获，所以函数返回后不依赖其局部参数的生命。若把捕获改成 `[&threshold]`，返回的闭包会引用已经结束生命的参数。owner 活着也救不了这个依赖。

`owned_values` 使用临时 vector，在 C++23 的这个组合中由 owning_view 持有它，函数返回后仍可遍历。对非 view 的 vector 左值，`views::all` 使用 ref_view；对这里的右值则使用 owning_view。因此 view 不是“不拥有”的同义词，也不是所有 view 都有延迟转换。[all、ref_view 与 owning_view](https://timsong-cpp.github.io/cppwp/n4950/range.all)

应沿依赖链分别检查底层元素、view 对象和闭包捕获。返回 view 只在这些依赖都满足实际使用时间时成立；`auto` 推导出一个可返回的类型，不会自动证明它们的生命周期。

### 4.2 惰性不等于每次都从头重新查询

在前向范围上，filter_view 的 `begin()` 会缓存第一次找到的起点，以满足后续调用的摊销常数时间要求。因此已经遍历过的 filter 不应当作会自动重新扫描全部源数据的查询系统；修改成员资格相关的数据或结构后，若需要重新筛选，应重新建立 view。[filter 起点缓存](https://timsong-cpp.github.io/cppwp/n4950/range.filter.view)

上例只改变仍然满足谓词的记录值，不改变序列结构及成员资格。更危险的做法是在遍历过程中让当前元素不再满足 filter 谓词；N4950 对修改 filter 迭代器所指元素有明确限制，结果不再满足谓词会导致未定义行为。本章不通过运行这种程序观察“筛选器会不会自动跳过它”。[filter 迭代器的修改边界](https://timsong-cpp.github.io/cppwp/n4950/range.filter#range.filter.iterator)

适合作为起点的工程合同是：一轮遍历期间保持结构及筛选条件稳定，修改结束后重建视图；确实需要稳定结果时物化为拥有值的容器。这是让依赖可审查的安排，不是宣称所有合法修改都必须禁止。

## 5 borrowed_range 只处理一部分悬挂风险

范围算法若从一个即将结束生命的临时 vector 返回迭代器，调用方在语句结束后就不能使用它。部分 ranges 算法用 `borrowed_iterator_t` 或 `borrowed_subrange_t` 选择返回类型：对不满足相应借用条件的右值范围，返回 `ranges::dangling`，而不是交出那个迭代器。[dangling 的返回类型规则](https://timsong-cpp.github.io/cppwp/n4950/range.dangling)

`borrowed_range` 关注取得的迭代器是否依赖范围变量本身的生命周期。对于 span 这样的包装对象，销毁包装不必使迭代器失效；这项性质不保证底层元素一直存在，也不取消容器修改带来的失效规则。这里讨论的是迭代器有效性，不能把它扩张为任意范围对象及其所有关联状态都可以随时销毁。[borrowed_range 的语义要求](https://timsong-cpp.github.io/cppwp/n4950/range.range#5)

**完整实验 `range-lifetime.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <concepts>
#include <iostream>
#include <ranges>
#include <span>
#include <vector>

int main() {
    using Rows = std::vector<Reading>;
    static_assert(std::ranges::borrowed_range<Rows&>);
    static_assert(!std::ranges::borrowed_range<Rows>);
    static_assert(std::ranges::borrowed_range<std::span<Reading>>);
    Rows rows{{101, 10, true}, {103, 30, true}};
    auto found = std::ranges::find(std::span{rows}, 103, &Reading::id);
    if (found == std::span{rows}.end() || found->value != 30) return 1;
    auto unavailable = std::ranges::find(Rows{{101, 10, true}}, 101, &Reading::id);
    static_assert(std::same_as<decltype(unavailable), std::ranges::dangling>);
    auto filtered = std::span{rows} | std::views::filter([](const Reading& r) {
        return r.valid;
    });
    static_assert(!std::ranges::borrowed_range<decltype(filtered)>);
    std::cout << "borrowed range concerns the wrapper, not immortal elements\n";
}
```

输出为 `borrowed range concerns the wrapper, not immortal elements`。临时 span 的销毁不会销毁 rows 的元素，所以取得的迭代器可以继续用；但 rows 之后重新分配或结束生命，访问仍会失效。`Rows&` 满足 borrowed_range 是模板参数包含左值引用这一事实，不是 vector 从此承诺所有迭代器永久有效。[borrowed_range 条件](https://timsong-cpp.github.io/cppwp/n4950/range.range)

filter_view 即使建立在 span 上也不是 borrowed_range。其迭代器继续前进时需要访问父 view 保存的谓词；底层元素活着不能代替父 view 的生命。这个反例说明，组合后要重新检查结果类型的合同，不能把底层范围的一项性质机械传播给所有 adapter。

**编译负例 `dangling-result.cpp`：返回对象不提供解引用操作，不是运行时内存反例。**

```cpp
#include <algorithm>
#include <vector>

int main() {
    auto result = std::ranges::find(std::vector<int>{10, 20}, 20);
    return *result;
}
```

执行器用 `-c` 检查目标诊断，不能把链接失败算作成功。另一方面，把已经悬挂的 span 交给算法，或者直接从局部 vector 返回普通迭代器，并不会被这套返回类型规则全面拦截。它不是 G1 所说的语言级借用检查器。

## 6 组合视图可能降低算法可用能力

filter 需要逐项寻找下一个符合条件的位置。即使底层 vector 可以一步跳到第 n 个元素，也不能凭同样操作直接到达第 n 个匹配项。因此 vector 的 filter_view 不再提供随机访问，不能直接传给 `ranges::sort`。

**编译负例 `sort-filter.cpp`：筛选结果缺少排序所需的随机访问能力。**

```cpp
#include <algorithm>
#include <ranges>
#include <vector>

int main() {
    std::vector<int> values{30, -1, 10};
    auto positive = values | std::views::filter([](int n) { return n > 0; });
    std::ranges::sort(positive);
}
```

修复要从任务出发：若原序列应被整体排序，就对原容器排序后再筛选；若只需要一份排序后的独立显示结果，就先把筛选结果物化，再排序新容器。两者对原始数据和存储成本的影响不同，不能为了让代码编译就随意互换。

同样，transform 可能返回新值而非可写引用；一个 view 对象是 const，也未必能调用每种 adapter 的 begin。具体类型、元素可写性、闭包状态及算法要求都要一起检查。到这里，G3 的表达式与类型判断已经成为实际工具，而不只是一组需要记忆的分类。

## 7 用变化后的条件检验模型

### 7.1 迁移问题

1. 为输入流先计算 distance，再 reserve 并复制，为什么可能得不到原来的输入？
2. 比较器用 `<=`，短数组测试一直得到正确顺序，是否可以接受？
3. remove_if 后容器 size 没变，尾部也碰巧保留被剔除编号，能否把尾部直接当审计记录？
4. filter 返回后底层 vector 仍活着，为什么按引用捕获局部阈值仍可能失败？
5. 临时 span 允许算法返回迭代器，为什么这不能证明以后扩容仍可用？
6. 要对匹配记录排序，同时保持源数据原顺序，应该调整哪个阶段？

### 7.2 推理与修正

**第一题。** 输入范围可能只能遍历一次，求距离本身已经消耗它。reserve 不会恢复来源，应一次读取并追加，或在第一遍明确建立可重复遍历的数据副本。

**第二题。** 不能。相同值下比较仍返回 true，违反严格弱序；几次运行结果不能补足语义前提。应先修正关系，再用测试验证具体数据的结果。不要把不合法比较器交给算法后等待 sanitizer 替你证明它错误。

**第三题。** 不能。算法只保证保留前缀的结果，尾部处于有效但未指定状态。需要记录剔除项时，应在压缩前收集或改用具有合适结果合同的操作。

**第四题。** view 同时依赖元素与闭包引用的对象，保持一个依赖活着并不保持另一个。按值保存本例的小整数阈值可以切断该局部生命周期依赖；其他捕获仍需逐项判断。

**第五题。** borrowed_range 讨论的是范围包装对象的生命，不是对底层元素失效规则的豁免。vector 扩容仍要求重新取得元素访问路径。

**第六题。** 把筛选结果复制到拥有值的容器，再对该容器排序。直接排序原容器会破坏原顺序；直接排序 filter 又不满足能力要求。是否值得保留副本由业务和成本约束决定。

算法和 view 现在已经能够表达“怎样处理一批数据”。下一步要回答“怎样找到其中那条记录”，以及为查询额外建立的结构怎样跟随修改。[第三单元](g04-lookup-and-indexes.md)从 lower_bound 的一个常见误判继续。
