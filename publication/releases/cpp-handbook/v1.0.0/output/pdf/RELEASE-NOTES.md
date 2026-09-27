# Modern C++ 工程学习手册 v1.0.0

Modern C++ Engineering Handbook 的首个正式出版版本，包含 G0–G12，共 407 页。

本版只将已接受 RC1 的生成身份调整为正式阅读版：封面、控制页、页脚、元数据及来源状态提示。正文、实验源码、章节版本、排版规则、历史候选与历史 PDF 均未改写。

## 下载与校验

请下载 `Modern-Cpp-Engineering-Handbook-v1.0.0.pdf`、`release-manifest.json`、`RELEASE-NOTES.md` 和 `SHA256SUMS`，放在同一目录，执行：

```sh
shasum -a 256 -c SHA256SUMS
```

最终 PDF SHA-256：

```text
ce4f6d5f6e4b8c1e2789eedd1fc151462d31e929b724ce2eb95c780f90766510
```

在 Windows 可用 `Get-FileHash -Algorithm SHA256 Modern-Cpp-Engineering-Handbook-v1.0.0.pdf` 核对。摘要证明下载字节一致，不代表全书技术正确性或跨平台认证。

## 版本绑定

- 出版 ID／版本：`CPP-HANDBOOK / 1.0.0`。
- Markdown 内容：`8f479deaf660533b2ad82e1f721eb41a363112b6`。
- Visual Profile v1.0：`1c11c5940c05fe29c46c4500935d5efb673d46a7`；接受登记 `ea2e613b97ddd8a146c7899e7ffde7e80c238e57`。
- 已接受 RC1：`2f4caf671bc42e6e3b03a8eda8255e1a392e5798`。本版是新字节，不沿用 RC1 摘要。
- 发布标签：`cpp-handbook-v1.0.0`。精确构建输入、执行身份及冻结载荷 ID 见随附 manifest 和仓库发布记录。

## 本次验证与限制

全书结构、源内容对应、书签和正文引用经过本地检查，407 页完成渲染；人工检查仅覆盖代表页，不是逐页精读。与 RC1 对比，书签树、链接目标和点击区域、正文导航坐标保持一致；正文提取文本仅排除生成的出版身份差异。出版回归与 C++ 实验是不同证据，本轮未重跑 C++、性能或并发实验，也不宣称 CI 通过。

阅读器证据的具体文件摘要、范围及未测项见仓库 `reader-smoke.md`；旧 RC1 的 Preview／Chrome 结果不自动等于最终 PDF 重新实测。正式 PDF 的源章节仍保留冻结时的历史状态文字，章首说明已明确它们不是当前出版状态。

保留已接受的非阻塞视觉限制：局部目录／Gate 留白、个别标签位置、长代码软折行及章节收尾节奏。没有可访问性认证、硬实时保证或全平台验证声明。

本版资产不原位替换；后续任何 PDF 字节变化须使用新候选、新摘要和新出版版本。
