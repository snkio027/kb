# G4 序列修改与记录身份

G3 已经解释了怎样复制一批读数、把结果交给调用方，以及移动以后由谁持有存储。现在让这批数据持续变化：接收新读数、插入迟到记录、删除无效项，再按另一种顺序展示。问题不再只是一项操作是否得到正确的值，还包括原先取得的指针、位置和记录编号能否继续使用。

本单元从 `vector` 的具体修改开始，再讨论何时值得改变存储表示。[第二单元](g04-algorithms-and-views.md)处理算法和惰性视图，[第三单元](g04-lookup-and-indexes.md)处理按键查找与索引一致性。完整实验使用 C++23；工具链、命令和结果集中在 [G4 验证说明](g04-verification.md)。这里不测容器速度，也不重新实现 G3 的资源包装。

## 1 一条记录同时具有值、位置和身份

原来的整数序列只回答“第几个数是多少”。现在给每条读数增加业务编号和有效标记。编号在同一批内唯一；本单元由输入保证，第三单元再讨论重复编号怎样处理。编号不是地址，也不是自动生成的稳定句柄，只是我们约定用来认出同一条业务记录的键。

本单元所说的记录身份由业务编号 `id` 表达，不等同于 C++ 对象身份。对这里的 `Reading`，给已有元素赋入另一条记录的值，不需要结束该元素对象的生命周期，却会改变它所代表的业务记录。因此，“还是同一个元素对象”和“还是同一条记录”必须分别判断。

下面是三个单元共用的完整头文件。`Reading` 的全部成员共同组成值，默认相等比较检查全部字段，不能只比较编号就宣称两批数据完全一致。这里用整数读数排除浮点特殊值，使首次推理集中在序列关系上。

**完整实验共用文件 `reading.hpp`**

```cpp
#ifndef G4_READING_HPP
#define G4_READING_HPP

struct Reading {
    int id;
    int value;
    bool valid;
    bool operator==(const Reading&) const = default;
};

#endif
```

设一批数据依次包含编号 101、103、105。下标 1 目前对应 103，`&rows[1]` 目前可以访问那个元素，而 `id == 103` 是一项业务判断。这三种定位恰好重合，不代表以后始终重合。插入一条 102 后，103 可以保持原值，却移动到下标 2；重新分配后，103 仍在序列里，旧元素借用却不能继续使用。

因此每次修改都需要分别追问：结果值是什么，位置是否改变，旧访问路径是否有效。G1 的[借用模型](g01-borrowing-and-invalidation.md)已经说明合法地址和业务身份不能混同；G4 要把这个区分用于选择具体操作，而不是再背一张孤立的失效表。

## 2 容量为修改提供空间，不替修改提供全部保证

`reserve` 告诉 vector 预计需要的容量，不增加序列元素；`resize` 才改变元素个数。预留容量后直接把 `begin()` 当作任意数量输出元素的写入位置，仍然不成立。要么先建立元素再赋值，要么让插入操作建立新元素。

对一批数量可估计的输入，先预留一次合理容量有助于减少重新分配。不要在每次追加前都机械调用 `reserve(size() + 1)`：这会干预实现原有的容量增长策略，在某些实现和工作负载中造成反复搬迁。标准没有承诺容量一定翻倍，`shrink_to_fit` 也只是收缩请求，不能把它作为确定释放全部多余容量的合同。[vector 容量操作](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity)

### 2.1 先读一个有明确修改阶段的程序

下面的程序预留足够空间，分别做末尾追加、中间插入和按条件删除。它只保留修改点之前的借用，并在插入或删除后使用新返回的迭代器。源文件与头文件放在同一目录。

**完整实验 `sequence-edit.cpp`**

```cpp
#include "reading.hpp"
#include <algorithm>
#include <iostream>
#include <span>
#include <vector>

int main() {
    std::vector<Reading> rows{{101, 10, true}, {103, 30, true}};
    rows.reserve(8);
    const auto capacity = rows.capacity();
    auto* first = &rows.front();
    {
        std::span<const Reading> prefix{rows};
        rows.push_back({105, 50, false});
        if (prefix.size() != 2 || prefix[1].id != 103) return 1;
        if (rows.size() != 3 || rows.capacity() != capacity) return 2;
    }

    auto inserted = rows.insert(rows.begin() + 1, Reading{102, 20, false});
    const Reading after_insert[] = {
        {101, 10, true}, {102, 20, false}, {103, 30, true}, {105, 50, false}
    };
    if (!std::ranges::equal(rows, after_insert)) return 3;
    if (inserted != rows.begin() + 1 || inserted->id != 102) return 4;
    if (first != &rows.front() || first->id != 101) return 5;

    for (auto it = rows.begin(); it != rows.end();) {
        if (!it->valid) it = rows.erase(it);
        else ++it;
    }
    const Reading kept[] = {{101, 10, true}, {103, 30, true}};
    if (!std::ranges::equal(rows, kept) || rows.capacity() != capacity) return 6;
    if (first != &rows.front() || first->value != 10) return 7;
    std::cout << "sequence edits preserve values and renew positions\n";
}
```

