# 一个笑话如何长成 10 万星基础设施：Caveman 与 Agent Token 经济学的"诚实数字"解剖

> 2026-10-03 · AI Agent / 开发者工具 · 本文约 4500 字

## 引言：一个笑话，和三组互相打架的数字

先看三组关于同一个项目的数字：

- **65%**——项目 README 首页的宣传语："Skill make agent talk like caveman. 65% output token saved."
- **8.5%**——JetBrains 实验室用 86 个真实编码任务做配对 A/B 测试后的实测结论：输出 token 只省了 8.5%，宣传的 65% "off-chart"（完全不在图上）。
- **1.4–2.4×**——Adobe Research 发表论文 CAVEWOMAN（arXiv:2606.24083），在 8 个模型、5 个数据集上测得 caveman 风格输出确实能把实现成本降到 1/1.4 至 1/2.4，最好情况 3×。

三组数字都"真"，但讲的是三件不同的事。而这三组数字围绕的项目——**Caveman**（[JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman)）——可能是 2026 年 AI 开发者工具生态里最有意思的一个样本：它从 2026 年 4 月的一个周五玩笑开始，一周 4000 星，如今突破 **100,000 星**，登顶过 GitHub Trending 和 Hacker News 双榜第一，被 ThePrimeagen 做成反应视频（标题："No way this actually works"），被学术论文引用，被 JetBrains 拉进实验室公开处刑——然后，它把处刑结果原封不动挂在了自己 README 的最显眼处。

它的 slogan 本身就是梗：**"why use many token when few token do trick"**（何必用多 token，少 token 也行）。让 AI 编程助手像原始人一样说话：砍掉所有客套、铺垫、总结性废话，只留下诊断和修复方案。代码、命令、文件路径、错误信息一个字节不动。

但如果你只把它当梗，就错过了这个项目真正 valuable 的部分。Caveman 半年来的演化史，实际上是一部**Agent token 经济学的实证研究史**：钱到底花在哪了？压缩输出还是压缩输入？宣传数字和实测数字差 7.6 倍说明了什么？一个项目被独立第三方打脸之后，正确的反应是什么？

本文基于项目 README、JetBrains 测试报告、Adobe CAVEWOMAN 论文和项目内嵌的 benchmark 数据，把这些问题一次拆完。

## 关键数据一览

| 维度 | 数据 |
|------|------|
| 项目 | JuliusBrussee/caveman（Apache-2.0，TypeScript/Python） |
| 起点 | 2026 年 4 月的一个周五玩笑，一周 4,000 星 |
| 现状 | 100,000+ 星；GitHub Trending #1（2026.07）；HN #1；Product Hunt 日榜 #8 |
| 三层架构 | Skill（压缩输出）+ Proxy（压缩读取）+ Middleware（嵌入自建 Agent） |
| 宣传数字 | 输出 token 节省 65% |
| JetBrains 实测 | 86 个真实编码任务，强制激活：**输出 token -8.5%**，成本约 -10%，质量无可测退化（sign test p=0.82） |
| Adobe 论文 | 输出通道压缩：实现成本降 **1.4–2.4×**（最高 3×）；输入通道压缩：**净成本反升 ~1.15×**（最差 2.7×），严格双输 |
| Proxy 实测（repo 内） | 6 类场景 54 次运行：输入 token 总计 **-33.2%**（885,793 → 591,673），18/18 答案校验通过；对照组 Headroom 仅 -6.7% 且 3/18 失败 |
| 单点极值 | 浏览器页面压缩：121 vs 15,704 token（**129.8×**）；记忆文件压缩平均 **-46%** |
| 生态位 | 支持 30+ Agent（Claude Code、Codex、Gemini、Cursor、Windsurf、Cline、OpenClaw…），原生 wrap 10 个 |

## 从玩笑到基础设施：Caveman 的三级火箭

Caveman 的产品结构演化，几乎是踩着"被质疑—回应质疑"的节奏长出来的。理解这三层，就理解了整个项目的逻辑。

