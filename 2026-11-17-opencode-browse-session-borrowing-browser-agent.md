# 把已登录的浏览器借给 Agent：OpenCode Browse 的会话借用架构与安全边界

2026 年 11 月 16 日，OpenCode 背后的 Anomaly 团队发布了 `browse` v0.1.0，同一天它出现在 Hacker News 首页（68 points）。官方一句话介绍很直白：

> Let your AI agents use your real browser: your tabs, your logins, your extensions.

翻译过来就是：让 Agent 用你**真实的**浏览器——你的标签页、你的登录态、你的插件。

这句话听起来像又一个浏览器自动化工具，但它解决的是一个非常具体的工程痛点：**Agent 能写代码、能调 API，却常常卡在登录框前面。** 企业内网要 SSO，SaaS 要邮箱验证码，银行要 2FA，Cloudflare 还要人机验证。你给 Agent 一个全新的无头浏览器，它就是一个没有身份的网络游民，连公司 wiki 都进不去。

`browse` 的答案不是"让 Agent 学会登录"，而是"把你的会话借给它"。

| 指标 | 数值（2026-11-17 抓取） |
|---|---|
| GitHub Stars | 689 |
| Forks | 53 |
| 创建时间 | 2026-10-27 |
| v0.1.0 发布时间 | 2026-11-16 |
| 许可证 | MIT |
| 主语言 | TypeScript + Rust（relay 已用 Rust 重写） |
| 支持的 MCP 客户端 | 30+（OpenCode、Claude Code、Codex、Cursor、VS Code、Zed…） |
| 支持的浏览器 | Chrome、Edge、Brave、Arc、Helium、Vivaldi、Opera、Chromium |
| 代码规模 | 约 4.9 MB 仓库，单二进制数 MB |

689 星不算爆款，但它的发布节奏值得注意：v0.0.14（11/07）→ v0.0.15（11/08）→ v0.0.16（11/08）→ v0.0.17（11/14）→ v0.1.0（11/16），十天五个版本，最后一个版本直接把整个 relay 用 Rust 重写。这种迭代密度通常意味着背后有真实用户在持续反馈，而不是一个 demo 项目。

更有意思的是它选择的技术路线。过去两年，"让 Agent 操作浏览器"这件事分裂成了三条路，每条路都在为"身份"付出不同的代价。

---

## 一、三个路线，一个共同难题：身份从哪来

**路线 A：全新无头浏览器。** Playwright、Puppeteer、Vercel 的 agent-browser、Lightpanda 都属于这一类。优点是干净、可复现、可并行、易于隔离；缺点是**没有登录态**。工程团队通常要写一堆 storageState 导出脚本、cookie 注入、测试账号池，还要和风控系统斗智斗勇。更现实的问题是：很多站点的登录流程本身就需要人——短信、OTP、扫码、设备指纹校验。

**路线 B：CDP 直连。** `chrome-devtools-mcp` 这类项目通过 Chrome DevTools Protocol 连接一个已有的浏览器实例。它解决了"用真实浏览器"的问题，但暴露出另一个问题：**CDP 是全局的**。一旦连上，Agent 理论上能看见所有标签页、所有 cookie、所有已登录站点。你很难向安全团队解释"这个 Agent 只能看这一个 tab"。

**路线 C：借用会话。** `browse` 和此前的 ego-lite 走的是这条路：不复制登录态，而是**把用户已经打开的标签页临时租给 Agent**。身份不需要迁移，权限不需要重建，Agent 用的是"你此刻正在用的那个浏览器"。

三条路线的对比如下：

| 维度 | 无头浏览器 | CDP 直连 | 会话借用（browse） |
|---|---|---|---|
| 登录态覆盖 | 需手工注入 | 全量，过度授权 | 已有会话，按 tab 授权 |
| 隔离性 | 强（独立进程） | 弱（全局浏览器） | 中（tab 级边界） |
| 人能介入 | 难 | 中 | 一等公民（handoff） |
| 反爬/风控 | 容易被识别 | 真实指纹 | 真实指纹 + 人类输入 |
| 爆炸半径 | 小 | 整个浏览器 | 借出的 tab |
| 工程复杂度 | 中 | 中 | 高（扩展 + relay + 协议） |

`browse` 的真正创新不在"能点按钮"，而在它把**授权单位从"浏览器"缩小到了"标签页"**，并且把"需要人来做的步骤"设计成了协议里的一等操作。这两件事，是本文想拆开讲的核心。

