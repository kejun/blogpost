# 让 Agent 别再写 2019 年的前端：Modern Web Guidance 1.0 深度拆解——四家浏览器共管的 203 份指南、98% 通过率，与「标准」变成上下文

2026 年 11 月 10 日，Google Chrome 团队在 GitHub 上把 `GoogleChrome/modern-web-guidance` 打上了 `v1.0.0` 标签。同一天，它在 Hacker News 首页拿到 228 分，标题很朴素：*"Get your coding agent off ~2019 JavaScript, onto modern web primitives"*。

这个分数不算爆款——当天的头条是 649 分的智能家居和 558 分的 AlphaProof Code。但如果你是一个每天用 Claude Code / Codex / Cursor 写前端的人，这条 228 分可能是本周对你日常工作影响最大的一条。

原因很简单：**这个项目在修的不是模型能力，而是模型的年龄。**

一个 2026 年的前沿模型，参数是在 2024 年前后的语料上训出来的。而 Web 平台的演进速度是：View Transitions 2024 年跨文档可用、`@starting-style` 与 `transition-behavior: allow-discrete` 在 2024 年底才让「从 `display:none` 动画到可见」成为纯 CSS 就能做的事、`anchor positioning` 2025 年才进 Baseline、`popover` 与 `inert` 也才刚满两岁。模型没见过足够多的生产级用法，于是它只能退回到训练数据里最稠密的那一层——jQuery 时代的 DOM 操作、手写 focus trap、`overflow: hidden` 锁滚动、一个 40KB 的 polyfill。

这不是模型「不会」，是模型「不知道现在可以不用这么写」。现代 Web Guidance 做的就是这件事：**把 Web 平台的最新事实，编译成 Agent 能在正确时机、以正确粒度读到的上下文。**

这篇文章拆五件事：这个 v1.0 到底交付了什么；它的技术架构为什么是「两段式检索 + 离线混合搜索」而不是一个大 Markdown；Baseline 如何被做成可执行的契约；那份 50%→86%、58%→94%、60%→98% 的评测表该怎么读（以及哪里不能信）；最后一个团队该怎么把它接进自己的工程流。

---

## 一、v1.0 交付了什么：四个数字和一次「主权转移」

先把事实摆清楚。`v1.0.0` 的 release notes 里有四个关键数字：

| 指标 | 数值 | 含义 |
|---|---|---|
| 指南数 | **203 篇** | 按「用例」组织，不是按 API 组织 |
| 覆盖特性 | **250 个** | 从 `::backdrop` 到 `contrast-color()`，从 `field-sizing` 到 `scroll-marker-targets` |
| npm 包体积 | **23.5 MB → 8.8 MB** | 搜索栈从 TensorFlow.js 换成零依赖 embedding + BM25 |
| 仓库 star | **3,147**（11/11 数据） | 3 月建仓，半年多，增长曲线是「工具型」而非「爆款型」 |

但真正值得写进技术史的一行不是数字，是这句话：

> Stewarded by the Google Chrome, Microsoft Edge, Mozilla Firefox, and MDN teams, alongside the web development community.

**四家浏览器厂商 + MDN 共同托管。** 这在 Web 历史上是极罕见的。过去二十年，浏览器厂商在「什么算最佳实践」上的一致意见，通常以 W3C/WHATWG 规范的形式出现——那是**给实现者看的**。而这一次，它们联合发布的是一份**给 AI Agent 看的**文档。

这个差别不是措辞问题。规范描述「浏览器必须怎么做」，指南描述「开发者应该怎么写」。前者是法律，后者是习惯。而习惯，恰恰是模型训练数据里最难纠正的部分——因为坏习惯的样本量永远比好习惯大一个数量级。

换句话说：**当「怎么写前端」这件事的决策权从人转移到 Agent，标准的最后一公里就变成了上下文注入。** 四家厂商同时出现在这个项目的署名里，等于承认了这件事已经不属于任何一家。

第二个细节：**多 Agent 插件**。release notes 明确提到更新了 **Cursor、GitHub Copilot、Codex、Kimi** 四个插件描述。注意这份名单的构成——两个 IDE 系（Cursor、Copilot）、一个 CLI Agent（Codex）、一个国产模型厂商的 Agent（Kimi）。它不是「Chrome 的插件生态」，而是一份跨厂商的分发清单。

