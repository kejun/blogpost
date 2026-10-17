# 当 Agent 开始有自己的 App Store：Claude Code 官方插件目录与 Cursor 插件仓库深度拆解

> 2026 年 10 月 17 日。今天 GitHub Trending 上出现了两个非常罕见的身影：`anthropics/claude-plugins-official`（40,520 星）和 `cursor/plugins`（11,941 星）。一个是 Anthropic 官方维护的 Claude Code 插件目录，一个是 Cursor 官方维护的插件仓库，两者在同一个 24 小时内同时活跃（最后推送时间分别是 10-16 16:36 UTC 与 10-16 23:56 UTC）。
>
> 这不是巧合。当两个最主流的编码 Agent 厂商在同一个月把「插件市场」作为一级产品形态推上台面，意味着 Agent 的扩展机制正在从「零散脚本 + 提示词」走向「有清单、有版本、有市场、有审核的软件生态」。这篇文章不做新闻转述，而是把两个仓库的 `marketplace.json`、`plugin.json` 逐字段拆开，回答三个问题：插件到底是什么？两个格式差异在哪？供应链风险怎么办？

---

## 一、从"插件"这个词说起：Agent 扩展的三层演进

要理解今天的插件市场，必须先看清过去两年 Agent 扩展机制的演进路径。它大致经历了三层，而今天正好站在第三层的起点上。

**第一层：MCP（Model Context Protocol）。** 2024 年底 Anthropic 开源 MCP，解决的是「模型如何访问外部工具和数据」的问题。MCP Server 是一个独立进程，通过 stdio 或 HTTP 暴露 tools/resources/prompts。它的抽象层级是**能力**：你有了一个数据库 MCP，模型就能查数据库。但 MCP 不解决「怎么用得好」——它只提供接口，不提供流程。

**第二层：Skills。** 2025 年 Anthropic 提出 Agent Skills，本质是「把一段可复用的专家流程，连同它的脚本、模板、参考资料打包成一个目录，按需加载」。`SKILL.md` 带 frontmatter（name/description），主体是给模型看的操作说明。它的抽象层级是**方法论**：不是「你能用什么工具」，而是「遇到这类任务应该按什么步骤做」。技能解决了提示词工程的复用问题，但它仍然只是文件，没有分发机制。

**第三层：Plugin（插件）。** 这就是今天的主题。插件是一个**分发单元**：它把 MCP 服务器配置、Skills、Slash Commands、Subagents、Hooks 打包在一起，配上一份 `plugin.json` 清单和一个市场目录 `marketplace.json`，让用户可以一条命令安装、更新、卸载。

用一句话概括三者的关系：

> **MCP 是「手」，Skills 是「肌肉记忆」，Plugin 是「装着这些东西的盒子 + 货架 + 物流」。**

一旦有了「物流」，Agent 生态就第一次具备了类似 npm / App Store 的网络效应：作者写一次，所有人安装；平台方审核，用户信任。这解释了为什么两个仓库会同时爆发。

---

## 二、Anthropic 的答案：`claude-plugins-official` 拆解

先看数据。截至今天，这个仓库的元信息是：

- **星标**：40,520
- **创建时间**：2025-11-20（注意：这是仓库的创建时间，插件目录的爆发发生在 2026 年下半年的持续推送中）
- **最后推送**：2026-10-16 16:36 UTC
- **Topics**：`claude-code`、`mcp`、`skills`
- **描述**：Official, Anthropic-managed directory of high quality Claude Code Plugins.

### 2.1 仓库结构：内部插件 vs 外部插件

README 里的第一句就是结构说明，只有两行，但信息量很大：

```
/plugins          - Internal plugins developed and maintained by Anthropic
/external_plugins - Third-party plugins from partners and the community
```

这是典型的 **first-party / third-party 双轨制**。内部插件由 Anthropic 团队开发，例如：

