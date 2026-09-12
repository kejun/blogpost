# 当知识库开始"编译"：llm_wiki 1.9 万星、Karpathy 模式与 RAG 的"解释执行"之殇

> 你把 50 篇论文丢进知识库，然后问同一个问题两遍。传统 RAG 的做法是：每次查询都重新检索、重新拼装、重新生成——仿佛昨晚的阅读从未发生过，仿佛它今天第一次见到这些文档。更糟的是，两次的答案可能还不一样。
>
> llm_wiki 的回答只有一句话：**"Knowledge is compiled once and kept current, not re-derived on every query."**（知识编译一次、持续保鲜，而不是每次查询重新推导。）

这个 2026 年 9 月冲上 GitHub Trending 的桌面应用（18,720 星、今日 +647、2,134 fork），把 Andrej Karpathy 的一份 gist 变成了一个完整的"自建知识库"产品。它戳中的是过去两年 RAG 架构最深的隐痛：**检索式问答没有积累**。而它的解法，是一整套借自编译器设计的隐喻——三层架构、增量构建、链接器、静态分析。今天这篇文章，我们拆开看看这个"编译制知识库"到底是怎么运作的，以及它是不是 RAG 范式的真正接班人。

---

## 一、Karpathy 的反 RAG 宣言：三层架构与"编译-维护"模型

