# Flue 技术调研文档

> **The Agent Harness Framework** — 如果知道怎么用 Claude Code，就知道怎么用 Flue 构建 Agent。

| 维度 | 信息 |
|------|------|
| **仓库** | https://github.com/withastro/flue |
| **组织** | Astro（withastro） |
| **许可证** | MIT |
| **语言** | TypeScript |
| **包管理器** | pnpm（workspace） |
| **状态** | Experimental — APIs may change |
| **核心依赖** | `@mariozechner/pi-agent-core`（Agent Harness）、`@mariozechner/pi-ai`（AI provider abstractions）、Hono、esbuild、valibot、just-bash |

---

## 一、项目概述与定位

### 1.1 什么是 Flue？

Flue 是一个 **TypeScript Agent 框架**，核心理念是：**Agent = 目录**。一个包含 `agents/`、`roles/`、`.agents/skills/`、`AGENTS.md` 的目录，经过编译即可部署为自包含的服务器工件。

与传统的 AI SDK（如 Vercel AI SDK、LangChain）不同，Flue 不是另一个拼凑 LLM API 的工具库，而是一个 **运行时无关（runtime-agnostic）的框架**——类似于 Astro/Next.js 之于 Web，Flue 之于 Agent。

### 1.2 核心设计哲学

1. **100% headless，无需人类操作员**——不像 Claude Code/Codex 需要人在 TUI 前操作，Flue 的 Agent 完全自主运行
2. **无 TUI/无 GUI**——纯 TypeScript，面向程序化调用
3. **目录即 Agent**——Agent 的逻辑大部分活在 Markdown 里（skills、context、AGENTS.md），代码很少
4. **Write once, deploy anywhere**——同一套代码可部署到 Node.js、Cloudflare Workers、GitHub Actions、GitLab CI 等

### 1.3 与 Claude Code 的关系与区别

| 特性 | Claude Code | Flue |
|------|-------------|------|
| 交互方式 | TUI + 人类操作员 | Headless API |
| 工具集 | 内置（read/write/edit/bash/grep/glob） | 相同工具集（read/write/edit/bash/grep/glob/task） |
| 上下文发现 | 自动发现 AGENTS.md + .claude/ | 运行时自动发现 AGENTS.md + .agents/skills/ |
| 部署 | 无法部署 | 编译为可部署服务器 |
| 会话持久化 | 本地文件 | 平台相关（Node: 内存/自定义 DB；Cloudflare: Durable Object SQLite） |
| 技能系统 | .claude/commands/、.claude/settings | .agents/skills/（SKILL.md）+ roles/ |
| 多模型 | 单一模型 | 每个 Agent/Session/Call 级别可独立指定模型 |

**本质上，Flue 把 Claude Code 的 Agent Harness（pi-agent-core）抽离为可编程的基础设施。**

---

## 二、整体架构

### 2.1 Monorepo 结构

