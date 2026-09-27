# FM 系列整理：结构、语义与证据记录

状态：**ACCEPTED — FM Series Review @ `9c48ce0`**；两项非阻断精度修正已补齐并提交核对。日期：2026-09-27。返回 [FM 总导航](../README.md)。

下列 §1–5 保留原交付时的记录口径，所述“本批”“当前输入”均绑定 `9c48ce0`，不改写为本次重新执行；最新接受与修正见 [§6](#6-系列接受与精度修正收口)。

本批把现有 FM-0～FM-9 整理为 C++23 失败语义工程手册，不新增主题卷，不等同全系列技术验收完成。修改前基线为 `3c6dce94144213e77be98508cceb9c2631113ad6`；新正文由承载本记录的提交保存，本文件不回写自己的最终摘要。

## 1. 范围与信息架构

统一主线为：操作与合同 → 失败检测／表示／传播 → 状态及提交 → 恢复权限与影响范围 → 验证证据。文件名和原 § 编号保留；新增主题分组组织阅读。README 提供首次学习、工程设计、故障速查三条路径；[系列阅读约定](../series-guide.md)集中维护术语、主讲位置与公共 C1–C8 审查问题。

| 章节 | 主讲职责及本轮整理 | 顶层阅读组织 |
| --- | --- | --- |
| FM-0 | 总模型；合并 API review、logging、retry 等重复定义，以精确链接回查主讲章 | 九个主题分组 |
| FM-1 | 前置／后置条件、验证、断言与 UB；区分合法失败和违约后果 | 六个主题分组 |
| FM-2 | 值结果、错误类型、组合条件与所有权返还 | 四个主题分组 |
| FM-3 | 异常对象、传播、匹配与实际展开；保留终止路径限制 | 四个主题分组 |
| FM-4 | 状态保证与 prepare–commit–cleanup；以条件化状态表串联机制 | 四个主题分组 |
| FM-5 | `noexcept`、move/copy、traits、容器条件和泛型组合 | 五个主题分组 |
| FM-6 | 构造、分配、显式完成与清理责任 | 四个主题分组 |
| FM-7 | 原生错误身份、领域转换和上下文 | 三个主题分组 |
| FM-8 | 执行／观察边界、控制状态、重试与恢复协议 | 五个主题分组 |
| FM-9 | 待项目采纳的政策；唯一可填写 API 合同模板与验证设计 | 六个主题分组及最终总图 |

H1 是书名式章标题，H2 是主题分组，原编号小节为 H3；原 H3 子题改为就地加粗标签并保留显式锚点。十篇正文的 442 个旧定位目标全部仍可解析。FM-0 §46/47 合并的审查细项锚点保留在原节，由统一合同承接；因此“保留链接”不意味着重复段落原样保留。

移除装饰横线，将单行 `text` 标签转为行内表示，收拢相邻短段；多行流程、C++ 源码和必要表格保留。H2 数量从 304 降至 71（包括阅读入口／目录），这只是层级盘点，不是质量评分或知识点删减指标。

没有为视觉统一重写全部段落，也没有把长实验拆成无法运行的碎片。FM 采用本次系列约定；未修改、也不声称自动继承 G 系列的完整 Editorial Profile 验收。

## 2. 语义审计与差异处置

以下是对既有主题的缩紧、区分与必要补条件，不是新机制清单。标准规则与工程建议分别标识；涉及状态的示意表是推理，不伪装成已执行实验。

| 问题 | 处置与主讲位置 | 保留的限制 |
| --- | --- | --- |
| Failure / error / exception 混用 | FM-0 §2–3 与阅读约定区分失败、错误状态、错误表示和传播 | 不抹去 fault → error state → failure 的历史语境 |
| 正常返回被当成成功 | FM-1 §3、FM-2 §0–1 区分成功、合法 absence 和错误值 | `false` 的含义取决于接口合同 |
| 违约、UB、终止被视为同一结果 | FM-1 §6、§48 区分责任与具体语言／接口后果 | validation 不能证明全部生命周期和同步条件 |
| Debug/Release 被当成 `assert` 开关 | FM-1 §13/§25 与 FM-9 §12 以 `NDEBUG` 为准 | 部署配置与语言规则分开；断言表达式仍须定义良好 |
| checked 必然更慢的暗示 | FM-1 §28 不把有检查等同于固定额外开销 | 不新增 benchmark 或性能结论 |
| 保证语言混轴 | FM-0 §29–33、FM-4 §4、FM-9 总图统一状态、传播、处置三条轴 | `noexcept` 不自动提供 no-fail、strong 或恢复 |
| RAII 被泛化到所有退出 | FM-3 §5、FM-4 §1–3/§19、FM-0 §39 限定正常退出和实际展开 | 终止不保证完整析构，清理不等于业务回滚 |
| 有 swap 就声称事务成立 | FM-4 §5–7 给出 S0–S3 的状态、前提与提交后报告语义 | 无故障注入实现；不推出文件／数据库持久化承诺 |
| no-throw 与泛型条件 | FM-5 §13/§16 区分提交可完成、隐式析构异常规格与元素操作 | 保留原容器、trait、表达式边界及 T17 判据 |
| nothrow 分配／Rule of Zero 过度外推 | FM-6 §8/§14 补标准分配形式、初始化与跨成员不变量条件 | 不验证 class-specific allocator 或所有移出状态 |
| 错误身份丢失 | FM-7 §6 保留 category 与等价条件映射的职责 | 不把整数相同当成跨错误域相同 |
| 报告动作似乎永不失败 | FM-3 §7、FM-8 §4 说明日志、`set_exception` 的自身失败 | promise 片段不是完整 thread-entry 隔离实现 |
| 协程异常覆盖过宽 | FM-8 §7 区分函数体路径与帧／参数／promise 建立 | 不增加 task runtime，也未执行协程失败矩阵 |
| 超时／重试隐含“未提交” | FM-0 §55–56、FM-8 §10/§17–19 分离观察、停止请求、提交与去重前提 | key/ID 本身不是幂等证明；补偿不等于抹去历史 |
| `nodiscard` 被当成强制错误检查 | FM-9 §25 标明建议诊断与工程告警政策 | 不保证拒绝编译或实际处理结果 |

附件中的“`noexcept` 内部 throw 就终止”“RAII 覆盖任意退出并执行恢复”“commit 前天然保持旧状态”等概括未直接照抄。维护稿分别保留内部捕获、实际展开和隔离准备的条件，避免整理反而削弱此前修订。

主讲位置与重复治理采取“简短提醒＋精确回链”，不机械删除安全边界。FM-0 保留总体模型，FM-4 定义状态保证，FM-8 定义跨边界恢复协议，FM-9 提供项目选择与可填写合同。其他章节末尾的 checklist 是公共 C1–C8 之上的机制回查，允许必要的局部重复。

## 3. 条款依据与推理边界

继续采用 C++23 最终草案 N4950；原先注明的 LWG 3843 及历史实现差异不变。本轮定向读取下列条款，不声称对所有外链、全部标准修订或每个正文命题做了独立验证：

- [异常规格](https://timsong-cpp.github.io/cppwp/n4950/except.spec)：非抛出边界与隐式异常规格。
- [终止与展开](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)：不能依赖全部终止路径执行完整展开。
- [构造与析构中的异常](https://timsong-cpp.github.io/cppwp/n4950/except.ctor)：已完成子对象及委托构造边界。
- [程序终止设施](https://timsong-cpp.github.io/cppwp/n4950/support.start.term)：不把终止与正常作用域退出混同。
- [new-expression](https://timsong-cpp.github.io/cppwp/n4950/expr.new)：分配与初始化是不同阶段。
- [promise](https://timsong-cpp.github.io/cppwp/n4950/futures.promise)：共享状态和报告操作的前提／错误。
- [协程变换](https://timsong-cpp.github.io/cppwp/n4950/dcl.fct.def.coroutine)：建立阶段与函数体异常处理的范围。
- [nodiscard](https://timsong-cpp.github.io/cppwp/n4950/dcl.attr.nodiscard)：推荐诊断不等于强制处理。
- [诊断库中的 error category 与条件映射](https://timsong-cpp.github.io/cppwp/n4950/diagnostics#syserr.errcat.derived)：错误码身份和跨域等价关系不是只比较整数。

状态表、数组填充合同、跨边界恢复和去重条件属于明确前提下的工程分析。没有为这些文字新增“执行通过”的标签。

## 4. 实际检查与证据

本机：macOS 26.7 arm64；Python 3.12.14；Pandoc 3.11。命令从仓库根目录运行，`python3` 在本轮实际使用 `/Users/nekoreb/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3` 的绝对路径调用。所有检查均为本地证据，不声明 CI 通过。

```sh
python3 c++/failure-model/review/audit_series.py
python3 c++/learning/check_docs.py
python3 c++/failure-model/review/verify_fm.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
git diff --check
```

| 证据类别 | 本轮执行与结果 | 不能推出什么 |
| --- | --- | --- |
| 结构与保护审计 | [series-audit.json](series-audit.json)：十篇的 H1–H3、旧锚点、215 个 C++ 载荷、T01–T20 元数据／源码及五项自检；历史证据和范围核对 | 不能自动证明新文案语义、旧锚点上下文或排版视觉质量 |
| 文档解析与链接 | `check_docs.py`：GFM 解析和本地文件／fragment 检查，最终零错误；数量见下方检查收口 | 链接存在不是技术正确性；不批量验证联网 URL |
| C++ 编译与负例诊断 | [series-verification-results.json](series-verification-results.json)：最终输入上同一组 20 例 × 两套工具链；40 次判定均符合原 oracle | 不是 40 个不同实验，不覆盖全部 215 个代码块 |
| 性能观察 | **NOT RUN** | 不将检查布局或常数说明解释成实测性能 |
| 并发动态检测 | **NOT RUN**；T12 是最小 join 后观察例，不是 TSan/stress | 没有建立并发协议证明或跨平台保证 |
| PDF／视觉 | **NOT BUILT / NOT VALIDATED**（本次 FM） | 不更改已发布 G 手册的状态 |

两套工具链分别为 Apple Clang 21.0.0（`clang-2100.3.34.2`，`_LIBCPP_VERSION=220106`）与 Homebrew Clang 23.1.2（`_LIBCPP_VERSION=230102`）；均为 arm64、libc++，`__cpp_lib_expected=202211`。未执行 GCC/libstdc++、Linux、Windows 或其他架构。

批内两次准备性重跑也各得到 40/40；修正链接与文本空白后完成第三次收口运行。三轮共 120 次判定，维护记录只收录最后一轮绑定最终输入的 40 项，不把重复运行计成更多样例。

每套 20 例包括：13 个 `run`、4 个 `compile_fail`、1 个 `compile`、1 个受控 `death` 和 1 个 UBSan `sanitizer_negative`。UBSan 负例按诊断判断；它不是并发动态检测。两套均无 FAIL、DIVERGENCE、SKIP 或 HARNESS_ERROR。命令、源码摘要、诊断与退出码保存在新 JSON；未运行不记 PASS。

执行器和历史 JSON 均未修改。新 JSON 是本轮临时执行结果的原样副本；执行器沿用的 `source_base=7869082…` 字段标识历史问题起点，**不是本轮文档字节基线**。本轮准确输入由其中的 `source_files_sha256` 绑定，修改前来源由本记录与结构审计的 `base=3c6dce9…` 绑定。

R01 继续关闭：T17 的完整区间相等、存储独立及修改隔离检查未变，本轮重跑正常 T17。**未重跑历史 12 次 R01 mutation 对照**；相关源码和判据的历史身份不因本次 40 项重跑而被替换。仍未注入分配失败，也没有穷举复制／移动语义。

检查收口：结构审计 PASS；Pandoc 解析 40 份 Markdown、本地链接／fragment 821 处，零错误；`git diff --check` 退出 0。结构审计同时复核新执行记录绑定当前 11 份输入文档、原执行器和 T01–T20 源码／判据。`cmp` 确认新执行 JSON 与最终临时结果逐字节一致。

批内曾发现修订记录尚未创建、一个新加的 `NDEBUG` 节链接写错，以及一行文本尾随空白；均已补齐／修正并重跑相关检查。最终通过不覆盖这些中间结果，也不将它们解释成 C++ 反例失败。通用检查器报告的 16 个 G 系列分页信号是既有源稿提示，不是本轮 FM 的九个信号。

## 5. 出版风险、保留项与停止边界

结构审计在 FM 正文登记九个出版源稿信号：五个长代码／模板／文本块、四个表格宽度提示。它们不是自动判定的 Markdown 错误，也不是已解决的 PDF 分页问题。完整 C++ 实验、流程顺序及表格字段关系保留；后续出版应处理续页身份、表头和软折行，不在本轮插入 renderer 私有指令。

保留现有 FM 机制深度、C++23 资料身份、历史实现差异与未验证边界。不增加 ABI 展开内部实现、新标准研究、跨语言专题或治理章节。长篇中的必要回顾未被压成纯速查笔记。

本批只改变 FM 当前维护文档及新增审计／执行记录：G0–G12、出版系统、历史 `dist/`、PDF、历史 FM 审核资料均未改动。提交并推送后进入集中复审；不自行把候选升级为 ACCEPTED，不启动 PDF、正式发布或下一轮扩写。

## 6. 系列接受与精度修正收口

用户已对 `3c6dce9 → 9c48ce0c8db2e0f66fd20d43df5f5a1099fb573f` 完成提交级复审，结论为系列级审核通过、零阻断项、两项非阻断精度建议。审核意见确认范围完整性、证据边界、技术抽查与系列架构；**不等于全部正文技术证明**。本节登记该接受意见，并说明随后补齐的差异，不能倒称用户已独立复核本次新字节。

本次修正只有两项语义主题：

- FM-8 §3：明确新线程 invoke expression 因异常退出会调用 `std::terminate()`，需要隔离时仍须显式捕获／保存或转换失败；保持 §2 的报告失败边界。依据仍是 N4950 `[thread.jthread.cons]/5`，没有切换到更新草案。
- FM-4 §19：把“所有资源都由对象拥有”收紧为当前组件承担释放责任的资源，并明确借用保持 non-owning；§18 checklist 同步避免暗示只能独占所有权。FM-9 §28 的 `Resources → RAII` 改为 `Owned resources (release responsibility) → RAII`。Core Guidelines R.1/R.3 是工程建议，不冒充语言规则。

十篇页首移除过时的“系列整理候选”标识，状态集中在 README 和本记录维护；除此之外，FM-0/1/2/3/5/6/7 仅改这一行标识。没有重新组织章节，没有新增示例或改动 C++／测试判据。

本次文档核对使用 Python 3.12.14、Pandoc 3.11，与 §4 相同绝对路径；从仓库根目录执行以下只读载荷／范围比较，以及 `python3 c++/learning/check_docs.py`、`git diff --check`：

```sh
python3 -B - <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, 'c++/failure-model/review')
from audit_series import parse, payload
base = '9c48ce0c8db2e0f66fd20d43df5f5a1099fb573f'
root = Path('c++/failure-model')
def before(path):
    return subprocess.check_output(['git', 'show', f'{base}:{path}'])
chapters = sorted(root.glob('fm[0-9]-*.md'))
cpp = cases = targets = 0
for path in chapters + [root / 'review/fm-verification-samples.md']:
    old, new = before(path).decode(), path.read_text()
    assert payload(old) == payload(new), path
    cases += len(payload(new)[1])
    if path in chapters:
        cpp += len(payload(new)[0])
        old_h, old_ids, _ = parse(old)
        new_h, new_ids, _ = parse(new)
        assert old_h == new_h and old_ids == new_ids, path
        targets += len(set(old_ids))
assert (len(chapters), cpp, cases) == (10, 215, 20)
record = root / 'review/series-verification-results.json'
assert record.read_bytes() == before(record)
for name, digest in json.loads(record.read_text())['source_files_sha256'].items():
    assert hashlib.sha256(before(root / name)).hexdigest() == digest
allowed = {str(p) for p in chapters} | {
    str(root / 'README.md'), str(root / 'review/series-revision.md')}
changed = subprocess.check_output(
    ['git', 'diff', '--name-only', base, '--'], text=True).splitlines()
assert set(changed) <= allowed, changed
assert not subprocess.check_output(
    ['git', 'ls-files', '--others', '--exclude-standard'], text=True).strip()
print(json.dumps(dict(status='PASS', chapters=10, cpp_blocks=cpp,
    cases=cases, baseline_targets=targets,
    historical_verification_binding='MATCH @ 9c48ce0',
    outside_scope_changes=[])))
PY
```

本次结果：载荷、标题／目标、历史执行输入绑定与范围检查通过；40 份 Markdown 的 822 处本地链接／fragment 零错误，`git diff --check` 退出 0。`9c48ce0` 的 562 个定位目标保持不变，其中包含原 442 个旧目标。仅改变说明文字、审查问题与 `text` 政策标签，未改变 C++ 源码。

`series-audit.json`、`series-verification-results.json`、执行器及更早证据全部保持原字节。`audit_series.py` 的完整命令属于 §4 的原批次检查，其整文件绑定应在 `9c48ce0` 快照重现；不能对本次已变化正文继续宣称原 `verification_binding: MATCH`。这里检查的是**旧结果仍准确绑定旧快照，且当前提取源码／判据未变**，没有追写历史摘要，也没有为获得新的全绿状态改动审计器。

本次 C++ 编译／负例重跑、R01 mutation、性能观察、TSan／并发动态检测均为 **NOT RUN**；FM PDF 为 **NOT BUILT / NOT VALIDATED**。此前的本地 40 项最终执行结果继续保持历史身份，不成为 CI 或本次重跑结论。

系列审核已接受，精度修正已补齐，FM-0～FM-9 进入长期内容维护；补丁随本次提交供核对。本轮到此收口，不启动真实项目验证、结构性重写、FM-10 或 PDF 出版。
