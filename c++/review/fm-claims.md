# FM 关键命题与修订状态

基线问题来自用户提供的 `FM-Accuracy-Review-7869082.md`，针对提交 `786908271dfa479c0d4aeb2239b19bd15f90e768`。本表只登记影响工程决策的定向命题，不是全系列逐句标准认证。

规范基线固定为 [C++23 最终草案 N4950](https://timsong-cpp.github.io/cppwp/n4950/)，并显式采用已纳入该稿的 [LWG 3843](https://cplusplus.github.io/LWG/issue3843)。HTML 是草案渲染，不是 ISO 正式出版物；没有无声换成后续标准草案，也没有完成所有 DR 审计。

“已修订”表示本轮正文已落实；“已验证”仅指列出的命题与条件。正式采纳、完整技术验收与提交／推送状态不由这张表自动决定。

| 问题／命题 | 正文与必要条件 | 类型／依据 | 文档修订 | 验证与未覆盖边界 |
| --- | --- | --- | --- | --- |
| A01：out_of_range 需要描述参数 | [FM-1 §23](../fm1-contracts-assertions-ub.md#23-ub-与-runtime-error-的根本区别)；区分定义良好的抛出与 UB，不将其归入 runtime_error 继承分支 | 标准事实；[out.of.range](https://timsong-cpp.github.io/cppwp/n4950/diagnostics#out.of.range) | 已修订 | T01 预期拒绝、T02 运行；不证明异常构造永不分配 |
| A02：分配不等于复制内容 | [FM-5 §7](../fm5-noexcept-move-copy.md#7-copy-与-failure)；明确缓冲区值复制、空对象和所有权不变量 | 示例契约，不是语言强制深复制 | 已修订 | T17 深复制、赋值、空对象、移出状态；未注入分配失败 |
| A03：move 不保证移动构造 | [FM-5 §5 / §10 / §12](../fm5-noexcept-move-copy.md#5-stdmove-不执行移动)；结合 cv/ref、候选集及重载决议，未声明与 deleted 不同 | 标准事实；[forward](https://timsong-cpp.github.io/cppwp/n4950/utility#forward) | 已修订 | T03 复制回退与 const 对象；traits 不证明存在移动构造 |
| A04：open 返回值与 errno 分离 | [FM-0 §41](../fm0-failure-model.md#41-示例文件读取)、[FM-7 §1](../fm7-error-code-system-error.md#1-errno)；先确认 -1，再保存 errno；考虑选项 | POSIX 接口事实；[open(2)](https://man7.org/linux/man-pages/man2/open.2.html) | 已修订 | T20 缺失路径与 O_CREAT；不测试配置事务 |
| B01：unreachable 需要可达性证明 | [FM-1 §34](../fm1-contracts-assertions-ub.md#34-stdunreachable--c23)；固定底层类型的未命名枚举值可存在 | 标准事实；[static.cast/10](https://timsong-cpp.github.io/cppwp/n4950/expr.static.cast#10)、[utility.unreachable](https://timsong-cpp.github.io/cppwp/n4950/utility#utility.unreachable) | 已修订 | T04 正例、T05 隔离 UBSan；不承诺所有 UB 均获诊断 |
| B02：线程隔离覆盖报告失败 | [FM-0 §27](../fm0-failure-model.md#27-thread-boundary)、[FM-8 §2](../fm8-failure-boundaries.md#2-stdthread)、FM-9 清单；join 后读单写者槽，报告后备不得再依赖失败设施 | 标准事实与工程策略；[except.terminate](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)、[propagation](https://timsong-cpp.github.io/cppwp/n4950/propagation) | 已修订 | T11 人为 helper 终止、T12 捕获／观察；未注入线程创建、join 或捕获内部分配失败 |
| B03：monadic 不是任意错误域连接器 | [FM-2 §11](../fm2-value-based-failure.md#11-monadic-composition)；and_then 保留 E，or_else 保留 T，另核查 cv/ref 与构造条件 | 标准事实；[expected.object.monadic](https://timsong-cpp.github.io/cppwp/n4950/expected.object.monadic) | 已修订 | T08 拒绝不同 E、T09 转换正例、T18 四条 pipeline 路径；非所有重载穷举 |
| B04：value() 与 move-only E | [FM-2 §12 / §16](../fm2-value-based-failure.md#12-value-与-operator)；左右值 Mandates 均须核对，复制错误可能再抛异常 | 标准事实；[observers/8～13](https://timsong-cpp.github.io/cppwp/n4950/expected.object.obs)、[LWG 3843](https://cplusplus.github.io/LWG/issue3843) | 已修订 | T06、T07、T10、T16、T19；历史 libstdc++ 14 差异保留，本机结果单列 |
| B05a：RAII 不保证所有终止都展开 | [FM-3 §5](../fm3-exception-semantics.md#5-stack-unwinding)，连带 FM-0/4/5/9；区分实际 unwind 与 terminate | 标准事实；[except.terminate/2](https://timsong-cpp.github.io/cppwp/n4950/except.terminate#2) | 已修订 | 条款与跨章核对；不以某次析构观测声称可移植清理保证 |
| B05b：委托构造体失败的析构 | [FM-3 §6](../fm3-exception-semantics.md#6-未完成构造的对象)、[FM-6 §3](../fm6-construction-destruction-allocation.md#3-partial-construction)、FM-4 §8；目标构造已成功是关键 | 标准事实；[except.ctor/3～4](https://timsong-cpp.github.io/cppwp/n4950/except.ctor) | 已修订 | T13 析构计数；不是所有构造／继承路径矩阵 |
| B06：error_code 参数不等于 noexcept | [FM-7 §14](../fm7-error-code-system-error.md#14-api-双版本模式)；核查具体重载与完整表达式 | 标准事实＋实现观测；[current.path](https://timsong-cpp.github.io/cppwp/n4950/fs.op.current.path)、[fs.err.report](https://timsong-cpp.github.io/cppwp/n4950/fs.err.report) | 已修订 | T15 查询为本库观测，不把未规定 noexcept 的函数必须为 false 作为规范测试 |
| B07：容器保证依具体操作 | [FM-5 §11](../fm5-noexcept-move-copy.md#11-move-only--throwing-move)；CopyInsertable 含 allocator 条件；unspecified 不等于 basic 或 UB | 标准事实；[vector.capacity/4](https://timsong-cpp.github.io/cppwp/n4950/vector.capacity#4)、[vector.modifiers/2](https://timsong-cpp.github.io/cppwp/n4950/vector.modifiers#2) | 已修订 | 定向条款核对；未执行容器异常注入矩阵 |
| B08：noexcept operator 查询整个表达式 | [FM-5 §3](../fm5-noexcept-move-copy.md#3-noexceptexpr)；包括默认实参等求值 | 标准事实；[expr.unary.noexcept](https://timsong-cpp.github.io/cppwp/n4950/expr.unary.noexcept) | 已修订 | T14 编译语义对照，不执行未定义的函数 |
| C01：保持分析维度独立 | FM-0 §29/34/37/47/62、FM-4 §4/5/18、FM-9 §2/9；频率≠严重性，传播≠状态≠终止 | 工程模型与契约审查 | 已修订 | 定点跨章复查；no-fail 提交另查前置条件、返回通道与清理 |
| C02：策略与标准事实分离 | FM-9 §0/9/11；profile 明确采纳后才约束项目 | 工程策略，不是新增语言规则 | 已修订 | 正文／README 边界复查；无项目采纳批准 |
| C03：validated 状态须持续成立 | FM-1 §17；生命周期、可变别名、后续修改与同步仍受约束 | 工程契约条件 | 已修订 | 文字契约复查；未执行借用／并发完整测试 |

## 示例身份与覆盖边界

完整运行例、编译语义例、预期编译失败、UBSan 反例和受控终止分别判定。每个已标记程序的源码、模式和来源可由 Markdown 中稳定 T-ID 定位；生成的临时 cpp 不作为维护入口。

[本轮记录](fm-review-7869082.md)列出测试分母、工具链身份、内容摘要及实际结果。重复定义优先引用主章节；本轮只合并与上述问题直接相关的碎片，不开展全系列大规模改写。
