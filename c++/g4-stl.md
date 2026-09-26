# C++ Systems Track · G4 Practical STL & Abstraction

**Version:** 1.0  
**Status:** Complete / Frozen Review Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0–G3；G6/G7 的机器与并发模型可用于深化理解  
**Scope:** Containers / Iterators / `span` / `mdspan` / Algorithms / Ranges / Views / Sorting / Searching / Associative Containers / Flat Representations / Invalidation / Ownership-friendly APIs / Vocabulary Types  
**Purpose:** 学会根据**语义、所有权、访问模式与系统成本**选择和组合标准库 abstraction，而不是背容器 API。

---

# 0. G4 的定位

我们之前主动暂停 G4，是因为单纯按照：

```text
vector
deque
list
map
unordered_map
algorithm
ranges
```

逐项介绍，很容易退化成 STL 手册。

经过 G1–G3、G5–G7 后，现在重新看 STL，可以建立更完整的模型：

```text
Semantic Requirement
        ↓
Ownership / Lifetime
        ↓
Access Pattern
        ↓
Required Capabilities
        ↓
Container / View / Algorithm
        ↓
Machine Cost
```

G4 的核心问题不是：

> `vector` 有哪些 member functions？

而是：

> **为什么这里应该拥有数据、那里只应该借用数据；为什么这里需要 contiguous storage、那里需要 ordered lookup；为什么 algorithm 应依赖 capability 而不是 concrete container？**

---

# Part I · STL 的正确 Mental Model

# 1. STL 不是“一堆容器”

现代 C++ 标准库中一条非常重要的抽象链是：

```text
Storage / Ownership
        ↓
Container
        ↓
Iterator / Range
        ↓
Algorithm
        ↓
View / Transformation
```

例如：

```cpp
std::vector<int> values{3, 1, 4, 1, 5};

std::ranges::sort(values);
```

这里：

```text
vector
→ owns storage

range interface
→ exposes iterable elements

ranges::sort
→ requires appropriate iterator/range capabilities
```

算法并不需要知道：

> “这是 vector。”

它真正要求的是类似：

```text
random-access
sortable
writable
```

这些 capabilities。

---

# 2. Container 与 Algorithm 的解耦

传统 OO 容易想：

```cpp
values.sort();
```

但 STL 的经典设计更像：

```cpp
std::ranges::sort(values);
```

也就是：

```text
Data Structure
≠
Operation Set
```

算法通过 iterator/range abstraction工作。

这允许：

```text
same algorithm
+
many compatible representations
```

而无需：

```text
base class
virtual dispatch
```

这是一种非常 C++ 的：

> **Static Generic Abstraction**

---

# 3. G4 的三个核心对象

以后看到 STL code，首先区分：

## Owner

例如：

```cpp
std::vector<T>
std::string
std::map<K, V>
```

它们管理 element/storage lifetime。

---

## View

例如：

```cpp
std::span<T>
std::string_view
std::mdspan<...>
ranges views
```

通常不拥有底层元素。

---

## Algorithm

例如：

```cpp
std::ranges::sort
std::ranges::find
std::ranges::lower_bound
std::ranges::transform
```

临时操作某个 range。

这三者的 lifetime contract 完全不同。

---

# Part II · `std::vector`：现代 C++ 默认动态序列

# 4. `vector<T>` 应该是第一默认候选

如果需求只是：

> “我要拥有一组数量运行时变化的同类型对象。”

第一候选通常应该是：

```cpp
std::vector<T>
```

而不是：

```cpp
std::list<T>
std::deque<T>
T**
custom linked nodes
```

原因不仅是 API。

而是它提供：

```text
single ownership object
contiguous T storage
O(1) indexing
excellent iteration locality
low per-element overhead
simple serialization/interoperability
SIMD-friendly representation
```

---

# 5. `size()` 与 `capacity()`

必须严格区分：

```text
size
=
当前活着的 T objects 数量

capacity
=
当前 storage 最多可以容纳多少 T
```

例如：

```cpp
std::vector<int> values;

values.reserve(1024);
```

此时：

```text
size     = 0
capacity >= 1024
```

没有：

```text
1024 个 int objects
```

只有：

> 足以容纳它们的 storage。

---

# 6. `reserve()` vs `resize()`

```cpp
values.reserve(1024);
```

主要改变：

> storage capacity。

而：

```cpp
values.resize(1024);
```

改变：

> active object count。

因此：

```text
reserve
→ storage management

resize
→ object lifetime management
```

这是 G1/G2 在 STL 中最重要的区别之一。

---

# 7. `clear()` 不等于释放 Capacity

```cpp
values.clear();
```

语义上：

```text
destroy all elements
size = 0
```

但通常：

```text
capacity retained
```

所以：

```cpp
std::vector<T> buffer;
buffer.reserve(max_count);

for (;;) {
    buffer.clear();
    fill(buffer);
    process(buffer);
}
```

是一种非常优秀的：

> **storage reuse**

模式。

---

# 8. `shrink_to_fit()`

```cpp
values.shrink_to_fit();
```

只是：

> request。

不能把它当成：

```text
“保证 capacity == size”
```

的 portable contract。

而且高频执行通常没有意义：

```text
allocate
copy/move
release
```

反而破坏 reuse。

---

