# Reading Edition · 集中审核记录

状态：**IMPLEMENTED / VISUAL PROFILE CANDIDATE / AWAITING INDEPENDENT REVIEW**。本批只实施阅读版排版、分页、导航及其验证；v2 架构不再拆分重构，正式 `publish` 仍关闭。不改冻结正文，不启动全 G0～G12 出版。

实施起点：`fed7e085f77721c66076be344652d48eac27f041`。C++ 内容仍固定于 `8f479deaf660533b2ad82e1f721eb41a363112b6`。构建使用提交前的输入快照，逐文件摘要绑定实际实现；不声称制品已经由随后产生的提交 SHA 重建。

## 本批结果

十份主制品使用 Balanced Reading；另提供 C++ 合订版及 ESD Reference 的 Compact Reference 对照，共 12 份 PDF。[视觉 Profile 候选](visual-profile.md)规定实际参数、保留规则与启发式边界；它尚不是冻结的视觉基线。

主要变化：短表整块保留；短记录整条保留，长记录以标签—值为不可拆字段组；代码保留首尾上下文，长实验续页重复实验 ID 和文件名；软折行采用向量提示与悬挂缩进；流程图不静默折行；标题视觉角色与 Markdown 层级分离；减少重复横线和外框；合订目录显示文档与主要节；C++ 章内导航、历史源状态与全卷导航明确区分。

Final Gate 的题号和首句在出版层同排，加粗分组标签与下一题保持。源代码、题目、参考答案及技术 oracle 原字节不变。页眉显示当前文档和主要节，生成条款索引切换自己的页眉；完整构建身份留在控制页。

## 制品与样张

[inventory.json](inventory.json)记录完整制品摘要、源身份及候选 ID；下表均为审核副本，不是正式发布。

| 阅读产品 | Balanced | Compact 对照 |
| --- | --- | --- |
| C++ G6 | [内存与性能](cpp-handbook/output/pdf/G6-draft.pdf) | — |
| C++ G7 | [并发与内存模型](cpp-handbook/output/pdf/G7-draft.pdf) | — |
| C++ 合订 | [G6 + G7](cpp-handbook/output/pdf/CPP-PILOT-G6-G7-draft.pdf) | [同内容、不同结构密度](cpp-handbook/output/pdf/CPP-PILOT-G6-G7-COMPACT-draft.pdf) |
| ESD Suite | [套系关系](esd/output/pdf/ESD-SUITE-000-draft.pdf) | — |
| ESD Method | [方法论](esd/output/pdf/ESD-METHOD-001-draft.pdf) | — |
| ESD Reference | [工程参考](esd/output/pdf/ESD-REFERENCE-001-draft.pdf) | [同内容、不同结构密度](esd/output/pdf/ESD-REFERENCE-001-COMPACT-draft.pdf) |
| ESD Governance | [治理](esd/output/pdf/ESD-GOV-001-draft.pdf) | — |
| ESD Assurance | [保证论证](esd/output/pdf/ESD-ASSURANCE-001-draft.pdf) | — |
| ESD Operations | [生产与运行](esd/output/pdf/ESD-OPS-001-draft.pdf) | — |
| ESD 合订 | [工程保证工作手册](esd/output/pdf/ESD-HANDBOOK-draft.pdf) | — |

两套样张不比较 11 pt 与更小字号，而只比较节距、字段距、目录与表格行距。当前建议保留 Balanced 为主候选；Compact 的记录更紧凑，但局部因整块保留而出现较大的页尾留白，不能把页数减少自动解释为阅读改进。

最终页数：C++ 为 **50 / 46 / 94**，ESD 为 **17 / 31 / 59 / 38 / 42 / 49 / 229**（Suite、Method、Reference、Governance、Assurance、Operations、合订）。十份主制品合计 **655 页**，上一批为 678 页；两份 Compact 样张为 **92 / 58 页**，全批共 **805 页**。页数仅说明实际制品规模，不是优化得分。

## 实际命令与证据

