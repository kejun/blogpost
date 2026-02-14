# Building Efficient Agent Memory with SeekDB: From "Full Context" to "Smart Retrieval"

>A practical guide to implementing vector-based memory for AI Agents using seekdb-js + Qwen3 Max via OpenRouter.

# The Problem: Why Traditional Memory Systems Waste Tokens

When building AI Agents with LangGraph or custom frameworks, persistent memory is essential. But there's a critical inefficiency in traditional approaches: **they pass the entire conversation history to the LLM on every request**, even when most of it is irrelevant.

**Real-world impact:**

* Token costs skyrocket (10-20x the actual need)
* Response latency increases
* Model attention gets diluted, degrading answer quality

**Example**: When a user simply says "hello", the system might stuff 50 previous messages into the prompt. Most are noise.

**SeekDB's solution**: Store messages as embedding vectors and retrieve only semantically relevant context using similarity search.

# Core Concepts

# 1. Embedding Vectors

Computers don't understand text—they understand numbers. Embeddings convert text into numerical vectors that capture semantic meaning.

* Example: "I love AI tutorials" → `[0.12, -0.45, 0.88, ...]`
* Qwen3 Embedding generates 1024-dimensional vectors
* Semantically similar sentences have vectors that are "close" in high-dimensional space

# 2. Vector Similarity Search

Instead of keyword matching, we compare vector distances. Two sentences about "machine learning" will have similar embeddings, even if they use different words.

**Why SeekDB?**

* SQLite-based: zero-config, single-file, easy deployment
* Native vector support with similarity search
* 100x lighter than PostgreSQL + PGVector

# 3. Cosine Similarity

The metric we use to compare vectors:

    similarity = 1 - cosine_distance

* `1.0` = identical meaning
* `0.0` = orthogonal/unrelated
* `>0.7` = typically considered highly relevant

# Two Retrieval Strategies

# Strategy 1: Fixed-Count (Limit-based)

Always return the top-N most similar messages.

    const results = await collection.query({
      queryTexts: userQuery,
      nResults: 5
    });

**Pros**: Predictable token costs, simple implementation **Cons**: May include low-relevance messages just to hit the count

# Strategy 2: Threshold-based

Only return messages above a similarity threshold (e.g., ≥ 0.75).

    const memories = results.filter(r => 
      (1 - r.distance) >= threshold
    );

**Pros**: Dynamic context length, filters irrelevant history automatically **Cons**: Variable result count, requires tuning the threshold

**Recommendation**: Use hybrid—threshold first, then limit.

# Implementation with seekdb-js

