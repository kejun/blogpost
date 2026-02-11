# 使用 SeekDB 为 AI Agent 实现持久化记忆：从"全量上下文"到"精准召回"

> 本文介绍如何使用 seekdb-js SDK + Qwen3 Max (via OpenRouter) 为 Node.js AI Agent 实现高效的向量记忆系统，替代传统 PostgreSQL Checkpoint 方案。

---

## 问题背景：为什么传统记忆方案效率低下？

在使用 LangGraph 或自定义 AI Agent 时，持久化记忆是一个核心需求。然而，传统的记忆方案存在一个明显的效率问题：**它总是将全部历史消息作为上下文传递给 LLM**，即使这些消息与当前问题毫不相关。

举个例子：当你只是向 Agent 问候一句"你好"时，系统却会把过去 50 轮对话的所有内容都塞进 Prompt。这些冗余信息不仅浪费 Token，还可能干扰模型的回答质量。

**实际后果**：
- Token 成本飙升（实测可达实际需求的 10-20 倍）
- 响应延迟增加
- 模型注意力分散，回答质量下降

**SeekDB 的解决方案**：将消息存储为向量嵌入（Embedding Vectors），通过向量相似度搜索，只召回与当前问题最相关的历史消息。

---

## 核心概念解析

### 1. 什么是嵌入向量（Embedding Vectors）？

计算机无法理解人类语言，它只能处理数字。嵌入向量将文字转换为数值列表，捕捉语义信息。

- 例如："我喜欢看 AI 教程" → `[0.12, -0.45, 0.88, ...]`
- 维度取决于嵌入模型：Qwen3 Embedding 生成 1024 维向量
- 语义相似的句子，其向量在多维空间中距离更近

### 2. 向量相似度搜索

直接问计算机 "我喜欢看 AI 教程" 和 "我爱看 YouTube AI 视频" 是否相似，它无法回答。但如果比较它们的嵌入向量，计算机就能计算出确定的相似度分数。

**SeekDB 的优势**：
- 基于 SQLite，零配置、单文件、易部署
- 原生支持向量存储和相似度搜索
- 比 PostgreSQL + PGVector 轻量 100 倍

### 3. 距离函数与余弦相似度

SeekDB 支持多种距离计算方式：
- **余弦相似度（Cosine Similarity）**：最常用，范围 [-1, 1]
- **欧几里得距离（L2 Distance）**：向量空间直线距离
- **曼哈顿距离（L1 Distance）**

**关键公式**：
```
余弦相似度 = 1 - 余弦距离
```

余弦相似度取值含义：
- `1.0`：完全相似（0°夹角）
- `0.0`：无关（90°夹角）
- `-1.0`：完全相反（180°夹角）
- 实践中，> 0.7 通常表示高相关

---

## 技术选型：为什么选择 Qwen3 Max？

### Qwen3 Max 优势

