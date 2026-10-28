# 当终端变成一个库：Ghostty 1.4 深度拆解——libghostty、100% Kitty 图形与 Agent 时代的终端内核

> 2026 年 10 月 27 日，Ghostty 1.4 发布，Hacker News 首页 675 分、209 条评论。大多数人讨论的是"要不要从 iTerm2 换过来"，但真正值得写的是发布说明之外的那句话：Ghostty GUI 只是 libghostty 的一个"豪华技术演示"。

## 一、终端为什么又变成了热点

过去两年，开发者工具的创新几乎都发生在"上层"：编辑器变成了 Agent 宿主，IDE 开始内嵌聊天面板，CLI 开始输出 JSON 给模型看。终端——这个看起来四十年没变过的部件——反而被当成了理所当然的基础设施。

但 2026 年的现实是：**Agent 的主要工作界面仍然是终端**。Claude Code、OpenCode、Codex CLI、各种"agentic terminal"（Herdr、cmux），本质都是"把一个 PTY 会话包装成可编程对象"。当 Agent 要在一秒钟内读取几万行构建日志、要在滚动缓冲区里搜索上一次失败的堆栈、要判断某个进程是"卡住了"还是"还在跑"，终端模拟器的内核质量就直接变成了 Agent 的产品质量。

这就是 Ghostty 1.4 的语境。它不是一次普通的版本更新，而是这个项目从"一个终端应用"转向"一个终端内核"的转折点。发布数据本身就很能说明问题：

| 指标 | 数值 |
|------|------|
| 开发周期 | 7 个月 |
| 贡献者 | 172 人 |
| 提交数 | 2,889 |
| GitHub Stars | 约 62.7k（2026-10-27） |
| 历史贡献者 | 422 人 |
| 安全公告 | 10 个 GHSA（含 3 个影响 1.3.0/1.3.1） |

值得注意的是那 10 个安全公告。它们大多不是"用户做错了什么"，而是"只要显示恶意输出就可能中招"：Kitty 图形命令可以强制巨量分配、越界读写临时目录；tmux control mode 的畸形布局可以让所有窗口崩溃；甚至 `cd` 进一个名字精心构造的目录，zsh shell integration 就会替你发送 OSC 52 改写剪贴板。**在一个 Agent 会主动 `git clone` 陌生仓库、自动 `cat` 未知文件的世界里，这些不是边角料漏洞，而是主攻击面。**

## 二、1.4 的性能账：一次"发现内核限制"的优化

Ghostty 官方给出的性能数字相当密集，但真正有意思的不是数字，而是数字背后的因果链。

### 2.1 pty 的 1 KiB 诅咒

Ghostty 团队在剖析 macOS 上的吞吐瓶颈时发现了一件反直觉的事：**内核会把每次从 pty 读取的数据量硬性截断在约 1 KiB，无论你给的读缓冲区有多大。**

这意味着旧的架构有一个结构性缺陷：读一次 → 解析一次 → 再读一次。每 1 KiB 就要付一次 per-read 开销，而写端（比如 `cargo build` 或 `cat` 一个大文件）会因为终端在解析而阻塞。终端的"快"，被一个看不见的内核常量锁死了。

1.4 的解法是把职责拆开：**一个线程专门把 pty 抽干（drain），另一个线程专门解析。** 这不是什么高深算法，但它把"读"和"算"解耦，写端不再等待解析。结果是 macOS（M4 Max）上端到端 I/O 吞吐提升 25%–55%。

这个案例值得所有做 I/O 密集型工具的团队记一笔：**当你的性能曲线在某个点上突然变平，先怀疑上游有一个你没意识到的批次上限，而不是先优化自己的循环。**

### 2.2 VT 解析：ASCII 5.7 倍，CJK 3.4 倍

VT 解析器的基准数据：

| 场景 | 1.3.x | 1.4 | 提升 |
|------|-------|-----|------|
| 纯 ASCII 解析 | 128 MB/s | 725 MB/s | 5.7× |
| CJK 文本 | — | — | 3.4× |
| asciinema 真实录像（2.6 GB） | — | — | 约 1.25× |
| `cat` 150 MB 文件（macOS） | 1.5 s | 566 ms | 2.65× |
| OSC 52 剪贴板负载解析 | — | — | 30× |
| 短 OSC（如改标题） | — | — | 6× |

