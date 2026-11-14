# 13 万颗星之后，llama.cpp 才敢叫 1.0：一次「把 API 当合同」的发布

2026 年 11 月 13 日，`ggml-org/llama.cpp` 打了 `v1.0.0` 标签。同一天发布 `ggml v1.0.0`。

Hacker News 上这条消息拿到 20 分、2 条评论。同一时刻的首页被 FAA 全国停飞（1081 分）、逆向工程 Air Purifier（654 分）、哥德尔手稿被 AI 解锁（302 分）占满。按热度算，这是 llama.cpp 三年来最不起眼的一天。

但那 20 分背后是：134,873 个 star、25,574 次 fork、约 12.4 万次提交、2,239 位贡献者（含匿名）、177 个模型架构实现文件、8 条正式分发渠道。这样一个项目，三年半里始终只有 `master` 和 nightly build（`b12194` 这类 tag 一天出几十个），从来没有一个"可以 pin 住"的版本号。

所以 v1.0.0 的新闻稿写得极其克制——没有新模型的首发、没有 benchmark 屠榜、没有 demo 视频。它的正文第一段是这么说的：

> "Every new integration means more developers depending on our library interfaces and therefore having a flexible but stable API is paramount. Today we release libraries v1.0.0, highlighting our responsibility to those developers."

翻译过来：**我们过去是在给自己写代码，现在是在给你们写库。**

这句话比任何功能都重。本文要拆的是：一次"没有功能"的 1.0 发布，为什么是本地 AI 生态真正的分水岭；以及当推理引擎开始认真对待 semver 时，它必须同时解决哪些工程问题——ABI、模型架构爆炸、KV cache 的数值格式、MoE 专家卸载、以及一个本地 HTTP server 突然变成攻击面之后的账。

---

## 一、先把数据摆出来：这不是一个"项目"，这是一个基础设施

| 指标 | 数值 | 备注 |
|---|---|---|
| Stars | 134,873 | 2026-11-13 抓取 |
| Forks | 25,574 | |
| 贡献者 | 2,239（含匿名） | GitHub contributors API 分页上限推算 |
| 提交数 | ≈123,700 | commits 分页 12,374 页 × 10 |
| 仓库创建 | 2023-03-10 | 距今约 1,345 天 |
| 平均提交 | ≈92 次/天 | 三年半连续 |
| 模型架构实现 | 177 个 `.cpp` 文件（`src/models/`） | 官方口径"150+ 架构变体" |
| 分发渠道 | 8 条 | Docker / Debian / Homebrew / conda-forge / MacPorts / Winget / XCFramework / 预编译包 |
| 本次移除的废弃 API | 35 个函数 + `llama_set_warmup` + `defrag_thold` | PR #30565 |

平均每天 92 次提交，连续 1,345 天。这个数字需要放在对照系里才有意义：Linux 内核在合并窗口期的日均提交量是三位数，但那是全球数千名全职内核开发者；llama.cpp 是一个 MIT 许可、无公司编制、靠 Hugging Face 团队 + 社区维护的推理引擎。

再看下游。这一层才是 1.0 的真正理由：

- `ollama/ollama`：186,895 stars，历史上长期直接复用 llama.cpp 的 ggml 后端与模型加载路径；
- `nomic-ai/gpt4all`：77,346 stars；
- `abetlen/llama-cpp-python`：10,676 stars，几乎所有 Python 侧的本地推理 demo 都从它开始；
- `lmstudio-ai/lms`：5,425 stars，闭源产品的 CLI 外壳。

四个下游加起来接近 28 万 star。它们的共同点是：都把 `libllama` 的 C 头文件当成"事实标准"在用，而那个头文件三年半里从没承诺过稳定性。`llama_set_warmup` 这类函数今天存在、明天被标记 deprecated、后天消失，下游只能靠读 diff 活着。

这就是 1.0 要解决的问题，而且它是**社会问题**，不是技术问题。

---

## 二、v1.0.0 到底改了什么：一次"收口"

