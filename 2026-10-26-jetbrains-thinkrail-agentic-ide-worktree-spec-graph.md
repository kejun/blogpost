# 当 IDE 开始围着 Agent 重写：JetBrains ThinkRail 深度拆解——git worktree 工作区、SPEC.md 图谱与「薄壳」哲学的代价

> 2026 年 10 月 25 日，一个叫 ThinkRail 的项目同时出现在 Hacker News 首页的两条讨论里：`JetBrains Thinkrail`（159 分、111 条评论）和前一天发布的 `ThinkRail from JetBrains`（56 分、81 条评论）。GitHub Trending 上它当天涨了 675 星，总星数 1,688，仓库 7 月 8 日才创建，8 月 19 日才第一次公开——三个月的项目，被拿来和 Cursor、Claude Code、Codex CLI 放在同一张桌子上讨论。
>
> 但真正值得写的不是"JetBrains 也做了个 AI IDE"。而是它选了一条和所有人的相反的路：**不做模型、不做 Agent 内核、甚至不做编辑器内核，只做三层东西——git worktree 隔离、turn 级快照审查、SPEC.md 图谱。** 官方原话是"ThinkRail is on purpose a thin layer on top of Pi"。
>
> 这篇拆解四件事：为什么"薄"在这个时间点反而是优势；worktree 并发模型真实的成本结构；turn 级 diff 为什么是对 Agent 可观测性的一次修正；以及 spec-driven development 最大的问题——**当 spec 本身由模型生成时，它到底是护栏，还是自我确认的幻觉**。

---

## 一、先把事实摆清楚：三个月，1,688 星，一个 incubator 项目

关键数据（截至 2026-10-26 00:00 UTC，来自 GitHub API 与 Trending 页面）：

| 指标 | 数值 |
|------|------|
| 仓库 | `JetBrains/thinkrail` |
| 创建时间 | 2026-07-08 |
| 首次公开发布 | 2026-08-19（Introducing ThinkRail） |
| Stars / Forks | 1,688 / 102 |
| 单日新增 Star | 675（GitHub Trending，10-25） |
| Open Issues | 199 |
| 最近提交 | 2026-10-25 22:50 UTC |
| License | Apache-2.0 |
| 最新版本 | v0.3.0-nightly.6（10-25）；稳定版 v0.2.0（10-18） |
| 形态 | 原生桌面应用（Electrobun 打包）+ `thinkrail` CLI 打开同一套 Web UI |

它依赖的上游同样值得摆出来：

| 指标 | 数值 |
|------|------|
| 上游 Agent | `earendil-works/pi`（pi coding agent） |
| pi Stars | 117,780（MIT） |
| npm 月下载 | 15,807,646 次（2026-09-23 → 10-22，`@earendil-works/pi-coding-agent`） |
| 集成方式 | 以库的形式嵌入 ThinkRail 进程，共用 `~/.pi` |
| 应用状态目录 | `~/.thinkrail` |

把这两张表放在一起看，第一个结论就出来了：**ThinkRail 不是一个新 Agent，它是一个给已经有 117k 星、月下载 1500 万次的 Agent 加壳的产品。** 这解释了它为什么能在三个月内做出可用版本——Agent 的推理循环、工具调用、上下文管理、provider 适配，全部由 pi 负责；JetBrains 只需要做"壳"该做的事。

而这个"壳"的选择，恰好踩在 2026 年 IDE 竞争最痛的那个点上。

---

## 二、IDE 的三次抽象：为什么"薄壳"这次是优势

过去三年，带 AI 的编辑器经历了三次抽象迁移，每一次都在换"谁是主体"：

**第一次（2021–2023）：编辑器是主体，AI 是补全。** Copilot 把模型塞进光标位置，交互单位是"一行/一个函数"。IDE 的架构几乎没变，只是多了一个 inline suggestion provider。

**第二次（2024–2025）：聊天是主体，编辑器是结果展示区。** Cursor、Windsurf 把整个编辑器 fork 掉，围绕 chat 重排 UI。这时候出现了第一批结构性矛盾：diff 怎么展示、多文件改动怎么审查、Agent 跑飞了怎么回滚。答案通常是"做一个更好的 diff 面板"。

