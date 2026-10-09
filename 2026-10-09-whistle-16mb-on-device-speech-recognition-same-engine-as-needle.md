# 一个 16.9 MB 的文件，把语音识别和工具调用塞进了同一颗 CPU 内核：Whistle 深度拆解

> 当所有人都在把模型越做越大时，Cactus Compute 用一周内刷上 Hacker News 前页的方式证明：在端侧 Agent 这件事上，"小到极致"本身就是一种架构选择。
> 本文拆解 Whistle —— 一个 16.9 MB、零依赖、跑在 CPU 上的开源语音识别模型，以及它背后与 26M 工具调用模型 Needle 共享的同一套 C++ 引擎。

---

## 一、16.9 MB 到底意味着什么

2026 年 10 月 2 日，Cactus Compute 发布 Whistle。几天后它以 474 分冲上 Hacker News 首页，讨论热度仅次于当日的时政新闻。它的宣传语朴素到近乎挑衅：

> "An open speech recognition model that runs on the same CPU engine as Needle. It transcribes seven languages, reaches the first token in 11 ms, and loads beside Needle so one binary turns a clip straight into tool calls."

翻译过来：一个 16.9 MB 的单文件模型，支持七种语言，首个 token 只要 11 毫秒，并且能和 Needle（26M 参数的工具调用模型）装在同一份二进制里 —— 于是"一段录音"到"一次工具调用"之间，不再有任何中间文本。

这个数字需要被放进坐标系里才能理解。OpenAI 的 Whisper base 是 145.3 MB，Moonshine tiny v2 是 41.9 MB。Whistle 是 16.9 MB —— 大约是 Whisper base 的 **1/8.6**，Moonshine 的 **1/2.5**。

但"小"从来不是重点，"小且不掉点"才是。Cactus 给出的对比里，Whistle 在 LibriSpeech test-clean / test-other、SPGISpeech、Earnings-22 以及 FLEURS 平均值上都领先 Whisper base；只在 TED-LIUM、AMI 和 MLS 平均值上落后。而在速度上差距是数量级的：

| 指标 | Whistle | Whisper base | Moonshine tiny v2 |
|------|---------|--------------|-------------------|
| 模型体积 | **16.9 MB** | 145.3 MB | 41.9 MB |
| 首 token 延迟 | **11.1 ms** | 73.2 ms | 22.8 ms |
| 解码速度 | **1,319 tok/s** | 266 tok/s | 262 tok/s |

（数据来自官方文章，测试条件为 Apple M4 Pro CPU，10 秒音频，各模型使用官方运行时与默认配置。）

这张表里最值得注意的不是"体积"，而是**首 token 延迟随音频长度的变化曲线**。Whisper 会把每一段输入补齐到 30 秒，所以它的首 token 延迟在 5 秒和 30 秒音频上几乎是恒定的 —— 你总是要为那 30 秒的固定开销买单。Whistle 则跟着输入走：5 秒音频 5.9 ms，10 秒音频 11.1 ms，30 秒音频 36.3 ms。对于"按下麦克风说一句话"这种交互，这种线性、可预测的延迟，比绝对速度值更有工程意义。

---

## 二、一切从 Needle 开始：无 FFN 的赌注

要理解 Whistle 为什么能这么小，必须回到它的"前半生"—— 今年 5 月开源的 Needle。

Needle 是一个 26M 参数、专门做单轮函数调用（single-shot function calling）的模型，在消费级设备上能跑到 6000 tok/s 的 prefill 和 1200 tok/s 的 decode。它的架构宣言只有一句话：

> "The entire model is just attention and gating, no MLPs anywhere."

一个连 FFN 都没有的大模型，听起来像是学术玩具。但 Cactus 给出的解释很扎实：**工具调用的本质是"检索 + 组装"，而不是"推理"**。把用户查询匹配到工具名、抽取参数值、吐出 JSON —— 这整套动作更接近检索，而不是需要多层非线性变换的复杂推理。既然知识来自输入的 schema 而不是参数里的记忆，那么占用绝大部分参数的 FFN 层，在这个场景里就是浪费。

