# G0～G7 理论与专业术语修订记录

2026-10-03 · **PENDING READER REVIEW / NOT FROZEN**

本批依据“一次性完成 G0～G7 修订”的授权，重新打开 18 篇 Content v2 正文。读者定位为学习能力强、有工程经验的高级工程师；不以降低术语密度代替解释，也不以增加实验数量代替理论。Base 为 `b052f59f58582d7675e15ba96fed48f086744cec`。旧版本的精读接受仍成立，新正文须另经集中审核。

## 1 内容修订与阅读入口

[Editorial Profile v1.1](../editorial-profile.md)统一理论深度与术语策略：中文承担推导，英文保留专业定位；核心模型须能回查 definition、relation、rule、boundary。`rework/README.md` 不再要求“术语首次出现后统一使用中文”，也不再作为平行规范维护另一套规则。逐单元入口见[阅读与理论回查](README.md#g0g7-阅读与理论回查)。

| 章节 | 本批补强的理论关系 | 没有由此增加的结论 |
| --- | --- | --- |
| G0 | caller／callee 的语言、ABI 与绑定合同；declaration／entity／linkage；symbol／relocation；as-if rule | 链接成功不证明所有跨 TU 合同一致；未启动完整 ABI 专题 |
| G1 | scope／storage duration／lifetime；borrow contract；invalidation；value／representation／access type | 没有引入 borrow checker、完整 provenance 或序列化框架 |
| G2 | resource invariant；cleanup／commit／durability；ownership graph／access graph；handoff 与 closure 使用区间 | RAII 不自动证明业务回滚、持久性或线程安全 |
| G3 | representation invariant 与 abstraction function；prepare／commit；type／value category／lifetime；result object | move 不自动转移资源；零构造观察不是性能证明 |
| G4 | 五种身份／有效性坐标；摊销成本；multi-pass；strict weak ordering；view 依赖；跨容器 invariant | 未重新实现容器或索引，也未新增性能结果 |
| G5 | 调用信息流；satisfaction／modeling／subsumption；实例化需求；binding time；实现供应集合 | 编译可行不等于语义模型成立；未扩展技巧库或构建平台 |
| G6 | footprint／traffic／reuse；吞吐与依赖关键路径；测量边界；measurement validity 与因果判断 | 新成本推导是分析模型，不是新测量；保留 SoA 未普遍占优的旧观察 |
| G7 | data-race freedom／linearizability／liveness；lock invariant；wait-for graph；MO／RF／HB；逐代双向交接 | 未做模型检查，不把有限运行或 TSan 无诊断当作完整协议证明 |

新增理论紧邻对应案例，原有 H1/H2 主线保持；少量 H3 编号调整用显式 alias 保留旧定位。语言规则继续引用 C++23 / N4950，线性化性质补引 Herlihy／Wing（1990）。新增英文不是另一套标题列表：它们分别指向定义、责任或推导层次。概念间的因果关系仍用连续中文解释。

## 2 新正文与历史证据的关系

[机器审计](theory-terminology-audit.json)分别记录 Base 正文摘要、当前正文摘要和所绑定历史 JSON 的身份。它比较全部 fenced payload，而不只数代码块；再将各组具名源文件的 SHA-256 与相应历史 `source_sha256` 完整映射比较。G1 使用包含第三单元的 `g01-review-results.json`，不拿早期两单元结果冒充三单元验证。

八个执行器、共用 helper、历史 JSON 与八份验证说明均未改。历史记录中的平台、工具链、选项、PASS／CLEAN_OBSERVED／OBSERVED／SKIP 和未验证部分保留原身份。实验源码相同支持继续引用那些具体执行事实，不证明新增论述已由实验穷举验证。

这些执行器绑定原批次的受保护输入，当前文字变化可能触发其拒绝条件。需要复现历史完整执行时，应在对应历史 checkout 中运行；本轮不修改 guard 以制造当前工作树“全绿”。独立实验可继续按正文提取源码执行，但结果须单独登记。

| 本轮检查 | 结果及边界 |
| --- | --- |
| 18 篇正文结构与 payload 审计 | PASS；145 个 fenced payload、269 个旧定位目标保留 |
| 具名实验源码绑定 | MATCH；8 组共 102 个文件映射与历史摘要一致，组间同名文件分别计数 |
| 迁移题／答案 | 18 个从首个 Gate 标题至文末的区域逐字节不变 |
| 审计自检 | 5 项：允许普通文字变化；拒绝代码、Gate、定位目标和源文件身份变化 |
| 范围外已跟踪文件 | 1,150 个文件 Git blob 身份与 Base 一致，包括 v1、FM、出版系统、历史 PDF 与制品 |
| C++ 编译／负例重跑 | **NOT RUN**；本批不改代码或执行判据 |
| 性能重测／生成物重取 | **NOT RUN**；未改变原观察的输入或口径 |
| 并发动态检测／stress 重跑 | **NOT RUN**；人工理论复核与历史动态检测分开 |
| PDF | **NOT BUILT / NOT VALIDATED**；不改历史发行版，不启动 G8 |

## 3 实际检查与复核边界

从仓库根目录执行：

```sh
python3 c++/rework/audit_theory_revision.py
python3 c++/learning/check_docs.py
git diff --check
```

审计通过后用下列命令生成新记录；输出采用排他创建，不覆盖已有记录。再次复核时运行上面的无输出参数形式。

```sh
python3 c++/rework/audit_theory_revision.py --output c++/rework/theory-terminology-audit.json
```

实际环境为 macOS arm64、Python 3.9.6、Pandoc 3.11。上面四条命令均已执行：审计及排他生成返回 0，`check_docs.py` 最终检查 **68 份 Markdown／947 处本地链接，0 errors**，`git diff --check` 返回 0。它们是本地检查，不是 CI 结果。

本地链接检查的首次执行因本文尚未落盘报告两处缺失链接，不计为通过；补齐后重跑得到上述结果。结构审计额外覆盖这 18 篇重编稿的 H1～H3、重复锚点、fence 配对与 HTML 折叠；既有 `check_docs.py` 的深层版式风险检查主要针对 v1 十三章，仍报告 16 项历史 `code_or_diagram_pagination` 风险，不能把它们当成本批 PDF 检验。

人工自查重点是新增论述是否给出可解释的关系，以及是否把语言规则、工程分析模型和实际观察混在一起。本批没有声称穷举审查全部标准条款、重新验证所有外部 URL、完成跨平台测试或获得 CI 结果。技术深度和阅读体验仍须由集中精读审核判断，结构 PASS 不替代读者接受。
