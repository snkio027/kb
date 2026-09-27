# C++23 失败语义工程手册 · Publication v1.0.0

English title: **Modern C++ Failure Semantics Handbook**。Publication ID：`CPP-FAILURE-MODEL`。

状态：**PUBLICATION_CANDIDATE / NOT RELEASED**。正式阅读版身份不等于已获公开发布批准；当前未创建 tag 或 GitHub Release。

## 内容与版本

读者正文为 `series-guide.md` 和 FM-0～FM-9，共 158 页。11 份源文件逐字节固定到 `45b305eace0f057420587d685cb3f962f3f0552c`；来源审查已关闭，不重排章节、不改正文、实验、审查清单或模板。`1.0.0` 是整书出版版本；各篇的 `source@45b305e` 是源快照身份，不是新设的章节 SemVer。

源仓库 README 和 review 记录不进入正文。代码块内的 Markdown 模板按原样保留，不能理解为已填写的项目合同。五个正文 `fm-test` 标记生成实验身份；`sample.cpp` 是单代码块的出版文件标签，不是原稿新增文件名。

## 出版检查

沿用 Publication System v2 和冻结 Visual Profile v1.0：11 份原稿、527 个 fenced payload（含 215 个 C++ 块）、189 个显式 HTML 锚点、383 个标题定位以及正文链接保真已按随附记录核验。全文已渲染；38 个代表页总览与八个语义重点页详查未发现出版 blocker。

Preview 11.0 / macOS 26.7 实际打开与目录显示正常，但后续 UI 查询超时，未完成其全部交互卡。用户对精确摘要候选的 Chrome smoke card 回复“通过”；Chrome/OS 版本及逐项结果未提供。其他阅读器未测，不宣称跨平台兼容性认证。

## 保留限制

- 性能、并发动态检测／TSan、完整协程、ABI 兼容和分布式故障实验未因本次出版而执行或验收。
- FM-5 throwing-move 注入矩阵、分配失败等原有覆盖限制原样保留。历史 C++ 结果未重写成新执行证据。
- 第 158 页收尾留白、长模板跨页及少数代码软折行属于冻结视觉规则的非阻塞限制；没有重新设计版式。
- PDF 搜索／抽取检查使用已声明的规范化规则，不证明全部缩进、无障碍或任意阅读器行为。无 PDF/UA、CI 或跨机器字节级可复现声明。

## 最终发布 Gate

候选字节、校验和、支持范围与证据已固定；等待集中审核与最终 publish 授权。拟定 tag 为 `cpp-failure-model-v1.0.0`。正式发布只分发已接受的候选字节，不在上传时重新编译；同名不同内容不得覆盖。
