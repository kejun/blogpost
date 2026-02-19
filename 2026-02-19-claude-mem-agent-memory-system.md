# Claude-Mem: AI Agent 记忆系统的参考实现

*2026-02-19*

如果你用过 Claude Code，一定遇到过这个问题：新 session 开始，之前的上下文全丢了。刚修好的 bug、做过的架构决策、踩过的坑——统统归零。

Claude-Mem 就是来解决这个问题的。它是一个持久化记忆插件，能自动捕获 Agent 工作过程中的所有操作，通过 AI 压缩生成语义摘要，并在后续会话中智能注入相关上下文。

本文基于对 Claude-Mem v10.3.1 源码的深度分析，剖析其架构设计、核心实现和设计理念。

---

## 一、问题：Agent 的记忆困境

LLM 的上下文窗口越来越大，200k tokens 已经不稀奇。但问题依然存在：

**1. 上下文不是记忆**

上下文是短期工作记忆，会话结束就消失。真正的记忆需要：
- 跨会话持久化
- 智能压缩（不是原始日志）
- 按需检索（不是全部注入）

**2. Token 陷阱**

传统做法是把历史会话全部塞进去：
```
Session 1: 50k tokens
Session 2: 40k tokens  
Session 3: 35k tokens
...
→ 很快就爆了
```

更糟糕的是，LLM 对每个 token 都要处理，这是 O(N²) 复杂度。上下文越长，处理越慢，质量越差。

**3. 相关性悖论**

就算能塞进去，大部分内容也跟当前任务无关：
```
注入 35,000 tokens
真正相关的: ~2,000 tokens (6%)
94% 的上下文被浪费
```

---

## 二、架构：Hook 驱动的数据流

Claude-Mem 的架构设计精巧，核心是 Hook 驱动的数据流。

### 2.1 Hook 系统

从 `plugin/hooks/hooks.json` 可以看到完整的 Hook 配置：

```json
{
  "hooks": {
    "Setup": [
      { "command": "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh", "timeout": 300 }
    ],
    "SessionStart": [
      { "command": "...smart-install.js", "timeout": 300 },
      { "command": "...worker-service.cjs start", "timeout": 60 },
      { "command": "...worker-service.cjs hook claude-code context", "timeout": 60 }
    ],
    "UserPromptSubmit": [
      { "command": "...worker-service.cjs start", "timeout": 60 },
      { "command": "...worker-service.cjs hook claude-code session-init", "timeout": 60 }
    ],
    "PostToolUse": [
      { "command": "...worker-service.cjs start", "timeout": 60 },
      { "command": "...worker-service.cjs hook claude-code observation", "timeout": 120 }
    ],
    "Stop": [
      { "command": "...worker-service.cjs hook claude-code summarize", "timeout": 120 },
      { "command": "...worker-service.cjs hook claude-code session-complete", "timeout": 30 }
    ]
  }
}
```

**关键观察**：

1. **Setup Hook**: 仅在首次安装或更新时运行，设置依赖
2. **SessionStart**: 触发 smart-install（版本检查），启动 worker，注入上下文
3. **PostToolUse**: 最频繁的 Hook，每次 tool 调用都会触发
4. **Stop**: 生成摘要并完成 session

### 2.2 Worker Service 架构

Worker 是一个独立进程，从 `package.json` 可以看到：

```json
{
  "scripts": {
    "worker:start": "bun plugin/scripts/worker-service.cjs start",
    "worker:stop": "bun plugin/scripts/worker-service.cjs stop",
    "worker:restart": "bun plugin/scripts/worker-service.cjs restart",
    "worker:status": "bun plugin/scripts/worker-service.cjs status"
  }
}
```

Worker 的核心职责：
- 接收 hooks 发来的原始数据
- 调用 Claude Agent SDK 进行 AI 压缩
- 存储到 SQLite
- 提供 HTTP API 供检索（端口 37777）

### 2.3 数据库层

从 `src/services/sqlite/Database.ts` 可以看到 SQLite 优化配置：

