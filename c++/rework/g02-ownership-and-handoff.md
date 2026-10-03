# G2 借用与所有权交接

[上一单元](g02-resource-lifecycle.md)给临时文件安排了唯一的关闭责任。现在回到读数处理：解析、校验、统计都要访问同一批数据，稍后执行的任务可能还要继续使用它。是不是每传给一个函数，就应当复制一份 `shared_ptr`？

先问访问需要持续多久，以及调用结束后谁还必须保持数据存在。同步计算可以借用；独立任务可以接管；确实存在多个独立参与者时才需要共同延长生命。本单元沿同一读数批次比较这些关系，最后把它们用于延迟任务和回调环。实验均为单线程，不把“稍后调用”伪装成并发执行；语言基线、运行记录和边界见[验证说明](g02-verification.md)。

## 1 多个访问者不一定需要多个 owner

### 1.1 Ownership graph 与 access graph

理解对象关系时，可以分别画两张逻辑图。ownership graph 的边表示谁维持目标的生命管理责任，access graph 的边表示谁在什么条件下可以访问目标。两张图常常交叉，却不是同一张图：一个 Batch 可以由局部变量直接拥有，同时被多个同步 callee 借用；一个 shared_ptr 可以维持对象生命，却不授予对全部状态的并发修改权。

区分两张图以后，参数设计就不再从指针种类开始。只需要读数据的 callee 应取得足够完成读取的访问；需要把数据保存到未来的组件，才要进一步说明由谁维持那段时间的 lifetime。把所有边都改成 shared ownership 可能消除某些悬挂，却也可能延迟释放、形成环，并隐藏系统真正的结束条件。

### 1.2 按 callee 的实际需要选择权限

假设调用方持有一个读数批次，依次调用校验和求和函数。只要调用期间批次存在、有关视图没有失效，这两个函数可以使用 `const Batch&` 或 `span<const int>`。它们没有理由决定批次何时销毁，也不必知道调用方把它放在局部变量、`unique_ptr` 还是别的对象里。

这种接口把依赖缩小为“需要数据”，而不是“需要参与数据的生命管理”。如果每个只求和的函数都接受 `shared_ptr`，调用方就被迫配合一种拥有方式，函数还可能通过保存副本把生命区间悄悄延长。参数类型不应表达它并不需要的权限。

值成员通常是最直接的起点。`Batch` 直接持有 `vector<int>`，由 vector 管理元素和存储；没有必要再为这个成员套一个 `unique_ptr<vector<int>>`。独立分配应来自实际需要，例如可选存在、跨作用域交接或运行时多态，而不是“对象重要，所以应该放到堆上”。直接成员仍可能在内部动态分配，不能据此声称没有堆成本。

下面的类型用于完整实验。删除复制只是避免计数器把未经登记的隐式复制算错，不代表读数批次天然不能复制；独立值的复制语义留给 G3。构造中 vector 初始化先于 `live` 增加，若初始化失败，不会留下虚构的活对象计数。

**文件 `batch.hpp`**

```cpp
#ifndef G2_BATCH_HPP
#define G2_BATCH_HPP
#include <vector>

struct Batch {
    static inline int live = 0;
    static inline int destroyed = 0;
    int sequence;
    std::vector<int> values;
    explicit Batch(int id) : sequence(id), values{10, 20, 30} { ++live; }
    Batch(const Batch&) = delete;
    Batch& operator=(const Batch&) = delete;
    ~Batch() noexcept { --live; ++destroyed; }
};

inline int sum(const Batch& batch) {
    int result = 0;
    for (int value : batch.values) result += value;
    return result;
}
#endif
```

`sum` 的合同是同步读取、不保存引用。这个约束不是 `const&` 自动保证的：函数仍可能把地址写入某个全局位置，也不能靠 `const` 防止其他别名修改对象。调用者和实现者必须一起维护使用区间；这里的固定小整数也刻意避开了通用数值求和的溢出问题。

## 2 unique_ptr 把动态对象的释放责任交给一个句柄