注意最后两行。OSC 序列的解析提速来自"批量处理 + 避免逐字节状态机"的改造，这类优化对大 payload 是数量级的。对 Agent 场景尤其重要：Agent 经常一次性把整份文件、整段 JSON、整块 base64 图片塞进终端，OSC 52 和 Kitty graphics 的 payload 解析速度直接决定了"贴一张截图要等多久"。

配套的还有一组"周边"优化，容易被忽略但很能体现工程量：

- **Resize 快 6 倍**（120×80、1 万行 scrollback），CJK/emoji 历史下快 3–5 倍；
- **渲染持锁时间减少 2.7–11 倍**，重输出时给 I/O 线程让路；
- **复制/搜索快 1.5–8 倍**（纯文本、HTML、VT 三种格式化路径）；
- **macOS 启动快 15%，首帧快 27%**；
- **空闲能耗**：display link 在无事可画时睡眠。

这些数字单看都不惊人，但它们共同指向一个工程判断：**终端的"手感"不是某一个指标，而是十几次小延迟的叠加。** 1.4 做的是把这些叠加项逐个削掉。

### 2.3 内存：scrollback 压缩与 GPU 资源回收

1.4 最"产品化"的一项改动是 **scrollback 透明压缩**：

- 对典型文本历史，物理内存下降 **70%–90%**；
- 只在终端空闲时压缩，滚动/搜索时按需解压，官方称对 I/O 吞吐无可测影响；
- 因此默认 scrollback 上限从 **10 MB 提升到 50 MB**——即使塞满，内存通常还比旧版的 10 MB 更少；
- 仅 macOS 与 64 位 Linux 可用，可通过 `scrollback-compression` 关闭。

还有两个细节很能说明"内存卫生"的差距：

1. 空终端页内存从 **128 KiB 降到 16 KiB**（macOS）；
2. **隐藏标签页释放 GPU 资源**：1 个可见 + 20 个隐藏标签，GPU 内存从约 **385 MiB 降到 18 MiB**，重新可见时重建耗时不到 1 毫秒。

第 2 点对 Agent 工作流是实打实的：一个 Agent 常常开十几个 tab 跑并行任务，旧架构下每个 tab 都攥着 GPU 纹理不放。18 MiB vs 385 MiB，差的不是"优雅"，是"能不能在这台机器上再跑一个本地模型"。

### 2.4 Linux 的渲染管线重写

GTK 端这次把 `GtkGLArea` 整个换掉了：渲染器在自己的线程上用 EGL 绘制，每帧导出为 DMABUF 交给 GTK 显示，三缓冲，主线程不再有 OpenGL 调用。

最直观的收益是**分数缩放下文字不再模糊**（125%、150% 缩放）。这个问题修过一次又因为上游 GTK 变更复发，这次的解法是"按窗口真实分数缩放渲染，让每个渲染像素精确映射到一个屏幕像素"。同时带来一个部署代价：需要系统 EGL 库，老驱动只能走 CPU 拷贝回退。

## 三、libghostty：这才是真正的产品

如果只读官方 release notes，你会以为 1.4 是一个终端应用的更新。但 Mitchell Hashimoto 在 HN 评论区亲自补上了另一半——而且说得很直白：

> "Ghostty GUI 只是一个被 glorify 了的技术演示（对 libghostty 而言）。"

### 3.1 一个可嵌入的终端内核

libghostty-vt 是一个 C 库，从 Ghostty 中抽出的终端模拟核心：转义序列解析、终端状态维护、输入事件编码、scrollback、换行、resize 时的 reflow。API 按职责分组，覆盖面相当完整：

- **Terminal / Render State**：完整终端状态与增量渲染状态更新（给自定义渲染器用）；
- **Formatter**：把终端内容格式化为纯文本、VT 序列或 HTML；
- **Snapshot**：编码与增量恢复终端状态；
- **Search**：包括 scrollback 在内的内容搜索；
- **OSC / SGR Parser**、**Paste**、**Unicode Utilities**；
- **Key / Mouse / Focus Encoding**；
- **Byte-stream I/O**、**自定义 allocator**、**WebAssembly 工具**。

