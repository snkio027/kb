# Modern C++ Engineering Handbook · v1.0.0 RC1

状态：**READY_FOR_RELEASE_DECISION / NOT RELEASED / PUBLISH NOT AUTHORIZED**。本轮按用户批准的 D1–D3 完成 Release Candidate Identity Pass；不重新设计排版，不修改内容，不创建 tag 或正式 release。阅读器判断来自本机 Preview 抽样和用户对 Chromium 检查卡的总体“正常”反馈，证据强度分别保留，见[阅读器记录](reader-smoke.md)。

## 候选与身份

[打开 RC1 PDF](candidate/output/pdf/Modern-Cpp-Engineering-Handbook-v1.0.0.pdf)，407 页，2,741,616 bytes。

```text
Publication ID      CPP-HANDBOOK
Title               Modern C++ 工程学习手册
English title       Modern C++ Engineering Handbook
Publication version 1.0.0
Candidate label     RC1
PDF SHA-256         c011cc4ecddcb20892b0753539356af42c8b2eb636dd2b40b9934bab5af98d0c
Candidate ID        437a5be22378ce3ed4b375312a6982f71126411486a547dad88f29d0fee3b572
```

[SHA256SUMS](SHA256SUMS) 同时绑定 PDF 和[发布候选清单](release-manifest.json)。从本目录执行 `shasum -a 256 -c SHA256SUMS` 可核对下载字节；重新编译不承诺相同摘要，不可用重新编译产物替换此候选。

| 绑定层 | 精确身份 |
| --- | --- |
| 本批实现 Base | `f2880516ea8d71abb6e83f0d463308974e2ae7ca` |
| Markdown Content | `8f479deaf660533b2ad82e1f721eb41a363112b6` |
| Visual Profile v1.0 | `1c11c5940c05fe29c46c4500935d5efb673d46a7` |
| Visual acceptance | `ea2e613b97ddd8a146c7899e7ffde7e80c238e57` |
| Accepted Preview | `eb7f5672d1128607d4f34fa34217aefa9ba99b33` |
| 本批实际输入 | [run.json](candidate/run.json) 的工作树输入摘要，不以旧 Base 冒充新实现字节 |
| 新执行身份 | `fad57208da11c803c0f04980dcd174454a4a06234aeffbb22694fa6dbe3b46f0` |

新 `cpp-handbook-rc1` profile 只调整生成身份：封面／控制页的双语书名、出版版本、RC1 状态，页脚／元数据及最终文件名；源章版本仍为 `1.2.1 / 1.1.1`。源稿原有 `PDF NOT BUILT / NOT VALIDATED` 等历史陈述完整保留，并仍由 source-snapshot 提示限定身份。

引擎增加的最小参数是安全 PDF basename 与 `PREVIEW / RELEASE_CANDIDATE` channel；默认旧行为不变，不允许 `RELEASED`。没有修改编排器、共享 LaTeX、字号、边距、颜色或分页规则。两个引擎文件的限定例外由 `test-release-identity.py` 的固定摘要锁定，profile/模板/主题/全部源 AST 有另外的差异检查。

引擎原有 `PREVIEW_READY`、候选 manifest 中的 draft/review purpose 是**内部工作流标签**，没有被改成发布协议；实际 PDF 及外置 publication manifest 使用 RC1 身份。封面上的“尚未正式发布”与本轮状态一致。若最终发布要求去掉 RC 标记，必须形成新字节并重新绑定，不能在发布时悄悄替换。

## 本次实际检查

全部为本地执行／自查，不是 CI、独立审稿或内容重新验收。命令、工具链、日志和输入摘要见 [checks.json](checks/checks.json)。本轮真实 RC1 full build 仅 1 次，终态 `PREVIEW_READY`；没有失败／取消的 RC1 尝试。失败、取消和隔离反例由此次重跑的回归夹具覆盖。

