# G3 · 值语义、移动与成本模型

**版本：** 1.2.1 · Professional Handbook · 全书一致性修订

**状态：** 本轮编辑修订待集中审核；接受历史与冻结候选见[系列状态](README.md#基线与证据状态)。PDF **NOT BUILT / NOT VALIDATED**。

**语言基线与范围：** C++23。前置为 G1/G2；覆盖值、复制/移动、返回、参数与表示成本；Zig/Rust 仅作对照。

**阅读约定：** [Editorial Profile v1.0](editorial-profile.md) · [全书术语、证据与引用](handbook-guide.md)。

[上一章：G2](g02-raii-and-ownership.md) · [全系列导航](README.md) · [下一章：G4](g04-stl-and-ranges.md)

## 阅读入口

本章的问题是：**同样写 `auto b = a;`，为什么有时复制数据、有时只多一条访问路径？写 std::move 又改变了什么？**

- 主阅读线：[值与表示](#g3-part-1) → [复制实验](#g3-lab-copy) → [移动与消除](#g3-part-5) → [移动与返回实验](#g3-lab-move) → [参数合同](#g3-part-9) → [容器迁移](#g3-part-15) → [Final Gate](#g3-gate)。
- 回查层：按下面的主题目录查找接口、架构、跨语言和审查材料，不要求一次连续读完。
- 前置自测：能否画出 vector、span、shared_ptr 分别拥有和借用什么？若还混淆，先返回 G2。
- 完成目标：遇到复制/移动表达式，按“类型合同 → 候选操作 → 表示 → 实际成本”逐层判断。

带 `g-lab` 的块为完整定向实验。其余代码保留为片段和设计素材；成本公式是分析维度，不能代替测量。跨语言部分不在本批编译范围。

### 章节目录

- [1. 逻辑值、表示与复制成本](#g3-section-1)
- [2. 实验 · G3-L1：复制的是完整值，还是访问关系？](#g3-section-2)
- [3. 平凡复制与对象表示](#g3-section-3)
- [4. 移动、异常保证与复制消除](#g3-section-4)
- [5. 实验 · G3-L2～L4：转换、重载与结果对象](#g3-section-5)
- [6. 返回值、参数与借用边界](#g3-section-6)
- [7. 容器迁移与稳定身份](#g3-section-7)
- [8. 对象表示策略](#g3-section-8)
- [9. 值导向架构与生命周期解耦](#g3-section-9)
- [10. 成本图与接口决策](#g3-section-10)
- [11. 跨语言回查](#g3-section-11)
- [12. 工程审查与常见误判](#g3-section-12)
- [13. 术语与统一模型](#g3-section-13)
- [14. Final Gate](#g3-section-14)
- [15. Final Gate · 参考答案与常见误判](#g3-section-15)
- [16. 工程原则回查](#g3-section-16)
- [17. G3 → G4](#g3-section-17)

<a id="g3-section-1"></a>

## 1. 逻辑值、表示与复制成本

<a id="g3-part-0"></a>

### 1.1 本章的工程问题

[G1 §1](g01-object-model.md#g1-object)检查访问有效性，[G2 §1](g02-raii-and-ownership.md#g2-section-1)检查清理责任，G3 追问值在系统流动时支付了什么成本。正确性是前提，但“用了智能指针”或“写了 move”都不能直接推出性能。

本章按三步阅读表达式：类型表示什么逻辑值；操作允许改变哪些状态；表示如何映射到分配、元素操作和间接访问。

<a id="g3-part-1"></a>

### 1.2 Logical Value 与 Representation

**先问类型的逻辑值是什么**

| 类型 | 逻辑值/责任 | 常见表示模型，非 ABI 保证 |
| --- | --- | --- |
| vector<int> | 拥有一串 int | 外部元素存储，加指针/长度/容量等状态 |
| span<int> | 借用一段连续 int | 指针与范围；静态 extent 可编码在类型中 |
| unique_ptr<T> | 独占资源或为空 | 指针及 deleter 状态 |
| shared_ptr<T> | 共享拥有关系及保存的指针 | 对象指针与控制信息关联 |
| array<int, N> | 内嵌 N 个 int | 元素作为对象组成部分 |

这里的“常见表示”帮助估计成本，不允许据此访问私有布局、假定固定 sizeof 或跨 ABI 序列化。

**Representation Size 不等于 Payload Size**

vector 对象本身可以很小，拥有的序列却很大。`auto copy = values;` 的复制工作随元素及 allocator 合同变化，而不只处理 sizeof(vector) 个字节。先分清 wrapper 与 payload，再谈便宜还是昂贵。

<a id="g3-part-2"></a>

### 1.3 Value Semantics

**相同值，不是相同对象**

[机制片段 · 不承诺独立编译]

```cpp
std::string a{"hello"};
std::string b = a;
```

b 是新对象，初始字符串内容与 a 相同；修改 b 的字符不会因此修改 a。对一般 T，先查其复制合同，不能从赋值语法推导这种独立性。

**Value Semantics 不等于 memcpy**

复制操作要保持类型的语义合同。它可能逐成员复制、分配新 payload、更新引用计数或复制 view 元数据。trivially copyable 的表示复制规则也不赋予任意资源 owner 用 memcpy 克隆清理责任的许可。

**View 的复制不是数据深复制**

span 的逻辑值是访问范围，复制后仍指向同一底层数据。因此两个 view 对象独立，但其元素访问存在别名。说“复制成功”时必须说明复制的是 view 还是被观察的数据。

**Shared Owner 的复制**

[机制片段 · 不承诺独立编译]

```cpp
auto a = std::make_shared<Model>();
auto b = a;
```

新建的是 b 这个 shared_ptr 对象，而不是第二个 Model。两个句柄共同参与管理同一资源；若需独立模型，应定义模型复制/clone 的操作，不要把复制 shared_ptr 当作快照。

**Move-only 仍可表达完整的值抽象**

FileDescriptor、unique_ptr、FrameLease 可以有明确的空/拥有状态和转移协议，只是不允许复制同一责任。不可复制不是“没有值语义”；是否能深复制独立资源仍由类型合同决定。

<a id="g3-part-3"></a>

### 1.4 Copy Cost Model

**同一语法对应不同工作**

int 复制标量；array<T, N> 处理内嵌元素；vector<T> 复制时可能分配并复制 N 个元素；span 复制范围；shared_ptr 复制管理关系并更新计数。语法越相似，越需要回到类型。

**sizeof 只描述对象本体**

对内嵌定长数据，复制成本可能与大小相关；对外部拥有者，payload 规模可能远大于对象本体。也不能把更大的 sizeof 直接解释成更慢：需要结合访问模式、编译器优化与硬件。

**Inline 与 Indirect**

inline 把数据放在对象内部，减少访问跳转，但迁移对象需要处理内嵌数据。indirect 多一层访问，却可能仅交接外部存储句柄。所谓“移动便宜”常来自这一表示选择，而不是关键字本身。

**成本递归组合**

[机制片段 · 不承诺独立编译]

```cpp
struct RobotState {
    std::string name;
    std::vector<float> joints;
    Pose pose; // 片段：Pose 由应用定义。
};
```

分析其复制，要分别检查三个成员；vector<T> 又要检查每个 T。可用“分配＋元素操作＋同步＋间接访问”列账，但它不是可直接相加的物理耗时公式，缓存与优化会改变结果。

**复制构造与复制赋值不是同一成本**

`T b = a;` 初始化新对象，`b = a;` 必须处理 b 的旧状态。已有容量可能复用，旧资源可能需要释放，allocator 条件也可能改变路径。benchmark 若把二者混测，就无法解释差异。

**O(1) 不等于 Cheap**

裸指针复制、共享计数更新、大型但固定大小的结构复制，都可能相对某个 N 是 O(1)，常数和机器行为却不同。报告成本时说明 N 是什么，并观察字节、分配、元素操作、同步、缓存和延迟分布。

<a id="g3-section-2"></a>

## 2. 实验 · G3-L1：复制的是完整值，还是访问关系？

<a id="g3-lab-copy"></a>

**预测：**修改 vector 副本、span 副本、shared_ptr 副本各会影响谁？完整运行例使用完整范围比较，既检查内容，也检查长度，避免空结果被前缀比较误判通过。

<!-- g-lab {"id":"G3-L1","mode":"run","stdout":"value-independent; view-aliases; shared-aliases\n"} -->
[完整实验 · G3-L1 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <algorithm>
#include <iostream>
#include <memory>
#include <span>
#include <vector>

int main() {
    const int expected[]{1, 2, 3};
    std::vector<int> source{1, 2, 3};
    auto copy = source;
    if (!std::ranges::equal(copy, expected)) return 1;
    if (copy.data() == source.data()) return 2;
    copy[0] = 9;
    if (source[0] != 1) return 3;

    std::span<int> view{source};
    auto view_copy = view;
    view_copy[1] = 8;
    const int changed[]{1, 8, 3};
    if (!std::ranges::equal(source, changed) ||
        view_copy.data() != source.data()) return 4;

    auto owner = std::make_shared<int>(4);
    auto shared = owner;
    *shared = 7;
    if (shared.get() != owner.get() || *owner != 7) return 5;
    std::cout << "value-independent; view-aliases; shared-aliases\n";
}
```

**原因：**vector 副本拥有独立元素；span 副本复制访问范围；shared_ptr 副本复制共同管理同一对象的句柄。三个语法相似的 copy，复制的逻辑值并不相同。

**改变条件：**把 vector 副本缩成一个元素，范围相等检查必须失败；只比较副本长度的前缀会漏掉这个错误。此变体作为本批执行器的定向自查，不改正文正确实现。

**边界：**这里元素是 int。若 vector 的元素本身是 span 或 shared_ptr，复制外层容器不会递归消除内层别名。

<a id="g3-part-4"></a>

<a id="g3-section-3"></a>

## 3. 平凡复制与对象表示

### 3.1 Triviality

**Trivial Copy**

例如：

[机制片段 · 不承诺独立编译]

```cpp
struct Sample {
    std::uint64_t timestamp;
    float value;
    std::uint32_t signal_id;
};
```

可以检查：

[机制片段 · 不承诺独立编译]

```cpp
static_assert(std::is_trivially_copyable_v<Sample>);
```

这种类型非常适合：

```text
dense arrays
bulk data movement
telemetry
sensor samples
```

**`trivially copyable` 不等于 Wire Format**

仍然要考虑：

```text
endianness
padding
ABI
alignment
schema version
floating representation
```

所以：

[机制片段 · 不承诺独立编译]

```cpp
send(fd, &sample, sizeof(sample), ...);
```

不自动成为正确跨系统 serialization。

<a id="g3-part-5"></a>

<a id="g3-section-4"></a>

## 4. 移动、异常保证与复制消除

### 4.1 Move Semantics

**Copy 与 Move 的根本区别**

Copy：

[机制片段 · 不承诺独立编译]

```cpp
T b = a;
```

要求：

```text
a logical value preserved
b obtains equivalent logical value
```

Move：

[机制片段 · 不承诺独立编译]

```cpp
T b = std::move(a);
```

允许：

```text
a logical state changes
b reuses/transfers a's existing state/resource
```

所以 move 的性能潜力来自：**Source value no longer needs to be preserved.**

**从转换到真正操作，中间还有重载决议**

**问题：**如果类型只有复制构造，写 std::move 会强行生成移动构造吗？

不会。对对象表达式，std::move 提供 xvalue（值类别定义见 [G1 §5](g01-object-model.md#g1-category)）；其概念形式是 `static_cast<std::remove_reference_t<T>&&>(x)`，其中 T 是推导出的模板参数。后续初始化、赋值或消费函数才选择并执行实际操作。

不能把“调用者允许消费源状态”说成语言已经证明可以安全消费。候选中可能有移动、有可绑定右值的复制，或者有被删除的最优函数而直接报错。“没声明移动”和“显式删除移动”不是同一个重载集合。下面实验先验证最常混淆的 const 和 copy-only 两条路径。

**为什么普通 vector 移动构造很便宜？**

vector 的元素通常在外部分配的连续存储中，普通 `vector(vector&&)` 可以交接这份存储，复杂度为常数；复制构造需复制元素，工作量随 N 增长。

**边界：**显式带 allocator 的移动构造，以及移动赋值，在 allocator 不兼容或不能传播时可能逐元素处理；不能把所有带 move 字样的操作都标成 O(1)。目标原有资源的清理也可能是成本。array 的元素内嵌，不能只交接一个外部缓冲区句柄。

**为什么 Array Move 仍可能 O(N)**

[机制片段 · 不承诺独立编译]

```cpp
std::array<T, N>
```

elements inline。

没有：

```text
allocation handle
```

可以直接 transfer。

所以：

```text
move array
≈ move N elements
```

对于 scalar T：

```text
move ≈ copy
```

因此：**Move syntax does not imply O(1).**

**Move Cost 来自 Representation**

```text
Indirect owner
→ transfer handle
→ often cheap

Inline payload
→ transfer payload itself
→ often similar to copy
```

**Moved-from ≠ Dead**

移动后，源对象通常仍在生命周期内，但值可能改变。标准库类型通常给出 valid-but-unspecified 的移动后合同，具体类型可给更强保证，例如相应 unique_ptr 转移后源为空。

对用户类型，语言不会自动修复错误的移动实现；要自行维持承诺的不变量和清理能力。操作还有自身前置条件：不能因为 vector 可析构，就无条件调用它的 front()。也不要要求所有 moved-from 容器都为空。

区分三件事：对象是否仍活着、哪些操作允许、逻辑值是否保持。它们不是同一个问题。

**`const` 与 Move**

[机制片段 · 不承诺独立编译]

```cpp
const T value;
T copy = std::move(value);
```

`std::move(value)`产生：

```text
const T&&
```

而普通 move constructor：

[机制片段 · 不承诺独立编译]

```cpp
T(T&&)
```

通常无法接受 const source。

因为 move经常需要：修改 source state。

所以经常回退：

```text
copy via const T&
```

必须记：**`std::move(const T)` 经常不会真正 move。**

<a id="g3-part-6"></a>

### 4.2 `noexcept` Move

**`noexcept` 不只是 Optimization Hint**

[机制片段 · 不承诺独立编译]

```cpp
T(T&&) noexcept;
```

表达：move不会让 exception逃出。

这会直接影响：

```text
generic algorithms
containers
vector relocation
```

**为什么 Vector 会关心？**

reallocation：

```text
allocate new storage
↓
construct old elements in new storage
```

若 move：

```text
可能修改 source
并可能 throw
```

做到一半失败：rollback困难。

若 copy：

```text
source unchanged
```

新 storage失败：可以直接丢弃 partial copies。

所以：

```text
noexcept move
```

通常让 container更安全地选择 cheap move path。

**Move-only + Throwing Move**

这是非常棘手组合：

```text
copy impossible
move may throw
```

container不能 fallback copy。

因此对 resource owner：

```text
move-only
O(1)
noexcept
simple empty state
```

是很好的设计目标。

<a id="g3-part-7"></a>

### 4.3 Copy Elision / RVO / NRVO

**最好的 Move 是没有 Move**

现代性能层级经常是：

```text
Copy
↓
Move
↓
Direct Construction / Elision
```

**C++17+ Same-type Prvalue**

[机制片段 · 不承诺独立编译]

```cpp
T make() {
    return T{};
}
```

现代模型：

```text
result object
↓
T constructed directly there
```

不是：

```text
temporary T
↓ move
result T
```

因此：move constructor甚至可以不存在。

**Guaranteed Case**

[机制片段 · 不承诺独立编译]

```cpp
class Immovable {
public:
    Immovable() = default;
    Immovable(const Immovable&) = delete;
    Immovable(Immovable&&) = delete;
};

Immovable make() {
    return Immovable{};
}
```

C++17+ 可以成立。

这证明：guaranteed copy elision不是“更快的 move”。

**NRVO**

[机制片段 · 不承诺独立编译]

```cpp
T make() {
    T value;
    return value;
}
```

`value` 是 named local。

这是：Named Return Value Optimization。

NRVO成功：

```text
local value
和
function result
实际上对应同一个最终 object
```

**Guaranteed Prvalue Case ≠ NRVO**

必须区分：

[机制片段 · 不承诺独立编译]

```cpp
return T{};
```

和：

[机制片段 · 不承诺独立编译]

```cpp
T value;
return value;
```

前者 C++17+ same-type result construction有更强语义保证。

后者：NRVO仍是 permitted/expected，但不是同等级 guaranteed case。

**NRVO Failure → Implicit Move**

[机制片段 · 不承诺独立编译]

```cpp
T make() {
    T value;
    return value;
}
```

如果 NRVO不发生，eligible local可走：

```text
implicit move
```

所以通常不需要：

[机制片段 · 不承诺独立编译]

```cpp
return std::move(value);
```

**`return std::move(local)` 是典型 Smell**

[机制片段 · 不承诺独立编译]

```cpp
T make() {
    T value;
    return std::move(value);
}
```

`std::move(value)` 是 xvalue。

通常：不再保持简单 NRVO candidate形式。

因此可能从：

```text
0 transfers
```

退化成：

```text
1 move
```

所以 ordinary local return默认：

[机制片段 · 不承诺独立编译]

```cpp
return value;
```

<a id="g3-section-5"></a>

## 5. 实验 · G3-L2～L4：转换、重载与结果对象

<a id="g3-lab-move"></a>

**G3-L2：const 与 copy-only 的反直觉路径**

先写出四次构造分别调用什么。计数来自明确定义的构造函数，不测 vector 的实现选择。

<!-- g-lab {"id":"G3-L2","mode":"run","stdout":"copies=2 moves=1 copy-only=1\n"} -->
[完整实验 · G3-L2 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <iostream>
#include <utility>

struct Tracked {
    static inline int copies = 0, moves = 0;
    Tracked() = default;
    Tracked(const Tracked&) { ++copies; }
    Tracked(Tracked&&) noexcept { ++moves; }
};

struct CopyOnly {
    static inline int copies = 0;
    CopyOnly() = default;
    CopyOnly(const CopyOnly&) { ++copies; } // 没有声明移动构造。
};

int main() {
    Tracked source;
    Tracked a{source};
    Tracked b{std::move(source)};
    const Tracked fixed;
    Tracked c{std::move(fixed)};
    CopyOnly original;
    CopyOnly d{std::move(original)};
    if (Tracked::copies != 2 || Tracked::moves != 1 ||
        CopyOnly::copies != 1) return 1;
    std::cout << "copies=2 moves=1 copy-only=1\n";
}
```

a 复制，b 移动，c 的 const 右值不能绑定普通 Tracked&& 因而复制；d 可绑定 const CopyOnly&，所以复制。显式删除 CopyOnly(CopyOnly&&) 会让它成为更优但不可调用的候选，这是手动扩展，不能继续期待复制回退。

**G3-L3：不需要复制/移动的 prvalue 返回**

<!-- g-lab {"id":"G3-L3","mode":"run","stdout":"direct-result=7\n"} -->
[完整实验 · G3-L3 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <iostream>

struct Immovable {
    int value;
    explicit Immovable(int n) : value(n) {}
    Immovable(const Immovable&) = delete;
    Immovable(Immovable&&) = delete;
};

Immovable make() { return Immovable{7}; }

int main() {
    auto value = make();
    if (value.value != 7) return 1;
    std::cout << "direct-result=7\n";
}
```

这里同类型 prvalue 直接初始化结果对象，不需要先建立一个源临时再移动。删除复制/移动仍可成立；这不同于“优化器碰巧删掉了一次 move”。

**G3-L4：具名局部返回不能靠可选 NRVO 挽救非法程序**

完整**编译失败反例**：

<!-- g-lab {"id":"G3-L4","mode":"compile_fail","diagnostic":"(?:deleted constructor|call to deleted|use of deleted)[\\s\\S]*Immovable"} -->
[反例 · 编译失败 · G3-L4 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
struct Immovable {
    Immovable() = default;
    Immovable(const Immovable&) = delete;
    Immovable(Immovable&&) = delete;
};

Immovable make() {
    Immovable local;
    return local;
}
int main() { auto value = make(); }
```

NRVO 是允许的省略，不让本来选到已删除构造函数的程序变合法。预期是针对 Immovable 的 deleted-constructor 诊断，不是任何编译失败。

**反思：**`return local;` 符合 NRVO 条件时应保留机会；改成 `return std::move(local);` 会使这条 NRVO 规则不再适用。不要用一个编译器、一次 -O0 计数结果宣称所有返回都复制或都不复制。[N4950：class.copy.elision](https://timsong-cpp.github.io/cppwp/n4950/class.copy.elision)

<a id="g3-part-8"></a>

<a id="g3-section-6"></a>

## 6. 返回值、参数与借用边界

### 6.1 Return-by-Value Cost Model

看到：

[机制片段 · 不承诺独立编译]

```cpp
T result = make_t();
```

不要问：“复制几次？”

而应该拆成：

```text
1. ConstructCost(T)
2. Result placement
3. Transfer cost
4. Dynamic resource work
5. ABI lowering
```

现代理想：

```text
TransferCost = 0
```

但：

```text
construct payload
allocate
I/O
decode
```

这些真实工作不会因为 elision消失。

<a id="g3-part-9"></a>

### 6.2 Parameter Passing

**参数类型首先是 Semantic Contract**

不是：

```text
哪个写法最快？
```

而是：

```text
callee要：
borrow?
own?
consume?
mutate?
view?
share?
```

**`T`**

[机制片段 · 不承诺独立编译]

```cpp
void f(T value);
```

表示：callee获得自己的 T value。

caller lvalue：

```text
copy
```

caller xvalue：

```text
重载决议可能选择 move、copy，或因无可行操作而失败
```

same-type prvalue：

```text
direct parameter construction可能消除不必要 transfer
```

**`const T&`**

[机制片段 · 不承诺独立编译]

```cpp
void f(const T& value);
```

表示：required read-only borrow。

适合：

```text
large expensive-to-copy value
callee只同步读取
```

**`T&`**

[机制片段 · 不承诺独立编译]

```cpp
void f(T& value);
```

表示：required mutable borrow。

函数修改：caller-visible object。

**`T&&`**

非模板：

[机制片段 · 不承诺独立编译]

```cpp
void consume(T&& value);
```

表示：rvalue reference to a consumable object。

但：reference本身不是 ownership transfer。

真正 transfer通常发生在：

[机制片段 · 不承诺独立编译]

```cpp
store(std::move(value));
```

**Named `T&&` 仍然是 Lvalue Expression**

[机制片段 · 不承诺独立编译]

```cpp
void consume(T&& value) {
    sink(value);             // lvalue
    sink(std::move(value));  // xvalue
}
```

类型：

```text
T&&
```

与表达式 category：

```text
lvalue
```

必须分开。

<a id="g3-part-10"></a>

### 6.3 Sink Parameters

如果函数最终需要：保存自己的 value。

典型：

[机制片段 · 不承诺独立编译]

```cpp
class Robot {
public:
    explicit Robot(std::string name)
        : name_(std::move(name)) {}

private:
    std::string name_;
};
```

这里：

```text
T by value
+
move into member
```

常适合：

```text
copy expensive
move cheap
```

的 type。

例如：

```text
string
vector
Frame
```

**Lvalue Caller**

```text
copy into parameter
+
cheap move into member
```

**Rvalue Caller**

```text
move/direct construct parameter
+
cheap move into member
```

所以：by-value sink 是 API simplicity 与性能之间很好的折中。

<a id="g3-part-11"></a>

### 6.4 Small Values

例如：

[机制片段 · 不承诺独立编译]

```cpp
struct RobotId {
    std::uint64_t value{};
};
```

通常：

[机制片段 · 不承诺独立编译]

```cpp
Robot* find_robot(RobotId id);
```

优于：

[机制片段 · 不承诺独立编译]

```cpp
Robot* find_robot(const RobotId& id);
```

原因：

```text
small
cheap copy
register-friendly
no aliasing relation
no lifetime dependency
```

**Strong Small Types**

包装：

```text
uint64_t → RobotId
int64_t → Timestamp
```

通常不产生有意义性能损失。

却带来：

```text
type safety
API clarity
semantic distinction
```

这是典型 zero-overhead abstraction。

<a id="g3-part-12"></a>

### 6.5 Views

**`std::span<T>`**

[机制片段 · 不承诺独立编译]

```cpp
void process(std::span<const Sample> samples);
```

表达：

```text
non-owning
contiguous
bounded
read-only sequence view
```

它不要求 caller是：

```text
vector
```

所以 API表达的是：data shape

而不是：owner/container representation。

**为什么 Span By Value**

span本身通常只是：

```text
pointer
+
extent
```

cheap to copy。

所以：

[机制片段 · 不承诺独立编译]

```cpp
void process(std::span<const T> values);
```

而不是：

[机制片段 · 不承诺独立编译]

```cpp
void process(const std::span<const T>& values);
```

**`std::string_view`**

同样：

[机制片段 · 不承诺独立编译]

```cpp
void parse(std::string_view text);
```

适合：character-sequence borrow。

但如果函数/class需要长期保存：string_view并不拥有 characters。

需要重新做 ownership decision。

<a id="g3-part-13"></a>

### 6.6 Borrow vs Ownership Boundary

同步：

[机制片段 · 不承诺独立编译]

```cpp
void inspect(const Frame& frame);
```

owner在 caller，borrow只覆盖 call。

异步：

[机制片段 · 不承诺独立编译]

```cpp
submit(...)
```

调用返回后 task继续运行。

因此：**Async boundary often becomes ownership boundary。**

不能把：

[机制片段 · 不承诺独立编译]

```cpp
const Frame&
span
T*
```

随便保存进 async callback。

必须选择：

```text
copy
move
shared ownership
lease
```

之一。

<a id="g3-part-14"></a>

### 6.7 Aliasing 与 Parameter Performance

Reference：

[机制片段 · 不承诺独立编译]

```cpp
void f(const Vec3& a, const Vec3& b);
```

允许潜在：

```text
a and b alias
```

Value：

[机制片段 · 不承诺独立编译]

```cpp
void f(Vec3 a, Vec3 b);
```

parameters是独立 local values。

对 small scalar/aggregate，by value可能：

```text
更容易 registerize
减少 aliasing constraints
减少 lifetime relationships
```

所以：reference不只是“省 copy”。

它也改变 optimizer的 memory model。

<a id="g3-part-15"></a>

<a id="g3-section-7"></a>

## 7. 容器迁移与稳定身份

### 7.1 Container Relocation

**`size` vs `capacity`**

```text
size
=
live T object count

capacity
=
storage capacity for up to N T objects
```

所以：

[机制片段 · 不承诺独立编译]

```cpp
values.reserve(100);
```

不是：构造100个 T。

而是：准备 storage。

**Reallocation**

capacity不足：

```text
old storage
[T][T][T][T]

↓ allocate bigger storage

new raw storage

↓ construct new T objects from old values

↓ destroy old T objects

↓ deallocate old storage
```

重点：**这是 object lifetime migration，不只是 bytes copy。**

**Move Constructor ≠ Object Teleportation**

[机制片段 · 不承诺独立编译]

```cpp
T b = std::move(a);
```

是：

```text
new T object b begins lifetime
a remains alive
```

不是：同一个 object直接改地址。

所以：

```text
Move
≠
Relocation
```

**Reallocation Invalidation**

old element lifetimes结束。

所以：

```text
T*
T&
iterator
```

若指向旧 vector elements：reallocation后失效。

pointer object自己并没改变。

是：backing object relationship失效。

<a id="g3-part-16"></a>

### 7.2 `reserve()`

`reserve()` 价值不仅是：

```text
reduce allocations
```

还可以：

```text
reduce element moves/copies
reduce address invalidation
move latency out of hot path
improve tail-latency predictability
```

但：

[机制片段 · 不承诺独立编译]

```cpp
values.reserve(n);
```

本身如果 capacity不足，也会：reallocate并立即invalidate旧 element references。

<a id="g3-part-17"></a>

### 7.3 Amortized Complexity

vector几何增长使：

```text
push_back
→ amortized O(1)
```

但单次 expansion：

```text
O(N)
```

所以：amortized O(1) ≠ every operation O(1)。

对于 realtime：

```text
average latency
```

可能不重要。

更关心：

```text
worst-case / bounded latency
```

因此：

```text
reserve
fixed-capacity storage
ring buffer
pool
```

经常重要。

<a id="g3-part-18"></a>

### 7.4 `vector<T>` vs `vector<unique_ptr<T>>`

**Dense Value Storage**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<Detection>
```

布局：

```text
[D][D][D][D]
```

优点：

```text
contiguous
few allocations
prefetch-friendly
cache-friendly
```

缺点：

```text
element addresses can change on reallocation
```

**Pointerized Storage**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<std::unique_ptr<Detection>>
```

布局：

```text
[p][p][p][p]
 │  │  │  │
 ▼  ▼  ▼  ▼
 D  D  D  D
```

优点：

```text
pointee address stable across outer vector growth
dynamic polymorphism friendly
```

代价：

```text
N allocations
N indirections
fragmentation
poor locality
```

因此：不要仅为地址稳定就 pointerize small value types。

<a id="g3-part-19"></a>

### 7.5 Stable ID vs Stable Address

如果 domain identity是：

[机制片段 · 不承诺独立编译]

```cpp
TrackId{42}
```

那么 Track object storage可以：

```text
move
compact
reallocate
```

只要 TrackId不变。

因此：**Address is a storage property, not necessarily domain identity。**

许多系统更适合：

```text
stable ID
+
central owner
```

而不是：

```text
heap everything to get stable addresses
```

<a id="g3-part-20"></a>

<a id="g3-section-8"></a>

## 8. 对象表示策略

### 8.1 Representation Strategies

**Inline**

```text
payload inside object
```

例如：

```text
int
Vec3
array<T,N>
```

优点：

```text
no allocation
good locality
simple lifetime
```

缺点：

```text
object large
move may be same as copy
```

**Indirect**

```text
small wrapper
→ external payload
```

例如：

```text
vector
PImpl
heap buffer
```

优点：

```text
small object
stable payload address possible
cheap move
```

代价：

```text
allocation
indirection
cache miss
```

**Hybrid**

```text
small runtime value
→ inline

large runtime value
→ indirect
```

例如常见：

```text
std::string SSO
small-function/SBO wrappers
small-vector abstractions
```

<a id="g3-part-21"></a>

### 8.2 SSO / SBO

**Small String Optimization**

常见 std::string实现：

```text
short string
→ characters inline

long string
→ heap storage
```

因此：

```text
short copy
→ maybe no allocation

long copy
→ allocation + O(N)

short move
→ small inline transfer

long move
→ handle transfer
```

**SSO Threshold 不是 Portable Guarantee**

不要依赖：

```text
<= 15 / 22 / 23 chars
```

这种具体值。

它属于：

```text
stdlib implementation
ABI
toolchain
```

**SBO Trade-off**

```text
larger wrapper
↕
fewer small-object allocations
```

如果 inline buffer太大：

```text
cache density ↓
vector relocation bytes ↑
object footprint ↑
ABI constraints ↑
```

所以：SBO不是越大越好。

<a id="g3-part-22"></a>

### 8.3 Performance Cliff

Hybrid representation存在 threshold：

```text
size <= N
→ inline

size > N
→ heap
```

因此 runtime cost可能：

```text
N
→ no allocation

N+1
→ allocation + migration
```

产生：performance cliff。

所以 benchmark不能只测：

```text
one tiny string
```

应看真实：

```text
value-size distribution
histogram
percentiles
```

<a id="g3-part-23"></a>

### 8.4 `optional<T>`

`std::optional<T>` 概念：

```text
storage for T
+
engaged state
```

empty：

```text
T storage exists
T lifetime inactive
```

engaged：

```text
T object lifetime active
```

再次体现：Storage exists ≠ object alive。

**`optional<Large>` Empty 仍可能很大**

因为 wrapper必须：随时能够 inline容纳一个 Large。

所以：

```text
empty optional
≠
pointer-sized
```

大量 sparse large optionals可能并不适合 inline representation。

<a id="g3-part-24"></a>

### 8.5 `variant`

[机制片段 · 不承诺独立编译]

```cpp
std::variant<A, B, C>
```

需要：

```text
storage for largest alternative
+
active tag
```

因此 size通常主要由：

```text
max(sizeof(A), sizeof(B), sizeof(C))
```

决定。

运行时 operation cost：取决于当前 active alternative。

还要处理可能的 valueless_by_exception 状态：某些抛异常的类型改变操作之后可能没有 active alternative。存储足够容纳候选类型，不等于一直存在其中一个活对象。

所以：

```text
same static type
different runtime state
different operation cost
```

<a id="g3-part-25"></a>

<a id="g3-section-9"></a>

## 9. 值导向架构与生命周期解耦

### 9.1 Value-oriented Architecture

高性能 C++ 不等于：

```text
everything inline
everything by value
```

真正目标：

```text
small metadata
→ value

large unique payload
→ movable owner

synchronous algorithm input
→ borrow/view

independent immutable generations
→ narrow shared ownership

pooled resource
→ lease

hot collections
→ dense value containers

identity
→ stable ID when possible
```

<a id="g3-part-26"></a>

### 9.2 Large Logical Value 可以仍然是 Small Movable Object

例如：

[机制片段 · 不承诺独立编译]

```cpp
struct InferenceRequest {
    RequestId id;
    Timestamp timestamp;
    std::shared_ptr<const Model> model;
    FrameLease frame;
};
```

它代表：

```text
large model
large frame
```

但 object representation可能只有：

```text
small values + small handles
```

Move：

```text
RequestId
→ cheap

Timestamp
→ cheap

shared_ptr
→ handle transfer

FrameLease
→ lease transfer
```

所以：**Logical payload size ≠ object size ≠ move cost。**

<a id="g3-part-27"></a>

### 9.3 Copy as Decoupling

Copy 不只是：data movement。

它还可以购买：

```text
lifetime independence
thread independence
storage abstraction
generation independence
```

例如 small metadata：

[机制片段 · 不承诺独立编译]

```cpp
FrameMetadata metadata = frame.metadata();
```

几十 bytes copy。

换：Detection result 不再依赖 Frame lifetime。

这可能是优秀 trade-off。

<a id="g3-part-28"></a>

### 9.4 Zero-copy

Zero-copy通常真正表示：避免主要 large payload duplication。

仍会复制：

```text
metadata
pointer
size
lease
handle
```

所以：Zero-copy ≠ zero data movement。

**Zero-copy 的代价**

```text
less memory bandwidth
↓
more lifetime coupling
aliasing
reuse coordination
possibly synchronization
```

必须记：**Zero-copy turns bandwidth cost into coordination cost.**

**Shared Immutable Data**

如果多个 consumers共享大 payload，最好：

```text
shared
+
immutable
```

这样主要解决：

```text
lifetime
```

而不是额外解决：

```text
data race
synchronization
consistency
```

<a id="g3-part-29"></a>

### 9.5 Pool + Lease

Pool：

```text
owns backing storage
```

Lease：

```text
owns temporary usage right
```

不是：

```text
lease owns allocation
```

cleanup：

```text
last/use lease ends
→ return slot to pool
```

而不是：

```text
delete buffer
```

**Pool Stale View**

Pool reuse时：

```text
same memory address
new generation
```

旧 span/pointer可能：

```text
address still mapped
but logical data generation changed
```

因此：address-valid ≠ lifetime-valid ≠ generation-valid。

ASan也未必能发现。

<a id="g3-part-30"></a>

<a id="g3-section-10"></a>

## 10. 成本图与接口决策

### 10.1 Cost Graph

高性能代码不要只画 Ownership Graph。

还应该画：

### 10.2 Value/Copy/Move Graph

```text
where values are:
copied
moved
directly constructed
borrowed
```

### 10.3 Allocation Graph

```text
startup allocations
per-frame allocations
per-item allocations
control blocks
temporary storage
```

### 10.4 Indirection Graph

```text
object
↓
pointer
↓
object
↓
PImpl
↓
payload
```

每个 pointer可能增加：cache-miss risk。

### 10.5 Lifetime/Invalidation Graph

```text
who borrows?
what invalidates?
reallocation?
erase?
pool reuse?
generation replacement?
shutdown?
```

<a id="g3-part-31"></a>

### 10.6 Performance Cost Axes

完整 cost model：

```text
1. Bytes moved
2. Allocation count
3. Deallocation count
4. Object construction/destruction
5. Element copy/move
6. Atomic/refcount operations
7. Locks
8. Pointer indirections
9. Cache footprint
10. Reallocation
11. Invalidation
12. Lifetime coordination
13. Tail latency
14. ABI/layout constraints
```

所以：**Big-O is necessary but not sufficient。**

<a id="g3-part-32"></a>

### 10.7 Copy Cost Equation

工程近似：

```text
CopyCost(T)
≈
InlineBytesMoved
+
Allocations
+
OwnedPayloadCopy
+
Σ MemberCopyCost
+
Synchronization
+
Cache/MemoryTraffic
+
RepresentationTransition
```

Move：

```text
MoveCost(T)
≈
StateTransfer
+
DestinationOldStateCleanup
+
Σ MemberMoves
+
AllocatorConstraints
+
InvariantRepair
+
Synchronization
```

<a id="g3-part-33"></a>

### 10.8 Parameter Decision Model

先问语义：

```text
Does callee:
borrow?
own?
mutate?
consume?
view?
share?
```

然后才问性能。

默认：

| 语义                                 | C++ 首选起点         |
| ------------------------------------ | -------------------- |
| small independent value              | `T`                  |
| callee needs own value               | `T`                  |
| large read-only borrow               | `const T&`           |
| required mutable borrow              | `T&`                 |
| optional observer                    | `T*`                 |
| contiguous sequence borrow           | `std::span<T>`       |
| text borrow                          | `std::string_view`   |
| unique owner transfer                | `std::unique_ptr<T>` |
| shared lifetime acquisition          | `std::shared_ptr<T>` |
| move-only lease/value transfer       | `T`                  |
| explicit consume-only existing value | sometimes `T&&`      |

<a id="g3-part-34"></a>

### 10.9 Container Review Model

看到：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<T>
```

问：

```text
T copy cost?
T move cost?
T move noexcept?
T address-sensitive?
T value-like?
stable address required?
growth frequency?
reserve possible?
what borrows elements?
what invalidates them?
```

Container performance：是 element semantics 与 storage topology 的组合。

<a id="g3-part-35"></a>

### 10.10 Healthy High-performance Pipeline

典型：

```text
Small control/meta values
        ↓
       T

Large unique payload
        ↓
cheap movable owner / lease

Synchronous stage access
        ↓
span / const& / T&

Independent large immutable generation
        ↓
shared_ptr<const T>

Long-lived identity
        ↓
stable logical ID

Hot collections
        ↓
dense contiguous values
```

<a id="g3-part-36"></a>

<a id="g3-section-11"></a>

## 11. 跨语言回查

### 11.1 C++ vs Zig

**C++**

```text
copy/move/destructor
→ heavily encoded in type operations

value syntax
→ can hide expensive semantic work

RVO/NRVO/elision
→ powerful destination construction
```

**Zig**

```text
ordinary value operations simpler
clone/resource duplication generally explicit
allocator commonly explicit
result-location semantics
```

所以：

```text
C++
more semantic machinery behind ordinary syntax

Zig
more operational cost visible in APIs/control flow
```

<a id="g3-part-37"></a>

### 11.2 C++ vs Rust

Rust：

```text
non-Copy T assignment
→ ownership move

source usually becomes statically unusable
```

C++：

```text
lvalue
→ copy if copyable

std::move(x)
→ explicitly expose xvalue
source remains live moved-from object
```

Rust静态保证更多 lifetime规则。

但：

```text
cache
layout
allocation
Vec relocation
Arc refcount
AoS/SoA
```

仍然必须由工程师设计。

<a id="g3-part-38"></a>

<a id="g3-section-12"></a>

## 12. 工程审查与常见误判

### 12.1 Code Review Protocol

对 performance-sensitive code：

**Step 1 — Identify Logical Values**

这个 type 到底表示什么？

**Step 2 — Classify Representation**

```text
inline
indirect
hybrid
```

**Step 3 — Locate Large Payloads**

```text
vectors
buffers
images
matrices
strings
models
```

**Step 4 — Mark Every Copy**

判断：

```text
small value copy?
deep payload copy?
view copy?
shared ownership copy?
```

**Step 5 — Mark Every Move**

问：

```text
who consumes?
what is transferred?
cheap?
O(1)?
noexcept?
```

**Step 6 — Review Returns**

[机制片段 · 不承诺独立编译]

```cpp
return T{};
return local;
return std::move(local);
```

明确：

```text
guaranteed direct construction
NRVO
pessimizing move
```

**Step 7 — Review Parameters**

确认接口真正表达：

```text
borrow
own
consume
view
share
```

**Step 8 — Review Containers**

问：

```text
why this container?
why pointerized?
why not dense values?
reserve?
invalidation?
```

**Step 9 — Count Allocations**

特别查：

```text
per item
per request
per frame
per callback
```

**Step 10 — Count Indirections**

每一层 pointer都问：why?

**Step 11 — Review Lifetime of Views**

```text
span
string_view
reference
pointer
iterator
```

谁 backing？

何时 invalid？

**Step 12 — Measure**

使用：

```text
benchmark
allocation counters
profilers
assembly
hardware counters
```

验证 hot path。

<a id="g3-part-39"></a>

### 12.2 高频 Smells

**1**

[机制片段 · 不承诺独立编译]

```cpp
return std::move(local);
```

普通 local return：NRVO pessimation smell。

**2**

[机制片段 · 不承诺独立编译]

```cpp
std::vector<std::unique_ptr<SmallValue>>
```

没有 polymorphism/stable address原因：pointerization smell。

**3**

[机制片段 · 不承诺独立编译]

```cpp
const TinyStruct&
```

机械 const-ref：cargo-cult borrow。

**4**

[机制片段 · 不承诺独立编译]

```cpp
std::shared_ptr<T>
```

只因为 many users：ownership uncertainty。

**5**

[机制片段 · 不承诺独立编译]

```cpp
const std::vector<T>&
```

函数实际只需要：

```text
contiguous sequence
```

考虑 span。

**6**

保存：

```text
span
string_view
T*
T&
```

却没有 backing lifetime contract。

**7**

为了“zero-copy”：

```text
shared_ptr everything
```

可能将简单 memory copy换成更昂贵 lifetime/refcount/cache成本。

**8**

已知 batch size，但 hot path vector不 reserve。

**9**

为了 stable address而 heap allocate所有 small objects。

**10**

使用 copy/move constructor side effects承担业务 correctness。

Elision可能让这些 operations根本不发生。

<a id="g3-part-40"></a>

<a id="g3-section-13"></a>

## 13. 术语与统一模型

### 13.1 Core Terminology

| English                 | 中文核心含义                                         |
| ----------------------- | ---------------------------------------------------- |
| Logical Value           | 类型对外表示的语义值                                 |
| Representation          | object在机器中的内部表示                             |
| Value Semantics         | object copy/move所定义的逻辑值关系                   |
| Copy Construction       | 从已有对象创建新对象值                               |
| Copy Assignment         | 用已有值替换已存在对象状态                           |
| Move Construction       | 从可消费source建立新对象                             |
| Move Assignment         | 用可消费source替换已有target状态                     |
| Moved-from State        | move后source仍存活的合法状态                         |
| Copy Elision            | 不建立/不转移某些中间对象                            |
| RVO                     | Return Value Optimization                            |
| NRVO                    | Named Return Value Optimization                      |
| Result Object           | 函数调用返回值最终对应的对象                         |
| Inline Representation   | payload直接存在object内部                            |
| Indirect Representation | object通过handle/pointer管理外部payload              |
| Hybrid Representation   | runtime按状态在inline/indirect之间切换               |
| SSO                     | Small String Optimization                            |
| SBO                     | Small Buffer/Object Optimization                     |
| Relocation              | 将值从一处storage迁移到另一处并结束旧object lifetime |
| Invalidation            | 之前合法的access path变为非法                        |
| Amortized Complexity    | 多次操作平均后的复杂度保证                           |
| Zero-copy               | 避免主要payload duplication                          |
| Stable ID               | 与物理storage address解耦的logical identity          |

<a id="g3-part-41"></a>

### 13.2 最终统一公式

```text
Performance(T, operation)
=
Logical Semantics
×
Representation
×
Runtime State
×
Storage Topology
×
Ownership/Lifetime Contract
```

或者更工程化：

```text
Cost
=
Bytes Moved
+
Allocations
+
Element Operations
+
Indirections
+
Synchronization
+
Cache Effects
+
Lifetime Coordination
```

因此：**C++ performance is semantic.**

<a id="g3-part-42"></a>

### 13.3 G1 + + Unified Mental Model

任何 access/value/resource问题，现在都可以按三层判断：

```text
Layer 1 — Validity

Does the object exist?
Is storage valid?
Is access in bounds?
Has it been invalidated?


Layer 2 — Ownership

Who keeps it alive?
Who cleans it up?
Who borrows?
Who shares?


Layer 3 — Cost

What is copied?
What is moved?
What is allocated?
How many indirections?
What layout reaches the CPU?
```

压缩：

```text
Correct?
↓
Owned correctly?
↓
Efficiently represented and moved?
```

<a id="g3-gate"></a>

<a id="g3-part-43"></a>

<a id="g3-section-14"></a>

## 14. Final Gate

### 14.1 Final Gate

必须能够独立解释：

**Value**

1. Logical value和object representation区别是什么？
2. Value semantics为什么不等于deep copy？
3. span/shared_ptr为什么也拥有自己的value semantics？
4. move-only type为什么仍能成为优秀value abstraction？

**Copy**

1. 为什么`sizeof(vector)`不能预测copy成本？
2. inline与indirect value copy成本有什么不同？
3. O(1)为什么不等于cheap？
4. copy为什么有时是lifetime-decoupling primitive？

**Move**

1. `std::move`真正做什么？
2. 为什么vector move常O(1)而array move O(N)？
3. moved-from object为什么仍然alive？
4. 为什么const常阻止真正move？
5. 为什么cheap resource-owner move应尽量`noexcept`？

**Elision**

 1. `return T{};`与`return local;`有什么区别？
 2. guaranteed copy elision与NRVO区别是什么？
 3. 为什么`return std::move(local)`通常是错误？
 4. 为什么return-by-value不等于copy-heavy API？

**Parameters**

 1. `T` / `const T&` / `T&` / `T&&`分别是什么semantic contract？
 2. small value为什么常by value？
 3. sink为什么常适合by value？
 4. span/string_view为什么通常by value？
 5. 为什么跨async boundary必须重新做ownership decision？

**Containers**

 1. vector size与capacity区别是什么？
 2. reallocation为什么开始新object lifetimes？
 3. 为什么pointer/reference/iterator失效？
 4. 为什么noexcept move影响vector relocation？
 5. reserve为什么同时是performance和lifetime工具？
 6. amortized O(1)为什么不适合直接推断realtime latency？

**Representation**

 1. inline / indirect / hybrid分别交换什么？
 2. SSO/SBO为什么能降低allocation？
 3. SBO为什么可能伤cache density？
 4. 为什么hybrid representation会产生performance cliff？
 5. optional/variant如何再次体现storage与object lifetime分离？

**Architecture**

 1. zero-copy真正消除了什么？
 2. zero-copy新增什么协调成本？
 3. stable ID为什么有时优于stable address？
 4. 为什么dense small values通常优于pointerized small values？
 5. 如何同时画ownership/cost/allocation/invalidation graph？

<a id="g3-section-15"></a>

## 15. Final Gate · 参考答案与常见误判

- **Value 1～4：**逻辑值是类型承诺表示的意义，representation 是实现它的状态。复制 view 复制访问关系，复制 shared_ptr 复制拥有关系，不是深复制目标。move-only 可表达只能交接的资源权利；误判是把 value 一律等同可复制大对象。
- **Copy 1～4：**vector 本体小，元素存储在外；inline 按内嵌状态处理，indirect owner 可能分配并复制 payload。O(1) 隐藏常数、同步和缓存成本；真正复制独立数据可以解耦生命周期，复制 view 不行。
- **Move 1～5：**std::move 是转换，随后才决议操作。普通 vector 移动构造交接存储，array 通常逐元素处理；allocator 相关重载另论。源仍活着，可用操作由合同限定。const 常阻止普通移动参数绑定；真实不抛的移动可帮助容器维持保证，不能为“快”谎报 noexcept。
- **Elision 1～4：**同类型 prvalue 可直接构造结果；具名局部的 NRVO 是可选的，相关操作仍须满足语言要求。return std::move(local) 排除了该 NRVO 条件，通常多余。按值返回可以直接构造或转移所有权，不等于深复制。
- **Parameters 1～5：**T 建立参数值，const T& 借用只读路径，T& 提供可变路径，具体非推导 T&& 接受右值但不自动消费。小值、view 通常复制元数据更自然；sink 按值可统一接收复制或转移，但要计入额外操作。异步越过调用范围，引用有效性需重新证明。
- **Containers 1～6：**size 数元素，capacity 数可容纳空间；重分配建立新元素并结束旧元素，使旧访问失效。复制/移动可行性和异常保证影响迁移策略。reserve 可控制部分重分配窗口，但不免除 erase 等失效；摊销均值也不限制单次延迟。
- **Representation 1～5：**inline 换局部性，indirect 换稳定句柄/可转移存储，hybrid 在运行时选择。SSO/SBO 减小对象的分配次数但增加 wrapper 大小，阈值切换可能突增成本。optional 可无值，variant 也可能 valueless_by_exception；字节空间存在不等于每个候选对象同时活着。
- **Architecture 1～5：**zero-copy 避免 payload 重复，不消除同步、保活和复用协调。ID 可与地址解耦，但需防陈旧代际；dense 小值常改善局部性，并非通用性能定理。为同一数据流分别标 owner、分配点、操作成本和失效点，才能看出局部优化是否把成本转嫁给下游。

**完成标准：**能对 G3-L1～L4 先预测、后解释，并把“复制了什么/谁仍拥有/何时失效”写成三行。性能结论还需目标 workload 测量；本批计数实验不是 benchmark。

<a id="g3-part-44"></a>

<a id="g3-section-16"></a>

## 16. 工程原则回查

### 16.1 如果几个月后只记住十五条

1. **不要从C++语法猜性能；先理解type的logical value和representation。**

2. **`sizeof(T)`只描述object本体，不一定描述它拥有或代表的数据规模。**

3. **Copy要求保留source logical value；Move允许消费source state；Elision可以完全消除transfer。**

4. **`std::move`只是xvalue cast，真正move由后续operation执行。**

5. **Indirect owner通常copy昂贵、move便宜；inline value的move可能和copy一样贵。**

6. **Moved-from object仍然alive；只能依赖其type明确提供的moved-from contract。**

7. **`noexcept` move是generic performance contract，而不仅是异常声明。**

8. **Modern C++应大胆return-by-value；`return local;`让NRVO和implicit move工作，不要机械`std::move`。**

9. **参数首先表达borrow/own/consume/view/share，然后才讨论性能。**

10. **Small values适合value-flow；large synchronous input适合borrow；large ownership通常适合move。**

11. **vector用growth-time relocation与地址不稳定交换dense contiguous storage和优秀cache locality。**

12. **SSO/SBO用更大的wrapper换取减少small-value allocation，因此同时影响cache、move、ABI和threshold cliffs。**

13. **Zero-copy将memory-bandwidth成本转换成lifetime、aliasing、reuse和synchronization成本。**

14. **Small copy有时是在购买lifetime independence、thread independence和storage abstraction。**

15. **健康的高性能C++系统通常是dense small values + cheap movable owners + narrow borrows + explicit shared islands + measured storage reuse。**

<a id="g3-section-17"></a>

## 17. G3 → G4

本章按学习稿继续维护；定向实验不等于所有成本判断都已经测量。

我们已经回答：**一个C++ value在程序中流动时，它的copy、move、return、parameter passing和container relocation究竟意味着什么成本。**

[G4 §1](g04-stl-and-ranges.md#g4-section-1)把本章的值与表示模型用于整个数据集合。下面是问题之间的依赖，不是需要重新背诵的术语目录。

```text
Container
    ↓
Storage Topology
    ↓
Iterator
    ↓
Invalidation
    ↓
Algorithm
    ↓
Ranges / Views
    ↓
Abstraction Cost
```

下一阶段的核心问题将变成：**怎样选择、遍历和组合一整个value集合，同时仍然保持对memory layout、iterator validity、algorithmic complexity和machine cost的控制。**
