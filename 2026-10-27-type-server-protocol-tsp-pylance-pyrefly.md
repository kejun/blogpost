# 当类型检查器从 IDE 里被拆出来：Type Server Protocol (TSP) 深度拆解——Pylance × Pyrefly、快照语义与一场关于「协议归属权」的争论

2026 年 10 月 21 日，微软在 Python 博客上发了一篇标题相当克制的文章：《Pylance + Pyrefly: bring your preferred type checker to Visual Studio Code》。同一天，Pylance 仓库里多了一份 `docs/tsp/type-server-protocol.md`，两百来行 Markdown 加三份 schema 文件，定义了一个新协议：**Type Server Protocol（TSP）**。两天后它出现在 Hacker News 首页，178 分、132 条评论——分数不算爆，但评论区吵得异常激烈，因为这件事表面上是「VS Code 支持换类型检查器」，实质上是**把 IDE 智能层和类型分析引擎之间那条藏了五年的缝，第一次公开切开，并试图用协议把它固化下来**。

这篇文章想做的事很简单：把 TSP 的协议设计讲透（多数报道只翻译了公告），然后用工程视角判断它到底解决了什么问题、代价是什么、以及为什么 basedpyright 的维护者会用「desperate attempt」（绝望的尝试）这种词来形容它。

## 一、先把事件说清楚：谁和谁，换了什么

公告的核心信息有三层：

**第一层，Pylance 与 Pyright 解耦。** 过去五年里，VS Code 的 Python 体验（补全、悬停、跳转、环境管理）和类型检查（诊断报错）是同一个东西——Pylance 是闭源发行版，Pyright 是它的开源分析引擎，两者紧耦合。现在 Pylance 被重新定义为「Python 的 IDE 智能层」，类型检查器变成它下面一个**可插拔的静态分析组件**。Pyright 仍是默认，但不再是唯一。

**第二层，Meta 的 Pyrefly 成为第一个外部后端。** 这是一次相当罕见的合作：微软（VS Code + GitHub Copilot）与 Meta（类型分析引擎）联手。Pyrefly 是 Meta 从 2017 年起在 Instagram 级别代码库上打磨出来的检查器，官方基准是 **1.8M 行/秒**，并且他们长期在维护公开的 Python 类型检查器性能对比基准（CPU 与内存两个维度）。微软在公告里特意强调了 Meta 对生态的投入：NumPy 类型完整度接近 90%、pandas 公共 API 类型覆盖补全——这其实是在暗示一件事：**Pyrefly 在科学计算/AI 库的类型信息上，可能比 Pyright 更完整**，而 AI 库恰好是当下 Python 用户最密集的地带。

**第三层，TSP 是开标准，不是私有扩展。** 协议文档、TypeScript 接口定义、机器可读的协议模型 `tsp.json`、JSON Schema 全部放在 Pylance 的开源仓库里，语义化版本号，0.x 阶段允许 minor 版本破坏性变更。

使用路径也已经落地：Pylance 2026.4.1+，在环境里装了 Pyrefly（或 `pyrefly.toml` / `pyproject.toml` 的 `tool.pyrefly`）就会弹提示「检测到 Pyrefly，要不要用它作为诊断来源」；也可以在设置里手动选 `Python › Analysis: Diagnostics Source`，三选一：`Pylance`、`Pylance + Pyright`、`Pylance + Pyrefly`。状态栏会显示当前诊断源。

一句话总结：**编辑器前端不再绑定检查器后端，中间夹了一个协议。** 这就是 LSP 在 2016 年对编辑器做过的事，现在被下移了一层。

## 二、为什么需要新协议？因为 LSP 问不出「这个表达式是什么类型」

这是理解 TSP 最关键的一点，也是最容易被忽略的一点：**LSP 不是为类型语义设计的**。

LSP 的请求集合围绕「编辑器特性」组织：`textDocument/completion`、`textDocument/hover`、`textDocument/definition`、`textDocument/publishDiagnostics`。这些接口有个共同特征——**返回的是给人看的、为渲染优化过的内容**。

举几个具体的错配：

