# C++ Systems Track · G2 RAII & Ownership Architecture

- **Version:** 1.0 · Frozen Review Baseline
- **Prerequisite:** G1 Object Model & Lifetime
- **Language Baseline:** C++23
- **Comparison Language:** Zig
- **Scope:** RAII / Ownership / `unique_ptr` / Rule of Zero & Five / Failure Safety / `shared_ptr` / `weak_ptr` / Ownership Graph / Lease
- **Purpose:** 作为进入 G3 Value Semantics & Performance 前的长期资源管理与所有权推理手册

---

# Part 0 · G2 的根本问题

G1 解决：

> **一个 pointer/reference/view 此刻还能否合法访问 object？**

G2 进一步问：

> **究竟是谁负责保证那个 object/resource 活够久，又是谁决定它最终什么时候结束？**

统一模型：

```text
                RESOURCE
                   ▲
                   │
          lifetime controlled by
                   │
                 OWNER
                   │
       ┌───────────┼───────────┐
       │           │           │
     Value       Unique      Shared
     Owner        Owner       Owners
       │           │           │
       └───────────┼───────────┘
                   │
                   │ exposes
                   ▼
               BORROW / VIEW
            T& / T* / span / ...
```

G2 的核心不是“智能指针”。

而是：

> **Resource Lifetime Architecture。**

---

# Part 1 · Resource、Handle 与 Ownership

## 1.1 Resource 不等于 Memory

系统资源包括：

```text
heap allocation
file descriptor
socket
mutex lock
thread
GPU buffer
database transaction
mapped region
temporary file
frame-buffer lease
```

共同模式：

```text
Acquire
   ↓
Use
   ↓
Release
```

因此：

> Resource management 本质上是 lifetime management。

---

## 1.2 Handle 不等于 Resource

例如：

```cpp
int fd = ::open(...);
```

这里：

```text
fd
→ C++ int object / handle

kernel file resource
→ actual managed resource
```

同样：

```cpp
T*
```

可能只是一个 resource access handle。

所以：

```text
Handle
≠
Resource
≠
Ownership
```

---

## 1.3 Ownership 的工程定义

> **Ownership = 谁拥有结束某个 resource lifetime 并执行最终 cleanup 的责任。**

例如：

```text
Unique Owner
    │
    │ final cleanup responsibility
    ▼
 Resource
```

其它对象可能持有很多：

```text
pointer
reference
span
iterator
```

但那只是 access。

---

## 1.4 Aliasing ≠ Ownership

```cpp
int value{42};

int* p = &value;
int* q = &value;
int& r = value;
```

存在：

```text
p ─┐
q ─┼──→ value
r ─┘
```

这是 multiple aliases。

但并没有 multiple owners。

必须永久记住：

> **Many pointers ≠ shared ownership。**

---

# Part 2 · Manual Cleanup 为什么无法规模化

## 2.1 单一路径看起来很简单

```cpp
int process() {
    int fd = ::open("data.bin", O_RDONLY);

    if (fd == -1) {
        return -1;
    }

    // use fd

    ::close(fd);
    return 0;
}
```

只有：

```text
open
↓
use
↓
close
```

一条路径时没问题。

---

## 2.2 Early Return 立即破坏协议

```cpp
if (!validate(fd)) {
    return -2;
}
```

现在：

```text
acquire
↓
return
↓
cleanup skipped
```

产生 resource leak。

---

## 2.3 多资源会形成手工 Cleanup Stack

```text
Acquire A
↓
Acquire B
↓
Acquire C
```

任何失败路径都必须：

```text
Release C
↓
Release B
↓
Release A
```

程序员实际上在手工维护：

> Resource Lifetime Stack。

控制流越复杂：

```text
early return
exceptions
partial initialization
callbacks
multiple resources
```

维护成本越高。

---

# Part 3 · RAII

## 3.1 RAII 的真正定义

RAII：

> **Resource Acquisition Is Initialization**

不要仅理解成：

> constructor acquire，destructor release。

更重要的是：

> **把 Resource Lifetime 绑定到 C++ Object Lifetime。**

```text
C++ Owner Object
──────────────────────────► lifetime

constructor / acquisition
        │
        ▼
Resource owned
████████████████████████
                        │
                        ▼
                    destructor
                        │
                        ▼
                    release
```

---

## 3.2 Deterministic Cleanup

例如：

```cpp
{
    FileDescriptor file{fd};

    work();
}
```

正常 scope exit：

```text
FileDescriptor lifetime ends
↓
~FileDescriptor()
↓
close(fd)
```

exception unwinding：

```text
exception
↓
stack unwind
↓
~FileDescriptor()
↓
close(fd)
```

因此 RAII 的重要性质是：

> **deterministic cleanup under normal C++ lifetime termination / unwinding。**

不是 GC-style “以后某个时候回收”。

---

## 3.3 RAII ≠ Smart Pointer

以下全部属于 RAII：

```text
std::unique_ptr
std::vector
std::fstream
std::lock_guard
FileDescriptor
Socket
Transaction
MappedRegion
FrameLease
```