对做 Agent 工具链的人来说，`Formatter` + `Snapshot` + `Search` 这三个 API 几乎就是"给模型看的终端"所需的全部：把屏幕内容格式化成模型友好的文本、把会话状态快照下来做断点续跑、在几万行 scrollback 里精确检索。

### 3.2 跨平台矩阵与真实采用

官方给出的 libghostty 近半年进展，密度高得不像一个副项目：

- 对 Ghostty 核心的覆盖接近 **100%**，且可用编译开关裁剪功能以减小体积/攻击面；
- CI 覆盖 **Apple（macOS/iOS/visionOS）、Windows（MSVC 与 GNU）、Linux、FreeBSD、Android、WebAssembly，以及 freestanding（无操作系统，直接跑在硬件上）**；
- 绑定覆盖 C、Zig、Go、Swift、Python、Rust、.NET 等主流语言；
- 空终端内存占用再降 **90%**；在 4 核 8 GB 的 Linux 服务器上验证过 **10,000 个活跃终端**同时收发；
- **驱动 JetBrains 全系 IDE 的终端，覆盖 1,250 万活跃用户**；
- 是 Herdr、cmux 等一批"agentic terminal / editor"的共同内核；
- 正在被讨论替换 Neovim 的 `libvterm`（PR #39773，2026-05-13 开，仍在进行）；
- 支撑 Emacs 的 Ghostel；被 Antithesis 用来对终端程序做模糊测试，反向给 tmux、btop、各类 shell 提交了数百个修复。

最后一条尤其值得玩味：**一个终端内核的测试能力，反过来变成了整个终端生态的 bug 发现器。** 这是"基础设施"才有的杠杆效应。

Mitchell 还给出了明确路线图：**未来几个月内给 libghostty 打 1.0 标签，并声明 ABI 稳定。**

### 3.3 为什么"把终端做成库"是对的

终端模拟器长期是一个"应用品类"，而不是"基础设施品类"。每个 GUI 终端——iTerm2、Kitty、WezTerm、Alacritty、Windows Terminal——都自带一套 VT 解析器，各自实现一遍 xterm 兼容性的边角，各自踩一遍同样的坑。

libghostty 的赌注是：**VT 解析应该是 libc 级别的共享组件，而不是每个应用的私产。** 一旦这个判断成立，收益是复利的：

1. 应用层不用再为"兼容性"付费，可以专注渲染、键位、工作流；
2. 内核层因为被大量下游使用，获得远超单应用的测试覆盖与模糊测试压力；
3. 新的终端形态（IDE 内嵌、浏览器、Agent 沙箱、嵌入式设备）可以直接复用，而不必从零写一个"够用的 VT"。

JetBrains 的 1,250 万用户就是这条路线的第一个大样本：IDE 团队不需要自己维护终端内核，Ghostty 也不需要自己去抢 IDE 的市场。**这是一种"上游化"的战略，而不是"替代品"的战略。**

## 四、协议层：Ghostty 第一次"补齐"了 Kitty 的图形栈

要理解 1.4 的意义，得先理解 Kitty graphics protocol 在今天的地位：它已经事实性地成为"终端里显示图片"的标准，`kitten icat`、`chafa`、部分 TUI 文件管理器、甚至一些 AI 工具的输出预览都依赖它。

Ghostty 在 1.4 里做完了最后两块拼图：**动画（animation）** 与 **相对放置（relative placements）**。加上此前的静态图像、传输、裁剪、删除，Ghostty 现在声称覆盖了 **100% 的已发布规范**——是 Kitty 本体之外第一个做到的终端（同时也是 libghostty 的能力）。

这不是"多支持两个命令"的问题，真正的工作量在一致性上。官方提到的几个例子：

