# 你的 Agent 会话，能不能像 Bash History 一样跟着你走？Atuin Threads 与「会话即日志」的工程真相

2026 年 11 月 11 日，Atuin 的维护者 Ellie 在官方博客发了一篇不太像发布公告的文章，开头是一句很朴素的抱怨：

> 过去一两年，我用终端的方式彻底变了。以前 shell 里跑的每条命令都是我写的；现在，我机器上跑的命令，一半以上不是我写的。
> 但 shell history 跟着我走，agent session 不跟。

同一天，Atuin Threads 在 Hacker News 首页拿到 184 分、23 条讨论。分数不算爆款——那天的头条是 591 分的 AWS 本地模拟器。但如果你每天在 Claude Code、Codex、Copilot CLI、OpenCode 之间来回横跳，并且手上不止一台机器，这条 184 分大概是本周最值得读的一条。

因为它解决的不是「模型聪不聪明」，而是一个更尴尬的问题：**过去两年我们把最值钱的工作过程，存成了八种互不兼容的临时文件，然后丢在各自的 home 目录里烂掉。**

这篇文章拆四件事：Atuin Threads 到底把「会话」建模成了什么；为什么它的核心数据结构是一棵带 head 指针的树而不是一个数组；跨 harness 恢复为什么注定是**有损编译**（以及损失清单长什么样）；最后，这套东西对「开发者工具该怎么做」意味着什么。

---

## 一、三种工作记录，只有一种没有版本控制

先把资产盘点清楚。一个工程师每天的产出，大致落在三个地方：

| 资产 | 载体 | 是否跟随你 | 是否可检索 | 是否有历史 |
|---|---|---|---|---|
| 代码 | Git | ✅（push/pull） | ✅ | ✅（commit graph） |
| 命令 | shell history | ✅（atuin 已解决） | ✅（FTS + 模糊） | ⚠️（线性，无分支） |
| **会话** | `~/.claude`、`~/.codex`、SQLite… | ❌ | ❌ | ❌ |

第三行是空白。而它恰恰是信息密度最高的一行。

一个 Git commit 记录的是「结果」：三行 diff，一条 message。而一个 agent session 记录的是「过程」——你最初的意图、模型尝试了什么、哪条路走死了、报错原文是什么、你为什么放弃方案 A 选了方案 B。Ellie 在文章里举了个特别真实的例子：他反复改了很多次 onboarding 流程，每次都不满意，那些被放弃的版本从来没进过 main。当新 agent 再来做 onboarding 时，它能把之前所有失败尝试连同「为什么放弃」一起捞出来，不需要他写一份巨大的 spec。

> These sessions contain the code that never made it into main, as well as my initial prompts and iteration. Subsequent agents can use this to figure out exactly what I want, without me having to write up a giant spec.

这句话点出了 session history 的真正价值：**它是「未提交工作」的唯一记录**。Git 只保存成功路径，session 保存搜索树。而搜索树里的死胡同，恰恰是下一次搜索最有用的先验。

问题是，这份记录现在的存在形式大概是这样的：

- Claude Code：`~/.claude/projects/<项目 slug>/<session-id>.jsonl`
- Codex：`~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-<timestamp>-<id>.jsonl`
- OpenCode：一个 SQLite 数据库
- 其他：各家自己的 JSON / JSONL / DB

八到十种格式，四种存储引擎，零个通用查询接口。你的工作记忆被按工具切成了碎片，每换一个 harness 就断一次片。

---

## 二、把会话压成一条 append-only log

Atuin Threads 的第一个决定，也是最关键的决定：**不试图统一各家的会话格式，而是先造一个足够小的中间表示，再把各家格式编译进来。**

它的存储 schema 只有两张表（`crates/atuin-ai/migrations/20260413000000_create_ai_sessions.sql`）：

```sql
CREATE TABLE sessions (
    id                TEXT PRIMARY KEY,
    head_id           TEXT,          -- 当前 HEAD，指向某个 event
    server_session_id TEXT,          -- 同步到服务端后的 id
    directory         TEXT,
    git_root          TEXT,
    created_at        INTEGER NOT NULL,
    updated_at        INTEGER NOT NULL,
    archived_at       INTEGER
);

CREATE TABLE session_events (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL,
    parent_id     TEXT,              -- 指向上一个 event → 树
    invocation_id TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    event_data    TEXT NOT NULL,     -- JSON
    created_at    INTEGER NOT NULL
);
```

