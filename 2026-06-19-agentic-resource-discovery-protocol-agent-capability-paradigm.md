# Agentic Resource Discovery 协议：当 Agent 不再需要人类帮它找工具

> 2026 年 6 月中旬，HuggingFace 联合 Microsoft、Google、GoDaddy 等公司发布了一份全新的开放规范：**Agentic Resource Discovery（ARD）**。它的核心主张只有一个 —— **让 Agent 自己去搜索、发现和接入工具、Skills 和其他 Agent，而不是等着人类开发者帮它配置好。**

这听起来像个小改动。但它实际上解决的是 Agent 生态中最根本的基础设施鸿沟：**我们有 MCP 来调用工具，有 A2A 来调用 Agent，有 Skills 来传递指令，但没有一个标准来回答"我该用什么"这个问题。**

在人类软件世界里，这个问题靠搜索引擎、应用商店和文档解决。在 Agent 世界里，这个问题至今的答案是：**写在配置文件里。**

ARD 试图改变这一点。它不是又一个协议，而是所有协议的"前置层"—— Discovery Layer。

---

## 一、发现鸿沟：Agent 生态的"最后一公里"问题

### 1.1 当前 Agent 工具接入的三种模式

要理解 ARD 为什么重要，先看现在 Agent 是怎么获得能力的。

**模式一：硬编码（Hardcoded）**

```json
// claude_desktop_config.json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_TOKEN": "xxx" }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user"]
    }
  }
}
```

每个 MCP Server 的 URL、命令、参数，全部手动写入配置文件。用户需要知道哪个工具存在、怎么安装、怎么配置。这是目前绝大多数 MCP 客户端的工作方式。

**模式二：全量注入（Full Context Dump）**

把所有可用工具的描述一股脑塞进 LLM 的上下文窗口，让模型自己挑。这是 Anthropic Claude Desktop 和一些 Agentic 框架的做法。问题很明显：上下文预算有限，工具描述往往太薄，无法有效消歧。

**模式三：搜索策略（Search-based）**

用语义搜索过滤工具描述，再把候选集喂给 LLM。比全量注入好一些，但工具描述的质量参差不齐，搜索结果往往不够精确。

这三种模式有一个共同特征：**发现和执行是绑定的。** 工具必须在执行前就被人类找到、安装、配置好。如果 Agent 需要一个新的能力（比如"帮我把这篇论文转成播客"），它没法自己去找这个工具——它只能告诉用户"我没有这个能力"，或者更糟：**自己从零重写逻辑。**

### 1.2 问题有多严重？

我们不妨量化一下。HuggingFace 的 Hub 上已经有：
- 数千个 MCP Server
- 84,000+ 颗星的 Agent Skills 仓库
- 数十万个可以包装为 Agent 能力的 Spaces
- A2A 协议下越来越多的互联 Agent

这些能力中，**绝大部分对用户和 Agent 来说是不可见的。** 不是不存在，而是没有发现通道。用户不知道它们存在，Agent 更不可能找到它们。

这就像互联网有了 HTTP 协议但没有搜索引擎——网站都在，但你只能访问你知道 URL 的那些。

---

## 二、ARD 是什么：把"发现"从 Agent 架构中独立出来

### 2.1 核心定义

Agentic Resource Discovery 是一份**开放规范**（Draft），不是某个公司的产品。它的核心定义非常简洁：

> ARD 定义了一个标准化的能力发现层，让 Agent 可以在运行时动态搜索、发现和接入 MCP 工具、Skills 和其他 Agent，而无需预先配置。

它解决了两个层面的问题：

**静态发现**：通过 `.well-known/ai-catalog.json` 文件，让任何 Publisher 在已知 URL 上发布自己的能力目录。

**动态发现**：通过 `POST /search` REST API，让 Agent 用自然语言搜索能力，获得结构化的能力卡片。

### 2.2 架构分层：ARD 在 Agent 协议栈中的位置

```
┌─────────────────────────────────────────────────┐
│                   Agent Application              │
├─────────────────────────────────────────────────┤
│              ARD (Discovery Layer)               │  ← 新增
│         "我需要什么能力？去哪里找？"              │
├──────────────┬──────────────┬──────────────────┤
│     MCP      │     A2A      │     Skills        │
│   工具调用    │  Agent 调用   │   指令传递         │
├──────────────┴──────────────┴──────────────────┤
│              Transport Layer                    │
│          HTTP / Stdio / WebSocket               │
└─────────────────────────────────────────────────┘
```

