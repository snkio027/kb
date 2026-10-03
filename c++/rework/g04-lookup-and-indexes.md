# G4 按键查找与索引一致性

前两个单元已经能收集、修改和处理一批读数。现在界面需要反复询问“编号 103 当前对应什么值”，而批次中的排列顺序可能改变。扫描整批可以得到答案；增加排序约束、使用关联容器或维护独立索引，也可以改变查找方式。但查询结构越多，需要共同维护的关系就越多。

本单元沿同一个 `Reading` 模型，先用有序 vector 建立精确查找，再区分 map 与 unordered_map 的合同，最后完成一个整体替换的带索引批次。目标不是设计通用数据库，而是解释：单个容器各自有效，为什么还不足以保证多容器组件正确。共用头文件见[第一单元](g04-sequences-and-identity.md)，执行结果见[G4 验证说明](g04-verification.md)。

## 1 lower_bound 返回边界，不直接返回匹配结论

### 1.1 Partition invariant 与 membership 是两个命题

对查询 key，可以把范围中的判断写成 `comp(project(element), key)`。lower_bound 要求这些判断形成先 true、后 false 的分区，并寻找首个 false 的位置。它解决 boundary search（边界查找），不直接证明那里存在一个与 key 等价的元素。全范围按同一关系排序，是让多次查询都满足分区条件的一种常用组织。

