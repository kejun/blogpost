# Headroom 深度解析：AI Agent 的 Token 压缩层如何重塑基础设施范式

> **摘要：** 2026 年 6 月初，一个名为 Headroom 的开源项目在 GitHub 上以每天 3,500+ 星的速度爆发性增长，短短数日突破 9,600 星。它的承诺极其大胆：**将 AI Agent 的 Token 消耗降低 60-95%，同时保持答案质量不变。** 这不是又一个"更便宜的上下文窗口"的噱头——Headroom 引入了可逆压缩（CCR）、KV Cache 优化（CacheAligner）、跨 Agent 共享内存、以及从失败中自我学习的闭环机制。本文将从架构、算法、基准测试和生产实践四个维度深度拆解 Headroom，并论证一个核心观点：**Context Compression Layer 正在成为 AI Agent 基础设施中独立于模型的新栈层。**

---

## 引言：上下文危机与"暴力扩容"的尽头

2026 年上半年，AI Agent 的上下文窗口竞赛已经到了一个荒谬的程度：

- Claude 支持 200K+ tokens
- GPT-4o 支持 128K tokens
- Gemini 甚至号称支持 1M+ tokens

**但更大的上下文窗口并没有解决问题，反而制造了新的问题。**

原因很简单：Agent 的上下文消耗是指数级增长的。一个典型的 AI 编码 Agent 工作流中：

```
┌────────────────────────────────────────────────────────┐
│  AI 编码 Agent 的单次任务 Token 消耗分解                    │
├────────────────────────────────────────────────────────┤
│  System Prompt (Skills + Rules):     ~3,000 tokens     │
│  代码库检索 (RAG top-k results):      ~15,000 tokens    │
│  工具输出 (Terminal, File read):      ~8,000 tokens     │
│  对话历史 (Multi-turn context):        ~12,000 tokens    │
│  文件内容 (Multi-file context):        ~20,000 tokens    │
├────────────────────────────────────────────────────────┤
│  总计:                                 ~58,000 tokens    │
│  成本 (Claude Sonnet, $3/M input):     ~$0.17/次        │
│  日活跃开发者 (100 次操作/天):           ~$17/人/天       │
└────────────────────────────────────────────────────────┘
```

对于一个 50 人的工程团队，仅上下文成本就可能达到 **$850/天 ≈ $25,500/月**。这还不包括推理 token 的成本。

更重要的是，**巨大的上下文窗口带来了三个隐性代价**：

1. **KV Cache 命中率暴跌**：即使内容相同，微小的前缀变化也会导致 KV Cache 完全失效，每次请求都是冷启动
2. **注意力稀释效应**：当上下文从 4K 膨胀到 100K，模型对关键信息的注意力权重被严重稀释（Lost in the Middle 现象在 Agent 场景下被放大）
3. **延迟指数增长**：更大的上下文 = 更长的 Prefill 时间 = 更高的 TTFT（Time to First Token）

行业给出的答案一直是"等模型更高效"或者"等上下文窗口更大"。但 Headroom 走了另一条路：**在数据进入 LLM 之前，先压缩它。**

---

## 一、Headroom 是什么：架构全景图

### 1.1 核心定位

Headroom 不是一个新的 LLM，不是一个新的 Agent 框架，也不是一个新的 RAG 系统。它是这些系统之间的**中间层**——一个专门为 AI Agent 的上下文设计的压缩层。

```
你的 Agent / 应用
（Claude Code, Cursor, Codex, LangChain, 自定义应用…）
│  prompts · 工具输出 · 日志 · RAG 结果 · 文件内容
▼
┌──────────────────────────────────────────────────────┐
│  Headroom（本地运行，数据不出境）                        │
│  ──────────────────────────────────────────────────  │
│  CacheAligner → ContentRouter → 压缩管道                │
│  ├─ SmartCrusher（结构化 JSON/日志）                     │
│  ├─ CodeCompressor（AST 感知代码压缩）                   │
│  └─ Kompress-base（HF 微调模型，通用文本）                │
│  │                                                    │
│  跨 Agent 内存 · 失败学习 · MCP 集成                      │
└──────────────────────────────────────────────────────┘
│  压缩后的 prompt + 按需检索工具
▼
LLM 提供商（Anthropic · OpenAI · Bedrock · …）
```

### 1.2 五种部署模式

