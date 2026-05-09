# DFlash：用 Block Diffusion 重写 LLM 推理加速——Speculative Decoding 的范式转移

**文档日期：** 2026 年 5 月 9 日  
**标签：** DFlash, Speculative Decoding, LLM Inference, Block Diffusion, EAGLE-3, SGLang, vLLM, GPU Utilization

---

## 一、背景：LLM 推理的"内存墙"与加速焦虑

### 1.1 自回归解码的结构性瓶颈

截至 2026 年 5 月，大语言模型的参数量已经触及万亿级别。然而，无论模型多大、多聪明，**每一次 token 生成都必须等待前一个 token 完成**——这是自回归（Autoregressive, AR）解码的本质约束。

这个约束导致了一个经典的**内存墙（Memory Wall）**问题：

```
GPU 推理的时间分配（典型场景）：

┌────────────────────────────────────────────────────┐
│  计算 (Compute)    ████████░░░░░░░░░░░░░░░░  ~15%  │
│  内存带宽 (Memory)  ████████████████████░░░░  ~85%  │
└────────────────────────────────────────────────────┘

每生成一个 token：
  1. 从 HBM 加载所有权重（数百 GB/s）
  2. 做一次矩阵乘法（计算密集度极低）
  3. 写回 KV cache
  4. 回到步骤 1 → 循环 N 次
```

在这种模式下，GPU 的算力被严重浪费——计算单元大部分时间在等待内存数据。这就是为什么即使你拥有 H100，推理吞吐仍然受限于**内存带宽而非算力**。

### 1.2 现有加速方案的天花板

社区尝试过多种方案来突破这个瓶颈：

| 方案 | 原理 | 加速比 | 局限 |
|------|------|--------|------|
| **KV Cache 优化** (PagedAttention, RadixAttention) | 减少内存碎片和重复计算 | 1.2-1.5× | 优化了内存管理，但没有改变串行本质 |
| **张量并行/流水线并行** | 分布式推理 | 取决于硬件 | 增加通信开销，不减少 token 步数 |
| **投机解码 (Speculative Decoding)** | 小模型草稿 + 大模型验证 | 2-3× | **草稿本身也是串行的** |
| **扩散 LLM 直接生成** | 并行生成所有 token | 理论很高 | 质量远低于 AR 模型 |

其中，**投机解码**是最有前途的方向，但它也有一个天花板：**草稿模型仍然是自回归的**。即便是当前最先进的 EAGLE-3，它的草稿也是逐个 token 生成的，这意味着草稿阶段的延迟仍然随猜测数量线性增长。

这就是 DFlash 要解决的问题。

---

## 二、投机解码的演进：从 Medusa 到 DFlash

### 2.1 投机解码的基本框架

投机解码的核心思想可以用一句话概括：**"让一个小模型先猜，大模型批量验证"**。

```
传统自回归解码：
  Token₁ → Token₂ → Token₃ → Token₄ → Token₅ → ...  (N 次前向传播)

投机解码：
  [草稿模型] 猜 Token₂, Token₃, Token₄, Token₅  (M 次前向传播)
  [目标模型] 一次性验证所有猜测              (1 次前向传播)
  接受 3 个 → 等效速度提升 ~4×
```

关键指标是**接受长度（Acceptance Length）**τ：平均每个验证周期被目标模型接受的草稿 token 数量。τ 越大，加速效果越显著。

### 2.2 投机解码的三代演进

**第一代：独立草稿模型（2023）**

早期方法（如 SpecDecoding、Lookahead Decoding）使用一个独立的小模型来生成草稿。问题是：小模型没有大模型的"知识"，猜测质量很差，τ 通常在 1-2 之间。

**第二代：特征增强草稿（2024-2025）**

EAGLE、EAGLE-2、EAGLE-3 系列代表了这个方向。它们的核心创新是：**从目标模型提取隐藏层特征，注入到草稿模型中**。这样草稿模型不再"盲猜"，而是基于目标模型的内部表征来预测未来 token。

