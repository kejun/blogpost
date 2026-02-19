# Claude-Mem: AI Agent 记忆系统的参考实现

*2026-02-19*

如果你用过 Claude Code，一定遇到过这个问题：新 session 开始，之前的上下文全丢了。刚修好的 bug、做过的架构决策、踩过的坑——统统归零。

Claude-Mem 就是来解决这个问题的。它是一个持久化记忆插件，能自动捕获 Agent 工作过程中的所有操作，通过 AI 压缩生成语义摘要，并在后续会话中智能注入相关上下文。

本文基于对 Claude-Mem v10.3.1 的深度调研，剖析其架构设计和核心设计理念。

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

## 二、架构：六钩子 + Worker + 数据库

Claude-Mem 的架构设计精巧：

### 2.1 六个生命周期钩子

```
SessionStart  → context-hook.ts    → 启动 worker，注入上下文
UserPromptSubmit → new-hook.ts     → 创建 session，保存 prompt
PostToolUse   → save-hook.ts       → 捕获 tool 执行（最频繁）
Stop          → summary-hook.ts    → 生成 session 摘要
SessionEnd    → cleanup-hook.ts    → 标记 session 完成
```

其中 `PostToolUse` 是核心——每次 Agent 读文件、执行命令、搜索代码，都会被捕获。

### 2.2 Worker Service

独立进程 (Bun + Express)，监听 localhost:37777：
- 接收 hooks 发来的原始数据
- 调用 Claude Agent SDK 进行 AI 压缩
- 存储到 SQLite
- 提供 HTTP API 供检索

### 2.3 数据库层

两层存储：
- **SQLite + FTS5**: 全文搜索，关键词匹配
- **ChromaDB**: 向量存储，语义搜索

混合检索：先 FTS5 粗筛，再 ChromaDB 精排。

---

## 三、核心设计：Progressive Disclosure

这是 Claude-Mem 最有价值的设计理念。

### 3.1 传统 RAG 的问题

```
用户问：之前那个 bug 怎么修的？

传统 RAG:
┌─────────────────────────────────┐
│ 检索 20 条相关记录               │
│ 每条 ~500 tokens                │
│ 总共 10,000 tokens              │
│ 用户看了一条就说：哦对就是这个    │
│ 90% 的 tokens 白费了             │
└─────────────────────────────────┘
```

### 3.2 渐进式披露

**核心原则**: 先显示索引和检索成本，让 Agent 自主决定获取什么。

```
Claude-Mem 方案:
┌─────────────────────────────────┐
│ Step 1: search() 返回索引        │
│ | ID | Time | Type | Title |    │
│ | #123 | 10:30 | 🔴 | Hook timeout |
│ | #124 | 10:35 | 🟡 | Fix npm cache |
│ ~50 tokens per result           │
│                                  │
│ Step 2: Agent 看到 #123 相关     │
│ get_observations([123])         │
│ 获取完整内容 ~500 tokens         │
│                                  │
│ 总消耗: ~550 tokens              │
│ 相关性: 100%                     │
└─────────────────────────────────┘
```

**效果**: 从 10,000 tokens → 550 tokens，节省 95%。

### 3.3 三层工作流

```
Layer 1: search(query) → 索引 + ID (~50-100 tokens/result)
Layer 2: timeline(anchor=ID) → 时间线上下文
Layer 3: get_observations([IDs]) → 完整详情 (~500-1000 tokens/result)
```

这个设计的关键洞察是：**不要一开始就获取完整内容，先看索引，再按需获取。**

---

## 四、Observation 分类系统

Claude-Mem 会对每条记录自动分类：

| 图标 | 类型 | 含义 |
|------|------|------|
| 🎯 | session-request | 用户的原始目标 |
| 🔴 | gotcha | 关键边界情况/陷阱 |
| 🟡 | problem-solution | Bug 修复/解决方案 |
| 🔵 | how-it-works | 技术解释 |
| 🟢 | what-changed | 代码/架构变更 |
| 🟣 | discovery | 学习/洞察 |
| 🟠 | why-it-exists | 设计原理 |
| 🟤 | decision | 架构决策 |
| ⚖️ | trade-off | 有意妥协 |

