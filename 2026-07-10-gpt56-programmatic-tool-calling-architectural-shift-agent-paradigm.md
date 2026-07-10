# GPT-5.6 与 Programmatic Tool Calling：从"模型调用工具"到"模型编程调用工具"的范式转移

> **摘要：** 2026 年 7 月 9 日，OpenAI 发布 GPT-5.6 系列模型（Sol、Terra、Luna），在 Hacker News 首页获得 976 票、730 条评论，成为近期 AI 领域最引人注目的发布。但比模型能力提升更值得关注的是一个被多数评论忽视的架构级创新——**Programmatic Tool Calling**。它允许模型在 Responses API 的托管运行时中编写并执行 JavaScript 程序来编排工具调用，从根本上改变了 Agent 工具调用的通信范式：从"串行往返"升级为"程序化编排"。本文深度解析这一架构变化的技术细节、性能影响、安全边界，以及它对 Agent 生态的深远意义。

---

## 一、GPT-5.6 发布概览：不只是又一个"更强模型"

### 1.1 模型家族：Sol、Terra、Luna

GPT-5.6 不是单一模型，而是一个三档家族：

| 模型 | 定位 | 关键特征 |
|------|------|----------|
| **GPT-5.6 Sol** | 旗舰模型 | SOTA 编码/知识/科学推理，Agents' Last Exam 53.6 分 |
| **GPT-5.6 Terra** | 平衡模型 | 超越 Claude Fable 5（adaptive reasoning），成本约 1/16 |
| **GPT-5.6 Luna** | 性价比模型 | 超越 Opus 4.8，成本约 1/16，时间约 1/3 |

在 **Agents' Last Exam**（跨 55 个领域的长时间专业工作流评估）中，GPT-5.6 Sol 以 53.6 分刷新纪录，超出 Claude Fable 5（adaptive reasoning）13.1 分。更关键的是，即使以 medium reasoning 运行，Sol 仍能以约 **四分之一的成本** 超越 Fable 5。

在 **Artificial Analysis Coding Agent Index** 上，Sol 以 80 分创 SOTA，比 Fable 5 高 2.8 分，同时使用不到一半的输出 token、一半的时间、约三分之一的成本。

### 1.2 一个被忽视的信号

HN 上 730 条评论中，绝大多数集中在"模型能力对比"和"价格"上。但如果你仔细阅读 OpenAI 的技术文档，会发现 GPT-5.6 引入了一项**架构级别**的变更，其意义不亚于 2023 年 3 月 Plugin 生态的开启：

**Programmatic Tool Calling**。

这不是一个小的 API 改进。它从根本上改变了 Agent 与工具的交互范式。

---

## 二、传统 Tool Calling 的架构困境

### 2.1 串行往返模型的本质

在 GPT-5.6 之前（包括所有主流模型的当前实现），Agent 工具调用遵循一个固定模式：

```
Agent 发出请求
    → API 调用工具 A
    → 返回结果给模型
    → 模型分析结果，决定下一步
    → API 调用工具 B
    → 返回结果给模型
    → 模型分析结果，决定下一步
    → API 调用工具 C
    → ...
```

这个模式有几个**结构性缺陷**：

**第一，Token 浪费。** 每一次工具调用的完整输出都要经过模型。假设工具 A 返回 50 条记录，模型需要在下一轮 prompt 中"看到"全部 50 条，然后决定下一步。但实际上模型可能只需要其中的 3 条关键信息。

**第二，延迟累积。** 每一轮工具调用都是一次完整的 HTTP 往返。10 步任务 = 10 次往返。即使每次往返只有 200ms，累积延迟也达到 2 秒——这还没计算模型的推理时间。

**第三，中间状态无法压缩。** 模型在步骤 2 获得的信息无法直接传递给步骤 5 的工具调用。每一轮都是独立的 prompt context，中间状态只能通过 prompt 中的文本传递。

**第四，无法并行。** 如果工具 B 和工具 C 是独立的（不依赖彼此的结果），模型仍然需要串行调用，因为它无法在一次请求中发起两个独立的 tool call 分支。