cleanup 可以是：

```text
delete
close
unlock
rollback
munmap
return_to_pool
```

所以：

> RAII 是 resource protocol → object lifetime 的映射。

---

## 3.4 C++ vs Zig

C++：

```cpp
void run() {
    File file = open_file();

    work();
}
```

cleanup protocol 位于：

```text
File type
↓
~File()
```

Zig：

```zig
fn run() !void {
    var file = try openFile();
    defer file.deinit();

    try work();
}
```

cleanup protocol 位于：

```text
lexical scope
```

可以概括：

```text
C++
type/object-driven cleanup

Zig
scope/control-flow-driven cleanup
```

---

# Part 4 · Unique Ownership

## 4.1 Unique Ownership Invariant

```text
At most one final owner
        │
        ▼
     Resource
```

可以有：

```text
many borrowers
```

但只能有：

> 一个最终 cleanup responsibility owner。

---

## 4.2 为什么 Unique Owner 禁止 Copy？

如果：

```text
Owner A ─┐
         ├──→ same resource
Owner B ─┘
```

两边都执行最终 cleanup：

> double free / double close。

因此 move-only resource owner 通常：

```cpp
FileDescriptor(const FileDescriptor&) = delete;
FileDescriptor& operator=(const FileDescriptor&) = delete;
```

---

## 4.3 为什么允许 Move？

Ownership 必须可以转移：

```text
Owner A
  │
  │ move
  ▼
Owner B
```

保持：

```text
exactly one owner
```

因此：

```cpp
FileDescriptor(FileDescriptor&& other) noexcept;
```

通常会把：

```text
source:
Owning(resource)
→ Empty

destination:
Empty/New
→ Owning(resource)
```

---

# Part 5 · `std::unique_ptr<T>`

## 5.1 正确定位

```cpp
std::unique_ptr<T>
```

不是：

> 更聪明的 `T*`。

而是：

> **unique-owning RAII object whose resource happens to be pointer-shaped。**

它编码：

```text
unique ownership
destruction
copy forbidden
move transfer
nullable/empty state
pointer-like borrow access
```

---

## 5.2 默认创建方式

```cpp
auto robot = std::make_unique<Robot>();
```

优先于：

```cpp
std::unique_ptr<Robot> robot{new Robot};
```

因为：

```text
allocation
↓
immediately enters owner abstraction
```

减少 raw owning pointer 暴露。

---

## 5.3 核心 API 按 Ownership 理解

| Operation         | Ownership Meaning                      |
| ----------------- | -------------------------------------- |
| `make_unique`     | 建立 unique ownership                  |
| destructor        | 销毁 owned resource                    |
| `operator*`, `->` | borrow pointee                         |
| `get()`           | 暴露 borrowed raw pointer              |
| `release()`       | 放弃 ownership，不销毁 resource        |
| `reset()`         | 结束当前 ownership / adopt 新 pointer  |
| move constructor  | transfer ownership                     |
| move assignment   | replace current ownership via transfer |
| copy              | forbidden                              |

---

## 5.4 `get()` vs `release()`

```cpp
T* view = owner.get();
```

：

```text
owner remains owner
view only borrows
```

而：

```cpp
T* raw = owner.release();
```

：

```text
owner → empty
raw handle now carries cleanup responsibility by convention
```

必须记：

> **`get()` borrows；`release()` transfers responsibility out。**

---

## 5.5 `unique_ptr` 不证明 Borrow Lifetime

```cpp
auto owner = std::make_unique<Robot>();

Robot* view = owner.get();

owner.reset();

view->update(); // dangling
```

所以：

```text
unique_ptr
solves ownership uniqueness

does not solve borrow lifetime
```

G1 仍然有效。

---

## 5.6 `unique_ptr<T[]>`

```cpp
auto values = std::make_unique<int[]>(count);
```

表达：

> unique ownership of dynamically allocated array。

但普通动态序列通常优先：

```cpp
std::vector<T>
```

因为 vector 同时管理：

```text
length
capacity
element lifetime
iteration
copy/move
```

---

## 5.7 Custom Deleter

完整模型：

```cpp
std::unique_ptr<T, Deleter>
```

因此可以管理：

```text
FILE*
C library handles
foreign runtime handles
custom allocated objects
```

只要 deleter 能正确表达 cleanup protocol。

例如：

```cpp
struct FileCloser {
    void operator()(std::FILE* file) const noexcept {
        if (file != nullptr) {
            static_cast<void>(std::fclose(file));
        }
    }
};

using File = std::unique_ptr<std::FILE, FileCloser>;
```

---

## 5.8 非 Pointer-shaped Resource 不要硬套 `unique_ptr`

POSIX：

```cpp
int fd;
```

更自然：

```cpp
class FileDescriptor;
```

原因：

```text
fd is integer handle
not naturally pointer-shaped
```

所以：

> dedicated RAII owner type 往往比强行使用 `unique_ptr` 更准确。

---

# Part 6 · Value Ownership 优先

