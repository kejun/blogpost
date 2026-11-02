# 当一个浏览器决定不再画画：Lightpanda 1.0 深度拆解——Zig 重写、无渲染引擎，与 AI Agent 的浏览器成本账

2026 年 10 月 2 日，Lightpanda 发布 1.0。官方博客给出的数字很克制：两年、约 1 万次 commit、174 万个 Web Platform Tests（WPT）子测试通过、CORS 默认开启。

但在 GitHub 上，这个故事是另一种讲法：4 万颗星，日趋势榜前列，Zig 写的、不是 Chromium fork、不是 WebKit patch，而是一个从零开始、**没有图形渲染管线**的浏览器。它的 README 第一行就写着「为 AI agent 和自动化而生的无头浏览器」，第二行是「比 Chromium 轻 16 倍、快 9 倍」。

浏览器这个品类已经十几年没有真正的新玩家了。上一个试图从零写渲染引擎的团队，大多死在 Web 兼容性的长尾里。所以真正值得问的不是「它有多快」，而是：

**一个浏览器，凭什么可以不会画画？拆掉渲染之后，它还是浏览器吗？以及，省下来的那部分资源，到底能换成多少钱？**

这篇文章分五层拆：渲染税从哪里来、拆掉之后剩什么、协议兼容为什么是最难的护城河、WPT 数字背后的真实含义，以及一个 agent 基础设施团队真正该算的成本账。

---

## 一、渲染是给谁看的：Chrome 为人类设计的三层税

要理解 Lightpanda 的选择，得先承认一件反直觉的事：**headless Chrome 一直在做无用功，而且是被架构决定的、无法通过参数关掉的无用功。**

一个正常浏览器把 HTML 变成屏幕上的像素，要经过 style resolution（计算样式）、layout（布局）、paint（绘制）、composite（合成）四个阶段。Headless 模式下没有屏幕，但这条管线依然在跑——因为 DOM 的很多可观测行为依赖布局结果。`getBoundingClientRect()` 返回什么？元素可见性怎么判断？点击坐标在哪里？在 Chromium 的模型里，这些问题的答案都来自布局树。

于是第一层税是**计算税**：为了回答脚本提出的、看似与视觉无关的问题，浏览器必须先把页面「排版」出来。

第二层税更隐蔽，是**进程模型税**。Chrome 的多进程架构是为安全隔离和稳定性设计的：一个 tab 一个 renderer 进程，崩了不牵连别人。这在人类浏览场景里是极好的工程决策；在「一台机器上跑一千个并发抓取会话」的场景里，就变成了每个会话都要背一份进程开销、一份 V8 堆、一份 GPU 相关初始化。你可以在容器里跑 headless Chrome，但你没办法让它的进程模型为「一千个短生命周期会话」优化。

第三层税是**协议语义税**，也是最少被讨论的一层。Puppeteer 和 Playwright 通过 CDP（Chrome DevTools Protocol）驱动 Chrome。CDP 有 650 条命令、200 个类型，看起来能力极其完整——但它最初是为「一个人类开发者对着 DevTools 面板调试页面」设计的，不是为「一个脚本已经知道它想操作哪个 DOM 节点」设计的。

Lightpanda 的 CTO Pierre Tachoire 在《CDP Under the Hood》里举了一个非常锋利的例子：**点击一个元素**。在 DOM 层面，这是「找到节点、触发 click」一步；在 CDP 层面，因为没有 DOM 级的用户交互命令，客户端只能先查出元素的渲染坐标，把虚拟鼠标移过去，再派发鼠标事件。三次往返，而且依赖渲染。

更荒诞的是「取整个页面的 HTML」。按 CDP 的领域划分，正确做法是 `DOM.getDocument` + `DOM.getOuterHTML`。但 Tachoire 把 Puppeteer、Playwright、Chromedp、Rod 四个主流库的实现全扒了一遍，结论是：**没有一家用 DOM 域**。Puppeteer 和 Playwright 都改用 `Runtime.callFunctionOn` 注入 JS 直接读 `document.documentElement.outerHTML`；Chromedp 是 `DOM.performSearch` 加函数调用；Rod 干脆先取 `window` 再调 `DOM.getOuterHTML`。

