# G3 值的复制、赋值与移动

G2 把 `Batch` 暂时做成不可复制类型，借此看清一份数据由谁持有、何时释放。现在有了不同的需求：保留原始读数供审核，同时生成一份可以修改的校准结果。复制一个 `shared_ptr` 仍然让两条路径指向同一个 Batch，不能满足这个要求。我们需要的不是第二个 owner，而是第二个可以独立变化的值。

本单元先让普通成员完成这件事，再展开一个需要自定义复制的表示，逐步检查复制构造、赋值失败、移动和移出状态。[下一单元](g03-expressions-and-return.md)继续把这个类型传入函数、返回给调用方，最后用表达式类别解释选择了哪个操作。完整实验使用 C++23；[验证说明](g03-verification.md)单独保存命令、工具链、判据与未验证范围。本章不测耗时，也不把实验用类型推荐为通用容器。

## 1 复制之前先确定什么算同一个值

### 1.1 用 abstraction function 描述值，而不是逐字节描述对象

一个值类型需要同时描述合法表示和它代表的逻辑值。可以把合法表示条件记为 `I(r)`，把表示 r 映射到业务值的 abstraction function（抽象映射）记为 `V(r)`。这里借用数据抽象中的分析模型；abstraction function 不是 C++ 核心语言定义的实体。本例的 V 取出批次号与有序读数，不把数组地址或备用容量纳入值。不同表示只要映射到同一 V，就可以在当前合同下表示相等的值。

复制的成功条件因此不是“成员逐个赋过值”，而是目标满足 I，且 `V(target) = V(source_before)`；本例还要求源值不变、后续允许的修改互不影响。最后一项是观察上的独立性：内部共享不可变表示可以支持某些值语义，直接共享可变 vector 却不符合这里的独立修改合同。不能把所有值类型都定义成“物理内存完全不共享”，也不能只凭复制构造存在就认定值语义成立。

### 1.2 成员语义如何组成外层值

对这批读数，逻辑值由批次号和有序的整数序列组成。两个 Batch 的对象地址不同，甚至内部容量不同，都不妨碍它们表达相同的值。相反，两个对象虽然都能读出第一个数，却可能长度不同，不能称为完整值相等。

这里要求的值语义（value semantics）包含两层：复制完成时，新对象与源对象具有相同的逻辑值；以后修改新对象的读数，不改变源对象的读数。第二层不是 C++ 看到“复制构造函数”几个字就能自动保证的。若成员是 `shared_ptr<vector<int>>`，默认复制会复制共享关系，修改同一 vector 仍会被双方看到；若成员是 span，复制得到的是另一份借用视图。类型选择和操作实现共同决定复制了什么。

最直接的生产起点仍然是 G2 的 `int` 加 `vector<int>`，只是去掉为生命计数实验设置的析构和复制禁令。vector 已经实现元素存储的复制与清理，外层不需要重复写一套循环。下面是这个表示的独立完整实验，不与后面的同名 Batch 放在同一翻译单元。

**文件 `memberwise-value.cpp`**

```cpp
#include <algorithm>
#include <iostream>
#include <memory>
#include <vector>

struct Batch {
    int sequence;
    std::vector<int> values;
};

int main() {
    const int input[] = {10, 20, 30};
    Batch source{7, {10, 20, 30}};
    Batch copied = source;
    if (copied.sequence != 7 || !std::ranges::equal(copied.values, input))
        return 1;
    if (copied.values.data() == source.values.data()) return 2;
    copied.values[0] = 99;
    if (!std::ranges::equal(source.values, input)) return 3;

    auto shared = std::make_shared<Batch>(source);
    auto peer = shared;
    peer->values[0] = 88;
    if (shared->values[0] != 88 || source.values[0] != 10) return 4;
    std::cout << "member copy owns independent values; shared handle does not\n";
}
```

