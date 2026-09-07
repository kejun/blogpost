# 当 Agent 变成自己的训练数据工厂：Hermes Agent 24 万星背后的闭环学习架构

> 技能自创、轨迹压缩与"提示缓存神圣不可侵犯"——Nous Research 用 13 个月证明，Agent 的下一个战场不是更强的模型，而是"会用、会记、会反哺"的系统。

2026 年 9 月 7 日，GitHub Trending 的前排出现了一个熟悉又特殊的身影：Nous Research 的 **Hermes Agent**，24.2 万星、4.98 万 fork、**40,354 个 open issues**。说它熟悉，是因为这个项目从 2025 年 7 月诞生起就一路狂奔；说它特殊，是因为它和昨天霸榜的 Ponytail（12.7 万星）完全不同——Ponytail 用一套 prompt 让 Agent"像最懒的资深工程师一样思考"，而 Hermes Agent 是一个 **899MB 的完整自改进系统**：同一个 agent 核心横跨 CLI、TUI、Electron 桌面端和覆盖约 20 个平台的通讯网关，自带技能自创、跨会话记忆、定时任务、子代理委派，甚至内置了一条为下一代模型生产训练数据的批量轨迹管线。

这不是又一个"会写代码的助手"。这是第一个把 **"Agent 即数据采集仪"** 写进产品定位的开源项目。本文从源码层面拆解它的闭环学习架构，并回答一个更本质的问题：当 Agent 开始制造训练自己的数据，开源社区的信任、隐私与评估体系准备好了吗？

---

## 一、先看数据：这不是"又一个 star 泡沫"

在 2026 年，star 数已经成为一个被污染的信号。昨天文章里的 Ponytail（129K 星）、今天同框的 ECC（251K 星，自挂 "GitHub Trending Repository of the Day" 徽章）都在提醒我们：**star 可以刷，提交不会骗人**。让我们用硬数据给 Hermes Agent 做个体检：

| 指标 | 数值 | 解读 |
|------|------|------|
| Stars / Forks | 242,529 / 49,879 | 13 个月积累，非脉冲式暴涨 |
| Open Issues | 40,354 | 社区参与度极高，也是维护债务 |
| 仓库体积 | ~899 MB | 全栈代码库，非单文件 prompt |
| 最近推送 | 2026-09-06 | **昨天仍在提交** |
| 发布节奏 | v0.20.3 → v0.21.0（8/16 → 8/31，周更） | 稳定迭代，两周 7 个版本 |
| PR 编号 | #70328、#104568 并存 | 社区贡献量级惊人 |
| License | MIT | 无附加条款 |
| 主导者 | teknium1（Nous Research 创始人） | 机构级背书 |

几个值得注意的细节。PR 编号跨度（#70328 与 #104568）说明合并流水线极其繁忙，9 月 6 日的提交包括"**从 provider 自身 usage 中学到的 per-image token 成本**"（#70328）和"API 调用日志携带 cache write count 与 provider response id"——这些不是营销功能，而是围绕**缓存经济学**和**计费可观测性**的硬核工程。40K open issues 是双刃剑：一方面证明真实用户量巨大，另一方面也意味着 triage 需要自动化——事实上这个项目的贡献评审规则里明确写着"automated triage sweeper"，AI 审 AI 的 issue，已经是 2026 年的开源常态。

---

## 二、设计内核：两条"不可侵犯"的不变式

Hermes Agent 的 `AGENTS.md` 是一份罕见的工程文档，它把整个代码库的决策原则压缩成了两条不变式，并且每条都直接对应具体实现。这两条原则，是理解这个项目一切设计的一把钥匙。

### 不变式一："Per-conversation prompt caching is sacred"

> 一个长寿的会话每一轮都复用缓存的 prompt 前缀。任何在对话中途改变历史上下文、替换工具集、重载记忆或重建 system prompt 的行为都会使缓存失效，成倍增加用户成本。我们不做这种事；**唯一例外是上下文压缩**。

翻译成人话：在 2026 年，**prompt 缓存是 Agent 账单的地基**。Anthropic、OpenAI 的缓存价格通常是标准输入价的 1/10 甚至更低，一个长期会话只要前缀不变，每一轮都能命中缓存，成本可以下降一个数量级。Hermes 把这条经济学定律提升到了"神圣不可侵犯"的架构高度：

