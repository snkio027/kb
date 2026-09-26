# G10～G12 综合与应用卷 · 修订与验证

日期：2026-09-27。Base：`4d7158a023aee00b54e565a57cda953fac3a5b48`。本批依据“启动”授权完成最后一个 Markdown 正文批次，提交推送后等待集中审核；不自动开始全系列 sweep、PDF Pilot 或正式发布。

§1～5 保留交付时的范围、证据和待审状态；当前接受结论见 §6，不改写已绑定摘要的正文或原始执行记录。

## 1. 交付身份与编辑边界

| 对象 | 本批状态 |
| --- | --- |
| G0～G9 | 已接受源稿保持不变 |
| Editorial Profile | v1.0 不变 |
| G10 / G11 / G12 | 1.1 · Professional Handbook Edition，待集中审核 |
| FM、design、既有执行器和历史 JSON | 不改；结构检查器单独扩至 G0～G12 |
| PDF | **NOT BUILT / NOT VALIDATED** |

G10 是 Systems Runtime Engineering：从需求、不变量与所有权图进入双队列协议、关闭、故障、消费和测量。G11 是 Robotics Systems Engineering：时间、物理意义、控制、安全和集成边界；实验不涉及硬件动作。G12 是 Unified Systems Model：C++ 主线，Rust/Zig 是辨认证明责任的第二层对照，最后形成可复用 review protocol。

三章从碎片化 Part 重组为 22 / 20 / 22 个连续主题章节。原编号主题通过显式锚点映射，保留技术去向；不宣称每个旧编号仍是一节独立正文。重要内容和答案都是普通 Markdown 章节，不依赖 HTML 折叠或 renderer 私有 hack。

## 2. 原稿去向与事实边界

| 原稿范围 | 维护稿位置 | 处置 |
| --- | --- | --- |
| G10 0～38 | §1～4 | 需求、接收责任、表示与队列提交点 |
| G10 39～75 | §5～7 | 线程依赖、错误、预算与 drain/abort |
| G10 76～125 | §8～12 | 指标、表示演进、ABI、构建、测试和测量 |
| G10 126～168 | §13～15 | 优化条件、资源/异常保证、实现阶段与图 |
| G10 169～189 | §16～17 | 反模式与九类完成 Gate，区分项目目标和已执行切片 |
| G11 0～54 | §1～5 | 物理闭环、时间域、部署、内存与数值 |
| G11 55～117 | §6～9 | 快照回收、估计控制、安全与 ROS/QoS |
| G11 118～177 | §10～13 | 大载荷、配置、观测、仿真、时限与输出不变量 |
| G11 178～205 | §14～15 | 项目阶段、反例与语言边界 |
| G12 0～88 | §1～6 | C++ 语义主线与三语言证明责任对照 |
| G12 89～175 | §7～11 | ABI/build、元数据、时限、API 与 FFI |
| G12 176～239 | §12～15 | 系统审查、项目选择、长期维护与六张图 |
| G12 240～278 | §16～17 | 跨章组合与正文封顶 |
| 各章原末尾 Part | Gate、答案、复核与来源 | 30 / 35 / 30 道原问题全部保留，新增逐题推理答案 |

本批明确修正或补足的条件：

- Accepted 在任务对消费者可见前登记；不能在快 worker 完成后再覆盖回 Accepted。取消归档在 join 后进行，正常 drain 的遗漏不冒充 Cancelled。
- count-bound 不等于 byte-bound；外部阻塞提交者和诊断历史也占资源。本实验是固定 64 字节载荷、有限 ID 账本，不伪装成无限任务服务。
- 部分启动失败须先唤醒再 join。stop token 不自动唤醒普通 CV；成员反序析构不能代替 drain 顺序。
- 空异常类型没有动态成员，不代表异常运行时无分配；未做 bad_alloc 或 OS 同步失败注入。
- 双缓冲原子索引不单独解决旧读者存储复用；检查版本后丢弃副本也不能修复已发生的非原子 data race。
- G11 分开测量时间、接收时间、逻辑仿真时间和主机 steady_clock；模型内 0 输出不解释为通用硬件 safe state。
- 分配计数限定当前线程的可替换 C++ allocation functions，不宣称拦截 malloc、其他线程或 page fault。
- G12 区分 `span<const T>` 与 `const span<T>`、C++/Rust/Zig move、正常清理与进程终止；private 成员不是自动 ABI 隐藏。
- ROS 概念回查固定 Jazzy 文档线；Rust 2024 为 edition 而非编译器版本；Zig 固定 0.15.2 参考线，二者本批均未编译运行。

