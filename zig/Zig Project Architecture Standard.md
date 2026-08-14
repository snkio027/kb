# Zig Project Architecture Standard

**Version:** 1.0

**Status:** Frozen Baseline

**Language Baseline:** Zig 0.16 series，语义核验基于 Zig 0.16.0

**Verified:** 2026-08-14

**Scope:** Zig Application / CLI / Library / Systems Tool / Multi-Artifact Project / Multi-Package Repository

**Purpose:** Source Organization, Semantic Boundaries, Module Architecture, Package Lifecycle, Artifact Topology, Build Graph, Testing, Naming & Evolution

---

## 0. Standard Positioning

### 0.1 Purpose

本标准不是为了定义一套“唯一正确”的 Zig 项目目录模板。

Zig 官方定义的是语言与工具链机制，例如：

- Source File Semantics；
- Compilation Model；
- Module；
- root module；
- `@import`；
- File / Declaration Discovery；
- Build System；
- Package Management；
- Naming Style；
- Testing Model。

在这些机制之上，项目仍然必须作出大量 Architecture Decision。

因此，本标准的目标是建立一套：

> **Zig-native Architecture Reasoning Model**

使项目能够明确回答：

- 一个 declaration 为什么属于这里；
- 一个 file 为什么应该存在；
- 一个 directory 表达什么语义；
- 一个 dependency 为什么跨越 Module；
- 一个 Module 为什么值得成为独立 boundary；
- 一个 Package 为什么具有独立生命周期；
- 一个 Artifact 为什么需要独立构建；
- 哪些代码实际上会进入 compilation；
- 哪些 tests 实际上会被发现和执行；
- `build.zig` 究竟拥有哪部分系统拓扑。

本标准冻结的是：

> **Architecture reasoning rules**

而不是某一棵固定目录树。

---

## 1. Authority Model

本标准严格区分 Zig 官方事实与项目工程规则。

| 标记      | Authority            | 定义                                                       |
| --------- | -------------------- | ---------------------------------------------------------- |
| **[O-S]** | Official Semantics   | Zig 官方语言、编译器、标准库或 Build System 明确定义的语义 |
| **[O-G]** | Official Guidance    | Zig 官方 Style Guide / Documentation 给出的指导性建议      |
| **[E]**   | Engineering Standard | 基于 Zig 机制推导出的本标准工程规则                        |
| **[P]**   | Project Preference   | 推荐默认值或项目结构偏好，不代表 Zig 普遍要求              |

本标准中的：

- **MUST**
- **MUST NOT**
- **SHOULD**
- **SHOULD NOT**
- **MAY**

仅表达：

> **采用本 Architecture Standard 后的工程约束强度。**

它们不意味着 Zig 编译器本身强制要求这些结构。这是本标准最重要的认识论边界。

---

## 2. Versioning Boundary

Zig 尚未进入 1.0，语言、标准库、Build System 与 Package Management 仍可能发生较大变化。

截至本标准核验日期，Zig 官方将 **0.16.0** 列为最新稳定版本。

因此：

> **本标准的 [O-S] 与 [O-G] 内容 MUST 与明确的 Zig Toolchain Baseline 绑定。**

当项目升级 Zig baseline 时：

- `[O-S]` MUST 重新核验；
- `[O-G]` MUST 重新核验；
- `[E]` SHOULD 检查其原始语义依据是否仍然成立；
- `[P]` 不因 Zig 版本变化自动获得或失去权威性。

换言之：

```text
Zig Version Upgrade
        │
        ▼
Official Semantic Delta Audit
        │
        ├── unchanged
        ├── wording update
        ├── API example update
        └── architecture implication change

```

Architecture Standard **MUST NOT** 将特定版本偶然存在的 API 误写成永恒的 Zig 架构真理。

---

## 3. Core Thesis — Explicit Architecture

Zig 项目架构不应该被简化为：

> Flat Architecture

也不应该被简化为：

> Layered Architecture

本标准采用的核心原则是：

> **Explicit Architecture**

结构必须来源于真实的软件语义和依赖压力，而不是来源于预制框架模板。

- 当 declarations 共同表达一个紧密语义能力时：**keep them together**
- 当一个 type 已经形成独立、复杂、可理解的行为边界时：**give it a coherent source file**
- 当两个子系统之间存在真正的 compilation / dependency boundary 时：**introduce a Module**
- 当一个组件拥有独立 dependency、identity、distribution 或 release lifecycle 时：**consider a Package**
- 当系统需要产生一个独立执行、链接、测试或工具产品时：**introduce an Artifact**

因此：

> **Structure follows semantic pressure.**

而不是：

> Structure follows framework convention.

---

## 4. Zig Architecture Ontology

Zig 项目不能通过一棵目录树完整描述。必须首先区分：

```text
File
Directory
Module
Package
Artifact
Build Step

```

这些对象不是同一个抽象层。本标准禁止建立如下机械映射：

```text
Directory = Module
Module    = Package
Package   = Artifact

```

也不采用这样的伪线性层级模型：

```text
Declaration
    ↓
File
    ↓
Module
    ↓
Package

```

更准确的架构模型是多个相互关联、但彼此正交的视图。

---

## 5. Seven Independent Architecture Views

成熟 Zig 项目 SHOULD 能够同时解释以下七张图。

