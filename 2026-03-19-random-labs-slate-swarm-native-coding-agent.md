# Slate：超越 ReAct 与 RLM

2026-03-09·Random Labs 团队·

研究架构

[#](#section-0) 引言
----------------------------

在这份技术报告中，我们将介绍一种新的 agent 架构模式，并展示单线程 agent 如何泛化到超越 ReAct 与 RLM 的范式。

Random Labs 的目标，是为软件工程构建通用化、非 benchmark-maxxed、端到端的 agent。本文内容让我们朝这一目标更近了一步。

我们首先审视现代基于 LLM 的 agent 所面临的一系列问题：长时程任务、战略与战术的平衡，以及工作上下文管理。我们会分析这些问题已有的解决方案及其局限。在梳理完现代 agent 面临的问题之后，我们将介绍 Slate 的架构：一种基于线程的情节记忆（episodic memory）系统，能够同时解决上述所有问题。

[#](#section-1) 背景
--------------------------

要构建具备泛化能力的 agent，必须同时解决三个相互叠加的问题：长时程任务执行、战略与战术推理之间的平衡，以及工作记忆管理。这三件事单独看都并非无解——困难在于它们彼此交织、互相影响。

### [#](#section-2) 理解长时程任务

长时程任务具有路径依赖性（即所需动作彼此依赖的任务），而成功所需的最少步骤数又超过了最小化 harness 能处理的范围。这里的“最小化 harness”，指的是围绕模型构建的受限工具调用循环，不额外提供规划或记忆基础设施。Terminus 和 Simple Codex 都属于这一类，而大多数真正被拿来完成实际工作的 agent 并不属于这一类。[[4]](#ref-4)[[5]](#ref-5)

为了完成这类任务，agent 需要三样东西：足够的工作记忆，使模型能在恰当的时刻关注恰当的上下文；在战略性执行与战术性执行之间取得平衡，使模型既能规划得当，也能执行正确；以及在不丢失整体目标的前提下，将任务过程中发现的新信息整合进来。

### [#](#section-3) 工作记忆

模型无法在整个上下文窗口中均匀地分配注意力。随着上下文长度增加，模型对信息的关注能力会逐渐衰减。可用部分——直到但不包括衰减区域——就是工作记忆。Dex Horthy 将上下文窗口中检索质量下降的那一段称为 “Dumb Zone（愚钝区）”。[[6]](#ref-6) 工作记忆，本质上就是在那一点之前可有效利用的上下文窗口。[[25]](#ref-25)

上下文窗口与 Dumb Zone

工作记忆  Dumb Zone  注意力衰减  上下文窗口

上下文窗口并非所有位置都同样可用。随着窗口被填满，右侧边缘——也就是 Dumb Zone——的注意力质量会明显下降。

性能退化与输入长度 [[24]](#ref-24)

![Context Rot：Claude Sonnet 4、GPT-4.1、Qwen3-32B 和 Gemini 2.5 Flash 在不同输入长度下的模型性能变化——随着上下文增长，性能以非均匀方式下降。](https://research.trychroma.com/img/context_rot/hero_plot.png)

即便是在简单任务上，四个前沿模型的性能也都会随着输入长度增加而以非均匀方式退化。来源：Hong、Troynikov 与 Huber，《Context Rot》（Chroma，2025）。

### [#](#section-4) 战略与战术

战略（strategy）是基于知识的开放式规划，它指引系统朝目标前进；战术（tactics）则是学习得到的、局部的动作序列，能够切实推动任务向目标迈进。有趣的是，这一区分恰好直接映射到强化学习历史上解决围棋、国际象棋等游戏的方式。在国际象棋中，Stockfish 这类传统引擎通过穷举走子树来搜索（某种基于战术的搜索算法）[[16]](#ref-16)。相比之下，自我博弈 RL 则产生了能够学习“哪些局面在战略上更重要”的系统。

> “在多盘对局中，AlphaZero 会为了长期战略优势而弃子，这表明它的局面评估比早期国际象棋程序中基于规则的评估方式更灵活，也更依赖上下文。” [[11]](#ref-11)

暴力穷举 vs. 价值 / 策略执行

暴力穷举：对搜索树中每个节点、每个深度都进行评估（Stockfish）  价值 / 策略引导搜索（AlphaZero）  policy：走子选择（战术）  value：剪枝（战略）

暴力穷举会在每一层评估每一个节点。价值/策略引导搜索则使用价值网络从战略上判断局面，并使用策略网络从战术上选择走法——通过探索远少得多的节点，达到更强的表现。

在围棋中，这种分离更加明显：战略关注势、地的平衡与全局思维，而战术则关注“算路”（对具体局部变化的计算）以及生死题。当 DeepMind 构建 AlphaGo 时，这种分工是被直接写进架构里的：价值网络负责局面判断（战略），策略网络负责落子选择（战术）。[[14]](#ref-14) 对 AlphaZero 在训练过程中内部表征的研究发现，战术性概念——例如子力价值——最先学会，随后才是王安全与机动性等战略性概念。这些概念是在训练的不同阶段、网络的不同层中分别涌现出来的。[[12]](#ref-12)

AlphaZero：概念在训练阶段中的涌现

训练步数  0  16k–32k  32k–64k  128k+  子力价值与空间  王安全、威胁、机动性  更复杂的权衡  战术  战略（局面）  战略（长时程）  这些概念大约在 20 层网络中的第 10 层附近开始可以被线性解码，然后趋于平台期

> “……子力价值是一个基石概念，它最先形成。随后，围绕机动性的议题（王安全、进攻与防守）开始出现。最后进入一个精炼阶段，网络学会做出复杂的权衡……” [[12]](#ref-12)

![McGrath 等人（PNAS 2022）图 5：基于人工定义概念的价值回归随时间的变化。(A) 子力价值权重收敛到标准值；(B) 物质优势在训练早期就能预测价值，而机动性和王安全则在更后期才出现。](https://randomlabs.ai/alphazero-fig5.jpg)

AlphaZero 在自我博弈训练中的概念涌现。战术概念（子力、空间）会在前 32k 步内学会；战略性的局面概念（王安全、威胁、机动性）则在 32k+ 后出现。长时程的权衡推理最后才发展出来。McGrath 等，PNAS 2022。

该论文中由前世界冠军 Vladimir Kramnik 给出的定性评估，也直接印证了这种顺序：在 16k 步时，AlphaZero 还会在物质上吃亏；到 32k 时，它已经牢固掌握了子力价值。32k 到 64k 的飞跃主要体现在失衡局面中的王安全理解。超过 128k 后，提升则主要体现在它知道哪些进攻会成功——包括接受物质牺牲并将其兑现——而不再主要来自局面或残局技术。也就是说：先有战术知识，后有战略判断。

#### 软件工程：一种开放式的长时程博弈

我们认为软件工程是一种更加开放、几乎没有终局的博弈，在其中战略与战术都会发挥作用，只是取决于具体任务。例如，记住并执行一条 bash 命令属于简单战术；而设计一个能够随着演进仍保持向后兼容的 schema，则更偏向战略。

战略 vs. 战术光谱

战术  战略  运行一条 bash 命令  编写测试套件  规划一次重构  设计一个 schema

软件工程任务分布在一条连续谱上。战术是立即可执行的；战略则要求对未来状态与各种权衡进行推理。

这也可以从另一个事实中看出来：如果要求模型先写一个计划，或一步一步地思考任务，本质上是在先给它一个“知识检索任务”，再给它一个“agent 执行任务”。最初的规划/思考，可以被视为模型在检索知识、为求解路径制定策略，然后再使用战术去执行该计划。

> 顺带一提——AGENTS.md 文件中的大多数规则，其实都是战术性的，例如“绝不要运行数据库命令”。

[#](#section-5) 既有方法
--------------------------------

现有方法没有一种能同时解决上述所有问题。每种方法都在“解决一两个问题”与“牺牲另外的问题”之间做了权衡。

### [#](#section-6) 解决工作记忆并击败 Dumb Zone

最先想到的方案，往往是“把模型上下文压缩一下就好了！”只要我们能定期稳定地丢弃无关上下文，问题似乎就能解决。这种策略被称为 _compaction_（压缩整理）。

#### 压缩整理（Compaction）

从孤立地解决工作记忆问题的角度看，压缩整理是一种天真的方案。

压缩整理在很大程度上仍未被真正解决。大多数所谓的“compaction”，其实都只是有损压缩（尽管确实已经进步很多）。

> 2025 年初（大约 5 月），我们构建了最早一批基于滑动窗口的 agent 之一，它可以运行极长的会话（用户报告最长达到 2 天）。这个 agent 现在已经弃用，但仍可以通过 npm 包获取：`npm i -g @randomlabs/slatecli`

现实中已经有一些“能工作但有损”的压缩案例：

*   Claude Code 中的 compaction（众所周知地不太理想）
*   Geoffrey Huntley 的著名 Ralph Wiggum loop [[17]](#ref-17)
*   Amp 的 handoff 机制（很受欢迎，但需要用户提供指导）[[18]](#ref-18)

其中 Amp 的实现大概是最有意思的，因为 handoff 的设计目标就是为一个全新的 agent 会话提供启动上下文。

压缩整理的核心问题在于：它的有损性不是确定性的，这意味着我们可能会不可预测地丢掉重要信息。

#### 子代理（Subagents）

为了避免压缩整理的有损性，我们也可以尝试把“不重要的上下文”隔离起来。这就是 subagent 登场的地方。

从孤立解决工作记忆问题的角度看，subagent 是第二种天真的方案。Subagent 的效果相对还不错，因为它能隔离上下文。但这种隔离也意味着，天真的实现无法跨上下文边界传递信息，因为它最终只返回一条响应消息（参见 codex/claude-code subagents）。

### [#](#section-7) Markdown 规划

为了在任务的不同部分、压缩整理过程以及彼此隔离的 subagent 上下文之间保持一致性，我们可以预先做计划。

Markdown 计划也是平衡战略与战术的一种方式。要求模型先把任务规划出来，会迫使它调用自身的 _knowledge_ 来为任务制定策略；从整体上看，这通常会比直接利用它已经学到的行为模式得到好得多的结果。再给模型一个“在文档中追踪任务进展”的战术手段，就能让它在执行过程中反复刷新自己对 _strategy_ 的理解，并保持对齐。

随着模型持续变强，并在这类 Markdown 规划风格上得到更多训练，仅靠一个简单 Markdown 文件就能完成的任务范围必然会不断扩大。不过，借助规划与直接调用已学行为之间，很可能始终会存在差异。

> 我们可以把这称为 knowledge overhang（知识悬置）。也就是：某个模型理论上拥有这些知识，但如果不用“think step by step”或文件规划之类的技巧，它在战术层面并不能直接访问这些知识。[[22]](#ref-22)

作为 rollout sampling 的 Knowledge Overhang

起点  可在战术上访问的知识  Knowledge Overhang  Knowledge Overhang  模型知识边界  模型知识边界  可在战术上访问的知识

将 knowledge overhang 理解为一个 rollout sampling 问题：模型的潜在知识覆盖了任务空间中的广泛轨迹，但直接的战术采样只能触及其中很窄的一段。规划、chain-of-thought 与脚手架能够扩展被采样到的区域。

但这种形式的规划能走多远，必然是有上限的。只是随着模型变强，这个上限也会不断提高。

**三种关键失败模式：**

*   模型在写计划时不够充分（计划写得不够具体）
*   模型在执行计划时不够充分（模型“丢了主线”，漏掉计划中的部分内容）
*   模型忘了自己有自由意志，而它学到的战术又不足以让它适应新信息（它忘了要沿着正确方向更新计划）

我们大概都见过计划写得太粗糙，然后需要继续追问模型去补全的情况。我们也都见过模型没有完整执行计划，或者在计划还没完成时就提前宣布胜利。此外，在这种场景下，模型还必须记得在遇到新信息时更新计划，而这从来都不是有保证的。

随着针对这种规划形式的 RL 不断改进，这三种失败模式都已有明显改善（只要回想你过去一年里是如何使用这些工具的，就能看出来）。不过，要抑制这些失败模式，仍然需要直接的 RL。随着 RL 后训练投入增加，对于任意固定的任务复杂度，这些失败概率会下降；但对模型而言，这类行为依然天然不直观（从逻辑上说，这一点恰恰由“必须专门训练这种行为”所证明）。

### [#](#section-8) 直接任务分解

然而 Markdown 计划会过时，因此下一步自然就是让执行结构变成强制性的，并在执行过程中持续更新。很多实现会把这做成一棵任务树，要求模型在继续之前先逐个完成每个节点。这解决了“提前停止”的问题，也可以利用 subagent 的上下文隔离来提高完整性。（参见 ADaPT [[19]](#ref-19)）

在这种系统中，模型会接收一个主任务，派生出若干子任务，希望执行这些子任务，然后再返回去完成主任务。

直接任务分解树

主任务  子任务 A  子任务 B  子任务 C  叶子  叶子  执行或继续拆分  执行或继续拆分

直接任务分解：将任务表示为一棵树，每个节点要么直接执行，要么继续拆成子任务。它很彻底，但也很僵硬——一旦需要适应新信息，就必须重写整棵树。

如果还想进一步提高完整性，可以再引入一个 gating 机制，要求任务必须依次走过 N 个不同步骤，才能被标记为已完成。

**两个主要失败模式：**

*   由于线性的任务依赖，系统很难适应新信息
*   系统无法把主任务彻底分解清楚，导致子任务及其结果没有被重新整合回来

至于如何验证这一点，就留给读者自己动手了（拿 `gpt2-codegolf` 任务试一下就知道 [[20]](#ref-20)）。严格地让 agent 按任务树推进，并为每个任务设置验证步骤与动作门槛，确实有助于让 agent 不跑偏，但也几乎不给它留下灵活执行任务的空间。

采用这种带门控任务树的核心前提，是为了避免模型常见的“过早停止”失败模式；但代价则是，在这个过程中牺牲了自然语言与隐式规划所带来的灵活性，换来了结构上的僵硬。

直觉上看，对结构化任务数据的依赖就是这里的主要问题根源，同时它也是彻底性的来源。

这种僵硬会让整个系统更难表达多样行为，也更难灵活处理任务。我们可以说，这样的系统 _expressivity_（表达能力）较低。

### [#](#section-9) 表达能力与归纳偏置

当一个 agent harness 只需较少的输出操作，就能支持大量可能的终态时，我们说它具有较高的表达能力。

为了说明不同工具的表达能力差异，可以对比两个 harness。Harness A 有一个 `file_read` 工具；Harness B 只能使用 `sed` 命令。无论 Harness A 多么努力，也无论给它多强的模型，Harness A 都永远无法表达“编辑文件”这个动作。相反，Harness B 虽然可能在 token 效率上差一些，却完全能够读取、写入、搜索文本等等。这正是 `sed` 工具表达能力更强的结果：通过一个略微更复杂的接口，你可以表达更广泛的操作。

Harness 表达能力：可达行为空间

Harness A——仅有 file\_read  Harness B——sed  ✓ 读取文件  ✗ 写入文件  ✗ 搜索文本  ✗ 原地编辑  ✓ 读取文件  ✓ 写入文件  ✓ 搜索文本  ✓ 原地编辑

表达能力关注的是“可达行为空间”。一个更具表达力的接口，能让同样的模型解锁更多可能的终态。

系统的表达能力很重要，但模型是否能用好这个系统也同样重要。模型对某个 harness 的使用能力，直接取决于该接口在它训练分布中的“熟悉程度”。

举例来说，有两个都很有表达力的系统：Bash 与 Python REPL。

它们在训练数据中的典型用法存在差异。带有 Python REPL 的 harness _能够_ 完成许多与 Bash shell 环境相同的工作。但模型完成任务的速度，很大程度上取决于所需操作在训练数据中出现得有多频繁。例如，如果任务要求 agent 在 Ubuntu VM 中修复一个带有 C 绑定的包问题，并使用修补后的包，那么在 Python REPL harness 中完成这件事，可能就会比在 Bash harness 中更困难。

尽管理论上两者同样具有高表达力，但模型在如何使用这些 harness 上仍然存在偏置。

模型的归纳偏置、系统的表达能力，以及所采用的采样方法，共同决定了我们最终观察到的行为。作为 harness 构建者，目标是让“期望的行为”成为“自然发生的行为”。

> 注：这里的归纳偏置，指的是模型从原始预训练到 rubric 后训练过程中被塑造出来的默认偏好行为。

作为 harness 构建者，你的工作是设计一个 harness，使系统能够自然而然地表达出你想要的行为。系统 _能否_ 表达这些行为，取决于 harness 本身的表达能力，以及模型的归纳偏置长什么样。

回到任务分解这个问题：强制模型遵循严格步骤的任务图，会明显限制整个系统的表达能力。

### [#](#section-10) RLM 与递归分解

Agent 系统需要一种更灵活的方式，既能分解任务，也能执行任务。RLM 是最接近在这些需求之间取得平衡的方法。它不强制预先固定分解结构，而是给模型一个 Python REPL，并允许它递归地运行操作，让任务结构自然地从模型自身的推理中涌现出来，而不是被事先规定。

子调用（无论是直接的 LLM 查询还是类似 RLM 的 subagent）能够封装上下文；REPL 则让模型可以迭代式地适应问题，而不是只能以“一次性提交然后等待结果”的模式工作。模型在 Python _脚本编写_ 上拥有海量训练数据，因此它熟悉这个接口，并天然偏向于使用它；上下文还可以通过引用传递，从而保留单一事实来源；同时，模型也具备以一种 _自然_ 且非强制的方式来分解任务的能力。

本质上，只要拥有正确的原语和模型偏好使用的接口，任务分解就会自然涌现。

但这里有一个问题。

注意官方实现是有深度限制的，对吧？[[2]](#ref-2) 论文里只讨论了 depth=1。可一旦真的允许 _递归_（depth=N），模型就需要某种防止过度分解的保护机制。不是说模型一定会过度分解，而是它确实可能会——尤其是在你明确要求它做任务分解的时候。只要接口允许无限分解，harness 就必须内建一层防止过度分解的保护。

不过，还有第二个问题：当系统在执行中途发现新数据时，它要如何适配？由于 REPL 缺乏中间结果，模型必须为当前步骤预先提交完整方案，只有在最后才能知道是否成功。你可以把这想象成在一个迷宫里解题，但你必须闭着眼一次性猜出未来 _n_ 步。在这种设定下，你唯一得到的反馈，就是最终落在什么位置。几乎没有中途修正路线的空间，尤其是在环境本身还在变化的时候。要么你在另一端成功出来，要么你就没出来。

盲目的 N 步执行

一次性提交  S  整条路径预先承诺  意外状态不可见——无法适应  只有最终反馈  反应式  S  看到意外状态 → 调整 ✓  REPL：看不到中间状态  ReAct / 工具循环：可逐步适应

没有中间反馈时，模型必须一次性提交完整的步骤序列——就像蒙着眼走迷宫。只有执行结束时，它才知道自己撞墙了。而有逐步反馈时，它会立刻发现墙并改道。

这可以被描述为系统栈各层之间缺乏同步。模型把操作卸载给某个系统（LLM 或程序），而那个系统会 _在隔离环境中_ 处理信息，并且只返回最终结果；这会限制主模型在执行计划（例如 REPL 中的程序）过程中遇到失败时的适应能力。对于读取一个不会变化的环境中的信息来说，这完全没问题。但在真正做实现时，这种由缺乏同步带来的僵硬性，至少也是个大问题。

> 顺带一提……如果把上面的观察与对 deep research agent 的理解结合起来，你会发现一种非常具体的上下文工程模式：基于栈的隔离在研究场景中效果很好，因为它可以把检索任务拆成对不可变数据的隔离操作，然后再综合起来。

过度分解与僵硬性，都是 ReAct 类 agent 不太会遭遇的失败模式，因为 ReAct 的规划与执行是隐式发生的，一次一轮，这让模型能够保持灵活和响应性。[[21]](#ref-21)

此时，几乎每个试图构建 agent 的人都会想到：“要不我做一个 planner agent，再来一个 implementer agent，再来一个 reviewer agent？”

让我提前告诉你结果：它大概会“能用”，但你实际使用时会烦透它。它慢、笨重，而且工作起来阻力很大。这很大程度上是因为它采用了过于严格的执行模式，而不是让模型自行决定最合理的任务处理方式。这也许会提升 benchmark 分数，但并不会真正改善你的开发体验。在执行阶段维持通用表达能力，_极其_ 重要。

有一些 agent 架构就是基于这种原则运行的：Devin、Manus、Claude Code，以及 Altera 的 Sid 项目（现在叫 [shortcut](https://shortcut.ai/)）。

### [#](#section-11) Devin、Manus 与 Altera

Devin、Manus，以及 Altera 的 PIANO 架构，都可以归入“高层做规划、低层做执行”的一类，并通过某种机制在 system 1 与 system 2 的思考之间做同步，以获得一个可长时间运行且具备持久状态的 agent。[[7]](#ref-7)[[8]](#ref-8)[[9]](#ref-9)[[10]](#ref-10)

它们都遵循一种模式：由高层规划 agent 负责制定策略，把任务委派给低层 subagent，将低层 agent 的上下文压缩为某种表示，再把这一格式化上下文返回给高层 agent，以实现两层之间的同步。Altera 的方法还额外允许 agent 同时进行多种形式的处理。

这种规划形式，很容易落入上文任务分解部分或 RLM 部分提到的那类失败：过于严格的执行约束削弱了系统对新信息作出反应的能力，并且必然会让 subagent 像运行脚本一样以同样方式失败。

同步型 subagent（即主 agent 阻塞等待 subagent 返回结果）更可靠，但速度更慢。而异步 subagent 则会引入额外问题：什么时候、以及如何对结果进行汇总与对账。

Devin / Manus / Altera：规划—委派—压缩循环

1. 制定策略  2. 委派  3. 执行  4. 压缩并返回  ↑ 上下文在这里丢失  ![Lance Martin《Context Engineering in Manus》中的 Manus 上下文缩减图——展示了工具结果的完整表示与紧凑表示，以及过期结果如何从上下文中被裁剪。](https://randomlabs.ai/manus-reduction.png)

Devin/Manus/Altera 模式：高层战略 agent 委派给低层执行器，对结果进行压缩，再同步回去。每一道压缩边界，都有可能丢失关键状态。来源：Lance Martin，《Context Engineering in Manus》。[[10]](#ref-10)

### [#](#section-12) Codex 与 Claude Code

它们非常简单：把工作通过某种 prompt 形式委派给一个 subagent，subagent 完成后再响应回来。

这种方法显式地引入了同步问题，因为主父级与子级上下文是隔离的，主进程必须依赖某种消息传递机制（在这里，就是发送一个 prompt，接收一个 response）。这也解释了为什么最初 subagent 最适合拿来做搜索，因为大多数搜索操作本质上是探索性的，实际上并不需要保留太多上下文。

幸运的是，对这些实验室团队而言，他们完全可以通过训练，让模型擅长把任务委派给 subagent，也擅长成为 subagent。作为 harness 构建者，这并不是一件值得赌它不会发生的事。

Claude 没有必要地为 subagent 定义了持久角色，但这是因为它的同步方式是消息传递（我们认为在当前模型行为下，对于 mainthread + subagent 架构而言，这并不是正确方向；不过模型在这件事上会越来越擅长，因为它们会为此接受训练）。

我们认为，单线程 agent 其实还远没有被彻底解决。作为一个行业，我们还没必要现在就转向“agent 团队”。

<figure>
          <p class="figure-title">Agent 架构分类</p>
          <table style="width:100%;border-collapse:collapse;font-family:'JetBrains Mono',monospace;font-size:10px;">
            <thead>
              <tr>
                <th style="text-align:left;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">维度</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">ReAct</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">Markdown 计划</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">任务树</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">RLM</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">Devin / Manus / Altera</th>
                <th style="text-align:center;padding:6px 7px;background:#1a1a1a;color:#F1F2F2;font-weight:600;border:1px solid #333;">Claude Code / Codex</th>
                <th style="text-align:center;padding:6px 7px;background:#70808D;color:#F1F2F2;font-weight:600;border:1px solid #333;">Slate</th>
              </tr>
            </thead>
            <tbody>
              <tr style="background:#F8F8F8;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">规划</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">隐式</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">文件</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">显式</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">REPL</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">规划 agent</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">计划模式</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">隐式</td>
              </tr>
              <tr style="background:#fff;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">分解方式</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">无</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">无</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">直接树状分解</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">REPL 函数</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">基于任务</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">subagent 委派</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">隐式</td>
              </tr>
              <tr style="background:#F8F8F8;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">同步机制</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">单线程</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">单线程</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">门控步骤</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">REPL 返回</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">压缩后返回</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">消息传递</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">episode</td>
              </tr>
              <tr style="background:#fff;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">中间反馈</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">每步</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">每步</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">任务失败时</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">执行过程中</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">压缩后</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">消息传递</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">每个 episode</td>
              </tr>
              <tr style="background:#F8F8F8;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">上下文隔离</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">每个子任务</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">每次子调用</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">subagent</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">subagent</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">每个线程</td>
              </tr>
              <tr style="background:#fff;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">上下文压缩</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">基于任务</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">REPL 切片</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">subagent 压缩</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">Compaction</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">episode 压缩</td>
              </tr>
              <tr style="background:#F8F8F8;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">并行执行</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">N/A</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">在 REPL 中</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">仅 Altera</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">原生支持</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">原生支持</td>
              </tr>
              <tr style="background:#fff;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">表达能力</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">高</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">高</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">低</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">高</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">中</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">中</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">高</td>
              </tr>
              <tr style="background:#F8F8F8;">
                <td style="padding:5px 7px;border:1px solid #e0e0e0;color:#1a1a1a;font-weight:500;">适应性</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">是</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">若更新计划则是</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">否</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">是</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">是</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;">受消息传递限制</td>
                <td style="padding:5px 7px;border:1px solid #e0e0e0;text-align:center;color:#70808D;font-weight:500;">是</td>
              </tr>
            </tbody>
          </table>
          <figcaption>从关键系统属性维度比较不同 agent 架构。Slate 同时具备 ReAct 的表达能力与响应性，以及其他系统所具备的上下文隔离、并行性与压缩能力。</figcaption>
        </figure>



[#](#section-13) Slate 的方法：线程编织与 Episode
--------------------------------------------------------------

总结一下前面讲过的内容：

*   压缩整理（Compaction）：如何在保留关键信息的同时压缩一条 agent 执行轨迹
*   战略一致性：如何让 agent 能对问题制定策略，并在整个求解过程中始终与该策略保持一致
*   表达能力：如何设计接口，使 agent 能表达更复杂的行为
*   任务分解：如何拆解任务、解决子问题，同时又在最高层保持灵活性
*   同步：当执行上下文彼此隔离时，如何同步系统中各处正在进行的工作

在这一部分，我们提出一个用于解决这些问题的架构原语：_thread_（线程）。核心洞见在于：在一个 orchestrator 线程与多个 worker 线程之间进行频繁且有边界的同步，能够真正实现速度、延迟与智能之间可用的平衡。

### [#](#section-14) 线程

这个想法很简单：使用一种高度具备表达能力的接口，去访问模型中的 knowledge overhang，使模型能够围绕自己的行动制定策略，而不必把精力放在实现细节的战术上。一个中心化的编排 agent 通过高表达力接口把动作委派给工作线程（这可以是某个工具、某个 CLI 等。我们之所以选择 DSL，是因为拥有编程模型会带来更高灵活性）。工作线程执行该动作，然后返回主 orchestrator。

听起来像 subagent？不完全是。

线程是非常具体的。每个线程只执行一个动作，动作完成后就暂停，并把控制权交还给主线程。你可以把一个动作理解成一种战术：执行一串命令、从文件 Y 中提取 X，等等。与面向特定目的的 subagent 不同，线程是服务于系统当前意图的通用 worker。orchestrator 决定下一步做什么，而线程负责执行。普通 subagent 通常是持久存在的，有时还会在后台运行，并由于上下文隔离而通过消息传递与主线程（或彼此）同步。相比之下，线程的目的只是累积上下文，作为该特定工作流的持久、可复用存储；它们也不把消息传递作为与 orchestrator 沟通的主要方式。相反，每次线程动作都会为“仅该动作序列的执行历史”生成一个压缩表示。这个压缩表示称为 _episode_，并会被直接共享给主线程。

线程 vs. Subagent：上下文隔离

Subagent  orch- estrator  sub- agent A  sub- agent B  msg  每个 agent 都有自己隔离的上下文  线程  共享 / 可组合上下文  orch- estrator  T1  T2  ctx in  ctx in  episode  episode  T1→T2  上下文被显式共享——episode 可以跨线程组合

Subagent 各自在自己的隔离上下文中运行，只能通过消息传递进行通信。线程则显式共享上下文。orchestrator 把上下文传入每个线程，episode 再返回，而一个线程的 episode 还可以成为另一个线程的输入。

### [#](#section-15) 用线程解决情节记忆

线程在完成一个动作过程中所采取的步骤，构成了一个 _episode_。这让我们在 LLM 中获得了一种可处理的、真正的情节记忆形式。

情节记忆，就是对一个已完成 episode 的压缩表示：只保留重要结果，而不是通往这些结果时每一步完整的战术轨迹。子线程不会与主线程进行来回消息传递。相反，它们执行完毕后，返回的是 episode。正是这种内建的完成边界，使得 compaction 在 Slate 架构中变得自然。

Episode 还可以直接作为其他线程的输入。这使得线程具有可组合性。一个线程可以用前一个线程的 episode 来初始化，继承其中有用的结论与工作历史，而不必继承完整上下文。正是这种可组合性，让基于线程的架构在作为原语时拥有极高表达能力，也使它区别于那些只回传一条响应字符串的天真 subagent 设计。

### [#](#section-16) 线程编织

线程化执行最终带来的是一种系统：它能够隐式且自适应地分解任务——而无需任何静态计划。orchestrator 不必预先做出不可更改的承诺，但 _必须_ 以有边界、可压缩的工作单元形式把任务外化出来。这就是 thread weaving（线程编织）：orchestrator 负责派发，线程负责执行，episode 负责组合。

其机制是：orchestrator 以 _引用方式_ 使用线程，从而获得复杂上下文路由的语义——这和 RLM 借助 REPL 实现的能力相似，但没有那种僵硬性，因为动作是在一个线程内部逐步执行的。由于线程作用域是有边界的，系统会自然地与当前计划同步。又因为线程是由 LLM 驱动，而不是静态脚本，所以它们能对意外环境状态作出反应，而不是直接崩溃。

最终得到的是一个能够隐式、自适应分解任务的系统。orchestrator 会在执行过程中一边管理规划，一边管理分解。它不需要一开始就锁死在静态计划上。但它 _必须_ 把这种分解外化成有用的工作单元，以便后续压缩并引用。频繁同步也意味着，当任务中途出现新信息时，orchestrator 可以更新自己的策略。

Slate：线程编织与 Episode 架构

orchestrator  派发线程  episodes → 输入  slate  orch.  T1  T2  T3  T4  T1+T2 输入  T2+T3 输入  T3+T4 输入  T5  T6  派发  episode 作为输入  episode 返回给 orch.

线程编织：从单个 orchestrator 线程派发出有边界的 worker episode，并在完成后同步回这个编排线程。线程 T1/T2/T3 独立运行；它们产生的 episode 会成为后续工作的输入。

### [#](#section-17) 线程即进程：从操作系统视角看 LLM 系统

线程与 episode 可以直接映射到一种操作系统式的框架中。[[26]](#ref-26)

![Karpathy 的 LLM OS 图示：LLM 作为一种正在涌现的操作系统内核，管理上下文（RAM）、进程（工具调用/subagent）、存储（文件）以及外设（浏览器、终端、API）。](https://randomlabs.ai/karpathy-llm-os.png)

Karpathy 对 LLM OS 的 framing——把 LLM 看作操作系统内核。上下文窗口 = RAM。工具调用 = 进程。文件 = 存储。[[26]](#ref-26)

更具体地说，Karpathy 的 LLM OS 将 LLM 描述为一个操作系统内核：管理上下文（RAM）、派生进程（工具调用、subagent）、读写存储（文件、记忆），以及协调外设（浏览器、终端、API）之间的 I/O。正如操作系统内核本身并不执行应用逻辑一样，主线程 LLM 也负责调度任务、管理资源、维护进程状态，从而让工作在整个系统中被正确路由。

Slate 的线程架构与此一一对应。编排层就是内核；线程是隔离的进程；episode 是进程返回值：它们是对进程做了什么的压缩总结，并被提交回内核的工作记忆中。文件系统、终端与 Web 是外设；模型的上下文窗口就是 RAM——稀缺、宝贵，而且需要被主动管理。

在这个框架下，Slate 的 episode 架构给出了一个直接答案：不要让 RAM 一路堆满直到进程崩溃，而是把每次线程返回都视为一个自然时机，来决定哪些信息应该保留、哪些应该压缩、哪些应该丢弃。

### [#](#section-18) 长时程任务的瓶颈

长时程 agent 任务真正的瓶颈是上下文管理，而不是模型智能。由于 knowledge overhang 的存在，模型其实已经足以解决比当前成功率所显示的更多任务。缺口在于系统问题，而不是能力问题。

Slate 的一个令人惊讶之处在于：我们的路由机制居然真的能工作。模型似乎能够理解如何以有用且恰当的方式在系统中路由上下文，尽管我们并没有专门训练它们这样做。对这种路由行为的正式分析与 benchmark，将留待未来工作。

至于真正的感受——留给读者自己去体验。

今天，我们正式把这个 agent 以公开测试版的形式发布。你可以访问我们的主页，或者运行 `npm i -g @randomlabs/slate` 来使用它。

### [#](#section-19) 一些有意思的观察

在开发与测试过程中，有几个结果让我们感到意外：

*   **在真实工作流中实现大规模并行执行。** 真实的软件任务会自然分解成多个并行线程工作流。orchestrator 可以同时派发多个线程，并在继续之前综合它们的 episode。这与按顺序逐步执行的 agent 有本质区别，而在实践中它似乎也更快。
*   **跨模型组合。** 在同一个任务中混合使用 Sonnet 和 Codex，效果很好。episode 边界天然充当了模型之间的清晰交接点，同时不会损失上下文一致性。

[#](#section-20) 参考资料
---------------------------

1.  [RLM —— 递归语言模型（论文）](https://arxiv.org/pdf/2512.24601v1)
2.  [RLM —— 博客概览](https://alexzhang13.github.io/blog/2025/rlm/)
3.  [Karpathy：LLM 作为计算机的框架](https://x.com/karpathy/status/1935518272667217925?lang=en)
4.  [TerminalBench 2.0：Simple Codex 基线](https://www.tbench.ai/leaderboard/terminal-bench/2.0/simple_codex/unknown/gpt-5.3-codex%40openai)
5.  [Terminus 最小化 harness](https://www.tbench.ai/news/terminus)
6.  [Dex Horthy：“Dumb Zone”](http://youtube.com/watch?v=rmvDxxNubIg)
7.  [Altera：Project Sid / PIANO 架构](https://arxiv.org/pdf/2411.00114)
8.  [Devin / Cognition：不要构建多 agent](https://cognition.ai/blog/dont-build-multi-agents)
9.  [Manus：面向 AI agent 的上下文工程](https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus)
10.  [Manus：上下文工程笔记与幻灯片](https://rlancemartin.github.io/2025/10/15/manus/)
11.  [Silver 等：AlphaZero（Science，2018）](https://www.science.org/doi/10.1126/science.aar6404)
12.  [对 AlphaZero 知识获取过程的探测（PNAS）](https://www.pnas.org/doi/10.1073/pnas.2206625119)
13.  [Stockfish vs LCZero：两种竞争范式](https://www.mdpi.com/1099-4300/24/4/550)
14.  [Silver 等：AlphaGo（Nature，2016）](https://storage.googleapis.com/deepmind-media/alphago/AlphaGoNaturePaper.pdf)
15.  [DeepMind：AlphaGo 的创新点](https://deepmind.google/blog/innovations-of-alphago/)
16.  [Stockfish 国际象棋引擎](https://github.com/official-stockfish/Stockfish)
17.  [Geoffrey Huntley：Ralph loop](https://ghuntley.com/ralph/)
18.  [Amp：handoff 机制](https://ampcode.com/news/handoff)
19.  [ADaPT：按需分解与规划](https://arxiv.org/pdf/2311.05772)
20.  [TerminalBench 2.0：gpt2-codegolf 任务](https://www.tbench.ai/benchmarks/terminal-bench-2/gpt2-codegolf)
21.  [Yao 等：ReAct —— 推理与行动的协同](https://arxiv.org/pdf/2210.03629)
22.  [Wei 等：chain-of-thought 提示](https://arxiv.org/pdf/2201.11903)
23.  [Manus：架构幻灯片](https://docs.google.com/presentation/d/1Z-TFQpSpqtRqWcY-rBpf7D3vmI0rnMhbhbfv01duUrk/edit?pli=1&slide=id.g38aedf7fc8c_0_143#slide=id.g38aedf7fc8c_0_143)
24.  [Hong、Troynikov、Huber：Context Rot —— 增加输入 token 如何影响 LLM 性能（Chroma，2025）](https://research.trychroma.com/context-rot)
25.  [人类的工作记忆](https://pmc.ncbi.nlm.nih.gov/articles/PMC8573634/)

[← 返回博客](/blog)![](https://randomlabs.ai/glyphs/glyph_14.svg)