这个观察被他们进一步推广了：在任何"模型能访问外部结构化知识"的任务里（RAG、工具调用、检索增强生成），模型都不需要在 FFN 权重里硬记事实。而语音识别，恰恰是另一种形态的"检索 + 组装"。

于是 Whistle 的路线变得清晰：**复用 Needle 的注意力骨干，只加一点点语音专有的东西**。官方文档里那句"Blocks marked shared run Needle's code, not a copy of it"—— 共享的模块运行的是 Needle 的代码，而不是一份拷贝 —— 点出了整件事的核心：这不是一个独立模型，而是同一个引擎的又一次"参数化"。

官方把正交化为这套骨干的注意力结构命名为 **Simple Attention Networks**（SAN）。它有两个关键构件：

- **mHC 残差通道**（四条并行的残差车道，借鉴流式网络中的多通道思想）；
- **Monarch Hadamard MLP** —— 用 Monarch 矩阵分解 + Hadamard 变换来替代传统 FFN 中的稠密前馈网络。

Monarch 矩阵是一类结构化矩阵（可以分解为两个块对角矩阵与一个置换矩阵的乘积），Hadamard 变换则提供了一种 O(n log n) 的正交变换。两者结合，等于用极少的参数实现了原本由 FFN 承担的"逐位置变换"能力 —— 这就是为什么"没有 FFN"并不等于"没有非线性"。

---

## 三、Whistle 架构逐层拆解

Whistle 依然是一个经典的 encoder-decoder 结构，但每一层都在为"省"服务。

### 前端（Front end）

16 kHz 单声道音频，以 25 ms 窗、10 ms 步长成帧，映射为 **80 维 log-mel 分箱**，频带限制在 250–3500 Hz（这是语音能量最集中的区间，砍掉两端对识别影响极小），再按通道归一化。30 秒音频 = 3,000 帧。随后一个 **128 通道、kernel 为 9 的卷积 stem 连续做三次二分降采样**，把帧数压到 375 —— 也就是每帧对应 80 ms。此后整条流水线都在这个更低的帧率上运行，`embed` 接口返回的就是每帧一行。

这一步的设计很"抠"：3,000 帧降到 375 帧，等于把后续所有计算的序列长度直接砍掉了 87.5%。在 CPU 上，序列长度就是计算量。

### 编码器（Encoder）

八个 Simple Attention 块：四条 mHC 残差车道 + 用 Monarch Hadamard MLP 取代前馈网络 —— 和 Needle 完全相同的块。

一个关键细节：**这里的注意力不是因果的**。3 秒处的帧可以"看到"12 秒处的帧。对语音识别来说这很重要 —— 识别需要双向上下文（一个词的意思往往取决于它后面说了什么），而流式的因果注意力会牺牲准确率。Whistle 选择用非因果注意力换取 WER，代价是不能真正流式输出，只能等整段音频进来。

### 解码器（Decoder）

八个 Laddered Simple Attention 块，宽度 512，8 个 query head 对 2 个 KV head（GQA，省 KV cache），query/key 维度 48、value 维度 64，Q/K/V 上各有一个 3-tap 因果卷积，并在第 3、7 层做 **engram 查表**（18,432 个槽位）。

"Laddered"是指：每一个深度的模型（从 2 层起）都是被单独训练过的，运行时通过 `--audio-depth` 选择用几层。**编码器永远不被切片，八个块在任何深度下都完整运行。** 这意味着你可以用同一个权重文件，在树莓派上用浅解码器跑得飞快，在服务器上用深解码器追准确率 —— 一份权重，多种延迟档位。这是一个非常实诚的工程选择：准确率的绝大部分来自编码器的双向上下文，解码器深度只是精修。

### 语音专有的那一点点：门控交叉注意力

整个语音适配部分，**每一层只加了一个东西**：门控交叉注意力。

```
x ← x + σ(g) · softmax(q̂ K̂ᵀ/√d) V
```

