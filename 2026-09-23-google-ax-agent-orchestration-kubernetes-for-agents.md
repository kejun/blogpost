# 当 Agent 有了自己的"Kubernetes"：Google AX 单日 2300 星背后的 Agent 运行时战争

> 2026-09-23 · AI技术 · 本文约 4600 字

## K8s 老兵们的"二次创业"

9 月 23 日的 GitHub Trending 第一名，是一个叫 `google/ax` 的 Go 仓库：**7,556 stars、352 forks、单日新增 2,305 星**。仓库简介只有一句话——"Google's open agentic orchestration runtime"（Google 的开放 Agent 编排运行时）。

比星数更值得注意的是贡献者名单。往下翻它的底层依赖项目 `agent-substrate/substrate`（2,957 星，同日 +245），你会看到几个 Kubernetes 圈的老面孔：**thockin（Tim Hockin，Kubernetes 联合创始人）**、**BenTheElder（Ben Elder，K8s 发布负责人）**，以及 ax 仓库里的 **rakyll（Jaana Dogan，前 Go 团队核心成员）**。这批人当年定义了"容器怎么被编排"，现在他们在定义"Agent 怎么被编排"。

Google Cloud 官方博客同日发布了对应的产品化叙事——**Agent Executor（AX）**，定位是"Google 的开源 Agent 执行、恢复与分布式部署运行时标准"。注意用词：**runtime standard**。这不是又一个 Agent 框架，而是 Google 对"Agent 执行层标准席位"的公开争夺。

核心数据一览：

| 维度 | 数据 |
|------|------|
| Stars / Forks | google/ax：7,556 / 352（单日 +2,305）；agent-substrate/substrate：2,957 / 383 |
| 语言 / 许可 | Go / Apache 2.0 |
| 一句话定位 | 声明式 Agent 编排器：沙箱化、工作区预装、网络围栏、集群级规模化运行 |
| 底层运行时 | Agent Substrate（gVisor/microVM，actor-worker 多路复用） |
| 状态存储 | Redis（Hashes + Streams + PubSub），刻意绕开 etcd |
| 性能指标 | resume < 500ms、500+ 次/秒挂起恢复、10x 容器运行时密度 |
| CLI 形态 | kubectl-shaped：apply / get / watch / describe / delete + suspend / resume / ssh |
| 成熟度 | v1alpha1，官方明示"稳定版前会有重大破坏性变更" |

为什么这个项目值得认真拆？因为它正面回答了一个所有做 Agent 平台的人都在撞墙的问题：**Agent 到底是一种什么工作负载（workload），现有的基础设施为什么接不住它？**

## Agent：既不是微服务，也不是批处理任务

AX README 里有一段话，值得每个基础设施工程师抄下来：

> "Agents are a new kind of workload. They are neither stateless microservices nor run-to-completion batch jobs. They accumulate state, need strict isolation, call out to model APIs and tool servers, and can burn money in a loop if nobody is watching."
>
> （Agent 是一种新型工作负载。它们既不是无状态微服务，也不是跑完即走的批处理任务。它们积累状态、需要严格隔离、会调用模型 API 和工具服务器，而且如果没人盯着，它们能在死循环里把钱烧光。）

Google Cloud 博客补充了另一个精准的描述：**Agent 是"等待外部输入的非线性程序"（nonlinear programs that wait for external inputs）**。

把这三个特征展开，就能看清传统基础设施的每一处错位：

**第一，状态积累 vs. 无状态假设。** Kubernetes 的核心契约是"Pod 是牲口不是宠物"——随时杀掉、随时重建。但一个跑了 6 小时的编码 Agent，它的文件系统改动、对话上下文、中间产物都是不可再生的状态。杀掉重建意味着 6 小时白干。

**第二，等待输入 vs. 常驻占用。** Agent 的生命周期里大部分时间在"等"：等 LLM 返回、等人工审批（HITL）、等外部 API。传统容器为等待付费——一个 8GB 内存的 Pod 挂着等人类点一下"确认"，成本全在空转。Agent Substrate 的设计文档直白地承认了这个前提："agent-like applications tend to be idle most of the time"（Agent 类应用大部分时间是空闲的），整个系统就是围绕这个空闲率做重度多路复用。

