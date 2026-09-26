# G6 · 内存布局、机器成本与性能测量

Modern C++ Systems Engineering · [Editorial Profile v1.0](editorial-profile.md) 编辑状态：Professional Handbook Edition。PDF：NOT BUILT / NOT VALIDATED。

- **Version:** 1.1
- **Status:** Professional Handbook Edition · 待集中审核
- **Language Baseline:** C++23
- **Track:** Modern C++ Systems Track
- **Prerequisites:** G0 Native Toolchain & Machine Boundary, G1 Object Model, G2 RAII & Ownership, G3 Value Semantics, G5 Generic Programming
- **Scope:** Object Layout / Alignment / Padding / Cache / Locality / AoS / SoA / Allocation / Arena / Pool / PMR / Virtual Memory / TLB / Branch Prediction / Cache Coherence / False Sharing / Benchmarking / Profiling
- **Purpose:** 建立从 C++ object representation 一直追踪到 CPU、Cache、Virtual Memory、多核和性能证据的统一分析模型。

## 阅读入口

主线从对象布局（object layout）追到局部性（locality）、分配（allocation）、虚拟内存（virtual memory）、控制流和跨核协调，再用测量（measurement）与性能剖析（profiling）检验假设。数组结构布局（AoS，array of structures）与结构数组布局（SoA，structure of arrays）只是表示选择，不能预设赢家。先读第 1～9 节，再用实验和 Gate 检查推理；其余部分供回查。


### 章节目录

