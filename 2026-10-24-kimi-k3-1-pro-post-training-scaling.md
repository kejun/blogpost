# 当开源模型的进步只剩「后训练」：Kimi K3.1 Pro 深度拆解——3T 参数、1M 上下文与一次可测量的「能力削减」

> 2026 年 10 月 23 日，Moonshot 发布 Kimi K3.1 Pro。它没有换基座，没有换架构，甚至没有换预训练数据配比——它只是把后训练（post-training）的算力堆到了一个前所未有的量级。结果是一个在 Terminal-Bench 4.0 上拿到 65.7%、距离 Claude Opus 5.5 只差 0.7 个百分点的开放权重模型。Hacker News 上 655 分、416 条评论，讨论的焦点却不是分数，而是另一件事：Moonshot 主动从训练数据里删掉了网络安全内容，把自家模型的漏洞挖掘能力从 90.5% 压到了 81.0%。

这篇文章想讨论三件事：后训练如何成为开放权重模型唯一的规模化杠杆；当「能力」可以被精确地做减法时，安全工程发生了什么变化；以及这些数字对一线开发者选择模型、设计 Agent 系统意味着什么。

---

## 一、先把事实摆清楚：这不是一次「新模型」发布

如果只看营销口径，K3.1 Pro 是「新一代」。但技术博客里写得很直白：

> Kimi K3.1 Pro is a post-trained version of Kimi K3, with substantially larger post-training compute.

翻译过来：**基座模型就是 K3，权重是同一套，只是后训练阶段投入了「substantially larger」的算力**。这在过去两年里是很少见的发布方式。我们习惯了「预训练 scaling law」叙事——更多 token、更多参数、更大集群。而 K3.1 Pro 传递的信号是：在 3T 级 MoE 这个体量上，预训练的边际收益已经进入平台期，真正的差异化发生在模型「毕业」之后的最后一段路。

几个关键事实：

- **规模**：3T 级（3 trillion 参数量级）MoE，开放权重模型里最大的之一
- **上下文**：1,048,576 token（1M），与 K3 系列一致，API 侧全系支持
- **权重**：完整权重承诺 **11 月 4 日前** 释放
- **双 SKU**：`kimi-k3.1-pro` 与 `kimi-k3.1-pro-highspeed`，后者速度 2-3×
- **定价**（每百万 token）：标准版输入 $2.00 / 输出 $10.00 / 缓存命中 $0.20；缓存写入按 TTL 分档，5 分钟 $2.00、1 小时 $4.00。Highspeed 版本输入 $4.00 起，输出 $20.00
- **迁移压力**：K2 系列将于 2026 年 12 月底全部退役，10 月 31 日起对新注册用户关闭

注意最后一条。这不是一个「多一个选择」的发布，而是一个带强制迁移窗口的发布。当一个厂商敢于给旧系列设定硬性退役日期，说明它对自己在新架构上的成本曲线有足够信心。

而在第三方视角下，Artificial Analysis 给出的 Intelligence Index 是 **55 分，落在 Pareto 线上**——意思是：在「智能水平 / 单任务成本」这张图上，它没有被任何模型严格支配。这比「第一」更有意义。因为它意味着开放权重模型第一次在**性价比前沿**上占住了位置，而不只是在「便宜」这个维度上。

---

## 二、后训练工程栈：为什么这是「工厂」而不是「配方」

技术博客里有一句话，信息密度极高，但很容易被略过：

> To enable large-scale joint RL across hundreds of downstream domains, we optimized every layer of the stack — the RL framework, long-context inference, training efficiency, sandbox infrastructure, rollout scheduling, and a shared platform for environment quality checks — so that each increment of RL compute delivers stable, predictable returns.

拆开来看，这是六个完全不同的问题，而它们必须同时被解决，后训练才能 scale：

**1. RL 框架。** 数百个下游领域的联合 RL，意味着异构 reward、异构 rollout 长度、异构验证器。传统 PPO 实现里，一个 batch 内所有样本共享同一个序列长度分布假设；当你的任务里既有「改一个 typo」也有「跑 167 轮实验调一个行走控制器」时，这个假设直接崩掉。需要的是按任务维度做梯度累积与长度分桶的调度器。

**2. 长上下文推理。** 1M 上下文的 RL rollout 是灾难性的：一次 forward 就要吃掉几十 GB KV cache，而 RL 需要同一 prompt 采样 8-16 次做 advantage 估计。这解释了为什么 K3 系列在 KV cache 压缩上投入巨大——rollout 阶段的显存占用直接决定了 on-policy 数据的吞吐。

