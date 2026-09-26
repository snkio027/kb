# C++ Systems Track · G10 Systems Runtime Project

**Version:** 1.0  
**Status:** Complete Project Architecture / Implementation Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0–G9  
**Project Type:** High-performance bounded in-process dataflow runtime  
**Primary Goal:** 将 G0–G9 从“能够解释”提升到“能够组合成一个正确、可测、可演进的 C++23 系统”  
**Project Working Name:** `flow-runtime`

---

# 0. G10 的定位

G0–G9 基本完成了知识模型：

```text
G0   Native toolchain / binary pipeline
G1   Object / storage / lifetime
G2   RAII / ownership
G3   Value semantics / copy / move
G4   STL / ranges / views
G5   Templates / concepts
G6   Memory / cache / performance
G7   Concurrency / memory model
G8   ABI / C interop
G9   Build / package / native ecosystem
```

从 G10 开始，不再问：

> `std::span` 是什么？

而是问：

> 为什么这个 runtime boundary 应该接受 `span` 而不是 `vector&`？

不再问：

> release/acquire 怎么工作？

而是问：

> 这个 queue 的 ownership handoff 究竟在哪里发生，需要什么 synchronization？

不再问：

> `noexcept` move 为什么重要？

而是问：

> 为什么 task type 必须保证 cheap/noexcept movement，才能让 bounded queue 的 failure model保持简单？

G10 是整个 Track 的第一次：

# **Integration Gate**

---

# 1. 项目目标

我们构建一个：

> **Bounded Multi-stage Data Processing Runtime**

逻辑：

```text
Input
  │
  ▼
Ingress
  │
  ▼
Bounded Queue
  │
  ▼
Worker Pool
  │
  ▼
Processing
  │
  ▼
Bounded Queue
  │
  ▼
Sink
```

核心要求：

```text
bounded memory
bounded queue capacity
explicit ownership
no silent data loss
deterministic shutdown
clear error semantics
observable runtime state
measurable throughput/latency
installable C++ library
stable optional C ABI
```

第一版**故意不接 Kafka、HTTP、数据库、ROS**。

因为 G10 要验证：

> C++ systems architecture

而不是第三方 SDK 使用能力。

---

# 2. 为什么不用复杂业务做第一版？

如果同时引入：

```text
Kafka
HTTP
TLS
database
protobuf
cloud SDK
```

出现问题以后，你很难知道到底是：

```text
C++ lifetime bug?
queue bug?
network semantics?
dependency API?
shutdown behavior?
allocator?
```

所以 G10 使用：

> **Synthetic but structurally realistic workload**

例如：

```text
InputSource
produces binary blocks

Processor
parses / validates / transforms records

Sink
collects checksums / statistics
```

这样：

```text
runtime complexity
```

和：

```text
domain complexity
```

被解耦。

---

# 3. 最终架构

```text
                        ┌──────────────────────┐
                        │      Runtime         │
                        │                      │
 Source                 │                      │            Sink
───────▶ Ingress ─────▶ │  InputQueue         │
                        │      │               │
                        │      ▼               │
                        │  Worker Pool         │
                        │      │               │
                        │      ▼               │
                        │  OutputQueue ───────────────▶ Output
                        │                      │
                        └──────────────────────┘
```

进一步：

```text
              ownership transfer
                      │
                      ▼

Source → InputItem → Queue → Worker → Result → Queue → Sink
```

整个项目最重要的 architecture invariant：

> **大型 mutable payload 在任意时刻尽量只有一个逻辑 writer/owner。**

---

# Part I · Requirements

# 4. Functional Requirements

Runtime 必须支持：

```text
submit input
process input concurrently
produce result
bounded buffering
graceful drain
abort
error reporting
metrics
```

核心 API：

```cpp
Runtime runtime{config};

runtime.start();

runtime.submit(item);

runtime.close();

runtime.join();
```

---

# 5. Non-functional Requirements

必须明确：

### Correctness

```text
No UB
No data race
No use-after-free
No silent loss after accepted submission
```

### Resource Bounds

```text
bounded input queue
bounded output queue
bounded worker count
bounded per-worker scratch
```

### Performance

```text
contiguous hot data
low allocation steady-state
coarse enough task granularity
minimal shared mutation
```

### Operability

```text
metrics
structured state
clear shutdown
diagnostics
```

### Engineering

```text
C++23
modern CMake
sanitizers
tests
benchmarks
install/export
```

---

# 6. Non-goals

第一版不实现：

```text
distributed execution
persistent queue
exactly-once
dynamic plugin scheduling
lock-free MPMC
custom allocator everywhere
coroutines
network I/O
NUMA scheduler
real-time deadline scheduler
```

这点极其重要。

优秀系统的第一步往往是：

> **明确不解决什么。**

---

# Part II · Core Invariants

# 7. Invariant 1 — Accepted Work Must Have One Outcome

一旦：

```cpp
submit(item)
```

返回：

```text
Accepted
```

该 item 必须最终进入以下状态之一：

```text
Succeeded
Failed
Cancelled
```

不能：

```text
Accepted
↓
silently disappear
```

---

# 8. Invariant 2 — Ownership Is Unique Along the Hot Path

```text
Caller owns Item
        │
        │ successful submit
        ▼
InputQueue owns Item
        │
        │ pop
        ▼
Worker owns Item
        │
        │ produce result
        ▼
OutputQueue owns Result
        │
        │ pop
        ▼
Sink owns Result
```

没有：

```text
Worker A + Worker B
simultaneously mutating same Item
```

---

# 9. Invariant 3 — Queue Memory Is Bounded

对于 queue：

```text
0 <= size <= capacity
```

永远成立。

当 full：

```text
push blocks / rejects
```

而不是：

```text
allocate forever
```

---

# 10. Invariant 4 — State Destruction Happens After Threads Exit

必须：

```text
close / stop
↓
wake workers
↓
worker return
↓
join
↓
destroy queues / pools / config
```

绝不：

```text
destroy queue
↓
worker still reading queue
```

---

# 11. Invariant 5 — No Exception Escapes Thread Entry

每个 thread：

```cpp
void worker_entry() noexcept;
```

异常必须转换为：

```text
task failure
runtime failure
shutdown request
```

中的明确语义。

---

# 12. Invariant 6 — Shutdown Is Idempotent

调用：

```cpp
runtime.close();
runtime.close();
runtime.close();
```

不会：

```text
double close
double free
invalid transition
```

---

# Part III · Runtime State Machine

# 13. Runtime Lifecycle

不要使用：

```cpp
bool running_;
```

表达所有生命周期。

定义：

```cpp
enum class RuntimeState : std::uint8_t {
    Created,
    Running,
    Closing,
    Stopping,
    Stopped,
};
```

状态图：

```text
Created
   │ start
   ▼
Running
   │
   ├── close ─────────▶ Closing
   │                      │
   │                      │ drain complete
   │                      ▼
   │                    Stopped
   │
   └── abort ─────────▶ Stopping
                          │
                          │ workers exit
                          ▼
                        Stopped
```

---

# 14. `close()` Semantics

```text
Running
↓
Closing
```

意味着：

```text
reject new submissions
preserve accepted queued work
workers continue processing
sink drains results
exit when pipeline empty
```

也就是：

> **Graceful Drain**

---

# 15. `abort()` Semantics

```text
Running / Closing
↓
Stopping
```

意味着：

```text
reject new submissions
wake all waiters
request cancellation
queued work may be cancelled
running work cooperatively stops where safe
```

---

# 16. `join()`

只负责：

> 等待 runtime execution结束。

它不应该暗中决定：

```text
drain or abort?
```