### 第一级：Skill——让 Agent 的"嘴"变小

最初的 Caveman 只是一个规则文件（rule file）。一行命令安装：

```bash
npx skills add JuliusBrussee/caveman -g
```

效果立竿见影。README 里的经典对比：

> **正常 Agent（69 token）**："The reason your React component is re-rendering is likely because you're creating a new object reference on each render cycle. When you pass an inline object as a prop, React's shallow comparison sees it as a different object every time, which triggers a re-render. I'd recommend using useMemo to memoize the object."
>
> **Caveman Agent（19 token）**："New object ref each render. Inline object prop = new ref = re-render. Wrap in `useMemo`."

同样的诊断，同样的修复，同样的 `useMemo`——死掉的只有清嗓子的部分。项目自己的总结很精辟：**"Caveman no make brain smaller. Caveman make *mouth* smaller."**（原始人不缩小大脑，只缩小嘴巴。）

关键设计约束有三条，后来被证明是整个项目可信度的基石：

1. **代码、命令、路径、错误信息永不压缩**——只动散文部分；
2. **安全警告和"你确定吗"确认自动恢复完整句子**，然后再切回原始人模式；
3. **从不改写用户的 prompt**——这条在 Adobe 论文出来后显得极具先见之明（后文详述）。

Skill 还带了一族衍生命令：`/caveman lite`（简洁但礼貌）、`/caveman ultra`（纯咕噜声）、`/caveman wenyan`（文言文模式，"because someone asked"）、`/caveman-commit`（一行 Conventional Commit）、`/caveman-review`（一行一条发现：`L42: 🔴 null deref. Guard it.`）、`/caveman-compress CLAUDE.md`（压缩记忆文件，保留所有标题/路径/命令并备份原文）。

### 第二级：Proxy——让 Agent 的"眼睛"变小

这是转折点，而转折的起因是一次公开的打脸（下一节详述）。JetBrains 的结论是：**Agent 的账单大头是"读"，不是"写"，而任何说话风格都治不了"读"**。

于是 2026 年下半年，Caveman 发布了本地 proxy：跑在你的机器上，位于 Agent 和 AI 提供商之间，在每次调用前压缩 Agent 要读的东西——日志、测试输出、JSON、diff、搜索结果。两个设计细节值得注意：

- **每个被压缩的字节都有备份**（本地 SQLite，一个恢复句柄），Agent 随时可以拉回原文。压缩是无损可逆的，这是它和"粗暴截断"类工具的本质区别；
- **完全本地运行**，不经第三方服务器。

Proxy 还附带了一组非常实用的诊断工具：`caveman learn` 读取你机器上已有的数月 Agent 历史，本地分析并按 token 消耗量排序"你的钱都花哪了"，每条附一行修复建议；`caveman learn implement` 把修复逐条交给 Claude Code/Codex 执行，每条 diff 需要你确认，没有让消息变小的修复自动回滚；`caveman trial` 直接对同一任务跑带/不带 caveman 的真实会话 A/B 对比；`caveman browse <url>` 给 Agent 一个压缩后的网页视图，替代 15,000 token 的 accessibility dump。

### 第三级：Middleware——把压缩嵌入你自建 Agent

面向不用终端 Agent、而是用 LangChain / Vercel AI SDK / OpenAI / Anthropic SDK 自己写 Agent 的开发者：一层 wrapper 包住你已有的调用，工具结果在进模型前被压缩，原文留在你的历史里，模型可以取回。TypeScript 和 Python 双栈，stable 1.0：

```bash
npm install @caveman-ai/middleware @caveman-ai/sdk
pip install 'caveman-middleware[langchain]' caveman-sdk
```

三级火箭的关系是"可叠加"：大多数用户从小石头（skill）开始，被账单教育之后升级到大石头（proxy），构建自己产品的团队则直接用 middleware。

