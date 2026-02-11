# Building Efficient Agent Memory with SeekDB: From "Full Context" to "Smart Retrieval"

> A practical guide to implementing vector-based memory for AI Agents using seekdb-js + Qwen3 Max via OpenRouter.

---

## The Problem: Why Traditional Memory Systems Waste Tokens

When building AI Agents with LangGraph or custom frameworks, persistent memory is essential. But there's a critical inefficiency in traditional approaches: **they pass the entire conversation history to the LLM on every request**, even when most of it is irrelevant.

**Real-world impact:**
- Token costs skyrocket (10-20x the actual need)
- Response latency increases
- Model attention gets diluted, degrading answer quality

**Example**: When a user simply says "hello", the system might stuff 50 previous messages into the prompt. Most are noise.

**SeekDB's solution**: Store messages as embedding vectors and retrieve only semantically relevant context using similarity search.

---

## Core Concepts

### 1. Embedding Vectors

Computers don't understand text—they understand numbers. Embeddings convert text into numerical vectors that capture semantic meaning.

- Example: "I love AI tutorials" → `[0.12, -0.45, 0.88, ...]`
- Qwen3 Embedding generates 1024-dimensional vectors
- Semantically similar sentences have vectors that are "close" in high-dimensional space

### 2. Vector Similarity Search

Instead of keyword matching, we compare vector distances. Two sentences about "machine learning" will have similar embeddings, even if they use different words.

**Why SeekDB?**
- SQLite-based: zero-config, single-file, easy deployment
- Native vector support with similarity search
- 100x lighter than PostgreSQL + PGVector

### 3. Cosine Similarity

The metric we use to compare vectors:
```
similarity = 1 - cosine_distance
```

- `1.0` = identical meaning
- `0.0` = orthogonal/unrelated
- `>0.7` = typically considered highly relevant

---

## Two Retrieval Strategies

### Strategy 1: Fixed-Count (Limit-based)

Always return the top-N most similar messages.

```javascript
const results = await collection.query({
  queryTexts: userQuery,
  nResults: 5
});
```

**Pros**: Predictable token costs, simple implementation
**Cons**: May include low-relevance messages just to hit the count

### Strategy 2: Threshold-based

Only return messages above a similarity threshold (e.g., ≥ 0.75).

```javascript
const memories = results.filter(r => 
  (1 - r.distance) >= threshold
);
```

**Pros**: Dynamic context length, filters irrelevant history automatically
**Cons**: Variable result count, requires tuning the threshold

**Recommendation**: Use hybrid—threshold first, then limit.

---

## Implementation with seekdb-js

### Setup

```bash
npm install seekdb
```

### Database Connection

```javascript
import { SeekdbClient } from 'seekdb';

const client = new SeekdbClient({
  host: '127.0.0.1',
  port: 2881,
  user: 'root',
  password: '',
  database: 'test',
});

// Create collection with Qwen3 embeddings
const collection = await client.createCollection({
  name: 'chat_memory',
  configuration: {
    dimension: 1024,
    distance: 'cosine',
  },
});
```

### The AgentMemory Class

```javascript
class AgentMemory {
  constructor(collection) {
    this.collection = collection;
  }

  async store(role, message) {
    await this.collection.add({
      ids: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      documents: message,
      metadatas: { role, timestamp: Date.now() },
    });
  }

  async recall(query, options = {}) {
    const { strategy = 'threshold', threshold = 0.75, limit = 5 } = options;
    
    const results = await this.collection.query({
      queryTexts: query,
      nResults: strategy === 'threshold' ? 50 : limit,
    });

    // Convert distances to similarities
    const memories = results.ids[0].map((id, i) => ({
      id,
      role: results.metadatas[0][i].role,
      message: results.documents[0][i],
      similarity: 1 - (results.distances[0][i] || 0),
    }));

    if (strategy === 'threshold') {
      return memories.filter(m => m.similarity >= threshold);
    }
    return memories.slice(0, limit);
  }
}
```

### Complete Agent Example

```javascript
import { OpenRouterClient } from './OpenRouterClient.js';

const llm = new OpenRouterClient({
  apiKey: process.env.OPENROUTER_API_KEY,
  model: 'qwen/qwen3-max'
});

const memory = new AgentMemory(collection);

async function chat(userMessage) {
  // 1. Retrieve relevant context
  const context = await memory.recall(userMessage, {
    strategy: 'threshold',
    threshold: 0.75
  });

  // 2. Build prompt with only relevant history
  const systemPrompt = context.length > 0
    ? `Relevant context:\n${context.map(c => 
        `${c.role}: ${c.message}`).join('\n')}`
    : 'You are a helpful assistant.';

  // 3. Call LLM with filtered context
  const response = await llm.chat([
    { role: 'system', content: systemPrompt },
    { role: 'user', content: userMessage }
  ]);

  // 4. Store interaction
  await memory.store('user', userMessage);
  await memory.store('assistant', response);

  return response;
}
```

---

## Cost Comparison

Tested with 995 stored messages:

| Approach | Messages Passed | Token Cost | Latency |
|----------|----------------|------------|---------|
| Full Context | 995 (all) | 100% baseline | Slow |
| SeekDB + Limit | 5 | ~5% (95% saved) | Fast |
| SeekDB + Threshold | 18 (dynamic) | ~15% (85% saved) | Fast |

**Monthly savings** (10k sessions, 50 msgs/session):
- Qwen3 Max at $1.6/M tokens
- Full context: ~$1,600
- SeekDB approach: ~$80
- **Savings: $1,520/month (95%)**

---

## Why SeekDB + OpenRouter?

| Feature | PostgreSQL+PGVector+OpenAI | SeekDB+OpenRouter |
|---------|---------------------------|-------------------|
| Deployment | Complex | Zero-config |
| Size | Hundreds of MB | <5 MB |
| Startup | Seconds | Milliseconds |
| Model choice | Limited | 300+ models |
| China access | Requires proxy | Direct access |
| Cost | GPT-4: $5/M | Qwen3: $1.6/M |

---

## Key Takeaways

1. **Memory isn't about storing everything—it's about retrieving the right things**
2. Vector similarity > keyword matching for semantic understanding
3. Threshold-based retrieval is smarter but requires tuning
4. Qwen3 Max + SeekDB is the optimal stack for cost-effective, high-quality Agent memory

**Full code**: https://github.com/kejun/seekdb-agent-memory

---

*SeekDB makes every line of code serve product value, not infrastructure.*
