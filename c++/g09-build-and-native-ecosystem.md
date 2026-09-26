# C++ Systems Track · G9 Build & Native Ecosystem

**Version:** 1.0  
**Status:** Complete / Frozen Review Baseline  
**Language Baseline:** C++23  
**Tooling Baseline:** Modern CMake 4.x / Clang / Ninja / CTest / clangd / clang-tidy / Sanitizers  
**Prerequisites:** G0–G8  
**Scope:** Build Graph / Targets / Usage Requirements / CMake / Presets / Toolchains / Dependency Discovery / Package Managers / Install & Export / C++ Modules / PCH / Unity / LTO / Sanitizers / Testing / Cross Compilation / Packaging / Developer Tooling  
**Purpose:** 建立从 **C++ source tree** 到 **可重复、可安装、可消费、可发布的 native artifacts** 的完整工程模型。

截至当前官方文档，CMake 的最新稳定文档线为 **4.4.x**；本章采用当前 modern target-based CMake 模型，而不是历史上的全局 flag / directory-based CMake 写法。:chatgpt-content-reference{index="0"}

---

# 0. G9 的定位

到 G8 为止，我们已经知道：

```text
source
  ↓
translation unit
  ↓
compiler
  ↓
object file
  ↓
linker
  ↓
library / executable
  ↓
loader
```

但真实工程中，不可能手工维护：

```bash
clang++ -I... -D... -c a.cpp
clang++ -I... -D... -c b.cpp
ar ...
clang++ ...
```

尤其当系统出现：

```text
多个 library
多个 executable
测试
代码生成
第三方依赖
不同 OS
不同 CPU
Debug / ASan / Release
安装
打包
交叉编译
```

以后。

G9 要解决的是：

> **怎样把我们已经学会的 compilation/link/artifact relationships，转化为一张可维护、可移植、可复现的 Build Graph。**

---

# 1. 最重要的认知：CMake 不是 Compiler

CMake 不是：

```text
compiler
linker
package manager
test framework
```

它更接近：

> **Build-system generator + build-graph configuration system**

例如：

```text
CMake
  ↓ generate
Ninja build graph
  ↓ execute
Clang compiler/linker
  ↓
binary artifacts
```

所以：

```text
CMakeLists.txt
```

不是直接：

> “告诉 CPU 怎么构建”。

而是在描述：

```text
Targets
Dependencies
Properties
Usage Requirements
Install Rules
```

CMake 再把这些信息映射给：

```text
Ninja
Make
Visual Studio
Xcode
...
```

等 generator/backend。

---

# 2. Build System 的本质是 Artifact Graph

假设：

```text
core.cpp
decoder.cpp
main.cpp
```

真正关系：

```text
core.cpp
   │
   ▼
core.o
   │
   ├───────────┐
   ▼           │
libcore.a      │
   │           │
decoder.cpp    │
   │           │
   ▼           │
decoder.o      │
   │           │
   └─────┬─────┘
         ▼
    libdecoder.a
         │
main.cpp │
   │     │
   ▼     │
main.o   │
   └──┬──┘
      ▼
   executable
```

因此 Build System 真正管理：

```text
Nodes
=
artifacts

Edges
=
dependencies
```

这就是 G0 的：

> Build System = Artifact Graph

正式工程化。

---

# Part I · Source Tree / Build Tree / Install Tree

# 3. 三棵树必须严格分开

现代 CMake 工程最好形成：

```text
Source Tree
Build Tree
Install Tree
```

三层。

---

# 4. Source Tree

例如：

```text
project/
├── CMakeLists.txt
├── cmake/
├── include/
├── src/
├── tests/
└── examples/
```

Source tree 是：

> version-controlled source of truth。

不应该被 compiler outputs 污染。

---

# 5. Build Tree

例如：

```text
build/
├── CMakeCache.txt
├── CMakeFiles/
├── compile_commands.json
├── src/
├── tests/
└── artifacts...
```

这是：

> derived state。

应当可以：

```bash
rm -rf build
```

然后完整重新生成。

这叫：

> **Out-of-source Build**

应该作为默认。

---

# 6. Install Tree

例如：

```text
prefix/
├── bin/
├── lib/
├── include/
└── lib/cmake/MyLib/
```

这是：

> 另一个项目真正消费你时看到的 representation。

非常重要：

```text
Build Tree
≠
Install Tree
```

一个库：

> 在当前 repo 能编译，

并不意味着：

> install 后真的能被另一个项目正确 `find_package()`。

---

# 7. 一个成熟 Library 必须测试 Install Tree

典型闭环：

```text
configure
↓
build
↓
test
↓
install to temporary prefix
↓
configure separate consumer
↓
find_package(MyLib)
↓
link MyLib::MyLib
↓
run
```

这才能证明：

> package 本身可消费。

---

# Part II · Target：Modern CMake 的核心对象

# 8. 不要把 CMake 理解成“设置一堆变量”

Modern CMake 的核心是：

> **Target**

例如：

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

这里最重要的是：

```text
vehicle_core
vehicle_app
```

是 graph nodes。

---

# 9. Target 携带 Properties

例如一个 target 可以拥有：

```text
sources
include directories
compile features
compile definitions
compile options
link dependencies
link options
visibility
PIC
module sets
header sets
```

因此应该理解：

```text
Target
=
Artifact
+
Build Requirements
+
Usage Requirements
```

---

# 10. 为什么 Target Model 强？

假设：

```text
app
↓
decoder
↓
fmt
```

如果 decoder public header 本身使用 fmt：

```cpp
#include <fmt/format.h>
```

那么：

> app 也需要能够找到 fmt headers。

现代 CMake 可以沿 target dependency graph 自动传播这个 requirement。

官方文档也明确指出，`target_link_libraries()` 不只是“调用 linker”，而是在描述 target relationships 和 usage requirements。:chatgpt-content-reference{index="1"}

---

# Part III · `PRIVATE / PUBLIC / INTERFACE`

这是 Modern CMake 最重要的三个词。

---

# 11. `PRIVATE`

```cmake
target_link_libraries(foo
    PRIVATE
        bar
)
```

表示：

```text
foo itself needs bar

but

foo's consumers
do not inherit bar as a usage requirement
```

可以理解：

```text
implementation dependency
```

---

# 12. `PUBLIC`

```cmake
target_link_libraries(foo
    PUBLIC
        bar
)
```

表示：

```text
foo needs bar

AND

foo consumers also need bar
```

即：

```text
implementation requirement
+
interface requirement
```

---

# 13. `INTERFACE`

```cmake
target_link_libraries(foo
    INTERFACE
        bar
)
```

表示：

```text
foo itself does not consume bar

but

consumers of foo need bar
```

最常见：

> header-only abstraction。

官方文档把这三者直接定义为 target property/usage-requirement 的传播规则。:chatgpt-content-reference{index="2"}

---

# 14. 最准确的判断方法

不要问：

> “这是 public dependency 还是 private dependency？”

先问 C++：

> **我的 public interface 是否要求 consumer 理解这个 dependency？**

例如：

```cpp
// foo.hpp
#include <bar/type.hpp>

class Foo {
public:
    bar::Type value() const;
};
```

那么：

```text
bar
```

泄漏进 Foo source interface。

通常：

```cmake
target_link_libraries(foo
    PUBLIC
        bar::bar
)
```

---

# 15. 如果只在 `.cpp` 使用

```cpp
// foo.cpp
#include <bar/bar.hpp>
```

Public header完全不知道 Bar。

那么：

```cmake
target_link_libraries(foo
    PRIVATE
        bar::bar
)
```

更合理。

所以：

> **PUBLIC / PRIVATE / INTERFACE 是 source abstraction boundary 在 build graph 中的投影。**

---

# Part IV · Target-scoped Configuration

# 16. Avoid Global Include Directories

历史式：

```cmake
include_directories(
    include
    third_party/foo/include
)
```

把 include path 隐式施加给：

```text
当前目录
+
子目录中大量 targets
```

依赖关系变得模糊。

优先：

```cmake
target_include_directories(core
    PUBLIC
        ...
)
```

---

# 17. Avoid Global Compile Flags

历史：

```cmake
set(CMAKE_CXX_FLAGS
    "${CMAKE_CXX_FLAGS} -Wall -Wextra")
```

问题：

```text
字符串拼接
跨 compiler 差异
污染所有 targets
不表达 usage relationship
难以组合
```

现代：

```cmake
target_compile_options(core
    PRIVATE
        ...
)
```