## 被 JetBrains 公开处刑：8.5% 对 65%

2026 年 7 月，JetBrains AI 团队发了一篇标题就充满火药味的测试报告：《Speaking to AI Agents like Cavemen Saves 65% of Tokens. We Test.》

他们的动机写得直白："Claim cheap to make. Verify expensive."（吹牛便宜，验证贵。）而且他们抓住了一个关键的逻辑漏洞：**Agent 不是聊天窗口**。Agent 的输出流里，代码、diff、工具调用、精确错误字符串才是大头——而 Caveman 声称自己"不碰这些"。那么在一个真实的 agentic 工作负载里，一个只压缩"工具调用之间的旁白"的 skill，到底能省多少？

实验设置相当扎实：

| 项 | 配置 |
|------|------|
| 测试框架 | HarnessHarbor 0.17（Docker 沙箱、任务级验证器、配对运行） |
| Agent | Claude Code 2.1.200，headless，bypassPermissions |
| 模型 | claude-sonnet-5，reasoning effort low |
| 基准 | SkillsBench 86/87 个任务，每个任务有自动评分测试（0-1 分） |
| 对照 | A 臂：原生 Claude Code；B 臂：Caveman **强制激活**（每条回复都开） |
| 规模 | 3 轮运行，约 240 次计费 trial，总花费约 $106 |

"强制激活"这个细节很重要：Caveman 正常使用时要靠用户或 Agent 自己触发，JetBrains 把它按在每条回复上开——**这意味着测出来的是理论上限**。

结果三连：

**发现一：省 8.5%，不是 65%。** 82 个配对任务上，输出 token 从 592k 降到 542k。宣传的 65% 来自聊天式问答场景（就像 README 里那个 React 对比例子），而真实编码会话里，可压缩的旁白本来就没多少。更有意思的是方法论花絮：他们第一轮 10 个任务的小样本跑出了 **-29.5%** 的惊艳数字——随着样本量增大，数字蒸发，收敛到 -8.5%。报告的结论一句话值得裱起来：**"Never trust a k=1 eval."**（永远别信小样本评估。）

**发现二：质量零退化。** 这是 JetBrains 自称"真正关心"的问题：让 Agent 说话变糙，会不会让它变笨？82 个配对任务：8 个变好，10 个变差，64 个打平；sign test p=0.82，离显著性差得远；平均任务分 0.326（基线）vs 0.311（skill 臂），差距 0.015。早期小样本里"吓人"的差距同样随样本量缩小——是噪声的形状，不是效应的形状。

**发现三：成本节省真实但脆弱。** 按 token 推算应该省约 10%，按任务算确实如此。但整轮的原始总账反而显示 skill 臂**贵了 11.6%**（$40.60 vs $36.39）——全部倒挂来自一个 trial：一个依赖审计任务在 skill 臂膨胀突破了 200k 长上下文计价档，单次计费 $8.29（对照臂同任务 $0.33）。而更早一轮里，同类离群值出现在基线臂（$3.25）。这是任务属性，不是 skill 属性——但它揭示了一个残酷现实：**在长上下文阶梯计价面前，个位数的百分比优化可以被单个离群任务整个抹平**。

## Adobe 的 CAVEWOMAN 论文：压缩的不对称性

如果说 JetBrains 回答了"skill 在 Agent 场景值多少"，Adobe Research 的论文《How Large Language Models Behave Under Linguistic Input and Output Compression》（arXiv:2606.24083，社区昵称 CAVEWOMAN）回答的是一个更基础的问题：**语言压缩这个操作本身，在哪个通道上成立？**

论文设计了一个双通道评估协议：对同一条目，分别压缩"用户的 prompt"（输入通道）和"模型的回复"（输出通道），在 8 个模型 × 5 个数据集 × 5 个压缩级别上测量任务准确率、实现成本和与无约束参考文本的一致性。结论的不对称性非常锋利：

