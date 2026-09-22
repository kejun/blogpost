# 当 Agent 不再"点击"UI：Builder.io 开源 Agent-Native 框架与 Action-First 应用架构

> 2026-09-22 · AI技术 · 本文约 4500 字

## 一个"老前端"的新赌注

9 月 22 日的 GitHub Trending 第一名，是一个叫 `BuilderIO/agent-native` 的 TypeScript 仓库：**5,877 stars、534 forks、单日新增 607 星**。仓库创建于 2026 年 3 月 12 日，蛰伏半年后，选择在 AI 应用框架竞争最白热化的时刻开源。

出品方 Builder.io 值得多说两句。创始人 Steve Sewell 过去几年的作品序列——可视化 CMS Builder.io、"可恢复性"前端框架 Qwik、把第三方脚本扔进 Web Worker 的 Partytown、一份代码编译到所有框架的 Mitosis——几乎每一部都在回答同一个问题：**前端架构的基本假设过时了，敢不敢推倒重来？** 这一次，他瞄准的基本假设是：应用是为"人点击 UI"设计的。

Agent-Native 的定位一句话就能说清：**一个开源 TypeScript 框架，用来构建"自主 Agent + 专用 UI"配对的 agentic 应用**。每个能力只定义一次（称为 action），Agent 把它当工具调用，UI 把它当函数调用——两条路径共享同一份校验、权限和实现。官方文档里最有信息量的一句话是：

> "The agent does not click through the UI. It works through the same action layer as the UI."
> （Agent 不点击 UI。它和 UI 走同一个 action 层。）

核心数据一览：

| 维度 | 数据 |
|------|------|
| Stars / Forks | 5,877 / 534（创建于 2026-03-12，单日 +607） |
| 语言 / 许可 | TypeScript / MIT（README 声明） |
| 一句话定位 | 一次定义 action，同时暴露为 Agent 工具、UI Hooks、HTTP、MCP、A2A、CLI |
| 数据层 | PostgreSQL（生产）+ PGlite（本地开发），Drizzle ORM，Nitro 兼容部署 |
| LLM 接入 | BYO：Builder.io 免费额度 / Anthropic / OpenAI / 本地 Ollama |
| 官方示例应用 | 9 个：Clips、Design、Slides、Analytics、Calendar、Mail、Assets、Content、Plans |
| 环境要求 | Node 22.22+、pnpm，`npx @agent-native/core create` 一键起项目 |

为什么值得认真拆？因为它正面回答了一个大多数团队都在回避的问题：**当 Agent 成为应用的第二用户，应用架构本身要怎么改？** 答案不是"加个聊天框"，也不是"让 Agent 截图点按钮"，而是把应用的能力层重构成人和 Agent 的"共同地基"。

## 文本框的幻觉：Coding Agent 为什么"看起来"不需要 UI

Agent-Native 文档开篇的洞察非常锋利：

> "Coding agents work with more than a text box. Their environment provides context, tools, files, tests, and previews that make their capabilities and results visible."
> （编码 Agent 用的远不止一个文本框。它们的环境提供了上下文、工具、文件、测试和预览，让能力和结果都可见。）

Claude Code、Cursor 让用户误以为"一个聊天框就够了"，但那是错觉——代码仓库本身就是 Agent 的豪华工作环境：文件系统是上下文，shell 是工具，测试是验证器，diff 是结果预览。编码 Agent 之所以强大，是因为软件工程在过去五十年恰好沉淀出了一个**机器可读、结构完整的工作环境**。

知识工作没有这个运气。做邮件、做报表、做设计、管日历的人，面对一个空白文本框时，必须自己猜：Agent 能干什么？它知道我现在在看什么？我该怎么问？文档用了一个精准的说法："people have to guess what the agent can do"——**能力的不可见性，是知识工作 Agent 化的第一瓶颈**。

Agent-Native 的解法是把 coding agent 的环境结构移植给知识工作应用，三个共享层：

1. **Shared actions（共享能力）**：Agent 调工具和 UI 调函数走同一条路；
2. **Shared data（共享数据）**：Agent 干的活立刻出现在 UI 里，UI 里的改动 Agent 立刻可见；
3. **Shared application state（共享应用状态）**：Agent 知道用户当前在哪个页面、选中了哪条记录、激活了哪个视图。

UI 在这里的角色不是"Agent 的遥控器"，而是 Agent 的 IDE——让能力可见、让上下文可携带、让结果可检查可修改。人可以在 UI 里改两笔，再把接力棒交回 Agent，中间不丢失任何进度。

