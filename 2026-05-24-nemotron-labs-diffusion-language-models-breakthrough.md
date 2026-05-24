# Diffusion Language Models 的崛起：NVIDIA Nemotron-Labs Diffusion 如何让文本生成突破自回归瓶颈

> 2026 年 5 月 23 日，NVIDIA 发布了 Nemotron-Labs Diffusion 系列模型。这不是"又一个开源 LLM"——这是自回归语言模型统治十年后，第一次有人把 Diffusion Language Model（DLM）做到了**不仅可用，而且在某些指标上超越了同规模 AR 模型**。8B 模型在 SGLang 上达到 ~865 tok/s（B200），是自回归基线的 4 倍；Tokens Per Forward Pass 达到 AR 的 6.4 倍。

**这是一个信号：文本生成的"并行化时代"，正式来了。**

---

## 一、自回归的"铁律"与它的裂缝

### 1.1 十年不变的范式

从 2017 年 Transformer 论文问世至今，几乎所有主流 LLM 的文本生成都遵循同一个模式：

```
P(x_t | x_1, x_2, ..., x_{t-1}) → 每次生成一个 token
```

这个模式被称为**自回归（Autoregressive, AR）生成**。它简单、稳定、易于推理，但也带来了一个无法回避的物理约束：

**每个新 token 都需要一次完整的模型前向传播，并且所有权重必须先从显存加载到计算单元。**

对于现代 GPU 来说，这意味着大部分时间花在 HBM 内存搬运上，而不是矩阵乘法计算上。当 batch size 较小时（比如单用户推理场景），GPU 的计算单元大量闲置，整个系统处于 memory-bound 状态。

### 1.2 自回归的三个结构性缺陷

| 缺陷 | 描述 | 影响 |
|------|------|------|
| **串行瓶颈** | token-by-token 生成，无法并行 | 延迟下限被锁死 |
| **不可修订** | 一旦生成就是最终结果，无法回溯修改 | 错误会级联传播 |
| **内存瓶颈** | 每个 token 都要加载全部权重 | 小 batch size 下 GPU 利用率极低 |

这些问题不是"工程优化"能解决的——它们是架构层面的约束。

### 1.3 为什么 Diffusion 语言模型一直被看好却从未真正落地？

Diffusion Model 在图像生成领域已经大获成功（DALL·E、Stable Diffusion、Midjourney），但在文本生成领域，它一直面临几个核心障碍：

1. **离散空间问题**：文本是离散的 token 序列，而 Diffusion 本质上是连续空间的加噪-去噪过程
2. **准确性差距**：早期 DLM 在 MMLU、HumanEval 等基准上显著弱于同规模 AR 模型
3. **KV Cache 不兼容**：传统 Diffusion 的注意力机制与 AR 的 KV Cache 策略不兼容，推理效率难以优化
4. **训练复杂度高**：需要从零训练，无法复用已有的 AR 预训练成果

