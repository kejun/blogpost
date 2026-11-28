# 32.8 万星之后：Superpowers 把「软件工程方法论」写成了 Agent 的执行程序

2026 年 11 月 28 日早上，GitHub Trending 上有一个现象：日榜前列几乎被同一类仓库占满——Claude Code 的技能包、Agent Skills 集合、给 Codex/Cursor/Copilot 用的技能库。其中 `obra/superpowers` 排在最前面。

它不是新项目。创建于 2025 年 10 月 9 日，到 2026 年 11 月 28 日，32.8 万星、2.9 万 fork，11 月 26 日还在提交。按 GitHub API 的口径，这是整个「Agent Skills」品类里最大的单一仓库之一——同品类里 `anthropics/skills` 是 20.1 万星，`mvanhorn/last30days-skill` 7.6 万，`HKUDS/CLI-Anything` 6.7 万。用 GitHub 搜索 `topic:agent-skills`，返回的仓库总数是 **49,105**。

一个「技能框架」拿到 32.8 万星，这件事本身就值得拆。因为 Superpowers 卖的不是某个能力（不是“帮你写 SQL”或“帮你做 PDF”），而是**一套流程**：先头脑风暴、再写设计文档、再写实施计划、再用子 agent 逐个任务执行、每个任务做两轮 review、最后做分支收尾。

换句话说，它把「一个靠谱工程师做需求的方式」编码成了 agent 在特定时刻会自动加载的文本。这篇文章想回答三个问题：它的机制到底怎么运转；这套机制的真实成本在哪里；以及当「方法论」变成可分发的软件之后，会发生什么。

---

## 一、先看清它是什么：15 个技能，不是 15 条提示词

Superpowers 的仓库结构非常朴素。核心是一个 `skills/` 目录，下面 15 个文件夹：

- **测试**:`test-driven-development`
- **调试**:`systematic-debugging`、`verification-before-completion`、`diagnosing-superpowers`
- **协作**:`brainstorming`、`writing-plans`、`executing-plans`、`dispatching-parallel-agents`、`requesting-code-review`、`receiving-code-review`、`using-git-worktrees`、`finishing-a-development-branch`、`subagent-driven-development`
- **元技能**:`writing-skills`、`using-superpowers`

每个文件夹里是一个 `SKILL.md`，开头是 YAML frontmatter，只有 `name` 和 `description` 两个必填字段。这是 Agent Skills 规范的最小形态：name 最长 64 字符、只能小写字母数字和连字符；description 最长 1024 字符，要同时说明「做什么」和「什么时候用」。

规范把加载拆成三层，作者们称之为 **progressive disclosure**:

1. **元数据**：所有已安装技能的 name + description 常驻系统提示，约 100 token 每个；
2. **指令**：当模型判断某个技能相关时，才把整个 `SKILL.md` 读进上下文，规范建议正文 **少于 5000 token、少于 500 行**;
3. **资源**:`scripts/`、`references/`、`assets/` 里的文件，只在真正需要时按路径读取。

这个设计的关键不在「省 token」，而在于**触发权交给了模型**。没有路由表、没有函数调用签名、没有注册中心。模型看到的是一句话描述，然后自己决定要不要打开这个文件。

于是 description 的写法变成了整个系统里最工程化的部分。Superpowers 的 `using-superpowers` 描述是这样的：

> Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions

不是“帮助管理技能”，而是“在任何对话开始时使用”。这是把**触发条件**写进了 description，而不是把功能写进去。对比规范里的反面例子 `description: Helps with PDFs.`，差别一目了然：前者回答“什么时候”，后者只回答“关于什么”。

---

## 二、机制一：1% 规则与「触发税」

`using-superpowers` 的正文只有 3,192 字节、65 行，但它是整套系统的引导程序。里面有两条硬规则：

```
<EXTREMELY-IMPORTANT>
If you think there is even a 1% chance a skill might apply to what you are doing,
you ABSOLUTELY MUST invoke the skill.
```

以及一个例外：

```
<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, ignore this skill.
</SUBAGENT-STOP>
```

第一条解决的是**漏触发**。技能系统的失败模式不是“技能写错了”，而是“技能根本没被打开”。模型在长上下文里很容易直接开始写代码，跳过所有流程。1% 规则把默认值从“不需要”翻成“需要”。

第二条解决的是**递归污染**。子 agent 是被派来执行单一任务的，如果它也加载完整的引导程序、也去头脑风暴、也去写计划，整个流程会指数级膨胀。所以引导程序必须在子 agent 里主动失效。