因此 membership test（成员存在性判断）还需要两步：确认结果不是 end，再按同一 key relation 检查等价。仅检查未到 end 会把缺口映射到后继；仅检查值相等却先解引用 end，又会违反访问前提。把算法的 postcondition 拆成这两项，比背一句“二分查找返回迭代器”更能指导 wrapper 的实现和测试。[N4950：lower_bound](https://timsong-cpp.github.io/cppwp/n4950/lower.bound)

### 1.2 在整数 key 上建立完整查询

假设数据按编号递增排列。查询 103 时，二分查找可以反复排除一半范围；查询不存在的 102 时，同样可以找到“第一个不小于 102 的位置”，也就是 103 所在的位置。这是合法的边界结果，不是编号相等的证明。

`lower_bound` 要求范围相对于本次比较表达式已经分区。有序序列是满足反复查询的常见安排，但单次调用的前提并不是“函数会帮忙排序”。对未满足前提的范围调用它，再观察结果是否凑巧正确，没有验证价值。[lower_bound 的前提和返回值](https://timsong-cpp.github.io/cppwp/n4950/lower.bound)

**完整实验 `ordered-lookup.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <iostream>
#include <optional>
#include <span>
#include <vector>

// rows must be sorted by id with unique ids; return a value, not a retained borrow.
std::optional<Reading> find_reading(std::span<const Reading> rows, int id) {
    auto it = std::ranges::lower_bound(rows, id, {}, &Reading::id);
    if (it == rows.end() || it->id != id) return std::nullopt;
    return *it;
}

int main() {
    std::vector<Reading> rows{{105, 50, false}, {101, 10, true}, {103, 30, true}};
    std::ranges::sort(rows, {}, &Reading::id);
    const Reading expected[]{{101, 10, true}, {103, 30, true}, {105, 50, false}};
    if (!std::ranges::equal(rows, expected)) return 1;
    if (find_reading(rows, 103) != std::optional{Reading{103, 30, true}}) return 2;
    if (find_reading(rows, 102).has_value()) return 3;
    if (find_reading(rows, 100) || find_reading(rows, 106)) return 4;
    if (find_reading({}, 101)) return 5;
    auto snapshot = find_reading(rows, 101);
    rows[0].value = 99;
    if (!snapshot || snapshot->value != 10) return 6;
    std::cout << "ordered lookup checks both boundary and key equality\n";
}
```

预期输出为 `ordered lookup checks both boundary and key equality`。测试既查询命中，也查询两个已存在编号之间的缺口、首项之前、末项之后和空范围。缺口测试尤其重要：删掉编号比较后，102 会错误地得到 103；即使全部访问都合法，结果也不符合查询合同。

这里的返回值是 `optional<Reading>`，复制一条很小的记录，让查询结果独立于后续修改。它只表达“找到或未找到”，不表示所有可能失败都已转为值；例如查询之前建立大容器仍可能分配失败。若 Reading 变成大对象，可以重新选择返回借用的 API，但必须把有效期写进合同，不能只为了省复制就默认保存内部地址。

<a id="11-排序依据必须与查询依据一致"></a>

### 1.3 排序依据必须与查询依据一致

本例按整数 id 排序并用相同投影查找。若改用自定义比较器，等价通常由 `!comp(a, b) && !comp(b, a)` 定义，不必等同 `operator==`。本例的 `it->id != id` 适用于当前整数顺序，不能原封不动套到大小写折叠或其他归一化键。

同理，把序列按 value 排序后继续按 id 做二分查询，破坏了前提；只修改 value 不破坏 id 顺序，只修改某个 id 则可能破坏它。一个接口若允许调用方任意修改排序键，就把维护有序性的责任泄露到了每个调用点。下一节的关联容器以及最后的封装，都在控制这项修改权限。

## 2 map 把键关系纳入容器不变量

如果每次增删后都需要有序查询，可以让 `map<int, Reading>` 维护键顺序。这里 map 的键是编号；若 mapped value 再含一份 Reading.id，还需要保证两者一致。容器只维护自己的 key，不会自动检查用户值中的重复字段，所以真实设计也可以只在 mapped value 中保存读数与状态。

关联容器的唯一性依据比较等价关系，而不是固定调用 `==`。其元素 key 不能经普通迭代器直接改写，正是为了避免绕过排序关系；合法的改键要通过对应操作重新参与容器组织。本章不展开 node handle 的完整转移协议。[关联容器要求](https://timsong-cpp.github.io/cppwp/n4950/associative.reqmts)

另一个重要区别是查询与更新。`find` 或 `contains` 不插入缺失项；`at` 缺失时抛 `out_of_range`；`operator[]` 缺失时会尝试建立 mapped value。把 `table[id]` 放进日志或只读查询路径，可能悄悄改变状态，甚至发生分配。下面用小值避免昂贵构造掩盖这项语义。

**完整实验 `map-operations.cpp`**

```cpp
#include <iostream>
#include <map>

int main() {
    std::map<int, int> values{{101, 10}, {103, 30}};
    const auto original_size = values.size();
    if (values.find(102) != values.end() || values.contains(102)) return 1;
    if (values.size() != original_size) return 2;
    auto [position, inserted] = values.try_emplace(103, 99);
    if (inserted || position->second != 30) return 3;
    auto [updated, added] = values.insert_or_assign(103, 33);
    if (added || updated->second != 33 || values.size() != original_size) return 4;
    int created = values[102];
    if (created != 0 || values.size() != original_size + 1) return 5;
    if (values.at(101) != 10 || values.at(103) != 33) return 6;
    std::cout << "lookup, conditional insertion and replacement are distinct\n";
}
```

输出为 `lookup, conditional insertion and replacement are distinct`。`try_emplace` 在键已存在时不从传入参数构造新的 mapped value，`insert_or_assign` 则明确更新已有值；它们返回的 bool 说明是否发生插入，不能把 false 一律解释为失败。[map 更新操作](https://timsong-cpp.github.io/cppwp/n4950/map.modifiers)、[map 元素访问](https://timsong-cpp.github.io/cppwp/n4950/map.access)

不过 `try_emplace(id, expensive_function())` 仍然必须先求值函数实参。需要“键已存在就连准备都不做”时，要另行设计准备边界；容器不能撤销发生在调用之前的工作。并发场景还不能把一次独立 `find` 加一次插入自动视为原子操作，那是 G7 的问题。

## 3 unordered_map 改变查找组织，也改变失效条件

散列容器用哈希值选择桶，再通过键等价关系判断是否匹配。相等键必须得到相同哈希；哈希相同不代表键相等，碰撞仍要比较。对仍保存在同一容器中的键，哈希和等价关系需要保持一致；不能一边修改比较依赖的外部状态，一边期待已有桶布局自动更新。[无序关联容器要求](https://timsong-cpp.github.io/cppwp/n4950/unord.req)

rehash 重新组织桶，会使迭代器失效，但不使已有元素的指针和引用失效。这个区分与 deque 类似：遍历状态还依赖容器的组织方式，不只是元素地址。平均常数时间查询也不等于固定耗时，最坏情况仍可线性；本章不根据复杂度符号判定它一定比有序 vector 或 map 快。

**完整实验 `hash-references.cpp`**

```cpp
#include "reading.hpp"
#include <iostream>
#include <unordered_map>

int main() {
    std::unordered_map<int, Reading> table;
    table.emplace(101, Reading{101, 10, true});
    table.emplace(103, Reading{103, 30, true});
    Reading* saved = &table.at(103);
    const auto before = table.bucket_count();
    if (before == table.max_bucket_count()) return 1;
    table.rehash(before + 1);
    if (table.bucket_count() <= before || table.size() != 2) return 2;
    if (saved != &table.at(103) || *saved != Reading{103, 30, true}) return 3;
    auto current = table.find(103); // Acquire a new iterator after rehash.
    if (current == table.end() || &current->second != saved) return 4;
    if (table.erase(101) != 1 || table.size() != 1 || saved->id != 103) return 5;
    std::cout << "rehash renews iterators but preserves element references\n";
}
```

输出为 `rehash renews iterators but preserves element references`。程序没有保留旧迭代器做比较，也不检查某个固定桶数或遍历顺序。擦除 101 不影响借用的 103；若擦除 103，就必须停止使用 saved。

使用字符串键时还要回到 G1/G2 的拥有模型。`unordered_map<string_view, ...>` 复制的是视图，不是字符。原字符串释放会造成悬挂；原字符串即使仍活着，修改内容也可能改变已经入表的键的哈希或等价关系。选择拥有字符串的 key，或提供明确的不变存储及生命合同，才能使索引假设成立。仅把 map 对象保存得足够久并不够。

## 4 一份序列加一份索引，需要共同提交

### 4.1 Representation invariant 必须覆盖两个容器之间的关系

索引是从主数据推导出来的表示，不是另一份可以独立宣称正确的真相。对当前唯一编号、整体替换合同，令 rows 有 n 项，则有效状态要求：index 也恰有 n 个条目；对每个合法 i，`index[rows[i].id] = i`；所有 rows 的 id 不重复。这里的下标表达式是数学关系说明，不是在证明过程中通过 map 的 `operator[]` 插入数据。

这组条件使正向查询、完整覆盖和无额外条目同时成立。只检查每个 index value 在 `[0, n)` 内不够，因为它仍可能指向错误记录；只验证几个命中的查询也不够，因为可能漏掉一个未查编号。**组件 invariant 不等于成员 invariant 的简单并集**，关系本身需要初始化、每次更新和失败路径共同保持。

### 4.2 把关系更新放进同一个 commit boundary

业务既想保留接收顺序，又要反复按编号查询，可以保留 vector，并维护 `id → 下标` 的索引。它没有消除第一单元的位置变化，只是把变化的跟踪责任集中到一个组件里。核心不变量是：每条记录的编号恰好对应它当前的下标，索引中也没有指向别的记录的额外条目。

如果先排序 vector，再逐项更新索引，中途失败时可能留下“序列是新顺序、索引还是旧顺序”。两个标准容器各自有效，组件仍然错误。类似地，用下标而不是裸指针可以避免某些存储搬迁问题，却不能自动解决擦除或排序后的业务错位。

本例选择一个受限而容易审查的合同：整批替换，不开放原地增删和键修改；准备阶段先建完整新状态，重复编号拒绝；成功后一次交接 owner。所有查询同步执行，无并发读写。为了明确生命和提交边界，状态存放在 unique_ptr 管理的对象中，而不是让两个成员分别提交。

**完整实验共用文件 `indexed-batch.hpp`**

```cpp
#ifndef G4_INDEXED_BATCH_HPP
#define G4_INDEXED_BATCH_HPP
#include "reading.hpp"
#include <cstddef>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <vector>

class IndexedBatch {
    struct State {
        std::vector<Reading> rows;
        std::unordered_map<int, std::size_t> index;

        explicit State(std::vector<Reading> input) : rows(std::move(input)) {
            index.reserve(rows.size());
            for (std::size_t i = 0; i < rows.size(); ++i) {
                if (!index.emplace(rows[i].id, i).second)
                    throw std::invalid_argument("duplicate reading id");
            }
        }
    };

    std::unique_ptr<State> state_ = std::make_unique<State>(std::vector<Reading>{});

public:
    IndexedBatch() = default;
    IndexedBatch(const IndexedBatch&) = delete;
    IndexedBatch& operator=(const IndexedBatch&) = delete;
    IndexedBatch(IndexedBatch&&) = delete;
    IndexedBatch& operator=(IndexedBatch&&) = delete;

    void replace(std::vector<Reading> input) {
        auto next = std::make_unique<State>(std::move(input));
        state_ = std::move(next);
    }

    std::optional<Reading> find(int id) const {
        auto it = state_->index.find(id);
        if (it == state_->index.end()) return std::nullopt;
        return state_->rows.at(it->second);
    }

    std::span<const Reading> rows() const { return state_->rows; }
};

#endif
```

`State` 构造失败时，已经构造的 rows、index 及其中的元素由语言和标准库负责清理，旧 state_ 没有参与准备。成功以后 unique_ptr 的移动赋值接管新状态，并销毁旧状态；本例使用默认删除器，成员析构不抛异常。因此提交点之后两份结构来自同一次准备，不会出现一半新、一半旧的状态。

这里显式删除复制和移动，是为了把实验范围限定到整体替换；否则默认移动会使源 state_ 为空，还需要定义源对象方法的合法调用范围。我们不为本章顺便添加第二套值语义实现。容器和智能指针承担了清理工作，组件只负责它们之间的关系。

<a id="41-失败后旧批次仍在不等于调用方输入未变"></a>

### 4.3 失败后旧批次仍在，不等于调用方输入未变

replace 按值接收输入：调用方给左值时复制，给右值时可以移动。即使新 State 因重复编号而构造失败，调用方用于交付的原对象也可能已经被移出。这里的保持原值保证针对 IndexedBatch 的旧状态，不自动覆盖全部实参。

此外，输入参数的构造、分配新 State、vector 或索引分配都可能抛异常；本例没有把所有异常转换为 optional。find 的 optional 只表达查询缺失，`.at()` 还会对错误下标抛异常，但即使下标在范围内，也不能据此证明编号映射正确。正确性仍依赖建立过程的不变量。

<a id="42-同时检查正向结果与失败后的关系"></a>

### 4.4 同时检查正向结果与失败后的关系

**完整实验 `indexed-replacement.cpp`**

```cpp
#include "indexed-batch.hpp"
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string_view>

int main() {
    IndexedBatch batch;
    if (!batch.rows().empty() || batch.find(101)) return 1;
    batch.replace({{103, 30, true}, {101, 10, true}});
    const Reading first[]{{103, 30, true}, {101, 10, true}};
    if (!std::ranges::equal(batch.rows(), first) ||
        batch.find(101) != std::optional{Reading{101, 10, true}}) return 2;
    {
        auto borrowed = batch.rows();
        bool rejected = false;
        try { batch.replace({{105, 50, true}, {105, 55, false}}); }
        catch (const std::invalid_argument& e) {
            rejected = std::string_view(e.what()) == "duplicate reading id";
        }
        if (!rejected || !std::ranges::equal(batch.rows(), first)) return 3;
        if (borrowed.data() != batch.rows().data() ||
            !std::ranges::equal(borrowed, first) || batch.find(105)) return 4;
        if (batch.find(103) != std::optional{Reading{103, 30, true}}) return 5;
    }
    batch.replace({{101, 11, false}, {103, 33, true}, {107, 70, true}});
    const Reading next[]{{101, 11, false}, {103, 33, true}, {107, 70, true}};
    if (!std::ranges::equal(batch.rows(), next) ||
        batch.find(103) != std::optional{Reading{103, 33, true}} ||
        batch.find(107) != std::optional{Reading{107, 70, true}}) return 6;
    if (batch.find(102)) return 7;
    batch.replace({});
    if (!batch.rows().empty() || batch.find(101)) return 8;
    std::cout << "rows and index commit together; rejected input preserves old state\n";
}
```

输出为 `rows and index commit together; rejected input preserves old state`。测试覆盖空状态、乱序输入、重复键拒绝、失败后旧借用及全部旧值保留、位置改变后的查询、缺失键、成功清空。失败发生在真实的重复键检查处，不是模拟操作系统内存不足；分配失败路径仅作机制分析，本批没有定向注入。

rows 返回的 span 只允许借用到下一次成功替换或组件销毁前；失败的准备没有改变旧状态，所以例中的旧借用仍有效。成功替换后旧状态销毁，不能再访问旧 span。例子用局部作用域减少误用，但这不是运行时借用登记。

## 5 查询结构的收益要与维护代价一起计算

| 表示 | 本章适用情形 | 必须维护的关系 |
| --- | --- | --- |
| 未排序 vector | 少量或偶发查询，保留输入顺序 | 逐项查找，不能假定二分前提 |
| 按键排序的 vector | 集中构建，反复只读查询 | 排序键、重复键策略、修改后重排 |
| map | 持续更新并需要键顺序 | 比较等价关系、键修改边界 |
| unordered_map | 以等值查找为主 | 哈希与等价一致、rehash 的失效规则 |
| 序列加索引 | 顺序与查询组织需要分离 | 两份结构及其共同提交 |

二分查询的比较次数可以是对数级，但若使用非随机访问迭代器，走到中间位置本身仍可能需要线性数量的迭代器递增。成员 `map::lower_bound` 能利用容器内部组织，不等价于对 map 的迭代器调用通用算法。复杂度要明确计数对象，不能只看函数名。[二分算法复杂度说明](https://timsong-cpp.github.io/cppwp/n4950/alg.binary.search)

C++23 的 flat_map 为有序平坦存储提供标准接口，但其默认表示分开保存 key 和 mapped value，不是固定的 `vector<pair>`；其代理引用和底层序列要求也应单独处理。当前有序 vector 足以建立查询模型，flat_map 的完整使用、库支持差异和测量先保留在[旧 G4 回查](../g04-stl-and-ranges.md#g4-part-xvi)，不在这里未经验证地替换组件。[flat_map 表示](https://timsong-cpp.github.io/cppwp/n4950/flat.map.overview)

本例整体替换的代价包括新旧两份状态同时存在、重新建立全部索引和成功后的借用失效。若产品需要高频单项更新、持久稳定句柄或并发快照，应重新选择合同；不能只给 replace 加一把锁就宣称所有外部 span 都安全。G7/G10 再讨论跨线程使用，G6 再度量这些表示的实际成本。

## 6 用变化后的条件检验模型

### 6.1 迁移问题

1. lower_bound 返回非 end，为什么仍可能是缺失键？需要什么输入才能抓住省略相等检查的错误？
2. 给 map 自定义大小写无关比较后，键唯一性还按普通字符串 `==` 判断吗？
3. `try_emplace` 没插入新键，昂贵实参函数却已经运行，是否是标准库错误？
4. unordered_map rehash 后元素指针仍可用，能否继续递增旧迭代器？
5. 将索引的地址改成下标，为什么仍不能在排序后原样保留？
6. replace 接收右值以后发现重复键，组件保持旧状态，是否意味着调用方交付的 vector 也保持原值？

### 6.2 推理与修正

**第一题。** 边界可能指向下一个更大的键。应测两个现有键之间的缺口，并继续测首前、尾后和空范围；只测命中与末尾缺失会遗漏最典型错误。

**第二题。** 不再必然如此。唯一性依据比较器诱导的等价关系；查询、去重和插入必须使用相容规则。忽略这一点可能把业务认为相同的键保存两次，或错误地合并不同身份。

**第三题。** 不是。实参求值发生在进入函数之前；条件插入只约束容器内部是否构造并插入 mapped value。准备成本需要在调用边界之外单独安排。

**第四题。** 不能。指针指向元素，迭代器还承担遍历组织关系；rehash 的合同分别规定了两者。应重新取得迭代器，不能用某次实现仍可递增来否定失效规则。

**第五题。** 下标仍可能合法，但已对应别的编号。索引不变量包含 id 与当前位置的对应，不只是整数是否小于 size。更新序列必须同时维护索引，或者重建并一起提交。

**第六题。** 不意味着。实参可能已经移入形参，再移入准备中的状态。组件保证保护的是旧 state_；调用方输入的移动后状态由那次交付操作决定，不能把局部强保证扩张到整个调用环境。

G4 至此把容器、算法与视图连接到 G1～G3 的对象、借用和值模型。接下来 G5 研究这些接口背后的类型推导、约束和实例化；不需要在进入泛型之前先背完标准库所有容器名。