- `textDocument/hover` 返回的是 `MarkupContent`（Markdown 或纯文本）。你要拿类型信息，只能去解析一段渲染过的字符串。字符串是人看的，不是程序读的。
- 你想知道「第 12 行第 8 列这个表达式**推断**出来的类型是什么」，LSP 没有对应请求。hover 会给你一段 `(variable) x: int | str`，但这是 Pyright 内部格式化后的产物，粒度、结构、稳定性都不受协议约束。
- 你想批量问一万个节点的类型（比如做一个类型覆盖率统计工具、一个自动加注解工具、一个 Agent 的代码理解层），LSP 的模型完全不支持：没有批次语义、没有一致性快照、没有并发读通道。

TSP 的设计就是围绕这三个痛点展开的。它是 **JSON-RPC 协议，复用 LSP 的传输层和数据形状**（`Position`、`Range`、URI 用字符串、行 0-based、字符偏移 0-based UTF-16 code unit），但请求全部走 `typeServer/` 前缀，语义完全不同。

从「上下文」角度看，这是 LSP 生态里一个反复出现的模式：**LSP 变成了一个壳，真正的语义能力都塞在 `experimental` 里**。TSP 的选择是诚实地承认这一点，另起一个协议，但共享传输层——好处是任何 LSP 客户端基础设施（stdio、JSON-RPC 框架、文档同步）都能直接复用，实现成本被压到很低。

## 三、协议解剖：七个请求撑起一整个类型服务

TSP 的请求集合小得令人意外。完整列表如下：

| 消息 | 方向 | 作用 |
|------|------|------|
| `typeServer/getSupportedProtocolVersion` | client → server | 返回 semver，做兼容性检查 |
| `typeServer/getSnapshot` | client → server | 取当前分析快照 ID（非负整数） |
| `typeServer/snapshotChanged` | server → client | 通知快照推进 `{old, new}` |
| `typeServer/connection` | client → server | 多连接控制 `{type: open\|close, kind, args}` |
| `typeServer/getPythonSearchPaths` | client → server | 给定 `fromUri` 返回搜索路径 |
| `typeServer/resolveImport` | client → server | 把 import 描述符解析成文件 URI |
| `typeServer/getComputedType` | client → server | 流敏感推断类型 |
| `typeServer/getDeclaredType` | client → server | 源码里显式写的类型 |
| `typeServer/getExpectedType` | client → server | 上下文期望类型 |

七个请求、一个通知、一个控制消息，就这样。对比 LSP 上百个方法，这个规模是有意为之——文档里明确写了「The current protocol is intentionally small」。

### 3.1 三种类型查询的区别，值得单独讲

这是整个协议里最有设计感的部分。同一个节点，TSP 能给你三个不同的答案：

```python
def foo(a: int | str) -> None: ...

x = 1
y = x + 1        # getComputedType(y 的 rhs) → int
foo(4)           # getExpectedType(实参 4)      → int | str
                 # getDeclaredType(foo 的参数 a) → int | str
```

- **Computed**：基于控制流推断出来的。`isinstance` 窄化之后，`a` 的 computed type 就是 `int`。
- **Declared**：源码里写死的注解。`a` 的 declared type 永远是 `int | str`。
- **Expected**：外部上下文对这个位置的期待。这决定了「把 `4` 换成 `"4"` 会不会报错」。

把三者分开，是**类型工具链能做对事的前提**。举个真实场景：自动补注解工具必须用 computed 类型（因为你想要的是「实际推断结果」，不是「用户可能已经写错的东西」），但如果要把注解写进源码，你得先确保这个推断结果**在语法上可表达**——`int | str` 可以，某个内部合成的 `Synthesized` 类型不行。而类型驱动的重构工具（比如"把参数类型收窄"）需要 declared 和 expected 两端对照，才能判断改动是否破坏调用点。

LSP 的 hover 把这三个概念压成一段字符串，正是过去所有类型相关工具都只能靠正则和猜测的原因。

### 3.2 快照（snapshot）：整个协议的正确性基石

