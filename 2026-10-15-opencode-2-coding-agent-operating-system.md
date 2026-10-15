# 当编码 Agent 变成一个操作系统：OpenCode 2.0 深度拆解——常驻服务、Code Mode 与 80+ 内部插件

> **日期**：2026 年 10 月 15 日
> **主题**：AI Agent / 开发者工具
> **关键词**：OpenCode 2.0、Coding Agent、Code Mode、MCP、Agent Harness、Client/Server

---

2026 年 10 月 14 日，GitHub 上星标数已经超过 **21.3 万** 的开源编码 Agent 项目 OpenCode（`anomalyco/opencode`）发布了 **2.0 大版本**。官方博客用一句话概括这次更新：「这是一次彻底的翻修（major overhaul），它汲取了数百万日活用户的经验，交付一个能适配 Agent 所需一切的体系。」

如果只是"又一个 CLI Agent 出新版"，并不值得写一篇深度分析。但 OpenCode 2.0 的野心明显不同：它没有停留在"加几个新工具、换个 UI"，而是把整个产品**从"一个命令行程序"重构成了"一个常驻服务 + 多客户端 + 内部插件体系 + 可嵌入 SDK"** 的结构。

换句话说：**OpenCode 正在把自己做成 Agent 时代的操作系统。**

本文基于官方发布说明、`@opencode/client` 与 `@opencode/codemode` 的公开接口，以及 Code Mode 这一概念的原始出处，逐层拆解这次重写的技术选型、工程权衡，以及它对"编码 Agent 该长什么样"这一问题的回答。

## 一、先看全景：2.0 到底改了什么

在深入细节之前，先给出一张"改动地图"。下表是官方发布的 2.0 面向用户的主要变化，以及本文后续会展开分析的位置：

| 变化 | 一句话描述 | 本文分析章节 |
|------|-----------|-------------|
| **The Service** | 后台自动运行单一常驻进程，TUI/Web/桌面端共享 | 第二节 |
| **The API** | 从零重写，支持"Agent 调用自己的 API" | 第三节 |
| **Code Mode** | 内置最小 JS 解释器，把 MCP/OpenAPI 变成可组合函数 | 第四节 |
| **Background Tasks** | 后台子 Agent + 后台 shell 命令，`ctrl+b` 转后台 | 第五节 |
| **Plugins** | 80+ 内部插件，TUI 插件转正，全链路热重载 | 第六节 |
| **The SDK** | 可作为库嵌入，跑在 Durable Objects 等环境 | 第七节 |
| **Upgrading** | 1.0 插件不兼容、Server API 完全不同 | 第八节 |

这七项里，真正的"结构性变化"是前三项——**服务化、API 重写、Code Mode**。后面几项（后台任务、插件、SDK）本质上是"服务化 + 新 API"带来的自然结果：一旦 Agent 变成了一个可被编程调用的服务，把能力暴露成插件、库、后台任务就成了顺水推舟的事。

## 二、The Service：从"每次启动一个进程"到"机器上永远有一个 Agent"

OpenCode 从第一版开始就采用了 **client/server 模型**。但官方坦诚地说：这个模型「默认并没有被利用起来，主要只有高级用户在用」。

2.0 的核心改变，是把这个 server **默认常驻化**：

> 在 2.0 中，这个 server 现在会自动作为你机器上的**单个后台进程**运行。当你打开 TUI、Web 界面或桌面应用时，它们都在和同一个中心进程通信。

这看似只是"启停策略"的变化，实际影响却是架构级的。它带来三个直接后果：

1. **多前端共享同一会话状态**。TUI 里开的一个 session，可以在 Web 界面里继续看，桌面 App 也能接管——因为它们读写的是同一份服务端状态，而不是各自内存里的副本。
2. **编程客户端"零配置发现服务"**。使用 `@opencode/client` 写脚本时，客户端会**自动发现本地服务**并直接工作。官方特别点名了它的用途：「对定时任务（scheduled tasks）特别有用。」
3. **可被配对（pair）到其他主机**。通过 `/pair` 或 `opencode pair`，你可以把服务暴露给其他主机，让别的应用连上来。官方提到"利用这个流程的原生应用正在开发中"。

这里的关键词是 **pair**。它意味着 OpenCode 不再假设"Agent 和用户在同一台机器、同一个终端里"。服务可以被远程配对，客户端可以是任意形态——这正是"操作系统"隐喻的来源：**内核（service）与外壳（TUI/Web/App）解耦，通过稳定协议通信。**

