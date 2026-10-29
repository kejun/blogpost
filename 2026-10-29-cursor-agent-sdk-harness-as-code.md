# 当 Agent 变成一份可评审的代码库：Cursor Agent SDK 深度拆解——`bot/` 目录约定、Evals 与「harness 商品化」的边界

2026 年 10 月 28 日，Cursor 发布了 Agent SDK，Hacker News 上 89 分、107 条评论。分数不算爆，但评论区是这半年里质量最高的一批——因为大家争的不是「好不好用」，而是一个更根本的问题：

> 「2026 年，被反复重造的轮子是 agent harness。」（HN 用户原话）

这句话既是最狠的批评，也恰好是最准确的行业判断。Agent SDK 这个品类，OpenAI 有 Agents SDK，Anthropic 有 Claude Agent SDK，Google 有 ADK，Vercel 有 AI SDK。现在 Cursor 也来了。名字撞车到 HN 上有人吐槽：「OpenAI 和 Anthropic 已经占了 Agent SDK 这个品牌，Vercel 叫 AI SDK，Google 叫 ADK。求求大家给新项目起个好名字。」

但如果你只看到「又一个 SDK」，就会错过这次发布真正有意思的地方。Cursor 做的事情不是抽象层，而是**把 harness 变成文件系统约定**——这件事在产品形态上其实很激进，也很容易被误读。这篇文章想拆的是：它到底怎么组织一个 Agent，为什么这个组织方式值得认真对待，以及它在 107 条质疑里站不站得住。

---

## 一、发布的到底是什么

先看 Cursor 自己的定位，这句话信息量很大：

> 「Agent SDK 让我们用代码定义 Agent，并像管理其他软件项目一样管理它们。它是我们用来构建自家托管 Agent（Bugbot、Security Reviewer、Rollouts）的框架。」

关键在最后半句。Bugbot 是 Cursor 的 PR 审查机器人，Security Reviewer 是安全审查，Rollouts 是灰度发布助手——这些都是 Cursor 已经在卖的产品。Agent SDK 是把**内部生产用的 harness 直接商品化**。这个路径和 Anthropic 把 Claude Code 的内部循环抽成 Claude Agent SDK 是同构的，也和 Vercel 把内部 AI 能力抽成 AI SDK 同构。

所以它的卖点不是「更容易写 Agent」，而是「你写的 Agent 和 Cursor 自己跑在生产上的 Agent 用的是同一套运行时」。对采购方来说这是一句有分量的话：你不是在用某个实验性框架，而是在用 Bugbot 的骨架。

发布的版本号很低调：`@grok/agent-sdk` 0.3.0，2026-10-23 GA。对，包名是 `@grok/agent-sdk`，不是 `@cursor/agent-sdk`。此前它叫 `@cursor/bdk`。文档里的默认模型是 `grok-4.5`，`effort=high`、`fast=true`。官方博客的示例代码里写的还是 `model: { id: "composer-2.5" }`——Cursor 自家的模型。

这个命名混乱不是小事，它是理解这次发布的一把钥匙。HN 上有人直接点出来：

> 「视频里还在显示 `@grok/agent-sdk`。同时我们知道 Grok Bot 其实就是 Cursor……里面一定很热闹。」

一个 SDK 的包名、默认模型、产品品牌分布在三个不同的名字上，说明它是在一次组织/品牌整合的过程中被推出来的。对开发者的实际影响是具体的：你在 `npm install` 的时候会看到 `@grok`，在 dashboard 里看到 Cursor，在模型列表里看到 `composer-2.5` 和 `grok-4.5` 并存。这不是致命问题，但它意味着**这个 SDK 的边界还在移动**，接口稳定性需要用版本号去赌——0.3.0 已经是 GA，但 0.2.29 到 0.3.0 之间就删掉了 `defineAgent` 的 `persistent` 字段，而且删除方式是硬失败：

> 「`persistent` 字段已被移除。Discovery 会拒绝仍然设置它的配置，错误信息是 `persistent was removed. Delete it from defineAgent.`，所以 `validate`、`dev`、`deploy` 都会失败，直到你删掉这个字段。」

这是一个典型的「早期 GA」信号：语义变更不做兼容层，直接让 `validate` 红掉。好处是不会静默出错，坏处是你的 CI 会在某个早上突然挂掉。

