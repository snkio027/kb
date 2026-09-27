# FM 系列阅读约定：术语、状态与证据

本文件与 [FM 总导航](README.md)共同服务 C++23 失败语义工程手册。它确定系列内用语和主讲位置，不取代标准、项目合同或正文中的适用条件。十篇文件名、旧 § 编号与旧锚点保持；新增主题分组用于阅读，不改变历史审校对象身份。

## 1. 一次操作，而不是一个语言特性

分析对象是“在满足前置条件的输入上执行一次操作”。先明确成功后置条件（success postcondition），再问可能在哪里失去成功、如何报告、哪些状态已变化，以及谁有资格恢复。故障注入可以检查某些路径，但“如何证明”不能一律理解为跑一次样例。

```text
契约与输入 → 操作阶段 → 检测与传播
                         │
                         ▼
             状态、不变量、所有权、提交事实
                         │
                         ▼
                恢复／补偿／拒绝／终止
                         │
                         ▼
              命题 → 判据 → 证据 → 边界
```

正常返回不等于业务成功：返回 `unexpected`、`false` 或合法的 absence 都可能是接口规定的正常返回分支。成功与各失败分支须分别写后置条件；违反前置条件也不能当成被调函数承诺处理的普通失败输入。

## 2. 统一词义与主讲位置

### 2.1 原因、状态、表示与传播

