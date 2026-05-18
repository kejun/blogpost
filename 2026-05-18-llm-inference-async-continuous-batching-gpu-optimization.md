# LLM 推理的"隐形浪费"：异步连续批处理如何释放 24% 的 GPU 算力

**文档日期：** 2026 年 5 月 18 日  
**标签：** LLM Inference, Continuous Batching, CUDA Streams, GPU Optimization, vLLM, Transformers  
**参考来源：** HuggingFace Blog — [Unlocking asynchronicity in continuous batching](https://huggingface.co/blog/continuous_async)

---

## 一、背景：每一块空闲的 GPU 都在烧钱

### 1.1 一个令人不安的数字

HuggingFace 在 2026 年 5 月 14 日发布了一篇看似低调却极其重要的技术博客：**《Unlocking asynchronicity in continuous batching》**。文章揭示了一个在生产级 LLM 推理服务中长期被忽视的事实——

> 在使用连续批处理（Continuous Batching）的 LLM 推理服务器中，**GPU 有接近 24% 的时间处于空闲等待状态**。

这个数字不是估算，而是通过精确的 CPU/GPU profiling 得到的实测数据：在 H200 GPU 上，用 8B 参数模型以 batch size 32 生成 8K tokens，总耗时 300.6 秒，其中 **72.1 秒** GPU 什么都没做，只是在等 CPU 准备好下一个 batch。

一笔简单的经济账：一块 H200 按需租赁价格约 $5/小时。如果一天 24 小时运行，成本 $120。其中 24% 的时间 GPU 在空转——也就是说，你每天白白烧掉 **$28.8**，每年就是 **$10,512**。这还只是单卡。如果你的推理集群有 100 块 GPU，这个数字就是 **$1,051,200**。

这不是"优化"，这是**捡钱**。

### 1.2 连续批处理的"盲点"

要理解为什么会有这么大的浪费，得先回到连续批处理的基本原理。

连续批处理（Continuous Batching）是 Orca 论文（2022）提出的经典推理优化技术，也是 vLLM、TGI 等主流推理引擎的核心调度策略。它的核心思想很直接：

```
传统批处理：
Batch 1: [Req1, Req2, Req3, Req4]  →  全部完成后才能处理新请求
            │
            ▼  大量 padding 浪费

连续批处理：
Step 1: [Req1, Req2, Req3, Req4]
Step 2: [Req1, Req2, Req5]         ← Req3/4 完成，Req5 立刻补入
Step 3: [Req1, Req6, Req7]         ← 始终保持高利用率
```

连续批处理解决了**空间维度**的浪费——不再用 padding token 填满整个 batch。但它引入了一个**时间维度**的浪费，而这个浪费几乎没有人讨论：

**CPU 和 GPU 在交替工作，而不是并行工作。**

```
同步连续批处理的时序：

CPU:  [准备 Batch N] → [等待 GPU] → [准备 Batch N+1] → [等待 GPU]
GPU:  [等待 CPU]      → [计算]     → [等待 CPU]       → [计算]

     ↑ CPU 忙时 GPU 闲 ↑ GPU 忙时 CPU 闲 ↑ 从未同时工作
```

在每一次 forward pass 中，这个"等待"的时间可能只有几毫秒。但当你在一个每秒执行数百次的循环中累积这些毫秒——它们就变成了 24% 的总运行时间。

---

## 二、核心技术：从同步到异步的三步跨越

### 2.1 第一步：用 CUDA Stream 解放 CPU

问题的第一个关键：如何让 GPU 开始计算后，CPU 不必等待结果就能继续做别的事？

答案是 **CUDA Stream**。

在 PyTorch 中，如果你从未手动指定过 stream，你的所有操作都运行在 **default stream** 上。default stream 有一个隐藏属性：**它是同步的**。任何在 default stream 上的操作，都会等待 GPU 上所有其他 stream 完成；反过来，任何非 default stream 的操作，也会等待 default stream 清空后才能启动。

这意味着：**只要你用 default stream，CPU 就永远要等 GPU**。

解决办法是改用非 default stream。在非 default stream 上启动一个 kernel launch 或非阻塞的内存拷贝，CPU 会立刻拿到控制权继续执行——GPU 在后台跑，CPU 不阻塞。

```python
# 同步方式（default stream）
output = model(input)        # CPU 阻塞，等待 GPU 完成
result = output.cpu()        # 结果已经准备好了

# 异步方式（非 default stream）
with torch.cuda.stream(compute_stream):
    output = model(input)    # CPU 立刻返回，GPU 在后台计算
# CPU 可以继续做其他事情，不用等 GPU
```

但这里有一个陷阱：如果把连续批处理中的三个 GPU 操作（H2D 传输、计算、D2H 传输）放到不同的 stream 上而不做任何同步，它们会**同时启动**——计算 stream 会在数据传输完成之前就读取 GPU 内存，D2H 传输会在计算完成之前就取走数据。结果就是**静默的垃圾输出**，不会报错，但全是错的。

### 2.2 第二步：用 CUDA Event 强制依赖顺序

CUDA Event 是解决这个依赖问题的机制。它的原理很优雅：

- `stream.record(event)`：在 stream 中插入一个标记点，GPU 执行到这个位置时标记 event 为完成
- `stream.wait(event)`：stream 在执行到这里时暂停，直到 event 被标记完成

重要的是：**wait 只阻塞 stream 本身，不阻塞 CPU**。CPU 把整个流水线排好后就可以走人了，GPU 内部的依赖关系由 event 自动管理。

```python
# 正确的异步流水线
h2d_stream.record(h2d_done)      # H2D 传输完成后标记
compute_stream.wait(h2d_done)     # 计算必须等传输完成
compute_stream.record(compute_done)  # 计算完成后标记
d2h_stream.wait(compute_done)     # 回传必须等计算完成
```

这样我们就得到了一个正确的异步执行流水线：

```
CPU:  [准备数据] → [排队所有 GPU 操作] → [继续准备下一个 batch！]
GPU:  [H2D] →[计算] →[D2H] →[H2D] →[计算] →[D2H] →...
                ↑ 依赖关系由 Event 管理，无需 CPU 干预
```

### 2.3 第三步：Pipelining——真正的并行

上面解决了"一个 batch"的异步执行，但还没实现"两个 batch 并行"。要消除那 24% 的浪费，我们需要做到：

> **当 GPU 在计算 Batch N 时，CPU 同时在准备 Batch N+1。**

HuggingFace 的实现策略是：

1. GPU 用 compute stream 执行 Batch N 的 forward pass
2. CPU 在 GPU 计算的同时，根据 Batch N 的输出（异步地从 D2H stream 取回）准备 Batch N+1
3. 这里有一个精巧的依赖：Batch N+1 的 KV cache 更新依赖 Batch N 的输出 token，所以需要额外的 event 来保证 CPU 读到了正确的结果后再启动 Batch N+1 的 GPU 操作

最终的时间线变成了这样：

```
异步连续批处理的时序：

CPU:  [准备 Batch 1] → [准备 Batch 2] → [准备 Batch 3] → [准备 Batch 4]
GPU:  [等待] → [计算 Batch 1] → [计算 Batch 2] → [计算 Batch 3] → [计算 Batch 4]

     ↑ CPU 和 GPU 同时工作 ↑ 重叠区域 = 被节省的 24% 时间
```

实测数据：从 300.6 秒降到 **228 秒**——**24% 的免费加速**，不需要改模型，不需要改 kernel，只需要重新编排 CPU 和 GPU 的协作方式。

---

## 三、深入剖析：为什么这个优化如此重要

### 3.1 三个 stream 的设计哲学

HuggingFace 的实现中使用了三个独立的 CUDA stream：

| Stream | 用途 | 为什么独立 |
|--------|------|-----------|
| **H2D Stream** | CPU → GPU 输入数据传输 | 可以与前一个 batch 的 D2H 重叠 |
| **Compute Stream** | GPU 上的 forward pass | 核心计算，依赖 H2D 完成 |
| **D2H Stream** | GPU → CPU 输出数据传输 | 可以与下一个 batch 的 H2D 重叠 |

这种三 stream 设计不是随意选择的。它对应了连续批处理流水线的三个天然阶段，每个阶段的依赖关系不同：

```
Batch N-1                  Batch N                    Batch N+1
┌─────────────┐     ┌────────────────────┐     ┌────────────────────┐
│  H2D        │     │  H2D               │     │  H2D               │
│  Compute    │     │  Compute           │     │  Compute           │
│  D2H        │     │  D2H               │     │  D2H               │
└─────────────┘     └────────────────────┘     └────────────────────┘
                     ↑ 三个 stream 的并行执行     ↑ 时间线持续向前
```

关键在于：**Batch N 的 H2D 可以和 Batch N-1 的 D2H 同时进行**（因为它们在不同的 stream 上，且没有依赖关系）。这种 stream 间的重叠是异步优化的核心收益来源。

### 3.2 KV Cache 的双缓冲策略

异步连续批处理最棘手的技术细节是：**KV cache 是共享状态**。

在同步模式下，每个 batch 计算完成后，CPU 立即更新 KV cache（写入新生成的 token，删除已完成的请求），然后为下一个 batch 读取更新后的 KV cache。这是串行的，所以没有并发问题。

在异步模式下，问题变得微妙：当 GPU 正在用 Batch N 的 KV cache 计算时，CPU 可能正在准备 Batch N+1，需要读取（或修改）KV cache。如果设计不当，就会出现数据竞争——GPU 读到一个正在被 CPU 修改的 KV cache 状态。

HuggingFace 的解决方案本质上是**双缓冲（Double Buffering）**：维护两个 KV cache 表——一个"active"表供 GPU 当前 batch 使用，一个"staging"表供 CPU 准备下一个 batch。当 Batch N 完成后，通过 event 同步点交换两个表。

```python
# 简化的双缓冲逻辑
kv_cache_active = {...}    # GPU 正在使用
kv_cache_staging = {...}   # CPU 正在准备

# GPU 计算 Batch N，使用 active
# CPU 准备 Batch N+1，使用 staging

# 当 Batch N 的 D2H 完成后，event 触发交换
swap(kv_cache_active, kv_cache_staging)
```

这种设计保证了 GPU 和 CPU 永远不会同时读写同一份数据，同时也不需要深拷贝——只是交换指针。

### 3.3 默认 stream 的"隐形陷阱"

文章中有一个极其重要的警告，值得每个做 GPU 编程的开发者记住：

> 在 PyTorch 中，`tensor.cpu()` 看起来是一个普通的函数调用，但如果 tensor 来自 default stream，它会**隐式同步**——CPU 会等到 GPU 上所有操作完成后才返回。

这个行为是 PyTorch 有意设计的，目的是让默认的使用模式是"安全"的。但对于追求极致性能的场景，它是一个**隐形陷阱**。

```python
# 陷阱：看起来是异步的，但实际是同步的
output = model(input)       # default stream
result = output.cpu()       # 隐式等待所有 GPU 操作完成！

# 正确：使用非 default stream + 非阻塞传输
with torch.cuda.stream(compute_stream):
    output = model(input)
# 使用 CUDA event 或 stream.wait_stream() 来精确控制同步点
```

这个问题的普遍性在于：**几乎所有 PyTorch 教程和示例代码都使用 default stream**。一个从教程学来的推理服务，在生产环境中天然就带着 24% 的性能浪费。

---

## 四、行业影响：谁在做，谁没做

### 4.1 主流推理引擎的现状

截至 2026 年 5 月，主流 LLM 推理引擎对异步连续批处理的支持程度不一：

| 推理引擎 | 连续批处理 | 异步批处理 | 状态 |
|---------|-----------|-----------|------|
| **vLLM** | ✅ 核心特性 | ⚠️ 部分支持 | vLLM 内部已有 stream 并行，但 HuggingFace 的实现更彻底 |
| **TGI (Text Generation Inference)** | ✅ 支持 | ⚠️ 有限 | 主要依赖 Rust + Python 混合架构，异步程度受架构限制 |
| **Transformers (HuggingFace)** | ✅ 新增 | ✅ 新增 | 本文讨论的实现正是 transformers 库的新功能 |
| **TensorRT-LLM** | ✅ 支持 | ✅ 支持 | NVIDIA 官方方案，基于 CUDA graph 的深度优化 |
| **SGLang** | ✅ 支持 | ⚠️ 部分 | RadixAttention 主要优化 KV cache 复用 |

HuggingFace 这个实现的特殊意义在于：**它是第一个在 transformers 这个最广泛使用的库中原生实现的异步连续批处理**。这意味着任何用 `pipeline` 或 `TextGenerationMixin.generate()` 的用户，不需要换引擎就能获得 24% 的加速。

### 4.2 这个优化在推理优化图谱中的位置

LLM 推理优化是一个多层级的技术栈，异步连续批处理只是其中一层：

```
LLM 推理优化栈（自底向上）：

┌────────────────────────────────────────────────────┐
│ L7: 模型架构     │ FlashAttention、GQA、MoE         │
├────────────────────────────────────────────────────┤
│ L6: 量化压缩     │ INT8/INT4/GPTQ/AWQ               │
├────────────────────────────────────────────────────┤
│ L5: 投机解码     │ Speculative Decoding、Medusa     │
├────────────────────────────────────────────────────┤
│ L4: 调度策略     │ Continuous Batching + Async ★   │ ← 本文讨论的层
├────────────────────────────────────────────────────┤
│ L3: 内存管理     │ PagedAttention、KV Cache Offload │
├────────────────────────────────────────────────────┤
│ L2: Kernel 优化  │ CUDA Graph、Fused Kernels        │
├────────────────────────────────────────────────────┤
│ L1: 系统级       │ 多 GPU 并行、Tensor/Pipeline     │
└────────────────────────────────────────────────────┘
```

异步连续批处理的独特价值在于：**它不依赖任何模型改动或 kernel 重写**。它是纯粹的"编排优化"——在现有的计算和传输操作之间，重新安排执行顺序。这使得它几乎是"免费的午餐"：

- 不需要重新训练模型
- 不需要量化或压缩
- 不需要写自定义 CUDA kernel
- 只需要正确管理 stream 和 event 的依赖关系

当然，"免费"是有条件的：你需要确保你的推理引擎正确实现了异步编排，而大多数现有的实现并没有做到极致。

---

## 五、实战指南：如何评估你的推理服务

### 5.1 诊断你的 GPU 利用率

如果你正在运行 LLM 推理服务，可以用以下方法诊断是否受同步等待的影响：

**方法一：Nsight Systems**

```bash
# 使用 Nsight Systems 分析 CPU/GPU 时间线
nsys profile --trace=cuda,nvtx python inference.py
nsys report generate -o profile report.nsys-rep
```

在 Nsight 报告中，寻找以下模式：
- 绿色的 GPU 活跃段和红色的 CPU 活跃段是否交替出现（同步）
- 是否有明显的间隙（GPU 空闲等待 CPU 或反之）

**方法二：PyTorch 内置 profiling**

```python
import torch
from torch.profiler import profile, ProfilerActivity

with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as prof:
    model.generate(inputs, max_new_tokens=100)

# 分析 CPU 和 GPU 操作的重叠情况
print(prof.key_averages().table(sort_by="cuda_time_total"))
```

**方法三：简单的 timeline dump**

HuggingFace 提供了一个 [简易脚本](https://gist.github.com/remi-or/8de44738629c4d3c72451aa01df1a2ab)，可以在连续批处理循环中 dump CPU 和 GPU 的活动跨度，生成类似文章中的 timeline 图。

### 5.2 判断是否需要异步优化

不是所有场景都能从异步批处理中受益。以下是判断标准：

| 场景 | 是否受益 | 原因 |
|------|---------|------|
| **大 batch（>16）** | ✅ 显著 | CPU batch 准备时间占比大，异步重叠收益高 |
| **小 batch（<4）** | ⚠️ 有限 | 计算时间本身很短，CPU  overhead 占比小 |
| **长文本生成（>1000 tokens）** | ✅ 显著 | 大量 forward pass 循环，异步收益累积 |
| **短文本生成（<50 tokens）** | ❌ 不明显 | 总循环次数少，优化收益被 overhead 抵消 |
| **高并发多请求** | ✅ 显著 | 连续批处理调度频繁，CPU 工作量大 |
| **单请求离线推理** | ❌ 不适用 | 无批处理需求，异步收益有限 |

---

## 六、深度思考：从"24% 浪费"看 AI 基础设施的成熟度

### 6.1 浪费是行业的"成熟度标尺"

24% 的 GPU 空闲时间——这个数字本身比技术细节更值得思考。

在传统的云计算和数据库领域，类似的"浪费"在基础设施成熟的过程中被逐步消除：
- 数据库从表锁 → 行锁 → MVCC，并发度提升了几个数量级
- 网络从阻塞 IO → 非阻塞 IO → epoll/IO_uring，吞吐量指数增长
- 存储从同步写入 → 异步写入 → Write-Ahead Log，延迟大幅降低

**每一次"从同步到异步"的转变，都标志着一个技术栈从"能用"走向"高效"。**

LLM 推理服务正处在这个转折点上。连续批处理解决了空间维度的浪费，异步连续批处理正在解决时间维度的浪费。下一个浪费会是什么？也许是**跨节点的 KV cache 共享**，或者是**预计算与生成阶段的流水线重叠**。

### 6.2 "免费加速"的代价

异步连续批处理被称为"免费加速"，但这个"免费"有前提条件：

**第一，调试复杂度剧增。** 同步代码是线性的、可推理的。异步代码需要精确管理 stream、event、内存屏障——一个漏掉的 event wait 就会导致静默的数据损坏。在 GPU 编程中，"静默错误"是最危险的 bug 类型。

**第二，可移植性下降。** CUDA stream 和 event 是 NVIDIA 专属的。如果你的推理服务需要支持 AMD GPU（通过 ROCm）或 Apple Silicon（通过 Metal），异步逻辑需要完全不同的实现。

**第三，边际收益递减。** 当 CPU 和 GPU 的协作被优化到几乎完美重叠后，继续压榨的空间会越来越小。下一个量级的加速需要更底层的优化——kernel 级别的改动、模型架构的调整，甚至硬件级的支持。

### 6.3 对开发者的启示

对于大多数 AI 应用开发者来说，这个故事的启示不是"你应该自己实现异步连续批处理"，而是：

**选择正确的推理引擎，比优化自己的推理代码更重要。**

在 2026 年的 LLM 推理生态中，性能差异不再是模型能力的差异，而是**基础设施工程质量的差异**。同样的模型，在不同的推理引擎上，吞吐量可以相差 3-5 倍。而其中一部分差异，就来自于"谁正确地实现了异步连续批处理"。

如果你的推理服务还在用同步的 `model.generate()` 循环，换到一个正确实现异步优化的引擎，你可能就获得了 24% 的免费加速。这是目前 AI 基础设施领域**投入产出比最高**的优化之一。

---

## 七、总结

HuggingFace 的这篇博客揭示了一个简单但深刻的道理：**在 GPU 推理中，最大的浪费往往不是计算不够快，而是组织不够好。**

同步连续批处理让 CPU 和 GPU 轮流工作，像两个人共用一把扳手——一个人拧螺丝的时候，另一个人在旁边等着。异步连续批处理给了每个人自己的扳手，让他们同时工作。

24% 的 GPU 空闲时间，不是硬件瓶颈，不是算法缺陷，而是一个**工程组织问题**。它提醒我们：在追求更大模型、更多参数、更强算力的同时，不要忽视了那些"免费"的优化——重新审视你的系统是如何组织计算的，可能比升级硬件更有价值。

> **核心要点：**
> 1. 同步连续批处理中，GPU 约 24% 的时间在等待 CPU，这是纯粹的时间浪费
> 2. 使用 CUDA Stream + Event 可以实现 CPU/GPU 的并行工作，消除这些等待
> 3. 关键技术方案：三 stream 分离（H2D/Compute/D2H）+ CUDA Event 依赖管理 + KV Cache 双缓冲
> 4. 这是一个"免费"的优化——不需要改模型、不需要写 kernel，只需要正确的编排
> 5. HuggingFace transformers 已原生实现，升级即可受益
> 6. 选择正确实现的推理引擎，比手动优化推理代码更重要

---

*本文基于 HuggingFace 官方博客 [Unlocking asynchronicity in continuous batching](https://huggingface.co/blog/continuous_async) 的深度解读与分析。该博客是 HuggingFace 高效 LLM 推理系列文章的第二篇，第一篇为 [Continuous Batching from First Principles](https://huggingface.co/blog/continuous_batching)。*
