# 当 50 个 Agent 同时往一个分支提交：gitai 深度拆解——Scion 的开源实现，与「合并吞吐」这件被忽视的基础设施

2026 年 10 月 15 日，一个叫 `feder-cr/git-ai` 的仓库出现在 GitHub 上。四天之后，它拿到 2452 颗星、270 个 fork，登上 Trending。它的自我介绍只有一句话：

> Git designed for AI agents.

这句话很容易被当成又一个营销口号。但点开 README 会发现，它不是给 git 套一层 CLI 包装，也不是给 Agent 做一个"更好用的 commit 工具"，而是把 GitLab 的 Gitaly 服务端整个 fork 过来，重写了落地（land）路径、存储核心和权限模型。它做的事情，和 Anthropic 十月初那篇《Redesigning source control》里描述的 Scion，是同一件事——只不过 Scion 是内部系统，永不开源，而 gitai 是它的公开实现。

这件事值得认真对待，因为它触及了一个正在变得紧迫、但大多数人还没感受到的问题：**当写代码的人从人类变成 Agent，版本控制的瓶颈不再是"写"，而是"合"。**

## 一、先看一组让人不太舒服的数字

Anthropic 在那篇文章里给了两个时间点的对比：2026 年 5 月，他们平均每天合并约 2500 次代码变更；到 9 月，这个数字超过 30000。四个月，12 倍。他们自己的说法是"对合并代码的潜在需求几乎是无限的，每移除一个瓶颈，代码产量立刻再上一个台阶"。

配套的基础设施数字更直观：

- 主分支历史接近 **100 GB**；
- 压缩后的工作副本超过 **25 GB**；
- 每天大约 **2500 万次 checkout**（仅 CI，不含开发环境和 Agent 沙箱）；
- 如果每次都朴素地拉取，每天会产生 **600 PB** 的 git 流量。

为了扛住这些，他们在峰值时维护了**几百个内部 git 镜像**，再加上 blob 存储里的仓库快照（seeds）。这套组合在合并率低的时候能用，但随着 main 的推进速度加快，seed 离 tip 越来越远，依赖历史的 diff、blame 在部分克隆上越来越难保证正确。

于是他们问了一个很朴素的问题：如果从第一天就假设"客户端永远在线"，版本控制会长成什么样？

这个问题同样适用于 gitai。它对这个问题的回答，构成了整篇文章的技术骨架。

## 二、Scion 的五条公理，以及 gitai 的对应实现

Anthropic 总结的五条原则，值得逐条对照，因为它们几乎每一条都在和 git 的原始设计对着干：

**1. 客户端永远在线。** git 假设客户端可以离线工作，所以每个克隆都是完整仓库。但 Agent 和 CI job 按定义就是在线的。既然在线，就没必要本地持有完整历史——需要什么，向服务器要。

**2. 客户端与服务端不对称。** 在 git 里，每个客户端都能当服务器。Scion 里，服务端负责回答文件历史、blame、创建提交、执行 merge/rebase；客户端只维护一个有界对象缓存、把文件铺到磁盘上、监听文件系统变化。客户端算得很少，但本地数据也少得多。

**3. 源码管理是一个可以被任意程序调用的服务。** 一个 CI job 想知道"这行最后是谁改的"，在 git 世界里要么本地留一份仓库，要么祈祷托管平台提供对应 API。Scion 把所有查询都做成 API，很多 job 根本不需要本地仓库。

**4. 一切必须水平扩展。** 几百个镜像的方案在仓库超过单机磁盘/内存上限时就崩了。Scion 里没有"某个地方存在完整副本"这回事，连服务端也没有，也因此没有 packfile、没有仓库维护。

**5. 提交必须廉价、增量、无锁。** git 是本地提交、之后 push；Scion 是服务端提交，没有 push 这一步。于是 commit / rebase / merge 的成本必须与**变更大小**成正比，而不是与**仓库大小**成正比。相应地，Scion 极力避免 ref——因为 ref 是全局状态，是扩展性的天敌。

gitai 把这五条落到了具体组件上。它不是从零写一个 VCS，而是站在 Gitaly 的肩膀上：