### 5.1 Physical Source Tree

回答：**源码物理上放在哪里？**

例如：

```text
src/
├── cli/
├── engine/
├── protocol/
└── platform/

```

它表达 **Physical Organization**，而不是 **Dependency Graph**。Directory 首先解决的是定位、聚类与认知导航问题。

### 5.2 Semantic Container / Namespace View

回答：**哪些 declarations 属于同一个语义 container？**

Zig 0.16 明确定义：每个 Zig source file 隐式都是一个 `struct` declaration，文件顶层可以包含 declarations，也可以包含 fields；拥有 fields 的 source file 可以直接作为可实例化 type。

因此，`foo.zig` 并不只是“装代码的文本文件”。它本身拥有语言级 container 语义。

一个 source file 可以自然表达：

- coherent namespace；
- coherent type；
- type + closely related operations；
- domain contract；
- implementation-local semantic cluster。

### 5.3 Module Dependency Graph

回答：**哪个 compilation boundary 可以依赖哪个 boundary？**

Zig Compilation 被划分为 Modules。每个 Module 是一组 source files，其中一个是 root source file；Module 可以依赖其他 Module，并通过 module name 使用 `@import()` 导入其 root source file。官方同时明确允许 Module Dependency Graph 出现 dependency loops。

例如：

```text
CLI
 │
 ▼
Application
 │
 ├───────────┐
 ▼           ▼
Protocol   Platform

```

这是 **Compilation Dependency Architecture**，而不是目录树。

### 5.4 Declaration Discovery Graph

回答：**编译器实际上会发现并分析哪些源码和 declarations？**

Zig 不会简单递归扫描目录中的全部 `.zig` 文件。0.16 Compilation Model 明确定义 discovery rules，包括：

- 被分析的 `@import` 会发现目标 file；
- 被分析的 type/file 会进一步发现其中相关 `comptime` / `export`；
- test compilation 对 root module 中被分析 type/file 的 test declarations 有额外 discovery 行为；
- 被使用的 named declaration 才进一步进入 semantic analysis。

因此：

```text
File exists        ≠  File is discovered
Declaration exists ≠  Declaration is analyzed
Test exists        ≠  Test is necessarily part of this test compilation

```

Discovery 是 Architecture Reality 的一部分。

### 5.5 Package Dependency / Lifecycle View

回答：**哪些组件拥有独立 dependency identity 与 distribution lifecycle？**

Zig Package Management 使用 `build.zig.zon` 等机制描述 package metadata 和 dependencies；0.16 package management 继续强化了 package identity，例如 dependency override 会涉及 package `name` 与 `fingerprint`。

但是，**Package = independent lifecycle boundary** 是本标准的工程解释 **[E]**，而不是对 Zig 官方 Package 概念的穷尽性定义。

本标准用 Package 表达：

- dependency lifecycle；
- identity；
- external consumption；
- independent distribution；
- independent version/release concerns；
- independent build ownership。

Package **SHOULD NOT** 只是“更大的目录”。

### 5.6 Artifact / Product Graph

回答：**最终构建什么？**

例如：

```text
                   core
                /    |    \
               /     |     \
              ▼      ▼      ▼
            CLI    Daemon   Tests
             │       │       │
             ▼       ▼       ▼
           exe     exe     test artifact

```

Zig Build System 可以构建 executable、static/dynamic library、test compilation 等产品，并将它们放入更大的 build topology。

因此：

> **Artifact Graph MUST NOT be mechanically derived from Module Graph.**

同一个 Module 可以服务多个 Artifacts。一个 Artifact 也可以组合多个 Modules。

### 5.7 Build Step DAG

回答：**构建任务之间存在什么 dependency constraints？**

Zig Build System 将项目表示为由 Steps 构成的 Directed Acyclic Graph；无依赖的步骤可以独立、并发运行。

所以：

```text
Module Dependency Graph ≠ Build Step DAG

```

尤其重要的是：`Module Graph` 官方允许 cycle；而 `Build Step Graph` 本质上是 DAG。

因此本标准使用：

> **Build Graph gives construction dependencies and scheduling constraints.**

而不是错误地把 Build Graph 描述成一个全局线性 construction order。

---

## 6. Fundamental Distinction

整份标准建立在以下区别之上：

| Entity          | Primary Responsibility                         |
| --------------- | ---------------------------------------------- |
| **Declaration** | 最小命名语义单元                               |
| **Source File** | semantic container / namespace / type locality |
| **Directory**   | physical organization                          |
| **Module**      | compilation dependency boundary                |
| **Package**     | dependency / identity / distribution lifecycle |
| **Artifact**    | executable / linking / testing product         |
| **Build Step**  | construction dependency / task topology        |

因此：

> **Logical Architecture MUST NOT be mechanically derived from Physical Structure.**

---

## 7. The Eight Architecture Laws

### ZIG-ARCH-01 — Source Files Are Semantic Containers

**Authority:** [O-S] + [E]

Source File 不只是物理文本文件。它 SHOULD 表达：

> **one coherent type or one coherent namespace**

例如：

```zig
pub const Header = struct {
    // ...
};

pub const Message = union(enum) {
    // ...
};

pub fn encode(...) ... {
    // ...
}

pub fn decode(...) ... {
    // ...
}

```

