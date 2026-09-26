# G11 · 机器人系统工程

**版本：** 1.1 · Professional Handbook Edition · 综合与应用卷

**状态：** 待集中审核；PDF NOT BUILT / NOT VALIDATED

**主线：** C++23；Robotics Systems Engineering；仿真不构成实时或物理安全保证。

**编辑基线：** [Editorial Profile v1.0](editorial-profile.md)，保持 v1.0。

## 阅读入口

本章在 G10 的资源与并发模型上加入时间、物理意义和安全状态。先读 §1～8，再读 §13 与 §16 的仿真实验；ROS/QoS 是 §9 的集成回查，不是学习主线。

原稿的 Complete/Frozen 是历史编辑标记，不沿用为技术验收。编号主题以 `g11-topic-N` 映射到相应主题组，保留技术去向；章节不再逐个复制原有 Part。完整实验与机制片段有可见身份，Gate 答案是普通章节。

- [1. 物理闭环与实时合同](#g11-section-1)
- [2. 时间域、数据年龄与控制步长](#g11-section-2)
- [3. 调度、干扰与优先级反转](#g11-section-3)
- [4. 内存阶段与故障表示](#g11-section-4)
- [5. 单位、坐标系与数值表示](#g11-section-5)
- [6. 传感器采集、通道语义与快照回收](#g11-section-6)
- [7. 估计、控制与硬件边界](#g11-section-7)
- [8. 看门狗、故障锁存与命令仲裁](#g11-section-8)
- [9. ROS 2、QoS 与借出缓冲区](#g11-section-9)
- [10. 大载荷、配置事务与安全过滤](#g11-section-10)
- [11. 故障隔离、观测与测试阶梯](#g11-section-11)
- [12. 执行等级与集成拓扑](#g11-section-12)
- [13. 输出不变量与工程分层](#g11-section-13)
- [14. 可运行学习案例的范围](#g11-section-14)
- [15. 常见误判与语言选择](#g11-section-15)
- [16. 完整实验：逻辑仿真、快照与时序](#g11-section-16)
- [17. 机器人路径复核记录](#g11-section-17)
- [18. Final Gate](#g11-section-18)
- [19. Final Gate · 参考答案与常见误判](#g11-section-19)
- [20. 参考资料与验证边界](#g11-section-20)

<a id="g11-section-1"></a>

<a id="g11-topic-0"></a>
<a id="g11-topic-1"></a>
<a id="g11-topic-2"></a>
<a id="g11-topic-3"></a>
<a id="g11-topic-4"></a>
<a id="g11-topic-5"></a>
<a id="g11-topic-6"></a>
<a id="g11-topic-7"></a>
<a id="g11-topic-8"></a>

## 1. 物理闭环与实时合同

### 1.1 软件结果会改变下一次输入

机器人系统工程（robotics systems engineering）把软件正确性放进物理闭环：测量、估计、控制、执行再影响下一轮测量。正确数值若过期才送到执行器，可能已不是正确动作。因此本章关注 value、unit、frame、time、lifetime 与 failure 的联合合同，而不是 ROS 2 API 教程。

```text
World → Measure → Estimate → Control → Safety → Actuate
  ▲                                               │
  +--------------- feedback ----------------------+
Non-RT: configuration / planning / ROS / logging
Timing-critical: bounded state / control / safety
Hardware: bus / driver / local watchdog
```

三个执行域可以在部分场景合并，但不能默认共享不可控阻塞。视觉、规划、UI、控制和硬件 I/O 有不同的吞吐、时限与故障需求；“实时”不是给整个仓库贴的标签。

### 1.2 快、可预测和安全是不同判断

周期（period）是计划 release 间隔；deadline 是完成期限；本章把 release jitter 明确定义为实际开始减计划开始，执行时间则是完成减实际开始。1 kHz 对应 1 ms 计划周期，不保证每次实际间隔恰为 1 ms。平均 10 µs 不能覆盖偶发 200 ms 停顿。

Hard real-time 要在明确平台及负载假设下保证截止期限；firm real-time 的迟到结果失去价值但允许受控 miss；soft real-time 的迟到降低服务质量。它们描述需求和保证，不是根据一次最大值自动分类。§16 的桌面仿真只给出本机 timing observation，不能证明 WCET 或物理安全。

<a id="g11-section-2"></a>

<a id="g11-topic-9"></a>
<a id="g11-topic-10"></a>
<a id="g11-topic-11"></a>
<a id="g11-topic-12"></a>
<a id="g11-topic-13"></a>
<a id="g11-topic-14"></a>
<a id="g11-topic-15"></a>
<a id="g11-topic-16"></a>
<a id="g11-topic-17"></a>
<a id="g11-topic-18"></a>
<a id="g11-topic-19"></a>
<a id="g11-topic-20"></a>
<a id="g11-topic-21"></a>
<a id="g11-topic-22"></a>

## 2. 时间域、数据年龄与控制步长

### 2.1 时间戳必须有语义和来源

测量时间、设备发送、内核接收、应用接收与处理完成不是同一时间。收到数据后写 steady_clock::now，只能给它应用接收时间，不能将通信抖动消掉而称作测量时间。设备计时器、主机单调时钟、UTC、PTP 与 ROS 仿真时钟即使都以 ns 表示，也不能未经映射直接相减。

跨时钟域转换应声明偏移、漂移、同步误差和失效条件；时间戳倒退、设备重启和序列回绕也要处理。仿真时间可以暂停或回拨，主机 steady_clock 适合本地 duration，不应冒充物理测量时钟。控制的 freshness 先检查时间域和“非未来”，再计算 age，避免无符号减法下溢。

### 2.2 固定步长与实际步长不能悄悄替换

固定步长离散控制器基于配置周期；measured-step 算法使用实际 elapsed time。两者都需要各自稳定性前提，不能将一次调度延迟直接当作大 dt 填入原本固定步长的积分器。控制接口应显式携带 tick/time/duration，并定义接近零、过大或非有限 dt 的策略。

典型循环为 read → estimate → control → safety → write；每步需审查输入规模、分配、等待、异常和未知回调。配置解析、模型加载与日志移到非实时域，经过验证的规范化配置在安全点发布。本章 timing 模块故意用逻辑 1 ms 仿真步长，同时单独记录主机 wake/finish；它不是实时物理 plant 的保真模拟。

<a id="g11-section-3"></a>

<a id="g11-topic-23"></a>
<a id="g11-topic-24"></a>
<a id="g11-topic-25"></a>
<a id="g11-topic-26"></a>
<a id="g11-topic-27"></a>
<a id="g11-topic-28"></a>
<a id="g11-topic-29"></a>
<a id="g11-topic-30"></a>

## 3. 调度、干扰与优先级反转

### 3.1 优先级是部署条件，不是证明

Linux 的 SCHED_FIFO/SCHED_RR、CPU affinity、隔离核心和 IRQ 布局可改变调度干扰，但 page fault、驱动、锁持有者、固件和热降频仍影响尾延迟。高优先级线程也可能因等待低优先级持锁者而发生优先级反转（priority inversion）。未分析竞争与锁持有时间，不能仅凭“平时不竞争”称其有界。

本章以 [ros2_control Jazzy Controller Manager](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html) 为部署回查线，不给机器设置实时权限，也不更改调度器、内存锁定或系统配置。Linux 部署建议与 macOS 仿真实验是两种证据，不能互相替代。

### 3.2 把不确定工作移出关键路径

Non-RT 回调可慢慢构建完整 snapshot，控制线程在边界处接收。若选择 try_lock，读者失败时必须有“保留旧值并检查 age”策略，且仍不能声称底层调用有硬时间上界。若选择无锁发布，必须额外证明存储回收和重试上界。架构是在时间约束、数据新鲜度与实现复杂度间取舍，不是逢 mutex 必改 CAS。

<a id="g11-section-4"></a>

<a id="g11-topic-31"></a>
<a id="g11-topic-32"></a>
<a id="g11-topic-33"></a>
<a id="g11-topic-34"></a>
<a id="g11-topic-35"></a>
<a id="g11-topic-36"></a>
<a id="g11-topic-37"></a>
<a id="g11-topic-38"></a>
<a id="g11-topic-39"></a>
<a id="g11-topic-40"></a>

## 4. 内存阶段与故障表示

### 4.1 初始化分配不等于运行期永不分配

general heap 的问题是时间和锁/页面行为未必满足合同，而非每次 new 必然慢。初始化可预留容器、构造对象、预热和触页；运行期复用有界表示。reserve 只保证一定容量，超过容量仍可扩张。C++23 没有标准 inplace_vector；可用 array + size 或经验证的有界容器，手动 raw storage 则重新承担对象生命周期责任。

memory locking 与 pre-touch 把部分页面成本移出关键阶段，但不把任意程序变为 hard real-time。官方 [ROS 2 Jazzy 实时示例源码文档](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Demos/Real-Time-Programming.rst)讨论这些条件；本批没有执行该 Linux 示例或其特权操作。

### 4.2 故障是受控状态，不只是 throw

关键路径可选择不抛接口，但 noexcept 遇到未处理异常会 terminate，不会自动生成安全命令。sensor timeout、非法状态和 actuator fault 应输入显式状态机；日志与报告失败也不能反过来阻塞安全路径。

分配审计必须声明观测面。§16 替换可替换的 C++ allocation functions，在当前线程的确定性 control phase 计数，并用一次显式分配作检测对照；它不拦截第三方 malloc、驱动分配、OS 页面活动或其他线程。观察到 0 只支持此范围内的结论，不等于全进程零分配认证。

<a id="g11-section-5"></a>

<a id="g11-topic-41"></a>
<a id="g11-topic-42"></a>
<a id="g11-topic-43"></a>
<a id="g11-topic-44"></a>
<a id="g11-topic-45"></a>
<a id="g11-topic-46"></a>
<a id="g11-topic-47"></a>
<a id="g11-topic-48"></a>
<a id="g11-topic-49"></a>
<a id="g11-topic-50"></a>
<a id="g11-topic-51"></a>
<a id="g11-topic-52"></a>
<a id="g11-topic-53"></a>
<a id="g11-topic-54"></a>

## 5. 单位、坐标系与数值表示

### 5.1 double 没有物理语义

米、弧度、秒、牛顿和力矩都可能表示为 double，却不是可互换量。边界把设备单位规范化到约定单位，接口用 strong units 或明确 schema。位置还必须属于 frame；T_A_B 需说明是把 B 坐标变到 A，还是相反。静态关节链可借助类型约束，运行时地图/传感器图则需要动态身份和校验，两者不宜无限模板化。

刚体变换包含旋转和平移，四元数要统一 wxyz/xyzw、主动/被动旋转、乘法方向和归一化规则。本章保留这些审查责任，不把单自由度实验扩大成 SE(3) 数学验证。

### 5.2 数值库的表达式仍要检查存储与别名

固定维矩阵适合许多小规模控制状态，动态矩阵应在初始化确定形状并复用。固定尺寸也不意味着包含它的所有高层操作都无分配。Eigen 风格表达式可能融合计算，也可能为别名、安全或代价生成临时；noalias 只能在确实无别名时使用，不能为了提速掩盖 A = A * B 的依赖。

NaN/Inf、奇异点、数值条件、近零 dt 和漂移属于算法边界。clamp 不负责把 NaN 变成安全数值；写执行器前应先检查 finite，再检查 limits 与 freshness。具体 Eigen 行为应按锁定版本回查；[官方 Aliasing 说明](https://libeigen.gitlab.io/eigen/docs-nightly/group__TopicAliasing.html)用于机制解释，是 nightly 文档而非本机验证版本。本批不编译 Eigen。

<a id="g11-section-6"></a>

<a id="g11-topic-55"></a>
<a id="g11-topic-56"></a>
<a id="g11-topic-57"></a>
<a id="g11-topic-58"></a>
<a id="g11-topic-59"></a>
<a id="g11-topic-60"></a>
<a id="g11-topic-61"></a>
<a id="g11-topic-62"></a>
<a id="g11-topic-63"></a>
<a id="g11-topic-64"></a>
<a id="g11-topic-65"></a>
<a id="g11-topic-66"></a>
<a id="g11-topic-67"></a>

## 6. 传感器采集、通道语义与快照回收

### 6.1 FIFO 与 latest-value 服务不同需求

驱动适配层把 vendor packet 转为规范样本，附测量时间、clock domain 和 sequence。timestamp 回答“何时”，sequence 帮助发现丢失、乱序和重启；二者不能互相替代。拥塞策略应按数据意义选阻塞、丢旧、丢新或进入 fault。

连续位置状态可能只需最新值；逐个排空百毫秒历史会使控制长期落后。Stop、ResetFault、交易或边沿事件则不能随意覆盖中间项。latest-value 与 FIFO 是两种合同，不是同一个 queue 调小容量。

### 6.2 原子发布指针没有证明存储可复用

双缓冲先写 inactive，再发布索引，只解决发布顺序的一部分。读者可能仍在读 A，写者发布 B 后立刻复写 A 会形成竞争。需要阶段握手、读者 pin、引用拥有或回收协议。对非 atomic payload 使用“读版本号—复制—再读版本号”，即使最后丢弃副本，也不能消除复制期间已经发生的 C++ data race。

实验使用受 mutex 保护的完整 Snapshot：writer 在锁内发布，reader try_lock 成功才整体复制，失败不修改旧值。它证明 generation 字段关系，并明确不是 lock-free 或 hard-RT 方案。真正无等待回收是独立设计问题，不拿一个双缓冲图冒充实现。

<a id="g11-section-7"></a>

<a id="g11-topic-68"></a>
<a id="g11-topic-69"></a>
<a id="g11-topic-70"></a>
<a id="g11-topic-71"></a>
<a id="g11-topic-72"></a>
<a id="g11-topic-73"></a>
<a id="g11-topic-74"></a>
<a id="g11-topic-75"></a>
<a id="g11-topic-76"></a>
<a id="g11-topic-77"></a>
<a id="g11-topic-78"></a>
<a id="g11-topic-79"></a>
<a id="g11-topic-80"></a>
<a id="g11-topic-81"></a>
<a id="g11-topic-82"></a>

## 7. 估计、控制与硬件边界

### 7.1 Single writer 保持算法状态一致

估计器的状态向量、协方差和历史由一个执行上下文修改，多传感器输入先处理时钟映射、排序和迟到策略。摄像头 t0 的观测在 t0+50ms 才处理，算法应决定回溯、预测、丢弃或乱序更新，不能把 return 时间替换状态有效时间。

控制器一次 update 固定一份状态与目标 snapshot；逐字段读取不同 generation 可能组成从未存在过的配置。控制器可持有积分/滤波状态，但不直接发 ROS、重新解析配置或打开文件。单写者减少锁和一致性负担，不自动证明数值稳定。

### 7.2 限幅、速率限制与执行器 I/O

saturation 限制数值范围，rate limit 限制每单位时间变化，积分器还需 anti-windup 协调。它们不能用同一个 clamp 替代。实验仅用有界 PD 控制和单自由度积分 plant，不实现 PID anti-windup，也不宣称真实机器人稳定。

硬件接口返回规范状态和写入结果，不把 vendor 类型扩散进 core。若 read/write 有可分析上界，合并到一个循环减少 handoff；若可能堵塞，则隔离到 I/O 域并为延迟、丢包和 freshness 建模。C SDK/驱动边界继续遵守 [G8](g08-abi-and-c-interop.md) 的分配域、异常与句柄规则。

<a id="g11-section-8"></a>

<a id="g11-topic-83"></a>
<a id="g11-topic-84"></a>
<a id="g11-topic-85"></a>
<a id="g11-topic-86"></a>
<a id="g11-topic-87"></a>
<a id="g11-topic-88"></a>
<a id="g11-topic-89"></a>
<a id="g11-topic-90"></a>
<a id="g11-topic-91"></a>
<a id="g11-topic-92"></a>
<a id="g11-topic-93"></a>
<a id="g11-topic-94"></a>
<a id="g11-topic-95"></a>

## 8. 看门狗、故障锁存与命令仲裁

### 8.1 安全动作必须由物理系统定义

主机可能 hang、crash 或失联；执行器不能无限保持上一次危险输出。看门狗（watchdog）应尽量靠近驱动/MCU，并与独立安全链分层。软件 E-stop topic 可以传播意图，但不是硬件安全链的替代，也不构成认证结论。

safe state 可能是受控制动、失能、保持或其他动作，不能普遍等同“输出 0”。本章仿真把 0 作为模型内安全命令，只用于状态机实验，禁止直接据此驱动硬件。

### 8.2 状态、授权与超时共同控制输出

用 Initializing/Standby/Active/Fault/Emergency/ShuttingDown 等明确状态代替互相冲突的 bool。某些 fault 应锁存，直到明确复位条件成立；下一帧正常不能自动恢复动力。多个 planner、teleop、校准和安全源先由 arbiter 决定优先级、模式、租约和有效期，再进入控制器。

RT↔Non-RT 通道传经过验证的完整状态、命令或配置。普通 middleware 发布与日志放到非实时端；[realtime_tools Jazzy](https://control.ros.org/jazzy/doc/realtime_tools/doc/index.html)提供面向这类边界的工具，但使用工具名不自动满足端到端时限。

<a id="g11-section-9"></a>

<a id="g11-topic-96"></a>
<a id="g11-topic-97"></a>
<a id="g11-topic-98"></a>
<a id="g11-topic-99"></a>
<a id="g11-topic-100"></a>
<a id="g11-topic-101"></a>
<a id="g11-topic-102"></a>
<a id="g11-topic-103"></a>
<a id="g11-topic-104"></a>
<a id="g11-topic-105"></a>
<a id="g11-topic-106"></a>
<a id="g11-topic-107"></a>
<a id="g11-topic-108"></a>
<a id="g11-topic-109"></a>
<a id="g11-topic-110"></a>
<a id="g11-topic-111"></a>
<a id="g11-topic-112"></a>
<a id="g11-topic-113"></a>
<a id="g11-topic-114"></a>
<a id="g11-topic-115"></a>
<a id="g11-topic-116"></a>
<a id="g11-topic-117"></a>

## 9. ROS 2、QoS 与借出缓冲区

### 9.1 集成层不能接管未声明的控制责任

ROS adapter 依赖普通 C++ core，而非 Controller 继承 Node。这样算法可在 unit、replay、仿真和硬件部署间复用。Executor 决定 callbacks 在何时何线程执行；callback groups、组合进程与多线程配置会改变交错，不能把 ROS timer 当作具有硬期限的 motor scheduler。

本章固定以 Jazzy 文档线解释概念，不追逐“当前最新发行版”。RMW、传输、序列化、进程拓扑和具体版本必须随部署记录；ros2_control 管理控制器与硬件生命周期，但应用的分配、阻塞和回调仍由项目分析。configure/activate/read-write/deactivate/error/cleanup 应与物理状态关联。

### 9.2 QoS 是数据合同，不是安全保证

History/Depth 决定积压语义，Reliability 决定传输保证，Durability 决定迟加入者的历史数据，Deadline/Lifespan/Liveliness 描述发布间隔、数据有效期及活跃性。配对不兼容可能根本不通信。高频 sensor profile 常选择 best effort 和小队列，但具体关键测量应按需求重选；reliable 不等于及时，不等于 actuator watchdog。[ROS 2 Jazzy QoS 文档](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst)

### 9.3 Zero-copy 必须说明减少了哪次复制

intra-process 转移、shared-memory transport、middleware loan 是不同路径。借出缓冲发布后所有权归还 middleware，不能继续读取原 loan；若要保留，需要新的合法拥有/复制合同。底层是否支持 loan、是否分配和是否无锁取决于实现，不能用“zero-copy”一词包办。[Jazzy RMW 接口合同](https://github.com/ros2/rmw/blob/jazzy/rmw/include/rmw/rmw.h)还区分参数错误的提前失败与已经归还所有权的路径；调用失败后也必须按具体函数合同处理，而非一律继续使用原指针。

少复制可能降低带宽，也会耦合池压力、回收与慢读者。原稿的 loan 规则保留，但本批没有安装 ROS、运行 RMW、验证 QoS 配对或 loan API，属于文档回查而非运行证据。

<a id="g11-section-10"></a>

<a id="g11-topic-118"></a>
<a id="g11-topic-119"></a>
<a id="g11-topic-120"></a>
<a id="g11-topic-121"></a>
<a id="g11-topic-122"></a>
<a id="g11-topic-123"></a>
<a id="g11-topic-124"></a>
<a id="g11-topic-125"></a>
<a id="g11-topic-126"></a>
<a id="g11-topic-127"></a>
<a id="g11-topic-128"></a>
<a id="g11-topic-129"></a>

## 10. 大载荷、配置事务与安全过滤

### 10.1 数据布局由访问模式决定

1920×1080×3 字节约 6.22 MB，一次完整复制在 30 FPS 下约 187 MB/s 的数据量，尚未计读写总线流量和额外拷贝。共享不可变帧可服务感知、录制与可视化，但慢读者可能长期占用池；必须限制租约或退化策略。

关节状态若每次同时用位置、速度、力矩，AoS 可能自然；只扫描一个字段时 SoA 值得测量。固定结论“机器人都应 SoA”与 G6 的访问模式原则冲突。

### 10.2 一次发布一套合法参数

Kp/Ki/Kd 逐个 atomic 更新不保证读者看到同一套参数。非实时端构造、校验并预计算整个 ControllerConfig，再在安全点发布 generation，旧读者结束后回收。目标位置和速度也应同代消费。

安全过滤不仅接受 desired command，还接受 mode、当前状态、限制、故障和时间。合法数值的过期命令也可能危险；invalid input 应确定性地导致 safe command 或 fault，而不是继续上一次控制输出。

<a id="g11-section-11"></a>

<a id="g11-topic-130"></a>
<a id="g11-topic-131"></a>
<a id="g11-topic-132"></a>
<a id="g11-topic-133"></a>
<a id="g11-topic-134"></a>
<a id="g11-topic-135"></a>
<a id="g11-topic-136"></a>
<a id="g11-topic-137"></a>
<a id="g11-topic-138"></a>
<a id="g11-topic-139"></a>
<a id="g11-topic-140"></a>
<a id="g11-topic-141"></a>
<a id="g11-topic-142"></a>
<a id="g11-topic-143"></a>
<a id="g11-topic-144"></a>
<a id="g11-topic-145"></a>
<a id="g11-topic-146"></a>
<a id="g11-topic-147"></a>

## 11. 故障隔离、观测与测试阶梯

### 11.1 不让低关键性失败拖垮高关键性路径

感知超时、UI 崩溃和总线故障是不同 failure domain。控制器可按合同使用有限时间的旧状态、预测或安全模式，但不无限等待视觉。RT telemetry 写有界预分配记录，非实时线程格式化/落盘；缓冲满也要有丢弃或降级策略。

观测包括 wake/执行时间、deadline miss、数据 age、乱序/丢失、队列深度、I/O 耗时和故障。平均值、p99 与 max 都来自有限样本，观测 max 不是理论上界。sequence、generation 与各时钟域时间戳共同支持追踪。

### 11.2 Simulation、replay、HIL 各有不同覆盖

算法单元测试使用确定输入；replay 固定测量时间和事件序列；SIL 连接软件 plant；HIL 再纳入部分真实硬件、驱动和时序；最终真机还要验证物理安全。仿真时间与主机时钟应分开，因此一个 replay 通过不说明部署 jitter 达标。

边界测试覆盖 NaN、Inf、近零/过大 dt、时间跳变、迟到、掉线、限幅、故障锁存和复位。控制 phase 分配计数也是特定观测，不证明所有输入或库路径都无分配。本批只做单自由度 SIL 风格逻辑与桌面时序观察，HIL、ROS、page fault、真实驱动及安全认证全部未验证。

<a id="g11-section-12"></a>

<a id="g11-topic-148"></a>
<a id="g11-topic-149"></a>
<a id="g11-topic-150"></a>
<a id="g11-topic-151"></a>
<a id="g11-topic-152"></a>
<a id="g11-topic-153"></a>
<a id="g11-topic-154"></a>
<a id="g11-topic-155"></a>
<a id="g11-topic-156"></a>
<a id="g11-topic-157"></a>
<a id="g11-topic-158"></a>
<a id="g11-topic-159"></a>
<a id="g11-topic-160"></a>
<a id="g11-topic-161"></a>
<a id="g11-topic-162"></a>
<a id="g11-topic-163"></a>
<a id="g11-topic-164"></a>

## 12. 执行等级与集成拓扑

### 12.1 RT-safe 必须展开为具体条件

RT_SAFE、INIT_ONLY、NON_RT、BLOCKING 可以用作项目标签，但必须附“何平台、何输入规模、何分配/等待/异常限制”。标注 noexcept 或 high priority 都不能替代这些条件。数据通道应同时写明生产/消费频率、允许丢失、最旧可用 age 和关闭后行为。

线程划分来自阻塞、所有权和时限：采集、估计、控制、ROS、遥测和感知可能分开；若 I/O 有界且任务周期一致，read-estimate-control-write 合并又可能更简单。组件同进程减少某些 IPC 成本，却扩大失败耦合；一节点一进程也不是默认正确。

### 12.2 时间对齐与命令授权

近似传感器同步的 tolerance 影响物理一致性和丢弃率；插值或积分到目标时间是算法选择，不是只加 mutex。估计 state(t_est) 供 t_now 控制时，需判断 age、预测误差和降级条件。命令也有自身生成时间和有效期。

Disabled → Arming → Active、Active → Fault 与 Emergency 转移应指定发起者和条件。Shutdown 的验收终点是执行器进入定义好的状态，不只是线程退出。实验只涵盖 standby/active/fault/shutdown 简化机，未实现多源仲裁或真实 arming 流程。

<a id="g11-section-13"></a>

<a id="g11-topic-165"></a>
<a id="g11-topic-166"></a>
<a id="g11-topic-167"></a>
<a id="g11-topic-168"></a>
<a id="g11-topic-169"></a>
<a id="g11-topic-170"></a>
<a id="g11-topic-171"></a>
<a id="g11-topic-172"></a>
<a id="g11-topic-173"></a>
<a id="g11-topic-174"></a>
<a id="g11-topic-175"></a>
<a id="g11-topic-176"></a>
<a id="g11-topic-177"></a>

## 13. 输出不变量与工程分层

### 13.1 先检查是否允许动作，再检查数值

允许 actuation 至少需要：Active、状态有效、clock domain 可比较、时间非未来且足够新、目标未过期、输入输出 finite、数值/速率在限制内、执行器健康。异常数值不能通过 clamp 被“洗白”，写入失败也不能只写日志后继续 Active。

安全过滤决定模型内输出，底层 watchdog 处理上层停止更新；二者覆盖不同故障。真实 brake/drive 状态反馈、不可逆硬件动作和功能安全分析不在本章桌面实验里。

### 13.2 依赖方向与性能优先级

core 放 units/state/estimation/control/safety，runtime 放通道/生命周期，hardware 与 ROS 是 adapter，simulation 消费相同 core。内部同工具链可用 virtual driver；长期第三方二进制边界应回到小而明确的 C 合同，不能把 C++ 类布局当通用 ABI。

优化先修错误时间域、不可控阻塞和无界通道，再查分配/页面、数据复制、缓存布局，最后才是指令级优化。把最快的数学核放在错误执行域，仍不能满足控制系统合同。

<a id="g11-section-14"></a>

<a id="g11-topic-178"></a>
<a id="g11-topic-179"></a>
<a id="g11-topic-180"></a>
<a id="g11-topic-181"></a>
<a id="g11-topic-182"></a>
<a id="g11-topic-183"></a>
<a id="g11-topic-184"></a>
<a id="g11-topic-185"></a>
<a id="g11-topic-186"></a>

## 14. 可运行学习案例的范围

### 14.1 robot-control-core 的阶段产物

原项目阶段从纯数学、固定步长 plant、真实时钟循环，扩展到 sensor thread、非实时命令、故障注入、分配审计，最后 ROS adapter。完整实验保留其学习顺序，但明确划出本批切片：一个有界 PD 控制器、一个单自由度积分 plant、独立的快照并发测试、计数插桩及 1000 周期的主机时序记录。

它不是整机调度器。多速率独立 sensor/control/ROS 线程、真实 bus、复杂估计器、ROS 参数生命周期和 HIL 继续是项目练习要求，不会因为 Markdown Edition 完成而变成已经实现。

### 14.2 三种问题使用三种判据

确定性注入要求非法输入使 fault 锁存且输出为模型定义的 0，正常帧不能自动恢复；显式 reset 后仍需 activate。快照测试要求观测到的所有字段属于同一 generation。分配测试要求当前线程该阶段的可替换 C++ 分配调用计数为 0，并先确认计数器能检测分配。

时序则完整记录 wake offset、执行耗时和 deadline miss，不以固定 ns 阈值判 PASS。安全逻辑通过与 timing observation recorded 是不同状态。G11 的代码、运行平台和未验证部分见 §16 与批次记录。

<a id="g11-section-15"></a>

<a id="g11-topic-187"></a>
<a id="g11-topic-188"></a>
<a id="g11-topic-189"></a>
<a id="g11-topic-190"></a>
<a id="g11-topic-191"></a>
<a id="g11-topic-192"></a>
<a id="g11-topic-193"></a>
<a id="g11-topic-194"></a>
<a id="g11-topic-195"></a>
<a id="g11-topic-196"></a>
<a id="g11-topic-197"></a>
<a id="g11-topic-198"></a>
<a id="g11-topic-199"></a>
<a id="g11-topic-200"></a>
<a id="g11-topic-201"></a>
<a id="g11-topic-202"></a>
<a id="g11-topic-203"></a>
<a id="g11-topic-204"></a>
<a id="g11-topic-205"></a>

## 15. 常见误判与语言选择

### 15.1 相近的词往往掩盖不同合同

fast 不是 real-time；高优先级不是期限保证；reserve 不是硬容量；接收时间不是测量时间；单位相同不代表同一时钟域；latest-state 不等于必须处理每一帧；reliable 不等于安全；zero-copy 不等于零生命周期成本；shared_ptr 不等于共享写入安全。

同样，controller 直接依赖 vendor packet、关键循环偶尔日志、最后一次 clamp 代替 safety、软件 topic 代替硬件 E-stop、为“微服务风格”拆出大量 ROS 进程，都绕开了真实合同。应逐条回到时限、失效模式和所有权，而非靠框架名称作答。

### 15.2 语言是工具选择，不是物理保证

C++ 与既有数值库、ROS 和硬件 SDK 集成常有现实价值；Rust 可降低安全代码中的生命周期/数据竞争风险；Zig 的显式资源与 C 互操作有助于某些底层组件。但三者都不能自动证明 deadline、jitter、驱动行为或物理安全，也不能用语言标签代替具体依赖版本与团队能力评估。

更多语言带来 FFI、构建、调试、错误与资源域成本。先把控制 core 与 adapter 边界设计清楚，再考虑替换局部实现，最后在 [G12](g12-cpp-zig-rust.md) 统一讨论证明责任。

<a id="g11-section-16"></a>

## 16. 完整实验：逻辑仿真、快照与时序

### 16.1 分开运行，分开解释

G11-C1 将确定性控制逻辑和主机时序分为两个程序。使用与 G10 同一条 `verify_synthesis.py` 命令，但分类记录，不把模型故障测试、分配计数和 jitter 混成一个 PASS。

control_test 要求八类注入进入 Fault、保持模型定义的 0 输出、正常帧不自动复位、显式 reset/activate 与 shutdown 生效。10000 个逻辑步检查 finite、幅值/速率和受观测的 C++ 分配调用数。并发快照用 generation 与所有字段关联，允许跳过中间代，但不允许混代。

两个错误变体分别删除 freshness 判定、在发布时破坏字段关系；均要求编译成功后以目标 invariant 和固定退出码拒绝。第三个变体在 step 内直接调用 allocation function，必须被分配计数拒绝。它们检验判据能辨认错误，不是声称原实现含这些错误。

### 16.2 完整文件

<!-- s-lab {"id":"G11-C1","mode":"control"} -->

[完整实验 · G11-C1 · control.hpp]

<!-- s-file {"path":"control.hpp"} -->
```cpp
#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <mutex>
namespace robot {
enum class Mode { standby, active, fault, shutdown };
struct Snapshot {
    std::uint64_t generation{}, sensor_ns{}, command_ns{};
    double position{}, velocity{}, target{};
};
class Mailbox {
    std::mutex mutex_;
    Snapshot value_{};
public:
    void publish(Snapshot value) {
        std::lock_guard lock{mutex_};
        value_ = value;
    }
    bool try_read(Snapshot& output) {
        std::unique_lock lock{mutex_, std::try_to_lock};
        if (!lock.owns_lock()) return false;
        output = value_;
        return true;
    }
};
class Controller {
    Mode mode_{Mode::standby};
    double previous_{};
    static bool valid(const Snapshot& s, std::uint64_t now) noexcept {
        return s.generation != 0 && s.sensor_ns <= now && s.command_ns <= now
            && now - s.sensor_ns <= 5'000'000
            && now - s.command_ns <= 50'000'000
            && std::isfinite(s.position) && std::isfinite(s.velocity)
            && std::isfinite(s.target);
    }
    double fault() noexcept { mode_ = Mode::fault; previous_ = 0; return 0; }
public:
    Mode mode() const noexcept { return mode_; }
    bool activate() noexcept {
        if (mode_ != Mode::standby) return false;
        mode_ = Mode::active;
        return true;
    }
    bool reset(const Snapshot& s, std::uint64_t now) noexcept {
        if (mode_ != Mode::fault || !valid(s, now)) return false;
        mode_ = Mode::standby;
        previous_ = 0;
        return true;
    }
    void shutdown() noexcept { mode_ = Mode::shutdown; previous_ = 0; }
    double step(const Snapshot& s, std::uint64_t now, double dt,
                bool actuator_healthy = true) noexcept {
        if (mode_ != Mode::active) return 0;
        if (!valid(s, now) || !std::isfinite(dt) || dt <= 0 || dt > 0.01
            || !actuator_healthy) return fault();
        const double requested = 20 * (s.target - s.position) - 2 * s.velocity;
        if (!std::isfinite(requested)) return fault();
        const double limited = std::clamp(requested, -5.0, 5.0);
        previous_ = std::clamp(limited, previous_ - 100 * dt, previous_ + 100 * dt);
        return previous_;
    }
};
} // namespace robot
```

[完整实验 · G11-C1 · allocations.hpp]

<!-- s-file {"path":"allocations.hpp"} -->
```cpp
#pragma once
#include <cstddef>
namespace allocations {
extern thread_local bool active;
extern thread_local std::size_t calls;
}
```

[完整实验 · G11-C1 · allocations.cpp]

<!-- s-file {"path":"allocations.cpp"} -->
```cpp
#include "allocations.hpp"
#include <cstdlib>
#include <new>
namespace allocations {
thread_local bool active = false;
thread_local std::size_t calls = 0;
}
namespace {
void count() noexcept { if (allocations::active) ++allocations::calls; }
void* ordinary(std::size_t n) {
    count();
    if (void* p = std::malloc(n ? n : 1)) return p;
    throw std::bad_alloc{};
}
void* aligned(std::size_t n, std::align_val_t a) {
    count();
    void* p = nullptr;
    if (posix_memalign(&p, static_cast<std::size_t>(a), n ? n : 1) == 0) return p;
    throw std::bad_alloc{};
}
}
void* operator new(std::size_t n) { return ordinary(n); }
void* operator new[](std::size_t n) { return ordinary(n); }
void* operator new(std::size_t n, std::align_val_t a) { return aligned(n, a); }
void* operator new[](std::size_t n, std::align_val_t a) { return aligned(n, a); }
void* operator new(std::size_t n, const std::nothrow_t&) noexcept {
    try { return ordinary(n); } catch (...) { return nullptr; }
}
void* operator new[](std::size_t n, const std::nothrow_t&) noexcept {
    try { return ordinary(n); } catch (...) { return nullptr; }
}
void* operator new(std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept {
    try { return aligned(n, a); } catch (...) { return nullptr; }
}
void* operator new[](std::size_t n, std::align_val_t a, const std::nothrow_t&) noexcept {
    try { return aligned(n, a); } catch (...) { return nullptr; }
}
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
void operator delete(void* p, std::align_val_t) noexcept { std::free(p); }
void operator delete[](void* p, std::align_val_t) noexcept { std::free(p); }
void operator delete(void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t, std::align_val_t) noexcept { std::free(p); }
void operator delete(void* p, const std::nothrow_t&) noexcept { std::free(p); }
void operator delete[](void* p, const std::nothrow_t&) noexcept { std::free(p); }
void operator delete(void* p, std::align_val_t, const std::nothrow_t&) noexcept {
    std::free(p);
}
void operator delete[](void* p, std::align_val_t, const std::nothrow_t&) noexcept {
    std::free(p);
}
```

[完整实验 · G11-C1 · control_test.cpp]

<!-- s-file {"path":"control_test.cpp"} -->
```cpp
#include "control.hpp"
#include "allocations.hpp"
#include <atomic>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <new>
#include <thread>
void require(bool ok, int code) {
    if (!ok) { std::cerr << "control invariant=" << code << '\n'; std::exit(code); }
}
int main() {
    using robot::Mode;
    constexpr std::uint64_t now = 100'000'000;
    const robot::Snapshot good{1, now, now, 0, 0, 1};
    // Independent injections: stale sensor, stale command, future, NaN, Inf, bad dt/I/O.
    for (int which = 0; which != 8; ++which) {
        robot::Controller c;
        require(c.activate(), 1);
        require(c.step(good, now, 0.001) > 0, 2);
        auto bad = good;
        double dt = 0.001;
        bool io = true;
        if (which == 0) bad.sensor_ns = now - 5'000'001;
        if (which == 1) bad.command_ns = now - 50'000'001;
        if (which == 2) bad.sensor_ns = now + 1;
        if (which == 3) bad.position = std::numeric_limits<double>::quiet_NaN();
        if (which == 4) bad.target = std::numeric_limits<double>::infinity();
        if (which == 5) dt = 0;
        if (which == 6) dt = 0.02;
        if (which == 7) io = false;
        require(c.step(bad, now, dt, io) == 0 && c.mode() == Mode::fault, 21);
        require(c.step(good, now, 0.001) == 0 && c.mode() == Mode::fault, 22);
        require(!c.activate(), 23);
        require(c.reset(good, now) && c.mode() == Mode::standby, 24);
        require(c.activate(), 25);
        c.shutdown();
        require(c.step(good, now, 0.001) == 0 && c.mode() == Mode::shutdown, 26);
        require(!c.reset(good, now) && !c.activate(), 27);
    }
    // Count replaceable C++ allocation calls in THIS thread / phase only.
    allocations::active = true;
    void* probe = ::operator new(8); // Direct call avoids new-expression elision.
    ::operator delete(probe);
    allocations::active = false;
    require(allocations::calls == 1, 28);
    allocations::calls = 0;
    robot::Controller c;
    c.activate();
    double position = 0, velocity = 0, previous = 0;
    bool valid = true;
    allocations::active = true;
    for (std::uint64_t tick = 1; tick <= 10'000; ++tick) {
        const auto stamp = tick * 1'000'000;
        robot::Snapshot s{tick, stamp, stamp, position, velocity, 1};
        const double command = c.step(s, stamp, 0.001);
        valid = valid && std::isfinite(command) && std::abs(command) <= 5
            && std::abs(command - previous) <= 0.1000001;
        previous = command;
        velocity += command * 0.001;
        position += velocity * 0.001;
    }
    allocations::active = false;
    require(valid && c.mode() == Mode::active, 29);
    require(allocations::calls == 0, 30);
    std::cout << "control verified; tracked_cpp_allocations=" << allocations::calls << '\n';
    // Generation consistency: all fields are copied while holding the same mutex.
    robot::Mailbox box;
    std::atomic<bool> done{};
    std::atomic<bool> midpoint_seen{};
    std::jthread writer([&] {
        for (std::uint64_t gen = 1; gen <= 10'000; ++gen) {
            box.publish({gen, gen, gen, double(gen), double(gen * 2), double(gen * 3)});
            if (gen == 5000)
                while (!midpoint_seen.load()) std::this_thread::yield();
        }
        done.store(true);
    });
    std::size_t observed = 0;
    auto inspect = [&](const robot::Snapshot& s) {
        if (s.generation == 0) return;
        ++observed;
        require(s.sensor_ns == s.generation && s.command_ns == s.generation
            && s.position == double(s.generation)
            && s.velocity == double(s.generation * 2)
            && s.target == double(s.generation * 3), 31);
    };
    robot::Snapshot snapshot{};
    do {
        if (box.try_read(snapshot)) inspect(snapshot);
        if (snapshot.generation == 5000) midpoint_seen.store(true);
    } while (!done.load());
    writer.join();
    require(box.try_read(snapshot), 32);
    inspect(snapshot);
    require(observed > 0 && midpoint_seen && snapshot.generation == 10'000, 33);
    std::cout << "snapshot generations verified\n";
}
```

[完整实验 · G11-C1 · timing.cpp]

<!-- s-file {"path":"timing.cpp"} -->
```cpp
#include "control.hpp"
#include <array>
#include <chrono>
#include <iostream>
#include <thread>
using Clock = std::chrono::steady_clock;
using Ns = std::chrono::nanoseconds;
struct Trace { long long wake_ns, execution_ns; bool missed; };
int main() {
    constexpr int cycles = 1000;
    constexpr auto period = Ns{1'000'000};
    std::array<Trace, cycles> traces{};
    robot::Controller c;
    c.activate();
    double position = 0, velocity = 0;
    const auto start = Clock::now() + std::chrono::milliseconds{5};
    for (int tick = 0; tick != cycles; ++tick) {
        const auto release = start + tick * period;
        std::this_thread::sleep_until(release);
        const auto wake = Clock::now();
        const auto logical = std::uint64_t(tick + 1) * 1'000'000;
        robot::Snapshot s{std::uint64_t(tick + 1), logical, logical,
                          position, velocity, 1};
        const double command = c.step(s, logical, 0.001);
        velocity += command * 0.001;
        position += velocity * 0.001;
        const auto finish = Clock::now();
        traces[tick] = {std::chrono::duration_cast<Ns>(wake - release).count(),
                       std::chrono::duration_cast<Ns>(finish - wake).count(),
                       finish > release + period};
    }
    if (!std::isfinite(position) || c.mode() != robot::Mode::active) return 2;
    // All formatting is outside the sampled phase. No deadline threshold is a PASS oracle.
    std::cout << "position=" << position << '\n';
    for (int i = 0; i != cycles; ++i)
        std::cout << i << ',' << traces[i].wake_ns << ','
                  << traces[i].execution_ns << ',' << traces[i].missed << '\n';
}
```

### 16.3 观察合同

timing 的首行保留最终 plant 状态，后续 1000 行为 `tick,wake_offset_ns,execution_ns,deadline_missed`。绝对计划时刻为 start + tick × 1ms；迟到时继续执行下一逻辑步，可能出现连续赶进度。本实验没有丢周期、重同步或真实控制补偿策略，记录应据此解释。

执行器计算 p50/p99/max 和 miss count，记录为 OBSERVED；无论本机 jitter 大小都不声称 hard real-time。程序正常返回仅检查模型状态与有限值。没有 affinity、mlock、特权调度、真实传感器、ROS、HIL 或硬件 actuation；也没有检测整个进程 malloc 或 page fault。

<a id="g11-section-17"></a>

## 17. 机器人路径复核记录

### 17.1 十六个审查维度

| 维度 | 应留下的回答 |
| --- | --- |
| Physical / units / frame | 物理量、规范单位、坐标变换方向 |
| Time / freshness | 时钟域、测量时刻、age 与失效界限 |
| Ownership / writer | buffer owner、借用期限、状态修改者 |
| Execution / blocking | 关键域、等待点、平台假设 |
| Memory / bounds | 分配面、容量、循环上界 |
| Numerics / safety | finite、稳定性条件、fault 与安全动作 |
| Shutdown / middleware | 停止后硬件状态、传输与回收合同 |
| Measurement | 采样条件、时间分布和未覆盖路径 |

### 17.2 本批的结论边界

本章可执行部分检验简化控制模型、锁存、generation 和可替换 C++ 分配调用；采样的是本机调度，不是 Linux 实时部署。生成一致性由 mutex 整体复制提供，TSan 只补充动态观察，不能据无报告证明双缓冲无锁协议。零命令仅是仿真约定，不能当作真机操作建议。

<a id="g11-section-18"></a>

## 18. Final Gate

先闭卷写出条件、机制与反例，再核对下一节；保留原稿问题，不在题干下先给结论。

### 18.1 Real-Time

1. Fast 和 real-time 有什么根本区别？
2. Period、deadline、jitter 分别是什么？
3. 为什么 average latency不能证明 real-time behavior？
4. `SCHED_FIFO` 为什么不等于 hard-real-time guarantee？

### 18.2 Time

1. measurement timestamp 和 receive timestamp有什么区别？
2. 两个相同单位的 timestamp 为什么仍可能不能相减？
3. `steady_clock` 适合解决什么问题？
4. delayed camera observation进入 estimator时为什么不能假装是“现在”？

### 18.3 Memory

1. 为什么 RT loop避免 general heap allocation？
2. `reserve()` 为什么不等于 fixed-capacity guarantee？
3. pre-touch解决的是哪类成本？
4. 为什么 C++23 中不能直接假定有 `std::inplace_vector`？

### 18.4 Concurrency

1. 为什么 single-writer state对机器人特别有价值？
2. latest-value channel 与 FIFO queue适合的语义有什么区别？
3. 为什么 double-buffer仍然有 lifetime/reuse问题？
4. 为什么 RT loop通常不应等待 non-RT mutex？

### 18.5 Numerics

1. 为什么裸 `double` 在 robot API中容易制造单位错误？
2. coordinate frame为什么属于 type/API semantics？
3. quaternion使用时至少要统一哪些 conventions？
4. fixed-size numerical representation为什么常适合 control core？

### 18.6 Control

1. 为什么 Controller 应该使用 consistent snapshot？
2. saturation 和 rate limiting分别限制什么？
3. 为什么 stale command可能比 numeric out-of-range一样危险？
4. cancellation/fault发生时 controller应该如何保持 invariant？

### 18.7 Hardware

1. 为什么 vendor SDK type不应进入 domain core？
2. hardware read可能阻塞时为什么要重新考虑 thread topology？
3. actuator watchdog为什么应该尽量靠近硬件？

### 18.8 ROS 2

1. 为什么 ROS callback executor不应该自动等价于 motor-control scheduler？
2. QoS为什么必须由 message semantics决定？
3. SensorDataQoS 为什么典型采用 best-effort/small depth？
4. loaned message publish后为什么不能继续使用？
5. 为什么普通 ROS publisher不适合直接放进 hard-RT update loop？

### 18.9 Safety

1. 为什么 software topic不能替代真正安全 E-stop architecture？
2. fault为什么通常应该进入显式 state machine？
3. 如何定义“允许向 actuator 输出 command”的完整 invariant？

<a id="g11-section-19"></a>

## 19. Final Gate · 参考答案与常见误判

答案按上一节分组和题号对应。重点是推理与适用条件，不把关键词复述当作通过。

### 19.1 Real-Time

1. fast 只说明某种耗时统计；real-time 要在条件下满足时限/可预测性。短平均值不能担保每次截止期限。

2. period 是计划 release 间隔，deadline 是完成期限，jitter 是指定事件相对计划时刻的偏移变化；必须说明测的是 wake 还是完成。

3. 平均抹去尾部，有限样本 max 也不是 WCET。需要平台/负载假设、阻塞上界和部署证据。

4. 调度策略不消除中断、固件、page fault、锁、驱动和硬件干扰；优先级提升也可能伤害其他关键线程。

### 19.2 Time

1. 前者描述物理采样时刻，后者描述传输后的接收时刻；用后者替代会把可变通信延迟混入估计。

2. 单位相同仅表示刻度，原点、速度和跳变规则可能不同；先建立 clock-domain 转换及误差。

3. 适合进程内持续时间、超时和相对调度，不受 wall-clock 调整的同类影响；不能自动对应设备测量时钟。

4. 估计值属于过去，需按算法回溯、预测、乱序更新或丢弃。假装现在会把时延误差变成状态误差。

### 19.3 Memory

1. 问题在于 allocator 及页面路径的时间边界不明，不是每次分配都慢。初始化分配与运行期回收也要分别审查。

2. reserve 后还能超过 capacity；真正有界接口应拒绝超限或用固定表示。array 同时意味着所有元素已构造。

3. 把首次触页等部分成本提前，不证明以后没有页面、缓存或 OS 干扰；需在目标平台验证。

4. 它不属于 C++23 标准设施。应选 array+size 或明确依赖的静态容器，不把未来设施写成本基线。

### 19.4 Concurrency

1. 估计器/控制器每份可变状态有一个写者，减少复合不变量与锁域；读者仍需合法快照与生命周期。

2. 连续状态允许跳过中间代时适合 latest；每个事件都有意义或顺序要求时用 FIFO。不能仅凭频率决定。

3. 发布新的索引后旧读者可能仍访问原槽；重用必须等读者结束或有回收协议，release/acquire 本身不够。

4. 持锁者可能因非实时工作长期停顿，引入优先级反转。try_lock+旧值策略也需 freshness，且不是自动硬时限证明。

### 19.5 Numerics

1. double 不区分角度、弧度、长度和力矩；单位进入类型/schema 才能限制误用。数值相等不是物理相同。

2. 同一个三元组在不同 frame 含义不同；变换方向和可组合性属于接口正确性，不只是注释。

3. 至少规定元素顺序、乘法方向、主动/被动约定及单位长度维护；否则数学形式相同仍可能旋转反向。

4. 尺寸和工作量容易限定，减少动态 resize；但其他表达式、临时或库路径仍需检查，不是全链零分配保证。

### 19.6 Control

1. 分开读取可能拼出不同 generation 的状态/目标，控制计算需固定同代输入；snapshot 自身的取得也要合法。

2. saturation 限幅值，rate limiting 限随时间变化；积分控制还要 anti-windup，不是一次 clamp 能完成。

3. 目标可能已不适合当前状态，数值合法也可能产生危险动作；有效期与授权是输出条件。

4. 保持 fault 锁存和模型定义的安全输出，停止非法更新，显式复位再激活。真实 safe state 由物理系统决定。

### 19.7 Hardware

1. vendor 单位、布局与时钟应在 adapter 规范化，否则算法/仿真被硬件接口绑住。

2. 阻塞会侵蚀控制期限；可隔离 I/O，但新增 handoff、延迟和时钟责任。若 I/O 有界，单循环可能更合理。

3. 主机挂死时上层软件已无法自救，靠近 actuator 的独立 watchdog 可在失联时执行本地策略；仍需硬件安全设计。

### 19.8 ROS 2

1. Executor 为 callbacks 提供执行机制，不自动给出 motor loop 期限保证；多线程/group 还会改变并发交错。

2. 不同数据允许的丢失、过期、积压和迟加入行为不同；reliable 并非所有场景最合适，兼容性也要核对。

3. 常重视及时最新测量而非补齐每帧；关键低频传感仍可能需要其他合同，不能机械照搬。

4. 发布归还 loan 的所有权，继续访问不在原借用范围；需要按该 RMW/API 合同重新获得合法对象。

5. 普通发布路径可能涉及不可控分配、锁和 I/O；关键端应通过经过分析的 handoff 交给非实时端。

### 19.9 Safety

1. 软件消息仍依赖进程、调度、通信和供电，无法覆盖它们共同失效；真正 E-stop 需要独立、经风险分析的安全链。

2. 状态机把进入、锁存、复位和授权条件显式化，避免多个 bool 形成非法组合，也便于注入复核。

3. Active、有效且新鲜状态/目标、可比较时钟、非未来时间、finite、幅值/速率限制和健康 actuator 同时成立；否则进入明确安全策略。

<a id="g11-section-20"></a>

## 20. 参考资料与验证边界

ROS 概念回查固定 Jazzy 文档线：[QoS](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Concepts/Intermediate/About-Quality-of-Service-Settings.rst)、[实时示例](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Demos/Real-Time-Programming.rst)、[Controller Manager](https://control.ros.org/jazzy/doc/ros2_control/controller_manager/doc/userdoc.html)、[realtime_tools](https://control.ros.org/jazzy/doc/realtime_tools/doc/index.html)。这些是概念与部署回查，不是本机安装/运行记录。实验工具链、原始时序、覆盖面与未知项见[批次记录](learning/synthesis-revision.md)及[原始结果](learning/synthesis-results.json)。

本章使用 [Editorial Profile v1.0](editorial-profile.md)，Markdown 是内容与完整实验事实源。PDF **NOT BUILT / NOT VALIDATED**；长文件与表格的源稿风险不等于实际分页已验收。