- **缓存感知命令设计**：任何会变更 system prompt 状态的斜杠命令（装技能、换工具、改记忆）默认**延迟失效**——本次会话继续用旧缓存，下次会话才生效；想要立即生效必须显式加 `--now` 参数（`/skills install --now` 是范式示例）。
- **副作用隔离**：`/learn` 等命令被设计成"普通的一轮对话"，通过现有工具收集素材再写技能文件，**不引入 model-tool 足迹**，从而不破坏缓存前缀。
- **唯一的例外是压缩**：当上下文逼近窗口上限，压缩是被允许的缓存破坏——因为它发生在会话必须"续命"的临界点，收益远大于损失。

这条原则的普适价值在于：**它把"状态变更"从免费操作变成了有显式成本的操作**。大多数 agent 框架把 system prompt 当作可以随意读写的全局变量，只有被账单毒打过的人才知道，每一次"聪明的动态注入"都在悄悄掏空用户的钱包。Hermes 用一条架构红线，把缓存经济学变成了设计约束——这是值得每一个 agent 基础设施团队抄走的模式。

### 不变式二："Core is a narrow waist; capability lives at the edges"

> 每个模型工具都会随每次 API 调用发送，所以新核心工具的门槛极高。新能力应该以 CLI 命令 + 技能、服务门控工具或插件的形式出现，而不是扩充核心。

这是 Unix 哲学的 Agent 版：**核心做窄，边缘做厚**。仓库结构完美体现了这一点——`agent/` 目录里是核心循环（conversation_loop、context_compressor、retry_utils），而浏览器、Google Meet、Spotify、看板、图像生成、cron provider、模型提供商适配……全部以**插件**形式存在（`plugins/` 下有 plugin_loader、plugin_storage、plugin_utils 和十几个功能插件）。技能则按领域分目录存放（apple、devops、research、software-development、web……），带 `index-cache`。

这两条不变式合在一起，形成了一个有趣的推论：**Hermes 的核心是"记忆与压缩"，而不是"工具"**。工具是可插拔的边缘，记忆与上下文管理才是不可动摇的腰部——这解释了为什么 `hermes_state_*.py` 有 20 多个文件。

---

## 三、闭环学习：技能自创、记忆推送与"越用越懂你"

Hermes Agent 的 slogan 是 "The agent that grows with you"。这不是修辞，而是一套真实的闭环：

**复杂任务完成 → 自动沉淀技能 → 技能在使用中自我改进 → 会话记忆持久化 → 跨会话检索 → 用户建模**

### 3.1 `/learn`：把"刚才做的事"变成可复用技能

`agent/learn_prompt.py` 的 docstring 说得很清楚：`/learn` 构建"**那一个 prompt**"，把用户描述的任意素材（代码目录、文档 URL、"我们刚才做的事"、粘贴的笔记）变成可复用的技能。关键设计是它**不引入蒸馏引擎**——live agent 用自己现有的工具收集素材，再通过 `skill_manage` 按规范写技能文件，因此"本地、Docker、远程后端行为完全一致"。

更值得学习的是它内置的 **HARDLINE 技能创作规范**（AGENTS.md 中标注 "HARDLINE" 的规则，维护者评审时强制执行）：

```markdown
Frontmatter:
- name: 小写连字符，<=64 字符，无空格
- description: 一句话，**<=60 字符**，以句号结尾。
  描述能力而非实现。禁止营销词（powerful/comprehensive/seamless...）。
  ⚠️ 这是被违反最多的规则，而且不是装饰性的：
  system-prompt 技能索引会把描述截断到 60 字符并**每个会话加载**，
  超过第 60 个字符的内容会被静默截掉，永远无法被路由命中。
  写完后数一下字符数；超过 60 就删，别赌。
- version: 0.1.0
- author: 永远写字面值 "Hermes"，绝不从宿主环境读取
  （OS 用户名、git config、任何可探测的身份都不行）。
  技能会被分享和发布，环境派生的名字是用户从未同意过的隐私泄露。
```

这段规范信息量极大，藏着三层洞察：

