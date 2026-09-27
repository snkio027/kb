# Modern C++ 工程学习手册 · v1.0.0 发布记录

本目录保存用户于 2026-09-27 批准的正式版发布载荷。授权范围为：仅修正出版身份，完成新字节检查后直接发布到 `snkio027/kb` GitHub Releases，标签 `cpp-handbook-v1.0.0`，不再逐项申请批准。授权不包括正文／实验、视觉重设计或历史资产覆盖。

**打包不等于发布成功。** 对外状态以 [GitHub Release](https://github.com/snkio027/kb/releases/tag/cpp-handbook-v1.0.0) 和随后提交的 `publication-receipt.json` 为准。标签固定到已核对载荷的提交；发布后回执另行提交，不移动标签。

## 最终载荷

四个下载文件位于 [output/pdf](output/pdf/)：PDF、`release-manifest.json`、`RELEASE-NOTES.md`、`SHA256SUMS`。从该目录执行 `shasum -a 256 -c SHA256SUMS`；校验清单使用下载后的平面文件名，不依赖仓库路径。

```text
Publication  CPP-HANDBOOK / 1.0.0
Filename     Modern-Cpp-Engineering-Handbook-v1.0.0.pdf
Pages        407
SHA-256      ce4f6d5f6e4b8c1e2789eedd1fc151462d31e929b724ce2eb95c780f90766510
Base         2f4caf671bc42e6e3b03a8eda8255e1a392e5798
Content      8f479deaf660533b2ad82e1f721eb41a363112b6
Visual       1c11c5940c05fe29c46c4500935d5efb673d46a7
```

生成的 `PUBLICATION EDITION / PUBLICATION` 是出版身份，不是引擎自行授予发布批准。构建入口仍只准备预览／冻结字节，通用 `publish` 命令仍关闭；本次经明确授权用 GitHub CLI 分发经检查的精确载荷，不新增通用发布框架。冻结器原有 `DRAFT_READING_CANDIDATE_FOR_REVIEW` 等内部字段保留历史含义，外部 manifest 与发布回执单独表达授权和分发事实。

## 身份修正与实际尝试

`cpp-handbook-v1` 继承 RC1 的 13 个冻结来源、编排和视觉规则。仅更新封面、控制页、页脚、元数据及章首来源身份说明；表格、字号、边距、色阶、分页规则不变。共享引擎只允许新增中性 `PUBLICATION` 渲染身份，不允许 `RELEASED`，也不打开发布入口。精确差异由 `test-publication-identity.py` 验证。

本轮两次真实全书构建均为 `PREVIEW_READY`，不是失败／取消：

1. `dcc6498077057919a18c2167c834b10b2ef57bf9bf5bd69fd79e1c2314d9c21a/94050b6803064dd3865bb2fe13a261aa`：首轮生成身份调整，SHA-256 `3fb84ea43c2aa317cc65da2f0eb0b17f1997a0228ce528d0d58146d6db0a99d2`；代表页发现生成的来源说明仍称“阅读试件”，因此**不作为发布载荷**。
2. `8bbde993ed7cb74ad676ce2e34cc6ad1d7750491e8c0d7d9f9687307f6994fd4/c47b061ebbb54dc39bf08c90230b627d`：只在正式版主题中覆盖来源说明文字，再次完整构建；本目录绑定此最终字节。

二者均位于 `publication/build/preview/` 的独立目录，内部 Seatbelt 隔离启用。第一次的 [checks](checks/checks.json) 保持原样；[checks-final](checks-final/checks.json) 是最终 profile 的重跑记录，不把两轮合计宣传为更多不同用例。

## 检查口径

| 类别 | 本次结果与范围 |
| --- | --- |
| 出版回归 | 最终 112 项：43 isolation + 8 candidate + 15 products + 14 real preview + 13 reading + 6 full + 8 RC identity + 5 publication identity；未出现 SKIP |
| 文档检查 | 38 份 C++ 文档、962 本地链接，无错误；16 个已登记分页风险保留；不是技术正确性证明 |
| 内容／结构 | 13 章、953 fenced payload、1,714 anchors、30 labs／68 files、1,014 title spans；引擎另检查 6,972 ordered units、896 inline literals、268 table relations |
| 导航 | 9,457 destinations、779 annotations、335 正文内部引用（79 跨章）、14 顶层书签组；目标、点击区域及正文坐标与 RC1 一致 |
| 身份差异 | 元数据与每页生成身份检查；第 3–407 页提取文本除页脚／来源身份提示外一致；不声称像素完全相同 |
| 渲染／人工 | 全 407 页渲染，9 组 corpus 结构检查；实际代表页及发现见 `visual-inspection.json`，不把生成全部页图等同人工审阅 |
| 保护范围 | 相对 Base 的 934 个范围外文件逐字节一致，历史 `design/dist/` 完整集合相同；旧 RC1／旧 PDF／正文未修改 |
| Reader | 见 [reader-smoke.md](reader-smoke.md)，按具体字节与证据来源区分，未测项不填通过 |
| C++／性能／并发／CI | 本轮不执行、不追加历史技术结论；出版回归不能代替这些验证 |

全部为本地执行、自查及已注明的用户反馈。已接受留白、折行、少量标签位置和章末节奏仍保留，不声称修复。源章节历史 `PDF NOT BUILT` 等文字未改，不能当作当前制品状态。

## 可复核命令与证据

本机 CPython 3.12.14、macOS 26.7 arm64、Pandoc 3.11、LuaHBTeX 1.24.0 / TeX Live 2026、Poppler 26.05.0、pypdf 6.10.0。具体可执行文件、工具输入与摘要以 `evidence/run.json`、`evidence/preview-audit.json` 为准。

```sh
python3 -B publication/engine/pub.py preview --profile cpp-handbook-v1
python3 -B publication/reviews/full-handbook/audit-full.py <attempt>
python3 -B publication/tools/reading-review.py <attempt>
python3 -B publication/releases/cpp-handbook/v1.0.0/audit-identity.py <attempt>
python3 -B publication/releases/cpp-handbook/v1.0.0/check-delivery.py <new-output>
python3 -B publication/releases/cpp-handbook/v1.0.0/verify.py
python3 -B publication/releases/cpp-handbook/v1.0.0/verify.py <fresh-downloaded-assets-directory>
```

`assemble.py` 是此次一次性接收器：读取最终检查与人工记录，使用原冻结机制接收精确字节，排他创建新输出，拒绝覆盖，不执行编译或联网。`evidence/export.json` 明列导出及省略内容，不假装是完整 build。未导出的冻结源可由源提交取得，构建时读取的准确工作树输入摘要在 run 中，不以 Base 冒充新输入。

发布流程：提交并推送载荷 → 创建签名 tag → 创建含四个资产的 GitHub draft → 下载并核对全部字节 → 发布 draft → 再次下载、核对远端状态及 tag → 另行提交发布回执。没有在上传时重新编译、替换资产、移动 tag 或覆盖同名版本。
