# G6 分配策略与性能测量

上一单元只看扫描：给定一批已经存在的读数，怎样排列和访问它们。真实系统还要接收新批次、准备存储、构造对象，并在处理完成后清理。如果每轮扫描节约的时间，被重新分配和转换全部吃掉，局部优化就没有解决用户面对的问题。

本单元仍沿同一批 Reading 推进。先观察资源请求落在哪个阶段，再测量已经定义清楚的扫描内核。分配次数、对象生命周期、进程内存和执行耗时分别回答不同问题；只有把它们接回同一条工作流，才有可能做出可靠的性能判断。

## 1 分配一次存储，不等于构造一次对象

### 1.1 四个操作有四种成本

分配（allocation）取得满足大小和对齐要求的存储；构造（construction）在其中建立对象及其初始状态；析构（destruction）执行对象结束时的工作；释放（deallocation）把存储交还给相应资源。G1/G2 已经解释了正确性，本章只计量它们发生在哪里，不再重新推导对象生命规则。

`vector::reserve` 能提前取得容量，却不会因此创建那么多个元素；之后的插入才增加 size。`clear` 结束元素生命周期，保留可复用容量。即使清理后 size 为零，vector 仍可能持有大量存储。只有把“有多少有效对象”和“保留多少可用存储”分开，才能解释为什么预留后插入很快、清空后进程内存却没有明显下降。[N4950：vector 容量](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity)、[清理与修改](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers)

分配器自身也不是一次系统调用的同义词。通用分配器可能从线程缓存或既有块中满足请求，也可能需要获取新内存、同步共享元数据或处理较大的请求。释放给分配器不保证立刻归还操作系统；虚拟地址预留、物理页准备和首次触及也可能发生在不同时间。因而“malloc 次数减少”是一个机制变化，不是同等比例的延迟收益承诺。

### 1.2 存储持续期不能直接变成速度排名

自动存储持续期对象常由栈帧承载，但编译器可能将其放进寄存器或完全消除；含 vector 成员的局部对象，其元素仍可使用动态存储。动态分配对象也可能在很长时间内反复使用，初始化成本只付一次。“栈快、堆慢”省略了对象大小、访问模式、分配频率和优化结果，无法指导当前批处理。

这里更有用的问题是：每个业务批次新增了哪些资源请求？哪些请求只是为了重复获得同样大小的工作区？改变复用周期后，峰值保留量和失败边界发生了什么？先把工作量定位，之后才谈消除某类成本。

## 2 在资源边界观察请求

allocation policy 改变的是资源请求何时发生、由谁满足、何时归还；它不直接规定对象算法或机器最终耗时。因此本节先把 instrumentation boundary（计量边界）固定在 memory_resource，再讨论请求量。对这一边界之外的系统分配、页准备或缓存效果，不能用计数器的零值推出“没有成本”。

### 2.1 计数器究竟看到了什么

多态内存资源（polymorphic memory resource，PMR）把分配策略放进运行时资源对象，容器通过 `polymorphic_allocator` 请求存储。下面的包装器只计数成功通过它的请求，并把真正的分配交给 upstream。它不是全进程 malloc 拦截器，不观察 RSS，不知道分配器内部碎片，也不计入其他未经过它的对象。

**完整实验 G6-A1/A2 的资源包装器 · `counting-resource.hpp` · 单线程仪器**

```cpp
#pragma once
#include <algorithm>
#include <cstddef>
#include <memory_resource>

class CountingResource final : public std::pmr::memory_resource {
    std::pmr::memory_resource* upstream_ = std::pmr::new_delete_resource();
    void* do_allocate(std::size_t bytes, std::size_t alignment) override {
        void* p = upstream_->allocate(bytes, alignment);
        ++allocations;
        requested_bytes += bytes;
        live_bytes += bytes;
        peak_bytes = std::max(peak_bytes, live_bytes);
        return p;
    }
    void do_deallocate(void* p, std::size_t bytes, std::size_t alignment) override {
        upstream_->deallocate(p, bytes, alignment);
        ++deallocations;
        live_bytes -= bytes;
    }
    bool do_is_equal(const std::pmr::memory_resource& other) const noexcept override {
        return this == &other;
    }
public:
    std::size_t allocations = 0;
    std::size_t deallocations = 0;
    std::size_t requested_bytes = 0;
    std::size_t live_bytes = 0;
    std::size_t peak_bytes = 0;
    CountingResource() = default;
    CountingResource(const CountingResource&) = delete;
    CountingResource& operator=(const CountingResource&) = delete;
};
```