EAGLE-3 达到了约 2-3× 的实际加速比，是当前的 SOTA。但它有一个根本限制：**草稿仍然是自回归的**。

**第三代：并行草稿（2026）——DFlash**

DFlash 的回答是：**为什么草稿模型一定要是串行的？** 如果我们可以用扩散模型来并行生成整个 token 块，草稿阶段的延迟就不再随 token 数量增长。

---

## 三、DFlash 的核心突破：Block Diffusion Drafting

### 3.1 为什么扩散模型能做草稿？

DFlash 论文（arXiv:2602.06036）的作者——Jian Chen、Yesheng Liang 和 Zhijian Liu——提出了一个关键洞察：

> **大型自回归 LLM 的隐藏特征中，隐式地包含了多个未来 token 的信息。**

这个现象在 Samragh et al. (2025) 的工作中也被观察到。简单来说：当目标模型处理完当前上下文后，它的内部表征已经"知道"接下来大概率会出现什么——只是它被训练成一次只吐出一个 token。

DFlash 的思路是：**既然大模型已经知道了，为什么不把这些知识提取出来，喂给一个擅长并行生成的模型？**

### 3.2 Block Diffusion 的工作机制

DFlash 使用一个**轻量级的 block diffusion 模型**作为草稿模型。整个流程分三步：

#### Step 1: 特征融合（Feature Fusion）

在目标模型完成 prefill 或 verification 后，从目标模型的多个层（均匀采样）提取隐藏特征，通过一个轻量投影进行融合：

```
目标模型:  Layer 0 ──→ Layer 8 ──→ Layer 16 ──→ Layer 24
              ↓           ↓            ↓           ↓
          [提取隐藏特征] ─→ [融合投影] ─→ [融合上下文向量]
```

#### Step 2: KV 注入（KV Injection）—— 这是 DFlash 区别于 EAGLE-3 的关键

这是 DFlash 最精妙的设计：

```
EAGLE-3 的做法：
  目标特征 → 仅作为草稿模型第一层的输入
  问题：信号随层数增加而稀释 → 草稿模型不能太深

DFlash 的做法：
  目标特征 → 注入到草稿模型每一层的 KV Cache
  效果：每层都获得完整的上下文信息 → 接受长度随深度增加
```

这个区别至关重要。在 EAGLE-3 中，目标模型的信号只在草稿模型的第一层出现，随着数据流过后续层，信号逐渐被稀释。这迫使 EAGLE-3 只能使用极浅的架构（单层 Transformer），严重限制了草稿质量。

而 DFlash 将融合后的特征直接注入到草稿模型**每一层**的 Key/Value 投影中，并存储在 KV Cache 里。这意味着：

- **每一层都获得完整的目标模型上下文**
- **草稿模型可以更深、更有表达力**
- **接受长度 τ 随草稿模型深度增加而提升**

#### Step 3: 并行草稿生成（Parallel Drafting）

条件化后的扩散模型在**单次前向传播**中预测整个 token 块（通常 block_size=16）：

```
扩散草稿：
  [噪声] + [目标上下文] + [上一个已验证 token]
    ↓ (单次前向传播)
  [Token₂, Token₃, ..., Token₁₇]  ← 16 个 token 同时生成

目标验证：
  一次性验证所有 16 个 token，接受前 k 个
```

### 3.3 架构精简：只训练中间层

DFlash 的草稿模型**复用了目标模型的 embedding 层和 LM head**，只训练少量的中间层（通常 5-10 层）。这意味着：

- 草稿模型的参数量极小（仅目标模型的几分之一）
- 训练成本可控
- 推理时额外的内存开销几乎可以忽略

---

## 四、性能基准：6× 无损加速意味着什么

### 4.1 与 EAGLE-3 的直接对比

论文在 Qwen3-8B 上对比了 DFlash 和 EAGLE-3 在多个基准上的表现（greedy decoding, temperature=0）：

