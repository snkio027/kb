# G 系列实验与证据

这里保存 G0～G12 的定向证据与记录；正文 Markdown 是实验源代码的单一维护入口。G12 使用综合审查案例，不另造实验执行器。[Editorial Profile](../editorial-profile.md) 统一编辑规则，不由执行器重新定义学习目标。

全书的状态标签及引用身份见[阅读约定](../handbook-guide.md)。本轮 [Editorial Sweep](editorial-sweep.md) 只进行编辑与只读保真检查：历史整篇文档摘要仍指向旧提交，新文档摘要另存；完整代码块、提取标记及 Gate 保持情况见 [冻结候选清单](editorial-sweep-results.json)。代码未变不记为重新编译或再次检测。

从仓库根目录执行：

```sh
python3 c++/learning/verify_g.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_native.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_synthesis.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 -m unittest discover -s c++/learning -p 'test_*.py'
python3 c++/learning/check_docs.py
```

只使用本机已有工具，不下载依赖。四个实验执行器各自创建新系统临时目录，开头打印 `Evidence:` 路径；其中 `results.json` 保存提取源码摘要、完整命令、诊断与结果，源码/目标文件/汇编留在对应实验子目录。不会写入历史 PDF 或 FM 证据。`g-lab/g-file` 标识 G0～G4；`h-lab/h-file` 标识 G5～G7；`n-lab/n-file` 标识 G8～G9；`s-lab/s-file` 标识 G10～G11。其余代码块不纳入完整程序执行。

## 四类证据

| 类别 | 判据与不能推出的结论 |
| --- | --- |
| 文档结构/链接 | Pandoc GFM 解析、本地链接与锚点、H1～H3、代码身份及源稿风险；不验证联网 URL 或 PDF 分页 |
| C++ 编译/目标诊断与合同 | 静态断言、编译/链接负例、运行不变量及定向 ASan/UBSan；按阶段区分，不统称静态证明 |
| 性能与机器观察 | 布局、资源请求、基准及主机时序均保留条件；汇编/符号观察不是端到端性能，数值不以更快为 PASS |
| 并发动态检测 | TSan 正负对照及对应插桩执行；普通 stress/shutdown 另列运行合同，CLEAN_OBSERVED 不等于形式化证明 |

历史 JSON 的分类名保持原样。下文“本批”按所在执行器/历史批次理解，不表示当前编辑 Sweep 新增了这些执行。G5～G7 的具体执行合同如下；G8～G9、G10～G12 的差异在各自小节说明。

`verify_handbook.py` 无跨类别的“全部 PASS”。`RECORDED` 表示要求的记录收集完成；环境缺失记 SKIP 并以 INCOMPLETE 退出。观察记录缺项、不变量失败、无关错误、超时和信号崩溃记 FAIL。每个子进程有 45 秒上限，Ctrl-C 取消/超时终止相应进程组；不以超时视作安全停机证据，也不承诺 SIGKILL 或系统故障下清理完毕。

TSan 显式使用 `halt_on_error=1:abort_on_error=0:exitcode=66:symbolize=0`。先检查无竞争探针能正常运行，再要求 D3 报告 data race 且返回 66。关闭外部符号化，不验收源码行号栈。D1/D2 均先普通运行，再在探针支持时插桩运行。SKIP 不可解释为无竞争。

G6-M3 使用 -O3、分离编译、无 LTO，初始化不计时；每轮结果校验和可观察，保留全部 42 条行列布局测量。CPU 采样 profile、硬件计数器和端到端业务性能不在本次实测内；汇编与局部分配计数不冒充这些证据。

先在正文预测，再运行，再解释差异。`PASS` 表示该实验的具体判据满足，不表示整篇文章、整套标准库或全部平台已经验证。编译失败反例必须匹配目标诊断；ASan 反例必须检测到指定错误，崩溃或超时不能替代它。工具缺失记为 `SKIP`，不计通过。

执行器会编译并运行正文里的代码，**不是不可信代码沙箱**。仅运行已经检查过的本仓库实验。

## G8～G9 的本机验证入口

