# C++23 失败语义工程手册 · v1.0.0 发布记录

**RELEASED — 2026-09-27**。[GitHub Release](https://github.com/snkio027/kb/releases/tag/cpp-failure-model-v1.0.0) 已公开，四个资产在公开前后均完整下载回验，见[发布回执](publication-receipt.json)。用户对 `4f8fe84` 候选明确回复“批准发布”，见[授权记录](authorization.json)。本次只分发既有字节，没有重新编译。

源稿 `45b305e` 已接受；本次 PDF 是独立出版证据，不升级 FM 技术验证范围。`output/pdf/`、`evidence/` 和原候选说明继续保持 `4f8fe84` 的历史字节，内部 `PUBLICATION_CANDIDATE / NOT RELEASED` 字段不会被追写为发布事实。

- [正式 PDF 的仓库原字节](output/pdf/Modern-Cpp-Failure-Semantics-Handbook-v1.0.0.pdf) — 158 页，与候选完全相同。
- [发布 SHA256SUMS](distribution/SHA256SUMS) — 校验下载后的 PDF、manifest 与 release notes。
- [发布 manifest](distribution/release-manifest.json) — 来源、候选绑定、授权与支持范围；不是上传回执。
- [发布 notes](distribution/RELEASE-NOTES.md) — 内容范围与保留限制。
- [历史候选 manifest](output/pdf/release-manifest.json)和[历史候选说明](release-notes.md) — 不用于本次正式下载的元数据。
- [完整批次审核入口](../../../reviews/failure-model/README.md) — 实施边界、实际检查、失败尝试与视觉审阅。

PDF SHA-256：

```text
2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c
```

候选 ID：`d4ef80eb65a20e3048c9814b40b733bbb9c509c38303d19438ed9d422636d83d`。

```sh
# 下载四个发布文件到同一个新目录后，在该目录执行。
shasum -a 256 -c SHA256SUMS
```

签名 tag：`cpp-failure-model-v1.0.0`，固定于载荷提交 `d5629f05d00fd902c0462de181b3e359c4270cc1`。已完成草稿上传、下载回验、公开发布及第二次下载回验；回执另行提交，不移动 tag、不覆盖同名历史字节。通用 `publish` 命令仍关闭；本次经明确授权使用 GitHub CLI 分发。

发布阶段重新核对了 1,118 个受保护既有文件、完整历史 `design/dist/` 集合和旧 G 手册 Release 的四个资产身份，均未变。GitHub `isImmutable=false`；不替换资产／不移动 tag 是项目政策，不声称服务端强制不可变。下载回验使用已认证 CLI，不冒充匿名会话测试。

四个资产的仓库来源：PDF 保留于 `output/pdf/`，其余三个同名发布文件取自 `distribution/`。不从两个目录使用混合通配符上传，避免误用历史候选元数据。`distribution/` 不重复存储 PDF。本地及下载目录可分别核验：

```sh
python3 -B publication/releases/cpp-failure-model/v1.0.0/verify-release.py
python3 -B publication/releases/cpp-failure-model/v1.0.0/verify-release.py <新下载目录>
```

该只读核验器校验四个资产、授权／候选绑定、`4f8fe84` 全部既有文件（仅两份当前导航 README 可变）及历史 `design/dist/` 文件集合。候选阶段 121 项回归不在发布阶段重跑；原 `verify-delivery.py` 的 `NOT RELEASED` 输出仍描述不可变的候选包，不是查询线上发布状态。

## 随附证据

[候选清单](evidence/candidate-manifest.json)、[完成终态](evidence/candidate-result.json)、[预览审计](evidence/preview-audit.json)、[FM 专项审计](evidence/fm-review/audit.json)、[视觉观察](evidence/visual-inspection.json)、[阅读器记录](evidence/reader-evidence.json)、[历史技术证据身份](evidence/historical-technical-evidence.json)及[导出范围](evidence/export.json)相互独立，分别回答构建、内容对应、视觉和兼容性问题。

158 页均已渲染，摘要见[全页渲染清单](evidence/all-page-render-inventory.json)；仓库只导出 38 个代表页及其总览，不复制全部本地中间文件。该目录是**选定证据导出**，不是完整可离线重放的工具链包。

Reader qualification 有边界：Chrome 精确候选获用户“通过”反馈，版本及逐项结果未提供；Preview 11.0 实际打开与书签显示正常，后续交互因工具超时未完成。用户在这些限制已披露后批准发布；保留原始观察，不把批准改写为全矩阵 PASS。
