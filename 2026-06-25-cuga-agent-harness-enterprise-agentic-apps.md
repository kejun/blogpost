# CUGA 深度解析：当 Agent 框架走向"Harness 时代"——IBM 如何让 24 个 Agentic App 用同一个模式跑通生产

**文档日期：** 2026 年 6 月 25 日  
**标签：** AI Agent, Agent Harness, CUGA, IBM Research, Enterprise AI, Agentic App, MCP, A2A, Policy System

---

## 一、背景：Agent 开发的"一周水管期"

2026 年 6 月 23 日，IBM Research 在 Hugging Face 博客上发表了一篇看似低调但信息量巨大的文章：*Build real agentic apps using CUGA: two dozen working examples on a lightweight harness*。文章开头的一句话直接戳中了每一个写过 Agent 的开发者的痛点：

> Most agentic apps start with a week of plumbing before the agent does anything useful.

你挑一个框架、接模型客户端、写 tool adapter、构建状态流、设计 UI……最后才开始写那个真正属于你自己的部分——Agent 到底该干什么。有趣的部分反而最后才到。

CUGA（**C**onfigurable **U**niversal **G**eneralist **A**gent）试图颠覆这个流程。它的核心论点很简单：**Agent 开发的大头不是模型选择，也不是工具定义，而是围绕模型的编排层——规划、执行循环、工具调用、状态管理、自我修正。** 如果你能把这些"水管"标准化，剩下的工作就只剩下两件事：工具列表 + Prompt。

这篇文章的特别之处在于，IBM 不是空谈架构，而是拿出了 **24 个单文件可运行的 Agentic App**，覆盖从电影推荐到七 Agent 协作的线索生成系统，每个都共享同一个骨架。你读完一个，就读完了全部。

更值得关注的信号：CUGA 在 **AppWorld**（750 个真实 API 任务，457 个 API）和 **WebArena**（复杂自主 Web Agent 基准）上都拿到了 **第一名**，且分别霸榜 7 个月和 7 个月。这不是一个玩具项目——它是一个被基准验证过的、面向生产环境的通用 Agent Harness。

---

## 二、Harness vs Framework：概念层面的范式转移

要理解 CUGA 的价值，首先要区分两个容易混淆的概念：**Agent Framework** 和 **Agent Harness**。

### 2.1 两者的本质区别

```
Agent Framework vs Agent Harness

┌────────────────────────────────────────────────────────────┐
│  Framework（框架）                                           │
│  提供的是"积木"——组件、API、扩展点。                            │
│  你需要自己拼装：选什么模型？怎么写规划？                      │
│  怎么处理工具失败？如何管理状态？                             │
│  代表：LangChain、LlamaIndex、CrewAI、AutoGen                 │
│                                                              │
│  你写的代码量 ≈ 70% 编排 + 30% 业务逻辑                       │
├────────────────────────────────────────────────────────────┤
│  Harness（操控系统 / 驾驶舱）                                 │
│  提供的是"发动机+底盘"——规划、执行、反思、状态追踪。            │
│  你只需要定义：工具有哪些？Agent 该做什么？                     │
│  代表：CUGA                                                  │
│                                                              │
│  你写的代码量 ≈ 10% 编排 + 90% 业务逻辑                       │
└────────────────────────────────────────────────────────────┘
```

这个区别不是语义游戏。它决定了一个团队在 Agent 项目上的投入结构。

在 Framework 模式下，团队需要维护一套自己的编排逻辑——这恰恰是 Agent 最脆弱的部分。规划循环怎么写？工具调用失败了怎么重试？长程任务中如何保持中间状态？这些都不是业务逻辑，但决定了 Agent 能不能跑起来。

Harness 模式的回答是：**这部分不应该由每个团队重复发明。** 它应该是标准化的基础设施，像 Kubernetes 之于容器、React 之于前端组件一样——你用它，而不是重新造它。

### 2.2 CUGA 的架构决策

CUGA 做了一个关键的架构决策：**把编排层做到足够深，让上层应用几乎只关心工具列表和 Prompt。**

```python
def make_agent():
    from cuga import CugaAgent
    from _llm import create_llm

    return CugaAgent(
        model=create_llm(
            provider=os.getenv("LLM_PROVIDER"),
            model=os.getenv("LLM_MODEL"),
        ),
        tools=_make_tools(),
        special_instructions=_SYSTEM,
        cuga_folder=str(_DIR / ".cuga"),
    )
```

