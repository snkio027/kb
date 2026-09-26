# C++ Systems Track · G11 Robotics Systems with Modern C++23

**Version:** 1.0  
**Status:** Complete / Frozen Review Baseline  
**Language Baseline:** C++23  
**Prerequisites:** G0–G10  
**Primary Environment:** Linux / POSIX-class robotics systems  
**Integration Layer:** ROS 2 / `ros2_control` / native device SDKs  
**Scope:** Real-time / Determinism / Control Loops / Time / Sensor Acquisition / Coordinate Frames / Numerical Representation / State Estimation / Control / Hardware Interface / Memory Discipline / Threading / Zero-copy / ROS 2 / DDS-QoS / Safety / Watchdogs / Simulation / HIL / Observability / Testing  
**Purpose:** 建立一套从 **Physical World → Sensors → Estimation → Control → Actuation** 的现代 C++ 机器人系统工程模型。

截至 2026 年 9 月，ROS Index 将 Humble、Jazzy、Kilted 和 Lyrical 列为活跃 ROS 2 distributions，Rolling 是开发发行线。本章不绑定某一个 distribution，而把 ROS 2 视为机器人系统的 integration/middleware layer；具体 API 应始终按照项目所选发行版验证。:chatgpt-content-reference{index="0"}

---

# 0. G11 的定位

G10 构建的是：

```text
Input
  ↓
Queue
  ↓
Processing
  ↓
Output
```

这是一个典型软件系统。

机器人增加了一个决定性的东西：

# **Physical Time**

程序不再只需要：

> 算对。

还可能要求：

> **在某个时间之前算对。**

一个控制输出：

```text
correct answer
```

如果晚了 100 ms，

可能已经是：

```text
wrong action
```

因此机器人 C++ 的统一模型是：

```text
Correctness
×
Timing
×
Lifetime
×
Numerics
×
Physical Semantics
×
Failure Behavior
```

---

# 1. 从软件系统进入物理系统

机器人典型闭环：

```text
Physical World
      │
      ▼
   Sensors
      │
      ▼
Acquisition / Timestamp
      │
      ▼
State Estimation
      │
      ▼
Planning / Command
      │
      ▼
Control
      │
      ▼
Actuator Command
      │
      ▼
   Hardware
      │
      └──────────────▶ Physical World
```

这不是普通单向 pipeline。

而是：

# **Feedback Loop**

输出会改变下一次输入。

---

# 2. 机器人系统的三个 Execution Planes

本章建议把机器人软件至少分成三个 execution domains：

```text
┌──────────────────────────────────────────────┐
│ Non-Real-Time / Orchestration Plane          │
│ ROS graph / config / logging / UI / planning │
└──────────────────┬───────────────────────────┘
                   │ snapshots / commands
                   ▼
┌──────────────────────────────────────────────┐
│ Deterministic / Real-Time-ish Compute Plane  │
│ estimation / control / safety / fast state   │
└──────────────────┬───────────────────────────┘
                   │ bounded data
                   ▼
┌──────────────────────────────────────────────┐
│ Hardware I/O Plane                           │
│ CAN / EtherCAT / serial / device SDK / GPIO  │
└──────────────────────────────────────────────┘
```

关键思想：

> **不要默认让 ROS callbacks、网络、日志、动态配置和 motor control loop 共享同一个 execution context。**

---

# Part I · Real-Time 到底是什么意思

# 3. Real-Time ≠ Fast

这是机器人领域最必须消灭的误区。

一个程序：

```text
average latency = 10 µs
```

但偶尔：

```text
max latency = 200 ms
```

它可能非常“快”，

却完全不适合作为严格周期控制器。

Real-time 更关心：

> **时间行为是否具有可接受的上界和可预测性。**

---

# 4. Period

周期控制：

```text
t0
│ update
├──────── T ────────┐
                    t1
                    │ update
                    ├──── T ────▶
```

如果：

```text
frequency = 1 kHz
```

理论 period：

```text
T = 1 ms
```

---

# 5. Deadline

假设每个 control cycle：

```text
release at t
```

必须在：

```text
t + 1 ms
```

之前完成。

那么：

```text
deadline = 1 ms
```

如果：

```text
execution = 200 µs
```

有：

```text
800 µs margin
```

但这只是一次 observation。

真正关心的是：

> worst-case / high-percentile / bounded execution behavior。

---

# 6. Jitter

理想 wakeup：

```text
0 ms
1 ms
2 ms
3 ms
```

实际：

```text
0
1.012
1.997
3.041
3.998
```

偏离期望时刻的变化：

> **Jitter — 抖动**

机器人 control 中往往：

```text
latency important
+
jitter equally important
```

---

# 7. Hard / Firm / Soft Real-Time

## Hard Real-Time

Deadline miss：

> 不允许发生于系统正确性假设之内。

它需要非常强的：

```text
timing analysis
OS/hardware assumptions
bounded operations
```

---

## Firm Real-Time

结果超过 deadline：

> 已经没有价值，

但偶发 miss 不一定造成灾难。

---

## Soft Real-Time

Deadline miss：

> 降低质量，

但系统仍可继续。

大量：

```text
perception
visualization
high-level planning
```

更接近 soft real-time。

---

# 8. 不要把整个机器人标记成“Real-Time”

一个机器人内部同时可能有：

```text
1 kHz motor loop          → strong timing requirement

200 Hz state estimation   → deterministic/high-rate

30 Hz vision              → throughput + latency

10 Hz planning            → soft real-time

logging                   → non-real-time

UI                        → non-real-time
```

所以：

> **Real-time 是某个 execution path 的 property，不是整个 repository 的标签。**

---

# Part II · 时间模型

# 9. 机器人最危险的数据之一：Timestamp

普通：

```cpp
double position;
```

往往不够。

真正状态是：

```text
position
+
what time does this value describe?
```

例如：

```cpp
struct JointSample {
    JointPosition position;
    TimePoint timestamp;
};
```

---

# 10. Measurement Time ≠ Receive Time

传感器：

```text
physical measurement
      │
      ▼
sensor firmware
      │
      ▼
bus/network
      │
      ▼
driver
      │
      ▼
application
```

可以至少有：

```text
measurement timestamp
device transmission timestamp
kernel receive timestamp
application receive timestamp
```

它们不是一回事。

---

# 11. 错误做法

收到 message：

```cpp
sample.timestamp =
    std::chrono::steady_clock::now();
```

然后称：

> “这是 sensor timestamp。”

实际上它最多是：

> application receive time。

如果通信延迟有变化：

```text
measurement time
→ receive time
```

的误差会进入 estimator。

---

# 12. Clock Domains

一个机器人可能同时存在：

```text
MCU hardware timer

camera device clock

LiDAR clock

Linux CLOCK_MONOTONIC

PTP synchronized clock

ROS time

wall clock / UTC
```

必须明确：

> **每个 timestamp 属于哪个 clock domain。**

---

# 13. Clock Domain 不可直接相减

假设：

```text
camera_ts = device clock
imu_ts    = host monotonic
```

直接：

```cpp
camera_ts - imu_ts
```

语义上毫无意义。

必须先有：

```text
clock synchronization
or
clock-domain transformation
```

---

# 14. `steady_clock`

进程内部 measurement：

```cpp
auto now =
    std::chrono::steady_clock::now();
```

非常适合：

```text
durations
timeouts
benchmarking
periodic scheduling
```

因为它的设计目标是：

> monotonic，避免 wall-clock 调整破坏 duration reasoning。

---

# 15. Wall Clock 不应驱动 Control Loop

```text
UTC / system_clock
```

可能因为：

```text
NTP
manual correction
time synchronization
```

发生 adjustment。

控制算法更自然使用：

> monotonic clock / hardware clock。

---

# Part III · Periodic Control Loop

# 16. 控制 Loop 的核心结构

```cpp
while (!stop_requested()) {
    const auto wake_time = ...;

    const SensorState sensors =
        hardware.read();

    const StateEstimate estimate =
        estimator.update(sensors);

    ControlCommand command =
        controller.update(estimate);

    safety.apply(command);

    hardware.write(command);

    wait_until_next_period();
}
```

真正需要审查的是：

```text
每一步是否 bounded？
是否 allocate？
是否 block？
是否 throw？
是否 page fault？
是否获得 mutex？
是否调用 unknown callback？
```

---

# 17. Real-Time Loop 的基本规则

对于强 timing path，默认避免：