```
flue/
├── packages/
│   ├── sdk/              # @flue/sdk — 核心 SDK
│   │   ├── src/
│   │   │   ├── agent.ts          # Agent Harness 封装 + 内置工具（read/write/edit/bash/grep/glob/task）
│   │   │   ├── agent-client.ts   # Agent HTTP Client（SSE 流式消费）
│   │   │   ├── build.ts          # 构建系统（esbuild + Plugin 模式）
│   │   │   ├── build-plugin-node.ts       # Node.js 构建插件
│   │   │   ├── build-plugin-cloudflare.ts # Cloudflare 构建插件
│   │   │   ├── client.ts         # FlueClient — HTTP 客户端接口
│   │   │   ├── session.ts        # Session 核心实现（997行）
│   │   │   ├── session-history.ts# 会话历史管理（消息树/分支）
│   │   │   ├── compaction.ts     # 上下文压缩（自动摘要）
│   │   │   ├── context.ts        # 上下文发现（AGENTS.md、skills 解析）
│   │   │   ├── roles.ts          # 角色解析与模型选择
│   │   │   ├── sandbox.ts        # 沙箱抽象
│   │   │   ├── mcp.ts            # MCP 协议集成
│   │   │   ├── dev.ts            # 开发服务器（watch-mode + hot-reload）
│   │   │   ├── command-helpers.ts# 命令辅助函数
│   │   │   ├── env-utils.ts      # 环境工具（SessionEnv 作用域）
│   │   │   ├── result.ts         # 结果提取（Valibot schema → LLM 结构化输出）
│   │   │   ├── types.ts          # 全量类型定义（484行）
│   │   │   ├── cloudflare/       # Cloudflare 平台适配层
│   │   │   │   ├── index.ts              # Durable Object + Worker 入口
│   │   │   │   ├── context.ts            # Cloudflare Worker 上下文
│   │   │   │   ├── session-store.ts      # DO-backed SQLite 会话存储
│   │   │   │   ├── cf-sandbox.ts         # Cloudflare Container 沙箱
│   │   │   │   ├── virtual-sandbox.ts    # 虚拟沙箱（R2-backed 等）
│   │   │   │   └── define-command.ts     # Cloudflare 命令定义
│   │   │   └── node/             # Node.js 平台适配层
│   │   │       ├── index.ts              # Hono 服务器 + 本地模式
│   │   │       └── define-command.ts     # Node 命令定义（child_process）
│   │   └── ...
│   ├── cli/              # @flue/cli — CLI 工具（flue dev/run/build）
│   │   └── bin/flue.ts   # 706行 CLI 入口
│   └── connectors/       # @flue/connectors — 外部沙箱连接器
│       └── src/daytona.ts # Daytona 沙箱集成
├── apps/
│   └── www/              # 文档网站（Astro + Cloudflare Pages）
├── examples/
│   ├── hello-world/      # 7 个示例 Agent
│   └── assistant/        # 助手 Agent 示例
└── docs/                 # 部署文档（Cloudflare、Node、GitHub Actions、GitLab CI）
```

### 2.2 三层抽象模型

```
┌─────────────────────────────────────────────────────────┐
│  User Code (Agent Handler)                               │
│  ┌─────────────────────────────────────────────┐        │
│  │ export default async ({ init, payload }) => { │        │
│  │   const agent = await init({ model, sandbox })│        │
│  │   const session = await agent.session()       │        │
│  │   return await session.prompt("...", {result}) │        │
│  │ }                                              │        │
│  └─────────────────────────────────────────────┘        │
│                        ↕ FlueContext                     │
├─────────────────────────────────────────────────────────┤
│  SDK Runtime Layer                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ Session  │→│ Harness  │→│ pi-agent-core Agent   │  │
│  │ (prompt, │  │ (tools,  │  │ (agent loop, tool     │  │
│  │  skill,  │  │ compaction│  │  execution, streaming) │  │
│  │  task,   │  │ , model  │  └──────────────────────┘  │
│  │  shell)  │  │ resolve) │                             │
│  └──────────┘  └──────────┘                             │
│        ↕              ↕                                  │
│  ┌──────────────────────────────────────────────────┐   │
│  │ SessionEnv (统一的沙箱/文件系统/Shell 抽象接口)       │   │
│  │ exec() readFile() writeFile() stat() readdir()   │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  Platform Layer (Build Plugin)                          │
│  ┌─────────────────┐   ┌──────────────────────────┐    │
│  │ Node Plugin     │   │ Cloudflare Plugin        │    │
│  │ - Hono server   │   │ - Durable Objects        │    │
│  │ - esbuild bundle│   │ - Wrangler config merge  │    │
│  │ - external deps │   │ - TS entry (no bundle)   │    │
│  └─────────────────┘   └──────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## 三、核心概念详解

### 3.1 Agent = 目录

一个 Flue workspace 的目录结构：

```
workspace/
├── agents/                    # Agent 定义（TypeScript 文件）
│   ├── translate.ts           # 翻译 Agent
│   ├── reviewer.ts            # 代码审查 Agent
│   └── support.ts             # 客服 Agent
├── roles/                     # 角色定义（Markdown 文件）
│   ├── triager.md             # 支持分诊角色
│   └── analyst.md             # 数据分析角色
└── .agents/                   # Skills 目录（运行时在 sandbox cwd 中发现）
    └── greet/
        └── SKILL.md
```

**关键设计决策**：`AGENTS.md` 和 `.agents/skills/` **不被打包进构建产物**，而是在运行时从 session 的 cwd 动态发现。这使得：
- 同一个 Agent 部署可以在不同项目上下文中使用（不同项目的 AGENTS.md 提供不同上下文）
- Skills 随项目文件自然存在，不需要单独维护

### 3.2 Agent 文件结构

每个 Agent 是一个 TypeScript 文件，导出默认函数和 triggers 配置：

```typescript
// agents/translate.ts
import type { FlueContext } from '@flue/sdk/client';
import * as v from 'valibot';