四行构造函数。模型通过环境变量切换（OpenAI、Anthropic、watsonx、Ollama 都行），工具列表和系统提示是唯一需要业务开发者关心的部分。`cuga_folder` 存状态和策略，代码本身不关心底层用的是哪个模型。

这就是 Harness 承诺的交付物：**同一套编排引擎，不同的工具+Prompt 组合，产出完全不同的 Agent。**

---

## 三、技术深挖：CUGA 的核心引擎

### 3.1 Plan → Execute → Reflect 循环

CUGA 的核心是一个 **规划-执行-反思** 循环，这是它与大多数"直接调用模型"框架的关键差异：

```
CUGA Agent 执行循环

用户请求
  │
  ▼
┌──────────────┐
│  Plan (规划)  │ ← 在动作之前先制定计划
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ Execute (执行)    │ ← 混合工具调用 + CodeAct（代码执行）
│ • Tool Call      │
│ • CodeAct        │
└──────┬───────────┘
       │
       ▼
┌──────────────┐
│ Reflect (反思) │ ← 检查结果，捕获错误，必要时重新规划
└──────┬───────┘
       │
       ├── 成功 → 输出结果
       │
       └── 失败 → 回到 Plan，带着上下文修正
```

这个循环解决了一个在长程任务中极其常见但多数框架处理不好的问题：**在二十步的任务中，大多数 Agent 会因为丢失中间结果并在下一步重新推导（经常推导错）而崩溃。** CUGA 通过显式的状态管理和反思步骤来避免这一点——它不只是把上一轮的输出当下一轮的输入，而是真正检查"上一步做对了吗？"。

这也是 CUGA 能在 AppWorld 和 WebArena 霸榜的核心原因：基准测试中的复杂任务恰恰是这种"丢失中间状态→重新推导→推导错误→级联失败"模式的高发区。

### 3.2 CodeAct + Tool Call 混合执行

CUGA 的执行层不只是调用预定义工具。它还支持 **CodeAct**（代码执行）模式——Agent 可以在运行时动态生成并执行代码来处理工具返回的数据。

这带来一个关键优势：**当预定义工具不够用时，Agent 不会卡住。** 它可以自己写一段 Python 代码来处理数据结构、做数学运算、或者格式化输出。这种"工具不够，代码来补"的模式在 WebArena 这种需要灵活处理 Web DOM 的场景中特别有用。

但这也意味着需要更严格的沙箱控制。CUGA 支持三种代码执行沙箱：

| 沙箱类型 | 适用场景 | 隔离级别 |
|---------|---------|---------|
| Local | 开发/测试 | 低 |
| Docker/Podman | 生产环境 | 高 |
| E2B Cloud | 多租户/云端部署 | 最高 |

### 3.3 三种推理模式：成本/延迟的声明式切换

CUGA 最务实的设计之一是把 **成本/延迟权衡从代码提升到了配置层**：

```toml
# settings.toml
[cuga_mode]
mode = "fast"      # 快速：少规划，直接执行
# mode = "balanced"  # 平衡：适度规划
# mode = "accurate"  # 精确：完整规划+反思
```

同一个 Agent 定义，只需要改一个环境变量，就能在快速、平衡、精确三种模式之间切换。这意味着你可以在开发阶段用 `accurate` 模式调试 Agent 行为，在生产环境切换到 `fast` 模式降低成本——**不需要改任何业务代码**。

更重要的是，这个设计隐含了一个被忽视的事实：**大多数 Harness 假设底层用的是前沿模型，靠模型能力来兜底规划失败的情况。** CUGA 的思路反过来——它自己做规划、反思、变量追踪这些"脏活"，从而让较小的开源模型也能胜任复杂任务。这也是为什么 CUGA 的在线演示跑的是 `gpt-oss-120b` 而不是某个闭源前沿模型：**Harness 在替模型扛活。**

---

## 四、工具集成模式：MCP + 内联工具的"二八定律"

### 4.1 工具定义的统一接口

CUGA 支持三种工具来源，但用同一套接口绑定：