---

## 二、目录即配置：`bot/` 下的十四个约定

Agent SDK 最核心的设计决策是：**不提供链式 API，用目录结构表达 Agent 的能力边界。**

一个标准项目长这样：

```text
my-agent/
├── package.json
├── bot/
│   ├── agent.ts              # defineAgent({ model, local, hosting })
│   ├── instructions.md       # 常驻 system prompt（根 Agent 必需）
│   ├── tools/
│   │   └── approve_pr.ts     # 一个文件 = 一个具名工具
│   ├── skills/
│   │   └── pr-review.md      # 按需加载的流程
│   ├── mcp-connections/
│   │   └── linear.ts         # 模型可见的 MCP server
│   ├── host-connections/
│   │   └── metrics.ts        # 模型永远看不到的 MCP
│   ├── subagents/
│   │   └── reviewer/
│   │       ├── agent.ts
│   │       └── instructions.md
│   ├── extensions/
│   │   └── ci.ts
│   ├── channels/
│   │   └── github.ts         # 暴露为 /v1/channels/github
│   ├── hooks/
│   │   └── audit.ts          # 只观察，不干预
│   ├── schedules/
│   │   └── nightly.ts        # cron 驱动
│   ├── reminders/
│   ├── artifacts.ts
│   ├── sandbox/workspace/**
│   └── lib/                  # 共享代码，永不被发现
└── evals/
    ├── evals.config.ts
    └── readiness.eval.ts
```

这张表值得逐行读，因为它把 Agent 的「能力面」拆成了可枚举的十四个槽位，每个槽位的语义是排他的：

- **`tools/` vs `skills/`**：工具是 TypeScript 函数，有 zod schema，模型通过 function calling 调用；skill 是 Markdown 流程，按需注入上下文。前者是「能做什么」，后者是「怎么一步步做」。这个区分在 Claude Code 的 Skills 体系里也出现过，但 Cursor 把它做成了目录级约定而非配置项。
- **`mcp-connections/` vs `host-connections/`**：这是全篇最漂亮的一个设计。前者挂给模型，模型能看到工具列表并调用；后者只给宿主代码用，模型永远看不见。文档写得很明确：「MCP servers for host code and `mcp oauth`. The model never sees them.」为什么需要这个？因为现实里大量 MCP 连接是为了拿凭证、做 OAuth 换 token、或者读一个不该进上下文的内部服务。把它们塞进模型可见的工具列表，既浪费 token 又增加注入面。**把「模型可见性」提升为一等公民的目录区分，是我在这套设计里看到的最有洞察力的一处。**
- **`hooks/` 是 observe-only**：只能订阅事件，不能改写决策。这和很多框架里 hook 可以拦截、修改、短路的设计相反。限制看起来是退步，实际上是在保护可预测性——如果 hook 能改 Agent 的输出，你就没法用 eval 复现一次运行。
- **`lib/` 永不被发现**：共享代码放这里，不会被误当成工具注册。这个细节说明设计者踩过「文件名即注册」的坑。

发现机制本身有明确规则：`.ts` 文件在发现目录里就按定义加载，无法识别的目录产生 validation warning，而不是静默忽略。并且提供了两个自查命令：

```bash
agent-sdk validate --dir .    # 有 error 时返回非零
agent-sdk info --dir .        # 打印实际发现的 surface
agent-sdk info --dir . --json # 与 GET /v1/info 同构
```

文档里有一句话我特别喜欢：

> 「当 `info` 里少了某个 tool 或 channel，说明文件放错了目录，或者扩展名不对。」

这是把「配置错误」变成了「路径错误」。传统框架里，一个工具没注册上，你要去读源码、看装饰器、查 registry；这里你只要看文件在哪。**用文件系统替代注册表，本质上是把一类运行时谜题降维成了 `ls` 就能解决的问题。**

顺带说一个工程细节：`serve` 遇到 error 拒绝启动，warning 不阻塞。这个分级是对的——拼错目录名不该让服务起不来，但互相矛盾的配置必须硬失败。

---

## 三、`defineAgent` 的克制

`bot/agent.ts` 的全部内容通常是这样：

