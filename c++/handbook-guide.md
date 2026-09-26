# 全书阅读约定与跨章索引

本页是 G0～G12 的阅读辅助，不是 G13，也不另立编辑规范；规则仍以 [Editorial Profile v1.0](editorial-profile.md) 为准。先沿[主阅读路线](README.md#从哪里开始)建立模型，再从本页返回概念主讲处。章节应用可以重述必要前提，但不把每个应用点重新写成定义章。

## 1. 术语回查：同名不等于同一保证

本表统一跨章使用的中文与英文，详细定义和反例在主讲处。代码标识符与 Final Gate 原题保留原样；表内短释不替代适用条件。

| 统一用语 | 主讲处 | 跨章使用边界 |
| --- | --- | --- |
| 翻译单元（translation unit，TU） | [G0 §1](g00-native-toolchain.md#g0-build) | 不等于最终程序或完整构建图 |
| 对象 / 存储 / 生命周期（object / storage / lifetime） | [G1 §1](g01-object-model.md#g1-object) | 存储仍在不证明对象仍可访问 |
| 所有权 / 借用（ownership / borrowing） | [G2 §1](g02-raii-and-ownership.md#g2-section-1) | 清理责任与访问能力分开 |
| RAII（Resource Acquisition Is Initialization） | [G2 §1.4](g02-raii-and-ownership.md#g2-part-3) | 正常清理机制不等于外部事务回滚 |
| 值类别（value category） | [G1 §5](g01-object-model.md#g1-category) | 描述表达式，不描述对象是否已移走 |
| 值语义 / 复制 / 移动（value semantics / copy / move） | [G3 §1](g03-value-semantics-and-performance.md#g3-section-1)、[§4](g03-value-semantics-and-performance.md#g3-section-4) | 转换、重载决议与资源转移分开 |
| 复制消除（copy elision） | [G3 §4](g03-value-semantics-and-performance.md#g3-section-4) | 语言条件与机器返回约定分开 |
| 视图 / 失效（view / invalidation） | [G4 §3](g04-stl-and-ranges.md#g4-section-3) | 不拥有不代表一定安全，也不代表一定零成本 |
| 推导 / 实例化（deduction / instantiation） | [G5 §2](g05-generics-and-compile-time.md#g5-section-2)、[§8](g05-generics-and-compile-time.md#g5-section-8) | 接受某个表达式不等于证明语义合同 |
| 分配 / 构造（allocation / construction） | [G6 §5](g06-memory-and-performance.md#g6-section-5) | 存储策略与对象初始化分开 |
| 结构体数组 / 数组组成的结构体（AoS / SoA） | [G6 §4](g06-memory-and-performance.md#g6-section-4) | 表示选择，不能预设性能赢家 |
| 基准测量 / 性能剖析（benchmarking / profiling） | [G6 §9](g06-memory-and-performance.md#g6-section-9) | 测多快与解释成本在哪里不是同一证据 |
| 数据竞争 / 竞态条件（data race / race condition） | [G7 §2](g07-concurrency-and-memory-model.md#g7-section-2) | 无数据竞争不等于业务时序正确 |
| 先发生关系（happens-before，HB） | [G7 §3](g07-concurrency-and-memory-model.md#g7-section-3) | 语言顺序关系，不是墙钟先后 |
| 写入权限（mutation authority） | [G7 §11](g07-concurrency-and-memory-model.md#g7-section-11) | 拥有或延长寿命不自动授权并发写入 |
| 应用编程接口 / 应用二进制接口（API / ABI） | [G8 §1](g08-abi-and-c-interop.md#g8-section-1) | 源码可重编译不等于旧二进制可用 |
| 分配域（allocation domain） | [G8 §6](g08-abi-and-c-interop.md#g8-section-6) | 创建与释放须遵守兼容的分配合同 |
| 使用要求（usage requirements） | [G9 §2](g09-build-and-native-ecosystem.md#g9-section-2) | 目标传播规则，不是目录级全局选项 |
| 正常排空 / 中止 / 取消（drain / abort / cancellation） | [G10 §7](g10-systems-runtime-project.md#g10-section-7) | 停止接收、等待执行者与终态归档分开 |
| 数据新鲜度 / 数据年龄（freshness / age） | [G11 §2](g11-robotics.md#g11-section-2) | 时间域可比较后，才有年龄计算意义 |
| 证明责任（proof burden） | [G12 §1](g12-cpp-zig-rust.md#g12-section-1) | 编译器、库、系统与部署承担不同义务 |

## 2. 章节之间交接什么

| 阅读段 | 带入的问题 | 交给下一段的模型 |
| --- | --- | --- |
| G0～G1 | 代码怎样变成程序，访问何时有效？ | 工具阶段、对象与存储分层 |
| G2～G3 | 谁管理资源，值传递改变什么？ | 所有权图、失效点与成本假设 |
| G4～G5 | 如何组合集合与可复用抽象？ | 数据访问合同与编译期边界 |
| G6～G7 | 怎样解释机器成本与并发顺序？ | 条件化测量、同步与回收协议 |
| G8～G9 | 边界怎样跨二进制和项目延续？ | 接口合同与可消费安装包 |
| G10～G11 | 组合正确性如何面对时间和物理约束？ | 接收责任、关闭协议与时限边界 |
| G12 | 哪些证明仍由系统承担？ | 可带到新项目的审查协议 |

重复出现的例子按职责区分：[G6 的 shared_ptr 集合](g06-memory-and-performance.md#g6-section-17)关注表示与机器成本，[G7 的共享可变状态](g07-concurrency-and-memory-model.md#g7-section-20)关注写入与同步，[G12 的案例](g12-cpp-zig-rust.md#g12-section-18)审查证据能否支持结论。它们不是三个并行的所有权定义。Gate 答案中的必要重述、反例前提及局部安全边界保留，不能仅因重复而删除。

## 3. 怎样读证据标签

先看命题和判据，再看状态；执行阶段数、不同实验数、工具链数和重复轮数分别统计。[实验入口](learning/README.md)给出命令，历史记录保存当时的原始标签，本页不重写 JSON 枚举。

| 用语 | 支持的结论 | 不支持的推论 |
| --- | --- | --- |
| 标准保证 / 实现约定 / 工程建议 | 分别依赖语言条款、平台或项目合同 | 不能互换为“本机已验证” |
| PASS | 已执行的具体判据满足 | 整章正确、跨平台或生产批准 |
| DETECTED | 指定错误在受控执行中被目标诊断捕获 | 任意崩溃、超时都算成功检测 |
| CLEAN_OBSERVED | 所列插桩路径未观察到目标报告 | 无缺陷、无数据竞争或形式化证明 |
| OBSERVED | 给定输入、选项和环境的观察 | 固定性能常量或硬实时时限 |
| SKIP / NOT RUN | 环境不支持或本批未执行，按记录区分 | 通过或没有问题 |
| NOT VALIDATED / NOT ESTABLISHED | 验收未完成或相应结论尚未建立 | 由其他局部成功自动补齐 |
| FAIL / INCOMPLETE | 判据不满足或所需记录未齐，原因另列 | 用正常阶段掩盖失败或缺项 |
| RECORDED | 执行器要求的记录已收集 | 所有系统性质都已证明 |
| ACCEPTED | 指定提交与范围获复审接受 | 新编辑字节、全部平台或 PDF 自动获批 |

结构/本地链接、C++ 编译与目标诊断、性能观察、并发动态检测仍分四类。ASan/UBSan 是定向动态检查，不能因位于 `cpp_validation` 分类就称为静态证明；符号表、汇编与布局观察也不是端到端性能结果。人工协议推理必须列假设，与形式化模型检查和实测分开。

本轮只改编辑与引用：历史整篇 Markdown 摘要不会匹配新稿；完整实验文件与代码块的字节保持情况另见[一致性检查记录](learning/editorial-sweep.md)。代码未变允许准确定位旧证据所测源码，但不等于在新日期重跑，更不验证新增的文字合同。

## 4. 参考资料的版本与访问身份

引用分三层记录：语言/文档版本线、实际读取的页面身份、实际执行的工具链。版本线和访问日期不是不可变网页归档；Markdown 内容冻结也不等于冻结第三方网站。下列策略用于本书回查，不把尚未重读的资料登记为今天已核验。

| 资料组 | 本书引用线 | 本轮处理与边界 |
| --- | --- | --- |
| C++ | C++23 / N4950 条款链接 | 延续既有固定草案；不改称最终 ISO 文本 |
| Rust | 1.85.0 随附文档；2024 edition | 本轮读四个固定版本页面；未运行 rustc |
| Zig | 0.15.2 文档 | G8 与 G1/G12 对齐；未运行 Zig |
| CMake | 4.4 文档线 | 实测 4.4.3 见历史证据；最低 3.28 不作全矩阵承诺 |
| ROS 2 / ros2_control / rmw | Jazzy 文档或分支 | 分支可更新，不冒充 commit 快照或本机部署 |
| Clang / Apple / Itanium ABI | 正文所链官方资料 | 滚动说明或平台约定；工具身份看各次执行记录 |
| Eigen / Conan / vcpkg | nightly / 2.x / manifest 文档 | 保留范围回查身份，未新增执行或版本兼容验证 |

本轮实际读取日期为 **2026-09-27** 的固定页面：

- [Rust 1.85.0：未定义行为边界](https://doc.rust-lang.org/1.85.0/reference/behavior-considered-undefined.html)。
- [Rust 1.85.0：类型布局](https://doc.rust-lang.org/1.85.0/reference/type-layout.html#the-c-representation)。
- [Rust 1.85.0：所有权](https://doc.rust-lang.org/1.85.0/book/ch04-01-what-is-ownership.html)。
- [Rust 1.85.0：Send / Sync](https://doc.rust-lang.org/1.85.0/nomicon/send-and-sync.html)。
- [Zig 0.15.2：C 互操作](https://ziglang.org/documentation/0.15.2/#C)。

选择 Rust 1.85.0 是固定比较资料，不是推荐升级或声称最新版本，也没有把历史比较改写为该编译器的运行结果。unsafe 细则可能演进；本书只使用已列的概念边界，不由几句概括建立完整 Rust 别名模型。页面 URL、HTTP 结果与读取字节 SHA-256 记入[本轮检查结果](learning/editorial-sweep-results.json)；未归档网页正文，摘要不能替代离线原件。

其他外部链接仅在清单中标记既有版本线与本轮未重查，不混入本地链接检查的通过数。后续技术变更若依赖其最新内容，须重新读取并登记身份；不把滚动 URL 的今天内容追写成旧实验依据。

## 5. 冻结与出版的边界

已接受源稿位于 `b4728e3`；本轮编辑修订生成新的 Markdown 冻结候选，以[外置摘要清单](learning/editorial-sweep-results.json)识别，不把最终摘要写回被摘要文件。候选等待集中复审；接受记录可以独立更新，不借此改动实验源代码。

完整实验继续按文件提取。长代码、ASCII 图与表格的源稿风险交给未来 renderer 处理续页、身份、字号和书签，不裁剪成伪代码，也不写私有分页指令。本轮 **PDF NOT BUILT / NOT VALIDATED**，不启动 G6/G7 Pilot 或全系列出版。
