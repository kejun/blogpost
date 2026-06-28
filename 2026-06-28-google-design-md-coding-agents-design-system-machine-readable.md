# Google DESIGN.md 深度解析：当设计系统变成"Agent 可读"——AI 编码时代的视觉规范协议

**文档日期：** 2026 年 6 月 28 日  
**标签：** AI Agent, DESIGN.md, 开发者工具, 设计系统, 设计 Token, 编码 Agent, Google Labs, 前端工程

---

## 一、引子：你的 AI 编码 Agent 根本不懂你的设计

> "An agent that reads this file will produce a UI with deep ink headlines in Public Sans, a warm limestone background, and Boston Clay call-to-action buttons."

— Google Labs, DESIGN.md README

这句话看似平淡，实际上揭示了一个 2026 年所有前端开发者都在面对的残酷现实：**AI 编码 Agent 的视觉输出质量，与设计系统的"可机器理解程度"直接相关。**

2026 年 6 月，Google Labs 在 GitHub 上开源了 **DESIGN.md**——一个用纯文本格式描述完整设计系统的规范文件。短短几天内，这个项目冲到 GitHub Trending 前列，**总星数突破 22,320，单日新增 1,541 星**，成为近期增长最快的开发者工具项目之一。

为什么一个"设计规范格式"能引发如此大的关注？因为它回答了一个所有人都遇到过但没人正式解决的问题：

**当 Claude Code、Cursor、OpenCode 这些 AI 编码 Agent 替我们写 UI 时，怎么让它们"理解"你的品牌？**

---

## 二、问题的根源：设计系统与 AI 编码之间的"翻译鸿沟"

### 2.1 Figma 到代码的千年难题

设计系统从来都不缺格式。Figma Variables、Style Dictionary、Tokens Studio、W3C Design Tokens Format Module——每个都有完整的生态。但它们有一个共同的前提假设：**消费者是人类开发者**。

人类开发者拿到设计系统后，会做这些工作：

- 理解品牌调性（"这个产品应该是活泼的还是严肃的？"）
- 推断缺失场景（"设计稿里没写 hover 状态，但我应该知道要加一个"）
- 做视觉判断（"这个间距看起来太紧了，我调大一点"）
- 跨组件推理（"如果按钮是圆角 8px，那卡片也应该是"）

AI 编码 Agent 做不到这些——至少，在设计系统以 Figma 文件或 PDF 形式存在时做不到。

### 2.2 当前的"解决方案"及其失败模式

在实践中，团队用以下几种方式让 Agent 遵守设计规范：

| 方法 | 工作原理 | 失败模式 |
|------|---------|---------|
| Prompt 里写描述 | "用 Material Design 3 风格，主色 #1A1C1E" | 上下文窗口有限，描述不完整，Agent 经常遗忘或误解 |
| 截图 + 视觉分析 | 给 Agent 看设计稿截图 | Agent 能模仿表面样式，但缺乏系统性理解，每个组件都要重新"看图" |
| Tailwind 配置 | 把设计 Token 转成 Tailwind config | 只能解决值的问题，解决不了"为什么"的问题 |
| 组件库封装 | 提供封装好的 React 组件 | 灵活性差，Agent 遇到新场景时无法正确组合 |

**根本问题是：这些方法都只传递了"值"，没有传递"意图"。**

DESIGN.md 的核心创新就在于它同时解决了两个层面的问题：
1. **机器可读的 Token 层**（YAML front matter）
2. **人类可读的意图层**（Markdown 正文）

---

## 三、DESIGN.md 的技术架构：双层结构的设计哲学

### 3.1 文件结构：一个文件，两层语义

```markdown
---
version: alpha
name: Heritage
colors:
  primary: "#1A1C1E"
  secondary: "#6C7278"
  tertiary: "#B8422E"
  neutral: "#F7F5F2"
typography:
  h1:
    fontFamily: Public Sans
    fontSize: 3rem
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: -0.02em
  body-md:
    fontFamily: Public Sans
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.6
  label-caps:
    fontFamily: Space Grotesk
    fontSize: 0.75rem
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0.1em
rounded:
  sm: 4px
  md: 8px
spacing:
  sm: 8px
  md: 16px
---

## Overview

Architectural Minimalism meets Journalistic Gravitas. The UI evokes a
premium matte finish — a high-end broadsheet or contemporary gallery.

## Colors

The palette is rooted in high-contrast neutrals and a single accent color.

- **Primary (#1A1C1E):** Deep ink for headlines and core text.
- **Tertiary (#B8422E):** "Boston Clay" — the sole driver for interaction.
```

