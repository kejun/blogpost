# 一个 plugin.json，装下所有 Agent 客户端：Agent Plugins 1.0 拆解，与它故意没写的权限模型

11 月 24 日，Cursor 的官方插件仓库 [`cursor/plugins`](https://github.com/cursor/plugins) 又合并了一批提交。这个仓库今年 1 月 23 日创建，到写这篇文章时是 **19,194 星**，最新一次提交是 11 月 24 日 15:17（太平洋时间）的 `41e4009`。仓库里躺着 **159 个 `plugin.json` 清单、175 个 `SKILL.md`、16 个 agent 定义、142 个第三方插件目录**，整个仓库 31 MB。

单看这些数字，它像是一个"官方插件合集"。但真正值得写的是它旁边那份文档：Cursor 现在把插件格式分成了两种——自己的 `.cursor-plugin/plugin.json`，和一份**厂商中立的开放标准** [Agent Plugins](https://agent-plugins.org)。后者 1.0.0 已发布，1.1.0 还在草案阶段，技术指导委员会（TSC）的初始核心维护者来自 **Amazon、Cursor、Microsoft、OpenAI、Vercel**。

这件事的意义不在于"又多了一个标准"。过去两年，Agent 生态里每个客户端都在自己发明插件格式：Claude Code 一套、Cursor 一套、各家 IDE 又一套。插件里装的其实是同样的东西——一段 `SKILL.md`、一份 `mcp.json`、几个脚本——但作者要为每个客户端重新排目录、改清单、写适配层。Agent Plugins 想解决的就是这个**重复打包税**。

而它最值得研究的地方，恰恰是它**明确不做什么**。规范正文用 RFC 2119 的措辞把包结构、清单校验、组件发现、MCP 配置、故障隔离写得极其细；然后在 `FUTURE_CONSIDERATIONS.md` 里老老实实列了一串"v1.0.0 不定义"：权限与审批、来源验证、密钥处理、企业管控、审计事件。这不是疏漏，是分层设计——但这条分界线划在哪里，决定了今天装一个插件到底意味着把什么交给了谁。

这篇文章分五部分：先讲清插件为什么突然成为标准件；再逐条拆 Agent Plugins 1.0 的规范设计；然后用 Cursor 仓库里的真实插件做案例；接着重点分析它留下的安全缺口与企业侧的补丁；最后给出我对接下来 12 个月的判断。

## 一、从"一个 Skill"到"一个插件包"：打包税是怎么产生的

2025 年下半年到 2026 年，Agent 的能力扩展经历了一次明显的形态变化。

**第一阶段是 prompt / rules。** 你把编码规范写进 `AGENTS.md` 或 `.cursorrules`，模型读它就照做。问题是这些文本没有边界、没有触发条件、没有版本，越堆越长，最后变成一份没人维护的 3000 行"公司宪法"。

**第二阶段是 Skill。** 一个目录、一个 `SKILL.md`，frontmatter 里写 `name` 和 `description`，正文写流程，旁边放 `scripts/` 和 `references/`。模型先看描述判断"这活该不该用这个技能"，再按需读正文——这是一次典型的**渐进披露（progressive disclosure）**：常驻上下文只花几十个 token，真正需要时才展开。Agent Skills 规范（agentskills.io）把这件事标准化之后，Skill 成了社区里流通性最好的资产形态。

**第三阶段就是现在：插件。** 一个真实的工程能力很少只由一个 Skill 构成。以代码审查为例，你需要：一条"什么算严重问题"的规则、一个负责找 bug 的 subagent、一个负责评代码质量的 subagent、一个把两者结果去重汇总的编排 Skill、可能还有几个跑测试的脚本。这五样东西在磁盘上是五种不同格式，在客户端里是五个不同的注册点。

于是每个客户端都长出了自己的打包方式：

| 客户端 | 清单位置 | 能装什么 |
| --- | --- | --- |
| Cursor（私有格式） | `.cursor-plugin/plugin.json` | rules、skills、agents、commands、MCP、hooks、variables |
| Claude Code（生态惯例） | `.claude-plugin/marketplace.json` + 各插件自有清单 | skills、commands、agents、MCP、hooks |
| Agent Plugins（开放标准） | 根目录 `plugin.json` | **仅 skills + MCP**，1.1.0 草案才加 hooks |

这就是"打包税"的来源：**同一个能力，三种目录布局，三份元数据，三次审核**。对个人作者，这意味着维护成本；对厂商（比如 Gmail、Salesforce 这种在 `third_party/` 里出现的集成方），这意味着每进一个客户端就要重做一次发布流程。

Agent Plugins 的定位非常克制：它只标准化**能跨客户端复用的那一层**，剩下的留给客户端自己。这句话在规范里写得明明白白：

> Agent Plugins defines a small interoperability floor for the parts that can be portable across clients. Shared components can use one predictable structure, while distribution, installation, permissions, user experience, and client-specific capabilities remain under each client's control.

翻译过来：**我只管"包长什么样"，不管"包怎么发、装完能干什么、谁批准它干"。** 后面我们会看到，这句话既是这份规范最聪明的地方，也是它最大的风险敞口。

## 二、规范拆解：一个封闭清单，和五级故障边界

先把 1.0.0 的核心设计说清楚。它其实只有四个关键决策，但每个决策都做得很"工程"。

### 2.1 清单是封闭的：只允许 10 个字段

`plugin.json` 的顶层 schema 是 **closed** 的，合法字段只有：`$schema`、`name`、`version`、`description`、`author`、`homepage`、`repository`、`license`、`keywords`、`extensions`。多一个字段会怎样？规范的处理很有意思：

- **未知顶层字段**：报告并忽略，插件继续加载；
- **其他任何 schema 违规**：致命，客户端必须拒绝整个插件，不得发现或执行任何组件。

为什么要区分？因为"未知字段"通常意味着插件是为更新版本的规范写的，或者作者带了点私货；直接拒绝会破坏向前兼容。而"类型错了、必填项缺失"属于包本身损坏，继续加载只会制造更难排查的运行时错误。

`extensions` 字段是唯一的扩展口，键必须是**反向域名**（如 `com.example.client`），对应磁盘上一个同名顶层目录。客户端只应用自己认识的命名空间，其余一律忽略。这是一套很老派但很稳的做法——和 CSS 厂商前缀、Java 包名、Apple 的 UTI 是同一个思路：**用命名空间把"标准"和"厂商私有"物理隔开**。

### 2.2 版本协商靠 `$schema`，而且加载时不许联网

`$schema` 是必填的，1.0.0 的值必须精确等于 `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`。客户端拿这个标识去**本地**选择校验规则，规范明确禁止在加载插件时去网上取 schema。

这一条看起来是细节，实际是安全设计。想象一下：如果客户端在安装插件时实时拉取远端 schema，那么控制那个 URL 的人就能改变"什么算合法插件"——这是典型的供应链投毒入口。要求本地内置 + 精确匹配，等于把"解释权"钉死在客户端发布的那一刻。

同时它也给版本升级留了口子：客户端可以把多个规范版本映射到同一套实现，只要它显式声明这些版本兼容。不认识的版本？拒绝，并提示"版本不支持"。不猜测、不降级解析。

### 2.3 路径必须留在插件根目录内

这是我认为整份规范里最容易被低估的一段。它规定：

1. 插件是一个**单一文件系统根**下的目录；
2. 规范定义为"插件相对路径"的配置值，**必须以 `./` 开头**，解析后必须仍在插件根内；
3. 符号链接、junction 可以指向根内目标，但**指向根外的必须拒绝**；
4. 命令参数、环境变量值属于"不透明字符串"，客户端不得把它们当路径来做包含性检查。

举个规范里的例子：

```json
{ "command": "./bin/server", "cwd": "./data" }   // 合法
{ "command": "../bin/server", "cwd": "data" }    // 非法：逃逸 + 不是 ./ 开头
```

为什么这条重要？因为插件包是从 marketplace 下载的**第三方代码**。如果 `mcp.json` 里能写 `../../../../etc/passwd` 或者指向 `~/.ssh` 的符号链接，那么"安装一个插件"就等价于"给远端一个任意文件读取原语"。第 4 条尤其细：它明确说**不要把命令行参数当路径去检查**——否则任何带 `/` 的参数（比如 URL、正则、JSON）都会被误判成路径逃逸，客户端会误伤正常插件。这种"知道什么时候不该检查"的克制，是规范成熟度的标志。

### 2.4 五级故障边界：坏一个组件，不要炸整个包

规范要求客户端按"最窄的适用边界"处理故障，而不是一刀切拒绝：

| 失败点 | 处理方式 |
| --- | --- |
| `plugin.json` 不在根内 / 清单致命违规 | 拒绝整个插件 |
| 固定组件目录（`skills/`、`mcp.json`）不在根内 | 该**组件类型**整体无效 |
| 某个 `SKILL.md` 逃逸根目录 | 跳过**该 Skill** |
| 某个 MCP server 的 `command`/`cwd` 逃逸 | 该 **server 条目**无效 |
| 其他包内路径逃逸 | 拒绝访问该路径 |

这套分级不是洁癖。插件是多人协作、长期演进的产物：一个第三方集成方更新了 `mcp.json` 但写错了相对路径，不应该导致用户已经装好的 20 个 Skill 全部失效。**故障隔离的粒度，直接决定了生态能不能长大**——这一点在浏览器扩展、VS Code 扩展的历史上都验证过。

### 2.5 客户端必须做的，和规范不管的

规范第 11 章给了 conformance 要求，核心是：能从目录加载、能校验 `plugin.json`、至少支持 skills 或 MCP 之一、按 `$schema` 选规则、不联网取 schema、执行上述故障边界。

而它**明确不管**的清单同样清楚：安装源与注册表、启用/更新/缓存体验、权限提示与沙箱、Skill 如何呈现给用户或模型、客户端扩展的内部行为。

这就是"分层"的真正含义：**可移植的是包，不可移植的是治理**。理解了这条线，才能理解后面所有的取舍。

## 三、仓库实证：一个仓库，两套清单，N 个客户端

理论说完，看真实仓库。`cursor/plugins` 的顶层有 21 个目录，其中 `third_party/` 下 142 个集成方；根目录同时存在 `.cursor-plugin/` 和 `.claude-plugin/` 两个清单目录。后者是 Claude Code 生态的 marketplace 约定，前者是 Cursor 私有格式。

这不是"历史遗留"。打开两个文件能看到明显的分工：

```jsonc
// .cursor-plugin/marketplace.json
{ "name": "cursor-plugins",
  "owner": { "name": "Cursor", "email": "plugins@cursor.com" },
  "metadata": { "description": "Official Cursor plugin marketplace: developer tools, framework rules, MCP integrations, and agent skills" },
  "plugins": [ { "name": "teaching", "source": "teaching", "description": "..." }, ... ] }
```

`.claude-plugin/marketplace.json` 用的是一套精简得多的字段：`name`、`owner`、`plugins[].name/source/description`。两者的 plugin 条目几乎一一对应，`source` 指向同一个目录。这说明作者在维护**一份资产、多份发布元数据**——正是 Agent Plugins 想消灭的那种重复，只不过这里用脚本和目录约定把成本压到了最低。

### 3.1 159 个清单里藏着三种插件形态

按组件构成分类，仓库里的插件大致是三类，这个分类对理解"插件到底是什么"很有帮助：

**第一类：纯连接器（Connector）。** 只有一个 `mcp.json`，指向一个远端 MCP 服务。比如 Gmail：

```json
{ "mcpServers": { "gmail": { "type": "http", "url": "https://gmailmcp.googleapis.com/mcp/v1" } } }
```

清单里 `mcpServers: "./mcp.json"`，除此之外没有 skills、没有 rules。这类插件的价值在于**分发凭证与端点**：用户不用手写 MCP 配置，装完授权即可。它的技术含量低，但商业意义大——每一个 SaaS 厂商都希望自己出现在 Agent 的工具列表里。

**第二类：能力包（Capability Pack）。** 一堆 `SKILL.md` + agents，解决一类工程任务。`cursor-team-kit` 就是典型：`check-compiler-errors`（跑编译/类型检查并汇总）、`control-cli`（给交互式 CLI 搭确定性测试脚手架）……每个 Skill 的 frontmatter 只有两行，正文用 "Trigger / Workflow / Output" 三段式写。这种结构不是文风偏好，而是为了**让模型能低成本判断"要不要读"**：`description` 里塞满触发条件（"compile or type-check failures are blocking local validation or CI"），正文才展开步骤。

**第三类：编排器（Orchestrator）。** 最复杂，也最能说明"插件"这个抽象为什么必要。看 `thermos`。

### 3.2 案例拆解：thermos 如何用插件表达一条多 Agent 工作流

`thermos` 的清单声明了 `skills: "./skills/"` 和 `agents: "./agents/"`，磁盘上是：

```text
thermos/
├── .cursor-plugin/plugin.json
├── agents/
│   ├── thermo-nuclear-review-subagent.md
│   └── thermo-nuclear-code-quality-review-subagent.md
└── skills/
    ├── thermo-nuclear-review/SKILL.md
    ├── thermo-nuclear-code-quality-review/SKILL.md
    └── thermos/SKILL.md          ← 编排入口
```

编排入口 `thermos/SKILL.md` 的 frontmatter 有一行关键配置：`disable-model-invocation: true`。意思是**不要靠模型自己"想起来"用我，必须显式调用**。理由很实在：这是一个会启动两个后台 subagent、消耗大量 token 的重操作，不该被一句"帮我看看这个 PR"误触发。

它的 workflow 写得很具体，值得逐条看：

1. 从用户请求 / PR / 当前分支确定审查范围；
2. **先收集 diff 和必要的文件上下文**，让审查者不用猜；
3. 在**同一条消息里**并行启动两个后台 subagent（`run_in_background: true`）：
   - `thermo-nuclear-review-subagent`：找 bug、破坏性变更、安全、DevEx 回归、feature flag 泄漏；
   - `thermo-nuclear-code-quality-review-subagent`：可维护性、结构、文件膨胀、抽象是否合理；
4. 两个 subagent 拿到**同一份**范围化上下文；
5. 汇总时**先去重**，重叠发现加权，分歧自己裁决，摘要从简。

而 subagent 定义里有一条我很欣赏的约束：

> Finish your **independent** audit first (fresh eyes).

先独立审完，再去看 PR 讨论区里 BugBot 和人类的评论。这个顺序不是仪式感——如果先读讨论，模型会被已有结论锚定，等于把一个"独立审查者"退化成了"评论区总结器"。**多 Agent 系统的质量，往往取决于这类"信息隔离"的细节，而不是模型多聪明。**

这段案例说明了一件事：插件不只是"打包 prompt"。它同时承载了**触发策略**（`disable-model-invocation`）、**执行拓扑**（并行 + 后台）、**上下文契约**（同一份 diff）、**聚合规则**（去重、加权、裁决）。这些如果散落在用户的自定义配置里，永远无法复用；装进插件，才成为一个可分发、可版本化的工程资产。

### 3.3 `minClientVersions`：跨客户端发行已经是既成事实

最能证明"一份包、多客户端"不是画饼的，是清单里的 `minClientVersions`。它按客户端标识声明最低版本，值可以是语义化版本，也可以是字符串 `"never"`——后者表示**对该客户端完全隐藏、不可安装**。

仓库里真实的例子：

```json
"minClientVersions": {
  "cursor": "never",
  "grokbot": "0.30.0",
  "sand": "0.30.0"
}
```

这是 Tesla 插件：在 Cursor 里不出现，只在 Grok Bot（`grokbot`，`sand` 是它已弃用的旧标识）0.30.0 及以上可用。换句话说，这个仓库的分发对象**不止 Cursor 一个客户端**，而且同一个包可以按客户端做灰度、做区域/合规限制、做能力门槛。

这也解释了为什么 schema 里 `minClientVersions` 的类型是"任意客户端标识 → 版本要求"的开放字典，而不是写死 `cursor` 一个键。规范作者显然预期会有更多客户端接进来。

但必须把话说清楚：**TSC 里有某家公司，不等于那家公司的客户端已经实现了这份规范。** 治理席位是治理席位，实现是实现。目前能直接验证的，是 Cursor 文档明确写了"支持 Agent Plugins 格式"、以及这个仓库里两套清单并存。至于其他客户端支持到什么程度，需要各自查文档——这正是标准落地期最容易被夸大的地方。

## 四、规范的留白：v1.0.0 不定义信任，而插件恰好是最需要信任的形态

现在说最重要的部分。

Agent Plugins 1.0.0 的 `FUTURE_CONSIDERATIONS.md` 里有五段"v1.0.0 不定义"的清单，几乎是逐条点名了插件生态未来两年所有的事故类型：

- **权限与审批**：清单里没有权限声明（文件系统、网络、工具访问），没有客户端强制的能力限制，没有安装时的用户同意流，没有分级信任（sandboxed / user-approved / organization-approved）。
- **来源验证**：不规定签名验证、不规定"发布物 → 源仓库 → 构建"的证明链、不规定客户端是否要求可信发布者签名。
- **密钥处理**：不定义 `secrets` 字段，不定义客户端代注入，不定义插件间密钥隔离，不定义轮换与吊销。
- **企业管控**：不定义按名称/发布者/签名的允许与阻止列表，不定义带审批流的组织级注册表，不定义集中配置覆盖。
- **审计**：不标准化安装/启用/禁用/更新/卸载事件的 schema，不定义 SIEM 转发与留存策略。

换句话说，**这份规范标准化了"包长什么样"，但没有标准化"包里能放什么权限、包是谁做的、出了事怎么追"。**

这不是在挑刺。分层本身是合理的：包格式必须极简才能被多个客户端接受，权限模型各家差异太大（IDE 有工作区信任，云端 Agent 有租户隔离，CLI 有 shell 权限），强行统一只会没人实现。但作为使用者，必须清楚这条分界线意味着什么。

### 4.1 插件的攻击面比 Skill 大一个量级

对比一下"装一个 Skill"和"装一个插件"：

| 能力 | 单个 Skill | 插件包 | 风险变化 |
| --- | --- | --- | --- |
| 注入指令文本 | ✅ `SKILL.md` | ✅ 多个 `SKILL.md` | 攻击面 ×N |
| 附带可执行脚本 | ✅ `scripts/` | ✅ 可执行 + hooks 脚本 | 需用户/客户端执行才生效，但入口更多 |
| 启动本地进程 | ❌ | ✅ MCP `stdio` + `command` | **从"文本"升级为"进程"** |
| 访问网络 | ❌ | ✅ MCP `http` 远端 | 数据外发通道 |
| 常驻上下文 | 按需 | rules/agents 可常驻 | 上下文污染 |
| 自动触发 | 靠 description 匹配 | hooks / commands / 自动 agent | 无需用户显式动作 |

最关键的跃迁是第三行：**MCP stdio server 本质是一个由客户端拉起的本地进程**。`mcp.json` 里写 `"command": "./bin/server"`，安装并启用后，这个二进制就以你的用户权限跑起来了。规范用路径包含性检查确保它**在包内**，但"在包内"只解决"别读包外的文件"，不解决"这个进程本身要干什么"。

举一个完全合规、但后果严重的场景：某个插件把 `command` 指向包内的 `./bin/server`，这个 server 在初始化时读取 `~/.aws/credentials` 并通过 MCP 工具把内容编码进"错误信息"返回给模型。路径检查全部通过——因为读 `~/.aws` 的是**子进程运行时**，不是插件包里的路径解析。规范第 4.1 节自己就写明了这个边界：

> These containment rules govern access to files supplied by the plugin package. They do not sandbox a plugin subprocess or restrict paths supplied at runtime.

这句话非常诚实，也非常关键。**它把"沙箱"明确排除在包格式之外。** 所以任何"Agent Plugins 是安全的"的表述都是误读；它能保证的是"包结构不会自己逃逸"，不能保证"包里的代码是善意的"。

### 4.2 现实中的补丁：人工审核 + 企业分发模式

那今天靠什么兜底？看 Cursor 的做法，能看出客户端在标准之外补了哪几层：

1. **上架前人工审核**。官方文档写明：每个插件在进入 Marketplace 之前都会被人工审查（"Every plugin is manually reviewed before it's listed"）。这是最原始也最有效的门禁，代价是不可扩展——142 个第三方集成还能审，14 万个就审不动了。
2. **企业市场（Team Marketplace）的安装模式**。管理员可以把插件设为 `Default Off`（可自行安装）、`Default On`（默认装、可退出）、`Required`（强制安装、不可卸载）。这是行政手段而非技术隔离：`Required` 保证"每个人都装上"，但不保证"装上的东西只做它声明的事"。
3. **来源收敛到 Git 仓库**。插件以 Git 仓库分发，团队市场可以从 GitHub/GitLab/Bitbucket/Azure DevOps 导入，还能开启 "Serve marketplace from Cursor" 让 Cursor 保存一份同步副本，成员无需源仓库访问权限。好处是可审计、可 pin 到分支；坏处是**没有签名**，仓库被改了你不会收到密码学意义上的告警。
4. **自动刷新有节流**。GitHub 导入的市场最多每 10 分钟重新索引一次，快速连续 push 会被合并到最新 commit。已经在跑的 Cloud Agent 会**保持启动时的插件版本**，要新开 agent 才拿到更新。这条设计其实很有价值：它给"插件被悄悄更新"提供了一个天然的版本冻结窗口。

这些补丁都有效，但都是**客户端侧、非标准化**的。换一个客户端，同样一个插件可能既没有人工审核，也没有安装模式，更没有版本冻结。**这就是"可移植的包"遇到"不可移植的治理"时的真实摩擦。**

### 4.3 一个具体的裂缝：占位符不兼容

标准落地期最典型的摩擦，往往不是大问题，而是这种小细节。Cursor 文档里有一句很不起眼的话：

> Cursor does not expand the standard's `${PLUGIN_ROOT}` and `${PLUGIN_DATA}` variables in `mcp.json`; use `${CURSOR_PLUGIN_ROOT}` for the plugin root.

也就是说：一个严格按 Agent Plugins 规范写的插件，如果它在 `mcp.json` 里用了 `${PLUGIN_ROOT}`，在 Cursor 里**不会按预期展开**。为了在 Cursor 上跑通，作者得改成 `CURSOR_PLUGIN_ROOT`——而这个变量名是 Cursor 私有的。于是一个"可移植插件"实际上又长出了一根客户端专属的刺。

这不是谁的错误，而是所有"最小公约数标准"的宿命：**标准定义核心，客户端扩展边缘；边缘一旦被使用，可移植性就开始漏气。** 判断一份标准能不能活，不能看它写了多少，要看它的扩展点会不会被滥用成事实标准。

### 4.4 哪些东西仍然不可移植

按 Cursor 文档自己的对照表，Agent Plugins 只覆盖 **skills + MCP**；Cursor 私有格式额外有 rules、agents、commands、hooks、variables。1.1.0 草案正在加"可移植 hooks"，但 agents / commands / rules 仍无处安放。

这带来一个可以预期的结构：**同一个能力会被拆成两层发布**。

- **底层"可移植包"**：1 个 `plugin.json` + skills + `mcp.json`，能进所有客户端，但表达力弱；
- **上层"客户端增强包"**：`.cursor-plugin/plugin.json` 里再加 rules/agents/hooks/commands，只有 Cursor 用户拿得到完整体验。

`cursor/plugins` 仓库就是这个结构的活样本：根目录同时维护两套 marketplace 清单，159 个 `plugin.json` 里有相当一部分是 `.cursor-plugin/` 格式。这不是过渡期的混乱，而很可能是**长期稳态**——因为客户端永远有动力做差异化，而作者永远有动力只维护一份。

## 五、工程建议：把插件当供应链，而不是当配置

如果你是插件使用者，或者正在给团队搭 Agent 工作流，下面几条是我认为最值得马上做的。

**1. 把"安装"当成"引入依赖"，而不是"打开一个开关"。** 依赖要有来源、有版本、有锁。插件目前的现实是：以 Git 仓库分发、按分支刷新、无签名。那就用手头能做的补：pin 到具体 commit 而不是 `main`；在团队市场里用 `Default Off` 起步，验证后再考虑 `Default On`；把"插件版本变更"纳入变更评审，而不是让它随自动刷新悄悄发生。

**2. 对 MCP stdio 插件做进程级审查。** 判断标准不是"清单写得规不规范"，而是三个问题：它 `command` 指向什么？这个进程启动时读哪些路径、连哪些域名？它暴露的工具里，有没有"读文件/执行命令/发网络请求"这类原语？纯 HTTP 连接器（如 Gmail 那种 `type: "http"` 的远端服务）风险面小得多——数据在厂商侧，至少边界清晰。**优先选远端 HTTP，谨慎对待本地 stdio**，这条经验在 MCP 生态里通用。

**3. 密钥不要写进插件配置。** v1.0.0 没有 `secrets` 字段，这意味着密钥要么走环境变量、要么走客户端自己的凭证存储。无论哪种，都不要把长期 token 明文写进仓库里的 `mcp.json`——插件是会被复制、分享、提交到 Git 的。用短期凭证、按插件单独授权、定期轮换，这三件事现在就得做，不能等标准。

**4. 控制 Skill 的常驻预算。** `cursor/plugins` 一个仓库就有 175 个 `SKILL.md`。Skill 的设计本意是渐进披露：常驻的只有 `description`，正文按需读。但即便如此，如果团队把几十上百个 Skill 全量启用，光描述就是一笔不小的常驻开销（按每个描述几十 token 的量级估算，全量常驻会占到数千至万级 token 预算——具体取决于客户端如何聚合，这里只能给量级判断，不能给精确数字）。做法是按项目/角色分组启用，把"每次都相关"的规则留在 rules 里，把"偶尔用一次"的留成 Skill。

**5. 写插件时，把"触发条件"当成一等公民。** 看 `cursor-team-kit` 的写法：`description: "Run compile and type-check commands and report failures"`，正文第一段就是 `## Trigger`。这比写一段漂亮的能力介绍有用得多——模型是靠描述做路由的，描述里没有场景，Skill 就等于不存在。反过来，重操作要加 `disable-model-invocation: true`（如 thermos），避免被误触发。

**6. 如果你的团队有内部工具，现在就该做成插件。** 这是我认为最被低估的机会。过去内部工具的接入方式是"写文档、拉群、手动配 MCP"，现在可以打包成：一个 `plugin.json` + 几个 Skill + 一个 `mcp.json`，通过团队市场以 `Default On` 分发。成本不高，收益是**新人第一天就能让 Agent 用上内部系统**。注意先做权限收窄：内部插件尤其容易把"只读查询"和"写操作"混在一个 MCP server 里。

## 六、判断：接下来 12 个月会发生什么

基于上面拆出来的结构，我给三个可验证的判断。

**判断一：标准会活下来，但"完全可移植的插件"会长期是少数。** 原因是激励不对称：客户端有动力保留差异化组件（rules、hooks、agents 是体验护城河），作者有动力只维护一份。稳态不是"大家都写标准格式"，而是"标准格式做底座、客户端格式做增强"，仓库里两套清单并存就是证据。可验证信号：一年后主流插件是否仍然以私有格式为主、标准格式仅作为兼容层。

**判断二：竞争重心会从"格式"转向"分发与信任"。** 包格式一旦收敛，差异化只能发生在三处：市场审核能力、企业管控（允许/阻止列表、组织注册表、审计）、以及签名与来源证明。这三件事恰好都在 `FUTURE_CONSIDERATIONS.md` 的待办里。可验证信号：是否出现跨客户端的插件签名方案，或至少出现"发布者验证"的市场标签。

**判断三：插件的事故会先于标准出现。** 因为 v1.0.0 已经足够简单、足够多客户端愿意实现，安装量会先涨；而权限模型、密钥隔离、审计都还在"future"。历史规律是：扩展生态的安全事件总在格式统一之后、治理统一之前密集发生（浏览器扩展、npm 供应链都走过这条路）。对个人用户的建议很朴素：**在标准补上权限声明之前，把每个插件都当成"以你的权限运行的第三方程序"来对待。**

## 结语

Agent Plugins 1.0 是一份克制得近乎冷淡的规范。它只做四件事：定义封闭清单、用 `$schema` 钉死版本、用路径包含性把包锁在根目录里、用五级故障边界保证"坏一个不炸全部"。剩下的一律交给客户端。

这种克制值得尊重。多客户端生态里，**能被所有实现者接受的规范，一定是"少到不能再少"的那一份**。但也正因为它这么少，它把最难的问题原封不动地留给了使用者和平台：这个包是谁做的？它要什么权限？它什么时候被换掉了？出了事怎么追？

插件正在成为 Agent 时代的标准件。标准件的好处是可以互换、可以组合、可以规模化；标准件的代价是**你不再逐一看清每一个零件**。在权限模型补上之前，这份代价得由每个装插件的人自己承担——包括正在读这篇文章的你。

---

**资料来源**

- `cursor/plugins` 仓库：GitHub API 与本地 clone（19,194 stars，159 个 `plugin.json`，175 个 `SKILL.md`，16 个 agent 定义，142 个 `third_party/` 目录，最新提交 `41e4009`，2026-11-24）
- Cursor 文档：Plugins 概览与 Plugins reference（两种格式、组件对照、marketplace 审核、team marketplace 安装模式、`${PLUGIN_ROOT}` 不展开的说明）
- Agent Plugins：agent-plugins.org 与 `agentplugins/agent-plugins-spec` 仓库（1.0.0 规范正文、`FUTURE_CONSIDERATIONS.md`、1.1.0 草案状态、TSC 初始成员）
- 案例：`thermos`、`cursor-team-kit`、`third_party/gmail`、`third_party/tesla` 的清单与 `SKILL.md` 原文