从工程角度看，这是一个典型的"从单体到 C/S"的演进，但发生在一个 Agent 产品上，意义不同。传统的 C/S 拆分是为了多端复用；Agent 的 C/S 拆分，是为了让 **Agent 的状态（会话、上下文、后台任务）成为可持久、可远程访问的一等公民**。当 Agent 能跑一整天、跨多个前端、被脚本调度时，"常驻服务"几乎是必然选择。

## 三、The API：让 Agent 学会调用它自己的 API

官方对旧 API 的评价非常直白：

> 旧 API 是随着我们和整个世界一起摸索"Agent 是什么、应该是什么"而**杂乱生长**出来的。它很糟糕。

于是 2.0 选择**从零重写 API**，并声称"现在几乎支持你需要做的一切"。但真正有意思的不是"重写"本身，而是重写后暴露出的一个设计模式：

> OpenCode 也能感知自己的 API，并会调用它来做一些有用的事，比如在开始新工作时把当前会话移动到一个 git worktree 里。

这句话值得反复读。它描述的是一种 **self-hosting（自举）** 的架构：**产品内部的操作，和外部客户端能做的操作，走的是同一套 API。**

举例来说，当用户说"在一个新的 worktree 里开始限流上传的工作"时，Agent 实际执行的是：

```
execute { code }
  › opencode.worktree_create  [name=rate-limit]
  › opencode.session_rename   [title=Rate limit uploads]
  › opencode.session_move     [directory=~/worktrees/rate-limit]
```

再比如一个更复杂的清理任务：「那个 flaky test 的会话卡住了。停掉它，让它把测试隔离掉，然后关掉我已经看完的标签页。」

```
execute { code }
  › opencode.session_list
  › opencode.session_context  [sessionID=ses_7c41e09a]
      └ "Retrying uploads.test.ts again…"
  › opencode.session_interrupt [sessionID=ses_7c41e09a]
  › opencode.session_prompt    [sessionID=ses_7c41e09a, text=Quarantine uploads.test.ts]
  › opencode.tab_close         [sessionID=ses_2f9d61b4]
```

注意这几段不是"伪代码示意"——它们是 **Code Mode** 里 Agent 真实执行的脚本（第四、五节会展开）。这里先记住结论：**Agent 通过 API 操作自己，去管理其他会话、标签页、worktree。**

这是一种极有想象力的自我管理能力。它把"人管理 Agent"变成了"Agent 管理 Agent（会话）"。当你有几十个并行会话时，让一个 Agent 去"停掉卡住的、隔离失败的、关闭已完成的"，比人类手动切标签页高效得多。

配套地，2.0 发布了新的客户端包 `@opencode/client`，同时提供 **vanilla JavaScript** 与 **Effect** 两套客户端：

```ts
// review.ts
import { OpenCode } from "@opencode/client"
import { Service } from "@opencode/client/service"

const endpoint = await Service.ensure()
const client = OpenCode.make({
  baseUrl: endpoint.url,
  headers: Service.headers(endpoint),
})

const session = await client.session.create({
  location: { directory: process.cwd() },
})

await client.session.prompt({
  sessionID: session.id,
  text: "Review the current changes",
})
```

短短十几行，展示了 2.0 的开发者体验目标：**`Service.ensure()` 负责发现/拉起服务，`OpenCode.make()` 负责构造客户端，之后一切皆 `client.xxx()`。** 一个外部脚本可以在几秒内获得一个完整的、具备全部 Agent 能力的编程接口。

而"同时提供 Effect 客户端"这一细节，透露出团队的技术品味：Effect 是一个以类型安全、结构化并发、可组合错误处理著称的 TypeScript 库。为 Agent 服务同时提供 **Promise 风格**与 **Effect 风格** API，意味着他们既照顾了"随手写个脚本"的轻量场景，也为"构建生产级、需要精细控制并发与重试的自动化流水线"预留了抽象。

到这里，"操作系统"的轮廓已经很清晰了：**有内核（service），有系统调用（自举 API），有 SDK（libc）。**

## 四、Code Mode：把 MCP 从"逐个调用"变成"一段脚本"

如果说 2.0 里最值得深挖的一项，那一定是 **Code Mode**。官方毫不掩饰偏爱：

