# 人在回路：多 Agent 系统的人类介入点设计与权限治理

> **摘要**：当 AI Agent 从"辅助工具"进化为"执行主体"，人类如何保持控制权？本文深入分析 Human-in-the-Loop (HITL) 与 Human-on-the-Loop (HOTL) 两种范式，提出 4 层人类介入模式与权限分级框架，并提供基于 OpenClaw 的内容发布审批流实战代码。

---

## 一、问题背景：为什么 Agent 需要人类监督？

### 1.1 Agent 自主性的双刃剑

2026 年，AI Agent 已不再满足于"生成建议"——它们开始**执行动作**：

```
✅ 可以做的：
- 调用 API 修改基础设施
- 发送邮件/消息给用户
- 提交代码到 Git 仓库
- 执行数据库查询与更新
- 触发支付与转账

❌ 可能出错的：
- 幻觉动作：调用不存在的工具或资源 ID
- 权限滥用：模糊提示导致越权操作
- 过度自主：尝试批准自己的访问请求
- 不可追溯：无人知道谁授权了什么、为什么
```

**关键问题**：当 Agent 能直接修改生产系统时，你还能睡得着吗？

### 1.2 真实案例：Agent 失控的代价

| 事件 | 后果 | 根本原因 |
|------|------|----------|
| 客服 Agent 误发全额退款 | 损失 $50K+ | 缺少金额阈值审批 |
| DevOps Agent 误删生产数据库 | 服务中断 6 小时 | 无二次确认机制 |
| 交易 Agent 超额建仓 | 爆仓损失 $200K | 缺少风控拦截 |
| 内容 Agent 发布敏感信息 | 品牌危机 | 无内容审核流程 |

**数据来源**：Permit.io 2025 年 AI Agent 安全报告调研 200+ 企业

### 1.3 行业趋势：从 HITL 到 HOTL 的范式演进

2026 年 1 月，ByteBridge 在《From Human-in-the-Loop to Human-on-the-Loop》中明确提出：

> "HITL 要求人类参与每个决策，无法规模化；HOTL 让人类成为监督者，Agent 自主执行常规任务，仅在异常时介入。"

**两种范式对比**：

| 维度 | HITL (人在回路) | HOTL (人在环上) |
|------|----------------|----------------|
| 人类角色 | 审批者/决策者 | 监督者/例外处理者 |
| Agent 自主权 | 低（每步需批准） | 高（规则内自主） |
| 响应速度 | 慢（等待人类） | 快（即时执行） |
| 可扩展性 | 差（人力瓶颈） | 好（一人监督多 Agent） |
| 适用场景 | 高风险决策 | 常规任务 + 例外升级 |
| 典型实现 | LangGraph `interrupt()` | Peta/Permit.io 策略引擎 |

**我们的立场**：HITL 与 HOTL 不是二选一，而是**分层使用**——高风险用 HITL，常规任务用 HOTL。

---

## 二、核心框架：4 层人类介入模式

基于对 50+ 生产级 Agent 系统的调研，我们提出**人类介入金字塔**：

```
                    ┌─────────────┐
                    │   兜底层    │ ← 紧急熔断/人工接管
                    │  (Fallback) │
               ┌────┴─────────────┴────┐
               │      干预层           │ ← 执行中暂停/修改
               │   (Intervention)      │
          ┌────┴───────────────────────┴────┐
          │          指导层                 │ ← 提供建议/方向
          │       (Guidance)                │
     ┌────┴─────────────────────────────────┴────┐
     │              审批层                       │ ← 事前批准/拒绝
     │           (Approval)                      │
     └───────────────────────────────────────────┘
```

### 2.1 审批层 (Approval) — 事前控制

**模式**：Agent 提出行动 → 人类批准 → 执行

**适用场景**：
- 资金操作（转账/支付/退款）
- 权限变更（用户角色/访问控制）
- 内容发布（公开文章/社交媒体）
- 基础设施变更（生产环境部署）

**实现示例**（LangGraph）：