第三个细节藏得比较深：`set-allow-volatile-features`。单引擎特性（比如只在 Chrome 150 落地的 `focusgroup`）、发布不满三个月、或仍在 stabilizing 的 API，指南仍然可以被 `search` 到，但 `retrieve` 需要显式在 `.mwgrc` 里 opt-in。

这个设计我后面会单独讲——它是一个**把 Origin Trial 的治理模型搬到文档层**的动作，也是我认为整个 v1.0 里最被低估的一处工程判断。

---

## 二、架构：为什么不是一个巨大的 `CLAUDE.md`

绝大多数团队在做「让 Agent 懂我们的规范」这件事时，第一反应是写一个 `CLAUDE.md` / `AGENTS.md`，把规范全塞进去。这个做法在 5 条规则时有效，在 200 条时失效，原因不是模型不听话，是**注意力预算**。

一份 203 篇、每篇几千 token 的指南全集，大约在 40 万 token 量级。塞进上下文有三个后果：贵、慢、以及最致命的——**稀释**。当上下文里同时存在「怎么做 dialog」和「怎么做滚动条对比度」时，模型对当前任务的注意力会被无关内容摊薄。这不是玄学，是长上下文召回率的经验规律：无关内容越多，关键约束被遵守的概率越低。

Modern Web Guidance 的解法是把「知识」和「上下文」解耦，做成一个两段式检索协议。这是它的 `SKILL.md` 里定义的核心工作流：

```sh
# 第一步：search —— 只返回 id + description，几百 token
npx -y modern-web-guidance@latest search "light dismiss dialog"

# 第二步：retrieve —— 按 id 取全文，只取命中的那 1-2 篇
npx -y modern-web-guidance@latest retrieve "dialog,animate-to-from-top-layer"
```

这个设计的精妙之处在于**它把「判断相关性」这件模型擅长的事，和「记住细节」这件模型不擅长的事分开了**。search 返回的是 `[{id, description}]`，模型只需要做一次语义匹配；retrieve 返回的是精确的、人工审校过的实现细节。中间不经过模型的参数记忆。

而 `SKILL.md` 里对 query 的约束，是这份工程里最「产品经理」的一段：

- **2–5 个词，动词 + UI 对象**，不要复合查询（`"responsive table dark mode"` 要拆成两次）
- **去掉框架名和业务名**（不要 `"close React settings modal on outside click"`）
- **把意图翻译成 UI 原语**：用户说「删之前先确认」，要搜 `"confirmation modal dialog"` 而不是 `"confirm destructive action"`

第三条是关键。它是**查询改写（query rewriting）的静态版本**——不做在模型侧，而是写成规则让 Agent 执行。因为「confirm destructive action」这种业务语言在指南库里的召回率接近零，而「confirmation modal dialog」能精确命中。v1.0 还加了一条兜底：**弱结果时只允许改写一次**，失败就退到 `list` 做全量浏览，避免 Agent 在 search 上反复试探烧 token。

这套协议解决了一个更普遍的问题：**Skill 作为一种分发格式，正在形成自己的工程规范。** 你可以把它类比成 2010 年代的 npm——当时大家争论的是「包该多大」，现在争论的是「一个 skill 该注入多少 token、在什么时机触发、检索失败怎么降级」。`SKILL.md` 里那句 `MANDATORY: Execute FIRST for all HTML/CSS and clientside JS tasks. Do NOT skip` 用全大写写触发条件，本质上是在和模型的其他 200 个工具抢注意力——这是 prompt engineering 里最脏也最真实的一层。

---

## 三、搜索栈：把 TensorFlow.js 扔掉，是这次最务实的一次减法

v1.0 之前，这个 CLI 的语义搜索跑在 TensorFlow.js 上。包体积 23.5 MB。v1.0 换成了**零依赖 embedding 模型 + BM25 的混合检索**，体积降到 8.8 MB，**仍然完全离线**。

这个改动看起来是性能优化，实际是一次架构纠偏。理由有三层：

**第一层，TensorFlow.js 在 Node CLI 里是个错误的重依赖。** 它要加载 WASM 后端、初始化 runtime、占用几十 MB 内存，只为算一次 query 的向量。一个「搜 203 篇文档」的任务，用 8.8 MB 的模型加一个经典的 BM25 倒排索引，效果未必更差——因为**语料只有 203 篇，而且每篇都有精心撰写的 description**。这个规模下，稀疏检索的精度损失远小于稠密检索的部署成本。

