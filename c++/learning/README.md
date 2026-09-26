# G 系列实验与证据

这里保存 G0～G7 的定向执行器与记录；正文 Markdown 是实验源代码的单一维护入口。[Editorial Profile](../editorial-profile.md) 统一编辑规则，不由执行器重新定义学习目标。

从仓库根目录执行：

```sh
python3 c++/learning/verify_g.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 c++/learning/verify_handbook.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
python3 -m unittest discover -s c++/learning -p 'test_*.py'
python3 c++/learning/check_docs.py
```

只使用本机已有编译器，不下载依赖。两个实验执行器各自创建新系统临时目录，开头打印 `Evidence:` 路径；其中 `results.json` 保存提取源码摘要、完整命令、诊断与结果，源码/目标文件/汇编留在对应实验子目录。不会写入历史 PDF 或 FM 证据。`g-lab/g-file` 标识 G0～G4；`h-lab/h-file` 标识 G5～G7。其余代码块不纳入完整程序执行。

## 四类证据

| 类别 | 判据与不能推出的结论 |
| --- | --- |
| 文档结构/链接 | Pandoc GFM 解析、本地链接与锚点、H1～H3、代码身份及源稿风险；不验证联网 URL 或 PDF 分页 |
| C++ 编译/诊断 | 静态断言、正例、理由匹配的编译/链接负例；符号表是目标工具链观察，不规定符号拼写或数量 |
| 性能观察 | 布局、指定 PMR 资源请求、三规模七轮 AoS/SoA 基准及汇编；数值标记 OBSERVED，不以更快为 PASS |
| 并发动态检测 | 本次 stress/shutdown 不变量及 TSan 正负对照；CLEAN_OBSERVED/DETECTED 不等于协议已形式化证明 |

`verify_handbook.py` 无跨类别的“全部 PASS”。`RECORDED` 表示要求的记录收集完成；环境缺失记 SKIP 并以 INCOMPLETE 退出。观察记录缺项、不变量失败、无关错误、超时和信号崩溃记 FAIL。每个子进程有 45 秒上限，Ctrl-C 取消/超时终止相应进程组；不以超时视作安全停机证据，也不承诺 SIGKILL 或系统故障下清理完毕。

TSan 显式使用 `halt_on_error=1:abort_on_error=0:exitcode=66:symbolize=0`。先检查无竞争探针能正常运行，再要求 D3 报告 data race 且返回 66。关闭外部符号化，不验收源码行号栈。D1/D2 均先普通运行，再在探针支持时插桩运行。SKIP 不可解释为无竞争。

G6-M3 使用 -O3、分离编译、无 LTO，初始化不计时；每轮结果校验和可观察，保留全部 42 条行列布局测量。CPU 采样 profile、硬件计数器和端到端业务性能不在本次实测内；汇编与局部分配计数不冒充这些证据。

先在正文预测，再运行，再解释差异。`PASS` 表示该实验的具体判据满足，不表示整篇文章、整套标准库或全部平台已经验证。编译失败反例必须匹配目标诊断；ASan 反例必须检测到指定错误，崩溃或超时不能替代它。工具缺失记为 `SKIP`，不计通过。

执行器会编译并运行正文里的代码，**不是不可信代码沙箱**。仅运行已经检查过的本仓库实验。

- [回到全系列学习导航](../README.md)
- [Professional 批次修订与验证记录](professional-revision.md)
- [Professional 批次原始执行记录](professional-results.json)
- [60c5562 学习版修订记录（历史）](revision-notes.md)
- [60c5562 学习版执行结果（历史）](verification-results.json)
