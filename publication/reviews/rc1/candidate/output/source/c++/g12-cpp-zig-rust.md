# G12 · 统一系统模型与工程审查

**版本：** 1.1.1 · Professional Handbook · 全书一致性修订

**状态：** 本轮编辑修订待集中审核；接受历史与冻结候选见[系列状态](README.md#基线与证据状态)。PDF **NOT BUILT / NOT VALIDATED**。

**语言基线与范围：** C++23。Unified Systems Model；承接 G0～G11，Rust/Zig 仅作第二层机制对照。

**阅读约定：** [Editorial Profile v1.0](editorial-profile.md) · [全书术语、证据与引用](handbook-guide.md)。

[上一章：G11](g11-robotics.md) · [全系列导航](README.md)

## 阅读入口

先用 §1～12 重建 C++ 系统模型，再做 §18 的综合审查。Rust/Zig 用来识别证明责任的差异，不要求并行学习三门语言，也不新增独立语言实验。

原稿的 Complete/Frozen 是历史编辑标记，不沿用为技术验收。编号主题以 `g12-topic-N` 映射到相应主题组，保留技术去向；章节不再逐个复制原有 Part。完整实验与机制片段有可见身份，Gate 答案是普通章节。

- [1. 全书的终点：分配证明责任](#g12-section-1)
- [2. 对象、存储与清理边界](#g12-section-2)
- [3. 所有权、借用、别名与值传递](#g12-section-3)
- [4. 分配与失败：机制不等于事务](#g12-section-4)
- [5. 泛型、分派与容器抽象](#g12-section-5)
- [6. 机器成本与并发协议](#g12-section-6)
- [7. 二进制与构建：保证到哪里结束](#g12-section-7)
- [8. 编译期元数据与外部生成](#g12-section-8)
- [9. 时限、嵌入式与性能证据](#g12-section-9)
- [10. 安全抽象、状态与 API 合同](#g12-section-10)
- [11. 子系统选择与跨语言成本](#g12-section-11)
- [12. 可迁移的系统审查协议](#g12-section-12)
- [13. 四类项目的对照推理](#g12-section-13)
- [14. 长期维护与常见错误推论](#g12-section-14)
- [15. 三类论证与六张关系图](#g12-section-15)
- [16. 跨章应用与语言反思](#g12-section-16)
- [17. 可带入新项目的最终检查](#g12-section-17)
- [18. 审查练习：把同一套模型用于三个案例](#g12-section-18)
- [19. 全书回查与证据分层](#g12-section-19)
- [20. Final Gate](#g12-section-20)
- [21. Final Gate · 参考答案与常见误判](#g12-section-21)
- [22. 参考资料与验证边界](#g12-section-22)

<a id="g12-section-1"></a>

<a id="g12-topic-0"></a>
<a id="g12-topic-1"></a>
<a id="g12-topic-2"></a>
<a id="g12-topic-3"></a>
<a id="g12-topic-4"></a>

## 1. 全书的终点：分配证明责任

### 1.1 先识别系统问题，再讨论语言

本章不是 C++、Rust、Zig 功能排名。C++ 是正文主线；另两种语言帮助区分偶然的语言机制与真实系统复杂性。C++ 的值类别、重载规则和文本包含有明显语言历史；但所有权转移、借用失效、分配拓扑、跨核顺序、二进制合同和时限并不会因为换语言而消失。

统一问题是：系统要求什么，哪个层次表达它，谁负责证明？类型检查、库封装、架构不变量、动态检测和部署观察不是互相替代的“安全分数”。选择语言是选择一部分证明责任（proof burden）的分配，不是把整个系统正确性外包给编译器。

### 1.2 比较的基线与限制

C++ 基线为 C++23/N4950；Rust 保留 2024 edition 对照口径，所有权、布局与 unsafe 概念回查固定到 1.85.0 随附官方文档，读取日期与摘要见[引用约定](handbook-guide.md#4-参考资料的版本与访问身份)；Zig 机制回查固定 0.15.2 文档，不使用含糊的“Modern Zig”版本。本批不运行 Rust/Zig 编译器，所有比较均为解释模型，不构成交叉语言兼容性或性能验证。

C++ 提供 RAII、值类型、模板与机器表示控制，但许多非法访问要由程序员排除；safe Rust 把更多借用和线程共享合法性放进静态约束，仍依赖 unsafe 实现的健全性（soundness）；Zig 的 allocator、错误和清理表达更显式，却不提供同样的 borrow-checking 保证。不要把示意风格画成优劣坐标。

<a id="g12-section-2"></a>

<a id="g12-topic-5"></a>
<a id="g12-topic-6"></a>
<a id="g12-topic-7"></a>
<a id="g12-topic-8"></a>
<a id="g12-topic-9"></a>
<a id="g12-topic-10"></a>
<a id="g12-topic-11"></a>
<a id="g12-topic-12"></a>
<a id="g12-topic-13"></a>
<a id="g12-topic-14"></a>
<a id="g12-topic-15"></a>
<a id="g12-topic-16"></a>

## 2. 对象、存储与清理边界

### 2.1 用 C++ 对象模型打开问题

storage 是存放对象的资源，object 是具有类型与生命周期的语言实体，value 是其状态；三者不能互换。取得足够对齐的存储不普遍意味着已经构造任意 T；手工构造、销毁与复用继续受 [G1](g01-object-model.md#g1-object) 的规则约束。Rust 的 value/place 与 Zig 的 typed storage 不是逐字对应 C++ 标准术语，但都要回答初始化、访问有效期和存储回收。

owner.reset 后旧指针仍有地址，并不意味着对象仍活着。RAII 可以可靠安排 owner 的释放，却不能自动证明所有 borrower 都已结束。Rust 静态借用规则能排除许多此类 safe-code 路径；Zig 的 defer 让配对可见，却不会检查整个借用图。

### 2.2 类型驱动与作用域驱动的清理

C++ 的析构函数和 Rust Drop 可把资源清理能力绑定到拥有类型；Zig 常在获取资源旁用 defer/errdefer 安排清理。类型携带 deinit 方法不意味着 Zig 会自动调用它，复制一个资源结构体也不自动取消原值的清理责任。

这些是正常语言控制流下的机制，不是“任何进程终止都会执行清理”的保证。C++ terminate、Rust panic=abort、进程被杀或显式泄漏均需单独处理。不要用 cleanup 示例推导持久化事务、设备断电或远端副作用一定回滚；[FM 失败模型](failure-model/README.md)专门展开这些边界。

<a id="g12-section-3"></a>

<a id="g12-topic-17"></a>
<a id="g12-topic-18"></a>
<a id="g12-topic-19"></a>
<a id="g12-topic-20"></a>
<a id="g12-topic-21"></a>
<a id="g12-topic-22"></a>
<a id="g12-topic-23"></a>
<a id="g12-topic-24"></a>
<a id="g12-topic-25"></a>
<a id="g12-topic-26"></a>
<a id="g12-topic-27"></a>
<a id="g12-topic-28"></a>
<a id="g12-topic-29"></a>
<a id="g12-topic-30"></a>
<a id="g12-topic-31"></a>
<a id="g12-topic-32"></a>
<a id="g12-topic-33"></a>
<a id="g12-topic-34"></a>

## 3. 所有权、借用、别名与值传递

### 3.1 可写权限比指针形状更重要

C++ 的 value、unique_ptr、shared_ptr、引用和 span 可表达不同意图；裸 T* 仍可能表示 owner、nullable borrow 或外部句柄，必须有合同。`span<const T>` 只禁止经该视图修改元素，不保证底层不可被其他别名修改，更不会延长 owner 生命周期；它与仅将视图对象声明为 `const span<T>` 不同。

Rust &T 的共享访问需考虑 UnsafeCell 内部可变性，不能粗暴说“所有内容永远 immutable”；&mut T 提供受规则约束的独占访问。unsafe/raw pointer 并不免除别名与有效性义务，精确 unsafe 模型也不能被几句口号替代。[Rust Reference](https://doc.rust-lang.org/1.85.0/reference/behavior-considered-undefined.html)

Zig 的 []const T、[]T、指针形状表达访问方式与长度，但不静态证明整个 borrower graph。三种 slice 在机器层可能都类似地址+长度，不能据此跨 ABI 假定布局，也不能认为语言保证相同。

### 3.2 三种“移动”不能直接翻译

C++ std::move 是表达式转换，实际调用由重载决议决定；用户定义的 move 可转移资源，也可没有期望的廉价行为，移后源对象还存在并受其类型合同约束。Rust 非 Copy 值移动使原 binding 不再可用，不是调用用户 move constructor；Copy 也不是“成本必定很小”的性能保证。

Zig 普通赋值没有 Rust 式源值不可用的所有权状态转移。拥有资源的 struct 若普通复制后两边都 deinit，可能重复释放。语言不同，但审查仍应画 owner、借用期限、别名和写入权限（mutation authority），再检查复制/移动究竟改变了哪条边，详见 [G2](g02-raii-and-ownership.md#g2-section-1) 与 [G3](g03-value-semantics-and-performance.md#g3-section-4)。

<a id="g12-section-4"></a>

<a id="g12-topic-35"></a>
<a id="g12-topic-36"></a>
<a id="g12-topic-37"></a>
<a id="g12-topic-38"></a>
<a id="g12-topic-39"></a>
<a id="g12-topic-40"></a>
<a id="g12-topic-41"></a>
<a id="g12-topic-42"></a>
<a id="g12-topic-43"></a>
<a id="g12-topic-44"></a>
<a id="g12-topic-45"></a>
<a id="g12-topic-46"></a>
<a id="g12-topic-47"></a>
<a id="g12-topic-48"></a>
<a id="g12-topic-49"></a>
<a id="g12-topic-50"></a>

## 4. 分配与失败：机制不等于事务

### 4.1 谁拥有存储策略

C++ vector/PMR 与 Rust Vec/Box 常把普通分配隐藏在 owner 内；Zig 常把 allocator 参数显式传给需要动态内存的函数。显式分配能力允许调用者选择 arena、池或固定缓冲，但 API 出现 allocator 不意味着内部不会分配、不会锁或一定更快。反过来，高层 owner 简化使用，却要求另标注容量、重用和分配失败边界。

分配拓扑要同时写明发生频率、由谁释放、何时回收和能否有界。C++ resource 必须比使用它的 PMR 容器活得久；传入 allocator 和保存 allocator 都有生命周期义务。机器成本取决于实际策略，而非语言名。

### 4.2 错误通道没有自动回滚

expected、Result 与 Zig error union 都可把预期失败作为值传播；C++ exceptions 提供另一传播通道，panic/terminate/abort 又是不同级别的停止策略。取消是控制结果，不能无条件合并为业务错误；bug/invariant failure 与可恢复失败应分开处理。

先修改 A，再修改 B，最后返回错误，三种语言都不会自动恢复 A。强事务保证仍需要 prepare → commit、补偿或明确部分提交合同。析构/Drop/defer 能处理资源，却不普遍撤销外部动作。跨边界转换错误时还要定义输出是否有效、是否重试以及谁已接收责任。

<a id="g12-section-5"></a>

<a id="g12-topic-51"></a>
<a id="g12-topic-52"></a>
<a id="g12-topic-53"></a>
<a id="g12-topic-54"></a>
<a id="g12-topic-55"></a>
<a id="g12-topic-56"></a>
<a id="g12-topic-57"></a>
<a id="g12-topic-58"></a>
<a id="g12-topic-59"></a>
<a id="g12-topic-60"></a>
<a id="g12-topic-61"></a>
<a id="g12-topic-62"></a>
<a id="g12-topic-63"></a>

## 5. 泛型、分派与容器抽象

### 5.1 编译期特化共享同一种成本取舍

C++ templates/concepts、Rust generics/traits 与 Zig comptime 都能让静态已知信息形成专门代码；具体机制、约束检查和实例化时机不同。C++ concepts 不证明任意运行时语义，Rust trait bounds 不自动证明业务合同，comptime 也不意味着所有成本免费。

特化可能减少运行时分支并促进内联，同时增加构建时间、二进制体积、调试复杂度与指令缓存压力。动态 virtual、trait object、函数表或类型擦除可能更紧凑，但带来间接分派及生命周期接口。选择依据实际变化维度，参见 [G5](g05-generics-and-compile-time.md#g5-section-9)。

### 5.2 相似容器背后仍有失效规则

vector、Vec 与 allocator-backed dynamic array 都可能拥有连续存储；span、slice 则借用范围。增长引发重分配会改变地址，稳定地址、稳定索引和稳定逻辑身份不是同一要求。Rust 约束可阻止很多借用期间增长的 safe-code 错误，C++/Zig 需要明确 API 失效规则。

“指针、大小、容量”是理解成本的模型，不是所有容器必须具有这三字段、可以跨语言 memcpy 的布局规范。跨 ABI 只传双方正式约定的表示，不能用容器相似性跳过 G8。

<a id="g12-section-6"></a>

<a id="g12-topic-64"></a>
<a id="g12-topic-65"></a>
<a id="g12-topic-66"></a>
<a id="g12-topic-67"></a>
<a id="g12-topic-68"></a>
<a id="g12-topic-69"></a>
<a id="g12-topic-70"></a>
<a id="g12-topic-71"></a>
<a id="g12-topic-72"></a>
<a id="g12-topic-73"></a>
<a id="g12-topic-74"></a>
<a id="g12-topic-75"></a>
<a id="g12-topic-76"></a>
<a id="g12-topic-77"></a>
<a id="g12-topic-78"></a>
<a id="g12-topic-79"></a>
<a id="g12-topic-80"></a>
<a id="g12-topic-81"></a>
<a id="g12-topic-82"></a>
<a id="g12-topic-83"></a>
<a id="g12-topic-84"></a>
<a id="g12-topic-85"></a>
<a id="g12-topic-86"></a>
<a id="g12-topic-87"></a>
<a id="g12-topic-88"></a>

## 6. 机器成本与并发协议

### 6.1 类型安全不能取消缓存与同步成本

连续性、对齐、working set、指针追逐、TLB 和 AoS/SoA 取决于具体访问路径。shared_ptr、Arc 或自建原子引用计数都可能付出间接访问和缓存行竞争；安全拥有不是 contention-free。零额外抽象成本也不意味着所选算法、分配和同步本身免费，仍要测具体实现，详见 [G6](g06-memory-and-performance.md#g6-section-9)。

### 6.2 数据竞争安全不等于协议正确

C++ 通过 mutex/atomic 建立 happens-before；safe Rust 的 Send/Sync 与借用约束排除一大类非法跨线程访问，但不能自动排除死锁、错误关闭顺序、过载或原子状态机的逻辑错误。实现 Send/Sync 的 unsafe 责任不能交给命名猜测。[Rustonomicon](https://doc.rust-lang.org/1.85.0/nomicon/send-and-sync.html)

单写者、分片、不可变 generation 与消息传递能简化三种语言中的共享图。队列交接仍有接收点、失败、背压和析构责任；C++ 的 std::move 不像 Rust 一样禁止随后使用源变量。原子 acquire/release 只在具体读写关系满足条件时发布数据，不能把“用了 acquire”当普遍 barrier。

### 6.3 进展与回收是独立证明

lock-free 描述系统进展，不保证每个线程在限定步骤内完成，也不是性能排名。并发节点何时可回收仍需要 hazard、epoch、引用拥有或其他协议；语言静态借用不能自动表达所有动态回收算法。Rust unsafe 将人工义务局部化，但仍须保持有效值、生命周期和别名不变量；C++/Zig 同样应缩小低层实现边界，而非让裸指针遍布业务。

<a id="g12-section-7"></a>

<a id="g12-topic-89"></a>
<a id="g12-topic-90"></a>
<a id="g12-topic-91"></a>
<a id="g12-topic-92"></a>
<a id="g12-topic-93"></a>
<a id="g12-topic-94"></a>
<a id="g12-topic-95"></a>
<a id="g12-topic-96"></a>
<a id="g12-topic-97"></a>
<a id="g12-topic-98"></a>
<a id="g12-topic-99"></a>
<a id="g12-topic-100"></a>
<a id="g12-topic-101"></a>
<a id="g12-topic-102"></a>
<a id="g12-topic-103"></a>
<a id="g12-topic-104"></a>
<a id="g12-topic-105"></a>
<a id="g12-topic-106"></a>

## 7. 二进制与构建：保证到哪里结束

### 7.1 C ABI 是可约定的底层边界，不是安全证书

C++ 与 Rust 原生 ABI 都不应被当作跨任意工具链版本的长期通用合同，Zig native 表示也不能直接等同 C。明确目标平台的 C ABI、版本化结构、不透明句柄和创建者销毁接口能缩小互操作表面，但仍须规定大小/对齐、空值、范围、借用、回调、线程与错误。

Rust raw pointer FFI 无法由编译器推断 C 库是否保留指针、能否并发销毁；错误的 safe wrapper 可以把不成立的 unsafe 假设暴露给所有调用者。C++ private vector 成员仍参与公开类布局，只有真正隐藏对象或合适 PImpl 等边界才能隔离，不能把 private 误认成 ABI 不可见。参见 [G8](g08-abi-and-c-interop.md#g8-section-4)。

### 7.2 工具整合度不同，依赖图仍存在

CMake/Ninja 与包管理器分工，Cargo 整合 package/build/test 流程，Zig toolchain 提供构建图工具。它们都有制品节点、输入与依赖边；遗漏生成器输入、工具身份或链接依赖，仍会造成陈旧或不完整产物。

C++ 文本包含、宏配置、翻译单元与历史 ABI 增加一些语言特有复杂性；Rust cfg 与 Zig comptime/build options 用不同机制表达配置，但不会消除条件组合测试。源码能编译、能链接、能运行、能安装消费是不同 Gate，详见 [G9](g09-build-and-native-ecosystem.md#g9-section-7)。

<a id="g12-section-8"></a>

<a id="g12-topic-107"></a>
<a id="g12-topic-108"></a>
<a id="g12-topic-109"></a>
<a id="g12-topic-110"></a>
<a id="g12-topic-111"></a>
<a id="g12-topic-112"></a>

## 8. 编译期元数据与外部生成

### 8.1 不把所有 schema 塞进类型系统

静态 DBC/schema、协议表和多车型配置可以用 C++ constexpr/生成源码、Rust const/build script/procedural macro、Zig comptime/外部生成表达。问题不是哪种语法最短，而是源数据身份、诊断位置、生成文件可审阅性与编译成本是否可控。

大量外部元数据用独立生成阶段有利于区分解析错误和语言编译错误，也便于 diff 生成结果。若使用语言内特化，则要限制生成量并记录输入依赖。G9 的 build graph 原则继续适用，不能因为 generator 写在语言工具链里就不声明依赖。

### 8.2 泛型预算是长期维护预算

每个变体都可能增加诊断、链接、缓存和 code-size 成本。选择表驱动还是专门代码，应把版本更新、测试覆盖与可观察机器结果一起比较。本章不增加新的 decoder 实现；将此前知识压缩成设计选择问题，而不是再建一套特化框架。

<a id="g12-section-9"></a>

<a id="g12-topic-113"></a>
<a id="g12-topic-114"></a>
<a id="g12-topic-115"></a>
<a id="g12-topic-116"></a>
<a id="g12-topic-117"></a>
<a id="g12-topic-118"></a>
<a id="g12-topic-119"></a>
<a id="g12-topic-120"></a>
<a id="g12-topic-121"></a>
<a id="g12-topic-122"></a>
<a id="g12-topic-123"></a>
<a id="g12-topic-124"></a>
<a id="g12-topic-125"></a>
<a id="g12-topic-126"></a>
<a id="g12-topic-127"></a>
<a id="g12-topic-128"></a>

## 9. 时限、嵌入式与性能证据

### 9.1 没有 GC 只是一个条件

C++ 的析构、Rust 的 Drop、Zig 的 defer 都可能执行有成本的清理；通用 allocator、OS 调度、锁与 I/O 仍可能无可用上界。memory-safe 或 allocation-explicit 都不是 deadline 证明。嵌入式语言选择还受目标工具链、vendor SDK、no_std/runtime 支持、调试与认证约束。

实时需求必须在平台、负载、输入上界与故障模型下分析，不能用桌面 microbenchmark 代替。[G11](g11-robotics.md#g11-section-16) 的 timing observation 与物理时限论证分开，是这个原则的具体例子。

### 9.2 性能比较必须比较同一个命题

语言不能统一预测最快实现。算法、布局、分配、检查消除、编译器、并发拓扑和工作负载共同决定结果。Rust 的边界检查可能消除也可能保留；C++ 抽象可能优化掉也可能导致额外工作；Zig 显式代码也可能有差的局部性。

用等价功能和失败边界比较，保留原始时间、参数和校验值。specialization 同时影响编译时间、代码大小与 I-cache；不能只比较执行热点忘记交付成本。本批没有三语言 benchmark、嵌入式或跨平台运行。

<a id="g12-section-10"></a>

<a id="g12-topic-129"></a>
<a id="g12-topic-130"></a>
<a id="g12-topic-131"></a>
<a id="g12-topic-132"></a>
<a id="g12-topic-133"></a>
<a id="g12-topic-134"></a>
<a id="g12-topic-135"></a>
<a id="g12-topic-136"></a>
<a id="g12-topic-137"></a>
<a id="g12-topic-138"></a>
<a id="g12-topic-139"></a>
<a id="g12-topic-140"></a>
<a id="g12-topic-141"></a>
<a id="g12-topic-142"></a>
<a id="g12-topic-143"></a>
<a id="g12-topic-144"></a>
<a id="g12-topic-145"></a>
<a id="g12-topic-146"></a>
<a id="g12-topic-147"></a>
<a id="g12-topic-148"></a>
<a id="g12-topic-149"></a>
<a id="g12-topic-150"></a>

## 10. 安全抽象、状态与 API 合同

### 10.1 将非法状态排除到哪一层

enum/variant、Rust enum 与 Zig tagged union 都能把状态相关数据绑在一个合法分支；但转换是否合法仍需要业务条件。nullable、optional、owned、borrowed 是不同维度，不能让一个裸指针无声地承担所有意义。

Rust 的静态保证依赖正确的编译器、库与 unsafe 封装，并非“任何写着 Rust 的系统都不会出内存错误”；C++ 工程约定与 sanitizer 有价值，却不是同等静态保证；Zig 显式检查也不能自动证明生命周期。低层实现边界应小而可审查，外部 API 必须让安全使用者不容易破坏内部不变量。

### 10.2 借用输入、拥有输出是同一个系统合同

[机制片段 · C++ 接口合同示意，不承诺独立编译]

```cpp
std::expected<std::vector<float>, DecodeError>
decode(std::span<const std::byte> input);
```

这里输入只借用到调用返回，输出 owner 负责释放，但签名本身仍未说明别名限制、长度上界和分配失败。Rust 的 `Result<Vec<_>, _>` 以另一套类型约束表达拥有结果；Zig 的 ![]f32 则还需要写清结果由哪个 allocator 释放，或用显式 deinit 的 owner 结构封装。不能把任意 slice 都叫 owned。

内部可以使用丰富语言抽象，稳定外部用小 C adapter 映射 status、输出和释放接口。便利 API 与分配可见性有取舍，关键是用户能知道调用期间哪些资源和责任发生变化。

<a id="g12-section-11"></a>

<a id="g12-topic-151"></a>
<a id="g12-topic-152"></a>
<a id="g12-topic-153"></a>
<a id="g12-topic-154"></a>
<a id="g12-topic-155"></a>
<a id="g12-topic-156"></a>
<a id="g12-topic-157"></a>
<a id="g12-topic-158"></a>
<a id="g12-topic-159"></a>
<a id="g12-topic-160"></a>
<a id="g12-topic-161"></a>
<a id="g12-topic-162"></a>
<a id="g12-topic-163"></a>
<a id="g12-topic-164"></a>
<a id="g12-topic-165"></a>
<a id="g12-topic-166"></a>
<a id="g12-topic-167"></a>
<a id="g12-topic-168"></a>
<a id="g12-topic-169"></a>
<a id="g12-topic-170"></a>
<a id="g12-topic-171"></a>
<a id="g12-topic-172"></a>
<a id="g12-topic-173"></a>
<a id="g12-topic-174"></a>
<a id="g12-topic-175"></a>

## 11. 子系统选择与跨语言成本

### 11.1 根据依赖与风险选局部边界

已有 C++ SDK、数值库和原生生态可能使 C++ 最直接；复杂不可信输入及共享生命周期可能提高 Rust 静态约束的价值；显式 allocator、C glue 和小型底层工具可能契合 Zig。它们是评估维度，不是“控制一定 C++、服务一定 Rust、驱动一定 Zig”的固定分工。

生态、团队熟悉度、debugger、构建支持、认证和五年维护成本都要进入决策。旧系统若已经满足合同，仅因语言更新而重写没有自动收益；也不能用既有生态为所有内存风险免责。

### 11.2 FFI 要翻译语义，不只翻译类型

跨语言增加工具链、包生态、CI、调试、错误与所有权翻译。边界宜粗且稳定，减少每几个操作就在语言间往返。Creator destroys 便于维持分配域；跨边界保留内存用显式 handle 或 release callback；调用期 borrow 不能被后台偷偷保存。

exception/Result/error union 可转为 C status 与输出，但输出有效性和重试责任必须一起翻译。Send/Sync 不会穿过 void* 自动生效，同一 handle 是否可并发、destroy 是否需要静默期、callback 在何线程都要公开。语言保证、库抽象、架构不变量是三个层次，不能把其中一个当作全部。

<a id="g12-section-12"></a>

<a id="g12-topic-176"></a>
<a id="g12-topic-177"></a>
<a id="g12-topic-178"></a>
<a id="g12-topic-179"></a>
<a id="g12-topic-180"></a>
<a id="g12-topic-181"></a>
<a id="g12-topic-182"></a>
<a id="g12-topic-183"></a>
<a id="g12-topic-184"></a>
<a id="g12-topic-185"></a>
<a id="g12-topic-186"></a>
<a id="g12-topic-187"></a>
<a id="g12-topic-188"></a>
<a id="g12-topic-189"></a>
<a id="g12-topic-190"></a>
<a id="g12-topic-191"></a>
<a id="g12-topic-192"></a>
<a id="g12-topic-193"></a>
<a id="g12-topic-194"></a>
<a id="g12-topic-195"></a>
<a id="g12-topic-196"></a>

## 12. 可迁移的系统审查协议

### 12.1 用可回答的问题建立记录

面对新项目，按如下顺序写出具体对象、边和证据，而不是勾“已考虑”。缺少证据可以记 UNKNOWN，不能根据语言选择补成 PASS。

| 审查层 | 必须回答 | 需要的产物 |
| --- | --- | --- |
| State / lifetime | 什么状态，何时失效 | 对象与生命周期图 |
| Owner / borrow | 谁释放，谁临时访问 | 拥有/借用期限 |
| Mutation / alias | 谁可写，路径是否重叠 | writer 与别名合同 |
| Storage / allocation | 大小、频率、上界、回收 | 资源预算与观测 |
| Failure / commit | 失败前后谁已负责 | 状态机与提交点 |
| Concurrency / overload | 顺序、等待、容量、唤醒 | 同步和关闭论证 |
| ABI / build | 什么跨独立制品边界 | 接口与消费实验 |
| Timing / evidence | 期限和已知证据范围 | 条件化观察及缺口 |

### 12.2 语言选择放在约束之后

C++ 编译器检查类型、约束与部分静态语义，不完整证明动态指针合法性；Rust 提供更多所有权/共享约束，也不自动检查业务账目或调度；Zig 的类型、comptime 与模式相关检查同样不是全系统证明器。

单位、正确 shard key、过载策略、交易提交和 actuator 安全仍需领域定义。随后才选择哪些义务交给类型系统、哪些交给库、哪些需审查和运行证据。这里的“证明”是明确前提下的论证，不暗示本手册已经完成形式化验证。

<a id="g12-section-13"></a>

<a id="g12-topic-197"></a>
<a id="g12-topic-198"></a>
<a id="g12-topic-199"></a>
<a id="g12-topic-200"></a>
<a id="g12-topic-201"></a>
<a id="g12-topic-202"></a>
<a id="g12-topic-203"></a>
<a id="g12-topic-204"></a>
<a id="g12-topic-205"></a>
<a id="g12-topic-206"></a>
<a id="g12-topic-207"></a>
<a id="g12-topic-208"></a>
<a id="g12-topic-209"></a>
<a id="g12-topic-210"></a>

## 13. 四类项目的对照推理

### 13.1 同一协议，不同风险权重

高吞吐二进制 decoder 应先写清输入不可信程度、边界检查、schema 身份、输出所有权和 C ABI。C++ 的 span/生成表、Rust 的 slice/Result、Zig 的 allocator/comptime 都能表达实现；选择取决于已有系统和风险，不先作速度排名。

并发网络服务还需任务拥有、取消、超时和背压；memory safety 可以降低攻击面，却不能防止永不关闭的连接队列。机器人 core 增加测量时间、单位、硬件 watchdog 与部署时限；小型原生工具增加目标支持、C 库和可分发构建。四者不能由同一“语言得分表”解决。

### 13.2 成本问题要落到实现

问字节数、分配次数、分支、cache miss 和同步操作，而不是“哪门语言最快”。hash map 的具体实现、安全策略和数据分布可能比语言本身影响更大。原子计数、连续数组和间接图也只有在布局和访问一致时才可比较。

选择语言实际上决定一部分风险由编译器排除、一部分通过清晰 API 限制、一部分靠测试和运行管理。它不是无代价转移，仍要记录替代方案与缺失证据。

<a id="g12-section-14"></a>

<a id="g12-topic-211"></a>
<a id="g12-topic-212"></a>
<a id="g12-topic-213"></a>
<a id="g12-topic-214"></a>
<a id="g12-topic-215"></a>
<a id="g12-topic-216"></a>
<a id="g12-topic-217"></a>
<a id="g12-topic-218"></a>
<a id="g12-topic-219"></a>
<a id="g12-topic-220"></a>
<a id="g12-topic-221"></a>
<a id="g12-topic-222"></a>
<a id="g12-topic-223"></a>
<a id="g12-topic-224"></a>
<a id="g12-topic-225"></a>
<a id="g12-topic-226"></a>

## 14. 长期维护与常见错误推论

### 14.1 系统由团队和时间共同塑造

代码审查能力、工具链支持、依赖健康、入职成本、调试和升级能力，都影响长期风险。C++ 团队需要明确 owner/borrow 与构建规范；Rust 团队仍需审查 unsafe、async 和 FFI；Zig 团队仍需统一 allocator 与清理协议。语言简洁不自动带来一致架构。

小而版本化的 C 边界可以作为渐进替换点，但替换实现仍要验证语义、并发、分配域和旧消费者。API 长寿、可调试性与迁移成本通常值得和今天的几个百分点性能一起权衡。

### 14.2 不接受从局部优势推到整体正确

Memory-safe 程序仍可死锁、错算金额或发错力矩；显式代码仍可显式写错 lifetime；RAII 仍允许悬挂 borrow；borrow checker 不能推断所有外部资源合同；无 GC 不等于 real-time；C ABI 不等于安全边界；多语言不必然降低复杂度。

工程上应要求每个强结论指出前提、机制、反例与证据，而非“某语言所以不需要检查”。本章不发布语言选型排名，也不倡导为了风格纯度整体重写。

<a id="g12-section-15"></a>

<a id="g12-topic-227"></a>
<a id="g12-topic-228"></a>
<a id="g12-topic-229"></a>
<a id="g12-topic-230"></a>
<a id="g12-topic-231"></a>
<a id="g12-topic-232"></a>
<a id="g12-topic-233"></a>
<a id="g12-topic-234"></a>
<a id="g12-topic-235"></a>
<a id="g12-topic-236"></a>
<a id="g12-topic-237"></a>
<a id="g12-topic-238"></a>
<a id="g12-topic-239"></a>

## 15. 三类论证与六张关系图

### 15.1 语义、安全和运行合同分开

语义论证回答输出/状态是否正确；安全论证回答执行是否违反内存、生命周期和共享规则；运行合同论证回答资源、过载、故障与时限是否满足部署需求。编译接受、sanitizer clean、吞吐更高分别只覆盖这些维度的一部分。

六张图分别是 ownership、lifetime、mutation、storage/cost、synchronization 与 binary-boundary。一个 Buffer 的 private vector 管存储，span 借用，扩容使旧路径失效，线程写入需要权限，类是否跨 ABI 暴露仍取决于外部表示。这比只认识 class/vector/span 的语法多出整套工程含义。

### 15.2 不可变配置仍要发布与回收

C++ `atomic<shared_ptr<const Config>>`、Rust 受同步保护的 Arc generation、Zig 明确的 pointer/reclamation 都须完成“私下构造 → 发布 → 旧读者结束 → 回收”。没有任何一个语法自动证明控制线程的最后释放有界。

借用输出接口、显式 allocator 及拥有型结果的对照，应回到这些图检查。G12 不再添加重复编译例子，而在 §18 用 G10/G11 的实际协议和证据缺口练习整套审查。

<a id="g12-section-16"></a>

<a id="g12-topic-240"></a>
<a id="g12-topic-241"></a>
<a id="g12-topic-242"></a>
<a id="g12-topic-243"></a>
<a id="g12-topic-244"></a>
<a id="g12-topic-245"></a>
<a id="g12-topic-246"></a>
<a id="g12-topic-247"></a>
<a id="g12-topic-248"></a>
<a id="g12-topic-249"></a>
<a id="g12-topic-250"></a>
<a id="g12-topic-251"></a>
<a id="g12-topic-252"></a>
<a id="g12-topic-253"></a>
<a id="g12-topic-254"></a>
<a id="g12-topic-255"></a>
<a id="g12-topic-256"></a>
<a id="g12-topic-257"></a>
<a id="g12-topic-258"></a>
<a id="g12-topic-259"></a>
<a id="g12-topic-260"></a>

## 16. 跨章应用与语言反思

### 16.1 G10 与 G11 共享底层责任

G10 无论由哪种语言实现，仍要保证 accepted work 有结果、队列有界、abort 唤醒、线程先退出再销毁依赖；G11 在此之上增加单位、时间域、freshness、故障锁存与 safe actuation。改变语言不会消除这些架构边。

语言能减少一类非法程序的可表达空间，仍不能决定 capacity 是否符合负载、deadline 是否可满足、业务事件是否允许丢失。比较 Rust/Zig 应帮助发现 C++ 接口中未表达的义务，不是把它们加入本手册当作新课程。

### 16.2 从比较反过来改进 C++ 设计

从 Rust 学到的是缩短可变借用、使 owner 可见、用 variant/expected 减少非法状态；从 Zig 学到的是分配能力、失败与低层机制应在关键边界可见。C++ 也提醒其他语言：ABI、最终布局、析构顺序和原生工具链都是现实约束。

选择 subsystem 语言时同时看 ecosystem、safety、ABI、performance、timing、ownership、allocation、concurrency、tooling、team、certification 和 evolution，不简单给星级。保持 C++ 主线不是忽略其他设计，而是用同一套问题检验它们。

<a id="g12-section-17"></a>

<a id="g12-topic-261"></a>
<a id="g12-topic-262"></a>
<a id="g12-topic-263"></a>
<a id="g12-topic-264"></a>
<a id="g12-topic-265"></a>
<a id="g12-topic-266"></a>
<a id="g12-topic-267"></a>
<a id="g12-topic-268"></a>
<a id="g12-topic-269"></a>
<a id="g12-topic-270"></a>
<a id="g12-topic-271"></a>
<a id="g12-topic-272"></a>
<a id="g12-topic-273"></a>
<a id="g12-topic-274"></a>
<a id="g12-topic-275"></a>
<a id="g12-topic-276"></a>
<a id="g12-topic-277"></a>
<a id="g12-topic-278"></a>

## 17. 可带入新项目的最终检查

### 17.1 十二个问题形成一个可复用入口

对 Buffer、Connection、Job、RobotState、Decoder 或 Queue，回答：它是什么；住在哪里；谁拥有；谁借用；何时结束生命周期；什么使已有路径失效；复制/移动成本；分配在哪里；谁可写；跨线程顺序如何建立；什么跨 ABI；有何时限要求。

回答要包含真实对象和条件，不能只写“RAII”“atomic”“C ABI”。若某题依赖外部模块，需要列出对方的合同及失效后果；若未测量，记录缺口而非猜测。这样语言选择才是实现工具，系统约束才是主线。

### 17.2 正文到 G12 封顶

本书不再追加 G13。后续维护围绕实际使用、全书一致性和出版视图，不扩成新百科。原稿末尾的全系列 COMPLETE 只表示主题目录闭环，不能覆盖当前审核状态、平台限制和 PDF 未构建事实。

G0～G12 已接受源稿与本轮 Editorial Sweep 修订按[系列状态](README.md#基线与证据状态)分开：本轮形成待集中审核的内容冻结候选，未启动 PDF Pilot 或正式发布。学习成果应体现为能解释一个真实设计的责任与反例，而不是不断增加章节。

<a id="g12-section-18"></a>

## 18. 审查练习：把同一套模型用于三个案例

### 18.1 案例 A：运行时的账本为什么可能自洽却错误

**给定实现。** 提交者把任务放入队列后再写 accepted；worker 可能已经结束。汇总只用 succeeded + failed + cancelled 推算 accepted，再验证二者相等。

**独立推理。** 列出提交到消费的线性化点，寻找状态覆盖交错；指出从同一组终态算两边属于循环判据。应保留调用者实际 Accepted 返回记录、每个 ID 的预期和结果值；accepted 必须在消费者可见前登记。drain 后的未决项应暴露，而非悄悄归入 cancelled。

**对应证据。** [G10 协议](g10-systems-runtime-project.md#g10-section-4)给出锁内提交；[运行时实验](g10-systems-runtime-project.md#g10-section-18)记录调用者数量、逐 ID 结果与提前关闭 output 的错误变体。只支持这些输入与调度观察，不是持久化 exactly-once 或形式化证明。

### 18.2 案例 B：机器人“时间没问题”的错误推论

**给定声明。** 某次 1 kHz 仿真平均执行很快，allocation counter 为 0，TSan 没有报告，于是控制器被称为 hard-real-time safe。

**独立推理。** 平均耗时没有包含 release jitter 和最坏等待；计数器只观察当前线程的可替换 C++ allocation functions；TSan 不检查时限、单位或物理动作。还需明确平台、调度、驱动、页面、freshness、实际 safe state 和独立 watchdog。

**对应证据。** [G11 时序与边界](g11-robotics.md#g11-section-16)区分确定性模型与 timing observation。结论应拆为“模型注入满足判据”“观测到该范围分配数”“记录本机 jitter”“硬实时/HIL/物理安全 NOT VALIDATED”。没有把 1000 个采样改写为普遍上界。

### 18.3 案例 C：Rust 包装层为什么仍需审查 C++ 库

**给定接口。** C 库返回 opaque handle，包装者因为指针只是地址而为 wrapper 声明可跨线程共享；destroy 可能与后台 callback 并发。

**独立推理。** 地址可复制不代表被指对象可并发访问；Send/Sync 的安全前提必须来自库合同。应确定回调线程、停止注册与静默点、句柄销毁前在途调用是否结束、谁释放 callback context，以及异常/panic 如何限制。无法确认则不能给 safe API 承诺该共享能力。

**对应证据。** [G8 回调与销毁](g08-abi-and-c-interop.md#g8-section-11)提供审查模型。本批没有执行 Rust FFI、异步 callback 或动态卸载测试，案例 C 仅为推理练习。不能把前两例的 C++ 编译结果借来填补此缺口。

<a id="g12-section-19"></a>

## 19. 全书回查与证据分层

### 19.1 十三章是一条责任链

| 章节 | 应能回答的系统问题 |
| --- | --- |
| G0 / G1 | 机器制品如何形成，对象何时合法存在 |
| G2 / G3 | 谁管理资源，值怎样传递及付出什么成本 |
| G4 / G5 | 数据如何访问，哪些变化在编译期表达 |
| G6 / G7 | 机器成本与跨执行者共享如何分析 |
| G8 / G9 | 二进制合同与可消费构建如何成立 |
| G10 / G11 | 组件怎样组合，时间和物理约束怎样加入 |
| G12 | 哪些义务由语言承担，哪些仍留给系统 |

### 19.2 四类证据不能压成一格

文档结构与链接只证明可导航和源稿约束；C++ 编译及目标负例检查某些静态/运行命题；性能观察描述特定输入与环境；并发动态检测观察插桩路径。G12 再用审查案例解释这些证据各自能推出什么。

本章没有独立实验执行器，也没有把解释题统计成技术测试数量。原始 G12 的全部 Final Gate 问题保留为下一节，参考答案独立呈现，便于先闭卷推理。

<a id="g12-section-20"></a>

## 20. Final Gate

先闭卷写出条件、机制与反例，再核对下一节；保留原稿问题，不在题干下先给结论。

### 20.1 Object / Lifetime

1. C++、Rust、Zig 在 lifetime proof responsibility 上最大的区别是什么？
2. 为什么 Zig `defer` 和 C++ RAII不是完全同一种 abstraction？
3. 为什么 Rust borrow checker并没有消除 lifetime这个系统问题？

### 20.2 Ownership

1. C++ `unique_ptr`、Rust ownership 与 Zig手动 ownership convention 有什么根本差别？
2. Rust move 和 C++ move为什么不能简单翻译成同一概念？
3. 为什么 Zig resource struct普通复制可能需要特别谨慎？

### 20.3 Borrowing

1. `span<const T>`、`&[T]`、`[]const T` 机器层可能很接近，为什么语言保证却差异巨大？
2. Rust `&mut T` 对 aliasing表达了什么重要思想？

### 20.4 Allocation

1. Zig allocator-as-parameter 的架构价值是什么？
2. 为什么 allocator显式不自动意味着更高性能？
3. C++/Rust隐藏 allocator有什么 API优势和可观测性代价？

### 20.5 Error

1. `expected<T,E>`、`Result<T,E>` 和 Zig error union 的共同系统模型是什么？
2. 为什么 error-as-value 不能自动提供 strong transactional guarantee？

### 20.6 Genericity

1. C++ template、Rust generic、Zig comptime 最终有什么共同机器 trade-off？
2. 为什么更多 compile-time specialization可能伤 I-cache？

### 20.7 Concurrency

1. Rust safe code解决了哪些 C++ concurrency错误？
2. 为什么 Rust仍然需要理解 acquire/release 和 CAS？
3. 为什么 single-writer是三门语言共同的重要架构原则？

### 20.8 ABI

1. 为什么三门语言之间最稳健的长期 ABI仍然通常是 C ABI？
2. Rust的安全 guarantees为什么不能自动穿过 FFI？
3. 为什么 ownership/thread-safety必须写进 ABI contract？

### 20.9 Build

1. Cargo、Zig Build、CMake最大的生态模型差异是什么？
2. 为什么它们底层都仍然可以理解成 artifact graph？

### 20.10 Real-Time

1. 为什么 C++、Rust、Zig都不能自动保证 real-time？
2. 为什么没有 GC不是 sufficient condition？

### 20.11 Architecture

1. 什么时候应该选择 C++？
2. 什么时候 Rust的 static guarantees价值尤其高？
3. 什么类型的问题特别适合 Zig的显式 allocator/C interop/comptime模型？
4. 多语言系统的真正成本是什么？
5. 为什么 language choice 应该是 systems-design procedure 的后半部分，而不是第一步？

<a id="g12-section-21"></a>

## 21. Final Gate · 参考答案与常见误判

答案按上一节分组和题号对应。重点是推理与适用条件，不把关键词复述当作通过。

### 21.1 Object / Lifetime

1. C++ 主要靠对象规则、RAII 和 API 合同；safe Rust 静态检查更多借用关系；Zig 更依赖显式清理与工程约定。都仍有运行环境和低层边界义务。

2. RAII 把清理绑定到拥有类型的析构，defer 常绑定词法控制流。可调用 deinit 的类型也不自动在离域时执行，二者不能按名字等同。

3. 静态检查限制可表达的借用，但架构仍决定谁拥有、多久有效、外部资源何时失效；FFI/unsafe 又增加人工义务。

### 21.2 Ownership

1. unique_ptr 是 C++ 库的独占 owner，类型支持但不检查所有借用；Rust move/borrow 是核心规则；Zig 资源责任由 API 和显式清理约定维持。

2. std::move 不本身转移资源，C++ move 调用后源对象仍存活；Rust 非 Copy 值移动使源不可用，且没有用户 move constructor 协议。

3. 普通复制可能产生两个指向同一资源的值，若两边均清理会重复释放。要定义逻辑转移并限制误用，不能以复制语法推断独占。

### 21.3 Borrowing

1. 相似地址+长度模型不等于相同生命周期/别名静态约束，也不等于正式 ABI 布局兼容。

2. 它表达受规则约束的独占访问；不应再有冲突访问路径。unsafe 与内部可变性需按具体规则审查，不能只背“一个可变引用”。

### 21.4 Allocation

1. 显式传入动态存储能力，让调用者选择策略、预算与寿命；依然要保证 allocator 比使用它的对象有效得更久。

2. 实际策略可能仍是锁竞争严重的通用堆，也可能有很多小分配；显式只改善可见性，不决定机器成本。

3. 拥有容器封装清理、简化调用，但调用点未必看到分配/回收。性能或时限敏感 API 应另说明成本与复用合同。

### 21.5 Error

1. 都可表达成功值或预期错误，并通过控制流传播；取消、panic/terminate 和基础设施灾难仍需独立分类。

2. 错误值不撤销已发生的修改。准备所有会失败的工作后提交，或定义补偿/部分提交，才是状态保证。

### 21.6 Genericity

1. 静态特化可能减少运行时工作，同时增加编译、链接和代码体积；语言机制不同但预算相同。

2. 多个相似专门版本增加代码足迹，可能挤出热点。更易内联也可能更大，需测实际二进制和工作负载。

### 21.7 Concurrency

1. 在 sound 的实现前提下，借用和 Send/Sync 约束排除许多非同步共享、悬挂和非法跨线程访问；不保证所有业务并发结果正确。

2. 原子协议仍要证明发布、读到哪个写入、状态转换和回收；safe 使用 atomics 也能写出逻辑错误或死锁。

3. 减少同一状态竞争写入，使复合不变量与缓存成本更易分析；跨线程读者仍需同步和生命周期合同。

### 21.8 ABI

1. 目标平台 C ABI 可形成更小、明确的共同合同，避免语言私有对象/异常布局；仍须锁定平台和版本，不是普遍稳定魔法。

2. raw pointer 和外部回调没有携带可由编译器验证的完整 owner/线程合同，wrapper 必须人工证明 unsafe 前提。

3. 类型签名不能说明保留多久、谁释放、并发何时合法或何时销毁；漏掉这些会让双方各自“正确”却集成出错。

### 21.9 Build

1. Cargo 更整合包工作流，Zig 提供工具链构建模型，C++ 常由 CMake/生成器/包管理器协作；具体能力与版本相关。

2. 都有源、生成物、库、工具与依赖边。集成度高也不会自动知道未声明的输入或外部环境。

### 21.10 Real-Time

1. 时限取决于工作上界、调度、页面、锁、I/O 和硬件；语言保证只覆盖其中部分表达与安全性。

2. 无 GC 仍可能因 allocator、析构、引用回收、缺页、锁或设备阻塞而迟到。absence of GC 不是完整时间分析。

### 21.11 Architecture

1. 既有 C++/原生库、硬件 SDK、数值生态和接口成本主导，且团队能维持所需证明责任时；不是无条件因性能标签选择。

2. 不可信输入或复杂共享生命周期带来高内存风险，依赖与团队又能支持时；仍需设计资源与业务协议。

3. allocator 策略、C 互操作、静态元数据和小型底层组件很关键时值得评估；不忽略生态、目标支持和维护成本。

4. 多套工具链、包生态、调试、部署、FFI、错误/所有权翻译与升级矩阵；边界收益必须大于这些成本。

5. 先知道资源、失败、并发、二进制与时限约束，才知道哪些语言保证真正有价值。个人语法偏好不能替代需求。

<a id="g12-section-22"></a>

## 22. 参考资料与验证边界

C++ 语义使用 [N4950](https://timsong-cpp.github.io/cppwp/n4950/)及前面章节的定向条款；Rust 比较回查 [Reference 的未定义行为边界](https://doc.rust-lang.org/1.85.0/reference/behavior-considered-undefined.html)、[Send/Sync](https://doc.rust-lang.org/1.85.0/nomicon/send-and-sync.html)、[Ownership](https://doc.rust-lang.org/1.85.0/book/ch04-01-what-is-ownership.html)；Zig 回查 [0.15.2 文档](https://ziglang.org/documentation/0.15.2/)。Rust 2024 是 edition，不是具体编译器版本。本批未执行 Rust/Zig，不声明这些机制已在本机编译验证。编辑去向、审查练习与平台边界见[批次记录](learning/synthesis-revision.md)。

引用版本与证据解释统一见[全书约定](handbook-guide.md)。正文在 G12 结束。可沿 [§12 的审查协议](#g12-section-12)用于新项目；后续是全书一致性和出版视图，不增加新的技术章。
