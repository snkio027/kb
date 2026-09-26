# C++ Systems Track · G6 Memory & Performance

**Version:** 1.0  
**Status:** Frozen Review Baseline  
**Language Baseline:** C++23  
**Track:** Modern C++ Systems Track  
**Prerequisites:** G0 Native Toolchain & Machine Boundary, G1 Object Model, G2 RAII & Ownership, G3 Value Semantics, G5 Generic Programming  
**Scope:** Object Layout / Alignment / Padding / Cache / Locality / AoS / SoA / Allocation / Arena / Pool / PMR / Virtual Memory / TLB / Branch Prediction / Cache Coherence / False Sharing / Benchmarking / Profiling  
**Purpose:** 建立从 C++ object representation 一直追踪到 CPU、Cache、Virtual Memory、多核和性能证据的统一分析模型。

---

# 0. 文档定位

G6 不再主要学习“C++ 有哪些语法”。

它研究的是：

> **一个语义正确的 C++ 程序，最终怎样使用 CPU 和内存，以及这些选择为什么会快或慢。**

前面几个阶段分别解决：

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

---

# 1. G6 的统一性能模型

分析一段 hot code 时，不再只问：

```text
有几条语句？
算法是不是 O(N)？
有没有 virtual？
有没有 new？
```

而是至少拆成：

```text
Performance Cost
≈
Useful Compute
+
Bytes Moved
+
Memory Latency
+
Allocation / Deallocation
+
Indirection
+
Address Translation
+
Control-flow Cost
+
Cross-core Coordination
```

并且这些成本又依赖：

```text
Representation
×
Access Pattern
×
Working-set Size
×
Runtime Distribution
×
Thread Topology
```

所以一个贯穿 G6 的原则是：

> **复杂度是性能分析的起点，而不是终点。**

两个算法都可能是：

```text
O(N)
```

但一个可能连续扫描内存，另一个可能每一步都随机追 pointer。

机器行为可以相差巨大。

---

# Part I · Object Layout

# 2. `sizeof(T)` 的准确含义

```cpp
sizeof(T)
```

表示一个 `T` object representation 所占的 byte 数，并且必须允许：

```cpp
T values[N];
```

中的相邻 objects 正确排列。

所以它并不等于：

> 所有成员 `sizeof` 简单相加。

例如：

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

---

# 3. Alignment

```cpp
alignof(T)
```

表示：

> `T` object 起始地址必须满足的 alignment requirement。

例如某平台：

```text
alignof(uint32_t) = 4
```

意味着一个正常 `uint32_t` object 的地址通常必须满足：

```text
address % 4 == 0
```

Alignment 存在的原因可能包括：

```text
CPU load/store requirements
ABI
atomic operations
SIMD/vector instructions
access efficiency
```

重要的是：

> **能够进行 unaligned access，不等于 alignment 无意义。**

---

# 4. Internal Padding 与 Tail Padding

## 4.1 Internal Padding

成员之间为了使下一个 member 正确对齐而加入的 bytes。

例如：

```cpp
struct S {
    std::uint8_t a;
    std::uint32_t b;
};
```

可能：

```text
[a][pad][pad][pad][ b b b b ]
```

---

## 4.2 Tail Padding

最后一个 member 后面的 padding。

例如：

```cpp
struct S {
    std::uint32_t x;
    std::uint8_t y;
};
```

可能：

```text
[x x x x][y][pad][pad][pad]
```

这样：

```cpp
S values[2];
```

中第二个 `S` 仍然从满足 `alignof(S)` 的地址开始。

因此：

> **Tail padding 的一个核心作用是保证 array stride 正确。**

---

# 5. Member Ordering

考虑：

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

在常见 64-bit ABI 下，`A` 可能显著大于 `B`。

如果每个 object 差 8 bytes：

```text
10,000,000 objects
× 8 bytes
=
80 MB
```

因此 member ordering 会影响：

```text
RAM footprint
cache density
page density
memory bandwidth
TLB reach
```

但不能机械执行：

> “所有 struct 都从大字段排到小字段。”

因为 declaration order 同时决定：

```text
construction order
destruction reverse order
ownership teardown dependency
semantic grouping
ABI/layout
```

所以：

> **Member ordering 是架构设计，不是格式化规则。**

---

# 6. Inline Representation 与 Indirect Representation

## Inline

```cpp
std::array<float, 1024>
```

payload 就在 object 内部。

因此：

```text
sizeof(object)
≈
logical payload footprint
```

---

## Indirect

```cpp
std::vector<float>
```

vector object 本身通常只是类似：

```text
pointer
size
capacity
```

而真正的大 payload 位于 dynamic allocation。

因此：

```cpp
sizeof(std::vector<float>)
```

只能说明：

> vector wrapper 本身的 representation。

不能说明：

> 它拥有的数据总 footprint。

同理：

```text
unique_ptr
shared_ptr
string
vector
PImpl
```

都必须分析完整 object graph，而不只是 `sizeof(wrapper)`。

---

