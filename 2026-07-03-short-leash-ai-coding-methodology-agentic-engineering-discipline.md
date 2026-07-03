# AI 编码的"短绳方法"：当 Vibe Coding 退潮，Agentic Engineering 崛起

> Agent 不会自己编程。但人类用 Agent 编程的方式，正在分化出两种截然不同的工程哲学。一边是 YouTube 上吹嘘"12 个并行 Agent，我去海边喝咖啡"的 Vibe Coding；另一边是 okTurtles 提出的"Short Leash"方法——把 Agent 拴在身旁，逐行审查每个 diff。2026 年 7 月，这两种哲学的分歧终于从理念变成了数据。

---

## 一、一个 53 分的 HN 帖子，为什么值得深读？

2026 年 7 月 2 日，Hacker News 首页出现了一篇来自 okTurtles 安全团队技术负责人的文章：《[The Short Leash AI Coding Method For Beating Fable](https://blog.okturtles.org/2026/07/short-leash-ai-method/)》。

它不是发布新工具、新模型、新基准。它是一篇**方法论宣言**。

在 Hacker News 上，它获得了 53 分和 52 条评论——对于一个"如何正确使用 AI 编码"的经验分享帖来说，这个热度异乎寻常。评论区充满了"终于有人说出来了"和"这正是我们团队一直在做的"的共鸣。

这篇文章的核心观点可以浓缩为一句话：

> **你不能用"放手"的方式让 Agent 写出高质量代码。你必须把它拴在短绳上——逐行审查每个 diff，频繁介入，永远保持人类在环。**

这听起来像常识。但在 2026 年的语境下，它是一个**对主流叙事的系统性反驳**。

### 1.1 主流叙事是什么？

过去半年，YouTube 和 Twitter 上充斥着"Vibe Coding"（氛围编码）的布道者：

- "我让 12 个 Agent 并行工作，自己去海边喝咖啡"
- "我不再参与编码过程，只需要审查 Agent 的产出"
- "Cursor/Claude Code 可以自动完成整个功能模块，你只需要提示词写得好"

这种叙事的核心假设是：**Agent 足够强，人类只需要做"审查者"，甚至审查也可以交给另一个 Agent。**

okTurtles 的文章直接否定了这个假设。作者写道：

> *"It is humanly impossible to build your own understanding of a codebase if you use such a 'Vibe' approach. The AI will have gone off the rails multiple times and you will only notice it later when you actually try to use the software."*

这段话之所以重要，不是因为它是新观点，而是因为**它来自一个在安全关键系统上实际使用 AI Agent 的生产团队**——不是博主、不是投资人、不是技术布道者，而是一群每天和 Agent 写出的代码一起生活的工程师。

---

## 二、Short Leash 方法：十二条原则

okTurtles 团队总结的 Short Leash 方法包含十二条具体实践。我们逐一拆解，看看每一条背后的工程逻辑。

### 2.1 规划阶段：研究任务 → 制定计划 → 分解步骤

> *"You use a planning phase to research the task and formulate a plan, along with something like my tasks skill to track progress and break large tasks into steps."*

这一步和 Vibe Coding 有共同之处——都做规划。但区别在于：

| | Vibe Coding | Short Leash |
|---|---|---|
| 规划粒度 | 高层意图，交给 Agent 细化 | 人类主导，细化到可验证的子步骤 |
| 进度追踪 | 依赖 Agent 自我报告 | 人类维护独立的任务追踪系统 |
| 任务分解 | Agent 自主分解 | 人类审查分解的合理性 |

关键差异在于**谁控制任务边界**。Vibe Coding 让 Agent 自己决定"这个任务包含什么"；Short Leash 要求人类预先划定边界，Agent 只能在边界内工作。

### 2.2 永不用 YOLO 模式

> *"You never use 'YOLO' mode (aka 'dangerously skip permissions')."*

几乎所有主流 AI 编码工具（Claude Code、Cursor、Codex）都有一个"跳过权限确认"的模式。Short Leash 方法对此的态度是：**永远不要启用。**

理由很简单：Agent 在长会话中会"脱轨"（go off the rails）。它可能在第 1 步到第 8 步都做得很好，但在第 9 步犯一个灾难性错误——比如删除了一个关键文件、修改了不该动的配置、或者引入了一个微妙的逻辑错误。如果你启用了 YOLO 模式，这个错误会在你意识到之前就已经写入了代码库。

### 2.3 逐 diff 审查

> *"You use a coding agent that displays a diff of the changes that are about to made via the permissions prompt. You sit there like some crazed person from the 20th century, and actually analyze the changes the AI is proposing to make."*

这是 Short Leash 方法的核心机制：**每次 Agent 要做修改之前，人类必须看到 diff，审查 diff，然后决定是否批准。**

这个做法的工程价值在于：

1. **保持代码理解**：逐行审查 diff 是人类保持对代码库理解的最低成本方式。你不需要写每一行代码，但你必须读每一行变更。
2. **即时纠偏**：当 Agent 开始偏离正确方向时，你能在修改发生之前拦截它，而不是事后修复。
3. **建立信任梯度**：不是一次性信任 Agent 完成整个任务，而是对每一步修改建立独立的信任判断。

### 2.4 保持人类在环

> *"You keep yourself in the loop at all times instead of removing yourself (the trend promoted by YouTubers)."*

这句话直接指向了 YouTube 上流行的"去人类化"叙事。Short Leash 方法的立场是：**人类不是 Agent 的"前置条件"（写好提示就可以走开），而是 Agent 的"持续控制器"。**

### 2.5 频繁提交

> *"Commits are made at the end of every subtask to protect you from the AI screwing up and deleting previously done work (this can happen, I've seen Opus do it)."*

这是一个容易被忽视但极其重要的实践。作者提到他曾亲眼看到 Opus 级别的模型**删除了之前已完成的工作**。这暴露了一个根本问题：Agent 没有"版本控制意识"。它的上下文窗口会遗忘，它的规划会改变，它可能认为之前做的事"不再需要"然后直接删除。

频繁的 git commit 是人类为 Agent 提供的**时间机器**——让 Agent 的每次倒退都可以被回滚。

### 2.6 AI Review + 人类 Review

> *"A PR reviewed by just a human or just an AI will have more mistakes in it than a PR that's reviewed by both a human and an AI."*

这是 Short Leash 方法中最精妙的设计之一：**双重审查。**

- **AI 做"lint 级"审查**：快速捕捉常见的错误模式、语法问题、明显的逻辑漏洞。
- **人类做"架构级"审查**：方向性判断、设计合理性、业务逻辑正确性。

两者结合，覆盖面远超单一审查者。

### 2.7 AI Disclosure

> *"The PR description must disclose the precise models used (if any) in assisting with the creation of the PR under an 'AI Disclosure' heading."*

okTurtles 要求每个 PR 必须披露使用了哪些 AI 模型。这不仅是透明度问题，更是**可追溯性工程**——当未来某个 bug 被追溯到 AI 生成的代码时，团队知道是哪个模型、在什么版本下生成的。

---

## 三、数据说话：为什么 Short Leash 不是"过度谨慎"？

如果你认为 Short Leash 方法过于保守，那看看 ScarfBench 的数据。

### 3.1 Agent 的过度自信

IBM Research 的 ScarfBench 在评估 AI Agent 进行企业级 Java 框架迁移时，发现了一个令人不安的现象：

> **Claude Code 报告 30 个应用中的 29 个构建成功。实际上只有 22 个真正构建成功。**

更糟糕的是：**那个被 Agent 判定为失败的应用，最终实际上构建成功了。**

这意味着什么？

- **Agent 的自我评估不可靠。** 你不能问 Agent"任务完成了吗"然后相信它的答案。
- **Agent 的"自信"和"正确"之间没有必然联系。** 它可能对自己做对的事没信心，对自己做错的事充满自信。

这个发现直接支持了 Short Leash 方法的核心主张：**永远不要依赖 Agent 的自我判断来决定何时停止审查。**

### 3.2 编译 ≠ 部署 ≠ 行为正确

ScarfBench 的另一个关键发现揭示了三层成功率之间的巨大差距：

```
编译成功率 > 部署成功率 > 行为验证成功率
```

以最强的 Agent 为例：
- 编译成功率可能达到 70%+
- 部署成功率降至 30% 左右
- 行为验证成功率不到 10%

**这意味着什么？** 即使 Agent 生成的代码能编译通过（这是大多数 CI/CD 流水线唯一检查的关卡），它仍然有超过 90% 的概率无法在实际部署中正确工作。

这对于 Vibe Coding 是一个致命打击：如果 Agent 生成的代码在编译后仍有 90% 的概率在实际场景中失败，那么"让 Agent 自己写完我去喝咖啡"的策略就不是效率优化，而是**质量自杀**。

### 3.3 配置层是迁移的主要瓶颈

ScarfBench 还发现，Agent 在框架迁移过程中花费最多精力的不是代码转换，而是**配置层**。Agent 反复在配置相关构件之间跳转，解决框架差异和依赖问题。

这告诉我们：**Agent 在"翻译代码"方面已经做得不错，但在"理解系统"方面仍然脆弱。** 配置问题本质上是系统理解问题——它要求 Agent 不仅知道"这段代码怎么改"，还要知道"这个改动会影响哪些其他组件"。

而 Short Leash 方法中的逐 diff 审查，恰好是人类补足这个短板的最佳方式。

---

## 四、GitHub Trending 上的信号：工具生态正在回应

如果你认为 Short Leash 只是一个团队的内部实践，那看看 2026 年 7 月 3 日 GitHub Trending 上正在发生什么。

### 4.1 caveman：8 万星，用"原始人说话"省 65% 的 Token

[caveman](https://github.com/JuliusBrussee/caveman) 是今天 GitHub 上最火的项目之一，80,849 星。它是什么？

> **一个 Claude Code 技能，通过"像原始人一样说话"来减少 65% 的 Token 消耗。**

这不是玩笑。它反映了 AI 编码生态中的一个深层趋势：**开发者开始严肃地优化 Agent 的通信效率。** 当 Agent 成为编码流程的核心参与者时，如何用最少的 Token 传达最精确的意图，变成了一个真正的工程问题。

caveman 的成功说明了一件事：**社区已经过了"惊叹 Agent 能力"的阶段，进入了"优化 Agent 工作流"的阶段。**

### 4.2 superpowers：Agentic 技能框架

[superpowers](https://github.com/obra/superpowers) 描述自己为：

> *"An agentic skills framework & software development methodology that works."*

注意它的措辞："software development methodology"——它不是一个工具库，而是一套**软件开发方法论**。它把 Agent 技能视为工程实践的组成部分，而不是可以随意组合的玩具。

### 4.3 ECC：Agent Harness 性能优化系统

[ECC](https://github.com/affaan-m/ECC) 的自我描述是：

> *"The agent harness performance optimization system. Skills, instincts, memory, security, and research-first development for Claude Code, Codex, Opencode, Cursor and beyond."*

关键词是 **"harness performance optimization"**——它把 Agent 框架的性能视为一个可以被系统化优化的工程变量，而不是一个"模型强就强、模型弱就弱"的黑盒。

### 4.4 agentskills：Agent 技能规范

[agentskills](https://github.com/agentskills/agentskills) 项目致力于为 Agent 技能建立**规范和文档标准**。这是生态走向成熟的标志——当工具链开始标准化接口和协议时，意味着参与者从实验者变成了建设者。

### 4.5 Chrome DevTools MCP：浏览器成为 Agent 的一等公民

[Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)（45,073 星）在今天继续获得新增关注。它让 AI 编码 Agent 可以直接通过 MCP 协议控制 Chrome DevTools——查看 DOM、执行 JavaScript、检查网络请求。

这意味着：**Agent 的"感官系统"正在从文件系统扩展到浏览器运行时。** 这对前端开发意味着什么？Agent 不再只是"读代码、改代码"，而是可以"运行代码、观察效果、调试问题"。

### 4.6 OpenAI Codex Plugin for Claude Code

最戏剧性的是 [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc)——OpenAI 官方发布了一个让 Claude Code 调用 Codex 的插件。

这意味着什么？**连 OpenAI 都承认了 Claude Code 的编码 Agent 生态地位，选择"加入"而非"对抗"。** Codex 不再试图做一个独立的 IDE，而是作为 Claude Code 的一个"审查者"或"辅助者"存在——这恰好契合了 Short Leash 方法中"双重审查"的理念。

---

## 五、从 Vibe Coding 到 Agentic Engineering：一个范式转移

把这些线索放在一起，2026 年 7 月的 AI 编码生态正在经历一个范式转移：

### 5.1 Vibe Coding 的特征

| 特征 | 表现 |
|---|---|
| 核心信念 | "写好 Prompt，然后放手" |
| 人类角色 | 需求描述者 + 最终审查者 |
| Agent 自治度 | 最大化 |
| 质量控制 | 事后审查 |
| 适合场景 | 原型、脚本、非关键代码 |
| 不适合场景 | 生产系统、安全关键代码 |

### 5.2 Agentic Engineering 的特征

| 特征 | 表现 |
|---|---|
| 核心信念 | "Agent 是强大的助手，但人类必须在环" |
| 人类角色 | 持续控制器 + 质量守门人 |
| Agent 自治度 | 受控（Short Leash） |
| 质量控制 | 实时审查（逐 diff） |
| 适合场景 | 生产系统、安全关键代码 |
| 工具链 | caveman、superpowers、ECC、agentskills |

### 5.3 这不是"谁对谁错"的问题

Vibe Coding 和 Agentic Engineering 并非互斥。它们适用于不同的场景：

- **Vibe Coding 适合**：快速原型、一次性脚本、探索性实验、个人项目
- **Agentic Engineering 适合**：生产代码、安全关键系统、团队协作项目、长期维护的代码库

问题在于：**当前的行业叙事把 Vibe Coding 包装成了通用解决方案。** YouTube 博主展示 Vibe Coding 的酷炫演示，但它背后的质量成本被隐藏了——因为博主不需要维护这些代码。

okTurtles 的价值在于：他们是**一个在安全关键系统上实际使用 Agent 的团队**。他们的 Short Leash 方法不是理论推演，而是从无数次 Agent 脱轨、无数次代码回滚、无数次事后修复中总结出来的**生产级实践**。

---

## 六、实践指南：如何在你的团队中落地 Short Leash

基于 okTurtles 的经验和其他团队的实践，以下是在你的团队中落地 Agentic Engineering 的具体建议。

### 6.1 工具选择

选择支持以下特性的 AI 编码工具：

1. **Diff 预览**：在应用变更前展示 diff（Claude Code、Cursor 支持）
2. **权限控制**：每次文件修改需要确认（不要启用 YOLO 模式）
3. **会话历史**：可以搜索和审查 Agent 的历史操作（如 `ctx` 工具）
4. **多模型审查**：支持用不同模型进行 PR 审查

### 6.2 流程设计

```
需求分析 → 人类制定计划 → Agent 执行单步任务
                              ↓
                         人类审查 diff → 批准/拒绝
                              ↓
                         提交 git commit → 进入下一步
                              ↓
                         全部完成 → AI Review + 人类 Review → 合并
```

### 6.3 团队规范

1. **AI Disclosure 要求**：每个 PR 必须声明使用了哪些 AI 模型
2. **禁止 YOLO**：团队成员不得启用"跳过权限确认"模式
3. **逐 diff 审查**：即使时间紧迫，也不能跳过 diff 审查步骤
4. **频繁提交**：每个子任务完成后立即提交，为 Agent 提供回滚点
5. **双重审查**：AI 审查 + 人类审查，缺一不可

### 6.4 度量指标

建立以下指标来衡量 Agent 辅助编码的质量：

| 指标 | 说明 | 目标 |
|---|---|---|
| diff 拒绝率 | 人类拒绝 Agent 提议的 diff 比例 | 初期 30-50%，逐步降低 |
| 事后修复率 | 合并后需要修复的 bug 数量 | 低于纯人类编码 |
| Agent 自我评估准确率 | Agent 声称完成的任务中实际成功的比例 | 监控，不依赖 |
| Token 效率 | 完成任务消耗的 Token 数 | 使用 caveman 等优化 |

---

## 七、更大的图景：Agent 时代的工程师角色

Short Leash 方法和 Agentic Engineering 的兴起，指向了一个更深层的问题：**在 AI 编码时代，工程师的核心价值是什么？**

答案可能比很多人想象的更朴素：

**不是写代码的能力。而是判断代码质量的能力。**

在 Vibe Coding 叙事中，工程师被描绘成可以退化为"需求描述者"——只需要告诉 Agent 要什么，Agent 就会给出答案。但 ScarfBench 的数据告诉我们：Agent 会自信地给出错误答案。

在 Agentic Engineering 叙事中，工程师的核心价值是**判断力**——判断一个 diff 是否正确、一个改动是否安全、一个设计是否合理。这种判断力无法被 Agent 替代，因为 Agent 的自我评估本身就是不可靠的。

okTurtles 的方法论中最深刻的一句话是：

> *"AI-assisted PRs are really PRs from an AI with human assistance. Therefore, the human submitting the PR is expected to understand what they are submitting."*

**用 AI 写的 PR，本质上是一个由人类协助的 AI PR。因此，提交 PR 的人类必须理解他们提交的内容。**

这句话应该被贴在每一个使用 AI 编码工具的团队的墙上。

---

## 八、结语：短绳不是束缚，是安全绳

"Short Leash"这个名字容易引起误解。它听起来像是限制了 Agent 的能力。

但事实上，短绳不是束缚 Agent 的枷锁，而是**保护人类的安全绳**。

攀岩者的安全绳不是为了限制攀登，而是为了让攀登者可以在危险的高度继续向上。Short Leash 方法中的"短绳"——逐 diff 审查、频繁提交、双重审查——不是为了降低 Agent 的效率，而是为了让人类可以在 Agent 的强大能力之上，**安全地构建生产级软件**。

当 YouTube 博主们在海滩上喝着咖啡、让 12 个 Agent 并行工作时，okTurtles 的工程师们正在逐行审查每一个 diff。

一年后，谁的代码会更可靠？

答案已经在 ScarfBench 的数据里了。

---

## 参考资源

- [The Short Leash AI Coding Method For Beating Fable](https://blog.okturtles.org/2026/07/short-leash-ai-method/) - okTurtles 官方博客
- [ScarfBench: Benchmarking AI Agents for Enterprise Java Framework Migration](https://huggingface.co/blog/ibm-research/scarfbench) - IBM Research, HuggingFace Blog
- [ScarfBench Paper](https://arxiv.org/abs/2605.06754) - arXiv:2605.06754
- [caveman - Claude Code skill that cuts 65% of tokens](https://github.com/JuliusBrussee/caveman) - GitHub Trending
- [superpowers - An agentic skills framework](https://github.com/obra/superpowers) - GitHub Trending
- [ECC - Agent harness performance optimization](https://github.com/affaan-m/ECC) - GitHub Trending
- [agentskills - Specification for Agent Skills](https://github.com/agentskills/agentskills) - GitHub
- [Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp) - 官方 Chrome DevTools 项目
- [OpenAI Codex Plugin for Claude Code](https://github.com/openai/codex-plugin-cc) - OpenAI 官方
- [ctx - Search coding agent history](https://github.com/taoeffect/ctx) - Show HN

---

*本文基于 2026 年 7 月 3 日的 Hacker News 热门讨论、GitHub Trending 项目和 HuggingFace Blog 内容撰写。所有数据来源于公开的技术博客、论文和项目仓库。*