| 基准 | Baseline | + EAGLE-3 | + DFlash | DFlash vs EAGLE-3 |
|------|----------|-----------|----------|-------------------|
| **GSM8K** | 1× | 2.13× | **5.20×** | 2.44× |
| **MATH-500** | 1× | 2.18× | **6.17×** | 2.83× |
| **AIME24** | 1× | 2.25× | **5.91×** | 2.63× |
| **AIME25** | 1× | 2.18× | **5.85×** | 2.68× |
| **HumanEval** | 1× | 2.48× | **5.20×** | 2.10× |
| **MBPP** | 1× | 2.27× | **4.75×** | 2.09× |
| **SWE-bench** | 1× | 1.90× | **2.92×** | 1.54× |
| **MT-Bench** | 1× | 1.94× | **2.79×** | 1.44× |
| **Alpaca** | 1× | 1.88× | **2.27×** | 1.21× |

**核心发现：**

1. **数学和代码基准上，DFlash 的加速比是 EAGLE-3 的 2.5 倍以上。** 这些任务的 token 序列具有更高的可预测性，block diffusion 的优势被最大化。

2. **对话和开放生成任务上，加速比仍然可观（1.2-1.5×）。** 这表明 DFlash 在低可预测性场景下也不会退化。

3. **所有加速都是"无损"的。** 因为最终输出由目标模型验证，生成质量与纯自回归解码完全一致。

### 4.2 采样模式和 Thinking 模式下的表现

DFlash 不仅在 greedy decoding 下表现优秀，在采样模式（temperature=1）下同样强劲：

| 基准 | DFlash Speedup (temp=1) |
|------|------------------------|
| GSM8K | 2.76× |
| MATH-500 | 3.31× |
| AIME24 | 2.66× |
| AIME25 | 2.65× |

对于启用了 thinking mode 的推理模型（如 Qwen3 的 thinking 模式），DFlash 实现了约 **4.5× 的加速**——这是因为 thinking 过程生成了大量中间推理 token，这些 token 的模式相对可预测，非常适合 block diffusion 草稿。

### 4.3 跨模型的泛化能力

DFlash 不是针对某个特定模型优化的，它已经适配了众多主流模型：

| 目标模型 | DFlash 草稿模型 | 加速比（典型值） |
|----------|----------------|-----------------|
| Qwen3-4B | Qwen3-4B-DFlash-b16 | ~5× |
| Qwen3-8B | Qwen3-8B-DFlash-b16 | ~6× |
| Qwen3.5-27B | Qwen3.5-27B-DFlash | ~5× |
| Qwen3.5-35B-A3B | Qwen3.5-35B-A3B-DFlash | ~4.5× |
| Gemma-4-26B-A4B-it | Gemma-4-26B-A4B-it-DFlash | ~5× |
| Qwen3-Coder-30B-A3B | Qwen3-Coder-30B-A3B-DFlash | ~4× |
| LLaMA-3.1-8B-Instruct | LLaMA3.1-8B-Instruct-DFlash | ~4.5× |

更令人印象深刻的是，DFlash 已经覆盖了 MiniMax-M2.5、Kimi-K2.5、gpt-oss-20b/120b 等模型，并且 DeepSeek-V4、GLM-5.1 等模型的适配也在路上。

---

## 五、技术深度分析：为什么 DFlash 能赢？

### 5.1 扩散草稿 vs 自回归草稿的复杂度分析

让我们从计算复杂度的角度来理解为什么扩散草稿具有结构性优势：

```
自回归草稿（EAGLE-3）：
  生成 γ 个 token 的延迟 = γ × T_AR
  其中 T_AR 是单次前向传播的时间
  即使草稿模型只有一层，延迟也随 γ 线性增长

扩散草稿（DFlash）：
  生成 γ 个 token 的延迟 = T_diff (常数)
  T_diff 与 γ 基本无关（单次前向传播）
  代价：需要足够大的 block_size 来覆盖 γ
```

