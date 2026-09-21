# 当 Claude Code 有了自己的"操作系统"：ECC 26 万星背后的上下文经济学、本能学习与 Harness 工程

> 2026-09-21 · AI技术 · 本文约 4700 字

## 一个不含模型代码的 Trending 第一

9 月 21 日，GitHub Trending 第一名不是模型，不是框架，而是一个几乎不含"产品代码"的仓库：`affaan-m/ECC`。截至本文写作，它的数字是：**263,715 stars、39,453 forks、208 个开放 issue**——而它诞生于 2026 年 1 月 18 日，只有八个月历史，平均每天净增约 1,072 颗星。

ECC 这个名字是刻意模糊的。它的前身叫 `everything-claude-code`——作者 Affaan Mustafa 把自己使用 Claude Code 的全部个人配置（agents、skills、hooks、rules、记忆系统）公开成仓库。今年 3 月一条 X 长帖让它一周内暴涨 2.5 万星；6 月的 v2.0 版本直接把定位改成了 **"The Agent Harness Operating System"（Agent Harness 操作系统）**，仓库也随之改名为三个字母的 ECC。

核心数字一览：

| 维度 | 数据 |
|------|------|
| Stars / Forks | 263,715 / 39,453（创建于 2026-01-18） |
| 内容物 | 68 个 agents、292 个 skills、94 个 command shims + hooks/rules/memory/安全工具 |
| 许可与商业模式 | MIT 开源 + ECC Pro（$19/seat/月，私有仓库 GitHub App） |
| npm 下载量（ecc-universal） | 周 7,625 / 月 26,069 |
| Harness 支持 | Claude Code（稳定）、Codex（原生插件）、Cursor/OpenCode（beta）、Copilot/Gemini/Zed/Antigravity/Qwen/Hermes/OpenClaw/Kimi 等（实验） |
| 版本节奏 | v2.0（6/10）→ v2.1（7/27）→ v2.2（8/28）→ v2.2.1（9/8），周更 |
| 赞助商 | CodeRabbit、Greptile、Moonshot AI（Kimi）、Itô Markets、SerpApi |

为什么值得认真拆？因为 ECC 代表了一个很少被正面讨论的信号：**当模型快速商品化，AI 编程的竞争重心正在从"模型本身"转移到"harness"——模型外面那圈脚手架：上下文管理、流程纪律、记忆、安全。** ECC 是第一个把这圈脚手架做成完整"操作系统"并获得大规模采用的项目。它的口号只有八个词，但信息量极大：

> **"Optimize the context window. Persist everything else."**（优化上下文窗口，其余一切持久化。）

## 上下文窗口就是 RAM：一个字面意义上的 OS

理解 ECC 的最好方式，是把它的口号当真：它确实在用操作系统的隐喻管理 Agent。上下文窗口是稀缺的、易失的 RAM；其他一切——记忆、技能、规则、学到的行为——都应该像磁盘上的数据一样持久化，按需换入换出。

把 ECC 的组件逐个映射到 OS 概念，会发现这个类比惊人地完整：

| OS 概念 | ECC 对应物 | 说明 |
|---------|-----------|------|
| RAM | 上下文窗口（200k） | 一切设计的出发点：稀缺、昂贵、易失 |
| 磁盘 | Memory Vault + session 文件 | "Persist everything else" 的落地 |
| 内核态拦截 | hooks（PreToolUse/PostToolUse/Stop/SessionStart） | 确定性执行点，不依赖模型自觉 |
| 进程 | 68 个 agents | 各有角色、工具白名单、指定模型 |
| 应用程序 | 292 个 skills | 按需加载的能力包，lazy loading |
| 系统调用 | 94 个 command shims | `/plan`、`/tdd`、`/code-review` 等标准入口 |
| 驱动程序 | instincts（本能） | 从使用中自动学到的低层行为 |
| 权限系统 | rules + GateGuard + AgentShield | 从行为规范到安全审计的完整边界 |
| 休眠/唤醒 | PreCompact hook + SessionStart hook | 压缩前存盘、启动时恢复 |

这不是修辞。看几个具体的"内核机制"：

**动态系统提示注入。** 与其把所有规范塞进每次会话都加载的 CLAUDE.md，ECC 建议按场景准备多份 context 文件，用 shell alias 动态注入：

```bash
alias claude-dev='claude --system-prompt "$(cat ~/.claude/contexts/dev.md)"'
alias claude-review='claude --system-prompt "$(cat ~/.claude/contexts/review.md)"'
alias claude-research='claude --system-prompt "$(cat ~/.claude/contexts/research.md)"'
```