**3. 训练效率。** 「每个单位的 RL 算力带来稳定可预测的回报」这句话的关键词是 **predictable**。RL 训练最恐怖的不是慢，是不收敛且不可预测。当你在数百个 domain 上联合训练，任何一个 domain 的 reward hacking 都会污染共享表征。所以要的不是更快的 kernel，而是**可观测性**：每一步都能定位是哪个 domain 的梯度在拖后腿。

**4. 沙箱基础设施。** Agentic RL 的本质是「模型在环境里行动，环境给反馈」。数百个领域的沙箱意味着数百种运行时：终端、浏览器、CAD 软件、Unity 引擎、财务软件、Blender。沙箱的启动延迟直接进入 rollout 的 critical path。启动一个 Unity 场景要 40 秒，你的 RL 吞吐就被钉死在 40 秒/rollout。

**5. Rollout 调度。** 长尾任务（比如那个跑了几百轮实验的行走模拟器）会拖垮整个 batch。需要的是异步、可抢占、带优先级回填的调度——本质上是把 RL 训练当成一个分布式作业系统来设计。

**6. 环境质量平台。** 这是最容易被低估的一环。RL 环境的 bug 会以「模型能力不行」的形式表现出来。一个奖励函数写错的沙箱，会稳定地教模型学错东西，而且很难被发现——因为 loss 曲线看起来很正常。所以他们建了一个**共享的环境质检平台**，在环境进入训练池之前先做验证。

这六件事放在一起，结论很清楚：**后训练已经不是「调参」，而是「建厂」**。而建厂的能力，恰恰是开放权重厂商相对学术团队的结构性优势——也是相对闭源厂商唯一能追平的路径，因为基座权重大家最终都会有（K3 已开源）。

HN 上有一条评论说得挺准：

> It's a bit fascinating to me how all of these labs have rolled their own completely unique RL environments. I wonder how much the industry will centralize around a few key patterns.

我的判断是：**不会收敛到少数框架，但会收敛到少数「环境标准」**。框架层（verl、OpenRLHF 这类）已经相当同质化，真正的护城河是环境——谁拥有高质量、可验证、难作弊的环境池，谁就拥有后训练的数据飞轮。K3.1 Pro 的六个 domain（coding / 3D / finance / cyber / science / office）本质上就是六个环境池。

---

## 三、基准数据怎么读：三个「看起来平淡、其实很关键」的地方

先把核心数字列出来。以下全部来自官方技术博客与附录脚注，评估设定统一为 reasoning effort = max、temperature = 1.0、top-p = 0.95：

| 基准 | K3.1 Pro | 参照组 | 读法 |
|---|---|---|---|
| Terminal-Bench 4.0 | **65.7%** | Opus 5.5 66.4 / GPT-6 Astra 58.2 | 用 Claude-Code harness 跑，几乎贴住闭源最强 |
| Kimi Code Bench 3.0 Long-horizon（内部） | **61.2%** | K3 55.95% | 同一基座，后训练 +5.25 个点 |
| BenchCAD（with tools, Voxel IoU） | **92.7** | Opus 5.5 96.2 / GPT-6 95.9 / Fable 5.1 92.6 / DeepSeek 81.6 | 3D 重建接近闭源第一梯队 |
| BenchCAD（without tools） | **72.8** | Opus 5.5 73.0 / Fable 5.1 60.6 / DeepSeek 41.2 | 单次生成几乎追平 Opus，断层领先同级开源 |
| OfficeQA Pro v2 | **64.4** | 官方称 SOTA | 纯图像 PDF 语料，考检索+跨文档核验 |
| Frontier Finance | **58.6** | — | 端到端投资工作流 |
| Kimi Hallu Bench Hard（claim-level，越低越好） | **8.3** | K3 23.4 / Opus 5.5 15.0 / GLM-5.3 22.6 / DeepSeek 23.3 | 幻觉率降 64.5% |
| xdev-bench-hard（pass@3，cyber） | **81.0** | 未削减版 90.5 / DeepSeek 85.7 / GLM 57.1 / K3 33.3 | 主动做减法的证据 |

**第一个关键点：BenchCAD 的「有无工具」落差，比绝对分数更能说明问题。**