---

# 18. Avoid `link_directories()`

不要：

```cmake
link_directories(/some/path)
target_link_libraries(app foo)
```

让 linker靠名字搜索。

优先：

```text
Imported Target
or
real CMake Target
```

例如：

```cmake
find_package(Foo CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        Foo::Foo
)
```

---

# 19. 核心原则

> **Every build requirement should attach to the narrowest target that actually owns that requirement.**

这就是 target-based CMake 的纪律。

---

# Part V · Library Target Types

# 20. `STATIC`

```cmake
add_library(core STATIC ...)
```

生成：

```text
.a
.lib
```

archive。

---

# 21. `SHARED`

```cmake
add_library(core SHARED ...)
```

生成：

```text
.so
.dylib
.dll
```

对应动态 library。

---

# 22. `MODULE`

```cmake
add_library(plugin MODULE ...)
```

更接近：

> 动态加载 plugin，

而不是正常作为 dependent target 链接使用的 shared library。

---

# 23. `OBJECT`

```cmake
add_library(core_objects OBJECT
    a.cpp
    b.cpp
)
```

生成：

```text
a.o
b.o
```

但不先 archive/link成普通 library。

适合非常特定：

```text
reuse same compiled objects
special artifact composition
```

场景。

不要把它作为普通 library 默认。

---

# 24. `INTERFACE`

```cmake
add_library(project_options INTERFACE)
```

不生成真正 library artifact。

它代表：

> 一组 Usage Requirements。

官方 current CMake 文档明确规定 interface library 可以携带 `INTERFACE_*` properties、headers 和 install/export metadata，而无需生成 library artifact。:chatgpt-content-reference{index="3"}

---

# 25. Alias Target

```cmake
add_library(MyProject::core
    ALIAS
    core
)
```

非常适合让 build-tree usage 与 installed package usage 接近：

```text
MyProject::core
```

名字具有：

```text
namespace-like
```

语义。

---

# Part VI · Compile Features

# 26. 不要把 C++ Standard 当裸 Flag

不推荐：

```cmake
target_compile_options(core
    PRIVATE
        -std=c++23
)
```

因为：

```text
GNU/Clang/MSVC flags differ
```

优先：

```cmake
target_compile_features(core
    PUBLIC
        cxx_std_23
)
```

或者 target properties：

```cmake
set_target_properties(core PROPERTIES
    CXX_STANDARD 23
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)
```

---

# 27. 为什么 `cxx_std_23` 可以是 `PUBLIC`？

如果 public headers 使用：

```cpp
std::expected
std::mdspan
concepts
```

consumer 编译这些 headers 也必须使用：

> C++23-capable mode。

因此：

```cmake
target_compile_features(core
    PUBLIC
        cxx_std_23
)
```

是一个真正 Usage Requirement。

---

# 28. `CXX_EXTENSIONS NO`

建议明确：

```cmake
CXX_EXTENSIONS NO
```

意味着倾向：

```text
-std=c++23
```

而不是 GNU-style：

```text
-std=gnu++23
```

让项目更靠近标准语言。

除非项目明确依赖 compiler extensions。

---

# Part VII · Header Sets

# 29. Header 不只是“手工 install 一个目录”

现代 CMake支持：

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

这样 headers：

```text
belong to target
```

而不是：

```text
CMake完全不知道的一堆文件
```

Current CMake 的 header file sets 可以随 target 一起 install/export。:chatgpt-content-reference{index="4"}

---

# 30. 为什么 File Set 更好？

它知道：

```text
public header membership
base directory
installation relationship
IDE visibility
export relationship
```

比：

```cmake
install(DIRECTORY include/ ...)
```

语义更强。

---

# Part VIII · Generator Expressions

# 31. `$<...>`

CMake 有一套：

> **Generator Expressions**

例如：

```cmake
target_compile_options(core
    PRIVATE
        $<$<CXX_COMPILER_ID:Clang>:
            -Wall
            -Wextra
        >
)
```

它们不是普通 configure-time variable。

通常在：

> generate/build configuration context

中求值。

---

# 32. Build Interface / Install Interface

非常重要：

```cmake
target_include_directories(core
    PUBLIC
        $<BUILD_INTERFACE:
            ${CMAKE_CURRENT_SOURCE_DIR}/include
        >
        $<INSTALL_INTERFACE:
            ${CMAKE_INSTALL_INCLUDEDIR}
        >
)
```

Build tree：

```text
repo/include
```

Install tree：

```text
prefix/include
```

使用不同路径。

这正是：

> Build Tree ≠ Install Tree

在 target interface上的表达。

---

# 33. Generator Expressions 不要过度使用

如果 CMakeLists充满：

```text
$<$<AND:$<BOOL:...>,...>:...>
```

会迅速变成另一种编程语言迷宫。

原则：

> generator expression 用于真正依赖 configuration/generator/target context 的条件，而不是取代正常 CMake structure。

---

# Part IX · Configure / Generate / Build

# 34. CMake 有多个阶段

典型：

```bash
cmake --preset dev
```

执行：

```text
Configure
↓
Generate
```

得到 backend graph。

然后：

```bash
cmake --build --preset dev
```

让 backend：

```text
Ninja
```

真正执行 compile/link。

---

# 35. Configure

主要处理：

```text
CMake language
project options
find_package
feature detection
target graph
cache
```

---

# 36. Generate

把 target graph 转换为：

```text
Ninja files
Makefiles
Xcode projects
Visual Studio projects
```

---

# 37. Build

实际：

```text
compiler
assembler
archiver
linker
custom commands
```

开始执行。

---

# 38. 为什么理解阶段很重要？

如果：

```text
find_package fails
```

这是：

> configure-time problem。

如果：

```text
undefined symbol
```

通常：

> build/link problem。

如果：

```text
shared library not found at runtime
```

则已经进入：

> loader/runtime problem。

G0 的 error-phase model在这里继续成立。

---

# Part X · Generators

# 39. Ninja

对于 command-line / Clang workflow：

```text
Ninja
```

通常是非常优秀的默认：

```text
fast
simple
parallel
widely supported
compile_commands friendly
```

CMake负责：

```text
generate Ninja graph
```

Ninja负责：

```text
execute it
```

---

# 40. IDE Generators

也可以：

```text
Xcode
Visual Studio
```

它们通常属于：

> multi-configuration generators。

理解这个区别非常重要。

---

# Part XI · Single-config vs Multi-config

# 41. Single-config

例如典型：

```text
Ninja
Unix Makefiles
```

一个 build tree 通常对应一个：

```text
Debug
Release
RelWithDebInfo
...
```

configuration。

常通过：

```text
CMAKE_BUILD_TYPE
```

选择。

---

# 42. Multi-config

例如：

```text
Visual Studio
Xcode
Ninja Multi-Config
```

同一个 generated build tree 可以拥有：

```text
Debug
Release
...
```

多个 configuration。

因此不能在 CMake project里到处假设：

```cmake
if(CMAKE_BUILD_TYPE STREQUAL "Debug")
```

能覆盖所有 generators。

---

# 43. 更成熟的方法

优先：

```text
target properties
generator expressions
presets
```

描述 config-specific requirements。

例如：

```cmake
target_compile_definitions(core
    PRIVATE
        $<$<CONFIG:Debug>:
            PROJECT_DEBUG_BUILD=1
        >
)
```

---

# Part XII · CMake Presets

# 44. Presets 解决什么？

以前 README：

```bash
cmake -S . -B build \
  -GNinja \
  -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_CXX_COMPILER=clang++ \
  -D...
```

每个人复制不同 command。

Presets 把：

> supported configure/build/test workflows

变成 version-controlled configuration。

Current CMake presets schema覆盖 configure、build、test、package 和 workflow presets。:chatgpt-content-reference{index="5"}

---

# 45. `CMakePresets.json`

应该：

> 提交进 Git。

表示：

```text
Project-supported build configurations
```

例如：

```json
{
  "version": 10,
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
  ]
}
```

具体 schema version 应根据你要求的最低 CMake 版本选择，

不要机械复制当前最大版本。

---

# 46. `CMakeUserPresets.json`

用于：

```text
developer-local paths
local toolchains
machine-specific configuration
```

通常：

> 不作为团队共享项目配置。

这正好区分：

```text
project policy
vs
local environment
```

---

# 47. 推荐的 Preset 语义

例如：

```text
dev
san
release
```

而不是：

```text
elliott-macbook-debug
company-laptop2
```

共享 presets描述：

