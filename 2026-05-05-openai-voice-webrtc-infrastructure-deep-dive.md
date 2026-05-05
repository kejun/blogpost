# OpenAI 低延迟语音 AI 架构深度解析：WebRTC 如何支撑 9 亿周活的实时对话

**文档日期：** 2026 年 5 月 5 日  
**标签：** OpenAI, WebRTC, 低延迟架构, Voice AI, 实时媒体传输, Split Relay, Transceiver, Kubernetes, 基础设施

---

## 一、引言：当 AI 学会了"插话"

2026 年 5 月 4 日，OpenAI 官方技术博客发布了一篇工程长文——*How OpenAI delivers low-latency voice AI at scale*——详细披露了支撑 ChatGPT Voice 和 Realtime API 的 WebRTC 基础设施架构。文章在 Hacker News 上迅速冲上首页，获得超过 220 分和 87 条评论，引发了开发者社区的热烈讨论。

这篇文章之所以重要，不在于它披露了什么商业机密，而在于它是**少数几家顶级 AI 公司之一公开分享其实时媒体传输基础设施的完整架构设计**。

> **ChatGPT Voice 已拥有超过 9 亿周活跃用户。在如此规模下，每一次语音交互的延迟都必须控制在人类对话感知的阈值内——大约 150-200 毫秒。**

超过这个阈值，用户就会感知到"不自然的停顿"、"被打断时反应迟钝"，或者"插话（barge-in）失败"。这正是语音 AI 从"能用"到"好用"之间最难以跨越的鸿沟。

本文将从技术角度深入拆解 OpenAI 的这套架构，涵盖以下关键设计：

- **为什么选择 WebRTC 而非 WebSocket/HTTP**
- **SFU vs Transceiver 模型的抉择**
- **Split Relay 架构：将协议终止与数据包路由解耦**
- **ICE ufrag 巧妙复用：零额外开销的首包路由**
- **Global Relay：地理分布的低延迟接入**
- **Go 语言高性能 UDP 转发的工程实践**
- **对 AI Agent 语音交互基础设施的启示**

---

## 二、为什么是 WebRTC？

### 2.1 语音 AI 的核心约束：连续流

在讨论架构之前，先要理解语音 AI 对传输协议的特殊要求。

与传统的请求-响应模式不同，语音 AI 需要**音频作为连续流到达**。当用户还在说话时，系统就应当开始转录、推理、调用工具、生成语音响应。这就是 OpenAI 所说的：

> *"The difference between a system that feels conversational and one that feels like push-to-talk."*
> （感觉像在对话的系统，和感觉像对讲机的系统之间的区别。）

这意味着协议必须支持：

| 需求 | 传统 HTTP/WebSocket | WebRTC |
|------|-------------------|--------|
| 双向实时流 | ✅ 支持（WebSocket） | ✅ 原生支持 |
| NAT 穿透 | ❌ 需额外工作 | ✅ ICE 标准化 |
| 媒体加密 | ❌ 需自行实现 | ✅ DTLS + SRTP |
| 编解码协商 | ❌ 需自行实现 | ✅ 标准协商流程 |
| 拥塞控制 | ❌ 需自行实现 | ✅ RTCP 反馈 |
| 回声消除 | ❌ 需自行实现 | ✅ 客户端原生支持 |
| 抖动缓冲 | ❌ 需自行实现 | ✅ 客户端原生支持 |

WebRTC 的核心价值在于：**它把最困难的部分——NAT 穿透、加密传输、编解码协商、拥塞控制——全部标准化了**。对于 AI 产品而言，这意味着团队可以把精力集中在"如何将实时媒体连接到模型"上，而不是重新发明底层传输。

### 2.2 WebRTC 生态的成熟度

OpenAI 特别提到了两位关键人物：

- **Justin Uberti**：WebRTC 的原始架构师之一
- **Sean DuBois**：Pion（Go 语言 WebRTC 实现）的创建者和维护者

两人现在都是 OpenAI 的员工。这意味着 OpenAI 不仅在使用 WebRTC，而且在推动 WebRTC 标准本身的发展。

Pion 是一个纯 Go 的 WebRTC 实现，不依赖 CGO，这使得它天然适合在 Kubernetes 环境中部署——这也是 OpenAI 选择它的重要原因之一。

---

## 三、架构抉择：SFU vs Transceiver