# 9. `push_back` vs `emplace_back`

已有 object：

```cpp
T value = make_value();
values.push_back(std::move(value));
```

自然使用：

```cpp
push_back
```

直接根据 constructor arguments 构造：

```cpp
values.emplace_back(arg1, arg2);
```

可以使用：

```cpp
emplace_back
```

但：

> `emplace_back` 不是“高级版 push_back”。

例如：

```cpp
values.emplace_back(make_value());
```

不一定比：

```cpp
values.push_back(make_value());
```

更好。

现代 compiler + guaranteed elision/move semantics 下，区别经常没有想象中大。

优先表达：

> **真实构造意图。**

---

# 10. `vector` Reallocation

当：

```text
size == capacity
```

且需要继续增长时，vector 可能：

```text
allocate larger storage
↓
construct/move/copy elements there
↓
destroy old elements
↓
release old storage
```

因此：

> reallocation 是一次 object relocation event。

不是简单：

```text
realloc some bytes
```

---

# 11. 为什么 `noexcept` Move 对 Vector 重要？

如果 `T`：

```text
move may throw
copy available
```

vector 为维持异常保证，在 relocation 时可能倾向：

```text
copy
```

而不是：

```text
move
```

这就是 G2/G3 的：

```cpp
T(T&&) noexcept;
```

为什么会影响 container behavior。

---

# Part III · Iterator / Pointer / Reference Invalidation

# 12. Invalidation 是 STL 最重要的系统能力之一

考虑：

```cpp
std::vector<int> values{1, 2, 3};

int* p = &values[0];

values.push_back(4);

use(*p);
```

是否合法？

答案取决于：

> `push_back()` 是否触发 reallocation。

如果发生：

```text
old storage
↓
destroy/release
```

那么：

```text
p
```

dangling。

---

# 13. Vector Reallocation Invalidation

一旦 reallocation：

```text
all iterators
all pointers
all references
```

指向旧 elements 的访问路径全部失效。

这是必须形成条件反射的规则。

---

# 14. 没有 Reallocation 也不等于全部稳定

例如：

```cpp
values.erase(values.begin());
```

即使 underlying allocation 没变，

elements 会向前移动。

所以指向 erase point 及其之后元素的：

```text
iterators
references
pointers
```

可能失效或改变所代表的逻辑元素。

因此 invalidation 不仅来自：

```text
allocation
```

还来自：

> element relocation / removal。

---

# 15. Stable Logical ID vs Stable Physical Address

如果系统长期引用：

```text
Vehicle #1234
```

不要因为 vector element address 方便，就把：

```cpp
Vehicle*
```

当永久 identity。

更稳健：

```cpp
struct VehicleId {
    std::uint32_t value;
};
```

然后：

```text
ID
→ lookup
→ current physical representation
```

G3/G6/G7 中的：

> **stable logical identity > accidental storage address**

在 STL 中同样成立。

---

# 16. Invalidation Review Table

可以记住这一层级，而不是死背所有细节：

| Container       | Growth/Insert 的典型稳定性                                     |
| --------------- | -------------------------------------------------------------- |
| `vector`        | reallocation 会使全部 element refs/iterators 失效              |
| `array`         | storage 固定，无结构性 reallocation                            |
| `deque`         | 分段存储；iterator invalidation 规则比 vector 更复杂           |
| `list`          | node address通常稳定；erase 只使被删 node 失效                 |
| `map` / `set`   | node-based，insert 通常不使既有 element refs/iterators 失效    |
| `unordered_map` | rehash 使 iterator 失效；element references/pointers 通常保持  |
| `flat_map`      | contiguous underlying sequence，insert/erase 可能移动 elements |

真正使用时：

> 对具体 mutation 查对应 container contract，而不是凭“看起来应该稳定”猜。

---

# Part IV · `std::array`

# 17. `std::array<T, N>`

当 element count 是：

> compile-time fixed

优先考虑：

```cpp
std::array<T, N>
```

而不是裸：

```cpp
T[N]
```

它提供正常 container interface：

```cpp
size()
begin()
end()
data()
```

并保持：

> inline contiguous storage。

---

# 18. `array` 的 Representation

```cpp
std::array<float, 16> values;
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

---

# 19. `array<T, N>` 的 N 个 T 都是活对象

这一点 G5 已经强调过：

```cpp
std::array<T, 1024>
```

不是：

> capacity 1024 的 raw storage。

而是：

> 1024 个正常 `T` objects。

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

---

# Part V · `std::deque`

# 20. `deque` 是 Segmented Sequence

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

```cpp
deque[i]
```

仍然支持 random access，

但：

```cpp
&deque[i + 1] == &deque[i] + 1
```

不能作为一般连续存储假设。

---

# 21. `deque` 什么时候有价值？

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

---

# 22. `deque` 的代价

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

---

# Part VI · `list` / `forward_list`

# 23. Linked List 的抽象优势

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

---

# 24. 但 “O(1) Insert” 很容易骗人

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

于是有人直接得出：

> list 更快。

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

所以：

> Big-O 必须和 G6 machine model 一起分析。

---

# 25. 什么时候应该真的考虑 `list`？

当下面要求是真实核心需求：

```text
node address/reference stability
frequent splice between lists
frequent insert/erase at known positions
large/non-movable nodes where relocation is unacceptable
```

而不是：

> “听说中间删除是 O(1)。”

---

# 26. `forward_list`

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

---

# Part VII · `std::span`

# 27. `std::span<T>` 是 G4 最重要的 API 类型之一

`span` 表示：

> **non-owning contiguous sequence view**

例如：

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

```cpp
void decode(
    const std::byte* data,
    std::size_t size);
