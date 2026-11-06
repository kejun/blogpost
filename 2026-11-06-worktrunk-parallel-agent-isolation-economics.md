# 十个 Agent 同时改一个仓库：Worktrunk 与「并行开发的隔离经济学」

> 2026 年 11 月，GitHub Trending 上出现了一个很不"AI"的项目：一个用 Rust 写的 git worktree 命令行工具，11,500 颗星，README 里没有模型、没有 token、没有 benchmark，只有一句话——**"A CLI for git worktree management, designed for running AI agents in parallel."**
>
> 这可能是今年最被低估的一类基础设施。当所有人都在讨论 Agent 能写多少代码时，真正的瓶颈已经悄悄转移到了另一个地方：**十个 Agent 同时改同一个仓库，文件系统怎么办？**
>
> 这篇文章拆四件事：并行 Agent 的冲突到底发生在哪一层；git worktree 为什么是"最小可行隔离"；Worktrunk 用 copy-on-write 缓存把冷启动成本压到接近零的工程细节；以及这套方案真实的能力边界——它隔离了什么，又没隔离什么。

---

## 一、并行的瓶颈不在模型，在 `index.lock`

先看一个几乎所有团队都遇到过的场景。

你让 Claude Code 修一个鉴权 bug，同时让 Codex 补三个单元测试，再让另一个 Agent 去升级依赖。三个任务互不相干，理论上应该并行。但十分钟后你回到终端，看到的是：

```
fatal: Unable to create '.git/index.lock': File exists.
```

或者更隐蔽的版本：任务看起来都成功了，但 `git status` 里混着三个任务的改动，你分不清哪一行是谁写的；一个 Agent 跑了 `git stash`，另一个 Agent 的未提交工作瞬间消失；某个 Agent 执行 `git checkout -b` 切走了分支，剩下两个 Agent 还在往错误的分支上提交。

这些不是"模型不够聪明"的问题，而是**仓库是一个单例资源**。一个普通的 git 工作目录里，`.git/HEAD`、`.git/index`、工作区文件树，全都是全局唯一的状态。多个进程并发写，本质上是没有事务的多线程写同一块内存。

行业最初的反应是"给每个 Agent 一个容器"。这当然有效，但成本结构很难看：一个装满依赖的 Node 仓库镜像动辄 2–5 GB，冷启动 30 秒到几分钟；十个并行任务就是十份完整副本，磁盘和内存都要乘十。更麻烦的是，容器里的代码和宿主机上的编辑器、调试器、dev server 是割裂的——Agent 改完，人还得想办法把结果搬回来。

第二条路是 `git clone`。隔离性最好（独立对象库），但也最贵：每个 clone 都要重新下载/复制整个 `.git`，Linux 内核这种仓库单份就是几个 GB；而且 clone 出来的仓库之间无法直接 fetch 本地分支，协作要靠 remote。

第三条路，也是 Worktrunk 选的这条路，是 `git worktree`。

它的定位极其克制：**不隔离进程、不隔离网络、不隔离内核，只隔离「工作区」这一层**。共享同一个对象库和 refs，但每个 worktree 有独立的 HEAD、独立的 index、独立的文件树。用一句话概括：

> 容器隔离的是机器，worktree 隔离的是"我正在改的那份文件"。

