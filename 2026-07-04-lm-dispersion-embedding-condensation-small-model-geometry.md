# 小模型的几何困境：嵌入坍缩与弥散损失——为什么"缩放定律"可能解释错了什么

> **摘要：** ICML 2026 接收论文 "Dispersion Loss Counteracts Embedding Condensation" 揭示了一个被长期忽视的现象：小语言模型的 token 嵌入在 Transformer 层间会向狭窄的锥形空间坍缩（embedding condensation），而大模型则天然抵抗这种坍缩。作者提出弥散损失（dispersion loss）作为正则化项，在 mid-training 阶段即可显著改善小模型的泛化能力。本文深入分析这一几何现象的四个核心特征、弥散损失的技术细节、与 Kaiming He 最新 "Diffuse and Disperse" 工作的关联，以及为什么这个发现可能动摇我们对"缩放定律"的理解根基。

---

## 引言：大模型更好的真正原因，可能不是参数更多

> "Larger language models are better than smaller language models, but might not merely because they have more parameters. It can be partially attributed to how they organize the information in the latent representations."
> —— LM-Dispersion 论文结论

2026 年 7 月 3 日，一条 Hacker News 首页的帖子引起了我的注意：**"Dispersion loss counteracts embedding condensation in small language models"**。这篇被 ICML 2026 接收的论文来自耶鲁大学 Gerstein 实验室团队，它提出了一个看似简单却极其深刻的观察：

**小语言模型和大语言模型之间最关键的区别，可能不在于参数量，而在于它们如何组织潜在表示的几何结构。**

这不是一篇"又一个新的损失函数"的工程论文。它从第一性原理出发，重新审视了一个我们以为已经理解的问题——**为什么大模型更好？**

答案可能比你想象的更几何、更本质。

---

## 一、嵌入坍缩：一个被忽视的几何现象

### 1.1 什么是嵌入坍缩（Embedding Condensation）

每个 Transformer 层的每个输入 token 都被表示为一个高维嵌入空间中的向量。随着这些向量逐层传递，它们的行为表现出一种令人不安的趋势——

**它们逐渐指向越来越相似的方向。**

用余弦相似度来度量，就是：随着层数加深，所有 token 对之间的余弦相似度趋向正值且越来越接近 1。这意味着嵌入向量被"挤压"进了一个狭窄的锥形子空间（narrow cone-like subspace）。

论文将这一现象命名为**嵌入坍缩（embedding condensation）**。

直观理解：想象 768 维空间中有一堆指向各个方向的箭头。经过几层 Transformer 后，这些箭头开始"对齐"，最终几乎都指向同一个方向。当所有嵌入向量都指向相似方向时，模型区分不同 token 的能力自然会受到损害——你失去了高维空间的表达能力。

### 1.2 数学直觉：从理论预测到实证发现

这一现象的理论根源可以追溯到 2023 年的一篇理论工作 "A mathematical perspective on Transformers"（Bétermin et al., 2023）。该论文证明了一个令人不安的定理：

> **如果无限堆叠 Transformer 层，所有 token 嵌入最终会聚到同一点。**

LM-Dispersion 团队在 2025 年 4 月观看该论文的一场演讲后受到启发，开始追问：**这个理论上的极端情况，在现实模型中是否会以某种"弱化版"出现？**

答案是肯定的。而且它出现的方式比我们想象的更系统、更值得警惕。

### 1.3 可视化：余弦相似度热图

论文展示了不同模型的余弦相似度热图（cosine similarity heatmap），横轴是 token 对，纵轴是 Transformer 层。

- **GPT-2（1.5B）**：浅层时相似度分布较宽，深层时大面积变为正红色（高相似度）
- **GPT-2-XL（1.5B）**：深层仍然保持了相当宽的相似度分布
- **Qwen3-0.6B**：坍缩极为严重，深层几乎所有 token 对都指向几乎相同的方向
- **Qwen3-32B**：即使到了最深层，嵌入向量仍然保持了足够的角度多样性

