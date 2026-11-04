# 当 Agent 学会读「结构」而不是看「像素」：Vercel agent-desktop 深度拆解

> 12,669 颗星、一个月 2.2 万次 npm 下载、v1.1.0 在 11 月 3 日刚刚发布。Vercel Labs 的 agent-desktop 想回答一个非常具体的问题：如果桌面 Agent 不截图、不做像素匹配、不猜坐标，它还能不能操作 Finder、Excel 和 Photoshop？
>
> 它的答案是：能，只要你愿意把「屏幕」换成「可访问性树」。

---

## 一、桌面 Agent 的真正瓶颈，从来不是模型

过去两年，桌面自动化（computer use）几乎被一种范式统治：截一张图，交给多模态模型，让它输出 `(x, y)` 坐标，然后点击；再截图，再判断。

这条路径在 Demo 里极其惊艳，在生产里极其脆弱。原因不神秘：

1. **分辨率与缩放的漂移**。同一个按钮在 100%、125%、150% 缩放下坐标不同；外接显示器换了、窗口最大化了、系统更新了字体，坐标全废。
2. **视觉理解的不可靠性**。模型看到的是「一个蓝色按钮」，但它未必知道你点的是「保存」还是「另存为」；同类图标在不同应用里含义不同。
3. **Token 成本与延迟**。一张 1920×1080 的截图，即使压缩到 1280 宽，视觉 token 也在千级；一个需要 20 步的任务，仅观测就要烧掉数万 token，且每步都要等一次 VLM 推理。
4. **无法验证**。点完之后，除了「再截一张图看看」，你没有别的证据证明动作生效了。

这四点合起来，构成了桌面 Agent 的可靠性天花板。模型再强，也只是在为一个信息质量很差的观测接口做补救。

agent-desktop 的切入点因此显得很「工程」：**它不猜，它去问操作系统。**

---

## 二、agent-desktop 是什么：一个没有模型的「手和眼」

用一句话概括：**agent-desktop 是一套把桌面应用的可访问性树（accessibility tree）暴露成 JSON 的 CLI 与 C 库，Agent 通过 ref 精确操作元素。**

它有几个值得注意的定位选择：

- **它不是 Agent**。仓库里没有模型、没有 prompt、没有规划器。README 写得很直白："The loop lives in your agent; agent-desktop has no model inside." 它只负责观测与执行。
- **它是一套原语，不是一个框架**。60 个命令名、56 个可执行命令，覆盖观察、点击、输入、键盘鼠标、窗口管理、通知、剪贴板、等待、会话与追踪。
- **它是 Rust 写的本地二进制**，通过 npm 分发（含 x64/ARM64 原生包），同时提供 `libagent_desktop_ffi` 这个 C ABI，让 Python、Go、C++ 甚至一个 Rust Agent 直接进程内调用，省掉每次 spawn 进程的开销。
- **它同时是 MCP Server**。`agent-desktop mcp` 把每条命令映射成一个 MCP 工具（`desktop_snapshot`、`desktop_click`、`desktop_session_start`），任何支持 MCP 的宿主都能直接接入。

发布时间线也值得记一笔：仓库 2026 年 2 月创建，11 月 3 日发布 v1.1.0，一个月 npm 下载 22,652 次，Apache-2.0。它不是实验室玩具，而是已经在被集成的基础设施。

---

## 三、架构：一个 trait，三套操作系统方言

agent-desktop 的架构图非常克制，只有四层：

```
Agent (CLI / MCP / FFI)
        ↓
   agent-desktop-core
        ↓
   PlatformAdapter (trait)
        ↓
macOS AX ／ Windows UIA ／ Linux AT-SPI
```

关键在第三层。`PlatformAdapter` 是一个 Rust trait，把「读树、找元素、执行动作、读窗口状态」抽象成统一接口；三个平台各自实现：

| 平台 | 系统 API | 最低要求 |
|---|---|---|
| macOS | AX API（Accessibility） | macOS 13+，Intel/Apple Silicon |
| Windows | UI Automation | Windows 10 1809+，x64/ARM64 |
| Linux | AT-SPI | Ubuntu 24.04+，X11 或 Wayland |

