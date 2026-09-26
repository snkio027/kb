# FM 定向修订与验证记录 — 7869082

日期：2026-09-26。问题基线：`786908271dfa479c0d4aeb2239b19bd15f90e768`。状态：**已完成本轮本地修订与定向验证，待复审**；不表示全部代码块、全部标准命题或项目 profile 已验收。

初次修订对应提交 `0c7e989`。本次在其上补强 R01：下文“实际工具链与结果”和“证据绑定”已更新为补强后的重跑记录；初轮文档检查另标为历史记录，R01 的具体改动、对照实验和复现命令见专节。旧结果可从该精确提交读取，不被解释成已经验证新判据。

## 范围与材料身份

保留 FM-0～FM-9 的文件名、章节编号及整体结构，处理 A01～A04、B01～B08 和相应跨章边界。未改 G 系列、PDF 或 `design/`。用户随后明确要求每批变更完成检查后提交并推送供审核；本轮按该授权交付，不代表技术复审或项目规范批准。

用户提供的两份报告是审核输入，未将其中的示例执行说明当成更改仓库范围或正式批准的授权：

| 输入材料 | SHA-256 |
| --- | --- |
| `FM-Accuracy-Review-7869082.md` | `c3a3379de429043d076c95e729f57b01da94ea1c452c9fc1d5ce61d8a069f2dc` |
| `FM-Verification-Evidence-7869082.md` | `46ff57889dcf71b482f9ec4bbf1bc69b401b7e35e9201282ff91d1edb7057d34` |

已核对附件中 16 个源程序的 SHA-256。T01～T16 保留测试身份；T12、T14 直接置于相应正文作为单一维护源；T15 明确调整为查询结果仅观察、设置版本不得抛出的判据。新增 T17～T20 支持实际正文改动。

## 修订内容与判据

- 确定错误：补 out_of_range 描述参数；完成 Buffer 深复制；准确描述 move 的重载选择；分清 open 返回值与 errno。
- 条件补全：monadic 的类型／构造约束、value() 与 move-only E、线程报告再失败、枚举有效值前置条件、终止与清理、委托构造、error_code 重载及容器 throwing move 的具体保证。
- 跨章一致性：频率与严重性分开；异常传播、状态与终局策略分开；noexcept 不等于 no-fail；FM-9 仍是待采纳模板；validated 数据必须在使用期间保持不变量。
- 阅读调整只覆盖这些修订点：把碎片改成条件表与连贯解释；精确定义用链接复用，没有整体重写全部章节。