# 7. Object Representation ≠ Logical Value

假设：

```cpp
struct S {
    std::uint8_t a;
    std::uint32_t b;
};
```

即使：

```cpp
x.a == y.a && x.b == y.b
```

也不能普遍推出：

```cpp
std::memcmp(&x, &y, sizeof(S)) == 0
```

适合作为 logical equality。

因为 object representation 可能包含：

```text
padding
multiple valid representations
pointer representation
floating-point representation details
```

所以：

```text
Logical Equality
≠
Byte-for-byte Object Representation Equality
```

同样：

> `std::is_trivially_copyable_v<T>` 不等于 `T` 可以直接作为 portable wire format。

序列化还必须考虑：

```text
endianness
padding
ABI
versioning
schema
type width
```

---

# Part II · Cache & Locality

# 8. Memory Hierarchy

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

因此很多程序不是：

> CPU arithmetic 不够快。

而是：

> CPU 等不到数据。

---

# 9. Cache Line

CPU 通常不会为了访问：

```cpp
float value;
```

只向更远 memory 层请求 4 bytes。

数据通常以 cache-line 粒度进入 cache。

现代许多平台常见：

```text
64-byte cache line
```

但这是 hardware property，不是 C++ 标准保证。

因此：

```cpp
sum += sample.value;
```

可能逻辑只读取：

```text
4 bytes
```

而 memory hierarchy 实际引入：

```text
包含这个 value 的整条 cache line
```

这就是为什么：

> **Data layout 会直接决定 memory traffic。**

---

# 10. Spatial Locality

> 短时间内访问地址彼此接近的数据。

例如：

```cpp
for (const auto& value : values) {
    process(value);
}
```

对于：

```cpp
std::vector<T>
```

通常：

```text
[T][T][T][T][T]
→ → → → →
```

非常适合 spatial locality。

---

# 11. Temporal Locality

> 短时间内反复访问同一份数据。

例如：

```cpp
state.position += velocity;
use(state.position);
state.position += correction;
```

`state.position` 很可能仍位于：

```text
register / cache
```

因此后续访问更便宜。

---

# 12. Cache-line Utilization

假设：

```text
cache line = 64 B
```

而一个算法每条 line 只真正使用：

```text
4 B
```

则：

```text
useful ratio ≈ 6.25%
```

也就是说：

> 代码只写了一个 4-byte load，不代表 memory subsystem 只付出了 4 bytes 的成本。

这成为 SoA / hot-cold split 的主要动机之一。

---

# 13. Pointer Chasing

Dense layout：

```text
[T][T][T][T][T]
```

Pointerized layout：

```text
[p][p][p][p]
 │  │  │  │
 ▼  ▼  ▼  ▼
 T  T  T  T
```

后者可能引入：

```text
extra pointer load
random heap locations
cache misses
dependent loads
poor hardware prefetch
more pages
larger TLB working set
```

所以：

```cpp
std::vector<T>
```

与：

```cpp
std::vector<std::unique_ptr<T>>
```

即使遍历都是：

```text
O(N)
```

实际性能仍可能完全不同。

---

# 14. Dependent Memory Access

链表：

```text
Node0 → Node1 → Node2 → Node3
```

下一地址必须等：

```text
Node0.next
```

先从 memory 返回。

这意味着：

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

多个 memory misses 很难充分并行。

所以 pointer chasing 的一个深层问题是：

> **Memory-Level Parallelism 较差。**

---

# 15. Hardware Prefetch

规则访问：

```text
X
X+64
X+128
X+192
```

硬件容易预测：

> 很可能还会继续向后读。

于是提前请求下一些 cache lines。

完全随机访问：

```text
0xA...
0xF...
0x21...
```

则难得多。

因此：

```text
contiguous
regular-strided
```

访问模式通常更硬件友好。

---

# 16. Working Set

> 某个时间窗口内真正活跃的数据集合。

如果 working set 能较好驻留 cache：

```text
cache hits ↑
latency ↓
```

如果远大于 cache：

```text
replacement ↑
memory traffic ↑
```

因此：

> Object footprint 不仅影响 RAM，也决定能有多少 hot objects 同时留在 cache。

---

# 17. Cache Density

假设：

```text
cache line = 64 B
```

如果：

```text
sizeof(T) = 8
```

一条 line 大约可以容纳：

```text
8 objects
```

如果：

```text
sizeof(T) = 32
```

只能容纳：

```text
2 objects
```

因此 object size 会影响：

> 每次 cache fill 能顺便带进多少 useful objects。

---

# 18. Latency 与 Bandwidth

## Latency

> 等某个特定数据到达需要多久。

Random pointer chasing 容易 latency-bound。

---

## Bandwidth

> 单位时间能够搬多少 bytes。

大型连续 scan 更容易 bandwidth-bound。

例如：

```cpp
for (float x : huge_values) {
    sum += x;
}
```

虽然会产生很多 cache misses，

但：

```text
sequential
predictable
prefetchable
parallel memory requests
```