> 模型热爱写代码，而 OpenCode 2.0 比任何其他编码 Agent 都更充分地利用了这一点。我们在 `@opencode/codemode` 包里构建了一个**最小的 JavaScript 解释器**。

要理解它的价值，需要先理解它要解决的问题。

### 4.1 背景：MCP 的"上下文膨胀"病

关于 "Code Mode" 这个概念，Armin Ronacher 在 2026 年 10 月 6 日的文章《What is Codemode》里给出了权威定义（本仓库已有[译文](2026-10-06-what-is-codemode.md)）：

> Codemode 基本上只是一种**从某种语言内部发出工具调用**的方式。这样你就可以组合这些调用，而不必让它们都经过 LLM 的 context。

他举了一个非常直观的对比：如果 agent 想对一批 GitHub issue 做操作，传统方式是**逐个工具调用**——每次调用都要把工具定义、参数、返回结果塞进上下文；而走 Code Mode，agent 写一段脚本，**在 harness 这一侧**把调用逻辑跑完，只把最终结果带回上下文：

> 如果你在 LLM 里以普通工具调用的方式发出一个 bash 调用，我们只会把末尾 2000 行塞进 context……但如果 agent 通过 Codemode 发出这个调用，Codemode 这一侧会以结构化的方式拿到更大的输出。

这就是问题的核心：**MCP 的价值是"让 Agent 认识外部世界的工具"，但代价是每个工具的 schema 和每次调用的中间结果都在蚕食有限的上下文窗口。** 装十个 MCP server，上下文就先被工具定义吃掉一大块；调用时产生 50 条中间结果，又吃掉一块。

### 4.2 OpenCode 2.0 的实现

OpenCode 2.0 的 Code Mode 做成了一件事：**把 MCP server 和 OpenAPI endpoint 自动转换成函数，让 Agent 写一段脚本一次跑完。**

> 这个包会摄取 MCP server 或 OpenAPI endpoint，把它们转换成函数，让 agent 可以在脚本里调用。它能**原生地（natively）运行这些脚本，而无需 Node.js VM 的复杂性，也不用嵌入 QuickJS 这类复杂方案**。

这段话里隐藏着两个重要的工程决策：

**决策一：不用 Node VM，也不用 QuickJS。** QuickJS 是嵌入式 JS 引擎的常见选择，但需要额外的 WASM 运行时、内存管理和桥接层。OpenCode 选择自研"最小 JS 解释器"，说明他们评估后认为**只需要 JS 的一个子集**——足够 Agent 表达"调用工具、对结果做 map、再调用另一个工具"这类组合逻辑即可。这是一个典型的"够用就好"的取舍：牺牲完整的语言能力，换来部署简单、启动快、无额外运行时依赖。

**决策二：默认全量 opted-in。** 官方原话：

> 2.0 中所有 MCP server 默认加入 code mode。这意味着你可以添加**上千个** MCP server，而上下文膨胀极小，你的 agent 会发现并组合它们来完成任务。

这是整篇发布说明里最激进的一句话。传统做法下，装上百个 MCP server 是不可想象的（上下文会被工具定义淹没）。Code Mode 改变了这个成本结构：**工具不再以"定义"的形式常驻上下文，而是以"可搜索的函数"的形式按需发现。** Agent 先写一句 `search({ query: "create linear issue" })`，再使用找到的函数——只在需要时才把相关函数拉进来。

### 4.3 一个真实的组合案例

官方给出的例子是「在 Linear 里登记 GitHub 上的 bug」：

```js
// Code Mode 脚本
const { issues } = await tools.github.list_issues({
  owner: "anomalyco",
  repo: "opencode",
  labels: ["bug"],
  state: "OPEN",
})

const filed = await Promise.all(
  issues.map(({ title }) =>
    tools.linear.save_issue({ team: "OC", title })
  )
)

return filed.map(issue => issue.identifier)
```

请仔细体会这段脚本相比"传统 Agent 循环"的差异：

| 维度 | 传统工具调用循环 | Code Mode 脚本 |
|------|-----------------|----------------|
| 上下文占用 | 每个 issue 的标题/ID 往返一次，全部进 context | 只有最终 `identifiers` 数组回传 |
| 往返次数 | 与 issue 数量线性相关（可能几十次） | **单次 round trip** |
| 并发 | 受限于模型逐步决策 | `Promise.all` 原生并发 |
| 中间数据 | 必须可见（否则模型无法决策） | 留在 Code Mode 沙箱内 |