[关键命题台账](fm-claims.md)分别记录正文位置、适用条件、固定标准条款、修订状态和验证边界。以 [N4950](https://timsong-cpp.github.io/cppwp/n4950/) 与已注明的 LWG 3843 为依据，不无声混入后续标准。

## 验证方法

从仓库根目录运行：

```sh
python3 c++/review/verify_fm.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

[执行器](verify_fm.py)只提取带稳定 `fm-test` 标记的 20 个程序：完整程序、编译语义例、预期编译失败、UBSan 和受控终止分别判定。原始测试源码在[样例附录](fm-verification-samples.md)或各正文，不维护平行的手写 cpp。

编译公共参数：

```text
-std=c++23 -O1 -Wall -Wextra -pedantic -pthread
```

- 仅编译用例加 `-fsyntax-only`。
- UBSan 用例加 `-fsanitize=undefined -fno-sanitize-recover=all`，单独子进程执行。
- 每个工具链、每个样例使用全新的临时工作目录；T20 只在自己的目录创建文件。
- 负例必须匹配相应诊断，不把任意编译失败算作成功；超时／信号造成的编译器失败不算预期拒绝。
- T11 必须退出 86；T05 必须出现不可达点的运行时诊断，不能只看非零返回值。
- 完整记录编译器路径、版本、标准库宏、输入文档与样例摘要、命令、诊断、返回码及判定。
- 缺少编译器／预检能力记 SKIP；有跳过时不返回全通过的 0。T16 若被接受，保留 DIVERGENCE 并返回非零。

这不是执行不可信代码的通用沙箱。样例均经本轮阅读，进程隔离用于分离终止／UB 反例；不要将该执行器用于未经审查的外部任意代码。

## 实际工具链与结果

环境：macOS / Darwin arm64。两套工具链都属于 Clang + libc++ 家族，使用了不同版本的 libc++ 头文件；不能称为独立标准库家族交叉验证。

| 工具链 | 标准库身份 | expected feature | 样例数 | 符合各自预期 | FAIL / DIVERGENCE / SKIP / HARNESS_ERROR |
| --- | --- | --- | --- | --- | --- |
| Apple Clang 21.0.0（clang-2100.3.34.2） | `_LIBCPP_VERSION=220106` | `202211` | 20 | 20 | 0 / 0 / 0 / 0 |
| Homebrew Clang 23.1.2 | `_LIBCPP_VERSION=230102` | `202211` | 20 | 20 | 0 / 0 / 0 / 0 |

执行命令退出 0；“符合预期”包括正确拒绝、UBSan 诊断与受控终止，不是说 20 份程序都是可正常运行的生产正例。

| 样例 | 目的／判定身份 | Apple Clang | Homebrew Clang |
| --- | --- | --- | --- |
| T01 | 原式预期编译失败 | PASS（编译 1） | PASS（编译 1） |
| T02 | 修正后的运行正例 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T03 | move 的复制回退 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T04 | 未命名枚举值 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T05 | 隔离 UBSan 反例 | PASS（编译 0；运行 -6） | PASS（编译 0；运行 -6） |
| T06 | move-only E 左值 value() 拒绝 | PASS（编译 1） | PASS（编译 1） |
| T07 | 判状态后解引用 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T08 | 不同 E 的 and_then 拒绝 | PASS（编译 1） | PASS（编译 1） |
| T09 | 显式错误域转换 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T10 | 错误对象复制再抛出 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T11 | 人为报告失败／受控终止 | PASS（编译 0；运行 86） | PASS（编译 0；运行 86） |
| T12 | 保存异常并 join 后处理 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T13 | 委托构造体失败析构 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T14 | 完整表达式 noexcept／仅编译 | PASS（编译 0） | PASS（编译 0） |
| T15 | error_code 重载／实现观测 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T16 | move-only E 右值 value() 拒绝 | PASS（编译 1） | PASS（编译 1） |
| T17 | 完整值、存储独立、修改隔离、空对象、移出状态 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T18 | 完整 pipeline 四条路径 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T19 | 错误分支返还任务所有权 | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |
| T20 | POSIX open/errno/O_CREAT | PASS（编译 0；运行 0） | PASS（编译 0；运行 0） |

T05 的 -6 表示本次子进程被 SIGABRT 终止，且日志包含 `runtime error: execution reached an unreachable program point`；这不是对任意实现的 UB 行为保证。T06 / T16 诊断包含 `is_copy_constructible_v<Error>`；T08 包含 `is_same_v<ParseError, FileError>`。T15 两套输出均为 `query_noexcept=0 change_noexcept=1`。

**历史差异仍保留：** 用户附件报告 GCC 14.2 和 Clang 17 共用 libstdc++ 14，T16 被接受，各 16 个用例中 15 个符合预期、1 个 DIVERGENCE。本次未重跑那套 Linux 工具链；本机 libc++ 拒绝 T16 不会改写该历史记录。

初轮另执行了 10 项判定器断言，覆盖无关诊断不得通过、编译器被信号终止、T16 接受时的 DIVERGENCE、UBSan 诊断与受控退出码等。使用不存在的编译器进行入口验证，得到 20 SKIP、退出 2，没有误报全通过。这些是 harness 检查，不计入上表的 20 个 C++ 命题用例；R01 未修改执行器，也未重复该组自检。

## 证据绑定

[完整本机验证结果](fm-verification-results.json)现保留 R01 后两套工具链的完整 20 例重跑，以及 `r01_mutations` 中 12 次 T17 对照编译／运行的命令、诊断、源码摘要与判定。仅将两组原始临时目录前缀分别替换为 `<RUN>`、`<R01_RUN>`，没有改写其余诊断内容或结果。它是路径归一化副本，不是原始字节副本；原结果由 `0c7e989` 的同路径文件保留。

结果中的 `source_base` 是初轮问题基线，`revision_review_base` 是 R01 的审核基线，均不冒充修订后的提交；实际验证输入由 `source_files_sha256`、每例 `source_sha256` 和 `runner_sha256` 绑定。该记录不把最终摘要写回任何被计算摘要的源文件。被绑定的文档、样例或执行器发生后续变化，应重新运行并更新外部结果记录。

## 文档与范围检查（0c7e989 历史记录）

- 使用 `pandoc -f gfm -t json <file>` 解析本轮 14 份 Markdown，检查单一一级标题、标题层级、代码围栏和 390 个本地链接／锚点：通过。41 个外链没有进行全量连通性探测；本轮采用的关键条款已定向读取。
- 十篇 FM 的编号章节标题与问题基线逐项相同；原有文件名、章节顺序及前后导航保持不变。
- `git diff --check` 与五个新文件的 `git diff --no-index --check /dev/null <file>`：通过；Python `ast.parse` 和结果 JSON 解析通过。
- 验证记录的 11 个输入文档摘要、20 个样例摘要、执行器摘要均与当前文件一致；重算两个工具链的 40 项判定均与记录一致。
- 与修订前 100 个现存文件的 SHA-256 快照比较，只有十篇 FM 与 `c++/README.md` 改变；其余 89 个文件逐字节不变，包含原有四篇未跟踪 G 文档。新文件仅为本目录中的命题台账、样例、执行器、结果和本记录。
- G 系列、PDF、`design/` 及已有出版工具未修改；未构建 PDF。提交仅纳入本轮 FM 修订与验证材料，四篇原有未跟踪 G 文档保持不动；实际提交及远端核对结果在交付消息中报告。

上述检查用于本轮文档与证据的一致性，不替代完整技术复审。

## R01：T17 判据补强

复审输入为 `FM-ReReview-0c7e989.md`（SHA-256：`db44af2370fb5f54b37931372c1101c391838d9e7e3d995ee2d052df17510c40`），审核基线为 `0c7e989e7b53630017c98a4dd3d3260ef9c85b34`。本轮只修改 T17 判据及关联说明、A02 台账与执行证据，不改变 `Buffer` 实现，也不重写其他章节。状态：**补强已实现并在本机验证，待复审确认**。

三迭代器比较没有表达两个完整区间的长度相等。T17 现改用 `std::ranges::equal`，并给复制赋值补上存储独立与修改隔离检查；复制构造已有的独立性检查保留。[N4950：alg.equal](https://timsong-cpp.github.io/cppwp/n4950/algorithms#alg.equal)

本机实际执行：Apple Clang 21.0.0 / libc++ 220106 和 Homebrew Clang 23.1.2 / libc++ 230102，工具身份见上表。完整 T01～T20 在每套工具链各重跑一次，均为 20 个符合各自预期；此外执行以下 **6 个 T17 版本 × 2 套工具链，共 12 次编译与运行**。这 12 次没有并入“20 个命题用例”的分母。

| 实现 | 旧判据：Apple / Homebrew 运行码 | 补强判据：Apple / Homebrew 运行码 |
| --- | --- | --- |
| 原正确实现 | 0 / 0 | 0 / 0 |
| M1：赋值为空操作 | 0 / 0（复现盲点） | 4 / 4（拒绝错误实现） |
| M2：非空复制截断为一字节 | 0 / 0（复现盲点） | 1 / 1（拒绝错误实现） |

12 次编译均成功，未用无关编译失败替代拒绝判据。M1 的 unused-parameter 警告保留在诊断中；未启用 `-Werror`。这些错误实现仅生成到独立临时目录，不存在于正文的 `Buffer` 中。

T17 源码摘要：

- 旧判据：`f69e5a0bc2e837842526a3f3553e9c6fb55d209a898fe44816078da73d6bb3be`。
- 新判据：`fa2aa5114a5e972b4c66787c61273c99b58bfa4c17ccf57c7bc273ec23edbe42`。

六个版本的源码摘要均与附件对应程序一致，但附件的 Linux / libstdc++ 14 运行仍是外部历史证据；本段是另行执行的 macOS / libc++ 结果。未新增分配失败注入或完整变异测试覆盖。

以下轻量复现命令从仓库根目录执行，复用未修改的执行器，不安装依赖、不增加测试框架。它从当前 Markdown 提取 T17；只有匹配精确替换位置且还原的旧源码摘要正确时才继续。JSON 中旧判据变体的 `PASS` 只表示“成功复现测试盲点”，不表示错误实现正确。

<!-- fm-r01-reproducer -->
```sh
PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import importlib.util
import json
from pathlib import Path
import tempfile

spec = importlib.util.spec_from_file_location("fm", "c++/review/verify_fm.py")
fm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fm)
samples, inputs = fm.collect()
current = next(c["source"] for c in samples if c["id"] == "T17")

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("T17 no longer matches the reviewed replacement")
    return text.replace(old, new, 1)