在一个新目录保存文件，再执行：

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic memberwise-value.cpp -o memberwise-value
./memberwise-value
```

预期输出为 `member copy owns independent values; shared handle does not`。第一个复制建立独立 vector；`make_shared` 又从 source 复制出一个 Batch，但随后的 `peer = shared` 只共享这一个新对象。测试因此同时检查值、存储和后续修改，不能用“构造成功”或“两个指针相等”替代这些命题。

隐式定义的复制构造对非 union 类逐个初始化基类和成员，调用各成员自己的复制操作。它不是统一的“浅复制”，也不是递归复制所有可达对象的“深复制”。本例能得到独立读数，是因为 vector 的元素复制恰好满足需要；编译器并不知道业务要求的是独立读数。[成员复制规则](https://timsong-cpp.github.io/cppwp/n4950/class.copy.ctor)

## 2 为什么还需要展开一个手写复制的类型

理解 vector 版本以后，才值得问：如果一个小型资源包装本身要提供这种复制合同，工作落在哪里？例如一个库只给我们独占数组句柄，外层又需要把批次号、长度和这块存储作为一个值交付。这里用 `unique_ptr<int[]>` 表示独占数组，故意把平时由 vector 隐藏的准备、提交和移出状态显露出来。

这不是为了得到比 vector 更快的 Batch。新表示没有容量复用、迭代器接口或通用分配器，复制赋值还会临时同时保留两块存储。它只是一个边界明确的学习用组件。若成员本来已经表达所需语义，保留上一节的简单表示更合理。

约定如下：`sequence_` 和前 `size_` 个整数构成逻辑值；长度为零时没有数组，非零时数组恰好能承载全部元素。空批次仍可带批次号，不把所有空值都强行合并。成功复制保留这两部分值且存储独立；非自移动把源重置为批次号 0 的空值；自复制和自移动保持原值。`values()` 只借用，不允许借用者承担释放责任。

为了检验复制中途的失败，分配边界提供一个一次性故障开关。正常路径实际分配 `int[]`；开关打开时，在这一次非空分配开始前抛 `bad_alloc`。它不耗尽机器内存，也不声称覆盖所有分配器行为。计数器只统计本例经过这个入口的分配尝试与成功次数，不能当成整个进程的堆分配总量。

**文件 `batch-storage.hpp`**

```cpp
#ifndef G3_BATCH_STORAGE_HPP
#define G3_BATCH_STORAGE_HPP
#include <cstddef>
#include <memory>
#include <new>
#include <utility>

struct BatchStorage {
    static inline bool fail_next = false;
    static inline unsigned attempts = 0;
    static inline unsigned allocations = 0;

    static std::unique_ptr<int[]> allocate(std::size_t size) {
        if (size == 0) return {};
        ++attempts;
        if (std::exchange(fail_next, false)) throw std::bad_alloc{};
        auto data = std::make_unique<int[]>(size);
        ++allocations;
        return data;
    }
};
#endif
```

这里只复制 int，元素赋值不抛异常，所以故障集中在存储准备。换成任意 `T` 时，元素构造、部分区间销毁、对齐和 allocator 都会进入设计，不能直接把 `int` 改成模板参数就声称得到通用容器。实验开关也是单线程状态，不用于并发代码。

## 3 复制构造要建立新值，而不是接管旧数组

下面给出后续实验共用的完整定义。第一次阅读先跟踪普通构造、`clone` 和复制构造；赋值与移动在后面分别解释。把整份定义放在这里，是为了让每个操作始终接受同一套不变量约束，而不是展示几份互相不兼容的伪代码。

**文件 `value-batch.hpp`**

```cpp
#ifndef G3_VALUE_BATCH_HPP
#define G3_VALUE_BATCH_HPP
#include "batch-storage.hpp"
#include <algorithm>
#include <cstddef>
#include <memory>
#include <span>
#include <utility>

class Batch {
    int sequence_ = 0;
    std::size_t size_ = 0;
    std::unique_ptr<int[]> data_;