开发、评审、研究三种"人格"各占一份文件，需要哪个换入哪个——这就是 RAM 的按需分页。

**会话间记忆文件。** 每个 session 结束前让 Agent 写一份状态摘要到 `.tmp` 文件，内容强制包含三类信息：哪些方法**已验证有效**（带证据）、哪些**试过但失败**、哪些**还没试**。下一个 session 只传文件路径。失败的尝试被显式记录，防止新会话重蹈覆辙——这是把"防重复踩坑"做成了数据结构。

**MCP 是"内存泄漏"。** ECC 的一个反流行观点：不要常开一堆 MCP server。每个 MCP 的工具描述都常驻上下文，十个 MCP 能把 200k 窗口吃到只剩约 70k。它的建议是激进但务实的：**能用 CLI 的 MCP 一律换成 CLI + skill**——GitHub MCP 换成一个包装 `gh pr create` 的 `/gh-pr` 命令，Supabase MCP 换成直接调 Supabase CLI 的 skill。功能不变，常驻内存归零。

## 五大子系统拆解

### 1. 进程调度：五阶段流水线与"迭代检索"

ECC 的编排核心是一个五阶段 orchestrator，每阶段绑定专职 agent，产出物落盘为文件：

```
Phase 1: RESEARCH (Explore agent)     → research-summary.md
Phase 2: PLAN     (planner agent)     → plan.md
Phase 3: IMPLEMENT (tdd-guide agent)  → 代码变更
Phase 4: REVIEW   (code-reviewer)     → review-comments.md
Phase 5: VERIFY   (build-error-resolver) → 通过或回环
```

铁律是：每个 agent 一个明确输入、一个明确输出；输出即下一阶段的输入；不许跳阶段；agent 之间执行 `/clear` 释放上下文。

比流水线更有洞察的是它对**子代理上下文问题**的正面处理：orchestrator 掌握任务的语义背景，而子代理只拿到字面 query，不知道"为什么要查这个"。ECC 的解法是迭代检索模式——orchestrator 必须评估子代理的每一次返回，不满意就带着追问让它回到源头再查，最多循环三轮，并且"传递目标上下文，而不只是查询本身"。这解决了多 Agent 系统里最常见的信息折损问题。

并行化上，ECC 的态度意外地保守：明确反对"开 N 个终端"的表演式并行，主张**最小可行并行**——用 git worktree 给每个实例独立工作区，用"级联法"管理（新任务开在右侧标签，从左到右扫，同时在手的任务不超过 3-4 个）。

### 2. 记忆层次：从 .tmp 文件到 Memory Vault

ECC 的记忆是三层结构：会话内（strategic compact）、会话间（.tmp 状态文件 + memory hooks）、跨 harness（Memory Vault）。最值得说的是最外层。

`ecc memory` 命令和 `memory_save` 工具把会话中值得保留的上下文写成标准化的 `ecc.memory.v1` Markdown 文档，带完整 frontmatter（scope、trust、type、status）和固定分区（Summary / Grounding / Handoff / Body / History）。scope 分三级：project（默认，存 `.ecc/memory/`）、team（显式路径）、user（`~/.ecc/memory/`，必须显式 opt-in）。

几个安全设计显示了作者对"记忆即攻击面"的清醒：

- **create-only 语义**：未经 review 的记忆可以被保存和检索，但永远不会伪装成"精选知识"混入高信任上下文；
- **最小工具面**：记忆 MCP server 只暴露 4 个工具（save/search/read/doctor），刻意压缩注入面；
- **server-bound identity**：环境变量 `ECC_MEMORY_HARNESS` 只是身份声明，不是信任凭证——"frontmatter 里写 user scope，不等于真的能写进 user 域"；
- **fail-closed .gitignore**：user scope 永不进 git，项目级记忆共享前自动脱敏（git author、路径、邮箱替换为占位符）。

README 里那句话应该裱起来：**"Memory is unreviewed context, not executable policy."**（记忆是未经审查的上下文，不是可执行策略。）记忆可以加载为上下文，但绝不能被自动执行——这一条划清了"记忆系统"和"提权漏洞"的界线。

跨 harness 是 Memory Vault 的杀手场景：你在 Hermes 里调研完一个方案，`ecc memory save` 落盘，切到 Codex 实现时直接 `ecc memory search` 取回——**记忆跟着项目走，而不是跟着某个厂商的客户端走**。

