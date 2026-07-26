# 当浏览器不再只属于你：ego-lite 与"人机共浏"范式的崛起

> 从"Agent 驱动浏览器"到"人与 Agent 共享浏览器"——一次被低估的基础设施范式转移

## 引言：Agent 的"浏览器困境"

2026 年 7 月，一个名为 ego-lite 的开源项目在 GitHub 上以每天近 1000 星的速度飙升。它的定位很简单：**一个让你和 AI Agent 在同一个浏览器里并行工作的浏览器**。

这听起来不像是什么革命性概念。毕竟，我们已经有了一打"AI 浏览器"和"Agent 浏览器自动化工具"。但如果你仔细审视当前 Agent 生态中浏览器交互的现状，你会发现一个被严重低估的结构性问题：

**Agent 无法真正"使用"你的浏览器。**

不是技术上的不能——Playwright 可以驱动 Chrome，browser-use 可以操作网页。而是工程实践上的不能：你的登录态、你的 Cookie、你的扩展、你正在看的标签页——这些东西要么无法干净地传递给 Agent，要么一旦传递就与你的正常使用产生冲突。

ego-lite 的出现，标志着浏览器作为 Agent 基础设施的第三条路线正在成型。而这条路线，可能比前两条都更接近终局。

## 三条路线：Agent 浏览器交互的范式演进

### 第一条路线：自动化框架（2023-2025）

以 Playwright、Puppeteer、browser-use、Vercel agent-browser 为代表。核心思路是：**Agent 通过外部接口驱动一个独立的浏览器实例**。

```
Agent → CLI/API → CDP Protocol → Chrome Instance（独立）
```

这条路线的问题在 2026 年已经暴露无遗：

- **登录态断裂**：Agent 驱动的是一个"干净"的浏览器实例，你的 Gmail 登录、GitHub Session、企业内网 Cookie 都不存在。要么手动导出 Cookie（安全风险），要么让 Agent 重新登录（验证码、2FA 阻断）。
- **资源冲突**：如果 Agent 驱动的是你正在用的浏览器，你们的标签页会互相干扰。Agent 打开了一个页面，你的鼠标突然跳了。
- **CLI 瓶颈**：Agent 通过命令行与浏览器交互，每一步都是"发命令→等结果→解析输出→发下一条命令"。一个复杂的多步操作可能需要几十次工具调用，每次调用都消耗 Token。

Vercel 的 agent-browser 在 Rust 层面做了大量优化（启动速度、内存占用、Snapshot 质量），但它本质上仍然是一个"外部驱动器"——Agent 在浏览器外面，通过一根管子（CDP）操控里面的东西。

### 第二条路线：AI 原生浏览器（2025-2026）

以 ChatGPT Atlas、Perplexity Comet 为代表。核心思路是：**浏览器内置 AI Agent，Agent 和浏览器是一体的**。

这条路线解决了登录态问题（Agent 就在浏览器里面），但引入了新的限制：

- **Agent 锁定**：只有浏览器内置的那个 Agent 能驱动它。你用 Claude Code？不行。你用 Codex？也不行。
- **不可组合**：你无法让多个 Agent 并行工作，无法让外部工具链介入。
- **封闭生态**：浏览器本身是商业产品，Agent 的能力边界由厂商决定。

### 第三条路线：共享浏览器（2026-）

ego-lite 代表的路线。核心思路是：**浏览器是一个共享工作空间，人和 Agent 各自拥有独立的"空间"（Space），但共享同一套登录态、Cookie 和浏览器状态**。

```
┌─────────────────────────────────────────────────────┐
│                  ego-lite Browser                    │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │  Your Space  │  │ Agent Space 1│  │ Agent Sp.2│ │
│  │  (你的标签页) │  │ (Claude Code)│  │ (Codex)   │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │     Shared State: Logins / Cookies / Extensions ││
│  └─────────────────────────────────────────────────┘│
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │     ego-browser: JS Tool Layer (Snapshot,       ││
│  │     Click, Fill, Navigate, Capture)             ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

这不是"Agent 在浏览器外面驱动它"，也不是"Agent 被锁在浏览器里面"。而是**浏览器本身被重新设计为一个多租户工作空间**，人和 Agent 是一等公民，各自有独立的执行上下文，但共享底层状态。

## 技术深潜：为什么"Code-Base"比"CLI-Base"快 2.5 倍

ego-lite 最值得关注的设计决策不是"共享浏览器"这个概念本身，而是它暴露给 Agent 的接口形态：**不是 CLI 命令，而是 JavaScript 函数**。

传统的 Agent 浏览器交互是这样的：

```
Agent: 调用工具 `browser_navigate(url="https://github.com")`
       → 等待结果
