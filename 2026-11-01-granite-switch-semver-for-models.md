# 当模型开始发补丁版：IBM Granite Switch 4.1.1 深度拆解——冻结的基座、可按需激活的 aLoRA，与「模型即软件」的真实代价

2026 年 10 月 14 日，IBM 发布 Granite Switch 4.1。13 天后，10 月 27 日，4.1.1 发布。

如果你只看版本号，这像是一次无关紧要的补丁：两个 adapter 里只有一个换了权重，基座一个参数都没动，prompt 格式、调用方式、读出逻辑全部不变，官方文档的原话是「fully backwards compatible with 4.1, no migration」。但这次 patch release 值得单独写一篇长文，因为它把一个过去只存在于论文和 demo 里的说法，第一次做成了可复现的工程事实：

**模型的版本号，第一次真的具备了软件版本号的语义。**

不是"我们发了新模型，请重新做评测、重新调 prompt、重新压测、重新迁移"这种假 semver，而是：`4.1.1` 相对 `4.1` 的差异，等于一个 patch 应该有的差异——基座二进制不变，只替换了一个动态库，旧调用方零改动。

这件事的技术含量，全在"怎么做到"这四个字上。而它的工程代价，也全藏在"零改动"背后没人愿意讲的地方。这篇文章分三层拆：架构层（一个 checkpoint 里到底装了什么）、内核层（为什么这件事以前做不快）、以及供应链层（当 adapter 变成可以独立发版的依赖，会发生什么）。

---

## 一、先看清这个"模型包"：它不是一个模型，是一份依赖清单

Granite Switch 4.1.1 不是"训练了一个新模型"。它是一个**被编译出来的产物**。

一个部署单元里并置了四样东西：

| 组件 | 具体形态 | 是否在 4.1.1 变动 |
|---|---|---|
| 基座 | `ibm-granite/granite-4.1-30b`，30B 参数，128K 上下文（另有 8B 版本） | ❌ 完全冻结 |
| `decision` aLoRA | 通用决策 adapter，输入「状态 + 带标签选项的问题」，输出选项上的 softmax 分布 | ✅ 权重更新 |
| `guardian-core` aLoRA | 安全决策 adapter，检测 harm / jailbreak / 脏话 / 暴力 / 色情 / 社会偏见 / 不道德行为 | ❌ 未变 |
| 语音编码器 | `granite-speech-5.0-470m-turboctc`，470M 参数，非自回归 conformer CTC | ✅ 语言从 1 种扩到 7 种 |

这四样东西被 `granite-switch` 0.1.1 这个 composer 打包成**一个** HuggingFace 仓库、**一个** vLLM checkpoint。adapter 的激活不是靠请求参数指定 `adapter_id`，而是靠 **chat template 里的控制 token**——模型自己在生成过程中，在它内部的 "switch 层" 判断当前 token 该套哪个 adapter。

这个设计选择非常关键，也是后面所有性能讨论的根源：**adapter 的切换粒度是 token，不是 request。**

传统 vLLM 多 LoRA 部署的假设是"一个请求进来，指名一个 adapter，整条序列都用它"。Granite Switch 打破了这个假设：同一条生成轨迹里，前半段在聊天，中间一个控制 token 之后变成"在 8 个选项里选一个"，再来一段又变成"把关这条回复是否安全"。对 serving 引擎来说，这是它从来没被设计来处理的负载。

这也是为什么 IBM 非得自己写 kernel——不是炫技，是现有路径在这个负载下会塌。

### 版本表本身就是接口契约

看官方模型卡给的版本对照表，比任何架构图都更能说明问题：

| Revision | Tag | Adapters | Speech |
|---|---|---|---|
| **4.1.1**（latest, `main`） | `granite-switch-4.1.1-30b` | `guardian-core`, `decision`（权重更新） | 7 语言 |
| 4.1 | `granite-switch-4.1-30b` | `guardian-core`, `decision` | 英语 |