```text
general heap allocation
unbounded lock contention
blocking I/O without bound
filesystem
network DNS
logging output
dynamic plugin loading
exception propagation
sleep with uncontrolled semantics
unbounded container growth
```

注意：

> “避免”来自 determinism requirement，不是 C++ 语言禁止。

---

# 18. Control Loop 不应该做 Configuration Parsing

坏：

```text
control iteration
↓
read YAML
↓
lookup parameters
↓
allocate string
↓
update controller
```

更好：

```text
Non-RT configuration
      │
      ▼
validate
      │
      ▼
immutable ControllerConfig
      │
      ▼
atomic/snapshot publication
      │
      ▼
RT controller reads snapshot
```

---

# 19. Dynamic Outside, Static Inside 再次出现

```text
Non-RT world:
complex dynamic decisions

        ↓ once

RT loop:
simple fixed representation
fixed bounds
predictable code path
```

这是 G5/G6/G7 的机器人版。

---

# Part IV · `dt` 到底是什么？

# 20. 理想定周期

Controller可能假设：

```cpp
constexpr Seconds dt{0.001};
```

即 1 kHz。

但真实 cycle：

```text
0.00098
0.00101
0.00103
...
```

---

# 21. Two Models

### Fixed-step Controller

算法理论上基于：

```text
dt = exact configured period
```

适合某些离散控制设计。

### Measured-step Controller

使用：

```text
actual elapsed time
```

更新 integrator / estimator。

两者都可以正确。

关键：

> 不要含糊地在两种模型之间漂移。

---

# 22. Control Timing Contract

Controller API可以显式：

```cpp
struct ControlTick {
    SteadyTime timestamp;
    Duration period;
};
```

然后：

```cpp
ControlCommand update(
    const ControlTick& tick,
    const RobotState& state);
```

时间成为 first-class input。

---

# Part V · Linux Scheduling / Determinism

# 23. 普通 OS Scheduler 优化什么？

普通 desktop/server Linux主要面向：

```text
fairness
throughput
general responsiveness
```

而不是：

> 保证 motor loop 每 1 ms 精确运行。

---

# 24. Real-Time Scheduling

Linux提供类似：

```text
SCHED_FIFO
SCHED_RR
```

实时 scheduling classes。

`ros2_control` 官方 Controller Manager 文档明确把降低 main control loop jitter 作为目标，并尝试对主线程设置 `SCHED_FIFO` priority 50；官方也给出了 realtime priority 和 memory-lock 权限配置，并建议 real-time 或 low-latency kernel 来改善 determinism。:chatgpt-content-reference{index="1"}

---

# 25. Priority 不等于 Deadline Guarantee

设置：

```text
SCHED_FIFO
priority high
```

只解决 scheduling policy 的一部分。

仍有：

```text
interrupts
drivers
kernel sections
page faults
memory contention
SMI/firmware
thermal effects
locks
other RT tasks
```

所以：

> `SCHED_FIFO` ≠ “现在就是 hard real-time”。

---

# 26. CPU Affinity

可将 control thread限定到：

```text
specific CPU/core set
```

目标：

```text
reduce migration
improve cache affinity
reduce scheduler interference
```

但 affinity也可能造成：

```text
load imbalance
competing interrupts
wrong core selection
```

所以需要测量。

---

# 27. Isolation

更严格系统可能：

```text
reserve CPU
move IRQs
partition RT/non-RT tasks
```

形成：

```text
Core 0:
OS / network / ROS

Core 1:
control

Core 2-3:
perception
```

但这属于：

> system deployment profile，

不是 C++ 代码本身能保证的。

---

# Part VI · Priority Inversion

# 28. 场景

```text
Low-priority thread
holds mutex

High-priority control thread
waits mutex

Medium-priority thread
keeps running
```

结果：

```text
high priority
indirectly blocked by
low priority
```

叫：

> **Priority Inversion**

---

# 29. 为什么 RT Loop 应避免普通 Shared Locks

即使：

```text
mutex normally uncontended
```

只要存在：

> unbounded holder execution

就很难给 control path建立严格 timing bound。

---

# 30. 更好的架构

不要：

```text
ROS callback
     │
     ▼
shared mutex
     ▲
     │
RT control
```

倾向：

```text
ROS callback
     │
     ▼
prepare immutable command snapshot
     │
     ▼
single atomic/double-buffer publication
     │
     ▼
RT control
```

把 unpredictable non-RT execution与 RT loop隔离。

---

# Part VII · Memory Discipline

# 31. `new` 为什么在 RT Loop 中危险？

不是因为：

> heap一定慢。

而是 general allocator：

```text
fast path normally
but
possible slow path
locks
metadata
page acquisition
fragmentation
```

执行时间通常缺乏你想要的严格 bound。

---

# 32. Initialization Phase vs Runtime Phase

推荐：

```text
Initialization
────────────────
allocate
reserve
construct
load model
warm buffers
prefault pages
create threads

        ↓

Real-Time Runtime
─────────────────
reuse
fixed capacity
bounded operations
```

这是非常强的 phase separation。

---

# 33. `vector.reserve()` 不是 Hard Capacity

```cpp
values.reserve(1024);
```

只保证：

> 至少预留 capacity。

仍可以：

```cpp
values.push_back(...); // 1025th
```

然后 reallocate。

如果要求：

> runtime绝不能 allocate，

需要 abstraction真正编码：

```text
capacity <= N
```

---

# 34. C++23 没有标准 `inplace_vector`

需要特别注意：

```cpp
std::inplace_vector
```

属于 C++26 方向，不是 C++23 baseline。

在 C++23 中可以选择：

```text
carefully designed FixedVector<T,N>
third-party static_vector
array + explicit size
domain-specific bounded container
```

不要把未来标准类型误当 C++23。

---

# 35. 简单 Fixed Buffer

```cpp
template <typename T, std::size_t N>
class FixedBuffer {
public:
    bool push(T value) noexcept(/* ... */);

    [[nodiscard]]
    std::span<T> values() noexcept;

private:
    std::array<T, N> storage_;
    std::size_t size_{};
};
```

但注意：

```text
array<T,N>
```

意味着 N 个 `T` 已构造。

真正 fixed-capacity vector-like container：

> 需要 raw storage + manual lifetime。

G1 再次回来。

---

# 36. Memory Locking

在严格 latency-sensitive Linux system 中，可以考虑：

```text
mlockall
```

等机制，降低关键 pages 被换出、first-touch page fault 出现在 control loop 中的风险。ROS 2 的实时示例也明确以“控制执行期间避免 page faults”为目标，并通过 memory locking 等配置进行验证。:chatgpt-content-reference{index="2"}

---

# 37. Pre-touch

预先：

```text
allocate
↓
touch pages
↓
enter control phase
```

不是让 memory 更快，

而是：

> 把 demand-page cost 移出关键 timing window。

G6.5 在机器人中变成实际 requirement。

---

# Part VIII · Exceptions

# 38. Real-Time Loop 中 Exception 的问题

Exception 正常语义并非“慢所以禁止”。

真正问题包括：

```text
unpredictable exceptional path
stack unwinding
cleanup execution
error-path complexity
```

在 hard/firm RT path 中通常更倾向：

> 在边界前验证好，把 hot loop变成非抛出操作。

---

# 39. API 可以使用 `noexcept`

例如：

```cpp
ControlCommand Controller::update(
    const RobotState& state,
    Duration dt) noexcept;
```

这形成：

> failure policy contract。

但只写 `noexcept` 并不会让内部自动可靠。

如果真抛：

> `std::terminate()`。

---

# 40. Fault 应成为 State

比在 loop中 throw：

```cpp
throw SensorFault{};
```

更常见的 RT架构：

```cpp
enum class ControlStatus {
    Ok,
    SensorTimeout,
    InvalidState,
    ActuatorFault,
};
```

然后安全 state machine处理。

---

# Part IX · Numerical Representation

# 41. 机器人系统不是“全是 `double`”

下面这些虽然机器表示都可能是：

```cpp
double
```

但语义完全不同：

```text
meter
meter / second
radian
radian / second
newton
newton-meter
second
```

把它们全部裸 `double`：

> compiler无法帮助发现单位错误。

---

# 42. Strong Units

例如：

```cpp
struct Radians {
    double value{};
};

struct Meters {
    double value{};
};
```

或者采用成熟 units library。

目标：

```cpp
void set_angle(Radians angle);
```

而不是：

```cpp
void set_angle(double value);
```

---

# 43. Degrees vs Radians 是经典 Physical Type Bug

```cpp
controller.set_angle(90.0);
```

到底是：