- 图像现在会随 `CSI S` / `CSI T` / 滚动区域一起移动并被裁剪（#4323）；
- 重传一个已存在的 image ID 会替换旧图并清除旧放置（#6711），失败的续传不再留下残影；
- 无效图像数据现在返回错误响应而不是静默——**此前客户端会一直挂着等**（#13889 等）；
- 删除命令的语义（`d=p`、`d=c`、`d=a`、空 range）与 Kitty 对齐；
- 高图之后的 cursor 移动与 Kitty 一致，连续图片不再重叠；
- 被 CAN/SUB 取消的 OSC/APC 序列直接丢弃，不再执行。

配套的性能改进是 **SIMD 批量解析**：64 MiB 图像数据在 x86_64 Linux 上解析快约 **16 倍**。

### 4.1 Kitty clipboard protocol（OSC 5522）

1.3 只能"解析但忽略" OSC 5522，1.4 真正实现了它。区别很关键：

| 能力 | OSC 52 | OSC 5522 |
|------|--------|----------|
| 读/写纯文本 | ✅ | ✅ |
| 读/写图片、HTML 等任意格式 | ❌ | ✅ |
| 让程序选择剪贴板中的特定格式 | ❌ | ✅ |
| 告知程序 paste 中包含哪些格式（mode 5522） | ❌ | ✅ |

最后一行是"终端里粘贴一张图"的关键：程序需要知道剪贴板里有没有 `image/png`，才能决定是接收图片还是当文本处理。

安全上，Ghostty 保持了保守默认：**读默认需要确认（带内容预览，包括图片）**，写默认允许；新增 `clipboard-write-limit-bytes`（默认 64 MiB），超限的写入直接失败且不改动剪贴板。程序若携带 password，用户的授权可在该终端会话内记住。

这个设计值得借鉴的地方是：**它把"权限"做成了会话级的、可见的、可预览的**，而不是一个全局开关。对 Agent 场景，这几乎是必须的——你不能让一个跑了 `curl | bash` 的进程悄悄读走用户剪贴板里的密码。

### 4.2 `ghostty +ssh`：把 shell integration 收敛成一个 CLI

1.2 引入的 SSH shell integration 是"实验性、每个 shell 各写一份"的状态，官方说这部分逻辑占了 shell integration 脚本的约三分之一。1.4 把它收敛成一个 drop-in 包装器：

```bash
# 直接用
ghostty +ssh user@example.com

# 或者让所有 ssh 都走它
alias ssh='ghostty +ssh --'
```

它在连接前做三件事：

1. 把 Ghostty 自带的 terminfo 安装到远端（这样 `TERM=xterm-ghostty` 才有意义）；
2. 转发 `COLORTERM`、`TERM_PROGRAM`、`TERM_PROGRAM_VERSION`；
3. 转发用户原本的 ssh 参数，一个不改。

失败回退策略也很务实：远端没有 `tic` 就退回 `TERM=xterm-256color`；`--terminfo=false`、`--forward-env=false`、`--verbose` 分别控制每一步。

工程细节上还有几处"踩过坑才会做"的修正：

- 始终安装**自己捆绑的** terminfo，而不是接受远端已有的 `xterm-ghostty` 条目；
- Ghostty 升级导致 terminfo 变化时**自动重装**；
- 本地不再需要 `infocmp` 或本地 terminfo；
- 缓存按 **host + port** 区分（同一地址后面的两台机器不再共享缓存）；
- `ssh-env` 不再静默覆盖 `~/.ssh/config` 里的 `SetEnv`（#11518）。

**为什么这件事重要？** 因为"终端能力协商"是远程开发体验里最容易被忽视的一环。TERM 不对，颜色、光标形状、下划线样式、truecolor、甚至 bracketed paste 全部降级；而这些降级在 Agent 场景下会变成实际的错误——比如 bracketed paste 失效导致多行命令被逐行执行。

## 五、Agent 时代的终端：OSC 7501 是个信号

1.4 的 changelog 里藏着一行不起眼但意味深长的记录：

> `vt`: 解析新的 **program status protocol（OSC 7501）**，让程序报告自己是 idle、working、done、blocked 还是 failed。**这是 Ghostty 项目开创的第一个终端规范。**

把它和另外两条放在一起看：

