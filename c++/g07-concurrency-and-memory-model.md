# C++ Systems Track · G7 Concurrency & C++ Memory Model

**Version:** 1.0  
**Status:** Frozen Review Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0–G6  
**Scope:** Data Race / Happens-before / Atomics / Memory Ordering / Mutex / Condition Variable / CAS / Lock-free / ABA / Memory Reclamation / Concurrent Queues / Thread Lifetime / `std::jthread` / Cancellation / Thread Pool / Backpressure / Concurrency Architecture  
**Purpose:** 建立一套能够从 C++ Memory Model 一直推导到真实并发系统架构的统一 reasoning framework。

---

# 0. G7 到底解决什么问题？

G6 已经告诉我们：

```text
CPU Core 0
    │
    ├── cache
    │
    └────────────┐
                 │ coherence
    ┌────────────┘
    │
CPU Core 1
```

我们已经知道：

```text
cache line
false sharing
atomic RMW
coherence traffic
```

会影响性能。

但这还不能回答：

> **两个 C++ threads 到底什么时候可以合法地观察彼此的内存操作？**

也就是说：

```text
Hardware Question
─────────────────
CPU 如何执行这些 loads/stores？

            ≠

C++ Language Question
─────────────────────
程序员什么时候有权推理：
“Thread B 看到了 Thread A 写的数据”？
```

G7 的核心就是后一件事。

---

# 1. G7 的统一链路

整个阶段可以压缩成：

```text
Memory Location
      ↓
Conflicting Access
      ↓
Data Race?
      ↓
Atomic / Non-atomic
      ↓
Ordering Relations
      ↓
Happens-before
      ↓
Synchronization Primitive
      ↓
Ownership / Lifetime
      ↓
Concurrent Protocol
      ↓
Progress Guarantee
      ↓
Queue / Runtime
      ↓
Concurrency Architecture
```

最重要的一条纪律：

> **不要从 `atomic`、`mutex`、CAS API 开始设计并发系统。**

而应该先问：

```text
谁拥有数据？
谁可以修改？
哪些状态必须一致？
什么时候发生 ownership handoff？
哪些关系必须建立 happens-before？
```

然后再选择 primitive。

---

# Part I · Data Race & Memory Model

# 2. Data Race 是 G7 的第一道门槛

考虑：

```cpp
int value = 0;
bool ready = false;

// Thread A
value = 42;
ready = true;

// Thread B
while (!ready) {
}

use(value);
```

人类直觉：

```text
Thread B 看到了 ready == true
          ↓
Thread A 肯定已经执行了 value = 42
          ↓
所以 value == 42
```

C++ 并不允许这样推理。

这里首先存在：

> **Data Race**

因此：

> **Undefined Behavior**

---

# 3. Data Race 的核心条件

一个实用模型：

如果两个 potentially concurrent operations：

1. 访问同一个 memory location；
2. 至少一个是 write；
3. accesses conflict；
4. 至少一个是 non-atomic；
5. 两者之间没有合适的 happens-before；

那么可能形成：

> **Data Race**

C++ 对普通 data race 的态度不是：

```text
“也许读到旧值”
```

而是：

```text
Undefined Behavior
```

这点必须和 Java / Go 一类语言的某些直觉严格区分。

---

# 4. `read/read` 与 `read/write`

通常：

```text
read / read
→ 不冲突
```

而：

```text
read / write
write / write
→ conflicting
```

所以：

```cpp
const Config config;
```

在正确 publication 后被多个 threads 只读：

> 是非常自然的模型。

真正复杂的是：

> Shared Mutable State。

---

# 5. Data Race 不等于 Race Condition

## Data Race

是 C++ Memory Model 的技术概念。

例如：

```text
non-atomic conflicting accesses
+
no happens-before
```

结果：

> UB。

---

## Race Condition

是更广义的逻辑问题：

> 程序结果取决于不受控制的 interleaving。

例如：

```cpp
std::atomic<int> balance{100};

if (balance.load() >= 80) {
    balance.fetch_sub(80);
}
```

两个 threads 都可能：

```text
load 100
load 100
subtract
subtract
```

最后：

```text
-60
```

所有 atomic operations 本身合法，

但业务 invariant 被破坏。

所以：

```text
Data-race-free
≠
Race-condition-free
```

---

# 6. `volatile` 不是并发同步

```cpp
volatile bool ready = false;
```

不能替代：

```cpp
std::atomic<bool>
```

C++ `volatile` 不提供：

```text
atomicity
happens-before
inter-thread synchronization
```

必须永久记：

```text
volatile
≠
atomic
≠
mutex
```

---

# Part II · Ordering Relations

# 7. `sequenced-before`

描述：

> 同一 thread 内 C++ abstract machine 的顺序关系。

例如：

```cpp
data = 42;
ready.store(true);
```

有：

```text
data = 42
    │
    │ sequenced-before
    ▼
ready.store(true)
```

注意：

> 这不是“CPU 一定先把 data 写入 DRAM”。

它是：

> 语言级 ordering relation。

---

# 8. `synchronizes-with`

跨线程 synchronization primitive 可以建立：

> **synchronizes-with**

例如 release/acquire：

```text
Thread A                    Thread B

release store
      │
      │ synchronizes-with
      ▼
                           acquire load
```

前提是：

> acquire 真正接到了对应的 publication。

不是只因为源码中写了两个关键词。

---

# 9. `happens-before`

这是 G7 最核心的 relation。

