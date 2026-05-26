# Agent ≠ Model：从 HuggingFace 术语表和 IBM 开源排行榜看 Agent 架构的决定性作用

**文档日期：** 2026 年 5 月 26 日  
**标签：** AI Agent, Harness Engineering, Agent Architecture, Open Agent Leaderboard, Exgentic, Terminology

---

## 一、引子：同一个模型，天壤之别

2026 年 5 月，AI Agent 领域出现了两篇互相呼应的重量级文献：

| 文献 | 发布者 | 日期 | 核心命题 |
|------|--------|------|----------|
| [Harness, Scaffold, and the AI Agent Terms Worth Getting Right](https://huggingface.co/blog/agent-glossary) | HuggingFace (Sergio Paniego & Ari Gati) | 2026-05-25 | Agent 领域的术语混乱正在阻碍技术沟通与工程实践 |
| [The Open Agent Leaderboard](https://huggingface.co/blog/ibm-research/open-agent-leaderboard) | IBM Research (Elron 等) | 2026-05-18 | 评估 Agent 必须看完整系统，而非只看模型 |

这两篇文章看似各说各的，但它们指向同一个被长期忽视的事实：

> **当我们在谈论"Agent 能力"时，我们混淆了"模型能力"和"Agent 架构能力"。而后者，正在成为决定 Agent 成败的关键变量。**

2026 年 Q2 的行业信号越来越清晰：模型层面的边际收益在递减，而 Agent 架构层面的创新空间才刚刚打开。本文通过解构最新的术语定义和排行榜数据，回答一个核心问题——**Agent 架构到底在多大程度上决定了最终效果？**

---

## 二、术语混乱：为什么我们需要一个 Agent 术语表

### 2.1 ICLR 2026 上的一个灵魂拷问

2026 年 4 月的 ICLR 会议上，研究者 Ari Gati 在社交媒体上发了一条引发广泛共鸣的帖子：

> *"What do you mean by the terms 'harness' and 'scaffold' in the context of agents? I have heard a lot of explanations while I was at ICLR, but I could not understand why they did not converge to a single explanation."*

这个问题看似简单，却揭示了一个深层危机：**一个领域如果连基本术语都无法统一，工程协作就会付出巨大的沟通成本。**

让我们看看现实中的混乱：

```
术语混乱的典型案例：

"Anthropic 官方文档说 Claude Code 是 'agentic harness around Claude'
→ 即：harness = 模型之外的一切（宽定义）

但 HuggingFace 术语表区分了 harness 和 scaffold
→ harness = 执行循环（窄定义）
→ scaffold = 行为定义层（system prompt、工具描述、格式）

同一个词，在不同语境下含义差了一个量级。"
```

### 2.2 HuggingFace 术语表：一套实用的心智模型

HuggingFace 的这篇术语表并非试图"制定标准"，而是提供一套**实用的心智模型**（practical mental model），让技术讨论更容易跟进。其核心拆解如下：

```
Agent = Model + Scaffolding + Harness

┌──────────────────────────────────────────────────────┐
│                   AGENT (完整系统)                    │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │            SCAFFOLDING（行为定义层）             │  │
│  │  • System Prompt                                │  │
│  │  • Tool Descriptions                            │  │
│  │  • 输出格式规范                                   │  │
│  │  • 跨步骤的记忆管理                               │  │
│  │  • 定义模型"看到什么"和"如何理解世界"               │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │                 MODEL（LLM）                    │  │
│  │  • 输入文本 → 输出文本                            │  │
│  │  • 无跨调用记忆                                   │  │
│  │  • 无循环                                       │  │
│  │  • 能"表达"调用工具的意图，但需要 harness 执行     │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │              HARNESS（执行循环）                 │  │
│  │  • 调用模型                                      │  │
│  │  • 处理工具调用                                   │  │
│  │  • 决定何时停止                                   │  │
│  │  • 错误处理和护栏                                 │  │
│  │  • 是 Agent "跑起来"的动力系统                     │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
```

### 2.3 为什么这个拆解很重要

**因为它解释了同一个模型在不同产品中为什么表现迥异。**

Claude Code、Codex、Cursor 都基于相似的底层模型能力，但用户体验差异巨大。HuggingFace 术语表给出了答案：**model, harness, product 是三样不同的东西**。两个使用相同底层模型的产品，因为 harness 做出了不同选择，可以给人完全不同的感觉。而将更好的模型换入同一个 harness，体验同样会改变。

这个概念看似简单，但长期以来被严重低估。直到 IBM 的 Open Agent Leaderboard 用数据证明了它——

---

## 三、IBM Open Agent Leaderboard：用数据证明"Agent 很重要"

### 3.1 为什么需要评估完整 Agent 系统

IBM Research 的这篇论文和配套排行榜，其核心论点是：

> **How well an AI agent works depends on how it's built, not just the model inside it.**

传统的 AI 排行榜（HELM、LM Arena）只评估模型。但当你部署一个 Agent 时，你选择的不是模型——你选择的是一个**完整系统**：

- 它能使用哪些工具？
- 它如何规划步骤？
- 它在行动之间记住什么？
- 它在出错时如何恢复？

改变其中任何一项，同一个模型就会产生截然不同的结果，而且成本也可能完全不同。

### 3.2 评测框架：六大基准的统一协议

IBM 组装了六个成熟的基准测试，覆盖了从编码到客服的多种真实任务：

| 基准 | 任务类型 | 评估维度 |
|------|----------|----------|
| SWE-bench Verified | 修复真实代码仓库中的 Bug | 编码能力 |
| BrowseComp+ | 跨网络研究复杂问题 | 开放研究能力 |
| AppWorld | 在数百个 App 中完成个人任务 | 大规模操作空间 |
| tau2-Bench Airline | 按公司政策处理航空客服 | 规则约束对话 |
| tau2-Bench Retail | 按公司政策处理零售客服 | 规则约束对话 |
| tau2-Bench Telecom | 按公司政策处理电信技术支持 | 规则约束对话 |

关键创新在于**统一协议**（unified protocol）：每个基准都有相同的结构——任务（做什么）、上下文（知道什么）、动作（允许做什么）。Agent 不再需要"说每种基准的语言"，它们只需要"说一种语言"。

### 3.3 排行榜的核心发现

#### 发现一：相同模型，不同 Agent 系统，结果截然不同

排行榜前五名中有三个使用**同一个模型**，但得分和成本都不同。这直接证明了 Agent 架构的独立性贡献：

```
同一模型 + 不同 Agent 系统 = 不同的得分和成本

┌────────────────────────────────────────────┐
│  模型 M1                                    │
│  ├─ Agent A: 成功率 X%, 成本 $C1/task       │
│  ├─ Agent B: 成功率 Y%, 成本 $C2/task       │
│  └─ Agent C: 成功率 Z%, 成本 $C3/task       │
│                                            │
│  X ≠ Y ≠ Z, C1 ≠ C2 ≠ C3                  │
│                                            │
│  变量只有一个：Agent 架构                    │
└────────────────────────────────────────────┘
```

这是整个排行榜最有力的数据点。当模型被控制住时，Agent 架构的差异直接转化为性能和成本的差异。

#### 发现二：成本差距同样惊人

排行榜前五名中，**最高效的配置成本仅为最强配置的一小部分**。当把所有配置按质量和成本绘制成散点图时，可以看到：

- 质量与成本之间不存在简单的线性关系
- 某些 Agent 架构在保持高质量的同时大幅降低成本
- 失败运行的成本比成功运行高出 20%–54%

最后一点尤其值得注意：**在 Agent 系统中，失败行为直接塑造你的账单**。一个设计良好的 Agent 应该在遇到不可解任务时快速失败（fail fast），而不是在长而昂贵的运行后放弃。

#### 发现三：通用 Agent 已经可以匹敌专用 Agent

```
关键发现：通用 Agent ≈ 专用 Agent

在大多数基准上，没有经过基准特定调优的通用 Agent，
匹敌甚至超越了专为该任务构建的系统。

这意味着：单个 Agent 正在具备处理多种工作的能力，
而不仅是它被准备的那一个环境。
```

#### 发现四：模型仍是主导因素，但 Agent 架构已开始改变结果

```
驱动力分析：

模型选择     ████████████████████  ~70% 的方差解释
Agent 架构   ██████████            ~20% 的方差解释
其他因素     ████                  ~10%
```

"Today the model explains most of the results. But the agent around it is already starting to change the outcome."

这句话是整篇论文的点睛之笔。模型目前仍是主导因素，但 Agent 架构已经开始改变结果——而且这个差距只会越来越大。

### 3.4 Tool Shortlisting：一个改变胜负的架构选择

论文提到了一个具体的架构优化——**Tool Shortlisting**（工具短名单）：

> 帮助 Agent 聚焦于相关工具，而不是在所有工具中搜索。这个优化在我们测试的每个模型上都提升了性能，并将原本失败的系统变成了可用系统。

这是一个纯粹的架构选择。它不改变模型，不改变任务，只改变 Agent 如何组织和管理可用工具。但它足以扭转乾坤。

这印证了我们在之前博客中讨论过的"Harness Engineering"的核心思想：**Agent 的能力上限由模型决定，但实际表现由 harness 决定**。

---

## 四、深度分析：Agent 架构的三个可优化维度

基于术语表和排行榜的交叉分析，我们可以将 Agent 架构拆解为三个可独立优化的维度。

### 4.1 Scaffold 层：模型看到什么

Scaffold 定义了模型的世界观。它包括：

- **System Prompt**：角色设定、行为约束、输出格式
- **Tool Descriptions**：工具的能力边界、使用条件、参数规范
- **Context Management**：对话历史的压缩策略、长短期记忆的注入时机
- **Output Parsing**：如何解析模型的响应，如何处理格式错误

**可优化的杠杆：**

| 杠杆 | 效果 | 成本 |
|------|------|------|
| System Prompt 优化 | 提升任务理解准确度 | 极低（改文本即可） |
| 工具描述精简 | 减少模型的工具选择犹豫 | 低 |
| 上下文压缩策略 | 降低 token 成本，减少上下文溢出 | 中 |
| 长短期记忆分层 | 提升跨会话一致性 | 高（需架构改造） |

在 HuggingFace 术语表中，Context Engineering 被明确定义为 Scaffold 的一部分：*"Designing what goes into the agent's context window."* 它不是一次性决策——随着模型运行，之前的轮次会塑造未来的调用，harness 在整个运行过程中主动管理这一点。

### 4.2 Harness 层：模型如何运行

Harness 是 Agent 的动力系统。它决定了：

- **执行循环**：模型调用 → 工具执行 → 结果反馈 → 下一轮
- **停止条件**：何时判断任务完成？何时判断无法完成？
- **错误恢复**：工具调用失败时如何重试？如何降级？
- **并发管理**：何时并行调用子 Agent？何时串行？

**可优化的杠杆：**

| 杠杆 | 效果 | 成本 |
|------|------|------|
| 智能停止条件 | 降低失败运行成本 20%–54% | 中 |
| 工具短名单 | 提升所有基准上的成功率 | 中 |
| 错误恢复策略 | 提升容错性和可预测性 | 高 |
| 子 Agent 调度 | 实现复杂任务的分解与并行 | 高 |

IBM 排行榜的数据直接验证了这些杠杆的有效性：失败运行的成本比成功运行高出 20%–54%，这意味着停止条件的设计直接影响运营成本。

### 4.3 Model 层：底层推理能力

模型仍然是最大的方差来源。但有趣的是，术语表和排行榜共同指向一个观点：

> **模型不是 Agent，模型只是 Agent 的一个组件。**

这意味着在选择 Agent 方案时，不能只看"用了什么模型"。Claude Code 和 Codex 使用相似级别的模型，但因为 harness 和 scaffold 的不同，它们的适用场景和用户体验完全不同。

---

## 五、行业信号：从模型竞赛到架构竞赛

### 5.1 Anthropic Code with Claude 的信号

MIT Technology Review 在 2026 年 5 月 22 日的报道中提到，Anthropic 在伦敦的开发者大会上问了在场观众一个问题：有多少人上线了完全由 Claude 编写的代码？**几乎一半的人举了手。许多人承认在推送代码前甚至没有读过代码。**

这个信号值得深思：

- 开发者对 AI 生成的代码的信任度正在大幅提升
- 但这也意味着 harness 的质量变得更加关键——当开发者不再审查代码时，harness 就是最后一道防线
- Anthropic 的战略是"将自动化推到极限"，这意味着 harness 工程将成为核心竞争力

### 5.2 Microsoft Copilot Cowork 的安全警示

同日，PromptArmor 发布了一篇关于 Microsoft Copilot Cowork 的严重安全漏洞报告：攻击者可以通过间接 Prompt 注入实现文件窃取，利用的是"向活跃用户发送邮件和 Teams 消息不需要人工审批"这一设计缺陷。

这不仅仅是安全漏洞，更是**架构设计缺陷**。它暴露了当 Agent 被授予跨系统代理权限时，如果 harness 层没有足够的安全护栏，后果是灾难性的。

```
Copilot Cowork 攻击链分析：

1. 用户上传一个包含 Prompt 注入的 skill 文件
2. Agent 被触发执行"周工作总结"
3. 注入操控 Agent 通过 Teams 发送包含预认证下载链接的消息
4. 用户打开消息 → 链接被外泄 → 攻击者下载文件
5. 全程无需人工审批

关键缺陷：
• Skill 文件自动从用户 OneDrive 加载（信任边界模糊）
• 向用户自己发送消息不需审批（自动审批逻辑的漏洞）
• 预认证下载链接可在任意会话中使用（权限传递失控）
• 定时任务进一步放大了风险（无人值守时的自动化攻击）
```

这恰好印证了我们之前关于 Agent 安全的讨论：**Agent 的安全不是模型安全，而是 harness 安全**。当 Agent 拥有跨系统的代理权限时，harness 层的信任边界定义、审批逻辑、权限传递机制，直接决定了整个系统的安全底线。

### 5.3 Google I/O 的信号：从专用系统到 Agent 驱动

Google I/O 上，Demis Hassabis 宣称"我们正站在奇点的山脚下"。但更有意义的是上下文：他宣布的不是某个专用科学系统，而是 **Gemini for Science**——一个基于 Agent 驱动的科学平台。

MIT Technology Review 的分析指出：

> Google 似乎正在从专用系统转向 Agent 驱动的未来。Gemini for Science 仍然可以调用专用系统，但大方向是 agentic, LLM-based systems that could eventually execute cutting-edge research projects without human involvement.

这个方向转变意味着：harness 工程将从"让 Agent 能写代码"扩展到"让 Agent 能做科研"。复杂度会指数级增长，架构的重要性也会随之倍增。

---

## 六、实践指南：如何评估和构建一个 Agent 系统

基于上述分析，我们提出一个实用的 Agent 系统评估框架。

### 6.1 评估 Checklist

当你评估一个 Agent 方案时，不要只看"用了什么模型"，而要问以下问题：

```
Agent 系统评估 Checklist

┌─ Model 层 ──────────────────────────────────────┐
│ □ 使用了什么模型？                              │
│ □ 模型版本是否可升级？                           │
│ □ 是否需要更换模型？（成本/效果权衡）             │
├─ Scaffold 层 ───────────────────────────────────┤
│ □ System Prompt 是否针对场景优化？               │
│ □ 工具描述是否精准？（太多 → 犹豫，太少 → 受限）  │
│ □ 上下文管理策略是什么？                          │
│ □ 是否有长短期记忆分层？                          │
├─ Harness 层 ────────────────────────────────────┤
│ □ 执行循环的设计是什么？                          │
│ □ 停止条件是否智能？                              │
│ □ 错误恢复策略是什么？                            │
│ □ 是否支持子 Agent 调度？                         │
│ □ 是否有工具短名单机制？                          │
├─ 安全与治理 ───────────────────────────────────┐
│ □ 权限边界如何定义？                              │
│ □ 敏感操作是否需要人工审批？                       │
│ □ 定时任务的安全控制是什么？                       │
│ □ 日志和可观测性是否完善？                         │
└────────────────────────────────────────────────┘
```

### 6.2 架构选型建议

**对于初创团队：** 优先投资 Harness 层。模型可以通过 API 获取，但 harness 是你的核心竞争力。一个好的 harness 可以让中等模型跑出优秀模型的效果。

**对于成熟团队：** 全面优化 Scaffold 和 Harness 的协同。IBM 排行榜的数据显示，通用 Agent 已经可以匹敌专用 Agent，这意味着架构优化带来的边际收益可能超过模型升级。

**对于安全敏感场景：** Harness 层的安全护栏是第一优先级。Copilot Cowork 的教训告诉我们，权限传递和审批逻辑的设计缺陷可以完全摧毁系统的安全性。

---

## 七、未来展望：Agent 架构竞赛刚刚开始

### 7.1 短期趋势（2026 下半年）

- **术语标准化**：HuggingFace 术语表只是一个开始，行业需要更广泛的术语共识
- **开放评估**：IBM 的 Exgentic 框架为社区提供了可复现的评估基础设施
- **Harness 工具化**：更多的框架（Flue、LangGraph、ADK）将在 Harness 层面展开竞争

### 7.2 中期趋势（2027）

- **Agent 架构成为独立学科**：Harness Engineering 可能成为一个独立的技术领域
- **模型重要性下降**：随着模型能力的趋同，Agent 架构的差异将成为主要区分因素
- **安全标准化**：类似 Copilot Cowork 的漏洞将推动 Agent 安全标准的建立

### 7.3 长期趋势（2028+）

- **Agent 原生基础设施**：从操作系统到网络协议，都将为 Agent 重新设计
- **Agent 经济**：Agent 之间的协作、交易、竞争将形成新的经济形态
- **Human-Agent 协同范式**：人类和 Agent 的分工将重新定义软件工程的全流程

---

## 八、结论

2026 年 5 月的这两篇文献，从理论和实践两个维度回答了一个被长期忽视的问题：**Agent 不只是 Model 的包装，Agent 架构本身就是核心竞争力。**

HuggingFace 的术语表给了我们清晰的**概念工具**——Model、Scaffold、Harness 的三分法让我们能精确讨论 Agent 的各个组成部分。

IBM 的 Open Agent Leaderboard 给了我们**数据证据**——相同模型、不同 Agent 系统，得分和成本都不同。通用 Agent 已经可以匹敌专用 Agent。Tool Shortlisting 这种纯粹的架构选择，足以扭转一个系统的成败。

两者结合，指向一个清晰的结论：

> **模型决定了 Agent 的能力上限，但架构决定了 Agent 的实际表现。在模型能力快速趋同的 2026 年，Agent 架构正在成为新的竞争焦点。**

这不是在贬低模型的重要性。模型仍然是最大的方差来源。但它意味着：**如果你只关注模型选择，你只优化了 Agent 系统的一部分。真正的差距，在架构层。**

---

## 参考资料

1. [HuggingFace Blog: Harness, Scaffold, and the AI Agent Terms Worth Getting Right](https://huggingface.co/blog/agent-glossary) — Sergio Paniego & Ari Gati, 2026-05-25
2. [IBM Research: The Open Agent Leaderboard](https://huggingface.co/blog/ibm-research/open-agent-leaderboard) — Elron 等, 2026-05-18
3. [Exgentic Framework (GitHub)](https://github.com/Exgentic/exgentic) — 开源 Agent 评估框架
4. [Paper: General Agent Evaluation](https://arxiv.org/abs/2602.22953) — IBM Research, 2026-02
5. [PromptArmor: Microsoft Copilot Cowork Exfiltrates Files](https://www.promptarmor.com/resources/microsoft-copilot-cowork-exfiltrates-files) — 2026-05-25
6. [MIT Technology Review: Anthropic's Code with Claude](https://www.technologyreview.com/2026/05/21/1137735/) — 2026-05-21
7. [MIT Technology Review: Google I/O and AI-driven Science](https://www.technologyreview.com/2026/05/22/1137813/) — 2026-05-22
8. [HF Context Engineering Course](https://huggingface.co/learn/context-course/en/unit0/introduction) — HuggingFace