`main` 走最新，每一个 release 都打了 tag，可以 pin。回滚的方式就是 `revision="granite-switch-4.1-30b"`——这一行代码在 2026 年的 LLM 部署里已经算奢侈了。绝大多数团队回滚一个模型版本的方式是：找到上周的镜像 tag、翻 CI 记录、祈祷权重文件还在对象存储里没被生命周期策略删掉。

"能给模型 pin 版本"听起来平淡，但它是一个前提条件：**没有可 pin 的版本，就没有可信的回归测试；没有回归测试，就没有资格谈"更新模型"。** 大多数团队所谓的模型升级，本质是一次没有 baseline 的重新赌博。

---

## 二、aLoRA：这次发布真正的技术地基

要理解 4.1.1 为什么能"只换一个 adapter 就发版"，得先理解 aLoRA（activated LoRA）解决的是什么问题。

### 普通 LoRA 推理时到底慢在哪

LoRA 的训练成本很低——99% 的权重冻结，只训练低秩分解出来的 A、B 两个小矩阵。但**推理**时的账不一样。

标准 LoRA 的做法是把 adapter 的增量**叠加进每一层的权重**，然后整条前向都用这个被修改过的权重。问题出在 KV cache 上：一旦你在对话中途切换 adapter，被修改过的权重会让此前算出的 K/V 全部失效——因为它们是用另一套权重算的。于是引擎必须**从对话开头重新 prefill 一遍**。

一段 30K token 的上下文，切一次 adapter 就要重算 30K token 的 prefill。这不是"稍微慢一点"，这是把首 token 延迟直接乘以一个与上下文长度成正比的系数。

IBM 的说法很直白：传统 LoRA 的做法，让"长对话中途插入一次专项判断"这种 Agent 时代最高频的操作，成本变成不可接受。

### aLoRA 的关键取舍：只在生成段激活

aLoRA 的思路是把 adapter 的作用域从"整个前向"缩到"激活之后的那一段"。它直接复用基座已经算好、存在 KV cache 里的 embedding，不重算历史。IBM Research 公布的量级是：单个任务上 aLoRA 比传统 LoRA 快 **20–30 倍**，一次包含多次 aLoRA 调用的端到端对话最多快 **5 倍**。

代价是什么？论文里写得很诚实：因为 adapter 拿不到"任务感知"的 embedding（那些 embedding 是 base 模型为原始请求算的），前几版 aLoRA 的精度打不过普通 LoRA。解决办法是**把 rank 调大**，用更大的网络容量从通用 embedding 里榨出更多上下文线索。

于是有了一个非常反直觉的工程结论：**aLoRA 是用显存换延迟，而且在小 rank 场景下这笔交易并不划算。** 这也解释了后面 SWITCH kernel 为什么把"混合 rank"当成头号优化目标——aLoRA 天生就要用大 rank，而一个模型里同时装着一堆不同 rank 的 adapter 是常态，不是例外。

官方仓库里那张 race 遥测图给了最直观的对比：同样的模型、同样的硬件，跑到 5/16 个查询时，aLoRA 的 KV cache 命中率是 **74%**，普通 LoRA 是 **29%**（1/16）。命中率的差距不是性能指标，是**成本结构**的差距——它决定了你的账单是按"生成了多少 token"算，还是按"重算了几遍上下文"算。

### JEV 51.33 这个分数该怎么读

4.1.1 的 `decision` adapter 在公开的 Jev Decision Index v0.3 上，用文档规定的调用配方（固定 decision-engine system prompt → `State:` 轮走冻结基座 → `### DECISION` 轮给出问题和单 token 选项标签 → 读第一个 assistant token 的 logits 做 softmax）跑出的分数是：

| Overall | Knowledge | Language | Retrieval | Tools | Arts |
|---|---|---|---|---|---|
| 51.33 | 34.8 | 58.5 | 59.8 | 69.0 | 25.9 |