**第三次（2026）：Agent 是主体，IDE 退化成"观测与干预界面"。** 一旦 Agent 能连续跑几十分钟、开子 Agent、改几十个文件，人的角色就从"写代码"变成"分配任务 + 审查结果 + 处理异常"。这时候 IDE 真正需要提供的能力只剩三类：

1. **隔离**：让多个 Agent 同时跑而不互相踩；
2. **审查**：把 Agent 的副作用变成可逐块接受/拒绝的事实；
3. **上下文治理**：让 Agent 在跨会话时仍然知道"这个项目为什么是这样"。

ThinkRail 的三层设计——worktree 工作区、turn 级 Review、SPEC.md 图谱——正好一一对应。它没有去卷"谁的补全更准""谁的 Agent 更聪明"，因为那两件事它做不了也不该做。JetBrains 官方博客写得很直白：

> ThinkRail is on purpose a thin layer on top of Pi; nothing about how the agent thinks, what it is allowed to do, or how it manages context is ThinkRail's to reinvent.

这句话在工程上是有代价的（后面会讲），但在产品定位上极其清醒：**当 Agent 内核的迭代速度是"每周一个 breaking change"时，任何在壳里重新实现 Agent 的公司，都会把 80% 的工程预算花在追赶上游。**

顺带说一句商业背景：JetBrains 自己在 2025–2026 年过得并不轻松，主力 IDE 的订阅增长被 VS Code + AI 插件侵蚀，AI Assistant 的口碑也一直不温不火。ThinkRail 挂在 `JetBrains/thinkrail` 下、带 `incubator` 徽章，本质是一次低成本下注：**用最小的团队验证"Agent 工作台"这个形态，成了就收编进 Fleet/IntelliJ 体系，不成就当一个开源实验。** 199 个 open issue 和高频 nightly，说明它现在确实还在"实验"阶段，而不是"产品"阶段。

---

## 三、架构拆解 A：把 git worktree 当作一等公民

ThinkRail 最核心、也最容易被低估的设计，是"每个 workspace 就是一个真正的 git worktree"。

### 3.1 它到底怎么落地

打开一个 git 仓库作为 project，点 "Start building"，选一个 base branch，写一句任务描述——这句话同时是 workspace 名字和 Agent 的初始 prompt。然后：

- 在 `~/.thinkrail/worktrees/<project-name>/workspace-N` 下创建一个 worktree；
- 给它自己的分支、自己的工作目录；
- 在里面启动一个 pi 会话，Agent 立刻开始干活。

你的主 checkout 完全没被碰过。打开原来的 IDE，看到的还是干净的 main。

这个设计的技术基础是 git 的一个老特性：`git worktree add`。它和 `git clone` 的关键区别在于：

| 维度 | `git clone` | `git worktree add` |
|------|-------------|--------------------|
| 对象库 | 完整复制一份 `.git` | 与原仓库共享 object store |
| 创建成本 | O(仓库大小)，秒级到分钟级 | O(元数据)，毫秒级 |
| 分支约束 | 独立仓库，随便检出 | 同一分支不能被两个 worktree 同时检出 |
| 磁盘占用 | 每个副本一份 | 只多一份工作区文件 |
| 与主仓库的关系 | 弱（靠 remote 同步） | 强（共享 refs、共享 reflog 之外的元数据） |

对"一个任务开一个工作区"这种高频、短生命周期的场景，worktree 的成本模型是决定性的。如果一个 workspace 要 clone 一次 2GB 的仓库，没人会在一天里开十个；但 worktree 是毫秒级的，开十个的心理成本接近于零。**产品形态是被底层原语的成本曲线决定的**——这一点在 ThinkRail 之前，只有少部分做 Agent 编排的团队想明白。

### 3.2 "Settled shelf"：一个被认真设计过的生命周期

大多数同类产品的工作区列表是只增不减的，用一周就变成垃圾场。ThinkRail 0.2.0 引入了 Settled shelf（沉降架）：workspace 会在两种情况下自动移到一个"已沉降"分区——