> 用途。

个人 machine差异放：

```text
UserPresets / toolchain / environment
```

---

# 48. Dev Profile

目标：

```text
fast incremental build
debug information
warnings
clangd
tests
```

不是：

> “所有可能 instrumentation 全开”。

---

# 49. Sanitizer Profile

例如：

```text
ASan
UBSan
```

强调：

> correctness diagnostics。

不要作为性能测量 baseline。

---

# 50. Release Profile

目标：

```text
optimization
NDEBUG where appropriate
production-like codegen
possibly IPO/LTO
```

但仍应考虑：

> symbols / profiling ability。

高质量 production binary不一定意味着：

> 完全没有 debug symbols。

---

# Part XIII · Toolchain File

# 51. Toolchain File 解决什么？

> **What toolchain / target platform are we building for?**

典型：

```text
compiler
sysroot
target architecture
platform
cross-compilation environment
```

`CMAKE_TOOLCHAIN_FILE` 在 CMake run 很早阶段就被读取，用于确定 compiler/toolchain/target-platform 信息。:chatgpt-content-reference{index="6"}

---

# 52. Preset vs Toolchain

这是必须严格区分的。

## Preset

```text
How do we invoke/configure this project?
```

例如：

```text
dev
release
asan
```

---

## Toolchain

```text
What platform/compiler environment are we targeting?
```

例如：

```text
native clang
aarch64-linux cross compiler
embedded ARM
vcpkg toolchain
```

---

# 53. 不要把所有项目 Options 都塞进 Toolchain

Toolchain file应该主要描述：

> toolchain/platform environment。

业务 project options：

```text
enable tests
enable examples
feature X
```

属于 project/preset 层。

---

# Part XIV · Cross Compilation

# 54. Build Machine 与 Target Machine

Cross compile：

```text
Host:
macOS arm64

Target:
Linux aarch64
```

Compiler运行在 host，

生成：

> target binary。

这会影响：

```text
find_library
find_program
try_run
code generators
```

---

# 55. Host Tool vs Target Tool

假设 build过程需要：

```text
code_generator
```

它必须：

> 在 build host 上运行。

而 library：

```text
libvehicle.so
```

是：

> target artifact。

所以 cross build会形成两个不同 artifact worlds：

```text
Host tools
Target binaries
```

这是复杂 native build最容易踩坑的地方之一。

---

# 56. `try_compile` vs `try_run`

Cross compile 时：

```text
compile target program
```

可能可行。

但：

```text
run target executable on host
```

通常不可行。

所以 build logic 不应该无意识依赖：

> configure 时执行 target binaries。

---

# Part XV · Dependency Discovery

# 57. `find_package`

CMake希望依赖最终暴露为：

> Imported Targets

例如：

```cmake
find_package(fmt CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        fmt::fmt
)
```

而不是：

```cmake
include_directories(${FMT_INCLUDE_DIR})
link_libraries(${FMT_LIBRARY})
```

---

# 58. Module Mode

寻找：

```text
FindFoo.cmake
```

这种 Find Module通常：

> 由 CMake、OS 或消费项目提供，

需要自己猜：

```text
headers在哪？
library在哪？
版本是什么？
```

Current CMake 文档明确把 Module Mode 描述为较 heuristic、可能过时的 discovery mechanism。:chatgpt-content-reference{index="7"}

---

# 59. Config Mode

寻找类似：

```text
FooConfig.cmake
foo-config.cmake
```

Current CMake 还支持正在发展的：

```text
Common Package Specification
*.cps
```

package descriptions。:chatgpt-content-reference{index="8"}

Config package通常由：

> package 自己安装。

因此它知道：

```text
its targets
components
usage requirements
dependencies
```

Current official docs也指出 Config packages 通常比外部 Find modules 更可靠，因为它们由 package 本身提供直接信息。:chatgpt-content-reference{index="9"}

---

# 60. 推荐消费模型

优先：

```cmake
find_package(Foo CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        Foo::Foo
)
```

而不是拿：

```text
FOO_INCLUDE_DIRS
FOO_LIBRARIES
```

手工拼图。

---

# Part XVI · Imported Targets

# 61. Imported Target 是什么？

外部 library：

```text
已经存在
```

但 CMake将它建模成正常 target：

```text
Foo::Foo
```

它可以携带：

```text
include dirs
link library path
compile definitions
transitive dependencies
```

于是 consumer：

```cmake
target_link_libraries(app PRIVATE Foo::Foo)
```

就足够。

---

# 62. 这是真正的 Dependency Object

不要把 dependency理解成：

```text
一个 .a 路径
```

真正依赖可能包括：

```text
library
headers
defines
other libraries
system libraries
compile mode
```

Imported target把它封装成：

> 一等 build graph node。

---

# Part XVII · `FetchContent`

# 63. Source Dependency

另一种策略：

> 在 configure/build ecosystem 内获得 dependency source，并作为 build graph一部分。

CMake提供：

```text
FetchContent
```

典型用于：

```text
small CMake-native dependencies
tests
developer tools
projects where source integration is desired
```

---

# 64. `FetchContent` 不是 Package Manager

它可以：

```text
download/populate source
make dependency available
```

但 package manager通常还负责：

```text
binary caching
version graph
profiles
compiler/ABI settings
registries
package recipes
```

不要混。

---

# 65. `FetchContent` 的一个架构风险

所有 dependency 源码进入同一次 configure/build universe：

```text
option collisions
policy interactions
long configure/build times
dependency-specific assumptions
```

所以：

> 大型 dependency graph不应该无脑全部 FetchContent。

---

# Part XVIII · Package Manager

# 66. CMake 与 Package Manager 的职责不同

```text
Package Manager
↓
resolve / obtain dependency artifacts

CMake
↓
consume them as build graph targets
```

成熟 integration应该让：

```text
find_package()
```

在项目 CMakeLists里保持正常，

而 package manager负责让 package可被发现。

---

# 67. Conan 2

Current Conan 2 文档的推荐 CMake flow是：

```text
Conan install
↓
generate toolchain/package config metadata
↓
CMake configure
```

其 `CMakeToolchain` 生成 CMake toolchain 信息；current Conan 文档也已引入更现代的 `CMakeConfigDeps`，作为 `CMakeDeps` 的改进方向。:chatgpt-content-reference{index="10"}

理想项目 CMakeLists仍然写：

```cmake
find_package(fmt CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        fmt::fmt
)
```

而不是：

```text
if CONAN ...
```

到处侵入 build logic。

---

# 68. vcpkg

vcpkg 当前官方指南推荐大多数用户采用：

> **Manifest Mode**

即项目内：

```text
vcpkg.json
```

声明 direct dependencies，并支持版本/registry 等项目级能力。:chatgpt-content-reference{index="11"}

它通常通过：

```text
CMAKE_TOOLCHAIN_FILE
```

集成到 CMake。

---

# 69. Conan vs vcpkg 的选择模型

不要问：

> “谁绝对更高级？”

更应该看：

```text
organization package workflow
binary cache requirements
cross compilation
custom recipes
dependency ecosystem
registries
CI model
platforms
```

概念上：

### vcpkg

倾向：

```text
manifest-centric
strong Microsoft/CMake integration
large port ecosystem
```

### Conan

倾向：

```text
package recipe/profile model
complex binary/package configuration
cross-platform package publishing
```

两者都可以和现代 CMake target model很好组合。

---

# Part XIX · Dependency Policy

# 70. Dependency 的四种来源

可以把依赖粗分：

```text
System-provided package
Package-manager package
Source-integrated dependency
Vendored source
```

---

# 71. System Package

例如 Linux distro提供。

优点：

```text
OS integration
security updates
```

缺点：

```text
version variability
cross-platform reproducibility lower
```

---

# 72. Package Manager

优点：

```text
version declaration
reproducibility
binary/source management
```

适合大型跨平台工程。

---

# 73. FetchContent / Source-integrated

优点：

```text
simple
same build universe
```

适合较小依赖。

---

# 74. Vendor

源码直接进入 repo：

```text
third_party/
```

优点：

```text
maximum pinning/control
offline builds
```

代价：

```text
maintenance
updates
repo size
licensing/governance
```

---

# 75. Dependency Policy 应该明确

不要每个开发者随意：

```text
brew install Foo
FetchContent Bar
git submodule Baz
Conan Qux
```

同一个项目混成不可复现环境。

应定义：

> 哪类 dependency 通过什么 mechanism 获取。

---

# Part XX · Install