export const triggers = { webhook: true };  // HTTP 触发
// export const triggers = { cron: '0 */6 * * *' };  // Cron 触发

export default async function ({ init, payload, env, id }: FlueContext) {
  const agent = await init({ model: 'anthropic/claude-sonnet-4-6' });
  const session = await agent.session();
  
  const result = await session.prompt(
    `Translate this to ${payload.language}: "${payload.text}"`,
    { result: v.object({ translation: v.string(), confidence: v.picklist(['low','medium','high']) }) }
  );
  
  return result;  // 自动序列化为 JSON 响应
}
```

**三种 Agent 类型**：
1. **Webhook Agent**（`triggers: { webhook: true }`）— 通过 HTTP POST `/agents/:name/:id` 调用
2. **Cron Agent**（`triggers: { cron: '...' }`）— 仅在 manifest 中声明，需外部调度器调用
3. **Triggerless Agent**（无 triggers）— 仅 CLI 本地调用（`flue run`），部署后不暴露 HTTP 路由

### 3.3 Session 核心架构

Session 是 Flue 最核心的抽象（`session.ts`，997 行），管理着完整的 LLM 交互生命周期。

#### Session 的四个核心方法

| 方法 | 作用 | 是否记录到历史 |
|------|------|----------------|
| `prompt(text, options)` | 向 LLM 发送消息，获取回复 | ✅ 记录 |
| `skill(name, options)` | 调用一个 Skill（带指令的专门任务） | ✅ 记录 |
| `task(text, options)` | 创建**分离的**子 Agent 会话（最多 4 层嵌套） | ❌ 仅返回最终答案 |
| `shell(command, options)` | 执行 Shell 命令（不经过 LLM） | ✅ 记录 |

#### 会话历史树（SessionHistory）

Session 历史不是一条线性列表，而是一棵**带分支的树**：

```
SessionData v2:
├── entries: [
│   ├── { type: 'message', id: 'm1', parentId: null, message: ... }     // 用户消息
│   ├── { type: 'message', id: 'm2', parentId: 'm1', message: ... }     // Agent 回复
│   ├── { type: 'compaction', id: 'c1', parentId: 'm2', summary: '...' } // 压缩摘要
│   ├── { type: 'message', id: 'm3', parentId: 'c1', message: ... }     // 新消息（接在摘要后）
│   └── { type: 'branch_summary', id: 'b1', fromId: 'm1', summary: '...' } // 分支摘要
│   ]
├── leafId: 'm3'       // 当前对话链的叶子节点
└── metadata: { ... }
```

这种树结构支持：
- **上下文压缩**：将旧消息替换为摘要节点，新消息挂在摘要之后
- **分支**：不同调用路径可以有不同的历史分支
- **恢复**：可以从任意节点重建上下文

#### 上下文压缩（Compaction）

```typescript
interface CompactionConfig {
  enabled?: boolean;              // 默认启用
  reserveTokens?: number;         // 保留的 token 余量，默认 16384
  keepRecentTokens?: number;      // 不压缩的最近 token 数，默认 20000
}
```

压缩流程：
1. 计算当前上下文 token 数（使用 pi-ai 的 `calculateContextTokens`）
2. 如果超出窗口（总 token - reserveTokens），触发压缩
3. 调用辅助 LLM 生成摘要（包含文件读写记录等 details）
4. 将旧消息替换为一个 `compaction` 节点
5. 新对话接在摘要之后继续

### 3.4 内置工具（6 + 1 个）

Flue 为 Agent 提供了一组与 Claude Code 相同的内置工具：

| 工具 | 描述 | 限制 |
|------|------|------|
| `read` | 读取文件或列目录 | 最多 2000 行 / 50KB |
| `write` | 写入文件（自动创建父目录） | — |
| `edit` | 精确文本替换（oldText→newText） | oldText 必须唯一匹配 |
| `bash` | 执行 Bash 命令 | 输出截断至 2000 行 / 50KB |
| `grep` | 正则搜索文件内容 | 最多 100 个匹配 |
| `glob` | 按 glob 模式查找文件 | 最多 1000 个结果 |
| `task` | 委托给分离的子 Agent | 最大嵌套深度 4 |

**关键设计**：这些工具不依赖特定平台，而是通过 `SessionEnv` 抽象接口实现。无论在 Node.js 虚拟沙箱、Cloudflare 容器还是 Daytona 容器中，工具的实现逻辑完全相同。

### 3.5 沙箱体系（Sandbox）

Flue 的 `SessionEnv` 接口统一了所有沙箱模式：

```typescript
interface SessionEnv {
  exec(command, options?): Promise<ShellResult>;
  readFile(path): Promise<string>;
  writeFile(path, content): Promise<void>;
  stat(path): Promise<FileStat>;
  readdir(path): Promise<string[]>;
  exists(path): Promise<boolean>;
  mkdir(path, options?): Promise<void>;
  rm(path, options?): Promise<void>;
  cwd: string;
  resolvePath(p): string;
  cleanup(): Promise<void>;
  scope?(options?): Promise<SessionEnv>;  // 操作级作用域
}
```

**四种沙箱模式**，按复杂度递增：

| 模式 | 启动时间 | 隔离性 | 适用场景 | 平台 |
|------|----------|--------|----------|------|
| **Empty Virtual** | 毫秒 | 无（内存 FS） | 简单的 prompt-response Agent | 全部 |
| **Virtual + Shell Setup** | 毫秒 | 无 | 需要少量静态上下文文件 | 全部 |
| **R2-backed Virtual** | 毫秒 | 无 | 知识库、客服 Agent（持久化文件存储） | Cloudflare |
| **Local** | 毫秒 | 无（共享主机 FS） | 代码审查、CI 任务、开发工具 | Node.js |
| **Container** | 秒级 | 完全隔离 | 多租户编码 Agent、复杂开发环境 | 全部 |

#### Virtual Sandbox 实现

虚拟沙箱基于 [just-bash](https://github.com/vercel-labs/just-bash)，提供了一个内存文件系统 + Bash 模拟器，无需容器即可支持文件读写和命令执行。

在 Cloudflare 上，`getVirtualSandbox(env.BUCKET)` 可以将 R2 桶挂载为沙箱文件系统，Agent 可以用 grep/glob/read 搜索整个知识库。

#### 命令系统（Commands）

`defineCommand` 提供了一种**安全的特权 CLI 桥接**机制：

```typescript
// 白名单方式暴露 git 命令，不泄露 process.env 中的 API key
const git = defineCommand('git', { env: { GIT_AUTHOR_NAME: 'flue-bot' } });