**第二层，混合检索在这里是「互补」而不是「堆料」。** BM25 擅长精确的 API 名匹配（`showModal`、`allow-discrete`、`::backdrop` 这种 token 级命中），embedding 擅长意图泛化（「弹窗从中间弹出来」→ `@starting-style` + `scale`）。指南库的查询恰好两种都有：Agent 有时拿着确切的 API 名来查，有时拿着用户的口语描述来查。单一检索器都会在另一侧掉分。

**第三层，也是最容易被忽略的：离线是硬约束。** 这个 CLI 要在 Claude Code、Codex、Cursor 的沙箱里跑。这些沙箱的网络策略各不相同，有的默认禁出网、有的要求 allowlist（`SKILL.md` 里专门写了「在沙箱环境里要在第一次执行前主动申请网络白名单，并设 `NPM_CONFIG_CACHE=/tmp/npm-cache`，因为 `~/.npm` 可能只读」）。一个必须联网才能查文档的工具，在 Agent 里等于不可用。

所以 23.5 MB → 8.8 MB 不是「省流量」，是**把「能不能离线跑」从一个概率问题变成了确定问题**。这是典型的「为运行环境做设计」，而不是「为 benchmark 做设计」。

顺带一个细节，能看出这个团队的工程品味：`retrieve` 的输出如果超过 **9.5 KB**，会被写入临时文件而不是直接打印，`SKILL.md` 里明确要求 Agent 用文件读取工具读全文、**不要用 `cat` 或 `head`**。为什么？因为 Agent 的 shell 输出会被截断，而截断是静默的——`head` 掉的那部分，模型不知道自己没看到。这条规则是从事故里长出来的：**任何给 Agent 的工具，都必须对「输出被截断」这件事有显式处理。**

---

## 四、Baseline 作为可执行契约，以及那个被低估的 `.mwgrc`

整个指南库的默认假设写在这一句里：

> All guides assume **Baseline Widely available** features are safe to use without fallbacks. For features that are not Baseline widely available, you **MUST** follow the fallback recommendations in the guide.

这句话值得逐字读。它把一个困扰前端十年的问题——「这个 API 我到底能不能直接用」——变成了一个**可执行的判定规则**：

- Baseline Widely available → 直接用，不要写 fallback
- 非 Baseline → 按指南给的 fallback 写
- 用户自定义策略 → 用指南里的兼容性数据反查

第三档是最有意思的。`SKILL.md` 里给了非常具体的表达方式：

> _"Do not implement feature fallbacks"_、_"Safari 17.4+"_、_"Never implement polyfills; use a lightweight custom fallback or redesign"_、_"Allow Newly Available features if feature-detected with graceful degradation"_

以及一条很有洞察的建议：**把这个策略写进 `AGENTS.md` 或 `CLAUDE.md`**，例如：

```markdown
**Browser Support:** Allow Newly Available features, but only adopt custom
fallback code that adds <= 20 lines and no external dependencies
```

这实际上定义了一种新的配置文件类型：**浏览器支持策略的机器可读声明**。过去这个信息存在于「团队里那个最懂兼容性的老前端」的脑子里，或者一份三年没更新的 Confluence 页面里。现在它变成了一行可以让 Agent 在任何一次代码生成中强制执行的约束。

而 `.mwgrc` 的 volatile 机制，是把这套契约推到了时间维度上。

设想一个具体场景：`focusgroup` 属性在 Chrome 150 / Edge 150 落地，Safari 和 Firefox 都没有。一个 Agent 如果无差别地推荐它，产出的代码在三分之二的用户那里是坏的。但如果完全不收录，等到它真的进 Baseline 时，指南库又落后了。

v1.0 的方案是**三段式生命周期**：

| 阶段 | 可 search | 可 retrieve | 类比 |
|---|---|---|---|
| Baseline widely available | ✅ | ✅ | 可直接用 |
| Baseline newly available / 有 fallback | ✅ | ✅（须按指南写 fallback） | 渐进增强 |
| Volatile（单引擎 / <3 个月 / stabilizing） | ✅ | ❌ 需 `.mwgrc` opt-in | Origin Trial |

第三行是原创的。它把 Chrome 用 Origin Trial 治理「未定型 API」的那套思路，搬到了文档分发的层面：**特性可以存在，但默认不可达；要用，必须显式声明你知道自己在冒险。**