这说明什么？说明 CDP 的「规范用法」在真实负载下是错的——DOM 域是为调试单个节点优化的，内存开销大、速度慢，不适合批量提取。每个自动化库都在绕开协议作者的设计，各自发明一套 workaround。**协议是标准的，用法是部落知识。**

这三层税叠加起来，就是 Lightpanda 切入的缝：如果 agent 只需要 DOM 和 JS 执行结果，那 style/layout/paint/composite 全是可以砍的；如果砍掉渲染，进程模型可以重写成单进程多 isolate；如果重写引擎，就可以在协议层直接提供「按节点点击」这种自动化原生语义，而不必模拟鼠标。

---

## 二、拆掉渲染之后，还剩什么

Lightpanda 的架构文档写得很直白：它保留「自动化真正用到的那部分浏览器」，具体是五层。

```
控制面   fetch / serve(CDP, WebDriver) / agent / mcp / HTTP API
   │
网络层   libcurl：主文档、子资源、cookie jar、robots.txt、WebSocket
   │
解析层   html5ever（Rust，Servo 项目）：HTML → DOM
   │
执行层   V8 15.5：isolate / context / promise / module
   │
Web API  Zig 原生实现：DOM、事件、fetch、Crypto、Observer、Storage
```

这套组合里最值得注意的不是「用了 V8」，而是**每一层都选了现成的、经过验证的组件，唯独胶水层自己写**。HTML 解析交给 Servo 的 html5ever，通过 C ABI 调用；JS 引擎直接用 V8，Zig 代码只是一层薄薄的 C++ API 封装；网络用 libcurl。真正从零实现的，是 DOM、Web API 和整个对象生命周期管理——也就是「浏览器语义」本身。

这是一个非常清醒的工程取舍。浏览器难的不是解析 HTML，也不是执行 JS，而是**让几万个 Web API 在正确的时机、以正确的顺序、带着正确的错误语义互相作用**。Lightpanda 没有重新发明 V8，它重新发明的是 V8 外面那圈东西。

### 单进程，但不是一个「大 Chrome」

运行时只有一个进程，进程内是严格的四层对象树：

- **App**：进程级服务，包括 arena pool（共享内存池）、网络层、遥测、SQLite 存储后端。
- **Browser**：包一个 V8 isolate。isolate 有线程亲和性，所以 browser 创建在哪个线程就只能在哪个线程用；它持有自己的 HTTP client，从 App 的池子里借 arena。
- **Session**：一个 browsing context group，拥有 cookie jar 和 localStorage/sessionStorage——这些状态要跨导航存活，所以挂在 session 而不是 page 上。
- **Page / Frame**：page 是 tab 级容器，frame 持有真正的 DOM（Document）和 Window。

这个划分解决了一个很实际的问题：**并发会话之间的状态隔离，不必靠进程**。一个 browser 一个 isolate，一个 session 一份 cookie/storage，多个 session 可以在同一个进程里跑，内存按 session 线性增长而不是按进程。

官方基准给出的数字是：940 个页面、25 个并发 tab，峰值内存 37MB + 每个额外 tab 3MB，总计 109MB；同样负载下 Obscura 是 201MB，Moli 是 230MB。而面对 headless Chrome 的单页抓取基准（100 页），Lightpanda 是 123MB 对 2GB，执行时间 5 秒对 46 秒。

注意这里的量级差异不是「优化了 20%」，而是**改变了扩容曲线的斜率**。Chrome 的成本模型大致是「每会话固定开销 + 页面开销」，固定开销很大；Lightpanda 把固定开销压到接近零，变成「每 tab 3MB」。当你的业务是每天抓 2000 万页时，前者需要一整个集群，后者可能只需要一个机架。

### 为什么是 Zig

这个问题值得单独说，因为它同时是 Lightpanda 最大的差异化和最大的风险。

选 Zig 的理由很充分：手动内存管理让 arena 分配成为可能（整个 browser 生命周期内批量分配、批量释放，避免每个 DOM 节点一次 malloc）；与 C/C++ 的互操作几乎零成本（直接调 V8 的 C++ API、libcurl 的 C API）；comptime 让 Web API 的绑定代码可以在编译期展开；没有 GC，延迟可预测。