把 release notes 按"是否影响下游"重排，会看到一个非常清晰的形状：功能改动很多，但 API 改动只有五条，且全部指向同一个方向——**把实验区的东西收进主头文件，把主头文件里的历史包袱扔出去**。

### 2.1 删掉的部分

```
llama.h: remove llama_set_warmup, 35 deprecated functions,
         defrag_thold and --defrag-thold   (#30565)
```

`llama_set_warmup` 是个典型的历史遗留：它的语义在不同后端上不一致，在 Metal 上近似 no-op，在 CUDA 上会触发一次真实的前向。这种函数留在公开头文件里，下游就会有人依赖它，而依赖它的代码在换硬件时行为会变。三年半的沉积，最后一次性清掉 35 个。

`defrag_thold` 更有意思。它是 KV cache 碎片整理阈值——一个纯内部启发式参数，被暴露成了 CLI flag 和 context 参数。删除它等于承认：**碎片整理的策略应该由引擎决定，不该由用户调参**。这是引擎成熟的一个明确信号：从"给你所有旋钮"变成"我们替你决定，只暴露有语义的接口"。

### 2.2 收进来的部分

```
llama.h: promote the NextN API from llama-ext.h,
         rename llama_set_embd_state_src -> llama_set_ctx_state_src  (#30565)
```

这是本次发布最重要的单条改动。`llama-ext.h` 是 llama.cpp 的"实验扩展头"，语义上是"以下内容随时可能变"。NextN（多 token 预测 / 推测解码的模型侧接口）在里面待了很久，被 Ollama、LM Studio 等下游用 `#include "llama-ext.h"` 的方式接进去。

把它提到 `llama.h`，意思是：**推测解码不再是实验特性，它是核心能力的一部分**。配套的 `llama_set_embd_state_src` → `llama_set_ctx_state_src` 重命名也不是修辞——`embd` 是 embedding 的缩写，而实际语义是"设置上下文状态来源"，旧名字在接入视觉/音频子上下文时会误导人。

### 2.3 多模态的合并

```
mtmd: remove clip.h, consolidate model/subcontext infra into mtmd  (#31865)
```

`clip.h` 是 CLIP 视觉编码器的入口，属于"单模态时代"的设计。本次直接删掉，把视觉、音频、语音生成的子上下文统一到 `mtmd`（multi-modal）命名空间下，并让多个子上下文共享同一块 compute buffer（#31945）。

这条改动的外部可见度很低，但它是 ABI 层面的重活：删一个公开头文件，所有 `#include "clip.h"` 的下游都会编译失败。放在 1.0 做，是因为**只能在这个时间点做**——1.0 之后再删，就是 2.0。

### 2.4 一张表看清"1.0 的语义"

官方给出的 semver 规则表值得逐行读：

| 变更类型 | 版本位 | 官方定义 |
|---|---|---|
| MAJOR | 破坏 `./include` 下的公开 C API | |
| MINOR | 向后兼容的功能、后端更新、**模型支持**、API 新增 | |
| PATCH | 无 API 变更的修复 | |

第三行的"模型支持 = MINOR"是整个表格里最不标准、也最关键的一行。

按教科书 semver，新增对 Kimi-K3.1-Pro 的支持应该算 feature，确实是 MINOR。但 llama.cpp 一年新增几十个架构（本次一口气加了 Kimi-K3.1-Pro、Ripple-65B-Preview、xing4_0、drama-3 TTS、MageVL-Cowork、Kimi-K3.1 vision），如果每次都是 MINOR，版本号会以周为单位跳。他们还是这么定了——因为对下游来说，**"我的引擎能跑新模型了"和"我的代码不用改"是两件必须分开的事**。

这条规则实际上是在说：在这个项目里，模型覆盖度是产品指标，API 是契约。产品可以每周变，契约不行。

---

## 三、为什么 ABI 比 API 难十倍