# 76. Build Success ≠ Package Success

Library project不应该只做到：

```text
cmake --build
```

真正 library lifecycle：

```text
Build
↓
Test
↓
Install
↓
Consumer
```

---

# 77. `GNUInstallDirs`

不要硬编码：

```cmake
DESTINATION lib
DESTINATION include
```

优先：

```cmake
include(GNUInstallDirs)
```

使用：

```text
CMAKE_INSTALL_BINDIR
CMAKE_INSTALL_LIBDIR
CMAKE_INSTALL_INCLUDEDIR
```

让 distro/package maintainer 能控制 layout。

Current CMake install docs明确建议 package projects使用这些标准 install directory variables。:chatgpt-content-reference{index="12"}

---

# 78. Install Target

例如：

```cmake
install(
    TARGETS core
    EXPORT MyProjectTargets
    FILE_SET HEADERS
)
```

意义：

```text
Install artifact
+
Install public headers
+
Associate target with export set
```

---

# Part XXI · Export

# 79. Export 的目标

消费项目应该能够：

```cmake
find_package(MyProject CONFIG REQUIRED)

target_link_libraries(app
    PRIVATE
        MyProject::core
)
```

而不需要知道：

```text
library path
header path
compiler flags
transitive dependencies
```

---

# 80. `install(EXPORT ...)`

例如：

```cmake
install(
    EXPORT MyProjectTargets
    NAMESPACE MyProject::
    DESTINATION
        ${CMAKE_INSTALL_LIBDIR}/cmake/MyProject
)
```

生成：

> installed imported-target descriptions。

---

# 81. 为什么 Namespace 很重要？

```text
core
```

名字过于模糊。

安装后：

```text
MyProject::core
```

清楚表达：

> imported target from package MyProject。

而且如果 typo：

```text
MyProjct::core
```

CMake可以更早发现 target不存在，

不像裸 linker name可能被悄悄解释成：

```text
-lMyProjct::core
```

之类的问题。

---

# Part XXII · Package Config

# 82. `<Package>Config.cmake`

当 consumer：

```cmake
find_package(MyProject CONFIG REQUIRED)
```

需要找到：

```text
MyProjectConfig.cmake
```

它通常负责：

```text
load exported targets
find package dependencies
expose components
```

---

# 83. Relocatable Package

错误 Config：

```cmake
set(MYPROJECT_INCLUDE_DIR
    "/Users/alice/work/project/include")
```

安装包搬到：

```text
/usr/local
```

立即失效。

应让 package：

> 相对 install prefix 可迁移。

CMake 官方提供 `configure_package_config_file()` 专门帮助生成 relocatable Config 文件，并推荐它而不是普通 `configure_file()` 处理 package config。:chatgpt-content-reference{index="13"}

---

# 84. Version Config

可以生成：

```text
MyProjectConfigVersion.cmake
```

帮助：

```cmake
find_package(
    MyProject
    2.1
    REQUIRED
)
```

判断 version compatibility。

官方 `CMakePackageConfigHelpers` 提供 `write_basic_package_version_file()` 等 helper。:chatgpt-content-reference{index="14"}

---

# Part XXIII · Package Dependencies

# 85. Exported Target 依赖另一个 Package

例如：

```text
MyProject::core
↓ PUBLIC
fmt::fmt
```

你的：

```text
MyProjectConfig.cmake
```

通常需要：

```cmake
include(CMakeFindDependencyMacro)
find_dependency(fmt CONFIG)
```

然后再：

```cmake
include(
    "${CMAKE_CURRENT_LIST_DIR}/MyProjectTargets.cmake"
)
```

否则 consumer加载：

```text
MyProject::core
```

时可能找不到：

```text
fmt::fmt
```

---

# 86. 这就是为什么 `PUBLIC` Dependency 属于 Package Contract

C++ public interface泄漏：

```text
dependency type
```

会一路传播：

```text
C++ API
↓
CMake Usage Requirement
↓
Package dependency
↓
Consumer graph
```

整个系统高度一致。

---

# Part XXIV · Generated Files

# 87. Build 可能包含 Code Generation

例如：

```text
signals.csv
↓
generator
↓
generated_decoder.cpp
↓
compile
```

这也是 artifact graph。

---

# 88. `add_custom_command(OUTPUT ...)`

好的 codegen应该声明：

```text
inputs
outputs
dependencies
command
```

让 build system知道：

> 输入什么时候改变、哪些 outputs 要重新生成。

而不是：

```cmake
execute_process(...)
```

在 configure 阶段随便生成所有 build outputs。

---

# 89. Configure-time vs Build-time Generation

如果 output：

> 随 build dependency变化，

更适合 build graph custom command。

如果只是：

```text
configure template based on project version
```

可以使用：

```cmake
configure_file(...)
```

在 configure 阶段。

必须明确：

```text
configure dependency
vs
build dependency
```

---

# 90. Generated File 也应该属于 Target

```cmake
target_sources(decoder
    PRIVATE
        ${generated_cpp}
)
```

而不是生成完后成为：

> Build system无法追踪的神秘文件。

---

# Part XXV · C++ Modules

# 91. C++ Modules 改变什么？

传统：

```text
header
↓ textual include
each TU reparses
```

Modules：

```text
module interface
↓
compiler-managed compiled module information
↓
import
```

目标之一：

```text
reduce textual inclusion
stronger dependency semantics
```

但 modules 会让：

> Build system 必须理解 module dependency graph。

---

# 92. CMake 的 `CXX_MODULES` File Set

Current CMake 提供：

```cmake
target_sources(core
    PUBLIC
        FILE_SET CXX_MODULES
        FILES
            src/core.cppm
)
```

作为一等 module source model；当前官方文档显示 `CXX_MODULES` file sets 自 CMake 3.28 起进入该 target model，并可参与安装/export。:chatgpt-content-reference{index="15"}

---

# 93. 为什么 Modules 需要 Build-system Support？

假设：

```cpp
export module A;

import B;
```

Build system必须知道：

```text
B module artifact
↓
must exist before
A compilation
```

而普通 source dependency scanner过去主要只处理：

```text
#include
```

因此 modules不是：

> 把 `.hpp` 后缀改成 `.cppm`

那么简单。

---

# 94. 当前工程策略

Modern CMake 已有 first-class module support，

但实际成熟度仍然取决于：

```text
compiler
generator
standard library module support
IDE/tooling
dependency packaging
```

因此本 Track 的稳定工程基线仍然是：

```text
headers + target-based CMake
```

Modules：

> 应理解并实验，但不要为了“现代”无条件重构整个大型工程。

---

# 95. Standard Library Modules

C++23 标准定义了：

```cpp
import std;
```

等标准库 module方向。

但实际可用性依赖：

> compiler + standard library + build-system integration。

因此：

```text
Language Feature Exists
≠
Your Toolchain Stack Is Fully Production-ready
```

这是 G9 非常重要的一条经验。

---

# Part XXVI · Precompiled Headers

# 96. PCH

传统 headers很重：

```text
<vector>
<string>
<unordered_map>
...
```

每个 TU重复 parse。

PCH：

> 预编译一组稳定 headers。

CMake：

```cmake
target_precompile_headers(core
    PRIVATE
        <vector>
        <string>
)
```

---

# 97. PCH 是 Build-performance Optimization

它不应该改变：

> source semantics。

因此：

```text
Build correctness
```

不能依赖：

> “某 header刚好通过 PCH 被间接 include。”

每个 source/header仍应拥有正确 dependencies。

---

# 98. PCH 的 Trade-off

收益：

```text
compile time ↓
```

代价：

```text
larger precompiled artifact
dependency invalidation
toolchain-specific behavior
possible reduced modularity pressure
```

先 profile build time，

不要一开始就塞一个：

```text
everything.hpp
```

---

# Part XXVII · Unity Builds

# 99. Unity Build

原：

```text
a.cpp → a.o
b.cpp → b.o
c.cpp → c.o
```

Unity可能把多个 source组合成：

```text
unity.cpp
  includes a.cpp
  includes b.cpp
  includes c.cpp
```

减少：

```text
frontend startup
header reparsing
```

---

# 100. Unity 的风险

原本不同 TU 隔离的：

```text
static names
anonymous namespaces
macros
implementation assumptions
```

可能发生碰撞/interaction。

所以：

> Unity build是 build-time optimization，不应成为正确性前提。

项目必须能正常：

> 非 Unity 构建。

---

# Part XXVIII · LTO / IPO

# 101. LTO