- 它的 PR 被 merge 或 close；
- 连续 7 天没有"活动"（可在 Settings 里改成 1/3/7/14 天或永不）。

注意官方对"活动"的定义：**chat turn、终端输入、HEAD 移动**，而不是"你打开看了一眼"。这个细节很关键——它区分了"消费"和"生产"。你在窗口里滚动 diff 不算活动，因为那不会让工作区变得更有价值；只有产生新提交、新对话、新命令才算。

同时它给了两个显式覆盖：`Settle` 和 `Keep active`。这是一个典型的"自动化为默认、手动为逃生舱"的设计。

### 3.3 并发不是免费的：worktree 模型的四个真实成本

这是大多数吹 worktree 的文章会跳过的部分。我把代价列清楚：

**成本一：依赖缓存不共享。** 每个 worktree 是独立的工作目录，`node_modules`、`.venv`、`target/`、`build/` 都要各自装一遍。一个中型前端项目 800MB 依赖，开五个 workspace 就是 4GB。pnpm 的全局 store 能缓解（硬链接复用），但 npm/yarn 用户会直接感受到磁盘和安装时间的放大。

**成本二：端口、数据库、容器名冲突。** 五个 Agent 同时跑 `npm run dev`，五个都想要 3000。五个都跑 `docker compose up`，容器名撞车。ThinkRail 本身不解决这个问题——它只保证文件系统隔离，不保证运行时隔离。你需要自己在项目里约定端口偏移、数据库 schema 前缀、compose project name。**这是"文件隔离 ≠ 环境隔离"的经典陷阱。**

**成本三：合并成本被推迟，而不是被消除。** 隔离的好处是并行，代价是最后要合并。五个 Agent 各自改了同一个 `types.ts`，合并时你还得人肉解冲突。worktree 把"实时冲突"变成了"结算冲突"，这在任务彼此独立时是纯赚，在任务高度耦合时是纯亏。判断标准很简单：**如果两个任务会改同一批文件，就不要开两个 workspace。**

**成本四：同一分支不能双开。** git 的硬约束。ThinkRail 的处理是每个 workspace 自动建新分支，这规避了冲突，但也意味着分支数量会膨胀——一个项目跑一个月，远程仓库里可能躺着几十个 `thinkrail/xxx` 分支。需要配套的分支清理策略（好在 PR merge 后会自动沉降 + 可以删远端分支）。

---


## 四、架构拆解 B：turn 级快照——把"Agent 说它做完了"变成文件系统事实

ThinkRail 0.2.0 最狠的一个功能，官方叫 "Every turn gets a receipt"（每一轮都有一张收据）。作者的原话很扎心：

> The agent finishes, says it's done, and I scroll the transcript trying to piece together what it actually changed. That isn't a review. It's archaeology.

翻译：**Agent 说"完成了"，然后你在聊天记录里往上翻，试图拼凑它到底改了什么。那不叫 review，那叫考古。**

### 4.1 实现细节里藏着真功夫

具体机制：当一轮 run 开始时，宿主（host）对 worktree 做一次快照；run 结束时再做一次。两相比较，得出 `3 files changed · +27 −4` 这样一行收据，外加一个 "Review turn" 按钮。

三个实现细节值得单独拎出来：

**第一，数字不来自 Agent 的工具调用记录，而来自文件系统快照。**

这是本质区别。如果统计来源是 Agent 的 `edit_file` 调用，那么以下行为全部会漏掉：

- Agent 跑了一个 `sed -i` 或 `python script.py` 批量重写文件；
- Agent 跑了 `prettier --write` / `gofmt` / `cargo fmt`；
- Agent 用 `git mv` 做了重命名；
- Agent 调用某个 codegen 工具生成了文件。

这些都不经过"编辑工具"，但都真实改变了代码。**只有快照对比才能捕获"副作用"，工具日志只能捕获"意图"。** 这个区别在 Agent 时代被无限放大，因为 Agent 最常见的失败模式恰恰是"它以为它改了，其实改的是另一个路径"或者"它跑了脚本改了 40 个文件但只报告了 3 个"。

**第二，快照不碰 HEAD、index 和 reflog。**