## 6.1 Unique Ownership 不等于 `unique_ptr`

```cpp
class RobotRuntime {
private:
    Logger logger_;
};
```

这里：

```text
RobotRuntime
owns Logger
```

已经是 unique/value ownership。

不需要：

```cpp
std::unique_ptr<Logger>
```

---

## 6.2 Value Ownership 为什么最好推理？

没有：

```text
heap allocation
nullable owner
pointer chasing
independent lifetime
allocator overhead
```

只要：

```text
child lifetime == parent lifetime
```

优先：

```cpp
T member_;
```

所以默认 ladder：

```text
Value
↓
Unique dynamic ownership
↓
Shared ownership only if necessary
```

---

# Part 7 · Ownership Taxonomy

可以把常见关系统一成：

| Semantic Relationship       | C++ 常见表达              |
| --------------------------- | ------------------------- |
| Value ownership             | `T`                       |
| Unique dynamic ownership    | `std::unique_ptr<T>`      |
| Required mutable borrow     | `T&`                      |
| Required read-only borrow   | `const T&`                |
| Optional borrow/observer    | `T*`, `const T*`          |
| Sequence borrow             | `std::span<T>`            |
| Shared ownership            | `std::shared_ptr<T>`      |
| Shared-domain weak observer | `std::weak_ptr<T>`        |
| Pool-backed temporary right | dedicated move-only Lease |
| Raw OS resource owner       | dedicated RAII type       |

---

## 7.1 五个独立 API 维度

任何参数/返回类型都可以问：

```text
Ownership
Nullability
Mutability
Extent
Lifetime / Invalidation
```

例如：

```cpp
const T&
```

：

```text
Ownership   = borrow
Nullability = required
Mutability  = read-only
Extent      = one object
```

而：

```cpp
std::span<const T>
```

：

```text
Ownership   = borrow
Mutability  = read-only
Extent      = runtime bounded sequence
```

---

# Part 8 · Function Signature 就是 Ownership Contract

## 8.1 `T`

```cpp
void process(T value);
```

通常：

> callee 获得自己的 value。

lifetime 与 caller 相对解耦。

---

## 8.2 `T&`

```cpp
void process(T& value);
```

通常：

> required mutable borrow。

---

## 8.3 `const T&`

```cpp
void process(const T& value);
```

通常：

> required read-only borrow。

---

## 8.4 `T*`

```cpp
void process(T* value);
```

信息不足。

可能是：

```text
optional borrow
legacy API
output parameter
C-compatible handle
array start
```

所以需要额外 contract。

---

## 8.5 `std::unique_ptr<T>`

```cpp
void consume(std::unique_ptr<T> value);
```

非常清晰：

> callee takes unique ownership。

---

## 8.6 `std::shared_ptr<T>`

```cpp
void schedule(std::shared_ptr<T> value);
```

应读成：

> callee acquires a shared ownership stake。

而不是：

> 传一个 pointer。

---

## 8.7 不要泄漏 Ownership Representation

如果函数只是：

```text
read T
```

不要因为 caller 恰好有：

```cpp
std::unique_ptr<T>
```

就写：

```cpp
void inspect(const std::unique_ptr<T>&);
```

更合理：

```cpp
void inspect(const T&);
```

原则：

> **Accept the least ownership-aware abstraction the function actually needs.**

---

# Part 9 · Rule of Three / Five / Zero

## 9.1 为什么 Raw Owner 会触发 Special Member 问题？

```cpp
class Buffer {
private:
    int* data_{nullptr};
    std::size_t size_{0};
};
```

如果 `data_` owning：

默认 memberwise copy：

```text
copy pointer value
```

而不是：

```text
copy allocation ownership semantically correctly
```

于是可能 double delete。

---

## 9.2 Rule of Three

C++98：

```text
Destructor
Copy Constructor
Copy Assignment
```

如果一个 raw-resource class 需要自己管理其中一个，通常必须系统审查三个。

---

## 9.3 Rule of Five

C++11 以后再加入：

```text
Move Constructor
Move Assignment
```

所以 raw resource owner 必须审查：

```text
destruction
copy construct
copy assign
move construct
move assign
```

---

## 9.4 Rule of Five 不是目标

不是：

> 每个 class 都手写五个函数。

而是：

> 如果你已经直接管理 raw resource，就必须完整定义 resource state transition。

---

## 9.5 Rule of Zero 才是现代默认目标

```cpp
class Robot {
private:
    std::string name_;
    std::vector<Sensor> sensors_;
    std::unique_ptr<Engine> engine_;
};
```

如果 members 已经拥有正确：

```text
copy
move
destruction
```

语义，那么外层 class 不需要自己写这些机制。

这就是：

> **semantic composition。**

---

## 9.6 Rule of Zero 的本质

```text
Raw Resource
     ↓
Small Proven RAII Owner
     ↓
Higher-Level Domain Types
     ↓
Rule of Zero
```

复杂度集中在：

> 少数真正的 resource boundary types。

而不是散布到每个业务 class。