- `code-review`、`pr-review-toolkit`：代码审查工作流
- `plugin-dev`、`example-plugin`：插件开发工具链与参考实现
- `mcp-server-dev`、`mcp-tunnels`：MCP 相关工具
- `clangd-lsp`、`gopls-lsp`、`jdtls-lsp`、`kotlin-lsp`、`lua-lsp`、`php-lsp`、`pyright-lsp`、`ruby-lsp`、`rust-analyzer-lsp`、`swift-lsp`、`typescript-lsp`：**一整套 LSP 语言服务器插件**
- `claude-security`、`security-guidance`：安全
- `code-modernization`、`feature-dev`、`frontend-design`
- `hookify`、`commit-commands`、`session-report`、`receipts`

外部插件则由合作伙伴提交，例如 `asana`、`context7`、`discord`、`firebase`、`github`、`gitlab`、`imessage`、`laravel-boost`、`linear`、`playwright`、`serena`、`telegram`、`terraform`。

值得注意的是那组 LSP 插件：`clangd-lsp`、`pyright-lsp`、`gopls-lsp`……这意味着 Anthropic 把「每种语言都要有一个能读懂代码的 LSP 后端」当作基础设施来对待。编码 Agent 的竞争，正在从「模型多聪明」下沉到「工具链多完整」。

### 2.2 全量统计：315 个插件说明什么

我把 `marketplace.json` 完整拉下来做了统计，这是文章里最有价值的一组数字：

| 指标 | 数值 |
|------|------|
| 插件总数 | **315** |
| 分类：development | 123 |
| 分类：productivity | 69 |
| 分类：database | 39 |
| 分类：monitoring | 22 |
| 分类：security | 18 |
| 分类：deployment | 9 |
| 分类：design | 8 |
| 分类：automation / learning | 各 3 |
| 分类：testing / math / location | 各 2 |
| 分类：migration | 1 |
| 无分类 | 14 |
| `renames` 迁移映射 | 10 条 |
| 来源类型：`url` | 164 |
| 来源类型：`git-subdir` | 98 |
| 来源类型：本地 `./plugins/...` | 53 |

两个观察：

**第一，265+ 个插件来自外部合作伙伴，而不是 Anthropic 自己。** 315 个插件中只有 53 个是本地（内部）来源，其余 262 个通过 `url` 或 `git-subdir` 指向外部 Git 仓库。这说明客户端厂商的克制策略：**Anthropic 只提供货架和规范，货由生态填。**

**第二，`database` 分类有 39 个插件，比 `security`（18）还多一倍。** 这对数据库行业从业者是个信号：数据仓库、查询引擎、迁移工具（`migration` 分类虽然只有 1 个）正在成为 Agent 插件的高地。Agent 要落进企业，最终绕不开数据。

### 2.3 一个插件长什么样

