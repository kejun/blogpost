# 每个 ADK 开发者都应了解的 5 个 Agent Skill 设计模式

**来源：** Google Cloud Tech (@GoogleCloudTech)  
**发布时间：** 2026 年 3 月 18 日  
**原文链接：** https://x.com/googlecloudtech/status/2033953579824758855  
**作者：** @Saboo_Shubham_ 和 @lavinigam

---

## 引言

当涉及到 `SKILL.md` 时，开发者倾向于纠结格式——把 YAML 写对、构建目录结构、遵循规范。但随着超过 30 个 agent 工具（如 Claude Code、Gemini CLI 和 Cursor）标准化为同一布局，格式问题实际上已经过时。

现在的挑战是**内容设计**。规范解释了如何打包 skill，但对如何组织内部逻辑**毫无指导**。例如，一个封装 FastAPI 约定的 skill 与一个四步文档流水线的 skill 运作方式完全不同，尽管它们的 `SKILL.md` 文件外表看起来一样。

通过研究生态系统中 skill 的构建方式——从 Anthropic 的仓库到 Vercel 和 Google 的内部指南——我们发现了五个重复出现的设计模式，可以帮助开发者构建 agent。

本文涵盖每个模式的可用 ADK 代码：

1. **Tool Wrapper（工具封装器）：** 让你的 agent 立即成为任何库的专家
2. **Generator（生成器）：** 从可复用模板生成结构化文档
3. **Reviewer（审查器）：** 按严重程度对代码进行清单评分
4. **Inversion（反转）：** agent 在行动前采访你
5. **Pipeline（流水线）：** 用检查点强制执行严格的多步工作流

---

## 模式 1：Tool Wrapper（工具封装器）

Tool Wrapper 为你的 agent 提供特定库的按需上下文。你不是将 API 约定硬编码到系统提示词中，而是将它们打包到 skill 中。你的 agent 只在实际使用该技术时加载此上下文。

这是最简单的实现模式。`SKILL.md` 文件监听用户提示词中的特定库关键词，从 `references/` 目录动态加载内部文档，并将这些规则作为绝对真理应用。这正是你将团队内部编码指南或特定框架最佳实践直接分发到开发者工作流中的机制。

### 示例：FastAPI Tool Wrapper

这是一个教 agent 如何编写 FastAPI 代码的 Tool Wrapper 示例。注意指令如何明确告诉 agent 仅在开始审查或编写代码时加载 `conventions.md` 文件：

```yaml
# skills/api-expert/SKILL.md
---
name: api-expert
description: FastAPI development best practices and conventions. Use when building, reviewing, or debugging FastAPI applications, REST APIs, or Pydantic models.
metadata:
  pattern: tool-wrapper
  domain: fastapi
---

You are an expert in FastAPI development. Apply these conventions to the user's code or question.

## Core Conventions

Load 'references/conventions.md' for the complete list of FastAPI best practices.

## When Reviewing Code

1. Load the conventions reference
2. Check the user's code against each convention
3. For each violation, cite the specific rule and suggest the fix

## When Writing Code

1. Load the conventions reference
2. Follow every convention exactly
3. Add type annotations to all function signatures
4. Use Annotated style for dependency injection
```

---

## 模式 2：Generator（生成器）

Tool Wrapper 应用知识，而 Generator 强制执行一致的输出。如果你苦恼于 agent 每次运行生成不同的文档结构，Generator 通过编排填空过程来解决这个问题。

它利用两个可选目录：`assets/` 保存输出模板，`references/` 保存风格指南。指令充当项目经理。它们告诉 agent 加载模板、阅读风格指南、询问用户缺失的变量，然后填充文档。这适用于生成可预测的 API 文档、标准化提交消息或搭建项目架构。

### 示例：技术报告生成器

在这个技术报告生成器示例中，skill 文件不包含实际布局或语法规则。它只是协调这些资产的检索，并强制 agent 逐步执行：