注意 `parent_id` 和 `head_id` 这两列。它们让一个 session 从「消息数组」变成了「有向树 + 一个可移动的 HEAD」——这就是 Git 的形状。

事件类型只有七种，全部在 `event_serde.rs` 里手工序列化：

```
user_message | text | tool_call | tool_result
out_of_band_output | system_context | skill_invocation
```

七种。这是整个项目的品味所在：**中间表示的字段越少，能适配的 harness 越多；反过来，任何一个为了「保真」而加的字段，都会变成第八个适配器的噩梦。**

这里有个容易被忽略的工程细节：`id` 的生成方式分两类。有原生 id 的行（Claude Code 的 `uuid`、Codex 的 `call_id`）直接用原生 id 做键；没有 id 的行（标题、压缩摘要、某些 turn 上下文）用**内容哈希**生成 `syn-<hash>` 的合成 id。

这不是小聪明，而是幂等性的地基。同一个 transcript 被重复扫描两遍，哈希相同 → 主键冲突 → 不会重复插入。跨机器同步时，两台机器对同一行内容算出同一个 id → 天然去重，不需要任何协调。**内容寻址把「同步」降级成了「集合并集」。**

同步层复用的是 Atuin 原本为 shell history 写的引擎。作者说得很直接：

> We put a lot of time and effort into building a reliable, encrypted sync engine. It's generic, and can sync anything that can be modelled as an append-only log. As it turns out, most AI sessions are exactly this.

客户端加密走 PASETO v4（内部是 XChaCha20 + BLAKE2b），服务端拿到的只有密文；可以自托管，也可以完全本地。这句话在 HN 上被反复追问——有个用户直接问「把 shell history 和 agent session 全放到别人的服务器上，我是不是太偏执了」，底下三条回复都是同一句：客户端加密，或者自己跑 server。

设计上这是对的：**同步引擎应该是通用的，agent session 只是它的第二个用户。** 反过来，如果一开始就为「agent session 同步」写一套专用协议，那这套代码永远只能服务一个产品。

---

## 三、适配器的真实成本：49,805 行

中间表示很干净，但脏活全在两头。我拉下 `atuinsh/atuin` 的源码数了一下 `crates/atuin-common/src/harnesstools/` 的规模：

```
49,805 行（含 session 解析、rehydrate 回写、sync 快进、fork 逻辑）
```

按 harness 拆分，前几名是：

| Harness | 相关代码行数 | 原生存储 |
|---|---|---|
| opencode | 7,411 | SQLite |
| sync（通用层） | 5,691 | — |
| codex | 5,611 | JSONL（分页模式） |
| hermes | 3,741 | JSONL |
| claude code (`ccode`) | 3,503 | JSONL |
| grok | 3,417 | JSONL |
| kiro | 3,327 | JSONL |
| pi | 3,225 | JSONL |
| copilot | 2,331 | JSONL |

也就是说，**一个「八种 harness 都能读能写」的功能，代码量是中间表示本身的近百倍。** 这就是协议碎片化的税，而且是一次性付不完的税——每加一个 harness，就要重付一遍。

更值得注意的是捕获方式。很多人第一反应是「挂 hook」：Claude Code 有 hooks，Codex 也有。但作者在 HN 回复里明确否掉了这条路：

> We actually don't use hooks at all at the moment, and instead rely on parsing session files.

理由藏在文件格式的注释里。以 Codex 为例，`codex/session.rs` 要处理的是 `~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-<timestamp>-<id>.jsonl`，而这个格式本身在版本间演化过：0.32 之前的 rollout 行没有时间戳；0.156 之后进入 `history_mode: "paginated"`，每行带 `ordinal` 序号；0.160 起工具通过 `exec` 脚本运行，命令是否失败只记在命令自己的事件里。Claude Code 那边则是 `projects/<slug>/<id>.jsonl`，subagent 的 transcript 嵌套在父 session 下，`claude --resume <id>` 会在所有 project 目录里找同名 id，找到多个还会放弃。

这些细节说明一件事：**hook 覆盖的是「事件流」，而 transcript 文件才是「事实源」。** 一个 agent 可能被 Ctrl-C 打断、可能崩溃、可能被 IDE 插件以非交互方式调用、可能在容器里跑完就销毁——这些路径未必都会触发 hook，但都会留下（或丢掉）transcript。要保证「不漏」，只能盯文件。

