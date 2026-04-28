# AI 工程基础设施：从模型中心到平台中心的范式转移

**文档日期：** 2026 年 4 月 28 日  
**标签：** AI Engineering, Infrastructure, MCP Protocol, Enterprise Architecture, Cloudflare, AGENTS.md, Code Mode, Knowledge Layer

---

## 一、背景分析：当模型趋同时，什么才是差异化？

### 1.1 从"选模型"到"建平台"

2024-2025 年，AI 应用开发的核心决策是"选哪个模型"。GPT-4 vs Claude vs Gemini——模型能力的差距决定了产品的上限。

进入 2026 年 Q2，一个关键转折正在发生：**前沿模型的能力差距正在收敛**。VILA-Lab 对 Claude Code 的源码级分析揭示了一个颠覆性数据：

> **Claude Code 代码库中，98.4% 是确定性基础设施代码，仅 1.6% 是 AI 决策逻辑。**

这不是 Claude Code 的特例。当 Andrej Karpathy 指出"OpenClaw 时刻之所以重要，是因为它让大量非技术用户第一次体验到 AI 不只是 ChatGPT"时，他揭示的正是同一个趋势——**AI 的价值不再来自模型本身，而来自模型周围的工程基础设施**。

### 1.2 行业信号：基础设施层的爆发

2026 年 4 月，多个标志性事件指向同一方向：

| 事件 | 信号 |
|------|------|
| **OpenAI 解除微软云独占** | 模型厂商走向多云，基础设施层独立化 |
| **LangChain 发布 2026 年 4 月更新** | Agent 框架从"编排"转向"治理" |
| **Cloudflare iMARS 项目全量上线** | 3,683 用户、4795 万请求/月、93% R&D 采用率 |
| **MCP Server Portal + Code Mode** | 解决工具膨胀的上下文开销问题 |
| **AGENTS.md 成为事实标准** | OpenAI Codex、Claude Code、Windsurf全面支持 |

关键洞察：**AI 工程正在经历从"模型中心"到"平台中心"的范式转移。**

---

## 二、核心问题定义：企业 AI 工程的三大挑战

### 2.1 挑战一：上下文膨胀与工具税

MCP 协议让 Agent 可以连接任意工具，但每个工具定义都消耗上下文窗口。Cloudflare 的实践揭示了一个严峻的数学问题：

```
场景：GitLab MCP 服务器
├── get_merge_request    → ~450 tokens
├── list_pipelines       → ~380 tokens
├── get_file_content     → ~420 tokens
├── ... (34 个工具总计)
└── 工具 Schema 总开销    → ~15,000 tokens

在 200K 上下文窗口中：15,000 / 200,000 = 7.5% 的预算
在 Agent 提问之前，就已经消耗了 7.5% 的上下文窗口。
```

当企业部署 13 个 MCP 服务器、暴露 182+ 工具时，问题呈指数级放大。**工具税（Tool Tax）正在吃掉 Agent 的有效上下文。**

### 2.2 挑战二：知识孤岛与 Agent 盲区

Agent 可以读取代码，但无法看到代码背后的系统：

```
Agent 能看到的：
  ├── src/users/api.ts       ← 代码文件
  ├── tests/users.test.ts    ← 测试文件
  └── package.json           ← 依赖声明

Agent 看不到的：
  ├── 谁拥有这个服务？
  ├── 它依赖哪些数据库？
  ├── 部署流程是什么？
  ├── 团队编码规范是什么？
  └── 哪些文件是自动生成的，不应修改？
```

没有结构化知识，Agent 就像盲人摸象——能摸到局部，但拼不出全局。

### 2.3 挑战三：安全治理与规模化矛盾

Trend Micro 2026 年 2 月的报告指出：**492 个 MCP 服务器暴露在公网上且零认证**。当企业有数千名开发者、数百个 Agent 实例时，如何确保：

- API Key 不泄露到开发者笔记本
- 每个请求都有可追溯的用户归因
- 模型调用成本可控且透明
- 生成的代码经过安全审查

传统的手动审批流程无法扩展到 3,683 用户、每天 68.8 万请求的规模。

---

## 三、解决方案：Cloudflare 的三层架构

Cloudflare 的 iMARS 团队（Internal MCP Agent/Server Rollout Squad）用 11 个月时间，构建了一套完整的企业级 AI 工程基础设施。他们的架构分为三层，每一层都对应一个核心挑战。

### 3.1 平台层：统一入口，零配置接入

#### 架构全景