这个分类系统让 Agent 能快速扫描历史：
```
看到 🔴 gotcha → "这个坑我踩过，值得注意"
看到 🟤 decision → "这是当时的架构决策，可能有参考价值"
看到 🟣 discovery → "这是我学到的，可能有用"
```

---

## 五、Endless Mode: 突破上下文限制

这是 Beta 功能，但设计思路很有启发性。

### 5.1 问题：O(N²) 复杂度

LLM 的 attention 机制是二次复杂度：每个 token 都要和所有其他 token 计算关系。

```
Tool 调用 1: +2k tokens
Tool 调用 2: +3k tokens  
Tool 调用 3: +1k tokens
...
Tool 调用 50: 上下文已 100k+ tokens

每次响应都要重新处理所有历史 → 越来越慢
```

### 5.2 仿生记忆架构

人类怎么处理这个问题？我们有工作记忆和长期记忆。

Claude-Mem 的 Endless Mode 模仿这个设计：

```
Working Memory (上下文窗口):
  → 仅压缩后的 observations (~500 tokens each)
  → 快速、高效

Archive Memory (磁盘文件):
  → 完整 tool outputs
  → 完美召回，可搜索
```

### 5.3 实时压缩

关键创新：每次 tool 调用后，**阻塞等待** worker 生成压缩 observation，然后替换原始 output。

```
原始: Read file → 5000 tokens 内容
压缩: observation → "读取 config.yaml，发现 API key 配置错误"
存储: 5000 tokens 存磁盘，上下文只留 ~100 tokens
```

**效果**: O(N²) → O(N)，可以无限延长会话。

---

## 六、OpenClaw 集成

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

支持将新 observations 推送到 Telegram/Discord/Slack 等渠道，实时监控 Agent 的学习过程。

---

## 七、工程细节

### 7.1 智能安装缓存

早期版本每次 SessionStart 都跑 `npm install`（2-5秒）。v5.0.3 引入版本标记：

```javascript
const currentVersion = getPackageVersion();
const installedVersion = readFileSync('.install-version');

if (currentVersion !== installedVersion) {
  await runNpmInstall();
  writeFileSync('.install-version', currentVersion);
}
```

**效果**: 2-5s → 10ms，99.5% 提升。

### 7.2 僵尸进程防护

v10.2.6 解决了 observer 子进程累积问题：
- 双重清理：finally block + 后台 reap
- 定期扫描孤儿进程并杀死

### 7.3 ChromaDB 连接

v10.3.0 用 `chroma-mcp` MCP 连接替代 WASM embeddings：
- 解决原生二进制问题
- 解决跨平台安装问题
- 优雅的子进程生命周期

---

## 八、对 Agent 系统设计的启示

### 8.1 Context Engineering vs Prompt Engineering

Claude-Mem 体现了 **Context Engineering** 的核心思想：

> Prompt Engineering 是一次性任务，Context Engineering 是持续迭代过程。

Context Engineering 管理：
- 系统指令
- 工具定义
- 外部数据
- 消息历史
- 运行时检索

### 8.2 关键原则

1. **Context is finite**: 把上下文当成有限资源
2. **Make costs visible**: 显示每条记录的 token 成本
3. **Design for autonomy**: 让 Agent 自主决定获取什么
4. **Start simple**: 先做最简单的，按需添加

### 8.3 可复用的模式

| 模式 | 适用场景 |
|------|---------|
| Progressive Disclosure | 大量历史数据检索 |
| 分类标签系统 | 快速扫描定位 |
| 混合检索 (关键词+语义) | 提高检索准确率 |
| 实时压缩 | 长会话场景 |

---

## 九、总结

Claude-Mem 是目前最成熟的 Claude Code 记忆插件，解决了 Agent 记忆的核心问题：

1. **持久化**: 跨会话保存上下文
2. **渐进式披露**: 大幅节省 tokens
3. **自动化**: 无需手动干预
4. **可观测**: Web UI 实时查看记忆流

对于正在设计 Agent 记忆系统的开发者，这是必读的参考实现。

---

## 参考链接

- GitHub: https://github.com/thedotmack/claude-mem
- 官网: https://claude-mem.ai/
- 文档: https://docs.claude-mem.ai/
- OpenClaw 集成: https://docs.claude-mem.ai/openclaw-integration

---

*本文基于 Claude-Mem v10.3.1 源码和文档调研*