> **Link-Time Optimization**

传统：

```text
TU A compile independently
TU B compile independently
↓
link machine objects
```

LTO 保留更多 compiler IR/summary information，

允许 link阶段跨 TU：

```text
inline
dead-code elimination
constant propagation
devirtualization
```

---

# 102. CMake 中是 IPO Property

```cmake
set_property(
    TARGET core
    PROPERTY
        INTERPROCEDURAL_OPTIMIZATION TRUE
)
```

更成熟的配置通常先检测：

```text
toolchain supports IPO?
```

再为 release target/profile启用。

---

# 103. LTO 不是 Release = On 的必然规则

代价：

```text
link time
memory
debug/profiling changes
toolchain compatibility
binary build complexity
```

收益：

> workload-dependent。

应该：

```text
benchmark production binary
```

决定。

---

# Part XXIX · Warnings

# 104. Warning 是 Target Policy

例如内部 helper：

```cmake
add_library(project_warnings INTERFACE)
```

然后根据 compiler：

```text
Clang/GCC
MSVC
```

发布 warning options。

业务 target：

```cmake
target_link_libraries(core
    PRIVATE
        project_warnings
)
```

---

# 105. 为什么 Warning 通常 `PRIVATE`？

你可能希望自己的源码：

```text
-Wall
-Wextra
-Wconversion
```

但不应该把：

> 你的 warning policy

强迫给 downstream consumers。

尤其：

```text
-Werror
```

几乎不应该作为 installed public usage requirement。

---

# 106. `-Werror` 的正确位置

CI/internal build：

> 很合理。

第三方 consumer：

> 不应该被你的 package强制。

所以：

```text
warnings-as-errors
```

更像：

> project build policy

而不是 library interface。

---

# Part XXX · Sanitizers

# 107. Sanitizer Profile

开发中：

```text
ASan
UBSan
TSan
```

是非常重要的动态 correctness工具。

但它们：

```text
change binary
insert runtime checks
change timing/layout
```

所以应该通过：

```text
dedicated profile/preset
```

管理。

---

# 108. 不要把 Sanitizer Flags 全局写死

比如：

```cmake
set(CMAKE_CXX_FLAGS
    "... -fsanitize=address")
```

会污染：

```text
every target
dependencies
host tools
possibly install/export usage
```

更合理：

```text
sanitizer interface target
```

只 link到：

> 你真正控制的 targets。

---

# 109. Compile + Link 两边都重要

Sanitizer通常不仅需要 compile instrumentation，

还需要：

```text
link sanitizer runtime
```

所以配置应同时考虑：

```cmake
target_compile_options(...)
target_link_options(...)
```

Current CMake target link options本身也支持 PUBLIC/PRIVATE/INTERFACE usage model。:chatgpt-content-reference{index="16"}

---

# Part XXXI · Clang Tooling

# 110. `compile_commands.json`

clangd真正需要：

> 每个 TU 的真实 compile command。

CMake + Ninja/Make可以生成：

```text
compile_commands.json
```

通常：

```cmake
CMAKE_EXPORT_COMPILE_COMMANDS=ON
```

于是 clangd知道：

```text
include paths
defines
language mode
generated headers
```

不是：

> 靠编辑器猜。

---

# 111. clangd 是 Build Graph Consumer

这是一个很好的 mental model：

```text
CMake
↓
compile database
↓
clangd
```

所以 clangd“找不到 header”时，

问题经常不是 LSP：

> 而是 build description不完整或 compile database过期。

---

# 112. clang-tidy

CMake targets可以关联：

```text
CXX_CLANG_TIDY
```

进行静态分析。

但要区分：

```text
editor-time lint
CI static analysis
every build compile hook
```

全量 clang-tidy 可能显著拖慢 build。

所以应设计 profile。

---

# 113. clang-format 不属于 Build Correctness

clang-format：

> source formatting tool。

不应该因为：

```text
format check
```

而污染正常 target compile graph。

可以：

```text
CI job
developer command
pre-commit workflow
```

单独运行。

---

# Part XXXII · CTest

# 114. Test 也是 Target Consumer

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

测试应该和真实 consumer一样：

> link public target。

不要通过：

```text
直接 include src/private implementation
```

绕过接口，

除非明确是 white-box test。

---

# 115. Test Layer

可以区分：

```text
unit
component
integration
install-consumer
benchmark
```

不要把全部混成：

```text
tests
```

一个命令概念。

---

# 116. CTest Preset

Current presets支持 test presets，

因此：

```bash
ctest --preset dev
```

可以成为团队稳定入口。:chatgpt-content-reference{index="17"}

---

# Part XXXIII · Benchmarks

# 117. Benchmark 不是普通 Unit Test

Unit test：

```text
correct?
```

Benchmark：

```text
how fast?
```

它们需要不同环境：

```text
optimized build
noise control
representative input
```

所以不要把 microbenchmarks放在：

> Debug/ASan test profile

里得出性能结论。

---

# Part XXXIV · Coverage

# 118. Coverage 也是 Instrumentation Profile

Coverage需要：

```text
compiler instrumentation
special link/runtime settings
```

应作为：

```text
coverage preset/profile
```

而不是永久 build option。

---

# Part XXXV · Symbol Visibility

# 119. G8 → G9

G8确定：

> 默认隐藏内部 symbols 是优秀 shared-library策略。

CMake可以通过 target properties表达：

```text
CXX_VISIBILITY_PRESET
VISIBILITY_INLINES_HIDDEN
```

再配合：

```text
export macro
```

明确 public ABI。

---

# 120. Visibility 是 Target Property，不应靠每个 Source 手写 Flags

这正是 CMake target abstraction的价值：

```text
ABI policy
→ target property
```

而不是：

```text
每个 compile command拼 -fvisibility...
```

---

# Part XXXVI · Position Independent Code

# 121. PIC

Shared library在很多平台需要：

> position-independent code。

CMake target property：

```text
POSITION_INDEPENDENT_CODE
```

比手工：

```text
-fPIC
```

更跨平台、更语义化。

---

# Part XXXVII · Runtime Library Paths

# 122. Build-time Link Success 不等于 Runtime Load Success

Executable：

```text
links libfoo.dylib
```

运行时 loader还要：

> 找到这个 artifact。

涉及：

```text
RPATH
RUNPATH
install_name
loader paths
```

等平台机制。

---

# 123. 不要硬编码 Developer Absolute Path

错误 package：

```text
/Users/alice/build/foo/libfoo.dylib
```

进入 installed artifact。

另一个机器：

> 立即失效。

安装设计必须：

> relocatable。

G8 的 ABI boundary 与 G9 的 install layout 在这里相遇。

---

# Part XXXVIII · Project Options

# 124. Options 应该表达真实 Feature

例如：

```cmake
option(MYPROJECT_BUILD_TESTS
    "Build project tests"
    ON
)
```

合理。

---

# 125. 不要制造巨大 Option Matrix

如果：

```text
USE_FOO
USE_BAR
FOO_MODE_A
FOO_MODE_B
NEW_ENGINE
LEGACY_ENGINE
```

随意组合，

实际 build matrix：

```text
2^N
```

可能根本没有测试。

每一个 option：

> 都是 configuration state-space multiplier。

---

# 126. Feature Flags 也需要测试矩阵

如果 project声称支持：

```text
shared/static
tests on/off
modules on/off
exceptions on/off
```

就应该：

> CI 验证这些组合中的 supported set。

否则只是理论支持。

---

# Part XXXIX · Project Structure

# 127. 一个健康的 Library + App Structure

```text
project/
├── CMakeLists.txt
├── CMakePresets.json
├── cmake/
│   ├── ProjectOptions.cmake
│   ├── ProjectWarnings.cmake
│   └── MyProjectConfig.cmake.in
├── include/
│   └── myproject/
│       └── decoder.hpp
├── src/
│   ├── CMakeLists.txt
│   └── decoder.cpp
├── apps/
│   ├── CMakeLists.txt
│   └── cli.cpp
├── tests/
│   ├── CMakeLists.txt
│   └── decoder_test.cpp
└── benchmarks/
```

不需要迷信这个具体目录。

关键：

```text
ownership boundaries
target boundaries
public/private headers
```

清晰。

---

# 128. Root `CMakeLists.txt` 不应该装整个世界

Root负责：

```text
minimum version
project()
global project-level decisions
add_subdirectory
install/package setup
```

各 component：

> 自己定义自己的 targets。

不要把 2000 行所有 targets 全塞 root。

