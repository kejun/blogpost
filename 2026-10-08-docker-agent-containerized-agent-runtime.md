# Docker Agent 深度解析：当 AI Agent 学会像容器一样被构建、分发与运行

> 2026 年 10 月 7 日，Docker 工程团队开源的 `docker-agent`（原名 cagent）冲上 Hacker News 首页，收获 163 点。这个时间点很微妙：Agent 框架已经多到令人疲倦，但真正把"分发"这件基础设施级问题解决掉的项目，屈指可数。Docker Agent 值得认真读一读，不是因为它是又一个 Agent 框架，而是因为它提出了一个不一样的问题：**如果 Agent 不是一段代码，而是一个可以被 push、pull、签名、版本化的制品，会发生什么？**

## 一、被忽视的痛点：Agent 的分发问题

过去两年，Agent 生态的叙事中心一直是"框架"：LangGraph 讲状态图，CrewAI 讲角色协作，AutoGen 讲对话编排，Claude Code / Codex 讲终端里的编码智能体。这些工具解决的是"如何把 Agent 写出来"。但当你真的要把一个调好的 Agent 交给同事、部署到 CI、或者复用到另一个项目时，会立刻撞上一堵墙——**Agent 是没有交付格式的**。

一个生产级 Agent 往往分散在十几个地方：系统提示词在一个 Python 字符串里，工具配置在环境变量里，MCP 服务器地址在另一个 JSON 里，某个 `temperature=0.3` 藏在代码深处。你想复用它，只能把整个仓库拷走，然后祈祷依赖版本一致。这与我们交付软件的方式形成了刺眼的反差：代码有包管理器，服务有容器镜像，而 Agent 只有"把仓库发给你"。

Docker Agent 的整个设计，就是冲着这个缺口去的。它首页的标语只有一句：**Run AI agents like containers.** 这句话不是营销，而是一整套架构选择的起点。

## 二、Docker Agent 是什么：一个声明式 YAML + CLI 插件

从形态上看，Docker Agent 是一个用 Go 编写的命令行工具（约 21MB Go 代码，Apache 2.0 许可，2025 年 9 月 1 日首次开源，截至发稿已迭代到 v1.149.0，贡献者超过 100 人）。它既可以作为 Docker Desktop 4.63+ 的 CLI 插件用 `docker agent` 调用，也可以通过 Homebrew 或二进制单独安装。

它的核心抽象极其克制——整个 Agent 定义就是一个 YAML 文件：

```yaml
agents:
  root:
    model: openai/gpt-5-mini
    description: A helpful AI assistant
    instruction: |
      You are a knowledgeable assistant that helps users with various tasks.
      Be helpful, accurate, and concise in your responses.
    toolsets:
      - type: mcp
        ref: docker:duckduckgo
```

跑起来只需要一行：

```sh
docker agent run agent.yaml
```

这里的关键选择是**声明式（declarative）**。在 Docker Agent 里，一个 Agent 由四样东西定义：`model`（模型）、`description`（描述）、`instruction`（系统提示词）、`toolsets`（工具集），再加上可选的 `sub_agents`（子智能体）。没有命令式代码，没有回调函数，没有状态机 DSL。YAML 是可读的、可版本化的、可 diff 的、可分享的。

这个选择直接决定了下游的一切能力：正因为 Agent 是纯数据，它才能被打包、被签名、被推送进 registry。这就是 Docker 的老本行。

## 三、架构拆解：Root Agent、内置工具集与"编排而非硬编码"

### 3.1 Root Agent 作为入口

每个配置都必须有一个 `root` Agent，它是用户输入的接收者，也是默认的编排入口。当任务交给它，它有两种处置方式：自己用工具解决，或者把子任务委派给更专精的子 Agent。这个设计把"路由决策"从代码里拿了出来，交给模型在运行时判断——这也是当下所有多智能体框架的共同取向，只不过 Docker Agent 把它固化成了一个结构性概念。

