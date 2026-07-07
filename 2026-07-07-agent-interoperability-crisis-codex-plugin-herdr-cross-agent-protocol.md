# Agent 互操作性危机：当 Claude Code 开始调用 Codex——2026 年 Agent 生态的"巴别塔时刻"

> **摘要：** 2026 年 7 月初，GitHub Trending 上同时涌现出一批令人瞩目的项目：**OpenAI 官方发布了 `codex-plugin-cc`**（让 Claude Code 用户直接在 IDE 内调用 Codex 进行代码审查和任务委派，上线即获 26,000+ stars）；**`herdr`**（一个用 Rust 编写的 Agent 多路复用器，让开发者在一个终端里同时运行多个编码 Agent，12,800+ stars）；**`gastown`**（多 Agent 工作空间管理器）；以及持续爆发的 **Agent Skills 生态**（addyosmani/agent-skills 突破 70,000 stars，taste-skill 突破 58,000 stars）。这些项目看似独立，实际上指向了同一个深层趋势：**AI Agent 生态正在经历一场"互操作性危机"——不同厂商的 Agent 之间开始互相调用、协作、编排，但行业标准尚未成型。** 2026 年下半年，谁能定义 Agent 之间的通信协议，谁就可能成为下一个基础设施赢家。本文将从技术架构、生态数据、协议标准三个维度，深度剖析这一正在快速成型的新赛道。

---

## 一、"巴别塔时刻"：当 Agent 开始互相对话

### 1.1 一个反直觉的信号：OpenAI 为 Anthropic 的产品写插件