---

# Part XL · 一个完整 Modern CMake Library

# 129. Root

```cmake
cmake_minimum_required(VERSION 4.0)

project(
    VehicleSignals
    VERSION 1.0.0
    LANGUAGES CXX
)

include(GNUInstallDirs)
include(CTest)

add_subdirectory(src)

if(BUILD_TESTING)
    add_subdirectory(tests)
endif()
```

注意：

> `cmake_minimum_required()` 应选择项目真正愿意支持的最低 CMake 版本。

即使开发机安装 4.4.x，

也不意味着 library必须要求 4.4。

---

# 130. Library Target

```cmake
add_library(vehicle_signals)

add_library(
    VehicleSignals::vehicle_signals
    ALIAS
    vehicle_signals
)

target_sources(vehicle_signals
    PRIVATE
        decoder.cpp

    PUBLIC
        FILE_SET HEADERS
        BASE_DIRS
            ${PROJECT_SOURCE_DIR}/include
        FILES
            ${PROJECT_SOURCE_DIR}/include/vehicle/decoder.hpp
)

target_compile_features(vehicle_signals
    PUBLIC
        cxx_std_23
)

set_target_properties(vehicle_signals PROPERTIES
    CXX_EXTENSIONS NO
)
```

---

# 131. Dependency

```cmake
find_package(fmt CONFIG REQUIRED)

target_link_libraries(vehicle_signals
    PRIVATE
        fmt::fmt
)
```

假设 fmt只在：

```text
decoder.cpp
```

使用。

如果 public header使用 fmt types：

```text
PRIVATE
```

就不对了。

应该：

```text
PUBLIC
```

---

# 132. Include Paths

使用 header file sets 后，

现代 CMake能够知道 header base directories；

如果仍需显式 include directory：

```cmake
target_include_directories(vehicle_signals
    PUBLIC
        $<BUILD_INTERFACE:
            ${PROJECT_SOURCE_DIR}/include
        >
        $<INSTALL_INTERFACE:
            ${CMAKE_INSTALL_INCLUDEDIR}
        >
)
```

---

# 133. Warnings

```cmake
add_library(project_warnings INTERFACE)

target_compile_options(project_warnings
    INTERFACE
        $<$<CXX_COMPILER_ID:Clang,AppleClang>:
            -Wall
            -Wextra
            -Wpedantic
        >
)

target_link_libraries(vehicle_signals
    PRIVATE
        project_warnings
)
```

Notice：

```text
warnings policy
```

没有传播给 installed consumer。

---

# 134. Install

```cmake
install(
    TARGETS vehicle_signals
    EXPORT VehicleSignalsTargets
    FILE_SET HEADERS
)

install(
    EXPORT VehicleSignalsTargets
    NAMESPACE VehicleSignals::
    DESTINATION
        ${CMAKE_INSTALL_LIBDIR}/cmake/VehicleSignals
)
```

---

# 135. Config Generation

```cmake
include(CMakePackageConfigHelpers)

configure_package_config_file(
    ${PROJECT_SOURCE_DIR}/cmake/VehicleSignalsConfig.cmake.in
    ${PROJECT_BINARY_DIR}/VehicleSignalsConfig.cmake

    INSTALL_DESTINATION
        ${CMAKE_INSTALL_LIBDIR}/cmake/VehicleSignals
)

write_basic_package_version_file(
    ${PROJECT_BINARY_DIR}/VehicleSignalsConfigVersion.cmake

    VERSION
        ${PROJECT_VERSION}

    COMPATIBILITY
        SameMajorVersion
)

install(
    FILES
        ${PROJECT_BINARY_DIR}/VehicleSignalsConfig.cmake
        ${PROJECT_BINARY_DIR}/VehicleSignalsConfigVersion.cmake

    DESTINATION
        ${CMAKE_INSTALL_LIBDIR}/cmake/VehicleSignals
)
```

---

# 136. Consumer

完全独立的另一个项目：

```cmake
find_package(
    VehicleSignals
    1
    CONFIG
    REQUIRED
)

add_executable(app
    main.cpp
)

target_link_libraries(app
    PRIVATE
        VehicleSignals::vehicle_signals
)
```

这才是：

> **真正完成的 native library package。**

---

# Part XLI · CMake Anti-pattern Catalogue

# 137. Anti-pattern 1 — Global Flags

```cmake
set(CMAKE_CXX_FLAGS ...)
```

问题：

> 不属于 target graph。

---

# 138. Anti-pattern 2 — Global Include Directories

```cmake
include_directories(...)
```

制造隐式依赖。

---

# 139. Anti-pattern 3 — Absolute Link Paths

```cmake
target_link_libraries(app
    /usr/local/lib/libfoo.a
)
```

强绑定本机环境。

---

# 140. Anti-pattern 4 — Link by Bare Name When Target Exists

```cmake
target_link_libraries(app PRIVATE foo)
```

如果真正 package提供：

```text
Foo::Foo
```

优先 imported target。

---

# 141. Anti-pattern 5 — `file(GLOB ...)` Blindly Discover Sources

例如：

```cmake
file(GLOB SOURCES src/*.cpp)
```

是否合适取决于 workflow。

显式 source membership：

```text
更清楚地表达 target contents
```

尤其 public library/API。

现代 CMake对 glob也有 configure-dependency机制，但通常不需要为省几行 source list牺牲清晰 build graph。

---

# 142. Anti-pattern 6 — Fetch Everything

把整个 ecosystem：

```text
50 dependencies
```

全部 FetchContent进入一个 configure universe。

维护成本会急剧上升。

---

# 143. Anti-pattern 7 — Package Manager Logic Leaks Into CMake Everywhere

```cmake
if(CONAN)
...
elseif(VCPKG)
...
```

理想：

```text
package manager provides package
↓
CMake uses find_package + targets
```

---

# 144. Anti-pattern 8 — Install Untested

Library只有本 repo：

```text
build passes
```

从未测试：

```text
install + external find_package
```

---

# 145. Anti-pattern 9 — Public Absolute Paths

Installed target的：

```text
INTERFACE_INCLUDE_DIRECTORIES
INTERFACE_LINK_LIBRARIES
```

携带开发机绝对路径。

Package不可 relocatable。

官方 CMake 也特别警告 installed package interface 不应硬编码依赖在构建机上的绝对 library 路径。:chatgpt-content-reference{index="18"}

---

# 146. Anti-pattern 10 — Global `-Werror`

让 dependency/consumer 因不同 compiler warning：

> 直接无法构建。

---

# 147. Anti-pattern 11 — CMake as General-purpose Programming Language

几十层：

```text
functions
macros
dynamic variables
string magic
```

用来模拟 package manager/framework。

CMake应该主要：

> 描述 build graph。

复杂业务逻辑应尽量留在：

```text
real scripts/tools
```

里。

---

# Part XLII · Reproducibility

# 148. “能编译”不等于“可复现”

真正要记录：

```text
source commit
compiler version
stdlib
CMake version
dependency versions
target platform
build options
```

否则：

```text
same source
```

可能产生不同 binary。

---

# 149. Lock Dependency Versions

Package manager：

```text
manifest / lock / recipe revisions
```

应成为 reproducibility strategy的一部分。

不要仅写：

```text
find_package(Foo REQUIRED)
```

却对 CI/production使用哪个 Foo版本毫无控制。

---

# 150. Compiler 也属于 Input

例如：

```text
Clang 20
vs
Clang 22
```

可能改变：

```text
diagnostics
optimization
ABI in edge cases
codegen
```

所以发布 binary时：

> Toolchain identity 是 artifact metadata。

---

# Part XLIII · Hermeticity

# 151. Hermetic Build 的目标

尽量避免：

```text
build结果依赖开发者机器偶然安装了什么
```

例如：

```text
/usr/local/include/foo
```

被意外找到。

---

# 152. 完全 Hermetic 不一定是所有项目目标

Distro packaging反而可能明确：

> 使用 system dependencies。

所以 again：

> Build philosophy 应匹配 distribution model。

关键不是：

> 每个项目都完全 hermetic。

而是：

> dependency source必须明确。

---

# Part XLIV · CI Matrix

# 153. CI 不应该只验证一个 Build

一个 serious C++ library至少应考虑：

```text
compiler
OS
architecture
build profile
shared/static where supported
```

但不要笛卡尔积爆炸。

选择：

> 真正承诺支持的 matrix。

---

# 154. 一个合理层次

例如：