```ts
import { homedir } from "node:os";
import { join } from "node:path";
import { defineAgent } from "@grok/agent-sdk";

export default defineAgent({
  name: "Robo",
  model: {
    id: "composer-2.5",
    params: [
      { id: "effort", value: "high" },
      { id: "fast", value: "true" },
    ],
  },
  local: { cwd: join(homedir(), ".cache", "factory", "robo") },
});
```

字段表里能看出克制：`model`、`name`、`description`、`instructions`、`local`、`hosting`、`concurrency`、`builtinTools`、`tools`（白名单）、`fs`、`skills`。没有 `memory` 配置项（memory 是一个 hook），没有 `retriever`，没有 `chain`，没有 `agent_executor`。

有两个设计选择值得单独说：

**第一，effort 和 speed 是 params 而不是 id 后缀。** 文档明确写了「Agent SDK rejects an id like `grok-4.5-fast`」。为什么这是对的？因为一旦把推理强度编进模型名，模型名就变成了笛卡尔积：`grok-4.5-fast-high`、`grok-4.5-slow-low`……每加一个维度就翻倍，而且路由层要维护一张巨大的别名表。把 params 正交出来，`id` 只标识「哪个模型」，`params` 标识「怎么跑」，这是数据库范式里的一对多拆表思路，在 LLM 调用层同样成立。

**第二，`tools` 是白名单，省略即全部。** 也就是说默认给全套标准工具，收敛要靠显式列表。这个默认值有点危险——默认开放永远比默认收紧更容易出事故。但配合 `local.sandbox` 就能理解设计者的意图：

> 「`local.sandbox` 在 Cursor 本地沙箱里运行 Agent。默认关闭，所以 shell 命令自动批准并继承 serve 进程的环境变量，包括宿主机的凭证。当 turn 读取不可信输入时（webhook payload、PR diff、入站聊天）把它打开。沙箱限制的是工具本身，所以被注入的 prompt 没法说服模型去做它做不到的事。」

这段话把威胁模型讲清楚了：**提示注入的防线不在模型，在工具能力边界**。沙箱限制工具，而不是试图让模型「识别恶意指令」——后者在 2026 年已经被证明不可靠。默认关闭是便利性妥协，但文档把「什么时候必须打开」写成了明确的触发条件（不可信输入），这比含糊的「建议开启」有用得多。

---

## 四、Evals：把「感觉变好了」变成断言

Agent SDK 里我认为最有长期价值的部分不是目录结构，是 evals。因为它回答了一个所有 Agent 团队都在流血的问题：**你改了 prompt，怎么知道是变好还是变坏？**

它的 eval 不是单元测试，而是跑真实 Agent、真实工具，然后对**工具调用序列**和**回复形态**做断言：

```ts
// evals/readiness.eval.ts
import { defineEval, includes } from "@grok/agent-sdk/evals";

export default defineEval({
  tags: ["smoke"],
  async test(t) {
    await t.send("Is https://github.com/acme/checkout/pull/42 ready to approve?");

    t.succeeded();
    t.calledTool("inspect_pr");
    t.notCalledTool("approve_pr");
    t.check(t.reply, includes(/ready|blocked|approve/i));
  },
});
```

`t.calledTool` / `t.notCalledTool` 这两个断言看起来朴素，但它抓住了 Agent 评测的核心：**结果对不代表过程对**。一个 PR 审查 Agent 恰好批准了一个该批准的 PR，但如果它没调 `inspect_pr` 就批了，那它是蒙对的，下次遇到该拒的就会出事。传统 benchmark 只看最终答案，这类「过程正确性」完全测不出来——这也是我此前在《AI Agent 的可靠性缺口》里反复强调的点：从 benchmark 到生产，缺的不是分数，是**过程可验证性**。

三个细节让这套 eval 从玩具变成工程：

1. **会话级断言 vs 轮次级断言**。文档写得很精确：「一次 case 里多个 `t.send` 共享 session。对返回的 turn 做断言只检查那一轮，对 `t` 做断言检查整个会话。」多轮 Agent 的失败往往在第三轮才显现（上下文污染、工具状态残留），能分开断言才有可能定位。
2. **`workspaceFiles` 固定输入**。「Seed the files the agent reads instead of depending on your checkout.」这条直击痛点：如果你的 eval 依赖本地 git 状态，那它不是 eval，是抽奖。把 PR diff 作为字符串注入工作区，测试就变成了确定性输入上的确定性断言。
3. **judge 用于语义正确性**。`t.judge.factuality("The lint step failed on src/sidebar.ts.").atLeast(0.8)` —— 当正确性依赖语义而非结构时用模型裁判，同时给了阈值。用 LLM 评 LLM 有争议，但比正则匹配强，而且阈值化之后至少是一个可回归的数字。