- 解析（但未实现）Kitty 桌面通知协议（OSC 99）；
- 解析（但未实现）Kitty 拖放协议（OSC 72）；
- 新增 **visibility reports**（mode 2033），让程序可以询问"终端当前是否可见"，从而在隐藏时停止渲染。

这三件事指向同一个方向：**终端正在从"被动显示字节流的设备"变成"可查询、可协商、可编排的运行时"。**

为什么 Agent 需要 OSC 7501？因为目前所有 agent harness 判断"任务是否结束"的办法都很脏：

- 抓 prompt 字符串（`$ `、`❯`）——换个主题就崩；
- 等固定超时——慢命令误杀，快命令空等；
- 解析 shell 的 `PROMPT_COMMAND` 钩子——跨 shell 不通用；
- 读进程退出码——只对直接子进程有效，管不到 tmux、ssh、docker exec。

一个标准化的"程序状态"通道，意味着终端可以向上层（IDE、Agent、窗口管理器）报告：这个 pane 在跑、卡住了、还是失败了。**这是把"终端里的黑盒"变成"有状态机的对象"的第一步。** Ghostty 现在只是"能解析"，GUI 还没用起来，但规范先立住了——这恰恰是基础设施项目的典型节奏：先让协议存在，再让生态跟上。

同类的还有 `DECXCPR`（扩展光标位置报告）、`DECSTR`（软复位）、`CSI 19 t`（字符单位屏幕尺寸）、`DECBKM`，以及把 `esctest`（Thomas Dickey 的终端一致性测试套件）接进 CI。这些都是"可编程终端"的地基。

### 5.1 安全：Agent 把终端变成了不可信输入的显示器

回到那 10 个 GHSA。它们的共同结构是：**攻击者只需要让受害者"看到"输出。**

- Kitty graphics 命令 → 崩溃、挂起、强制巨量分配、越界访问临时目录外的文件；
- 恶意输出经 tmux control mode → 崩溃并关闭所有窗口（**不需要安装 tmux**）；
- 清屏进 scrollback → 在小 scrollback-limit 下破坏内存；
- 构造的目录名 → zsh integration 发送任意转义序列（如静默改写剪贴板）；
- macOS 上 Cmd+点击构造的 OSC 8 链接 → 打开不安全本地文件或自定义 URL scheme，进而任意命令执行。

对传统用户，这些需要"手贱点一下"。对 Agent，**它们是日常工作流**：clone 一个仓库、`ls` 一个目录、`cat` 一个 README、点开日志里的链接。终端的输入信任边界，从"用户自己敲的命令"扩大到了"模型决定要看的任何东西"。

Ghostty 的应对是把危险序列默认关掉，需要显式开启：

```ini
# 允许程序调整窗口大小（CSI 8 t）——可能被远端程序滥用
vt-window-resize-allowed = true

# 允许程序请求终端重新执行……（默认关闭）
```

这个"默认拒绝 + 显式开启"的姿态，比"默认允许 + 文档警告"更适合 Agent 时代。值得所有做 Agent 沙箱的团队抄作业：**终端是 Agent 的 TCB（可信计算基）的一部分，它的默认配置应该按"会显示敌意内容"来设计。**

## 六、代价：升级 1.4 会踩到的坑

一次 2,889 个提交的大版本，破坏性变更不会少。官方列的 "Breaking Changes" 里，有几条会直接咬到现有用户：

### 6.1 `copy-on-select` 语义重写

| 配置 | 1.3 含义 | 1.4 含义 |
|------|----------|----------|
| `none` | — | 不复制 |
| `primary` | — | 复制到 selection clipboard（Linux 中键粘贴） |
| `clipboard` | 同时写 selection 与系统剪贴板 | **只写系统剪贴板** |
| `both` | — | 两者都写 |

macOS 上的默认值从 `true` 改成了 **`none`**——选中文本不再自动复制，中键粘贴默认失效。官方给的迁移方案很明确：想要 1.3 行为就设 `copy-on-select = primary`；如果你原本写的是 `clipboard` 又依赖"两处都写"，改成 `both`。