这是 ARD 最重要的设计决策：**它不是取代 MCP、A2A 或 Skills，而是位于它们之上，作为发现层。**

这意味着：
- MCP Server 不需要修改自己的协议，只需要在 ARD 注册表中登记自己
- A2A Agent 不需要改变通信方式，只需要让自己可被发现
- Skills 不需要改变格式，只需要暴露自己的存在

ARD 只做一件事：**让能力变得可发现。** 执行还是交给各自的协议。

### 2.3 关键设计原则

**解耦发现与执行（Decoupled Discovery and Execution）**

ARD 的发现结果是一个标准化的能力卡片（Catalog Entry），包含能力的元数据、调用方式、使用示例等。Agent 拿到卡片后，用对应的协议（MCP/A2A/Skills）去执行。发现和执行的解耦意味着 ARD 可以支持任何执行协议，不需要因为新协议的出现而修改规范。

**联邦式注册（Federated Registries）**

没有一个"中心化的 App Store"。任何组织都可以运行自己的 ARD 注册表，多个注册表之间可以互相联邦查询。HuggingFace 的 Discover Tool 是一个参考实现，Microsoft、Google 也可以运行自己的。Agent 可以搜索任何一个注册表，也可以同时搜索多个。

**媒体类型抽象（Media Type Abstraction）**

ARD 用 HTTP 媒体类型（`application/ai-skill`、`application/mcp-server-card+json` 等）来区分不同类型的能力。这意味着新的能力类型可以通过新的媒体类型加入，不需要修改规范本身。这是一种面向未来的设计。

---

## 三、HuggingFace Discover Tool：ARD 的第一个生产级实现

### 3.1 它是什么

HuggingFace 的 Discover Tool（`hf discover`）是 ARD 规范的第一个参考实现，集成在 HuggingFace CLI 中。它做了什么？

**把 Hub 上已有的能力包装成 ARD 格式的目录条目。**

Hub 上已经有：
- 运行中的 Spaces（Gradio 应用）
- Agent Skills（带 `SKILL.md` 或 `agents.md`）
- MCP Server（带 `mcp-server` 标签的 Spaces）

Discover Tool 通过 Hub 的语义搜索后端，把这些能力索引为 ARD 格式的条目，暴露给 Agent 搜索。

### 3.2 工作流程

```
Agent 发出自然语言查询
       │
       ▼
POST /search { "query": { "text": "fine tune a sentence transformer" } }
       │
       ▼
Hub 语义搜索（带 agents=true 过滤）
       │
       ▼
返回 ARD 格式的 Catalog Entries
       │
       ├── application/ai-skill → 生成 SKILL.md 包裹 agents.md
       ├── application/mcp-server-card+json → 生成 MCP 能力卡片
       └── application/vnd.huggingface.space+json → 原始 Space 元数据
       │
       ▼
Agent 选择条目，用对应协议执行
```

关键点在于 **自动转换**：很多 Spaces 自带 `agents.md` 文件，描述 Agent 应该如何与它们交互。Discover Tool 读取这个文件，自动包装成 `SKILL.md` 格式（包含 name、description、source metadata），让任何 Skill-aware 客户端都能直接加载。

对于标记为 `mcp-server` 的 Space，Discover Tool 生成指向 Gradio MCP endpoint 的 HTTP 能力卡片。

### 3.3 实际使用示例

```bash
# 安装
uv tool install huggingface_hub

# 搜索 Skills：微调语言模型
hf discover search "Fine tune a language model"

# 搜索 MCP Servers：图像生成
hf discover search "Generate an image" --json --kind mcp

# 搜索其他 ARD 注册表
hf discover search "Purchase aeroplane tickets" --registry-url <catalog-url>
```

REST API 同样可用：

```bash
curl -s https://huggingface-hf-discover.hf.space/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "text": "fine tune a sentence transformer",
      "filter": {
        "type": ["application/ai-skill"]
      }
    },
    "pageSize": 5
  }'
```

这意味着**任何编程语言、任何 Agent 框架**都可以直接调用 ARD 搜索，不需要依赖特定的 SDK。