但代价同样明确：Zig 还在 1.0 之前的语言演进期（Lightpanda 要求 Zig 0.17.0 这个特定版本），生态远不如 Rust；招人难；第三方库少，很多基础设施要自己写；调试工具链不成熟。这也是为什么它必须依赖 Rust 的 html5ever 和 C 的 libcurl——**语言选择决定了它不可能真正「自包含」**。

对比同赛道的 Obscura 和 Moli 都选了 Rust：Rust 有更强的生态和内存安全保证，但 arena 式的批量内存管理写起来更别扭。这是一个典型的「控制力 vs 生态」的取舍，没有标准答案，只有是否与产品定位匹配。Lightpanda 要的是极致的内存控制和启动速度，Zig 是合理选择；但如果它要做成一个通用平台，语言就会成为长期负担。

---

## 三、协议兼容：真正的护城河不在引擎，在「别人已经写好的脚本」

一个新浏览器最难的从来不是跑得快，而是**让现有代码不改就能跑**。

Lightpanda 的策略是「在你已经用的接口上等你」：CDP（Puppeteer、Playwright、Chromedp 直接连）、WebDriver Classic 和 BiDi（Selenium、Puppeteer）、MCP（任何支持 MCP 的 AI 应用）、HTTP API（一个 POST 拿 HTML/Markdown）。

迁移成本被压缩成一行：把 `browserWSEndpoint` 指向 `ws://127.0.0.1:9222`。这是一个极其聪明的增长设计——它把「换浏览器」从一个季度的迁移项目，变成一次配置修改。

但这里有个容易被忽略的陷阱：**CDP 兼容不等于行为兼容。**

前面说过，四个主流库取 HTML 的方式各不相同，而且都绕开了 CDP 的 DOM 域。这意味着 Lightpanda 要实现「Puppeteer 能跑」，就不能只实现 CDP 规范，而要实现 Puppeteer 那套具体的调用序列、它对返回值的假设、它对错误码的处理、它在 `Runtime.callFunctionOn` 里注入的那段 JS 所依赖的每一个 API。

Tachoire 的结论很到位：「实现 CDP 时，没有任何标准化的做事方式。每个自动化库对 CDP 的解释都不同。」这就是为什么 WPT 通过率不能完全代表「Playwright 脚本能不能跑」——WPT 测的是 Web 平台标准，不是 CDP 客户端的行为契约。

Lightpanda 的 1.0 公告里提到它现在是**唯一原生同时说 CDP、WebDriver 和 MCP** 的浏览器，不用中间驱动。这句话的含金量在于：它把「协议适配」当成了核心产品能力，而不是附属功能。对一个 agent 基础设施来说，这比多实现几个 CSS 属性重要得多。

顺带一提，1.0 还补上了 WebDriver，官方给的数字是「比 headless Chrome 快 4.4 倍、内存少 7 倍」——Selenium 生态里那些跑不动的老脚本，突然有了一个几乎零改造的加速路径。

---

## 四、174 万条 WPT 背后的真实含义

Lightpanda 最容易被误读的数字，是「174 万」。

2024 年 11 月 beta 发布时，它通过 2,645 条 WPT 子测试。到 2026 年 9 月，这个数字是 1,739,845。两年涨了 658 倍。任何看到这条曲线的人第一反应都应该是：**这条曲线里有多少是真实能力，有多少是测试套件的统计假象？**

官方自己给出了答案，而且给得相当诚实：

| 时间段 | 增量来源 | 通过数变化 |
|---|---|---|
| 2024.11 – 2026.03 | DOM、HTML、Fetch、URL、cookies、events | 2,645 → ~290,000 |
| 2026.04 | `encoding/` 套件开始通过（约 115 万条，多为字符映射表） | 数天内跳涨 |
| 2026.04 – 2026.09 | workers、Shadow DOM、IndexedDB、XPath、WebSocket、forms | 再增 ~340,000 |

