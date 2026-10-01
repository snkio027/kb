# G6 布局与访问成本

G5 已经让同一条读数规则适用于不同输入类型。现在考虑一个更具体的问题：系统不断收到带编号、数值和有效标记的读数，分析阶段反复计算有效读数之和。两份实现得到同一个答案，都只扫描一次，时间复杂度也都是 O(N)。为什么它们仍可能有明显的耗时差异？

复杂度描述输入增长时工作量的变化趋势，没有规定一次访问怎样落到机器上。字段之间的距离、访问次序、地址依赖以及编译器生成的指令，会改变相同算法需要搬运多少数据、能够重叠多少工作。本单元从读数的物理表示出发，建立解释这些差异的模型；[下一单元](g06-allocation-and-measurement.md)再把分配、测量与证据连接起来。对象是否存在、借用是否有效、访问类型是否合法，仍以前面 G1～G4 的合同为前提，不能用性能结果替代。

## 1 从一条读数到一批读数

### 1.1 对象大小不是字段大小之和

延续 G4 的 Reading：编号用于回查，数值参与计算，有效标记决定是否计入总和。首先暂不优化它，只观察布局。

**完整实验 G6-L1 · `layout.cpp` · 布局观察，不固定大小或偏移**

```cpp
#include <cstddef>
#include <iostream>
#include <type_traits>

struct Reading {
    int id;
    int value;
    bool valid;
};

static_assert(std::is_standard_layout_v<Reading>);

int main() {
    Reading batch[2]{};
    if (sizeof(batch) != 2 * sizeof(Reading)) return 1;
    std::cout << "{\"size\":" << sizeof(Reading)
              << ",\"alignment\":" << alignof(Reading)
              << ",\"id_offset\":" << offsetof(Reading, id)
              << ",\"value_offset\":" << offsetof(Reading, value)
              << ",\"valid_offset\":" << offsetof(Reading, valid)
              << ",\"int_size\":" << sizeof(int)
              << ",\"bool_size\":" << sizeof(bool) << "}\n";
}
```