**必须说清楚：这个分数不能和通用 benchmark 横向对比。** 它是机会校正后的加权聚合，测试集是决策类任务，满分 100 不代表"51 分等于不及格"——决策任务的随机基线远高于 0（选项越少基线越高），51.33 在一个 4–8 选项的决策集上意味着"显著高于随机，但远未到可靠"。

真正值得注意的是**内部结构**：Tools 69.0 和 Retrieval 59.8 明显高于 Arts 25.9 和 Knowledge 34.8。这个分布讲了一个很具体的故事——**结构化的、有明确工具调用语义的决策，模型已经能做；开放域的、需要世界知识和审美判断的决策，还差得远。**

对做 Agent 的人，这是一条可以直接照抄的选型规则：把 decision adapter 用在"给定状态，从有限动作空间里选一个"的场合（路由、分流、是否放行、走哪个工具），不要用在"这个方案好不好"这种没有客观 label 的判断上。后者不是 adapter 能修的，是基座世界知识的问题。

### Doom 与 60–100 次决策/秒

官方博客里最不像企业 PR 的一段，是 Doom 的实验：一个自定义的 3B Granite Switch 模型在游戏里做分裂决策，**每秒 60–100 次**，对比 Jev 报告的 **10 次/秒**。

这个对比之所以重要，不是因为它好玩，而是因为它标定了一条**延迟下限**：当决策被压缩成"一次前向 + 读几个 label token 的 logits"，它就不再是"生成一段文本"这个量级的操作。生成式决策要 decode 出 `{"action": "shoot"}` 这一串 token，每一步都要走一遍完整采样；logits 读出只需要一个 forward，且这个 forward 的 KV cache 是和聊天共享的。

60–100 Hz 意味着 **10–16ms 一次决策**。这个数字在机器人、游戏 AI、实时风控、交互式 UI 里有完全不同的意义——它把"LLM 能不能进控制回路"从"理论上可以"变成了"延迟预算够"。

而且这个 3B 模型还能**同时解说**。这一点最容易被忽略：同一个 checkpoint 里，决策走 adapter、解说走基座，两者共享同一份 KV。这不是"两个模型拼起来"，是"一个模型的不同部分同时在线"。传统的做法要么跑两个模型（双倍显存、双倍 prefill），要么串行（延迟翻倍）。

---

## 三、SWITCH kernel：为什么这件事在 2026 年之前做不快

架构讲清楚了，接下来是最硬的部分：**为什么必须改 kernel。**

vLLM 的多 LoRA 支持建立在 Punica 的 SGMV kernel 上。它在"一个请求一个 adapter、全程不变"的经典场景下表现很好，Granite Switch 最初就是直接用的。但有两个设计选择，在 Switch 的负载下代价极高。

### 问题一：每个线性层三次 launch

对每一个被 LoRA 包裹的线性层（QKV、O、gate/up、down），Punica 依次启动三个 kernel：

1. 基座 GEMM
2. **shrink**：`x · A`，写进一个 fp32 buffer
3. **expand**：`buffer · B`，加回输出

在 decode 阶段，batch 小、序列短，每个 kernel 本身的计算量都很小，**launch 的固定开销占比极高**。三个 launch 意味着三份固定开销，而这部分开销和"这个 adapter 有多重要"完全无关。

### 问题二：所有 adapter slot 按最大 rank 分配

这一条更致命。vLLM 用**引擎级**的单个 `max_lora_rank` 来分配堆叠的 LoRA 权重和 shrink buffer。

意思是：只要你加载了一个 rank-512 的 adapter，哪怕它旁边还有 11 个 rank-32 的 adapter，**所有请求都会按 rank-512 的宽度计算**——包括那 92% 只需要 rank-32 的请求。

在一个"通用 adapter + 一堆专家 adapter"的模型里，这不是边缘情况，这是**主路径**。而 aLoRA 恰恰因为精度补偿的需求，天生倾向大 rank。两个问题叠在一起：你为了精度用了大 rank，又因为一个大 rank 拖慢了所有小 rank 的调用。

### SWITCH 的六个字母