也就是说，**174 万里有 115 万来自字符编码测试**。这部分当然是真实的兼容性——编码错了，中文、日文、emoji 页面就会乱码——但它对「能不能跑一个现代 Web 应用」的边际贡献，远小于数字给人的印象。

真正有意义的对比是横向的。2026 年 9 月 wpt.fyi 上 Chrome 通过 2,184,491 条，Firefox 通过 2,137,997 条。Lightpanda 大约是 Chrome 的 80%。而那 20% 的缺口，官方说得很清楚：**超过一半集中在 CSS、editing、SVG 三个套件**——恰好都是布局和绘制相关的。

这构成了一个逻辑闭环：不渲染 → CSS/布局/SVG 测试大量失败 → WPT 永远差 20% → 但这 20% 对 agent 的典型任务（读内容、填表单、点按钮、抓数据）影响有限。

问题是，「影响有限」不等于「没有影响」。真实世界里，大量站点用 CSS-in-JS 在运行时注入样式，用 IntersectionObserver 做懒加载，用 `getBoundingClientRect()` 判断元素是否可见再决定要不要渲染内容。Lightpanda 的文档承认：元素尺寸是「基于 CSS 和 HTML 属性的合理近似」，元素位置是「根据 DOM 深度和兄弟顺序模拟的，不是真实布局」。这意味着：

- 依赖真实布局做逻辑判断的页面，行为可能与 Chrome 不同；
- `Page.captureScreenshot` 返回的是占位图，不是真实渲染；
- Canvas / WebGL / 复杂视觉效果，基本不可用。

所以正确的理解是：**Lightpanda 不是「更快的 Chrome」，而是「另一个产品类别的浏览器」**。它覆盖的是「机器读取和操作页面」这个子集，而不是「像素级还原页面」这个全集。用 WPT 总分去比较它和 Chrome，就像用「单词量」比较一本字典和一本小说——数字可比，用途不可比。

### 同赛道横评：它不是唯一一个想明白这件事的

2026 年 10 月 19 日，Lightpanda 官方发了一篇横评，对比了四个「从零写的 AI 原生浏览器」：Lightpanda（Zig）、Obscura（Rust）、Moli（Rust，Lexmount）、Cloudflare Kitesurf（Rust → Wasm，闭源）。

| 指标 | Lightpanda | Obscura | Moli | Kitesurf |
|---|---|---|---|---|
| 总耗时（940 页 / 25 tab） | 4.5s | 11.5s | 17.4s | 未测 |
| CPU 时间 | 12s | 29s | 40s | 未测 |
| 峰值内存 | 109MB | 201MB | 230MB | 未测 |
| WPT 全量通过率 | 80% | 30% | 未跑完 | 69%（仅跑 30% 文件） |
| 协议 | CDP / WebDriver / MCP | CDP / MCP | CDP / WebDriver | CDP（经 Browser Run） |
| 开源协议 | AGPL-3.0 | Apache-2.0 | Apache-2.0 / MIT | 闭源 |
| 创建时间 | 2023.02 | 2026.04 | 2026.08 | 2026.05 |

这张表里最值得玩味的不是 Lightpanda 赢了，而是**竞争格局的形成速度**：Obscura 2026 年 4 月创建，Moli 8 月，Kitesurf 5 月。半年内冒出至少三个同方向项目，说明「为机器重写浏览器」已经从一家公司的执念，变成了一个被验证的需求类别。

同时也要看清横评的方法论问题：这是 Lightpanda 自己跑的 benchmark，负载是「爬一个 940 页的 demo 站点」，对爬虫友好，对交互密集型 agent 任务代表性有限。Moli 的 WPT 跑了 10 小时没跑完，被记为「无完整结果」，这在统计上对 Moli 不公平——但也确实反映了工程成熟度差距（Lightpanda 有 10,779 次 commit、3,148 个合并 PR、76 位贡献者，Obscura 是 1,533 / 552，Moli 是 2,051 / 1,222）。

另外一个容易被忽略的点是许可证。Lightpanda 用 AGPL-3.0，这意味着如果你修改它并以网络服务形式提供，可能需要开源你的修改。对内部基础设施团队通常不是问题，但对想基于它做商业产品的团队，这是一个必须在选型第一周就确认的法务问题。Obscura 和 Moli 的 Apache/MIT 在这一点上更友好——**性能领先不等于商业适配**。