这不只是视觉上的差异。Spearman 相关系数和 Kendall's Tau 的定量分析都确认了同一个趋势：**在同一个模型族中，模型越小，坍缩越严重。**

---

## 二、四个核心发现：坍缩不只是"小模型的毛病"

### 2.1 发现一：越大越抵抗坍缩（Larger Model, Less Condensation）

这是论文的第一个核心观察，也是最直观的：

| 模型族 | 小模型 | 大模型 | 趋势 |
|--------|--------|--------|------|
| GPT-2 | 124M | 1.5B (XL) | 显著 |
| Qwen3 | 0.6B | 32B | 显著 |
| OLMo | 1B | 7B | 显著 |

关键细节：**这个趋势在多个独立的模型族中都成立**，包括 GPT-2、Qwen3、OLMo 等。这不是某个特定架构的巧合，而是一个跨架构的系统性现象。

论文在四种不同的输入数据集上验证了这一现象的一致性：WikiText、PubMedQA、IMDb、SQuAD。**嵌入坍缩对输入文本的选择鲁棒地存在**——它不是由特定类型的数据触发的，而是模型本身的固有行为。

### 2.2 发现二：控制变量实验确认因果关系

仅仅观察相关性是不够的。"更大的模型坍缩更少"可能是由许多混杂因素造成的——更大的模型通常有更多层、更大的隐藏维度、不同的初始化策略、更多的训练数据。

为了隔离"模型大小"这一单一变量，论文设计了一个**严格控制变量的实验**：

- 训练 4 个 GPT-2 类模型
- **唯一的变量是 MLP 维度**
- 所有其他因素完全相同：层数、嵌入维度、数据集、训练配置

结果：**即使在这种极端控制下，"越大越抵抗坍缩"的趋势仍然稳定复现。**

这个实验的重要性在于，它将嵌入坍缩从"相关性观察"提升到了"因果性现象"——模型大小本身（具体说是 MLP 维度）直接影响了嵌入空间的几何组织方式。

### 2.3 发现三：坍缩在初始化时就已出现

最令人惊讶的发现之一是：**嵌入坍缩不是在训练过程中产生的，而是在模型初始化时就已存在。**

论文分析了 OLMo-3-1025-7B 从初始化到预训练完成的多个检查点：

1. **初始化后**：已经存在明显的坍缩
2. **预训练中期**：坍缩开始被缓解
3. **最终 base 模型**：坍缩进一步被缓解，但并未完全消除

这意味着：

> **预训练的作用部分是在"修复"初始化引入的几何缺陷，而不是"创造"好的几何结构。**

这个发现对模型初始化设计有深远影响——如果我们能设计出初始就不坍缩的初始化方案，预训练可能会更高效。

### 2.4 发现四：知识蒸馏不是解法

一个自然的想法是：既然大模型不坍缩，那用大模型蒸馏小模型，小模型是不是就能学会"不坍缩"？

论文的第四个实验给出了否定的答案：

> **知识蒸馏不能让小模型学会抵抗嵌入坍缩。**

蒸馏后的小模型在行为上更接近大模型的输出分布，但其内部嵌入空间的几何结构仍然是坍缩的。这意味着**输出行为相似 ≠ 内部表征健康**——一个蒸馏模型可能在基准测试上表现不错，但其内部表示的表达能力仍然受限。

这对蒸馏社区是一个重要的提醒：蒸馏传递了"做什么"，但没有传递"怎么表征"。

---

## 三、弥散损失：一个简洁的几何正则化器

### 3.1 核心思想

既然问题是嵌入向量"挤在一起"，最直接的解决方案就是让它们"散开"。

弥散损失（dispersion loss）的核心思想极其简洁：**在训练过程中，额外加一个正则化项，鼓励同一序列中所有 token 的嵌入向量在单位超球面上均匀分散。**

数学上，它通过对所有 token 对之间的余弦相似度施加惩罚来实现：