## Action 解剖：一份定义，六个表面

整个框架的支点是 `defineAction()`。看官方示例：

```ts
// actions/hello.ts
import { defineAction } from "@agent-native/core/action";
import { z } from "zod";

export default defineAction({
  description: "Return a friendly greeting.",   // 告诉 Agent 何时用这个工具
  schema: z.object({                             // 运行时校验 + TS 类型 + LLM 工具定义，三合一
    name: z.string().default("world").describe("Name to greet"),
  }),
  http: { method: "GET" },                       // 只读操作暴露为 GET，供 useActionQuery 调用
  readOnly: true,
  run: async ({ name }) => {                     // Agent 和 UI 共享的业务逻辑
    return { message: `Hello, ${name}!` };
  },
});
```

把这一个文件丢进 `actions/` 目录（扁平结构，启动时自动扫描，无需注册），它就同时变成六种东西：

| 表面 | 调用方式 | 典型使用者 |
|------|---------|-----------|
| Agent Tool | Agent 读 description + schema，在对话中直接调用 | 内置聊天 Agent |
| UI Hooks | `useActionQuery()` / `useActionMutation()` / `callAction()` | React 组件 |
| HTTP API | 自动挂载到 `/_agent-native/actions/<name>` | 外部脚本、后端集成 |
| MCP Tool | 任何 MCP host 可发现和调用 | Claude Desktop、Cursor、Codex |
| A2A Tool | 其他 agent-native 应用通过 A2A 协议调用 | 工作区里的兄弟应用 |
| CLI 命令 | `pnpm action hello '{"name":"Steve"}'` | 终端、cron、手工测试 |

这里有个容易被低估的工程巧思：**zod schema 一份定义打三份工**——运行时输入校验、TypeScript 类型推断（`useActionQuery` 的入参和返回值全自动带类型）、LLM 工具定义的 JSON Schema。tRPC 当年用同样的手法统一了"浏览器 ↔ 服务端"的类型真相，Agent-Native 把这个思路推进到"人 ↔ Agent ↔ 机器"的三方统一。

对比一下既有方案，差异化就出来了：

| 方案 | 类型安全 | UI 可调 | Agent 可调 | 跨协议暴露 |
|------|---------|--------|-----------|-----------|
| 传统 REST/GraphQL API 层 | 手工维护 | ✅ | 需另写集成 | 部分 |
| tRPC | ✅ 端到端 | ✅ | ❌（仅浏览器/Node 客户端） | ❌ |
| Next.js Server Actions | ✅ | ✅ | ❌ | ❌ |
| MCP-first 设计 | 取决于实现 | ❌（UI 需另写） | ✅ | ✅（仅 MCP） |
| **Agent-Native Actions** | ✅ | ✅ | ✅ | ✅（HTTP/MCP/A2A/CLI 全自动） |

传统架构的病根，文档说得很直白：大多数应用在前端和数据库之间建了一个**只有浏览器能调**的 API 层；Agent 想要同样的能力，就得再写一套独立集成，重新实现、重新维护、重新出 bug。Agent-Native 直接取消了这个分裂——"only one implementation to write, and only one place for a bug to hide"（只写一份实现，bug 只有一个藏身之处）。

配套的工程约定也齐全：`server/db/schema.ts` 放 Drizzle 表定义，`server/lib/access.ts` 放共享的访问守卫（`accessFilter` / `assertAccess` / `authorize`），所有调用路径——无论来自点击还是来自 LLM——都跑同一套 schema 校验、权限检查和审计日志。文档还立了一条纪律：**`actions/` 之外的任何代码不得直接 import action 的 `run` 函数**，必须走六个表面之一，否则审计链就断了。

## 上下文感知：Agent 看见你看的，还能控制你看的

如果说 action 层解决"Agent 能干什么"，context awareness 层解决"Agent 知道你在干什么"。文档里的反面场景很生动：没有上下文感知的 Agent 是瞎的——用户明明盯着一封邮件，Agent 还在问"which email?"。

框架用六个模式打通了这条双向通道：

