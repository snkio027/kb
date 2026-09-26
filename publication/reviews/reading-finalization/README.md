# Reading Edition Finalization

目标：**Publication Visual Profile v1.0 Freeze Candidate**。基于 `783c7d3b9b6a1e4f715a960c18e687604143f98b`，仅定稿出版组件与验证；不是新的技术基线或正式发布。

## 审核入口

- [视觉与分页合同](visual-profile.md)：硬约束、人工判据及冻结边界。
- [八组 A/B 决策](component-ab/decisions.json)：真实语义样本、前后页图和选择理由；属于中间组件试件，不冒充最终制品。
- [最终制品清单](inventory.json)：12 份 PDF 的路径、页数、SHA-256 与源身份。
- [最终页图审阅记录](visual-inspection.json)：实际查看的图片、摘要、观察与限制。
- [最终回归记录](final-checks/checks.json)：实际执行命令、输出摘要与受保护文件比较。
- [C++ 预览入口](cpp-handbook/output/README.md)、[ESD 预览入口](esd/output/README.md)：最终阅读文件及对应原始源副本。

`STRUCTURAL_PASS` 只表示已定义的结构／几何信号通过；`VISUAL_REVIEWED_SELF_REVIEW_NOT_APPROVAL` 表示实际页图自查。二者不得合写为“全部出版验收通过”。本目录供集中审核，尚不宣告独立评审或 `VISUAL_PROFILE_FROZEN`。

## 本次处理

| 问题 | 出版层处置 | 验证方式 |
| --- | --- | --- |
| 危险身份与代码失联 | 将紧邻代码的明确源标签放入首段代码框；续页重复角色、实验 ID、文件名 | 首标签与第一源码行目的地同页；真实长反例续页回归；页图审阅 |
| 短结尾尾页 | 按精确源标题选择短收尾单元，局部回收标题／段落间距，保留正常留白 | Ops 结论及 Compact G6 过渡＋参考入口 A/B；收尾页眉复核 |
| 空模板成为字段流 | 独立 Empty Template：名称、顺序字段、可填写空值线；不生成数据行 | 原字段顺序与空行语义核对；短模板整体；38 字段长模板强制续页回归 |
| Record 起始位置不齐 | 修正 minipage 首行与目的地的垂直模式，标签和值共用首行起点 | PDF 目的地基线差检查、8.8 pt 错位反例与实际记录页 |
| 标签过强 | 保留源角色／实验文件身份；内部 Cxx、Txx 和映射 ID 留在 JSON | 源标签仍逐段核对；实验续页身份检查；普通字面块页图 |
| 任意字符折行过早 | 空格、语义标点、identifier 边界、应急字符四级断点 | `OPERATIONAL` 整词；下划线断点优先级；180 字符无分隔串真实编译 |

不改变主字号、页边距或主色阶。未修改 `pub.py`、`candidate.py`、`source_model.py`、链接解析器或发布架构。正式 `publish` 仍关闭。

## 冻结与证据身份

C++ G6/G7 继续读取 `8f479deaf660533b2ad82e1f721eb41a363112b6` 的内容字节；ESD 六篇按实际工作树字节绑定。原始 Markdown、实验源码、Final Gate、历史 PDF、`design/dist/` 及两个旧 review 目录都不重写。

本次更新的是出版源码和新生成的预览字节。历史 C++ 编译／诊断、性能和并发动态证据不重跑、不改摘要、不升级为新执行结果。没有执行 G0–G12 全书构建、正式发布或 PDF/UA 验证。

本机候选复制已经检查过的 PDF，不在冻结时重新编译。审核导出不是完整候选目录；每个产品的 `export.json` 明列导出／未导出项，`derived-export.json` 单独绑定派生页图和几何检查。最终 PDF 必须以本目录 `inventory.json` 为准，不混用组件试件。

## 实际结果（2026-09-27，本地）