这些缺陷在简单任务中不明显，但当任务复杂度上升时，它们成为 Agent 能力的**结构性天花板**。

### 2.2 业界的修补方案

在 GPT-5.6 之前，社区和厂商尝试过多种修补方案：

- **Agentic Frameworks（LangGraph、CrewAI 等）**：在框架层面实现并行和状态管理，但增加了额外的复杂性和延迟。
- **ReAct 模式**：通过 "Thought → Action → Observation" 循环让模型自主决策，但本质上仍是串行往返。
- **Parallel Tool Calling**：部分 API 支持在同一轮请求中发起多个 tool call，但控制逻辑仍在模型端，无法利用中间结果做动态分支。

这些方案都在**应用层**修补问题，而非在**架构层**解决问题。

---

## 三、Programmatic Tool Calling 的架构解析

### 3.1 核心理念：模型写代码，代码调工具

Programmatic Tool Calling 的工作方式可以用一句话概括：

> **模型不再直接调用工具，而是编写一个 JavaScript 程序，这个程序在 OpenAI 的托管 V8 运行时中执行，程序内部调用工具、处理中间结果、做条件分支。**

具体流程如下：

```
Agent 发出请求
    → 模型生成 JavaScript 程序
    → 程序在隔离 V8 运行时中执行
    → 程序内部：
        - 并行调用多个工具
        - 过滤、聚合、排序中间结果
        - 根据条件做分支判断
        - 循环处理数据集
    → 程序返回精简的结构化结果
    → 模型接收精简结果，生成最终响应
```

注意关键区别：**中间结果不再回到模型的 prompt 中**，而是在程序内部处理，只有最终的结构化结果返回给模型。

### 3.2 技术细节