| Scion 的设计点 | gitai 的实现 |
|---|---|
| 永远在线的客户端，按需取对象 | `ObjectService.GetObjects` / `GetTree`，`graft clone`、`graft sparse` |
| 历史查询上移到服务端 | `DerivedDataService`（Blame / PathHistory）+ 既有 CommitService |
| 没有 merge queue 的落地 | `OperationService.UserLand`，compare-and-swap 加重试 |
| 变更集日志 | `ChangesetService` 读 `<gitdir>/graft/changesets.jsonl` |
| 派生数据只算一次 | 以 (kind, commit, path) 的 SHA-256 为键的内容寻址存储 |
| 严格的多级缓存 | `graft-cache` 的 daemon / regional 两层，逐对象校验 |
| Agent 一等公民 | 每 Agent token、RPC allowlist、分支策略 |

关键的工程判断是"fork Gitaly 而不是重写"。Gitaly 已经把 Git 的底层能力包装成了 gRPC 服务，上游所有 RPC 保持可用，这意味着 gitai 可以渐进式替换，而不是要求用户一夜之间迁移整个工作流。代价是背上了一个庞大的 Go 代码库和 GitLab 的历史包袱——这一点我们后面会算账。

## 三、问题的真正形状：CAS 循环里的 27 次重试

要理解 gitai 做了什么，必须先看清 git 托管在并发写入下到底哪里疼。

一个分支的更新，本质是一次**比较并交换（CAS）**：读当前 tip T，把新提交 C rebase 到 T 上得到 C'，然后尝试把 ref 从 T 原子地改成 C'。如果在这期间别人先把 T 改成了 T2，你的 CAS 就失败，得从第一步重来。

单个开发者偶尔撞上一次，无感。但当 50 个 Agent 同时往 main 上落变更时，这个循环会退化成活锁式的抖动。gitai 自己的基准测试给出了非常具体的数据（50 个 Agent，每人 5 次变更，共 250 次，其中 20% 故意制造冲突）：

| 指标 | 关闭批处理的"经典"模式 | gitai 批处理 |
|---|---|---|
| 成功落地数 | 100–101 | 200 |
| 每次成功落地的尝试次数 | **27** | **1.0** |
| 每分钟落地数 | 240–272 | 1862–2544 |
| p99 延迟 | 6.3–7.0 s | 1.5–1.8 s |

请注意"27"这个数字。它意味着在一个 50 Agent 的竞争窗口里，一次变更平均要重试 26 次才能成功——而这 26 次里，绝大部分工作（rebase、写对象、跑 hook）都是白做的。更糟的是，默认的 `max_attempts = 20`，所以在更激烈的场景下，变更不是变慢，而是直接失败。

这就是"merge queue"存在的原因：与其让所有人互相踩，不如排队。但队列本身是串行的，吞吐上限被单次处理时间锁死。gitai 的答案不是队列，而是**把竞争从分支挪到进程内的一小块内存里**，然后用一次 ref 更新发布一整批结果。

## 四、批处理车道：把 27 次重试压成 1 次

gitai 把这套机制叫 **land lane（落地车道）**。一个 lane 由三元组 `(storage, 相对路径, 分支)` 唯一确定，注册在 `landlane.Registry` 里。规则很干净：

- 请求按 FIFO 进入车道；
- 一个车道同一时刻只跑一个 batch，不同分支的车道并行；
- batch 在"首个排队请求等待满 `window`"或"排队数达到 `max_size`"时成型，先到先算；
- 已在队列里但上下文被取消的请求直接移除，调用方拿到 `Canceled`。

默认参数是 `window = 10ms`、`max_size = 50`。10 毫秒这个值不是拍脑袋：它大致等于一次本地 fsync 的量级，既能攒出有意义的批次，又不会让单个请求等太久。

一个 batch 的执行过程值得完整看一遍，因为它把很多"必须原子"的东西拆解得很清楚：

