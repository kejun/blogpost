# DB9.ai 产品设计与架构深度分析报告

**调研时间：** 2026-03-20  
**调研对象：** https://db9.ai  
**数据源：** 官网、文档、Hacker News 讨论

---

## 🎯 一、产品定位

### 核心主张
> **"Postgres but for agents"** — 为 AI Agent 设计的 Serverless PostgreSQL

### 目标用户
1. **Agent 开发者** — 需要存储 Agent 状态、上下文和产出物
2. **平台工程师** — 构建多 Agent 或多租户系统
3. **评估者** — 正在比较 DB9 vs Neon/Supabase/托管 Postgres

### 价值主张
- **零配置** — 无需注册，匿名数据库立即可用
- **全功能内置** — 嵌入、向量搜索、文件系统、HTTP 调用、定时任务都在 SQL 层
- **标准 PostgreSQL** — 任何 Postgres 客户端/ORM 都能直接连接

---

## 🏗️ 二、技术架构

### 整体架构
```
┌─────────────────────────────────────────────────┐
│ Clients                                          │
│ psql · ORMs · drivers · SDK · CLI · Browser     │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌─────────────────┐     ┌──────────────────┐
│ Control Plane   │     │ Data Plane       │
│ (db9-backend)   │     │ (db9-server)     │
│                 │     │                  │
│ REST API        │     │ pgwire protocol  │
│ Auth & tokens   │     │ SQL engine       │
│ DB lifecycle    │     │ Extensions       │
│ Branching       │     │ Worker engine    │
│ Observability   │     │                  │
└────────┬────────┘     └────────┬──────────┘
         │                       │
         └──────────┬────────────┘
                    ▼
           ┌────────────────┐
           │ TiKV           │
           │ (distributed   │
           │ KV storage)    │
           └────────────────┘
```

### 核心组件

#### 1. 数据平面 (db9-server)
- **语言：** Rust + Tokio 异步运行时
- **协议：** PostgreSQL wire protocol (端口 5433)
- **存储：** TiKV (分布式 KV，Raft 共识，ACID 事务)

**内部组件：**
| 组件 | 职责 |
|------|------|
| pgwire listener | 接受 Postgres 协议连接，处理 TLS/认证 |
| SQL parser | sqlparser-rs 解析 SQL 为 AST |
| Analyzer | 单遍名称解析和类型检查 |
| Optimizer | 基于成本的优化，DPccp _join 重排序_ |
| Executor | Volcano 模型拉取式迭代器管道 |
| TiKV store | 事务管理（悲观锁、快照隔离） |
| RLS engine | 行级安全策略执行 |
| Extension runtime | 编译时扩展注册 |
| Worker engine | pg_cron、异步触发器、auto-analyze |

#### 2. 控制平面 (db9-backend)
- **框架：** Axum (Rust web 框架)
- **元数据存储：** SQLite 或 PostgreSQL
- **职责：** 数据库 CRUD、用户管理、Token 生命周期、分支、迁移、可观测性

#### 3. 客户端工具
- **CLI：** `db9` 命令行工具
- **SDK：** TypeScript SDK (`get-db9` npm 包)
- **Browser SDK：** 客户端数据访问（带 RLS）

---

## 🔌 三、核心功能设计

### 1. 即时配置 (Instant Provisioning)
```bash
# CLI - 无需注册
db9 create --name myapp

# SDK - 幂等
import { instantDatabase } from 'get-db9';
const db = await instantDatabase({
  name: 'myapp',
  seed: 'CREATE TABLE ...'
});
```

**设计亮点：**
- 匿名账户可创建 5 个数据库
- SSO 认领后解除限制
- SDK 自动复用已存在数据库

### 2. 内置 Embeddings 和向量搜索
```sql
-- 启用扩展
CREATE EXTENSION embedding;

-- 生成 embedding 并存储
INSERT INTO docs (content, vec)
VALUES ('deployment guide', embedding('deployment guide')::vector);

-- 语义搜索
SELECT content FROM docs
ORDER BY vec <-> embedding('how do I deploy?')::vector
LIMIT 5;
```

**设计亮点：**
- 无需外部 embedding 服务
- 服务器端生成、缓存
- 每租户并发限制（默认 5）
- 支持 HNSW 索引