所以：

```cpp
runtime.close();
runtime.join();
```

和：

```cpp
runtime.abort();
runtime.join();
```

语义明确不同。

---

# Part IV · Data Model

# 17. `InputItem`

我们采用：

```cpp
using ItemId = std::uint64_t;

struct InputItem {
    ItemId id{};
    std::vector<std::byte> payload;
};
```

第一版非常直接。

但这里立即值得问：

> queue 移动一个 vector 到底移动什么？

---

# 18. `vector` Move

通常：

```text
InputItem move
↓
move vector control state
↓
payload allocation ownership transferred
```

而不是复制整个 payload。

因此：

```text
small control object
+
large movable heap payload
```

是一个合理初始设计。

---

# 19. 但长期更好的 Representation

性能阶段可以演进为：

```cpp
class BufferLease {
public:
    // move-only
};

struct InputItem {
    ItemId id{};
    BufferLease payload;
    std::size_t size{};
};
```

这样：

```text
Payload storage
```

从：

```text
per-item vector allocation
```

转向：

```text
buffer pool
```

但第一版不要提前实现 pool。

---

# 20. 为什么不直接裸 Pointer？

不使用：

```cpp
struct InputItem {
    std::byte* data;
    std::size_t size;
};
```

因为它没有表达：

```text
who owns data?
who frees?
when invalid?
```

除非额外 protocol非常清楚。

G10 的默认目标：

> 让 ownership 尽可能存在于类型中。

---

# 21. Result

例如：

```cpp
struct ProcessResult {
    ItemId id{};
    std::uint64_t checksum{};
    std::size_t record_count{};
};
```

它是：

```text
small
trivially movable
self-contained value
```

非常适合 queue。

---

# Part V · Borrowed Views Inside a Task

# 22. Owner 到达 Worker

Worker取得：

```cpp
InputItem item;
```

它拥有 payload。

Processor 不需要 ownership。

所以调用：

```cpp
process(
    item.id,
    std::span<const std::byte>{item.payload});
```

这里：

```text
InputItem
→ owner

span
→ temporary borrow
```

这就是 G2 + G4 的正确组合。

---

# 23. Processor API

```cpp
class Processor {
public:
    [[nodiscard]]
    ProcessResult process(
        ItemId id,
        std::span<const std::byte> input,
        WorkerScratch& scratch) const;
};
```

它明确：

```text
input
→ borrowed read-only

scratch
→ mutable caller-owned workspace

return
→ owned value
```

非常清晰。

---

# Part VI · Worker Scratch

# 24. 为什么每个 Worker 有自己的 Scratch？

如果 processing需要临时：

```text
decompression buffer
parse buffer
temporary records
```

差的设计：

```cpp
std::vector<std::byte> global_scratch;
std::mutex scratch_mutex;
```

所有 worker抢同一个 buffer。

---

# 25. Per-worker Scratch

```cpp
struct WorkerScratch {
    std::vector<std::byte> decode_buffer;
    std::vector<Record> records;
};
```

每个 worker：

```text
owns one WorkerScratch
```

于是：

```text
no mutex
storage reused
cache affinity
steady-state allocation reduced
```

---

# 26. Worker Scratch Initialization

启动：

```cpp
scratch.decode_buffer.reserve(config.max_payload_size);
scratch.records.reserve(config.max_records_per_item);
```

之后 hot path：

```text
clear
reuse
```

这正是 G6：

> reserve + reuse before custom allocator。

---

# Part VII · Queue Contract

# 27. 我们需要什么 Queue？

第一版：

```text
MPMC bounded blocking queue
```

因为：

```text
multiple submitters
multiple workers
```

以及 output：

```text
multiple workers
one sink
```

其实是：

```text
input queue  → MPMC
output queue → MPSC
```

但为了第一版 simplicity：

> 两边都可以先使用同一个 mutex/CV bounded queue implementation。

---

# 28. 为什么不直接 Lock-free？

因为 G10 的目标是：

> integration correctness。

Mutex queue：

```text
clear
easy to test
easy to shutdown
strong invariants
```

如果 profiling 以后证明：

```text
queue synchronization
```

是主要瓶颈，

再替换。

---

# 29. Queue API

```cpp
enum class PushResult {
    Accepted,
    Closed,
};

template <typename T>
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t capacity);

    PushResult push(T value);

    std::optional<T> pop();

    void close() noexcept;

    void abort() noexcept;

    [[nodiscard]]
    std::size_t size() const;
};
```

---

# 30. 为什么 `push(T value)`？

它是：

> by-value ownership sink。

Caller：

```cpp
queue.push(item);            // copy
queue.push(std::move(item)); // move
```

内部：

```cpp
queue_.push_back(std::move(value));
```

表达清晰。

---

# 31. `pop()` 为什么返回 `optional<T>`？

语义：

```text
T
→ got an item

nullopt
→ queue permanently closed/aborted and no item available
```

这比：

```cpp
bool pop(T& out);
```

更 value-oriented。

如果实际性能证明大 `T` return 有问题，

可以再调整。

---

# Part VIII · BoundedQueue State Machine

# 32. Queue States

```cpp
enum class QueueState : std::uint8_t {
    Open,
    Closed,
    Aborted,
};
```

---

# 33. Producer Predicate

```text
state != Open
OR
size < capacity
```

如果：

```text
Open + full
```

等待。

如果：

```text
Closed / Aborted
```

立即返回拒绝。

---

# 34. Consumer Predicate

```text
state == Aborted
OR
!queue.empty()
OR
state == Closed
```

---

# 35. Closed Semantics

```text
Closed + non-empty
→ continue drain

Closed + empty
→ end-of-stream
```

---

# 36. Aborted Semantics

可以定义：

```text
abort
→ destroy/discard all queued items
→ wake everyone
→ pop returns nullopt
```

注意：

> 这必须是明确 contract。

---

# Part IX · Queue Implementation

# 37. Skeleton

```cpp
template <typename T>
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t capacity)
        : capacity_{capacity} {}

    PushResult push(T value) {
        std::unique_lock lock{mutex_};

        not_full_.wait(lock, [&] {
            return state_ != QueueState::Open ||
                   queue_.size() < capacity_;
        });

        if (state_ != QueueState::Open) {
            return PushResult::Closed;
        }

        queue_.push_back(std::move(value));

        lock.unlock();
        not_empty_.notify_one();

        return PushResult::Accepted;
    }

    std::optional<T> pop() {
        std::unique_lock lock{mutex_};

        not_empty_.wait(lock, [&] {
            return state_ != QueueState::Open ||
                   !queue_.empty();
        });

        if (state_ == QueueState::Aborted) {
            return std::nullopt;
        }

        if (queue_.empty()) {
            return std::nullopt;
        }

        T value = std::move(queue_.front());
        queue_.pop_front();

        lock.unlock();
        not_full_.notify_one();

        return value;
    }

private:
    std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;

    std::deque<T> queue_;

    std::size_t capacity_{};
    QueueState state_{QueueState::Open};
};
```

`close()` / `abort()` 补齐即可。

---

# 38. 为什么用 `deque`？

这里 queue逻辑：

```text
push_back
pop_front
```

而且：

```text
不要求 contiguous batch view
```

所以 deque 是合理 baseline。

后续如果 profiling证明：

```text
queue locality
```

重要，可以替换：

```text
preallocated ring buffer
```

但 API 不变。

这就是 representation hiding 的价值。

---

# Part X · Worker

# 39. Worker Representation