对于"多个 Agent 在同一个仓库上并行开发"这个具体问题，后者恰好是成本最低、语义最贴切的一层抽象。这也是为什么 JetBrains 的 ThinkRail 把 worktree 当作 workspace 的底层实现（我在 [10 月 26 日那篇拆解](https://github.com/kejun/blogpost/blob/main/2026-10-26-jetbrains-thinkrail-agentic-ide-worktree-spec-graph.md)里讨论过 IDE 侧的用法），而 Worktrunk 做的是把这一层从"能用"变成"好用"的 CLI 层。

## 二、worktree 的内部结构：为什么它便宜得离谱

要理解 Worktrunk 的设计空间，得先看清 `git worktree add` 到底做了什么。

执行 `git worktree add -b feat ../repo.feat` 之后，git 会在主仓库的 `.git/worktrees/` 下创建一个以 worktree 名命名的目录，里面只有几个小文件：

```
.git/worktrees/repo.feat/
├── HEAD          # 该 worktree 当前指向的分支（独立）
├── index         # 暂存区（独立，这是并行的关键）
├── commondir     # 指回主仓库的 .git
├── gitdir        # 指回 worktree 自己的 .git 文件
└── locked        # 可选，防止被 prune 误删
```

而新目录 `../repo.feat/` 里只有一个 `.git` **文件**（不是目录），内容是一行 `gitdir: /path/to/main/.git/worktrees/repo.feat`。

关键点在这里：**objects 和 refs 是共享的**。新 worktree 不复制任何 blob、tree、commit，它只是换了一套"指针 + 暂存区 + 文件检出"。所以创建一个 worktree 的耗时和仓库历史大小基本无关，通常是几十毫秒级；磁盘增量约等于工作区文件本身的大小。

这个设计的三个直接推论，构成了并行开发的全部基础：

**第一，`index` 独立，所以 `git add` 不打架。** 暂存区是并行开发中最容易被忽视的共享状态。两个 Agent 在同一个工作区里各自 `git add`，暂存区会变成两个任务改动的并集，谁也无法干净地提交自己那一份。worktree 把 index 变成 per-worktree 资源，这个问题从根上消失了。

**第二，`HEAD` 独立，所以分支切换不互相干扰。** 同一个分支在 git 里默认只能被一个 worktree 检出（除非 `--force`），这条限制看似不便，实际上是一道重要的护栏：它保证了"一个分支只有一份可写工作区"，避免了两个进程同时改同一个分支文件树这种最难调试的状态。

**第三，对象库共享，所以合并几乎零成本。** 因为所有 worktree 的 commit 都写进同一个 `objects/`，从 `feat` 合并到 `main` 不需要任何网络传输或对象复制，`git merge`/`rebase` 只是在同一份对象图上移动指针。这是 worktree 相对 clone 的决定性优势。

但便宜是有代价的。worktree 只共享"被 git 追踪的东西"，**所有被 `.gitignore` 排除的东西都不共享**——而现代项目的构建产物和依赖，恰恰全在 `.gitignore` 里。一个 Rust 项目的 `target/` 轻松 1–14 GB，一个 Node 项目的 `node_modules/` 动辄几万个文件。十个 worktree 就是十份冷启动：每次都要重新 `npm ci`、重新编译依赖，第一次跑测试要等几分钟。

**这才是并行开发真正的成本中心。** 不是 git 操作，不是模型调用，而是"每个隔离环境都要从零把依赖装一遍"。

## 三、Worktrunk 的核心洞察：worktree 的问题从来不是能力，是 UX

`git worktree` 这个特性 2015 年就进了 git（2.5），十年来用的人一直不多。原因很朴素：**它的心智负担和收益不成比例**。

官方命令要求你同时记住两套坐标：分支名和路径。创建一个 worktree 要写三遍分支名：

```bash
git worktree add -b feat ../repo.feat
cd ../repo.feat
```

删除时要先切走、再 remove、再删分支：

```bash
cd ../repo && git worktree remove ../repo.feat && git branch -d feat
```

这套 UX 对人类来说只是"有点烦"，对 Agent 来说却是致命的：**Agent 的每一步都是一次工具调用，每一步都可能失败、都可能被上下文截断。** 一条命令里塞三个动作，失败后无法幂等重试；路径和分支两套坐标不一致时，Agent 会开始猜。

Worktrunk 的全部设计都围绕一个决定展开：**worktree 只按分支名寻址，路径由模板推导。**

```bash
wt switch feat              # 切到 feat 对应的 worktree
wt switch -c -x claude feat # 创建 worktree 并直接启动 claude
wt remove                   # 清理当前 worktree + 分支
wt list                     # 带状态的列表
```

三条核心命令，对应三个动作，全部幂等。这条看似平淡的设计原则，其实是"agent-native 工具"和"人类工具"的分水岭：

- **单一坐标系统**：分支是唯一 ID，路径是派生量。Agent 不需要在两种命名之间做映射。
- **一条命令一个意图**：失败可以原样重试，不需要人工判断"执行到哪一步了"。
- **状态可查询**：`wt list` 输出结构化状态（未提交改动、与 main 的偏离、ahead/behind、CI 结果），并且支持 `--format=json`——这一点比什么都重要，因为 Agent 需要的是可解析的事实，不是给人看的表格。
- **目录切换由 shell 集成接管**：`wt config shell install` 注入 shell hook，让 CLI 能改变父 shell 的 cwd。否则子进程 `cd` 完就退出，Agent 依然停在原地。

`wt list` 的输出值得单独看一眼，它其实是一份"并行任务仪表盘"：

```
  Branch       Status      HEAD±     main↕    main…±    Remote⇅  Commit    Age  Message
@ feature-api  +   ↕⇡     +54   -5   ↑4  ↓1  +234  -24   ⇡3      6814f02   30m  Add API tests
^ main             ^⇅                                    ⇡1  ⇣1  41ee083    4d  Merge fix-auth
+ fix-auth         ↕|                ↑2  ↓1   +25  -11     |     b772e68    5h  Add secure token
```

`@` 是当前 worktree，`^` 是主 worktree，`+` 是其他 worktree。`HEAD±` 是未提交改动，`main↕` 是相对 main 的领先/落后提交数，`main…±` 是相对 merge-base 的行数变化。加上 `--full` 还会多两列：CI 状态和 LLM 生成的变更摘要。

这张表解决的是并行开发中最实际的认知问题：**当有八个任务在跑时，人（和 Agent）需要知道"哪个已经可以合并、哪个还有冲突、哪个已经死了三天"。** 没有这个视图，并行度越高，混乱越严重。

## 四、冷启动经济学：14 GB 的 `target/` 与 20 秒的 reflink

现在回到上一节留下的问题：如何让十个 worktree 不装十遍依赖。

Worktrunk 的答案是 `wt step copy-ignored`——把 gitignore 的文件从一个 worktree 复制到另一个。听起来很笨，复制 14 GB 怎么可能快？关键在"复制"的实现方式。

在支持 reflink 的文件系统上（macOS 的 APFS、Linux 的 btrfs 与 XFS、Windows 的 ReFS），复制走的是 copy-on-write：**新文件与源文件共享同一批磁盘块，直到任意一方发生写入，才真正分配新块。** 官方文档给出的实测数据非常直白：

| 命令 | 耗时 | 额外磁盘占用 |
|------|------|--------------|
| `cp -R target/`（完整复制） | 约 2 分钟 | 14 GB |
| `cp -Rc` / `wt step copy-ignored`（reflink） | 约 20 秒 | 约 0 |

Rust 项目里的实测效果更贴近日常：复制 `target/` 之后，首次构建从约 68 秒降到约 3 秒——因为所有依赖 crate 的编译产物都被复用，只需要编译真正改动的那一个 crate。

这里有三个容易被忽略的工程细节，值得逐条拆开。

**细节一：reflink 是 per-file 的，所以耗时随文件数增长，而不是随字节数增长。** `cp -Rc` 要为每个文件建立一个新的 inode 和 extent 映射，元数据操作是主要开销。所以 14 GB 但只有几千个文件的 `target/` 只要 20 秒；而 `node_modules/` 可能有 5–10 万个文件，即使总大小只有 500 MB，reflink 也可能要几十秒。这就引出了官方给 Node 项目的建议：如果没有原生依赖，直接符号链接比复制更快——

```toml
[pre-start]
deps = "ln -sf {{ primary_worktree_path }}/node_modules ."
```

**细节二：Python 的 venv 不能复制。** 因为 venv 里的 `pyvenv.cfg`、shebang、`.pth` 文件都写着绝对路径，复制到新目录后指向的还是老路径。这类"路径绑定"的依赖只能重建，官方建议直接用 `uv sync`——快到现在复制已经不划算了。这是一个很好的提醒：**CoW 不是万能加速器，它只对"内容寻址、路径无关"的产物有效。**

**细节三：复制必须是幂等的、增量的。** `copy-ignored` 默认跳过目标端已存在的文件，重复执行安全；需要覆盖时显式 `--force`。对 Agent 工作流来说这是硬要求——hook 可能因为超时被重跑，非幂等的初始化脚本会把环境搞坏。

而".worktreeinclude"这个设计，暴露了另一个层面的思考：**默认复制所有 gitignore 文件是危险的**。`.env`、本地数据库、API key、`~/.aws` 的软链，都可能被无声地搬进十个新目录。所以 Worktrunk 提供了 `.worktreeinclude` 白名单（文件必须既被 gitignore 又在白名单里），以及 `--require-include` 开关来强制白名单模式——后者与 Claude Code 桌面版的行为对齐。这是一个典型的"安全默认值 vs 便利默认值"的取舍，Worktrunk 选了便利，但把收紧的开关做得很明确。

## 五、隔离不止是目录：端口、数据库与进程组

复制完文件，第二个问题立刻出现：**十个 worktree 都想启动 dev server，都想连数据库，端口和库名全撞。**

这不是 worktree 特有的问题，而是所有"多环境并行"的通用问题。Worktrunk 的处理方式是把"环境变量"变成模板的一等公民：

```toml
[post-start]
server = "wt step tether -- npm run dev -- --port {{ branch | hash_port }}"

[list]
url = "http://localhost:{{ branch | hash_port }}"
```

`hash_port` 把分支名哈希到 10000–19999 区间，**同一个分支永远得到同一个端口**。这个"确定性"很重要：Agent 重连、人肉调试、CI 复现，都不需要再去问"这次分到的是哪个端口"。而 `wt list` 直接把 URL 列出来，等于给每个 worktree 一个稳定地址。

数据库的做法更完整，用 per-branch state vars 把派生值串起来：

```toml
[[post-start]]
db = """
docker run -d --rm \
  --name {{ vars.container }} \
  -p {{ vars.port }}:5432 \
  -e POSTGRES_DB={{ branch | sanitize_db }} \
  postgres:16
"""

[pre-remove]
db-stop = "docker stop {{ vars.container }} 2>/dev/null || true"
```

注意 `('db-' ~ branch) | hash_port` 这个写法——在分支名前加前缀再哈希，是为了让数据库端口和 dev server 端口落在不同的哈希点上，避免碰撞。`sanitize_db` 负责把分支名（可能含 `/`、`-`、大写、数字开头）转成合法库名，并附加短哈希防重名。

还有一个细节值得单独说：`wt step tether`。dev server 通常是"启动一个 shell，shell 再 fork 出 node 进程"的进程树，直接 kill 父进程经常留下孤儿进程占着端口。`tether` 把命令放进独立进程组，在 worktree 被删除时整组回收。**这是"隔离"这个词最容易被忽略的一层：不只是文件系统要隔离，进程生命周期也要。**

## 六、Hooks：把"环境准备"从 Agent 的上下文里拿走

Worktrunk 的 hook 系统有十种事件，按生命周期分五组，每组再分 `pre-` 和 `post-`：

| 事件 | `pre-`（阻塞） | `post-`（后台） |
|------|----------------|-----------------|
| switch | `pre-switch` | `post-switch` |
| create | `pre-start` | `post-start` |
| commit | `pre-commit` | `post-commit` |
| merge | `pre-merge` | `post-merge` |
| remove | `pre-remove` | `post-remove` |

这个设计里最值得学的是**阻塞语义的划分**：`pre-*` 失败会中止整个操作，`post-*` 在后台跑、输出写日志。

为什么这个区分重要？因为它对应了两类完全不同的任务：

- **正确性依赖的步骤**必须阻塞。比如生成 `.env`、安装依赖、`uv sync`——后面的 `--execute` 命令（比如直接启动 Claude）需要它们完成。
- **耗时但不阻塞的步骤**必须后台化。比如起 dev server、跑全量构建、复制缓存。如果 `post-start` 是阻塞的，创建 worktree 就要等 20 秒的 reflink 加 60 秒的构建，Agent 的首次响应延迟直接翻倍。

官方文档明确建议："优先用 `post-start` 而不是 `pre-start`，除非后续步骤真的需要它完成。" 这条建议背后是一个很实际的观察：**Agent 的交互是"创建环境 → 立刻开始读代码 → 稍后才跑测试"，把重活放在后台，正好和这个节奏对齐。**

`wt merge` 时的 hook 顺序也被明确定义：`pre-commit → pre-merge → pre-remove` 串行阻塞，全部 `post-*` 在合并完成后并行启动。这个顺序不是随便排的——`pre-commit` 跑格式化/lint，`pre-merge` 跑测试和安全扫描，`pre-remove` 保存测试产物。三者的失败后果不同：前两个失败应该阻止合并，最后一个失败只应该告警。

**但 hook 系统真正的难题不是调度，是安全。**

`.config/wt.toml` 是仓库里的文件。这意味着：**克隆一个仓库，就获得了一份可以在你机器上执行的 shell 脚本。** 这不是理论风险——`post-start = "curl ... | sh"` 完全合法。

Worktrunk 的应对是首次运行审批：

```
▲ repo needs approval to execute 3 commands:

○ pre-start install:
   npm ci
○ pre-start build:
   cargo build --release
○ pre-start env:
   echo 'PORT={{ branch | hash_port }}' > .env.local

❯ Allow and remember? [y/N]
```

审批结果存进 `~/.config/worktrunk/approvals.toml`；**命令内容一变，就要重新审批**（这挡住了"先批准无害命令、后续提交改成恶意命令"的攻击）；拒绝时跳过该操作的全部项目命令，但不影响已保存的审批。`--yes` 供 CI 使用，`--no-hooks` 供临时绕过。

这是一个务实的设计，但它只保护"人手动创建 worktree"的场景。**如果 Agent 自己跑 `wt switch`，谁来做这个审批？** 这是所有 agent-native 工具共同的开放问题：审批链路要么上移到 Agent 的权限层（比如 Claude Code 的 allowlist），要么在 CI/沙箱里以 `--yes` 运行并接受"仓库代码可信"的前提。Worktrunk 选择了把决定权交给人，这在当下是诚实的做法，但也意味着它还没完全解决"无人值守的并行"。

## 七、`wt merge`：把 GitHub 的 Merge 按钮搬到本地

并行开发的下半场是合并。十个 worktree 跑完，就有十个分支等着进 main。

传统做法是 push → 开 PR → CI → review → merge，一轮下来十几分钟到几小时。对于 Agent 生成的、以"小步快跑"为特征的分支，这套流程的开销远大于收益。Worktrunk 的 `wt merge` 直接在本地复刻了 GitHub 的 squash-merge 语义：

```
commit → squash → rebase → hooks → fast-forward → cleanup
```

具体来说：把源分支的所有提交 squash 成一个、rebase 到目标分支、跑 `pre-merge` 测试、把目标分支 fast-forward 到新提交、然后删掉 worktree 和分支。整个流程一条命令，而且**冲突会留在源 worktree 里**让你（或 Agent）解决或 abort，不会把目标分支搞成半合并状态。

这个顺序有两个值得称道的设计决策：

**其一，默认 squash。** Agent 产生的提交历史通常是"wip"、"fix"、"fix again"、"actually fix"——保留它们只会污染 main。squash 成一条带 LLM 生成信息的提交（`wt step commit` 支持从 diff 生成 conventional commit 风格的消息），更符合"一个任务 = 一个可回滚单元"的原则。需要保留历史时用 `--no-squash`，需要 merge commit 时用 `--no-ff`。

**其二，fast-forward 而不是 merge commit。** 因为 rebase 已经把源分支接到了目标分支顶端，fast-forward 只是移动指针，不产生新的合并节点。这让 main 保持线性，`git log` 可读，`git bisect` 有效。

但这里有一个必须点明的**结构性风险**：`wt merge` 的测试跑在本地，跑的是 `pre-merge` hook 里配置的命令。如果这个命令是 `cargo test`，那它只验证了单元测试；集成测试、E2E、安全扫描、跨平台构建，全都不在链路里。**本地 merge 越顺滑，越容易绕过 CI。** 合理的做法是把 `pre-merge` 配置成"和 CI 第一层完全一致"的命令集，把完整 CI 留给 push 之后的流水线；而不是把 `pre-merge` 当成 CI 的替代品。

另一个细节：`wt merge` 合并的是"源分支到目标分支"，方向与 `git merge` 相反（`git merge` 是把目标合进当前分支）。这个方向选择更符合"我在功能分支上，我要把它合进 main"的心智模型，也和 GitHub 的 PR 语义一致。小设计，但减少了一类经典误操作。

## 八、能力边界：worktree 不隔离什么

宣传语说"隔离"，但工程上必须精确：worktree 只隔离了**文件系统里的工作区**。以下这些，它一个都没隔离：

| 共享资源 | 后果 | 缓解手段 |
|----------|------|----------|
| Docker daemon | 容器名、网络、端口、volume 全局冲突 | 用分支名做容器名前缀 + `hash_port` |
| 宿主机端口空间 | 两个 worktree 抢 3000 端口 | `hash_port` 派生确定性端口 |
| 数据库实例 | 十个 Agent 写同一个 schema，互相清表 | per-branch 容器 + per-branch 库名 |
| `~/.cache`、`~/.cargo`、`~/.npm` | 并发写缓存可能损坏（多数工具有锁，但不保证） | 显式设置 per-worktree 缓存目录 |
| GPU / 显存 | 十个 Agent 同时跑推理，OOM | 外部调度器或信号量 |
| `.git/hooks` | 共享，一个 Agent 装 hook 影响所有 worktree | 尽量用 wt hooks 替代 git hooks |
| git 配置与凭据 | `user.email`、credential helper 全局共享 | 明确接受，或按仓库覆盖 |
| 网络与外部 API 配额 | 十个 Agent 同时打同一个 rate limit | 网关层限流 |

这份表说明了一件事：**worktree 是"文件系统级隔离"，不是"环境级隔离"。** 它解决了 80% 的日常冲突（文件、index、分支），但剩下 20% 是容器/VM 才能解决的。

那么什么时候该上容器？一个粗略的成本模型：

设并发 Agent 数为 `N`，单份完整环境（镜像 + 依赖 + 构建产物）大小为 `S`，环境冷启动时间为 `T`，任务平均时长为 `D`。容器方案的成本约等于 `N × (S 磁盘 + T 启动)`；worktree + CoW 方案约等于 `N × (S 元数据 + T_install)`，其中 reflink 的 `S` 只剩 inode 开销，`T_install` 通常从分钟级降到秒级。

当 `N ≤ 10`、任务以"读改代码 + 跑单测"为主、依赖能在本机装下时，worktree 的性价比碾压容器；当 `N > 20`、或任务需要不可信代码执行、需要不同内核/系统库、需要网络隔离时，容器是唯一正确答案。**两者不是替代关系，是分层关系**：外层容器保证安全边界，内层 worktree 保证开发效率。

Worktrunk 自己也很清楚这个边界。它没有做容器编排，没有做资源配额，没有做网络代理——它只把"worktree + hooks + 状态视图"这三件事做到极致。这种克制在一个所有人都在做"平台"的年份里，反而显得稀缺。

## 九、一份可落地的配置，与三个必然踩的坑

如果要把这套东西用起来，最小的可用配置大概是这样：

```toml
# .config/wt.toml
[post-start]
copy = "wt step copy-ignored --require-include"
deps = "npm ci --prefer-offline"
server = "wt step tether -- npm run dev -- --port {{ branch | hash_port }}"

[pre-merge]
test = "npm run lint && npm run test:unit"

[list]
url = "http://localhost:{{ branch | hash_port }}"
```

配套的 `.worktreeinclude` 只列真正需要复用的东西：

```
node_modules/
.next/
.env.local
```

三个我认会踩的坑，提前说：

**坑一：`node_modules` 的文件数会惩罚 reflink。** 几万个文件的元数据操作可能比 `npm ci --prefer-offline` 还慢。先测一次 `time wt step copy-ignored`，再决定是复制还是符号链接。符号链接的代价是"所有 worktree 共享一份依赖"——如果某个 Agent 要升级依赖，就会污染其他人。

**坑二：`.env` 是并行开发最大的隐形耦合。** 如果十个 worktree 共用一份 `.env`，那么"改配置"这个动作本身就成了并发写。理想做法是把 `.env` 生成放进 `post-start`，用模板变量派生 per-branch 的值（端口、库名、回调地址）。这也是 Worktrunk 把模板系统做进 hook 的原因。

**坑三：worktree 会累积，`git worktree list` 会越来越长。** Agent 崩溃、任务被取消、分支被放弃，都会留下垃圾目录和锁。`wt step prune` 可以清理已合并的分支，但**未合并的、有未提交改动的 worktree 需要人判断**。这在无人值守场景下是个真实的运维负担：磁盘会被慢慢吃满，`git` 的 `.git/worktrees` 元数据也会膨胀。

## 十、判断：并行度的上限，由环境编排决定

回到开头那个问题：为什么 2026 年会出现一个 11,500 星的 git worktree CLI？

因为行业已经到了一个拐点：**单个 Agent 的能力不再是瓶颈，"同时跑多少个 Agent"成了瓶颈。** 而并行度不是模型参数决定的，是由环境编排决定的——你能不能在一秒内开出一个干净、依赖齐全、端口不冲突、能被独立回收的工作区。

从这个角度看，Worktrunk 的价值不在它省了多少条命令，而在它把并行开发需要的隐含契约显式化了：

- 用分支名做唯一标识 → 消除坐标歧义；
- 用 CoW 复用构建产物 → 把冷启动从分钟压到秒；
- 用 hook 生命周期管理环境 → 把"准备环境"从 Agent 的上下文里剥离；
- 用 `wt list --format=json` 暴露状态 → 让 Agent 能自己判断"现在能不能合并"。

这四条合起来，其实定义了一种新的工具形态：**为 Agent 设计的工具，不该是给人用的工具的简化版，而应该是"幂等、单意图、状态可查、成本可预测"的重新设计。** `git worktree` 提供了能力，Worktrunk 提供了契约。

它当然不完美。安全审批在无人值守场景下没有答案；本地 merge 容易绕过完整 CI；worktree 只隔离文件系统，容器该做的事它一件也做不了。但这些都是"边界清晰"的不完美——你知道它在哪里失效，也就知道该在哪里补上容器。

而这，可能比又一个"全能 Agent 平台"更有价值。

---

**参考与延伸**

- Worktrunk 仓库：<https://github.com/max-sixty/worktrunk>（Rust，MIT/Apache-2.0，11.5k stars）
- 官方文档：<https://worktrunk.dev>（hooks、copy-ignored、merge pipeline 的完整语义）
- `git worktree` 内部结构：`.git/worktrees/<name>/{HEAD,index,commondir,gitdir}`
- reflink 支持矩阵：APFS（macOS）、btrfs / XFS（Linux）、ReFS（Windows）；ext4 / NTFS 无 reflink
- 关联阅读：[当 IDE 开始围着 Agent 重写：JetBrains ThinkRail 深度拆解](https://github.com/kejun/blogpost/blob/main/2026-10-26-jetbrains-thinkrail-agentic-ide-worktree-spec-graph.md)
