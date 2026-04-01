# 我阅读了 Claude Code 的记忆源代码。这个限制会静默删除你代理的记忆

**作者：** mem0  
**原文：** https://x.com/mem0ai/status/2039041449854124229  
**翻译时间：** 2026-04-01

---

![封面图片](./article_cover.jpg)

我阅读了 Claude Code 的记忆源代码。

200 行索引上限。每轮 5 个文件。没有嵌入向量。

以下是当 Claude 说它记得你时实际发生的情况，以及如何修复它。

## 记忆泄漏

有人将完整的 Claude Code 源代码发布到了互联网上。

工程师们立即开始研究有趣的部分：提示词、工具定义、计费逻辑。

![Claude Code 记忆目录](./article_img4.jpg)
*Claude Code 记忆目录*

我直接查看了 `src/memdir/`。

七个文件。整个记忆架构。其中隐藏着一个 Anthropic 从未公开记录的硬性限制。

![Claude Code Memory Architecture](./article_img5.jpg)
*Claude Code Memory Architecture（原文拼写为 Architetcure）*

![My personal memory in Claude](./article_img3.jpg)
*My personal memory in Claude*


## 记忆系统实际工作原理

![Claude Code memory](./article_img2.png)
*Claude Code memory*

Claude Code 将记忆存储为磁盘上的纯 Markdown 文件。

**路径：** `~/.claude/projects/<你的仓库名称>/memory/`

每个项目都有自己的文件夹。每次对话都可以写入其中。文件在会话之间持久化。这就是整个持久化模型。

还有一个名为 `MEMORY.md` 的索引文件。它位于该文件夹的根目录。Claude 在每次会话开始时读取此索引以了解存在哪些记忆。

这就是有趣的地方。

## 200 行上限

MEMORY.md 在源代码中有两个硬性限制。

**200 行最大值。** 如果你的索引超过这个限制，系统会静默截断它。它会在截断的内容后附加一个警告，但只有你去文件中查找时才能看到这个警告。Claude 看到的是干净的系统提示，完全不知道索引被截断了。

**25KB 最大值。** 针对每行异常长的边缘情况的单独字节上限。

失败模式是静默的。你达到 201 行。记忆从底部消失。Claude 停止知道它们的存在。它不会告诉你。不会报错。只是忘记。

## 四种记忆类型

源代码将记忆限制为 exactly 四种类型：

- **用户记忆** 跟踪你是谁。你的角色、专业知识、偏好、你喜欢如何沟通。仅私密。
- **反馈记忆** 跟踪你给出的指导。纠正、验证过的方法、需要停止的事情。
- **项目记忆** 跟踪代码库中发生的事情。截止日期、决策、代码本身无法推导出的架构上下文。
- **参考记忆** 存储指向外部系统的指针。在哪里跟踪 bug。要关注哪个 Slack 频道。

代码明确指出：如果信息可以通过 grep 或 git 从当前代码库中推导出来，则**不应**将其保存为记忆。

## Sonnet 侧边调用

每轮，Claude Code 都会向 Claude Sonnet 发起单独的 API 调用。只是为了找出哪些记忆文件与你的当前查询相关。

过程：扫描所有记忆文件，提取它们的文件名和描述，将该清单发送给 Sonnet，要求它选择最相关的文件。最多返回 5 个文件。

这是一个语义相关性步骤，但它仅基于文件名和一行描述。不是嵌入向量。不是向量搜索。只是语言模型读取列表并做出判断。

## 记忆新鲜度

源代码有一个 `memoryFreshnessText()` 函数，为超过一天的记忆生成陈旧警告。

警告内容："此记忆已有 X 天历史。记忆是时间点观察，而非实时状态。关于代码行为的声明或 [file:line](file:line) 引用可能已过时。"

这会在 Claude 看到之前直接添加到记忆内容中。Claude 知道旧记忆可能是错误的。但无法从外部知道哪些记忆触发了这个警告。

## 后台代理

有一个 `extract-memories` 代理在对话结束后运行。后台进程会审查发生的事情并自动提取记忆。

这意味着两种不同的东西在写入你的记忆目录。会话期间的主代理。之后的后台提取器。

代码包含此功能的特性标志（EXTRACT_MEMORIES、tengu_passport_quail）。并非对所有人都开启。但架构已经存在。

## 团队记忆

有一个用于团队范围记忆的 TEAMMEM 特性标志。