```cpp
class Worker {
public:
    Worker(
        std::size_t index,
        BoundedQueue<InputItem>& input,
        BoundedQueue<ProcessResult>& output,
        const Processor& processor,
        const RuntimeConfig& config);

private:
    void run(std::stop_token stop) noexcept;

    std::size_t index_{};

    BoundedQueue<InputItem>& input_;
    BoundedQueue<ProcessResult>& output_;

    const Processor& processor_;

    WorkerScratch scratch_;

    std::jthread thread_;
};
```

---

# 40. Borrowed Dependencies

Worker拥有：

```text
thread
scratch
```

但借用：

```text
input queue
output queue
processor
config-derived values
```

因此必须保证：

> Runtime owns those dependencies longer than Worker thread lifetime.

---

# 41. Member Order

重要：

```cpp
WorkerScratch scratch_;
std::jthread thread_;
```

thread 最后声明。

于是：

```text
destruction:
thread join first
↓
scratch destroyed
```

避免 worker访问已销毁 scratch。

---

# 42. Worker Loop

```cpp
void Worker::run(std::stop_token stop) noexcept {
    try {
        for (;;) {
            if (stop.stop_requested()) {
                return;
            }

            auto item = input_.pop();

            if (!item) {
                return;
            }

            auto result =
                processor_.process(
                    item->id,
                    item->payload,
                    scratch_);

            if (output_.push(
                    std::move(result)) !=
                PushResult::Accepted) {
                return;
            }
        }
    } catch (...) {
        // report runtime failure
    }
}
```

但是这段还不够好。

---

# 43. Cancellation Gap

如果 Worker blocked：

```cpp
input_.pop();
```

然后 Runtime：

```cpp
request_stop();
```

单独 stop token：

> 未必能唤醒 queue CV。

因此 abort需要：

```text
input_queue.abort()
output_queue.abort()
```

使 wait predicate成立并 `notify_all()`。

这比到处 stop callback 更直接。

---

# 44. Lifecycle Responsibility

这里：

```text
Queue close/abort
```

负责：

> interrupt blocking queue waits。

`stop_token`：

> 传播 CPU task cancellation。

二者角色不同。

这正是 G7.7 的模型。

---

# Part XI · Runtime Ownership Graph

# 45. Runtime Owns Everything

```cpp
class Runtime {
private:
    RuntimeConfig config_;

    Processor processor_;

    BoundedQueue<InputItem> input_;
    BoundedQueue<ProcessResult> output_;

    Sink sink_;

    std::vector<Worker> workers_;

    std::jthread sink_thread_;
};
```

但我们马上要检查 destruction order。

---

# 46. Dependency Graph

Workers依赖：

```text
processor
input
output
```

Sink thread依赖：

```text
output
sink
```

所以它们必须：

> 比 threads 活得久。

---

# 47. Declaration Order

更合理：

```cpp
RuntimeConfig config_;

Processor processor_;
Sink sink_;

BoundedQueue<InputItem> input_;
BoundedQueue<ProcessResult> output_;

std::vector<Worker> workers_;
std::jthread sink_thread_;
```

析构反序：

```text
sink_thread
workers
output
input
sink
processor
config
```

但 shutdown仍应该显式进行，

而不是只依赖成员析构碰巧正确。

---

# Part XII · Sink

# 48. Sink Thread

单独线程：

```text
OutputQueue
    ↓
Sink Thread
    ↓
Sink State
```

只有一个 writer修改：

```text
statistics / output
```

所以 Sink内部可以：

> single-writer ordinary mutable state。

不需要全局 mutex。

---

# 49. Sink Example

```cpp
class Sink {
public:
    void consume(ProcessResult result) {
        ++count_;
        checksum_ ^= result.checksum;
    }

    [[nodiscard]]
    SinkSummary summary() const;

private:
    std::uint64_t count_{};
    std::uint64_t checksum_{};
};
```

但：

> `summary()` 如果其他线程在 sink thread运行时调用，会 data race。

---

# 50. Summary Policy

第一版简单：

> 只允许 `join()` 后读取 summary。

因此：

```text
sink thread completed
↓
join
↓
read Sink
```

通过 thread completion/join建立 HB。

无需 atomics。

这就是：

> **阶段化 ownership 简化同步。**

---

# Part XIII · Runtime Start

# 51. Constructor 不一定立即启动 Threads

更稳健：

```cpp
Runtime runtime{config};

runtime.start();
```

而不是 constructor 内：

```text
立即把 this 暴露给多个 threads
```

优势：

```text
construction phase
↓
fully initialized
↓
start execution phase
```

状态更清晰。

---

# 52. `start()` Transition

只允许：

```text
Created → Running
```

重复：

```cpp
runtime.start();
```

应该：

```text
error / rejected state transition
```

而不是偷偷创建第二批 threads。

---

# Part XIV · `submit()`

# 53. Runtime API

```cpp
enum class SubmitResult {
    Accepted,
    Closed,
};

SubmitResult submit(InputItem item);
```

内部：

```text
state must be Running
↓
input queue push
```

---

# 54. Accepted Boundary

一旦：

```text
input queue owns item
```

Runtime必须承担：

> 最终 outcome responsibility。

如果 push因为 closed失败：

```text
caller still conceptually owns failed item
```

API需要避免不清晰 move-after-failure semantics。

---

# 55. 更精细的 API

可以设计：

```cpp
std::expected<void, SubmitError>
submit(InputItem item);
```

但如果失败时 caller需要拿回 original move-only item，

则 value-taking interface需要重新设计。

例如：

```cpp
SubmitResult try_submit(InputItem& item);
```

成功才 move。

这是：

> API semantics 与 ownership semantics必须一起设计。

第一版可约束：

> caller提交后不依赖失败时保留 item payload。

并写入 contract。

---

# Part XV · Processing Kernel

# 56. 一个可测 Kernel

Input：

```text
binary payload
```

定义简化 record：

```text
8-byte chunks
```

每个 chunk：

```text
u32 id
u32 value
```

Processor：

```text
validate payload size
parse records
compute checksum
count records
```

---

# 57. 为什么这个 Kernel 合适？

它足够简单：

> correctness容易验证。

但仍会触发：

```text
span
endianness
parsing
contiguous access
scratch reuse
bounds
branching
benchmark
```

适合作为 G10 integration workload。

---

# 58. Explicit Decode

不要：

```cpp
auto* records =
    reinterpret_cast<const RawRecord*>(
        input.data());
```

直接把 bytes伪装成 objects。

而：

```cpp
std::uint32_t load_u32_le(
    std::span<const std::byte, 4> bytes);
```

显式 parse。

这兑现 G1/G8：

```text
wire representation
≠
C++ object representation
```

---

# Part XVI · Error Model

# 59. 三类 Error 必须区分

### Item Error

例如：

```text
malformed payload
invalid record
```

只影响当前 item。

---

### Runtime Error

例如：

```text
worker infrastructure failed
unexpected exception
queue invariant failure
```

可能需要：

```text
abort runtime
```

---

### Cancellation

不是 error。

```text
shutdown / abort request
```

单独语义。

---

# 60. Item Result

可以：

```cpp
using ItemOutcome =
    std::expected<
        ProcessResult,
        ProcessError>;
```

然后 output queue传：

```cpp
struct CompletedItem {
    ItemId id{};
    ItemOutcome outcome;
};
```

---

# 61. 为什么 Error 也作为 Value？

这样：

```text
Worker
↓
Result Queue
↓
Sink
```

成功/失败使用：

> 同一 ownership channel。

不需要 worker直接：

```text
修改 global error map
```

避免 shared mutation。

---

# Part XVII · Runtime Failure

# 62. Unexpected Exception

Thread boundary：

```cpp
catch (...) {
    runtime_error_channel.report(
        std::current_exception());
}
```