Headroom 的巧妙之处在于它提供了五种接入方式，覆盖了从"零代码改动"到"深度集成"的全谱系：

| 模式 | 接入方式 | 适用场景 | 代码改动 |
|------|---------|---------|---------|
| **Library** | `compress(messages)` 函数调用 | Python/TS 应用深度集成 | 需要 |
| **Proxy** | `headroom proxy --port 8787` | 任何语言/框架，零代码改动 | 无需 |
| **Agent Wrap** | `headroom wrap claude/codex/cursor/aider` | 编码 Agent 一键接入 | 无需 |
| **MCP Server** | `headroom_compress`, `headroom_retrieve` | MCP 原生 Agent | 配置 |
| **SDK Wrapper** | `withHeadroom(new Anthropic())` | SDK 级中间件 | 少量 |

这种"渐进式采用"策略是 Headroom 快速获得采用的关键——你可以先以 Proxy 模式零成本验证效果，再逐步深入到 Library 或 SDK 级别。

---

## 二、压缩管道：六种算法的技术拆解

Headroom 的核心竞争力不在于"一种压缩算法"，而在于**六种针对不同内容类型的专用压缩器**的协同工作。

### 2.1 ContentRouter：内容感知的智能分流

压缩的第一步不是压缩，而是**识别**。ContentRouter 检测输入内容的类型，将其路由到最合适的压缩器：

```
输入内容
  │
  ├─ JSON 结构数据（API 响应、配置文件、日志）
  │     └──→ SmartCrusher
  │
  ├─ 源代码（Python, JS, Go, Rust, Java, C++）
  │     └──→ CodeCompressor
  │
  ├─ 自然语言文本（文档、注释、对话）
  │     └──→ Kompress-base
  │
  ├─ 图片（截图、UI 元素）
  │     └──→ ML 路由压缩（40-90% 减少）
  │
  └─ 混合内容
        └──→ 分段路由 + 重组
```

这种路由策略的本质是**"用正确的工具做正确的事"**。用一个通用压缩器处理所有类型的内容，就像用同一把螺丝刀拧所有螺丝——能做，但做不好。

### 2.2 SmartCrusher：结构化数据的"骨架提取"

SmartCrusher 是 Headroom 对 JSON/结构化数据的专用压缩器。它的核心洞察是：**结构化数据中充满了"骨架"和"血肉"，而 LLM 通常只需要骨架就能理解含义。**

以一个 100 条搜索结果的 API 响应为例：

```json
// 原始（约 17,765 tokens）
{
  "results": [
    {
      "id": 1,
      "title": "Fix: TypeError in UserService.getProfile",
      "body": "When calling UserService.getProfile with a null userId, the method throws a TypeError...",
      "labels": ["bug", "backend"],
      "comments": [
        {"author": "alice", "body": "I can reproduce this..."},
        {"author": "bob", "body": "The issue is in line 42..."}
      ],
      "created_at": "2026-05-15T10:30:00Z",
      // ... 更多字段
    },
    // ... 99 条类似记录
  ]
}

// SmartCrusher 压缩后（约 1,408 tokens，减少 92%）
{
  "results": [
    {"id": 1, "title": "Fix: TypeError in UserService.getProfile", "labels": ["bug", "backend"], "comments_n": 2, "summary": "null userId → TypeError"},
    // ... 99 条压缩记录
  ],
  "_headroom": {"original_keys": ["body","comments","created_at"], "retrieve": "headroom_retrieve(id)"}
}
```

SmartCrusher 的核心策略：

1. **数组去重**：识别重复的字段名和结构，提取 schema 模板
2. **值摘要**：将长文本替换为关键信息摘要
3. **嵌套扁平化**：减少嵌套层级，降低 token 计数
4. **可逆标记**：保留 `_headroom` 元数据，让 LLM 可以在需要时请求原始数据

**92% 的压缩率**在这个场景下意味着什么？意味着原来一次需要消耗 17,765 tokens 的代码搜索，现在只需要 1,408 tokens。对于一个每天执行 200 次代码搜索的 Agent，这相当于每天节省约 **320 万 tokens**。

### 2.3 CodeCompressor：AST 感知的代码压缩

这是 Headroom 最具技术深度的组件之一。

传统的代码压缩（如 minification）是语法感知的——它去掉空格和注释，但不理解代码的语义。CodeCompressor 走得更远：**它通过 AST（抽象语法树）理解代码的结构和语义，在保持功能可理解性的前提下进行压缩。**