IBM 把自己写的 kernel 命名为 **SWITCH**，恰好每个字母对应一个设计决策：

- **S**witched delta —— 被切换的增量，而不是全量重算
- **W**-ext fusion —— 把 base GEMM 和 shrink 融合成**一次** fused GEMM
- **I**n-place —— expand 就地写回，不再分配临时 buffer
- **T**iled —— 分块处理
- **C**onditional skip —— 无 adapter 时跳过
- **H**eterogeneous rank —— **每个 adapter 按自己的 rank 展开，不再 padding 到 max**

前五条把三次 launch 压成两次（fused GEMM + 就地 expand），最后一条解决 padding 浪费。

### 数字

在 Granite 4.1 3B、batch 32 上：

| 场景 | SWITCH 相对 Punica |
|---|---|
| 所有 adapter 同 rank | **1.2–1.4×** 更快 |
| 混一个 rank-128 在 rank-32 里 | **最高 2.5×** 更快 |
| 混一个 rank-512 在 rank-32 里 | **最高 5.9×** 更快 |
| 空闲（无 adapter 激活） | **略慢于**原生 vLLM |

最后一行必须被单独拎出来说，因为它是这份技术报告里最诚实的一句话：**这套优化不是免费的。** 当没有任何 adapter 激活时，vLLM + SWITCH 比原生 vLLM 慢一点点——fused kernel 的通用路径有额外开销。

这条曲线定义了这个架构的适用边界：**如果你的负载里 adapter 调用占比很低（比如 95% 的请求都是纯聊天），Granite Switch 是在为一个你用不上的能力付税。** 只有当"每几次生成就要插一次结构化判断"成为常态时，这笔账才划算。

而 Agent 场景恰好就是这种常态。一个典型的工具调用循环：读用户意图（决策）→ 生成工具参数（聊天）→ 校验参数是否越权（决策）→ 生成结果解释（聊天）→ 安全检查（决策）。**决策和生成在同一个循环里高频交替**，这正是 SWITCH 那 5.9× 派上用场的地方。

还有一个限制不能漏：这套 kernel **目前只是 Granite Switch 的 vLLM backend 的一部分，不是其他架构的 drop-in 替代**，数字是单卡（TP=1）的。它支持张量并行，但没有给出多卡数据。这意味着你在 8 卡上做 TP 部署时，能拿到多少收益是未知的——**不要拿单卡数字去写容量规划。**

---

## 四、语音这条链路：整个发布里最值得学的一处"诚实"

4.1.1 最大的用户可见变化，是语音从 1 种语言扩到 7 种（英、法、德、西、葡、意、日），并且直接输出**带标点和大小写的转写文本**。

工程实现上，它是把一个 470M 的非自回归 conformer CTC 编码器**共置（co-located）**在同一个 checkpoint 里。调用方式完全不变——还是同一个 `/v1/chat/completions`，只是 content 里多了一个 `input_audio` 片段：

```python
response = client.chat.completions.create(
    model="ibm-granite/granite-switch-4.1-30b",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "Answer the question in the audio."},
        {"type": "input_audio", "input_audio": {"data": "<base64-wav>", "format": "wav"}},
    ]}],
)
```

没有独立的语音服务，没有单独的 `/v1/audio/transcriptions` 端点，没有"先 ASR 再喂给 LLM"的两跳延迟。语言从音频里自动检测，不用传 `language` 参数。转写结果被**拼接（splice）进 chat context**，替代原来的 audio content part。

省下的不只是延迟。真正省掉的是**一整条运维链路**：一个独立的语音服务意味着独立部署、独立扩容、独立监控、独立版本、独立的鉴权和限流、以及两个服务之间那条永远会在半夜断掉的网络连接。把 470M 编码器塞进已有 checkpoint，等于把这条链路降级成一个配置项。

### 但它明确说了"没有联合训练"

模型卡里这段话，语气克制但信息量极大：