$$\mathcal{L}_{disp} = \log \sum_{i \neq j} \exp(\text{cosine\_sim}(h_i, h_j) / \tau)$$

其中 $h_i$ 是第 $i$ 个 token 的嵌入向量，$\tau$ 是温度参数。这个形式与 InfoNCE 损失有相似之处，但关键区别在于：**它不需要正样本对，是一个完全自包含的正则化器。**

### 3.2 与其他正则化方法的对比

论文对比了四种不同的"让嵌入散开"的方案：

| 方法 | 机制 | 特点 |
|------|------|------|
| **弥散损失** | 均匀角度分散 | 自包含，不需要外部数据 |
| 去相关损失 | 不同特征维度不相关 | 鼓励特征维度正交 |
| ℓ₂-repel + 范数正则化 | 增加欧氏距离 + 限制膨胀 | 需要额外的范数约束 |
| 正交化损失 | 锐角推开，钝角不变 | 有固定的距离边界 |

弥散损失的优势在于**简洁性和自包含性**——它不需要外部预训练模型（与 REPA 不同），不需要正样本对（与对比学习不同），也不需要额外的参数。它只是一个"即插即用"的正则化项。

### 3.3 与 "Diffuse and Disperse" 的关联

弥散损失的设计灵感来自 Kaiming He（何恺明）和 Runqian Wang 的 "Diffuse and Disperse: Image Generation with Representation Regularization" 论文。那篇论文在图像生成领域提出了类似的表示正则化思路。

LM-Dispersion 团队在 2025 年 6 月看到这篇论文后，将其核心思想适配到了语言模型的 mid-training 场景。两个工作的关键区别：

- **Diffuse and Disperse**：面向图像生成，关注扩散模型的表示学习
- **弥散损失**：面向语言模型，关注 Transformer 层的嵌入几何

两个工作共同揭示了一个跨模态的深层规律：**无论处理的是像素还是 token，让内部表示保持分散而不是坍缩，都是提高模型表达能力的关键。**

### 3.4 效果可视化

论文展示了弥散损失在 mid-training 阶段的定性效果：

- **基线（默认损失）**：从已经坍缩的嵌入开始，mid-training 后改善有限
- **弥散损失**：从同样的坍缩嵌入开始，mid-training 后嵌入被显著"推开"，锥形空间明显扩大

定量结果方面，弥散损失在多个下游任务上带来了**虽小但一致的改善**。作者坦诚地指出，这些增益"细微到需要正式的统计检验才能与噪声区分"——这在机器学习论文中是一种难得的诚实。

---

## 四、为什么这个发现很重要：超越论文本身

### 4.1 对小模型训练的启示

2026 年的 AI 工程实践正在经历一个关键转变：**企业越来越多地在生产中部署 1-7B 的小型模型**，因为推理成本、延迟和隐私需求使得"调用最大 API"不再总是最优选择。

在这种背景下，嵌入坍缩的意义变得极为实际：

1. **你的小模型可能在"假装理解"**：由于嵌入坍缩，小模型的内部表示空间被严重压缩，这意味着它对不同输入的区别能力可能被系统性低估
2. **mid-training 是一个被低估的阶段**：弥散损失在 mid-training 阶段的收益表明，在预训练和 SFT 之间加入一个"几何修复"阶段可能是提升小模型能力的有效路径
3. **初始化设计可能比架构设计更关键**：既然坍缩在初始化时就已出现，重新设计初始化方案可能比修改架构更有效

### 4.2 对"缩放定律"的重新审视

Kaplan et al. (2020) 的缩放定律告诉我们：性能随参数量和训练计算量的增长而稳定提升。这个规律在经验上是成立的。

但 LM-Dispersion 提出了一个更深层的问题：

> **缩放定律描述的是"什么"（性能随规模增长），但没有解释"为什么"（规模是如何影响性能的）。**

嵌入坍缩提供了一个可能的"为什么"：

- 大模型不仅仅是"有更多的参数来记住更多的东西"
- 大模型的内部表示空间保持了更好的几何结构，使得信息组织更高效
- 这种几何优势部分来自于更大的 MLP 维度天然抵抗坍缩