1. 在仓库上开**一个** quarantine（隔离对象目录），读一次分支 tip；
2. 按顺序把每个请求落到"滚动 tip"上：
   - 解析 commit ID，非法则单独失败（`InvalidArgument`）；
   - 对该请求的 actor 评估 standalone 访问策略，拒绝则单独失败（`PermissionDenied`）；
   - 若 commit 已可从滚动 tip 到达 → 报 `already_landed`，什么都不改；
   - 若滚动 tip 是 commit 的祖先 → 快进，滚动 tip 前移；
   - 否则 rebase（或按 `STRATEGY_MERGE` 合并），冲突则**只让这一个请求失败**；若请求带了 `resolve_conflicts` 且解析器启用，先尝试自动解决；
3. 全部处理完后，用**一次** CAS 把原始 tip 换成最终滚动 tip。

注意这里的核心洞察：**冲突不再是全局失败，而是局部失败。** 在一个 batch 里，一个请求的 rebase 冲突不会影响其他 49 个请求的落地。这正是批处理能同时提升吞吐和成功率的原因——经典模式下，一次 CAS 失败意味着所有人都得重来；批处理模式下，一次 CAS 失败只影响一个 batch，而且 batch 内部的顺序执行天然消除了绝大部分竞争。

变更集日志里，这次更新记为 `operation=land_batch`，带一个成员列表；如果 batch 里只成功了一个，则记成普通的 `land`。这个细节很重要：审计日志不应该因为内部优化而改变语义。

### 更狠的一层：把 git 进程数压到常数

批处理解决了竞争，但没解决单次落地本身的成本。gitai 的 phase 4b 做了另一件事：把每次落地的 git 子进程调用压到几乎恒定。

在此之前，一次落地要付出约 9 个短 git 进程的开销；此外每个新对象写盘时 fsync 一次、quarantine 迁移时又 fsync 一次，一次批处理请求背后大约 **12 次 fsync**。在 ext4 上一个 fsync 约 6ms 的机器上，这就是 70ms 起步的纯 I/O。

优化后的判定逻辑是：先用 `git cat-file --batch-check` 剥一次 commit，再用 **一次** `git rev-list --parents commit ^tip` 拿到"这次变更新增的提交列表"，然后：

- 列表为空 → 已经落地；
- tip 是列表里某个提交的父提交 → 快进；
- 否则需要 rebase，此时再用一次 `git merge-base --independent` 判断列表是否精确（抵消提交时间戳偏斜导致的 `rev-list` 提前终止）。

结论是：**无论历史多长，一次落地最多 4 个 git 进程。** 这个性质非常关键——它把成本与仓库规模解耦，而不是与变更规模解耦。Anthropic 那条"提交成本必须与变更大小成正比"的公理，在这里第一次落到了具体实现上。

配套的还有 `UserCommitFiles` 的优化：单文件请求从 10–15 个 git 进程降到 6 个。基准数据显示中位数从 217ms 降到 177ms，p99 从 600ms 降到 444ms。幅度不算惊人，但这类优化是可以叠加的。

## 五、存储核心：当仓库状态住进数据库

如果说批处理是"快"，存储核心就是"能扩"。

gitai 的 `[graft.storage]` 是可选项（默认关闭），一旦开启，仓库状态的真相就从磁盘上的 ref 文件，搬到了**强一致的数据库 + 对象存储**：

```
            clients (SDK, graft CLI, git over SSH/HTTP)
                 |                       |
          +------v------+         +------v------+
          |   node A    |         |   node B    |   任意节点服务任意仓库
          |  gate/voter |         |  gate/voter |
          |   syncer    |         |   syncer    |
          |  local git  |         |  local git  |   本地仓库只是缓存
          +--+-------+--+         +--+-------+--+
             |       |               |       |
   changesets|       |packs          |       |
             v       v               v       v
       +-----------+  +--------------------------+
       | database  |  | object storage (bucket)  |
       | SQLite/PG |  | repos/<id>/packs/...     |
       +-----------+  +--------------------------+
```

几个设计细节值得单独拎出来：

