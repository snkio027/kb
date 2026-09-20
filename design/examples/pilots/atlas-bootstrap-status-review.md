# Atlas 试点 01：Bootstrap 状态与 adoption 边界

> 非规范性、回顾性抽样记录。已执行两个 mock 契约测试；仅完成单评审者初评，未批准风险等级，未作生产放行或对象级符合性声明。

## 1. 对象与边界

| 字段 | 本次记录 |
| --- | --- |
| 记录 ID / 日期 | `ATLAS-PILOT-STATUS-001` / 2026-09-21（北京时间） |
| 项目 | [snkio027/atlas](https://github.com/snkio027/atlas) |
| 受评源提交 | [`aca4ff137a1d254cfeceaec24526e0699b585e92`](https://github.com/snkio027/atlas/commit/aca4ff137a1d254cfeceaec24526e0699b585e92)，定位时已核对远端 `main`；后续评审仍绑定此提交，不随分支移动 |
| 文档基线 | `kb@a67fb259d9a37bfcfc0c3b6b6418aeb06bd6aac2` / `2.0.0-draft.1` |
| 评估问题 | 状态是否区分已知不就绪与不可判定？健康输出是否被误当成控制权移交完成？ |
| 评估方式 | 仓库只读审阅；固定提交七个依赖文件的隔离导出；既有 mock 契约测试 |
| 执行 / 记录者 | Codex；不是具名 Owner、独立 Reviewer 或批准者 |
| 风险等级 / 批准者 | 待指定；本次只读活动不决定未来变更的生产风险等级 |
| 排除范围 | 真实集群、真实 API 故障、生产就绪、性能、恢复演练、adoption 实现及激活、完整规范符合性 |

本次没有修改 Atlas，没有执行真实 `apply`、恢复或凭据操作，也未运行全量质量门禁。两个脚本中的 Kubernetes/组件探测均由 fixture 或函数替身提供；子进程使用显式环境，不继承调用环境。

### 基线选择与现有改动

Atlas 本地 `HEAD` 为 `427e026b109c865e20c527a7d38b7e3c58c30747`，定位时落后已核对的远端提交 36 个提交，并有三处未提交改动：`bootstrap/argocd/handoff.sh`、`bootstrap/argocd/render.sh`、`clusters/kind/local-orbstack.yaml`。本次未拉取、重置或覆盖该工作树。

旧本地快照曾作过一次初探测试，但不纳入本记录的有效结果。下文全部执行证据来自 `aca4ff1` 的隔离导出；执行前逐文件核对 Git 对象摘要，执行后再次核对导出文件、原工作树状态和上述改动文件摘要。

## 2. 控制依据与有限主张

Atlas 的 [AGENTS.md](https://github.com/snkio027/atlas/blob/aca4ff137a1d254cfeceaec24526e0699b585e92/AGENTS.md) 规定架构高于实现和测试，并禁止单凭健康测试证明信任移交有效。[Bootstrap README](https://github.com/snkio027/atlas/blob/aca4ff137a1d254cfeceaec24526e0699b585e92/bootstrap/README.md) 区分观察性 `status`、检查性 `status --check` 与 adoption；[ADR-0002](https://github.com/snkio027/atlas/blob/aca4ff137a1d254cfeceaec24526e0699b585e92/docs/adr/0002-monotonic-bootstrap-adoption-proof.md) 定义 Receipt 创建为控制权移交线性化点。

以下均为初评，`SUPPORTED` 只覆盖表中明确限定的 fixture 和提交。

| 主张 ID | 可检验主张与覆盖 | 证据 / 初评 |
| --- | --- | --- |
| C-01 | 在既有 Argo 状态 fixture 中，READY 需要全部 Seed 控制面工作负载就绪；命名空间读取错误报告 UNAVAILABLE；健康输出不标为 adoption | E-01 / `SUPPORTED` |
| C-02 | 在既有 CLI fixture 中，`status --check` 对完整就绪报告返回 0，对已知不就绪返回 1，对不可判定或无效报告返回 2；混合已知异常与 UNAVAILABLE 返回 2 | E-02 / `SUPPORTED` |
| C-03 | 在既有 CLI fixture 中，观察性 `status` 保留零退出兼容行为且不隐藏漂移；集群缺失或不可判定时不探测 Argo；非法 `doctor --check` 不加载环境配置 | E-02 / `SUPPORTED` |

这些主张不声称覆盖全部输入、真实集群语义或端到端 adoption；fixture 测试与被测实现也不构成两种独立方法的交叉验证。

## 3. 执行证据

原始记录：[atlas-status-aca4ff1.json](evidence/atlas-status-aca4ff1.json)。包含执行时间、环境、源提交、七个依赖文件 SHA-256、完整标准输出/错误、退出码和隔离检查结果。它是本次抽样的原始执行记录，不宣称为完整 Evidence Bundle。

| 证据 | 既有脚本 | 执行结果 | 耗时 | 证据结论 |
| --- | --- | --- | --- | --- |
| E-01 | [status-contract.sh](https://github.com/snkio027/atlas/blob/aca4ff137a1d254cfeceaec24526e0699b585e92/tests/bootstrap/status-contract.sh) | `PASS`，退出码 0，2 条 PASS 摘要 | 42 ms | 对 C-01 为 `SUPPORTS` |
| E-02 | [status-exit-contract.sh](https://github.com/snkio027/atlas/blob/aca4ff137a1d254cfeceaec24526e0699b585e92/tests/bootstrap/status-exit-contract.sh) | `PASS`，退出码 0，5 条 PASS 摘要 | 1,022 ms | 对 C-02、C-03 为 `SUPPORTS` |

执行时间为北京时间 2026-09-21 02:18:51–02:18:52；JSON 保留 UTC 精确时间。PASS 摘要条数不等于独立测试用例数。耗时仅为两个命令的运行时间，不含准备、阅读、归档或人工评审。

证据在采集时对所声明快照为 `CURRENT`。源文件、Oracle、依赖、运行环境或主张范围变化时，须重新评估适用性并按需重跑；不得沿用为新提交或真实环境的支持证据。

### 复现方式

在有该提交的 Atlas 仓库中导出相同七个文件，避免混入未提交改动。下面只执行已审阅的 mock 脚本，不调用真实集群。

```bash
set -euo pipefail
pilot_dir=$(mktemp -d /private/tmp/atlas-status-review.XXXXXX)
git archive aca4ff137a1d254cfeceaec24526e0699b585e92 \
  tests/bootstrap/status-contract.sh \
  tests/bootstrap/status-exit-contract.sh \
  tests/lib/assert.sh \
  bootstrap/lib/runtime.sh \
  bootstrap/argocd/status.sh \
  bootstrap/atlas \
  bootstrap/status/report.sh | tar -x -C "$pilot_dir"
cd "$pilot_dir"
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  TMPDIR=/private/tmp/ LC_ALL=C \
  /opt/homebrew/bin/bash tests/bootstrap/status-contract.sh
env -i PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin \
  TMPDIR=/private/tmp/ LC_ALL=C \
  /opt/homebrew/bin/bash tests/bootstrap/status-exit-contract.sh
```

本次使用 macOS arm64、Bash 5.3.15，依赖系统命令与 Homebrew Bash；其他机器必须记录自己的环境，不能照抄本次环境或耗时作为新证据。导出后应按 JSON 中的 SHA-256 核对文件；若导出或摘要核对失败，停止执行，不产生有效 PASS 记录。

## 4. 判定边界与已知缺口

### CLI 退出码不是符合性状态

Atlas CLI 的 0/1/2 表达“完整就绪 / 已知不就绪 / 不可判定”，不可判定优先，是其检查命令的契约。它不能直接映射成 `CONFORMANT / NONCONFORMANT / UNKNOWN`。

[03 §10.2](../../03-系统设计与工程保证治理及符合性规范-v1.0.0.md) 汇总的是当前范围内全部适用义务：未获有效例外覆盖的强制义务已知不满足优先于未知；底层事实仍须完整保留。两个聚合器对象和用途不同，不要求共享枚举或优先级。

### adoption 缺口仍然存在

固定提交的 ADR-0002 明确记载：Identity v2、生产保护激活、Signal、Receipt 及 receipt-aware 普通 Bootstrap 路径尚未实现或启用，INV-02 运行时缺口仍开放。这是项目已登记的缺口，不是此次测试新发现或修复的问题。

本次测试只能支持健康输出与 adoption 概念不混用，不能支持“普通 Bootstrap 已实现单调退出控制”。不得以排除生产验证为由抹去这一已知反证，也不能把缺口改写成单纯未知。若后续符合性评估将该义务纳入适用范围，且确认未满足、没有有效例外覆盖，应按 §10.2 汇总为 `NONCONFORMANT`；是否允许受限动作另由有权主体决定。

### 本轮不作对象级符合性或 Gate 声明

本次仅抽样，不具备逐项适用义务清单、具名 Owner、独立评审及批准授权。没有形成对象级符合性结论或 Gate Decision；没有申请或批准 Exception。两个测试的 `PASS` 不自动补齐这些信息。

| 规范检查点 | 本次观察 | 待办 / 边界 |
| --- | --- | --- |
| GOV-REQ-009：风险等级有依据 | 识别到控制权与 Tier-0 边界；没有直接把 Atlas 定为 R2 | Owner 明确具体变更的后果、暴露、可逆性、关键未知及批准者 |
| ASSUR-REQ-005：无证据时保持未知 | 真实运行表现、独立评审一致性与人工成本均未验证 | 这些项保持未验证；不覆盖已知 adoption 缺口 |
| ASSUR-REQ-006：局部证据不推出端到端性质 | 三个主张限定于既有 fixture；未声称 adoption 成立 | 后续端到端 Claim 需要单独论证与证据 |
| ASSUR-REQ-026：状态不跨层偷换 | 分开记录执行、证据、Claim；区分 CLI 与符合性汇总 | 不据此授予 Gate GO 或正式符合性 |

此表是抽样记录，不替代 [03 §10.4](../../03-系统设计与工程保证治理及符合性规范-v1.0.0.md) 的逐 ID、逐子义务评估，也不将未列条款默认为不适用或已满足。

## 5. 试点反馈与下一步

| 试点问题 | 当前可报告结果 |
| --- | --- |
| 条款是否容易理解？ | 单评审者已完成一次试填；“执行状态 / 符合性 / Gate”的区分可落到真实代码，但不能代表团队普遍理解 |
| 状态能否一致判定？ | 尚未进行独立复评，不能报告一致率；优先复评混合异常、未知及既有 adoption 缺口的处理 |
| 证据收集成本是否合理？ | 已记录命令耗时；人工准备和评审成本未计量，不能据此认定成本低 |
| 有何实际教训？ | 本地与远端版本差异会导致证据错绑；应先固定对象，再执行和收集证据 |

下一步由 Atlas Owner 提名真实待评审变更及具名 Reviewer，确认风险等级和必要独立性；以本记录和原始证据进行独立复评，记录分歧与实际耗时。当前不需要为这一切片扩写六篇核心文档；更不代表其草案已获正式发布批准。