这句话信息量很大。它意味着实现上不能用 `git stash`（会动 index 和 reflog），也不能 `git commit` 一个临时提交（会动 HEAD）。可行的路径大致是：直接读工作区文件树 + 用独立的临时 index 文件（`GIT_INDEX_FILE` 指向别处）做 tree 对象比较，或者干脆在文件系统层做 content hash 的集合差分。无论哪种，设计意图是一致的——**审查功能不能污染被审查对象的 git 状态**。用户随时可以 `git status` 看到一个干净的、符合预期的仓库。

这是个很小但很专业的决定。很多 Agent 工具为了实现"自动提交/自动回滚"，会在仓库里塞 `refs/agent/xxx` 或者直接 commit，结果用户的 `git log` 变成一堆噪音。

**第三，hunk 级的 Keep / Revert 用内容哈希做 key。**

> Keep is keyed to the hunk's content, so it survives line shifts and lapses when the agent edits that hunk again.

这是一个被绝大多数 diff 工具忽略的问题。传统 diff 用"文件路径 + 行号区间"标识一个 hunk。但 Agent 的工作方式是持续编辑——你刚标记"这个 hunk 我接受了"，Agent 又在上面插了三行，行号全变了，你的标记就错位了。用内容哈希做 key，行号漂移不影响；而如果 Agent 真的又改了这个 hunk 的内容，哈希变化，标记自动失效——这正是你想要的语义。

### 4.2 为什么"按 turn 审查"比"按 chat 审查"更符合 Agent 的工作方式

人在写代码时，一个 commit 是一个逻辑单元；Agent 在跑任务时，一个 **turn** 才是一个逻辑单元——一次"思考 → 调工具 → 观察 → 再思考"的闭环。一次任务可能包含 20 个 turn。

如果只能看"整个会话的最终 diff"，你面对的是 20 个 turn 叠加后的结果，无法判断哪一步是必要的、哪一步是跑偏后的自我修补。如果只能看"每个工具调用"，你又会被几十条 `edit_file` 淹没，看不到整体。

turn 级快照卡在中间：**粒度足够粗，能看出"这一轮干了什么"；又足够细，能定位"哪一轮开始跑偏"。** 这是可观测性设计里典型的"正确抽象层级"问题，ThinkRail 选对了。

一个小细节也能说明团队在做真实产品：超过 400 行改动的 diff 默认折叠，lock 文件和生成文件默认折叠，超过 50 个文件时提示切到 "One file" 模式；大文件和大 diff 做了虚拟化，聊天代码高亮移出主线程。这些都是被真实使用痛过之后才会加的。

### 4.3 仍未解决的部分

官方自己承认："the single-turn view is read-only, so Keep only works on the branch diff." 也就是说，你可以在"整条分支的累计 diff"上逐 hunk 接受/拒绝，但没法在"单轮 diff"上操作。这在逻辑上合理（单轮接受意味着要重写后续轮次的结果），但体验上是割裂的。

更根本的问题是：**Keep/Revert 只处理"代码是否保留"，不处理"为什么这么改"。** 一个 hunk 被 Revert 了，Agent 下一轮很可能再改一遍，因为它不知道为什么被拒。目前唯一的通道是 "Ask agent about this hunk"——人肉解释。这说明 Agent 工作台还缺一层结构化的"审查反馈协议"：拒绝理由应该成为下一轮的上下文，而不是靠人再打一遍字。

---

## 五、架构拆解 C：SPEC.md 图谱——显式上下文 vs 隐式检索

第三个支柱是 Spec-Driven Development（SDD）。这是 ThinkRail 里最有争议、也最值得深挖的部分。

### 5.1 设计：一个带 YAML 头的文档图

基本约定是：每个真正的模块旁边放一个 `SPEC.md`，文件开头是 YAML header：

```yaml
---
id:            # 唯一标识，其他 spec 靠它引用
type:          # goal-and-requirements | architecture-design | module-design | submodule-design | task-spec
title:         # 完整标题
status:        # draft | active | stale | done | deprecated
parent:        # 上一层 spec 的 id
depends-on:    # 其他重要 spec 的 id 列表
tags:          # 标签
---
```

