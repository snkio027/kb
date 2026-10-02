# G7 原子操作、数据发布与槽位复用

[上一单元](g07-shared-state-and-shutdown.md)把读数、索引和退出状态放进同一把锁下。mutex 同时提供排他访问和同步关系，因此我们可以按状态变化逐步推导队列行为。现在把问题缩小：只有一个生产者和一个消费者，只共用一个 Reading 槽位。能否不用 mutex，仍然明确知道谁可以读、谁可以写、何时能覆盖旧值？

这个问题比“atomic 是否比锁快”更适合进入原子操作。我们先定义访问权限和交接顺序，再选择需要的内存序。整个单元没有性能排名；一个没有 mutex 的程序也可能忙等、争用缓存行，或依赖并不无锁的底层实现。语言正确性仍然先于机器成本。

## 1 原子对象提供什么，不提供什么

### 1.1 单个访问的不可分割性

原子操作（atomic operation）使针对同一原子对象的相应访问不可分割。load 读取值，store 替换值，读改写操作（read-modify-write，RMW）把读取与修改组成一个原子步骤。`fetch_add`、成功的 compare-exchange 都属于后者。

这种不可分割性不自动向外扩展。两个 atomic 对象不组成一个事务；atomic 指针也不自动延长所指对象的生命周期。即使每个字段单独都是 atomic，读者仍可能得到不同轮次的字段组合。要读一致快照，必须说明版本、重试、不可变对象或锁怎样把多个字段联系起来。

