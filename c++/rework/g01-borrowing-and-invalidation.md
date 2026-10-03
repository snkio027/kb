# G1 借用、范围与访问失效

[第一单元](g01-storage-and-lifetime.md)研究了一个对象在同一块存储上的建立和结束。现在把读数收集成一批，交给另一个函数处理。调用方不想复制整批数据，接收方也不应负责释放它，于是双方通过指针、引用或 `std::span` 共享访问。

本书把“不拥有目标，只在约定期间通过某条路径访问目标”的关系称为借用（borrowing）。这是工程分析术语，不是 C++ 核心语言提供的一套借用检查机制。指针、引用和 `span` 只能表达其中一部分信息；目标的生命周期、允许的操作和失效条件，仍需由接口合同及其使用者保证。

问题随之变成：接收方什么时候还能使用这条访问路径？容器仍然存在，只说明容器对象本身没有结束生命；其中的元素可能已经搬到新存储、被删除，或者不再对应原来的逻辑记录。本单元用一批整数读数逐步改变这些条件，重点放在访问有效性，不展开容器的性能选型和类类型移动策略。

## 1 从单个地址到一段范围

假设我们收到四个整数读数，写成 `int samples[4]{10, 20, 30, 40};`。这里存在一个数组对象，其中有四个 `int` 元素子对象。数组占用的大小为 `4 * sizeof(int)`；不需要先假定一个 `int` 是四字节，才能理解其边界。