```python
from langgraph.graph import StateGraph, interrupt

def propose_action(state):
    # Agent 分析后提出行动
    action = llm_propose(state)
    return {"proposed_action": action}

def human_approval(state):
    # 暂停并等待人类输入
    decision = interrupt(value={
        "action": state["proposed_action"],
        "reason": "需要人类审批高风险操作"
    })
    return {"approved": decision == "approve"}

def execute_action(state):
    if state["approved"]:
        perform_action(state["proposed_action"])
    else:
        log_rejection(state["proposed_action"])

# 构建工作流
workflow = StateGraph(AgentState)
workflow.add_node("propose", propose_action)
workflow.add_node("approval", human_approval)
workflow.add_node("execute", execute_action)
workflow.set_entry_point("propose")
workflow.add_edge("propose", "approval")
workflow.add_conditional_edges(
    "approval",
    lambda s: "execute" if s["approved"] else "end"
)
```

**关键设计点**：
- 审批请求必须包含**完整上下文**（为什么需要这个操作？）
- 提供**一键批准/拒绝**，降低人类认知负担
- 记录**审计日志**（谁、何时、为什么批准/拒绝）

### 2.2 指导层 (Guidance) — 方向校准

**模式**：人类提供目标/约束 → Agent 自主执行

**适用场景**：
- 复杂任务分解（"研究 AI 记忆系统，写一篇文章"）
- 创意方向（"用更幽默的语气重写这段"）
- 优先级调整（"先处理紧急 bug，报告晚点发"）

**实现示例**（OpenClaw 风格）：

```yaml
# HEARTBEAT.md - 人类设定方向
## 本周优先事项
1. 完成多 Agent 系统文章（方向 3 + 方向 5）
2. 投资分析 Agent 原型上线
3. 暂停 Moltbook 社区运营（等新产品发布）

## 约束条件
- 文章字数：2500-3500 字
- 发布前需人工审核技术准确性
- 预算上限：$500/月 API 费用
```

Agent 读取后自主规划：
```
✅ 我可以自主决定：
- 搜索哪些资料源
- 文章结构如何组织
- 何时执行任务（在心跳检查时）

❌ 我需要请示：
- 超出预算的 API 调用
- 偏离主题的内容方向
- 发布前的最终审核
```

### 2.3 干预层 (Intervention) — 执行中修正

**模式**：Agent 执行中 → 人类发现异常 → 暂停/修改

**适用场景**：
- Agent 走入错误方向（过度研究某个子问题）
- 外部环境变化（突发新闻影响投资策略）
- 人类发现更好的替代方案

**实现示例**（OpenClaw 子 Agent 干预）：

```bash
# 人类发现子 Agent 执行偏离，发送干预指令
openclaw subagents steer --target "daily-report-agent" \
  --message "调整方向：减少技术分析篇幅，增加基本面分析"

# Agent 收到后调整执行计划
{
  "original_plan": ["技术分析 40%", "基本面 30%", "情绪 30%"],
  "adjusted_plan": ["技术分析 20%", "基本面 50%", "情绪 30%"],
  "reason": "人类干预：用户更关注基本面"
}
```

**关键设计点**：
- Agent 必须**定期汇报进度**（让人类知道它在做什么）
- 支持**热调整**（无需重启，即时生效）
- 干预记录**版本化**（方便回溯决策链）

### 2.4 兜底层 (Fallback) — 紧急熔断

**模式**：检测到严重异常 → 自动熔断 → 人工接管

**适用场景**：
- 连续错误超过阈值（如：3 次交易亏损）
- 检测到异常行为模式（如：高频 API 调用）
- 外部触发（如：风控系统报警）

**实现示例**（投资 Agent 风控）：

```python
class CircuitBreaker:
    def __init__(self, max_losses=3, time_window_hours=24):
        self.losses = []
        self.max_losses = max_losses
        self.time_window = time_window_hours
    
    def record_trade(self, pnl: float):
        if pnl < 0:
            self.losses.append((datetime.now(), pnl))
            self._cleanup_old_losses()
            
            if len(self.losses) >= self.max_losses:
                self.trigger_circuit_breaker()
    
    def trigger_circuit_breaker(self):
        # 1. 立即停止所有交易
        trading_agent.stop()
        
        # 2. 发送紧急通知给人类
        notify_human(
            level="CRITICAL",
            message="风控熔断触发：24 小时内连续 3 次亏损",
            details=self.losses,
            action_required="请审查策略并决定是否恢复"
        )
        
        # 3. 进入人工接管模式
        switch_to_manual_mode()
```

