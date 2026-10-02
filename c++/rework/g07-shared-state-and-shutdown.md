# G7 共享状态、条件等待与退出协议

前面几章处理读数时，程序通常只有一条控制流：读入一批数据，变换、查找，再释放资源。现在让采集线程持续产生 Reading，让工作线程取出并处理。单线程时正确的容器操作放进两个线程以后，为什么仍可能出错？即使给每次读写加锁，为什么程序还可能永远退不出来？

这两个问题对应不同层次。语言要求相互冲突的访问具有适当的同步关系；业务还要求一次操作看到完整状态，并且每个等待都有能够使它结束的状态变化。本单元先建立这些关系，再实现一个容量有限、能够排空和中止的通道。[下一单元](g07-atomics-and-publication.md)改变同步机制，但沿用相同的责任划分。我们不在这里扩建线程池，也不把成功启动几个线程当作并发模型已经成立。

## 1 从共享变量到同步关系

### 1.1 对象存在，不代表可以同时访问

G1 的存储、生命周期和类型化访问规则继续有效。并发额外要求回答：其他线程能否在这次访问期间修改或销毁同一片对象存储？地址、类型和所有者都正确，不能排除这种冲突。

C++ 的内存位置（memory location）是非位域的标量类型对象，或连续的非零宽度位域组成的最大序列。它不是缓存行；两个普通 int 成员可以属于不同内存位置，即使恰好落在同一缓存行。前者影响语言层面的数据竞争判定，后者可能影响 G6 所说的伪共享成本。容器中的不同元素也不能一概按物理字节独立推断，位压缩表示和容器自身的结构修改还需要各自的合同。[N4950：内存位置](https://timsong-cpp.github.io/cppwp/n4950/intro.memory)

相互冲突的求值不仅包括对同一内存位置的读写、写写，还包括对象生命周期开始或结束与重叠存储上的相关访问。另一线程析构对象，并不会因为它“不是给字段赋值”而绕过同步要求。两个线程都只读已经安全发布、期间也不被修改或销毁的数据，则没有这种读写冲突。

### 1.2 三种关系各自回答什么

顺序先于（sequenced-before，后文简称 SB）描述同一线程内求值之间由语言规定的偏序。例如两个独立完整表达式先后执行，前一个完整表达式的求值先于后一个。它不等于“源码左边永远先于右边”；一个表达式内部的求值次序仍需按该表达式的规则判断。[N4950：求值顺序](https://timsong-cpp.github.io/cppwp/n4950/intro.execution)

同步于（synchronizes-with，SW）由具体同步操作建立跨线程关系。例如对同一个 mutex，解锁与随后取得其所有权的加锁之间存在同步关系。普通函数先后被调用、两个日志的时间戳有先后、一个线程睡得更久，都不能自行建立这样的边。

先发生于（happens-before，HB）把线程内的顺序与线程间的同步连接起来。本章不使用 `memory_order_consume`；在这一范围内，可以用 SB、SW 及其传递闭包推导 HB。这对应 N4950 中 simply happens before 与 happens before 相同的情形，不是删除 consume 规则后给整个 C++ 重新下定义。

```text
采集线程                           工作线程
写入读数
   │ SB
unlock(m) ───────── SW ────────→ lock(m) 成功
                                     │ SB
                                  读取读数

因此：写入读数 HB 读取读数
```

这里的“可见”有规则上的含义：在普通标量对象的读之前，HB 关系及中间写入的约束决定其可见副作用。不能把它理解成“某条指令把所有缓存都刷新了”。HB 也不是挂钟时间上的总排序；没有建立关系的两个动作，不能仅凭某次运行中谁先打印来补上一条边。[N4950：竞争与顺序关系](https://timsong-cpp.github.io/cppwp/n4950/intro.races)

### 1.3 数据竞争与协议错误不是同义词

就本章的普通多线程程序而言，如果存在两个潜在并发、相互冲突的动作，至少一个不是原子操作，且双方没有 HB 先后关系，就发生数据竞争（data race），行为未定义。这里不讨论信号处理函数的特殊规则。把变量写成 volatile 不会提供线程间的互斥或同步，也不会把普通复合操作变成原子操作。

协议错误可以没有数据竞争。例如先在锁内检查队列非空，解锁后再加锁取队首：每次容器访问都受保护，但别的消费者可能在两次加锁之间取走最后一项。错误在于“检查与消费同一个状态”的操作被拆开了。另一个例子是两个原子 load/store 组成的加一，单个访问都原子，整个读改写却可能丢失更新；下一单元会确定性复现它。

因此，审查顺序应当是先找共享对象及冲突访问，再找同步边，最后检查业务不变量和进展条件。没有 data race 只是其中一层，不自动保证没有丢任务、死锁、饥饿或重复处理。

## 2 用一个锁保护完整不变量

### 2.1 临界区保护的是关系

互斥量（mutex）允许一个线程在临界区内独占受保护状态。所有访问者必须遵守同一个约定；给写端加锁、读端直接读取，或者两端各锁不同对象，都不能保护这份共享状态。锁本身也需要先构造，并在所有使用者结束后才能销毁。

通道不只包含数组。它还有队首、元素数、接收状态和交接计数。它们共同表达“哪些槽位含有有效待取数据”。若只把 `size` 改成 atomic，数组内容与索引之间的关系并不会随之成为一次不可分割的操作。

一个操作具有线性化点（linearization point），是指可以在其调用与返回之间选出一个逻辑生效瞬间，使并发操作的结果符合相应的顺序合同。这是我们分析接口的方法，不是说每段临界区只生成一条机器指令。通道的成功提交在锁内完成元素写入和计数更新后生效；取出、关闭和中止也在同一把锁下作出决定。因此并发提交与关闭谁先获得这次状态修改机会，决定该次提交被接收还是拒绝。

`lock_guard` 适合覆盖整个作用域的加锁；`unique_lock` 还支持显式解锁以及交给条件变量临时释放、重新获得所有权。两者管理锁的释放责任，不替程序员选择正确的锁范围。临界区里调用任意用户回调尤其危险：回调可能再次取得同一把锁，也可能进行无界等待。取出工作后再处理，通常比在通道锁内执行工作更容易分析。[N4950：mutex 合同](https://timsong-cpp.github.io/cppwp/n4950/thread.mutex.requirements.mutex)

### 2.2 先说明通道状态

本例传递按值复制的 Reading，不把指向内部槽位的引用交给消费者。成功提交表示通道接收了一份值；成功取出表示这份值已经交给调用方。它不表示业务处理成功，更不承诺外部副作用恰好执行一次。

| 状态 | 提交 | 取出 | 后续变化 |
| --- | --- | --- | --- |
| open | 有空间则接收，否则等待 | 有数据则交付，否则等待 | 可 close 或 abort |
| closing | 拒绝 | 交付已有数据，空后返回 drained | 可升级为 abort |
| aborted | 拒绝 | 返回 aborted | 保持终态 |

`close()` 是排空请求：停止接收，但保留队列里已经接收的数据。`abort()` 是放弃尚未交付的数据：清空队列并唤醒等待者。已经交给调用方的工作不受队列控制，中止不能将其撤回。真正的运行时还要规定在途工作的取消和失败处置，这属于 G10 的组合问题。

在计数未溢出、同步设施正常工作的前提下，通道维持两个不变量：`0 <= queued <= capacity`，以及 `accepted = queued + delivered + discarded`。第二式中 delivered 是已交付，不是已完成。对失败结果的统计如果需要放进同一方程，必须在更外层增加在途、成功、失败等状态，不能偷偷改变这个字段的含义。

## 3 等待条件，而不是等待一次通知

### 3.1 条件变量怎样封闭检查与等待的窗口

条件变量（condition variable）不存储“通知余额”。它帮助线程在条件不满足时释放锁并等待；醒来以后，线程重新取得锁，再判断共享状态。等待可能被通知唤醒，也可能伪唤醒；一次通知还可能让多个竞争者重新争锁，先获得锁的人已经消耗了条件。因此返回等待本身不是继续工作的许可。

带谓词的 `wait(lock, pred)` 等价于在谓词不成立时反复等待。谓词及影响它的非原子状态都在同一把 mutex 下访问。`wait` 的解锁并进入等待是原子阶段，随后重新加锁；通知与这些阶段在同一条件变量上有标准规定的顺序。这使“在锁内检查不满足，再释放锁开始等待”不留下一个可被正常状态更新漏过的检查窗口。[N4950：condition_variable](https://timsong-cpp.github.io/cppwp/n4950/thread.condition.condvar)

生产者等待的条件不是只有“队列有空间”，还必须包括“通道已不再接收”；消费者等待的条件不是只有“队列有数据”，还必须包括“通道已结束”。否则 close 改了状态并发出通知，线程重新检查谓词仍为 false，又睡回去，退出就无法完成。

### 3.2 通知与数据发布各负什么责任

修改共享状态时持锁，改完解锁，再通知，是本例采用的顺序。数据发布由同一 mutex 的解锁／加锁关系承担；通知负责让等待者有机会重新检查条件。通知并不替代保护数组与索引的锁。

一次提交只新增一个可消费元素，一次取出只新增一个空位，因此分别唤醒一名对端等待者。关闭或中止改变所有等待者的退出条件，必须让两类等待者都有机会醒来，所以通知两个条件变量上的所有等待者。通知并不提供公平调度，也不保证某个线程在固定时限内取得锁。

**共享实现 G7-Q · `channel.hpp` · 固定存储的有界值通道**

```cpp
#pragma once
#include <array>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <stdexcept>

struct Reading {
    unsigned id;
    unsigned value;
};

enum class State { open, closing, aborted };
enum class Take { item, drained, aborted };

struct Snapshot {
    State state;
    std::size_t queued, waiting_push, waiting_pop, peak;
    std::uint64_t accepted, delivered, discarded;
};

class Channel {
    std::mutex mutex_;
    std::condition_variable not_empty_, not_full_;
    std::array<Reading, 8> slots_{};
    const std::size_t capacity_;
    std::size_t head_{}, size_{}, waiting_push_{}, waiting_pop_{}, peak_{};
    std::uint64_t accepted_{}, delivered_{}, discarded_{};
    State state_{State::open};

public:
    explicit Channel(std::size_t capacity) : capacity_(capacity) {
        if (capacity == 0 || capacity > slots_.size())
            throw std::invalid_argument("capacity");
    }

    bool push(Reading reading) {
        std::unique_lock lock(mutex_);
        if (state_ == State::open && size_ == capacity_) {
            ++waiting_push_;
            not_full_.wait(lock, [&] {
                return state_ != State::open || size_ < capacity_;
            });
            --waiting_push_;
        }
        if (state_ != State::open) return false;
        slots_[(head_ + size_) % capacity_] = reading;
        ++size_;
        ++accepted_;
        if (size_ > peak_) peak_ = size_;
        lock.unlock();
        not_empty_.notify_one();
        return true;
    }

    Take pop(Reading& output) {
        std::unique_lock lock(mutex_);
        if (state_ == State::open && size_ == 0) {
            ++waiting_pop_;
            not_empty_.wait(lock, [&] {
                return state_ != State::open || size_ != 0;
            });
            --waiting_pop_;
        }
        if (state_ == State::aborted) return Take::aborted;
        if (size_ == 0) return Take::drained;
        output = slots_[head_];
        head_ = (head_ + 1) % capacity_;
        --size_;
        ++delivered_;
        lock.unlock();
        not_full_.notify_one();
        return Take::item;
    }

    void close() {
        {
            std::lock_guard lock(mutex_);
            if (state_ == State::open) state_ = State::closing;
        }
        not_empty_.notify_all();
        not_full_.notify_all();
    }

    void abort() {
        {
            std::lock_guard lock(mutex_);
            state_ = State::aborted;
            discarded_ += size_;
            size_ = 0;
        }
        not_empty_.notify_all();
        not_full_.notify_all();
    }

    Snapshot snapshot() {
        std::lock_guard lock(mutex_);
        return {state_, size_, waiting_push_, waiting_pop_, peak_,
                accepted_, delivered_, discarded_};
    }
};
```

数组在通道构造时就存在，Reading 的复制不抛异常；临界区内不分配、不执行用户代码。失败的 pop 不修改 output。中止只是从协议上丢弃槽位中的值，并不提前结束数组元素的生命周期；对持有其他资源的复杂任务，清理行为及其锁内成本必须重新设计，不能直接推广本例。

`waiting_push`、`waiting_pop` 和 peak 是教学验证用的观测字段，和其他状态受同一把锁保护。它们让测试确认某类线程已进入等待路径，不是通道正确性依赖的信号。例子不提供同步设施故障恢复：mutex／wait 抛出异常后的观测计数恢复、线程创建资源耗尽等不在本实现的运行合同内，也不宣称 close/abort 是绝不会失败的通用清理函数。

## 4 从实现逐步推导协议

### 4.1 初始化、交付与复用

通道先构造，再启动借用它的线程。线程构造与新线程启动之间的标准同步关系使初始化可供新线程使用。运行阶段，所有 slots、head、size 和 state 的访问都持有同一把锁；push 完成写入后解锁，pop 取得锁后复制该值，因此建立了写入到读取的 HB 路径。pop 在解锁前把值复制到调用方独立对象，再减少 size；下一次 push 取得锁以后才能覆盖释放的槽位。于是复用也有“读完旧值 HB 写入新值”的方向。

这两个方向缺一不可。发布保证消费者不会过早读；复用保证生产者不会过早覆盖。mutex 同时建立两者，容易让人忽略第二条边。下一单元去掉锁后，必须显式重新证明它。

### 4.2 状态与计数的归纳检查

初始队列为空，三种累计计数均为零。成功 push 只在 open 且有空间时进行，同时增加 queued 和 accepted；成功 pop 减少 queued 并增加 delivered；abort 将当前 queued 加入 discarded，然后清零。close 不改变计数。因此每一步都保持计数等式。拒绝和终态返回不改变这些数。

同一 mutex 将这些状态变化串行化，并不决定多个生产者之间按业务编号的先后顺序。FIFO 保留的是成功入队的逻辑顺序；两个生产者谁先到达该生效点，可能与它们生成编号的顺序不同。全局编号顺序若是业务要求，必须增加重排或上游排序协议。

### 4.3 安全性不等于一定完成

容量不越界、值不被并发覆盖属于安全性（safety）：坏事不会发生。等待最终返回属于活性（liveness）：某个进展最终发生。上述状态推导在语言同步规则下说明安全性和唤醒条件，没有证明调度公平性或最大延迟。

消费者不取数据时，满队列的生产者可以一直等。关闭必须由仍能执行的参与者发起；如果主线程先 join 一个等待满队列的生产者，却没有消费者，也没有先 close/abort，程序会按错误的依赖关系互等。即使所有字段都受锁保护，死锁仍然成立。多个锁还需要一致的获取次序；同时取得一组互斥量可以使用 `scoped_lock` 的相应协议，但它不能解决锁外的任务依赖环。

## 5 确认等待已经发生，再测试退出

下面的测试先让容量为一的通道装满，或让消费者面对空通道。主线程反复取得受锁保护的快照，直到看到等待计数。没有其他参与者能满足数据条件，因此这是实际进入等待路径的证据，而不是根据时间猜测调度。若线程始终不能到达该状态，外部执行器会超时并报告失败；超时不是成功退出的替代结果。

**完整实验 G7-Q1 · `channel-contract.cpp` · 排空、中止、阻塞退出与计数合同**

```cpp
#include "channel.hpp"
#include <initializer_list>
#include <iostream>
#include <thread>

int fail(int code) {
    std::cout << "contract failure=" << code << '\n';
    return code;
}

bool balanced(Snapshot s) {
    return s.accepted == s.queued + s.delivered + s.discarded &&
           s.waiting_push == 0 && s.waiting_pop == 0;
}

int main() {
    Reading out{99, 99};
    Channel ordinary(2);
    if (!ordinary.push({1, 17}) || !ordinary.push({2, 34})) return fail(1);
    ordinary.close();
    ordinary.close();
    if (ordinary.pop(out) != Take::item || out.id != 1 || out.value != 17)
        return fail(2);
    if (ordinary.push({3, 51})) return fail(3);
    if (ordinary.pop(out) != Take::item || out.id != 2 || out.value != 34)
        return fail(4);
    if (ordinary.pop(out) != Take::drained || out.id != 2 || out.value != 34)
        return fail(5);
    if (!balanced(ordinary.snapshot())) return fail(6);

    for (bool aborting : {false, true}) {
        Channel full(1);
        if (!full.push({10, 20})) return fail(7);
        bool accepted = true;
        std::jthread producer([&] { accepted = full.push({11, 22}); });
        while (full.snapshot().waiting_push != 1) std::this_thread::yield();
        if (aborting) full.abort(); else full.close();
        producer.join();
        if (accepted) return fail(8);
        if (aborting) {
            if (full.pop(out) != Take::aborted) return fail(9);
        } else {
            if (full.pop(out) != Take::item || out.id != 10 || out.value != 20)
                return fail(10);
            if (full.pop(out) != Take::drained) return fail(11);
        }
        auto s = full.snapshot();
        if (!balanced(s) || s.accepted != 1 || s.queued != 0 ||
            s.delivered != (aborting ? 0U : 1U) ||
            s.discarded != (aborting ? 1U : 0U)) return fail(12);

        Channel empty(1);
        Take result = Take::item;
        std::jthread consumer([&] { Reading local{}; result = empty.pop(local); });
        while (empty.snapshot().waiting_pop != 1) std::this_thread::yield();
        if (aborting) empty.abort(); else empty.close();
        consumer.join();
        if (result != (aborting ? Take::aborted : Take::drained)) return fail(13);
        if (!balanced(empty.snapshot())) return fail(14);
    }

    Channel escalation(2);
    if (!escalation.push({1, 2})) return fail(15);
    escalation.close();
    escalation.abort();
    escalation.abort();
    escalation.close();
    auto s = escalation.snapshot();
    if (s.state != State::aborted || s.accepted != 1 || s.discarded != 1 ||
        s.delivered != 0 || s.queued != 0 || !balanced(s)) return fail(16);
    if (escalation.push({3, 4}) || escalation.pop(out) != Take::aborted)
        return fail(17);
    std::cout << "channel contract verified\n";
}
```

`accepted` 和 result 不是 atomic，但只有子线程写，主线程在成功 join 后读。线程完成同步于对应 join 的成功返回，这建立了所需 HB；把它们改成 atomic 并不能弥补遗漏 join 所造成的生命周期问题。[N4950：thread 的 join](https://timsong-cpp.github.io/cppwp/n4950/thread.thread.member)

这个实验让每个 close/abort 的阻塞路径都实际到达，但不覆盖所有线程交错。特别是它没有证明两个关闭者任意竞争时的所有调度，也没有用一次终态统计证明外部任务的业务副作用。

## 6 从单条路径到多参与者

两个生产者分别提交不重叠的编号区间，两个消费者将取出的完整值保存到各自独占的 vector。只有在全部 join 之后，主线程才汇总、按编号排序，并逐条验证没有遗漏、重复或字段错配。不能只比总和：丢一条、重复另一条可能碰巧得到相同结果。

**完整实验 G7-Q2 · `channel-stress.cpp` · 有限调度扰动与逐项核对**

```cpp
#include "channel.hpp"
#include <algorithm>
#include <array>
#include <iostream>
#include <thread>
#include <vector>

int main() {
    constexpr unsigned per_producer = 500;
    for (unsigned round = 0; round != 24; ++round) {
        Channel channel(1 + round % 8);
        std::array<std::vector<Reading>, 2> received;
        std::array<bool, 2> accepted{true, true};
        std::array<Take, 2> endings{Take::item, Take::item};
        std::vector<std::jthread> producers, consumers;
        try {
            for (unsigned c = 0; c != 2; ++c) {
                received[c].reserve(2 * per_producer);
                consumers.emplace_back([&, c] {
                    Reading item{};
                    Take result;
                    while ((result = channel.pop(item)) == Take::item) {
                        received[c].push_back(item);
                        if ((item.id + round) % 13 == 0) std::this_thread::yield();
                    }
                    endings[c] = result;
                });
            }
            for (unsigned p = 0; p != 2; ++p) {
                producers.emplace_back([&, p] {
                    for (unsigned i = 0; i != per_producer; ++i) {
                        unsigned id = p * per_producer + i;
                        if (!channel.push({id, id * 17U + 3U})) {
                            accepted[p] = false;
                            break;
                        }
                        if ((id + round) % 11 == 0) std::this_thread::yield();
                    }
                });
            }
            for (auto& producer : producers) producer.join();
            channel.close();
            for (auto& consumer : consumers) consumer.join();
        } catch (...) {
            // Startup/allocation failure on the controlling thread must wake workers.
            channel.abort();
            for (auto& producer : producers)
                if (producer.joinable()) producer.join();
            for (auto& consumer : consumers)
                if (consumer.joinable()) consumer.join();
            std::cerr << "controller setup/join failed\n";
            return 70;
        }
        auto s = channel.snapshot();
        if (!accepted[0] || !accepted[1] || endings[0] != Take::drained ||
            endings[1] != Take::drained || s.state != State::closing ||
            s.queued != 0 || s.accepted != 2 * per_producer ||
            s.delivered != s.accepted || s.discarded != 0 ||
            s.peak > 1 + round % 8 || s.waiting_push || s.waiting_pop) return 1;
        received[0].insert(received[0].end(), received[1].begin(), received[1].end());
        std::ranges::sort(received[0], {}, &Reading::id);
        if (received[0].size() != 2 * per_producer) return 2;
        for (unsigned id = 0; id != 2 * per_producer; ++id)
            if (received[0][id].id != id || received[0][id].value != id * 17U + 3U)
                return 3;
    }
    std::cout << "stress rounds=24 records=24000 verified\n";
}
```

这里没有用 yield 建立正确性：去掉它，协议推导仍应成立。它只改变调度机会，也不承诺其他线程马上运行。每个 received vector 在启动对应线程前预留足够容量，线程只写自己那一份；排序发生在 join 之后。主线程启动失败时先 abort，使已经启动的线程能离开等待，再显式 join 后返回失败，不依赖未捕获异常路径是否展开栈。这只是对该失败路径的设计处理，本批没有注入线程创建失败或同步设施故障；清理所需的同步操作仍以前述正常工作条件为前提。

运行次数、容量和编号范围都是本次有限测试输入。它们不等于模型检查，也没有覆盖无限运行时计数溢出、优先级反转或调度不公平。TSan 可以帮助发现本次执行中的未同步访问，不能证明队列符合所有并发历史。

## 7 线程生命与失败的收束

### 7.1 请求停止、唤醒与等待完成是三件事

`std::jthread` 在仍可 join 时析构，会先请求停止再 join。停止请求是协作信号，不是强制终止；线程函数不检查相应 token，或阻塞在不响应它的等待中，就不会因此自行退出。本通道用 close/abort 改变自己的谓词，普通 `condition_variable` 的 wait 不会因为别处 request_stop 就自动返回。需要 stop-aware 等待时，可以另选 `condition_variable_any` 的相关重载，但仍须定义请求与队列数据同时出现时的优先级。[N4950：jthread](https://timsong-cpp.github.io/cppwp/n4950/thread.jthread.class)、[可停止等待](https://timsong-cpp.github.io/cppwp/n4950/thread.condvarany.intwait)

正确的生命期依赖是：停止或关闭请求先让等待有退出条件，然后等待使用者真正完成，最后销毁共享对象。`detach()` 只解除 thread 对象与执行线程的关联，没有替被借用的 Channel 延长生命。把 Channel 包进 shared_ptr 也只改变其生存管理，不会让一个没有退出条件的等待自动结束。

### 7.2 工作异常不会通过 join 自动返回

若新线程调用的函数异常逃出，`thread`／`jthread` 要求终止程序，join 不是异常传播通道。若希望隔离工作失败，需要在线程入口捕获、保存，再通过同步后的明确观察点交给控制线程。[N4950：jthread 构造与入口调用](https://timsong-cpp.github.io/cppwp/n4950/thread.jthread.cons)

下面将业务失败固定注入第一项处理，避免用随机故障掩盖退出问题。处理在 pop 返回之后进行，没有持有通道锁。worker 保存异常并中止队列，控制线程 join 后才读 exception_ptr。

**完整实验 G7-Q3 · `worker-failure.cpp` · 保存失败、唤醒对端与交付计数**

```cpp
#include "channel.hpp"
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <thread>

int main() {
    Channel channel(2);
    channel.push({1, 10});
    channel.push({2, 20});
    std::exception_ptr failure;
    std::jthread worker([&] {
        try {
            Reading item{};
            if (channel.pop(item) != Take::item)
                throw std::logic_error("missing work");
            throw std::runtime_error("injected processing failure");
        } catch (...) {
            failure = std::current_exception();
            channel.abort();
        }
    });
    worker.join();
    auto s = channel.snapshot();
    if (!failure || s.state != State::aborted || s.accepted != 2 ||
        s.delivered != 1 || s.discarded != 1 || s.queued != 0) return 1;
    try {
        std::rethrow_exception(failure);
    } catch (const std::runtime_error& e) {
        if (std::string_view(e.what()) != "injected processing failure") return 2;
        std::cout << "failure observed after join; delivered is not completed\n";
        return 0;
    } catch (...) {
        return 3;
    }
    return 4;
}
```

delivered 为一，但这项工作恰好失败了，说明“已经交付”不能替换为“已经成功”。`current_exception`、异常对象保存以及后备报告的完整极端失败边界见 FM；这个教学路径不构造一个永不失败的上报系统。若 abort 自身因同步设施故障而抛出，仍可能越过线程入口并终止；这在当前约定之外，不能因为写了 catch 就宣称线程被绝对隔离。

## 8 迁移题

1. 将 size 改为 atomic，其他字段不变，并删除 mutex，为什么不能保留当前通道合同？
2. 消费者在锁内检查空队列，解锁后再调用不带谓词的 wait，会丢掉哪一项保证？
3. 关闭满通道后，先等待生产者退出还是先排空队列？答案为什么取决于退出谓词？
4. abort 返回后，为什么不能立即销毁 Channel，也不能断言所有业务处理均未发生？
5. 两个消费者各自得到一半编号，汇总总和正确，但某个编号出现两次，这可能逃过哪类测试？
6. TSan 没有报告，所有字段也都加锁，线程仍不能退出，应从哪个层面继续分析？

## 9 推理答案

1. atomic size 只约束它自身的访问。槽位写入、索引变化和状态判断需要组成同一次受保护状态转移；重复消费者可能选中同一元素，生产者还可能覆盖正在复制的槽位。必须重新设计并证明完整协议，不能只升级一个字段。
2. 检查结束与真正进入等待之间，生产者可能更新状态并通知；通知不存储余额，消费者随后入睡便错过当前条件。不带谓词的等待还不能处理伪唤醒和其他消费者已经消耗数据的情况。应在同一 mutex 下检查谓词，并用 wait 的释放／等待协议连接两步。
3. 本例生产者在非 open 时也能离开等待，所以 close 后可以先 join 生产者，再排空；Q1 正在验证这条路径。若谓词只有“有空间”，先 join 就可能一直等待，必须改变协议而不是靠碰巧有消费者取走数据救场。
4. abort 只改变状态并通知，不等待函数调用全部返回；线程仍可能访问条件变量、mutex 或调用方结果。已经 pop 出去的数据属于调用方，队列无法撤回它正在进行的操作。必须等待使用者结束，并在更外层定义在途任务的后果。
5. 计数或总和只约束一个汇总量，不足以证明完整集合与字段对应。测试需要验证长度、每个唯一编号和相应值。并发实现安全与测试 oracle 足够强是两个不同问题，TSan 也不会替你查业务重复。
6. 查等待条件、谁负责满足条件、关闭顺序以及锁和任务依赖图。这属于活性或业务协议问题；没有未同步内存访问不能排除死锁。有限执行观察也不能提供公平性证明，应同时检查静态依赖和实际阻塞路径。

## 10 验证与阅读边界

本单元的[验证说明](g07-verification.md)分别报告正常合同、有限 stress、受控业务故障和 TSan；第二单元的已知 data race 作为工具阳性对照。协议推导是基于明确前提的人工论证，没有使用形式化证明器。两个错误变体另外检查关闭拒绝与丢弃计数的判据，不把编译失败、超时或崩溃计为成功拒绝。

多锁事务、完整线程池、任务取消传播、work stealing 和生产级 MPMC 无锁回收仍可在 [v1 G7](../g07-concurrency-and-memory-model.md)定位相关讨论，但本批不宣称已经重编或实现。先稳定“对象何时可访问、状态何时生效、等待怎样结束”，再进入原子操作，才能判断某个更复杂方案究竟省掉了什么，又增加了哪些证明责任。