```python
def _make_tools():
    from langchain_core.tools import tool

    # 内联工具：业务特定的能力
    @tool
    def search_ibm_catalog(query: str) -> str:
        """Search the IBM Cloud Global Catalog for real IBM Cloud services."""
        ...

    # MCP 工具：通用的、无状态的能力
    from _mcp_bridge import load_tools
    web_tools = load_tools(["web"])

    return [search_ibm_catalog, *web_tools]
```

这里有一个值得注意的模式：**通用能力走 MCP，业务特定能力走内联函数。**

IBM 维护了 7 个公共 MCP 服务器（36 个工具），涵盖 Web 搜索、Wikipedia/arXiv、地理编码和天气、金融报价等通用能力。CUGA 的 MCP Bridge 自动解析这些服务器的 URL，开发者只需要一行 `load_tools(["web"])` 就能拿到全套 Web 搜索能力。

这个模式的好处很直观：
- **减少重复开发**：每个 App 不需要自己写 Web 搜索、天气查询等通用工具
- **集中维护**：通用工具的更新（如 API 变更、认证升级）在 MCP 服务器端统一处理
- **即插即用**：新的 App 只需要定义 1-2 个自己的业务工具，其余全部复用

### 4.2 工具返回的"无聊约定"

CUGA 的 24 个 App 中有一个很容易被忽略但极其重要的约定：**每个内联工具都返回统一的信封格式**：

```python
# 成功
{"ok": True, "data": {...}}

# 失败
{"ok": False, "code": "...", "error": "..."}
```

"这看起来很无聊，但它不是。"

CUGA 的规划器对声明式失败做优雅处理（"地理编码没返回数据，跳过那一节继续"），但对未声明的失败会崩溃（原始堆栈跟踪在规划中途冒泡，整个运行脱轨）。在 24 个 App 中，那些运行可靠的 App 恰恰是工具永远不会向 Agent 抛出裸异常的。

**一个无聊的约定，就是 Agent 能自我恢复和直接崩溃之间的区别。**

这一点在 Agent 工程中有广泛适用性。当你在设计 Agent 工具时，"工具永远不抛异常"比"工具功能强大"更重要。因为 Agent 的规划循环假设工具调用要么成功（返回数据）要么失败（返回错误码），但不处理"抛异常"这种第三态。

### 4.3 Prompt 的结构化写法

CUGA 的 App 展示了一个 Prompt 写法的最佳实践：**把 Prompt 写成有序步骤，明确"不要做什么"，而不是写成角色设定。**

```
系统提示（IBM Cloud Advisor）：
1. 推荐服务前必须先搜索目录验证
2. 推荐 3-7 个服务，每个说明其在架构中的角色
3. 绝不发明不存在的服务名称
```

第三条规则尤其重要——一个推荐不存在服务的 Agent 比没有 Agent 更糟糕。Prompt 中的"don't make things up"规则直接对应了 Agent 工程中的一个核心问题：**幻觉不只是输出生成阶段的产物，它也会在工具调用规划阶段出现。**

---

## 五、治理层：让 Agent 守住边界

### 5.1 六种策略类型

Demo Agent 搜索产品目录没有风险。但当你把同一个模式指向写文件、跑 shell 命令、碰生产环境时，问题就变了：**你怎么阻止它做让你后悔的事？**

CUGA 的回答是：**在运行时做治理，而不是事后加包装。** 它提供六种策略类型，分别回答团队在释放 Agent 之前都会问的问题：

| 策略类型 | 回答的问题 | 触发时机 |
|---------|-----------|---------|
| **Intent Guard** | 能否直接拒绝某个请求？ | Agent 选择工具之前 |
| **Tool Approval** | 能否在危险工具运行前让人类审批？ | Agent 生成代码后，检查使用了哪些工具 |
| **Tool Guide** | 能否指导某个工具的使用方式而不重写它？ | 工具调用时 |
| **Playbook** | 能否为常见任务锁定已知的好流程？ | 任务匹配时 |
| **Output Formatter** | 能否强制最终输出为指定格式？ | 最终消息生成后 |
| **CustomPolicy** | 以上都不合适时的逃生舱口 | 自定义 |

```python
# Intent Guard 示例：阻止破坏性 Git 操作
await agent.policies.add_intent_guard(
    name="Block force-push",
    keywords=["--force", "--no-verify"],
    response="Blocked: destructive git flags are not permitted.",
)
```

### 5.2 语义匹配：超越关键词

策略的触发不只是关键词匹配。CUGA 的策略存储在一个 **sqlite-vec 向量存储** 中，支持语义匹配：