在选择了 WebRTC 之后，下一个关键问题是：**在哪里终止 WebRTC 连接？**

### 3.1 SFU（Selective Forwarding Unit）模型

SFU 是视频会议系统的标准架构：每个参与者连接到 SFU，SFU 接收所有流并选择性转发给其他参与者。

```
Client A ──┐
           ├──► SFU ──► Client B
Client B ──┤            (AI Agent)
Client C ──┘
```

SFU 的优势在于复用了成熟的视频会议基础设施：信令、媒体路由、录制、可观测性，以及未来扩展（如人工接管、多参与者）。

### 3.2 Transceiver（收发器）模型

Transceiver 模型则是：一个 WebRTC 边缘服务终止客户端连接，然后将媒体和事件转换为更简单的内部协议，发送给推理后端。

```
Client ──► Transceiver ──► Inference Backend
           (终止 WebRTC)     (内部协议)
```

OpenAI 选择了 Transceiver 模型，原因在于其流量特征：

> *"Most sessions are 1:1 — one user talking to one model, or one application talking to one real-time agent — with latency sensitivity on every turn."*

| 维度 | SFU | Transceiver |
|------|-----|-------------|
| 适用场景 | 多人会议、课堂、协作 | 1:1 对话 |
| 延迟 | 额外一跳转发 | 直接路由到推理 |
| 复杂性 | 维护多流状态 | 简单，状态集中 |
| 扩展性 | 随参与者数增长 | 随会话数线性增长 |

对于 9 亿周活的 1:1 语音场景，Transceiver 是更合理的选择。

---

## 四、核心难题：WebRTC 在 Kubernetes 中的不兼容

### 4.1 传统 WebRTC 的端口模型

传统 WebRTC 使用**每个会话一个端口**（one-port-per-session）模型。这意味着：

- 10,000 个并发会话 → 需要 10,000 个公共 UDP 端口
- 100,000 个并发会话 → 需要 100,000 个公共 UDP 端口

这在裸金属服务器上不是问题，但在 Kubernetes 中是灾难性的：

1. **云负载均衡器不擅长管理数万个 UDP 端口**：每个端口范围都增加负载均衡器配置、健康检查、防火墙策略和滚动发布的复杂度
2. **大端口范围难以保护**：扩大了外部可达的攻击面，使网络策略难以审计
3. **与自动伸缩不兼容**：Pod 不断被添加、删除和重新调度。要求每个 Pod 预留和通告大量稳定端口范围会让弹性变得脆弱

### 4.2 方案对比

OpenAI 评估了多种方案：

| 方案 | 优点 | 缺点 |
|------|------|------|
| 每会话独立 IP:Port（原生 UDP） | 客户端到服务器直接路径<br>无转发层 | 每个会话需一个公共 UDP 端口<br>难以暴露和保护<br>不适合 K8s |
| 每服务器独立 IP:Port | 公共 UDP 占用大幅减少<br>单 Socket 可复用 | 仅解决主机内复用<br>跨负载均衡集群仍需确定性路由 |
| TURN Relay | 客户端只需到达 Relay 地址<br>可在边缘集中策略 | TURN 分配增加往返延迟<br>跨服务器迁移/恢复困难 |
| **无状态转发器 + 有状态终止器**（OpenAI 方案） | 公共 UDP 占用极小<br>Transceiver 仍拥有完整 WebRTC 会话 | 媒体到达 Transceiver 前多一跳<br>需要 Relay 和 Transceiver 之间的自定义协调 |

OpenAI 选择了最后一种方案——**Split Relay 架构**。

---

## 五、Split Relay 架构：协议终止与数据包路由的解耦

### 5.1 核心设计思想

这是整个架构最精妙的部分：**将数据包路由（packet routing）与协议终止（protocol termination）分离**。

```
                   Global Relay (无状态)
                        │
                        │ 解析 ufrag，转发
                        ▼
Client ◄──WebRTC──► Transceiver (有状态)
         (信令直接到)   │
                        │ 内部协议
                        ▼
              Inference Backend
```

- **Relay**：一个轻量级的 UDP 转发层，拥有极小的公共 UDP 占用。**不解密媒体、不运行 ICE 状态机、不参与编解码协商**。它只读取足够的数据包元数据来选择目的地，然后将数据包转发给拥有该会话的 Transceiver。
- **Transceiver**：有状态的 WebRTC 端点，拥有所有协议状态（ICE、DTLS、SRTP、会话生命周期）。

