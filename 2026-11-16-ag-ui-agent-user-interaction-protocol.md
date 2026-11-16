# 当 Agent 走出聊天框：AG-UI 用 16 种事件重写「人机界面」

2026 年 11 月 16 日，`ag-ui-protocol/ag-ui` 出现在 GitHub Trending 日榜上。这个仓库的数字是这样的：

| 指标 | 数值（2026-11-16 抓取） |
|---|---|
| Stars | 17,834 |
| Forks | 1,818 |
| 贡献者 | 192（含匿名） |
| 创建时间 | 2025-05-07 |
| 最近推送 | 2026-11-15 |
| Open Issues | 593 |
| 许可证 | MIT |
| `@ag-ui/core` 周下载量 | 6,077,562 |
| `@ag-ui/core` 月下载量 | 19,085,336 |

18 个月，1.7 万星，单包月下载 1900 万次——这个量级已经不能用「又一个 Agent 框架」来解释。更值得注意的是它的发版节奏：11 月 10 日、12 日、13 日各发一版，几乎每两天一个 release。一个协议型项目能维持这种迭代速度，说明下游有一批人在真实生产环境里等着它修 bug。

它叫 AG-UI，全称 Agent-User Interaction Protocol。官方一句话定义：

> 一个开放的、轻量级的、基于事件的协议，用来标准化 AI Agent 如何连接到面向用户的应用。

本文要回答三个问题：为什么 MCP 和 A2A 之后还需要第三个协议；AG-UI 到底规定了什么（不是概念图，是事件、状态、恢复规则）；以及当你的产品真的接上它之后，会在哪些地方踩坑。

---

## 一、协议栈的第三层：工具、Agent、用户

过去两年，Agent 协议的故事基本是两层：

- **MCP** 解决 Agent 怎么拿工具、拿数据。它定义的是 Agent ↔ 资源。
- **A2A** 解决 Agent 之间怎么互相调用。它定义的是 Agent ↔ Agent。

但一个真实产品里最脆弱的那一段，恰恰是第三段：**Agent ↔ 用户**。

这段链路今天长什么样？每个团队自己写一套。LangGraph 用 `astream_events` 吐一种 JSON，CrewAI 有 `step_callback`，Vercel AI SDK 有 data stream protocol，OpenAI Assistants 有自己的 SSE 事件，Anthropic 的 Messages API 又是另一种流式结构。前端要为每个后端写一个适配器，改一次 prompt 结构就要改一次解析逻辑。

更麻烦的是，聊天框这种 UI 已经不够用了。用户要看见 Agent 正在改哪个单元格、正在填哪张表单、正在等哪一步审批；Agent 也要看见用户当前选中的那段代码、打开的那个文件、填了一半的表单。**这已经不是「流式文本」问题，而是双向状态同步问题。**

AG-UI 的定位就是把这一段标准化。它给出的三层分工非常清晰：

```
MCP   → Agent 与工具/数据
A2A   → Agent 与 Agent
AG-UI → Agent 与用户界面
```

三层不重叠，也不互相替代。这个定位之所以成立，是因为它抓住了两个别人没抓的东西：**共享状态**（shared state）和**中断恢复**（interrupt/resume）。前者决定了 Agent 能不能「看见」界面，后者决定了人能不能在关键时刻「拦住」Agent。

---

## 二、协议解剖：一次 run 就是一条事件流

AG-UI 的核心抽象小得惊人：

```typescript
type RunAgent = () => Observable<BaseEvent>

class MyAgent extends AbstractAgent {
  run(input: RunAgentInput): RunAgent {
    const { threadId, runId } = input
    return () =>
      from([
        { type: EventType.RUN_STARTED, threadId, runId },
        {
          type: EventType.MESSAGES_SNAPSHOT,
          messages: [
            { id: "msg_1", role: "assistant", content: "Hello, world!" }
          ],
        },
        { type: EventType.RUN_FINISHED, threadId, runId },
      ])
  }
}
```

**任何东西，只要能实现 `run(input) -> Observable<BaseEvent>`，就是 AG-UI 兼容的 Agent。** 它不要求你用它的运行时，不要求你换框架，甚至不要求你的 HTTP 层长什么样。

官方口径是「约 16 种标准事件类型」，按用途分成几类：

| 类别 | 代表事件 | 作用 |
|---|---|---|
| 生命周期 | `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR` / `STEP_STARTED` / `STEP_FINISHED` | 界定一次 run 的边界与内部阶段 |
| 文本消息 | `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END` | 流式 token，带 messageId 做拼接 |
| 工具调用 | `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` / `TOOL_CALL_RESULT` | 参数流式生成、执行、回填结果 |
| 状态管理 | `STATE_SNAPSHOT` / `STATE_DELTA` / `MESSAGES_SNAPSHOT` | 全量快照与增量补丁 |
| 活动 | `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` | 非消息型进度（“正在检索 3/7”） |
| 特殊 | `RAW` / `CUSTOM` | 透传原生事件、业务自定义 |