### 3. fs9 — SQL 层文件系统
```sql
-- 读取 CSV 为表
SELECT * FROM fs9('/data/results.csv');

-- 写入文件
SELECT fs9_write('/data/output.json', '{"status": "complete"}');

-- 检查文件存在
SELECT fs9_exists('/data/results.csv');
```

**限制：**
- 单文件 100 MB
- 单次操作读取预算 128 MB
- 支持 CSV、JSON Lines、Parquet（自动 schema 推断）

### 4. HTTP from SQL
```sql
-- GET 请求
SELECT status, content
FROM http_get(
  'https://api.example.com/enrich',
  '[{"field":"Authorization","value":"Bearer sk-..."}]'::jsonb
);

-- POST 请求
SELECT content FROM http_post(
  'https://hooks.slack.com/services/...',
  '{"text": "Task complete"}',
  'application/json'
);
```

**安全边界：**
- 仅 HTTPS（禁止明文 HTTP）
- 阻止私有/回环 IP（SSRF 防护）
- 每语句 100 请求，每租户 20 并发
- 响应最大 1 MB，请求体最大 256 KB
- 5 秒超时

### 5. 数据库分支
```bash
db9 branch create myapp --name experiment
# Agent 在分支上工作...
db9 branch delete experiment
```

**分支包含：**
- ✓ 表和行
- ✓ 文件和上传
- ✓ Cron 任务
- ✓ 用户权限
- ✓ 扩展

### 6. 定时任务 (pg_cron)
```sql
SELECT cron.schedule(
  'cleanup-old-context',
  '0 */6 * * *',
  $$DELETE FROM context WHERE created_at < now() - interval '7 days'$$
);
```

### 7. Agent Onboarding
```bash
# 一键安装技能
db9 onboard --agent claude   # Claude Code
db9 onboard --agent codex    # OpenAI Codex
db9 onboard --agent opencode # OpenCode
```

**安装范围：**
- `--scope user` — 全局安装（默认）
- `--scope project` — 当前项目
- `--scope both` — 两者

---

## 🛡️ 四、多租户隔离

### 隔离模型
```
TiKV Cluster
├─ Keyspace A (tenant_a)
│ ├─ System metadata (tables, schemas, types, extensions, roles)
│ ├─ Table data (rows keyed by table ID + primary key)
│ ├─ Index data (secondary index entries)
│ └─ Worker state (cron jobs, task queue)
├─ Keyspace B (tenant_b)
│ └─ ... (完全独立)
└─ Keyspace C (tenant_c)
    └─ ...
```

### 连接模型
- 用户名格式：`tenant_id.role` (如 `a1b2c3d4e5f6.admin`)
- db9-server 解析用户名获取租户 ID，查找 keyspace
- 所有键编码包含 keyspace 前缀
- **无跨租户查询路径**

### 独立资源
- 表和 schema 命名空间
- 角色和权限
- 扩展安装状态
- Worker 队列和 cron 任务
- 内存配额 (`DB9_TENANT_MEMORY_QUOTA_BYTES`)

---

## ⚠️ 五、架构限制与边界

| 领域 | 当前状态 |
|------|----------|
| 执行模型 | 单进程、单节点，无分布式查询执行 |
| 计划缓存 | 仅会话本地，无跨连接共享 |
| GIN 索引 | 规划器生成计划但执行回退到表扫描 |
| 并行查询 | 不支持，单 Tokio 任务执行 |
| 外部数据包装器 | 不支持，使用 HTTP 扩展替代 |
| 逻辑复制 | 不支持，使用分支或 REST API |
| 事务隔离 | 快照隔离（对应 PG 的 REPEATABLE READ） |
| 可串行化 | 语法接受但降级为 Repeatable Read |

---

## 💡 六、设计启发点

### 1. **"能力内置，而非外挂"**
DB9 的核心哲学是将 Agent 需要的能力（embeddings、文件、HTTP、cron）编译进数据库，而不是作为外部服务。这减少了：
- 服务间网络调用
- API 密钥管理复杂度
- 故障点数量

**启发：** 在设计数据库产品时，考虑目标工作负载的完整需求链，将高频依赖的能力内化。