**写路径的顺序是"先传 pack，再提交 changeset"。** 新对象先作为**一个不可变 pack** 上传到 `repos/<repo_id>/packs/<sha256>-<nonce>.pack`，key 里带随机 nonce，因此"一个 pack 恰好属于一个 changeset"，两次字节相同的写入会存成两个对象。这样做的代价是存储放大，换来的是一个非常强的性质：**changeset 永远不会引用一个没有完整上传的 pack**。对象创建用条件写（S3/GCS/Azure）或 `link(2)`（file bucket，因为 gocloud 的 file driver 的 create-only 写不是原子的——它会先检查 key 不存在再 rename，两个写者都会成功）。

**提交点是数据库事务。** 在 authoritative 模式下，`Prepared` 阶段 git 已经持有 ref 锁，此时只做一次 `for-each-ref` 读期望旧值，然后用**每个 ref 一次 CAS** 在一个事务里提交 changeset。事务失败，git 事务中止。CAS 冲突会被 land 路径当成"输掉了 git 竞争"来处理，于是自动追赶重试。

**读路径是"追平再服务"。** 每个节点在处理请求前，先把本地仓库追到数据库 head：下载缺失 changeset 的 pack、校验、建索引、无 hook 地移动 ref。一个完全没有该仓库的节点会从 changeset 1 开始重建一个新的 bare reftable 仓库。水位记在 `<gitdir>/graft/storage/applied` 里。

**服务器变成可重建的缓存。** 这句话是整个设计的题眼。因为真相在数据库和对象存储里，任何一个节点挂掉都不影响正确性，加节点就是加缓存容量。这直接对应 Scion 的"没有完整副本、没有 packfile 维护"。

还有一个工程上很实在的优化：**group commit**。changeset 日志按 ticket 顺序合批，一次 fsync 落多个事务；quarantine 迁移也改成每个目录 fsync 一次而不是每个文件一次。实测提交阶段（从 hook 提交到条目持久化）平均 22–27ms，每次组写包含 2.5–3.1 个事务，单次写 13–18ms。对比优化前 profile 里的 92–99ms ticket 等待加 7ms 追加，这是数量级的改善。

顺带说一句，这个项目在 benchmark 文档里罕见地诚实：他们明确写了"提交阶段 ≤20ms 的目标**没有达到**（实际 22–27ms）"，也写了"p99 不高于基线这一条**并非每一对都满足**"。这种把失败指标摊开写的做法，比一堆漂亮数字更值得信任。

## 六、派生数据：Bloom 过滤器与被「预先算计」的 blame

Scion 文章里有个容易被忽略但极其重要的概念：**派生数据（derived data）**。

changeset 只记录"相对第一个父提交改了哪些文件"，它本身回答不了"谁最后改了这一行""哪些提交动过这个路径"。这些答案需要额外的数据结构。Scion 的做法是把所有非 changeset 的东西统称派生数据，用一套通用机制计算，且每种类型都是**递归定义**的——它在某个 changeset 上的值，由它在父 changeset 上的值算出。

好处有三：新增一种派生数据很容易；每种都可以独立选择"急切算"还是"惰性算"；因为客户端看不到内部结构，可以随时优化而不破坏兼容。

gitai 的 `internal/graft/derived` 是这个思路的直接翻译。存储键是 `(kind 名, kind 版本, commit ID)` 的哈希，写在 `<gitdir>/graft/derived/` 下，一 key 一文件，写入用临时文件 + rename 保证原子。因为键里含 commit ID，而 commit 不可变，所以**存下来的值永远不会过期，永远不需要失效逻辑**——这是个很漂亮的简化。版本号进 key 则意味着"编码或语义变了就 bump 版本，旧条目自然再也不会被读到"。

目前实现了两类：

**`graph`**：每个提交存 `uint32 generation` + 若干 skip pointer（第 k 个是沿第一父走 2^k 步的提交）。generation 是父提交最大值加一，根为 1。有了它，`IsAncestor`、`MergeBases`、`MergeBase` 都能在**不递归**的情况下回答，因此历史深度不再是限制。索引在内存里用 LRU 缓存最多 10 万条。有意思的是，默认 `graph_ancestry = false`，也就是默认还是问 Git，只有显式打开才走图索引——典型的"先在旁边跑，验证等价再切换"的保守工程风格。

**`changed-paths`**：每个提交存一份"相对第一父改了哪些文件"的摘要。摘要包含两部分：

