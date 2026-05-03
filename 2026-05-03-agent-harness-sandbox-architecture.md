# Agent Harness 架构抉择：沙箱内 vs 沙箱外

**文档日期：** 2026 年 5 月 3 日  
**标签：** AI Agent, Agent Architecture, Sandbox, Harness Engineering, Multi-Agent, Production Infrastructure

---

## 一、引言：一个正在撕裂社区的问题

2026 年 5 月初，Hacker News 首页出现了一篇引发激烈讨论的文章：

> **"The agent harness belongs outside the sandbox"**
>
> 45 points，33 comments，社区意见两极分化。

与此同时，GitHub Trending 上出现了多个 Agent Harness 相关项目：

| 项目 | 语言 | Stars | 日增 |
|------|------|-------|------|
| [ruvnet/ruflo](https://github.com/ruvnet/ruflo) | TypeScript | 36,772 | 1,299 |
| [1jehuang/jcode](https://github.com/1jehuang/jcode) | Rust | 2,830 | 482 |
| [browserbase/skills](https://github.com/browserbase/skills) | JavaScript | 1,499 | 346 |

这些数字背后有一个共同的信号：**Agent Harness 正在从"实现细节"变为"架构决策"**。

过去两年，我们讨论 Agent 架构时，注意力集中在模型选择、提示工程、工具调用策略上。但 2026 年上半年的实践告诉我们，一个更基础的问题正在浮出水面：

**Agent 的控制循环（harness loop）应该运行在哪里？**

这个问题的答案，决定了你的 Agent 系统的安全性、可扩展性、成本结构和运维复杂度。而且——大多数人在一开始根本没想过这个问题。

这篇文章要深入分析两种架构模式的核心差异、工程取舍，以及为什么 2026 年的实践正在推动行业走向"沙箱外 Harness"。

---

## 二、什么是 Agent Harness？

在深入架构之前，先明确概念。

**Agent Harness 是驱动 LLM 的控制循环。** 它做的事情看似简单，实则构成了 Agent 的全部骨架：

```
┌─────────────────────────────────────────────┐
│              Agent Harness Loop              │
│                                              │
│  1. 发送 prompt → LLM                        │
│  2. 接收 response（含 tool calls）            │
│  3. 执行 tool calls（bash, read, write...）   │
│  4. 将结果反馈给 LLM                          │
│  5. 重复，直到模型说"我完成了"                  │
│                                              │
└─────────────────────────────────────────────┘
```

每个生产级 Agent 都有一个 Harness。无论是 Claude Code、Cursor、Codex CLI，还是你自己构建的内部系统——区别只在于：**这个循环跑在哪里。**

---

## 三、两种架构模式

### 3.1 模式 A：Harness 在沙箱内

```
┌──────────────────────────────────────────┐
│              Sandbox Container            │
│  ┌────────────────────────────────────┐   │
│  │       Agent Harness Process         │   │
│  │                                     │   │
│  │  ┌──────┐  ┌──────────┐  ┌───────┐ │   │
│  │  │ LLM  │→ │ Tool     │→ │ Loop  │ │   │
│  │  │ API  │  │ Executor │  │ State │ │   │
│  │  └──────┘  └──────────┘  └───────┘ │   │
│  │                                     │   │
│  │  .claude/skills/  .claude/memory/   │   │
│  │  project files                      │   │
│  └────────────────────────────────────┘   │
│                                            │
│  LLM API keys → INSIDE sandbox ⚠️          │
│  User tokens → INSIDE sandbox ⚠️           │
│  DB credentials → INSIDE sandbox ⚠️        │
└──────────────────────────────────────────┘
```

**这是大多数个人开发者接触到的模式。** 当你在笔记本上运行 Claude Code 时，或者在远程容器里启动一个 Agent 时——Harness 和代码运行在同一个容器中。

**优势：**
- 执行模型简单：一个容器，一个进程树，一个文件系统，一个生命周期
- 可复用现成的 Harness：Claude Code SDK、OpenClaw 等开箱即用
- Skills 和 Memories 是本地文件，直接读写，零额外抽象

**劣势：**
- 凭据暴露在沙箱内：LLM API keys、用户 token、数据库访问都在容器里
- 沙箱 = 会话：沙箱挂了，会话就没了，没有恢复能力
- 无法空闲回收：Harness 在沙箱内运行，你没法在 Agent 思考时暂停沙箱
- 多用户是噩梦：多个工程师共享同一个 Agent 时，变成分布式文件系统问题

### 3.2 模式 B：Harness 在沙箱外

```
┌───────────────────────────┐       ┌──────────────────────┐
│   Backend Server          │  API  │  Sandbox Container    │
│                           │◄─────►│                       │
│  ┌─────────────────────┐  │       │  ┌────────────────┐   │
│  │  Agent Harness      │  │       │  │  Tool Executor │   │
│  │                     │  │       │  │  (bash, read,  │   │
│  │  ┌──────┐           │  │       │  │   write)       │   │
│  │  │ LLM  │           │  │       │  └────────────────┘   │
│  │  │ API  │           │  │       │                       │
│  │  └──────┘           │  │       │  project files        │
│  │                     │  │       │                       │
│  │  ┌───────────────┐  │  │       └──────────────────────┘
│  │  │ Inngest/Temporal│  │
│  │  │ (Durable Exec) │  │       ┌──────────────────────┐
│  │  └───────────────┘  │       │  Database              │
│  │                     │       │                        │
│  │  LLM API keys ✓     │       │  Skills (shared)       │
│  │  User tokens ✓      │       │  Memories (org-wide)   │
│  │  DB credentials ✓   │       │  Session state         │
│  └─────────────────────┘       └──────────────────────┘
```

**这是面向多用户、生产级系统的架构选择。** Harness 运行在你的后端服务上，当需要执行工具时，通过 API 调用沙箱。沙箱只负责执行命令，不包含任何凭据。

**优势：**
- 凭据隔离：LLM API keys、用户 token 永远不进沙箱
- 沙箱可回收：Agent 不执行命令时，沙箱可以暂停或销毁
- 故障恢复：沙箱挂了，Harness 可以启动新沙箱继续工作
- 多用户天然支持：共享状态通过数据库而非分布式文件系统

**劣势：**
- 现成 Harness 不能直接用：它们都假设本地文件系统
- 需要解决持久化执行（durable execution）问题
- 文件系统访问需要虚拟化抽象

---

## 四、三大核心工程挑战

选择"沙箱外 Harness"架构后，你会遇到三个必须解决的工程问题。这也是那篇 HN 文章的核心贡献——它不仅提出了问题，还给出了实际解决方案。

### 4.1 挑战一：持久化执行（Durable Execution）

**问题：** Agent 循环是一个长时间运行的函数。短则几分钟，长则数小时。它必须能承受滚动部署、扩缩容和实例故障。把循环放在 API 服务器的内存里，第一次部署新版本时就会崩溃。

**行业实践对比：**

| 方案 | 特点 | 适用场景 |
|------|------|----------|
| **Inngest** | Serverless 函数，每步 checkpoint，无需自建集群 | 中小规模，快速迭代 |
| **Temporal** | 工业级工作流引擎，强大的状态管理 | 大规模，复杂编排 |
| **自定义消息队列** | 灵活但需要自建可靠性和 checkpoint 机制 | 有特殊需求的团队 |
| **内存 + 重启恢复** | 最简单但最脆弱，部署即丢失状态 | 个人开发，非生产 |

**关键洞察：** 不需要 Temporal 的全部能力。Inngest 的 DX 和零运维已经能满足大多数 Agent Harness 的持久化需求。每步 checkpoint 意味着服务器重启后，循环可以从断点继续。

```python
# 伪代码：基于 Inngest 的 Agent Harness
@inngest.function()
async def agent_loop(ctx, session_id: str):
    state = await ctx.run("load_state", load_session_state, session_id)
    
    while not state.done:
        # 每步 checkpoint
        response = await ctx.run("llm_call", call_llm, state.messages)
        state.messages.append(response)
        
        if response.tool_calls:
            for tool_call in response.tool_calls:
                result = await ctx.run(
                    f"execute_{tool_call.name}",
                    execute_tool_in_sandbox,
                    sandbox_id=state.sandbox_id,
                    tool=tool_call
                )
                state.messages.append(result)
        
        await ctx.run("save_state", save_session_state, session_id)
```

### 4.2 挑战二：沙箱生命周期管理

**问题：** Harness 大部分时间是暂停的——在等待 LLM 响应、在工具调用之间、在等 CI 完成。我们希望沙箱也能跟着暂停，只在 Agent 真正需要执行命令时激活。但冷启动需要数秒，在交互式会话中这是不可接受的延迟。

**关键指标：25ms 恢复时间**

实践表明，使用 Blaxel 等沙箱管理平台，可以实现 **25ms 从待机状态恢复**。这个延迟低到 Agent 几乎察觉不到沙箱曾经消失过。

```
时间线：
t=0ms    Agent 发出 tool call 请求
t=5ms    Harness 收到请求，检查沙箱状态
t=10ms   沙箱处于 standby，发送 resume 信号
t=35ms   沙箱恢复完成，开始执行命令
t=200ms  命令执行完成，返回结果
t=205ms  Harness 将结果反馈给 LLM
t=...    等待 LLM 响应（沙箱自动 standby）
```

**对比：如果 Harness 在沙箱内：**
- 无法在 LLM 调用期间暂停沙箱（因为 Harness 就在沙箱里运行）
- 闲置期间持续消耗计算资源
- 无法实现"按需供给"的资源模型

**成本影响估算：**

假设一个 Agent 会话平均持续 30 分钟，其中：
- 25% 的时间在真正执行命令
- 75% 的时间在等待（LLM 调用、用户交互、CI）

| 模式 | 资源使用 | 30 分钟会话成本 |
|------|----------|-----------------|
| Harness 在沙箱内 | 全程运行 | 100% |
| Harness 在沙箱外 | 按需激活 | ~25-30% |

**对于大规模部署，这是一个 3-4 倍的成本差异。**

### 4.3 挑战三：文件系统虚拟化

**这是最复杂、也最有创意的问题。**

现代 Agent Harness 不止是 bash + LLM。它们有：
- **Skills**：按需读取的 prompt 片段（`.claude/skills/foo.md`）
- **Memories**：Agent 为自己或用户写的笔记（`.claude/memory/MEMORY.md`）
- **Subagents**：子代理
- **Plans**：计划和待办列表

这些东西都假设存在一个**本地文件系统**。Skill 是一个文件，Memory 是一个文件。Harness 用同样的 read/write 工具读写它们，就像读写源代码一样。

**这在笔记本上完美运行。但当 Harness 在沙箱外时，文件系统不再是"一个可以指向的东西"。**

#### 方案对比

| 方案 | 复杂度 | 多用户一致性 | 性能 |
|------|--------|-------------|------|
| **保持沙箱持久化** | 低 | 差（每个会话独立） | 高 |
| **退出时同步到 DB** | 中 | 差（最终一致性） | 中 |
| **增加 memory_read/write 工具** | 中 | 好 | 低（工具稀释注意力） |
| **文件系统虚拟化** | 高 | 好 | 高 |

#### 文件系统虚拟化：一接口，两后端

最优雅的解决方案是**虚拟化文件系统访问**：

```
Agent 调用 read(path)
         │
         ▼
┌─────────────────────────┐
│    Harness 路由层         │
│                          │
│  path 分析：              │
│  - workspace/* → 沙箱     │
│  - skills/*  → 数据库     │
│  - memory/*  → 数据库     │
└────────┬────────────────┘
         │
    ┌────┴────┐
    ▼         ▼
  沙箱      PostgreSQL
  (项目文件)  (skills + memories)
```

Agent 不知道区别。对它来说，只有一个文件系统，它读和写文件。只是——有些文件存在于 Postgres 中，有些存在于远在千里之外的沙箱里。

**为什么不能直接加 memory_read 和 memory_write 工具？**

两个原因：

1. **工具越多，Agent 越差。** 每个工具都会稀释模型对其他工具的注意力，让 prompt 变长，增加模型每次需要做的决策。两个几乎一样的工具（`read` 和 `memory_read`）尤其糟糕——模型必须从上下文中区分它们，而且经常会选错。

2. **模型是在特定的 API 面上训练的。** Anthropic 和其他前沿模型厂商几乎肯定在类似 Claude Code 的 Harness 上做强化学习。这种训练让模型擅长特定的接口：`read(path)`、`write(path, content)`、`edit(path, old, new)`。如果你发明 `memory_read`，你就偏离了训练路径——你得到的是模型的一般能力，减去它针对精确约定学到的优化。

**文件系统虚拟化保留了模型训练时使用的 API 面，把复杂性推给了基础设施层。这就是正确的抽象层级。**

---

## 五、GitHub Trending 的信号

今天 GitHub 上的趋势进一步强化了这个架构判断：

### jcode：用 Rust 重写 Harness 的性能革命

[jcode](https://github.com/1jehuang/jcode) 是一个用 Rust 编写的 Coding Agent Harness，它的性能数据令人震惊：

| 工具 | 1 会话内存 | 10 会话内存 | 启动时间 |
|------|-----------|------------|----------|
| **jcode** | 27.8 MB | 117.0 MB | **14.0 ms** |
| Claude Code | 386.6 MB | 2,300.6 MB | 3,436.9 ms |
| Cursor Agent | 214.9 MB | 1,632.4 MB | 1,949.7 ms |
| OpenCode | 371.5 MB | 3,237.2 MB | 1,035.9 ms |

**jcode 比 Claude Code 快 245 倍启动，每个额外会话只增加 ~9.9 MB 内存。** 这不是微调——这是架构层面的重写。

jcode 还内置了语义记忆系统：每个 turn/response 被嵌入为语义向量，通过余弦相似度查询记忆图谱，实现了"类人"的自动回忆能力——Agent 不需要主动调用记忆工具，就能把相关信息注入对话。

### ruflo：企业级多 Agent 编排

[ruflo](https://github.com/ruvnet/ruflo) 已经达到了 **36,772 stars**，它的架构明确采用了"Harness 在外"模式：

- 分布式蜂群智能（swarm intelligence）
- RAG 集成
- 原生 Claude Code / Codex 集成
- 企业级架构

它的成功说明了一个趋势：**开发者正在寻找能规模化运行 Agent 的基础设施，而不只是在本地跑个 CLI。**

---

## 六、架构决策矩阵

什么时候选哪种架构？以下是一个实用的决策框架：

```
                        多用户？
                       /         \
                     是           否
                    /              \
              需要共享状态？      个人使用？
             /            \         /     \
           是             否      简单     需要
          /                \     场景     安全
         /                  \    /         \
    Harness 外          Harness 外      Harness 内
    (DB 共享)           (虚拟化 FS)     (本地容器)
```

**具体建议：**

| 场景 | 推荐架构 | 理由 |
|------|---------|------|
| 个人开发笔记本 | Harness 在沙箱内 | 简单，无运维 |
| 远程开发容器（单人） | Harness 在沙箱内 | Claude Code SDK 即用 |
| 团队共享 Agent（< 10 人） | Harness 在沙箱外 | 凭据安全 + 共享状态 |
| 企业级 Agent 平台 | Harness 在沙箱外 | 所有优势都需要 |
| Agent-as-a-Service | Harness 在沙箱外 | 多租户隔离 + 成本控制 |

---

## 七、更深层的思考：Harness 架构如何影响 Agent 能力

Harness 在哪里运行，不只是一个工程决策。它深刻影响 Agent 能做什么。

### 7.1 安全边界的重新定义

当 Harness 在沙箱内，"安全"意味着在沙箱里限制权限。但 Agent 的 prompt injection、工具调用滥用等问题，很难在沙箱内完全防范。

当 Harness 在沙箱外，沙箱变成了**纯执行环境**——它没有任何凭据、任何外部访问能力。即使 Agent 被 prompt injection 攻破，它也只能接触到被隔离的工作目录。真正的攻击面在 Harness 层，而 Harness 层是人类代码控制的，可以做更精细的审计和策略执行。

### 7.2 跨沙箱协作

Harness 在外让一个有趣的模式成为可能：**一个 Agent 会话可以在不同时间点使用不同的沙箱。**

- 编译代码时用带编译器的沙箱
- 跑测试时用带测试框架的沙箱
- 部署时用带部署工具链的沙箱

每个沙箱都是临时的、专用的、最小权限的。Harness 作为协调者，根据需要创建和销毁它们。这在 Harness 在内的架构中几乎不可能实现。

### 7.3 可观测性的质的飞跃

当 Harness 在沙箱外，所有的 LLM 调用、工具执行、状态变化都经过后端。这意味着：

- 完整的审计日志：谁在什么时候让 Agent 做了什么
- 实时监控：Agent 的性能、成本、错误率
- A/B 测试：不同模型、不同 scaffold 在同一任务上的对比
- 回放调试：重现任何 Agent 会话的完整执行轨迹

这些都是 Harness 在沙箱内时要么不可能、要么成本极高的能力。

---

## 八、行业趋势：2026 年的 Harness 战争

回顾 2026 年上半年的行业动态：

1. **OpenClaw** 从个人助手演变为平台，Harness 架构是其核心
2. **Anthropic** 在 Claude Code 中持续优化本地 Harness 体验
3. **Microsoft** 的 VS Code Copilot 争议（自动添加 `Co-Authored-by` 引发 555 points 的 HN 热帖）提醒我们：Agent 与开发者的交互边界正在被重新定义
4. **IBM Research** 的 VAKRA 基准测试显示，现有 Agent 在企业环境中的推理和工具使用能力仍然堪忧
5. **Hugging Face** 的评估成本分析揭示：Agent 评估正在吞噬推理成本

所有这些信号指向同一个结论：**Harness 不再是实现细节，而是 Agent 产品的核心竞争力。**

谁能做出更好的 Harness 架构——更安全、更高效、更可观测、更易扩展——谁就能在 Agent 基础设施的竞争中胜出。

---

## 九、总结：架构决定上限

Agent Harness 的位置选择，不是一个可以后期重构的决策。它从第一天就决定了：

- 你的安全模型是什么样的
- 你的成本结构是什么样的
- 你的多用户能力是什么样的
- 你的可观测性是什么样的

2026 年的实践正在给出明确的答案：

> **对于任何需要走向生产的 Agent 系统，Harness 应该在沙箱外。**
>
> 本地开发可以继续用沙箱内的简单模式——但当你的 Agent 服务多个用户、处理敏感数据、需要可扩展时，"Harness 在外"不是一个可选项，而是必选项。

这不是一场理论争论。它是正在发生的架构演进。那些早期做出正确选择的团队，已经在享受凭据隔离、弹性沙箱、共享状态带来的红利。而那些忽略这个问题的团队，迟早会在多用户场景、安全审计、成本控制上付出代价。

**Harness 架构决定了你的 Agent 能走多远。** 在开始构建之前，想清楚这个问题。

---

## 参考资源

- [The agent harness belongs outside the sandbox](https://www.mendral.com/blog/agent-harness-belongs-outside-sandbox) - Mendral 团队的技术博客
- [1jehuang/jcode](https://github.com/1jehuang/jcode) - Rust 编写的下一代 Coding Agent Harness
- [ruvnet/ruflo](https://github.com/ruvnet/ruflo) - Claude 多 Agent 编排平台
- [browserbase/skills](https://github.com/browserbase/skills) - Claude Agent SDK + Web Browsing
- [AI evals are becoming the new compute bottleneck](https://huggingface.co/blog/evaleval/eval-costs-bottleneck) - Hugging Face 博客
- [Inside VAKRA: Reasoning, Tool Use, and Failure Modes of Agents](https://huggingface.co/blog/ibm-research/vakra-benchmark-analysis) - IBM Research
- [Holistic Agent Leaderboard (HAL)](https://hal.cs.princeton.edu/) - Princeton 的 Agent 基准测试平台
