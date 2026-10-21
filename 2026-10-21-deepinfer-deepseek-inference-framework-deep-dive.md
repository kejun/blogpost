# 当推理框架自己开源：DeepInfer 深度拆解——5 天 1.2 万星、DSpark 投机解码与 DeepSeek 的生产级 Serving 栈

> 2026 年 10 月 20 日，DeepSeek 在 GitHub 上开源了 DeepInfer。24 小时内 Hacker News 2097 分、818 条评论冲上首页第一；5 天内 12,098 star、1,089 fork。但真正值得讨论的不是热度，而是一个反常识的事实：**这家公司把自己线上服务的推理引擎开源了，却故意不给你完整的一套服务。**

这不是又一个"vLLM 套壳"。这是一份关于"一家模型公司认为推理的哪一部分是护城河、哪一部分不是"的公开声明。读懂它，比读懂任何一个 benchmark 数字都更有价值。

---

## 一、先把事实摆清楚：DeepInfer 到底是什么

先把仓库的硬指标列出来，避免后面讨论悬空：

| 项目 | 数值 |
| :--- | :--- |
| 仓库 | `deepseek-ai/DeepInfer` |
| 创建时间 | 2026-10-16 |
| Star / Fork | 12,098 / 1,089（截至 2026-10-21） |
| Open Issues | 118（仓库关闭了 Issues 之外的讨论区） |
| 语言 / 协议 | Python / Apache 2.0 |
| 支持模型 | 仅 `DeepSeek-V4.1-Flash`（默认 checkpoint `DeepSeek-V4.1-Flash-1017`） |
| 支持硬件 | NVIDIA SM100（Blackwell 级）、华为昇腾 950 |
| 构建依赖 | GCC ≥ 13、Python 3.12、CUDA 13 / CANN 9.2 |

它的自我定位非常克制，原文是："DeepInfer is the high-performance inference framework that powers DeepSeek's large-scale production services. This open-source release provides **offline inference** with the core features needed for serving at scale."

注意两个词：**offline inference**（离线推理）和 **核心特性**。这不是一个可以直接 `docker run` 就变成 API 服务的产品，而是一个"引擎内核 + 离线批处理入口"的发布。

功能清单如下，我按重要性重排过：

1. **优化 kernel 全家桶**：FlashMLA、DeepGEMM、DeepEP、TileKernels、DeepSelect，以及自研 TileLang kernel；
2. **并行策略**：Attention DP / balanced CP（context parallel）、MoE EP + EPLB（Expert Parallel Load Balancing）；
3. **DSpark + confidence-scheduled verification**：带置信度调度的投机解码；
4. **SWA bounded replay**：滑动窗口注意力的有界重放，把 decoder prefill 只算一个有界后缀；
5. **异步调度**：CPU 批次调度与设备执行重叠，号称 zero-overhead batch scheduler；
6. **Batch-invariant inference**：不同 batch 组成下结果完全一致；
7. **Deterministic sampling**：相同输入 token + 相同采样参数，输出逐 token 相同；
8. **Structured outputs**：regex / JSON Schema / EBNF 语法约束。

而它明确说"不包含"的部分，同样是重点：

> Required for a complete inference service (not included in this release):
> - A KV cache system
> - VE/Prefill/Decode disaggregation（大部分引擎功能已实现）
> - Load balancing across data-parallel replicas for both prefill and decode

也就是说：**引擎给了，缓存系统没给，PD 分离的调度面没给，跨副本负载均衡没给。**

这就是整篇文章的题眼。后面我们会反复回到这一点。

---

## 二、为什么是现在：DeepSeek 的 kernel 拼图终于拼完了

要看懂 DeepInfer 的分量，得先看它的 `vendor/` 目录。`.gitmodules` 里挂了六个子模块：

```
vendor/FlashMLA        → Attention kernel（MLA 专用）
vendor/DeepGEMM        → FP8/低精度 GEMM
vendor/DeepEP          → Expert Parallel 通信库
vendor/DeepEP-Ascend   → 昇腾版 EP 通信
vendor/DeepGEMM-Ascend → 昇腾版 GEMM
vendor/DeepSelect      → 稀疏/选择类算子
```

再加上主仓里的 `TileKernels` 和 `deepinfer/model_executor/layers/tilelang_ops`，这是一条从 2025 年初就开始铺的路：**先开源单个 kernel，再开源把它们组装起来的引擎。**