> The speech encoder and the LLM are not yet jointly trained — there is no trained projection coupling them together yet; see docs/AUDIO.md for the full design and limitations (**no decode-time steering**).

翻译成工程语言：

1. **编码器和 LLM 之间存在一个未训练的投影层。** 转写出来的文本是"硬拼"进上下文的，不是一个学出来的跨模态对齐。这意味着上限被锁在"ASR 有多准"上——ASR 错了，LLM 没有任何机会用声学信息去纠正。
2. **没有 decode-time steering。** 解码时不能反过来引导 ASR。真人在嘈杂环境里听不清一个词，会用上下文去猜；这个架构做不到——ASR 在 LLM 解码之前就已经定稿了。

这个限制在什么场景下致命？**专有名词、产品型号、人名、代码标识符。** 通用 ASR 在这些词上错误率最高，而这些恰好是企业场景里最需要准确的部分。一个"把客户名念错"的会议纪要助手，比一个"没有语音功能"的助手更糟——因为它看起来能用，于是没人复核。

所以在评估这个能力时，要问的不是"支持几种语言"，而是"我的领域词汇表能不能喂给它"。当前架构下，唯一可行的补救是在 prompt 里塞术语表让 LLM 做后处理纠正——**这本质上是在用第二个模型修补第一个模型的错误，成本翻倍且不可靠。**

我把这件事称为"这次发布里最值得学的一处诚实"：IBM 完全可以在博客里只写"7 语言、带标点"，没人会去翻 docs/AUDIO.md 确认是否联合训练。他们写了，并且在模型卡里用加粗标出来。这种披露质量，比多支持三种语言更有价值。

---

## 五、单端点的经济学：显存几乎不涨，这是重点

官方反复强调一句话：

> All three of these technologies (along with the underlying base model) are composed into one model, **taking up approximately the same amount of VRAM on a GPU as the base model would by itself.**

这句话如果成立，它的意义远超"省显卡"。

30B 模型（bf16）光权重就是 60GB 左右，加上 128K 上下文的 KV cache，一台 80GB 的卡勉强够单并发长上下文。在这个预算里再塞一个 470M 的 ASR 编码器（约 1GB）和两个 aLoRA，在总量上是噪声。

对比一下传统方案要付的显存代价：

| 方案 | 需要常驻的模型 | 相对成本 |
|---|---|---|
| 各自独立部署 | 30B chat + 30B decision + 独立 ASR 服务 | **2× 基座 + ASR** |
| 一个基座 + 动态加载 LoRA | 30B + N 个 adapter（KB 级） | ~1× 基座，但切 adapter 要重算 prefill |
| **Granite Switch** | 30B + adapter + 编码器（同一 checkpoint） | **~1× 基座** |

这三行的差别不在数字，在**可行性**。第一行在很多私有化场景里直接出局——客户给你的就是两张卡，你没法部署两个 30B。第三行才有机会。

这就是"模块化"真正的商业价值：**它不是让强者更强，而是让中等预算的部署能同时提供多种能力。** 一个 8B 版本在单张 24GB 卡上跑 chat + decision + 7 语言语音，这个组合在三年前需要一整个机柜。

### 后端与兼容性

- **vLLM**：官方推荐路径，`pip install "granite-switch[vllm]>=0.1.1"`，接受 vLLM `0.26.x` 到 `0.30.x` 五条线，`transformers>=5.16`，PyTorch 2.11+ / CUDA 13+
- **HuggingFace Transformers**：原型验证路径，同一份 checkpoint，无需转换
- **llama.cpp**：原生推理支持
- **API 兼容**：可以直接顶替 `/v1/systemone` 的调用位置

最后一条容易被忽略但很关键：`/v1/systemone` 是 Jev / typesafe.ai 那套"system one 决策模型"的接口约定。Granite Switch 兼容它，意味着**替换一个闭源决策模型不需要改上层代码**。这是一个非常明确的竞争动作——不是"我们也做了决策模型"，而是"你可以把我插到你已有的位置"。

### 什么时候该用，什么时候别碰