---

## 9.7 `= default` 不等于“不声明”

```cpp
~Widget() = default;
```

仍然是：

> user-declared destructor。

这会影响某些 implicit move-generation rules。

所以：

> 没有必要就不要为了“显式”机械写 special members。

---

## 9.8 Member Type 语义向上传播

如果：

```cpp
class Robot {
private:
    std::unique_ptr<Engine> engine_;
};
```

那么：

```text
unique_ptr non-copyable
↓
Robot copy also unavailable

unique_ptr movable
↓
Robot can be implicitly movable
```

前提是没有其它 user-declared special-member 规则阻止生成。

这就是 C++ ownership composition 很强的一点。

---

# Part 10 · Failure Safety

## 10.1 Exception Safety 真正研究什么？

不是：

```text
try/catch
```

而是：

> **如果 operation 中途失败，剩下的 program state 仍满足什么 guarantee？**

因此更广义应该理解：

> Failure Safety。

即使使用：

```text
std::expected
Zig error union
C error code
```

同样需要。

---

## 10.2 Object Invariant

一个 class 应保证：

```text
constructor success
→ invariant holds

operation success
→ invariant holds

operation failure
→ invariant still holds
```

资源不能：

```text
leak
double cleanup
half-own
dangling internally
```

---

## 10.3 Basic Guarantee

失败后：

```text
no resource leak
object invariants remain valid
object may have changed state
```

即：

> valid but state may change。

---

## 10.4 Strong Guarantee

失败时：

> state 保持原样。

```text
success → commit S1
failure → rollback S0
```

即：

> commit-or-rollback。

---

## 10.5 No-throw Guarantee

Operation 保证：

> 不允许 exception 逃出。

典型：

```text
destructor
swap
simple resource move
cleanup primitive
```

---

# Part 11 · Transactional Update

高质量 mutation 常采用：

```text
Prepare
↓
Validate
↓
Perform failure-prone work on temporary state
↓
No-throw Commit
↓
Automatic cleanup of old state
```

而不是：

```text
Destroy old state
↓
Start risky work
↓
Hope it succeeds
```

---

## 11.1 Example

不佳：

```cpp
model_.reset();
model_ = build_model(config);
```

如果 `build_model()` 失败：

```text
old model already gone
```

更好：

```cpp
auto next = build_model(config);
model_ = std::move(next);
```

失败：

```text
old model unchanged
```

成功：

```text
commit new model
```

---

## 11.2 Copy-and-Swap 的真正意义

```cpp
T copy{other};
swap(copy);
```

不是一个语法技巧。

而是：

```text
Prepare temporary
↓
may fail

noexcept swap
↓
Commit

temporary destructor
↓
Cleanup old state
```

属于 RAII transactional update。

---

# Part 12 · Constructor Failure

## 12.1 Complete Object 构造失败

如果 constructor 中：

```text
member A constructed
member B constructed
member C throws
```

那么：

```text
destroy B
destroy A
```

complete object 本身：

> 从未成功建立，因此不会正常运行 complete-object destructor。

---

## 12.2 为什么 Member RAII 如此重要？

Raw resource：

```cpp
class Session {
    int fd_;
    std::byte* buffer_;
};
```

constructor 中途 throw：

> 很容易 leak。

RAII members：

```cpp
class Session {
private:
    FileDescriptor fd_;
    std::vector<std::byte> buffer_;
};
```

construction failure：

> 已构造 members 自动 rollback。

---

# Part 13 · C++ vs Zig Failure Rollback

C++：

```cpp
class Session {
    Buffer buffer_;
    Socket socket_;
};
```

如果 `socket_` constructor throws：

```text
buffer_ destructor runs automatically
```

Zig：

```zig
const buffer = try allocator.alloc(u8, 4096);
errdefer allocator.free(buffer);

const socket = try Socket.connect();
errdefer socket.close();
```

Zig显式：

```text
errdefer rollback
```

C++：

```text
subobject lifetime rollback
```

可以总结：

```text
C++
type/object-driven rollback

Zig
scope/control-flow-driven rollback
```

---

# Part 14 · Shared Ownership

## 14.1 什么是真正 Shared Ownership？

```text
Owner A ─┐
Owner B ─┼──→ Resource
Owner C ─┘
```

三个 owner 都参与：

> resource 必须保持 alive。

只有：

```text
last strong owner gone
```

时 resource 才销毁。

---

## 14.2 `shared_ptr` Copy 不复制 Pointee

```cpp
auto a = std::make_shared<Model>();
auto b = a;
```

结果：

```text
a ─┐
   ├──→ same Model
b ─┘
```

复制的是：

> ownership handle。

不是 Model value。

---

## 14.3 Control Block

典型实现需要：

```text
strong/reference count
weak count
deleter
allocation metadata
```

概念：

```text
shared_ptr A ─┐
shared_ptr B ─┼──▶ Control Block ──▶ Resource
weak_ptr W ···┘
```

---

## 14.4 Resource 与 Control Block Lifetime