README 给出的标准结构：

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json      # Plugin metadata (required)
├── .mcp.json            # MCP server configuration (optional)
├── commands/            # Slash commands (optional)
├── agents/              # Agent definitions (optional)
├── skills/              # Skill definitions (optional)
└── README.md            # Documentation
```

要点：`plugin.json` 是**唯一必需**的文件，其余组件都是可选的。这是「渐进式复杂度」的设计——一个最简单的插件可以只有一个清单文件加一个 `commands/` 目录。

### 2.4 三个被低估的设计细节

**细节一：marketplace.json 里带 `renames` 迁移表。**

```json
"renames": {
  "adlc": "agentforce-adlc",
  "airwallex": "airwallex-agentos",
  "convex-backend": "convex",
  "vals": "valtown",
  "wordpress.com": "build-with-wordpress",
  "qodo-skills": "qodo",
  "atlassian-forge-skills": "forge-skills",
  "azure-skills": "azure",
  "sonarqube-agent-plugins": "sonarqube",
  "data-agent-kit-starter-pack": "data-agent-kit"
}
```

README 里对此有明确解释：插件的 `name` 是**不可变 slug**。一旦发布，用户就按这个名字装上了，改名会让用户的安装直接报 `plugin-not-found`。想改显示名就用 `displayName`；万不得已要改 slug，必须在 `renames` 表里登记，加载器会在用户下次同步时透明地把旧 slug 重写为新 slug。

这是**包管理器的必修课**——npm 的 deprecated、PyPI 的 yanked、Maven 的 relocation，都是同一个问题的不同答案。Anthropic 学得很快：在一个仅供内部使用、发布不到一年的市场里，已经有 10 条重命名记录，说明命名治理从一开始就被当成真问题对待。列表里 `adlc → agentforce-adlc`、`atlassian-forge-skills → forge-skills` 这种「去厂商前缀化 / 加厂商前缀化」的反复，正是生态早期的典型震荡。

**细节二：`strict: false` 的 skill-bundle 插件。**

README 里有一段相对冷门的说明：当插件的源仓库只有 `SKILL.md` 文件、没有 `.claude-plugin/plugin.json` 清单时，市场条目可以直接声明 skills：

```json
{
  "name": "example-bundle",
  "source": {
    "source": "git-subdir",
    "url": "https://github.com/example-org/sdk.git",
    "path": "packages/agent-skills",
    "ref": "main",
    "sha": "<commit sha>"
  },
  "strict": false,
  "skills": ["./skill-a", "./skill-b", "./skill-c"],
  "homepage": "https://github.com/example-org/sdk"
}
```

这解决了一个很现实的摩擦：很多厂商早已把自己的 Agent Skills 放进 SDK 仓库（比如 `packages/agent-skills`），但没有动力为 Claude Code 单独做一个插件外壳。`strict: false` + `git-subdir` + 显式 `skills` 数组，允许**从任意仓库的任意子目录，暴露任意深度的 skill 子集**，每个 skill 注册为 `<plugin-name>:<skill-name>`。

这是一条极强的生态引力条款：**零改造即可接入。** 对比之下，MCP 生态里厂商还需要写一个 server 进程；而 skill-bundle 模式让「我已经有 SKILL.md」的厂商只加一个 JSON 条目就能上架。

**细节三：`sha` 锁定与 trust 警告。**

市场条目里的来源几乎都带 `sha` 字段（`git-subdir` 和 `url` 类型都有），例如：

```json
"source": {
  "source": "git-subdir",
  "url": "https://github.com/42Crunch-AI/claude-plugins.git",
  "path": "plugins/api-security-testing",
  "ref": "v1.5.5",
  "sha": "faf5305385de8afed9468904e8639be737aff39e"
}
```

`ref` + `sha` 双锁定：`ref` 是人类可读的版本标签（`v1.5.5`），`sha` 是不可篡改的内容定位符。这是**供应链安全的基本盘**——即使上游仓库重写标签（Git 允许 force-push 标签，这是著名的攻击手法），市场仍然能安装到经过审核的那一次提交。

尽管这样，README 顶部仍然挂着一句罕见的、加粗的免责声明：

> **⚠️ Important:** Make sure you trust a plugin before installing, updating, or using it. Anthropic does not control what MCP servers, files, or other software are included in plugins and cannot verify that they will work as intended or that they won't change.

「Anthropic 不控制插件里包含哪些 MCP server、文件或其他软件，也无法验证它们是否按预期工作、是否会变化。」——这是一家头部厂商对插件生态安全模型的诚实表态：**市场审核 ≠ 沙箱隔离**。插件一旦安装，它带的 MCP server 就是本机进程，带的 hook 就是在你的项目里执行的代码。

---

## 三、Cursor 的答案：`cursor/plugins` 拆解

Cursor 的官方仓库数据：

- **星标**：11,941
- **创建时间**：2026-01-23
- **最后推送**：2026-10-16 23:56 UTC（就在写稿前几小时）
- **描述**：Cursor plugin specification and official plugins
- **README 首句**：Official Cursor plugins for popular developer tools, frameworks, and SaaS products.

### 3.1 结构：每个插件一个独立目录 + 双清单

README 明确指出："Each plugin is a standalone directory at the repository root with its own `.cursor-plugin/plugin.json` manifest."——每个插件在仓库根下独立成目录，各自拥有 `.cursor-plugin/plugin.json`。仓库整体则有一份根级 `.cursor-plugin/marketplace.json`：

```json
{
  "name": "cursor-plugins",
  "owner": { "name": "Cursor", "email": "plugins@cursor.com" },
  "metadata": {
    "description": "Official Cursor plugin marketplace: developer tools, framework rules, MCP integrations, and agent skills"
  },
  "plugins": [
    { "name": "teaching", "source": "teaching", "description": "..." },
    { "name": "continual-learning", "source": "continual-learning", "description": "..." }
  ]
}
```

注意 Cursor 这里的 `source` 是一个**相对路径字符串**（`"thermos"`），而不是对象。这比 Anthropic 的 `{"source": "git-subdir", "url": ..., "path": ..., "ref": ..., "sha": ...}` 简洁得多——因为 Cursor 的官方仓库是**单体市场（monorepo marketplace）**：所有官方插件都在同一个仓库里，指路只需要一个相对目录名。而 Anthropic 的目录是**聚合市场（aggregator marketplace）**：绝大多数插件住在别人的仓库里，所以必须描述「去哪个 repo 的哪个子目录、取哪个 ref/sha」。

这两个模型对应两种截然不同的运营选择：

| 维度 | Anthropic（聚合型） | Cursor（单体型） |
|------|---------------------|------------------|
| 插件归属 | 大部分在第三方仓库 | 全部在本仓库 |
| 上架门槛 | 填提交表单 + 审核 | 提 PR |
| 版本控制 | `ref` + `sha` 双锁定 | 随仓库提交 |
| 生态规模速度 | 快（零改造接入） | 慢（需要 PR 合入） |
| 质量一致性 | 参差，依赖审核 | 高度一致 |
| 安全边界 | 需要 sha pin | 天然受仓库权限约束 |

这不是谁对谁错，而是「广度优先」与「一致性优先」的分野。Cursor 用 106 个插件换来了整齐划一；Anthropic 用 315 个插件换来了覆盖面积。

### 3.2 `plugin.json` 的字段：比 Anthropic 更"发布化"

看 `thermos` 插件（Cursor 自研的"热核级"分支审查插件）的清单：

```json
{
  "name": "thermos",
  "displayName": "Thermos",
  "version": "1.0.0",
  "description": "Thermo-nuclear branch review: deep correctness and security audits plus harsh code-quality rubrics, parallel subagents, thermos orchestration, and optional take-the-wheel and FSD merge-ready flows.",
  "author": { "name": "Cursor", "email": "plugins@cursor.com" },
  "homepage": "https://github.com/cursor/plugins",
  "repository": "https://github.com/cursor/plugins",
  "license": "MIT",
  "logo": "assets/logo.png",
  "keywords": ["thermos", "thermo-nuclear", "code-review", "deep-review", "code-quality", "security-review", "subagents"],
  "category": "developer-tools",
  "tags": ["review", "quality", "shipping", "automation"],
  "skills": "./skills/",
  "agents": "./agents/"
}
```

把它和 Anthropic 的字段对照，能看到一个明显的差异：**Cursor 的清单更像一个应用商店条目**。它有 `displayName`（显示名）、`version`（独立语义化版本）、`logo`（图标）、`keywords` + `tags`（两套检索维度）、`license`、`repository`。这是一个「要被人类在 UI 里浏览、比较、安装」的清单。

Anthropic 的清单则更偏「机器解析 + 人类扫一眼」：`name` / `description` / `author` / `category` / `source` / `homepage`。它没有 `version` 字段——因为版本信息被 `ref` + `sha` 取代了。

一个细节值得注意：Cursor 的 `skills` 和 `agents` 字段是**路径字符串**（`"./skills/"`、`"./agents/"`），表示目录；而 Anthropic 在 `strict: false` 模式下用的是**路径数组**（`["./skill-a", "./skill-b"]`），表示精确挑选的子集。前者是「整目录暴露」，后者是「按需挑选」。

### 3.3 组件类型：Cursor 多一个 `rules`，Anthropic 多一个 `commands`

Cursor 插件的组件构成（从 `create-plugin` 插件的 README 归纳）：

- **Skills**：`SKILL.md` + frontmatter
- **Rules**：`.mdc` 文件（Cursor 特有，注入到模型上下文的持久规则）
- **Agents**：子 Agent 定义（`agents/`）
- **Commands**：斜杠命令
- **MCP**：`mcp.json` 里的 MCP server 定义

Anthropic 插件的组件构成（从 README 归纳）：

- **MCP server 配置**：`.mcp.json`
- **Slash commands**：`commands/`
- **Agent definitions**：`agents/`
- **Skill definitions**：`skills/`
- **Hooks**：从 `hookify` 等插件名称可推断

两者几乎完全重合，差异只有一处：**Cursor 有 `rules`（`.mdc`），Anthropic 有 `hooks`。** `rules` 是「常驻上下文注入」，`hooks` 是「生命周期事件回调」。这反映了两个产品的哲学：Cursor 更强调让模型"一直在正确的上下文里"，Claude Code 更强调"在正确的时机做正确的事"。

### 3.4 106 个插件的分类地图

Cursor 的 106 个插件可以分成几个清晰的层次：

**A. Cursor 自研的 Agent 工作流**（最有研究价值的一类）：

- `thermos`：热核级分支审查——深度安全/正确性审计 + 严苛代码质量评分 + 并行子 Agent 编排 + 可选的 merge-ready PR 流程
- `orchestrate`：把大任务扇出到并行云 Agent，配 planner / worker / verifier 与结构化交接
- `ralph-loop`：基于 "Ralph Wiggum 技巧"的迭代自指 AI 循环
- `cursor-team-kit`：CI、代码审查、发布、本地自动化、验证的内部团队工作流
- `agent-compatibility`：CLI 驱动的仓库兼容性扫描
- `advisor`：在重大决策前、卡住时、宣布完成前咨询更强的模型
- `pstack`（作者 Lauren Tan）/ `dyl-stack`（作者 Dylan Gattey）：外部知名工程师的个人 Agent 工作流

**B. 组件/界面类**：`pr-review-canvas`（把 PR diff 渲染成按重要度分组的审查画布）、`docs-canvas`、`create-plugin`（脚手架 + 预提交质量检查）

**C. 三方 SaaS 集成**（60+ 个，占了半壁江山）：从 Google 全家桶（Gmail / Drive / Calendar / Docs / Sheets / Slides / BigQuery）到 Salesforce、HubSpot、Intercom、Zoom、Todoist、Calendly、QuickBooks、Xero、Shopify、Stripe 系的 Square、以及一长串金融数据（S&P Global、Interactive Brokers、Robinhood、Coinbase、eToro、Webull、Finary）。

**D. 语音与 SDK**：`grok-voice`（把 Grok 实时语音接进应用）、`cursor-sdk`（用 TypeScript SDK 构建自动化）

这里的信号非常清楚：**SaaS 厂商正在把「被 Agent 调用」当作和「被人类点击」同等重要的入口。** 60+ 个三方集成不是 Cursor 求来的，是厂商主动来提 PR 的——因为一旦用户的 Agent 能直接操作你的产品，你就进入了 AI 工作流；反之则被绕过。

一个有趣的细节：`cli-for-agent` 这个插件教的是「如何设计 Agent 能可靠运行的 CLI」——flags、带示例的 help、管道、错误、幂等性、dry-run。它把我们在别处讨论过的"为 Agent 构建 CLI 工具"直接变成了一个可安装的插件。

---

## 四、收敛：两个市场其实在说同一件事

把两份清单放在一起逐字段比对，会看到一个比"竞争"更有意思的事实——**它们在同一周里收敛到了一套几乎相同的抽象**。

**共同点一：都叫 `plugin.json` + `marketplace.json` 双清单。** 一个是 `.claude-plugin/`，一个是 `.cursor-plugin/`，目录名不同，职责完全相同：前者描述"这个插件是什么"，后者描述"这个市场里有哪些插件"。

**共同点二：都用 `source` 表达"插件住哪儿"。** 都支持本地路径、Git URL、子目录三种形态。Anthropic 把它显式建模成 `{source: "git-subdir" | "url" | local}`，Cursor 用字符串简写——但语义集合完全一致。

**共同点三：都把 Skills 当作一等组件。** 两个清单都有 `skills` 字段，都指向包含 `SKILL.md` 的目录。**Skills 已经从 Anthropic 的内部格式，变成了跨厂商的通用扩展格式。**

**共同点四：命名层级一模一样：`name`（机器标识）/ `displayName`（人类显示）/ `description` / `author` / `category` / `homepage`。** 这基本就是 npm `package.json` 的骨架。Agent 插件市场在重新发明包管理，而且是自觉地、按已被验证的范式在发明。

**共同点五：都把 MCP 当作既有事实。** 两个仓库的 topics / 描述里都直接出现 `mcp`；MCP server 配置是插件可选项之一，而非插件本身。MCP 已经沉淀为底座。

差异则集中在四个真实的设计取舍上：

| 取舍点 | Anthropic | Cursor |
|--------|-----------|--------|
| 市场拓扑 | 聚合器（去中心化源） | 单体（集中式源） |
| 版本表达 | `ref` + `sha`，无 `version` 字段 | `version` 语义化字段 |
| 命名治理 | 不可变 slug + `renames` 迁移表 | 未在 README 中强调 |
| 组件特色 | `hooks`（事件回调） | `rules`（`.mdc` 上下文注入） |
| 最低接入成本 | 一个 JSON 条目（`strict:false`） | 一个 PR |

四个取舍里，最值得开发者注意的是**版本表达的差异**。

**Anthropic 选择"内容寻址"**：没有 `version` 字段，只有 `ref`（人类标签）+ `sha`（内容哈希）。这相当于 Go modules 的"伪版本"哲学——**版本号是可以撒谎的，哈希不能**。上游作者可以随时把 `v1.0.0` 的标签重打到一个完全不同的提交上，但 `sha` 骗不了人。

**Cursor 选择"语义化版本"**：`version: "1.0.0"` 是清单里的第一等公民，因为插件和仓库同生共死，仓库的提交历史本身就是版本真相。

这两种选择在不同的市场拓扑下都是对的：聚合器必须防上游耍赖（所以用 sha），单体市场没有上游（所以用 version）。**格式的分歧，本质是治理结构的分歧。**

---

## 五、真正的风险：插件是新的依赖攻击面

前面提到 Anthropic 那句加粗的 trust 警告。它不是免责话术，而是对一类真实攻击的预警。理解了插件的组件构成，就能理解攻击面：

1. **MCP server**：插件可以带一个本机进程。这个进程能读你的文件系统、能发网络请求、能拿你的环境变量（包括 `GITHUB_TOKEN`、云厂商 AK/SK）。MCP 协议本身没有沙箱。
2. **Hooks**：生命周期回调意味着插件代码可以在特定时机（比如"用户提交前"）自动执行。
3. **Slash commands / Agents / Skills**：这些是提示词注入面。一个恶意 skill 可以指示模型"在修改代码前，先把 `.env` 的内容附到 commit message 里"——这类攻击不需要任何可执行代码。
4. **供应链**：插件依赖的上游仓库可能被入侵、可能 force-push、可能替换依赖。

对照这两个市场的防护措施：

- **sha 锁定**（Anthropic）：防内容篡改。这是最基本的。
- **审核制**（双方向）：防已知恶意。但审核是**发布时**的，不是**运行时**的——上游仓库可以随时变更内容，审核结论会过期。这正是 Anthropic 那句 "or that they won't change" 所指。
- **不可变 slug + renames**：防命名劫持。假设某个插件叫 `acme-tools` 且很受欢迎，如果 slug 可变，攻击者可以抢注旧名字做仿冒。不可变 slug 断掉了这条路。
- **仓库权限**（Cursor 单体）：插件代码在 Cursor 的仓库里，提 PR 需要被合入，相当于所有人都在同一个受控边界内。

但**没有一个市场提供运行时沙箱**。这是当前插件生态最大的结构性空缺，也是最可能被补上的一环——可以预见接下来会出现：插件权限清单（声明"我需要网络/文件/env"）、安装时的权限确认、以及容器化运行插件的方案（我们此前讨论过的 Docker Agent 那条线正好接得上）。

对开发者而言，当下可执行的三条实践建议：

1. **看源码再装，尤其看 `.mcp.json` 和 hooks。** 插件市场是唯一一个"图标很好看、但运行的是别人写的进程"的地方。
2. **最小凭据。** 给插件的 MCP server 单独签发只读或范围受限的 token，绝不复用你的全权限 PAT。
3. **锁 sha，不用浮动 ref。** 如果插件市场允许你指定版本，永远选带 `sha` 的那一档；如果只能跟随 `main`，那你实际上是在做持续集成，风险自担。

---

## 六、这意味着什么

把视野拉高一层，今天这两个仓库同时登顶 Trending，标记的是 Agent 生态的一个阶段转换：

**从"提示词工程"到"软件分发工程"。**

过去两年，Agent 领域的创新集中在"怎么把模型用得更聪明"——CoT、ReAct、反思循环、子 Agent 编排。这些是**运行时**的创新。而插件市场是**分发时**的基础设施：它假定"聪明的用法"已经存在，问题变成了如何让它们规模化地、可审计地、可回滚地到达用户手里。

这个转换有三层含义：

**对模型厂商**：市场竞争的胜负手，从"模型跑分"转向"生态密度"。315 个 vs 106 个插件的差距，比几个 MMLU 百分点的差距更让用户难以迁移。Anthropic 用 `strict: false` + `git-subdir` 把接入成本压到接近零，是在打一场典型的两边市场闪电战。

**对 SaaS 厂商**：必须回答一个问题——"我的产品怎么被 Agent 调用？"这份答案现在有了标准格式：写一个 `plugin.json`，声明你的 skills / commands / MCP，然后提交。60+ 个集成已经在 Cursor 那边给出了示范。不做的代价是被 Agent 工作流绕过。

**对开发者（尤其数据库从业者）**：`database` 分类在 Anthropic 目录里排到第三（39 个），这不是偶然。数据是 Agent 价值的最终落点：再聪明的 Agent，最终要写回一个数据库、查一次数仓、跑一次迁移。围绕查询引擎、schema 管理、迁移工具的插件化，是一个确定性的机会窗口。

而对我们这些**同时用多个 Agent 的人**，一个现实的问题已经浮现：同一个 Skill 要不要为 Claude Code 和 Cursor 各写一份？从两份清单的高度重合来看，理性答案是否定的——**写一份 `SKILL.md`，然后为两个市场各写一份薄薄的清单文件。** 格式已经收敛到这个程度了。

---

## 七、结语

今天这两个仓库放在一起看，最好的注脚是 Anthropic 那段 `strict: false` 的文档。它允许你把一个已经存在的 `SKILL.md` 目录，零改造地变成市场里的一个可安装条目。

这个条款的技术含量不高，但它的姿态很明确：**客户端厂商争夺的不是"插件在谁的格式里"，而是"插件在谁的货架上"。** 格式趋同、治理分化——一个用 sha 和 renames 管住去中心化的上游，一个用单体仓库换来整齐划一——这就是 2026 年 10 月 Agent 插件生态的真实图景。

上一次看到这一幕，是 2008 年的手机应用商店，和 2010 年的 npm。今天的区别只有一个：商店里卖的不是给人用的软件，而是**给 Agent 用的能力**。而这次，货架搭建只用了不到一年。

---

### 参考数据来源

- GitHub Trending，2026-10-17（`anthropics/claude-plugins-official` 40,520★；`cursor/plugins` 11,941★）
- `anthropics/claude-plugins-official` README 与 `.claude-plugin/marketplace.json`（315 个插件，10 条 renames，来源分布 url 164 / git-subdir 98 / local 53）
- `cursor/plugins` README、`.cursor-plugin/marketplace.json`（106 个插件）与 `thermos/.cursor-plugin/plugin.json`、`create-plugin/README.md`
- Hacker News 首页（2026-10-17）："How the Claude Code team does code review"（200 pts）、"Llama.cpp on a jailbroken PS5"（158 pts）

*本文数据于 2026-10-17 08:00 (Asia/Shanghai) 通过 GitHub API 与 raw 文件抓取，所有统计均为脚本实测，非估算。*