### 3. 学习系统：instincts——不动权重的统计式自我改进

如果说记忆是"存盘"，Continuous Learning v2.1 的 instincts（本能）就是 ECC 最原创的部分：**让 Agent 从你的使用行为中自动学出可量化、可审计、可回滚的行为倾向——完全不碰模型权重。**

机制拆开看：

1. **观察**：PreToolUse/PostToolUse hooks 捕获每次提示、工具调用和结果（v1 用 Stop hook 只在会话结束观察，v2 改为逐工具调用观察，可靠性 100%）；
2. **分析**：后台 Haiku agent 读取观察日志，识别三类模式——用户纠正（"不要用 class，用函数式"）、错误解决路径、重复出现的工作流；
3. **结晶**：每个模式写成一条原子 instinct——一个 trigger、一个 action、一个 0.3-0.9 的置信度、领域标签、证据记录：

```yaml
id: prefer-functional-style
trigger: "when writing new functions"
confidence: 0.7
domain: "code-style"
scope: project
---
## Action
Use functional patterns over classes when appropriate.
## Evidence
- Observed 5 instances of functional pattern preference
- User corrected class-based approach on 2025-01-15
```

4. **进化**：`/evolve` 把相关 instincts 聚类升级为正式的 skill、command 甚至 agent；`/instinct-export` 可以打包分享给别人——你的 Agent 直觉变成了可流通的资产。

v2.1 补上了关键一块：**项目级隔离**。instincts 默认按 git remote/repo path 哈希存到项目专属目录，React 习惯不会污染 Python 项目；只有当一个 instinct 在 2 个以上项目中独立出现，才通过 `/promote` 升级为全局。这是对"跨项目污染"这个自我改进系统经典失败模式的正面回答。

注入侧同样克制：默认最多注入 6 条 instincts，置信度阈值 0.7，按技术栈匹配度排序。学到的东西不是无脑全塞回上下文，而是过一遍"相关性 + 置信度"的门控。

把 instincts 放进 2026 年的坐标系里看会更清楚它的意义：Agent 自我改进目前有两条路——**改权重**（RL/微调：贵、慢、不透明、有灾难性遗忘风险）和**改上下文先验**（instincts：便宜、即时、每条都有证据可审计、随时可删）。ECC 选了后者，并用置信度加权做出了类似 explore/exploit 的统计结构。这条路线的上限或许不如 RL，但工程性价比和可控性完胜——这与本专栏写过的"混合确定性 Agent 架构"（2026-07-24）、"Agent 控制工程学"（2026-09-14）是同一条思想脉络的延伸：把概率系统关进确定性的笼子里，笼子本身要能学习。

一个真实案例：今年 5 月 Show HN 上的 Jynx（游戏队友匹配 App），21.4 万行 Dart、23 个功能模块，全程用 Claude Code 开发，其工程底座正是 ECC 的 instincts 体系——22 个 hooks、18 个 skills、13 条 instincts、8 份 rules。单人 + Agent + 学到的本能，交付了一个双端上架的商业级应用。

### 4. 安全内核：AgentShield 与"配置文件即攻击面"

ECC 可能是第一个把"Agent 配置本身当作安全审计对象"的主流项目。其独立工具 AgentShield（npm 包 `ecc-agentshield`，诞生于 2026 年 2 月 Anthropic 官方 Claude Code Hackathon）扫描的正是你天天加载却从不 review 的东西：CLAUDE.md、settings.json、MCP 配置、hooks、agent 定义、skills，共五类风险——秘密泄露（14 种模式）、权限审计、hook 注入分析、MCP server 风险画像、agent 配置审查。102 条静态分析规则，1,282 个测试，98% 覆盖率。

最有意思的是 `--opus` 模式：起三个 Opus 4.6 agent 跑红队/蓝队/审计员流水线——攻击者找利用链，防御者评估防护，审计员综合定级。用对抗推理补静态扫描的盲区，输出 A-F 分级，critical 发现直接 exit code 2 卡住 CI。配套的运行期防线是 GateGuard：在 `rm`、`git checkout --force`、`find -exec` 这类破坏性命令执行前做 hook 级拦截。

ECC 对供应链的态度也值得一抄：README 开头就警告**存在带恶意代码的假镜像**，并列全六个官方安装路径；AgentShield 文档甚至强调"registry 上架不等于审计，安装记录要写明版本、来源和完整性校验"。这与我在《AI Agent Skills 供应链安全危机》（2026-06-14）里的判断一致：skills/hooks/配置文件就是新的可执行代码，而大多数团队还在把它们当"配置"随意复制粘贴。