```text
strong_count > 0
→ Resource alive

strong_count == 0
→ Resource destroyed

weak observers remain
→ Control block may remain alive

weak_count == 0
→ Control block released
```

再次验证：

```text
storage/control metadata exists
≠
resource object alive
```

---

## 14.5 Shared Ownership 最大成本：Non-local Lifetime

Unique：

```text
one owner
→ destruction point easy to reason
```

Shared：

```text
many owners across program
→ last-owner point may be non-local
```

所以：

> deterministic rule，不等于 locally obvious destruction。

---

# Part 15 · `std::weak_ptr`

## 15.1 Weak Observer

`weak_ptr`：

> 不增加 strong ownership count，因此不延长 pointee lifetime。

它观察：

> shared ownership domain。

---

## 15.2 `lock()`

```cpp
if (auto model = weak.lock()) {
    model->run();
}
```

含义：

```text
if object alive
→ acquire temporary strong ownership
→ safe to use during this owner lifetime

if expired
→ return empty shared_ptr
```

因此：

> `lock()` = lifetime re-acquisition attempt。

---

## 15.3 为什么不先 `expired()`？

因为：

```text
check alive
↓
time passes
↓
last owner disappears
↓
use
```

存在 TOCTOU race。

正确：

> 直接 `lock()` 获得 lifetime right。

---

# Part 16 · Shared Ownership Cycles

```text
A ──strong──▶ B
▲             │
└────strong───┘
```

外部 owner 消失以后：

```text
A count >= 1
B count >= 1
```

永不归零。

结果：

> leak。

Reference counting 无法自动收集 strong cycles。

---

## 16.1 打破 Cycle

典型：

```text
Parent ──strong──▶ Child
Parent ◀··weak··── Child
```

反向关系：

> observation

而不是 ownership。

所以用：

```cpp
std::weak_ptr<Parent>
```

或者普通 borrow，取决于 topology。

---

# Part 17 · Shared Ownership ≠ Thread Safety

`shared_ptr` control-block bookkeeping 对独立 shared handles 的并发 copy/destruction 提供相应线程安全语义。

但：

```cpp
std::shared_ptr<std::vector<int>>
```

并不会自动让：

```cpp
values->push_back(...)
```

并发安全。

必须区分：

```text
shared lifetime safety
≠
pointee data-race safety
```

---

# Part 18 · Shared Ownership 的使用准则

优先只有在：

```text
multiple independent components
really need to keep same resource alive
```

时使用。

典型：

```text
independent async tasks
immutable model/config generations
callback lifetime
event fan-out
```

不要因为：

```text
很多函数都需要访问
不知道谁 delete
传起来方便
担心 raw pointer
```

就直接升级到 `shared_ptr`。

---

# Part 19 · Async Boundary

同步：

```cpp
void process(const Frame& frame);
```

caller lexical lifetime 可以保证：

```text
Frame alive through call
```

异步：

```cpp
executor.submit(...)
```

function 已返回。

因此：

> **Async boundary 经常也是 ownership boundary。**

---

## 19.1 Raw `this`

```cpp
executor.submit([this] {
    work();
});
```

只 borrow。

必须保证：

```text
*this outlives callback
```

---

## 19.2 Shared Self

```cpp
executor.submit([self] {
    self->work();
});
```

callback 成为 owner。

---

## 19.3 Weak Self

```cpp
executor.submit([weak] {
    if (auto self = weak.lock()) {
        self->work();
    }
});
```

callback 不延长 lifetime。

object 不存在时：

> no-op / cancel / domain-specific behavior。

---

# Part 20 · `enable_shared_from_this`

如果 object 已经属于某个 shared ownership domain：

```cpp
class Session : public std::enable_shared_from_this<Session> {
    ...
};
```

`shared_from_this()`：

> 获取属于同一 control block 的新 shared owner。

千万不要：

```cpp
std::shared_ptr<Session>{this};
```

因为这会创建独立 control block，可能造成：

> double deletion。

---

# Part 21 · Pool + Lease

并不是所有 multi-consumer resource 都应该 shared-own。

例如 Frame buffer：

```text
FramePool
   │ owns storage
   ▼
Buffer

FrameLease
   │ owns temporary usage right
   ▼
Buffer
```

Consumer 不负责：

```text
delete Buffer
```

而负责：

```text
release lease
↓
return buffer to pool
```

所以 Lease 是另一种 ownership semantics。

---

## 21.1 RAII Lease

```cpp
class FrameLease {
public:
    FrameLease(const FrameLease&) = delete;
    FrameLease& operator=(const FrameLease&) = delete;

    FrameLease(FrameLease&&) noexcept;
    FrameLease& operator=(FrameLease&&) noexcept;

    ~FrameLease() noexcept;

private:
    FramePool* pool_{nullptr};
    Frame* frame_{nullptr};
};
```

语义：

```text
copy forbidden
move transfers lease
destructor returns resource to pool
```

RAII 依然成立。

---

# Part 22 · Shutdown Architecture

Ownership 不只是 startup。

