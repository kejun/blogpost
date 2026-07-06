# AI 品味工程：当"审美"成为 Agent 时代的新工程学科——从 taste-skill 看 AI Slop 危机

> **摘要：** 2026 年 7 月初，一个名为 [taste-skill](https://github.com/Leonxlnx/taste-skill) 的开源项目在不到一周内飙升至 57,000+ stars，日均新增 800+ star。它的 README 只有一句话："gives your AI good taste. stops the AI from generating boring, generic slop." 与此同时，另一个名为 [caveman](https://github.com/JuliusBrussee/caveman) 的项目以 85,000+ stars 霸榜 GitHub Trending，用"像穴居人一样说话"的方式为 Claude Code 削减 65% 的 token 消耗。这两个看似毫不相关的项目——一个追求"美感"，一个追求"效率"——实际上指向了同一个深层趋势：**AI Agent 的输出质量正在分化为两个独立维度——功能正确性和审美质量，而后者正在催生一门全新的工程学科：AI 品味工程（AI Taste Engineering）。** 本文将从技术机制、生态数据、行业趋势三个维度，深度剖析这一正在快速成型的领域。

---

## 一、什么是"AI Slop"？一个正在被认真对待的危机

### 1.1 从玩笑到危机

"Slop"这个词在 AI 社区已经从一个自嘲的玩笑，演变成一个**被严肃对待的技术问题**。它指的是 AI 生成的那种"功能上没毛病，但审美上平庸到令人窒息"的输出：

- 一个前端页面：布局是居中的三栏卡片，配色是 Tailwind 默认的 slate/blue，圆角是 `rounded-lg`，阴影是 `shadow-md`——**一切正确，一切无聊**。
- 一段代码：命名规范、类型完整、错误处理到位——**但结构千篇一律，没有任何对业务域的独特表达**。
- 一份文档：Markdown 格式完美、层级清晰、emoji 用得恰到好处——**但读起来像 100 份同类文档的平均值**。

问题的关键不在于"AI 做错了什么"，而在于**AI 做对了太多事情，以至于输出收敛到了一个统计意义上的"最安全方案"**。这个最安全方案就是 slop。

### 1.2 为什么 slop 在 2026 年爆发？

三个因素叠加：

**第一，Coding Agent 的普及率出现了指数级增长。** 2026 年上半年，Claude Code、OpenAI Codex、Cursor Agent 等编码 Agent 的日活用户增长了 5 倍以上（据 GitHub 官方数据，Codex 周活跃仓库数从 1 月的 20 万增长到 6 月的 110 万）。这意味着每天有数十万开发者在用相同的模型、相同的系统提示、相同的工具链生成代码和 UI。

**第二，Agent Skills 生态的标准化降低了"使用 AI"的门槛。** Vercel  Labs 推出的 [agent-skills](https://github.com/vercel-labs/agent-skills) 规范（通过 `npx skills add` 一键安装）让任何人都能为 Agent 注入预定义的行为模式。标准化带来了效率，但也带来了**输出的趋同化**——当 10 万个开发者使用同一个 skill 时，他们的产出自然会收敛。

**第三，模型的"安全偏好"天然倾向于平庸。** 经过 RLHF 训练的模型，其输出分布的方差被有意压缩——模型被奖励"安全"的回答，惩罚"冒险"的回答。这种压缩在对话场景中是合理的（你不希望 AI 胡说八道），但在创意和设计场景中是**致命的**：它直接消灭了"好品味"所需要的变异空间。

### 1.3 一个数据点：taste-skill 的 star 增长曲线

taste-skill 的 star 增长不是线性的，而是典型的**病毒式扩散**：

| 日期 | Stars | 日增 |
|------|-------|------|
| 7 月 1 日 | ~32,000 | — |
| 7 月 2 日 | ~38,000 | ~6,000 |
| 7 月 3 日 | ~43,000 | ~5,000 |
| 7 月 4 日 | ~48,000 | ~5,000 |
| 7 月 5 日 | ~54,000 | ~6,000 |
| 7 月 6 日 | ~57,440 | ~3,440 |

**五天内新增 25,000+ stars。** 在 2026 年的 GitHub 生态中，这是极少数能匹敌 OpenAI 官方项目增速的社区项目。更值得注意的是，它的 fork 数也达到了 3,931——意味着大量开发者不仅在"收藏"它，还在**基于它构建自己的变体**。

---

## 二、taste-skill 的技术解剖：如何给 AI "植入品味"？

### 2.1 核心设计：三个可调旋钮

taste-skill 的核心创新极其简洁。它不试图教会 AI 什么是"美"，而是提供**三个可量化的设计维度旋钮**，让开发者根据项目需求调整 AI 输出的"品味方向"：

| 旋钮 | 范围 | 含义 | 低端效果 | 高端效果 |
|------|------|------|----------|----------|
| `DESIGN_VARIANCE` | 1-10 | 布局实验性 | 居中、对称、保守 | 不对称、现代、冒险 |
| `MOTION_INTENSITY` | 1-10 | 动画深度 | 仅 hover 效果 | 滚动驱动、磁吸效果 |
| `VISUAL_DENSITY` | 1-10 | 信息密度 | 大量留白、极简 | 密集仪表盘风格 |

这三个旋钮的精妙之处在于：**它们不规定具体该怎么做，而是规定了"偏离默认值多远"**。这恰恰抓住了品味的本质——品味不是"正确"，而是"有方向性地偏离平均"。

### 2.2 v2 架构：从静态规则到推断引擎

taste-skill v2（实验版）做了一次重要的架构升级。v1 是一个静态的 SKILL.md 文件，包含固定的设计规则和 CSS 片段。v2 则变成了一个**推断引擎**：

```
设计 Brief → Brief 推断 → 设计系统映射 → 三旋钮调参 → 输出代码
```

具体来说：

1. **Brief 推断**：读取用户的项目描述，自动判断项目类型（SaaS 落地页、电商、作品集、Dashboard 等）。
2. **设计系统映射**：根据项目类型，自动映射到一组设计决策——字体选择、间距体系、色彩策略、组件风格。
3. **三旋钮调参**：根据项目类型自动设定三个旋钮的初始值，同时允许开发者手动覆盖。
4. **输出代码**：生成带有 GSAP 动画骨架、精确间距系统、层次分明的视觉层级的完整代码。

v2 还引入了几个关键的"防 slop"规则：

- **硬禁止 em-dash（—）**：AI 在文本排版中滥用 em-dash 是 slop 的典型标志。v2 在 SKILL.md 中明确禁止。
- **Canonical GSAP code skeletons**：提供标准化的 GSAP 动画骨架代码，避免 AI 生成平庸的 CSS transition。
- **Redesign-audit protocol**：对已有项目进行"审美审计"——先分析现有设计的问题，再针对性修复。
- **Strict pre-flight check**：在生成代码前，强制 Agent 检查是否满足品味约束。

### 2.3 技术实现：SKILL.md 作为品味载体

taste-skill 的载体是 [SKILL.md](https://github.com/Leonxlnx/taste-skill) 文件——这是 2026 年 Agent Skills 生态的事实标准格式。SKILL.md 本质上是一个带有 frontmatter 的 Markdown 文件，定义了 Agent 在执行特定任务时应遵循的规则、约束和工作流程。

taste-skill 的 SKILL.md 大约包含 2,000-3,000 行的设计规则，涵盖：

- **布局系统**：网格、间距、响应式断点的具体数值范围
- **排版规则**：字体搭配、行高、字号比例（基于 Modular Scale）
- **色彩策略**：色相选择、对比度要求、渐变使用条件
- **动效指南**：缓动曲线、持续时间、触发时机
- **反模式列表**：明确列出"不要这样做"的具体场景

**这不是一个"提示词"，而是一份设计规范。** 它和传统设计规范的区别在于：它被写成了 LLM 能理解并执行的格式。

### 2.4 多 skill 组合：品味作为可组合的模块

taste-skill 不是单一 skill，而是一个 skill 集合：

| Skill | 安装名 | 定位 |
|-------|--------|------|
| taste-skill | `design-taste-frontend` | 通用默认（v2 实验版） |
| taste-skill-v1 | `design-taste-frontend-v1` | 原版 v1（向后兼容） |
| gpt-taste | `gpt-taste` | 针对 GPT/Codex 的更严格变体 |
| soft-skill | `high-end-visual-design` | 高端、安静、昂贵感 UI |
| minimalist-skill | `minimalist-ui` | Notion/Linear 风格 |
| brutalist-skill | `industrial-brutalist-ui` | 工业粗野主义 |
| redesign-skill | `redesign-existing-projects` | 现有项目审计+修复 |
| output-skill | `full-output-enforcement` | 防止 Agent 输出半成品 |

这种**模块化品味**的设计反映了一个重要认识：**品味不是单一的，而是场景依赖的**。同一个 Agent 在构建金融 Dashboard 时需要的是"冷静、精确、高密度"的品味，而在构建创意作品集时需要的是"大胆、不对称、高对比"的品味。taste-skill 通过可组合的 skill 模块，让品味的切换变得和 `npm install` 一样简单。

---

## 三、更大的图景：AI Slop 危机的多维度表现

### 3.1 不只是 UI：slop 正在渗透所有 Agent 输出领域

taste-skill 聚焦于前端 UI，但 slop 问题的影响范围远不止于此。从 GitHub Trending 的数据可以看出，slop 危机正在多个维度同时爆发：

**代码 slop：**
AI 生成的代码倾向于使用最常见的模式——`try-catch` 包裹一切、过度抽象的 service 层、千篇一律的错误处理。代码"看起来正确"但缺乏对业务逻辑的深入表达。

**文档 slop：**
AI 生成的文档有完美的 Markdown 格式、恰到好处的 emoji、标准的层级结构——但缺乏深度见解，读起来像维基百科条目。

**架构 slop：**
当 Agent 被要求设计系统架构时，它们倾向于输出"微服务 + 消息队列 + 缓存"的标准模板，而不是基于具体业务约束做出有取舍的设计决策。

**创意 slop：**
AI 生成的品牌设计、logo、配色方案都收敛到了"安全区"——蓝色系、圆角、渐变背景。

### 3.2 一个对比：taste-skill vs. caveman 的两条路径

GitHub Trending 上同时爆火的两个项目——taste-skill（57k stars）和 [caveman](https://github.com/JuliusBrussee/caveman)（85k stars）——恰好代表了应对 AI 输出质量问题的两条截然不同的路径：

| | taste-skill | caveman |
|---|---|---|
| 核心理念 | 给 AI 注入好的审美品味 | 让 AI 用最少 token 说话 |
| 解决问题 | AI 输出平庸、无聊 | AI 输出冗长、啰嗦 |
| 方法论 | 添加设计规则和约束 | 删除多余语言和格式 |
| Token 影响 | 可能增加（更详细的规范） | 减少 65% |
| 目标用户 | 前端开发者、设计师 | 所有 Agent 用户 |
| 哲学隐喻 | "AI 需要学品味" | "AI 需要学会闭嘴" |

caveman 的 README 写着："why use many token when few token do trick"——它通过强制 Agent 用极简的"穴居人语言"交流，减少了 65% 的 token 消耗。这表面上和 taste-skill 毫无关系，但**它们共享同一个底层诊断**：默认状态下的 AI Agent 输出是有问题的，需要外部干预来纠正。

区别在于：taste-skill 说"AI 的输出需要更有品味"，caveman 说"AI 的输出需要更精简"。两者都是对 AI 默认输出质量的否定。

### 3.3 GitHub Trending 的完整信号

7 月 5-6 日的 GitHub Trending 上，与 Agent 输出质量相关的项目构成了一个**完整的生态信号**：

| 项目 | Stars | 解决的问题 |
|------|-------|-----------|
| taste-skill | 57,440 | AI 审美平庸 |
| caveman | 84,842 | AI 输出冗长 |
| planning-with-files | ~30,000 | Agent 规划不持久 |
| herdr | 12,040 | 多 Agent 编排混乱 |
| gastown | ~5,000 | 多 Agent 工作空间管理 |
| codex-plugin-cc | 25,436 | Agent 间互操作 |
| output-skill | (taste-skill 子项目) | Agent 输出不完整 |

这个生态的共同特征是：**它们都不在改进模型本身，而是在模型之外构建质量保障层。** 这暗示了一个重要判断：社区已经不再等待"下一个更强的模型"来解决输出质量问题，而是接受了"模型本身不会自动变好"的现实，开始在应用层做文章。

---

## 四、AI 品味工程：一门新学科的诞生

### 4.1 为什么"品味"需要工程化？

在传统软件开发中，品味是设计师的领域。设计师通过教育、经验和直觉来做出审美决策。但在 Agent 时代，这个模式被打破了：

**Agent 正在成为第一线的"设计执行者"。** 当开发者用自然语言描述一个页面，Agent 直接生成代码——中间没有设计师介入。这意味着**品味的责任从设计师转移到了……模型的系统提示词上**。

但系统提示词里的品味和设计师的品味有一个根本区别：设计师的品味是**内化的、直觉的、可适应的**，而系统提示词里的品味是**外化的、规则的、僵化的**。taste-skill 尝试做的，就是把后者尽可能逼近前者。

### 4.2 AI 品味的量化框架

我们可以尝试为"AI 品味"建立一个量化框架。基于 taste-skill 的实践和社区讨论，以下维度可以作为品味的量化指标：

#### 4.2.1 布局方差指数（Layout Variance Index, LVI）

衡量 UI 布局偏离"默认居中三栏"模板的程度。计算方式：

```
LVI = (非标准布局决策数) / (总布局决策数)
```

其中"非标准布局决策"包括：非对称网格、非居中 hero、非标准断点、非常规组件排列等。

**LVI = 0**：完全标准的模板布局
**LVI = 0.3-0.5**：有设计感的布局
**LVI > 0.7**：实验性/冒险性布局

taste-skill 的 `DESIGN_VARIANCE` 旋钮本质上就是在控制 LVI。

#### 4.2.2 动效丰富度指数（Motion Richness Index, MRI）

衡量 UI 中动效的层次和质量：

```
MRI = Σ(动效复杂度 × 动效数量) / 页面组件数
```

其中动效复杂度分为：
- Level 1：CSS hover transition（0.5 分）
- Level 2：滚动触发动画（1 分）
- Level 3：物理引擎/磁吸效果（2 分）
- Level 4：自定义 GSAP 时间轴（3 分）

#### 4.2.3 排版精确度指数（Typography Precision Index, TPI）

衡量排版决策的精确程度：

```
TPI = (使用系统字体的决策 + 使用模块化字号比例 + 使用合理行高) / 总排版决策
```

#### 4.2.4 Slop 密度（Slop Density, SD）

衡量输出中 slop 特征的出现频率：

```
SD = (slop 特征数) / (总特征数)
```

Slop 特征包括：em-dash 滥用、默认蓝色配色、`rounded-lg` + `shadow-md` 组合、`space-y-4` 统一间距、`container mx-auto px-4` 的无脑使用等。

**这些指标不是精确的科学测量，而是工程化的启发式工具。** 它们的价值不在于绝对数值，而在于提供了一个**可讨论、可比较、可改进的框架**。

### 4.3 品味工程与对齐税的关系

在 2026 年 6 月的博客文章《[LLM 的"对齐税"](https://github.com/kejun/blogpost/blob/main/2026-06-18-llm-alignment-tax-when-safety-training-becomes-performance-liability.md)》中，我们讨论了安全训练如何变成性能负债。品味工程揭示了**对齐税的另一个维度**：

> **RLHF 不仅压缩了模型在"安全性"上的输出方差，也压缩了模型在"创造性"上的输出方差。**

这是一个被严重忽视的副作用。当模型被奖励"安全的回答"时，它学到的不仅仅是"不要输出有害内容"，还包括"不要输出冒险的、非标准的、可能被批评的设计决策"。

这就是为什么 AI 生成的 UI 总是看起来差不多：**不是模型"不知道"更好的设计，而是它的训练过程系统性地惩罚了偏离平均值的输出。**

品味工程的本质，就是**在推理时绕过这种压缩**——通过外部注入的设计规范和约束，让模型能够输出它"知道"但被训练过程"压制"的内容。

---

## 五、行业趋势：品味工程正在成为独立赛道

### 5.1 Hugging Face 的信号

Hugging Face 近期发布的 [Dharma AI 博客《Why Specialization Is Inevitable》](https://huggingface.co/blog/Dharma-Ai/why-specialization-is-inevitable) 提出了一个与品味工程高度相关的观点：

> **通用模型在某些领域的表现正在被专门训练的"小模型"超越，因为专业化允许模型在特定分布上做出更精确的决策。**

这与品味工程的逻辑完全一致：通用模型的设计输出是平庸的，因为它被训练为"对所有人都有用"。而注入了特定品味规范的 Agent，相当于在特定设计分布上做了"专业化"——它的输出不再面向所有人，而是面向一个具体的审美方向。

### 5.2 Garry Tan 的"gstack"叙事

就在 2026 年 6 月底，Y Combinator CEO Garry Tan 发布了 [gstack](https://github.com/kejun/blogpost/blob/main/2026-06-27-garry-tan-gstack-virtual-engineering-team-agent-specialization.md)——"虚拟工程团队"的概念。他提出：

> **未来的工程团队不是"人 + Agent"，而是"一群专业化的 Agent"，每个 Agent 在特定领域有超越通才的能力。**

在这个框架下，"品味"不是一个抽象概念，而是一个**可分配给特定 Agent 的专长**。你可以有一个专门负责前端品味的 Agent，它被 taste-skill 训练过；一个专门负责代码质量的 Agent，它被 Short Leash 方法约束过；一个专门负责架构的 Agent，它被领域知识填充过。

**品味工程的终局，可能就是 gstack 所描述的"专业化 Agent 团队"。**

### 5.3 Meta 收购 Manus 的信号

Meta 在 2026 年 6 月以 20 亿美元收购了 Manus——一个以"持久化文件规划"为核心能力的 AI Agent 公司。[planning-with-files](https://github.com/OthmanAdi/planning-with-files)（社区版的 Manus 方法论）在 GitHub 上获得了大量关注，其 v3.0 版本引入了"自主模式"和"完成门控"。

Manus 的核心理念是：**Agent 的质量不仅取决于模型能力，更取决于它的工作方法。** taste-skill 的理念与此一脉相承——Agent 的审美质量不仅取决于模型能力，更取决于它被植入了什么样的品味规范。

Meta 的收购传递了一个信号：**大公司已经认识到，Agent 的核心竞争力正在从"模型层"下沉到"方法层"。** 品味工程正是这个"方法层"的重要组成部分。

---

## 六、批判性视角：品味工程的局限与风险

### 6.1 "品味"能标准化吗？

这是品味工程面临的最根本质疑。传统意义上的"品味"是主观的、文化的、历史的。将品味编码为 SKILL.md 中的规则列表，本质上是在做一件**高度简化的事**：

> **把多维的、模糊的审美判断，压缩为一维的、可执行的规则集。**

这种压缩不可避免地丢失信息。taste-skill 的三旋钮系统可以调出"更有趣的布局"，但它无法判断"这个布局是否适合这个品牌的调性"。后者需要的是对品牌历史、行业语境、目标用户群的深层理解——这些目前还超出了 SKILL.md 的能力范围。

### 6.2 品味工程的"二阶 slop"风险

一个有趣的风险是：**当 taste-skill 被广泛使用后，它本身可能成为新的 slop 来源。**

想象一下：如果 10 万个前端项目都使用 taste-skill v2，`DESIGN_VARIANCE=7, MOTION_INTENSITY=5, VISUAL_DENSITY=3`，那么这些项目的共同特征是"非对称布局、中等动效、适度留白"——这本身就会成为 2026 年下半年的**新 slop 模板**。

这就是品味工程的悖论：**任何被标准化的品味，最终都会失去它的"品味"属性，变成新的平均。**

解决这个问题可能需要：
- **动态品味注入**：根据项目特征自动调整品味参数，而非使用固定值
- **品味进化机制**：定期更新品味规则，引入新的设计趋势
- **反收敛约束**：强制 Agent 在每次生成时引入一定量的随机变异

### 6.3 品味工程可能加剧设计师的边缘化

一个更深层的伦理问题是：**当品味被编码为 SKILL.md，设计师的角色会发生什么变化？**

当前的趋势是：开发者用 taste-skill 替代了与设计师的合作。开发者不再需要理解设计原理，只需要 `npx skills add taste-skill` 就能获得"有品味"的输出。

短期内，这提高了效率。但长期来看，这可能导致：
- 设计师的议价能力下降
- 设计教育的价值被削弱
- 最终用户接收到的"品味"越来越同质化（因为只有几个流行的 taste-skill 变体在流通）

**品味工程应该增强设计师的能力，而不是替代设计师。** 这是行业需要认真思考的问题。

---

## 七、前瞻：品味工程的三个发展方向

### 7.1 从静态 SKILL.md 到动态品味代理

当前的品味工程主要依赖静态的 SKILL.md 文件。未来的方向是**动态品味代理**——一个能根据项目上下文、用户反馈、设计趋势自动调整品味参数的 Agent。

这个代理会：
1. 分析项目的品牌调性、目标用户、行业特征
2. 从品味知识库中选择合适的设计方向
3. 在生成过程中动态调整品味参数
4. 根据用户反馈持续优化品味模型

这相当于为每个项目创建一个"AI 设计总监"。

### 7.2 品味评估基准的标准化

目前品味评估主要依赖主观判断。未来需要**标准化的品味评估基准**，类似于 ScarfBench 对 Agent 编码能力的评估。

一个品味基准可能包括：
- **设计方差测试**：输出与标准模板的偏离度
- **原创性测试**：输出与已有设计的相似度
- **适用性测试**：品味选择与项目语境的匹配度
- **一致性测试**：同一品味规则在不同项目中的稳定表现

Hugging Face 的 [Every Eval Ever](https://huggingface.co/blog/eee-community-evals) 项目正在推动社区评测的标准化，品味评估可能成为下一个重要方向。

### 7.3 品味工程的开源协作模式

taste-skill 的成功已经证明了一种新的开源协作模式：**品味作为开源项目**。

taste-skill 有 57,000+ stars 和近 4,000 forks，意味着大量开发者在贡献自己的品味变体。这种模式类似于设计系统的开源协作（如 Tailwind CSS），但更聚焦于"品味"这个更抽象的层面。

未来的品味工程可能发展出：
- **品味注册中心**：类似 npm 的品味包管理
- **品味版本控制**：跟踪品味规范的演进
- **品味 A/B 测试**：用数据验证不同品味的效果
- **品味经济**：优质品味规范的价值发现机制

---

## 结语：品味是 Agent 时代最后的差异化因素

2026 年的 Agent 生态正在经历一个关键转折：**模型能力正在快速趋同，而品味正在成为最后的差异化因素。**

当所有 Agent 都能写出正确的代码、生成可用的 UI、输出格式完美的文档时，决定一个项目质量的不再是"能不能做"，而是"做得有没有品味"。

taste-skill 的 57,000+ stars 不是一个偶然现象。它是整个社区对 AI Slop 危机的集体回应。caveman 的 85,000+ stars 是同一枚硬币的另一面——对 AI 输出质量的另一种修正。

品味工程这门新学科才刚刚起步。它的工具箱还很粗糙（三个旋钮、一堆规则、一些 SKILL.md 文件），但它指向的方向是清晰的：**在模型能力趋同的时代，品味是最后的竞争壁垒。**

对于构建 Agent 应用的工程师来说，这意味着：

1. **不要只关注 Agent 的"功能正确性"——关注它的"审美输出质量"**
2. **将品味规范纳入 Agent 配置的标准流程**——就像你配置 API key 一样自然
3. **建立品味评估机制**——用数据衡量 Agent 输出的"品味得分"
4. **警惕品味同质化**——定期审视你的 Agent 输出是否正在变成新的 slop

模型可以生成代码。但品味，仍然需要被工程化。

---

> **参考资料：**
> 1. Leonxlnx, [taste-skill: The Anti-Slop Frontend Framework for AI Agents](https://github.com/Leonxlnx/taste-skill), GitHub, July 2026
> 2. JuliusBrussee, [caveman: Claude Code skill that cuts 65% of tokens](https://github.com/JuliusBrussee/caveman), GitHub, July 2026
> 3. OthmanAdi, [planning-with-files: Persistent file-based planning for AI coding agents](https://github.com/OthmanAdi/planning-with-files), GitHub, July 2026
> 4. ogulcancelik, [herdr: Agent multiplexer that lives in your terminal](https://github.com/ogulcancelik/herdr), GitHub, July 2026
> 5. Dharma AI, [Why Specialization Is Inevitable](https://huggingface.co/blog/Dharma-Ai/why-specialization-is-inevitable), Hugging Face Blog, June 2026
> 6. Hugging Face, [Featuring Every Eval Ever Results on Hugging Face Model Pages](https://huggingface.co/blog/eee-community-evals), June 2026
> 7. IBM Research / Hugging Face, [ScarfBench: Benchmarking AI Agents for Enterprise Java Framework Migration](https://huggingface.co/blog/ibm-research/scarfbench), June 2026
> 8. Vercel Labs, [Agent Skills Specification](https://github.com/vercel-labs/agent-skills), GitHub, 2026
> 9. GitHub Trending data, July 5-6, 2026