```yaml
# skills/report-generator/SKILL.md
---
name: report-generator
description: Generates structured technical reports in Markdown. Use when the user asks to write, create, or draft a report, summary, or analysis document.
metadata:
  pattern: generator
  output-format: markdown
---

You are a technical report generator. Follow these steps exactly:

Step 1: Load 'references/style-guide.md' for tone and formatting rules.

Step 2: Load 'assets/report-template.md' for the required output structure.

Step 3: Ask the user for any missing information needed to fill the template:
- Topic or subject
- Key findings or data points
- Target audience (technical, executive, general)

Step 4: Fill the template following the style guide rules. Every section in the template must be present in the output.

Step 5: Return the completed report as a single Markdown document.
```

---

## 模式 3：Reviewer（审查器）

Reviewer 模式将**检查什么**与**如何检查**分开。你不是写一个长的系统提示词详细说明每个代码异味，而是将模块化的评分标准存储在 `references/review-checklist.md` 文件中。

当用户提交代码时，agent 加载此清单并系统地评分，按严重程度分组发现。如果你将 Python 风格清单换成 OWASP 安全清单，使用完全相同的 skill 基础设施就能获得完全不同的专业审计。这是自动化 PR 审查或在人类查看代码前捕获漏洞的有效方法。

### 示例：代码审查器

以下代码审查器 skill 展示了这种分离。指令保持静态，但 agent 动态加载特定的审查标准，并强制基于严重程度的结构化输出：

```yaml
# skills/code-reviewer/SKILL.md
---
name: code-reviewer
description: Reviews Python code for quality, style, and common bugs. Use when the user submits code for review, asks for feedback on their code, or wants a code audit.
metadata:
  pattern: reviewer
  severity-levels: error,warning,info
---

You are a Python code reviewer. Follow this review protocol exactly:

Step 1: Load 'references/review-checklist.md' for the complete review criteria.

Step 2: Read the user's code carefully. Understand its purpose before critiquing.

Step 3: Apply each rule from the checklist to the code. For every violation found:
- Note the line number (or approximate location)
- Classify severity: error (must fix), warning (should fix), info (consider)
- Explain WHY it's a problem, not just WHAT is wrong
- Suggest a specific fix with corrected code

Step 4: Produce a structured review with these sections:
- **Summary**: What the code does, overall quality assessment
- **Findings**: Grouped by severity (errors first, then warnings, then info)
- **Score**: Rate 1-10 with brief justification
- **Top 3 Recommendations**: The most impactful improvements
```

---

## 模式 4：Inversion（反转）

Agent 天生想要立即猜测和生成。Inversion 模式翻转了这个动态。不是用户驱动提示词、agent 执行，而是 agent 充当面试官。

Inversion 依赖明确的、不可协商的门控指令（如"在所有阶段完成前不要开始构建"）来强制 agent 先收集上下文。它按顺序提出结构化问题，在进入下一阶段前等待你的回答。agent 在完整了解你的需求和部署约束前，拒绝合成最终输出。

### 示例：项目规划器

看看这个 project planner skill。关键元素是严格的分相和明确的门控提示词，在收集所有用户回答前阻止 agent 合成最终计划：

```yaml
# skills/project-planner/SKILL.md
---
name: project-planner
description: Plans a new software project by gathering requirements through structured questions before producing a plan. Use when the user says "I want to build", "help me plan", "design a system", or "start a new project".
metadata:
  pattern: inversion
  interaction: multi-turn
---

You are conducting a structured requirements interview. DO NOT start building or designing until all phases are complete.

## Phase 1 — Problem Discovery (ask one question at a time, wait for each answer)

Ask these questions in order. Do not skip any.
- Q1: "What problem does this project solve for its users?"
- Q2: "Who are the primary users? What is their technical level?"
- Q3: "What is the expected scale? (users per day, data volume, request rate)"

## Phase 2 — Technical Constraints (only after Phase 1 is fully answered)

- Q4: "What deployment environment will you use?"
- Q5: "Do you have any technology stack requirements or preferences?"
- Q6: "What are the non-negotiable requirements? (latency, uptime, compliance, budget)"

## Phase 3 — Synthesis (only after all questions are answered)

1. Load 'assets/plan-template.md' for the output format
2. Fill in every section of the template using the gathered requirements
3. Present the completed plan to the user
4. Ask: "Does this plan accurately capture your requirements? What would you change?"
5. Iterate on feedback until the user confirms
```