如果：

```text
A happens-before B
```

C++ 允许你在语言层推理：

> A 的相关 memory effects 对 B 有定义良好的顺序保证。

典型链：

```text
sequenced-before
+
synchronizes-with
+
transitivity
=
happens-before
```

---

# 10. 最重要的一张图

```cpp
int data = 0;
std::atomic<bool> ready{false};

// Producer
data = 42;
ready.store(true, std::memory_order_release);

// Consumer
while (!ready.load(std::memory_order_acquire)) {
}

use(data);
```

关系：

```text
Thread A                           Thread B

data = 42
    │
    │ SB
    ▼
ready.store(true, release)
    │
    │ SW
    ▼
                              ready.load(acquire)
                                     │
                                     │ SB
                                     ▼
                                  read data
```

因此：

```text
write data
    │
    │ HB
    ▼
read data
```

其中：

```text
SB = sequenced-before
SW = synchronizes-with
HB = happens-before
```

这是整个 G7 最值得长期保留的图之一。

---

# 11. 为什么 `data` 可以不是 Atomic？

因为：

```text
Producer write data
```

与：

```text
Consumer read data
```

已经通过：

```text
release/acquire synchronization
```

建立 HB。

所以真正原则不是：

> 跨线程数据全部必须 atomic。

而是：

> **Conflicting accesses 必须有合法 synchronization。**

Atomic 只是建立 synchronization 的一种工具。

---

# Part III · Atomicity & Memory Ordering

# 12. Atomicity ≠ Ordering

考虑：

```cpp
std::atomic<int> x;
```

Atomicity回答：

> 对 `x` 的某个 operation 是否作为 indivisible atomic operation 被观察？

Ordering回答：

> 这个 operation 与其它 memory operations 之间建立什么顺序关系？

这是两个维度。

---

# 13. Atomic Operation 三类

## Load

```cpp
x.load(order);
```

---

## Store

```cpp
x.store(value, order);
```

---

## Read-Modify-Write

```cpp
x.fetch_add(...);
x.exchange(...);
x.compare_exchange_weak(...);
```

同时有：

```text
read side
+
write side
```

---

# 14. Memory Order 属于 Operation

不是：

```text
“这个 atomic variable 是 acquire atomic”
```

而是：

```cpp
x.load(std::memory_order_acquire);

x.store(
    value,
    std::memory_order_release);

x.fetch_add(
    1,
    std::memory_order_relaxed);
```

同一个 atomic object：

> 不同 operations 可以使用不同 memory order。

---

# 15. `memory_order_relaxed`

保证：

```text
atomicity
+
该 atomic object 自己的 modification order
```

但不自动建立：

> surrounding ordinary data 的跨线程 synchronization。

典型：

```cpp
processed.fetch_add(
    1,
    std::memory_order_relaxed);
```

适合：

```text
statistics
independent counter
ticket generation
```

前提：

> 不依赖它去发布其它 state。

---

# 16. Modification Order

每个 atomic object 都拥有：

> 对其所有 modifications 的一致总顺序。

例如：

```text
x:
0
↓
1
↓
2
↓
3
```

所以 `relaxed` 并不是：

> “atomic value 本身也完全乱序。”

它仍然具有该 object 自己的 atomic coherence。

---

# 17. `memory_order_release`

典型角色：

> **Publish**

```cpp
payload = build_payload();

ready.store(
    true,
    std::memory_order_release);
```

表示：

> release 之前 sequenced-before 的相关 operations，可以通过合适 acquire 建立跨线程 HB。

不要翻译成：

```text
flush cache to RAM
```

---

# 18. `memory_order_acquire`

典型：

```cpp
if (ready.load(
        std::memory_order_acquire)) {
    use(payload);
}
```

如果 acquire 观察到对应 release publication，

则 release 之前的 writes：

```text
HB
```

acquire 之后的 reads。

---

# 19. Release / Acquire 的核心不是 Cache Flush

错误模型：

```text
release
↓
flush all cache to DRAM

acquire
↓
reload from DRAM
```

正确模型：

```text
C++ ordering contract
        ↓
compiler lowering
        ↓
hardware ordering + coherence
```

现代 CPU 可能：

> cache-to-cache 直接传递数据。

DRAM 根本不需要出现在这次交互里。

---

# 20. `memory_order_acq_rel`

主要用于 RMW：

```text
Acquire previous publication
+
Publish new state
```

例如：

```cpp
state.compare_exchange_weak(
    expected,
    desired,
    std::memory_order_acq_rel);
```

但：

> **RMW 不自动意味着一定需要 acq_rel。**

如果只需要 atomicity：

```text
relaxed
```

可能就够。

如果只需要 acquire：

```text
acquire
```

也可能够。

---

# 21. `memory_order_seq_cst`

默认 atomic ordering：

```cpp
x.load();
x.store(...);
```

使用：

```text
seq_cst
```

除了相应 acquire/release 类语义外，

还对 seq_cst atomic operations 提供一个：

> 单一 global sequentially-consistent total order。

因此：

> 最容易进行跨多个 atomic 的全局 reasoning。

---

# 22. Memory Order 不是性能等级表

错误：

```text
relaxed = fastest
acquire/release = medium
seq_cst = slowest
```

这会带偏思维。

正确：

> Memory order 是 correctness contract。

性能成本取决于：

```text
target architecture
compiler
operation
contention
```

选择顺序：