然后：

```text
request abort
```

---

# 63. Failure Channel

第一版可以：

```cpp
std::mutex error_mutex_;
std::exception_ptr fatal_error_;
```

只允许：

> first fatal error wins。

例如：

```cpp
void report_fatal(
    std::exception_ptr error) noexcept {
    {
        std::lock_guard lock{mutex_};

        if (!fatal_error_) {
            fatal_error_ = error;
        }
    }

    abort();
}
```

低频 control-path 使用 mutex：

> 完全合理。

---

# 64. 不要为低频 Failure Path 上 Lock-free

这是 G10 非常重要的一条。

Fatal error：

```text
极少发生
```

为了它设计：

```text
lock-free exception pointer publication
```

毫无必要。

系统优化应该优先 hot path。

---

# Part XVIII · Backpressure

# 65. 为什么 Queue Capacity 是 First-class Config？

```cpp
struct RuntimeConfig {
    std::size_t worker_count{};
    std::size_t input_capacity{};
    std::size_t output_capacity{};

    std::size_t max_payload_size{};
    std::size_t max_records_per_item{};
};
```

这些不是：

> implementation trivia。

它们决定：

```text
memory bound
burst tolerance
latency
```

---

# 66. Approximate Memory Budget

假设：

```text
input capacity = 256
max payload    = 1 MiB
```

如果每个 item 都独立持有满 payload：

```text
worst-ish input payload live memory
≈ 256 MiB
```

再加：

```text
workers
scratch
output
allocator overhead
```

因此 queue capacity应该和：

> memory budget

联合设计。

---

# 67. Count-based Capacity 不一定足够

如果 item size差异巨大：

```text
1 KiB
1 MiB
100 MiB
```

`capacity = 100`

并不能真正 bound bytes。

高级版本可以：

> Byte-budget Queue。

---

# 68. Byte-budget Queue

每个 item具有：

```cpp
std::size_t memory_cost() const noexcept;
```

Queue跟踪：

```text
used_bytes
```

Push predicate：

```text
used_bytes + item_cost <= capacity_bytes
```

这更适合：

> variable-size payload systems。

---

# 69. 为什么第一版先 Count-bound？

因为先验证：

```text
ownership
shutdown
threading
correctness
```

再增加：

```text
byte accounting
```

避免一次引入过多 invariants。

G10强调：

> **Complexity staging**

---

# Part XIX · Shutdown Protocol

# 70. Graceful Close

完整顺序：

```text
1. Runtime Running → Closing

2. InputQueue.close()
   no new submissions

3. Workers drain input queue

4. Last worker completion eventually closes output queue

5. Sink drains output queue

6. Sink exits

7. Join workers + sink

8. State → Stopped
```

注意：

> 谁负责关闭 output queue？

---

# 71. 不能在 `close()` 时立即关闭 Output

如果：

```text
input closed
```

workers仍可能正在：

```text
process item
↓
push result
```

如果 output同时被 closed：

> accepted input 的结果可能无法提交。

破坏：

```text
Accepted → one outcome
```

Invariant。

---

# 72. Output Close 需要 Completion Coordination

需要知道：

> 所有 workers 都不会再 produce result。

简单方案：

```text
Runtime owner:
close input
join all workers
close output
join sink
```

顺序：

```text
close input
↓
workers drain
↓
join workers
↓
close output
↓
sink drains
↓
join sink
```

非常清晰。

---

# 73. 这比 Last-worker Atomic 更简单

另一种可以：

```text
worker_count atomic decrement
last worker closes output
```

但为什么需要？

Owner本来就有：

```text
join workers
```

这个自然 phase barrier。

所以第一版：

> 用结构化 phase ordering。

不要为了并发而增加不必要并发。

---

# 74. Graceful Shutdown Final Sequence

```text
stop accepting submissions
        ↓
close input
        ↓
workers drain input
        ↓
join workers
        ↓
close output
        ↓
sink drains output
        ↓
join sink
        ↓
Stopped
```

这是 G10 的核心 shutdown invariant。

---

# 75. Abort Sequence

```text
state → Stopping
↓
input.abort()
↓
output.abort()
↓
request_stop workers/sink
↓
wake all waits
↓
join workers
↓
join sink
↓
Stopped
```

Queued data：

> 按 contract 丢弃/取消。

---

# Part XX · Worker Count

# 76. Default

Config允许：

```cpp
worker_count = N;
```

CLI 可默认：

```text
hardware_concurrency hint
```

但：

> 不把它叫 optimal。

---

# 77. Benchmark Sweep

必须实际测试：

```text
1
2
4
8
...
```

测：

```text
items/sec
MiB/sec
p50
p99
queue depth
CPU utilization
```

G6 measurement discipline在 G10第一次真正落地。

---

# Part XXI · Metrics

# 78. 最小 Metrics

必须至少观察：

```text
submitted
completed
failed
cancelled

input queue depth
output queue depth

processing latency
queue latency

bytes processed
```

---

# 79. 不要每个 Item 打 Log

Hot path：

```cpp
std::println(...)
```

会彻底污染：

```text
performance
timing
contention
```

Metrics使用：

```text
counters
periodic aggregation
```

日志只记录：

```text
state transitions
errors
configuration
```

---

# 80. Per-worker Metrics

```cpp
struct WorkerMetrics {
    std::uint64_t processed{};
    std::uint64_t failed{};
    std::uint64_t bytes{};
};
```

由 worker独占修改。

Join后聚合：

```text
无需 atomic
```

如果需要 runtime live metrics，

可升级为：

```text
cache-line-separated per-worker atomics
```

但第一版：

> post-join metrics 足够。

---

# Part XXII · Latency Instrumentation

# 81. Item Timestamp

Submit：

```cpp
item.enqueued_at =
    std::chrono::steady_clock::now();
```

Worker dequeue：

```text
start_at
```

Completion：

```text
finish_at
```

于是：

```text
Queue Delay
=
start - enqueue

Processing Time
=
finish - start

End-to-end
=
finish - enqueue
```

---

# 82. 为什么使用 `steady_clock`？

性能 duration：

> 不应该受 wall-clock adjustment影响。

所以：

```cpp
std::chrono::steady_clock
```

是正确 abstraction。

---

# Part XXIII · Memory Strategy v1

# 83. First Version

```text
InputItem.payload
→ vector<byte>

WorkerScratch
→ reusable vectors

Queues
→ deque values
```

允许 per-input allocation。

目标：

> 正确 baseline。

---

# 84. Profile 后可能发现

```text
allocation 25%
```

再进入 v2：

```text
BufferPool
BufferLease
```

---

# 85. Buffer Pool Architecture

```text
BufferPool
┌───────────┐
│ buffer 0  │
│ buffer 1  │
│ buffer 2  │
└───────────┘
      │
      ▼
 BufferLease
```

Lease move-only。

析构：

```text
return buffer to pool
```

RAII。

---

# 86. `BufferLease`

```cpp
class BufferLease {
public:
    BufferLease() = default;

    BufferLease(
        const BufferLease&) = delete;

    BufferLease&
    operator=(const BufferLease&) = delete;

    BufferLease(
        BufferLease&&) noexcept;

    BufferLease&
    operator=(BufferLease&&) noexcept;

    ~BufferLease();

    [[nodiscard]]
    std::span<std::byte> bytes() noexcept;

private:
    BufferPool* pool_{};
    Buffer* buffer_{};
};
```

它正好验证：

```text
G2 Rule of Five
G3 Move
G4 span
G6 Pool
G7 queue ownership transfer
```

---

# Part XXIV · Do We Need PMR?