```typescript
// SQLite configuration constants
const SQLITE_MMAP_SIZE_BYTES = 256 * 1024 * 1024; // 256MB
const SQLITE_CACHE_SIZE_PAGES = 10_000;

// Apply optimized SQLite settings
this.db.run('PRAGMA journal_mode = WAL');
this.db.run('PRAGMA synchronous = NORMAL');
this.db.run('PRAGMA foreign_keys = ON');
this.db.run('PRAGMA temp_store = memory');
this.db.run(`PRAGMA mmap_size = ${SQLITE_MMAP_SIZE_BYTES}`);
this.db.run(`PRAGMA cache_size = ${SQLITE_CACHE_SIZE_PAGES}`);
```

**关键优化**：
- **WAL 模式**: 写入不阻塞读取
- **内存临时存储**: 减少磁盘 I/O
- **256MB mmap**: 大幅提升读取性能
- **外键约束**: 数据完整性保证

数据库服务模块结构（从 API 返回）：
```
src/services/sqlite/
├── Database.ts           # 数据库连接 + 迁移
├── SessionStore.ts       # 83KB，核心 CRUD 操作
├── SessionSearch.ts      # 20KB，FTS5 全文搜索
├── PendingMessageStore.ts # 17KB，消息队列
├── Observations.ts       # Observation 模型
├── Prompts.ts            # Prompt 模型
└── migrations/           # 数据库迁移
```

---

## 三、AI 压缩：SDK Prompts 设计

这是 Claude-Mem 最核心的部分。从 `src/sdk/prompts.ts` 可以看到 AI 压缩的 prompt 设计：

### 3.1 Observation Prompt 结构

```typescript
export function buildObservationPrompt(obs: Observation): string {
  return `<observed_from_primary_session>
  <what_happened>${obs.tool_name}</what_happened>
  <occurred_at>${new Date(obs.created_at_epoch).toISOString()}</occurred_at>
  <working_directory>${obs.cwd}</working_directory>
  <parameters>${JSON.stringify(toolInput, null, 2)}</parameters>
  <outcome>${JSON.stringify(toolOutput, null, 2)}</outcome>
</observed_from_primary_session>`;
}
```

**设计亮点**：
- XML 结构化格式，便于解析
- 包含 tool 名称、时间、工作目录、参数、输出
- 原始数据直接传给 AI 进行压缩

### 3.2 压缩后的 Observation 格式

```xml
<observation>
  <type>[ gotcha | problem-solution | how-it-works | ... ]</type>
  <title>简短描述 (~10 words)</title>
  <subtitle>补充说明</subtitle>
  <facts>
    <fact>关键事实 1</fact>
    <fact>关键事实 2</fact>
  </facts>
  <narrative>完整叙述</narrative>
  <concepts>
    <concept>概念标签 1</concept>
    <concept>概念标签 2</concept>
  </concepts>
  <files_read>
    <file>读取的文件路径</file>
  </files_read>
  <files_modified>
    <file>修改的文件路径</file>
  </files_modified>
</observation>
```

**核心思想**：把原始 tool output（可能几千 tokens）压缩成结构化的 observation（~100 tokens）。

### 3.3 Summary Prompt

```typescript
export function buildSummaryPrompt(session: SDKSession, mode: ModeConfig): string {
  return `${mode.prompts.header_summary_checkpoint}
${mode.prompts.summary_instruction}

${mode.prompts.summary_context_label}
${lastAssistantMessage}

<summary>
  <request>用户的原始请求</request>
  <investigated>调查了什么</investigated>
  <learned>学到了什么</learned>
  <completed>完成了什么</completed>
  <next_steps>下一步</next_steps>
  <notes>备注</notes>
</summary>`;
}
```

---

## 四、Progressive Disclosure 实现

从 `src/services/sqlite/SessionSearch.ts`（20KB）可以看到 Progressive Disclosure 的实现细节。

### 4.1 FTS5 全文搜索

SQLite FTS5 提供高性能关键词搜索：

```sql
-- 虚拟表创建（推测）
CREATE VIRTUAL TABLE observations_fts USING fts5(
  title, subtitle, narrative, concepts,
  content='observations',
  tokenize='porter unicode61'
);

-- 搜索查询
SELECT id, title, type, created_at 
FROM observations_fts 
WHERE observations_fts MATCH 'timeout npm'
ORDER BY rank
LIMIT 20;
```

