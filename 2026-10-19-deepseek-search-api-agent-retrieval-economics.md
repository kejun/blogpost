# 当搜索变成 0.75 美元/千次：DeepSeek Search & Fetch 深度拆解，以及 Agent 检索层的成本重构

> 2026 年 10 月 18 日，DeepSeek 在 API 文档里悄悄上线了两个新端点：`/v1/tools/search` 和 `/v1/tools/fetch`。没有发布会，没有 benchmark 榜单，只有一句定价——**每 1000 次成功请求 0.75 美元**。这条消息在 Hacker News 首页拿到 530 分、252 条评论，讨论的焦点却不是模型能力，而是「搜索 API 到底该值多少钱」。

这篇文章想回答四个问题：**DeepSeek 卖的到底是什么？0.75 美元/千次在成本结构上意味着什么？当搜索从"人用"变成"Agent 用"，接口设计有哪些新约束？以及，自建检索层的团队应该如何重新算这笔账？**

---

## 一、事件：一次没有发布会的产品上线

DeepSeek 这次上线的两个端点非常克制：

| 端点 | 方法 | 作用 | 定价 |
|------|------|------|------|
| `https://api.deepseek.com/v1/tools/search` | POST | 查询并返回结构化网页结果 | $0.75 / 1000 次成功请求 |
| `https://api.deepseek.com/v1/tools/fetch` | POST | 抓取单个网页，返回 Markdown | $0.75 / 1000 次成功请求 |

认证方式与 DeepSeek 模型 API 完全一致，同一个 Bearer Token，同一个账户余额。没有单独的注册、没有单独的 SDK、没有单独的配额体系——**搜索被当成模型的"附属工具"，而不是一个独立产品**。

计费口径值得单独拎出来说：

- 按**成功请求**计费，不按 token、不按返回条数；
- Search 必须返回**非空结果数组**才计费，空结果、超时、失败都不收费；
- Fetch 必须真正返回页面内容才计费；
- `count` 参数（1–50）只控制返回多少条，**不影响单价**；
- 每个账户 Search 与 Fetch 各自独立限流，均为 **5 QPS**；Fetch 还有额外的**单域名 QPS 限制**。

还有一个容易被忽略的细节：官方文档写明，通过 DeepSeek Harness、Claude Code 或 Codex 调用时，服务端工具调用已经在命中这两个 API，**目前免费，2026 年 11 月 1 日北京时间 0 点开始按请求计费**。

这句话的信息量很大。它意味着 DeepSeek 已经把搜索能力嵌进了主流编码 Agent 的工具链里，先用一个多月的免费窗口培养调用习惯，再开始收钱。这是典型的"基础设施先行、计费后置"打法——**先把搜索变成 Agent 的默认动作，再对默认动作收费**。

从竞争位置看，DeepSeek 并不是第一个做搜索 API 的。Tavily、Exa、Brave、Firecrawl、Serper 都已经在这个市场里跑了好几年。但 DeepSeek 是第一个把价格直接压到**不足主流竞品十分之一**，同时又把模型、搜索、抓取放在同一张账单上的玩家。

这就不是"再做一个搜索 API"那么简单了。它是在重写 Agent 检索层的成本基线。

---

## 二、为什么搜索突然成了 Agent 的"第二张账单"

过去两年，大家算 Agent 成本主要算两件事：输入 token 和输出 token。搜索 API 的费用通常被归到"工具调用"里，占比不大。但当 Agent 从 demo 走向长时程任务，这个假设正在失效。

### 2.1 调用次数从「每轮一次」变成「每步多次」

一个典型的研究型 Agent，完成一次任务的平均工具调用结构大致是：

- 3–8 次 query 改写与召回；
- 5–20 次网页抓取；
- 2–5 轮基于抓取结果的补充搜索；
- 每轮搜索返回 5–10 条结果，其中 60%–80% 的内容不会被真正使用。