```text
Invariant
↓
Required HB edge
↓
Synchronization protocol
↓
Sufficient memory order
```

不是：

```text
想更快
↓
换 relaxed
```

---

# Part IV · Mutex & Condition Variable

# 23. Mutex 保护的是 Invariant

不是：

> “锁住一个变量”。

例如：

```cpp
struct Account {
    int balance;
    int reserved;
};
```

真正需要保护的是：

```text
balance >= 0
reserved >= 0
reserved <= balance
```

也就是：

> 多个字段构成的 logical invariant。

---

# 24. Mutex 提供两件事

## Mutual Exclusion

同一时刻：

> 只有一个 owner 进入 critical section。

---

## Memory Synchronization

一个 thread：

```text
writes
↓
unlock
```

另一个：

```text
successful lock
↓
reads
```

可以建立相应 synchronization / HB。

因此 mutex 内保护的数据：

```cpp
int value_;
```

不需要全部改 atomic。

---

# 25. RAII Locking

默认：

```cpp
std::lock_guard lock{mutex};
```

需要：

```text
unlock/relock
condition_variable
deferred locking
```

时使用：

```cpp
std::unique_lock lock{mutex};
```

多个 mutex：

```cpp
std::scoped_lock lock{a, b};
```

优先避免手写：

```cpp
mutex.lock();
...
mutex.unlock();
```

---

# 26. Critical Section 原则

不是：

> “越短越好。”

而是：

> **覆盖维护 invariant 所需的最小完整 logical transaction。**

不能为了缩短锁：

```text
check
unlock
...
lock
update
```

把本应 atomic 的业务操作拆开。

同时不要无必要地把：

```text
I/O
network
sleep
large computation
callbacks
```

放在 hot shared lock 内。

---

# 27. Deadlock

经典：

```text
Thread A:
holds A
waits B

Thread B:
holds B
waits A
```

解决方法：

```text
consistent lock order
std::scoped_lock
architecture redesign
```

如果系统出现：

```text
大量 mutex
随机组合获取
```

应该考虑：

> 是否 shared-state topology 本身已经过度复杂。

---

# 28. Condition Variable 等待的是 Predicate

不是 Notification。

正确：

```cpp
cv.wait(lock, [&] {
    return closed_ || !queue_.empty();
});
```

真正业务事实：

```text
queue non-empty
or
closed
```

`notify_one()` 只是：

> “state 可能已经改变，请重新检查。”

---

# 29. Notification 是 Edge，Predicate 是 State

```text
Predicate
=
persistent truth

Notification
=
transient wakeup hint
```

所以 notification 先于 wait 发生：

> 不会因为“丢 notification”导致逻辑失败，

只要 predicate state 仍然成立。

---

# 30. Spurious Wakeup

`wait()` 可以在没有目标业务事件时返回。

另外多个 waiters 竞争：

```text
A wakes and consumes item
B wakes afterwards
queue empty
```

因此：

```cpp
if (!predicate()) {
    cv.wait(lock);
}
```

通常错误。

应：

```cpp
cv.wait(lock, predicate);
```

或：

```cpp
while (!predicate()) {
    cv.wait(lock);
}
```

---

# Part V · Atomic RMW / CAS

# 31. 为什么 `load + store` 不等于 Atomic Transition？

```cpp
if (state.load() == Ready) {
    state.store(Running);
}
```

两个 individually atomic operations，

仍然可能：

```text
Thread A load Ready
Thread B load Ready
Thread A store Running
Thread B store Running
```

两个 threads 都认为自己抢到了 transition。

---

# 32. CAS

```cpp
value.compare_exchange_strong(
    expected,
    desired);
```

语义：

```text
if current == expected:
    current = desired
    return true
else:
    expected = current
    return false
```

关键：

> CAS 把 check + update 合成一个 atomic RMW。

---

# 33. `expected` 是 In/Out Parameter

成功：

```text
atomic = desired
expected unchanged
return true
```

失败：

```text
atomic unchanged
expected = actual observed value
return false
```

这就是为什么 CAS loop 不需要每次重新 load。

---

# 34. CAS Loop

```text
load current
↓
compute desired
↓
CAS
 ├─ success → done
 └─ failure
      ↓
 current updated
      ↓
 retry
```

这是：

> **Optimistic Concurrency**

观察：

```text
current state
```

尝试：

```text
conditional commit
```

冲突：

```text
retry
```

---

# 35. Weak vs Strong

```text
compare_exchange_weak
```

允许：

> spurious failure。

适合：

```text
retry loop
```

因为失败本来就会重试。

```text
compare_exchange_strong
```

适合：

> 一次失败就具有明确业务意义的 one-shot attempt。

必须记：

```text
weak / strong
```

和：

```text
relaxed / acquire / release
```

是两条完全不同维度。

---

# 36. Success / Failure Ordering

成功：

> RMW

可以具有 acquire/release 角色。

失败：

> 只读，没有 modification。

所以：

```cpp
compare_exchange_weak(
    expected,
    desired,
    success_order,
    failure_order);
```

两条 path 可以需要不同 memory order。

---

# Part VI · ABA & Reclamation

# 37. CAS 只比较 Current Value

如果：

```text
A
↓
B
↓
A
```

CAS 最后看到：

```text
current == expected == A
```

会认为相等。

它不知道历史经历过 B。

这就是：

> **ABA**

---

# 38. ABA 不是 Use-after-free

ABA：

> state/version/history 问题。

Reclamation：