Shutdown 是 ownership/dependency graph 的镜像。

假设：

```text
WorkerPool borrows Logger
WorkerPool borrows ModelManager
WorkerPool holds FrameLease
```

那么必须：

```text
stop workers
↓
drain/cancel work
↓
join threads
↓
destroy tasks
↓
release FrameLeases
↓
destroy FramePool / ModelManager
↓
destroy Logger
```

原则：

> **Borrowers must end before their owners/backing resources。**

---

## 22.1 Member Declaration Order

C++ members：

```cpp
class Runtime {
private:
    Logger logger_;
    ModelManager models_;
    FramePool frames_;
    WorkerPool workers_;
};
```

构造：

```text
logger
models
frames
workers
```

析构：

```text
workers
frames
models
logger
```

所以 member order 可以编码：

> destruction dependency。

---

## 22.2 不要用 Shared Ownership 掩盖 Shutdown Bug

如果 domain 要求：

```text
Worker must stop before Logger
```

正确方案：

> 修 Worker shutdown/join protocol。

不是：

```cpp
std::shared_ptr<Logger>
```

让 Logger 神秘地继续活。

必须记：

> **Do not use shared ownership to hide an ordering bug.**

---

# Part 23 · Healthy Ownership Graph

一个成熟系统通常希望：

```text
Broad Value / Unique Ownership Tree
                +
        Explicit Borrow Edges
                +
     Narrow Shared-Lifetime Islands
                +
       Lease / Pool where needed
```

而不是：

```text
Everything is shared_ptr
```

---

# Part 24 · Robot Runtime 参考模型

```text
RobotRuntime
│
├──owns(value)────▶ Config
│
├──owns(value)────▶ Logger
│
├──owns(value)────▶ SensorManager
│                    │
│                    └──owns(unique)──▶ Sensor implementations
│
├──owns(value)────▶ ModelManager
│                    │
│                    └──shared────────▶ immutable Model generation
│                                         ▲
│                                         │ shared
│                                  InferenceTask
│
├──owns(value)────▶ FramePool
│                    │
│                    └──owns──────────▶ Frame buffers
│                                         ▲
│                                         │ lease
│                                  InferenceTask
│
└──owns(value)────▶ WorkerPool
                     │
                     └──owns──────────▶ Tasks

InferenceTask - -borrow- -▶ Logger
```

这张图基本概括了 G2 的最终目标。

---

# Part 25 · C++ vs Zig Ownership Architecture

| 维度                  | C++                           | Zig                           |
| --------------------- | ----------------------------- | ----------------------------- |
| Resource cleanup      | destructor / RAII             | `defer` / `deinit`            |
| Unique owner type     | 可强编码                      | 多依赖 API discipline         |
| 禁止 copy owner       | `= delete` / member semantics | 无直接等价语言机制            |
| Ownership transfer    | move semantics                | explicit data-flow convention |
| Value ownership       | 强                            | 强                            |
| Allocation policy     | 常由 owner abstraction 封装   | allocator 通常显式            |
| Borrow                | `T&`, `T*`, span              | `*T`, slice                   |
| Borrow lifetime proof | 弱                            | 弱                            |
| Shared ownership      | `shared_ptr`                  | 需要具体 abstraction          |
| Weak observer         | `weak_ptr`                    | 需要具体 abstraction          |
| Failure rollback      | RAII / unwinding              | `defer` / `errdefer`          |
| Pool/Lease            | dedicated RAII type           | explicit lease + defer        |

核心差异：

```text
C++
更多 ownership protocol
进入 type / object semantics

Zig
更多 allocation / cleanup protocol
留在显式 control flow
```

---

# Part 26 · Rust 第三坐标

Rust：

```text
Box<T>
Rc<T>
Arc<T>
Weak<T>
&T
&mut T
```

不仅表达 owner 类型，还静态检查更多 borrow/lifetime relationship。

但 Rust 仍不能替架构师决定：

```text
Value or Box?
Unique or Arc?
Pool or Arc?
Generation or mutation?
Who should own whom?
```

所以：

> Ownership topology 始终是 architecture problem。

---

# Part 27 · G2 Code Review Protocol

以后审查任何资源型 C++ 系统，按以下顺序。

## Step 1 — Enumerate Resources

```text
memory
fd
socket
thread
GPU buffer
model
frame
lock
transaction
```

---

## Step 2 — Identify Natural Owner

问：

> 谁应该执行最终 cleanup？

---

## Step 3 — Prefer Value Ownership

如果 lifetime 与 parent 完全一致：

```cpp
T member_;
```

---

## Step 4 — Identify Real Dynamic Lifetime

若有：

```text
runtime polymorphism
PImpl
stable address
dynamic tree
independent lifetime
```

才进入：

```cpp
std::unique_ptr<T>
```

等 dynamic owner。

---

## Step 5 — Mark Borrow Edges

```text
T&
const T&
T*
span
string_view
iterator
```

并回答：

> 谁必须 outlive 谁？

---

