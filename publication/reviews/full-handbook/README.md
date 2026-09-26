# G0–G12 Full Handbook Build

本批只验证冻结的 Publication Visual Profile v1.0 在全书中的适用性，不设计新排版，不重新验收 C++ 技术内容，不执行正式发布。

## 交付结果

**PUBLICATION_CANDIDATE_FOR_REVIEW — 1 份全书 / 407 页 / G0–G12。**

阅读 [Modern C++ 全书 PDF](cpp-handbook-full/output/pdf/CPP-HANDBOOK-draft.pdf)。本件可搜索，保留原章编号、目录、分组书签及跨章定位；状态是待集中审核的候选，不是正式发布。

| 绑定项 | 值 |
| --- | --- |
| Candidate ID | `ecdca3ee3aa9654d60eef16fa99c324d6fec5a782a754761c14a07a4e33104b2` |
| PDF SHA-256 | `80aabc252ef41eccb04a67504af1401e3f89211a43a1a89d761980143b225b26` |
| 最终 preparation / attempt | `cbf823ee…be2a5e4` / `bf7b6b4fb9b84f53b0093e93a5855785` |
| 结构状态 | `STRUCTURAL_PASS`，不等于人工阅读或技术批准 |
| 代表页自查 | `VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL`，54 张页图 |
| 正式发布 | `NOT RELEASED`，publish 继续关闭 |

精确身份见[制品清单](inventory.json)、[候选 manifest](cpp-handbook-full/candidate-manifest.json)和[导出清单](cpp-handbook-full/export.json)。Git 中保存的是审核导出包，不是完整本地候选：未导出的编译中间文件、工具输入等逐项列在 `export.json` 的 omitted 中。代表页和几何报告为另行生成的审核证据，由[派生证据清单](cpp-handbook-full/derived-export.json)绑定，不冒充候选原始载荷。

## 输入与边界

| 身份 | 固定对象 |
| --- | --- |
| Markdown 内容 | `8f479deaf660533b2ad82e1f721eb41a363112b6`，G0–G12 共 13 篇 |
| 视觉实现 | `1c11c5940c05fe29c46c4500935d5efb673d46a7` |
| 视觉接受登记／本批 Base | `ea2e613b97ddd8a146c7899e7ffde7e80c238e57` |
| 新产品入口 | `cpp-handbook-full`，一份 `CPP-HANDBOOK` 合订阅读候选 |
| 既有产品与发布 | ESD、Pilot、历史 review、PDF、`design/dist/` 保持原字节；publish 关闭 |

G0–G4 保留 1.2.1，G5–G12 保留 1.1.1；合订制品 `candidate.1` 不替代各章版本。十三章身份、原编号、实验文件与 Gate 均保留。正文中的历史“待审核”“PDF NOT BUILT”等状态是内容快照，不改写为本次结果；生成的控制页单独标明冻结视觉 profile 与全书预览身份。

## 本批接入与缺陷修复

共享构建流程、Lua Filter、LaTeX 组件及旧产品配置均不改。新 profile 沿用 Balanced、字号、边距、颜色、层级、代码头尾与 G6 收尾规则，不增加 Compact 比较。共享检查器将反复解析的 PDF 目的地表缓存一次，避免全书级重复工作；坐标、顺序、归属和内容判据不变。内部链接解析器修复别名到真实章节标签的选择，并调整对应回归；两者均不是引擎架构或排版重构。

