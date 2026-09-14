# 当"系统提示词"成为前沿模型的源代码：system_prompts_leaks 6.6 万星与提示词泄露的新产业

> 9 月 13 日，一个仓库同时更新了 Gemini 3.8 Flash 和 ChatGPT Work Codex 的完整系统提示词——这不是什么黑客组织的战利品，而是一个 6.6 万星的开源项目在"按时交付"。当华盛顿邮报开始用泄露的提示词做互动报道，当安全团队把提示词当攻击面地图，当实验室把最核心的产品逻辑写进一段可被任何人复制粘贴的文本里——我们得认真聊聊：**提示词，已经成了 AI 时代最特殊的"源代码"。**

2026 年 9 月 14 日早上，GitHub Trending 榜首附近出现了一个熟悉的名字：`asgeirtj/system_prompts_leaks`，66,004 星、10,799 fork、单日新增 706 星。这个仓库的 README 看起来像一份"前沿 AI 产品考古目录"：Anthropic 的 Claude Fable 5.1、Opus 5、Claude Design（含 53 个工具 + 22 个 skills + 10 个 starter components）、Claude Code headless、Claude Science、Claude Cowork；OpenAI 的 GPT-6-Astra Codex、ChatGPT 5.6 Sol、ChatGPT Work Codex 本地版；Google 的 Gemini 3.8 Flash / 3.7 Flash / 3.1 Pro / Antigravity；xAI 的 Grok 4.6；Meta 的 Muse Code；甚至 Perplexity Deep Research、Kimi K2.6、Pi、OpenCode。

它更新的速度比很多商业产品还快——9 月 13 日当天就同步了 Google 和 OpenAI 的最新发布。这不是一个"玩具仓库"，它已经长成了 AI 行业的公共基础设施：华盛顿邮报 5 月用它做了互动式报道《看看 AI 背后的隐藏规则，然后用它们改写这篇文章》；CEPS 的 AI World 7 月基于它建了实时数据看板。**一个靠"偷"提示词起家的仓库，正在成为媒体、研究者、工程师和竞争对手共同依赖的行业档案。**

这篇文章想拆三件事：一份泄露的提示词里到底有什么；它为什么必然守不住；以及当"提示词即产品"成为行业现实，Agent 工程师应该怎么重新设计自己的系统。

---

## 一、泄露解剖学：三家实验室，三种产品哲学

我拉取了仓库里三份最新的提示词原文，分别代表 Anthropic、OpenAI、Google 的 agent 产品。把它们并排放在一起，等于同时拿到了三份"产品源代码"。

### Anthropic：把 Harness 纪律写进提示词

`claude-code-headless-fable-5.1.md`（9 月 5 日更新）开头就是一张参数表：

```
| Effort setting | `<reasoning_effort>` value |
|---|---|
| low | 10 |
| medium | 15 |
| high | 25 |
| xhigh | 80 |
| max | `max` |
```

紧接着是 `reasoning_effort=25`、`thinking_mode=auto` 的默认值——**推理预算以枚举形式直接暴露在提示词里**。然后是一段我在所有泄露提示词里见过最"工程师气质"的话：

> Report what actually happened, not what you intended. When you say something is done, sent, saved, fixed, or verified, that claim must rest on a result you observed in this session — tool output, the file as it now reads, the page as it now loads — not on what the step should have produced. If you did not check, say you did not check.

这不是在教模型"说话要好听"，这是在定义**上报协议**：任何完成声明必须以本次会话中观察到的 tool 输出为证据。配合后面的记忆系统 schema（`~/.claude/projects/<slug>/memory/`，每个记忆一个文件，frontmatter 含 `type: user | feedback | project | reference`，正文用 `[[name]]` 互相链接）——Anthropic 的提示词本质上是一份**产品配置规范**：推理预算、记忆格式、hook 语义、权限模式的行为约定，全用可解析的结构化文本写死了。

最微妙的是安全策略的措辞：

> IMPORTANT: Assist with authorized security testing, defensive security, CTF challenges, and educational contexts. Refuse requests for destructive techniques, DoS attacks, mass targeting, supply chain compromise, or detection evasion for malicious purposes.