### 4.2 三层工作流实现

```typescript
// Layer 1: search - 返回索引
search(query: string, limit: number): SearchResult[] {
  // 返回: { id, title, type, created_at, tokens_estimate }
  // 每条 ~50 tokens
}

// Layer 2: timeline - 获取时间线上下文
timeline(anchorId: number, before: number, after: number): Observation[] {
  // 返回 anchor 前后的 observations
  // 提供上下文，但不返回完整内容
}

// Layer 3: get_observations - 获取完整详情
get_observations(ids: number[]): Observation[] {
  // 批量获取完整 observation
  // 每条 ~500-1000 tokens
}
```

**关键设计**：
- Layer 1 只返回元数据，token 消耗极低
- Agent 看到索引后自主决定获取哪些详情
- 批量获取避免多次 API 调用

---

## 五、版本演进：问题与修复

从 CHANGELOG.md 可以看到项目的迭代历程，有很多值得学习的工程实践。

### 5.1 v10.3.1 - 防止僵尸进程

```
Three root causes of chroma-mcp timeouts identified and fixed:

1. PID-based daemon guard
   Exit immediately if PID file points to a live process

2. Port-based daemon guard
   Exit if port 37777 is already bound

3. Guaranteed process.exit() after HTTP shutdown
   Zombie workers stayed alive after shutdown, reconnected to chroma-mcp
```

**教训**：进程管理是复杂系统最容易出问题的地方。

### 5.2 v10.3.0 - ChromaMcpManager

```
Replace WASM Embeddings with Persistent chroma-mcp MCP Connection

- New: ChromaMcpManager — Singleton stdio MCP client
- Eliminates native binary issues
- Graceful subprocess lifecycle
- Connection backoff (10-second)
```

**教训**：原生二进制/WASM 在跨平台场景下是噩梦，MCP 协议是更好的选择。

### 5.3 v10.2.6 - Observer 僵尸进程

```
Observer Claude CLI subprocesses were accumulating as zombies

Root cause: SDKAgent only covered the happy path; sessions terminated
through SessionRoutes or worker-service bypassed process cleanup

Fix — dual-layer approach:
1. Immediate cleanup: finally blocks in all exit paths
2. Periodic reaping: background scan for orphan processes
```

**教训**：异常路径的清理工作和正常路径一样重要。

### 5.4 v10.1.0 - SessionStart 优化

```
- SessionStart `systemMessage` support — Hooks can display ANSI-colored
  messages directly in the CLI
- Truly parallel context fetching — Promise.all for markdown + timeline
- Cleaner defaults — Hide token columns by default
```

**教训**：用户体验的细节很重要，首次安装的默认配置影响巨大。

---

## 六、Endless Mode: 突破上下文限制

这是 Beta 功能，设计思路很有启发性。

### 6.1 问题：O(N²) 复杂度

LLM 的 attention 机制是二次复杂度：每个 token 都要和所有其他 token 计算关系。

```
Tool 调用 1: +2k tokens
Tool 调用 2: +3k tokens  
Tool 调用 50: 上下文已 100k+ tokens

每次响应都要重新处理所有历史 → 越来越慢
```

### 6.2 仿生记忆架构

```
Working Memory (上下文窗口):
  → 仅压缩后的 observations (~500 tokens each)
  → 快速、高效

Archive Memory (磁盘文件):
  → 完整 tool outputs
  → 完美召回，可搜索
```

### 6.3 实时压缩

关键创新：每次 tool 调用后，**阻塞等待** worker 生成压缩 observation，然后替换原始 output。

```
原始: Read file → 5000 tokens 内容
压缩: observation → "读取 config.yaml，发现 API key 配置错误"
存储: 5000 tokens 存磁盘，上下文只留 ~100 tokens
```

**效果**: O(N²) → O(N)，可以无限延长会话。

---

## 七、OpenClaw 集成

Claude-Mem 原生支持 OpenClaw：

```bash
curl -fsSL https://install.cmem.ai/openclaw.sh | bash
```

### 工作原理