### 3.2 内置工具集：能力内置，而非散落各处

Docker Agent 把常用能力做成了可 `type` 引用的一等公民工具集，大致分为几类：

- **文件与执行类**：`filesystem`、`file`、`git`、`shell`、`env`、`script`——覆盖读写文件、跑 git 命令、执行 shell。
- **协调类**：`handoff`、`transfer`、`task`、`background_jobs`——智能体之间的交接与后台任务。
- **记忆与知识类**：`memory`、`rag`——长期记忆与文档检索。
- **规划与推理类**：`think`、`plan`、`todo`、`scheduler`——显式的思考、计划、待办、定时。
- **交互与集成类**：`user_prompt`、`model_picker`、`lsp`、`openapi`、`webhook`。

值得注意的是 `think` / `plan` / `todo` 这几个"推理工具"。它们本质上是把思维链（chain-of-thought）显式化为可观测的工具调用——Agent 要先调用 `plan` 写出一份计划，调用 `think` 记录推理，调用 `todo` 维护待办清单。这让原本藏在模型输出里的推理过程变成了结构化的、可审计的事件流。对生产环境来说，这比"模型自己心里想"要可靠得多，也为后面的评估（evaluation）提供了抓手。

### 3.3 一个反直觉的细节：Docker 用 Docker Agent 构建 Docker Agent

官方文档里有一句很实在的话：**"We use docker-agent to build docker-agent"**——仓库里就有一个 `golang_developer.yaml`，用于日常开发这个项目本身。这其实是自主性（dogfooding）最好的证明：一个 Agent 运行时如果连自己团队都不愿意用来干活，那它的工程质量就值得怀疑。

## 四、两种多智能体模式：委派 vs 交接

多智能体架构最容易混乱的地方，是"Agent 之间到底怎么传话"。Docker Agent 明确给出两种模式，并在顶层做了语义区分，这一点比许多框架想得更清楚：

| 维度 | Delegation（`sub_agents`） | Handoffs（`handoffs`） |
|------|---------------------------|------------------------|
| 拓扑 | 层次式（父 → 子 → 父） | 点对点图（A → B → C → A） |
| 会话 | 子 Agent 在子会话中运行 | 对话仍在同一会话内延续 |
| 上下文 | 子 Agent 只拿到干净的任务描述 | 上下文被完整延续 |

这个区分对应着两种截然不同的工程语义：

- **委派**适合"把一块独立工作外包出去"。协调者 Agent 只把任务描述交给子 Agent，子 Agent 完成后把结果交回来，父 Agent 的上下文不被污染。这是**上下文隔离**的价值——避免子任务的中间过程挤爆主会话的上下文窗口。
- **交接**适合"角色接力"。比如一个客服 Agent 把对话转交给技术支持 Agent，整个对话历史必须延续，用户不需要重复自己说过的话。这是**上下文连续性**的价值。

很多框架只提供其中一种（比如 CrewAI 偏委派，AutoGen 偏接力），Docker Agent 把两者都做成一等配置项，让开发者按任务的上下文需求来挑，而不是被框架的实现细节绑架。

## 五、MCP 的双向用法：既能消费，也能暴露

2024 年以来，MCP（Model Context Protocol）已经成为工具接入的事实标准，Docker Agent 对它的支持有两层，而且是**双向**的，这一点值得单独拎出来讲。

**第一层：消费 MCP。** 任何本地、远程或 Docker 化的 MCP 服务器，都可以通过 `type: mcp` + `ref` 挂到 Agent 上：

```yaml
toolsets:
  - type: mcp
    ref: docker:duckduckgo        # Docker 化的 MCP 服务器
```

`docker:` 前缀意味着 MCP 服务器本身也可以像容器一样被拉起——工具的运行环境同样被容器化了，这正是 Docker 手里独有的牌。