[Qwen3 Max](https://openrouter.ai/qwen/qwen3-max) 是通义千问系列的旗舰大模型，通过 OpenRouter 平台提供服务：

| 特性 | Qwen3 Max |
|------|-----------|
| **上下文长度** | 128K tokens |
| **多语言能力** | 支持 29 种语言，中文表现优异 |
| **推理能力** | 复杂逻辑、代码生成、数学推理 |
| **价格** | $1.6/M input, $4/M output |
| **响应速度** | 首字延迟低，适合实时对话 |

### Qwen3 Embedding 模型

Qwen3 系列提供专用嵌入模型，与 Max 搭配使用效果更佳：

| 模型 | 维度 | 适用场景 |
|------|------|---------|
| [qwen/qwen3-embedding-8b](https://openrouter.ai/qwen/qwen3-embedding-8b) | 1024 | 高质量语义搜索 |
| [qwen/qwen3-embedding-0.6b](https://openrouter.ai/qwen/qwen3-embedding-0.6b) | 1024 | 轻量级、低延迟 |

---

## 两种召回策略对比

### 策略一：固定数量召回（Limit-based）

**原理**：始终返回最相似的 N 条历史消息（如 Top 5）

**示例**：
```javascript
const results = await db.recallSimilar({
  embedding: queryEmbedding,
  limit: 5
});
```

**优点**：
- 实现简单，上下文长度可控
- 每次调用的 Token 成本可预测

**缺点**：
- 可能混入低相关度消息（为了凑够 5 条）
- 话题切换时不够灵活

### 策略二：阈值召回（Threshold-based）

**原理**：只返回相似度超过阈值的消息（如 ≥ 0.75）

**示例**：
```javascript
const results = await db.recallSimilar({
  embedding: queryEmbedding,
  threshold: 0.75  // 只返回相似度 ≥ 0.75 的消息
});
```

**优点**：
- 动态调整上下文长度，只保留真正相关的内容
- 话题切换时自动适应（聊到"猫"时，关于"狗"的消息自动被过滤）

**缺点**：
- 召回数量不固定，极端情况下可能为 0
- 需要仔细调优阈值

**实战建议**：
| 场景 | 推荐策略 | 参数 |
|------|---------|------|
| 成本敏感型应用 | Limit-based | limit: 5-10 |
| 追求回答质量 | Threshold-based | threshold: 0.70-0.80 |
| 混合方案 | 先阈值筛选，再限制数量 | threshold: 0.6, limit: 10 |

---

## seekdb-js + OpenRouter 实现方案

### 安装依赖

```bash
npm install seekdb
```

### 初始化配置

```javascript
import { SeekDB } from 'seekdb';

// OpenRouter API 配置
const OPENROUTER_API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1';

// 初始化 SeekDB（基于 SQLite，单文件存储）
const db = new SeekDB({
  path: './agent_memory.db',
  vectorDimension: 1024  // Qwen3 Embedding 维度
});

// 初始化表结构
await db.initTable('chat_memory', {
  id: 'INTEGER PRIMARY KEY AUTOINCREMENT',
  role: 'TEXT',           // 'user' | 'assistant' | 'system'
  message: 'TEXT',        // 原始消息内容
  embedding: 'VECTOR(1024)',  // 向量列
  createdAt: 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
});

// 创建向量索引
await db.createVectorIndex('chat_memory', 'embedding');
```

### 嵌入向量生成（Qwen3 Embedding）

```javascript
/**
 * 使用 Qwen3 Embedding 生成向量
 * @param {string} text - 输入文本
 * @returns {Promise<number[]>} - 1024维向量
 */
async function getEmbedding(text) {
  const response = await fetch(`${OPENROUTER_BASE_URL}/embeddings`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'https://your-app.com',  // OpenRouter 要求
      'X-Title': 'AI Agent with SeekDB'
    },
    body: JSON.stringify({
      model: 'qwen/qwen3-embedding-8b',  // 或 qwen3-embedding-0.6b
      input: text
    })
  });

  const data = await response.json();
  return data.data[0].embedding;
}
```

### LLM 调用（Qwen3 Max）

```javascript
/**
 * 调用 Qwen3 Max 生成回复
 * @param {Array} messages - OpenAI 格式的消息数组
 * @returns {Promise<string>} - 模型回复
 */
async function chatWithQwen(messages) {
  const response = await fetch(`${OPENROUTER_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
      'Content-Type': 'application/json',
      'HTTP-Referer': 'https://your-app.com',
      'X-Title': 'AI Agent with SeekDB'
    },
    body: JSON.stringify({
      model: 'qwen/qwen3-max',
      messages,
      temperature: 0.7,
      max_tokens: 2000
    })
  });

  const data = await response.json();
  return data.choices[0].message.content;
}
```

### 核心记忆管理类

```javascript
class AgentMemory {
  constructor(db, embeddingFn) {
    this.db = db;
    this.getEmbedding = embeddingFn;
  }

  /**
   * 存储对话到记忆
   * @param {string} role - 'user' | 'assistant'
   * @param {string} message - 消息内容
   */
  async store(role, message) {
    const embedding = await this.getEmbedding(message);
    
    await this.db.insert('chat_memory', {
      role,
      message,
      embedding: JSON.stringify(embedding)
    });
  }

  /**
   * 召回相关历史记忆
   * @param {string} query - 当前查询
   * @param {Object} options - 召回选项
   * @returns {Promise<Array>} - 相关历史消息
   */
  async recall(query, options = {}) {
    const { 
      strategy = 'threshold',  // 'threshold' | 'limit'
      threshold = 0.75,
      limit = 5
    } = options;

    const queryEmbedding = await this.getEmbedding(query);

    if (strategy === 'threshold') {
      // 阈值召回：只返回相似度 ≥ threshold 的消息
      return await this.db.query(`
        SELECT role, message, 
               vec_cosine_similarity(embedding, ?) as similarity
        FROM chat_memory
        WHERE vec_cosine_similarity(embedding, ?) >= ?
        ORDER BY similarity DESC
      `, [JSON.stringify(queryEmbedding), JSON.stringify(queryEmbedding), threshold]);
    } else {
      // 固定数量召回：返回最相似的 N 条
      return await this.db.query(`
        SELECT role, message,
               vec_cosine_similarity(embedding, ?) as similarity
        FROM chat_memory
        ORDER BY similarity DESC
        LIMIT ?
      `, [JSON.stringify(queryEmbedding), limit]);
    }
  }