| 机制 | 方向 | 说明 |
|------|------|------|
| `navigation` 状态键 | UI → Agent | 每次路由变化写入：当前视图、打开的记录 ID、激活的标签页 |
| `__url__` 状态键 | UI → Agent | 框架自动同步当前 URL，Agent 每轮对话都收到 `<current-url>` 块（含解析后的 query 参数） |
| `selection` 状态键 | UI → Agent | 用户选中/多选的行、块、图形、资产 |
| `view-screen` action | Agent 主动读 | 把上述轻量状态键"水化"成真实记录和屏幕摘要 |
| `sendToAgentChat()` | UI → Agent | 把一次点击（命令、评论锚点、Cmd+I 选中文本）变成一轮 Agent 对话 |
| `navigate` 状态键 | **Agent → UI** | Agent 反过来指挥 UI 跳转路由、聚焦对象；`set-search-params` 工具可直接改 URL 筛选参数 |

注意最后一条：**这是双向的**。Agent 不仅能读"用户在看什么"，还能写"让用户看什么"——用户说"帮我筛出西区续约客户"，Agent 直接改 URL query 参数，列表当场刷新。设计上还有个值得学的分层纪律：URL query 参数是可分享筛选状态的唯一真相源，`navigation` 只存语义化 ID，重数据一律由 `view-screen` 现场从数据库取——**状态键保持轻量语义，记录永远拿新鲜的**。

这条路线和 computer-use（截图 + 模拟点击）形成了鲜明对照。我们今年 4 月分析过感知架构的"截图 vs 无障碍树"之争，Agent-Native 相当于给出了第三种答案：**既不解析像素，也不注入浏览器 DOM，而是让应用主动上报结构化语义状态**。代价是应用必须为 Agent 重新设计（greenfield），收益是零 OCR 误差、零坐标漂移、权限和审计完整闭环。对自建应用来说，这几乎是唯一正确的路线。

## Agent Teams：把"编排器-专家"模式焊进 SQL

框架的第三根支柱是 Agent Teams。心智模型：**主聊天是 orchestrator（编排器），不是巨石**。遇到适合专家处理的任务——"用我的口吻写邮件"、"跑一个 BigQuery 分析"、"review 这个 PR"——主 Agent 通过 `agent-teams` 工具 spawn 一个子 Agent，子 Agent 拥有独立的线程、系统提示词和工具集，在主聊天里以**实时 chip（预览卡片）**的形式内联出现，点击可展开完整对话。

`agent-teams` 工具的完整动作集：`spawn`（启动）、`status`（查进度）、`read-result`（取结果）、`send`（给运行中的子 Agent 发消息）、`list`（列出当前用户所有任务）——**主 Agent 和子 Agent 之间是双向消息**，子 Agent 遇到歧义可以反问。

工程上最有含金量的细节在持久化：子 Agent 状态写入 `application_state` SQL 表（`agent-task:<taskId>` 键下），事件流式推送的同时落盘，abort 信号通过 SQL 传播——官方明确说"tasks survive serverless cold starts"（任务能活过 serverless 冷启动）。这意味着一个跑 20 分钟的子 Agent 任务不怕函数实例回收，任何进程都能接管恢复。把 Agent 运行时状态当数据库行来管理，而不是当内存对象，这是把 AgentOps 做进框架层的少数实践之一。

子 Agent 的定义方式也顺应了事实标准：`agents/<slug>.md`，**Markdown + YAML frontmatter**——和 Claude Code subagents 同一血脉。再配合 skills（可复用专长）、`memory/MEMORY.md`（持久记忆）、automations（定时/事件触发），一个"配置即 Agent"的资源体系就齐了。这与我们 9 月 19 日分析过的 AGENTS.md 标准化浪潮完全同频：**Agent 的定义正在收敛为"带 frontmatter 的 Markdown 文件"**。

官方给出的 9 个示例应用也不是 demo 性质，而是可直接克隆的完整产品：Clips（录制并理解会议/屏幕/语音备忘）、Mail（邮件分诊、代拟回复、跟进）、Analytics（对数据提问并生成仪表盘）、Design、Slides、Calendar、Assets、Content、Plans（含线框图和原型的可视化计划）。等于把"agent-native 应用长什么样"这个问题给出了九个参考答案。

## 冷静评估：四个必须直视的问题

**其一，安全面是乘法不是加法。** UI 和 Agent 共享 action 层，意味着任何一个 action 的权限漏洞同时暴露给两条通道。更隐蔽的是 `view-screen`：它把用户正在看的内容拉进 Agent 上下文——如果用户正在看一封恶意邮件，邮件里的注入指令就顺着这条"合法"通道进了上下文。框架提供了 `readOnly` 标记、exposure flags（控制 action 是否暴露给 MCP/A2A）和全路径审计日志，但**默认暴露策略是否足够保守、审批流（approval）是否强制**，需要在生产采用前逐项审计。共享即效率，共享即风险，这是一体两面。