如果这些 declarations 共同表达一个紧密的 protocol capability，就没有必要机械拆成 `Header.zig`, `Message.zig`, `Kind.zig`, `Encoder.zig`, `Decoder.zig`。只有当某个对象已经产生足够强的独立语义压力时，才 SHOULD 拆分 Source File。

### ZIG-ARCH-02 — Filesystem Hierarchy Is Not the Dependency Graph

**Authority:** [O-S] + [E]

例如：

```text
src/
├── config/
├── protocol/
├── runtime/
└── storage/

```

绝不自动意味着存在 `config module`, `protocol module`, `runtime module`, `storage module`。

Directory 提供 Physical Organization。Module 提供 Compilation Dependency。

因此：

> **Filesystem hierarchy MUST NOT be treated as the Module Graph.**

### ZIG-ARCH-03 — Modules Are Explicit Compilation Boundaries

**Authority:** [O-S] + [E]

真正的跨子系统 dependency SHOULD 通过 Module Graph 显式表达。

Module SHOULD 在出现以下 Architecture Driver 时建立：

- independent public surface；
- cross-subsystem dependency；
- dependency isolation；
- different compilation configuration；
- shared use by multiple artifacts；
- stable subsystem boundary；
- architecture topology需要在 `build.zig` 中显式表达。

Module MUST NOT 因为“这里有个目录”而自动创建。

同时必须注意：

> **Module 是 dependency boundary，不是安全边界，也不是传统 OOP 意义上的 private namespace。**

不要把 Module 神化成 Zig 并未提供的访问控制系统。

### ZIG-ARCH-04 — Packages Represent Independent Lifecycle Boundaries

**Authority:** [O-S foundation] + [E]

Package SHOULD 在组件真正出现以下压力时建立：

```text
Independent Dependency Lifecycle
+ Independent Identity
+ Independent Distribution
+ Independent Version / Release Concern
+ Independent Build Ownership

```

并不是每一个 Module 都值得成为 Package。

因此：

```text
one package + multiple modules + multiple artifacts

```

完全可以是一个成熟大型 Zig 项目的正确形态。

### ZIG-ARCH-05 — Artifacts Are Orthogonal to Modules

**Authority:** [O-S] + [E]

Module 回答：**What code depends on what code?**
Artifact 回答：**What gets built?**

例如一个 `core module` 可以同时服务 `atlas CLI`, `atlas daemon`, `unit test suite`, `integration test executable`, `code generator`。

因此：

> **Module Graph MUST NOT be derived from Artifact Graph, and Artifact Graph MUST NOT be derived from directory structure.**

### ZIG-ARCH-06 — Discovery Must Be Intentional

**Authority:** [O-S] + [E]

项目 MUST 明确理解：

```text
repository membership ≠ compilation membership

```

同样：

```text
test source exists ≠ test is discovered ≠ test artifact is executed

```

Source / Test membership SHOULD 可以从 import graph、root source files、test roots、Build Graph 清晰推理出来。

### ZIG-ARCH-07 — Structure Follows Semantic Pressure

**Authority:** [E]

本标准既不追求 **Flatness**，也不崇拜 **Layering**。正确目标是：

> **the minimum structural depth required to express real semantic boundaries**

因此：

```text
compiler/
├── frontend/
│   ├── lexer/
│   ├── parser/
│   └── ast/
├── semantic/
├── backend/
└── linker/

```

只要每一层都表达真实语义，就是合理结构。应该消灭的是 **Artificial Hierarchy**，而不是 **Hierarchy itself**。

### ZIG-ARCH-08 — Naming Must Reveal Semantics

**Authority:** [O-G] + [E]

Zig 0.16 Style Guide 明确警告在 type names 中使用过度泛化的 `Value`, `Data`, `Context`, `Manager`, `State`, `utils`, `misc`，因为这些词往往没有提供真正的分类信息。

本标准将这一原则扩展到 Architecture Naming。以下名称 SHOULD 被视为 semantic smell：

```text
utils.zig
misc.zig
helpers.zig
common.zig
managers/
contexts/

```

除非项目能够清楚解释其真正语义。例如 `utils.zig` 更可能应该成为 `checksum.zig`, `path.zig`, `encoding.zig`, `process.zig`。

命名本身就是 Architecture Design。

---

## 8. Boundary Decision Framework

结构不能按照“项目越来越大”机械升级。正确方式是根据 boundary pressure 作决定。

### 8.1 When to Create a New File?

创建新 Source File SHOULD 至少满足一项：

- 一个 coherent type 已经足够 substantial；
- 一个 namespace 已经形成独立语义；
- 当前 file 混合了多个不相关 responsibilities；
- 拆分可以明显改善 locality；
- 拆分可以形成更清晰的 semantic container。

不要默认 `one declaration = one file`，也不要无限维持 `everything.zig`。

### 8.2 When to Create a Directory?

Directory SHOULD 解决：

- physical navigation；
- semantic grouping；
- large subsystem organization；
- platform/backend grouping；
- fixtures/assets 等资源定位。

Directory 本身 **SHOULD NOT** 被认为产生 Module、Package、Public API、Artifact。创建 Directory 的理由可以只是：“这些文件在语义和认知上属于一起。”这已经足够。

### 8.3 When to Create a Module?

创建新 Module SHOULD 至少存在一个明确 driver：