### 5. 成本调节器：token 经济学的工程化

ECC 给出的成本优化不是理念而是一张参数表：

| 设置 | 默认 | 推荐 | 效果 |
|------|------|------|------|
| `model` | opus | **sonnet** | 成本降约 60%，覆盖 80%+ 编码任务 |
| `MAX_THINKING_TOKENS` | 31,999 | **10,000** | 每请求隐性思考成本降约 70% |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | 95 | **50** | 提前压缩，长会话质量更好 |
| `CLAUDE_CODE_SUBAGENT_MODEL` | — | **haiku** | 子代理一律用最便宜的合格模型 |

再叠加模型路由纪律（探索/简单编辑/写文档 → Haiku；多文件实现/PR 评审 → Sonnet；架构/安全/复杂调试 → Opus）、MCP 数量红线（<10 个 server、<80 个工具）、用 mgrep 替代 grep（官方引用的 50 任务基准显示 token 消耗约为 grep 工作流的一半），以及"战略性压缩"——在研究完成、里程碑结束等逻辑断点手动 `/compact`，而不是等 95% 时被动触发。

还有一个容易被忽略的评估指标选择问题。ECC 在文档里明确区分了两种 pass 率：

```
pass@k：k 次尝试至少成功一次   k=1: 70%  k=3: 91%  k=5: 97%
pass^k：k 次尝试全部成功       k=1: 70%  k=3: 34%  k=5: 17%
```

"能用就行"看 pass@k，"必须稳定"看 pass^k——同一个 Agent，两种口径下是完全不同的产品。大多数团队 demo 时用 pass@k 的直觉，上线后才发现用户要的是 pass^k。

## 生态坐标：skills 战争的"元层"

把 ECC 放进 2026 年 9 月的时间切片，能看到一条清晰的演化链：

1. **格式标准化**：Anthropic 的 Agent Skills 开放标准（2025-10）统一了 skill 的文件格式；AGENTS.md 成为跨工具的项目说明标准（本专栏 2026-09-19）。
2. **单点爆款**：`cloudflare/security-audit-skill` 一个 skill 拿下 18k stars（2026-09-17）。
3. **集合库**：`addyosmani/agent-skills` 97k stars——今天和 ECC 同在 Trending 前列。
4. **元层**：ECC——不止提供 skills，而是提供整个 harness 的"发行版"：agents + skills + hooks + rules + 记忆 + 学习 + 安全审计 + 跨 harness 移植。

第 4 层的出现意味着 harness 配置本身成了独立的软件品类。而 ECC 押注的另一个判断是：**harness 会持续碎片化**（Claude Code、Codex、Cursor、Copilot、OpenClaw、Kimi……），所以它把宝押在"可移植层"上——94 个 command shim 就是抽象层，同一套语义在不同 harness 上翻译执行，Memory Vault 让记忆跨客户端流转。其支持矩阵难得地诚实：Claude Code 稳定、Codex 原生、Cursor/OpenCode beta、Copilot 只有 instructions（"没有 agents/hooks，ECC 的价值大打折扣"是 README 原话）、Windows 平台连 GAN 编排路径都缺。"universal"目前更多是方向而非现状，但这种把 gap 写在明面上的工程文化，本身就是它口碑的一部分。

商业模式也值得注意：MIT 开源打底，ECC Pro（$19/seat/月）把私有仓库的深度分析（10k+ commits、自动 PR、团队共享）做成 GitHub App 收费，赞助商名单里同时出现 CodeRabbit、Greptile 两家代码评审公司和 Moonshot AI——一个"个人配置仓库"已经长出了一条 agent infra 的商业食物链。

## 冷静看：操作系统，还是膨胀软件？

赞美之后，几个必须直面的问题：

**一是星标与使用的落差。** 26.3 万 stars，npm 周下载却只有 7,625。当然，claude plugin 安装不走 npm、大量用户只"阅读"不安装（ECC 的方法论价值确实可以只读获取，如同 awesome 清单），但这个 30 倍以上的落差仍提示：相当一部分星标是"收藏式学习"而非生产部署。ECC 的真实护城河不是那 292 个 skills——它们大多可被复制——而是方法论叙事 + 社区品牌 + 更新速度。