大部分"1.0 发布"讨论的是函数签名。llama.cpp 的情况要复杂一层：它的公开面不止 `llama.h`，还有 `ggml.h`——一个张量库的 C API，而且是**被动态加载的后端**共用的。

### 3.1 后端是运行时加载的 `.so`

ggml 的架构是：核心库 `libggml` + 一组后端动态库（CPU、CUDA、Metal、Vulkan、HIP、SYCL、OpenCL、RPC……）。每个后端编译成独立动态库，在运行时按可用性加载。博客原文：

> "Each backend can be compiled as a dynamic library and optionally loaded at runtime."

这句话的含义是：**后端和核心的边界是一条 ABI 边界，不是一条源码边界**。用户装的是预编译二进制（Homebrew、Debian、winget），他升级核心库但没升级 CUDA 后端——这时如果 `ggml_tensor` 的结构体布局变了，程序不会编译失败，它会段错误。

这是 C 库最经典的陷阱，也是为什么 glibc 至今不敢动 `struct stat`。llama.cpp 在 1.0 之前，这条边界是靠"nightly 一起发、一起装"来规避的：反正大家都是同一天的 build。

一旦进了 Debian stable 和 conda-forge，这个前提就消失了。发行版会把 `libggml` 和后端库分开打包、分别升级、分别被不同包的依赖约束。所以 1.0 的必要前提不是"代码写好了"，而是"分发渠道要求你不能随便动结构体"。

### 3.2 具体的 ABI 风险点在本次发布里长什么样

本次有两条改动直接踩在这条线上：

**第一条：`llama_context_params` 新增字段。**

```
llama.h: add moe_cache_size and moe_cache_cpu_share
         to llama_context_params  (#30966)
```

`llama_context_params` 是值传递结构体。往中间插字段 = 破坏 ABI；往末尾加字段 = 仍然破坏 ABI（在老调用方眼里结构体大小变了，栈上布局错位）。标准解法是"保留字段 + setter 函数"或"版本化结构体"。llama.cpp 的处理方式是：这是一个 MAJOR 版本，所以可以直接加。

**第二条：`mtmd_helper_gen_audio_inp` 增加 `temp` 参数。**

```
mtmd.h: add MTMD_GEN_AUDIO_TYPE_DRAMA3
        and temp in mtmd_helper_gen_audio_inp  (#31613, #31655)
```

改函数签名，同样是 MAJOR-only 的操作。这两条如果分散在 0.9.x 的 PATCH 里，下游会在某次 `apt upgrade` 之后静默崩溃。放在 1.0.0 一次性做掉，是最省社会成本的选择。

### 3.3 所以 1.0 的真实内容是一份"债务清单"

把上面拼起来看，v1.0.0 干的事其实是：

1. 把三年半积累的 API 债务（35 个废弃函数、`llama_set_warmup`、`defrag_thold`、`clip.h`）一次性还清；
2. 把已经被下游事实依赖的实验 API（NextN）转正；
3. 承诺从此以后，破坏性变更只发生在 MAJOR。

这三件事没有一件能靠"写得更好"完成，它们全是协调工作。这也是为什么发布博客里出现了这么一段几乎不像技术博客的话：

> "We expect this trend to continue as local AI and privacy become increasingly important in our everyday lives."

把"隐私"和"API 稳定性"放在同一个句子里，逻辑是通的：**隐私要求本地部署，本地部署要求能长期维护，长期维护要求版本可锁定**。一个每天变 92 次的 master 分支，企业 IT 部门没法审批。

---

## 四、177 个 `.cpp` 文件：模型架构爆炸下的工程经济学

`src/models/` 下有 177 个文件：`afmoe.cpp`、`apertus.cpp`、`arcee.cpp`、`arctic.cpp`、`arwkv7.cpp`、`baichuan.cpp`、`bailingmoe.cpp`……一个架构一个文件，按字母序排下来像一本模型族谱。