正文写的是"意图"：这个模块是干什么的、它拥有什么、为什么某些非显然的决定要这么做。文档之间通过 `id` 互相引用，形成一张图（spec graph），而不是一棵目录树。

项目根目录另有 `goal-and-requirements.md` 和 `architecture.md` 描述全局。Agent 被要求：**先读 spec，再读代码；从全局 spec 开始，然后读离当前代码最近的那个 SPEC.md，需要时再沿 `depends-on` 扩展。**

### 5.2 技术本质：这是一个手工维护的检索索引

把它和 RAG 对比，价值就清楚了：

| 维度 | 向量检索（RAG） | SPEC.md 图谱 |
|------|-----------------|--------------|
| 索引来源 | 代码/文档切片的 embedding | 人（或 Agent）显式写的结构 |
| 检索单位 | 相似度 top-k 片段 | 语义上"最近"的模块规格 |
| 可解释性 | 低（为什么召回这段？） | 高（沿 parent/depends-on 走） |
| 可审查 | 不可 review | 就是一个 Markdown 文件，可 diff、可 review |
| 维护成本 | 自动，但会漂移 | 手动，但漂移可见 |
| 失效模式 | 召回错的片段，静默 | spec 过期，但至少读得到"过期了" |

关键差异在最后两行。**向量检索的失败是静默的**：它召回了三个看起来相关但其实过时的片段，模型照用，你无从察觉。而 spec 是文件，`status: stale` 就写在头上，`git log` 能看到它上次修改是三个月前——**漂移是可观测的**。

在"Agent 要连续跑几十轮、跨会话保持意图"的场景里，可观测性的价值高于召回率。这也是为什么 2026 年一批团队从"全自动 RAG"退回到"手工维护的上下文文件"（AGENTS.md、CLAUDE.md、SPEC.md）——不是因为 RAG 不先进，而是因为**工程系统需要的是可调试性，不是最高分**。

### 5.3 但是：HN 上那句最狠的批评是对的

回到 10 月 25 日那条讨论。有人翻出 ThinkRail 自己的 specs 目录，写道：

> How is this llm-vomit "specs that are ground truth" etc.?

这句话不好听，但它戳中了 SDD 的结构性矛盾：**如果 spec 是 Agent 写的，而 Agent 又是按 spec 干活的，那这是一个自我确认的闭环。** 模型生成一份"看起来很像规格说明"的文档，然后用这份文档约束自己，最后产出代码——三步都自洽，但没有一步引入外部真相。

spec-driven 的前提是"意图先于实现，且意图来自人"。一旦这个前提被打破，spec 就从"护栏"退化成"事后的合理化叙事"。更糟的是它会**伪装成权威**：因为文件名叫 SPEC.md、头上写着 `status: active`，后来的 Agent 会更信任它，甚至优先于代码本身。

这不是 ThinkRail 独有的问题，而是整个 2026 年 SDD 浪潮的通病。可行的缓解手段有四个，我认为应该成为团队规范：

1. **spec 的关键决策必须能追溯到人**。`architecture.md` 里每一条非显然决策，标注"谁在什么约束下决定的"。Agent 可以起草，但必须有人签字。
2. **禁止 spec 从代码反推生成**。代码是 spec 的实现，spec 是代码的意图；反推得到的只是"代码现在长什么样"的复述，没有信息增量。
3. **把 spec 纳入 CI**。至少做三件事：`id` 唯一性、`depends-on` 引用完整性、`status: active` 的 spec 必须有对应的模块目录。这三条都能用几十行脚本查出来，成本极低。
4. **改代码必须同 PR 改 spec**。ThinkRail 的 AGENTS.md 模板里已经写了 "Never diverge silently"，但"写了规则"和"规则被执行"是两件事——需要 review checklist 或 CI 检查兜底。

顺带说，spec graph 的 `status` 字段设计得不错（draft/active/stale/done/deprecated），它给了漂移一个显式的表达位置。但如果没有工具定期扫描"`status: active` 但 90 天没动过"的 spec，这个字段就只是装饰。

---

## 六、被忽略的第四层：扩展兼容层与安全边界