// 细粒度控制：只暴露一个特权环境变量
const npm = defineCommand('npm', { env: { NPM_TOKEN: process.env.NPM_TOKEN } });

// 完全自定义实现
const gh = defineCommand('gh', async (args) => {
  const res = await fetch('https://api.github.com/...');
  return { stdout: await res.text() };
});
```

命令是**按调用授权**的——在 prompt/skill/shell 调用时传入 `commands: [git, npm]`，Agent 只能在该调用期间使用这些命令。

### 3.6 角色系统（Roles）

Roles 是 Markdown 文件，定义 Agent 的行为模式：

```markdown
---
description: 支持分诊 Agent
model: anthropic/claude-opus-4-7   # 可选：为该角色指定特定模型
---

你是一个支持分诊员。在回复之前 thoroughly 搜索知识库...
```

**模型选择优先级**（从高到低）：
1. 调用级 `model`（`prompt("...", { model: "..." })`）
2. 角色级 `model`（role markdown 的 frontmatter）
3. Agent 级 `model`（`init({ model: "..." })`）
4. 构建时默认值

### 3.7 结果提取（Structured Output）

Flue 使用 Valibot schema 将 LLM 的自然语言回复转换为结构化数据：

```typescript
const result = await session.prompt("分析数据", {
  result: v.object({
    issues: v.array(v.object({
      file: v.string(),
      severity: v.picklist(['low', 'medium', 'high']),
      description: v.string(),
    })),
    summary: v.string(),
  }),
});
// result.issues 和 result.summary 有完整类型
```

实现流程：
1. 将 schema 转换为 prompt 文本（附加到用户消息后）
2. LLM 回复后，用另一个 LLM 调用提取结构化数据
3. 用 Valibot 验证提取结果
4. 如果验证失败，重试（带错误信息）

---

## 四、构建系统

### 4.1 构建架构

Flue 使用 **Plugin 模式**的构建系统，支持不同部署目标：

```typescript
interface BuildPlugin {
  name: string;
  generateEntryPoint(ctx: BuildContext): string | Promise<string>;
  bundle?: 'esbuild' | 'none';
  entryFilename?: string;
  esbuildOptions?(ctx: BuildContext): Record<string, any>;
  additionalOutputs?(ctx: BuildContext): Record<string, string> | Promise<...>;
}
```

**两种构建策略**：

| 策略 | 说明 | 适用目标 |
|------|------|----------|
| `esbuild` | 打包为单个 `dist/server.mjs`，外部化用户依赖 | Node.js |
| `none` | 只写 TS 入口文件，下游工具（wrangler）负责打包 | Cloudflare |

### 4.2 构建流程

```
1. 发现 workspace 中的 roles/ 和 agents/
2. 从 agent 文件正则解析 triggers（webhook / cron）
3. 生成 manifest.json（Agent 清单）
4. 调用 BuildPlugin.generateEntryPoint() 生成服务器入口代码
5. 根据 bundle 策略：
   a. esbuild → 打包为 dist/server.mjs
   b. none → 直接写入 TS 入口文件