---

## 四、深入分析：ARD 为什么是 Agent 架构的范式转移

### 4.1 从"能力预设"到"能力发现"

让我们回到 Agent 架构的本质问题。

当前的 Agent 架构有一个隐含假设：**Agent 需要的所有能力，在执行前就已经确定了。** 这个假设在 Demo 场景下没问题——你做一个代码助手，提前装好 MCP Filesystem 和 MCP GitHub，Agent 就能工作了。

但到了生产环境，这个假设就会崩溃：

- 用户问 Agent"帮我分析一下这家公司的财务报表"，Agent 需要金融数据工具——它没有，也没法自己找
- Agent 在调试一个前端 Bug，需要浏览器自动化工具——它需要人类先去安装 Playwright MCP Server
- Agent 想把一篇论文转成播客——它需要 TTS 工具，但人类从来没配置过

这就是"能力预设"模式的根本局限：**Agent 的能力上限，等于人类开发者愿意为它配置的工具数量。**

ARD 改变了这个方程。有了发现层，Agent 可以：
1. 理解任务需要什么能力
2. 搜索可用的能力
3. 选择最合适的能力
4. 动态接入并执行

这不是"Agent 更聪明了"，而是 **Agent 的基础设施从封闭系统变成了开放系统。**

### 4.2 对比：传统软件生态的发现模式

我们可以从传统软件生态的发展历程中获得启发：

| 时代 | 发现方式 | 局限性 |
|------|----------|--------|
| 1980s | 手册 + 口耳相传 | 信息极度不对称 |
| 1990s | 搜索引擎 | 质量参差不齐，需要人工筛选 |
| 2000s | 应用商店 | 中心化控制，审核瓶颈 |
| 2010s | 包管理器 + 语义搜索 | npm/pip 生态繁荣 |
| 2020s（Agent） | **ARD** | 联邦式、Agent-native 的能力发现 |

ARD 不是简单地复制应用商店或包管理器。它的独特之处在于：

**Agent-native 的发现语义。** 传统搜索引擎为人眼优化，返回的是网页链接和摘要。ARD 为 Agent 优化，返回的是结构化的能力卡片，包含调用协议、参数 schema、使用示例——Agent 可以直接消费的信息。

**协议无关性。** npm 只能发现 Node.js 包，pip 只能发现 Python 包。ARD 可以发现在任何协议上运行的能力——MCP、A2A、Skills、甚至未来的新协议。

**联邦而非中心化。** 没有一个"ARD App Store"控制一切。任何组织都可以运行自己的注册表，并且注册表之间可以互相联邦。这避免了中心化平台的审核瓶颈和单点故障。

### 4.3 技术细节：ai-catalog.json 和 REST API

ARD 规范定义了两个核心接口：

**静态清单：`ai-catalog.json`**

```json
{
  "version": "1.0",
  "publisher": {
    "name": "HuggingFace",
    "url": "https://huggingface.co"
  },
  "capabilities": [
    {
      "id": "hf-discover",
      "type": "application/ai-skill",
      "name": "Discover Tool",
      "description": "Search for ML tools, Skills, and MCP servers",
      "endpoint": "https://huggingface-hf-discover.hf.space/mcp",
      "queries": ["fine tune model", "train model", "generate image"]
    }
  ]
}
```

这个文件放在 `.well-known/ai-catalog.json` 路径下，任何爬虫或 Agent 都可以发现。这是一个**被动发现**机制——不需要主动注册，只需要放一个文件。

**动态搜索 API**

```
POST /search
Content-Type: application/json

{
  "query": {
    "text": "natural language query",
    "filter": {
      "type": ["application/ai-skill"],
      "tags": ["ml", "training"]
    }
  },
  "pageSize": 10,
  "pageToken": "..."
}
```

这是一个**主动发现**机制——Agent 用自然语言描述需求，注册表返回匹配的能力。搜索不仅基于关键词，还支持标签过滤、类型过滤和语义相似度排序。

**联邦查询**

ARD 注册表可以配置三种联邦模式：
- `auto`：自动查询已知的其他注册表
- `referrals`：返回推荐的其他注册表 URL
- `none`：只搜索本地

这意味着 ARD 可以渐进式部署——从一个注册表开始，逐步扩展到联邦网络。