## 3. 可执行模块与判据

正文是 17 个完整源文件的唯一维护入口，执行器只提取到新的临时目录。辅助 sanitizer 探针属于测试设施，其完整源码和摘要另保存在原始证据；TSan 已知竞争对照复用未改的 G7-D3。

| 模块 | 目标命题 | 判据 |
| --- | --- | --- |
| G10-R1 | 跨组件接收、结果和关闭 | 独立调用者数量、逐 ID 终态/校验值、容量、阻塞唤醒 |
| G10-R1 安装消费 | 库在生产树之外可用 | 安装迁移后，C11/C++23 独立 CTest 非空成功 |
| G10-R1 基准 | 指定小载荷的批次成本 | 18 行完整 sweep、校验值、实际秒数；无速度阈值 |
| G11-C1 逻辑 | fault latch/reset/shutdown | 八类注入、有效值和有界幅值/变化 |
| G11-C1 分配与快照 | 观测范围内无分配、generation 一致 | 分配检测对照；中点握手与完整字段关系 |
| G11-C1 时序 | 本机模拟 1 kHz 调度表现 | 1000 行采样及期限标记一致；无硬实时 PASS |
| G12 三个审查案例 | 正确解释证据与缺口 | 人工逻辑推演，不记入编译或动态测试数 |

四个错误变体要求先编译成功，再按精确退出码及目标诊断拒绝：提前关 output 返回 10；接受过期数据返回 21；混合 generation 返回 31；step 内分配返回 30。异常崩溃、超时和编译失败不能替代拒绝证据。变体 PASS 表示判据抓到了受控错误，不表示错误实现可接受。

G10 普通运行每次含 20 轮相同多生产者场景，并覆盖 full input、full output、empty input、重复关闭/join、析构、处理异常和部分启动失败。轮数不计作不同实验。G11 的 snapshot 中点握手确保读者在写者结束前检查过一代；它不是无锁实现。

## 4. 四类证据分别报告

环境为 macOS 26.7 / arm64。Apple Clang 21.0.0（libc++ 220106）与 Homebrew Clang 23.1.2（libc++ 230102），两者 C++23 宏为 202302L；C 接口消费者为 C11。CMake/CTest 4.4.3，Ninja 1.13.2。两套 Clang/libc++ 配置不等于跨 OS 或跨标准库实现验证。

实际主命令：

```sh
python3 c++/learning/verify_synthesis.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s c++/learning -p 'test_*.py'
python3 c++/learning/check_docs.py
git diff --check
```

完整命令、输出、输入与执行器摘要见 [synthesis-results.json](synthesis-results.json)。四类证据不汇总为“全系列全部通过”：

| 类别 | 结果口径 |
| --- | --- |
| 文档结构/链接 | 最终 GFM、本地链接、H1～H3、代码身份和源稿风险；见下方实际数字 |
| C++ 编译/合同 | 两模块 × 两工具链；另四变体 × 两工具链；编译、功能、安装及目标诊断分别记录 |
| 性能观察 | 两套各 18 行运行时 sweep 和 1000 行控制时序；四份 OBSERVED 记录 |
| 并发动态检测 | 两个已知 race 对照 DETECTED；两模块 × 两套 TSan CLEAN_OBSERVED，非协议证明 |

最终执行器：64 条 cpp_validation 阶段 PASS、4 条 ASan/UBSan 目标错误 DETECTED、4 条 ASan/UBSan 模块 CLEAN_OBSERVED；并发类别有 2 条启动探针 PASS、2 条已知竞争 DETECTED、4 条模块 CLEAN_OBSERVED；性能类别 4 条 OBSERVED。无 FAIL/SKIP，execution 为 RECORDED。这些是阶段记录，不是 84 个不同实验；其中 native 功能运行与 sanitizer 重跑也不是新的实验设计。