| 证据类别 | 本次结果与边界 |
| --- | --- |
| 出版回归 | 43 isolation + 8 candidate + 15 products + 14 real preview + 13 reading + 6 full + 8 identity = **107 项**；退出码全 0，未出现 skip；不是 107 项 C++ 实验 |
| 文档结构／链接 | `c++/learning/check_docs.py`：38 份、962 本地链接、无错误；16 个分页风险仍保留。该工具历史 `pdf: NOT BUILT` 字段不描述本轮制品状态 |
| 全书结构／内容 | 13 章，953 fenced payload、1,714 anchors、30 labs／68 files；1,014 title spans、6,972 ordered units、896 inline literals、268 table relations，均按有界检查通过 |
| 导航 | 9,457 destinations、779 annotations；335 正文内部引用（含 79 跨章）按归属／目标／次数核对；14 顶层书签组 |
| 与旧候选比较 | 均为 407 页；destination 集合及正文目的地页码／坐标完全一致；不是所有像素一致性证明 |
| 渲染与视觉 | 407 页自动渲染，9 组 corpus `STRUCTURAL_PASS`；10 张 Poppler 代表页实际查看，另有 Preview 原生截图观察；没有逐页人工精读 |
| Reader | Preview 新字节实测＋Chromium 用户总体反馈；Acrobat/Safari/mobile 未测，不扩大支持矩阵 |
| 历史保护 | 对 Base 的 866 个范围外文件逐字节核对通过，`design/dist/` 完整文件集合相同；包括全部冻结正文、既有 PDF 和历史证据 |
| C++ / 性能 / 并发 | **NOT RUN**；未追写历史技术执行记录 |

[结构报告](candidate/derived/full-review/structure.json)、[身份与坐标比较](candidate/derived/identity-audit.json)、[语义 corpus](candidate/derived/reading-regression/page-map.json)、[人工视觉记录](visual-inspection.json) 均绑定新 PDF。54 张全书代表页被生成，不代表全部已查看；仓库仅导出实际查看的 10 张图。历史已接受的留白、少数折行、Gate 标签／章末节奏作为 known non-blocking limitations 保留，不声称本轮修复。

提交前另对本批三份维护说明运行 Pandoc GFM 解析及只读本地目标存在性检查：3 份文档、21 处链接通过；23 个新 profile／交付 JSON 可解析。未访问联网链接，也不把这些检查当作内容正确性或 reader 证据。`verify.py` 复核候选摘要、导出清单、输入身份、866 个保护文件与历史 `dist/` 集合通过。

## 执行与复核命令

以下从仓库根目录执行，Python 需满足 `publication/requirements.txt`。本机使用 bundled Python 3.12.14；Pandoc 3.11、LuaHBTeX 1.24.0 / TeX Live 2026、Poppler 26.05.0、pypdf 6.10.0；精确身份以 run/audit 为准。

```sh
python3 -B publication/engine/pub.py preview --profile cpp-handbook-rc1
python3 -B publication/reviews/full-handbook/audit-full.py <attempt>
python3 -B publication/tools/reading-review.py <attempt>
python3 -B publication/reviews/rc1/audit-identity.py <attempt>
python3 -B publication/reviews/rc1/check-delivery.py <new-check-output>
python3 -B publication/reviews/rc1/verify.py
```

实际 attempt：`publication/build/preview/d04e7b31cc325aa3fd8e8ef3081256ca5cc9aa0bed12ad03b000fccb279d2191/ce1afd089e084955a8b126f8c46ed270`。内部 Seatbelt 隔离始终启用。完成图片检查后运行本目录 `capture.py <attempt>`，沿用既有 candidate 机制冻结原字节，不重编译；该脚本是本轮一次性接收记录，拒绝覆盖已有导出，不是通用发布／自动资格判定入口。

[导出清单](candidate/export.json) 明列原候选导出项及未导出项；[派生清单](candidate/derived-export.json) 区分额外结构报告／页图与候选原 payload。本目录不是完整本地 build/candidate 副本，也不是正式 release 目录。

## 发布决策仍待授权

已固定出版名、版本与文件名；未来 release record 预留 `publication/releases/cpp-handbook/v1.0.0/`，tag 预留 `cpp-handbook-v1.0.0`，**本轮均未创建**。分发目的地、最终发布接受／执行授权仍需明确。`publish` 入口保持关闭。

`READY_FOR_RELEASE_DECISION` 只表示 RC1 已具备交付决策所需的本批证据，尚待集中审核和最终发布决定；不等于 `RELEASED`，也不授予修改正文／视觉基线或正式发布权限。