这里有一个容易被忽略的工程决策：**每个二进制在编译期就绑定一个平台**，不是运行时动态适配。这意味着发布产物是「macOS 版」「Windows 版」「Linux 版」，各自只链接自己那套系统框架。代价是不能跨平台交叉操作，收益是二进制更小、依赖更少、行为更可预测——对一个要被 Agent 反复调用的 CLI 来说，这是正确的取舍。

同一套 core 同时服务 CLI 和 C 库，保证两条路径的行为一致：CLI 打印的 JSON envelope，和 FFI 返回的结构体，语义上是同一份契约（当前契约版本 2.6）。

---

## 四、核心抽象：ref 不是选择器，是「带代际的句柄」

这是整篇文章最值得细看的部分。

一次 `snapshot` 返回的树里，每个可交互节点带一个 `ref_id`，形如：

```
@s8f3k2p9:e8
```

前半段是 `snapshot_id`，后半段是这次快照内的元素编号。**裸的 `@e8` 会被直接拒绝**，返回 `INVALID_ARGS`：

```json
{
  "version": "2.6",
  "ok": false,
  "command": "click",
  "error": {
    "code": "INVALID_ARGS",
    "message": "Invalid ref_id '@e1': expected @<snapshot_id>:e<N>",
    "disposition": { "delivery": "not_delivered", "retry": "safe" }
  }
}
```

为什么要强制带快照 ID？因为这解决了一个分布式系统里的经典问题：**陈旧引用**。

UI 是会变的。你 snapshot 之后，列表刷新了、弹窗关了、按钮从第三行挪到第五行。如果你只用「第 8 个元素」这种位置索引，动作就会打到错误的元素上——而且是静默打错，这比报错可怕得多。

agent-desktop 的做法是把 ref 变成一次观测的「代际句柄」：

- 快照内的元素被重新编号，旧 ref 天然失效；
- 动作时如果 UI 已变化，返回 `STALE_REF`；
- 如果目标不唯一（比如两个同名按钮），返回 `AMBIGUOUS_TARGET`；
- 两种情况都要求你**重新 snapshot，用新 ref 重试**。

这和数据库的乐观并发控制（OCC）是同一个思路：读的时候记下版本，写的时候校验版本，冲突就重读。区别只是这里的「版本」是快照 ID，「行锁」变成了「元素身份」。

v1.1.0 里还有一条更深的改进：在 macOS 上，**ref 会通过元素自身的 accessibility address 重新识别**；Linux 与 Windows 则通过一套 capture rule 解析。换句话说，ref 不只是「这次快照里的第 N 个节点」，它还携带了足以在树结构轻微变化后重新定位元素的身份信息。这显著降低了「刷新一下就得重来」的概率，但并没有取消版本校验——身份重识别是尽力而为，代际校验才是正确性保证。

这个设计值得所有做 Agent 工具的人抄一遍：**观测产物必须自带失效语义**，否则 Agent 永远不知道自己拿到的是不是过期世界。

---

## 五、快照预算：承认「看不全」比假装看得全更重要

可访问性树有一个现实问题：它可能非常大。一个打开的 VS Code 窗口、一个满是数据的 Excel，节点数轻松上万。全量序列化既慢又贵。

agent-desktop 没有假装自己能一次看完全世界，而是把「截断」变成协议的一部分：

- `data.complete`：这棵树是否完整；
- `data.truncated`：是否因为预算被截断；
- `data.nodes_observed`：实际观测到多少节点；
- 每个被截断的子树节点上带 `subtree_truncated: true`。

注意一个细节：**即使被截断，命令仍然返回 `ok: true`**。这是一个很成熟的设计判断——「部分成功」不应该被当成失败，否则 Agent 会陷入无限重试；但它必须被显式标注，否则 Agent 会以为世界就这么大。

对应到 Agent 侧，正确做法是分层观测：