故事要从源头说起。llm_wiki 的 README 第一行致敬的不是某个框架，而是 Karpathy 2026 年的一份 gist——[llm-wiki.md](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。它的开篇就宣判了 RAG 的死刑缓期：

> Most people's experience with LLMs and documents looks like RAG... the LLM is rediscovering knowledge from scratch on every question. There's no accumulation.

（大多数人与 LLM 和文档的互动就是 RAG……LLM 在每个问题上都从零重新发现知识。没有任何积累。）

这句话值得反复咀嚼。因为我们这两年所有的知识库产品——NotebookLM、ChatGPT 文件上传、无数企业 RAG 平台——底层都是同一个抽象：**documents in, chunks indexed, retrieved at query time**。它们的架构决定了"查询时重建"是宿命：向量库里存的是碎片，不是理解；每次问答都要靠检索召回碎片、再靠模型现场拼装。用编译器的语言说，这是**解释执行**——源代码每次运行都要重新解析、重新解释，没有任何中间产物沉淀下来。

Karpathy 提出的替代方案，是知识库版的 **AOT 编译（Ahead-of-Time Compilation）+ 增量构建**：

| 层 | 角色 | 谁拥有 | 类比 |
|----|------|--------|------|
| **Raw Sources** | 原始文档（不可变，唯一事实来源） | 你 | 源代码 |
| **Wiki** | LLM 生成的 Markdown 页面（摘要、实体页、概念页、综合对比） | LLM | 编译产物 |
| **Schema** | 结构规则与工作流约定（CLAUDE.md / AGENTS.md） | 你与 LLM 共同演进 | 编译器配置 |

配套三个核心操作：**Ingest**（编译：读新源 → 生成/更新页面）、**Query**（执行：在已编译产物上回答问题）、**Lint**（静态分析：查矛盾、查过期声明、查孤立页面、查缺失的交叉引用）。两个特殊文件充当"符号表"与"构建日志"：`index.md` 是全部页面的目录（LLM 每次 ingest 后更新，查询时先读它导航），`log.md` 是追加式的时间线记录——Karpathy 特意强调格式要可被 Unix 工具解析：`grep "^## \[" log.md | tail -5` 就能拿到最近 5 条操作记录。

最妙的一句类比藏在 gist 里：

> Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.

（Obsidian 是 IDE，LLM 是程序员，wiki 是代码库。）

这个框架把"知识管理"从**消费行为**（检索、阅读）重构成了**开发行为**（编写、编译、维护、重构）。人类负责需求（sourcing、提问），LLM 负责全部苦力活（总结、交叉引用、归档、记账）。而 llm_wiki 做的事情，就是把这个模式文档产品化为一个 Electron + Rust 的跨平台桌面应用，并补上了 Karpathy 没写的一层：**purpose.md**——schema 管"知识怎么组织"，purpose 管"知识为什么存在"（目标、关键问题、演进中的论点），LLM 每次 ingest 和 query 时都会读它。这是"编译制知识库"里最容易被忽视、却最关键的抽象：没有方向的编译器，只会产出死代码。

## 二、把"编译"工程化：llm_wiki 的写入侧设计

Karpathy 的模式文档可以复制粘贴给任何 Agent 用，但把它做成产品，考验的是"写入侧"的工程细节。llm_wiki 在这块有几个值得单拎出来的设计。

**第一，两步 Chain-of-Thought Ingest。** 原始模式里 LLM 一边读一边写（单步），llm_wiki 把它拆成两次顺序 LLM 调用：

- **Step 1 (Analysis)**：LLM 读源 → 输出结构化分析（关键实体/概念/论点、与现有 wiki 的关联、与已有知识的矛盾与张力、结构建议）
- **Step 2 (Generation)**：LLM 拿分析结果 → 生成 wiki 文件（带 frontmatter 的源摘要、实体页、概念页、更新 index/log/overview、给人类的 review 项、给 Deep Research 的搜索词）

"先理解、再落盘"的分离，是这套管线质量的根本保障——它把"读"和"写"两个异构任务从共享上下文的纠缠里拆开，analysis 成了 generation 的"编译中间表示"（IR）。Karpathy 在 gist 里说单个源可能触碰 **10-15 个 wiki 页面**——没有中间表示，一次性完成这种跨页面的更新很容易顾此失彼。

**第二，SHA256 增量缓存，这是"增量编译"的字面实现。** 每个源文件在 ingest 前先 hash，未变化的文件直接跳过——省 token、省时间。这个设计与编译器里基于文件时间戳/哈希的增量构建（make、ninja）同构：**只有变更的部分触发重编译**。配上持久化 ingest 队列（串行执行防止并发 LLM 调用、崩溃后可恢复、失败自动重试 3 次），写入侧就有了"构建系统"的可靠性语义。

**第三，sources[] 可溯源字段。** 每个生成的 wiki 页面在 YAML frontmatter 里记录贡献它的原始文件列表。这一层" provenance 元数据"是后面知识图谱四信号模型中"来源重叠"信号的数据基础，也是"Read Sources Only"模式（只基于原始材料回答）的前提。**编译产物和源码之间的对应关系被显式保留了**——这是很多黑盒 RAG 平台做不到的审计能力。

## 三、知识图谱：四信号相关性模型，或者说，"链接器"

交叉引用（[[wikilink]]）是 wiki 的语法，但只有把它变成可计算的图，才谈得上"链接器"。llm_wiki 的 4-Signal Relevance Model 是全文最像工程论文的部分：

| 信号 | 权重 | 含义 |
|------|------|------|
| Direct link | ×3.0 | 页面间存在 [[wikilink]] 直接链接 |
| Source overlap | ×4.0 | 页面共享同一原始来源（frontmatter sources[]） |
| Adamic-Adar | ×1.5 | 共享共同邻居（按邻居度数加权） |
| Type affinity | ×1.0 | 同类型页面加成（实体↔实体、概念↔概念） |

注意权重的设计品味：**"来源重叠"（×4.0）权重最高**——因为同一份原始文档"喂"出来的页面，语义关联最可信，这比单纯的链接结构更接近真实的知识血缘；Adamic-Adar 这个图论经典指标（在社交网络分析中用于衡量两个节点通过共同邻居的相似度，且对高连接度邻居做惩罚）被用来捕捉"没有显式链接但处于同一主题邻域"的页面。四路信号加权后，就得到了整个 wiki 的相关性图，驱动后续的图扩展检索、社区发现和洞察生成。

真正的亮点是 **Louvain 社区发现**：基于链接拓扑自动发现知识簇，并计算每个社区的 cohesion 分数（实际边数/可能边数），低于 0.15 的松散社区会被标记警告。这在编译器世界里对应的是**模块化分析**——自动告诉你"你的知识库里哪些页面天然抱团、哪些簇是散沙"。Graph Insights 更进一步做**静态分析**：

- **Surprising Connections**（意外关联）：跨社区边、跨类型链接、外围↔枢纽耦合，用复合惊讶分数排序。这相当于 lint 器发现"这两个模块不该互相依赖"的反向信号——**"这两个簇居然有关联"往往就是研究灵感来源**。
- **Knowledge Gaps**（知识缺口）：孤立页面（度数 ≤ 1）、稀疏社区——对应编译器警告里的"未引用的符号"。每个缺口都挂一个 Deep Research 按钮：LLM 读取 purpose.md + overview.md 生成领域感知的搜索主题，调 Tavily/SerpApi/SearXNG 多查询搜索，结果自动 ingest 回 wiki。

这套"分析-发现-补充"闭环，是纯 RAG 架构完全不存在的能力：RAG 只回答你问的问题，而 wiki 的图分析会**主动告诉你该问什么**。

## 四、查询侧：四阶段检索管线，RAG 被"降级"为可选组件

llm_wiki 最反直觉的设计在查询侧：**它保留了 RAG，但把它贬为可选的增强组件，默认关闭**。四阶段检索管线如下：

1. **Phase 1 — Tokenized Search**：英文按词切分 + 去停用词；**中文用 CJK bigram 分词**（"每个"→[每个, 个…]）；标题命中 +10 分。同时搜 wiki/ 和 raw/sources/。
2. **Phase 1.5 — Vector Semantic Search（可选）**：任何 OpenAI 兼容的 /v1/embeddings 端点，向量存 LanceDB（Rust 后端），余弦相似度召回语义相关但无关键词重叠的页面，与 tokenized 结果合并。
3. **Phase 2 — Graph Expansion**：以 top 检索结果为种子节点，沿四信号相关性图做 **2-hop 带衰减遍历**，把"相邻知识"也拉进上下文。
4. **Phase 3 — Budget Control**：可配置上下文窗口（4K → 1M token），按比例分配：**60% wiki 页面、20% 对话历史、5% index、15% 系统**。页面按"检索分 + 图相关分"综合排序择优。
5. **Phase 4 — Context Assembly**：载入整页全文（不是摘要片段！），系统提示词注入 purpose.md、语言规则、引用格式、index.md，模型回答时必须按编号引用页面 [1]、[2]。

三个细节值得展开。**其一，"整页全文而非片段"**——这是与 RAG 背道而驰的选择：RAG 为了塞进上下文窗口必须切 chunk，而 wiki 页面本身就是"已经提炼过的知识单元"，天然带着上下文，直接整页载入比碎片拼装有更高的信息密度。**其二，默认关闭的向量搜索**——作者在 benchmark 里给出了诚实的数据：开启向量搜索后召回率从 58.2% 提升到 71.4%（+13.2pp），但它不是默认项。这说明在 ~100 个源、数百页的规模下（Karpathy 声称 index.md 导航"surprisingly well"的规模），**图结构 + 关键词检索已经够用，向量是锦上添花而非地基**——对个人知识库这个场景，这是极其务实的取舍。**其三，Cited references 面板和"Save to Wiki"**——有价值的问答答案可以直接归档回 wiki/queries/ 并触发 re-ingest，把"查询的产出"也变成"编译产物"的一部分。探索会复利，而不是消散在聊天记录里。

## 五、为什么是现在：知识层的"编译"运动正在合流

llm_wiki 不是孤例，而是 2026 年"记忆/知识持久化"运动的一个浪头。把它放进坐标系：

- **Karpathy 的 llm-wiki.md gist**：模式宣言。gist 本身还推荐了 qmd（本地 Markdown 混合检索引擎，BM25/向量 + LLM 重排）和 Obsidian Web Clipper 作为配套工具——示范了"编译制知识库"的工具链生态。
- **Hugging Face 博客《Give Your Coding Agents a Memory You Own》（Funes，9 月 3 日）**：给编码 Agent 一个"你拥有的记忆"——同一个主题的另一条实现路径：记忆应该用户自持、可审计，而不是锁在厂商的托管向量库里。
- **同期 GitHub Trending 的 hyperresearch（+153 星/日）**：Agent 驱动的研究知识库——Agents 收集、搜索、综合网络研究，写进持久化的可搜索 wiki；**alphaXiv OpenResearch（Rust）**：并行研究 Agent。三个项目不约而同选择了"wiki 作为 Agent 的持久记忆介质"。

这波合流的底层逻辑是**经济学**。RAG 是 query-time 税：每一次问答都付一次检索 + 拼装 + 生成的 token 和延迟，且知识零积累；wiki 是 write-once, read-many：ingest 时付一次编译成本（Analysis + Generation 两次 LLM 调用），之后每次查询只是"读已编译产物 + 小规模图扩展"。配合增量缓存，后续 ingest 只对变更文件付费。**第一次查询 RAG 赢，第 100 次查询 wiki 赢**——而知识管理本质上是一个"第 100 次查询"的游戏。更重要的是质量维度：wiki 里矛盾已被标记、综合已反映全部阅读史、交叉引用已存在；RAG 每次都在赌"这次检索能把碎片拼对"。

## 六、批判与边界：编译制知识库的死穴

作为值得认真对待的范式，它有三个边界必须点破。

**第一，幻觉会在编译期固化——这是最危险的一条。** RAG 的错误是"临时的"：每次查询重新生成，错了下次还有机会；wiki 的错误是"持久的"：一旦错误的页面被写进编译产物，它会被后续所有查询当作既成事实引用——**编译错误会传播**（就像 C++ 里一个错误的头文件污染所有 includer）。Karpathy 用"人类策展、LLM 维护"和 Lint 操作来对冲，llm_wiki 补了 Async Review System（LLM 标记需要人类判断的项目）。但本质上，编译制知识库把"幻觉风险"从查询期转移到了编译期，**风险没有消失，只是换了时间点**——它要求 ingest 阶段有更强的人机协作纪律（一次一源、逐条 review），这对"批量灌入"场景是摩擦。

**第二，它是"累积型知识"的抽象，不是"实时数据"的抽象。** 股价、系统状态、依赖版本这些每次都要重新推导的动态信息，编译制是错误隐喻——你的"编译器"再快也追不上数据变化。llm_wiki 的适用域是研究、阅读、领域深潜、竞争分析这类"越读越厚"的知识；判断一个场景适不适合 wiki 范式，只需问一句：**"这份知识的价值在于'历史积累'还是'当前状态'？"**

**第三，"编译警告"不是"编译错误"——没有类型系统兜底。** 真正的编译器有类型系统在编译期拒绝非法程序；而 wiki 的矛盾检测靠提示词，Lint 的结果是"建议"而非"阻断"。llm_wiki 的修复手段（图洞察、孤立页警告、社区凝聚力评分）本质是*启发式静态分析*，它能让问题可见，但不能保证问题被消灭。当 wiki 规模大到超过 LLM 单次上下文能审视的范围，一致性维护会指数变难——这是所有"LLM 写文件"方案共同的天花板。

## 结语：知识层正在经历软件工程走过的那条路

llm_wiki 的 1.9 万星，是 2026 年开发者对"知识必须积累"的一次集体确认。把它和记忆系统的整条技术脉络连起来看（[记忆是剂量，不是开关](2026-08-19-agent-memory-dosage-calibration-context-database.md)、[超越 Agent 记忆系统的技术路径](超越Agent记忆系统的技术路径.md)、[多向量检索范式的复兴](2026-08-31-multivector-late-interaction-retrieval-paradigm.md)），会发现一条清晰的主线：**AI 知识层正在重演软件工程的演进史——从解释执行走向编译 + 增量构建 + 链接器 + 静态分析。** RAG 不会死，但它会从"默认范式"降级为"可选组件"——就像今天没人再用解释器跑生产级应用，但脚本场景里它依然顺手。

下一个值得盯的方向有两个：一是 wiki 的"类型系统"——结构化 schema 校验、版本化、冲突的确定性解决，让"编译警告"变成"编译错误"；二是多 Agent 协作写——当多个 Agent 共享一个 wiki 时，"谁改了实体页、为什么改"需要真正的 VCS 语义（我们此前分析过 [Atlas 与 Agent 时代的源代码管理](2026-09-03-atlas-source-control-for-agents.md)，这正是它的用武之地）。而 llm_wiki 已经给出了正确的第一步：**把知识当代码对待，让 AI 当那个永不休息的编译器。**

---

*参考：GitHub Trending 2026-09-12（llm_wiki 18,720 星 / 今日 +647）；llm_wiki README 与架构文档（nashsu/llm_wiki，基于 Karpathy llm-wiki.md 模式）；Andrej Karpathy《llm-wiki.md》gist（2026）；Hugging Face Blog《Give Your Coding Agents a Memory You Own》（2026-09-03）；GitHub Trending：hyperresearch、alphaXiv/OpenResearch（2026-09-12）；llm_wiki 检索管线 benchmark（召回率 58.2% → 71.4%）。*