```text
90 degrees
or
90 radians?
```

接口完全无法表达。

在机器人边界：

> 单位应该进入 type/schema/documentation contract。

---

# Part X · Coordinate Frames

# 44. Position 永远属于某个 Frame

```text
(1, 2, 3)
```

没有 frame：

> 几乎没有物理意义。

可能是：

```text
world frame
base frame
camera frame
end-effector frame
IMU frame
```

---

# 45. Transform

一般：

```text
T_A_B
```

应该明确 convention：

> 它表示把 B 中表示的坐标变换到 A？

还是反过来？

如果团队不统一：

> 数学全部可能“看起来对”。

---

# 46. SE(3)

刚体 pose通常可以理解为：

```text
rotation R ∈ SO(3)
translation t ∈ R³
```

组成：

```text
T =
[R t]
[0 1]
```

不用在 G11 重新讲 Lie group数学课程，

但 C++ representation 必须保留：

```text
frame
convention
units
normalization
```

---

# 47. Quaternion

Quaternion：

```text
q
```

用于 rotation时通常要求：

```text
||q|| = 1
```

数值运算后：

> 可能需要维护 normalization。

还必须统一：

```text
wxyz vs xyzw storage order
active vs passive rotation
right/left multiplication convention
```

这些都是 API contract。

---

# 48. Frame-safe API

可以概念性设计：

```cpp
template <typename From, typename To>
class Transform;
```

于是：

```cpp
Transform<CameraFrame, BaseFrame>
```

比裸：

```cpp
Eigen::Matrix4d
```

具有更强 semantic information。

但不要无限 template 化 runtime frame graph。

---

# 49. Static vs Runtime Frames

Robot kinematic chain：

```text
Base
→ Shoulder
→ Elbow
```

可能 compile-time known。

ROS/SLAM world中的：

```text
map
odom
sensor_137
dynamic object
```

往往 runtime-known。

所以：

> frame type safety 和 dynamic frame graph 应在合适 boundary 组合。

---

# Part XI · Eigen / Numerical C++

# 50. Eigen 类库为什么在机器人常见？

因为机器人核心大量涉及：

```text
vectors
matrices
rotations
Jacobians
least squares
filters
optimization
```

其 C++ abstraction 可以实现：

```text
high-level math expression
+
compile-time dimensions
+
SIMD-friendly codegen
```

---

# 51. Fixed-size Matrix

例如：

```cpp
Eigen::Matrix<double, 6, 6>
```

尺寸 compile-time known。

对机器人常见小矩阵很自然：

```text
3×3
4×4
6×6
```

通常也更容易避免 dynamic shape/allocation路径。

---

# 52. Dynamic Matrix

```cpp
Eigen::MatrixXd
```

shape runtime-known。

如果在 RT loop 中：

```text
resize
allocate
```

就要特别审查。

更好的 phase：

```text
initialize dynamic sizes before loop
↓
reuse matrix storage
```

---

# 53. Expression Templates

代码：

```cpp
c = a + b;
```

不一定先创建完整：

```text
temporary a+b
```

再赋值。

Expression template可以让 compiler fuse expression。

但：

> 复杂表达式仍需查看 aliasing、temporary materialization 与 codegen。

不要认为：

```text
Eigen syntax
=
automatically optimal
```

---

# 54. Aliasing

例如：

```cpp
A = A * B;
```

output与input alias。

Math library必须知道是否：

```text
temporary required
```

某些 API提供：

```text
noalias-like
```

提示。

只有在确实不存在 alias时使用。

错误 noalias 声明：

> 会破坏数学正确性。

---

# Part XII · Sensor Acquisition

# 55. Driver Boundary

典型：

```text
Hardware
   ↓
Kernel / Vendor SDK
   ↓
Driver Adapter
   ↓
Canonical Sample
```

不要让：

```text
vendor-specific struct
```

扩散整个系统。

---

# 56. Canonical Sample

例如：

```cpp
struct ImuSample {
    SensorTime timestamp;

    Vec3 angular_velocity;
    Vec3 linear_acceleration;

    ImuSequence sequence{};
};
```

Adapter负责：

```text
vendor units
↓
canonical SI units

vendor timestamp
↓
clock-domain model
```

---

# 57. Normalize at Boundary

如果某设备输出：

```text
degrees/s
g
milliseconds
```

进入 domain core 时立即转换成：

```text
rad/s
m/s²
seconds/nanoseconds
```

不要让单位差异流到 estimator内部。

---

# 58. Sequence Number

高频 sensor stream最好有：

```text
timestamp
sequence
```

二者解决不同问题：

```text
timestamp
→ when?

sequence
→ did we miss / reorder samples?
```

---

# 59. Overflow Policy

Sensor producer：

```text
10 kHz
```

consumer暂时跟不上。

你必须定义：

```text
block sensor?
drop oldest?
drop newest?
overwrite latest?
fault?
```

不是所有 sensor data 都应该“绝不丢”。

---

# 60. Latest-state vs FIFO

控制 loop可能真正需要：

> 最新 joint state。

如果 queue积压：

```text
state at t-100ms
state at t-99ms
...
```

逐个处理反而使 controller永远落后。

这时 abstraction可能应该是：

# **Latest Value**

而不是 FIFO queue。

---

# 61. Command 则可能不同

例如：

```text
MoveArm
Stop
ResetFault
```

如果语义是 event sequence：

> FIFO/order可能非常重要。

所以：

```text
Sensor State
Command Event
```

不能机械使用同一种 channel。

---

# Part XIII · Latest-value Channel

# 62. Latest Snapshot

```text
Sensor Thread
     │
     ▼
 latest state
     │
     ▼
Control Thread
```

Producer不断覆盖：

> 最新完整 generation。

Consumer每 cycle：

> 读取当前最新 snapshot。

中间版本可以被跳过。

---

# 63. 适合

```text
joint state
latest pose estimate
target setpoint
configuration snapshot
```

前提：

> 中间每个 update 没有独立事件语义。

---

# 64. 不适合

```text
financial transaction
button edge event
state-machine command
discrete action
```

因为跳过中间 value可能改变 semantics。

---

# Part XIV · Double Buffering

# 65. 基本结构

```text
Buffer A
Buffer B

Writer writes inactive buffer
      ↓
publish active index/pointer
      ↓
Reader reads published complete buffer
```

关键：

> reader不观察 half-written state。

---

# 66. 为什么比 Shared Mutex 更适合某些 RT Read Paths？

Non-RT writer：

```text
build snapshot
```

可以慢一些。

RT reader：

```text
load pointer/index
↓
read immutable snapshot
```

没有：

```text
mutex contention
```

---

# 67. 但 Double Buffering 有 Reuse 问题

Writer不能：

```text
publish B
↓
立刻 overwrite A
```

如果 reader仍然使用 A。

简单单-reader周期系统可以通过严格 phase协议解决。

多个任意 reader：

> 重新进入 generation reclamation 问题。

G7.5 又回来了。

---

# Part XV · State Estimation

# 68. Estimator 的角色

Sensors：

```text
noisy
partial
different rates
different clocks
```

Estimator输出：

```text
coherent robot state
```

例如：

```cpp
struct RobotState {
    StateTime timestamp;

    Pose base_pose;
    Velocity base_velocity;

    JointState joints;
    Covariance covariance;
};
```

---

# 69. Estimator 应该有明确 Single Writer

通常一个 estimator execution context：

```text
owns mutable filter state
```

例如：

```text
state vector
covariance
bias estimates
history
```

避免多个 callbacks并发直接 mutate filter internals。

---

# 70. Multi-sensor Input

```text
IMU ─────┐
Encoder ─┼──▶ Estimator
Camera ──┤
LiDAR ───┘
```

需要解决：

```text
timestamp ordering
clock conversion
out-of-order observations
latency
interpolation
buffering
```

而不仅：

> “mutex保护 EKF。”

---

# 71. State Timestamp

Estimator output时间应该有明确含义：

```text
state estimate valid at time t
```

而不是：

> “函数 return 的时间”。

这对：

```text
prediction
control
sensor fusion
```

极其重要。

---

# 72. Delayed Measurement

视觉 measurement可能：

```text
captured at t0
processed at t0 + 50ms
```

Estimator必须决定：

```text
apply as if now?
rewind history?
out-of-sequence update?
discard?
```

这是算法 contract。

Runtime不能凭 receive time替代 measurement time。

---

# Part XVI · Control Architecture

# 73. Controller 输入应该是完整 Consistent Snapshot

不要：