**输出通道压缩：成立。** 大多数 API 模型上实现成本降 1.4–2.4×，四个开源权重模型在公共计价档上全部成立，最好情况 3×。

**输入通道压缩：严格双输（strict lose-lose）。** 把人类 prompt 压成原始人话，净成本不降反升——五基准均值约 1.15×，最差数据集 1.8×，强压缩下 2.7×。原因是模型会**用更长的回复来补偿**含糊的输入，同时准确率还在崩。你以为省了输入 token，实际买了更多输出 token 和更差的结果。

这里必须给 Caveman 的设计决策记一功：**它从不改写用户的 prompt，只动 Agent 的嘴**。README 里那句 "Caveman never rewrites your prompts. Only the agent's mouth." 在论文出来后从设计品味升级成了有实证支撑的正确性。

论文还有一个更微妙的发现，对所有做输出压缩的人都适用：在非推理模型上，**约一半"正确"的生成，其表面文本已经不再蕴含模型自己无约束基线生成的内容**——也就是说答案对了，但表述和模型"本来想说的话"出现了系统性偏离。这种 divergence 在长度控制重打分、多重比较校正和互补语义度量下都存活。翻译成工程语言：压缩输出不是免费的，它改变的不只是长度，还有文本的语义结构——对于要把 Agent 输出直接展示给最终用户的场景（而不是内部工具链），这是一个需要权衡的风险。

（顺带一提，社区对这个方向的独立验证不止一家。9 月初 ponytail 项目发布的对照基准里，caveman 被当作"说话简短但正常开发"的控制臂使用，以证明 ponytail 的效果不是单纯来自话少——一个梗项目被同行当作实验仪器，这本身就是它进入基础设施行列的标志。）

## Proxy 的数字：账单大头在"读"，而"读"是可以砍的

JetBrains 的打脸没有让项目死掉，反而给了它路线图。README 里那句话写得坦荡：**"The JetBrains number is why the proxy exists."**（JetBrains 的数字就是 proxy 存在的原因。）他们测的是 skill 单独作用——2026 年 7 月，proxy 还没发布。而他们的发现是：Agent 的账单大头是读取，说话风格治不了。

于是就有了 proxy 的 pinned benchmark（54 次运行的 Claude Code 基准，provider 上报的输入 token，每场景 3 轮，每个答案对照精确 oracle 校验）：

| 场景 | 直连 Claude Code | 经 caveman proxy | 变化 |
|------|-----------------:|-----------------:|-----:|
| CSV 离群值排查 | 165,823 | 74,484 | **-55.1%** |
| 日志大海捞针 | 148,807 | 74,068 | **-50.2%** |
| YAML 配置漂移 | 132,124 | 71,027 | **-46.2%** |
| 测试输出排错 | 150,377 | 108,514 | -27.8% |
| 部署 JSON 漂移 | 147,975 | 108,939 | -26.4% |
| Dashboard HTML 告警 | 140,687 | 154,641 | **+9.9%** |
| **总计** | **885,793** | **591,673** | **-33.2%** |

18/18 答案校验全过，case 聚类的 95% 置信区间 14.6%–48.5%。同套件里竞品 Headroom 的 wrap 只省 6.7%，且 18 个校验挂了 3 个。

注意那张表里的红行：**Dashboard HTML 场景，caveman 反而多花了 9.9% 的 token**——因为该场景没有可用的压缩变换，proxy 白白付出了自己的开销。维护者在表格下面留了一段话，我认为是 2026 年开源项目里最值得抄写的一段：

> "**Maintainer note.** The HTML row is red and it stays red. That case had no compression transform, so caveman paid its own overhead and won nothing back. The day I hide a red row is the day you should stop trusting the green ones."
>
> （HTML 那行是红的，而且它会一直红着。那个场景没有压缩变换，caveman 付了自己的开销却什么都没赚回来。哪天我藏起了红色的行，你们就该停止相信那些绿色的行。）