还有一个必须提的安全细节，文档用一句话带过但很关键：

> 「Evals 跑真实工具，所以先给任何写操作加护栏。」

`approve_pr` 这种工具在 eval 里是真的会去 GitHub 上批准 PR 的。文档给的方案是「keep side effects out of eval sessions」——在 eval 会话里把写工具替换成 dry-run 实现。这是所有 Agent eval 框架的公共陷阱：**测试环境和生产环境共用工具，是第一批事故的来源。**

---

## 五、Hillclimbing：一套「改一个变量」的方法论

如果只是提供 eval，那 Agent SDK 和别的框架差别不大。真正让我停下来读了两遍的是 `hillclimbing.md` 这一页——它把「怎么优化 Agent」写成了一套有顺序的工程流程，而不是玄学。

核心定义：

> 「Hillclimbing 每次只做一个可测量的改动。固定输入，改一个东西，只有在同一次运行变好、且没有移动你冻结的行为时才保留它。」

流程六步：按用户的方式跑（不部署、不发线上）→ 读 trajectory，用一句话说出主要失败 → 改**一个**杠杆 → 重跑同一批 fixtures → 比较正确性/效率/契约契合度 → 保留、回滚或收窄。

然后是真正的干货——**杠杆的选择顺序**：

> 「从能消除失败的最早位置开始。在 turn 之前把证据准备好，然后改证据的形状，然后改指令或 skill，然后移除或限制诱导模型乱逛的工具，只有当 Agent 无法表达修复时才改框架。」

这个顺序值得单独拎出来：**证据 > 指令 > 工具 > 框架**。

它反直觉的地方在于，绝大多数人的第一反应是改 prompt（指令），而文档说先改「宿主已经准备好的证据」。原因文档也给了：

> 「修宿主或证据往往同时改善质量和延迟，因为模型少找了很多 ground truth。」

配套的例子非常有说服力：

```text
before: 14 tool calls, 92 seconds, 6 repeated reads
after:   5 tool calls, 31 seconds, 0 repeated reads
```

工具调用从 14 降到 5，延迟从 92 秒降到 31 秒，重复读从 6 次到 0。做法不是让模型「更聪明」，而是把模型本来要找的信息提前放进上下文。这是我在 2026 年看到的最务实的 Agent 优化结论：**大部分「模型不行」其实是「上下文工程没做」**。模型反复读同一个文件，不是因为它笨，是因为宿主没把答案摆在它面前。

还有一条我完全同意的方法论要求：

> 「每个保留的改动都需要一个在改动前会失败的 eval。」

这是 hillclimbing 和「凭感觉调 prompt」的分水岭。没有这条，你的优化历史就是一堆无法归因的 commit。

---

## 六、部署：`deploy` 只认 pushed ref

部署模型很干脆：

```bash
agent-sdk login
agent-sdk validate
agent-sdk deploy          # 构建 pushed ref，打印 URL
```

关键约束：「`deploy` 构建的是 pushed ref，所以未提交的改动不会上线。」以及可以跨仓部署：

```bash
agent-sdk deploy \
  --repo https://github.com/acme/agents \
  --ref main \
  --path agents/weather \
  --slug weather-agent
```

「只部署 pushed ref」这个约束看起来是限制，实际上是**可审计性的基础**。你能回答「线上跑的是哪个 commit」这个问题，才谈得上回滚。相比之下，很多 Agent 平台的部署是「把当前工作区的状态打包上传」，线上版本和 git 历史对不上，出事只能靠猜。

凭证处理也是同一套思路：

```ts
export default defineAgent({
  hosting: {
    egressDomains: ["api.weather.example.com"],
    secretNames: ["WEATHER_API_KEY"],
  },
});
```

```bash
agent-sdk secret set weather-agent WEATHER_API_KEY
```