这意味着：**对于相同的草稿 token 数量，扩散草稿的延迟是固定的，而自回归草稿的延迟线性增长。** 这就是为什么一个 10 层的 DFlash 草稿模型在生成 16 个 token 时，延迟反而比 1 层的 EAGLE-3 生成 8 个 token 还要低。

### 5.2 朴素扩散草稿为什么失败？

论文做了一个关键消融实验：**不使用目标模型特征的朴素 block diffusion 草稿**。

结果很惨淡：

| 指标 | 朴素扩散草稿 | DFlash（有目标特征） |
|------|-------------|---------------------|
| GSM8K 接受长度 | 3.38 | ~8 |
| GSM8K 加速比 | 2.83× | 5.20× |
| AIME24 加速比 | 3.43× | 5.91× |

这验证了一个核心论点：**不是扩散模型不行，而是没有目标模型知识的扩散模型不行。** 扩散模型的并行能力是基础设施，目标模型的特征注入才是灵魂。

### 5.3 与 DiffuSpec / SpecDiff-2 的对比

其他使用扩散模型做投机解码的工作（如 DiffuSpec、SpecDiff-2）也有类似想法，但它们使用 7B 参数的大型扩散模型作为草稿模型——这对于生产部署来说完全不切实际。

DFlash 的关键贡献是证明了：**轻量化的扩散草稿（仅复用 embedding + LM head + 少量中间层）在目标特征注入的条件下，可以达到甚至超越大型独立扩散草稿的质量。**

---

## 六、生产部署：DFlash 的工程实践

### 6.1 SGLang 集成

DFlash 已经深度集成到 SGLang 中，生产部署非常简单：

```bash
python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-35B-A3B \
  --speculative-algorithm DFLASH \
  --speculative-draft-model-path z-lab/Qwen3.5-35B-A3B-DFlash \
  --speculative-num-draft-tokens 16 \
  --tp-size 1 \
  --attention-backend trtllm_mha \
  --mem-fraction-static 0.75 \
  --trust-remote-code
```

### 6.2 vLLM 集成

vLLM v0.20.1+ 也包含了 DFlash 核心支持：

```bash
vllm serve Qwen/Qwen3.5-27B \
  --speculative-config '{"method":"dflash","model":"z-lab/Qwen3.5-27B-DFlash","num_speculative_tokens":15}' \
  --attention-backend flash_attn \
  --max-num-batched-tokens 32768
```

对于 Gemma-4 模型，目前需要使用 z-lab 维护的临时 vLLM 构建（或通过 Docker 镜像）。

### 6.3 Apple Silicon 支持

DFlash 还提供了 MLX 后端，在 Apple M5 Pro 上测试了 Qwen3、Qwen3.5 和 Gemma-4 模型的推理加速。这使得开发者可以在本地机器上体验 speculative decoding 的加速效果。

### 6.4 部署注意事项

| 考虑因素 | 建议 |
|----------|------|
| **Block Size** | 默认 16，可根据任务类型调整。数学/代码任务可用更大 block_size |
| **Attention Backend** | Flash Attention 3 推荐，Triton 作为备选 |
| **内存预算** | 草稿模型额外开销很小（< 5%），主要消耗仍在目标模型 |
| **Thinking 模式** | DFlash 对 thinking 模式有显著加速（~4.5×），建议启用 |
| **采样策略** | temperature=0 时加速最佳，但 temperature=1 时仍然有效 |

---

## 七、DFlash 的深远意义：重新定义扩散 LLM 的角色

### 7.1 从"竞争者"到"协作者"

过去几年，扩散 LLM（Diffusion LLM, dLLM）一直被放在一个尴尬的位置：**人们试图训练扩散模型来直接替代自回归 LLM，但质量始终差距明显。**

DFlash 提出了一个完全不同的思路：

> **扩散模型不需要在生成质量上与自回归模型竞争。它只需要成为一个优秀的草稿者。**

这是一个范式转移：

