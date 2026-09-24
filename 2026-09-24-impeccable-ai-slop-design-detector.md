# 当"AI 味"成为工程问题：Impeccable 7 万星背后——模型掷不出自己的骰子，61 条规则替它掷

> 2026-09-24 · AI技术 · 本文约 4600 字

## 一眼就能认出的"AI 脸"

先看一份"通缉名单"：

- 全站 Inter 字体，配一段可以贴到任何产品上的文案；
- 紫到蓝的渐变，出现在按钮、文字和背景上；
- 卡片套卡片，五层 padding 和阴影包着同一块内容；
- 每个标题上方一个圆角方形图标底座；
- 深色页面上的一圈径向渐变光晕；
- 灰字放在彩色背景上，小标签几乎不可读。

如果你在过去一年里看过任何 AI 生成的落地页，这份名单大概率让你会心一笑——每一项都似曾相识，组合起来就是俗称的 **AI slop（AI 泔水）**。它不是 bug，页面能跑、布局不错、甚至挺"好看"；它是统计学问题：所有模型在几乎相同的 SaaS 模板语料上训练，不施加外力时，会不约而同地伸手去拿同一批"最可能的设计"。

9 月 24 日的 GitHub Trending 上有一个不含任何模型代码的仓库正在持续吸星：**pbakaus/impeccable**，70,325 stars、4,268 forks，口号只有一句——"The design language that makes your AI harness better at design"（让你的 AI 编程工具更懂设计的设计语言）。它的核心主张是把上面那份"通缉名单"工程化：**61 条确定性检测规则 + 24 个设计命令 + 实时浏览器迭代**，不用 LLM、不用 API key，就能在 Agent 写代码的同时抓出"AI 味"。

作者是 Paul Bakaus——jQuery UI 的创建者，先后在 Google 主导 Google for Creators、创办 Spotter Studio，一个从"设计工具"一路做到"Agent 工具"的创意技术人。这个项目值得认真拆的原因不只是星数：**它是第一个把"设计质量"从提示词玄学变成 CI 式闭环的规模化实践**，而它的 research 页面，可能是目前对"LLM 创意收敛"最诚实的一份第一手实验记录。

## 关键数据一览

