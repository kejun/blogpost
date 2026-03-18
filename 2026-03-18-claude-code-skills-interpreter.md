# Claude Code Skills 实战指南：从理解到应用

**原文来源：** Anthropic 工程师 Thariq (@trq212) 推文系列  
**解读整理：** 克军  
**日期：** 2026 年 3 月 18 日

---

## 一、一句话理解 Skills

> **Skills 不是"提示词模板"，而是"可执行的知识包"**

想象一下：你有一个新入职的工程师，你会怎么让他快速上手？

- ❌ 错误方式：给他一份 100 页的文档让他读完
- ✅ 正确方式：给他一个工作区，里面有代码示例、脚本工具、常见问题清单，告诉他"遇到 X 问题时看 Y 文件，需要 Z 功能时运行这个脚本"

**Skills 就是后者** —— 它是一个文件夹，里面可以包含：
- `SKILL.md` — 主指令文件
- `references/` — 参考文档、API 说明
- `assets/` — 模板文件
- `scripts/` — 可执行脚本
- `config.json` — 配置信息

---

## 二、为什么 Skills 重要？

### 问题：Claude 知道很多，但不知道"你的"方式

Claude 懂编程，懂 FastAPI，懂 Python 最佳实践。但它不知道：

- 你们团队的命名约定是什么
- 你们内部库的坑在哪里
- 你们的部署流程有什么特殊要求
- 哪些错误是你们踩过一定要避免的

### Skills 的价值：把团队知识"产品化"

| 没有 Skills | 有 Skills |
|------------|----------|
| 每个新人重复问同样的问题 | 新人装一个 Skill 就懂团队规范 |
| 资深工程师反复回答相同问题 | 问题被沉淀到 Skill 里，一次编写多次复用 |
| Claude 按通用方式写代码 | Claude 按你们团队的方式写代码 |
| 知识散落在 Slack、文档、人脑子里 | 知识集中在 Skills 文件夹，可版本控制、可分发 |

---

## 三、9 种 Skills 类型：你应该从哪种开始？

不是所有 Skills 都适合你的团队。根据 Anthropic 的经验，**从这 3 种开始最有效**：

### 🥇 优先级 1：库和 API 参考（最快见效）

**适用场景：** 团队有内部库、常用第三方库、或 Claude 经常用错的 API

**示例结构：**
```
skills/billing-lib/
├── SKILL.md          # 主指令
└── references/
    ├── conventions.md    # 约定和最佳实践
    └── gotchas.md        # 常见陷阱
```

**SKILL.md 核心内容：**
```markdown
你是计费系统专家。当用户编写或审查计费相关代码时：

1. 加载 references/conventions.md 了解最佳实践
2. 检查 references/gotchas.md 避免已知陷阱
3. 所有计费函数必须包含金额校验和日志记录
```

**为什么先做这个：** 投入小（几小时），见效快（立刻减少错误），复用高（每次写相关代码都触发）

---

### 🥈 优先级 2：产品验证（最容易被忽视）

**适用场景：** 需要确保 Claude 的输出能正常工作，尤其是 UI、API 端点等

**示例结构：**
```
skills/signup-verifier/
├── SKILL.md
└── scripts/
    └── verify-signup.sh   # 自动化验证脚本
```

**核心价值：** 让 Claude 自己验证自己的工作，而不是等人 review 时发现问题

**Anthropic 建议：** 值得让工程师花一周时间把验证 Skills 做好 —— 这比事后修复 bug 便宜得多

---

### 🥉 优先级 3：业务流程自动化（最节省时间）

**适用场景：** 团队有重复性工作流，如发站会、开工单、写周报

**示例：** `standup-post` Skill
- 自动聚合昨天的 GitHub 活动
- 拉取 Jira/Linear 中完成的工单
- 生成格式化的站会帖子
- 发布到指定 Slack 频道

**为什么有效：** 把 15 分钟的手动工作变成一条命令

---

## 四、写好 Skills 的 5 个关键技巧

### 技巧 1：不要陈述显而易见的内容

❌ 错误示例：
```markdown
你是 Python 专家。写代码时要：
- 使用正确的语法
- 遵循 PEP 8
- 写清晰的变量名
```