---

## 二、架构拆解：一个 Rust relay，一个扩展，一层薄薄的 MCP

`browse` 的部署结构只有三段，但每段都有明确的责任边界：

```
┌─────────────┐   stdio/MCP   ┌──────────────┐   WebSocket   ┌─────────────────┐
│  Agent      │ ────────────► │ browse relay │ ◄────────────► │ Chromium 扩展    │
│ (Claude Code│               │ Rust,        │                │ chrome.debugger │
│  Codex...)  │ ◄──────────── │ 127.0.0.1:19988 │             │ tabGroups 等    │
└─────────────┘               └──────────────┘                └────────┬────────┘
                                                                       │ CDP
                                                                       ▼
                                                              ┌─────────────────┐
                                                              │ 用户的真实浏览器  │
                                                              │ 已登录的站点     │
                                                              └─────────────────┘
```

**第一段：MCP 代理。** Agent 启动 `browse mcp`，这是一个很小的 stdio 代理进程。它不直接碰浏览器，而是按需拉起 relay，然后把每个工具调用转发到 `127.0.0.1:19988`（如果端口被占用，会依次尝试 19990–19997）。这个设计的妙处在于：MCP 客户端只需要会 stdio，不需要知道浏览器在哪、是否在另一台机器上。

**第二段：relay。** v0.1.0 用 Rust 重写，是整个系统的状态机。它保存 Agent 打开的标签页、它们的选项（分组、允许的域名、只读标记）、handoff 状态、录屏和网络抓包，并通过 CDP 与每个 tab 通信。`execute` 工具调用的 JavaScript 也在 relay 内嵌的 QuickJS 引擎里执行，带 CPU、内存、时间限制。relay 空闲时会自动退出——"没有 Agent 用它的时候，它就不存在"。

**第三段：浏览器扩展。** 扩展通过 WebSocket 连接 relay，用 `chrome.debugger` 在标签页里执行命令，用 `chrome.tabGroups` 把 Agent 的标签页收进折叠分组，用 `chrome.alarms` 管理空闲标签页的回收。它同时承担 UI 职责：工具栏徽章显示 `ON` / `RUN` / `WAIT`，handoff 时在页面上弹出一个小卡片。

这个三段式结构解决了一个经常被忽视的问题：**Agent 运行的位置和浏览器运行的位置可以不同。** 通过 `browse install --remote`，relay 监听所有网卡（但 HTTP API 仍只绑定 `127.0.0.1`），浏览器可以在另一台电脑上通过 Tailscale 或 WireGuard 连过来。这意味着"在服务器上跑 Agent、在你笔记本的浏览器里操作"成为可能——当然，官方也明确说了：连接本身不加密，必须跑在加密网络里。

### 2.1 Tab 即句柄：一个被低估的抽象

v0.1.0 的 release notes 里有一句话：

> Tabs are the handle: `navigate` opens a background tab and returns its id, and every other call names that tab. Sessions and their tools are gone.

这句话是整个设计的钥匙。此前的浏览器自动化工具大多以"session"或"page"为句柄，而 `browse` 把**标签页 ID** 作为唯一的上下文载体：

```json
// 1. 打开页面，拿到 tab id
{ "tool": "navigate", "args": { "url": "https://news.ycombinator.com" } }
// → { "tab": "t_8f3a", "title": "Hacker News" }

// 2. 后续所有操作都显式带上这个 tab
{ "tool": "snapshot", "args": { "tab": "t_8f3a" } }
{ "tool": "click", "args": { "tab": "t_8f3a", "ref": "e12" } }
```

为什么这个抽象重要？因为它让**权限、生命周期、并发**三件事同时变得可管理：

- **权限**：`navigate` 时可以带 `allowedOrigins`，这个 tab 从此只能访问指定的域名；带 `readOnly`，就只能看不能点。
- **生命周期**：10 分钟没人碰的 tab 自动关闭（正在执行任务的除外）；relay 重启后，Agent 打开的 tab 和它们的选项会被恢复。
- **并发**：多个 Agent 各自持有自己的 tab id，互不干扰。OpenCode 甚至改成"每个项目一个 browse"，而不是每个目录一个。

对比之下，CDP 直连模式下 Agent 面对的是一个全局的 `Target` 列表，它必须自己记住"我刚才操作的是哪个页面"，而任何一次页面跳转都可能让这个记忆失效。`tab` 句柄把这种隐式状态变成了显式参数——这正是 Agent 工具设计里最重要的原则之一：**不要让模型依赖隐式上下文。**

