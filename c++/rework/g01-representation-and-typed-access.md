# G1 对象表示、类型化访问与别名

前两个单元已经说明，一个地址可以在不同时刻承载不同对象，容器也可能在自身存活期间让旧借用失效。现在再收紧一个条件：即使对象活着、地址正确、范围也没有越界，能否通过另一种类型读取它？

从读数处理出发，这个问题很实际。我们可能想观察读数在内存中的字节、保存一份副本，或者检查浮点数的位表示。这几件事需要不同的操作；把指针转换成想要的类型，并不能替代它们。本单元只建立字节观察、表示复制与类型化访问的边界，不展开联合体、继承子对象和分配器的完整规则。

## 1 数值相同与字节相同是两种判断

在前面的 `Reading` 中，`value` 表达一个读数。应用关心的通常是这个数，而工具或二进制接口还可能关心它占据哪些字节。对象表示（object representation）涵盖对象占用的全部字节；值表示（value representation）则是其中参与表达数值的位。两者之间可能存在填充位（padding bits）。因此，`sizeof` 给出的空间大小，不等于应用需要传输的信息量。[C++23 对表示与填充位的定义](https://timsong-cpp.github.io/cppwp/n4950/basic.types.general)

本单元先取一个不带资源责任的整数读数 `std::uint32_t sample`。这个精确宽度类型若由实现提供，就没有填充位；本例要求环境提供它。这里不顺便假定所有平台的 `int` 都是 32 位，也不假定一个 C++ 字节必然是八位。[精确宽度整数的条件](https://timsong-cpp.github.io/cppwp/n4950/cstdint.syn)

接下来只做三件事：取得字节视图，另存一份字节快照，再从快照恢复。暂时不规定字节在文件或网络中的顺序。

## 2 字节视图仍然是一条借用路径

`std::as_bytes` 把已有 span 对应的对象表示暴露为只读字节范围，长度是原范围的字节数。它不复制目标，也不使目标延寿。这个接口把上一单元的借用模型直接带到了表示层。[as_bytes 的接口合同](https://timsong-cpp.github.io/cppwp/n4950/span.objectrep)

**文件 `representation-copy.cpp`**

```cpp
#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <span>
#include <type_traits>

int main() {
    using Word = std::uint32_t;
    static_assert(std::is_trivially_copyable_v<Word>);
    const Word original = 0x01020304u;
    Word sample = original;
    auto view = std::as_bytes(std::span{&sample, std::size_t{1}});
    std::byte snapshot[sizeof(Word)];
    std::memcpy(snapshot, &sample, sizeof(sample));
    if (view.size() != sizeof(Word)) return 1;
    if (!std::ranges::equal(view, snapshot)) return 2;

    sample = 0;
    if (std::ranges::equal(view, snapshot)) return 3;
    std::memcpy(&sample, snapshot, sizeof(sample));
    if (sample != original || !std::ranges::equal(view, snapshot)) return 4;

    Word copied = 0;
    std::memcpy(&copied, &sample, sizeof(copied));
    if (copied != original) return 5;
    copied = 7;
    if (sample != original) return 6;
    std::cout << "view tracks source; snapshot restores value\n";
}
```

```sh
clang++ -std=c++23 -O0 -g -Wall -Wextra -Wpedantic representation-copy.cpp -o representation-copy
./representation-copy
```

程序先确认视图与快照覆盖相同字节。把 `sample` 改成零以后，视图立即观察到源对象的新表示，快照却仍保存原表示，因此两者不再相等。随后把快照复制回来，`sample` 恢复原数值。最后的 `copied` 是独立对象，修改它不会改变 `sample`。正常输出为 `view tracks source; snapshot restores value`。

这里不要求第一字节必须是 `04` 或 `01`。字节顺序由当前实现决定；判据检查视图、快照和数值的关系，不把本机的一个十六进制序列写成跨平台常量。对这个无填充的整数，比较全部表示字节也不会读取结构体中未指定的填充内容。

## 3 为什么这次 memcpy 能恢复数值

关键条件不是“`memcpy` 很底层”，而是源对象的类型和平时的使用方式满足了规则。`Word` 是可平凡复制类型（trivially copyable type）；本例处理完整对象，并把保存的同一份表示复制回来，或复制到另一个已经存在的同类型完整对象。C++ 对这些情形提供数值恢复或保持的保证。[可平凡复制对象的字节复制规则](https://timsong-cpp.github.io/cppwp/n4950/basic.types.general)

复制仍要满足实际内存前提：源范围可读、目标范围可写、长度正确，`memcpy` 的两个范围不能重叠。它不检查这些条件。本例的三个存储区域彼此独立，目标 `sample` 和 `copied` 都已经初始化；不需要靠猜测隐式对象创建来解释程序。C++23 的 `memcpy` 确实还有相关隐式创建规则，但不能据此宣称它能调用任意类的构造函数。[memcpy 的 C++ 特殊规定](https://timsong-cpp.github.io/cppwp/n4950/cstring.syn)

第一单元的 `Reading` 有自定义析构函数，并不是可平凡复制类型。允许观察它的表示，不代表复制全部字节就完成了一次合法的 `Reading` 复制。若对象还持有资源指针，把地址字节复制一份更不会自动复制资源，或分配新的释放责任。是否存在复制操作、它应该做什么，是后续值语义与所有权需要回答的问题。

同样，结构体的字段逐一相等，也不保证 `memcmp` 所比较的全部字节相同；填充和类型自身的表示规则会参与结果。内存快照不能直接充当通用相等比较，更不是可以长期保存、跨机器恢复的序列化协议。

## 4 允许观察字节，不等于允许用任意类型读取

别名（aliasing）描述的是不同访问路径涉及同一个对象的关系，不意味着这些路径本身都错。例如第一单元的 `Reading*` 和 `Reading&` 就合法指向同一对象。真正要检查的是：当前这次访问所用的类型，是否允许访问目标对象的值。

C++23 的相关规则允许与对象动态类型相似的类型、对应的有符号或无符号类型，以及 `char`、`unsigned char`、`std::byte` 这几类表示访问。这里的“相似类型”是标准术语，不是“大小或字段看起来差不多”；常见的增加 const 限定不能与换成无关类型混淆。`signed char` 不在任意对象表示访问的这份名单里，也不能因为某个类型恰好占一个字节，就赋予它相同权限。[类型化访问规则](https://timsong-cpp.github.io/cppwp/n4950/basic.lval#11)

工程资料常把这组类型化访问限制称为严格别名规则（strict aliasing）。本文以 C++ 的访问规则为准，不把 `-fno-strict-aliasing` 等编译器选项当作另一套可移植的语言语义。[Clang 的相关说明](https://clang.llvm.org/docs/UsersManual.html#strict-aliasing)

考虑一个活着的 `float measured`。**反例，不执行：** 即使地址同时满足浮点和整数的大小、对齐要求，把 `&measured` 转为 `std::uint32_t*`，再通过 `*reinterpret_cast<std::uint32_t*>(&measured)` 读取，也没有获得整数访问权限。目标仍是那个浮点对象；整数不是它对应的有符号或无符号类型，也不是上述字节访问类型。这次读值违反类型化访问规则，而不只是“可能读到一个奇怪数字”。

`reinterpret_cast` 在这里转换指针，不复制数值、不建立新的整数对象，也不替代构造。转换表达式能够编译，与随后通过该指针访问是否合法，是两件事。[reinterpret_cast 的指针转换规则](https://timsong-cpp.github.io/cppwp/n4950/expr.reinterpret.cast)

这种许可也不是双向的：能把对象表示当字节观察，不代表任意字节数组都能反过来当成任意 `T`。第一单元已经处理了存储大小、对齐和对象建立；本节再补上类型化访问。三者应同时成立，不能拿其中一项替代另外两项。

## 5 bit_cast 产生另一个值，不制造另一条对象别名

如果目标确实是把一个浮点数的表示取到整数对象里，可以使用 `std::bit_cast`。它要求源类型与目标类型大小相同，且两者可平凡复制；结果是目标类型的值，而不是指向源对象的引用。[bit_cast 的约束与结果](https://timsong-cpp.github.io/cppwp/n4950/bit.cast)

下面只比较有效、确定的 `1.5F` 表示。实验显式要求八位字节、32 位 IEC 60559 二进制浮点环境；不满足时应停在编译条件检查，而不能沿用本机执行结论。没有从任意外部字节构造浮点值，也不使用 NaN 或其他特殊表示来扩大问题。

**文件 `representation-value.cpp`**

```cpp
#include <bit>
#include <climits>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <limits>

int main() {
    using Bits = std::uint32_t;
    static_assert(CHAR_BIT == 8 && sizeof(float) == sizeof(Bits));
    static_assert(std::numeric_limits<float>::is_iec559);
    static_assert(std::numeric_limits<float>::radix == 2);
    static_assert(std::numeric_limits<float>::digits == 24);
    static_assert(std::numeric_limits<float>::max_exponent == 128);

    float measured = 1.5F;
    Bits representation = std::bit_cast<Bits>(measured);
    Bits byte_copy = 0;
    std::memcpy(&byte_copy, &measured, sizeof(measured));
    if (representation != byte_copy) return 1;
    float restored = std::bit_cast<float>(representation);
    if (restored != measured) return 2;

    Bits numeric = static_cast<Bits>(measured);
    if (numeric != 1) return 3;
    std::cout << "numeric=" << numeric << "; restored=" << restored << '\n';
    measured = 2.5F;
    if (restored != 1.5F || std::bit_cast<float>(representation) != 1.5F) return 4;
    std::cout << "source=" << measured << "; restored=" << restored << '\n';
}
```

用前例相同的编译选项运行这个文件，预期输出是：

```text
numeric=1; restored=1.5
source=2.5; restored=1.5
```

`static_cast` 在此做数值转换：舍去 `1.5F` 的小数部分后，结果 1 可以由目标整数类型表示。[浮点到整数转换规则](https://timsong-cpp.github.io/cppwp/n4950/conv.fpint)不保证超出可表示范围时也安全。`bit_cast` 处理表示关系，程序再把这份表示转换回浮点，得到原来的 `1.5F`。修改 `measured` 后，`restored` 没有变化，说明它不是对源浮点对象的另一条访问路径。`memcpy` 的对照目标也是独立、已经存在的整数对象；没有通过整数指针直接读取浮点对象。

这些接口仍不承诺“任意相同长度的比特都能转换成有效值”。按 C++23 规则，`bit_cast` 的结果表示必须对应目标类型的值，源填充位和不确定值另有约束；满足大小与类型 traits，只解决调用约束，不保证任意输入都可以安全解释。本例使用无填充的整数和上述浮点环境，并从已知有效浮点值出发，避开这类未建立前提的输入。

## 6 先选操作，再检查它承担什么责任

| 目的 | 本单元采用的操作 | 没有自动得到的能力 |
| --- | --- | --- |
| 观察当前表示 | `as_bytes` 得到只读视图 | 数据副本、延寿或并发同步 |
| 保存及恢复已知表示 | 满足类型与范围前提的 `memcpy` | 任意类的复制语义或跨平台序列化 |
| 从表示取得独立目标值 | 满足约束与表示条件的 `bit_cast` | 对源对象的可写别名 |
| 转换访问路径的类型 | 指针 `reinterpret_cast` | 对象创建、合法读值或失效修复 |

这些例子没有测量哪种写法“更快”。优化器可能把合法的表示复制化成很少的指令，但源码是否满足语言规则先于机器码比较。也不运行类型化访问反例并等待 sanitizer 报错：未出现诊断不能证明任意类型别名合法。

### 6.1 用变化后的条件检验模型

1. `sample` 改成零以后，为什么字节视图变了而快照没有变？如果源对象连同其存储都已结束，快照和视图又有什么不同？
2. 已经能用 `bit_cast` 从浮点取得整数表示，为什么还不能通过整数指针读取同一个浮点对象？
3. 两个结构体每个字段都相等，能否用 `memcmp` 替代语义相等比较，并把原始字节直接作为长期文件格式？

### 6.2 推理与修正

**第一题。** 视图借用源表示，快照拥有另一组字节。源数值修改会被视图观察到，不会同步修改快照。源对象及其存储都已结束后，旧视图不能继续读取；字节数组快照仍可独立存在，但将它恢复为某个对象还需要满足相应类型和表示条件。

**第二题。** `bit_cast` 建立的是独立结果值，原来的浮点对象没有因此变成整数对象。通过指针别名读值则直接涉及源对象的类型化访问许可；大小相同、表示可转换，都不能替代这项许可。

**第三题。** 不能作为通用做法。填充和其他表示差异不等于字段值差异；文件格式还要明确字段编码、字节顺序、版本及输入校验。应按业务值定义比较和编码，而不是把当前编译器的一次内存布局当作协议。

至此，G1 把访问有效性分成了可连续追问的条件：存储是否适合，对象是否存在，借用是否失效，访问类型是否允许。接下来的 G2 才处理谁承担清理责任、怎样把这些前提封装在接口里。值类别仍留给 G3；布局成本与测量留给 G6，不在这里继续扩展对象模型条目。