所有事件共享四个基础字段：`type`、`timestamp`（可选）、`rawEvent`（转换前的原始数据）、`metadata`（开放键值对象）。`metadata` 的设计值得单独说一句：消费者按 key 合并 metadata 到消息上，**后写覆盖先写**。这解决了一个很实际的工程问题——token 用量通常只有在这条消息的最后一个事件上才知道，生产者不需要在开头就预知它。

另外，大多数事件可以带一个可选的 `subagentRunId`。没有这个字段的事件属于父 Agent，带了就归属到某个子 Agent。这个设计让「一个主 Agent 派三个子 Agent 并行干活」的场景，前端可以按子 Agent 分组渲染，而不是把三路 token 混成一段乱码。

还有一点容易被忽略：`RUN_STARTED` 里有个 `parentRunId`，官方描述是「用于分支/时间旅行的血缘指针，形成 git 式 append-only log」。这句话信息量很大——它意味着这个协议在设计时就考虑了回滚和分叉，而不是事后打补丁。

---

## 三、状态同步：快照兜底，增量走 RFC 6902

AG-UI 的状态模型只有两条规则：

1. 状态是一个结构化对象，跨交互持久存在，Agent 和前端都能读写。
2. 同步只有两种方式：全量 `STATE_SNAPSHOT`，增量 `STATE_DELTA`。

```typescript
interface StateSnapshotEvent {
  type: EventType.STATE_SNAPSHOT
  snapshot: any
}

interface StateDeltaEvent {
  type: EventType.STATE_DELTA
  delta: JsonPatchOperation[]  // RFC 6902
}
```

选 JSON Patch 而不是「自定义 diff 格式」，是一个很克制的决定。`add` / `remove` / `replace` / `move` / `copy` / `test` 六种操作有现成库、有 RFC、有测试套件，前端不需要为这个协议再学一套语义。

但真到生产环境，这段设计会冒出三个必须自己处理的问题：

**第一，顺序与乱序。** SSE 本身保序，但一旦换 WebSocket 或多路复用，delta 就可能交错。协议没有规定序号字段，靠的是传输层保证。这意味着如果你要做多标签页同步、或者断线重连后补发，必须在应用层加 `runId` + 递增序号，否则一个晚到的 `replace` 会覆盖掉更新的值。

**第二，delta 的幂等性。** `replace` 是幂等的，`add` 到数组不是。断线重连时如果重放一段 delta，数组会重复插入。实践做法是：重连后先让后端发一次 `STATE_SNAPSHOT`，把前端状态整体替换，再继续消费后续 delta。协议本身给了快照这个「复位按钮」，但要不要按、什么时候按，是客户端的事。

**第三，Agent 改状态和用户改状态会打架。** 典型场景：Agent 正在往表格里写第 5 行，用户同时删了第 3 行。JSON Patch 的路径是绝对路径（`/rows/4`），删掉第 3 行之后，Agent 那条指向 `/rows/4` 的补丁就会打到错误的行上。RFC 6902 里的 `test` 操作就是干这个的——先校验再修改，不匹配就整批失败。**如果你的产品有并发编辑，请在关键 delta 前面加 `test`，否则这类 bug 会以「数据偶尔串行」的形式出现，极难复现。**

`MESSAGES_SNAPSHOT` 是另一个实用设计：它一次性给出完整消息列表，用于「连接中断后重建对话」「服务端压缩历史」这类场景。官方在 `RunStarted` 的 `input` 字段里也留了同样的余地——可以只发增量消息，由 `compactEvents()` 归一化。

---

## 四、工具调用的双向性：前端也是一个执行器

MCP 让 Agent 能调后端工具。AG-UI 补上的是另一半：**Agent 可以调前端工具**。

协议里的 `Tool` 结构和 OpenAI function calling 一致：`name` + `description` + JSON Schema 的 `parameters`。区别在于工具定义的位置：

- **后端定义的工具**留在 Agent 框架配置里，由后端执行。
- **客户端定义的工具**通过 `RunAgentInput.tools` 传进来，Agent 调用时事件流回到前端，由前端执行。

这个能力打开的场景很具体：Agent 说「帮我把这个图表切换成折线图」，前端收到 `TOOL_CALL_START`，本地执行 `switchChartType`，再把结果通过 `TOOL_CALL_RESULT` 回填。整个过程不需要后端知道你的图表库是 ECharts 还是 D3。

代价是**安全边界整体前移**。后端工具的执行环境是你控制的服务器；前端工具的执行环境是用户的浏览器。任何「前端工具」实际上都是暴露给 Agent 的一段可调用代码，而 Agent 的输入可能被 prompt injection 污染。实践上至少要守住三条：