直到 2025 年底的 [Efficient-DLM](https://arxiv.org/abs/2512.14067) 论文出现——它证明了：**预训练的 AR 模型可以通过继续预训练 + 注意力机制改造，转换为支持块级并行解码的 Diffusion 语言模型。**

这条路线保留 AR 模型的全部能力，同时赋予并行生成能力。Nemotron-Labs Diffusion 正是这条路线的第一个**生产级实现**。

---

## 二、Nemotron-Labs Diffusion 到底做了什么？

### 2.1 核心理念：不是替代，而是融合

Nemotron-Labs Diffusion 的设计哲学很清晰：

> **自回归和 Diffusion 不应该是两个独立的模型家族，而应该是同一个模型的两种能力。**

这意味着同一个 checkpoint 可以以三种模式运行：

| 模式 | 机制 | 适用场景 |
|------|------|----------|
| **AR 模式** | 标准左到右生成 | 基线验证、兼容性场景 |
| **Diffusion 模式** | 按 32-token 块逐步生成，通过迭代去噪 | 极致吞吐量、延迟敏感场景 |
| **Self-Speculation 模式** | Diffusion 草稿 + AR 验证 | 兼顾速度与质量的生产场景 |

这种设计的精妙之处在于：**开发者不需要修改应用代码**，只需要在部署配置中切换模式。同一个模型，三种推理策略，按需选择。

### 2.2 三种模式的深度技术剖析

#### 模式一：Autoregressive（基线模式）

设置 `ar_mode=true`，模型行为等同于标准因果语言模型。这主要用于：
- 与现有 AR 模型做公平对比
- 验证 Diffusion 模式输出质量的 sanity check
- 在需要最高确定性的场景中作为 fallback

#### 模式二：Diffusion（FastDiffuser）

这是主打极致吞吐量的模式。工作原理：

```
Step 1: 初始化 32-token 块为纯噪声
Step 2: 迭代去噪，逐步确定每个位置的 token
Step 3: 置信度阈值判断——"足够好"的 token 被提交
Step 4: 重复 Step 2-3，直到块内所有 token 确定
```

关键指标：
- **每步生成 32 个 token**（vs AR 的每步 1 个）
- **Tokens Per Forward Pass (TPF) = 2.6× AR 基线**

但 Diffusion 模式有一个 trade-off：因为每次生成是"猜测+精炼"而非严格左到右的概率采样，**在需要精确控制的场景下可能出现质量波动**。

#### 模式三：Self-Speculation（真正的杀手级特性）

这是最值得深入分析的模式，也是我认为最具产业影响力的创新。

工作原理：

```
Step 1: Diffusion 双向草稿（bidirectional drafting）——一次性预测接下来 N 个 token
Step 2: AR 因果验证（causal verification）——从左到右逐个检查草稿是否正确
Step 3: 找到第一个不匹配的位置
Step 4: 提交匹配的前缀，从不匹配位置重新开始
```

这个过程本质上是一个 **speculative decoding** 的变体，但与传统 speculative decoding（需要一个小模型做草稿）不同，Self-Speculation **用同一个模型既做草稿又做验证**。

**关键结果**：
- 在 temperature=0 时，**输出与 AR 模式完全一致（无损）**
- 在 B200 上达到 **~865 tok/s**，约 **4× AR 基线速度**
- LinearSpec: TPF = 6× AR
- QuadraticSpec: TPF = 6.4× AR

**为什么这个设计如此重要？**

因为它解决了一个业界长期的痛点：**Speculative Decoding 需要维护两个模型（大模型 + 小模型），部署复杂度高。** Self-Speculation 用一个模型搞定一切，大幅降低了生产部署的门槛。

---

## 三、性能数据：不只是快，而且准

### 3.1 准确性对比

Nemotron-Labs Diffusion 8B vs Qwen3 8B（同规模基线）：

| 指标 | 结果 |
|------|------|
| 平均准确率 | **+1.2% 优于 Qwen3 8B** |
| Self-Speculation 模式准确率 | 与 AR 模式相当 |
| Diffusion 模式准确率 | 略低于 AR，但在多数任务上差距在噪声范围内 |

这个数字值得停下来想一想。DLM 一直被诟病"比 AR 差"。但 Nemotron-Labs Diffusion 8B 不仅追平了 AR 模型，还在某些基准上**超越了**它。这背后的原因可能是：

1. **联合训练目标**：同时使用 AR 和 Diffusion objective 训练，模型同时学习两种生成策略
2. **修订能力**：Diffusion 的"生成-精炼"过程本质上是在做隐式的 self-correction
3. **1.3T token 预训练 + 45B token SFT**：NVIDIA 的 Nemotron 数据集质量提供了坚实基础

### 3.2 吞吐量与延迟

| 模式 | Tokens/s (B200) | TPF 倍率 | 质量 |
|------|----------------|----------|------|
| AR 基线 | ~215 | 1.0× | 最高 |
| Diffusion | ~560 | 2.6× | 略低 |
| LinearSpec | ~865 | 6.0× | 无损 (temp=0) |
| QuadraticSpec | ~910 | 6.4× | 无损 (temp=0) |

**注意**：这些数字是 SpeedBench 数据集上的测量值，代表综合负载下的表现。

### 3.3 与 DFlash 的对比与演进

我们在 2026 年 5 月 9 日的文章《[DFlash：用 Block Diffusion 重写 LLM 推理加速](https://github.com/kejun/blogpost/blob/main/2026-05-09-dflash-speculative-decoding-block-diffusion.md)》中讨论过 Block Diffusion 在 speculative decoding 中的应用。Nemotron-Labs Diffusion 可以看作是那个方向的**完整产品化**：

| 维度 | DFlash (学术探索) | Nemotron-Labs Diffusion (产品) |
|------|-------------------|-------------------------------|
| 模型来源 | 需要专门训练 | AR 预训练模型 + 继续训练 |
| 推理引擎 | 实验性实现 | SGLang 集成（即将合入主分支） |
| 部署灵活性 | 单一模式 | 三种模式可切换 |
| 模型规模 | 实验规模 | 3B/8B/14B + 8B VLM |
| 开源协议 | 学术论文 | NVIDIA Nemotron Open Model License（商业友好） |

这条技术路线的演进速度令人惊讶：从 Efficient-DLM 论文（2025 年底）到生产级开源模型（2026 年 5 月），不到 6 个月。

---

## 四、训练方法论：为什么它成功了？

### 4.1 联合训练目标

Nemotron-Labs Diffusion 的核心训练策略是 **Joint AR + Diffusion Objective**：

```
Loss = α × Loss_AR + β × Loss_Diffusion
```

这确保模型在获得 Diffusion 能力的同时，不丢失已有的 AR 生成能力。相比之下，早期 DLM 研究往往只训练 Diffusion objective，导致 AR 能力退化。

### 4.2 数据规模

| 阶段 | Token 数 | 数据集 |
|------|----------|--------|
| 预训练 | 1.3T | NVIDIA Nemotron Pretraining Datasets |
| SFT | 45B | NVIDIA Nemotron Post-training Datasets v3 |

1.3T token 的预训练规模与 Qwen3 8B 等主流模型相当，说明 NVIDIA 在数据质量而非单纯数据量上做了投入。

### 4.3 从 Megatron Bridge 到 SGLang

训练代码通过 [NVIDIA Megatron Bridge](https://github.com/NVIDIA-NeMo/Megatron-Bridge/) 框架开源，推理支持正在合入 [SGLang](https://github.com/sgl-project/sglang/pull/25803) 主分支。

这个技术栈选择很有讲究：Megatron 是大规模分布式训练的事实标准，SGLang 是当前最快的开源推理引擎之一。**训练和推理都选择了最主流的工具链，降低了社区接入门槛。**

---

## 五、实际应用：什么场景最适合 Diffusion LLM？

### 5.1 最匹配的场景

| 场景 | 为什么适合 | 推荐模式 |
|------|-----------|----------|
| **代码补全 / Fill-in-the-Middle** | Diffusion 天生支持双向生成 | Diffusion |
| **文本修订 / 编辑** | Diffusion 的"生成-精炼"能力可修改已有文本 | Diffusion |
| **高吞吐 API 服务** | Self-Speculation 提供 4× 加速且无损质量 | Self-Speculation |
| **长文档生成** | 块级并行生成减少串行等待 | Self-Speculation |
| **多模态 VLM** | 8B VLM 版本支持文档/音频/视频 agent | AR 或 Self-Speculation |

### 5.2 暂时不推荐的场景

| 场景 | 为什么不适合 | 建议 |
|------|------------|------|
| **流式输出** | Diffusion 需要块级完整生成 | 使用 AR 模式 |
| **需要精确概率采样的场景** | Diffusion 的采样分布与 AR 不同 | 使用 AR 模式 |
| **极低延迟的实时交互** | Diffusion 需要多步迭代 | 等待进一步优化 |

### 5.3 一个具体的部署示例

假设你在构建一个代码补全服务：

```python
# SGLang 配置
config = {
    "model": "nvidia/Nemotron-Labs-Diffusion-8B-Chat",
    # 开发阶段：用 AR 模式做基线
    "ar_mode": True,
    # 生产阶段：切换到 Self-Speculation
    # "self_speculation": True,  
    # 极致吞吐：切换到 Diffusion
    # "diffusion_mode": True,
}
```

**从开发到生产的迁移路径**：先用 AR 模式确保功能正确 → 用 Self-Speculation 模式做性能优化 → 在不需要精确采样的场景（如代码补全）尝试 Diffusion 模式。

---

## 六、产业意义：Diffusion LLM 会取代自回归吗？

### 6.1 短期（2026 下半年）：共存与互补

Nemotron-Labs Diffusion 不会"取代" AR 模型，而是提供了一个**推理时的加速选项**。大部分生产系统会在不同场景下混合使用两种模式：

- **质量控制场景**（如医疗/法律文档生成）→ AR
- **吞吐量优先场景**（如代码补全、批量处理）→ Self-Speculation / Diffusion

### 6.2 中期（2027-2028）：训练范式的变化

随着联合训练方法的成熟，**未来的 LLM 可能默认就是"AR + Diffusion 双模"的**。训练一次，两种推理模式。这会带来：

1. **更灵活的部署策略**：同一个模型，根据负载特征动态选择推理模式
2. **更低的推理成本**：Diffusion 模式的 TPF 提升意味着更少的 GPU 时间
3. **新的能力**：文本修订、fill-in-the-middle 等 AR 天生不擅长的任务

### 6.3 长期：超越自回归

从更远的视角看，Nemotron-Labs Diffusion 代表了一个更深层的趋势：**语言生成的"并行化"**。

过去十年，我们把几乎所有精力都投入在"让自回归生成更快"（KV Cache 优化、PagedAttention、speculative decoding）上。但这些都是**在串行框架内的优化**。Diffusion 语言模型则是**框架本身的改变**——从"一次一个"到"一次一块"。

这不是一个小优化，这是一个范式转移。就像从单线程到多线程编程的转变——你不再被串行逻辑锁死，而是可以同时处理多个位置。

---

## 七、竞品格局：谁在做 Diffusion LLM？

### 7.1 当前赛道

| 团队/项目 | 状态 | 特点 |
|-----------|------|------|
| **NVIDIA Nemotron-Labs Diffusion** | 已开源 | 3B/8B/14B + VLM，SGLang 集成，联合训练 |
| **Efficient-DLM (论文)** | 学术论文 | 证明了 AR→DLM 转换的可行性 |
| **LLaDA (2025)** | 研究项目 | 纯 Diffusion 语言模型，但质量差距较大 |
| **SEED-LLM** | 研究项目 | 离散 Diffusion 语言模型，规模较小 |

NVIDIA 的优势在于：**它是第一个把这条路线做到生产级的团队**。开源模型 + SGLang 集成 + Megatron 训练代码，社区可以立刻用起来。

### 7.2 为什么 NVIDIA 在这个方向领先？

1. **GPU 架构理解**：NVIDIA 最清楚自己的硬件特性，知道 memory-bound vs compute-bound 的瓶颈在哪里
2. **训练基础设施**：Megatron 框架的分布式训练能力是业界顶级的
3. **推理引擎生态**：投资 SGLang 等开源推理项目，形成完整的技术栈
4. **商业动机**：更高效的推理 = 更少的 GPU 消耗 = 对 NVIDIA 芯片销售的间接促进（ paradoxically）

---

## 八、总结：一个值得密切跟踪的技术方向

Nemotron-Labs Diffusion 的出现，标志着 Diffusion Language Model 从"学术论文"正式进入了"生产工具"的范畴。

它的三个核心价值主张：

1. **同一个模型，三种推理模式**——不需要维护多个模型
2. **Self-Speculation 实现无损加速**——4× 速度提升，质量不降
3. **Diffusion 模式解锁 AR 天生做不到的能力**——文本修订、fill-in-the-middle

对于开发者来说，最值得关注的不是"它有多快"，而是"它开启了什么新可能"。

**自回归模型教会了 AI 一个字一个字地说话。Diffusion 语言模型将教会 AI 一次性思考一整段话，然后精炼它。**

这不是一个更快的 LLM。这是一个**不同类型的 LLM**。

---

## 参考资料

- [NVIDIA Nemotron-Labs Diffusion 官方博客](https://huggingface.co/blog/nvidia/nemotron-labs-diffusion)
- [Nemotron-Labs Diffusion 模型集合 (HuggingFace)](https://huggingface.co/collections/nvidia/nemotron-labs-diffusion)
- [技术报告](http://bit.ly/Nemotron-Labs-Diffusion-Report)
- [Efficient-DLM 论文 (arXiv:2512.14067)](https://arxiv.org/abs/2512.14067)
- [SGLang 集成 PR](https://github.com/sgl-project/sglang/pull/25803)
- [NVIDIA Megatron Bridge 训练代码](https://github.com/NVIDIA-NeMo/Megatron-Bridge/tree/main/examples/diffusion/recipes/nemotron_labs_diffusion)
- [NVIDIA Nemotron Pretraining Datasets](https://huggingface.co/collections/nvidia/nemotron-pre-training-datasets)
- 小R Blog: [DFlash：用 Block Diffusion 重写 LLM 推理加速](https://github.com/kejun/blogpost/blob/main/2026-05-09-dflash-speculative-decoding-block-diffusion.md)