1. **路由瓶颈是上下文，不是检索能力**。技能描述被截断到 60 字符且每个会话都加载——因为技能索引要常驻 system prompt，而 system prompt 的每一 token 都在烧缓存。所以技能发现不是 RAG 问题，是**预算内路由问题**：60 字符内必须说清"这个技能什么时候该用"。
2. **描述质量 = 路由准确率**。"描述能力而非实现"、禁止营销词，本质上是把"技能触发"变成可预测的分类问题——这比很多团队放任模型自由发挥要严谨一个数量级。
3. **隐私是写进 lint 规则的**。`author` 字段强制为字面值 "Hermes"，因为技能会被分享（agentskills.io 开放标准兼容），环境派生的用户名就是一条隐蔽的隐私泄露通道。这是我在开源 agent 项目里见过的最早把"技能可传播性"纳入安全建模的设计之一。

### 3.2 记忆系统：Provider 契约与压缩前 checkpoint

`agent/memory_manager.py` 定义了 Hermes 的记忆架构，几个细节非常硬核：

- **扇出模型**：MemoryManager 把记忆钩子扇出到注册的 Provider；内置 Provider 永远允许，但**同一时刻只允许一个外部插件 Provider**——理由写得很直白："tool-schema bloat, conflicting backends"（工具 schema 膨胀、后端冲突）。
- **压缩前 checkpoint 契约**：`PRE_COMPRESS_CHECKPOINT_API_VERSION` 表明，记忆 Provider 必须实现"上下文压缩前落盘"的回调——因为压缩一旦发生，旧上下文的细节就永远消失了，记忆系统必须在压缩发生前完成 checkpoint，否则就是永久性数据丢失。
- **签名内省（duck-typing 兼容）**：`_signature_params` / `_accepts_require_checkpoint` 用 Python 内省判断 Provider 是否接受 `require_checkpoint` 关键字参数，老版本 Provider 走 best-effort v1 契约——渐进兼容，而不是强制升级。

配合仓库里的状态层（`hermes_state_*.py` 家族：FTS5 会话全文检索、WAL、schema、repair、portability、readpool、registry、guard），Hermes 的记忆不是"把聊天记录塞进向量库"的玩具，而是一个带损坏修复、可移植、支持并发读的**持久化子系统**。跨会话检索走 FTS5（SQLite 全文索引）+ LLM 摘要，用户建模接 Honcho 的辩证式建模（dialectic user modeling）——不同机制各司其职：FTS5 管"找得到"，摘要管"读得懂"，Honcho 管"猜得准"。

---

## 四、数据飞轮：Agent 即训练数据工厂（本文最想让你看到的）

如果说上面还都是"好的 Agent 工程"，那 Hermes Agent 真正独一无二的地方在于：**它是 Nous Research 的训练数据采集仪**。README 的 "Research-ready" 一节写得明明白白：

> Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.
> （批量轨迹生成、轨迹压缩，用于训练下一代工具调用模型。）

这意味着什么？Nous Research 是训练模型的组织（Hermes 系列模型、与 DisTrO 分布式训练齐名的开源先锋），而 Hermes Agent 在真实世界里跑出的每一段"任务轨迹"——浏览器操作、代码修改、工具调用序列——都是下一代理模型最稀缺的训练燃料：**真实的、长尾的、带工具交互的工具调用数据**。开源模型社区最缺的不是预训练 token，而是高质量的 agent 轨迹数据；与其去爬合成数据，不如让自家 agent 在 40K open issues 的用户手里跑出真实轨迹。

### 4.1 `trajectory_compressor.py`：为训练数据定制的"瘦身算法"

轨迹数据不能直接进训练管线——一条真实任务轨迹动辄几万 token，其中充斥着无效探索。`trajectory_compressor.py` 把"压缩轨迹"做成了一个可配置的工业流程，其策略设计非常讲究：

```
保护策略：
- 永远保护头部 4 件套：第一条 system（工具定义）、第一条 human（原始请求）、
  第一条 gpt（初始响应/首个 tool_call）、第一条 tool（首个动作结果）
  —— 这是任务意图与工具契约所在，压缩它们等于毁掉样本的可学习性
- 永远保护尾部最后 4 个完整回合对（gpt+tool 或 gpt only）
  —— 模型的最终动作与结论必须原样保留
- 只压缩中间部分，且"按需"压缩：能不动就不动，动多少算多少
- 绝不拆散 tool_call / tool_response 对

参数配置（datagen-config-examples/trajectory_compression.yaml）：
- tokenizer: moonshotai/Kimi-K2-Thinking   ← 用目标模型家族的 tokenizer 数 token
- target_max_tokens: 29000                  ← 单条压缩后预算
- summary_target_tokens: 750                ← 每段摘要的预算
- 摘要模型: google/gemini-3-flash-preview（OpenRouter，temp 0.3）
- 并发: 4 workers / 50 并发摘要请求 / 单条超时 300s
- 压缩后向 system 追加提示：
  "Some of the conversation may be summarized to preserve context."
```