数组在很多表达式里可以转换为首元素指针。转换得到的 `int*` 仍然没有携带元素数：从 `samples` 得到的地址，可以用来访问首元素，却不会让接收方自动知道有四个元素。数组也没有因此变成一个指针对象；它仍在原地，转换只是产生了另一种表达式结果。[数组到指针的转换](https://timsong-cpp.github.io/cppwp/n4950/conv.array)

这解释了一个容易误读的接口：函数参数写成 `int values[100]`，不会要求每位调用者提供一百个元素。普通数组形参会调整为指针形参。若函数循环访问一百次，却收到四元素数组，形参拼写不能保护它。[函数参数类型的调整](https://timsong-cpp.github.io/cppwp/n4950/dcl.fct)

`std::span` 把连续范围所需的位置和长度作为一个接口传递。它仍然不拥有元素，但接收方不必再把一个指针和另一个容易写错的长度参数自行配对。下面用完整程序观察这种关系。

**文件 `array-span.cpp`**

```cpp
#include <iostream>
#include <span>
#include <type_traits>

// Synchronous read only; no retained view. The sum must be representable as int.
int sum(std::span<const int> values) {
    int result = 0;
    for (int value : values) result += value;
    return result;
}

int main() {
    int samples[4]{10, 20, 30, 40};
    static_assert(sizeof(samples) == 4 * sizeof(int));
    static_assert(std::is_same_v<decltype(samples), int[4]>);
    static_assert(std::is_same_v<decltype(&samples), int (*)[4]>);

    const std::span<int> const_view{samples};
    std::span<const int> readonly{samples};
    const_view[1] = 25;
    auto middle = readonly.subspan(1, 2);
    bool good = readonly.size() == 4 && readonly[1] == 25;
    good = good && middle.size() == 2 && middle[0] == 25 && middle[1] == 30;
    good = good && sum(readonly) == 105 && sum(middle) == 55;
    std::cout << "array sum=" << sum(readonly) << '\n';
    std::cout << "middle sum=" << sum(middle) << '\n';
    return good ? 0 : 1;
}
```

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic array-span.cpp -o array-span
./array-span
```

这里的和都能用 `int` 表示；示例不是处理任意长度、任意读数的防溢出聚合器。输出应为 `array sum=105` 和 `middle sum=55`。`middle` 指向中间两个已有元素，并没有另建一个独立的两元素数组。

### 1.1 const 限制的是哪一层

`const_view` 的 `const` 修饰 span 对象本身，而不是它的元素类型：这个 span 不能重新赋值，但元素类型仍是 `int`，所以仍可通过它修改元素。`readonly` 的元素类型是 `const int`，不能经由它执行同样的写入；不过它仍然看到别的合法路径刚写入的 25。

这与上一单元的 `const Reading*` 相同：限制一条访问路径，不等于冻结目标的所有别名。复制 span 通常复制的是范围描述，不是数据快照；若需要一个不会随后续修改而改变的独立值，应当明确复制数据或设计其他一致性机制。

### 1.2 长度信息不等于自动检查每次访问

C++23 的 `span::operator[]` 要求索引小于 `size()`；标准不保证它像抛异常的检查接口一样处理越界。某个标准库的加固模式可能提供额外诊断，但不能把这种配置当作所有 C++23 程序的保证。[span 元素访问](https://timsong-cpp.github.io/cppwp/n4950/span.elem)

范围还必须本来就有效。随意用一处地址和一个大数构造 span，既不会取得更多存储，也不会建立更多元素。类似地，尾后指针可以表示遍历终点，却不是一个可读取的元素；只能在所属数组及其允许的尾后范围内进行相应指针运算。

因此，span 让合同更容易表达，没有替调用者证明全部前提。接收方要尊重长度，提供方则要保证所描述的对象和范围真实有效。

## 2 借用承诺的是一次使用关系

### 2.1 Borrow contract：目标、操作与有效区间

本书把借用（borrowing）作为工程分析术语：borrower 获得某种访问能力，但不因此接管 release responsibility。要判断一次借用，至少需要知道目标是什么、通过什么类型和范围访问、允许哪些操作，以及哪段使用期间必须保持哪些条件。单独一个地址只表达其中很小一部分，`span<T>` 增加元素类型与长度，却仍未完整表达失效事件或跨线程协议。

例如 `sum(span<const int>)` 的 callee 需要的是读取一段现存整数；caller 负责在读取期间维持目标、范围与修改约束。这个合同可以允许 owner 在调用以后立即修改或销毁数据，因为 callee 不保留访问。若 callee 返回一个指向输入的 view，责任区间就跨过了返回点；“调用完成”不再是 caller 可以结束目标的依据。

有效区间也不只是一个结束时刻，它通常由事件限定：下一次 reallocation、相关位置的 erase、成功替换底层状态、owner 销毁。复制 view 不会把区间延长；让 view 自己比 owner 更早析构也不自动证明期间每次访问都合法。后面的实验正是在区分**包装对象仍存在**和**本次访问仍获合同允许**。

### 2.2 同步调用与延迟使用的不同义务

上例的 `sum` 采用同步读取合同：只在调用期间读取，不保存 span，不修改源数据。这种接口的要求较容易检查——调用期间四个元素必须活着，而且没有别的操作使它们失效。

如果把 span 保存成成员，或者捕获到稍后执行的任务里，时间范围就变了。函数返回并不意味着借用结束；实际使用可能发生在 owner 销毁、容器扩容或下一批数据覆盖之后。此时需要明确谁维持数据、哪些操作被冻结、何时释放这项约束。裸指针和 span 类型本身没有编码这些约定。

也不要把要求简化成“span 对象的生命周期一定比 owner 短”。一个不再访问元素的旧 span 可以留在作用域内；反过来，owner 明明还活着，借用也可能已经失效。真正需要逐次满足的是：**发生元素访问时，目标仍符合该访问路径和接口合同**。

这里还有一个临时对象陷阱。C++23 允许某些只读 span 从临时连续范围构造，例如把 `std::vector<int>{10, 20}` 用作 `std::span<const int>` 的来源。但临时 vector 通常在完整表达式结束时销毁，保存 span 不会延长它的生命；之后再访问元素就不能成立。[span 范围构造条件](https://timsong-cpp.github.io/cppwp/n4950/span.cons)允许构造某种表达式，不等于替它担保未来的生命周期。

对于函数新产生的一批数据，按值返回一个拥有元素的容器，与返回其局部容器的 span 是两种不同交付。前者把数据的拥有关系带给调用方，后者只留下了一个失去来源的访问路径。是否复制或省略构造是 G3 的问题，不能为了避免想象中的复制成本先选择悬挂借用。

## 3 vector 中有三种不同的存在

把固定数组换成 `std::vector<int>` 后，需要同时跟踪三个层次：vector 对象本身、它当前管理的存储、序列里已经存在的元素。

`size()` 描述序列有多少元素，`capacity()` 描述不要求重新分配就能容纳多少元素。对空 vector 调用 `reserve(4)` 后，容量至少为四，但序列仍然为空；这不授予 `samples[0]` 的访问资格。底层分配与隐式对象创建还有更低层的规则，本章不据此猜测所有底层对象的存在，只按容器接口确认 `[0, size())` 内的元素。

`push_back` 则真正增加元素。它如果超过原容量，需要重新分配；没有超过时，仍要依据具体操作的失效规则判断旧借用。容量是这项推理的条件之一，不是整个容器永远安全的证明。

### 3.1 Invalidation 是接口合同，不是探测地址是否可读

失效（invalidation）说明旧 pointer、reference 或 iterator 不能再按原接口承诺继续使用。其原因可能是目标 lifetime 结束、存储迁移，也可能是容器操作对位置关系作出了更强的失效规定。读取旧地址偶尔成功，至多说明那次机器访问没有显式故障，不能恢复已经失去的许可。

需要分别问三个问题：对象是否仍存在，旧访问路径是否仍有效，它是否仍表示想要的业务记录。前两项成立也未必保证第三项，例如对仍有效的位置赋入了另一条记录的值。这个区分将在 G4 发展成 value、position、object identity 与 record identity 的模型；在这里，它已经足以说明为什么 sanitizer 不能替接口设计证明“拿到的还是原来那条数据”。

## 4 在同一程序中改变容量条件

以下程序先预留空间并建立两个元素，再追加第三个；随后明确请求超过当前容量的空间，最后清空序列。所有分配均假设成功；若实际分配失败，实验失败而不是把异常当作正常结果。

**文件 `vector-borrows.cpp`**

```cpp
#include <algorithm>
#include <iostream>
#include <span>
#include <vector>

int main() {
    std::vector<int> samples;
    auto* owner = &samples;
    samples.reserve(4);
    if (!samples.empty() || samples.capacity() < 4) return 1;
    samples.push_back(10);
    samples.push_back(20);

    const auto reserved = samples.capacity();
    {
        int* first = &samples[0];
        std::span<const int> prefix{samples};
        samples.push_back(30); // Within reserved capacity, appended at the end.
        if (samples.capacity() != reserved || first != &samples[0]) return 2;
        if (*first != 10 || prefix.size() != 2 || prefix[1] != 20) return 3;
        std::cout << "append owner-size=" << samples.size()
                  << " borrowed-size=" << prefix.size() << '\n';
    } // Stop using these access paths before the invalidating operation.

    const auto before_growth = samples.capacity();
    if (before_growth == samples.max_size()) return 4;
    samples.reserve(before_growth + 1); // Successful call must reallocate.
    const int expected[]{10, 20, 30};
    if (&samples != owner || samples.capacity() <= before_growth) return 5;
    if (!std::ranges::equal(samples, expected)) return 6;
    std::span<const int> renewed{samples};
    if (renewed.size() != 3 || renewed[2] != 30) return 7;
    std::cout << "reallocated owner-alive size=" << renewed.size() << '\n';

    const auto retained = samples.capacity();
    samples.clear();
    // renewed is no longer used to access elements.
    if (!samples.empty() || samples.capacity() != retained) return 8;
    std::cout << "cleared size=" << samples.size() << "; capacity-retained\n";
}
```

本例的输出应为：

```text
append owner-size=3 borrowed-size=2
reallocated owner-alive size=3
cleared size=0; capacity-retained
```

### 4.1 没有重新分配，旧 span 也不会自动增长

第一次追加位于序列末尾，而且没有超过容量。已有两个元素的引用、指针保持有效；`prefix` 可以继续访问原来的两个元素，但它的长度仍为构造时的二。span 不订阅 vector 的大小变化，也不代表“从现在到以后一直跟随整个容器”。

这解释了一类看似奇怪的结果：程序没有悬挂访问，却漏处理了刚追加的元素。原因不是内存错误，而是保留了一个合法但较短的视图。若函数要处理当前整批数据，应在约定的时刻重新取得范围。

旧尾后迭代器也不能因没有重新分配就继续沿用。末尾插入改变了序列终点；“旧元素指针仍有效”和“全部旧迭代器都有效”不是同一句话。这里没有使用旧 `end()` 来冒险比较。[vector 插入的失效规则](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers)

### 4.2 重新分配保持数值，不保持旧借用

第二次 `reserve` 的参数是当前容量加一，而不是一个凭经验猜测的常量。若调用成功，它一定需要重新分配。我们不假定容量按两倍增长，也不靠打印出不同地址来决定是否失效。[vector 容量与 reserve 合同](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity)

可以把这次成功操作理解为：为新容量安排存储，在新位置建立这批元素，完成转移后结束旧元素并放弃旧存储。本例元素为 `int`，结果中的三个数必须保留；涉及类类型时的复制、移动选择和失败恢复，留给 G3 及失败语义专题。本节不对所有类型承诺同一种实现顺序。

```text
vector 对象：始终是 samples

操作前  samples ──> 旧存储中的 [10, 20, 30]
                       ↑ 旧的元素借用

操作后  samples ──> 新存储中的 [10, 20, 30]
                       ↑ 重新取得的借用
```

图中数值相同，不代表三个旧元素的访问路径自动跟随搬迁。重新分配会使旧元素的引用、指针和迭代器失效；使用者必须重新取得它们。本例用局部作用域让旧访问路径的名字在重新分配前退出可见范围，随后建立 `renewed`，因此没有通过失效指针比较新旧地址或访问旧元素。

这个作用域只是减少误用的代码组织手段。指针和 span 退出作用域，不会通知 `vector`、释放元素或改变容器状态，也没有解除某种运行时借用登记。如果事先把旧指针复制到外部变量，作用域结束仍不能阻止程序后来误用它；有效性始终由对象和容器的合同决定。

这也不同于第一单元的同址透明替换：这里不是在仍保留的原存储上用同类型完整对象覆盖原对象，不能借用透明替换规则“追踪”容器搬迁。

### 4.3 clear 保留容量，不保留元素接口

最后的 `clear()` 使序列为空，但保留容量。程序可以随后追加新的元素，不需要先把所有容量丢掉；但旧 `renewed` 描述的那三个元素已不能再按原借用使用。`renewed` 变量仍在作用域里，并不会自动把自己的长度改成零。

这正好把第一单元的模型带回标准容器：存储仍有复用价值，不等于旧元素仍可访问。不要在 `clear()` 后用下标读取所谓“缓存的旧值”；容器合同没有提供这样的读取接口。

## 5 没有重新分配，也可能失去原来的逻辑位置

现在只删除中间一个元素。若只盯着存储基址，容易忽略另一件事：后面的元素需要填补空缺，下标与逻辑记录之间的关系变了。

**文件 `erase-position.cpp`**

```cpp
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::vector<int> samples{10, 20, 30, 40};
    int& prefix = samples.front();
    const auto old_capacity = samples.capacity();
    const auto old_index = 2U; // At this moment, it selects value 30.
    if (samples[old_index] != 30) return 1;

    auto next = samples.erase(samples.begin() + 1);
    const int expected[]{10, 30, 40};
    if (!std::ranges::equal(samples, expected)) return 2;
    if (next != samples.begin() + 1 || *next != 30) return 3;
    if (&prefix != &samples.front() || prefix != 10) return 4;
    if (samples.capacity() != old_capacity || samples[old_index] != 40) return 5;
    std::cout << "after erase next=" << *next
              << " old-index-now=" << samples[old_index] << '\n';
}
```

输出是 `after erase next=30 old-index-now=40`。`prefix` 位于删除点之前，可以继续使用。删除点及其后的旧迭代器、引用则按失效规则处理；程序改用 `erase` 返回的迭代器定位新的后继元素。

这里不应画成“所有后续对象先析构、再逐一重建”的固定过程。删除中间元素可以包含赋值搬移，元素位置上的 C++ 对象与应用层所说的“原来那条记录”并不是同一种身份。即使某处地址仍落在活元素上，也不能据此推断它仍代表旧读数。

同样，下标不是一个免维护的稳定句柄。旧下标 2 仍在合法范围内，读取没有越界，却已经得到 40 而不是 30。若应用必须跨删除、排序或重建追踪同一业务实体，需要明确稳定 ID、查找和失效策略；那是更高层的数据结构选择，不由“把指针换成整数”自动解决。

## 6 让工具识别一次具体的失效访问

前面的例子都避免了失效访问。现在只把重新分配实验中的一个条件改坏：保留旧元素指针，重新分配后仍然读取它。

**以下是未定义行为反例，只在临时目录的独立进程中使用 AddressSanitizer 运行，不是正常程序。** 预期是工具报告 `heap-use-after-free`，不是返回某个旧读数。

**文件 `stale-borrow.cpp`**

```cpp
#include <vector>

int read_borrowed(const int* value) {
    return *value;
}

int main() {
    std::vector<int> samples{10, 20, 30};
    const int* borrowed = &samples[0];
    if (samples.capacity() == samples.max_size()) return 1;
    samples.reserve(samples.capacity() + 1);
    return read_borrowed(borrowed); // Intentional stale access; sanitizer only.
}
```

执行器先用合法程序确认本机 sanitizer 能够编译并运行，再把这个反例放进独立进程，要求指定退出码 86 和目标诊断同时出现。不能把普通编译失败、进程崩溃或超时算作“成功抓住错误”。具体命令在[验证说明](g01-verification.md)。

这个实验验证的是工具能否识别本次堆存储释放后的读取。它不证明 ASan 可以诊断第一单元的全部原地生命周期错误，也不负责发现前一节那种“合法下标读到了另一条逻辑记录”的错误。工具报告和语言、容器合同的推理分别承担不同工作。[AddressSanitizer 的能力与用法](https://clang.llvm.org/docs/AddressSanitizer.html)

## 7 从接口合同决定何时重取借用

| 操作条件 | 旧访问路径应怎样处理 | 本例暴露的问题 |
| --- | --- | --- |
| 不重新分配的末尾追加 | 既有元素路径可保留，旧终点不可沿用；span 长度不自动更新 | 没有悬挂也可能漏掉新元素 |
| 成功的容量增长重新分配 | 重新取得元素指针、引用、迭代器和视图 | owner 活着不能保护旧存储借用 |
| 删除中间元素 | 删除点及之后的旧迭代器、引用失效；重新判断位置含义 | 同一下标不等于同一条记录 |
| 清空序列 | 停止使用全部旧元素借用 | 容量保留不代表元素保留 |
| owner 结束生命 | 停止通过借用访问其原元素 | 复制 span 不复制拥有关系 |

表不是所有容器和操作的失效矩阵。遇到具体操作，应先确定它的前提、成功或失败路径以及类型条件，再查相应规则；不要把这里对 `vector<int>` 的判断套给所有容器。

### 7.1 用变化后的条件检验模型

1. `prefix` 创建后，vector 在不重新分配的情况下追加一个元素。为什么既不能说 span 悬挂，也不能说它已经覆盖全部新元素？
2. 把检测条件写成“旧指针数值和新 `data()` 不同才失效”，问题在哪里？
3. `erase` 后 ASan 没有报告，但旧下标得到另一条读数。应该修改 sanitizer 设置，还是回到业务身份和位置关系？
4. `const std::span<int>` 与 `std::span<const int>` 各限制什么？其中哪个是独立数据快照？
5. 某函数保存了调用方提供的 span，约定下一帧再处理。原来“仅在调用期间有效”的合同还够用吗？

### 7.2 推理与修正

**第一题。** 已有元素仍在允许使用的状态，原范围并未因此失效；但 span 保存的是取得时的范围描述，不会随 vector 更新。若业务要处理新增元素，应重新形成符合当前任务的范围。

**第二题。** 失效规则来自操作合同，不来自地址是否看起来改变。重新分配后再求值旧指针也不应被当作通用的合法性检查。应先依据容量条件判断操作，再停止使用失效路径并重取借用。

**第三题。** 回到身份与位置。程序可能一直在合法的内存范围里运行，只是业务把“下标 2”误当成了“那条读数”。内存检测器无法代替逻辑身份设计，测试需要覆盖删除后记录是否仍正确对应。

**第四题。** 前者约束 span 对象本身的修改，元素仍是可写 `int`；后者限制通过该视图修改元素。二者都不拥有副本，都不是自动冻结的快照。若有其他可写别名，读到的内容仍可能变化。

**第五题。** 不够。借用使用时间已经延长，必须有明确的存活及失效约束，或者改为交付独立数据或合适的拥有关系。仅把参数从指针换成 span，不会解决延迟使用问题。

前两个单元已经建立了生命区间和借用失效的模型，还剩一项访问前提：即使对象活着，也不能随意换一种类型读取它。[第三单元](g01-representation-and-typed-access.md)先说明对象表示与类型化访问，再交给 G2 处理清理责任、借用与提前退出；值类别仍放到 G3 的复制、移动与返回主线。