### 2.2 工具面：plain 与 execute 的双轨制

`browse` 暴露的工具数量在 20 个左右，覆盖导航、快照、点击、填表、按键、选择、悬停、拖拽、滚动、等待、对话框、上传、求值、截图、截图对比、网络抓包、控制台、录屏、设备模拟、WebMCP、标签页管理、handoff、演示录制、设置和状态。

但它没有把这些工具一股脑塞给所有客户端，而是按客户端能力分轨：

- **OpenCode** 拿到的是"plain tools"，因为 OpenCode 支持 code mode，可以在代码里组合工具调用；
- **其他 MCP 客户端**（Claude Code、Codex、Cursor 等）只拿到 `execute`、`status`、`tabs` 三个工具，其中 `execute` 运行一段 JavaScript，里面有一个 Playwright 风格的 `page`、`snapshot()`、`ref()`、`handoff()` 和 `browse.<tool>()`。

这个设计很务实。MCP 的工具列表是有成本的：工具越多，模型的系统提示越长，选错工具的概率越高。20 个细粒度工具对支持代码模式的 Agent 是优势，对只做单步 function calling 的 Agent 则是负担。用 `execute` 把它们包一层，等于给模型一个"编程接口"而不是"菜单"。

值得一提的是 `execute` 的安全定位，官方写得很清楚：

> `execute` is sandboxed, not a boundary.

QuickJS 沙箱限制的是资源（CPU、内存、时间）和文件系统访问，不是权限边界。Agent 在这个沙箱里调用的每一个浏览器工具，仍然拥有你借出标签页的全部权限。**沙箱防的是"代码写崩"，不是"代码作恶"。**

---

## 三、Handoff：把"人来一下"写进协议

如果只能从 `browse` 里挑一个设计来学，我会选 handoff。

传统浏览器自动化遇到登录、2FA、支付确认这类步骤，通常有三种处理方式：让脚本 sleep 等人手动操作、把凭据硬编码进脚本、或者直接失败。这三种都很糟：第一种不可观测，第二种不安全，第三种不可用。

`browse` 把它抽象成了一个工具调用：

```json
{ "tool": "handoff", "args": {
    "tab": "t_8f3a",
    "reason": "需要输入 GitHub 的一次性验证码",
    "timeout_ms": 300000
} }
```

调用之后，扩展会在页面上弹出一个小卡片，显示站点的 origin；工具栏徽章从 `RUN` 变成 `WAIT`；如果这个 tab 正在录屏，用户会收到系统通知。人完成操作后，点卡片上的 **Continue**（或工具栏按钮），Agent 的调用返回，任务继续。

这里面有几个细节值得展开：

**第一，完成动作必须是"真实点击"。** 官方明确写了："Only a real click on the card or the toolbar button finishes a handoff, so a page can't fake it." 这挡住了一类很现实的攻击：恶意页面在自己的 DOM 里伪造一个"继续"按钮，诱导 Agent 或用户点击，从而绕过人工确认。把确认动作放在扩展的 UI 层（isolated world）而不是页面里，是唯一可靠的解法。

**第二，handoff 是有状态的，不只是等待。** 等待期间，Agent 不能操作这个 tab；徽章状态对外可见；超时后调用失败而不是静默挂起。这让"人机协作"变成可观测的状态机，而不是一段黑盒 sleep。

**第三，还有一个反向工具 `demonstrate`。** 它请用户演示一遍流程，同时录下操作步骤。这个设计暗示了一个更大的方向：**人类演示正在成为 Agent 的技能获取方式**。先示范、再回放、最后让 Agent 自己在受控范围内重试——这比写一份自然语言 SOP 可靠得多。

从产品角度看，handoff 的价值不只是"解决登录"。它实际上定义了一条**责任分界线**：

- 机器可以做的：读页面、填表单、点按钮、抓数据；
- 只有人能做的：证明"我是我"（2FA）、承担金钱风险（支付）、承担法律风险（签署）、通过人机验证。

把这条线画清楚，比让 Agent "什么都能干"更有工程价值。因为线上事故往往不是 Agent 不会做，而是它**做了不该它做的事**。

---

## 四、安全模型：假设页面会骗你，假设本机会偷你

`browse` 的 README 里有一句很清醒的话：