**第三，规模形态的倒置。** Kubernetes 控制面为"数千个长运行服务"优化；而 Agent 平台的真实负载是"数百万个亚秒级工具调用"——短命、高频、海量。用前者的控制面接后者的流量，撞墙是必然的。

**第四，烧钱循环的风险。** Agent 会自主决策，决策失误的代价不是 500 错误，而是真金白银的 token 消耗和不可逆的外部副作用。这要求隔离（isolation）和网络围栏（egress fencing）成为平台默认能力，而不是应用自觉。

AX 的答案是把这一切收敛成**四个声明式原语**——如果你用过 Kubernetes，这套东西会非常眼熟。

## 四个原语：Task、Workspace、Gateway、Model

看官方示例，一个完整的 Agent 任务就是一份 YAML：

```yaml
# task.yaml
apiVersion: ax.io/v1alpha1
kind: Workspace
metadata:
  name: golang
spec:
  git:
    - repo: https://github.com/golang/go.git
      branch: "my-fix"
---
apiVersion: ax.io/v1alpha1
kind: Task
metadata:
  name: test
spec:
  workspaces:
    - name: golang
  goal: "Ensure that Go tool chain is available and is built from source"
  debug: true # 允许 `ax ssh` 进入沙箱
```

然后三条命令完成部署、观察和"贴身监工"：

```bash
ax apply -f task.yaml
ax watch task test          # 实时流式观察状态迁移
ax ssh test -- ls -al /workspace   # 直接钻进 Agent 的沙箱看它在干嘛
```

四个原语各司其职：

| 原语 | 解决的问题 |
|------|-----------|
| **Task** | 在带 CPU/内存限额的隔离沙箱里运行不可信的 Agent 代码 |
| **Workspace** | 预装 Git 仓库、MCP 服务器、skill 包——让每个 Agent"热启动" |
| **Gateway** | 把出站流量锁死在显式的主机白名单上（egress allowlist） |
| **Model** | 声明平台自身使用的 LLM，凭据从 Kubernetes Secret 注入 |

外加两个专为 Agent 设计的动词：**`ax suspend` / `ax resume`**——把空闲的 Agent 挂起（checkpoint 全部状态），需要时在任意 worker 上精确恢复到中断点。

这套设计里最容易被低估的是 **Gateway**。当 Agent 能自主写代码、自主执行，"它能连到哪"就成了安全边界的核心问题——提示词注入攻击的标准套路就是诱导 Agent 向外发送数据。AX 把网络围栏做成声明式原语（默认白名单），等于把"数据外泄防御"从应用层下沉到了平台层。这和当年 Kubernetes NetworkPolicy 的思路一脉相承：**安全不能靠 Agent 自觉，要靠基础设施兜底。**

而 `ax ssh` 是一个信号：AX 的设计者深知 Agent 平台的调试有多痛。"看 Agent 在干什么"不应该靠日志猜，而应该能直接钻进沙箱围观。

## 架构深潜：为什么他们"背叛"了 etcd

AX 的 DESIGN.md 开头就抛出了一个对 Kubernetes 生态大不敬的判断：

> "Storing millions of short-lived tasks as Kubernetes CRDs pushes etcd past its comfort zone (single-digit GB storage limits, write-rate bottlenecks, control plane degradation)."
>
> （把数百万个短命任务存成 K8s CRD 会把 etcd 推出舒适区：个位数 GB 的存储上限、写速率瓶颈、控制面退化。）

这是所有"用 CRD 扩展 Kubernetes"的项目最终都会撞上的墙。etcd 是为强一致的配置存储设计的，不是为高频状态流设计的。一个 Agent 任务每秒可能产生多次状态变更，乘以百万级任务数，etcd 的 watch 机制和写路径会先于业务崩溃。

AX 的解法是"**保留 Kubernetes 的壳，替换 Kubernetes的心脏**"：

```
ax apply -f task.yaml
        │
        ▼
    ax-server（无状态 gRPC API）
        │  存储 & 发布事件
        ▼
    Redis（Task Hashes + Event Streams + PubSub）
        │  XREADGROUP（Streams 消费组）
        ▼
    ax-controller（水平扩展的调和控制器）
        │  gRPC（Control API）
        ▼
    Agent Substrate（Atespace 供给 / Actor 激活 / Worker 分配 / Egress 过滤）
```