```cpp
controller.read_position();
controller.read_velocity();
controller.read_target();
```

每次可能来自不同 generation。

更好：

```cpp
ControlInput input{
    .state = state_snapshot,
    .target = target_snapshot,
};
```

同一 update使用固定 snapshot。

---

# 74. Controller 应尽量 Pure-ish

理想：

```cpp
ControlOutput Controller::update(
    const ControlInput& input,
    Duration dt) noexcept;
```

内部可能有：

```text
integrator
previous state
filter state
```

所以不是纯函数。

但 external side effects尽量少。

不要在 `update()`：

```text
publish ROS
write log file
reload config
open socket
```

---

# 75. Saturation

控制输出必须进入 actuator physical limits：

```text
u_raw
↓
saturation
↓
u_safe
```

例如：

```text
torque min/max
velocity limit
position limit
current limit
```

限制不是 UI validation。

而是：

> physical safety invariant。

---

# 76. Rate Limit

即使 target在合法范围，

变化过快也可能危险：

```text
0 N·m
↓ one cycle
100 N·m
```

所以可以有：

```text
value limit
rate limit
acceleration/jerk limit
```

不同层。

---

# 77. Anti-windup

对包含积分项的 controller：

```text
actuator saturated
```

但 integrator仍无限增长，

会产生：

> integral windup。

所以 saturation和controller state必须协同设计。

这不是 C++问题，

但必须进入 controller abstraction。

---

# Part XVII · Hardware Interface

# 78. Hardware Core Interface

例如：

```cpp
class MotorBus {
public:
    [[nodiscard]]
    BusState read() noexcept;

    WriteStatus write(
        std::span<const MotorCommand>) noexcept;
};
```

它应该隔离：

```text
SocketCAN
EtherCAT SDK
vendor C API
serial implementation
```

---

# 79. Avoid Vendor Types in Domain

坏：

```cpp
void Controller::update(
    VendorXMotorPacket packet);
```

这样 controller 被 SDK绑死。

更好：

```text
Vendor Packet
↓ adapter
MotorState
↓
Controller
```

---

# 80. C ABI 非常适合 Driver Boundary

很多硬件 SDK本身是：

```text
C
C-compatible shared library
vendor ABI
```

G8 模型正好适用：

```text
opaque handle
pointer + length
explicit create/destroy
no exceptions across boundary
```

---

# Part XVIII · Device I/O Thread

# 81. Hardware Read 是否应该直接发生在 Controller Thread？

取决于设备 I/O guarantee。

如果：

```text
read call
has strict bounded duration
```

可以集成。

如果可能：

```text
block
driver stall
network timeout
```

最好：

```text
I/O thread
↓
bounded/latest channel
↓
control
```

---

# 82. Trade-off

独立 I/O thread：

```text
+ isolates blocking
+ decouples driver

- extra handoff
- extra latency
- timestamp complexity
```

没有 universal answer。

---

# Part XIX · Watchdog

# 83. 控制系统必须假设 Software 会停止正常更新

例如：

```text
controller hang
process crash
communication lost
```

Actuator不能无限保持：

> 上一次 torque command。

---

# 84. Command Watchdog

Motor controller / MCU 可以要求：

```text
new command every <= T
```

如果 timeout：

```text
enter safe state
```

这比上层软件自己：

```text
“我会一直正常跑”
```

可靠得多。

---

# 85. Watchdog 应尽量靠近 Actuator

```text
Cloud watchdog
```

通常没有意义。

更健康：

```text
host software watchdog
+
motor controller / MCU watchdog
+
hardware safety chain
```

分层防御。

---

# 86. Emergency Stop

E-stop 不应被理解成：

> ROS topic `/emergency_stop`。

真正 safety-critical E-stop 往往需要：

```text
independent hardware chain
safety PLC/controller
power/drive safe state
```

软件消息可以参与系统，

但不应该是唯一安全屏障。

---

# Part XX · Fault State Machine

# 87. 不要用很多 Bool

坏：

```cpp
bool sensor_fault;
bool motor_fault;
bool stopping;
bool disabled;
bool emergency;
```

组合可能产生：

```text
2^5 states
```

很多非法。

---

# 88. Explicit State

```cpp
enum class RobotMode {
    Initializing,
    Standby,
    Enabled,
    Fault,
    EmergencyStop,
    ShuttingDown,
};
```

定义合法 transition：

```text
Initializing → Standby
Standby      → Enabled
Enabled      → Fault
Fault        → Standby
*            → EmergencyStop
```

---

# 89. Fault Should Be Latched?

某些 fault：

```text
sensor timeout
overcurrent
encoder fault
```

不应因为下一 cycle暂时正常：

> 自动恢复。

需要：

```text
fault latch
+
explicit reset conditions
```

这是 physical system safety contract。

---

# Part XXI · Command Arbitration

# 90. 一个机器人往往有多个 Command Sources

```text
autonomous planner
teleoperation
safety controller
calibration
manual service
```

不能都直接：

```text
write actuator target
```

---

# 91. Arbitration Layer

```text
Planner ─────┐
Teleop ──────┼──▶ Command Arbiter ─▶ Controller
Safety ──────┘
```

定义：

```text
priority
ownership
mode
timeout
validity
```

---

# 92. Command 也需要 Timestamp / Validity

```cpp
struct TargetCommand {
    CommandTime timestamp;
    Duration valid_for;
    Target target;
};
```

过期 command：

> 不应继续作用于 actuator。

这就是 ROS QoS lifespan / application validity semantics 背后的物理意义。

---

# Part XXII · RT ↔ Non-RT Boundary

# 93. 推荐结构

```text
                  NON-RT
┌─────────────────────────────────────┐
│ ROS / planning / config / logging   │
└────────────────┬────────────────────┘
                 │ snapshots/commands
                 ▼
        bounded RT-safe handoff
                 │
                 ▼
┌─────────────────────────────────────┐
│          RT / deterministic         │
│ estimate → control → safety → write │
└────────────────┬────────────────────┘
                 │ state snapshots
                 ▼
        bounded RT-safe handoff
                 │
                 ▼
┌─────────────────────────────────────┐
│ ROS publish / logging / telemetry   │
└─────────────────────────────────────┘
```

---

# 94. RT Thread 不应直接做普通 ROS Publish

`realtime_tools` 官方文档明确指出，普通 ROS publisher 不应直接用于 hard-real-time controller update loop；`RealtimePublisher` 的设计就是让 realtime side准备数据，由额外 non-realtime thread执行 ROS topic publish。:chatgpt-content-reference{index="3"}

这正好验证本章的边界设计：

```text
RT generates state
↓
handoff
↓
non-RT middleware publication
```

---

# 95. Reverse Direction

ROS callback接收：

```text
new target
new config
mode change
```

也不要：

```text
callback thread
locks controller internal state
```

更好：

```text
validate
↓
construct command/config snapshot
↓
publish
↓
RT loop consumes next safe point
```

---

# Part XXIII · ROS 2 在系统中的位置

# 96. ROS 2 不是你的 Robot Control Algorithm

ROS 2 提供：

```text
discovery
message transport
services
actions
parameters
lifecycle
tooling
ecosystem integration
```

控制算法：

> 应尽量是可脱离 ROS runtime 单独测试的普通 C++。

---

# 97. 推荐 Dependency Direction

不要：

```text
Controller
↓
rclcpp::Node
```

而是：

```text
ROS Adapter
↓
Controller Core
```

也就是：

```text
ROS
is an adapter/integration layer
```

不是 domain core 的 superclass。

---

# 98. 为什么？

这样 controller可以：

```text
unit test without ROS
simulation
HIL
embedded integration
different middleware
```

并减少：

```text
callback/threading semantics
```

渗透算法内部。

---

# Part XXIV · ROS 2 Middleware

# 99. RMW Layer

ROS 2 通过 middleware abstraction 将上层 ROS API 与具体传输实现隔离。当前 ROS 2 文档描述了 DDS/RTPS 家族以及 Zenoh 等不同 RMW backend；这意味着“ROS 2 topic”并不等价于一个固定 transport implementation。:chatgpt-content-reference{index="4"}

因此性能分析不能只说：

> “ROS 2 latency 是多少？”

还必须知道：

```text
RMW implementation
transport
serialization
process topology
QoS
message size
network
```

---

# Part XXV · ROS 2 QoS

# 100. QoS 不是“网络高级选项”

机器人 message 有不同 physical semantics。

例如：

```text
camera frames
motor command
map
configuration
heartbeat
```

不应该全部采用相同 delivery policy。