---

## 五、把数字换成钱：一个 agent 团队的成本账

性能数字只有在能换算成账单时才有意义。我们来做一个粗略的建模。

假设一个中等规模的 agent 产品：每天执行 200 万次页面操作，峰值并发 500 个会话，每个会话平均访问 8 个页面。

**方案 A：headless Chrome 集群。**
Lightpanda 官方基准中，100 个页面峰值 2GB 内存。按每会话一个 Chrome 实例、每实例约 300–500MB（取决于页面复杂度）估算，500 并发需要 150–250GB 内存。考虑 CPU 和稳定性余量，实际需要约 20–30 台 16 核 / 64GB 的机器，或者等量的容器配额。

**方案 B：Lightpanda。**
940 页 / 25 tab 的峰值是 109MB，折算每 tab 约 4MB 增量，加上基础开销。500 并发会话，即使按每会话 20MB 的保守估计，也只需要 10GB 量级的内存；实际瓶颈更可能是网络出口和 CPU 的 JS 执行，而不是内存。

即使不考虑「9 倍速度」带来的吞吐提升，仅内存一项就是**一个数量级的差异**。云上 256GB 内存的实例月费大约在数千元到上万元区间，20 台机器的集群与 2 台机器的集群，差价是每月数十万级别的运营成本。对于一个每天抓取量在百万页以上的团队，这不是「优化」，这是商业模型能不能成立的问题。

这也解释了 Lightpanda 创始团队的动机：他们在上一家公司每天从 2000 万个页面抓数据，跑在 headless Chrome 集群上，「又贵又难维护」。他们不是想做浏览器，是想让自己的账单消失。

但成本账还有另一半，是容易被忽略的**隐性成本**：

1. **兼容性返工**。80% 的 WPT 意味着 20% 的站点可能出问题。如果你的业务是「抓任何用户给的 URL」，长尾站点的失败率会直接变成客服工单。需要一套 fallback 机制：Lightpanda 失败时切回 Chrome。
2. **协议行为差异**。现有 Playwright 脚本可能在边缘 case 上行为不同，尤其是依赖布局、截图、PDF、文件下载、复杂 iframe 的流程。
3. **运维成熟度**。Chrome 有十几年的生产实践、无数 StackOverflow 答案、成熟的容器镜像和监控方案。新引擎意味着新的崩溃模式、新的内存泄漏、新的「为什么这个页面卡住」。
4. **许可证与供应链**。AGPL 的法务评估、Zig 工具链的版本锁定、V8 升级的跟进节奏（Lightpanda 1.0 升到了 V8 15.5.35.13，这是需要持续投入的维护工作）。

所以真实的决策不是「Chrome vs Lightpanda」，而是**「哪些流量走轻引擎，哪些走重引擎」**。理性的架构是分层：80% 的结构化抓取、内容读取、表单填充走 Lightpanda；20% 需要真实渲染、截图比对、复杂前端交互的走 Chrome。这也正好对应 Lightpanda 文档里那句「需要真实像素时，请用完整浏览器」。

---

## 六、安全：当浏览器开始替 agent 访问「没人验证过的页面」

1.0 公告里，Lightpanda 把 CORS 默认开启放在了和 174 万 WPT 同等重要的位置。这个选择值得单独讨论，因为它揭示了一个被低估的事实：**agent 浏览器是一个全新的攻击面。**

传统浏览器的安全模型假设：用户会看到地址栏，用户会判断这个站点是否可信，用户的 cookie 里装着银行和邮箱。Agent 浏览器的假设完全不同：没有人在看地址栏，agent 会根据网页内容自主决定下一步动作，而它可能带着你的 API key、内网访问权限、云元数据端点的可达性。

在这个模型下，缺失 CORS 意味着什么？意味一个恶意页面上的 JS 可以 `fetch('http://169.254.169.254/latest/meta-data/...')` 或者调用内网服务，然后把结果读出来、塞进页面、被 agent 当作「网页内容」带走。这不是理论风险——SSRF 是云环境里最经典的提权路径之一。