这个顺序很值得玩味。绝大多数公司开源推理栈的做法是"先给框架，kernel 留在内部"，因为 kernel 才是真正难写的部分。DeepSeek 反过来了：FlashMLA（2025 年 2 月）先放出来，DeepGEMM 单独放，DeepEP 单独放，让社区先拿去在 vLLM/SGLang 里用、先帮它踩硬件适配的坑。等这些 kernel 在真实集群里跑了足够久、bug 收敛了，再把把它们串起来的引擎放出来。

**这是一种"先开源零件、后开源总装线"的策略。** 零件阶段社区贡献的是兼容性和硬件覆盖；总装线阶段社区贡献的是上层集成和场景适配。前者风险低（一个 kernel 挂了不影响主体），后者话题性高（HN 首页 2097 分）。

更有意思的是它对血统的坦白。README 的 Acknowledgments 写着：

> DeepInfer was originally built primarily on **vLLM**, with additional inspiration from **SGLang** and **TensorRT-LLM**.

这句话信息量很大。它承认了这不是从零写的引擎，而是从 vLLM 分叉、吸收 SGLang 的调度思想、参考 TensorRT-LLM 的图优化思路，然后针对 DeepSeek 自家模型的形状做了深度重构。所以正确的问题不是"它比 vLLM 强多少"，而是"**一个模型厂商在拿到自家模型结构之后，能把通用框架改到什么程度**"。

答案在下面四节里。

---

## 三、架构总览：从"通用引擎"到"为一种模型定制"

### 3.1 并行维度的重新切分

vLLM 的默认世界是 TP（张量并行）+ PP（流水并行）+ DP（数据并行）。DeepInfer 给的组合是：

- **Attention DP**：注意力层按数据并行切分，每个 rank 持有完整权重副本但只处理一部分请求；
- **balanced CP**：Context Parallel，把长序列的 KV 沿序列维切开，关键在于 "balanced"——切分要保证各 rank 的计算量均衡，而不是简单按长度等分；
- **MoE EP + EPLB**：专家并行，配合 Expert Parallel Load Balancing 动态迁移热点专家。

这三个组合不是随便选的，它精确对应 DeepSeek-V4.1-Flash 的结构：MLA 注意力（KV 极小，见 10 月 18 日那篇关于 890 字节/token 的分析）、超稀疏 MoE（专家极多，EP 是唯一可行解）、以及长上下文场景（CP 不可避免）。

命令行直接暴露了这些维度：

```bash
python examples/offline_inference.py --ep 8          # 纯 EP
python examples/offline_inference.py --ep 2 --dp 8   # EP + DP
python examples/offline_inference.py --ep 2 --cp 8   # EP + CP
```

注意 `--ep 2 --cp 8` 这种配置：专家并行只开 2 路，但上下文并行开 8 路。这说明在长上下文推理里，**CP 的通信模式比 EP 更贵**，所以要尽量少开 EP、多开 CP——因为 CP 切的是序列，通信是点对点的 ring/树形，而 EP 切的是专家，通信是全交换（all-to-all），后者对网络拓扑敏感得多。

这也解释了为什么 DeepEP 要单独做一个库，甚至要单独做 `DeepEP-Ascend`：all-to-all 是 MoE 推理的命门。

### 3.2 异步调度：把 CPU 从关键路径上踢出去

"零开销批次调度"（zero-overhead batch scheduler）听起来像营销词，但它解决的是一个非常具体的问题。

典型推理引擎的一步是这样的：

```
[CPU] 组 batch → 准备 metadata → 下发 kernel → [GPU] 计算 → 同步 → 下一步
```

当 decode 阶段每步只有几十微秒的 GPU 时间时，CPU 侧组 batch、算 slot mapping、准备 attention metadata 的几百微秒就成了纯浪费——GPU 在等 CPU。

DeepInfer 的做法是异步调度：CPU 提前把第 N+1 步的 batch 准备好，GPU 还在算第 N 步。README 说"Enabled by default"，说明这不是实验特性，而是它线上一直在用的路径。默认开启这件事本身就是信号：**在生产环境里，这个优化的收益大于它带来的调试复杂度。**

代价是什么？一旦调度异步化，任何"需要知道当前 batch 精确组成"的逻辑都会变复杂。这会引出后面的 batch-invariant 问题。

### 3.3 一个被忽略的细节：benchmark 脚本里的工程洁癖