```
旧范式：
  扩散 LLM vs 自回归 LLM → 扩散 LLM 质量不足 → 失败

新范式（DFlash）：
  扩散 LLM（草稿） + 自回归 LLM（验证） → 并行草稿 + 无损验证 → 双赢
```

### 7.2 对 LLM 推理生态的影响

DFlash 的成功将影响多个层面：

**1. 推理服务提供商**

对于云服务商（如 Together AI、DeepInfra、Fireworks），DFlash 意味着在不损失质量的前提下，**单卡吞吐提升 4-6 倍**。这直接转化为更低的成本和更高的利润。

**2. 本地部署场景**

对于需要在本地部署 LLM 的企业，DFlash 的加速效果意味着：**用更少的 GPU 完成相同的推理负载**，或者**用现有的 GPU 服务更多用户**。

**3. Agent 系统**

AI Agent 通常需要多次调用 LLM（规划、工具调用、反思），每次调用的延迟累积起来非常可观。DFlash 的加速可以显著降低 Agent 的端到端延迟，使实时 Agent 交互成为可能。

**4. 未来研究方向**

DFlash 打开了一扇门：

- **Draft 模型架构的专门优化**：既然草稿模型不需要独立生成高质量文本，它的架构可以针对"快速平行预测"进行专门设计
- **自适应 block size**：根据上下文的可预测性动态调整草稿 block 大小
- **多草稿策略**：同时使用多个草稿模型，选择最佳猜测
- **与 dLLM 加速技术的结合**：DFlash 兼容进一步的扩散 LLM 加速技术

---

## 八、局限性与开放问题

### 8.1 当前局限

| 局限性 | 说明 |
|--------|------|
| **训练成本** | 虽然草稿模型小，但每个目标模型都需要训练一个专用草稿模型 |
| **Block Size 固定** | 当前 block_size 是超参数，不能自适应调整 |
| **MoE 模型支持** | 对 MoE 架构的适配仍在进行中（DeepSeek-V4、MiniMax-M2.7 等标记为 "Coming soon"） |
| **超长上下文** | block diffusion 在超长上下文下的表现需要更多验证 |

### 8.2 开放问题

1. **Draft 模型的最优架构是什么？** 当前 DFlash 复用了目标模型的部分层，但可能存在更优的草稿专用架构。

2. **能否跨模型共享草稿？** 训练一个通用的草稿模型，服务于多个目标模型？

3. **与 Speculative Sampling 的结合？** 除了验证式投机解码，能否与基于采样的投机策略结合？

4. **在 Agent 工作流中的端到端收益？** 现有基准主要测试单轮生成，Agent 的多轮交互场景下收益如何？

---

## 九、总结

DFlash 代表了一个重要的技术突破：**它将 block diffusion 的并行生成能力与 speculative decoding 的无损验证机制完美结合，实现了超过 6× 的无损加速。**

核心贡献可以概括为三点：

1. **目标特征 KV 注入**：让草稿模型的每一层都获得完整的目标模型上下文，打破了 EAGLE-3 的信号稀释瓶颈。

2. **扩散草稿的结构性优势**：草稿延迟与 token 数量解耦，使得更深的草稿模型反而比更浅的自回归草稿更快。

3. **轻量化的工程实现**：仅训练少量中间层，复用目标模型的 embedding 和 LM head，部署成本极低。

DFlash 已经获得 GitHub 3,800+ stars，并被 SGLang 和 vLLM 两大推理框架集成。对于任何关注 LLM 推理性能的人来说，这是一个值得深入了解和部署的技术。

> **关键引用：** Chen, J., Liang, Y., & Liu, Z. (2026). DFlash: Block Diffusion for Flash Speculative Decoding. arXiv:2602.06036.

---

*本文基于 DFlash 论文（arXiv:2602.06036）、GitHub 仓库（z-lab/dflash）及官方博客（z-lab.ai/projects/dflash）编写。基准数据来源于论文原文。*