所以仍可能非常高效。

这说明：

> **Cache miss 本身不是性能 verdict。**

---

# 19. Arithmetic Intensity

粗略定义：

```text
Useful Computation
──────────────────
Bytes Moved
```

如果：

```text
1 add / many bytes
```

更可能 memory-bound。

如果：

```text
many FLOPs / few bytes
```

更可能 compute-bound。

因此优化前要问：

```text
memory-bound?
compute-bound?
latency-bound?
branch-bound?
```

---

# Part III · AoS / SoA / AoSoA

# 20. AoS — Array of Structures

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

```text
[ts id value valid]
[ts id value valid]
[ts id value valid]
```

优势：

```text
complete entity contiguous
simple ownership
simple lifetime
simple invariants
natural API
```

适合：

> 每次处理一个完整 entity。

---

# 21. SoA — Structure of Arrays

```text
timestamps: [ts][ts][ts]
ids:        [id][id][id]
values:     [v ][v ][v ]
valid:      [x ][x ][x ]
```

适合：

> 批量扫描某几个字段。

例如只计算 values：

```text
[value][value][value][value]
```

每条 cache line 几乎都装当前 kernel 真正需要的数据。

---

# 22. SoA 的第一收益

不是首先：

> SIMD。

而是：

> **减少 Overfetch 和无用 data movement。**

之后才进一步改善：

```text
vector loads
SIMD
masked processing
column compression
```

---

# 23. SoA 的成本

SoA 将一个 logical row 拆成多个 arrays。

于是必须保持：

```text
timestamps.size()
==
ids.size()
==
values.size()
==
valid.size()
```

产生新的 structural invariant。

同时可能增加：

```text
multiple allocations
coordinated reserve/growth
exception-safety complexity
API complexity
borrow invalidation complexity
```

所以 SoA 是：

> 用 representation complexity 换 performance opportunity。

---

# 24. AoSoA

```text
Block 0:
    x[N]
    y[N]
    z[N]

Block 1:
    x[N]
    y[N]
    z[N]
```

它折中：

```text
SoA SIMD friendliness
+
bounded block locality
+
some entity neighborhood
```

常用于：

```text
particles
physics
robotics kernels
HPC
```

但实现复杂度高。

默认路线应该是：

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

---

# 25. Hot / Cold Split

例如：

```cpp
struct Robot {
    Position position;     // hot
    Velocity velocity;     // hot

    std::string name;      // cold
    DebugInfo debug;       // cold
};
```

physics loop 只需要：

```text
position
velocity
```

则拆为：

```text
RobotState
RobotMetadata
```

可以同时降低：

```text
cache working set
memory bandwidth
page working set
TLB pressure
```

这往往比：

> 省几 bytes padding

有价值得多。

---

# 26. Layout 的统一原则

```text
Frequently co-accessed data
→ colocate

Independently scanned data
→ separate

Independent high-frequency writers
→ separate cache lines / regions
```

这三条贯穿单线程和多线程 data layout。

---

# 27. Phase-specific Representation

系统不必只有一种 domain representation。

可以：

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

一次 representation transform：

```text
O(N)
```

如果后续：

```text
大量重复处理
```

完全可能值得。

因此：

> **Representation 可以服务某个 processing phase，而不是服务抽象上的“对象纯洁性”。**

---

# Part IV · Allocation

# 28. Allocation 与 Construction

```cpp
new T(args...)
```

概念上：

```text
raw storage allocation
+
T construction
```

而：

```cpp
delete p;
```

：

```text
T destruction
+
storage deallocation
```

必须永久分开：

```text
Allocation
Construction
Destruction
Deallocation
```

---

# 29. General Heap Allocation 的成本

可能包含：

```text
allocator metadata
size classes
free-list operations
synchronization
cache misses
fragmentation handling
occasionally acquiring more pages
```

但：

> 普通 `new` 一般不意味着每次都直接进行 syscall。

Allocator 通常已经从 OS 获取较大的 memory regions。

---

# 30. Stack 为什么便宜？

Stack 有非常强的：

> LIFO lifetime discipline。

概念：

```text
allocate
→ move stack pointer

deallocate
→ restore stack pointer
```

General heap 则支持：

```text
A allocate
B allocate
C allocate
B free
D allocate
A free
...
```

因此需要更复杂的 free-space management。

可以理解成：

> **Heap 用 bookkeeping 成本购买 arbitrary lifetime flexibility。**

---

# 31. Per-item Allocation

例如：

```cpp
std::vector<std::unique_ptr<Detection>>
```

大量 small values 时可能产生：

```text
N allocations
N allocator metadata
N indirections
fragmentation
poor cache locality
more pages
larger TLB working set
```

所以如果：

```text
small
value-like
no polymorphism
no address-stability requirement
```

通常优先：

```cpp
std::vector<Detection>
```

---

# 32. Internal / External Fragmentation

## Internal Fragmentation

请求：

```text
24 B
```

allocator 给：

```text
32 B slot
```

内部没用掉的 8 B。