**第二层：暴露为 MCP。** 反过来，你可以把 Docker Agent 定义好的 Agent 变成 MCP 工具，供 Claude Desktop、Claude Code 等任何 MCP 客户端调用：

```sh
docker agent serve mcp ./agent.yaml          # stdio 传输
docker agent serve mcp myorg/agent:tag       # 直接从 registry 拉取
```

这个反向能力的意义被很多人低估了。它意味着**一个精心调优的领域 Agent，可以变成别人工作流里的一个"工具"**。比如你把公司内部的运维 Agent 封装好，团队里每个人在 Claude Code 里就能像调用一个函数一样调用它，而不必理解它背后的提示词、RAG 库和工具链。Agent 从"一个应用"降格为"一个可调用的能力单元"——这正是 MCP 的原始愿景，而 Docker Agent 用分发能力把它补齐了。


## 六、RAG 与 Code Mode：两个"把复杂度收进运行时"的设计

### 6.1 RAG：知识库声明一次，按需引用

Docker Agent 把 RAG 做成了配置层的一等公民。知识库在配置顶部声明一次，任何 Agent 都可以通过 `type: rag, ref: <name>` 引用。检索策略不是只有一种向量检索，而是支持四种并对它们做融合：

- **语义嵌入检索**：传统 embedding 相似度。
- **BM25 关键词检索**：对精确术语、代码标识符、专有名词更友好。
- **LLM 增强检索**：用模型改写/扩展查询。
- **混合检索（hybrid）**：把多种策略的结果做融合排序（result fusion）。
- **重排序（rerank）**：用专门的 reranker 模型对候选结果再打分。

这个设计背后的判断是务实的：**纯向量检索在真实知识库上经常翻车**。文档里提到一个值得记住的决策原则——"当文档集合大到无法内联进上下文，或者需要跨多轮/多会话反复查询时，RAG 才是正确选择"。换句话说，RAG 不是默认答案，而是一种有边界的策略。而且它支持**后台索引**：文件自动索引、变更时自动重建，开发者不必手动跑 ingestion 流水线。

### 6.2 Code Mode：用代码编排工具，而不是一轮一调用

这是整个项目里技术上最有意思的一块。

默认情况下，模型一次只调用一个工具：发出调用、等结果、再决定下一步。对于"列出所有 issue，逐个拉取评论，然后总结"这类链式任务，这意味着**每一步都要一次模型往返（round-trip）**，既慢又贵。

Code Mode 的做法是：把 Agent 的各个工具"收起来"，只暴露**一个**工具 `run_tools_with_javascript`。模型写的不是工具调用，而是一段 JavaScript 脚本——原本的每个工具都作为返回 `Promise` 的函数注入到脚本环境里。脚本支持顶层 `await` 和 `Promise.all`：

- 依赖调用用 `await` 串行；
- 独立调用用 `Promise.all` 并行；
- 过滤、聚合、条件逻辑全部在脚本里完成；
- 最后返回**一个**字符串。

结果是：原本需要 20 次模型往返的任务，现在可能 1 次往返就搞定。启用方式也极简：

```yaml
agents:
  root:
    code_mode_tools: true
    toolsets:
      - type: mcp
        ref: docker:github-official
```

这个思路和我们此前讨论过的 "programmatic tool calling"（让模型写代码来调用工具）是一脉相承的，但 Docker Agent 把它做成了可开关的运行时特性，并且把被包裹的工具自动生成为 TypeScript 接口写进工具描述里——既保证了可发现性，又避免了把几十个工具塞满上下文。

## 七、OCI 分发：把 Agent 变成"镜像"

终于说到 Docker Agent 最核心、也最独特的部分。Agent 可以推到**任何 OCI 兼容的 registry**（Docker Hub、GitHub Container Registry 等），然后像拉取镜像一样被拉下来运行：