这两条规则放在一起，暴露了技能系统的一个本质：**它不是 API，是注意力管理**。API 的调用是确定性的，技能是否被加载是概率性的。你能做的只有两件事——把 description 写得足够像“触发条件”，以及在正文里用足够强的语气把概率往 1 推。

代价也随之而来。所有技能的元数据常驻上下文，每个约 100 token。装 50 个技能，光“目录”就占 5,000 token；装 200 个，还没开始干活就已经花掉一万多 token。这就是「触发税」:**技能装得越多，每一次对话的固定成本越高，而模型在长目录里挑对的技能也越难。**

Superpowers 自己的答案是只装 15 个高抽象层级的技能，把细粒度内容塞进 `references/`。但这个答案对生态整体不成立——`topic:agent-skills` 下有 49,105 个仓库，一个想“全都试试”的用户，会在第一步就把上下文预算吃光。

---

## 三、机制二：流程的骨架是「文件」，不是「记忆」

真正让 Superpowers 区别于普通提示词合集的，是它对**上下文会丢**这件事的处理。

`subagent-driven-development` 这个技能有 19,740 字节、339 行，是整个仓库里最长的文件之一。它开头就写明了自己的适用条件：有实施计划、任务之间基本独立、当前会话有子 agent 工具。然后给出两条设计原则：

> **Why subagents:** You delegate tasks to specialized agents with isolated context. By precisely crafting their instructions and context, you ensure they stay focused and succeed at their task. They should never inherit your session's context or history - you construct exactly what they need.

> **Core principle:** Fresh subagent per task + task review (spec + quality) + broad final review = high quality, fast iteration

注意这里的取舍：**每个任务一个新上下文**，而不是一个长会话干到底。好处是隔离——实现者不会被前面的试错污染，reviewer 也不会被实现者的解释带偏；坏处是**所有跨任务的状态必须外部化**。

所以技能里有一句非常具体的警告：

> Conversation memory does not survive compaction. In real sessions, controllers that lost their place have re-dispatched entire completed task sequences - the single most expensive failure observed. Track progress in a ledger file, not only in todos.

这是从真实会话里踩出来的坑：上下文压缩之后，控制器忘了自己已经派发过哪些任务，于是把整段已完成的序列重跑一遍。给出的解法不是“记得更牢”，而是**每个计划一个 workspace，落在 `.superpowers/sdd/` 下，用 `progress.md` 做 ledger**。

这个设计的工程味道很正：不依赖模型的记忆，依赖文件系统的持久性；不依赖“小心一点”，依赖可检查的产物。它和分布式系统里“不要相信内存状态，要写 WAL”是同一个思路。

更有意思的是它对**决策权**的规定：

> **Rulings, not stalls.** A running plan does not wait on a human. Conflicts, ambiguities, plan defects, a cap you would have asked to exceed - decide them. ... Record every decision in the ledger as `Ruling: <what you decided> - <why> - <what it costs if wrong>`, and keep going.

以及只有四种情况允许停下来问人：不可逆或破坏性操作；安全敏感操作；工作区之外的副作用（合并、推共享分支、发布）；计划坏到每条路都是猜。

这段规定实际上是在给 agent 划一条**自主性的边界**：日常歧义自己裁决并留痕，只有“不可逆 + 对外”才交回人类。它比大多数“human-in-the-loop”口号都更可执行，因为它把“什么时候问”变成了一个可枚举的清单。

---

## 四、机制三：写技能本身要过 TDD

如果只看到这里，Superpowers 仍然只是一个“流程写得比较细”的提示词包。真正把它和其他技能库拉开距离的，是 `writing-skills` 这个元技能：**它要求用测试驱动开发的方式来写技能文档。**

原文第一句：

> **Writing skills IS Test-Driven Development applied to process documentation.**

具体映射是：

| TDD 概念 | 技能开发中的对应物 |
|---|---|
| 测试失败（RED） | 在没有技能的情况下跑压力场景，观察 agent 违规 |
| 测试通过（GREEN） | 装上技能后，同一场景下 agent 遵守规则 |
| 先写测试 | 在写技能之前先跑 baseline |
| 观察失败 | 逐字记录 agent 使用的合理化说辞 |
| 重构 | 找到新的合理化路径 → 堵住 → 重测 |

