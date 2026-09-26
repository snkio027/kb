# 技术知识库

系统设计、平台架构与系统编程的技术文档，包含 Markdown 正文及配套 PDF。

## 阅读入口

| 主题 | 内容 | 入口 |
| --- | --- | --- |
| 系统设计与工程保证 | 方法论、工程手册、治理、证据与运行韧性 | [文档导航与 PDF](design/README.md) |
| Atlas 平台架构 | 平台总体架构、GitOps 控制面与 AI Agent 控制面 | [总体架构](<atlas/Atlas Architecture Design.md>) · [GitOps](<atlas/Atlas GitOps Control Plane Design.md>) · [AI 控制面](<atlas/AI-Native Platform Control Plane Architecture Standard.md>) |
| C++ 学习手册 | G0～G12 系统编程主线与 FM 失败模型专题 | [学习导航](c++/README.md) · [失败模型](c++/failure-model/README.md) |
| Zig 项目架构 | 源码组织、模块边界、包生命周期与构建图 | [架构标准](<zig/Zig Project Architecture Standard.md>) |

## PDF 与目录约定

- [design/dist/](design/dist/)：双卷 PDF、构建清单和 SHA-256 校验和。
- [atlas/pdf_build/](atlas/pdf_build/)、[c++/pdf_build/](c++/pdf_build/) 与 [zig/pdf_build/](zig/pdf_build/)：各主题已有的 PDF 及配套 LaTeX 源文件。
- Markdown 保留各文档的版本、适用范围与工程约束；PDF 用于阅读与分享。
- 编译中间文件、渲染预览、系统元数据及本地环境不纳入版本控制。`design/` 的构建方式见其[说明](design/README.md#构建与检查)。
