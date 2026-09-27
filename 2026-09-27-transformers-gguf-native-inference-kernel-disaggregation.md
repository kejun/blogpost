# 当 transformers 开始"说 llama.cpp 的语言"：GGUF 原生推理深度拆解——追平 C++ 的 98% 背后，是推理引擎的"内核化"解体

> 2026-09-27 · AI技术 · 本文约 4700 字

## 一条博客，缝合本地推理的"大陆裂谷"

9 月 22 日，Hugging Face 官方博客发了一篇分量远超字数的文章：**《Transformers now runs llama.cpp quants》**——transformers 现在可以高效运行 GGUF 量化模型了。不是"能加载"（那早在 2024 年就有了），而是**权重保持压缩状态直接推理，性能追平 llama.cpp**。

博客开头引用了 HF CTO Julien Chaumond 四月的一条推文：

> "这就是我们现在的位置，不瞒你说，感觉相当神奇 🧙‍♀️ Qwen3.6 27B 通过 llama.cpp 跑在 MacBook Pro 里的 Pi coding agent 中。在 HF 代码库上做非平凡任务，这已经非常、非常接近调用 Claude 最新的 Opus 了……"

过去几年，本地推理世界存在一条清晰的"大陆裂谷"：一边是 **llama.cpp 阵营**——C++ 写的、推理优先、GGUF 格式，撑起了 Ollama、LM Studio、Jan 等几乎所有本地 AI 工具，模型下载量以百万计；另一边是 **transformers 阵营**——Python/PyTorch 写的、研究优先、safetensors 格式，是全世界模型定义的"事实源头"。部署的人和研究的人，用的甚至是两套互不相认的文件格式。

现在，这条裂谷被从内核层面缝合了。而操刀的双方——transformers 和 GGML/llama.cpp 团队——如今都在同一家公司。

## 关键数据一览

| 维度 | 数据 |
|------|------|
| 发布时间 | 2026-09-22（HF 官方博客） |
| 代码状态 | transformers main 分支（随下一个正式版发布），需配合 kernels 库 |
| 首批硬件 | Apple Silicon（MPS/Metal），打包推理路径暂为 Mac 独占 |
| 首批架构 | Qwen3.5 dense + MoE（含兼容的 Qwen3.8 checkpoint） |
| 测试环境 | MacBook Pro M2 Max / 32GB 统一内存 / macOS 26.6 / PyTorch 2.12.1 / kernels 0.17.0 |
| 4B 模型性能 | transformers 70.4 tok/s vs llama.cpp 71.8 ± 0.4（**98%**） |
| 27B 模型性能 | transformers 15.9 tok/s vs llama.cpp 13.4 ± 0.9（**反超 18%**） |
| MoE 35B-A3B 性能 | transformers 60.2 tok/s vs llama.cpp 61.3 ± 0.5（**98%**） |
| 内核加速贡献 | 层级内核带来 1.51×–2.09× 提速 |
| 生成循环优化贡献 | 1.16×–1.79× 提速（对**所有** transformers 模型生效） |
| 复用内核数量 | 5 个：ggml-quantization、ggml-norm、ggml-attn、ggml-gated-delta-net、topk |
| 内存占用参照 | Qwen3.5-4B：BF16 8.42GB → Q4_K_M 2.74GB（约 1/3） |

## 前情：从"反量化导入"到"打包推理"，中间隔了一次收购

严格说，transformers 支持 GGUF 不是新闻——2024 年 8 月的 v4.44 就能加载 GGUF 文件了。但那条路径是**导入式**的：加载时把 4-bit 权重反量化成 bf16/fp16，推理时和普通模型无异。文件小了，**内存一点没省**，对"想在 32GB 的 Mac 上跑 27B 模型"的人来说毫无意义。

真正的转折发生在 2026 年 2 月 20 日：**GGML 和 llama.cpp 团队整体加入 Hugging Face**。官宣博客里那句话现在读来像是一份技术路线图："llama.cpp 是本地推理的基础构件，transformers 是模型定义的基础构件，这简直是天作之合（a match made in heaven）。"公告同时承诺了两件事：一是让新模型从 transformers 的"定义源头"一键进入 llama.cpp；二是改善 ggml 系软件的打包和用户体验。