---

## External Fragmentation

总 free space 足够，

但：

```text
散成多个小 region
```

无法满足一块较大的 contiguous request。

Fragmentation 不只浪费 RAM，

还可能恶化：

```text
page usage
locality
TLB pressure
```

---

# 33. Allocation Optimization Ladder

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

这是非常重要的顺序。

不要：

```text
看到 new
→ 写 memory pool
```

---

# 34. `reserve + clear`

非常重要的 steady-state pattern：

```cpp
std::vector<Sample> samples;
samples.reserve(max_samples);

for (;;) {
    samples.clear();

    collect(samples);
    process(samples);
}
```

如果 capacity 不再增长：

```text
steady-state allocation ≈ 0
```

在引入 custom allocator 前应该优先考虑这种简单方案。

---

# 35. Arena / Region Allocation

核心：

```text
large region

[A][B][C][free........]
          ↑
        cursor
```

每次 allocation：

```text
align cursor
return cursor
advance cursor
```

最终：

```text
reset / release whole region
```

适合：

```text
request lifetime
batch lifetime
parser pass
frame processing
compiler AST
```

即：

> 一批 objects 拥有近似共同 lifetime。

---

# 36. Arena 的真正来源

Arena 快不是因为“特殊内存”。

而是因为它限制：

> individual arbitrary deallocation。

因此不需要一般性的：

```text
free-list search
coalescing
per-object reclaim
```

再次体现：

> **Lifetime constraints 可以换来更简单、更可预测的 memory management。**

---

# 37. Arena 与 Object Lifetime

Arena reset 只是在处理：

> storage。

它不会自动正确销毁 placement-new 出来的：

```text
string
vector
file wrapper
mutex
```

等 non-trivial objects。

因此：

```text
Arena Storage Lifetime
≠
C++ Object Lifetime
```

---

# 38. Pool

Pool 适合：

```text
many same/similar-size objects
+
individual arbitrary lifetimes
```

结构：

```text
[used][free][used][free]
        ↑          ↑
        free list
```

allocate：

```text
pop free slot
```

free：

```text
push slot back
```

---

# 39. Arena vs Pool

```text
Arena
→ lifetime grouped
→ bulk release

Pool
→ slots reused independently
→ arbitrary per-object lifetime
```

这是根本区别。

---

# 40. Stale Generation

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

旧 pointer：

```text
same address
```

但已经：

```text
different object
different lifetime
different generation
```

所以：

> **Stable address 不等于 stable logical identity。**

Generational handle：

```cpp
struct Handle {
    std::uint32_t index;
    std::uint32_t generation;
};
```

可以检测 stale access。

---

# 41. `std::pmr`

核心 abstraction：

```cpp
std::pmr::memory_resource
```

它把：

```text
container/value behavior
```

和：

```text
runtime allocation strategy
```

进行一定程度解耦。

例如：

```cpp
std::pmr::vector<T>
```

可以配：

```text
monotonic_buffer_resource
unsynchronized_pool_resource
synchronized_pool_resource
custom resource
```

---

# 42. `monotonic_buffer_resource`

类似 arena：

```text
allocate monotonically
individual deallocate normally does not reclaim slot
release resource together
```

适合：

```text
batch/request/phase-local allocations
```

但 container destructor 仍然负责：

> 正确结束 element lifetimes。

Memory resource 只改变：

> raw storage allocation policy。

---

# 43. Allocation Profile 要看什么？

至少：

```text
allocation count
allocated bytes
size distribution
lifetime distribution
peak live bytes
thread of allocation
thread of free
```

尤其：

```text
millions of tiny allocations
```

往往比少数大 allocation 更可疑。

---

# Part V · Virtual Memory

# 44. Pointer 通常是 Virtual Address

用户态：

```cpp
T* p;
```

通常首先代表：

> virtual address。

不是直接的 DRAM physical address。

每个 process 有自己的：

```text
Virtual Address Space
```

---

# 45. Pages

Virtual memory 以 page 为主要映射粒度。

例如平台可能使用：

```text
4 KiB
16 KiB
large pages
...
```

这是 OS / hardware property。

Virtual pages：

```text
VPage 100
VPage 101
VPage 102
```

可以分别映射到：

```text
不同 physical pages
```

所以：

> virtual contiguous 不代表 physical contiguous。

---

# 46. MMU / Page Table

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

```text
Virtual Page Number
+
Page Offset
```

映射改变 page number，

offset 保持。

---

# 47. TLB

> **Translation Lookaside Buffer**

缓存：

```text
Virtual Page
→
Physical Page
```

的 translation。

因此 memory access 同时涉及两套 locality：

```text
Address Translation Locality
+
Data Cache Locality
```

---

# 48. TLB Miss 与 Page Fault

必须严格区分。

## TLB Miss

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

---

## Page Fault

CPU 当前无法完成访问：

```text
trap to kernel
```

可能是：

```text
first anonymous-page touch
copy-on-write
mapped file page
protection fault
illegal address
```

因此：