**从客户端的视角来看，WebRTC 会话没有任何变化。** 它仍然在与一个标准的 WebRTC 端点通信。

### 5.2 首包路由：ICE ufrag 的巧妙复用

Relay 面临一个关键挑战：**如何路由第一个数据包？**

在第一个数据包到达时，Relay 上没有任何会话状态。它必须在不暂停、不查询外部服务的情况下，立即决定将数据包转发到哪里。

OpenAI 的解决方案极其优雅：**利用 WebRTC 协议中已有的 ICE ufrag（用户名片段）作为路由元数据**。

每个 WebRTC 会话在信令阶段交换 ICE ufrag——一个用于 STUN 连接性检查的短标识符。OpenAI 的做法是：

1. **在信令阶段**，Transceiver 生成一个包含路由元数据的 server ufrag，编码了目标集群和 Transceiver 的信息
2. **SDP 应答**中向客户端通告共享的 Relay VIP（虚拟 IP）和 UDP 端口（如 `203.0.113.10:3478`）
3. **客户端发送的第一个媒体数据包**通常是 STUN binding request
4. **Relay 解析 STUN 数据包头**，读取 server ufrag，解码路由提示，将数据包转发给对应的 Transceiver
5. **Relay 建立会话映射**后，后续的 DTLS、RTP、RTCP 数据包直接在会话内流动，无需重新解码 ufrag

```
信令阶段:
Client ──HTTP──► Transceiver
                 │ 生成 ufrag = "clusterA:transceiver42:randomSalt"
                 │ SDP 应答: Relay VIP = 203.0.113.10:3478
                 ▼

媒体阶段（首包）:
Client ──STUN(ufrag)──► Relay
                        │ 解析 ufrag → clusterA:transceiver42
                        ▼
                  Transceiver #42

媒体阶段（后续包）:
Client ──DTLS/RTP──► Relay ──► Transceiver #42
                    (直接转发，无需解析)
```

这个设计的精妙之处在于：**路由信息编码在协议已有的字段中，不需要任何额外的信令或查找**。ICE ufrag 本来就是为了连接性检查而存在的，OpenAI 只是在其中嵌入了路由元数据。

### 5.3 容错与恢复

Relay 的状态设计也非常讲究：

- **内存中维护最小映射**：`<client IP:Port, transceiver IP:Port>` 的短期超时映射，仅用于流转发和可观测性
- **Redis 缓存持久化**：路由建立后，映射存储在 Redis 中，以便在 Relay 重启时快速恢复
- **无状态恢复**：如果 Relay 重启并丢失了会话，下一个 STUN 数据包会通过 ufrag 路由提示重建会话

这种设计使得 Relay 的重启只会造成最小的流量中断，而不是全量会话重建。

---

## 六、Global Relay：地理分布的低延迟接入

### 6.1 第一跳延迟的决定性影响

对于语音 AI 而言，**客户端到 OpenAI 网络的第一跳距离**直接影响感知延迟。如果数据包需要先穿过半个地球的公共互联网才能进入 OpenAI 的网络，那么即使内部延迟再低，用户的体验也会很差。

### 6.2 架构

```
                    ┌─── Global Relay (Tokyo)
                    │
Client (Beijing) ───┤─── Global Relay (Singapore) ← 最近接入
                    │
                    └─── Global Relay (San Jose)
```

- **信令**：使用 Cloudflare 的 geo 和 proximity steering，让 HTTP/WebSocket 请求到达最近的 Transceiver 集群
- **媒体**：SDP 应答中通告最近的 Global Relay 地址
- **ufrag**：包含足够的路由信息，让 Global Relay 将媒体路由到指定的集群

这种设计确保了**信令和媒体都通过就近的路径进入 OpenAI 网络**，同时会话仍然锚定在一个 Transceiver 上。

### 6.3 效果

| 指标 | 集中式接入 | Global Relay |
|------|-----------|-------------|
| 第一跳 RTT | 高（取决于用户位置） | 低（就近接入） |
| 抖动 | 高（公共互联网波动） | 低（快速进入骨干网） |
| 丢包 | 高 | 低 |
| 连接建立时间 | 长 | 短 |

---

## 七、Go 语言高性能 UDP 转发：工程实践