| 术语 | 本系列含义 | 主讲位置 |
| --- | --- | --- |
| 失败（failure） | 操作未达到其正常成功后置条件；可能仍正确履行“报告失败”的接口合同 | [FM-0 §2](fm0-failure-model.md#2-failure-不等于-exception) |
| 领域结果（domain outcome） | 合同允许的普通分支；例如 lookup miss，不必归为组件失败 | [FM-0 §5](fm0-failure-model.md#5-domain-outcome) |
| 故障原因（fault） | 导致偏差的原因；不自动等于已观察到的对外失败 | [FM-0 §3](fm0-failure-model.md#3-fault--error--failure) |
| 错误状态（error state） | 系统状态偏离所要求的正确状态；可能被纠正而未向外失效 | 同上 |
| 错误表示（error representation／error object） | 错误码、错误对象等机器可处理信息；对象本身可以完全有效 | [FM-2 §6](fm2-value-based-failure.md#6-error-type-设计)、[FM-7 §3](fm7-error-code-system-error.md#3-stderror_code) |
| 异常（exception） | C++ 异常对象及其非局部传播机制，不是失败原因分类 | [FM-3 §1–2](fm3-exception-semantics.md#1-exception-是非局部控制流) |
| 契约违反（contract violation） | 调用方或实现破坏约定；具体后果须看接口与语言规则，不能一概等同 UB | [FM-1 §6](fm1-contracts-assertions-ub.md#6-runtime-failure-与-contract-violation) |
| 终止（termination） | 不再沿普通调用返回继续执行的处置；不是携带给调用者的错误值 | [FM-1 §33](fm1-contracts-assertions-ub.md#33-stdterminate) |

`error` 在可靠性讨论中可能指 error state，在 API 中又常指 error object。本系列保留这两种语境并写出限定词，不把原有 fault → error state → failure 模型强行改成“error 只能是一个返回值”。`panic` 不是 C++23 的统一机制；提及时须注明语言／运行时和具体行为，不将其默认等同于 `throw` 或 `terminate`。

### 2.2 清理、回滚与恢复

| 术语 | 要回答的不同问题 | 主讲位置 |
| --- | --- | --- |
| 清理（cleanup） | 谁释放／结束已取得资源的责任？清理是否会失败？ | [FM-4 §1–3](fm4-raii-exception-safety.md#1-raii-的真正含义) |
| 回滚（rollback） | 能否恢复到合同指定的先前状态？逆操作自己失败怎么办？ | [FM-4 §10](fm4-raii-exception-safety.md#10-rollback-不是免费操作) |
| 恢复（recovery） | 是否重新进入能继续承担职责的定义良好状态？ | [FM-0 §16](fm0-failure-model.md#16-recovery) |
| 补偿（compensation） | 已发生的不可撤销效果如何用后续动作补救？不等于原操作从未发生 | [FM-4 §15](fm4-raii-exception-safety.md#15-failure-与-partial-side-effects) |
| 重试（retry） | 再执行是否安全、仍有预算且被策略允许？ | [FM-8 §18–19](fm8-failure-boundaries.md#18-idempotency) |
| 恢复边界（recovery boundary） | 哪一层有足够状态、上下文和权限决定下一步？ | [FM-0 §17](fm0-failure-model.md#17-recovery-boundary) |
| 传播边界（failure boundary） | 当前错误形式不能或不应越过哪里？ | [FM-8 §1](fm8-failure-boundaries.md#1-boundary-的本质) |
| 失败域（failure domain） | 哪些任务、资源或组件会受到影响？ | [FM-0 §20](fm0-failure-model.md#20-failure-domain) |

本系列中文“传播边界”对应正文的 failure boundary；“错误域”对应 error category/domain，与失败影响范围不是同一概念。`catch` 是处理动作，既不证明已经恢复，也不保证报告动作成功。

### 2.3 保证不是一条从失败到终止的等级线

状态保证统一回查 [FM-4 §4](fm4-raii-exception-safety.md#4-exception-safety-guarantees)。本系列分别描述三条轴：

| 分析轴 | 可用表述 | 不能推出什么 |
| --- | --- | --- |
| 失败后状态 | strong：约定状态不变；basic：不变量／资源管理成立、值可变；明确部分进度；缺少可依赖保证 | basic 不意味着下一次操作一定成功；部分进度可以是有效状态 |
| 异常传播 | no-throw；`noexcept` 规格；某个完整表达式的查询结果 | 不保证 no-fail、无错误返回、正常完成或完整清理 |
| 处置与可恢复性 | 拒绝、恢复、补偿、升级、重启、终止 | “不可恢复”不是 strong/basic 旁边的状态保证等级 |

这里的 no-fail 指合法前提和约定模型内确实完成操作；终止不算完成。Strong guarantee 必须给出受保护状态及失败通道，不能默认覆盖日志、文件、网络和远端世界。`effects unspecified` 不是自动降级为 basic，也不自动等同 UB。

RAII 将资源清理责任与对象生命周期绑定；适用的是正常退出和确实发生的展开，不承诺所有终止都执行析构。`noexcept` 内部可抛出并捕获；搜索 handler 触及其非抛出边界才触发相应终止规则。参见 [N4950 异常规格](https://timsong-cpp.github.io/cppwp/n4950/except.spec)与[终止及展开限制](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)。

## 3. 沿状态转换审查，而不是只标注“可能 throw”

提交点（commit point）指合同把准备状态接受为新状态的边界；它需要实现依据，不是给某行代码加上名字就存在。主讲及状态表见 [FM-4 §7](fm4-raii-exception-safety.md#7-commit-point)。

每次 mutation 依次记录：

1. **S0：进入前。** 哪些前提、不变量、值和所有权成立？观察范围是什么？
2. **S1：准备中。** 分配、校验、构造、回调、日志可能失败；是否已经碰过受保护状态？
3. **S2：提交后。** 哪些新状态已生效，旧状态由谁清理？返回或通知还能否失败？
4. **调用方观察。** 成功、明确未提交、明确部分提交、已提交但报告失败、完成状态未知分别如何表示？

若准备阶段修改了外部状态，就不能仅凭“临时对象会析构”声称失败前原状不变。若提交后报告失败，也不能让调用者按“失败一定未提交”盲目重试。内存中的 swap、文件操作和数据库提交具有不同观察／持久化边界，不因都称 commit 就共享保证。

**数组填充问题的分析方式。** 对已有的 `fill(buffer)` 类接口，先约定是在给存活元素赋值，还是在原始存储中构造。再说明成功计数、失败后的已提交前缀、当前元素、剩余元素和资源责任；分配、T 的构造／赋值、回调与错误对象构造都要纳入失败集。没有实现与这些前提，仅凭“参数是数组”或“返回错误值”不能断言无异常。此处是合同分析，不新增一个未经验证的填充实现。

## 4. 公共审查合同与章节增量

<a id="review-contract"></a>

全系列共用以下八项问题。各章末尾的 checklist 只承担主题增量；不必让十篇分别复制完整表。

| 项 | 必须写清的内容 | 证据应对准的命题 |
| --- | --- | --- |
| C1 输入与成功 | 合法前提、正常领域结果、成功后置条件 | 输入与结果判断不是同一个模糊 bool |
| C2 失败集与通道 | 来源、检测点、值／异常／终止、错误转换 | 所有声明通道及转换失败都有归属 |
| C3 状态与提交 | 观察范围、每个阶段、不变量、失败后置条件、提交认知 | 失败发生后还能依赖什么，而不只是 catch 到了什么 |
| C4 所有权与清理 | 取得、转移、失败返还／销毁、析构及显式完成 | 无泄漏不等于回滚，cleanup 不等于业务成功 |
| C5 组合前提 | 参数、临时对象、T/E、allocator、回调、返回及报告 | no-throw 与 no-fail 分别成立于哪些条件 |
| C6 恢复与影响范围 | 谁决定恢复／补偿／终止，失败域与并发观察点 | 处理失败的代码自身仍满足合同 |
| C7 重试与控制状态 | 幂等／去重、截止期、预算、取消、完成不确定性 | 请求停止不等于已经停止，超时不证明未提交 |
| C8 验证与限制 | 标准／工程建议／观测、oracle、反例、环境、SKIP、未测项 | 测试能区分承诺与错误实现，结果不被扩大 |

无关项可以说明不适用。局部纯函数不必虚构远端重试政策；项目模板也不强迫所有 API 采用同一错误类型。可填写模板统一放在 [FM-9 §26](fm9-project-failure-profile.md#26-public-api-failure-documentation-template)。

## 5. 技术论述与证据的阅读规则

先看章节用途、主阅读线和失败契约，再读机制／例子、状态影响、边界条件与章末回查。不机械要求每篇都有同样十五个标题，也不增加没有证据的 Rust/Zig 对照。

标准规则继续引用 N4950 固定条款；“建议”“默认”表示工程选择；运行结果只绑定实际工具链和程序；状态表中的预期是推理目标，不伪装成执行输出。无 `fm-test` 标记的 C++ 块不因排版更专业而成为完整实验，危险上下文和省略条件继续有效。

验证分开报告：文档结构／链接、C++ 编译与负例诊断、性能观察、并发动态检测。旧 JSON 不更新为新正文摘要；本轮另比较实际提取源码和判据，新增执行结果另存。20 个样例覆盖若干语言与库边界，不是全部片段、异常注入点或恢复协议的证明。

本轮仅整理 Markdown 与相应审计材料。长代码、表格和流程的分页留给未来出版层，不插入私有 renderer 指令；重要内容不藏进 `<details>`。PDF **NOT BUILT / NOT VALIDATED**，G 系列与已发布制品不受本次 FM 状态改变影响。