代价是必须追着格式跑。Atuin 的 CHANGELOG 里，几乎每个 patch 版本都有一两条 `*(threads)*` 修复，比如「Claude Code shell 编辑的 diff 要捕获」「omp 子 transcript 被误标成 Pi」「Grok 的 tool result 应按 call 而不是按 output 建键」。这是一场没有终点的军备竞赛，而它恰恰是这类工具的真正护城河——**不是想法，是那 5 万行适配代码和背后几十个格式细节。**

---

## 四、跨 harness 恢复，是一次有损编译

这是全文我最想讲的部分，也是 Atuin 的文档写得最诚实的地方。

「在 Claude Code 里开始，在 Codex 里继续」听起来像是复制一段 messages 数组。实际上不是。Codex 的 `rehydrate.rs` 开头就列了一张「什么活下来、什么被丢掉」的清单。我把关键几项整理成表：

| 信息 | 跨 harness 后 | 原因 |
|---|---|---|
| 用户 prompt | ✅ 原样 | — |
| 助手文本回复 | ✅ 原样 | — |
| tool call + 输入 | ✅（尽量映射成目标 harness 的同名工具） | shell / read / write / edit / search 有对应物 |
| tool call 的**输出** | ⚠️ 按原样写回；被策略隐去或超限时写成 `UNCAPTURED_OUTPUT` | 目标 harness 无法重放 |
| 文件 patch | ⚠️ 转成目标格式的「文件变更」事件 | Codex 靠它显示 diff |
| **推理（reasoning）** | ❌ **全部丢弃** | `encrypted_content` 只有原模型能读 |
| 目标 harness 自己注入的 system context | ❌ 丢弃 | 属于原环境 |
| usage / token 计数 | ❌ 丢弃 | 属于原模型调用 |
| 模型选择 | ❌ 丢弃 | 目标用自己的默认模型 |

推理被丢掉这一条，注释写得很干脆：

> A `reasoning` item without that ciphertext is worse than none: resuming sends it back to the Responses API by `id`, which a store-less request cannot resolve. The model's earlier reasoning is not something it needs to continue.

翻成工程语言：**reasoning token 是加密的、绑定供应商的、不可移植的。** 它不是「模型的思考记录」，它是「供应商的私有状态」。所以任何声称能「完整迁移会话」的工具，只要没提 reasoning，就是在撒谎——不是不想带，是带不了。

第二类损失更有意思：**工具语义的坍塌**。

`harnesstools/continuation.rs` 里规定，跨 harness 继续时，被捕获的 tool call 会尽量映射成目标 harness 的同名工具；映射不了的、没有输入的、或者**由模型供应商自己执行的**（比如 Claude Code 的 web search——结果只有那个供应商能读），统一降级成一句文本注记：

```
[ran a shell command]
[edited `src/store.rs`]
```

这是一个非常务实的设计：**降级成「自然语言事实」，而不是降级成「错误的结构」。** 模型读一句「这里跑过一个 shell 命令」完全能理解上下文；但如果给它一个 schema 不合法的 `function_call`，很多 harness 会直接解析失败。宁可损失结构，也不能产出非法行。

还有一条容易被忽略的约束：写回的行必须让目标 harness 的 API 接受。Codex 侧要求「after the marker, user 和 assistant 交替，以 user 开头、以 assistant 结尾」，所以连续同角色的行会被合并；opencode 按 id 里的时间戳排序，所以原始时间戳要「向前微调」以保证单调递增。

看明白这层，你会发现所谓「会话可移植」根本不是数据搬运问题，而是**在两种互不兼容的协议之间做一次保真度受限的编译**。编译器要保证输出是合法的，而不是保证输入被完整表达。

顺带说一个反直觉的结论：**新会话不是原会话的副本。** `continuation.rs` 明确写着，跨 harness 继续会在目标端创建一个**全新的 session**，用自己的新 id，只在第一行写一个 marker 指回原会话。这既是为了让目标 harness 能正常 `--resume`，也顺手保住了血缘关系——像 Git 的 `cherry-pick`：新 commit，但记着来源。

---

## 五、为什么是树，而不是数组

如果把 session 当成聊天记录，一个数组就够了。Atuin 偏偏用了 `parent_id`。

原因在 `atuin-client/src/ai_session/database/heads.rs` 的模块注释里，写得像一份分布式系统的设计文档：

> A session keeps one id across machines. Each machine's transcript is a line of it, and the synced rows hold every line at once.

翻译一下：一个 session 的 id 在所有机器上相同，**每台机器的原生 transcript 只是这个 session 的一条「线」**。同步存储里同时躺着所有线。于是会出现三种状态：