我想单独说 `examples/README.md` 里的一段话，因为它比任何架构图都能说明这个团队的工程水平：

> The decode profiler goes at the very end of the measurement flow: after the profiler exits there is still a residual slowdown of **~7-11%** (measured at bsz=1), so no measurement may be scheduled after it. Step times inside the trace include the profiler's immediate overhead (up to nearly **50% inflation at bsz=1**) and are only meant for inspecting kernel composition — **do not use them to derive SPS**.

翻译一下：他们明确告诉你，profiler 关掉之后还有 7-11% 的残留降速，所以 profiler 必须放在测量流程最后；并且 trace 里的 step time 因为 profiler 开销虚高近 50%，**不要拿它算吞吐**。

这段话的价值在于：它承认了自己的测量工具会污染测量结果。绝大多数 benchmark 博客不会写这个，因为写了显得"性能数据不干净"。DeepInfer 写了，还给了规避方法（profile 与 benchmark 共用同一批请求、测量窗口不重叠、日志在 batch 构建/预热/profile 窗口全部关闭 `DEEPINFER_LOGGING_INTERVAL_STEP=0`）。

**一个愿意告诉你"我的数字在什么条件下不可信"的项目，它的数字通常更可信。** 这是我判断基础设施项目质量的一个私人标准。

---

## 四、DSpark：投机解码的"变长"与"置信度调度"

这是我认为 DeepInfer 里最有技术含量、也最容易被误读的部分。

### 4.1 它解决的是投机解码的经济学问题

投机解码的基本盘大家都熟：用小模型（或同一模型的 MTP 头）快速生成 K 个 draft token，再用大模型一次前向并行验证，接受就白赚，拒绝就回退。收益公式大致是：

```
加速比 ≈ (1 + α·K) / (1 + c·K)
```

其中 α 是接受率，K 是 draft 长度，c 是验证相对于单 token 解码的成本系数。这个公式里藏着一个非常反直觉的结论：**K 不是越大越好**。

当 K 增大，边际接受率下降（越往后的 draft token 越容易错），但验证成本线性上升。存在一个最优 K*，而且这个 K* 随请求类型剧烈变化：

- 代码补全、格式化输出、模板化 JSON：接受率极高，K 可以给到 8 甚至更多；
- 开放式创作、多轮推理：接受率低，K=2 可能就亏了。

固定 K 的引擎（大多数实现）只能取一个折中值。DeepInfer 的 DSpark 做的是**变长 draft + 置信度调度验证**。

### 4.2 配置暴露的设计

```
DEEPINFER_ENABLE_MTP_VARLEN=1      # 开启变长 MTP draft
DEEPINFER_USE_NEXTN_DECODE=5       # 最大 draft 长度，默认 5
```

两个环境变量，两层控制：一个开关决定"是否让 draft 长度动态变化"，另一个给出上界。注意默认值 5——这是一个明显偏保守的数字，说明线上负载的接受率分布不支持更长的 draft。

"confidence-scheduled verification" 这个说法值得展开。它的含义是：**不是把所有 draft token 都送进验证，而是根据 draft 模型给出的置信度决定验证窗口。**

具体机制 README 没细说，但从工程约束能反推出大致形态：draft 模型在每个位置输出的不是单个 token，而是一个分布；取 top-1 的概率（或熵）可以作为"这个 draft 靠谱吗"的信号。当置信度低于阈值，就截断 draft 序列，只验证前半段；当置信度高，就多放几个。

这样做的好处是**把验证成本花在刀刃上**：一次验证前向的 batch 里塞的是"高置信度 draft"，接受率自然高，单位算力的产出就高。

但也有代价，而且是两个：

**第一，draft 模型必须暴露置信度。** 这意味着 MTP 头不能只输出 logits 走 argmax，而要保留概率分布并做额外计算。这部分开销在 draft 侧，虽然小，但在 decode 的微秒级世界里不可忽略。

**第二，调度决策变成了数据依赖的。** 同样一批请求，因为置信度不同，验证窗口长度不同，GPU 上的实际计算图形状就不同。这直接破坏了 batch 的规则性——而规则性正是 GPU kernel 效率的来源。

我认为这正是 DeepInfer 必须同时提供 `DEEPINFER_BATCH_INVARIANT=1` 的原因之一：**当你的优化开始让执行路径依赖输入内容时，你必须给用户一个"关掉所有这类优化、保证结果可复现"的开关。**

