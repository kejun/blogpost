# ClawTeam 深度调研：Agent 群体智能的极简实现

**调研对象：** https://github.com/HKUDS/ClawTeam  
**调研时间：** 2026 年 3 月 18 日  
**项目版本：** v0.1.2 (PyPI) / v0.3 (Roadmap)  
**整理：** 克军

---

## 一、项目定位：让 Agent 自主组队

**ClawTeam** 是一个**框架无关的多 Agent 协调 CLI 工具**，旨在实现"Agent 群体智能"（Swarm Intelligence）。

### 核心理念

> 今天的 Agent 各自为战 🤖，明天的 Agent 将协同作战 🦞🤖🤖🤖

人类只需提供目标，Agent 群体自动完成剩余的一切：
- 自主组建团队
- 分配任务
- 协同工作
- 共享发现
- 收敛到最优方案

### 关键差异化

| 维度 | ClawTeam | 其他多 Agent 框架 |
|-----|---------|-----------------|
| **使用者** | **AI Agent 自身** | 人类编写编排代码 |
| **安装** | `pip install` + 一句提示词 | Docker、云 API、YAML 配置 |
| **基础设施** | 文件系统 + tmux | Redis、消息队列、数据库 |
| **Agent 支持** | 任意 CLI Agent | 仅限特定框架 |
| **隔离机制** | Git Worktree（真实分支） | 容器或虚拟环境 |
| **协调方式** | 群体自组织 CLI 命令 | 硬编码编排逻辑 |

---

## 二、核心功能详解

### 1. Agent 自组织

Leader Agent 可以创建和管理 Worker Agent，无需人类干预：

```bash
# Leader Agent 执行：
clawteam spawn --team my-team \
  --agent-name worker1 \
  --task "实现认证模块"
```

**关键特性：**
- 自动注入协调提示词，零手动配置
- Worker 自主报告状态、结果和空闲状态
- 支持任意 CLI Agent（Claude Code、Codex、OpenClaw 等）

### 2. 工作空间隔离

每个 Agent 拥有独立的 **Git Worktree**：

```bash
# 分支命名规范
clawteam/{team}/{agent}

# 例如：
clawteam/webapp/backend1
clawteam/webapp/frontend
clawteam/webapp/tester
```

**优势：**
- 避免并行 Agent 之间的代码冲突
- 支持 checkpoint、merge、cleanup 命令
- 真实的分支隔离，非虚拟环境

### 3. 任务跟踪与依赖

共享看板，支持依赖链：

```bash
# 创建带依赖的任务
clawteam task create my-team "实现 JWT 认证" \
  -o backend1 \
  --blocked-by task-001  # 等待 API 设计完成

# 完成任务时自动解除下游阻塞
clawteam task update my-team task-001 --status completed
```

**状态流转：**
```
pending → in_progress → completed / blocked
```

### 4. Agent 间通信

点对点收件箱 + 广播：

```bash
# 发送消息
clawteam inbox send my-team worker1 "开始实现认证模块"

# 广播到所有成员
clawteam inbox broadcast my-team "紧急：发现安全漏洞"

# 接收消息（消费）
clawteam inbox receive my-team

# 查看消息（只读）
clawteam inbox peek my-team
```

**传输模式：**
- **file**（默认）：JSON 文件，适用于单机/共享文件系统
- **p2p**：ZeroMQ PUSH/PULL，带离线回退

### 5. 监控与仪表板

```bash
# 终端看板
clawteam board show my-team

# 自动刷新（3 秒间隔）
clawteam board live my-team --interval 3

# 平铺 tmux 视图（同时观看所有 Agent）
clawteam board attach my-team

# Web UI（SSE 实时推送）
clawteam board serve --port 8080
```

### 6. 团队模板

TOML 文件定义团队原型，一键启动：

```bash
# 启动内置的 AI 对冲基金模板（7 个 Agent）
clawteam launch hedge-fund \
  --team fund1 \
  --goal "分析 AAPL、MSFT、NVDA 2026 Q2"
```