### 2. **"标准协议优先"**
DB9 完全兼容 PostgreSQL wire protocol，这意味着：
- 任何 Postgres 客户端都能连接
- 所有 ORM（Prisma、Drizzle、TypeORM、SQLAlchemy 等）开箱即用
- LLM 已熟悉 SQL，无需学习专有查询语言

**启发：** 利用现有生态的惯性，降低采用门槛。

### 3. **"匿名优先，渐进式认证"**
- 首次使用无需注册，自动创建匿名账户
- 达到限制时引导 SSO 认领
- 凭证本地存储复用

**启发：** 降低初始摩擦，让用户体验核心价值后再要求承诺。

### 4. **"分支即原语"**
数据库分支不是事后添加的功能，而是核心设计：
- 轻量级拷贝，写时共享
- 包含数据、文件、cron、权限、扩展
- 支持预览环境、schema 实验、回滚点

**启发：** 将开发工作流的核心需求（实验、回滚、隔离）提升到原语级别。

### 5. **"SQL 作为编排层"**
DB9 让 SQL 成为编排层：
- 在 SQL 中调用 HTTP API
- 在 SQL 中读写文件
- 在 SQL 中生成 embeddings
- 在 SQL 中调度任务

**启发：** SQL 不仅是查询语言，也可以是工作流编排语言。

### 6. **"Agent 技能安装"**
`db9 onboard` 命令将 DB9 安装为 AI Agent 的"技能"：
- 教会 Agent 如何使用 DB9 CLI
- 支持多个 Agent 平台（Claude Code、Codex、OpenCode）
- 支持用户级和项目级安装

**启发：** 将产品深度集成到 Agent 的工作流中，让 Agent"学会"使用你的产品。

### 7. **"控制平面/数据平面分离"**
- 控制平面：REST API，管理生命周期
- 数据平面：pgwire 协议，执行 SQL
- 客户端工具与两者对话

**启发：** 清晰的控制/数据分离，便于独立扩展和演进。

---

## 📊 七、竞争对比

| 特性 | DB9 | Neon | Supabase |
|------|-----|------|----------|
| 目标用户 | AI Agent | 开发者 | 全栈开发者 |
| 即时配置 | ✓ 秒级 | ✓ | ✓ |
| 内置 Embeddings | ✓ | ✗ | ✗ |
| 内置文件系统 | ✓ | ✗ | ✓ (Storage) |
| HTTP from SQL | ✓ | ✗ | ✗ |
| 数据库分支 | ✓ | ✓ | ✗ |
| 内置 Cron | ✓ | ✗ | ✓ |
| 匿名使用 | ✓ | ✗ | ✗ |
| Agent 技能 | ✓ | ✗ | ✗ |
| 自托管 | ✗ | ✗ | ✓ |

---

## 🎯 八、对数据库产品设计的启示

### 1. 垂直整合 > 水平组合
DB9 选择将 Agent 工作流需要的能力垂直整合到数据库层，而不是让用户自己组合多个服务。这种设计：
- **优点：** 减少集成复杂度、降低延迟、简化运维
- **代价：** 系统复杂度集中在数据库团队

### 2. 工作负载驱动设计
DB9 不是"通用 Postgres"，而是明确为 AI Agent 工作负载优化：
- 秒级数据库创建/销毁
- 内置向量搜索和 embeddings
- 文件与数据同层访问
- 分支支持实验性操作

**启示：** 与其做通用数据库，不如为特定工作负载深度优化。

### 3. 开发者体验即产品
- CLI 优先设计
- 一键安装
- 详尽的文档
- Agent 技能支持

**启示：** 在功能同质化的时代，DX 是差异化关键。

### 4. 安全边界内置
HTTP 扩展的安全限制（HTTPS only、SSRF 防护、速率限制）是编译时内置的，而不是文档建议。

**启示：** 将安全最佳实践编码到产品中，而非依赖用户遵循文档。

---

## 🔗 参考链接

- 官网：https://db9.ai
- 文档：https://db9.ai/docs
- Discord：https://discord.gg/5P3RuyZCgs
- HN 讨论：https://news.ycombinator.com/item?id=xxx（Postgres with Builtin File Systems）

---

*报告生成：2026-03-20 | 调研执行：Andy*
