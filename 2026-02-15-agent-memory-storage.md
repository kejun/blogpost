# 生产级 Agent 记忆存储：我遇到的坑和选型思路

上个月把一个 Claude Agent 部署到生产环境，跑了三周，踩了不少记忆存储的坑。写出来给大家参考。

## 第一个问题：向量库不是万能的

初始方案：所有对话历史全塞向量库，语义搜索召回。

跑了两周发现几个问题：

1. **精确查询太慢**
   用户问「上次那个配置参数是多少」，向量搜索返回一堆语义相似但无关的结果，LLM 还得重新理解上下文。

2. **事务不一致**
   更新用户偏好时，向量索引和业务数据不同步，导致同一轮对话里记忆对不上。

3. **存储成本爆炸**
   一天 5000 条对话，向量库账单涨得吓人，但其实 80% 只需要精确存储，不需要语义搜索。

## 我的解决方案：双写策略

现在改成两层存储：

```typescript
import { SeekDB } from '@oceanbase/seekdb';

const db = new SeekDB({
  // 向量搜索：语义相似度
  // 关系存储：精确查询 + 事务
});

async function storeAgentMemory(params: {
  agentId: string;
  userId: string;
  type: 'conversation' | 'preference' | 'task';
  content: string;
  embedding?: number[];
}) {
  // 1. 语义内容 → 向量库（异步，不阻塞主流程）
  if (params.embedding) {
    await db.hybridSearch.index({
      vector: params.embedding,
      metadata: {
        agentId: params.agentId,
        type: params.type,
        timestamp: Date.now()
      }
    });
  }

  // 2. 核心数据 → 关系表（事务保证一致性）
  await db.transaction(async (trx) => {
    const memoryId = await trx.insert('agent_memories', {
      agent_id: params.agentId,
      user_id: params.userId,
      memory_type: params.type,
      content: params.content,
      metadata: JSON.stringify({
        embeddingIndexed: !!params.embedding,
        indexedAt: Date.now()
      }),
      created_at: new Date(),
      updated_at: new Date()
    });

    // 用户偏好需要实时查询，单独特存一张表
    if (params.type === 'preference') {
      await trx.insert('user_preferences', {
        user_id: params.userId,
        agent_id: params.agentId,
        preferences: params.content,
        last_updated: new Date()
      }, {
        onConflict: 'user_id, agent_id',
        updateFields: ['preferences', 'last_updated']
      });
    }

    return memoryId;
  });
}
```

**效果：**
- 精确查询走 SQL，响应时间从 200ms 降到 20ms
- 偏好更新原子化，不会出现记忆冲突
- 存储成本降了 60%

## 第二个问题：MCP 服务器连接的生产级坑

之前直接让 Agent 连数据库 MCP 服务器，DEV Community 那篇 MCP 安全风险文章里说的问题全遇到了：

**1. 认证蔓延**
   每个 MCP 服务器独立 token，5 个服务 5 套认证，轮换时经常有服务挂掉。

**2. 权限失控**
   Agent 第一次连数据库时把整个表权限放出去了，后来才发现。

**3. 完全没有 observability**
   Agent 调了什么查询、返回什么数据，一概不知，出了问题没法复盘。

现在加了 MCP 网关：

```json
// .mcp/gateway.json
{
  "mcpServers": {
    "memory-gateway": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-gateway", "--config", "./gateway-config.yaml"],
      "env": {
        "GATEWAY_AUTH": " centralized-auth-provider"
      }
    }
  }
}

// gateway-config.yaml
auth:
  strategy: "oauth2"
  providers:
    - id: "seekdb"
      type: "oauth2"
      client_id: "${SEEKDB_CLIENT_ID}"
      client_secret: "${SEEKDB_CLIENT_SECRET}"
      
access_policies:
  - resource: "agent_memories"
    permissions: ["read", "write"]
    conditions:
      - user.premium_tier == true
      
audit:
  enabled: true
  sink: "cloudwatch"
```

**变化：**
- 认证统一管，token 自动刷新
- 细粒度权限控制，具体到表和操作
- 每一次调用都有审计日志

## 第三个问题：记忆分层

后来加了多 Agent 协作，发现记忆需要分层：

| 层级 | 存储方式 | 生命周期 | 用途 |
|-----|---------|---------|-----|
| 工作记忆 | LLM context | 单次对话 | 当前任务上下文 |
| 会话记忆 | Redis + 关系表 | 24小时 | 跨轮次对话 |
| 长期记忆 | 向量库 + 关系表 | 永久 | 用户偏好、历史模式 |

代码层面：

```typescript
// 工作记忆：直接塞 context
async function buildWorkingMemory(sessionId: string) {
  const recentMessages = await redis.lrange(`session:${sessionId}:messages`, -10, -1);
  return recentMessages.map(JSON.parse);
}

// 会话记忆：24小时过期
async function storeSessionMemory(sessionId: string, message: Message) {
  await redis.rpush(`session:${sessionId}:messages`, JSON.stringify(message));
  await redis.expire(`session:${sessionId}:messages`, 86400);
}

// 长期记忆：持久化存储
async function consolidateToLongTerm(sessionId: string, summary: string) {
  await storeAgentMemory({
    agentId: currentAgent,
    userId: currentUser,
    type: 'conversation',
    content: summary,
    embedding: await generateEmbedding(summary)
  });
}
```

## 踩坑总结

1. **别一股脑全塞向量库** — 精确查询和事务场景先用关系数据库兜底
2. **生产环境 MCP 必须加网关** — 安全和可观测不是「以后再加」
3. **记忆分层越早做越好** — 后期重构比重写还麻烦
4. **事务是底线** — 用户偏好更新失败比搜索慢更致命

你们生产环境的 Agent 记忆方案是什么样的？有什么坑或者更好的实践？

---

**标签：** [AI Agent] [MCP] [数据库] [记忆存储] [实战]