Lightpanda 1.0 的安全清单，基本是照着 agent 的威胁模型逐条补的：

- **CORS 默认强制**：每个 `fetch()` 和 XHR 都走同源策略，跨域读响应需要服务端显式允许。官方说 `cors/` 套件通过 371/463（80%），剩余 92 条还在补。
- **资源加载改为 opt-in**（0.4.0）：iframe、worker、外部样式表默认不加载，需要 `--load-resources` 显式开启。这既是性能优化，也是攻击面收缩——页面里藏的第三方脚本默认不执行。
- **跨域重定向剥离 Authorization**（0.4.0）：给 A 站点设的凭证，不会跟着 302 跳到 B 站点。
- **Cookie 收紧**：页面 JS 不能改 HttpOnly；`SameSite=Strict` 在跨站导航时生效；`SameSite=Lax` 的例外只覆盖安全方法；`Set-Cookie` 的 Domain 是公共后缀时直接拒绝。
- **网络过滤**：`--block-cidrs` 和 `--block-private-networks`，把浏览器挡在私有子网和云元数据端点之外。
- **解析器与协议加固**：URL authority 的 CR/LF 注入、WebSocket 消息长度整数溢出，以及一批 use-after-free / double-free 修复。

这份清单的专业度，比很多「AI 浏览器」产品都高。它说明团队真的想过「如果这个浏览器跑在客户的 VPC 里，会被怎么打」。

但也要指出边界：CORS 只约束页面脚本的跨域读取，不约束 agent 自己的工具调用；`--block-private-networks` 是网络层黑名单，不是完整的 SSRF 防护；浏览器沙箱（进程隔离、seccomp）在单进程架构下天然弱于 Chrome 的多进程模型。**单进程换来的内存优势，代价是隔离性的下降。** 对多租户场景，这是一个需要认真评估的取舍——你可能需要在容器层做更强的隔离，而这又会吃掉一部分成本优势。

另一个现实约束是 AGPL-3.0。对内部工具无碍；如果你打算把 Lightpanda 嵌入 SaaS 并对公网提供服务，修改后的代码需要开源。这不是缺陷，是商业模式选择，但选型时必须提前确认。

---

## 七、PandaScript：比「快」更重要的一个设计

如果这篇文章只能留一个技术洞察，我会选这个，而不是 16 倍内存。

Lightpanda 有一个叫 `agent` 的模式：用自然语言描述任务，内置 agent 直接驱动浏览器——注意，**agent 跑在浏览器进程内**，不是通过 CDP 远程控制。官方文档的原话是「模型和引擎之间没有协议」。

更关键的是它的输出：agent 会话可以 `/save` 导出一个 **PandaScript**——一段原生 JavaScript，调用 Lightpanda 内置的浏览器原语。之后用 `lightpanda run session.js` 重放，**不需要 LLM，不需要 API key，完全确定性**。

这个设计解决的是 agent 工程里最痛的一个问题：**探索和执行被混在一起。**

今天绝大多数 browser agent 的部署方式是：每次任务都让 LLM 重新看页面、重新决策、重新点击。同一个流程跑一万次，就烧一万次 token，承担一万次模型不确定性，还要面对「今天模型心情不好，多点了两下」的随机性。而实际上，一个业务流程一旦被探索出来，99% 的执行都是重复的——登录、搜索、翻页、填表、导出，每一步都是确定的。

PandaScript 把这个过程拆成两个阶段：

1. **探索阶段**：LLM + 浏览器，允许试错，产出的是一个可读的脚本；
2. **执行阶段**：脚本 + 浏览器，零 token、零模型、可 review、可版本控制、可 diff。

这和「录制回放」的老思路形似而神不同。传统的 Selenium IDE 录制产生的是基于选择器的脆弱脚本；PandaScript 是真正的 JS，可以写循环、条件、错误处理，还可以调用 `page.extract({...})` 直接产出结构化数据。它更像是「把 agent 的探索结果编译成程序」。