✅ 正确示例：
```markdown
你是 FastAPI 专家。我们的团队约定：
- 所有端点必须使用 Annotated 风格依赖注入
- 响应模型必须显式声明，禁止隐式推断
- 错误处理统一使用 HTTPException，禁止裸 raise
```

**原则：** Skills 的价值在于**差异化知识** —— Claude 已经知道的不要写，写它不知道的。

---

### 技巧 2：建立 Gotchas 部分（最高价值内容）

Gotchas 是 Skills 中信号最强的部分。每次 Claude 犯错，就把这个错误加进去。

**示例：**
```markdown
## 常见陷阱

1. **金额精度问题**：所有金额计算必须使用 Decimal，禁止 float
   - 错误：`total = price * quantity`
   - 正确：`total = Decimal(str(price)) * Decimal(str(quantity))`

2. **时区处理**：所有时间戳必须存储为 UTC，展示时转换
   - 错误：`datetime.now()`
   - 正确：`datetime.now(timezone.utc)`

3. **日志格式**：必须包含 request_id 用于追踪
   - 错误：`logger.info("processed")`
   - 正确：`logger.info("processed", extra={"request_id": ctx.request_id})`
```

**迭代方式：** 每次 Claude 犯同样的错误，就更新 Gotchas —— Skill 会随时间变聪明。

---

### 技巧 3：使用渐进式披露（控制上下文大小）

不要把所有内容塞进 SKILL.md。用文件系统组织，让 Claude 按需读取。

**示例结构：**
```
skills/api-expert/
├── SKILL.md              # 核心指令（保持简短）
├── references/
│   ├── conventions.md    # 详细约定
│   ├── api-patterns.md   # API 设计模式
│   └── gotchas.md        # 陷阱列表
├── assets/
│   └── endpoint-template.md  # 端点模板
└── scripts/
    └── lint-api.sh       # 校验脚本
```

**SKILL.md 只写：**
```markdown
你是 API 专家。当编写或审查 API 代码时：

1. 加载 references/conventions.md 了解约定
2. 使用 assets/endpoint-template.md 作为起点
3. 完成后运行 scripts/lint-api.sh 校验
4. 检查 references/gotchas.md 避免已知问题
```

**好处：** Claude 只在需要时读取详细文件，节省上下文，提高响应速度。

---

### 技巧 4：描述字段是给模型看的（不是给人看的）

❌ 错误描述：
```yaml
description: 这个 Skill 用于 API 开发
```

✅ 正确描述：
```yaml
description: 当用户要创建新的 API 端点、修改现有端点、或审查 API 代码时使用
```

**原因：** Claude Code 启动时会扫描所有 Skills 的描述来决定激活哪个。描述应该说明**何时触发**，而不是**是什么**。

---

### 技巧 5：存储脚本，让 Claude 组合而非重构

给 Claude 现成的代码，让它专注于组合而非从头编写。

**示例：** 数据科学 Skill 中提供辅助函数库
```python
# scripts/data_utils.py
def fetch_events(start_date, end_date, event_types):
    """从事件源获取数据"""
    ...

def calculate_retention(cohort_id, periods):
    """计算留存率"""
    ...

def plot_conversion_funnel(data):
    """绘制转化漏斗"""
    ...
```

**Claude 可以：**
```python
# 根据用户请求"分析上周的转化情况"自动生成
from data_utils import fetch_events, plot_conversion_funnel

events = fetch_events('2026-03-10', '2026-03-17', ['signup', 'activation', 'purchase'])
plot_conversion_funnel(events)
```

**价值：** Claude 把时间花在理解需求和组合功能上，而不是重写基础函数。

---

## 五、实际应用场景：数据库开发者的 Skills

作为数据库产品设计和开发者，你可以创建这些 Skills：

### 1. SQL 规范 Skill
```yaml
name: sql-expert
description: 当用户编写 SQL 查询、设计表结构、或优化数据库性能时使用
```
- 团队的 SQL 风格约定
- 索引设计最佳实践
- 常见查询陷阱（N+1、全表扫描等）