确实需要独立动态对象时，`std::make_unique<Batch>(7)` 把分配和构造得到的对象直接放入独占 owner。`unique_ptr` 的复制被禁止，移动可以交接责任；它管理的是被指对象，不会因复制裸指针而增加一个 owner。默认 deleter 对单对象使用 `delete`，数组形式和自定义资源需要相应的释放协议。[unique_ptr 的单对象合同](https://timsong-cpp.github.io/cppwp/n4950/unique.ptr.single)

本例从借用开始，再分别观察移动、`release` 和接管。`consume` 按值接收 owner，表示参数成功构造后已经接手，无论后续业务处理是否成功，都由这份参数负责清理。

**文件 `unique-handoff.cpp`**

```cpp
#include "batch.hpp"
#include <iostream>
#include <memory>
#include <stdexcept>
#include <utility>

int consume(std::unique_ptr<Batch> batch, bool reject) {
    if (!batch) throw std::invalid_argument("missing batch");
    if (reject) throw 7;
    return sum(*batch);
}

int main() {
    auto owner = std::make_unique<Batch>(7);
    Batch* borrowed = owner.get();
    if (sum(*borrowed) != 60 || Batch::live != 1) return 1;
    const auto& const_owner = owner;
    const_owner->values[0] = 11;
    if (sum(*borrowed) != 61) return 2;

    auto next = std::move(owner);
    if (owner || next.get() != borrowed || Batch::live != 1) return 3;
    Batch* raw = next.release();
    std::unique_ptr<Batch> adopted(raw); // No throwing work in the gap.
    if (next || adopted.get() != borrowed || Batch::live != 1) return 4;

    bool caught = false;
    try { (void)consume(std::move(adopted), true); }
    catch (int value) { caught = value == 7; }
    // borrowed/raw are not used after consume destroys the batch.
    if (!caught || adopted || Batch::live != 0 || Batch::destroyed != 1)
        return 5;
    if (consume(std::make_unique<Batch>(8), false) != 60) return 6;
    if (Batch::live != 0 || Batch::destroyed != 2) return 7;
    std::cout << "borrow does not own; transfer consumes even on failure\n";
}
```

把 `batch.hpp` 与程序放在同一目录，编译和运行：

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic unique-handoff.cpp -o unique-handoff
./unique-handoff
```

预期输出为 `borrow does not own; transfer consumes even on failure`。开头的 `get()` 没有改变 owner，移动后也没有复制 Batch；改变的是负责最后 `delete` 的句柄。`const_owner` 限制句柄本身，不把目标 Batch 变成 const，这与 G1 中 `const span<int>` 的层次区分一致。

`release()` 则走出类型提供的自动管理：它返回原指针并让 owner 为空，但不销毁对象。实验立即构造新 owner，且中间没有可抛出的工作。日常交接应直接移动 `unique_ptr`，不需要绕道裸指针；`release` 主要用于确实接管资源的外部接口，还必须确认该接口失败时责任归谁。若外部接口只是借用，就应传 `get()`，不能把借用当接管。

与之相对，`reset()` 会替换拥有的指针并清理旧资源。[release 与 reset 的规定](https://timsong-cpp.github.io/cppwp/n4950/unique.ptr.single.modifiers)并不替调用方证明新指针来源合法。**反例，不执行：** `owner.reset(owner.get())` 不是无害的自赋值，它可能删除目标后仍保存那个指针，后续再次访问或析构都出了问题。

## 3 函数签名应该说明责任是否跨过调用边界

### 3.1 Handoff 的生效点早于还是晚于函数体

一次函数调用需要分别分析实参求值、参数初始化、函数体执行以及结果交付。ownership transfer 发生在哪一步，由所执行的操作决定，不由“消费函数”这个名字决定。对按值 `unique_ptr` 参数，caller 用右值初始化参数时就完成移动；callee 进入函数体时已经持有 owner。对 `unique_ptr&&` 参数，建立的只是引用，资源仍可能留在 caller 的句柄中。

这会改变失败的解释。callee 在函数体开头发现业务条件不满足时，可能尚未处理任何数据，却已经取得释放责任。若接口要求 rejection 不消耗输入，就必须把检查与交接组织成满足该后置条件的协议。G3 将进一步区分 expression category 与实际移动；这里先固定责任边界，不能把一次 throw 误当作整条调用时间线倒放。

### 3.2 失败结果不自动归还 caller 的输入

上一程序的拒绝路径揭示了一个容易忽略的区别：业务操作失败，不等于调用方仍拥有输入。按值传递 `unique_ptr` 时，参数构造已经完成交接；函数体抛异常会清理该参数，调用方的 owner 已经为空。若接口想承诺“拒绝时完全不接管”，就必须采用另一种合同，不能只给原函数换个名字。

一种设计是先同步验证借用数据，再由单独的接管操作承诺接手。另一种是接收 owner 的引用，只有满足条件时才显式移动它；这种形式需要清楚说明哪些结果会改变调用方句柄。涉及并发或可变外部状态时，验证和接管之间还可能需要原子协议，本章的单线程分步验证不能解决那个问题。

| 接口形式 | 必须说明的责任 | 本身不能保证什么 |
| --- | --- | --- |
| `const Batch&`、`span<const int>` | 在约定使用期内借用，不接管 | 不自动延寿，也不自动禁止实现保存地址 |
| `Batch*` | 可能为空的借用，是否允许空需另说 | 非空不证明目标存活 |
| `unique_ptr<Batch>` 按值 | 参数建立后接管独占责任 | 业务失败不自动归还输入 |
| `unique_ptr<Batch>&` | 允许改变调用方 owner，结果合同要具体 | 不保证一定发生交接 |
| `shared_ptr<const Batch>` 按值 | 持有一份共享拥有关系，可延长生命 | 不冻结其他可写别名，不提供数据同步 |
| `weak_ptr<Batch>` 按值 | 保存一个可尝试取得共享拥有关系的观察者 | 不承诺稍后一定取得目标 |

`unique_ptr<Batch>&&` 仍然是引用参数；绑定这个引用本身不移动 owner，只有函数内部执行相应操作才会发生交接。它适合某些接收协议，但不能仅凭 `&&` 就断言资源已转移。相反，按值参数让接手发生在进入函数体以前。G3 会展开表达式类别与重载规则，G2 先把接口的责任时间点讲明白。

实际封装文件或 C 库句柄时，也可以给 `unique_ptr` 配一个自定义 deleter。以 `std::unique_ptr<std::FILE, FileCloser>` 为例，`FileCloser` 应按约定调用 `fclose`，不能使用默认 `delete`。但 deleter 的返回结果不会自动成为 `unique_ptr` 的业务结果；若需要显式报告关闭失败，上一单元那样的具名操作更容易表达。资源 API 的释放协议决定包装方式，不能因为名字里有 pointer 就套用同一种清理。

## 4 shared_ptr 共享的是同一份生命管理关系

当两个独立处理者必须各自保证批次在自身工作完成以前存在时，共享所有权才有明确用途。复制 `shared_ptr<Batch>` 不复制 Batch，它让另一个句柄参与同一拥有关系。最后一个强 owner 释放这份关系时，普通 `make_shared` 案例中的 Batch 被销毁；最后释放可能发生在一个离创建点很远的位置。

实现需要保存引用计数、释放操作等共享控制信息，通常称为控制块（control block）。对象生命与控制信息的生命不完全一致：`weak_ptr` 不延长 Batch 的生命，但观察失效还需要控制信息。使用 `make_shared` 时，对象与控制信息常放在同一分配中，弱观察者可能使那块分配继续保留；这不意味着已经销毁的 Batch 又能被读取。不应把某种具体分配布局写成语言保证。

在本章的普通 `make_shared` 用法里，`weak.lock()` 成功得到临时的强 owner，失败得到空结果。它把“检查是否还能拥有”和“取得拥有关系”作为一个原子操作处理；先问 `expired()` 再通过旧裸指针访问，并没有同等保证。[weak_ptr 的观察规则](https://timsong-cpp.github.io/cppwp/n4950/util.smartptr.weak.obs)

**文件 `shared-lifetime.cpp`**

```cpp
#include "batch.hpp"
#include <iostream>
#include <memory>

int main() {
    auto owner = std::make_shared<Batch>(7);
    auto peer = owner;
    std::weak_ptr<Batch> observer = owner;
    if (owner.get() != peer.get() || Batch::live != 1) return 1;
    peer->values[0] = 11;
    if (sum(*owner) != 61) return 2;
    auto lease = observer.lock();
    if (!lease || lease.get() != owner.get()) return 3;
    std::shared_ptr<int> sequence(owner, &owner->sequence);
    owner.reset();
    peer.reset();
    if (observer.expired() || !lease || sum(*lease) != 61) return 4;
    lease.reset();
    if (observer.expired() || Batch::live != 1 || *sequence != 7) return 5;
    sequence.reset();
    if (!observer.expired() || observer.lock() ||
        Batch::live != 0 || Batch::destroyed != 1) return 6;
    observer.reset();
    std::cout << "shared object; weak lock retains; member alias retains owner\n";
}
```

第一次修改通过 `peer` 进行，`owner` 立即看到变化，说明没有独立数据副本。随后 `owner.reset()` 和 `peer.reset()` 都不是“销毁 Batch”的同义词，因为 `lease` 和 `sequence` 仍保持拥有关系。测试检查这些阶段，而不是只依赖某个时刻的 `use_count()` 数字。

`sequence` 使用了别名构造：访问指针指向 Batch 的成员，拥有关系仍与原 Batch 相同。被访问的地址与被管理对象因此可以不同。[shared_ptr 的构造合同](https://timsong-cpp.github.io/cppwp/n4950/util.smartptr.shared.const)明确区分这两件事。本例的整数成员在 Batch 存活期间保持位置，所以关系成立；若改为指向 `values[0]`，vector 重新分配仍可使这个指针失效，持有 Batch 并不会冻结其内部存储。

不要从原 owner 的 `get()` 再构造一个独立的 owning `shared_ptr` 来“多保一份”。那样不是加入原有控制块，可能形成两套都要删除同一对象的责任。正确方式是复制原 `shared_ptr`，或使用与它共享拥有关系的构造形式。类确实需要从成员函数取得同一拥有关系时，可研究 `enable_shared_from_this`，但它有对象已纳入适当共享管理等前提，不是任意 `this` 的安全包装器。

共享关系也不能替代 G1 的访问判断。除了内部容器失效，别名构造还允许保存空访问指针而继续持有资源，或在不拥有资源时保存非空指针。因此不能把 `bool(shared_ptr)`、拥有关系存在、任意目标可访问这三个命题无条件画等号。本章实验仅使用有效的普通对象与成员别名，不执行上述失效访问。

## 5 延迟使用首先改变的是使用区间

### 5.1 Closure 的生命与一次 invocation 的生命

lambda 的 closure object 保存捕获状态，执行一次 `operator()` 只是使用它的一次 invocation（调用）。把 closure 放入队列后，即使还没有调用、调用已结束或任务已取消，closure 仍可能存在；按值捕获的 owner 因而可能继续保留资源。反过来，按引用捕获的目标也不会因 closure 存在而延寿。

审查延迟任务要分别问：任务何时入队，何时最后一次使用捕获，何时销毁任务对象；取消是否只阻止执行，还是也及时释放捕获。weak_ptr 将其中一条强保留边改为可失败的获取，不消除这些事件。`lock()` 成功后取得的 shared_ptr 负责维持本次使用期，后续状态访问仍须遵守自己的同步合同。这使 lifetime management 与 work completion 保持分离，而不是用“任务结束了”含混代替二者。

### 5.2 在现有 Batch 上比较两种保留策略

同步 `sum` 返回时，调用方能知道借用已结束；把求和包装为稍后调用的任务以后，这个时间点就消失了。捕获一个裸指针或 `[this]` 只保存访问路径，不延长目标生命。调度器尚未真正引入线程，生命问题就已经存在。

下面把任务对象留在当前线程稍后调用，隔离出“任务比创建动作活得久”这一条件。第一个任务独占 Batch，任务完成一次计算后仍保留数据，直到任务对象被销毁。第二个任务只保存弱观察，目标消失时返回空结果。这两种选择对应不同的业务承诺：必须保住输入，或者目标消失就放弃本次工作。

**文件 `deferred-work.cpp`**

```cpp
#include "batch.hpp"
#include <iostream>
#include <memory>
#include <optional>
#include <utility>

int main() {
    {
        auto owner = std::make_unique<Batch>(1);
        auto task = [owned = std::move(owner)] { return sum(*owned); };
        std::optional<decltype(task)> queued(std::move(task));
        if (owner || Batch::live != 1 || (*queued)() != 60) return 1;
        if (Batch::live != 1) return 2;
        queued.reset(); // Destroying a queued task also releases its capture.
        if (Batch::live != 0 || Batch::destroyed != 1) return 3;
        // The moved-from task is never invoked.
    }
    auto owner = std::make_shared<Batch>(2);
    auto optional_task = [weak = std::weak_ptr<Batch>(owner)]
                        () -> std::optional<int> {
        auto lease = weak.lock();
        if (!lease) return std::nullopt;
        return sum(*lease);
    };
    if (optional_task() != std::optional<int>{60}) return 4;
    owner.reset();
    if (Batch::live != 0 || optional_task().has_value()) return 5;
    if (Batch::destroyed != 2) return 6;
    std::cout << "owned task retains; discarded task releases; weak task may skip\n";
}
```

这里 `optional` 只提供一个可以明确销毁任务的位置，不是线程队列。重置它会销毁闭包，再销毁闭包中的 owner；调用闭包本身不会自动清空捕获。若实际系统在队列中保留已经执行的任务，资源也可能随之保留。这个现象应从任务存储策略理解，而不是归咎于“智能指针释放不及时”。

弱任务每次都先 `lock()`，成功后把局部 `lease` 保留到本次求和完成。省略这份局部 owner，再使用之前保存的裸指针，就丢掉了刚刚建立的生命保障。相反，若队列必须处理每个被接受的输入，悄悄跳过已过期对象就违反业务合同，应让队列拥有数据或明确报告取消，不能只因为 weak 不形成环就一律选它。

真正异步系统还需要规定：提交失败时任务归谁，取消是请求还是已经停止，谁等待正在运行的任务，资源何时可以销毁。本例只覆盖任务对象的持有和销毁，不覆盖并发取消。安全的停机顺序通常需要先停止接收、再结束或排空工作、确认使用者已停止、最后释放被借用资源；具体等待、同步和故障协议由 G7/G10 展开。

## 6 回调环不是引用计数能够自动收集的对象图

引用计数解决的是“还有多少份强拥有关系”，不是“还有没有外部代码能够到达这个对象”。当 Session 保存一个回调，回调又强捕获同一个 Session，就形成一个环：外部句柄全部消失，环中的强计数仍不为零。

下面先有意建立这种**逻辑错误反例**，检查资源没有按期销毁，再通过实验保留的弱观察者取得临时 owner，主动拆环。随后改用弱捕获，检查外部 owner 消失后资源能够清理。程序不会把强环泄漏留到进程退出，也不会解引用已销毁对象。

**文件 `ownership-cycle.cpp`**

```cpp
#include "batch.hpp"
#include <functional>
#include <iostream>
#include <memory>

struct Session {
    std::shared_ptr<Batch> batch = std::make_shared<Batch>(1);
    std::function<void()> callback;
};

int main() {
    auto session = std::make_shared<Session>();
    std::weak_ptr<Session> observer = session;
    session->callback = [keep = session] { (void)sum(*keep->batch); };
    session.reset();
    bool retained = !observer.expired() && Batch::live == 1;
    {
        auto rescue = observer.lock();
        if (!rescue) return 1;
        rescue->callback = {}; // Break the edge while rescue keeps Session alive.
    }
    if (!retained || !observer.expired() || Batch::live != 0) return 2;

    session = std::make_shared<Session>();
    observer = session;
    session->callback = [weak = observer] {
        if (auto lease = weak.lock()) (void)sum(*lease->batch);
    };
    session->callback();
    session.reset();
    if (!observer.expired() || Batch::live != 0 || Batch::destroyed != 2)
        return 3;
    std::cout << "strong callback cycle observed and broken; weak edge releases\n";
}
```

这里修改强回调时，`rescue` 独立保持 Session 的生命，避免在销毁捕获的同时把当前正在访问的外层对象也销毁。弱版本把反向关系定义为观察：回调不负责让 Session 长期存活，调用期间才临时取得强 owner。这是业务关系的选择，不是把所有反向边机械替换成 weak。

若本来就是父对象严格包含子对象的树，值成员或 `unique_ptr` 加明确借用常常更容易理解。为了修一个模糊的生命问题，先把整张图改成 shared，再用 weak 修环，会让责任更难追踪。应先画出谁负责让谁活着，再选表示，而不是从指针类型倒推架构。

## 7 共享生命不提供共享可变状态的同步

把 `shared_ptr<Batch>` 传给两个线程，最多解决它们参与生命管理的方式，不会让并发修改 `values` 自动安全。需要分别分析三层对象：共享控制信息、各线程持有的句柄对象、实际 Batch 数据。标准对拥有关系的计数协作提供相应保证；同一个句柄变量的无同步读写、被指对象的数据访问仍有各自的竞争问题。[shared_ptr 的数据竞争边界](https://timsong-cpp.github.io/cppwp/n4950/util.smartptr.shared#util.smartptr.shared.general)

`shared_ptr<const Batch>` 限制的是通过这条路径修改 Batch，不会消除其他已经存在的可写别名。`use_count() == 1` 也不能证明没有裸指针借用者，更不能把一瞬间的观察升级成独占并发修改许可。这与 G1 的“访问有效性不是地址的永久属性”相呼应：拥有关系只是判断的一部分。

本单元没有启动线程，也没有 TSan 结果。延迟任务、强环和弱观察的实验支持的是生命管理模型，不能借此声明队列、并发共享对象或完整停机协议已被验证。要进入 G7，必须再引入同步关系和操作之间的顺序，而不是再复制几份 shared_ptr。

## 8 按实际责任选最简单的表示

回到最初的批次处理。同步求和只需要借用；跨作用域接管可以移动独占 owner；多个独立参与者确需分别延寿，才使用共享关系；目标消失时允许放弃的任务，可以保存弱观察。对象由谁访问，与对象由谁释放，是两张有联系但不能合并的图。

资源不总是“最后 delete 一个对象”。缓冲池租约的析构可能是归还使用权，锁 guard 的析构是解锁，线程 owner 的结束还可能涉及停止与等待。把这些理解为 RAII 的应用是合理的，但仍要逐个说明协议：例如租约必须保证池在归还时存在，线程不能在仍借用成员时任由成员先销毁。它们并没有被本章的文件或 Batch 实验自动覆盖。

### 8.1 用变化后的条件检验模型

1. 同步校验函数只读 Batch，却要求 `shared_ptr<Batch>` 参数。这个要求引入了什么原本不需要的耦合？改成引用以后还需要说明什么？
2. 按值接收 `unique_ptr` 的函数在第一条业务语句就拒绝输入。调用方能否继续使用原 owner？换成 `unique_ptr&&` 为什么不能直接得出相同结论？
3. 两个 shared_ptr 的 `get()` 相同，是否足以证明它们属于同一拥有关系？为什么不能从 `get()` 重建第二个 owning shared_ptr？
4. 一个 aliasing shared_ptr 保持 Batch 存活，但保存的是 `values.data()`。为什么扩容以后还可能不能用？若改成上面固定的整数成员，有何不同？
5. 延迟任务弱捕获目标，目标消失时返回空结果。什么业务允许这种设计，什么业务不允许？
6. 强回调环中的 Batch 在外部 owner 消失后仍然存在，为什么这不是普通借用失效？用 `use_count() == 1` 能证明并发修改安全吗？

### 8.2 推理与修正

**第一题。** 接口把读数据与共享生命管理绑定，迫使本可使用局部值或独占 owner 的调用方采用共享表示。引用能缩小依赖，但仍需承诺使用只发生在调用期间、不保存失效路径；const 不会自动实现这些约束。

**第二题。** 本例参数的移动构造已接走责任，抛异常后资源随参数销毁，调用方 owner 为空。右值引用参数只绑定到原对象，是否移动取决于函数体。调用是否成功与责任何时交接要分别写入合同，不能靠“传了 move”猜测。

**第三题。** 指针相同只说明保存的地址相同，不说明控制块身份。独立接管同一个裸指针会制造重复释放责任。应复制原有 shared_ptr，或使用明确共享原有拥有关系的构造；地址比较不是所有权证明。

**第四题。** Batch 的生命覆盖不到其每一块内部存储的稳定性。vector 重新分配后旧元素地址失效，持有 Batch 不能挽救它。固定成员在本例中随 Batch 存活且不发生重建，所以其地址稳定；两者依赖的是不同的存储关系。

**第五题。** 可选刷新、对象已消失就无须处理的通知可以采用弱观察；承诺处理所有已接收输入的队列不能无声跳过。后者应拥有输入，或把取消作为明确结果。避免环不是足以替代业务要求的理由。

**第六题。** 强环中对象仍然活着，只是释放时机违反预期；悬挂则是访问路径比目标活得更久。引用计数不能自动收集环，也不能计算裸借用者或替代同步，因此计数为 1 不构成并发独占许可。

G2 到这里建立了释放、借用、交接与共同延寿的边界。后续 G3 将转向值语义：同一个对象怎样复制、移动、赋值和返回，哪些操作建立独立值，哪些只改变资源归属，以及这些选择怎样影响成本和失败保证。