6. 写入 additionalOutputs（如 wrangler.jsonc）
```

**关键设计**：Node 构建**外部化**用户依赖（不打包进 bundle），这样 `node_modules` 在运行时仍可用。这避免了 esbuild 打包原生模块（如 `fs`、`tar`）时的兼容性问题。

### 4.3 Node 插件

- 生成 Hono 服务器，监听 `PORT`（默认 3000）
- 路由：`GET /health`、`GET /agents`、`POST /agents/:name/:id`
- Agent 通过 Durable Object 模式管理（每个 Agent name+id 一个 session）
- `FLUE_MODE=local` 环境变量允许调用 triggerless Agent

### 4.4 Cloudflare 插件

- 生成 TS 入口（不打包，wrangler 负责）
- 合并 wrangler.jsonc 配置（用户配置 + Flue 的 DO bindings）
- 自动检测 `class_name` 包含 "Sandbox" 的 DO binding，自动 re-export 为 `@cloudflare/sandbox` 的 `Sandbox` 类
- 在 DO 中使用 SQLite 持久化会话

---

## 五、CLI 工具

### 5.1 三个命令

| 命令 | 作用 | 使用场景 |
|------|------|----------|
| `flue dev` | 长时间运行的 watch-mode 开发服务器 | 本地开发，文件变更自动重建 |
| `flue run` | 一次性构建 + 调用 + 退出 | CI/脚本调用 |
| `flue build` | 仅构建，不运行 | 生产部署 |

### 5.2 Workspace 发现

```
当前目录
  ├── .flue/agents/  ← 如果 .flue/ 存在，优先使用
  └── agents/        ← 否则用项目根目录
```

### 5.3 `flue run` 工作原理

```
1. 构建 workspace → dist/server.mjs
2. 启动临时 Node 服务器（FLUE_MODE=local）
3. 通过 SSE 流式调用 Agent
4. stderr 流式输出 Agent 的 text_delta 和 tool 事件
5. stdout 输出最终结果（JSON）
6. 关闭服务器，退出
```

SSE 消费者解析服务器推送的事件，实时在 stderr 打印 Agent 的思考过程和工具调用。

---

## 六、部署模式

### 6.1 Node.js 部署

```bash
flue build --target node
node dist/server.mjs  # 监听 PORT（默认 3000）
```

部署目标：VPS、Docker、Railway、Fly.io、AWS/GCP/Azure 等。

**Session 持久化**：默认内存存储，重启丢失。需传入自定义 `SessionStore` 实现（SQLite、Postgres、Redis 等）。

### 6.2 Cloudflare Workers 部署

```bash
flue build --target cloudflare
wrangler deploy --secrets-file .env
```

**Session 持久化**：Durable Objects 内置 SQLite，自动持久化。

**沙箱策略选择**（4 级）：

1. **Empty Virtual** → `init({ model })` — 毫秒启动，最便宜
2. **Virtual + Shell Setup** → `session.shell('mkdir -p ...; cat > ...')` — 动态创建上下文
3. **R2-backed Virtual** → `getVirtualSandbox(env.KNOWLEDGE_BASE)` — 持久化知识库
4. **Container** → `getSandbox(env.Sandbox, id)` — 完整 Linux 环境

### 6.3 GitHub Actions / GitLab CI

Flue 支持在 CI 环境中运行 Agent（通过 `flue run`），适用于：
- 自动代码审查
- PR 评论生成
- CI 任务自动化

---

## 七、示例 Agent 分析

### 7.1 Hello World

```typescript
// .flue/agents/hello.ts
export const triggers = { webhook: true };