- independent dependency boundary；
- independent public surface；
- dependency isolation；
- compilation configuration difference；
- multiple artifact reuse；
- architectural dependency direction；
- stable subsystem contract。

如果唯一理由是“这里已经有一个目录”，则 **SHOULD NOT** 创建 Module。

### 8.4 When to Create a Package?

Package SHOULD 解决：

- dependency lifecycle；
- package identity；
- external consumption；
- independent distribution；
- independent release/version concern；
- independent ownership。

如果一个 component 永远和主项目一起发布、使用相同 dependency policy、没有 external consumer、没有独立 ownership、不需要独立 distribution，那么它大概率只是 **Module or internal source subsystem** 而不是 Package。

### 8.5 When to Create an Artifact?

Artifact SHOULD 对应一个真正 Build Product：

```text
CLI executable
Daemon executable
Static library
Dynamic library
Test artifact
Object artifact
Code generator executable

```

不要为了某个代码目录创建 Artifact。Artifact 是 **Runtime / Linking / Testing Boundary**，不是 **Organizational Folder Boundary**。

### 8.6 When to Create a Build Step?

Build Step SHOULD 表达一个真正的 construction dependency，例如：

- compile；
- install；
- run；
- test；
- code generation；
- asset generation；
- packaging；
- verification；
- invocation of finite build tools。

不要为了“视觉上有阶段”而人为制造没有 dependency 意义的 Steps。

---

## 9. Source Organization Standard

### 9.1 File Naming

**Authority:** [O-G]

Zig Style Guide 将 source files 分成 type-like 与 namespace-like 两类：

- 文件拥有 top-level fields、表达可实例化 type 时，SHOULD 使用 `TitleCase`；
- 否则作为 namespace-like file，SHOULD 使用 `snake_case`；
- directories SHOULD 使用 `snake_case`。

官方同时明确指出这些是 general rules of thumb，有合理理由时可以偏离。
例如：

```text
Client.zig
Parser.zig
Config.zig

protocol.zig
checksum.zig
process.zig

```

### 9.2 File-as-Type

File-as-Type 是 Zig source-file struct 语义的自然使用方式，不是模仿 class。

例如：

```zig
buffer: []const u8,
position: usize,

const Parser = @This();

pub fn init(buffer: []const u8) Parser {
    return .{
        .buffer = buffer,
        .position = 0,
    };
}

```

然后：

```zig
const Parser = @import("Parser.zig");

```

这直接利用 Source File Struct，而不是人为模拟 OOP class。

---

## 10. Import Architecture

### 10.1 Local Implementation Relationship

**Authority:** [E]

同一 Module 内部的 implementation composition MAY 使用相对 source-file import：

```zig
const parser = @import("parser.zig");
const codec = @import("internal/codec.zig");

```

它表达 **local implementation relationship**。

### 10.2 Cross-Boundary Relationship

跨稳定 Architecture Boundary 时 SHOULD 优先使用 Named Module：

```zig
const protocol = @import("protocol");

```

表达 **explicit compilation dependency**。

因此应高度警惕：

```zig
@import("../../../../common/protocol.zig");

```

如果这条路径穿越了真实 architecture boundary，它意味着 **Filesystem Navigation is encoding Architecture Dependency**。

本标准规定：

> **Relative imports SHOULD remain within a coherent local implementation boundary. Cross-subsystem dependencies SHOULD normally be represented as named Module dependencies.**

这是 `[E]`，而不是 Zig 编译器的普遍代码风格要求。

---

## 11. `root.zig` Standard

### 11.1 Root Source File ≠ `root.zig`

**Authority:** [O-S] + [P]

必须严格区分 `root source file` 与 `root.zig`。

Zig Compilation 中存在特殊 root module，且 `@import("root")` 指向它的 root source file；这个文件并不必须叫 `root.zig`。

因此：

> **`root.zig` has no intrinsic language magic merely because of its filename.**

当前官方 `zig init` 会生成 `src/main.zig` 和 `src/root.zig`，说明这种 topology 是官方脚手架展示的自然默认之一，但不是语言要求。

### 11.2 Module Root as Intentional Public Surface

**Authority:** [E]

当项目选择 `root.zig` 作为 reusable Module root 时，SHOULD 将它视为：

> **Module Facade / Intentional Public Surface**

例如：

```zig
pub const Client = @import("Client.zig");
pub const Config = @import("Config.zig");

pub const protocol = @import("protocol.zig");

pub const Error = error{
    InvalidConfiguration,
    ConnectionFailed,
};

```

内部 `internal/parser.zig`, `wire.zig`, `platform_posix.zig` 不需要机械 re-export。

Module Root SHOULD 回答：**外部 consumer 被允许长期依赖什么？** 而不是：**当前目录里有哪些文件？**

因此：

> **A Module Root SHOULD expose a domain contract, not a source-file inventory.**

---

## 12. Process Boundary Standard

### 12.1 Thin `main.zig`

**Authority:** [E]

对于 Application / CLI：

> **`main.zig` SHOULD represent the process boundary.**

它通常负责：

- process entry；
- process capabilities；
- argument/environment acquisition；
- top-level I/O capability；
- allocator/resource boundary；
- fatal-error translation；
- exit semantics；
- translation from ambient process state into explicit application inputs。