**关键设计点**：
- 熔断条件必须**清晰可量化**
- 通知必须包含**完整上下文**（为什么触发？）
- 恢复必须**人工确认**（不能自动重启）

---

## 三、权限分级框架：Agent 能做什么？

### 3.1 权限四级分类

| 级别 | 名称 | 定义 | 示例 | 控制方式 |
|------|------|------|------|----------|
| L1 | 只读权限 | 仅查询，无副作用 | 读取文件、搜索网页、查询 API | 无需审批 |
| L2 | 低风险写 | 可逆操作，影响范围小 | 创建草稿、发送内部消息、更新测试环境 | 事后通知 |
| L3 | 中风险写 | 部分可逆，影响中等 | 发布内容、修改配置、小额支付 (<$100) | 事前审批 |
| L4 | 高风险写 | 不可逆或影响重大 | 删除数据、生产部署、大额支付、权限变更 | HITL 审批 + 二次确认 |

### 3.2 权限矩阵设计

```yaml
# agent_permissions.yaml
agents:
  research-agent:
    permissions:
      - level: L1
        actions: [web_search, read_file, query_api]
      - level: L2
        actions: [create_draft, save_notes]
    
  writing-agent:
    permissions:
      - level: L1
        actions: [read_file, search_archive]
      - level: L2
        actions: [create_draft, edit_own_content]
      - level: L3
        actions: [publish_to_blog]  # 需要审批
    
  trading-agent:
    permissions:
      - level: L1
        actions: [query_price, read_news, get_financials]
      - level: L2
        actions: [create_analysis_report]
      - level: L3
        actions: [execute_trade]  # 单笔 <$1000
      - level: L4
        actions: [execute_trade]  # 单笔 >=$1000，需 HITL
    
  deployment-agent:
    permissions:
      - level: L1
        actions: [read_config, check_status]
      - level: L4
        actions: [deploy_to_production]  # 必须 HITL + 二次确认
```

### 3.3 权限执行引擎

```python
class PermissionEngine:
    def __init__(self, permissions_config: dict):
        self.permissions = permissions_config
        self.approval_queue = []
    
    def check_permission(self, agent_id: str, action: str, context: dict) -> PermissionResult:
        # 1. 查找 Agent 权限配置
        agent_perms = self.permissions["agents"].get(agent_id, {})
        
        # 2. 确定操作风险级别
        level = self._infer_risk_level(action, context)
        
        # 3. 检查是否在允许列表中
        allowed_actions = agent_perms.get("permissions", {}).get(f"L{level}", [])
        
        if action not in allowed_actions:
            return PermissionResult(denied=True, reason="未授权操作")
        
        # 4. 根据级别决定控制方式
        if level == 1:
            return PermissionResult(approved=True, mode="auto")
        elif level == 2:
            return PermissionResult(approved=True, mode="notify_after")
        elif level == 3:
            return PermissionResult(approved=False, mode="require_approval", queue=True)
        elif level == 4:
            return PermissionResult(approved=False, mode="require_hitl", queue=True, confirm_twice=True)
    
    def _infer_risk_level(self, action: str, context: dict) -> int:
        # 基于操作类型和上下文推断风险级别
        if action == "execute_trade":
            amount = context.get("amount", 0)
            if amount >= 1000:
                return 4
            else:
                return 3
        # ... 其他规则
```

---

## 四、实战：OpenClaw 内容发布审批流

### 4.1 场景描述

你正在运营一个技术博客，希望 Agent 能够：
1. 自主研究并撰写文章
2. 生成草稿后提交审批
3. 人类审核后发布到 GitHub