也就是说，**一次任务 20–50 次搜索/抓取请求是常态**。按 Tavily 基础搜索 $8/1000 次、抓取约 $1.6/1000 页计算，单任务检索成本约 $0.16–$0.40；按 DeepSeek 的 $0.75/1000 计算，同样规模约 $0.015–$0.04。差了一个数量级。

当模型本身的价格已经打到每百万 token 几毛钱时，**检索费用反而成了单任务成本里增长最快的那一项**。这是 2026 年 Agent 工程的一个结构性变化：推理在变便宜，但"让模型看见真实世界"在变贵。

### 2.2 搜索质量直接决定 token 成本

更隐蔽的一层是：搜索 API 的返回格式，会影响下游模型的 token 消耗。

传统搜索引擎返回 title + snippet（约 100–200 字符），Agent 拿到后往往还要再 fetch 一次全文。这是一次额外的网络往返、一次额外的计费、一次额外的延迟。

DeepSeek 的 Search 响应里同时给了四个层级的文本：

| 字段 | 长度 | 用途 |
|------|------|------|
| `title` | 短 | 展示、去重 |
| `snippet` | 100–200 字符 | UI 展示、快速判断 |
| `summary` | 600–800 字符 | **给模型读**，通常足以判断相关性 |
| `content` | 全文（`need_content=true` 时） | 深度阅读、引用 |

这个设计的关键在于 `summary`：**它把"是否值得抓全文"的判断，前移到了搜索响应里**。如果 Agent 先用 summary 做一轮筛选，只对 20%–30% 的结果调用 Fetch，那么总请求数和总 token 数都会显著下降。

换句话说，DeepSeek 不是单纯在卖"搜索结果"，它在卖一个**两级检索流水线**：Search 负责召回与粗排，Fetch 负责精读。价格相同（都是 $0.75/1000），但调用比例可以由工程侧控制。这比"搜索一个价、抓取另一个价"的定价模型更容易做预算。

### 2.3 平台补贴期的窗口

文档里那句"11 月 1 日前免费"，对正在选型的团队意味着一个明确的决策窗口：**用一个月时间，把检索层做成可替换的抽象层，然后用真实流量对比 DeepSeek 与现有供应商的质量和成本**。

但不要把它理解成"免费所以先用"。免费期最大的风险是**把调用模式写死**——比如假设搜索永远返回全文、假设延迟稳定、假设没有 QPS 限制。等计费开始、限流生效，架构就要返工。

正确的做法是：从第一天起就按"付费 + 5 QPS + 部分失败"的约束来设计。

---

## 三、接口拆解：为「机器读者」设计的搜索层

把 DeepSeek 的 Search 响应逐字段拆开，会发现它不是把搜索引擎的 HTML 结果包一层 JSON，而是针对 Agent 的阅读习惯重新组织过。

一个完整的响应项长这样：

```json
{
  "rerank_score": 2.4,
  "title": "DeepSeek V4 model released",
  "url": "https://example.com/deepseek-v4",
  "snippet": "DeepSeek V4 is now available, with tool calling and long-context support.",
  "summary": "DeepSeek has released the V4 model. The release adds improved tool calling and long-context support for agent workflows.",
  "content": "DeepSeek V4 is now generally available...",
  "site_name": "Example News",
  "site_icon": "https://example.com/favicon.ico",
  "date": "2026-06-01T00:00:00+00:00",
  "authority": 3
}
```

### 3.1 `rerank_score`：一个 0–3 的「质量分」

官方定义是：综合相关性、权威性、时效性的 0–3 分，**1.5 分以上视为高质量结果**。

这个字段的价值不在于分数本身，而在于它给了工程侧一个**可调阈值**。多数搜索 API 只返回一个排序后的列表，Agent 无法判断"第 7 条到底该不该读"。有了绝对分数，就可以做三件事：

1. **截断**：只把 `rerank_score >= 1.5` 的结果喂给模型，减少噪声；
2. **分级**：高分结果直接进上下文，低分结果只保留 title 用于去重；
3. **监控**：统计每次查询的分数分布，识别"检索失败"（比如全部分数低于 1.0），触发 query 改写而不是硬读。