---

## 模式 5：Pipeline（流水线）

对于复杂任务，你不能承受跳过步骤或忽略指令。Pipeline 模式强制执行严格的顺序工作流，带有硬性检查点。

指令本身充当工作流定义。通过实现明确的钻石门条件（如要求在进入最终组装前用户批准），Pipeline 确保 agent 不能绕过复杂任务并呈现未验证的最终结果。

此模式利用所有可选目录，仅在需要的特定步骤拉取不同的参考文件和模板，保持上下文窗口干净。

### 示例：文档流水线

在这个文档流水线示例中，注意明确的门条件。agent 被明确禁止在进入组装阶段前，用户确认上一步生成的 docstring：

```yaml
# skills/doc-pipeline/SKILL.md
---
name: doc-pipeline
description: Generates API documentation from Python source code through a multi-step pipeline. Use when the user asks to document a module, generate API docs, or create documentation from code.
metadata:
  pattern: pipeline
  steps: "4"
---

You are running a documentation generation pipeline. Execute each step in order. Do NOT skip steps or proceed if a step fails.

## Step 1 — Parse & Inventory

Analyze the user's Python code to extract all public classes, functions, and constants. Present the inventory as a checklist. Ask: "Is this the complete public API you want documented?"

## Step 2 — Generate Docstrings

For each function lacking a docstring:
- Load 'references/docstring-style.md' for the required format
- Generate a docstring following the style guide exactly
- Present each generated docstring for user approval

Do NOT proceed to Step 3 until the user confirms.

## Step 3 — Assemble Documentation

Load 'assets/api-doc-template.md' for the output structure. Compile all classes, functions, and docstrings into a single API reference document.

## Step 4 — Quality Check

Review against 'references/quality-checklist.md':
- Every public symbol documented
- Every parameter has a type and description
- At least one usage example per function

Report results. Fix issues before presenting the final document.
```

---

## 选择正确的 Agent Skill 模式

每个模式回答不同的问题。使用此决策树找到适合你用例的模式：

| 如果你想... | 使用模式 |
|------------|---------|
| 教 agent 关于特定库或框架的知识 | Tool Wrapper |
| 生成具有统一结构的文档 | Generator |
| 根据清单审计代码或内容 | Reviewer |
| 在 agent 行动前收集需求 | Inversion |
| 强制执行多步骤、有序的工作流 | Pipeline |

---

## 模式可以组合

这些模式不是互斥的。它们可以组合。

- Pipeline skill 可以在最后包含 Reviewer 步骤来复查自己的工作
- Generator 可以在开始时依赖 Inversion 来收集必要的变量，然后填充模板
- 得益于 ADK 的 `SkillToolset` 和渐进式披露，你的 agent 只在运行时将上下文 token 花费在需要的确切模式上

**停止尝试将复杂脆弱的指令塞进单个系统提示词。** 分解你的工作流，应用正确的结构模式，构建可靠的 agent。

---

## 今天就开始

Agent Skills 规范是开源的，并在 ADK 中原生支持。你已经知道如何打包格式。现在你知道如何设计内容。

使用 [Google Agent Development Kit](https://google.github.io/adk-docs/) 构建更智能的 agent。

---

**推文数据：** 44.8 万查看 · 1,718 喜欢 · 3,293 书签 · 419 转帖 · 21 回复

*翻译整理于 2026-03-18*