数据本身之外，还有两个诚实细节：README 明说这份 benchmark 的原始 harness artifacts 不在仓库 checkout 里，"treat it as a pinned report, not a public reproduction"（当作固定报告，不是可公开复现的实验）；skill 部分的 benchmark 表格位置干脆留着一段占位注释："No reviewed API benchmark result is published here yet."——没有经过人工审查的结果就不发布，宁缺毋滥。

### Token 到底流向哪里：几个刺眼的单点数字

Proxy benchmark 之外，Caveman 顺手测量了几个"没人量过但人人都在付钱"的地方，每一个都挺刺眼：

**1. 浏览器页面：129.8×。** 针对一个 200 行表格问一个聚焦问题，Playwright 的 ARIA accessibility snapshot 要 **15,704 token**，caveman 的压缩视图只要 **121 token**。当然小表单场景只有 2.3× 优势（benchmark 自己写的），但只要你的 Agent 需要"看网页"，这就是数量级的差别。这也解释了为什么各家 browser-use 方案都在卷 snapshot 压缩。

**2. Subagent tax：219k / 267k。** `subagent-tax` 工具测量"每个 subagent 在干任何实际工作之前必须重发的 harness 前缀"。在一台真实机器上，一个 267k 字符的请求里 **219k 字符是工具 schema**。换句话说：你派一个 subagent 去改一行代码，它开口前先付了 82% 的"上下文过路费"。这个数字和业界最近反复讨论的"context engineering"是同一件事的两个侧面——工具定义、系统提示、插件 schema 这些"税"，在多 Agent 编排里是按 subagent 数量乘法征收的。

**3. 记忆文件：-46%。** 五个真实 `CLAUDE.md` 风格文件的压缩测试，平均缩小 46%，标题、代码、路径、URL 逐一验证完整。对重度使用记忆文件的工作流（比如 OpenClaw 这类每天加载 AGENTS.md/MEMORY.md 的系统），这是每次调用都在付的固定成本。

**4. Skill 自身像素化：-61%。** 最赛博朋克的一条：把已安装的 skill 文本渲染成 PNG 图片页，让模型以图像方式"读"——1,069 token 的 skill 变成约 415 token。`caveman convert --dry-run` 会算出哪些 skill 像素化是赚的，逐字节可逆。这背后是一个真实的模型特性：对许多多模态模型，一张密集文本截图的 token 成本低于同样内容的文本 token 成本。用图像通道绕过文本计费——梗是真梗，数字是真数字。

## 诚实工程：这个项目真正的护城河

把上面的碎片拼起来，你会发现 Caveman 最值得写的不是"原始人说话"这个梗，而是它对数字的态度。我把它总结为四条"诚实工程"实践，每一条都和行业惯例反着来：

**1. 把打脸报告挂在 README 首页。** JetBrains 那篇"宣传 65% 实测 8.5%"的报告链接，就放在项目徽章区，和 10 万星、HN 第一并列。README 的说法是："Every number below is either from a committed run in this repo or from a named third party. Nothing rounded up. Where a number is small, it says so. Where a row is red, it stays red."（下面每个数字要么来自仓库内提交的运行，要么来自署名第三方。不上取整。数字小就写小。行是红的就让它红。）

**2. 主动写明对自己不利的机制。** 比如：skill 规则本身会在每次调用时**增加**输入 token，短输出能否回本取决于你的 Agent、缓存和计价方式——这笔账在 `docs/HONEST-NUMBERS.md` 里全额公开。再比如 telemetry：CLI 和 agent hooks 默认上报使用统计（随机安装 ID + 你的 IP），文档里直接写了关闭命令 `caveman telemetry off`，且 skill 单独使用永不上报。

**3. 三个来源的数字并排展示，不替读者做选择。** Adobe 的 1.4–2.4×（聊天式任务）、JetBrains 的 8.5%（agentic 任务）、repo 自己的 50%（十个开发问题、对比"Answer concisely"控制组）——README 把三行放在一张表里，然后写："Read those three together and you get the honest picture."（三个一起读，才是诚实的图景。）