这个结构看似简单，但每一层都有明确的设计意图：

**YAML Front Matter（机器层）：**
- 结构化、可解析、可验证
- 支持 Token 引用语法 `{colors.primary}`
- 可直接转换为 tokens.json、Tailwind config、Figma Variables
- Agent 可以通过 YAML 解析器精确读取值

**Markdown Body（人类/意图层）：**
- 描述品牌的"性格"（Architectural Minimalism、Journalistic Gravitas）
- 解释 Token 的语义用途（"sole driver for interaction"）
- 给 Agent 提供推理上下文（当 Token 不够用时，Agent 可以参考意图层做推断）

### 3.2 Token 引用系统：设计系统的"指针"

DESIGN.md 借鉴了 W3C Design Tokens Format 的 `{path.to.token}` 语法，实现了组件级的 Token 组合：

```yaml
components:
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "{colors.tertiary-container}"
```

这个设计看似简单，但实际上解决了 Agent 编码中最常见的一个问题：**不一致性**。

当 Agent 知道 `button-primary` 的 `backgroundColor` 引用了 `{colors.tertiary}`，它就能在修改主题色时自动更新所有引用该 Token 的组件——这正是人类设计师做设计系统时的思维方式。

### 3.3 章节结构与 Agent 理解路径

DESIGN.md 定义了固定的章节顺序，这不仅仅是格式约定，而是**Agent 的理解路径**：

| 章节 | 作用 | Agent 理解目标 |
|------|------|---------------|
| Overview | 品牌调性 | "这个产品应该给人什么感觉？" |
| Colors | 色彩系统 | "用什么颜色表达什么含义？" |
| Typography | 字体层级 | "文字如何建立信息层次？" |
| Layout | 布局与间距 | "元素之间如何呼吸？" |
| Elevation & Depth | 层级关系 | "什么是浮起的，什么是沉下去的？" |
| Shapes | 形状语义 | "圆角传达什么感觉？" |
| Components | 组件规范 | "按钮、卡片、输入框长什么样？" |
| Do's and Don'ts | 设计约束 | "什么绝对不能做？" |

这个顺序不是随意的。它模拟了一个人类设计师学习一个设计系统的认知过程：先从整体感觉开始，然后逐层深入到具体组件。**DESIGN.md 实际上是把设计师的认知路径"编码"成了 Agent 可以执行的结构。**

---

## 四、CLI 工具链：验证、Diff 和 Agent 集成

DESIGN.md 不只定义格式，还提供了一套完整的 CLI 工具链：

### 4.1 Lint：设计系统的类型检查

```bash
npx @google/design.md lint DESIGN.md
```

输出结构化 JSON，包含错误、警告和信息：

```json
{
  "findings": [
    {
      "severity": "warning",
      "path": "components.button-primary",
      "message": "textColor (#ffffff) on backgroundColor (#1A1C1E) has contrast ratio 15.42:1 — passes WCAG AA."
    }
  ],
  "summary": { "errors": 0, "warnings": 1, "info": 1 }
}
```

**这个 lint 工具的意义远不止"检查格式是否正确"。** 它内置了 WCAG 对比度检查——这意味着 Agent 在生成 UI 时可以自动验证可访问性。想象一下：Agent 生成了一个按钮，lint 工具立即告诉它"这个配色在 WCAG AA 下不通过"，Agent 自动修正。这形成了一个**设计质量的自动反馈循环**。

### 4.2 Diff：设计系统的版本控制

```bash
npx @google/design.md diff DESIGN.md DESIGN-v2.md
```

```json
{
  "tokens": {
    "colors": { "added": ["accent"], "removed": [], "modified": ["tertiary"] },
    "typography": { "added": [], "removed": [], "modified": [] }
  },
  "regression": false
}
```