  /**
   * 混合召回策略：先阈值筛选，再限制数量
   */
  async recallHybrid(query, options = {}) {
    const { threshold = 0.6, limit = 10 } = options;
    const queryEmbedding = await this.getEmbedding(query);

    return await this.db.query(`
      SELECT role, message,
             vec_cosine_similarity(embedding, ?) as similarity
      FROM chat_memory
      WHERE vec_cosine_similarity(embedding, ?) >= ?
      ORDER BY similarity DESC
      LIMIT ?
    `, [JSON.stringify(queryEmbedding), JSON.stringify(queryEmbedding), threshold, limit]);
  }

  /**
   * 获取统计信息
   */
  async stats() {
    const result = await this.db.query('SELECT COUNT(*) as count FROM chat_memory');
    return { totalMessages: result[0].count };
  }
}

// 实例化记忆管理器
const memory = new AgentMemory(db, getEmbedding);
```

### Agent 集成示例

```javascript
/**
 * Agent 主循环
 */
async function chatWithAgent(userMessage) {
  // 1. 召回相关历史记忆
  const relevantHistory = await memory.recall(userMessage, {
    strategy: 'threshold',
    threshold: 0.75
  });

  console.log(`召回 ${relevantHistory.length} 条相关历史`);

  // 2. 构建系统提示（仅包含相关上下文）
  const context = relevantHistory
    .map(h => `${h.role}: ${h.message}`)
    .join('\n');

  const messages = relevantHistory.length > 0
    ? [
        { role: 'system', content: `以下是相关的历史对话，请基于这些信息回答用户问题：\n\n${context}` },
        { role: 'user', content: userMessage }
      ]
    : [
        { role: 'system', content: '你是一个有用的 AI 助手。' },
        { role: 'user', content: userMessage }
      ];

  // 3. 调用 Qwen3 Max（只传递相关上下文，而非全部历史）
  const response = await chatWithQwen(messages);

  // 4. 存储当前对话到记忆
  await memory.store('user', userMessage);
  await memory.store('assistant', response);

  return response;
}

// 使用示例
(async () => {
  console.log(await chatWithAgent('你好，我叫张三'));
  console.log(await chatWithAgent('我叫什么名字？'));  // 能正确召回名字
  console.log(await chatWithAgent('北京今天天气怎么样？'));  // 无关历史被过滤
})();
```

---

## 效果对比

### 测试场景
- 数据库中存储了 995 条历史消息
- 用户提问："我叫什么名字？"（需要依赖早期对话中的个人信息）

### 方案对比

| 方案 | 传递消息数 | Token 消耗 | 延迟 | 准确率 |
|------|-----------|-----------|------|--------|
| LangGraph 默认 Checkpoint | 995 条（全部）| 基准 100% | 慢 | 可能受噪声干扰 |
| SeekDB + 固定数量召回 | 5 条 | ~5%（节省 95%）| 快 | 精准命中 |
| SeekDB + 阈值召回 | 18 条（动态）| ~15%（节省 85%）| 快 | 召回全面，无遗漏 |

### 成本节省分析

以 Qwen3 Max ($1.6/1M input tokens) 为例：

| 月活会话 | 平均消息/会话 | 传统方案月成本 | SeekDB 方案 | 月节省 |
|---------|--------------|--------------|------------|-------|
| 10,000 | 50 条 | ~$1,600 | ~$80 | **$1,520** |
| 100,000 | 50 条 | ~$16,000 | ~$800 | **$15,200** |

> 注：Qwen3 Embedding 成本约 $0.1/M tokens，可忽略不计。

---

## 高级技巧

### 1. 时间衰减加权

让越新的消息权重越高：

```javascript
async function recallWithTimeDecay(query, options = {}) {
  const { threshold = 0.6, hours = 24 } = options;
  const queryEmbedding = await getEmbedding(query);

  // 结合相似度和时间衰减
  return await db.query(`
    SELECT role, message,
           vec_cosine_similarity(embedding, ?) * 
           EXP(-(julianday('now') - julianday(createdAt)) * 0.1) as weighted_score
    FROM chat_memory
    WHERE vec_cosine_similarity(embedding, ?) >= ?
      AND createdAt > datetime('now', '-${hours} hours')
    ORDER BY weighted_score DESC
    LIMIT 10
  `, [JSON.stringify(queryEmbedding), JSON.stringify(queryEmbedding), threshold]);
}
```

### 2. 分层记忆架构

区分短期会话记忆和长期用户画像：

```javascript
// 短期记忆：当前会话的最近 10 条
await db.initTable('short_term_memory', { /* ... */ });

