# KB Publication Layout Architecture — Next Generation Design Study

状态：**DESIGN QUESTIONS / CONSTRAINTS FROZEN — IMPLEMENTATION NOT STARTED**。2026-09-27 收口；现状核对基于 `a86d504019bdd08ddc771fea1239ff9a798f2dbb`。本文是短研究边界，不是新的宏观标准或实施授权。

## 1. Scope / Non-goals

只冻结四类问题：Reader / Audit 信息边界；组件、产品、视觉与渠道职责；布局依赖闭包；变更分类与验证 Gate。第一优先级是 **layout dependency selection / identity isolation**，先证明新旧实现可以安全共存，再讨论拆包。

生产状态保持：KB Publication System v2 **STABLE**；[Visual Profile v1.0](reviews/reading-finalization/visual-profile.md) **FROZEN**；[Modern C++ Handbook v1.0.0](releases/cpp-handbook/v1.0.0/README.md) 与 [Failure Semantics Handbook v1.0.0](releases/cpp-failure-model/v1.0.0/README.md) 均 **RELEASED**。下一代布局实现与以下两类实验均 **NOT STARTED**。

不重写正文、实验或 Gate，不修改现有布局、字体、模板、历史 profile、已发布资产或 tag；不重建两本书，不新设 Visual Profile v2，不扩展 Print Profile、多引擎或插件框架。目录树不是本轮决策对象。

## 2. Reader vs Audit Information

| 信息类别 | 归属 | 不能丢失的内容 |
| --- | --- | --- |
| Inline Semantic Context | 必须跟正文／组件 | 反例、危险条件、适用前提、实验身份及必要证据限制 |
| Reader Publication Identity | PDF 阅读层 | 书名、版本、章节、页码及必要的历史状态解释 |
| Build / Audit Identity | manifest / evidence | preparation ID、工具、输入摘要、依赖闭包 |
| Release Identity | release record | tag、PDF SHA-256、发布载荷 commit、分发状态 |

核心不变量：**可以减少工程噪声，但不能减少理解语义所必需的信息。** 审计信息可以集中，危险／反例身份和语义限制不能被移到读者难以关联的附录。历史状态提示可以研究“总说明＋必要章内提示”，不能直接删除，也不能改变冻结正文。

## 3. Responsibility Model

逻辑关系为 `Source Adapter → Semantic Document Model → Layout Components → Visual Profile → Presentation Channel → Artifact`；这是职责示意，不预先规定执行流水线或要求每层各建一个目录。

| 角色 | 责任与边界 |
| --- | --- |
| Source Adapter / Semantic Document Model | 识别源结构并保留语义、身份、引用和源块映射；不得暗改内容 |
| Layout Components | Code、Table、Record、Template、Heading、Pagination、Navigation 的行为合同 |
| Product Profile | 选择源、章节组成、语义分类及产品导航；不复制整套视觉机械 |
| Visual Profile | 字体、字号、颜色、版心、spacing 与组件外观；不定义发布批准 |
| Presentation Channel | preview / candidate / publication 的读者可见身份；不是分发状态机 |
| Release Authorization | 完全位于生成系统之外；由明确授权和分发回执表达 |

必须保持 `channel = publication ≠ release authorized ≠ released`。历史 Pilot / RC / publication profile 原样保留为证据入口。未来中性接口如 `\KBCodeBox` 应先通过 compatibility facade 兼容既有 `Preview*` 接口，不做一次性重命名；namespace cleanup 本身不是交付目标。

## 4. Layout Dependency Model

当前 [source_model.py](engine/source_model.py) 递归快照整个 `publication/latex/`。拟研究的模型为：

```text
product/profile
  → declared layout selection
  → exact repository dependency closure
  → preparation identity
  → restricted build
  → observed runtime closure
```

**Declared repo inputs** 是事前声明／解析得到的仓库依赖集合；**Observed runtime inputs** 是实际运行观测到的 `.fls`、字体和 TeX 包等输入。二者关联但不能互相冒充：运行时观测不能给未声明仓库依赖补授权，也不单独证明读取隔离。

未来需证明的两个目标：加入未使用的实验布局，旧产品 preparation identity 不变；访问未声明的仓库布局依赖，fail closed。应同时覆盖被选中的依赖变更使身份变化、传递依赖、路径越界及工具／字体变化的身份记录。仅事后发现 `.fls` 不匹配，不足以宣称事前输入隔离已经成立。