规则写得很硬：「提交 secret 的名字，永远不要提交值。不要把 `NAME=VALUE` 传给 `secret set`，也不要用 `CURSOR_` 开头的名字。」以及一个容易踩的坑：「托管的 secret 在模块加载之后才到，所以要在需要它的 handler、tool 或 callback 内部读取，而不是模块顶层。」

为什么？因为模块顶层求值时 secret 还没注入，你读到的是 `undefined`，而且不会报错——这是最典型的一类「本地能跑线上挂」的故障。

隐私模式矩阵也值得注意：

| 隐私设置 | 托管部署 |
|---|---|
| Privacy Mode | 可用。部署数据按同样方式存储，模型请求走同样的 Privacy Mode 处理 |
| Privacy Mode (Legacy) | 不可用。`deploy`、托管 session、eval run 全部拒绝 |

「Privacy Mode 可用，但数据照存」这句话写得很诚实，也很容易被误读成「开了隐私模式还存我代码？」——它说的是：Privacy Mode 管的是**模型请求**的处理方式，不是**部署产物**的存储。要真正不出网，就得 self-host：每个 Agent 是一个 Node 进程，可以打进容器，跑在你自己的网络和进程控制里。

这个二分法（托管省事 / 自托管保命）是 2026 年 Agent 基础设施的标准形态，Cursor 没有发明新东西，但把边界写清楚了，这已经比大多数产品文档强。

---

## 七、竞品矩阵：harness 到底在竞争什么

HN 上那句「被反复重造的轮子」值得认真回应。把几个 SDK 放在一起看，会发现它们其实不在同一个抽象层上：

| SDK | 抽象单位 | 运行位置 | 强项 | 代价 |
|---|---|---|---|---|
| Cursor Agent SDK | 目录即 Agent（`bot/`） | Cursor 托管或自托管 Node | Evals + hillclimbing 方法论、PR/Slack/issue 原生 channel、与 Bugbot 同源 | 品牌与包名混乱、0.x GA、强绑定 Cursor 模型路由 |
| OpenAI Agents SDK | Agent / Handoff / Guardrail 对象 | 你的进程 | handoff 语义清晰、guardrails 一等公民 | 事件驱动的多 Agent 编排要自己搭 |
| Claude Agent SDK | 会话 + 工具循环 | 你的进程 | 与 Claude Code 同源、工具协议成熟 | 生态偏 Anthropic |
| Google ADK | 图 / workflow | 你的进程或 Vertex | 显式图结构、多语言（Python/Java/Go） | 图抽象对简单 Agent 是负担 |
| Vercel AI SDK | 流式调用 + 工具 | 你的 serverless | 前端流式体验最好、provider 中立 | 不是完整 harness，编排要自己写 |

看完这张表，那句批评就得改写一下：**被重造的不是轮子，是「Agent 的默认形状」。** 每个 SDK 都在赌一种形状：

- OpenAI 赌 **handoff**——Agent 之间转交控制权。
- Google 赌 **graph**——把 Agent 当工作流节点。
- Vercel 赌 **stream**——把 Agent 当一种特殊的 HTTP 响应。
- Cursor 赌 **repository**——把 Agent 当一个代码仓库，能力边界由目录表达。

这四种形状里，Cursor 的选择最"无聊"，但也最容易被现有工程流程吸收。因为一个仓库天然拥有：版本控制、code review、CI、依赖管理、环境变量、部署流水线。Agent 一旦是仓库，前面这些东西全部免费继承——这正是文档反复强调的那句「changes can go through the same version control and review process as the rest of your software」。

HN 上有一条质疑非常犀利：

> 「诚实地问：为什么任何 Agent SDK 的 API 不能就是一份 PROMPT.md 加一个跑 LLM 带工具的 runtime？为什么需要 LangChain 那种过度抽象？是为了确定性边界吗？」

这条评论其实是在替 Cursor 说话——因为 Cursor 的答案恰恰是「不需要过度抽象」。`bot/` 目录里没有 `AgentExecutor`、没有 `Runnable`、没有 `Chain`。`instructions.md` 就是那份 PROMPT.md，`tools/*.ts` 就是那些工具，`lib/` 就是共享代码。**它用目录约定替代了类型系统里的抽象层级。** 这算不算「SDK」都两说，它更像一个**项目模板加一个运行时约定**。