1. 前端工具必须是**白名单注册**，不能由 Agent 动态声明。
2. 涉及写操作的前端工具（提交表单、删除、支付）必须走 interrupt 审批，不能直达。
3. 工具返回值要当作不可信输入处理，尤其是会被渲染进 DOM 的部分。

第三条在 2026 年尤其重要。当 Agent 能读写页面状态、又能调用前端函数时，「XSS」这个词的含义变了——不再只是用户输入注入脚本，而是**模型输出驱动了本不该被触发的 UI 动作**。

---

## 五、Interrupt：整个协议里最难、也最值钱的部分

如果只让我保留 AG-UI 的一个设计，我会选 interrupt。

大多数 Agent 框架的「human-in-the-loop」是假的：跑完一整轮，把结果丢给用户看，用户点个「继续」。这不是中断，这是批处理。真正的中断要求：Agent 在**执行到一半**时停下来，把「我在等什么」序列化出去，等人回复，然后**从断点继续**，而不是重跑。

AG-UI 的做法是把中断建模成一次 run 的正常结局：

```typescript
// Run 1 结束
{ type: "RUN_FINISHED", outcome: { type: "interrupt", interrupts: [...] } }

// Run 2 开始（同一个 thread）
RunAgentInput { threadId, resume: [{ interruptId, status, payload? }, ...] }
```

`Interrupt` 对象的字段很讲究：

| 字段 | 作用 |
|---|---|
| `id` | 关联 interrupt / resume / 幂等 / 审计的相关系键 |
| `reason` | 分类路由提示，核心值含 `tool_call` 等 |
| `responseSchema` | 期望的 `resume.payload` 的 JSON Schema |
| `expiresAt` | 可选 ISO-8601 TTL，过期 resume 直接 `RunError` |
| `message` | 给用户看的说明 |

配套的规则一共八条，其中三条决定了实现难度：

- **必须覆盖全部未决中断。** 一次 `resume` 数组要回应上一轮所有 open interrupt，**不支持部分恢复**。这逼着前端把「同时等三个审批」当成一个整体来处理。
- **幂等。** 同一个 `interruptId` 重复提交必须安全。网络重试是常态，没有这条，一次超时重发就会让 Agent 执行两遍副作用。
- **恢复模式无关。** 中断发生时，Agent 必须把恢复所需的状态全部发出去，协议不假设你是「重放事件」还是「框架原生 checkpoint」。这句话翻译过来：**恢复的正确性责任在 Agent 实现方，不在协议**。这是最容易背锅的地方——很多人以为用了 AG-UI 就自动获得断点续跑，其实协议只规定了「你必须把状态交出来」，交得够不够，是你的事。

`expiresAt` 的存在也说明设计者想过真实运维：审批可能压一小时，也可能压三天。三天后用户点「同意」，Agent 早就该报错而不是拿着过期上下文继续跑。

从审计角度看，`interrupt.id` 是最好的锚点。一次「Agent 提议删除 200 行数据 → 人批准 → 执行」的完整链路，可以用这一个 id 串起来：谁提的、提的什么、谁批的、什么时候批的、执行结果如何。这在金融、医疗这类需要留痕的场景里，比任何「Agent 可观测性平台」都实在。

---

## 六、传输层与中间件：SSE 是默认值，不是约束

AG-UI 明确不规定传输方式，官方列举了 SSE、WebSocket、webhook。参考实现是 HTTP + SSE，这也是最省事的选择：单向流、自动重连、代理友好、`EventSource` 原生支持。

但它留了一个更重要的东西：**中间件层的「宽松匹配」**。

意思是，后端不必严格产出 AG-UI 格式的事件，只要「兼容」就行——字段名对得上、语义能映射，中间件负责转换。这一条是它能快速吞下十几个框架的根本原因。让 LangGraph 改自己的事件模型是不可能的，让它写一个 200 行的适配器是可能的。

官方给的接入面同样很薄：

```typescript
const agent = new HttpAgent({ url: "https://your-agent-backend/run" })
```

一个 URL，一个 `HttpAgent`，前端就拿到了完整事件流。需要自定义时，实现 `AbstractAgent.run()` 即可。这种「默认能用、深入可改」的分层，是协议类项目能不能活下来的分水岭——太多协议死在「要么全用我的，要么别用」。

---

## 七、生态：12 个框架的公约数，也是它的风险

AG-UI 官方列出的支持矩阵，覆盖了当下主流的一线框架：

| 类型 | 框架 |
|---|---|
| 深度合作 | LangGraph、CrewAI |
| 一方支持 | Microsoft Agent Framework、Google ADK、Google Antigravity、AWS Strands Agents、Mastra、Pydantic AI、Agno、LlamaIndex、AG2 |
| 进行中 | AWS Bedrock Agents |