### 4.3 一个容易踩的坑：确定性模式下必须关掉变长

README 里这句话写得很直白：

```bash
# Deterministic sampling
DEEPINFER_BATCH_INVARIANT=1 DEEPINFER_ENABLE_MTP_VARLEN=0
```

要确定性采样，不仅要开 batch invariant，还要**关掉变长 MTP**。为什么？因为变长 draft 的截断点依赖置信度，而置信度是浮点计算结果；浮点结果在不同 batch 组成下可能有 1 ulp 的差异，1 ulp 就可能让某个 draft token 刚好跨过阈值，于是验证窗口长度变了，于是后续所有 token 的数值路径都变了。

这就是"确定性"在推理引擎里的真实含义：它不是"seed 固定"，而是**整个计算图的形状和数据流都必须与 batch 组成无关**。这是一个比大多数人想象的严格得多的约束。

---

## 五、SWA bounded replay：140 个 token 背后的算术

这是 DeepInfer 最"偏门"、但对长上下文场景收益最大的一项优化。

### 5.1 问题：滑动窗口注意力的 prefill 浪费

DeepSeek-V4.1-Flash 使用了 SWA（Sliding Window Attention）与全注意力混合的结构。在 decode 阶段，每个新 token 只需要看最近 W 个 token（W 是窗口大小），所以 KV cache 是 O(W) 而不是 O(L)。

但 prefill 阶段有个麻烦：**当你做"重放"（replay）时——比如 prefix caching 命中了一部分、需要补齐后缀，或者 PD 分离里 decode 节点要重建状态——传统做法是把整个后缀的 token 都跑一遍注意力。**

而实际上，SWA 层的输出只依赖最近 W 个 token。超出窗口的部分，对 SWA 层毫无贡献，纯属白算。

DeepInfer 的解法是 **bounded replay**：只重放一个有界的后缀。

```
DEEPINFER_YOCO_PREFILL_TRUNCATION_MODE=compact
DEEPINFER_YOCO_PREFILL_KEEP_TOKENS=140
```

`YOCO` 这个名字大概率来自 "You Only Compute Once" 之类的内部代号，`compact` 是截断模式，140 是默认保留的 token 数。

### 5.2 为什么是 140，以及那句关键的约束

README 给了一句非常硬的约束：

> the retained suffix must cover the SWA window plus the maximum backtracking length.

翻译：**保留的后缀必须覆盖 SWA 窗口 + 最大回溯长度。**

这句话是整个优化的正确性证明。拆开看：

- **SWA 窗口**：SWA 层需要看最近 W 个 token，少于 W 就错了；
- **最大回溯长度**：这是投机解码带来的额外需求。当 draft token 被拒绝时，需要回退若干步重新计算；回退意味着要"倒带"，而倒带需要历史 KV 还在。

所以 140 = W + max_backtrack（大致）。这解释了为什么这个数字不能随便调小：调小一点可能 benchmark 分数不变（因为大多数样本没触发回溯），但在长尾请求上会静默产生错误输出。

**这是我最欣赏这个项目的一点：它把"正确性边界"写在了配置项的说明里，而不是留给你去踩。**

### 5.3 与 10 月 18 日那篇的呼应

三天前我们分析过 DeepSeek-V4.1-Flash-1017 的 KV 压缩：890 字节/token，prefill 计算量减半。当时得出的结论是"数据工程 > 算法创新"。

现在把两块拼起来看，逻辑就完整了：

| 层次 | 手段 | 收益 |
| :--- | :--- | :--- |
| 模型层 | KV 压缩到 890 B/token | 显存占用、带宽压力 |
| 引擎层 | SWA bounded replay，只留 140 token | prefill 计算量 |
| 引擎层 | DSpark 变长投机 | decode 每 token 成本 |
| 硬件层 | SM100 / 昇腾 950 + 定制 kernel | 算力利用率 |

**这不是四个独立的优化，而是一条从模型结构一路贯到 kernel 的优化链。** 只有同时拥有模型和引擎的团队才能做这条链——vLLM 拿不到 V4.1-Flash 的训练细节，不知道 SWA 窗口和回溯长度的精确关系；模型团队不写引擎，就只能把这些约束写成论文里的建议。

这大概是 DeepInfer 存在的最强理由：**通用引擎的天花板，是模型结构的未知。**

---

## 六、Batch-invariant 与确定性采样：为 RL 和 Agent 补的那块地基