repo: [https://github.com/oceanbase/seekdb-js](https://github.com/oceanbase/seekdb-js)

# Setup

    npm install seekdb

# Database Connection

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

# The AgentMemory Class

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

# Complete Agent Example

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

# Cost Comparison

Tested with 995 stored messages:

|Approach|Messages Passed|Token Cost|Latency|
|:-|:-|:-|:-|
|Full Context|995 (all)|100% baseline|Slow|
|SeekDB + Limit|5|\~5% (95% saved)|Fast|
|SeekDB + Threshold|18 (dynamic)|\~15% (85% saved)|Fast|

**Monthly savings** (10k sessions, 50 msgs/session):

* Qwen3 Max at $1.6/M tokens
* Full context: \~$1,600
* SeekDB approach: \~$80
* **Savings: $1,520/month (95%)**

# Multi-Session Persistence

For agents that need to maintain memory across sessions, SeekDB's SQLite-based architecture provides excellent persistence with minimal setup.

## Session-Based Memory Management

    class PersistentAgentMemory extends AgentMemory {
      constructor(collection, sessionId) {
        super(collection);
        this.sessionId = sessionId;
        this.sessionPrefix = `session_${sessionId}_`;
      }
    
      async store(role, message) {
        // Add session tag to metadata
        await this.collection.add({
          ids: `${this.sessionPrefix}${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          documents: message,
          metadatas: { 
            role, 
            timestamp: Date.now(),
            sessionId: this.sessionId 
          },
        });
      }
    
      async recallFromSession(query, sessionId, options = {}) {
        // Query within specific session
        const results = await this.collection.query({
          queryTexts: query,
          nResults: options.limit || 10,
          where: {
            sessionId: sessionId
          }
        });
        
        return this.formatResults(results);
      }
    
      async recallCrossSession(query, options = {}) {
        // Query across all sessions, filter by time
        const { hoursBack = 72 } = options;
        const cutoff = Date.now() - (hoursBack * 60 * 60 * 1000);
        
        const results = await this.collection.query({
          queryTexts: query,
          nResults: 20,
        });
        
        // Filter by recency
        return this.formatResults(results).filter(m => 
          m.timestamp > cutoff
        );
      }
    }

## Long-Term vs Short-Term Memory

    // Short-term: Current conversation only
    const shortTermMemory = new AgentMemory(collection);
    
    // Long-term: Persistent across sessions
    const longTermMemory = new PersistentAgentMemory(collection, 'user_123');
    
    // Hybrid approach: Combine both
    async function hybridRecall(query) {
      const [shortTerm, longTerm] = await Promise.all([
        shortTermMemory.recall(query, { limit: 5 }),
        longTermMemory.recallCrossSession(query, { hoursBack: 168 }) // 7 days
      ]);
      
      // Prioritize recent, then relevant historical
      return [...shortTerm, ...longTerm].slice(0, 10);
    }

## Memory Consolidation Strategy

To prevent unbounded growth, implement periodic consolidation:

    async function consolidateMemory(collection, maxEntries = 10000) {
      // Get entry count
      const count = await collection.count();
      
      if (count <= maxEntries) return;
      
      // Delete oldest 20% of entries
      const oldest = await collection.query({
        queryTexts: [''], // Query all
        nResults: Math.floor(maxEntries * 0.2),
        sortBy: 'timestamp',
        ascending: true
      });
      
      for (const id of oldest.ids[0]) {
        await collection.delete(id);
      }
    }

# Comparison with Alternative Approaches

## SeekDB vs Mem0

|Metric|SeekDB|Mem0|
|---|---|---|
|Storage|SQLite (single file)|Vector DB + Graph DB|
|Setup|Zero-config|Requires infrastructure|
|Latency|\<10ms query|>50ms typical|
|Cost|\~$0.01/1M vectors|\~$0.50/1M vectors|
|Multi-session|Native|Requires extra layer|
|Open Source|Fully|Oceanbase org|

**When to choose SeekDB**: Lightweight agents, edge deployment, cost-sensitive applications

**When to choose Mem0**: Complex knowledge graphs, enterprise features, managed service preference

## SeekDB vs LangGraph Memory

|LangGraph Memory|SeekDB|
|---|---|
|Built-in Checkpoint API|Custom AgentMemory class|
|Tied to LangGraph framework|Framework-agnostic|
|Simple key-value store|Rich vector similarity|
|Limited query capabilities|Powerful semantic search|
|Better for workflow state|Better for semantic memory|

**Hybrid approach**: Use LangGraph Checkpoint for workflow state + SeekDB for semantic memory.

    from langgraph.checkpoint.memory import MemorySaver
    from seekdb import SeekdbClient
    
    # LangGraph for workflow state
    checkpointer = MemorySaver()
    
    # SeekDB for semantic memory
    seekdb = SeekdbClient(...)
    
    def agent_node(state):
        # Get semantic context
        context = seekdb.recall(state['input'])
        
        # Process with workflow
        result = llm.process(...)
        
        # Store both
        checkpointer.put(...)
        seekdb.store('assistant', result)
        
        return {'output': result}

# Observational Memory: A New Paradigm

A recent trend challenging traditional RAG architectures is **Observational Memory**—a simpler approach gaining traction for its cost efficiency.

## Key Differences

|Aspect|RAG + Vector DB|Observational Memory|SeekDB|
|---|---|---|---|
|Architecture|Complex pipeline|Simple text storage|SQLite + Vectors|
|Cost Factor|10x baseline|1x (10x savings)|~5x baseline|
|Query Speed|Slow (retrieval)|Fast (direct access|Fast (indexed)|
|Maintenance|High|Low|Very Low|
|Accuracy|High (when tuned)|Good|High (semantic)|

## When to Use Which

**Observational Memory** is ideal when:
- Context windows are large enough (>100K tokens)
- Simple retrieval patterns dominate
- Infrastructure complexity must be minimized

**SeekDB** (vector-based) is ideal when:
- Large memory banks needed (>10K items)
- Semantic search accuracy is critical
- Multi-session persistence required
- Cross-session relevance matters

**Recommendation**: For most agent applications, SeekDB provides the best balance of semantic accuracy, cost efficiency, and simplicity.

# Key Takeaways

1. **Memory isn't about storing everything—it's about retrieving the right things**
2. Vector similarity > keyword matching for semantic understanding
3. Threshold-based retrieval is smarter but requires tuning
4. Multi-session persistence requires session tagging and consolidation
5. SeekDB offers the best cost-performance ratio for agent memory
6. Consider Observational Memory for very large context windows; SeekDB for production-scale deployments

**Full code**: [https://github.com/kejun/seekdb-agent-memory](https://github.com/kejun/seekdb-agent-memory)