这个思路可以推广到浏览器之外：**任何 agent 工作流，都应该有一个「探索 → 固化 → 重放」的路径。** 探索用最贵的模型，固化用最便宜的运行时，重放用确定性的执行器。大多数团队把 100% 的流量都花在探索上，这才是 agent 成本居高不下的真正原因——不是模型太贵，是每次都在重新发明同一段流程。

配合 MCP 的 HTTP 传输，这个模型还能扩展成多 agent 协作：每个 `Mcp-Session-Id` 对应一个独立的浏览会话（独立页面、cookie、内存），相同 id 的多个 agent 共享同一个浏览上下文。这让「一个 agent 登录，另一个 agent 接着操作」成为可能，而不需要把 cookie 导来导去。

---

## 八、它不适合谁：一份诚实的边界清单

技术文章最容易犯的错，是把「可行」写成「适用」。以下是 Lightpanda 明确不适用的场景：

- **需要真实截图的**：`Page.captureScreenshot` 返回占位图。视觉回归测试、UI 审核、多模态 agent 的「看图」能力，全部不成立。
- **需要真实布局的**：元素位置是模拟的，`getBoundingClientRect()` 不可信。依赖坐标点击、拖拽、可视化编辑器的流程会出问题。
- **Canvas / WebGL / 复杂 SVG**：没有渲染管线，这些内容无法正确呈现。
- **重 CSS 的现代前端**：CSS-in-JS、容器查询、复杂的响应式逻辑，可能触发布局相关 API 的差异行为。
- **需要浏览器级沙箱隔离的多租户场景**：单进程架构的隔离强度不如 Chrome 的多进程模型，需要额外的容器层补偿。
- **强合规环境**：AGPL-3.0 需要法务前置评估；闭源分发的商业产品基本可以排除。

反过来说，它最适合的场景也很清晰：

- 大规模内容抓取与索引（这是它的出身）；
- RAG 的数据采集层——把页面转成 Markdown 或结构化 JSON；
- agent 的「读网页 / 填表单 / 点按钮」工具层；
- CI 里的端到端测试（不需要截图的那些）；
- 需要成百上千并发会话、且成本敏感的任何 workload。

---

## 九、结论：浏览器正在分裂成两个物种

Lightpanda 1.0 的意义，不在于它比 Chrome 快多少倍。它的意义在于，它把一个隐含假设打破了：**「浏览器」必须是一个能画画的完整软件。**

过去二十年，浏览器公司在「更完整地实现 Web 平台」这条路上竞争，WPT 分数是军备竞赛的记分牌。但 AI agent 的出现，创造了一个新的需求类别：不需要像素，只需要语义；不需要完整，只需要够用；不需要单用户，只需要高并发。在这个类别里，Chrome 的完整性从优势变成了负担。

于是浏览器开始分裂成两个物种：

- **人类浏览器**：追求完整、追求像素、追求兼容，Chrome / Firefox / Safari 继续卷 WPT 的最后一个百分点；
- **机器浏览器**：追求吞吐、追求内存、追求确定性，Lightpanda / Obscura / Moli / Kitesurf 在另一个维度上竞争。

这两者不会互相取代，就像卡车不会取代轿车。但基础设施团队需要开始问一个过去不会问的问题：**我的这个 workload，真的需要一个能画画的浏览器吗？**

如果答案是否定的，那么省下来的不只是一个数量级的内存，还有一整套为「人」设计的架构税：进程模型、协议语义、渲染管线、以及每次都要重新看页面、重新决策的 token 账单。

Lightpanda 用 Zig 重写了一个浏览器，但它真正的产品洞察是另一句话：**Agent 不需要看见网页，它只需要理解网页。** 想明白这一点，16 倍内存和 9 倍速度只是自然结果。

---

**参考资料**

- Lightpanda 1.0 公告：https://lightpanda.io/blog/posts/lightpanda-1-0
- 架构总览：https://lightpanda.io/docs/core-concepts/architecture-overview
- AI 原生无头浏览器横评（2026-10-19）：https://lightpanda.io/blog/posts/benchmarking-ai-native-headless-browsers
- CDP Under the Hood：https://lightpanda.io/blog/posts/cdp-under-the-hood
- WPT 仪表盘：https://perf.lightpanda.io/wpt
- GitHub：https://github.com/lightpanda-io/browser