如果是这样，那么**缩放定律的本质可能部分是一个几何定律**——更多的参数通过维持更好的表示几何来获得更好的性能。

### 4.3 对知识蒸馏社区的挑战

发现四（蒸馏不能修复坍缩）对知识蒸馏社区提出了一个严肃的挑战：

当前的蒸馏方法主要关注**输出行为的模仿**——让小模型输出与大模型相似的预测。但如果大模型的优势部分来自于其内部表示的几何健康度，那么仅仅模仿输出是不够的。

这引出了一个重要的研究方向：**表示蒸馏（representation distillation）**——不仅要模仿输出，还要模仿健康的内部表示几何。

### 4.4 对未来研究方向的影响

论文明确列出了几个值得探索的方向：

**方向一：更好的正则化器**
弥散损失是一个简单直接的方案，可能不是最优的。更精心设计的反坍缩方法可能带来更大的收益。

**方向二：超越预训练**
嵌入坍缩在 SFT 和 RL 阶段会如何演变？它会重新出现、稳定、还是与对齐目标产生不同的交互？这是一个完全开放的问题。

**方向三：机制和因果性**
嵌入坍缩的根本原因是什么？它与下游行为（如泛化能力）之间的因果联系能否被更强地建立？

**方向四：更好的架构**
能否设计天生抵抗坍缩的模型族或模块，而不只是依赖损失函数层面的正则化？

**方向五：更好的初始化**
能否开发让模型起始于"不那么坍缩"状态的初始化方案，从而减轻训练目标的负担？

这些方向中的任何一个如果被深入探索，都可能带来比弥散损失本身更大的影响。

---

## 五、批判性视角：论文做了什么，没做什么

### 5.1 论文的优势

1. **观察驱动而非工程驱动**：从一个理论问题出发，发现了具有实际意义的现象
2. **控制变量实验**：在混杂因素众多的模型大小研究中做了罕见的严格控制实验
3. **跨模型族验证**：在 GPT-2、Qwen3、OLMo 三个独立模型族中验证了同一趋势
4. **诚实的结果报告**：明确承认收益"细微"，pre-training 实验"薄弱"

### 5.2 论文的局限

1. **收益幅度有限**：弥散损失的改善是统计意义上显著的，但绝对幅度不大。对于追求 SOTA 的团队来说，这可能不足以改变训练流程
2. **预训练实验薄弱**：作者承认大规模预训练实验"昂贵"，因此数据有限。这是一个诚实的局限，但也意味着结论的推广需要更多验证
3. **mid-training 方案的非常规性**：继续在 WikiText 上进行 mid-training 不是业界标准做法。通常 mid-training 用于增强特定领域能力
4. **缺乏对推理阶段的分析**：坍缩在解码/推理阶段如何影响生成质量，论文没有涉及

### 5.3 一个更深层的问题

论文展示了一个有趣的不对称性：

> **预训练能缓解坍缩，但不能完全消除；弥散损失能进一步缓解，但改善幅度有限。**

这可能暗示了一个更深层的事实：**嵌入坍缩可能不是可以通过训练完全消除的"缺陷"，而是 Transformer 架构的一个固有倾向。**

如果这是真的，那么最终的解决方案可能不在于更好的损失函数，而在于**根本不同的架构设计**——一种天生不会坍缩的序列建模方式。

---

## 六、实践建议：如果你正在训练小模型

基于这篇论文和更广泛的文献，以下是一些对实践者有用的建议：

### 6.1 检查你的小模型的嵌入坍缩

你可以用不到 100 行代码检查你的模型是否存在嵌入坍缩：

