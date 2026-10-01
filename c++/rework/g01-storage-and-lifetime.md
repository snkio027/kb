# G1 存储、对象与生命周期

G0 追踪的是程序怎样生成。现在程序已经开始运行，我们把观察对象缩小到一块内存：它的地址已知，空间足够，甚至还保留着上一次写入的数值。这些条件是否足以让程序通过一个 `Reading*` 读取读数？

答案取决于这块存储上发生过什么。取得空间、建立对象、使用对象、结束对象生命和归还空间，是有关联但不能互相代替的动作。本单元沿着一个读数对象的建立、销毁和同址重建展开；[第二单元](g01-borrowing-and-invalidation.md)再把模型用于数组、`span` 和容器借用。语言基线为 C++23，执行命令与平台限制集中在[验证说明](g01-verification.md)。

## 1 普通局部变量隐藏了哪些步骤

写下 `Reading reading{1, 42};` 时，很容易把它理解为“得到一个变量”。这行代码实际上把几件事组合在一起：声明名称 `reading`，为一个 `Reading` 对象安排存储，并按两个实参初始化它。正常离开作用域时又会自动调用析构函数。在这种写法下，存储和对象的起止通常贴得很近，所以不容易看出它们的区别。

本章把这些动作拆开观察，不是建议日常业务代码都手工管理生命周期。恰恰相反，拆开后可以看见普通局部对象替我们维持了哪些关系，也能理解容器和资源句柄为什么需要精心实现。

下面的类型代表一个带序号的整数读数。计数器只服务于实验：`live` 记录已完成构造而尚未执行本例析构计数的对象数，另外两个计数器记录构造和析构次数。它们不是通用的生命周期检测器，也不支持多线程并发修改。

**文件 `reading.hpp`**

```cpp
#ifndef G1_READING_HPP
#define G1_READING_HPP

struct Reading {
    static inline int live = 0;
    static inline int constructed = 0;
    static inline int destroyed = 0;

    int sequence;
    int value;

    Reading(int seq, int measured) noexcept
        : sequence(seq), value(measured) {
        ++live;
        ++constructed;
    }

    Reading(const Reading&) = delete;
    Reading& operator=(const Reading&) = delete;

    ~Reading() noexcept {
        --live;
        ++destroyed;
    }
};

#endif
```

这里暂时禁止复制，避免一个观察语句无意制造副本，也不引入移动实现。`Reading` 有自己编写的构造函数和析构函数；我们会显式建立它，而不依赖隐式创建对象的规则。后面的容器例子使用整数元素，不要求这个实验类型满足容器的复制或移动条件。

## 2 有一块存储，还没有本例的 Reading

为这个类型准备空间，可以声明 `alignas(Reading) std::byte storage[sizeof(Reading)];`。`sizeof` 解决空间大小，`alignas` 解决对齐要求。两者缺一不可：一段空间容得下全部字节，不代表它的起始地址适合放置该类型。