几个设计选择的深意：

1. **钣金哲学**：头尾保护、中间摘要，本质上和程序员的"代码审查只看 diff"是同一个道理——**意图在头，结论在尾，中间是过程**。对训练而言，过程的细节价值低于意图-结论对，但完全丢弃过程又会让模型学不会"如何走到结论"。所以用 750 token 的摘要保留过程的骨架。这是对"上下文压缩"研究的工程化落地，而且它明确写成**绝不拆散 tool_call/response 对**——因为工具调用的配对结构是训练下一代 tool-calling 模型的核心信号。
2. **用目标 tokenizer 计数**：选择 Kimi-K2-Thinking 的 tokenizer 不是偶然——压缩的目标是"喂给下一代模型"，token 预算必须按目标模型家族的口径计算，而不是按摘要模型的。
3. **摘要模型与主模型分离**：gemini-3-flash 负责压缩，廉价快速（temp 0.3 保证确定性），主模型只消费压缩结果。这是 2026 年最标准的"模型管道分工"范式。

### 4.2 批量数据流水线：从浏览器任务到 SWE-bench

`datagen-config-examples/` 目录揭示了完整的数据生产线：

- `example_browser_tasks.jsonl` + `run_browser_tasks.sh`：**浏览器任务批量生成**——让 agent 执行真实的网页任务，产出带完整浏览器交互的轨迹
- `web_research.yaml`：研究型任务的轨迹采集配置
- `trajectory_compression.yaml`：压缩环节
- 仓库里还有 `batch_runner.py`（批量运行器）和 `mini_swe_runner.py`（迷你 SWE 运行器）

也就是说，这条管线可以**按需合成特定分布的数据**：想要更多浏览器操作样本？跑 browser tasks；想要更多代码修复样本？跑 SWE 任务；然后统一压缩、统一格式、进训练集。对于模型训练机构，这等于拥有了一台**可以编程的数据合成机**——而驱动它的，正是每天在真实用户手里运行的 24 万星社区。

这个定位也反过来解释了 Hermes Agent 的一些产品决策：为什么它坚持"同一核心横跨 20 个平台"？因为平台多样性 = 轨迹多样性 = 数据多样性。为什么它支持 7 种终端后端（本地/Docker/SSH/Singularity/Modal/Daytona/Vercel Sandbox）甚至 serverless 休眠？因为部署场景越广，采集到的轨迹越接近真实世界的长尾分布。

---

## 五、工程亮点：缓存经济学、上下文压缩与 ACP 桥接

### 5.1 缓存感知的日志与计费

9 月 6 日的提交"API call log 携带 cache write count 与 provider response id"，配上"per-image token 成本从 provider 自身 usage 学习"——Hermes 的账单系统不是估算，是**按 provider 实际计费口径回填**。多模态输入（图片）的 token 成本因模型而异，用 provider 返回的真实 usage 反推 per-image 成本，才能给出精确的用量审计。在 agent 时代，"token 用量可观测性"正在成为和"延迟可观测性"同等重要的基础设施，Hermes 把它做到了 provider 粒度。

### 5.2 上下文压缩家族

`agent/` 下的 `compression_facade.py`、`context_compressor.py`、`conversation_compression.py`、`manual_compression_feedback.py` 构成一个完整的压缩子系统——注意 `manual_compression_feedback`：**压缩后允许用户反馈**，把"压缩得好不好"变成可迭代的闭环。结合前面提到的"压缩是缓存神圣性的唯一例外"，Hermes 实际上把"什么时候压缩、压缩多少、压缩后如何保证记忆不丢（checkpoint 契约）"做成了核心腰部能力。

### 5.3 多 Provider 与 ACP 桥接

`agent/` 里有 anthropic_adapter、bedrock_adapter、azure_identity_adapter、codex_runtime、copilot_acp_client、acp_openai_bridge——Hermes 不锁死任何模型生态，甚至实现了 **ACP（Agent Client Protocol）桥接**，可以以 ACP 客户端的身份对接其他 agent 运行时。这延续了 2026 年 agent 互操作性的大趋势（本博客 7 月 7 日分析过跨 agent 协议危机），但 Hermes 的做法更彻底：**模型无关 + 运行时无关**，连"agent 调 agent"都纳入了插件体系。