这类变更的麻烦在于它**不会报错**：配置合法、启动正常，只是你某天发现"选中复制"不灵了。对靠 dotfiles 管理多台机器的人，这是典型的"沉默迁移成本"。

### 6.2 键盘绑定迁移

- macOS：`cmd+↑/↓` 从"滚到顶/底"改回 `jump_to_prompt`（对齐 Terminal.app）。要保留旧行为得显式 `keybind = cmd+arrow_up=scroll_to_top`。
- GTK：`ctrl+shift+page_up/down` 从"切 tab"改成"移动 tab"（对齐 Firefox / GNOME Terminal / VS Code）；`jump_to_prompt` 挪到 `ctrl+shift+↑/↓`——**这会让终端里运行的程序收不到这两个键**，需要时用 `unbind` 还回去。

键盘绑定是肌肉记忆，任何改动都会被感知为"变难用了"。但对跨平台一致性来说，这些对齐是必要的：Ghostty 的目标不是"和 1.3 一样"，而是"和用户的其它工具一样"。

### 6.3 平台门槛抬高

- **GTK 4.18 + libadwaita 1.7**（1.3 是 4.14 / 1.5）。官方明确点名：**Ubuntu 24.04 LTS 不满足要求**，只能用旧版 Ghostty 或 Flatpak。
- 渲染改走 EGL，需要可用的系统 EGL 实现；不能导出 DMABUF 的驱动回退到 CPU 拷贝（更慢但能跑）。
- 好消息：macOS 最低版本仍是 13（Ventura），虽然官方说未来会 drop。

**Ubuntu 24.04 这个点值得单独说。** 它是最主流的 LTS 之一，被排除意味着大量 CI 容器、开发机、云桌面无法直接装 1.4 的 deb。Ghostty 的选择是"跟 GTK/Adwaita 版本策略走，其余的交给 Flatpak"。这是一个明确的取舍：**要么维护一堆老版本兼容分支，要么让打包生态承担碎片化。** 他们选了后者。

### 6.4 社区真正在意的事

HN 那 209 条评论里，被反复提到但**不在** 1.4 功能列表里的需求，反而更能说明这个项目的处境：

- **Kitty 的 hints mode**（用键盘跳转/选择屏幕上的 URL、路径、哈希）——一条高赞评论直言这是"唯一阻止我从 Kitty 换过来"的功能；
- **tmux -CC 集成**——`tmux control mode` 在 VT 层已经解析了很多，但"仍未接到 GUI"；
- **`⌘+F` 后 `⌘+V` 不响应**这类交互细节；
- **"为什么不用 iTerm2"**——一位用户实测 M1 MacBook Pro 上"没感觉到明显差异"，并抱怨 `cmd+,` 打开的是默认文本编辑器而不是设置界面。

这些反馈揭示了一个残酷的事实：**性能数据说服的是工程师，日常手感说服的是用户。** Ghostty 在"内核质量"上已经明显领先，但在"十年积累的交互细节"上，它仍然是后来者。1.4 的 16 小时手写 release notes 体现了维护者的诚意，但 hints mode 这类功能的缺失，不是靠 release notes 能补的。

## 七、给工程团队的三条可操作结论

抛开"要不要换终端"，Ghostty 1.4 对做基础设施和 Agent 工具的团队有三条直接可用的经验。

### 7.1 把"共享内核"当成架构选项，而不是妥协

如果你在做的东西里有某个组件被多个产品重复实现（终端解析、LSP 客户端、diff 算法、语法高亮、沙箱执行），认真考虑把它抽成库。判断标准不是"能不能抽"，而是：

1. 这个组件的正确性是否依赖大量边角兼容性？（VT 转义序列就是典型）
2. 它的测试成本是否高于实现成本？（libghostty 被 Antithesis 拿去 fuzz，反过来修了 tmux/btop）
3. 是否有多种前端形态需要它？（GUI、IDE、Web、嵌入式）

三条都中的组件，做成库的长期收益远大于"少写一个抽象层"的短期收益。JetBrains 1,250 万用户用 libghostty，就是这个判断的验证。

### 7.2 性能优化先找"上游批次限制"

