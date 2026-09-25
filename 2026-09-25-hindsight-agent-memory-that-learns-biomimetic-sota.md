# 当记忆开始"学习"：Hindsight 2.7 万星背后——从榜单中游到 91.4% 的 Agent 记忆逆袭，与 Jev 重排器的六条教训

> 2026-09-25 · 记忆系统 · 本文约 4700 字

## 全站第一的记忆系统

先看今天（9 月 25 日）GitHub Trending 的第一名：

**vectorize-io/hindsight**，27,758 stars、2,680 forks，单日新增 **1,668 星**——这个日增速在全站所有语言、所有品类中排第一。仓库开源仅 11 个月（2025 年 10 月 30 日创建），MIT 协议，Python 主体，最近一次 push 距离本文写作只有几个小时，PR 编号已经排到 4400+。

它的定位只有一句话：**"Agent Memory That Learns"（会学习的 Agent 记忆）**。README 开宗明义地把矛头对准了整个赛道："大多数 Agent 记忆系统专注于召回对话历史。Hindsight 专注于让 Agent 学习，而不只是记住。"

这个博客的读者可能对这个名字有印象。今年 4 月的[《AI Agent 记忆系统 2026 技术状态》](https://github.com/kejun/blogpost/blob/main/2026-04-08-ai-agent-memory-state-2026-architecture-benchmark.md)盘点过当时的记忆系统格局：在那份基于 LOCOMO 的榜单里，Hindsight 综合分 0.73，排在 Zep（0.77）等系统之后，属于"中游偏上、有想法但没证明自己"的选手，我们当时给它贴的标签是"MCP 协议型记忆"。

五个月过去，局面完全变了。

## 关键数据一览

| 维度 | 数据 |
|------|------|
| Stars / Forks / 开放 Issue | 27,758 / 2,680 / 191（2026-09-25，GitHub API） |
| 单日新增 | +1,668（GitHub Trending 全站第一） |
| 创建时间 | 2025-10-30（约 11 个月） |
| 许可 / 语言 | MIT / Python |
| 最新版本 | 0.10.1（2026-09-21）；7 月底至 9 月中 8 周发了 6 个版本 |
| Benchmark | LongMemEval **91.4%**、LoCoMo **89.61%**（此前最强开源系统 75.78%） |
| 小模型逆袭 | 开源 20B backbone：同底座全上下文基线 39% → **83.6%**，超过全上下文 GPT-4o |
| 独立复现 | Virginia Tech Sanghani 中心 + 《华盛顿邮报》（竞品分数多为厂商自报） |
| 论文 | [arXiv:2512.12818](https://arxiv.org/abs/2512.12818)《Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects》 |
| 生态 | 25+ LLM 提供商、60+ 集成、18 个 coding agent 一键接入、MCP 原生 |
| 存储 | PostgreSQL + pgvector / Oracle AI Database 23ai（企业级全功能对等）/ 内嵌 pg0 |
| 部署 | Docker、pip、Helm、单机内嵌（无服务器）、Cloud（usage-based + 99.9% SLA） |
| 生产用户 | Fortune 500 企业（官方口径） |

需要说明时间线：论文提交于 2025 年 12 月，SOTA 分数并非这五个月才刷出来的。真正的逆袭故事在于——4 月时它还是榜单上"自报分数存疑"的众多玩家之一，9 月时它已经完成了 benchmark 的第三方独立复现、8 周 6 个版本的功能狂飙、18 个 coding agent 的生态卡位，以及 Fortune 500 的生产落地。**分数只是入场券，工程速度和生态密度才是它甩开身位的原因。**

## 架构拆解：仿生四层记忆与三个动词

Hindsight 论文里对现有系统的批评非常直接：当前一代记忆系统把记忆当成"外挂层"——从对话里抽取显著片段、存进向量库或图库、检索 top-k 塞回提示词。这套做法有三个原罪：**混淆证据与推断**（把"用户说过 X"和"系统推测 Y"混在一锅里检索）、**无法在长时间跨度上组织信息**（事实平铺，越攒越乱）、**难以解释推理**（说不出答案是从哪条记忆来的）。

它的解法是一套"仿生数据结构"，把记忆组织成四个逻辑网络：

- **World facts（世界事实）**：关于世界的客观知识——"炉子会烫手"；
- **Experiences（经历）**：Agent 自己的第一人称经验——"我碰了炉子，很疼"；
- **Observations（观察）**：从大量记忆中整合出的、有证据支撑的信念；
- **Mental models（心智模型）**：从观察和事实中综合出的、对 Agent 所处世界的理解。

四层之上是三个核心操作，也是 API 的全部动词：

```python
# Retain：写入记忆（LLM 抽取事实/时间/实体/关系 → 规范化 → 多重索引）
client.retain(bank_id="my-bank", content="Alice got promoted to senior engineer",
              context="career update", timestamp="2025-06-15T10:00:00Z")

# Recall：四路并行检索（语义向量 / BM25 关键词 / 实体-时间-因果图 / 时间窗过滤）
# → RRF 融合 → cross-encoder 重排 → 按 token 预算裁剪
client.recall(bank_id="my-bank", query="What does Alice do?")

# Reflect：对记忆做深度分析，形成新连接，回答"需要思考而非查找"的问题
client.reflect(bank_id="my-bank", query="What should I know about Alice?")
```

其中最有意思的设计是 **Observations 的"信念修正"机制**。后台进程持续把相关事实整合成去重后的观察，每条观察保留支撑证据的**原文引用和证明计数（proof count）**；新证据到来时，观察是被**精炼（refine）而非覆盖**——新信息可以强化、削弱或扩展一个既有信念，而不是悄悄替换它。这正是对"证据与推断混淆"的正面回答：检索出来的每条结论都能回溯到原始引文，Agent 解释自己的推理时不需要编造。

另一个细节是 **Bank（记忆库）** 的抽象：一个 bank 就是一个"大脑"，服务一个用户、一个 Agent 或一个项目，隔离是严格的（无跨库泄漏）。Bank 还携带 **disposition traits（性情特质）**——怀疑度、字面化程度、共情度——这些特质会影响 reflect 在其记忆上如何推理。给记忆系统装"性格旋钮"，这在 4 月我们盘点的那批系统里还没有出现过。

## Knowledge Pages：记忆编译出自己的 wiki

如果说四层架构是论文里的 Hindsight，那么今年夏天最大的产品创新是 0.9.0 引入的 **Knowledge Pages（知识页）**——也是我认为对整个行业最有启发的部分。

一个 knowledge page 是 bank 写给自己的"活文档"，回答一个固定问题（比如"我们的错误处理约定是什么？"），并随着 bank 学到更多而自动重写。页面组织成 wiki 式的文件夹树，`hindsight fs mount` 可以把整棵树投影到磁盘上成为普通 markdown 文件——`ls`、`grep`、编辑器、Agent 的文件工具全都直接可用。0.9.2 又把知识库暴露为原生 MCP surface（7 个工具），Agent 用连接 retain/recall 的同一条 MCP 连接就能维护自己的 wiki。

关键的设计哲学藏在文档的一句话里：**"页面是投影，不是存储"（a page is a projection, not storage）**。删掉一个页面不会丢失任何东西，因为它随时可以从已经抽取、去重、调和过的记忆中重建；页面反映的是"当前成立的认知"，而不是"所有人说过的所有互相矛盾的话"。

读过本博客 9 月 12 日[《当知识库开始"编译"》](https://github.com/kejun/blogpost/blob/main/2026-09-12-llm-wiki-compiled-knowledge-rag-interpreted.md)的读者会立刻认出这个思想：RAG 是"解释执行"——每次查询重新检索、重新拼装、重新生成；而编译制知识是"编译一次、持续保鲜"。llm_wiki 把这个理念做成了个人知识库产品，Hindsight 则把它做成了 Agent 记忆系统的内建层——**mental model 的读取是一次数据库读，不调检索、不调 LLM**，Agent 每次启动时直接带着"已settled 的知识页"开工，而不是每个 session 重新发现世界。两条独立演化的产品线在同一个架构判断上会师，这基本可以确认："编译式记忆"不是某一家的奇思妙想，而是行业共识正在形成。

## 0.10 波次：能看见的记忆、可搬家的记忆

9 月的两个版本（0.10.0 / 0.10.1）把 Hindsight 推上了今天的 trending 第一，值得单独拆两个功能。

**其一：多模态记忆与事实级溯源。**0.10.0 之前，支持工单里的截图对记忆系统是隐形的——图里印着的 request ID 对 Agent 来说等于不存在。现在 retain 的 content 可以是文本、图片、文件的有序混合块，图片按其在序列中的位置被阅读（两段文字之间的图表，就按"两段文字之间的图表"来理解）。更硬核的是溯源粒度做到了 **fact 级**：recall 返回一条事实时，可以附带它被抽取自的那一张截图，而不是"这个 chunk 里的所有图片"。当归属不确定时，系统的选择是**丢弃而非就近猜测**——官方的原话是"一条没有引用的事实，好过一条引用错误的事实"。在幻觉治理上，这是一个值得所有 RAG 系统抄走的默认值。

**其二：Bank 可移植。**0.10.1 让一个 bank 可以被 clone、export、import、原地 rename。配套博客[《Bring the Facts, Not the Beliefs》](https://hindsight.vectorize.io/blog/2026/09/23/bring-facts-not-beliefs)讲了一个反直觉的迁移哲学：迁移记忆历史时，**导入原始事实材料，让目标 bank 自己重建信念**，而不是把旧系统里已经凝结的结论直接搬过去——因为旧结论携带着旧系统的重复、偏见和已过时的推断。这个"迁事实、不迁信念"的原则，本质上是对"记忆系统之间存在有损格式转换"这一工程现实的诚实处理，和数据库迁移里"迁原始数据而非迁物化视图"是同构的。

顺带一提生态卡位：`npx @vectorize-io/hindsight-coding-agents install all` 一条命令把 18 个 CLI coding agent（Claude Code、Codex、Cursor、Copilot、opencode、Devin……）接到**同一个 per-repo bank** 上——bank 从 git 历史和过往 session 自动构建，注入正在开工的 Agent，外加持续保鲜的架构/约定/在途工作知识页。宣传语说得很准："你早上向一个 Agent 解释过的东西，下午打开另一个 Agent 时还在那里，**因为记忆属于项目，而不是属于工具**。"在 coding agent 混战、用户频繁换工具的当下，"跨工具的项目级记忆"是个非常聪明的中立位。

## Jev 重排器：六条写进生产系统的教训

0.10.1 还做了一件与本博客高度相关的事：把 TypeSafe 的 **Jev** 加为重排器（reranker）提供商。如果你读过 9 月 16-17 日关于 [System One Models 和 Jev 生态](https://github.com/kejun/blogpost/blob/main/2026-09-17-jev-system-one-ai-decision-layer-ecosystem.md)的两篇文章，会记得 Jev 的特殊性：它不产生文本，输入一段文字和一个类型化问题，输出带校准概率的类型化答案。当时我们判断这类"类型化决策模型"会在检索、路由、过滤等场景找到自己的位置——9 月 24 日 Hindsight 发布的[集成复盘](https://hindsight.vectorize.io/blog/2026/09/24/adding-jev-reranker-what-we-learned)，就是这个判断的第一份生产级验证，而且坦诚得罕见：两个失败的设计带着数字被写进了官方博客。

**教训一：显而易见映射是错的，listwise 打败 pairwise。**用 Jev 的 Noul（是/否概率）对每个候选问"这条相关吗"再排序，是最自然的设计——但仍然是成对判断：300 个候选就是 300 次网络往返、300 个互相看不见的独立判断。团队改用 Choice（多选一）把整个候选池一次提交，返回的概率分布直接就是排名。实测（200 题 LoCoMo）：listwise recall@1 **0.94** vs pairwise **0.87**，调用量只有后者的 **1/30**。背后的原理可以泛化到一切 LLM 评估场景：**相对判断比绝对判断容易**——"哪个最好"避开了打分制每次都要重新回答的问题：0.6 到底是什么意思？

**教训二：别给模型"以上都不是"的选项。**想在 Choice 里加一个 "none of these" 来表达"没有相关的"？实测 200 题里 **35 题返回全空**——因为 Choice 的选项是互相竞争 alternatives，"以上都不是"在难题上总是赢家。改用 Score（有序等级）问"相关性延续到第几条"才对。

**教训三：别给逃生舱。**在 Score 里加一个"没有相关内容"等级，同样的失败小一号重演：7% 的查询返回空，gold retention 从 0.81 掉到 0.65。最终设计上**故意不存在这个等级**——至少一条候选永远存活。同一个功能里两次栽在同一个坑，团队总结："给模型一个干净的说'没有'的方式，它说'没有'的频率就会远超数据支持的程度。"

**教训四：排序和过滤是两个产品决策。**剪枝（pruning）的精度数字非常漂亮：30 个候选平均只留 1.6 条，存活结果的精度从 0.051 提到 0.850，**17 倍**；真实 bank 上 300 条候选剪到 3 条。但它同时切掉 19% 的 gold evidence，且短名单封顶 12 条。团队的取舍：排序默认开（人人都想要更好的顺序），剪枝默认关（丢弃大部分候选池是"你的 Agent 是干什么的"这一产品问题——消费者是 LLM 提示词时这买卖划算，消费者是人或需要捞第 14 名的针时就不划算）。

核心性能对比（LoCoMo，对照默认的本地 MiniLM cross-encoder）：

| 配置 | recall@1 | recall@5 | NDCG@10 | 延迟/查询 |
|------|----------|----------|---------|-----------|
| 30 候选：本地 MiniLM（默认） | 0.800 | 0.876 | 0.850 | 0.12s |
| 30 候选：Jev（仅排序） | **0.950** | **0.966** | **0.957** | **0.027s** |
| 240 候选：本地 MiniLM | 0.583 | 0.719 | 0.682 | 0.41s |
| 240 候选：Jev（仅排序） | **0.783** | **0.903** | **0.856** | **0.063s** |

候选池越大差距越大——一边在做 240 次串行判断，另一边在做一次整体比较。但博客同样把丑话说全了：Jev 是第三方托管 API（自托管 Hindsight 就是为了数据不出门的部署直接不合格）、会 fail closed（需要配置 RRF 垫底的 fallback 链）、重排器是服务器级配置（多租户只能共用一个）。**分数、代价、失败模式一起给**，这才是工程复盘该有的样子。

## 不性感的工程，才是 Fortune 500 敢用的原因

夏天六个版本里最不显眼、可能最有价值的是成本和稳定性工程：

| 改动 | 版本 | 效果 |
|------|------|------|
| Anthropic Message Batches | 0.8.5 | retain/整合类负载 token 五折 |
| Anthropic prompt caching | 0.8.5 | 重复提示前缀不再全价计费 |
| 按操作设置 reasoning effort | 0.8.6 | 只在抽取等关键环节为推理付费 |
| retain 内存预算 | 0.9.2 | 45MB 文档的处理内存从 385MB 降为与文档大小无关的常数 |
| 纯 ASGI 请求路径 | 0.10.0 | 健康检查吞吐 2,476 → 7,917 rps（双核） |
| 免物化 ID 的 token 计数 | 0.10.0 | 单次 recall 的计数阶段 34.2ms → 5.0ms |

再加上企业刚需的周边：**Memory Defense**（按 bank 开关的写入防线，45 种密钥/PII 模式扫描，命中即脱敏成 `[REDACTED:github_token]` 或直接拒写）、**默认多语言**（输入语言端到端保留，实体保持原文字——"张伟"不会被规范化成 "Zhang Wei"，这对中文场景是实打实的细节）、Prometheus 指标、admin CLI、webhook、租户/鉴权/存储三类扩展点，以及 Oracle AI Database 23ai 的全功能对等支持。

Oracle 那条值得数据库从业者多看一眼：一个 MIT 协议的 Agent 记忆系统，把"存储后端"做成了可插拔层，Postgres 系与 Oracle 系平权。这印证了本博客 8 月 19 日在[《记忆是剂量，不是开关》](https://github.com/kejun/blogpost/blob/main/2026-08-19-agent-memory-dosage-calibration-context-database.md)里的判断——**Agent 记忆基础设施正在收敛为一个数据库问题**：向量、全文、图、时间序列四种索引的混合负载，加上事务性的信念修正，最终都要落在存储引擎上。谁能把这四种负载在一个引擎里跑好，谁就有资格接住这波记忆系统的需求。

## 三个判断

**判断一：记忆系统的竞争已经从"召回"进入"学习"阶段。**检索质量（recall@1 从 0.8 到 0.95）只是入场券，真正的差异化在证据/推断分离、观察精炼、心智模型重写这条"信念修正回路"上。只会存和取的系统会越来越像大宗商品——四路检索 + RRF + 重排的管线，任何一个有决心的团队三个月都能复刻；但"每条结论可回溯到原文引用、每次新证据触发信念的精炼而非覆盖"是一套需要长期打磨的数据模型。Hindsight 的护城河不在管线，在 schema。

**判断二：接入成本决定生态，生态决定标准。**Hindsight 这轮爆发的直接推手不是论文分数，而是"两行代码给现有 Agent 加记忆"的 LLM Wrapper（`wrap_openai(OpenAI(), bank_id="user-123")`，底层 LiteLLM 覆盖 100+ 模型）、18 个 coding agent 的一键接入、60+ 框架集成和 per-bank 的默认 MCP 端点。当"用上它"的成本低到接近零时，benchmark 上领先 5 个点和领先 15 个点的生态后果是一样的。这也是给所有基础设施创业者的教科书案例：先赢接入，再赢标准。

**判断三：类型化决策模型（System One）开始在生产系统里"打工"。**Jev 集成是 9 月我们分析 TypeSafe 时 predicted 的第一个大规模生产用例落地——而且落地方式很说明问题：它没有取代任何 LLM，而是嵌进检索管线里做那个"只需要排序、不需要说话"的环节，用 1/30 的调用量拿到更好的 recall。文本模型负责生成，决策模型负责判断，管线负责编排——这个三层分工，大概率会是未来两年 AI 应用架构的常态。

## 结语

4 月盘点记忆系统格局时，我们的结论是"这个赛道演进快得离谱，任何选型都应看架构可演化性而非单点分数"。五个月后，Hindsight 用自己的轨迹给这句话做了注脚：它 12 月发论文时是学术明星，4 月在第三方榜单里只是中游，9 月靠 8 周 6 个版本的工程狂飙和几乎零门槛的生态接入冲上全站第一。

对开发者的行动建议很直接：如果你在维护一个需要跨 session 积累的 Agent（尤其是 coding agent 或长期运行的 AI 员工），Hindsight 值得一个下午的评估——Docker 一行起服务，`pip install hindsight-litellm` 两行接记忆，内嵌 pg0 模式甚至不需要外部数据库。就算最终不用它，它的三个设计也值得抄进你自己的系统：**证据与推断分离、信念精炼而非覆盖、以及"没有引用的事实好过引用错误的事实"。**

记忆系统的终局不是更大的向量库，而是让 Agent 的每一次经历都变成它下一次决策的养料。Hindsight 的名字起得很准——事后诸葛亮不可怕，可怕的是每次事后都学不到东西。

---

## 参考链接

- GitHub: https://github.com/vectorize-io/hindsight
- 论文: Hindsight is 20/20: Building Agent Memory that Retains, Recalls, and Reflects (arXiv:2512.12818)
- 文档: https://hindsight.vectorize.io
- Benchmarks: https://benchmarks.hindsight.vectorize.io
- Jev 重排器复盘: https://hindsight.vectorize.io/blog/2026/09/24/adding-jev-reranker-what-we-learned
- 夏季版本总结: https://hindsight.vectorize.io/blog/2026/09/18/what-hindsight-learned-this-summer
- 相关旧文: [AI Agent 记忆系统 2026 技术状态](https://github.com/kejun/blogpost/blob/main/2026-04-08-ai-agent-memory-state-2026-architecture-benchmark.md) · [当知识库开始"编译"](https://github.com/kejun/blogpost/blob/main/2026-09-12-llm-wiki-compiled-knowledge-rag-interpreted.md) · [Jev 生态](https://github.com/kejun/blogpost/blob/main/2026-09-17-jev-system-one-ai-decision-layer-ecosystem.md) · [记忆是剂量，不是开关](https://github.com/kejun/blogpost/blob/main/2026-08-19-agent-memory-dosage-calibration-context-database.md)
