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
- 初次整理提交 `7869082` 只调整层级、拆分和导航。其后的本轮技术修订保留章节编号与文件名，按复审意见修正事实、补齐条件并验证关键示例；修订不再以原稿逐字保真作为唯一判据。
- 当前仍是工程指导初稿，不是已批准项目规范或已全面验证的工程基线。关键命题的正文修订状态与验证状态分别记录；定向结果不能代表全部代码块通过。

### 定向技术审校

- [修订范围、实际结果与未验证项](review/fm-review-7869082.md)
- [关键命题、适用条件及固定标准依据](review/fm-claims.md)
- [正反例与边界样例](review/fm-verification-samples.md)

示例以 Markdown 为单一维护源。标有 `fm-test` 的 20 个样例分别注明完整运行例、编译语义例、编译失败、UBSan 或受控终止身份；验证脚本直接提取正文／附录，不维护手写 `.cpp` 副本。未标记的历史 `cpp` 块按片段／伪代码阅读，不能假定可独立编译；“错误／反例”上下文不是实现建议。这不免除片段中关键机制的准确性责任，也不表示已穷举全部历史代码块。

```sh
python3 c++/review/verify_fm.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

命令从仓库根目录执行；只用已有编译器。输出写入新建的系统临时目录，脚本会打印证据位置。缺少工具或能力明确记为 SKIP，不计作通过；负例须核对预期诊断／退出码。具体判定、跨平台限制见上述记录。

## C++ Systems Track

以下为已纳入版本管理的 G 系列文档入口。本次保持原文件及现有编号，不补造缺号章节。

| 章节 | 文档 |
| --- | --- |
| G0 | [Native Toolchain](g0-native-toolchain.md) |
| G1 | [Object Model](g1-object-model.md) |

整理时本地另有 G2（RAII & Ownership）、G3（Value & Performance）、G5（Generic Programming & Compile-time）和 G6（Memory）四篇未跟踪文档；它们未纳入本次 FM 文档提交，暂不作为审核版链接入口。

已有 PDF 与相关文件保留在 `pdf_build/`；本次仅整理 Markdown，没有重新构建或修改 PDF。