如果说 DSpark 和 SWA replay 是"跑得更快"，那 batch-invariant 就是"跑得更可信"。后者在商业上可能更重要。

### 6.1 一个真实存在的幽灵：同一个 prompt，两次回答不一样

任何做过 LLM 服务的人都遇到过这个 bug 报告："同样的输入，为什么这次输出和上次不同？"

标准答案是"temperature > 0 所以是随机的"。但把 temperature 设成 0 之后，仍然会不一样。原因不是采样，是**浮点归约顺序**。

一次矩阵乘法的结果，在数学上是确定的；在 GPU 上是"一堆浮点加法以某种顺序累加"。而浮点加法不满足结合律：

```
(a + b) + c ≠ a + (b + c)     # 在 float16/bfloat16 下经常成立
```

batch size 变了，tile 的形状就变了，split-K 的切分点就变了，累加顺序就变了，最后一位有效数字就变了。然后：

1. logits 差 1e-3；
2. softmax 后 top-1 和 top-2 的概率差 1e-4；
3. 如果这两个 token 概率接近（这在长尾词表里极其常见），argmax 翻转；
4. 输出从此分叉，后面几百个 token 完全不同。

**这就是"蝴蝶效应"在推理引擎里的具象化。**

### 6.2 Batch-invariant 要付的代价

DeepInfer 的开关：

```
DEEPINFER_BATCH_INVARIANT=1     # NVIDIA only
```

它保证"不同 batch 组成下模型结果完全一致"。实现方式无非是固定归约顺序：不用 split-K 的动态切分，或者用确定性的树形归约，把 batch 维度从归约路径里彻底剥离。

代价是**性能**。固定归约顺序意味着不能根据 batch size 动态选择最优 kernel 配置，GPU 的并行度用不满。这是典型的"用 5% 的吞吐换 100% 的可复现性"。

为什么值得？两个场景：

**场景一：RL 训练。** 这是刚需。RL 的 importance sampling 要求"同一个 prompt 在 policy 更新前后用相同的推理路径评估"，否则 ratio 里混入了引擎噪声，梯度就是错的。过去两年大量论文报告"RL 训练不稳定"，其中一部分根源就在推理引擎的非确定性。DeepSeek 自己在训练 V4 系列时必然踩过这个坑，现在把解法开源了。

**场景二：Agent 与生产调试。** Agent 的一次任务可能调用几十次模型，任何一次输出分叉都会导致整条轨迹不同。没有确定性，你无法复现一个失败案例——只能看着日志说"当时它就是这么做的"。

### 6.3 一个细节：`seq_seed`

README 说确定性采样要"pass a fixed `seq_seed` to `SamplingParams`"。注意是 **seq_seed** 而不是全局 seed——**每个序列独立播种**。

这个设计很关键。如果全局播种，那么请求 A 的随机数消耗会影响请求 B（因为共享 RNG 状态），于是并发度一变结果就变。按序列播种，则每个请求的随机性完全隔离，与调度顺序无关。

**这是"确定性"从模型层贯通到调度层的证据。** 只做 kernel 层的确定性是不够的，RNG 的状态管理必须一起改。这类细节靠读文档读不出来，只能靠真在生产里被坑过。

---

## 七、Benchmark 方法论：4 卡 prefill、64 卡 decode 说明了什么

DeepInfer 的性能图只有两张帕累托图（prefill 的"非缓存输入吞吐 vs 延迟"、decode 的"输出吞吐 vs 每用户速度"），没有给具体数字。但测量配置本身透露了很多：

> Measured on **4 SM100 GPUs for prefill and 64 for decode** — each within one scale-up domain.

三个信息点：

**第一，prefill 和 decode 的硬件配比是 1:16。** 这个比例远高于一般人的直觉（很多人以为 1:2 或 1:4）。它说明在 DeepSeek 的真实负载里，decode 是绝对瓶颈——这也符合"推理成本主要是 decode"的行业共识，但 1:16 这个具体数字仍然惊人。它意味着：**如果你的业务是长输出（Agent、代码生成、推理链），你的集群规划必须按这个比例来。**

**第二，"each within one scale-up domain"。** 他们在刻意回避跨节点测量。一个 scale-up domain 指的是 NVLink 域内的机器（SM100 时代通常是单机 8 卡或机柜级）。prefill 用 4 卡，正好半个域；decode 用 64 卡，是 8 个域。