# 87. 第一版：不需要

不要因为 G6 学了：

```text
std::pmr
```

就把全部 containers 改成：

```cpp
std::pmr::vector
```

先测。

---

# 88. PMR 的可能位置

如果 processing每 item产生很多：

```text
small temporary allocations
```

可以：

```text
WorkerScratch
owns monotonic_buffer_resource
```

每 item：

```text
reset arena
```

形成：

```text
per-worker
per-item region allocation
```

但只有 profile证明才做。

---

# Part XXV · Processor Extensibility

# 89. 是否做 Virtual Processor？

第一版可以：

```cpp
class Processor {
public:
    ProcessResult process(...) const;
};
```

concrete type。

没必要：

```cpp
virtual ProcessResult process(...) = 0;
```

只是为了“架构好看”。

---

# 90. Runtime Generic Processor？

可以：

```cpp
template <typename Processor>
class Runtime;
```

但会把整个 runtime header/template化。

也没必要。

---

# 91. Thin Type-erased Boundary

如果确实想 runtime替换 processor：

```cpp
using ProcessFn =
    std::move_only_function<
        ProcessResult(
            ItemId,
            std::span<const std::byte>,
            WorkerScratch&)>;
```

但仍要评估：

```text
indirect call
ownership
copy/move
```

第一版 concrete Processor 最简单。

---

# Part XXVI · Runtime API

# 92. Public API

```cpp
namespace flow {

struct RuntimeConfig;

class Runtime {
public:
    explicit Runtime(RuntimeConfig config);

    ~Runtime();

    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;

    Runtime(Runtime&&) = delete;
    Runtime& operator=(Runtime&&) = delete;

    void start();

    SubmitResult submit(InputItem item);

    void close() noexcept;

    void abort() noexcept;

    void join();

    [[nodiscard]]
    RuntimeState state() const noexcept;

    [[nodiscard]]
    RuntimeSummary summary() const;

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

}
```

---

# 93. 为什么 Runtime 不 Movable？

一个 running Runtime：

```text
threads capture internal state
queues
mutexes
condition variables
```

移动整个 runtime identity：

> 没有明显价值，反而增加大量 lifetime complexity。

所以：

```cpp
Runtime(Runtime&&) = delete;
```

完全合理。

---

# 94. 为什么使用 PImpl？

G8 + G9。

Public API：

```text
small
stable
```

内部：

```text
threads
queues
Processor
metrics
```

隐藏。

收益：

```text
compile dependency
ABI flexibility
implementation evolution
```

G10 正好实际使用一次。

---

# Part XXVII · C ABI

# 95. 是否必须实现？

作为 G10验收项：

> 实现最小 C ABI。

因为它可以验证 G8 是否真正掌握。

---

# 96. C ABI Surface

```c
typedef struct flow_runtime flow_runtime;

typedef struct flow_runtime_config {
    uint32_t struct_size;
    uint32_t abi_version;

    uint32_t worker_count;
    uint32_t input_capacity;
    uint32_t output_capacity;
} flow_runtime_config;

flow_status flow_runtime_create(
    const flow_runtime_config* config,
    flow_runtime** out_runtime);

void flow_runtime_destroy(
    flow_runtime* runtime);

flow_status flow_runtime_start(
    flow_runtime* runtime);

flow_status flow_runtime_submit(
    flow_runtime* runtime,
    uint64_t item_id,
    const uint8_t* data,
    size_t size);

flow_status flow_runtime_close(
    flow_runtime* runtime);

flow_status flow_runtime_join(
    flow_runtime* runtime);
```

---

# 97. Boundary Decision

这里 submit：

```text
input borrowed only during call
```

C++ wrapper在 call内部：

```text
copy into owned InputItem
```

因此 C caller可以在 return后立即释放自己的 buffer。

简单可靠。

---

# 98. Future Zero-copy Extension

以后如果需要：

```text
zero-copy ownership transfer
```

必须增加新的 explicit ABI：

```text
buffer acquire/release
callback deleter
opaque buffer handle
```

不能偷偷把当前 borrowed contract变成 stored borrow。

那会是 semantic break。

---

# Part XXVIII · Project Structure

# 99. Repository

```text
flow-runtime/
├── CMakeLists.txt
├── CMakePresets.json
├── cmake/
│   └── FlowRuntimeConfig.cmake.in
│
├── include/
│   └── flow/
│       ├── runtime.hpp
│       ├── types.hpp
│       └── flow.h
│
├── src/
│   ├── CMakeLists.txt
│   ├── runtime.cpp
│   ├── bounded_queue.hpp
│   ├── worker.cpp
│   ├── processor.cpp
│   └── c_api.cpp
│
├── apps/
│   └── flow-bench/
│
├── tests/
│   ├── unit/
│   ├── concurrency/
│   ├── shutdown/
│   └── package/
│
├── benchmarks/
│   ├── processor_bench.cpp
│   ├── queue_bench.cpp
│   └── runtime_bench.cpp
│
└── docs/
    ├── architecture.md
    ├── invariants.md
    └── performance.md
```

---

# Part XXIX · CMake Targets

# 100. Target Graph

```text
Flow::runtime
     │
     ├── flow_cli
     ├── flow_tests
     └── external consumer
```

Optional C ABI：

> 同一 library public symbols。

或者拆：

```text
Flow::core
Flow::c_api
```

均可。

第一版保持一个 library更简单。

---

# 101. CMake

```cmake
add_library(flow_runtime)

add_library(
    Flow::runtime
    ALIAS
    flow_runtime
)

target_sources(flow_runtime
    PRIVATE
        runtime.cpp
        worker.cpp
        processor.cpp
        c_api.cpp

    PUBLIC
        FILE_SET HEADERS
        BASE_DIRS
            ${PROJECT_SOURCE_DIR}/include
        FILES
            ${PROJECT_SOURCE_DIR}/include/flow/runtime.hpp
            ${PROJECT_SOURCE_DIR}/include/flow/types.hpp
            ${PROJECT_SOURCE_DIR}/include/flow/flow.h
)

target_compile_features(flow_runtime
    PUBLIC
        cxx_std_23
)

set_target_properties(flow_runtime PROPERTIES
    CXX_EXTENSIONS NO
)
```

---

# 102. Internal Headers

```text
bounded_queue.hpp
```

不放：

```text
include/
```

因为它不是 public API。

放：

```text
src/
```

或者：

```text
src/detail/
```

强调：

> implementation detail。

---

# Part XXX · Build Profiles

# 103. `dev`

```text
Debug-ish
warnings
compile_commands
tests
```

---

# 104. `san`

```text
ASan
UBSan
tests
```

Thread-specific：

```text
TSan
```

最好独立 preset，

不要与 ASan机械混用。

---

# 105. `release`

```text
optimization
benchmarks
profiling
```

---

# Part XXXI · Test Strategy

# 106. Testing Pyramid

```text
Unit
↓
Concurrency Protocol
↓
Runtime Integration
↓
Shutdown
↓
Stress
↓
Package Consumer
```

---

# 107. Unit — Processor

给定 bytes：

```text
known records
```

验证：

```text
checksum
count
parse errors
```

完全单线程。

---

# 108. Unit — Queue

测试：

```text
FIFO
full blocking
close
abort
move-only values
```

---

# 109. Concurrency Queue Tests

例如：

```text
4 producers
4 consumers
1M IDs
```

最终验证：

```text
each accepted ID consumed exactly once
```

可以：

```text
sort results
compare expected sequence set
```

不要只：

> “跑完没 crash”。

---

# 110. TSan

运行 concurrency tests：

```text
ThreadSanitizer profile
```

目标：