TSP 用「快照」这个概念替代了 LSP 的隐式一致性假设。规则很硬：

- 快照是一个非负整数，**只增不减**；
- 任何可能让已返回结果失效的事件（打开/关闭文件、编辑、配置变更、watched file 变更、依赖变化、缓存重置）都必须推进快照；
- 每个类型对象、handle、符号都**绑定在产生它的那个快照上**，跨快照比较没有意义；
- 请求带过期快照 → 服务端返回 JSON-RPC 错误码 **-32802（ServerCancelled）**，客户端应当取新快照后重试。

这套设计直接对应一个真实痛点：**异步编辑下的类型撕裂**。用户打字时，分析线程还在处理上一个版本的文档；如果此时 IDE 拿旧的分析结果去渲染新的 AST，就会出现「悬停显示的类型属于三行之前的代码」。LSP 对此没有明确答案，各家实现自己加 debounce、自己丢结果。TSP 把它变成了协议里的一等公民——快照不是优化，是语义。

值得注意的是 `-32802` 的选择：它原本是 LSP 里表示「服务端主动取消请求」的码，TSP 借用它表达「你的快照太旧，重试即可」。这个语义漂移是个小的技术债——错误码复用会让客户端的错误处理逻辑变得模糊（取消和过期在语义上并不相同），文档里也承认这是「preferred」而非专用码。

### 3.3 类型载荷：9 种 kind 和一个刻意留白的 schema

类型结果是 JSON 可序列化的 tagged object，靠数字 `kind` 判别：

| kind | 类型 | 说明 |
|------|------|------|
| 0 | BuiltIn | `unknown`/`any`/`unbound`/`ellipsis`/`never` 等 |
| 1 | Declared | 源码声明类型的基类 |
| 2 | Function | `def` 定义的函数与方法 |
| 3 | Class | 类与其实例 |
| 4 | Union | `int \| str \| None` |
| 5 | Module | `import os` 得到的模块对象 |
| 6 | TypeVar | `T`/`P`/`Ts` |
| 7 | Overloaded | 多个 `@overload` 签名 |
| 8 | Synthesized | 类型检查器合成、无源码节点的类型 |
| 9 | TypeReference | 按 id 引用同响应内的其他类型，用于去重与环 |

关键细节有三个。**第一，TypeReference + id 是为递归类型准备的**：一个自引用的类如果不做引用化，序列化会直接爆栈；id 只在单个响应图内有效，不是全局身份。**第二，`Overloaded` 是单独一类而不是数组**，因为重载决议的结果依赖调用点，客户端需要看到完整签名集合才能自己判断。**第三，`Synthesized` 显式承认了「有些类型在源码里写不出来」**——这是类型工具必须面对的现实，也是 TSP 比 hover 字符串诚实的地方。

但这里也藏着 basedpyright 攻击的靶子：整个 Type union 是**为 Python 的类型系统量身定制的**，没有 rank-N/forall 的表示，没有 effect row，没有 refinement 类型的位置。「声明一个通用协议，却把载荷定义成一个语言的 AST 投影」——这确实让「TSP 能否跨语言」这个问题变得可疑。

### 3.4 多连接：把读请求从单条 JSON-RPC 管道里解放出来

TSP 0.4.1 引入了可选的多连接模式，是整个协议里工程味最重的一块。

问题很实际：JSON-RPC over stdio 是**单管道串行**的。一个 Agent 或后台工具发起几千次 `getComputedType`，会把主连接堵死，连带阻塞文档同步和诊断推送——编辑器表现为「卡一下」。LSP 生态里这被称为 head-of-line blocking，各家靠请求优先级、批量接口、或者干脆开第二个进程来绕。

TSP 的答案是：主连接**独占可变状态**（LSP 生命周期、workspace/配置/文件 watcher/文档同步、`snapshotChanged`、`typeServer/connection` 控制消息），额外连接**只读**，通过 `typeServer/connection` 带 `ipc` 端点开通道。协商走 LSP `initialize` 的 `capabilities.experimental.typeServerMultiConnection.supportedTransports`，双方列表有交集才启用；不支持时必须仍能单连接正确工作。额外连接上只允许 0.4.1 定义的那七类读请求，收到 LSP 流量或状态变更**必须拒绝**。

