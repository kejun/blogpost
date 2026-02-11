# 使用 SeekDB 为 AI Agent 实现持久化记忆：从"全量上下文"到"精准召回"

> 本文介绍如何使用 seekdb-js SDK + Qwen3 Max (via OpenRouter) 为 Node.js AI Agent 实现高效的向量记忆系统。
> 
> **完整代码仓库**: https://github.com/kejun/seekdb-agent-memory

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
- Qwen3 Embedding 8B 生成 **4096 维**向量（注意：不是 1024 维）
- 语义相似的句子，其向量在多维空间中距离更近

### 2. 向量相似度搜索

直接问计算机 "我喜欢看 AI 教程" 和 "我爱看 YouTube AI 视频" 是否相似，它无法回答。但如果比较它们的嵌入向量，计算机就能计算出确定的相似度分数。

**SeekDB 的优势**：
- 基于 OceanBase，支持大规模向量数据
- 原生支持向量存储和相似度搜索
- 比 PostgreSQL + PGVector 更易部署

### 3. 距离函数与余弦相似度

SeekDB 支持多种距离计算方式：
- **余弦相似度（Cosine Similarity）**：最常用，范围 [-1, 1]
- **欧几里得距离（L2 Distance）**：向量空间直线距离

**关键公式**：
```
余弦相似度 = 1 - 余弦距离
```

余弦相似度取值含义：
- `1.0`：完全相似（0°夹角）
- `0.0`：无关（90°夹角）
- 实践中，> 0.7 通常表示高相关

---

## 技术选型

### Qwen3 Max + Qwen3 Embedding

| 组件 | 模型 | 维度 | 说明 |
|------|------|------|------|
| LLM | qwen/qwen3-max | - | 128K 上下文，$1.6/M input |
| Embedding | qwen/qwen3-embedding-8b | **4096** | 高质量，与 Max 搭配效果佳 |
| Embedding | qwen/qwen3-embedding-0.6b | 1024 | 轻量级，延迟更低 |

---

## 两种召回策略对比

### 策略一：固定数量召回（Limit-based）

始终返回最相似的 N 条历史消息。

**适用场景**：成本敏感型应用，需要可预测的 Token 成本。

### 策略二：阈值召回（Threshold-based）

只返回相似度超过阈值的消息（如 ≥ 0.75）。

**适用场景**：追求回答质量，愿意接受动态上下文长度。

### 策略三：混合召回（推荐）

先阈值筛选，再限制数量。兼顾质量和可控性。

---

## 完整实现代码

> 以下代码来自实际仓库：https://github.com/kejun/seekdb-agent-memory

### 1. 安装依赖

```bash
npm install seekdb @seekdb/qwen dotenv
```

### 2. 环境变量配置（.env）

```bash
# OpenRouter API Key
OPENROUTER_API_KEY=your_key_here

# SeekDB 连接配置
SEEKDB_HOST=127.0.0.1
SEEKDB_PORT=2881
SEEKDB_USER=root
SEEKDB_PASSWORD=
SEEKDB_DATABASE=test

# Embedding 配置
EMBEDDING_MODEL=qwen/qwen3-embedding-8b
EMBEDDING_DIMENSION=4096  # 8B 模型是 4096 维

# LLM 配置
LLM_MODEL=qwen/qwen3-max
```

### 3. 数据库连接配置

