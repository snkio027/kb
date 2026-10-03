# G8 从调用表达式到二进制合同

G7 已经让读数在不同线程之间安全交接。现在把处理逻辑交给一个独立构建的库：应用程序保留原来的可执行文件，只替换库文件。头文件看起来没有变化，程序为什么仍可能读错数据？反过来，库内部换了容器、增加了成员，为什么有些接口又可以继续使用？

区别在于，caller 编译时究竟把哪些假设固化进了机器代码。源文件能够描述的规则，比 linker 实际核对的信息丰富得多。本单元沿一个真实的分离编译实验建立这条链，再解释调用约定、对象布局和运行时耦合。[第二单元](g08-c-boundary-and-ownership.md)为同一类读数处理任务建立小而明确的 C 边界，[第三单元](g08-loading-and-evolution.md)保留旧消费者，观察新提供者的加载与替换。

语言规则采用 C++23；C 文件采用 C11。寄存器、目标文件和动态库实验限定于本次 macOS arm64 工具链，不用一个平台的汇编图代替整个 C++ 模型。[验证说明](g08-verification.md)区分合同测试、目标诊断和工件观察。

## 1 旧 caller 保留了哪些信息

### 1.1 源码兼容与二进制兼容是不同实验

应用编程接口（application programming interface，API）说明源码怎样调用组件，以及合法调用应得到什么行为。应用二进制接口（application binary interface，ABI）则规定独立编译的组件怎样在机器层面交换控制与数据：如何标识实体，参数在哪里，结果写到哪里，数据怎样布局，哪些运行时设施必须一致。

如果更新头文件以后重新编译应用，编译器可以重新选择重载、计算成员偏移、分配结果存储。这是在检验 source compatibility。若应用一个字节都不变，它继续使用旧的偏移、调用序列和已内联代码；新库必须适应这些既定行为，才谈得上对这个旧消费者 binary compatible。**一起重编译成功，没有执行“旧 caller 调用新 callee”这个命题。**

这里的兼容关系有方向，也有支持环境。记 `C_old` 为旧消费者，`P_new` 为新提供者，`E` 为目标架构、运行时及构建配置，则问题是 `compatible(C_old, P_new | E)`。这个记法是工程分析模型，不是标准定义的类型 trait。它不自动推出新消费者能使用旧提供者，更不推出另一种 CPU 或标准库配置也兼容。

### 1.2 编译时消失的信息，链接时不会凭空回来

caller 编译一次按值传参时，必须根据当时的类型和目标 ABI 决定传递方式；访问数组时，必须知道元素步长；析构局部对象时，必须知道应调用什么清理路径。linker 通常拿到的是符号引用、重定位和目标文件元数据，而不是可以重新推导全部 C++ 语义的源程序。

这解释了为什么符号存在只是必要检查之一。假如调用双方使用了不一致的返回类型，某些名字改编规则仍可能给出同名符号；链接器完成绑定后，caller 和 callee 却可能分别把结果理解成寄存器值与内存写入。本文不运行这种不一致调用来追求固定崩溃：结果不能作为可移植实验判据。

语义兼容还要另查。把读数单位从毫伏改成伏，可能不改变任何机器布局，却破坏旧程序的数值解释；把“返回前完成”改成“保留指针稍后处理”，则改变了 G1/G2 的借用和释放责任。这些并不都属于狭义 ABI，但不能从完整接口审查中删除。

## 2 把 linkage 与 symbol 分开

### 2.1 同一个词常被用于不同层次