```text
no data races
```

但仍需 protocol reasoning。

---

# 111. Shutdown Tests

必须覆盖：

```text
close while queue empty
close while queue full
close with tasks running
abort while producers blocked
abort while workers blocked
repeated close
repeated abort
join after close
```

Shutdown bugs通常藏在：

> 非 happy path。

---

# 112. Lifetime Tests

尤其：

```text
Runtime destroyed immediately after start
Runtime destroyed after close
C handle destroyed after join
```

确保：

```text
no UAF
no terminate
no hanging thread
```

ASan 很有价值。

---

# 113. Fault Injection

Processor故意：

```cpp
throw std::runtime_error{"injected"};
```

验证：

```text
worker catches
fatal error recorded
runtime aborts
join terminates
error observable
```

这是 thread error boundary 的实际验收。

---

# Part XXXII · Property-style Invariants

# 114. Accepted Count Equation

Graceful drain后：

```text
accepted
=
succeeded
+
failed
```

如果有 cancellation：

```text
accepted
=
succeeded
+
failed
+
cancelled
```

这是非常强的 runtime invariant。

---

# 115. No Duplicate

对于 unique ItemId：

```text
each accepted id
→ exactly one completion outcome
```

---

# 116. Bounded Depth

instrument：

```text
max_observed_queue_depth
```

必须：

```text
<= configured capacity
```

---

# Part XXXIII · Benchmark Strategy

# 117. Processor Microbenchmark

不经过 thread/queue。

测：

```text
MiB/s
records/s
ns/item
```

回答：

> processing kernel 多快？

---

# 118. Queue Benchmark

只测：

```text
producer ↔ queue ↔ consumer
```

不同：

```text
SPSC
MPSC
MPMC-ish baseline
```

用于理解 queue overhead。

但第一版 runtime不必因为这个 benchmark立即换 queue。

---

# 119. Runtime End-to-end Benchmark

Synthetic source：

```text
generate N payloads
```

计时：

```text
submit first item
↓
all results drained
```

测：

```text
throughput
p50/p95/p99
queue wait
processing time
```

---

# 120. Worker Sweep

```text
1
2
4
8
...
```

观察：

```text
speedup
saturation
regression
```

---

# 121. Payload Sweep

```text
256 B
4 KiB
64 KiB
1 MiB
```

观察：

> Task granularity对 scheduler/queue overhead占比的影响。

---

# 122. Queue Capacity Sweep

```text
1
4
16
64
256
```

观察：

```text
throughput
queue latency
memory footprint
submit blocking
```

---

# Part XXXIV · Profiling

# 123. Baseline First

记录：

```text
commit
compiler
profile
worker count
payload size
throughput
p99
allocations
```

然后 profile。

---

# 124. Potential Outcomes

### Allocator Hot

升级：

```text
buffer reuse / pool
```

### Queue Hot

考虑：

```text
batching
SPSC/MPSC partition
ring buffer
```

### Processor Hot

看：

```text
layout
SIMD
branch
algorithm
```

### Memory-bandwidth Hot

增加 workers可能没有意义。

---

# 125. 不允许“理论优化”

每个优化必须：

```text
Hypothesis
↓
Evidence
↓
Change
↓
Measure
↓
KEEP / REVERT
```

这就是 G6 冻结后的纪律。

---

# Part XXXV · Optimization Ladder

# 126. Level 0 — Correct Baseline

```text
mutex/CV queue
vector payload
per-worker scratch
```

---

# 127. Level 1 — Storage Reuse

```text
reserve
clear
reuse
```

---

# 128. Level 2 — Batch Processing

Worker一次：

```text
pop N items
process batch
push N results
```

减少：

```text
queue synchronization / item
```

---

# 129. Level 3 — Buffer Pool

减少：

```text
large allocation churn
```

---

# 130. Level 4 — Queue Topology Specialization

如果 architecture允许：

```text
MPSC → dispatcher → SPSC per worker
```

可能降低 contention。

---

# 131. Level 5 — SoA Processing

如果 processing kernel只访问少数 fields：

```text
AoS → SoA
```

---

# 132. Level 6 — PMR / Arena

仅当：

```text
small temp allocations
```

是真实 hotspot。

---

# 133. Level 7 — Lock-free

只有：

```text
queue synchronization
```

已经被 profile证明是主要瓶颈，

且 architecture/sharding/batching 不足时才考虑。

---

# Part XXXVI · Why Batching Usually Comes Before Lock-free

# 134. 例子

原：

```text
1 item
→ queue lock
→ notify
→ worker
```

每秒：

```text
10M items
```

同步频率：

```text
10M/s
```

改为：

```text
64 items / batch
```

同步约：

```text
156k/s
```

降低约两个数量级。

通常远比：

> 把 mutex换成更复杂 CAS

有效。

---

# 135. Batch Type

```cpp
struct InputBatch {
    std::vector<InputItem> items;
};
```

但这又可能产生：

```text
nested allocations
```

可以进一步：

```text
fixed-capacity batch
```

或者：

```text
vector reserve/reuse
```

依 profile演进。

---

# Part XXXVII · Data-oriented Processing

# 136. Parse Output

第一版：

```cpp
struct Record {
    std::uint32_t id;
    std::uint32_t value;
};

std::vector<Record> records;
```

AoS。

---

# 137. 如果 Kernel 只 Aggregates Value

Profile后可以考虑：

```cpp
struct Records {
    std::vector<std::uint32_t> ids;
    std::vector<std::uint32_t> values;
};
```

SoA。

但必须重新处理：

```text
column invariant
exception safety
allocation topology
```

不提前优化。

---

# Part XXXVIII · Shared Configuration

# 138. Processor Config

如果 runtime运行期间 config不变：

```cpp
const Processor processor_;
```

Workers：

```text
read-only
```

天然并发友好。

---

# 139. Dynamic Configuration

高级扩展：

```text
Config V1
↓
atomic shared_ptr<const Config>
↓
Config V2
```

immutable snapshot。

这可以作为 G7.9 的实际扩展实验。

不是 v1 requirement。

---

# Part XXXIX · No Global State

# 140. 禁止

```cpp
static Runtime* global_runtime;
static std::mutex global_mutex;
```

核心组件通过：

```text
explicit ownership
constructor injection
```

获得 dependencies。

好处：

```text
tests
multiple runtime instances
lifetime clarity
```

---

# Part XL · Logging

# 141. 日志策略

只在：

```text
start
close
abort
fatal error
summary
```

这些 control path 打 log。

不要：

```text
one log per record
```

---

# 142. Structured Fields

例如：

```text
event=runtime_started
workers=8
input_capacity=128
```

而不是大量：

> 不可机器解析的随意字符串。

具体 logging library不是 G10重点。

---

# Part XLI · Resource Accounting

# 143. Runtime Summary

```cpp
struct RuntimeSummary {
    std::uint64_t submitted{};
    std::uint64_t succeeded{};
    std::uint64_t failed{};
    std::uint64_t cancelled{};

    std::uint64_t bytes{};
};
```

Join后：

```text
immutable summary
```

供 caller获取。

---

# 144. 最重要检查

Graceful：

```text
submitted
=
succeeded
+
failed
```

Abort：

```text
submitted
=
succeeded
+
failed
+
cancelled
```

如果不成立：

> ownership/outcome protocol存在漏洞。

---

# Part XLII · Exception Guarantees

# 145. `submit()`

如果 queue insertion因为 allocation抛异常怎么办？

第一版：

```text
InputQueue internal deque may allocate
```

`submit()` 可以传播：

```text
std::bad_alloc
```

但 Runtime state不得破坏。

---