启用时，某些记忆是私密的（只有你能看到），其他是团队范围的（所有贡献者共享）。项目约定进入团队记忆，个人偏好保持私密。

## Claude Code 实际如何忘记

以下是破坏性的场景。

你已经在一个实际项目上使用 Claude Code 三个月了。它已经学会了：

- 你的偏好和工作方式
- 一月份做出的架构决策
- 某个端点不稳定，测试中不应信任
- 你的团队对热修复跳过 PR 审查

然后你达到了第 201 条。

索引静默截断。最旧的记忆从底部消失。Claude 在下次会话加载一个全新的上下文，完全不知道这些记忆曾经存在。

接下来发生的事情：

- Claude 编写了一个命中不稳定端点的测试
- Claude 再次询问你的 PR 审查策略
- Claude 与你几个月前同意的架构相矛盾
- **它不是在幻觉。它没有坏掉。它只是忘记了。而且它无法告诉你。**

新鲜度警告让情况更糟——它们只针对已加载的记忆触发。如果记忆被截断出索引，它永远不会被加载。没有警告。没有信号。Claude 不知道它不知道什么。

## 限制 + 修复

默认系统设计良好的 v1 版本：扁平的 Markdown 文件、清晰的四类型分类、周到的新鲜度警告。对大多数项目来说是正确的起点。

但它有一个上限。200 行索引。每轮 5 个文件。没有嵌入向量。

mem0 完全替换了这一层。使用向量存储代替 Markdown 文件。使用嵌入相似性代替读取文件名的 Sonnet 侧边调用。没有索引上限，没有记忆悬崖，没有静默截断。

mem0 插件在 Claude Code 和 Cowork 中都有效。两条命令安装：

```
/plugin marketplace add mem0ai/mem0
/plugin install mem0@mem0-plugins
```

从那时起，你将获得语义搜索、跨会话召回和完整的记忆管理：add_memory、search_memories、update_memory、delete_memory。

当你达到上限时，这正是你替换它的方式。

![Full Memory Architecture](./article_img1.jpg)
*Full Memory Architecture*

---

图片内容：

以下是图片内容的中文翻译与结构化整理，完整呈现“Claude Code Memory Architecture — 完整第一性原理生命周期”的八个阶段及底层机制：

---

# Claude 代码记忆架构 —— 完整第一性原理生命周期

> 从进程启动 → 会话 → 查询 → 响应 → 后台代理 → 关闭 → 下一会话的每个触点


## 阶段 1：进程启动与会话初始化（setup.ts + main.tsx）

1. **入口点**：`cli.tsx → main.tsx → setup.ts`  
   - 进程启动，设置工作目录 (CWD)，设定会话 ID。

2. **清除内存文件缓存**（在工作区切换时）  
   - 确保新 CWD 中的内存文件被重新发现。

3. **initSessionMemory() – 同步操作**  
   - 注册 `postSamplingHook` 用于会话内存提取。  
   - 门控检查（GrowthBook）延迟至钩子运行时执行。  
   - 需要 `isAutoCompactEnabled()` 才能继续。

4. **startTeamMemoryWatcher()**（若启用 TEAMMEM 功能）  
   - 后台监听器，用于组织同步的团队内存变更。

5. **initExtractMemories()**（来自 backgroundHousekeeping）  
   - 创建闭包作用域状态：游标、重叠防护、待处理上下文。

6. **initAutoDream()**  
   - 创建闭包：上次扫描时间、整合运行器。

7. **预取**：在 REPL.tsx 中调用 `getMemoryFiles()`  
   - 触发异步目录遍历，填充首个渲染器。  
   - 填充 memoized 缓存供 `getUserContext()` 使用。

8. **captureHooksConfigSnapshot()**  
   - 快照 `InstructionsLoaded` 钩子，记录 session_start 原因。

🔹 **关键文件**：`setup.ts:294`, `main.tsx`, `screens/REPL.tsx`  
🔹 **结束状态**：会话 ID 已设置，钩子已注册，缓存已预热


## 阶段 2：内存发现（utils/claudemd.ts）

`getMemoryFiles()` – 记忆化、异步、每会话单目录遍历

### 发现顺序（后续更高优先级影响模型注意力）：

1. **MANAGED**: `/etc/claude-code/CLAUDE.md + rules/*.md`  
   - 企业/MDM 策略。始终加载。不可排除。

2. **USER**: `~/.claude/CLAUDE.md + ~/.claude/rules/*.md`  
   - 个人全局指令。可包含外部内容。  
   - 受 `isSettingSourceEnabled('userSettings')` 控制。