分工非常清晰：

- **ax-server**：无状态 gRPC 入口，校验 manifest、写 Redis、发事件——可以任意水平扩展；
- **Redis**：状态存储 + 工作队列。用 Redis Streams 的消费组（XREADGROUP）做控制器之间的任务分发，天然支持 at-least-once 语义和消费者横向扩展；
- **ax-controller**：调和循环（reconciliation loop）worker——注意这个词，AX 保留了 Kubernetes 最精髓的声明式调和思想，只是把调和的状态源从 etcd 换成了 Redis；
- **ax-task-runner**：每个任务容器内的 entrypoint，负责工作区引导、元数据服务和 Agent 命令执行，自定义镜像可以直接嵌入这个 runner 包。

而 Kubernetes 本身并没有被抛弃——它退到了更擅长的位置：**节点供给、Pod 生命周期、自动扩缩容**。Agent Substrate 明确说明自己"leverages Kubernetes for infrastructure provisioning and worker lifecycle management"，Agent 级别的调度和控制则由自己的最小化控制面（minimal control plane）接管，"bypass some of the limitations of Kubernetes, without reinventing the rest of it"——绕过局限，但不重造其余部分。

这是一个值得学习的架构姿态：**不是"取代 K8s"，而是"在 K8s 之上再造一层为 Agent 而生的控制面"**。就像当年的 Istio 没有替换 Kubernetes，而是在其上补了服务网格层。

## Agent Substrate：actor/worker 多路复用的密度经济学

AX 负责"编排语义"，真正的脏活累活在底层的 **Agent Substrate**。它的核心抽象是一对概念：

- **Actor**：逻辑上的 Agent 实例（应用、Agent、工具、沙箱），数量可达数百万；
- **Worker**：物理上就绪的执行单元（K8s Pod），数量远小于 Actor。

系统把大量 Actor 映射到少量 Worker 上，赌的就是前面说的"Agent 大部分时间在空闲"。官方 Demo 的数据相当激进：**约 250 个有状态 Actor 跑在 8 个物理 Pod 上，30x+ 超额订阅**；整体宣称比标准容器运行时高 **10 倍密度**，挂起/恢复激活速率超过 **500 次/秒**，resume 延迟 **低于 500ms**。

支撑这个密度的是三件事：

**1. 全状态快照（Full-state Snapshotting）。** 挂起不是"杀进程存参数"，而是把易失内存（RAM）和文件系统状态完整快照。恢复时"State Persistence: Persistent working memory (volatile RAM) and filesystem state preserved perfectly across hibernation cycles"——连内存都原样保真。这意味着一个正在执行到一半的 Python 进程、一个开着的数据库连接池，都可以被冻结和迁移。

**2. Actor Teleport。** 恢复不要求回到原来的 Worker——快照可以被"传送"到池子里任意可用的 Worker 上激活。这解耦了 Actor 的身份和物理位置，是整个多路复用模型成立的前提。

**3. gVisor / microVM 双沙箱技术。** 隔离层面用 Google 自家 2018 年开源的 gVisor（用户态内核拦截 syscall）或 microVM，提供"zero-trust kernel and network isolation"。gVisor 这项技术在容器时代一直不温不火——性能损耗换来的安全边界对传统工作负载不够划算；但在"运行不可信 Agent 生成代码"的场景下，它的价值终于对上了号。**老技术找到了新场景，这是基础设施史上反复上演的桥段。**

还有一个容易被忽略的细节：Substrate 文档提到它支持"holistic infrastructure optimizations for RL scenarios that span agentic, inference and training cycles"——为跨越 Agent 执行、推理和训练循环的强化学习场景做整体优化。配合 AX 博客里的 **Trajectory Branching（轨迹分支）**能力——在任意 checkpoint 处分叉 Agent 的决策路径，不丢上下文地探索多条轨迹——你几乎可以确定：**这套基础设施同时也是为大规模 Agent RL 训练准备的**。评估一千条分支轨迹、从中筛选成功路径做训练数据，正是当前 Agent 能力提升的核心飞轮。