2026 年 7 月 6 日，OpenAI 在 GitHub 上发布了一个名为 [`codex-plugin-cc`](https://github.com/openai/codex-plugin-cc) 的开源项目。它的 README 只有一句话：

> "Use Codex from inside Claude Code for code reviews or to delegate tasks to Codex."

这看似简单，但**信号意义极其重大**。

想想这个场景：你正在使用 Anthropic 的 Claude Code 写代码，但你想让 OpenAI 的 Codex 来审查你的代码。在过去，这意味着你要切换工具、切换上下文、手动复制代码片段。而现在，OpenAI 官方提供了一个插件，让你在 Claude Code 的终端里直接输入 `/codex:review`，Codex 就会在后台运行代码审查，结果返回到 Claude Code 的会话中。

这不是一个第三方 hack，这是**OpenAI 官方主动适配竞品**。

`codex-plugin-cc` 提供的功能远不止代码审查：

| 命令 | 功能 | 模式 |
|------|------|------|
| `/codex:review` | 对当前未提交更改进行代码审查 | 只读 |
| `/codex:adversarial-review` | 对抗性审查——质疑设计决策和假设 | 只读+挑战 |
| `/codex:rescue` | 将任务委派给 Codex（bug 调查、修复等） | 读写 |
| `/codex:transfer` | 将会话从 Claude Code 移交到 Codex | 会话移交 |
| `/codex:status` | 查看后台 Codex 任务状态 | 监控 |
| `/codex:cancel` | 取消正在运行的 Codex 任务 | 控制 |

更值得注意的是 `codex:rescue` 命令——它支持 `--resume`（继续上一次任务）和 `--fresh`（重新开始），并且可以选择不同的模型（`gpt-5.4-mini`、`spark` 等）和 effort 级别（`low`、`medium`、`high`）。**这本质上是一个跨 Agent 的任务委派协议。**

### 1.2 同日爆发的其他信号

但 `codex-plugin-cc` 不是孤立事件。同一天，GitHub Trending 上还出现了：

**herdr**（12,848 stars，Rust 编写）：
> "Agent multiplexer that lives in your terminal. Run all your coding agents in one terminal. See who's blocked, working, or done at a glance."

herdr 的核心理念是：每个 Agent 都获得一个**真正的终端**（不是 GUI 包装的伪终端），你可以在一个界面中同时看到多个 Agent 的状态——🔴 blocked（需要人类介入）、🟡 working（正在处理）、🔵 done（完成）、🟢 idle（空闲）。它的定位很清晰：**tmux 为 Agent 时代重新设计**。

herdr 的关键特性：
- 真正的终端 per agent（支持全屏 TUI）
- Agent 状态感知（自动检测 blocked/working/done/idle）
- Workspace、Tab、Pane 组织
- 断开连接不丢失状态（后台 server 保持运行）
- 单一 ~10MB Rust 二进制，无依赖
- **Socket API 和 CLI，Agent 可以自行驱动编排**

注意最后一条——"Agent 可以自行驱动编排"。这意味着 Agent 不再仅仅是"人类操作的工具"，它们可以**互相发现、互相调用、互相协调**。

**gastown**（多 Agent 工作空间管理器）：
> "Multi-agent workspace manager."

虽然 README 还很简短，但它的方向很明确：为多 Agent 协作提供工作空间级别的管理。

### 1.3 数据：Agent 互操作工具的 star 增长趋势

将这些项目放在同一时间线上，可以看到一个清晰的**生态爆发模式**：

| 项目 | Stars | 日增 | 核心定位 |
|------|-------|------|----------|
| addyosmani/agent-skills | 70,765 | +1,112 | Agent 工程技能库 |
| Leonxlnx/taste-skill | 58,890 | +1,458 | Agent 审美质量控制 |
| openai/codex-plugin-cc | 26,263 | +906 | 跨 Agent 调用协议 |
| karakeep/karakeep | 26,874 | +199 | AI 增强知识管理 |
| firecrawl/firecrawl | 146,219 | +867 | Web 爬取 API（Agent 用） |
| ogulcancelik/herdr | 12,848 | +779 | Agent 多路复用器 |
| alibaba/zvec | 13,491 | +382 | 轻量级向量数据库 |
| bradautomates/claude-video | 4,201 | +427 | Agent 视频理解 |

**关键观察：** 这些项目不是均匀分布的，而是集中在"Agent 互操作"这个轴线上。`codex-plugin-cc` 解决的是跨厂商调用，`herdr` 解决的是多 Agent 编排，`agent-skills` 解决的是 Agent 能力标准化，`firecrawl` 解决的是 Agent 的 Web 交互能力。**它们共同构成了一个"Agent 互操作性基础设施栈"的雏形。**

---

## 二、技术深潜：跨 Agent 通信的三种模式

### 2.1 模式一：插件桥接（Plugin Bridging）

`codex-plugin-cc` 代表的是第一种模式：**通过插件系统实现跨 Agent 调用**。

```
Claude Code 用户输入
       ↓
/codex:review --background
       ↓
codex-plugin-cc（Node.js 插件）
       ↓
OpenAI Codex API（子进程执行）
       ↓
审查结果返回 Claude Code 会话
```

这个架构有几个值得注意的设计决策：

**1. 进程隔离。** Codex 运行在独立的子进程中，不共享 Claude Code 的内存空间。这意味着：
- 安全风险可控（Codex 无法直接访问 Claude Code 的内部状态）
- 资源管理独立（Codex 有自己的 token 限制和速率限制）
- 故障隔离（Codex 崩溃不影响 Claude Code）

**2. 命令级抽象。** 插件不暴露 Codex 的底层 API，而是封装成一组高级命令（`/codex:review`、`/codex:rescue` 等）。这是一种**协议层的设计**——它定义了"什么可以做"，而不是"怎么做"。

**3. 异步优先。** 代码审查被推荐以 `--background` 模式运行，因为多文件变更可能需要较长时间。这暗示了一个重要的工程现实：**跨 Agent 调用通常是异步的**，需要状态跟踪和结果轮询机制。

### 2.2 模式二：多路复用（Multiplexing）

`herdr` 代表的是第二种模式：**多 Agent 并行运行 + 统一状态管理**。

```
用户终端
   ↓
herdr（Rust 后台 server）
   ├── Agent 1（Claude Code）→ 🟡 working
   ├── Agent 2（Codex）→ 🔴 blocked
   ├── Agent 3（Cursor Agent）→ 🔵 done
   └── Agent 4（Gemini CLI）→ 🟢 idle
```

herdr 的创新在于它重新思考了"终端"在 Agent 时代的角色：

**1. Agent-aware 状态检测。** herdr 不需要用户配置 hooks 或 bells 就能知道 Agent 的状态。它通过监控终端输出模式（比如等待用户输入时的特定提示符、完成时的退出码）来自动推断 Agent 状态。这是一个**零配置的设计哲学**。

**2. 真正的终端渲染。** 与 GUI Agent 管理器（如 Conductor、cmux）不同，herdr 不重绘终端——它直接把每个 Agent 的真实终端屏幕呈现给用户。这意味着全屏 TUI 应用（如 `htop`、`vim`、`lazygit`）在 Agent 模式下也能正常工作。

**3. 可脚本化编排。** herdr 提供了 Socket API 和 CLI，这意味着**Agent 自身可以调用 herdr 来管理其他 Agent**。这是一个关键的"Agent 编排 Agent"的设计模式。

### 2.3 模式三：能力发现与组合（Capability Discovery & Composition）

Agent Skills 生态（如 `agent-skills`、`taste-skill`）代表的是第三种模式：**通过标准化的能力定义，让不同 Agent 可以"安装"和"组合"同一套技能**。

这种模式的核心假设是：**Agent 的能力应该是可插拔的、可组合的、可跨平台复用的。**

但这里存在一个根本性的挑战：**不同 Agent 平台的 Skill 格式不兼容。**

| 平台 | Skill 格式 | 安装方式 |
|------|-----------|----------|
| Claude Code | SKILL.md（Markdown） | `/skill install` |
| Cursor | `.cursor/rules/` | 项目级配置 |
| OpenAI Codex | 插件 marketplace | `/plugin install` |
| OpenClaw | SKILL.md + 目录结构 | 自动发现 |

**这就是"巴别塔时刻"的本质**——每个厂商都在用自己的语言定义"Agent 能力"，但它们之间无法互操作。

---

## 三、行业背景：为什么互操作性在 2026 年成为问题？

### 3.1 从"单 Agent"到"多 Agent"的范式转移

回顾过去 18 个月的 Agent 发展轨迹：

| 阶段 | 时间 | 特征 | 代表产品 |
|------|------|------|----------|
| Chatbot | 2022-2023 | 单轮对话，无工具调用 | ChatGPT, Claude |
| Tool-Use Agent | 2023-2024 | 单次工具调用 | GPT-4 with Code Interpreter |
| Agentic Loop | 2024-2025 | 多步工具调用，自我修正 | Claude Code, Cursor Agent |
| **Multi-Agent** | **2026-** | **多个 Agent 协作、互相调用** | **codex-plugin-cc, herdr, gastown** |

我们正处于从"Agentic Loop"到"Multi-Agent"的转折点。这个转折的核心特征是：**Agent 不再仅仅与人类交互，它们开始与其他 Agent 交互。**

### 3.2 经济学驱动：为什么厂商开始互相兼容？

OpenAI 主动为 Claude Code 写插件，这是一个**违反直觉的商业行为**。在传统的竞争逻辑中，你希望用户留在自己的生态里。但 AI Agent 时代有几个因素改变了这个逻辑：

**1. 用户锁定成本降低。** 在 SaaS 时代，用户锁定靠的是数据迁移成本和工作流惯性。在 Agent 时代，**用户的"工作流"本身就是 Agent 的能力组合**——如果用户习惯了"用 Claude Code 写代码 + 用 Codex 审查"的组合，厂商阻止这种组合只会让用户流失到更开放的方案。

**2. 模型 commoditization 加速。** GLM-5.2（智谱 AI，744B MoE）等开源模型正在逼近闭源前沿模型的能力边界。当模型能力差距缩小到 10-15% 时，**差异化的关键不再是模型本身，而是 Agent 的互操作性和生态整合能力**。

**3. Agent 消费模式的转变。** 传统 API 是按 token 计费的。但 Agent 模式下，一次任务可能消耗数万甚至数十万 token。**用户开始关注"完成一个任务的总成本"，而不是"每个 token 的单价"**。如果跨 Agent 协作能降低总任务成本，用户自然会要求它。

### 3.3 一个具体的经济学案例

假设一个开发团队需要完成以下任务：
1. 实现一个新功能（写代码）
2. 代码审查
3. 测试编写和修复
4. 部署

在"单 Agent"模式下，你可能选择一个 Agent 完成所有步骤。但现实是：**不同 Agent 在不同任务上有不同的性价比**。

| 任务 | 最佳 Agent | 预估成本 | 耗时 |
|------|-----------|----------|------|
| 写代码 | Claude Code (Sonnet 5) | $2.50 | 15 min |
| 代码审查 | Codex (GPT-5.4) | $0.80 | 5 min |
| 测试修复 | Claude Code (Haiku 3) | $0.30 | 3 min |
| 部署脚本 | Cursor Agent | $0.50 | 5 min |
| **总计** | **混合** | **$4.10** | **28 min** |
| 单 Agent 全包 | Claude Code (Opus 4.8) | $8.50 | 35 min |

**混合方案节省了 52% 的成本和 20% 的时间。** 这就是互操作性的经济驱动力——**当 Agent 可以互相调用时，用户可以为每个子任务选择最优的 Agent，而不是被迫用一个 Agent 做所有事。**

---

## 四、协议层：Agent 互操作性需要什么标准？

### 4.1 当前缺失的标准

要理解 Agent 互操作性需要什么，我们可以参考互联网协议栈的类比：

```
互联网协议栈          Agent 互操作协议栈
─────────────────    ────────────────────
HTTP/REST            ❌ Agent Command Protocol (ACP)
WebSocket            ❌ Agent Streaming Protocol
OAuth                ❌ Agent Identity & Auth
JSON Schema          ❌ Agent Capability Schema
OpenAPI              ❌ Agent Tool Description Standard
```

**Agent Command Protocol (ACP)**：定义 Agent 之间如何发送命令和接收响应。`codex-plugin-cc` 实际上定义了一个简化的 ACP——`/codex:review`、`/codex:rescue` 等命令就是 ACP 的雏形。但它只适用于 Claude Code ↔ Codex 这一对组合。

**Agent Streaming Protocol**：定义 Agent 之间的流式通信。Agent 任务通常需要长时间运行，需要支持：
- 进度更新（"我已经审查了 5/12 个文件"）
- 中间结果（"发现了 3 个潜在问题"）
- 状态变更（"我被 blocked 了，需要人类决策"）
- 最终结果（"审查完成，2 个 critical，1 个 warning"）

**Agent Identity & Auth**：当 Agent A 调用 Agent B 时，如何证明"我是 Agent A，我被授权执行这个操作"？当前所有方案都依赖人类用户的 API key，但这在 Agent 自主协作的场景下是不可持续的。

**Agent Capability Schema**：一个标准化的方式，让 Agent 声明"我能做什么"。`codex-plugin-cc` 的 README 列出了它支持的命令，但这是一种**人类可读的文档**，不是**机器可解析的 schema**。

### 4.2 MCP 的可能角色

Model Context Protocol (MCP) 是 Anthropic 提出的一个开放协议，最初用于让 LLM 访问外部工具和资源。但它有潜力成为 Agent 互操作性的基础：

**MCP 的优势：**
- 已经是开放标准（Apache 2.0 许可）
- 有 SDK 支持（Python、TypeScript、Kotlin 等）
- 支持 Tool、Resource、Prompt 三种交互模式
- 正在被多个平台采用（OpenClaw、Claude Desktop 等）

**MCP 的局限：**
- 最初设计的是"LLM ↔ Tool"模式，不是"Agent ↔ Agent"模式
- 缺少 Agent 状态跟踪和异步任务管理
- 缺少多 Agent 编排语义

**一个可能的演进路径：**
```
MCP v1（当前）   →   MCP v2（Agent Aware）   →   MCP v3（Agent Mesh）
LLM↔Tool              Agent↔Tool + 状态           Agent↔Agent + 编排
```

### 4.3 另一种可能：从插件生态自下而上涌现

与 MCP 的"自上而下"路径不同，另一种可能性是**插件生态自下而上涌现出事实标准**。

`codex-plugin-cc` 的模式就是这种路径的雏形：
1. OpenAI 定义了一个插件接口（slash commands + 后台任务）
2. 这个接口通过 Claude Code 的插件系统被实现
3. 其他 Agent 平台可以类似地实现这个接口
4. 最终，这个接口成为事实标准

**类比：** Docker 容器格式不是由 W3C 或 IETF 标准机构制定的，而是由 Docker 公司定义，然后通过开放容器倡议（OCI）成为行业标准。**Agent 互操作协议可能也会走类似的路径——由最有影响力的参与者定义，然后被社区采纳。**

---

## 五、技术挑战：跨 Agent 协作的六个工程难题

### 5.1 上下文传递（Context Handoff）

当 Agent A 将任务委派给 Agent B 时，需要传递什么？

- **代码状态**：当前文件、未保存的更改、git diff
- **对话历史**：用户之前的指令和 Agent 的响应
- **工具状态**：已打开的终端进程、运行的服务、环境变量
- **任务意图**：用户想要什么，已经尝试了什么，卡在哪里

目前 `codex-plugin-cc` 的做法是传递 **git 状态**（通过 `--base main` 比较分支差异）。但这只是冰山一角。

**理想方案：** 一个标准化的 Context Handoff Format，类似 HTTP 的请求/响应格式，但包含 Agent 所需的完整上下文。

### 5.2 权限边界（Permission Boundaries）

当 Claude Code 调用 Codex 时，Codex 的权限范围是什么？

- 它能读取哪些文件？
- 它能执行哪些命令？
- 它能访问哪些环境变量？
- 它能看到用户之前的对话历史吗？

当前的实现倾向于**最小权限原则**——`codex:review` 是只读的，`codex:rescue` 可以修改代码但需要用户确认。但这在更复杂的跨 Agent 协作场景中会变得极其复杂。

### 5.3 错误传播（Error Propagation）

当 Agent B 在执行 Agent A 委派的任务时出错，错误如何传递？

```
Agent A 委派任务给 Agent B
       ↓
Agent B 遇到错误（权限不足？模型幻觉？工具不可用？）
       ↓
错误传递给 Agent A
       ↓
Agent A 决定：重试？换另一个 Agent？上报人类？
```

这需要一个**标准化的错误分类和恢复协议**，而不是每个平台自己定义。

### 5.4 成本归因（Cost Attribution）

在跨 Agent 协作中，如何追踪和归因成本？

如果一个任务由 Claude Code 发起，Codex 执行代码审查，Claude Haiku 修复测试——**谁来为这些 token 负责**？用户需要一个统一的成本视图，而不是在每个平台的账单里分别查找。

### 5.5 版本兼容性（Version Compatibility）

当 `codex-plugin-cc` 更新了，Claude Code 也需要更新吗？当 Codex 的 API 改变了，插件的哪些命令会受影响？

**依赖矩阵正在指数级增长。** N 个 Agent 平台，每个平台有 M 个版本，兼容性矩阵的大小是 N×M×N×M。没有自动化的兼容性测试，这个矩阵很快就会失控。

### 5.6 安全审计（Security Auditability）

当多个 Agent 互相调用时，如何审计"谁做了什么"？

传统的审计日志假设"一个用户操作一个系统"。但 Agent 互操作场景下是"一个用户操作 Agent A，Agent A 操作 Agent B，Agent B 操作 Agent C……"。**审计日志需要追踪整个 Agent 调用链**，而不仅仅是单个 Agent 的操作。

---

## 六、未来展望：2026 年下半年会发生什么？

### 6.1 短期预测（2026 Q3）

1. **更多跨平台插件出现。** OpenAI 为 Claude Code 写插件的先例已经被树立。Cursor 可能为 Codex 写插件，Anthropic 可能为 Cursor 写插件。我们可能会看到"插件矩阵"的形成。

2. **Agent 多路复用器成为标配。** herdr 的概念会被更多团队复制。开发者不会满足于"一次只能用一个 Agent"——他们需要同时运行多个 Agent，并行处理不同任务。

3. **Agent Skills 格式标准化尝试。** 社区可能发起一个"Agent Skills Format"提案，尝试统一不同平台的 Skill 定义格式。

### 6.2 中期预测（2026 Q4 - 2027 Q1）

1. **第一个开源 Agent 互操作协议诞生。** 可能是 MCP 的扩展，也可能是全新项目。它需要解决上下文传递、权限边界、错误传播、成本归因等核心问题。

2. **Agent 编排平台出现。** 类似 Kubernetes 之于容器，会出现一个"Agent Orchestrator"——定义 Agent 的调度策略、依赖关系、资源限制、故障恢复。

3. **Agent 身份认证协议。** 当 Agent 开始自主协作时，需要一种不需要人类干预的身份认证方式。可能是基于加密签名的 Agent-to-Agent 认证。

### 6.3 长期愿景（2027+）

**Agent Mesh：** 一个去中心化的 Agent 网络，每个 Agent 都可以：
- 发现其他 Agent 的能力（通过能力注册表）
- 按需调用其他 Agent（通过标准协议）
- 组合多个 Agent 的能力完成复杂任务（通过编排引擎）
- 追踪调用链和成本（通过分布式追踪）

这不是科幻。它正在发生。**`codex-plugin-cc` 就是 Agent Mesh 的第一个原型。**

---

## 七、对开发者的建议

如果你是一个使用 AI Agent 的开发者：

1. **开始试验跨 Agent 工作流。** 安装 `codex-plugin-cc`，尝试"用 Claude Code 写代码 + 用 Codex 审查"的组合。记录成本和时间，看看是否比单 Agent 更高效。

2. **关注 Agent 多路复用工具。** 如果你有多个 Agent 订阅（Claude Pro、ChatGPT Plus 等），herdr 类型的工具可以让你同时利用它们，而不是浪费闲置的配额。

3. **为你的项目定义 Agent 能力清单。** 无论使用什么平台，明确记录你的项目需要哪些 Agent 能力（代码生成、审查、测试、部署等），以及每个能力由哪个 Agent 提供。这会让你在平台之间迁移时更加从容。

4. **参与协议标准的讨论。** Agent 互操作性标准的制定窗口正在打开。现在是参与讨论、提出需求、影响方向的最佳时机。

---

## 八、结论：Agent 互操作性是 2026 年最重要的基础设施战役

回顾 2026 年上半年的 AI 行业，我们见证了模型能力的快速收敛（GLM-5.2 逼近 Opus）、编码 Agent 的爆发式增长（Claude Code、Codex、Cursor 三足鼎立）、以及 Agent Skills 生态的标准化尝试。

但所有这些都建立在一个未经检验的假设之上：**每个 Agent 都在自己的生态里工作。**

`codex-plugin-cc`、`herdr`、`gastown` 的出现打破了这个假设。它们告诉我们：**Agent 不应该被锁定在单一平台里。Agent 应该像微服务一样，可以互相调用、组合、编排。**

这场互操作性战役的赢家，可能不是拥有最强模型的公司，而是**定义了 Agent 之间如何对话的协议**。

就像 HTTP 定义了浏览器和服务器之间的对话方式，TCP/IP 定义了网络之间的互联方式——**下一个伟大的基础设施，可能是定义 Agent 之间如何协作的协议。**

而这一天，比大多数人想象的要近得多。

---

*本文基于 2026 年 7 月 6-7 日的 GitHub Trending、Hacker News、Hugging Face Blog 等公开信息撰写。所有项目和数据均来自公开来源。*

**参考资料：**
- [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) - Use Codex from Claude Code
- [ogulcancelik/herdr](https://github.com/ogulcancelik/herdr) - Agent multiplexer
- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) - Production-grade engineering skills
- [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) - Taste skill for AI
- [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) - Web scraping API for agents
- [martinalderson.com - GLM 5.2 and the upcoming AI margin collapse](https://martinalderson.com/posts/the-upcoming-ai-margin-collapse-part-1-glm-5-2/)
- [Hacker News Frontpage](https://news.ycombinator.com/)
- [Hugging Face Blog](https://huggingface.co/blog)