ThinkRail 还有一层设计，媒体几乎没提，但对"能不能真用"影响最大：**它把整个 Agent 生态的配置文件都当成自己的输入。**

具体来说，它会在这些位置发现 skills：`~/.pi`、`~/.claude`、`~/.codex`、`~/.copilot`、`~/.gemini`，以及当前项目里对应的目录（`.claude/`、`.gemini/` 等）。也就是说，你为 Claude Code 写的 skill、为 Codex 写的 prompt，可以直接在 ThinkRail 里用。

这个决定在体验上极香（迁移成本≈0），在工程上则制造了两个硬问题。

### 6.1 冲突解决策略过于"诚实"

官方文档写得很清楚：

> If two extensions register the same tool name, Pi keeps both loaded, reports a conflict, and the load order decides which one is used.

**两个扩展注册同名工具时，两个都加载，报一个冲突，然后由加载顺序决定用哪个。**

这是最省事但最危险的选择。工具名冲突时，正确的做法应该是"拒绝启动并要求显式消歧"，而不是"按顺序静默取一个"。因为 Agent 决定调哪个工具是基于名字和描述的——它根本不知道背后有两个实现，更不知道这次用的是 A 还是 B。一旦 A 是只读查询、B 会写数据库，行为差异是灾难性的。

可以理解团队为什么这么选：生态兼容优先，早期不想因为冲突阻断用户。但这个技术债会在用户装了 20 个 skill 之后集中爆发。至少应该提供一个 "strict mode"：冲突即报错。

### 6.2 安全模型：这次做对了

相比之下，安全边界的设计明显更成熟，几个细节值得抄：

**（1）未信任项目不加载任何可执行配置。** 打开一个新克隆的仓库时，它不会加载该仓库自带的 `.pi` settings、extensions、skills、prompts、`SYSTEM.md`，并且信任提示会**明确列出"信任后会加载什么"**。这是"默认拒绝 + 知情同意"的标准做法。对比很多 Agent 工具一旦 `cd` 进目录就自动读取 `CLAUDE.md` 并执行其中指令——那等于 `git clone` 即 RCE。

**（2）仓库自带的 MCP server 必须显式批准。** `.pi/mcp.json` 里定义的 server 不会自动启动，要先批准"它到底会运行什么命令"。

**（3）凭据不允许写进配置。** Settings 只存引用，secrets 必须是 `${VAR}` 或 `!command`，并且**拒绝把凭据直接写进 URL**（防止 `https://user:token@host` 这种形式被日志和 git 记录）。

**（4）权限授予存在项目记录里，不在仓库里。** "Always allow" 的授权写在 project record 上，而不是写回 `.pi/mcp.json`——**这样仓库无法把自己预置成"已授权"状态**。并且当 server 的 command 或 URL 变化时，授权自动重置。这是一个很聪明的"防供应链"设计：配置可以随仓库分发，授权不能。

**（5）MCP 调用前按只读性分级询问。** 对 server 没有标记为 read-only 的调用，在聊天里弹出 `Deny · Allow once · Allow in this chat · Always allow`，并且**参数直接展示在 tool card 上**。参数可见这一点很重要——大部分工具只问"是否允许调用 write_file"，不告诉你写哪个文件。ThinkRail 把参数摊开，人才有可能做出判断。

这套模型本质上是在回答一个问题：**Agent IDE 的攻击面比 IDE 大得多，因为它会自动执行仓库里的文本。** 传统 IDE 的插件需要用户主动安装；Agent IDE 的"插件"可能就藏在被打开的仓库里。这个区别值得所有做 Agent 工具的人写进设计文档。

---

## 七、横向对比：它到底在和谁竞争

把当前主流的五条路线放在一张表里，ThinkRail 的位置就很清楚了：