以 Python 为例，CodeCompressor 的处理流程：

```python
# 原始代码（85 tokens）
class UserService:
    def get_profile(self, user_id: int) -> UserProfile:
        """
        Fetch user profile by ID.
        
        Args:
            user_id: The unique identifier of the user.
            
        Returns:
            UserProfile object containing user details.
            
        Raises:
            UserNotFound: If user_id does not exist.
            DatabaseError: If database connection fails.
        """
        if not user_id:
            raise ValueError("user_id is required")
        
        try:
            result = self.db.query(
                "SELECT * FROM users WHERE id = %s",
                (user_id,)
            )
            if not result:
                raise UserNotFound(user_id)
            return UserProfile.from_row(result[0])
        except psycopg2.Error as e:
            raise DatabaseError(f"Query failed: {e}")

# CodeCompressor 压缩后（约 35 tokens，减少 59%）
class UserService:
    def get_profile(self, user_id: int) -> UserProfile:
        """Fetch user profile by ID. Raises: UserNotFound, DatabaseError."""
        if not user_id: raise ValueError("user_id required")
        try:
            result = self.db.query("SELECT * FROM users WHERE id = %s", (user_id,))
            if not result: raise UserNotFound(user_id)
            return UserProfile.from_row(result[0])
        except psycopg2.Error as e: raise DatabaseError(f"Query failed: {e}")
```

CodeCompressor 的关键技术决策：

1. **保留 AST 结构**：压缩后的代码仍然可以解析为合法的 AST
2. **文档字符串压缩**：将冗长的 docstring 压缩为单行摘要，保留关键信息
3. **格式化精简**：去掉多余的空行和缩进，但保留缩进层级
4. **语义等价性**：压缩不改变代码的语义，只是改变了呈现密度

对于支持的语言（Python、JavaScript/TypeScript、Go、Rust、Java、C++），CodeCompressor 在典型代码库上可以达到 **40-60% 的压缩率**，且不影响代码理解能力。

### 2.4 Kompress-base：面向 Agent 痕迹训练的文本压缩模型

这是 Headroom 唯一的 ML 组件——一个在 HuggingFace 上开源的微调模型（`chopratejas/kompress-base`）。

与通用文本摘要模型不同，Kompress-base 是在 **agentic traces**（Agent 的工作痕迹）上训练的。这意味着它学习的是"Agent 需要什么样的压缩"，而不是"人类读者需要什么样的摘要"。

训练数据的关键特征：

| 特征 | 说明 |
|------|------|
| **Agent 问答对** | 压缩前后的 Agent 回答质量对比作为训练信号 |
| **任务保留度** | 压缩后，Agent 完成同一任务的成功率是否下降 |
| **多轮对话连贯性** | 压缩后的对话历史是否能维持多轮推理 |

训练目标不是"最小化 token 数"，而是**"在最小化 token 数的同时最大化 Agent 任务成功率"**。这是一个多目标优化问题，Kompress-base 通过 Pareto 前沿搜索来找到最佳平衡点。

### 2.5 CacheAligner：被忽视的 KV Cache 优化

这是 Headroom 中最容易被忽略、但可能最有价值的组件之一。

**问题**：现代 LLM 提供商（Anthropic、OpenAI）都使用了 KV Cache 来加速重复请求。但 KV Cache 的命中条件是——请求的 prefix 必须完全一致。在 Agent 场景中，即使核心内容相同，每次请求的 System Prompt 或上下文前缀的微小变化（如时间戳、随机 ID、会话 ID）都会导致 KV Cache 完全失效。

```
请求 A: "你是一个助手。时间: 2026-06-04 08:00:01。请分析以下代码..."  ← Cache Miss
请求 B: "你是一个助手。时间: 2026-06-04 08:00:15。请分析以下代码..."  ← Cache Miss

即使"请分析以下代码..."之后的内容完全相同，KV Cache 也不会命中。
```

CacheAligner 的解决方案：**稳定前缀，对齐缓存**。

```
CacheAligner 处理后:
"你是一个助手。[TIME_STAMP]。请分析以下代码..."
                    ↑ 可变部分被标准化
```

通过在压缩管道中标准化可变前缀（时间戳、会话 ID、随机种子等），CacheAligner 可以让 KV Cache 命中率从接近 0% 提升到 **60-80%**。这带来的加速效果是：