> object lifetime 问题。

两者经常同时出现，但必须分开。

---

# 39. Unlinked ≠ Reclaimable

一个 node：

```text
Linked
↓
Unlinked
↓
Retired
↓
Reclaimable
↓
Destroyed
```

从 lock-free structure 中删除：

> 只解决 Logical Membership。

不代表：

> 没有 reader 仍持有 pointer。

---

# 40. Pointer Acquisition ≠ Safe Dereference

并发：

```cpp
Node* p = head.load();
```

只得到：

> pointer value。

并没有自动保证：

> `*p` object lifetime 仍然 active。

另一个 thread 可能：

```text
remove
delete
```

发生在：

```text
load p
```

和：

```text
p->next
```

之间。

---

# 41. Tagged Pointer / Generation

把：

```text
pointer
```

扩展成：

```text
(pointer, generation)
```

例如：

```text
(A, 41)
→
(B, 42)
→
(A, 43)
```

旧：

```text
(A, 41)
```

不再等于：

```text
(A, 43)
```

可以检测一类 ABA。

但：

> 不自动解决 pointee lifetime。

---

# 42. Reclamation Strategies

## Reference Counting

```text
reader holds ownership
→ node cannot die
```

简单组合，代价：

```text
atomic refcount
control block
coherence traffic
```

---

## Hazard Pointer

reader 显式发布：

```text
I currently protect Node A
```

reclaimer：

```text
A appears in hazard set
→ cannot free
```

流程：

```text
load pointer
↓
publish hazard
↓
revalidate source
↓
dereference
↓
clear hazard
```

---

## Epoch-based Reclamation

reader 表示：

```text
I am active in epoch E
```

retired node：

> 等所有可能仍在旧 epoch 的 readers 离开后再 reclaim。

---

## RCU / QSBR

```text
build new generation
↓
publish
↓
wait grace period
↓
reclaim old generation
```

特别适合：

```text
read-heavy
write-rare
```

系统。

---

# 43. Lock-free 不是性能等级

Lock-free 是：

> Progress Guarantee。

不是：

> “一定比 mutex 快”。

CAS contention 可能产生：

```text
retry storm
cache-line ping-pong
```

一个低 contention mutex 可能更快、更简单。

---

# 44. Progress Guarantees

粗略：

```text
Wait-free
⇒
Lock-free
⇒
Obstruction-free
```

## Lock-free

系统整体保证：

> 持续有某个 operation 取得进展。

不保证每个 thread 都不饿死。

## Wait-free

更强：

> 每个 operation 都在有限步骤内完成。

---

# 45. `atomic<T>::is_lock_free()` 不是算法证明

它只回答：

> 这个 atomic object 的 implementation 是否 lock-free。

不代表：

> 整个 data structure / allocator / reclamation / operation path 是 lock-free。

---

# Part VII · Concurrent Queue

# 46. Queue 首先按 Topology 分类

| Queue | Producer | Consumer |
| ----- | -------: | -------: |
| SPSC  |        1 |        1 |
| MPSC  |        N |        1 |
| SPMC  |        1 |        N |
| MPMC  |        N |        N |

Topology 直接决定：

```text
谁写 enqueue cursor？
谁写 dequeue cursor？
哪里需要 CAS？
哪里可能 single-writer？
```

---

# 47. SPSC 的关键简化

```text
Producer:
only writer of tail

Consumer:
only writer of head
```

因此：

> 不需要 CAS 去争抢 cursor ownership。

只需正确 publication。

---

# 48. SPSC 的两条 HB Edge

## Producer → Consumer

```text
construct slot
↓
tail.store(release)
↓
tail.load(acquire)
↓
consume slot
```

因此：

```text
slot write
HB
slot read
```

---

## Consumer → Producer

```text
finish consuming
↓
head.store(release)
↓
head.load(acquire)
↓
reuse slot
```

因此：

```text
old generation use
HB
new generation construction
```

这两条就是 SPSC correctness 骨架。

---

# 49. MPSC 的关键新问题

多个 producers 可以：

```text
reserve slots
```

但 reservation completion 可以 out-of-order：

```text
P0 reserves slot 10
pause

P1 reserves slot 11
writes + publishes
```

于是：

```text
reservation frontier
≠
ready frontier
```

简单 global tail 不够。

---

# 50. MPMC 为什么需要 Per-slot Generation

Physical slot 会反复：

```text
slot 3 generation 0
slot 3 generation 1
slot 3 generation 2
```

所以常见：

```text
per-slot sequence number
```

同时编码：

```text
free generation
ready generation
consumed generation
```

这其实就是：

> ABA generation 思想在 ring slot 上的应用。

---

# 51. Bounded Queue = Backpressure

如果 producer rate：

```text
>
consumer rate
```

无界 queue：

```text
memory ↑
latency ↑
```

bounded queue：

```text
full
```

显式告诉上游：

> 系统已达到当前 processing capacity。

Full 是：

> 正常系统状态。

不是异常。

---

# 52. Queue 是 Ownership Boundary

成功：

```cpp
queue.push(std::move(job));
```

自然语义：

```text
Producer owns Job
↓
Queue owns Job
↓
Consumer owns Job
```

因此跨线程 queue 中优先：

```text
owned value
move-only handle
lease
unique ownership
```

而不是未经约束的 borrowed pointer。

---

# Part VIII · Thread Lifetime & Shutdown

# 53. `std::thread`

如果 destructor 时：