**内置模板：**
- AI 对冲基金（7 Agent）
- 代码审查团队
- 研究论文团队
- 自定义模板

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   CLI / Agent 上层调用                    │
│           (commands.py, watcher.py, lifecycle.py)        │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    MailboxManager                        │
│  - 构建 TeamMessage (Pydantic 模型)                      │
│  - 序列化为 JSON bytes                                   │
│  - 委托 I/O 给 self._transport                          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     Transport (ABC)                      │
├───────────────────┬─────────────────────────────────────┤
│   FileTransport   │         P2PTransport                │
│   (文件传输)       │         (ZeroMQ + 文件回退)          │
└───────────────────┴─────────────────────────────────────┘
```

### 3.2 核心模块

| 模块 | 路径 | 职责 | 代码量 |
|------|------|------|--------|
| **CLI** | `clawteam/cli/commands.py` | 所有 CLI 命令入口 | 2000+ 行 |
| **团队管理** | `clawteam/team/manager.py` | 团队生命周期管理 | - |
| **任务存储** | `clawteam/team/tasks.py` | 文件任务存储，支持依赖跟踪 | - |
| **邮箱系统** | `clawteam/team/mailbox.py` | Agent 间消息传递 | - |
| **传输层** | `clawteam/transport/` | 抽象传输接口 | - |
| **工作空间** | `clawteam/workspace/` | Git Worktree 管理 | - |
| **生成后端** | `clawteam/spawn/` | tmux 和 subprocess 后端 | - |
| **看板** | `clawteam/board/` | 终端和 Web 仪表板 | - |
| **模板** | `clawteam/templates/` | TOML 团队模板 | - |

### 3.3 数据存储布局

```
~/.clawteam/
├── teams/{team}/
│   ├── config.json          # TeamConfig（名称、成员、领导者）
│   ├── inboxes/{agent}/     # msg-{timestamp}-{uuid}.json
│   └── events/              # 事件日志（只追加）
├── tasks/{team}/
│   └── task-{id}.json       # 独立任务文件
├── plans/
│   └── {agent}-{id}.md      # 计划文档
└── workspaces/{team}/       # Git Worktree
```

### 3.4 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `CLAWTEAM_AGENT_ID` | 唯一 Agent 标识符 | - |
| `CLAWTEAM_AGENT_NAME` | 人类可读的 Agent 名称 | - |
| `CLAWTEAM_AGENT_TYPE` | Agent 角色类型 | `general-purpose` |
| `CLAWTEAM_TEAM_NAME` | 所属团队名称 | - |
| `CLAWTEAM_DATA_DIR` | 数据目录 | `~/.clawteam` |
| `CLAWTEAM_TRANSPORT` | 传输后端 | `file` |

---

## 四、使用场景

### 场景 1：自主 ML 研究（8 Agent × 8 H100 GPU）

**基于：** [@karpathy 的 autoresearch](https://github.com/karpathy/autoresearch)

**人类输入：**
> "用 8 块 GPU 优化这个 LLM 训练配置。"

**Leader Agent 自主完成：**
```
├── 📖 阅读实验协议
├── 🏗️ 创建团队：clawteam team spawn-team autoresearch
├── 🚀 分配 8 个研究方向：
│   ├── GPU 0: "探索模型深度 (DEPTH 10-16)"
│   ├── GPU 1: "探索模型宽度 (ASPECT_RATIO 80-128)"
│   ├── GPU 2: "调整学习率和优化器"
│   ├── GPU 3: "探索批量大小和累积"
│   └── GPU 4-7: Codex agents 并行实验
├── 🔄 每 30 分钟检查结果：
│   ├── 读取每个 agent 的 results.tsv
│   ├── 识别最佳发现 (depth=12, batch=2^17, norm-before-RoPE)
│   └── 交叉融合：告诉新 agent 从最佳配置开始
├── 🔧 重新分配：
│   ├── 终止空闲 agent，清理 worktrees
│   ├── 从最佳 commit 创建新 worktrees
│   └── 用组合优化方向生成新 agent
└── ✅ 2430+ 实验后：val_bpb 1.044 → 0.977（6.4% 提升）
```

**成果：**
- 2430+ 实验
- ~30 GPU 小时
- 零人工干预

### 场景 2：Agent 软件工程

**人类输入：**
> "构建一个全栈 todo 应用，带认证、数据库和 React 前端。"

**Leader Agent 自主完成：**
```
├── 🏗️ 创建团队：clawteam team spawn-team webapp
├── 📋 创建带依赖链的任务：
│   ├── T1: "设计 REST API schema" → architect
│   ├── T2: "实现 JWT 认证" --blocked-by T1 → backend1
│   ├── T3: "构建数据库层" --blocked-by T1 → backend2
│   ├── T4: "构建 React 前端" → frontend
│   └── T5: "集成测试" --blocked-by T2,T3,T4 → tester
├── 🚀 生成 5 个子 Agent（每个独立 git worktree）
├── 🔗 依赖自动解除：
│   ├── architect 完成 → backend1 和 backend2 自动解锁
│   ├── 所有后端完成 → tester 自动解锁
│   └── 每个 agent 调用：clawteam task update <id> --status completed
├── 💬 子 Agent 通过 inbox 协调：
│   ├── architect → backend1: "这是 OpenAPI 规范：..."
│   ├── backend1 → tester: "认证端点就绪 /api/auth/*"
│   └── tester → leader: "全部 47 个测试通过 ✅"
└── 🌳 Leader 合并所有 worktrees 到 main 分支
```

### 场景 3：AI 对冲基金（7 Agent 团队）

**一键启动：**
```bash
clawteam launch hedge-fund \
  --team fund1 \
  --goal "分析 AAPL、MSFT、NVDA 2026 Q2"