`verify_native.py` 当前明确支持 Darwin / Clang / Mach-O，要求指定 Clang++ 旁存在 Clang C 编译器，并已安装 CMake、CTest、Ninja、nm、otool。其他平台或缺工具返回 INCOMPLETE，不冒充已支持。完整实验声明最低 CMake 3.28；本批只实测结果中记录的版本。

四个模块共 20 个正文文件：G8-B1 为 C/C++ 分离编译、符号观察与目标链接负例；G8-B2 为真实 C11 消费者和 C++23 共享提供者；G9-P1 为静态 PRIVATE 依赖、安装迁移及独立 Config 消费；G9-P2 为 dev presets 和输入依赖失效验证。另有错误计数与遗漏生成依赖两个受控变体，要求编译成功后按精确运行码拒绝。

结果分为 `compile_link_consumer` 和 `binary_observation`，后者不是性能观察。性能测量与并发动态检测本批均为 NOT RUN；不沿用 G6/G7 的历史结果冒充本批覆盖。CTest 要求非空测试集成功，不接受任意零退出空跑。每个命令最多 60 秒，沿用已有进程组取消/超时清理；本批未重做真实 Ctrl-C 生命周期实验。

P1 移动安装前缀并重命名临时生产者源码/构建目录，不删除原件；消费者只能使用新的安装位置。P2 将临时值文件从 7 改成 19，显式推进输入时间戳以避免粗粒度文件系统遗漏重建，再观察程序结果；这不是构建性能测量。其 CTest `generated.initial` 固定检查初始值 7，变更阶段由执行器直接用期望 19 检查程序，不宣称旧的固定期望测试在变更后仍通过。控制搜索环境不等于 hermetic 构建，生成脚本也不视为安全沙箱。

- [G8～G9 修订、主题去向与验证边界](native-revision.md)
- [G8～G9 本地原始证据](native-results.json)

## G10～G12 综合与应用卷

`verify_synthesis.py` 使用已有 Clang C/C++、CMake、CTest 与 Ninja，当前只验证 Darwin 路径；不下载依赖、不连接硬件。17 个正文源文件形成两个模块，另有四个受控错误变体。G12 的三个案例是逻辑复核练习，不算编译或动态测试。

G10-R1 包含固定载荷、有限账本的双队列运行时：实际等待输入满、输出满、空输入等条件后检查取消；检查多生产者记账、逐 ID 结果、graceful drain、异常、部分启动失败与析构。随后安装、迁移并隐藏临时生产树，编译运行独立 C11/C++23 消费者。worker/capacity sweep 共 18 个观测行，不设速度门槛。

G11-C1 分开检查故障锁存/复位、确定性 plant、当前线程可替换 C++ 分配调用、并发 generation，以及 1000 周期的 1 kHz 主机时序。中点握手保证快照测试确实在 writer 结束前检查过一代。malloc、页面、真实 ROS/驱动/HIL、hard-real-time 与物理安全均未验证。

结果分 `cpp_validation`、`performance_observation`、`concurrency_dynamic`；结构检查另报。`cpp_validation` 含编译/安装、功能不变量及 ASan/UBSan 的定向运行，不能把其中每条阶段断言称为一个新实验。TSan 先跑启动探针和来自既有 G7-D3 的已知竞争检测对照；这次重用对照不意味着 G7 正文或全套旧实验重新验收。各检测器环境分开，失败不得以信号崩溃或不相关退出码替代。原始证据记录受控 options，禁用外部符号化；ASan 未检查 leaks。

每个命令最多 60 秒，调用既有进程组超时/取消 helper；本批没有新的真实 Ctrl-C 实验。探针或主实验失败、无法获得预期诊断、记录缺项都不能变成 RECORDED。缺少支持项记 SKIP/INCOMPLETE，动态无报告也不等于协议已证明。源码树与安装树移动仅发生在新临时目录内，不改仓库源码。

- [综合与应用卷修订及验证边界](synthesis-revision.md)
- [本批原始证据与失败历史](synthesis-results.json)

- [回到全系列学习导航](../README.md)
- [Professional 批次修订与验证记录](professional-revision.md)
- [Professional 批次原始执行记录](professional-results.json)
- [60c5562 学习版修订记录（历史）](revision-notes.md)
- [60c5562 学习版执行结果（历史）](verification-results.json)