**其二，成熟度还在早期。** 仓库 3 月创建，总星数不到 6 千，单日 +607 说明爆发刚刚开始；API 必然高频变动。另一个小信号：GitHub API 目前检测不到标准 LICENSE 文件（README 声明 MIT），合规敏感的企业应等许可文件落地再说。文档质量倒是一流——这很 Builder.io。

**其三，"agent-native"品类的真实性拷问。** 反方观点是：MCP 已经解决了"Agent 调用你的应用"，为什么还要重构应用？这个质疑对存量应用成立，但对增量应用不成立——MCP 只能暴露你已有的 API，解决不了"Agent 不知道用户在看什么"、"UI 和 Agent 两套实现漂移"、"子任务状态活不过冷启动"这些**应用内部**的结构性问题。Agent-Native 赌的是：Agent 是第二用户，而给用户用的东西不能靠外挂。存量迁移路径确实是它的短板——这本质上是个 greenfield 框架。

**其四，商业动机要摆上桌面。** 接入 LLM 的第一选项是"Connect Builder.io 用免费额度"，导流意图明显。但客观说，MIT 许可 + BYO LLM（Anthropic/OpenAI/Ollama 都行）+ PostgreSQL 自有数据 + "Everything you build stays yours"的承诺，把锁定风险压到了同类框架的低位。

## 大图景：模型商品化，价值上移到应用层

把镜头拉远，今天的技术圈有两个信号事件恰好构成互文。其一是小米 MiMo v2.6 开源发布，HN 433 分——社区最高赞评论不是吹性能，而是称赞其训练全程透明（实时 RL 训练仪表盘 + 详尽技术报告）；其二是 Linear 发文承认"AI coding 让 CI 成了瓶颈，我们重做了整条流水线"（HN 113 分）。HN 讨论区还有一条被反复引用的判断：**多家模型路由商的开放权重模型流量占比已过半**。

三件事指向同一个结论：模型层正在快速商品化，连"训练过程"都成了可展示的开源资产；与此同时，软件的每一个环节——编码、CI、应用架构——都在为 Agent 重写。竞争重心从"谁的模型强"上移到"谁的应用层和 harness 层为 Agent 设计得好"。我们今年写过的 Copilot SDK（Agent-as-a-Library）、ECC（harness 操作系统）、为 Agent 重写的开发者工具（SEM/LSP），全部在这条主线上。Agent-Native 是这条线在**应用框架层**的最新落子。

历史总在押韵。2010 年代，"API-first"重构了后端——能力必须先于界面存在；2013 年，"mobile-first"重构了前端——响应式成为默认要求。Agent-Native 想成为的，是 2026 年的那个"first"：**action 层就是新的 API 层，agent-native 就是新的 mobile-friendly**。

## 给前端工程师的行动清单

如果你是前端工程师，我的建议分三档：

- **现在就可以做**：把"能力定义"从组件里抽出来。哪怕不用这个框架，也学它的纪律——一份 zod schema 同时服务校验、类型和未来的工具定义；UI 状态语义化（navigation/selection 分离）；URL query 做可分享状态的唯一真相源。这些模式框架无关，即刻可用。
- **小项目试水**：用 Chat 模板起一个内部工具（Node 22.22+、`npx @agent-native/core create`），重点验证 action 层的权限模型和 `view-screen` 的上下文注入是否符合你的安全预期。
- **生产暂缓**：等三件事——LICENSE 文件正式落地、API 进入稳定期（关注 breaking change 频率）、社区出现第一个非官方的安全审计报告。

Steve Sewell 用 Qwik 赌过"渲染范式"，用 Mitosis 赌过"框架互操作"，这次用 Agent-Native 赌的是"应用的第二用户"。前两赌都赢在了理念、输在了时机。这一次，时机可能是对的——因为文本框的幻觉正在破灭，而知识工作的"代码仓库"，还没有人建出来。

---

**参考链接**

- GitHub: https://github.com/BuilderIO/agent-native
- 文档: https://agent-native.com/docs
- Actions 架构: https://agent-native.com/docs/actions-overview
- 上下文感知: https://agent-native.com/docs/context-awareness
- Agent Teams: https://agent-native.com/docs/agent-teams
- 示例应用: https://agent-native.com/apps
- 相关讨论: Hacker News 首页（2026-09-21/22），Xiaomi MiMo v2.6 发布帖（433 分），Linear CI 重构（113 分）