```text
joinable == true
```

会：

> `std::terminate()`。

所以 thread lifetime 必须显式解决：

```text
join
or
detach
```

---

# 54. `detach()` 不解决 Lifetime

它只是：

> 解除 `std::thread` object 与执行线程的 join relationship。

不会解决：

```text
thread still accesses this
thread still accesses queue
thread still accesses stack object
```

所以 detach 常常只是：

> 隐藏 ownership 问题。

---

# 55. `std::jthread`

核心：

```text
RAII join
+
cooperative stop
```

Destructor 大体：

```text
request_stop
↓
join
```

但：

> stop 是 request，不是 kill。

Worker 必须 cooperate。

---

# 56. `stop_token`

表示：

> 观察 cancellation request 的 capability。

不是：

```text
pause/resume state
```

而是 monotonic：

```text
not requested
↓
requested
```

---

# 57. Cancellation 必须唤醒 Blocked Thread

错误：

```text
request_stop
```

但 worker 正 blocked：

```cpp
cv.wait(...)
```

它可能根本醒不过来检查 stop。

因此需要：

```text
stop-aware wait
```

或：

```text
stop_callback
↓
notify
```

---

# 58. Cancellation Point 必须保持 Invariant

不能：

```text
update half of shared state
↓
see stop
↓
return
```

如果状态因此不一致。

Cancellation 和 Exception Safety 有同样结构：

```text
prepare
↓
safe cancellation point
↓
commit
```

---

# 59. Member Destruction Order

成员：

> 按声明顺序构造，逆序析构。

所以如果 thread 访问：

```text
mutex
queue
config
```

thread member 通常应：

> 最后声明。

例如：

```cpp
class Worker {
    std::mutex mutex_;
    Queue queue_;

    std::jthread thread_;
};
```

析构：

```text
thread_ joins
↓
queue_
↓
mutex_
```

保证：

> worker 不会 outlive dependencies。

---

# 60. Shutdown 基本顺序

```text
1. Stop accepting new work

2. Publish close/stop state

3. Wake blocked threads

4. Drain or abort according to contract

5. Thread functions return

6. Join

7. Destroy shared state/resources
```

这是必须长期保留的 shutdown template。

---

# 61. Drain vs Abort

## Drain

```text
reject new work
↓
process already accepted work
↓
exit
```

## Abort

```text
reject new work
↓
request cancellation
↓
discard/cancel according to contract
↓
exit
```

两者绝不能用一个模糊：

```cpp
stop();
```

让 caller 猜。

---

# Part IX · Thread Pool & Runtime

# 62. Thread ≠ Task

Thread：

> execution resource。

Task：

> unit of work。

Thread pool 的本质：

```text
many tasks
↓
bounded worker threads
```

把：

```text
logical concurrency
```

和：

```text
physical parallelism
```

解耦。

---

# 63. C++23 Task Representation

非常适合：

```cpp
using Task =
    std::move_only_function<void()>;
```

因为 Task 经常捕获：

```text
unique_ptr
socket
buffer lease
move-only handle
```

这和 ownership transfer 模型一致：

```text
Submitter
→ Queue
→ Worker
```

---

# 64. Worker 不能持 Queue Lock 执行 Task

正确：

```text
lock queue
↓
move task out
↓
unlock
↓
execute task
```

Queue mutex 只保护：

> queue invariant。

Task execution 已经变成：

> worker-local ownership。

---

# 65. Pool 必须考虑两种 Bound

```text
Worker count
```

限制：

> physical parallelism。

```text
Queue capacity
```

限制：

> backlog。

只有 bounded workers、unbounded queue：

> overload 仍然可以把 memory/latency 推爆。

---

# 66. CPU-bound 与 I/O-bound Pool

CPU-bound：

```text
worker count
≈ available compute resources
```

从此附近开始 benchmark。

I/O-bound：

> threads 可能大量 blocked，

worker count 可能更大。

但更成熟可能使用：

```text
async I/O
```

避免大量 blocked OS threads。

---

# 67. Resource Isolation

不要把：

```text
CPU tasks
blocking database calls
fsync
network waits
background cleanup
```

全部塞进一个 global pool。

否则：

> blocking work 会 starve CPU work。

典型：

```text
CPU pool
blocking pool
async I/O runtime
```

分离。

---

# 68. Thread Pool Starvation Deadlock

Pool 只有一个 worker：

```text
Task A runs
↓
submit Task B to same pool
↓
A waits future B
↓
B waits for a worker
↓
the only worker is occupied by A
```

没有 mutex cycle，

仍然 deadlock。

这是：

> execution-capacity dependency cycle。

---

# 69. Bounded Submit 也能 Deadlock

多个 workers：

```text
each running task
↓
blocking submit child task
```

queue full。

所有 workers：

```text
wait queue capacity
```

但 queue capacity 只能通过：

> worker consuming tasks

来释放。

于是：

```text
Workers
↓ wait for
Queue Capacity
↓ requires
Workers
```

形成 cycle。

Backpressure 必须结合：

> resource graph

分析。

---

# 70. Global Queue vs Work Stealing

Global MPMC：

```text
simple
good natural balancing
central contention
```

Per-worker queue：

```text
locality
less global contention
```

空闲 worker：

```text
steals
```

Work stealing 本质：

> common case local ownership，rare case cross-worker coordination。

---

# Part X · Concurrency Architecture

# 71. 并发设计最重要的问题：有几个 Writer？