| 产品 | 形态 | Agent 内核 | 隔离模型 | 审查粒度 | 上下文载体 | 扩展协议 |
|------|------|-----------|---------|---------|-----------|---------|
| Cursor | VS Code fork | 自研 | 单仓库 + checkpoint | 文件/整会话 | rules + 索引 | 自有 |
| Claude Code | CLI + 轻量 IDE 集成 | 自研 | 单目录 + git | 整会话 diff | CLAUDE.md | Skills / MCP |
| Codex CLI | CLI + 常驻 daemon | 自研 | 单目录 | 整会话 | AGENTS.md | MCP |
| OpenCode 2 | 常驻服务 + 多前端 | 自研 | session 级 | 整会话 | 自有 | 80+ 内部插件 |
| **ThinkRail** | **桌面 App + CLI（同一 UI）** | **pi（嵌入库）** | **git worktree / 任务** | **turn 级 + hunk 级** | **SPEC.md 图谱** | **pi skills + 跨生态目录 + MCP** |

三个差异点值得强调：

**差异一：它是唯一把"隔离"做成产品主语的。** 其他产品的默认工作流仍然是"在当前目录干活"，隔离靠 checkpoint 或 git 兜底。ThinkRail 的默认工作流是"每个任务一个 worktree"，主目录永远干净。这个默认值的差异，会直接改变人的工作习惯——你会更愿意同时开三个任务，因为你知道它们不会互相踩。

**差异二：它是唯一把审查粒度做到 turn 的。** 其他产品的 review 基本停留在"会话结束看总 diff"。turn 级审查配合"每步完成即可 commit"，实际上是把 Agent 的工作流改造成了"小步提交"——这恰好是人类工程师被验证过的最佳实践。

**差异三：它是唯一明确"不做模型"的。** 用 JetBrains AI 也行，接自己的 provider 也行，`thinkrail` 自己没有账号体系（"ThinkRail has no accounts of its own"）。在一个所有厂商都想锁定模型的时代，这是个反直觉但可能正确的选择：**工作台的价值应该来自工作流，而不是模型绑定。**

---

## 八、独到判断：三个结构性风险

我不认为 ThinkRail 会成为主流 IDE，但它大概率会影响主流 IDE。以下是我认为它必须面对的三个结构性问题。

### 风险一：薄壳的宿命是"上游一动，全线震动"

嵌入 pi 作为库，意味着 pi 的 API 变更会直接穿透到 ThinkRail。看版本节奏：0.2.0 是 10 月 18 日，到 10 月 25 日已经发到 `0.3.0-nightly.6`——**七天六个 nightly**。这个速度对一个依赖它的 GUI 来说是不可承受的：每一个 nightly 都可能改工具协议、改事件结构、改上下文管理策略，而 GUI 层要跟着改渲染、改状态机。

更现实的问题：199 个 open issue 对一个 1,688 星的项目来说是很高的比例（约 12%）。这说明它现在处于"功能跑得比修 bug 快"的阶段。作为尝鲜可以，作为团队标准工具需要谨慎。

### 风险二：worktree 只解决了"文件隔离"，没解决"环境隔离"

前面列过四条成本，这里给一个判断标准。适合用多 workspace 并行的任务：

- 改动文件集合基本不重叠（如"改文档" vs "改后端接口"）；
- 不需要长驻服务（dev server、数据库迁移）；
- 依赖已通过 pnpm/uv 这类共享 store 的工具管理。

不适合的任务：

- 多个任务都要改同一个核心类型/接口定义；
- 任务需要跑 e2e、需要独占端口或数据库；
- 需要增量构建缓存（worktree 之间不共享 `target/`、`.next/`）。

**worktree 是"并行度的放大器"，不是"并行度的创造者"。** 任务本身耦合，开再多工作区也只是把冲突推到合并那一刻。

### 风险三：spec 的"真实性赤字"是这类产品的天花板

这一点最根本。Agent IDE 的长期价值，取决于它能不能让 Agent 在**跨会话**时保持正确。目前有三条路：

1. **更大的上下文窗口**——成本高，且长上下文中间的信息会被稀释（lost in the middle 仍未解决）；
2. **自动检索（RAG / 代码索引）**——便宜，但失败静默、不可调试；
3. **手工维护的结构化上下文（spec）**——可调试、可 review，但维护成本高，且极易退化成"模型自说自话"。

ThinkRail 押的是第三条。这条路的天花板不在工具，而在**团队有没有能力写出好的 spec**。写 spec 是一种被遗忘了二十年的技能，绝大多数 2020 年代入职的工程师没受过这个训练。工具能提供模板、能提供图谱、能提供 lint，但不能替人决定"这个模块的边界在哪、为什么这么切"。

