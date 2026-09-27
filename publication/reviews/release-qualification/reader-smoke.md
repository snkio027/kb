# Reader Compatibility · 同字节候选实测

状态：**PARTIAL / NOT QUALIFIED**。2026-09-27，本机 macOS 26.7（25G229）/ arm64。对象为 [407 页候选](../full-handbook/cpp-handbook-full/output/pdf/CPP-HANDBOOK-draft.pdf)，SHA-256 `80aabc252ef41eccb04a67504af1401e3f89211a43a1a89d761980143b225b26`，测试前后均核对。没有重新导出或生成另一份 PDF。

## 方法与证据等级

通过原生 UI 操作 Preview，查看实际阅读器截图，并读取 accessibility tree 核对当前页、目标标题、搜索和选中文本。不是用 Poppler 渲染替代阅读器。截图与 UI 原始返回保留在本次会话工具记录中；本目录保存人工整理的执行记录，**没有另行归档截图，也不是可独立重放的 UI 自动化测试套件**。

应用版本来自本机应用包 `Info.plist`，不是网络查询：Preview 11.0、Google Chrome 153.0.8010.53、Safari 27.0。发现应用已安装不等于完成该阅读器测试。

## 环境矩阵

| 阅读环境 | 实际状态 | 范围或原因 |
| --- | --- | --- |
| macOS Preview 11.0 | `SMOKE_OBSERVED_NO_BLOCKER` | 打开、书签、目录点击、正文跨章跳转、指定页、中文复制与搜索、标识符搜索、代表页渲染 |
| Chromium PDF viewer / Chrome 153.0.8010.53 | `NOT RUN / TOOL_POLICY_BLOCKED` | 打开本地 `file:` PDF 请求被浏览器工具安全策略拒绝；没有进入 PDF viewer，不能评价兼容性 |
| Safari PDF viewer / Safari 27.0 | `NOT RUN / NOT ATTEMPTED` | Safari 已安装；不切换浏览器控制面重试被禁止的本地浏览器打开操作，不声称 Safari 自身报错 |
| Adobe Acrobat Reader | `NOT RUN / NOT AVAILABLE` | 应用清单及 `/Applications` 未发现 Reader；未安装，未验证其他安装位置或虚拟机 |
| iPad / iPhone | `NOT RUN / OPTIONAL` | 无接入设备；不是 iOS 兼容性结论 |

浏览器工具返回：`The requested URL protocol is not allowed. Allowed protocols: "http:", "https:".` 并明确禁止通过间接执行、替代浏览器控制面等达成同一被拒绝操作。因此没有启动 HTTP 服务、改变安全设置、上传文件或用其他入口规避。**这是测试环境限制，不是 PDF 打不开的制品缺陷；也不能计为 PASS。**

## Preview 动作与结果

原有 Preview 窗口已打开此仓库候选，窗口 URL 与登记路径一致，起始页 294/407。全程未使用保存、标注或编辑功能。

| ID | 实际操作 | 可见结果与边界 |
| --- | --- | --- |
| P01 | 前往第 1 页，查看封面 | 中文书名、`CPP-HANDBOOK`、`vcandidate.1`、`PREVIEW / DRAFT` 可见；没有缺字或遮挡 |
| P02 | 显示文档目录侧栏，点击 G0 书签 | 阅读说明及 G0–G12 章组可见；落到 12/407，标题为 G0 原生工具链与机器边界；未逐个展开全部层级 |
| P03 | 点击 G0 正文“下一章：G1” | 从 12/407 跳到 20/407，G1 对象模型与生命周期；不是用目录点击替代正文链接测试 |
| P04 | 查找 `CMakeUserPresets.json` | 在 1 页中找到，结果页 316/407；正文显示完整标识符 |
| P05 | 在 G0 正文三击选中下述中文句，复制，再粘入查找框 | 查找框与复制内容一致，在第 12 页找到 1 个匹配；只验证此句，不承诺任意代码复制保真 |
| P06 | 前往第 3 页，点击页面目录中的 G0 | 落到 12/407，标题与目标一致；另一个 G1 实验条目的自动点击返回 offscreen，未把该尝试计为有效导航证据 |
| P07 | 前往固定语义页，实际查看 8 幅阅读器画面 | 覆盖下表 15 个物理页；未见缺字、严重裁切、重叠或危险身份消失，保留已接受留白／折行 |

P05 复制并回读的原句：

> 本章围绕一个问题：为什么一份源码能编译成目标文件，却不能链接成程序？

部分 Preview AX 链接标为 disabled，其 `press on the link` 动作没有导航；改用普通 click 后 P03/P06 成功。记录以最终可见落页为准，不把发出动作本身当成成功。

### 实际视觉样本

| 语义样本 | 实际截图中的物理页 | 观察 |
| --- | --- | --- |
| cover / identity | 1 | 中英文、预览状态和版本可读 |
| control / TOC | 2–3 | 控制信息、目录字形与页码无明显缺损 |
| G6 experiment continuation | 234–235 | G6-M1 续页及 G6-M2 起始代码、实验身份可辨 |
| G7 danger / continuation | 278–279 | G7-D2 续页保留实验与文件；G7-D3 警示、编号和代码同页可见 |
| G8 inline identifiers | 294–295 | `requested_version` 在下划线后折行，`extern "C"` 可读；没有将可接受折行重新列为 blocker |
| G9 inline identifiers | 316–317 | `CMakeUserPresets.json` 完整可读，正文及代码未明显裁切 |
| G12 Final Gate | 402–403 | 全书回查与 Gate 问题可读，表格与题目无明显错位 |
| last page | 406–407 | 参考答案和参考资料完整可见；保留末页留白 |

未做：Preview 外链打开、专项缩放矩阵、任意多行代码复制／重新编译、所有书签／779 链接逐个点击、全页精读、屏幕阅读器、打印、PDF/UA、其他 OS 实测。G0/G1 落页与搜索另有 AX 观察，不把它们算入以上 15 页截图数。结束时返回原阅读页 294，未保存 PDF。

## 补测卡与关闭条件

后续每个阅读器使用同一 SHA-256 的本地文件，先记录 OS／应用精确版本，再按 P01–P07 复核；不能用换过字节的新 PDF 继承本表结果。对浏览器另补外链行为，对 Safari 补一次缩放检查；复制至少包含上述中文句与一个技术标识符。记录动作、来源页、目标标题／页、实际结果、截图或可复核观察及限制。

只有打不开、缺字、可重复的错误／失效内部跳转、无法使用的大纲、根本性搜索／提取失败、严重裁切等才作为 release blocker。普通抗锯齿、hinting、留白或滚动差异不重开版式设计。

桌面矩阵仍按 Preview、Acrobat Reader、Chromium、Safari 待完成，移动端可选。若决定缩小支持矩阵，需要用户明确接受未测风险并登记支持范围；执行方不把 `NOT RUN` 自动豁免。当前整体 Reader Compatibility Gate 保持未关闭。