> Page fault 不等于程序一定出错。

---

# 49. Allocation ≠ Physical Memory Immediately

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

所以：

```text
malloc/new 10 GB
```

与：

```text
touch 10 GB of actual pages
```

不是同一件事。

---

# 50. First Touch

第一次真正访问 large memory：

```text
page faults
page zeroing
mapping work
```

可能产生 latency spike。

因此 latency-sensitive 系统有时会：

```text
preallocate
pre-touch
reuse
```

把成本从：

```text
hot phase
```

搬到：

```text
initialization
```

这叫：

> **Latency Placement**

而不是凭空消除工作。

---

# 51. Page Locality / TLB Reach

Dense storage：

```text
many useful objects / page
```

意味着一个 TLB entry 可以服务更多 object accesses。

Sparse pointer graph：

```text
few useful bytes spread over many pages
```

则可能：

```text
TLB working set ↑
page walks ↑
```

因此 object density 同时影响：

```text
cache density
page density
TLB reach
```

---

# 52. Huge Pages

更大 page：

```text
translations needed ↓
TLB reach ↑
```

但可能增加：

```text
internal waste
mapping granularity
fault cost
memory management complexity
```

所以只有：

> translation overhead 已被 profile 证明有意义

时才值得考虑。

---

# 53. `mmap`

核心不是：

> “读取文件的另一种 API”。

而是：

> 把 virtual address range 映射到某种 backing object。

访问：

```cpp
mapped[i]
```

看起来只是普通 pointer access，

但可能隐藏：

```text
TLB miss
page fault
filesystem
storage I/O
```

所以：

> **Pointer syntax 不揭示 memory latency class。**

---

# Part VI · Branch Prediction & Control Flow

# 54. Branch Prediction

CPU 遇到：

```cpp
if (condition) {
    foo();
} else {
    bar();
}
```

不能总停下来等 condition 完成。

因此：

```text
predict branch
↓
fetch predicted path
↓
execute speculatively
↓
verify later
```

---

# 55. Predictable Branch

例如：

```text
99.9% true
```

通常很容易预测。

因此：

> `if` 并不天然昂贵。

真正可能贵的是：

> **Branch Misprediction**

---

# 56. Misprediction

预测错误：

```text
wrong-path instructions
↓
discard/squash
↓
restart correct path
```

成本显著高于单纯 compare。

所以 branch 成本取决于：

```text
data distribution
branch history
microarchitecture
```

---

# 57. Branch Cost 是 Runtime-state-dependent

同样：

```cpp
if (valid) {
    process();
}
```

数据：

```text
99.9% true
```

和：

```text
50/50 random
```

性能可能完全不同。

因此：

> **Input distribution 是性能 specification 的一部分。**

---

# 58. Source Branchless ≠ Machine Branchless

```cpp
count += value >= threshold;
```

源码没有 `if`，

compiler 仍决定具体 lowering。

反过来：

```cpp
if (value >= threshold) {
    ++count;
}
```

也可能被编译成 branchless code。

所以：

> 查看 optimized machine code，而不是从 C++ syntax 猜。

---

# 59. Branchless 的 Trade-off

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

```text
expensive computation
invalid operation
memory load
rare path
```

且容易预测，

branch 往往更好。

---

# 60. SIMD 与 Mask

当一条 vector instruction同时处理多个 lanes：

```text
lane 0 true
lane 1 false
lane 2 true
...
```

单一 scalar control-flow branch 很难表达。

因此 SIMD 常用：

```text
mask
select
blend
masked operations
```

这也是 SoA 更容易 vectorize 的一个原因。

---

# 61. Fast Path / Slow Path

高概率场景：

```text
short
predictable
hot
```

低概率异常：

```text
large diagnostics
error handling
logging
```

可以拆：

```text
fast path
+
cold slow path
```

这既可能帮助：

```text
branch predictability
```

也可能改善：

```text
instruction-cache working set
```

---

# 62. `[[likely]]` / `[[unlikely]]`

它们主要是：

> compiler optimization hints。

不是：

```text
runtime branch predictor command
```

也不是 correctness guarantee。

应该来自：

```text
real domain distribution
profile
strong invariant
```

而不是凭感觉乱加。

---

# 63. Direct / Indirect Dispatch

Direct call：

```cpp
decode_msg_100();
```

target compile-time known。

Function pointer：

```cpp
fn();
```

target runtime known。

Virtual dispatch：

```cpp
obj.virtual_method();
```

通常也是 indirect control flow。

Indirect dispatch 可能影响：

```text
target prediction
inlining
interprocedural optimization
```

但 target 稳定、每次 useful work 足够多时：

> 成本完全可能很小。

---

# 64. Static Dispatch

Template specialization：

```cpp
process<Camera>();
```

target 更容易在 compile time 决定。

优势：

```text
direct call
inline
constant propagation
```

代价：

```text
more specializations
larger code
I-cache pressure
compile time
```

所以 static dispatch 不是免费胜利。

---

# Part VII · Cache Coherence & False Sharing