**4. 把复现工具交给用户。** `caveman trial` 让你在自己的工作负载上跑 A/B，`caveman learn` 分析你自己的历史账单。README 原话："That A/B outranks every number on this page."（那个 A/B 比本页所有数字都权威。）一个项目敢于宣布"你自己测的结果比我宣传的重要"，这在营销驱动的 AI 工具生态里几乎是行为艺术。

对照同赛道的工具更能看出差异。README 里有一张与 RTK、Headroom 的对比表（引用均来自对方自己的 README，标注了引用日期），维度选得很刁："压缩什么"、"能不能拿回原文"、"是否回传数据"。RTK 只压 shell 命令输出且 `Read`/`Grep` 工具调用会绕过它；Headroom 在上面那个 54 次运行的基准里 -6.7% 且 3/18 校验失败。Caveman 的差异点始终是两个：**压缩可逆**（本地 SQLite 存原文，一个句柄取回）和**压缩面完整**（说 + 读 + 网页 + 记忆文件 + skill 自身）。

## 给工程师的实用判断：什么时候用哪一层

基于以上所有数字，可以画出一张相当清晰的决策表：

| 你的场景 | 该用什么 | 预期收益 | 备注 |
|----------|---------|---------|------|
| 聊天式问答、代码解释、学习辅助 | Skill | 大（中位数 -50% 输出，Adobe 口径 1.4–2.4× 成本） | 65% 宣传数字真实适用的场景 |
| 日常 agentic 编码（Claude Code/Codex） | Skill | 小（输出 -8.5% 上限，成本约 -10%） | 质量无损（p=0.82），喜欢就用，别指望省大钱 |
| Agent 大量读日志/测试输出/JSON/网页 | **Proxy** | 中大（实测 -33.2% 输入 token；网页场景可达 129.8×） | 真正的账单大头在这里；注意 HTML 类无可压缩场景会倒贴 ~10% |
| 多 subagent 编排、重记忆文件工作流 | Proxy + learn 诊断 | 视 harness 而定 | 先跑 `caveman learn` 看 subagent tax 和 schema 占比，再决定值不值得 |
| 自建 Agent 产品 | Middleware | 取决于工具结果占比 | 原文留在你的历史里、模型可取回，是产品级压缩的正确形态 |
| 输出直接面向最终用户（客服、教育） | 慎用输出压缩 | — | CAVEWOMAN 的 surface divergence 发现：一半"正确"输出的表述已偏离模型本意 |
| 想省"输入侧"的钱（压缩用户 prompt） | **不要用任何 caveman 式压缩** | 负收益 | Adobe 实测严格双输：成本 +15% 起，准确率崩塌 |

三条通用经验，超出 Caveman 本身：

**第一，先测量，后优化。** Agent 成本优化的第一动作永远是搞清 token 流向——你机器上现成就有数月历史，`caveman learn`（或任何等价分析）五分钟就能告诉你答案。没有测量的压缩是在黑暗里挥刀。

**第二，输出压缩是止痛药，输入压缩才是手术。** 大多数团队的 Agent 账单结构是"读"占绝对大头（JetBrains 的核心发现、subagent tax 的 82%、ARIA snapshot 的 15k token 都指向同一结论）。调 Agent 的说话风格是最低成本的入门动作，但真正的节省在工具输出、页面快照、harness 前缀这些"读"的通道里。

**第三，小样本会系统性骗你。** JetBrains 的 -29.5% 幻影、ponytail 基准里差点发表的 4% 假差距（SessionStart hook 污染了 baseline 臂）、CAVEWOMAN 的多重比较校正——2026 年下半年三个互相独立的评估工作，不约而同把"never trust a k=1 eval"写进了结论。Agent 时代的工程评估，样本量和配对设计不再是学术洁癖，而是防止你基于幻觉数字做架构决策的生存技能。