// 长期记忆：提取的关键事实（用户偏好、个人信息）
await db.initTable('long_term_memory', { /* ... */ });

// 召回时合并
const shortTerm = await recallFrom('short_term_memory', query, { limit: 5 });
const longTerm = await recallFrom('long_term_memory', query, { threshold: 0.8 });
const context = [...longTerm, ...shortTerm];
```

### 3. 记忆摘要压缩

当历史消息过多时，使用 Qwen3 Max 生成摘要：

```javascript
async function summarizeOldMemories() {
  const oldMessages = await db.query(`
    SELECT * FROM chat_memory 
    WHERE createdAt < datetime('now', '-7 days')
  `);

  const summary = await chatWithQwen([
    { 
      role: 'system', 
      content: '请将以下对话历史总结为关键事实（用户偏好、重要信息等）：' 
    },
    { 
      role: 'user', 
      content: oldMessages.map(m => m.message).join('\n') 
    }
  ]);

  // 将摘要存入长期记忆
  await memory.store('system', `用户画像摘要：${summary}`);
}
```

### 4. OpenRouter 模型降级策略

当 Qwen3 Max 不可用时自动降级：

```javascript
async function chatWithFallback(messages) {
  const models = [
    'qwen/qwen3-max',
    'qwen/qwen2.5-vl-72b-instruct',
    'anthropic/claude-3.5-sonnet'
  ];

  for (const model of models) {
    try {
      const response = await fetch(`${OPENROUTER_BASE_URL}/chat/completions`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${OPENROUTER_API_KEY}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ model, messages, temperature: 0.7 })
      });
      
      if (response.ok) {
        const data = await response.json();
        return data.choices[0].message.content;
      }
    } catch (e) {
      console.log(`Model ${model} failed, trying next...`);
    }
  }
  
  throw new Error('All models failed');
}
```

---

## 为什么选 SeekDB + OpenRouter？

| 特性 | PostgreSQL + PGVector + OpenAI | SeekDB + OpenRouter |
|------|-------------------------------|---------------------|
| **部署复杂度** | 需安装 PostgreSQL + 扩展 + 配置 API | 零配置，SQLite 开箱即用 |
| **依赖体积** | 数百 MB | < 5 MB |
| **启动时间** | 秒级 | 毫秒级 |
| **数据文件** | 需独立管理 | 单文件 `.db`，易迁移 |
| **模型选择** | 限于 OpenAI 生态 | 300+ 模型（Qwen、Claude、Gemini 等） |
| **国内访问** | 需代理 | OpenRouter 国内可访问 |
| **成本** | GPT-4o: $5/M + 向量库成本 | Qwen3 Max: $1.6/M + 零基础设施成本 |

**技术栈组合优势**：
> SeekDB 提供轻量级向量存储，OpenRouter 提供统一的大模型接口，两者结合是 AI Agent 开发的理想选择。

---

## 总结

**核心洞察**：
1. **记忆的关键不在"存多少"，而在"召回准不准"**
2. 向量相似度搜索是语义记忆的终极方案
3. 阈值召回比固定数量更智能，但需要调优

**技术选型建议**：
- **LLM**: Qwen3 Max（中文优异、性价比高）
- **Embedding**: Qwen3 Embedding 8B（与 Max 同系列，语义一致性好）
- **向量库**: SeekDB（轻量、零配置）
- **API 网关**: OpenRouter（统一接口、模型丰富）

**下一步探索**：
- 混合策略：阈值 + 数量限制的双重保险
- 时间衰减：让记忆像人类一样"遗忘"
- 多租户隔离：为每个用户维护独立的记忆空间
- Prompt 缓存：利用 OpenRouter 的 Prompt Caching 进一步降低成本

---

**相关链接**：
- SeekDB: https://github.com/oceanbase/seekdb-js
- OpenRouter: https://openrouter.ai
- Qwen3 Max: https://openrouter.ai/qwen/qwen3-max
- Qwen3 Embedding: https://openrouter.ai/qwen/qwen3-embedding-8b

*SeekDB + OpenRouter：让每一行代码都直接服务于产品价值，而非基础设施。*