# 65. Coherence

多核：

```text
Core 0 Cache
    ↕
coherence
    ↕
Core 1 Cache
```

当同一 memory region 被多个 cores 访问，

hardware 必须保持 cache copies 的一致性。

重要粒度通常是：

> cache line / coherence block，

而不是 C++ object。

---

# 66. False Sharing

```cpp
struct Counters {
    std::atomic<std::uint64_t> a;
    std::atomic<std::uint64_t> b;
};
```

Thread 0：

```text
writes a
```

Thread 1：

```text
writes b
```

如果：

```text
a + b
```

位于同一 cache line，

硬件仍会让 line ownership在 cores 之间反复转移。

这叫：

> **False Sharing**

即：

```text
logically separate
but
physically shared coherence block
```

---

# 67. True Sharing vs False Sharing

## True Sharing

多个 threads 真正更新同一个：

```cpp
std::atomic<uint64_t> counter;
```

共享不可避免。

---

## False Sharing

多个 threads 更新不同 values，

只因为物理 colocated 而产生 coherence contention。

因此：

```text
Race-free
≠
Contention-free
≠
Fast
```

---

# 68. `memory_order_relaxed` 不能解决 False Sharing

`relaxed` 控制的是：

> C++ memory-ordering contract。

但 atomic write 仍然必须获得：

> 对对应 coherence line 的 writable ownership。

因此：

```text
weak ordering
+
terrible false sharing
```

完全可能同时存在。

---

# 69. Shared Immutable Data

多个 cores 只读：

```text
immutable Model
```

cache lines 可以保留共享副本。

因此：

```text
Shared Immutable Data
```

同时具有：

```text
simpler synchronization
+
friendly cache-coherence behavior
```

这也是 immutable snapshot architecture 强大的原因。

---

# 70. 优先减少 Shared Mutation

不要遇到 false sharing 就先 padding。

更强的优化顺序：

```text
1. Remove sharing
2. Single writer
3. Per-thread / per-worker state
4. Batch aggregation
5. Cache-line isolation
```

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

---

# 71. Parallel Partition

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

因为 interleaved writes 很容易让每条 cache line被多个 cores同时修改。

因此：

> Parallel partition 应尽可能和 physical ownership region 对齐。

---

# 72. `alignas` 与 Interference Size

C++ 提供：

```cpp
std::hardware_destructive_interference_size
std::hardware_constructive_interference_size
```

用于表达：

```text
avoid destructive sharing
or
encourage constructive colocating
```

的 implementation-specific尺度。

例如：

```cpp
struct alignas(
    std::hardware_destructive_interference_size)
Counter {
    std::atomic<std::uint64_t> value{};
};
```

但隔离 cache lines 会增加 footprint。

仍然是：

```text
coherence isolation
vs
memory density
```

的 trade-off。

---

# Part VIII · Measurement & Profiling

# 73. 性能首先要定义 Metric

可能是：

```text
Latency
Throughput
p99
CPU utilization
Memory footprint
Allocation rate
Startup time
Energy
```

“更快”不是完整 requirement。

---

# 74. Latency vs Throughput

Latency：

> 一次 operation 多久完成。

Throughput：

> 单位时间完成多少工作。

增加 batch size 可能：

```text
throughput ↑
latency ↑
memory ↑
```

所以必须知道优化目标。

---

# 75. Tail Latency

平均值可能隐藏极端慢请求。

因此系统常看：

```text
p50
p90
p95
p99
p99.9
max
```

例如：

```text
p99 = 10 ms
```

表示：

> 大约 99% observations 不超过 10ms。

不是：

> 最慢 1% 平均值是 10ms。

---

# 76. Benchmark / Profiler / Tracing

## Benchmark

回答：

> **某个操作有多快？**

---

## Profiler

回答：

> **CPU 时间花在哪里？**

---

## Tracing

回答：

> **一条 request/job 的事件时间线是什么？**

例如：

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

---

# 77. End-to-end First

先看整个系统：

```text
Download     20%
Decompress   40%
Decode        5%
Produce      10%
Waiting      25%
```

如果 decode 只占 5%，即使加速很多：

> end-to-end 也不会提升很多。

这就是 Amdahl's Law 的工程直觉。

---

# 78. Microbenchmark

适合回答：

```text
AoS vs SoA kernel
runtime dispatch vs static dispatch
allocator A vs allocator B
```

但必须控制：

```text
setup
allocation
RNG
logging
dead-code elimination
constant folding
cache state
input distribution
```

最大的风险是：

> **非常精确地测错问题。**

---

# 79. Optimized Build

生产性能实验必须接近 production：

```text
-O2 / -O3
```

不能以：

```text
-O0
```

作为主要性能结论。

因为：

```text
templates
span
iterators
small wrappers
```

很多 abstraction 成本只有 optimizer 后才真正体现。

---

# 80. Dead-code Elimination

如果 benchmark result 从未被使用，

compiler可能删掉整个 computation。

所以 benchmark 必须：