old = current
for name in ("copied", "assigned"):
    old = replace_once(old, f"std::ranges::equal({name}.bytes(), input)",
                       f"std::equal({name}.bytes().begin(), {name}.bytes().end(), input)")
old = replace_once(old,
    "    if (assigned.bytes().data() == original.bytes().data()) return 6;\n"
    "    assigned.bytes()[0] = std::byte{8};\n"
    "    if (original.bytes()[0] != std::byte{1}) return 7;\n", "")
if fm.sha(old.encode()) != "f69e5a0bc2e837842526a3f3553e9c6fb55d209a898fe44816078da73d6bb3be":
    raise ValueError("Reconstructed old T17 does not match 0c7e989")
if old.split("int main()")[0] != current.split("int main()")[0]:
    raise ValueError("Buffer implementation changed")

cases = []
for label, source in (("old", old), ("strengthened", current)):
    noop = replace_once(source, "        swap(other);",
                        "        // Deliberately broken mutation: copy assignment does nothing.")
    truncated = replace_once(source, "          size_{other.size_} {",
                             "          size_{other.size_ == 0 ? 0U : 1U} {")
    for name, code, rejected_rc in (("correct", source, 0),
                                   ("noop", noop, 4), ("truncated", truncated, 1)):
        cases.append(dict(id=f"T17-{label}-{name}", mode="run",
                          source=code, source_sha256=fm.sha(code.encode()),
                          exit_code=0 if label == "old" else rejected_rc,
                          oracle=label, deliberate_mutation=name != "correct"))