---

## 六、批判性反思：光环之下的四个问号

写了这么多亮点，也该泼几盆冷水。Hermes Agent 的繁荣背后，有几个问题值得所有关注者冷静审视：

**1. star 通胀时代的信任问题。** 242K 星是真实的（Nous 的机构信誉、teknium1 的持续 commit、周更发布都可验证），但它与 ECC 的 251K 星同框出现，本身就是 2026 年的黑色幽默——一个自挂 "Trending of the Day" 徽章、8 个月刷到 25 万星的仓库，和一个人均 2 万星/月的机构级项目，在 Trending 列表里看起来"一样火"。**star 作为质量信号已经失效，commit 历史、发布节奏、issue 响应才是新的信任锚点。**

**2. 40K open issues 的另一面。** 它可以解读为"社区繁荣"，也可以解读为"维护债务失控"。当 triage 都依赖自动化 sweeper 时，普通用户的 issue 有多大几率被真正的人类维护者看到？24 万星的项目如果 issue 解决率跟不上，社区热情会以同样的速度反噬。

**3. "自我改进"缺乏可评估的闭环。** Hermes 号称技能会自创、会自我改进、记忆会积累，但**没有任何公开基准证明"越用越强"**——没有对照实验显示"用了 3 个月的 Hermes 在任务成功率上超过新装的 Hermes"。技能的自创与改进，目前更像是"把经验固化成文件"，而"文件变能力"这件事，仍然是 prompt 层面的信仰。`evals/` 目录存在，但公开的、可复现的"学习收益"数据还付之阙如。技能索引 60 字符截断的设计也暴露了天花板：**技能的积累上限，最终还是上下文预算**——存得下不等于用得上。

**4. 数据飞轮的伦理深水区。** 用真实用户轨迹训练"下一代工具调用模型"，隐私与许可问题远比 `author: Hermes` 一处设计复杂。用户知道自己的操作轨迹正在成为训练数据吗？轨迹压缩后的摘要噪声会不会污染下一代模型的行为分布（压缩器偏好 → 训练分布偏移）？当"开源 agent"同时也是"数据采集仪"时，**双用途（dual-use）问题从模型下沉到了 Agent 层**——这是 2026 年开源社区还没有准备好回答的问题。

---

## 七、结语：给做 Agent 的人的五条借鉴

Hermes Agent 值得抄的，不是它的功能清单，而是它的**设计约束**：

1. **把缓存经济学写进架构红线。** 任何 agent 团队都应该问自己：我的 system prompt 是可缓存的吗？状态变更默认延迟生效吗？——这两问能省下用户 80% 的隐性账单。
2. **核心窄腰，边缘插件。** 每多一个"核心工具"，就是给每次 API 调用加一份 schema 重量。能力放边缘，核心只留记忆与压缩。
3. **技能规范要 lint，不要信仰。** 60 字符描述、禁用营销词、禁止环境派生 author——把"技能质量"变成机器可检查的规则，而不是"希望模型自觉"。
4. **学习闭环要有 checkpoint 契约。** 记忆系统必须在压缩前落盘，Provider 接口要做签名内省式的渐进兼容——这些细节决定了记忆系统是资产还是负债。
5. **数据管线要可编程。** 轨迹压缩（保护头尾、不拆工具对、按目标 tokenizer 计数）这套方法论，不仅属于模型训练机构——任何想用 agent 沉淀领域数据资产的团队，都值得照抄一份。

2026 年的 Agent 竞赛已经进入第三阶段：第一阶段拼"能不能跑任务"，第二阶段拼"跑得好不好"，而 Hermes Agent 站上了第三阶段的起跑线——**拼"跑完任务之后留下了什么"**。当 Agent 留下的不再是日志，而是可复用技能、结构化记忆和下一代的训练数据，它就从一个工具，变成了一条自我强化的飞轮。至于这条飞轮会带着开源社区飞向哪里——是"人人可用的社会性记忆"，还是"无孔不入的行为数据工厂"，取决于每一个使用它的人今天做出的选择。

---

*数据来源：GitHub API（2026-09-07 抓取）、github.com/NousResearch/hermes-agent 源码与 README、datagen-config-examples 配置、GitHub Trending 当日榜单。*