```

**团队结构：**
```
├── 📊 投资组合经理（Leader）
├── 🤖 5 个分析师 Agent：
│   ├── 🎩 巴菲特分析师 → 价值投资（护城河、ROE、DCF）
│   ├── 🚀 成长分析师 → 颠覆性（TAM、网络效应）
│   ├── 📈 技术分析师 → 指标（EMA、RSI、布林带）
│   ├── 📋 基本面 → 财务比率（P/E、D/E、FCF）
│   └── 📰 情绪分析师 → 新闻 + 内部交易信号
└── 🛡️ 风控经理（等待所有分析师信号后收敛）
```

---

## 五、命令参考速查

### 团队生命周期
```bash
clawteam team spawn-team <team> -d "description" -n <leader>
clawteam team discover                    # 列出所有团队
clawteam team status <team>               # 显示成员
clawteam team cleanup <team> --force      # 删除团队
```

### 生成 Agent
```bash
clawteam spawn --team <team> --agent-name <name> --task "do this"
clawteam spawn tmux codex --team <team> --agent-name <name> --task "do this"
```

### 任务管理
```bash
clawteam task create <team> "subject" -o <owner> --blocked-by <id1>,<id2>
clawteam task update <team> <id> --status completed   # 自动解除依赖
clawteam task list <team> --status blocked --owner worker1
clawteam task wait <team> --timeout 300
```

### 消息传递
```bash
clawteam inbox send <team> <to> "message"
clawteam inbox broadcast <team> "message"
clawteam inbox receive <team>             # 消费消息
clawteam inbox peek <team>                # 只读不消费
```

### 监控
```bash
clawteam board show <team>                # 终端看板
clawteam board live <team> --interval 3   # 自动刷新
clawteam board attach <team>              # 平铺 tmux 视图
clawteam board serve --port 8080          # Web UI
```

### 配置
```bash
clawteam config show                      # 显示所有配置
clawteam config set <key> <value>         # 设置配置
clawteam config get <key>                 # 获取配置值
clawteam config health                    # 健康检查
```

---

## 六、技术亮点

### 6.1 任务锁机制

```python
# 当任务状态变为 in_progress 时获取锁
if status == TaskStatus.in_progress:
    self._acquire_lock(task, caller, force)

# 完成时释放锁
if status in (TaskStatus.completed, TaskStatus.pending):
    task.locked_by = ""
```

### 6.2 依赖自动解除

```python
# 完成任务时自动解除下游阻塞
if status == TaskStatus.completed:
    for other in all_tasks:
        if task.id in other.blocked_by:
            other.blocked_by.remove(task.id)
            if not other.blocked_by:
                other.status = TaskStatus.pending
```

### 6.3 P2P 离线回退

```python
# P2PTransport 在对方离线时自动回退到 FileTransport
if not peer_exists or not pid_alive:
    return self._fallback.deliver(recipient, data)
```

### 6.4 原子写入

```python
# tmp + rename 模式确保崩溃安全
tmp_path = inbox_dir / f".tmp-{uuid}-{timestamp}.json"
final_path = inbox_dir / f"msg-{timestamp}-{uuid}.json"

# 1. 写入临时文件
tmp_path.write_bytes(data)