    static std::unique_ptr<int[]> clone(std::span<const int> values) {
        auto data = BatchStorage::allocate(values.size());
        if (!values.empty()) std::copy(values.begin(), values.end(), data.get());
        return data;
    }
public:
    Batch() noexcept = default;
    Batch(int sequence, std::span<const int> values)
        : sequence_(sequence), size_(values.size()), data_(clone(values)) {}
    Batch(const Batch& other) : Batch(other.sequence_, other.values()) {}
    Batch& operator=(const Batch& other) {
        if (this != &other) {
            Batch next(other);
            swap(next);
        }
        return *this;
    }
    Batch(Batch&& other) noexcept
        : sequence_(std::exchange(other.sequence_, 0)),
          size_(std::exchange(other.size_, 0)), data_(std::move(other.data_)) {}
    Batch& operator=(Batch&& other) noexcept {
        if (this != &other) {
            Batch next(std::move(other));
            swap(next);
        }
        return *this;
    }
    ~Batch() = default;

    void swap(Batch& other) noexcept {
        using std::swap;
        swap(sequence_, other.sequence_);
        swap(size_, other.size_);
        data_.swap(other.data_);
    }
    int sequence() const noexcept { return sequence_; }
    std::size_t size() const noexcept { return size_; }
    std::span<int> values() noexcept { return {data_.get(), size_}; }
    std::span<const int> values() const noexcept { return {data_.get(), size_}; }
};

inline bool has_value(const Batch& batch, int sequence,
                      std::span<const int> expected) {
    return batch.sequence() == sequence &&
           std::ranges::equal(batch.values(), expected);
}
#endif
```

复制构造以 `const Batch&` 借用源，随后委托给普通构造：先取得源的批次号与完整范围，再分配新数组、复制全部整数。非空复制完成后，两个 Batch 管理不同数组；空值则无须分配。任何一步失败，都没有一个已经完成构造的新 Batch 可以交给调用方，源的值也没有被修改。`unique_ptr` 负责已经取得的局部存储，不需要在每条异常路径补写 `delete[]`。

`make_unique<int[]>(size)` 先对数组元素进行值初始化，随后 `std::copy` 写入实际读数。本例选择直观且安全的实现，不把这两个阶段说成一次最优拷贝，也不引入未初始化存储来追求尚未测量的性能收益。

这里没有对 Batch 本体做 `memcpy`。它含有独占 owner，复制指针表示既不分配新数组，也不建立正确的释放责任。G1 允许对满足条件的可平凡复制对象复制字节，不能用来绕过本类的值合同。也不能为“避免分配”从 `other.data_.get()` 构造第二个独占 owner，那会制造重复释放责任。

`has_value` 是实验中的完整值判据，不是此类型完整的比较接口。它比较批次号和两个完整范围，因而空结果或只复制第一项不会侥幸通过。它不比较地址：地址不属于逻辑值，存储独立性需要另查。

**文件 `copy-value.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>