```python
import torch
from torch.nn.functional import cosine_similarity

def measure_condensation(model, dataloader, layer_indices=[-1]):
    """测量模型在指定层的嵌入坍缩程度"""
    similarities = []
    model.eval()
    
    for batch in dataloader:
        with torch.no_grad():
            outputs = model(batch, output_hidden_states=True)
            for layer_idx in layer_indices:
                hidden = outputs.hidden_states[layer_idx]  # [batch, seq_len, dim]
                # 计算所有 token 对的平均余弦相似度
                normed = hidden / hidden.norm(dim=-1, keepdim=True)
                sim_matrix = torch.bmm(normed, normed.transpose(1, 2))
                # 取上三角（排除对角线）的平均值
                mask = ~torch.eye(sim_matrix.size(1), dtype=bool)
                avg_sim = sim_matrix[:, mask].mean()
                similarities.append(avg_sim.item())
    
    return sum(similarities) / len(similarities)

# 平均余弦相似度越高（越接近 1），坍缩越严重
# 健康模型的深层值通常在 0.1-0.4 之间
# 严重坍缩的模型可能达到 0.7-0.9
```

如果你的小模型的平均深层余弦相似度超过 0.6，嵌入坍缩可能正在限制你的模型性能。

### 6.2 考虑加入弥散损失

在 mid-training 阶段加入弥散损失作为一个轻量级正则化项：

```python
def dispersion_loss(hidden_states, tau=0.05):
    """计算弥散损失"""
    # hidden_states: [batch, seq_len, dim]
    normed = hidden_states / hidden_states.norm(dim=-1, keepdim=True)
    sim_matrix = torch.bmm(normed, normed.transpose(1, 2))
    
    # 取非对角线元素
    mask = ~torch.eye(sim_matrix.size(1), dtype=bool, device=sim_matrix.device)
    off_diag = sim_matrix[:, mask].view(-1, sim_matrix.size(0))
    
    # log-sum-exp trick for numerical stability
    max_sim = off_diag.max(dim=1, keepdim=True).values
    loss = max_sim + torch.log(
        torch.exp(off_diag - max_sim).sum(dim=1) / tau
    ).mean()
    return loss
```

建议权重从 0.1 开始，根据效果调整。

### 6.3 关注 mid-training 的几何健康度

不要只在基准测试上评估 mid-training 的效果。监控嵌入空间的几何指标（平均余弦相似度、奇异值分布等）可以提供额外的信号。

---

## 结语：几何可能是理解 LLM 的最后一块拼图

LM-Dispersion 论文的价值不在于弥散损失本身（一个简单但收益有限的正则化器），而在于它提出了一个我们之前很少认真思考的问题：

**语言模型的性能差异，在多大程度上是一个几何问题？**

如果嵌入空间的几何结构确实是决定模型表达能力的关键因素，那么：

- 缩放定律可能不仅是关于"多少参数"，还是关于"参数如何组织表示"
- 小模型的瓶颈可能不仅是容量不足，还是几何退化
- 未来的模型设计可能需要同时优化功能和几何两个目标

在 2026 年的夏天，当我们讨论 AGI 的距离时，也许我们应该先问问一个更基本的问题：**我们的模型在内部到底是如何组织信息的？**

答案可能藏在那些嵌入向量的角度里。

---

## 参考文献

1. Liu, C., Sun, X., Xiao, X., et al. (2026). "Dispersion loss counteracts embedding condensation and improves generalization in small language models." *ICML 2026*. PMLR.
2. Wang, R., He, K. (2025). "Diffuse and Disperse: Image Generation with Representation Regularization." *arXiv:2506.09027*.
3. Bétermin, E., et al. (2023). "A mathematical perspective on Transformers." *arXiv:2312.10794*.
4. Kaplan, J., et al. (2020). "Scaling Laws for Neural Language Models." *arXiv:2001.08361*.
5. Hacker News 讨论: [Dispersion loss front page post](https://news.ycombinator.com/item?id=48780826)

---

*本文基于 ICML 2026 论文 "Dispersion loss counteracts embedding condensation and improves generalization in small language models" 撰写，结合了作者对 2026 年 AI 工程实践的观察和分析。论文项目页面：https://chenliu-1996.github.io/projects/LM-Dispersion/*