这比"固定取 top-k"更接近人类研究员的 behavior：先扫一眼质量，再决定读不读。

### 3.2 `authority`：0–4 的权威分层

`authority` 是另一个有意思的字段：0–4 的整数，3 以上为"高权威来源"，-1 表示未知。

它解决的是 RAG 里一个长期痛点：**相关性高不等于可信**。一个 SEO 农场页面可能和 query 高度相关，但它的结论不可引用。有了 authority 分层，工程侧可以实施差异化策略：

- 事实性问题：要求至少一条 `authority >= 3` 的来源；
- 观点性问题：允许低 authority，但要求多源交叉；
- 代码问题：优先 GitHub / 官方文档（通常 authority 较高），降低内容农场权重。

当然，authority 的具体判定逻辑官方没有公开。它是一个**黑盒信号**，适合做粗筛，不适合做最终裁决。真正需要引用的事实，仍然应该回到原文核对。

### 3.3 `ori_question`：把「用户意图」和「检索 query」分开

这是整个 API 里最容易被低估的字段。

```json
{
  "query": "DeepSeek V4 release date",
  "ori_question": "DeepSeek 下一代模型什么时候发布？现在能用吗？",
  "count": 10
}
```

`query` 是真正发给搜索引擎的串，`ori_question` 是触发这次搜索的原始用户问题（1–128 字符）。官方说明是"用于改善 query 理解"。

这背后是一个现实问题：Agent 生成的 query 经常是"关键词堆砌"，丢失了用户的真实意图。比如用户问"这个库能不能在 Windows 上用"，Agent 改写成 `library Windows support`，搜索引擎可能返回一堆安装教程，而不是兼容性说明。把原始问题一起传进去，等于给检索层提供了**意图上下文**，让它能在召回阶段做更准确的判断。

对工程侧的启示是：**不要让 Agent 只生成 query，要让它同时保留原始问题**。这也是 query rewriting 的最佳实践——改写可以优化表达，但不能丢失意图。

### 3.4 查询算子：把「搜索语法」暴露给 Agent

DeepSeek 支持一套相当完整的算子：

| 算子 | 示例 | 用途 |
|------|------|------|
| `site:` | `DeepSeek site:github.com OR site:huggingface.co` | 限定站点，支持 OR 组合 |
| `-site:` | `-site:example.com` | 排除站点 |
| `-term` | `-advertisement` | 排除词 |
| `"..."` | `"exact phrase"` | 精确短语 |
| `-"..."` | `-"release notes"` | 排除短语 |
| `lang:` | `lang:zh,en` | 限定语言 |
| `after:` / `before:` | `after:2025-01-01` | 时间范围 |

这套语法对 Agent 非常实用。比如做"竞品价格监控"时，可以直接 `site:competitor.com after:2026-09-01`；做"开源项目调研"时，可以 `site:github.com OR site:huggingface.co`。

但要注意：**算子是把双刃剑**。Agent 如果滥用 `site:`，会把自己的信息源锁死在一个小圈子里，形成"检索回音室"。实践中应该把算子当作"精修工具"，而不是默认策略——先用自然语言 query 召回，再用算子做补充验证。

### 3.5 `localization`：一个 IP 参数引发的合规思考

`localization` 字段允许传入一个 IP 地址来本地化搜索结果。这个设计的初衷是让搜索结果更贴近用户所在地区（比如本地新闻、本地服务）。

但它也带来一个明显的合规问题：**服务端凭什么相信调用方传入的 IP？** 如果任何人都可以伪造 IP 来获取其他地区的搜索结果，那么这个参数就可能被用于绕过地域内容限制。文档没有说明是否做了校验，只写了"可选的 IP 地址"。

对企业的建议是：如果业务涉及地域敏感内容，不要依赖这个参数做合规判断，而应该在应用层维护明确的地域策略。

### 3.6 Fetch：只做一件事，但做对了

Fetch 的接口极简：