---

# 101. 重要 QoS 维度

ROS 2 的 QoS API 包括：

```text
History
Depth
Reliability
Durability
Deadline
Lifespan
Liveliness
```

等策略。当前 `rclcpp` QoS API 也明确暴露这些 policy categories。:chatgpt-content-reference{index="5"}

---

# 102. Reliability

典型：

```text
Reliable
Best Effort
```

关键问题：

> 丢数据和阻塞等待重传，哪个更符合 topic semantics？

---

# 103. Sensor Data

ROS 2 的 `SensorDataQoS` 默认采用 Keep Last depth 5、Best Effort、Volatile 等设置，这反映了高频传感数据经常更重视最新数据和低延迟，而不是为每一帧强制可靠重传。:chatgpt-content-reference{index="6"}

但：

> 不应该因为名字叫 sensor 就机械使用。

例如：

```text
low-rate critical measurement
```

可能有不同要求。

---

# 104. Durability

回答：

> 新 subscriber 加入时，是否应该获得历史/最近发布状态？

例如：

```text
static config/map
```

与：

```text
camera stream
```

需求完全不同。

---

# 105. History / Depth

```text
Keep Last N
```

实际上就是：

> middleware backlog bound。

深度太大：

```text
stale data latency ↑
memory ↑
```

深度太小：

```text
burst drop ↑
```

又是 backpressure/queueing问题。

---

# 106. Deadline

可以表达：

> publisher期望在某个时间尺度持续提供数据。

这与 control system的：

```text
sensor timeout
heartbeat
```

语义有关。

但 middleware deadline事件：

> 不应自动替代 application safety watchdog。

---

# 107. Lifespan

Lifespan描述 data有效期。DDS/RMW实现中的 lifespan policy就是限制一份数据被认为有效的最大持续时间。:chatgpt-content-reference{index="7"}

对机器人：

```text
stale target
```

尤其值得建模。

---

# 108. Liveliness

帮助检测：

> publisher 是否仍然 alive/maintaining liveliness contract。

但同样：

```text
middleware liveliness
≠
actuator safety watchdog
```

两层都可能需要。

---

# Part XXVI · ROS Executor

# 109. Callback 并不是“凭空发生”

ROS node的：

```text
subscription callbacks
timers
services
actions
```

最终需要 executor决定：

> 哪个 executable callback 什么时候在哪个 thread运行。

因此：

```text
Callback Threading Model
```

是并发 architecture 的一部分。

---

# 110. 不要在 Callback 内假设 Single Thread

只要系统进入：

```text
multi-threaded executor
callback groups
composition
```

callback interleaving就可能改变。

因此 state所有权必须明确。

---

# 111. RT Core 不应该依赖 Executor Timing

如果 motor loop requirement：

```text
1 kHz periodic
low jitter
```

不要仅依赖：

> “ROS timer callback应该差不多每 1ms 调一次。”

更稳健是：

```text
dedicated control execution context
```

再通过 adapter和 ROS 交互。

---

# Part XXVII · `ros2_control`

# 112. `ros2_control` 的角色

`ros2_control` 当前官方文档将其描述为面向 ROS 2 的机器人（实时）控制框架，包含 controller manager、hardware components、controllers 等机制。:chatgpt-content-reference{index="8"}

从我们的模型看，它大致对应：

```text
ROS world
   │
Controller Manager
   │
Controller update
   │
Hardware Interfaces
   │
Physical robot
```

---

# 113. Control Framework 不等于 Automatic Real-Time Safety

即使框架提供 realtime-oriented architecture，

你自己的 controller若：

```text
allocates
logs
takes contended mutex
calls blocking service
```

仍可能破坏 determinism。

---

# 114. Hardware Interface Lifecycle

硬件 adapter应该明确：

```text
configure
activate
read/write
deactivate
error
cleanup
```

这和 G7/G10 lifecycle state machine完全一致。

---

# Part XXVIII · Zero-copy / Loaned Messages

# 115. “Zero-copy” 应该精确定义

至少可能指：

```text
no user-level payload copy
middleware-loaned buffer
intra-process ownership transfer
shared-memory transport
```

它们不是同一件事。

---

# 116. ROS Loaned Messages

ROS 2 RMW 接口支持 loaned message 的概念；官方 API 明确规定，loaned message publish 后 ownership 会交回 middleware，发布之后继续使用该 message 是 undefined behavior。同时，底层是否需要分配、是否 lock-free 是 implementation-defined，而非“用了 loaned message 就必然零分配/lock-free”。:chatgpt-content-reference{index="9"}

这与我们 G2/G3 的模型完全一致：

> **Loan = explicit temporary ownership/borrowing contract。**

---

# 117. Zero-copy 的代价

减少：

```text
memory bandwidth
copy latency
```

但增加：

```text
buffer lifetime coordination
ownership constraints
pool pressure
backpressure coupling
```

所以：

> Zero-copy 不是免费性能按钮。

---

# Part XXIX · Camera / LiDAR 大 Payload

# 118. 大图像尤其不适合随意 Copy

例如：

```text
1920×1080×3
≈ 6 MB/frame
```

30 FPS：

```text
≈ 180 MB/s
```

仅一次完整 copy就是明显 bandwidth。

如果 pipeline多 copy几次：

> 很快进入 memory-bandwidth domain。

---

# 119. Better Pattern

```text
Capture Buffer
     │
     ▼
Owned / Loaned Frame
     │
     ├── perception borrow
     ├── recorder borrow
     └── visualization?
```

但这引入：

> 多 reader lifetime。

可使用：

```text
shared immutable frame
reference count
buffer pool
loan protocol
```

取决于性能需求。

---

# Part XXX · Robot Data Topology

# 120. 高频状态通常适合 SoA 吗？

例如 100 个 joints：

```cpp
struct JointState {
    double position;
    double velocity;
    double effort;
};
```

AoS：

```text
[p v e][p v e][p v e]
```

如果 controller每次对每 joint都同时用：

```text
position + velocity + effort
```

AoS完全可能很好。

---

# 121. SoA 不是机器人默认答案

如果 kernel只：

```text
process all position
```

SoA可能更好：

```text
positions[]
velocities[]
efforts[]
```

还是 G6：

> access pattern drives layout。

---

# Part XXXI · Command Snapshot

# 122. Non-RT Command

Planner产生：

```cpp
struct MotionTarget {
    TargetTime timestamp;
    Pose target_pose;
    Velocity target_velocity;
};
```

构造完成后：

```text
publish immutable target snapshot
```

---

# 123. RT Consume

Control loop每 cycle：

```text
load current target generation
↓
hold same target during update
```

不要在一次 controller update中：

```text
position target = V1
velocity target = V2
```

snapshot consistency很重要。

---

# Part XXXII · Configuration

# 124. Static Config

例如：

```text
joint limits
motor constants
kinematic dimensions
control gains
```

Initialization时：

```text
parse
validate
compile/precompute
```

运行时使用：

> normalized config representation。

---

# 125. Dynamic Gain Tuning

ROS parameter callback：

```text
new gains
```

不要直接：

```text
write active controller fields one by one
```

构造：

```cpp
ControllerConfig next;
```

验证：

```text
all invariants
```

一次 publish generation。

---

# 126. Parameter Update 是 Transaction

如果：

```text
Kp
Ki
Kd
```

必须形成一个 consistent set，

不要三个 independent atomics：

```text
Kp V2
Ki V1
Kd V2
```

immutable config snapshot是自然解。

---

# Part XXXIII · Safety Layer

# 127. Controller 和 Safety Filter 分离

```text
Controller
produces desired command
         │
         ▼
Safety / Limits Layer
         │
         ▼
Hardware command
```

这样 safety rules不散落在：

```text
planner
controller
driver
```

各处。

---

# 128. Safety Layer 输入

至少：

```text
requested command
current state
limits
fault status
timestamp / age
```

输出：

```text
safe command
or
fault transition
```

---

# 129. Command Age

如果 target：

```text
timestamp = t0
```

current：

```text
t0 + 3 sec
```

即使 numeric value完全合法，

也可能：

> 已经过期。

因此 freshness是安全状态的一部分。

---

# Part XXXIV · Failure Containment

# 130. Perception Failure 不应该直接破坏 Motor Thread

例如 vision：

```text
throws
runs out of memory
misses deadline
```

control loop应有：

```text
last valid state
timeout policy
fallback
safe mode
```

而不是：

```text
control thread blocks waiting vision
```

---

# 131. Pipeline 要按 Failure Domain 分层