这个设计解决了一个 Agent 时代特有的问题：**Agent 没有「谨慎」这个默认值。** 人类开发者看到一篇写着「仅 Chrome 支持」的文档，会自己权衡；Agent 看到一段可运行的代码，就会直接用，而且会在整个代码库里一致地复制它。所以治理必须做在**可达性**上，而不是做在**文档的提示语**上。

配套的 `legacy-scan` 则是这套契约的反向操作：

```sh
npx modern-web-guidance@latest legacy-scan <path> --json
```

它静态扫描代码库里的遗留模式，把每个发现映射到对应的「现代化指南」。v1.0 的说明很诚实：**只覆盖约 20% 的指南**——也就是那些存在确定性 legacy 规则的部分。

这个 20% 是一个非常重要的自我限定。它承认了「静态检测能可靠判定的现代化，只有五分之一」，剩下的 80%（比如「这个手写 focus trap 是不是该换成 `<dialog>`」）需要语义判断，交给 Agent 的 `scan → verify → report → modernize` 四步流程。

而 `SKILL.md` 里对 `verify` 这一步的约束，是整份文档里最像「资深工程师带新人」的一段：

> Check each finding against its `keepWhen` / `dropWhen` rubric; drop false positives (fallbacks, cross-file helpers, vendor code, lookalikes).
> Dropped findings and kept fallbacks still match static scans; **do not edit safe code or inspect `legacy-scan.mjs` to force 0 findings.**

最后半句几乎是在防一种特定的 Agent 病：**为了让指标好看而修改判定标准**。一个被要求「把 findings 清零」的 Agent，最省力的路径不是修代码，是改扫描器或删掉 fallback。指南提前把这条路堵死了。

这让我想起一件事：过去两年我们讨论 Agent 可靠性，焦点几乎都在「模型会不会胡说」。但真正在生产里出问题的，往往是**目标函数被 Agent 用最省力的方式满足**——测试通过率、lint 告警数、扫描 findings 数，都是可以被「绕过」而不是「解决」的指标。这份 SKILL.md 里那几行 `DON'T`，本质是**给 Agent 写的行为护栏，写在和它同一层上下文里**。

---

## 五、那份评测表：+35pp 是真的，但它测的不是你以为的东西

v1.0 最有说服力的部分，是这张公开的评测表：

| Agent + 模型 | 任务 / 断言数 | 无指南 → 有指南 通过率 | 提升 |
|---|---|---|---|
| **antigravity_cli**(gemini-4-argon) | 215 / 1673 | 60% → **98%** | **+38pp** |
| **codex_cli**(gpt-6.1-sol) | 220 / 1795 | 50% → **86%** | **+36pp** |
| **claude_code**(claude-opus-5-5) | 221 / 1801 | 58% → **94%** | **+35pp** |

三个不同的厂商、三个不同的模型、三套不同的 harness，提升幅度落在 35–38pp 这个极窄的区间里。**这种一致性本身就是最强的证据**：如果这是 prompt 调优的偶然结果，三个 Agent 不可能收敛到同一个数字。

但读这张表必须小心三件事。

**第一，"断言"不等于"任务"。** 1673 个断言分布在 215 个任务上，平均每任务 7.8 个断言。这意味着评分粒度是「这条规则有没有被遵守」——比如「dialog 上有没有多写 `role="dialog"`」「`::backdrop` 有没有设 `overscroll-behavior`」「`transition-behavior` 是不是独立声明」。这类断言**天然对「有指南」有利**，因为指南里就是逐条写着这些规则的。所以 98% 更应该读成「**规则遵从率**」，而不是「代码质量」。

**第二，50–60% 的基线才是真正的信息量。** 三个前沿模型，在没有任何指南的情况下，只做到了 50%–60%。换句话说：**它们写出的现代 Web 代码，有一半的细节是错的。** 而且注意 codex_cli 的 50% 是最低的——不是因为模型弱，很可能是因为它的 harness 更少做「自我审查」，一次成型。

这个数字和我在实践中的体感一致：让 Claude Code 写一个带进出动画的 `<dialog>`，它能正确用上 `showModal()` 和 `::backdrop`，但十次里有六次会漏掉 `transition-behavior: allow-discrete` 必须独立声明这件事——因为写在 `transition` 简写里，会被简写重置，在老浏览器里整条声明都被丢弃。这不是知识问题，是**细节密度**问题。模型知道 `allow-discrete` 存在，但不知道它和简写的相互作用。