```json
POST /v1/tools/fetch
{ "url": "https://example.com/article" }
```

返回：

```json
{
  "title": "Example article",
  "content": "# Example article\n\nArticle content."
}
```

两个字段，没有多余的东西。`content` 是 Markdown，标题层级、代码块、列表都保留。这对 LLM 友好——Markdown 比 HTML 少 80% 以上的标签噪声，比纯文本保留了结构信息。

错误码设计也值得一看：

| 状态码 | 含义 | 是否重试 |
|--------|------|----------|
| 400 | 请求格式错误 | 否 |
| 401 | 认证失败 | 否 |
| 402 | 余额不足 | 充值后 |
| 403 | 被安全策略拒绝 | 否 |
| 404 | 无法提取可用内容 | 否 |
| 408 | 读取请求体超时 | 是 |
| 413 | 请求体过大 | 否 |
| 429 | QPS 超限 | 是（退避） |
| 500 / 504 | 服务端/下游错误 | 是 |

这个分类很清晰：**4xx 里只有 408 和 429 值得重试，其余都是"改了再试"**。很多 Agent 框架的通病是无差别重试所有失败请求，结果在 403/404 上浪费大量时间和配额。按错误码分类处理，是最基本的工程纪律。

### 3.7 5 QPS：最容易被忽视的硬约束

文档写明：Search 和 Fetch 各自 **5 QPS**，按账户计算，与 API Key 无关；Fetch 还有单域名 QPS 限制。

5 QPS 意味着什么？如果一个 Agent 任务需要 30 次检索，串行执行至少 6 秒；如果 10 个用户同时发起任务，就需要排队。对于研究型 Agent（单任务 20–50 次请求），5 QPS 是**明显不够**的。

这暴露了 DeepSeek 当前的产品定位：**它更适合"轻量级、低并发"的 Agent 场景**，而不是高并发的生产级检索服务。对比 Tavily、Exa 的企业版（通常支持数十到数百 QPS），5 QPS 更像是一个"开发者预览"级别的限制。

对工程侧的含义：

- 必须在客户端做**令牌桶限流**，而不是靠服务端 429 来发现瓶颈；
- 必须做**请求合并**：多个 Agent 共享同一 query 时，走本地缓存而不是重复请求；
- 必须做**优先级队列**：交互式请求优先于后台批处理；
- 如果 QPS 不够，就要准备**多供应商分流**，而不是死等扩容。

---

## 四、价格对比：0.75 美元到底便宜在哪里

把所有主流检索 API 放在一张表里，按"一次搜索 + 一次抓取"的组合成本计算（单位：美元/千次）：

| 供应商 | 搜索单价 | 抓取单价 | 组合成本（搜索+抓取） | 备注 |
|--------|----------|----------|------------------------|------|
| **DeepSeek** | $0.75 | $0.75 | **$1.50** | 按成功请求计费，5 QPS |
| Tavily（basic） | $8.00 | $1.60（5 页/credit） | $9.60 | 高级搜索 $16/千次 |
| Exa | $4.00 | $1.00/页 | $5.00 | Deep Search $12–15/千次 |
| Firecrawl | $1.66（2 credits/10 结果） | $0.83/页 | $2.49 | 需年付 $83/月 10 万 credits |
| Brave Search API | 约 $5/千次 | 不含抓取 | — | 自有索引，LLM Context 另计 |
| Serper | 约 $1/千次 | 不含抓取 | — | 转售 Google 结果 |

需要说明的是，这张表只比较"单价"，不比较"质量"。搜索 API 的真实成本还包括：

1. **无效请求成本**：返回了结果但内容不相关，下游模型读了一堆噪声，token 白烧；
2. **重试成本**：失败率高时，实际请求数可能是成功数的 2–3 倍；
3. **工程成本**：解析、去重、清洗、缓存、监控，这些都不在 API 账单里；
4. **合规成本**：抓取受 robots.txt、版权、站点条款约束，法务风险要单独评估。