### 4.4 安全问题：谁在控制 Agent 能发现什么？

ARD 引入了一个关键问题：**当 Agent 可以自己发现工具时，谁来控制安全边界？**

在传统模式下，安全边界很清楚——人类开发者配置的工具列表就是安全边界。Agent 只能调用人类允许它调用的工具。

在 ARD 模式下，安全边界需要重新定义：

**注册表级别的安全**
- Publisher 身份验证：谁可以发布能力？
- 合规认证：能力是否通过了安全审核？
- 访问控制：哪些 Agent 可以搜索哪些能力？

**Agent 级别的安全**
- 能力白名单/黑名单：Agent 可以访问哪些类型的能力？
- 权限沙箱：发现的能力在什么权限范围内执行？
- 审计日志：Agent 发现和使用了哪些能力？

ARD 规范本身不解决这些安全问题——它只是定义了发现接口。但这些问题必须在生产部署前得到解决。HuggingFace 的 Discover Tool 在实现中加入了一些安全措施：
- 只返回 `RUNNING` 状态的 Space
- Publisher 身份通过 Hub 账户体系验证
- 搜索请求可以通过 API token 进行访问控制

但这些只是起点。随着 ARD 的普及，**Agent 能力发现的安全模型**将成为一个独立的研究和工程领域。

---

## 五、ARD 的生态影响：Agent 经济的催化剂

### 5.1 能力市场的启动

ARD 本质上为 Agent 能力创建了一个**发现市场**。这个市场有几个关键特征：

**供给侧爆炸。** 目前 Hub 上有数千个 MCP Server 和数十万个 Spaces。大多数对 Agent 来说是不可见的。ARD 让它们变得可发现，供给侧可能从几千扩展到几十万。

**需求侧激活。** 当 Agent 可以自己搜索能力时，用户对"我的 Agent 不能做 X"的容忍度会降低——Agent 应该说"让我找一个能做 X 的工具"，而不是"我没有这个能力"。

**正反馈循环。** 更多的发现 → 更多的使用 → 更多的开发者发布能力 → 更多的发现。这是所有平台市场的经典正反馈循环。

### 5.2 与传统应用商店的区别

ARD 不是 App Store。几个关键区别：

| 维度 | App Store | ARD |
|------|-----------|-----|
| 审核 | 中心化审核 | 去中心化，Publisher 自治 |
| 安装 | 用户手动安装 | Agent 动态接入 |
| 付费 | 应用内购买为主 | 各能力自行定价 |
| 发现 | 搜索 + 推荐 | 自然语言搜索 + 语义匹配 |
| 执行 | 沙箱内运行 | 通过各自协议执行 |

ARD 更像是一个**去中心化的能力搜索引擎**，而不是一个应用分发平台。它不控制分发，不控制定价，不控制执行——它只做发现。

### 5.3 对未来 Agent 架构的影响

ARD 的普及将深刻影响 Agent 架构的设计：

**Agent 从"工具消费者"变成"能力消费者"。** 传统 Agent 消费预配置的工具列表。ARD Agent 消费动态发现的能力。这意味着 Agent 的架构需要支持能力的动态加载和卸载。

**上下文窗口的新用途。** 不再需要把所有工具描述塞进上下文窗口。Agent 只需要在需要时搜索能力，把具体的能力卡片加入上下文。上下文窗口的利用效率将大幅提升。

**Agent 组合性的增强。** 当 Agent 可以发现其他 Agent 时（A2A + ARD），Agent 之间的组合和协作将变得更加灵活和动态。一个 Agent 可以在运行时发现自己需要的协作 Agent，而不是在编码时就确定。

---

## 六、批判性思考：ARD 面临的挑战

### 6.1 发现质量：如何避免"垃圾能力"？

当任何 Publisher 都可以在 ARD 注册表中发布能力时，**发现质量**成为核心问题。

如果 Agent 搜索"fine tune a model"，返回的结果中混杂着质量低劣、过时、甚至恶意的能力卡片，那么 ARD 的价值就大打折扣。

可能的解决方案：
- **Publisher 声誉系统**：类似 npm 的包下载量和 Star 数
- **能力质量评分**：基于使用反馈、错误率、响应时间等指标
- **社区审核**：类似 GitHub 的 issue/PR 机制
- **认证体系**：类似"Verified Publisher"

