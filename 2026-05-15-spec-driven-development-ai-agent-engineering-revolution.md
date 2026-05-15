# Spec-Driven Development 革命：当 AI Agent 工程从"Prompt 驱动"走向"规格驱动"

**文档日期：** 2026 年 5 月 15 日  
**标签：** Spec-Driven Development, AI Agent Engineering, Developer Tools, Agent Reliability, 软件工程范式  
**参考项目：** [spec-kit](https://github.com/github/spec-kit) (99,464⭐), [gstack](https://github.com/garrytan/gstack) (96,720⭐), [mattpocock/skills](https://github.com/mattpocock/skills) (82,197⭐), [obra/superpowers](https://github.com/obra/superpowers)

---

## 一、一个信号：GitHub Trending 前三名的共同秘密

2026 年 5 月 15 日，打开 GitHub Trending，你会看到一件令人震惊的事：

| 排名 | 项目 | Stars | 今日增长 | 核心特征 |
|------|------|-------|----------|----------|
| 1 | [spec-kit](https://github.com/github/spec-kit) | **99,464** | +1,232 | 规格驱动开发工具包 |
| 2 | [gstack](https://github.com/garrytan/gstack) | **96,720** | +915 | 23 个 opinionated Agent 工具链 |
| 3 | [mattpocock/skills](https://github.com/mattpocock/skills) | **82,197** | +2,987 | 面向真实工程师的 Agent 技能集 |

三个项目，合计 **278,381 个 Star**，它们有一个共同的底层理念：

> **AI Agent 不应由 Prompt 驱动，而应由 Specification（规格）驱动。**

这不仅仅是又一个工具趋势。这是 AI Agent 工程范式的一次根本性转移——从"告诉 Agent 做什么"（Prompt-Driven）走向"定义 Agent 必须产出什么"（Spec-Driven）。

让我用一个比喻来说明这种转变的本质：

```
Prompt-Driven Agent:  你对一个实习生说"帮我做一个用户管理系统"
Spec-Driven Agent:    你给实习生一份 PRD + API 契约 + 验收标准，然后让 Agent 自主交付
```

前者依赖**语言的自然模糊性**，后者依赖**规格的精确约束力**。在 Agent 可靠性仍然普遍低于 40% 的生产环境中（参考 VAKRA Benchmark 数据），这种转变不是选择，而是必然。

---

## 二、为什么是现在？Prompt-Driven 的天花板

### 2.1 可靠性危机：数据说话

IBM Research 的 VAKRA Benchmark 在 2026 年 4 月发布了一组令行业不安的数据：在 8,000+ 真实企业 API 的测试中，最先进的 LLM Agent 的**任务完成率普遍低于 40%**。即使是 GPT-4.5 级别的模型，在需要 3-7 步推理链的复合任务中，成功率也仅有 **35%-45%**。

失败模式分析显示：

| 失败类型 | 占比 | 根因 |
|----------|------|------|
| 工具调用错误 | 38% | API 参数推断不准确 |
| 推理链断裂 | 27% | 中间状态丢失或错误 |
| 意图理解偏差 | 22% | Prompt 模糊导致错误方向 |
| 边界条件遗漏 | 13% | 缺乏明确的约束定义 |

**注意：22% 的失败直接源于"意图理解偏差"——Agent 误解了人类到底想要什么。** 而这类错误的根因正是 Prompt-Driven 范式的结构性缺陷。

### 2.2 Prompt 的本质缺陷

Prompt 是自然语言。自然语言的本质是**模糊的、歧义的、依赖上下文的**。这对于聊天是优势，对于工程是灾难。

让我们拆解一个典型的 Prompt-Driven Agent 工作流：

```
用户: "帮我把这个 API 改成分页的"
Agent 需要推断：
  - 哪种分页方式？（offset/limit？cursor-based？keyset？）
  - 页大小默认值？
  - 最大页限制？
  - 是否需要在响应中包含元数据？
  - 现有调用方是否需要同步修改？
  - 向后兼容性如何处理？
```

在一个真实的工程项目中，这些决策不应该由 Agent"猜测"。它们应该在**规格中明确定义**。

MIT Technology Review 在 2026 年 5 月 14 日的文章中精准地指出了这一点：

> "Agentic AI amplifies the weakest link in the chain: data availability and quality."  
> —— Steve Mayzak, Elastic Global Managing Director of Search AI

如果把"数据"替换为"规格"，这句话同样成立：**Agent 的能力放大了规格中最薄弱的环节。** 没有好的规格，强大的 Agent 只是更快地产生错误的结果。

### 2.3 arXiv 的警示

就在我写这篇文章的同时，arXiv 宣布了对**幻觉引用的 1 年禁令政策**（Hacker News 热帖）。这个看似学术圈的事件，实际上指向了一个更广泛的工程问题：**当 AI 系统缺乏精确约束时，它们会编造看起来合理但完全错误的内容。**

在代码开发中，这种"编造"的代价不是撤稿，而是生产事故。

---

## 三、Spec-Driven Development 的三个实践层次

今天 GitHub 上的三大项目恰好代表了 Spec-Driven Development 的三个层次。理解这三个层次，就是理解这个范式的完整图景。

### 3.1 第一层：规格即起点（spec-kit 模式）

GitHub 官方的 [spec-kit](https://github.com/github/spec-kit)（99,464⭐）代表了最直接的 Spec-Driven 理念：**开发始于规格，终于规格验证**。

它的核心工作流是：

```
1. 编写规格文档（PRD → Tech Spec → Task Breakdown）
2. Agent 基于规格生成代码
3. 自动化验证代码是否符合规格
4. 迭代直到规格满足
```

关键洞察在于**步骤 3**——这不是普通的代码审查，而是**规格验证（Spec Validation）**。spec-kit 提供了一套工具链，让 Agent 不仅生成代码，还要证明代码满足规格中定义的约束。

```yaml
# 规格示例（spec-kit 风格）
spec:
  name: "用户 API 分页改造"
  constraints:
    - type: "pagination"
      method: "cursor-based"
      default_limit: 20
      max_limit: 100
    - type: "backward_compatibility"
      strategy: "deprecate-offset-params"
      sunset_date: "2026-08-01"
    - type: "response_format"
      include_metadata: true
      fields: ["next_cursor", "has_more", "total_count"]
  acceptance_criteria:
    - "所有现有 offset/limit 参数返回 deprecation warning"
    - "新 cursor 参数通过集成测试"
    - "响应包含规定的元数据字段"
    - "P99 延迟不超过原实现的 110%"
```

这个规格文档既是**Agent 的输入**，也是**验证的基准**。它消除了 Prompt 中"暗示但没明说"的灰色地带。

### 3.2 第二层：技能即规格（mattpocock/skills 模式）

[mattpocock/skills](https://github.com/mattpocock/skills)（82,197⭐）走了另一条路：**把工程实践编码为 Agent 可执行的技能规格**。

这个项目的核心理念是：**好的 Agent 不是更强的模型，而是更好的技能定义。**

一个 skill 文件的本质是一份**行为规格**：

```markdown
# skill: react-component-review.md
# 当 Agent 审查 React 组件时，必须检查以下规格：

## 必须检查
- [ ] props 类型定义完整（no `any`）
- [ ] 副作用有清理函数
- [ ] 列表渲染使用稳定 key
- [ ] 状态更新不使用直接突变
- [ ] 自定义 hooks 遵循命名约定

## 常见反模式
- useEffect 中直接调用 setState 导致无限循环
- 在渲染函数中创建新对象/数组（破坏 memo）
- 将复杂计算放在渲染层而非 useMemo

## 输出格式
按"严重"、"警告"、"建议"三级输出，每条附带修复代码
```

这不是"建议"，这是**可执行的检查清单**。Agent 在审查代码时，不是"尽力而为"，而是**逐条验证**。

这种方法的精妙之处在于：**它把人类的工程判断力（engineering judgment）编码为机器可执行的规则。** 不是限制 Agent 的能力，而是给能力加上方向。

### 3.3 第三层：团队即规格（gstack 模式）

[Garry Tan](https://github.com/garrytan) 的 [gstack](https://github.com/garrytan/gstack)（96,720⭐）代表了最宏观的 Spec-Driven 视角：**把一个完整的工程团队的组织结构和职责编码为 Agent 技能集合**。

gstack 包含 23 个 opinionated 工具，每个扮演一个角色：

| 角色 | 功能 | 规格关注点 |
|------|------|------------|
| CEO | 战略决策与优先级 | 目标对齐、资源分配 |
| Designer | UI/UX 审查 | 设计系统一致性 |
| Eng Manager | 代码审查与架构 | 技术规范、代码质量 |
| Release Manager | 发布流程管理 | 版本控制、变更日志 |
| Doc Engineer | 文档生成与验证 | 文档完整性、准确性 |
| QA | 测试策略与执行 | 覆盖率、边界条件 |

这本质上是在说：**一个成功的 Agent 驱动开发流程，需要的不是更强的模型，而是一个由规格定义的"虚拟工程团队"，每个角色有明确的职责、检查标准和输出格式。**

---

## 四、深度技术分析：Spec-Driven vs Prompt-Driven 的能力对比

### 4.1 信息论视角

从信息论的角度看，Prompt-Driven 和 Spec-Driven 的根本差异在于**信息密度和信噪比**。

一个典型的开发任务 Prompt：
```
"帮我把用户列表 API 改成分页的，注意性能和兼容性"
```
信息量估算：约 15 个有效约束词，但**歧义度 > 60%**（"分页"可能指 5 种方案，"性能"没有量化标准，"兼容性"没有定义范围）。

等效的 Spec 文档：
```yaml
api: user-list
change: add-pagination
method: cursor-based
cursor_field: id
default_limit: 20
max_limit: 100
deprecation: offset-params
sunset: 2026-08-01
performance: P99 <= current * 1.1
compatibility: all-existing-endpoints
tests: integration + contract
```
信息量估算：约 12 个约束字段，但**歧义度 < 5%**（每个字段有明确的类型和值域）。

```
Spec-Driven 信息效率 = 有效约束 / 歧义度 ≈ 12 / 0.05 = 240
Prompt-Driven 信息效率 = 有效约束 / 歧义度 ≈ 15 / 0.60 = 25
```

**Spec 的信息效率是 Prompt 的近 10 倍。** 这不是因为 Spec 说了更多信息，而是因为它消除了歧义。

### 4.2 可靠性模型

让我们建立一个简单的可靠性模型。假设一个 Agent 完成开发任务需要经过 N 个决策点，每个决策点的正确率为 p：

```
P(任务成功) = p^N
```

对于 Prompt-Driven：
- 典型决策点 N ≈ 8-12（API 设计、分页方案、错误处理、测试策略、兼容性处理……）
- 每个决策点正确率 p ≈ 0.75（基于 Agent 对模糊意图的推断能力）
- **P(成功) = 0.75^10 ≈ 5.6%**

对于 Spec-Driven：
- 典型决策点 N ≈ 3-5（大部分决策已被规格确定）
- 每个决策点正确率 p ≈ 0.92（基于精确规格的执行能力）
- **P(成功) = 0.92^4 ≈ 71.6%**

这个简化模型解释了为什么 Spec-Driven 在实践中能带来**数量级的可靠性提升**——它通过前置决策，既减少了决策点数量，又提高了每个决策点的准确率。

### 4.3 与 VAKRA Benchmark 的关联

VAKRA Benchmark 揭示的失败模式中，"意图理解偏差"（22%）和"工具调用错误"（38%）合计占了 **60%** 的失败。这两类错误都可以通过 Spec-Driven 方法直接缓解：

- **意图理解偏差 → 规格消除歧义**：当 API 分页方式、页大小、兼容性策略在规格中明确定义时，Agent 不需要"猜测"用户的意图。
- **工具调用错误 → 规格定义接口契约**：当 API 的参数类型、返回值格式、错误码在规格中精确描述时，Agent 的工具调用准确率显著提升。

事实上，IBM Research 在 VAKRA 的 SEL-BIRD 任务集合中已经观察到了类似的趋势：**当工具接口有明确的 schema 定义时，Agent 的工具调用准确率从 52% 提升到 78%**。

---

## 五、实际案例：三个 Spec-Driven 的落地模式

### 5.1 模式一：规格优先的代码生成

这是 spec-kit 的核心模式。工作流如下：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  编写规格   │ ──→ │ Agent 生成  │ ──→ │ 规格验证    │ ──→ │ 人类审查    │
│  PRD/Tech   │     │ 代码 + 测试 │     │ 自动化检查  │     │ 规格迭代    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     ↑                                                            │
     └────────────────────────────────────────────────────────────┘
                        反馈循环
```

关键差异：在 Prompt-Driven 模式中，人类审查的是**代码**；在 Spec-Driven 模式中，人类审查的是**规格**。代码由规格保证正确性。

**实际收益**（基于社区报告的数据）：
- PR 审查时间减少 65%（审查规格 vs 审查代码）
- 返工率降低 72%（规格阶段的错误修复成本是代码阶段的 1/8）
- Agent 产出的一次通过率从 35% 提升到 78%

### 5.2 模式二：规格化的代码审查

这是 mattpocock/skills 的模式。不是让 Agent"尽力审查"，而是定义**审查规格**：

```markdown
# Code Review Spec
## Scope
- 仅审查本次 PR 的变更文件
- 忽略格式和 lint 问题（由 CI 处理）

## 检查项
### P0 - 必须阻断
- [ ] 安全漏洞（SQL 注入、XSS、硬编码密钥）
- [ ] 数据一致性破坏（无事务的多步写操作）
- [ ] 向后兼容性破坏（无迁移的 API 变更）

### P1 - 建议修复
- [ ] 性能回归（新增 N+1 查询、无分页的列表查询）
- [ ] 错误处理缺失（未处理的 Promise rejection、无 fallback）
- [ ] 测试覆盖率下降 > 2%

### P2 - 可选优化
- [ ] 代码可读性改进
- [ ] 命名一致性
- [ ] 注释补充

## 输出格式
按 P0 → P1 → P2 排序，每条附带：
- 问题描述
- 影响范围
- 修复建议（含代码）
- 严重性评级
```

这种方法的本质是**把高级工程师的审查判断力降维为可执行的检查清单**。不是替代工程师，而是让 Agent 的审查输出达到工程师的水准。

### 5.3 模式三：角色化的 Agent 编排

这是 gstack 的模式。把一个工程团队拆解为**角色化的 Agent 规格**：

```
User Request
     │
     ▼
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  CEO    │ ──→ │ Eng Mgr  │ ──→ │ Designer │ ──→ │  Coder   │
│ 拆解需求 │     │ 技术方案 │     │ UI 审查  │     │ 代码实现  │
└─────────┘     └──────────┘     └──────────┘     └──────────┘
                                                    │
                     ┌──────────┐     ┌──────────┐  │
                     │   QA     │ ←── │  Release │  │
                     │ 测试验证 │     │  管理发布 │  │
                     └──────────┘     └──────────┘  │
                                                    │
                     ┌──────────┐                   │
                     │   Doc    │ ←─────────────────┘
                     │ 文档生成 │
                     └──────────┘
```

每个角色有明确的**输入规格**、**输出规格**和**质量门槛**。这本质上是在用规格定义一个**虚拟工程组织的 SOP**。

---

## 六、行业影响：Spec-Driven 将如何重塑开发流程

### 6.1 开发者的角色转变

Spec-Driven Development 不会取代开发者，但会改变开发者的核心工作：

```
Prompt-Driven 时代：开发者 = 写 Prompt + 审查代码
Spec-Driven 时代： 开发者 = 写规格 + 审查规格
```

这意味着：
- **需求分析能力**比编码能力更重要
- **系统思维**比实现细节更重要
- **规格写作**（Spec Writing）将成为核心技能
- **验收标准设计**将成为关键能力

### 6.2 对 AI Agent 行业的影响

| 维度 | 当前状态 | Spec-Driven 时代 |
|------|----------|-----------------|
| 核心竞争力 | 模型能力 | 规格理解 + 执行可靠性 |
| 评估标准 | Benchmark 分数 | 规格满足率 |
| 商业模式 | API 调用计费 | 规格交付计费 |
| 开发者工具 | Prompt 工程工具 | 规格工程工具 |
| 质量保障 | 人工代码审查 | 自动化规格验证 |

### 6.3 对企业的启示

MIT Technology Review 在金融服务 AI 的文章中提到：

> "You can't just stop at explaining where the data came from and what it was transformed into... You need an auditable and governable way to explain what information the model found and the logic of why that data was right for the next step."

这段话同样适用于 Spec-Driven Development。在企业级场景中，Agent 的**决策可追溯性**和**结果可验证性**不是"加分项"，而是**合规要求**。规格文档天然提供了这种可追溯性——你可以追溯每一行代码到规格中的哪一条约束，每一个决策到规格中的哪一条授权。

---

## 七、挑战与局限

Spec-Driven Development 不是银弹。它有几个需要正视的挑战：

### 7.1 规格写作的成本

写一份好的规格比写一个 Prompt 难得多。它要求：
- 对系统的深入理解
- 对所有边界条件的枚举
- 对验收标准的精确量化

**短期成本**：规格写作可能比直接写代码花更多时间。
**长期收益**：规格的一次性投入可以在多次迭代中复用，摊薄成本。

### 7.2 规格的维护负担

规格不是一次性的。随着产品迭代，规格需要同步更新。这引入了新的**规格-代码同步**问题：

```
规格 v1.0 → 代码 v1.0 → 新需求 → ???
```

解决方案：**规格即代码（Spec-as-Code）**。把规格纳入版本控制，用自动化工具检测规格-代码偏离。spec-kit 已经在朝这个方向探索。

### 7.3 过度规格化的风险

不是所有决策都需要规格化。过度规格化会：
- 扼杀 Agent 的创造力
- 增加维护成本
- 减慢开发速度

**原则**：只规格化"不可逆的决策"和"高风险的约束"。对于探索性的、可以快速回滚的决策，保留 Prompt-Driven 的灵活性。

---

## 八、未来展望：Spec-Driven 的下一步

### 8.1 规格自动生成

当前的 Spec-Driven 依赖人类手写规格。下一步是**从需求描述自动生成规格草案**：

```
自然语言需求 → LLM 生成规格草案 → 人类审核/修改 → Agent 执行
```

这形成了一个**混合智能回路**：LLM 负责"从模糊到结构化"，人类负责"从结构化到精确化"，Agent 负责"从精确化到实现"。

### 8.2 规格市场

就像 mattpocock/skills 已经展示的，**规格（技能）可以共享和复用**。未来可能出现：
- 规格市场（Spec Marketplace）：可复用的 API 设计规范、安全审查规范、性能测试规范
- 规格组合：像 npm 包一样组合和继承规格
- 规格验证服务：第三方提供规格合规性审计

### 8.3 规格语言标准化

今天每个项目都有自己的规格格式。未来可能出现**规格描述语言（Specification Description Language, SDL）**：

```yaml
# 假想的 SDL
spec:
  version: "1.0"
  domain: "web-api"
  constraints:
    - type: security
      rules: [OWASP-Top10, data-encryption]
    - type: performance
      metrics: {P99_latency: "200ms", throughput: "1000rps"}
    - type: compatibility
      policy: "semantic-versioning"
  acceptance:
    - type: automated-tests
      coverage: 90%
    - type: contract-tests
      provider: "pact"
```

一旦规格语言标准化，规格就可以跨 Agent、跨工具、跨组织流转——这才是 Spec-Driven Development 的终极形态。

---

## 九、结论

Spec-Driven Development 不只是一个工具趋势。它是 AI Agent 工程从"玩具"走向"生产"的必经之路。

三个项目的爆发式增长——spec-kit（99K⭐）、gstack（97K⭐）、mattpocock/skills（82K⭐）——不是一个巧合。它们是同一个范式转移的三个侧面：

1. **spec-kit**：规格是开发的起点和终点
2. **mattpocock/skills**：工程实践需要被规格化为可执行的检查清单
3. **gstack**：工程组织需要被规格化为角色化的 Agent 协作流程

这个范式的核心信念很简单：**与其让 Agent 在模糊中猜测，不如在精确中执行。**

在 VAKRA Benchmark 告诉我们"Agent 在 8000+ 真实 API 面前集体崩溃"的今天，这个信念不是一种选择，而是一种生存策略。

Prompt-Driven 让我们看到了 AI Agent 的可能性。Spec-Driven 将让我们兑现这种可能性。

---

*本文基于 2026 年 5 月 15 日的公开数据和项目信息撰写。引用的 Star 数据为当日 GitHub 实时数据。*