官方口径是"150+ 架构变体"。这个数字本身就是 llama.cpp 最被低估的资产——它意味着无论社区今天出了什么奇怪的结构（线性注意力、mHC、DSA、MLA、MoE 路由、MTP），两周内大概率能在 llama.cpp 上跑起来。

### 4.1 这个架构是怎么长出来的

关键设计是：**模型实现和推理引擎解耦**。一个架构文件只做三件事——定义超参、把 GGUF 里的张量映射到 ggml 张量、构建计算图。采样、KV cache、批处理、后端调度全在核心层。

这套设计的好处在这个 PR 里体现得最干净：

```
Ripple-65B-Preview (ricursive): new dense 65B architecture, no new ops  (#31692)
```

"no new ops" 是关键词。一个 65B 的稠密模型，接入成本是"零新算子"——只用已有的 ggml op 拼出图。这意味着新架构的接入成本从"实现 CUDA kernel"降到了"写一个图构建函数"。

对比一下：如果你想在某个自研引擎里加一个新架构，通常要动 kernel、动内存规划、动量化表。llama.cpp 把这三件事都挡在了架构文件之外。

### 4.2 代价：样板代码与 CI 矩阵

这套架构不是免费的。177 个文件里有大量重复：

- 每个架构都要写一遍 `load_arch_tensors`，把 GGUF 的命名约定映射到内部命名；
- 每个架构都要声明 `build_arch_graph`，即使 90% 的图结构和 LLaMA 一样；
- RoPE 的实现本次被重构为 per-model `build_rope`（#31683），原因正是"每个模型对 RoPE 的变体处理不一样，共享实现反而更难维护"。

这是典型的"复制优于抽象"策略。在 177 个变体、每周新增 1-2 个的现实下，抽象层的维护成本会超过复制成本。代价是核心层的每次重构（比如本次把 model 变成 `llm_graph_context` 的成员，#31733）都要扫一遍全部 177 个文件。

CI 是另一个代价。博客里专门提到：

> "Thanks to HF technologies such as HF Buckets and HF Jobs we are able to scale the capacity necessary to guarantee correctness for every change that lands on the master branches. With hardware support from NVIDIA, AMD, Qualcomm, Arm, IBM and Intel, we continue to enroll more self-hosted runners across all major hardware platforms."

六个硬件厂商 + 每条 master 提交都要跑正确性验证。这是"每天 92 次提交"能成立的唯一原因：没有这套 CI，177 个架构 × 8 个后端 = 1,416 种组合，人工回归是不可能的。

一个可验证的推论：llama.cpp 的真实护城河不是性能，是**这张 CI 矩阵**。任何新玩家想追，第一年要花的钱不在算法，在自建 runner 机房。

---

## 五、三条性能主线：把"显存不够"拆成三个可算的账

1.0 的性能改动集中在三处：FP8 KV cache、MoE 专家缓存、PLE 分片外挂。它们的共同思路是**把"模型太大"这个笼统的抱怨，拆成三个可以分别定价的资源问题**。

### 5.1 FP8 KV cache：省的不是算力，是带宽

```
FP8 KV caches (-ctk/-ctv f8_e4m3) with optional
static per-tensor scales  (#28392)
```

先算一笔账。以一个 64 层、8 个 KV head、head_dim=128 的 GQA 模型为例：

- 每 token 每层 KV 元素数 = 2（K 和 V）× 8 × 128 = 2,048
- 全模型每 token = 2,048 × 64 = 131,072 个元素
- FP16 存储 = 256 KB/token
- 32K 上下文 ≈ **8 GB**
- FP8 存储 = **4 GB**

32K 上下文省 4 GB，在 24 GB 消费级卡上就是"能不能再开一个并发请求"的区别。

但真正重要的不是容量，是**解码阶段的内存带宽**。自回归解码每生成一个 token，都要把整个 KV cache 读一遍（attention 需要全部历史 K/V）。这是纯带宽操作，算力利用率通常只有个位数百分比。