1. 先 `snapshot -i` 只取可交互元素（`-i` 过滤掉纯装饰节点），把树压到可处理规模；
2. 目标不在其中时，用 `find --role button --name "保存"` 做定向搜索，而不是加大全量预算；
3. `find` 的返回还贴心地带了 `roles_present`——当 `--role` 匹配为空时，它会告诉你「这次搜索实际看到了哪些 role」，把「没找到」从黑箱变成一个可诊断的信号。

`find` 的三种返回形态也值得一提：默认返回 `matches/total_matches/truncated`；`--first/--last/--nth N` 返回单个 `match` 对象（无匹配时为 `null`）；`--count` 只返回数量。这是典型的 CLI 设计品味：让调用方用参数决定输出形态，而不是返回一个巨大的、需要二次解析的复合结构。

此外，节点还带 `native_id`（如 `{ "kind": "ax_identifier", "value": "undo_button" }`）、`states`（如 `["disabled"]`，或 `checked`、`expanded`）、`available_actions`。这些字段是把「视觉线索」翻译成「结构化事实」的关键：Agent 不需要猜按钮是不是灰的，它读到 `disabled` 就知道。

---

## 六、`ok: true` 不等于「事情发生了」：disposition 模型

如果只能从 agent-desktop 里学一个概念，我建议是这个：**动作结果与动作效果必须分开表达。**

每个 ref 动作（`click`、`type`、`toggle`…）返回一个 `disposition` 对象，两个字段：

```json
{ "delivery": "delivered_unverified", "retry": "unsafe" }
```

- `delivery`：`delivered_verified` / `delivered_unverified` / `not_delivered`（已满足）。
- `retry`：`safe` / `unsafe`。

这两个字段回答的是两个不同问题：**「输入送达了吗？」**和**「如果没送达，我能不能无副作用地重试？」**

为什么必须分开？考虑一个「提交订单」按钮：第一次点击可能已经触发了订单创建，但因为响应慢，你的观测没看到变化。如果此时你按「失败」重试，就会下两个单。而如果动作是「聚焦输入框」，重试一百次也没关系。

于是 agent-desktop 的规则是：

- **只有 `error.disposition.retry === "safe"` 才允许重试**；
- `ok: true` 只表示命令返回了已送达或已满足的结果，**不表示应用层面发生了效果**；
- 想确认效果，必须**重新观测**（observe → act → verify）。

这套语义对应了三态：已验证送达、已送达未验证、未送达但已满足。它比布尔值的 `success/failure` 多出来的信息量，恰好是 Agent 做决策所需要的。

我在很多 Agent 工具里看到的问题是：工具返回 `200 OK`，Agent 就认为任务完成。agent-desktop 明确把这个幻觉拆掉了——它在文档里有一句话说得非常狠：

> `ok: true` means the command returned a delivered or already-satisfied result. It does not mean the application effect happened.

这句话应该刻在每个做 Agent 工具的人桌上。

---

## 七、headless 与「交互租约」：不抢用户焦点的礼貌

默认情况下，agent-desktop 的动作是 **headless** 的：不移动指针、不抢焦点，直接向目标元素投递事件。只有加 `--headed` 才会模拟物理输入（真实移动鼠标、真实按键）。

这个设计解决了一个长期被忽视的体验问题：**Agent 在后台干活时，不该把你正在用的电脑抢走。**

但 headless 不是万能的。有些应用只认真实的焦点与指针事件：自绘控件、部分 Electron 应用、某些安全软件保护的窗口。对这些场景，`--headed` 是逃生舱。而某些命令（如 `key-down`/`key-up`/`mouse-down`/`mouse-up`）在 v1.1.0 里会拒绝执行，除非有一个守护进程能保证「按下的键一定会被释放」——这是防止 Agent 卡住一个 Shift 键导致整台机器不可用的保护。

v1.1.0 的 changelog 里还有一条小但重要的改动：「move the cursor before taking the interaction lease」。翻译过来是：先移动光标，再获取交互租约。这背后是一个真实存在的竞态——如果先拿租约再移动，中间这一小段时间里，另一个进程（或用户）也可能在操作鼠标，导致输入错位。把顺序反过来，就把「租约覆盖的范围」和「实际物理状态」对齐了。

这类细节不会出现在发布博客的标题里，但它们决定了一个自动化工具能不能被长期信任。