```

更完整。

---

# 28. Span 不拥有数据

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

span：

> dangling。

---

# 29. Span 不延长 Lifetime

必须永久保留：

```text
view lifetime
≤
underlying storage lifetime
and
no invalidating mutation
```

例如：

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

---

# 30. `span` 也可能因 Reallocation 失效

```cpp
std::vector<int> values{1, 2, 3};
std::span<const int> view = values;

values.push_back(4);  // may reallocate

use(view);
```

如果 reallocation：

> span 指向旧 storage。

所以：

> Non-owning view correctness = owner lifetime + storage stability。

---

# 31. `span<T>` vs `span<const T>`

```cpp
std::span<T>
```

表示：

> mutable borrowed elements。

```cpp
std::span<const T>
```

表示：

> read-only access path。

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

```cpp
std::span<const T>
```

非常自然。

---

# 32. Static Extent

```cpp
std::span<const std::byte, 8>
```

表示：

> extent = 8 是类型的一部分。

相比：

```cpp
std::span<const std::byte>
```

动态 extent。

固定协议字段：

```cpp
std::uint64_t decode(
    std::span<const std::byte, 8> bytes);
```

可以把：

> “必须恰好 8 bytes”

编码进 API type。

---

# 33. `span` 是非常好的 Representation Boundary

假设内部：

```cpp
std::vector<float> values_;
```

对算法不必暴露：

```text
vector ownership/capacity API
```

可以暴露：

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

而不是：

> 修改 owner representation 的能力。

---

# Part VIII · `std::string_view`

# 34. `string_view` 是字符领域的 Borrowed View

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

---

# 35. 最危险的 `string_view`

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

返回 view：

> dangling。

因此：

```text
string_view
```

和：

```text
span
```

一样首先是：

> lifetime contract。

---

# 36. `string_view` 不保证 Null Termination

```cpp
std::string_view view;
```

只表示：

```text
pointer + length
```

不能默认：

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

---

# Part IX · `std::mdspan` — C++23 多维 View

# 37. `mdspan` 是 G4 与高性能计算的重要连接

C++23：

```cpp
std::mdspan
```

表达：

> 对多维数据的 non-owning structured view。

例如概念：

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

---

# 38. `mdspan` 不负责 Ownership

和 span 一样：

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

---

# 39. Layout Policy

`mdspan` 的重要价值是可以表达：

```text
layout_right
layout_left
layout_stride
```

也就是说：

> logical `(i, j)` 如何映射到 linear storage offset。

这直接连接 G6：

```text
row-major
column-major
strided layout
```

和 cache locality。

---

# 40. `mdspan` 的系统意义

以前函数可能：

```cpp
void process(
    const float* data,
    std::size_t rows,
    std::size_t cols,
    std::size_t stride);
```

现在可以将：

> shape + layout mapping + element access

打包成 view abstraction。

同时不要求算法：

> 拥有数据。

这非常适合：

```text
robotics
linear algebra
image processing
tensor kernels
sensor matrices
```

---

# Part X · Iterator：不是“高级 Pointer”

# 41. Iterator 的核心是 Traversal Capability

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

应该理解：

> **Container topology 决定 iterator 能力。**

---

# 42. Examples

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

```cpp
std::ranges::sort(range);
```

需要：

> random-access sortable range。

因此不能：

```cpp
std::ranges::sort(std::list<int>);
```

这不是标准库“故意刁难”。

而是：

> sort algorithm 的操作需求与 linked-list iterator capability 不匹配。

`std::list` 有自己的：

```cpp
list.sort();
```

可以利用 node relinking。

---

# 43. Contiguous Iterator

`vector` iterator 具有：

> contiguous semantics。

所以可以和：

```text
pointer
span
C APIs
SIMD
```

自然衔接。

这是 vector 与 deque 虽然都 random access，却存在的一个重要能力差异。

---

# Part XI · Algorithm First

# 44. 优先表达“我要做什么”

比如寻找：

```cpp
auto it = std::ranges::find(values, target);
```

而不是首先：

```cpp
for (...) {
    if (...) {
        ...
    }
}
```

原因不是：

> loop 不好。

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

---

# 45. 但不要迷信“算法永远优于 Loop”

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

```cpp
for (const Sample& sample : samples) {
    ...
}
```

可能更合理。

因此原则：

> **Prefer algorithms when they express the operation naturally; fuse work when one-pass semantics/performance matters.**

---

# 46. Ranges Algorithms

传统：

```cpp
std::sort(values.begin(), values.end());
```

现代 C++：

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

---

# 47. Projection

非常好用：

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

```cpp
std::ranges::sort(
    signals,
    [](const Signal& a, const Signal& b) {
        return a.id < b.id;
    });
