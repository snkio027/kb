# Publication v2 · 集中审核记录

本批状态为 **IMPLEMENTED / REVIEW CANDIDATE**。ESD 七份与 C++ 三份均为 **PREVIEW_READY**；两个原字节候选为 **CANDIDATE_PREPARED_FOR_REVIEW / AWAITING_INDEPENDENT_REVIEW**。视觉 profile 为 **PILOT / NOT FROZEN**，正式发布仍关闭。

## 基线与架构迁移

实施起点为 `a2195d9557f1c4e86b7f64c290844c63493b2f18`。C++ 内容单独固定于 `8f479deaf660533b2ad82e1f721eb41a363112b6`，不能用实施 HEAD 替代。实际构建发生于提交前工作树；准备记录逐文件绑定实现、配置与源字节，不声称 PDF 已由最终提交 SHA 重建。

| 原活动链路 | v2 维护位置 | 分离结果 |
| --- | --- | --- |
| `design/scripts/pub.py` | [engine/pub.py](../../engine/pub.py)、[source_model.py](../../engine/source_model.py) | 仓库相对源与完整 Git revision；不再固定 `design/` 或六篇默认源 |
| `design/scripts/preview.py` | [engine/preview.py](../../engine/preview.py)、[links.py](../../engine/links.py) | 共享 AST、编译、执行身份、渲染；profile 提供元数据、视图与导航策略 |
| `preview.tex` / `preview-theme.sty` | [latex](../../latex/) + [profiles](../../profiles/) | 共享机械与产品模板/主题分离，不围绕旧静态模板做搬迁 |
| `filters/preview.lua` | [engine/filters/blocks.lua](../../engine/filters/blocks.lua) | 保留代码/记录续页、标题链；支持源 anchor alias 与声明式换页 |
| `preview_audit.py` | [engine/preview_audit.py](../../engine/preview_audit.py) | 通用内容/定位检查，前言/索引名称及策略由 profile 提供 |
| `candidate.py` | [engine/candidate.py](../../engine/candidate.py) | 通过 prepared source identity 绑定嵌套路径，不使用 basename 假设 |

Engine 不含 ESD/G6/G7 产品分支。两个 [profile.json](../../profiles/esd/profile.json) / [C++ profile](../../profiles/cpp-handbook/profile.json) 分别声明 source catalog、standalone/combined views、adapter、导航、元数据和审计策略。新增产品需要自己的可信 profile，不提供通用插件平台。

旧 `design/scripts/pub.py preview` 安全转发到 v2 ESD；旧内部 preview/candidate worker 拒绝直接运行；旧测试命令转发。六个早已关闭的危险写入入口继续拒绝，历史 `design/build/` 与 `design/dist/` 不迁移、不重写。旧 v1 attempt 不能被新候选命令冒充为 v2 验收记录。

准备与候选继续使用 no-follow 目录句柄、排他创建、独立 attempt、内容摘要，以及 `fsync pending → no-replace link` 终态提交点。Git clean/smudge/process filter 在状态探测前拒绝；真实编译使用 macOS Seatbelt 限定写入本次 `work/` 并禁用网络与 TeX shell escape。取消清理进程组，worker 监控父进程退出。提交后成功事实保留；这些机制不宣称电源故障下目录持久性或抵抗同账号恶意并发替换。

## 实际执行与结果

平台为 macOS 26.7 / arm64，Python 3.12.14，Pandoc 3.11，LuaHBTeX 1.24.0 / TeX Live 2026，Poppler 26.05.0，pypdf 6.10.0。工具文件摘要、pypdf 文件及实际 TeX/字体输入摘要均在两份 `preview-audit.json` 的 `execution_identity` 中。依赖按身份绑定，不随候选打包，未声称跨机器字节可重现。

本机使用的 Python：

```text
/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3
```

以下 `python3` 表示该解释器；从仓库根目录执行。真实构建需允许控制器启动 `sandbox-exec`，不是允许编译器任意写入。桌面外层沙箱第一次拒绝嵌套 Seatbelt（退出 71），确认原因后获准运行控制器；构建器自身隔离没有关闭。

```sh
python3 -B publication/engine/pub.py preview --profile esd
python3 -B publication/engine/pub.py preview --profile cpp-handbook
python3 -B publication/reviews/v2-pilot/check-delivery.py --output publication/reviews/v2-pilot/checks
```

最后一条是本轮实际证据采集命令；重跑时应使用新的输出目录，不覆盖已提交记录。其原始日志和逐文件保护结果见 [checks.json](checks/checks.json)。