**二是膨胀悖论。** 292 个 skills、68 个 agents，全量安装本身就违背 ECC 自己的上下文经济学。项目方的答案是 profile 分级安装、skill-first 策略、lazy loading、`/context-budget` 审计——但"需要一套治理体系来治理 292 个技能"这个事实，恰好印证了 Ponytail 式"反过度工程"（本专栏 2026-09-06）的批评：大多数开发者的最优解可能是通读 ECC 文档，然后手搓 15 个属于自己的 skills。ECC 更大的价值是"教材"而非"依赖"。

**三是 bus factor。** 一个单人维护者，周更节奏横跨十来个 harness。这既是"一人即公司"新杠杆的惊人样本（Agent 反过来帮他维护 Agent 的配置——ECC 的 CHANGELOG 里大量条目就是 Agent 协作的产物），也是真实的单点风险：一旦作者弃坑或方向漂移，26 万星的项目没有治理结构可以接住。赞助与 Pro 收入是可持续性的尝试，但目前更像个人项目而非基金会项目。

**四是学习系统的攻击面。** instincts 的观察-结晶管道意味着：**持续向 Agent 输入特定"纠正"，就能定向植入低置信度本能，再等它们被 `/evolve` 聚合成 skill**。证据字段和置信度门控提高了攻击成本，但没有改变"从环境学习"固有的投毒风险。Memory Vault 的 create-only 设计防的是记忆冒充策略，防不了记忆污染判断。AgentShield 用对抗扫描审自己的配置是对的方向，但"自我改进系统的安全性"目前全行业都没有成熟答案。

## 对开发者的启示

即使你一行 ECC 都不装，也值得带走这几件事：

1. **Harness engineering 正在成为一门显学。** 上下文经济学（什么常驻、什么换页）、流程纪律（验证闭环、证据留痕）、记忆分层（会话内/会话间/跨工具）——这些会像"微服务架构"一样出现在职位描述里。
2. **抄模式，别抄清单。** 模型路由表、session 状态文件（有效/失败/待办三分法）、`/clear` 纪律、pass@k 与 pass^k 的口径区分、MCP→CLI+skill 的替换——每一个都是几十行配置就能落地的独立模式。
3. **把 Agent 配置当代码治理。** 你的 CLAUDE.md、hooks、skills 应该进 git、过 review、跑扫描。`agentshield scan --path .` 可以直接白嫖（npm 全局安装即可），哪怕不用 ECC 的其他部分。
4. **自我改进从"上下文先验"做起。** instincts 的 confidence + evidence + scope 三元组，是任何想让 Agent"越用越顺手"的系统都值得参考的最小设计——比微调便宜三个数量级，比塞 CLAUDE.md 严谨三个数量级。

## 结语

ECC 的 26 万星，本质是开发者社区用星标投票承认了一件事：**模型不再是唯一的变量。** 当 Claude Code、Codex、Cursor 像浏览器一样可以随手更换，真正稀缺的是那层可移植的工程方法论——它决定同一个模型在你手里是玩具还是生产力。

从 prompt engineering 到 context engineering，再到今天初现轮廓的 harness engineering，这门学科的名字还在变，但 ECC 已经写下了它的第一份"内核源码"。八个月，一个人，26 万星——这本身可能就是文中最强的一条 instinct：**在 Agent 时代，把个人工作流产品化，是杠杆率最高的开源路径。**

---

**参考链接：**
- GitHub: [affaan-m/ECC](https://github.com/affaan-m/ECC)（MIT，263.7k stars，前身 everything-claude-code）
- 官网: [ecc.tools](https://ecc.tools) / GitHub App: [apps/ecc-tools](https://github.com/apps/ecc-tools)
- npm: [ecc-universal](https://www.npmjs.com/package/ecc-universal) / [ecc-agentshield](https://www.npmjs.com/package/ecc-agentshield)
- 作者的三条源头长帖: [abbreviated guide](https://x.com/affaan/status/2012378465664745795) / [longform guide](https://x.com/affaan/status/2014040193557471352) / [security setup](https://x.com/affaan/status/2033263813387223421)
- 仓库内文档: [the-longform-guide.md](https://github.com/affaan-m/ECC/blob/main/the-longform-guide.md) / [continuous-learning-v2](https://github.com/affaan-m/ECC/tree/main/skills/continuous-learning-v2) / [token-optimization](https://github.com/affaan-m/ECC/blob/main/docs/token-optimization.md)
- AgentShield: [github.com/affaan-m/agentshield](https://github.com/affaan-m/agentshield)
- 实际案例: [Show HN: Jynx](https://news.ycombinator.com/item?id=48336119)（214k 行 Dart，22 hooks / 18 skills / 13 instincts）