运行方式如下，其他正常程序也各自独立编译，不把多个 `main` 链接到一起：

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic sequence-edit.cpp -o sequence-edit
./sequence-edit
```

预期输出为 `sequence edits preserve values and renew positions`。比较使用完整范围和全部字段，所以漏删尾项、把 103 的值交给 102、只留下第一个元素，都不能满足判据。

### 2.2 为什么末尾追加与中间插入不同

第一次追加没有超过容量，原有两个元素的借用仍可用，但 `prefix` 仍只有两个元素。它是当时取得的范围描述，不是容器的实时订阅；旧 `end()` 也不能因未重新分配就继续沿用。

中间插入虽然也没有重新分配，却必须为 102 腾出位置。插入点之前的借用保持有效；插入点及之后的旧指针、引用、迭代器，包括尾后迭代器，都按失效处理。因此程序只继续使用指向 101 的 `first`，定位新元素则使用 `insert` 的返回值。[vector 插入合同](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers)

实现通常会在尚未使用的末端存储构造元素，并通过赋值调整已有位置。不能把所有中间插入都画成“全体析构再构造”，也不能从某个元素地址未变推出它仍代表旧记录。对有资源成员的类型，构造和赋值可能具有不同成本与异常行为，这正是 G3 区分两者的用途。

`emplace_back` 可以直接用参数构造新增元素，但它不会取消容量条件。新增元素不必先形成一个临时 Reading，与原有全部元素是否因重新分配而搬迁，是两个问题。把 push_back 换成 emplace_back，不能据此继续使用本来已经失效的借用，也不能直接得出“整个调用零复制”的结论。

### 2.3 删除时为何接住返回的迭代器

`erase` 后，删除位置及其后的旧迭代器和引用失效。返回值指向新的后继，删除末项时返回新的终点。循环若在删除后又无条件递增，会跳过刚移到当前位置的元素；若继续递增旧迭代器，则已经违反接口合同。

程序每次重新取 `rows.end()`，而不是保存删除前的终点。101 始终位于所有删除点之前，所以它的借用可保留；这是一项针对当前操作顺序的证明，不是对 vector 的永久承诺。也不要仅通过“ASan 没报警”判断旧迭代器可用：其地址可能仍落在已分配存储里，工具未必识别容器层的失效。

## 3 重新分配把 G3 的复制与移动变成容器问题

当容量不够时，新存储必须容纳原有值。对 `int`，读者容易把这想象成复制一段字节；对拥有资源的类，vector 需要遵守元素类型及容器操作的要求。旧对象和新对象处在不同存储上，G3 中复制建立独立值、移动交接资源的差异，现在决定失败后能留下什么状态。

考虑两个元素类型：一个移动构造声明不抛异常；另一个允许抛异常，但仍可复制。若移动旧元素到一半失败，部分源元素可能已被改动，恢复原值未必容易。复制旧元素则可以让旧值继续存在，直到准备完成。常见实现因此在这种情况下采用复制；然而标准规定的是条件化保证，不是要求所有实现逐字调用 `std::move_if_noexcept`。

对 `reserve`，除不可 CopyInsertable 类型的移动构造抛异常这一例外外，异常应不产生影响。如果元素不满足 CopyInsertable，且搬迁时移动构造抛异常，该情形不再享有上述无效果保证，不能假定失败后仍保留原值。[reserve 的异常保证](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity#4)

这里的 CopyInsertable 对应标准的 Cpp17CopyInsertable，是元素相对于该容器及其 allocator 的复制插入要求，不仅是“有一个名字叫复制构造的函数”。这不是“所有 vector 操作都有强保证”：中间插入、赋值搬移和只能抛异常移动的类型，必须分别查相应条款。`noexcept` 也不能随意添加以诱导容器移动；错误承诺会把抛异常变成终止。

### 3.1 用构造计数观察实现选择

下面只改变移动构造的异常规格。两种类型的移动实现实际上都不抛异常；计数器用于观察本机库的选择，不能证明真实 throwing-move 路径。数组里仅有三个整数负载，构造次数也不能换算成性能收益。

**完整观察实验 `relocation-observation.cpp`**

```cpp
#include <iostream>
#include <utility>
#include <vector>