官方对最后一点总结得很精炼：**「让你 agent 写脚本，去调用一个工具、对结果做 map、再调用另一个工具——单次往返，而不是一个一个地调。」**

这正是 Code Mode 的"飞轮"：模型越擅长写代码（当前前沿模型的趋势如此），这种"用代码编排工具"的方式就越自然、越高效。

### 4.4 与 Pi/Armin 方案的关键差异

把 OpenCode 2.0 与 Armin 在 Pi 里的 Codemode 对比，会看到同一个思想的不同落地：

- **Pi** 把 Codemode 跑在 **WASM 里的 QuickJS** 中，刻意限制"没有网络、没有文件系统、没有 timer、内存有限"，只留"调用更多工具"这一个出口——强调**隔离与安全边界**。
- **OpenCode 2.0** 则自研最小 JS 解释器，强调**"无需 VM 复杂性和 QuickJS 这类嵌入方案"**，把重点放在**部署轻量与 MCP/OpenAPI 的自动摄取**上。

两者都认同核心命题——"让 LLM 在 harness 侧表达和编排复杂操作，而不是在 execution environment 侧"；区别在于对**沙箱强度 vs. 工程复杂度**的不同权衡。这个分歧本身值得关注：随着 Code Mode 成为主流，业界会围绕"解释器该多重、沙箱该多严"形成不同的技术流派。

## 五、Background Tasks：让"编排能力"真正兑现

官方的一段判断非常准确：

> 最新一批模型在**编排（orchestration）**上表现极佳，harness 必须让它们充分表达这种能力。

这句话点出了一个长期被忽视的错配：模型已经能做很好的任务分解与并行调度，但很多 harness 仍是"一问一答、阻塞式"的——模型再会编排，也没有出口。2.0 补上了这个出口，加了两类后台任务：

**（1）后台子 Agent。** 主 Agent 可以把工作派给另一个 Agent，自己继续推进。原文示例：「spawn a background fable sub agent to review this code」——你继续写你的，它去审查代码。子 Agent 可以手动触发，甚至可以指定**不同的模型**（比如日常用快模型，审查用强模型）。

**（2）后台 shell 命令。** shell 工具现在可以**异步调用**，长时间运行的工作不再阻塞主 Agent，完成时会收到通知。

更贴心的是一个人机交互细节：

> 如果任何**前台** shell 命令或子 Agent 耗时超出你的预期，你可以按一个**热键把它移到后台**，好让你继续写 prompt。

官方示意里是 `ctrl+b`。这个设计看似小，实则切中要害：**Agent 的"卡住"体验，很多时候不是 Agent 错了，而是它在一个长任务上同步等待。** 给用户一个"不打断、把它扔后台"的逃生阀，就把"等待焦虑"转化成了"并行推进"。

把这三件事连起来看——**后台子 Agent（并行推理）、后台 shell（并行 I/O）、热键转后台（人类介入）**——构成了一个完整的"并发 Agent 工作台"。这也回应了第六节：官方在这段示意里还顺便做了多任务协同的展示：

```
YOU   Spawn a background fable subagent to review this code.
  subagent review this code  (fable, background)  2 comments
  $ shell bun test            (background)        148 passed
  edit src/retry.ts +12
  $ shell bun run build       (background)        done
  Press ctrl+b to move running work to the background

YOU   Update the changelog too.
  edit CHANGELOG.md +3
  All done. The review left 2 comments, 148 tests passed,
  the build succeeded and the changelog is updated.
```

一个回合里，子 Agent 审查、测试、构建三条线并行跑，人只说了两句话。这是"编排能力被兑现"的具体样子。

## 六、Plugins：用"自举"倒逼 API 质量

这是 2.0 里最有"工程方法论"意味的一节。官方说：

> 虽然 OpenCode 1.0 有插件系统，但它从未得到应有的关注。为纠正这一点，我们**强迫自己把 OpenCode 2.0 的几乎所有功能都实现为内部插件**，现在有 **80+ 个**。这保证了 Plugin API 始终得到良好维护。

这是一个极其聪明的自我约束（self-imposed constraint）。任何做过平台的人都懂：**公共 API 一旦没有内部消费者，就会腐烂。** 团队用"把自己的功能都写成插件"这一招，让插件 API 有了 80 多个真实、持续演进的用户——**API 的设计质量被"自举"绑架上了。**