## Step 6 — Find Ownership Transfer Boundaries

例如：

```text
factory
queue submission
task creation
manager insertion
```

判断：

```text
value
move
unique ownership transfer
shared ownership acquisition
lease transfer
```

---

## Step 7 — Find Invalidators

```text
destroy
erase
clear
reallocation
reload
pool reuse
shutdown
generation replacement
```

---

## Step 8 — Find Shared Islands

问：

> 多个独立参与者是否真的需要共同延长 lifetime？

---

## Step 9 — Find Strong Cycles

```text
A owns B
B owns A
```

决定：

```text
weak edge
borrow edge
or redesign
```

---

## Step 10 — Review Failure Paths

问：

```text
partial construction?
allocation failure?
early return?
exception?
expected/error return?
```

是否：

```text
no leak
invariants preserved
rollback semantics明确
```

---

## Step 11 — Review Async Captures

```text
[this]
[raw_ptr]
[shared]
[weak]
[unique = std::move(...)]
```

每一种 capture 都是 lifetime semantics。

---

## Step 12 — Review Shutdown Order

确保：

> borrowers/tasks end before resources they borrow。

---

# Part 28 · 高频 Smells

看到：

```cpp
T* member_;
```

先问：

> owner or borrow？

---

看到：

```cpp
delete member_;
```

问：

> 为什么没有 RAII owner？

---

看到：

```cpp
std::shared_ptr<T>
```

问：

> 为什么 domain 真需要 shared ownership？

---

看到：

```cpp
const std::unique_ptr<T>&
```

问：

> 函数真的需要 ownership handle，还是只需要 `const T&`？

---

看到：

```cpp
[this]
```

进入 async callback：

> 立即审查 object lifetime。

---

看到：

```cpp
~Foo();
```

问：

> 为什么 Foo 需要 user-declared destructor？是否影响 implicit move？

---

看到：

```cpp
owner.reset();
owner = build_new();
```

问：

> 为什么不先 prepare new state，再 commit？

---

看到：

```cpp
std::move(x)
```

问：

> 哪个后续 move operation 真正消费 xvalue？

---

# Part 29 · 高频错误直觉

### 错误

> RAII = smart pointer。

正确：

> RAII 是 acquire/release protocol 与 object lifetime 的绑定。

---

### 错误

> Unique ownership = `unique_ptr`。

正确：

> value member 本身经常就是最佳 unique owner。

---

### 错误

> 多个 users = shared ownership。

正确：

> 多数 users 只是 borrowers。

---

### 错误

> shared_ptr 是更安全的 unique_ptr。

正确：

> 它表达不同、且更复杂的 ownership topology。

---

### 错误

> `unique_ptr` 解决 dangling。

正确：

> 它解决 owner uniqueness，不证明 borrow lifetime。

---

### 错误

> Rule of Five 是现代 class 标准模板。

正确：

> 高层 class 应尽量 Rule of Zero。

---

### 错误

> `try/catch` = exception safety。

正确：

> exception/failure safety 是 failure 后的 state guarantee。

---

### 错误

> shared_ptr thread-safe = T thread-safe。

错误。

---

### 错误

> zero-copy = shared_ptr。

错误。

可能更正确的是：

```text
Pool + Lease
```

---

### 错误

> raw pointer 出现就是坏 C++。

错误。

Raw non-owning pointer 可以非常合理。

---

# Part 30 · G2 核心术语表

| English            | 核心含义                                             |
| ------------------ | ---------------------------------------------------- |
| Resource           | 必须遵守 acquire/release protocol 的实体             |
| Handle             | 对 resource 的标识/访问表示                          |
| Ownership          | 最终 lifetime/cleanup responsibility                 |
| Borrow             | 不拥有 resource 的临时访问关系                       |
| Unique Ownership   | 单一最终 owner                                       |
| Shared Ownership   | 多 owner 共同延长 lifetime                           |
| Observer           | 非拥有访问角色                                       |
| Weak Observer      | 不延长 shared lifetime 的 observer                   |
| RAII               | resource lifetime → object lifetime                  |
| Move-only Type     | copy 非法、move 转移状态/ownership                   |
| Rule of Five       | raw-resource 类型的 special-member 全面审查          |
| Rule of Zero       | 通过 RAII members 组合，外层无需手写 special members |
| Basic Guarantee    | failure 后仍合法，无 leak，state 可改变              |
| Strong Guarantee   | commit-or-rollback                                   |
| No-throw Guarantee | exception 不逃出 operation                           |
| Control Block      | shared ownership bookkeeping                         |
| Lease              | 对 resource temporary usage right 的 owner           |
| Ownership Graph    | 决定 resource destruction topology 的关系图          |
| Invalidation       | 某操作使 borrow/view 不再合法                        |
| Shutdown Order     | resource dependency 的反向 teardown 顺序             |

---

# Part 31 · G2 最终统一公式

G1 可以写：

```text
Valid Access
=
Valid Storage
×
Active Object Lifetime
×
Correct Type
×
Bounds
×
Alignment
×
Access Rules
```