template<bool NoThrow>
struct Element {
    int value;
    static inline unsigned copies = 0;
    static inline unsigned moves = 0;
    explicit Element(int n) : value(n) {}
    Element(const Element& other) : value(other.value) { ++copies; }
    Element(Element&& other) noexcept(NoThrow)
        : value(std::exchange(other.value, -1)) { ++moves; }
};

template<bool NoThrow>
bool observe(const char* label) {
    using T = Element<NoThrow>;
    std::vector<T> rows;
    rows.reserve(3);
    for (int n : {10, 20, 30}) rows.emplace_back(n);
    const auto capacity = rows.capacity();
    if (capacity == rows.max_size()) return false;
    T::copies = T::moves = 0;
    rows.reserve(capacity + 1);
    if (rows.size() != 3 || rows.capacity() <= capacity) return false;
    if (rows[0].value != 10 || rows[1].value != 20 || rows[2].value != 30)
        return false;
    std::cout << label << " copies=" << T::copies << " moves=" << T::moves << '\n';
    return true;
}

int main() {
    if (!observe<true>("nothrow")) return 1;
    if (!observe<false>("potentially-throwing")) return 2;
}
```

实验以 `capacity() + 1` 明确触发成功的重新分配，不猜增长倍数，也不读取旧元素地址。退出码检查的是完整值和容量后置条件；输出记录两种类型各自的复制、移动次数。执行器不把“必须是 0 次复制、3 次移动”设为跨实现判据，实际数字见验证记录。

本例没有注入分配失败或元素复制失败，没有统计析构、分配器内部操作，也未验证一般 allocator。G3 的故障注入证明的是那个手写 Batch 的提交边界，不能直接继承成 vector 的所有异常路径实测。

## 4 排序改变顺序，不替你追踪业务记录

中间删除之后不能保留受影响的旧迭代器；排序暴露的是另一个问题。对这里的 `vector<Reading>`，排序不要求 vector 重新分配，也不改变大小，但算法会交换或移动赋值元素的值。原来指向某个位置的有效引用，可能读到另一条编号记录。

“稳定排序”也没有解决这件事。稳定性（stability）表示比较等价的元素保留原有相对顺序，不表示地址、下标或全部记录的位置不变。下一单元用投影与重复排序键验证这个区别。

如果界面选中了编号 103，跨排序保存“下标 1”就把业务身份绑定到了位置；保存编号，再按当前批次查找，是另一种合同。若编号会在不同批次复用，还需要批次身份或代际信息。仅有一个整数 ID 不足以解决删除后重建的全部问题，本章不因此引入通用句柄池。

## 5 要保留地址时，改变哪一层存储

一种办法是让 vector 保存独占指针，把可移动的句柄与需要稳定地址的 Reading 分开。vector 重新分配时改变的是句柄的位置；只要目标对象未被销毁或替换，指向目标的借用仍可使用。代价是独立分配、间接访问以及更复杂的清理关系，不能因此宣布这种表示“更高级”。

`deque` 和 `list` 提供不同的操作合同。deque 在两端插入时保留已有元素引用，却使迭代器失效；它不能当作一个连续数组交给 span。list 支持节点操作和成员排序，已有元素的引用与迭代器可按其具体合同保留，但按序号定位需要遍历。[deque 修改规则](https://timsong-cpp.github.io/cppwp/n4950/deque.modifiers)、[list 成员操作](https://timsong-cpp.github.io/cppwp/n4950/list.ops)

**完整实验 `stable-storage.cpp`**

```cpp
#include "reading.hpp"
#include <deque>
#include <iostream>
#include <list>
#include <memory>
#include <vector>