1. **本机副本落后**（别处从相同的尾巴继续了）→ 快进，把缺的行原地 append 到本机 transcript 末尾，id 不变；
2. **本机副本自己往前走了**（分叉）→ 绝不改写，提示用户 fork；
3. **本机在另一条线上** → 同理，只 fork。

规则里最硬的一条是：**只允许 clean fast-forward，任何需要改写已有行的操作都拒绝，除非用户显式选了一个 head。**

这和 Git 是一个哲学：不改写历史，分叉就分叉，让用户决定 merge 还是 rebase。

但 session 比 Git 多了一个麻烦：**并行工具调用会产生假分叉。** 模型同时发三个 tool call，树立刻变成三叉；一次 compaction 也会分叉。如果按「节点数 > 1 就算分叉」判定，几乎每个会话都是分叉的，fork 提示会把用户逼疯。

Atuin 的解法是引入 **substantive row** 的概念：只有「用户 prompt」和「助手文本」算实质行；工具行不算。一个分叉只有在其下**至少两个子树各自包含实质行**时才算数；每条最终到达不了「有效分叉」的路径就是一个 head，head 的 tip 取该路径上最后一个实质行之后最新的叶子。

> Nothing here is stored: `AiSessionDatabase::analyse` reads the session's rows each time.

这句话也值得单独说：**head 和 diverged 状态全部是按需从行里算出来的，不落库。** 因为这些状态依赖于「哪些行已经同步过来了」，而同步是异步的、可能乱序到达的；一旦缓存，就要处理缓存失效。重算一遍的成本，远低于维护一致性的成本。在数据量只有几万行的场景里，这是绝对正确的取舍。

---

## 六、安全：你把 `.claude` 目录当什么？

HN 讨论里有一整条支线，比文章本身更值得警惕。

一个用户说自己花了两个月把各个 agent 相互隔离：激进沙箱、定期扫描 transcript 里的泄漏凭据、每个 agent 独立加密的凭据库、甚至按工作领域做物理和网络隔离。另一个人接上：

> yes agent leak secrets. "Yes, and don't ask again" in Claude Code would also save secrets in `.claude/settings.local.json`.

第三条最扎心：

> the agent can write to that file too. The file that decides what it is allowed to do is just another file in the repo for it. I now treat the agent config files as something to protect from the agent itself.

这已经超出本文范围了，但它和 Threads 直接相关：**agent transcript 里天然含密钥。** 你让 agent 读 `.env`、跑 `export TOKEN=...`、curl 一个带签名的 URL，这些都会明文进 JSONL。所以 Threads 把「捕获 session」做成 opt-in、把同步做成端到端加密、把服务端做成可自托管，不是营销话术，是这类工具能不能被企业接受的前提。

反过来说，作为使用者，你应该问三个问题：

1. 捕获是默认开还是默认关？（Atuin：opt-in）
2. 加密在客户端还是服务端？（客户端，PASETO v4，服务端只见密文）
3. 能不能只同步某个目录 / 某个仓库？（`[threads]` 里支持 global / host / workspace / branch / directory 五档过滤，`ctrl-r` 循环切换）

第三点很实用：`workspace` 和 `branch` 这两档意味着**会话可以按 git 仓库和分支聚合**。这意味着你在 `feature/auth` 分支上做的所有探索，天然和这个分支绑定；切分支时，看到的就是这个分支的历史。这是把 session 挂到代码坐标系上，而不是挂在时间轴上。

---

## 七、MCP：让 agent 自己查历史

Threads 另一个值得单独说的设计是 `atuin mcp`：把会话检索做成 MCP 工具，agent 可以自己搜。

安装就一行：

```bash
atuin mcp install claude   # 或 codex / pi / opencode
```

这个设计的意义在于，它绕过了「上下文窗口」这个硬约束。你不需要把历史塞进 prompt，agent 在需要的时候自己去查。作者举的例子很典型：Sentry 日常 triage agent 发现头像上传 403，用一句 `seeing some tigris avatar issues?` 就让另一个 agent 找到了当天早些时候那次调查，直接拿到根因。

这里其实藏着一个产品判断：**记忆不该是「注入」，而该是「检索」。** 注入是 O(上下文)，检索是 O(需要)。前者随历史线性膨胀，后者不随历史增长。Atuin 选后者，是因为它本来就是个搜索工具——FTS5 contentless 索引，`messages_fts` 虚拟表，按 session / 目录 / 仓库 / 分支过滤。检索是它的母语。