七个月后，这篇博客就是承诺的第一次大额兑现——而且方向比外界预期的更激进：不是把 transformers 模型导出成 GGUF（那是 llama.cpp 侧的事），而是**把 ggml 的 GPU 内核搬进 PyTorch 的执行流里**。收购的组织整合，落到了内核层面的代码整合。

## 技术方案一：不造运行时，只借内核——kernels 库的"特洛伊木马"

这次集成最关键的架构决策是**没有**做的事：没有把 llama.cpp 运行时嵌入 transformers，没有 fork 一个推理引擎，也没有用 PyTorch 重写一遍量化算子。取而代之的路线是——

> 权重以 GGUF 打包格式原样驻留在 Metal 显存里，通过 HF 的 [kernels](https://huggingface.co/docs/kernels/index) 库调用 ggml 的预编译 Metal 内核完成计算。

kernels 库是 HF 推出的"GPU 内核分发机制"：内核作者把编译好的二进制发布到 Hub 上，使用方像 `from_pretrained` 拉模型一样拉内核，按 PyTorch 版本匹配构建。这次用到的五个内核分工如下：

| 内核 | 职责 |
|------|------|
| [ggml-quantization](https://huggingface.co/kernels/ggml-org/ggml-quantization) | 直接读取打包的量化权重做矩阵运算（含 MoE 选中专家），**避免每次解码前展开整个权重矩阵** |
| [ggml-norm](https://huggingface.co/kernels/ggml-org/ggml-norm) | 融合归一化算子，含 Qwen3.5/3.8 使用的零中心 RMSNorm |
| [ggml-attn](https://huggingface.co/kernels/ggml-org/ggml-attn) | ggml 的 Metal flash attention，覆盖 prompt 处理与逐 token 解码 |
| [ggml-gated-delta-net](https://huggingface.co/kernels/ggml-org/ggml-gated-delta-net) | 加速 Qwen3.5/3.8 混合架构中线性注意力层的 gated delta network |
| [topk](https://huggingface.co/kernels/transformers-community/topk) | MoE 专家路由（softmax + top-k 融合），HF 自研的 Metal 实现 |

前四个来自 ggml，第五个补的是 MoE 路由这个 llama.cpp 之外的独立瓶颈。加载体验上做到了零配置：`AutoModelForCausalLM.from_pretrained(model_id, gguf_file=filename)` 一行搞定，检测到 Metal 环境自动挂载 ggml 内核、自动选 `ggml-attn` 作为注意力实现，拉不到内核就降级 sdpa 并给出警告；完全没有兼容内核时才退回反量化路径。

用户视角，这就是普通的 transformers：`apply_chat_template`、`generate`、logits processor、hooks，全都不变。C++ 世界的性能优势，被拆成了五个可以在 Hub 上独立下载的二进制包，"特洛伊木马"式地进入了 Python 世界。

层级内核的收益可以单独度量（固定启用量化内核，对比开/关其余层级内核）：

| 模型 | 仅量化内核 | 全部层级内核 | 提速 |
|------|-----------|-------------|------|
| Qwen3.5-4B (Q4_K_M) | 44.2 tok/s | 70.4 tok/s | **1.59×** |
| Qwen3.8-27B (UD-Q4_K_M) | 10.5 tok/s | 15.9 tok/s | **1.51×** |
| Qwen3.5-35B-A3B (UD-IQ4_XS) | 28.8 tok/s | 60.2 tok/s | **2.09×** |

MoE 模型收益最大（2.09×）符合直觉：专家路由 + 稀疏激活意味着每 token 的 GPU 计算量小，算子调度和融合质量的占比就高，`topk` 融合内核和 gated-delta-net 加速正好打在这类模型的七寸上。

## 技术方案二：两个 PR 干掉 CPU-GPU 同步点，所有模型白拿加速

博客里更值得 Python 工程师细读的部分，是两个看似不起眼的 `generate` 循环改动：

- **[PR #48814](https://github.com/huggingface/transformers/pull/48814)：尽早丢弃无用的 attention mask。** decoder-only 输入无 padding 时，那个全 1 的 mask 在生成开始处直接删掉，下游注意力代码不必每个 token 都检查一遍"这 mask 能不能跳过"，因果注意力语义不变。
- **[PR #47975](https://github.com/huggingface/transformers/pull/47975)：延迟停止检查。** 停止判定改为异步拷贝、下一步再消费——CPU 不必等 GPU 把"要不要停"的结果读回来，可以持续给 GPU 排活儿；流式输出同理，多跑的那一步从结果里裁掉。

这两个改动的本质是同一件事：**消灭逐 token 生成循环里的 CPU-GPU 同步点**。自回归解码是个"小步快跑"的负载，每 token 的 GPU 计算可能只要几毫秒，任何一次同步等待都会让 GPU 空转；哪怕每 token 只等 1ms，累积起来也是两位数的吞吐损失。这正是 llama.cpp、vLLM 这类 C++/CUDA 引擎长年碾压 PyTorch eager 模式的真正原因——不是 Python 慢，是**同步慢**。

| 模型 | 优化前 | 优化后 | 提速 |
|------|--------|--------|------|
| Qwen3.5-4B | 49.6 tok/s | 70.4 tok/s | **1.42×** |
| Qwen3.8-27B | 13.7 tok/s | 15.9 tok/s | **1.16×** |
| Qwen3.5-35B-A3B | 33.7 tok/s | 60.2 tok/s | **1.79×** |

这组数据的分布规律教科书级：**单 token 计算量越小，循环优化收益越大**。27B dense 模型每 token 要搬 16.5GB 里的十几个 GB 权重，计算时间足以掩盖 CPU 调度开销，只拿到 1.16×；而 MoE 模型每 token 只激活 3B 参数，GPU 干完活儿就开始等 CPU，优化后 1.79×。这也解释了为什么 HF 强调这两个 PR "改善所有 transformers 模型，不只是 GGUF"——任何在 Mac 上用 `generate` 写自定义解码循环的人（约束解码、投机采样、agent 工具调用中途拦截）都白拿这笔加速。

值得注意的是团队的技术选型：他们明确选择**让 eager 执行变快，而不是依赖 torch.compile**。理由是交互场景要的是"秒开 + 稳定的出字流"，编译暂停和输入形状变化触发的重编译在聊天场景不可接受。这是给"本地推理"这个使用场景量身定做的工程判断——服务端批量场景尽可以 compile，笔记本上的单会话不行。

## Benchmark 细读：98%、118%、98%，以及那个反超

正面对比 llama.cpp（M2 Max 32GB，llama.cpp b10200 / ggml 0.18.0 Metal 后端）：

| 模型 | transformers | llama.cpp (tg128) | 比值 |
|------|-------------|-------------------|------|
| Qwen3.5-4B · Q4_K_M · 2.74GB | 70.4 tok/s | 71.8 ± 0.4 | 98% |
| Qwen3.8-27B · UD-Q4_K_M · 16.5GB | **15.9 tok/s** | 13.4 ± 0.9 | **118%** |
| Qwen3.5-35B-A3B · UD-IQ4_XS · 16.3GB | 60.2 tok/s | 61.3 ± 0.5 | 98% |

三个细节值得放大：

**第一，transformers 的数字是"吃亏"口径。** llama-bench 的 tg128 是纯解码吞吐（`-p 0` 排除 prompt 处理），而 transformers 侧是完整 `generate` 128 token **含 12 token 的 prefill**，取三次预热跑的最好成绩。口径对 transformers 不利，结果却是打平甚至反超——纯解码的真实差距比表格更小。

**第二，27B dense 的反超说明 llama.cpp 并非处处最优。** 一个合理推测：Qwen3.8-27B 是较新的架构，b10200 对它的 Metal 路径（尤其零中心 RMSNorm 和混合注意力）未必调优到位；而 transformers 侧直接复用了 ggml 最新内核 + 上述两个循环优化。"C++ 引擎天然快"的直觉，在架构快速迭代期并不总成立——**谁先适配新架构，谁就快**。

**第三，测试方法论难得地诚实。** 基准脚本里赫然写着 `time.sleep(90) # let the machine cool: back-to-back runs decay by 10% or more`——连续跑分因散热会衰减 10% 以上，所以每轮之间让机器凉 90 秒。笔记本上做严肃 benchmark 的都懂这条注释的含金量，把它公开写进博客的却不多。

## 生态影响：GGUF 从"部署格式"升格为"研究格式"

性能追平只是入场券，真正的变化是 GGUF 在 transformers 里解锁的五件事：

1. **Python 里实验 GGUF**：用 hooks 查看中间激活、改 forward、原型自定义层——以前这些操作对 llama.cpp 用户是黑箱；
2. **评测 GGUF**：直接套用现有 transformers 评测流水线度量量化 checkpoint 的质量损失；
3. **验证 GGUF 转换**：同一框架里加载原始 checkpoint 和它的 GGUF 转换版，逐层对比权重转换是否正确；
4. **尝试新解码思路**：自定义 logits processor、stopping criteria，或者干脆用 Python 写生成循环；
5. **从 GGUF 继续微调**：`GgufConfig(dequantize=True)` 反量化成 bf16 后接入标准训练流程。

第五条最值得玩味。它意味着 GGUF 第一次有了"逆向通道"：社区量化师（Unsloth、bartowski、LM Studio Community）发布的成品，可以被研究者拿回来继续训练、再发布。量化格式从单向的"发布终点"变成了可循环的中间产物。

配套的 `transformers serve` CLI 直接暴露 OpenAI 兼容 API（`transformers serve "unsloth/Qwen3.5-4B-GGUF:Qwen3.5-4B-Q4_K_M.gguf"`），Jan、Pi 等客户端填个 `localhost:8000/v1` 就能连——Mac 本身成了一台"个人模型服务器"。对我们此前在 [Deltafin 一文](https://github.com/kejun/blogpost/blob/main/2026-09-09-deltafin-kimi-k3-ssd-streaming-inference.md)里追踪的"消费级硬件跑大模型"趋势，这是又一块拼图：当 2.74GB 的 Q4_K_M 就能塞进 4B 模型、16.5GB 塞进 27B，"本地模型够不够用"的问题正在变成"本地工具链顺不顺手"的问题。

## 更大的棋局：推理引擎的竞争单位，正从"运行时"降到"内核"

博客的"Beyond GGUF"一节暴露了真正的野心：

> 更大的机会，是把 ggml 的性能带给 llama.cpp **不支持**的模型。

这句话点破了一个行业结构性矛盾：**新架构的诞生速度，远快于单体推理引擎适配它们的速度。** llama.cpp 每支持一个新架构，都要在 C++ 里完整实现一遍模型——这就是为什么 Qwen 的 gated delta net 混合线性注意力、各种研究性变体，往往在发布后数周甚至数月才进 llama.cpp，有些永远进不去。而 transformers 天然拥有几乎所有新架构的 PyTorch 参考实现，缺的只是快内核。

kernels 库路线把这个矛盾解耦了：**内核只对张量负责，不对模型负责。** ggml-attn 不需要知道整个模型是不是 GGUF 加载的，ggml-norm 可以被任何 transformers 模型调用。于是"加速一个新架构"从"在 llama.cpp 里重写模型"降维成"为它缺的算子找到或写一个内核"。博客明说下一步是多模态：视觉、音频模型复用同样的 attention/norm/matmul 内核，无需等待 llama.cpp 的完整实现。

把镜头拉远，这是推理引擎"单体运行时"模式的解体前奏。vLLM、TensorRT-LLM、llama.cpp 都是垂直整合的巨构：自己的调度器、自己的内存管理、自己的算子库，性能护城河建立在"整栈最优"上。而 kernels-as-distribution 模式主张：一个 PyTorch 模型定义 + 一组可插拔的 Hub 分发内核，就能拿到专用引擎 98% 的性能。如果这条路走通，巨构引擎的护城河会收窄到只剩调度和批处理——因为 80% 的性能来自那几个热点内核（matmul、attention、norm、routing），而内核正在变成跨运行时流通的"标准件"。数据库行业演过同一出戏：从各家整栈执行引擎，到 Velox、DataFusion 这样的组件化执行层被到处嵌入。GPU 推理栈正在重走这条路，而 HF 手里同时握着"模型定义的源头"（transformers）和"最强的本地内核"（ggml），是唯一有资格做内核流通平台的玩家。

## 局限与冷思考：Mac 优先，不是偶然，也是边界

泼冷水的时间。当前版本的边界相当明确：

- **打包推理路径仅 MPS**：CUDA/ROCm 用户暂时只有反量化导入的老路，"GGUF 支持"不等于"你的设备上有打包内核"；
- **批处理是短板**：无 padding 的单会话受益最大，带 padding 的 batch 性能会掉，`generate_batch` 在 MPS 上还在路上——现阶段定位就是"一个人、一台 Mac、一个对话"；
- **架构覆盖窄**：Qwen3.5 dense/MoE + 兼容的 Qwen3.8，其他架构要排队（HF 开了 issue 通道按需求排优先级）。

Apple Silicon 优先当然不是偶然：统一内存架构天然适合大模型塞笔记本，MacBook Pro 是 HF 开发者自己的人均装备，而"Local AI"恰好是 HF 收购 llama.cpp 时打出的旗帜。但要清醒：**交互式单会话是本地推理里最简单的一档负载**。真正的考验在后面——CUDA 上的打包内核、批处理、以及非 Qwen 系架构的长尾适配。2 月收购公告里"single-click 发布"的承诺，这次兑现了一半（llama.cpp → transformers 方向），反方向（transformers 新模型 → llama.cpp）还欠着。

## 结语：格式先赢，运行时后和

回看这场整合的时间线：GGUF 用三年时间赢下了"本地推理格式之战"——Ollama、LM Studio、Jan 全部构建其上，下载量以百万计；今年 2 月，格式的发明者被格式最大分发平台（HF）收编；9 月，两个曾经平行的世界在内核层面接通。

这几乎是基础软件史上反复上演的剧本：**先有事实标准的格式，再有围绕格式的运行时大和解。** SQLite 之于数据库文件、OCI 之于容器镜像、ONNX 之于框架互操作（虽然它只成功了一半）——格式的统一总是跑在引擎统一前面，因为格式是生态的最大公约数，而引擎只是公约数的一种实现。

对开发者的实操建议很简单：如果你的场景是 Mac 上的单会话交互 + Qwen 系模型，现在就可以在 transformers 里直接用 GGUF，性能和 llama.cpp 没有实质差距，还白得 Python 生态的全部可调试性；如果是生产服务端，llama.cpp/vLLM 依然是正解——HF 自己都说 llama.cpp 仍是"本地推理效率优先时的推荐引擎"。但值得盯住的是方向：**当 Python 侧拿到 C++ 侧 98% 的性能，"研究用 transformers、部署用 llama.cpp"的分工惯例，第一次有了松动的理由。** 而这，可能才是 9 月 22 日那篇博客最深的一层含义。

---

## 参考链接

- [Transformers now runs llama.cpp quants — Hugging Face Blog (2026-09-22)](https://huggingface.co/blog/transformers-llama-cpp-quants)
- [GGML and llama.cpp join HF (2026-02-20)](https://huggingface.co/blog/ggml-joins-hf)
- [transformers GGUF 文档](https://huggingface.co/docs/transformers/main/en/quantization/gguf)
- [kernels 库文档](https://huggingface.co/docs/kernels/index)
- [PR #48814: Drop unnecessary attention mask early](https://github.com/huggingface/transformers/pull/48814)
- [PR #47975: Defer the stopping check](https://github.com/huggingface/transformers/pull/47975)
- [GGUF 格式规范](https://github.com/ggml-org/ggml/blob/master/docs/gguf.md)
- [Unsloth Qwen3.5-4B-GGUF](https://huggingface.co/unsloth/Qwen3.5-4B-GGUF)
- [llama-bench 工具](https://github.com/ggml-org/llama.cpp/tree/master/tools/llama-bench)