但即便把这些都算上，DeepSeek 的价格仍然低得离谱。**$1.50 完成一次"搜索 + 抓取"**，而 Tavily 的组合成本是 $9.60，Exa 是 $5.00，Firecrawl 是 $2.49。DeepSeek 比最便宜的 Firecrawl 还低 40%，比 Tavily 低 84%。

这不是"价格战"级别的差异，这是**成本结构级别的差异**。

### 4.1 为什么 DeepSeek 能这么便宜

低价通常有三种来源：补贴、效率、或者垂直整合。DeepSeek 这次更像是第三种。

**第一，自有索引，不转售 SERP。** 官方明确说 Search 由"DeepSeek 自研搜索引擎"驱动。这意味着它不需要向 Google/Bing 支付每千次 $3–$5 的上游费用，也不需要承担转售 API 的加价。对比 Serper 这类"Google 结果代理"，成本结构完全不同。

**第二，搜索与模型同侧部署。** 搜索结果的 rerank、summary 生成，都可以用自家小模型完成，边际成本远低于调用第三方 LLM。`summary` 字段（600–800 字符）本质上是一次小模型推理，如果放在外部供应商，这部分成本会摊到 API 价格里。

**第三，按成功请求计费，降低了"无效流量"的摩擦。** 空结果不收费，意味着 DeepSeek 把"检索失败"的风险留给了自己。这既是对质量的自信，也是一种获客策略——开发者不会因为"搜不到还扣钱"而流失。

**第四，搜索是模型的"入口"，不是利润中心。** 搜索 API 的真正价值，是让更多 Agent 调用 DeepSeek 模型。搜索本身可以不赚钱，甚至亏钱，只要它能带动模型 token 的消耗。这是典型的"剃刀-刀片"模型：搜索是剃刀，模型是刀片。

这也解释了为什么 11 月 1 日前通过 Harness/Claude Code/Codex 调用免费——**它要的是调用习惯，不是搜索收入**。

### 4.2 低价不等于低成本：三个隐藏账单

但工程团队不能只看单价。以下三项在真实生产里会显著抬高"实际成本"：

**（1）5 QPS 的排队成本。** 假设单任务 30 次请求，10 个并发用户，理论最短完成时间是 60 秒（30×10/5）。如果业务要求 10 秒内响应，5 QPS 直接不可行。这时要么加机器做多账户分流（违反条款风险），要么接受排队，要么换供应商。**限流是比单价更硬的约束。**

**（2）抓取失败的长尾。** Fetch 的 404 包含多种情况：URL 不可用、被站点策略阻挡、目标站点报错、内容类型不支持、页面无可提取的 Markdown。真实网页里，这部分比例不低——尤其是需要登录、反爬严格、或纯 JS 渲染的站点。失败不收费，但**重试和降级的人力成本要自己承担**。

**（3）质量不达标的返工。** 低价搜索如果召回质量差，Agent 会多轮改写 query、多读几篇不相关文章，最终 token 成本反而更高。检索层的经济学不是"每次请求多少钱"，而是"**每个正确回答多少钱**"。

一个简单的判断公式：

```
单任务检索成本 = 请求次数 × 单价 + 无效阅读的 token 成本 + 失败重试成本 + 工程维护成本
```

DeepSeek 只优化了第一项。后三项，仍然取决于你的工程能力。

---

## 五、实战：把检索层做成「可替换、可预算、可观测」的流水线

下面是一套生产可用的检索层设计，核心原则是：**不把任何一家供应商写死，不把任何一次调用当成必然成功。**

### 5.1 分层架构

```
Agent
  │
  ▼
Query Planner（改写 + 意图保留 + 算子选择）
  │
  ▼
Retrieval Router（供应商选择 / 预算 / 限流 / 缓存）
  │
  ├── DeepSeek Search ──► Rerank Filter（score ≥ 1.5, authority ≥ 2）
  ├── Tavily / Exa ─────► 质量兜底
  └── 本地缓存（Redis / SQLite）
  │
  ▼
Content Fetcher（两段式：summary 先筛，Fetch 精读）
  │
  ▼
Context Assembler（去重 / 截断 / 引用标注）
```

