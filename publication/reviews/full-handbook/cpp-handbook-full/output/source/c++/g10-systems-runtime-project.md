# G10 · 系统运行时工程

**版本：** 1.1.1 · Professional Handbook · 全书一致性修订

**状态：** 本轮编辑修订待集中审核；接受历史与冻结候选见[系列状态](README.md#基线与证据状态)。PDF **NOT BUILT / NOT VALIDATED**。

**语言基线与范围：** C++23。Systems Runtime Engineering；前置为 G0～G9，组合运行时协议、安装消费与测量。

**阅读约定：** [Editorial Profile v1.0](editorial-profile.md) · [全书术语、证据与引用](handbook-guide.md)。

[上一章：G9](g09-build-and-native-ecosystem.md) · [全系列导航](README.md) · [下一章：G11](g11-robotics.md)

## 阅读入口

本章把 G0～G9 组合成可执行的工程案例。先读 §1～7 写出不变量与关闭顺序，再运行 §18；性能分析回查 §8、§12～13，安装边界看 §9～10。

原稿的 Complete/Frozen 是历史编辑标记，不沿用为技术验收。编号主题以 `g10-topic-N` 映射到相应主题组，保留技术去向；章节不再逐个复制原有 Part。完整实验与机制片段有可见身份，Gate 答案是普通章节。

- [1. 项目合同：从语言机制到有界数据流](#g10-section-1)
- [2. 不变量与生命周期状态](#g10-section-2)
- [3. 载荷、借用与工作线程私有存储](#g10-section-3)
- [4. 有界队列的状态与线性化点](#g10-section-4)
- [5. 工作线程、Sink 与 happens-before 论证](#g10-section-5)
- [6. 启动、接收与错误模型](#g10-section-6)
- [7. 背压预算与关闭协议](#g10-section-7)
- [8. 指标与时延的测量口径](#g10-section-8)
- [9. 表示演进、PImpl 与 C 边界](#g10-section-9)
- [10. 工程布局与构建配置](#g10-section-10)
- [11. 验证按协议命题组织](#g10-section-11)
- [12. 从性能观察到 profile 假设](#g10-section-12)
- [13. 优化阶梯与配置发布](#g10-section-13)
- [14. 可观察性、异常保证与交付](#g10-section-14)
- [15. 实现阶段与工程记录](#g10-section-15)
- [16. 常见架构误判及其反例](#g10-section-16)
- [17. 验收层次与本章的完成含义](#g10-section-17)
- [18. 完整实验：运行时协议、安装与观察](#g10-section-18)
- [19. 跨组件复核记录](#g10-section-19)
- [20. Final Gate](#g10-section-20)
- [21. Final Gate · 参考答案与常见误判](#g10-section-21)
- [22. 参考资料与验证边界](#g10-section-22)

<a id="g10-section-1"></a>

<a id="g10-topic-0"></a>
<a id="g10-topic-1"></a>
<a id="g10-topic-2"></a>
<a id="g10-topic-3"></a>
<a id="g10-topic-4"></a>
<a id="g10-topic-5"></a>
<a id="g10-topic-6"></a>

## 1. 项目合同：从语言机制到有界数据流

### 1.1 问题、产物与非目标

系统运行时（systems runtime）要回答的不是“队列怎样写”，而是多个正确组件组合后，是否仍保留接收、资源、失败与退出合同。本章沿用 `flow-runtime`：输入经有界队列交给工作线程，结果经第二个有界队列进入单写者 Sink。业务采用可核对的合成载荷，不接 Kafka、HTTP、数据库或 ROS；这样可以把生命周期缺陷与第三方协议故障分开定位。

目标包括并发提交、背压（backpressure）、正常排空（graceful drain）、中止（abort）、错误可观察、资源预算以及可安装的原生库。分布式执行、持久队列、跨崩溃 exactly-once、动态调度插件、协程、NUMA 和实时调度不是本章实现目标。进程内每个已接收任务恰有一个终态，不等于外部业务副作用“恰好一次”。

### 1.2 用三张图约束设计

```text
Caller → InputQueue → Worker × N → OutputQueue → Sink
          bounded       │           bounded       │
                        └─ local scratch           └─ single writer

Runtime owns: configuration, processor, queues, sink, threads
Thread lifetime is nested inside all borrowed dependencies
```

输入所有权、线程拓扑与依赖生命周期是三种关系，不能只画一张类图代替。队列负责交接，Processor 只在任务期间借用数据，Sink 在全部线程结束后向调用者交还只读汇总。读本章时先为每条箭头写明“谁可以写、何时交接、失败后谁负责”，再查看实现。

<a id="g10-section-2"></a>

<a id="g10-topic-7"></a>
<a id="g10-topic-8"></a>
<a id="g10-topic-9"></a>
<a id="g10-topic-10"></a>
<a id="g10-topic-11"></a>
<a id="g10-topic-12"></a>
<a id="g10-topic-13"></a>
<a id="g10-topic-14"></a>
<a id="g10-topic-15"></a>
<a id="g10-topic-16"></a>

## 2. 不变量与生命周期状态

### 2.1 接收是责任转移点

`submit` 返回 Accepted 后，运行时必须最终报告 Succeeded、Failed 或 Cancelled。接收前被拒绝不属于 Cancelled；同一个 ID 不能被两个终态重复计算。仅验证总数相等还不够，重复一项并遗漏另一项也会使总数相等，因此还要核对每个接收 ID 的终态和结果。

队列满足 `0 ≤ depth ≤ capacity`；大型可变载荷沿热路径尽量只有一个逻辑拥有者。依赖对象在访问它的线程退出并被 join 后才能销毁。线程入口是异常边界，但其故障报告路径本身也必须有可执行的失败策略；写了 `noexcept` 不意味着锁、分配或报告不会失败。

### 2.2 不把 close、abort、join 混为一谈

```text
Created → start → Running → close → Closing → join → Stopped
                    └──────── abort → Stopping → join → Stopped
Closing ───────────────────── abort ────┘
```

close 停止接收并保留已接收工作；abort 停止接收、唤醒等待者并允许取消尚未完成的工作；join 是等待和阶段收口，不应暗中替调用者选择 drain 或 abort。close/abort 必须幂等，重复 start 应拒绝。

生命周期操作需要调用方合同。实验规定公开 `start`、`join`、`summary` 和析构由外部 owner 串行执行；公开 `submit`、`close()`、`abort()` 的前置条件是 `start()` 已成功返回。在此之后，close/abort 可与 submit 竞争。终止接收后先等外部提交线程返回，再 join 运行时。析构不能与尚在调用成员函数的外部线程竞争，也不能从内部 worker 自我 join。

实现没有用显式 RuntimeState 检查全部非法调用；成功 start 前公开 close/abort 属于合同外调用，不承诺抛错或特定结果。内部启动失败回滚和析构清理不受这一公开调用前置条件限制，§18 已有部分启动失败与析构测试也不等于测试了所有非法转换。

<a id="g10-section-3"></a>

<a id="g10-topic-17"></a>
<a id="g10-topic-18"></a>
<a id="g10-topic-19"></a>
<a id="g10-topic-20"></a>
<a id="g10-topic-21"></a>
<a id="g10-topic-22"></a>
<a id="g10-topic-23"></a>
<a id="g10-topic-24"></a>
<a id="g10-topic-25"></a>
<a id="g10-topic-26"></a>

## 3. 载荷、借用与工作线程私有存储

### 3.1 拥有者与处理视图分离

原始项目的通用表示是 `InputItem { id, vector<byte> payload }`。普通 vector 移动构造通常转移存储管理状态；带不同分配器的操作则不能无条件推定常数时间。把“控制对象很小”与“载荷很大”分开，有利于跨队列移动，但必须继续检查所有别名和分配器条件，详见 [G3](g03-value-semantics-and-performance.md#g3-section-4)。

Processor 接收 `span<const byte>`，明确只在调用期间读输入，不保存它。worker 持有载荷 owner，返回值是自包含的小结果；异步保留 span 会越过借用期限。裸指针加长度可以表达视图，却不能独自说明拥有、释放和失效，不能直接作为跨线程任务的默认所有权表示。

### 3.2 Scratch 是每个 worker 的预算

解码缓冲、临时记录和解压空间应由工作线程独占，初始化时 reserve，任务间 clear/reuse。clear 销毁元素而不缩减 vector 容量；超过已留容量仍会分配，元素析构也可能承担成本。全局 scratch 加 mutex 把本可并行的处理串行化，也扩大了共享写入范围。

BufferLease 可在测量后替代逐任务 vector，成为 move-only 的池租约。其 pool 必须比所有 lease 活得久，归还路径要线程安全且不抛，池耗尽需背压或明确拒绝。实验先用固定 64 字节自包含载荷：这是可测、总量有界的集成切片，不冒充已完成通用变长缓冲池。

<a id="g10-section-4"></a>

<a id="g10-topic-27"></a>
<a id="g10-topic-28"></a>
<a id="g10-topic-29"></a>
<a id="g10-topic-30"></a>
<a id="g10-topic-31"></a>
<a id="g10-topic-32"></a>
<a id="g10-topic-33"></a>
<a id="g10-topic-34"></a>
<a id="g10-topic-35"></a>
<a id="g10-topic-36"></a>
<a id="g10-topic-37"></a>
<a id="g10-topic-38"></a>

## 4. 有界队列的状态与线性化点

### 4.1 队列不只是容器

输入是多生产者、多消费者；输出是多生产者、单消费者。第一版可复用 mutex/CV 队列。生产者等待“非 Open 或有空间”；消费者等待“非 Open 或非空”。Closed 允许继续 drain；Aborted 结束消费并取消剩余责任。通知只提示重新检查，状态和谓词必须在同一个 mutex 下维护。[N4950 条件变量](https://timsong-cpp.github.io/cppwp/n4950/thread.condition.condvar)

入队提交是接收的线性化点（linearization point）：先确保能保存任务，再登记 Accepted，最后允许消费者观察。若先公开任务、返回前才另写 Accepted，快 worker 可能先完成，而提交者再把终态覆盖回 Accepted。实验把不抛出的接收登记放在队列锁内，和槽位提交组成一个不可被消费者插入的步骤。

### 4.2 值参数、异常与实际内存上界

`push(T value)` 是所有权接收端，但调用前的 move 可能已经改变源；拒绝入队不意味着原调用者还保留载荷。需要“失败仍保留输入”的 API，应另定义成功才 move 的接口或返回未接收的 owner。不要靠返回码猜 moved-from 状态。

deque 支持首删尾增，是通用正确性基线，但条目数有界不等于完全预分配。完整实验改用预分配的 optional 槽位环，限制 T 的移动构造、析构及提交回调不抛。这样队列提交不需要动态扩容。若泛化为会抛的 T，要重新证明半提交恢复；不能删掉约束继续宣称同一保证。处理载荷必须在释放队列锁后进行。

<a id="g10-section-5"></a>

<a id="g10-topic-39"></a>
<a id="g10-topic-40"></a>
<a id="g10-topic-41"></a>
<a id="g10-topic-42"></a>
<a id="g10-topic-43"></a>
<a id="g10-topic-44"></a>
<a id="g10-topic-45"></a>
<a id="g10-topic-46"></a>
<a id="g10-topic-47"></a>
<a id="g10-topic-48"></a>
<a id="g10-topic-49"></a>
<a id="g10-topic-50"></a>

## 5. 工作线程、Sink 与 happens-before 论证

### 5.1 借用依赖要活得更久

worker 借用队列、处理器和只读配置，独占 scratch。线程应在全部依赖初始化后启动；仅把 jthread 声明在最后并不足够，因为析构若先等待 Sink，而输出又必须等 worker 结束才能关闭，仍会死锁。显式 shutdown 顺序优先于“成员反序析构恰好正确”。

stop token 是协作请求，不会自动改变普通 condition_variable 的谓词或唤醒等待。队列 close/abort 负责终止阻塞等待；长时间 CPU 任务应另在安全点检查取消。实验处理固定短载荷，不承诺强制抢占不返回的用户处理函数。

### 5.2 两种同步边与剩余义务

生产者在队列 mutex 下写槽位，解锁与消费者之后的锁定建立发布关系；消费者取得独占任务后再处理。Sink 是 checksum 数组的唯一写者；owner 只在 Sink join 返回后读取。线程完成与成功 join 返回同步，不需要为这份阶段化汇总的每个元素加 atomic。[N4950 join](https://timsong-cpp.github.io/cppwp/n4950/thread.thread.member)

ledger 的跨线程状态用 atomic，槽位内容用 mutex，Sink 数组用单写者与 join。这些机制分工不同。仍须论证无重复 ID、输出生产者全部结束后才关输出、abort 使每个等待条件成立。TSan 无报告不能替代这些协议和进展论证。

<a id="g10-section-6"></a>

<a id="g10-topic-51"></a>
<a id="g10-topic-52"></a>
<a id="g10-topic-53"></a>
<a id="g10-topic-54"></a>
<a id="g10-topic-55"></a>
<a id="g10-topic-56"></a>
<a id="g10-topic-57"></a>
<a id="g10-topic-58"></a>
<a id="g10-topic-59"></a>
<a id="g10-topic-60"></a>
<a id="g10-topic-61"></a>
<a id="g10-topic-62"></a>
<a id="g10-topic-63"></a>
<a id="g10-topic-64"></a>

## 6. 启动、接收与错误模型

### 6.1 分阶段构造与部分启动失败

构造分配状态，不立即暴露 this 给线程；start 在完整对象上启动 Sink 和 workers。创建第 k 个线程失败时，前 k−1 个线程可能已经阻塞在队列上。回滚必须先 abort 队列，再唤醒、join 已创建线程，最后传播启动错误，不能只依赖 `vector<jthread>` 的析构去“自动解决”。

submit 的快速状态检查只是减少无效工作，最终接收判定必须与输入队列状态使用同一提交边界。因此 close 与正在等待的 submit 竞争时，后者可能被拒绝；不能把“调用发生在 close 前”当作已经 Accepted。

### 6.2 区分数据错误、基础设施故障与取消

格式错误属于 item failure，仍沿结果通道送给 Sink；意外处理异常属于 fatal runtime failure，应记录并触发 abort；取消是独立控制结果，不伪装成解析错误。通用实现可用 expected 表达处理结果、exception_ptr 保存首个 fatal 异常。低频错误通道不需要为展示技术而设计无锁发布。

实验用可复制错误枚举和 fatal 标志，以故意抛出的空 Injected 类型测试线程边界；类型没有动态成员，不代表异常运行时不会分配。它没有验证异常文本日志、bad_alloc 或 mutex/OS 同步设施损坏的恢复。noexcept abort 中若同步原语自身失效会终止，不能把灾难性失败解释为已经正常清理。二进制解码的通用版本应显式读取字节和端序，不把字节数组 reinterpret_cast 成未建立生命周期的记录对象。

<a id="g10-section-7"></a>

<a id="g10-topic-65"></a>
<a id="g10-topic-66"></a>
<a id="g10-topic-67"></a>
<a id="g10-topic-68"></a>
<a id="g10-topic-69"></a>
<a id="g10-topic-70"></a>
<a id="g10-topic-71"></a>
<a id="g10-topic-72"></a>
<a id="g10-topic-73"></a>
<a id="g10-topic-74"></a>
<a id="g10-topic-75"></a>

## 7. 背压预算与关闭协议

### 7.1 条目数只是资源预算的一部分

队列容量决定突发吸收、等待时延和占用。变长载荷至少需要最大 payload、worker scratch、输出和调用者阻塞期间持有的载荷预算；无限数量的外部 submitter 即使阻塞在有限队列上，也能持有无限份输入。字节预算队列还需处理单项超过总预算与整数溢出，例如用 `cost <= budget - used`，而非未经检查相加。

实验额外限定 max_items，ledger 和结果存储在启动前分配；它是有限任务批次的运行时，不是无限历史事件数据库。扩大为长期服务时，应把终态流交给有消费确认和保留策略的外部系统，不能任由诊断账本增长。

### 7.2 正常排空与中止是不同提交路径

```text
Graceful:
close input → workers drain → join workers
            → close output → sink drains → join sink → summary

Abort:
reject input → abort both queues → wake test gates / waiters
             → join external submitters → join workers and sink
             → finalize outstanding accepted IDs as cancelled
```

Sink 在 join workers 期间必须继续消费，否则 worker 可能因输出满而永远不能结束。close input 时立刻 close output 会丢失已接收任务的结果。

中止后的取消归档只能在所有执行者停止后进行；否则一个“已取消”任务可能随后又发布成功。实验保存未消费槽位至 join，再把仍 Accepted 的账项标为 Cancelled 并清空槽位。正常排空若留下 Accepted，必须报告 unresolved，不能也归为 Cancelled 来掩盖丢失。运行中的外部副作用不能靠这个账本回滚。

<a id="g10-section-8"></a>

<a id="g10-topic-76"></a>
<a id="g10-topic-77"></a>
<a id="g10-topic-78"></a>
<a id="g10-topic-79"></a>
<a id="g10-topic-80"></a>
<a id="g10-topic-81"></a>
<a id="g10-topic-82"></a>

## 8. 指标与时延的测量口径

### 8.1 先定义计数，再谈速度

硬件线程数只是起点，不是最优 worker 数。独立记录提交尝试、Accepted、Rejected、Succeeded、Failed、Cancelled 和 unresolved；还应观察队列高水位、字节数及各阶段等待。worker 私有计数可在 join 后聚合，实时指标才引入必要的共享访问与缓存行成本。每条记录都打印日志会改变被测系统。

实验同时记录调用者侧成功接收数量和逐 ID 预期，再对照 ledger，避免仅从终态相加得到 accepted 的循环论证。重复 ID 被明确拒绝；该规则只覆盖一个 Runtime 对象生命周期，不处理持久化幂等键。

### 8.2 duration 不等于 wall time 业务时间戳

用 steady_clock 测持续时间。至少区分“开始 submit”“提交实际成功”“worker 开始”“处理结束”“Sink 消费完成”：入队阻塞、排队、处理与端到端不是同一个量。将处理完成减提交时间称作整个系统的 end-to-end，会遗漏输出队列和 Sink。

§18 基准只测启动完成后的首次提交到 join 完成，给出整个有限批次的总时长和吞吐派生值；不伪造尚未采集的逐任务 p50/p99，也不把它当 profile。需要分位数时为每个阶段定义采样点并评估观测开销。

<a id="g10-section-9"></a>

<a id="g10-topic-83"></a>
<a id="g10-topic-84"></a>
<a id="g10-topic-85"></a>
<a id="g10-topic-86"></a>
<a id="g10-topic-87"></a>
<a id="g10-topic-88"></a>
<a id="g10-topic-89"></a>
<a id="g10-topic-90"></a>
<a id="g10-topic-91"></a>
<a id="g10-topic-92"></a>
<a id="g10-topic-93"></a>
<a id="g10-topic-94"></a>
<a id="g10-topic-95"></a>
<a id="g10-topic-96"></a>
<a id="g10-topic-97"></a>
<a id="g10-topic-98"></a>

## 9. 表示演进、PImpl 与 C 边界

### 9.1 先复用，再选择池或区域分配

vector 载荷加私有 scratch 是通用起点；固定载荷环是本章实验切片。测量证明分配占比显著后，再考虑 BufferLease、每 worker 的 monotonic_buffer_resource 或批处理。区域 reset 必须晚于区域内对象析构与所有借用结束；PMR 不会自动延长 resource 生命周期。

Processor 初始用具体类型足够。virtual、template Runtime 或 move_only_function 各有接口、代码体积、间接调用和状态所有权成本。只有确有替换需求时才选择，不把整个调度器模板化当作架构完整性的证据。

### 9.2 运行时身份不随意移动

线程捕获内部状态、队列含 mutex，运行中的 Runtime 默认不复制也不移动。PImpl 降低头文件依赖并隐藏布局，但不把整个 C++ 接口自动变成跨工具链稳定 ABI。公开 C++ 调用仍有标准库、异常和编译器合同，详见 [G8](g08-abi-and-c-interop.md#g8-section-4)。

C 入口用 opaque handle、pointer + size、显式 create/destroy 和状态码。输入仅借用到 submit 返回，包装层复制进运行时拥有的载荷。未来 zero-copy 必须新建租约或释放回调合同，不能悄悄把“调用期借用”改成后台保留。实验提供最小静态库 C 消费者，但没有承诺版本化共享 ABI：配置协商、动态加载、异步回调和旧二进制升级仍需独立验收。

<a id="g10-section-10"></a>

<a id="g10-topic-99"></a>
<a id="g10-topic-100"></a>
<a id="g10-topic-101"></a>
<a id="g10-topic-102"></a>
<a id="g10-topic-103"></a>
<a id="g10-topic-104"></a>
<a id="g10-topic-105"></a>

## 10. 工程布局与构建配置

### 10.1 库目标比项目目录更重要

公开头文件在 include/flow，队列细节在 src；Flow::runtime 表达语言要求、线程依赖和安装头文件。tests 验证协议，apps/bench 观察批次成本，独立 consumer 只通过安装包 find_package。一个 main.cpp 能运行，不代表库已可消费。

开发、ASan/UBSan、TSan 和优化观察应分开构建目录；ASan 与 TSan 不放进同一个二进制。G9 已解释 presets、生成图与安装导出，本章只把它们用于集成，不复制完整构建教程。实验以执行器的显式命令选择配置，未另外声称实现了一组 dev/san/release presets。

### 10.2 安装消费的真实边界

源码树内目标成功可能受未声明 include path 帮助。实验安装后迁移前缀，并暂时隐藏临时生产者源码/构建目录，再创建 C11 与 C++23 两个独立消费者。C 编译单元通过 C 头文件调用，但静态 C++ 实现仍由 C++ 链接器提供运行库；“C 消费者”不等于不用 C++ runtime。

源码、编译器、参数和执行结果需要一起保存。本批不下载依赖，不发布包，不写历史 PDF 或 dist。安装隔离是测试目录的消费检验，不是供应链签名或跨平台认证。

<a id="g10-section-11"></a>

<a id="g10-topic-106"></a>
<a id="g10-topic-107"></a>
<a id="g10-topic-108"></a>
<a id="g10-topic-109"></a>
<a id="g10-topic-110"></a>
<a id="g10-topic-111"></a>
<a id="g10-topic-112"></a>
<a id="g10-topic-113"></a>
<a id="g10-topic-114"></a>
<a id="g10-topic-115"></a>
<a id="g10-topic-116"></a>

## 11. 验证按协议命题组织

### 11.1 正例、阻塞点和错误变体

处理核的字节值、错误标记先有确定预期；集成测试再用多提交者、多 worker 和小容量迫使频繁交接。等待一个线程“应该阻塞了”不能靠随便 sleep：实验读取受锁保护的 waiter 计数，确认输入满、输出满或消费者空等具体前置条件后才 close/abort。等待有截止时间；超时是失败，不是成功取消。

正常 drain 检查 128 个 ID 的终态和完整 checksum，重复 20 次；取消分别覆盖输入生产者阻塞、输出生产者阻塞和空输入消费者等待；还覆盖重复关闭、重复 join、析构兜底、部分启动失败及 worker 异常。错误变体提前关闭 output，在保持可编译的前提下必须被接收账本判据拒绝，而不是把任意 crash 当作发现错误。

### 11.2 动态检测与论证互补

ASan/UBSan 检查本次执行中可检测的内存/未定义行为；TSan 检查插桩执行中的数据竞争。执行器先运行干净启动探针及目标诊断的检测能力对照，再跑本章协议测试。SKIP 与失败分别保存，不用“全部通过”掩盖不支持的工具链。

测试可证明这些输入和调度观察下的断言满足；它不穷举调度，不证明 wait-free，不验证 OS mutex 失败恢复，更不保证有限时间内完成任意用户任务。协议推理、变体拒绝和动态观测是三种不同证据。

<a id="g10-section-12"></a>

<a id="g10-topic-117"></a>
<a id="g10-topic-118"></a>
<a id="g10-topic-119"></a>
<a id="g10-topic-120"></a>
<a id="g10-topic-121"></a>
<a id="g10-topic-122"></a>
<a id="g10-topic-123"></a>
<a id="g10-topic-124"></a>
<a id="g10-topic-125"></a>

## 12. 从性能观察到 profile 假设

### 12.1 分层基准避免归因跳跃

Processor 微基准隔离字节解析；队列基准隔离交接；运行时基准观察整体，三者回答不同问题。worker、载荷大小、容量都影响结果。比较时固定输入、工具链、优化配置和功能判据，重复采样并保留原始值，不挑最好一次。

本批基准覆盖 workers 1/2/4、capacity 1/16、每组合 3 次、每次 2000 个固定载荷。checksum 防止把无工作实现当性能改善。秒数和吞吐没有固定 PASS 门槛；只检查观测格式、工作量和结果一致。该小载荷用例很可能主要体现同步成本，不能外推大图像、磁盘或真实解析器。

### 12.2 测量不是已经做过 profiling

若 allocator 热，先定位分配调用和生命周期；若 queue 热，观察等待、批量与拓扑；若 Processor 热，检查算法、布局和生成代码；若内存带宽饱和，更多 worker 未必有效。必须用实际 profile 支持归因，而非看到某组吞吐低就断言 cache miss 或 false sharing。

本批没有采样调用栈、硬件计数器或生成汇编分析，状态为 PROFILE NOT RUN。后续优化记录应包含假设、基线、一次受控变化、重复测量和 KEEP/REVERT 决定，不把“理论应更快”当证据。

<a id="g10-section-13"></a>

<a id="g10-topic-126"></a>
<a id="g10-topic-127"></a>
<a id="g10-topic-128"></a>
<a id="g10-topic-129"></a>
<a id="g10-topic-130"></a>
<a id="g10-topic-131"></a>
<a id="g10-topic-132"></a>
<a id="g10-topic-133"></a>
<a id="g10-topic-134"></a>
<a id="g10-topic-135"></a>
<a id="g10-topic-136"></a>
<a id="g10-topic-137"></a>
<a id="g10-topic-138"></a>
<a id="g10-topic-139"></a>

## 13. 优化阶梯与配置发布

### 13.1 每项优化都带来新的义务

优先复用存储，再尝试批处理、池、队列分片、AoS/SoA、区域分配，最后才考虑无锁。把 64 项一次交接可减少理想条件下的同步次数，却增加批次等待、部分失败和内存峰值；“通常值得先试”不等于总吞吐一定提高。批次自身的 vector 也可能分配。

按 worker 分出 SPSC 队列，必须重新讨论负载不均、任务顺序与关闭协调；把 AoS 改成 SoA，要保持列长和索引关系，并证明异常时不留下半更新；引入池，要解决耗尽、归还和借用失效。改变表示不能绕过 G1/G2/G7 的原有责任。

### 13.2 配置更新也有生命周期

运行期间不变的配置最好只读共享。需要更新时，先私下构造并验证整个 generation，再发布，旧读者结束后才回收旧版本。`atomic<shared_ptr<const Config>>` 提供一种拥有型发布方法，但引用计数及最后一个引用释放可能落到读路径，且操作不保证 lock-free。

不要让工作线程逐字段读多个独立 atomics 后误认得到一致配置。G11 的控制参数更需要整个 generation 的一致性和读路径时间边界；跨章复用的是发布/回收论证，不是固定容器选择。

<a id="g10-section-14"></a>

<a id="g10-topic-140"></a>
<a id="g10-topic-141"></a>
<a id="g10-topic-142"></a>
<a id="g10-topic-143"></a>
<a id="g10-topic-144"></a>
<a id="g10-topic-145"></a>
<a id="g10-topic-146"></a>
<a id="g10-topic-147"></a>
<a id="g10-topic-148"></a>
<a id="g10-topic-149"></a>
<a id="g10-topic-150"></a>

## 14. 可观察性、异常保证与交付

### 14.1 无全局单例不等于没有共享状态

运行时显式拥有依赖，避免全局 Runtime 指针和随意共享 counters。控制路径日志记录 start/close/abort/fatal/summary；热路径只写有界指标。账本可以帮助解释责任去向，但必须与调用者接收记录独立对照，不能把自洽统计当成端到端结果正确。

通用 deque 入队可能分配并抛异常；提交点必须说明异常发生时队列、参数 owner 和 accepted 状态各自如何。C++ API 可为基础设施故障抛异常、以值表达业务失败；C ABI 则在边界翻译。强保证依赖所有参与操作，不是看到 noexcept swap 就自动成立。

### 14.2 工程完成是多个 Gate 的交集

能安装 Flow::runtime、独立 C++ 消费及 C 头文件调用，是本章完成的可执行学习切片。长生命周期 ABI、所有配置组合、真实生产日志、动态模块和分配失败矩阵未实现，不把它们列成已经通过。

资源汇总在 join 后是不可变视图；运行时观测若要在后台持续读取，必须新增同步和一致性合同。不能把实验的 post-join summary 直接搬到实时监控线程调用。

<a id="g10-section-15"></a>

<a id="g10-topic-151"></a>
<a id="g10-topic-152"></a>
<a id="g10-topic-153"></a>
<a id="g10-topic-154"></a>
<a id="g10-topic-155"></a>
<a id="g10-topic-156"></a>
<a id="g10-topic-157"></a>
<a id="g10-topic-158"></a>
<a id="g10-topic-159"></a>
<a id="g10-topic-160"></a>
<a id="g10-topic-161"></a>
<a id="g10-topic-162"></a>
<a id="g10-topic-163"></a>
<a id="g10-topic-164"></a>
<a id="g10-topic-165"></a>
<a id="g10-topic-166"></a>
<a id="g10-topic-167"></a>
<a id="g10-topic-168"></a>

## 15. 实现阶段与工程记录

### 15.1 阶段是内部工具，不是逐补丁审批

合理实现顺序为安装骨架、单线程 Processor、有界队列、单 worker 全链、多 worker、关闭协议、指标基准和可选 C 边界。每一步都保持前一步的可验证命题，最终作为一个完整能力批次交付。本章实验已经给出能编译、运行和安装消费的整体，而不是让读者自行补齐 close/abort 才能使用。

锁自由队列、hazard pointers、SIMD、定制 malloc、协程和 NUMA 不是禁止知识，而是在没有需求或 profile 前不加入集成基线。先使最小协议可解释，才知道后续复杂性解决什么问题。

### 15.2 记录必须能回到具体源码

架构记录放 ownership/thread/lifecycle 图；不变量记录放 accepted outcome、容量和销毁顺序；性能记录放条件、观察和限制。ADR 只记录有实际替代方案的决策，不为每个小实现动作创建治理负担。

Markdown 中的完整文件是本实验唯一维护源码；执行器提取到新临时目录并记录文件摘要。源稿版本、命令、结果与边界一起构成证据，不拿旧运行的 JSON 为新字节背书。六张跨章审查图在 [G12 §15](g12-cpp-zig-rust.md#g12-section-15)汇总。

<a id="g10-section-16"></a>

<a id="g10-topic-169"></a>
<a id="g10-topic-170"></a>
<a id="g10-topic-171"></a>
<a id="g10-topic-172"></a>
<a id="g10-topic-173"></a>
<a id="g10-topic-174"></a>
<a id="g10-topic-175"></a>
<a id="g10-topic-176"></a>
<a id="g10-topic-177"></a>
<a id="g10-topic-178"></a>
<a id="g10-topic-179"></a>
<a id="g10-topic-180"></a>

## 16. 常见架构误判及其反例

### 16.1 共享与等待常被隐藏在“方便”里

每项都改全局 atomic counter 会造成额外共享写入；到处 shared_ptr 只延长生命周期，不决定写入权限（mutation authority）。裸借用指针进队列可能指向提交者栈；让 worker 拥有共享队列又会使多个析构责任相互冲突。把依赖注入和 owner 图画清楚，比增加智能指针种类更重要。

无界队列只是把过载从等待改成内存失控。处理时持队列锁把计算与交接串行化。过早关闭 output 会使已接收结果无处提交；只 request_stop 不通知 CV 会使等待者永远看不到退出机会。

### 16.2 类型复杂性不能代替生命周期

线程在依赖构造前启动、只靠 destructor 决定排空还是取消、未测量就写 lock-free、把所有组件都变为模板参数，分别扩大了失效窗口、隐式行为、证明负担和构建成本。实验让这些问题显式化，但没有声称一种 API 适用所有生产环境。

<a id="g10-section-17"></a>

<a id="g10-topic-181"></a>
<a id="g10-topic-182"></a>
<a id="g10-topic-183"></a>
<a id="g10-topic-184"></a>
<a id="g10-topic-185"></a>
<a id="g10-topic-186"></a>
<a id="g10-topic-187"></a>
<a id="g10-topic-188"></a>
<a id="g10-topic-189"></a>

## 17. 验收层次与本章的完成含义

### 17.1 不把学习稿完成改写为生产认证

原稿的 correctness、sanitizer、ownership、shutdown、performance、build、package、ABI、explainability 九类 Gate 继续保留。正文完整意味着读者有规格、推理、实现切片和判据；它不代表全部生产功能、平台或 sanitizer 可检测范围已经覆盖。

本章的硬判据是具体功能、终态和资源上界；性能是条件化观察；并发是协议论证加动态证据；公开 C 接口只验证当前消费者。真实项目若要求旧二进制兼容、长时间可用性或强时限，必须补上对应证据，而不是升级章节状态字符串。

### 17.2 收口后的学习方式

先闭卷画 ownership、等待依赖和 drain 图，再运行完整实验；预测提前关闭输出会在哪条断言失败。之后读实际时长数据，提出可被 profile 证伪的假设。只有能解释每个类型、容量、同步和失败边界的理由，才算掌握项目，而不是把测试输出复制到笔记。

<a id="g10-section-18"></a>

## 18. 完整实验：运行时协议、安装与观察

### 18.1 命题、命令与检查边界

G10-R1 以固定载荷、有限 ID 集合实现双队列 runtime。先根据 §2～7 预测 drain、abort 和异常的账本，再运行：

```sh
python3 c++/learning/verify_synthesis.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

命令从仓库根执行，路径可按本机编译器调整。执行器把正文文件提取到新的临时目录，输出其绝对路径和 results.json；记录编译器、标准库宏、参数与每个文件摘要。当前执行路径为 macOS/Clang，其他平台明确 SKIP，不把未运行记为 PASS。

正常程序应输出 `runtime protocols verified`；错误变体提前关输出，必须先编译成功，再以 `invariant=10` 和返回码 10 被拒绝。取消测试实际等待 waiter 计数，不以延迟猜阻塞。20 轮并发测试是同一协议的重复观察，不是 20 个新实验。

独立 C/C++ 消费者要求安装迁移后可运行。C 接口只是当前静态库实验：data 必须指向 64 个可读字节，调用期间有效；ID 为 [0,256) 且单实例内唯一；先成功 start，再 submit/close/join；所有生命周期调用按 owner 合同串行，destroy 前不得还有调用。输出指针必须指向有效可写对象，不与 handle 或彼此重叠。无效非空指针不能由 C 包装层检测。destroy(nullptr) 合法，成功创建的 handle 只销毁一次。本批没有旧共享二进制升级承诺。

### 18.2 完整文件

文件保留为可提取的完整单元，长代码是未来 PDF 续页风险，不用缩小字号或删除实现隐藏。源码中测试 gate 和启动失败参数仅服务确定性反例，不是生产 scheduling API。

<!-- s-lab {"id":"G10-R1","mode":"runtime"} -->

[完整实验 · G10-R1 · include/flow/runtime.hpp]

<!-- s-file {"path":"include/flow/runtime.hpp"} -->
```cpp
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>

namespace flow {
enum class Outcome { unseen, pending, accepted, succeeded, failed, cancelled, rejected };
enum class Submit { accepted, closed, invalid };
enum class Fault { none, malformed, injected };
struct Item {
    std::size_t id{};
    std::array<std::byte, 64> payload{};
    Fault fault{};
};
struct Config {
    std::size_t workers{2}, input_capacity{4}, output_capacity{4}, max_items{256};
    // Laboratory scheduling controls, not a production scheduling API.
    bool hold_workers{}, hold_sink{};
    int fail_start_after{-1};
};
struct QueueStats { std::size_t depth{}, peak{}, push_waiters{}, pop_waiters{}; };
struct Summary {
    std::vector<Outcome> outcomes;
    std::vector<std::uint64_t> checksums;
    std::size_t accepted{}, succeeded{}, failed{}, cancelled{}, unresolved{};
    QueueStats input, output;
    bool fatal{}, protocol_error{};
};
class Runtime {
public:
    explicit Runtime(Config);
    ~Runtime();
    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;
    Runtime(Runtime&&) = delete;
    Runtime& operator=(Runtime&&) = delete;
    void start();
    Submit submit(Item);
    void close();
    void abort() noexcept;
    void join(); // Owner only; first close/abort, then join external submitters.
    Summary summary() const; // Owner only, after join.
    QueueStats input_stats() const;
    QueueStats output_stats() const;
    void release_workers();
    void release_sink();
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
} // namespace flow
```

[完整实验 · G10-R1 · src/queue.hpp]

<!-- s-file {"path":"src/queue.hpp"} -->
```cpp
#pragma once
#include <algorithm>
#include <condition_variable>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <type_traits>
#include <vector>
#include "flow/runtime.hpp"

namespace flow::detail {
template<class T> class Queue {
    static_assert(std::is_nothrow_move_constructible_v<T>);
    static_assert(std::is_nothrow_destructible_v<T>);
    enum class State { open, closed, aborted };
    mutable std::mutex mutex_;
    std::condition_variable readable_, writable_;
    std::vector<std::optional<T>> slots_;
    std::size_t head_{}, tail_{}, size_{}, peak_{}, pushes_{}, pops_{};
    State state_{State::open};
public:
    explicit Queue(std::size_t capacity) : slots_(capacity) {
        if (capacity == 0) throw std::invalid_argument("zero capacity");
    }
    template<class Commit> bool push(T value, Commit commit) {
        static_assert(std::is_nothrow_invocable_v<Commit>);
        std::unique_lock lock{mutex_};
        if (state_ == State::open && size_ == slots_.size()) {
            ++pushes_;
            writable_.wait(lock, [&] {
                return state_ != State::open || size_ < slots_.size();
            });
            --pushes_;
        }
        if (state_ != State::open) return false;
        slots_[tail_].emplace(std::move(value));
        commit(); // No throw; acceptance becomes visible before a consumer can pop.
        tail_ = (tail_ + 1) % slots_.size();
        peak_ = std::max(peak_, ++size_);
        lock.unlock();
        readable_.notify_one();
        return true;
    }
    bool push(T value) { return push(std::move(value), []() noexcept {}); }
    std::optional<T> pop() {
        std::unique_lock lock{mutex_};
        if (state_ == State::open && size_ == 0) {
            ++pops_;
            readable_.wait(lock, [&] { return state_ != State::open || size_ != 0; });
            --pops_;
        }
        if (state_ == State::aborted || size_ == 0) return std::nullopt;
        std::optional<T> value{std::move(*slots_[head_])};
        slots_[head_].reset();
        head_ = (head_ + 1) % slots_.size();
        --size_;
        lock.unlock();
        writable_.notify_one();
        return value;
    }
    void close() {
        std::lock_guard lock{mutex_};
        if (state_ == State::open) state_ = State::closed;
        readable_.notify_all();
        writable_.notify_all();
    }
    void abort() noexcept {
        std::lock_guard lock{mutex_};
        state_ = State::aborted;
        // Keep storage until all users exit; join finalizes outstanding outcomes.
        readable_.notify_all();
        writable_.notify_all();
    }
    void clear_after_join() {
        std::lock_guard lock{mutex_};
        for (auto& slot : slots_) slot.reset();
        size_ = 0;
    }
    QueueStats stats() const {
        std::lock_guard lock{mutex_};
        return {size_, peak_, pushes_, pops_};
    }
};
class Gate {
    std::mutex mutex_;
    std::condition_variable ready_;
    bool open_;
public:
    explicit Gate(bool held) : open_(!held) {}
    void wait() {
        std::unique_lock lock{mutex_};
        ready_.wait(lock, [&] { return open_; });
    }
    void release() noexcept {
        std::lock_guard lock{mutex_};
        open_ = true;
        ready_.notify_all();
    }
};
} // namespace flow::detail
```

[完整实验 · G10-R1 · src/runtime.cpp]

<!-- s-file {"path":"src/runtime.cpp"} -->
```cpp
#include "flow/runtime.hpp"
#include "queue.hpp"
#include <atomic>
#include <optional>
#include <stdexcept>
#include <thread>

namespace flow {
struct Result { std::size_t id; std::uint64_t checksum; bool valid; };
struct Injected {};
struct Runtime::Impl {
    Config config;
    detail::Queue<Item> input;
    detail::Queue<Result> output;
    detail::Gate worker_gate, sink_gate;
    std::unique_ptr<std::atomic<Outcome>[]> ledger;
    std::vector<std::uint64_t> checksums;
    std::atomic<bool> accepting{}, aborted{}, fatal{}, protocol_error{};
    bool started{}, joined{}; // Owner-thread lifecycle, never read by workers.
    std::vector<std::jthread> workers;
    std::jthread sink;

    explicit Impl(Config c)
        : config(c), input(c.input_capacity), output(c.output_capacity),
          worker_gate(c.hold_workers), sink_gate(c.hold_sink),
          ledger(std::make_unique<std::atomic<Outcome>[]>(c.max_items)),
          checksums(c.max_items) {
        if (c.workers == 0 || c.max_items == 0)
            throw std::invalid_argument("zero workers/items");
        for (std::size_t i = 0; i < c.max_items; ++i)
            ledger[i].store(Outcome::unseen);
        workers.reserve(c.workers);
    }
    void finish(std::size_t id, Outcome outcome) noexcept {
        auto expected = Outcome::accepted;
        if (!ledger[id].compare_exchange_strong(expected, outcome))
            protocol_error.store(true);
    }
    void abort() noexcept {
        accepting.store(false);
        aborted.store(true);
        input.abort();
        output.abort();
        worker_gate.release();
        sink_gate.release();
    }
    void worker() noexcept {
        std::optional<std::size_t> current;
        try {
            worker_gate.wait();
            while (auto item = input.pop()) {
                current = item->id;
                if (item->fault == Fault::injected) throw Injected{};
                std::uint64_t sum = 0;
                for (auto b : item->payload) sum += std::to_integer<unsigned>(b);
                Result result{item->id, sum, item->fault != Fault::malformed};
                if (!output.push(result) && !aborted.load())
                    protocol_error.store(true);
                current.reset();
            }
        } catch (...) {
            if (current) finish(*current, Outcome::failed);
            fatal.store(true);
            abort();
        }
    }
    void consume() noexcept {
        try {
            sink_gate.wait();
            while (auto result = output.pop()) {
                checksums[result->id] = result->checksum; // Sink is the only writer.
                finish(result->id, result->valid ? Outcome::succeeded : Outcome::failed);
            }
        } catch (...) {
            fatal.store(true);
            abort();
        }
    }
    void join_threads() {
        for (auto& worker_thread : workers)
            if (worker_thread.joinable()) worker_thread.join();
        output.close(); // Output stays open until every producer has exited.
        if (sink.joinable()) sink.join();
    }
};
Runtime::Runtime(Config c) : impl_(std::make_unique<Impl>(c)) {}
Runtime::~Runtime() {
    // Caller must have stopped all external calls before destroying the object.
    if (impl_->started && !impl_->joined) {
        impl_->abort();
        try { join(); } catch (...) { std::terminate(); }
    }
}
void Runtime::start() {
    auto& p = *impl_;
    if (p.started) throw std::logic_error("already started");
    p.started = true;
    try {
        p.sink = std::jthread([&p] { p.consume(); });
        for (std::size_t i = 0; i < p.config.workers; ++i) {
            if (p.config.fail_start_after == static_cast<int>(i)) throw Injected{};
            p.workers.emplace_back([&p] { p.worker(); });
        }
        p.accepting.store(true);
    } catch (...) {
        p.fatal.store(true);
        p.abort();
        p.join_threads();
        p.joined = true;
        throw;
    }
}
Submit Runtime::submit(Item item) {
    auto& p = *impl_;
    if (!p.accepting.load()) return Submit::closed;
    if (item.id >= p.config.max_items) return Submit::invalid;
    auto expected = Outcome::unseen;
    if (!p.ledger[item.id].compare_exchange_strong(expected, Outcome::pending))
        return Submit::invalid; // IDs are unique for one Runtime lifetime.
    const auto id = item.id;
    if (!p.input.push(std::move(item), [&p, id]() noexcept {
            p.ledger[id].store(Outcome::accepted);
        })) {
        p.ledger[id].store(Outcome::rejected);
        return Submit::closed;
    }
    return Submit::accepted;
}
void Runtime::close() {
    impl_->accepting.store(false);
    impl_->input.close();
}
void Runtime::abort() noexcept { impl_->abort(); }
void Runtime::join() {
    auto& p = *impl_;
    if (!p.started || p.accepting.load()) throw std::logic_error("close/abort first");
    if (p.joined) return;
    p.join_threads();
    if (p.aborted.load()) {
        for (std::size_t i = 0; i < p.config.max_items; ++i) {
            auto expected = Outcome::accepted;
            p.ledger[i].compare_exchange_strong(expected, Outcome::cancelled);
        }
    }
    p.input.clear_after_join();
    p.output.clear_after_join();
    p.joined = true;
}
Summary Runtime::summary() const {
    const auto& p = *impl_;
    if (!p.joined) throw std::logic_error("join first");
    Summary s;
    s.outcomes.resize(p.config.max_items);
    s.checksums = p.checksums;
    for (std::size_t i = 0; i < p.config.max_items; ++i) {
        const auto state = p.ledger[i].load();
        s.outcomes[i] = state;
        if (state == Outcome::succeeded) ++s.succeeded;
        if (state == Outcome::failed) ++s.failed;
        if (state == Outcome::cancelled) ++s.cancelled;
        if (state == Outcome::accepted || state == Outcome::pending) ++s.unresolved;
    }
    s.accepted = s.succeeded + s.failed + s.cancelled + s.unresolved;
    s.input = p.input.stats();
    s.output = p.output.stats();
    s.fatal = p.fatal.load();
    s.protocol_error = p.protocol_error.load();
    return s;
}
QueueStats Runtime::input_stats() const { return impl_->input.stats(); }
QueueStats Runtime::output_stats() const { return impl_->output.stats(); }
void Runtime::release_workers() { impl_->worker_gate.release(); }
void Runtime::release_sink() { impl_->sink_gate.release(); }
} // namespace flow
```

[完整实验 · G10-R1 · tests/runtime_test.cpp]

<!-- s-file {"path":"tests/runtime_test.cpp"} -->
```cpp
#include "flow/runtime.hpp"
#include <atomic>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <thread>
#include <vector>
using namespace std::chrono_literals;
using flow::Outcome;
void require(bool ok, int code) {
    if (!ok) { std::cerr << "invariant=" << code << '\n'; std::exit(code); }
}
template<class Predicate> void await(Predicate predicate, int code) {
    const auto end = std::chrono::steady_clock::now() + 5s;
    while (!predicate()) {
        require(std::chrono::steady_clock::now() < end, code);
        std::this_thread::sleep_for(1ms);
    }
}
flow::Item item(std::size_t id, flow::Fault fault = flow::Fault::none) {
    flow::Item value{};
    value.id = id;
    value.fault = fault;
    value.payload.fill(std::byte(id % 251 + 1));
    return value;
}
void accounting(const flow::Summary& s, std::size_t accepted) {
    require(s.accepted == accepted && s.unresolved == 0 && !s.protocol_error, 10);
    require(accepted == s.succeeded + s.failed + s.cancelled, 11);
}
int main() {
    // Multi-producer input, multiple workers, independent caller-side acceptance.
    for (int repeat = 0; repeat != 20; ++repeat) {
        flow::Runtime runtime{{.workers=3, .input_capacity=2, .output_capacity=1}};
        runtime.start();
        std::atomic<std::size_t> accepted{};
        std::vector<std::jthread> producers;
        for (std::size_t p = 0; p != 4; ++p) {
            producers.emplace_back([&, p] {
                for (std::size_t id = p; id < 128; id += 4) {
                    auto fault = id % 17 == 0 ? flow::Fault::malformed : flow::Fault::none;
                    if (runtime.submit(item(id, fault)) == flow::Submit::accepted)
                        ++accepted;
                }
            });
        }
        for (auto& p : producers) p.join();
        require(runtime.submit(item(0)) == flow::Submit::invalid, 12);
        require(runtime.submit(item(999)) == flow::Submit::invalid, 13);
        runtime.close();
        runtime.close();
        require(runtime.submit(item(200)) == flow::Submit::closed, 14);
        runtime.join();
        runtime.join();
        const auto s = runtime.summary();
        accounting(s, accepted.load());
        require(accepted == 128 && s.succeeded == 120 && s.failed == 8, 15);
        require(s.input.peak <= 2 && s.output.peak <= 1 && !s.fatal, 16);
        for (std::size_t id = 0; id != 128; ++id) {
            const auto want = id % 17 == 0 ? Outcome::failed : Outcome::succeeded;
            require(s.outcomes[id] == want
                && s.checksums[id] == 64 * (id % 251 + 1), 17);
        }
    }
    // Prove producer is blocked before close, then allow graceful draining.
    {
        flow::Runtime r{{.workers=1, .input_capacity=1, .hold_workers=true}};
        r.start();
        require(r.submit(item(0)) == flow::Submit::accepted, 20);
        flow::Submit second{};
        std::jthread p([&] { second = r.submit(item(1)); });
        await([&] { return r.input_stats().push_waiters == 1; }, 21);
        r.close();
        p.join();
        require(second == flow::Submit::closed, 22);
        r.release_workers();
        r.join();
        accounting(r.summary(), 1);
        require(r.summary().outcomes[0] == Outcome::succeeded, 23);
    }
    // Abort while a producer is blocked on full input.
    {
        flow::Runtime r{{.workers=1, .input_capacity=1, .hold_workers=true}};
        r.start();
        require(r.submit(item(0)) == flow::Submit::accepted, 24);
        flow::Submit second{};
        std::jthread p([&] { second = r.submit(item(1)); });
        await([&] { return r.input_stats().push_waiters == 1; }, 25);
        r.abort();
        r.abort();
        p.join();
        r.join();
        const auto s = r.summary();
        accounting(s, 1);
        require(second == flow::Submit::closed && s.cancelled == 1, 26);
        require(s.outcomes[1] == Outcome::rejected, 27);
    }
    // Abort while worker is blocked on full output; sink has not consumed.
    {
        flow::Runtime r{{.workers=1, .output_capacity=1, .hold_sink=true}};
        r.start();
        for (std::size_t i = 0; i != 3; ++i)
            require(r.submit(item(i)) == flow::Submit::accepted, 28);
        await([&] { return r.output_stats().push_waiters == 1; }, 29);
        r.abort();
        r.join();
        accounting(r.summary(), 3);
        require(r.summary().cancelled == 3, 30);
    }
    // Abort wakes empty-input consumers; destruction also wakes/join threads.
    {
        flow::Runtime r{{.workers=2}};
        r.start();
        await([&] { return r.input_stats().pop_waiters == 2; }, 31);
        r.abort();
        r.join();
        accounting(r.summary(), 0);
    }
    { flow::Runtime r{{}}; r.start(); }
    // A fatal processor exception terminates that item and cancels remaining work.
    {
        flow::Runtime r{{.workers=1, .hold_workers=true}};
        r.start();
        require(r.submit(item(0, flow::Fault::injected)) == flow::Submit::accepted, 32);
        require(r.submit(item(1)) == flow::Submit::accepted, 33);
        r.close();
        r.release_workers();
        r.join();
        auto s = r.summary();
        accounting(s, 2);
        require(s.fatal && s.failed == 1 && s.cancelled == 1, 34);
        require(s.outcomes[0] == Outcome::failed, 35);
    }
    // Partial startup failure unwinds already-created threads without deadlock.
    {
        flow::Runtime r{{.workers=2, .fail_start_after=1}};
        bool caught = false;
        try { r.start(); } catch (...) { caught = true; }
        require(caught && r.summary().fatal, 36);
    }
    std::cout << "runtime protocols verified\n";
}
```

[完整实验 · G10-R1 · apps/bench.cpp]

<!-- s-file {"path":"apps/bench.cpp"} -->
```cpp
#include "flow/runtime.hpp"
#include <chrono>
#include <iostream>
int main() {
    constexpr std::size_t count = 2000;
    for (std::size_t workers : {1U, 2U, 4U})
        for (std::size_t capacity : {1U, 16U})
            for (int repeat = 0; repeat != 3; ++repeat) {
                flow::Runtime r{{.workers=workers, .input_capacity=capacity,
                                 .output_capacity=capacity, .max_items=count}};
                r.start(); // Startup excluded; submit through drain is timed.
                const auto begin = std::chrono::steady_clock::now();
                for (std::size_t i = 0; i != count; ++i) {
                    flow::Item value{};
                    value.id = i;
                    value.payload.fill(std::byte{3});
                    if (r.submit(value) != flow::Submit::accepted) return 2;
                }
                r.close();
                r.join();
                const double seconds = std::chrono::duration<double>(
                    std::chrono::steady_clock::now() - begin).count();
                const auto s = r.summary();
                if (s.succeeded != count || s.unresolved || s.protocol_error) return 3;
                std::uint64_t sum = 0;
                for (auto value : s.checksums) sum += value;
                if (sum != count * 192 || seconds <= 0) return 4;
                std::cout << workers << ',' << capacity << ',' << repeat << ','
                          << count << ',' << seconds << ',' << sum << '\n';
            }
}
```

[完整实验 · G10-R1 · include/flow/flow.h]

<!-- s-file {"path":"include/flow/flow.h"} -->
```c
#ifndef FLOW_H
#define FLOW_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct flow_handle flow_handle;
enum flow_status { FLOW_OK, FLOW_CLOSED, FLOW_INVALID, FLOW_ERROR };
int flow_create(flow_handle** out);
void flow_destroy(flow_handle*);
int flow_start(flow_handle*);
int flow_submit(flow_handle*, size_t id, const uint8_t* data, size_t size);
int flow_close(flow_handle*);
int flow_join(flow_handle*, size_t* succeeded, uint64_t* checksum);
#ifdef __cplusplus
}
#endif
#endif
```

[完整实验 · G10-R1 · src/c_api.cpp]

<!-- s-file {"path":"src/c_api.cpp"} -->
```cpp
#include "flow/flow.h"
#include "flow/runtime.hpp"
#include <new>
struct flow_handle { flow::Runtime runtime{flow::Config{}}; bool started{}; };
extern "C" {
int flow_create(flow_handle** out) {
    if (!out) return FLOW_INVALID;
    *out = nullptr;
    try { *out = new flow_handle; return FLOW_OK; } catch (...) { return FLOW_ERROR; }
}
void flow_destroy(flow_handle* h) { delete h; }
int flow_start(flow_handle* h) {
    if (!h || h->started) return FLOW_INVALID;
    try { h->runtime.start(); h->started = true; return FLOW_OK; }
    catch (...) { return FLOW_ERROR; }
}
int flow_submit(flow_handle* h, size_t id, const uint8_t* data, size_t size) {
    if (!h || !h->started || !data || size != 64) return FLOW_INVALID;
    try {
        flow::Item item{};
        item.id = id;
        for (size_t i = 0; i != size; ++i) item.payload[i] = std::byte{data[i]};
        switch (h->runtime.submit(item)) {
        case flow::Submit::accepted: return FLOW_OK;
        case flow::Submit::closed: return FLOW_CLOSED;
        case flow::Submit::invalid: return FLOW_INVALID;
        }
    } catch (...) { return FLOW_ERROR; }
    return FLOW_ERROR;
}
int flow_close(flow_handle* h) {
    if (!h || !h->started) return FLOW_INVALID;
    try { h->runtime.close(); return FLOW_OK; } catch (...) { return FLOW_ERROR; }
}
int flow_join(flow_handle* h, size_t* succeeded, uint64_t* checksum) {
    if (!h || !h->started || !succeeded || !checksum) return FLOW_INVALID;
    try {
        h->runtime.join();
        auto s = h->runtime.summary();
        if (s.fatal || s.protocol_error || s.unresolved) return FLOW_ERROR;
        uint64_t sum = 0;
        for (auto value : s.checksums) sum += value;
        *succeeded = s.succeeded;
        *checksum = sum;
        return FLOW_OK;
    } catch (...) { return FLOW_ERROR; }
}
}
```

[完整实验 · G10-R1 · consumer/main.cpp]

<!-- s-file {"path":"consumer/main.cpp"} -->
```cpp
#include <flow/runtime.hpp>
int main() {
    flow::Runtime runtime{{.workers=1}};
    runtime.start();
    flow::Item item{};
    item.payload.fill(std::byte{3});
    if (runtime.submit(item) != flow::Submit::accepted) return 1;
    runtime.close();
    runtime.join();
    auto s = runtime.summary();
    return s.succeeded == 1 && s.checksums[0] == 192 && !s.unresolved ? 0 : 2;
}
```

[完整实验 · G10-R1 · consumer/main.c]

<!-- s-file {"path":"consumer/main.c"} -->
```c
#include <flow/flow.h>
#include <string.h>
int main(void) {
    flow_handle* h = NULL;
    uint8_t data[64];
    size_t completed = 999;
    uint64_t checksum = 0;
    memset(data, 3, sizeof(data));
    if (flow_create(&h) != FLOW_OK || flow_start(h) != FLOW_OK) return 1;
    if (flow_submit(h, 0, data, sizeof(data)) != FLOW_OK) return 2;
    memset(data, 9, sizeof(data)); /* Input was copied during submit. */
    if (flow_close(h) != FLOW_OK || flow_join(h, &completed, &checksum) != FLOW_OK) return 3;
    flow_destroy(h);
    return completed == 1 && checksum == 192 ? 0 : 4;
}
```

[完整实验 · G10-R1 · CMakeLists.txt]

<!-- s-file {"path":"CMakeLists.txt"} -->
```cmake
cmake_minimum_required(VERSION 3.23)
project(Flow VERSION 1.0.0 LANGUAGES CXX)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
find_package(Threads REQUIRED)
add_library(flow STATIC src/runtime.cpp src/c_api.cpp)
add_library(Flow::runtime ALIAS flow)
set_target_properties(flow PROPERTIES EXPORT_NAME runtime CXX_EXTENSIONS NO)
target_compile_features(flow PUBLIC cxx_std_23)
target_sources(flow PUBLIC FILE_SET HEADERS BASE_DIRS include
    FILES include/flow/runtime.hpp include/flow/flow.h)
target_link_libraries(flow PUBLIC Threads::Threads)
add_executable(runtime_test tests/runtime_test.cpp)
target_link_libraries(runtime_test PRIVATE flow)
add_executable(runtime_bench apps/bench.cpp)
target_link_libraries(runtime_bench PRIVATE flow)
enable_testing()
add_test(NAME protocols COMMAND runtime_test)
set_tests_properties(protocols PROPERTIES TIMEOUT 30)
install(TARGETS flow EXPORT FlowTargets FILE_SET HEADERS
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
configure_package_config_file(cmake/FlowConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/FlowConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Flow)
write_basic_package_version_file(${CMAKE_CURRENT_BINARY_DIR}/FlowConfigVersion.cmake
    VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(EXPORT FlowTargets NAMESPACE Flow::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Flow)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/FlowConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/FlowConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Flow)
```

[完整实验 · G10-R1 · cmake/FlowConfig.cmake.in]

<!-- s-file {"path":"cmake/FlowConfig.cmake.in"} -->
```cmake
@PACKAGE_INIT@
include(CMakeFindDependencyMacro)
find_dependency(Threads)
include("${CMAKE_CURRENT_LIST_DIR}/FlowTargets.cmake")
```

[完整实验 · G10-R1 · consumer/CMakeLists.txt]

<!-- s-file {"path":"consumer/CMakeLists.txt"} -->
```cmake
cmake_minimum_required(VERSION 3.23)
project(FlowConsumer LANGUAGES C CXX)
find_package(Flow 1 CONFIG REQUIRED)
add_executable(cpp_consumer main.cpp)
target_link_libraries(cpp_consumer PRIVATE Flow::runtime)
add_executable(c_consumer main.c)
set_target_properties(c_consumer PROPERTIES C_STANDARD 11 C_STANDARD_REQUIRED YES)
target_link_libraries(c_consumer PRIVATE Flow::runtime)
enable_testing()
add_test(NAME cpp_consumer COMMAND cpp_consumer)
add_test(NAME c_consumer COMMAND c_consumer)
```

### 18.3 阅读实际结果

运行时报告先看逐 ID 终态与 checksum，再看计数；查看 abort 是在什么等待状态触发。Sink 可在 abort 竞争前完成已弹出的结果，这类任务允许保留成功，不要求所有 Accepted 一律取消。测试通过并不证明所有调度，尤其不支持任意阻塞 Processor 的强制终止。

基准每行是 `workers,capacity,repeat,items,seconds,checksum`，共 18 行。时间越小不自动判定“方案更好”：输入小、容量和环境固定，不能推出生产吞吐。原始行保留，派生 items/s 和分布供观察；没有固定性能数值 oracle。

<a id="g10-section-19"></a>

## 19. 跨组件复核记录

### 19.1 将代码与论证逐项连接

| 命题 | 本章机制 | 反例或检查 |
| --- | --- | --- |
| Accepted 有终态 | 锁内提交 ledger，join 后核对 | 提前关输出变体 |
| 输入/输出有界 | 固定槽位环 | peak 不超过 capacity |
| 取消能解除等待 | 两队列 abort 加唤醒 | full input/output 与 empty input |
| 依赖先于线程存活 | 完成启动后运行，显式 join | 析构兜底、部分启动失败 |
| 处理异常不逃线程 | worker catch、fatal、abort | injected fault 后终态 |
| 安装接口可消费 | 导出目标、安装头文件 | 隐藏生产树后的 C/C++ 消费者 |

### 19.2 保留剩余问题

实验不验证无限任务服务、持久队列、真实变长解码、不可撤销副作用、分配失败、OS 同步设施失败、采样 profile 或严格进展保证。当前错误注入是受控处理异常与部分启动失败，不等于所有异常矩阵穷举。学习时应以这些缺口提出后续项目问题，而不是修改记录将它们视为已完成。

<a id="g10-section-20"></a>

## 20. Final Gate

先闭卷写出条件、机制与反例，再核对下一节；保留原稿问题，不在题干下先给结论。

### 20.1 Ownership

1. `InputItem` 从 caller 到 worker 的 ownership怎样变化？
2. 为什么 Processor 参数应该是 `span` 而不是 `vector`？
3. 为什么 queue 中的 raw borrowed pointer 很危险？

### 20.2 Queue

1. 为什么 queue 必须 bounded？
2. full 是 error 还是系统状态？
3. mutex/CV queue为什么是合理 baseline？
4. 为什么不能持 queue lock处理 item？

### 20.3 Worker

1. 为什么每 worker应该有自己的 scratch？
2. 为什么 worker thread必须晚于 dependencies构造、早于 dependencies析构？
3. 为什么 thread entry应该是 exception boundary？

### 20.4 Shutdown

1. `close` 与 `abort` 有什么根本区别？
2. 为什么 close input 后不能立刻 close output？
3. 为什么 output queue要在 workers完全结束之后再关闭？
4. 为什么 abort必须 wake blocked waiters？

### 20.5 Memory

1. 哪些 allocations发生在 hot path？
2. `reserve + clear` 消除了什么？
3. 什么时候值得引入 BufferPool？

### 20.6 Concurrency

1. 哪些 state 真正 shared mutable？
2. 为什么 Sink可以不使用 atomic counters？
3. 哪个 synchronization relation保证 join后 summary可安全读取？

### 20.7 ABI

1. C ABI 为什么使用 opaque handle？
2. 为什么 C submit API采用 pointer + size？
3. 为什么异常不能逃出 C ABI？

### 20.8 Build

1. 为什么 runtime应该成为 installable target？
2. 为什么 external consumer test是 G9 的真正验收？

### 20.9 Performance

1. 应先测 processor还是直接换 lock-free queue？
2. 为什么 batching通常优先于 CAS微优化？
3. 为什么 worker_count 必须测量而不是按 CPU 数猜？
4. queue capacity怎样影响 throughput、latency和memory？

### 20.10 Architecture

1. 如果 profiling显示 output queue contention严重，第一反应应该是什么？

<a id="g10-section-21"></a>

## 21. Final Gate · 参考答案与常见误判

答案按上一节分组和题号对应。重点是推理与适用条件，不把关键词复述当作通过。

### 21.1 Ownership

1. 成功提交时 caller 的任务值进入队列，pop 后由 worker 独占；Processor 只借用，结果再交给输出队列与 Sink。失败的值参数可能已从源移动，不能推定原 owner 未变。

2. span 表达调用期间读取连续范围，不要求 vector 的分配策略，也不接管释放。但它不自动证明 owner 存活，异步保留必须另设计。

3. 队列延长等待而不延长 pointee 生命周期。提交者栈退出、容器扩容或 owner 重置都可能使指针悬挂；有明确外部生命周期协议时才可借用。

### 21.2 Queue

1. 有限内存需要可计算容量，永久生产过快时必须背压、拒绝或按业务降级；无界缓冲只推迟失败。

2. full 是正常过载状态，可阻塞、返回暂时拒绝或触发策略，不一定是程序缺陷。必须写清终止等待条件。

3. 它把复合状态放在一个锁域，谓词、提交点与关闭容易论证；不是说 mutex 永远最快，而是当前目标先需要可验证正确性。

4. 处理时间扩大锁持有范围，阻塞其他 push/pop，可能造成反馈死锁。先交接所有权、解锁，再计算。

### 21.3 Worker

1. 独占 scratch 消除共享写入和锁竞争，并复用容量；仍需预算每线程内存和元素析构成本。

2. 线程可能立即执行，也可能延迟结束；依赖构造完成才启动，停止并 join 后才销毁，不能仅靠碰巧的调度。

3. 逃出线程入口的异常会导致终止。边界应区分 item failure 和 fatal，报告后唤醒退出；报告自身失败仍需明示限制。

### 21.4 Shutdown

1. close 保留已接收工作并 drain；abort 可将未完成责任归为取消。二者都停止新接收，但业务后果不同。

2. 输入关闭后 worker 仍可持有已取出的任务；立刻关输出会拒绝这些结果，留下 Accepted 无终态。

3. join workers 是不再有输出生产者的阶段屏障。Sink 在此期间要持续消费，之后关输出才可结束消费。

4. stop 标志若不改变等待谓词并通知，CV 上的线程可能永远不醒。输入、输出和其他阻塞点都要覆盖。

### 21.5 Memory

1. 通用版本可能有输入 vector、deque 槽、scratch 增长及日志分配；实验固定载荷环提前分配，summary 的复制在 join 后，不属于处理热路径。

2. 已有容量可复用，减少后续扩容；它不保证超过容量时不分配，也不消除元素构造/析构或外部分配。

3. 实际 profile 显示大载荷分配是重要成本时。还要处理池上界、耗尽、lease 归还和 pool 比借用者长寿。

### 21.6 Concurrency

1. 队列状态/槽位、跨线程 ledger、停止与故障标志需要同步；任务和私有 scratch 不共享写；Sink 数据在运行期只有一个 writer。

2. 只有 Sink 修改，owner 等 Sink join 后再读，阶段分离使普通字段合法；运行中直接调用同一 summary 则不是这个合同。

3. 线程完成与对应成功 join 返回 synchronizes-with，再经调用线程顺序到达读取。不是 sleep 足够久或 bool 看起来为 true。

### 21.7 ABI

1. 句柄隐藏 C++ 对象布局和管理方式，让创建/销毁留在实现分配域；但不自动给并发或版本兼容保证。

2. 连续字节无需暴露 vector，extent 明确。仍要定义空指针、有效范围、是否重叠、是否保留，以及大小上界。

3. 本接口规定 C 状态通道，不能要求外部消费者理解 C++ 展开 ABI。包装层捕获并翻译，noexcept 声明本身不会翻译。

### 21.8 Build

1. 目标传播头文件、语言和链接需求，使应用不是依赖源码内部路径。可安装才有真实消费边界。

2. 独立构建可揭露缺失导出、安装依赖和偶然 include path；静态消费者通过仍不证明动态 ABI 升级或所有平台。

### 21.9 Performance

1. 先测整体和分层成本，再定位主导原因。没有 profile 不能认定锁是瓶颈，更不能据此引入回收复杂性。

2. 批处理减少每项交接次数，但增加等待与部分失败语义。应测吞吐、时延和容量，不把理想次数比当实测提速。

3. CPU hint 不包含带宽、task 粒度、调度和 Sink 瓶颈；更多线程可引入竞争，所以使用 worker sweep。

4. 更深缓冲可吸收突发，也扩大排队时延和内存；持续吞吐最终受最慢阶段限制，不能无限加深解决过载。

### 21.10 Architecture

1. 先确认 profile 真把成本定位在输出交接，再尝试结果批量、MPSC 专化、worker 本地聚合或分片 Sink，重新核对顺序与记账；不是立即写 lock-free MPMC。

<a id="g10-section-22"></a>

## 22. 参考资料与验证边界

N4950 的 [条件变量](https://timsong-cpp.github.io/cppwp/n4950/thread.condition.condvar)、[线程 join](https://timsong-cpp.github.io/cppwp/n4950/thread.thread.member)用于同步规则回查；[Clang ASan](https://clang.llvm.org/docs/AddressSanitizer.html)、[UBSan](https://clang.llvm.org/docs/UndefinedBehaviorSanitizer.html) 与 [TSan](https://clang.llvm.org/docs/ThreadSanitizer.html)说明检测机制。实际版本、结果、SKIP、错误变体和平台限制在[批次记录](learning/synthesis-revision.md)与[原始结果](learning/synthesis-results.json)。工具文档不是本机已执行证据。

引用版本与证据解释统一见[全书约定](handbook-guide.md)。下一章 [G11 §1～2](g11-robotics.md#g11-section-1)在资源与关闭模型上加入物理语义和时钟域；运行时协议通过定向测试，不等于新增了实时保证。