`sizeof(T)` 给出 T 对象占用的字节数；`alignof(T)` 给出对该类型对象的对齐要求。对齐约束对象可以放在哪里，大小描述它占据多少存储，两者不是同一量。实现可能在成员之间插入填充，也可能在最后一个成员之后留下尾部填充，使数组中的后续元素同样满足对齐。数组元素连续排列，因此下一条 Reading 的起点相隔 `sizeof(Reading)`，而不是相隔三个成员大小之和。这里没有位域、继承或虚函数，且先确认 standard-layout，才用 `offsetof` 观察成员位置。[N4950：sizeof](https://timsong-cpp.github.io/cppwp/n4950/expr.sizeof)、[对齐](https://timsong-cpp.github.io/cppwp/n4950/basic.align)

常见实现可能给出 12 字节的 Reading，但实验没有把 12 写成语言规则。更重要的是如何使用这个数字：如果只读取 value 和 valid，编号及填充不参与答案，却占据对象数组的地址跨度。修改成员顺序有时能减少填充，但这个具体类型未必因此变小；必须重新观察，不能把“较宽字段放前面”当作普遍最优算法。布局变化也可能涉及持久化格式、外部接口或 ABI，不能仅因本地变小就任意修改公开类型。

### 1.2 连续对象与连续字段

结构数组（array of structures，AoS）把完整 Reading 连续存放。它适合按记录操作：查到一个编号后，附近就是该记录的其余字段。数组结构（structure of arrays，SoA）则把每类字段放在自己的连续序列中。分析阶段只读 value 与 valid 时，不必沿着编号字段跨步前进。

这两种表示的区别是“哪些数据相邻”，不是“一个使用连续内存、另一个不连续”。AoS 的对象连续，SoA 的各列连续；SoA 的多列彼此并不保证相邻。两者也都可能使用动态分配。以下三个文件定义同一任务的两种表示，以及各自的扫描内核。

**完整实验 G6-L2 的共享定义 · `readings.hpp` · 单线程、非负数值、等长列**

```cpp
#pragma once
#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <utility>
#include <vector>

static_assert(std::numeric_limits<int>::max() >= 1'048'575);

struct Reading {
    int id;
    int value;
    bool valid;
    bool operator==(const Reading&) const = default;
};

struct Columns {
    std::vector<int> ids;
    std::vector<int> values;
    std::vector<unsigned char> valid;
};

inline Columns to_columns(std::span<const Reading> input) {
    Columns columns;
    columns.ids.reserve(input.size());
    columns.values.reserve(input.size());
    columns.valid.reserve(input.size());
    for (const auto& reading : input) {
        columns.ids.push_back(reading.id);
        columns.values.push_back(reading.value);
        columns.valid.push_back(reading.valid);
    }
    return columns;
}

inline bool represents(std::span<const Reading> input, const Columns& c) {
    if (c.ids.size() != input.size() || c.values.size() != input.size() ||
        c.valid.size() != input.size()) return false;
    for (std::size_t i = 0; i < input.size(); ++i) {
        if (c.ids[i] != input[i].id || c.values[i] != input[i].value ||
            c.valid[i] != static_cast<unsigned char>(input[i].valid)) return false;
    }
    return true;
}

// 本章生成器的合同：n <= 1'048'576；生成不依赖随机库实现。
inline std::vector<Reading> make_readings(std::size_t n, bool shuffled) {
    std::vector<Reading> result;
    result.reserve(n);
    for (std::size_t i = 0; i < n; ++i) {
        result.push_back({static_cast<int>(i), static_cast<int>(i % 1024),
                          i < n / 2});
    }
    if (shuffled) {
        std::uint32_t state = 0x13579bdfU;
        for (std::size_t i = n; i > 1; --i) {
            state = state * 1664525U + 1013904223U;
            const auto j = static_cast<std::size_t>(state) % i;
            std::swap(result[i - 1], result[j]);
        }
    }
    return result;
}

std::uint64_t sum_aos(std::span<const Reading> input);
// 前置条件：values 与 valid 等长；value 非负；valid 仅含 0 或 1。
std::uint64_t sum_soa(std::span<const int> values,
                      std::span<const unsigned char> valid);
```

**完整实验 G6-L2 的扫描内核 · `scan.cpp` · 同一组值，两个地址序列**

```cpp
#include "readings.hpp"

std::uint64_t sum_aos(std::span<const Reading> input) {
    std::uint64_t total = 0;
    for (const auto& reading : input) {
        if (reading.valid) total += static_cast<std::uint64_t>(reading.value);
    }
    return total;
}

std::uint64_t sum_soa(std::span<const int> values,
                      std::span<const unsigned char> valid) {
    std::uint64_t total = 0;
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (valid[i]) total += static_cast<std::uint64_t>(values[i]);
    }
    return total;
}
```

**完整实验 G6-L2 的判据 · `scan-contract.cpp` · 全值对应先于求和结果**

```cpp
#include "readings.hpp"
#include <iostream>

int main() {
    std::vector<std::vector<Reading>> cases{
        {}, {{7, 17, true}}, {{9, 23, false}},
        {{1, 3, true}, {2, 5, false}, {3, 11, true}}
    };
    for (std::size_t n : {2U, 17U, 4096U}) {
        cases.push_back(make_readings(n, false));
        cases.push_back(make_readings(n, true));
    }
    for (const auto& input : cases) {
        const auto c = to_columns(input);
        if (!represents(input, c)) return 2;
        std::uint64_t expected = 0;
        for (const auto& r : input) {
            if (r.valid) expected += static_cast<std::uint64_t>(r.value);
        }
        if (sum_aos(input) != expected) return 1;
        if (sum_soa(c.values, c.valid) != expected) return 3;
    }
    auto malformed = to_columns(cases.back());
    malformed.ids.pop_back();
    if (represents(cases.back(), malformed)) return 4;
    // 不把非法范围交给 sum_soa；这里检查的是边界前的表示验证。
    std::cout << "complete records and both scans agree\n";
}
```

只比较求和结果不足以证明转换保真。例如转换时丢掉编号，结果仍可能完全相同。`represents` 先检查三个范围长度，再逐记录比较所有字段，避免用“更快的错误表示”参加计时；单元素非零有效读数则能揭露遗漏末元素的扫描。执行器另外注入两种错误，检验这些判据确实拒绝它们。生成器的规模上限与 int 范围断言共同保证编号转换可表示；本组实验还要求实现提供所用的精确宽度整数类型，不把本机类型宽度宣称为所有 C++ 实现的保证。

Columns 是教学用的透明结构，不是对任意修改都安全的生产组件。独立修改一列会破坏关系；将它作为公开 API 时，需要封装更新、限制修改阶段，或共同提交所有列。`to_columns` 在局部对象中完成构造，异常时不会返回半成品，但这不能替任意后续列操作提供保证。G4 的[索引一致性](g04-lookup-and-indexes.md)解释了同类关系不变量。

## 2 访问为何会搬运不需要的字段

### 2.1 缓存行、局部性与工作集

处理器通常不为每次 C++ 字段读取都向主存单独请求那几个字节。数据缓存以缓存行（cache line）为常见的填充与管理粒度，邻近地址的数据可能随同进入缓存。空间局部性（spatial locality）表示相近地址在相近时间内被访问；时间局部性（temporal locality）表示同一数据在较短间隔后再次使用。前者让一次搬运服务于后续相邻访问，后者让已搬入的数据得到复用。

这里的“相近”必须放在具体层级和访问窗口中理解。工作集（working set）描述在给定时间窗口或计算阶段内实际参与访问的数据集合，其覆盖的内存足迹反映该范围内的活跃访问规模。它不等于进程已分配内存的总和，也不要求其中每个字节都被重复访问；是否存在时间复用，是进一步的访问模式属性。经典工作集模型按时间窗口统计访问过的页；本章将这一思路用于数据、缓存行或页时，同样需要说明观察窗口与粒度。[Denning：工作集模型](https://denninginstitute.com/pjd/PUBS/WSModel_1968.pdf)

一个持有数 GB 历史数据的进程，当前可能只在几 KB 状态上计算；一次顺序扫描大数组，即使每条缓存行只读一次、只写一个累加器，整个扫描阶段的访问足迹也不能说成一个整数。这不意味着所有扫描过的数据必须同时驻留在缓存中，更不意味着它们都有复用价值。对当前求和，活跃字段是 value 和 valid，而 AoS 让这些字段分布在完整 Reading 的地址跨度内。

若对象步长为 S、N 条记录全部经过扫描，AoS 覆盖的对象存储规模是 N×S；SoA 两列的逻辑载荷则为 N×`sizeof(int)` 加 N×`sizeof(unsigned char)`。这能提出“热字段更紧密”的假设，却还不是总线流量的测量。编译器是否读取无效记录的 value、访问是否命中缓存、预取带来多少额外搬运，都会改变实际流量。不能把逻辑字节数除以时间，就命名为“实测 DRAM 带宽”。[Arm：缓存层级与局部性](https://learn.arm.com/learning-paths/servers-and-cloud-computing/memory-subsystem/cache-hierarchy/)

### 2.2 容量并不是唯一限制

L1、L2 及更外层缓存通常在容量、访问成本和共享范围上有所取舍，具体层数、容量和延迟由机器决定。把数组大小与某级缓存标称容量相比较，只能得到粗略线索。缓存还要容纳其他数据和指令；在组相联结构中，地址映射及有限关联度也会使尚未用满总容量的缓存发生冲突。第一次访问、容量不足、映射冲突可以造成不同的未命中，不能由一条耗时曲线唯一识别。

顺序地址容易让硬件预取器提前发出请求；这有助于隐藏等待，但没有把数据变成免费。过早或无用的预取可能占用带宽及缓存空间。把指针链换成连续数组，往往同时改变空间密度、地址可预测性和请求独立性，所以即使数组更快，也不该把全部收益归给其中一个词。

一次观测若要进一步声称“瓶颈在缓存未命中”，需要与目标 CPU 匹配的计数器或其他独立证据，并排除指令、分支、缺页及调度等解释。本章计时不采集这些计数器，因此只将其作为待检验的机制假设。测量结果不会反向创造机器规格。

## 3 等待时间与完成速率为什么不同

延迟（latency）是一次操作从开始到结果可用所需的时间；吞吐量（throughput）是在给定时间内完成多少操作；带宽（bandwidth）则通常描述每单位时间传送的数据量。单次读取延迟较高，并不意味着连续扫描只能每隔这么久读取一个元素：只要后续请求的地址已知，处理器可能同时等待多个请求。

内存级并行性（memory-level parallelism，MLP）描述这种独立内存请求的重叠机会。若只允许一条“读取节点→得到下一地址→再次读取”的依赖链，下一步地址在前一步完成前尚不可用，增加外部带宽也未必能提升它的速度。数组下标则能提前算出后续地址，较容易产生重叠。乱序执行提供利用独立性的机会，并不消除真正的数据依赖。[Arm：依赖式 pointer chase](https://learn.arm.com/learning-paths/servers-and-cloud-computing/memory-subsystem/pointer-chase-latency/)

可以用一个受限模型理解上限：假设每个请求搬运 L 字节、平均等待 t 秒、最多同时有 M 个有效请求，那么仅从在途请求容量估算，完成速率不可能无限超过 M/t，请求流量约受 M×L/t 限制；此外还受各层实际带宽、端口、依赖和指令发射能力约束。这不是用于预测某颗 CPU 的精确公式，而是解释为什么“延迟高”“带宽满”“独立请求不足”需要不同的优化。

当前求和还有累加器依赖。编译器在允许保持结果语义时，可能用多个部分和或向量归约缩短依赖链。这里使用非负的小整数与足够宽的无符号累加器；给定规模下总和不会溢出。若换成浮点数，重新结合加法可能改变舍入结果，不能无条件复用同一优化论证。机器成本必须建立在运算合同之后。

计算受限（compute-bound）与内存受限（memory-bound）因此不是类型或算法的永久属性。相同扫描在小工作集上可能主要付出循环与指令成本，在更大规模上受到数据传输限制；指针链又可能等待依赖载入，而没有填满带宽。算术强度（arithmetic intensity）把计算工作量与某一层级需要传送的字节数联系起来：在同一计算范围内，若计算量为 W、该层级流量为 B，则 `I = W/B`。这里假定 W、B 均为正；工作量如何计数、流量对应哪个层级，都必须先说明。

令 P 为对应计算吞吐的上限、D 为该层级带宽的上限，执行时间为 T，则有 `W/T ≤ min(P, I×D)`，等价地，`T ≥ max(W/P, B/D)`。这是 **Roofline 风格的吞吐上界／时间下界模型**：计算上限与带宽上限共同限制可达到的吞吐；W 与 P 必须采用一致的工作量单位，B 与 D 必须对应同一存储层级。即使允许计算与传输完全重叠，真实执行仍可能受依赖关键路径、MLP、分支、端口及其他瓶颈限制，不能把这个下界当作精确耗时，也不能用浮点峰值直接估计本章整数扫描。[Williams 等：Roofline 模型](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/EECS-2008-134.pdf)

这套模型最重要的用途是排除不相干的方案：如果独立请求数不足，仅增加向量加法吞吐未必有效；如果已经受数据传输限制，减少必需流量可能比少一条整数指令有用。本章没有测到 B、P、D，不能用 CPU 宣传峰值和逻辑字段大小拼出“已证明的瓶颈”。

## 4 表示选择服务于哪个阶段

### 4.1 SoA 的收益伴随转换与维护成本

AoS 的优势是单条记录完整、更新关系直观；SoA 的优势是特定字段扫描紧凑，但多列关系与多次分配需要管理。按编号随机查一条记录的全部字段，与顺序汇总百万条记录的一个字段，是两个不同任务。一个表示没有义务在两者上同时最优。

假设转换耗时为 C，一次 AoS 扫描为 A，一次 SoA 扫描为 S，同一批只读数据扫描 q 次。在忽略其他差异的模型下，转换路线的成本为 C+qS，原路线为 qA。只有当 A>S 且 q(A−S)>C 时，这一项转换才有摊销收益。若每轮输入都变化，C 也许每轮都要付；若还保留原始 AoS，峰值存储、复制和失效风险也应计入。只对扫描计时，不能替整个流程回答是否值得转换。

按阶段保留不同表示是可行的设计：接收阶段用完整记录保持更新简单，分析阶段建立只读列快照。热／冷分离（hot/cold splitting）也遵循同一原则：让高频字段靠近，把低频但较大的说明或历史信息移到其他位置。它增加了一层关联及可能的间接访问，只有访问频率和生命周期支持这种划分时才值得。

分块的 AoSoA 将记录分成小块、块内按列保存，用来折中整列扫描与局部记录处理；块大小需要结合算法批次、向量化及实际硬件。本章不引入第三套内核，也不先拍定一个“最佳块长”。先能解释两种基本表示，才有依据增加布局参数。

### 4.2 C++ 对齐、缓存行与虚拟内存页

三种尺度容易被混在一起。语言对齐要求约束 T 对象的放置；缓存行属于缓存层级；虚拟内存页属于地址映射和保护。`alignof(Reading)` 没有告诉我们缓存行大小，也没有保证对象不跨页。普通连续 vector 保证虚拟地址上的元素连续，不承诺背后物理页连续。

转换后援缓冲区（translation lookaside buffer，TLB）缓存地址转换信息。TLB 未命中意味着所需转换没有在该缓存命中，可能需要页表遍历；缺页异常（page fault）则是地址转换／访问过程中需要操作系统介入的事件，二者不是同义词。一个程序可能在物理内存充足时仍有很多 TLB 未命中，也可能在第一次触及已预留区域时经历映射或物理页准备。仅计 malloc 的调用时间，可能漏掉后续首次写入的成本。

把每页只访问一个节点的链压紧，可能同时改善缓存和地址转换的局部性。反过来，大页涉及操作系统策略、内存利用率及部署环境，不是给容器加一个类型参数就能兑现的承诺。本章不申请大页，不测 TLB，也不把 Apple 平台的现象外推到所有 Arm 或 x86。[Linux 内核文档：缓存与 TLB 的不同职责](https://www.kernel.org/doc/html/v4.19/core-api/cachetlb.html)

## 5 分支与向量化怎样进入同一模型

### 5.1 相同有效比例，不一定相同预测难度

本任务的 `if (valid)` 不是装饰。若有效记录集中在前半段，结果序列有长连续区间；若将同一批完整记录打乱，有效比例与最终总和不变，但判断结果的顺序改变。分支预测试图在控制条件尚未完成时预测后续路径，预测失败可能使错误路径上的工作作废。有效率 50% 只描述数量，不能完整描述可预测性。

不过源码里有 if，不等于目标代码一定含有逐元素条件跳转。编译器可能生成条件选择、掩码或向量指令，也可能保留分支。把表达式改成乘以 0/1，可能只是手工模仿编译器已经完成的变换，还可能引入额外载入或计算。要讨论 branchless 的收益，先确认实际生成代码，并保持错误路径不能被额外求值等语义限制。

本章生成器打乱的是完整记录，因此保持同一批值与身份，但也改变了数值的访问顺序。顺序版与打乱版是两个工作负载，不是隔离分支预测机制的完美实验；即使耗时不同，也不能仅凭它量化“分支失败罚时”。

### 5.2 编译器需要合法性与成本两层判断

向量化（vectorization）把多个标量操作组织为 SIMD 等并行运算。规则地址、简单循环和可分析的数据依赖有利于编译器判断；但“能够合法转换”与“成本模型认为值得转换”是两个问题。AoS 也可能被向量化，SoA 也不保证被向量化。编译器还要考虑循环长度、尾部处理、目标指令、寄存器压力和数据重排。

本章使用 Clang 的循环向量化备注观察编译选择，并保留独立内核的汇编摘要。备注说明某次编译做了什么，不能证明指令在某次运行中占了多少时间；未向量化也不等于程序性能不合格。LLVM 官方将合法性检查、运行时检查和成本模型分别讨论，适合对照理解。[LLVM：Auto-Vectorization](https://llvm.org/docs/Vectorizers.html)

类型化访问的合法性继续由 [G1](g01-representation-and-typed-access.md)负责。不能通过违反别名规则“帮助”编译器，也不能把关闭某个优化选项当作修复语言错误。优化前必须先保持完整值、范围、生命周期与运算语义；优化后再测量，并解释新增前提。

## 6 从单线程布局走向共享数据的边界

空间靠近在单线程扫描中通常值得研究，但在多核更新时可能产生另一种成本：不同线程修改不同对象，若它们位于同一一致性粒度中，可能反复转移可写权限，这通常称为伪共享（false sharing）。它与多个线程更新同一个逻辑状态的真共享不同，也与 C++ 数据竞争不是同一个判断维度；访问可以满足语言同步要求，却仍付出很高的一致性通信成本。

因此“压得越紧越好”也不成立。按线程分区、减少共享更新、合并写入，可能比加 padding 更根本；过度填充则会增大扫描和地址转换负担。缓存行大小、共享拓扑与实际访问协议都要核实，不能把 `alignas(64)` 当作跨机器保证。本单元没有运行并发代码；下一章 G7 才建立同步、进展与退出协议，随后再讨论它们的机器成本。

## 7 迁移题

1. 某实现的 Reading 为 12 字节，分析只需要 5 字节字段。能否说 AoS 每条必然从 DRAM 读取 12 字节，而 SoA 必然读取 5 字节？
2. 链表遍历占用的带宽很低却很慢。为什么“带宽尚有余量”不足以排除内存瓶颈？
3. SoA 的扫描比 AoS 快，但一次转换后只扫描一次。还需要哪些量才能做产品决策？
4. 两批数据的有效比例都是 50%，一批成段出现、一批打乱。若第二批慢，能否直接算出分支预测失败代价？
5. vector 连续、对象也满足对齐，为何仍可能受到页映射或 TLB 的影响？
6. 用 SoA 得到正确总和，是否足以认定表示转换保真？如果增加多线程写入，布局审查还会新增什么问题？

## 8 参考推理

1. 不能。12 是对象步长，5 是本例活跃字段的逻辑载荷；两者都不是已测得的层级间流量。命中、预取、无效记录的值是否载入、缓存行边界都会影响实际搬运。可以用它们提出密度假设，再用合适证据检查，不能把静态字节算式冒充 DRAM 计数器。
2. 依赖链可能在前一次读完后才能知道下一地址，限制同时在途的请求。此时单次等待决定进度，带宽没有被充分利用是依赖造成的结果，不是“内存很空闲所以必定是计算瓶颈”。应区分等待延迟、可重叠请求数和传输上限。
3. 至少需要转换、分配、扫描次数和结果回写成本，并检查峰值存储、更新维护与源数据有效期。C+qS 与 qA 只能描述选定部分，还要放回完整请求路径。改变表示可以是阶段性策略，不必把整个产品永久改为列式。
4. 不能。源码分支可能被消除或向量化，打乱还改变了访问数据的顺序。先观察生成代码，再使用目标平台的分支事件、采样或受控实验区分解释。有效比例不是预测难度的充分描述，耗时差值也不是单一硬件机制的直接读数。
5. 连续是虚拟地址合同，对齐是语言的对象放置合同。访问仍要完成地址转换，首次触及、转换缓存容量及页映射都可能影响成本。TLB 未命中不等于缺页，也不等于物理内存不足。
6. 不能。丢失编号、交换等和值甚至丢掉无效记录，都可能不改变总和；必须检查全字段和所属关系。多线程还要检查独立对象的写入是否导致一致性通信、是否存在真共享，以及语言层的同步合同。这些成本与正确性问题分别举证，单线程计时不能证明它们。

## 9 继续阅读与证据边界

下一步进入[分配策略与性能测量](g06-allocation-and-measurement.md)。本单元的布局、表示和求和是可观察对象；缓存、MLP、TLB、分支与一致性是解释模型。模型并未因为同一程序得到一组耗时而逐一被实验识别。[G6 验证说明](g06-verification.md)分别记录源代码判据、布局观察、优化备注、计时和未测范围；精读接受与工具执行同样是不同状态。