output = Path(tempfile.mkdtemp(prefix="fm-r01-"))
report = dict(review_base="0c7e989e7b53630017c98a4dd3d3260ef9c85b34",
              source_files_sha256=inputs,
              runner_sha256=fm.sha(Path("c++/review/verify_fm.py").read_bytes()),
              scope="T17 only: six versions; old mutation PASS means reproduced blind spot",
              toolchains=[])
for index, compiler in enumerate(("/usr/bin/clang++", "/opt/homebrew/opt/llvm/bin/clang++")):
    info, rows = fm.run_compiler(compiler, output / f"compiler-{index}", cases)
    info["results"] = rows
    report["toolchains"].append(info)
    for row in rows:
        print(compiler, row["id"], row.get("compile", {}).get("returncode"),
              row.get("run", {}).get("returncode"), row["status"])
ok = all(row["status"] == "PASS"
         for tc in report["toolchains"] for row in tc["results"])
report["exit_code"] = 0 if ok else 1
(output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print("Evidence:", output / "results.json")
raise SystemExit(report["exit_code"])
PY
```

R01 收尾检查：重新以 `pandoc -f gfm -t json <file>` 解析 14 份 Markdown，标题层级、围栏和 391 个本地链接／锚点通过；`git diff --check` 通过。当前 11 个输入文档、20 个样例和执行器摘要与新结果匹配，40 项常规判定及 12 项对照判定重算一致；正文里的 `Buffer` 实现及其余 19 个样例源码与 `0c7e989` 相同。与本轮开始时 106 个现存文件的 SHA-256 比较，仅 FM-5、A02 台账、本记录和结果 JSON 四个文件改变，其余 102 个文件不变，包括五篇原有未跟踪 G 文档。未重新执行初轮 harness 自检、未做外链全量探测，未修改或构建 PDF。

## 剩余边界

本次不宣称完成：

- 历史全部代码块分类／编译、全部标准命题或后续 DR 穷举。
- MSVC、本机以外平台、独立标准库家族全面对照；Linux 附件结果只作外部证据。
- 所有 cv/ref 重载、分配失败、容器 throwing move、线程创建／join／日志设施的故障注入矩阵。
- 全库 CI、完整 ASan / TSan、性能／实时性、部署实现或项目规范批准。

B05a、B07 等的结果是条款与跨章核对，不冒充已做运行时穷举。T18 使用内存替身，不验证真实文件加载。局部阅读体验改进不代表所有碎片与重复均已消除。

本轮接收的是限定范围内的技术修订和可复现验证，是否通过集中复审仍待审核者判断。