- 精确的排序文件列表，最多 2 万条；超过就记成 overflow，查询退化为按路径限制的 diff；
- 一个覆盖所有目录前缀和路径的 **Bloom 过滤器**，**每 key 16 bit、4 个哈希函数，误判率约 0.2%**。

这里的关键是：Bloom 过滤器的**否定答案永远正确**。所以它可以安全地用来"跳过肯定没改过这个路径的提交"，而不会漏掉任何真正改过的提交。`PathHistory` 于是变成了"沿 lastmod-firstparent 链走，但用摘要做预过滤，证明没改的直接跳过，不读 tree"。查询只读摘要、从不计算摘要；摘要由 eager 机制在 ref 更新提交后异步预热。

这是一个值得记住的模式：**用概率数据结构做保守剪枝，把"精确但昂贵"的路径留给少数情况**。它比"缓存整个 diff"省空间，比"每次重算"省时间，而且正确性不依赖概率——概率只影响性能。

## 七、边界感：AI 被刻意放在服务器之外

gitai 最让我意外的一点，不是它用了 AI，而是它**克制地不用 AI**。

README 里有一句明确声明：*"服务端从不调用语言模型，每个 AI 功能都能配任意 provider，或者干脆不用。"* 这在 2026 年一个 AI 项目里几乎算反潮流。

具体体现在冲突解决上。当一次 land 因为 merge 冲突失败，且请求带了 `resolve_conflicts`、操作者也启用了 resolver 时，服务端会把冲突的 base/ours/theirs 三方内容打包成 JSON，通过 stdin 或 HTTP POST 发给一个**独立程序** `graft-resolve`。协议是版本化的（当前 v1），请求里包含仓库、分支、tip、commit、merge base、双方 commit message、actor，以及每个冲突文件的路径、模式和三份 base64 内容。

服务端对解析结果做校验，然后自己构造 merge commit，加上 trailer：

```
Graft-Resolved-By: graft-resolve/trivial,union
Graft-Resolved-Path: docs/CHANGELOG.md
Graft-Resolved-Path: pkg/config.go
```

失败（无解析器、路径被拒、答案非法、超时、无法解决）一律回退成普通的 `merge_conflict`，分支绝不留在半成品状态。

权限控制也做得很细：`paths_allow` / `paths_deny` 用 glob（注意 `*.lock` **不**匹配 `sub/go.lock`，要按深度逐个写），`max_files` 默认 20，`max_file_bytes` 默认 1MB，`actors` 限定哪些身份可以请求解析。而且 actor 来自 token 认证，**不是**调用方自报的 `gl_username`——这个区分很关键，否则任何人都能冒充有权限的身份。

同样的边界感出现在另外两个"Agent 化"组件上：

- **`graft-verify`**：变更先落地，测试在 tip 上跑；失败则二分定位，用 `UserRevert` 回滚罪魁，commit 上带 `Graft-Auto-Revert` trailer，并限制每小时的回滚次数。这是"先合后验"（land-then-test）而非"先验后合"，在 Agent 高频提交下更现实——因为等待 CI 的串行队列会把吞吐打回原形。
- **`graft-superfan`**：每个组件一个"监控 Agent"，跟随 changeset 流（不是服务器遥测），用确定性规则生成摘要，可选的 LLM 只做总结。同样，AI 是可选增强，不是正确性依赖。

## 八、该泼的冷水

写到这里，需要冷静一下。gitai 很聪明，但它不是万能药，而且有几个必须看清的限制。

**第一，基准测试的规模有限，且噪音不小。** 50 Agent × 5 变更 = 250 次落地，跑在一台 16 核机器上（Intel Core Ultra 7 255H，WSL2，ext4 虚拟盘）。这个规模和 Anthropic 每天 3 万次合并差着两个数量级。更值得注意的是他们自己披露的：两次 base 运行在 50 Agent 下吞吐差了近一倍（1427 vs 833 lands/min），"因为负载上升，逐对数字的波动比 100 Agent 下的整体效应更大"。所以"8 倍吞吐"这类结论，方向可信，倍数要打折看。

