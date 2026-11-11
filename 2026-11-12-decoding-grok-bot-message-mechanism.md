# 解码 Grok Bot：消息机制

> 原文：Wei Su，《Decoding Grok Bot - The Message Mechanism》，weisu.io，原页面未标注发布日期。
>
> 本文为全文翻译，未做删节。分节标题、表格、代码块与链接均对应原文；代码与提示词片段一字未改。

本文回答三个问题：

* 为什么 Grok Bot 能连发好几个独立气泡，而不是一次回复一大段？
* 为什么文件永远是一张独立的卡片，从不混进正文？
* 这是系统提示词约束出来的，还是别的什么东西？

---

## 一句话版本

**Grok Bot 并没有用系统提示词去约束模型的文本格式，而是把"给用户发消息"变成了一次工具调用，工具名叫 `SendMessage`。**

三个设计决策由此而来：

1. **模型平时输出的文本永远不会展示给用户**——它被当作内部思考，要么丢弃，要么只记在内部。
2. **每一个用户可见的气泡都是一次 `SendMessage` 工具调用**——几条消息就是几次调用，所以它们天然是分开的。
3. **气泡类型由工具的 `type` 枚举决定**——文本、文件、交互控件、凭据请求各有各的类型。渲染器按类型分支，于是"文件混进正文"在结构上就不可能发生。

通常的做法正好相反。不是界面从模型的散文里解析结构，而是**模型通过一个带类型的 API 去操作界面——聊天界面是模型往里写入的输出设备，而不是一个反过来解读它的渲染器。**

---

## 工具是怎么定义的

### 工具说明

这个工具自带一段说明，随工具一起给到模型：

```
## Communicating with the user

The `SendMessage` tool is your only user-visible communication channel.
Regular assistant text is treated as internal thinking and is not shown
to the user.

Use `SendMessage` for:
- meaningful progress updates;
- questions or blockers requiring user input when the Ask Question tool
  is not appropriate;
- the final result of your work.

After a progress message, continue working normally. After sending your
final message, stop without repeating it. A successful tool result means
the message was delivered.
```

几点值得注意：

* 第一句就把 `SendMessage` 声明为**唯一**的用户可见通道。
* 它把节奏写死了：进度更新 → 继续干活 → 最终结果 → 停。这就是我们观察到的那个节律的来源：「好的，我去查一下……」（第一次调用）→ 工具执行 → 「查完了……」（第二次调用）。
* 这段说明是**按条件注入**的：只有在 `options.sendMessageEnabled === true` 时才追加，也就是说工具是否暴露、提示词文本是否出现，共用同一个开关。

### 参数 schema（Zod）

```js
// the tool's parameter schema, in outline
type:    one of  text | attachment | widget | cursor-agent | secret-request
content: string, required when type is text
         "The message to show to the user."
url:     string, required when type is attachment
         "Use file:// for local files or https:// for remote files and standalone media."
images:  array of { url, alt? }, optional
         "file:// or https:// URL of the image."
         alt: "Optional short description of this image, shown on hover
               and as its fullscreen caption."

// plus a cross-field validation pass that rejects mismatched combinations
```

`type` 字段自己的描述是这样写的：

> *"text 用于聊天消息，**attachment 用于真正的文件或独立媒体**，widget 用于带可选项的交互式提问，cursor-agent 用 bcId 引用一个 Cursor 云端 Agent（渲染成一张卡片，点击就在 Cursor 里打开该 Agent），secret-request 通过安全掩码输入向用户索取凭据（绝不通过聊天粘贴）。"*

### 状态闸门

```
This turn is already waiting on the user (you sent a question widget or
handed the box back to them), so this message was not delivered. Wait for
the user — their response arrives as the next message — then say this on
your next turn.
```

如果模型已经发过一个 widget（正在等用户选择），或者已经把沙箱控制权交回给用户，那么之后的 `SendMessage` 调用会**在运行时被拒绝**，并把上面这段文字返回给模型，让它自己纠正。这是一个纯代码层面的会话状态机，跟提示词无关。

---

## 五种气泡类型

