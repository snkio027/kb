# G2 资源责任与确定性清理

G1 已经回答了怎样合法访问一个对象。现在把读数写入临时文件：文件打开成功，写入途中却发现输入不合格，函数必须提前返回。指向文件的 `FILE*` 仍然是一个普通指针；它的局部变量离开作用域，并不会替我们关闭流。谁来保证这条路径也履行清理责任？

本单元沿一个临时文件句柄展开，先建立独占释放责任，再处理提前退出、部分构造、责任转移和关闭失败。[第二单元](g02-ownership-and-handoff.md)把同一判断用于读数批次的借用、延迟使用与共享。语言基线为 C++23；完整文件可在同一新目录编译，执行记录与未验证范围见[验证说明](g02-verification.md)。这些例子是学习用组件，不是完整文件事务库。

## 1 指针消失不等于资源结束

资源（resource）是需要按协议取得和归还的东西。动态存储是一种资源，打开的流、锁的持有权、线程以及缓冲池租约也是。资源句柄（resource handle）是操作资源的入口，可能表现为指针或整数；复制这个入口，不会自动产生一份新的资源，也不会说明哪份副本负责最后的释放。

`std::tmpfile()` 成功时创建一个临时二进制更新流，返回 `std::FILE*`；失败时返回空指针。本章只在新临时文件上操作，不覆盖用户文件。`std::fclose()` 负责关闭流，并有自己的失败结果。这些是 C 标准库接口，C++ 的 `<cstdio>` 沿用相应语义。[C++ 文件接口](https://timsong-cpp.github.io/cppwp/n4950/c.files)与 [C11 N1570 §7.21.4.3、§7.21.5.1](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)给出了这里使用的合同。

设想手工版本依次做三件事：打开文件、检查并写入读数、关闭文件。如果第二步增加一个提前返回，第三步就到不了；如果第二步调用的函数抛异常，普通的后续语句也不会自动执行。把 `close` 补到每个分支可以暂时修好，但以后增加第二个资源，作者又要重新判断每条路径已经取得哪些资源、应按什么顺序清理。

我们把这项责任称为所有权（ownership）：在本章的工程模型中，owner 负责执行资源的释放协议。借用者只获得约定范围内的访问权，不能擅自关闭。这里讨论的是当前组件承担的责任，不要求它拥有每个被引用的资源；外部拥有的对象、只读视图和共享资源都可以有合理的合同。

资源获取即初始化（Resource Acquisition Is Initialization，RAII）的作用，是让一份资源责任成为一个对象的状态。只要 owner 已成功建立，它的析构就有确定的清理动作。这样，调用方只需维持对象结构，不必把每条退出路径重新翻译成一份清理程序。owner 可以是普通局部对象或值成员，不需要先放到堆上。

## 2 用资源协议约束包装类型

本例的 `TempFile` 只有两种可观察状态：空，或者独占一个打开的流。空对象可以销毁、关闭和接收转移，但不能写入；拥有对象允许写入，并负责最终调用一次关闭。复制被禁止，移动后源对象为空。`close()` 显式交还关闭结果，析构则只执行不抛异常的后备关闭。

这份合同已经包含一个有意的取舍：析构不能把文件写入成功作为承诺。临时文件只是中间资源，业务需要检查关闭结果时必须显式调用 `close()`。如果业务要求原子替换正式文件、持久化或出错后恢复旧数据，那是另一个协议，不能从 RAII 推导出来。

为了稳定观察失败路径，先给出一个很薄的实验后端。正常路径实际调用 `tmpfile` 和 `fclose`；两个开关分别模拟“这次获取未取得资源”和“这次关闭报告失败”。关闭失败注入仍会真实调用 `fclose`，随后改变返回结果，**不是在本机制造磁盘故障**。计数器记录成功取得流的次数、关闭调用次数和报告的错误次数，不是操作系统泄漏检测器，也不支持多线程。

**文件 `file-api.hpp`**

```cpp
#ifndef G2_FILE_API_HPP
#define G2_FILE_API_HPP
#include <cstdio>
#include <utility>

struct FileApi {
    static inline int opened = 0;
    static inline int close_calls = 0;
    static inline int close_errors = 0;
    static inline bool fail_open = false;
    static inline bool fail_close = false;

    static std::FILE* open() noexcept {
        if (std::exchange(fail_open, false)) return nullptr;
        std::FILE* file = std::tmpfile();
        if (file) ++opened;
        return file;
    }

    static int close(std::FILE* file) noexcept {
        // Precondition: file denotes an open stream owned by the caller.
        const bool injected = std::exchange(fail_close, false);
        ++close_calls;
        const int result = std::fclose(file);
        if (result != 0 || injected) {
            ++close_errors;
            return EOF;
        }
        return 0;
    }
};
#endif
```

把故障注入放在资源接口处，能保留后面 owner 的完整状态变化。它不通过抛异常打断析构，也不依赖填满磁盘或耗尽系统描述符。代价是证据范围必须讲清楚：测试能证明包装类型怎样响应这里的返回值，不能证明某个真实设备会以同样方式失败。

## 3 把空状态和拥有状态落实到每个操作

以下头文件完整定义 owner。先沿 `create()`、`write()`、`close()` 和析构阅读；移动操作在 §6 再逐行解释。只有私有构造函数能接收裸句柄，业务调用方不能随意把一个借来的 `FILE*` 包成第二个 owner。

**文件 `temp-file.hpp`**

```cpp
#ifndef G2_TEMP_FILE_HPP
#define G2_TEMP_FILE_HPP
#include "file-api.hpp"
#include <stdexcept>
#include <string_view>
#include <utility>

class TempFile {
    std::FILE* file_ = nullptr;
    explicit TempFile(std::FILE* file) noexcept : file_(file) {}
public:
    TempFile() noexcept = default;
    static TempFile create() {
        std::FILE* file = FileApi::open();
        if (!file) throw std::runtime_error("temporary file unavailable");
        return TempFile{file};
    }
    TempFile(const TempFile&) = delete;
    TempFile& operator=(const TempFile&) = delete;
    TempFile(TempFile&& other) noexcept
        : file_(std::exchange(other.file_, nullptr)) {}
    TempFile& operator=(TempFile&& other) noexcept {
        if (this != &other) {
            (void)close();
            file_ = std::exchange(other.file_, nullptr);
        }
        return *this;
    }
    ~TempFile() noexcept { (void)close(); }

    explicit operator bool() const noexcept { return file_ != nullptr; }
    std::FILE* get() const noexcept { return file_; }

    void write(std::string_view text) {
        if (!file_) throw std::logic_error("write on empty TempFile");
        if (!text.empty() &&
            std::fwrite(text.data(), 1, text.size(), file_) != text.size()) {
            throw std::runtime_error("temporary file write failed");
        }
    }
    int close() noexcept {
        std::FILE* file = std::exchange(file_, nullptr);
        if (!file) return 0;
        return FileApi::close(file);
    }
};
#endif
```

`create()` 的关键是获取成功以后没有留下会抛异常的未受管阶段。非空指针立刻进入不抛出的私有构造函数，返回的对象接管责任。若未来在取得裸句柄后增加字符串分配、日志或校验，而这些操作可能失败，就必须先建立 owner，不能指望尚未建立的包装对象替自己清理。

`write()` 拒绝空对象，把短写转换为异常；短写以前已经产生的输出不被撤销。这里用异常只是为了让调用方显式处理失败，并观察栈展开，换成错误码也仍然需要清理。`get()` 返回借用入口，调用方不得对它执行 `fclose` 或另行接管；类型系统不会自动阻止这类违反合同的行为。

`close()` 先把 `file_` 置空，再调用后端。这样即使后端报告失败，这个 owner 也不会在析构时重试已经关闭的流。对 `fclose`，关闭操作使流与文件脱离关联；错误返回不是“可以继续拿同一个 `FILE*` 重试”的许可。别把这一处理搬到所有整数句柄或设备 API 上：释放失败以后是否仍持有资源，必须读各自的接口合同。

析构与移动赋值中的 `(void)close()` 明确忽略关闭结果。忽略是一项可见的策略，不是自动处理了错误；对这个临时资源，后备路径优先结束持有关系。如果用户需要可靠地获知关闭结果，应在 owner 仍可调用时显式关闭并检查返回值，而不是等到析构再想办法把失败送回来。

## 4 三条退出路径共用同一份清理责任

下面实际写入三字节读数，再定位到开头并读回，确认操作的确发生在可用的流上。`fseek` 同时为更新流的写转读提供所需的定位步骤。随后分别正常结束、提前返回、抛出并在外部捕获。

**文件 `cleanup-paths.cpp`**

```cpp
#include "temp-file.hpp"
#include <iostream>
#include <string_view>

void record(int mode) {
    auto file = TempFile::create();
    file.write("42\n");
    if (std::fseek(file.get(), 0, SEEK_SET) != 0)
        throw std::runtime_error("seek failed");
    char bytes[3]{};
    if (std::fread(bytes, 1, sizeof(bytes), file.get()) != sizeof(bytes) ||
        std::string_view(bytes, sizeof(bytes)) != "42\n")
        throw std::runtime_error("readback failed");
    if (mode == 1) return;
    if (mode == 2) throw 42;
}

int main() {
    for (int mode = 0; mode != 3; ++mode) {
        bool caught = false;
        try { record(mode); }
        catch (int value) { caught = value == 42; }
        if (caught != (mode == 2)) return 1;
        if (FileApi::opened != mode + 1 ||
            FileApi::close_calls != mode + 1 || FileApi::close_errors != 0)
            return 2;
    }
    FileApi::fail_open = true;
    bool rejected = false;
    try { auto file = TempFile::create(); }
    catch (const std::runtime_error&) { rejected = true; }
    if (!rejected || FileApi::opened != 3 || FileApi::close_calls != 3)
        return 3;
    std::cout << "normal/return/throw closed; failed acquire owns nothing\n";
}
```

将本单元的两个头文件与程序放在一起，编译和运行：

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic cleanup-paths.cpp -o cleanup-paths
./cleanup-paths
```

预期输出为 `normal/return/throw closed; failed acquire owns nothing`。每轮结束都检查累计次数，不能只在所有操作结束后看到“好像没有泄漏”就算通过。获取失败的第四次调用没有增加拥有的资源，也没有虚构一项关闭责任。

局部 owner 在正常离开作用域和这里实际发生的异常展开中都会析构。[块变量退出规则](https://timsong-cpp.github.io/cppwp/n4950/stmt.dcl)和[栈展开规则](https://timsong-cpp.github.io/cppwp/n4950/except.ctor)提供语言依据；实验只是具体执行的观察。未捕获异常、`std::terminate`、强制结束进程和断电不在这项保证内，不能依赖它们完整展开栈。[终止边界](https://timsong-cpp.github.io/cppwp/n4950/except.terminate)尤其需要与“确定性析构”一起理解。

## 5 外层构造失败时成员仍能履行自己的责任

读数处理会同时使用两个临时流。把两个 `TempFile` 直接作为 `Session` 成员，可以让部分构造的状态体现在对象结构里。普通非委托构造失败时，尚未完成的完整对象不会调用自身析构；已经完成构造的子对象仍按规则清理。因此，不能把所有关闭语句都堆到 `~Session()`，然后让成员只保存裸指针。

**文件 `member-failure.cpp`**

```cpp
#include "temp-file.hpp"
#include <iostream>

TempFile open_second(bool reject) {
    FileApi::fail_open = reject;
    return TempFile::create();
}

struct Session {
    static inline int destroyed = 0;
    TempFile input;
    TempFile output;
    explicit Session(int mode)
        : input(TempFile::create()), output(open_second(mode == 1)) {
        if (mode == 2) throw std::runtime_error("invalid session");
    }
    ~Session() noexcept { ++destroyed; }
};

int main() {
    { Session session(0); }
    if (FileApi::opened != 2 || FileApi::close_calls != 2 ||
        Session::destroyed != 1) return 1;
    for (int mode : {1, 2}) {
        bool caught = false;
        try { Session session(mode); }
        catch (const std::runtime_error&) { caught = true; }
        const int expected = mode == 1 ? 3 : 5;
        if (!caught || FileApi::opened != expected ||
            FileApi::close_calls != expected || Session::destroyed != 1)
            return 2;
    }
    if (FileApi::close_errors != 0) return 3;
    std::cout << "members cleaned; completed Session destructors=1\n";
}
```

沿三次构造分别推演：正常构造取得两个流，完整对象析构一次；第二成员获取失败时，只需清理第一个成员；构造函数体拒绝输入时，两个成员都已建立，都需要清理。后两次没有进入 `~Session()`，计数仍停在 1，但关闭次数从 2 增长到 3，再到 5。

成员按类中声明顺序初始化，不按初始化列表的书写次序；销毁次序相反。[成员初始化次序](https://timsong-cpp.github.io/cppwp/n4950/class.base.init)决定了依赖应怎样放置。如果日志对象必须活到文件清理完成，应先声明日志成员、后声明依赖它的文件成员，并确保析构所调用的日志操作自身也满足失败合同。排好顺序只解决生命区间，不保证日志不会失败。

本例没有使用委托构造。若委托目标已成功完成、委托体随后抛异常，完整对象析构规则不同，不能把这里的 `destroyed == 1` 当成所有构造失败的通则。G1 已经建立这项区分，G2 只把它落实到资源成员，而不重复展开全部构造形式。

## 6 移动赋值还要处理目标原有的责任

假设 `source` 正拥有一个流。移动构造先取出它的句柄，再把源置空；新对象成为唯一负责关闭的一方。没有复制文件内容，也没有移动底层流的位置。`std::move(source)` 本身只是让相应重载有机会被选中，真正取句柄和置空的是 `TempFile` 的移动构造函数；完整值类别推导留给 G3。

移动赋值多了一件事：目标可能已经拥有另一个流。本例先关闭目标的旧流，再接手源流；自移动时保持原状。如果仅覆盖 `file_`，旧流的释放责任就丢了；如果接手以后不清空源，两个对象又会试图关闭同一个流。资源类型的特殊成员必须作为一组状态转换检查，不能只补一个析构函数。

**文件 `owner-transfer.cpp`**

```cpp
#include "temp-file.hpp"
#include <iostream>
#include <type_traits>

int main() {
    static_assert(!std::is_copy_constructible_v<TempFile>);
    static_assert(!std::is_copy_assignable_v<TempFile>);
    static_assert(std::is_nothrow_move_constructible_v<TempFile>);
    static_assert(std::is_nothrow_move_assignable_v<TempFile>);
    auto source = TempFile::create();
    auto target = TempFile::create();
    auto* borrowed = source.get();
    TempFile moved(std::move(source));
    if (source || moved.get() != borrowed || FileApi::close_calls != 0)
        return 1;
    bool empty_rejected = false;
    try { source.write("bad"); }
    catch (const std::logic_error&) { empty_rejected = true; }
    if (!empty_rejected) return 2;
    target = std::move(moved);
    if (moved || target.get() != borrowed || FileApi::close_calls != 1)
        return 3;
    auto* same_owner = &target;
    target = std::move(*same_owner);
    if (target.get() != borrowed || FileApi::close_calls != 1) return 4;
    target.write("still owned\n");
    TempFile empty;
    target = std::move(empty);
    // borrowed is no longer used after target closes the stream.
    if (target || empty || FileApi::opened != 2 ||
        FileApi::close_calls != 2 || FileApi::close_errors != 0) return 5;
    std::cout << "move transfers; assignment closes old; source becomes empty\n";
}
```

`borrowed` 在本例的移动构造和接管后仍指向同一个打开的流，因为这些操作只交接句柄。最终用空对象赋值给 `target` 时，流被关闭，旧借用随之失效。不能推广成“所有类型移动都保持借用”：内联存储的类型、容器操作以及其他资源协议可能有不同规则。

下面是独立的**编译负例，不运行**，验证不能复制同一份释放责任。它应因复制构造函数已删除而失败，不是任意编译错误都算符合预期。

**文件 `owner-copy.cpp`**

```cpp
#include "temp-file.hpp"
int main() {
    auto file = TempFile::create();
    TempFile copied(file); // Expected diagnostic: deleted copy constructor.
}
```

我们没有为 `TempFile` 实现“复制时重新打开一个文件”，因为那会引入另一种资源语义。需要复制独立数据时，应明确如何取得新资源、复制多少内容以及失败后保留什么；这正是 G3 要展开的问题。更高层类型若已由这些正确的成员组成，通常无需再手工写清理函数，这就是 Rule of Zero 的设计方向。它不保证外层可复制；不可复制的成员会继续约束外层。

## 7 关闭失败不能在析构中变成业务成功

考虑一份必须检查最终输出的文件。最后一次写入没有立刻报告错误，不意味着关闭一定成功；`fclose` 还涉及缓冲输出。显式的 `close()` 返回结果，给调用方一个仍能改变业务结论的位置。析构没有返回值，若异常在栈展开中逃出析构，还可能触发终止；因此本例的析构被设计为不抛出，而不是让它负责报告全部业务错误。

**文件 `close-failure.cpp`**

```cpp
#include "temp-file.hpp"
#include <iostream>

int main() {
    {
        auto file = TempFile::create();
        file.write("42\n");
        FileApi::fail_close = true;
        if (file.close() != EOF || file) return 1;
        if (file.close() != 0 || FileApi::close_calls != 1) return 2;
    }
    if (FileApi::close_calls != 1 || FileApi::close_errors != 1) return 3;
    {
        auto file = TempFile::create();
        if (file.close() != 0 || file) return 4;
    }
    {
        auto file = TempFile::create();
        FileApi::fail_close = true; // Destructor fallback has no result channel.
    }
    if (FileApi::opened != 3 || FileApi::close_calls != 3 ||
        FileApi::close_errors != 2) return 5;
    std::cout << "explicit close reports failure; fallback does not retry\n";
}
```

第一个作用域检查两个不同命题：失败被报告，owner 同时已经为空。第二次关闭空对象按本类合同返回 0，不是在宣告第一次操作后来成功了；调用方必须保留第一次结果。第三个作用域只用计数器观察后备关闭报告过错误，程序没有把这个错误通过析构返回给业务层。

移动赋值也采用后备关闭策略，所以它的 `noexcept` 不代表旧文件一定写入成功。对临时工作流可以接受的取舍，未必适合正式输出。若目标旧资源的关闭结果重要，应先显式完成并检查，再决定是否交接新资源；必要时提供不同的具名操作，而不是强迫移动赋值承载一项可失败的提交事务。

同样，RAII 能清理准备阶段取得的流，不能撤销已经写出的外部数据。强保证必须指出保护的是哪些状态，并论证准备、提交、返回与清理的失败边界。不能只因所有局部对象都会析构，就声称整个操作“失败时什么都没发生”。更完整的失败分类可回查 [FM-4](../failure-model/fm4-raii-exception-safety.md)，这里不复制那套分类。

## 8 从清理函数回到责任边界

在这个例子里，真正重要的不是类比原来多写了多少行，而是责任有了可检查的位置。工厂负责从外部协议进入拥有状态；写入只借用现有流；移动改变责任归属；显式关闭提供失败结果；析构在其他路径中履行后备责任。普通调用方不再逐条维护这些状态转换。

这个小类仍有明确限制：错误只有简化的异常与整数结果，没有保留详细系统错误；`get()` 依赖调用方遵守借用合同；实验后端是单线程的；没有保证持久化、崩溃恢复或事务回滚。看到这些限制，不应该通过把所有问题塞进一个“万能 RAII 类”来解决。应把资源协议封装在边界处，再让业务操作声明它额外需要的保证。

其余完整程序沿用 §4 的编译选项，把文件名替换为相应的 `.cpp`；`owner-copy.cpp` 只编译并核对已删除复制构造的诊断，不运行。所有文件、输出与故障注入判据也可由验证说明中的命令统一提取执行。

### 8.1 用变化后的条件检验模型

1. 在 `FileApi::open()` 成功后、`TempFile{file}` 之前增加一段可能抛异常的字符串处理，会破坏什么？只在 `~TempFile()` 里增加关闭代码够不够？
2. `Session` 的第二成员构造失败，为什么没有调用 `~Session()`，却仍能关闭第一个流？把两个成员换成裸 `FILE*` 后还能沿用结论吗？
3. 移动赋值的目标已有一个流，源为空。什么都不做是否正确？直接覆盖目标句柄又有什么问题？
4. `close()` 返回 EOF 后对象已经为空。为什么不能重试旧 `FILE*`，又不能把随后对空对象关闭所得的 0 当作业务成功？
5. 写入已有正式文件后抛异常，所有 owner 都正确析构。这足以证明操作具有强保证吗？

### 8.2 推理与修正

**第一题。** 新增了“已经取得资源、尚未由 owner 管理”的可失败区间。异常发生时没有已构造的 `TempFile` 可供析构，所以应先建立 owner，再做可能失败的操作。析构函数里多写逻辑不能修复对象根本没有建立的问题。

**第二题。** 子对象分别拥有自己的完成状态，已完成构造的成员按异常清理规则销毁。裸指针成员的销毁只结束指针对象，不执行关闭流的协议。让成员具有正确的资源语义，才是这个组合成立的原因。

**第三题。** 本类移动赋值的结果应与源的空状态一致，因此目标原有流需要关闭，目标随后为空。什么都不做保留了不符合赋值合同的旧资源；只覆盖句柄则丢掉了释放入口。它们都不是正确的状态转换。

**第四题。** 释放责任与操作成功是两条不同的判断。对这里的流，关闭以后不能再使用该句柄；EOF 记录的是失败结果。空对象的再次关闭只说明本次无事可做，不能抹掉先前失败。其他 API 是否允许重试，应另查合同。

**第五题。** 不足。清理资源与回滚数据不同，外部文件可能已经改变。必须定义强保证覆盖的状态，并采用能保持它的更新或提交协议；本章的临时资源 owner 本身不提供这项能力。

下一单元把问题从“一个 owner 怎么关闭资源”推进到“多个调用者之间怎样安排访问与责任”，再解释何时真的需要共享所有权。