```
┌─────────────────────────────────────────────────────────────────┐
│                    开发者终端 (Developer CLI)                     │
│  OpenCode / Windsurf / Claude Code (MCP-compatible clients)     │
└────────────────────────┬────────────────────────────────────────┘
                         │  opencode auth login <URL>
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Proxy Worker (Hono App)                            │
│  ├── 服务共享配置 (.well-known/opencode)                        │
│  ├── JWT 验证 + 用户 UUID 映射 (D1 + KV)                        │
│  ├── 请求路由 (Anthropic / OpenAI / Google / Workers AI)        │
│  ├── API Key 注入 (客户端零 Key)                                 │
│  └── 模型目录自动更新 (cron → KV)                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AI Gateway                                    │
│  ├── 20.18M 请求/月  │  241.37B tokens 路由                     │
│  ├── 成本追踪 + BYOK + Zero Data Retention                      │
│  └── 多模型路由 + 负载均衡                                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────────┐
    │ Frontier  │  │ Workers  │  │ MCP Server   │
    │ Models    │  │ AI       │  │ Portal       │
    │ 91.16%    │  │ 8.84%    │  │ 13 servers   │
    └──────────┘  └──────────┘  │ 182+ tools   │
                                └──────────────┘
```

#### 关键设计决策

**决策 1：单一代理 Worker 作为控制面**

Cloudflare 没有让客户端直连 AI Gateway，而是通过一个代理 Worker 集中路由。这个看似增加了一层复杂度的设计，带来了巨大的灵活性：

```typescript
// Proxy Worker 核心逻辑（简化版）
export default {
  async fetch(request: Request, env: Env) {
    // 1. 验证 Cloudflare Access JWT
    const jwt = request.headers.get("cf-access-token");
    const user = await validateJWT(jwt);

    // 2. 映射到匿名 UUID（隐私保护）
    const anonId = await getAnonUUID(user.email, env.D1, env.KV);

    // 3. 注入 Provider API Key（客户端零 Key）
    const provider = extractProvider(request.url);
    const apiKey = env.PROVIDER_KEYS[provider];

    // 4. 转发到 AI Gateway
    return fetch(rewriteToAIGateway(request), {
      headers: {
        "cf-aig-authorization": `Bearer ${apiKey}`,
        "cf-aig-metadata": JSON.stringify({ userId: anonId }),
      },
    });
  },
};
```

**效果**：每用户成本追踪、模型目录管理、权限执行——全部在不修改客户端配置的情况下实现。

**决策 2：One URL 配置一切**

```bash
# 开发者只需执行一条命令
opencode auth login https://opencode.internal.cloudflare.com
```

这条命令触发完整的配置链：

```
auth login
  → 获取 .well-known/opencode 配置
    → 执行 cloudflared access login（SSO 认证）
      → 获取 signed JWT
        → 合并 provider / model / MCP server / agent / permission 配置
          → 本地存储，后续请求自动携带 JWT
```

**效果**：3,683 名开发者零手动配置，全部通过一条命令完成接入。

### 3.2 知识层：从代码孤岛到知识图谱

#### Backstage：16K+ 实体的服务目录

```
Backstage 服务目录（Cloudflare 内部）：
├── 2,055 个服务
├── 167 个库 + 122 个包
├── 228 个 API（含 Schema 定义）
├── 544 个系统（45 个域）
├── 1,302 个数据库 + 277 个 ClickHouse 表
├── 375 个团队 + 6,389 个用户（含所有权映射）
└── 完整的依赖关系图
```

Agent 通过 Backstage MCP 服务器（13 个工具）可以：

```
用户提问："修改 user-service 的认证逻辑，会影响哪些下游服务？"

Agent 工作流：
1. Backstage MCP → 查询 user-service 的 ownership
   → 返回：由 auth-team 维护
2. Backstage MCP → 查询依赖关系图
   → 返回：api-gateway, dashboard, notification-service 依赖它
3. Backstage MCP → 拉取相关 API Schema
   → 返回：228 个 API 定义中的相关部分
4. 生成影响分析报告
```

**没有 Backstage，Agent 只能看到代码。有了 Backstage，Agent 能看到整个工程组织。**

#### AGENTS.md：让每个仓库为 AI 做好准备

Cloudflare 处理了约 3,900 个仓库，为每个仓库生成结构化的 `AGENTS.md` 文件：

```markdown
# AGENTS.md

## Repository
- Runtime: cloudflare workers
- Test command: `pnpm test`
- Lint command: `pnpm lint`

## How to navigate this codebase
- All cloudflare workers are in src/workers/, one file per worker
- MCP server definitions are in src/mcp/, each tool in a separate file
- Tests mirror source: src/foo.ts -> tests/foo.test.ts

## Conventions
- Testing: use Vitest with `@cloudflare/vitest-pool-workers`
- API patterns: Follow internal REST conventions

## Boundaries
- Do not edit generated files in `gen/`
- Do not introduce new background jobs without updating `config/`

## Dependencies
- Depends on: auth-service, config-service
- Depended on by: api-gateway, dashboard
```

