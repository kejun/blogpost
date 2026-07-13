# 编码 Agent 的"隐性税"：当 Harness 在你说第一个字之前就烧掉 9 万 Token

> 你的 Agent 还没开始工作，就已经花了一大笔钱。这笔钱不是给模型的，是给"包装模型的壳"的。

2026 年 7 月 12 日，一篇题为 [《Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k》](https://systima.ai/blog/claude-code-vs-opencode-token-overhead) 的技术分析文章登上 Hacker News 首页，以 **427 分、238 条评论** 的热度引发社区激烈讨论。这篇文章做了一个简单但极其重要的事：在 Agent 和模型 API 之间架了一个日志代理，**精确测量了两个编码 Agent Harness 在每一个 HTTP 请求中到底发送了什么**。

结果令人震惊。

让两个 Agent 回复一句"OK"，Claude Code 消耗了约 **33,000 tokens** 的系统开销，而 OpenCode 只有约 **7,000 tokens**。在一个真实的、带 11 个 MCP 服务器和 72KB 指令文件的生产配置下，OpenCode 的首次请求消耗了 **90,817 tokens**，Claude Code 的配置则产生了约 **75,000 tokens** 的 payload（含 118 个工具定义和 311KB 数据）——**这些数字发生在用户甚至还没有输入第一个字之前**。

这不是一个"哪个工具更好"的对比。这是一个关于 **AI Agent Harness 架构设计中"隐性税"（Token Tax）如何成为生产成本第一大变量** 的深度分析。

---

## 一、什么是 Harness？为什么它的开销重要？

在 Agent 工程中，**Harness** 是连接人类意图和模型能力的那层"壳"。它负责：

- 组装系统提示词（System Prompt）
- 注册和注入工具 Schema
- 管理会话上下文和历史
- 处理权限、沙箱、子 Agent 调度
- 注入各类提醒块、技能目录、代理类型列表

Claude Code、OpenCode、Cursor、Codex——这些都是 Harness。它们共用同一批底层模型（Claude、GPT），但**用户体验、性能和成本的差异，绝大部分来自 Harness 层，而不是模型层**。

这就带来了一个被长期忽视的问题：**Harness 的设计选择，正在以用户无法察觉的方式，深刻影响 Agent 的生产成本和能力边界。**

---

## 二、"地板"测量：一句 OK 的代价

测量方法很朴素：在 Harness 和 API 端点之间放一个日志代理，捕获每个请求的完整 JSON payload 和 API 返回的 usage block。排除所有配置、MCP 服务器、指令文件、记忆，只测"最干净的裸机"。

### 2.1 首次请求的组件拆解

让 Agent 回复一句"Reply with exactly: OK"（22 个字符），两个 Harness 的首次请求payload 如下：

| 组件 | Claude Code | OpenCode |
|------|-------------|----------|
| 系统提示词 | 27,344 字符，3 个 block | 9,324 字符，1 个 block |
| 工具 Schema | 27 个工具，99,778 字符 | 10 个工具，20,856 字符 |
| 首消息脚手架 | 7,997 字符（`<system-reminder>` blocks） | 无 |
| 实际用户 prompt | 22 字符 | 22 字符 |
| **首次请求总 token（校准后）** | **~32,800** | **~6,900** |

关键洞察：

**工具定义是最大开销。** Claude Code 的 27 个工具中，除了核心编码工具，还包括一整套后台 Agent 和编排套件——从 `CronCreate`、`Monitor` 到 `Task` 系列、worktree 管理、推送通知。这些工具即使你一次都不会用到，它们的 JSON Schema 也会被完整序列化进每一个请求。

**系统提示词是"行为教条"的容器。** Claude Code 的 27,344 字符系统提示包含三个 block：Agent 类型委托目录、可用技能目录、用户上下文。OpenCode 只有一个 block，以 "You are OpenCode, the best coding agent on the planet" 开头。即使去掉所有工具，Claude Code 的纯系统提示词（约 6,500 tokens）仍然是 OpenCode（约 2,000 tokens）的 **3 倍以上**。

**`<system-reminder>` 块是隐性增长项。** Claude Code 在首条用户消息中注入了 3 个 reminder block，随着会话推进，这个数字会增长到 4 个甚至更多。这意味着**Harness 的开销不仅是一个固定常数，它还会随轮次增长**。

### 2.2 零工具对照实验

为了分离"系统提示词"和"工具 Schema"的权重，测量者分别禁用了所有工具：

- Claude Code（零工具）：系统提示词约 **6,500 tokens**
- OpenCode（零工具）：系统提示词约 **2,000 tokens**

即使没有任何工具，Claude Code 的"行为教条"（语气规则、安全指引、任务管理指令、环境描述）仍然是 OpenCode 的 3 倍。这些教条本身不是坏的——它们确实让 Agent 更安全、更可控——但**每一字节都按 token 计费**。

---

## 三、五个"乘数"：生产环境的真实账单

地板测量揭示了基线开销。但真实的生产会话不会停留在地板上。让我们看五个让账单膨胀的乘数。

### 乘数 1：指令文件（Instruction File）

把一个 72KB 的生产级 `AGENTS.md`（或 `CLAUDE.md`）放进工作区：

- OpenCode：从 13,152 tokens 涨到 **33,336 tokens**（+20,184）
- Claude Code：从 39,005 tokens 涨到 **59,243 tokens**（+20,238）

两个 Harness 对指令文件的 token 税是**对称的**——约 20,000 tokens 每个请求。但机制完全不同：

- **Claude Code 2.1.207 完全忽略 `AGENTS.md`**，只在文件被重命名为 `CLAUDE.md` 时才注入，且注入到首条用户消息中。
- **OpenCode 两个文件名都认**，注入到系统提示词中。

**实践教训：** 确认你的 Harness 实际读取哪个文件名。一个被忽略的指令文件是"静默失败"——你以为 Agent 读过你的规则，它其实没读。

### 乘数 2：MCP 服务器

挂载 5 个公共的、无凭证的 MCP 服务器：

- Claude Code：payload 增加约 **4,900 tokens**，工具数从 27 涨到 69
- OpenCode：metered 增加约 **6,967 tokens**，工具数从 10 涨到 52

**每个小型 MCP 服务器约 1,000–1,400 tokens/请求**。生产环境中带丰富 API 的 MCP 服务器，其 Schema 可能是这个数字的数倍。

**另一个静默失败：** Claude Code 在 print 模式下会**静默忽略**项目级 `.mcp.json`，直到你显式传入 `--mcp-config` 标志。

### 乘数 3：框架模板

故事驱动型工作流框架（如 BMAD）将一个 slash 命令扩展为包含角色、协议和检查清单的大型 prompt 模板。

一个代表性的 8,405 字符模板约 **2,100 tokens**。如果一次会话需要 9 轮请求，这个模板会被**完整重发 9 次**，产生约 18,900 tokens 的框架税。

公式：`框架税 = 模板大小 × 请求轮次数`

### 乘数 4：子 Agent（Subagents）

这是**最大的 token 乘数**。

让 Claude Code 把一个任务分发给两个并行子 Agent：

- 直接执行：**121,000 tokens**
- 分发到两个子 Agent：**513,000 tokens**
- **乘数：4.2x**

为什么？因为每个子 Agent 都要支付自己的 bootstrap 开销（3,554 字符的 Agent 系统提示词 + 24/27 个工具），然后父 Agent 还要消耗子 Agent 的完整 transcript。

OpenCode 的子 Agent 设计更精简：1,379 字符系统提示词 + 5 个工具。但其子 Agent 通道的完整数字未能通过测量者的网关环境完成量化。

**如果你在重负载会话中惊讶于账单，第一个该查的地方就是子 Agent 扇出。** 委托是强大的，但它也是单个最大的 token 乘数。

### 乘数 5：扩展思考（Extended Thinking）

思考输出按**输出速率**计费，是输入速率的 5 倍。而且 reasoning block 会被携带进对话历史，在后续每一轮都被重发。

在推理密集型任务中，思考 token 会与上述所有乘数**复合叠加**——思考 block 加入历史，历史被重发，重发时携带思考，思考又触发更多思考……

---

## 四、"一切加起来"：生产配置的全貌

测量者跑了一个"完整生产配置"的最终测试：

**OpenCode 的完整配置：**
- 11 个 MCP 服务器（邮件、日历、任务管理、参考管理、产品分析等）
- 72KB 指令文件
- 首次请求：**90,817 tokens**（冷缓存写入）
- 携带 **179 个工具**、**277KB Schema**

**Claude Code 的完整配置：**
- 4 个 MCP 服务器 + 已安装插件 + 同样指令文件
- Payload 约 **75,000 tokens**，**311KB**，**118 个工具**

**这发生在用户还没有输入第一个字之前。**

相对于 OpenCode 约 7,000 tokens 的地板，完整配置是一个 **约 12x 的乘数**。Harness 决定了地板；你的配置决定了账单。

---

## 五、缓存经济学：Prompt Caching 救不了你

Claude API 的 prompt caching 允许 Harness 将请求前缀写入缓存（TTL 5 分钟），后续读取按 1/10 价格计费。但**有三个成本完全不受缓存折扣影响**：

### 5.1 缓存写入本身

每次会话暂停超过 TTL——比如你思考了 5 分钟、开了个会、吃了个午饭——缓存就失效了。下次请求需要**以写入价格重付整个栈**。一个 85,000-token 的冷写入按 1.25x 的写入溢价计费，本身就是一笔不小的开销。

### 5.2 缓存读取 × 请求轮次

缓存读取虽然便宜（1/10 价格），但**乘以请求轮次后仍然可观**。子 Agent 扇出和串行工具循环会迅速膨胀读取次数。

### 5.3 上下文窗口消耗——完全免疫缓存折扣

这是最致命的一点。**85,000 tokens 的 bootstrap 消耗了超过 40% 的 200,000-token 上下文窗口**，而且这个数字**与缓存无关**。上下文窗口的消耗是按 token 数量计费的物理限制，缓存不改变任何物理事实。

一个有趣的设计差异：OpenCode 的请求前缀在每次运行中**字节级完全一致**，这意味着它可以一次写入、反复读取。而 Claude Code 的请求前缀**在会话中会动态变化**——它会重新写入数万个 prompt-cache token，在某些任务中比 OpenCode 多写入 **54 倍**的缓存 token。

---

## 六、反转：什么时候"重 Harness"反而更便宜？

测量中有一个反直觉的发现。

在一个多步骤的 write-run-test-fix 循环任务中：

| 指标 | Claude Code | OpenCode |
|------|-------------|----------|
| 模型请求数 | 3 | 9（+1 标题调用） |
| 工具调用风格 | 单轮并行批量 | 每轮单工具调用 |
| 累计 metered 输入 | **~121,000** | **~132,000** |

Claude Code 将整个任务（2 个文件写入 + 2 个脚本执行）**批量打包进一次并行工具往返**。OpenCode 每轮只做一个工具调用，跑了 9 轮。

因为基线开销在每次请求中都会被重发，**请求轮次会放大基线**。OpenCode 付了 9 次 ~7,000 的基线，Claude Code 付了 3 次 ~33,000 的基线——最终总额反而接近了。

**公式：总输入 ≈ 基线 × 请求轮次 + 对话增长**

一个大基线但激进批量的 Harness，和一个小基线但串行执行的 Harness，可以到达同一个终点。

但这有个前提：**任务必须足够简单，以至于批量策略生效**。在更复杂的任务中，Claude Code 的 `<system-reminder>` 块会随着轮次增长（首条消息 3 个，第一个工具轮次就涨到 4 个），这个隐性增长项最终会吞噬批量带来的节省。

---

## 七、模型条件化：Claude Code 的自适应策略

测量者用 Claude Fable 5 重跑了地板测试，发现了一个意料之外的现象：

**Claude Code 的系统提示词是模型条件化的（Model-Conditional）。**

| 模型 | 系统提示词字符数 | 工具 Schema 字符数 | 地板倍率 |
|------|-----------------|-------------------|---------|
| Sonnet 4.5 | 27,787 | 99,778 | 4.7x |
| Fable 5 | 10,526 | 82,283 | 3.3x |

同样的 27 个工具，但发送给 Fable 5 的教条大幅缩减。Claude Code 似乎在**针对更新的模型减少行为约束**——可能是因为更强的模型需要更少的"引导"。

OpenCode 的 payload 在两个模型间**字节级完全一致**。

这意味着 Harness 的开销不仅是架构问题，还是**模型选择问题**。用更强的模型可能降低 Harness 的相对开销，但也可能因为更强的模型本身单价更高而抵消。

---

## 八、Harness 税的工程启示

### 8.1 对你的钱包的影响

让我们算一笔实际的账。假设一个典型的日常开发会话：

- 30 轮对话
- 1 个 72KB 指令文件（+20,000 tokens/请求）
- 5 个 MCP 服务器（+5,000 tokens/请求）
- 不使用子 Agent

Claude Code 的每请求基线约 33,000 + 20,000 + 5,000 = **58,000 tokens**。
30 轮 × 58,000 = **1,740,000 tokens** 的纯 Harness 税。

按 Claude Sonnet 4.5 的缓存读取价格（约 $0.30/M tokens），光这层壳就要花掉 **$0.52**。再加上实际的模型推理、工具执行和输出——**你在"空转"上的花费可能占到总账单的 40-60%**。

### 8.2 对你的上下文的影响

一个 200,000-token 的上下文窗口。你的 72KB 指令文件占了 20,000 tokens。你的 5 个 MCP 服务器占了 5,000 tokens。你的系统提示词和工具定义占了 33,000 tokens。

**58,000 tokens——接近 30% 的上下文窗口，在你说第一个字之前就已经被占用了。**

留给代码、文件内容、错误信息、对话历史的空间，只剩下 142,000 tokens。而在长会话中，对话历史本身会迅速填满这个空间，触发截断或摘要。

### 8.3 对 Harness 设计的启示

测量结果指向几个明确的设计方向：

**1. 工具 Schema 的按需加载。** 不要一次性注入所有工具。Claude Code 的 27 个工具中，可能一次会话只用 3-5 个。根据任务类型动态选择工具子集，可以砍掉 60-80% 的工具 Schema 开销。

**2. 指令文件的分级加载。** 不是所有指令都需要在每个请求中携带。全局行为规则可以进系统提示词（一次写入、反复缓存读取），而项目级规则可以按需注入。

**3. 子 Agent 的"热启动"。** 如果子 Agent 需要被频繁调用，应该有一种机制让它共享父 Agent 的缓存前缀，而不是每次都从头 bootstrap。

**4. `<system-reminder>` 块的精简。** 随着轮次增长的 reminder 块是隐性的 token 膨胀源。应该评估每个 reminder 是否真的在每个轮次都需要。

**5. Harness 的 Token 可观测性。** 正如 systima.ai 指出的，"你的 Agent 到底发送了什么"这个问题，应该能用数据回答，而不是凭感觉。EU AI Act 第 12 条要求你记录和了解系统行为——这不仅是合规需求，也是成本优化需求。

---

## 九、更广阔的图景：Harness Engineering 的 2026

这篇文章之所以在 HN 上引爆（427 分，238 评论），是因为它触及了 2026 年 AI 工程的核心矛盾：

**模型能力正在快速逼近，但 Harness 设计的差距在拉大。**

想想最近几周的其他新闻：

- **GPT-5.6 引入 Programmatic Tool Calling**，从"模型调用工具"进化到"模型编程调用工具"，从根本上改变了工具调用的架构。
- **GitHub 上 `destructive_command_guard` 一天涨 444 星**，说明社区开始认真对待"Agent 执行危险命令"这个问题——这本质上也是 Harness 层的设计决策。
- **DesktopCommanderMCP 接近 8,000 星**，它给 Claude 提供了终端控制、文件系统搜索和 diff 编辑能力——又一个让 Harness 更"重"的方向。
- 我们之前讨论过的 **Headroom** 项目，试图在 Agent 和模型之间加一层 Token 压缩层——本质上就是在对抗 Harness 税。

Harness 不再只是一个"包装壳"。它正在成为 AI 工程中最有差异化的竞争点——也是最大的成本变量。

---

## 十、我的判断

作为长期跟踪 AI Agent 基础设施的观察者，我认为 Harness Token Tax 问题在 2026 下半年会经历三个阶段：

**第一阶段（现在）：发现和测量。** systima.ai 的文章是标志性事件——社区开始用数据而不是直觉来理解 Harness 开销。

**第二阶段（Q3 2026）：优化和竞争。** Harness 开发者会开始把"低 Token 税"作为卖点。我们会看到更智能的工具按需加载、指令文件分级、子 Agent 热启动等技术。

**第三阶段（Q4 2026）：标准化和协议化。** 可能会出现一个类似"Agent Token Budget Protocol"的标准，让 Harness、模型和用户在 token 预算上达成明确的契约。就像 HTTP 的 `Content-Length` 头一样，Agent 请求也应该有一个 `Token-Budget` 头。

**我的核心判断：** 2026 年的 AI 工程，模型不再是瓶颈。**Harness 的 Token 税才是。** 谁能把壳做薄，谁就能在 Agent 经济中赢得最大的成本优势。

---

## 参考资料

1. systima.ai, ["Claude Code Is Way More Token-Hungry Than OpenCode"](https://systima.ai/blog/claude-code-vs-opencode-token-overhead), 2026-07-12
2. Hacker News, ["Claude Code sends 33k tokens before reading the prompt; OpenCode sends 7k"](https://news.ycombinator.com/item?id=48883275), 427 分 / 238 评论
3. GitHub Trending, [destructive_command_guard](https://github.com/Dicklesworthstone/destructive_command_guard), 2,851 stars
4. GitHub Trending, [DesktopCommanderMCP](https://github.com/wonderwhy-er/DesktopCommanderMCP), 7,974 stars
5. ploy.ai, ["Migrating a production AI agent to GPT-5.6: 2.2x faster, 27% cheaper"](https://ploy.ai/blog/migrating-a-production-ai-agent-to-gpt-5-6), 2026-07-12
6. EU AI Act, Article 12: Technical Documentation requirements

---

*本文基于 systima.ai 的公开测量数据和 Hacker News 社区讨论撰写。所有数字均来自原文引用，部分推演和判断为作者独立观点。*