关键设计点：

1. **Query Planner 必须保留 `ori_question`**，改写只优化表达，不改变意图；
2. **Router 按任务类型选供应商**：时效性强的走 Brave/DeepSeek，语义检索走 Exa，深度研究报告走 Tavily Research；
3. **缓存键包含 query + 时间窗 + 语言**，而不是只按 query 缓存——否则会返回过期结果；
4. **Fetch 只对高分结果执行**，并且设置单任务预算上限（比如最多 20 次）；
5. **Context Assembler 做去重**：同一 URL 的多次命中只保留一份，按段落级相似度合并。

### 5.2 一个可运行的 Python 骨架

```python
import asyncio, hashlib, json, time
from dataclasses import dataclass
from typing import Any

import httpx

DEEPSEEK_BASE = "https://api.deepseek.com"
API_KEY = "sk-..."  # 从环境变量读取，不要硬编码


@dataclass
class Budget:
    max_search: int = 20
    max_fetch: int = 20
    used_search: int = 0
    used_fetch: int = 0

    def can_search(self) -> bool:
        return self.used_search < self.max_search

    def can_fetch(self) -> bool:
        return self.used_fetch < self.max_fetch


class RateLimiter:
    """简单的令牌桶：5 QPS，留一点余量避免边界抖动。"""

    def __init__(self, qps: float = 4.5):
        self.interval = 1.0 / qps
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._last + self.interval - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()


async def search(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    query: str,
    ori_question: str,
    count: int = 8,
    need_content: bool = False,
) -> list[dict[str, Any]]:
    await limiter.acquire()
    resp = await client.post(
        f"{DEEPSEEK_BASE}/v1/tools/search",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "query": query,
            "ori_question": ori_question,
            "count": count,
            "need_content": need_content,
        },
        timeout=20.0,
    )
    if resp.status_code == 429:
        await asyncio.sleep(2.0)  # 退避后由上层决定是否重试
        raise RuntimeError("rate_limited")
    resp.raise_for_status()
    return resp.json().get("results", [])


async def fetch_page(
    client: httpx.AsyncClient,
    limiter: RateLimiter,
    url: str,
) -> str | None:
    await limiter.acquire()
    resp = await client.post(
        f"{DEEPSEEK_BASE}/v1/tools/fetch",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"url": url},
        timeout=30.0,
    )
    if resp.status_code in (403, 404):
        return None  # 不值得重试
    if resp.status_code in (408, 429, 500, 504):
        raise RuntimeError(f"retryable_{resp.status_code}")
    resp.raise_for_status()
    return resp.json().get("content") or None


async def retrieve(question: str, queries: list[str]) -> list[dict]:
    budget = Budget()
    limiter = RateLimiter()
    seen: set[str] = set()
    candidates: list[dict] = []

    async with httpx.AsyncClient() as client:
        for q in queries:
            if not budget.can_search():
                break
            try:
                results = await search(client, limiter, q, question)
                budget.used_search += 1
            except Exception:
                continue

            for r in results:
                url = r.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                # 质量闸门：分数与权威性双阈值
                if r.get("rerank_score", 0) < 1.5:
                    continue
                if r.get("authority", -1) not in (-1,) and r["authority"] < 2:
                    continue
                candidates.append(r)

        # 只对前 N 条高分结果抓全文
        candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
        pages: list[dict] = []
        for r in candidates[: budget.max_fetch]:
            try:
                content = await fetch_page(client, limiter, r["url"])
                budget.used_fetch += 1
                if content:
                    pages.append({**r, "content": content})
            except Exception:
                continue
        return pages
```

这段代码有几个刻意的选择：

- **限流器是客户端主动的**，不是等服务端 429 再退避；
- **预算上限是硬编码的**，防止 Agent 失控烧钱；
- **质量闸门在抓取之前**，避免把配额浪费在低分结果上；
- **403/404 不重试**，408/429/5xx 才重试；
- **去重在 URL 层**，但生产环境还应该加内容指纹（正文 simhash）去重。