它 **SHOULD NOT** 成为 CLI parsing + configuration engine + networking + storage + retry policy + protocol implementation + state machine + business workflow 的总容器。

### 12.2 Zig 0.16 Process Capability Model

Zig 0.16 引入 `std.process.Init` 作为 `main` 的可选参数，为程序提供预初始化的 allocator、arena、I/O、environment map、argv 等 process-level capabilities。

因此，本标准将传统 `main owns the allocator` 提升为更准确的：

> **`main` owns the process capability boundary.**

典型形态：

```zig
const std = @import("std");
const app = @import("app");

pub fn main(init: std.process.Init) !void {
    const args =
        try init.minimal.args.toSlice(init.arena.allocator());

    try app.run(
        init.gpa,
        init.io,
        args,
    );
}

```

核心不是特定函数签名，而是 architecture direction：

```text
OS / std.start
      │
      ▼
   main.zig
      │
      │ translate ambient process capabilities
      ▼
 Application Core

```

因此：

> **Application Core SHOULD receive explicit capabilities rather than rediscover ambient process state throughout the codebase.**

---

## 13. Public API Standard

Public API 是 Architecture Asset。Module Root SHOULD 公开 **semantic contract**，而不是 **physical implementation layout**。

警惕：

```zig
pub const parser = @import("parser.zig");
pub const lexer = @import("lexer.zig");
pub const cache = @import("cache.zig");
pub const wire = @import("wire.zig");
pub const internal = @import("internal.zig");

```

如果 consumer 最终依赖 `module internal directory topology`，那么 physical refactor 将演变成 API break。

更稳定的 surface：

```zig
pub const Client = @import("Client.zig");
pub const Config = @import("Config.zig");
pub const Request = @import("request.zig").Request;

```

**Conformance test：**

> **Can the implementation directory be reorganized without forcing consumers to change imports?**

如果答案始终是否定的，Public Boundary 可能尚未形成。

---

## 14. Dependency Architecture Standard

### 14.1 Dependency Direction Must Be Explainable

成熟项目 SHOULD 能够画出 Module Dependency Graph。

例如：

```text
CLI
 │
 ▼
Application
 │
 ├─────────────┐
 ▼             ▼
Protocol     Platform

```

Architecture Review MUST 能回答：**哪个 Module 被允许依赖哪个 Module？**，而不是：“反正文件能 import 到就行。”

### 14.2 Dependency Cycles

**Authority:** [O-S] + [E]

Zig 官方明确允许 Module dependency loops。但本标准规定：

> **Semantic ownership cycles SHOULD be avoided by default.**

如果出现 `A ↔ B`，第一步 SHOULD 检查：

- ownership 是否混乱；
- API 是否双向泄漏；
- 是否缺少共同 semantic abstraction；
- 是否应该重新划分 subsystem boundary。

可能的重构：

```text
      C
     / \
    ▼   ▼
    A   B

```

但：

> **不要机械地为了消灭 graph cycle 而制造毫无语义价值的 `shared` Module。**

如果所谓 `C` 只是垃圾桶（`common`, `utils`, `shared`），那通常只是把问题移动了位置。

### 14.3 Deliberate Root Backreferences

root module 被隐式暴露为 `@import("root")`，官方也描述了 library 读取 root declarations 以获取应用级全局配置的模式。

因此必须区分 `semantic subsystem cycle` 与 `host configuration / inversion hook`。

例如：

```text
Application Root
      │
      ▼
   Library
      │
      └──── @import("root")

```

这种关系 MAY 是有意设计的 host-provided configuration。

所以：

> **Do not mechanically equate every graph backreference with broken ownership.**

真正需要审查的是：**semantic ownership 是否循环。**

---

## 15. Build Architecture Standard

### 15.1 `build.zig` Owns Build Topology

**Authority:** [O-S] + [E]

Zig Build System 可以声明和配置 build artifacts、options、tests、generated files、system/project tools 等，并以 Step DAG 组织任务。

因此 `build.zig` SHOULD 拥有：

- Modules；
- module dependency wiring；
- Artifacts；
- targets；
- optimization configuration；
- package dependencies；
- build options；
- test compilations；
- run steps；
- code generation；
- packaging-related tasks；
- build dependency topology。

核心原则：

> **`build.zig` owns construction topology, not application semantics.**

### 15.2 Permitted Build Work

`build.zig` MAY 编排 finite、reproducible、build-related 的操作，例如：

```text
compile, generate, verify, package, run project tool, run system tool, install, test

```

官方 Build System 本身支持 generated files、system tools 与 project tools。因此本标准不是：“任何外部命令都不能放进 build.zig。”

### 15.3 Runtime Boundary

`build.zig` **SHOULD NOT** 成为以下行为的长期所有者：

- application runtime state；
- business workflow；
- production reconciliation；
- long-lived deployment control plane；
- runtime recovery policy；
- operational state machine。

例如：

```text
desired production state
      ↓
continuous reconciliation
      ↓
failure recovery

```

不属于 `Build Step DAG`。即使 Zig Build API 在技术上可以启动某些程序，也不意味着 Build System 应该拥有其运行时语义。

---

## 16. Test Architecture Standard

### 16.1 Unit Tests Near Semantics

**Authority:** [E]

默认情况下 Unit Test SHOULD 与被测试 declaration 共置。
例如：