| 新章节暴露的问题 | 全书产品层处理 | 限定 |
| --- | --- | --- |
| 实验标记使用 g/h/n/s 四个前缀 | 枚举原始前缀，复用原 Pilot adapter；保留原命名空间、完整 JSON 载荷与文件关系 | 只改解析副本，不运行实验 |
| 连续 HTML 锚点被解析成混合 RawInline／SoftBreak | 仅拆分已验证的 anchor-only 段落，再交给原别名映射 | 不吞掉未知 HTML |
| C++ 尖括号被误识别成 HTML | 按 G3/G4/G5 的精确 token 与出现次数原样打印 | 源文字不改；未知 token 仍拒绝 |
| Mach-O `@rpath`／`@loader_path` 被误识别成文献引用 | 按 G8/G9 的精确库存恢复为字面语法 | 不是重新解释真实参考文献 |
| `↔` 字形缺失 | 新 theme 增加与既有箭头相同的数学字形回退 | 不换字体或色阶 |
| G8/G9 两处普通标识符越界 | `requested_version`、`CMakeUserPresets.json` 使用既有行内代码组件，拆出的行内节点直接归属原段落 | 原字符不变；CJK／标识符间增加排版词边界，不引入包裹整段的 TeX group |
| G9 §5.1 同段对比预设时长文件名仍越界 | 在原有分号处把团队预设和个人预设分成两个排版段落 | 文字、标点、顺序均保留；精确匹配与保真检查约束，不设置任意断字 |
| 普通正文中的 C 链接 ASCII 引号被 TeX 转成弯引号 | G8 的 `"C"` 字面语法使用既有行内代码组件 | 不放宽内容审计来掩盖字符变化 |
| 嵌套的 Final Gate 小节再次触发清页，留下孤立父标题 | 新产品将既有 Gate 开页规则绑定到顶层编号节，不匹配 `13.1` 子节 | 不改 Gate 内容或共享分页算法 |
| G12 §8 标题落在页尾，首块进入次页 | 用既有开页策略绑定该精确标题 | 不按物理页码打补丁，不改变其他产品 |
| 源 HTML 别名只有 PDF destination，没有 LaTeX 引用 label，导致正文链接未生成可点击区域 | 同视图链接改指别名所属章节的真实 label；原别名 destination、源 URI 与外部源链接均保留 | 独立复核正文中的点击区域：章节归属、目标与重复次数，不拿目录链接代替正文链接 |

这不是 Typography Pass 3。仅处理全书接入、缺字和可读边界 blocker；普通留白、局部折行和已接受的非阻塞限制继续保留。

## 构建与检查命令

```sh
python3 -B publication/engine/pub.py preview --profile cpp-handbook-full
python3 -B publication/tools/reading-review.py <completed-preview-attempt>
python3 -B publication/reviews/full-handbook/audit-full.py <completed-preview-attempt>
python3 -B publication/reviews/full-handbook/check-delivery.py <new-check-directory>
python3 -B publication/reviews/full-handbook/verify-delivery.py
```

使用已有 macOS Seatbelt 内部沙箱、Pandoc、LuaLaTeX 与 Poppler；每次尝试写新目录。失败／取消尝试不作为成功制品。候选冻结仅复制已检查的成功预览字节，不重新编译。

`checks/`、`final-checks/`、`integration-checks/`、`integration-checks-2/`、`integration-checks-3/` 是批内中间执行记录，不是最终输入验收。第二组虽然文件名包含 final，但执行过程中适配仍在变化；后三组已经设置输入前后比对，因此如实报告输入漂移。最终证据只使用 `delivery-checks/`，要求全部命令成功且运行前后输入摘要相同。不覆盖或追写中间 JSON。

## 证据口径与停止点

### 实际执行结果

平台为 macOS 26.7 / arm64，Python 3.12.14；Pandoc 3.11、LuaHBTeX 1.24.0 / TeX Live 2026、Poppler 26.05.0、pypdf 6.10.0。完整命令、耗时、摘要与原始日志见[最终检查记录](delivery-checks/checks.json)。全部为本地证据，不声称 GitHub CI 结果。