这条声明已经建立了字节数组对象，不能说它“没有创建任何对象”。更准确的描述是：字节数组存在，但本例的 `Reading` 尚未构造。C++23 允许某些操作隐式创建特定类别的对象；我们的 `Reading` 不属于这里可以靠字节数组声明隐式启动生命的类型，因此选择显式构造能把实验边界说清楚。[对象模型与字节数组提供存储的规则](https://timsong-cpp.github.io/cppwp/n4950/intro.object)

随后把 `storage` 转换成 `Reading*`，也没有补上构造。指针类型告诉编译器后续表达式应按什么类型分析，不会因为换了一个类型名字就执行初始化。这里需要的是在这处存储建立对象的操作，而不是更多次强制转换。

`std::construct_at` 接收位置和构造实参，在指定位置初始化对象，并返回指向新对象的指针。它不替调用者取得一块新的存储，也不检查任意地址是否有足够空间；本例用字节数组的大小和对齐先满足前提。[construct_at 的定义](https://timsong-cpp.github.io/cppwp/n4950/specialized.construct)

## 3 完整追踪建立、销毁和重建

将以下文件与 `reading.hpp` 放在同一个新目录。先预测每行输出，再运行；不要在两次构造之间插入对旧成员的读取来“看看还剩什么”。

**文件 `lifecycle.cpp`**

```cpp
#include "reading.hpp"
#include <cstddef>
#include <iostream>
#include <memory>

int main() {
    alignas(Reading) std::byte storage[sizeof(Reading)]{};
    auto* location = reinterpret_cast<Reading*>(storage);
    std::cout << "raw live=" << Reading::live << '\n';
    if (Reading::live != 0 || Reading::constructed != 0) return 1;

    Reading* first = std::construct_at(location, 1, 42);
    Reading& alias = *first;
    const Reading* observer = first;
    std::cout << "constructed live=" << Reading::live
              << " value=" << first->value << '\n';
    bool good = Reading::live == 1 && first->sequence == 1;
    good = good && first->value == 42 && std::addressof(alias) == first;

    alias.value = 43;
    good = good && observer->value == 43;
    std::destroy_at(first);
    std::cout << "destroyed live=" << Reading::live << '\n';
    good = good && Reading::live == 0 && Reading::destroyed == 1;

    // No member access through first, alias, or observer in this interval.
    Reading* second = std::construct_at(location, 2, 84);
    good = good && first == second && std::addressof(alias) == second;
    good = good && alias.sequence == 2 && observer->value == 84;
    std::cout << "rebuilt live=" << Reading::live
              << " sequence=" << alias.sequence << '\n';

    std::destroy_at(second);
    good = good && Reading::live == 0;
    good = good && Reading::constructed == 2 && Reading::destroyed == 2;
    std::cout << "final live=" << Reading::live
              << " constructed=" << Reading::constructed
              << " destroyed=" << Reading::destroyed << '\n';
    return good ? 0 : 2;
}
```

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic lifecycle.cpp -o lifecycle
./lifecycle
```

这个例子的预期输出是：

```text
raw live=0
constructed live=1 value=42
destroyed live=0
rebuilt live=1 sequence=2
final live=0 constructed=2 destroyed=2
```

第一行和第三行都没有可按本例正常成员接口访问的活 `Reading`，但两者所处的历史不同。第一行尚未构造；第三行已经析构。字节数组在这两个时刻都存在。第二次构造又使用了同一位置，却建立了一个新的对象，其序号为 2。

```text
时间          准备    构造 1     析构 1    构造 2     析构 2    离开
storage       |------------------------------------------------|
Reading #1            |----------|
Reading #2                                |----------|
```

图中没有按指令或真实耗时画比例，只强调存储区间可以覆盖多个对象生命区间。`live` 的增减发生在函数体内，是辅助观察；语言边界不由这个整数决定。对本例，初始化完成后进入通常意义上的对象生命周期，而类对象的生命在析构调用开始时结束。构造和析构期间另有访问规则，所以析构函数仍可以访问自己的成员；不能从时间边界推出“析构函数体不能使用成员”。[生命周期规则](https://timsong-cpp.github.io/cppwp/n4950/basic.life)与[构造析构期间的规则](https://timsong-cpp.github.io/cppwp/n4950/class.cdtor)需一起理解。

## 4 析构之后没有发生什么

### 4.1 destroy_at 不等于释放存储

对这里的非数组类对象，`std::destroy_at(first)` 调用析构函数。它不会把 `storage` 交回某个堆分配器，也不会保证把那片字节清成零。析构之后，字节可能看起来没有变化，但这不能支持 `first->value` 这样的成员访问。[destroy_at 的定义](https://timsong-cpp.github.io/cppwp/n4950/specialized.algorithms#specialized.destroy)

反过来，也不能把 `first` 立即理解成“任何形式都不能提及的比特串”。在存储尚未复用或释放的这段间隔内，语言允许对表示该存储位置的指针作有限使用，例如按 `void*` 处理；这不等于允许继续读取已经结束生命的对象。应判断具体操作，而不是给指针笼统贴一个“还能用”的标签。

本例有意不执行间隔中的错误成员访问。AddressSanitizer 主要跟踪可检测的内存访问错误，不是完整的 C++ 对象生命判定器；存储仍在时，某次非法生命周期访问未必会被它报告。靠一次成功读取或一次无诊断运行，无法推翻语言约束。

### 4.2 字节数组不会替你调用 Reading 的析构函数

普通局部 `Reading reading{1, 42};` 的析构由作用域退出规则安排。现在局部变量却是一个字节数组；在它提供的空间中手工构造 `Reading`，不会替这个数组登记一项“退出时自动析构 Reading”的业务动作。

因此，本例需要在复用和离开前安排清理。如果 `Reading` 将来拥有文件、锁或其他资源，遗漏清理可能使资源责任悬空，即使那块存储稍后自然消失。反过来，给一个普通局部 `Reading` 显式析构后又让自动析构照常发生，也不能当作安全清理两遍；必须考虑是否已有合适的新对象供隐式析构处理。

这正是手工实验与可复用组件之间的差距。实验通过简单控制流让构造和析构成对出现；生产接口还要处理提前返回、异常和责任转移。后续 G2 用资源句柄封装这些责任，本章先把责任确实存在这件事展示出来。

## 5 同址重建后，旧指针会怎样

完整例子里，`first`、`alias` 和 `observer` 都是在第一个对象活着时取得的。第一个对象销毁以后，没有通过它们访问成员；第二个对象建立以后，却使用旧的 `alias` 读到了新序号。这不是“旧对象复活了”。

这里满足透明替换（transparent replacement）的条件：新旧对象都是完整的 `Reading`，存储位置完全重合，原对象不是 `const` 完整对象，也不涉及基类或其他潜在重叠子对象。对这种替换，旧指针、引用或名称会在新对象生命开始后指代新对象。因此本例的旧引用能合法访问序号 2。

这项结论既不能缩成“对象一析构，旧指针永远不能再用”，也不能扩大成“地址相同，旧指针一定能用”。若改成不同类型、基类子对象或其他不满足条件的情形，需要重新分析；不能只比较地址数值。这里使用 `construct_at` 的返回值 `second`，也让新对象的访问入口直接可见。

`std::launder` 并不是自动修复悬挂的开关。它有已经存在合适对象及字节可达性等前提，不负责分配、构造或延寿。本例的透明替换不需要它；更复杂的子对象复用留到确实需要实现相关组件时再展开。[launder 的前提](https://timsong-cpp.github.io/cppwp/n4950/ptr.launder)

## 6 指针与引用提供访问路径，不接管对象

`first` 是一个指针对象，自己保存一个指针值；`alias` 是对 `Reading` 的引用。`std::addressof(alias)` 得到的是被引用对象的地址，不是另一个独立 `Reading` 的地址。例子里执行 `alias.value = 43`，修改的就是 `first` 所指对象。

`observer` 的类型为 `const Reading*`，所以不能通过这条路径直接赋值给 `value`。但原对象并不是 `const`，另一条合法的可写路径仍能修改它。因此 `observer->value` 随后读到 43；`const` 访问路径没有制造只读快照，也没有提供并发同步。

下面的完整文件只用于检查编译器拒绝通过只读路径赋值，不会生成和运行程序。

**文件 `const-access.cpp`**

```cpp
#include "reading.hpp"

int main() {
    Reading reading{1, 42};
    const Reading* observer = &reading;
    observer->value = 99; // Expected compile error: this access path is const.
}
```

再把问题推进一步：即使使用引用而不是指针，也没有自动延长一般被引用对象的生命。引用无法重新绑定，并不意味着目标不会先死；指针非空，也只排除了空指针值，不能证明目标存活、索引有效或访问类型正确。

访问有效性因此不是地址的一项永久属性。要沿这条路径找到目标对象，再结合当前生命区间、类型、边界和可修改性判断。本单元只讨论单线程；并发访问还要建立同步关系，不能从“对象活着”直接推出并发安全。

## 7 构造失败时，哪些对象已经存在

前面 `Reading` 的构造函数不抛异常。现在让它成为另一个对象的成员，再让外层构造失败，就能看见“成员已构造”和“完整对象已构造”不是同一个状态。

**文件 `constructor-failure.cpp`**

```cpp
#include "reading.hpp"
#include <cstddef>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string_view>

struct Envelope {
    static inline int completed = 0;
    static inline int destroyed = 0;
    Reading reading;

    explicit Envelope(bool reject) : reading(7, 42) {
        if (reject) throw std::runtime_error("rejected envelope");
        ++completed;
    }

    ~Envelope() noexcept { ++destroyed; }
};

int main() {
    alignas(Envelope) std::byte storage[sizeof(Envelope)]{};
    auto* location = reinterpret_cast<Envelope*>(storage);
    Envelope* current = nullptr;
    bool caught = false;
    try {
        current = std::construct_at(location, true);
    } catch (const std::runtime_error& error) {
        caught = std::string_view{error.what()} == "rejected envelope";
    }
    bool good = caught && current == nullptr;
    good = good && Envelope::completed == 0 && Envelope::destroyed == 0;
    good = good && Reading::constructed == 1 && Reading::destroyed == 1;
    good = good && Reading::live == 0;
    std::cout << "rejected outer-destroyed=" << Envelope::destroyed
              << " member-destroyed=" << Reading::destroyed << '\n';

    current = std::construct_at(location, false);
    good = good && current->reading.value == 42 && Reading::live == 1;
    std::destroy_at(current);
    good = good && Envelope::completed == 1 && Envelope::destroyed == 1;
    good = good && Reading::live == 0 && Reading::destroyed == 2;
    std::cout << "retry outer-destroyed=" << Envelope::destroyed
              << " member-destroyed=" << Reading::destroyed << '\n';
    return good ? 0 : 1;
}
```

用与前例相同的编译选项运行，应得到：

```text
rejected outer-destroyed=0 member-destroyed=1
retry outer-destroyed=1 member-destroyed=2
```

`Envelope` 的成员先初始化，随后才进入构造函数体。第一次在函数体抛异常时，成员 `reading` 已完成构造，所以异常退出会析构它；外层 `Envelope` 没有完成构造，不会调用它的析构函数。这里讨论的是这个非委托构造函数，不把结论推广到所有构造形式。[构造异常的清理规则](https://timsong-cpp.github.io/cppwp/n4950/except.ctor)

赋值 `current = std::construct_at(...)` 也尚未完成，所以 `current` 仍为 `nullptr`。存储本身来自外面的字节数组，失败没有结束这个数组的存在；第二次可以按完整流程重新尝试构造。若这里换成普通 `new Envelope(...)`，还有分配及构造失败后的相应存储释放规则，不能把两种写法混为一谈。

最重要的推理是逐层判断完成状态。不能因为“调用过构造函数”就在错误路径里无条件 `destroy_at(current)`，也不能因为外层构造失败就认为所有已经构造的成员都不会清理。

## 8 临时对象的延寿不会沿引用自动传递

前面没有任何引用负责对象的生命。C++ 确实存在某些引用绑定延长临时对象生命周期的规则，但这不是引用普遍拥有的能力。下面沿同一个 `Reading` 类型比较直接绑定和经过函数参数的绑定。

**文件 `reference-lifetime.cpp`**

```cpp
#include "reading.hpp"
#include <iostream>

const Reading& forward_reading(const Reading& input) noexcept {
    return input;
}

int main() {
    bool good = true;
    {
        const Reading& direct = Reading{1, 42};
        good = good && Reading::live == 1 && direct.value == 42;
        std::cout << "direct live=" << Reading::live << '\n';
    }
    good = good && Reading::live == 0 && Reading::destroyed == 1;

    [[maybe_unused]] const Reading& indirect = forward_reading(Reading{2, 84});
    // The temporary has been destroyed. Do not access through indirect.
    good = good && Reading::live == 0 && Reading::destroyed == 2;
    std::cout << "forwarded live=" << Reading::live << '\n';
    return good ? 0 : 1;
}
```

直接绑定的临时对象持续到内层作用域结束，因此第一行输出 `direct live=1`。第二个临时对象绑定到函数的引用参数，持续到包含调用的完整表达式结束；也就是初始化语句结束时已经销毁。函数返回引用，没有再次延长它的生命，第二行输出 `forwarded live=0`。[临时对象生命周期与引用参数例外](https://timsong-cpp.github.io/cppwp/n4950/class.temporary)

此时 `indirect` 这个引用仍在作用域里，但不能再用来读成员。实验只检查独立的计数器，没有执行悬挂访问。函数是否内联不改变这些语义，不能希望优化器“看穿转发”后顺便赋予另一种延寿规则。

这也是审查返回引用接口时应追踪真实对象的原因。返回语法里出现 `const&`，只描述访问形式；你仍要找到对象在哪里建立、由什么事件结束生命。对于从函数交付新数据，按值返回和借用已有对象承担不同的责任，后面分别展开。

## 9 把访问判断压缩成一条路径

| 当前状态 | 本例允许做的事 | 不能据此推出的结论 |
| --- | --- | --- |
| 字节数组存在，Reading 未构造 | 检查大小与对齐，准备构造位置 | 转成 `Reading*` 就已建立对象 |
| Reading 构造完成 | 按类型和访问权限读取、修改成员 | 任意别名、越界或并发访问都安全 |
| 析构完成，存储尚未复用 | 安排新的构造，有限处理存储位置 | 旧成员值看起来还在，所以可以读取 |
| 同址构造新 Reading | 使用返回的新指针；本例还满足透明替换 | 任意类型或子对象复用都会自动修复旧引用 |
| 存储也已结束 | 不再通过原访问路径使用其内容 | 非空地址仍代表一个可用对象 |

### 9.1 用变化后的条件检验模型

1. 把 `alignas(Reading)` 删除，但保留 `sizeof(Reading)`，哪项前提失去了保证？一次运行未报错能补回它吗？
2. 在两次 `construct_at` 之间，旧的 `first` 仍非空。为什么不能读取 `first->value`？为什么又不能简单说“连按 `void*` 处理都不行”？
3. 第二次重建改成另一个类型，即使大小恰好相同，旧 `Reading&` 还能沿用吗？
4. `Envelope` 构造失败时为什么 `Reading::destroyed` 增加，而 `Envelope::destroyed` 没增加？
5. 把 `forward_reading` 写成一行内联函数，是否能让 `indirect` 安全延寿？

### 9.2 推理与修正

**第一题。** 足够的字节数仍在，但对象要求的起始对齐不再由该声明保证。当前实现可能碰巧把数组放在足够对齐的位置；这一偶然结果不能替代接口前提，应在声明或分配方式上明确满足它。

**第二题。** 原对象的生命已经结束，而原存储仍存在。这段间隔限制的是具体操作：旧成员访问不合法，某些不把存储当作活对象使用的操作仍被允许。不要用非空检查代替生命周期推理，也不要把存储未释放与对象存活混为一谈。

**第三题。** 不能沿用本例的透明替换推理。类型相同是这里的重要条件之一，空间大小相同并不足够。应从新的构造结果取得正确类型的访问路径，并单独考虑旧别名、清理责任和存储复用是否合法。

**第四题。** 成员初始化已经完成，外层初始化没有完成。异常清理据此析构成员，而不调用这个未完成构造的完整对象的析构函数。检查清理责任时需要一层一层分析，不能只看最外层的成功或失败。

**第五题。** 不能。临时对象的销毁时机由表达式和绑定规则决定，不由函数是否生成独立调用指令决定。这正好延续 G0 的区分：机器实现可以改变，语言约束不能靠观察一个编译结果重新定义。

本单元刻意没有同时展开值类别、联合体、字节级序列化和所有对象复用特例。现在先把模型用于一批会增长、删除、重新分配的元素，看看一个依然活着的 owner 为什么仍可能让借用失效：[G1 借用、范围与访问失效](g01-borrowing-and-invalidation.md)。