我把适用边界整理成一个判断清单：

**该用：**
- Agent 循环里决策与生成高频交替（工具路由、参数校验、放行判断）
- 私有化部署，显卡预算被硬约束，但需要多能力
- 需要极低延迟的结构化输出（10–16ms 级）
- 已经在用 `/v1/systemone` 且想摆脱单一供应商

**别用：**
- 负载 95% 以上是纯生成（在为用不上的能力付 SWITCH 的额外开销）
- 需要多卡 TP 且对吞吐有硬指标（官方只给了 TP=1 数字）
- 语音场景涉及大量专有名词（未联合训练 + 无 decode-time steering）
- 需要开放域判断质量（Arts 25.9 / Knowledge 34.8 说明这条路还长）

---

## 六、当 adapter 变成可以独立发版的依赖

现在说这篇文章真正想说的部分。

4.1.1 演示的流程是：训练一个新的 adapter → 塞进已有 checkpoint 的槽位 → 发 patch 版 → 旧调用方零改动。IBM 明确说了下一步：

> We're working on tutorials and an **Adapter SDK** so developers and third-party providers can build their own adapters — iterate on versions, test features, and ship updates the way you ship software.

注意 "third-party providers"。这句话一旦落地，模型的供应链结构就变了：**基座是运行时，adapter 是包，而包的作者不一定是基座厂商。**

这在软件世界里是常态，在模型世界里是新局面。而软件世界过去三十年踩过的坑，会一个不落地重演——只是速度更快，因为模型的行为差异比库的行为差异难观测得多。

### 坑一：semver 的"兼容"承诺在模型上不成立

软件里的 patch 版兼容性，靠的是**接口不变**。模型里的"接口"是什么？

对 `decision` adapter，IBM 说得很具体：prompt 格式不变、调用方式不变、读出逻辑不变（读第一个 assistant token 在 label 上的 logits）。这三条是**结构性的接口**，它们确实没变，所以旧代码能跑。

但还有第四条没被承诺：**概率分布的语义不变。**

同一个输入，4.1 给出 `{approve: 0.71, reject: 0.29}`，4.1.1 可能给出 `{approve: 0.58, reject: 0.42}`。结构完全兼容，调用完全正常，但如果你在业务层设了 `if p > 0.65 then auto_approve` 这样的阈值，**这次 patch 悄悄改变了你的自动放行率**。

这就是模型版 semver 最危险的地方：**破坏性变更可以发生在"接口完全兼容"的外壳下。** 库不会在你调同一个函数时悄悄改变返回值分布；模型会。

结论很硬：**用模型做阈值决策的系统，必须把 adapter 版本 pin 死，并且把"分数分布漂移"纳入监控。** 只监控"调用成功率"和"延迟"是不够的——那两项在这次变更里都不会动。

### 坑二：组合爆炸，而评测是组合不起来的

一个模型里装 12 个 adapter function 时，理论上限是 2^12 种组合。每个组合的行为不是各组成部分行为的简单叠加——adapter 之间会相互影响，因为它们的增量最终作用在同一组权重上。

IBM 的应对是在 token 级别用 Mellea 强制输出 schema（"a LoRA adapter trained to a specific input/output contract — a score, a decision, a rewritten query — with the output schema enforced at the token level"）。这在**契约层**是有效的：输出一定符合格式。

但格式正确不等于语义正确。`{"risk": "low"}` 是合法 schema，也可能是错误判断。而当你组合了 5 个 adapter，出错时你很难归因——是某个 adapter 的权重退化了？是组合产生了干扰？还是上游检索给的上下文不对？

**这就是"模型即软件"这个比喻最脆弱的接缝：软件的组合测试可以穷举，模型的组合测试只能抽样，而抽样在非确定系统上连"通过"的定义都不清楚。**