**第二，200/250 不是 bug，是设计。** 关闭 resolver 时，50 个故意冲突的变更被退回给 Agent，这是正确行为。但这也说明：**批处理提升的是无冲突场景的吞吐，冲突仍然要靠上游解决。** 如果你的 Agent 工作流本身就容易在同一批文件上打架，批处理帮不了你，你需要的是任务切分策略。

**第三，fork Gitaly 是一笔长期负债。** 上游 Gitaly 是 GitLab 的核心组件，演进速度快、内部耦合深。gitai 目前的策略是"所有上游 RPC 保持可用"，这在初期是巨大优势，但长期要持续 rebase 上游、还要维护自己新增的 `ObjectService`、`ChangesetService`、`DerivedDataService`、`UserLand`。这类 fork 的典型命运是被上游的变化拖死。项目自己也很清醒，README 里直接列出了已知缺口——比如存储核心的 **pack 垃圾回收还没做**。

**第四，`changesets.jsonl` 的 flock 方案有天花板。** 默认（非 storage core）模式下，变更集日志是 append-only JSONL 加文件锁。这在单机、几十个 Agent 的场景够用，但它本质上还是一个单点串行写。真正的水平扩展要等 `[graft.storage]` 的 authoritative 模式成熟，而那个模式目前还需要"先 shadow 导入、再切 authoritative"的迁移流程，运维复杂度不低。

**第五，它解决的是"合并吞吐"，不是"代码质量"。** 当一个系统能把 50 个 Agent 的提交在一秒内全部落进 main，随之而来的问题是：谁来看这些代码？gitai 给了"语义化审批规则"（纯注释变更需要的审批数可以少于逻辑变更），这个想法很有意思，但它把"什么样的变更需要多少人看"变成了可配置策略——配置错了，等于自动放行。

## 九、结论：Agent 原生基础设施的三条判据

把 gitai 放回更大的图景里，它其实回答了一个正在浮现的问题：**什么样的基础设施才算"Agent 原生"？**

从 Scion 和 gitai 的实现里，可以抽出三条判据：

**一、成本必须与"变更规模"成正比，而不是与"系统规模"成正比。** 一次 land 最多 4 个 git 进程、与历史长度无关；一次提交只写增量 changeset、与仓库大小无关。任何随仓库增长而线性变慢的操作，在 Agent 时代都会变成硬墙。

**二、全局状态越少越好。** ref 是全局状态，merge queue 是全局状态，文件锁也是全局状态。gitai 把 ref 更新压缩成"每 batch 一次 CAS"，把队列换成进程内的 lane，把锁的持有时间压到只读一次旧值。减少全局状态，就是减少"50 个 Agent 互相等待"的可能性。

**三、正确性不能依赖概率，但性能可以。** Bloom 过滤器只用来做否定剪枝，LLM 只用来解决冲突和写摘要，两者失效时都退回确定性路径。这个"AI 在边界外、确定性在内核"的分层，可能是所有 Agent 基础设施都应该抄的作业。

至于 gitai 本身，我的判断是：**现在就该读它的代码和设计文档，但不一定现在就该上生产。** 版本 0.2.0，接口还会变，pack GC 还没做，storage core 的云上条件写甚至标注了"untested here"。但它的 `LAND-BATCHING.md`、`STORAGE.md`、`DERIVED.md` 这几份文档，把"高频并发写入下的版本控制"这个问题拆解得极其清楚，光是读文档的收益就已经超过很多生产系统。

四天 2452 星，说明有大量的人正在遇到同一个问题。这大概是 2026 年最值得关注的信号之一：**当 Agent 的数量超过人类开发者，我们脚下这层用了二十年的地基，开始需要重浇了。**

---

**参考资料**

- gitai 仓库与设计文档：https://github.com/feder-cr/git-ai（MIT，v0.2.0，2026-10-15 创建）
- Anthropic Engineering, *Redesigning source control*（2026-10，2026-10-15 更新）
- gitai `doc/graft/ARCHITECTURE.md`、`LAND-BATCHING.md`、`STORAGE.md`、`DERIVED.md`、`RESOLVE.md`、`BENCH.md`
- Hacker News 首页与 GitHub Trending（2026-10-19/20 数据）