代价也很清楚：目录约定是隐式契约。你没法通过读类型定义知道 `bot/hooks/` 里能做什么，只能读文档。类型系统帮不了你，`validate` 能帮一点，但错误发现的时机比编译器晚。

---

## 八、四个质疑，逐个回应

把 107 条评论归纳一下，主要火力集中在四点。我尽量给出自己的判断，而不是替 Cursor 辩护。

**质疑一：「谁会用它而不是 Anthropic SDK？」**

这个问题在 2026 年已经没有干净答案了。如果你的 Agent 主要工作是读代码、改代码、审 PR，Cursor 的优势是 channel 层已经做好了——GitHub/GitLab/Bitbucket 的 PR 事件、Slack 的消息、issue tracker、PagerDuty 的告警，都是内置 route，不用自己写 webhook 解析和鉴权。Anthropic 的 SDK 给你更好的工具循环，但「PR 事件怎么进来」要自己搭。**这是产品集成度 vs 抽象纯净度的取舍**，不是能力高低。

**质疑二：「为什么不用开源 harness？」**

评论里有人说：「2026 年 10 月了，为什么不用开源 harness？alpha 在哪？」这个问题问得好，但答案可能不在技术侧。用托管 harness 换的是：sandbox 实现、secret 注入、session 存储、artifact 保留、并发限制、可观测性。这些东西开源方案都有，但需要你自己运维。**对小团队，运维成本比锁定成本更贵。** 反过来说，如果你已经有成熟的 Agent 运行时，这套 SDK 的增量价值确实主要是 evals 那一页文档。

**质疑三：「品牌和命名混乱」**

这是最实在的批评。`@grok/agent-sdk`、`cursor.com` dashboard、`composer-2.5` / `grok-4.5` 三个名字并存。更麻烦的是文档里同时出现 "Cursor Automations"、"Grok Bot"、"Agent SDK" 三个产品，对比表还要专门解释三者的区别：

> 「Cursor Automations：在 dashboard 里定义 prompt、model 和 trigger。Grok Bot：在 app 里配置 instructions、skills 和连接的工具。Agent SDK：一个可版本控制的 Markdown + TypeScript 项目。」

三个产品、三种抽象、同一批用户。这是典型的「内部组织边界泄漏到产品界面」。它不影响代码能不能跑，但影响你判断「我该学哪个」。

**质疑四：「2026 年了，还有人在用 Cursor 吗？」**

这条最狠：「我从 tab 时代就很爱它，但自从它开始追 agentic workflow，产品体验越来越差。」这已经不是技术问题了，是产品战略问题——当一个公司从「编辑器」转向「Agent 平台」，它要同时服务两类用户：想写代码的人，和想让自己不写代码的人。这两类人的诉求在 UI 上是冲突的。

我的判断：Agent SDK 是 Cursor 在为「第二类用户」铺基础设施。它赌的是未来 Agent 比人更常提交代码，那么「管理 Agent」的市场比「编辑代码」的市场大。这个赌注合理，但执行上它必须先解决命名和产品边界——现在的状态像是三条产品线在同一个发布会上撞车。

---

## 九、什么时候该用，什么时候别用

按我自己的判断给个决策清单。

**该用的场景：**

1. **你已经有明确的、重复发生的事件驱动任务**。PR 审查、告警初筛、issue 分类、合规检查。这类任务的输入是结构化事件，输出是有限动作，`channels/` + `tools/` + `evals/` 的模型刚好贴合。
2. **你需要「过程可验证」而不是「答案差不多」**。金融、合规、安全审查这类场景，`t.calledTool` / `t.notCalledTool` 的价值远大于 BLEU 分数。
3. **你的团队已经在用 Cursor，且愿意接受托管**。集成成本最低，dashboard、日志、playground 都是现成的。
4. **你想抄它的方法论而不是它的代码**。就算你不用这个 SDK，`hillclimbing.md` 那套「证据 > 指令 > 工具 > 框架」的顺序，以及「每个保留改动配一个会失败的 eval」的纪律，可以直接搬到任何框架里。**这一页文档的价值可能高于整个 SDK。**

**别用的场景：**