FP8 把这次读取的字节数减半，等于在同样的 HBM 带宽下把解码吞吐往上抬。这解释了为什么 KV cache 量化在 2025—2026 年成了推理引擎的标配竞争点：它不改变模型质量的上限，只改变带宽的换算率。

`f8_e4m3` 是 OCP（Open Compute Project）的 8 位浮点格式：4 位指数、3 位尾数、无符号位偏移。选它而不是 `e5m2`，是因为 KV 值的动态范围远小于梯度，精度比范围更值钱。配套的"optional static per-tensor scales"是工程细节里最有含量的一条：per-tensor 静态 scale 意味着**校准时算一次、推理时零开销**，而不是 per-token 动态量化（那要在 kernel 里做归约，反而拖慢）。

一个常被忽略的坑：本次同时修了"量化 KV cache 的设备端状态拷贝大小"（#30541）。这类 bug 只在**混合精度**（一部分层 FP16、一部分 FP8）时暴露，症状是上下文切换后输出漂移。它说明 FP8 KV 不是"打开一个 flag"，它牵着 KV 状态管理、checkpoint、slot 复用一整套机制。

### 5.2 MoE 专家缓存：把"稀疏"变成"可预测的稀疏"

```
MoE cache: CPU share for misses, LRFU/ClassLRU replacement,
           no CPU wait on cached experts  (#30966, #31233, #31888)
```

MoE 的诱惑是"激活参数少"，陷阱是"总参数还是得放得下"。一个 200B-A20B 的模型，权重 200B，显存装不下，只能把专家放 CPU 内存，按需搬运。

朴素做法是每次路由到某个专家就从 CPU 拷到 GPU——PCIe 4.0 x16 单向约 25 GB/s，拷一个 100 MB 的专家要 4 ms，而这 4 ms 里 GPU 完全空转。解码一个 token 要过几十层，每层 top-k 路由，累加起来就是灾难。

llama.cpp 的三步走是标准的缓存工程：

1. **专家级缓存 + 可配置 CPU 份额**（`moe_cache_cpu_share`）：GPU 上留固定数量的专家槽位，其余放 CPU 内存。槽位数和 CPU 份额都是 `llama_context_params` 的新字段。
2. **LRFU / ClassLRU 替换策略**（#31233）：LRFU（Least Recently/Frequently Used）混合了"最近用过"和"用得频繁"两个信号。为什么不能用纯 LRU？因为 MoE 路由有**层间相关性**——某类 token（比如代码里的运算符）会稳定地激活同一批专家，纯 LRU 会被一次性长尾请求污染。
3. **命中时不等待 CPU**（#31888）：这是最关键的一条优化。如果专家已在缓存里，就不要让 CPU 参与同步——把"查表"和"搬运"解耦，避免为了判断"要不要拷"而引入一次主机同步。

`ClassLRU` 里的 "Class" 指的是按专家类别分组。这在有 shared expert（共享专家，如 DeepSeek 系列）的架构里很重要：shared expert 永远命中，不该占用可替换槽位的统计口径。

### 5.3 PLE 分片：把 embedding 当可换零件

```
external PLE/engram loading from separate GGUF shards
via --shard / --ple  (#31185)
```

PLE（Per-Layer Embedding）是 Gemma 系列引入的结构：除了输入层的 token embedding，每一层还有自己的一份 embedding 表。它的好处是"用查表代替一部分计算"，坏处是**参数量爆炸且访问局部性极好**——每个 token 只用一行。

这类张量的最优存储位置不是显存，是 NVMe。`--shard` / `--ple` 允许把 PLE/engram 拆成独立的 GGUF 分片，按需 mmap。配合本次的 "Windows unbuffered model load, mirroring the Linux DirectIO path"（#26014），llama.cpp 实际上在做一件很明确的事：**把模型权重按访问模式分层**——热权重进显存，冷权重走 page cache，超大查表走 DirectIO 绕过 page cache。

这三条线拼起来，是同一个判断：2026 年的本地推理瓶颈已经不是 FLOPs，而是**显存容量 × 带宽 × 访问模式**的三维约束。引擎的竞争力在于能不能把模型拆得足够细，然后分别放到对的介质上。

