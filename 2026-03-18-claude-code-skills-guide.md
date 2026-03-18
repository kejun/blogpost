# 构建 Claude Code 的经验：我们如何使用 Skills

**作者：** Thariq (@trq212) - Anthropic  
**发布时间：** 2026 年 3 月 18 日  
**原文链接：** https://x.com/trq212/status/2033949937936085378  
**推文数据：** 394.5 万查看 · 1.1 万喜欢 · 3.3 万书签 · 1,909 转帖

---

## 引言

Skills 已成为 Claude Code 中最常用的扩展点之一。它们灵活、易于制作、分发简单。

但这种灵活性也使得难以知道什么最有效。什么类型的 Skills 值得制作？写好 Skill 的秘诀是什么？什么时候应该与他人分享？

我们在 Anthropic 内部广泛使用 Claude Code 的 Skills，有数百个处于活跃使用状态。以下是我们关于使用 Skills 加速开发所学到的经验。

---

## 什么是 Skills？

如果你是 Skills 的新手，建议阅读[官方文档](https://code.claude.com/docs/en/skills)或观看我们关于 [Agent Skills 的新课程](https://anthropic.skilljar.com/introduction-to-agent-skills)。本文假设你已经对 Skills 有一定了解。

关于 Skills 的一个常见误解是它们"只是 markdown 文件"，但 Skills 最有趣的部分在于它们**不仅仅是文本文件**。它们是可以包含脚本、资产、数据等的文件夹，agent 可以发现、探索和操作这些内容。

在 Claude Code 中，Skills 还有[各种配置选项](https://code.claude.com/docs/en/skills#frontmatter-reference)，包括注册动态钩子。

我们发现 Claude Code 中一些最有趣的 Skills 创造性地使用了这些配置选项和文件夹结构。

---

## Skills 的类型

在编目我们所有的 Skills 后，我们注意到它们聚类为几个重复出现的类别。最好的 Skills 清晰地属于某一类；更令人困惑的则跨越几类。这不是一个详尽的列表，但它是思考你的组织是否缺少任何类别的好方法。

### 1. 库和 API 参考 (Library & API Reference)

解释如何正确使用库、CLI 或 SDK 的 Skills。这些既可以用于内部库，也可以用于 Claude Code 有时有问题的常用库。这些 Skills 通常包括参考代码片段文件夹和 Claude 编写脚本时要避免的陷阱列表。

**示例：**
- `billing-lib` — 你们内部的计费库：边缘情况、陷阱等
- `internal-platform-cli` — 内部 CLI 包装器的每个子命令，附带使用示例
- `frontend-design` — 让 Claude 更擅长你的设计系统

### 2. 产品验证 (Product Verification)

描述如何测试或验证代码正常工作的 Skills。这些通常与外部工具（如 playwright、tmux 等）配对进行验证。

验证 Skills 对于确保 Claude 的输出正确非常有用。值得让工程师花一周时间只是让你的验证 Skills 变得优秀。

考虑使用诸如让 Claude 录制其输出视频以便你可以准确看到它测试了什么，或在每个步骤对状态强制执行编程断言等技术。这些通常通过在 Skill 中包含各种脚本来完成。

**示例：**
- `signup-flow-driver` — 在无头浏览器中运行注册 → 邮箱验证 → 入职流程，在每个步骤都有断言状态的钩子
- `checkout-verifier` — 使用 Stripe 测试卡驱动结账 UI，验证发票实际进入正确状态
- `tmux-cli-driver` — 用于交互式 CLI 测试，当你需要验证的东西需要 TTY 时

### 3. 数据获取和分析 (Data Fetching & Analysis)

连接到你的数据和监控栈的 Skills。这些 Skills 可能包括使用凭证获取数据的库、特定仪表板 ID 等，以及常见工作流或获取数据方式的说明。

**示例：**
- `funnel-query` — "我连接哪些事件可以看到注册 → 激活 → 付费"以及实际拥有规范 user_id 的表
- `cohort-compare` — 比较两个队列的留存或转化，标记统计显著的差异，链接到细分定义
- `grafana` — 数据源 UID、集群名称、问题 → 仪表板查找表

### 4. 业务流程和团队自动化 (Business Process & Team Automation)

将重复性工作流自动化为一条命令的 Skills。这些 Skills 通常是指令相当简单，但可能对其他 Skills 或 MCP 有更复杂的依赖。对于这些 Skills，将先前结果保存在日志文件中可以帮助模型保持一致性并反思工作流的先前执行。

**示例：**
- `standup-post` — 聚合你的工单追踪器、GitHub 活动和先前的 Slack → 格式化的站会帖子，仅增量
- `create-<ticket-system>-ticket` — 强制执行模式（有效枚举值、必填字段）以及创建后工作流（通知审查者、Slack 中链接）
- `weekly-recap` — 合并的 PR + 关闭的工单 + 部署 → 格式化的回顾帖子

### 5. 代码脚手架和模板 (Code Scaffolding & Templates)

为代码库中的特定功能生成框架样板的 Skills。你可能会将这些 Skills 与可组合的脚本结合使用。当你的脚手架有无法纯粹通过代码覆盖的自然语言需求时，它们特别有用。

**示例：**
- `new-<framework>-workflow` — 用你的注释脚手架新的服务工作流/处理器
- `new-migration` — 你的迁移文件模板加上常见陷阱
- `create-app` — 新的内部应用，预先连接你的认证、日志记录和部署配置

### 6. 代码质量和审查 (Code Quality & Review)

在你的组织内强制执行代码质量并帮助审查代码的 Skills。这些可以包括确定性脚本或工具以获得最大的稳健性。你可能希望将这些 Skills 作为钩子的一部分或在 GitHub Action 中自动运行。

**示例：**
- `adversarial-review` — 生成新鲜视角的子代理来批评，实施修复，迭代直到发现退化为吹毛求疵
- `code-style` — 强制执行代码风格，特别是 Claude 默认做不好的风格
- `testing-practices` — 关于如何编写测试和测试什么的说明

### 7. CI/CD 和部署 (CI/CD & Deployment)

帮助你在代码库中获取、推送和部署代码的 Skills。这些 Skills 可能引用其他 Skills 来收集数据。

**示例：**
- `babysit-pr` — 监控 PR → 重试不稳定的 CI → 解决合并冲突 → 启用自动合并
- `deploy-<service>` — 构建 → 烟雾测试 → 逐渐流量滚动与错误率比较 → 回归时自动回滚
- `cherry-pick-prod` — 隔离的工作树 → cherry-pick → 冲突解决 → 带模板的 PR

### 8. 运行手册 (Runbooks)

接受症状（如 Slack 线程、警报或错误签名），遍历多工具调查，并生成结构化报告的 Skills。

**示例：**
- `<service>-debugging` — 映射症状 → 工具 → 查询模式，用于你的最高流量服务
- `oncall-runner` — 获取警报 → 检查常见嫌疑犯 → 格式化发现
- `log-correlator` — 给定请求 ID，从每个可能接触过它的系统拉取匹配的日志

### 9. 基础设施运营 (Infrastructure Operations)

执行例行维护和运营程序的 Skills — 其中一些涉及从防护栏中受益的破坏性操作。这些使工程师更容易在关键运营中遵循最佳实践。

**示例：**
- `<resource>-orphans` — 查找孤立的 pod/卷 → 发布到 Slack → 浸泡期 → 用户确认 → 级联清理
- `dependency-management` — 你组织的依赖审批工作流
- `cost-investigation` — "为什么我们的存储/出口账单飙升"，带有特定的存储桶和查询模式

---

## 制作 Skills 的技巧

一旦你决定了要制作的 Skill，如何编写它？以下是我们发现的一些最佳实践、技巧和诀窍。

我们最近还发布了 [Skill Creator](https://claude.com/blog/improving-skill-creator-test-measure-and-refine-agent-skills)，使在 Claude Code 中创建 Skills 变得更加容易。

### 不要陈述显而易见的内容

Claude Code 对你的代码库了解很多，Claude 对编码了解很多，包括许多默认观点。如果你发布的 Skill 主要是关于知识，试着专注于将 Claude 推出其正常思维方式的信息。

[frontend design skill](https://github.com/anthropics/skills/blob/main/skills/frontend-design/SKILL.md) 是一个很好的例子 — 它由 Anthropic 的一位工程师通过与顾客迭代改进 Claude 的设计品味、避免经典模式（如 Inter 字体和紫色渐变）而构建。

### 建立陷阱部分 (Gotchas Section)

任何 Skill 中信号最高的内容是 Gotchas 部分。这些部分应该从 Claude 使用你的 Skill 时遇到的常见故障点建立起来。理想情况下，你会随时间更新你的 Skill 以捕获这些陷阱。

### 使用文件系统和渐进式披露

就像我们之前说的，Skill 是一个文件夹，而不仅仅是一个 markdown 文件。你应该将整个文件系统视为一种上下文工程和渐进式披露的形式。告诉 Claude 你的 Skill 中有哪些文件，它会在适当的时候阅读它们。

渐进式披露的最简单形式是指向其他 markdown 文件供 Claude 使用。例如，你可以将详细的函数签名和使用示例拆分到 `references/api.md` 中。

另一个例子：如果你的最终输出是 markdown 文件，你可以在 `assets/` 中包含一个模板文件供复制使用。

你可以有参考文件夹、脚本、示例等，帮助 Claude 更有效地工作。

### 避免过度限制 Claude

Claude 通常会尝试坚持你的指令，因为 Skills 是如此可重用，你会希望小心不要过于具体。给 Claude 它需要的信息，但给它适应情况的灵活性。

### 仔细考虑设置

一些 Skills 可能需要用户设置上下文。例如，如果你要制作一个将站会帖子发布到 Slack 的 Skill，你可能希望 Claude 询问发布到哪个 Slack 频道。

这样做的一个好模式是在 Skill 目录中的 `config.json` 文件中存储这些设置信息，如上面的示例所示。如果配置未设置，agent 可以询问用户信息。

如果你希望 agent 提出结构化的多项选择题，你可以指示 Claude 使用 AskUserQuestion 工具。

### 描述字段是给模型看的

当 Claude Code 启动会话时，它会构建每个可用 Skill 及其描述的列表。这是 Claude 扫描以决定"是否有针对此请求的 Skill？"的内容。这意味着描述字段不是摘要 — 它是**何时触发此 PR 的描述**。

### 内存和存储数据

一些 Skills 可以通过在其中存储数据来包含某种形式的内存。你可以将数据存储在任何地方，从简单的仅追加文本日志文件或 JSON 文件，到复杂的 SQLite 数据库。

例如，`standup-post` Skill 可能会保留一个 `standups.log`，记录它写的每个帖子，这意味着下次运行它时，Claude 会读取它自己的历史，并可以告诉从昨天开始有什么变化。

存储在 Skill 目录中的数据可能会在你升级 Skill 时被删除，因此你应该将其存储在稳定的文件夹中。截至目前，我们提供 `${CLAUDE_PLUGIN_DATA}` 作为每个插件存储数据的稳定文件夹。

### 存储脚本并生成代码

你能给 Claude 的最强大工具之一是代码。给 Claude 脚本和库让 Claude 将其回合花在组合上，决定下一步做什么，而不是重构样板代码。

例如，在你的数据科学 Skill 中，你可能有一个从事件源获取数据的函数库。为了让 Claude 进行复杂分析，你可以给它一组辅助函数。

Claude 可以即时生成脚本来组合这些功能，为诸如"周二发生了什么？"之类的提示进行更高级的分析。

### 按需钩子 (On Demand Hooks)

Skills 可以包含仅在调用 Skill 时激活并在会话期间持续的钩子。用于你不想一直运行但有时非常有用的更固执己见的钩子。

**示例：**
- `/careful` — 通过 PreToolUse 匹配器在 Bash 上阻止 `rm -rf`、`DROP TABLE`、强制推送、`kubectl delete`。你只想在知道要接触生产环境时使用它 — 一直开启会让你发疯
- `/freeze` — 阻止特定目录外的任何编辑/写入。调试时很有用："我想添加日志，但我一直不小心'修复'不相关的东西"

---

## 分发 Skills

Skills 的最大好处之一是你可以与团队的其他人分享它们。

与他人分享 Skills 有两种方式：

1. **将你的 Skills 检入你的仓库**（在 `./.claude/skills` 下）
2. **制作一个插件**，拥有一个 Claude Code 插件市场，用户可以上传和安装插件（在[文档](https://code.claude.com/docs/en/plugin-marketplaces)中阅读更多）

对于在相对较少的仓库中工作的较小团队，将 Skills 检入仓库效果很好。但每个检入的 Skill 也会为模型的上下文增加一点。随着规模扩大，内部插件市场允许你分发 Skills 并让你的团队决定安装哪些。

### 管理市场

如何决定哪些 Skills 进入市场？人们如何提交它们？

我们没有集中团队来决定；相反，我们尝试有机地找到最有用的 Skills。如果你有一个想要人们尝试的 Skill，你可以将其上传到 GitHub 中的沙盒文件夹，并在 Slack 或其他论坛中指向它。

一旦 Skill 获得关注（由 Skill 所有者决定），他们可以提交 PR 将其移入市场。

警告一下，创建糟糕或冗余的 Skills 可能很容易，所以在发布前确保你有某种策划方法很重要。

### 组合 Skills

你可能希望有相互依赖的 Skills。例如，你可能有一个上传文件的文件上传 Skill，以及一个制作 CSV 并上传它的 CSV 生成 Skill。这种依赖管理尚未原生构建到市场或 Skills 中，但你可以按名称引用其他 Skills，如果安装了它们，模型将调用它们。

### 衡量 Skills

为了了解 Skill 的表现，我们使用 PreToolUse 钩子让我们在公司内记录 Skill 使用情况（[示例代码](https://gist.github.com/ThariqS/24defad423d701746e23dc19aace4de5)）。这意味着我们可以找到流行或与我们的预期相比触发不足的 Skills。

---

## 结论

Skills 是 agent 极其强大、灵活的工具，但仍然处于早期阶段，我们都在 figuring out 如何最好地使用它们。

更多地将其视为有用技巧的百宝箱，而不是权威指南。理解 Skills 的最好方法是开始、实验，看看什么对你有效。我们的大多数 Skills 都始于几行和一个陷阱，随着 Claude 遇到新的边缘情况，人们不断添加内容而变得更好。

希望这对你有帮助，如有任何问题请告诉我。

---

*翻译整理于 2026-03-18*