- [1. 阅读模型](#g6-section-1)
- [2. 对象布局](#g6-section-2)
- [3. 缓存与局部性](#g6-section-3)
- [4. 数据布局：AoS、SoA 与 AoSoA](#g6-section-4)
- [5. 分配、区域与内存资源](#g6-section-5)
- [6. 虚拟内存与地址翻译](#g6-section-6)
- [7. 分支预测与控制流](#g6-section-7)
- [8. 缓存一致性与伪共享](#g6-section-8)
- [9. 测量、剖析与证据](#g6-section-9)
- [10. 统一性能审查](#g6-section-10)
- [11. 跨语言回查](#g6-section-11)
- [12. 术语回查](#g6-section-12)
- [13. 实验与验证](#g6-section-13)
- [14. Final Gate](#g6-section-14)
- [15. Final Gate · 参考答案与常见误判](#g6-section-15)
- [16. 工程原则回查](#g6-section-16)
- [17. G1～G6 的统一系统模型](#g6-section-17)
- [18. 从机器观察转向语言并发模型](#g6-section-18)
- [19. 参考与验证入口](#g6-section-19)

<a id="g6-section-1"></a>

## 1. 阅读模型

<a id="g6-topic-0"></a>

### 1.1 文档定位

G6 不再主要学习“C++ 有哪些语法”。 它研究的是：**一个语义正确的 C++ 程序，最终怎样使用 CPU 和内存，以及这些选择为什么会快或慢。** 前面几个阶段分别解决：

```text
G1
Object 是否存在？
Lifetime 是否有效？
Access 是否合法？

        ↓

G2
谁拥有？
谁借用？
谁负责 cleanup？

        ↓

G3
Value 怎样 copy / move / return？
这些操作真实成本是什么？

        ↓

G5
哪些差异应该由 compiler 在 compile time specialization？

        ↓

G6
这些 object / value / abstraction
最终如何映射到 CPU、Cache 和 Memory？
```

因此 G6 的核心链路是：

```text
C++ Type
    ↓
Object Representation
    ↓
Storage Topology
    ↓
Cache Lines
    ↓
Virtual Pages / TLB
    ↓
Allocation Topology
    ↓
Control Flow
    ↓
Multi-core Coherence
    ↓
Measured Performance
```

<a id="g6-topic-1"></a>

### 1.2 G6 的统一性能模型

性能分析先确定指标，再分解成本来源。计算、数据搬运、访存等待、分配、地址翻译、控制流和跨核协调是审查维度，不是可以直接相加的同量纲耗时公式；它们会重叠执行并互相制约。 两个 O(N) 算法可能分别连续扫描和依赖式追指针。表示、访问模式、工作集（working set）、输入分布和线程拓扑共同决定机器行为。复杂度给出规模趋势，不能替代具体工作负载的观测；G6-M3 会在保持计算结果一致的条件下记录布局差异，而不规定哪一方必须更快。

<a id="g6-section-2"></a>

## 2. 对象布局

<a id="g6-topic-2"></a>

### 2.1 `sizeof(T)` 的准确含义

`sizeof(T)`

表示一个 `T` object representation 所占的 byte 数，并且必须允许：

`T values[N];`

中的相邻 objects 正确排列。 所以它并不等于：所有成员 `sizeof` 简单相加。 例如：

[机制片段 · 不承诺独立编译]

```cpp
struct Sample {
    std::uint8_t flags;
    std::uint32_t id;
    float value;
};
```

成员名义大小：

```text
1 + 4 + 4 = 9 bytes
```

但常见 ABI 下可能得到：

```text
offset 0   flags      1 byte
offset 1   padding    3 bytes
offset 4   id         4 bytes
offset 8   value      4 bytes
────────────────────────────
sizeof(Sample) = 12
```

具体数字属于 ABI / implementation，不是 C++ 标准固定值。

<a id="g6-topic-3"></a>

### 2.2 Alignment

`alignof(T)`

表示：`T` object 起始地址必须满足的 alignment requirement。 例如某平台：`alignof(uint32_t) = 4` 意味着一个正常 `uint32_t` object 的地址通常必须满足：`address % 4 == 0` Alignment 存在的原因可能包括：

CPU load/store requirements、ABI、atomic operations、SIMD/vector instructions、access efficiency。

重要的是：**能够进行 unaligned access，不等于 alignment 无意义。**

<a id="g6-topic-4"></a>

### 2.3 Internal Padding 与 Tail Padding

**Internal Padding**

成员之间为了使下一个 member 正确对齐而加入的 bytes。 例如：

[机制片段 · 不承诺独立编译]

```cpp
struct S {
    std::uint8_t a;
    std::uint32_t b;
};
```

可能：`[a][pad][pad][pad][ b b b b ]`

**Tail Padding**

最后一个 member 后面的 padding。 例如：

[机制片段 · 不承诺独立编译]

```cpp
struct S {
    std::uint32_t x;
    std::uint8_t y;
};
```

可能：`[x x x x][y][pad][pad][pad]` 这样：

`S values[2];`

中第二个 `S` 仍然从满足 `alignof(S)` 的地址开始。 因此：**Tail padding 的一个核心作用是保证 array stride 正确。**

<a id="g6-topic-5"></a>

### 2.4 Member Ordering

考虑：

[机制片段 · 不承诺独立编译]

```cpp
struct A {
    std::uint8_t a;
    std::uint64_t b;
    std::uint8_t c;
};

struct B {
    std::uint64_t b;
    std::uint8_t a;
    std::uint8_t c;
};
```

在常见 64-bit ABI 下，`A` 可能显著大于 `B`。 如果每个 object 差 8 bytes：

```text
10,000,000 objects
× 8 bytes
=
80 MB
```

因此 member ordering 会影响：

RAM footprint、cache density、page density、memory bandwidth、TLB reach。

但不能机械执行：“所有 struct 都从大字段排到小字段。” 因为 declaration order 同时决定：

construction order、destruction reverse order、ownership teardown dependency、semantic grouping、ABI/layout。

所以：**Member ordering 是架构设计，不是格式化规则。**

<a id="g6-topic-6"></a>

### 2.5 Inline Representation 与 Indirect Representation

**Inline**

`std::array<float, 1024>`

payload 就在 object 内部。 因此：

`sizeof(object) ≈ logical payload footprint`

**Indirect**

`std::vector<float>`

vector object 本身通常只是类似：

pointer、size、capacity。

而真正的大 payload 位于 dynamic allocation。 因此：

`sizeof(std::vector<float>)`

只能说明：vector wrapper 本身的 representation。 不能说明：它拥有的数据总 footprint。 同理：

unique_ptr、shared_ptr、string、vector、PImpl。

都必须分析完整 object graph，而不只是 `sizeof(wrapper)`。

<a id="g6-topic-7"></a>

### 2.6 Object Representation ≠ Logical Value

假设：

[机制片段 · 不承诺独立编译]

```cpp
struct S {
    std::uint8_t a;
    std::uint32_t b;
};
```

即使：

`x.a == y.a && x.b == y.b`

也不能普遍推出：

`std::memcmp(&x, &y, sizeof(S)) == 0`

适合作为 logical equality。 因为 object representation 可能包含：

padding、multiple valid representations、pointer representation、floating-point representation details。

所以：

`Logical Equality ≠ Byte-for-byte Object Representation Equality`

同样：`std::is_trivially_copyable_v<T>` 不等于 `T` 可以直接作为 portable wire format。 序列化还必须考虑：

endianness、padding、ABI、versioning、schema、type width。

<a id="g6-section-3"></a>

## 3. 缓存与局部性

<a id="g6-topic-8"></a>

### 3.1 Memory Hierarchy

简化模型：

```text
Registers
   ↓
L1 Cache
   ↓
L2 Cache
   ↓
LLC / L3
   ↓
DRAM
```

通常：

```text
closer to CPU
→ smaller
→ faster

farther from CPU
→ larger
→ slower
```

因此很多程序不是：CPU arithmetic 不够快。 而是：CPU 等不到数据。

<a id="g6-topic-9"></a>

### 3.2 Cache Line

缓存行（cache line）是硬件进行缓存填充及一致性管理的重要粒度；其具体大小和层级由处理器决定，C++ 不规定固定为 64 字节。相邻访问可能复用同一行，写入不同对象也可能争用同一一致性单元。 用 64 字节推演是一个显式假设，不是本机事实。实验记录操作系统可报告的缓存行和页大小；这些查询也不是完整的缓存拓扑测量。不能仅凭 `sizeof(T)` 和一个假定行宽，就断言实际 miss 数或 false sharing 已经发生。

<a id="g6-topic-10"></a>

### 3.3 Spatial Locality

短时间内访问地址彼此接近的数据。 例如：

[机制片段 · 不承诺独立编译]

```cpp
for (const auto& value : values) {
    process(value);
}
```

对于：

`std::vector<T>`

通常：

```text
[T][T][T][T][T]
→ → → → →
```

非常适合 spatial locality。

<a id="g6-topic-11"></a>

### 3.4 Temporal Locality

短时间内反复访问同一份数据。 例如：

[机制片段 · 不承诺独立编译]

```cpp
state.position += velocity;
use(state.position);
state.position += correction;
```

`state.position` 很可能仍位于：`register / cache` 因此后续访问更便宜。

<a id="g6-topic-12"></a>

### 3.5 Cache-line Utilization

假设：`cache line = 64 B` 而一个算法每条 line 只真正使用：`4 B` 则：

```text
useful ratio ≈ 6.25%
```

也就是说：代码只写了一个 4-byte load，不代表 memory subsystem 只付出了 4 bytes 的成本。 这成为 SoA / hot-cold split 的主要动机之一。

<a id="g6-topic-13"></a>

### 3.6 Pointer Chasing

Dense layout：`[T][T][T][T][T]` Pointerized layout：

```text
[p][p][p][p]
 │  │  │  │
 ▼  ▼  ▼  ▼
 T  T  T  T
```

后者可能引入：

extra pointer load、random heap locations、cache misses、dependent loads、poor hardware prefetch、more pages、larger TLB working set。

所以：

`std::vector<T>`

与：

`std::vector<std::unique_ptr<T>>`

即使遍历都是：`O(N)` 实际性能仍可能完全不同。

<a id="g6-topic-14"></a>

### 3.7 Dependent Memory Access

链表：

```text
Node0 → Node1 → Node2 → Node3
```

下一地址必须等：`Node0.next` 先从 memory 返回。 这意味着：

```text
load Node0
↓
wait
↓
discover Node1
↓
load Node1
↓
wait
```

多个 memory misses 很难充分并行。 所以 pointer chasing 的一个深层问题是：**Memory-Level Parallelism 较差。**

<a id="g6-topic-15"></a>

### 3.8 Hardware Prefetch

规则访问：

```text
X
X+64
X+128
X+192
```

硬件容易预测：很可能还会继续向后读。 于是提前请求下一些 cache lines。 完全随机访问：

0xA...、0xF...、0x21...。

则难得多。 因此：

contiguous、regular-strided。

访问模式通常更硬件友好。

<a id="g6-topic-16"></a>

### 3.9 Working Set

某个时间窗口内真正活跃的数据集合。 如果 working set 能较好驻留 cache：

```text
cache hits ↑
latency ↓
```

如果远大于 cache：

```text
replacement ↑
memory traffic ↑
```

因此：Object footprint 不仅影响 RAM，也决定能有多少 hot objects 同时留在 cache。

<a id="g6-topic-17"></a>

### 3.10 Cache Density

假设：`cache line = 64 B` 如果：`sizeof(T) = 8` 一条 line 大约可以容纳：`8 objects` 如果：`sizeof(T) = 32` 只能容纳：`2 objects` 因此 object size 会影响：每次 cache fill 能顺便带进多少 useful objects。

<a id="g6-topic-18"></a>

### 3.11 Latency 与 Bandwidth

**Latency**

等某个特定数据到达需要多久。 Random pointer chasing 容易 latency-bound。

**Bandwidth**

单位时间能够搬多少 bytes。 大型连续 scan 更容易 bandwidth-bound。 例如：

[机制片段 · 不承诺独立编译]

```cpp
for (float x : huge_values) {
    sum += x;
}
```

虽然会产生很多 cache misses，但：

sequential、predictable、prefetchable、parallel memory requests。

所以仍可能非常高效。 这说明：**Cache miss 本身不是性能 verdict。**

<a id="g6-topic-19"></a>

### 3.12 Arithmetic Intensity

粗略定义：

```text
Useful Computation
──────────────────
Bytes Moved
```

如果：`1 add / many bytes` 更可能 memory-bound。 如果：`many FLOPs / few bytes` 更可能 compute-bound。 因此优化前要问：

- memory-bound?
- compute-bound?
- latency-bound?
- branch-bound?

<a id="g6-section-4"></a>

## 4. 数据布局：AoS、SoA 与 AoSoA

<a id="g6-topic-20"></a>

### 4.1 AoS — Array of Structures

[机制片段 · 不承诺独立编译]

```cpp
struct SignalSample {
    std::uint64_t timestamp;
    std::uint32_t id;
    float value;
    std::uint8_t valid;
};

std::vector<SignalSample> samples;
```

内存：

[ts id value valid]、[ts id value valid]、[ts id value valid]。

优势：

complete entity contiguous、simple ownership、simple lifetime、simple invariants、natural API。

适合：每次处理一个完整 entity。

<a id="g6-topic-21"></a>

### 4.2 SoA — Structure of Arrays

- timestamps: [ts][ts][ts]
- ids:        [id][id][id]
- values:     [v ][v ][v ]
- valid:      [x ][x ][x ]

适合：批量扫描某几个字段。 例如只计算 values：`[value][value][value][value]` 每条 cache line 几乎都装当前 kernel 真正需要的数据。

<a id="g6-topic-22"></a>

### 4.3 SoA 的第一收益

不是首先：SIMD。 而是：**减少 Overfetch 和无用 data movement。** 之后才进一步改善：

vector loads、SIMD、masked processing、column compression。

<a id="g6-topic-23"></a>

### 4.4 SoA 的成本

SoA 将一个 logical row 拆成多个 arrays。 于是必须保持：

timestamps.size()、==、ids.size()、==、values.size()、==、valid.size()。

产生新的 structural invariant。 同时可能增加：

multiple allocations、coordinated reserve/growth、exception-safety complexity、API complexity、borrow invalidation complexity。

所以 SoA 是：用 representation complexity 换 performance opportunity。

<a id="g6-topic-24"></a>

### 4.5 AoSoA

- Block 0:
- x[N]
- y[N]
- z[N]
- Block 1:
- x[N]
- y[N]
- z[N]

它折中：

```text
SoA SIMD friendliness
+
bounded block locality
+
some entity neighborhood
```

常用于：

particles、physics、robotics kernels、HPC。

但实现复杂度高。 默认路线应该是：

```text
AoS
↓
measured field-wise bottleneck
↓
SoA
↓
clear block/SIMD need
↓
AoSoA
```

<a id="g6-topic-25"></a>

### 4.6 Hot / Cold Split

例如：

[机制片段 · 不承诺独立编译]

```cpp
struct Robot {
    Position position;     // hot
    Velocity velocity;     // hot

    std::string name;      // cold
    DebugInfo debug;       // cold
};
```

physics loop 只需要：

position、velocity。

则拆为：

RobotState、RobotMetadata。

可以同时降低：

cache working set、memory bandwidth、page working set、TLB pressure。

这往往比：省几 bytes padding 有价值得多。

<a id="g6-topic-26"></a>

### 4.7 Layout 的统一原则

```text
Frequently co-accessed data
→ colocate

Independently scanned data
→ separate

Independent high-frequency writers
→ separate cache lines / regions
```

这三条贯穿单线程和多线程 data layout。

<a id="g6-topic-27"></a>

### 4.8 Phase-specific Representation

系统不必只有一种 domain representation。 可以：

```text
Ingress
→ AoS

Compute
→ SoA

Storage
→ Columnar

External API
→ Row DTO
```

一次 representation transform：`O(N)` 如果后续：`大量重复处理` 完全可能值得。 因此：**Representation 可以服务某个 processing phase，而不是服务抽象上的“对象纯洁性”。**

<a id="g6-section-5"></a>

## 5. 分配、区域与内存资源

<a id="g6-topic-28"></a>

### 5.1 Allocation 与 Construction

`new T(args...)`

概念上：

`raw storage allocation + T construction`

而：

`delete p;`

：

`T destruction + storage deallocation`

必须永久分开：

Allocation、Construction、Destruction、Deallocation。

<a id="g6-topic-29"></a>

### 5.2 General Heap Allocation 的成本

可能包含：

allocator metadata、size classes、free-list operations、synchronization、cache misses、fragmentation handling、occasionally acquiring more pages。

但：普通 `new` 一般不意味着每次都直接进行 syscall。 Allocator 通常已经从 OS 获取较大的 memory regions。

<a id="g6-topic-30"></a>

### 5.3 Stack 为什么便宜？

通常的栈帧存储管理利用后进先出的调用结构，可以用栈指针调整批量取得和归还空间，省去一般堆分配器的任意释放搜索与同步。但 automatic storage duration 是语言概念，局部对象也可能被放入寄存器或完全消除。 “栈便宜”只讨论常见存储管理路径，不包含构造函数、巨大栈帧、触页或栈溢出成本。不能把复杂对象改成局部变量，就据此认定其内部动态分配或清理工作消失。

<a id="g6-topic-31"></a>

### 5.4 Per-item Allocation

例如：

`std::vector<std::unique_ptr<Detection>>`

大量 small values 时可能产生：

N allocations、N allocator metadata、N indirections、fragmentation、poor cache locality、more pages、larger TLB working set。

所以如果：

small、value-like、no polymorphism、no address-stability requirement。

通常优先：

`std::vector<Detection>`

<a id="g6-topic-32"></a>

### 5.5 Internal / External Fragmentation

**Internal Fragmentation**

请求：`24 B` allocator 给：`32 B slot` 内部没用掉的 8 B。

**External Fragmentation**

总 free space 足够，但：`散成多个小 region` 无法满足一块较大的 contiguous request。 Fragmentation 不只浪费 RAM，还可能恶化：

page usage、locality、TLB pressure。

<a id="g6-topic-33"></a>

### 5.6 Allocation Optimization Ladder

优先级：

```text
1. Avoid allocation
2. Inline storage
3. reserve + reuse
4. batch allocations
5. Arena
6. Pool
7. Custom allocator/resource
8. Measure again
```

这是非常重要的顺序。 不要：

```text
看到 new
→ 写 memory pool
```

<a id="g6-topic-34"></a>

### 5.7 `reserve + clear`

当容量足够时，`reserve` 加上反复填充与 `clear` 可以复用 vector 的元素存储，优先于引入自定义分配器。`clear` 销毁已有元素但保留容量，后续在容量内构造元素不需要重分配这块存储。 这个结论不意味着整个过程没有分配或成本：元素自身可能另行分配，析构和重新构造也必须执行。G6-M2 记录指定 PMR 资源收到的请求，并单独核对活对象数；它不代表全进程 allocator profile。

<a id="g6-topic-35"></a>

### 5.8 Arena / Region Allocation

核心：

```text
large region

[A][B][C][free........]
          ↑
        cursor
```

每次 allocation：

align cursor、return cursor、advance cursor。

最终：`reset / release whole region` 适合：

request lifetime、batch lifetime、parser pass、frame processing、compiler AST。

即：一批 objects 拥有近似共同 lifetime。

<a id="g6-topic-36"></a>

### 5.9 Arena 的真正来源

Arena 快不是因为“特殊内存”。 而是因为它限制：individual arbitrary deallocation。 因此不需要一般性的：

free-list search、coalescing、per-object reclaim。

再次体现：**Lifetime constraints 可以换来更简单、更可预测的 memory management。**

<a id="g6-topic-37"></a>

### 5.10 Arena 与 Object Lifetime

Arena reset 只是在处理：storage。 它不会自动正确销毁 placement-new 出来的：

string、vector、file wrapper、mutex。

等 non-trivial objects。 因此：

`Arena Storage Lifetime ≠ C++ Object Lifetime`

<a id="g6-topic-38"></a>

### 5.11 Pool

Pool 适合：

`many same/similar-size objects + individual arbitrary lifetimes`

结构：

```text
[used][free][used][free]
        ↑          ↑
        free list
```

allocate：`pop free slot` free：`push slot back`

<a id="g6-topic-39"></a>

### 5.12 Arena vs Pool

```text
Arena
→ lifetime grouped
→ bulk release

Pool
→ slots reused independently
→ arbitrary per-object lifetime
```

这是根本区别。

<a id="g6-topic-40"></a>

### 5.13 Stale Generation

Pool：

```text
slot 42
generation 7
→ Task A
```

释放再复用：

```text
slot 42
generation 8
→ Task B
```

旧 pointer：`same address` 但已经：

different object、different lifetime、different generation。

所以：**Stable address 不等于 stable logical identity。** Generational handle：

[机制片段 · 不承诺独立编译]

```cpp
struct Handle {
    std::uint32_t index;
    std::uint32_t generation;
};
```

可以检测 stale access。

<a id="g6-topic-41"></a>

### 5.14 `std::pmr`

核心 abstraction：

`std::pmr::memory_resource`

它把：`container/value behavior` 和：`runtime allocation strategy` 进行一定程度解耦。 例如：

`std::pmr::vector<T>`

可以配：

monotonic_buffer_resource、unsynchronized_pool_resource、synchronized_pool_resource、custom resource。

<a id="g6-topic-42"></a>

### 5.15 `monotonic_buffer_resource`

`std::pmr::monotonic_buffer_resource` 为一组生命周期相近的分配提供单调增长的存储。单独的 deallocate 不归还对应块；`release` 或资源销毁统一释放其管理的存储，但不会代替放在其中的对象执行析构。 因此顺序应是结束所有相关对象及借用，再释放资源。即使容器已 `clear`，它通常仍持有 capacity；这时释放资源后继续使用该容器仍是错误设计。内存资源必须活得比依赖它的容器久。PMR 抽象的是存储分配策略，不是 GC，也不自动提供线程安全。

<a id="g6-topic-43"></a>

### 5.16 Allocation Profile 要看什么？

至少：

allocation count、allocated bytes、size distribution、lifetime distribution、peak live bytes、thread of allocation、thread of free。

尤其：`millions of tiny allocations` 往往比少数大 allocation 更可疑。

<a id="g6-section-6"></a>

## 6. 虚拟内存与地址翻译

<a id="g6-topic-44"></a>

### 6.1 Pointer 通常是 Virtual Address

用户态：

`T* p;`

通常首先代表：virtual address。 不是直接的 DRAM physical address。 每个 process 有自己的：`Virtual Address Space`

<a id="g6-topic-45"></a>

### 6.2 Pages

Virtual memory 以 page 为主要映射粒度。 例如平台可能使用：

4 KiB、16 KiB、large pages、...。

这是 OS / hardware property。 Virtual pages：

VPage 100、VPage 101、VPage 102。

可以分别映射到：`不同 physical pages` 所以：virtual contiguous 不代表 physical contiguous。

<a id="g6-topic-46"></a>

### 6.3 MMU / Page Table

简化：

```text
Virtual Address
      ↓
MMU
      ↓
Page Table
      ↓
Physical Address
```

一个 virtual address 可以概念拆：

`Virtual Page Number + Page Offset`

映射改变 page number，offset 保持。

<a id="g6-topic-47"></a>

### 6.4 TLB

**Translation Lookaside Buffer**

缓存：

```text
Virtual Page
→
Physical Page
```

的 translation。 因此 memory access 同时涉及两套 locality：

`Address Translation Locality + Data Cache Locality`

<a id="g6-topic-48"></a>

### 6.5 TLB Miss 与 Page Fault

必须严格区分。

**TLB Miss**

```text
translation not in TLB
↓
page-table walk
↓
mapping found
↓
continue
```

page 可能完全正常 resident。

**Page Fault**

CPU 当前无法完成访问：`trap to kernel` 可能是：

first anonymous-page touch、copy-on-write、mapped file page、protection fault、illegal address。

因此：Page fault 不等于程序一定出错。

<a id="g6-topic-49"></a>

### 6.6 Allocation ≠ Physical Memory Immediately

可能发生：

```text
allocator returns virtual range
↓
not every page physically touched yet
↓
first access
↓
page fault / backing / zeroing
```

所以：`malloc/new 10 GB` 与：`touch 10 GB of actual pages` 不是同一件事。

<a id="g6-topic-50"></a>

### 6.7 First Touch

第一次真正访问 large memory：

page faults、page zeroing、mapping work。

可能产生 latency spike。 因此 latency-sensitive 系统有时会：

preallocate、pre-touch、reuse。

把成本从：`hot phase` 搬到：`initialization` 这叫：**Latency Placement** 而不是凭空消除工作。

<a id="g6-topic-51"></a>

### 6.8 Page Locality / TLB Reach

Dense storage：`many useful objects / page` 意味着一个 TLB entry 可以服务更多 object accesses。 Sparse pointer graph：`few useful bytes spread over many pages` 则可能：

```text
TLB working set ↑
page walks ↑
```

因此 object density 同时影响：

cache density、page density、TLB reach。

<a id="g6-topic-52"></a>

### 6.9 Huge Pages

更大 page：

```text
translations needed ↓
TLB reach ↑
```

但可能增加：

internal waste、mapping granularity、fault cost、memory management complexity。

所以只有：translation overhead 已被 profile 证明有意义 时才值得考虑。

<a id="g6-topic-53"></a>

### 6.10 `mmap`

核心不是：“读取文件的另一种 API”。 而是：把 virtual address range 映射到某种 backing object。 访问：

`mapped[i]`

看起来只是普通 pointer access，但可能隐藏：

TLB miss、page fault、filesystem、storage I/O。

所以：**Pointer syntax 不揭示 memory latency class。**

<a id="g6-section-7"></a>

## 7. 分支预测与控制流

<a id="g6-topic-54"></a>

### 7.1 Branch Prediction

CPU 遇到：

[机制片段 · 不承诺独立编译]

```cpp
if (condition) {
    foo();
} else {
    bar();
}
```

不能总停下来等 condition 完成。 因此：

```text
predict branch
↓
fetch predicted path
↓
execute speculatively
↓
verify later
```

<a id="g6-topic-55"></a>

### 7.2 Predictable Branch

例如：`99.9% true` 通常很容易预测。 因此：`if` 并不天然昂贵。 真正可能贵的是：**Branch Misprediction**

<a id="g6-topic-56"></a>

### 7.3 Misprediction

预测错误：

```text
wrong-path instructions
↓
discard/squash
↓
restart correct path
```

成本显著高于单纯 compare。 所以 branch 成本取决于：

data distribution、branch history、microarchitecture。

<a id="g6-topic-57"></a>

### 7.4 Branch Cost 是 Runtime-state-dependent

同样：

[机制片段 · 不承诺独立编译]

```cpp
if (valid) {
    process();
}
```

数据：`99.9% true` 和：`50/50 random` 性能可能完全不同。 因此：**Input distribution 是性能 specification 的一部分。**

<a id="g6-topic-58"></a>

### 7.5 Source Branchless ≠ Machine Branchless

`count += value >= threshold;`

源码没有 `if`，compiler 仍决定具体 lowering。 反过来：

[机制片段 · 不承诺独立编译]

```cpp
if (value >= threshold) {
    ++count;
}
```

也可能被编译成 branchless code。 所以：查看 optimized machine code，而不是从 C++ syntax 猜。

<a id="g6-topic-59"></a>

### 7.6 Branchless 的 Trade-off

Branchless：

```text
control uncertainty ↓
```

但可能：

```text
extra work ↑
extra loads ↑
dependency chain ↑
```

如果 branch 能跳过：

expensive computation、invalid operation、memory load、rare path。

且容易预测，branch 往往更好。

<a id="g6-topic-60"></a>

### 7.7 SIMD 与 Mask

当一条 vector instruction同时处理多个 lanes：

lane 0 true、lane 1 false、lane 2 true、...。

单一 scalar control-flow branch 很难表达。 因此 SIMD 常用：

mask、select、blend、masked operations。

这也是 SoA 更容易 vectorize 的一个原因。

<a id="g6-topic-61"></a>

### 7.8 Fast Path / Slow Path

高概率场景：

short、predictable、hot。

低概率异常：

large diagnostics、error handling、logging。

可以拆：

`fast path + cold slow path`

这既可能帮助：`branch predictability` 也可能改善：`instruction-cache working set`

<a id="g6-topic-62"></a>

### 7.9 `[[likely]]` / `[[unlikely]]`

它们主要是：compiler optimization hints。 不是：`runtime branch predictor command` 也不是 correctness guarantee。 应该来自：

real domain distribution、profile、strong invariant。

而不是凭感觉乱加。

<a id="g6-topic-63"></a>

### 7.10 Direct / Indirect Dispatch

Direct call：

`decode_msg_100();`

target compile-time known。 Function pointer：

`fn();`

target runtime known。 Virtual dispatch：

`obj.virtual_method();`

通常也是 indirect control flow。 Indirect dispatch 可能影响：

target prediction、inlining、interprocedural optimization。

但 target 稳定、每次 useful work 足够多时：成本完全可能很小。

<a id="g6-topic-64"></a>

### 7.11 Static Dispatch

Template specialization：

`process<Camera>();`

target 更容易在 compile time 决定。 优势：

direct call、inline、constant propagation。

代价：

more specializations、larger code、I-cache pressure、compile time。

所以 static dispatch 不是免费胜利。

<a id="g6-section-8"></a>

## 8. 缓存一致性与伪共享

<a id="g6-topic-65"></a>

### 8.1 Coherence

多核：

Core 0 Cache、↕、coherence、↕、Core 1 Cache。

当同一 memory region 被多个 cores 访问，hardware 必须保持 cache copies 的一致性。 重要粒度通常是：cache line / coherence block，而不是 C++ object。

<a id="g6-topic-66"></a>

### 8.2 False Sharing

[机制片段 · 不承诺独立编译]

```cpp
struct Counters {
    std::atomic<std::uint64_t> a;
    std::atomic<std::uint64_t> b;
};
```

Thread 0：`writes a` Thread 1：`writes b` 如果：

```text
a + b
```

位于同一 cache line，硬件仍会让 line ownership在 cores 之间反复转移。 这叫：**False Sharing** 即：

logically separate、but、physically shared coherence block。

<a id="g6-topic-67"></a>

### 8.3 True Sharing vs False Sharing

**True Sharing**

多个 threads 真正更新同一个：

`std::atomic<uint64_t> counter;`

共享不可避免。

**False Sharing**

多个 threads 更新不同 values，只因为物理 colocated 而产生 coherence contention。 因此：

```text
Race-free
≠
Contention-free
≠
Fast
```

<a id="g6-topic-68"></a>

### 8.4 `memory_order_relaxed` 不能解决 False Sharing

`relaxed` 控制的是：C++ memory-ordering contract。 但 atomic write 仍然必须获得：对对应 coherence line 的 writable ownership。 因此：

`weak ordering + terrible false sharing`

完全可能同时存在。

<a id="g6-topic-69"></a>

### 8.5 Shared Immutable Data

多个 cores 只读：`immutable Model` cache lines 可以保留共享副本。 因此：`Shared Immutable Data` 同时具有：

`simpler synchronization + friendly cache-coherence behavior`

这也是 immutable snapshot architecture 强大的原因。

<a id="g6-topic-70"></a>

### 8.6 优先减少 Shared Mutation

不要遇到 false sharing 就先 padding。 更强的优化顺序：

1. Remove sharing、2. Single writer、3. Per-thread / per-worker state、4. Batch aggregation、5. Cache-line isolation。

例如：

```text
shared atomic ++ per event
```

通常远差于：

```text
thread-local ++
↓
one aggregate update per batch
```

<a id="g6-topic-71"></a>

### 8.7 Parallel Partition

较好：

```text
Thread 0 → contiguous block A
Thread 1 → contiguous block B
```

较差：

```text
Thread 0 → even indexes
Thread 1 → odd indexes
```

因为 interleaved writes 很容易让每条 cache line被多个 cores同时修改。 因此：Parallel partition 应尽可能和 physical ownership region 对齐。

<a id="g6-topic-72"></a>

### 8.8 `alignas` 与 Interference Size

对齐与填充可以帮助分离频繁写入的状态，但增大 footprint 也可能破坏局部性。`std::hardware_destructive_interference_size` 是实现提供的干扰间距建议；可用性、值和目标配置必须实测，不能当作所有处理器的真实缓存行枚举。 若使用显式 `alignas` 值，要说明目标假设，并检查数组步长和实际地址关系。单凭两个字段的地址不同不能排除 false sharing；反过来，记录了对齐也不证明该工作负载一定更快。减少共享写、线程本地聚合和批量合并往往比无限加 padding 更重要。

<a id="g6-section-9"></a>

## 9. 测量、剖析与证据

<a id="g6-topic-73"></a>

### 9.1 性能首先要定义 Metric

可能是：

Latency、Throughput、p99、CPU utilization、Memory footprint、Allocation rate、Startup time、Energy。

“更快”不是完整 requirement。

<a id="g6-topic-74"></a>

### 9.2 Latency vs Throughput

Latency：一次 operation 多久完成。 Throughput：单位时间完成多少工作。 增加 batch size 可能：

```text
throughput ↑
latency ↑
memory ↑
```

所以必须知道优化目标。

<a id="g6-topic-75"></a>

### 9.3 Tail Latency

平均值可能隐藏极端慢请求。 因此系统常看：

p50、p90、p95、p99、p99.9、max。

例如：`p99 = 10 ms` 表示：大约 99% observations 不超过 10ms。 不是：最慢 1% 平均值是 10ms。

<a id="g6-topic-76"></a>

### 9.4 Benchmark / Profiler / Tracing

**Benchmark**

回答：**某个操作有多快？**

**Profiler**

回答：**CPU 时间花在哪里？**

**Tracing**

回答：**一条 request/job 的事件时间线是什么？** 例如：

```text
queued
↓
download
↓
decompress
↓
decode
↓
produce
```

它们解决的是不同问题。

<a id="g6-topic-77"></a>

### 9.5 End-to-end First

先看整个系统：

Download     20%、Decompress   40%、Decode        5%、Produce      10%、Waiting      25%。

如果 decode 只占 5%，即使加速很多：end-to-end 也不会提升很多。 这就是 Amdahl's Law 的工程直觉。

<a id="g6-topic-78"></a>

### 9.6 Microbenchmark

适合回答：

AoS vs SoA kernel、runtime dispatch vs static dispatch、allocator A vs allocator B。

但必须控制：

setup、allocation、RNG、logging、dead-code elimination、constant folding、cache state、input distribution。

最大的风险是：**非常精确地测错问题。**

<a id="g6-topic-79"></a>

### 9.7 Optimized Build

生产性能实验必须接近 production：`-O2 / -O3` 不能以：`-O0` 作为主要性能结论。 因为：

templates、span、iterators、small wrappers。

很多 abstraction 成本只有 optimizer 后才真正体现。

<a id="g6-topic-80"></a>

### 9.8 Dead-code Elimination

如果 benchmark result 从未被使用，compiler可能删掉整个 computation。 所以 benchmark 必须：让结果具有 observable relevance。 不要机械用 `volatile` 解决所有问题。 专业 benchmark framework 通常提供专门 optimization barriers。

<a id="g6-topic-81"></a>

### 9.9 Warm-up

第一次运行可能包括：

cold caches、page faults、branch-predictor cold state、dynamic-linking initialization、filesystem cache effects。

所以必须明确：测 cold-start，还是 steady-state？ 两个都是合法目标，但不能混。

<a id="g6-topic-82"></a>

### 9.10 Dataset Size

Benchmark 应覆盖：

small、medium、large。

使 working set：

fits small cache、fits larger cache、exceeds cache、streams from memory。

否则小 dataset 的结果可能完全不能代表 production。

<a id="g6-topic-83"></a>

### 9.11 Input Distribution

例如：

```text
branch:
99% true
vs
50/50 random

hash:
uniform
vs
collision-heavy

string:
SSO short
vs
heap-backed long
```

都会改变结果。 所以：Input distribution 是 benchmark specification 的一部分。

<a id="g6-topic-84"></a>

### 9.12 Hardware Counters

可以帮助观察：

cycles、instructions、branch misses、cache misses、TLB misses、loads/stores。

它们解释：为什么慢。 但最终是否优化成功仍然由：

end-to-end latency、throughput、tail、memory。

决定。

<a id="g6-topic-85"></a>

### 9.13 Profiler Before Assembly

正确顺序：

```text
profile
↓
find hotspot
↓
inspect hotspot assembly
```

Assembly 是：microscope。 Profiler 是：map。 不要研究一个只占 0.1% CPU 的函数三小时汇编。

<a id="g6-topic-86"></a>

### 9.14 Bottleneck Moves

优化前：

allocator 40%、decode    30%。

优化 allocator 后：

allocator 3%、decode   65%。

说明：新瓶颈浮现。 因此必须：

```text
profile
→ optimize
→ profile again
```

而不是一次 profile 后一路凭经验优化。

<a id="g6-topic-87"></a>

### 9.15 One Variable at a Time

如果同时：

```text
AoS → SoA
heap → arena
branch → branchless
runtime → template
```

最终快 30%，你不知道是谁贡献的。 所以尽可能：一次改变一个主要因素。 保留：

baseline、change、result、interpretation。

<a id="g6-topic-88"></a>

### 9.16 Performance Evidence Ladder

```text
Level 0
Intuition

    ↓

Level 1
Timing

    ↓

Level 2
Profiling / Tracing

    ↓

Level 3
Assembly / Hardware Counters

    ↓

Level 4
Production-like / Real System Metrics
```

越往下层越解释 mechanism，越往高层越证明真实系统价值。

<a id="g6-section-10"></a>

## 10. 统一性能审查

<a id="g6-topic-89"></a>

### 10.1 G6 九层 Review Protocol

任何性能敏感代码都可以按下面顺序检查。

**Layer 1 — Object Representation**

问：

- sizeof(T)?
- alignof(T)?
- padding?
- inline or indirect?

**Layer 2 — Access Pattern**

问：

- sequential?
- strided?
- random?
- pointer chasing?

**Layer 3 — Working Set**

问：

- 多少 bytes？
- 多少 cache lines？
- 多少 pages？
- 是否反复使用？

**Layer 4 — Data Layout**

问：

- 哪些 fields 是 hot？
- 哪些 fields 总一起访问？
- AoS / SoA？
- Hot/cold split？

**Layer 5 — Allocation**

问：

- 多少次 allocation？
- size distribution？
- lifetime distribution？
- 是否能 reuse？

**Layer 6 — Virtual Memory**

问：

- first touch？
- page faults？
- TLB working set？
- dense or sparse pages？

**Layer 7 — Control Flow**

问：

- branch distribution？
- predictable？
- indirect dispatch？
- branch 能跳过多少工作？

**Layer 8 — Multi-core**

问：

- 谁写什么？
- shared mutation？
- same cache line？
- single writer possible？
- batching possible？

**Layer 9 — Evidence**

问：

- 优化目标是什么？
- baseline 是什么？
- profile 证据是什么？
- 改完实际改善多少？

<a id="g6-topic-90"></a>

### 10.2 G6 Performance Smell Catalogue

**Smell 1 — Pointerized Small Values**

`std::vector<std::unique_ptr<SmallValue>>`

却没有：

polymorphism、stable-address、independent lifetime。

等真实需求。

**Smell 2 — Per-item Allocation**

[机制片段 · 不承诺独立编译]

```cpp
for (...) {
    std::make_unique<T>();
}
```

位于百万级 hot path。

**Smell 3 — Cold Data in Hot Struct**

```text
hot numeric state
+
strings
+
debug metadata
+
rare fields
```

全部混排。

**Smell 4 — Random Access on Huge Dataset**

却只因为 container 是 `vector` 就认为 cache-friendly。

**Smell 5 — Premature SoA**

没有 profile 就把简单 data model 拆成复杂 columns。

**Smell 6 — Branchless Cargo Cult**

把 highly predictable branch 改成每次都执行昂贵工作。

**Smell 7 — Shared Atomic per Event**

高频业务事件全部更新同一个 global atomic。

**Smell 8 — Per-thread Counters Adjacent**

逻辑独立，却共享 cache line。

**Smell 9 — Custom Pool Before Reuse**

连：

reserve、clear、reuse。

都没试，就自己维护 allocator。

**Smell 10 — Huge Template Specialization**

只为了消除一个 branch，生成大量近似函数，增加 I-cache/code-size压力。

**Smell 11 — Benchmarking `-O0`**

用 debug lowering 得出 production 性能结论。

**Smell 12 — Optimizing Without Baseline**

只有：“我感觉现在快了。” 没有可重复 benchmark / profile。

<a id="g6-section-11"></a>

## 11. 跨语言回查

<a id="g6-topic-91"></a>

### 11.1 C++

C++ 的性能优势来自：

explicit representation control、value semantics、contiguous standard containers、compile-time specialization、low-level memory access、RAII。

但相应要求工程师真正理解：

lifetime、aliasing、layout、allocator behavior、cache、memory model。

语言不会自动替你选择最优 representation。

<a id="g6-topic-92"></a>

### 11.2 Zig

Zig 更显式暴露：

allocator、array/slice distinction、layout、comptime。

使：

- where does allocation happen?
- who owns allocator?

通常更容易从 API 看出。 但：

cache、TLB、AoS/SoA、false sharing、memory bandwidth。

这些机器规律完全一样。

<a id="g6-topic-93"></a>

### 11.3 Rust

Rust 更强地静态约束：

ownership、borrows、thread safety traits。

但同样不能自动解决：

bad locality、too many allocations、Arc contention、false sharing、poor AoS layout。

因此：**Memory safety 与 memory performance 是不同维度。**

<a id="g6-topic-94"></a>

### 11.4 跨语言共同事实

无论：

```text
C++
Zig
Rust
```

都无法绕开：

cache-line granularity、page granularity、TLB、memory bandwidth、branch predictor、coherence、working set。

这些属于：machine architecture 而不是某种语言哲学。

<a id="g6-section-12"></a>

## 12. 术语回查

<a id="g6-topic-95"></a>

### 12.1 G6 核心术语表

| Term                     | 核心含义                                                 |
| ------------------------ | -------------------------------------------------------- |
| Object Representation    | 一个 object 在内存中的 byte-level representation         |
| Alignment                | object address 必须满足的边界要求                        |
| Padding                  | 为 alignment / layout 插入的非成员 value bytes           |
| Tail Padding             | object 末尾用于保证相邻 array element 正确对齐的 padding |
| Cache Line               | cache hierarchy 中的重要数据传输/coherence 粒度          |
| Spatial Locality         | 短时间访问相邻地址                                       |
| Temporal Locality        | 短时间重复访问同一数据                                   |
| Working Set              | 一段时间内活跃访问的数据集合                             |
| Cache Density            | 单个 cache line 能容纳多少 useful data/object            |
| Pointer Chasing          | 通过一个 pointer load 的结果决定下一次 memory address    |
| Memory-Level Parallelism | 同时存在多个独立 memory requests 的能力                  |
| Bandwidth-bound          | 性能主要由 bytes/sec 限制                                |
| Latency-bound            | 性能主要由单次 memory wait 限制                          |
| Arithmetic Intensity     | Useful computation / bytes moved                         |
| AoS                      | Array of Structures                                      |
| SoA                      | Structure of Arrays                                      |
| AoSoA                    | Array of Structures of Arrays                            |
| Hot/Cold Split           | 将高频和低频访问数据分离                                 |
| Arena                    | group-lifetime / region allocator                        |
| Pool                     | 固定或少数 slot size 的 reusable allocator               |
| Fragmentation            | allocation 布局导致的内部/外部空间浪费                   |
| PMR                      | Polymorphic Memory Resource                              |
| Virtual Address          | process 看到的虚拟地址                                   |
| Page                     | virtual-memory mapping 粒度                              |
| TLB                      | virtual→physical translation cache                       |
| TLB Miss                 | address translation cache miss                           |
| Page Fault               | 当前 memory access 需要 kernel/VM 处理                   |
| First Touch              | 首次真正访问某 virtual page                              |
| Branch Prediction        | CPU 预测 branch control flow                             |
| Misprediction            | branch outcome预测错误                                   |
| Speculative Execution    | 按预测路径提前执行                                       |
| Indirect Call            | target address 在 runtime 决定的 call                    |
| Cache Coherence          | 多核 caches 对 shared memory 保持一致的机制              |
| False Sharing            | 不同 logical data 因同 cache line 上的写而互相干扰       |
| True Sharing             | 多线程真正读写同一个 logical state                       |
| Benchmark                | 测量“多快”                                               |
| Profiling                | 定位“时间花在哪”                                         |
| Tracing                  | 描述“事件什么时候发生”                                   |
| Hardware Counter         | CPU 暴露的微架构事件计数                                 |
| Tail Latency             | 延迟分布高 percentile 部分                               |
| Amdahl's Law             | 局部优化受未优化部分比例限制的总体收益规律               |

<a id="g6-section-13"></a>

## 13. 实验与验证

本章完整实验以 Markdown 中的源文件为准；从仓库根目录运行下列命令。执行器提取文件到新建临时目录，完整命令和原始输出写入结果记录，不修改历史制品。

[命令 · 自动提取、编译及分项记录]

```sh
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

只有带 `h-lab/h-file` 标记的完整实验及隔离反例参加本章定向执行；其他机制片段不是已验证的完整实现。改变条件用于理解判据，若未单独运行，不计作新增证据。

### 13.1 G6-M1 · 对象布局不是语言常量

**命题、观察与边界。** 记录 sizeof、alignof、offsetof，并用静态断言检查数组大小与元素大小的关系；只对语言要求检查，绝不硬编码 Sample 必须为 12 字节。成员顺序的成本意义要结合实际目标及大量对象推理。

<!-- h-lab {"id":"G6-M1","mode":"observation"} -->

[完整实验 · G6-M1 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <type_traits>

struct Sample { std::uint8_t flags; std::uint32_t id; float value; };
struct Reordered { std::uint32_t id; float value; std::uint8_t flags; };
static_assert(std::is_standard_layout_v<Sample>);
static_assert(sizeof(Sample) % alignof(Sample) == 0);
int main() {
    Sample values[2]{};
    static_assert(sizeof(values) == 2 * sizeof(Sample));
    std::cout << "{\"size\":" << sizeof(Sample)
              << ",\"align\":" << alignof(Sample)
              << ",\"id_offset\":" << offsetof(Sample, id)
              << ",\"value_offset\":" << offsetof(Sample, value)
              << ",\"reordered_size\":" << sizeof(Reordered) << "}" << std::endl;
}
```

**运行与判据。** 上述统一命令中的 `G6-M1` 提取并处理本模块。程序的语义不变量须成立，JSON 数值作为 OBSERVED 保存；不要求固定布局或分配字节数。

### 13.2 G6-M2 · 资源请求与对象生命周期分别计数

**命题、观察与边界。** 指定 PMR 资源只统计本容器的请求；reserve 后在容量内重复构造与 clear，不增加该资源请求，但仍执行元素析构。不用这个局部计数冒充全进程分配 profile。

<!-- h-lab {"id":"G6-M2","mode":"observation"} -->

[完整实验 · G6-M2 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include <cstddef>
#include <iostream>
#include <memory_resource>
#include <vector>

struct Counting : std::pmr::memory_resource {
    std::size_t allocations = 0, deallocations = 0, bytes = 0;
    void* do_allocate(std::size_t n, std::size_t a) override {
        void* p = std::pmr::new_delete_resource()->allocate(n, a);
        ++allocations;
        bytes += n;
        return p;
    }
    void do_deallocate(void* p, std::size_t n, std::size_t a) override {
        ++deallocations;
        std::pmr::new_delete_resource()->deallocate(p, n, a);
    }
    bool do_is_equal(const std::pmr::memory_resource& r) const noexcept override {
        return this == &r;
    }
};
struct Item {
    static inline int live = 0;
    Item() { ++live; }
    Item(const Item&) { ++live; }
    Item(Item&&) noexcept { ++live; }
    ~Item() { --live; }
};
int main() {
    Counting resource;
    {
        std::pmr::vector<Item> items{&resource};
        items.reserve(64);
        const auto allocated = resource.allocations;
        const auto capacity = items.capacity();
        if (allocated == 0 || Item::live != 0) return 1;
        for (int round = 0; round < 20; ++round) {
            for (int n = 0; n < 64; ++n) items.emplace_back();
            if (Item::live != 64) return 2;
            items.clear();
            if (Item::live != 0 || items.capacity() != capacity ||
                resource.allocations != allocated) return 3;
        }
    }
    if (Item::live != 0 || resource.allocations != resource.deallocations) return 4;
    std::cout << "{\"allocations\":" << resource.allocations
              << ",\"deallocations\":" << resource.deallocations
              << ",\"requested_bytes\":" << resource.bytes << "}" << std::endl;
}
```

**运行与判据。** 上述统一命令中的 `G6-M2` 提取并处理本模块。程序的语义不变量须成立，JSON 数值作为 OBSERVED 保存；不要求固定布局或分配字节数。

### 13.3 G6-M3 · 同一求和工作负载的 AoS / SoA 观察

**命题、观察与边界。** 两种布局都读取 key，AoS 另带冷字段。三个规模、一次预热、七轮交替顺序，分配与初始化不计入计时；每次求和必须符合完整期望值。分离编译且不启用 LTO，避免调用者把重复工作折叠；生成汇编供回查。输出 elapsed_ns 只是当前进程观察，不能归因于某个缓存层或当作固定性能排名。

<!-- h-lab {"id":"G6-M3","mode":"benchmark"} -->

[完整实验 · G6-M3 · kernel.hpp]

<!-- h-file {"path":"kernel.hpp"} -->
```cpp
#pragma once
#include <cstddef>
#include <cstdint>
struct Record { std::uint64_t key; std::uint64_t cold[7]; };
std::uint64_t sum_aos(const Record*, std::size_t);
std::uint64_t sum_soa(const std::uint64_t*, std::size_t);
```

[完整实验 · G6-M3 · kernel.cpp]

<!-- h-file {"path":"kernel.cpp"} -->
```cpp
#include "kernel.hpp"
std::uint64_t sum_aos(const Record* p, std::size_t n) {
    std::uint64_t sum = 0;
    for (std::size_t i = 0; i < n; ++i) sum += p[i].key;
    return sum;
}
std::uint64_t sum_soa(const std::uint64_t* p, std::size_t n) {
    std::uint64_t sum = 0;
    for (std::size_t i = 0; i < n; ++i) sum += p[i];
    return sum;
}
```

[完整实验 · G6-M3 · main.cpp]

<!-- h-file {"path":"main.cpp"} -->
```cpp
#include "kernel.hpp"
#include <chrono>
#include <iostream>
#include <vector>

int main() {
    using Clock = std::chrono::steady_clock;
    for (std::size_t n : {1024U, 65536U, 1048576U}) {
        std::vector<Record> aos(n);
        std::vector<std::uint64_t> soa(n);
        std::uint64_t expected = 0;
        for (std::size_t i = 0; i < n; ++i) {
            aos[i].key = soa[i] = i % 251;
            expected += soa[i];
        }
        if (sum_aos(aos.data(), n) != expected ||
            sum_soa(soa.data(), n) != expected) return 1;
        for (int trial = 0; trial < 7; ++trial) {
            for (int position = 0; position < 2; ++position) {
                const bool use_aos = ((trial + position) % 2 == 0);
                const auto begin = Clock::now();
                const auto sum = use_aos ? sum_aos(aos.data(), n)
                                         : sum_soa(soa.data(), n);
                const auto end = Clock::now();
                if (sum != expected) return 2;
                const auto elapsed = std::chrono::duration_cast<
                    std::chrono::nanoseconds>(end - begin).count();
                std::cout << "{\"n\":" << n << ",\"trial\":" << trial
                          << ",\"layout\":\"" << (use_aos ? "aos" : "soa")
                          << "\",\"elapsed_ns\":" << elapsed
                          << ",\"checksum\":" << sum << "}" << std::endl;
            }
        }
    }
}
```

**运行与判据。** 上述统一命令中的 `G6-M3` 提取并处理本模块。以 -O3 分离编译两个 TU，不启用 LTO；记录 42 条测量及对应校验和，汇编输出属于代码生成观察。 **测量解释边界。** G6-M3 的计时含单次函数调用和计时器开销，小规模可能接近分辨率；每轮交替顺序并不消除系统噪声。这里记录的是进程墙钟间隔，不是 CPU 周期、实际 DRAM 流量、缓存/TLB miss 或端到端吞吐。CPU 采样 profile 和硬件计数器本批未采集；汇编不是其替代证据。后续真实优化应另以热点和输入分布为依据。

<a id="g6-section-14"></a>

## 14. Final Gate

<a id="g6-topic-96"></a>

### 14.1 Object Layout

应能解释：

1. 为什么 `sizeof(struct)` 不等于 members size sum？
2. Alignment 到底限制什么？
3. Internal padding 与 tail padding 有什么区别？
4. 为什么 member reordering 可以改变大数组 footprint？
5. 为什么 `memcmp` 通常不是普通 struct equality？
6. 为什么 `sizeof(vector<T>)` 不代表真实 payload footprint？

<a id="g6-topic-97"></a>

### 14.2 Cache

应能解释：

1. 什么是 cache line？
2. 什么是 spatial locality？
3. 什么是 temporal locality？
4. 什么叫 cache-line utilization？
5. 为什么 pointer chasing 不只是多一次 pointer dereference？
6. 为什么 sequential streaming 可以 cache miss 很多却仍然快？
7. latency-bound 与 bandwidth-bound 区别是什么？
8. working set 为什么重要？

<a id="g6-topic-98"></a>

### 14.3 Data Layout

应能解释：

1. AoS 和 SoA 物理布局区别是什么？
2. 哪种 workload 更适合 AoS？
3. 哪种 workload 更适合 SoA？
4. 为什么 SoA 往往更容易 SIMD？
5. SoA 会引入哪些新的 invariant？
6. AoSoA 在交换什么？
7. 为什么 hot/cold split 可能比 member padding 优化更重要？
8. 为什么 domain entity 不必等价于实际 C++ struct object？

<a id="g6-topic-99"></a>

### 14.4 Allocation

应能解释：

1. `new T` 至少包含哪两个阶段？
2. 为什么 `new` 不等于每次 syscall？
3. 为什么 per-item heap allocation 常常非常昂贵？
4. stack 为什么通常 storage management 很便宜？
5. Arena 的核心 lifetime constraint 是什么？
6. Pool 和 Arena 有什么不同？
7. 为什么 arena reset 不能自动替代 destructor？
8. 为什么 stable pool address 仍然会产生 stale pointer？
9. `reserve + clear` 为什么应该优先于 custom allocator？
10. PMR 真正抽象的是什么？

<a id="g6-topic-100"></a>

### 14.5 Virtual Memory

应能解释：

1. 用户态 pointer 为什么通常是 virtual address？
2. virtual contiguous 与 physical contiguous 有什么区别？
3. page table 做什么？
4. TLB 做什么？
5. TLB miss 与 page fault 有什么区别？
6. 为什么 allocation 与 physical backing 不是一回事？
7. first touch 为什么会造成 latency spike？
8. dense layout 为什么也改善 TLB locality？
9. huge pages 在优化什么？
10. `mmap` 为什么可能让普通 pointer access 隐含 I/O latency？

<a id="g6-topic-101"></a>

### 14.6 Control Flow

应能解释：

1. CPU 为什么需要 branch prediction？
2. branch misprediction 真正浪费什么？
3. 为什么 `if` 不是天然昂贵？
4. 为什么 50/50 random branch 往往难预测？
5. 为什么 source-level branchless 不代表 machine branchless？
6. branchless 为什么可能做更多无用工作？
7. function pointer 为什么是 indirect control flow？
8. 为什么 static dispatch 不一定最终更快？
9. instruction working set 与 code bloat 有什么关系？

<a id="g6-topic-102"></a>

### 14.7 Multi-core

应能解释：

1. cache coherence 解决什么？
2. 什么是 true sharing？
3. 什么是 false sharing？
4. 为什么不同 variables 仍然可能互相拖慢？
5. 为什么 `memory_order_relaxed` 不解决 false sharing？
6. 为什么 shared immutable data 非常友好？
7. 为什么 per-thread aggregation 往往比 global atomic 强？
8. 为什么 contiguous block partition 比 even/odd interleave 更适合并行写？
9. 为什么 race-free 不代表 fast？

<a id="g6-topic-103"></a>

### 14.8 Measurement

应能解释：

1. latency 和 throughput 有什么区别？
2. p99 表示什么？
3. benchmark / profiler / tracing 分别回答什么？
4. 为什么先做 end-to-end measurement？
5. 什么是 Amdahl's Law 的工程含义？
6. 为什么 microbenchmark 容易测错？
7. 为什么 benchmark 必须使用 optimized build？
8. 为什么 input distribution 是 benchmark specification？
9. 为什么 assembly 应该在 profiling 后看？
10. 为什么优化后必须再次 profile？
11. 为什么 hardware counter 不是最终 verdict？
12. 为什么性能收益必须和 complexity cost 一起评估？

<a id="g6-section-15"></a>

## 15. Final Gate · 参考答案与常见误判

### 15.1 Object Layout 与 Cache

Object Layout 1～6：成员对齐造成内部空隙，对象尾部填充保证数组中下一元素对齐，所以成员大小之和不等于 sizeof。对齐限制可用地址；调整成员次序可能减少 padding，重复到大数组时改变 footprint。普通 struct 的 padding 与表示差异使 memcmp 不能普遍替代逻辑相等；vector 本体通常只保存控制状态，元素存储另计。具体布局以目标 ABI 与 G6-M1 的输出为证，不能背固定字节数。

Cache 1～4：缓存行是传输/一致性的重要粒度；空间局部性复用邻近地址，时间局部性复用近期数据，行利用率描述一行中本次计算真正使用的部分。5～8：追指针把下一地址依赖于前次加载，限制并行访存和预取；连续流式读取可利用并发请求和带宽，即使 miss 很多也未必慢。latency-bound 等待依赖链，bandwidth-bound 受数据速率限制；工作集变化会改变驻留行为。单次耗时不能独立判定是哪种瓶颈。

### 15.2 Data Layout 与 Allocation

Data Layout 1～3：AoS 把同一对象字段放一起，适合逐对象使用多字段；SoA 把同字段排成连续数组，适合跨对象列扫描。4～6：SoA 的规律访问有利于向量化，但要维持长度、索引和更新一致性；AoSoA 以块为单位折中行列局部性、SIMD 宽度与尾部处理。7～8：热冷拆分避免每次搬运大段不用的数据，收益可能超过几个 padding 字节；领域实体可映射为多个存储区域，代价是显式维护关联不变量。G6-M3 只观察一种列扫描，不为全部工作负载选择 SoA。

Allocation 1～4：普通 new-expression 结合取得存储与初始化；通用分配器可从用户态缓存取块，并非每次系统调用。逐项分配增加管理、碎片和间接访问；常见栈帧利用后进先出结构批量管理存储，但对象构造并不免费。5～8：arena 依赖成组存活/释放，pool 依赖槽位复用；归还存储不替代析构，地址复用也可能让旧指针指向错误代次。9～10：reserve/reuse 用简单的容量合同减少请求；PMR 替换分配策略，不替代对象生命周期与资源依赖顺序。G6-M2 的计数只覆盖指定资源。

### 15.3 Virtual Memory 与 Control Flow

Virtual Memory 1～5：普通用户态地址由页表映射，虚拟连续不要求物理连续；TLB 缓存翻译，miss 可由页表遍历解决，page fault 才涉及当前访问需内核处理的异常，后者也不一定发生磁盘 I/O。6～10：分配虚拟区间、取得物理 backing 和实际触页不是同一事件；first touch 可能引入清零/分配延迟。紧凑布局减少活跃页，huge pages 用更大映射范围减少翻译压力，但有碎片等代价。mmap 文件可使首次普通读取触发缺页和 I/O。本批未采集 TLB/缺页硬件事件，不能从这些机制解释直接推出已经实测。

Control Flow 1～4：预测帮助流水线提前取指，预测错误会丢弃投机工作；稳定分布的 if 可预测，独立随机的 50/50 分支通常更困难，但实际相关性由数据决定。5～6：编译器可把源码 if 转为选择指令，也可反向生成跳转；无分支方案可能计算两侧和增加访存。7～9：函数指针目标运行时决定，静态分派可能利于优化，也可能增加代码体积与指令工作集。先看热点，再读相关汇编；不能按源码关键字估算周期。

### 15.4 Multi-core 与 Measurement

Multi-core 1～5：一致性协调核间对共享内存的缓存状态；true sharing 是同一逻辑状态竞争，false sharing 是不同状态碰到同一干扰粒度。relaxed 不取消原子写的所有权协调，所以不是 false sharing 修复。6～9：真正不可变的共享数据减少写失效；本地聚合减少全局 RMW。连续块分区通常比交错写更易分离写入行，但要检查边界和实际布局。race-free 只排除一类语言错误，不保证没有等待、争用或坏局部性。

Measurement 1～3：延迟是单次完成时间，吞吐是单位时间产出；p99 是给定样本分布的百分位，不是最大值。benchmark 测量工作负载，profile 归因热点，trace 重建事件时间线。4～6：端到端指标保证局部热点确实相关；未优化部分限制总体收益。微基准会受优化消除、输入、热身和计时开销影响，不能机械外推。

Measurement 7～12：测量目标发布配置时使用相应优化选项；调试构建可用于诊断，但不能代表优化构建性能。输入分布、规模与顺序都是实验合同。profile 指导汇编阅读，优化后瓶颈可能转移所以要再测。计数器是可解释信号，不是因果裁决；收益还要与维护、内存和构建复杂度比较。未采集的 CPU profile 或硬件 counter 必须登记 NOT RUN，不用汇编代替。

<a id="g6-section-16"></a>

## 16. 工程原则回查

<a id="g6-topic-104"></a>

### 16.1 如果半年后只能记住十五条

1. **C++ 性能不能从语法直接判断，必须追到 object representation、access pattern 和 machine behavior。**

2. **`sizeof(T)` 描述 object stride；alignment 和 padding 会决定大量 dense objects 的真实 footprint。**

3. **CPU 的核心成本之一是 data movement，而不是单纯 arithmetic instruction count。**

4. **Cache line utilization 决定一次 memory transfer 中有多少 bytes 真正为当前 kernel 服务。**

5. **Contiguous dense storage 的优势来自 cache locality、prefetch、memory-level parallelism、page locality 和 TLB reuse。**

6. **Pointer chasing 的代价远不止“多一次解引用”：它会制造 dependent loads、cache misses、page spread 和 TLB pressure。**

7. **AoS 与 SoA 没有绝对 winner；representation 必须由 hot access pattern 决定。**

8. **Hot/cold splitting 往往比微调几个 padding bytes 更值得优先考虑。**

9. **最好的 allocation 优化首先是不 allocation：inline、reserve、reuse、batch。**

10. **Arena 用 grouped lifetime 换廉价 allocation；Pool 用固定 slot topology 换廉价重复复用；两者都不会取消 C++ lifetime rules。**

11. **Virtual address、cache、TLB、page fault 和 physical memory 是不同层次的问题。**

12. **Branch 不天然昂贵；不可预测的 control flow 才可能昂贵，branchless 同样可能做更多无用工作。**

13. **多线程 correctness 和多线程 performance 是两个不同问题；false sharing 可以让完全 race-free 的程序严重退化。**

14. **高性能设计优先减少高频跨边界动作：allocation、page fault、shared mutation、cache-line ownership transfer、runtime dispatch。**

15. **任何性能优化都必须经过 Measure → Explain → Change → Measure Again 的证据闭环。**

<a id="g6-section-17"></a>

## 17. G1～G6 的统一系统模型

现在我们已经可以用同一个流程分析绝大多数系统 C++。 假设看到：

`std::vector<std::shared_ptr<Record>>`

不要只看类型名字。 按顺序问：

```text
G1 — Object Model
Record / shared_ptr / vector 哪些 objects 存在？
哪些 references/pointers 可能失效？

G2 — Ownership
为什么 Record 需要 shared ownership？
谁延长 lifetime？

G3 — Value Cost
shared_ptr copy 有没有 refcount？
Record 是否可以直接 value-store？
move/copy 成本如何？

G5 — Genericity
哪些行为需要 compile-time specialization？
这里的 template 是否真的必要？

G6 — Machine
多少 allocations？
多少 indirections？
Record 散落多少 pages？
iteration locality怎样？
shared_ptr control blocks是否跨线程竞争？
是否存在 false sharing？
真正 profile 热点在哪里？
```

这就是从：“会写 C++” 走向：**能够解释 C++ 系统为何以某种方式工作。**

<a id="g6-section-18"></a>

## 18. 从机器观察转向语言并发模型

G6 的成本分析不能替代同步正确性；下一章 [G7](g07-concurrency-and-memory-model.md) 以普通数据发布为例，区分硬件一致性与 C++ 可依赖的顺序。当前为 Markdown 编辑稿，不沿用历史 Frozen 标记授予技术基线资格。

<a id="g6-section-19"></a>

## 19. 参考与验证入口

[全系列导航](README.md) · [实验说明](learning/README.md) · [本批修订与证据](learning/professional-revision.md)

布局和分配结论区分语言合同与目标 ABI；生成汇编的工具选项见 [Clang 用户手册](https://clang.llvm.org/docs/UsersManual.html)。本批输出不构成处理器性能排名。