### 5.3 观测指标：别只看「调用成功率」

检索层的监控至少要覆盖四类指标：

| 类别 | 指标 | 异常信号 |
|------|------|----------|
| 可用性 | 请求成功率、P95 延迟、429 比例 | 429 > 5% 说明限流不够 |
| 质量 | 平均 rerank_score、高分结果占比、空结果率 | 空结果率 > 15% 说明 query 有问题 |
| 成本 | 单任务搜索/抓取次数、单任务检索成本 | 次数突增说明 Agent 在"乱搜" |
| 效果 | 引用命中率、答案正确率、人工复核通过率 | 成本降了但正确率也降，说明过度压缩 |

最后一类最容易被忽略：**检索层的目标不是"少花钱"，而是"用更少的钱拿到同样或更好的答案"**。如果只盯成本，很容易把召回压得太狠，最后模型答不出来，用户流失，反而更贵。

---

## 六、行业影响：搜索 API 正在从「工具」变成「模型入口」

DeepSeek 这次上线的真正意义，不在于又多了两个端点，而在于它把搜索 API 的商业模式往前推了一步。

### 6.1 从「按查询收费」到「按成功结果收费」

传统搜索 API 的计费逻辑是"你查了，我就收钱"，不管结果有没有用。DeepSeek 改成"有结果才收钱"，本质上是把**检索质量的风险**从调用方转移到了供应方。

这会倒逼整个行业跟进。可以预见，未来一年内，"空结果不计费""失败不计费"会成为搜索 API 的标配。这对开发者是好事——它让"检索层的试错成本"大幅下降。

但它也有副作用：供应商会倾向于**放宽召回**，以确保"总有结果返回"。宽召回意味着更多低质量结果，最终还是要靠 `rerank_score` 和 `authority` 这类信号来过滤。**计费方式的改变，会把质量博弈从"有没有结果"推向"结果有多准"。**

### 6.2 从「独立 API」到「模型自带工具」

DeepSeek 把搜索和模型放在同一个账户、同一个 Key、同一张账单下，这是一个明确的信号：**搜索不再是独立的基础设施，而是模型能力的一部分**。

对比来看：

- OpenAI 的 web search 是模型内置工具，按调用计费，不单独卖 API；
- Anthropic 的 web search 也是通过 Claude API 提供，按搜索次数计费；
- Google 的 Gemini 自带 Grounding with Google Search，按千次查询计费；
- DeepSeek 则同时提供"模型内置"和"独立端点"两种形态。

这个趋势对独立搜索 API 厂商（Tavily、Exa、Brave）意味着什么？

短期看，是价格压力。长期看，是**价值重心的转移**：当"能搜"变成标配，"搜得准、搜得深、搜得可解释"才是差异化。Exa 的语义索引、Brave 的自有索引与低延迟、Tavily 的深度研究能力，都是模型厂商短期内难以复制的。

换句话说，**通用搜索会商品化，垂直检索能力会溢价**。

### 6.3 数据飞轮与隐私张力

搜索 API 还有一个不常被讨论的维度：**数据回流**。

当 Agent 通过搜索 API 发起查询，供应商能看到什么？query、点击、抓取内容、以及（可能的）下游使用情况。这些数据可以用来改进检索质量，也可以用来训练模型。DeepSeek 的隐私政策没有在这次文档里展开，但企业客户必须问清楚三个问题：

1. query 和抓取内容是否会被用于训练？
2. 是否支持零数据保留（ZDR）？
3. 数据存储在哪里，是否跨境？

对于金融、医疗、法务等敏感行业，这三个问题的答案可能比价格更重要。

### 6.4 对自建检索团队的启示

如果你所在团队已经在自建检索层（爬虫 + 向量库 + rerank），DeepSeek 的低价并不意味着"自建没意义了"。相反，它把自建的价值重新定义了一遍：