```text
Fast PR:
Clang / Linux dev
tests
sanitizers

Main:
Clang + GCC
Linux + macOS
Release build
install-consumer test

Scheduled:
larger matrix
benchmarks
ABI checks
```

原则比具体平台列表重要。

---

# Part XLV · Build Performance

# 155. 编译性能也是工程性能

大型 C++ 工程的：

```text
clean build
incremental build
link time
configure time
```

直接影响：

> Developer Experience。

所以值得 measure。

---

# 156. 常见杠杆

从高层到低层：

```text
header dependency reduction
PImpl
forward declarations
target boundaries
Modules
PCH
Unity build
faster linker
distributed/cache compilation
```

不要一上来：

> Unity Everything。

---

# 157. Header Dependency 是 Build Graph Dependency

如果：

```cpp
// public.hpp
#include <huge_dependency.hpp>
```

那么所有 downstream TUs：

> 都需要处理这份 dependency。

所以 G8 PImpl 不仅是 ABI technique，

还是：

> Build-time dependency firewall。

---

# Part XLVI · Build Cache

# 158. Compilation Cache

诸如 compiler cache systems可以利用：

```text
same compiler input
→ reuse previous object output
```

减少重复编译。

但要注意：

```text
compiler command line
preprocessed content
environment
```

都会影响 cache key。

---

# 159. Reproducible Compile Commands 更利于 Cache

到处动态：

```text
absolute temp paths
timestamps
random defines
```

会降低 cache hit。

所以 build determinism与：

> build performance

也有关。

---

# Part XLVII · Packaging

# 160. CPack

CMake生态还提供：

```text
CPack
```

用于生成：

```text
archives
installer/package formats
```

它位于：

```text
install tree
↓
distribution artifact
```

这一层。

---

# 161. 先把 Install 做对，再谈 Package

如果：

```text
cmake --install
```

生成的树本身就不正确，

CPack不会神奇修复。

所以：

```text
Build
↓
Install
↓
Package
```

严格分层。

---

# Part XLVIII · G9 推荐工程 Profile

# 162. 核心工程原则

推荐把项目分成：

```text
Project Semantics
Toolchain
Build Profile
Dependency Resolution
Artifact Packaging
```

五层。

不要揉成一个巨型：

```text
CMakeLists.txt
```

---

# 163. Project Semantics

```text
targets
source membership
public/private dependencies
language requirements
install/export
```

这是：

> repo核心事实。

---

# 164. Toolchain

```text
compiler
architecture
sysroot
cross target
```

---

# 165. Build Profile

```text
dev
san
release
coverage
```

---

# 166. Dependency Resolution

```text
system
Conan
vcpkg
FetchContent
vendor
```

---

# 167. Artifact Packaging

```text
install prefix
package config
archive
container/image
SDK
```

---

# Part XLIX · Practical Labs

# 168. Lab 1 — Convert Global CMake to Target CMake

从：

```cmake
include_directories(include)
add_definitions(-DFOO)
set(CMAKE_CXX_FLAGS "...")

add_executable(app ...)
target_link_libraries(app foo)
```

重构为：

```text
targets
usage requirements
imported dependencies
```

要求能解释：

> 每个 requirement真正属于哪个 target。

---

# 169. Lab 2 — PUBLIC / PRIVATE

设计：

```text
core
network
app
```

`network.hpp` public interface 使用：

```cpp
core::Message
```

闭卷判断：

```cmake
target_link_libraries(network
    ??? core
)
```

答案不是背：

> PUBLIC。

而是推：

```text
consumer compiles network.hpp
↓
must understand core::Message
↓
core is interface requirement
```

---

# 170. Lab 3 — Installable Library

实现：

```text
MyLib::core
```

支持：

```bash
cmake --install
```

然后 separate consumer：

```cmake
find_package(MyLib CONFIG REQUIRED)
```

成功。

这是 G9 最重要实践之一。

---

# 171. Lab 4 — Presets

至少：

```text
dev
san
release
```

三套。

所有人只需要：

```bash
cmake --preset dev
cmake --build --preset dev
ctest --preset dev
```

避免 README 中复制长命令。

---

# 172. Lab 5 — Cross Compile

即使没有真实 embedded board，

也需要读懂一个 toolchain：

```text
target OS
target CPU
compiler
sysroot
find modes
```

并解释：

> 为什么 host code generator 与 target executable必须区分。

---

# 173. Lab 6 — Dependency Integration

同一个简单 dependency分别：

```text
find_package(system/package manager)
FetchContent
```

消费。

观察：

> 项目 target code应该尽量保持相同。

---

# 174. Lab 7 — Build-time Codegen

输入：

```text
signals.csv
```

生成：

```text
generated.cpp
generated.hpp
```

用：

```text
add_custom_command(OUTPUT ...)
```

建图。

修改 csv：

> 只重新生成/编译受影响 artifacts。

---

# 175. Lab 8 — C++ Module

实现一个最小：

```cpp
export module math;
```

通过：

```cmake
FILE_SET CXX_MODULES
```

构建。

重点不是 syntax，

而是观察：

```text
module dependency scanning
build ordering
generated module artifacts
```

与传统 header build 的差异。

---

# 176. Lab 9 — Build Performance

记录：

```text
clean build
incremental one-line .cpp change
public header change
```

时间。

然后分别尝试：

```text
PImpl
PCH
Unity
```

观察：

> 它们优化的是哪一类 build cost。

---

# Part L · G9 Review Protocol

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

---

# Part LI · 高频错误

# 177. 错误 1

> CMake 是 compiler。

错。

它主要生成/配置 build graph。

---

# 178. 错误 2

> `target_link_libraries` 只控制 linker。

错。

它还是 transitive usage-requirement graph 的核心。:chatgpt-content-reference{index="19"}

---

# 179. 错误 3

> PUBLIC 表示“这是一个公开 library”。

错。

它表示：

```text
current target itself需要
+
consumer也需要
```

---

# 180. 错误 4

> 所有 compiler flags 放 `CMAKE_CXX_FLAGS` 最方便。

短期方便，

长期摧毁 target isolation。

---

# 181. 错误 5

> CMake target link 到 `.a` 文件路径就完成 dependency modeling。

没有表达：

```text
headers
defines
transitive libs
usage requirements
```

---

# 182. 错误 6

> Preset 和 Toolchain 是一回事。

错。

```text
Preset
→ workflow/configuration

Toolchain
→ compiler/target environment
```

---

# 183. 错误 7

> vcpkg/Conan 可以替代 CMake。

它们解决 dependency/package problem，

CMake解决 project build graph。

---

# 184. 错误 8

> FetchContent 是完整 package manager。

不是。

---

# 185. 错误 9

> Library在本仓库能链接，所以 package已经正确。

必须：

> install + external consumer test。

---

# 186. 错误 10

> Release = `-O3`。

Production profile还包括：

```text
debug symbols
LTO policy
visibility
assert policy
sanitizer off
ABI settings
```

等。

---

# 187. 错误 11

> Modules 替代 headers 后 build system 会更简单。

恰恰需要 build system更准确理解 module dependency graph。

---

# 188. 错误 12

> PCH / Unity / LTO 都是应该默认打开的“性能选项”。

它们优化不同阶段，

都有 trade-off。

---

# 189. 错误 13

> clangd 配不好就是编辑器问题。

很多时候是：

> compile database/build graph不准确。

---

# 190. 错误 14

> Cross compile 只是换一个 compiler executable。

还涉及：

```text
sysroot
target platform
host tools
package discovery
try-run
```

---

# 191. 错误 15

> CMake越复杂说明工程越专业。

优秀 CMake 往往：

> target model清晰、逻辑很少、关系明确。

---

# Part LII · C++ / Zig / Rust 对照

# 192. C++ / CMake

C++ 本身没有统一官方 package/build system。

因此生态历史上高度分散：

```text
Make
Autotools
CMake
Meson
Bazel
package managers
IDE projects
```

CMake最终成为最广泛的 interoperability layer之一。

代价：

> 它必须兼容大量平台、compiler、历史模式。

---

# 193. Zig Build

Zig build system更接近：

> 语言/toolchain原生 artifact graph API。

它天然知道：

```text
target
optimization
compiler
artifact
module
```

因此很多概念比 CMake更统一。

---

# 194. Rust Cargo

Cargo进一步把：

```text
build
dependency resolution
package publishing
feature graph
test
```

高度整合。

C++ 则通常由：

```text
CMake
+
package manager
+
CTest
+
external tooling
```

组合完成。

