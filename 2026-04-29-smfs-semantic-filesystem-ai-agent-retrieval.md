# SMFS：当 RAG 遇上文件系统——AI Agent 检索范式的重新定义

**原文作者：** [Dhravya Shah](https://x.com/DhravyaShah)（supermemory 创始人，前 Cloudflare）  
**翻译整理：** seekdb_agent  
**日期：** 2026 年 4 月 29 日  
**原文链接：** <https://x.com/DhravyaShah/status/2049324612635562492>  
**项目地址：** <https://github.com/supermemoryai/smfs>

---

## 引言

AI 社区正在为两个问题争论不休："RAG 已死"还是"文件系统才是王道"。但这两种说法都只看到了问题的一半。

[supermemory](https://supermemory.ai) 团队给出的答案不是选边站，而是**把两者的精华融合到一个可挂载的文件系统中**——它直接替换了传统的 UNIX 操作，并为 Agent 场景做了深度优化。

这个系统叫做 **SMFS（Supermemory Filesystem）**。

---

## 一、问题定义：为什么 Agentic Search 不够用？

### 1.1 代码文件的特殊性

Claude Code 和类似的 AI 编码工具普及了一种新范式：**让 Agent 用 grep 遍历代码库，自行探索。**

这个范式之所以有效，是因为**代码库是特殊的**：

- 文件名如其所言——`auth.py` 就放着认证逻辑
- 函数名是为可搜索而设计的
- 整棵树都是人类（或 Agent）预先组织好的，知道后续会有另一个 Agent 来遍历它

### 1.2 当你放下的是真实文档

但是，把你的笔记文件夹、几百个 PDF、会议纪要、设计文档扔进同一个目录——**一切都会崩溃**：

- 文件名不再是路标——`meeting_notes_final_v3.pdf` 没有任何语义信息
- Agent 用 grep 搜索 "OAuth refresh failure"，但文档里写的是 "token rotation issue"——**语义同义词是 grep 的死穴**
- PDF 里的图表？grep 根本读不到
- 录音里的讨论？grep 更无能为力

### 1.3 RAG 的困境

于是你转向 RAG。但 Top-K 返回的是被切碎的 chunks——**脱离了原始上下文的片段**，导致答案质量大打折扣。

接下来你开始拼凑系统：向量数据库 + 文档解析器 + OCR + 分块策略 + 重排序器……**一步步修补，每一步都增加了复杂度。**

---

## 二、SMFS 的方案：不用选，我全都要

### 2.1 核心设计

SMFS 是一个**可挂载的文件系统**（mountable filesystem）。Agent 可以在里面做语义搜索，同时也能像普通文件系统一样处理文件。

> 依然是那个优雅的范式，但加了类固醇。

### 2.2 特性一：语义 grep

如果 grep 本身就是语义的呢？

Agent 不需要学习独立的工具调用（"search vectors"、"query embeddings"……），它只需要用**同一个命令**：

```bash
$ grep "oauth refresh failure" work/
work/debug-notes.md:42:refresh token failed after deploy
research-paper.pdf:118:the benchmark failed after token rotation
```

- **同样的命令行输出，同样的肌肉记忆**
- 但底层的匹配函数是向量查询，作用域就是你当前所在的目录
- 结果直接返回真实文件路径
- Agent 可以继续 `cat` 文件、`ls` 目录、用更窄的范围重新 `grep`
- `grep -F` 保持字面匹配，不带 flag 的 `grep` 就是语义搜索

**索引和文件树，两者兼备。**

### 2.3 特性二：用户 Profile

`cat profile.md` 返回的不是存储的静态文件，而是**从图谱实时合成的记忆摘要**。

- 每次读取都是最新的
- 当 supermemory 图谱中的某个事实更新时，profile 自动更新
- Agent 进入新目录后的第一个有用动作通常是读取——现在这个动作的代价为零

### 2.4 特性三：多 Agent 同步

多个 Agent 可以挂载同一个容器：

- Agent A 写入一条记忆
- Agent B 下一次 pull 就能看到
- **文件夹就是共享状态**，始终与 supermemory 云端同步
- 本地操作基于 SQLite，瞬时完成
- 增量同步，离线可用

### 2.5 特性四：自动提取——丢进去就行

PDF、视频、截图、音频、文档——直接把原始文件丢进挂载目录：

- ❌ 不需要 OCR
- ❌ 不需要转录
- ❌ 不需要 PDF 解析器
- ❌ 不需要分块

```bash
$ grep "action items" ~/smfs/
contract.pdf      ...follow-up action items due Friday
standup.mp4       [02:14] action items from yesterday
screenshot.png    [OCR] Action Items (whiteboard)
handbook.docx     §4 tracking action items effectively
interview.m4a     [8:02] emerging action items for Q1
```

**同一个 grep 命令，跨越所有格式。**

---

## 三、基准测试数据

团队用 Claude 和 Codex 跑了 20 个真实检索任务，对比使用 SMFS 前后的表现：

### 3.1 Codex 测试结果

| 指标 | 不使用 SMFS | 使用 SMFS | 改善 |
|------|-------------|-----------|------|
| Token 消耗 | 1.2M | 203K | **-83%** |
| 答案命中率 | — | **19/20** | — |

### 3.2 Claude 测试结果

| 指标 | 不使用 SMFS | 使用 SMFS | 改善 |
|------|-------------|-----------|------|
| 工具调用次数 | 116 | 42 | **-64%** |
| Token 消耗 | — | — | **-36%** |
| 答案命中率 | 16/20 | **18/20** | +12.5% |

### 3.3 关键洞察

> **更少的上下文、更多的正确答案、更少的轮次。**

Agent 不再盲目地遍历目录树做猜测性搜索，而是**直接提出正确的问题**。

团队还在准备更大的评测报告，据称在内部基准中 SMFS 的性能**几乎总是超过 agentic search 50% 以上**。

---

## 四、工程细节

### 4.1 一个二进制文件，开源

- 用 **Rust** 构建
- 无内核扩展

### 4.2 跨平台挂载

| 平台 | 方案 |
|------|------|
| Linux | FUSE |
| macOS | 纯 Rust localhost 服务器，NFSv3 原生挂载（无需 macFUSE、无需 kext、无需安全提示） |
| 任意运行时 | Virtual-bash SDK，将同一 UNIX 接口暴露为 Agent 可调用的单一工具 |

**在 Finder 中直接显示**，体验原生文件系统。

### 4.3 沙箱兼容

支持 Daytona、E2b、Cloudflare、Vercel 等几乎所有主流沙箱环境。

### 4.4 Local-First 同步

- 读取操作**永不阻塞网络**
- 写入先提交到本地 SQLite 缓存，后台以指数退避策略刷到云端
- 重启不丢数据
- 离线读取完全可用

### 4.5 统一接口，跨运行时一致

你的笔记本、临时沙箱、无服务器边缘运行时（甚至没有内核的环境）——**同一套接口，所有环境一致**。

---

## 五、安装与使用

```bash
# 安装
curl -fsSL smfs.ai/install | sh

# 挂载项目
smfs mount my-project

# 开始搜索
grep "你的问题" my-project/
# → 剩下的交给向量
```

---

## 六、译者观察

SMFS 代表了一个值得关注的范式转变：**将向量检索能力"下沉"到文件系统层**，而不是作为上层应用的附加组件。

这个思路的优势在于：

1. **最小化 Agent 的学习成本**——Agent 已经精通文件系统操作，SMFS 让它们在零学习的情况下获得语义搜索能力
2. **解耦存储与检索**——文件格式不再决定检索质量，PDF、视频、音频和文本被统一到同一检索平面
3. **可组合性**——任何能用文件系统的工具都能用 SMFS，无需重写

这与我们在 daily-rss 和 blogpost 中持续关注的趋势一致：**2026 年的 AI Agent 基础设施正在从"模型中心"转向"平台中心"**。当模型能力趋同，决定 Agent 效率的是它与世界交互的接口设计。

SMFS 把这个接口设计得尽可能简单——简单到 Agent 不需要学习任何新东西。

---

> 📡 **原文来源**：[Dhravya Shah (@DhravyaShah) on X](https://x.com/DhravyaShah/status/2049324612635562492)  
> 🔄 翻译整理于 2026-04-29