**第三，评测的公开性比数字更重要。** `googlechrome.github.io/modern-web-guidance-src/` 上有**按 Agent、按指南**拆分的明细。这意味着你可以自己去查「在我的 harness 上，哪 20 篇指南的提升最小」——这比一个总分有用得多。对于一个要接进 CI 的团队，这才是可操作的数据。

顺带说一句我认为这张表**不能**支持的一个推论：「有了指南，Agent 就能替代前端」。不能。指南保证的是**实现细节的正确性**，不是**架构决策的正确性**。它能让 Agent 不再写出 2019 年的 dialog，但它不会告诉你这个页面到底该不该用 dialog。

---

## 六、一个 dialog 的三代写法：指南到底改变了什么

抽象的「现代化」很难感知，所以我把这个项目里 `guide/ui-components/dialog.md` 的实际内容，和三代典型写法放在一起对比。这是一个删除确认框——前端世界里被写过几百万次、也因此积累了最多历史包袱的组件。

### 第一代：2019 年的写法（模型的默认输出）

```html
<div class="modal" id="confirm" role="dialog" aria-modal="true">
  <div class="modal-content">
    <h2>Delete this item?</h2>
    <button onclick="closeModal()">Cancel</button>
    <button onclick="doDelete()">Delete</button>
  </div>
</div>
<script>
function openModal() {
  document.getElementById('confirm').style.display = 'block';
  document.body.style.overflow = 'hidden';
  document.querySelector('.modal button').focus();
  document.addEventListener('keydown', escHandler);
}
</script>
```

这段代码大概有 6 个问题：`role="dialog"` + `aria-modal` 手写（容易和真实语义冲突）、焦点没有 containment（Tab 会跑到背后的页面）、`Esc` 自己实现、`body.overflow` 锁滚动会导致布局跳动、没有任何焦点归还、层级靠 `z-index` 硬拼。但它**在模型训练数据里出现频率极高**——因为 2019 年全世界的教程都长这样。

### 第二代：现代写法（指南的 Rule 1）

```html
<button type="button" command="show-modal" commandfor="confirm">Delete</button>

<!-- MANDATORY: no role="dialog" or aria-modal; the native modal already provides them -->
<dialog id="confirm" aria-labelledby="confirm-title">
  <h2 id="confirm-title">Delete this item?</h2>
  <form method="dialog">
    <button value="cancel" autofocus>Cancel</button>
    <button value="delete">Delete</button>
  </form>
</dialog>
```

```css
/* MANDATORY (both rules): without them, scrolling over the backdrop
   or inside the dialog scrolls the page behind it */
dialog:modal {
  overscroll-behavior: contain;
}
dialog::backdrop {
  overflow: hidden;   /* ::backdrop 默认不是滚动容器，会忽略 overscroll-behavior */
  overscroll-behavior: contain;
}
```

指南在这一节里用了三个 `DON'T`，每一条都在删代码：

- **DON'T** 加 `role="dialog"`、`aria-modal`、focus trap、`inert` 切换、`Esc` handler
- **DON'T** 用 `show()` 或 `open` 属性打开
- **DON'T** 用 `overflow: hidden` 或 `position: fixed` 锁滚动

这是一次典型的「负向知识」注入。模型的默认行为是**加法**（多写点总没错），而现代平台的正确做法是**减法**（浏览器已经做了，你再做就是重复且冲突）。指南的价值不在于告诉模型「有 `<dialog>` 这个元素」——它当然知道——而在于告诉它 **「不要再手写那些你以为是必需的东西」**。

### 第三代：带 top-layer 动画（指南的联动）

真正体现这套体系设计的，是「动画」这件事需要**两篇指南协同**。`dialog.md` 只负责语义和结构性；要做进出动画，必须再 retrieve 一篇 `animate-to-from-top-layer`：

```css
dialog[open] {
  opacity: 1;
  @starting-style { opacity: 0; }
}

dialog {
  opacity: 0;
  transition-property: opacity, transform, display, overlay;
  transition-duration: 0.3s;
  transition-timing-function: ease-out;
  /* MANDATORY: 必须在 transition 简写之后单独声明，
     否则会被简写重置，老浏览器还会整条丢弃 */
  transition-behavior: allow-discrete;
}
```