**身份定义尚待研究。** 当前 [pub.py](engine/pub.py) 还将 HEAD、dirty 状态和工作区状态摘要纳入 preparation identity。缩小布局快照范围并不能独自满足第一个目标。需明确完整 preparation identity、所选输入身份与 provenance 各自职责，以及比较时固定哪些非布局条件；不得通过隐藏上下文或把局部摘要冒充完整身份来获得“不变”。新模型未证明前，现有行为不改。

## 5. Change Classes and Gates

| Class | 变化 | 最低证据要求 |
| --- | --- | --- |
| A | 内部接口／文件拆分、兼容 facade | 结构、语义、导航回归＋visual no-regression |
| B | Reader metadata、页眉页脚、前置页 | 定向视觉 A/B＋identity 检查 |
| C | 字体、字号、版心、spacing | 全书 pagination / glyph / copy / search 检查＋新视觉接受 |
| D | Code / table renderer 等机制变化 | 完整出版 qualification＋reader compatibility |

混合变化取适用 Gate 的并集，不用较轻类别替代较重验证；各类均保留源字节、危险身份、导航及历史制品保护。Class D 的 qualification 是出版范围，不等于 C++、性能或并发技术验收。

内部 commit 变化不自动要求 Visual Profile 升版；真正改变读者可见视觉规则时才形成新的 Visual Profile candidate。内部重构仍须视觉不退化检查，不能以“仅拆文件”豁免。实测、人工观察、未测和历史证据分别报告。

## 6. Reference Corpus

采用两本已发布 PDF 的精确字节，不用重新构建物替代参照物：

- **Modern C++ Handbook**：407 页，tag `cpp-handbook-v1.0.0`；SHA-256 `ce4f6d5f6e4b8c1e2789eedd1fc151462d31e929b724ce2eb95c780f90766510`；[发布回执](releases/cpp-handbook/v1.0.0/publication-receipt.json)。
- **Failure Semantics Handbook**：158 页，tag `cpp-failure-model-v1.0.0`；SHA-256 `2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c`；[发布回执](releases/cpp-failure-model/v1.0.0/publication-receipt.json)。

固定研究场景：cover / publication info、TOC、chapter opening、dense prose、long experiment、dangerous example、code continuation、soft-wrap、comparison matrix、record、literal template、cross-chapter link、Final Gate、last page。

每个场景以后绑定“语义目的＋书／源对象／稳定目标＋PDF 摘要”；物理页码只是该字节版本下的定位结果。复用[既有语义 corpus](tools/reading-corpus.json)与两书审核记录，不声称本轮已建立新的可执行 corpus 或完成样页复核。若两书不具备某种真实组件，明确登记覆盖缺口；不得把 literal template 冒充 Empty Template，也不替代原有边界／负例 fixture。

## 7. Open Research Questions

首先确定依赖选择、传递闭包、事前读取边界与运行时核对的关系，以及 HEAD／工作区 provenance 如何与输入身份共存。其后才决定最小组件接口、共享模板的产品参数、通用 glyph policy 和私有 API 的兼容边界；现有 `fvextra` 实现不在本轮替换。

两类实验必须独立，均待后续授权：

- **Experiment A — Reader Metadata**：只比较前置页、页眉页脚、source-history 提示及审计元数据集中方式；字体、字号和版心不动。
- **Experiment B — Typography / Font**：只替换字体 stack，其余保持 v1；验证 glyph coverage、CJK/Latin 匹配、嵌入、copy/search、identifier rendering、换行、分页漂移、PDF 大小、license 和版本锁定。Source Han / Noto / Sarasa 仍只是候选，未核验、未选型。

代表页 A/B 用于研究，不等于 Class C 全书验收。字体替换导致的分页变化属于观察结果，不暗中调整边距或字号补偿后仍称“只换字体”。视觉参数冻结不等于跨机器字节级可复现。

## 8. Decision Boundary

本轮只冻结问题、约束、场景类别与后续证据要求；不冻结未验证的解决方案。后续第一项研究是依赖选择／身份隔离，先给出可反驳的命题、比较条件和失败判据，再决定是否启动实现。收益应能用两本书的真实语料独立验证，而不是以拆包数量、文件数或命名一致性衡量。

**本文不授权修改 Visual Profile v1.0、现有 layout implementation、已发布 PDF 或历史 profile。** 本次仅登记设计研究，不运行字体／元数据实验，不启动重构，不改变生产或技术验收状态。
