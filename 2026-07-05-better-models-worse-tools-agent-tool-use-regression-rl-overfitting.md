# 越强越脆弱：当 SOTA 模型开始"搞砸"工具调用——Better Models, Worse Tools 的技术深潜

> **摘要：** 2026 年 7 月初，两件看似独立的事件同时引爆了开发者社区：Flask 创始人 Armin Ronacher 在个人博客发表《Better Models: Worse Tools》，揭示 Claude Opus 4.8 和 Sonnet 5 在外部工具调用上的表现**倒退**于旧版模型；同时 GitHub Codex 仓库 #30364 号 issue 用 39 万次调用数据证明 GPT-5.5 的 reasoning tokens 被异常聚类在 516/1034/1552 等固定阈值，导致复杂任务性能下降。两件事指向同一个深层问题：**后训练（post-training）对单一工具生态的过拟合，正在制造"脆弱的通才"**。本文从技术机制、数据证据、行业趋势三个维度，深度剖析这一正在被忽视的 Agent 可靠性危机。

---

## 一、一个违反直觉的发现：更强的模型，更差的工具调用

2026 年 7 月 4 日，Armin Ronacher（lucumr.pocoo.org，Flask、PyPI、Pi 编辑器的创建者）发表了一篇技术博客：[《Better Models: Worse Tools》](https://lucumr.pocoo.org/2026/7/4/better-models-worse-tools/)。这篇文章在 Hacker News 上迅速获得 72 分和 19 条评论——不是因为它介绍了什么新工具，而是因为它指出了一个**反直觉且令人不安**的现象：

> **Anthropic 最新的 SOTA 模型（Opus 4.8、Sonnet 5）在使用非 Claude Code 工具时，表现比旧版模型更差。**

这不是"小模型偶尔犯错"的常见问题。这是最强的模型，在它们的"主业"上出现了系统性退化。

### 1.1 问题的具体表现

Ronacher 的 Pi 编辑器有一个嵌套结构的 edit 工具，schema 大致如下：

```json
{
  "path": "some/file.py",
  "edits": [
    {
      "oldText": "text to replace",
      "newText": "replacement text"
    }
  ]
}
```

旧版模型调用这个工具时，基本能正确生成符合 schema 的参数。但 Opus 4.8 和 Sonnet 5 开始**发明额外字段**：

```json
{
  "oldText": "...",
  "newText": "...",
  "requireUnique": true       // ← 模型自创的字段
}
```

或者：

```json
{
  "oldText": "...",
  "newText": "...",
  "oldText2": "",
  "newText2": ""             // ← 模型自创的字段
}
```

Ronacher 观察到的自创字段"动物园"包括：`type`、`id`、`kind`、`unique`、`requireUnique`、`matchCase`、`in_file`、`forceMatchCount`、`children`、`notes`、`cost`、`oldText2`、`newText2`、`oldText_2`、`newText_2`，甚至还有一个 `event.0.additionalProperties`。

**最让人沮丧的是：`oldText` 和 `newText` 的内容本身是正确的。** 模型确实产生了正确的编辑意图，但在 JSON 对象的末尾自行添加了无意义的字段。这就像你的同事正确地写完了代码，但非要在文件末尾加一段毫无关系的注释——结果整个文件编译不过。

### 1.2 失败的触发条件

Ronacher 做了大量实验，发现失败有几个关键特征：

| 条件 | 是否触发 |
|------|----------|
| 单轮简单提示"编辑这个文件" | ❌ 不触发 |
| Agent 式长对话（读取→诊断→编辑） | ✅ 触发 |
| 剥离 thinking blocks | 失败率减半 |
| 开启 strict tool invocation | 完全消除 |
| Opus 4.8 在特定用户会话中 | 约 20% 失败率 |

这些特征揭示了一个重要线索：**失败不是随机的退化，而是与训练方式密切相关**。

---

## 二、技术机制分析：为什么更好的模型会更差？

### 2.1 工具调用的本质：文本，不是魔法

理解这个问题的关键前提是：**LLM 的工具调用并不是什么神奇的内部机制，它本质上只是文本生成。**

模型接收到的是：对话历史 + 系统提示 + 可用工具列表（JSON Schema 描述）。服务器将这些打包成一个大的 prompt，里面带有特殊的标记 token。因为模型在训练和强化学习中见过这种格式的示例，它在生成过程中的某个时点会"发出"某种被 API 或客户端解释为"调用这个工具，使用这些参数"的内容。

对于 Anthropic 模型，虽然我们不知道确切格式，但有人泄露过 "ANTML" 标记，大致结构像这样：

```xml
<antml:function_calls>
  <antml:invoke name="edit">
    <antml:parameter name="path">some/file.py</antml:parameter>
    <antml:parameter name="edits">
[
  {
    "oldText": "text to replace",
    "newText": "replacement text"
  }
]
    </antml:parameter>
  </antml:invoke>
</antml:function_calls>
```

注意几个关键事实：
1. 这看起来像 XML，但实际上不是真正的 XML——只是方便 tokenization 和训练的标记约定
2. 简单字符串参数以内联形式出现，而对象数组以 JSON 序列化形式嵌入
3. **模型没有真正的 schema 验证能力**——它只是在"模仿"它见过的格式

### 2.2 两种让模型输出正确 JSON 的方法

要让模型产生结构化的工具调用参数，工程上有两条路：

**方法一：事后验证。** 让模型输出 JSON，然后用代码验证是否符合 schema，不符合则报错让它重试。

**方法二：约束解码（constrained decoding）。** 在采样时屏蔽掉违反语法的 token。如果 schema 规定编辑对象只能有 `oldText` 和 `newText` 两个 key，采样器可以阻止模型输出 `"in_file"` 或 `"type"` 这样的 key。

方法二通常被称为"grammar-aware decoding"或"constrained sampling"，是目前最可靠的工具调用约束方式。OpenAI 的 Harmony 格式甚至引入了 `<|constrain|>json` 这样的显式标记，让推理栈在采样时切换到 JSON 约束模式。

**但 Anthropic 的情况要模糊得多。** 没有公开的严格约束机制文档，没有公开的 Claude Code harness 源码。我们只能从现象推断。

### 2.3 Ronacher 的核心假说：训练过拟合

Ronacher 提出了一个非常有说服力的假说：

> **这不是随机退化，而是训练的人工产物（training artifact）。**

推理链如下：

1. **旧版模型**在训练时，接触到的工具文档是 Anthropic 公开的平台文档——格式相对通用、标准化
2. **新版模型**的后训练（post-training）很可能包含了 Claude Code 或类似 harness 的交互数据
3. Claude Code 的工具 schema 与公开文档**并不一致**——它使用更扁平的 `file_path`/`old_string`/`new_string` 结构，而非嵌套的 `edits[]`
4. 更重要的是，Claude Code 的客户端是一个**极度宽容的修复器**（"slop harness"）：
   - 它有参数别名系统（`old_str` = `old_string`，`new_str` = `new_string`，`path` = `file_path`）
   - 它静默过滤未知 key
   - 它修复 Unicode 转义错误
   - 它有泄漏的 `<invoke` 标记检测和重试状态机
   - 它不使用 strict mode

这意味着：**如果 RL 训练在这样一个宽容的 harness 中进行（或模拟），轻微格式错误的工具调用仍然可以完成任务并获得奖励。harness 完全吸收了错误，模型没有学习到"不应该发明额外字段"的梯度信号。**

更糟糕的是，模型可能变得**强烈适应** Claude Code 的工具 schema。当面对语义相同但结构不同的工具时（如 Pi 的嵌套 `edits[]`），这个工具就变成了**分布外（off-distribution）输入**。而且——训练得越好的模型，先验越强，越难适应。

这就是核心悖论：**模型越"好"（越接近 Claude Code 的训练分布），它对外部工具的适应性就越差。**

### 2.4 失败的高熵时刻

Ronacher 还提供了一个非常精细的观察：自创字段出现在**最高熵的时刻**——在输出一个长达数百 token 的转义 `newText` 字符串之后，模型必须决定是输出 `}` 结束对象，还是输出 `, "..."` 继续添加字段。

对于嵌套在 XML 标记内的 JSON 字符串，这包含了多层转义和格式嵌套。在高熵决策点，具有更强 Claude Code 先验的模型更容易"滑入"它习惯的模式——比如添加一个它认为可能存在的可选字段。

---

## 三、另一个证据：GPT-5.5 Codex 的 Reasoning Token 聚类

就在 Ronacher 的文章发布的同一天，GitHub Codex 仓库出现了一个 [极具分量的 issue #30364](https://github.com/openai/codex/issues/30364)，用大量数据揭示了 GPT-5.5 的另一个"退化"模式：

### 3.1 数据概览

该 issue 分析了 390,195 条响应级 token 记录，覆盖 865 个会话，时间跨度从 2026 年 2 月到 6 月。核心发现：

| 指标 | 数值 |
|------|------|
| 总响应记录 | 390,195 |
| 覆盖会话数 | 865 |
| 精确 reasoning_output_tokens = 516 的事件 | 3,363 |
| GPT-5.5 占所有响应的比例 | 19.3% |
| GPT-5.5 占精确 516 事件的比例 | **82.0%** |
| GPT-5.5 的 exact-516 / >=516 比率 | **44.0%** |
| 非 GPT-5.5 的 exact-516 / >=516 比率 | 1.3% |

按模型分解：

| 模型 | 响应记录 | exact-516 / >=516 比率 |
|------|----------|----------------------|
| gpt-5.5 | 75,401 | **44.0%** |
| gpt-5.4 | 25,214 | 19.8% |
| gpt-5.2 | 247,575 | 0.34% |
| gpt-5.3-codex | 13,333 | 0.0% |
| gpt-5.3-codex-spark | 26,179 | 0.0% |

按月趋势更为触目惊心：

| 月份 | exact-516 / >=516 比率 | 平均 reasoning tokens | P90 reasoning tokens |
|------|----------------------|---------------------|---------------------|
| 2026-02 | 0.11% | 268.1 | 772 |
| 2026-03 | 2.45% | 256.8 | 723 |
| 2026-04 | 4.25% | 228.7 | 669 |
| 2026-05 | **53.30%** | **106.9** | **344** |
| 2026-06 | 35.84% | 168.5 | 515 |

### 3.2 这意味着什么？

516、1034（= 516×2）、1552（≈ 516×3）这些精确值不可能是自然分布的结果。它们看起来像是**硬性阈值边界**——模型的 reasoning 过程在到达某个固定 token 数时被截断或强制停止。

更令人担忧的是，当 516 聚类急剧上升时（5 月达到 53.3%），**整体的 reasoning token 使用量却在下降**：P90 从 772 降到 344。这意味着不是模型"想得更久了"，而是它"想得更短了但被迫停在固定边界上"。

这与 Claude 模型的工具调用退化形成了完美的呼应：

| 现象 | Claude | GPT-5.5 Codex |
|------|--------|---------------|
| 表现形式 | 工具调用发明额外字段 | Reasoning tokens 聚类在固定阈值 |
| 触发条件 | Agent 式长对话、复杂编辑 | 复杂/高赌注 Codex 任务 |
| 趋势 | 新版本比旧版本更差 | 5 月起急剧恶化 |
| 根本原因假说 | RL 对单一 harness 过拟合 | Reasoning budget 截断/路由行为 |
| 共同特征 | **模型越强，表现越不稳定** | **模型越强，表现越不稳定** |

---

## 四、行业背景：Agent 工具生态正在爆发，但地基在摇晃

### 4.1 GitHub Trending 的信号

就在同一周，GitHub Trending 上出现了大量与 Agent 工具调用直接相关的项目：

| 项目 | Stars | 说明 |
|------|-------|------|
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | 45,769 | Chrome DevTools 的 MCP 接口，让编码 Agent 直接控制浏览器 |
| [alibaba/page-agent](https://github.com/alibaba/page-agent) | 23,094 | JavaScript 页面内 GUI Agent，用自然语言控制网页 |
| [ogulcancelik/herdr](https://github.com/ogulcancelik/herdr) | 11,427 | 终端内的 Agent 多路复用器 |
| [agentskills/agentskills](https://github.com/agentskills/agentskills) | — | Agent Skills 规范与文档 |
| [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc) | 24,390 | 从 Claude Code 调用 Codex |

整个行业正在疯狂建设 Agent 工具的**协议层**和**适配层**。MCP（Model Context Protocol）已成为事实标准，各种工具正在被封装成 Agent 可调用的接口。

**但问题恰恰在于：如果底层模型对"工具应该长什么样"的先验越来越窄、越来越偏向特定生态，那这些协议层和适配层可能从一开始就在打一场必输的仗。**

### 4.2 Hugging Face 的"Agent 评测"运动

Hugging Face 博客近期连续发布多篇与 Agent 工具使用评测相关的文章：

- [ScarfBench](https://huggingface.co/blog/ibm-research/scarfbench)：企业 Java 框架迁移的 Agent 基准
- [Is it agentic enough?](https://huggingface.co/blog/is-it-agentic-enough)：用你自己的工具链评测开源模型的 Agent 能力
- [Agentic Resource Discovery](https://huggingface.co/blog/agentic-resource-discovery-launch)：让 Agent 自己搜索可用工具

这些项目的共同特征是：**不再相信厂商的基准分数，而是用实际的工具使用场景来评测。** 这本身就说明了业界对"模型声称的 Agent 能力"的不信任正在加深。

### 4.3 一个被忽视的"对齐税"变种

在 2026 年 6 月的一篇本博客文章《[LLM 的"对齐税"](https://github.com/kejun/blogpost/blob/main/2026-06-18-llm-alignment-tax-when-safety-training-becomes-performance-liability.md)》中，我们讨论了安全训练如何变成性能负债。但 Ronacher 的观察揭示了一个**更隐蔽的"对齐税"**：

> **对单一工具生态的 RL 过拟合，本质上是一种"能力税"——模型在一个环境中表现得越好，在另一个环境中的表现就越差。**

这与传统的"对齐税"不同。传统对齐税是"安全训练降低了能力"，而这里是**"能力训练降低了泛化"**。模型没有变得更"安全"或更"有害"，它只是变得**更狭隘**。

---

## 五、解决方案框架：如何构建对模型退化有韧性的 Agent 工具层

既然问题来自训练过拟合，那解决方案就需要在工具层和应用层同时着手。

### 5.1 约束解码：最直接的工程解法

如果模型在采样时不被允许输出 schema 之外的 key，那它就不可能发明额外字段。这正是 OpenAI Harmony 的 `<|constrain|>json` 标记所解决的问题。

对于 Anthropic 模型，可以启用 `strict: true` 参数。Ronacher 的实验表明：

> **开启 strict tool invocation 后，问题完全消除。**

但这也有代价：strict mode 对工具定义的复杂度有限制，Anthropic 对过长的工具定义会直接拒绝 API 请求。这是一个**在可靠性和灵活性之间的工程权衡**。

### 5.2 工具设计：扁平优于嵌套

从 Ronacher 的分析可以得出一个实用的工具设计原则：

> **工具 schema 越扁平、越接近模型训练分布，调用成功率越高。**

具体来说：
- 避免深层嵌套结构（如 `edits[]` 数组内的对象）
- 减少可选参数的数量
- 避免在同一工具中混合多种操作模式
- 使用与主流 harness（Claude Code、Codex）兼容的参数命名

### 5.3 宽容的 harness：必要的"脏代码"

Claude Code 的客户端是一个教科书级的宽容 harness 设计：

```
参数别名系统 → Unicode 转义修复 → 未知 key 过滤 → 泄漏标记检测 → 重试状态机
```

每个环节都在吸收模型的"错误"，让 Agent 流程继续运行。这看起来像脏代码，但在当前模型不可靠的阶段，**它是最有效的可靠性保障**。

值得注意的悖论是：宽容的 harness 让 RL 训练缺乏"错误信号"，从而加剧了过拟合。这是一个**自证的恶性循环**。

### 5.4 上下文管理：减少 thinking blocks 的噪声

Ronacher 发现剥离 thinking blocks 可以将失败率减半。这提示了一个实用的优化方向：

- 在工具调用前**清理对话历史**，特别是移除冗长的 thinking traces
- 在工具调用步骤使用**独立的 system prompt**，减少历史噪声
- 考虑将工具调用步骤与 reasoning 步骤**解耦**，降低上下文复杂度

### 5.5 多模型冗余：不要把鸡蛋放在一个篮子里

鉴于不同模型的退化模式不同（Claude 过拟合工具 schema，GPT-5.5 有 reasoning token 截断），一个实用的策略是：

- 对关键 Agent 流程使用**多模型投票**或**主备切换**
- 在检测到工具调用失败率升高时**自动降级到旧版模型**
- 将模型版本的"可靠性元数据"纳入 Agent 调度决策

---

## 六、深层问题：闭源模型 vs. 工具生态的开放性

Ronacher 在文章最后提出了一个值得深思的问题：

> **Anthropic 的模型完全封闭，Claude Code 的 harness 也完全封闭。工具开发者面对的是一个"黑盒训练出来的模型，在黑盒工具生态中优化"的局面。**

对比之下：
- OpenAI 的 Codex harness 是开源的，至少在 GitHub 上可以 inspect
- OpenAI 的 Harmony 格式有文档，告诉你他们如何思考工具调用
- OpenAI 的 gpt-oss 虽然训练目标是 Harmony，但至少**透明**
- Google 的模型允许提供 LARK grammar 来约束自定义工具

Anthropic 的情况最不透明。你不知道模型在训练中见过什么工具、RL 奖励了什么行为、Claude Code 的内部 harness 到底做了什么。你只能从行为反推，就像 Ronacher 做的那样。

这对于整个 Agent 工具生态来说是一个**系统性的风险**：如果最大的模型供应商的工具生态是封闭的，那么第三方工具永远处于"分布外"的劣势地位。

---

## 七、一个框架：Agent 工具可靠性的"不可能三角"

综合所有观察，我提出一个 Agent 工具可靠性的**不可能三角**：

```
        模型能力
          ▲
         / \
        /   \
       /     \
      /       \
     /         \
    /  ❌ 不可能 \
   /  同时实现  \
  /_____________\
 工具泛化性      训练效率
```

- **模型能力**：在特定任务上表现出色
- **工具泛化性**：能适应不同 schema、不同 harness 的工具
- **训练效率**：在单一生态中快速获得高奖励

**你最多只能同时实现两个。** 当前的趋势是：模型厂商选择了"模型能力 + 训练效率"，牺牲了"工具泛化性"。

这解释了为什么 Opus 4.8 在 Claude Code 中可能表现完美（模型能力 + 训练效率），但在 Pi 编辑器中却频繁出错（工具泛化性缺失）。这也解释了为什么 GPT-5.5 在简单任务中表现优异，但在复杂 Codex 任务中会出现 reasoning token 聚类（训练效率优化导致了能力天花板）。

---

## 八、前瞻：2026 年下半年的三个关键观察点

基于以上分析，我认为 2026 年下半年应该关注三个方向：

### 8.1 Anthropic 是否会回应？

Ronacher 的文章和 GPT-5.5 的 issue 都指向同一个问题。如果 Anthropic 不回应或不做调整，这意味着他们接受了"封闭生态过拟合"的策略——对 Anthropic 的用户来说没问题，但对整个 Agent 工具生态来说是一个坏信号。

### 8.2 约束解码是否会成为标准？

OpenAI 的 Harmony 格式已经提供了显式的约束机制。如果 Anthropic 跟进，或者社区发展出独立于模型的约束解码层（如 vLLM 的 grammar-constrained sampling），那将大幅降低工具调用的不确定性。

### 8.3 开源模型是否会抓住"工具泛化性"的机会？

当前开源模型（Qwen 3.6、GLM-5.2 等）在绝对能力上仍然落后于闭源 SOTA，但它们在工具泛化性上可能有天然优势——因为它们没有绑定到任何一个封闭的 harness 生态中。如果开源社区能够系统性地优化这一优势，可能会在 Agent 基础设施层形成一个**新的竞争维度**。

---

## 结语：模型变强的速度，正在超过它变得可靠的速度

2026 年 7 月的这两个事件，揭示了一个 Agent 时代正在浮现的深层矛盾：

**我们越来越依赖模型做"正确的事"，但模型变得越来越"只对一种事正确"。**

这不是模型厂商的错——RL 天然倾向于优化单一目标，而单一目标天然倾向于过拟合。这是**RLHF 范式在 Agent 时代的系统性局限**。

对于构建 Agent 应用的工程师来说，这意味着：

1. **不要信任模型的"工具调用能力"是一个稳定的特性**——它会随着版本波动，甚至退化
2. **在工具层做防御性编程**——假设模型会发明额外字段、会搞错参数名、会输出半截 JSON
3. **监控工具调用的失败模式**——将失败率、失败类型纳入 Agent 可观测性的核心指标
4. **准备降级方案**——当最新模型的可靠性不如旧版时，要敢于回退

模型变强是确定的。但模型变可靠，不一定会随之发生。有时候，它恰恰相反。

---

> **参考资料：**
> 1. Armin Ronacher, ["Better Models: Worse Tools"](https://lucumr.pocoo.org/2026/7/4/better-models-worse-tools/), July 4, 2026
> 2. GitHub Issue, ["GPT-5.5 Codex reasoning-token clustering may be leading to degraded performance"](https://github.com/openai/codex/issues/30364), July 2026
> 3. GitHub Issue, ["gpt-5.5 xhigh sometimes short-circuits with reasoning_output_tokens=516"](https://github.com/openai/codex/issues/29353), June 2026
> 4. OpenAI, [Harmony Response Format Documentation](https://github.com/openai/harmony), 2026
> 5. Hugging Face, ["Is it agentic enough? Benchmarking open models on your own tooling"](https://huggingface.co/blog/is-it-agentic-enough), June 2026
> 6. IBM Research / Hugging Face, ["ScarfBench: Benchmarking AI Agents for Enterprise Java Framework Migration"](https://huggingface.co/blog/ibm-research/scarfbench), June 2026