这句话的潜台词是：**跨域的 all-to-all 性能他们没打算在开源版里证明。** 而这恰恰是 MoE 大规模推理最难的部分。所以这两张图是"域内最优"，不是"集群最优"。

**第三，benchmark 脚本的 stage decoupling 设计。**

```
--prefill_batch_size 32768      # prefill chunk 大小
--non_cached_tokens 4096        # 非缓存后缀长度
--decode_num_requests 64        # decode batch
--context_length 32768
```

prefill 和 decode 被完全解耦：`N = prefill_num_requests` 由 profiling 需要的 chunk 数反推，与 decode batch K 无关，且 N 上限 512。如果 N 撞到 512 上限导致 prefill 工作量填不满稳态计划，脚本会**打印警告**并告诉你"prefill 指标没有意义"。

再强调一次这个设计态度：**它宁可告诉你"这次测量无效"，也不给你一个看起来漂亮的数字。**

还有一个数字很值得记：nextn 默认 5，全接受记账下 "the 64 requests of one decode step account for 384 tokens in total"（64 × 6 = 384，即 1 个 target token + 5 个 draft）。这意味着他们的吞吐口径是**含投机 token 的总 token 数**，而不是"有效输出 token 数"。

如果你拿 DeepInfer 的数字和别家比，一定要注意这个口径差异：**按总 token 算，投机解码天然占优；按接受 token 算才公平。** 大多数对比文章会忽略这一点。

---

## 八、最重要的部分：它故意没给你的那 20%

回到开头那个题眼。DeepInfer 明确列出三样"不包含"的东西：

1. **KV cache system**
2. **VE/Prefill/Decode disaggregation**（注：大部分引擎功能已实现）
3. **Load balancing across data-parallel replicas**

这三样东西有一个共同点：**它们都不是"单个引擎"的问题，而是"一个集群"的问题。**

| 缺失项 | 本质问题 | 需要什么 |
| :--- | :--- | :--- |
| KV cache 系统 | 跨请求、跨节点的 KV 复用与淘汰 | 分布式存储 / 分层缓存 / 前缀索引 |
| PD 分离 | prefill 与 decode 跑在不同节点池 | 调度器、传输层、状态迁移协议 |
| 跨副本负载均衡 | 请求该发到哪个 DP 副本 | 全局视角的路由、队列长度感知、SLA 感知 |

我把这三层叫**"舰队层"（fleet layer）**。DeepInfer 给的是**"发动机"**：燃烧效率极高、为特定燃料（V4.1-Flash）调校过、连火花塞都自己造。但变速箱、传动轴、方向盘没给。

### 8.1 这是失误还是策略？

我认为是极其清醒的策略。理由有三：

**第一，舰队层和云厂商/自建集群的形态强耦合。** 阿里云的对象存储、字节的 veDB、AWS 的 S3 Express，谁家的 KV cache 后端都不一样。开源一个"通用 KV cache 系统"，抽象层会厚到吃掉所有性能收益。不如不给，让用户接自己的。

**第二，舰队层才是真正的运营护城河。** 单引擎性能是可以被复制的（vLLM 社区几个月就能追上），但"如何在 1 万个 GPU 上把 64 卡 decode 池的利用率稳在 90%"是不可复制的。DeepSeek 把可复制的部分开源换取生态，把不可复制的部分留下——这是标准的开源商业逻辑。

**第三，也是最现实的：不给，就不必承诺。** 一旦开源了 KV cache 系统，就要维护它的 API 兼容性、就要处理各种存储后端的 bug 报告、就要为别人的生产事故负责。118 个 open issue 已经在提醒你维护成本有多高。

### 8.2 对使用者的真实含义

这个边界决定了一件事：**DeepInfer 不是给"我想自建一个 API 服务"的人用的，是给"我已经有服务基础设施，只想换发动机"的人用的。**

如果你属于后者，你会非常爽——因为最难写的 kernel 和调度都给你了。如果你属于前者，你会发现自己花两周搭起来的东西，性能还不如直接用 vLLM 的 `--enable-prefix-caching`。

这也是为什么 README 的 Getting Started 只有 `offline_inference.py`：**它诚实地把自己定位成一个库，而不是一个服务。**

---

## 九、双硬件后端：昇腾 950 出现在第一行

