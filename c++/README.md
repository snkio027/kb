# C++ 工程文档

本目录按主题保留完整工程文档。G 系列覆盖语言与系统编程基础；FM 系列聚焦失败语义、状态保证与恢复边界。

## Modern C++ Failure Model

FM-0～FM-9 建议按编号顺序阅读。每篇保留完整正文、示例、表格和检查清单，并提供章内目录与前后章导航。

| 章节 | 完整文档 | 主要内容 |
| --- | --- | --- |
| FM-0 | [统一失败模型](fm0-failure-model.md) | 失败分类、责任、传播、状态保证、恢复边界与失败域 |
| FM-1 | [Contracts / Assertions / UB](fm1-contracts-assertions-ub.md) | 前置条件、不变量、输入校验、断言与未定义行为的边界 |
| FM-2 | [Value-Based Failure](fm2-value-based-failure.md) | `bool`、sentinel、`optional`、`expected` 与结构化错误类型 |
| FM-3 | [Exception Semantics](fm3-exception-semantics.md) | 异常对象、捕获、栈展开、重抛、转换与异常边界 |
| FM-4 | [RAII & Exception Safety](fm4-raii-exception-safety.md) | 资源所有权、异常安全保证、提交点与部分副作用 |
| FM-5 | [noexcept / Move / Copy](fm5-noexcept-move-copy.md) | 条件 `noexcept`、移动与复制、容器迁移和泛型保证 |
| FM-6 | [Construction / Destruction / Allocation](fm6-construction-destruction-allocation.md) | 构造不变量、工厂、分配失败、析构与显式关闭 |
| FM-7 | [error_code / system_error / OS Failure](fm7-error-code-system-error.md) | `errno`、错误身份、错误域、上下文与系统错误转换 |
| FM-8 | [Failure Boundaries](fm8-failure-boundaries.md) | 线程、协程、ABI、RPC、取消、超时、重试与失败隔离 |
| FM-9 | [Project-Level Failure Profile](fm9-project-failure-profile.md) | 项目级策略、API 合同、审查模板、故障注入与最终总图 |

### 来源与整理边界

- 来源：[研究失败模型](https://chatgpt.com/g/g-p-6aa8c2d2c1cc819185b2f45d804a5914-c-23jin-jie/c/6ab766db-76ac-83e8-b59c-868dac31e54b) 会话；访问可能需要原账号权限。
- 整理日期：2026-09-26。
- 采用会话中最后输出的工程文档：FM-0、FM-1，以及 FM-2～FM-9 合集，共三份 Markdown 导出稿；不重复收录前面的讲解和对话过渡语。
- 合集按原章节边界拆分为八篇；末尾的“Modern C++ Failure Model — 最终总图”完整保留在 FM-9。
- 整理只调整标题层级、文档拆分和导航；保留原章节编号、正文措辞、代码、表格、清单及可复用模板。原文中的工程建议不因此成为项目已批准的规范。
- 本次未独立核验 C++ 标准条款，也未编译或运行全部示例；内容接收与排版检查不等于技术审校或实现验证。

## C++ Systems Track

以下为已纳入版本管理的 G 系列文档入口。本次保持原文件及现有编号，不补造缺号章节。

| 章节 | 文档 |
| --- | --- |
| G0 | [Native Toolchain](g0-native-toolchain.md) |
| G1 | [Object Model](g1-object-model.md) |

整理时本地另有 G2（RAII & Ownership）、G3（Value & Performance）、G5（Generic Programming & Compile-time）和 G6（Memory）四篇未跟踪文档；它们未纳入本次 FM 文档提交，暂不作为审核版链接入口。

已有 PDF 与相关文件保留在 `pdf_build/`；本次仅整理 Markdown，没有重新构建或修改 PDF。