务实的做法是把责任划分清楚：
1. **单 adapter 级**：厂商或 adapter 作者必须给出该 adapter 在固定 eval 集上的分数，且每个版本都给（4.1.1 给了 JEV 分数，这一点做得对）
2. **组合级**：由集成方负责，且只能覆盖你**实际部署的那几个组合**，不要试图覆盖可能的组合
3. **端到端**：用生产流量回放，比任何 benchmark 都可信

### 坑三：第三方 adapter 是一个新的攻击面

这一条我认为最被低估。

一个 adapter 是几 MB 到几十 MB 的权重矩阵。它不像 pickle 那样能直接执行任意代码（权重是纯数值），但它能做的事足够糟：**在不触发任何安全告警的前提下，改变模型对特定输入的行为。**

想象一个从社区装的 "compliance-check" adapter：它在 99.9% 的输入上表现完美，但在某个特定 token 序列出现时，让 guardian adapter 的输出概率偏向"安全"。没有代码执行，没有网络请求，没有异常日志。模型卡上写着"提升合规检测准确率"，评测分数确实提升了。

这不是假想。2026 年我们已经看过 Skills 生态的供应链事故、MCP server 的投毒、IDE 插件的即时后门。adapter 是同类问题的下一个载体，而且比它们都更隐蔽——因为**adapter 的"行为"没有源码可读。** 你可以 review 一个 Skill 的 Markdown，可以 review 一个 MCP server 的 Python，但你没法 review 一个 LoRA 的 4096×32 的浮点数矩阵。

所以一旦 Adapter SDK 开放，会立刻出现三个刚需：
- **adapter 的签名与来源追溯**（谁训的、用什么数据、在什么基座上）
- **adapter 的行为测试套件**（不是准确率，是"对特定触发词的鲁棒性"）
- **组合白名单**（只允许经过验证的 adapter 组合上线，而不是任意 compose）

IBM 现在用的是 Apache 2.0 + 自家 library，没有这个问题。但他们在博客里主动把"第三方 adapter"写成路线图，就意味着这个问题一定会来。**开源生态的速度永远快过治理机制的建设速度，这一点在 2026 年被反复验证。**

### 坑四：可复现性依赖 composer 版本

模型卡里有一句非常容易被划过的话：

> This checkpoint is produced with `granite-switch==0.1.1` by composing the base model with the aLoRA versions of `guardian-core` ... plus the ASR cascade.

并且给了完整的 compose 命令。这是好事——**模型产物是可复现的构建结果，而不是一个黑盒二进制。**

但这也意味着：**你的模型行为依赖于 composer 的版本。** `granite-switch` 0.1.2 改了 control token 的注入方式，或者改了 adapter 合并的数值精度（fp32 累加 vs bf16），你 compose 出来的"同一个模型"就不是同一个模型了。

软件世界对这件事的解法是 lockfile。模型世界现在还没有。你只能在模型卡里手写 `granite-switch==0.1.1`，然后祈祷下游没人在 CI 里 `pip install --upgrade`。

**这是一个明确的、现在就该建的基础设施缺口：模型也需要 lockfile。** 记录 base 的 commit hash、每个 adapter 的 revision、composer 的精确版本、以及合并时的数值精度设置。缺任何一项，"我们能复现这个模型"就是一句空话。

---

## 七、把这件事放回 2026 年的坐标系

Granite Switch 4.1.1 单独看，是一次克制的 patch release：一个 adapter 换权重，语音加六种语言。放在今年的技术脉络里看，它是三条趋势的交点。

**第一条：模型的能力正在从"更大"转向"更专"。** 过去两年的主线是 scaling，今年开始，越来越多的发布在讲"用更小的模型 + 更专的组件在特定任务上打赢大模型"。Granite Switch 的 3B 版本在 Doom 上跑到 60–100 决策/秒，Jev 的 27B 是 10 次/秒——这不是参数量的胜利，是**架构的胜利**。

**第二条：推理成本的压力正在重塑模型形态。** 当一个模型要同时扮演聊天、决策、审核、转写四个角色时，"四个模型"的方案在显存和延迟上都不成立。把能力塞进一个 checkpoint、共享一份 KV cache，是被账单逼出来的架构创新，不是研究品味。