| 维度 | 数据 |
|------|------|
| Stars / Forks / 开放 Issue | 70,325 / 4,268 / 42（2026-09-24，GitHub API） |
| 创建时间 | 2025-11-16（约 10 个月，日均净增约 230 星） |
| 许可 / 语言 | Apache-2.0 / JavaScript + 自包含二进制引擎 |
| 内容物 | 1 个 skill、24 个命令、61 条确定性检测规则 + 6 条设计评审模式 |
| 发布节奏 | 65 个 release，最新 skill-v4.3.1（2026-09-08） |
| 分发渠道 | npx 安装器、Claude Code 插件市场、VS Code Marketplace、Grok Build 插件、Git submodule、ZIP；GitHub Copilot 应用内置（Experimental 开关） |
| Harness 支持 | Claude Code、Cursor、Codex CLI、Gemini CLI、GitHub Copilot、Grok Build、OpenCode、Hermes、DeepSeek Harness、Trae、Qoder、Rovo Dev、Pi、Veto 等 |
| 起源 | Anthropic 官方 frontend-design skill（"Impeccable started from there"——README 原话） |
| 首次登 HN | [2026-01-12，"Impeccable Style"](https://news.ycombinator.com/item?id=46587284)，103 分、64 评论 |

## 模型掷不出自己的骰子：一份罕见的第一手实验记录

impeccable 官网藏了一篇题为 **"The Model Can't Roll Its Own Dice"（模型掷不出自己的骰子）** 的研究笔记，记录了作者团队用真实设计 campaign 做的十几轮实验。它没有 arXiv 编号，但恰恰因为工程现场属性，比很多论文更有说服力。几个核心发现：

**发现一：创意提示词无效，收敛是刚性的。**团队尝试了 16 种"创意框架"——扮演挑剔的客户、使用设计行话、世界观隐喻、痛陈平庸设计之弊——结果 **35 次响应里有 30 次提出了同一个概念**（把页面想象成一条软件请求的 trace 瀑布图）。措辞在变，idea 不变。"对创造力的更强呼吁，把我们一次次带回同一个设计。"

**发现二：拒绝第一个默认值，只会落到第二个默认值。**"写下前三个想法、不看、构建第四个"这类拒绝式提示确实能避开首选，但会**稳定地落在次选上**。换着法子拒绝，得到的还是两个可靠的默认值——分布没有被拓宽，只是在两个峰之间跳。

**发现三：让模型"选最好的"，选择本身就是收敛点。**让模型基于受众推导出 7 个设计方向（每个附理由），清单确实多样了；但接一句"构建最有共鸣的那个"，**30 组实验里 27 组选中了同一个赢家**。多样性死在"选择"这一步。

团队的解法简单到近乎粗暴——**把骰子从模型手里拿走，交给脚本**：

1. **Propose（提议）**：模型基于受众产出一个多样化短名单——这是它擅长的；
2. **Assign（指派）**：脚本从名单中**随机抽取**一个方向——随机性由代码保证；
3. **Build（构建）**：模型实现被指派的方向，并记录复现密钥（reproduction key），抽到不满意的可以重放调查。

这是全文最值得抄走的一个模式：**模型负责"生成相关选项"，代码负责"打破对称性"。**任何用 LLM 做创意性工作（文案、命名、方案探索、UI 变体）的团队都会撞上同一堵墙——LLM 是最大似然机器，"最可能"天然等于"最平庸"，而这个性质无法用提示词修复，只能从架构上绕开。

实验还贡献了几个反直觉的细节。比如**防御性提示词会杀死产出**：他们曾加了一条"戏服检查"（如果访客先注意到借来的形式而不是产品，方案作废），结果发现这条规则会否掉他们自己评为 10/10 的人类参考案例（一个 teletext 风格的网站）；统计下来提示词里**每 1 条鼓励对应 5 条劝阻**，产出变得畏首畏尾。删掉检查、改成"先投入概念，再打磨清晰度"，带来了整个 campaign 最大的单项质量提升。再比如**新皮肤盖不住旧骨架**：一个 teletext 主题页面细节满分（页码标签、像素电平条、四色导航钮），但抽掉颜色纹理后，底下仍是标准营销网格——团队由此提炼出指令"**借形式的骨架，不借它的衣服**"。

## 架构拆解：知识、词汇、检测的三层分离

回到工具本身。impeccable 的架构可以拆成三层，每层解决一个不同的问题。

**第一层：知识外化（PRODUCT.md + DESIGN.md）。**`/impeccable init` 扫描项目、只追问缺失的关键信息，把"持久的产品真相"（受众、目的、使用场景、约束、语气、证据）写入 `PRODUCT.md`；把视觉系统（色板、字体、字号阶梯、圆角、组件规则）写入 `DESIGN.md`。这与 AGENTS.md/CLAUDE.md 是同一个哲学：**上下文不属于对话，属于文件系统**——模型每次醒来都能读到，Agent 换代也不丢。关键设计是两者严格分离：产品事实和视觉方向不能混写，`DESIGN.md` 同时是人类文档和机器可读的 token 契约（检测器拿它当规则源，见下文）。

**第二层：设计词汇表（24 个命令）。**这是最有"前端味"的一层：把模糊的设计批评变成一组**动词 API**。`polish`（发布前最后一遍）、`audit`（a11y/性能/响应式技术检查）、`critique`（UX 设计评审：层级、清晰度、情绪共鸣）、`bolder`/`quieter`（放大/收敛）、`distill`（提炼本质）、`harden`（错误处理、i18n、文本溢出、边界情况）、`onboard`（首次使用流程、空状态）、`animate`、`colorize`、`typeset`、`layout`、`delight`、`overdrive`（炫技效果）、`clarify`（UX 文案）、`adapt`、`live`/`generate`（浏览器内实时变体迭代）……人和 Agent 从此共享同一套设计语汇："给这个定价页 polish 一下，保留我们的直角和冷色板，去掉 AI tells"——这句话在没有词汇表之前，需要三段模糊的自然语言。`/impeccable pin <command>` 还能把常用命令钉成独立快捷方式（如 `/audit`）。

**第三层：确定性检测（61 条规则 + hook 闭环）。**这是与所有"设计提示词合集"的分水岭。检测器是一个自包含二进制（首次运行下载到 `~/.impeccable/bin/`，不依赖 Node、不依赖 LLM、不需要 API key），有三个数据来源：**Source**（静态分析代码和样式，无需浏览器）、**Browser**（检查渲染后的页面，Chrome 扩展或给 CLI 一个 URL）、**Design review**（需要判断力的 6 条模式，交给 LLM critique）。61 条规则分三类：

| 规则类别 | 示例 | 数据源 |
|----------|------|--------|
| **AI slop** | 装饰性网格线背景、圆角卡片侧边彩条、发丝边框+大范围阴影双重描边、重复渐变条纹、径向光晕背景、渐变文字、标题上方的图标底座、斜体衬线大标题、超大 hero 标题、压缩的字间距、滥用字体（Inter/Geist）、深色模式霓虹描边、"AI 配色"（紫渐变+亮青色） | Source / Browser / Design review |
| **Quality** | 过小的界面文字、大段全大写正文、彩色背景上的灰字 | Source |
| **Your design system** | 使用了 DESIGN.md 之外的字体/颜色/圆角/字号——"要么用系统内的值，要么先更新系统" | Source（对照 DESIGN.md） |

第三类尤其聪明：**它把 DESIGN.md 从文档升格为 lint 配置的等价物**——设计系统的漂移（drift）从"设计评审会上的一句抱怨"变成了可自动拦截的 finding。而 hook 机制把检测嵌进 Agent 的工作循环：Agent 编辑 UI 文件 → 设计 hook 触发检测器 → findings 回传给 Agent → Agent 修复 → 复检归零。官网演示的完整闭环是：4 个 tells 被发现（AI beige、斜体衬线、侧边彩条、脉冲圆点）→ 写回源码 → 0 findings。同一套引擎还输出 CLI exit code，可以直接挂进 PR 流水线——**设计审查第一次有了 CI 的形态**。

## 站在 Anthropic 官方 skill 的肩膀上：从提示词到工程闭环

impeccable 明确承认起点是 Anthropic 的 `frontend-design` skill——"第一个被广泛使用的 Claude 设计技能"。读一下官方 skill 的原文，能看出两代方案的差距在哪。

Anthropic 的做法本质上是**高质量提示词工程**：让模型扮演"以独特视觉身份闻名的设计工作室主创"；要求基于题材本身取材（"给 8-11 岁女孩做的玩具和金融分析师的仪表盘必须完全不同"）；两遍工作法（先出 token 化的设计计划，对照 brief 自查"这是为这个 brief 做的选择，还是任何类似页面都会得到的默认值"，再动手）；甚至引用 Chanel 的名言"出门前照照镜子，摘掉一件配饰"。

最有意思的是官方 skill 里那份**精确到十六进制的 tell 清单**：奶油底 `#F4F1EA` + 高对比衬线标题 + 陶土色强调（常为 `#D97757`）——skill 原文特意注明**这是 Anthropic 自家 Claude 界面的强调色**，出现在用户产品里就成了"AI 味"的铁证；近黑底 + 单一酸性绿/朱红强调；发丝线报纸式布局 + 零圆角；SaaS 卡片套装（所有内容切成一样的圆角卡片 + `rgba(0,0,0,.1)` 同款阴影）；模板化 chrome（每个标题上方的全大写 eyebrow 标签、`A · B · C` 式中点连接、`WORD — fragment` 式破折号标签、`#0B0B0B` 式"染色近黑"、小数据标签一律等宽字体、链接尾巴上的"→"）。模型厂商自己把这些默认倾向写进提示词让模型回避——这是"模型知道自己的毛病"的第一手证据。

但提示词方案有两个天花板，恰好被 impeccable 补上：

1. **执行不可验证。**skill 说"避免灰字放彩底"，但没有任何机制确认模型这次真的避开了。impeccable 用确定性检测器把每条"建议"变成可执行断言——建议会漂移，断言不会。
2. **对抗不了统计惯性。**如前文实验所示，提示词层面的"要有创意"在 35 次里输了 30 次。impeccable 的 Propose/Assign/Build 承认这一点，用脚本随机性做结构性对抗。

一个可以概括为：**Anthropic 教模型"什么不要做"，impeccable 给 harness 装上"做了就会被抓"的探测器，再用代码骰子解决"该做什么"的收敛问题。**三者是互补而非替代——事实上 impeccable 的 skill 文件里就嵌着各家模型的"惯犯清单"（按 provider 分 build："plus guidance for common design mistakes made by its models"）。

## 分发即战略：harness 碎片化时代的"可移植技能层"

impeccable 的增长曲线（10 个月 7 万星）离不开它的分发工程。几个值得注意的选择：

- **引擎是单个自包含二进制**，首次运行自动下载缓存；Node 只在 `npx` 安装器这一层出现。这意味着技能可以挂进任何能跑 shell 的 harness，不被 JS 生态绑架。
- **一份 skill，N 个 build**：安装器检测本机已装的 harness（`~/.claude`、`~/.codex`、`~/.grok`、项目级 `.cursor` 等），为每个工具生成对应目录结构和 hook 清单，支持 15+ 个 provider；还能以 Git submodule 方式 vendored 进企业仓库，`npx impeccable link` 统一链接。
- **进入了平台默认位**：GitHub Copilot 应用内置（Settings → Experimental 开启），VS Code Marketplace 上架独立扩展。从"社区技能"到"平台内置"，这是技能类项目能拿到的最强分发。

这与我上周拆解 ECC 时的判断一致：**harness 在持续碎片化，价值在向 harness 之上的可移植层迁移。**ECC 押注的是配置与记忆的可移植，impeccable 押注的是设计知识的可移植——同一场运动的两个切面。当一个技能能同时插进 Claude Code、Cursor、Codex、Copilot、Trae、DeepSeek Harness，它事实上成了一家"跨平台设计部门"，而 61 条规则库就是这个部门的质量手册。

## 冷思考：检测器的三个开放问题

给这个项目泼三盆必要的冷水。

**第一，规则库是滞后指标。**slop 模式随模型代际更替——官网自己用一个"New eras. Familiar model habits"的标签页承认了这一点：紫色渐变是 GPT 时代的味道，beige 编辑风是 Claude 时代的味道，neobrutalist 是另一家的味道。今天的 61 条规则抓的是**上一代模型的默认值**；当所有模型被反馈训练得绕开这些 tell，新的收敛点会出现，规则库要永远追着跑。好消息是它的架构（规则与引擎分离、周更 release 节奏）就是为追着跑设计的；坏消息是这意味着**"0 findings"只等于"没有已知的 AI 味"，不等于"有好设计"**。

**第二，反趋同工具会不会制造新趋同？**如果几十万个项目都用同一套 61 条规则做拦截、用同一批命令做打磨，产出会不会收敛到"impeccable 风格"——一种新的制服？作者在研究页其实已经触碰过这个问题（外部参考池：博物学家的田野手册、报纸体育版——用异领域参考打破同领域收敛），但工具层面的答案目前只有 `/impeccable live` 的变体生成和方向随机指派。这是所有"品味基础设施"的共同悖论：**把品味标准化到可检测的那一刻，也在把它变成新的默认值。**

**第三，判断力的边界。**官网措辞很克制："A finding is a reason to look closer"（一个 finding 只是再看一眼的理由）——规则命中不等于错误，刻意的设计选择可能正好踩在规则上。61 条确定性规则 + 6 条需要 LLM 判断的评审模式，这个配比说明作者清楚哪些能自动化、哪些不能。但 hook 闭环里 Agent 自动修复 findings 时，"把刻意的越界当成 slop 抹平"的风险是真实存在的——v4.2.3 加入"区分新 findings 与存量 findings"和 per-app DESIGN.md，正是在缓解这类误伤。设计系统检查（用了系统外的颜色就报警）在成熟团队手里是护栏，在没有 DESIGN.md 沉淀的团队手里可能只是噪音。

## 结语：三条可迁移的启示

把 impeccable 当作一面镜子，能照出 Agent 工程的三个通用命题：

1. **把模型的默认倾向当作环境事实来工程化。**模型的"惯性"不是缺陷报告里的一行，而是像重力一样的环境常数。提示词只能提醒，架构才能对抗：随机性交给代码（Propose/Assign/Build）、验证交给确定性检查器、判断留给模型。这个三分法适用于设计，同样适用于文案、测试生成、方案探索。
2. **知识写进文件，而不是留在对话里。**PRODUCT.md/DESIGN.md 的本质是把"人类设计师脑子里的上下文"外化成版本控制的契约——人读文档，机器读 lint 配置，同一份文件。这是 AGENTS.md 模式在设计域的复刻，也再次验证：**Agent 时代的基础设施是 Markdown。**
3. **技能的分发能力决定技能的影响力。**同样的 61 条规则，锁在一个 harness 里是玩具，跨 15 个 harness + 平台内置 + PR 流水线才是基础设施。当"设计审查"有了 exit code，它才真正进入工程的话语体系。

十年前，前端行业用 ESLint 把"代码风格之争"从 code review 的口水战变成了流水线上的红绿灯。impeccable 正在对"设计品味之争"做同样的事——它未必是终局（规则库的滞后性和新趋同悖论都还开着），但方向大概率是对的：**AI 生成内容的质量控制，最终不会靠更聪明的模型自觉，而是靠模型外面那圈诚实的、确定性的、可以被 CI 调用的探测器。**

---

## 参考资料

- [pbakaus/impeccable（GitHub）](https://github.com/pbakaus/impeccable) · [官网 impeccable.style](https://impeccable.style)
- [The Model Can't Roll Its Own Dice（impeccable 研究笔记）](https://impeccable.style/research/)
- [Slop 规则目录（61 checks）](https://impeccable.style/slop) · [Changelog](https://impeccable.style/changelog/) · [FAQ](https://impeccable.style/faq/)
- [Anthropic frontend-design skill](https://github.com/anthropics/skills/tree/main/skills/frontend-design)
- [Neo Mirai 案例研究](https://impeccable.style/cases/neo-mirai)
- Hacker News 讨论：[Impeccable Style（2026-01-12，103 分）](https://news.ycombinator.com/item?id=46587284)
- 本系列相关：[ECC：Agent Harness 操作系统](https://github.com/kejun/blogpost/blob/main/2026-09-21-ecc-agent-harness-operating-system.md) · [前端 AI Coding 常见问题全景](https://github.com/kejun/blogpost/blob/main/2026-09-19-ai-coding-frontend-common-problems.md) · [Shopify 收购 Tailwind](https://github.com/kejun/blogpost/blob/main/2026-09-10-shopify-acquires-tailwind-llm-era-ui-standard.md)

*数据截至 2026-09-24 08:00（Asia/Shanghai），星数等指标以 GitHub API 实时查询为准。*