---

## 六、`llama-server` 从 demo 变成攻击面

本次发布里最容易被略过、但我认为最重要的一组改动，是安全。

```
security: add --allow-unauthenticated-tools and
          --media-allow-private-urls opt-ins  (#32113, #32115)
security: fix --cors-origins, DNS rebinding, CORS proxy SSRF
          and child instance access  (#32098, #32115, #32120)
restrict the HF_TOKEN to huggingface.co hosts  (#31730)
cancel MCP tool calls on client disconnect or timeout  (#32025)
```

### 6.1 威胁模型变了

2023 年的 `llama-server` 是个"在自己机器上跑个 demo"的工具，`--host 0.0.0.0` 被写在无数教程里。2026 年的 `llama-server` 是什么？

- 一个 OpenAI 兼容的 HTTP API（`/v1/chat/completions`、`/v1/audio/speech`）；
- 一个 MCP 客户端（会去调用外部工具）；
- 一个会主动抓取远程 URL 的媒体加载器（图片、音频输入）；
- 一个带 Web UI 的单页应用，默认监听本地端口。

这四条加起来，等于把一个**带内网访问权限的代理**放在了用户机器上。而它的默认部署位置，通常是 `localhost`。

### 6.2 DNS rebinding：为什么"只监听 127.0.0.1"不够

本地服务的传统安慰是"我只绑 127.0.0.1，外网打不到"。DNS rebinding 让这个安慰失效：

1. 用户访问 `evil.example`，页面里的 JS 开始请求 `http://attacker-controlled-domain:8080`；
2. 该域名的 DNS TTL 设为 0，第一次解析返回攻击者 IP（页面加载成功，同源建立）；
3. 随后重新解析，返回 `127.0.0.1`；
4. 浏览器认为仍是同源，于是 JS 可以读 `http://attacker-controlled-domain:8080/v1/chat/completions` —— 实际打到的是用户本机的 llama-server。

防御的关键不是绑地址，是**校验 `Host` 头**（只接受 `localhost` / `127.0.0.1` / 明确配置的域名）。本次修复里 `--cors-origins`、DNS rebinding、CORS proxy SSRF 被列在同一行，因为它们本质是同一个洞的三张脸：**浏览器可以用你的本地 server 当跳板**。

### 6.3 两个新 flag 的语义：默认安全

`--allow-unauthenticated-tools` 和 `--media-allow-private-urls` 这两个 flag 名字起得很讲究——它们是**opt-in**，也就是说默认行为变成了"拒绝"。

- `--media-allow-private-urls`：默认拒绝加载指向私有网段（10/8、172.16/12、192.168/16、169.254/16、::1）的媒体 URL。这挡住的是 SSRF：让 server 去抓 `http://169.254.169.254/latest/meta-data/`（云厂商元数据服务）或内网管理面板。
- `--allow-unauthenticated-tools`：默认要求 MCP 工具调用必须来自已认证的客户端。这挡住的是"任何本机进程都能驱动你的 agent 去执行工具"。

这两条改动的深层含义是：**llama.cpp 承认自己现在跑在别人的生产环境里了**。一个 demo 不需要这些 flag；一个要进企业内网的东西必须有。

### 6.4 `HF_TOKEN` 的作用域收敛

```
restrict the HF_TOKEN to huggingface.co hosts  (#31730)
```

这条看起来最小，其实最典型。`HF_TOKEN` 是一个有写权限的 Hugging Face 凭据。原来的实现里，任何走 HTTP 客户端的路径（包括用户可控的模型下载 URL）都可能带上这个 header。一旦有人构造一个 `--model https://evil.example/x.gguf`，token 就泄露了。

修复方式是把它绑到 host 白名单。这是一个**凭据作用域**问题，和浏览器 cookie 的 `Domain` 属性、OAuth 的 `audience` 是同一类设计。它出现在推理引擎里，说明引擎已经复杂到需要做凭据管理了。