| 证据层 | 实际执行与结果 | 不推出的结论 |
| --- | --- | --- |
| 文档结构／链接 | `check_docs.py`：38 份 Markdown、962 处本地链接，无 errors；保留 16 个代码／图分页风险提示 | 不验证 C++ 正确性或联网 URL；该检查器固定输出的 PDF NOT BUILT 仅表示自身不检查 PDF |
| 出版回归 | isolation 43、candidate 8、products 15、preview 14、reading 13、full-handbook 6，共 99 项，全部通过，无 SKIP；输入前后摘要一致 | 不是 99 个 C++ 实验；真实编译失败／取消用例操作一次性夹具仓库，不是重复中断最终 407 页制品 |
| 源适配保真 | 13 份源与 `8f479de` 精确字节相同；953 个 fenced payload、1,714 个显式锚点、30 组实验／68 个文件标记载荷对应 | 不重跑历史实验，AST 中的排版段落边界不宣称与 Markdown 空白一模一样 |
| PDF 全书结构 | 407 页均渲染；1,014 个源标题区间、6,972 个顺序单元、896 个行内字面量、268 个表格行关系检查通过；无正文／关系／字面量丢失、孤立标题或 overfull blocker | 有界提取不是逐字形和代码缩进证明 |
| 导航 | 14 个一级书签组（说明页＋13 章）、9,457 个 named destinations、779 个链接注释；335 处内部源引用，其中 79 处跨章；按所属章节、目标及重复次数核对正文点击区域 | 未逐个在阅读器点击；不以目录链接代替正文链接，不核验网页可达性 |
| 阅读信号／视觉 | 冻结 corpus 的 9 个适用样本，信号 `STRUCTURAL_PASS`；407 页几何扫描，262 个中文标点边界字形按既有规则分类，未解释越界 0；54 张 120 dpi 代表页实际查看 | 不声称 407 页全人工精读，不是独立用户接受、PDF/UA 或打印认证 |
| 历史保护 | Base 中除本次明确修改的 4 个既有文件外，678 个已跟踪文件逐字节不变；`design/dist/` 完整文件集合与字节不变 | 不重新解释旧审核记录，也不回写旧 PDF／JSON 摘要 |
| C++ 编译／负例诊断 | `NOT RUN` | 既有技术证据保持历史身份 |
| 性能观察 | `NOT RUN` | 不新增跨机器性能结论 |
| 并发动态检测 | `NOT RUN` | 不新增 TSan／stress 或协议正确性结论 |

全书定位与抽样页见[结构报告](cpp-handbook-full/full-review/structure.json)，实际查看范围、图像摘要和判断见[视觉自查](visual-inspection.json)。本批补充检查发现的内部别名链接缺陷，是在第一次 `PREVIEW_READY` 之后发现的；该中间版本没有被交付。修复后重新编译，再通过独立正文点击区域检查。所有 11 次全书尝试的终态和日志在[尝试记录](attempt-history.json)：7 次失败、2 次取消、2 次 PREVIEW_READY，只有最后一次绑定本候选。一项取消的外层清理曾报 PermissionError／退出 1，但终态为 CANCELLED，未留下 PREVIEW_READY；另一次正常取消退出 130。没有把这些尝试计为成功。

### 已知非阻塞限制

- 第 11 页目录尾与第 18 页短 Gate 留白较大，沿用冻结的开页规则；没有丢内容。
- 第 109／165 页的粗体 Gate 类别标签可留在页尾、题目在下一页继续；不是危险示例身份丢失。
- 第 304／382 页等长代码仍有不够理想的软折行，但续行符、实验与文件身份可辨。
- 第 45 页短引导与后续块、末页参考资料仍存在局部节奏／留白空间；本批不再做新的视觉优化。

这些是本次自查保留给集中审核的已知非阻塞限制，不声称全部已经修复或已由用户逐项接受。正文危险反例标签、完整实验续页身份及冻结源码字节仍按阻断底线检查。

结构检查、代表页自查、用户接受及正式发布是不同状态。C++ 编译／负例诊断、性能测量、并发动态检测均不在本批重跑；既有技术证据保持历史身份。没有跨平台、PDF/UA、打印或全页人工阅读认证。

交付全书 Publication Candidate 后停止，等待集中审核与最终发布决策，不自动 publish，不新增章节，不借审核扩写内容或重开版式设计。