---

# 195. 为什么学 CMake 仍然很重要？

不是因为：

> CMake语言优雅。

而是因为：

> C++ native ecosystem 的现实 interoperability value 极高。

尤其：

```text
third-party libraries
robotics
HPC
embedded
SDKs
cross-platform
```

大量项目已经围绕 CMake ecosystem组织。

---

# 196. 不要把 Zig Build 当“CMake Syntax Replacement”

如果用 Zig build驱动 C++：

> 可以是非常优秀的学习/内部项目选择。

但面对：

```text
third-party CMake package
install/export ecosystem
C++ SDK consumers
ROS/native ecosystem
```

仍然需要理解：

> CMake package model。

因为问题不只是：

```text
“怎么执行 clang++”
```

而是：

> **怎样参与整个 C++ native dependency ecosystem。**

---

# Part LIII · G9 Final Fifteen Axioms

如果半年以后只保留十五条：

1. **Build system 的核心是 Artifact Dependency Graph，而不是 shell command 集合。**

2. **Modern CMake 的核心 abstraction 是 Target：artifact + build properties + transitive usage requirements。**

3. **`PRIVATE / PUBLIC / INTERFACE` 应从 C++ source interface dependency 推导，而不是靠经验背诵。**

4. **Build requirement 应附着到最窄的 owning target，避免 global include paths、flags 和 linker state。**

5. **Source Tree、Build Tree、Install Tree 是不同 representations；一个库必须测试真正的 install-consumer path。**

6. **Preset 描述项目支持的 build workflow，Toolchain 描述 compiler/target environment；两者不能混。**

7. **Dependency package 应尽量以 Imported Target 的形式进入 CMake graph，而不是裸路径和全局变量。**

8. **CMake、Conan/vcpkg、Ninja 分别解决 build graph、package resolution、build execution 等不同问题，不应混为一层。**

9. **一个可发布 library 的完成条件不仅是 build 成功，而是 install/export/config/version/consumer 全链路成立。**

10. **Generated code 也必须成为 build graph 中具有明确 input/output/dependency 的 artifact。**

11. **C++ Modules 需要 build system参与 dependency scanning；语言 feature availability 不等于整个 compiler/stdlib/build stack 都已成熟。**

12. **PCH、Unity、LTO 都是特定阶段的 optimization，不是“现代 C++ 必开选项”。**

13. **Cross compilation 是 Host Universe 与 Target Universe 的分离，不只是换 compiler path。**

14. **Developer tooling 应消费真实 build truth：clangd 来自 compile database，测试来自真实 targets，package tests来自 install tree。**

15. **优秀 CMake 的目标不是展示 CMake 技巧，而是用最少的隐式状态准确表达 C++ artifact architecture。**

---

# Part LIV · G9 Final Gate

完成 G9 后，应能闭卷回答：

## Build Model

1. CMake、Ninja、Clang 分别做什么？
2. 什么是 artifact graph？
3. Source/Build/Install Tree 为什么必须区分？

## Targets

1. Target 为什么是 modern CMake 核心？
2. Target property 与 usage requirement 区别是什么？
3. Interface Library 为什么可以没有 binary artifact？

## Scopes

1. `PRIVATE` 的准确含义是什么？
2. `PUBLIC` 为什么等于 implementation + interface requirement？
3. `INTERFACE` 什么场景最自然？
4. 如何从 public C++ header 推导 dependency scope？

## Language

 1. 为什么 `cxx_std_23` 比裸 `-std=c++23` 更好？
 2. public header 使用 C++23 feature 时为什么 standard requirement可能需要传播？

## Configuration

 1. Preset 与 Toolchain File 区别是什么？
 2. Single-config 与 Multi-config generator 有什么区别？
 3. 为什么不应该到处依赖 `CMAKE_BUILD_TYPE`？

## Dependencies

 1. Module-mode `find_package()` 与 Config-mode 区别？
 2. Imported Target 为什么比 `FOO_LIBRARIES` 更成熟？
 3. FetchContent 为什么不是 package manager？
 4. Conan/vcpkg 为什么最好不要污染 project target logic？

## Packaging

 1. Build成功为什么不代表 library package正确？
 2. `install(EXPORT ...)` 解决什么？
 3. `<Package>Config.cmake` 有什么作用？
 4. 为什么 installed package 必须 relocatable？
 5. `find_dependency()` 为什么对 PUBLIC dependency重要？

## Advanced Build

 1. PCH优化的是什么？
 2. Unity Build 的风险是什么？
 3. LTO为什么是跨 TU optimization？
 4. Modules 为什么要求 build-system dependency scanning？

## Tooling

 1. 为什么 clangd 要依赖 `compile_commands.json`？
 2. 为什么 sanitizer/coverage应该独立 profile？
 3. 为什么 benchmark 不应该基于 Debug/ASan build？

## Cross Compilation

 1. 什么是 Host Tool 与 Target Artifact？
 2. `try_run()` 为什么在 cross build中危险？
 3. Toolchain file 为什么必须很早读取？

## Architecture

 1. 为什么 CMakeLists越长越复杂并不意味着工程越成熟？
 2. Modern CMake 的最终目标是什么？

答案应该能够压缩成：

> **准确描述 artifacts、dependencies 和 usage requirements，然后让 toolchain/backend 自动推导命令。**

---

# Part LV · G0 → G9 的统一闭环

现在我们已经完成了一条非常完整的 native systems 链路：

```text
G0
Source → Object → Link → Load

        ↓

G1
Object / Storage / Lifetime

        ↓

G2
Ownership / RAII

        ↓

G3
Value / Copy / Move

        ↓

G4
Containers / Views / Algorithms

        ↓

G5
Templates / Compile-time Genericity

        ↓

G6
Memory / Cache / Performance

        ↓

G7
Concurrency / Memory Model

        ↓

G8
ABI / Binary Boundaries

        ↓

G9
Build / Package / Artifact Ecosystem
```

现在假设看到：

```cmake
target_link_libraries(vehicle_processor
    PUBLIC
        decoder
)
```

你不再只是问：

> “PUBLIC 语法是什么意思？”

而是应该沿整条链追：

```text
decoder 是否出现在 public C++ API？
        ↓
consumer 是否需要它的 headers/types？
        ↓
它是否成为 transitive build requirement？
        ↓
是否成为 installed package dependency？
        ↓
是否扩大 ABI surface？
        ↓
consumer toolchain 是否兼容？
```

也就是说：

> **Build System 已经不再是“项目最后补上的脚本”，而是软件 architecture 的可执行表达。**

---

# G9 完成状态

```text
G9.1   Artifact Graph / Target Model
G9.2   Usage Requirements
G9.3   PRIVATE / PUBLIC / INTERFACE
G9.4   C++23 Compile Features
G9.5   File Sets / Headers
G9.6   Presets / Build Profiles
G9.7   Toolchain / Cross Compilation
G9.8   Dependency Discovery
G9.9   Conan / vcpkg / FetchContent
G9.10  Install / Export / Package Config
G9.11  Generated Code
G9.12  C++ Modules
G9.13  PCH / Unity / LTO
G9.14  Warnings / Sanitizers / Tooling
G9.15  Testing / CTest
G9.16  Packaging / CI / Reproducibility
G9.17  Build Performance / DX
────────────────────────────────────────
G9      COMPLETE / FROZEN
```

当前官方 CMake 文档所体现的主流方向也与本章的核心模型一致：以 targets 和 usage requirements 建模 dependency relationships，使用 presets 管理 workflows，以 toolchain 描述目标环境，通过 package config/imported targets 进行依赖消费，并以 file sets 承载 headers/modules。:chatgpt-content-reference{index="20"}

---

# 下一章：G10 — Systems Runtime Project

从这里开始，**知识章节阶段基本结束**。

G10 不再主要是：

```text
“讲一个新 C++ feature”
```

而是把 G0–G9 强制组合进一个真实 C++23 systems project。

完整项目需要同时兑现：

```text
C++23
RAII
value semantics
ownership
span / ranges
templates
bounded memory
cache-aware representation
threading
bounded queues
backpressure
graceful shutdown
error model
profiling
C ABI boundary
target-based CMake
installable package
tests
sanitizers
benchmarks
```

也就是说，G10 的核心问题会从：

> **“这个机制是什么？”**

正式转成：

> **“面对一个真实系统约束，我该怎样把这些机制组合成一个可以长期维护的工程？”**

这会是整个 Modern C++ Systems Track 的第一个综合验收章。