根据 OpenAI 的 [开发者文档](https://developers.openai.com/api/docs/guides/tools-programmatic-tool-calling)，Programmatic Tool Calling 有以下关键设计：

**隔离运行时：** 每个生成的程序在新的、隔离的 V8 运行时中执行。支持 JavaScript 和 top-level await，但**不提供** Node.js、包安装、直接网络访问、通用文件系统、子进程执行或控制台。

这意味着程序只能通过 API 请求中启用的工具与外部系统交互，无法"逃逸"到任意的计算环境。

**allowed_callers 机制：** 这是一个精细的权限控制系统：

| allowed_callers 值 | 行为 |
|---------------------|------|
| 省略或 `["direct"]` | 模型只能直接调用工具 |
| `["programmatic"]` | 只有程序代码可以调用该工具 |
| `["direct", "programmatic"]` | 模型和程序都可以调用 |

这使得开发者可以精确控制哪些工具允许被程序调用，哪些只能由模型直接调用。对于写操作或需要审批的操作，可以限制为仅 `["direct"]`，保留清晰的授权边界。

**支持的工具类型：** function、custom、mcp、apply_patch、local/hosted shell、code_interpreter——几乎涵盖了所有常用工具类型。

### 3.3 适用场景 vs 不适用场景

OpenAI 在文档中给出了明确的场景分类：

| 任务类型 | 推荐模式 | 原因 |
|----------|----------|------|
| 单次查询或操作 | 直接调用 | 杀鸡用牛刀 |
| 多个结果需要过滤、连接、排名、去重、聚合 | Programmatic | 程序能返回更小的结构化结果 |
| 有依赖关系但数据流可预测的调用链 | Programmatic | 代码可以推导后续参数 |
| 自适应搜索或语义评估 | 直接调用 | 每个结果都需要影响模型的下一步判断 |
| 写操作或需审批的操作 | 直接调用 | 保留清晰的授权边界 |
| 最终引用或原生产物验证 | 直接调用 | 除非程序保留原生输出并验证每一项 |

这个分类揭示了一个重要的设计哲学：**Programmatic Tool Calling 不是替代直接调用，而是补充分层**。当任务具有"可预测的控制流 + 可压缩的中间数据"时，程序化调用大幅降低 token 消耗和延迟；当任务需要"每一步都依赖模型的语义判断"时，直接调用仍然更合适。

---

## 四、性能影响的量化分析

### 4.1 Token 效率

从 GPT-5.6 的基准数据可以看出 Programmatic Tool Calling 的实际效果：

在 Artificial Analysis Coding Agent Index 上，GPT-5.6 Sol 使用了**不到一半的输出 token**，却取得了比 Fable 5 高 2.8 分的成绩。

这个数字背后的含义是：传统的串行往返模式中，大量 token 被消耗在传递中间结果上。当一个 Agent 需要调用 10 个工具来完成一个编码任务时，每个工具的输出可能包含数千 token 的上下文信息。而 Programmatic Tool Calling 允许程序在运行时内部过滤、聚合这些中间结果，只保留关键信息传递给模型。

假设一个典型场景：
- 传统模式：10 次工具调用 × 平均 2000 token/次中间结果 = 20,000 token 的中间数据传输
- Programmatic 模式：程序内部处理 20,000 token，只返回 200 token 的结构化摘要
- **Token 节省：约 99% 的中间数据不经过模型**

当然，实际情况不会这么极端。模型自身生成的 JavaScript 程序也会消耗 token，但总体来看，对于工具密集型任务，token 节省是显著的。

### 4.2 延迟优化

延迟优化来自两个方向：

**第一，减少往返次数。** 10 次串行工具调用需要 10 次 HTTP 往返。使用 Programmatic Tool Calling，这 10 次调用可以在一个程序内顺序或并行执行，只产生 1 次往返（模型生成程序 → 程序执行并返回结果）。

**第二，并行执行。** 程序中可以使用 `Promise.all()` 并行调用独立的工具。假设工具 B 和工具 C 都需要 500ms，串行需要 1000ms，并行只需要 500ms。

OpenAI 在文档中明确提到了"Programmatic Tool Calling supports Zero Data Retention (ZDR) workflows without requiring a persistent code-execution container"——这意味着即使在严格的零数据保留合规要求下，也可以使用程序化工具调用，而不需要额外部署代码执行容器。

### 4.3 ultra 模式：多 Agent 并行的另一条路径

与 Programmatic Tool Calling 互补的是 GPT-5.6 的 **ultra** 模式：

> "ultra goes further by coordinating four agents in parallel by default, trading higher token use for stronger results and faster time-to-result on demanding tasks."

ultra 模式在更高层面实现并行——不是单个 Agent 内的工具并行，而是**多个 Agent 实例并行工作**。在 BrowseComp、SEC-Bench Pro 和 Terminal-Bench 2.1 上，4-Agent 配置已经展示了"分数-延迟"前沿的显著上移。16-Agent 配置进一步推高了上限。

这两个特性（Programmatic Tool Calling + ultra 模式）共同构成了 GPT-5.6 的**双层并行架构**：
- **微观层**：Programmatic Tool Calling 在单个 Agent 内部实现工具调用的并行和中间数据压缩
- **宏观层**：ultra 模式在多个 Agent 之间实现任务的并行分解

---

## 五、安全边界的深度分析

### 5.1 隔离 V8 运行时：安全还是脆弱？

Programmatic Tool Calling 最引人注目的设计决策是：**让模型编写并执行代码**。这听起来像是一个安全隐患，但 OpenAI 的设计非常谨慎：

**运行时限制：**
- ❌ 无 Node.js（不能 require 任意模块）
- ❌ 无包安装（不能 npm install）
- ❌ 无直接网络访问（只能通过工具 API）
- ❌ 无通用文件系统
- ❌ 无子进程执行
- ❌ 执行间无持久化状态

**允许的交互：**
- ✅ 通过工具 API 与外部系统交互
- ✅ 使用 `text()` 和 `image()` 输出

这本质上创建了一个**沙箱化的工具编排层**。模型可以编写任意逻辑，但所有对外交互都必须通过预定义的工具接口。这类似于操作系统的系统调用机制——程序可以做任何计算，但要与外界交互必须通过受控的接口。

### 5.2 allowed_callers：细粒度权限控制

`allowed_callers` 机制是安全设计的关键创新。它允许开发者在工具级别定义调用权限：

```javascript
// 只有程序代码可以调用的工具（读操作）
{
  "type": "function",
  "name": "get_inventory",
  "allowed_callers": ["programmatic"]
}

// 只有模型可以直接调用的工具（写操作）
{
  "type": "function", 
  "name": "update_inventory",
  "allowed_callers": ["direct"]
}

// 两者都可以调用
{
  "type": "function",
  "name": "search_products", 
  "allowed_callers": ["direct", "programmatic"]
}
```

这种设计模式值得注意：**读操作可以委托给程序，写操作保留在模型直接控制下**。这是一个合理的默认安全策略，但同时也意味着——**如果开发者错误地将写操作工具标记为 `["programmatic"]`，就可能出现不受审批的自动化写操作**。

### 5.3 与 MCP 工具的集成

Programmatic Tool Calling 支持 MCP（Model Context Protocol）工具，这是一个重要的生态信号。MCP 正在成为 Agent 工具生态的事实标准，而 GPT-5.6 将 MCP 工具纳入程序化调用范围，意味着：

1. MCP 服务器提供的工具可以被程序批量调用和编排
2. 程序可以在运行时动态发现和调用 MCP 工具
3. MCP 工具的 `require_approval` 策略在程序执行中可以暂停流程

这实际上为 MCP 生态创造了一种新的使用模式：**MCP 服务器不再是"被模型逐个调用"的被动服务，而是可以被程序批量编排的主动组件**。

---

## 六、与 ChatGPT Work 的协同效应

与 GPT-5.6 同一天发布的 **ChatGPT Work** 是另一个值得关注的产品。它是一个内置于 ChatGPT 中的 Agent，专门处理长时间、多步骤的工作任务：

> "It can gather information across your apps and workflows to create finished materials like sheets, slides, docs, and web apps, and stay with complex projects for hours by breaking them into smaller steps and completing them independently."

ChatGPT Work 的底层模型就是 GPT-5.6。这意味着 Programmatic Tool Calling 的能力可以直接赋能实际的工作场景：

- **财务场景**：月结和预测从数天缩短到数小时——Agent 可以找到源数据、导入 Excel/Sheets、核对、创建幻灯片、验证结果
- **销售场景**：将对话发现转化为定制 PoC，通常需数周的工作在 24 小时内完成

这些场景的共同特点是：**多工具调用 + 中间数据处理 + 条件分支**——这正是 Programmatic Tool Calling 最擅长的任务形状。

---

## 七、行业影响：Agent 开发的范式转移

### 7.1 对 Agent 框架的挑战

现有的 Agent 框架（LangChain、LangGraph、CrewAI、AutoGen 等）都在应用层实现了自己的工具编排逻辑。Programmatic Tool Calling 将这部分能力下沉到 API 层，提出了一个根本性问题：

**当 API 原生支持程序化工具编排时，框架层的编排逻辑是否还有必要？**

答案可能是：**框架层需要重新定位自己的价值**。

传统的框架价值在于：
- 工具调用的编排和状态管理
- 多 Agent 协作
- 记忆管理

当 API 层提供了工具编排能力后，框架的价值将更多转向：
- **高层策略定义**：不是"如何调用工具"，而是"何时调用、调用什么、如何评估"
- **领域适配**：将通用工具编排能力适配到特定领域（如软件开发、数据分析、内容创作）
- **可观测性和调试**：程序内部执行的可视化和调试工具

### 7.2 对开源模型的启示

NVIDIA 同日发布了 [《Data for Agents》](https://huggingface.co/blog/nvidia/open-data-for-agents)，强调 Agent 能力的本质是数据问题而非模型架构问题。这两件事的巧合值得思考：

- **闭源端**（OpenAI）：通过 API 架构创新（Programmatic Tool Calling）提升 Agent 能力
- **开源端**（NVIDIA）：通过开放数据和合成数据提升 Agent 能力

两条路径，同一个目标：让 Agent 更高效、更可靠地完成任务。但它们的技术路径截然不同——一个是**架构层面的范式转移**，一个是**数据层面的能力增强**。

### 7.3 对开发者的实际建议

如果你正在构建基于 LLM 的 Agent 应用，以下是基于 Programmatic Tool Calling 的实用建议：

**立即行动：**
1. 审查你的工具调用模式——哪些工具调用是"可预测控制流 + 可压缩中间数据"？这些是 Programmatic Tool Calling 的最佳候选
2. 为你的写操作工具设置 `allowed_callers: ["direct"]`，保留审批边界
3. 为读操作工具设置 `allowed_callers: ["programmatic"]`，允许程序化批量处理

**中期规划：**
1. 考虑将 MCP 工具纳入程序化调用范围
2. 评估 ultra 模式在复杂任务中的性价比
3. 建立程序化调用的可观测性基础设施

**长期思考：**
1. 当 Agent 可以在程序内部编写任意逻辑时，如何确保行为的可预测性和可审计性？
2. Programmatic Tool Calling 是否会催生新的"Agent 编程语言"？
3. 当工具调用从模型端转移到程序端，如何设计有效的测试和验证体系？

---

## 八、批判性视角：Programmatic Tool Calling 的局限性

任何架构创新都有其边界。Programmatic Tool Calling 也不例外：

### 8.1 语义判断的不可委托性

文档明确指出，对于"自适应搜索或语义评估"任务，应该使用直接调用。这是因为：

> "each result should influence the model's next decision"

如果每一步的中间结果都需要模型的**语义理解**来决定下一步行动，那么程序化调用反而会降低效果。程序可以做基于规则的分支判断，但无法替代模型的语义推理。

这意味着 Programmatic Tool Calling 最适用于**结构化、可预测的任务**，而对于需要深度语义理解的探索性任务，直接调用仍然更合适。

### 8.2 调试和可观测性的挑战

当模型编写的程序在隔离 V8 运行时中执行时，调试变得困难：
- 程序是动态生成的，无法预先测试
- 执行状态在运行时中，无法外部观察
- 错误信息需要通过 API 返回，缺乏本地调试工具的直观性

虽然 OpenAI 提供了错误返回机制，但与传统的本地调试体验相比，仍有明显差距。

### 8.3 生态锁定的风险

Programmatic Tool Calling 是 OpenAI 的专有 API 特性。如果你的 Agent 架构深度依赖它，迁移到其他模型供应商将面临挑战。这与 MCP 的开放生态理念形成对比——MCP 是开放协议，而 Programmatic Tool Calling 是闭源 API。

对于需要多云策略的企业，这可能是一个需要权衡的架构决策。

---

## 九、结语：Agent 范式的又一次跃迁

回顾 AI Agent 的发展轨迹：

- **2023 年初**：ReAct 模式诞生，Agent 开始"思考-行动-观察"
- **2023 年中**：Plugin 生态开启，Agent 开始接入外部工具
- **2024 年**：MCP 协议标准化，工具生态走向开放
- **2025 年**：Agentic Frameworks 爆发，Agent 编排复杂化
- **2026 年中**：Programmatic Tool Calling 出现，工具调用下沉到 API 层

每一次跃迁都不是简单的"能力增强"，而是**架构层面的范式转移**。Programmatic Tool Calling 的意义在于：它首次让 Agent 不再只是一个"工具调用的编排者"，而是一个"能编写编排程序的工具使用者"。

这不是一个 API 功能的更新。这是 Agent 角色定义的一次根本性重构。

当 GPT-5.6 Sol 在 Agents' Last Exam 上以 53.6 分刷新纪录、同时只使用一半的 token 和三分之一的成本时，我们看到的不仅是模型的进步，更是 Agent 架构进化的一个新阶段。

**更强的模型很重要，但更重要的是：更强的工具使用方式。**

---

*本文基于 OpenAI 官方 GPT-5.6 发布文档、Programmatic Tool Calling 开发者指南、ChatGPT Work 产品页面，以及 Hugging Face 上 NVIDIA 的 Data for Agents 博客文章进行分析。所有数据引用截至 2026 年 7 月 10 日。*