`requested_bytes` 是累计成功请求量，`live_bytes` 是尚未配对释放的请求量，`peak_bytes` 是本包装层的峰值。累计量可以很大而峰值很小，例如每批创建再销毁同样大小的缓冲；峰值也可以长期不降，例如持续保留工作区。内部碎片描述分配块中未被有效载荷利用的部分，外部碎片描述空闲空间的分布妨碍满足某类请求；这个计数器都无法直接测量它们。

包装器依赖合法的 allocate/deallocate 配对，计数使用本章有界工作负载，不处理计数溢出、任意指针或并发调用。资源相等表示双方可以按资源合同互相释放分配物，不是“底层都用了 new 就一定相等”；这里保守地只认为自身相等。[N4950：memory_resource](https://timsong-cpp.github.io/cppwp/n4950/mem.res.class)

### 2.2 比较每批重建与保留容量

现在处理 16 批、每批 512 条读数。两条路径都预留足够容量，也逐字段检查当前批次。第一条每批结束就销毁 vector，第二条在批次之间 clear 并复用。这样观察的是复用周期，不把“未 reserve”混成另一个变量。

**完整实验 G6-A1 · `reuse.cpp` · 正确性判据与资源观察分开**

```cpp
#include "readings.hpp"
#include "counting-resource.hpp"
#include <iostream>
#include <memory_resource>

constexpr std::size_t count = 512;
constexpr int batches = 16;

void fill(std::pmr::vector<Reading>& data, int batch) {
    for (std::size_t i = 0; i < count; ++i) {
        data.push_back({static_cast<int>(i), batch * 10 + static_cast<int>(i),
                        i % 2 == 0});
    }
}

bool correct(const std::pmr::vector<Reading>& data, int batch) {
    if (data.size() != count) return false;
    for (std::size_t i = 0; i < count; ++i) {
        if (data[i] != Reading{static_cast<int>(i),
                batch * 10 + static_cast<int>(i), i % 2 == 0}) return false;
    }
    return true;
}

int main() {
    CountingResource fresh;
    for (int batch = 0; batch < batches; ++batch) {
        std::pmr::vector<Reading> data(&fresh);
        data.reserve(count);
        fill(data, batch);
        if (!correct(data, batch)) return 1;
    }
    CountingResource reused;
    {
        std::pmr::vector<Reading> data(&reused);
        data.reserve(count);
        const auto capacity = data.capacity();
        const auto requests = reused.allocations;
        for (int batch = 0; batch < batches; ++batch) {
            data.clear();
            if (!data.empty() || data.capacity() != capacity) return 2;
            fill(data, batch);
            if (!correct(data, batch)) return 3;
            if (reused.allocations != requests) return 4;
        }
    }
    if (fresh.live_bytes != 0 || reused.live_bytes != 0 ||
        fresh.allocations != fresh.deallocations ||
        reused.allocations != reused.deallocations) return 5;
    std::cout << "{\"fresh_requests\":" << fresh.allocations
              << ",\"reused_requests\":" << reused.allocations
              << ",\"fresh_bytes\":" << fresh.requested_bytes
              << ",\"reused_bytes\":" << reused.requested_bytes
              << ",\"fresh_peak\":" << fresh.peak_bytes
              << ",\"reused_peak\":" << reused.peak_bytes << "}\n";
}
```

若观察到复用路径只在开头请求存储，所支持的命题是“这个已预留容量足够的批处理，不需要在每批重新分配元素存储”。它没有测量耗时；两条路径仍构造并处理了相同数量的元素，也没有证明任何大小的批次都不再分配。将每轮 reserve 当前 size 加一，反而可能破坏容器原有增长策略；根据已知批次上限预留，与用微小增量强迫调整容量，是不同策略。

保留容量也有代价。偶发巨批次可能让工作区长期占据较高内存，多个工作线程各自保留峰值时尤其明显。回收策略应基于高水位、空闲阶段与延迟预算决定；`shrink_to_fit` 不是必须释放的命令，更不应该在每次 clear 后机械调用，抵消原本想获得的复用。

## 3 arena 改变的是回收单位

### 3.1 从单对象释放到阶段释放

arena 把若干分配归到同一个存储区域，在阶段结束时整体回收。`monotonic_buffer_resource` 是一种适合这种用途的标准资源：逐次分配消耗当前缓冲区，空间不足时可向 upstream 请求新块，单独的 deallocate 不回收这些块。它适合生命周期自然成批的工作，不适合只因为“分配很多”就无限持有所有历史块。

对象清理与存储回收仍是两层责任。资源只认识大小、对齐和块，不知道其中放了几个带析构副作用的对象。释放 arena 不会替代这些对象的析构；反过来，容器 clear 也不要求 arena 立刻把块归还 upstream。下面把这两个时刻分别观察。[N4950：monotonic_buffer_resource](https://timsong-cpp.github.io/cppwp/n4950/mem.res.monotonic.buffer)

**完整实验 G6-A2 · `arena.cpp` · 先结束对象，再回收资源**

```cpp
#include "counting-resource.hpp"
#include <array>
#include <iostream>
#include <memory_resource>
#include <new>
#include <vector>

struct Entry {
    static inline int live = 0;
    static inline int constructed = 0;
    static inline int destroyed = 0;
    int value;
    explicit Entry(int v) : value(v) { ++live; ++constructed; }
    Entry(const Entry&) = delete;
    Entry(Entry&& other) noexcept : value(other.value) { ++live; ++constructed; }
    ~Entry() { --live; ++destroyed; }
};

int main() {
    CountingResource upstream;
    std::pmr::monotonic_buffer_resource arena(&upstream);
    {
        std::pmr::vector<Entry> entries(&arena);
        entries.reserve(16);
        for (int i = 0; i < 16; ++i) entries.emplace_back(i);
        if (Entry::live != 16) return 1;
        for (int i = 0; i < 16; ++i) {
            if (entries[static_cast<std::size_t>(i)].value != i) return 2;
        }
        entries.clear();
        if (Entry::live != 0 || upstream.live_bytes == 0) return 3;
    } // vector 先交还自己的存储；arena 的逐项 deallocate 不回收块。
    const auto retained = upstream.live_bytes;
    if (retained == 0) return 4;
    arena.release();
    if (upstream.live_bytes != 0 || Entry::constructed != Entry::destroyed ||
        upstream.allocations != upstream.deallocations) return 5;

    alignas(std::max_align_t) std::array<std::byte, 64> buffer{};
    std::pmr::monotonic_buffer_resource bounded(
        buffer.data(), buffer.size(), std::pmr::null_memory_resource());
    bool exhausted = false;
    try {
        [[maybe_unused]] void* p = bounded.allocate(buffer.size() + 1, 1);
    } catch (const std::bad_alloc&) {
        exhausted = true;
    }
    if (!exhausted) return 6;
    std::cout << "{\"upstream_requests\":" << upstream.allocations
              << ",\"retained_before_release\":" << retained
              << ",\"live_after_release\":" << upstream.live_bytes
              << ",\"constructed\":" << Entry::constructed
              << ",\"destroyed\":" << Entry::destroyed
              << ",\"bounded_exhaustion\":true}\n";
}
```

这里故意让 vector 的作用域先结束，再调用 release。即使 clear 后没有活元素，vector 仍持有容量；提前回收资源会破坏它继续使用存储的前提。只保证“arena 对象还活着”也不够：一次 release 可以在对象仍存在时结束其已分配存储的有效期。G1 的借用模型同样适用于 arena，地址看起来没变不是继续访问的许可。

有界资源的测试请求超过初始缓冲区大小，又禁止 upstream 扩展，因此实际触发 `bad_alloc`。它验证的是资源预算耗尽，不是操作系统 OOM，也不证明异常路径满足硬实时要求。真实系统必须决定超预算时拒绝、降级还是转入其他资源；选择不是 PMR 自动提供的业务语义。

### 3.2 资源对象也是生命周期图的一部分

PMR 容器保存资源关联，但通常不拥有资源对象。容器和分配物的有效使用期不能超过相关资源及其存储的有效期。把使用栈上 arena 的容器返回给调用方，不会因为返回值移动而延长 arena 的生命。若缓冲区也来自局部数组，则又增加一层依赖：缓冲区、资源、容器及借用者必须按正确顺序结束。

复制／移动也不能只看容器类型相同。未显式指定 allocator 的 PMR 容器复制构造，会通过 allocator 选择规则取得资源；`polymorphic_allocator` 的选择函数返回默认资源关联，不是无条件继承来源 arena。移动赋值在资源不等且不传播 allocator 时，可能需要在目标资源中逐元素处理；不满足 allocator 交换前提时，不能用 swap 偷换两份责任。这里只建立需要回查的条件，不把每种容器操作展开成另一本 allocator 手册。[N4950：PMR 与 allocator 选择](https://timsong-cpp.github.io/cppwp/n4950/mem.res)、[容器 allocator 要求](https://timsong-cpp.github.io/cppwp/n4950/container.alloc.reqmts)

arena 与 pool 也不同。前者适合阶段结束时一起回收，后者倾向于让适合的块在多次获取／释放之间复用。二者都不能解除 owner 的清理责任，也不自动提供稳定逻辑身份或线程安全。本章不引入自制内存池；先把请求与生命区间对齐，才有理由增加分配机制。

## 4 把性能问题写成可检查的命题

### 4.1 先选指标，再选工具

性能命题需要先固定 estimand（待估计的量）：是一个已预热内核的一次 elapsed time，还是一项请求从到达到完成的 end-to-end latency；是固定资源下的 sustained throughput，还是某个输入分布下的 tail latency。若前后版本改变了输入、统计单位或计时边界，两个精确数字仍可能不可比较。

“更快”至少有三种可能：单次请求更早完成、单位时间处理更多数据、慢请求的尾部更短。平均值可以改善而尾延迟恶化；把更多工作批在一起可以提高吞吐，同时增加单条任务的等待。当前扫描实验只测一段连续计算的 elapsed time，不涉及到达过程、排队或 deadline，不能据此宣称系统 p99 或实时性。

微基准（microbenchmark）隔离一个局部操作；端到端测量覆盖用户面对的完整路径；采样剖析（sampling profile）帮助定位时间主要落在哪里；跟踪（trace）用事件及时间关系解释等待和阶段交错。它们不是彼此替代的四种“测速按钮”。先用全路径证据确认问题值得优化，再用微基准分辨机制，最后回到全路径检验收益。

例如扫描占原耗时比例 f，若只把这一部分加速 r 倍，忽略新增开销时总体加速上限为 1/((1−f)+f/r)。这个工作量分解说明：一个占比很小的内核，即使加速很多，也未必改善用户体验。若转换又增加成本，应把它加回分母，而不是只宣传内核倍率。

### 4.2 让编译器仍然做真实工作

基准程序若计算了从未使用的结果，优化器可以合法删除工作；若输入与结果完全可知，还可能提前求值或把多次调用合并。单纯多加一个循环不保证测到了重复计算。把所有对象标成 volatile 则改变了访问约束，测量对象已经不是原程序。

本章将扫描内核放在独立翻译单元中，关闭 LTO；计时主程序只能看到普通外部声明，不知道内核实现，不能把这些调用当作无副作用的已知表达式。每次调用的结果参与最终校验和，计时后再检查。这样保留了要测的重复调用，同时也保留了函数边界成本；它代表“独立编译内核”的配置，不代表整程序内联或 LTO 配置。

真正的 benchmark 框架通常还提供防止消除、计时控制和统计功能。本章不用额外库，是为了把证据边界写明；这不是建议生产性能团队重造通用基准框架。[Google Benchmark：避免优化消除的限制](https://google.github.io/benchmark/user_guide.html#preventing-optimization)

### 4.3 Cost model 与 causal claim 的距离

一个 cost model 把假定机制连接到预期结果，causal claim（因果判断）则声称观察到的变化确由某个因素造成。AoS 换成 SoA 同时改变地址序列、表示和编译器的优化机会，所以“这个实现更快”可以有测量依据，“快的部分全部来自 cache”却还需要额外证据。

可以从一个可反驳预测开始：若主要受某层数据流量限制，改变复用次数或工作规模，应当在相应条件下改变收益；若主要受生成分支影响，固定布局但改变合法的条件求值方式，可能得到不同趋势。这些只是下一步实验设计，不是本批已经做过的测试。每次变体仍要保留相同业务结果，并检查它没有同时放宽 correctness contract。

计量工具也会改变被测对象。分配包装器多执行计数，sanitizer 增加插桩，完整 trace 引入事件记录开销；它们可以验证机制或定位路径，却不能不加说明地充当生产性能。因而本文把正确性、资源请求、生成物、耗时与动态安全检测分开，最后再将不同证据接到同一个解释上。

## 5 测量同一批读数的两种扫描

### 5.1 输入、顺序与计时区间

下面的主程序与上一单元的 `scan.cpp` 分别编译。规模为 4,096、65,536、1,048,576 条；每种规模各有成段与打乱两种顺序，打乱不改变记录集合。每组做七对测量，交替改变 AoS／SoA 的先后顺序，并在每次计时前运行一次相同内核。每个进程重新构造数据，执行器连续运行三个独立进程，不并行跑其他本章基准。

预热仅使这次调用之前已走过同样代码和数据，不保证整个工作集留在某一级缓存，更不模拟所有冷启动。转换、分配、初始化与输出全部在计时区间之外；函数调用、重复循环和两次时钟读取在区间之内。小规模多重复几次以降低时钟开销占比，大规模减少重复次数；报告先除以 pass 数，不能直接比较不同 pass 数的区间总耗时。

**完整实验 G6-M1 · `benchmark.cpp` · 耗时为观察值，不要求 SoA 获胜**

```cpp
#include "readings.hpp"
#include <chrono>
#include <iostream>
#include <string_view>

using Clock = std::chrono::steady_clock;

template<class Function>
bool measure(std::size_t n, bool shuffled, int trial, int order,
             std::string_view layout, int passes, std::uint64_t expected,
             Function function) {
    if (function() != expected) return false;
    const auto start = Clock::now();
    std::uint64_t checksum = 0;
    for (int pass = 0; pass < passes; ++pass) checksum += function();
    const auto stop = Clock::now();
    const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
        stop - start).count();
    if (checksum != expected * static_cast<std::uint64_t>(passes) || ns <= 0)
        return false;
    std::cout << "{\"n\":" << n << ",\"shuffled\":" << shuffled
              << ",\"trial\":" << trial << ",\"order\":" << order
              << ",\"layout\":\"" << layout << "\",\"passes\":" << passes
              << ",\"ns\":" << ns << ",\"checksum\":" << checksum << "}\n";
    return true;
}

int main() {
    for (std::size_t n : {4096U, 65536U, 1048576U}) {
        const int passes = n == 4096 ? 64 : (n == 65536 ? 8 : 2);
        for (bool shuffled : {false, true}) {
            const auto data = make_readings(n, shuffled);
            const auto columns = to_columns(data);
            if (!represents(data, columns)) return 1;
            std::uint64_t expected = 0;
            for (const auto& r : data) {
                if (r.valid) expected += static_cast<std::uint64_t>(r.value);
            }
            auto aos = [&] { return sum_aos(data); };
            auto soa = [&] { return sum_soa(columns.values, columns.valid); };
            for (int trial = 0; trial < 7; ++trial) {
                if (trial % 2 == 0) {
                    if (!measure(n, shuffled, trial, 0, "aos", passes, expected, aos) ||
                        !measure(n, shuffled, trial, 1, "soa", passes, expected, soa)) return 2;
                } else {
                    if (!measure(n, shuffled, trial, 0, "soa", passes, expected, soa) ||
                        !measure(n, shuffled, trial, 1, "aos", passes, expected, aos)) return 2;
                }
            }
        }
    }
}
```

从仓库根目录执行，执行器提取全部实验文件并保存完整命令。它不覆盖已有结果文件：

```sh
python3 c++/rework/verify_g6.py \
  --compiler /usr/bin/clang++ \
  --compiler /opt/homebrew/opt/llvm/bin/clang++ \
  --nm /opt/homebrew/opt/llvm/bin/llvm-nm \
  --output /tmp/g6-rework-results-new.json
```

计时采用 `-O3`，不使用 fast-math、LTO 或 sanitizer。正确性另在 O0/O2 下执行，sanitizer 又是独立配置；不把它们的耗时拿来作性能比较。输入固定且可重建，只代表所选分布，不声称是一套代表所有业务的随机样本。

### 5.2 先检查测量有效，再阅读数值

这里要区分 measurement validity 与 optimization success。前者检查仪器确实测到了所声明的工作，后者才问改变是否改善了目标指标。有效实验完全可以得到 SoA 不占优的结果；无效实验即使显示十倍加速，也不支持优化结论。这个区别决定了为什么执行器应以输入、完整结果和记录矩阵作硬判据，而不以作者期望的性能排名作 PASS 条件。

第一层检查记录是否完整：规模、顺序、试次、layout 和 passes 是否组成预期矩阵，每一条 checksum 是否正确，进程是否正常退出，有没有超时或诊断。计时为零说明当前仪器没有得到可用区间，不是无限快。通过这些检查，只获得一组可以分析的观察；没有任何 “SoA/AoS 小于某比值才 PASS” 的条件。

第二层把每次区间换算成单次扫描时间，再保留每进程原值、最小值、中位数、最大值和四分位范围。七个连续试次共享机器状态，三个进程也共享同一台主机；这些不是独立同分布的业务请求，不能套一个漂亮置信区间就宣称总体已知。异常高值可能来自调度、温度或后台活动，不能不留原值便删除；最低值也只接近某种较少干扰的状态，不代表用户通常感受。

本章没有绑定 CPU 核、锁定频率、隔离后台程序或证明热稳态。交替次序和重复进程减少部分顺序偏差，却不能排除全部系统噪声。两套 Clang 的结果要分别解读，不把它们混成一个“机器性能平均值”。[实际观察与执行限制](g06-verification.md)给出本机结果；更换工具链或主机后重新测量，而不是以旧数字回归。

### 5.3 首次运行怎样改变解释

本批初次执行时，大规模打乱输入的 SoA 并没有更快。进一步查看两套编译器的输出，AoS 主循环把四条记录交错处理，以 `csel` 选择数值或零，并使用多个部分和；SoA 则保留了按有效标记跳过载入的条件跳转。循环备注没有报告 SIMD 向量化，因此不能把 AoS 的交错处理称为“使用了四路 SIMD”。完整汇编和备注随本批证据保存。

这个发现没有证明差值全部来自分支预测，却足以否定“只比较热字段字节数，就能预测速度”的解释。AoS 与 SoA 除了布局，也带来不同的索引表达式、字段表示（bool 与 unsigned char）及生成代码；我们测的是这两个具体实现，不是固定机器指令后只重新排列字节的理想实验。有效标记的 0/1 合同由生成器与表示检查保证，但编译器在独立内核中能利用的信息并不完全相同。

此时不为得到预定排名而悄悄重写 SoA 内核。若以后需要检验“保持表示不变、仅改变条件求值方式”的假设，应另设明确变体，再检查是否仍完整保留语义。本批先保留相反观察，让模型接受证据约束。

## 6 从观察走向可反驳的解释

假设大规模 SoA 更快。一个解释是热字段地址跨度较小，另一个是两种内核生成的向量代码不同，第三个是条件路径的处理不同。这些解释可能同时成立。下一步应选择最能区分它们的证据，例如核对汇编中的载入和归约，或在支持的平台采集 cache／branch 事件；不应该先把较快结果写成“缓存命中率提高了多少”。

若增加 CPU 采样，采样集中在扫描函数只能说明时间主要落在该范围，不会自动区分等待内存与算术指令。若增加硬件计数器，还要说明事件定义、计数范围、是否复用计数器、是否含内核活动及 CPU 型号；一个被称为 cache-miss 的事件不必等同于每次 DRAM 读取。剖析提供定位证据，因果仍需要受控变化和模型解释。

另一种结果也很有价值：两种表示相近，甚至 AoS 更快。此时应检查当前工作集是否足够小、转换收益是否不在被测路径中、列访问数量与生成指令是否抵消了密度优势，而不是立即加大填充或换数据直到“证明”预定结论。一个能够否定优化假设的实验，比一张永远支持作者偏好的排行榜更适合长期使用。

完整优化闭环因此是：确认正确性合同，定位端到端成本，提出带条件的机制假设，改变一个主要因素，复查生成物和测量，再检查完整路径及资源预算。G6 已建立局部表示与分配的仪器；真实项目的流量分布、CPU profile、硬件计数器、峰值内存和尾延迟仍需按项目补证。本批没有运行它们。

## 7 迁移题

1. clear 后 size 为零但内存没有归还，是否说明 RAII 失效或泄漏？计数器该检查哪一层？
2. 为避免分配，提前 reserve 到历史最大值。为什么这既可能降低延迟，也可能使产品变差？
3. 一个使用局部 arena 的 vector 已经 clear，能否先 release arena，再继续 push_back？返回这个 vector 能否延长资源生命？
4. PMR 观察显示请求从 16 次降到 1 次，可以宣传“快了 16 倍”吗？
5. 基准中 SoA 快 30%，业务扫描只占总耗时 10%。为什么不能预测业务也快 30%？
6. 某次编译备注说循环已向量化，计时却变慢。应保留哪项结果，下一步如何调查？

## 8 参考推理

1. 不一定。clear 结束元素，但容器可以保留容量，分配器也可以保留已交还的块。先查对象析构、容器的资源配对、资源保留量，再看进程／系统指标。每层的“仍占用”有不同含义；只有确认责任应已结束而未结束，才进一步讨论泄漏。
2. 预留足够容量可以把分配移出高频路径，但长期保留偶发峰值可能放大总内存、挤压其他工作集，并使多工作区场景不可扩展。需要常态规模、峰值频率、可接受延迟与回收时机，不能只看分配次数。
3. 不可据此认为安全。clear 后 vector 仍保留指向容量的关系，release 会使后续复用失去存储前提。先结束依赖资源的容器，再回收 arena；移动／返回只移动容器，不延长局部资源及缓冲区生命。若要跨阶段交接，必须重新设计所有权和存储有效期。
4. 不能。请求计数既不包含全部耗时，也不保证每次请求同样昂贵；初始化、扫描、缓存和系统噪声仍存在。该实验支持请求复用的机制命题，性能需要独立计时，产品收益还需要端到端测量。
5. 即使把“快 30%”精确定义为局部耗时减少 30%，总耗时也只从 1 变成 0.9+0.1×0.7=0.97，未计转换等新增开销。局部倍率、局部时间减少比例与总体收益不能混用；还要检查内存、延迟分布及维护成本。
6. 两项都保留。编译备注描述生成选择，计时描述该工作负载的执行观察，它们不矛盾。检查尾部处理、数据重排、循环规模、指令和寄存器压力，复查原始测量与噪声，再决定是否需要更定向的 profile。不能因为向量化“应该更快”就抛弃相反观察。

## 9 本章结束时应该能解释什么

G6 把“成本”拆成了具体关系：表示决定地址序列，地址序列与依赖决定可利用的局部性和并行机会；分配策略决定资源请求及回收周期；编译配置决定所测生成物；测量合同决定结果能支持多大的结论。它没有为每种容器给出速度排名。

G7 将从多个执行者共同访问状态开始。并发能增加可用计算资源，也会引入同步、通信、退出和生命周期问题；不应把当前单线程曲线简单乘以核心数。G6 的 source／工具／计时身份与未验证范围见[验证说明](g06-verification.md)，本批不启动 G7、不构建 PDF。