export default async function ({ init, payload }: FlueContext) {
  const agent = await init({ model: 'anthropic/claude-haiku-4-5-20251001' });
  const session = await agent.session();
  return await session.prompt(`Greet ${payload.name} warmly`);
}
```

最简 Agent：无沙箱、无角色、无结构化输出，纯 prompt-response。

### 7.2 Session Test（多轮对话）

```typescript
const s = await agent.session('conv-1');
await s.prompt('My favorite color is blue');
const r = await s.prompt('What is my favorite color?');
// r.text === "Your favorite color is blue"
```

展示了**会话持久化**：同一个 session ID 恢复之前的对话。

### 7.3 Task Test（子 Agent 委托）

```typescript
const s = await agent.session();
const r1 = await s.task('What is 2+2?');
const r2 = await s.task('What is 3+3?', { role: 'math' });
const combined = await s.prompt(`Combine: ${r1.text} and ${r2.text}`);
```

展示了**分离式子任务**：每个 task 有独立的上下文，只返回最终答案，不污染父会话历史。

### 7.4 With Tools（自定义工具）

```typescript
const weather: ToolDef = {
  name: 'get_weather',
  description: 'Get current weather for a city',
  parameters: Type.Object({ city: Type.String() }),
  execute: async ({ city }) => JSON.stringify({ city, temp: 22, condition: 'sunny' }),
};