G2 补上：

```text
Object Lifetime Stability
depends on
Ownership Architecture
```

最终：

```text
Correct Native Resource Access
=
G1 Access Validity
+
G2 Ownership / Lifetime Coordination
```

也就是：

```text
Can I access it?
        ▲
        │
        │ depends on
        │
Will its owner keep it alive?
```

---

# Part 32 · G2 Final Gate

你应能够独立回答：

## RAII

1. Resource 与 handle 为什么不同？
2. RAII 为什么不等于 smart pointer？
3. RAII 如何处理 early return 与 exception？
4. C++ RAII 与 Zig `defer` 的根本差异是什么？

## Unique Ownership

1. Ownership 到底是什么责任？
2. 为什么 unique owner 禁止 copy？
3. `std::move` 与真正 ownership transfer 分别在哪里发生？
4. `unique_ptr::get()` 和 `release()` 区别是什么？
5. 为什么 `unique_ptr` 仍可能产生 dangling borrow？

## Rule of Zero

 1. Rule of Three、Five、Zero 的区别是什么？
 2. 为什么业务 class 手写完整 Rule of Five 常是 smell？
 3. 为什么 `std::vector` / `std::string` / `unique_ptr` 能让外层 class 回归 Rule of Zero？
 4. 为什么 `~T() = default` 仍值得审查 move generation？

## Failure Safety

 1. Basic Guarantee 与 Strong Guarantee 区别是什么？
 2. 为什么 prepare → commit 是重要 mutation pattern？
 3. constructor 中途 throw 时哪些 objects 会销毁？
 4. 为什么 destructor 不应该让 exception 逃出？
 5. Zig `errdefer` 与 C++ partial-construction rollback 有什么对应关系？

## Shared Ownership

 1. Aliasing 和 shared ownership 有什么区别？
 2. control block 为什么存在？
 3. strong count 降到 0 后为什么 control block 可能还存在？
 4. 为什么 shared ownership destruction point 是 non-local？
 5. 为什么 strong cycle 会 leak？
 6. weak_ptr `lock()` 在 lifetime 上做了什么？
 7. 为什么 `shared_ptr<T>` 不意味着 `T` thread-safe？

## Architecture

 1. 为什么 value member 应优先于 unique_ptr？
 2. 多个 users 为什么不等于多个 owners？
 3. Pool + Lease 与 shared_ptr 的语义差异是什么？
 4. 为什么 shared ownership 应尽量限制成 narrow islands？
 5. 为什么 shutdown order 是 ownership architecture 的组成部分？
 6. 为什么 async boundary 经常也是 ownership boundary？
 7. 为什么 shared_ptr 不能用于掩盖错误的 join/shutdown protocol？

---

# Part 33 · 如果几个月后只记住十五条

1. **Resource 不等于 memory；file、socket、lock、GPU buffer 都有 lifetime protocol。**

2. **Ownership 是最终 cleanup responsibility，不是“谁拿着 pointer”。**

3. **RAII 把 resource lifetime 映射到 C++ object lifetime。**

4. **Value ownership 是最简单的 ownership，应优先考虑。**

5. **`unique_ptr` 表达 dynamic unique ownership，而不是 unique ownership 的唯一形式。**

6. **Borrow 可以有很多份，但 borrower 不决定 resource lifetime。**

7. **`get()` 是 borrow；`release()` 是把 ownership responsibility 重新降级为 raw convention。**

8. **Rule of Zero 是现代高层 class 的默认目标；Rule of Five 主要属于真正的低层 raw-resource owner。**

9. **Failure-safe mutation 应优先 prepare → validate → no-throw commit → automatic cleanup。**

10. **Shared ownership 表示多个独立 owner 共同延长 lifetime，而不是多个 users。**

11. **`weak_ptr` 不延长 lifetime，而通过 `lock()` 在使用前临时取得 strong lifetime。**

12. **Shared ownership cycle 是 reference counting 的结构性弱点。**

13. **Pool owns storage；Lease owns temporary usage right——两种 responsibility 不应混淆。**

14. **健康的大型系统通常是 value/unique ownership tree + explicit borrows + narrow shared islands。**

15. **语言可以帮助执行 ownership contract，但“谁应该拥有谁”始终是 architecture decision。**

---

# G2 → G3

G2 到此冻结。

我们已经回答：

> **谁拥有 object/resource，它如何安全地活着和死去？**

G3 将开始回答另一组问题：

> **如果一个 object 被复制、移动、返回、传参、放进 container，到底发生什么成本？**

主线将进入：

```text
Value Semantics
    ↓
Copy
    ↓
Move
    ↓
Copy Elision
    ↓
RVO / NRVO
    ↓
Pass by Value vs const&
    ↓
Container Relocation
    ↓
SSO / SBO
    ↓
Object Size / Allocation / Indirection
    ↓
Cache Locality
    ↓
Performance-aware API Design
```

也就是从：

> **Ownership Correctness**

正式进入：

> **Value Semantics + Performance Cost Model。**
