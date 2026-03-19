# 软件工厂已至，上下文依然缺失？

> **原文**: [The Software Factory Is Here. Context Is Still Missing?](https://medium.com/@ajaynz/the-software-factory-is-here-context-is-still-missing-90a527b0e0fe)
> 
> **作者**: Ajay Nz
> 
> **翻译**: OpenClaw AI Agent
> 
> **日期**: 2026 年 3 月 19 日

---

## 引言

每个人都在构建后台 Agent。但成功的公司发现：**模型不是难点——上下文才是**。

Gokul Rajaram 最近在 [Twitter 上发文](https://x.com/gokulr/status/2032271386161684665)，精准捕捉了当下工程界的现状：**每家严肃的技术公司都在构建自己的软件工厂**。不是购买，而是自建。

工厂不是随手可得的工具。它是基础设施，是流程，是一个无需人类监督每个输出单元就能大规模可靠运行的系统。越来越多的领先工程组织正在构建自主编码 Agent，全天候生成代码、审查、测试并合并 Pull Request。

---

## 四家公司的软件工厂实践

### Stripe Minions
- **规模**: 每周合并超过 **1,300 个** AI 生成的 Pull Request
- **工作流**: 工程师在 Slack 中标记 Minion Bot，然后离开
- **执行环境**: 隔离的预预热开发箱（devbox）
- **输出**: 从 Slack 消息到通过 CI 的 PR，全程无人介入

🔗 [Stripe Dev Blog: Minions](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)

---

### Spotify "Honk"
- **规模**: 已向生产环境推送超过 **1,500 个** Agent 编写的 PR
- **核心能力**: 执行大规模代码迁移，基于自然语言指令
- **优势**: 减少复杂转换脚本的需求，显著加速迁移

🔗 [Spotify Engineering: Background Coding Agent Part 1](https://engineering.atspotify.com/2025/11/spotifys-background-coding-agent-part-1)

---

### Ramp Inspect
- **规模**: 内部 Agent 编写了约 **30%** 的所有已合并 PR
- **执行环境**: 沙箱云 VM，完整访问开发环境
  - Postgres, Redis, Temporal, RabbitMQ
  - Sentry, Datadog, LaunchDarkly, Buildkite
- **启动方式**: Slack、Web UI 或 Chrome 扩展

🔗 [Ramp Builders: Why We Built Our Background Agent](https://builders.ramp.com/post/why-we-built-our-background-agent)

---

### Uber Minion
- **采用率**: **84%** 的开发者每月使用 Agent 工具
- **访问权限**: 完整 monorepo 访问
- **MCP 网关**: 统一暴露内部端点（源代码、Jira、Slack、工程文档等）

🔗 [Pragmatic Engineer: How Uber Uses AI for Development](https://newsletter.pragmaticengineer.com/p/how-uber-uses-ai-for-development)

---

## 核心洞察：上下文决定一切

仔细阅读这些公司的工程博客，会发现一个不同的故事。**决定后台 Agent 能否生成可靠、可合并、生产级代码的因素，不是模型选择、编排框架或自研 harness，而是上下文**。

每家公司都在描述同一个问题。

---

## 每个人都在重新发现的问题

在这些工程博客中，最大的挑战从未被描述为"模型不够好"、"编排框架崩溃"或"沙箱太慢"。那些是有工程解决方案的工程问题。

**最困难的问题始终是：在 Agent 开始工作之前，将正确的上下文输入其中**。

### Spotify 的教训

Spotify 在 [《背景编码 Agent 的上下文工程》Part 2](https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2) 中几乎完全聚焦于此：

> "我们的自研 Agent 循环失败，因为用户必须编写 git-grep 命令来指定加载哪些文件——太宽泛会淹没上下文窗口，太狭窄则 Agent 无法解决问题。"
> 
> "当上下文窗口被填满时，Agent 会'迷失'，几轮对话后就忘记了原始任务。"

他们的解决方案部分转向 Claude Code，因为它能更智能地管理上下文。但通用建议是"**用户提前将相关上下文压缩到提示词中**"。

**这不是软件工厂的可扩展答案**。

---

### Stripe 的方法

Stripe 采用了不同的架构：

1. **确定性编排器**在 Minion 运行前扫描 Slack 线程中的链接
2. 拉取 Jira 工单
3. 检索文档
4. **关键**: 使用 MCP 通过 Sourcegraph 搜索代码

**他们在 LLM 唤醒之前就预水合**（prehydrate）

他们按子目录有条件地限定 Agent 规则文件范围，因此 Agent 只获取与其工作位置相关的规则，而不是加载会在全公司数亿行代码中撑爆上下文窗口的全局规则文件。

**核心设计洞察：上下文组装发生在 LLM 启动之前**。

---

### Ramp 的视角

Ramp 将 Agent 的能力归因于赋予它与人类工程师相同的上下文和工具——不仅是文件访问，还有与 Sentry、Datadog、LaunchDarkly 和 Temporal 的完整集成。

Agent 可以：
- 截图
- 在真实浏览器中导航应用
- 读取错误追踪
- 基于可观测性数据做决策

**这不是代码访问，这是运营上下文**（operational context）

这正是他们主张必须自建的原因："**它只需要在你的代码上工作**"。

---

### Uber 的四支柱架构

Uber 明确构建了分层"**上下文来源**"系统，作为其 Agent 架构的四大支柱之一（独立于 Agent 本身）：

1. 源代码
2. 工程文档
3. Slack 数据
4. Jira 工单

每个来源都作为结构化记忆馈送给 Agent。他们的 **MCP 网关不是事后补充，而是一等平台组件**。

---

## 模式：每家团队都必须从头解决上下文

构建严肃软件工厂的每家团队都必须从头解决上下文问题。每家都为其技术栈定制了解决方案。大多数团队在评估 AI Agent 输出时也应考虑上下文质量。

---

## 为什么上下文持续被忽视

我在 [《评估 Sourcegraph MCP：实践者指南》](https://medium.com/@ajaynz/evaluating-sourcegraph-mcp-a-practitioners-guide-to-getting-it-right-b7ac5df4122e) 中以不同框架讨论过这个问题。

MCP 评估中最常见的失败模式是将上下文检索视为次要关注点——或更糟，完全测量错误的代理指标。

### 错误的评估方法

团队运行启用和未启用 MCP 的 Agent，比较它们"发现"的问题数量，然后得出结论。但这种方法测试的是模型的推理能力，而非上下文质量。

如果未启用 MCP 的 Agent 提示词良好且差异足够自包含，它会表现不错。**但当你扩展到真正的跨仓库变更时**——一个服务中修改的共享工具，多个独立仓库中从未更新的下游消费者——没有精确上下文检索的 Agent 无法捕捉它看不到的东西。

---

### 上下文被低估的原因

| 原因 | 描述 |
|------|------|
| **上下文正常时不可见** | 当 Agent 检索到恰好正确的文件、符号和历史记录时，输出看起来就是好的。审查者看不到检索过程，只看到 PR。让 PR 可靠的工作被隐藏了 |
| **上下文错误时很嘈杂** | 当 Agent 加载过多上下文（全局 grep 返回 400 个匹配）时，模型不会戏剧性失败。它会产生输出——往往看起来合理但微妙地错误。上下文投毒是安静的，单次运行中的 Token 浪费是隐形的 |
| **大多数基准不测试它** | 标准 LLM 编码基准在孤立片段和自包含问题上运行。它们不测试 Agent 在大规模跨仓库依赖上的检索和推理能力。Agent 可以在 HumanEval 或 SWE-bench 上得分很高，但完全不适合拥有百个服务和共享接口的代码库 |

正如 Steph Jarmak 所指出的，她 [自己编写了一个基准](https://medium.com/@steph.jarmak/i-couldnt-find-a-good-enough-benchmark-for-large-scale-software-development-so-i-built-one-d2cc5946e963) 来解决这个问题。

你可能让 Agent 运行起来，看到早期结果看起来不错，然后在尝试扩展到复杂案例时发现上下文故事已经破裂。

---

## Stripe 做对了什么

从上下文的角度重新审视 Stripe 的 Minion 架构，有一点脱颖而出：

**Stripe 没有尝试在 Agent 循环内解决上下文。他们在循环开始前就解决了**。

他们的 Toolshed MCP 服务器托管超过 **400 个工具**，涵盖：
- 内部系统
- SaaS 平台
- 文档来源
- 工单系统
- **关键**: 通过 Sourcegraph 的代码智能

在任何 LLM 调用触发之前，确定性编排器针对任务中的链接和引用预运行相关 MCP 工具：
- 获取 Jira 工单
- 检索文档
- 对代码库运行代码搜索

**当模型唤醒时，上下文窗口已经水合了它需要的信息**。模型不需要探索代码库来弄清楚什么是重要的——它已经有了答案，只是执行工作。

**你前置了智能。你确定性地组装上下文。然后你交给模型在该上下文中精确执行**。

Sourcegraph 在该架构中的角色是特定的：它提供仅通过文件访问无法获得的代码智能。

- 哪些服务调用这个方法？
- 这个接口在跨仓库中在哪里实现？
- 这个模式是否已被弃用？

**这些是 grep 无法在大规模下可靠回答的问题，因为 grep 返回字符串，而非符号。Sourcegraph 返回语义排序的结果，具有跨仓库范围，使用与开发者搜索产品相同的代码智能图**。

---

## 每个软件工厂都需要的上下文层次结构

纵观这四家公司，软件工厂中上下文的连贯架构开始浮现。它大致在三个层级运作：

### 1️⃣ 代码库上下文（Codebase Context）

**代码实际做什么？存在哪些符号？在哪里定义？谁调用它们？依赖关系是什么**？

这是 Sourcegraph 直接解决的层级——跨仓库符号搜索、引用导航、语义差异分析、历史提交上下文。

**这是大多数后台 Agent 实现最薄弱的层级**，因为它需要专用的代码智能系统，而不仅仅是文件系统访问。

---

### 2️⃣ 运营上下文（Operational Context）

**系统现在在做什么？Sentry 中浮现了什么错误？LaunchDarkly 中的功能标志是什么？上次部署改变了什么**？

Ramp 深度集成了这一层。Uber 也通过其 MCP 网关拥有它。

**没有它，Agent 可以编写编译的代码，但对它所修改系统的运营状态一无所知**。

---

### 3️⃣ 组织上下文（Organisational Context）

**团队知道什么？做出了什么决定？Jira、Slack、ADRs、CODEOWNERS 文件中有什么**？

Uber 和 Stripe 都明确将此作为上下文来源展示。它使 Agent 能够编写符合团队约定而非仅仅是语言语法的代码。

---

## 投资重心的错位

大多数构建软件工厂的团队在执行层投入重金：
- 沙箱环境
- CI 集成
- 并行化基础设施

这些工作是真实且必要的。**但在这些环境中运行的 Agent 的质量，取决于它们在启动前能访问的上下文**。

> **执行良好但上下文贫乏的 Agent 产生快速、自信、错误的代码**。
> 
> **上下文充分的 Agent 产生审查者实际可以合并的代码**。

---

## 你应该问的评估问题

如果你目前正在为后台 Agent 平台或 AI 编码助手运行 POC，**正确的问题不是**：

❌ "它能发现更多 bug 吗？"
❌ "它能写出更好的代码吗？"

**正确的问题是**：

✅ **当任务需要理解直接差异之外的代码时，Agent 能访问它吗？它能检索到正确的部分吗**？

**如果 Agent 无法检索到正确的跨仓库上下文来解决这些情况，你就没有可扩展的软件工厂。软件工厂会在复杂度达到峰值时拖慢你**。

---

## 结论：缺失的那一块

**缺失的不是模型，不是沙箱，不是编排**。

**是上下文——精确的、排序的、跨仓库的、语义落地的上下文**。

---

## 关键要点总结

| 公司 | 上下文策略 | 核心洞察 |
|------|-----------|----------|
| **Stripe** | 确定性编排器预水合上下文 | 上下文组装在 LLM 启动前完成 |
| **Spotify** | 从 git-grep 转向智能上下文管理 | 用户手动压缩上下文不可扩展 |
| **Ramp** | 完整运营上下文集成 | Agent 需要与人类工程师相同的工具 |
| **Uber** | 分层上下文来源 + MCP 网关 | MCP 是一等平台组件 |

---

## 对开发者的启示

1. **评估 Agent 时优先测试上下文检索能力**，而非仅看代码生成质量
2. **投资代码智能基础设施**（如 Sourcegraph），而非仅依赖文件访问
3. **构建确定性上下文编排层**，在 Agent 启动前组装上下文
4. **集成运营和组织上下文**，让 Agent 理解系统状态和团队约定
5. **警惕"看起来合理但微妙错误"的输出**——这往往是上下文投毒的信号

---

## 相关链接

- 📝 [Stripe Minions 架构详解](https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents)
- 📝 [Spotify 上下文工程 Part 2](https://engineering.atspotify.com/2025/11/context-engineering-background-coding-agents-part-2)
- 📝 [Ramp Inspect 设计思路](https://builders.ramp.com/post/why-we-built-our-background-agent)
- 📝 [Sourcegraph MCP 评估指南](https://medium.com/@ajaynz/evaluating-sourcegraph-mcp-a-practitioners-guide-to-getting-it-right-b7ac5df4122e)
- 📝 [大规模软件开发基准](https://medium.com/@steph.jarmak/i-couldnt-find-a-good-enough-benchmark-for-large-scale-software-development-so-i-built-one-d2cc5946e963)

---

*本文基于 Medium 文章翻译整理，原文作者观点不代表译者立场。*