Diff 工具能做 Token 级别的变更检测和回归分析。这对 Agent 驱动的开发工作流至关重要：

- Agent 修改设计后，Diff 可以精确告知改了什么
- 可以做回归检测（"你把按钮圆角从 8px 改成了 4px，这违反了品牌规范"）
- 可以和 Git 集成，在 PR 中自动生成设计变更报告

### 4.3 设计系统转换管道

DESIGN.md 的 Token 可以直接转换为：

```
DESIGN.md (源文件)
    │
    ├──→ tokens.json (W3C Design Tokens 格式)
    ├──→ tailwind.config.js (Tailwind 主题)
    ├──→ figma.variables (Figma Variables)
    └──→ CSS Custom Properties (:root { --color-primary: ... })
```

这意味着一个团队可以**只维护一个 DESIGN.md 文件**，然后自动同步到所有工具链中。对于 AI 编码 Agent 来说，这消除了"设计稿和代码不一致"这个最大的质量风险。

---

## 五、与现有设计系统方案的对比分析

### 5.1 横向对比

| 维度 | Figma Variables | Style Dictionary | W3C Tokens | DESIGN.md |
|------|----------------|-----------------|------------|-----------|
| 格式 | 二进制/专有 | JSON | JSON | Markdown + YAML |
| 人类可读性 | 差（需要 Figma 打开） | 中（JSON 对人不友好） | 差 | **优秀** |
| Agent 可读性 | 差（需 API） | 中 | 中 | **优秀** |
| 意图传达 | 无 | 无 | 无 | **有（Markdown 正文）** |
| 版本控制友好 | 差 | 好 | 好 | **极好** |
| Lint/验证 | Figma 内置 | 需自定义 | 需自定义 | **内置 CLI** |
| Diff 支持 | 差 | 文本 Diff | 文本 Diff | **语义 Diff** |
| 生态转换 | 需插件 | 可转换 | 需转换层 | **一键转换** |

### 5.2 核心差异：为什么 Markdown + YAML 赢了

DESIGN.md 选择 Markdown + YAML 不是技术上的妥协，而是一个深思熟虑的策略。

**Git 友好的纯文本**意味着：
- 每一行变更都可以 Code Review
- PR 中可以直接看到设计变更
- Git Blame 可以追踪设计决策的演进
- Agent 可以用普通的文件读写操作修改设计系统

**Markdown 正文**解决了所有纯 Token 方案都无法解决的问题：**意图传递**。

当 DESIGN.md 写下：

> "Tertiary (#B8422E): 'Boston Clay' — the sole driver for interaction, used exclusively for primary actions and critical highlights."

Agent 不仅知道了颜色值，还知道了：
- 这个颜色叫什么（"Boston Clay"——品牌命名）
- 它的使用场景（"primary actions and critical highlights"）
- 它的排他性约束（"sole driver"——不要用其他颜色做交互）

**这些语义信息在纯 JSON 格式的 Token 文件中是不可能表达的。** 而 Agent 恰恰最需要这些信息来做正确的设计决策。

---

## 六、DESIGN.md 在 AI 编码 Agent 工作流中的落地场景

### 6.1 场景一：Agent 从 DESIGN.md 生成完整 UI

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  DESIGN.md   │────→│ Claude Code  │────→│  React 组件   │
│ (设计系统)    │     │ (编码 Agent)  │     │ (符合规范)    │
└──────────────┘     └──────────────┘     └──────────────┘
```

工作流：
1. 在仓库根目录放置 DESIGN.md
2. 告诉 Agent："根据 DESIGN.md 实现登录页面"
3. Agent 解析 YAML Token，读取 Markdown 意图
4. 生成符合设计规范的 React/Vue 组件
5. 运行 `npx @google/design.md lint` 自动验证

### 6.2 场景二：Agent 自动更新设计系统

```
用户 → "把品牌色改成深蓝色"
       │
       ▼