**第三条：模型正在获得软件工程的形式。** 版本号、tag、pin、compose、独立发版的组件、第三方生态、SDK。这些不是营销词汇，是一套已经被验证过三十年的工程实践，现在被搬到模型上。搬过来的好处是显而易见的——可回滚、可增量、可组合。搬过来的代价也是显而易见的——**所有软件供应链的病，模型都会得一遍，而且症状更隐蔽。**

### 给不同角色的三条具体建议

**如果你是应用开发者：**
不要再把"换模型"当成一次性的项目。把它当成一次**依赖升级**来设计：pin 版本、准备回放集、监控输出分布而不只是错误率。如果做不到这三点，你就不具备升级模型的资格——不是因为技术不够，是因为你没有能力判断升级是否成功。

**如果你是基础设施工程师：**
Granite Switch 的 SWITCH kernel 值得读，但更值得抄的是它的思路：**当负载形态变了，优化 serving 引擎的通用路径往往不如重写一条专用路径。** 三次 launch 变两次、按各自 rank 展开而不是 padding 到 max——这两条优化没有任何"AI"成分，纯粹是把负载特征吃透了。你手上的推理服务里，大概率也有同样性质的浪费。

**如果你在做 Agent 产品：**
`decision` 这类"一次前向 + logits 读出"的接口，比"让模型输出 JSON"可靠得多，也快得多。Arts 25.9 / Knowledge 34.8 的分数说明它不该被用来做开放域判断，但 Tools 69.0 说明它在"选哪个工具、走哪条分支"上已经可用。**把决策从生成里拆出来，是今年最实用的一条 Agent 工程实践**——它同时降低了延迟、提高了可测性、并且让"这个判断对不对"变成一个可以用分类指标衡量的工程问题，而不是一个靠人读输出感觉的玄学问题。

### 最后一个观察

这次发布里最不起眼的一句话，可能是最重要的：

> The version number means what it means in software.

模型圈用版本号用了很久，但语义一直是乱的。`gpt-4-0613` 里的日期是快照，`claude-3-5-sonnet-20241022` 也是快照，`llama-3.1-70b-instruct` 里的 3.1 是训练批次。**没有一个是"兼容性承诺"。**

IBM 这次试图给它一个真正的语义：patch = 基座不动、接口不动、可以无脑升。这个承诺成立与否，要看他们下一次 minor 版本怎么做——如果 4.2 换了基座，"向后兼容"就立刻失效，因为基座一换，KV cache 复用链条断裂，所有 adapter 都得重训。**换句话说，semver 在模型上最多只能做到 patch 级有效，minor 级就是一次重新洗牌。**

这不是批评，这是这个领域目前的技术上限。但承认这个上限，比假装模型已经变成普通软件要诚实得多。

而对使用者来说，结论反而简单：**能用 patch 升级的，放心升，但记得 pin；涉及 minor 升级的，当成迁移项目做，不要当成升级做。** 这两句话的分界线，就是 Granite Switch 4.1.1 教给我们的全部东西。

---

## 参考

- Granite Switch 4.1.1 发布博客：*Update models like you update software* — huggingface.co/blog/ibm-granite/granite-switch-4-1-1
- Granite Switch 4.1 发布博客：*Chat, Decisions, and Speech from One Endpoint* — huggingface.co/blog/ibm-granite/granite-switch-4-1
- 模型卡 `ibm-granite/granite-switch-4.1-30b`（revision 4.1.1，Apache 2.0，2026-10-27）
- SWITCH kernels 技术说明 — github.com/generative-computing/granite-switch/blob/main/docs/SWITCH_KERNELS.md
- IBM Research：*A new kind of adapter helps LLMs get their words out faster*（aLoRA 原理与 20–30× / 5× 数据）
- granite-switch 仓库与 adapter function catalog — github.com/generative-computing/granite-switch
- Jev Decision Index v0.3（decision adapter 评测口径）