不是：

> 有几个线程。

而是：

```text
每一份 mutable state
有几个 writer？
```

复杂度通常随着：

```text
multiple writers
```

急剧上升。

---

# 72. Reasoning Complexity Ladder

粗略：

```text
Thread-local mutable
        ↓
Single-writer mutable
        ↓
Immutable shared
        ↓
Ownership transfer
        ↓
Mutex-protected shared mutable
        ↓
Atomic shared mutable
        ↓
Multi-object lock-free shared mutable
```

不是性能排名。

而是：

> reasoning complexity。

---

# 73. Privatize First

例如 metrics：

差：

```text
32 workers
→ one global atomic counter
```

更好：

```text
each worker
→ own counter
↓
periodic aggregation
```

这可以显著减少：

```text
coherence traffic
atomic contention
```

所以：

> **Privatize first, synchronize later.**

---

# 74. Single Writer Principle

一份 mutable state：

```text
one writer
```

意味着内部可以恢复：

> 普通单线程 C++。

其它 threads：

```text
send command
```

而不是：

```text
direct mutation
```

这会消灭大量：

```text
mutex
atomics
CAS
multi-field consistency problems
```

---

# 75. Message Passing 的真正价值

不是：

> “不用 shared memory。”

Queue 本身仍然共享。

真正变化的是：

> **Mutation Authority**

从：

```text
Many writers
→ same state
```

变成：

```text
Many producers
→ queue
→ one owner
→ state
```

---

# 76. Sharding

如果 single writer 成为 throughput ceiling：

```text
key
↓
shard
↓
single owner
```

例如：

```text
EntityId → shard 0
EntityId → shard 1
...
```

得到：

```text
within shard:
single writer

across shards:
parallelism
```

---

# 77. Shard Key = Ownership Key

Sharding 的本质不是：

> “分几个 queue”。

而是：

> 哪个 key 决定谁拥有 mutation authority？

例如：

```text
VehicleId
AccountId
PartitionId
ConnectionId
```

选错 shard key：

> cross-shard coordination 会非常多。

---

# 78. Immutable Snapshot

Read-heavy state：

```text
Config
RoutingTable
ModelRegistry
```

很适合：

```text
build V2 privately
↓
validate
↓
publish immutable V2
↓
readers use snapshot
```

而不是每次：

```text
lock config
read
unlock
```

---

# 79. Snapshot Consistency vs Freshness

Reader 可能持有：

```text
V1
```

而 current 已经：

```text
V2
```

这可能是：

> stale but internally consistent。

是否允许由 product/system contract 决定。

不要把：

```text
latest
```

和：

```text
consistent generation
```

混为一谈。

---

# 80. Old Generation 的 Lifetime

```text
not current
≠
safe to destroy
```

Old reader 可能还在使用 V1。

因此仍需要：

```text
shared_ptr
epoch
RCU
```

等 generation reclamation。

这和 lock-free node reclamation 完全同构。

---

# Part XI · Cross-cutting Principles

# 81. Ownership Graph

问：

```text
谁拥有 object？
谁借用？
谁转移？
谁销毁？
```

---

# 82. Synchronization Graph

问：

```text
哪些 HB edges 存在？
来自哪里？
```

例如：

```text
release/acquire
mutex
join
queue handoff
```

---

# 83. Mutation Graph

问：

```text
每份 state
有哪些 writer？
```

如果：

```text
N writers
```

重点审查。

---

# 84. Progress Graph

问：

```text
谁在等谁？
谁能让谁继续？
```

用于发现：

```text
deadlock
pool starvation
backpressure cycles
```

---

# 85. Lifetime / Reclamation Graph

问：

```text
logical removal
之后
什么时候真正能 destroy？
```

---

# 86. Cache Ownership Graph

G6 加入：

```text
哪些 cores 高频写哪些 cache lines？
```

Race-free 并不意味着：

> coherence-friendly。

---

# 87. Queue / Capacity Graph

问：

```text
压力积累在哪里？
谁被 backpressure？
capacity 释放依赖谁？
```

这对 runtime deadlock 极其重要。

---

# Part XII · G7 Unified Review Protocol

任何并发问题，建议按以下顺序。

---

## Layer 1 — State

```text
共享的 state 到底是什么？
```

---

## Layer 2 — Ownership

```text
谁拥有它？
谁控制 lifetime？
```

---

## Layer 3 — Writers

```text
有几个 writer？
能不能降到 1？
```

---

## Layer 4 — Conflict

```text
read/read?
read/write?
write/write?
```

---

## Layer 5 — Atomicity

```text
ordinary?
atomic?
compound invariant?
```

---

## Layer 6 — Ordering

```text
HB edge 从哪里来？
```

---

## Layer 7 — Synchronization

选择：

```text
mutex?
CV?
atomic?
CAS?
queue?
join?
```

---

## Layer 8 — Lifetime

```text
reader 持有 pointer 时 object 能不能死？
```

---

## Layer 9 — Progress

```text
blocking?
lock-free?
wait-free?
谁会饿死？
```

---

## Layer 10 — Backpressure

```text
full / overload 时怎么办？
```

---

## Layer 11 — Shutdown

```text
drain?
abort?
wake?
join?
```

---

## Layer 12 — Architecture

最后问：

```text
这份 shared mutable state
真的需要共享修改吗？
```

这是最重要的一层。

---

# Part XIII · Concurrency Smell Catalogue