# 2. 原子重命名
tmp_path.rename(final_path)
```

---

## 七、优缺点分析

### ✅ 优势

| 优势 | 说明 |
|-----|------|
| **极简主义** | 零服务器、零数据库、零云服务，仅文件系统和 tmux |
| **框架无关** | 支持任意 CLI Agent，无供应商锁定 |
| **Agent 驱动** | Agent 自主协调，人类只需提供目标 |
| **真实隔离** | Git Worktree 提供真实的分支隔离 |
| **原子写入** | tmp + rename 模式确保崩溃安全 |
| **JSON 输出** | 所有命令支持 `--json`，便于脚本和 Agent 解析 |
| **模板系统** | TOML 模板可复用团队原型 |
| **双传输模式** | 文件（默认）+ P2P（ZeroMQ，带离线回退） |

### ⚠️ 劣势

| 劣势 | 说明 |
|-----|------|
| **依赖 tmux** | 需要 tmux 支持（虽然大多数系统已预装） |
| **单机优先** | 跨机器需要 SSHFS 或手动配置 P2P |
| **无权限系统** | 当前版本无认证/授权（v0.6 计划中） |
| **无审计日志** | 只有事件日志，无操作审计 |
| **Python 3.10+** | 需要较新的 Python 版本 |
| **文档分散** | README 很长，但缺少分步教程 |

---

## 八、项目路线图

| 版本 | 功能 | 状态 |
|------|------|------|
| v0.2 | 单机文件系统，基础功能 | ✅ 已完成 |
| v0.3 | Config 系统、多用户协作、Web UI、团队模板 | ✅ 已完成 |
| v0.4 | Redis 传输（跨机器消息） | 🔜 计划中 |
| v0.5 | 共享状态层（跨机器配置/任务） | 🔜 计划中 |
| v0.6 | 权限模型、认证、审计日志 | 💡 探索中 |
| v0.7 | 自适应调度（动态任务重分配） | 💡 探索中 |
| v1.0 | 生产级（认证、权限、审计日志） | 💡 探索中 |

### v0.3 已完成内容

- **Config 系统：** `clawteam config show/set/get/health`
- **多用户协作：** `CLAWTEAM_USER` / `clawteam config set user`，(user, name) 复合唯一性
- **Web UI：** `clawteam board serve`，SSE 实时推送，深色主题看板
- **跨机器方案：** SSHFS/云盘 + `CLAWTEAM_DATA_DIR`，零代码改动

---

## 九、与其他框架对比

### vs AutoGen

| 维度 | ClawTeam | AutoGen |
|-----|---------|---------|
| 使用者 | AI Agent 自身 | 人类编写编排代码 |
| 基础设施 | 文件系统 + tmux | 需要 Python 运行时 |
| Agent 支持 | 任意 CLI Agent | 仅限 AutoGen Agent |
| 隔离机制 | Git Worktree | 进程隔离 |

### vs CrewAI

| 维度 | ClawTeam | CrewAI |
|-----|---------|--------|
| 使用者 | AI Agent 自身 | 人类定义角色和流程 |
| 基础设施 | 文件系统 + tmux | 需要 Python 运行时 |
| Agent 支持 | 任意 CLI Agent | 仅限 CrewAI Agent |
| 协调方式 | 群体自组织 | 硬编码流程 |

### vs LangGraph

| 维度 | ClawTeam | LangGraph |
|-----|---------|-----------|
| 使用者 | AI Agent 自身 | 人类定义图和边 |
| 基础设施 | 文件系统 + tmux | 需要 Python 运行时 |
| Agent 支持 | 任意 CLI Agent | 仅限 LangChain Agent |
| 状态管理 | 文件存储 | 需要检查点存储 |

---

## 十、总结与建议

### 核心价值

**ClawTeam** 是一个设计精巧的多 Agent 协调工具，其核心价值在于：

1. **降低门槛**：无需编写编排代码，Agent 自主协调
2. **保持灵活**：支持任意 CLI Agent，无框架锁定
3. **极简架构**：文件系统 + tmux，零运维负担
4. **生产就绪**：原子写入、文件锁、事件日志、Web UI

### 适用场景

✅ **推荐使用：**
- 需要多个 Agent 并行工作的复杂任务
- 希望 Agent 自主协调而非硬编码流程
- 追求极简部署（无数据库、无云服务）
- 快速原型验证和实验

❌ **不推荐使用：**
- 需要严格权限控制和审计日志的企业环境
- 需要跨大规模集群（100+ Agent）的场景
- 需要与特定 Agent 框架深度集成的场景

### 项目成熟度

**当前版本：** v0.3（Alpha）

- ✅ 核心功能完整
- ✅ 文档齐全（中英文韩文）
- ✅ 有实际生产案例（AutoResearch）
- ⚠️ 生产环境需谨慎评估

### 快速开始

```bash
# 1. 安装
pip install clawteam

# 2. 给 Claude Code 一句提示词
"构建一个全栈应用。使用 clawteam 将工作拆分给多个 Agent。"

# 3. 观看 Agent 自主组队、分工、协同工作
clawteam board attach my-team
```

---

**调研完成时间：** 2026-03-18  
**项目仓库：** https://github.com/HKUDS/ClawTeam  
**社区：** [飞书群](https://github.com/HKUDS/.github/blob/main/profile/README.md) | [微信群](https://github.com/HKUDS/.github/blob/main/profile/README.md)