int main() {
    const int input[] = {10, 20, 30};
    Batch original(7, input);
    Batch copied = original;
    if (!has_value(copied, 7, input)) return 1;
    if (copied.values().data() == original.values().data()) return 2;
    copied.values()[0] = 99;
    if (!has_value(original, 7, input)) return 3;

    Batch assigned;
    Batch* returned = &(assigned = original);
    if (returned != &assigned || !has_value(assigned, 7, input)) return 4;
    if (assigned.values().data() == original.values().data()) return 5;
    assigned.values()[1] = 88;
    if (!has_value(original, 7, input)) return 6;

    Batch empty(9, {});
    Batch empty_copy = empty;
    if (!has_value(empty_copy, 9, {}) || empty_copy.values().data()) return 7;
    assigned = empty;
    if (!has_value(assigned, 9, {}) || assigned.values().data()) return 8;
    Batch& alias = original;
    original = alias;
    if (!has_value(original, 7, input)) return 9;
    std::cout << "copy preserves complete value and independent storage\n";
}
```

把两个头文件与程序放在同一目录，用 §1 的选项编译 `copy-value.cpp`。预期输出为 `copy preserves complete value and independent storage`。这组检查覆盖复制构造和复制赋值各自的值、地址及修改隔离，也检查空值和自复制。它不是完整测试矩阵；例如超大输入和自定义元素类型不在本章类型的范围内。

## 4 赋值面对的是一个已经有值的目标

### 4.1 State transition 与 exception guarantee

构造要建立一个新有效对象；赋值是既有对象的一次 state transition（状态转移）。两者都可能失败，但赋值的 caller 已持有一个旧值，因而可以提出更强问题：失败以后，哪些旧状态必须保持？仅让每个成员最终可析构，只能说明部分清理条件成立，不能保证它们仍共同表示同一个合法批次。

对下面的 copy assignment，证明可拆成三步：prepare 只创建独立候选，不修改受保护的旧值；commit 将候选整体交给目标，且当前操作组合不会抛出；cleanup 结束旧表示的资源责任。这种分解依赖 I 与 V 的定义，不能只检查函数里出现了 swap。若 prepare 已修改源、commit 有一半可能失败，或 cleanup 违反不抛承诺，就必须重新评估保证。

这里的 strong guarantee 限定到已经声明的状态集合。分配尝试计数、外部日志乃至 caller 在参数初始化时移出的对象，都不当然属于它。明确保护集合，比一句“赋值是事务”更精确；并发原子性和持久化事务也不由这个单线程异常保证推出。

### 4.2 对现有目标应用 prepare / commit

`Batch copied = original` 中虽然出现 `=`，目标仍是在初始化；它不调用赋值运算符。`assigned = original` 则要求一个已存在对象改变值。后者在准备新数组以前就有旧批次号和旧数组，必须回答：如果准备失败，调用者看到哪一份值？

一个看似直接的实现会先写 `sequence_ = other.sequence_`，再替换数组。如果分配此时失败，目标就可能变成“新批次号配旧读数”。更糟的版本先清空旧数组再申请新数组，失败后连旧值也无法保留。每个成员分别能正确析构，不代表整个对象仍满足业务后置条件；RAII 解决的清理问题没有替代赋值事务。

本例先构造 `Batch next(other)`，这一阶段可能失败，但尚未触碰目标。准备完成后，`swap(next)` 依次交换组成逻辑值的三部分，且这些整数与默认 unique_ptr 的交换都不抛异常。交换以后，目标具有新值，next 持有旧数组；next 离开作用域时清理旧值。这个准备、提交、清理的次序，才支持“复制失败时目标值不变”的强保证。这里的提交是单线程操作中的失败边界，不承诺交换的并发原子性。

保证的范围也要说清：本例保护源与目标的逻辑值，以及失败时目标原有存储；故障注入计数器已经增加，并不会回滚。它也不承诺恢复外部日志或设备状态。仅声明一个 `noexcept swap` 而不检查准备阶段和清理阶段，仍不足以证明强保证。

**文件 `copy-failure.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <new>

