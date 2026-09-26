# G0～G7 Professional 批次修订与验证

日期：2026-09-27。Base：`60c5562f964717ba224d5e7f6f7bbcfe519a37ed`。§1～5 保留提交 `496d8973c113795340111053ddbc9ef2aaeec92d` 的交付记录；后续集中复审及收口见 §6。不授予全系列技术基线资格。

## 1. 编辑结果与范围

| 对象 | 本批状态 |
| --- | --- |
| [Editorial Profile](../editorial-profile.md) | v1.0，全系列单一编辑规则入口 |
| G0～G4 | Professional presentation refresh，1.2 呈现修订稿 |
| G5～G7 | Professional Handbook Edition，1.1 待审核编辑稿 |
| G8～G12、FM 与历史证据 | 本批不改动 |
| PDF | **NOT BUILT / NOT VALIDATED** |

G0～G4 按主题归组，保留旧定位锚点，提升完整答案为普通章节，增加人类可读代码身份；不增加实验，不更改既有实验源码、oracle 和技术覆盖。G4 的五列表格改为四组带字段名的记录，保留各单元格的对应关系。G0/G1 的主阅读章节编号继续沿用。

G5～G7 保留原稿理论主题，合并碎片化说明与单词型代码框，区分类型/表达式、静态/运行时、观察/保证。补齐完整实验、命题边界和 Final Gate 参考答案。更新的技术条件集中在原有问题：转发绑定选择、constexpr 丢弃分支、显式实例化覆盖范围、PMR 生命周期、SC 总序边界、CV 唤醒协议、CAS/ABA 表示、线程依赖销毁和快照可变别名。

## 2. 原稿主题去向

下面编号是 Base 原稿定位号，不是新目录号。新稿保留 G5～G7 的 `gN-topic-K` 锚点，G2～G4 保留 `gN-part-K` 历史锚点；目录改用主题标题与独立 section 锚点。

| 原稿 | 新稿中的主题去向 |
| --- | --- |
| G5 0～19 | 模板实体、三种推导模式、引用折叠、转发与消费接口 |
| G5 20～41 | 类模板/布局、Concepts、常量求值、静态特化与动态边界 |
| G5 42～60 | 编译/显式实例化、薄模板核心、泛型预算、代码生成、跨语言与审查 |
| G5 61～64 | 统一模型、术语、原有 Gate 全部分组、工程原则；65 的过渡并入导航 |
| G6 0～27 | 成本模型、布局、缓存/局部性、AoS/SoA/AoSoA、冷热与阶段性表示 |
| G6 28～72 | 分配/arena/pool/PMR、页表/TLB/缺页、分支/SIMD/分派、一致性/伪共享 |
| G6 73～95 | 指标、测量/profile/trace、优化证据、九层审查、跨语言、术语 |
| G6 96～104 | 原有八组 Gate、参考答案、工程原则；统一对象审查例保留 |
| G7 0～45 | 数据竞争、HB、内存序、锁/CV、CAS、ABA、回收与进展保证 |
| G7 46～80 | 队列拓扑/槽位协议、取消/停机、线程池/背压、单写者/分片/快照 |
| G7 81～105 及原 Part XII～XVIII | 七类关系图、十二层审查、反模式、35 题 Gate 与逐题答案、G0～G7 统一审查；历史 Complete/Frozen 和回补 G4 的过时流程说明改为当前边界 |

新增实验共 11 个：G5-C1～C5 五个编译/符号模块；G6-M1～M3 三个观察模块；G7-D1～D3 三个并发模块。不是把既有每个片段都变为完整程序；未纳入提取标记的片段不声称已编译。

## 3. 实际验证与结果口径

本批执行记录汇入 [professional-results.json](professional-results.json)。下列类别独立解释，执行器自身的单元测试不计为 C++ 实验。

环境：macOS 26.7 / arm64；Apple Clang 21.0.0（libc++ 220106）与 Homebrew Clang 23.1.2（libc++ 230102），两者 `__cplusplus=202302L`。不把两套 libc++ 工具链写成跨标准库覆盖。

| 证据类别 | 实际结果与边界 |
| --- | --- |
| 文档结构/链接 | 34 份 Markdown、661 处本地链接；8 章层级/代码身份检查无错误。5 个长代码风险保留，不能据此声明 PDF 分页通过 |
| C++ 编译/负例诊断 | G0～G4 的 12 个非 ASan 实验 × 2 工具链完成，另 2 个既有错误变体 × 2 被运行判据拒绝。G5 的 5 个模块 × 2 完成类型断言、目标诊断及链接检查；2 份 nm 输出单列观察 |
| 性能观察 | G6 的 3 个模块 × 2 完成；84 条 AoS/SoA 计时记录、两份布局、两份资源请求记录和两份汇编。无固定性能胜者判据。3 项可选 sysctl 查询因 Operation not permitted 记 SKIP |
| 并发动态检测 | G7-D1/D2 × 2 工具链 × 普通/TSan 两模式 = 8 次 CLEAN_OBSERVED；G7-D3 × 2 得到 data race 及退出码 66，记 DETECTED。不是并发协议完备证明 |

G0～G4 另有 G1-L2 ASan 阳性对照 × 2，均出现目标 heap-use-after-free 诊断与退出码 86。它属于动态内存检测，不记为并发检测。G0～G4 总计仍为 13 个正文实验 × 2 加 2 个既有变体 × 2，共 30 条结果；未增加实验。