3. **PROJECT**: 遍历 CWD + 文件系统根目录，每个目录检查：
   - `.claude/`（根级）
     - `.claude/CLAUDE.md`
     - `.claude/rules/*.md`（无条件 + 条件）
   - 更接近 CWD = 更高优先级（稍后加载）
   - 受 `isSettingSourceEnabled('projectSettings')` 控制
   - 通过 worktree 检测去重（规范 git 根）

4. **LOCAL**: `CLAUDE.local.md` 在每个目录中  
   - 私有，不进入 VCS。最高指令优先级。  
   - 受 `isSettingSourceEnabled('localSettings')` 控制。

5. **AUTOMEM**: `MEMORY.md` 入口点来自自动内存目录  
   - `~/.claude/projects/<git-root>/memory/MEMORY.md`  
   - 截断为 200 行 / 25KB。始终在上下文中。

6. **TEAMMEM**: 团队内存入口点（功能标志）  
   - 组织共享内存。XML 包装在上下文中。

✅ 每个文件：解析 frontmatter，剥离 HTML 注释，解析 @includes  
✅ 条件规则：路径 glob 匹配目标文件路径  
✅ 返回：`MemoryFileInfo[]` 含 path, type, content, globs, parent


## 阶段 3：API 调用的上下文组装

三个并行管道合并到 API 请求：

### ── SYSTEM PROMPT（constants/prompts.ts → getSystemPrompt()）──
- 静态部分（全局可缓存）：
  - intro → system rules → doing tasks → actions → tools → tone → output
- DYNAMIC_BOUNDARY 标记
- 动态部分（每会话，注册表管理）：
  - session_guidance → MEMORY SECTION → env_info → language → mcp

### ── THE MEMORY SECTION（systemPromptSection('memory', loadMemoryPrompt())）──
- 行为指令：4 类分类法（何时保存、什么不保存）
- MEMORY.md 索引内容（截断 200 行 / 25KB）
- 如何保存：两步写入（更新文件 + 更新索引）
- 如何访问：如何验证、信任回忆
- 搜索过去上下文（grep memory dir + transcripts）

### ── USER CONTEXT（context.ts → getUserContext()）──
- ClaudeMd: `getClaudeMds(filterInjectedMemoryFiles(getMemoryFiles()))`
  - 渲染所有 CLAUDE.md 文件为带标签文本块
  - 前缀：“Instructions OVERRIDE default behavior”
  - AutoMem/TeamMem 过滤掉当 tengu_moth_copse 在当前日期 “Today’s date is YYYY-MM-DD”

### ── SYSTEM CONTEXT（context.ts → getSystemContext()）──
- gitstatus: branch, main branch, user, status, recent commits
- cacheBreaker: optional debug injection

### ── RELEVANCE PREFETCH（memdir/findRelevantMemories.ts）──
- Sonnet 侧边调用选择最多 5 个内存文件 → 附加到消息

▶️ query.ts: systemPrompt + prependUserContext + appendSystemContext  
▶️ services/api/claude.ts: buildSystemPromptBlocks() + API params


## 阶段 4：模型响应与直接内存操作

模型可通过标准工具 DIRECTLY 读/写内存文件：

- **FileReadTool** – 读取任意内存文件  
  - 模型读取 topic files, MEMORY.md, CLAUDE.md  
  - readFileState 缓存追踪哪些已被读取

- **FileWriteTool** – 创建新内存文件  
  - Auto-memory 目录有写入 carve-out 权限  
  - isAutoMemPath() 绕过 DANGEROUS_DIRECTORIES 检查  
  - Team memory: teamMemSecretGuard 扫描后再写入

- **FileEditTool** – 更新现有内存文件  
  - 需要先读取同一文件（dedup guard）  
  - 同权限 carve-outs 如 Write

- **BashTool** + grep 内存目录，搜索转录  
  - 模型遵循 “Searching past context” instructions  
  - `grep -rn "<term>" ~/.claude/projects/.../memory/ --include="*.md"`

 模型的系统提示包含全文指令：

- WHEN to save (user corrections, confirmations, context)
- WHAT types (user/feedback/project/reference)
- WHAT NOT (code patterns, git history, architecture)
- HOW (frontmatter format, MEMORY.md index update)
- HOW TO VERIFY recalled facts (check files exist, grep)

⚠️ 当模型写入内存时：extractMemories 跳过该轮次范围  
(hasMemoryWritesSince • 互斥于后台代理)