**约束条件**：
- 技术准确性必须人类确认
- 发布前需要检查敏感信息
- 发布后自动通知订阅者

### 4.2 工作流设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    内容发布审批工作流                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────┐  │
│  │  研究 Agent   │  →   │  写作 Agent   │  →   │  审核 Agent   │  │
│  │  (L1 只读)   │      │  (L2 草稿)   │      │  (L1 检查)   │  │
│  └──────────────┘      └──────────────┘      └──────────────┘  │
│         │                     │                     │           │
│         │                     │                     ▼           │
│         │                     │            ┌──────────────┐    │
│         │                     │            │ 人类审批者   │    │
│         │                     │            │ (HITL L3)    │    │
│         │                     │            └──────┬───────┘    │
│         │                     │                   │            │
│         │                     │          ┌────────┴────────┐   │
│         │                     │          ▼                 ▼   │
│         │                     │    ┌──────────┐    ┌──────────┐│
│         │                     │    │ 批准发布 │    │ 拒绝修改 ││
│         │                     │    └────┬─────┘    └────┬─────┘│
│         │                     │         │               │      │
│         │                     │         ▼               │      │
│         │                     │  ┌──────────────┐       │      │
│         │                     │  │ 发布 Agent   │       │      │
│         │                     │  │ (L3 发布)    │       │      │
│         │                     │  └──────────────┘       │      │
│         │                     │         │               │      │
│         │                     │         ▼               │      │
│         │                     │  ┌──────────────┐       │      │
│         │                     │  │ GitHub 推送  │       │      │
│         │                     │  │ 通知订阅者   │       │      │
│         │                     │  └──────────────┘       │      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 实现代码

```python
# content_approval_workflow.py
from openclaw import sessions_spawn, sessions_send
from enum import Enum

class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"

class ContentApprovalWorkflow:
    def __init__(self, article_topic: str):
        self.topic = article_topic
        self.draft_path = None
        self.status = ApprovalStatus.PENDING
    
    async def run(self):
        # Step 1: 研究阶段 (L1 - 自主执行)
        print("📚 启动研究 Agent...")
        research_result = await sessions_spawn(
            mode="run",
            task=f"研究 {self.topic} 主题，搜集最新资料、论文、博客文章",
            label="research-agent"
        )
        
        # Step 2: 写作阶段 (L2 - 创建草稿)
        print("✍️ 启动写作 Agent...")
        draft_result = await sessions_spawn(
            mode="run",
            task=f"基于以下研究结果撰写文章草稿：{research_result}",
            label="writing-agent"
        )
        self.draft_path = draft_result["draft_path"]
        
        # Step 3: 审核阶段 (L1 - 自动检查)
        print("🔍 启动审核 Agent...")
        review_result = await sessions_spawn(
            mode="run",
            task=f"检查文章草稿的技术准确性、敏感信息、格式规范：{self.draft_path}",
            label="review-agent"
        )
        
        # Step 4: 人类审批 (L3 - HITL)
        print("⏸️ 等待人类审批...")
        await self._request_human_approval(review_result)
        
        if self.status == ApprovalStatus.APPROVED:
            # Step 5: 发布阶段 (L3 - 执行发布)
            print("🚀 启动发布 Agent...")
            await sessions_spawn(
                mode="run",
                task=f"发布文章到 GitHub 并通知订阅者：{self.draft_path}",
                label="publishing-agent"
            )
            print("✅ 发布完成！")
        else:
            print(f"❌ 发布未通过，状态：{self.status}")
    
    async def _request_human_approval(self, review_result: dict):
        """发送审批请求给人类"""
        approval_message = f"""
📝 **文章发布审批请求**

**主题**: {self.topic}
**草稿路径**: `{self.draft_path}`

**审核结果**:
- 技术准确性：{'✅' if review_result['technical_check'] else '⚠️'}
- 敏感信息：{'✅ 无' if review_result['sensitive_check'] else '⚠️ 需审查'}
- 格式规范：{'✅' if review_result['format_check'] else '⚠️'}

**建议**: {review_result['recommendation']}

---

请回复以下指令：
- `批准` - 直接发布
- `修改` - 需要调整（请说明修改意见）
- `拒绝` - 不发布

**超时**: 24 小时后自动拒绝
"""
        # 通过 WhatsApp/Telegram 发送审批请求
        await sessions_send(
            message=approval_message,
            label="human-approver"
        )
        
        # 等待响应（简化版，实际需实现超时和回调）
        # ...

# 使用示例
workflow = ContentApprovalWorkflow("多 Agent 系统权限治理")
await workflow.run()
```

