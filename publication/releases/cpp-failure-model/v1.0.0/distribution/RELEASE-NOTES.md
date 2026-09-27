# C++23 失败语义工程手册 · v1.0.0

**Modern C++ Failure Semantics Handbook** · `CPP-FAILURE-MODEL / 1.0.0` · 158 页。

本次经用户明确授权，分发已完成检查的正式身份候选；不重新编译 PDF。发布是否完成以 [GitHub Release](https://github.com/snkio027/kb/releases/tag/cpp-failure-model-v1.0.0) 的公开状态及仓库发布回执为准。

## 内容与来源

正文包含全书阅读约定 `series-guide.md` 与 FM-0～FM-9。内容精确固定到 `45b305eace0f057420587d685cb3f962f3f0552c`，候选及出版证据位于 `4f8fe84a17429bc0a3b731461bfac5f0e1402cda`。沿用 KB Publication System v2 与 Visual Profile v1.0；本次发布没有改变正文、实验、Gate、模板或排版。

PDF SHA-256：

```text
2957aab0ad153873307a83af9383f08dabcfb3caae8c5f27750a6f48ee3c4e9c
```

下载 PDF、`release-manifest.json`、`RELEASE-NOTES.md` 和 `SHA256SUMS` 到同一目录后执行：

```sh
shasum -a 256 -c SHA256SUMS
```

`1.0.0` 是整书出版版本，不改变章节来源身份。仓库原 `output/pdf/` 内的候选 manifest、候选说明与校验和仍是历史候选记录；本次下载随附的是 `distribution/` 中的授权分发元数据，PDF 字节完全相同。

## 检查与限制

候选阶段已有 121 项本地出版回归，158 页全页渲染及 38 个代表页视觉自查。11 份冻结源稿、527 个 fenced payload、189 个显式锚点及 146 处正文内部链接按随附证据核验。发布阶段仅重新核对字节、元数据、保护范围及下载结果，不把这些历史检查改写为重新执行。

- Chrome：用户对当前精确摘要 smoke card 回报“通过”；版本、OS 和逐项观察未提供。
- Preview 11.0 / macOS 26.7：打开、封面与书签树已观察，后续交互未完成。其他阅读器未测。
- 既有短尾留白、模板跨页、少数软折行限制保留，不声称版式无瑕疵。
- C++ 编译、性能、TSan／并发动态检测、完整协程、ABI 和分布式故障实验未因发布而重跑或验收；FM-5 等原有覆盖限制保持。
- 不声明 GitHub CI、PDF/UA、跨平台认证或跨机器字节级可复现。章节中历史证据状态不等于当前制品发布状态。

同版本资产及 tag 按项目政策不替换、不移动；需要修订时发布新版本。不把项目政策表述为 GitHub 服务端强制不可变。