```zig
fn decodeFrame(...) !Frame {
    // ...
}

test "decodeFrame rejects truncated header" {
    // ...
}

```

因为 unit test 测试的是 **Local Semantic Contract**，应尽可能保持 `implementation + local invariant + unit test` 的 locality。

### 16.2 Integration Tests Use Explicit Test Roots

Integration / System Tests SHOULD 使用独立 test root，例如：

```text
tests/
├── root.zig
├── integration.zig
└── fixtures/

```

然后由 Build System 显式创建相应 Test Compilation。

### 16.3 Test Discovery Must Be Explicit

Zig test discovery 依赖 Compilation Discovery，而不是递归扫描 `tests/`。官方给出的常见 discovery strategy 包括在 `test` / `comptime` block 中显式 `@import` 需要发现的源码。

例如：

```zig
test {
    _ = @import("integration.zig");
}

```

因此：

> **Test membership SHOULD be visible from the import/discovery graph.**

### 16.4 Dependency Module Tests Are Not Automatically the Root Suite

0.16 discovery rules 对 test declarations 的自动发现明确关联：**type/file 是否位于该 test compilation 的 root module。**

因此多 Module 项目 SHOULD 显式决定 `core tests`, `protocol tests`, `cli tests`, `integration tests` 分别属于哪个 Test Compilation。不要假设：“依赖 Module 里写了 test，所以 root test suite 一定自动运行它们。”

### 16.5 Test Compile ≠ Test Run

使用 Zig Build System 时，test compilation 与 test execution 是不同 Build Steps。官方明确指出：如果没有通过 `addRunArtifact` 等方式建立 Run Step dependency，仅创建 test compilation 并不会执行 tests。

因此：

```text
Test Exists → Discovered → Compiled → Run Step Exists → Executed

```

这些状态 MUST 被区分。

### 16.6 `refAllDecls` Is Not the Architecture Baseline

**Authority:** [E]

本标准不规定 `std.testing.refAllDecls(...)` 作为项目标准 test membership mechanism。

默认策略是让 membership 通过 explicit test roots、`@import`、discovery graph、Build Graph 清晰可推理。
目标是：

> **Test topology should be explicit rather than recovered from broad reflection tricks.**

特定项目 MAY 使用 `refAllDecls`，但必须知道自己希望解决的问题是什么。

---

## 17. Naming and Semantic Cohesion Standard

### 17.1 Generic Names Require Evidence

名称 `State`, `Context`, `Manager`, `Data`, `Value`, `Utils`, `Misc`, `Common`, `Helpers` 不自动禁止。

但使用它们时 SHOULD 能回答：

> What state? What context? What is actually managed? What is actually common?

例如 `State` 可能真正意味着 `Lifecycle`, `Snapshot`, `Progress`, `BootstrapStatus`, `ExecutionRecord`；而 `Manager` 可能真正意味着 `Pool`, `Scheduler`, `Registry`, `Executor`, `Repository`, `Coordinator`。命名越准确，Architecture Ownership 越清晰。

### 17.2 Avoid Ceremonial Layers

本标准不禁止 `domain/`, `application/`, `infrastructure/`, `adapters/`，也不默认推荐它们。如果问题本身确实具有这些变化边界和 dependency direction，它们完全合理。

但不要为了模仿 Clean Architecture, Hexagonal Architecture, DDD 而预先生成 `ports/`, `adapters/`, `repositories/`, `services/`, `managers/`, `contexts/`。

Architecture Boundary SHOULD 至少表达：

- independent semantics；
- independent dependency pressure；
- independent reason to change。

否则它只是 **Ceremonial Architecture**。

---

## 18. Evolution Standard — Structure Must Be Earned

项目 SHOULD 按真实 complexity 演化：

```text
Single File
    ↓
Several Semantic Files
    ↓
Intentional Public Surface
    ↓
Multiple Modules
    ↓
Multiple Artifacts
    ↓
Multiple Packages

```

这是一种可能的 evolution path，不是一条必须逐级经过的状态机。禁止：

```text
New Project → Generate Enterprise Architecture

```

抽象必须通过真实复杂性获得存在资格。

---

## 19. Reference Pattern A — Minimal Program

**Authority:** [P]

真正简单时：

```text
hello/
└── main.zig

```

已经足够。甚至不一定需要 Build System。不要为了显得专业，从第一天创建 `src/`, `internal/`, `packages/`, `modules/`, `tests/`。

---

## 20. Reference Pattern B — Small Application

**Authority:** [P]

随着第一个真实 semantic boundary 出现：

```text
project/
├── build.zig
├── build.zig.zon
└── src/
    ├── main.zig
    ├── config.zig
    └── process.zig

```

仍然完全可以只有一个 project Module。

---

## 21. Reference Pattern C — Medium Application

**Authority:** [P]

当核心逻辑需要与 process boundary 分离：

```text
project/
├── build.zig
├── build.zig.zon
│
├── src/
│   ├── main.zig
│   ├── root.zig
│   │
│   ├── Config.zig
│   ├── Engine.zig
│   │
│   ├── protocol.zig
│   ├── process.zig
│   │
│   └── platform/
│       ├── posix.zig
│       └── windows.zig
│
└── tests/
    └── root.zig

```

可能的 logical relationship：

```text
main.zig
   │
   ▼
Application Module
   │
   ▼
root.zig facade
   │
   ├── Config
   ├── Engine
   ├── protocol
   └── implementation files

```