int main() {
    const int input[] = {10, 20, 30};
    const int old[] = {4, 5};
    Batch source(7, input);
    Batch target(2, old);
    auto old_data = target.values().data();
    auto attempts = BatchStorage::attempts;
    auto allocations = BatchStorage::allocations;

    bool caught = false;
    BatchStorage::fail_next = true;
    try { Batch rejected(source); }
    catch (const std::bad_alloc&) { caught = true; }
    if (!caught || BatchStorage::attempts != attempts + 1 ||
        BatchStorage::allocations != allocations) return 1;
    if (!has_value(source, 7, input)) return 2;

    caught = false;
    BatchStorage::fail_next = true;
    try { target = source; }
    catch (const std::bad_alloc&) { caught = true; }
    if (!caught || BatchStorage::attempts != attempts + 2 ||
        BatchStorage::allocations != allocations) return 3;
    if (!has_value(target, 2, old) || target.values().data() != old_data)
        return 4;
    if (!has_value(source, 7, input)) return 5;

    Batch& alias = target;
    BatchStorage::fail_next = true;
    target = alias;
    if (!has_value(target, 2, old) || !BatchStorage::fail_next ||
        BatchStorage::attempts != attempts + 2) return 6;
    BatchStorage::fail_next = false;
    target = source;
    if (!has_value(target, 7, input) || !has_value(source, 7, input) ||
        target.values().data() == source.values().data()) return 7;
    std::cout << "failed preparation preserves target; later copy succeeds\n";
}
```

正常输出为 `failed preparation preserves target; later copy succeeds`。第一次注入对应复制构造，第二次对应复制赋值；两者都确认失败发生在预定边界。自赋值通过别名传入，显式判断让它既不分配也不消耗故障开关。最后再执行一次正常赋值，排除对象只是在失败以后无法继续使用却暂时没崩溃的情况。

复制并交换（copy-and-swap）是本例选择的策略，不是所有类型都应照搬的最佳实现。目标原本有足够容量时，vector 一类类型可能复用存储；本例则每次非自复制都先取得完整新数组，增加分配与峰值存储。把按值参数 `operator=(Batch other)` 与这里的 `const&` 版本混看也会遗漏成本：按值形式在进入函数体之前就要构造参数，函数体里的自赋值检查无法撤销那次复制。

## 5 移动改变存储归属，也必须定义源对象的后置状态

### 5.1 Move 的证明需要同时看两个对象

move operation 不是把 source 的 lifetime 搬到 destination。move construction 建立新对象，move assignment 修改既有对象；source 本身仍然存在，直到按自己的规则销毁。真正可能转移的是内部资源责任或表示，移动后的 source 需要有明确 postcondition，才能知道哪些后续操作仍可调用。

本例的非自移动同时要求目标得到原 V，源满足约定的空状态，旧目标资源被正确结束。这是两个对象和可能一份旧资源之间的关系。默认 memberwise move 可以分别正确移动 unique_ptr、复制整数，却破坏“size 与数组是否存在一致”的跨成员 invariant；于是“各成员可移动”不足以证明“外层默认移动正确”。反之，成员本来就完整封装了相关关系时，再手写特殊成员会徒增维护责任。

### 5.2 让移出状态满足 Batch 的明确合同

若调用方不再需要原批次，复制全部整数可能没有必要。本例的移动构造把批次号、长度和 unique_ptr 交给新对象，并把源的元数据置零、句柄清空。数组里的整数留在原地址，新的 Batch 承担其清理责任；旧 Batch 对象仍然存在，只是状态变成约定的空值。移动不是“销毁源对象”，也不是 `std::move` 在后台逐字节搬走数据。

为什么不能直接默认移动这个类？默认移动会分别处理成员：unique_ptr 被转走，整数成员仍得到原数值。源因此可能保留非零长度，却已没有数组。每个成员都处于自身允许的状态，组合却破坏了 `size_` 与 `data_` 的关系。自定义移动在这里有实质任务，不只是为了给日志增加一行“move”。

移动赋值还要结束目标的旧拥有关系。它先从源构造 next，再交换；next 随后释放目标旧数组。自移动经过身份判断保持原值。这是本类主动承诺的行为，不应外推成所有用户类型或标准库类型都必须如此。

**文件 `move-state.cpp`**

```cpp
#include "value-batch.hpp"
#include <iostream>
#include <type_traits>
#include <utility>

