# C++23 失败语义工程手册

Modern C++ Failure Semantics Handbook · [返回 C++ 总导航](../README.md)

本系列用于长期学习与工程回查：沿着一次操作，分析失败来源、表示与传播、已经改变的状态、剩余保证、恢复权限和验证证据。异常、`expected`、RAII 和 `noexcept` 是完成这些契约的机制，不是十篇彼此独立的语言特性介绍。

当前为 **ACCEPTED — FM Series Review**：`9c48ce0` 的系列级审核通过，无阻断项；两项非阻断精度修正已补齐，当前正文作为长期内容维护基线。接受来自用户对该提交的复审，新修正随本次提交供核对；不代表全部正文技术证明、全平台验证、项目政策采纳或 PDF 出版批准。[接受与修订记录](review/series-revision.md#6-系列接受与精度修正收口)明确区分审核意见、当前字节与历史执行证据。

## 1. 先建立同一张分析图

```text
操作与输入合同
    → 可能结果：成功／领域结果／运行时失败／契约违反
    → 检测、错误表示与传播
    → 状态：改了什么？不变量与所有权还成立吗？
    → 提交是否发生？调用者是否知道？
    → 处置：恢复／补偿／拒绝／升级／终止
    → 证据：命题、判据、实际观察与未验证边界
```

先读[系列阅读约定](series-guide.md)：统一术语、主讲位置、状态分析方法和八项公共审查问题。它是系列索引与分析约定，不是 FM-10，也不另建项目治理体系。

## 2. 首次学习路径

保留 FM-0～FM-9 的文件名与编号。首次按编号阅读，每章先看“阅读入口”与分组目录；历史 § 编号和定位锚点保留，便于旧审校记录继续定位。

| 章节 | 本章承担的问题 | 阅读后应形成的产出 |
| --- | --- | --- |
| [FM-0 · 统一失败模型](fm0-failure-model.md) | 失败来自哪里，谁负责处理，状态和传播为何独立？ | 一份操作失败分析图 |
| [FM-1 · 契约与可信边界](fm1-contracts-assertions-ub.md) | 哪些输入要检查，哪些条件由调用者建立？ | 前置条件、不变量与验证边界 |
| [FM-2 · 值通道与错误类型](fm2-value-based-failure.md) | 返回值携带哪些结果，如何保留错误与所有权？ | 值通道及失败后所有权合同 |
| [FM-3 · 异常传播语义](fm3-exception-semantics.md) | 抛出、展开、捕获与再传播改变了什么？ | 一条异常传播与清理路径 |
| [FM-4 · 资源清理与状态保证](fm4-raii-exception-safety.md) | 失败发生在哪个状态转换，提交前后保证什么？ | 状态转换表与提交论证 |
| [FM-5 · 异常边界与泛型保证](fm5-noexcept-move-copy.md) | `noexcept`、移动、复制和 swap 如何影响组合保证？ | 完整表达式与元素操作审计 |
| [FM-6 · 生命周期与资源失败](fm6-construction-destruction-allocation.md) | 对象何时有效，构造失败和显式完成由谁清理／观察？ | 生命周期及资源责任表 |
| [FM-7 · 系统错误与领域转换](fm7-error-code-system-error.md) | 原生错误如何成为稳定的 API 错误？ | 错误域、cause 与转换边界 |
| [FM-8 · 执行边界与恢复协议](fm8-failure-boundaries.md) | 线程、协程、ABI 和远端失败如何限制影响并被观察？ | 完成状态、恢复权限与重试条件 |
| [FM-9 · 项目失败契约与验证](fm9-project-failure-profile.md) | 如何把前述模型落实成项目可选择的政策与证据？ | 一份待采纳的 API／子系统 profile |

知识依赖不完全等于文件顺序：

```text
FM-0 模型 → FM-1 合同
                  ├→ FM-2 值通道 ───┐
                  └→ FM-3 异常通道 ─┴→ FM-4 状态保证
                                           ├→ FM-5 泛型组合
                                           └→ FM-6 生命周期
FM-2 / FM-3 → FM-7 系统错误转换
FM-4 / FM-6 / FM-7 → FM-8 边界与恢复 → FM-9 项目契约与验证
```

图表示主依赖，不要求遇到每个链接都立即跳读。构造／析构的细节可从 FM-3/FM-4 回查 FM-6；FM-9 的政策模板要在理解机制后选择，而不是倒过来当作语言标准。

## 3. 工程设计路径

已有 C++ 基础、正在设计一个 API 时，可按问题读取：

1. [定义成功、失败和前置条件](fm1-contracts-assertions-ub.md#3-postconditions)，写清受保护状态与失败输入。
2. 比较[值通道](fm2-value-based-failure.md#14-expected-不自动意味着-noexcept)与[异常通道](fm3-exception-semantics.md#15-exception-boundary)，不要从机制反推恢复能力。
3. 用 [FM-4 的状态转换与提交点](fm4-raii-exception-safety.md#7-commit-point)逐步分析 mutation；再核查[泛型表达式](fm5-noexcept-move-copy.md#17-generic-guarantee-composition)和[显式完成／清理](fm6-construction-destruction-allocation.md#13-explicit-close-pattern)。
4. 确定[错误转换](fm7-error-code-system-error.md#11-error-translation-示例)、[完成不确定性](fm8-failure-boundaries.md#17-ambiguous-remote-completion)与[重试预算](fm8-failure-boundaries.md#19-retry-budget)。
5. 填写 [FM-9 API 模板](fm9-project-failure-profile.md#26-public-api-failure-documentation-template)，按[公共审查问题](series-guide.md#review-contract)记录证据与缺口。

## 4. 故障排查与速查

| 当前疑问 | 主讲入口 | 必须一起看的边界 |
| --- | --- | --- |
| 已经 catch，为什么状态仍坏了？ | [FM-0：处理与恢复](fm0-failure-model.md#14-handling-不等于-recovery) | [FM-4：组合状态保证](fm4-raii-exception-safety.md#14-state-guarantee-必须组合分析) |
| `expected` 为什么仍会抛异常？ | [FM-2：值通道与异常](fm2-value-based-failure.md#14-expected-不自动意味着-noexcept) | [FM-5：完整表达式](fm5-noexcept-move-copy.md#3-noexceptexpr) |
| `noexcept`／析构为什么终止？ | [FM-5：传播边界](fm5-noexcept-move-copy.md#1-noexcept-的精确含义) | [FM-3：终止与展开](fm3-exception-semantics.md#5-stack-unwinding) |
| RAII 为什么没有回滚？ | [FM-4：清理与事务](fm4-raii-exception-safety.md#17-raii-不等于-transaction) | [FM-6：显式完成](fm6-construction-destruction-allocation.md#13-explicit-close-pattern) |
| strong guarantee 到底保护哪些状态？ | [FM-4：准备与提交](fm4-raii-exception-safety.md#5-strong-guarantee-的核心模式) | [FM-5：容器操作条件](fm5-noexcept-move-copy.md#11-move-only--throwing-move) |
| 复制测试为什么会误通过？ | [T17 与完整值比较](fm5-noexcept-move-copy.md#7-copy-与-failure) | [已补强的 R01 历史记录](review/fm-review-7869082.md#r01t17-判据补强) |
| 错误码为什么不能直接决定重试？ | [FM-7：事实与策略](fm7-error-code-system-error.md#10-底层错误不能直接决定业务策略) | [FM-8：幂等与完成状态](fm8-failure-boundaries.md#18-idempotency) |
| 断言／`unreachable` 能否处理坏输入？ | [FM-1：机制区别](fm1-contracts-assertions-ub.md#36-三种机制对比) | [FM-1：持续有效的验证结果](fm1-contracts-assertions-ub.md#17-validate-oncetrust-afterwards) |
| 线程或协程的错误由谁观察？ | [FM-8：执行边界](fm8-failure-boundaries.md#2-stdthread) | [promise 报告失败](fm8-failure-boundaries.md#4-stdpromise--stdfuture)与[协程建立阶段](fm8-failure-boundaries.md#7-coroutine-failure) |

## 5. 示例与证据怎么读

Markdown 是示例的单一维护源。标有 `fm-test` 的 T01–T20 才是现有执行器提取的定向样例；未标记 C++ 块是机制／契约片段，可能省略类型、资源策略和外围函数，不能假定可独立编译。反例按邻近警告阅读，不作为生产实现复制。

从仓库根目录运行既有执行器：

```sh
python3 c++/failure-model/review/verify_fm.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

结果写入新系统临时目录。负例需匹配诊断／退出码，SKIP 不算通过，T16 的实现差异不能为全绿而改判据。模式、平台、源码与判据的历史边界见[样例附录](review/fm-verification-samples.md)、[命题台账](review/fm-claims.md)及[历史修订记录](review/fm-review-7869082.md)。

`9c48ce0` 的结构审计、定向代码执行和条款复核保留在[系列修订记录](review/series-revision.md)；本次精度修正仅重做文档与载荷一致性检查，未重跑 C++。历史 JSON 仍绑定原输入，不冒充当前正文的整文件摘要。性能、并发动态检测、全平台验证和 PDF 的未验证边界不变；R01 保持关闭，不外推为全部复制语义已穷举。

## 6. 来源与维护边界

- 初始来源是[研究失败模型会话](https://chatgpt.com/g/g-p-6aa8c2d2c1cc819185b2f45d804a5914-c-23jin-jie/c/6ab766db-76ac-83e8-b59c-868dac31e54b)，原访问可能需要账号权限；`7869082` 保存首次拆分整理。
- `0c7e989` 保存定向事实修订，`be61a1d` 保存 R01 判据补强；目录迁移不改变这些历史证据的发生身份。
- 系列整理前字节由 `3c6dce94144213e77be98508cceb9c2631113ad6` 保存；`9c48ce0c8db2e0f66fd20d43df5f5a1099fb573f` 保存已接受的系列修订。本次仅补准两项措辞及接受标识，不再结构性重写，也不声称与首次导出逐字一致。
- 固定语言依据仍为 C++23 最终草案 N4950 与已注明的 LWG 3843；工程默认策略不冒充标准条款，不无声切换后续标准。
- FM-0 主讲总模型，FM-4 主讲状态保证，FM-9 主讲可裁剪模板；系列阅读约定只负责统一词义和回查，不复制三套定义。
- 本轮不扩 FM-10，不修改 G0–G12、出版系统、已发布 PDF 或历史 JSON；FM PDF **NOT BUILT / NOT VALIDATED**。