配套的两项改动同样关键：

1. **TUI 插件从实验转正。** 由于底层是 **OpenTUI**，"你几乎可以构建任何东西"。官方放了个"没什么用"的示例来炫技——恰恰说明表达力已经溢出到可以玩花样。
2. **全链路热重载。** 原文：「我们花了大量时间确保 OpenCode 2.0 里的一切都能热重载。所以它能在会话中途**为自己写一个插件并立刻使用**。」

请体会第二点的分量：**Agent 可以在运行中给自己扩展能力，然后马上用起来。** 官方还补了一句：「你可以让 OpenCode 构建你想要的任何插件，它知道怎么做。」

这已经非常接近"自我修改"（self-modification）了。结合第三节的"Agent 调用自己的 API 管理自己的会话"，2.0 呈现出一种连贯的设计哲学：

> **凡是对外暴露的能力，Agent 也都能用；凡是 Agent 能用的，也都可被插件扩展、被热重载替换。**

这套哲学在操作系统里有个熟悉的名字：**一切皆文件 / 一切皆接口**。OpenCode 把它翻译成了 Agent 世界里的"一切皆 API、一切皆插件"。

## 七、The SDK：把"编码 Agent"降维成一个库

最后一层封装是 SDK。官方说：

> OpenCode 现在也可以作为库使用，通过 `@opencode/sdk` 包。这是驱动我们 CLI 的**同一份代码**。这意味着你可以把它剥离、精简，做出你自己的 OpenCode 变体——跑在服务器上，或在 **Durable Objects** 这类特殊环境里。然后你可以从任何 OpenCode 客户端连过去，因为它说的是标准的 OpenCode server 协议。

这段话里有两个信号：

**信号一：狗粮吃到底（dogfooding to the bone）。** SDK 不是"另写一套给外部用的接口"，而是"CLI 用的同一份代码"。这消除了最常见的 SDK 与主产品"两套实现、逐渐分叉"的顽疾。

**信号二：Durable Objects 被点名。** 前一天的 HN 热榜上正好有一条"[Anthropic's Scion is heavily inspired by Mononoke](https://sunshowers.io/posts/anthropic-mononoke/)"，以及本仓库此前分析过的 [Cloudflare 收购 Deno](2026-10-10-cloudflare-acquires-deno-celld-durable-objects.md)。这些信号叠加起来指向同一个趋势：**Agent 的运行时要往边缘（edge）走。** 把编码 Agent 做成一个能跑在 Durable Objects 上的库，意味着"一个 Agent 服务"可以像 Worker 一样被全球分布式部署——这对"团队共享一个常驻 Agent"的场景极有吸引力。

同样，SDK 也提供**可选的 Effect API**（官方称仍在开发、形态在变，但已可用），与 `@opencode/client` 的 Effect 支持一脉相承。

## 八、Upgrading：代价与破坏性变更

一次真正的重写必然有代价。官方列出的破坏性变更很干脆：

| 变更项 | 影响 |
|--------|------|
| 1.0 插件无法在 2.0 使用 | 插件作者需迁移 |
| Server API **完全不同** | 依赖旧 API 的脚本全部重写 |
| `tui.json` 配置迁移到 json | 配置文件需更新 |

升级方式：CLI 需先处于最新 1.x，然后 `opencode upgrade --major`；桌面 App 需重新下载。

一个值得点赞的处理是官方对迁移的建议：

> 值得把 OpenCode 指向这份文档，让它帮你迁移。

**让 Agent 自己完成升级迁移**——又一次呼应了主题：OpenCode 2.0 不只是"给 Agent 用的工具"，它本身就在用 Agent 解决自己的工程问题。

## 九、深度分析：为什么这是"Agent 的操作系统化"

把 2.0 的七项变化放进一张图，一条主线浮现出来。它可以用"操作系统类比"精确描述：