这里所有文件名和目录都是 **Good Defaults**，不是 Zig language requirements。

---

## 22. Reference Pattern D — Multi-Artifact System

**Authority:** [P]

当同一个 Core 服务多个独立 executable：

```text
project/
├── build.zig
├── build.zig.zon
│
└── src/
    ├── core/
    │   ├── root.zig
    │   ├── Engine.zig
    │   └── protocol.zig
    │
    ├── cli/
    │   └── main.zig
    │
    └── daemon/
        └── main.zig

```

Module Graph：

```text
        core
       ▲    ▲
      /      \
     /        \
   cli       daemon

```

Artifact Graph：

```text
core
 ├── CLI executable
 ├── daemon executable
 └── test artifacts

```

Physical Tree、Module Graph、Artifact Graph 明确不同。

---

## 23. Reference Pattern E — Multi-Package Repository

**Authority:** [P]

只有出现真正 independent lifecycle 时再考虑：

```text
project/
├── packages/
│   ├── protocol/
│   │   ├── build.zig
│   │   └── build.zig.zon
│   │
│   └── engine/
│       ├── build.zig
│       └── build.zig.zon
│
└── apps/
    └── cli/

```

不要因为 `protocol/` “看起来很独立”，就立即升级为 Package。Package Boundary 是 **lifecycle decision**，而不是 **folder size decision**。

---

## 24. Consolidated Anti-Patterns

以下模式默认视为 Architecture Smell。

### AP-01 — Filesystem as Dependency Injection

```zig
@import("../../../../foo/bar.zig");

```

跨越真实 architecture boundary 时，用物理路径编码逻辑依赖。

### AP-02 — Module per Folder

```text
folder → module

```

机械一一对应。这只是重新引入 **Directory-as-Package thinking**。

### AP-03 — Package per Module

```text
module → package

```

忽略两者生命周期语义完全不同。

### AP-04 — Fat `main.zig`

Process Entry 直接拥有 storage、networking、retry、protocol、state machine、business semantics。

### AP-05 — God `root.zig`

Thin `main.zig` 不意味着：把所有实现搬进 `root.zig`。正确目标是：

```text
root.zig → Intentional Public Surface → Coherent Implementation

```

### AP-06 — Runtime Control Plane in `build.zig`

长期 operational state、runtime reconciliation 或 recovery policy 被塞进 Build Graph。

### AP-07 — Forced Flatness

因为“Zig 喜欢简单”而拒绝所有合理的 subsystem hierarchy。

### AP-08 — Ceremonial Architecture

因为某个 Architecture Pattern 流行，就提前创建没有语义压力的抽象层。

### AP-09 — Semantic Garbage Buckets

`utils`, `common`, `misc`, `helpers`, `shared` 不断吸收无法分类的逻辑。

### AP-10 — Premature Shared Module

看到 `A ↔ B` 立刻创建 `shared/`, `common/`，却没有真正发现 shared semantic contract。

---

## 25. Architecture Decision Matrix

| Question                                            | Create         | Primary Reason          |
| --------------------------------------------------- | -------------- | ----------------------- |
| 一个 type/namespace 已形成独立 cohesive semantics？ | **File**       | Semantic locality       |
| 多个 files 需要更好的物理导航？                     | **Directory**  | Physical organization   |
| 出现稳定 compilation dependency boundary？          | **Module**     | Dependency architecture |
| 出现独立 identity/distribution lifecycle？          | **Package**    | Lifecycle boundary      |
| 出现独立 executable/link/test product？             | **Artifact**   | Product boundary        |
| 构建任务之间出现明确 dependency constraint？        | **Build Step** | Construction topology   |

任何 Architecture Review 在新增结构前 SHOULD 先回答：

> **What pressure is this boundary responding to?**

如果答案只是：“这样看起来更标准”，通常不应创建该 boundary。

---

## 26. Conformance Review

Code Review / Architecture Review 不应该首先问：“这个文件应该放哪个标准目录？”，而应该按以下顺序检查。

### Semantic Ownership

1. What semantic responsibility does this declaration own?
2. Does that responsibility deserve a separate file?
3. Is the file a coherent type or namespace?

### Dependency

1. Is this relationship local implementation or cross-boundary dependency?
2. Does this boundary deserve a Module?
3. Can the Module Dependency Graph be explained?
4. Is a dependency cycle representing real semantic ownership confusion?

### Lifecycle

1. Does this component really need independent Package identity or lifecycle?

### Product

1. Is this a Module boundary or an Artifact boundary?

### Discovery & Testing

1. Will this source actually enter the Discovery Graph?
2. Will this test actually be discovered?
3. Is its Test Compilation actually executed?

### Build

1. Does `build.zig` describe construction topology or application runtime behavior?

### API

1. Can the public API survive internal directory reorganization?

### Naming

1. Does the chosen name reveal semantics or hide missing semantics?

如果这些问题都有清晰答案：**目录结构通常会自然变得正确。**

---

## 27. Conformance Levels

### Required

所有 `MUST` 和 `MUST NOT` 构成本标准的强制 Architecture Contract。

### Recommended

所有 `SHOULD` 和 `SHOULD NOT` 允许存在有理由的 deviation。但 deviation SHOULD 可以回答：