1. **你需要复杂的多 Agent 拓扑**。`subagents/` 支持并行分派，`defineConnection({ agent })` 支持 peer 调用，但这是「专家委派」模型，不是「图编排」。要做带条件分支、循环、人工审批节点的复杂流程，Google ADK 的图抽象或 Temporal 更合适——HN 上就有人说「Temporal workflows 是我支持多步 Agent 的主要积木」。
2. **你的合规要求「代码和凭证都不出网」**。托管部署会存你的仓库，自托管可以解决，但你要自己扛运维。
3. **你需要稳定的 API 契约**。0.3.0 GA 就在删字段且硬失败，说明接下来还会有语义变更。生产关键路径上要有 pin 版本 + CI 里跑 `validate` 的准备。
4. **你只是想调 LLM API**。那用 Vercel AI SDK 或裸 SDK，别为了目录约定引入一整套运行时。

**成本粗略估算：**

托管部署的计费走 Cursor 的模型用量。以文档里的 memory journal 示例为例，单轮 `inputTokens: 18234`、`outputTokens: 912`、`cacheReadTokens: 15002`——注意 cache read 占了输入的 82%，这是长 system prompt + 稳定工具集的典型画像。如果你把 `instructions.md` 写成三千字，每轮都在付这笔钱；而 `skills/` 的按需加载正是为了压这个数字。**所以「把什么放 instructions、什么放 skills」不是风格问题，是成本问题。** 一个每天跑 500 次的 PR 审查 Agent，instructions 少 2000 token，一天省 100 万 input token。

---

## 十、结论：Agent 工程正在收敛成「软件工程」

回到最开始那句 HN 评论。「被反复重造的轮子」这个判断，我认为对一半。

对的一半：harness 的核心循环——模型调用、工具执行、结果回填、循环终止——确实已经被重造了至少五遍，而且没有任何一家做出了数量级的差异。这部分是同质化的。

错的一半：**它们竞争的不是循环，是「Agent 应该长成什么样」这个问题的答案。** 而这个问题在 2026 年还没有共识，所以五种形状并存是合理的，不是浪费。

Cursor 给出的答案——Agent 是一个有 `bot/` 目录的仓库——是五个答案里最保守、也最容易被现有工程体系吸收的一个。它没有发明新的抽象，它把已有的抽象（目录、文件、git、CI、eval）重新排列了一遍。这种「不发明」本身就是一种判断：**Agent 工程的下一步不是更聪明的编排，而是更像软件工程。**

而这个判断，从它文档里最不起眼的一段代码就能看出来——那个把 PR diff 作为字符串注入 `workspaceFiles` 的 eval：

```ts
await t.send("Review pr/diff.patch and report blockers.", {
  workspaceFiles: { "pr/diff.patch": "diff --git a/..." },
});
```

固定输入、固定断言、可重复运行、失败可归因。这不是 AI 的技巧，这是测试的技巧。一个 Agent SDK 把测试放在这么靠前的位置，说明它已经不在赌「模型会变多强」，而是在赌「工程纪律决定谁能上生产」。

至于你要不要用它——我的建议是：**读它的文档，抄它的方法论，用不用它的运行时另说。** `hillclimbing.md` 那一页值得每个做 Agent 的人读一遍，哪怕你最后选了别的框架。因为「固定输入、改一个变量、用会失败的 eval 锁住收益」这套东西，跟框架无关，跟能不能把 Agent 做上线有关。

---

## 参考

- Cursor, *Introducing the Agent SDK*, 2026-10-28. https://cursor.com/blog/agent-sdk
- Cursor Docs, *Agent SDK*（含 Project layout / Evals / Hillclimbing / Deployment / Memory / Agent config 各页）. https://cursor.com/docs/agent-sdk
- Hacker News 讨论，"The Agent SDK"，107 条评论. https://news.ycombinator.com/item?id=50273731
- Cursor Docs, *Peer agents / Agent-to-agent*. https://cursor.com/docs/agent-sdk/guides/agent-to-agent
- Cursor Docs, *Changelog*（0.3.0 GA，2026-10-23，移除 `persistent`）. https://cursor.com/docs/agent-sdk/changelog
- Hugging Face Blog, *NVIDIA Nemotron 3.5 Transcribe and Granary v2*, 2026-10. https://huggingface.co/blog/nvidia/nemotron-transcribe-granary
- Google DeepMind, *Genie 4: A new generation of world simulation*, 2026-10-27. https://deepmind.google/blog/genie-4-a-new-generation-of-world-simulation/