### 7.1 为什么是 Go？

Relay 用 Go 编写，并且刻意保持实现精简。它不需要任何内核旁路（kernel-bypass）框架——这在 DPDK 等场景中常见，但会增加运维复杂度。

### 7.2 三个关键优化

#### 7.2.1 SO_REUSEPORT

```
Linux Socket: SO_REUSEPORT
    ↓
多个 Relay Worker 绑定同一 UDP 端口
    ↓
内核将入站数据包分发到不同 Worker
    ↓
避免单读循环瓶颈
```

Linux 的 `SO_REUSEPORT` 允许同一台机器上的多个 Relay Worker 绑定同一个 UDP 端口。内核然后会在这些 Worker 之间分发入站数据包。

#### 7.2.2 runtime.LockOSThread

```go
// 将读取 UDP 的 goroutine 锁定到特定 OS 线程
runtime.LockOSThread()
```

结合 `SO_REUSEPORT`，这倾向于让同一数据流（相同源和目标 IP:Port + 协议）的数据包落在同一个 CPU 核心上，改善缓存局部性并减少上下文切换。

#### 7.2.3 预分配缓冲区和最小化拷贝

- 预分配数据包缓冲区，避免运行时分配
- 最小化数据拷贝，降低 GC 压力
- 仅解析 STUN 头/ufrag，后续数据包保持不透明转发

### 7.3 性能特征

| 优化手段 | 解决的问题 |
|----------|-----------|
| SO_REUSEPORT | 消除单读循环瓶颈 |
| LockOSThread | 改善缓存局部性，减少上下文切换 |
| 预分配缓冲区 | 避免 GC 停顿 |
| 最小化拷贝 | 降低 CPU 开销 |
| 无内核旁路 | 降低运维复杂度 |

OpenAI 的结论是：**对于他们的工作负载，这种精简的 Go 实现已经足够，不需要引入内核旁路路线**。

---

## 八、架构全景图

将所有组件放在一起：

```
┌─────────────────────────────────────────────────────────┐
│                     Global Internet                      │
└──────────────┬──────────────────────┬───────────────────┘
               │                      │
      ┌────────▼────────┐    ┌────────▼────────┐
      │  Cloudflare     │    │  Cloudflare     │
      │  Geo Steering   │    │  Geo Steering   │
      │  (信令路由)     │    │  (信令路由)     │
      └────────┬────────┘    └────────┬────────┘
               │                      │
      ┌────────▼────────┐    ┌────────▼────────┐
      │   Transceiver   │    │   Transceiver   │
      │   (有状态)      │    │   (有状态)      │
      │   • ICE/DTLS    │◄──►│   • ICE/DTLS    │
      │   • SRTP        │    │   • SRTP        │
      │   • SDP 协商    │    │   • SDP 协商    │
      └────────┬────────┘    └────────┬────────┘
               │                      │
      ┌────────▼──────────────────────▼────────┐
      │          Global Relay 集群              │
      │  (无状态 UDP 转发)                      │
      │  • 解析 ufrag                           │
      │  • 首包路由                             │
      │  • 后续包直接转发                        │
      │  • Redis 缓存会话映射                    │
      │  • SO_REUSEPORT + LockOSThread          │
      └──────────────┬─────────────────────────┘
                     │
           ┌─────────▼──────────┐
           │  Internal Backbone  │
           │  (推理后端)          │
           │  • 转录             │
           │  • 推理             │
           │  • 语音生成          │
           │  • 工具调用          │
           │  • 编排             │
           └────────────────────┘
```

---

## 九、设计原则：从 OpenAI 的经验中提炼

OpenAI 在文章末尾总结了几个关键设计决策，这些原则对于任何构建实时 AI 基础设施的团队都有参考价值：

### 9.1 在边缘保留协议语义

> *"Clients still speak standard WebRTC, which keeps browser and mobile interoperability intact."*

不要改变客户端的协议。标准 WebRTC 意味着浏览器和移动端的互操作性保持完好。任何自定义都应该在服务器内部。

### 9.2 将硬状态集中在一处

> *"Transceiver owns ICE, DTLS, SRTP, and session lifecycle; relay only forwards packets."*

WebRTC 的复杂状态（ICE、DTLS、SRTP、会话生命周期）全部集中在 Transceiver。Relay 只做转发。这是典型的关注点分离。