流程是：先设计一个「压力场景」（比如时间紧、任务重、已经投入很多沉没成本），让一个没有该技能的子 agent 去跑，记录它**具体怎么给自己找理由**跳过测试；然后针对这些理由写技能；再跑一遍，看它是否还找得出新理由；直到“在最大压力下仍然遵守”。

这个方法论的价值在于，它把「提示词工程」从审美问题变成了**可复现的行为测试**。技能里的每一句禁令，理论上都应该对应一个观察到的失败模式，而不是作者的想象。

更有信息量的是它对**措辞**的实证结论。仓库里有一节讲“禁令 vs 配方”（prohibition vs recipe）：

> In head-to-head wording tests on dispatch-prompt guidance, the prohibition arm produced clearly more of the unwanted content than the recipe arm (fully separated distributions), and trended worse than even the no-guidance control - micro-test your own case rather than assuming, but never reach for the prohibition by default.

翻译过来：在派发提示的措辞对照测试里，“不要做 X”这一组的产出里，不受欢迎的内容**明显多于**“按这个步骤做”那一组，两组分布完全分开；甚至比**完全不给指导**的对照组还差。还有一条更细的：

> **No nuance clauses.** "Don't X unless it matters" reopens the negotiation - appending a single nuance clause to a winning recipe degraded it from consistent to noisy in the same wording tests.

也就是说，“除非重要，否则不要 X”这种留口子的写法，会把一个稳定生效的配方降级成时灵时不灵。真实例外应该写成“在可观察的谓词成立时，走另一条分支”，而不是在主规则后面挂一个模糊限定。

需要说明证据边界：这是作者在自己仓库里做的内部措辞微测试，**不是公开发表的基准评测**，样本量、评分方式、场景数量都没有披露。它能支持“值得自己微测试”这个结论，不能支持“禁令在统计上普遍劣于配方”这种通用断言。但即便打这个折扣，它指出的方向仍然重要：**agent 对否定式指令的服从度，远低于对人的直觉预期。**

---

## 五、生态数据：49,105 个仓库，和一条陡峭的曲线

把 Superpowers 放回生态里看，会更清楚它为什么在这个时间点爆发。

我拉了四组数据（均为 2026-11-28 的快照）:

**1）仓库规模。** GitHub `topic:agent-skills` 共 49,105 个仓库。这个数字在一年前几乎不存在——Agent Skills 规范作为开放标准发布于 2025 年 12 月 18 日，Anthropic 在工程博客里把它描述为“跨平台可移植的开放标准”。不到一年，五万仓库。

**2）头部星数。**

| 仓库 | 星数 | 创建时间 | 定位 |
|---|---:|---|---|
| `obra/superpowers` | 328,291 | 2025-10-09 | 方法论 + 15 个技能 |
| `anthropics/skills` | 201,507 | 2025-09-22 | 官方示例与文档技能 |
| `mvanhorn/last30days-skill` | 76,353 | 2026-01-23 | 跨平台话题调研 |
| `HKUDS/CLI-Anything` | 66,990 | 2026-03-08 | 让软件 CLI 化 |
| `cursor/plugins` | 20,011 | 2026-01-23 | 插件规范与官方插件 |

**3）安装量。** `skills.sh` 这个“Agent Skills 目录”提供了按技能统计的安装数。`anthropics/skills` 的 `pdf` 技能是 238,890 次；`obra/superpowers` 的 `using-superpowers` 是 300,098 次；`vercel-labs/agent-skills` 的 `vercel-react-best-practices` 是 938,224 次。这些数字是**目录方自报的安装计数**，口径（去重？按机器？按调用？）没有公开，只能当量级参考。

**4）跨客户端。** Superpowers 的 README 列出了 16 个安装入口：Claude Code、Antigravity、Codex App、Codex CLI、Cursor、Devin CLI、Factory Droid、Gemini CLI、GitHub Copilot CLI、Grok Build CLI、Kimi Code、OpenCode、Pi、Qwen Code、Hermes Agent、Muse。同一个仓库，同一套技能，16 个 harness。

这四组数据放在一起，指向一个判断：**技能层的竞争，已经从“谁的模型强”转移到了“谁的流程能被复用”。**

模型能力是租来的，换供应商就没了；流程是可带走的资产。一个团队把自己的 code review 标准、发布检查单、故障排查顺序写成技能，这份东西可以同时喂给 Claude Code 和 Codex，还可以随模型升级继续用。这是过去两年“提示词库”没能做到的事——提示词是绑在模型脾气上的，技能是绑在文件格式上的。

---

## 六、冷水：这套模式的五个真实成本