平台：macOS 26.7 / arm64。解释器为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`；下列 `python3` 指该解释器。Pandoc、LuaHBTeX、Poppler、pypdf、TeX 与字体身份均由各产品 `preview-audit.json` 的执行记录绑定。桌面环境需授权控制器启动内部 `sandbox-exec`；没有取消构建器自身隔离。

```sh
python3 -B publication/engine/pub.py preview --profile cpp-handbook
python3 -B publication/engine/pub.py preview --profile esd
python3 -B publication/tools/reading-review.py <cpp-completed-preview>
python3 -B publication/tools/reading-review.py <esd-completed-preview>
python3 -B publication/reviews/reading-edition/check-delivery.py --output publication/reviews/reading-edition/final-checks
python3 -B publication/reviews/reading-edition/capture-review.py <cpp-completed-preview> <esd-completed-preview>
python3 -B publication/reviews/reading-edition/verify-review.py
```

实际尝试路径记录于 [visual-inspection.json](visual-inspection.json)及两个 `run.json`。重跑须使用新的证据目录，不覆盖本次记录。`capture-review.py` 先校验样页与终态摘要，再复用现有 candidate 协议冻结、导出原字节，不重新编译或发布。

| 证据类别 | 最终结果与记录 | 不推出的结论 |
| --- | --- | --- |
| 隔离与终态 | [43 个测试](final-checks/test-publication-isolation.txt) | 不代表跨平台隔离、物理掉电持久性 |
| 候选边界 | [8 个测试](final-checks/test-candidate.txt) | 不代表发布事务已开放 |
| 来源与产品适配 | [15 个测试](final-checks/test-products.txt) | 不重新批准规范内容 |
| 编排及真实编译 | [12 个测试](final-checks/test-preview.txt) | 不等于全部真实页面已目视检查 |
| 阅读规则与反例 | [8 个测试](final-checks/test-reading.txt) | 不等于视觉质量自动证明 |
| 文档静态检查 | [38 文件、962 处本地链接、0 error](final-checks/check-docs.txt) | 不验证在线 URL 或 C++ 技术正确性 |
| 真实构建/结构/保真 | [C++ audit](cpp-handbook/preview-audit.json)、[ESD audit](esd/preview-audit.json) | PREVIEW_READY 不是视觉批准或发布批准 |
| 语义阅读信号 | [C++ page map](cpp-handbook/visual-regression/page-map.json)、[ESD page map](esd/visual-regression/page-map.json) | STRUCTURAL_PASS 不是逐页美学判定 |
| 实际页面自查 | [查看图片与摘要](visual-inspection.json)，产品内 `reading-review.json` | 自查不是独立审核，不声称逐字精读全部页面 |

86 是最终五组测试方法之和，不重复计算信号子场景、失败调试、前一轮回归或产品构建。历史 [checks](checks/checks.json) 是批内修正前的 84 项记录，不能冒充最终实现的 86 项证据。最终验证结果见 [final-checks/checks.json](final-checks/checks.json)，不是 GitHub CI。

C++ 编译/负例诊断实验、性能测量、并发动态检测本批均 **NOT RUN**；历史技术执行证据保持原字节。文档检查器原有的 `PDF NOT BUILT / NOT VALIDATED` 是其历史字段，不替代本轮独立的制品终态。

## 视觉回归与本轮修复

[semantic corpus](../../tools/reading-corpus.json)包含 15 个语义样本，绑定文档、标题、表格列或实验/文件身份，而不是固定物理页码。它们在独立版、合订版和密度样张中展开为多个样例。每份 `page-map.json` 记录语义目标 → 实际页 → 120 dpi PNG → 摘要；额外抽查 Final Gate、封面、控制页和模板。

```sh
python3 -B publication/tools/reading-review.py --density-compare publication/reviews/reading-edition/cpp-handbook/visual-regression/page-map.json
python3 -B publication/tools/reading-review.py --density-compare publication/reviews/reading-edition/esd/visual-regression/page-map.json
python3 -B publication/tools/reading-review.py --compare <previous-map> <current-map>
```

比较按相同样本与相同视图匹配；密度对照单独配对 Balanced / Compact，避免把两个变体混为同一视图。它输出可并排查看的语义页关系，不是像素阈值测试，也不自动授予视觉通过。

批内发现并修复了标题链与首个记录相分离、代码分段带来额外空行、字段标签与值定位、Final Gate 加粗分组标签遗留页尾、生成索引页眉沿用上一节，以及旧测试默认“最后一个视图就是合订版”的夹具假设。失败/中间制品留在忽略的 build 尝试目录，未充当本轮最终制品。

最终 805 页均完成 72 dpi 渲染；实际放大查看 **46 张 120 dpi 样页**，其中 38 张在最后一轮重建后经逐字节比较，与本轮已经查看的图片完全一致，其余变化页和新增页重新打开。C++ 的 17 个、ESD 的 16 个语义样本实例均为 `STRUCTURAL_PASS / 0 issue`。自动 page map 的 `NOT_REVIEWED` 保留其自动报告身份；另附的 `reading-review.json` 才是绑定最终字节的作者视觉自查，不追改自动报告来混淆两类证据。

## 接受的取舍与未验证项

保留源码空行和完整实验，Final Gate 的既定章节换页仍可能留下页尾空白。短表、短记录和代码尾部整块保留也可能增加留白；不通过缩小字体、删除条件或拆坏实验来填满页面。ESD 合订目录展开两层，因此比仅列六篇标题更长；没有将其机械压成一页。

源行定位和表格关系检查是有界审计。软折行提示为向量而非新增字符，但不保证任意阅读器复制时的空白、缩进与源码逐字节相同；随附源文件才是精确复制入口。未开展 PDF/UA 认证、实体打印、Linux/CI 可移植性、联网链接检查或独立视觉批准。没有为本批重新执行规范案例、C++ 实验或性能/并发测试。

候选及 Git 导出是不同集合：导出包含 PDF、原始源附件、审计、组件映射和查看记录；完整输入镜像、全部 TeX 中间件与全页 72 dpi PNG 留在本地 build。另行导出的 120 dpi 样页属于派生视觉证据，不冒充 candidate 原始 payload。`export.json` 与 `derived-export.json` 分别绑定两类材料，历史 v2 导出不追写。

本轮仅修改 `publication/`。最终保护检查逐字节核对 **227 个**非 publication 文件及历史 `reviews/v2-pilot/` 文件，并比较 `design/dist/` 完整文件集合，全部不变。冻结 C++、ESD 六篇正文、历史 evidence JSON、PDF 及 Final Gate 均保持原字节。

审核导出检查另核对 12 份 PDF / 805 页、70 张派生样页、46 张实际查看记录及全部摘要绑定，解析三份维护导航并检查 37 个本地链接。完整暂存 `git diff --cached --check` 对不可变 `output/source/` 附件中原有的行尾空白报错（退出 2）；这些字节与 Git 原件一致，不为排版检查改写。排除原字节附件后的暂存检查通过，原始命令及诊断见 [staged-validation.json](final-checks/staged-validation.json)。有限文本凭据模式未发现匹配，不等于全面秘密扫描。

```sh
git diff --cached --check -- . ':(exclude,glob)publication/reviews/reading-edition/*/output/source/**'
```

提交、推送供集中审核后停止。是否冻结 Visual Profile v1.0、是否做最后的局部校准、何时启动全系列 PDF，均不由本轮自查自动授权。
