# C++23 失败语义工程手册 · v1.0.0 候选载荷

**PUBLICATION_CANDIDATE — NOT RELEASED / PUBLISH NOT AUTHORIZED**。

本目录提前固定拟发布字节与身份，不表示已经发布。源稿 `45b305e` 已接受；本次 PDF 是独立出版证据，不升级 FM 技术验证范围。等待集中审核与最终 publish 授权。

- [正式身份候选 PDF](output/pdf/Modern-Cpp-Failure-Semantics-Handbook-v1.0.0.pdf) — 158 页。
- [SHA256SUMS](output/pdf/SHA256SUMS) — 校验 PDF、manifest 与 release notes。
- [Release manifest](output/pdf/release-manifest.json) — 来源、工具／执行身份、候选、支持范围与剩余 Gate。
- [Release notes](release-notes.md) — 内容范围与保留限制。
- [完整批次审核入口](../../../reviews/failure-model/README.md) — 实施边界、实际检查、失败尝试与视觉审阅。

PDF SHA-256：

```text
2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c
```

候选 ID：`d4ef80eb65a20e3048c9814b40b733bbb9c509c38303d19438ed9d422636d83d`。

```sh
cd publication/releases/cpp-failure-model/v1.0.0/output/pdf
shasum -a 256 -c SHA256SUMS
```

计划 tag：`cpp-failure-model-v1.0.0`，**尚未创建**。不在上传时重新编译，不覆盖同名历史字节。通用 `publish` 命令仍关闭。

## 随附证据

[候选清单](evidence/candidate-manifest.json)、[完成终态](evidence/candidate-result.json)、[预览审计](evidence/preview-audit.json)、[FM 专项审计](evidence/fm-review/audit.json)、[视觉观察](evidence/visual-inspection.json)、[阅读器记录](evidence/reader-evidence.json)、[历史技术证据身份](evidence/historical-technical-evidence.json)及[导出范围](evidence/export.json)相互独立，分别回答构建、内容对应、视觉和兼容性问题。

158 页均已渲染，摘要见[全页渲染清单](evidence/all-page-render-inventory.json)；仓库只导出 38 个代表页及其总览，不复制全部本地中间文件。该目录是**选定证据导出**，不是完整可离线重放的工具链包。

Reader qualification 有边界：Chrome 精确候选获用户“通过”反馈，版本及逐项结果未提供；Preview 11.0 实际打开与书签显示正常，后续交互因工具超时未完成。最终发布决策需保留或接受这些限制，不把它们改成全矩阵 PASS。