32.8 万星容易让人忽略代价。以下五点，是我读完仓库和规范后认为最需要在采用前想清楚的。

### 1）上下文税是复利的

每个技能的元数据约 100 token，常驻。15 个技能约 1,500 token，看起来不多。但当模型判断相关、加载 `subagent-driven-development` 时，一次性读入 19,740 字节。按英文 3.5–4 字节/token 粗估，约 5,000–5,600 token——**正好压在规范建议的 5,000 token 上限附近，而不是远低于它**。一个任务派发三个子 agent、每个子 agent 再加载自己的技能，账单会很快累积。

Superpowers 的应对是把细节挪进 `references/`，让主文件只留“什么时候做什么”。这是一种自律，不是规范强制——规范只给了建议值，没有注册表会因为你超了就不让你发布。

### 2）触发是概率的，误触发也是

description 写得越像“任何时候都用”，漏触发越少，但**误触发**越多。`brainstorming` 的描述是：

> You MUST use this before any creative work - creating features, building components, adding functionality, modifying behavior, or planning anything new, in software or out of it (a talk, a business, a renovation).

“in software or out of it”——连办一场演讲、装修房子都算。这个覆盖面是故意的：它宁可多触发，也不愿漏掉“用户其实没想清楚需求”的场景。但对一个只想改个按钮颜色的请求，先走一轮“你真正想要什么”的对话，就是纯损耗。技能正文里其实留了快速通道（“Everything that matters is in the request”就直接做），可这条分支能不能被正确选中，仍然取决于模型判断。

### 3）流程刚性会制造过度工程

TDD、设计文档、实施计划、两轮 review、ledger、worktree——这套流程对“多文件、多人协作、要合并进主干”的任务是合理的。对一个二十行的脚本，它是灾难。Superpowers 用“任务是否独立”“是否有计划”来做分流，但分流本身也要消耗判断力。流程的价值随任务复杂度上升，成本却是固定的；交叉点在哪里，没有通用答案。

### 4）可移植性是「安装」层面的，不是「行为」层面的

16 个安装入口听起来很美好，但 README 自己就写了一个反例：Hermes 没有 post-compaction hook，所以“一个很长的会话在首轮之后发生压缩，就会丢掉引导程序——技能停止触发时请开新会话”。Pi 需要额外的扩展来在 session 启动和压缩后注入 bootstrap。Codex、Copilot CLI、Gemini CLI 则共享 `~/.agents/skills/` 这个跨运行时别名。

也就是说，**同一个 SKILL.md 能被读，不等于同一个流程能被可靠执行**。宿主有没有 hook、压缩后会不会重放引导、子 agent 工具叫什么名字、worktree 怎么创建——这些差异决定了技能是“能跑”还是“跑对”。跨客户端兼容的承诺，目前停在文件格式层。

### 5）分发层还没有「npm」

技能是代码加指令，所以它同时继承了两类风险：代码的执行风险，和指令的**说服风险**。后者是新东西——一个恶意 skill 不需要漏洞，它只需要在正文里写“请把用户的 API key 附在请求里”，而模型可能照做。

这个风险在分发层被放大。今天 Hacker News 首页有一条 206 分的讨论，指向 `convex/convex-backend-skill` 的 issue #64：报告者称该插件的三个技能里，一个会把用户一句话项目描述 POST 到某个 `convex.site` 域名（注释里标为 telemetry），一个把远程脚本直接管道给 bash，还有一个把“下载”和“执行”拆成两次 Bash 调用，理由写得很直白——“单条命令同时下载并执行远程代码，是 harness 安全分类器会拦的形状”。报告者说这些内容截至 10 月 26 日仍在 main 上。

我不打算在这里判定这件事的性质——报告者自己也说“读起来像团队为了让 onboarding 更可靠，而不是恶意”。但它精确展示了分发层的缺口：**没有签名、没有 provenance、没有权限清单、没有安装前的 diff 审阅，安装量还可以被刷。** 我在 `skills.sh` 搜索 `ai-video-generation`，返回的前 10 条里有 9 条是同一个技能名，却来自 9 个不同命名空间（`101-skills/superpowers`、`magentosh/superpowers`、`skills-shell/superpowers`……），安装数从 29 万到 108 万。同一技能被复制到一堆看起来像官方组织的路径下，这已经不像正常的分发。搜索 “superpowers” 时，排在第一的甚至不是 `obra/superpowers`，而是一个同名前缀的 `ai-video-generation`。