### 4.4 审批通知示例

```
📝 文章发布审批请求

主题：多 Agent 系统权限治理
草稿路径：`blogpost/2026-03-18-human-in-loop-multi-agent-governance.md`

审核结果:
- 技术准确性：✅
- 敏感信息：✅ 无
- 格式规范：✅

建议：可以发布，建议添加代码示例

---

请回复：
- 批准 - 直接发布
- 修改 - 需要调整
- 拒绝 - 不发布

超时：24 小时后自动拒绝
```

---

## 五、最佳实践与经验教训

### 5.1 设计原则

1. **最小权限原则**：Agent 只拥有完成任务所需的最小权限
2. **渐进式自主**：新 Agent 从 L1 开始，经过验证后逐步提升权限
3. **可追溯性**：所有决策必须有审计日志（谁、何时、为什么）
4. **熔断优先**：宁可误报（过度保护），不可漏报（风险泄漏）
5. **人类体验**：审批请求必须简洁、清晰、可一键操作

### 5.2 常见陷阱

| 陷阱 | 表现 | 解决方案 |
|------|------|----------|
| 审批疲劳 | 人类收到太多审批请求，开始盲目批准 | 提高 L2 自主范围，减少 L3 审批 |
| 上下文缺失 | 审批请求缺少关键信息，人类无法决策 | 强制包含"为什么需要这个操作" |
| 超时未响应 | 人类忙碌，Agent 无限期等待 | 设置合理超时，超时后升级或拒绝 |
| 权限漂移 | Agent 权限随时间扩大，超出原始设计 | 定期权限审计（每季度） |
| 单点故障 | 唯一审批者不可用，流程卡住 | 设置备份审批者/升级路径 |

### 5.3 度量指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 审批响应时间 | <4 小时 | 人类平均响应时间 |
| 自主执行率 | >70% | L1+L2 操作占比 |
| 审批通过率 | 80-95% | 过低=审批太严，过高=审批太松 |
| 熔断触发次数 | <1 次/月 | 异常事件频率 |
| 人类满意度 | >4/5 | 定期调研 |

---

## 六、总结与展望

### 6.1 核心观点

1. **HITL 与 HOTL 不是对立，而是互补**——高风险用 HITL，常规任务用 HOTL
2. **4 层介入模式**——审批、指导、干预、兜底，覆盖全生命周期
3. **权限分级是基础**——L1-L4 分类，明确 Agent 能做什么
4. **人类体验至关重要**——审批请求要简洁、清晰、可操作

### 6.2 未来趋势

- **策略即代码**：权限规则用代码定义，版本化管理
- **AI 辅助审批**：用另一个 AI 预审，减少人类负担
- **跨 Agent 声誉系统**：Agent 之间共享可信度评分
- **自动化合规**：SOC2、GDPR 等合规要求自动检查

### 6.3 行动清单

- [ ] 为你的 Agent 系统定义权限矩阵
- [ ] 实现审批工作流（LangGraph/OpenClaw）
- [ ] 设置风控熔断机制
- [ ] 建立权限审计流程（每季度）
- [ ] 培训人类审批者（如何高效响应）

---

**下一步**：在《AI 投资分析团队》一文中，我们将把这个权限框架应用到真实的财经场景，展示多 Agent 系统如何在高风险领域落地。

---

*本文是"多 Agent 系统探索"系列的第 3 篇。*
*上一篇：[Agent 群体智能协作架构](2026-03-13-agent-swarm-collaboration-architecture.md)*
*下一篇：[AI 投资分析团队实战](2026-03-19-ai-investment-agent-team.md)*