# 88. Smell 1 — Global Mutable State

```text
all threads
→ one global map/state
```

然后不断增加：

```text
mutex
atomics
flags
```

---

# 89. Smell 2 — Atomic Every Field

```cpp
struct State {
    std::atomic<int> a;
    std::atomic<int> b;
    std::atomic<int> c;
};
```

但没人定义：

> multi-field consistency。

---

# 90. Smell 3 — Relaxed Cargo Cult

看到 atomic：

```cpp
memory_order_relaxed
```

只因为：

> “更快”。

却画不出 HB proof。

---

# 91. Smell 4 — Lock-free Cargo Cult

存在 mutex：

> 第一反应就是 CAS。

没有 profile，也没有 progress requirement。

---

# 92. Smell 5 — Detached Thread

```cpp
std::thread{...}.detach();
```

但 thread lifetime、dependencies、shutdown 全不明确。

---

# 93. Smell 6 — Unbounded Queue

用：

> “不阻塞 producer”

掩盖 processing capacity mismatch。

---

# 94. Smell 7 — Worker Waits Same Pool

Pool worker：

```text
submit child
↓
wait child
```

没有分析 execution-capacity cycle。

---

# 95. Smell 8 — Notification as State

```text
I got notify
therefore condition true
```

错误。

Predicate 才是 truth。

---

# 96. Smell 9 — Remove Then Delete

Lock-free structure：

```text
CAS remove node
↓
delete immediately
```

却没有 reclamation proof。

---

# 97. Smell 10 — Shared `shared_ptr<MutableT>` Everywhere

解决了 lifetime，

没有解决：

> mutation authority。

---

# 98. Smell 11 — All Workers Touch All Entities

随机 dispatch 所有 state，

造成：

```text
locks
cache migration
poor affinity
```

---

# 99. Smell 12 — Shutdown as One Bool

```cpp
bool running;
```

却没有定义：

```text
accepting?
draining?
aborting?
stopped?
```

---

# Part XIV · G7 Final Fifteen Axioms

如果半年后只能保留十五条：

1. **在讨论线程“看见什么”之前，先证明程序没有 Data Race。**

2. **Happens-before 是 C++ 并发推理的核心关系，不是 wall-clock 时间顺序。**

3. **Atomicity、memory ordering、logical transaction 是三个不同概念。**

4. **Release/Acquire 的本质是建立 publication → consumption 的 synchronization relation，不是刷新 cache。**

5. **Mutex 保护的是 shared-state invariant，而不是某个孤立变量。**

6. **Condition variable 等待的是 predicate；notification 只是唤醒提示。**

7. **Atomic `load + store` 不构成 atomic state transition；CAS 才能表达 conditional commit。**

8. **CAS success 不解决 pointer lifetime；lock-free structure 必须单独证明 memory reclamation。**

9. **ABA 的本质是 current value 恢复相同，但 logical history/generation 已改变。**

10. **Lock-free 是 progress guarantee，不是性能排名。**

11. **SPSC/MPSC/SPMC/MPMC 的区别本质上是 writer/claimer ownership topology 不同。**

12. **Thread 本身具有 lifetime；shutdown 必须遵循 stop accepting → wake → drain/abort → exit → join → destroy。**

13. **Bounded queue/backpressure 是系统稳定性 contract，不是容器细节。**

14. **并发复杂度主要来自 Shared Mutable State + Multiple Writers，因此优先 thread-local、single-writer、sharding、immutable snapshot 和 ownership transfer。**

15. **优秀并发架构的目标不是使用更聪明的 synchronization，而是让绝大多数业务 state 根本不需要 concurrent mutation。**

---

# Part XV · G7 Final Gate

下面这些问题应该能闭卷回答。

---

## A. Data Race

### 1

为什么：

```cpp
int x = 0;

// A
x = 1;

// B
use(x);
```

在没有 synchronization 时不能只说：

> “B 可能读到 0 或 1”？

因为：

> conflicting non-atomic accesses 可能构成 Data Race → UB。

---

### 2

为什么：

```text
sleep 1 second
```

不能建立 happens-before？

因为：

> wall-clock waiting 不是 C++ synchronization relation。

---

## B. Happens-before

### 3

解释：

```text
SB + SW + transitivity → HB
```

---

### 4

为什么普通 payload 可以通过 atomic flag publication 安全跨线程？

---

## C. Memory Order

### 5

什么场景适合：

```cpp
memory_order_relaxed
```

？

---

### 6

为什么：

```cpp
data = 42;
ready.store(true, relaxed);
```

不能配合 relaxed load 正确发布普通 `data`？

---

### 7

`acq_rel` 为什么主要自然出现在 RMW 上？

---

### 8

`seq_cst` 比 release/acquire 多提供的核心是什么？

---

## D. Mutex / CV

### 9

为什么 mutex 保护的是 invariant 而不是 variable？

---

### 10

为什么：

```cpp
if (!pred()) {
    cv.wait(lock);
}
```

通常错误？

---

### 11

为什么 notification 可以发生在 waiter 真正等待之前，而正确 predicate-based design 仍然不丢工作？

---

## E. CAS

### 12

CAS failure 为什么修改 `expected`？

---

### 13

为什么：

```text
weak CAS
```

不等于：

```text
weak memory ordering
```

？

---

### 14

为什么 atomic：

```text
load + store
```

不能替代 CAS？

---

## F. ABA / Reclamation

### 15

解释：

```text
A → B → A
```