```

Projection 表达：

> “使用这个字段作为排序 key。”

语义更清楚。

---

# 48. `lower_bound`

如果数据已经按 `id` 排序：

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

---

# 49. Sorted Vector 是一种非常强的 Associative Representation

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

这就是：

> **Flat Representation**

---

# Part XII · Ranges Views

# 50. View 是 Lazy Transformation

例如：

```cpp
auto positive =
    values |
    std::views::filter([](int value) {
        return value > 0;
    });
```

`positive` 通常不是：

> 一个新 vector。

它是：

> 对原 range 的 lazy traversal adapter。

---

# 51. Lazy 意味着什么？

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

---

# 52. View 不是 Owner

这又回到 lifetime：

```cpp
auto view =
    values |
    std::views::filter(pred);
```

如果 view 依赖：

```text
values
```

那么 values 的 lifetime / invalidation rules 仍然控制 view correctness。

不要因为语法变成：

```text
views pipeline
```

就忘记底层 storage。

---

# 53. Range Pipeline

例如：

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

---

# 54. Range Pipeline 不等于自动最快

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

因此 G6 原则保持：

> 优先写清晰 abstraction，然后 profile/assembly 验证 hot path。

---

# 55. View 的 Lifetime Trap

尤其不要随意：

```text
store a view
```

长期超过其 source owner。

例如 class member：

```cpp
std::span<const T> view_;
```

意味着 class 的 lifetime invariant必须包含：

> 被 view_ 借用的 owner 永远活得更久，而且不会使 storage invalid。

这是很强的 contract。

---

# Part XIII · Borrowed Range

# 56. 为什么 Ranges 要有 `borrowed_range`？

假设：

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

等机制表达：

> 某 range 的 iterator 是否可以安全独立于 range object lifetime 返回。

---

# 57. `std::ranges::dangling`

对于不安全的 rvalue range：

某些 range algorithm 的返回类型会成为：

```cpp
std::ranges::dangling
```

而不是给你一个立即悬空的 iterator。

这是一种非常漂亮的：

> **Lifetime-aware generic API design**

与 G1/G5 完全呼应。

---

# Part XIV · `std::map` / `std::set`

# 58. Ordered Associative Containers

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

---

# 59. `map` 的真正优势

不是：

> O(log N) 听起来不错。

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

---

# 60. `operator[]` 的语义

```cpp
map[key]
```

如果 key 不存在：

> 会插入默认构造的 mapped value。

所以只想查询时不要机械：

```cpp
if (map[key] == ...)
```

可能无意修改 container。

查询优先：

```cpp
map.find(key)
```

或者 C++20：

```cpp
map.contains(key)
```

---

# 61. `try_emplace`

例如：

```cpp
map.try_emplace(
    key,
    constructor_args...);
```

如果 key 已存在：

> 不需要构造 mapped object。

对于昂贵 value：

```text
lookup + conditional construction
```

很自然。

---

# Part XV · `std::unordered_map`

# 62. Hash Table

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

但这绝不意味着：

> “一定比 map 快”。

---

# 63. Hash Lookup 的真实 Cost

至少包括：

```text
hash computation
bucket access
collision handling
pointer/metadata traversal
key comparison
```

如果 key 是：

```cpp
std::string
```

hash 本身可能扫描整条 string。

所以：

```text
O(1)
```

指 container size N 的平均渐进复杂度，

不是：

> one CPU instruction。

---

# 64. Load Factor

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

---

# 65. `reserve`

如果预先知道约有：

```text
N entries
```

可以：

```cpp
table.reserve(N);
```

减少未来：

```text
rehash
```

次数。

这和 vector reserve 是同一思想：

> 使用 domain knowledge 提前稳定 storage topology。

---

# 66. Rehash Invalidation

Rehash 会：

> 重新组织 buckets。

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

---

# 67. `unordered_map` 最大的误区

> “Lookup 是 O(1)，所以这是最快字典。”

如果：

```text
N = 20
```

一个线性 scan：

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

因此：

> **Small N changes the game.**

---

# Part XVI · `std::flat_map` / `std::flat_set` — C++23

# 68. Flat Associative Containers

C++23：

```cpp
std::flat_map
std::flat_set
```

提供 associative-container-style interface，

但 representation 更接近：

> sorted contiguous sequence(s)

而不是 node tree。

---

# 69. Flat Map 的 Cost Model

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

---

# 70. `flat_map` vs Sorted Vector

如果只是内部实现：

```cpp
std::vector<Entry>
```

然后：

```cpp
std::ranges::sort
std::ranges::lower_bound
```

已经非常好。

`flat_map` 的价值：

> 提供更明确 associative semantics/API。

选择取决于：

```text
representation control
API expectations
mutation pattern
```

---

# 71. Dense Integer Key：别忘了 Array / Vector

假设 key：

```text
0 <= id < 64
```

不要第一反应：

```cpp
std::unordered_map<int, Entry>
```

直接：

```cpp
std::array<Entry, 64>
```

或：

```cpp
std::vector<Entry>
```

可能更合理。

Lookup：

```cpp
entries[id]
```

无需：

```text
hash
tree
node
```

这是一种非常重要的：

> **Exploit Domain Constraints**

---

# Part XVII · Container Selection

# 72. 不要按 Big-O 选 Container

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

---

# 73. 一个实用选择矩阵

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

是：

> starting point。

---

# Part XVIII · `optional` / `variant` / `expected`

# 74. STL 也提供“状态建模”类型

容器之外，现代标准库的重要抽象还有：

```cpp
std::optional<T>
std::variant<...>
std::expected<T, E>
```

这些不是主要 storage containers，

但对系统 API 非常重要。

---

# 75. `optional<T>`

表达：

```text
T exists
or
no T
```

例如：

```cpp
std::optional<Job> try_pop();
```

比：

```cpp
bool try_pop(Job& out);
```

有时更 value-oriented。

但如果 `T` 很大：

> 返回 optional<T> 仍然要分析 representation/move cost。

---

# 76. `variant`

```cpp
using Command =
    std::variant<
        Start,
        Stop,
        Update>;