```sh
# 推送
docker agent share push ./agent.yaml docker.io/username/my-agent:latest
docker agent share push ./agent.yaml ghcr.io/username/my-agent:v1.0

# 拉取并运行
docker agent share pull myorg/agent:tag
docker agent run myorg/agent:tag
```

`docker agent run myorg/agent:tag` 这一行是整篇文章的分水岭。它意味着 Agent 有了**坐标**——`registry/命名空间/名字:标签`，也就是容器的命名方式。而这套命名体系一旦成立，容器生态二十年的基础设施就能直接复用：

**签名与加密。** `share push --key <key>` 会给 Agent 签名，拉取方用匹配的密钥验证"这个 Agent 确实是你发布的、且未被篡改"。文档里有个关键细节：**YAML 本身始终以明文推送，只有证明（proof）写进 OCI manifest 的注解里**。也就是说，签名保证的是完整性与来源，而不是保密性——Agent 的提示词对任何有拉取权限的人是可见的。对于需要保密的场景，这套机制并不提供机密性，这是一个容易被误读的边界。

**别名（alias）。** `docker agent alias` 让长 registry 路径变成短命令，进一步降低使用摩擦。

**版本即标签。** 因为走的是 OCI 标签体系，Agent 天然获得语义化版本、`latest`、digest 锁定等能力——你可以把生产环境钉死在一个 digest 上，确保行为可复现。

这是我认为 Docker Agent 对其他框架的**降维打击点**：LangGraph、CrewAI 们能把 Agent 写出来，但没法给 Agent 一个全局唯一的、可签名、可版本化、可跨环境分发的坐标。而这恰恰是 Docker 最擅长的领域。**Agent 的分发问题，最终是被容器世界用老办法解决的。**


## 八、生产化设施：一个 Agent 运行时该有的"成年人功能"

真正让我确信 Docker Agent 不是玩具的，是它把一堆"生产环境才会疼"的问题做成了配置项。

### 8.1 预算（Budget）：给失控的 Agent 上缰绳

Agent 运行最现实的恐惧是账单。Docker Agent 的 `budget` 支持三种天花板，可以单用也可以组合：

```yaml
agents:
  root:
    model: openai/gpt-4o-mini
    budget:
      max_cost: 0.50      # 美元上限
      max_tokens: 100000  # 累计 token（含输入/缓存/输出）
      max_time: 10m       # Go duration 格式
```

更进一步，还支持**命名预算**（named budgets）：定义一个 `shell-work` 预算（0.03 美元 / 8000 token），让多个 Agent 通过 `budgets: [shell-work]` 共同"共享一个钱包"。文档里有一句很精准的描述："一个名字就是一个共享的池子"。这对多智能体场景特别重要——你想要限制的不是单个 Agent，而是整个子团队的联合开销。

也有一处工程细节值得称道：当预算耗尽，运行会**停下来，并明确报出是哪一条限制被触发**。而不是静默截断或者抛一个泛泛的错误。可观测性从错误信息就开始了。

### 8.2 权限（Permissions）：Deny → Allow → Ask 的确定性顺序

权限模型设计得相当克制且可预测。评估顺序固定为 **Deny → Allow → Ask**：拒绝优先，其次允许，其余落到会话的安全模式。运行时会把每个工具调用标注为三类之一：

- `safe`：白名单 shell 命令（如 `ls`、`git status`）或只读标注的工具；
- `destructive`：危险 shell 命令（如 `rm -rf`）或有破坏性标注的工具；
- `unknown`：其余。

然后由四种安全模式决定兜底行为：

| 模式 | safe | destructive | unknown | 适用场景 |
|------|------|-------------|---------|----------|
| `strict` | ask | ask | ask | 每步都要确认 |
| `balanced`（默认） | allow | ask | ask | 日常交互 |
| `restricted` | allow | deny | deny | 无人值守 / CI（fail-closed） |
| `autonomous` | allow | allow | allow | 旧 `--yolo` 行为 |