HN 上有人问这是不是会很耗 token（读历史当上下文）。回答是：默认不影响，因为你只在显式引用时才付这个成本。这也是「检索优先」的另一个好处——**成本可控，且可归因。**

---

## 八、这对开发者工具意味着什么

跳出 Atuin 本身，这件事有几个可迁移的判断。

**第一，session 正在变成一等公民。** 过去我们把「工作记录」等同于 commit；现在一半的工作发生在 commit 之前，而且形态是对话 + 工具调用。谁先把这份记录变成可查询、可迁移、可协作的资产，谁就拿到了下一个「Git」的位置。HN 上有人吐槽「现在人人都出一个 session manager，AI 的浏览器标签页」，但下面一条回复更准：你可以几小时 vibe 出一个壳，但适配八个 harness 的五万行代码抄不走。

**第二，跨工具的可移植性，只能靠「有损编译 + 显式血缘」实现。** 指望所有 harness 统一格式是不现实的——它们的会话结构服务于各自的 API（Anthropic 的 tool_use 块、OpenAI 的 Responses item、Codex 的 paginated rollout）。现实路径是：定一个极小的中间表示，把差异关在适配器里，跨端继续时诚实降级，并用 marker 保留血缘。任何承诺「100% 无损迁移」的方案，都要追问一句 reasoning 怎么办。

**第三，同步引擎要通用，agent 只是第二个用户。** Atuin 省下的一半工作量来自「shell history 已经把 append-only log 的同步、加密、冲突处理做完了」。这是个很值得抄的架构直觉：先找同构的老问题，复用它的基础设施。

**第四，安全边界要画在数据产生的地方。** transcript 里有密钥，所以加密必须在客户端，捕获必须 opt-in，服务端必须可自托管。这三条不是可选项，是准入条件。

**落地建议**（如果你打算在团队里用）：

- 先在单机跑 `atuin resume` 感受一下，确认它能不能认出你常用的 harness（当前支持 Claude Code、Codex、Copilot、OpenCode、Pi、Omp，加上 grok / kiro / hermes / amp 的适配）；
- `threads.capture_tools` 想清楚：开了才有 tool call 的输入输出，跨 harness 继续才有意义；不开就只剩对话文本；
- 团队共享还在做（opt-in 的 session sharing），现阶段别指望「把 thread 当 Git branch 交接」，但可以先用自托管 server 做个人跨机同步；
- 把 `workspace` / `branch` 过滤用起来，否则全局历史会迅速变成噪声——HN 上那句「一半 session 是扔掉的实验」是真的。

---

## 结语：给「过程」建一个版本库

Atuin 这个项目有意思的地方，是它两次都在解决同一个问题：**让易失的工作痕迹变成可检索的资产。** 第一次是 `.bash_history` 的第 501 行，第二次是散落在八种格式里的 agent transcript。

而它两次用的方法也一样：找一个足够小的、append-only 的、内容寻址的表示，把复杂世界编译进来，然后让检索去做剩下的活。

至于「会话能不能像 Git 一样 branch / merge / PR」，目前答案是不能——因为会话的 diff 没有稳定语义，两个分支的「同一处修改」根本无从对齐。所以 Atuin 只做到 head 指针 + 显式 fork，把合并留给人类。这看起来是退让，其实是准确：**在没有语义的地方强行自动合并，比不合并危险得多。**

真正值得记住的一句话，是作者那句抱怨背后的洞察：

> Agent sessions store the lot of it. Every command, its output, my intent, and everything I tried along the way. It's all there, in plain English, in my home directory! But just as with shell history all those years ago, we don't put it to work.

数据一直在那儿。缺的从来不是数据，是把它变成资产的那一层。

---

**参考**

- Atuin Blog, *Atuin Threads: All your agent sessions on every machine*, 2026-11-11 — https://blog.atuin.sh/threads-agent-sessions/
- `atuinsh/atuin` v18.24.x 源码：`crates/atuin-ai/`（schema、event_serde、store）、`crates/atuin-common/src/harnesstools/`（各 harness 的 session / rehydrate / sync / continuation）、`crates/atuin-client/src/ai_session/`（FTS5 索引、heads 分析）
- Hacker News 讨论（184 points, 23 comments），2026-11-11 — https://news.ycombinator.com/item?id=50453637
- Atuin 文档：自托管 server、`atuin mcp`、`[threads]` 配置