## 结语：梗的保质期，和诚实的复利

Caveman 的故事有一个反直觉的结尾。按常理，一个靠梗爆红的项目，在被权威第三方把 65% 打回 8.5% 之后，星数应该崩盘——营销数字被证伪等于产品死亡。但实际发生的是：项目把打脸报告挂上首页，照着报告的结论造出了 proxy，把 Adobe 的论文和自己的三层架构焊在一起，然后在每张 benchmark 表里保留红色的行。100,000 星是在这之后到的。

梗负责获客，诚实负责留存。"原始人说话"让 Caveman 一周拿到 4,000 星，但让它从梗变成基础设施的，是它对数字的态度：宣传数字、第三方打脸数字、自己测的数字，全部并排公示，谁也不藏。在一个充斥着 "10x productivity" 和 "90% cost reduction" 的 AI 工具生态里，这种把 HONEST-NUMBERS.md 当核心文档维护的项目，本身就是稀缺品。

而对整个行业，Caveman 半年演化史留下的最重要一份遗产，可能就是把 Agent 的 token 经济学第一次测了个明白：**Agent 写起来像求职信，读起来像消防栓**（"Most agents write like a cover letter and read like a firehose."）——求职信那部分只占账单的零头，消防栓那部分才是账单本身。谁去关消防栓，谁才真正省钱。

Why use many token when few token do trick. 但更重要的是：know which token do trick.

---

**参考链接**

- 项目仓库：https://github.com/JuliusBrussee/caveman
- JetBrains 测试报告：https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/
- Adobe CAVEWOMAN 论文：https://arxiv.org/abs/2606.24083
- ThePrimeagen 反应视频：https://www.youtube.com/watch?v=L29q2LRiMRc
- HN 讨论：https://news.ycombinator.com/item?id=47647455
- 本文相关旧文：《ponytail：最懒资深工程师的 Agent 方法论》（2026-09-06）、《Agent 输出的认知负荷问题》（2026-09-11）

## 附录：十分钟上手路径（如果你今天就想试）

按 README 的"first five minutes"整理，顺序即优先级：

**小石头（Skill，零风险）**

```bash
npx skills add JuliusBrussee/caveman -g
```

1. 随便问一个编码问题，观察 preamble 消失、答案保留；
2. `/caveman lite` 调到"简洁但礼貌"，受不了再 `/caveman ultra`；中文用户可试 `/caveman wenyan` 文言模式；
3. `/caveman-compress CLAUDE.md`（或 AGENTS.md）压缩记忆文件——它会备份原文，标题/路径/命令验证完整；
4. 想退出：说一句 `stop caveman`，正常散文回归。

**大石头（Proxy，先测量再决定）**

```bash
npm install -g @caveman-ai/cli && caveman setup --install
```

1. **先跑 `caveman learn`**——本地读取你已有的 Agent 历史，按消耗排序你的 token 去向，每条附一行修复。README 说这是"本 README 里最有价值的五分钟"，我同意：如果你的历史显示账单大头是工具 schema 和网页 snapshot，再往下走；
2. `caveman claude`（或 codex/gemini/opencode/openclaw…）把 proxy 挂到 Agent 前面；
3. `caveman shrink -- pnpm test` 压缩测试输出；`caveman browse <url>` 替代整页 ARIA dump；
4. `caveman trial -- claude` 在你自己的真实任务上跑一次带/不带对比，`caveman trial report` 看差异——记住项目自己的话：这个 A/B 比它 README 上所有数字都权威；
5. `caveman stats` 长期盯账单；不想要遥测：`caveman telemetry off`。

一个提醒：如果你在用长上下文阶梯计价的模型（如 200k 档），单个膨胀任务就能抹平整月优化（JetBrains 的 $8.29 教训）。压缩工具降低的是期望值，不是方差——对账单波动敏感的团队，方差控制（任务拆分、上下文预算、及时 compact）仍是另一门必修课。