Ghostty 最大的吞吐提升不是来自更快的解析器，而是发现"macOS 内核把 pty 读截断在 1 KiB"。这提示了一条通用的排查路径：

- 测吞吐时，先测**单次系统调用的有效载荷**，而不是总耗时；
- 如果吞吐随缓冲区增大而不变，几乎一定有上游批次上限；
- 解法通常是"读写解耦 + 双缓冲/双线程"，而不是"把循环写得更紧"。

同理，`cat` 150 MB 从 1.5 s 到 566 ms，靠的是"批量 + 解耦"，不是"更聪明的状态机"。

### 7.3 Agent 的终端必须按"敌意输入"设计

给所有做 Agent 沙箱 / 云端 IDE / 远程开发的人：

- **终端输出是不可信输入。** 任何"显示即执行"的序列（OSC 52、OSC 8、Kitty graphics 文件传输、窗口 resize）都应该默认关闭或需确认；
- **剪贴板要会话级授权 + 内容预览**，不要全局开关；
- **paste protection 要覆盖所有路径**：键盘粘贴、拖放、中键、程序化写入。Ghostty 这轮修的 10 个 GHSA 里，至少 3 个是"某条路径绕过了 paste protection"；
- **给 Agent 一个状态通道。** 短期可以自己发 OSC 自定义序列（`OSC 1337` 之类），长期关注 OSC 7501 的落地——它能替掉大量"抓 prompt 字符串"的脏代码。

## 八、结语：终端的"内核化"

Ghostty 1.4 表面上是一个终端应用的版本更新：更快的解析、更省的内存、更完整的 Kitty 支持、更可靠的 SSH。这些都是真的，数据也扎实。

但把它放回 2026 年的语境里，真正的叙事是另一件事：**终端正在经历一次"内核化"。** 过去它是最上层、最不可编程、最被当作黑盒的应用；现在它正在被拆成协议（Kitty graphics、OSC 5522、OSC 7501）、被抽成库（libghostty）、被嵌进 IDE 和 Agent 宿主、被要求提供状态与可见性查询。

这个转向的原因很现实：**当 Agent 成为主要用户，终端就不再是给人看的窗口，而是机器要读写、要查询、要编排的接口。** 一个 40 年历史的抽象，突然需要满足一批它设计时不存在的要求——低延迟的大量 I/O、不可信输出的安全隔离、结构化状态报告、跨平台可嵌入。

Ghostty 的赌注是：这些要求应该由一个高质量的内核来满足，而不是每个应用各自糊一遍。1.4 是这条路线的中点——libghostty 还没有 1.0，ABI 还会变，OSC 7501 还没有 GUI 消费方，Neovim 的替换还在 PR 里。但方向已经很清楚了。

对使用者，结论简单：如果你在 Linux 上且发行版满足 GTK 4.18，1.4 值得升；如果你在 Ubuntu 24.04，先走 Flatpak；如果你在 macOS 且依赖"选中即复制"，升级前先改配置。

对建设者，结论更有价值：**下一个值得做成库的"老组件"，可能就藏在你的技术栈最底层。** 那些看起来"每家公司都自己写一遍、都写得差不多、都有一堆兼容性 bug"的东西，往往就是基础设施的机会所在。

---

**参考资料**

- Ghostty 1.4.0 Release Notes：https://ghostty.org/docs/install/release-notes/1-4-0
- libghostty-vt API 文档：https://libghostty.tip.ghostty.org/
- Hacker News 讨论（675 分 / 209 评论）：https://news.ycombinator.com/item?id=50261998
- Mitchell Hashimoto 关于 libghostty 进展的评论（同上讨论串）
- Neovim 替换 libvterm 的 PR：https://github.com/neovim/neovim/pull/39773
- Kitty graphics protocol：https://sw.kovidgoyal.net/kitty/graphics-protocol/
- Kitty clipboard protocol：https://sw.kovidgoyal.net/kitty/clipboard/
- Ghostty 安全公告：GHSA-4hwh-wx3w-3fqg、GHSA-mhff-mv4q-fp63、GHSA-hcr9-7hcr-mjm8 等 10 项