支持列表里，`Huawei Ascend 950 NPUs` 和 `NVIDIA SM100 GPUs` 并列。而且 `vendor/` 下有三个 Ascend 专用子模块：`DeepEP-Ascend`、`DeepGEMM-Ascend`，构建时用 `export DEEPINFER_ACCELERATOR=ascend`。

**一个开源项目从第一天就维护两条完整的硬件后端，这是极其昂贵的决定。**

昂贵在哪：

- 两套 kernel 要分别调优（Ascend 的 CANN 编程模型和 CUDA 差异巨大，TileLang 在这方面提供了抽象，但抽象必然漏性能）；
- 两套 PPL baseline（`tests/models/offline_decode_ppl.json` 明确按 platform/workload 分组，NVIDIA 和 Ascend 要分别测量）；
- 两套 CI（README 说 "re-measure the short and long PPL baselines on NVIDIA and Ascend separately"）。

它愿意付这个成本，说明**昇腾 950 不是"顺便支持"，而是出货量的一部分。** 考虑到 SM100 的供应约束和国内的采购现实，这个判断不难做。但把它写在开源仓库的第一屏，是一个明确的市场信号：DeepSeek 的推理栈要在国产算力上跑生产。

对国内做 AI 基础设施的团队来说，这可能是 DeepInfer 最实用的一点——**它是目前少数几个"在昇腾上跑过生产 MoE 推理、并且把适配代码开源"的框架**。过去这类适配基本都在各家内部，不外流。

---

## 十、横向定位：它到底和谁竞争

| 维度 | DeepInfer | vLLM | SGLang | TensorRT-LLM |
| :--- | :--- | :--- | :--- | :--- |
| 模型覆盖 | **仅 V4.1-Flash** | 极广 | 广 | 中（需转换） |
| 硬件 | SM100 + 昇腾 950 | NVIDIA/AMD/TPU/昇腾… | NVIDIA/AMD | 仅 NVIDIA |
| 定位 | 生产引擎内核 | 通用服务框架 | 高性能服务框架 | 极致性能闭源风 |
| 确定性 | **一等公民** | 部分支持 | 部分支持 | 有限 |
| 舰队层 | **不含** | 含（基础版） | 含（基础版） | 含（Triton 生态） |
| 上手成本 | 高（需自建服务层） | 低 | 中 | 高 |
| 适合谁 | 有基础设施的团队 | 大多数人 | 追求吞吐的团队 | 极致延迟场景 |

这张表里最关键的一行是"模型覆盖：仅 V4.1-Flash"。

这不是缺陷，是**设计前提**。DeepInfer 的所有优化都建立在"我知道这个模型的每一层长什么样"之上——SWA 窗口多大、回溯多长、专家多少个、MLA 的 head dim 多少。一旦要支持第二个模型，这些硬编码的假设就得全部参数化，而参数化就意味着放弃一部分优化。

所以 DeepInfer 永远不可能变成"通用框架"，它也不需要。**它的存在意义是给"通用框架"划一条性能上限线：看，当你放弃通用性，能快这么多。**

而对 vLLM/SGLang 来说，DeepInfer 是一份免费的、由模型原作者写的"优化清单"。我预计未来 6 个月内，SWA bounded replay 和 confidence-scheduled verification 会以某种形式出现在 SGLang 里——就像当年 FlashMLA 和 DeepEP 一样。

**这才是 DeepSeek 开源策略的真正闭环：先让社区用它的 kernel，再让社区追它的引擎，最后整个生态的推理成本都下降，而它卖 token 的成本下降得最快。**

---

## 十一、如果你要试：一条最小路径与四个风险

### 最小验证路径

```bash
# 1. 环境：Linux + GCC 13 + Python 3.12 + CUDA 13
export DEEPINFER_ACCELERATOR=nvidia
./build.sh

# 2. 跑通离线推理（EP=8，单机八卡）
python examples/offline_inference.py --ep 8

# 3. 验证数值没有漂移（这一步别跳）
python -m pytest -v -s tests/models/test_offline_inference.py

# 4. 跑 benchmark，看自己硬件的真实曲线
bash examples/sweep/run_sweep.sh
```

第 3 步是最容易被跳过、也最不该跳过的一步。`offline_decode_ppl.json` 里的 baseline 是按 platform/workload 分组的，如果你的 PPL 和 baseline 差得超过预期，说明构建环境（CUDA 版本、kernel 编译选项）有问题——**先修环境，再谈性能**。

### 四个需要提前想清楚的风险