🔹 **关键洞察**：主代理与后台提取器是 MUTUALLY EXCLUSIVE


## 阶段 5：响应后后台代理（stopHooks.ts）

每次模型响应后，handleStopHooks() 触发 THREE 代理：

### A. extractMemories（fire-and-forget）
- Gate: EXTRACT_MEMORIES feature + isExtractModeActive() + !agentId
- Pattern: runForkedAgent – 预 fork 共享 prompt 缓存
- 计数自 lastMemoryMessageGuid 以来的新消息
- 跳过如果主代理刚写入内存（mutual exclusion）
- Throttle: turnsSinceLastExtraction vs tengu_bramble_Lintel
- Pre-injects existing memory manifest (avoids ls turn)
- Constrained tools: Read/Grep/Glob + Write ONLY in memdir
- Max 5 turns. Strategy: parallel reads + parallel writes
- Coalesces concurrent calls (stash + trailing run)
- Advances cursor on success; retries same range on failure
- Appends “Saved N memories” system message to main transcript

### B. sessionMemory（postSamplingHook）
- Gate: tengu_session_memory + autoCompact + thresholds met
- Thresholds: 18K tokens init, 5K growth between, 3 tool calls
- Trigger: (tokens AND tools) OR (tokens AND no tools in last turn)
- Writes to sessions/<id>/session_memory.md
- Template: Title, Current State, Task Spec, Files, WorkFlow, Errors, Codebase Docs, Learnings, Key Results, Worklog
- Only allowed to Edit the single session_memory.md file
- Used by compact system for pre-built conversation summary

### C. autoDream（fire-and-forget, rare）
- Gate: ≥24h + ≥5 sessions + no lock + not NAIR0S/remote
- 4 phases: Orient → Gather Signal → Consolidate → Prune


## 阶段 6：压缩与会话内存整合

当上下文窗口填满时，compression summarizes old messages:

### Session Memory Compact (sessionMemoryCompact.ts)
1. waitForSessionMemoryExtraction() – up to 15s
2. Read session_memory.md content
3. If not empty: use as pre-built summary (skip forked summarizer)
4. truncateSessionMemoryForCompact() – per-section 2000 token cap
5. Find boundary: preserve min 10K tokens / 5 text-block messages
6. Create compact boundary message with session memory content
7. Preserved segments: plan, todo list, file reads → post-compact

### Legacy Compact (compact.ts, without session memory)
1. Forked summarizer agent reads old messages
2. Produces summary text → compact boundary message
3. Post-compact messages: CLAUDE.md re-injected, plan re-attached

### Post-compact:
- resetGetMemoryFilesCache('compact') – re-discovers memory files
- InstructionsLoaded hooks fire with reason='compact'
- processSessionStartHooks() – re-runs session start hooks
- reAppendSessionMetadata() – update transcript
- markPostCompaction() in bootstrap state

### Session Memory Template (prompts.ts)
- Customizable: ~/.claude/session-memory/config/template.md
- Default sections: Session Title, Current State, Task Spec, Files & Functions, WorkFlow, Errors, Codebase Docs, Learnings, Key Results, Worklog
- Max: 12,000 total tokens, 2,000 per section


## 阶段 7：持久层 — 磁盘上存放什么？

```
~/.claude/
├── CLAUDE.md                 ← User instructions
├── rules/*.md                ← User rules
├── projects/
│   └── <sanitized-git-root>/
│       ├── memory/
│       │   ├── MEMORY.md     ← AUTO MEMORY (index, 200 lines max)
│       │   ├── user_role.md  ← Topic file
│       │   ├── feedback_*.md ← Topic files
│       │   ├── project_*.md  ← Topic files
│       │   ├── reference_*.md← Topic files
│       │   └── team/
│       │       └── MEMORY.md ← TEAM MEMORY (team index)
│       ├── logs/
│       │   ── YYYY/MM/YYYY-MM-ID.md ← NAIR0S daily logs
│       └── sessions/
│           └── <session-id>/
│               ├── transcript.jsonl    ← full conversation log
│               ── session_memory.md   ← SESSION MEMORY (per-session notes)
├── agent-memory/
│   └── <agent-type>/MEMORY.md ← USER-SCOPE AGENT MEMORY
├── session-memory/config/
│   ├── template.md           ← CUSTOMIZATION (custom session memory template)
│   └── prompt.md             ← (custom extraction prompt)
── /etc/claude-code/CLAUDE.md ← MANAGED (enterprise MDM policy)

<project-root>/
├── .CLAUDE.md                ← Project instructions, VCS
├── CLAUDE.local.md           ← Private local instructions
└── .claude/
    ├── CLAUDE.md             ← Project instructions, VCS
    ├── rules/*.md            ← Project rules, VCS
    ├── settings.json         ← Project settings
    ├── agent-memory/
    │   └── <type>/MEMORY.md  ← Agent memory, VCS
    └── agent-memory-local/
        └── <type>/MEMORY.md  ← Agent memory, private
```