---

## 八、和截图方案算一笔账

把两种范式放在同一张表里，差异会非常清楚：

| 维度 | 截图 + 坐标 | 可访问性树 + ref |
|---|---|---|
| 观测单位 | 像素图像 | 结构化节点（role/name/value/state） |
| 定位方式 | 视觉模型猜坐标 | 元素 ref，带快照代际 |
| 分辨率/缩放敏感 | 高 | 无 |
| 语义信息 | 需模型推断 | 原生提供（disabled/checked/expanded） |
| 失效检测 | 只能靠再截图对比 | `STALE_REF` / `AMBIGUOUS_TARGET` |
| 单次观测成本 | 千级视觉 token | 数百到数千文本 token（可用 `-i` 压缩） |
| 动作可验证性 | 弱 | `disposition` + 再观测 |
| 覆盖盲区 | 无（凡可见皆可点） | 自绘 UI、Canvas、游戏、a11y 缺失的应用 |

成本这一项需要说清楚：**可访问性树不是无条件更便宜。** 一个信息密集的窗口，JSON 化后的 token 数可能超过一张压缩截图；但它的优势在于可裁剪（`-i`、`find`、`--limit`）和可缓存（同一快照内多次操作复用 ref，无需重复观测）。而截图方案的成本是刚性的：每一步都要一张新图，且无法用「只取可交互元素」这类手段压缩。

在 20 步以上的长任务里，这个差异会被放大成数量级的差距——不是因为单步便宜，而是因为**树观测可以增量**，像素观测只能全量。

真正的结论不是「树一定优于图」，而是：**优先用结构化观测，把视觉留作兜底。** agent-desktop 自己也提供了 `screenshot` 命令，正是为那些「树里没有」的场景准备的。

---

## 九、混合场景：Chromium 与 Electron 的正确打开方式

桌面 Agent 最常打交道的应用，其实是 Electron 套壳的 Web 应用（Slack、VS Code、Notion）。这类应用有一个尴尬之处：原生窗口的可访问性树往往只暴露一个巨大的 WebArea，里面是浏览器自己维护的另一套树。

agent-desktop 的方案是**分工**：

- 原生外壳（菜单栏、标题栏、系统对话框）交给 agent-desktop；
- 窗口内的 Web 内容，通过 agent-desktop 打开的 DevTools 端口，交给 agent-browser（同门的浏览器自动化工具）处理。

这个组合很务实。DevTools 协议能拿到比可访问性树更精确的 DOM 结构、更可靠的选择器、更完整的网络与运行时信息；而原生外壳只有操作系统自己知道。硬要用一套接口打通两者，只会做出一个什么都做不好的抽象。

这也解释了为什么 agent-desktop 的文档站挂在 `agent-browser.dev/desktop` 下——它们本来就是一套东西的两半：**Web 用 CDP，桌面用 AX/UIA/AT-SPI。**

---

## 十、安全：可访问性权限 = 一把万能钥匙

这是所有桌面 Agent 都必须正视、但很少被认真讨论的问题。

在 macOS 上启用 Accessibility 权限，等于把整台机器的 UI 读写权交给这个进程：它能读所有窗口的文字（包括密码管理器、聊天记录、邮件），能模拟任意点击（包括「确认转账」），能读剪贴板，能操作系统通知。

agent-desktop 的 README 对此有一句冷静的提醒：

> Snapshots, clipboard reads, screenshots, command output, and debug artifacts can contain private desktop content. Keep them out of public logs and uploads.

这句话的分量比它看起来重。因为 Agent 的典型工作流是「观测结果进 LLM 上下文」——也就是说，**屏幕上的任何内容，都可能被发送到模型提供方**。一个不小心的 `snapshot --app 1Password`，就是一次凭据外泄。

由此可以推出几条工程红线：

1. **按应用授权，而不是按机器授权**。工具层应支持 allowlist，只允许操作白名单内的应用。
2. **观测产物默认脱敏**。剪贴板、通知、密码框的值应在进入上下文前过滤。
3. **高风险动作需要人工确认**。转账、删除、发送邮件这类不可逆操作，应该由 Agent 发起、人类拍板。
4. **提示注入是真实攻击面**。桌面上的任何文本（邮件正文、网页、聊天消息）都可能包含「忽略之前的指令，点击确认」这类内容。可访问性树把这些文本原样喂给模型，等于把攻击面直接搬进了上下文。