| 证据类别 | 实际结果 | 能支持的结论 |
| --- | --- | --- |
| 隔离/终态测试 | [43 / 43](checks/test-publication-isolation.log) | filter、路径、漂移、失败、信号与提交边界的夹具回归 |
| 候选测试 | [8 / 8](checks/test-candidate.log) | 不覆盖、摘要变化、取消及提交失败语义 |
| 产品/来源测试 | [15 / 15](checks/test-products.log) | nested path、immutable revision、profile 身份/漂移、raw HTML、锚点与引用策略 |
| 编排及真实编译测试 | [12 / 12](checks/test-preview.log) | 7 个编排用例、5 个真实编译用例；信号用例含 INT/TERM/KILL 三个子场景 |
| C++ 文档静态检查 | [38 文件 / 962 链接，0 error](checks/check-docs.log) | 原有结构/本地链接检查；16 个分页风险仍属原稿提示 |
| 真实 ESD / C++ 构建 | 7 + 3，678 页均已渲染 | 自动保真、结构、元数据及导航合同；不是视觉批准 |
| 作者视觉自查 | 39 张 contact sheets + 18 个 144 dpi 页面 | 有明确查看范围的视觉观察，不是独立验收 |

78 是四组测试方法总数，不把信号子场景、此前调试重跑或十个真实产品再次计入。最终四组均没有 SKIP；日志中的本地执行结果不是 GitHub CI。C++ 编译/诊断实验、性能测量和并发动态检测均 **NOT RUN**，不改写历史技术证据。原文检查器打印的 `PDF NOT BUILT / NOT VALIDATED` 是它原有的静态报告字段，不是本批 Pilot 的执行结论；本批制品状态以独立预览终态为准。

批内修复包括：候选目录仍引用旧布局、AST walker 对无 `t` 的容器访问、测试夹具的字面 `\\n`、C++ 字体缺失 `↕` / `⇒`（在产品主题映射为对应数学字形），以及导出检查器误用审计字段名。上述失败均未作为成功交付；最终记录来自修正后的全套运行，不通过改正文或放宽失败判据获得通过。

## 来源、锚点与候选身份

G6 原始文件为 67,250 字节，SHA-256 `adcf479bb9e41ee6d87d2fcd94325c8399f142b1ae8221e21e0870a991105d66`；G7 为 61,629 字节，SHA-256 `c3f8d4376cffb9bbc196905eb82e703ac5943ae629a89bade72089f2ed534730`。完整路径、revision、仓库身份、准备/执行标识均保留在 [C++ run.json](cpp-handbook/run.json) 与 [候选 manifest](cpp-handbook/candidate-manifest.json)。

G6 的 124 个、G7 的 128 个稳定 HTML anchor 均作为同名 PDF destination alias 检查，其页和位置对应所属章节；合订版共检查 252 个。实验 `h-lab` / `h-file` 注释有明确非打印语义身份，未知 raw markup 拒绝，adapter 前后代码块文本必须一致。原始 Markdown 附件按字节保留，未修改 Gate。

合订版由两篇 AST 组成单一文档，页码连续；G7 从物理第 52 页开始。源引用分类如下（不是 PDF 所有链接注解的数量）：

| 视图 | 同视图内部引用 | 视图外源引用 | 外部网页 |
| --- | ---: | ---: | ---: |
| G6 | 19 | 16 | 1 |
| G7 | 22 | 18 | 6 |
| G6+G7 | 45 | 30 | 7 |

合订后四处跨篇源引用转为内部 destination；独立版依声明策略使用固定 commit 源 URL。视图外仓库路径/片段在对应 Git 对象中解析，未知目标失败；普通外部 URL 保留，不声称已联网检查可达性。

ESD 合订版重建了六篇结构及 160 个条款索引，检查打印页码与跳转目标；全套包含 567 个源表格行关系，独立版/合订版分别检查。保留 DRAFT 身份，不构成 ESD 新 release。

冻结命令形态：

```sh
python3 -B publication/engine/pub.py candidate --profile esd \
  --from-preview publication/build/preview/c77a687ad6e68a5e1333fefb8f1fbebd620896342cf7b0c5b062e242ccb2923a/47872f8a920f4136aeaf951eedb59621
python3 -B publication/engine/pub.py candidate --profile cpp-handbook \
  --from-preview publication/build/preview/86c2d36aad975289ff4e861d3c1cdf02e618d760f6d989db3c6e146bf78055fc/4e535fff21684093a71f334f4575184c
```

ESD candidate ID：`72ffc0398c7fa9726a7433630f4de89ec859c22c1268eedff9e0e0f9b495edfa`。C++ candidate ID：`dc7edf09e12ccec481b72b3b9e3386adadc81bf0d9607ae665c562e8e637dd31`。冻结没有重新编译。

[capture-review.py](capture-review.py) 实际核对了两个完整候选的文件摘要、声明视图与审计视图相等、Git 原字节/嵌套准备输入/候选 source 附件相等，尤其断言 C++ 仍来自指定 `8f479de`。随后以排他创建导出本目录的审核子集；[ESD export](esd/export.json) 与 [C++ export](cpp-handbook/export.json) 明列 included/omitted。这里不是完整候选副本：输入镜像、全部排版中间文件和 PNG 留在本地忽略的 `publication/build/`，不冒充已上传。原始候选 manifest 不为迎合导出范围而改写。

## 制品入口与摘要