| 证据层 | 本次实际执行 | 不能推出的结论 |
| --- | --- | --- |
| 隔离／候选／产品回归 | 43＋8＋15 项通过 | 不是正式发布事务验收 |
| 真实编译及故障／取消／组件回归 | 14 项通过，包括错误下划线断点实现被定向拒绝 | 不是 C++ 技术实验重新执行 |
| 阅读规则与负例 | 13 项通过；本批总计 93 项，0 SKIP | 不将自动通过等同人工视觉批准 |
| 完整产品 | 12 份 PDF，780 页；全部渲染；两个产品均 `PREVIEW_READY`、`STRUCTURAL_PASS` | 不代表全部 780 页逐页人工审阅 |
| 语义回归 | 23 个 fixture 定义、55 个产品视图绑定；导出 77 张最终代表页图 | 物理页码不是永久样本身份 |
| 视觉自查 | 八组中间 A/B、50 张最终完整页图直接查看；未见本批范围内的视觉 blocker | 不是独立接受或 PDF/UA 认证 |
| 全页几何信号 | 780 页；317 个 CJK 标点字框侧承／突出信号按有界规则归类，0 未解释信号 | 原始信号仍保存；不是“零几何信号”或重叠检测证明 |
| 源与导出绑定 | 12 PDF／候选／输入／页图摘要一致；429 个受保护文件不变，`design/dist/` 完整文件集合不变 | 不改写既有技术证据身份 |
| 文档检查 | C++ 38 份 Markdown、962 个本地链接通过；本批维护入口 3 份解析、14 个本地文件链接通过；差异检查通过 | 未验证联网 URL；入口检查未声称锚点检查 |

最终页数：C++ G6 48、G7 44、合订 90、Compact 89；ESD Suite 17、Method 30、Reference 58、Governance 37、Assurance 41、Ops 47、合订 223、Reference Compact 56。页数是观察结果，不作为版式质量目标。

运行环境为 macOS 26.7 arm64、Python 3.12.14、Pandoc 3.11、LuaHBTeX 1.24.0 / TeX Live 2026。精确工具、字体及 TeX 依赖身份见各产品 `preview-audit.json`；没有跨平台或新版 fvextra 兼容结论。

`check-docs.txt` 中的 `PDF: NOT BUILT / NOT VALIDATED` 是未改动的 Markdown 检查器对内容冻结阶段的固定输出，不是本次预览状态。当前预览是否完成，以绑定本批输入的 `preview-result.json`、制品清单和独立视觉自查记录为准。

中间组件回归先后发现并在本批修复了空模板续页生成标题影响保真比对、TeX 下划线字符类别使 identifier 断点失效、收尾容器页眉 mark 未更新等问题。`checks/` 是较早的 91 项记录，`final-checks/` 才是最终 93 项证据，不把中间结果冒充最终验收。A/B 的 B 侧用于选择机制，最终 PDF 另由候选摘要和 50 张最终页图绑定。

G7 Gate 中源稿已有的独立表达式／问号格式保留；空模板只提供可阅读、可手写的空值线，不是交互式 AcroForm。自然留白和这些范围限制不转换为新的正文编辑任务。

## 复跑

```sh
python3 -B publication/engine/pub.py preview --profile cpp-handbook
python3 -B publication/engine/pub.py preview --profile esd
python3 -B publication/tools/reading-review.py <completed-preview-attempt>
python3 -B publication/reviews/reading-finalization/audit-geometry.py <completed-preview-attempt>
python3 -B publication/reviews/reading-finalization/check-delivery.py --output <new-check-directory>
python3 -B publication/reviews/reading-finalization/verify-review.py
```

真实编译仍要求 macOS Seatbelt 隔离后端、已记录的 Pandoc/LuaLaTeX/字体环境。检查和构建均使用新尝试目录，不覆盖旧记录。没有 GitHub CI 结论；本轮记录属于本地执行与自查。

## 停止边界

本批候选交付后停止，不进行第三轮非阻塞美化，不自动进入全书构建。集中审核通过后再登记视觉 profile 冻结；后续一般审美增强进入 backlog，内容、身份、历史制品安全或基本可读性 blocker 除外。