int main() {
    std::vector<std::unique_ptr<Reading>> owned;
    owned.push_back(std::make_unique<Reading>(Reading{103, 30, true}));
    Reading* record = owned.front().get();
    if (owned.capacity() == owned.max_size()) return 1;
    owned.reserve(owned.capacity() + 1);
    if (record != owned.front().get() || record->id != 103) return 2;

    std::deque<Reading> queue{{103, 30, true}};
    Reading& middle = queue.front();
    queue.push_front({101, 10, true});
    queue.push_back({105, 50, true});
    if (&middle != &queue[1] || middle.id != 103) return 3;

    std::list<Reading> nodes{{103, 30, true}, {101, 10, true}};
    auto saved = nodes.begin();
    Reading* address = &*saved;
    nodes.sort([](const Reading& a, const Reading& b) { return a.id < b.id; });
    if (saved->id != 103 || &*saved != address || nodes.front().id != 101)
        return 4;
    std::cout << "target identity follows the chosen storage contract\n";
}
```

这里没有沿用 deque 的旧迭代器；list 的排序是成员操作，不是下一单元要求随机访问的 `ranges::sort`。实验比较的也是仍有效的对象地址，没有尝试比较已失效的 vector 元素指针。

三种表示都不能保护已删除目标。若擦除唯一 owner，裸指针不会替它延寿；若另一个线程同时访问，还需要 G7 的同步和生命周期协议。“地址稳定”只解决一项约束，不能代替拥有关系、并发一致性或业务身份。

## 6 用操作合同选择表示

| 当前主要需求 | 可以考虑的起点 | 仍需承担的约束 |
| --- | --- | --- |
| 连续遍历，集中修改后再读取 | `vector<Reading>` | 修改阶段结束后重取借用 |
| 数量固定，整体随对象存在 | `array<Reading, N>` | 长度固定，排序仍改变位置对应的值 |
| 两端增长，保留已有元素引用 | `deque<Reading>` | 迭代器失效，不能假定连续存储 |
| 节点身份与成员重排操作重要 | `list<Reading>` | 无常数时间随机定位，遍历代价另测 |
| 顺序可变，目标地址需独立稳定 | `vector<unique_ptr<Reading>>` | 目标生命、分配与间接访问 |

这不是速度排行榜。顺序遍历、中间更新、查找次数、借用持续时间和内存预算共同决定选择。复杂度描述操作量怎样随规模变化；具体耗时还取决于元素大小、局部性、分配器与工作负载，测量方法留给 G6。

一个实用的起点是明确阶段边界：收集和修改期间不把元素借用交给长寿命消费者；修改完成后形成只读处理范围；下一轮修改之前结束这些使用。它不是 C++ 自动实施的借用检查，只是把接口合同组织得更容易遵守。若业务确实需要边修改边保留访问，再为那些具体操作选择更强的稳定性合同。

## 7 用变化后的条件检验模型

### 7.1 迁移问题

1. vector 已预留一万项容量，为什么在中间插入一条记录后仍不能沿用全部旧迭代器？
2. 界面保存了某条记录的下标，稳定排序后显示了另一条记录。是否说明排序算法违反了稳定性？
3. 将元素改成只有可能抛异常的移动、没有复制能力的类型，能否沿用“扩容失败必定保持原值”？
4. vector 保存 unique_ptr，外部保存 Reading 指针。扩容、排序和擦除唯一 owner 对这条指针分别意味着什么？
5. 用 list 避免元素搬迁以后，为什么还不能断言所有查找更快？
6. 删除循环用 `it = erase(it)` 后又执行 `++it`，即使没崩溃，可能遗漏什么？

### 7.2 推理与修正

**第一题。** 容量只排除了这次重新分配。插入点及之后的位置仍要调整，标准明确使相应访问路径失效。保留插入点之前的借用与重新取得受影响区域的迭代器，是两项不同处理。

**第二题。** 没有。稳定性只保留比较等价元素的相对顺序；记录仍然可能移动到另一个下标。应保存业务键并在当前序列中查找，或采用明确支持所需身份稳定性的表示。

**第三题。** 不能。类型落入 reserve 的例外边界，部分源元素可能已经被移动；不能将可复制类型或不抛移动类型的失败恢复结论照搬过来。要回到具体操作和元素能力的合同，而不是只看容器名。

**第四题。** 对正常的句柄搬移与排序，独立 Reading 对象可以仍在原处，外部指针继续指向它；擦除最后且唯一的 owner 会结束目标生命，此后不得访问。句柄自身的迭代器与目标指针需要分别判断。

**第五题。** 地址稳定不等于定位成本低。按序号或任意值查找仍可能逐节点遍历，间接访问也有机器成本。只有业务操作和规模明确以后，才能设计有意义的性能比较。

**第六题。** 返回的迭代器已经指向新的后继，再递增会跳过它；若删的是末项，还可能递增尾后迭代器。删除与未删除分支必须分别推进，而不是共用无条件递增。

现在我们已经知道修改怎样改变序列和借用。[第二单元](g04-algorithms-and-views.md)继续处理另一个层次：算法怎样使用这些访问能力，以及只描述一次未来遍历的 view 与独立结果有何区别。