名称的链接属性决定不同作用域或翻译单元中的声明能否指称同一实体。language linkage（语言链接属性）是另一层：C++ 为函数类型以及具有外部链接名称的相应函数、变量规定语言链接。实现将它映射到自己的命名与调用规则。最后，目标文件中的 symbol（符号）才是工具实际读到的记录。[N4950 dcl.link](https://timsong-cpp.github.io/cppwp/n4950/dcl.link)

`extern "C"` 指定 C language linkage，不是“动态导出”，也不是把函数体改用 C 编译。定义仍可使用 C++ 容器和异常；是否允许异常离开该入口，需要另定合同。visibility（可见性）控制的是目标平台的导出／绑定范围；动态加载则是 loader 的工作。三者解决不同问题。

标准还区分函数名称与函数类型的 language linkage。不能因为某个编译器没有在某项类型测试中区分 C/C++ 函数类型，就反过来删掉标准中的区分。本章将公共函数声明、函数指针 typedef 和实现置于一致的 C 链接约定中，不把本机 traits 结果当成语言规则的替代品。

### 2.2 名字改编保留的信息并不完整

C++ 重载需要区分多个同名实体，目标 ABI 常用 name mangling（名字改编）将命名空间、参数类型等编码进名称。它不是完整的函数合同编码。例如 Itanium C++ ABI 对普通非模板函数名通常不编码返回类型。即使工具能 demangle 回熟悉的签名，也读不到全部前置条件、ownership 或线程合同。[Itanium C++ ABI §5.1.5](https://itanium-cxx-abi.github.io/cxx-abi/abi.html#mangling-function)

同样，不是每个源码函数都必须留下独立的最终符号。内联、未使用实体删除和链接时优化可能消除或合并实现。本节故意关闭 LTO，分别编译 caller 与 provider，先把观察对象固定下来。G5 的[实例化与生成物](g05-constant-evaluation-and-codegen.md)说明的是实体怎样产生；这里关心已经产生的机器代码怎样相互找到。

## 3 用分离编译看清命名与调用

实验 G8-B1 同时包含 C 定义、C++ 重载、C 链接的大结果返回以及浮点调用。它不是业务库，只是下一单元接口设计之前的测量探针。所有整数加法测试使用给定小值，不据此赋予 `int` 溢出新的语义。

**完整实验 G8-B1 共用类型 `abi-types.h`**

```c
#ifndef G8_ABI_TYPES_H
#define G8_ABI_TYPES_H
#include <stdint.h>
typedef struct abi_triple {
    int64_t value;
    int64_t bias;
    int64_t adjusted;
} abi_triple;
#endif
```

**完整实验 G8-B1 公开声明 `abi-probe.h`**

```c
#ifndef G8_ABI_PROBE_H
#define G8_ABI_PROBE_H
#include "abi-types.h"
#ifdef __cplusplus
extern "C" {
#endif
int native_sum(int, int);
abi_triple abi_make(int32_t value, int32_t bias);
double abi_scale(int32_t value, double factor);
#ifdef __cplusplus
}
int calibrate(int);
double calibrate(double);
#endif
#endif
```

`__cplusplus` 分支让 C 编译器只看到 C 语法。两个 calibrate 是单独的 C++ 重载，不被放进 C 链接块；这不是在要求 C linker 支持 C++ 式重载。

**完整实验 G8-B1 C 提供者 `abi-sum.c`**

```c
#include "abi-probe.h"
int native_sum(int a, int b) { return a + b; }
```

**完整实验 G8-B1 C++ 提供者 `abi-provider.cpp`**

```cpp
#include "abi-probe.h"
int calibrate(int value) { return value + 1; }
double calibrate(double value) { return value + 0.5; }
extern "C" abi_triple abi_make(int32_t value, int32_t bias) {
    return {value, bias, int64_t{value} + bias};
}
extern "C" double abi_scale(int32_t value, double factor) {
    return value * factor;
}
```

**完整实验 G8-B1 caller `abi-caller.cpp`**

```cpp
#include "abi-probe.h"
#include <cstdio>
int main() {
    const auto result = abi_make(30, -7);
    if (result.value != 30 || result.bias != -7 || result.adjusted != 23)
        return 1;
    if (native_sum(2, 3) != 5 || calibrate(8) != 9 ||
        calibrate(1.25) != 1.75 || abi_scale(12, 0.5) != 6.0)
        return 2;
    std::puts("separate callers agree on values and call boundaries");
}
```

在新临时目录保存上述文件，macOS 下可直接运行以下命令；`clang` 与 `clang++` 应来自同一工具链。`-O0` 便于初次阅读，完整执行器还会检查 `-O2`。

```sh
clang -std=c11 -O0 -Wall -Wextra -Wpedantic -c abi-sum.c -o abi-sum.o
clang++ -std=c++23 -O0 -Wall -Wextra -Wpedantic -c abi-provider.cpp -o abi-provider.o
clang++ -std=c++23 -O0 -Wall -Wextra -Wpedantic -c abi-caller.cpp -o abi-caller.o
clang++ abi-caller.o abi-provider.o abi-sum.o -o abi-caller
./abi-caller
nm abi-provider.o
nm abi-caller.o
```

程序应退出 0，并输出 `separate callers agree on values and call boundaries`。先比较 provider 中的定义与 caller 中的未解析引用，再用支持 demangle 的工具读取 C++ 名称。Mach-O 的原始 C 符号可能有前导下划线；“C 链接”不等于所有文件格式都按源代码原样拼写。

### 3.1 一个应在链接阶段失败的反例

**链接反例 G8-B1 `abi-missing.cpp`**

```cpp
// Intentional mismatch: no shared header and no C language linkage.
int native_sum(int, int);
int main() { return native_sum(2, 3) == 5 ? 0 : 1; }
```

这个文件单独编译可以成功，但与 `abi-sum.o` 链接时，本机工具链寻找的是 C++ 形式的 native_sum，而 C 定义没有提供它。

```sh
clang++ -std=c++23 -O0 -c abi-missing.cpp -o abi-missing.o
clang++ abi-missing.o abi-sum.o -o abi-missing
```

有效判据是：两个对象已成功编译，链接以正常非零状态失败，诊断指出目标 native_sum 未解析。缺头文件、编译器不可用、超时或任意其他链接错误，都不能算这个反例通过。跨语言链接的具体实现受平台约束；本次诊断展示的是本机如何暴露错误，并不声称每种不一致声明都必须被 linker 查出。

修复不是给机器符号猜一个拼写，而是让 caller 和 provider 共用同一公开声明。声明一致仍只是起点；下一节说明相同名称之下还有哪些约定。

## 4 ABI lowering 把值放到哪里

### 4.1 从抽象调用到寄存器与存储

ABI lowering 是编译器把语言层的参数、结果和对象操作落实为目标调用序列的过程。calling convention（调用约定）决定哪些参数进入通用或浮点寄存器、哪些进入栈、聚合体怎样分类、哪些寄存器由 callee 保存，以及调用边界的栈对齐。它与源代码中的重载选择分属不同层次：先知道调用什么类型的函数，才谈怎样按目标约定传它的值。

在 AAPCS64 的相应基本约定中，通用参数／结果与浮点参数／结果使用不同寄存器组，间接结果地址使用 x8。Apple arm64 又有平台差异，不能把通用 AAPCS64 的所有条款原封不动套到 Apple 上。[AAPCS64 2025Q1 §6](https://github.com/ARM-software/abi-aa/blob/2025Q1/aapcs64/aapcs64.rst#6the-base-procedure-call-standard)与 [Apple 平台补充](https://developer.apple.com/documentation/xcode/writing-arm64-code-for-apple-platforms)是本节的两层依据。

本例的 abi_make 返回三个 int64_t 成员；在本次 arm64 lowering 中，caller 准备结果存储，把地址交给 callee，callee 在该地址写结果。abi_scale 则同时接收整数和 double，提供了观察两类参数位置的机会。用以下命令分别查看两侧，而不是只盯着函数体中的加法：

```sh
clang++ -std=c++23 -O0 -S abi-provider.cpp -o abi-provider.s
clang++ -std=c++23 -O0 -S abi-caller.cpp -o abi-caller.s
```

寻找调用 abi_make 前结果地址的准备、进入 callee 后对该地址的保存与写入，以及 abi_scale 的整数转换和浮点运算。本次实际摘录、对象摘要和完整命令由验证记录保存。寄存器重命名、栈暂存、指令顺序可以随优化改变；测试不要求汇编逐行相等，也不把汇编长短当作速度。

### 4.2 隐藏结果地址不是额外的语言对象

G3 已区分 [result object 与复制消除](g03-expressions-and-return.md)。ABI 为它安排一片结果存储，不意味着源程序中又发生一次可观察的复制；相反，同一个语言结果可以直接在 caller 提供的位置构造。也不能倒过来认为“看见 sret／隐藏地址，所以保证发生了 RVO”：sret 是机器传递机制，复制消除是语言对象语义，二者回答不同问题。

更重要的推导是：如果 callee 改成要求一个隐藏结果地址，而旧 caller 没有准备它，名称绑定成功仍不能补救调用协议。对复杂 C++ 参数，是否采用间接传递还可能受复制／析构的非平凡性影响，不只是 `sizeof` 大小。因此，“结构大小没变”同样不是完整 ABI 检验。

## 5 对象布局怎样成为公开承诺

### 5.1 private 不等于二进制隐藏

当公开类被 caller 按值创建时，caller 至少需要它的大小和对齐；访问内联成员可能进一步把偏移固化进去。private 限定的是源码访问权限，不是让编译器不知道成员存在。增加 private 字段、改变基类或调整对齐，都可能使旧 caller 准备的存储不再适合新实现。

实验 G8-B2 只在一个合法程序中观察不同类型的布局，绝不把旧类型对象伪装成新类型交给函数。它测的是变更可能影响什么，不是对不兼容调用做“试试看”。

**完整实验 G8-B2 `layout-observer.cpp`**

```cpp
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <type_traits>

struct ReadingV1 { std::uint32_t id; std::int32_t value; };
struct ReadingV2 {
    std::uint32_t id;
    std::int32_t value;
    std::int64_t measurement_time;
};
class OwnerV1 { [[maybe_unused]] std::int32_t bias_ = 0; };
class OwnerV2 {
    [[maybe_unused]] std::int32_t bias_ = 0;
    [[maybe_unused]] std::int64_t processed_ = 0;
};
static_assert(std::is_standard_layout_v<ReadingV1>);
static_assert(std::is_standard_layout_v<ReadingV2>);
static_assert(std::is_trivially_copyable_v<ReadingV1>);
int main() {
    std::printf("ReadingV1 size=%zu align=%zu value_offset=%zu\n",
        sizeof(ReadingV1), alignof(ReadingV1), offsetof(ReadingV1, value));
    std::printf("ReadingV2 size=%zu align=%zu time_offset=%zu\n",
        sizeof(ReadingV2), alignof(ReadingV2), offsetof(ReadingV2, measurement_time));
    std::printf("OwnerV1 size=%zu align=%zu\n", sizeof(OwnerV1), alignof(OwnerV1));
    std::printf("OwnerV2 size=%zu align=%zu\n", sizeof(OwnerV2), alignof(OwnerV2));
}
```

用 `clang++ -std=c++23 -O0 layout-observer.cpp -o layout-observer` 编译并运行。记录 size、align 和 offset，不把本机数值写成跨平台 PASS 常量。即使尾部追加成员保持前两个字段偏移，数组元素步长和按值参数的分类也可能改变。只验证“公共前缀还在原位置”，遗漏了 caller 如何定位第二个元素。

数组问题可以直接算出来：caller 按 `base + i × sizeof(ReadingV1)` 定位第 i 个元素，若 callee 按 `sizeof(ReadingV2)` 前进，即使两种类型的 id 都在偏移零，i 大于零时也不再保证指向同一记录。对齐则决定哪些基地址适合承载该类型；总字节数足够并不能替代对齐条件。这里的地址式只解释合法数组内的布局，不授权越界指针运算或把旧对象强转成新对象。

### 5.2 PImpl 与 opaque handle 缩小了哪一层

PImpl 让公开 C++ 类保存指向隐藏实现的成员，通常将依赖和布局变化留到实现文件。但公开包装类仍需遵守自己的 ABI：大小、对齐、特殊成员、内联函数及标准库配置仍有约束；不能因为用了 unique_ptr，就由语言保证其永远等于一个裸指针大小。删除不完整类型所需的操作也应在完整定义可见处实现。

opaque handle（不透明句柄）进一步让 caller 只保存一个前置声明类型的指针，并通过 provider 的 create/destroy 操作管理它。caller 不再计算内部对象大小。这减少了布局耦合，却没有自动建立 ownership：指针可能是 owner，也可能只是 borrow，责任必须来自具体函数合同。下一单元会把这一步落到真实实现，而非停在 `create(...)` 占位签名。

### 5.3 C++ runtime 也属于依赖面

虚调用可能依赖 vtable 槽位、子对象地址调整和 thunk；RTTI 依赖类型元数据的身份与可见性；异常传播依赖展开表、personality routine、类型匹配和清理代码。C++ 标准规定应得到的语言行为，但没有规定所有编译器必须使用同一张物理虚表。[Itanium C++ ABI](https://itanium-cxx-abi.github.io/cxx-abi/abi.html)描述的是具体实现合同。

同一产品统一工具链、标准库和构建配置时，可以选择让这些机制穿过共享库边界。独立升级的 SDK 则应显式维护这个支持矩阵。`extern "C"` 工厂返回一个多态 Base*，只收紧了工厂入口的命名约定，并没有隐藏返回对象的 C++ ABI。

二进制数据也不自动成为 wire format。G1 的[对象表示](g01-representation-and-typed-access.md)区分可复制表示与合法类型访问；G6 的[布局模型](g06-layout-and-access.md)解释空间和访问成本。持久格式还要另定端序、有效值、版本及解析过程。`standard-layout`、`trivially copyable` 和 packing 分别提供不同条件，没有哪一个等同“任意平台都能直接存盘”。

## 6 怎样判断一个变更需要什么证据

先问旧 caller 固化了什么，再选择工具。nm 能回答定义和引用的名称；布局观察能回答本构建的大小与偏移；汇编帮助解释参数和返回的 lowering；旧消费者配新提供者的运行才触及替换行为。它们都无法单独证明完整兼容性。

还要保持 ODR 与配置一致性。公共 inline、模板或类定义如果因为宏和不同头文件版本而不一致，可能违反单一定义规则；跨共享库并不会自动消除这个问题。更新库也不会改写已经内联进旧 caller 的逻辑。[N4950 basic.def.odr](https://timsong-cpp.github.io/cppwp/n4950/basic.def.odr)

本章因此记录编译器、target、标准库、SDK、链接命令、对象与可执行文件摘要。记录这些信息使观察可追溯，不宣称已经证明所有工具版本都兼容。下一单元先缩小边界，再在第三单元安排一个真正保留旧消费者的有限实验。

## 7 用变化后的条件检验模型

1. public 成员函数签名不变，只给 private 增加一个 int64_t。旧应用仍可能在哪里出错？如果只持有 opaque pointer，判断有什么不同？
2. 一个 C++ 非模板函数从返回 int 改成返回大型结构，但链接器没有报错。可以据此放行升级吗？
3. 给 C++ 函数加 extern "C" 后，为什么不能同时认为“已导出”“不抛异常”“C 能使用返回的 vector”？
4. 汇编中出现了隐藏结果地址，但构造计数实验没有移动。两项观察矛盾吗？
5. ReadingV2 的前两个字段偏移与 ReadingV1 相同，为什么旧数组仍不能直接按新类型遍历？
6. 新头文件与新库一起编译运行通过，旧应用替换库也通过了一组测试。这两份结果各支持什么，仍不能证明什么？

## 8 迁移题参考推理

1. 按值创建、数组步长、内联访问及特殊成员调用都可能保留旧布局假设。opaque pointer 不需要 caller 计算内部大小，因此可以隔离这类变化；但销毁入口、有效期及机器指针表示仍须相容。
2. 不可以。名字改编不保证编码返回类型，旧 caller 与新 callee 可能使用不同结果传递方式。应拒绝不兼容签名或增加新入口，而不是用一次运行是否崩溃决定合法性。
3. 三个推论分别越过了 visibility、失败传播和类型表示边界。language linkage 没有自动导出或 catch，也没有移除 vector 的布局、分配和运行时依赖。
4. 不矛盾。结果存储地址是 ABI 实现语言调用的一种方式；语言可以直接在最终结果对象的位置构造，不必存在另一个被移动的对象。不能从指令层存取次数反推特殊成员调用次数。
5. caller 用旧 sizeof 定位相邻元素，新 callee 用新 sizeof 前进；第二个元素的地址就可能分歧。公共前缀只涉及单个对象中的部分偏移，不解决步长、总存储大小和调用分类。
6. 前者检验这份源程序能适应新接口；后者检验保留的旧机器代码在给定配置和输入上可消费新库。二者都不是所有调用、所有编译器、所有历史版本的兼容性证明，还需检查未被测试覆盖的布局与语义承诺。
