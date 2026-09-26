# G9 · 构建、打包与原生生态

**版本：** 1.1.1 · Professional Handbook · 全书一致性修订

**状态：** 本轮编辑修订待集中审核；接受历史与冻结候选见[系列状态](README.md#基线与证据状态)。PDF **NOT BUILT / NOT VALIDATED**。

**语言基线与范围：** C++23。完整 CMake 实验声明最低 3.28，实测版本另记；最低要求不是各版本均已测试。

**阅读约定：** [Editorial Profile v1.0](editorial-profile.md) · [全书术语、证据与引用](handbook-guide.md)。

[上一章：G8](g08-abi-and-c-interop.md) · [全系列导航](README.md) · [下一章：G10](g10-systems-runtime-project.md)

## 阅读入口

本章的问题是：库在自己的仓库能构建，为什么安装后另一项目仍不能使用？先读 §1～7 建立 target、配置与包的模型，以 §18 的完整实验走通安装消费；再按实际问题阅读模块、工具、交叉编译和构建成本。后三类不是未执行就自动通过的功能清单。

首次出现的核心术语在主线中解释；代码标为机制片段时不承诺独立编译。只有完整实验标记纳入执行器。原稿的编号主题通过 `g9-topic-N` 锚点映射到对应主题组；新章节按工程问题组织，不再逐项复制数十个 Part。原稿的 Complete / Frozen 不沿用为技术验收。

- [1. 构建图与三棵目录树](#g9-section-1)
- [2. Target 与依赖传播](#g9-section-2)
- [3. 产物类型、语言要求与文件集](#g9-section-3)
- [4. 构建阶段与生成器](#g9-section-4)
- [5. 预设、工具链与交叉编译](#g9-section-5)
- [6. 依赖发现与供应策略](#g9-section-6)
- [7. 安装、导出与包配置](#g9-section-7)
- [8. 代码生成与模块依赖](#g9-section-8)
- [9. 构建优化、告警与检测配置](#g9-section-9)
- [10. 开发工具、测试与加载路径](#g9-section-10)
- [11. 项目组织与安装库示例](#g9-section-11)
- [12. 构建反模式](#g9-section-12)
- [13. 可复现性、矩阵与构建成本](#g9-section-13)
- [14. 工程配置的五层职责](#g9-section-14)
- [15. 实践路线与验证选择](#g9-section-15)
- [16. 常见误判](#g9-section-16)
- [17. C++、Zig 与 Rust 生态对照](#g9-section-17)
- [18. 完整实验：安装消费与生成依赖](#g9-section-18)
- [19. 构建复核协议](#g9-section-19)
- [20. Final Gate](#g9-section-20)
- [21. Final Gate · 参考答案与常见误判](#g9-section-21)
- [22. 工程原则与全链回查](#g9-section-22)
- [23. 参考资料与验证边界](#g9-section-23)

<a id="g9-section-1"></a>

<a id="g9-topic-0"></a>
<a id="g9-topic-1"></a>
<a id="g9-topic-2"></a>
<a id="g9-topic-3"></a>
<a id="g9-topic-4"></a>
<a id="g9-topic-5"></a>
<a id="g9-topic-6"></a>
<a id="g9-topic-7"></a>

## 1. 构建图与三棵目录树

### 1.1 CMake、后端与编译器的职责

CMake 配置项目并生成后端构建描述，不是 C++ 编译器，也不是完整包管理器。Ninja、Make 或 IDE 后端执行依赖图，编译器驱动编译、汇编和链接工具。CMakeLists 描述目标、输入、依赖、属性、使用要求及安装规则，而非逐行复述 shell 命令。

产物图中的边表示生成依赖或使用关系，不等于字节包含关系。静态库依赖另一静态库时，普通 archive 不自动嵌入依赖对象；最终链接仍须解析这些符号。G9-P1 让 core PRIVATE 依赖 helper，由消费者验证 CMake 是否保留必要链接关系。

### 1.2 源码、构建和安装是三种视图

源码树保存维护入口，包括公开头文件、实现、测试、配置模板与生成输入。构建树保存缓存、后端规则、编译数据库、对象和产物，应与源码分开，并可由记录的输入重新生成。清理前要核对具体路径及其中是否含手工材料，不把宽泛递归删除作为通用教程命令。

安装树才是另一项目得到的接口：头文件、库、可执行工具、包配置与导入目标。仓库内构建成功可能依赖源码路径、缓存或全局设置；它不证明安装包完整。学习闭环应是 configure → build → test → 临时安装 → 独立 find_package → link → run。迁移前缀和隐藏原生产者路径，可以暴露一部分偶然依赖。

<a id="g9-section-2"></a>

<a id="g9-topic-8"></a>
<a id="g9-topic-9"></a>
<a id="g9-topic-10"></a>
<a id="g9-topic-11"></a>
<a id="g9-topic-12"></a>
<a id="g9-topic-13"></a>
<a id="g9-topic-14"></a>
<a id="g9-topic-15"></a>
<a id="g9-topic-16"></a>
<a id="g9-topic-17"></a>
<a id="g9-topic-18"></a>
<a id="g9-topic-19"></a>

## 2. Target 与依赖传播

### 2.1 Target 表达需求的归属

构建目标（target）是现代 CMake 的核心对象：可包含产物、源码、编译定义/选项、语言要求、链接依赖、可见性、PIC 与头文件/模块集合。使用要求（usage requirements）描述消费者编译、链接或使用该目标需要什么，不只是一条 linker 参数。

例如 decoder 的公开头文件引用 fmt 类型，消费者也必须理解它；该依赖应进入公开接口。若 fmt 仅用于实现文件，编译接口通常可以保持私有。先从 C++ 接口事实推导 scope，再检查实际链接需求，不靠“这是公开库”猜 PUBLIC。

### 2.2 PRIVATE、PUBLIC 与 INTERFACE

PRIVATE 给目标自身使用；PUBLIC 同时给自身和消费者；INTERFACE 只描述消费者的需求。纯头文件库常用 INTERFACE 表达 include、特性和依赖，但三者都不是发布权限标记。

静态目标没有完成最终链接。PRIVATE bar 不会把 bar 的普通编译要求传播给消费者，却仍可能保留仅链接依赖，常见表达为 LINK_ONLY。包导出可能需要包含 bar 或在 Config 中找到它，不能因为 PRIVATE 就删掉。G9-P1 同时检查 helper 宏对 core 可见、对消费者不可见，以及最终链接确实解析 helper。[链接传播规则](https://cmake.org/cmake/help/v4.4/command/target_link_libraries.html)。

### 2.3 将配置附着到最小负责目标

全局 include_directories、CMAKE_CXX_FLAGS 字符串拼接和 link_directories 容易制造目录级隐式状态，污染第三方依赖和消费者。优先使用 target_include_directories、target_compile_options、target_compile_definitions 和实际/导入目标。

目录级配置并非语言上非法；问题是它往往不能清楚说明需求归属。已有 Foo::Foo 时优先消费目标，避免退回裸库名搜索；绝对库路径也不是完整依赖模型，因为它未描述头文件、定义、标准模式与传递库。

**机制示意。** 不要把 CMake 理解成“设置一堆变量”；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
add_library(vehicle_core
    src/core.cpp
)

add_executable(vehicle_app
    src/main.cpp
)

target_link_libraries(vehicle_app
    PRIVATE
        vehicle_core
)
```

<a id="g9-section-3"></a>

<a id="g9-topic-20"></a>
<a id="g9-topic-21"></a>
<a id="g9-topic-22"></a>
<a id="g9-topic-23"></a>
<a id="g9-topic-24"></a>
<a id="g9-topic-25"></a>
<a id="g9-topic-26"></a>
<a id="g9-topic-27"></a>
<a id="g9-topic-28"></a>
<a id="g9-topic-29"></a>
<a id="g9-topic-30"></a>
<a id="g9-topic-31"></a>
<a id="g9-topic-32"></a>
<a id="g9-topic-33"></a>

## 3. 产物类型、语言要求与文件集

### 3.1 选择正确产物类型

STATIC 生成对象归档；SHARED 生成可正常链接并在运行时加载的共享库；MODULE 通常供动态加载，不作为普通 target_link_libraries 依赖。OBJECT 复用已编译对象而不先归档，适用于特定组合需求，不宜机械替代普通库。

INTERFACE 目标通常不产生普通库二进制，但可携带使用要求、头文件和导出信息；带源或文件集时仍可能出现在构建图。ALIAS 提供命名空间形式的本地别名，帮助构建树与安装树消费名称接近；别名自身不是安装产物，实际目标导出名称要保持一致。

### 3.2 语言模式与头文件集合

target_compile_features(core PUBLIC cxx_std_23) 让 CMake 选择相应编译器的标准模式参数；它声明模式下限，不检查所有 C++23 库设施已实现。公开头文件使用 expected 等类型时，消费者也需要语言和库支持；Concepts 本身是 C++20，不能据“现代特性”统称为 C++23 要求。

CXX_STANDARD_REQUIRED 可在采用标准属性时防止模式降级；CXX_EXTENSIONS NO 请求不使用对应扩展模式，但不是禁用所有实现扩展的静态审计。HEADERS 文件集明确公开头文件成员、基目录和安装关系，比与目标无关的整目录安装更容易维护。

### 3.3 生成器表达式与两种接口

生成器表达式（generator expression）在生成及相关构建上下文求值，不是普通 configure-time 变量。含空格、分号或换行的表达式须按规则作为完整参数引用；为了排版把未引用表达式拆成多段，会改变 CMake 参数解析。

BUILD_INTERFACE 可使用源码/构建路径，INSTALL_INTERFACE 应相对安装前缀表达自身公开目录，不固化依赖库在开发机的位置。本批完整实例用 HEADERS 文件集维护路径关系。复杂条件可以先组织变量，但不应把每一条普通配置逻辑都写成嵌套表达式迷宫。[生成器表达式指南](https://cmake.org/cmake/help/v4.4/manual/cmake-generator-expressions.7.html)。

**机制示意。** Header 不只是“手工 install 一个目录”；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
target_sources(core
    PUBLIC
        FILE_SET HEADERS
        BASE_DIRS
            include
        FILES
            include/project/core.hpp
)
```

<a id="g9-section-4"></a>

<a id="g9-topic-34"></a>
<a id="g9-topic-35"></a>
<a id="g9-topic-36"></a>
<a id="g9-topic-37"></a>
<a id="g9-topic-38"></a>
<a id="g9-topic-39"></a>
<a id="g9-topic-40"></a>
<a id="g9-topic-41"></a>
<a id="g9-topic-42"></a>
<a id="g9-topic-43"></a>

## 4. 构建阶段与生成器

### 4.1 先定位失败阶段

Configure 处理 CMake 语言、选项、依赖发现、特性探测和目标关系；Generate 将其映射成 Ninja、Make 或 IDE 规则；Build 执行编译、归档、链接和自定义命令。后面还有 test、install 与实际运行加载，各自有不同前提。

find_package 找不到配置是配置/发现问题；undefined symbol 通常是链接问题；运行时缺少共享库则已经进入加载器。不要在每种错误下都先改 include path，应该沿 G0 的阶段模型追到对应输入和工具。

### 4.2 单配置与多配置

普通 Ninja、Unix Makefiles 通常一个构建树对应一个配置，通过 CMAKE_BUILD_TYPE 选择。Visual Studio、Xcode 和 Ninja Multi-Config 可在同一构建树中包含多个配置，并在 build/test/install 时选择。

因此到处使用 if(CMAKE_BUILD_TYPE STREQUAL Debug) 不能覆盖全部生成器。配置相关要求采用适当的 target 属性、CONFIG 表达式和命令参数；预设记录支持的调用组合。本批实际运行 Ninja 单配置，不将对多配置模型的说明冒充实测覆盖。

<a id="g9-section-5"></a>

<a id="g9-topic-44"></a>
<a id="g9-topic-45"></a>
<a id="g9-topic-46"></a>
<a id="g9-topic-47"></a>
<a id="g9-topic-48"></a>
<a id="g9-topic-49"></a>
<a id="g9-topic-50"></a>
<a id="g9-topic-51"></a>
<a id="g9-topic-52"></a>
<a id="g9-topic-53"></a>
<a id="g9-topic-54"></a>
<a id="g9-topic-55"></a>
<a id="g9-topic-56"></a>

## 5. 预设、工具链与交叉编译

### 5.1 预设记录工作流，工具链记录目标环境

CMakePresets.json 宜进入版本控制，描述团队支持的 configure/build/test 等流程；CMakeUserPresets.json 承载个人路径和机器差异，通常不共享。schema 版本按项目最低 CMake 版本选择，而不是每次复制官方示例中最大的数字。

预设名宜表达 dev、san、release 的用途。dev 关注增量构建、调试信息、告警和编辑器；san 关注诊断，不是性能基线；release 关注生产代码生成，但仍可保留符号以便 profile。LTO、assert、可见性和 ABI 选项都应是明确策略，不把 Release 等同于单个 -O3。G9-P2 只实际运行 dev 预设。

### 5.2 工具链应在探测前确定

Toolchain file 定义编译器、目标架构/系统、sysroot 和交叉环境，须在编译器识别及能力探测前生效。项目是否启用示例、测试或业务特性通常放在项目/预设层，而不是全部塞进工具链。

预设回答“如何调用和配置这个项目”，工具链回答“为哪个目标环境构建”。vcpkg 等也可借工具链入口集成发现逻辑，但这不取消两层职责的区别；切换编译器/目标时宜使用独立构建树，避免复用不相容缓存。

### 5.3 交叉构建的两类产物

代码生成器必须能在构建机运行，目标库/应用则要为目标平台生成。切换编译器路径不足以处理头文件、库、sysroot、find_program/find_library 及依赖包的环境选择。

try_compile 可以检验目标编译，try_run 还需要执行目标程序；交叉构建可能需模拟器、明确预填结果或重新设计探测。不能静默用宿主程序结果替代目标事实。本批没有配置交叉工具链、执行目标程序或验证 host/target 双图，相关路线保留为未运行。

<a id="g9-section-6"></a>

<a id="g9-topic-57"></a>
<a id="g9-topic-58"></a>
<a id="g9-topic-59"></a>
<a id="g9-topic-60"></a>
<a id="g9-topic-61"></a>
<a id="g9-topic-62"></a>
<a id="g9-topic-63"></a>
<a id="g9-topic-64"></a>
<a id="g9-topic-65"></a>
<a id="g9-topic-66"></a>
<a id="g9-topic-67"></a>
<a id="g9-topic-68"></a>
<a id="g9-topic-69"></a>
<a id="g9-topic-70"></a>
<a id="g9-topic-71"></a>
<a id="g9-topic-72"></a>
<a id="g9-topic-73"></a>
<a id="g9-topic-74"></a>
<a id="g9-topic-75"></a>

## 6. 依赖发现与供应策略

### 6.1 发现机制与导入目标

Module 模式寻找 FindFoo.cmake，由项目、CMake 或其他来源提供查找逻辑，可能依赖启发式路径和版本推断。Config 模式消费包提供的 FooConfig.cmake 等信息，通常更贴近自身目标、组件和依赖；它仍是可执行 CMake 代码，不是安全解析任意不可信数据。

导入目标（imported target）把已存在的库、include、定义、语言要求和传递依赖表达为 Foo::Foo。消费者尽量通过 find_package(... CONFIG REQUIRED) 加命名空间目标消费，而非拼 FOO_LIBRARIES/INCLUDE_DIRS。CMake 4.4 还描述 CPS 发现能力，其开关和状态须按版本核对；本批只验证传统 Config package。[find_package](https://cmake.org/cmake/help/v4.4/command/find_package.html)。

### 6.2 获取依赖和使用依赖不是同一层

FetchContent 可获取并接入源码，使依赖进入同一次配置/构建环境，适合受控的小型源码依赖；它不是完整包管理器。大量依赖共处一个 configure universe，会产生选项冲突、policy 交互和配置成本。

Conan 2 可通过工具链与依赖配置生成器连接 CMake；CMakeDeps/CMakeConfigDeps 的具体状态要按锁定版本查阅。vcpkg manifest 表达项目依赖并通过相应集成提供发现信息。两者都不应迫使核心 CMakeLists 到处写包管理器分支；理想接口仍是目标和 find_package。本批不下载、不运行这些包管理流程。

### 6.3 明确四类供应来源

系统包有操作系统整合和安全更新优势，但版本随发行环境变化；包管理器提供依赖声明和二进制/源码流程，仍需锁定配置；源码接入便于统一构建，但增加共同配置压力；vendor 提供离线控制，也带来更新、仓库规模和许可维护责任。

选择时比较组织的配方、二进制缓存、交叉目标、注册表、发布和 CI 需求，不宣布 Conan/vcpkg 存在普遍赢家。同一项目可合理混用来源，但应规定边界，避免各开发机偶然安装的软件决定构建结果。

**机制示意。** `find_package`；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
find_package(fmt CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        fmt::fmt
)
```

[机制片段 · 不承诺独立编译]

```cmake
include_directories(${FMT_INCLUDE_DIR})
link_libraries(${FMT_LIBRARY})
```

<a id="g9-section-7"></a>

<a id="g9-topic-76"></a>
<a id="g9-topic-77"></a>
<a id="g9-topic-78"></a>
<a id="g9-topic-79"></a>
<a id="g9-topic-80"></a>
<a id="g9-topic-81"></a>
<a id="g9-topic-82"></a>
<a id="g9-topic-83"></a>
<a id="g9-topic-84"></a>
<a id="g9-topic-85"></a>
<a id="g9-topic-86"></a>

## 7. 安装、导出与包配置

### 7.1 安装、导出、配置各解决什么

安装规则决定产物和公开头文件放在哪里；GNUInstallDirs 提供标准安装目录变量，适应 lib/lib64 等布局策略。install(TARGETS ... EXPORT ...) 把目标归入导出集合，install(EXPORT ...) 生成安装后的目标描述。命名空间名称既便于区分来源，也让不存在的目标更早报错。

包 Config 文件负责准备依赖、载入导出目标和处理组件。configure_package_config_file 帮助形成相对安装前缀的可迁移配置，但不能修复任意手写绝对路径。生产者 include/source/build 路径不应泄漏进公开安装接口；依赖应通过自身目标提供信息。

### 7.2 版本规则与传递依赖

write_basic_package_version_file 生成版本接受策略，SameMajorVersion 是发布者声明的兼容规则，不会自动比较 ABI、符号、布局或语义。G9-P1 实际检查支持的请求能发现包、不支持的主版本被配置诊断拒绝，不把这等同于 G8 的旧二进制升级验证。

导出目标需要外部 Foo::Foo 时，Config 通常先 include(CMakeFindDependencyMacro)、find_dependency(Foo CONFIG)，再加载自己的 targets。静态 PRIVATE 链接依赖也可能需要，不能只对 PUBLIC 依赖做发现。本批选择把 helper 一并安装导出，避免网络或外部包管理器成为实验前提。

### 7.3 迁移后独立消费

消费者是另一份 CMake 项目，只通过 Config 包和命名空间目标获得使用要求。实验先安装到临时前缀，再移动前缀、隐藏原生产者源码和构建目录，在新构建树配置消费者，并限制注册表及环境搜索的偶然帮助。

这一结果说明本次静态包可独立消费，不说明完全 hermetic、跨机器或逐字节可复现。编译器、SDK、系统库仍来自本机；共享库 RPATH、DLL 搜索、签名和发布事务是其他合同。[包配置辅助模块](https://cmake.org/cmake/help/v4.4/module/CMakePackageConfigHelpers.html)。

**机制示意。** `install(EXPORT ...)`；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
install(
    EXPORT MyProjectTargets
    NAMESPACE MyProject::
    DESTINATION
        ${CMAKE_INSTALL_LIBDIR}/cmake/MyProject
)
```

**机制示意。** Exported Target 依赖另一个 Package；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
include(CMakeFindDependencyMacro)
find_dependency(fmt CONFIG)
```

[机制片段 · 不承诺独立编译]

```cmake
include(
    "${CMAKE_CURRENT_LIST_DIR}/MyProjectTargets.cmake"
)
```

<a id="g9-section-8"></a>

<a id="g9-topic-87"></a>
<a id="g9-topic-88"></a>
<a id="g9-topic-89"></a>
<a id="g9-topic-90"></a>
<a id="g9-topic-91"></a>
<a id="g9-topic-92"></a>
<a id="g9-topic-93"></a>
<a id="g9-topic-94"></a>
<a id="g9-topic-95"></a>

## 8. 代码生成与模块依赖

### 8.1 生成输入和输出必须进入图

如果输入模式变化应导致生成源码变化，add_custom_command(OUTPUT ...) 应声明输出、生成命令及输入依赖，必要时说明额外产物。生成文件再列入实际 target 的源集合，使后端知道何时运行及何时编译。

configure_file 适合由项目配置产生的模板；execute_process 在 configure 阶段运行，不会自动成为后续构建依赖图。不能把每次配置恰好运行过脚本当作增量依赖完整。G9-P2 修改数据输入后只 build，并验证新值；故意漏掉 DEPENDS 的变体用陈旧值暴露错误。[自定义生成命令](https://cmake.org/cmake/help/v4.4/command/add_custom_command.html)。

### 8.2 模块需要新的依赖顺序

传统 include 是文本包含；命名模块还要准备可供 import 的编译器模块信息。A import B 时，构建图必须安排 B 的相关产物先于 A 的编译，因而需要依赖扫描与工具链集成，不是把 hpp 改成 cppm 就完成迁移。

CMake 的 CXX_MODULES 文件集从 3.28 引入，但可用组合还涉及编译器、扫描器、生成器、安装/导出与工具支持。C++23 import std 的语言存在性不等于当前标准库和 CMake 集成可用。此批主验证采用 headers；模块路线保留但 NOT RUN，不因设置 cxx_std_23 自动升级状态。[模块支持矩阵](https://cmake.org/cmake/help/v4.4/manual/cmake-cxxmodules.7.html)。

<a id="g9-section-9"></a>

<a id="g9-topic-96"></a>
<a id="g9-topic-97"></a>
<a id="g9-topic-98"></a>
<a id="g9-topic-99"></a>
<a id="g9-topic-100"></a>
<a id="g9-topic-101"></a>
<a id="g9-topic-102"></a>
<a id="g9-topic-103"></a>
<a id="g9-topic-104"></a>
<a id="g9-topic-105"></a>
<a id="g9-topic-106"></a>
<a id="g9-topic-107"></a>
<a id="g9-topic-108"></a>
<a id="g9-topic-109"></a>

## 9. 构建优化、告警与检测配置

### 9.1 PCH、Unity、LTO 优化不同阶段

PCH 复用稳定头文件解析产物，可减少前端工作，但引入失效成本与工具链依赖；源码不能依赖 PCH 偶然提供缺失 include。Unity 合并翻译单元，可能减少重复解析，也可能造成匿名命名空间、static 名称和宏冲突。非 Unity 构建仍应正确。

LTO/IPO 保留中间表示或摘要供链接期跨 TU 优化，可能带来内联、常量传播和去虚化，也增加链接耗时、内存与诊断复杂度。用 IPO 属性前检查工具链支持，并根据目标工作负载决定，不把 Release 自动等同于“所有优化全开”。本批未测量这些优化。

### 9.2 告警是项目策略，不是默认下游合同

告警选项通常 PRIVATE，尤其不宜把 -Werror 强加给使用不同编译器的消费者。内部 CI 严格告警和第三方接口要求是两件事；也不应让目录级全局告警污染受控范围外的依赖。

接口辅助目标可以复用告警配置，但 PRIVATE 链入静态库仍可能影响导出图。未导出的 project_warnings 不会仅因名字里有 private 就自动消失；需设计 build-only 关系并检查 export。小型示例直接给实际目标设置 PRIVATE 编译选项，更容易看清归属。

### 9.3 动态检测要覆盖编译与最终链接

ASan、UBSan、TSan 和 coverage 插桩会改变二进制、时序和布局，应由独立 profile 管理，不能混入生产性能结论。通常既需要编译选项，也需要在最终链接中带上对应运行时；给静态库配置一个不会发生的普通链接步骤，并不能自动完成这一点。

项目应明确哪些目标和依赖采用插桩、哪些组合受支持，再用 target_compile_options/target_link_options 表达。检测器没有报错仍不是所有未定义行为或并发协议正确性的证明；G9 本批没有新增动态检测结果。

**机制示意。** CMake 中是 IPO Property；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
set_property(
    TARGET core
    PROPERTY
        INTERPROCEDURAL_OPTIMIZATION TRUE
)
```

<a id="g9-section-10"></a>

<a id="g9-topic-110"></a>
<a id="g9-topic-111"></a>
<a id="g9-topic-112"></a>
<a id="g9-topic-113"></a>
<a id="g9-topic-114"></a>
<a id="g9-topic-115"></a>
<a id="g9-topic-116"></a>
<a id="g9-topic-117"></a>
<a id="g9-topic-118"></a>
<a id="g9-topic-119"></a>
<a id="g9-topic-120"></a>
<a id="g9-topic-121"></a>
<a id="g9-topic-122"></a>
<a id="g9-topic-123"></a>

## 10. 开发工具、测试与加载路径

### 10.1 开发工具消费真实构建信息

compile_commands.json 记录每个翻译单元实际需要的 include、宏、语言模式与命令。clangd 应消费对应配置的数据库；诊断缺头文件时先检查数据库是否过期、生成头是否存在及构建描述是否完整。CMake 的编译数据库支持也取决于生成器，并非所有 IDE 后端都相同。

clang-tidy 可作为 target 编译钩子、独立 CI 检查或编辑器诊断；成本不同，应分配置。clang-format 管理格式，不是 C++ 构建正确性证明，宜单独检查，避免把格式修改混入正常编译的副作用。

### 10.2 测试、基准和覆盖率不要混成一个结论

CTest 负责登记并调度测试，不自动决定其命题是否有效。组件测试应通过真实公开 target 消费，明确需要时才绕过接口做白盒测试；还要有独立安装消费路径。dev test preset 使调用方式固定，但“零个测试成功退出”不能冒充通过。

Benchmark 需要适当优化配置、输入和噪声控制，不基于 Debug/ASan 结果得出生产速度结论。Coverage 也是独立插桩配置；覆盖率数字不能替代有判别力的断言。本批只报告构建/消费与生成结果，不提供性能或并发检测证据。

### 10.3 可见性、PIC 与运行加载

G8 的导出策略可映射到 CXX_VISIBILITY_PRESET、VISIBILITY_INLINES_HIDDEN 和显式导出宏。PIC 使用 POSITION_INDEPENDENT_CODE 表达；静态对象若将进入共享库，是否需要 PIC 应在该产物组合中检查，不能只看后缀。

链接成功仍不保证运行加载正确。ELF 的 RPATH/RUNPATH、Mach-O 的 install name/@rpath/@loader_path 和 Windows 的 DLL 搜索属于不同平台机制。避免把开发机构建目录写死进交付产物；G8-B2 仅在本机验证相对加载，G9-P1 是静态包，不替代完整共享包迁移检查。

**机制示意。** Test 也是 Target Consumer；以下仅展示接口或结构，所需头文件、依赖类型及实现须另行补齐。

[机制片段 · 不承诺独立编译]

```cmake
include(CTest)

add_executable(core_tests
    tests/core_test.cpp
)

target_link_libraries(core_tests
    PRIVATE
        MyProject::core
)

add_test(
    NAME core.unit
    COMMAND core_tests
)
```

<a id="g9-section-11"></a>

<a id="g9-topic-124"></a>
<a id="g9-topic-125"></a>
<a id="g9-topic-126"></a>
<a id="g9-topic-127"></a>
<a id="g9-topic-128"></a>
<a id="g9-topic-129"></a>
<a id="g9-topic-130"></a>
<a id="g9-topic-131"></a>
<a id="g9-topic-132"></a>
<a id="g9-topic-133"></a>
<a id="g9-topic-134"></a>
<a id="g9-topic-135"></a>
<a id="g9-topic-136"></a>

## 11. 项目组织与安装库示例

### 11.1 项目结构服务目标归属

根 CMakeLists 管理最低版本、project、共同项目决策和子目录组织；组件负责自己的源成员、公开头、依赖和测试。include/src/apps/tests/benchmarks 等结构是常见手段，不是必须复制的模板。目标边界和所有权明确比目录名字更重要。

选项应表达真实可支持能力。shared/static、测试开关、模块、异常或引擎模式会扩大配置空间；列出选项不等于所有组合受支持。发布矩阵应明确实际承诺的集合，避免无测试的 2^N 组合。

### 11.2 可安装库的完整职责

完整生产者至少需要实际目标、稳定消费名称、公开文件集、语言要求、实现依赖、适当告警、安装规则、导出集合、Config/Version 配置以及测试。相关片段若缺模板、依赖目标或消费者，不应标为“完整可发布工程”。

G9-P1 给出完整文件集合，最低 CMake 声明为 3.28；实际执行工具版本另记。最低版本声明不是从 3.28 起所有版本都实测过。静态 helper 一并导出，告警直接附着实际目标，公开头文件使用 expected 验证消费者获得语言/库能力。

### 11.3 先定义独立消费者

消费者只写 find_package 和 target_link_libraries，不手工补生产者 include、库路径或编译宏。公开头文件需要的要求应自动传播，而实现 helper 宏不应泄漏。若发现消费者必须复制一串 README flags 才成功，应先审查 target interface。

构建树别名与导出名称保持接近，能减少两种消费方式的差异，但不能让本仓库测试代替安装后验证。完整实验在后文集中维护，避免多个不一致的 CMake 配置成为并行示例。

<a id="g9-section-12"></a>

<a id="g9-topic-137"></a>
<a id="g9-topic-138"></a>
<a id="g9-topic-139"></a>
<a id="g9-topic-140"></a>
<a id="g9-topic-141"></a>
<a id="g9-topic-142"></a>
<a id="g9-topic-143"></a>
<a id="g9-topic-144"></a>
<a id="g9-topic-145"></a>
<a id="g9-topic-146"></a>
<a id="g9-topic-147"></a>

## 12. 构建反模式

### 12.1 隐式状态与路径反模式

把所有 flags 放 CMAKE_CXX_FLAGS、全局 include/link directory、硬编码本机库路径，都会让需求归属和消费关系变模糊。有导入目标时退回裸库名，会丢失相应使用要求；安装接口出现开发机绝对路径，会使包在原仓库之外失效。

file(GLOB) 即使使用 CONFIGURE_DEPENDS 也需要理解生成器行为和源码成员变化；公开库通常显式列源更清楚。问题不是“任何 glob 都违法”，而是不应为省几行清单牺牲可见的图。

### 12.2 依赖、告警和框架反模式

把所有第三方依赖都 FetchContent 进一个配置环境，会扩大 policy/选项交互和构建成本。到处写 Conan/vcpkg 分支，使供应策略侵入项目语义。全局 -Werror 则可能把不受控消费者或依赖变成项目内部告警政策的受害者。

库从未安装给独立消费者，就不能把仓库构建成功当作包正确。大量动态变量、宏和字符串技巧也不等于专业 CMake；复杂业务生成逻辑宜交给合适工具，CMake 保持可读的输入/输出/依赖关系。

<a id="g9-section-13"></a>

<a id="g9-topic-148"></a>
<a id="g9-topic-149"></a>
<a id="g9-topic-150"></a>
<a id="g9-topic-151"></a>
<a id="g9-topic-152"></a>
<a id="g9-topic-153"></a>
<a id="g9-topic-154"></a>
<a id="g9-topic-155"></a>
<a id="g9-topic-156"></a>
<a id="g9-topic-157"></a>
<a id="g9-topic-158"></a>
<a id="g9-topic-159"></a>
<a id="g9-topic-160"></a>
<a id="g9-topic-161"></a>

## 13. 可复现性、矩阵与构建成本

### 13.1 可追踪、可再构建与位级复现

至少记录源码身份、编译器/标准库/SDK、CMake/后端、依赖版本、目标平台及选项。相同源码不保证相同二进制；manifest、lock 和 recipe revision 帮助约束输入，但路径、时间戳、环境和工具链也可能影响结果。

Hermetic 构建尝试排除偶然系统输入；发行版打包则可能明确选择系统依赖。目标应匹配交付模式，而不是把所有项目都宣布为 hermetic。本批清理部分搜索环境，只检验同机安装消费，不声称位级复现或完全隔离。

### 13.2 矩阵与构建成本

选择真实承诺的编译器、OS、架构、配置及 shared/static 集合，按快速 PR、主干和周期性检查分层；不要为追求全覆盖做无意义笛卡尔积。性能、安装消费者、ABI 和动态检测各有不同环境要求。

构建成本应区分 configure、clean build、实现改动的增量编译、公开头变动和链接。可用手段包括减少头依赖、前置声明、PImpl、目标划分、模块、PCH、Unity、链接器和分布式/缓存编译；先确认瓶颈，再选择工具。公开 include 的传递影响既是接口设计问题，也是构建图问题。

### 13.3 缓存与分发包

编译缓存依赖有效的输入键：编译器、选项、预处理内容、路径和环境等。随机宏、时间戳及无意义路径漂移可能降低命中；缓存命中也不能证明源依赖声明完整。

CPack 位于安装树到归档/安装器的分发层，不会替错误 install/export 规则补头文件或修复路径。先完成 build、test、install、独立 consumer，再讨论归档、签名及正式发布。此次不生成发行包。

<a id="g9-section-14"></a>

<a id="g9-topic-162"></a>
<a id="g9-topic-163"></a>
<a id="g9-topic-164"></a>
<a id="g9-topic-165"></a>
<a id="g9-topic-166"></a>
<a id="g9-topic-167"></a>

## 14. 工程配置的五层职责

### 14.1 五层职责独立维护

项目语义层规定 targets、源码成员、依赖 scope、语言和安装/导出；工具链层规定编译器、架构和 sysroot；构建配置层区分 dev/san/release/coverage；依赖解析层规定 system、包管理器、FetchContent 或 vendor 来源；制品交付层规定安装前缀、包配置及分发形式。

这些层可以有明确连接，但不应揉成无法复用的巨型 CMakeLists。学习者应能够指认每个选项属于哪一层，以及它改变的是接口、构建环境还是观察方式。

<a id="g9-section-15"></a>

<a id="g9-topic-168"></a>
<a id="g9-topic-169"></a>
<a id="g9-topic-170"></a>
<a id="g9-topic-171"></a>
<a id="g9-topic-172"></a>
<a id="g9-topic-173"></a>
<a id="g9-topic-174"></a>
<a id="g9-topic-175"></a>
<a id="g9-topic-176"></a>

## 15. 实践路线与验证选择

### 15.1 保留九条路线，明确本批执行集合

原有练习包括全局配置改 target、推导 PUBLIC/PRIVATE、可安装库、预设、交叉编译、依赖接入、代码生成、模块和构建成本。G9-P1 落实静态 PRIVATE 链接与安装消费；G9-P2 落实 dev 预设与输入变化后的重新生成。完整文件和判据在后文提供。

交叉工具链应能区分宿主生成器和目标产物；依赖练习比较不同来源但保持消费 target 稳定；模块练习关注扫描和排序；构建成本练习应保留基线与配置。上述扩展未在本批执行，不从两个已跑通流程推断其他能力通过。

<a id="g9-section-16"></a>

<a id="g9-topic-177"></a>
<a id="g9-topic-178"></a>
<a id="g9-topic-179"></a>
<a id="g9-topic-180"></a>
<a id="g9-topic-181"></a>
<a id="g9-topic-182"></a>
<a id="g9-topic-183"></a>
<a id="g9-topic-184"></a>
<a id="g9-topic-185"></a>
<a id="g9-topic-186"></a>
<a id="g9-topic-187"></a>
<a id="g9-topic-188"></a>
<a id="g9-topic-189"></a>
<a id="g9-topic-190"></a>
<a id="g9-topic-191"></a>

## 16. 常见误判

### 16.1 模型误判

CMake 不是编译器，target_link_libraries 不只是 linker 命令，PUBLIC 也不是“对外发布”。只有 .a 路径并没有表达完整依赖；把所有 flags 堆成字符串不等于配置简单。Preset 和 toolchain 分工不同，包管理器不替代项目构建图，FetchContent 也不自动成为完整供应系统。

Release 不等于单个 -O3，模块不会因为替代文本 include 就自动让构建系统更简单。clangd 错误可能来自编译数据库，而不只是编辑器设置；交叉编译也不只是更换编译器可执行文件。

### 16.2 验证误判

本仓库能链接不代表安装包完整；PCH、Unity 和 LTO 都有特定收益与代价，不应无测量全开。更长的 CMakeLists 不是成熟度指标。

最危险的简化是“build 返回 0，所以依赖图正确”。G9-P2 的错误变体仍能成功构建并运行，只是观察到旧数据；需要明确值判据，不能用编译成功替代生成依赖验证。

<a id="g9-section-17"></a>

<a id="g9-topic-192"></a>
<a id="g9-topic-193"></a>
<a id="g9-topic-194"></a>
<a id="g9-topic-195"></a>
<a id="g9-topic-196"></a>

## 17. C++、Zig 与 Rust 生态对照

### 17.1 不同生态组织相同责任

C++ 的原生构建生态由 CMake、其他构建系统、包管理器、CTest 和外部工具组合，历史兼容面广。Zig build 以语言/工具链的产物图接口组织 target、优化和模块；Cargo 更集中地组织包、依赖、feature、构建和测试。它们的集成程度不同，最终都需说明输入、目标和消费合同。

用 Zig 驱动内部 C++ 构建可以是合理选择，但参与第三方 CMake SDK、机器人/HPC 等生态仍需理解安装/导出与 Config 目标模型。比较不能只停在执行 clang++ 的语法；本批也不编译 Zig/Rust 构建示例，保留概念对照而非工具能力排名。

<a id="g9-section-18"></a>

## 18. 完整实验：安装消费与生成依赖

这些实验由正文提取到新临时目录，完整文件是唯一维护来源。执行器只运行已审阅的本地代码，不是安全沙箱；不修改历史 PDF、FM 或出版系统。

```sh
python3 c++/learning/verify_native.py /usr/bin/clang++ /opt/homebrew/opt/llvm/bin/clang++
```

### 18.1 G9-P1 · 静态依赖、安装导出与迁移消费者

**待验证命题。** 生产者静态库 PRIVATE 依赖 helper，公开传播头文件与 C++23 模式。安装后迁移前缀、隐藏原生产者源码和构建树，再以独立 find_package 消费。错误主版本须在配置阶段被拒绝。

**范围与前提。** 同机静态库包，不是共享库 RPATH 测试，不是 hermetic 或逐字节可复现证明。SameMajorVersion 是声明的版本接受策略，不是自动 ABI 判断。实验不访问注册表或下载第三方依赖。

<!-- n-lab {"id":"G9-P1","mode":"package"} -->

[完整实验 · G9-P1 · producer/CMakeLists.txt]

<!-- n-file {"path":"producer/CMakeLists.txt"} -->
```cmake
cmake_minimum_required(VERSION 3.28)
project(HandbookNative VERSION 1.2.0 LANGUAGES CXX)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(CTest)
add_library(native_helper STATIC helper.cpp)
add_library(native_core STATIC core.cpp)
add_library(HandbookNative::core ALIAS native_core)
set_target_properties(native_core PROPERTIES EXPORT_NAME core CXX_EXTENSIONS NO)
target_sources(native_core PUBLIC FILE_SET HEADERS
    BASE_DIRS include FILES include/handbook/core.hpp)
target_compile_features(native_core PUBLIC cxx_std_23)
target_compile_definitions(native_helper INTERFACE HELPER_PRIVATE=1)
target_link_libraries(native_core PRIVATE native_helper)
target_compile_options(native_core PRIVATE
    "$<$<CXX_COMPILER_ID:Clang,AppleClang,GNU>:-Wall;-Wextra>")
if(BUILD_TESTING)
    add_executable(native_test test.cpp)
    target_link_libraries(native_test PRIVATE HandbookNative::core)
    add_test(NAME native.value COMMAND native_test)
endif()
install(TARGETS native_core native_helper EXPORT HandbookNativeTargets
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    FILE_SET HEADERS DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(EXPORT HandbookNativeTargets NAMESPACE HandbookNative::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HandbookNative)
configure_package_config_file(HandbookNativeConfig.cmake.in
    ${CMAKE_CURRENT_BINARY_DIR}/HandbookNativeConfig.cmake
    INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HandbookNative)
write_basic_package_version_file(
    ${CMAKE_CURRENT_BINARY_DIR}/HandbookNativeConfigVersion.cmake
    VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/HandbookNativeConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/HandbookNativeConfigVersion.cmake
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/HandbookNative)
```

[完整实验 · G9-P1 · producer/HandbookNativeConfig.cmake.in]

<!-- n-file {"path":"producer/HandbookNativeConfig.cmake.in"} -->
```cmake
@PACKAGE_INIT@
include("${CMAKE_CURRENT_LIST_DIR}/HandbookNativeTargets.cmake")
check_required_components(HandbookNative)
```

[完整实验 · G9-P1 · producer/include/handbook/core.hpp]

<!-- n-file {"path":"producer/include/handbook/core.hpp"} -->
```cpp
#pragma once
#include <expected>
namespace handbook { std::expected<int, int> answer(); }
```

[完整实验 · G9-P1 · producer/helper.cpp]

<!-- n-file {"path":"producer/helper.cpp"} -->
```cpp
int helper_answer() { return 42; }
```

[完整实验 · G9-P1 · producer/core.cpp]

<!-- n-file {"path":"producer/core.cpp"} -->
```cpp
#include <handbook/core.hpp>
#ifndef HELPER_PRIVATE
#error "private helper requirements missing from producer"
#endif
int helper_answer();
std::expected<int, int> handbook::answer() { return helper_answer(); }
```

[完整实验 · G9-P1 · producer/test.cpp]

<!-- n-file {"path":"producer/test.cpp"} -->
```cpp
#include <handbook/core.hpp>
#ifdef HELPER_PRIVATE
#error "private helper compile requirement leaked to consumer"
#endif
int main() {
    const auto result = handbook::answer();
    return result && *result == 42 ? 0 : 1;
}
```

[完整实验 · G9-P1 · consumer/CMakeLists.txt]

<!-- n-file {"path":"consumer/CMakeLists.txt"} -->
```cmake
cmake_minimum_required(VERSION 3.28)
project(IndependentConsumer LANGUAGES CXX)
include(CTest)
set(REQUESTED_VERSION 1 CACHE STRING "Requested package version")
find_package(HandbookNative ${REQUESTED_VERSION} CONFIG REQUIRED)
add_executable(consume main.cpp)
target_link_libraries(consume PRIVATE HandbookNative::core)
add_test(NAME consumer.value COMMAND consume)
```

[完整实验 · G9-P1 · consumer/main.cpp]

<!-- n-file {"path":"consumer/main.cpp"} -->
```cpp
#include <handbook/core.hpp>
#ifdef HELPER_PRIVATE
#error "private helper compile requirement leaked to installed consumer"
#endif
int main() {
    const auto value = handbook::answer();
    return value && *value == 42 ? 0 : 1;
}
```

**运行与解释。** 本节开头的统一命令按 `G9-P1` 提取全部文件；具体编译、链接、运行及负例命令保存在 `results.json`。先预测结果，再用完整诊断核对，不能把任意构建失败或超时当作预期反例。

### 18.2 G9-P2 · 预设与代码生成依赖的失效检查

**待验证命题。** 通过 dev preset 配置、构建和测试；修改值文件后，不重新 configure，build 必须重新生成并编译。故意漏掉输入 DEPENDS 的错误变体编译成功，但旧值必须被观察判据拒绝。

**范围与前提。** 只检查此生成图的数据依赖与可见结果。没有用耗时阈值证明增量构建快，也没有启用 PCH、Unity、LTO、模块、交叉编译或 sanitizer。

<!-- n-lab {"id":"G9-P2","mode":"codegen"} -->

[完整实验 · G9-P2 · CMakeLists.txt]

<!-- n-file {"path":"CMakeLists.txt"} -->
```cmake
cmake_minimum_required(VERSION 3.28)
project(GeneratedValue LANGUAGES CXX)
include(CTest)
set(generated "${CMAKE_CURRENT_BINARY_DIR}/generated.hpp")
add_custom_command(OUTPUT "${generated}"
    COMMAND "${CMAKE_COMMAND}"
        "-DINPUT=${CMAKE_CURRENT_SOURCE_DIR}/value.txt"
        "-DOUTPUT=${generated}"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/generate.cmake"
    DEPENDS value.txt generate.cmake
    VERBATIM)
add_executable(generated_value main.cpp "${generated}")
target_include_directories(generated_value PRIVATE "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_features(generated_value PRIVATE cxx_std_23)
add_test(NAME generated.initial COMMAND generated_value 7)
```

[完整实验 · G9-P2 · generate.cmake]

<!-- n-file {"path":"generate.cmake"} -->
```cmake
file(READ "${INPUT}" value)
string(STRIP "${value}" value)
if(NOT value MATCHES "^[0-9]+$")
    message(FATAL_ERROR "expected nonnegative integer")
endif()
file(WRITE "${OUTPUT}" "#pragma once\ninline constexpr int generated_value = ${value};\n")
```

[完整实验 · G9-P2 · value.txt]

<!-- n-file {"path":"value.txt"} -->
```text
7
```

[完整实验 · G9-P2 · main.cpp]

<!-- n-file {"path":"main.cpp"} -->
```cpp
#include "generated.hpp"
#include <charconv>
#include <cstring>
#include <iostream>
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    int expected = 0;
    const auto end = argv[1] + std::strlen(argv[1]);
    const auto parsed = std::from_chars(argv[1], end, expected);
    if (parsed.ec != std::errc{} || parsed.ptr != end) return 3;
    std::cout << generated_value << '\n';
    return generated_value == expected ? 0 : 4;
}
```

[完整实验 · G9-P2 · CMakePresets.json]

<!-- n-file {"path":"CMakePresets.json"} -->
```json
{
  "version": 6,
  "configurePresets": [
    {
      "name": "dev",
      "generator": "Ninja",
      "binaryDir": "${sourceDir}/build/dev",
      "cacheVariables": {
        "CMAKE_BUILD_TYPE": "Debug",
        "CMAKE_EXPORT_COMPILE_COMMANDS": true
      }
    }
  ],
  "buildPresets": [
    {
      "name": "dev",
      "configurePreset": "dev"
    }
  ],
  "testPresets": [
    {
      "name": "dev",
      "configurePreset": "dev",
      "output": {
        "outputOnFailure": true
      }
    }
  ]
}
```

**运行与解释。** 本节开头的统一命令按 `G9-P2` 提取全部文件；具体编译、链接、运行及负例命令保存在 `results.json`。先预测结果，再用完整诊断核对，不能把任意构建失败或超时当作预期反例。

**未执行路线。** 前面列出的扩展练习仍可用于学习，但不自动计入本批通过项。执行记录按文档检查、编译/链接/消费、性能观察、并发检测分别说明；后两类在本批不运行。


<a id="g9-section-19"></a>

## 19. 构建复核协议

面对一个 C++ build system，按这个顺序审查。

| Layer                 | 关键问题                                                |
| --------------------- | ------------------------------------------------------- |
| Target Graph          | 实际 artifacts 是什么？                                 |
| Dependencies          | 每条 edge 为什么存在？                                  |
| Usage Requirements    | PUBLIC / PRIVATE / INTERFACE 是否与 C++ API 一致？      |
| Toolchain             | compiler / target platform 从哪里定义？                 |
| Profiles              | dev/san/release 是否清晰分开？                          |
| Dependency Resolution | package 来源是否明确？                                  |
| Reproducibility       | versions/toolchains 是否可追踪？                        |
| Generated Code        | inputs/outputs/dependencies 是否进入 graph？            |
| Tests                 | 是否测试真实 targets 与 install tree？                  |
| Install               | artifact/header layout 是否正确？                       |
| Export                | external consumer 能否只通过 namespaced target 使用？   |
| ABI                   | symbol visibility/shared/static policy 是否与 G8 一致？ |
| Cross Compile         | host/target artifacts 是否分离？                        |
| DX                    | clangd/compile database/incremental build 是否健康？    |
| Performance           | build optimizations是否基于真实数据？                   |

<a id="g9-section-20"></a>

## 20. Final Gate

完成 G9 后，应能闭卷回答：

### 20.1 Build Model

1. CMake、Ninja、Clang 分别做什么？
2. 什么是 artifact graph？
3. Source/Build/Install Tree 为什么必须区分？

### 20.2 Targets

1. Target 为什么是 modern CMake 核心？
2. Target property 与 usage requirement 区别是什么？
3. Interface Library 为什么可以没有 binary artifact？

### 20.3 Scopes

1. `PRIVATE` 的准确含义是什么？
2. `PUBLIC` 为什么等于 implementation + interface requirement？
3. `INTERFACE` 什么场景最自然？
4. 如何从 public C++ header 推导 dependency scope？

### 20.4 Language

1. 为什么 `cxx_std_23` 比裸 `-std=c++23` 更好？
2. public header 使用 C++23 feature 时为什么 standard requirement可能需要传播？

### 20.5 Configuration

1. Preset 与 Toolchain File 区别是什么？
2. Single-config 与 Multi-config generator 有什么区别？
3. 为什么不应该到处依赖 `CMAKE_BUILD_TYPE`？

### 20.6 Dependencies

1. Module-mode `find_package()` 与 Config-mode 区别？
2. Imported Target 为什么比 `FOO_LIBRARIES` 更成熟？
3. FetchContent 为什么不是 package manager？
4. Conan/vcpkg 为什么最好不要污染 project target logic？

### 20.7 Packaging

1. Build成功为什么不代表 library package正确？
2. `install(EXPORT ...)` 解决什么？
3. `<Package>Config.cmake` 有什么作用？
4. 为什么 installed package 必须 relocatable？
5. `find_dependency()` 为什么对 PUBLIC dependency重要？

### 20.8 Advanced Build

1. PCH优化的是什么？
2. Unity Build 的风险是什么？
3. LTO为什么是跨 TU optimization？
4. Modules 为什么要求 build-system dependency scanning？

### 20.9 Tooling

1. 为什么 clangd 要依赖 `compile_commands.json`？
2. 为什么 sanitizer/coverage应该独立 profile？
3. 为什么 benchmark 不应该基于 Debug/ASan build？

### 20.10 Cross Compilation

1. 什么是 Host Tool 与 Target Artifact？
2. `try_run()` 为什么在 cross build中危险？
3. Toolchain file 为什么必须很早读取？

### 20.11 Architecture

1. 为什么 CMakeLists越长越复杂并不意味着工程越成熟？
2. Modern CMake 的最终目标是什么？

<a id="g9-section-21"></a>

## 21. Final Gate · 参考答案与常见误判

### 21.1 Build Model

1. CMake 配置并生成构建描述，Ninja 执行依赖图，Clang 驱动编译/链接工具。阶段出错应分别检查配置发现、编译语义、链接符号和运行加载。

2. 产物图连接输入、派生产物及依赖；target 还携带使用要求。静态库依赖边不表示把依赖库字节塞进自己的 archive。

3. 源码树是维护入口，构建树是配置相关派生状态，安装树是消费者视图。G9-P1 隐藏前两者仍成功，才对后者独立消费提供证据。

### 21.2 Targets

1. Target 把源码成员、产物、编译配置和依赖关系放在有归属的对象上，减少全局隐式状态。

2. 自身属性参与本目标构建；INTERFACE 属性描述消费者需要什么。PUBLIC 同时设置两侧，不表示“库已经公开发布”。

3. 接口库可只承载使用要求而没有普通库二进制。若含文件集或自定义生成关系，仍可能参与构建图；没有 archive 不等于没有语义。

### 21.3 Scopes

1. PRIVATE 给自身使用，不把编译使用要求作为普通公开接口；静态目标仍可能向最终链接保留依赖。G9-P1 的 helper 宏对 core 可见、对消费者不可见，但 helper 符号必须参与最终链接。

2. PUBLIC 同时描述自身和消费侧要求。3. INTERFACE 只描述消费者要求，适合纯头文件接口或共享的接口策略。

4. 先独立编译公开头文件：它需要哪些类型、宏和头文件？再看库的未解析符号需要什么。仅据 `.cpp` 使用就断言安装包无此依赖，会遗漏静态链接边。

### 21.4 Language

1. cxx_std_23 让 CMake 选择编译器对应的标准模式参数，而不是把某家编译器选项写死。它只声明模式下限，不能保证标准库所有 C++23 组件齐全。

2. 消费者要编译公开头文件，所以语言和库要求也属于接口。G9-P1 用 expected 真实编译消费端；未据此宣称全部 C++23 实现已验证。

### 21.5 Configuration

1. Preset 描述项目如何配置/构建/测试，toolchain 描述编译器、目标平台和 sysroot；它们可引用彼此但职责不同。

2. 单配置生成器通常每个构建树选一个 CMAKE_BUILD_TYPE，多配置生成器在构建等阶段选配置。3. 因而硬编码 if(CMAKE_BUILD_TYPE STREQUAL Debug) 不能覆盖多配置行为；采用恰当的配置表达式和命令参数。

G9-P2 只运行 Ninja 单配置 dev preset，不把示例中的 san/release 建议算成实际执行。

### 21.6 Dependencies

1. Module 模式寻找 FindFoo.cmake，常依赖外部查找逻辑；Config 模式由包提供导入信息。两者都不是版本锁定策略。

2. 导入目标还能携带头文件、定义和传递依赖，不仅是一个路径列表。3. FetchContent 负责获取/接入源码，不自动提供完整二进制包管理。

4. Conan/vcpkg 应尽量在包获取与工具链层工作，使核心 target 逻辑仍通过 find_package 消费。常见误判是以为“使用了包管理器”就自动得到 hermetic 或逐字节复现。

### 21.7 Packaging

1. 本仓库构建可能靠源码 include、缓存、全局路径或已有依赖偶然成功；安装缺头文件、缺目标和硬编码路径要由独立消费者发现。

2. install(EXPORT) 生成安装后的目标描述。3. Config 负责加载目标、准备依赖和处理组件；Version 文件采用声明的版本接受策略。

4. 可迁移包尽量相对安装前缀定位自身；具体交付也可有明确固定路径策略，不能隐含开发机位置。5. PUBLIC 依赖通常要 find_dependency；静态 PRIVATE 链接依赖同样可能需要，不能只检查公开头文件。

G9-P1 验证同机静态包迁移及错误主版本拒绝，没有验证动态库加载路径、签名、发布事务或所有消费者配置。

### 21.8 Advanced Build

1. PCH 复用稳定头文件的解析产物，不能替代显式 include。2. Unity 合并翻译单元可能引入匿名命名空间、宏和静态名称碰撞；正常非 Unity 构建仍须成立。

3. LTO 让链接阶段看到更多跨翻译单元中间信息，效果和成本需测量。4. 模块导入先后及编译模块产物依赖必须进入构建图，改后缀不能完成迁移。本批没有执行上述优化或模块实验。

### 21.9 Tooling

1. clangd 需要实际编译命令的头文件路径、宏和模式；数据库过期或缺生成头文件会使编辑器诊断偏离真实构建。

2. Sanitizer/coverage 改变插桩与运行环境，应有独立配置和证据类别。3. Debug/ASan 不代表生产代码生成及时间成本，不能据其微基准得出发布性能结论。G9-P2 的命令日志与编译数据库是构建证据，不是性能测试。

### 21.10 Cross Compilation

1. 代码生成器运行于构建机，目标库运行于目标平台；必须区分两类工具和依赖。2. try_run 需要执行目标程序，交叉构建可能只能通过模拟器或预填结果解决，不能静默用宿主结果代替。

3. toolchain 必须在编译器识别与特性探测前影响目标环境。仅换编译器路径而继续使用宿主头文件/库，是典型的混合配置错误。本批交叉编译为 NOT RUN。

### 21.11 Architecture

1. 构建成熟度来自依赖和支持矩阵清楚，而非函数、宏与选项数量。每个新增选项都增加需要支持的配置集合。

2. 目标是准确表达产物、依赖和使用要求，让工具执行可检查的构建/交付流程。G9-P2 故意漏掉输入 DEPENDS 后仍能“构建成功”，但消费者看到旧值；因此成功退出并不等于依赖图正确。

<a id="g9-section-22"></a>

## 22. 工程原则与全链回查

如果半年以后只保留十五条：

1. Build system 的核心是 Artifact Dependency Graph，而不是 shell command 集合。

2. Modern CMake 的核心 abstraction 是 Target：artifact + build properties + transitive usage requirements。

3. `PRIVATE / PUBLIC / INTERFACE` 应从 C++ source interface dependency 推导，而不是靠经验背诵。

4. Build requirement 应附着到最窄的 owning target，避免 global include paths、flags 和 linker state。

5. Source Tree、Build Tree、Install Tree 是不同 representations；一个库必须测试真正的 install-consumer path。

6. Preset 描述项目支持的 build workflow，Toolchain 描述 compiler/target environment；两者不能混。

7. Dependency package 应尽量以 Imported Target 的形式进入 CMake graph，而不是裸路径和全局变量。

8. CMake、Conan/vcpkg、Ninja 分别解决 build graph、package resolution、build execution 等不同问题，不应混为一层。

9. 一个可发布 library 的完成条件不仅是 build 成功，而是 install/export/config/version/consumer 全链路成立。

10. Generated code 也必须成为 build graph 中具有明确 input/output/dependency 的 artifact。

11. C++ Modules 需要 build system参与 dependency scanning；语言 feature availability 不等于整个 compiler/stdlib/build stack 都已成熟。

12. PCH、Unity、LTO 都是特定阶段的 optimization，不是“现代 C++ 必开选项”。

13. Cross compilation 是 Host Universe 与 Target Universe 的分离，不只是换 compiler path。

14. Developer tooling 应消费真实 build truth：clangd 来自 compile database，测试来自真实 targets，package tests来自 install tree。

15. 优秀 CMake 的目标不是展示 CMake 技巧，而是用最少的隐式状态准确表达 C++ artifact architecture。

一条 `target_link_libraries(app PUBLIC decoder)` 不只是链接语法：先检查源码接口，再追到使用要求、安装包依赖、ABI 配置和消费者工具链。构建描述是架构的可执行表达；不是 CMake 越复杂，工程就越成熟。下一章 [G10 §10](g10-systems-runtime-project.md#g10-section-10)直接复用安装消费模型，将本章的交付合同与 G7 的关闭协议组合，不重新讲一遍 CMake 入门。

<a id="g9-section-23"></a>

## 23. 参考资料与验证边界

CMake 规则引用固定的 4.4 文档线：[构建模型](https://cmake.org/cmake/help/v4.4/manual/cmake-buildsystem.7.html)、[链接传播](https://cmake.org/cmake/help/v4.4/command/target_link_libraries.html)、[生成器表达式](https://cmake.org/cmake/help/v4.4/manual/cmake-generator-expressions.7.html)、[包配置](https://cmake.org/cmake/help/v4.4/module/CMakePackageConfigHelpers.html)、[生成命令](https://cmake.org/cmake/help/v4.4/command/add_custom_command.html)、[预设](https://cmake.org/cmake/help/v4.4/manual/cmake-presets.7.html) 和 [模块支持](https://cmake.org/cmake/help/v4.4/manual/cmake-cxxmodules.7.html)。工具版本和源码摘要以本批记录为准，不使用“最新稳定版”作为永久事实。

包管理器为范围说明，参见 [Conan](https://docs.conan.io/2/reference/tools/cmake/cmakeconfigdeps.html) 与 [vcpkg manifest](https://learn.microsoft.com/en-us/vcpkg/concepts/manifest-mode)。本批不运行包管理器，不验证其缓存或依赖复现性。

[历史验证与限制](learning/native-revision.md)仍保留编译、链接与消费的定向范围。当前编辑修订及源码字节对应见[全书一致性记录](learning/editorial-sweep.md)，不将旧结果冒充重跑。