```

表示：

> exactly one of several alternatives。

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

---

# 77. `std::visit`

```cpp
std::visit(
    [](auto&& command) {
        handle(command);
    },
    cmd);
```

配合 variant实现：

> closed set static sum type dispatch。

它不是 virtual inheritance hierarchy。

C++ compiler可以基于 alternative set 静态生成 dispatch machinery。

---

# 78. `expected<T, E>` — C++23

表示：

```text
success: T
or
failure: E
```

例如：

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

---

# 79. `expected` 不会自动带来 Strong Exception Safety

如果函数内部：

```text
modify shared state
↓
later return unexpected(error)
```

已经发生的 side effects：

> 不会因为返回 expected 自动 rollback。

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

---

# Part XIX · Practical SignalBatch

# 80. 建立一个真实组件

我们用一个简单数据处理模型贯穿：

```cpp
struct SignalSample {
    std::uint64_t timestamp_ns{};
    std::uint32_t signal_id{};
    float value{};
};
```

Owner：

```cpp
class SignalBatch {
public:
    explicit SignalBatch(std::size_t capacity) {
        samples_.reserve(capacity);
    }

    void push(SignalSample sample) {
        samples_.push_back(sample);
    }

    [[nodiscard]]
    std::span<const SignalSample> samples() const noexcept {
        return samples_;
    }

    [[nodiscard]]
    std::size_t size() const noexcept {
        return samples_.size();
    }

    void clear() noexcept {
        samples_.clear();
    }

private:
    std::vector<SignalSample> samples_;
};
```

---

# 81. 为什么这里不返回 `const vector&`？

可以：

```cpp
const std::vector<SignalSample>&
```

但这暴露：

```text
representation is vector
```

调用方获得：

```text
vector-specific API
capacity
allocator-related expectations
```

而算法实际只需要：

```text
contiguous read-only sequence
```

所以：

```cpp
std::span<const SignalSample>
```

提供更窄的 capability。

---

# 82. Sort by Signal ID

内部或构建阶段：

```cpp
std::ranges::sort(
    samples_,
    {},
    &SignalSample::signal_id);
```

现在 representation invariant：

```text
samples sorted by signal_id
```

可以支持：

```text
binary search
equal-range grouping
sequential group processing
```

---

# 83. Find One Signal

```cpp
auto it = std::ranges::lower_bound(
    samples_,
    signal_id,
    {},
    &SignalSample::signal_id);

if (it != samples_.end() &&
    it->signal_id == signal_id) {
    // found
}
```

这是一种：

```text
flat sorted representation
```

而不是 hash table。

如果 batch 是：

```text
build once
query/read many
```

非常自然。

---

# 84. Grouping by Key

排序：

```text
id:
1 1 1 4 4 8 8 8
```

同 ID naturally contiguous。

于是：

```text
process all signal 1
then 4
then 8
```

同时改善：

```text
lookup semantics
cache locality
batching
```

所以：

> 一个 representation choice 可以同时服务算法和机器。

---

# 85. Statistics

如果同时需要：

```text
count
min
max
sum
```

一个 fused loop：

```cpp
struct Stats {
    std::size_t count{};
    float min{};
    float max{};
    double sum{};
};

std::optional<Stats>
compute_stats(std::span<const SignalSample> samples) {
    if (samples.empty()) {
        return std::nullopt;
    }

    Stats stats{
        .count = 0,
        .min = samples.front().value,
        .max = samples.front().value,
        .sum = 0.0,
    };

    for (const SignalSample& sample : samples) {
        ++stats.count;
        stats.min = std::min(stats.min, sample.value);
        stats.max = std::max(stats.max, sample.value);
        stats.sum += sample.value;
    }

    return stats;
}
```

这里 manual loop 是合理的：

> 一次 traversal 完成多个 reductions。

---

# Part XX · Erase / Filter

# 86. 现代 Erase

以前典型：

```cpp
values.erase(
    std::remove_if(
        values.begin(),
        values.end(),
        pred),
    values.end());
```

现代：

```cpp
std::erase_if(values, pred);
```

表达更清楚。

---

# 87. Filter View vs Physical Removal

```cpp
auto valid =
    samples |
    std::views::filter(is_valid);