with tools 92.7，without tools 72.8，落差 19.9 分。而 Opus 5.5 是 96.2 / 73.0，落差 23.2 分。DeepSeek-V4.1-Flash-1017 是 81.6 / 41.2，落差 **40.4 分**。

这个落差的含义是：**模型的「裸能力」和「被 harness 放大后的能力」是两条不同的曲线**。落差小，说明模型倾向于一次性把问题想清楚（内化的空间推理）；落差大，说明模型严重依赖外部迭代反馈。DeepSeek 的 40.4 分落差意味着它在单次生成时空间推理很弱，但一旦给了工具调用循环就能补回来——这是典型的「agentic 补偿」。而 K3.1 Pro 的 19.9 分落差，说明它的 3D 空间推理已经部分内化。

对做 Agent 产品的团队，这个指标的实践意义是：**如果你的产品形态是单次生成（比如一键出 CAD 图纸），你该看 without tools；如果你的形态是长循环 Agent，你该看 with tools。同一个模型在两个场景下的相对排名可能完全不同。**

**第二个关键点：幻觉率的下降幅度，比 Terminal-Bench 的提升更重要。**

K3 的 claim-level 幻觉率是 23.4%，K3.1 Pro 是 8.3%——**降了 64.5%**。而且是在「Hard」难度、带工具的设定下测的（官方明确说明这是压力测试，故意挑模型容易出错的样本，不代表日常错误率）。

作为对照：Opus 5.5 在同设定下是 15.0，GLM-5.3 是 22.6，DeepSeek 是 23.3。也就是说，K3.1 Pro 在这个指标上**反超了 Opus 5.5 近一倍**。

这件事的技术含义值得展开。幻觉率不会因为「RL 步数变多」而自动下降——恰恰相反，长程 RL 常常让模型更自信地编造，因为它学会了「给出一个看起来完整的答案」比「承认不知道」更容易拿高分。K3.1 Pro 能把幻觉率砍掉三分之二，说明后训练里显式地加入了**事实性 reward**，而且这个 reward 是 claim-level 而非 response-level 的（否则无法定位到具体哪一句是编的）。

官方在财务章节的表述也印证了这一点：「Financial analysis and investment research demand a high degree of factual accuracy. To address this, we made targeted improvements to K3.1 Pro's factual accuracy.」——这不是通用能力的副产品，是**定向优化**。

**第三个关键点：Business Operation 从 8.9 到 37，是 4.2 倍，但绝对值依然很低。**

这是内部基准，测的是「模拟商业环境里的长程管理与决策」。4.2 倍听起来夸张，但 37 分意味着**三分之二的任务仍然失败**。

我不太愿意把这类内部基准当作能力证明——它没有公开数据集、没有第三方复现，而且「模拟商业环境」的奖励函数设计空间极大。但它传递了一个方向性信息：**长程决策是当前所有模型最薄弱的环节，即使是最强的后训练也刚把及格线从 9 分推到 37 分**。

这和 Terminal-Bench 的 65.7% 形成有趣对照。同样是「长程」，终端任务能到 65%，商业决策只有 37%。差别在哪里？**可验证性**。终端任务的成败是二值的、可自动判定的（测试通过与否）；商业决策的「正确」需要多轮、多维度、甚至事后数月才能验证。RL 的杠杆率，正比于奖励信号的信噪比。

一句话总结这一节：**后训练的收益分布极不均匀，它优先改善「可验证」的能力，而把「不可验证」的能力留在原地。** 这解释了为什么 coding 和 3D 进步神速，而 strategic reasoning 依然挣扎。

---

## 四、一个值得逐帧拆解的案例：36 处「肩部肌肉力臂」错误

官方博客里有个案例，比任何 benchmark 都更能说明「长程 Agent」到底长什么样。