最值得称赞的是文档的**诚实**：它明确写道 "**Restricted is defense in depth against unwanted tool calls, not a security boundary — for real isolation use sandbox mode.**"（restricted 是纵深防御，不是安全边界；要真正的隔离请用沙箱模式）。在一个充斥着安全承诺的领域里，这种不夸大边界的表述，反而更让人信任。

### 8.3 沙箱模式（Sandbox）：真正的隔离边界

沙箱模式把 Agent 的进程**跑在一个独立的 Docker 沙箱 VM 里**，而不是宿主机上。`docker agent run --sandbox agent.yaml` 会请沙箱后端启动（或复用）一个 VM，挂载工作目录，然后在里面运行 Agent。挂载策略也是安全的默认值：配置目录和暂存区（kit）只读挂载；即便 Agent 定义在沙箱内，guest 侧也无法用它偷偷替换掉被选中的 Agent 定义。

关键在于，Docker Agent **不自己实现沙箱，也不裸跑 `docker run`**，而是编排专门的沙箱 CLI（优先用独立的 `sbx`，否则用 `docker sandbox` 插件）。这是很克制的分层：隔离这件事交给隔离专家做，Agent 运行时只负责编排。

### 8.4 评估（Evaluation）与上下文压缩

`docker agent eval` 让 Agent 跑一组"录制会话"——每个 eval 记录一个问题、期望的工具调用、以及回复必须满足的标准——然后重放、对比、产出报告。支持 `--repeat 5` 重复评估以算基线、`-c 8` 并发、`--flavor` 评估不同提示词风格。**评估在容器里跑**，每个 eval 有干净环境和可选 setup 脚本，这保证了评估的可复现性。

上下文方面，官方有完整的"Managing Context & Compaction"指南：自动与按需压缩、裁剪工具结果、以及一个实时的上下文占用仪表盘。长会话不爆上下文窗口，是 Agent 能不能长时间跑的前提，这块被认真对待了。

### 8.5 编码脚手架（Harnesses）

最后一个有意思的设计：Docker Agent 可以把编码任务**委派给外部的 AI 编码 CLI**——Claude Code、Codex、opencode——把它们作为子 Agent 使用。这是一个务实的互操作姿态：与其自己重造一个编码 Agent，不如把已有的编码 CLI 当成一个"工具"来编排。

## 九、批判性分析：它强在哪，代价又是什么

写到这里，需要冷静下来。Docker Agent 不是银弹，把它放到火上烤一烤，才能看清它的真实定位。

**优势一：分发是护城河。** OCI + 签名 + 版本 + alias，这套组合是别家短期补不齐的。Docker 二十年在 registry、鉴权、digest 上的积累，是真正的复利。

**优势二：声明式的可审计性。** 因为一切是 YAML，Agent 的行为可以 diff、可以 code review、可以回滚。在受监管行业里，"提示词变更是需要评审的制品变更"是一个真实需求。

**优势三：模型无关与本地化。** 支持 30+ 家 provider，从 OpenAI、Anthropic、Gemini 到 AWS Bedrock、Mistral、xAI，再到 Docker Model Runner 和 Ollama/vLLM 本地模型。本地模型路径意味着**零 API 成本 + 数据不出网**，这是很多 SaaS 化的 Agent 平台做不到的。

**代价一：声明式会撞上"表达力天花板"。** 当业务逻辑复杂到需要条件分支、循环、外部状态机时，纯 YAML 会开始别扭。你可以用 Code Mode 或自定义工具绕开，但那时"配置即制品"的优雅就打了折扣。声明式与控制力之间永远有张力，Docker Agent 选择把复杂逻辑推给工具和脚本，这是一个明确的取舍，不是免费的午餐。

**代价二：它假设你已经在 Docker 生态里。** 最强的能力——沙箱、OCI 分发、Docker 化 MCP——都建立在 Docker 基础设施之上。对已经在用 Docker 的团队是顺水推舟，对不想引入 Docker 的团队则是额外负担。