### 9.3 利用协议已有的信息做路由

> *"The ICE ufrag gave us a first-packet routing hook without adding a hot-path lookup dependency."*

不引入额外的查找依赖。ICE ufrag 已经存在，只需在其中编码路由信息。这是**协议原生路由**的典范。

### 9.4 先优化常见情况，再考虑极端手段

> *"A narrow Go implementation with careful use of SO_REUSEPORT, thread pinning, and low-allocation parsing was enough for our workload."*

不需要 DPDK、eBPF 或内核旁路。精心编写的用户态代码已经足够。这是一个被低估的工程原则：**大多数团队不需要极端优化，需要的是正确地做基础优化**。

---

## 十、对 AI Agent 语音交互的启示

### 10.1 语音 Agent 的延迟预算

对于语音 AI Agent 而言，端到端延迟需要分解如下：

| 阶段 | 目标延迟 | 占比 |
|------|---------|------|
| 网络传输（RTT） | < 50ms | ~15% |
| 语音活动检测（VAD） | < 30ms | ~10% |
| 流式转录（ASR） | < 100ms | ~30% |
| LLM 推理（首 token） | < 200ms | ~60% |
| 语音合成（TTS 首帧） | < 100ms | ~30% |

网络传输是基础。如果网络延迟就超过了 100ms，即使模型推理再快，用户体验也会很差。

### 10.2 开源生态的追赶

OpenAI 的架构是闭源的，但开源生态正在快速追赶：

- **LiveKit**：开源的 WebRTC 基础设施，支持 AI Agent 场景，已在生产中大规模使用
- **Pipecat**：开源的语音 AI Agent 框架，支持流式 ASR/LLM/TTS 管线
- **Vocode**：专注于电话场景的开源语音 AI 框架
- **Pion WebRTC**：Go 语言的 WebRTC 实现，OpenAI 正是基于它构建

### 10.3 对于构建自研语音 Agent 团队的建议

1. **不要自己实现 WebRTC**：使用成熟的库（Pion、LiveKit、mediasoup）
2. **尽早考虑地理分布**：延迟不是"以后再说"的问题，而是第一天的设计约束
3. **将信令与媒体分离**：信令走 HTTP/WebSocket，媒体走 UDP。这样可以独立扩展
4. **利用协议原生字段做路由**：不要引入额外的查找依赖
5. **Go 足够快**：在 DPDK 之前，先做好 SO_REUSEPORT、线程绑定和内存预分配

---

## 十一、结语：基础设施决定了 AI 的上限

OpenAI 的这篇技术博客揭示了一个经常被忽视的事实：**AI 模型的能力只是故事的一半。另一半是，如何把这些能力以人类可以感知的速度传递到用户面前。**

当模型推理延迟已经压缩到 200ms 以内时，网络基础设施就成了新的瓶颈。OpenAI 选择重新设计 WebRTC 栈，不是因为它"喜欢"底层工程，而是因为在 9 亿周活的规模下，基础设施的每一个细节都在放大——包括延迟。

这篇文章最核心的工程启示可以总结为一句话：

> **最好的复杂化位置是在一个薄路由层中，而不是在每个后端服务中，也不是在自定义的客户端行为中。**

这个原则——**复杂性应该集中在基础设施的边缘层，而不是扩散到整个系统**——不仅适用于 WebRTC 和语音 AI，也适用于任何需要大规模实时交互的系统。

对于正在构建语音 AI Agent 的开发者来说，OpenAI 的架构不是一个可以直接复制的蓝图，而是一个思考框架：**你的实时媒体传输路径上，有多少跳是可以消除的？你的协议状态，是否集中在了正确的位置？你的路由决策，是否可以利用协议已有的信息？**

回答这些问题，可能就是你的语音 Agent 从"能用"到"好用"的关键一步。

---

*参考资料：*
1. OpenAI Blog, "How OpenAI delivers low-latency voice AI at scale", 2026-05-04
2. Addy Osmani, "Agent Skills", 2026-05-04
3. Hugging Face Blog, "AI evals are becoming the new compute bottleneck", 2026-04-29
4. WebRTC Working Group, W3C WebRTC Standard
5. Pion WebRTC, GitHub: pion/webrtc
6. RFC 5389, STUN: Session Traversal Utilities for NAT
7. RFC 8831, WebRTC: JavaScript APIs for Peer-to-Peer