## 阶段 8：跨会话反馈循环 — 记忆如何随时间改进

记忆系统形成 SELF-IMPROVING LOOP 跨越多个会话：

```
Session N          Session N+1          Session N+k
User converses     User converses       User converses
with AI            with AI              with AI
   ↓                   ↓                    ↓
-extractMemories→ disk  -extractMemories→ disk  -extractMemories→ disk
-sessionMemory→ disk    -sessionMemory→ disk    -sessionMemory→ disk
-directWrites→ disk     -directWrites→ disk     -directWrites→ disk
   ↑                   ↑                    ↑
loadMemoryPrompt() ← disk  loadMemoryPrompt() ← disk  loadMemoryPrompt() ← disk
findRelevantMemories() ← disk  findRelevantMemories() ← disk  findRelevantMemories() ← disk
getMemoryFiles() ← disk    getMemoryFiles() ← disk    getMemoryFiles() ← disk

autoDream
≥24h + ≥5 sess
Merge, prune,
resolve conflicts
      ↓
consolidate → disk
```

### 时间尺度：
- Within-turn (direct writes)
- End-of-turn (extract)
- Within-session (session memory)
- Cross-session (auto-memory persists)
- Multi-session (auto-dream consolidates)

### 4 种记忆类型：
- user (who they are)
- feedback (how to work)
- project (ongoing context)
- reference (external links)

### 显式排除项：
code patterns, git history, architecture, debugging solutions, ephemeral task details

---

## 🔐 安全与范围界定 — 信任边界

- Managed (enterprise) < User (personal) < Project (VCS) < Local (private)
- projectSettings CANNOT set autoMemoryDirectory (防止恶意 repo → ~/.ssh)
- Path normalization prevents traversal attacks (normalize + isAbsolute + length)
- Agent memory scopes: user (global), project (VCS), local (private)
- Team memory: secret scanner + guard prevents leaking credentials
- Background agents: constrained tool permissions (read-only bash, write only memdir)


## ⚙️ 配置旋钮

- autoMemoryEnabled (settings.json, env var, --bare)
- claudeMdExcludes (picomatch patterns to skip files)
- CLAUDE_CODE_DISABLE_AUTO_MEMORY, CLAUDE_CODE_DISABLE_CLAUDE_MDS
- CLAUDE_COWORK_MEMORY_PATH_OVERRIDE, CLAUDE_CODE_REMOTE_MEMORY_DIR
- Session memory: ~/.claude/session-memory/config/template_prompt.md
- Feature flags: tengu_passport_quail, tengu_session_memory, tengu_onyx_plover


---


## mem0 的不同之处

mem0 是专门为生产 AI 代理构建的记忆层。

mem0 使用向量存储代替扁平的 Markdown 文件。记忆被嵌入。检索是语义的。没有要截断的索引文件。

**Claude Code 的 mem0 插件用这个语义层替换了默认的基于文件的记忆。** 它们不再只是进入 `~/.claude/projects/...`，而是进入 mem0 的存储。检索使用嵌入相似性，而不是语言模型读取文件名。

没有 200 行上限。没有 5 文件检索限制。没有静默截断。六个月前的记忆如果与你现在的工作相关，就会出现。

Anthropic 提供的默认系统设计良好的 v1 版本。它对大多数开发者来说是正确的起点。

但当你达到上限时，插件系统正是你修复这个限制的方式。

你可以：

- *在此获取免费 API Key：* app.mem0.ai
- *或从我们的开源 GitHub 仓库自托管 mem0*

---

## In Context #4

*这篇博客是 **In Context** 的一部分，这是一个 mem0 博客系列，涵盖 AI 代理记忆和上下文工程。*

*mem0 是一个智能的开源记忆层，旨在为 LLM 和 AI 代理提供长期、个性化和上下文感知的跨会话交互。*

---

**原文链接：** https://x.com/mem0ai/status/2039041449854124229  
**翻译：** 由 Andy 翻译