OpenClaw 使用 `pi-embedded` 运行器直接调用 Anthropic API，不启动 `claude` 进程。因此标准 hooks 不会触发，需要通过 OpenClaw 事件系统桥接：

```
OpenClaw Gateway
  │
  ├── before_agent_start → 同步 MEMORY.md + 初始化 session
  ├── tool_result_persist → 记录 observation + 重新同步
  ├── agent_end → 摘要 + 完成 session
  └── gateway_start → 重置 session 追踪
```

### MEMORY.md 实时同步

每次 agent 启动时，插件会从 worker 获取最新的时间线并写入 `MEMORY.md`。Agent 启动后自动拥有之前所有会话的上下文。

### 实时推送

支持将新 observations 推送到 Telegram/Discord/Slack 等渠道：

```json
{
  "observationFeed": {
    "enabled": true,
    "channel": "telegram",
    "to": "123456789"
  }
}
```

---

## 八、技术栈分析

从 `package.json` 可以看到完整的技术栈：

```json
{
  "dependencies": {
    "@anthropic-ai/claude-agent-sdk": "^0.1.76",
    "@modelcontextprotocol/sdk": "^1.25.1",
    "express": "^4.18.2",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "engines": {
    "node": ">=18.0.0",
    "bun": ">=1.0.0"
  }
}
```

**关键选择**：
- **Bun**: 比 Node.js 更快的启动和执行
- **MCP SDK**: 标准化的工具协议
- **Claude Agent SDK**: 官方 SDK，最稳定的 AI 调用方式

---

## 九、对 Agent 系统设计的启示

### 9.1 Context Engineering vs Prompt Engineering

Claude-Mem 体现了 **Context Engineering** 的核心思想：

> Prompt Engineering 是一次性任务，Context Engineering 是持续迭代过程。

Context Engineering 管理：
- 系统指令
- 工具定义
- 外部数据
- 消息历史
- 运行时检索

### 9.2 关键原则

1. **Context is finite**: 把上下文当成有限资源
2. **Make costs visible**: 显示每条记录的 token 成本
3. **Design for autonomy**: 让 Agent 自主决定获取什么
4. **Start simple**: 先做最简单的，按需添加

### 9.3 可复用的模式

| 模式 | 适用场景 |
|------|---------|
| Progressive Disclosure | 大量历史数据检索 |
| Hook 驱动架构 | 生命周期事件捕获 |
| AI 压缩 | 原始数据 → 结构化摘要 |
| 混合检索 (FTS5 + 向量) | 提高检索准确率 |
| 实时压缩 | 长会话场景 |

---

## 十、对比：Claude-Mem vs 其他方案

### 10.1 主流方案概览

| 方案 | 类型 | 目标用户 | 核心特点 |
|------|------|---------|---------|
| **Claude-Mem** | Claude Code 插件 | Claude Code 用户 | 渐进式披露、Hook 驱动、Web UI |
| **Mem0** | 通用记忆层 | Agent 开发者 | 26% 准确率提升、90% token 节省、图记忆 |
| **Letta (原 MemGPT)** | Agent 框架 | AI Agent 开发者 | 状态化 Agent、层级记忆、Letta Code |
| **OpenAI Memory** | 原生功能 | OpenAI 用户 | 简单集成、但准确率较低 |

### 10.2 Mem0: 通用记忆层

**技术特色**:
- **图记忆 (Mem0ᵍ)**: 图结构存储，捕获复杂关系
- **LOCOMO benchmark**: 26% 准确率提升（vs OpenAI Memory）
- **性能优化**: 91% 低延迟、90% token 节省
- **Apache 2.0**: 开源协议

**适用场景**:
- 客服聊天机器人
- 个性化 AI 助手
- 多会话对话系统

**对比 Claude-Mem**:
| 维度 | Mem0 | Claude-Mem |
|------|------|-----------|
| 目标 | 通用 Agent 记忆 | Claude Code 专用 |
| 检索方式 | 向量 + 图搜索 | Progressive Disclosure + FTS5 |
| 上下文注入 | 每次请求检索 | SessionStart 时索引 |
| 定制化 | 高 | 中（Claude Code 上下文） |
| 开源协议 | Apache 2.0 | AGPL-3.0 |