## 五大原语能力：Durable Execution 的"Agent 特化版"

Google Cloud 博客总结了 Agent Executor 的五项原生能力，每一项都对应一个生产环境的真实痛点：

| 能力 | 机制 | 解决的痛点 |
|------|------|-----------|
| **Durable execution** | 事件日志 + 快照 | 长任务在宕机或 HITL 中断后自动恢复 |
| **Secure isolation** | secure-by-design 沙箱 | Agent 生成代码/多租户数据的副作用隔离 |
| **Session consistency** | 单写者（single-writer）架构 | 分布式组件并发写共享会话状态导致的损坏 |
| **Connection recovery** | 重连 + 按客户端最后序列号回填 | 网络抖动后用户体验断裂 |
| **Trajectory branching** | checkpoint 分叉 | 不丢状态地探索/评估多条决策路径 |

其中 **Session consistency 的单写者架构**值得多说一句。做过分布式 Agent 的团队都知道，当规划器、工具执行器、记忆模块都可能更新同一份会话状态时，竞态条件是最大的隐性 bug 来源。AX 直接在运行时层面强制单写者，把一致性从"应用小心翼翼"变成"平台结构性保证"——这和数据库领域"把并发控制下沉到存储引擎"是同一个哲学。

而 **Connection recovery 的序列号回填**（backfills responses from the last sequence seen by the client）本质上是在 Agent 协议里内置了事件溯源（event sourcing）的客户端重放语义。长时运行的 Agent 会话动辄数小时，把"断线重连不丢消息"做成平台默认能力，等于把 IM 系统二十年攒下的可靠性经验一次性注入 Agent 基础设施。

熟悉 Temporal 的读者会看出这里的传承与差异：Temporal 把 durable execution 做成了通用工作流引擎，开发者需要用它的 SDK 重写业务逻辑；AX 则试图做到 **harness 无关**——你的 Agent 用 LangChain、LangGraph、ADK、Claude Code、Codex 还是 Antigravity 写的都无所谓，Substrate 在内核层管理标准 OCI 容器，durable execution 由平台注入而非 SDK 侵入。这是"运行时标准化"和"框架锁定"的路线之争。

## Google 的棋局：Agent 时代的"GKE 剧本"

把镜头拉远，这次发布的战略意图相当清晰。

**第一步，开源立标准。** AX（Apache 2.0）+ Agent Substrate 双仓库开源，CLI 刻意做成 kubectl 形态（apply/get/watch/describe），降低 Kubernetes 存量用户的迁移心智成本。官方明说："We're building Agent Executor in the open so we can validate the design in the hands of real developers."

**第二步，生态全兼容。** 博客列出的联邦对象几乎覆盖了 Agent 生态的所有派系：Google 自家的 Antigravity 2.0、Deep Research、Managed Agents API；社区主流的 LangChain/LangGraph、ADK；甚至跨厂商的 A2A 协议（Agent2Agent）。CNCF Sandbox 项目 kagent 已经宣布用 Substrate 运行沙箱化 Agent 负载。

**第三步，企业主权叙事。** 博客用整节篇幅强调 "Own your agents, models, and compute"：防厂商锁定、自带 harness、数据平面完全自控、数据驻留合规。这套话术精准打向对"Agent 全托管黑盒"心存疑虑的企业 CTO。

**第四步（没明说的），GKE 商业化。** Substrate 的快速上手路径深度绑定 GCP：快照依赖 GCS 和 Workload Identity，`go run ./tools/setup-gcp bootstrap` 一键拉起 GKE 集群。同期发布的还有 GKE 上的 Agent Sandbox 托管服务。这就是当年 Kubernetes 开源 + GKE 托管的剧本重演：**开源层建立标准和心智，托管层收割企业需求。**

竞争格局里，每个玩家的位置也因此更清楚了：