执行器单元回归共 23 项（原有 13 项＋新增 10 项），检查提取、负例判据、TSan 退出/诊断约束、观察字段完整性与基准数据遗漏/重复/错误；其中既有真实子进程超时回归仍保留。这不是 23 个额外 C++ 实验。

实际命令（从仓库根目录）：

```sh
python3 c++/learning/check_docs.py
python3 -m unittest discover -s c++/learning -p 'test_*.py'
python3 c++/learning/verify_g.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
git diff --check
```

结构检查、单元回归、旧实验执行器与差异检查返回 0。新执行器返回 1 / INCOMPLETE：原因仅为上述三项可选硬件查询 SKIP，最终编译、实验不变量或 TSan 判据没有 FAIL。缓存行和页大小因此不作为本机已知事实。CPU sampling profile 与硬件计数器为 NOT RUN，而非 PASS。

首轮 G7-D3 虽报告目标 data race，却以 SIGABRT 返回 -6，按原判据判 FAIL。随后显式配置 `abort_on_error=0`，仍要求目标诊断和退出码 66，重跑完成；没有放宽判据。首轮两条原始失败记录与最终记录一并保存，以免把修复过程抹成从未失败。

来源/范围核对采用 Base 的 Git 对象与当前字节比较：G0～G4 的 665 个全部围栏代码块、13 个实验的元数据及提取源码、全部旧显式锚点均保持；G5/G6/G7 分别保留 65/105/106 个编号主题的对应锚点（G5 原稿 65 是过渡说明，已并入导航）。主题集合核对只证明去向可追踪，不能单独证明技术正确性。

Base 的 119 个已跟踪文件中，11 个属于本批修改，另外 108 个逐字节不变；包括 G8～G12、FM 正文和证据、历史 PDF、design 目录及其出版脚本/配置。新文件另行列入提交。保护检查与 G0～G4 内容对照的实际脚本及结果保存在 JSON 中；不以工作区看起来干净代替字节核对。

## 4. 出版源稿风险与人工复核

本批检查 H1～H3、链接/锚点、可见代码身份、重要 HTML 折叠、孤立标题、分隔线、宽表和长代码。G0～G7 不再用 details 承载答案，不含 H4 正文和装饰性水平线。源稿风险检测不是实际分页检测。

保留的长代码是有身份的完整实验：G2-L1、G4-L1、G6-M2、G6-M3 和 G7-D2。为保留完整提取源码，本批不按假想纸张强行切断它们；未来 renderer 必须支持可读续页、持续显示实验/文件身份，且不能裁切。宽表已按字段记录布局收口；最终风险行号由结构检查原始结果提供。

人工复核针对原稿主题去向、G0～G4 代码与判据身份、Gate 问答对应及关键同步/测量边界。未做 PDF 渲染、书签、页面视觉检查、可访问性认证或打印测试。出版源稿质量不等于 PDF 质量通过。

## 5. 保留事项与停止边界

- 编译/运行仅代表记录中的 macOS arm64、两套 Clang/libc++ 配置；不宣称 GCC、libstdc++、Windows/MSVC 或全部 C++23 库实现验证。
- G6 基准只有列求和工作负载；未采集 CPU sampling profile、硬件事件或真实业务端到端指标，不把生成汇编当作这些证据。
- G7 的有限 stress、shutdown 检查和 TSan 对照不替代协议证明；未做模型检查、分配失败注入、无锁 MPMC 回收验证或调度公平性证明。
- G0～G4 的 ASan 阳性对照单列为动态内存检测，不混入 G7 的并发检测。历史 FM 记录和历史学习版 JSON 保持不变。
- Markdown 本地链接检查不验证网络 URL。Zig/Rust 对照未编译。PDF 未构建、未验收，正式发布未执行。

完成检查后提交、推送，等待本批集中审核；不自动启动 G8～G9 或 G10～G12。

## 6. 集中复审与非阻塞收口

用户提供的集中复审接受 `496d8973c113795340111053ddbc9ef2aaeec92d`：Editorial Profile v1.0、G0～G4 呈现修订与 G5～G7 Professional Handbook Edition 可作为出版源稿基线；定向证据为 ACCEPTED WITH DECLARED LIMITATIONS。跨平台验证仍未建立，PDF 仍为 NOT BUILT / NOT VALIDATED。这是用户提交的审核结论，不是新增 CI 结果。

本次仅处理三项非阻塞编辑意见：G7 Gate 前两题移除内嵌答案，保留独立参考答案；G5 Gate 九类问题改用分组标题，移除重复标题；G7-D3 编译证据统一称为 known-race positive-control fixture。实验源码、判据和历史 JSON 不变；旧 JSON 的措辞与摘要属于原提交，不追写成当前执行结果。

本次实际检查：`python3 c++/learning/check_docs.py`（34 份 Markdown、662 处本地链接，无错误）；`python3 -m unittest discover -s c++/learning -p 'test_*.py'`（24 项通过，新增 1 项为模拟命令的证据措辞回归，不是 C++ 编译）；`git diff --check`（通过）。另与 `496d897` 比较，G5～G7 的 11 个实验元数据和源码完全一致。本次没有重跑 C++、性能或 TSan 实验，没有构建 PDF。

三项收口单独提交、推送后，依据本轮明确授权继续 G8～G9 完整批次；G10～G12 不随之启动。