```

只是：

> logical filtered view。

底层 samples 仍然全部存在。

而：

```cpp
std::erase_if(samples, is_invalid);
```

真正：

> 修改 owner、结束 object lifetime、移动后续 elements。

这两个 semantics 完全不同。

---

# 88. Lazy Filter 的 Cost

filter view 遍历时每个 element：

```text
predicate
↓
possibly skip
```

如果同一个 filtered subset 被重复处理很多次：

> 每次都重新 predicate。

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

---

# Part XXI · API Design

# 89. Owner API

如果函数：

> 接管一份 vector 所有权

可以：

```cpp
void consume(std::vector<Record> records);
```

by-value 明确：

> ownership enters function。

Caller：

```cpp
consume(std::move(records));
```

---

# 90. Borrowed Read-only

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

---

# 91. Borrowed Mutable

```cpp
void normalize(
    std::span<float> values);
```

表达：

> caller owns；function 可修改 elements。

---

# 92. 不要滥用 `const vector&`

```cpp
void process(
    const std::vector<Record>& records);
```

如果算法真正依赖：

```text
contiguous sequence
```

则：

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

---

# 93. 但也不要机械全部换 Span

如果 API 的 semantic contract 就是：

> “这是一个 vector owner，我需要 capacity、growth、push_back。”

那就应该：

```cpp
std::vector<T>&
```

或者更好的 owner abstraction。

例如：

```cpp
void fill(std::vector<T>& output);
```

如果目的明确是：

> 重用 caller-owned dynamic storage。

这是合法设计。

关键是：

> 参数类型应该表达所需 capability。

---

# Part XXII · Return Values

# 94. 返回 `vector` 很正常

```cpp
std::vector<Record> load_records();
```

现代 C++：

```text
copy elision
move semantics
```

使：

> return container by value

成为非常自然的 ownership transfer。

不要为了“怕 copy”机械：

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

---

# 95. 不要返回指向 Local Container 的 View

错误：

```cpp
std::span<const Record> load() {
    std::vector<Record> result;
    // ...
    return result;
}
```

返回 owner：

```cpp
std::vector<Record> load();
```

才正确。

这是：

> **Owner must cross boundary if data must outlive the function.**

---

# Part XXIII · Container Choice 与 ABI

# 96. 不要轻易把 STL Container 放进稳定 Binary ABI

例如 public dynamic library C++ ABI：

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

这不是说：

> 永远不能。

而是：

> container-rich C++ API 会形成很强 ABI coupling。

G8 会正式展开。

---

# Part XXIV · Container Choice 与 Concurrency

# 97. STL Container 本身通常不是“自动线程安全”

例如：

```cpp
std::vector<int> values;
```

多个 threads 只读：

> 在正确 publication 后很自然。

一个 thread修改、另一个同时读取：

> 需要同步。

不能因为：

```text
vector implementation internally complicated
```

就认为标准库会自动锁。

---

# 98. Different Elements 也要分析 Container Mutation

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

```cpp
std::vector<bool>
```

是特殊 bit-packed representation。

不同 logical bool elements 可能共享同一个 underlying word。

所以不要把普通 vector element reasoning直接套给：

```cpp
vector<bool>
```

---

# Part XXV · `vector<bool>`

# 99. 为什么它特殊？

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

```cpp
values[i]
```

通常返回：

> proxy reference

而不是普通：

```cpp
bool&
```

---

# 100. 什么时候可以用？

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

```cpp
std::vector<std::uint8_t>
```

可能更直观。

如果需要固定 bitset：

```cpp
std::bitset<N>
```

也可能更适合。

---

# Part XXVI · Flat vs Node-based

# 101. 一个统一机器模型

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

所以：

> **Topology is a trade-off, not ideology.**

---

# Part XXVII · STL 与 Memory Resource

# 102. Containers 与 `std::pmr`

G6 已经学习：

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

---

# 103. 不要让 Allocator Policy 泄漏过远

如果 subsystem 内部需要：

```cpp
std::pmr::vector<Temp>
```

不代表：

> 整个 domain model 所有 API 都需要传 `memory_resource*`。

与 G5 genericity 一样：

> **Policy propagation should stop at a deliberate boundary.**

---

# Part XXVIII · STL Performance Review

# 104. 看到 Container 时问什么？

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

---

# 105. `map` vs `unordered_map` vs `flat_map` vs `vector`

真正比较：

| Question          | `map`          | `unordered_map`              | `flat_map` / sorted vector | dense vector            |
| ----------------- | -------------- | ---------------------------- | -------------------------- | ----------------------- |
| Ordered traversal | ✓              | —                            | ✓                          | by index/order          |
| Lookup            | O(log N)       | avg O(1)                     | O(log N)                   | O(1) dense key          |
| Insert            | O(log N)       | avg O(1)                     | O(N)                       | depends                 |
| Locality          | poor/moderate  | poor/moderate                | high                       | very high               |
| Address stability | high           | relatively high for elements | low                        | low                     |
| Range query       | excellent      | poor                         | excellent                  | domain-specific         |
| Small/read-mostly | often overkill | often overkill               | strong                     | strongest if applicable |

没有一个 universal winner。

---

# Part XXIX · Practical Selection Rules

# 106. Rule 1 — `vector` Until Proven Otherwise

动态 sequence：

> 先 vector。

换掉它需要明确 requirement。

---

# 107. Rule 2 — Dense Key → Direct Index

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

---

# 108. Rule 3 — Read-heavy Lookup → Consider Sorted Flat Data

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

---

# 109. Rule 4 — Address Stability 必须是 Requirement 才值得付费

不要为了：

> “pointer 一直有效挺方便”

就默认 node containers。

长期 identity更推荐：

```text
ID / handle
```

---

# 110. Rule 5 — Borrow with Span/View, Own with Container

API boundary上：

```text
ownership
→ vector/string/owner type