┌──────────────────────────────┐
│ Agent 读取 DESIGN.md          │
│ 修改 colors.primary           │
│ 更新所有 Token 引用            │
│ 运行 lint 验证对比度           │
│ 运行 diff 生成变更报告          │
│ git commit -m "更新品牌色"    │
└──────────────────────────────┘
```

这是 DESIGN.md 最强大的能力——**Agent 可以安全地修改设计系统本身**，因为：
- YAML 是结构化的，修改是精确的
- lint 工具可以验证修改后的合规性
- diff 工具可以生成语义化的变更报告
- 纯文本格式天然支持 Git 版本控制

### 6.3 场景三：多 Agent 协作的设计-开发管线

```
设计 Agent ──→ DESIGN.md ──→ 开发 Agent ──→ 代码
    │                             │
    │ 更新设计                      │ 解析设计
    ▼                             ▼
 DESIGN.md (v2)               组件库 (更新)
```

DESIGN.md 可以作为设计和开发之间的**单一事实来源**（Single Source of Truth）。设计 Agent（如可以输出设计系统的 AI）生成 DESIGN.md，开发 Agent 解析 DESIGN.md 生成代码。两者之间不需要 Figma 账号、不需要截图、不需要会议——只需要一个文本文件。

---

## 七、深层分析：DESIGN.md 代表了什么范式转移

### 7.1 从"文档"到"协议"

传统设计系统的文档（Style Guide、Brand Book）是给人类阅读的。它们精美、详细、有大量的视觉示例——但 Agent 无法从中提取可执行的规范。

DESIGN.md 把设计系统从"文档"变成了"协议"。协议的特点：
- **双向**：人和 Agent 都可以读写
- **可验证**：lint 工具确保合规
- **可版本化**：Diff 工具追踪变更
- **可转换**：一键输出到各种格式

这意味着设计系统不再是"挂在墙上的画"，而是**可以参与开发循环的活文档**。

### 7.2 "意图层"是 Agent 时代的设计系统核心资产

回顾 3.1 节的双层结构，YAML Token 层解决的是"值"的问题，但 Markdown 意图层解决的才是"理解"的问题。

在 AI 编码时代，意图层的价值甚至超过 Token 层：

| 场景 | 仅有 Token | Token + 意图 |
|------|-----------|-------------|
| Agent 需要新增一个未定义的组件 | 猜测 | 参考意图推断 |
| 品牌调性调整 | 手动改所有值 | 改意图描述，Agent 自动推导 |
| 设计评审 | 只能看值对不对 | 可以看值是否符合意图 |
| 新成员 Onboarding | 读 JSON + 猜含义 | 读 Markdown 就能理解 |

**未来最有价值的设计系统资产，可能不再是 Figma 文件，而是 DESIGN.md 的意图描述。**

### 7.3 DESIGN.md 与 AGENTS.md 的类比

如果你用过 OpenClaw、Claude Code 或 Cursor，你可能熟悉 AGENTS.md——一个用 Markdown 告诉 AI Agent 如何工作的文件。

DESIGN.md 本质上就是 **"AGENTS.md for Design"**：

| | AGENTS.md | DESIGN.md |
|---|---------|-----------|
| 目标 | 让 Agent 理解项目的工作方式 | 让 Agent 理解产品的视觉语言 |
| 格式 | Markdown | Markdown + YAML |
| 内容 | 工作流程、工具、约定 | 颜色、字体、组件、约束 |
| 消费者 | 编码 Agent | 编码 Agent + 设计师 |
| 效果 | Agent 写出符合项目约定的代码 | Agent 产出符合品牌规范的 UI |

这不是巧合。2026 年的趋势是：**一切需要 Agent 理解的东西，最终都会变成 Markdown。** 因为 Markdown 是目前人类可读性和机器可解析性之间的最佳平衡点。

---

## 八、批判性视角：DESIGN.md 的局限与挑战

### 8.1 复杂设计系统的表达能力

DESIGN.md 目前覆盖的是基础的设计 Token（颜色、字体、间距、圆角、组件）。但对于以下场景，它的表达能力还不明确：

- **动效系统**（动画曲线、时长、物理效果）
- **响应式断点**（不同屏幕尺寸的适配规则）
- **国际化/本地化**（不同语言的排版差异）
- **无障碍规范的深度集成**（不只是对比度，还有焦点管理、屏幕阅读器等）
- **Design Token 的计算与派生**（如 `color-mix()`、透明度层级）

Google 的 spec 目前是 `alpha` 版本，这些问题在成熟后可能会通过扩展章节或嵌套 Token 来解决。

### 8.2 设计师的接受度

DESIGN.md 的目标用户是"人 + Agent"，但设计师这个群体对纯文本设计规范的接受度可能不如开发者。Figma 的可视化界面是设计师的核心工作流，让他们写 YAML 和 Markdown 可能有阻力。

不过，考虑到 DESIGN.md 支持与 Figma Variables 的双向转换，**设计师可以继续用 Figma 工作，转换工具自动生成 DESIGN.md**——这需要工具链的成熟。

### 8.3 "意图层"的质量依赖人类

DESIGN.md 的 Markdown 部分需要人类设计师写出高质量的意图描述。如果意图描述模糊或不准确，Agent 的推断就会出错。这实际上把设计系统的维护责任从"画好 Figma"变成了"写好 Markdown"——对很多团队来说这是一个文化转变。

---

## 九、实际落地：如何在你自己的项目中启用 DESIGN.md

### 9.1 最小启动方案

```bash
# 1. 安装 CLI
npm install @google/design.md