所以我更愿意把 ThinkRail 看成一个**提问工具**：它逼着你在让 Agent 干活之前，先把"这个项目是什么、这个模块负责什么"写下来。写不出来，说明你自己也没想清楚——这时候 Agent 写得再多也只是加速混乱。

---

## 九、落地清单：什么时候该用它

如果你在评估"要不要把团队工作流迁到 Agent IDE"，我给一份可操作的清单。

**适合引入的信号：**

- 团队已经在用 pi 或至少在用 CLI 型 Agent，且痛点是"审查难、并发乱、上下文丢"；
- 项目是标准的 git 仓库，模块边界相对清晰，能写得出 `SPEC.md`；
- 有 CI，能把 spec 校验和 PR 流程接起来；
- 依赖管理用 pnpm / uv / cargo 这类支持共享缓存的工具。

**暂时别用的信号：**

- 单体大仓库 + 强耦合代码，多个任务必然改同一批文件；
- 需要大量长驻服务、端口/数据库独占的本地开发；
- 团队没有 review 文化——turn 级审查在"没人看 diff"的团队里等于零；
- 生产环境敏感仓库：先用未信任项目的默认拒绝策略跑一遍，确认不会自动加载仓库内配置。

**如果要用，先做四件事：**

1. 在根目录写 `AGENTS.md`，明确"本项目 spec-driven，spec 是 source of truth，代码不得与 spec 静默分叉"；
2. 只给 2–3 个核心模块写 `SPEC.md`，跑两周，看 Agent 的实际行为有没有变好——不要一上来写 50 个；
3. 在 CI 里加三条 spec 校验（id 唯一、depends-on 完整、active spec 有对应目录）；
4. 给并发任务定一条硬规则：**改同一批文件的任务不许并行**，其余随便开。

---

## 十、结语：IDE 的下一场竞争，不在编辑器里

ThinkRail 现在的完成度，大概相当于 2024 年的 Cursor——方向对，细节糙，靠一群愿意忍受 nightly 的用户推着走。它可能活不下来，JetBrains 的 incubator 项目向来死亡率不低。

但它提出的三个问题是对的，而且会被所有 IDE 继承：

**第一，Agent 的副作用必须变成可审查的事实，而不是对话里的叙述。** turn 级快照 + hunk 级接受/拒绝，会成为标配。

**第二，"在我机器上跑"这个默认值该改了。** 每个任务一个隔离工作区，主分支永远干净——这不是洁癖，是并发的前提。

**第三，上下文治理是新的架构工作。** 过去十年我们讨论"代码怎么组织"，接下来五年要讨论"意图怎么组织"。SPEC.md 图谱不一定是对的答案，但"把意图显式化、结构化、可 diff 化"这个方向，大概率是对的。

最后一句话留给那个最扎心的批评。有人问：这些 LLM 生成的 spec 凭什么叫 ground truth？

答案只能是：**凭有人为它负责。** 如果没人负责，它就只是文档；如果有人负责，它就是规格。工具能做的，是把"谁负责"这件事变得可见——而这，恰好也是所有 Agent 产品最终要回答的问题。

---

## 参考资料

- ThinkRail 仓库与 README：https://github.com/JetBrains/thinkrail
- ThinkRail 0.2.0 发布说明：https://thinkrail.ai/blog/thinkrail-0-2-0-review-the-turn/
- An agentic IDE that follows Pi's philosophy：https://thinkrail.ai/blog/thinkrail-pi-skills-and-desktop-apps/
- ThinkRail Spec-Driven Development：https://thinkrail.ai/blog/thinkrail-sdd/
- ThinkRail Workspaces：https://thinkrail.ai/blog/thinkrail-workspaces/
- Introducing ThinkRail：https://thinkrail.ai/blog/introducing-thinkrail/
- Hacker News 讨论（2026-10-25）：https://news.ycombinator.com/item?id=50233294
- pi coding agent：https://github.com/earendil-works/pi
- git worktree 文档：https://git-scm.com/docs/git-worktree