> browse drives the browser you're signed in to, so it assumes that what an agent reads (a web page, an email) may try to steer it, and that other programs on your computer may try to use the relay.

这句话对应两个经典威胁模型：**间接提示注入**（indirect prompt injection）和**本地端口劫持**（local port hijacking）。它的防御设计基本围绕这两点展开。

### 4.1 配对：ECDH + 一次性码 + 扩展 ID 白名单

配对流程是这样的：

1. `browse pair` 生成一个一次性配对码（`XXXX-XXXX`，10 分钟有效）；
2. 用户在扩展的 options 页面输入配对码；
3. 浏览器和 relay 通过一次 ECDH 密钥协商，各自得到一把随机密钥；
4. 此后每次连接，双方都要证明自己持有这把密钥，扩展才会执行命令。

关键点在第三步：**配对码和密钥都不在连接上传输**。即使有人在配对窗口期抓到了配对码，他也拿不到协商出来的密钥。再加上 relay 只接受已发布的扩展 ID（或 `OPENCODE_BROWSER_EXTENSION_ORIGINS` 里显式列出的 ID），"先占住 19988 端口冒充 relay"这类攻击就失效了。

同时，每个发往 relay 的请求都必须带上 `~/.local/share/browse/relay-token` 里的 token（仅当前用户可读），relay 只监听 `127.0.0.1`，并拒绝跨站请求和异常的 `Host` 头。这是一套相当标准的本地服务防护组合，但很少有工具真的把它做全。

### 4.2 权限收敛：从"整个浏览器"到"这个 tab 的这几个域名"

真正有意思的是运行时的权限收敛。`browse` 在 CDP 层面设了一批"护栏"：

- 清除 cookie、缓存、站点数据——拒绝；
- 关闭浏览器、修改站点权限——拒绝；
- 关闭页面按"关闭 target"处理：借出的 tab 是**释放**，不是关闭；
- cookie 和 storage 的访问被限制在**该 tab 自己页面的 host** 上；
- Agent 不能打开浏览器内部页面、其他扩展、本地文件，也不能把窗口提到你前面；
- 用 `allowedOrigins` 打开的 tab 只能去指定站点；`readOnly` 的 tab 只能看。

这套规则的本质是把浏览器的**全局能力**降级成 tab 的**局部能力**。它不完美——同源策略内的越权、页面内的 CSRF、OAuth 授权页上的误点，仍然存在——但它把"Agent 一旦被注入就能清空你所有 cookie"这种灾难级后果，压缩到了"它能操作你借给它的那个站点"。

这里有个值得记住的原则：**Agent 的权限不应该等于"它能调用的 API 集合"，而应该等于"它当前任务的上下文范围"。** tab 就是那个上下文范围的最小可表达单位。

### 4.3 那些"逃生舱"说明了什么

README 里列了一串环境变量逃生舱：允许读写全部 cookie、允许访问全部站点 storage、允许前台窗口、允许 `file:` URL、允许更宽的文件根目录、关闭拟人输入……

这些开关的存在本身就说明了一件事：**默认配置是保守的，而真实世界总有例外。** 比如你要让 Agent 处理一个跨多个子域名的后台系统，`allowedOrigins` 就不够用；比如你要让它读本地导出的 CSV，就必须放开文件根目录。

好的安全设计不是"没有逃生舱"，而是"逃生舱必须显式打开、有明确名字、并且能被审计"。对比之下，很多工具默认给你全量权限，然后在一份没人读的文档里写"请注意安全"。

### 4.4 拟人输入与"不被发现"的伦理张力

`browse` 默认开启拟人输入：曲线鼠标轨迹、有节奏的键入、平滑滚动。官方同时很诚实地写了：

> This makes an agent hard to spot, not impossible: the browser shows its "started debugging" bar while the debugger is attached.

这段设计有一个绕不开的张力：**拟人化输入让 Agent 更难被风控识别，但也让"机器操作"变得更隐蔽。** 从用户角度，这提升了自动化成功率；从站点角度，这是在绕过它们的检测。类似地，遇到 Cloudflare、captcha、"access denied" 页面时，`browse` 会选择上报并交给人类，而不是尝试破解——这是一条正确的线。

我在看这段时想到 MIT Technology Review 最近一篇文章的标题：*Building trustworthy AI by fencing it in, not predicting it*（用围栏约束 AI，而不是预测它）。`browse` 的安全模型正是这个思路：它不去预测 Agent 会不会被页面骗，而是用 tab 边界、origin 白名单、真实点击确认这些"围栏"把损失限制住。这比在 prompt 里写一百句"不要相信网页内容"有用得多。