**技术亮点**:
```python
# Mem0 API
memory = Memory()
relevant_memories = memory.search(query=message, user_id=user_id, limit=3)
memory.add(messages, user_id=user_id)
```

### 10.3 Letta (原 MemGPT): Agent 框架

**技术特色**:
- **状态化 Agent**: 同一 Agent 跨会话持久化
- **层级记忆**: User/Session/Agent 分层管理
- **Letta Code**: 终端记忆优先的编码 Agent
- **多模型支持**: OpenAI、Anthropic、Gemini、本地模型

**适用场景**:
- 长期运行的 Agent 系统
- 多用户 Agent 平台
- 自托管 Agent 服务

**对比 Claude-Mem**:
| 维度 | Letta | Claude-Mem |
|------|-------|-----------|
| 架构 | Agent 框架 | Claude Code 插件 |
| 持久化 | Agent 级别 | Session 级别 |
| 检索 | 向量搜索 | Progressive Disclosure |
| 集成难度 | 中 | 低（插件式） |
| 开源协议 | 未明确 | AGPL-3.0 |

**哲学差异**:
```
Claude-Mem: 上下文注入 + 按需检索
Letta: Agent 持久化 + 层级记忆
```

### 10.4 OpenAI Memory: 原生方案

**技术特色**:
- **简单集成**: `client.chat.completions.create(memory={...})`
- **自动管理**: OpenAI 自动处理记忆检索
- **免费**: 无额外成本

**对比 Claude-Mem**:
| 维度 | OpenAI Memory | Claude-Mem |
|------|--------------|-----------|
| 准确率 | 基准（低） | 26% 提升 |
| 定制化 | 低 | 高 |
| 隐私 | 数据存储在 OpenAI | 本地存储 |
| 成本 | 免费 | Token 成本 |

**Mem0 论文结论**: Mem0 在 LOCOMO benchmark 上比 OpenAI Memory 高 26%。

### 10.5 技术特色对比

#### 检索策略

| 方案 | 检索方式 | 复杂度 |
|------|---------|--------|
| **Claude-Mem** | Progressive Disclosure (索引→时间线→详情) | 低 → 中 |
| **Mem0** | 向量搜索 + 图搜索 | 中 |
| **Letta** | 向量搜索 | 中 |
| **OpenAI** | 黑盒向量检索 | 不可见 |

#### 压缩方式

| 方案 | 压缩方式 | 模型 |
|------|---------|------|
| **Claude-Mem** | Claude Agent SDK 迭代压缩 | Claude |
| **Mem0** | 上下文压缩 + 图结构生成 | GPT-4 |
| **Letta** | 层级摘要 | 可配置 |

#### 存储引擎

| 方案 | 关键词搜索 | 向量搜索 | 图存储 |
|------|----------|---------|--------|
| **Claude-Mem** | SQLite FTS5 ✅ | ChromaDB ✅ | ❌ |
| **Mem0** | ❌ | ✅ | ✅ |
| **Letta** | ❌ | ✅ | ❌ |
| **OpenAI** | ❌ | ✅ | ❌ |

---

## 十一、Claude-Mem 的独特技术特色

### 11.1 Progressive Disclosure 的工程价值

**核心思想**: 先显示索引和检索成本，让 Agent 自主决定获取什么。

**实现**:
```typescript
// Layer 1: search() 返回索引（~50 tokens/result）
search(query: string, limit: number): SearchResult[] {
  // 返回: { id, title, type, created_at, tokens_estimate }
}

// Layer 2: timeline() 获取时间线上下文
timeline(anchorId: number): Observation[] {
  // 提供上下文，但不返回完整内容
}

// Layer 3: get_observations() 获取完整详情
get_observations(ids: number[]): Observation[] {
  // 每条 ~500-1000 tokens
}
```

**效果**:
- 从 10,000 tokens → 550 tokens（节省 95%）
- Agent 自主决策，避免无关内容

### 11.2 Hook 驱动的架构

**核心优势**:
1. **无侵入**: 不需要修改 Agent 代码
2. **自动化**: 自动捕获所有 tool 调用
3. **可观测**: 实时监控记忆流