54 项 Python 执行器单元回归通过（原 37 项、新 17 项）。它们检查提取、路径、变体先编译再运行、诊断/退出、观测完整性和 sanitizer 参数隔离，不是额外 C++ 实验。未重跑 G0～G9 全套正文实验；只重用 G7-D3 作为本批新执行的检测能力对照，旧 JSON 不追写。

最终时序观察中，Apple / Homebrew 两套配置的 1000 周期分别记录 4 / 1 次 deadline miss；release offset 的 p99 分别为 461542 / 250834 ns，max 为 1564209 / 1266209 ns。这里 p99 为排序后第 990 个样本，不是时限上界；不同工具链运行发生在不同时间，不能由此排名编译器。

每批 2000 项运行时 sweep 的总时长分别落在 0.000800667～0.0151794 秒、0.000920208～0.0188999 秒。所有 18 行条件与原始值保留，不挑最好结果。控制核很小且可优化，部分观测执行时间为 0 ns；这不等于零机器成本，也不把该计时作为精确 CPU 周期基准或稳定性证明。

### 4.1 首轮失败与批内修复

首轮已知故障探针得到了目标报告，但 ASan/UBSan 按平台默认 abort 返回信号，而同时设置的检测器 options 还使 TSan 的预期退出码被其他 common option 覆盖。执行器将它们记为 FAIL，并将依赖插桩运行记为 SKIP，没有放宽为“任意非零通过”。

修复为各检测器独立环境、显式 abort_on_error=0、规定退出码；组合 ASan/UBSan 使用一致公共选项。增加参数隔离回归后重跑成功。原始首轮完整失败日志保留为 first_run，最终完整记录为 final_run；中间四轮均 RECORDED，以路径、结果文件摘要、输入身份和汇总登记，不将它们冒充最终字节的运行。

单元回归首轮曾因测试错误预期 G11 有 6 个源文件而失败，实际为 5 个，修正为精确 12+5。编辑期链接检查在接收记录文件尚未生成时报告缺失，最终重新检查。一次额外 py_compile 因系统缓存目录写权限失败，未将它计为 PASS；正常脚本执行与 54 项回归独立完成语法/导入验证。

### 4.2 源稿检查与保护范围

最终结构检查返回 0：36 份 Markdown、817 处本地链接、13 章 Profile 层级检查，无错误。16 个长代码源稿风险中，7 个来自未改的 G0～G9，9 个来自本批完整文件；没有超宽表格、深于 H3 的标题或折叠内容风险。它不是互联网 URL、内容正确性或 PDF 页面验收。

本批对 128 个 Base 已跟踪文件逐个比较：6 个范围内文件修改，其余 122 个不变；另新增执行器、测试、修订记录、原始结果四个文件。G0～G9、Editorial Profile v1.0、FM、全部 design、历史 PDF、既有三个执行器及其历史 JSON 均属于不变集合；check_docs.py 只将 Profile 检查范围扩到 13 章。最终正文、执行器及 12 条正常/变体运行的源文件摘要重新核对匹配，G12 另记录编辑输入摘要，不冒充它有编译执行。

原稿主题锚点 190 / 206 / 279 个完整映射；Gate 问题 30 / 35 / 30 个逐条保持，并逐题提供答案。这些检查证明身份和去向集合完整，不独立证明每段技术论述正确。源码长文件保留为完整可提取单元，未来 PDF 需处理续页身份与分页；本批没有实际渲染页面。

## 5. 未验证事项与停止边界

当前证据仅支持有限集成实验：没有形式化 model checking、无限服务耐久、分配失败或同步设施失效恢复，没有采样 profile/硬件计数器，没有真实 Ctrl-C 新实验。ASan 禁用 leak 检查；未验收符号化栈。子进程执行使用已有超时/进程组 helper，不是安全沙箱或 SIGKILL 后清理保证。

G11 无 ROS/RMW/QoS 实际运行、Eigen 编译、Linux 实时部署、page fault、真实驱动、HIL、物理安全或 hard-real-time 证明。G12 无 Rust/Zig 编译、跨语言 FFI 和性能对比。G10 无版本化共享 ABI/旧消费者升级、动态卸载或生产可用性认证。benchmark 的固定小载荷与控制仿真不能外推真实工作负载。

