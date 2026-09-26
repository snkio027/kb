# G4 · STL、Ranges 与数据抽象

Modern C++ Systems Engineering · [Editorial Profile v1.0](editorial-profile.md)

编辑状态：Professional presentation refresh。PDF：NOT BUILT / NOT VALIDATED。

- **Version:** 1.2 · 呈现修订稿
- **Status:** Professional presentation refresh · 保留既有定向验证边界
- **Language Baseline:** C++23
- **Prerequisites:** G0–G3；G6/G7 的机器与并发模型可用于深化理解
- **Scope:** Containers / Iterators / `span` / `mdspan` / Algorithms / Ranges / Views / Sorting / Searching / Associative Containers / Flat Representations / Invalidation / Ownership-friendly APIs / Vocabulary Types
- **Purpose:** 学会根据语义、所有权、访问模式与系统成本选择和组合标准库 abstraction，而不是背容器 API。

## 阅读入口

[上一章：G3](g03-value-semantics-and-performance.md) · [全系列导航](README.md) · [下一章：G5](g05-generics-and-compile-time.md)

本章的问题是：**同一批数据，谁拥有、谁借用、怎样查询，才能同时说清正确性和成本？**

首次学习不需要先读 G5～G7：

1. [抽象模型](#g4-section-1)与[序列容器](#g4-section-2)：用 vector 建立 owner、size/capacity 和失效模型。
2. [视图](#g4-section-3)与[算法、Ranges](#g4-section-4)：学习 span、字符串借用、算法与 view。
3. [SignalBatch 完整实验](#g4-batch)：把排序、查询、统计和只读接口连起来。
4. [容量与 view 实验](#g4-labs)：验证边界，再做 [Final Gate](#g4-gate)。

其他容器、布局与状态类型用于回查；API、性能与跨语言材料用于第二遍对照。旧主题锚点保留，正文按下面的章节目录定位，不要求逐条背诵。只带 `g-lab` 标记的代码属于完整运行例；其余按上下文作片段、反例或自主练习。

选型的推理顺序是：需求语义 → 所有权/有效期 → 访问与更新模式 → 算法能力 → 表示与测量。不要从“某容器是 O(1)”倒推全部设计。

### 章节目录

- [1. 标准库的抽象模型](#g4-section-1)
- [2. 序列容器与失效](#g4-section-2)
- [3. 连续、多维与字符视图](#g4-section-3)
- [4. 迭代器、算法与 Ranges](#g4-section-4)
- [5. 关联表示与容器选择](#g4-section-5)
- [6. 状态建模](#g4-section-6)
- [7. SignalBatch：完整组件实验](#g4-section-7)
- [8. 数据修改与 API 边界](#g4-section-8)
- [9. 内存资源与性能决策](#g4-section-9)
- [10. 实验与观察](#g4-section-10)
- [11. 工程审查与常见误判](#g4-section-11)
- [12. 跨语言回查](#g4-section-12)
- [13. 工程原则回查](#g4-section-13)
- [14. Final Gate](#g4-section-14)
- [15. Final Gate · 参考答案与常见误判](#g4-section-15)
- [16. 统一模型](#g4-section-16)
- [17. 接下来怎么用](#g4-section-17)

<a id="g4-section-1"></a>

## 1. 标准库的抽象模型

<a id="g4-part-i"></a>

### 1.1 STL 的正确 Mental Model

**1. STL 不只是容器目录**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<int> values{3, 1, 4, 1, 5};
std::ranges::sort(values);
```

vector 拥有元素，range/iterator 暴露访问能力，算法通过这些能力工作。sort 需要随机访问和可排序等约束，而不是要求容器名必须叫 vector。

**2. 容器与算法怎样解耦？**

自由算法可以用于多个满足约束的表示，不必通过共同基类和虚函数。能力不满足时，不能靠“反正有 begin/end”调用；list 有适合自身结构的成员 sort。抽象的作用是表达必要能力，不是强迫一切操作使用同一形式。

**3. Owner、View 与 Algorithm**

| 角色 | 问题 | 例子 |
| --- | --- | --- |
| Owner | 谁管理元素与资源清理？ | vector、string、map |
| View / 借用接口 | 暴露哪种访问能力，依赖谁存活？ | span、string_view、默认 accessor 的 mdspan |
| Algorithm | 对范围要求什么能力与前置条件？ | sort、find、lower_bound、transform |

这是学习分工，不是互斥的标准类型分类：Ranges 的 owning_view 同时是 view 并持有底层 range。函数对象、投影和捕获也可能带自己的依赖。

<a id="g4-part-ii"></a>

<a id="g4-section-2"></a>

## 2. 序列容器与失效

### 2.1 vector：动态序列的默认起点

**4. 先考虑 vector，再寻找反要求**

如果要拥有运行时数量的同类型值，vector 提供连续元素、常数下标和较低的逐元素元数据成本，适合顺序遍历。这里排除 vector<bool> 的特殊表示；连续也不等于可直接作为 wire format，padding、字节序、对象语义仍需处理。

需要稳定节点、两端高频增长等反要求时，再比较其他容器。默认起点不等于无须测量的赢家。

**5. size 与 capacity 数的不是同一件事**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<int> values;
values.reserve(1024);
// size() == 0，capacity() >= 1024；还没有可用下标元素。
```

size 是现有元素数；capacity 是当前无需重分配能容纳的元素数。保留容量不许可访问 size 之外的元素。

**6. reserve 与 resize**

reserve 准备容量，不改变 size；resize 改变元素数，增长时初始化新元素，必要时还会分配。不是“一个快一个慢”的同义操作。想通过下标填充 N 个元素，应先建立这些元素，不能只 reserve(N)。

**7. clear 保留容量**

clear 销毁元素，使 size 为 0，并保留 capacity。因此“clear 后重新填充”可以复用 vector 的存储。元素自身析构仍可能释放其内部资源；这不证明每次迭代零分配。

[机制片段 · 不承诺独立编译]

```cpp
// 循环片段：fill/process 的合同由应用定义。
std::vector<T> buffer;
buffer.reserve(max_count);
for (;;) {
    buffer.clear();
    fill(buffer);
    process(buffer);
}
```

**8. shrink_to_fit 是请求**

它不保证 capacity 最终等于 size。若发生重分配，会使旧访问失效；频繁收缩还可能抵消存储复用收益。除非确有内存压力和使用阶段边界，不要把它机械加在每次 clear 后。

**9. push_back 与 emplace_back**

已有对象时，push_back 清楚表达加入一个值；直接给构造参数时，emplace_back 清楚表达就地构造。emplace_back(make_value()) 已经先求值出一个实参，并不能凭名字承诺完全免去转移；它不是高级版 push_back。

**10. 重分配是元素迁移，不只是字节 resize**

当成功插入使新 size 超过原 capacity，vector 必须取得更大容量，并按元素规则建立新位置、结束旧元素和释放旧存储。增长因子不是固定语言承诺。用非平凡类型时，不能把迁移理解为通用 realloc/memcpy。

**11. noexcept 为什么影响迁移选择？**

若移动可能修改源后抛出，而复制可用，复制可能更有利于保持异常保证。选择还受操作、类型要求和 allocator 条件影响；不能根据一次计数推出所有 vector 都按同一路径实现。必须真实满足合同才声明 noexcept。[FM-5](failure-model/fm5-noexcept-move-copy.md) 展开这些边界。

<a id="g4-part-iii"></a>

### 2.2 Iterator / Pointer / Reference Invalidation

**12. 从操作前提判断，而不是从地址外观判断**

[机制片段 · 不承诺独立编译]

```cpp
// 有条件危险的片段：若发生重分配，最后的读取非法。
std::vector<int> values{1, 2, 3};
int* p = &values[0];
values.push_back(4);
use(*p);
```

必须查原 capacity 与操作规则；不能依据 p 非空或一次运行没崩溃判断。本章 G4-L2 用可移植条件验证增长，不读取已失效指针。

**13. 重分配使旧元素的访问路径失效**

指向旧元素的 pointer、reference、iterator，以及旧 past-the-end iterator 都失效。后续要重新从 owner 获取合法访问，不能仅因为数值地址看似相同就继续用旧关系。

**14. 没有重分配，也有失效**

vector::erase 使擦除点及之后的迭代器和引用失效，旧尾后迭代器也失效；原位置可能被后续元素占据。指针地址与逻辑元素身份不能混为一谈。clear 更是结束全部元素，哪怕容量仍在。

**15. 长期身份与物理地址分开**

Vehicle #1234 是逻辑身份，不必永久绑定一个 vector 元素地址。ID/handle 可通过查找映射到当前表示，但还需范围检查和代际策略，防止回收后把旧 ID 误认成新对象。地址稳定和 ID 安全各有合同，不是换成整数就万事大吉。

**16. 回查表：记住问题，使用时查精确操作**

| 容器 | 首先检查的稳定性边界 |
| --- | --- |
| vector | 重分配全部失效；无重分配的插入/删除另有位置相关规则 |
| array | 无结构性增长；对象寿命与元素赋值的语义仍需区分 |
| deque | 分段随机访问；端点/中间操作对 iterator 与 reference 的影响不同 |
| list | 通常保持未删除节点，splice 须满足 allocator 等前提 |
| map / set | 插入不使已有迭代器/引用失效；擦除使被删元素失效 |
| unordered_map | rehash 使 iterator 失效，但不使元素 pointer/reference 失效 |
| flat_map | 默认平面序列；插入/擦除及底层容器决定移动与失效 |

此表不是完整操作合同，不能据它省略对 swap、move、allocator 等具体情形的检查。

<a id="g4-part-iv"></a>

### 2.3 `std::array`

**17. `std::array<T, N>`**

当 element count 是：compile-time fixed

优先考虑：

[机制片段 · 不承诺独立编译]

```cpp
std::array<T, N>
```

而不是裸：

[机制片段 · 不承诺独立编译]

```cpp
T[N]
```

它提供正常 container interface：

[机制片段 · 不承诺独立编译]

```cpp
size()
begin()
end()
data()
```

并保持：inline contiguous storage。

**18. `array` 的 Representation**

[机制片段 · 不承诺独立编译]

```cpp
std::array<float, 16> values{}; // 本例初始化元素，避免读取不确定值。
```

逻辑上接近：

```text
object itself
┌───────────────────────┐
│ 16 inline float values│
└───────────────────────┘
```

没有单独 heap allocation。

因此非常适合：

```text
small fixed buffers
SIMD blocks
protocol headers
compile-time tables
```

**19. `array<T, N>` 的 N 个 T 都是活对象**

这一点 G5 已经强调过：

[机制片段 · 不承诺独立编译]

```cpp
std::array<T, 1024>
```

不是：capacity 1024 的 raw storage。

而是：1024 个正常 `T` objects。

如果需要：

```text
capacity N
but size runtime
```

真正的 fixed-capacity vector 需要：

```text
raw storage
+
manual lifetime management
```

是另一种 abstraction。

<a id="g4-part-v"></a>

### 2.4 `std::deque`

**20. `deque` 是 Segmented Sequence**

概念不是：

```text
one contiguous block
```

而更接近：

```text
[block][block][block][block]
```

加一层 indexing structure。

因此：

[机制片段 · 不承诺独立编译]

```cpp
deque[i]
```

仍然支持 random access，

但：

[机制片段 · 不承诺独立编译]

```cpp
&deque[i + 1] == &deque[i] + 1
```

不能作为一般连续存储假设。

**21. `deque` 什么时候有价值？**

典型：

```text
frequent push_front
frequent push_back
random access required
don't need contiguous storage
```

相比 vector：

```text
front insertion
```

不需要整体移动全部 elements。

**22. `deque` 的代价**

相比 vector：

```text
segmented
extra indirection
poorer linear locality
not representable as one span
```

所以对于：

```text
high-throughput contiguous numeric processing
```

通常仍然优先 vector。

<a id="g4-part-vi"></a>

### 2.5 `list` / `forward_list`

**23. Linked List 的抽象优势**

[机制片段 · 不承诺独立编译]

```cpp
std::list<T>
```

典型能力：

```text
stable node addresses
O(1) insertion/erase with known iterator
splice
```

这些是真正优势。

**24. 但 “O(1) Insert” 很容易骗人**

对 vector：

```text
insert middle
→ O(N)
```

对 list：

```text
known iterator insert
→ O(1)
```

于是有人直接得出：list 更快。

但寻找 insertion point 可能仍然：

```text
O(N)
```

而 node traversal：

```text
pointer chasing
cache misses
allocation
```

实际成本很高。

所以：Big-O 必须和 G6 machine model 一起分析。

**25. 什么时候应该真的考虑 `list`？**

当下面要求是真实核心需求：

```text
node address/reference stability
frequent splice between lists
frequent insert/erase at known positions
large/non-movable nodes where relocation is unacceptable
```

而不是：“听说中间删除是 O(1)。”

**26. `forward_list`**

单链：

```text
Node → Node → Node
```

比 `list` 少一个 backward pointer。

适合非常特定的：

```text
forward-only intrusive-ish topology
```

但普通 application/system data 默认通常仍不应该优先 linked list。

<a id="g4-part-vii"></a>

<a id="g4-section-3"></a>

## 3. 连续、多维与字符视图

### 3.1 `std::span`

**27. `std::span<T>` 是 G4 最重要的 API 类型之一**

`span` 表示：**non-owning contiguous sequence view**

例如：

[机制片段 · 不承诺独立编译]

```cpp
void decode(std::span<const std::byte> input);
```

它表达：

```text
borrow
+
contiguous
+
extent available
```

比：

[机制片段 · 不承诺独立编译]

```cpp
void decode(
    const std::byte* data,
    std::size_t size);
```

更完整。

**28. Span 不拥有数据**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<int> values{1, 2, 3};

std::span<const int> view = values;
```

Ownership：

```text
vector
→ owns ints

span
→ borrows ints
```

如果：

```text
vector dies
```

span：dangling。

**29. Span 不延长 Lifetime**

访问时必须满足：

```text
每次通过 view 使用元素
→ 目标元素仍在生命周期内
→ 没有使该访问路径失效的操作
```

例如：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const int> get_view() {
    std::vector<int> values{1, 2, 3};
    return values;
}
```

错误。

返回后：

```text
values destroyed
↓
span dangling
```

**30. `span` 也可能因 Reallocation 失效**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<int> values{1, 2, 3};
std::span<const int> view = values;

values.push_back(4);  // may reallocate

use(view);
```

如果 reallocation：span 指向旧 storage。

所以：

owner 活着与地址未移动都只是必要审查项，还要检查元素生命周期、范围及具体操作的失效规则；不能把这句话当作完整安全公式。

**31. `span<T>` vs `span<const T>`**

[机制片段 · 不承诺独立编译]

```cpp
std::span<T>
```

表示：mutable borrowed elements。

[机制片段 · 不承诺独立编译]

```cpp
std::span<const T>
```

表示：read-only access path。

注意：

```text
const span
```

和：

```text
span<const T>
```

也不是一个概念。

通常 API 输入：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const T>
```

非常自然。

**32. Static Extent**

[机制片段 · 不承诺独立编译]

```cpp
std::span<const std::byte, 8>
```

表示：extent = 8 是类型的一部分。

相比：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const std::byte>
```

动态 extent。

固定协议字段：

[机制片段 · 不承诺独立编译]

```cpp
std::uint64_t decode(
    std::span<const std::byte, 8> bytes);
```

可以把：“必须恰好 8 bytes”

编码进 API type。

从运行时范围构造静态 extent span 时，调用者仍须满足相应长度前置条件；类型中的 8 不是对任意输入自动执行的长度验证。外部输入应先验证，再建立这种受约束的 view。

**33. `span` 是非常好的 Representation Boundary**

假设内部：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<float> values_;
```

对算法不必暴露：

```text
vector ownership/capacity API
```

可以暴露：

[机制片段 · 不承诺独立编译]

```cpp
[[nodiscard]]
std::span<const float> values() const noexcept {
    return values_;
}
```

算法得到的是：

```text
contiguous read-only range
```

而不是：修改 owner representation 的能力。

<a id="g4-part-viii"></a>

### 3.2 `std::string_view`

**34. `string_view` 是字符领域的 Borrowed View**

[机制片段 · 不承诺独立编译]

```cpp
void parse(std::string_view input);
```

表示：

```text
character sequence
+
length
+
no ownership
```

非常适合：

```text
parsing
lookup
read-only string parameters
```

**35. 最危险的 `string_view`**

[机制片段 · 不承诺独立编译]

```cpp
std::string_view make_name() {
    return std::string{"vehicle"};
}
```

编译可能成功。

但 temporary string：

```text
destroyed
```

返回 view：dangling。

因此：

```text
string_view
```

和：

```text
span
```

一样首先是：lifetime contract。

**36. `string_view` 不保证 Null Termination**

[机制片段 · 不承诺独立编译]

```cpp
std::string_view view;
```

只表示：

```text
pointer + length
```

不能默认：

[机制片段 · 不承诺独立编译]

```cpp
C_api(view.data());
```

安全。

因为底层 range 可能：

```text
not NUL terminated
```

或者 view 只是原字符串子区间。

与 C API 交互时必须明确 contract。

这会在 G8 再出现。

<a id="g4-part-ix"></a>

### 3.3 `std::mdspan` — C++23 多维 View

**37. `mdspan` 是 G4 与高性能计算的重要连接**

C++23：

[机制片段 · 不承诺独立编译]

```cpp
std::mdspan
```

表达：对多维数据的 non-owning structured view。

例如概念：

[机制片段 · 不承诺独立编译]

```cpp
std::mdspan<float,
            std::extents<std::size_t,
                         std::dynamic_extent,
                         3>>
    points;
```

表示：

```text
N × 3
```

二维 logical view。

**38. 默认 mdspan 不负责底层元素所有权**

使用默认 accessor/data handle 的常见模型是（自定义 accessor 可能改变句柄与资源管理语义）：

```text
owner
→ vector / array / external buffer

mdspan
→ multidimensional indexing view
```

这让：

```text
storage policy
```

与：

```text
logical multidimensional indexing
```

解耦。

**39. Layout Policy**

`mdspan` 的重要价值是可以表达：

```text
layout_right
layout_left
layout_stride
```

也就是说：logical `(i, j)` 如何映射到 linear storage offset。

这直接连接 G6：

```text
row-major
column-major
strided layout
```

和 cache locality。

**40. `mdspan` 的系统意义**

以前函数可能：

[机制片段 · 不承诺独立编译]

```cpp
void process(
    const float* data,
    std::size_t rows,
    std::size_t cols,
    std::size_t stride);
```

现在可以将：shape + layout mapping + element access

打包成 view abstraction。

同时不要求算法：拥有数据。

这非常适合：

```text
robotics
linear algebra
image processing
tensor kernels
sensor matrices
```

<a id="g4-part-x"></a>

<a id="g4-section-4"></a>

## 4. 迭代器、算法与 Ranges

### 4.1 Iterator：不是“高级 Pointer”

**41. Iterator 的核心是 Traversal Capability**

最简单：

```text
input iterator
forward iterator
bidirectional iterator
random-access iterator
contiguous iterator
```

能力逐渐增强。

不要首先背继承层级。

应该理解：**Container topology 决定 iterator 能力。**

**42. Examples**

```text
forward_list
→ forward

list
→ bidirectional

deque
→ random access

vector
→ contiguous
```

所以：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort(range);
```

需要：random-access sortable range。

因此不能：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort(std::list<int>);
```

这不是标准库“故意刁难”。

而是：sort algorithm 的操作需求与 linked-list iterator capability 不匹配。

`std::list` 有自己的：

[机制片段 · 不承诺独立编译]

```cpp
list.sort();
```

可以利用 node relinking。

**43. Contiguous Iterator**

`vector` iterator 具有：contiguous semantics。

所以可以和：

```text
pointer
span
C APIs
SIMD
```

自然衔接。

这是 vector 与 deque 虽然都 random access，却存在的一个重要能力差异。

<a id="g4-part-xi"></a>

### 4.2 Algorithm First

**44. 优先表达“我要做什么”**

比如寻找：

[机制片段 · 不承诺独立编译]

```cpp
auto it = std::ranges::find(values, target);
```

而不是首先：

[机制片段 · 不承诺独立编译]

```cpp
for (...) {
    if (...) {
        ...
    }
}
```

原因不是：loop 不好。

而是：

```text
find
```

直接表达 semantic intent。

这有利于：

```text
review
genericity
correctness
implementation optimization
```

**45. 但不要迷信“算法永远优于 Loop”**

如果 hot loop 需要：

```text
one traversal
simultaneously:
min
max
sum
valid count
error flags
```

将其拆成：

```text
min_element
max_element
accumulate
count_if
```

意味着多次 traversal。

这时一个 fused loop：

[机制片段 · 不承诺独立编译]

```cpp
for (const Sample& sample : samples) {
    ...
}
```

可能更合理。

因此原则：**Prefer algorithms when they express the operation naturally; fuse work when one-pass semantics/performance matters.**

**46. Ranges Algorithms**

传统：

[机制片段 · 不承诺独立编译]

```cpp
std::sort(values.begin(), values.end());
```

现代 C++：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort(values);
```

优点：

```text
less iterator boilerplate
concept-constrained API
projection support
range-based composition
```

**47. Projection**

非常好用：

[机制片段 · 不承诺独立编译]

```cpp
struct Signal {
    std::uint32_t id;
    float value;
};

std::ranges::sort(
    signals,
    {},
    &Signal::id);
```

而不是：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort(
    signals,
    [](const Signal& a, const Signal& b) {
        return a.id < b.id;
    });
```

Projection 表达：“使用这个字段作为排序 key。”

语义更清楚。

**48. `lower_bound`**

如果数据已经按 `id` 排序：

[机制片段 · 不承诺独立编译]

```cpp
auto it = std::ranges::lower_bound(
    signals,
    target_id,
    {},
    &Signal::id);
```

复杂度：

```text
O(log N)
comparisons
```

但对于 random-access contiguous storage，

memory behavior通常也很好。

**49. Sorted Vector 是一种非常强的 Associative Representation**

如果：

```text
read-heavy
updates infrequent
```

可以：

```text
vector
↓
sort once
↓
binary search many times
```

而不是直接：

```text
map
unordered_map
```

因为：

```text
contiguous iteration
low metadata
cache locality
```

经常非常优秀。

这就是：**Flat Representation**

<a id="g4-part-xii"></a>

### 4.3 Ranges Views

**50. View 是 Lazy Transformation**

例如：

[机制片段 · 不承诺独立编译]

```cpp
auto positive =
    values |
    std::views::filter([](int value) {
        return value > 0;
    });
```

`positive` 通常不是：一个新 vector。

它是：对原 range 的 lazy traversal adapter。

**51. Lazy 意味着什么？**

[机制片段 · 不承诺独立编译]

```cpp
auto view =
    values |
    std::views::transform(f);
```

通常：

```text
没有立即 transform 所有 elements
```

而是 iterator traversal 时：

```text
read element
↓
apply f
↓
produce transformed value/reference
```

因此：

```text
temporary allocation
```

通常可以避免。

**52. View 是否拥有数据，要看具体类型**

**问题：**下面两种写法都得到 view，能否认为都只借用？

[机制片段 · 不承诺独立编译]

```cpp
auto borrowed = std::views::all(values);                    // values 为 vector 左值
auto owned = std::views::all(std::vector<int>{1, 2, 3});     // vector 右值
```

前者通常为 ref_view，依赖外部 values；后者在 C++23 中可形成 owning_view，把 vector 持有在内部。view 是带特定语义/复杂度要求的 range，不是“不拥有”的同义词，也不保证每一种 view 都执行延迟转换。

**边界：**即使底层 range 被拥有，filter/transform 中按引用捕获的其他对象仍可能悬挂。借用型 view 也仍受底层容器失效规则影响；borrowed_range 不能替你证明底层元素活着。[N4950：Ranges](https://timsong-cpp.github.io/cppwp/n4950/ranges#range.all)

**53. Range Pipeline**

例如：

[机制片段 · 不承诺独立编译]

```cpp
auto ids =
    signals |
    std::views::filter([](const Signal& signal) {
        return signal.value > 0.0F;
    }) |
    std::views::transform(&Signal::id);
```

这表达：

```text
signals
↓
only positive values
↓
extract IDs
```

非常接近数据流语义。

**54. Range Pipeline 不等于自动最快**

Lazy pipeline 可能：

```text
inline completely
```

得到非常好机器码。

也可能因为：

```text
complex predicates
poor vectorization
multiple abstraction layers
```

产生不同 codegen。

因此 G6 原则保持：优先写清晰 abstraction，然后 profile/assembly 验证 hot path。

**55. View 的 Lifetime Trap**

尤其不要随意：

```text
store a view
```

长期超过其 source owner。

例如 class member：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const T> view_;
```

意味着 class 的 lifetime invariant必须包含：被 view_ 借用的 owner 永远活得更久，而且不会使 storage invalid。

这是很强的 contract。

<a id="g4-part-xiii"></a>

### 4.4 Borrowed Range

**56. 为什么 Ranges 要有 `borrowed_range`？**

假设：

[机制片段 · 不承诺独立编译]

```cpp
auto it =
    std::ranges::find(
        std::vector<int>{1, 2, 3},
        2);
```

temporary vector 在 full-expression 后销毁。

如果算法直接返回：

```text
iterator into temporary vector
```

就会立即 dangling。

Ranges framework 会通过：

```text
borrowed_range
```

等机制表达：iterator 的有效性是否不依赖 range 对象本身的生命周期。

这不保证底层元素无限存活。例如 span 满足 borrowed_range，但它指向的 vector 已销毁时，iterator 仍会悬挂。

**57. `std::ranges::dangling`**

对于不安全的 rvalue range：

某些 range algorithm 的返回类型会成为：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::dangling
```

而不是给你一个立即悬空的 iterator。

这是一种非常漂亮的：**Lifetime-aware generic API design**

与 G1/G5 完全呼应。

<a id="g4-part-xiv"></a>

<a id="g4-section-5"></a>

## 5. 关联表示与容器选择

### 5.1 `std::map` / `std::set`

**58. Ordered Associative Containers**

[机制片段 · 不承诺独立编译]

```cpp
std::map<K, V>
std::set<K>
```

提供：

```text
ordered keys
O(log N) lookup/insertion/erase
sorted iteration
range queries
stable node-like element addresses/iterators across ordinary insertion
```

实现通常基于 balanced tree，但标准 contract 并不要求你依赖具体树类型。

**59. `map` 的真正优势**

不是：O(log N) 听起来不错。

而是：

```text
ordering is part of required semantics
```

例如：

```text
lower_bound
upper_bound
range query
ordered traversal
```

以及 node stability 可能有价值。

**60. `operator[]` 的语义**

[机制片段 · 不承诺独立编译]

```cpp
map[key]
```

如果 key 不存在：会插入默认构造的 mapped value。

所以只想查询时不要机械：

[机制片段 · 不承诺独立编译]

```cpp
if (map[key] == ...)
```

可能无意修改 container。

查询优先：

[机制片段 · 不承诺独立编译]

```cpp
map.find(key)
```

或者 C++20：

[机制片段 · 不承诺独立编译]

```cpp
map.contains(key)
```

**61. `try_emplace`**

例如：

[机制片段 · 不承诺独立编译]

```cpp
map.try_emplace(
    key,
    constructor_args...);
```

如果 key 已存在：不需要构造 mapped object。

但调用的参数表达式仍会先求值；`try_emplace(key, expensive())` 不会因为 key 已存在就自动跳过 expensive()。

对于昂贵 value：

```text
lookup + conditional construction
```

很自然。

<a id="g4-part-xv"></a>

### 5.2 `std::unordered_map`

**62. Hash Table**

[机制片段 · 不承诺独立编译]

```cpp
std::unordered_map<K, V>
```

通常由：

```text
hash
bucket selection
collision handling
```

组成。

平均 lookup 常描述为：

```text
O(1)
```

但这绝不意味着：“一定比 map 快”。

**63. Hash Lookup 的真实 Cost**

至少包括：

```text
hash computation
bucket access
collision handling
pointer/metadata traversal
key comparison
```

如果 key 是：

[机制片段 · 不承诺独立编译]

```cpp
std::string
```

hash 本身可能扫描整条 string。

所以：

```text
O(1)
```

指 container size N 的平均渐进复杂度，

不是：one CPU instruction。

**64. Load Factor**

[机制片段 · 不承诺独立编译]

```cpp
map.load_factor();
map.max_load_factor();
```

粗略：

```text
elements / buckets
```

load factor 太高：

```text
collisions ↑
```

太低：

```text
bucket memory ↑
cache footprint ↑
```

**65. `reserve`**

如果预先知道约有：

```text
N entries
```

可以：

[机制片段 · 不承诺独立编译]

```cpp
table.reserve(N);
```

减少未来：

```text
rehash
```

次数。

这和 vector reserve 是同一思想：使用 domain knowledge 提前稳定 storage topology。

**66. Rehash Invalidation**

Rehash 会：重新组织 buckets。

因此：

```text
iterators invalidated
```

但对既有 elements 的：

```text
references/pointers
```

通常不会仅因为 rehash 而失效。

这和 vector reallocation 完全不同。

仍然要对具体 erase 等 operation 单独分析。

**67. `unordered_map` 最大的误区**

> “Lookup 是 O(1)，所以这是最快字典。”

如果：

```text
N = 20
```

一个线性 scan：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::find(...)
```

都可能更快。

原因：

```text
contiguous memory
simple comparisons
no hashing
no node chasing
```

因此：**Small N changes the game.**

<a id="g4-part-xvi"></a>

### 5.3 `std::flat_map` / `std::flat_set` — C++23

本 主题 的连续存储分析以默认底层容器为前提。flat_map 默认使用分别保存 key 和 mapped value 的 vector，不是固定的 vector<pair>；替换底层序列后，要重新检查连续性、代理引用与失效规则。[N4950：flat.map.overview](https://timsong-cpp.github.io/cppwp/n4950/flat.map.overview)

**68. Flat Associative Containers**

C++23：

[机制片段 · 不承诺独立编译]

```cpp
std::flat_map
std::flat_set
```

提供 associative-container-style interface，

但 representation 更接近：sorted contiguous sequence(s)

而不是 node tree。

**69. Flat Map 的 Cost Model**

Lookup：

```text
O(log N)
```

通常通过 binary search。

Iteration：

```text
contiguous / dense underlying storage
```

非常 cache-friendly。

但 insert/erase：

```text
O(N)
```

因为 elements 可能需要移动。

因此特别适合：

```text
read-heavy
build once
query many
moderate size
```

**70. `flat_map` vs Sorted Vector**

如果只是内部实现：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Entry>
```

然后：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort
std::ranges::lower_bound
```

已经非常好。

`flat_map` 的价值：提供更明确 associative semantics/API。

选择取决于：

```text
representation control
API expectations
mutation pattern
```

**71. Dense Integer Key：别忘了 Array / Vector**

假设 key：

```text
0 <= id < 64
```

不要第一反应：

[机制片段 · 不承诺独立编译]

```cpp
std::unordered_map<int, Entry>
```

直接：

[机制片段 · 不承诺独立编译]

```cpp
std::array<Entry, 64>
```

或：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Entry>
```

可能更合理。

Lookup：

[机制片段 · 不承诺独立编译]

```cpp
entries[id]
```

无需：

```text
hash
tree
node
```

这是一种非常重要的：**Exploit Domain Constraints**

<a id="g4-part-xvii"></a>

### 5.4 Container Selection

**72. 不要按 Big-O 选 Container**

先问 semantics：

```text
Do I need ordering?
Do I need contiguous storage?
Do I need stable addresses?
Do I insert in middle often?
Are mutations rare?
Is key domain dense?
Is N small?
```

之后再看 performance。

**73. 一个实用选择矩阵**

| Requirement                    | 默认候选                     |
| ------------------------------ | ---------------------------- |
| 动态拥有连续 values            | `vector`                     |
| 固定编译期数量                 | `array`                      |
| 两端高频增长                   | `deque`                      |
| 需要稳定 node / splice         | `list`                       |
| ordered associative            | `map`                        |
| average hash lookup            | `unordered_map`              |
| read-heavy sorted associative  | `flat_map` / sorted `vector` |
| dense integer ID               | `array` / `vector`           |
| borrowed contiguous input      | `span`                       |
| borrowed string input          | `string_view`                |
| multidimensional borrowed data | `mdspan`                     |

默认不是定论。

是：starting point。

<a id="g4-part-xviii"></a>

<a id="g4-section-6"></a>

## 6. 状态建模

### 6.1 `optional` / `variant` / `expected`

**74. STL 也提供“状态建模”类型**

容器之外，现代标准库的重要抽象还有：

[机制片段 · 不承诺独立编译]

```cpp
std::optional<T>
std::variant<...>
std::expected<T, E>
```

这些不是主要 storage containers，

但对系统 API 非常重要。

**75. `optional<T>`**

表达：

```text
T exists
or
no T
```

例如：

[机制片段 · 不承诺独立编译]

```cpp
std::optional<Job> try_pop();
```

比：

[机制片段 · 不承诺独立编译]

```cpp
bool try_pop(Job& out);
```

有时更 value-oriented。

但如果 `T` 很大：返回 optional<T> 仍然要分析 representation/move cost。

**76. `variant`**

[机制片段 · 不承诺独立编译]

```cpp
using Command =
    std::variant<
        Start,
        Stop,
        Update>;
```

表示：正常有值时持有若干候选之一；部分抛异常的类型改变操作可能使 variant 进入 valueless_by_exception，不能无条件假定一直有值。

比：

```text
type enum
+
void*
+
manual union
```

更安全。

非常适合：

```text
message passing
state-machine commands
protocol AST
```

**77. `std::visit`**

[机制片段 · 不承诺独立编译]

```cpp
std::visit(
    [](auto&& command) {
        handle(command);
    },
    cmd);
```

配合 variant实现：closed set static sum type dispatch。

它不是 virtual inheritance hierarchy。

C++ compiler可以基于 alternative set 静态生成 dispatch machinery。

**78. `expected<T, E>` — C++23**

表示：

```text
success: T
or
failure: E
```

例如：

[机制片段 · 不承诺独立编译]

```cpp
std::expected<Message, ParseError>
parse(std::span<const std::byte> input);
```

比：

```text
sentinel
global errno
out parameter
```

更明确。

**79. `expected` 不会自动带来 Strong Exception Safety**

如果函数内部：

```text
modify shared state
↓
later return unexpected(error)
```

已经发生的 side effects：不会因为返回 expected 自动 rollback。

所以：

```text
error representation
```

和：

```text
state transaction guarantee
```

仍然是不同问题。

G2 的 exception-safety model依旧适用。

<a id="g4-part-xix"></a>

<a id="g4-section-7"></a>

## 7. SignalBatch：完整组件实验

### 7.1 Practical SignalBatch

<a id="g4-batch"></a>

**80. G4-L1：从拥有一批数据到可查询的只读组件**

**需求：**构建时取得一批采样，之后多次读取；按 signal_id 查询，重复 ID 返回输入中第一条；空批次没有统计值。数据只允许有限 float，避免把 NaN 的业务规则藏在 min/max 里。

为使查询不依赖调用者“记得先排序”，本学习例在构造中排序，之后不提供 push/clear。它不是生产时序系统：单位、溢出策略、并发和吞吐目标均不在这个最小例子中。

先预测空输入、缺失 ID、小于/大于所有 ID、重复 ID 各会得到什么。下面是完整运行例：

<!-- g-lab {"id":"G4-L1","mode":"run","stdout":"sorted; first-duplicate; misses; stats; empty; finite-only\n"} -->
[完整实验 · G4-L1 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <optional>
#include <span>
#include <stdexcept>
#include <utility>
#include <vector>

struct SignalSample {
    std::uint64_t timestamp_ns{};
    std::uint32_t signal_id{};
    float value{};
    bool operator==(const SignalSample&) const = default;
};

struct Stats {
    std::size_t count{};
    float min{}, max{};
    double sum{};
};

class SignalBatch {
public:
    explicit SignalBatch(std::vector<SignalSample> samples)
        : samples_(std::move(samples)) {
        for (const auto& sample : samples_) {
            if (!std::isfinite(sample.value))
                throw std::invalid_argument("finite sample required");
        }
        std::ranges::stable_sort(samples_, {}, &SignalSample::signal_id);
    }

    std::span<const SignalSample> samples() const & noexcept {
        return samples_;
    }
    std::span<const SignalSample> samples() const && = delete;

    std::optional<SignalSample> find(std::uint32_t id) const {
        const auto it = std::ranges::lower_bound(
            samples_, id, {}, &SignalSample::signal_id);
        if (it == samples_.end() || it->signal_id != id)
            return std::nullopt;
        return *it;
    }

    std::optional<Stats> stats() const {
        if (samples_.empty()) return std::nullopt;
        Stats result{0, samples_.front().value, samples_.front().value, 0};
        for (const auto& sample : samples_) {
            ++result.count;
            result.min = std::min(result.min, sample.value);
            result.max = std::max(result.max, sample.value);
            result.sum += sample.value;
        }
        return result;
    }

private:
    std::vector<SignalSample> samples_;
};

int main() {
    const SignalBatch batch{{{20, 4, 2}, {10, 1, 1}, {30, 4, 3}}};
    const SignalSample expected[]{{10, 1, 1}, {20, 4, 2}, {30, 4, 3}};
    if (!std::ranges::equal(batch.samples(), expected)) return 1;
    const auto hit = batch.find(4);
    if (!hit || *hit != expected[1]) return 2;
    if (batch.find(0) || batch.find(2) || batch.find(9)) return 3;
    const auto stats = batch.stats();
    if (!stats || stats->count != 3 || stats->min != 1 ||
        stats->max != 3 || stats->sum != 6) return 4;
    const SignalBatch empty{std::vector<SignalSample>{}};
    if (!empty.samples().empty() || empty.find(1) || empty.stats()) return 5;
    bool rejected = false;
    try {
        SignalBatch invalid{{{0, 1, std::numeric_limits<float>::infinity()}}};
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    if (!rejected) return 6;
    std::cout << "sorted; first-duplicate; misses; stats; empty; finite-only\n";
}
```

**81. 为什么返回 span，而不是 const vector&？**

消费者只需“连续只读元素”，不需容量和 allocator API。span 提供较窄的接口，但仍有连续存储承诺，不能透明换成 list。它不保活；本例禁止直接从右值 batch 提取 span，也仍要求使用期间 owner 未销毁、未被移动/赋值、未通过外部别名改变元素。

**82. 为什么排序属于构建不变量？**

如果先发布 span，再允许任意 push，排序和借用有效性都可能破坏。此例在构造中用 stable_sort，保证重复 key 保留输入先后顺序。不是所有业务都该排序；时序读取和高频追加需要另一份明确接口合同。

**83. lower_bound 不等于“找到了”**

必须先满足与比较器/投影一致的分区前提，本例用排序建立它；再检查 end 与 key 相等。测试分别覆盖低端缺失、间隙缺失和高端缺失。只测一个命中会漏掉“返回第一个不小于目标的错误记录”。

**84. 重复记录与分组**

相同 ID 排在一起便于 equal_range 分组。本例 find 明确返回第一条的**值副本**；完整范围比较保留 timestamp、ID、value 的归属，不能只检查排序后的 ID 数量。更多聚合策略由需求定义，不暗中去重。

**85. 统计、预测与边界**

一次 loop 同时计算 count/min/max/sum，是有明确理由的手工融合；空批次返回 nullopt，而不是制造一个伪造的最小值。

实验使用可精确表示的小数值比较 sum，不把它推广成任意浮点求和的精确相等方案。只检查了一种非有限输入；没有注入分配失败或证明所有浮点误差界。改变条件练习：允许构建后追加会破坏哪些合同？应重新排序、失效旧 view，还是改用分阶段 builder？先说明选择，再写代码。

<a id="g4-part-xx"></a>

<a id="g4-section-8"></a>

## 8. 数据修改与 API 边界

### 8.1 Erase / Filter

**86. 现代 Erase**

以前典型：

[机制片段 · 不承诺独立编译]

```cpp
values.erase(
    std::remove_if(
        values.begin(),
        values.end(),
        pred),
    values.end());
```

现代：

[机制片段 · 不承诺独立编译]

```cpp
std::erase_if(values, pred);
```

表达更清楚。

**87. Filter View vs Physical Removal**

[机制片段 · 不承诺独立编译]

```cpp
auto valid =
    samples |
    std::views::filter(is_valid);
```

只是：logical filtered view。

底层 samples 仍然全部存在。

而：

[机制片段 · 不承诺独立编译]

```cpp
std::erase_if(samples, is_invalid);
```

真正：修改 owner、结束 object lifetime、移动后续 elements。

这两个 semantics 完全不同。

**88. Lazy Filter 的 Cost**

filter view 遍历时每个 element：

```text
predicate
↓
possibly skip
```

如果同一个 filtered subset 被重复处理很多次：每次都重新 predicate。

有时一次 materialize：

```text
filter once
↓
new compact vector
↓
many passes
```

更划算。

再次是：

```text
transformation cost
vs
reuse count
```

<a id="g4-part-xxi"></a>

### 8.2 API Design

**89. Owner API**

如果函数：接管一份 vector 所有权

可以：

[机制片段 · 不承诺独立编译]

```cpp
void consume(std::vector<Record> records);
```

by-value 明确：ownership enters function。

Caller：

[机制片段 · 不承诺独立编译]

```cpp
consume(std::move(records));
```

**90. Borrowed Read-only**

[机制片段 · 不承诺独立编译]

```cpp
void process(
    std::span<const Record> records);
```

表达：

```text
borrow
read-only
contiguous
```

**91. Borrowed Mutable**

[机制片段 · 不承诺独立编译]

```cpp
void normalize(
    std::span<float> values);
```

表达：caller owns；function 可修改 elements。

**92. 不要滥用 `const vector&`**

[机制片段 · 不承诺独立编译]

```cpp
void process(
    const std::vector<Record>& records);
```

如果算法真正依赖：

```text
contiguous sequence
```

则：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const Record>
```

通常更 general。

这样 caller 可以传：

```text
vector
array
C array
subspan
```

**93. 但也不要机械全部换 Span**

如果 API 的 semantic contract 就是：“这是一个 vector owner，我需要 capacity、growth、push_back。”

那就应该：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<T>&
```

或者更好的 owner abstraction。

例如：

[机制片段 · 不承诺独立编译]

```cpp
void fill(std::vector<T>& output);
```

如果目的明确是：重用 caller-owned dynamic storage。

这是合法设计。

关键是：参数类型应该表达所需 capability。

<a id="g4-part-xxii"></a>

### 8.3 Return Values

**94. 返回 `vector` 很正常**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Record> load_records();
```

现代 C++：

```text
copy elision
move semantics
```

使：return container by value

成为非常自然的 ownership transfer。

不要为了“怕 copy”机械：

[机制片段 · 不承诺独立编译]

```cpp
void load_records(
    std::vector<Record>& out);
```

除非：

```text
storage reuse
allocation control
bounded environment
```

确实是 API requirement。

**95. 不要返回指向 Local Container 的 View**

错误：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const Record> load() {
    std::vector<Record> result;
    // ...
    return result;
}
```

返回 owner：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Record> load();
```

才正确。

这是：**Owner must cross boundary if data must outlive the function.**

<a id="g4-part-xxiii"></a>

### 8.4 Container Choice 与 ABI

**96. 不要轻易把 STL Container 放进稳定 Binary ABI**

例如 public dynamic library C++ ABI：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Record>
get_records();
```

会把：

```text
stdlib implementation
allocator
layout
exception ABI
template instantiation
```

带进 binary boundary。

这不是说：永远不能。

而是：container-rich C++ API 会形成很强 ABI coupling。

G8 会正式展开。

<a id="g4-part-xxiv"></a>

### 8.5 Container Choice 与 Concurrency

**97. STL Container 本身通常不是“自动线程安全”**

例如：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<int> values;
```

多个 threads 只读：在正确 publication 后很自然。

一个 thread修改、另一个同时读取：需要同步。

不能因为：

```text
vector implementation internally complicated
```

就认为标准库会自动锁。

**98. Different Elements 也要分析 Container Mutation**

例如：

```text
Thread A modifies values[0]
Thread B modifies values[1]
```

对于普通 `vector<int>`，如果 storage 本身不发生结构性 mutation，两个不同 elements 是不同 memory locations，可以设计成合法并发访问。

但：

```text
false sharing
```

仍可能存在。

而：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<bool>
```

是特殊 bit-packed representation。

不同 logical bool elements 可能共享同一个 underlying word。

所以不要把普通 vector element reasoning直接套给：

[机制片段 · 不承诺独立编译]

```cpp
vector<bool>
```

<a id="g4-part-xxv"></a>

### 8.6 `vector<bool>`

**99. 为什么它特殊？**

为了 bit packing：

```text
1 bool
≈
1 bit
```

而不是普通：

```text
sizeof(bool)
```

排列。

因此：

[机制片段 · 不承诺独立编译]

```cpp
values[i]
```

通常返回：proxy reference

而不是普通：

[机制片段 · 不承诺独立编译]

```cpp
bool&
```

**100. 什么时候可以用？**

如果真实需求就是：

```text
dense bitset-like dynamic flags
```

它并不是“禁止使用”。

但必须知道：

```text
different semantics
proxy references
bit-level operations
concurrency implications
```

如果你只是想要正常 byte-addressable flags：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<std::uint8_t>
```

可能更直观。

如果需要固定 bitset：

[机制片段 · 不承诺独立编译]

```cpp
std::bitset<N>
```

也可能更适合。

<a id="g4-part-xxvi"></a>

### 8.7 Flat vs Node-based

**101. 一个统一机器模型**

Node-based：

```text
[node] → [node] → [node]
```

优点：

```text
address stability
cheap relinking
```

代价：

```text
allocation
metadata
pointer chasing
cache/TLB
```

Flat：

```text
[value][value][value][value]
```

优点：

```text
density
iteration
prefetch
SIMD
```

代价：

```text
insert/erase moves
address instability
```

所以：**Topology is a trade-off, not ideology.**

<a id="g4-part-xxvii"></a>

<a id="g4-section-9"></a>

## 9. 内存资源与性能决策

### 9.1 STL 与 Memory Resource

**102. Containers 与 `std::pmr`**

G6 已经学习：

[机制片段 · 不承诺独立编译]

```cpp
std::pmr::vector<T>
std::pmr::string
```

重要的是：

```text
container semantic role
```

和：

```text
allocation strategy
```

是两个维度。

如果：

```text
vector is the right topology
```

但默认 heap allocation不是最适合当前 lifetime，

不应该因此放弃 vector。

可以：

```text
vector semantics
+
arena resource
```

组合。

**103. 不要让 Allocator Policy 泄漏过远**

如果 subsystem 内部需要：

[机制片段 · 不承诺独立编译]

```cpp
std::pmr::vector<Temp>
```

不代表：整个 domain model 所有 API 都需要传 `memory_resource*`。

与 G5 genericity 一样：**Policy propagation should stop at a deliberate boundary.**

<a id="g4-part-xxviii"></a>

### 9.2 STL Performance Review

**104. 看到 Container 时问什么？**

不要只问 Big-O。

至少问：

```text
Who owns elements?
Inline or indirect?
Contiguous or node-based?
How many allocations?
How many indirections?
How stable are addresses?
What invalidates views?
What is the access pattern?
How large is N?
How often mutate?
How often iterate?
```

**105. `map` vs `unordered_map` vs `flat_map` vs `vector`**

真正比较：

**表示：`map`**

- Ordered traversal：✓
- Lookup：O(log N)
- Insert：O(log N)
- Locality：poor/moderate
- Address stability：high
- Range query：excellent
- Small/read-mostly：often overkill

**表示：`unordered_map`**

- Ordered traversal：—
- Lookup：avg O(1)
- Insert：avg O(1)
- Locality：poor/moderate
- Address stability：relatively high for elements
- Range query：poor
- Small/read-mostly：often overkill

**表示：`flat_map` / sorted vector**

- Ordered traversal：✓
- Lookup：O(log N)
- Insert：O(N)
- Locality：high
- Address stability：low
- Range query：excellent
- Small/read-mostly：strong

**表示：dense vector**

- Ordered traversal：by index/order
- Lookup：O(1) dense key
- Insert：depends
- Locality：very high
- Address stability：low
- Range query：domain-specific
- Small/read-mostly：strongest if applicable

没有一个 universal winner。

<a id="g4-part-xxix"></a>

### 9.3 Practical Selection Rules

**106. Rule 1 — `vector` Until Proven Otherwise**

动态 sequence：先 vector。

换掉它需要明确 requirement。

**107. Rule 2 — Dense Key → Direct Index**

如果 key domain：

```text
small
integer
dense
```

优先：

```text
array/vector
```

而不是 hash/tree。

**108. Rule 3 — Read-heavy Lookup → Consider Sorted Flat Data**

如果：

```text
build/update rare
lookup frequent
iteration frequent
```

考虑：

```text
sorted vector
flat_map
```

**109. Rule 4 — Address Stability 必须是 Requirement 才值得付费**

不要为了：“pointer 一直有效挺方便”

就默认 node containers。

长期 identity更推荐：

```text
ID / handle
```

**110. Rule 5 — Borrow with Span/View, Own with Container**

API boundary上：

```text
ownership
→ vector/string/owner type

borrow
→ span/string_view/mdspan
```

这是非常好的默认。

<a id="g4-part-xxx"></a>

<a id="g4-section-10"></a>

## 10. 实验与观察

### 10.1 Practical Lab

**111. Lab 1 — Container Selection**

给四个 workload：

**A**

10M `float` 顺序扫描。

**B**

1000 个 key，build once，查询 10M 次，需要 sorted iteration。

**C**

动态 queue，两端 push/pop。

**D**

需要把 node 从一个 sequence O(1) splice 到另一个，地址必须稳定。

闭卷选 container，并从：

```text
semantics
+
machine topology
```

两方面解释。

**112. G4-L2 — 用实际 capacity 判断失效**

<a id="g4-labs"></a>

**问题：**reserve(4) 之后第五次 push 一定重分配吗？不一定，capacity 只保证至少为 4。以下实验先填满实际 capacity，再成功追加，确保跨过容量边界。

<!-- g-lab {"id":"G4-L2","mode":"run","stdout":"reserve-no-elements; growth; clear-keeps-capacity\n"} -->
[完整实验 · G4-L2 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <algorithm>
#include <iostream>
#include <span>
#include <vector>

int main() {
    std::vector<int> values;
    values.reserve(4);
    if (!values.empty() || values.capacity() < 4) return 1;
    const auto old_capacity = values.capacity();
    values.resize(old_capacity, 7);
    {
        std::span<const int> view{values};
        if (view.size() != old_capacity ||
            !std::ranges::all_of(view, [](int n) { return n == 7; })) return 2;
    } // 不跨过失效点保存旧 view。
    values.push_back(9);
    if (values.size() != old_capacity + 1 ||
        values.capacity() <= old_capacity || values.back() != 9) return 3;
    const auto new_capacity = values.capacity();
    values.clear();
    if (!values.empty() || values.capacity() != new_capacity) return 4;
    std::cout << "reserve-no-elements; growth; clear-keeps-capacity\n";
}
```

为什么不读取扩容前的 p 来“证明它失效”？因为那样引入 UB，结果不是可移植判据。本实验检查触发条件，失效结论来自 [N4950：vector.capacity](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity)。erase 即使没有重分配，也有自己的失效规则。

**113. G4-L3 / L4 — 借用、拥有与算法能力**

下面的完整运行例同时检查 owning_view、borrowed_range 与 list 自有排序。先预测三个 range 的元素由谁保活。

<!-- g-lab {"id":"G4-L3","mode":"run","stdout":"borrowed-view; owning-view; list-member-sort\n"} -->
[完整实验 · G4-L3 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <algorithm>
#include <iostream>
#include <list>
#include <ranges>
#include <span>
#include <type_traits>
#include <vector>

int main() {
    std::vector<int> source{3, 1, 2};
    auto borrowed = std::views::all(source);
    auto owned = std::views::all(std::vector<int>{3, 1, 2});
    static_assert(std::ranges::view<decltype(owned)>);
    static_assert(std::ranges::borrowed_range<std::span<int>>);
    static_assert(!std::ranges::borrowed_range<std::vector<int>>);
    static_assert(std::is_same_v<
        decltype(std::ranges::find(std::vector<int>{1}, 1)),
        std::ranges::dangling>);
    source[0] = 9;
    const int borrowed_expected[]{9, 1, 2};
    const int owned_expected[]{3, 1, 2};
    if (!std::ranges::equal(borrowed, borrowed_expected)) return 1;
    if (!std::ranges::equal(owned, owned_expected)) return 2;
    std::list<int> nodes{3, 1, 2};
    nodes.sort();
    const int sorted[]{1, 2, 3};
    if (!std::ranges::equal(nodes, sorted)) return 3;
    std::cout << "borrowed-view; owning-view; list-member-sort\n";
}
```

**原因：**view 不排除拥有，borrowed_range 不保证底层元素永远活着。list 不能满足 ranges::sort 所需的随机访问能力，但有适合节点结构的成员 sort。

以下是**编译失败反例**，须出现 sort 的约束不满足诊断：

<!-- g-lab {"id":"G4-L4","mode":"compile_fail","diagnostic":"(?:no matching function|constraints not satisfied)[\\s\\S]*(?:sort|random_access)"} -->
[反例 · 编译失败 · G4-L4 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <algorithm>
#include <list>
int main() {
    std::list<int> values{3, 1, 2};
    std::ranges::sort(values);
}
```

**自主练习（未计入本批运行结果）：**写 `std::optional<double> average(std::span<const float>)`，规定空范围返回 nullopt；让 vector、array、C 数组和连续子范围调用它。指出借用不保活，列出浮点非有限值与求和误差策略，不把“加个 span”当作全部安全合同。

**114. Lab 4 — Sorted Vector vs Hash**

构造：

```text
N = 16
64
1024
1M
```

比较：

```text
linear vector lookup
sorted vector + lower_bound
unordered_map
map
```

不要只测 lookup。

还测：

```text
build cost
memory footprint
iteration
```

本练习未在本批测量。先校验四种表示的查询结果相同，再分开计时构建、命中/缺失查找和遍历；固定输入种子、优化选项和工具链，重复运行并保留分布。memory footprint 必须说明测的是元素字节、分配量还是进程 RSS，不能混为一项。不要在看到结果前指定赢家。

这个实验用于检验：“O(1) 总比 O(logN) 快”

这种直觉。

**115. Lab 5 — View Lifetime**

逐个判断：

[机制片段 · 不承诺独立编译]

```cpp
std::string text = "hello";
std::string_view a = text;
```

合法。

然后：

[机制片段 · 不承诺独立编译]

```cpp
std::string_view b = std::string{"hello"};
```

为什么危险？

再：

[机制片段 · 不承诺独立编译]

```cpp
text += very_large_suffix;
```

之后 `a` 是否仍然可靠？

根据：string storage invalidation

分析。

**116. Lab 6 — Range Projection**

定义：

[机制片段 · 不承诺独立编译]

```cpp
struct Record {
    std::uint32_t id;
    std::uint64_t timestamp;
};
```

要求：

```text
sort by timestamp
find by id
```

用：

[机制片段 · 不承诺独立编译]

```cpp
std::ranges::sort
std::ranges::find
```

以及 projection表达，而不是全部写 comparator boilerplate。

<a id="g4-part-xxxi"></a>

<a id="g4-section-11"></a>

## 11. 工程审查与常见误判

### 11.1 Review Protocol

看到一段 STL 代码，按这个顺序问。

**1. Ownership**

```text
Who owns elements?
```

**2. Lifetime**

```text
Any span/view/string_view/iterator?
What invalidates it?
```

**3. Required Semantics**

```text
ordered?
contiguous?
stable address?
front/back growth?
range query?
```

**4. Access Pattern**

```text
iterate?
random lookup?
batch?
hot/cold?
```

**5. Mutation Pattern**

```text
build once?
frequent insert?
frequent erase?
append only?
```

**6. Scale**

```text
N = 8?
1000?
10M?
```

**7. Storage Topology**

```text
flat?
segmented?
node-based?
```

**8. Invalidation**

```text
which operation invalidates:
pointer?
reference?
iterator?
view?
```

**9. Algorithm Capability**

```text
what iterator/range category does algorithm actually require?
```

**10. Measurement**

如果是 hot path：

```text
profile / benchmark
```

而不是仅凭 Big-O 判断。

<a id="g4-part-xxxii"></a>

### 11.2 高频错误

**117. 错误 1**

> `list` insert 是 O(1)，所以中间插入很多时应该用 list。

忽略了：

```text
finding position
allocation
cache misses
pointer chasing
```

**118. 错误 2**

> `unordered_map` O(1)，所以比 map/vector 快。

错。

Big-O 不表达：

```text
hash cost
memory topology
N
```

**119. 错误 3**

> `reserve(N)` 创建 N 个 objects。

错。

它主要准备 capacity。

**120. 错误 4**

> `clear()` 会释放 vector 内存。

不对：它销毁元素并保留 capacity。成员析构可能释放各自拥有的资源，不要与 vector 的元素存储混淆。

**121. 错误 5**

> `span` 更安全，所以可以忽略 lifetime。

错。

Span 不拥有也不延长 lifetime。

**122. 错误 6**

> `const vector&` 永远比 span 好，因为类型更具体。

通常 abstraction 反而过强。

**123. 错误 7**

> Ranges/View 会产生很多临时 containers。

许多 adaptor 是惰性处理，但 view 不等于 non-owning；既要查底层 range，也要查 predicate/capture 的生命周期。

**124. 错误 8**

> Lazy 总比 materialize 快。

不一定。

重复多次 traversal 时 materialization 可能更好。

**125. 错误 9**

> Iterator 没变成 null，所以仍然有效。

Invalid iterator/pointer 不需要变 null。

Dangling address 可以看起来完全正常。

**126. 错误 10**

> Stable address 就应该保存 pointer 作为长期 identity。

长期逻辑 identity 通常更适合 ID/handle。

**127. 错误 11**

> 返回 `vector` 会 copy 很多。

现代 C++ 的 value return + copy elision/move 通常非常自然。

**128. 错误 12**

> `vector<bool>` 和 `vector<T>` 没区别。

它是 bit-packed specialization，reference semantics 特殊。

<a id="g4-part-xxxiii"></a>

<a id="g4-section-12"></a>

## 12. 跨语言回查

### 12.1 C++ / Zig / Rust 对照

**129. Dynamic Contiguous Owner**

C++：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<T>
```

Rust：

```rust
Vec<T>
```

Zig 通常通过：

```text
allocator-backed ArrayList
or explicitly managed slices/storage
```

表达。

共同机器模型：

```text
contiguous owner
capacity growth
relocation
borrow invalidation
```

**130. Borrowed Contiguous View**

C++：

[机制片段 · 不承诺独立编译]

```cpp
std::span<T>
```

Rust：

```rust
&[T]
&mut [T]
```

Zig：

```zig
[]const T
[]T
```

一个重要差异：Rust borrow checker 会静态约束大量 lifetime/aliasing 问题；C++ span 的 lifetime discipline主要由程序员/API architecture维护。

**131. String View**

C++：

[机制片段 · 不承诺独立编译]

```cpp
std::string_view
```

Rust：

```rust
&str
```

Zig：

```zig
[]const u8
```

机器上都接近：

```text
pointer + length
```

但 Unicode/text semantics各语言 abstraction不同。

**132. Iterator / Range**

C++：

```text
iterator concepts
ranges
lazy views
```

Rust：

```text
Iterator trait
iterator adapters
```

Zig：更常见显式 loops/custom iterators，没有与 C++/Rust 同等规模的统一高级 iterator生态。

C++ STL 的突出特点是：container topology + iterator capability + generic algorithm

形成一个历史悠久而庞大的统一模型。

**133. Ownership Difference**

C++：

```text
container/view distinction
```

主要通过类型约定和 lifetime discipline。

Rust：ownership/borrow关系更强地进入 type system。

Zig：lifetime更显式但主要靠 programmer discipline。

底层问题仍然一样：

```text
owner dies
→ view must not remain usable
```

<a id="g4-part-xxxiv"></a>

<a id="g4-section-13"></a>

## 13. 工程原则回查

### 13.1 Final Fifteen Axioms

如果半年后只记十五条：

1. **STL 的核心不是容器目录，而是 Owner → Range/Iterator → Algorithm 的抽象分层。**

2. **动态拥有一组同类型 values 时，`std::vector` 应该是默认起点，除非存在明确反要求。**

3. **`size` 表示活对象数量，`capacity` 表示 storage 容量；`reserve` 与 `resize` 分属 storage 与 lifetime 两个层次。**

4. **任何长期保存 iterator/pointer/reference/span 前都必须明确 container 的 invalidation rules。**

5. **span、string_view 与默认 accessor 的 mdspan 不拥有底层元素；Ranges view 则须另查其 ownership 合同。**

6. **Iterator capability 来源于 storage topology；算法应依赖所需 capability，而不是具体 container name。**

7. **Ranges algorithms主要改善表达、constraints 和 projection，不改变 underlying machine fundamentals。**

8. **Views 通常 lazy；lazy 不自动等于 faster，是否 materialize 取决于 reuse 与 access pattern。**

9. **`map` 的核心价值是 ordered semantics/stability；`unordered_map` 的核心是 hashing semantics，而不是“一个 O(logN)、一个 O(1)”这么简单。**

10. **Read-heavy、build-rare 的 associative workload 应认真考虑 sorted flat representation / `flat_map`。**

11. **Dense integer key 最优 representation 很可能只是 `array` / `vector` direct indexing。**

12. **Linked node stability 要付出 allocation、pointer chasing、cache/TLB 的机器成本；只有真实需要时才值得。**

13. **API 应按 capability表达：owner 用 owner type，contiguous borrow 用 span，string borrow 用 string_view。**

14. **现代 C++ 返回 container by value 是正常 ownership transfer，不应因为旧式“怕 copy”直觉滥用 output parameter。**

15. **Container 选择最终是 Semantics × Lifetime × Access Pattern × Mutation Pattern × Scale × Machine Topology 的联合决策。**

<a id="g4-gate"></a>

<a id="g4-part-xxxv"></a>

<a id="g4-section-14"></a>

## 14. Final Gate

### 14.1 Final Gate

应该能闭卷回答以下问题。

**Vector**

1. `size` 和 `capacity` 根本区别是什么？
2. `reserve` 为什么不创建 N 个 objects？
3. reallocation 为什么会使旧 reference/pointer/iterator 失效？
4. 为什么 `noexcept` move 会影响 vector growth？

**Views**

1. `span` 为什么不是 owner？
2. `span<const T>` 与 `const vector<T>&` 的 abstraction boundary 有什么区别？
3. 为什么 `string_view` 很容易从 temporary string 产生 dangling？
4. `mdspan` 解决的是什么 abstraction 问题？

**Containers**

1. 为什么 vector 通常优于 list？
2. 什么情况下 list 的 node stability/splice 真正有价值？
3. deque 为什么 random-access 却不能当 contiguous storage？
4. `unordered_map` 为什么不自动比 map 快？
5. 什么 workload 适合 flat_map / sorted vector？
6. dense integer ID 为什么经常应该 direct indexing？

**Algorithms / Ranges**

 1. 为什么 STL algorithm 不属于 container member？
 2. iterator capability 与 container topology 有什么关系？
 3. projection 有什么价值？
 4. lazy view 与 materialized vector 应如何选择？
 5. 什么情况下 manual fused loop 比多个 algorithm passes 更合理？

**Lifetime**

 1. vector mutation后，如何判断已有 span 是否仍有效？
 2. stable physical address 与 logical identity 为什么不同？
 3. 为什么 `std::ranges::dangling` 是 lifetime-aware API design？

**API**

 1. 什么时候参数应该是 `std::span<const T>`？
 2. 什么时候 `std::vector<T>&` 反而是正确 API？
 3. 为什么 return `std::vector<T>` by value 是现代 C++ 的正常设计？

<a id="g4-section-15"></a>

## 15. Final Gate · 参考答案与常见误判

- **Vector 1～4：**size 是现有元素数，capacity 是不重分配可容纳数；reserve 不增加 size。重分配结束旧元素/存储，旧路径失效。迁移时的异常保证影响复制/移动选择，不能把 noexcept 当作一定零成本。
- **Views 1～4：**span 不管理清理；const span 元素路径与 const vector& 暴露的具体表示/API 不同。临时 string 被销毁，string_view 没有保活。mdspan 组合多维索引、映射和 accessor；默认 accessor 不拥有元素，自定义句柄语义另查。
- **Containers 1～6：**vector 常有更好局部性，但不是所有任务必胜。list 在确需节点稳定、已知位置和合法 splice 条件时有价值。deque 的随机访问通过分段实现，不承诺连续。hash、分配和数据规模决定常数；读多构建少可考虑排序平面表示；稠密有界 ID 可用直接索引，仍要检查范围与空槽。
- **Algorithms 1～5：**独立算法复用满足能力约束的表示，不意味着所有算法都必须是自由函数；list::sort 是反例。投影统一抽取字段。lazy 避免部分中间物化，但反复遍历会重做工作，predicate 还可能涉及缓存和生命周期。需要多项 reduction 时单次融合合理，是否更快仍需测量。
- **Lifetime 1～3：**逐项查操作规则：重分配使全部旧元素路径失效，erase 等即使不重分配也可失效。地址没变不等于还是同一个逻辑元素；ID 也需代际/失效策略。dangling 阻止部分临时非 borrowed range 的迭代器结果误用，不是完整借用检查器。
- **API 1～3：**同步连续只读输入可用 span<const T>，须声明不保存及有效期。确需改变容量/拥有序列结构时 vector<T>& 合理。按值返回表达拥有结果，可直接构造或移动；为避免想象中的复制而返回局部借用才危险。

**完成标准：**能解释 SignalBatch 的排序前提、重复 ID 合同、三种缺失查询和空统计；能指出四个 G4 实验分别没有证明什么。选型练习与 benchmark 保留为回访题，不伪记已完成。

<a id="g4-part-xxxvi"></a>

<a id="g4-section-16"></a>

## 16. 统一模型

### 16.1 与整个 Track 的统一

现在：

```text
G1
Object / Lifetime

        ↓

G2
Ownership / RAII

        ↓

G3
Value / Copy / Move

        ↓

G4
Representation Abstraction / STL

        ↓

G5
Generic Programming

        ↓

G6
Machine Performance

        ↓

G7
Concurrency
```

G4 在中间承担的角色变得非常清楚：**把正确的 object/value/lifetime model，包装成可复用且具备机器成本意识的数据结构与算法接口。**

以后看到：

[机制片段 · 不承诺独立编译]

```cpp
std::unordered_map<
    VehicleId,
    std::shared_ptr<State>>
```

不应该只识别：“hash map + shared_ptr”。

而应该连续追问：

```text
为什么需要 hash？
VehicleId 是不是 dense？
为什么 State 不能 inline？
为什么需要 shared ownership？
lookup 是否 hot？
多少 allocation？
是否 pointer chasing？
是否多线程修改？
地址稳定是否真的需要？
能不能 shard by VehicleId？
```

这就是 STL 从“库知识”转化为：**Systems Design Vocabulary**

的标志。

<a id="g4-section-17"></a>

## 17. 接下来怎么用

本章形成可学习的主线和定向实验，不宣称全部标准库能力冻结。下一次按 [G5 泛型与编译期编程](g05-generics-and-compile-time.md) 继续；遇到布局/并发成本再回查 G6/G7，遇到二进制接口再看 G8。

[返回全系列导航](README.md)