这套「单写多读」的划分是干净的：它把并发模型显式化，而不是让客户端猜。代价是 `ipc` 目前是唯一内建传输——意味着 Windows 命名管道、Unix domain socket、以及跨容器的场景都得各自适配，"可移植的开标准"在这里打了折扣。

## 四、最小可用客户端：三十行看出协议的形状

理解协议最快的方式是写一个能跑的客户端。下面这段假设有一个实现了 TSP 的类型服务器（`pyright-typeserver --stdio`，或 Pyrefly 的对应可执行文件）：

```ts
import { spawn } from "node:child_process";

const srv = spawn("pyright-typeserver", ["--stdio"]);
const pending = new Map<number, (v: any) => void>();
let id = 0;

// 极简 JSON-RPC over stdio：Content-Length 分帧
let buf = Buffer.alloc(0);
srv.stdout.on("data", (chunk) => {
  buf = Buffer.concat([buf, chunk]);
  for (;;) {
    const sep = buf.indexOf("\r\n\r\n");
    if (sep < 0) return;
    const len = Number(/Content-Length: (\d+)/.exec(buf.subarray(0, sep).toString())![1]);
    if (buf.length < sep + 4 + len) return;
    const msg = JSON.parse(buf.subarray(sep + 4, sep + 4 + len).toString());
    buf = buf.subarray(sep + 4 + len);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)!(msg); pending.delete(msg.id); }
    if (msg.method === "typeServer/snapshotChanged") console.log("snapshot →", msg.params.new);
  }
});

const send = (method: string, params?: any) =>
  new Promise<any>((res) => {
    const mid = ++id;
    pending.set(mid, res);
    const body = JSON.stringify({ jsonrpc: "2.0", id: mid, method, params });
    srv.stdin.write(`Content-Length: ${Buffer.byteLength(body)}\r\n\r\n${body}`);
  });

// 1) 版本协商
const { result: ver } = await send("typeServer/getSupportedProtocolVersion");
// 2) 走正常 LSP initialize + didOpen 喂状态
// 3) 取快照 → 查类型
const { result: snap } = await send("typeServer/getSnapshot");
const { result: t, error } = await send("typeServer/getComputedType", {
  arg: { uri: "file:///proj/app.py", range: { start: { line: 11, character: 8 }, end: { line: 11, character: 9 } } },
  snapshot: snap,
});
if (error?.code === -32802) { /* 快照过期：重新 getSnapshot 后重试 */ }
```

真正值得注意的是那些**没有出现**的东西：没有方法让你「问一个类型的字符串表示」，没有批量接口，没有「这个文件有哪些错误」。TSP 严格限定在「语义原语」上——类型、导入、搜索路径。诊断（diagnostics）依然走 LSP 的 `publishDiagnostics`。这个边界划得很聪明：诊断是编辑器 UI 的事，类型是程序的事，混在一起就是过去五年的状态。

## 五、为什么是现在？Agent 是那个没写进协议名的需求方

公告里有一句话很关键，藏在第二段：「a great type checking experience … as the bedrock of **static semantic intelligence for software agents**」。

这句不是公关辞令。回想一下 2026 年 Agent 写代码的实际瓶颈：不是生成，是**验证**。模型生成一段 Python，最便宜的验证方式是跑测试（慢、覆盖不全、有副作用），次便宜的是类型检查（快、纯静态、但输出是给人看的字符串）。当 Agent 想「我知道这个变量是 `DataFrame | None`，所以下一行该加个 `if x is not None`」，它需要的是结构化类型，不是 hover 里那句 `(variable) x: DataFrame | None`。

这也解释了 Pylance 在 TSP 里的定位：公告明确列了它给 Copilot 提供的东西——补全上下文、Chat 的代码理解、**面向 Python 代码库的 MCP 工具**。换句话说，TSP 是给「Copilot 的 Python 语义层」换发动机，而这台发动机未来的客户不只是 VS Code 的悬停提示，还有 Agent 工具链。