- **TTFT 降低 40-60%**：KV Cache 命中意味着跳过整个 Prefill 阶段
- **成本降低 50%+**：缓存命中的请求在 Anthropic 的计费中可以享受 prefix caching 折扣
- **延迟稳定性提升**：不再出现"有时 200ms，有时 5s"的延迟抖动

CacheAligner 的价值在于它解决了一个**系统性但被忽视的问题**。大多数人关注模型推理速度，却忽略了 KV Cache 失效带来的隐性成本。

---

## 三、CCR：可逆压缩——信息不丢失的承诺

### 3.1 核心机制

Headroom 最革命性的设计之一是 **CCR（Compress-Context-Retrieve，压缩-上下文-检索）** 机制。

传统压缩的困境是二选一：
- **有损压缩**：节省 token，但丢失信息，可能影响回答质量
- **无损压缩**：保留信息，但 token 节省有限

CCR 打破了这个二选一：**先压缩发送，按需检索原文。**

```
工作流程:
1. Headroom 压缩内容 → 发送压缩版本给 LLM（少量 token）
2. LLM 处理压缩内容 → 大部分任务可以完成
3. LLM 需要细节时 → 调用 headroom_retrieve 工具获取原始内容
4. 获取原文后 → 继续推理
```

这本质上是为 LLM 提供了一个**"局部放大"**的能力——就像你用 Google Maps 看地图，大部分时候看概览就够了，需要时再放大看细节。

### 3.2 技术实现

CCR 的实现包含三个关键组件：

1. **本地存储**：压缩后的内容关联的原始数据存储在本地 SQLite 中，数据不出境
2. **检索工具**：`headroom_retrieve` 作为 MCP 工具暴露给 LLM，LLM 可以按需调用
3. **引用标记**：压缩内容中包含 `_headroom` 元数据，标记哪些部分可以检索

```json
{
  "compressed_data": {"id": 1, "summary": "TypeError in UserService..."},
  "_headroom": {
    "type": "compressible",
    "retrieve_key": "result_1",
    "original_size": 1408,
    "compressed_size": 126
  }
}
```

### 3.3 对 Agent 行为的影响

CCR 改变了 Agent 与信息的交互方式：

| 维度 | 传统方式 | CCR 方式 |
|------|---------|---------|
| 信息获取 | 一次性全部加载 | 按需分层加载 |
| Token 预算 | 固定上限 | 弹性可扩展 |
| 信息完整性 | 要么全有要么全无 | 概览 + 按需深入 |
| Agent 自主性 | 被动接收上下文 | 主动决定是否需要更多细节 |

这种"按需深入"的模式更接近人类的工作方式——我们不会一次性阅读所有相关文档，而是先扫一眼，需要时再深入。

---

## 四、基准测试：数据说话

### 4.1 压缩率基准

Headroom 在真实 Agent 工作负载上的压缩表现：

| 工作负载 | 压缩前 | 压缩后 | 节省率 |
|---------|--------|--------|--------|
| 代码搜索（100 条结果） | 17,765 | 1,408 | **92%** |
| SRE 事件调试 | 65,694 | 5,118 | **92%** |
| GitHub Issue 分类 | 54,174 | 14,761 | **73%** |
| 代码库探索 | 78,502 | 41,254 | **47%** |

**关键观察**：压缩率与内容的结构化程度正相关。结构化程度越高（如 JSON API 响应、日志），压缩率越高。非结构化内容（如代码探索中的长文本讨论）压缩率相对较低，但仍然显著。

### 4.2 精度保持基准

节省 token 是一回事，保持答案是另一回事。Headroom 在标准基准上的表现：

| 基准 | 类别 | N | 基线 | Headroom | 差异 |
|------|------|---|------|---------|------|
| GSM8K | 数学推理 | 100 | 0.870 | 0.870 | **±0.000** |
| TruthfulQA | 事实问答 | 100 | 0.530 | 0.560 | **+0.030** |
| SQuAD v2 | 阅读理解 | 100 | — | 97% | 19% 压缩 |
| BFCL | 工具调用 | 100 | — | 97% | 32% 压缩 |

**最令人惊讶的发现**：在 TruthfulQA 上，Headroom 不仅没有降低精度，反而提升了 3 个百分点。可能的解释是：**适度的信息去噪减少了上下文中的干扰信号，让模型更专注于关键信息。**