borrow
→ span/string_view/mdspan
```

这是非常好的默认。

---

# Part XXX · Practical Lab

# 111. Lab 1 — Container Selection

给四个 workload：

### A

10M `float` 顺序扫描。

### B

1000 个 key，build once，查询 10M 次，需要 sorted iteration。

### C

动态 queue，两端 push/pop。

### D

需要把 node 从一个 sequence O(1) splice 到另一个，地址必须稳定。

闭卷选 container，并从：

```text
semantics
+
machine topology
```

两方面解释。

---

# 112. Lab 2 — Invalidation

```cpp
std::vector<int> values;
values.reserve(4);

values.push_back(1);
values.push_back(2);

int* p = &values[0];

values.push_back(3);
```

此时 `p`？

然后：

```cpp
values.push_back(4);
values.push_back(5);
```

此时呢？

要求回答：

> 不看“push_back”这个名字，而看是否发生 reallocation。

---

# 113. Lab 3 — Span Boundary

设计：

```cpp
float average(...);
```

要求支持：

```text
vector<float>
array<float,N>
subrange
C array
```

但不取得 ownership。

理想：

```cpp
float average(
    std::span<const float> values);
```

解释：

```text
ownership
mutability
extent
contiguity
lifetime
```

五个维度。

---

# 114. Lab 4 — Sorted Vector vs Hash

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

这会非常直观地打掉：

> “O(1) 总比 O(logN) 快”

这种直觉。

---

# 115. Lab 5 — View Lifetime

逐个判断：

```cpp
std::string text = "hello";
std::string_view a = text;
```

合法。

然后：

```cpp
std::string_view b = std::string{"hello"};
```

为什么危险？

再：

```cpp
text += very_large_suffix;
```

之后 `a` 是否仍然可靠？

根据：

> string storage invalidation

分析。

---

# 116. Lab 6 — Range Projection

定义：

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

```cpp
std::ranges::sort
std::ranges::find
```

以及 projection表达，而不是全部写 comparator boilerplate。

---

# Part XXXI · G4 Review Protocol

看到一段 STL 代码，按这个顺序问。

## 1. Ownership

```text
Who owns elements?
```

---

## 2. Lifetime

```text
Any span/view/string_view/iterator?
What invalidates it?
```

---

## 3. Required Semantics

```text
ordered?
contiguous?
stable address?
front/back growth?
range query?
```

---

## 4. Access Pattern

```text
iterate?
random lookup?
batch?
hot/cold?
```

---

## 5. Mutation Pattern

```text
build once?
frequent insert?
frequent erase?
append only?
```

---

## 6. Scale

```text
N = 8?
1000?
10M?
```

---

## 7. Storage Topology

```text
flat?
segmented?
node-based?
```

---

## 8. Invalidation

```text
which operation invalidates:
pointer?
reference?
iterator?
view?
```

---

## 9. Algorithm Capability

```text
what iterator/range category does algorithm actually require?
```

---

## 10. Measurement

如果是 hot path：

```text
profile / benchmark
```

而不是仅凭 Big-O 判断。

---

# Part XXXII · 高频错误

# 117. 错误 1

> `list` insert 是 O(1)，所以中间插入很多时应该用 list。

忽略了：

```text
finding position
allocation
cache misses
pointer chasing
```

---

# 118. 错误 2

> `unordered_map` O(1)，所以比 map/vector 快。

错。

Big-O 不表达：

```text
hash cost
memory topology
N
```

---

# 119. 错误 3

> `reserve(N)` 创建 N 个 objects。

错。

它主要准备 capacity。

---

# 120. 错误 4

> `clear()` 会释放 vector 内存。

通常不。

---

# 121. 错误 5

> `span` 更安全，所以可以忽略 lifetime。

错。

Span 不拥有也不延长 lifetime。

---

# 122. 错误 6

> `const vector&` 永远比 span 好，因为类型更具体。

通常 abstraction 反而过强。

---

# 123. 错误 7

> Ranges/View 会产生很多临时 containers。

Views 通常 lazy/non-owning。

---

# 124. 错误 8

> Lazy 总比 materialize 快。

不一定。

重复多次 traversal 时 materialization 可能更好。

---

# 125. 错误 9

> Iterator 没变成 null，所以仍然有效。

Invalid iterator/pointer 不需要变 null。

Dangling address 可以看起来完全正常。

---

# 126. 错误 10

> Stable address 就应该保存 pointer 作为长期 identity。

长期逻辑 identity 通常更适合 ID/handle。

---

# 127. 错误 11

> 返回 `vector` 会 copy 很多。

现代 C++ 的 value return + copy elision/move 通常非常自然。

---

# 128. 错误 12

> `vector<bool>` 和 `vector<T>` 没区别。

它是 bit-packed specialization，reference semantics 特殊。

---

# Part XXXIII · C++ / Zig / Rust 对照

# 129. Dynamic Contiguous Owner

C++：

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

---

# 130. Borrowed Contiguous View

C++：

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

一个重要差异：

> Rust borrow checker 会静态约束大量 lifetime/aliasing 问题；C++ span 的 lifetime discipline主要由程序员/API architecture维护。

---

# 131. String View

C++：

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

---

# 132. Iterator / Range

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

Zig：

> 更常见显式 loops/custom iterators，没有与 C++/Rust 同等规模的统一高级 iterator生态。

C++ STL 的突出特点是：

> container topology + iterator capability + generic algorithm

形成一个历史悠久而庞大的统一模型。

---

# 133. Ownership Difference

C++：

```text
container/view distinction
```

主要通过类型约定和 lifetime discipline。

Rust：

> ownership/borrow关系更强地进入 type system。

Zig：

> lifetime更显式但主要靠 programmer discipline。

底层问题仍然一样：

```text
owner dies
→ view must not remain usable
```

---

# Part XXXIV · G4 Final Fifteen Axioms

如果半年后只记十五条：

1. **STL 的核心不是容器目录，而是 Owner → Range/Iterator → Algorithm 的抽象分层。**

2. **动态拥有一组同类型 values 时，`std::vector` 应该是默认起点，除非存在明确反要求。**

3. **`size` 表示活对象数量，`capacity` 表示 storage 容量；`reserve` 与 `resize` 分属 storage 与 lifetime 两个层次。**

4. **任何长期保存 iterator/pointer/reference/span 前都必须明确 container 的 invalidation rules。**

5. **`std::span`、`string_view`、`mdspan` 都是 view，不拥有也不延长底层 storage lifetime。**

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

---

# Part XXXV · G4 Final Gate

应该能闭卷回答以下问题。

## Vector

1. `size` 和 `capacity` 根本区别是什么？
2. `reserve` 为什么不创建 N 个 objects？
3. reallocation 为什么会使旧 reference/pointer/iterator 失效？
4. 为什么 `noexcept` move 会影响 vector growth？

## Views

1. `span` 为什么不是 owner？
2. `span<const T>` 与 `const vector<T>&` 的 abstraction boundary 有什么区别？
3. 为什么 `string_view` 很容易从 temporary string 产生 dangling？
4. `mdspan` 解决的是什么 abstraction 问题？

## Containers

1. 为什么 vector 通常优于 list？
2. 什么情况下 list 的 node stability/splice 真正有价值？
3. deque 为什么 random-access 却不能当 contiguous storage？
4. `unordered_map` 为什么不自动比 map 快？
5. 什么 workload 适合 flat_map / sorted vector？
6. dense integer ID 为什么经常应该 direct indexing？

## Algorithms / Ranges

 1. 为什么 STL algorithm 不属于 container member？
 2. iterator capability 与 container topology 有什么关系？
 3. projection 有什么价值？
 4. lazy view 与 materialized vector 应如何选择？
 5. 什么情况下 manual fused loop 比多个 algorithm passes 更合理？

## Lifetime

 1. vector mutation后，如何判断已有 span 是否仍有效？
 2. stable physical address 与 logical identity 为什么不同？
 3. 为什么 `std::ranges::dangling` 是 lifetime-aware API design？

## API

 1. 什么时候参数应该是 `std::span<const T>`？
 2. 什么时候 `std::vector<T>&` 反而是正确 API？
 3. 为什么 return `std::vector<T>` by value 是现代 C++ 的正常设计？

---

# Part XXXVI · G4 与整个 Track 的统一

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

G4 在中间承担的角色变得非常清楚：

> **把正确的 object/value/lifetime model，包装成可复用且具备机器成本意识的数据结构与算法接口。**

以后看到：

```cpp
std::unordered_map<
    VehicleId,
    std::shared_ptr<State>>