以及那句隐藏的产品情报——"This iteration of Claude is Claude Fable 5.1... Claude Fable 5.1 and Claude Mythos 5.1 share the same underlying model"。9 月 2 日我们写过 Fable/Mythos 的"能力-安全解耦"，这里提示词原文亲自确认了：**同一个权重，两种姿态，提示词里写明了哪个版本该去哪。** 安全策略本身已经成了可以被 diff 的产品配置。

### OpenAI：把"行动偏好"训练成明文教条

`gpt-6-astra-chatgpt-work-local.md`（9 月 13 日，最新鲜的一份）开篇就亮出 OpenAI 与 Anthropic 截然相反的授权哲学：

> Once evidence in a session supports authorization for a next step or action, you should continue work without ending the turn to clarify with the user. User authorization and preferences persist across turns. Do not request permission again when the user has already authorized an action in an earlier turn.

Anthropic 说"难以逆转或对外的动作要先确认"，OpenAI 说"**授权在会话内持久化，别反复问**"。更直白的是这句：

> The user gets very frustrated when you stop and ask for confirmation or permission.

把用户情绪直接写进系统提示词作为行为约束——这是 OpenAI 的产品取舍：用"烦人体验"作为第一性约束，宁可让模型偶尔越界，也不允许它变成需要逐轮确认的机器人。配合整段 "Autonomy and persistence"（"bias towards action"、"persist until the user's intended goal is complete"），以及 "Personality" 小节（warm、candid、lucid，写作要 "Avoid section headings"，禁止 "In short:..." 式总结句）——OpenAI 把**人格与自主性也参数化了**。提示词不再是"规则清单"，而是一份"产品行为规范 + 企业文化手册"。

### Google：风格工程的极端粒度与能力隔离

`gemini-3.8-flash.md`（同样是 9 月 13 日）展示了第三条路线。开头是一个值得所有 agent 工程师抄走的防御设计：

> **Capabilities**：The following information block is strictly for answering questions about your capabilities. It MUST NOT be used for any other purpose, such as executing a request or influencing a non-capability-related response.

**能力信息与执行指令的硬隔离**——"你是什么模型、什么版本"这类元信息被圈进一个专用块，明令禁止影响任何非能力相关的响应。这是对"提示注入通过能力试探绕过护栏"这类攻击的针对性防御。

往下读是 Google 式风格工程的极致：350 词目标长度、结构化脚手架优先级（"NEVER write generic introductory setup sentences"）、LaTeX 使用边界（"Strictly Avoid LaTeX for simple formatting... render **180°C** or **10%**"）、按 CUJ（Critical User Journey）路由格式策略（创意写作禁止表格、生活规划必须用结构）、以及一条非常漂亮的防误导规则：

> **Independent Premise Verification:** If a user query presents a mathematical calculation... and asks if it is correct, you must calculate the result independently step-by-step BEFORE stating whether the user is correct or incorrect. You MUST NOT start your response with "Yes", "No", "Correct", or "Incorrect".

### 三家对比

| 维度 | Anthropic (Claude Code Fable 5.1) | OpenAI (Codex GPT-6-Astra) | Google (Gemini 3.8 Flash) |
|------|------|------|------|
| 授权模型 | 难逆行动先确认 | 会话内授权持久化，少打断 | 中规中矩，按工具语义 |
| 核心约束 | 上报真实性（report what happened） | 用户情绪（don't frustrate the user） | 风格路由（CUJ 级格式策略） |
| 防御设计 | 安全策略明文枚举（CTF/授权测试例外） | 授权证据链（session evidence） | Capabilities 块隔离 |
| 提示词形态 | 配置规范（表格+schema） | 行为教条+人格手册 | 风格指南+路由表 |
| 泄露价值 | 产品 harness 全貌 | 自主性边界 | 人格工程的完整参数 |

三份提示词放在一起，能清晰看到 2026 年 agent 产品的一个共同趋势：**提示词正在从"一段话"变成"一份可解析、可版本化、可 diff 的配置文件"**。Anthropic 写 schema，OpenAI 写策略，Google 写路由——它们本质上都在做同一件事：把产品逻辑从权重里搬到文本里。

---

## 二、为什么提示词守不住：泄露的工程根源