顺带说一句 MCP：`cancel MCP tool calls on client disconnect or timeout`（#32025）不是安全修复，是资源泄漏修复——客户端断开后工具调用还在跑，会一直占着后端。这条和上面几条放在一起，勾出的是同一个事实：**agent 时代的推理引擎不只是推理引擎，它是工具调用的运行时**。

---

## 七、分发即承诺：为什么 8 条渠道比 8 个功能重要

官方列出的分发渠道：

| 渠道 | 平台 | 谁在用 |
|---|---|---|
| Pre-release artifacts | Linux / macOS / Windows / Android / iOS | 尝鲜者、CI |
| Docker | Linux | 服务端、K8s |
| Debian | Linux | 发行版、企业镜像 |
| Homebrew | macOS / Linux | 开发者 |
| conda-forge | Windows / macOS / Linux | 数据科学、Python 生态 |
| MacPorts | macOS | 老派 Mac 用户 |
| Winget | Windows | 企业 Windows 部署 |
| XCFramework | iOS / macOS | App Store 应用 |

八条渠道，八个"必须长期兼容"的承诺。

这不是修辞。**一旦你的包进了 Debian stable，你的 ABI 就被冻住了**：stable 的生命周期是 2—5 年，期间发行版只会打安全补丁，不会跟着你跳 MAJOR。如果你的 `libggml` 在 stable 周期内改了结构体布局，整个发行版的依赖树都会崩。

同理，conda-forge 的包由社区维护者构建，他们的构建节奏和上游不同步；XCFramework 会被嵌进 App Store 应用，用户手机上的旧版本可能一两年不更新。

所以正确的因果链是：

> **分发渠道的存在，倒逼出版本契约；版本契约的存在，倒逼出 1.0。**

不是"我们成熟了所以发 1.0"，而是"我们已经进了八个包管理器，所以不得不发 1.0"。

博客里还有一句配套的话，指向同一个方向：

> "We are looking forward to expanding the ways in which ggml-org software is distributed... please check the following discussion."

那个 discussion（`ggml#1579`）是给打包者看的接入指南。一个开源项目开始维护"打包者文档"，说明它的用户画像已经从"clone 下来自己编译的开发者"变成了"用包管理器装二进制的终端用户"。这两类人的需求完全相反：前者要最新 master，后者要五年不变。

---

## 八、对生态的实际影响：pin 住，还是继续跟 nightly

### 8.1 下游终于可以写 `>=1.0,<2.0`

在此之前，下游的依赖声明只有三种写法，全都不好用：

- 依赖 git commit hash：能复现，但每次上游修复 bug 都要手动 bump；
- 依赖 nightly 日期：脆弱，且 nightly 不保证任何东西；
- 不 pin：某天上游删了 `llama_set_warmup`，你的构建挂了。

1.0 之后可以写：

```
# llama-cpp-python 这类绑定层
llama.cpp >= 1.0.0, < 2.0.0
```

这里有个容易踩的坑：**应该 pin MINOR，不要 pin PATCH**。按官方规则，MINOR 包含"后端更新和模型支持"，PATCH 只修 bug 不改 API。所以合理策略是：

- 应用层：`~=1.0`（允许 1.x，不允许 2.0）；
- 库/绑定层：pin 到 `1.0.*`，因为你要对着具体头文件做绑定生成；
- 分发打包：pin 到精确版本 + 后端库同版本，绝不能核心 1.0.1 配后端 1.0.0。

### 8.2 一个真实的风险：nightly 文化与 semver 文化的冲突

llama.cpp 的开发文化是"每天 92 次提交、几十个 nightly build"。这个文化造就了它的模型覆盖速度，但它和 semver 是天然冲突的：

- semver 要求"破坏性变更集中到 MAJOR"，意味着**想删一个废弃函数，可能要等半年**；
- nightly 文化要求"发现不对立刻改"，包括改 API。