Agent: 调用工具 `browser_snapshot()`
       → 等待结果，解析文本
Agent: 调用工具 `browser_click(ref="e12")`
       → 等待结果
Agent: 调用工具 `browser_type(ref="e15", text="search query")`
       → 等待结果
... 重复 10-30 次 ...
```

每一步都是一次完整的工具调用循环：构造请求→发送→等待→解析→决策→下一步。对于一个需要 15 步操作的复杂任务，这意味着 15 次工具调用，每次调用都带着完整的上下文（Snapshot 文本、历史消息），Token 消耗呈线性甚至超线性增长。

ego-lite 的做法是：**把浏览器能力暴露为页面内的 JavaScript 函数，Agent 写一段 JS 代码一次性执行多步操作**。

```javascript
// Agent 生成的代码，一次性执行
const page = await ego.navigate("https://github.com/login");
const snapshot = await ego.snapshot();
await ego.fill("#login_field", "username");
await ego.fill("#password", "password");
await ego.click("input[type=submit]");
await ego.waitForURL("**/dashboard");
const result = await ego.snapshot();
return result;
```

一次工具调用，完成 7 步操作。

ego-lite 的基准测试数据显示，在 4 个复杂浏览器自动化任务上，这种方式比 Vercel agent-browser 的 CLI 方式**快 2.5 倍，Token 消耗显著降低**。任务越复杂，差距越大。

这背后的洞察其实很朴素：**Agent 最擅长的事情是写代码，而不是一步步调用命令**。当你给 Agent 一个可编程的接口（而不是一个命令式的接口），它就能把多步任务编排成一个连贯的程序，而不是一个脆弱的命令序列。

这与 2026 年 7 月 GPT-5.6 引入的 "Programmatic Tool Calling" 理念一脉相承：从"模型调用工具"到"模型编程调用工具"。ego-lite 在浏览器这个具体领域里，把这个理念落到了实处。

## Space 抽象：Agent 并发执行的缺失原语

ego-lite 的另一个关键设计是 **Space**——每个 Agent 获得一个完全隔离的工作空间。

这解决了一个在实际使用中极其痛苦的问题：**Agent 并发**。

想象一个场景：你让 Claude Code 帮你做 10 个潜客的信息补全（每个都需要打开 LinkedIn、公司官网、Crunchbase），同时让 Codex 去爬 5 个竞品网站。在传统方案下：

- 如果用 10 个独立的 Playwright 实例：每个实例都没有你的登录态，LinkedIn 会要求重新登录，然后触发验证码。
- 如果共享一个浏览器实例：10 个 Agent 抢同一组标签页，互相覆盖，结果不可预测。

ego-lite 的 Space 模型让每个 Agent 在自己的 Space 里工作，共享登录态但互不干扰。你的鼠标不会跳，你的标签页不会被覆盖，而 15 个 Agent 在后台并行执行。

这个抽象看起来简单，但它填补了 Agent 基础设施栈中一个长期缺失的层：**Agent 的并发执行环境**。

在编码领域，我们有 git worktree 来实现并行开发分支。在计算领域，我们有容器和沙箱来实现并行任务执行。但在浏览器交互领域，直到 ego-lite 之前，没有一个原生的"并行工作空间"概念。

## 登录态问题：被忽视的 Agent 基础设施瓶颈

让我们把视角拉高一层。为什么"共享登录态"这件事如此重要？

2026 年的 AI Agent 已经可以写代码、做研究、管理文件、操作数据库。但有一个领域的能力远远落后于其他所有领域：**需要身份认证的 Web 交互**。

原因很简单：现代 Web 的身份认证体系是为人类设计的。OAuth 流程假设有一个人类在浏览器里点"授权"。2FA 假设有一个人类在看手机。CAPTCHA 假设有一个人类在证明自己是人类。

Agent 要绕过这些，目前的方案要么是：
1. **模拟人类**（Computer Use 路线）：截图→视觉理解→点击。慢、贵、脆弱。
2. **API 替代**（MCP/工具路线）：如果网站有 API，走 API。但大量网站没有开放 API。
3. **Cookie 注入**（灰色地带）：导出你的 Cookie 给 Agent。安全风险极高。

ego-lite 的方案是第四条路：**Agent 直接继承你的浏览器身份**。不需要模拟人类，不需要 API，不需要导出 Cookie。Agent 就在你的浏览器里，用你的 Session，像一个"在你电脑上操作的同事"。

这当然引入了新的安全问题——你的 Agent 现在可以访问你所有已登录的服务。但 ego-lite 通过 Space 隔离和可见性（你可以随时看到哪个 Space 有 Agent 在运行，可以接管或停止）来缓解这个风险。

更深层地看，这指向一个行业趋势：**Agent 的身份管理正在从"Agent 有自己的身份"转向"Agent 借用人类的身份"**。前者需要整个 Web 基础设施的改造（Agent 友好的 OAuth、Agent 身份标准），后者只需要一个浏览器。

## Snapshot 质量：Agent 的"视觉"瓶颈

ego-lite 声称拥有"市场上最强的页面 Snapshot"。这个说法值得认真对待，因为 **Snapshot 质量是 Agent 浏览器交互中最被低估的变量**。

Agent 不是真的"看到"网页。它看到的是一段文本化的页面表示——通常是 Accessibility Tree 的序列化，或者某种语义化的 DOM 摘要。这个表示的质量直接决定了 Agent 能否正确理解页面结构、找到目标元素、执行正确操作。

ego-lite 声称通过"内核级定制"（kernel-level customization）来处理深层嵌套 iframe 等困难场景。这暗示它不是简单地调用 Chrome 的 Accessibility API，而是在更底层对页面渲染做了干预。

对比来看：
- **Playwright/agent-browser**：依赖 Chrome 的 Accessibility Tree，对复杂 SPA、Shadow DOM、嵌套 iframe 支持有限。
- **Computer Use（截图路线）**：不依赖 DOM，但需要视觉模型理解像素，速度慢、成本高。
- **ego-lite**：内核级 Snapshot，声称在困难场景下显著优于竞品。

如果这个声称属实，那它意味着 Agent 浏览器交互的可靠性瓶颈不在模型能力，而在**感知层的质量**。一个 4o 级别的模型配合一个高质量的 Snapshot，可能比一个 Opus 级别的模型配合一个低质量的 Snapshot 表现更好。

## 安全与信任：共享浏览器的代价

任何"Agent 共享你的浏览器"的方案都必须面对一个根本性的信任问题：**你给了 Agent 你所有已登录服务的访问权限**。

ego-lite 的缓解措施包括：
- Space 隔离：Agent 只能在自己的 Space 里操作
- 可见性：你可以实时看到 Agent 在做什么
- 可中断：你可以随时接管或停止 Agent
- 本地存储：浏览数据不离开设备

但这些是"缓解"，不是"解决"。一个被 Prompt Injection 攻击的 Agent（比如在一个恶意网页上执行任务时），理论上可以访问你所有已登录的服务。

这与 2026 年 7 月 Hugging Face 披露的安全事件形成了有趣的呼应：在那次事件中，攻击者通过恶意数据集在 HF 的数据处理管线上执行代码，然后横向移动到内部集群。攻击面不是"模型"，而是"数据处理的执行环境"。

类似地，在共享浏览器模型中，攻击面不是"Agent 的推理能力"，而是"Agent 的执行环境"——也就是你的浏览器。一个恶意网页上的 Prompt Injection 可以通过 Agent 的手，触达你的 Gmail、你的银行、你的企业内网。

这不是 ego-lite 特有的问题——任何赋予 Agent 真实 Web 访问权限的方案都面临同样的风险。但 ego-lite 的"共享登录态"设计让这个风险更加集中：传统方案中，Agent 的独立浏览器实例本身就是一种隔离（虽然是以牺牲便利性为代价的隔离）。

## 生态位分析：ego-lite 在 Agent 基础设施栈中的位置

把 ego-lite 放在 2026 年的 Agent 基础设施全景中看：

```
┌─────────────────────────────────────────────────────┐
│  Agent Harness Layer                                │
│  (Claude Code, Codex, Cursor, OpenClaw)             │
├─────────────────────────────────────────────────────┤
│  Agent Skills / Tools Layer                         │
│  (ego-browser skill, MCP servers, CLI tools)        │
├─────────────────────────────────────────────────────┤
│  Agent Execution Environment                        │
│  (ego-lite Spaces, Sandboxes, Containers)           │  ← ego-lite 在这里
├─────────────────────────────────────────────────────┤
│  Browser / OS Runtime                               │
│  (Chromium, macOS, Linux)                           │
└─────────────────────────────────────────────────────┘
```

ego-lite 占据的是"Agent 执行环境"这一层——在 Harness 和底层 Runtime 之间，提供一个专为 Agent 设计的执行空间。

这个位置的竞争对手不是 browser-use（那是工具层），也不是 ChatGPT Atlas（那是完整产品）。它的真正竞争对手是**"Agent 不需要浏览器"这个假设**。

随着 MCP 协议的普及和 API 经济的发展，很多 Web 交互正在被"API 化"——Agent 不需要打开浏览器去 GitHub，它可以直接调用 GitHub API。但现实是，大量企业内网系统、SaaS 产品、政府网站仍然只有 Web 界面，没有开放 API。对于这些场景，浏览器交互在可预见的未来仍然是不可替代的。

ego-lite 赌的是：**在"API 覆盖一切"这个终局到来之前（如果它真的会到来的话），共享浏览器是 Agent Web 交互的最优解**。

## 数据与趋势

一些支撑这个判断的数据点：

- **ego-lite 上线后 GitHub 增长**：3,560 星，单日新增 986 星（2026-07-26），增速在浏览器工具类项目中罕见。
- **Agent 浏览器交互的 Token 成本**：根据 ego-lite 的基准测试，CLI 方式完成一个复杂任务平均需要 15-30 次工具调用；code-base 方式将其压缩到 3-5 次。按 Claude Sonnet 5 的定价，这意味着每个复杂浏览器任务的 Token 成本从 ~$0.15 降到 ~$0.06。
- **Computer Use 的成本对比**：Anthropic 的 Computer Use（截图+视觉理解路线）每个操作的平均成本约为 $0.03-0.05（包含视觉 Token），而 Snapshot+代码路线约为 $0.005-0.01。一个数量级的差距。
- **Agent 并发需求**：Cursor 在 2026 年 7 月披露其 Agent Swarm 架构以每秒 1000 次提交的速度运行。浏览器交互领域的并发需求虽然没那么极端，但"同时跑 5-10 个浏览器任务"已经是 power user 的常态。

## 未解决的问题

ego-lite 目前（2026 年 7 月）仍然是一个早期产品，有几个关键问题尚未解决：

1. **平台覆盖**：目前仅支持 macOS。Windows 和 Linux 在路线图上，但没有时间表。对于服务器端 Agent（无头环境），共享浏览器模型是否适用？
2. **安全模型的形式化**：Space 隔离的实现细节尚未公开审计。在恶意网页场景下的 Prompt Injection 防护，目前依赖 Agent Harness 层的能力，而非浏览器层。
3. **Snapshot 的可验证性**："市场上最强"是一个营销声称，缺乏独立的第三方基准测试。
4. **经验积累（Coming Soon）**：ego-lite 声称会将成功的操作蒸馏为可复用的工具和工作流，使类似任务快 5 倍。这个功能尚未发布，其实际效果有待验证。
5. **与 Headless 场景的兼容性**：大量 Agent 浏览器任务运行在 CI/CD 管线或服务器环境中，没有 GUI。ego-lite 的"共享浏览器"模型在这些场景下如何退化？

## 结语：浏览器作为 Agent 的"操作系统"

回顾计算机历史，每一次交互范式的转移都伴随着"共享"的深化：

- 从命令行到 GUI：多人共享一个屏幕（终端服务器）→ 每人一个屏幕
- 从桌面到 Web：多人共享一个应用（SaaS）→ 每人一个 Session
- 从 Web 到 Agent：人和 Agent 共享一个执行环境（？）

ego-lite 押注的是第三种"共享"：人和 Agent 共享一个浏览器，但各自拥有独立的执行空间。这不是一个技术上的小改进——它重新定义了"浏览器是谁的"这个根本问题。

在 2026 年的 Agent 基础设施栈中，模型能力已经不再是瓶颈（Claude Opus 5、GPT-5.6、GLM 5.2 都足够强），Harness 层正在快速成熟（Claude Code、Codex、Cursor 都在收敛到相似的架构），而**执行环境层**——Agent 实际"做事"的地方——仍然是最薄弱的一环。

浏览器是 Agent 执行环境中最大的一块拼图。ego-lite 不一定是对的，但它提出的问题是对的：**当 Agent 需要像人一样使用 Web 时，我们是应该给它一个"假人的浏览器"（自动化框架），还是应该让浏览器本身变成"人和 Agent 都能用的浏览器"？**

答案可能决定了未来三年 Agent 基础设施的走向。

---

*参考来源：*
- *ego-lite GitHub: https://github.com/citrolabs/ego-lite*
- *Vercel agent-browser: https://github.com/vercel-labs/agent-browser*
- *Hugging Face Security Incident Disclosure (July 2026): https://huggingface.co/blog/security-incident-july-2026*
- *GPT-5.6 Programmatic Tool Calling 分析: 本仓库 2026-07-10 文章*
- *Cursor Agent Swarm 架构: 本仓库 2026-07-21 文章*