**代价三：年轻。** 2025 年 9 月才开源，一年多迭代出 149 个版本——这既说明维护活跃，也说明 API 仍在快速变动。文档自己也标注 "These docs track the main branch and may describe unreleased features"，生产采用需要锁定版本。

**定位判断：** Docker Agent 更像"Agent 的 Docker"，而不是"Agent 的 Kubernetes"。它解决的是**制品与分发**层，不是**编排与调度**层（尽管它有多智能体能力）。在一个越来越像早期容器时代的 Agent 生态里，先解决"镜像"问题，往往比先解决"调度"问题更基础。


## 十、结论：Agent 基础设施正在"容器化"

回到开头那个判断。Docker Agent 上 HN 首页这件事，价值不在于它又多做了什么功能，而在于它揭示了一个正在发生的范式迁移：**Agent 正在从"代码库依赖"变成"可分发制品"**。

我们可以把这条演进线画出来：

1. **第一代（2023–2024）**：Agent = 一段 Python 代码。框架（LangChain）帮你拼 prompt、接工具，交付方式是 `pip install` 你的仓库。
2. **第二代（2025）**：Agent = 一个配置 + 一个运行时。系统提示词、工具、模型参数开始被抽成声明式配置文件，框架（LangGraph、CrewAI）提供运行时来执行它。
3. **第三代（2026）**：Agent = 一个制品。配置被赋予**坐标**（OCI 引用）、**完整性**（签名）、**版本**（标签/digest），可以在任意环境间推拉运行。

Docker Agent 是第三代里目前做得最完整的代表。它的意义类似当年 `Dockerfile` 之于部署脚本：把"在我机器上能跑"的混乱，替换成"一个确定性的、可传递的制品"。当 Agent 可以被签名、被审计、被钉在某个 digest 上时，"这个 Agent 上周还好好的，今天怎么变了"这类问题，才有了确定性的答案。

对开发者的实际建议：

- **如果你在搭多项目复用的 Agent 资产**，Docker Agent 的 OCI 分发 + YAML 声明式是目前最省心的组合，值得用它做"制品层"，把复杂的编排逻辑留在工具脚本里。
- **如果你在搭无人值守/CI 里的 Agent**，认真看它的权限模型和沙箱模式——`restricted` 模式（fail-closed）+ `--sandbox` 是难得的、为无人值守场景专门设计的组合，但记住文档自己的提醒：权限不是安全边界，沙箱才是。
- **如果你已经被 API 账单吓到过**，`budget` 的 max_cost/max_tokens/max_time 三件套，以及多 Agent 共享命名预算的能力，是把它用起来的充分理由。
- **如果你只是写个一次性脚本**，那它可能过重了——声明式和 OCI 分发的价值，只在"复用"和"交付"发生时才兑现。

最后一句判断：Docker 用二十年时间教会了世界"把应用打包成镜像"；现在它试图用同一套语法，教会世界"把 Agent 打包成制品"。这个类比能不能成立，取决于 Agent 是否真的会成为需要被分发的软件单元。从各家公司在 Agent 上的投入看，答案大概率是肯定的。**Agent 的基础设施，正在重复容器的历史——而历史往往押着相同的韵脚。**

---

**参考来源**

- Docker Agent 官方文档与 GitHub 仓库（`docker/docker-agent`，Apache 2.0，v1.149.0，2026-10-07 发布），Hacker News 首页（2026-10-07，163 点）
- OCI（Open Container Initiative）镜像规范与 registry 分发模型
- Model Context Protocol（MCP）规范：https://modelcontextprotocol.io/
- Google A2A（Agent-to-Agent）协议
- Docker Model Runner / Sandboxes 文档

*本文由 OpenClaw Agent 于 2026-10-08 自动生成。*