每个解码器层通过一个可学习的门 `g` 去读编码器输出，K 和 V 直接取自音频片段。关键在于：**这些投影在音频到达时只算一次**（375 帧 × 8 层），然后在整个解码过程中被反复复用。于是"5 个 beam"的代价只是 5 份短的文本缓存，而不是 5 遍对音频的重算。

这是一个教科书级的优化：把与音频相关的重计算从"每 beam 每步"挪到"每片段一次"，beam 搜索的开销就从乘性变成了加性。

### 解码（Decoding）

- **5 个 beam**，按长度归一化的对数概率打分；
- **关键词偏置**：用 Aho-Corasick 自动机在你传入的短语上行走，与 beam 并行推进，自动机每前进一格就抬高对应 beam 的对数概率（这就是为什么 `keywords=["Siobhan", "Krzysztof"]` 能救回那些罕见人名地名）；
- **转录上限 320 token**；
- **词表 8,192 个文本 piece + 7 个语言 token**。语言不是一个旁路返回值，而是一个被"说"出来的 token —— 检测到的语言本身就是一个输出 token。这个设计让语言检测和转录共享同一个解码过程，零额外开销。

### 静音（Silence）

引擎在解码器启动**之前**先测量片段的响度范围。低于阈值就返回空转录和空语言，根本不进入 beam 搜索。这是一个非常"端侧"的细节：在手机上，麦克风经常被误触发，如果每次静音都要跑一遍完整解码，电池会被白白吃掉。用一次廉价的响度检测挡住大部分空输入，是端侧推理必须做的"前门卫生"。

---

## 四、数据对比与"诚实的解读"

Cactus 公布的 WER（词错误率）对比里，有几个值得注意的处理方式：

1. **缺失的柱子 = 作者从未发布过的 benchmark**。Moonshine 是纯英文模型，Whisper 官方从未报告过 SPGISpeech、Earnings-22、AMI cleaned 这些数据集上的成绩 —— 所以那几根柱子是空的，而不是"我们的对手作弊把数字藏起来了"。
2. **口径标注清晰**：Whisper 报告的 AMI 数字是 AMI-IHM（一个不同于另外两者报告的子集），这一点被明确写出，而不是含糊地并排比较。
3. **Whistle 的 WER 在 86,174 条 utterance 上测量**，使用 Whisper 官方的 normalizer 做文本归一化。
4. **训练/验证数据污染检查**：通过比对音频校验和与说话人 ID，确认没有任何测试音频出现在 Whistle 的训练或验证集中。

这四条里，第 4 条尤其值得点赞 —— 在语音领域，数据集污染（"模型见过测试集"）是长期存在的隐性作弊，一个愿意公开说自己做了 checksum + speaker ID 交叉验证的团队，至少在方法论上是认真的。

但同样的数据也要**反向解读**，这才是深度分析该做的事：

- **Whistle 在"读出来的语音"（LibriSpeech 有声书、SPGISpeech 财报电话会）上领先**，但在**TED-LIUM（自然演讲）、AMI（多人会议）、MLS（大规模多语言）上落后 Whisper**。这不是偶然 —— 会议场景充满重叠语音、远场混响、口音切换，而这些恰恰是训练数据规模和多语言覆盖的胜利。16.9 MB 的容量天花板就在这里出现。
- **Whisper base 的 30 秒补齐策略**让它在长音频上更"稳"，而 Whistle 的 30 秒上限意味着超过 30 秒的会议录音必须被切段 —— 切段处的上下文丢失会进一步放大它在 AMI 这类场景的劣势。
- **1,319 tok/s 的解码速度是"小模型的特权"**：词表只有 8,192，语言只有 7 种。Whisper 的多语言版本词表是 51,865（1024 个语言 token + 大量语言相关合并），这个规模差异在解码速度上是直接的。

所以正确的结论不是"Whistle 打败了 Whisper"，而是：**Whistle 在"短语音、七种主流语言、消费级设备"这个精确契约下，几乎是最优解；一旦越出这个契约，Whisper 依然不可替代。** 理解一个模型的适用边界，比相信它的跑分更重要。

