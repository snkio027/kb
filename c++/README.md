# Modern C++ 工程学习手册

这套资料面向已有基础、需要长期学习和工程回查的读者：首次阅读建立模型，后续按问题查精确语义、成本与验证边界。G0～G12 是主线；[FM 失败模型](failure-model/README.md) 是异常、错误与恢复边界的专题。它不是 30 天课程教材，完成度不按天数或页数计算。

[Editorial Profile v1.0](editorial-profile.md) 是全系列唯一编辑基线。[全书阅读约定与跨章索引](handbook-guide.md)统一术语主讲位置、章节交接、证据标签和引用版本，帮助将十三章作为一本手册使用。已接受源稿与本轮编辑修订分别登记，见[基线与证据状态](#基线与证据状态)。

## 从哪里开始

第一次按 **G0 → G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8 → G9** 建立工具、对象、所有权、值、抽象、机器成本、并发、二进制接口与交付的连续模型；再用 **G10 → G11 → G12** 组合成运行时、物理系统和可迁移审查方法。各章目录支持主阅读与按需回查，不要求一口气读完。Final Gate 的参考答案是普通章节，先独立解释，再核对前提与误判。

| 阶段 | 章节与入口 | 这一站要解决的问题 | 动手产出 |
| --- | --- | --- | --- |
| 工具与对象 | [G0 原生工具链](g00-native-toolchain.md) | 编译通过，为什么还不能运行？ | 分离编译，定位缺失定义 |
| 工具与对象 | [G1 对象模型与生命周期](g01-object-model.md) | 地址还在，为什么不能读？ | 区分对象、存储和访问有效期 |
| 资源与值 | [G2 RAII 与所有权](g02-raii-and-ownership.md) | 谁清理资源，失败时怎么办？ | 验证正常、提前返回、异常清理 |
| 资源与值 | [G3 值语义与性能](g03-value-semantics-and-performance.md) | 写了 move，究竟发生了什么？ | 区分复制、移动、消除与借用 |
| 标准库实践 | [G4 STL 与 Ranges](g04-stl-and-ranges.md) | 如何组合拥有者、视图和算法？ | 一个可查询的只读数据批次 |
| 泛型 | [G5 泛型与编译期编程](g05-generics-and-compile-time.md) | 如何把约束变成可复用接口？ | 梳理模板约束与诊断 |
| 机器成本 | [G6 内存与性能](g06-memory-and-performance.md) | 布局和访问模式如何影响成本？ | 测量分配与局部性 |
| 并发 | [G7 并发与内存模型](g07-concurrency-and-memory-model.md) | 共享数据怎样建立可证明的顺序？ | 画出同步关系 |
| 语言边界 | [G8 ABI 与 C 互操作](g08-abi-and-c-interop.md) | 不同二进制怎样共享接口？ | C11 消费者检验 C++ 共享库合同 |
| 工程工具 | [G9 构建与原生生态](g09-build-and-native-ecosystem.md) | 离开源码树后还能消费库吗？ | 安装迁移、独立消费与生成依赖验证 |
| 综合实践 | [G10 系统运行时工程](g10-systems-runtime-project.md) | 组件组合后如何仍然正确？ | 记账、排空、取消、故障与安装消费 |
| 应用深化 | [G11 机器人系统工程](g11-robotics.md) | 时间、物理意义和故障怎样共同约束动作？ | 控制仿真、快照、分配与时序观察 |
| 综合审查 | [G12 统一系统模型](g12-cpp-zig-rust.md) | 哪些复杂性属于语言，哪些属于系统？ | C++ 主线审查；Rust/Zig 辅助辨认责任 |

G5 使用编译诊断、类型断言与符号观察；G6 使用布局、资源请求和基准观察；G7 先论证同步与生命周期，再使用动态检测。G8 以真实 C 消费者检查接口，G9 以安装树和生成图检查交付。G10 组合跨组件协议与条件化性能观察，G11 分离逻辑安全模型和主机时序，G12 用三个推理案例审查证据边界。共同方法是“命题 → 判据 → 证据 → 边界”，不是复制同一种 exact-stdout 实验形态。

本轮 [Cross-series Editorial Sweep](learning/editorial-sweep.md) 只处理全书一致性，不追加 G13，不扩大单章主题。跨章回查优先指向概念主讲处，应用章保留本地前提与必要重述；Final Gate、完整实验与历史证据不因去重而删除。当前形成 Markdown 冻结候选，待集中审核后再进入 G6/G7 PDF Pilot。

## 每次怎么学

1. **闭卷预测**：先回答章首问题，给实验写下预期输出或诊断。
2. **精读主线**：只读本次路线，不被所有进阶分支打断。
3. **运行并解释**：确认不是仅“没崩溃”，而是判据确实覆盖了目标命题。
4. **改变一个条件**：例如改成 const、空输入、缺失定义或延长借用，重新预测。
5. **完成 Gate**：先写答案，再对照参考推理；把错误原因记成一句话，下次从这句复习。

阅读速度由问题与验证负担决定，不将提醒或计划表当作学习证据。

## 按问题回查

| 遇到的问题 | 先看 | 再看 |
| --- | --- | --- |
| undefined symbol、动态库找不到 | [G0 五层诊断](g00-native-toolchain.md#g0-diagnosis) | [G9 工具与加载](g09-build-and-native-ecosystem.md#g9-section-10) |
| 悬挂、扩容后指针失效 | [G1 生命周期](g01-object-model.md#g1-object) | [G4 视图](g04-stl-and-ranges.md#g4-section-3) |
| 清理遗漏、异常后状态不明 | [G2 RAII](g02-raii-and-ownership.md#g2-part-3) | [FM-4 异常安全](failure-model/fm4-raii-exception-safety.md) |
| move 后仍复制、容器迁移成本 | [G3 移动与消除](g03-value-semantics-and-performance.md#g3-section-4) | [FM-5 noexcept / move / copy](failure-model/fm5-noexcept-move-copy.md) |
| expected、线程和 ABI 错误传播 | [FM 导航](failure-model/README.md) | [G7 停机](g07-concurrency-and-memory-model.md#g7-section-9) / [G8 错误输出](g08-abi-and-c-interop.md#g8-section-10) |
| 读过但无法独立推理 | 对应章 Final Gate | [实验与验证说明](learning/README.md) |

## 实验、来源与维护边界

从仓库根目录运行：

```sh
python3 c++/learning/verify_g.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_native.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_synthesis.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/check_docs.py
```

[实验说明](learning/README.md)解释输出位置、负例和 SKIP；[G0～G7 已接受批次](learning/professional-revision.md)、[G8～G9 已接受批次](learning/native-revision.md)与 [G10～G12 已接受批次](learning/synthesis-revision.md)分别记录。Markdown 是正文和完整实验的维护入口。G0～G12 的 C/C++ 代码块有可见身份；机制片段与明确反例不能据此声称全部可独立编译。以前的[学习版记录](learning/revision-notes.md)及 JSON 保留为历史证据，不追写成本批结果。

文件名采用 `gNN-英文主题.md`，编号补零方便排序，正文继续使用 G0～G12。主题名供定位，不作为学习进度或版本号。FM 正文与验证资料整体位于 `failure-model/`，已收口的技术内容不因目录调整重开。

G2～G12 的原始字节先由提交 `2dbaa95` 保存；G0/G1 与 FM 的修改前版本见 `be61a1d`。已有 `pdf_build/` 是历史制品，本批不重新生成、覆盖或宣称与当前学习稿同步。

## 基线与证据状态

| 对象 | 已接受来源或本轮状态 |
| --- | --- |
| Editorial Profile v1.0 | ACTIVE BASELINE；本轮不改 |
| G0～G7 | `496d897` 已接受；[记录](learning/professional-revision.md#6-集中复审与非阻塞收口) |
| G8～G9 | `e91e255` 已接受；[记录](learning/native-revision.md#5-集中复审接受与停止边界) |
| G10～G12 | `bc4c8c9` 已接受；[记录](learning/synthesis-revision.md#6-集中复审接受与停止边界) |
| 全系列源稿里程碑 | `b4728e3`：ACCEPTED — Professional Handbook Source Baseline |
| 本轮全书编辑修订 | G0～G4 v1.2.1 / G5～G12 v1.1.1；冻结候选，待集中审核 |
| 证据身份 | 历史本地执行记录不变，不称为 CI 或本轮重跑 |
| 验证边界 | 跨平台、形式化并发证明、硬实时/物理安全 NOT ESTABLISHED |
| Rust / Zig 可执行验证 | NOT RUN |
| PDF | **NOT BUILT / NOT VALIDATED** |

当前章稿为已接受内容之上的编辑修订，不把旧提交的 ACCEPTED 自动授予新字节。新旧摘要及代码/Gate 对应见[本轮记录](learning/editorial-sweep.md)与[冻结候选清单](learning/editorial-sweep-results.json)。内容候选不包含正式发布或第三方网页归档；集中复审后再确定内容冻结及 G6/G7 Pilot 的启动。