```text
Vision failure
≠
Motor bus failure
≠
Localization failure
≠
UI failure
```

不同 subsystem应有明确 containment boundary。

---

# Part XXXV · Determinism 与 Logging

# 132. RT Loop 中不应该直接格式化大型 Log

例如：

```cpp
std::println(
    "position={}, target={}, ...",
    ...);
```

可能涉及：

```text
formatting
locks
I/O
terminal
allocation
```

都不适合 deterministic path。

---

# 133. RT Telemetry Buffer

RT loop只写：

```cpp
struct TraceSample {
    std::uint64_t cycle;
    std::int64_t jitter_ns;
    double error;
};
```

到：

```text
preallocated SPSC trace buffer
```

non-RT thread：

```text
format
publish
write disk
```

---

# Part XXXVI · Observability

# 134. 必须测什么？

控制 loop：

```text
period
execution time
deadline miss
jitter
max latency
```

Sensor：

```text
input rate
age
drops
reordering
```

Queues：

```text
depth
drops/full
wait
```

Hardware：

```text
read/write duration
timeouts
faults
```

---

# 135. Average 不够

机器人尤其要关注：

```text
max
p99
p99.9
deadline miss count
```

一次：

```text
1 second stall
```

可能比平均 10 µs 更重要。

---

# 136. Trace Timeline

理想：

```text
sensor sample
     │
     ▼
driver
     │
     ▼
estimator
     │
     ▼
controller
     │
     ▼
motor write
```

跨 subsystem记录：

```text
timestamp
sequence
generation
```

才能分析真正 end-to-end latency。

---

# Part XXXVII · Simulation

# 137. Algorithm Core 必须能脱离 Hardware

如果 controller只能通过：

```text
真实 CAN device
```

才能测试，

设计耦合太强。

理想：

```text
Hardware Interface
       ▲
       │
Real ──┼── Simulated
       │
       └── Recorded Replay
```

---

# 138. Deterministic Replay

记录：

```text
sensor samples
timestamps
commands
```

然后离线：

```text
replay same sequence
```

验证：

```text
estimator output
controller decisions
fault transitions
```

这是非常强的 debugging能力。

---

# 139. Simulation Time

Simulation可能：

```text
faster than real time
slower than real time
paused
rewound/reset
```

所以：

> algorithmic simulation time 不应和 host steady clock混为一体。

---

# Part XXXVIII · Hardware-in-the-Loop

# 140. HIL

```text
Real controller software
        │
        ▼
simulated plant / partial physical hardware
```

用于验证：

```text
timing
driver
interfaces
failure modes
```

比纯 simulation更接近 deployment。

---

# 141. SIL / HIL / Real Robot

测试阶梯：

```text
Unit mathematical model

        ↓

SIL
Software-in-the-loop

        ↓

HIL
Hardware-in-the-loop

        ↓

Bench hardware

        ↓

Full robot
```

不要把所有 bug留给：

> 真机第一次发现。

---

# Part XXXIX · Testing Control Code

# 142. Pure Controller Tests

输入：

```text
state
target
dt
```

验证：

```text
output
saturation
fault behavior
```

完全不需要 ROS。

---

# 143. Property Tests

例如：

```text
|command| <= actuator_limit
```

对大量 randomized state成立。

---

# 144. Numerical Boundary Tests

必须覆盖：

```text
NaN
Inf
near-zero dt
large timestamp jump
singularity
quaternion norm drift
sensor dropout
```

机器人算法最危险的问题常在边界。

---

# 145. Timing Tests

不要只：

```text
function correctness
```

还测：

```text
allocation count
page faults
cycle latency
jitter
```

如果有 timing contract。

---

# Part XL · Allocation Tests

# 146. RT Phase “No Allocation” 应该被验证

不是只靠 code review。

可以：

```text
instrument allocator
count allocations
```

控制 phase期望：

```text
0
```

如果 requirement是零动态分配。

---

# 147. 但注意 Hidden Allocation

可能来自：

```text
std::function
string formatting
vector growth
ROS publish
Eigen dynamic resize
exception
unordered_map insertion
```

所以必须用实际 instrumentation。

---

# Part XLI · Real-Time Safety Classification

# 148. 建议给 API 标注 Execution Class

文档级：

```text
RT_SAFE
RT_INIT_ONLY
NON_RT
BLOCKING
```

例如：

```text
MotorBus::write
→ RT_SAFE under driver contract

load_config
→ NON_RT

publish_debug
→ NON_RT
```

不是 C++ keyword，

而是工程 contract。

---

# 149. RT-safe 的定义必须具体

不要只写：

> “real-time safe”。

应该列出：

```text
does not allocate
does not block on unbounded mutex
does not perform filesystem I/O
does not throw
bounded input sizes
execution analyzed under platform X
```

否则这个词没有审计价值。

---

# Part XLII · Architecture Example

# 150. 一套推荐机器人 Runtime

```text
                 ┌─────────────────────────┐
                 │       ROS / UI          │
                 │ planner / params / log  │
                 └───────────┬─────────────┘
                             │
                       target snapshot
                             │
                             ▼
┌───────────┐       ┌─────────────────────┐
│ Sensors   │──────▶│   Estimator Thread  │
└───────────┘       └─────────┬───────────┘
                              │
                        state snapshot
                              │
                              ▼
                    ┌─────────────────────┐
                    │    Control Thread   │
                    │ estimator snapshot  │
                    │ target snapshot     │
                    │ safety              │
                    └─────────┬───────────┘
                              │
                        actuator command
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Hardware Interface  │
                    └─────────────────────┘

RT telemetry ─────────▶ SPSC ─────────▶ ROS/log thread
```

核心特点：

```text
single-writer estimator
single-writer controller state
immutable snapshots
bounded handoffs
non-RT ROS integration
```

---

# Part XLIII · Thread Topology

# 151. Example

```text
Thread A
Hardware acquisition

Thread B
State estimation

Thread C
Control loop

Thread D
ROS executor / commands

Thread E
Telemetry / logging

Thread F...
Vision/perception pool
```

不是：

> “线程越多越专业”。

而是 execution-class isolation。

---

# 152. Could Acquisition + Control Be Same Thread?

当然。

如果：

```text
hardware read is bounded
state estimation cheap
timing aligned
```

一个 loop：

```text
read
estimate
control
write
```

反而：

```text
fewer handoffs
lower latency
simpler timing
```

所以线程划分必须来自：

> timing / blocking / ownership requirements。

---

# Part XLIV · ROS Node Topology

# 153. Process Boundary 不是免费

把每个 subsystem：

```text
one ROS node
one process
```

可能增加：

```text
serialization
IPC
context switches
memory copy
deployment complexity
```

---

# 154. Composition

多个 components可在一个 process中 composition，

减少某些 process boundaries。

ROS 2 也提供 composable-node infrastructure。:chatgpt-content-reference{index="10"}

但：

> process composition 会增加 failure coupling。

因此：

```text
performance isolation
vs
fault isolation
```

需要权衡。

---

# Part XLV · QoS Design Examples

# 155. Camera Frames

常见需求：

```text
high rate
latest data preferred
occasional loss acceptable
stale frame useless
```

可能倾向：

```text
Best Effort
small depth
volatile
```

---

# 156. Map / Static Configuration

常见：

```text
low-rate
new subscribers need latest state
```

可能倾向：

```text
Reliable
transient-like durability semantics
```

具体选择必须结合 RMW和系统 requirements。

---

# 157. Emergency Command

不要简单认为：

```text
Reliable ROS message
=
safety mechanism
```

reliability只是一层 transport property。

真正 safety stop通常需要：

```text
watchdog
local safe state
hardware path
```

---

# Part XLVI · Sensor Synchronization

# 158. Exact-time Synchronization

要求：

```text
camera.timestamp == imu.timestamp
```

现实中往往不成立。

---

# 159. Approximate Synchronization

定义：

```text
|t_camera - t_imu| <= tolerance
```

但 tolerance是物理系统 parameter。

过大：

```text
temporal inconsistency
```

过小：

```text
drop rate ↑
```

---

# 160. Interpolation

对于高频 IMU / encoder：

```text
state(t_camera)
```

可以通过邻近 samples：

```text
interpolate / integrate
```

而不是强行寻找 exact timestamp。

这是 estimator设计问题。

---

# Part XLVII · Latency Compensation

# 161. State Age

如果 estimator输出：

```text
state valid at t_est
```

controller现在：

```text
t_now
```

则：

```text
age = t_now - t_est
```