- **Temporal / Restate**：通用 durable workflow，Agent 无关，需要 SDK 侵入——AX 的差异化是"零改造接管任意 harness"；
- **E2B / Modal / Daytona**：托管代码沙箱，密度和冷启动是卖点——Substrate 用自托管 + 30x 超额订阅正面竞争成本曲线；
- **Cloudflare Agents / Workers**：边缘路线，Durable Object 做状态锚点——与 AX 的集群路线形成"边缘 vs. 中心"的对照；
- **kagent**：CNCF 生态的 K8s 原生 Agent 框架，选择骑在 Substrate 上而不是自建执行层——侧面验证了"执行层标准化"的吸引力。

## 冷静观察：alpha 就是 alpha

热度之外，几个事实必须放在台面上：

**1. 官方警告非常直白。** AX README 第一行就是 Warning："We will likely introduce major breaking changes prior to a stable release." Substrate 更是声明 "not ready for production use, APIs are almost guaranteed to change"，且明确标注 **不是 Google 官方支持的产品**、不在 Google 开源漏洞奖励计划范围内。现在 all-in 的团队要有推倒重来的心理准备。

**2. 运维门槛不低。** 你需要一个 Kubernetes 集群、ko 构建工具、容器镜像仓库、可达的 Substrate Control API，最顺滑的路径还深度绑定 GCP。对个人开发者和小团队，这不是"pip install 一下"就能玩的玩具——它瞄准的是平台工程团队和 Agent SaaS 提供商。

**3. Redis 单点问题没有展开讨论。** 把 etcd 换成 Redis 解决了写吞吐，但 Redis 的持久化语义（AOF/RDB）与 etcd 的 Raft 强一致不是一个量级。控制面状态丢失的爆炸半径有多大、如何做 HA，alpha 阶段的文档还没有给出生产级答案。

**4. "数十亿任务"的宣称未经第三方验证。** billions of tasks per cluster 是设计目标还是实测结果，目前没有公开数据。30x 超额订阅的 demo（250 actor / 8 pod）真实存在，但从 250 到 2.5 亿之间隔着无数个工程深渊。

但这些都不影响这个项目的信号价值：**单日 2,300+ 星说明社区对"Agent 专用基础设施"的渴求是真实的、迫切的。** 过去一年，Agent 框架层卷出了 LangGraph、CrewAI、AutoGen 的百花齐放；而现在，战火正在下移到执行层——Agent 到底跑在哪、状态存在哪、挂了怎么恢复、烧钱怎么熔断。框架决定 Agent 能多聪明，运行时决定 Agent 能多可靠、多便宜。**后者才是规模化的真正瓶颈。**

## 结语：工作负载定义基础设施，基础设施定义时代

回看计算史的每一次范式迁移，剧本惊人地相似：新工作负载出现 → 旧基础设施错位 → 新抽象层诞生 → 标准之争定胜负。虚拟机之于物理机，有了 VMware 和 Xen；容器之于虚拟机，有了 Kubernetes；Serverless 之于容器，有了 Lambda 和 Knative。

现在轮到 Agent。AX 和 Agent Substrate 押注的新抽象是：**Task/Workspace/Gateway/Model 四原语 + actor/worker 多路复用 + 全状态快照的 suspend/resume**。这套抽象会不会成为最终答案还两说——毕竟它自己都说 alpha 阶段什么都可能变。但方向大概率是对的：Agent 时代的"Pod"已经隐约可见，它不是一个常驻容器，而是一个**可以随时冻结、传送、分叉、复活的状态化进程**。

Tim Hockin 们从 Kubernetes 出发，正在给下一个十年的工作负载浇筑地基。上一次他们赢了。这一次，Temporal、Cloudflare、AWS 和整个开源生态都不会旁观。对开发者的实际建议是：**现在不用部署它，但一定要读懂它**——因为你未来两年要用的每一个 Agent 平台，几乎必然会长成它描述的这个样子，或者是对它的反驳。

---

**参考链接**

- google/ax GitHub 仓库：https://github.com/google/ax
- Agent Substrate 仓库：https://github.com/agent-substrate/substrate
- Google Cloud 官方博客《Agent Executor, Google's distributed Agent Runtime》：https://cloud.google.com/blog/products/ai-machine-learning/agent-executor-googles-distributed-agent-runtime
- AX 架构设计文档 DESIGN.md：https://github.com/google/ax/blob/main/DESIGN.md
- Hacker News 讨论（GitHub Trending，2026-09-22）