[inventory.json](inventory.json) 是十份 PDF 的完整 SHA-256、页数、源身份与候选清单。下面均为审核副本，复制后未编辑 PDF。

| 产品 | 页数 | 阅读入口 |
| --- | ---: | --- |
| G6 | 50 | [内存与性能](cpp-handbook/output/pdf/G6-draft.pdf) |
| G7 | 48 | [并发与内存模型](cpp-handbook/output/pdf/G7-draft.pdf) |
| G6+G7 | 96 | [逻辑合订 Pilot](cpp-handbook/output/pdf/CPP-PILOT-G6-G7-draft.pdf) |
| ESD SUITE | 18 | [套系关系](esd/output/pdf/ESD-SUITE-000-draft.pdf) |
| ESD METHOD | 32 | [方法论](esd/output/pdf/ESD-METHOD-001-draft.pdf) |
| ESD REFERENCE | 63 | [工程参考](esd/output/pdf/ESD-REFERENCE-001-draft.pdf) |
| ESD GOV | 42 | [治理](esd/output/pdf/ESD-GOV-001-draft.pdf) |
| ESD ASSURANCE | 44 | [保证论证](esd/output/pdf/ESD-ASSURANCE-001-draft.pdf) |
| ESD OPS | 50 | [生产与运行](esd/output/pdf/ESD-OPS-001-draft.pdf) |
| ESD 合订 | 235 | [工程保证工作手册](esd/output/pdf/ESD-HANDBOOK-draft.pdf) |

自动检查原件：[ESD audit](esd/preview-audit.json)、[C++ audit](cpp-handbook/preview-audit.json)。单节内容、表格关系和引用映射保留在各 `evidence/typeset/` 中。READY 不等于零视觉缺陷；提取采用有边界的规范化/顺序匹配，不保证逐字形或每处代码缩进。

## 视觉自查与未验收项

全部 678 页以 72 dpi 渲染并通过 39 张 contact sheets 查看整体布局；另在 144 dpi 查看下列物理页。记录分别绑定制品摘要与 audit 摘要：[ESD 自查](esd/reading-review.json)、[C++ 自查](cpp-handbook/reading-review.json)。

| 范围 | 放大查看的页 |
| --- | --- |
| G6 | 2、40、41、44、47 |
| G7 | 20、37、38、44 |
| G6+G7 | 3、52 |
| ESD 六篇独立版（按 SUITE → OPS） | 6、11、18、12、20、45 |
| ESD 合订 | 231 |

在上述范围内未发现阻塞性的内容裁切、重叠或不可读缩放。长代码和记录续页保留身份，抽查矩阵、ASCII 流程、Gate 及答案可读。contact sheets 只支持整体排版观察，不能替代全部小字逐页精读；没有声称人工逐字读完 678 页。

保留的 Pilot findings：部分独立版目录续页较空；Gate 前的强制分页会产生留白；生成目录与冻结正文中的章内目录并存；正文历史 `NOT BUILT / NOT VALIDATED`、待审核文字保持原样，由生成控制页解释其历史身份。字体、配色、代码续页细节与最终分页节奏尚未冻结。这些事项没有通过删除源内容来规避。

没有执行 PDF/UA 认证、打印设备验证、Linux/CI 可移植性验证、外部网页可达性检查或独立视觉批准。没有启动全 G0～G12 构建或正式发布。

## 保护范围与停止点

`check-delivery.py` 对起点 135 个已跟踪文件中的 127 个非授权修改目标逐字节比较，结果全部不变；允许变动的只有 `design/README.md` 与七个兼容入口/测试文件，其余实现均新增于 `publication/`。因此 C++ 全部源稿、六篇 ESD 正文、历史 PDF、原始证据及旧出版配置均未修改。

另在 `design/` 实际执行 `shasum -a 256 -c dist/sha256sums.txt`，两份历史 PDF 均为 `OK`。未暂存变更阶段的 `git diff --check` 通过；完整暂存后检查报出原字节 ESD 附件自带的行尾空白，见 [原始诊断](checks/staged-whitespace.json)（以 JSON 字符串保留输出）。这些附件与原 Git blob 相同，不能为了空白检查改写。排除两个产品的不可变 `output/source/` 后，以下检查通过；未把完整暂存检查报告为 PASS：

```sh
git diff --cached --check -- . ':(exclude,glob)publication/reviews/v2-pilot/*/output/source/**'
```

源内容冻结和历史制品身份不因本批出版实现改变。

审核副本可以独立重复执行 `python3 -B publication/reviews/v2-pilot/verify-review.py`。它核对导出文件摘要、PDF 集合/页数、候选/源 revision 关系，以及 31 项当前实现输入绑定；并解析三份维护导航 Markdown、检查本地文件链接和 JSON。它不重建 PDF，不要求本地保留完整候选目录。有限凭据模式检查未发现匹配，但不将此描述为全面秘密扫描。

本批交付审核包后停止，不自动进入视觉 Profile Freeze、全系列 PDF 或正式 release。