```javascript
// src/config/database.js
import { SeekdbClient } from 'seekdb';
import dotenv from 'dotenv';

dotenv.config();

/**
 * 创建 SeekDB 客户端
 */
export async function createClient() {
  return new SeekdbClient({
    host: process.env.SEEKDB_HOST || '127.0.0.1',
    port: parseInt(process.env.SEEKDB_PORT || '2881'),
    user: process.env.SEEKDB_USER || 'root',
    password: process.env.SEEKDB_PASSWORD || '',
    database: process.env.SEEKDB_DATABASE || 'test',
  });
}

/**
 * 获取 Embedding 维度（支持环境变量配置）
 */
export function getEmbeddingDimension() {
  const DEFAULT_DIMENSION = 4096;
  const raw = process.env.EMBEDDING_DIMENSION;
  
  if (!raw) return DEFAULT_DIMENSION;
  
  const dim = parseInt(raw, 10);
  if (!Number.isInteger(dim) || dim <= 0) {
    console.warn(`[config] Invalid EMBEDDING_DIMENSION="${raw}", using ${DEFAULT_DIMENSION}`);
    return DEFAULT_DIMENSION;
  }
  
  return dim;
}

/**
 * 自定义 OpenRouter Embedding 函数
 */
class OpenRouterEmbeddingFunction {
  constructor(config) {
    this.apiKey = config.apiKey;
    this.modelName = config.modelName;
    this.baseUrl = 'https://openrouter.ai/api/v1';
  }

  get name() {
    return 'openrouter-qwen-embedding';
  }

  async generate(texts) {
    const embeddings = [];

    for (const text of texts) {
      const response = await fetch(`${this.baseUrl}/embeddings`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'HTTP-Referer': process.env.APP_URL || 'http://localhost',
          'X-Title': process.env.APP_NAME || 'SeekDB Agent',
        },
        body: JSON.stringify({
          model: this.modelName,
          input: text,
        }),
      });

      if (!response.ok) {
        throw new Error(`Embedding API error: ${await response.text()}`);
      }

      const data = await response.json();
      embeddings.push(data.data[0].embedding);
    }

    return embeddings;
  }
}

export function createEmbeddingFunction() {
  return new OpenRouterEmbeddingFunction({
    apiKey: process.env.OPENROUTER_API_KEY,
    modelName: process.env.EMBEDDING_MODEL || 'qwen/qwen3-embedding-8b',
  });
}
```

### 4. 核心记忆管理类

```javascript
// src/memory/AgentMemory.js
import { createEmbeddingFunction, getEmbeddingDimension } from '../config/database.js';

export class AgentMemory {
  constructor(client, collectionName = 'chat_memory') {
    this.client = client;
    this.collectionName = collectionName;
    this.collection = null;
  }

  /**
   * 初始化集合
   */
  async init() {
    const embeddingFunction = createEmbeddingFunction();
    const embeddingDimension = getEmbeddingDimension();

    this.collection = await this.client.getOrCreateCollection({
      name: this.collectionName,
      configuration: {
        dimension: embeddingDimension,
        distance: 'cosine',
      },
      embeddingFunction,
    });

    console.log(`Collection ready: ${this.collection.name}`);
  }

  /**
   * 存储对话
   */
  async store(role, message) {
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    await this.collection.add({
      ids: id,
      documents: message,
      metadatas: { role, timestamp: Date.now() },
    });
  }

  /**
   * 召回相关历史
   * @param {string} query - 查询文本
   * @param {Object} options - 选项
   *   - strategy: 'threshold' | 'limit' | 'hybrid'
   *   - threshold: 相似度阈值（默认 0.75）
   *   - limit: 返回数量（默认 5）
   *   - role: 可选，按角色过滤（'user' | 'assistant'）
   */
  async recall(query, options = {}) {
    const {
      strategy = 'threshold',
      threshold = 0.75,
      limit = 5,
      role,  // 新增：角色过滤
    } = options;

    const where = role ? { role } : undefined;

    switch (strategy) {
      case 'threshold':
        return this._recallByThreshold(query, threshold, { where, limit });
      case 'limit':
        return this._recallByLimit(query, limit, { where });
      case 'hybrid':
        return this.recallHybrid(query, { threshold, limit, where });
      default:
        throw new Error(`Unknown strategy: ${strategy}`);
    }
  }

  async _recallByThreshold(query, threshold, options = {}) {
    const { where } = options;

    const results = await this.collection.query({
      queryTexts: query,
      where,
      nResults: 50,
    });

    const memories = [];
    const ids = results.ids[0];
    const documents = results.documents[0];
    const distances = results.distances?.[0] || [];
    const metadatas = results.metadatas?.[0] || [];

    for (let i = 0; i < ids.length; i++) {
      const similarity = 1 - (distances[i] || 0);

      if (similarity >= threshold) {
        memories.push({
          id: ids[i],
          role: metadatas[i]?.role || 'unknown',
          message: documents[i],
          similarity: parseFloat(similarity.toFixed(4)),
          timestamp: metadatas[i]?.timestamp,
        });
      }
    }

    return memories;
  }

  async _recallByLimit(query, limit, options = {}) {
    const { where } = options;

    const results = await this.collection.query({
      queryTexts: query,
      where,
      nResults: limit,
    });

    // 处理结果...
    return memories;
  }

  async recallHybrid(query, options = {}) {
    const { threshold = 0.6, limit = 10, where } = options;
    const thresholdResults = await this._recallByThreshold(query, threshold, { where, limit });
    return thresholdResults.slice(0, limit);
  }
}
```