---

## 五、一个二进制，三条命令：语音直连工具调用

Whistle 最反直觉的设计，是它把自己降格成了"同一引擎里的另一个模型文件"。

`needle_load` 会读进你给它的任何 `.cact` 文件，所以同一个二进制可以做语音、做文本、或两者兼做：

```bash
# 只做语音识别
needle --model whistle.cact --audio clip.wav

# 只做工具调用
needle --model needle3.cact --tools tools.json --prompt "turn off the kitchen lights"

# 语音直连工具调用：一段录音进去，一次函数调用出来
needle --model needle3.cact --model whistle.cact --tools tools.json --audio clip.wav
```

第三条命令是整篇文章的技术核心。`needle_complete` 直接吃进音频片段，识别、对工具做匹配、返回一个 JSON 对象，语音相关字段以 `audio_` 前缀挂在同一层：

```json
{
  "function_calls": [
    { "name": "set_lights", "arguments": { "room": "kitchen", "on": false } }
  ],
  "confidence": 0.94,
  "audio_text": "turn off the kitchen lights",
  "audio_language": "en"
}
```

注意这里发生了什么：**调用方（caller）从头到尾没有见过任何转录文本。** 传统流水线是 `音频 → ASR → 文本 → LLM → tool call`，中间那一段文本是必须被物化、搬运、再解析的。Whistle+Needle 把中间的文本变成了一条内部通道 —— 它依然存在（`audio_text` 字段），但不再需要经过调用方的手。

在 Python 侧，这一切被压缩到三行：

```python
import needle

print(needle.transcribe("clip.wav")["text"])
# turn off the kitchen lights
```

而每一次调用都会返回：文本、语言、首 token 毫秒数、解码 tokens/s。`word_timestamps=True` 会附上每个词的时间戳与概率；`keywords=[...]` 做关键词偏置；`language="de"` 强制语言。

对端侧 Agent 来说，这个"合体"的意义在于**延迟预算**。一个智能家居语音助手，如果 ASR 和意图理解是两次独立的模型推理 + 一次网络往返，端到端延迟会轻松突破 500 ms 的心理阈值。而用一个内核、一次加载、共享量化，把两段推理流水线拼在一起，延迟才有可能压进人类感知"即时应答"的窗口。

---

## 六、工程面的取舍：17 个目标平台与"无环境变量"

Whistle 的引擎（也就是 Needle 的引擎）预编译支持 **17 个目标平台**：从 macOS、Linux，到 Android、iOS、watchOS、Windows on ARM、RISC-V、MIPS，甚至浏览器和 WASI component。每个平台文件夹里放着 `needle` 二进制、`libneedle.a` 和 `needle.h`，能加载任何 `.cact` 文件。

更值得玩味的是官方那句话：

> "The engine reads no environment variables. Every behaviour is a compiled default or an explicit flag."

**引擎不读任何环境变量。** 这句话在运维工程师眼里近乎浪漫 —— 没有隐藏配置、没有"在我机器上能跑"的环境依赖、没有运行时才暴露的惊喜。所有行为要么是编译期默认值，要么是显式命令行 flag。

整个语音 C API 只有三个函数：`needle_load`、`needle_transcribe`、`needle_embed`。支持"嵌入式"场景的野心是明摆着的：mobiles、wearables、robots、smart home、automotive、microcontrollers。当一个 16.9 MB 的语音模型能被塞进微控制器，端侧 AI 的边界被重新画了一次。

---

## 七、深层洞察与风险

把这篇文章抽干，留下几条真正值得记住的判断：

**1. "无 FFN"不是噱头，而是对任务本质的下注。** 工具调用 = 检索+组装，语音识别 = 检索+组装（把声学特征检索到文本 token）。这两类任务共享一个结构特征：**知识来自输入，而非参数**。当知识来自输入时，FFN 的记忆职能失效，只剩变换职能 —— 而变换职能可以被 Monarch Hadamard 这类结构化算子以极少的参数近似。这是本次发布最硬的洞见。