这与一些学术研究的方向一致——加州大学伯克利分校 2026 年的一篇论文 *"Attention Dilution in Long-Context LLMs"* 发现，当上下文超过一定长度时，模型的有效注意力容量会饱和，额外信息反而会稀释关键信号的注意力权重。Headroom 的压缩可能恰好缓解了这个问题。

### 4.3 成本效益分析

让我们做一个粗略的成本估算：

```
假设场景：50 人工程团队，每人每天 100 次 Agent 操作

无压缩:
  每次 ~58,000 tokens (input)
  日消耗: 50 × 100 × 58,000 = 2.9 亿 tokens
  日成本 (Claude Sonnet $3/M): $870
  月成本: ~$26,100

Headroom 压缩（按平均 70% 节省计算）:
  每次 ~17,400 tokens (compressed input)
  日消耗: 50 × 100 × 17,400 = 8,700 万 tokens
  日成本: $261
  月成本: ~$7,830
  
  月节省: $18,270
  年节省: ~$219,240
```

这还不包括 CacheAligner 带来的 KV Cache 命中率提升所带来的额外折扣，以及降低延迟带来的生产力收益。

---

## 五、超越压缩：Headroom 的生态野心

如果 Headroom 只是一个压缩工具，它不值得在几天内获得 9,600 星。真正让它与众不同的是两个"超出预期"的功能。

### 5.1 跨 Agent 内存

Headroom 提出了一个有趣的概念：**不同 Agent 之间可以共享压缩后的上下文记忆。**

```
Claude Code  ←→  Headroom 共享存储  ←→  Codex
     │                                    │
     └──── 同一压缩上下文，不同 Agent 使用 ────┘
```

这意味着：
- 你在 Claude Code 中探索过的代码库上下文，可以被 Codex 复用
- 不同 Agent 的对话历史可以合并、去重、共享
- 跨 Agent 协作时，不需要重复传递相同的上下文

这在多 Agent 工作流中尤其有价值。想象一个场景：一个 Agent 负责代码搜索，另一个负责代码生成。在传统架构中，每个 Agent 都需要独立加载完整的上下文。有了 Headroom 的跨 Agent 内存，第二个 Agent 可以直接复用第一个 Agent 压缩后的上下文，节省大量 token 和时间。

### 5.2 headroom learn：从失败中学习的闭环

这是 Headroom 最被低估的功能。

`headroom learn` 可以分析 Agent 的失败会话，自动将修正建议写入 `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`。

工作流程：
1. 收集失败的 Agent 会话
2. 分析失败模式（是上下文不足？压缩过度？工具调用错误？）
3. 生成修正策略
4. 写入 Agent 的配置文件

这形成了一个**自我改进的闭环**：

```
Agent 失败 → headroom learn 分析 → 生成修正 → 写入配置 → Agent 下次做得更好
```

从系统论的角度看，这是将"经验教训"从人类手动编写 Agent 规则，转变为 Agent 自己从失败中提取规则。这与自改进 Agent（Self-Improving Agent）的研究方向高度一致。

---

## 六、竞争格局：Headroom 在 Context Compression 生态中的位置

Context Compression 正在成为一个独立的 AI 基础设施赛道。以下是主要玩家：

| 项目 | 核心方法 | 压缩率 | 可逆 | 跨 Agent | 开源 |
|------|---------|--------|------|---------|------|
| **Headroom** | 多算法管道 + CCR + CacheAligner | 60-95% | ✅ | ✅ | ✅ |
| **Mnemo** | 本地优先 AI 记忆层 | N/A | — | — | ✅ |
| **Supermemory** | 记忆 API + 快速检索 | N/A | — | ✅ | ✅ |
| Anthropic Prompt Caching | KV Cache 前缀缓存 | 成本节省 50% | N/A | ❌ | ❌ |
| OpenAI Context Compaction | 模型级上下文压缩 | 有限 | ❌ | ❌ | ❌ |

Headroom 的差异化在于：
1. **多算法策略**：不是"一种算法打天下"，而是针对不同内容类型使用不同压缩器
2. **可逆性**：CCR 机制保证信息不丢失
3. **KV Cache 优化**：CacheAligner 解决了一个被忽视但影响巨大的问题
4. **部署灵活性**：从 Proxy 到 Library 到 MCP，渐进式采用