本批保持待审核，不自行写为 ACCEPTED。G0～G12 的主题到此封顶；跨系列术语/重复清理及 G6/G7 PDF Pilot 留待本批集中复审后另行授权，不生成 PDF、不发布。

## 6. 集中复审接受与停止边界

依据用户本次提供的集中复审意见，审核对象固定为 `bc4c8c9b8a90308131b97b355e2b0be0cbd60d29`，直接基于 `4d7158a023aee00b54e565a57cda953fac3a5b48`。正式登记为：**ACCEPTED — G10–G12「综合与应用卷」Professional Handbook Source Baseline，保留已声明的平台、动态检测、性能与物理系统验证边界。** 本次复审没有阻塞接受的问题，不要求重新修改三章正文。

这是用户复审结论的登记，不是新增的独立技术复审、CI 结果或本机实验重跑。复审意见报告已通过 GitHub 核对提交、正文、执行器、原始 JSON 和变更范围，并指出查询时没有附着 Actions workflow/status；既有结果继续称为本地执行证据。远端材料不用于证明本机工作区状态，本次登记的本地检查另列于下。

| 对象 | 复审后状态 |
| --- | --- |
| Editorial Profile v1.0 | ACCEPTED，不改 |
| G0～G9 Professional Handbook Source Baseline | ACCEPTED，原有边界保持 |
| G10 Systems Runtime Engineering | ACCEPTED |
| G11 Robotics Systems Engineering | ACCEPTED |
| G12 Unified Systems Model | ACCEPTED |
| G10～G12 定向本地证据 | ACCEPTED WITH DECLARED LIMITATIONS |
| 跨平台验证 | NOT ESTABLISHED |
| 形式化并发证明 | NOT ESTABLISHED |
| 硬实时 / 物理安全 | NOT ESTABLISHED |
| Rust / Zig 可执行验证 | NOT RUN |
| PDF | NOT BUILT / NOT VALIDATED |

仅登记两项非阻塞后续提醒，不宣称已修复或已验证：

- **G10 生命周期合同**：未来全系列一致性清理时，应明确公开 `close()/abort()` 在成功 `start()` 后调用的前置条件，或另行实现并验证非法状态转换的拒绝。本次不变更 API、代码或实验，也不因此重开 G10。
- **G12 引用固定策略**：未来统一可重现引用时，为 Rust 官方 Reference 等滚动资料确定引用快照、访问日期或编译器基线；Rust 2024 edition 不等于固定编译器版本。本次不追补未经核验的历史访问事实，不引入 Rust/Zig 执行结论。

16 个长代码分页风险继续作为未来编排输入，不通过裁剪完整可提取程序来消除告警。本次不修改源稿、执行器或原始 JSON，不重新执行 C++ 编译、错误变体、sanitizer、性能和 Python 单元回归，也不生成 PDF。

本次实际运行 `python3 c++/learning/check_docs.py`（36 份 Markdown、819 处本地链接、13 章层级检查，无错误，原 16 个长代码源稿风险不变）及 `git diff --check`（通过）。通过 `git ls-tree` 枚举审核提交的 132 个已跟踪文件，将工作区字节逐一与 `git show <审核提交>:<路径>` 比较：仅系列 README 和本记录变化，其余 130 个文件不变，包括全部 G0～G12 正文、Editorial Profile、FM、design、执行器、原始 JSON 和历史 PDF；无新增文件。以上是本轮登记检查，不追写到历史执行证据。

G0～G12 至此形成完整、已接受的 Professional Handbook Source Baseline，但尚未完成全系列一致性清理后的内容基线冻结，也不表示所有技术命题或目标平台均已验收。

后续顺序保持为全系列 Cross-series Editorial Sweep（术语、重复解释、交叉引用、章节衔接、证据用语）→ 冻结 Markdown 内容基线 → G6/G7 PDF Pilot → 分页、书签、代码续页、表格和引用验收 → 全系列 PDF 出版。本次只登记、检查、提交及推送，随后停止，不自动启动上述后续工作，也不增加 G13。