int main() {
    static_assert(std::is_nothrow_move_constructible_v<Batch>);
    static_assert(std::is_nothrow_move_assignable_v<Batch>);
    const int input[] = {10, 20, 30};
    const int old[] = {4, 5};
    Batch source(7, input);
    auto address = source.values().data();
    auto allocations = BatchStorage::allocations;
    Batch moved(std::move(source));
    if (!has_value(moved, 7, input) || moved.values().data() != address ||
        BatchStorage::allocations != allocations) return 1;
    if (source.size() != 0 || source.sequence() != 0 ||
        source.values().data() != nullptr) return 2;

    Batch target(2, old);
    allocations = BatchStorage::allocations;
    target = std::move(moved);
    if (!has_value(target, 7, input) || target.values().data() != address ||
        BatchStorage::allocations != allocations) return 3;
    if (moved.size() != 0 || moved.sequence() != 0 ||
        moved.values().data() != nullptr) return 4;
    Batch& alias = target;
    target = std::move(alias);
    if (!has_value(target, 7, input) || target.values().data() != address)
        return 5;
    source = target;
    if (!has_value(source, 7, input) || source.values().data() == address)
        return 6;
    Batch empty;
    target = std::move(empty);
    if (!has_value(target, 0, {}) || target.values().data()) return 7;
    std::cout << "move transfers storage; source resets; self move preserves value\n";
}
```

预期输出为 `move transfers storage; source resets; self move preserves value`。地址与计数器支持的是这个实现没有为移动重新复制数组，不是“所有移动都是常数时间”的测量证明。若对象内嵌一个大数组，移动可能仍逐元素操作；若赋值需要结束昂贵的旧资源，交接句柄便宜也不代表整项操作便宜。

这里还有一个 G1 式的借用问题。源数组移动以后地址没变，旧元素指针可能仍指向活着的整数，但其生命现在由目标管理；目标被赋值或销毁时，借用可能结束。指向源 Batch 本身的引用则仍指向那个空对象。不能把“指向 owner 的引用”和“指向内部元素的指针”当成同一条路径。

标准库类型在未另行规定时，移出后通常处于有效但未指定状态；只应执行满足前置条件的操作，不能一律读取第一个元素。本类提供更具体的空状态合同，是设计选择。[标准库移出状态的规定](https://timsong-cpp.github.io/cppwp/n4950/lib.types.movedfrom)不是给任意手写移动自动补上后置条件，后者仍要由实现维护。

## 6 noexcept 说明失败边界，不负责让操作变便宜

Batch 的移动仅操作整数、默认 unique_ptr 和不抛异常的交换，不进行新数组分配，因此可以承诺异常不逃出。把复制构造也随手标为 `noexcept` 不会消除 `bad_alloc`；它只会改变异常逃逸的结果，使错误进入终止路径。异常规格必须由真实实现支持。[异常规格与终止](https://timsong-cpp.github.io/cppwp/n4950/except.spec)

`is_nothrow_move_constructible_v<Batch>` 检查的是相应构造表达式的可用性与异常性质，不检验读数是否正确复制、源是否清空或移动是否快。它甚至不能单独证明存在一个 `Batch(Batch&&)`：一个只有 `const&` 复制构造的类型，也可能从右值构造成功。下一单元会把这个区别直接交给编译器检查。

复制和移动还影响外层容器的失败保证。若迁移一个元素就破坏源，而迁移后续元素又可能抛异常，容器不能轻易回到旧状态；保留源不变的复制有时更适合准备新存储。这个因果比“vector 永远优先 move”准确。具体要求与例外应回查 [vector 修改操作](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers)；完整容器规则留给 G4，本章不以某个 libc++ 的构造次数替代合同。

## 7 从手写操作回到成员设计

现在再看开头的 vector 版本，就能理解零法则（Rule of Zero）的价值：若成员已经管理资源、外层没有额外的跨成员不变量，通常不必自行声明析构、复制和移动。这样不仅少写代码，也避免无意改变特殊成员函数的生成条件。

这些条件不能压成“编译器总会补齐五个函数”。用户声明析构、复制构造或复制赋值等操作，会影响隐式移动的生成；声明移动操作也会影响隐式复制。即使写的是 `= default` 或 `= delete`，它仍是用户声明。已经生成的默认操作还可能因为成员不支持相应行为而被定义为删除。尤其“没有移动候选”和“显式声明后删除移动候选”不等价，后者可能在重载选择以后直接导致编译失败。[复制与移动构造](https://timsong-cpp.github.io/cppwp/n4950/class.copy.ctor)、[赋值操作](https://timsong-cpp.github.io/cppwp/n4950/class.copy.assign)

五法则（Rule of Five）在这里是一项审查提醒：一旦需要干预资源和值的关系，就一起审视析构、复制构造、复制赋值、移动构造、移动赋值，而不是强制每个类手写五个函数。`unique_ptr` 成员让释放可以默认完成，却没有让本例的复制自动可用；批次号、长度和指针的组合，又让默认移动不满足要求。每个自定义操作都应能指出它具体维护哪一项关系。

值语义也不是无条件深拷贝所有关联对象。配置可以包含稳定的只读共享字典，图结构可以用明确 ID 表达外部身份。要先决定哪些部分属于这个值、哪些仍是借用或共享依赖，再选择成员与复制行为。本例只把批次号和整数序列视为值，因而独立数组足以表达要求；它没有替所有业务类型做出选择。

## 8 用变化后的条件检验模型

### 8.1 迁移问题

1. 把开头的 `vector<int>` 改成 `shared_ptr<vector<int>>`，默认复制仍能编译。为什么不再满足本章的校准副本要求？若内部数据不可变，判断可能怎样变化？
2. 复制构造可以直接初始化批次号；复制赋值为什么不能先改目标批次号，再申请新数组？强保证具体保护哪些状态？
3. 将 `size_` 与 unique_ptr 的移动全部写成 `= default`，源可能形成什么组合？仅看两个成员都“合法”够不够？
4. 为什么不能只用 `is_nothrow_move_constructible` 验证本例？若它为真，但移动把所有数据丢掉，哪些检查应当拒绝实现？
5. 源元素指针在移动后数值没有变化，源 Batch 的引用也仍有效。为什么这两条路径现在观察到的东西不同？
6. 一个赋值实现采用按值参数再 swap。它是否自动比本例更高效？若目标原本容量足够，应该比较哪些成本？

### 8.2 推理与修正

**第一题。** 默认复制 shared_ptr 复制的是共同拥有关系；副本修改同一 vector 会改变原对象看到的读数。若合同规定这部分状态确实不可变，并且不存在可写别名，共享表示可能仍能支持所需值行为，但还要考虑外部依赖、同步和生命周期；不能仅凭 const 句柄就认定全局不可变。

**第二题。** 构造失败时没有完成的新 Batch；赋值失败时目标却原本已有可用值。先改批次号会让目标在分配失败后留下混合状态。本例把所有可能失败的准备放在临时对象中，再不抛地交换，保护源与目标值及目标旧存储，不回滚实验计数或其他外部副作用。

**第三题。** unique_ptr 移出后为空，整数长度却可能仍为原值；源暴露的非空范围没有相应存储。类不变量是成员之间的关系，不是各成员合法性的简单相加。应显式重置元数据，或重新设计不需要独立长度的表示。

**第四题。** trait 只回答构造表达式的静态性质，不证明后置条件。测试必须先检查目标的完整值，再查存储关系与源状态；丢数据、截断或未清理源元数据都会在这些判据中暴露。类型检查与运行判据不能互相替代。

**第五题。** 指向源 Batch 的引用仍命名原对象，它已变成空值；元素指针命名数组里的对象，数组在本例中转归目标而没有搬走。后者的可用期要跟随新 owner 的后续操作，不能再用源对象是否存在来判断。

**第六题。** 按值参数可能在进入赋值体之前复制，即使随后发现自赋值也无法免去准备成本。复制并交换通常需要额外分配与峰值存储，复用容量则可能减少成本但使失败恢复更复杂。应先确定异常保证与典型输入，再计量，而不是用代码行数判断高效。

到这里，Batch 已经有可以推导的操作合同。下一步的问题是：调用表达式究竟选择复制、移动还是直接构造结果？这需要把类型、表达式类别与对象生命分开看。
