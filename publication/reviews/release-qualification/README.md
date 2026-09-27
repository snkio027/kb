# Modern C++ Handbook · 发布准备

日期：2026-09-27。范围：接受登记、同一候选 PDF 的阅读器兼容性抽样、发布合同与资格核对。本批不生成、重命名或修改 PDF，不修改正文、构建系统、视觉规则和历史证据，不发布。

## 当前结论

**候选已接受；发布准备记录已形成；阅读器兼容性仅部分完成；正式发布尚不具备批准条件。**

| 对象 | 状态与证据身份 |
| --- | --- |
| Full Handbook Candidate `eb7f567` | 用户集中复审接受，`ACCEPTED FOR RELEASE PREPARATION` |
| Preview 11.0 / macOS 26.7 arm64 | `SMOKE_OBSERVED_NO_BLOCKER`，仅限已执行项目 |
| 跨阅读器兼容性 | `PARTIAL / NOT QUALIFIED`，不是全矩阵通过 |
| 发布合同 | `PROPOSED / DECISIONS PENDING`，见合同中的 D1–D3 |
| PDF、正文、引擎、视觉规则及历史制品 | `UNCHANGED` |
| 正式发布 | `NOT RELEASED / NOT AUTHORIZED`，publish 继续关闭 |

## 接受登记与固定对象

用户在本会话中对 `eb7f567` 的集中复审意见是接受全书 Publication Candidate，并接受已登记的非阻塞视觉限制；本轮“批准”授权阅读器测试及发布准备，不授权发布。本记录登记该意见，不冒充本轮重新执行其 GitHub 签名、CI 或独立技术核验。

| 绑定项 | 精确身份 |
| --- | --- |
| 本批 Base / 已接受候选提交 | `eb7f5672d1128607d4f34fa34217aefa9ba99b33` |
| Markdown 内容 | `8f479deaf660533b2ad82e1f721eb41a363112b6` |
| Visual Profile v1.0 实现 | `1c11c5940c05fe29c46c4500935d5efb673d46a7` |
| Visual Profile 接受登记 | `ea2e613b97ddd8a146c7899e7ffde7e80c238e57` |
| Candidate ID | `ecdca3ee3aa9654d60eef16fa99c324d6fec5a782a754761c14a07a4e33104b2` |
| PDF | [CPP-HANDBOOK-draft.pdf](../full-handbook/cpp-handbook-full/output/pdf/CPP-HANDBOOK-draft.pdf)，407 页，2,730,020 bytes |
| PDF SHA-256 | `80aabc252ef41eccb04a67504af1401e3f89211a43a1a89d761980143b225b26` |

[上一批交付记录](../full-handbook/README.md)和候选 JSON 中的“待审核”是生成时状态，保留原字节。99 项回归、407 页渲染、54 张代表页自查及 C++ 历史证据没有被追写成此次执行。候选已在 Git 审核包中可见，不等于创建了正式 release。

## 本批材料与实际检查

- [阅读器实测记录](reader-smoke.md)：实际动作、观察、未执行环境与后续复核卡。
- [发布合同草案](release-contract.md)：候选与正式版身份、拟定命名、版本与位置、发布 Gate。
- [候选校验清单](SHA256SUMS)：校验现有候选，不是正式 release manifest。
- [只读检查器](verify.py)与[本次机器检查结果](checks.json)：保护范围、文档结构、本地链接与历史交付证据核对。

从仓库根目录执行，Python 需具备已有 pypdf 依赖；Pandoc 仅解析 Markdown，不调用 PDF 编译：

```sh
shasum -a 256 -c publication/reviews/release-qualification/SHA256SUMS
python3 -B publication/reviews/full-handbook/verify-delivery.py
python3 -B publication/reviews/release-qualification/verify.py
git diff --check
```

本机实际 Python 为 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`。检查器退出 0 只表示所列机器检查通过，不能消除阅读器 `NOT RUN`、决定发布身份或授权 publish。本批没有重跑出版 99 项回归、C++ 编译／诊断、性能、并发动态检测、PDF 构建和全页渲染；没有新增 CI 证据。

## 停止点

提交并推送本批记录供集中审核后停止。浏览器安全限制不以临时服务器、替代控制面或安装扩展绕过；Adobe 未安装、移动设备未接入，不自动安装或借用其他设备。可以由用户在可用环境按复核卡补测，再提交绑定同一摘要的记录。

发布前必须明确 D1–D3，并另行给出最终文件、版本、目标位置和执行发布的授权。现有候选接受不因环境未测而撤销，但也不升级为阅读器兼容性或正式发布批准。
