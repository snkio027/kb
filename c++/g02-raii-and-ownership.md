# G2 · RAII、资源与所有权

Modern C++ Systems Engineering · [Editorial Profile v1.0](editorial-profile.md)

编辑状态：Professional presentation refresh。PDF：NOT BUILT / NOT VALIDATED。

- **Version:** 1.2 · 呈现修订稿
- **Prerequisite:** G1 Object Model & Lifetime
- **Language Baseline:** C++23
- **Comparison Language:** Zig
- **Scope:** RAII / Ownership / `unique_ptr` / Rule of Zero & Five / Failure Safety / `shared_ptr` / `weak_ptr` / Ownership Graph / Lease
- **Purpose:** 作为进入 G3 Value Semantics & Performance 前的长期资源管理与所有权推理手册

## 阅读入口

[上一章：G1](g01-object-model.md) · [全系列导航](README.md) · [下一章：G3](g03-value-semantics-and-performance.md)

本章只抓住一个问题：**同一资源经过提前返回、异常和异步交接后，谁仍负有清理责任？**

- 主阅读线：[资源与 RAII](#g2-part-1) → [独占所有权](#g2-part-4) → [失败安全](#g2-part-10) → [清理实验](#g2-lab-cleanup) → [共享所有权](#g2-part-14) → [共享实验](#g2-lab-shared) → [Final Gate](#g2-gate)。
- 回查层：按下面的主题目录查找接口、架构、跨语言和审查材料，不要求一次连续读完。
- 前置自测：能否从 G1 解释“unique_ptr 活着，get() 得到的旧指针仍可能失效”？若不能，先画 reset 前后的对象关系。
- 完成目标：为一个 owner 标出获取、交接、借用失效和清理点，并能解释失败路径。只读懂智能指针 API 不算完成。

旧主题编号保留为回查锚点，正文按主题重新分层。只有带 `g-lab` 标记的程序是本批提取运行的完整实验，其余块按上下文视为片段或设计示意。跨语言对照未在本批编译。公式用于提示审查维度，不是形式化安全证明。

### 章节目录

- [1. 资源与清理模型](#g2-section-1)
- [2. 独占所有权与值成员](#g2-section-2)
- [3. 接口与所有权合同](#g2-section-3)
- [4. 特殊成员与失败安全](#g2-section-4)
- [5. 实验 · G2-L1：清理不是只覆盖快乐路径](#g2-section-5)
- [6. 回滚与共享所有权](#g2-section-6)
- [7. 实验 · G2-L2：弱观察不持有资源，lock 暂时持有](#g2-section-7)
- [8. 共享所有权的适用边界](#g2-section-8)
- [9. 异步边界与停机](#g2-section-9)
- [10. 架构与跨语言回查](#g2-section-10)
- [11. 工程审查与常见误判](#g2-section-11)
- [12. 术语与统一模型](#g2-section-12)
- [13. Final Gate](#g2-section-13)
- [14. Final Gate · 参考答案与常见误判](#g2-section-14)
- [15. 工程原则回查](#g2-section-15)
- [16. G2 → G3](#g2-section-16)

<a id="g2-section-1"></a>

## 1. 资源与清理模型

<a id="g2-part-0"></a>

### 1.1 本章的工程问题

G1 问“访问是否合法”，G2 问“谁让资源活着，谁负责最终清理”。先画最小关系，再选智能指针：

```text
owner ── manages ──> resource <── accesses ── borrower
       cleanup duty                         no cleanup duty
```

value、unique、shared 是不同的责任组织方式，不是智能指针 API 的难度等级。优先用最简单、足以表达实际生命周期的结构。

<a id="g2-part-1"></a>

### 1.2 Resource、Handle 与 Ownership

**Resource 不等于 Memory**

文件描述符、socket、锁、线程、GPU buffer、数据库事务、映射区域、临时文件和帧缓冲 lease，都有取得、使用和释放协议。清理动作不一定是 delete：它可以是 close、unlock、rollback、munmap 或归还池。

**Handle 不等于 Resource**

[反例片段 · 依邻近说明判定失效条件；不要用于生产代码]

```cpp
// POSIX 接口片段，省略头文件和错误处理。
int fd = ::open("data.bin", O_RDONLY);
```

fd 是一个 int 对象，内核里的打开文件状态才是被管理资源。复制这个整数不会复制资源，也不会替你决定哪一份负责 close。同理，T* 只表示一条访问路径，不能独自说明所有权。

**Ownership 的工程定义**

owner 负有按协议结束资源使用并完成最终清理的责任。独占 owner 负责这项责任；共享 owner 共同决定管理资源何时释放；borrower 可以访问但不能擅自清理。资源可以临时为空，责任也可以按类型合同转移。

**Aliasing ≠ Ownership**

[机制片段 · 不承诺独立编译]

```cpp
int value{42};
int* p = &value;
int* q = &value;
int& r = value;
```

三条别名路径访问同一对象，并没有产生三个 owner。因此“很多组件都用它”不是采用 shared_ptr 的充分理由；应先问它们是否真的需要独立延长生命。

<a id="g2-part-2"></a>

### 1.3 Manual Cleanup 为什么难维护

**单一路径很容易遗漏隐藏条件**

[机制片段 · 不承诺独立编译]

```cpp
// 演示手工清理路径，不是完整的文件处理实现。
int process() {
    int fd = ::open("data.bin", O_RDONLY);
    if (fd == -1) return -1;
    // use fd
    ::close(fd);
    return 0;
}
```

正常路径看起来成对，但还没有处理实际读取失败、close 结果等合同。此处只讨论“是否到达清理”，不把它当作可靠文件事务。

**一个提前返回就改变清理路径**

若在 use fd 处插入 `if (!validate(fd)) return -2;`，成功打开的描述符就越过 close。每增加分支，都要求作者重新检查所有已取得资源。

**多资源形成手工 Cleanup Stack**

取得 A 后取得 B，再取得 C；若 C 失败，必须清理已成功取得的 B、A，不能清理未取得的 C。返回、异常、部分初始化和回调会增加路径数。RAII 的价值是把这份状态记录交给对象结构，而不是复制多份 cleanup 分支。

<a id="g2-part-3"></a>

### 1.4 RAII

**把资源协议放进类型**

RAII（Resource Acquisition Is Initialization）把资源管理与对象的初始化/清理绑定。对象可以在创建时取得资源，也可表示空状态再按合同取得；核心是任何已拥有状态都有相应清理责任。

**确定性清理及其边界**

[机制片段 · 不承诺独立编译]

```cpp
// 接口片段：假定 FileDescriptor 已正确定义清理协议。
{
    FileDescriptor file{fd};
    work();
}
```

正常退出、提前 return，以及实际发生的异常展开，会按规则销毁已构造的局部 owner。它不依赖稍后某次 GC 才清理，但也**不承诺 terminate、强制结束进程或断电会完整展开**。失败细节见 [FM-3](failure-model/fm3-exception-semantics.md)。

**RAII 不等于 Smart Pointer**

vector 管元素和存储，lock_guard 管解锁，FileDescriptor 管句柄，FrameLease 管归还使用权。设计类型时问“析构履行什么协议”，而不是“能不能套一层 unique_ptr”。需要向调用方报告的 flush/close 失败通常应有显式操作，析构承担不抛出的后备清理。

**C++ 与 Zig 的责任放置不同**

C++ 把清理协议放进类型的析构；Zig 的常见做法是在调用作用域登记 defer。概念片段如下，未在本批编译：

```zig
fn run() !void {
    var file = try openFile();
    defer file.deinit();
    try work();
}
```

两者都能组织成对清理，但一个跟随 owner 对象，一个跟随词法作用域。跨作用域交接资源时，仍须明确谁接手责任；defer 的逆序规则见 G1 的版本化示例。

<a id="g2-part-4"></a>

<a id="g2-section-2"></a>

## 2. 独占所有权与值成员

### 2.1 Unique Ownership

**Unique Ownership Invariant**

```text
At most one final owner
        │
        ▼
     Resource
```

可以有：

```text
many borrowers
```

但只能有：一个最终 cleanup responsibility owner。

**为什么不能复制同一资源的清理责任？**

问题不是“unique owner 这个词禁止一切复制”，而是两份句柄如果都对**同一个资源**执行最终清理，就会 double close / double free。

因此，类似文件描述符所有者通常禁用复制：

[机制片段 · 不承诺独立编译]

```cpp
// 接口片段
FileDescriptor(const FileDescriptor&) = delete;
FileDescriptor& operator=(const FileDescriptor&) = delete;
```

另一种合法设计是复制时创建独立资源：例如 vector 的元素副本，或明确定义 clone 的资源包装。这样每份对象仍唯一拥有自己的资源。能否复制应由资源语义决定；不能把“复制一个地址”冒充“复制完整值”。

**为什么允许 Move？**

需要交接清理责任的 owner 可以设计为可移动；固定地址、不可迁移的 owner 也可以禁止移动。可移动 owner 的目标是：

```text
Owner A
  │
  │ move
  ▼
Owner B
```

保持：

```text
exactly one owner
```

因此：

[机制片段 · 不承诺独立编译]

```cpp
FileDescriptor(FileDescriptor&& other) noexcept;
```

通常会把：

```text
source:
Owning(resource)
→ Empty

destination:
Empty/New
→ Owning(resource)
```

<a id="g2-part-5"></a>

### 2.2 `std::unique_ptr<T>`

**正确定位**

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<T>
```

不是：更聪明的 `T*`。

而是：**unique-owning RAII object whose resource happens to be pointer-shaped。**

它编码：

```text
unique ownership
destruction
copy forbidden
move transfer
nullable/empty state
pointer-like borrow access
```

**默认创建方式**

[机制片段 · 不承诺独立编译]

```cpp
auto robot = std::make_unique<Robot>();
```

优先于：

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<Robot> robot{new Robot};
```

因为：

```text
allocation
↓
immediately enters owner abstraction
```

减少 raw owning pointer 暴露。

**核心 API 按 Ownership 理解**

| Operation         | Ownership Meaning                      |
| ----------------- | -------------------------------------- |
| `make_unique`     | 建立 unique ownership                  |
| destructor        | 销毁 owned resource                    |
| `operator*`, `->` | borrow pointee                         |
| `get()`           | 暴露 borrowed raw pointer              |
| `release()`       | 放弃 ownership，不销毁 resource        |
| `reset()`         | 结束当前 ownership / adopt 新 pointer  |
| move constructor  | transfer ownership                     |
| move assignment   | replace current ownership via transfer |
| copy              | forbidden                              |

**`get()` vs `release()`**

[机制片段 · 不承诺独立编译]

```cpp
T* view = owner.get();
```

：

```text
owner remains owner
view only borrows
```

而：

[机制片段 · 不承诺独立编译]

```cpp
T* raw = owner.release();
```

：

```text
owner → empty
raw handle now carries cleanup responsibility by convention
```

必须记：**`get()` borrows；`release()` transfers responsibility out。**

**`unique_ptr` 不证明 Borrow Lifetime**

[反例片段 · 依邻近说明判定失效条件；不要用于生产代码]

```cpp
auto owner = std::make_unique<Robot>();

Robot* view = owner.get();

owner.reset();

view->update(); // dangling
```

所以：

```text
unique_ptr
solves ownership uniqueness

does not solve borrow lifetime
```

G1 仍然有效。

**`unique_ptr<T[]>`**

[机制片段 · 不承诺独立编译]

```cpp
auto values = std::make_unique<int[]>(count);
```

表达：unique ownership of dynamically allocated array。

但普通动态序列通常优先：

[机制片段 · 不承诺独立编译]

```cpp
std::vector<T>
```

因为 vector 同时管理：

```text
length
capacity
element lifetime
iteration
copy/move
```

**Custom Deleter**

完整模型：

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<T, Deleter>
```

因此可以管理：

```text
FILE*
C library handles
foreign runtime handles
custom allocated objects
```

只要 deleter 能正确表达 cleanup protocol。

例如：

[机制片段 · 不承诺独立编译]

```cpp
struct FileCloser {
    void operator()(std::FILE* file) const noexcept {
        if (file != nullptr) {
            static_cast<void>(std::fclose(file));
        }
    }
};

using File = std::unique_ptr<std::FILE, FileCloser>;
```

此处是后备清理片段，忽略 fclose 返回值不等于证明写入/关闭成功。需要向调用方报告 I/O 失败时，提供显式 finish/close 协议，再保留不抛出的析构兜底。

**非 Pointer-shaped Resource 不要硬套 `unique_ptr`**

POSIX：

[机制片段 · 不承诺独立编译]

```cpp
int fd;
```

更自然：

[机制片段 · 不承诺独立编译]

```cpp
class FileDescriptor;
```

原因：

```text
fd is integer handle
not naturally pointer-shaped
```

所以：dedicated RAII owner type 往往比强行使用 `unique_ptr` 更准确。

<a id="g2-part-6"></a>

### 2.3 Value Ownership 优先

**Unique Ownership 不等于 `unique_ptr`**

[机制片段 · 不承诺独立编译]

```cpp
class RobotRuntime {
private:
    Logger logger_;
};
```

这里：

```text
RobotRuntime
owns Logger
```

已经是 unique/value ownership。

不需要：

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<Logger>
```

**Value Ownership 为什么通常最好推理？**

如果 Logger 的存在与父对象紧密绑定，直接写 `Logger logger_;`，就不必再为这个成员引入可空指针、单独分配和间接访问。成员仍可能在内部拥有动态缓冲区；“value member”不等于“整个对象零堆分配”。

成员按声明顺序初始化、逆序销毁；它们的生命周期也不是与父对象每个瞬间完全相同。这里的设计意图是让子资源的管理嵌入父对象结构，而不是手工维护另一套外部 owner。

选择顺序可从 value member 开始；确有可选存在、独立动态生命周期、多态等需要时考虑 unique ownership；只有多个独立参与者确需共同延长生命时再考虑 shared ownership。这是设计起点，不是禁止其他表示的语言规则。

<a id="g2-part-7"></a>

<a id="g2-section-3"></a>

## 3. 接口与所有权合同

### 3.1 Ownership Taxonomy

可以把常见关系统一成：

| Semantic Relationship       | C++ 常见表达              |
| --------------------------- | ------------------------- |
| Value ownership             | `T`                       |
| Unique dynamic ownership    | `std::unique_ptr<T>`      |
| Required mutable borrow     | `T&`                      |
| Required read-only borrow   | `const T&`                |
| Optional borrow/observer    | `T*`, `const T*`          |
| Sequence borrow             | `std::span<T>`            |
| Shared ownership            | `std::shared_ptr<T>`      |
| Shared-domain weak observer | `std::weak_ptr<T>`        |
| Pool-backed temporary right | dedicated move-only Lease |
| Raw OS resource owner       | dedicated RAII type       |

**五个独立 API 维度**

任何参数/返回类型都可以问：

```text
Ownership
Nullability
Mutability
Extent
Lifetime / Invalidation
```

例如：

[机制片段 · 不承诺独立编译]

```cpp
const T&
```

：

```text
Ownership   = borrow
Nullability = required
Mutability  = read-only
Extent      = one object
```

而：

[机制片段 · 不承诺独立编译]

```cpp
std::span<const T>
```

：

```text
Ownership   = borrow
Mutability  = read-only
Extent      = runtime bounded sequence
```

<a id="g2-part-8"></a>

### 3.2 Function Signature 就是 Ownership Contract

**`T`**

[机制片段 · 不承诺独立编译]

```cpp
void process(T value);
```

通常：callee 获得自己的 value。

参数对象有自己的生命周期，但若 T 是 span、指针或带借用成员的类型，底层数据仍依赖 caller 的资源；按值传参不自动消除别名。

**`T&`**

[机制片段 · 不承诺独立编译]

```cpp
void process(T& value);
```

通常：required mutable borrow。

**`const T&`**

[机制片段 · 不承诺独立编译]

```cpp
void process(const T& value);
```

通常：required read-only borrow。

**`T*`**

[机制片段 · 不承诺独立编译]

```cpp
void process(T* value);
```

信息不足。

可能是：

```text
optional borrow
legacy API
output parameter
C-compatible handle
array start
```

所以需要额外 contract。

**`std::unique_ptr<T>`**

[机制片段 · 不承诺独立编译]

```cpp
void consume(std::unique_ptr<T> value);
```

非常清晰：callee takes unique ownership。

**`std::shared_ptr<T>`**

[机制片段 · 不承诺独立编译]

```cpp
void schedule(std::shared_ptr<T> value);
```

应读成：callee acquires a shared ownership stake。

而不是：传一个 pointer。

**不要泄漏 Ownership Representation**

如果函数只是：

```text
read T
```

不要因为 caller 恰好有：

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<T>
```

就写：

[机制片段 · 不承诺独立编译]

```cpp
void inspect(const std::unique_ptr<T>&);
```

更合理：

[机制片段 · 不承诺独立编译]

```cpp
void inspect(const T&);
```

原则：**Accept the least ownership-aware abstraction the function actually needs.**

<a id="g2-part-9"></a>

<a id="g2-section-4"></a>

## 4. 特殊成员与失败安全

### 4.1 Rule of Three / Five / Zero

**为什么 Raw Owner 会触发 Special Member 问题？**

[机制片段 · 不承诺独立编译]

```cpp
class Buffer {
private:
    int* data_{nullptr};
    std::size_t size_{0};
};
```

如果 `data_` owning：

默认 memberwise copy：

```text
copy pointer value
```

而不是：

```text
copy allocation ownership semantically correctly
```

于是可能 double delete。

**Rule of Three**

C++98：

```text
Destructor
Copy Constructor
Copy Assignment
```

如果一个 raw-resource class 需要自己管理其中一个，通常必须系统审查三个。

**Rule of Five**

C++11 以后再加入：

```text
Move Constructor
Move Assignment
```

所以 raw resource owner 必须审查：

```text
destruction
copy construct
copy assign
move construct
move assign
```

**Rule of Five 不是目标**

不是：每个 class 都手写五个函数。

而是：如果你已经直接管理 raw resource，就必须完整定义 resource state transition。

**Rule of Zero 才是现代默认目标**

[机制片段 · 不承诺独立编译]

```cpp
class Robot {
private:
    std::string name_;
    std::vector<Sensor> sensors_;
    std::unique_ptr<Engine> engine_;
};
```

如果 members 已经拥有正确：

```text
copy
move
destruction
```

语义，那么外层 class 不需要自己写这些机制。

这就是：**semantic composition。**

**Rule of Zero 的本质**

```text
Raw Resource
     ↓
Small Proven RAII Owner
     ↓
Higher-Level Domain Types
     ↓
Rule of Zero
```

复杂度集中在：少数真正的 resource boundary types。

而不是散布到每个业务 class。

**`= default` 不等于“不声明”**

[机制片段 · 不承诺独立编译]

```cpp
~Widget() = default;
```

仍然是：user-declared destructor。

这会影响某些 implicit move-generation rules。

所以：没有必要就不要为了“显式”机械写 special members。

**Member Type 语义向上传播**

如果：

[机制片段 · 不承诺独立编译]

```cpp
class Robot {
private:
    std::unique_ptr<Engine> engine_;
};
```

那么：

```text
unique_ptr non-copyable
↓
Robot copy also unavailable

unique_ptr movable
↓
Robot can be implicitly movable
```

前提是没有其它 user-declared special-member 规则阻止生成。

这就是 C++ ownership composition 很强的一点。

<a id="g2-part-10"></a>

### 4.2 Failure Safety

**Exception Safety 真正研究什么？**

不是：

```text
try/catch
```

而是：**如果 operation 中途失败，剩下的 program state 仍满足什么 guarantee？**

因此更广义应该理解：Failure Safety。

即使使用：

```text
std::expected
Zig error union
C error code
```

同样需要。

**Object Invariant**

一个 class 应保证：

```text
constructor success
→ invariant holds

operation success
→ invariant holds

operation failure
→ invariant still holds
```

资源不能：

```text
leak
double cleanup
half-own
dangling internally
```

**Basic Guarantee**

失败后：

```text
no resource leak
object invariants remain valid
object may have changed state
```

即：valid but state may change。

**Strong Guarantee**

失败时：state 保持原样。

```text
success → commit S1
failure → rollback S0
```

即：commit-or-rollback。

**No-throw Guarantee**

Operation 保证：不允许 exception 逃出。这不等于操作一定完成：noexcept 函数仍可能终止或返回错误状态；事务提交需要另证 no-fail 条件。

典型：

```text
destructor
swap
simple resource move
cleanup primitive
```

<a id="g2-part-11"></a>

### 4.3 Transactional Update

高质量 mutation 常采用：

```text
Prepare
↓
Validate
↓
Perform failure-prone work on temporary state
↓
No-throw Commit
↓
Automatic cleanup of old state
```

而不是：

```text
Destroy old state
↓
Start risky work
↓
Hope it succeeds
```

**先准备，再在可证明的提交点替换**

**问题：**先 reset 旧模型，再构建新模型，构建失败后还有可用模型吗？

[机制片段 · 不承诺独立编译]

```cpp
// 不佳片段：失败前已经销毁旧值。
model_.reset();
model_ = build_model(config);
```

把可能失败的构建放在临时状态中：

[机制片段 · 不承诺独立编译]

```cpp
auto next = build_model(config);
model_ = std::move(next);
```

只有在 `build_model` 不改变旧模型、替换确实不会失败且旧值清理遵守合同等前提下，才能据此论证强保证。例如明确使用适合的 unique_ptr 与不抛出的 deleter，并把外部副作用另行处理。对未知 T，移动赋值未必是不失败的提交点。

**边界：**一个 `noexcept` 标注只禁止异常逃出，函数仍可能终止或通过其他渠道失败。强保证必须说明保护的状态范围，检查构建、验证、提交、返回和清理；参见 [FM-4](failure-model/fm4-raii-exception-safety.md)。

**Copy-and-Swap 的真正意义**

[机制片段 · 不承诺独立编译]

```cpp
T copy{other};
swap(copy);
```

不是一个语法技巧。

而是：

```text
Prepare temporary
↓
may fail

noexcept swap
↓
Commit

temporary destructor
↓
Cleanup old state
```

这是事务更新的候选结构。还必须证明 swap、提交后的返回和清理不会破坏所承诺的结果；单独看到 noexcept swap 不足以完成证明。

<a id="g2-part-12"></a>

### 4.4 Constructor Failure

**非委托构造失败与成员清理**

如果 constructor 中：

```text
member A constructed
member B constructed
member C throws
```

那么：

```text
destroy B
destroy A
```

对这种非委托构造失败，完整对象没有构造完成，不调用它自身的析构函数，已完成的子对象按规则清理。不要推广成“所有构造函数体抛异常都不析构完整对象”：委托构造的目标已成功完成、委托体随后抛出时，完整对象会析构。[N4950：except.ctor](https://timsong-cpp.github.io/cppwp/n4950/except.ctor)

**为什么 Member RAII 如此重要？**

Raw resource：

[机制片段 · 不承诺独立编译]

```cpp
class Session {
    int fd_;
    std::byte* buffer_;
};
```

constructor 中途 throw：很容易 leak。

RAII members：

[机制片段 · 不承诺独立编译]

```cpp
class Session {
private:
    FileDescriptor fd_;
    std::vector<std::byte> buffer_;
};
```

construction failure：已构造 members 自动 rollback。

<a id="g2-section-5"></a>

## 5. 实验 · G2-L1：清理不是只覆盖快乐路径

<a id="g2-lab-cleanup"></a>

**问题：**三个退出路径是否都释放资源？构造函数体中途失败时，是否需要完整对象的析构函数才能清理成员？

先预测四次调用后，资源的获取/释放数，以及完整 Session 的析构次数。这里用计数器模拟资源，避免把 OS 的关闭语义混入最小实验。

<!-- g-lab {"id":"G2-L1","mode":"run","stdout":"acquired=4 released=4 live=0 session-dtors=0\n"} -->
[完整实验 · G2-L1 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <iostream>

struct Resource {
    static inline int acquired = 0, released = 0, live = 0;
    Resource() { ++acquired; ++live; }
    Resource(const Resource&) = delete;
    Resource& operator=(const Resource&) = delete;
    ~Resource() noexcept { ++released; --live; }
};

void work(int mode) {
    Resource resource;
    if (mode == 1) return;
    if (mode == 2) throw 7;
}

struct Session {
    static inline int destructors = 0;
    Resource member;
    Session() { throw 9; } // 非委托构造；member 已完成。
    ~Session() { ++destructors; }
};

int main() {
    work(0);
    if (Resource::live != 0 || Resource::released != 1) return 1;
    work(1);
    if (Resource::live != 0 || Resource::released != 2) return 2;
    bool work_caught = false;
    try { work(2); }
    catch (int value) { work_caught = value == 7; }
    if (!work_caught || Resource::live != 0 ||
        Resource::released != 3) return 3;
    bool session_caught = false;
    try { Session session; }
    catch (int value) { session_caught = value == 9; }
    if (!session_caught || Resource::acquired != 4 ||
        Resource::released != 4 || Resource::live != 0 ||
        Session::destructors != 0) return 4;
    std::cout << "acquired=4 released=4 live=0 session-dtors=0\n";
}
```

**解释：**局部 owner 在正常退出、return 和本例的异常展开中清理；Session 未完成，但其 Resource 成员已经完成，所以成员单独被清理。无需依赖 Session 析构函数。

**改一个条件：**去掉 Resource 析构中的释放计数，应触发测试失败，而非只看到进程正常结束。另可写委托构造作为手动扩展，预测完整对象析构为何不同。

**边界：**这是模拟资源和已实际展开的异常路径，不证明 terminate、进程强制退出、断电或 OS close 失败都可自动恢复。析构不抛出也不等于外部数据已经持久化。

<a id="g2-part-13"></a>

<a id="g2-section-6"></a>

## 6. 回滚与共享所有权

### 6.1 C++ vs Zig Failure Rollback

C++：

[机制片段 · 不承诺独立编译]

```cpp
class Session {
    Buffer buffer_;
    Socket socket_;
};
```

如果 `socket_` constructor throws：

```text
buffer_ destructor runs automatically
```

Zig：

```zig
const buffer = try allocator.alloc(u8, 4096);
errdefer allocator.free(buffer);

const socket = try Socket.connect();
errdefer socket.close();
```

Zig显式：

```text
errdefer rollback
```

C++：

```text
subobject lifetime rollback
```

可以总结：

```text
C++
type/object-driven rollback

Zig
scope/control-flow-driven rollback
```

<a id="g2-part-14"></a>

### 6.2 Shared Ownership

**什么是真正 Shared Ownership？**

```text
Owner A ─┐
Owner B ─┼──→ Resource
Owner C ─┘
```

三个 owner 都参与：resource 必须保持 alive。

只有：

```text
last strong owner gone
```

时 resource 才销毁。

**`shared_ptr` Copy 不复制 Pointee**

[机制片段 · 不承诺独立编译]

```cpp
auto a = std::make_shared<Model>();
auto b = a;
```

结果：

```text
a ─┐
   ├──→ same Model
b ─┘
```

复制的是：ownership handle。

不是 Model value。

**Control Block**

典型实现需要：

```text
strong/reference count
weak count
deleter
allocation metadata
```

概念：

```text
shared_ptr A ─┐
shared_ptr B ─┼──▶ Control Block ──▶ Resource
weak_ptr W ···┘
```

**Resource 与 Control Block Lifetime**

最后一个 strong owner 释放时执行被管理资源的释放协议；只要仍有 strong owner 或 weak observer，控制信息就还需要存在。只有两类关联都结束后，控制块才可释放，不能仅凭“外部 weak_ptr 数为 0”就推导控制块释放。

还要区分 managed resource 与 stored pointer：shared_ptr 的别名构造可让保存的指针与真正管理的对象不同。管理对象活着，不自动证明任意别名目标仍有效。下方实验只使用普通 make_shared，不覆盖自定义 deleter 和别名构造。

**Shared Ownership 最大成本：Non-local Lifetime**

Unique：

```text
one owner
→ destruction point easy to reason
```

Shared：

```text
many owners across program
→ last-owner point may be non-local
```

所以：deterministic rule，不等于 locally obvious destruction。

<a id="g2-part-15"></a>

### 6.3 `std::weak_ptr`

**Weak Observer**

`weak_ptr`：不增加 strong ownership count，因此不延长 pointee lifetime。

它观察：shared ownership domain。

**`lock()`**

[机制片段 · 不承诺独立编译]

```cpp
if (auto model = weak.lock()) {
    model->run();
}
```

含义：

```text
if object alive
→ acquire temporary strong ownership
→ safe to use during this owner lifetime

if expired
→ return empty shared_ptr
```

因此：`lock()` = lifetime re-acquisition attempt。

**为什么不先 `expired()`？**

因为：

```text
check alive
↓
time passes
↓
last owner disappears
↓
use
```

存在 TOCTOU race。

正确：直接 `lock()` 获得 lifetime right。

<a id="g2-part-16"></a>

### 6.4 Shared Ownership Cycles

```text
A ──strong──▶ B
▲             │
└────strong───┘
```

外部 owner 消失以后：

```text
A count >= 1
B count >= 1
```

永不归零。

结果：leak。

Reference counting 无法自动收集 strong cycles。

**打破 Cycle**

典型：

```text
Parent ──strong──▶ Child
Parent ◀··weak··── Child
```

反向关系：observation

而不是 ownership。

所以用：

[机制片段 · 不承诺独立编译]

```cpp
std::weak_ptr<Parent>
```

或者普通 borrow，取决于 topology。

<a id="g2-part-17"></a>

### 6.5 Shared Ownership ≠ Thread Safety

`shared_ptr` control-block bookkeeping 对独立 shared handles 的并发 copy/destruction 提供相应线程安全语义。

但：

[机制片段 · 不承诺独立编译]

```cpp
std::shared_ptr<std::vector<int>>
```

并不会自动让：

[机制片段 · 不承诺独立编译]

```cpp
values->push_back(...)
```

并发安全。

必须区分：

```text
shared lifetime safety
≠
pointee data-race safety
```

<a id="g2-section-7"></a>

## 7. 实验 · G2-L2：弱观察不持有资源，lock 暂时持有

<a id="g2-lab-shared"></a>

**预测：**原 owner reset 后，weak 是否马上 expired？先看局部 lease 是否还在。完整运行例：

<!-- g-lab {"id":"G2-L2","mode":"run","stdout":"lease-keeps-alive; expired-after-release\n"} -->
[完整实验 · G2-L2 · main.cpp]

<!-- g-file {"path":"main.cpp"} -->
```cpp
#include <iostream>
#include <memory>

struct Model {
    static inline int live = 0;
    Model() { ++live; }
    ~Model() { --live; }
};

int main() {
    std::weak_ptr<Model> observer;
    {
        auto owner = std::make_shared<Model>();
        observer = owner;
        auto lease = observer.lock();
        if (!lease || lease.get() != owner.get() || Model::live != 1) return 1;
        owner.reset();
        if (observer.expired() || Model::live != 1) return 2;
        lease.reset();
        if (!observer.expired() || Model::live != 0) return 3;
    }
    if (observer.lock()) return 4;
    std::cout << "lease-keeps-alive; expired-after-release\n";
}
```

**原因：**weak 不增加 strong ownership；成功 lock 得到的 shared_ptr 会增加它。最后一份 strong owner 释放后，本例对象销毁，weak 仍可安全询问是否过期。

**改变条件：**在内层作用域额外保存 shared_ptr 副本，再观察 expired 何时成立。不要把“某个 owner reset”误认为“最后一个 owner reset”。

**边界：**本例不涉及并发，也不证明 Model 的读写线程安全；不同 shared_ptr 实例的控制块协作不等于同一个 shared_ptr 变量可以无同步并发改写。

<a id="g2-part-18"></a>

<a id="g2-section-8"></a>

## 8. 共享所有权的适用边界

### 8.1 Shared Ownership 的使用准则

优先只有在：

```text
multiple independent components
really need to keep same resource alive
```

时使用。

典型：

```text
independent async tasks
immutable model/config generations
callback lifetime
event fan-out
```

不要因为：

```text
很多函数都需要访问
不知道谁 delete
传起来方便
担心 raw pointer
```

就直接升级到 `shared_ptr`。

<a id="g2-part-19"></a>

<a id="g2-section-9"></a>

## 9. 异步边界与停机

### 9.1 Async Boundary

同步：

[机制片段 · 不承诺独立编译]

```cpp
void process(const Frame& frame);
```

caller lexical lifetime 可以保证：

```text
Frame alive through call
```

异步：

[机制片段 · 不承诺独立编译]

```cpp
executor.submit(...)
```

function 已返回。

因此：**Async boundary 经常也是 ownership boundary。**

**Raw `this`**

[机制片段 · 不承诺独立编译]

```cpp
executor.submit([this] {
    work();
});
```

只 borrow。

必须保证：

```text
*this outlives callback
```

**Shared Self**

[机制片段 · 不承诺独立编译]

```cpp
executor.submit([self] {
    self->work();
});
```

callback 成为 owner。

**Weak Self**

[机制片段 · 不承诺独立编译]

```cpp
executor.submit([weak] {
    if (auto self = weak.lock()) {
        self->work();
    }
});
```

仅保存 weak_ptr 的 callback 不在两次调用之间延长目标生命周期；成功 lock() 获得的局部 shared_ptr 会在本次使用期间延长它。

object 不存在时：no-op / cancel / domain-specific behavior。

<a id="g2-part-20"></a>

### 9.2 `enable_shared_from_this`

如果 object 已经属于某个 shared ownership domain：

[机制片段 · 不承诺独立编译]

```cpp
class Session : public std::enable_shared_from_this<Session> {
    ...
};
```

`shared_from_this()`：获取属于同一 control block 的新 shared owner。

千万不要：

[机制片段 · 不承诺独立编译]

```cpp
std::shared_ptr<Session>{this};
```

因为这会创建独立 control block，可能造成：double deletion。

<a id="g2-part-21"></a>

### 9.3 Pool + Lease

并不是所有 multi-consumer resource 都应该 shared-own。

例如 Frame buffer：

```text
FramePool
   │ owns storage
   ▼
Buffer

FrameLease
   │ owns temporary usage right
   ▼
Buffer
```

Consumer 不负责：

```text
delete Buffer
```

而负责：

```text
release lease
↓
return buffer to pool
```

所以 Lease 是另一种 ownership semantics。

**RAII Lease**

[机制片段 · 不承诺独立编译]

```cpp
class FrameLease {
public:
    FrameLease(const FrameLease&) = delete;
    FrameLease& operator=(const FrameLease&) = delete;

    FrameLease(FrameLease&&) noexcept;
    FrameLease& operator=(FrameLease&&) noexcept;

    ~FrameLease() noexcept;

private:
    FramePool* pool_{nullptr};
    Frame* frame_{nullptr};
};
```

语义：

```text
copy forbidden
move transfers lease
destructor returns resource to pool
```

RAII 依然成立。

<a id="g2-part-22"></a>

### 9.4 Shutdown Architecture

Ownership 不只是 startup。

Shutdown 是 ownership/dependency graph 的镜像。

假设：

```text
WorkerPool borrows Logger
WorkerPool borrows ModelManager
WorkerPool holds FrameLease
```

那么必须：

```text
stop workers
↓
drain/cancel work
↓
join threads
↓
destroy tasks
↓
release FrameLeases
↓
destroy FramePool / ModelManager
↓
destroy Logger
```

原则：**Borrowers must end before their owners/backing resources。**

**Member Declaration Order**

C++ members：

[机制片段 · 不承诺独立编译]

```cpp
class Runtime {
private:
    Logger logger_;
    ModelManager models_;
    FramePool frames_;
    WorkerPool workers_;
};
```

构造：

```text
logger
models
frames
workers
```

析构：

```text
workers
frames
models
logger
```

所以 member order 可以编码：destruction dependency。

**不要用 Shared Ownership 掩盖 Shutdown Bug**

如果 domain 要求：

```text
Worker must stop before Logger
```

正确方案：修 Worker shutdown/join protocol。

不是：

[机制片段 · 不承诺独立编译]

```cpp
std::shared_ptr<Logger>
```

让 Logger 神秘地继续活。

必须记：**Do not use shared ownership to hide an ordering bug.**

<a id="g2-part-23"></a>

### 9.5 Healthy Ownership Graph

一个成熟系统通常希望：

```text
Broad Value / Unique Ownership Tree
                +
        Explicit Borrow Edges
                +
     Narrow Shared-Lifetime Islands
                +
       Lease / Pool where needed
```

而不是：

```text
Everything is shared_ptr
```

<a id="g2-part-24"></a>

<a id="g2-section-10"></a>

## 10. 架构与跨语言回查

### 10.1 Robot Runtime 参考模型

```text
RobotRuntime
│
├──owns(value)────▶ Config
│
├──owns(value)────▶ Logger
│
├──owns(value)────▶ SensorManager
│                    │
│                    └──owns(unique)──▶ Sensor implementations
│
├──owns(value)────▶ ModelManager
│                    │
│                    └──shared────────▶ immutable Model generation
│                                         ▲
│                                         │ shared
│                                  InferenceTask
│
├──owns(value)────▶ FramePool
│                    │
│                    └──owns──────────▶ Frame buffers
│                                         ▲
│                                         │ lease
│                                  InferenceTask
│
└──owns(value)────▶ WorkerPool
                     │
                     └──owns──────────▶ Tasks

InferenceTask - -borrow- -▶ Logger
```

这张图基本概括了 G2 的最终目标。

<a id="g2-part-25"></a>

### 10.2 C++ vs Zig Ownership Architecture

| 维度                  | C++                           | Zig                           |
| --------------------- | ----------------------------- | ----------------------------- |
| Resource cleanup      | destructor / RAII             | `defer` / `deinit`            |
| Unique owner type     | 可强编码                      | 多依赖 API discipline         |
| 禁止 copy owner       | `= delete` / member semantics | 无直接等价语言机制            |
| Ownership transfer    | move semantics                | explicit data-flow convention |
| Value ownership       | 强                            | 强                            |
| Allocation policy     | 常由 owner abstraction 封装   | allocator 通常显式            |
| Borrow                | `T&`, `T*`, span              | `*T`, slice                   |
| Borrow lifetime proof | 弱                            | 弱                            |
| Shared ownership      | `shared_ptr`                  | 需要具体 abstraction          |
| Weak observer         | `weak_ptr`                    | 需要具体 abstraction          |
| Failure rollback      | RAII / unwinding              | `defer` / `errdefer`          |
| Pool/Lease            | dedicated RAII type           | explicit lease + defer        |

核心差异：

```text
C++
更多 ownership protocol
进入 type / object semantics

Zig
更多 allocation / cleanup protocol
留在显式 control flow
```

<a id="g2-part-26"></a>

### 10.3 Rust 第三坐标

Rust：

```text
Box<T>
Rc<T>
Arc<T>
Weak<T>
&T
&mut T
```

不仅表达 owner 类型，还静态检查更多 borrow/lifetime relationship。

但 Rust 仍不能替架构师决定：

```text
Value or Box?
Unique or Arc?
Pool or Arc?
Generation or mutation?
Who should own whom?
```

所以：Ownership topology 始终是 architecture problem。

<a id="g2-part-27"></a>

<a id="g2-section-11"></a>

## 11. 工程审查与常见误判

### 11.1 Code Review Protocol

以后审查任何资源型 C++ 系统，按以下顺序。

**Step 1 — Enumerate Resources**

```text
memory
fd
socket
thread
GPU buffer
model
frame
lock
transaction
```

**Step 2 — Identify Natural Owner**

问：谁应该执行最终 cleanup？

**Step 3 — Prefer Value Ownership**

如果 lifetime 与 parent 完全一致：

[机制片段 · 不承诺独立编译]

```cpp
T member_;
```

**Step 4 — Identify Real Dynamic Lifetime**

若有：

```text
runtime polymorphism
PImpl
stable address
dynamic tree
independent lifetime
```

才进入：

[机制片段 · 不承诺独立编译]

```cpp
std::unique_ptr<T>
```

等 dynamic owner。

**Step 5 — Mark Borrow Edges**

```text
T&
const T&
T*
span
string_view
iterator
```

并回答：谁必须 outlive 谁？

**Step 6 — Find Ownership Transfer Boundaries**

例如：

```text
factory
queue submission
task creation
manager insertion
```

判断：

```text
value
move
unique ownership transfer
shared ownership acquisition
lease transfer
```

**Step 7 — Find Invalidators**

```text
destroy
erase
clear
reallocation
reload
pool reuse
shutdown
generation replacement
```

**Step 8 — Find Shared Islands**

问：多个独立参与者是否真的需要共同延长 lifetime？

**Step 9 — Find Strong Cycles**

```text
A owns B
B owns A
```

决定：

```text
weak edge
borrow edge
or redesign
```

**Step 10 — Review Failure Paths**

问：

```text
partial construction?
allocation failure?
early return?
exception?
expected/error return?
```

是否：

```text
no leak
invariants preserved
rollback semantics明确
```

**Step 11 — Review Async Captures**

```text
[this]
[raw_ptr]
[shared]
[weak]
[unique = std::move(...)]
```

每一种 capture 都是 lifetime semantics。

**Step 12 — Review Shutdown Order**

确保：borrowers/tasks end before resources they borrow。

<a id="g2-part-28"></a>

### 11.2 高频 Smells

看到：

[机制片段 · 不承诺独立编译]

```cpp
T* member_;
```

先问：owner or borrow？

看到：

[机制片段 · 不承诺独立编译]

```cpp
delete member_;
```

问：为什么没有 RAII owner？

看到：

[机制片段 · 不承诺独立编译]

```cpp
std::shared_ptr<T>
```

问：为什么 domain 真需要 shared ownership？

看到：

[机制片段 · 不承诺独立编译]

```cpp
const std::unique_ptr<T>&
```

问：函数真的需要 ownership handle，还是只需要 `const T&`？

看到：

[机制片段 · 不承诺独立编译]

```cpp
[this]
```

进入 async callback：立即审查 object lifetime。

看到：

[机制片段 · 不承诺独立编译]

```cpp
~Foo();
```

问：为什么 Foo 需要 user-declared destructor？是否影响 implicit move？

看到：

[机制片段 · 不承诺独立编译]

```cpp
owner.reset();
owner = build_new();
```

问：为什么不先 prepare new state，再 commit？

看到：

[机制片段 · 不承诺独立编译]

```cpp
std::move(x)
```

问：哪个后续 move operation 真正消费 xvalue？

<a id="g2-part-29"></a>

### 11.3 高频错误直觉

**错误**

> RAII = smart pointer。

正确：RAII 是 acquire/release protocol 与 object lifetime 的绑定。

**错误**

> Unique ownership = `unique_ptr`。

正确：value member 本身经常就是最佳 unique owner。

**错误**

> 多个 users = shared ownership。

正确：多数 users 只是 borrowers。

**错误**

> shared_ptr 是更安全的 unique_ptr。

正确：它表达不同、且更复杂的 ownership topology。

**错误**

> `unique_ptr` 解决 dangling。

正确：它解决 owner uniqueness，不证明 borrow lifetime。

**错误**

> Rule of Five 是现代 class 标准模板。

正确：高层 class 应尽量 Rule of Zero。

**错误**

> `try/catch` = exception safety。

正确：exception/failure safety 是 failure 后的 state guarantee。

**错误**

> shared_ptr thread-safe = T thread-safe。

错误。

**错误**

> zero-copy = shared_ptr。

错误。

可能更正确的是：

```text
Pool + Lease
```

**错误**

> raw pointer 出现就是坏 C++。

错误。

Raw non-owning pointer 可以非常合理。

<a id="g2-part-30"></a>

<a id="g2-section-12"></a>

## 12. 术语与统一模型

### 12.1 核心术语表

| English            | 核心含义                                             |
| ------------------ | ---------------------------------------------------- |
| Resource           | 必须遵守 acquire/release protocol 的实体             |
| Handle             | 对 resource 的标识/访问表示                          |
| Ownership          | 最终 lifetime/cleanup responsibility                 |
| Borrow             | 不拥有 resource 的临时访问关系                       |
| Unique Ownership   | 单一最终 owner                                       |
| Shared Ownership   | 多 owner 共同延长 lifetime                           |
| Observer           | 非拥有访问角色                                       |
| Weak Observer      | 不延长 shared lifetime 的 observer                   |
| RAII               | resource lifetime → object lifetime                  |
| Move-only Type     | copy 非法、move 转移状态/ownership                   |
| Rule of Five       | raw-resource 类型的 special-member 全面审查          |
| Rule of Zero       | 通过 RAII members 组合，外层无需手写 special members |
| Basic Guarantee    | failure 后仍合法，无 leak，state 可改变              |
| Strong Guarantee   | commit-or-rollback                                   |
| No-throw Guarantee | exception 不逃出 operation                           |
| Control Block      | shared ownership bookkeeping                         |
| Lease              | 对 resource temporary usage right 的 owner           |
| Ownership Graph    | 决定 resource destruction topology 的关系图          |
| Invalidation       | 某操作使 borrow/view 不再合法                        |
| Shutdown Order     | resource dependency 的反向 teardown 顺序             |

<a id="g2-part-31"></a>

### 12.2 最终统一公式

G1 可以写：

```text
Valid Access
=
Valid Storage
×
Active Object Lifetime
×
Correct Type
×
Bounds
×
Alignment
×
Access Rules
```

G2 补上：

```text
Object Lifetime Stability
depends on
Ownership Architecture
```

最终：

```text
Correct Native Resource Access
=
G1 Access Validity
+
G2 Ownership / Lifetime Coordination
```

也就是：

```text
Can I access it?
        ▲
        │
        │ depends on
        │
Will its owner keep it alive?
```

<a id="g2-gate"></a>

<a id="g2-part-32"></a>

<a id="g2-section-13"></a>

## 13. Final Gate

### 13.1 Final Gate

你应能够独立回答：

**RAII**

1. Resource 与 handle 为什么不同？
2. RAII 为什么不等于 smart pointer？
3. RAII 如何处理 early return 与 exception？
4. C++ RAII 与 Zig `defer` 的根本差异是什么？

**Unique Ownership**

1. Ownership 到底是什么责任？
2. 为什么不能复制同一资源的清理责任？深复制新资源为何是另一回事？
3. `std::move` 与真正 ownership transfer 分别在哪里发生？
4. `unique_ptr::get()` 和 `release()` 区别是什么？
5. 为什么 `unique_ptr` 仍可能产生 dangling borrow？

**Rule of Zero**

 1. Rule of Three、Five、Zero 的区别是什么？
 2. 为什么业务 class 手写完整 Rule of Five 常是 smell？
 3. 为什么 `std::vector` / `std::string` / `unique_ptr` 能让外层 class 回归 Rule of Zero？
 4. 为什么 `~T() = default` 仍值得审查 move generation？

**Failure Safety**

 1. Basic Guarantee 与 Strong Guarantee 区别是什么？
 2. 为什么 prepare → commit 是重要 mutation pattern？
 3. constructor 中途 throw 时哪些 objects 会销毁？
 4. 为什么 destructor 不应该让 exception 逃出？
 5. Zig `errdefer` 与 C++ partial-construction rollback 有什么对应关系？

**Shared Ownership**

 1. Aliasing 和 shared ownership 有什么区别？
 2. control block 为什么存在？
 3. strong count 降到 0 后为什么 control block 可能还存在？
 4. 为什么 shared ownership destruction point 是 non-local？
 5. 为什么 strong cycle 会 leak？
 6. weak_ptr `lock()` 在 lifetime 上做了什么？
 7. 为什么 `shared_ptr<T>` 不意味着 `T` thread-safe？

**Architecture**

 1. 为什么 value member 应优先于 unique_ptr？
 2. 多个 users 为什么不等于多个 owners？
 3. Pool + Lease 与 shared_ptr 的语义差异是什么？
 4. 为什么 shared ownership 应尽量限制成 narrow islands？
 5. 为什么 shutdown order 是 ownership architecture 的组成部分？
 6. 为什么 async boundary 经常也是 ownership boundary？
 7. 为什么 shared_ptr 不能用于掩盖错误的 join/shutdown protocol？

<a id="g2-section-14"></a>

## 14. Final Gate · 参考答案与常见误判

- **RAII 1～4：**资源是受协议约束的能力，handle 只是标识；RAII 把协议绑定到对象清理，所以锁、文件和 lease 都能使用。已构造局部对象在正常退出与实际展开时清理，不保证终止路径展开。Zig defer 绑定词法作用域，C++ RAII 绑定对象；误判是把二者当作同一种隐式 GC。
- **Unique 1～5：**owner 负最终清理责任；不能浅复制同一资源的独占责任，但可明确 clone 独立资源。std::move 仅转换，转移在实际操作中发生。get 借用，release 交出指针并放弃管理而不释放资源；随后责任须有人接住。reset/销毁等仍可使 borrow 悬挂。
- **Rule of Zero 1～4：**Three 关注析构和复制，Five 加入移动，Zero 用成员类型承载这些语义。业务类手写五个成员会重复低层协议；并非禁止真正 owner 手写。成员语义能组合向外传播；用户声明的默认析构仍会影响隐式移动生成。误判是把 = default 当作“没有声明”。
- **Failure 1～5：**基本保证保不变量与资源，强保证还保约定状态不变。prepare/commit 隔离可失败工作，但提交和清理要另证。非委托构造失败清理已完成子对象；委托构造目标成功后体抛出会析构完整对象。析构逃逸会破坏清理，展开时再次抛出还会终止。errdefer 按错误退出回滚，RAII 按子对象完成状态展开，机制不能完全互换。
- **Shared 1～7：**alias 只是访问，共享拥有才延长管理资源生命；控制块维护强/弱关联及释放信息。strong 归零后 weak 仍需观察元数据。最终释放位置由最后 owner 决定；强环让彼此无法归零。lock 临时取得 strong owner；引用计数安全不保护 pointee 的可变数据。误判是“用了 shared_ptr 就不需要锁”。
- **Architecture 1～7：**value member 少一层独立生命周期，非所有场景最优。多个用户可以只借用；pool 管存储，lease 管临时使用权。缩小共享区域便于定位最终释放者。shutdown 要先停生产者、终止并等待工作、再撤销依赖，具体顺序由依赖图决定。异步跨越调用作用域，必须重选拥有或借用协议；shared_ptr 不能替代停止、唤醒和 join。

**完成标准：**解释两项实验全部判据，并为一个异步 callback 写出 owner、borrow 和停机顺序；进阶题答不出时返回对应主题，而不是扩大本次必读范围。

<a id="g2-part-33"></a>

<a id="g2-section-15"></a>

## 15. 工程原则回查

### 15.1 如果几个月后只记住十五条

1. **Resource 不等于 memory；file、socket、lock、GPU buffer 都有 lifetime protocol。**

2. **Ownership 是最终 cleanup responsibility，不是“谁拿着 pointer”。**

3. **RAII 把 resource lifetime 映射到 C++ object lifetime。**

4. **Value ownership 是最简单的 ownership，应优先考虑。**

5. **`unique_ptr` 表达 dynamic unique ownership，而不是 unique ownership 的唯一形式。**

6. **Borrow 可以有很多份，但 borrower 不决定 resource lifetime。**

7. **`get()` 是 borrow；`release()` 是把 ownership responsibility 重新降级为 raw convention。**

8. **Rule of Zero 是现代高层 class 的默认目标；Rule of Five 主要属于真正的低层 raw-resource owner。**

9. **Failure-safe mutation 应优先 prepare → validate → no-throw commit → automatic cleanup。**

10. **Shared ownership 表示多个独立 owner 共同延长 lifetime，而不是多个 users。**

11. **`weak_ptr` 不延长 lifetime，而通过 `lock()` 在使用前临时取得 strong lifetime。**

12. **Shared ownership cycle 是 reference counting 的结构性弱点。**

13. **Pool owns storage；Lease owns temporary usage right——两种 responsibility 不应混淆。**

14. **健康的大型系统通常是 value/unique ownership tree + explicit borrows + narrow shared islands。**

15. **语言可以帮助执行 ownership contract，但“谁应该拥有谁”始终是 architecture decision。**

<a id="g2-section-16"></a>

## 16. G2 → G3

本章的关键实验已纳入定向检查；进阶片段不因此变成全面验证的工程基线。

我们已经回答：**谁拥有 object/resource，它如何安全地活着和死去？**

G3 将开始回答另一组问题：**如果一个 object 被复制、移动、返回、传参、放进 container，到底发生什么成本？**

主线将进入：

```text
Value Semantics
    ↓
Copy
    ↓
Move
    ↓
Copy Elision
    ↓
RVO / NRVO
    ↓
Pass by Value vs const&
    ↓
Container Relocation
    ↓
SSO / SBO
    ↓
Object Size / Allocation / Indirection
    ↓
Cache Locality
    ↓
Performance-aware API Design
```

也就是从：**Ownership Correctness**

正式进入：**Value Semantics + Performance Cost Model。**