把 TSP 放进 2026 年的协议栈里看，层次就清楚了：

- **LSP** — 编辑器 ↔ 语言服务（补全、跳转、诊断）
- **DAP** — 编辑器 ↔ 调试器
- **MCP** — Agent ↔ 工具/数据源
- **TSP** — 工具/Agent ↔ 类型检查器（结构化语义）

每加一层，都是把一个原本藏在实现内部的接口暴露成契约。TSP 是这条路上最新的一块，也是最窄的一块——窄到只有七个请求，窄到只服务 Python。

## 六、争议：一个「开放标准」的归属权问题

HN 评论区最热的两条批评，都不是技术细节，而是政治：

**命名。** 「Type Server Protocol」是个通名，却只支持 Python。有人吐槽这是「mining the generic protocol namespace」，甚至翻出微软当年把 Web 框架叫「MVC」的旧账。这个批评看似鸡毛，实则有分量：协议命名决定了生态位的想象空间。叫 TSP，其他语言的实现者会犹豫——我实现的是「Type Server Protocol」还是「Python 类型服务的仿制品」？

**动机。** basedpyright 的文档写得毫不客气：

> 「type server protocol」是微软为了防止 Pylance 变得过时而做的绝望尝试——把类型检查外包给 basedpyright、ty、pyrefly 这类语言服务器，同时继续把某些语言服务器功能独占在 Pylance 里。这个协议除了微软不惠及任何人。它给任何选择支持它的语言服务器增加了不必要的复杂度。basedpyright 不支持，并强烈建议其他语言服务器也不要支持。

这段话的锋利之处在于它承认了一个事实：**TSP 确实把「检查器」商品化了**。检查器变成可替换的后端 → 竞争压到性能和类型完整度上 → Pylance 靠 Copilot 集成、环境管理、MCP 工具这些「上层」留住用户。对微软是防御性布局，对 Pyrefly/ty 是渠道，对 basedpyright 这类「自己就是完整语言服务器」的项目则是**降级**：从「一个可独立安装的 LSP 服务端」变成「Pylance 的一个插件后端」，功能边界由别人定。

但生态的反应比批评更说明问题：**Astral 的 ty 表态会支持 TSP**（ruff 仓库 discussion #23432），Pyrefly 已经是第一个实现。也就是说，主要商业玩家都接了。这不是因为协议优雅，而是因为 VS Code 的渠道太重要——**在分发面前，协议洁癖是奢侈品**。

技术上还有几条批评值得记录：

- **UTF-16 位置编码被继承下来**。有人惋惜「新协议是纠正这个错误决定的机会」。但客观说，TSP 复用 LSP 的 `Position` 语义是为了让客户端零成本接入（同一个文档同步、同一套坐标转换），改 UTF-8 会让所有现成 LSP 基础设施失效。这是典型的「一致性 > 正确性」权衡，而且文档明确要求：如果服务端内部用别的编码，**必须在协议边界转换**，并警告转换错误会导致客户端问错语法节点。
- **内存**。「现在我要同时养一个 TSP 和一个 LSP，吃两份内存？」这个担忧对 Pyright 场景不成立（同一进程内共享 analyzer/binder/evaluator 与 `vscode-languageserver` 实例，`pyright-typeserver` 只是 `pyright-internal` 的薄打包壳），但对「Pylance + 第三方检查器」成立：两个进程、两份 AST、两份索引。Pyrefly 的内存优势（官方基准里的重点项）在这里变成了决定性因素。
- **Python 专属的载荷**。没有 forall、没有 rank-N，`Type` union 是 CPython 类型系统的镜像。所谓「其他动态语言也能用」的辩护（PHP/Ruby/Erlang）在 schema 层面站不住——它们可以复用 JSON-RPC 骨架，但载荷要重写，那就不叫同一个协议了。

## 七、判断：这是基础设施，不是产品

我的看法是：**TSP 的价值不在协议本身有多好，而在于它把「类型语义」从编辑器 UI 里剥离出来这件事，第一次有了公开契约。**