**生成流水线**：

```
Backstage 实体元数据（所有权、依赖关系）
  → 仓库结构分析（语言、构建系统、测试框架）
    → 映射 Engineering Codex 规范
      → LLM 生成结构化文档
        → 自动创建 Merge Request
          → 团队审核和精炼
```

**效果**：Agent 不再需要从零推断仓库上下文，直接读取 `AGENTS.md` 即可获得结构化知识。

### 3.3 执行层：Code Mode 解决上下文膨胀

#### 传统 MCP 的问题

```
13 个 MCP 服务器 × 平均 14 个工具 = 182 个工具定义
每个工具定义 ~400 tokens
总开销：182 × 400 = 72,800 tokens

在 200K 上下文中：72,800 / 200,000 = 36.4%
```

**超过三分之一的上下文窗口被工具 Schema 吃掉。**

#### Code Mode 的解决方案

MCP Server Portal 的 Code Mode 将 182 个工具坍缩为 2 个 Portal 级工具：

```
传统模式：
  Client 看到 182 个工具 → 每次请求加载全部 Schema → 72,800 tokens

Code Mode：
  Client 看到 2 个工具：
    ├── portal_codemode_search   ← 搜索可用工具
    └── portal_codemode_execute  ← 执行工具调用
  每次请求开销：~800 tokens（减少 98.9%）
```

```
Code Mode 工作流程：
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  LLM 决策   │────→│ portal_codemode_ │────→│  动态发现工具    │
│  需要工具   │     │  search          │     │  获取 Schema     │
└─────────────┘     └──────────────────┘     └────────┬─────────┘
                                                      │
┌─────────────┐     ┌──────────────────┐              │
│  LLM 执行   │←────│  返回匹配的      │←─────────────┘
│  工具调用   │     │  工具列表        │
└─────────────┘     └──────────────────┘
```

**关键优势**：新增 MCP 服务器不再增加客户端的上下文开销。Portal 层面的 Code Mode 实现了**工具扩展的 O(1) 上下文成本**。

---

## 四、数据验证：规模化 AI 工程的真实指标

### 4.1 Cloudflare 内部数据（30 天）

| 指标 | 数值 | 意义 |
|------|------|------|
| 活跃用户 | 3,683（60% 全公司，93% R&D） | 企业级采用率 |
| AI 请求总量 | 4,795 万 | 日均 160 万请求 |
| AI Gateway 请求 | 2,018 万/月 | 统一路由层 |
| 路由 Token 量 | 2,413.7 亿 | 基础设施处理能力 |
| Workers AI Token | 518.3 亿 | 开源模型承担 8.84% |
| 使用团队数 | 295 | 跨部门覆盖 |
| Merge Request 增长 | 季度环比历史新高 | 开发效率提升 |

### 4.2 模型分布与成本优化

```
请求分布：
┌─────────────────────────────────────┐
│ Frontier Models (OpenAI/Anthropic/  │
│ Google)            13.38M  91.16%   │
│                                     │
│ Workers AI (开源模型)  1.3M   8.84%  │
└─────────────────────────────────────┘

成本案例：安全 Agent
├── 每日处理 Token：70 亿
├── 中端闭源模型年成本：~$240 万
├── Workers AI (Kimi K2.5) 年成本：~$55 万
└── 节省比例：77%
```

**趋势判断**：前沿模型处理复杂 Agent 编码工作，开源模型承担安全审查、文档生成、上下文文件生成等中等复杂度任务。混合模型策略正在成为企业标配。

### 4.3 开发效率提升

```
Merge Request 4 周滚动均值：
Q4 2025 基准：~5,600 MR/周
2026 Q1 末：  ~8,700 MR/周（+55%）
3 月 23 日周：10,952 MR/周（+96%）
```

**这不是模型升级带来的提升，而是工程基础设施带来的系统性效率改进。**

---

## 五、范式转移：从模型中心到平台中心

### 5.1 三层架构的抽象

Cloudflare 的架构可以抽象为 AI 工程基础设施的通用三层模型：

```
┌──────────────────────────────────────────────────────┐
│              应用层 (Application Layer)               │
│  Agent 应用 / 编码助手 / 自动化工作流                  │
│  关注点：用户体验、任务完成度、业务价值                 │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────┐
│              知识层 (Knowledge Layer)                 │
│  AGENTS.md / Backstage / 服务目录 / 规范文档          │
│  关注点：结构化知识、上下文注入、规范执行               │
└────────────────────────┼─────────────────────────────┘
                         │
┌────────────────────────┼─────────────────────────────┐
│              平台层 (Platform Layer)                  │
│  认证 / 路由 / 成本追踪 / MCP 网关 / 模型路由         │
│  关注点：安全、可观测、成本控制、可扩展性               │
└──────────────────────────────────────────────────────┘
```