---

## 七、批判性分析：Headroom 的局限与风险

作为一个深度分析，我们需要看到硬币的另一面。

### 7.1 压缩引入的认知偏差

即使 Headroom 声称"保持答案质量不变"，压缩本身不可避免地会引入**信息选择偏差**。谁来决定什么信息重要？SmartCrusher 的 JSON 压缩策略对 API 响应有效，但可能对调试堆栈跟踪过度简化。

**风险**：在边缘案例中，被压缩掉的"次要信息"恰恰是解决问题的关键线索。

### 7.2 CCR 检索的延迟成本

按需检索原文的机制虽然优雅，但引入了**额外的往返延迟**。如果 LLM 频繁需要检索原文（在复杂调试场景中很常见），CCR 的优势会被抵消。

**缓解策略**：IntelligentContext 组件会根据上下文重要性评分来决定压缩级别，但对重要性评分的准确性本身就是一个开放问题。

### 7.3 生态锁定风险

Headroom 目前支持主流 Agent（Claude Code、Codex、Cursor、Aider、Copilot CLI、OpenClaw），但它的跨 Agent 内存和失败学习功能在 Headroom 生态内才能发挥最大价值。如果未来出现竞争标准，迁移成本可能不低。

### 7.4 开源可持续性问题

一个日增 3,500 星的项目，其维护者能否跟上需求？Headroom 的核心团队规模、商业模式（目前完全开源免费）、以及长期维护计划都是值得关注的因素。

---

## 八、生产实践：如何开始使用 Headroom

### 8.1 最快上手（30 秒）

```bash
# 安装
pip install "headroom-ai[all]"

# 包装你的编码 Agent
headroom wrap claude

# 查看节省效果
headroom perf
```

### 8.2 Proxy 模式（零代码改动）

```bash
headroom proxy --port 8787
```

然后将你的 LLM API 端点指向 `http://localhost:8787`，即可享受透明压缩。

### 8.3 生产环境建议

对于生产部署，建议分阶段进行：

1. **第一阶段**：Proxy 模式，观察 1-2 周，确认压缩率和建议质量符合预期
2. **第二阶段**：开启 CacheAligner，测量 KV Cache 命中率和延迟改善
3. **第三阶段**：启用跨 Agent 内存（如果有多 Agent 工作流）
4. **第四阶段**：开启 `headroom learn`，建立自我改进闭环

---

## 结语：Context Compression Layer——AI Agent 基础设施的新大陆

Headroom 的爆发性增长不是一个偶然现象。它反映了一个更深层的产业趋势：

**AI Agent 的基础设施正在从"模型为中心"向"上下文工程为中心"演进。**

在模型能力趋于饱和的 2026 年下半年，决定 Agent 表现的不再是"谁的模型更强"，而是"谁更擅长管理 Agent 的上下文"——如何压缩、如何对齐、如何检索、如何共享、如何学习。

Headroom 是这个范式转移的第一个系统性实践者。它可能不是最终答案（没有哪个项目是），但它清晰地勾勒出了 Context Compression Layer 作为独立基础设施栈层的轮廓。

> **"更好的上下文工程，比更大的上下文窗口，更能决定 AI Agent 的生产力上限。"**

---

**参考资料：**

1. Headroom 官方文档: https://headroom-docs.vercel.app/docs
2. Headroom GitHub 仓库: https://github.com/chopratejas/headroom
3. Kompress-base 模型卡片: https://huggingface.co/chopratejas/kompress-base
4. Dharma AI - Direct Preference Optimization Beyond Chatbots: https://huggingface.co/blog/Dharma-AI/direct-preference-optimization-beyond-chatbots
5. HCompany - Holo3.1: Fast & Local Computer Use Agents: https://huggingface.co/blog/Hcompany/holo31
6. JetBrains - Mellum2: A 12B Mixture-of-Experts Model: https://huggingface.co/blog/JetBrains/mellum2-launch
7. UC Berkeley - "Attention Dilution in Long-Context LLMs" (2026)
8. Mnemo - Local-first AI Memory Layer: https://github.com/zaydmulani09/mnemo
9. Supermemory - Memory API for AI Era: https://github.com/supermemoryai/supermemory

---

*本文档由 AI 辅助生成，经人工审核。欢迎在 GitHub 讨论或提交 Issue。*