### 5. 智能 Agent 示例

```javascript
// src/demo/chat-demo.js
import { createClient } from '../config/database.js';
import { AgentMemory } from '../memory/AgentMemory.js';
import { OpenRouterClient } from '../llm/OpenRouterClient.js';

export class ChatAgent {
  constructor() {
    this.memory = null;
    this.llm = new OpenRouterClient();
    this.client = null;
  }

  async init() {
    this.client = await createClient();
    this.memory = new AgentMemory(this.client, 'chat_memory');
    await this.memory.init();
  }

  async chat(userMessage) {
    // 智能检测：是否是询问个人信息的查询
    const isProfileQuery = /我(擅长|会|职业|工作|做什么|是什么|叫什么)/.test(userMessage);
    
    // 根据查询类型动态选择召回策略
    const recallOptions = isProfileQuery
      ? { strategy: 'limit', limit: 3, role: 'user' }  // 个人信息查询：只查用户说过的话
      : { strategy: 'threshold', threshold: 0.65, limit: 5, role: 'user' };

    // 召回相关历史
    const relevantHistory = await this.memory.recall(userMessage, recallOptions);

    // 构建上下文
    const context = relevantHistory
      .map(h => `${h.role}: ${h.message}`)
      .join('\n');

    const systemPrompt = relevantHistory.length > 0
      ? `以下是与当前问题相关的历史对话：\n${context}`
      : '你是一个有用的 AI 助手。';

    // 调用 LLM
    const response = await this.llm.chat([
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userMessage },
    ]);

    // 存储对话
    await this.memory.store('user', userMessage);
    await this.memory.store('assistant', response);

    return response;
  }
}

// 使用示例
const agent = new ChatAgent();
await agent.init();

await agent.chat('你好，我是程序员，喜欢写代码');
await agent.chat('我擅长什么？');  // 能回忆起"程序员"、"写代码"
await agent.chat('北京天气怎么样？');  // 无关历史被过滤
```

---

## 关键特性：角色过滤

在实际应用中，我们通常只关心**用户自己说过的话**，而不是 Agent 的回复。通过 `role` 参数可以实现这一点：

```javascript
// 只召回用户自己说过的话
const memories = await memory.recall('我叫什么名字？', {
  strategy: 'limit',
  limit: 3,
  role: 'user',  // 关键：只查 user 角色的消息
});
```

这在处理个人信息查询时特别有用，可以避免召回 Agent 的礼貌回复等无关内容。

---

## 效果对比

| 方案 | 传递消息数 | Token 消耗 | 延迟 |
|------|-----------|-----------|------|
| 全量上下文 | 995 条 | 基准 100% | 慢 |
| SeekDB + Limit | 5 条 | ~5%（节省 95%）| 快 |
| SeekDB + Threshold | 18 条（动态）| ~15%（节省 85%）| 快 |

---

## 总结

**核心洞察**：
1. **记忆的关键不在"存多少"，而在"召回准不准"**
2. 向量相似度搜索是语义记忆的终极方案
3. 根据查询类型动态选择召回策略效果更佳

**技术栈组合**：
- **Vector DB**: SeekDB (OceanBase)
- **LLM**: Qwen3 Max via OpenRouter
- **Embedding**: Qwen3 Embedding 8B (4096维)

**完整代码**: https://github.com/kejun/seekdb-agent-memory