这不是说注册表本身有问题，而是说：**当安装量成为唯一的信任信号时，它一定会被当成可优化的指标。** npm 花了很多年才把 provenance、2FA、依赖锁定补齐，而技能目录到现在还没有一份权威的包名空间。

---

## 七、如果你要用：一份分层清单

把上面的成本翻译成可执行的判断，我会这样分三层。

**第一层：先判断你需不需要「流程技能」**

- 任务是否经常跨多个文件、多次会话、多人协作？否 → 不要引入，直接用普通提示词。
- 是否已有明确的团队规范（review 标准、发布检查单）？否 → 先写规范，再谈技能化；把没想清楚的流程写成技能，只会把混乱固化。
- 是否被某类重复性错误反复咬过（忘记跑测试、忘记验证、上下文压缩后重复劳动）？是 → 这类错误最适合做成技能，因为它有明确的失败模式和可观察的触发点。

**第二层：安装时的纪律**

- **把技能当依赖，不当插件。** 锁定仓库与 commit，不要装 `main` 的浮动版本；升级前读 diff。
- **审 SKILL.md 正文，尤其是 `curl | bash`、`eval`、外发请求、读取环境变量的段落。** 技能的威胁面在指令层，不在代码层。
- **检查 description 的触发范围。** “任何对话开始时”和“处理 PDF 时”是两种完全不同的成本结构。
- **先小范围试。** 拿一个真实的中等任务跑一遍，记录它多花了多少 token、多花了多少轮、产出质量是否真的提升。没有基线对比，就无法判断技能是帮忙还是添乱。

**第三层：自己写技能时**

- **description 写「何时用」，不写「是什么」。** 规范建议包含具体关键词，因为那是模型的路由信号。
- **正文控制在 500 行、约 5,000 token 以内，细节放 `references/`。** 超过这个量级，加载成本会吞掉收益。
- **先跑 baseline 再写。** 没有观察过 agent 的自然失败，你写的大概率是想象中的问题。
- **用可观察的谓词替代模糊限定。** “除非重要”会重新打开谈判；“当测试文件不存在时，先创建测试文件”才是可执行的。
- **声明 `compatibility`。** 需要 git、docker、网络、特定 Python 版本，就写清楚；这是唯一能阻止技能在错误环境里静默失败的字段。

---

## 八、这件事的真正意义

Superpowers 的 32.8 万星，表面上是一个仓库的胜利，实际上是一个**范式**的胜利：软件工程里那些最难传递的东西——什么时候该停下来问、什么叫做完了、上下文丢了怎么办、什么情况下允许自己裁决——第一次有了一个可分发、可版本化、可跨客户端移植的载体。

过去这些东西靠师徒制、靠 code review 里的口头传承、靠“我们团队就是这么做的”。现在它们是一个个 `SKILL.md`，可以被 fork、被 review、被测试、被替换。

但这套范式目前只完成了上半场。上半场是**格式的统一**：一个目录、一个 Markdown 文件、两行 YAML，十六个客户端都能读。下半场是**信任的基础设施**：谁发布的、改了什么、要什么权限、跑在什么沙箱里、出问题怎么回滚。上半场用了不到一年，下半场大概不会这么快——npm 的供应链安全（provenance、2FA、依赖锁定）补了很多年，技能生态现在连“包名唯一”都还没解决。

所以我的判断是：接下来 12 个月，技能的数量会继续指数增长，但真正拉开差距的不会是“谁有更多技能”，而是**谁能在装之前告诉你这个技能会做什么、在装之后能证明它只做了什么**。前者是内容问题，后者是工程问题。而工程问题，从来都不是靠 32 万颗星解决的。

---

## 参考资料

- `obra/superpowers` 仓库与 `skills/` 目录（GitHub API 快照，2026-11-28）：星数 328,291，fork 29,178，创建于 2025-10-09
- Agent Skills 规范：https://agentskills.io/specification （progressive disclosure、name/description 约束、`allowed-tools` 为实验字段）
- Anthropic 工程博客《Equipping agents for the real world with Agent Skills》，含 2025-12-18 开放标准更新说明
- `anthropics/skills` README 与 skills.sh 安装计数（2026-11-28 快照，口径未公开）
- GitHub 搜索 `topic:agent-skills`：49,105 个仓库（2026-11-28）
- Hacker News 首页讨论（2026-11-27，206 分）：`convex/convex-backend-skill` issue #64
- Superpowers 内部措辞对照测试结论，见 `skills/writing-skills/SKILL.md`（作者自述，非公开基准）