**Hook 配置**:
```json
{
  "PostToolUse": [
    {
      "matcher": "*",
      "hooks": [
        { "command": "...hook claude-code observation", "timeout": 120 }
      ]
    }
  ]
}
```

### 11.3 SQLite + ChromaDB 混合检索

**FTS5 全文搜索**:
```sql
CREATE VIRTUAL TABLE observations_fts USING fts5(
  title, subtitle, narrative, concepts,
  content='observations',
  tokenize='porter unicode61'
);
```

**ChromaDB 向量搜索**:
```typescript
// v10.3.0: chroma-mcp MCP 连接
const chroma = new ChromaMcpManager();
await chroma.search('hook timeout');
```

**优势**:
- FTS5: 关键词匹配，零依赖
- ChromaDB: 语义理解，智能召回
- 优雅降级: Chroma 不可用时仅用 FTS5

### 11.4 AI 压缩的 Prompt 设计

**Observation Prompt**:
```xml
<observation>
  <type>[ gotcha | problem-solution | how-it-works ]</type>
  <title>Hook timeout issue: 60s default too short</title>
  <facts>
    <fact>Tool read file took 65s</fact>
  </facts>
  <narrative>npm install hook timeout, increased to 120s</narrative>
</observation>
```

**压缩率**: 原始 5000 tokens → Observation 100 tokens（50:1）

### 11.5 OpenClaw 原生集成

**一键安装**:
```bash
curl -fsSL https://install.cmem.ai/openclaw.sh | bash
```

**事件桥接**:
```
OpenClaw Gateway
  ├── before_agent_start → 同步 MEMORY.md
  ├── tool_result_persist → 记录 observation
  └── agent_end → 生成摘要
```

**优势**: 无需手动配置，开箱即用

---

## 十二、总结

Claude-Mem 是目前最成熟的 Claude Code 记忆插件，其核心价值在于：

1. **持久化**: 跨会话保存上下文
2. **渐进式披露**: 大幅节省 tokens
3. **自动化**: 无需手动干预
4. **可观测**: Web UI 实时查看记忆流

### 与 Mem0 对比

| 维度 | Claude-Mem | Mem0 |
|------|-----------|------|
| 定位 | Claude Code 专用插件 | 通用记忆层 |
| 检索 | Progressive Disclosure | 向量 + 图 |
| 准确率 | 未基准化 | 26% > OpenAI Memory |
| Token 节省 | ~95% | ~90% |
| 开源协议 | AGPL-3.0 | Apache 2.0 |

### 与 Letta 对比

| 维度 | Claude-Mem | Letta |
|------|-----------|-------|
| 架构 | Claude Code 插件 | Agent 框架 |
| 持久化 | Session 级别 | Agent 级别 |
| 检索 | Progressive Disclosure | 向量搜索 |
| 集成难度 | 低 | 中 |

### 技术特色

1. **Progressive Disclosure**: 先索引后详情，Agent 自主决策
2. **Hook 驱动**: 无侵入自动捕获
3. **混合检索**: FTS5 + ChromaDB
4. **AI 压缩**: Claude Agent SDK 迭代压缩
5. **OpenClaw 集成**: 一键安装，完美集成

### 适用场景

- **Claude-Mem**: Claude Code 用户，需要持久化上下文
- **Mem0**: 通用 Agent 开发者，需要高性能记忆
- **Letta**: 长期运行的 Agent 系统，需要状态化 Agent

对于正在设计 Agent 记忆系统的开发者，Claude-Mem 是必读的参考实现，其 Progressive Disclosure 设计尤其值得借鉴。

---

## 参考链接

- Claude-Mem: https://github.com/thedotmack/claude-mem
- Mem0: https://github.com/mem0ai/mem0
- Letta (原 MemGPT): https://github.com/letta-ai/letta-code
- 官网: https://claude-mem.ai/
- 文档: https://docs.claude-mem.ai/
- OpenClaw 集成: https://docs.claude-mem.ai/openclaw-integration
- Mem0 论文: https://arxiv.org/abs/2504.19413

---

*本文基于 Claude-Mem v10.3.1 源码深度分析*