- **通用网页检索**：直接用 API 更划算，自建很难做到 $0.75/千次；
- **垂直领域检索**：自有数据、私有文档、行业术语，仍然需要自建；
- **混合检索**：通用 API 负责"广度"，自建索引负责"深度"，两者用同一个 Router 调度；
- **缓存与复用**：高频 query 的缓存，是自建层最稳定的成本优势。

一个务实的判断标准是：**如果某个检索场景的 query 分布足够集中（比如 Top 1000 query 覆盖 80% 流量），自建缓存 + API 回源的混合模式，成本可以再降一个数量级。**

---

## 七、局限与风险：三个不能忽略的问题

任何技术选型都要看边界。DeepSeek Search & Fetch 当前至少有三个明确的局限：

**第一，5 QPS 的天花板。** 这不是"稍微有点低"，而是"无法支撑中高并发生产系统"。如果你的 Agent 是面向 C 端用户、有峰值流量，5 QPS 会在第一时间成为瓶颈。短期内它更适合内部工具、离线批处理、低并发研究型 Agent。

**第二，抓取能力的边界。** Fetch 只返回"可提取的 Markdown"，对 JS 渲染、登录墙、反爬严格的站点，成功率会明显下降。文档也明确说"受目标站点可用性和访问策略约束"。需要登录态、需要交互的页面，仍然要靠 Playwright 之类的浏览器方案。

**第三，质量信号的黑盒性。** `rerank_score` 和 `authority` 都没有公开计算方式。它们适合做粗筛，但不能替代人工事实核查。对准确性要求高的场景（医疗、法律、金融），仍然需要多源交叉验证和引用溯源。

还有一点值得警惕：**低价可能吸引大量滥用**。当搜索成本低到可以忽略，Agent 会倾向于"多搜几次反正不贵"，导致 query 数量膨胀、上下文噪声增加、最终答案质量下降。**成本约束有时候是一种必要的架构纪律。**

---

## 八、结论：检索层的「水电化」

把这次发布放在更长的时间轴上看，它标志着 Agent 基础设施的一个转折点：**检索正在变成像水电一样的基础设施——便宜、随时可用、按用量计费，但质量和稳定性参差不齐。**

对开发者来说，这是好事。过去做 RAG，光是"搭一套能用的搜索 + 抓取"就要花几周；现在一条 curl 就能跑通，成本低到可以忽略。这会把竞争重心从"能不能检索"推向"检索得好不好、用得省不省、管得住不住"。

但也带来新的责任：

- **预算控制**要前置到架构里，而不是月底看账单才发现超支；
- **供应商抽象**要做，不能把业务逻辑绑死在任何一家 API 上；
- **质量评估**要持续做，低价不等于高性价比；
- **合规审查**要提前做，抓取和数据处理的法律风险不会因为 API 便宜而消失。

DeepSeek 用 $0.75/千次把检索层的价格打了下来。但真正的成本优势，从来不是"单价最低"，而是"**在每个正确回答上花最少的钱**"。这需要工程判断，而不是一个价格表。

---

## 附：落地检查清单

如果你打算本周就把检索层接上 DeepSeek，建议按这个顺序做：

- [ ] 用真实业务 query 跑 100 条，统计空结果率、平均 `rerank_score`、高分占比；
- [ ] 对比现有供应商的 top-5 重合度，评估召回差异；
- [ ] 测 P50/P95 延迟，确认 5 QPS 下的排队时间可接受；
- [ ] 实现客户端令牌桶 + 单任务预算上限；
- [ ] 对 `rerank_score < 1.5` 的结果做截断，观察答案质量变化；
- [ ] 对 `authority < 2` 的结果做标记，事实类问题要求多源交叉；
- [ ] 加 URL + 内容指纹双层去重；
- [ ] 按错误码分类重试（仅 408/429/5xx）；
- [ ] 建立单任务成本看板（搜索次数、抓取次数、token 消耗）；
- [ ] 保留第二家供应商作为 fallback，按任务类型分流。

检索层的战争才刚刚开始。价格只是入场券，工程质量才是终局。