> 策略会因为用户的意思触发，而不是因为精确的关键词触发。

这意味着一个 Intent Guard 可以被配置为"阻止任何涉及数据删除的请求"，而不需要穷举所有可能的关键词变体。Agent 说"帮我清空数据库"和"把数据表全删了"都会被同一个策略拦截。

### 5.3 策略的版本化管理

策略文件存储在 `.cuga` 文件夹中，**与代码一起版本化，而不是漂移到外部配置系统。** 这个设计决策很重要：策略是 Agent 行为的一部分，应该和代码一起被审查、回滚、审计。

---

## 六、多 Agent 架构：CugaSupervisor 模式

### 6.1 为什么需要 Supervisor

当单个 Agent 被自己的上下文淹死时（工具太多、证据太多、上下文太长），你需要拆分工作。CUGA 的答案是 **CugaSupervisor**：

```
CugaSupervisor 架构

                    ┌──────────────────┐
                    │    Supervisor     │
                    │  (只做一件事：     │
                    │   选哪个专家？)    │
                    └────┬──┬──┬───────┘
                         │  │  │
              ┌──────────┘  │  └──────────┐
              ▼             ▼             ▼
      ┌──────────┐  ┌──────────┐  ┌──────────┐
      │ Specialist│  │ Specialist│  │ Specialist│
      │ A (工具集)│  │ B (工具集)│  │ C (工具集)│
      └──────────┘  └──────────┘  └──────────┘
```

Supervisor 只做一件事：**决定把子任务委派给哪个专家。** 它的规划面保持很小，无论底层有多少工具。一个工具出问题只影响一个专家，不会拖垮整个运行。

专家甚至不必是本地的——它可以是通过 **A2A（Agent-to-Agent）协议** 访问的远程 Agent。增加能力意味着增加一个专家，而不是重写协调器。

### 6.2 实际案例：Ouroboros 七 Agent 线索生成系统

CUGA Apps 中的 **Ouroboros** 是一个七 Agent 的线索生成系统，它同时演示了多 Agent 模式和治理模式：

- **Supervisor** 管理 7 个专家 Agent
- 每个专家有自己的工具、Prompt 和隔离上下文
- Supervisor 附加了 3 个策略（Intent Guard + Tool Guide + Output Formatter）
- 这是唯一一个同时展示治理和多 Agent 形态的 App

这个结构揭示了一个重要的 Agent 工程模式：**增加 Agent 的横向扩展，不应该增加 Supervisor 的纵向复杂度。** 这正是 Supervisor 模式的核心价值。

### 6.3 Agent Skills：可组合的能力包

CUGA 还支持 **Agent Skills**——以 `SKILL.md` 文件形式打包的领域知识。Agent 只在任务需要时才拉入上下文，避免单个 Prompt 承载所有可能需要的知识。

这个模式和我们之前写过的 Agent Skills 组合工程文章（2026-05-16）中讨论的方向一致：**组合比创建更难，可组合的能力包是 Agent 工程的下一个前沿。**

---

## 七、数据与基准：CUGA 为什么能拿第一

### 7.1 AppWorld 霸榜

AppWorld 是一个包含 **750 个真实世界任务、457 个 API** 的基准测试。CUGA 从 2025 年 7 月到 2026 年 2 月连续 7 个月排名第一。

AppWorld 的设计哲学是"真实"——它不是精心构造的 toy benchmark，而是模拟了实际 API 集成的复杂性。CUGA 的 Plan-Execute-Reflect 循环在这种环境中表现出色的原因很直接：**真实 API 会返回意外的响应、超时、部分数据——需要 Agent 能自我修正，而不是在第一次失败后崩溃。**

### 7.2 WebArena 霸榜

WebArena 是一个更复杂的自主 Web Agent 基准，覆盖多个应用领域。CUGA 从 2025 年 2 月到 2025 年 9 月同样霸榜 7 个月。

WebArena 的核心挑战是 **在动态 Web 环境中保持状态和规划的一致性**。CUGA 的变量管理机制在这里发挥了关键作用——它不仅仅是把 Web 页面当无状态的输入输出，而是维护了一个跨步骤的状态字典，让 Agent 在二十步的 Web 操作中不会"忘记"中间结果。

### 7.3 小模型也能打的启示