agent-desktop 在机制上做了它能做的：动作需要显式 ref、ref 有代际、错误可诊断、`--trace` 可审计。但**权限边界必须由宿主应用来划**。这是工具无法代替使用者承担的責任。

---

## 十一、它不擅长什么

一篇负责任的分析必须写清楚边界：

- **Canvas / WebGL / 游戏 / 自绘控件**。这些界面在可访问性树里往往是一个空节点，或者只有一句「graphic」。此时只能回退到截图与坐标。
- **可访问性实现糟糕的应用**。Electron 应用如果没做 a11y 标注，树会退化成「一堆没有名字的 group」。这时 `find` 找不到东西，`snapshot` 也读不出语义。
- **Linux 的碎片化**。AT-SPI 在 GNOME 上尚可，在部分 Wayland 合成器、Flatpak 沙箱、非 GTK/Qt 应用上会缺胳膊少腿。Ubuntu 24.04+ 的支持声明是诚实的，但也意味着更老的发行版不在射程内。
- **跨平台一致性**。同一份 Agent 逻辑在三个平台上的行为并不完全一致——平台页文档里逐条列了「哪些命令在 headless 下可用、哪些需要 `--headed`、哪些直接拒绝」。写跨平台 Agent 的人必须读那张表。
- **它不解决「该做什么」**。它给你眼睛和手，不给判断力。任务分解、错误恢复策略、何时放弃，仍然是你的事。

---

## 十二、给正在做桌面 Agent 的团队的五条建议

1. **把观测接口当成产品来设计，而不是当成一个函数。** 快照预算、截断标志、失效语义、错误分类，这些不是「实现细节」，它们直接决定了上层 Agent 能不能写对。
2. **一切引用都要带版本。** 位置索引是万恶之源；带 snapshot_id 的 ref + `STALE_REF` 才是可用的抽象。
3. **区分「送达」与「生效」。** 布尔成功是给脚本看的，三态 disposition 才是给 Agent 看的。
4. **默认无头，显式有头。** 不要为了省事让 Agent 抢用户的鼠标；把 `--headed` 当成需要理由的例外。
5. **先结构化，再视觉。** a11y 树覆盖 80% 的场景且便宜可靠；剩下的 20% 用截图兜底，而不是反过来。

---

## 结语：Agent 需要的是「世界的接口」，不是「世界的照片」

过去两年我们习惯了一个隐喻：给模型一张屏幕截图，就像给人一双眼睛。

但眼睛只是开始。人类之所以能熟练操作电脑，不是因为我们能看见像素，而是因为我们知道「那是一个按钮」「它现在是禁用的」「点它会导致提交」。这些是**结构化的世界知识**，不是图像特征。

agent-desktop 的价值，不在于它比 GPT-5 更聪明，而在于它把这句话落到了工程上：**让 Agent 读到结构，而不是猜测像素。**

12,669 颗星和一个月 2.2 万次下载说明，很多人已经意识到这条路更接近生产。而 v1.1.0 里那些看起来琐碎的修复——光标顺序、按键释放保护、ref 身份重识别——才是这类基础设施真正的护城河：不是功能列表，而是**在真实世界的混乱里依然可预测**。

下一次当你看到某个 Agent 演示「自动帮你订机票」时，不妨问一句：它是靠看截图猜坐标，还是靠读结构拿句柄？

这个问题的答案，基本决定了它能不能活过 Demo。

---

**参考与延伸**

- 仓库：`vercel-labs/agent-desktop`（Apache-2.0，v1.1.0，2026-11-03）
- 文档：`agent-browser.dev/desktop`（JSON 契约 2.6、错误与恢复、平台能力表）
- 同门工具：`agent-browser`（Web 侧，基于 DevTools 协议）
- 相关文章：本仓库《当一个浏览器决定不再画画：Lightpanda 1.0 深度拆解》