```

不应该只识别：

> “hash map + shared_ptr”。

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

这就是 STL 从“库知识”转化为：

> **Systems Design Vocabulary**

的标志。

---

# G4 完成状态

```text
G4.1  vector / dynamic contiguous storage
G4.2  array / deque / list topology
G4.3  ordered / hash / flat associative data
G4.4  span / string_view / mdspan
G4.5  iterator capability / invalidation
G4.6  algorithms / ranges / projections
G4.7  lazy views / borrowed ranges
G4.8  vocabulary types
G4.9  ownership-friendly API design
G4.10 performance / representation selection
────────────────────────────────────────────
G4     COMPLETE / FROZEN
```

至此，之前刻意留下的 G4 缺口已经补齐。

---

# 下一章

按照当前路线，下一份不再拆课，直接产出完整章节：

# **G8 — ABI / Libraries / C Interop**

它会把 G0 的：

```text
object file
symbol
linker
loader
calling convention
```

与 G1–G7 的：

```text
type
layout
ownership
exception
templates
STL
lifetime
```

全部推到真正的 **Binary Boundary**：

```text
C++ Source API
        ↓
Name Mangling
        ↓
Calling Convention
        ↓
Object Layout / ABI
        ↓
Symbol Visibility
        ↓
Static / Shared Library
        ↓
C ABI Boundary
        ↓
Opaque Handle
        ↓
C++ ↔ C / Rust / Zig
```

这会正式回答一个系统工程里非常重要的问题：

> **为什么“两个源代码层面看起来兼容的 C++ 类型”并不意味着两个 binary components 可以安全互换？**