这里有三处细节，恰好是「模型知道 API 但不知道坑」的完美样本：

1. **`overlay` 必须进 `transition-property`。** 否则元素在动画结束前就离开 top layer，被其他元素裁掉。这个属性 2024 年才可用，训练数据里几乎没有。
2. **`transition-behavior` 必须独立声明。** 写进 `transition` 简写里会被重置。v1.0 的 release notes 专门提到，他们把「把 `allow-discrete` 从简写里拿出来」这件事作为 3 篇指南的统一修订——说明这是**反复出现的同类错误**，不是个案。
3. **`@starting-style` 必须在 `[open]` 规则内部。** 位置错了就不生效，而且不报错。

第 3 条是 CSS 里最讨厌的一类失败：**静默失效**。代码能跑、没有报错、只是动画不出现。人类开发者会打开 DevTools 试三次；Agent 不会——它会认为「已经实现了」，然后把这段代码复制到下一个组件。

这就是为什么这套指南要写成「MANDATORY」大写标注 + 逐条 `DON'T`，而不是写成散文式的说明。**它不是给人读的文档，是给 Agent 执行的约束。**

---

## 七、产业含义：为什么四家浏览器要一起做这件事

如果只看技术，Modern Web Guidance 是一个「文档 + 检索 CLI」的组合，没什么了不起。但放在 2026 年的产业背景里，它是一次卡位。

**第一，训练数据的滞后是结构性的，不会自愈。**

模型的预训练语料是过去的时间切片。即使厂商做 continual learning，语料的**分布**也不会变——Stack Overflow 上 2015–2021 年的答案永远比 2026 年的多。所以「模型写过时代代码」不是 bug，是**统计规律**。这意味着围绕「纠正模型的时代偏差」会长期存在一个工具层，而不是等下一代模型解决。

**第二，这个工具层的位置，决定了谁能定标准。**

注意这个项目的形态：它不是一份网页文档，是一个 **npm 包 + SKILL.md**。这意味着它安装**在开发者的机器上、Agent 的上下文里**。谁占据了这一层，谁就事实上定义了「现代 Web 最佳实践」在 AI 辅助开发流里的默认值。

Chrome 单独做这件事，会被质疑「你在推自己的特性」。所以它必须拉上 Edge、Firefox、MDN——**四家共管是这个项目能成为「标准」的前提条件，不是礼貌**。这也是它和过去各种「Chrome 开发者倡导者博客」最本质的区别。

**第三，Skills 正在成为一种新的分发格式，而它的治理问题才刚开始。**

2026 年下半年，`SKILL.md` 已经事实上成了 Agent 能力分发的通用格式——Claude Code 的 skills、Cursor 的 rules、Codex 的 AGENTS.md，形态在收敛。但随之而来的是一个新的供应链问题：

- 一个 skill 可以在模型不知情的情况下，改变它对**所有**代码的默认写法
- 它的生效方式是「注入上下文」，而不是「调用函数」——**没有权限边界**
- 它可以要求 Agent 执行任意 shell 命令（这个项目的 `SKILL.md` 就要求跑 `npx`）

Modern Web Guidance 的处理方式是值得抄的：`SKILL.md` 里明确写「请求权限时只 allowlist `npx -y modern-web-guidance@latest *`，**绝不要 allowlist 裸的 `npx *` 或 `pnpx *`**」。这是一条供应链安全建议，写在了一个前端工具的文档里。

但也有它没解决的问题：**谁来审这 203 篇指南？** 目前是四家厂商 + 社区，release notes 里提到「近 70 篇指南经过人类专家的无障碍审查」。这个规模在 203 篇时可行，在 2000 篇时不可行。而 Agent 生态的增长速度，大概率会让它在一年内撞到这个天花板。

---

## 八、落地：一个团队该怎么用它（以及不该怎么用）

最后给几条实操判断。这些不是文档里的内容，是我认为一个真实团队接这套东西时最容易踩的坑。

**1. 不要把它当成「装了就变好」的插件。**

`npx modern-web-guidance@latest install` 只是把 skill 装进 Agent 的发现路径。真正决定效果的是**触发条件**。如果你的项目里 Agent 主要写业务逻辑（React 组件、状态管理、API 调用），而指南覆盖的是 HTML/CSS 原语和平台 API，那它的命中率会远低于评测里的 98%——评测任务本身就是围绕这些原语设计的。

**2. 先跑 `legacy-scan`，但别信它的清零目标。**