| `type`           | 必填字段                        | 客户端渲染                                                             | 典型用途                                                  |
| ---------------- | ------------------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------- |
| `text`           | `content`                       | 普通文本气泡（react-markdown + KaTeX + Mermaid + highlight.js）        | 进度更新、结论                                            |
| `attachment`     | `url`（`file://` 或 `https://`）| 文件卡片（图标、文件名、大小、下载按钮）                               | Agent 产出的 PDF、Markdown、表格                          |
| `widget`         | 选项列表                        | 交互式提问控件                                                         | 需要用户做决定时                                          |
| `cursor-agent`   | `bcId`                          | Cursor 云端 Agent 卡片，点击在 Cursor 中打开                            | 跨产品交接                                                |
| `secret-request` | —                               | 掩码安全输入                                                           | API key 与密码，明确要求绝不粘贴进聊天                    |

另外还有一个独立的 `images` 数组：一次调用可以带多张图（`url` 加可选的 `alt`），以网格形式渲染，alt 文本用于悬停提示和全屏看图时的图注。

### 附件是怎么落地的

当 `type: "attachment"` 且 `url` 是一个 `file://` 路径（Agent 在云沙箱里生成的文件）时，宿主进程这样解析附件来源：

1. 解析本地/沙箱路径，读取文件。
2. 通过 attachments-service 把它收进每个 Agent 各自的附件目录（`<agentDir>/attachments`），以 SHA-256 做内容寻址。
3. 产出一条会话记录；渲染器按附件类型生成卡片并支持本地预览——PDF 用 pdfjs-dist，Word 用 mammoth，Excel 用 xlsx，全部在客户端解析。

换句话说，**文件本身走文件系统，聊天消息里只带一个引用**。这跟上传播径是同一套基础设施，只是反过来跑（上传是 渲染器 → IPC → 主进程暂存 → gRPC 的 `StageFiles`/`SyncFile` 分块同步进云沙箱）。

---

## 三层控制

这个机制的可靠性来自三层共同作用，而不是其中任何单独一层。

### 第 1 层：协议（硬约束）

一个 Zod schema 加上 `superRefine` 交叉校验，**在工具调用边界**上强制结构：

* `type: "text"` 必须带 `content`。
* `type: "attachment"` 必须带一个 scheme 合法的 `url`（校验报错原文是*"https:// scheme when type is attachment"*）。
* 任何枚举外的 `type` 会被直接拒绝——代码里有穷尽性检查。

校验失败会返回错误，模型在下一步重试。**坏输出在协议层就被弹回去，永远到不了 UI。**

### 第 2 层：提示词（软引导）

这段说明教模型三件事：

* 什么时候发（进度、阻塞、结果）；
* 节奏怎么走（发完进度继续干活，发完最终结果就停，不要重复）；
* 语义上怎么分（文件走 attachment，提问优先用专门的 Ask Question 工具）。

所以提示词**确实参与**，但它管的是*什么时候发、说什么*，而不是*怎么把文件和文本分开*。后者由 schema 负责。

> **注：这段说明并不在系统提示词里。** 它被包在 `<system_reminder>` 标签中，追加在**每一轮用户消息**的末尾（以 `user` 角色），并且当模型连续六次没有调用 `SendMessage` 时，运行时中间件会**再注入额外的提醒**。
> 整套机制——注入点、角色选择、以及为什么它完全不出现在 UI 上——本身就是一个独立话题。

### 第 3 层：运行时状态机与行为纠偏

宿主进程跟踪会话状态（是在等用户，还是在干活）。发得不是时候的调用会在代码里被拦截，并返回一段可读的错误，告诉模型等下一轮再说。

反方向也有兜底。一个提醒中间件会数一数自上次 `SendMessage` 以来发生了多少次其他工具调用，一旦超过阈值（默认 6），就注入一条提醒，推动模型汇报进度。那条提醒的措辞——*"make a real tool/function call, **not text you write**"*——读起来像一块补丁：只在提示词里声明"你写的文本是不可见的"还不够，因为模型仍然会时不时写出本来给用户看的文字。只有运行时检测才抓得住。

功能开关则单独控制呈现。其中一个开关管 Project 会话里的卡片式气泡，它的注释写得很明确：*"Presentation only — tool exposure and transcript normalization stay on when this is off."*