# 2. 在仓库根目录创建 DESIGN.md
touch DESIGN.md

# 3. 用你的设计 Token 填充 YAML front matter
# 4. 用 Markdown 写下你的品牌意图

# 5. 验证
npx @google/design.md lint DESIGN.md
```

### 9.2 与 AI 编码 Agent 集成

在 AGENTS.md（或 Cursor 的 `.cursorrules`、Claude Code 的 CLAUDE.md）中添加：

```markdown
## 设计规范
本项目的设计系统定义在根目录的 DESIGN.md 文件中。
所有 UI 组件必须严格遵循 DESIGN.md 中定义的 Token 和约束。
生成新组件前，先读取 DESIGN.md 确保理解品牌意图。
完成后运行 `npx @google/design.md lint DESIGN.md` 验证合规。
```

### 9.3 CI/CD 集成

在 GitHub Actions 中添加设计系统验证：

```yaml
- name: Lint Design System
  run: npx @google/design.md lint DESIGN.md

- name: Check Design Regressions
  if: github.event_name == 'pull_request'
  run: |
    npx @google/design.md diff origin/main:DESIGN.md DESIGN.md
    # 如果有 breaking token changes，fail the build
```

---

## 十、结论：设计系统的 Agent 原生时代

DESIGN.md 的意义不仅仅是一个新的文件格式。它标志着一个更深层的转变：

**设计系统正在从"给人看的文档"变成"人和 Agent 共享的协议"。**

在这个新范式中：
- **设计师**不再只产出 Figma 文件，还要产出 Agent 可读的设计意图
- **开发者**不再手动"翻译"设计稿，而是让 Agent 直接解析设计规范
- **Agent** 不再是"看图猜样式"的黑盒，而是"读取协议、执行规范"的可靠工具
- **团队**不再需要反复开会对齐设计实现，因为单一事实来源（DESIGN.md）可以自动验证

DESIGN.md 目前是 `alpha` 版本，功能还不完整。但它的方向是正确的——而且 Google Labs 把它放在开源社区中迭代，说明他们意识到了这个领域的竞争会非常激烈。

对于前端工程师来说，现在最该做的事是：**在你的下一个 AI 编码项目中，尝试用 DESIGN.md 替代设计稿截图。然后看看 Agent 给你的产出质量，是否比之前提高了一个量级。**

---

## 参考链接

- [Google Labs DESIGN.md 仓库](https://github.com/google-labs-code/design.md)
- [DESIGN.md 完整规范 (spec.md)](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md)
- [W3C Design Tokens Format Module](https://www.designtokens.org/)
- [HN 讨论：AI learns the "dark art" of RFIC design](https://news.ycombinator.com/)（同期热点参考）
- [GitHub Trending 实时数据](https://github.com/trending)（截至 2026-06-28）