# 146. Production Boundary

C ABI：

> exception必须转换。

C++ API：

可以选择：

```text
exceptions for infrastructure failure
expected for domain failure
```

但 contract必须统一。

---

# 147. Queue Push Strong-ish Semantics

理想：

```text
if insertion fails
→ queue unchanged
→ item remains caller-local parameter state according to operation semantics
```

标准 container已有相应 exception guarantees可利用。

不要手动写复杂 half-commit protocol。

---

# Part XLIII · Build / Install Requirements

# 148. G10 必须是真 Library

不是：

```text
只有一个 main.cpp
```

而是：

```text
Flow::runtime
```

可安装。

---

# 149. External Consumer Test

单独：

```text
consumer/
```

：

```cmake
find_package(Flow CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        Flow::runtime
)
```

必须成功。

这是 G9 验收。

---

# 150. C Header Consumer

另外一个：

```text
C-only program
```

调用：

```text
flow_runtime_create
flow_runtime_start
flow_runtime_submit
flow_runtime_close
flow_runtime_join
flow_runtime_destroy
```

这是 G8 验收。

---

# Part XLIV · Phase Plan

G10 不应一次写 3000 行。

按严格 phase推进。

---

# 151. Phase 0 — Skeleton

只完成：

```text
repository
CMake targets
presets
library
tests
install/export
```

Runtime还不处理数据。

Gate：

```text
build
test
install
external consumer
```

全部通过。

---

# 152. Phase 1 — Processor Single-threaded

实现：

```text
InputItem
Processor
ProcessResult
```

完全没有 concurrency。

Gate：

```text
functional correctness
ASan/UBSan
microbenchmark baseline
```

---

# 153. Phase 2 — BoundedQueue

实现：

```text
push
pop
close
abort
```

Gate：

```text
FIFO
bounded
move-only
multi-producer/consumer stress
TSan
shutdown tests
```

---

# 154. Phase 3 — One Worker

```text
InputQueue
↓
Worker
↓
OutputQueue
↓
Sink
```

只有：

```text
1 worker
```

先验证完整 pipeline。

---

# 155. Phase 4 — N Workers

增加：

```text
worker_count
```

验证：

```text
no duplicates
no loss
deterministic outcomes
```

---

# 156. Phase 5 — Lifecycle

正式实现：

```text
start
close
abort
join
```

大量 shutdown fault tests。

---

# 157. Phase 6 — Metrics / Benchmark

添加：

```text
queue timing
processing timing
worker metrics
runtime summary
```

建立 baseline。

---

# 158. Phase 7 — C ABI

添加：

```text
opaque handle
C lifecycle API
error conversion
```

---

# 159. Phase 8 — Profile-driven Optimization

此时才允许：

```text
buffer pool
batching
queue specialization
SoA
PMR
```

每个优化必须 ADR/measurement。

---

# Part XLV · Explicit Forbidden Premature Features

# 160. Phase 0–7 禁止

```text
custom lock-free queue
hazard pointers
hand-written SIMD
custom malloc
coroutines
template-metaprogrammed runtime
NUMA pinning
manual prefetch
```

除非：

> profile/requirements已经证明不可缺少。

这是 G10 的纪律。

---

# Part XLVI · Documentation Set

# 161. `architecture.md`

记录：

```text
pipeline
ownership graph
thread topology
state machine
```

---

# 162. `invariants.md`

只记录必须永远成立的：

```text
accepted work accounting
queue bounds
ownership
shutdown ordering
```

---

# 163. `performance.md`

每轮：

```text
baseline
hypothesis
profile
change
result
KEEP/REVERT
```

---

# 164. ADRs

只有真正需要选择时：

```text
ADR-0001 mutex queue baseline
ADR-0002 count-bound vs byte-bound
ADR-0003 buffer pooling after profiling
```

不要为显而易见的小事滥建 ADR。

---

# Part XLVII · Architecture Graphs

# 165. Ownership Graph

```text
Runtime
├── Processor
├── InputQueue
├── OutputQueue
├── Sink
├── Worker 0
│   ├── jthread
│   └── WorkerScratch
├── Worker 1
│   ├── jthread
│   └── WorkerScratch
└── SinkThread
```

---

# 166. Task Ownership

```text
Caller
  ↓ move
InputQueue
  ↓ move
Worker
  ↓ transform
OutputQueue
  ↓ move
Sink
```

---

# 167. Synchronization Graph

```text
submitters
   │ mutex/CV
   ▼
InputQueue
   │
workers
   │ mutex/CV
   ▼
OutputQueue
   │
sink thread
```

业务 payload本身：

> 不共享写入。

---

# 168. Lifetime Graph

```text
Runtime State
┌─────────────────────────────────┐
│                                 │
│ Queues                          │
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │ Worker Threads              │ │
│ │ ┌─────────────────────────┐ │ │
│ │ │                         │ │ │
│ │ └─────────────────────────┘ │ │
│ │                             │ │
│ └─────────────────────────────┘ │
│                                 │
└─────────────────────────────────┘
```

Thread lifetime必须嵌套在 dependencies lifetime内。

---

# Part XLVIII · G10 Review Protocol

面对这个 runtime，逐层问：

## Object

```text
哪些 objects存在？
```

## Ownership

```text
谁拥有 payload？
```

## Lifetime

```text
borrow/view何时失效？
```

## Value

```text
queue move真正搬什么？
```

## STL

```text
为什么是 deque/vector/span？
```

## Genericity

```text
哪部分真的需要 template？
```

## Memory

```text
allocation在哪？
working set多大？
```

## Concurrency

```text
谁写什么？
HB edge在哪？
```

## ABI

```text
public boundary暴露什么？
```

## Build

```text
external consumer能否只依赖 Flow::runtime？
```

## Performance

```text
真实瓶颈是什么？
```

这正好完整覆盖 G0–G9。

---

# Part XLIX · G10 Anti-pattern Catalogue

# 169. Global Shared Mutable Metrics

所有 worker：

```cpp
global_counter.fetch_add(...)
```

每 item执行。

第一版应：

> per-worker state + join aggregation。

---

# 170. Queue of Raw Borrowed Pointers

```cpp
queue.push(ptr);
```

但 pointee lifetime依赖 producer stack。

禁止。

---

# 171. Unbounded Queue

以：

> “避免 producer阻塞”

为理由。

禁止。

---

# 172. Worker Owns Queue

如果：

```text
each Worker creates/deletes shared queue
```

ownership拓扑混乱。

Queue应由 Runtime拥有。

---

# 173. Thread Starts Before Dependencies Constructed

G7.7 已经明确禁止。

---

# 174. Holding Queue Lock During Processing

直接摧毁 parallelism。

---

# 175. Output Queue Closed Too Early

导致：

```text
accepted input
↓
result silently lost
```

破坏系统 invariant。

---

# 176. Abort Without Wakeup

阻塞线程永远不退出。

---

# 177. Destructor-only Lifecycle

只有：

```cpp
~Runtime();
```

没有：

```text
close
abort
join
```

使重要的 potentially blocking/failure transitions 隐藏。

---

# 178. Custom Lock-free Before Profiling

禁止。

---

# 179. `shared_ptr` Everywhere

因为：

> “线程间安全”。

Lifetime safety并没有定义 mutation authority。

---

# 180. Generic Everything

```cpp
template<
    Queue Q,
    Processor P,
    Sink S,
    Allocator A,
    Scheduler X>
class Runtime;
```

第一版完全没有必要。

---

# Part L · Completion Criteria

G10 不是：

> “代码写完了。”

必须同时达到以下 Gate。

---

# 181. Correctness Gate