任务：在 [human-atlas](https://github.com/ashemag/human-atlas)（一个开源人体解剖模型，296 个骨骼组件含软骨、402 个肌肉组件）之上，构建一个人类行走动力学模拟器，并配套训练与评估流水线。

过程：**167 个 mission、420 次独立评审**。模型自己分析实验结果、诊断问题、迭代修改控制器。最终，模拟人从「几秒内就瘫倒」变成「交替步态连续行走 11.2 秒」。

真正的转折点在这里：

> When reward shaping failed to improve arm motion, K3.1 Pro did not simply keep adjusting the reward: it ran open-loop probes of the simulator's dynamics, identified and corrected 36 errors in shoulder-muscle moment-arm calculations, and then retrained the controller.

奖励塑形（reward shaping）失效之后，模型没有继续调奖励函数——它去做了开环探测（open-loop probe），发现模拟器里**肩部肌肉力臂的计算有 36 处错误**，修好，再重训控制器。

这个行为模式和「会写代码的模型」有本质区别。它包含三层能力：

**第一层：识别「问题不在我这里」。** 绝大多数模型在 reward 不涨时的默认反应是继续调超参、改奖励、加正则。这是「优化者」的本能。而正确判断是：**优化不动，可能是环境模型错了**。这需要模型对「自己的优化器在什么情况下会失效」有元认知。

**第二层：设计一个能证伪的探测实验。** 开环探测的意思是：不闭环控制，直接给肌肉施加已知激励，观察输出是否符合物理预期。这是一个**主动实验设计**行为——不是被动读日志，而是构造一个新实验来区分两种假设（控制器错 vs 模拟器错）。

**第三层：定位到具体数值错误。** 36 处力臂计算错误，意味着它必须理解 moment arm 的解剖学定义、比对模型实现、并逐项核验。这是领域知识 + 代码阅读 + 数值验证的复合能力。

我的判断是：**这三层能力，才是「long-horizon」这个词的真正含义**。它不是「能跑很多步」，而是「在长循环中保持对『当前失败属于哪一类』的正确归因」。Terminal-Bench 之所以能给到 65.7%，很可能就是因为这类 benchmark 里塞满了「测试挂了但根因在别处」的任务——而那恰好是后训练 RL 最能教出来的东西，因为环境可以自动验证「你修的是不是真因」。

反过来，这也是为什么「Business Operation 只有 37 分」：商业环境里没有 cheap 的 verifier，模型无法知道自己归因对不对。

---

## 五、1M 上下文与双 SKU：服务层才是真正的产品

技术上，1M 上下文早已不新鲜。但 K3.1 Pro 的定价结构透露了另一层信息。

标准版：输入 $2 / 输出 $10，缓存命中 $0.20——**缓存命中价是输入价的 1/10**。官方明确写了「API 自动为重复请求前缀启用上下文缓存计费」，TTL 默认 5 分钟，另有 1 小时档（写入 $4）。

这个价差意味着什么？做一个粗略测算。假设一个 coding agent 会话：系统提示 + 仓库上下文 80K token，每轮新增 2K，跑 50 轮，输出平均 1.5K。

- 无缓存：输入 ≈ 80K + 50×平均 130K ≈ 6.6M token → $13.2；输出 75K → $0.75。合计约 **$14**。
- 全缓存命中（前缀稳定）：6.6M 里约 6.4M 命中缓存 → $1.28 + 0.2M×$2 = $1.68；输出同 $0.75。合计约 **$2.4**。

**接近 6 倍的差距，只取决于你的 prompt 前缀是否稳定。** 这就是为什么「上下文工程」在 2026 年变成了一个成本工程问题：把易变内容（时间戳、随机 ID、动态工具列表）挪到 prompt 末尾，让前缀可缓存，比换一个更便宜的模型省得多。

而 Highspeed 版本（$4 / $20，2-3× 速度）的存在，说明 Moonshot 在明确切分两个市场：

- **批处理 / 长任务**：用标准版，吞吐优先，接受慢
- **交互式编码 / 实时对话**：用 Highspeed，2 倍价格换 2-3 倍速度

这是一个成熟的产品动作。它承认了「同样的智能，不同的时延需求应该有不同的价格」——而不是像很多厂商那样用一个 SKU 打天下，让交互式用户为吞吐买单。对做产品的团队，这个信号很实用：**如果你的 Agent 是后台跑的（CI、批量分析、数据管道），标准版；如果是人在环里的（IDE 补全、客服），Highspeed 的溢价完全可以被用户感知的响应速度覆盖。**

---

## 六、安全：一次可测量、可复现、可争议的「能力减法」

这是整篇博客最不寻常的部分，也是 HN 上 416 条评论真正的战场。

Moonshot 的做法可以拆成三步：

**第一步：定位能力来源。** 他们观察到「vulnerability research performance 随着后训练规模稳定提升」，然后回溯，发现网络安全内容**同时**存在于两个地方：mid-training 的通用语料里，以及 RL 环境池里。

**第二步：做对照实验。** 在不做任何处理的情况下，同一个 checkpoint 在内部基准 xdev-bench-hard 上 pass@3 达到 **90.5%**。这个基准考的是真实漏洞利用：给漏洞源码 + 简短提示 + 二进制，Agent 要在独立沙箱里实现任意代码执行并取回 secret string。任务覆盖 Linux kernel、Node.js、JavaScriptCore、Exim、VirGL，且**缓解措施全部开启**。

**第三步：删除，然后重测。** 从 mid-training 和 RL 两个阶段都移除 cyber 相关内容（保留通用 coding 任务），最终 K3.1 Pro 拿到 **81.0%**。

也就是说：**他们主动放弃了 9.5 个百分点的攻击性 cyber 能力，并把这个数字公开了。**

作为横向对照，同一基准上：DeepSeek-V4.1-Flash 85.7、GLM-5.3 57.1、Kimi K3 33.3。注意最后这个数字——K3 只有 33.3，而 K3.1 Pro 有 81.0。这说明**通用 coding 与长程调试能力的提升，会自然外溢到 cyber 任务上**，即使你删掉了 cyber 数据。官方的表述很诚实：「stronger general coding and long-horizon debugging capabilities generalize to cyber tasks even after targeted data removal」。

**这就是这一节最值得记下的洞察：能力删除是「相对」的，不是「绝对」的。** 你可以让模型相对同 pipeline 的未删减版弱 9.5 分，但你无法阻止通用能力进步把绝对水位继续推高。任何「我们删了数据所以安全了」的叙事都是不完整的。

再看他们的开放权重原则，两条：

1. 不发布会**扩展** cyber 能力绝对前沿的开放权重（K3.1 Pro 的攻击性 cyber 能力「by design」低于自家 pipeline 上限，也落后于已公开三个月以上的闭源前沿模型）
2. 但会**逐步提高**开放权重里可用的 cyber 能力，理由是「让能力渐进扩散，而不是集中在少数闭源系统里，最终让所有软件更安全」

这套逻辑在 HN 上被撕成了两半。反对者的核心论点（我摘几条高质量评论）：

> How will the world get ready without a model that's good at security? ... We can't catch up by hand. The only way to fight this fire is with fire.

> All of my PRs go through an adversarial security review by GLM-5.3, because it's the only smart-enough model with a good understanding of cybersecurity issues that won't regularly refuse the job. Removing that ability from frontier models helps nobody except cyber criminals.

支持者的核心论点：

> If defender A finds a vuln, then defender B doesn't need to find it again. Attackers generally act alone... open source models upgrade the attack and defense by the same amount, so open source cyber capabilities being at the frontier only results in a defender disadvantage.

我倾向于认为**双方都对了一半，而分歧点被大多数人忽略了**：这不是「开源 vs 闭源」的争论，而是「**能力扩散的速度** vs **防御方规模效应生效的速度**」的赛跑。

防御方确实有规模效应（一个漏洞被公开修补，所有下游受益），但这个效应有延迟——从漏洞被发现到补丁被广泛部署，平均是数月量级。而攻击方的能力扩散是即时的。所以在一个「能力每周跳一档」的市场里，**延迟就是净损失**。Moonshot 的「渐进扩散」本质上是在给防御方的规模效应买时间。

但这个论证有个致命弱点，反对者精准命中了：**你无法区分「防御性使用」和「攻击性使用」，因为它们是同一个能力。** 一个能审计你代码的模型，同样能审计别人的代码找漏洞。所以「渐进」这个旋钮，调的其实是「谁能用」，而不是「用来干什么」。

还有一个更微妙的批评值得记录（来自 HN）：

> So they admit that they could do more, but they won't?

这个质疑的合理性在于：如果能力上限是 90.5，你发布 81.0，那么「81.0 是安全水位」这个判断由谁审计？没有第三方能验证 90.5 这个数字，也没有第三方能验证删除是否彻底。**可测量的能力削减，目前仍然是「自证」的。** 这可能是未来一年最需要行业标准的地方——类似于模型卡（model card）但是针对「被移除的能力」的负向披露。

---

## 七、对一线团队的实际意义

抛开叙事，给几个可操作的判断。

**1. 如果你的 Agent 是「长循环 + 可自动验证」，K3.1 Pro 现在值得进候选池。** Terminal-Bench 65.7 意味着它在「测试挂了但根因在别处」这类任务上已经接近 Opus 5.5，而价格是 $2/$10。用 Claude-Code harness 就能直接跑，迁移成本低。

**2. 如果你的场景强依赖「不可验证的长程决策」（战略、投资判断、复杂谈判），不要被 4.2 倍提升迷惑。** 37 分的绝对值说明这类能力还在早期。这类场景目前更可靠的做法是「模型 + 结构化流程 + 人工卡点」，而不是端到端 Agent。

**3. 缓存命中率是 2026 年最被低估的成本杠杆。** 1/10 的价差意味着：优化 prompt 前缀结构的 ROI，远高于换模型。具体做法：静态系统提示 → 仓库/文档上下文 → 对话历史 → 动态工具结果，严格按「稳定性递减」排序。

**4. 关注 11 月 4 日的权重释放。** 3T MoE 的开放权重，实际可部署性取决于量化方案与专家并行实现。参考 K3 的社区经验，真正的门槛不是显存，是**专家路由的负载均衡**——3T 参数里激活部分很小，但 all-to-all 通信会成为瓶颈。自建推理的团队应该先算通信账，再算显存账。

**5. K2 系列的退役时间表要进排期。** 12 月底全量下线，10 月 31 日起新用户不可用。如果生产环境还在 K2.6/K2.7，现在就该做 A/B——尤其注意 K2 是 256K 上下文、K3 系列是 1M，`max_tokens` 与截断策略的隐式假设可能已经错了。

---

## 八、结论：三个判断

**第一，「后训练即产品」会成为开放权重厂商的标准打法。** 当基座权重最终公开（K3 已开源，K3.1 Pro 11 月 4 日），厂商之间的差异只剩三样：后训练算力、环境池质量、服务层工程（缓存/双 SKU/时延）。K3.1 Pro 把这三样都摆到了台面上，而且给出了可复现的数字。这比「我们又赢了某个榜单」有信息量得多。

**第二，「可验证性」正在成为模型能力的隐藏分层维度。** 同一个模型，在 Terminal-Bench 上 65.7%，在 Business Operation 上 37。差距不是能力差距，是**奖励信号质量差距**。这意味着未来两年，最有价值的工程工作不是训模型，而是**构造可验证的环境**——谁能让「商业决策」变得像「单元测试」一样可判定，谁就拿到了下一阶段的金矿。

**第三，安全正在从「对齐叙事」变成「能力会计」。** Moonshot 做的事情，本质上是把「我们删掉了什么」变成一张可审计的报表：90.5 → 81.0，任务集公开、评分脚本明确、对照实验清晰。这个方向是对的，但它暴露了一个新问题：**负向披露没有第三方审计机制**。在能力扩散速度超过防御部署速度的市场里，「相信我，我删了」是最脆弱的承诺形式。

最后一个观察。HN 上有人写道：

> This probably doesn't move the frontier, it just sits at the current frontier.

这话在 2026 年 10 月是对的。但值得注意的是：**当「坐在前沿」的成本从数亿美元预训练降到一次后训练，前沿就不再是少数人的地产，而是一个每周都在被重新测量的坐标。** 开放权重模型落后闭源的时间窗口，已经从一年压缩到大约一个月（ModelCompare 的估算）。这个窗口还会继续压缩——而压缩它的，正是本文讨论的这套「工厂」。

---

## 参考

- Kimi K3.1 Pro Tech Blog: *Advancing Open Intelligence* — https://www.kimi.ai/blog/kimi-k3-1-pro
- Kimi API Platform, Model Inference Pricing — https://platform.kimi.ai/docs/pricing/chat
- Kimi K3.1 Pro Quickstart（1M context / reasoning effort / tool calling）— https://platform.kimi.ai/docs/guide/kimi-k3-1-pro-quickstart
- Artificial Analysis, Kimi K3.1 Pro（Intelligence Index 55，Pareto 线）— https://artificialanalysis.ai/models/kimi-k3-1-pro
- Hacker News 讨论（655 points / 416 comments）— https://news.ycombinator.com/item?id=50212065
- human-atlas（案例中使用的开源人体解剖模型）— https://github.com/ashemag/human-atlas
- Terminal-Bench 4.0 Leaderboard — https://www.tbench.ai/

> 数据说明：文中所有 benchmark 数值均取自 Kimi 官方技术博客及其附录脚注（评估设定 reasoning effort=max, temperature=1.0, top-p=0.95）；第三方对比分数取自各模型技术报告或官方 leaderboard。内部基准（Kimi Code Bench 3.0、Kimi Hallu Bench、xdev-bench-hard、Internal Finance Benchmark）无公开数据集，引用时已标注「内部」。