### 5.2 对 AI 开发者的启示

**启示 1：基础设施是真正的差异化因素**

> "As frontier models converge in capability (top 3 within 1% on SWE-bench), the operational harness becomes the differentiator, not the model or the scaffolding."

当模型能力趋同时，**上下文管理、安全治理、成本优化、知识注入**这些" boring"的基础设施工作，才是决定 Agent 系统成败的关键。

**启示 2：AGENTS.md 是每个仓库的"AI 就绪"证书**

OpenAI Codex、Claude Code、Windsurf 都已支持 `AGENTS.md`。这不是一个文件，而是一种**协议**——告诉 Agent 如何与这个仓库协作。每个工程团队都应该：

1. 为每个仓库编写 `AGENTS.md`
2. 包含构建命令、测试命令、编码规范
3. 明确边界约束（哪些文件不应修改）
4. 声明依赖关系（上游/下游服务）

**启示 3：Code Mode 是 MCP 规模化的必经之路**

当工具数量超过 20 个时，传统 MCP 的上下文开销变得不可接受。Code Mode 通过动态发现而非静态加载，将上下文成本从 O(n) 降到 O(1)。这是 MCP 从"玩具"走向"生产"的关键一步。

**启示 4：代理模式优于直连**

```
直连模式：
  Client → Provider API
  问题：API Key 在客户端、无统一成本追踪、无法动态路由

代理模式：
  Client → Proxy → AI Gateway → Provider API
  优势：零 Key 分发、统一归因、动态路由、模型热切换
```

Cloudflare 的 Proxy Worker 模式证明了：**多一层抽象，换来的是无限的控制力。**

---

## 六、总结与展望

### 6.1 核心结论

1. **AI 工程正在从模型中心转向平台中心**。模型能力趋同，基础设施成为差异化关键。
2. **三层架构（平台层-知识层-执行层）是企业 AI 基础设施的通用模式**。Cloudflare 的实践提供了经过验证的参考实现。
3. **AGENTS.md 正在成为代码仓库的标配**。它是 Agent 理解仓库上下文的最低成本方式。
4. **Code Mode 解决了 MCP 规模化的上下文膨胀问题**。工具数量不再是瓶颈。
5. **混合模型策略（前沿 + 开源）是成本最优解**。Cloudflare 用 Workers AI 节省了 77% 的安全 Agent 成本。

### 6.2 未来展望

| 方向 | 预测 |
|------|------|
| **AGENTS.md 标准化** | 2026 年底可能成为 LSP 级别的行业标准 |
| **Code Mode 普及** | 从 Portal 层下沉到单个 MCP Server 层 |
| **知识图谱即服务** | Backstage 等内部工具将演变为 Agent 知识基础设施 |
| **模型路由智能化** | 基于任务复杂度自动选择最优模型（成本/质量平衡） |
| **AI 工程可观测性** | 从"请求追踪"升级为"Agent 行为审计" |

### 6.3 行动建议

对于正在构建或评估 AI 工程基础设施的团队：

1. **立即开始**：为关键仓库编写 `AGENTS.md`，这是成本最低、回报最高的投资
2. **部署统一入口**：无论用 AI Gateway 还是自建代理，确保所有 LLM 请求经过统一路由
3. **评估 Code Mode**：如果 MCP 工具超过 20 个，Code Mode 的上下文节省立竿见影
4. **建立知识图谱**：服务目录、依赖关系、团队所有权——这些结构化数据是 Agent 的"眼睛"
5. **混合模型策略**：不要把所有请求都送到最贵的模型。用开源模型处理中等复杂度任务，节省的成本可以用于关键时刻的前沿模型调用

---

**参考资料：**

- [Cloudflare: The AI engineering stack we built internally](https://blog.cloudflare.com/internal-ai-engineering-stack/) (2026-04-20)
- [VILA-Lab: Dive into Claude Code](https://github.com/VILA-Lab/Dive-into-Claude-Code) (2026-04)
- [Cloudflare: Enterprise MCP Reference Architecture](https://blog.cloudflare.com/enterprise-mcp/)
- [Augment Code: How to Build Your AGENTS.md](https://www.augmentcode.com/guides/how-to-build-agents-md) (2026-03)
- [Trend Micro: MCP Security Report](https://www.trendmicro.com) (2026-02)
- [OpenAI Codex Pricing](https://developers.openai.com/codex/pricing) (2026-04)