const agent = await init({ model, tools: [weather] });
```

自定义工具通过 `ToolDef` 接口注册，在 `init()` 时设为 Agent 级工具，或在 `prompt()`/`skill()` 时设为调用级工具。

### 7.5 With Skill（技能调用）

```typescript
const greeting = await session.skill('greet', {
  args: { name: 'World' },
  result: v.object({ greeting: v.string() }),
});
```

Skill 是 `.agents/skills/greet/SKILL.md` 中定义的 Markdown 指令。调用时：
1. 加载 SKILL.md 内容
2. 将 instructions + args + result schema 组合为 prompt
3. 发送给 LLM 执行
4. 验证并返回结构化结果

### 7.6 Compaction Test（上下文压缩）

```typescript
const s = await agent.session('compact-1');
for (let i = 0; i < 10; i++) {
  await s.prompt(`Message ${i}: ${'A'.repeat(200)}`);
}
```

当上下文 token 数接近模型窗口时，自动触发压缩。压缩后旧消息被替换为摘要。

---

## 八、依赖链与关键技术选型

### 8.1 核心依赖

```
@flue/sdk
├── @mariozechner/pi-agent-core    ← Agent Harness（agent loop、tool execution、streaming）
├── @mariozechner/pi-ai            ← AI provider 抽象（多模型路由、token 计算）
├── hono                           ← HTTP 框架（Node.js 服务器）
├── esbuild                        ← 构建打包
├── valibot                        ← 运行时 schema 验证（结构化输出）
├── just-bash (via pi-agent-core)  ← 虚拟沙箱（内存 FS + Bash）
└── package-up                     ← 查找 package.json（外部化依赖发现）
```

### 8.2 Agent Harness 的复用

Flue 没有自己实现 Agent loop，而是复用了 Mario Zechner 的 `pi-agent-core`。这是非常聪明的架构决策：
- 该库已经实现了完整的 agent loop（parallel tool execution、streaming、abort 等）
- Claude Code 的底层也是类似架构
- Flue 只需要在上面加一层**部署基础设施**（HTTP 路由、沙箱抽象、构建系统、持久化）

### 8.3 平台无关性设计

`SessionEnv` 接口是关键抽象。所有平台特定的沙箱实现（虚拟 FS、本地 FS、R2、Daytona 容器、CF Container）都实现同一个接口。这使得 Agent 代码完全不需要关心底层沙箱是什么。

---

## 九、设计亮点与评价

### 9.1 优点

1. **极低的学习曲线**——Agent 代码就是一个 async function，任何会写 TypeScript 的人都能上手
2. **目录即配置**——AGENTS.md、skills、roles 都是 Markdown，非程序员也能编辑
3. **运行时无关**——同一套代码部署到 Node 或 Cloudflare，无需修改
4. **沙箱渐进式**——从最简单的 prompt-response 到完整容器隔离，按需升级
5. **命令安全模型**——`defineCommand` 白名单式暴露 CLI，不泄露 host 环境变量
6. **会话树结构**——支持压缩、分支、恢复，不是简单的消息列表
7. **跨模型泛化**——每个调用可以指定不同模型，同一 Agent 可以用 haiku 做 cheap 调用、opus 做关键决策
8. **构建插件化**——添加新的部署目标只需实现一个 BuildPlugin

### 9.2 局限性与风险

1. **Experimental 状态**——API 可能变化，生产环境需谨慎
2. **仅 TypeScript**——不支持 Python/Rust 等其他语言写 Agent
3. **工具集有限**——目前只有 7 个内置工具，没有浏览器控制、数据库查询等高级工具
4. **无内置 Agent 编排**——多个 Agent 之间的协作（multi-agent orchestration）需要用户自己实现
5. **安全性依赖沙箱**——local sandbox 共享主机文件系统，多租户场景必须用容器
6. **Cloudflare run 不支持**——`flue run --target cloudflare` 不可用，只能用 `flue dev` 本地测试
7. **会话存储在 DO 中**——Cloudflare 部署的会话持久化绑定在 Durable Object 上，迁移到其他平台需要重新实现

### 9.3 与竞品的对比

| 维度 | Flue | LangGraph | CrewAI | Vercel AI SDK |
|------|------|-----------|--------|---------------|
| 定位 | Agent 部署框架 | Agent 编排框架 | Multi-Agent 框架 | LLM API 抽象 |
| Agent 定义 | 目录 + TypeScript | Python 代码 | Python 代码 | TypeScript 函数 |
| 部署 | 编译后可部署 | 需要自行部署 | 需要自行部署 | 需要自行部署 |
| 沙箱 | 内置（虚拟/本地/容器） | 无 | 无 | 无 |
| 运行时 | Node.js / Cloudflare | Python | Python | 任意 |
| 持久化 | 平台适配（DO SQLite / 自定义） | 需自行实现 | 需自行实现 | 无 |
| 工具集 | 内置 7 个 + 自定义 | 自定义 | 自定义 | 自定义 |
| 多模型 | 原生支持（per-call） | 支持 | 支持 | 支持 |

**Flue 的独特价值在于**：它是唯一一个将"Agent 定义 → 编译 → 部署"全链路打通的框架，且部署目标从 Node.js 到边缘计算全覆盖。

---

## 十、典型应用场景

1. **客服 Agent** — R2 知识库 + 虚拟沙箱 + Durable Object 持久化，部署在 Cloudflare Workers
2. **代码审查 Agent** — Node.js local sandbox 直接访问代码仓库，通过 GitHub Actions 触发
3. **翻译/摘要 Agent** — 简单的 prompt-response，部署在边缘，低延迟
4. **CI Agent** — triggerless agent，仅 `flue run` 在 CI 管道中调用
5. **多租户编码沙箱** — 容器沙箱 + per-session 隔离 + outbound Worker 保护 API key
6. **数据分析 Agent** — 本地沙箱访问数据文件，用 task 分离并行分析子任务

---

## 十一、总结

Flue 是一个设计精良的 Agent 部署框架，核心创新在于**将 Claude Code 级别的 Agent 能力从交互式工具转变为可部署的基础设施**。它的目录驱动开发模型、运行时无关的构建系统、渐进式沙箱策略和会话树持久化，使其成为构建和部署生产级 AI Agent 的强大工具。

对于熟悉 Claude Code/Codex/Gemini CLI 的开发者来说，Flue 的学习曲线几乎是零——你已经知道怎么写 Agent，Flue 只是帮你把它部署上线。

---

*调研日期：2025 年 | 基于仓库 commit 截至 HEAD 版本*