> 让结果具有 observable relevance。

不要机械用 `volatile` 解决所有问题。

专业 benchmark framework 通常提供专门 optimization barriers。

---

# 81. Warm-up

第一次运行可能包括：

```text
cold caches
page faults
branch-predictor cold state
dynamic-linking initialization
filesystem cache effects
```

所以必须明确：

> 测 cold-start，还是 steady-state？

两个都是合法目标，但不能混。

---

# 82. Dataset Size

Benchmark 应覆盖：

```text
small
medium
large
```

使 working set：

```text
fits small cache
fits larger cache
exceeds cache
streams from memory
```

否则小 dataset 的结果可能完全不能代表 production。

---

# 83. Input Distribution

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

都会改变结果。

所以：

> Input distribution 是 benchmark specification 的一部分。

---

# 84. Hardware Counters

可以帮助观察：

```text
cycles
instructions
branch misses
cache misses
TLB misses
loads/stores
```

它们解释：

> 为什么慢。

但最终是否优化成功仍然由：

```text
end-to-end latency
throughput
tail
memory
```

决定。

---

# 85. Profiler Before Assembly

正确顺序：

```text
profile
↓
find hotspot
↓
inspect hotspot assembly
```

Assembly 是：

> microscope。

Profiler 是：

> map。

不要研究一个只占 0.1% CPU 的函数三小时汇编。

---

# 86. Bottleneck Moves

优化前：

```text
allocator 40%
decode    30%
```

优化 allocator 后：

```text
allocator 3%
decode   65%
```

说明：

> 新瓶颈浮现。

因此必须：

```text
profile
→ optimize
→ profile again
```

而不是一次 profile 后一路凭经验优化。

---

# 87. One Variable at a Time

如果同时：

```text
AoS → SoA
heap → arena
branch → branchless
runtime → template
```

最终快 30%，

你不知道是谁贡献的。

所以尽可能：

> 一次改变一个主要因素。

保留：

```text
baseline
change
result
interpretation
```

---

# 88. Performance Evidence Ladder

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

越往下层越解释 mechanism，

越往高层越证明真实系统价值。

---

# Part IX · Unified Performance Review

# 89. G6 九层 Review Protocol

任何性能敏感代码都可以按下面顺序检查。

---

## Layer 1 — Object Representation

问：

```text
sizeof(T)?
alignof(T)?
padding?
inline or indirect?
```

---

## Layer 2 — Access Pattern

问：

```text
sequential?
strided?
random?
pointer chasing?
```

---

## Layer 3 — Working Set

问：

```text
多少 bytes？
多少 cache lines？
多少 pages？
是否反复使用？
```

---

## Layer 4 — Data Layout

问：

```text
哪些 fields 是 hot？
哪些 fields 总一起访问？
AoS / SoA？
Hot/cold split？
```

---

## Layer 5 — Allocation

问：

```text
多少次 allocation？
size distribution？
lifetime distribution？
是否能 reuse？
```

---

## Layer 6 — Virtual Memory

问：

```text
first touch？
page faults？
TLB working set？
dense or sparse pages？
```

---

## Layer 7 — Control Flow

问：

```text
branch distribution？
predictable？
indirect dispatch？
branch 能跳过多少工作？
```

---

## Layer 8 — Multi-core

问：

```text
谁写什么？
shared mutation？
same cache line？
single writer possible？
batching possible？
```

---

## Layer 9 — Evidence

问：

```text
优化目标是什么？
baseline 是什么？
profile 证据是什么？
改完实际改善多少？
```

---

# 90. G6 Performance Smell Catalogue

## Smell 1 — Pointerized Small Values

```cpp
std::vector<std::unique_ptr<SmallValue>>
```

却没有：

```text
polymorphism
stable-address
independent lifetime
```

等真实需求。

---

## Smell 2 — Per-item Allocation

```cpp
for (...) {
    std::make_unique<T>();
}
```

位于百万级 hot path。

---

## Smell 3 — Cold Data in Hot Struct

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

---

## Smell 4 — Random Access on Huge Dataset

却只因为 container 是 `vector` 就认为 cache-friendly。

---

## Smell 5 — Premature SoA

没有 profile 就把简单 data model 拆成复杂 columns。

---

## Smell 6 — Branchless Cargo Cult

把 highly predictable branch 改成每次都执行昂贵工作。

---

## Smell 7 — Shared Atomic per Event

高频业务事件全部更新同一个 global atomic。

---

## Smell 8 — Per-thread Counters Adjacent

逻辑独立，却共享 cache line。

---

## Smell 9 — Custom Pool Before Reuse

连：

```text
reserve
clear
reuse
```

都没试，就自己维护 allocator。

---

## Smell 10 — Huge Template Specialization

只为了消除一个 branch，生成大量近似函数，增加 I-cache/code-size压力。

---

## Smell 11 — Benchmarking `-O0`

用 debug lowering 得出 production 性能结论。

---

## Smell 12 — Optimizing Without Baseline

只有：