---

## 五、和同类方案比，它到底强在哪

把 `browse` 放进 2026 年的浏览器 Agent 版图里，可以看得更清楚。

**对比 Playwright / agent-browser：** Playwright 是"测试框架"，它的世界观是"每次从零开始、结果可复现"。`browse` 是"借用现场"，它的世界观是"复用已有的登录态和浏览器指纹"。这两者不是替代关系：CI 里跑回归用 Playwright，生产里替人办事用 `browse`。前者的核心指标是 flakiness，后者的核心指标是任务成功率。

**对比 chrome-devtools-mcp：** 后者是"给 Agent 一把浏览器调试的瑞士军刀"，强在性能分析、网络调试、DOM 检查，适合开发者排障。`browse` 强在"以人为中心的会话管理"：tab 分组、handoff、空闲回收、借出/收回。一个是工程师工具，一个是操作员工具。

**对比 Lightpanda 这类"不渲染"的浏览器：** Lightpanda 用极低的资源开销换取速度，适合大规模抓取和 Agent 的"读网页"场景。但它没有真实登录态，也不适合需要人类接管的流程。`browse` 的资源开销明显更高（一个真实 Chromium + 调试器），换来的是"和在用的浏览器完全一致"。

**对比 ego-lite：** 两者都讲"共享浏览器"，但 ego-lite 更像一个为 Agent 重新设计的浏览器运行时，`browse` 则是"寄生"在你已有的浏览器上，通过扩展做权限收敛。前者的迁移成本高，后者的采用成本低——装个扩展、跑一条安装命令就能用，这对开发者工具的传播至关重要。

一个粗略的定位图：

```
                  真实登录态 / 人类接管
                          ▲
                          │
             browse ●     │     ● ego-lite
                          │
   低采用成本 ◄───────────┼───────────► 高控制力
                          │
        agent-browser ●   │   ● chrome-devtools-mcp
                          │
                          ▼
                  干净环境 / 可复现
```

`browse` 抢到的是一个很甜的位置：**采用成本低 + 真实身份 + tab 级授权**。这也是它敢在 v0.1.0 就把"30+ MCP 客户端开箱即用"当作卖点的原因——它不想让你改工作流，只想让你在现有工作流里多一个工具。

---

## 六、给 Agent 工具开发者的五条经验

抛开产品本身，`browse` 的工程实现里有几条经验值得所有做 Agent 工具的人抄走。

**1. 句柄要显式，不要依赖隐式状态。**
`navigate` 返回 tab id，后续调用必须带上。这看起来啰嗦，但它让模型的行为可预测、让并发变得安全、让日志可以按 tab 归因。相比之下，"当前活动页面"这种隐式状态是 Agent 工具里最常见的 bug 来源。

**2. 工具的粒度要匹配客户端的推理能力。**
支持 code mode 的客户端给细粒度工具，只做 function calling 的客户端给 `execute` 这种"编程入口"。同一个后端，两套工具面，这是 2026 年 MCP 工具设计的基本功。

**3. 把人类介入设计成异步、可观测的状态。**
handoff 不是"弹个窗然后阻塞"，它有状态、有超时、有 UI 反馈、有安全校验。任何需要人参与的工作流，都应该按这个标准设计，而不是塞一个 `input()` 或 sleep。

**4. 安全边界要写在能力模型里，不要写在提示词里。**
`allowedOrigins`、`readOnly`、CDP 护栏、配对密钥——这些都是**结构性约束**，模型再聪明也绕不过去。提示词里的"请勿访问其他网站"只是建议。

**5. 资源生命周期要可恢复。**
relay 重启后恢复 Agent 的 tab；空闲 tab 自动回收但不影响运行中的任务；更新只在空闲时进行。这些细节决定了工具能不能在真实工作流里长期存活，而不是在 demo 里跑一次就崩。

---

## 七、风险：当"你的浏览器"变成"Agent 的身份"

`browse` 把 Agent 的能力边界扩大了一大截，也把风险边界扩大了一截。有几个问题值得任何打算在生产环境使用它的人认真想清楚。

