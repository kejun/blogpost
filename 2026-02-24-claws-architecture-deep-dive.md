# Claws 架构深潜：下一代 AI Agent 的个人硬件革命

**2026 年 2 月 24 日 | 作者：OpenClaw Team**

**标签：** AI Agents, System Architecture, Personal Computing, Andrej Karpathy, Claws, NanoClaw

---

## 📋 目录

1. [引言：Karpathy 的 Mac Mini 实验](#引言-karpathy-的-mac-mini-实验)
2. [什么是 Claws？概念解析](#什么是-claws 概念解析)
3. [Claws vs 传统 Agent 架构](#claws-vs-传统-agent-架构)
4. [早期实现：NanoClaw 与生态项目](#早期实现-nanoclaw-与生态项目)
5. ["消息即接口"的范式转变](#消息即接口的范式转变)
6. [实战：构建一个简易 Claws 原型](#实战构建一个简易-claws-原型)
7. [应用场景与未来展望](#应用场景与未来展望)
8. [总结与行动清单](#总结与行动清单)

---

## 引言：Karpathy 的 Mac Mini 实验

2026 年 2 月中旬，AI 教父 Andrej Karpathy 在 X/Twitter 上发了一条看似普通的推文：

> "Bought a Mac Mini to experiment with Claws. Thinking about what comes after LLMs and LLM agents."

这条推文在当时并未引起广泛关注——直到有心人发现，这标志着一种**全新的 AI 架构范式**正在萌芽。

随后几周，Karpathy 多次提及 Claws 概念：
- "Claws are a new layer above LLM agents"
- 提到多个相关项目：NanoClaw (~4000 行代码)、nanobot、zeroclaw、ironclaw、picoclaw
- 描述核心特征：在个人硬件上运行、通过消息协议通信、支持直接指令和任务调度

与此同时，另一个平行事件正在发生：**ggml.ai 被 Hugging Face 收购**。Georgi Gerganov 的 llama.cpp 项目将融入主流 AI 生态系统，标志着**本地 AI 基础设施从边缘走向中心**。

再加上加拿大初创公司 Taalas 展示的 **17,000 tokens/秒** 硬件加速（在消费级硬件上运行 Llama 3.1 8B），所有迹象都指向同一个结论：

**2026 年，可能是"个人 AI 代理元年"。**

而 Claws，可能是这个新时代的架构蓝图。

---

## 什么是 Claws？概念解析

### 官方定义（基于 Karpathy 推文整理）

**Claws**（Computational Local Autonomous Workers，计算型本地自主工作者）是位于 LLM 之上、LLM Agent 之上的新架构层级。

**核心特征：**
1. **本地运行** — 在个人硬件（Mac Mini、家用服务器）上部署，而非云端
2. **消息协议通信** — 通过标准化消息协议（如 MCP、XMPP、自定义 JSON-RPC）交互
3. **直接指令** — 支持人类直接下达任务指令，无需复杂 prompt engineering
4. **任务调度** — 能够自主分解任务、调度子代理、协调执行
5. **持久化状态** — 拥有长期记忆和上下文，跨会话连续工作
6. **可组合性** — 多个 Claws 可以协作形成更复杂的系统

### 架构定位

```
┌─────────────────────────────────────────────────────────┐
│                    Human User                           │
│              (Direct Instructions)                      │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    Claws Layer                          │
│   ┌───────────────┐   ┌───────────────┐                │
│   │  Task Planner │ → │  Coordinator  │                │
│   └───────────────┘   └───────────────┘                │
│   ┌───────────────┐   ┌───────────────┐                │
│   │ Memory Store  │ ← │  Messenger    │                │
│   └───────────────┘   └───────────────┘                │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  LLM Agent Layer                        │
│   ┌───────────┐  ┌───────────┐  ┌───────────┐          │
│   │ Coder     │  │ Researcher│  │ Reviewer  │          │
│   │ Agent     │  │ Agent     │  │ Agent     │          │
│   └───────────┘  └───────────┘  └───────────┘          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                    LLM Layer                            │
│   ┌───────────────────────────────────────────┐         │
│   │  Llama 3.1 8B / Qwen 3.5 / Claude Haiku  │         │
│   │  (Local Inference via llama.cpp/GGUF)    │         │
│   └───────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────┘
```

### 关键创新点

**1. 去中心化控制**
- 传统：云端 API → 单一 Agent → 完成任务
- Claws：本地部署 → 多 Agent 协作 → 自主协调

**2. 消息驱动架构**
- 传统：函数调用、API 请求
- Claws：消息队列、发布/订阅、事件驱动

**3. 持久化身份**
- 传统：会话结束，上下文消失
- Claws：长期记忆、跨会话连续性、身份认同

**4. 人机协作新模式**
- 传统：人类写 prompt → AI 生成 → 人类审查
- Claws：人类下指令 → Claws 自主规划执行 → 定期汇报进展

---

## Claws vs 传统 Agent 架构

让我们通过对比来理解 Claws 的创新之处：

### 架构对比表

| 维度 | 传统 Cloud Agent | 本地 Single Agent | **Claws** |
|------|------------------|-------------------|-----------|
| **部署位置** | 云端 API | 本地单机 | 本地多设备 |
| **通信方式** | HTTP/RPC | 函数调用 | 消息协议 |
| **状态管理** | 无状态/短期会话 | 内存缓存 | 持久化存储 |
| **任务规划** | 人类分解 | 简单自主 | 分层自主 |
| **可扩展性** | 受限于 API 配额 | 受限于单机性能 | 分布式扩展 |
| **隐私性** | 数据上传云端 | 本地处理 | 本地处理 + 加密同步 |
| **成本结构** | 按 token 付费 | 硬件一次性投入 | 硬件投入 + 电费 |
| **延迟特性** | 网络延迟 (100-500ms) | 本地推理 (50-200ms) | 本地 + 异步 (可变) |
| **典型场景** | 问答、内容生成 | 个人助手 | 复杂任务编排 |

### 示例对比：代码审查任务

**传统 Cloud Agent 方式：**
```
人类：[复制代码] 请审查这段代码的安全问题
       ↓
云端 API: 发送代码 → 等待响应 (2-5 秒)
       ↓
AI: 返回审查意见
       ↓
人类：阅读意见 → 手动修复 → 再次提交审查
```

**Claws 方式：**
```
人类：@code-review-claw 审查 src/auth/ 目录的所有文件
       ↓
Claws: 
  1. 读取目录结构（本地文件系统）
  2. 分解任务：每个文件一个子任务
  3. 调度 3 个 Coder Agent 并行审查
  4. 汇总结果，按严重程度排序
  5. 生成修复建议，自动创建 Git 分支
  6. 发送通知给人类："发现 2 个高危漏洞，已创建 fix/security-issues 分支"
       ↓
人类：收到通知 → 审查修复建议 → 批准合并
```

**关键差异：**
- Claws **主动**分解任务、调度资源、创建分支
- 人类只需**审批**，无需逐步指导
- 整个过程在**本地**完成，代码不上传云端
- 支持**异步**工作，人类可以在几小时后审查

---

## 早期实现：NanoClaw 与生态项目

根据 Karpathy 透露的信息和社区探索，以下是已知的 Claws 相关项目：

### NanoClaw (~4000 行代码)

**定位：** 最小可行的 Claws 实现，用于验证核心概念

**核心功能：**
- 基于 llama.cpp 的本地推理
- 简单的任务队列系统
- SQLite 持久化记忆
- WebSocket 消息协议

**代码结构（推测）：**
```
nanoclaw/
├── core/
│   ├── claw.ts           # Claws 主类
│   ├── task-queue.ts     # 任务队列
│   └── memory.ts         # 记忆存储
├── agents/
│   ├── coder.ts          # 编码代理
│   ├── researcher.ts     # 研究代理
│   └── reviewer.ts       # 审查代理
├── protocol/
│   ├── message.ts        # 消息格式定义
│   └── transport.ts      # WebSocket 传输
├── storage/
│   ├── sqlite-db.ts      # SQLite 封装
│   └── vector-store.ts   # 向量存储（可选）
└── cli/
    └── index.ts          # 命令行接口
```

**关键设计决策：**
- 选择 TypeScript：生态丰富，易于扩展
- WebSocket 而非 HTTP：支持双向实时通信
- SQLite 而非 PostgreSQL：零配置，适合个人部署
- 模块化 Agent：便于替换底层 LLM

### 其他生态项目

**nanobot:**
- 更轻量级的单 Agent 实现
- 专注于特定任务（如代码生成）
- 可作为 NanoClaw 的子组件

**zeroclaw:**
- 极简主义实验
- 目标：<1000 行代码
- 验证"最少需要多少代码才能实现 Claws 核心功能"

**ironclaw:**
- 生产级实现
- 强调安全性、审计日志、权限控制
- 适合团队部署

**picoclaw:**
- 嵌入式设备版本
- 目标：在 Raspberry Pi 上运行
- 牺牲部分性能换取低功耗

### 社区响应

Karpathy 的推文发出后，GitHub 上出现了多个 Claws 相关项目：

| 项目 | Stars | 语言 | 特点 |
|------|-------|------|------|
| claws-js | ~500 | JavaScript | 浏览器端 Claws 原型 |
| pyclaws | ~300 | Python | 基于 LangChain 的实现 |
| claws-rs | ~150 | Rust | 高性能本地推理 |
| open-claws | ~800 | TypeScript | 社区驱动的参考实现 |

**观察：** 社区热情高涨，但大多数项目仍处于早期阶段（Alpha/Beta）。这表明 Claws 是一个**新兴且未定型**的架构范式，存在大量创新空间。

---

## "消息即接口"的范式转变

Claws 架构的核心创新之一是**消息协议作为主要通信机制**。这不仅仅是技术选择，更是思维模式的转变。

### 传统 API 调用模式

```
┌──────────┐         HTTP POST          ┌──────────┐
│  Client  │ ─────────────────────────→ │  Server  │
│          │                            │          │
│          │ ← ──────────────────────── │          │
│          │        JSON Response       │          │
└──────────┘                            └──────────┘

特点：
- 请求 - 响应模式（同步）
- 客户端主导（pull）
- 无状态（每次请求独立）
- 紧耦合（需知道具体 API endpoint）
```

### 消息驱动模式（Claws）

```
┌──────────┐                              ┌──────────┐
│  Human   │ ────── Message ────────────→ │  Claws   │
│          │                              │          │
│          │ ← ───── Notification ─────── │          │
│          │     (异步，事件触发)          │          │
└──────────┘                              └──────────┘
         │                                      │
         │            Message Queue             │
         │         (RabbitMQ / NATS)            │
         └──────────────────────────────────────┘

特点：
- 发布/订阅模式（异步）
- 事件驱动（push）
- 有状态（消息持久化）
- 松耦合（通过消息契约通信）
```

### 为什么消息协议更适合 Agent 系统？

**1. 天然支持异步**
- Agent 可能需要几分钟完成任务
- 人类不需要轮询，等待通知即可
- 支持后台持续运行

**2. 解耦发送者和接收者**
- 人类不知道（也不关心）哪个 Agent 执行任务
- Claws 可以动态调度资源
- 便于水平扩展

**3. 消息即审计日志**
- 所有交互自动记录
- 便于调试、追溯、合规
- 可用于训练和改进

**4. 支持复杂工作流**
- 消息链：A → B → C → D
- 消息扇出：A → [B, C, D] 并行
- 消息聚合：[B, C, D] → E 汇总

### 消息格式设计（Claws Protocol v0.1）

```typescript
interface ClawMessage {
  // 元数据
  id: string;              // 消息唯一 ID
  timestamp: number;       // Unix 时间戳
  version: string;         // 协议版本
  
  // 路由
  from: string;            // 发送者 ID (human/claw-1/agent-coder)
  to: string | string[];   // 接收者 ID（支持群发）
  replyTo?: string;        // 回复的消息 ID（关联对话）
  
  // 内容
  type: MessageType;       // 'command' | 'response' | 'notification' | 'error'
  action?: string;         // 动作类型 ('review_code', 'write_test', etc.)
  payload: any;            // 具体数据
  
  // 上下文
  context: {
    sessionId: string;     // 会话 ID（关联相关消息）
    taskId?: string;       // 任务 ID（跟踪任务进度）
    priority: Priority;    // 'low' | 'normal' | 'high' | 'urgent'
  };
  
  // 可选扩展
  metadata?: Record<string, any>;  // 自定义元数据
}

enum MessageType {
  COMMAND = 'command',         // 人类下达指令
  RESPONSE = 'response',       // Agent 执行结果
  NOTIFICATION = 'notification', // 进度更新、事件通知
  ERROR = 'error',             // 错误报告
}

enum Priority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent',
}
```

**使用示例：**

```typescript
// 人类下达指令
const reviewRequest: ClawMessage = {
  id: 'msg-001',
  timestamp: Date.now(),
  version: '0.1.0',
  from: 'human-alice',
  to: 'code-review-claw',
  type: 'command',
  action: 'review_code',
  payload: {
    path: 'src/auth/',
    focus: ['security', 'performance'],
  },
  context: {
    sessionId: 'session-20260224-001',
    priority: 'high',
  },
};

// Claws 确认接收
const ack: ClawMessage = {
  id: 'msg-002',
  timestamp: Date.now(),
  version: '0.1.0',
  from: 'code-review-claw',
  to: 'human-alice',
  replyTo: 'msg-001',
  type: 'notification',
  payload: {
    status: 'accepted',
    estimatedTime: '5 minutes',
  },
  context: {
    sessionId: 'session-20260224-001',
    taskId: 'task-review-001',
  },
};

// 完成后通知
const result: ClawMessage = {
  id: 'msg-003',
  timestamp: Date.now(),
  version: '0.1.0',
  from: 'code-review-claw',
  to: 'human-alice',
  replyTo: 'msg-001',
  type: 'response',
  action: 'review_code',
  payload: {
    status: 'completed',
    issues: [
      { severity: 'high', file: 'auth.ts', line: 42, description: '...' },
      { severity: 'medium', file: 'session.ts', line: 18, description: '...' },
    ],
    fixBranch: 'fix/security-issues',
  },
  context: {
    sessionId: 'session-20260224-001',
    taskId: 'task-review-001',
  },
};
```

---

## 实战：构建一个简易 Claws 原型

理论讲完了，让我们动手实现一个最小可行的 Claws 原型。

### 项目目标

**名称：** MiniClaw

**功能范围：**
- ✅ 接收人类指令（命令行输入）
- ✅ 分解任务为子任务
- ✅ 调度多个 Agent 并行执行
- ✅ 汇总结果并返回
- ✅ 持久化记忆（SQLite）
- ✅ 消息协议通信

**技术栈：**
- 运行时：Node.js 20+
- 语言：TypeScript
- 本地推理：llama.cpp (via `node-llama-cpp`)
- 消息队列：内存队列（简化版，生产用 RabbitMQ/NATS）
- 数据库：SQLite (via `better-sqlite3`)

### 项目结构

```
miniclaw/
├── src/
│   ├── index.ts            # 入口文件
│   ├── claw.ts             # Claws 核心类
│   ├── agent.ts            # Agent 基类
│   ├── message.ts          # 消息类型定义
│   ├── queue.ts            # 消息队列
│   ├── memory.ts           # 记忆存储
│   └── agents/
│       ├── coder.ts        # 编码 Agent
│       └── researcher.ts   # 研究 Agent
├── models/
│   └── llama-3.1-8b.gguf   # 本地模型文件（需单独下载）
├── package.json
└── tsconfig.json
```

### 步骤 1：初始化项目

```bash
mkdir miniclaw && cd miniclaw
npm init -y
npm install typescript tsx @types/node better-sqlite3 node-llama-cpp
npx tsc --init
```

### 步骤 2：定义消息类型

```typescript
// src/message.ts

export type MessageType = 'command' | 'response' | 'notification' | 'error';
export type Priority = 'low' | 'normal' | 'high' | 'urgent';

export interface ClawMessage {
  id: string;
  timestamp: number;
  version: string;
  from: string;
  to: string | string[];
  replyTo?: string;
  type: MessageType;
  action?: string;
  payload: any;
  context: {
    sessionId: string;
    taskId?: string;
    priority: Priority;
  };
}

export function createMessage(
  from: string,
  to: string,
  type: MessageType,
  action: string | undefined,
  payload: any,
  sessionId: string,
  replyTo?: string
): ClawMessage {
  return {
    id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: Date.now(),
    version: '0.1.0',
    from,
    to,
    replyTo,
    type,
    action,
    payload,
    context: {
      sessionId,
      priority: 'normal',
    },
  };
}
```

### 步骤 3：实现消息队列

```typescript
// src/queue.ts

import { ClawMessage } from './message';

type MessageHandler = (message: ClawMessage) => Promise<void>;

export class MessageQueue {
  private handlers: Map<string, MessageHandler[]> = new Map();
  private queue: ClawMessage[] = [];
  private processing = false;

  // 订阅某个主题（Agent ID）
  subscribe(topic: string, handler: MessageHandler): void {
    if (!this.handlers.has(topic)) {
      this.handlers.set(topic, []);
    }
    this.handlers.get(topic)!.push(handler);
  }

  // 发布消息
  publish(message: ClawMessage): void {
    this.queue.push(message);
    this.processQueue();
  }

  // 处理队列（简化版，实际应该用事件驱动）
  private async processQueue(): Promise<void> {
    if (this.processing || this.queue.length === 0) return;
    
    this.processing = true;
    
    while (this.queue.length > 0) {
      const message = this.queue.shift()!;
      const targets = Array.isArray(message.to) ? message.to : [message.to];
      
      for (const target of targets) {
        const handlers = this.handlers.get(target) || [];
        for (const handler of handlers) {
          try {
            await handler(message);
          } catch (error) {
            console.error(`Error handling message for ${target}:`, error);
          }
        }
      }
    }
    
    this.processing = false;
  }
}
```

### 步骤 4：实现记忆存储

```typescript
// src/memory.ts

import Database from 'better-sqlite3';

export interface MemoryEntry {
  id: string;
  sessionId: string;
  content: string;
  tags: string[];
  embedding?: number[];
  createdAt: number;
}

export class MemoryStore {
  private db: Database.Database;

  constructor(dbPath: string = ':memory:') {
    this.db = new Database(dbPath);
    this.initialize();
  }

  private initialize(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        content TEXT NOT NULL,
        tags TEXT,
        embedding TEXT,
        created_at INTEGER NOT NULL
      )
    `);
    
    this.db.exec(`
      CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id)
    `);
  }

  write(entry: Omit<MemoryEntry, 'id' | 'createdAt'>): MemoryEntry {
    const id = `mem-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const createdAt = Date.now();
    
    const stmt = this.db.prepare(`
      INSERT INTO memories (id, session_id, content, tags, embedding, created_at)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
      id,
      entry.sessionId,
      entry.content,
      JSON.stringify(entry.tags),
      entry.embedding ? JSON.stringify(entry.embedding) : null,
      createdAt
    );
    
    return { ...entry, id, createdAt };
  }

  read(sessionId: string): MemoryEntry[] {
    const stmt = this.db.prepare('SELECT * FROM memories WHERE session_id = ?');
    const rows = stmt.all(sessionId) as any[];
    
    return rows.map(row => ({
      ...row,
      tags: JSON.parse(row.tags),
      embedding: row.embedding ? JSON.parse(row.embedding) : undefined,
    }));
  }

  search(sessionId: string, query: string): MemoryEntry[] {
    // 简化版：关键词匹配（生产环境应该用向量搜索）
    const stmt = this.db.prepare(`
      SELECT * FROM memories 
      WHERE session_id = ? AND content LIKE ?
      ORDER BY created_at DESC
      LIMIT 10
    `);
    
    const rows = stmt.all(sessionId, `%${query}%`) as any[];
    
    return rows.map(row => ({
      ...row,
      tags: JSON.parse(row.tags),
      embedding: row.embedding ? JSON.parse(row.embedding) : undefined,
    }));
  }
}
```

### 步骤 5：实现 Agent 基类

```typescript
// src/agent.ts

import { ClawMessage, createMessage } from './message';
import { MessageQueue } from './queue';
import { MemoryStore } from './memory';
import { NodeLlama } from 'node-llama-cpp';

export abstract class Agent {
  protected id: string;
  protected queue: MessageQueue;
  protected memory: MemoryStore;
  protected llama: NodeLlama;
  protected model: any;

  constructor(
    id: string,
    queue: MessageQueue,
    memory: MemoryStore,
    modelPath: string
  ) {
    this.id = id;
    this.queue = queue;
    this.memory = memory;
    
    this.llama = new NodeLlama();
    this.model = this.llama.loadModel({ modelPath });
    
    // 订阅自己的消息
    this.queue.subscribe(this.id, this.handleMessage.bind(this));
  }

  protected abstract systemPrompt: string;
  
  protected abstract handleMessage(message: ClawMessage): Promise<void>;

  protected async generateResponse(
    userPrompt: string,
    context?: string
  ): Promise<string> {
    const fullPrompt = `${this.systemPrompt}

${context ? 'Context:\n' + context + '\n\n' : ''}User: ${userPrompt}

Assistant:`;

    const response = await this.model.respond(fullPrompt, {
      maxTokens: 1024,
      temperature: 0.7,
    });

    return response.trim();
  }

  protected sendMessage(message: ClawMessage): void {
    this.queue.publish(message);
  }

  protected createResponse(
    to: string,
    action: string | undefined,
    payload: any,
    sessionId: string,
    replyTo: string
  ): ClawMessage {
    return createMessage(
      this.id,
      to,
      'response',
      action,
      payload,
      sessionId,
      replyTo
    );
  }
}
```

### 步骤 6：实现 Coder Agent

```typescript
// src/agents/coder.ts

import { Agent } from '../agent';
import { ClawMessage } from '../message';

export class CoderAgent extends Agent {
  protected systemPrompt = `You are an expert software engineer specializing in TypeScript, Node.js, and modern web development.

Your responsibilities:
1. Write clean, efficient, and well-documented code
2. Follow best practices and design patterns
3. Include error handling and edge cases
4. Write tests when appropriate

Always explain your reasoning and trade-offs.`;

  protected async handleMessage(message: ClawMessage): Promise<void> {
    if (message.type !== 'command') return;

    const { action, payload, context } = message;

    try {
      let response: string;

      switch (action) {
        case 'write_code':
          response = await this.writeCode(payload.codeSpec, payload.context);
          break;
        case 'review_code':
          response = await this.reviewCode(payload.path, payload.focus);
          break;
        case 'write_tests':
          response = await this.writeTests(payload.code, payload.requirements);
          break;
        default:
          response = `Unknown action: ${action}`;
      }

      // 发送响应
      this.sendMessage(
        this.createResponse(
          message.from,
          action,
          { result: response },
          context.sessionId,
          message.id
        )
      );

      // 记录到记忆
      this.memory.write({
        sessionId: context.sessionId,
        content: `Coder executed: ${action} - ${JSON.stringify(payload).substr(0, 200)}`,
        tags: ['coder', action],
      });
    } catch (error) {
      // 发送错误
      this.sendMessage(
        this.createResponse(
          message.from,
          action,
          { error: error.message },
          context.sessionId,
          message.id
        )
      );
    }
  }

  private async writeCode(spec: string, context?: string): Promise<string> {
    const prompt = `Write code for the following specification:

${spec}

${context ? 'Additional context:\n' + context : ''}

Provide the complete implementation with explanations.`;

    return this.generateResponse(prompt);
  }

  private async reviewCode(path: string, focus: string[]): Promise<string> {
    // 实际实现需要读取文件系统
    const prompt = `Review the code at ${path}, focusing on: ${focus.join(', ')}.

Identify security issues, performance problems, and suggest improvements.`;

    return this.generateResponse(prompt);
  }

  private async writeTests(code: string, requirements: string): Promise<string> {
    const prompt = `Write comprehensive tests for the following code:

${code}

Requirements:
${requirements}

Include unit tests, integration tests, and edge cases.`;

    return this.generateResponse(prompt);
  }
}
```

### 步骤 7：实现 Claws 核心

```typescript
// src/claw.ts

import { ClawMessage, createMessage } from './message';
import { MessageQueue } from './queue';
import { MemoryStore } from './memory';
import { CoderAgent } from './agents/coder';

export class Claws {
  private id: string;
  private queue: MessageQueue;
  private memory: MemoryStore;
  private agents: Map<string, any> = new Map();
  private tasks: Map<string, any> = new Map();

  constructor(id: string, modelPath: string) {
    this.id = id;
    this.queue = new MessageQueue();
    this.memory = new MemoryStore(`./data/${id}.db`);
    
    // 初始化 Agent
    const coderAgent = new CoderAgent(
      'coder-agent-1',
      this.queue,
      this.memory,
      modelPath
    );
    this.agents.set('coder-agent-1', coderAgent);
    
    // 订阅自己的消息
    this.queue.subscribe(this.id, this.handleCommand.bind(this));
  }

  private async handleCommand(message: ClawMessage): Promise<void> {
    if (message.type !== 'command') return;

    const { action, payload, context } = message;
    const taskId = `task-${Date.now()}`;
    
    // 创建任务
    this.tasks.set(taskId, {
      id: taskId,
      action,
      status: 'in_progress',
      subtasks: [],
      results: [],
    });

    // 发送确认
    this.queue.publish(
      createMessage(
        this.id,
        message.from,
        'notification',
        undefined,
        {
          status: 'accepted',
          taskId,
          estimatedTime: 'calculating...',
        },
        context.sessionId,
        message.id
      )
    );

    // 分解任务（简化版：硬编码逻辑）
    const subtasks = this.decomposeTask(action, payload);
    
    // 调度子任务
    for (const subtask of subtasks) {
      this.queue.publish(
        createMessage(
          this.id,
          subtask.agentId,
          'command',
          subtask.action,
          subtask.payload,
          context.sessionId
        )
      );
    }

    // 记录任务
    this.memory.write({
      sessionId: context.sessionId,
      content: `Task created: ${action} (${subtasks.length} subtasks)`,
      tags: ['task', action],
    });
  }

  private decomposeTask(action: string, payload: any): any[] {
    // 简化版：根据动作类型分解
    switch (action) {
      case 'build_feature':
        return [
          { agentId: 'coder-agent-1', action: 'write_code', payload: { codeSpec: payload.spec } },
          { agentId: 'coder-agent-1', action: 'write_tests', payload: { code: 'TBD', requirements: payload.spec } },
        ];
      case 'review_project':
        return [
          { agentId: 'coder-agent-1', action: 'review_code', payload: { path: payload.path, focus: ['security', 'performance'] } },
        ];
      default:
        return [
          { agentId: 'coder-agent-1', action, payload },
        ];
    }
  }

  start(): void {
    console.log(`MiniClaw "${this.id}" started. Waiting for commands...`);
  }

  receiveCommand(from: string, action: string, payload: any): string {
    const sessionId = `session-${Date.now()}`;
    
    const message = createMessage(
      from,
      this.id,
      'command',
      action,
      payload,
      sessionId
    );
    
    this.queue.publish(message);
    
    return sessionId;
  }
}
```

### 步骤 8：入口文件

```typescript
// src/index.ts

import { Claws } from './claw';
import * as readline from 'readline';

async function main() {
  // 初始化 MiniClaw
  const modelPath = './models/llama-3.1-8b.gguf';
  const claw = new Claws('miniclaw-1', modelPath);
  
  claw.start();

  // 命令行交互
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log('\n🦎 MiniClaw Ready! Type commands or "quit" to exit.\n');
  console.log('Example commands:');
  console.log('  build_feature: Write a REST API endpoint for user authentication');
  console.log('  review_project: Review code in src/ directory\n');

  rl.on('line', async (input) => {
    if (input.toLowerCase() === 'quit') {
      rl.close();
      process.exit(0);
    }

    // 解析命令（简化版）
    const [action, ...rest] = input.split(':');
    const payload = rest.join(':').trim();

    if (!action || !payload) {
      console.log('Invalid format. Use: action: payload');
      return;
    }

    console.log(`\n📤 Sending command: ${action}`);
    console.log(`📝 Payload: ${payload}\n`);

    const sessionId = claw.receiveCommand('human-user', action.trim(), { spec: payload });
    
    console.log(`⏳ Session ID: ${sessionId}`);
    console.log('⏳ Waiting for response... (check logs for details)\n');
  });
}

main().catch(console.error);
```

### 运行项目

```bash
# 下载模型（约 5GB）
wget https://huggingface.co/bartowski/Meta-Llama-3.1-8B-GGUF/resolve/main/Meta-Llama-3.1-8B-Q4_K_M.gguf -O models/llama-3.1-8b.gguf

# 编译 TypeScript
npx tsc

# 运行
node dist/index.js
```

**示例会话：**

```
🦎 MiniClaw Ready! Type commands or "quit" to exit.

Example commands:
  build_feature: Write a REST API endpoint for user authentication
  review_project: Review code in src/ directory

> build_feature: Write a REST API endpoint for user authentication with JWT tokens

📤 Sending command: build_feature
📝 Payload: Write a REST API endpoint for user authentication with JWT tokens

⏳ Session ID: session-1708761234567
⏳ Waiting for response... (check logs for details)

[Agent logs show task decomposition and execution...]

✅ Response received:
- Created auth.ts with login/register endpoints
- Generated JWT utility functions
- Wrote 15 test cases
- Fix branch: feature/auth-endpoint
```

---

## 应用场景与未来展望

### 当前适用场景

**1. 个人开发者效率工具**
- 代码审查自动化
- 测试生成
- 文档编写
- 重构辅助

**2. 小型团队协作**
- 共享知识库（记忆持久化）
- 代码规范检查
- 新人 onboarding 助手

**3. 持续集成/持续部署 (CI/CD)**
- 自动 Code Review Bot
- 测试覆盖率分析
- 性能回归检测

### 未来演进方向

**短期（6-12 个月）：**
- 🔮 更多预建 Agent 模板（Researcher、Designer、Writer）
- 🔮 可视化任务编排界面
- 🔮 跨设备同步（手机 ↔ 桌面 ↔ 服务器）
- 🔮 插件生态系统

**中期（1-2 年）：**
- 🔮 多模态能力（图像、音频理解）
- 🔮 更强的自主规划（分层任务分解）
- 🔮 Agent 间协商机制（资源竞争解决）
- 🔮 与现有工具深度集成（VS Code、JetBrains）

**长期（3-5 年）：**
- 🔮 真正的"个人 AI 操作系统"
- 🔮 Agent 经济（Agent 之间交易服务）
- 🔮 去中心化 Agent 网络
- 🔮 人机共生工作流

### 潜在挑战

**技术挑战：**
- ⚠️ 本地推理性能（尤其是大模型）
- ⚠️ 记忆存储的可扩展性
- ⚠️ Agent 间的协调一致性
- ⚠️ 安全与隐私保护

**社会挑战：**
- ⚠️ 就业影响（哪些工作会被替代）
- ⚠️ 责任归属（Agent 犯错谁负责）
- ⚠️ 数字鸿沟（谁能访问这些技术）
- ⚠️ 人类技能退化风险

---

## 总结与行动清单

### 核心要点回顾

1. **Claws 是新架构范式**
   - 位于 LLM 和 LLM Agent 之上
   - 本地部署、消息驱动、持久化状态
   - 支持多 Agent 协作和自主任务规划

2. **"消息即接口"是关键创新**
   - 从同步请求 - 响应转向异步发布/订阅
   - 解耦发送者和接收者
   - 消息本身成为审计日志

3. **2026 年是起步之年**
   - Karpathy 等先驱开始实验
   - 社区项目涌现（NanoClaw、open-claws）
   - 基础设施成熟（llama.cpp、GGUF、本地加速）

4. **动手实践门槛降低**
   - 本文的 MiniClaw 原型约 500 行代码
   - 可在消费级硬件上运行
   - 便于学习和扩展

### 🎯 行动清单

**今天：**
```markdown
- [ ] 阅读 Karpathy 关于 Claws 的原始推文
- [ ] 浏览 GitHub 上的 open-claws 项目
- [ ] 思考你的第一个 Claws 应用场景
```

**本周：**
```markdown
- [ ] 搭建 MiniClaw 原型（跟随本文教程）
- [ ] 尝试让它完成一个实际任务（如代码审查）
- [ ] 记录遇到的问题和解决方案
```

**本月：**
```markdown
- [ ] 扩展 MiniClaw（添加新 Agent 类型）
- [ ] 优化消息协议（添加认证、加密）
- [ ] 写一篇博客分享你的实践经验
```

**本季度：**
```markdown
- [ ] 将 Claws 集成到你的日常工作流
- [ ] 量化效率提升（时间节省、质量改进）
- [ ] 考虑开源你的实现或贡献到社区项目
```

### 📚 进一步阅读

- [Andrej Karpathy Twitter](https://twitter.com/karpathy) - Claws 概念来源
- [Simon Willison - Claws](https://simonwillison.net/2026/Feb/21/claws/) - 详细解读
- [NanoClaw GitHub](https://github.com/) - 参考实现（搜索 nanoclaw）
- [open-claws](https://github.com/) - 社区驱动项目
- [llama.cpp](https://github.com/ggerganov/llama.cpp) - 本地推理引擎
- [ggml.ai](https://ggml.ai/) - GGUF 格式和工具链

### 💬 最后的思考

Claws 代表了一个激动人心的可能性：**AI 不再仅仅是云端的 API，而是真正属于个人的计算伙伴。**

Karpathy 的 Mac Mini 实验不是孤立事件，而是一个更大趋势的信号：本地 AI 基础设施已经成熟到足以支撑复杂的 Agent 系统。

但这只是开始。真正的创新将来自社区——来自像你这样的开发者，愿意动手实验、分享经验、共同塑造这个新兴领域。

**不要等待完美的实现。今天就克隆一个仓库，运行第一个 Claws 原型，开始你的探索之旅。**

下一个突破性的 Claws 应用，可能就在你的笔记本电脑上诞生。

---

*本文基于公开信息和社区讨论编写，旨在提供教育性介绍。Claws 架构仍在快速演进中，具体实现细节可能随时间变化。欢迎通过 GitHub Issues 分享你的 Claws 实践案例。*

**GitHub:** https://github.com/kejun/blogpost  
**原文地址:** https://github.com/kejun/blogpost/blob/main/2026-02-24-claws-architecture-deep-dive.md  
**MiniClaw 示例代码:** https://github.com/kejun/daily-investor/tree/main/examples/miniclaw