> “我感觉现在快了。”

没有可重复 benchmark / profile。

---

# Part X · C++ / Zig / Rust Perspective

# 91. C++

C++ 的性能优势来自：

```text
explicit representation control
value semantics
contiguous standard containers
compile-time specialization
low-level memory access
RAII
```

但相应要求工程师真正理解：

```text
lifetime
aliasing
layout
allocator behavior
cache
memory model
```

语言不会自动替你选择最优 representation。

---

# 92. Zig

Zig 更显式暴露：

```text
allocator
array/slice distinction
layout
comptime
```

使：

```text
where does allocation happen?
who owns allocator?
```

通常更容易从 API 看出。

但：

```text
cache
TLB
AoS/SoA
false sharing
memory bandwidth
```

这些机器规律完全一样。

---

# 93. Rust

Rust 更强地静态约束：

```text
ownership
borrows
thread safety traits
```

但同样不能自动解决：

```text
bad locality
too many allocations
Arc contention
false sharing
poor AoS layout
```

因此：

> **Memory safety 与 memory performance 是不同维度。**

---

# 94. 跨语言共同事实

无论：

```text
C++
Zig
Rust
```

都无法绕开：

```text
cache-line granularity
page granularity
TLB
memory bandwidth
branch predictor
coherence
working set
```

这些属于：

> machine architecture

而不是某种语言哲学。

---

# Part XI · Terminology

# 95. G6 核心术语表

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

---

# Part XII · G6 Final Gate

# 96. Object Layout

应能解释：

1. 为什么 `sizeof(struct)` 不等于 members size sum？
2. Alignment 到底限制什么？
3. Internal padding 与 tail padding 有什么区别？
4. 为什么 member reordering 可以改变大数组 footprint？
5. 为什么 `memcmp` 通常不是普通 struct equality？
6. 为什么 `sizeof(vector<T>)` 不代表真实 payload footprint？

---

# 97. Cache

应能解释：

1. 什么是 cache line？
2. 什么是 spatial locality？
3. 什么是 temporal locality？
4. 什么叫 cache-line utilization？
5. 为什么 pointer chasing 不只是多一次 pointer dereference？
6. 为什么 sequential streaming 可以 cache miss 很多却仍然快？
7. latency-bound 与 bandwidth-bound 区别是什么？
8. working set 为什么重要？

---

# 98. Data Layout

应能解释：

1. AoS 和 SoA 物理布局区别是什么？
2. 哪种 workload 更适合 AoS？
3. 哪种 workload 更适合 SoA？
4. 为什么 SoA 往往更容易 SIMD？
5. SoA 会引入哪些新的 invariant？
6. AoSoA 在交换什么？
7. 为什么 hot/cold split 可能比 member padding 优化更重要？
8. 为什么 domain entity 不必等价于实际 C++ struct object？

---

# 99. Allocation

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

---

# 100. Virtual Memory

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

---

# 101. Control Flow

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

---

# 102. Multi-core

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

---

# 103. Measurement

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

---

# Part XIII · Fifteen Final Axioms

# 104. 如果半年后只能记住十五条

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

---

# Part XIV · G1–G6 Unified Systems Model

现在我们已经可以用同一个流程分析绝大多数系统 C++。

假设看到：

```cpp
std::vector<std::shared_ptr<Record>>
```

不要只看类型名字。

按顺序问：

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

这就是从：

> “会写 C++”

走向：

> **能够解释 C++ 系统为何以某种方式工作。**

---

# Part XV · G6 → G7

G6 到这里正式冻结。

下一阶段：

# G7 — Concurrency & C++ Memory Model

G6 已经告诉我们硬件层：

```text
Core 0 Cache
      ↕
Cache Coherence
      ↕
Core 1 Cache
```

但这仍然不能回答：

> **两个 C++ threads 到底在什么条件下可以合法地观察彼此的 writes？**

下一阶段从：

```cpp
bool ready = false;
int value = 0;

// Thread A
value = 42;
ready = true;

// Thread B
while (!ready) {
}

use(value);
```

开始。

人类很容易推理：

```text
看到 ready == true
↓
所以 value 应该 == 42
```

但这段代码首先存在：

> **Data Race**

在 C++ 中会进入：

> **Undefined Behavior**

G7 会正式建立：

```text
Thread
↓
Data Race
↓
Atomicity
↓
Sequenced-before
↓
Synchronizes-with
↓
Happens-before
↓
Visibility
↓
std::atomic
↓
relaxed
↓
acquire / release
↓
sequential consistency
↓
mutex
↓
condition_variable
↓
lock-free
```

最核心的目标不是背：

```cpp
memory_order_acquire
memory_order_release
```

而是建立一个精确模型：

> **什么时候另一个线程的 memory operation 对当前线程具有语言层面的顺序和可见性保证。**

G6 研究的是：

> **机器怎样执行 concurrent memory accesses。**

G7 将研究：

> **C++ 允许程序员怎样合法地推理 concurrent memory accesses。**

这两层必须严格分开。