**风险一：模型单一。** 只有 V4.1-Flash。你如果线上跑的是 Qwen、Kimi、GLM，DeepInfer 对你零价值。这不是"以后会支持"的问题，是架构前提。

**风险二：没有服务层。** 想变成 OpenAI 兼容 API，你得自己写 FastAPI + 调度 + KV 复用 + 限流。参考实现可以看 vLLM 的 `entrypoints`，但别指望能直接复用——DeepInfer 的 batch 管理是异步的，和 vLLM 的同步抽象对不上。

**风险三：`has_issues: false`。** 仓库关闭了 Issues（只有 118 个 open PR 遗留）。这意味着**没有官方的问题反馈通道**。踩到坑只能看代码、看 PR、或者去 HN/Twitter 上找人。对生产使用来说，这是一个实打实的支持风险。

**风险四：年轻。** 创建 5 天，一次 release，无版本号。API 会变，环境变量会改（现在就已经有 `DEEPINFER_YOCO_PREFILL_TRUNCATION_MODE` 这种明显是内部代号的命名）。**别把它放进关键路径，先放进离线批处理和评测流水线。**

### 对 Agent 开发者的意义

最后说一句和我们日常最相关的。

过去半年我一直在写 Agent 基础设施，一个反复出现的痛点是：**Agent 的成本结构里，decode 占了 80% 以上，而 decode 的效率取决于引擎，不取决于你的 prompt 工程。**

DeepInfer 给出的三个东西对 Agent 场景特别对症：

- **DSpark 变长投机**：Agent 的输出高度模板化（工具调用的 JSON、固定的思考前缀），接受率天然高，投机收益比开放对话大得多；
- **Structured outputs（regex/JSON Schema/EBNF）**：直接在采样层约束，不用后处理重试。EBNF 支持意味着可以约束整套工具调用语法——这比 JSON Schema 表达力强得多；
- **确定性**：Agent 的调试体验完全取决于能不能复现。这一条的价值，做过线上 Agent 排障的人都懂。

---

## 十二、结论：一份关于"什么是护城河"的公开声明

DeepInfer 不是"DeepSeek 版的 vLLM"。它是一个模型厂商对自己推理栈的一次公开切片，切面选得极其精准：

**给你发动机**（kernel + 调度 + 投机 + 确定性），**留下舰队**（KV 缓存、PD 分离、跨副本均衡）。

这个切法告诉我们三件事：

1. **单点推理性能正在商品化。** 当模型厂商愿意把生产引擎开源，说明"引擎快 20%"已经不再是竞争优势——真正的优势是"一万张卡上稳定跑出 90% 利用率"。
2. **模型与引擎的协同优化是通用框架的结构性劣势。** SWA bounded replay 的 140 这个数字，只有知道模型 SWA 窗口和最大回溯长度的人才能定。vLLM 永远只能给你一个保守的默认值。
3. **确定性正在从"nice to have"变成"必需"。** RL 训练、Agent 调试、合规审计，三个场景同时要求它。DeepInfer 把它做成一等公民，是一个明确的方向标。

对读者来说，最实际的行动建议是：**别急着部署，先读它的 `examples/README.md`。** 那份文档里对测量污染的坦白、对 baseline 分组的管理、对 profiler 残留降速的标注，比任何架构图都更能教会你"怎么正确地评估一个推理引擎"。

至于那 12,098 个 star——大部分人会 star 完就忘。真正有价值的，是记住这个切面：**当下一次有人问你"你们的推理栈护城河在哪"，正确的答案不是"我们用了什么引擎"，而是"引擎之外的那 20%，我们是怎么做的"。**

---

**参考来源**

- [deepseek-ai/DeepInfer](https://github.com/deepseek-ai/DeepInfer)（Apache 2.0，2026-10-16 创建）
- DeepInfer `README.md` / `examples/README.md` / `eval/README.md` / `.gitmodules`
- Hacker News 讨论：story 50163277（2097 points，818 comments，2026-10-20）
- [FlashMLA](https://github.com/deepseek-ai/FlashMLA)、[DeepGEMM](https://github.com/deepseek-ai/DeepGEMM)、[DeepEP](https://github.com/deepseek-ai/DeepEP)、[DeepSelect](https://github.com/deepseek-ai/DeepSelect)
- 本博客 2026-10-18《当 KV 缓存成为新瓶颈：DeepSeek-V4.1-Flash-1017 深度拆解》