CUGA 在线演示使用 `gpt-oss-120b`（开源模型）而非闭源前沿模型，但依然取得了 SOTA 成绩。这传递了一个对行业非常重要的信号：

> **Harness 的质量比模型的大小更重要。**

当编排层足够扎实时，开源模型在复杂任务上的表现可以匹敌甚至超越更大更强的前沿模型。这对于企业 AI 的成本结构有直接意义——你不需要为每个 Agent 任务都调用最贵的模型。

---

## 八、与已有文章的知识关联

本文与本博客已有文章的交叉引用：

| 已有文章 | 关联点 |
|---------|--------|
| [Agent Harness 架构抉择](2026-05-03) | 沙箱内 vs 沙箱外的决策，CUGA 提供了三种沙箱选项 |
| [Agent Tool-Use 可靠性瓶颈](2026-05-31) | 工具返回格式约定直接解决可靠性问题 |
| [AI Agent 可靠性鸿沟](2026-04-29) | Harness 层正是缩小 Benchmark 到生产差距的关键基础设施 |
| [Agent Skills 组合工程](2026-05-16) | CUGA 的 SKILL.md 机制是可组合能力的具体实现 |
| [Spec-Driven Development](2026-05-15) | CUGA 的策略系统（Playbook、Intent Guard）是规格驱动的执行保障 |

---

## 九、独立思考：CUGA 的局限与隐忧

### 9.1 IBM 生态锁定的风险

CUGA 虽然开源，但它的工具生态（7 个公共 MCP 服务器）和知识库引擎（Docling）深度绑定 IBM 基础设施。企业用户需要评估：这些依赖是否会在长期使用中形成隐性锁定？

### 9.2 复杂度的隐藏成本

Harness 模式的核心承诺是"你只需要写工具和 Prompt"。但实际上，**好的 Prompt 本身就是一门工程学科**。当编排层被抽象掉之后，开发者面对的直接是模型的行为调控——这并不比写编排代码简单，只是难度转移了。

### 9.3 多 Agent 调试的难度

CugaSupervisor 模式在架构上很优雅，但 **调试一个七 Agent 系统中"为什么 Supervisor 选了 A 而不是 B"** 的难度可能远超调试单 Agent。Agent 间的委托链和隔离上下文增加了故障定位的复杂度。

### 9.4 社区生态的成熟度

与 LangChain、LlamaIndex 等成熟框架相比，CUGA 的社区生态（教程、第三方集成、StackOverflow 讨论量）还远未达到临界质量。企业用户需要权衡"架构先进"和"社区成熟"之间的取舍。

---

## 十、总结：Harness 时代正在到来

CUGA 代表了 AI Agent 工程的一个微妙但重要的转变：**从"给开发者积木让他们自己搭"到"给开发者发动机让他们自己装车身"。**

这个转变的意义在于：
1. **标准化编排层**，减少每个团队重复发明轮子
2. **让模型选择成为配置而非架构决策**，降低迁移成本
3. **治理内建在运行时**，而不是事后补丁
4. **多 Agent 扩展不增加协调复杂度**

当 24 个 Agentic App 用同一个四行构造函数跑通从电影推荐到企业级线索生成的全部场景时，我们看到的不是一个框架的 API 设计——而是一个**新的 Agent 开发范式正在成型**。

Harness 不会是 Framework 的替代品，但在复杂、多步骤、需要治理的 Enterprise Agent 场景中，Harness 可能是通往生产的更短路径。

正如 IBM Research 在文章中所说：

> None of the individual pieces is unique to CUGA. What's different is that they come pre-assembled.

每一块砖都不是新的，但砌成了一堵不一样的墙。

---

**参考资料：**

1. IBM Research. "Build real agentic apps using CUGA: two dozen working examples on a lightweight harness." Hugging Face Blog, 2026-06-23. https://huggingface.co/blog/ibm-research/cuga-apps
2. CUGA Project. GitHub Repository. https://github.com/cuga-project/cuga-agent
3. CUGA Apps. Hugging Face Space. https://huggingface.co/spaces/ibm-research/cuga-apps
4. AppWorld Leaderboard. https://appworld.dev/leaderboard
5. WebArena Benchmark. https://webarena.dev/
6. CUGA Documentation. https://docs.cuga.dev/
7. Hugging Face Blog Feed. https://huggingface.co/blog/feed.xml
8. GitHub Trending. https://github.com/trending