> Why is this exception architecturally better here?

### Preference

所有 `[P]` 只是 recommended baseline。例如 `src/main.zig`, `src/root.zig`, `tests/root.zig`, `platform/posix.zig` 均不构成 conformance requirement。

---

## 28. Official Semantic Traceability

| ID           | Statement                                                                                     | Authority   | Official Basis                 |
| ------------ | --------------------------------------------------------------------------------------------- | ----------- | ------------------------------ |
| ZIG-SEM-01   | Every source file is implicitly a `struct`                                                    | O-S         | Zig 0.16 Compilation Model     |
| ZIG-SEM-02   | Module has a root source file                                                                 | O-S         | Compilation Model              |
| ZIG-SEM-03   | Modules can depend on Modules by name                                                         | O-S         | Compilation Model              |
| ZIG-SEM-04   | Module dependency loops are allowed                                                           | O-S         | Compilation Model              |
| ZIG-SEM-05   | `@import("root")` refers to root module                                                       | O-S         | Compilation Model              |
| ZIG-SEM-06   | Discovery follows explicit recursive rules                                                    | O-S         | File and Declaration Discovery |
| ZIG-SEM-07   | Root-module test discovery has special semantics                                              | O-S         | File and Declaration Discovery |
| ZIG-BUILD-01 | Build System is modeled as a Step DAG                                                         | O-S         | Zig Build System               |
| ZIG-BUILD-02 | Test Compile and Test Run are distinct Steps                                                  | O-S         | Zig Build System Testing       |
| ZIG-STYLE-01 | File-as-type uses TitleCase by convention                                                     | O-G         | Style Guide                    |
| ZIG-STYLE-02 | Namespace-like files/directories use snake_case                                               | O-G         | Style Guide                    |
| ZIG-STYLE-03 | Generic names such as Manager/State/utils/misc are discouraged                                | O-G         | Style Guide                    |
| ZIG-PROC-01  | `std.process.Init` exposes process capabilities to `main`                                     | O-S/API     | Zig 0.16 Release Notes         |
| ZIG-PKG-01   | 0.16 package identity uses package metadata including name/fingerprint in override resolution | O-S/tooling | Zig 0.16 Release Notes         |
| ZIG-PREF-01  | Current `zig init` emits `src/main.zig` and `src/root.zig`                                    | O-G/example | Official Getting Started       |

这张表是 Architecture Standard 与当前 Zig 官方语义之间的 Traceability Boundary。

---

## 29. Frozen Engineering Decisions

在 Zig 0.16 baseline 下，本标准冻结以下工程结论：

```text
Thin main.zig
Intentional Module Root
Relative imports stay local by default
Named Modules express cross-subsystem dependencies
Do not create one Module per directory
Do not create one Package per Module
Unit tests live near local semantics by default
Integration tests use explicit test roots
Test membership must be intentional
Semantic dependency cycles are smells by default
Public API must not mirror file inventory
build.zig owns construction topology
Long-lived runtime semantics stay outside build.zig
Naming must reveal semantic ownership
Structure must be earned by real complexity

```

这些属于 **Architecture choices derived from Zig semantics**，而不是 Zig 语言本身的 universal requirements。

---

## 30. Final Architecture Model

成熟 Zig 项目不应该只展示 `src/` 目录树。它 SHOULD 能够同时解释：

```text
Physical Source Tree
        │
Semantic Container / Namespace View
        │
Module Dependency Graph
        │
Declaration Discovery Graph
        │
Package Dependency / Lifecycle View
        │
Artifact / Product Graph
        │
Build Step DAG

```

这些不是一张图，也不是一个机械层级。它们共同构成项目的 Architecture Model。

---

## 31. Final Manifesto

Zig 项目架构的目标不是创造最漂亮的目录树。
不是最大程度减少文件数量。
不是模仿 Java Package。
不是模仿 Go Package。
不是模仿 Rust Crate。
不是因为 Zig 强调简单就拒绝 Architecture。
也不是因为大型系统复杂，就提前制造 Enterprise Ceremony。

真正应该保持的是：

> **File gives semantic locality.**
> **Directory gives physical organization.**
> **Module gives explicit compilation dependencies.**
> **Package gives lifecycle identity.**
> **Artifact gives build products.**
> **Discovery determines compilation reality.**
> **Build DAG gives construction dependencies.**
> **Naming communicates semantic intent.**
> **Explicitness gives architecture clarity.**

---

## 32. Architecture Freeze Statement

本 Standard v1.0 最终冻结的不是：

```text
src/
├── main.zig
├── root.zig
└── ...

```

这样的目录模板。

它冻结的是以下 Architecture Reasoning Model：

> **Do not derive logical architecture mechanically from physical structure.**

在 Zig 中：

```text
File ≠ Directory ≠ Module ≠ Package ≠ Artifact ≠ Build Step

```

这些对象拥有不同职责。只有当真实语义产生新的 boundary pressure 时，结构才应该增长。

因此，本标准最终坚持：

> **Neither flatness nor layering is the Zig architecture ideal. Explicitness is.**

项目应该：

> **Start simple.**
> **Discover real boundaries.**
> **Make those boundaries explicit.**
> **Keep dependency direction explainable.**
> **Keep compilation reality observable.**
> **Stop abstracting when the semantics are already clear.**