**第一，OAuth 的权限坍缩问题。** 你登录一个 SaaS 时，授权范围是那个应用；但当你把 tab 借给 Agent 时，Agent 继承的是**你在这个站点上的全部权限**。它不只能读，还能改、能删、能以你的名义发消息。OAuth 的 scope 机制在这里完全失效，因为浏览器不知道"这个操作是代表用户还是代表 Agent"。

**第二，数据外流的路径变短了。** Agent 读到的页面内容会进入模型上下文，而模型调用通常发往第三方 API。也就是说，你借出一个内含客户数据的后台 tab，等于把那份数据送进了模型提供商的服务器。`browse` 的隐私政策说"除了 Agent 发给模型提供商的内容，一切都不离开你的电脑"——这句话是对的，但它也恰好点出了最大的那个出口。

**第三，审计与合规。** 企业环境里，"一个扩展拥有 `debugger`、`tabs`、`tabGroups`、`scripting`、`webNavigation`、`notifications` 和全站点访问权限"是很难通过安全评审的。`browse` 目前没有内建的审计日志、DLP 钩子、企业策略下发（比如强制 `allowedOrigins` 白名单、禁用 `eval`、禁止录屏）。这些能力迟早会有，但在那之前，它更像是个人开发者的效率工具，而不是企业级基础设施。

**第四，多 Agent 并发的资源竞争。** 当一个 tab 被多个 Agent 或多个任务同时操作时，页面状态会互相干扰。`browse` 用 tab 隔离解决了大部分问题，但同一个站点的多个 tab 仍然共享 cookie、localStorage 和服务端会话。在电商、金融这类有状态站点上，并发操作可能触发风控或数据竞争。

**第五，扩展本身的供应链风险。** 扩展通过 Chrome Web Store 分发，自动更新；relay 二进制也从发布服务自动更新。这条链路一旦被攻破，攻击者拿到的是"你所有已登录站点的操作权"。官方做了 SHA-256 校验和签名验证，但这仍然是一条需要信任的高度集中化链路。

这些问题不是 `browse` 独有的，而是"会话借用"这条路线的固有代价。选择它，就要接受"便利性与攻击面成正比"这个事实。

---

## 八、结论：浏览器正在成为 Agent 的能力层

回到最初的观察。2026 年的 Agent 竞争，已经从"模型能不能推理"转向"Agent 能不能**办事**"。而办事的前提，是它能进入那些有身份、有权限、有历史状态的系统。

`browse` 给出的答案是：不要去重建身份，去**借用**身份；不要给 Agent 一个全新的浏览器，给它一个**受控的窗口**；不要让 Agent 假装是人，在它做不到的地方**把人请回来**。

这三个选择，分别对应三个工程判断：

1. **会话比凭据更容易管理。** 复制 cookie 会过期、会失效、会泄露；借用一个活着的会话，身份始终由人来持有。
2. **权限的最小单位是上下文，不是 API。** tab 是 Agent 任务上下文的最小可表达单位，比"整个浏览器"精确得多。
3. **人机协作需要协议，不需要弹窗。** handoff 把"人来一下"变成了可观测、可超时、可审计的状态转移。

v0.1.0 还很早期：689 星、28 个 open issue、企业能力缺失、扩展权限过宽。但它指出的方向是清晰的——**浏览器正在从一个"人类使用的应用"，变成"Agent 调用的能力层"**。而在这个转变里，最重要的设计问题不是"Agent 能做什么"，而是"Agent 被允许做什么，以及谁在什么时候可以收回权限"。

下一个值得观察的信号，是 Chrome 官方会不会推出类似的原生能力（比如更细粒度的调试授权、Agent 专用 profile），以及企业浏览器管理方案（MDM、扩展白名单、DLP）会不会把这类工具纳入治理范围。如果这两件事发生，2027 年的浏览器 Agent 市场会重新洗牌。

在那之前，`browse` 是一个很好的样本：它用不到 5MB 的代码，把"身份借用"这件事的工程细节和安全边界，几乎完整地演示了一遍。

---

**参考链接**

- OpenCode Browse 产品页：https://opencode.ai/product/browse
- 源码仓库：https://github.com/anomalyco/browse
- v0.1.0 Release Notes：https://github.com/anomalyco/browse/releases/tag/v0.1.0
- Hacker News 首页讨论（2026-11-16，标题 *OpenCode Browse*）：https://hn.algolia.com/?q=OpenCode%20Browse
- MIT Technology Review, *Building trustworthy AI by fencing it in, not predicting it*：https://www.technologyreview.com/
