# 系统设计与工程保证

本目录收录《优秀系统设计与工程保证标准》及其 PDF 出版工具。Markdown 是权威内容来源；文档关系以 [00 文档体系与规范关系](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md) 为准。

## 文档导航

| 编号 | 文档 | 阅读用途 |
| --- | --- | --- |
| 00 | [文档体系与规范关系](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md) | 规范地图、权威边界与阅读路径 |
| 01 | [优秀系统设计与工程保证方法论](01-优秀系统设计与工程保证方法论-v1.1.0.md) | 原则、术语、认识边界与架构推导 |
| 02 | [优秀系统设计：从约束、不变量到证据](02-优秀系统设计-从约束不变量到证据-v1.1.0.md) | Stage/Gate、模板、评审与工程案例 |
| 03 | [治理及符合性规范](03-系统设计与工程保证治理及符合性规范-v1.0.0.md) | 风险分级、角色、例外与符合性 |
| 04 | [论证、证据与裁决规范](04-工程保证论证证据与裁决规范-v1.0.0.md) | 保证论证、证据质量与裁决 |
| 05 | [生产就绪与运行韧性标准](05-生产就绪与运行韧性标准-v1.0.0.md) | SLO、发布、恢复与持续韧性 |

## 当前文档修订

六篇 Markdown 正在进行 `2.0.0-draft.1` 语义校准；仍处于待评审草案，尚未完成项目试运行。旧文件名暂作稳定入口，版本以正文元数据为准。批准、校准与试运行状态见 [00 §13](00-优秀系统设计与工程保证标准-文档体系与规范关系-v1.0.0.md)。

## 已发布 PDF

- [方法论卷 · v1.1.0](dist/01-优秀系统设计与工程保证方法论-v1.1.0.pdf)
- [工程参考卷 · v1.1.0](dist/02-优秀系统设计-从约束不变量到证据-v1.1.0.pdf)
- [构建清单](dist/build-manifest.json) · [SHA-256 校验和](dist/sha256sums.txt)

本轮不修改 PDF。以下 PDF 保留 v1.1.0 历史内容，不是当前 Markdown 草案的同步视图；后续正式发布需另行构建与验证。

PDF 统一保存在 `dist/`。发布版本不声明 PDF/UA 合规；字体替代记录见 [fonts.lock](fonts.lock)。

## 目录约定

| 路径 | 用途 |
| --- | --- |
| `00-…md` 至 `05-…md` | 权威文档 |
| [to-pdf.md](to-pdf.md) | PDF 出版设计与实现约束 |
| [publication/](publication/) | LaTeX 模板、主题、过滤器、图表与配置 |
| [scripts/](scripts/) | 构建、预检、渲染与比较工具 |
| [dist/](dist/) | 唯一受版本控制的 PDF 发布目录 |
| `build/` | 本地编译中间产物，可重新生成，已忽略 |
| `tmp/` | 本地渲染预览与缓存，可重新生成，已忽略 |

## 构建与检查

依赖 Pandoc、TeX Live / LuaLaTeX、latexmk、Poppler、Python 3，以及预检使用的 ripgrep 和 Perl。Python 检查与渲染依赖 `pypdf`、`pypdfium2`、Pillow；已验证的版本见 [package-lock.txt](package-lock.txt)、[texlive.profile](texlive.profile) 与 [fonts.lock](fonts.lock)。

从仓库根目录执行：

```sh
bash design/scripts/build.sh
bash design/scripts/preflight.sh
bash design/scripts/render-verify.sh
```

预检需要构建生成的 LaTeX 和日志，因此应先运行构建。渲染结果位于 `design/tmp/pdfs/`，用于人工检查版面。如检查依赖安装在独立 Python 环境中，可通过 `PYTHON_BIN` 指定其解释器路径。

比较两个版本的页面：

```sh
bash design/scripts/compare-renders.sh path/to/old.pdf path/to/new.pdf
```

比较发现差异时返回非零退出码，并列出有变化的页码。仅验证已发布文件的校验和时，在 `design/` 中执行 `sha256sum -c dist/sha256sums.txt`。
