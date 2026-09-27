<a id="fm-4--raii--exception-safety"></a>
# FM-4 · 资源清理与状态保证

> C++23 失败语义工程手册

[返回 FM 导航](README.md) · [上一章：FM-3](fm3-exception-semantics.md) · [下一章：FM-5](fm5-noexcept-move-copy.md) · [术语与审查约定](series-guide.md)

## 阅读入口

唯一主讲 strong/basic/no-throw/no-fail 的区别、prepare–commit–cleanup 和可观察状态。其他章节引用本章，不另设保证等级。

**主阅读线。** §1–7 → §10–17 → §18–19；用 §7 的状态表检查每个 mutation。

**失败契约。** 先限定受保护状态，再枚举准备、提交、返回、清理各阶段。RAII 管理责任，不能代替业务回滚、远端确认或持久化协议。

**证据边界。** 状态表与 swap 片段是条件化论证，不是已执行的全部失败注入；T17 只验证所列 Buffer 值语义，未注入分配失败。无 `fm-test` 标记的片段按上下文阅读，不自动视为完整实验。

## 本章目录

- [一、所有权与保证语言](#fm4-part-1)
- [二、事务式状态转换](#fm4-part-2)
- [三、清理与外部副作用](#fm4-part-3)
- [四、审查与回查](#fm4-part-4)

原 § 编号用于稳定回查；组标题只组织阅读，不新增机制范围。

<a id="fm4-part-1"></a>

## 一、所有权与保证语言

### 0. 文档定位

FM-4 解决：

> 一个操作失败以后，资源和状态如何仍然保持正确？

核心关系：

```text
RAII
+
ownership
+
state guarantees
+
transactional update
```

共同构成 C++ failure safety。

### 1. RAII 的真正含义

资源获取即初始化（Resource Acquisition Is Initialization，RAII）将清理／释放责任绑定到对象生命周期。Owner 可以管理内存、文件描述符、socket、锁、映射、GPU 资源或订阅，而不只是一种智能指针写法。

它统一正常返回、提前返回和实际展开中的资源清理；清理动作的成功条件、对象是否已完成构造，以及终止路径仍须分别分析。RAII 不自动恢复业务状态，也不保证关闭、flush 或持久化提交成功。

### 2. Owner Object

资源进入已构造的 owner 后，生命周期负责在应执行析构的退出路径调用清理：

```text
获取资源 → 已构造 owner → 使用 → 正常退出／实际展开 → 析构清理
```

获取后尚未进入 owner 的窗口需要单独保护。进程终止、`std::exit` 等路径不能泛化成“所有自动对象都析构”；尤其本系列的终止与展开限制见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)及 [N4950 终止设施](https://timsong-cpp.github.io/cppwp/n4950/support.start.term)。

### 3. RAII 与 Control Flow 解耦

错误：

```cpp
auto* resource = acquire();

step_a();
step_b();  // may throw

release(resource);
```

如果：`step_b throws`

release 被绕过。

正确：

```cpp
Resource resource = acquire();

step_a();
step_b();
```

cleanup 成为：`lifetime semantics`

而不是：`control-flow bookkeeping`

这里以正常作用域退出或实际进行的栈展开为前提，不是所有终止路径的清理承诺；详见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

### 4. Exception Safety Guarantees

以下是工程保证的术语，不应混成一个包含“终止”的线性等级。声明保证时应明确所覆盖的可观察状态、失败通道与前置条件。

<a id="no-throw-guarantee"></a>

**No-throw Guarantee**

本系列用 no-throw 描述**不向调用者传播异常**的保证；它不等于 no-fail。`noexcept` 也不证明操作成功、正常返回或完成清理。

若一个 commit 要求 no-fail，必须额外证明：合法前置条件下可正常完成，没有未处理的错误返回、异常或部分提交，后续返回与清理不会推翻声明的事务结果。终止进程不算完成这样的 commit。

<a id="strong-guarantee"></a>

**Strong Guarantee**

所约定的失败发生时，可观察状态与操作前一致。典型实现先准备临时状态再提交；外部副作用不因内存中的 swap 自动回滚。

<a id="basic-guarantee"></a>

**Basic Guarantee**

失败后不变量和资源管理仍成立，但值可能已改变。具体可继续执行哪些操作仍须由契约说明。

<a id="no-useful-guarantee"></a>

**No Useful Guarantee**

对于关注的失败路径，缺少可依赖的状态保证，不能自行升级成 basic。某条标准写 effects unspecified 也不能简单改称 UB，见 [FM-5 §11](fm5-noexcept-move-copy.md#11-move-only--throwing-move)。

终止是另一维度的处置策略；其清理限制见 [FM-3 §5](fm3-exception-semantics.md#5-stack-unwinding)。

<a id="fm4-part-2"></a>

## 二、事务式状态转换

### 5. Strong Guarantee 的核心模式

```text
prepare (may fail, original observable state unchanged)
    ↓
commit (normal completion assured under its preconditions)
    ↓
return / cleanup (compatible with the promised guarantee)
```

契约片段：

```cpp
void update(State& state, const Input& input) {
    State next = build_state(state, input);
    state.swap(next);
}
```

此结构只有在以下条件成立时才支持所声称的 strong guarantee：

- `build_state` 的失败不修改纳入保证的原状态，也没有无法撤销的外部副作用。
- `swap` 的前置条件满足；它真正完成提交，不能只是声明 `noexcept` 却在内部失败、终止或错误返回。
- `next` 的析构、返回路径及其他收尾与保证兼容；不能在提交后又向调用者报告一个声称“状态未变”的失败。

因此 `noexcept swap` 是有用线索，不是独立的事务证明。

### 6. Transactional Thinking

状态修改操作应思考：

```text
Prepare
Validate
Commit
Cleanup
```

而不是：

```text
边修改
边验证
边申请资源
边做不可逆副作用
```

后者极难提供 strong guarantee。

### 7. Commit Point

提交点（commit point）是合同把准备结果接受为新状态的边界。它不是异常处理机制，也不自动证明原子性、持久化或跨线程可见性。

以 §5 的隔离准备＋swap 为例，下表是**条件化推理**，不是已执行的故障注入记录：

| 阶段 | 状态与责任 | 失败时可以声称什么 |
| --- | --- | --- |
| S0：进入 | state 满足不变量，明确受保护的观察范围 | 前置条件不成立的调用不在此证明内 |
| S1：build_state | next 独立构造；state 尚未被改动 | 只有构造及清理满足条件，才可丢弃临时状态并保持旧 state |
| S2：swap 提交 | 满足 swap 前提，且它确实完成、不半途报错 | 成功后新 state 生效；`noexcept` 一项不足以证明 no-fail |
| S3：返回／清理 | 旧状态由 next 管理，调用者接收完成结果 | 若仍能报告失败，就不能同时许诺该失败意味着旧状态不变 |

因此，提交前“旧状态保持”必须由隔离准备证明；提交后“新状态有效”必须由提交与收尾证明。函数若在提交后返回错误，应明示已提交或完成未知，而不是复用“明确未提交”的错误。

文件写入、消息发布和数据库操作也需找边界，但各自的持久化、部分副作用及确认协议不同。它们只是分析对象，不是用来证明内存 swap 合同的类比。

### 8. Partial Construction

RAII 的强大之处在于：`subobjects constructed one by one`

某一步失败后：`already-constructed objects unwind automatically`

委托构造体失败与普通成员构造失败的区别见 [FM-6 §3](fm6-construction-destruction-allocation.md#3-partial-construction)。

因此应优先：

```cpp
class Session {
    File file_;
    Socket socket_;
    Buffer buffer_;
};
```

而不是：

```cpp
class Session {
    FileHandle file_{invalid};
    SocketHandle socket_{invalid};

    bool init();
};
```

后者创造大量：`partially initialized states`

### 9. Two-Phase Initialization

反模式：

```cpp
Widget widget;
if (!widget.init()) {
    ...
}
```

现在 `Widget` 存在：

```text
before init
after init
init partially failed
```

多个合法/非法状态。

如果可行，更推荐：

```cpp
auto widget = Widget::create(...);
```

或者 throwing constructor。

目标：

> 一个普通对象一旦存在，就满足其 invariant。

### 10. Rollback 不是免费操作

不要简单设计：

```text
do A
do B
do C

C failed

undo B
undo A
```

因为：`undo B 也可能失败`

高质量 strong guarantee 更偏向：

```text
build isolated new state
+
non-failing commit
```

而不是依赖复杂 rollback。

### 11. Copy-and-Swap

经典形式：

```cpp
Buffer& operator=(Buffer other) {
    swap(other);
    return *this;
}
```

模型：

```text
construct temporary
    ↓ may fail
old object unchanged

swap
    ↓ noexcept
commit

temporary destroys old state
```

这是非常清晰的 strong-guarantee 教学模型。

但不是所有类型都应该机械使用：

```text
temporary allocation
capacity reuse lost
performance tradeoff
```

需要实际评估。

<a id="fm4-part-3"></a>

## 三、清理与外部副作用

### 12. Resource Acquisition 顺序

多个资源：

```cpp
File file = open_file();
Socket socket = open_socket();
Buffer buffer = allocate_buffer();
```

每一步成功后立刻进入 owner。

那么：`buffer acquisition fails`

之前的：

```text
socket
file
```

都会由 RAII 自动清理。

不要：

```text
先获取三个 raw handle
再统一包装
```

这样会扩大 failure window。

### 13. Destruction 是 Cleanup Infrastructure

Destructor 应：`restore resource ownership balance`

而不是承担复杂可能失败的业务事务。

如果：

```text
flush
commit
network close handshake
database commit
```

的失败需要调用者知道，应提供：

```cpp
std::expected<void, CloseError> close();
```

析构函数只做：`non-throwing fallback cleanup`

### 14. State Guarantee 必须组合分析

高层操作的保证依赖：`sub-operation guarantees`

例如：

```text
Algorithm guarantee
=
allocation guarantee
+
T construction guarantee
+
T move/copy guarantee
+
commit operation guarantee
```

因此 generic code 不能脱离 `T` 的 semantics 宣称 guarantee。

### 15. Failure 与 Partial Side Effects

内存临时状态可以在未发布时丢弃；邮件已发送、付款已提交或消息已被确认，却可能没有恢复原状的逆操作。因此必须先限定 strong guarantee 所覆盖的状态，再描述外部效果。

回滚（rollback）恢复约定旧状态；补偿（compensation）用新动作补救已发生的效果，不保证历史被抹去，补偿自身也可能失败。无法保证全有或全无时，应明确部分进度、已提交范围及可重试条件，而不是把资源清理写成业务回滚。

### 16. Ambiguous Completion

典型：

```text
request sent
server committed
response lost
```

调用者看到：`timeout`

但实际：`operation may already have succeeded`

这不是普通 strong/basic guarantee 能完全表达的。

需要：

```text
idempotency
operation ID
deduplication
query-after-failure
transaction protocol
```

### 17. RAII 不等于 Transaction

RAII 可以保证：`resource cleanup`

但不能自动保证：`business state rollback`

例如：`File handle successfully closed`

并不能回滚：`已经写入磁盘的数据`

两者必须分开。

<a id="fm4-part-4"></a>

## 四、审查与回查

### 18. FM-4 Review Checklist

先用[公共 C1–C8 合同](series-guide.md#review-contract)检查完整操作，再用以下问题回查本章机制。

```text
[ ] 当前组件负责释放的 resource 是否立即进入明确的 owner，借用是否保持 non-owning？
[ ] raw ownership window 是否最小？
[ ] 对象是否存在 partially initialized state？
[ ] 异常传播、失败后状态和终局处置是否分别声明？
[ ] guarantee 是否依赖 T 的操作？
[ ] commit point 是否明确？
[ ] prepare 阶段是否修改原状态？
[ ] commit 是否真正 no-fail（含前置条件、错误返回与收尾），而不只是 noexcept？
[ ] rollback 本身是否可能失败？
[ ] destructor 是否承担可失败业务逻辑？
[ ] external side effect 是否存在 ambiguous completion？
[ ] failure 后 ownership／release responsibility 是否仍然明确（包括共享所有权）？
```

### 19. FM-4 核心不变量

> 当前组件负责释放的资源，应由明确的 owner / resource handle 将释放责任绑定到对象生命周期；借用资源必须明确保持 non-owning。

这是资源责任的工程建议，不要求当前组件拥有所有访问到的资源；参见 [C++ Core Guidelines R.1](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#Rr-raii) 与 [R.3](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines#Rr-ptr)。

> Strong guarantee 的首选模型是 prepare-then-commit，而不是复杂 rollback。

> Basic guarantee 至少要求 invariant 与 ownership 仍然正确。

> RAII 在适用生命周期路径履行资源清理责任；清理动作及其成功条件仍需审查，不自动保证业务事务原子性。

> External side effect 必须单独定义 commit semantics。