每个原子对象的修改具有自己的修改序（modification order），同一对象的写入和读改写在该顺序中排列。不同对象的修改序并不自动合并成整个程序的单一时间线。对同一个原子对象，标准还规定了读取与修改相对于 HB 的一致性约束；例如本线程一次写入先于后面的读取，后读不能再取该写入之前的旧修改值。relaxed 不会删除这些单对象规则。[N4950：原子顺序](https://timsong-cpp.github.io/cppwp/n4950/atomics.order)、[一致性规则](https://timsong-cpp.github.io/cppwp/n4950/intro.races)

### 1.2 原子的计数仍可能丢失更新

把计数器声明成 atomic，然后做 load、计算、store，并不等价于 fetch_add。两个线程都可以先读到零，再各自写入一。每个访问合法且不可分割，但第二次 store 覆盖的不是“一次新的增量”，而是根据过期值算出的同一个结果。

下面用 barrier 让两个线程都完成初始 load 后才继续。这样旧值必为零，丢失更新不是靠碰运气复现。普通模式用 CAS 重试，`--broken` 模式故意使用错误的 load/store 组合。两个模式均没有 data race，错误模式的非零退出来自业务判据，而不是未定义行为。

**完整实验 G7-A1 · `cas-counter.cpp` · 复合更新与确定性逻辑反例**

```cpp
#include <atomic>
#include <barrier>
#include <iostream>
#include <string_view>
#include <thread>

int main(int argc, char** argv) {
    const bool broken = argc == 2 && std::string_view(argv[1]) == "--broken";
    if (argc != 1 && !broken) return 64;
    std::atomic<unsigned> count{0};
    std::barrier loaded(2);
    auto increment = [&] {
        unsigned expected = count.load(std::memory_order::relaxed);
        loaded.arrive_and_wait();
        if (broken) {
            count.store(expected + 1, std::memory_order::relaxed);
        } else {
            while (!count.compare_exchange_weak(expected, expected + 1,
                       std::memory_order::relaxed, std::memory_order::relaxed)) {
                // A failed comparison updates expected; recompute desired each time.
            }
        }
    };
    std::jthread worker(increment);
    increment();
    worker.join();
    if (count.load(std::memory_order::relaxed) != 2) {
        std::cout << "lost update rejected\n";
        return 21;
    }
    std::cout << "cas count=2 verified\n";
}
```

barrier 在本实验中只是让两个初始读取完成后再进入竞争步骤，没有把之后两次修改串行化。join 使主线程在检查最终计数前等待另一线程完成。错误模式按所选输入固定得到一；正确模式若正常完成，则得到二。这是区分两种算法的判据，不是对任意 CAS 循环的进展保证。[N4950：barrier](https://timsong-cpp.github.io/cppwp/n4950/thread.barrier.class)

### 1.3 compare-exchange 的 expected 是输入也是输出

CAS 比较原子对象与 expected 的表示；对本例的 unsigned 整数可以直接按数值理解。成功时写入 desired，失败时把读到的原子值写回 expected。下一次尝试必须基于这个新值重新计算 desired。若把 desired 永久固定为最初的 `expected + 1`，一次失败后即使重试成功，也可能把计数写回不正确的值。

weak 允许比较相等时伪失败，所以通常放在重试循环中；strong 不允许这种伪失败，但仍可能因为值已改变而失败。strong 并不让“比较、失败后做其他工作、再尝试”的整个算法成为事务。对含填充位或多种表示的类型，还要阅读值表示比较的完整规定，不用整数案例替代所有类型的规则。

成功的 CAS 是 RMW，失败的 CAS 只是一次读取。因此双内存序参数分别描述成功和失败路径；失败序不能是 release 或 acq_rel。这里采用两条 relaxed 路径，因为 count 只记录数量，不发布其他数据。不要将旧标准对失败序的其他限制不加版本区分地写进 C++23 合同；本章只使用清楚匹配用途的组合。[N4950：原子类型操作](https://timsong-cpp.github.io/cppwp/n4950/atomics.types.operations)

## 2 内存序描述操作之间的约束

### 2.1 从读取标志推导到读取数据

假设生产者先写普通 Reading，再对原子标志执行 release store；消费者执行 acquire load，并且确实读到了这次发布写入的值。这个读取关系建立 release 到 acquire 的同步边，于是先前的数据写入通过 SB、SW、SB 形成到后续数据读取的 HB 链。消费者可以按这个协议读取 Reading，而不需要把它的每个字段都改成 atomic。

```text
生产者                           消费者
payload = reading
       │ SB
full.store(true, release) ── SW → full.load(acquire) 读到这次 true
                                          │ SB
                                     local = payload
```

条件里的“读到这次写入”不能省略。仅仅两端分别写了 release/acquire，不证明它们已经配对；操作不同的原子对象，或者 load 读到另一个不具备所需发布关系的值，都需要重新推导。完整规则还允许 acquire 从以该 release 为首的 release sequence 中取值；本章不用这条推广来隐藏中间步骤。

在 C++23 中，release sequence 是同一原子对象修改序中以 release 操作为首、随后连续由 RMW 构成的序列；不要把早期版本对同线程普通写的描述混入本版本。它有助于解释接力式发布，但不授予任意第三方修改 payload 的权限。

### 2.2 各种内存序不是性能等级

| 操作用途 | 本章选用的顺序 | 仍需证明的事 |
| --- | --- | --- |
| 独立计数或单对象原子更新 | relaxed | 复合操作是否需要 RMW，计数是否溢出 |
| 发布已经写完的数据 | release store | 发布前的数据访问由谁独占 |
| 接收发布后读取数据 | acquire load | 读到了哪次发布，数据何时可复用 |
| RMW 同时接收此前状态并发布后续状态 | acq_rel | 成功／失败路径及读到的发布来源 |
| 需要更易推理的 SC 原子次序 | seq_cst | 普通对象的访问仍无竞争，混合弱序另行分析 |

load 不能指定 release/acq_rel，store 不能指定 acquire/acq_rel；它们没有那一半操作可以承担相应作用。默认的 seq_cst（顺序一致序）为 SC 操作建立受标准约束的单一总序，并包含相应 acquire/release 效果。它不会把多个操作合成事务，也不会把未同步访问的普通对象变安全。将 SC 与弱序操作混用时，更不能把程序简单当成全部动作的一条总序。

选择 relaxed 需要指出究竟不依赖哪条跨对象同步关系，而不只是因为它名字看起来“轻”。选择 seq_cst 通常能降低初次推理负担，但不是性能结论。机器指令、争用、读写比和调度都会影响成本，本批不通过耗时决定哪种顺序正确。

### 2.3 “可见性”不能替代访问权限

release/acquire 常被简称为“让另一个线程看见数据”。更完整的说法是：满足读取关系时，它们约束相应求值的先后，使普通数据的访问符合语言规则。它既不是快照复制，也不是互斥锁。如果生产者发布后立即再修改同一个 payload，而消费者还在读，就缺少防止覆盖的反向关系。

类似地，acquire 到一个指针只解决此前初始化怎样到达读者的问题，不保证指针所指对象还活着。节点从某个原子链表摘除后，可能仍有读者保留旧指针；回收需要独立协议。G1 的访问有效性、G2 的释放责任，没有被一个 acquire 取代。

## 3 一个槽位需要两次交接

### 3.1 把 full 解释成访问阶段

单槽协议规定：只有一个生产者写 payload，只有一个消费者读 payload。full 为 false 时，生产者可以写下一条；写完后 release 发布 true。消费者 acquire 观察到 true 后复制完整 Reading，复制结束后 release 发布 false，交还槽位。生产者 acquire 观察到这次 false 后，才能覆盖旧内容。

```text
write(n)
   │ SB
store true (release) ── SW → load true (acquire)
                                    │ SB
                                 read(n)
                                    │ SB
load false (acquire) ← SW ── store false (release)
   │ SB
write(n+1)
```

第一条同步链保护本轮发布，第二条保护下一轮复用。消费者把数据复制到自己的 local 以后，可以先归还槽位，再处理 local；此时生产者与消费者操作的是不同对象。若 local 改成引用或 span 指向槽位，再归还槽位就没有实现这种分离。

### 3.2 为什么 bool 在这个限定协议里足够

full 的值会反复经历 false、true、false，不能只看布尔值就认为任何时候都安全。这里还依赖单生产者、单消费者和每一轮严格交替：生产者在自己上一轮 true store 之后的 load，受同对象一致性约束，不能回读那之前的 false；它必须等到后续消费者归还的 false。消费者同理不能在自己上一轮 false store 后回读更早的 true。由初始状态开始归纳，才能把观察到的标志对应到当前交接轮次。

如果增加第二个生产者，两人都可能看到 false 后同时写 payload；如果允许生产者不等归还而覆盖“最新值”，也破坏了归纳前提。把 bool 改成序号可以帮助检测代次，但序号本身并不允许对普通 payload 进行无同步读写。所谓 seqlock 风格的“读完发现版本变了就重试”，不能用事后重试抹去已经发生的 C++ 数据竞争。

**完整实验 G7-A2 · `slot-handoff.cpp` · 双向发布与逐代完整值检查**

```cpp
#include <atomic>
#include <iostream>
#include <thread>

struct Payload {
    unsigned id;
    unsigned value;
};

int main() {
    constexpr unsigned count = 20000;
    Payload payload{};
    std::atomic<bool> full{false};
    unsigned mismatches = 0;
    std::jthread producer([&] {
        for (unsigned id = 1; id <= count; ++id) {
            while (full.load(std::memory_order::acquire)) std::this_thread::yield();
            payload = {id, id * 17U + 3U};
            full.store(true, std::memory_order::release);
        }
    });
    std::jthread consumer([&] {
        for (unsigned id = 1; id <= count; ++id) {
            while (!full.load(std::memory_order::acquire)) std::this_thread::yield();
            Payload local = payload;
            full.store(false, std::memory_order::release);
            if (local.id != id || local.value != id * 17U + 3U) ++mismatches;
        }
    });
    producer.join();
    consumer.join();
    if (mismatches != 0 || full.load(std::memory_order::relaxed)) {
        std::cout << "slot value rejected\n";
        return 31;
    }
    std::cout << "slot generations=20000 verified\n";
}
```

本实验约定两条线程成功创建并各完成固定轮数，不是支持任意异常退出的通用通道。如果消费者提前离开，生产者可能永远等待；若第二条线程启动失败，也需要额外的停止与收束协议。上一单元处理的 close/abort 没有因为去掉 mutex 而自动继承到这里。测试遇到运行超时会失败，不会把不完成称为“安全的无锁实现”。

不匹配时消费者仍完成交接循环，最后才报告失败，避免测试自身在发现错误值后阻塞生产者。错误变体只损坏 value 的计算，保留同步，预期得到指定拒绝码；它检验的是完整值判据。删除 acquire 或提前归还槽位属于可能引入 data race 的改变，不应拿普通运行时是否刚好读错作为标准规则的 oracle。

## 4 从单槽推到队列时增加了什么

### 4.1 SPSC 的两个游标仍是两次交接

一个生产者、一个消费者的环形队列可以让生产者独占写入游标，消费者独占读取游标。发布写入位置告诉消费者哪些槽位已经准备好；发布读取位置告诉生产者哪些槽位已经可复用。原子游标不是全部共享状态，数组元素仍依赖这两条同步链。

容量判定还必须区分空与满，例如保留一个空槽，或者使用能区分轮次的计数方案。序号溢出、索引取模、读取游标的新旧程度以及取得元素时的复制／移动异常，都需要明确前提。单槽案例揭示证明结构，没有实现或验证完整 SPSC ring。

从 SPSC 增加到多生产者以后，一个写入游标不能再由单线程独占。预留位置与填充完成之间还可能有窗口：先抢到位置的生产者尚未写完，后面的生产者已经完成。消费者必须辨认每个位置是否真的可读，不能只根据一个推进的尾指针读取所有前面的槽位。生产级 MPSC／MPMC 算法的困难在这里，而不只是把 `++index` 换成 CAS。

### 4.2 ABA 与回收是不同的障碍

CAS 只比较当前表示。某个指针经历 A→B→A 后，比较仍可能成功，却已不是原来那次观察的逻辑历史，这通常称为 ABA。代次标签可以让部分历史变化可检测，但需要考虑标签宽度和回绕；它没有自动保持所指对象的生命。

即使从未发生 ABA，另一个线程也可能正在解引用被摘除的节点，因此“成功摘链”仍不等于“可以立即 delete”。hazard pointer、epoch 等方案承担读者保护和延迟回收责任，不能仅凭指针相等或 CAS 成功推出安全释放。本章到此建立问题边界，具体回收算法不挤入这条阅读主线。

### 4.3 不加锁不等于非阻塞进展

算法常用的进展术语需要说明考察的是哪个操作：lock-free 通常要求参与者持续执行算法步骤时，系统中仍有操作完成，允许某一参与者长期失败；wait-free 进一步要求每个参与者的操作在有限个自身步骤内完成，步数上界可以依赖输入规模。obstruction-free 的条件更弱，只要求获得足够长的独占执行机会时能够完成。这些是算法层面的进展分类，不是实时截止期承诺，也不表示操作系统必须在固定时间内调度某条线程。

`is_lock_free()` 只回答某种原子对象操作的实现性质，不证明使用它的整个算法具有该性质。单槽中的 push 若必须等待消费者归还，即使底层 bool 原子是 lock-free，这个等待对等方的操作也不能据此称为 lock-free。分配器、回收机制和隐藏的系统调用也可能成为进展依赖。[N4950：前进保证](https://timsong-cpp.github.io/cppwp/n4950/intro.progress)

需要减少忙等时，C++20 起的 atomic wait/notify 可以等待值变化，但仍需设计状态谓词和退出路径；值先变走再变回的瞬时变化可能无法被观察到，不能将其当作事件计数器。notify 不是 release store 的替代品。本批不增加另一套 wait 实现，避免把同步证明与调度策略同时换掉。[N4950：原子等待](https://timsong-cpp.github.io/cppwp/n4950/atomics.wait)

## 5 动态检测能提供哪一层证据

### 5.1 先用已知竞争确认检测通道

ThreadSanitizer（TSan）通过插桩和运行时跟踪帮助发现数据竞争。它不能穷举所有调度，也不能证明业务协议、内存回收和关闭设计正确。一次没有诊断的运行应记录为 CLEAN_OBSERVED，而不是“线程安全已经证明”。[Clang：ThreadSanitizer](https://clang.llvm.org/docs/ThreadSanitizer.html)

下面是故意存在未定义行为的阳性对照，只允许由执行器编译为 TSan 独立进程并受控运行。两次写入都在 barrier 之后，彼此之间没有 HB 关系；join 发生在这些访问之后，不能追溯消除已经发生的竞争。不要在非插桩模式运行它，更不能照搬为共享状态的实现。

**危险反例 G7-D1 · `race-control.cpp` · data race／未定义行为，仅限 TSan 阳性对照**

```cpp
#include <barrier>
#include <iostream>
#include <thread>

int main() {
    int shared = 0;
    std::barrier start(2);
    std::jthread worker([&] {
        start.arrive_and_wait();
        shared = 1;
    });
    start.arrive_and_wait();
    shared = 2;
    worker.join();
    std::cout << "undetected race value=" << shared << '\n';
}
```

执行器先确认 TSan 的安全探针能够编译运行，再要求本反例报告 `ThreadSanitizer: data race` 并返回指定退出码 66。超时、普通崩溃或其他错误不满足这个判据。只有工具通道成立后，正常实验的无诊断结果才记入动态检测证据；不可用或阳性对照失败会保留 SKIP／FAIL，不能换个说法混入通过数量。

### 5.2 不用压力测试代替内存模型

release/acquire 的合法性来自同步规则与具体读取关系，单槽的轮次来自状态归纳。运行 20000 轮只能说明这些执行中字段与代次一致，不能证明别的处理器、编译器或调度下没有问题。相反，错误实现只要找到一个符合前提的反例就足以被否定；正反两类证据的力量不对称。

本批分别保留人工协议推导、普通运行、有限 stress、错误变体和 TSan。没有运行模型检查器、硬件弱序 litmus suite、性能基准或完整 lock-free 队列测试。尤其不以“某个弱序结果没有出现”宣称该结果被标准禁止。

## 6 迁移题

1. 两个线程各做一次 relaxed load 后 store 加一，没有 data race，为什么仍可能得到一？换成 seq_cst load/store 能修复吗？
2. CAS 第一次失败后，为什么必须重新计算依赖 expected 的 desired？
3. 生产者 release 发布 true，消费者 relaxed 读到 true 后读普通 payload，当前证明少了哪条边？
4. 消费者 acquire 读到 true 后，先归还 false，再通过引用读取 payload，为什么与复制到 local 不同？
5. 单槽使用 bool 没有代次字段，为什么仍可论证逐轮对应？增加第二个生产者后哪项前提消失？
6. 指针 CAS 成功且 `is_lock_free()` 为 true，能否立即释放旧节点并宣称算法是 lock-free？

## 7 推理答案

1. 两次读取可以都观察零，两次写入都写一；原子性只覆盖单个操作。seq_cst 可以约束这些操作的总序，仍允许两个 load 在两个 store 之前，不能把分开的步骤变成 RMW。应选择 fetch_add、正确的 CAS 重试或更大范围的锁协议。
2. 失败会把实际读到的值写回 expected。如果 desired 沿用旧计算，后续 CAS 成功时提交的就不是对最新值的正确变换。对于有副作用的计算，还要进一步保证重试不会重复执行不可回滚的外部动作。
3. relaxed load 不承担 acquire 接收，不能按当前发布协议建立 release 到它的 SW。读到 true 这个数值本身不等于获得普通数据的同步许可。实验偶尔打印正确值不能填补缺失的规则前提。
4. 归还之后生产者可以开始覆盖槽位。独立 local 的复制已在归还前完成，后续处理不再碰共享 payload；引用仍指向共享对象，读与下一轮写可能没有 HB，造成数据竞争。指针和视图都不能靠改名获得独立快照。
5. 两方各自上一轮 store 与后续 load 的同对象一致性，加上严格交替和单写入者阶段，排除了观察本轮之前的过期标志。第二个生产者可以同时看到空槽，两人获得的并不是互斥写权限，这时 bool 协议不再成立。
6. 不能。CAS 成功只说明比较并修改了指针表示，既不排除 ABA，也不证明所有读者已经结束。原子操作无锁也不证明分配、重试、等待和回收组成的完整操作有进展保证。分别给出生命期证明与算法进展论证，不能用一个属性覆盖两者。

## 8 本单元留下的审查方法

面对新的原子算法，先列普通共享对象、原子状态和各阶段的访问者，再画出发布与复用的 HB 路径。随后检查失败重试是否保留业务意义、生命期如何结束、等待依赖谁推进。最后才选择动态工具检验实现是否违反已经写清的协议。这个次序承接 G1 的访问、G2 的责任和 G6 的成本，而不是另建一套脱离对象模型的“原子编程技巧”。

全部命令、工具链、摘要和未验证项见 [G7 验证说明](g07-verification.md)。目前两单元是 Content v2 新稿，等待精读接受；正文和实验完成不等于章节已经冻结，也不构成 PDF 或跨平台验收。