```text
all unit tests pass
integration tests pass
shutdown tests pass
stress tests pass
```

---

# 182. Sanitizer Gate

```text
ASan clean
UBSan clean
TSan concurrency suite clean
```

---

# 183. Ownership Gate

能够闭卷画：

```text
payload ownership graph
thread lifetime graph
queue ownership graph
```

---

# 184. Shutdown Gate

必须解释：

```text
close
abort
join
```

每一步的 state transition。

---

# 185. Performance Gate

拥有可重复 baseline：

```text
items/s
MiB/s
p50
p95
p99
worker sweep
```

---

# 186. Build Gate

```text
dev
san
release
```

presets全部工作。

---

# 187. Package Gate

```text
cmake --install
```

后：

```text
external C++ consumer
find_package(Flow)
```

成功。

---

# 188. ABI Gate

C program：

```text
create
start
submit
close
join
destroy
```

成功。

---

# 189. Explainability Gate

对于任何主要 design decision，能够回答：

```text
Why this type?
Why this owner?
Why this queue?
Why this synchronization?
Why this capacity?
Why this boundary?
What invalidates it?
What happens on failure?
```

这比代码量更重要。

---

# Part LI · G10 Final Fifteen Axioms

如果完成项目后只能记住十五条：

1. **真实系统设计应该从 invariants、ownership 和 lifecycle 出发，而不是从 class diagram 出发。**

2. **Queue 不只是数据结构，而是 backpressure boundary、synchronization boundary 和 ownership-transfer boundary。**

3. **Accepted work 必须拥有明确 terminal outcome；“进入系统后静默消失”属于 protocol failure。**

4. **大型 mutable payload 应尽量沿 pipeline 单一所有权移动，而不是跨 workers 共享修改。**

5. **Processor 应借用输入、拥有局部 scratch、返回 value；不要让 domain kernel承担 runtime synchronization。**

6. **每 worker 独占 scratch/reusable storage，通常比全局共享 buffer + mutex 更自然、更快。**

7. **第一版并发 runtime 应优先 mutex/CV bounded queue；lock-free 必须由 profile 或 progress requirement证明。**

8. **`close`、`abort`、`join` 是不同 lifecycle operations，必须拥有不同 contract。**

9. **Graceful drain 的正确顺序是关闭输入 → workers drain → join workers → 关闭输出 → sink drain → join sink。**

10. **Thread lifetime 必须严格嵌套在它访问的 state lifetime内；join 是重要的 lifetime barrier。**

11. **错误应该沿明确 channel 传播；domain error、runtime failure 和 cancellation 是三种不同语义。**

12. **资源 bounded 不只是 queue item count，还最终应该考虑 bytes、scratch、buffers 和 high-water memory。**

13. **性能优化顺序应优先 reuse、batching、sharding和data layout，再考虑 allocator tricks 和 lock-free。**

14. **一个 native library 只有在 build、test、install、external consumption 和 ABI boundary都成立后才算工程完成。**

15. **G10 的目标不是写出最复杂的 runtime，而是能证明一个足够简单的 runtime为什么正确、为什么 bounded、为什么性能合理。**

---

# Part LII · G10 Final Gate

完成后应能闭卷回答：

### Ownership

1. `InputItem` 从 caller 到 worker 的 ownership怎样变化？
2. 为什么 Processor 参数应该是 `span` 而不是 `vector`？
3. 为什么 queue 中的 raw borrowed pointer 很危险？

### Queue

1. 为什么 queue 必须 bounded？
2. full 是 error 还是系统状态？
3. mutex/CV queue为什么是合理 baseline？
4. 为什么不能持 queue lock处理 item？

### Worker

1. 为什么每 worker应该有自己的 scratch？
2. 为什么 worker thread必须晚于 dependencies构造、早于 dependencies析构？
3. 为什么 thread entry应该是 exception boundary？

### Shutdown

 1. `close` 与 `abort` 有什么根本区别？
 2. 为什么 close input 后不能立刻 close output？
 3. 为什么 output queue要在 workers完全结束之后再关闭？
 4. 为什么 abort必须 wake blocked waiters？

### Memory

 1. 哪些 allocations发生在 hot path？
 2. `reserve + clear` 消除了什么？
 3. 什么时候值得引入 BufferPool？

### Concurrency

 1. 哪些 state 真正 shared mutable？
 2. 为什么 Sink可以不使用 atomic counters？
 3. 哪个 synchronization relation保证 join后 summary可安全读取？

### ABI

 1. C ABI 为什么使用 opaque handle？
 2. 为什么 C submit API采用 pointer + size？
 3. 为什么异常不能逃出 C ABI？

### Build

 1. 为什么 runtime应该成为 installable target？
 2. 为什么 external consumer test是 G9 的真正验收？

### Performance

 1. 应先测 processor还是直接换 lock-free queue？
 2. 为什么 batching通常优先于 CAS微优化？
 3. 为什么 worker_count 必须测量而不是按 CPU 数猜？
 4. queue capacity怎样影响 throughput、latency和memory？

### Architecture

 1. 如果 profiling显示 output queue contention严重，第一反应应该是什么？

不是：

```text
“立刻手写 lock-free MPMC”
```

而应该依次考虑：

```text
batch results?
MPSC specialization?
one result batch per worker?
per-worker sink/sharding?
queue really dominant?
```

这就是 G10 要形成的系统工程思维。

---

# G10 完成状态

```text
G10.1   Requirements / Non-goals
G10.2   Invariants
G10.3   Runtime State Machine
G10.4   Data / Ownership Model
G10.5   Bounded Queue
G10.6   Worker / Scratch
G10.7   Processing Kernel
G10.8   Error Model
G10.9   Backpressure
G10.10  Shutdown / Drain / Abort
G10.11  Metrics / Observability
G10.12  Memory Strategy
G10.13  Profiling / Optimization Ladder
G10.14  C ABI
G10.15  CMake / Install / Package
G10.16  Tests / Sanitizers / Stress
G10.17  Benchmarks / Performance Gate
─────────────────────────────────────────
G10      COMPLETE ARCHITECTURE BASELINE
```

这里的 **COMPLETE** 和之前 G0–G9 稍有不同：

G0–G9 的完整意味着：

> 知识章节已经整理完成。

G10 的完整意味着：

> **项目规格、架构和验收标准已经完整；真正掌握 G10 必须实际把它实现并测出来。**

因此从课程意义上，G10 已经从“读文档”进入：

```text
Design
↓
Implement
↓
Break
↓
Debug
↓
Measure
↓
Refactor
```

的阶段。

---

# 下一章：G11 — Robotics C++

G11 会直接以完整章节形式进入你最终目标之一：

# **Robotics Systems with Modern C++23**

不会变成 ROS 2 API 教程，而是围绕真正的机器人系统约束：

```text
Sensor Input
    ↓
Timestamp / Synchronization
    ↓
State Estimation
    ↓
Planning
    ↓
Control
    ↓
Actuation
```

系统讨论：

```text
hard / soft real-time
control-loop deadlines
latency vs jitter
allocation discipline
fixed-capacity containers
sensor ownership
zero-copy boundaries
Eigen-style numerical data
coordinate frames
timestamp semantics
lock-free vs single-writer control state
double buffering
snapshot publication
thread/core topology
ROS 2 boundaries
DDS/QoS concepts
hardware SDK boundaries
C ABI/device drivers
failure / watchdog / safe state
```

最终会回答一个比“机器人为什么用 C++”更重要的问题：

> **机器人系统里的 C++ 到底承担哪类责任，哪些代码必须追求可预测性，哪些部分反而应该保持普通、清晰、可维护。**