---

## 与替代方案对比

| 方案                 | 怎么做                                                                                   | 弱点                                                                                                       | Grok Bot 的选择                                                                        |
| ------------------------ | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 系统提示词约定 | 模型在一次回复里穿插分隔符或标记；前端用正则切开 | 格式一旦漂移渲染就坏；文件只能以链接文本存在；交互控件根本做不了  | 未采用                                                                               |
| 一次性结构化载荷   | 模型输出一个包含所有气泡的大 JSON                              | 没法逐个气泡流式输出；中途一个错误就全废；"边干边报"不可能 | 未采用                                                                               |
| **消息即工具调用** | 一条消息一次工具调用，经 schema 校验、受状态机闸门管束                         | 多花一些回合和工具调用配额                                                                      | ✔ 采用，换来类型安全、流式输出、可交互、错误可重试 |

对一个长时间运行的桌面 Agent 来说，多几次工具调用的成本几乎可以忽略，而收益是实打实的：

* **天然的多气泡节奏**——进度气泡能插在干活过程中间，与工具执行交错。
* **类型安全的文件与控件**——UI 不会因为模型格式漂移而坏掉。
* **闭环交互**——widget 的选择结果和 secret-request 拿到的凭据都会以结构化数据回到 Agent，再配合状态机形成正常的轮次交接。
* **清晰的安全边界**——凭据走掩码输入而不是明文聊天，附件走文件系统而不是被塞进提示词。

---

## 设计经验

1. **把用户可见的输出降级成一次工具调用。**声明普通文本只是思考、不可见，逼着模型明确选择"要发什么、以什么形状发"。一句提示词加一份工具定义，就换来了一个完全结构化的 UI。
2. **把 schema 当作 UI 契约。**一个气泡类型枚举加上每种类型的必填字段，把"文件混进正文"从*指望模型规矩点*变成*结构上不可能*。
3. **让校验失败可恢复。**为模型写错误信息——自然语言，把怎么修写清楚——它就能自己修好，用户全程无感。
4. **把会话时序放进运行时。**"等用户回复时不要发"这类规则，写在代码里比写在提示词里可靠得多。
5. **文件走文件系统，只传引用。**消息里只带一个 `file://` 或 `https://` 引用，字节走内容寻址存储，预览在客户端解析，于是不占用任何模型上下文。

---

**参考来源**

- 原文：[Decoding Grok Bot - The Message Mechanism](https://www.weisu.io/articles/decoding-grok-bot/message-mechanism)，作者 Wei Su，weisu.io（Fumadocs 文档站）。原页面与 `llms.txt` 均未标注发布日期，故文件名日期取翻译日 2026-11-12。
- 原文正文无插图，仅代码块与表格；本译文未添加任何原文没有的配图。

**术语对照**

| 英文 | 中文 | 说明 |
| --- | --- | --- |
| bubble | 气泡 | 聊天界面里单条消息的呈现单位 |
| tool call | 工具调用 | 模型通过结构化参数触发宿主代码 |
| tool guidance | 工具说明 | 随工具定义一起注入模型的行为指引 |
| parameter schema | 参数 schema | Zod 定义的工具入参结构与校验 |
| cross-validation / superRefine | 交叉校验 | Zod 的跨字段校验钩子 |
| state gate | 状态闸门 | 运行时按会话状态拒绝不合时宜的调用 |
| widget | 控件 | 带可选项的交互式提问组件 |
| attachment | 附件 | 独立于文本的文件卡片 |
| secret-request | 凭据请求 | 掩码输入，避免凭据进入聊天明文 |
| renderer | 渲染器 | 客户端按类型把数据画成气泡/卡片 |
| transcript | 会话记录 | 宿主记录的对话流水 |
| content-addressed | 内容寻址 | 以 SHA-256 等哈希作为存储键 |
| sandbox | 沙箱 | Agent 执行代码/生成文件的隔离环境 |
| middleware | 中间件 | 在模型与工具之间插入的运行时逻辑 |
| feature flag | 功能开关 | 单独控制呈现或行为的开关 |
| system prompt | 系统提示词 | 与 `<system_reminder>` 注入区分 |