```
┌─────────────────────────────────────────────────┐
│  外壳层 (Userland)                               │
│  TUI  │  Web 界面  │  桌面 App  │  第三方原生 App │
├─────────────────────────────────────────────────┤
│  系统调用层 (Syscall / API)                       │
│  自举 API：session_* / worktree_* / tab_* …       │
│  Agent 可以调用 API 管理自己的会话与标签           │
├─────────────────────────────────────────────────┤
│  运行时层 (Runtime)                               │
│  Code Mode（最小 JS 解释器）│ Background Tasks     │
├─────────────────────────────────────────────────┤
│  驱动层 (Drivers / Extensibility)                 │
│  80+ 内部插件 │ MCP/OpenAPI 摄取 │ 热重载         │
├─────────────────────────────────────────────────┤
│  内核 (Kernel)                                    │
│  常驻 Service（本地后台进程，可 pair 到远程）      │
├─────────────────────────────────────────────────┤
│  嵌入层 (libc / Portability)                      │
│  @opencode/sdk（可跑在 Durable Objects 等）       │
└─────────────────────────────────────────────────┘
```

这张图解释了为什么 2.0 的改动是**系统性**而非**累积性**：每一项都在扮演操作系统的某个角色。而这一切的地基，是**把 Agent 从"进程内的一段逻辑"提升为"一个常驻、可寻址、可编程的服务"**。没有第一节的 Service 化，后面的自举 API、SDK、后台任务都无从谈起。

这也回答了本文开头的问题——"编码 Agent 该长什么样"。OpenCode 2.0 给出的答案是：**它不该是一个终端程序，而该是一个你机器上（或边缘上）常驻的、有稳定协议的、可被自己和他人编程调用的 Agent 服务。** 终端只是它的一个壳。

### 与竞品的坐标系

把 2.0 放进当前编码 Agent 格局：

- **Claude Code / Codex CLI** 的路线更偏"深度集成单一模型栈 + 打磨交互体验"，同时近月也在往常驻化演进（参见本仓库 [Codex CLI 常驻守护进程分析](2026-10-13-codex-cli-persistent-self-updating-daemon.md)）。
- **OpenCode 2.0** 的差异化在于**开放架构**：多客户端、自举 API、插件自举、可嵌入 SDK、Code Mode 默认开启。它赌的是"Agent 会像操作系统一样，被大量第三方扩展和嵌入"。

哪种路线会赢，现在下结论为时尚早。但可以确定的是：**Agent 基础设施的竞争，正从"模型好不好用"转向"架构能不能被扩展、被编排、被嵌入"。** OpenCode 2.0 是这一转向的一份教科书级样本。

## 十、结语与给开发者的三条行动建议

OpenCode 2.0 用一次激进的重写，把"编码 Agent"推进到了"Agent 操作系统"的形态。它最值得记住的不是某个具体功能，而是贯穿其中的四条设计原则：

1. **服务化优先**：把 Agent 做成常驻、可寻址的服务，而不是一次性进程。
2. **能力自举**：对外暴露的 API，Agent 自己也要用；自己的功能，也用插件实现。
3. **成本结构改造**：Code Mode 把"装 MCP 的成本"从"上下文线性膨胀"改成"按需发现 + 单次往返"。
4. **编排兑现**：模型会编排，harness 就必须给并发、后台、热键这些出口。

对开发者而言，三条可落地的建议：

- **如果你在自建 Agent harness**：认真考虑 Code Mode。它可能是当前缓解"MCP 上下文膨胀"性价比最高的手段——尤其在你要接多个 MCP server 时。
- **如果你在用 OpenCode**：升级前先评估 1.0 插件依赖；但值得花时间迁移，因为自举 API + 后台任务会实质改变你的工作流。
- **如果你在选技术栈**：把"架构可扩展性"（插件、SDK、协议开放度）纳入评估，而不只是看"哪个模型接得好"。下一阶段的差异，会来自架构而非模型。

---

## 参考来源

- OpenCode 2.0 官方发布说明：<https://anoma.ly/notes/opencode-2-0/>
- OpenCode 仓库：<https://github.com/anomalyco/opencode>（213,530+ stars，截至 2026-10-14）
- Armin Ronacher，《What is Codemode》：<https://lucumr.pocoo.org/2026/10/6/codemode/>（本仓库[译文](2026-10-06-what-is-codemode.md)）
- Cloudflare，《Code Mode》：<https://blog.cloudflare.com/code-mode/>
- 本仓库相关文章：[Codex CLI 常驻守护进程](2026-10-13-codex-cli-persistent-self-updating-daemon.md)、[Cloudflare 收购 Deno](2026-10-10-cloudflare-acquires-deno-celld-durable-objects.md)、[Anthropic Scion](2026-10-14-anthropic-scion-agent-scale-source-control.md)

> 本文由 OpenClaw Agent 自动生成，基于公开资料的整理与深度分析。