为什么 CAS 可能无法发现中间变化。

---

### 16

为什么：

```text
Unlinked
≠
Safe to delete
```

？

---

### 17

Hazard Pointer 与 Epoch 的核心区别是什么？

---

### 18

为什么 generation/tagged pointer 不能自动解决 lifetime reclamation？

---

## G. Queue

### 19

SPSC 为什么通常不需要 CAS 更新 head/tail？

---

### 20

SPSC 为什么需要两个方向的 release/acquire handoff？

---

### 21

MPSC 中为什么：

```text
reservation tail
```

不能直接等价于：

```text
published tail
```

？

---

### 22

Per-slot sequence number 在 MPMC queue 中解决的核心是什么？

---

## H. Thread Lifetime

### 23

为什么 joinable `std::thread` 析构会 terminate？

---

### 24

为什么 detach 不能解决 object lifetime？

---

### 25

为什么 `jthread.request_stop()` 不能强制杀死 thread？

---

### 26

为什么 thread member 通常应该最后声明？

---

## I. Thread Pool

### 27

为什么 worker 不应该持 queue mutex 执行 Task？

---

### 28

为什么 bounded pool 中 worker 递归 blocking submit 可能 deadlock？

---

### 29

为什么 CPU-bound 与 blocking-I/O task 不应该机械使用同一个 pool？

---

### 30

为什么 work stealing 的主要架构价值不是“更复杂”，而是 common-case local ownership？

---

## J. Architecture

### 31

为什么 single writer 能显著降低 concurrency complexity？

---

### 32

Sharding 的本质是什么？

不是：

> 多几个 queue。

而是？

---

### 33

Immutable snapshot 主要优化什么 workload？

---

### 34

为什么：

```text
old snapshot no longer current
```

仍不代表可立即销毁？

---

### 35

为什么“每个字段都 atomic”经常不如一个 immutable snapshot？

---

# Part XVI · G0–G7 的统一模型

现在我们已经可以把整个前半段课程连成一条线。

---

# 100. G1 — Object Model

```text
Can I legally access this object?
```

问：

```text
storage?
lifetime?
type?
bounds?
alignment?
```

---

# 101. G2 — Ownership

```text
Who keeps it alive?
```

问：

```text
owner?
borrower?
transfer?
cleanup?
```

---

# 102. G3 — Value Semantics

```text
What moves and what does it cost?
```

问：

```text
copy?
move?
allocation?
representation?
```

---

# 103. G5 — Genericity

```text
Which variation belongs at compile time?
```

---

# 104. G6 — Performance

```text
How does representation interact with the machine?
```

问：

```text
layout
cache
allocation
TLB
branch
coherence
```

---

# 105. G7 — Concurrency

```text
Who may access or mutate this state concurrently,
and what ordering/lifetime guarantees make that legal?
```

最终统一：

```text
Object
   ↓
Lifetime
   ↓
Ownership
   ↓
Representation
   ↓
Machine Cost
   ↓
Mutation Authority
   ↓
Synchronization
   ↓
Concurrent Architecture
```

这已经是一套相当完整的 systems reasoning model。

---

# Part XVII · 一个实际 Review Example

看到：

```cpp
std::shared_ptr<MutableModel> model;
std::mutex mutex;

void worker() {
    std::lock_guard lock{mutex};
    model->update(...);
}
```

以前可能只问：

> “mutex 会不会慢？”

现在应该按完整链路分析：

```text
G1
model pointee lifetime 是否有效？

G2
为什么是 shared ownership？

G3
shared_ptr copy/refcount 成本是什么？

G6
model working set 是否在 cores 间迁移？
mutex/cache-line 是否 contention？

G7
为什么有多个 writers？
能否 single writer？
能否 shard by model/entity？
readers 是否可以使用 immutable snapshot？
```

这就是 G7 真正想训练出来的能力：

> **把 synchronization problem 向上提升成 ownership architecture problem。**

---

# Part XVIII · G7 Completion Status

G7 当前正式冻结：

```text
G7.1  Data Race / Happens-before
G7.2  Memory Ordering
G7.3  Mutex / Condition Variable
G7.4  Atomic RMW / CAS
G7.5  Lock-free / ABA / Reclamation
G7.6  SPSC / MPSC / SPMC / MPMC
G7.7  Thread Lifetime / jthread / stop_token
G7.8  Thread Pool / Task Runtime / Backpressure
G7.9  Concurrency Architecture
──────────────────────────────────────────
G7     COMPLETE / FROZEN
```

到这里，最重量级的 C++ 语言/机器理论阶段基本完成。

接下来按照我们已经调整过的路线，**先不直接进入 G8**。

下一阶段应该回补之前主动跳过的：

# G4 — Practical STL & Abstraction

但这次不会回到：

> “vector / map / algorithm 分类讲解”

那种容易变成资料罗列的方式。

而会以一个实际 C++23 数据处理组件为主线，把 STL 真正放进系统设计：

```text
contiguous data
↓
span
↓
algorithms
↓
ranges
↓
sorting / lookup
↓
iterator invalidation
↓
associative containers
↓
flat representations
↓
ownership-friendly container API
```

重点回答：

> **什么时候应该让 STL abstraction 暴露出来，什么时候应该把 container choice 隐藏在系统 boundary 后面？**

然后再进入：

```text
G8 ABI / Libraries / C Interop
```

从语言、内存、并发世界正式走向 binary interface 世界。