ARD 规范目前没有内置这些机制，但它们对生产部署至关重要。

### 6.2 协议碎片化：太多的"标准"

Agent 协议生态正在快速碎片化：
- MCP（Model Context Protocol）
- A2A（Agent-to-Agent）
- Skills（Claude/Anthropic 体系）
- ARD（Agentic Resource Discovery）
- 还有无数厂商的私有协议

ARD 试图成为这些协议的"发现层"，但这个定位本身就有风险：如果执行协议本身不统一，发现层的价值也会受限。

想象一下：Agent 通过 ARD 找到了一个完美的能力，但那个能力使用了一个它不支持的私有协议——发现变得没有意义。

**解决方案**：ARD 需要与主流执行协议（MCP、A2A、Skills）深度集成，确保发现的结果可以被大多数 Agent 执行。HuggingFace 的 Discover Tool 已经在做这件事——它把 Spaces 包装成 MCP 和 Skills 两种格式。

### 6.3 延迟问题：发现需要时间

动态发现引入了额外的延迟：
1. Agent 理解任务需要什么能力（推理延迟）
2. Agent 搜索 ARD 注册表（网络延迟）
3. Agent 解析返回的能力卡片（处理延迟）
4. Agent 动态加载能力（初始化延迟）

对于实时性要求高的任务（如对话中的工具调用），这个延迟可能不可接受。

可能的优化方向：
- **预缓存**：Agent 提前缓存常用能力的发现结果
- **并行搜索**：同时搜索多个注册表
- **渐进式加载**：先加载能力的基本信息，在执行时再加载详细信息

---

## 七、与 MCP 企业级认证的协同效应

有趣的是，ARD 的发布与 MCP 的另一个重要进展几乎同时发生：**Enterprise-Managed Authorization（EMA）**。

EMA 让企业可以通过身份提供商（如 Okta）集中管理 MCP Server 的访问权限，实现"一次登录，全部接入"。Anthropic 已经在 Claude、Claude Code 和 Cowork 中实现了 EMA，VS Code 也在预览中支持。

**ARD + EMA 的组合意味着什么？**

在企业的场景下：
1. **ARD** 让 Agent 发现可用的能力
2. **EMA** 确保 Agent 只能访问它被授权访问的能力
3. 两个协议组合，形成一个**完整的企业级 Agent 能力管理方案**

这不是巧合。MCP 社区在推动标准化方面非常积极——从 MCP 协议本身，到 EMA 扩展，再到 ARD 规范，每一步都在解决 Agent 生态的一个关键瓶颈。

---

## 八、结论：Agent 基础设施的最后一块拼图

回顾 Agent 基础设施的演进：

1. **MCP** 解决了工具调用的标准化
2. **A2A** 解决了 Agent 之间的通信
3. **Skills** 解决了 Agent 指令的标准化
4. **EMA** 解决了企业级访问控制
5. **ARD** 解决了能力发现

ARD 不是最"性感"的协议——它不做推理，不做生成，不做执行。但它可能是**最重要的一块拼图**。

因为如果没有发现层，所有的执行协议都只能在封闭的、预配置的能力范围内工作。有了发现层，Agent 才能真正成为一个**开放系统**——能够动态发现、选择和接入它需要的任何能力。

这就是 ARD 的范式意义：**它不是让 Agent 更聪明，而是让 Agent 的世界更大。**

---

## 参考资料

1. HuggingFace Blog: [Agentic Resource Discovery: Let agents search](https://huggingface.co/blog/agentic-resource-discovery-launch)
2. HuggingFace Blog: [Designing the hf CLI as an agent-optimized way to work with the Hub](https://huggingface.co/blog/hf-cli-for-agents)
3. MCP Blog: [Enterprise-Managed Authorization: Zero-touch OAuth for MCP](https://blog.modelcontextprotocol.io/posts/enterprise-managed-auth/)
4. HuggingFace Blog: [Is it agentic enough? Benchmarking open models on your own tooling](https://huggingface.co/blog/is-it-agentic-enough)
5. HuggingFace Blog: [Harness, Scaffold, and the AI Agent Terms Worth Getting Right](https://huggingface.co/blog/agent-glossary)
6. ARD Specification: [GitHub ext-auth repository](https://github.com/modelcontextprotocol/ext-auth)