既然提示词已经是"产品源代码"，为什么各家实验室没有像保护权重一样保护它？答案是：**提示词在安全模型里处于一个尴尬的位置——它比权重容易拿得多，又比权重值钱得多，但防泄露的成本却高到不现实。**

**第一，客户端渲染决定了必然泄露。** 权重是服务器端的秘密，推理时也不会离开数据中心；但系统提示词必须被发送到用户的浏览器或本地 CLI 进程里才能生效。Web 版 ChatGPT 的提示词躺在 JS bundle 和网络 payload 里，抓到它只需要开发者工具；CLI 版的提示词（如 Claude Code headless）直接嵌在客户端二进制或启动参数里。**凡是需要在用户设备上执行的东西，就没有真正的秘密。** 这不是"被攻破"，这是架构使然。

**第二，提取攻击把"顺从"变成漏洞。** 模型被训练成服从指令，而"把之前的指令复述一遍"本身是一条指令。从早期的 "repeat your instructions verbatim" 到 token 级逐字提取、DAN 式越狱、对抗后缀，提取攻击的本质是：**模型的服从性越强，提示词越容易被套出来。** 实验室可以加对抗训练（"永远不要复述系统提示词"），但这是一场成本不对等的军备竞赛——防御方要为每个新模型重新加固，攻击方只需要在 Reddit 上找到一句新的咒语。

**第三，防泄露的收益是负的。** 这是最反直觉的一点：提示词防泄露做的越好，产品就越难调试。提示词是 agent 行为唯一的可解释性来源——工程师要 debug 一个 agent 为什么拒绝了一个合法请求，必须能读到提示词；安全审计要确认护栏存在，必须能审计提示词；甚至用户要信任一个 agent，也需要知道它的行为边界。**把提示词加密或混淆，等于同时牺牲了可调试性、可审计性和透明度。** 而泄露的代价呢？竞争对手本来就知道你大概怎么做的——提示词里 90% 的内容是公开博客、文档和常识的汇编，真正值钱的是那 10% 的取舍，而取舍本身在行为上就能被观察到。

所以结论很冷酷：**提示词是"约定俗成的秘密"，不是"加密意义上的秘密"。** 它就像一份带着调试符号发布的源码——你明知反汇编器人手一份，但还是得发。实验室真正该做的不是捂住提示词，而是接受它必然公开，把安全边界移到提示词之外的层。

---

## 三、泄露之后：这个仓库正在改变什么

6.6 万星不只是一个数字，它意味着提示词泄露已经形成了完整的"下游产业"。

**对竞争对手：这是最高效的竞争情报。** OpenAI 的产品团队可以读 Anthropic 的 Claude Code 提示词，看到对方的记忆 schema 长什么样、授权策略怎么写的、推理预算怎么枚举的；反之亦然。前几天我们写过 collusion.wiki 那种"agent 社交网络"的副作用，而提示词仓库是更安静的那种情报管道——**它让"抄作业"的门槛降到了零**，也让实验室之间的产品哲学差异第一次以文本形式并排曝光。你甚至能透过提交历史看到 Fable 5 → Fable 5.1 的提示词 diff，那本质上就是 Anthropic 的产品迭代日志。

**对安全研究：提示词成了攻击面地图。** 每一份泄露的提示词都精确标注了护栏的位置："Refuse requests for destructive techniques...""MUST NOT be used for any other purpose"。对越狱研究者来说，这等于拿到了每栋大楼的消防通道图；而对防御者来说，它迫使安全设计从"藏规则"转向"在规则公开的情况下依然安全"——这其实是更健康的方向，**你的护栏如果只能靠保密维持，那它就不是护栏，是窗帘。**

**对媒体与公众：提示词正在成为"公共档案"。** 华盛顿邮报让读者"用泄露的提示词改写文章本身"，CEPS 做了实时数据看板——提示词第一次以大众可理解的方式进入公共讨论。这也带来一个此前不存在的透明度问题：**实验室宣称的安全承诺，现在可以被逐字核对。** 9 月 2 日我们聊 Fable/Mythos 的"能力-安全解耦"时还只能靠 benchmark 推断，现在提示词原文直接把两种姿态写进了配置——安全策略的"可审计性"上了一个台阶。