打分的话：

- **设计（8/10）**：快照语义、三态类型查询、单写多读连接，这三件事都是踩过坑才会想到的。协议小是优点，`intentionally small` 是这份文档里最自信的一句。
- **通用性（4/10）**：命名和载荷都锁死在 Python。它更像是「Python Type Server Protocol」，只是没好意思写全。
- **生态时机（7/10）**：微软 + Meta + Astral 三家同时在场，这在 Python 工具链史上不常见。但 basedpyright 的公开反对说明社区并不统一，而协议 0.x 阶段的破坏性变更条款（minor 可破坏）意味着**现在押注它有风险**。
- **对 Agent 的意义（9/10）**：这是我最看重的部分。过去 Agent 读代码只能靠 grep + AST + 一遍遍跑测试；有了 TSP，一个 Agent 可以在 100ms 内拿到一万个节点的结构化类型，用它做约束求解、做补丁验证、做「这个改动会不会破坏类型契约」的前置判断。这比再多一层 prompt 有用得多。

实践建议，分三类人：

**如果你只是用 VS Code 写 Python**：暂时不用动。Pyright 仍是默认，Pyrefly 是「你想试就试」的选项。建议在**大仓库 + 重科学计算依赖**的项目里试一次 Pyrefly——1.8M 行/秒和更完整的 NumPy/pandas 类型是它最实在的两个卖点，切换成本是状态栏点一下。

**如果你在写工具（linter、codemod、类型覆盖率统计、Agent 的代码理解层）**：现在就该看 TSP，但**别把它当成稳定依赖**。0.x 的 minor 版本可能破坏兼容，做好版本探测（`getSupportedProtocolVersion`）和降级路径（回退到 CLI + JSON 输出）。好消息是这个协议足够小，抽象一层适配器的工作量大概是一天。

**如果你在维护一个语言服务器**：basedpyright 的反对有道理，但拒绝的代价是放弃 VS Code 这个最大分发渠道。更现实的策略是**双轨**：保留完整 LSP 服务端，同时提供一个薄 TSP 后端——注意 Pyright 的做法，把所有实现放在 `pyright-internal/src/typeServer/`，`pyright-typeserver` 只是一个打包壳，共享同一份 analyzer，这样维护成本接近于零。

最后说一个预测。TSP 让我想起 2016 年的 LSP：当时也没人相信所有编辑器会共用一个协议，结果五年内它成了默认。区别在于，LSP 解决的是「M 个编辑器 × N 个语言」的乘法问题，而 TSP 解决的是「1 个 IDE × N 个检查器」——规模小一个数量级，所以它的天花板也更低。它大概率不会成为跨语言标准，但很可能成为**Python 类型工具的事实接口**，并且在 Agent 工具链里被大量非 IDE 场景复用。

真正值得盯的信号不是协议文档，而是两件事：**第一，Pyrefly 通过 Pylance 的实际体验是否真的比 Pyright 快且准**（公告里的基准是 Meta 自己发的，需要第三方验证）；**第二，TSP 是否会走出 VS Code**——如果 Neovim、Zed、JetBrains 里出现独立的 TSP 客户端，那它就真的成了协议；如果一年后只有 Pylance 一家在用，那 basedpyright 那句「只惠及微软」就成了预言。

在那之前，这份两百行的 Markdown 至少证明了一件事：**把 IDE 里那些「理所当然和编辑器长在一起」的能力，一块一块拆成协议，是 2026 年开发者工具演进的主线。** TSP 只是最新的一块拼图。

---

**参考来源**

- Microsoft Python Blog, *Pylance + Pyrefly: bring your preferred type checker to Visual Studio Code*, 2026-10-21
- microsoft/pylance-release, `docs/tsp/type-server-protocol.md`（协议正文，对齐 Pylance 2026.4.1）
- pyrefly.org, *Pyrefly + Pylance* 及 *Speed and Memory Comparison* 基准
- basedpyright docs, *Pyright Type Server*（反对立场原文）
- Hacker News, *Type Server Protocol*, 2026-10-26，178 分 / 132 评论