### 2. 迁移脚本 Skill
```yaml
name: migration-helper
description: 当用户需要创建数据库迁移、修改表结构、或回滚变更时使用
```
- 迁移文件模板
- 向后兼容检查清单
- 回滚脚本生成

### 3. 性能分析 Skill
```yaml
name: query-profiler
description: 当用户需要分析慢查询、优化索引、或排查性能问题时使用
```
- EXPLAIN 输出解读指南
- 索引选择策略
- 常见性能问题诊断流程

### 4. 数据验证 Skill
```yaml
name: data-verifier
description: 当用户需要验证数据完整性、检查约束、或审计数据质量时使用
```
- 数据质量检查脚本
- 约束验证清单
- 异常数据报告模板

---

## 六、分发策略：小团队 vs 大团队

### 小团队（<20 人，<10 仓库）
**推荐：** 直接检入仓库
```
your-repo/
├── .claude/skills/
│   ├── sql-expert/
│   └── migration-helper/
└── src/
```

**优点：** 简单，版本与代码同步
**缺点：** 每个 Skill 增加一点上下文，仓库多了会累积

### 大团队（>20 人，>10 仓库）
**推荐：** 内部插件市场
```
skills-marketplace/
├── database/
│   ├── sql-expert/
│   └── migration-helper/
├── frontend/
│   └── design-system/
└── infra/
    └── deploy-helper/
```

**优点：** 集中管理，按需安装，易于发现
**缺点：** 需要额外基础设施

---

## 七、衡量 Skills 的效果

Anthropic 使用 PreToolUse 钩子记录 Skill 使用情况。你可以：

1. **追踪触发频率：** 哪个 Skill 最常用？
2. **识别触发不足：** 预期会用的 Skill 为什么没被触发？（可能是描述问题）
3. **收集反馈：** 用户遇到什么问题？更新 Gotchas

**简单方法：** 在 Skill 目录加一个 `usage.log`，每次触发时追加记录。

---

## 八、开始行动：你的第一个 Skill

### 步骤 1：选一个痛点
想一个你和团队经常重复的问题或任务。

### 步骤 2：创建文件夹
```bash
mkdir -p skills/your-skill-name/references
```

### 步骤 3：写 SKILL.md
```markdown
# skills/your-skill-name/SKILL.md
---
name: your-skill-name
description: 当用户要 [具体场景] 时使用
---

你是 [角色]。当处理 [场景] 时：

1. [步骤 1]
2. [步骤 2]
3. [步骤 3]

## 注意事项
- [注意 1]
- [注意 2]
```

### 步骤 4：测试并迭代
用它几次，记录 Claude 犯的错误，更新 Gotchas。

### 步骤 5：分享
检入仓库或发布到内部市场。

---

## 九、常见误区

### ❌ 误区 1：把 Skills 当文档写
Skills 是**可执行的指令**，不是参考文档。每条内容都应该能指导 Claude 的行动。

### ❌ 误区 2：一开始就追求完美
Anthropic 的 Skills 都是从几行开始，随时间迭代变好的。先发布，再完善。

### ❌ 误区 3：过度限制 Claude
给信息，给约束，但保留灵活性。Skills 应该指导而非束缚。

### ❌ 误区 4：不更新 Gotchas
Skills 是活的文档。每次 Claude 犯新错误，就更新 —— 这是 Skills 变聪明的方式。

---

## 十、总结

**Skills 的本质：** 把团队知识打包成可执行、可分发、可迭代的"知识产品"

**核心价值：**
1. 减少重复问题
2. 统一团队规范
3. 加速新人上手
4. 让 Claude 按你们的方式工作

**开始建议：**
1. 从库/API 参考开始（最快见效）
2. 建立 Gotchas 部分（持续迭代）
3. 使用渐进式披露（控制上下文）
4. 先发布再完善（不要追求完美）

**最终目标：** 让团队知识不再依赖个人记忆，而是沉淀为可复用的 Skills，让每个成员（包括 AI）都能站在团队的肩膀上工作。

---

*基于 Anthropic 工程师 Thariq 的推文系列整理，结合数据库开发场景解读*