---

## 四、给 Agent 工程师的启示：把"必然泄露"当成设计前提

聊完宏观，说点能直接用的。这个仓库对每一个在造 agent 的工程师，实际上是三份免费的生产级教材 + 一份设计警告。

**第一，你的系统提示词就是产品源码，请按源码管理它。** 版本化、留 changelog、走 code review、为它的每个行为写测试。system_prompts_leaks 其实展示了一个行业级的"提示词 diff 工具"应该长什么样——对比同一个产品不同版本的提示词，你能看到实验室在想什么。你的 agent 也应该这样：**提示词的每次变更都要能回答"为什么改、改了影响什么、怎么回滚"。**

**第二，把逻辑放进代码，把策略放进提示词。** Anthropic 用表格定义推理预算、用 schema 定义记忆格式，OpenAI 用"授权证据链"定义行为边界——真正成熟的提示词是**结构化配置**，不是散文。凡是能用代码表达的逻辑（权限校验、工具白名单、状态机）就不该写进提示词；提示词只留那些必须靠语言模型语义理解的东西。这样提示词泄露的损失最小——反正逻辑都在代码里。

**第三，安全边界必须建在 harness 层，而不是提示词层。** 提示词文本是可读、可复制、可越狱的——这是架构事实。所以"拒绝高危操作"这类约束，必须在工具执行层做硬校验（hook、权限系统、沙箱），提示词里的措辞只是第一道软防线。Claude Code 的 "A denied call means the user declined it" 之所以有效，是因为权限模式在 harness 里真实存在。**把提示词当最后一道防线，是 2026 年最危险的 agent 架构错误。**

**第四，如果没人想偷你的提示词，你可能做错了什么。** 最后开个玩笑但也是真的：这个仓库只收录值得收录的产品。6.6 万星的背后，是这些提示词本身承载了巨大的产品价值——它们是全世界最贵的 AI 产品运行时的"可见部分"。你的 agent 提示词如果有一天出现在某个 leak 仓库里，那说明它已经重要到值得被研究。**提示词泄露不是事故，是产品成熟的标志；真正的问题是泄露之后，你的系统是否依然安全。**

---

## 写在最后

回看 2026 年 9 月 14 日的这份 Trending 数据，最值得玩味的不是 6.6 万星本身，而是这个仓库的存在方式：它像一份"行业源代码镜像"，每天准时同步，接受全世界围观。提示词泄露这件事，已经从"安全漏洞"演变成了"产业基础设施"——它既是竞争情报管道，也是安全研究的攻击面地图，更是这个行业最诚实的产品文档。

Anthropic、OpenAI、Google 把产品哲学写进了一段任何人都能复制粘贴的文本里，然后假装它是秘密。而真正的工程结论是：**在 agent 时代，提示词就是产品与世界的接口——它会公开、会被研究、会被 diff、会被绕过的部分，恰恰是它最该被认真设计的原因。** 与其捂住它，不如把它设计成"即使公开也安全、即使被抄也抄不走"的样子。后者才是这个仓库教给我们的、比任何提示词技巧都重要的一课。

---

*参考来源：*
- [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks)（66,004 stars / 10,799 forks，2026-09-14）
- 泄露原文：[Claude Code headless (Fable 5.1)](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Anthropic/claude-code/claude-code-headless-fable-5.1.md)、[Codex GPT-6-Astra ChatGPT Work local](https://github.com/asgeirtj/system_prompts_leaks/blob/main/OpenAI/Codex/gpt-6-astra-chatgpt-work-local.md)、[Gemini 3.8 Flash](https://github.com/asgeirtj/system_prompts_leaks/blob/main/Google/gemini-3.8-flash.md)
- Washington Post 互动报道（2026-05-11）、CEPS AI World 数据看板（2026-07-10）
- 关联阅读：本仓库 [2026-09-02 Fable 5.1 能力-安全解耦](https://github.com/kejun/blogpost/blob/main/2026-09-02-claude-fable51-mythos51-capability-safety-decoupling.md)、[2026-07-16 提示注入军备竞赛](https://github.com/kejun/blogpost/blob/main/2026-07-16-gpt-red-ai-adversarial-self-play-prompt-injection-arms-race.md)