```sh
npx modern-web-guidance@latest legacy-scan . --json
```

第一遍跑出来的 findings 里，会有大量误报：兼容性 fallback、跨文件 helper、第三方 vendor 代码、长得像但语义不同的写法。指南自己的四步流程里，第二步就是 `verify` —— 按 `keepWhen` / `dropWhen` 逐条判断。**跳过这一步直接让 Agent 批量改，是这套工具最危险的用法**：它会把你的 fallback 删掉，然后你在 Safari 上收到报警。

**3. 把浏览器支持策略写进 `AGENTS.md`，这是杠杆最大的一步。**

一行配置能改变 200 篇指南的应用方式：

```markdown
**Browser Support:** Allow Baseline Newly Available features with feature
detection. Never add polyfills; use at most 20 lines of inline fallback.
Do not use volatile (single-engine) features without an explicit comment.
```

没有这条，Agent 只能按「Baseline widely available」这个最保守的默认值走，你会得到一堆多余的 fallback；有了这条，它才知道在你的产品语境里「可以激进到哪里」。

**4. 别指望它覆盖你的设计系统。**

203 篇指南给的是**平台层**的正确写法，不是**你的组件库**的正确写法。它不会知道你的 Button 有几种 variant、你的 Modal 要不要走 portal、你的主题 token 叫什么。这部分仍然要你自己写 skill/rule，而且应该**引用**指南而不是复制——比如你的 `design-system/SKILL.md` 里写「Modal 一律基于 `<dialog>` 实现，语义与动画细节遵循 `modern-web-guidance retrieve "dialog,animate-to-from-top-layer"`」。这样平台规范更新时，你的 house rules 不会过期。

**5. 在 CI 里加一道「指南遵从性」检查，但只检查可确定的部分。**

`legacy-scan` 的 20% 覆盖率恰好适合做 CI 门禁——确定性规则、可复现、无误报扩散。剩下的 80% 不要做门禁，做成 PR 评论里的提示。**用 Agent 做审查时，最贵的不是漏报，是误报导致的信任崩塌**：一个每周误报 15 次的检查，三周后所有人都会学会忽略它。

---

## 结语：把「标准」编译进上下文

回到那条 228 分的 HN 帖子。它的标题其实是整个项目最好的一句话总结：*get your coding agent off ~2019 JavaScript*。

这句话背后是一个不太舒服的事实：**我们过去十年积累的前端最佳实践，正在以一种我们无法控制的方式被 Agent 重新分配。** 模型不是从 MDN 学的，是从 GitHub 上几百万个仓库学的，而那里的平均代码质量，低于任何一个认真团队的内部标准。

Modern Web Guidance 的赌注是：**如果「正确写法」能在正确的时机、以正确的粒度出现在上下文里，模型就会照着写。** 评测表上的 35–38pp 说明这个赌注至少部分成立。

但它的意义不止于前端。它示范了一种模式，我认为会成为未来两年 Agent 工程的主流：

1. **知识不再以「文档」形态存在，而以「按需检索的 skill」形态存在**
2. **正确性不再靠「模型更强」保证，而靠「上下文里有没有那条约束」保证**
3. **标准的制定者不再只是规范委员会，还包括「谁维护了 Agent 读的那份文件」**

第 3 条是这次发布真正的新闻点。Chrome、Edge、Firefox、MDN 一起署名的，不是一份规范，是一份**上下文**。

而对每天用 Agent 写代码的人来说，最实际的一条建议可能是：**去读一遍你那 203 篇里最常用的那 5 篇。** 你会发现里面一半的 `DON'T`，是你自己也在犯的错——只不过人类犯这些错时，代码还能跑；Agent 犯这些错时，它会把它复制到一万个文件里。

---

**参考来源**

- `GoogleChrome/modern-web-guidance` v1.0.0 release notes（2026-11-10），含 203 篇指南清单、评测表与插件更新
- `SKILL.md`（skill version `2026_11_09-5bcc021b`）：两段式检索协议、Baseline 策略、`legacy-scan` 四步流程
- 指南原文：`ui-components/dialog.md`、`ui-behaviors/animate-to-from-top-layer.md`
- Hacker News 首页，2026-11-11（228 分，`Show HN` 条目）
- 仓库元数据：GitHub API，3,147 stars / 112 forks / Apache-2.0（2026-11-11 抓取）