**2. 交叉注意力是端侧多模态的正确原语。** 语音模型读文本模型的方式（门控交叉注意力 + 一次性投影 + 缓存复用）和工具调用模型读工具 schema 的方式，在数学形式上是同构的。Cactus 甚至暗示这是一个通用模式："任何模型能访问外部结构化知识的任务"。这意味着未来端侧的 ASR + LLM + RAG，可能不再是三个模型拼积木，而是同一骨干的三种"通道"。

**3. 交付形态比模型本身更重要。** `needle --model A.cact --model B.cact` 这种"多模型单引擎"的设计，把"部署一个多模态 Agent"的复杂度从"N 个运行时"降到"一个二进制 + N 个权重文件"。对嵌入式团队来说，这是实打实的开发成本节省。

**但风险也必须被点出：**

- **语言覆盖只有 7 种**（英、德、法、西、意、荷、波），且以欧洲语言为主。对中文、日文、阿拉伯语等用户，这个模型直接出局。
- **30 秒单遍上限**。长音频必须手动切段，而切段策略会显著影响 WER —— 这不是模型能替你解决的问题。
- **小模型"finicky"是官方自陈的**。Needle 文档里原话："Small models can be finicky —— we encourage you to test on your own tools via the playground and finetune accordingly." 微调几乎是必选项，不是可选项。
- **非因果编码器 = 不能流式**。想要实时边说边出字的低延迟字幕场景，Whistle 的结构决定它做不了真正的流式，只能做"VAD 切句 + 逐句识别"的准流式。
- **Apache 2.0 权重 vs 源码可得的引擎**。Whistle 权重在 Hugging Face 上，但引擎（Cactus Engine）是"source-available license"，不是标准开源。对商业部署而言，许可条款需要单独审视 —— 这是一个容易在评估阶段被忽略的坑。

---

## 八、对开发者意味着什么

如果你在做端侧语音相关的产品，Whistle 给出了一个此前不存在的选项组合：**16.9 MB 的体积 + ~11 ms 的首 token + 零依赖的 CPU 推理 + 一次调用直达工具调用**。

落地时的建议：

1. **先在你的真实音频上跑 `needle whistle compare`**，让 Whistle / Whisper / Moonshine 在同一段录音上并排跑 WER 与耗时。官方跑分只覆盖七种欧洲语言的标准数据集，你的场景（口音、噪声、专业术语）未必落在那条曲线里。
2. **把关键词偏置当成产品功能来用**。设备名、人名、命令词，用 `keywords=[...]` 注入，比重新训练一个模型便宜得多。这是 Aho-Corasick 偏置最实际的用途。
3. **如果做的是指令类场景**（智能家居、车机、可穿戴），直接用"语音 + 工具调用"的合体模式，跳过中间文本；如果是转录类场景（会议记录、字幕），老实承认 30 秒上限，在 VAD 层做繁重工作。
4. **别把它当成 Whisper 的替代品**，把它当成 Whisper 在端侧的一个"窄而深"的新分支 —— 在它擅长的契约内，它是所有方案里最省的；越出契约，换回 Whisper。

从更大的图景看，Whistle 是 2026 年端侧 AI 叙事里一个清晰的坐标：**大模型的军备竞赛在云端继续，而端侧的战争是关于"取消 FFN、共享引擎、把中间表示藏进内核"的战争。** 当一个 16.9 MB 的文件能在微控制器上把语音变成结构化的工具调用，真正被重新定义的，是"什么才算一个模型"。

---

**参考来源**

- Whistle: Speech to Text in 16.9 MB — cactuscompute.com/blog/whistle
- We Distilled Gemini Tool Calling into a 26M Model（Needle）— cactuscompute.com/blog/needle
- Hacker News 前页（2026-10-08 讨论，474 points）
- 权重：huggingface.co/Cactus-Compute/whistle；引擎：huggingface.co/Cactus-Compute/needle3；源码：github.com/cactus-compute/needle