可能需要：

```text
predict state forward
```

而不是直接把旧 state当当前 state。

---

# 162. Command Age

同理 planner target：

```text
generated at t_cmd
```

控制器可以判断：

```text
too stale?
```

而不是永远执行最后一条 command。

---

# Part XLVIII · Control-Loop State Machine

# 163. 不要只有 `enabled`

更清楚：

```cpp
enum class ControlMode {
    Disabled,
    Arming,
    Active,
    Fault,
    Emergency,
};
```

---

# 164. Transition Authority

例如：

```text
Disabled → Arming
```

只允许 lifecycle manager。

```text
Active → Fault
```

可以由 safety system触发。

```text
* → Emergency
```

高优先级。

State machine本身是 safety architecture。

---

# Part XLIX · Numerical Failure

# 165. `NaN` 是机器人中特别危险的值

例如：

```text
position = NaN
```

然后：

```cpp
std::clamp(position, min, max);
```

不能简单假设：

> clamp 会把所有异常数值变安全。

Floating-point NaN comparison semantics需要明确处理。

---

# 166. Validate Before Actuation

最终 motor command：

```text
finite?
within bounds?
timestamp fresh?
mode active?
sensor state valid?
```

必须在 write boundary前验证。

---

# Part L · Watchdog + Freshness Invariant

# 167. 一个非常强的 Safety Invariant

Actuator command只有当：

```text
control mode == Active
AND
state is valid
AND
state age <= max_age
AND
target age <= max_age
AND
command finite
AND
command within limits
```

时才允许输出。

否则：

```text
safe command / fault
```

这种 invariant比：

> 到处 if(error)

更容易审计。

---

# Part LI · Robot C++ Project Structure

# 168. 推荐分层

```text
robot/
├── core/
│   ├── math/
│   ├── units/
│   ├── state/
│   ├── estimation/
│   ├── control/
│   └── safety/
│
├── runtime/
│   ├── channels/
│   ├── scheduling/
│   └── lifecycle/
│
├── hardware/
│   ├── motor/
│   ├── imu/
│   └── camera/
│
├── adapters/
│   └── ros2/
│
├── simulation/
├── tests/
└── apps/
```

依赖方向：

```text
ROS adapter ───────┐
hardware adapter ──┼──▶ core
simulation ────────┘
```

而不是：

```text
core → ROS
```

---

# Part LII · Build Boundaries

# 169. Targets

例如：

```text
Robot::math
Robot::core
Robot::control
Robot::hardware
Robot::ros2_adapter
Robot::simulation
```

---

# 170. Core 应该尽量无 ROS Dependency

```text
Robot::control
```

只依赖：

```text
math
state
units
```

这样：

```text
unit tests
benchmarks
simulation
```

不需要启动 ROS runtime。

---

# Part LIII · Hardware Plugin Boundary

# 171. 是否使用 C++ Virtual Interface？

内部同一产品/toolchain：

```cpp
class MotorDriver {
public:
    virtual ~MotorDriver() = default;
    virtual BusState read() noexcept = 0;
    virtual WriteStatus write(...) noexcept = 0;
};
```

完全可能合理。

---

# 172. 第三方 Binary Driver

如果要：

```text
third-party plugin
long-lived ABI
different language
```

回到 G8：

```text
C ABI
opaque handle
function table
```

更稳健。

---

# Part LIV · Robotics Performance Hierarchy

# 173. 优先级 1 — Timing Architecture

先解决：

```text
wrong execution context
blocking operation
unbounded queue
bad timestamping
```

---

# 174. 优先级 2 — Memory Discipline

```text
unexpected allocation
page fault
buffer churn
```

---

# 175. 优先级 3 — Data Movement

```text
image copies
point-cloud copies
ROS serialization
```

---

# 176. 优先级 4 — Cache/Layout

```text
state representation
SoA/AoS
working sets
```

---

# 177. 优先级 5 — Instruction-level

最后才：

```text
branchless
SIMD
intrinsics
```

不要反过来。

---

# Part LV · Practical Project

# 178. G11 Project：`robot-control-core`

设计一个模拟 1 kHz joint-control runtime：

```text
Encoder Simulation
        │
        ▼
Sensor Thread
        │
        ▼
Latest State / SPSC
        │
        ▼
Controller @ 1 kHz
        │
        ▼
Safety Layer
        │
        ▼
Simulated Motor
```

同时：

```text
ROS/non-RT adapter simulation
        │
        ▼
Target Snapshot
```

---

# 179. Phase 0 — Pure Math

实现：

```text
units
joint state
target
PID/state-feedback controller
limits
```

无线程、无 ROS。

---

# 180. Phase 1 — Deterministic Simulator

```text
Plant
↓
Controller
↓
Plant
```

固定 simulation step。

验证：

```text
stability
saturation
fault behavior
```

---

# 181. Phase 2 — Real Clock Runtime

控制 loop：

```text
1 kHz
```

测：

```text
execution
jitter
deadline misses
```

---

# 182. Phase 3 — Sensor Thread

传感器线程模拟：

```text
2 kHz encoder
```

通过：

```text
latest snapshot / SPSC
```

传给 controller。

---

# 183. Phase 4 — Non-RT Commands

另一个线程：

```text
10 Hz
```

更新 target snapshot。

Controller不能：

> lock configuration mutex。

---

# 184. Phase 5 — Fault Injection

模拟：

```text
sensor timeout
NaN
late samples
motor write error
stale target
```

验证：

```text
Fault
Safe State
```

---

# 185. Phase 6 — Memory Audit

控制 phase：

```text
allocation count = 0
```

若这是项目 requirement。

---

# 186. Phase 7 — ROS Adapter

最后才接 ROS 2：

```text
subscription target
state publisher
parameter config
```

Core不改变。

---

# Part LVI · Robotics Review Protocol

面对机器人 C++ path，按这个顺序问。

| Layer       | Question                              |
| ----------- | ------------------------------------- |
| Physical    | 数据/command 对应什么物理量？         |
| Units       | 单位是什么？                          |
| Frame       | 属于哪个 coordinate frame？           |
| Time        | timestamp 属于哪个 clock domain？     |
| Freshness   | 数据多旧仍可用？                      |
| Ownership   | 谁拥有 buffer/state？                 |
| Writer      | 谁可以修改这份 state？                |
| Execution   | RT / deterministic / non-RT？         |
| Memory      | hot path 会 allocate/page fault 吗？  |
| Blocking    | 会等待 mutex/I/O/OS 吗？              |
| Bounds      | loops/queues/container 是否有上界？   |
| Numerics    | NaN/singularity/conditioning？        |
| Safety      | invalid input时输出什么？             |
| Shutdown    | actuator最终进入什么 safe state？     |
| Middleware  | ROS/QoS 是否符合 physical semantics？ |
| Measurement | latency/jitter/deadline是否实际测过？ |

---

# Part LVII · 高频错误

# 187. 错误 1

> 快就是 real-time。

错。

Real-time首先是 deadline/predictability问题。

---

# 188. 错误 2

> ROS timer = deterministic control scheduler。

不能这样假设。

---

# 189. 错误 3

> 设置高 priority 后就 hard real-time。

错。

---

# 190. 错误 4

> `reserve()` 后 vector 永远不会 allocate。

错。

超过 capacity仍会 grow。

---

# 191. 错误 5

> Sensor receive time就是 measurement time。

错。

---

# 192. 错误 6

> 所有 timestamp 都是 nanoseconds，所以能相减。

错。

Clock domain不同仍无意义。

---

# 193. 错误 7

> 最新数据必须全部排队处理。

对于 state stream可能反而导致系统越来越 stale。

---

# 194. 错误 8

> 所有 message 都应该 Reliable。

可靠性取决于 message semantics。

---

# 195. 错误 9

> Zero-copy 永远更好。

它用 lifetime/ownership coordination 换 copy reduction。

---

# 196. 错误 10

> shared_ptr 让机器人数据自动线程安全。

它主要解决 lifetime，不解决 mutation。

---

# 197. 错误 11

> Controller 可以直接操作 vendor SDK type。

会污染 domain boundary。

---

# 198. 错误 12

> RT loop中偶尔 logging没事。

“偶尔”正是 tail latency不可预测的来源。

---

# 199. 错误 13

> Safety 就是在最后 clamp。

Safety还包括：

```text
freshness
mode
fault
watchdog
finite values
rate limit
hardware state
```

---

# 200. 错误 14

> 软件 E-stop topic足够。

真正 safety-critical stop需要独立且符合安全要求的硬件/system设计。