再加上 CopilotKit 自家的 Direct-to-LLM 内置 Agent。这套名单的含金量在于：**它同时覆盖了 LangChain 系、微软系、Google 系、AWS 系**。这四家在 Agent 框架上是直接竞争关系，能让它们都实现同一个前端协议，说明 AG-UI 抢到的是一个「中立地带」——没有人愿意让自己的 Agent 只能配自己的 UI。

Dojo（dojo.ag-ui.com）是另一个被低估的资产。它把每个框架的每个特性做成可交互 demo：shared state、tool-based generative UI、HITL。对接新框架时，跑一遍 Dojo 就知道适配器写得对不对。**协议项目最缺的从来不是规范文档，是可执行的合规测试**，Dojo 填的就是这个坑。

但风险同样明显，至少三条：

**第一，商业绑定。** AG-UI 由 CopilotKit 发起并主导，MIT 许可，规范开放，但参考实现、文档、Dojo 都在 CopilotKit 的域名下。这不影响使用，但影响治理——如果哪天 CopilotKit 的商业策略变了，社区有没有能力接管？对比 MCP 交给 Linux 基金会之类的做法，AG-UI 目前还是「公司项目 + 开放规范」的形态。

**第二，事件膨胀。** 官方说「约 16 种」，但文档里已经有 Activity、Subagent、Draft 等分类，`metadata` 又是完全开放的。协议的熵会随时间上升。今天的 16 种事件是优势（好学），两年后如果变成 40 种，新接入方就要面对「我该实现哪些」的问题。规范里区分「核心」和「草案」是必要的，DeepSeek 之外的团队更该关心的是：**你的适配器声明支持哪个协议版本，而不是「支持 AG-UI」。**

**第三，593 个 open issue。** 对一个 18 个月、192 位贡献者的项目，这个数字不算离谱，但也不算健康。协议类项目的 issue 往往集中在「边界语义」上——某个事件该不该带某个字段、某种错误该用 `RunError` 还是新事件。这类讨论收敛得慢，会直接体现为下游适配器的行为不一致。

---

## 八、如果你要接：一份工程 checklist

把上面的分析压缩成可执行的动作，大概是这八条：

1. **pin 版本。** `@ag-ui/core` 每两三天发一版，别用 `^`。协议兼容性和实现兼容性是两件事。
2. **断线重连先要快照。** 任何重连路径都以 `STATE_SNAPSHOT` 复位，不要试图重放 delta。
3. **delta 加 `test`。** 有并发编辑的地方，用 RFC 6902 的 `test` 做前置校验，让冲突显式失败而不是静默写错。
4. **前端工具白名单 + 审批。** 写操作一律走 interrupt，读操作也要限制返回体积。
5. **interrupt 全量响应。** 前端要把「所有未决中断」当成一个表单来渲染，不能一次只处理一个。
6. **给 interrupt 设 TTL。** 没有 `expiresAt` 的审批会变成僵尸任务，占用 thread 状态。
7. **记录 `subagentRunId`。** 多 Agent 场景下，没有这个字段你无法归因「这句话是哪个子 Agent 说的」。
8. **在 CI 里跑 Dojo 用例。** 适配器改动后跑一遍，比读规范快十倍。

---

## 九、结语：协议竞争的本质是「谁定义边界」

回头看这三层协议，会发现一个有意思的对称：

- MCP 定义的是 **Agent 的能力边界**——它能碰什么。
- A2A 定义的是 **Agent 的协作边界**——它能找谁。
- AG-UI 定义的是 **Agent 的责任边界**——它能自己决定什么，什么必须问人。

前两个边界是技术问题，第三个是产品问题和治理问题。这也是为什么 AG-UI 里最「不性感」的 interrupt 章节，反而是长期价值最高的部分。一个能停下来问、能被打断、能留痕的 Agent，才可能被放进真实业务流；一个只会往前跑的 Agent，永远只能待在 demo 里。

17,834 颗星、月下载 1900 万次，说明市场已经用脚投票：**前端需要一层标准，而不是又一套 SDK。** 至于这层标准最终是 AG-UI、还是某个大厂后来居上的方案，取决于接下来 12 个月它在治理上的动作——毕竟协议这种东西，写得再好，也只是入场券。

---

**参考来源**

- AG-UI 官方仓库与 README：https://github.com/ag-ui-protocol/ag-ui
- AG-UI 文档（Events / State / Tools / Interrupts / Architecture）：https://docs.ag-ui.com
- AG-UI Dojo 交互式用例：https://dojo.ag-ui.com
- GitHub API 与 npm downloads API 数据，抓取时间 2026-11-16
- Hugging Face Blog RSS、Hacker News Front Page API，同日抓取用于选题比对