1.0 之后的现实会是：`master` 依然每天变，但 `v1.x` 分支的维护成本会上升。官方目前的做法是"MAJOR 才破坏"，没有承诺维护 LTS 分支。这意味着 2.0 发布时，1.x 不会有人给你打补丁。

对企业用户的建议很直接：**不要指望 llama.cpp 提供 LTS。要稳定，就自己 fork 一个 tag 自己维护。** 这听起来不友好，但它是 MIT 项目的常态——稳定性由使用者购买，不由上游赠予。

### 8.3 对竞争格局的影响

把 llama.cpp 和 vLLM（96,875 stars）放在一起看，分野已经很清楚了：

- vLLM 的目标是**吞吐**：PagedAttention、连续批处理、张量并行，服务的是"一张 A100 要跑多少 QPS"；
- llama.cpp 的目标是**覆盖**：177 个架构、8 个后端、8 条分发渠道、能在 Android 手机和 Apple Watch 级别的内存里跑。

1.0 之后，这个分野会固化。因为 1.0 承诺的是"接口稳定"，而接口稳定只有在"下游很多、部署环境很杂"的场景下才有价值。vLLM 的下游是集群运维，llama.cpp 的下游是几十万个桌面应用。

换句话说：**llama.cpp 的竞争对手不是 vLLM，是"每个应用自己写一个推理层"这件事。** 1.0 就是在告诉那些应用：别自己写了，我这层不会塌。

---

## 九、结论：1.0 的意思是"地基不再移动"

回头看这次发布，功能清单其实很扎实：Kimi-K3.1-Pro 的 DSA 替换、Ripple-65B 的零新算子接入、drama-3 TTS、`/v1/audio/speech` 端点、全新的 Web UI（聊天分组、Markdown 编辑器、移动端原生布局）。

但这些都不是重点。重点是三句话：

1. **`llama.h` 从此是合同。** 破坏它要付 MAJOR 的代价，这条规则改变了所有下游的决策方式——从"跟 master"变成"选版本"。
2. **模型覆盖度被正式定义为 MINOR。** 这是一个 LLM 时代特有的 semver 解释：架构会继续爆炸，但爆炸不应该震动 API。
3. **安全默认值反转了。** `--allow-unauthenticated-tools`、`--media-allow-private-urls` 都是 opt-in，说明项目接受了"我跑在别人的生产环境里"这个事实。

如果你只想要一个行动建议：

- **应用开发者**：把 llama.cpp 从 git submodule 换成 `>=1.0,<2.0`，然后把后端库和核心库锁在同一版本。这一步能省掉未来两年的构建事故。
- **服务端部署者**：升级后立刻检查你的 `--host` 和 CORS 配置。如果你的 `llama-server` 曾经用 `--host 0.0.0.0` 暴露过，默认安全值反转反而可能让你的旧脚本失效——但它失效的方式是"拒绝"，不是"静默放行"，这是好的失效方向。
- **观察者**：把 1.0 当作一个信号——本地 AI 的竞争维度已经从"能不能跑"转向"能不能被依赖"。下一个战场是 ABI 稳定性、后端覆盖广度，以及"你的引擎能不能进 Debian"。

三年半，12 万次提交，2,239 个人，134,873 颗星，最后换来一个版本号从 `b12359` 变成 `v1.0.0`。

对一个基础设施项目来说，这是最高级别的成就：**它终于无聊到可以被人信任了。**

---

**参考来源**

- llama.cpp v1.0.0 Release Notes：`https://github.com/ggml-org/llama.cpp/releases/tag/v1.0.0`
- 官方博客《llama.cpp v1.0.0: A stronger foundation for the local AI ecosystem》：`https://huggingface.co/blog/ggml-org/llama-cpp-v1`
- GitHub API 数据（stars / forks / contributors / commits / releases），2026-11-13 抓取
- 打包接入讨论：`https://github.com/ggml-org/ggml/discussions/1579`
- semver 规范：`https://semver.org`