---

# 201. 错误 15

> Robot architecture就是把所有东西拆成 ROS nodes。

Node/process topology必须服从：

```text
latency
copies
fault isolation
ownership
deployment
```

---

# Part LVIII · C++ / Zig / Rust Robotics Perspective

# 202. C++

优势集中在：

```text
mature robotics ecosystem
Eigen/numerics
hardware SDK compatibility
ROS 2 ecosystem
zero-overhead abstractions
fine control of memory/layout
```

代价：

```text
lifetime discipline
UB surface
complex build/ABI
manual concurrency proof
```

---

# 203. Rust

优势：

```text
ownership
data-race prevention
strong enums/result
safer asynchronous architecture
```

但 robotics ecosystem / vendor SDK / numerical integration深度仍要按具体领域评估。

Rust并不会自动解决：

```text
deadline
jitter
allocator determinism
physical safety
```

---

# 204. Zig

优势：

```text
explicit allocation
simple C interop
controllable runtime
small systems layers
```

很适合：

```text
drivers
embedded utilities
C-facing components
deterministic low-level tools
```

但高层 robotics/numerical ecosystem相对 C++ 小。

---

# 205. 混合架构

可以非常自然：

```text
C++:
control / robotics ecosystem / numerical core

Rust:
networked services / safety-sensitive tooling

Zig:
low-level device / build / C integration

C ABI:
stable interoperability boundary
```

不要追求：

> 一个语言统治整台机器人。

---

# Part LIX · G11 Final Fifteen Axioms

如果半年后只能留下十五条：

1. **机器人中的 real-time 不是“算得快”，而是在规定 timing assumptions 下具有可接受、可预测的 deadline behavior。**

2. **物理数据必须同时回答 value、unit、frame 和 timestamp；缺少任何一个都可能产生语义错误。**

3. **Measurement time、receive time 和 processing time 是不同概念；多 sensor 系统必须显式管理 clock domains。**

4. **Real-time/deterministic path 应与 ROS、logging、configuration、blocking I/O 等 non-RT work建立明确 execution boundary。**

5. **RT hot path 优先使用 initialization-time allocation、fixed bounds、storage reuse 和 bounded algorithms；`reserve()` 不等于 hard capacity。**

6. **控制器应尽量消费一个完整一致的 state/target snapshot，而不是在一次 update 中读取多个独立变化的 shared fields。**

7. **Single writer、immutable snapshot、SPSC/latest-value handoff 往往比共享 mutex/复杂 atomics 更适合机器人高频状态。**

8. **FIFO event stream 和 latest-state stream 是不同语义；不是所有 sensor update 都应该排队逐条处理。**

9. **ROS 2 是 integration/middleware layer，不应成为 control/domain algorithm 的不可分离基础类。**

10. **QoS 必须从数据的物理语义选择；Reliability、Depth、Deadline、Lifespan 等不是统一套用的“网络配置”。**

11. **Zero-copy/loaned buffers减少 data movement，却增加 lifetime、ownership 和 buffer-pressure coordination；必须整体评估。**

12. **Safety 是一条独立路径：limits、freshness、finite checks、fault state、watchdog 和 safe actuation 都应明确建模。**

13. **机器人 shutdown 的最终正确性不是“线程退出”，而是 actuator、bus 和 physical system进入定义良好的 safe state。**

14. **Simulation、replay、HIL 与 fault injection 是机器人软件正确性工程的一部分，而不是上线前可选测试。**

15. **优秀 Robotics C++ 的目标不是让所有代码都“real-time/lock-free”，而是把真正需要 deterministic behavior 的最小核心隔离并证明，其余代码保持清晰、普通、可维护。**

---

# Part LX · G11 Final Gate

应该能闭卷回答：

## Real-Time

1. Fast 和 real-time 有什么根本区别？
2. Period、deadline、jitter 分别是什么？
3. 为什么 average latency不能证明 real-time behavior？
4. `SCHED_FIFO` 为什么不等于 hard-real-time guarantee？

## Time

1. measurement timestamp 和 receive timestamp有什么区别？
2. 两个相同单位的 timestamp 为什么仍可能不能相减？
3. `steady_clock` 适合解决什么问题？
4. delayed camera observation进入 estimator时为什么不能假装是“现在”？

## Memory

1. 为什么 RT loop避免 general heap allocation？
2. `reserve()` 为什么不等于 fixed-capacity guarantee？
3. pre-touch解决的是哪类成本？
4. 为什么 C++23 中不能直接假定有 `std::inplace_vector`？

## Concurrency

 1. 为什么 single-writer state对机器人特别有价值？
 2. latest-value channel 与 FIFO queue适合的语义有什么区别？
 3. 为什么 double-buffer仍然有 lifetime/reuse问题？
 4. 为什么 RT loop通常不应等待 non-RT mutex？

## Numerics

 1. 为什么裸 `double` 在 robot API中容易制造单位错误？
 2. coordinate frame为什么属于 type/API semantics？
 3. quaternion使用时至少要统一哪些 conventions？
 4. fixed-size numerical representation为什么常适合 control core？

## Control

 1. 为什么 Controller 应该使用 consistent snapshot？
 2. saturation 和 rate limiting分别限制什么？
 3. 为什么 stale command可能比 numeric out-of-range一样危险？
 4. cancellation/fault发生时 controller应该如何保持 invariant？

## Hardware

 1. 为什么 vendor SDK type不应进入 domain core？
 2. hardware read可能阻塞时为什么要重新考虑 thread topology？
 3. actuator watchdog为什么应该尽量靠近硬件？

## ROS 2

 1. 为什么 ROS callback executor不应该自动等价于 motor-control scheduler？
 2. QoS为什么必须由 message semantics决定？
 3. SensorDataQoS 为什么典型采用 best-effort/small depth？
 4. loaned message publish后为什么不能继续使用？
 5. 为什么普通 ROS publisher不适合直接放进 hard-RT update loop？

## Safety

 1. 为什么 software topic不能替代真正安全 E-stop architecture？
 2. fault为什么通常应该进入显式 state machine？
 3. 如何定义“允许向 actuator 输出 command”的完整 invariant？

---

# Part LXI · G10 → G11 的升级

G10：

```text
Input
↓
Process
↓
Output
```

主要关注：

```text
ownership
queues
backpressure
shutdown
performance
```

G11：

```text
Physical State(t)
       ↓
Estimate(t)
       ↓
Control(t)
       ↓
Actuation(t)
       ↓
Physical State(t + Δt)
```

新增：

```text
time
units
frames
deadlines
jitter
numerical stability
physical safety
```

这意味着：

> 软件系统 correctness 被扩展为 cyber-physical correctness。

---

# Part LXII · G11 完成状态

```text
G11.1   Real-Time / Deadline / Jitter
G11.2   Clock Domains / Timestamp Semantics
G11.3   Periodic Control Architecture
G11.4   Linux RT Scheduling / Affinity
G11.5   RT Memory Discipline
G11.6   Numerical Representation / Units
G11.7   Coordinate Frames / Geometry
G11.8   Sensor Acquisition / Synchronization
G11.9   State Estimation Architecture
G11.10  Control / Limits / Safety
G11.11  Hardware Interface / Drivers
G11.12  Watchdogs / Fault State Machine
G11.13  RT ↔ Non-RT Handoff
G11.14  ROS 2 / RMW / QoS / Executors
G11.15  ros2_control Integration
G11.16  Zero-copy / Loaned Buffers
G11.17  Simulation / Replay / HIL
G11.18  Testing / Timing / Observability
G11.19  Robotics Project Architecture
─────────────────────────────────────────
G11      COMPLETE / FROZEN
```

G11 到这里完成以后，这条 Modern C++ Systems Track 只剩最后一个总收束章节：

# **G12 — C++ × Zig × Rust Unified Systems Model**

G12 不再是三门语言的 feature comparison。

它会把整条路线压缩到同一组底层问题：

```text
Object
Storage
Lifetime
Ownership
Borrowing
Aliasing
Value
Allocation
Error
Genericity
ABI
Concurrency
Build
Real-Time
```

然后对同一个系统设计分别回答：

```text
C++ 如何表达？
Rust 如何约束？
Zig 如何显式控制？

语言替你证明了什么？
程序员仍必须证明什么？
机器最终看到什么？
```

最终目标不是得出“哪门语言最好”，而是建立：

> **面对一个 systems problem，先识别约束，再决定哪些约束应该由语言、类型系统、runtime、architecture 或工程规范承担。**
