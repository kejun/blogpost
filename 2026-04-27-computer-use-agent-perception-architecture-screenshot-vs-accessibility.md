# Computer Use Agent 的感知架构之战：截图视觉 vs 无障碍树的技术路线深度分析

**文档日期：** 2026 年 4 月 27 日  
**标签：** Computer Use, GUI Agent, Accessibility Tree, Screenshot, UI Automation, DirectShell, OSWorld, Agent Architecture

---

## 一、背景分析：当 AI Agent 开始"看"你的屏幕

### 1.1 从终端到桌面：Agent 的能力边界扩张

2025 年，AI Agent 的核心交互界面仍然是终端和代码编辑器。Claude Code、Codex CLI、OpenCode 等工具在编程领域展示了惊人的能力。但 2026 年 4 月，行业迎来了一个关键转折点：

| 日期 | 事件 | 意义 |
|------|------|------|
| 2025 年初 | OpenAI Operator 发布 | 首个基于截图的 Web 自动化 Agent |
| 2025 年中 | Anthropic Computer Use API | 将桌面控制作为一等公民工具 |
| 2026 年 4 月 16 日 | OpenAI Codex Desktop 发布 | macOS 原生桌面自动化，支持后台并行 Agent 会话 |
| 2026 年 4 月 | Vercel Agent-Browser 发布 | 支持 Claude Code/Codex/Cursor 等工具的确定性浏览器自动化 |

**这标志着 Agent 从"编程助手"向"桌面操作员"的范式转变。**

### 1.2 核心问题：Agent 如何"感知"屏幕？

当 Agent 需要操作一个 GUI 应用时，它面临一个根本性问题：**如何理解屏幕上显示的内容？**

这个问题看似简单，却决定了整个 Agent 系统的性能上限、成本结构和可靠性边界。目前行业存在三种主要架构路线，它们之间的差异远比表面看起来深刻。

---

## 二、三种感知架构的深度对比

### 2.1 架构一：截图 + 视觉模型（Screenshot + Vision）

这是目前最主流的方案，也是 OpenAI Operator、Anthropic Computer Use、Google Project Mariner 等产品的核心技术栈。

**工作原理：**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Screenshot + Vision 架构                      │
│                                                                     │
│  ┌──────────┐    截图     ┌──────────────┐    Prompt + 图片    ┌───┐│
│  │  目标应用 │ ──────────→ │  屏幕捕获层   │ ──────────────────→│ L ││
│  │  (任意GUI) │            │  (PIL/pyautogui)│                 │ L ││
│  └──────────┘             └──────────────┘                     │ M ││
│                                         坐标/动作指令           │ L ││
│  ┌──────────┐    输入注入   ┌──────────────┐    ←─────────────  └───┘│
│  │  目标应用 │ ←────────── │  输入注入层   │   结构化输出          │
│  │  (任意GUI) │            │  (pyautogui/AutoPy)│                  │
│  └──────────┘             └──────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

**核心流程：**
1. 捕获屏幕截图（通常 1280×720 或 1024×768 缩放）
2. 将截图嵌入多模态 LLM 的 Prompt
3. LLM 输出目标坐标和动作（click(x, y), type(text)）
4. 通过输入注入层执行动作
5. 循环直到任务完成

**实际代码示例（简化版 Computer Use 实现）：**

```python
import base64
import pyautogui
from openai import OpenAI

class ScreenshotAgent:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        pyautogui.FAILSAFE = True  # 鼠标移到屏幕角落可中止
        
    def capture_screen(self) -> str:
        """捕获屏幕并编码为 base64"""
        screenshot = pyautogui.screenshot()
        # 缩放以控制 token 消耗
        screenshot = screenshot.resize((1024, 768))
        buffered = io.BytesIO()
        screenshot.save(buffered, format="JPEG", quality=80)
        return base64.b64encode(buffered.getvalue()).decode()
    
    def get_action(self, screenshot_b64: str, goal: str) -> dict:
        """调用多模态 LLM 获取下一步动作"""
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "你是一个桌面自动化助手。"},
                {"role": "user", "content": [
                    {"type": "text", "text": f"目标: {goal}\n分析当前屏幕并决定下一步操作。"},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{screenshot_b64}"
                    }}
                ]}
            ],
            tools=[{
                "type": "function",
                "function": {
                    "name": "computer_action",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {"enum": ["click", "type", "scroll", "hotkey"]},
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "text": {"type": "string"}
                        }
                    }
                }
            }]
        )
        return response.choices[0].message.tool_calls[0].function.arguments
    
    def execute(self, action: dict):
        """执行动作"""
        if action["action"] == "click":
            pyautogui.click(action["x"], action["y"])
        elif action["action"] == "type":
            pyautogui.typewrite(action["text"], interval=0.05)
        # ...
```

**优势：**
- **通用性最强**：适用于任何 GUI，无需目标应用支持
- **实现简单**：不需要理解目标应用的内部结构
- **跨平台**：Windows/macOS/Linux 通用

**劣势：**
- **Token 消耗巨大**：每张截图 1,200–5,000 tokens（GPT-4o/Claude）
- **速度慢**：截图 + LLM 推理 + 输入注入，每步 2–5 秒
- **精度有限**：LLM 的坐标预测存在固有误差，尤其是密集 UI
- **分辨率敏感**：缩放比变化导致坐标映射偏差
- **状态不可靠**：截图无法区分"视觉上相似但功能不同"的元素

### 2.2 架构二：无障碍 API 直接读取（Accessibility API）

这是 DirectShell、Windows-MCP、computer-mcp 等项目采用的方案。核心洞察是：**操作系统已经以结构化文本形式描述了所有 UI 元素，为什么还要截图？**

**工作原理：**

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Accessibility API 架构                          │
│                                                                     │
│  ┌──────────┐    UIA/AX API  ┌──────────────┐    结构化文本     ┌───┐│
│  │  目标应用 │ ──────────→   │  无障碍树提取  │ ────────────────→│ L ││
│  │  (任意GUI) │              │  (UIA/AX/AT-SPI)│               │ L ││
│  └──────────┘               └──────────────┘   50–200 tokens    │ M ││
│                                         结构化动作指令          │ L ││
│  ┌──────────┐    输入注入    ┌──────────────┐    ←─────────────  └───┘│
│  │  目标应用 │ ←──────────  │  输入注入层   │   (action + target)   │
│  │  (任意GUI) │             │  (UIA Invoke/AXPress)│               │
│  └──────────┘              └──────────────┘                        │
└─────────────────────────────────────────────────────────────────────┘
```

**DirectShell 的 .a11y.snap 输出示例：**

```
[1] [keyboard] "Adressfeld" @ 168,41 (2049x29)
[2] [click] "Neuer Chat" @ 45,200 (200x30)
[3] [keyboard] "Einen Prompt eingeben" @ 999,1177 (1069x37)
[4] [click] "Einstellungen" @ 1800,1350 (150x20)

# 4 operable elements in viewport
```

**4 行文本。** 截图方案需要 1,200–5,000 tokens 才能传达的信息，这里只用了几十个 token。

**各平台无障碍 API 对比：**

| 平台 | 框架 | 版本 | 覆盖范围 |
|------|------|------|----------|
| Windows | UI Automation (UIA) | 2005 | 原生 Win32/UWP/WPF/WinForms |
| macOS | NSAccessibility (AX) | 2001 | Cocoa/Carbon 应用 |
| Linux | AT-SPI2 (D-Bus) | 2001 | GTK/Qt/Electron 应用 |
| Android | AccessibilityService | 2009 | Android 应用 |
| Web | ARIA + DOM | 2014 | 浏览器内所有网页 |

**实际代码示例（DirectShell 风格的 SQL 查询）：**

```python
import sqlite3

class AccessibilityAgent:
    def __init__(self, db_path: str):
        """连接到 DirectShell 生成的 SQLite 数据库"""
        self.conn = sqlite3.connect(db_path)
        
    def get_visible_elements(self) -> list[dict]:
        """获取当前视口内所有可交互元素"""
        cursor = self.conn.execute("""
            SELECT id, role, name, x, y, width, height, value, enabled
            FROM elements 
            WHERE visible = 1 AND interactive = 1
            ORDER BY y, x
        """)
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def find_element(self, name_pattern: str, role: str = None) -> dict:
        """通过名称模式查找元素"""
        query = """
            SELECT id, role, name, x, y, width, height, value, enabled
            FROM elements 
            WHERE name LIKE ? AND role = ?
            LIMIT 1
        """
        cursor = self.conn.execute(query, (f"%{name_pattern}%", role))
        columns = [desc[0] for desc in cursor.description]
        row = cursor.fetchone()
        return dict(zip(columns, row)) if row else None
    
    def click_element(self, element_id: int):
        """通过元素 ID 点击（不需要坐标）"""
        # 写入动作队列，DirectShell 自动执行
        self.conn.execute(
            "INSERT INTO action_queue (action, target_id) VALUES (?, ?)",
            ("click", element_id)
        )
        self.conn.commit()
```

**优势：**
- **Token 效率极高**：50–200 tokens vs 1,200–5,000（10–30x 差距）
- **速度快**：本地 API 调用 < 200ms，无需网络 LLM 推理
- **精度极高**：直接按元素 ID 操作，不存在坐标偏差
- **上下文持久**：省下的 token 可以保留更多对话历史
- **结构化查询**：可以用 SQL 精确筛选目标元素

**劣势：**
- **平台相关**：每个 OS 需要不同的实现
- **应用依赖**：目标应用必须正确实现无障碍支持
- **覆盖不完整**：部分游戏引擎/自定义绘制应用不暴露无障碍树
- **学习曲线**：需要理解各平台无障碍 API 的语义差异

### 2.3 架构三：混合方案（Hybrid）

结合两种方案的优势：以无障碍树为主，截图作为 fallback。

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Hybrid 架构                                  │
│                                                                     │
│                    ┌─────────────────────────┐                      │
│                    │    感知决策路由器         │                      │
│                    └──────────┬──────────────┘                      │
│                               │                                     │
│              ┌────────────────┼────────────────┐                    │
│              ▼                ▼                 ▼                    │
│     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│     │ 无障碍树优先   │ │ 截图 fallback │ │ DOM (浏览器) │             │
│     │ (AT-SPI/UIA) │ │ (多模态LLM)  │ │ (Playwright) │             │
│     └──────┬───────┘ └──────┬───────┘ └──────┬───────┘             │
│            │                │                 │                     │
│            └────────────────┼─────────────────┘                     │
│                             ▼                                       │
│                    ┌─────────────────┐                               │
│                    │   统一动作执行层  │                               │
│                    │ (元素ID / 坐标)  │                               │
│                    └─────────────────┘                               │
└─────────────────────────────────────────────────────────────────────┘
```

**决策逻辑：**

```python
class HybridPerception:
    def perceive(self, context: PerceiveContext) -> PerceptionResult:
        # 1. 优先尝试无障碍树
        a11y_tree = self.get_accessibility_tree(context.target_app)
        if a11y_tree and self.is_sufficient(a11y_tree, context.goal):
            return PerceptionResult(
                source="accessibility",
                elements=a11y_tree,
                confidence=0.95
            )
        
        # 2. 如果是浏览器，尝试 DOM
        if context.is_browser:
            dom_info = self.get_dom_info(context.browser)
            if dom_info:
                return PerceptionResult(
                    source="dom",
                    elements=dom_info,
                    confidence=0.9
                )
        
        # 3. Fallback: 截图 + 视觉模型
        screenshot = self.capture_screenshot(context)
        vision_result = self.vision_model.analyze(screenshot, context.goal)
        return PerceptionResult(
            source="vision",
            elements=vision_result,
            confidence=0.6  # 视觉方案的固有低置信度
        )
```

---

## 三、数据验证：OSWorld 基准测试的残酷现实

OSWorld 是目前最权威的 GUI Agent 基准测试平台，模拟真实桌面操作任务。2026 年 2 月的数据揭示了三种架构的性能差异：

| Agent | 架构类型 | 成功率 | 平均耗时 | Token/步 |
|-------|----------|--------|----------|----------|
| **AskUI VisionAgent** | 截图 + 视觉 | 66.2% | N/A | 3,500 |
| **UI-TARS 2 (ByteDance)** | 截图 + 视觉 | 47.5% | 12–18 min | 2,800 |
| **OpenAI CUA o3** | 截图 + 视觉 | 42.9% | 15–20 min | 4,200 |
| **Claude Computer Use** | 截图 + 视觉 | 22–28% | 10–15 min | 3,800 |
| **DirectShell (预估)** | 无障碍树 | ~70%+ | < 2 min | 50–200 |
| **人类基线** | — | 72.4% | 30 sec – 2 min | — |

**关键洞察：**

1. **截图方案的天花板约 66%**：即使最先进的 AskUI VisionAgent，仍然比人类基线低 6 个百分点
2. **时间差距巨大**：Agent 需要 10–20 分钟完成的任务，人类 30 秒完成
3. **Token 成本不可忽视**：一个 10 步任务，截图方案消耗 30,000–40,000 tokens 仅用于"感知"，而无障碍方案仅需 500–2,000 tokens
4. **上下文窗口杀手**：截图方案在 10 步后基本耗尽上下文，而无障碍方案可以维持数百步的历史

---

## 四、技术深度分析：为什么截图方案存在根本性局限

### 4.1 信息熵问题

截图方案的本质是**对已经结构化的数据进行有损压缩，然后再尝试无损还原**：

```
原始数据（无障碍树）:
  结构化文本，包含: 元素类型、名称、值、位置、状态、层级关系
  信息量: ~500-2000 bytes (纯文本)
       ↓ 有损压缩
截图:
  像素阵列，包含: RGB 颜色值
  信息量: ~200-500 KB (JPEG 压缩后)
  丢失: 元素语义、层级关系、交互状态
       ↓ 尝试还原
LLM 视觉推理:
  从像素中推断: 这是什么元素？在哪里？能做什么？
  准确率: 受限于模型视觉能力 + 分辨率 + 遮挡
```

这相当于**拍一张 JSON 响应的照片，然后用 OCR 识别它**——而不是直接解析 JSON。

### 4.2 坐标映射的精度问题

截图方案的核心瓶颈在于坐标映射：

```python
# 截图方案中的坐标映射问题
screenshot_size = (1024, 768)      # LLM 看到的尺寸
actual_screen = (2560, 1440)       # 实际屏幕尺寸

# LLM 输出: click(x=512, y=384) — 基于截图尺寸
# 实际执行: 需要映射到实际屏幕
actual_x = 512 * (2560 / 1024)     # = 1280
actual_y = 384 * (1440 / 768)      # = 720

# 问题:
# 1. 缩放导致亚像素精度丢失
# 2. 多显示器场景下坐标空间更复杂
# 3. 滚动/缩放/窗口调整会改变映射关系
# 4. HiDPI/Retina 显示器的 2x 缩放引入额外误差层
```

无障碍方案直接按元素 ID 操作，完全规避了这个问题。

### 4.3 状态感知的缺失

截图无法传达的关键状态信息：

| 信息类型 | 截图能否获取 | 无障碍树能否获取 |
|----------|-------------|-----------------|
| 按钮是否禁用（grayed out） | ⚠️ 视觉推断 | ✅ `IsEnabled: false` |
| 文本框当前值 | ⚠️ OCR 识别 | ✅ `Value: "KD-4711"` |
| 元素是否被遮挡 | ❌ 无法判断 | ✅ `IsOffscreen: true` |
| 下拉菜单选项 | ⚠️ 需要展开后截图 | ✅ 直接读取选项列表 |
| 表单验证错误 | ⚠️ 视觉推断 | ✅ `ErrorMessage: "必填"` |
| 键盘焦点位置 | ❌ 难以判断 | ✅ `IsFocused: true` |

---

## 五、实际案例：DirectShell 的架构创新

DirectShell 在 2026 年 2 月发布，它的核心创新不是"使用无障碍 API"（这本身不新），而是**将无障碍树转化为可查询的 SQL 数据库**：

```
DirectShell 架构:

┌─────────────────────────────────────────────────────────┐
│  目标应用 (任意 GUI)                                      │
│         │                                               │
│         ▼ (UIA/AX/AT-SPI API, 500ms 刷新)               │
│  ┌─────────────────────────┐                            │
│  │   SQLite 数据库          │                            │
│  │   ┌───────────────────┐ │                            │
│  │   │ elements 表        │ │ ← 完整的无障碍树           │
│  │   │ (id, role, name,   │ │                            │
│  │   │  x, y, value, ...) │ │                            │
│  │   └───────────────────┘ │                            │
│  │   ┌───────────────────┐ │                            │
│  │   │ action_queue 表    │ │ ← 写入即执行               │
│  │   │ (action, target_id)│ │                            │
│  │   └───────────────────┘ │                            │
│  └──────────┬──────────────┘                            │
│             │                                           │
│    ┌────────┼────────┬────────┬────────┐               │
│    ▼        ▼        ▼        ▼        ▼               │
│   .db     .snap    .a11y   .a11y    控制台            │
│  (完整)  (交互元素) (焦点)  (LLM快照)  (可视化)         │
└─────────────────────────────────────────────────────────┘
```

**四种输出格式的设计哲学：**

| 格式 | 大小 | 用途 | 设计意图 |
|------|------|------|----------|
| `.db` (SQLite) | 100KB–1.5MB | 脚本/程序直接查询 | 完整数据，任意 SQL 查询 |
| `.snap` | 3–15 KB | 自动化脚本 | 仅交互元素，分类标注 |
| `.a11y` | 3–10 KB | 上下文感知 Agent | 焦点 + 输入 + 可见内容 |
| `.a11y.snap` | 1–5 KB | LLM 消费 | 编号可操作元素，最小 token |

**LLM 读取 .a11y.snap 的 Prompt 示例：**

```
当前屏幕状态:
[1] [keyboard] "Search" @ 200,50 (300x30)
[2] [click] "Settings" @ 1800,30 (80x25)
[3] [click] "Logout" @ 1800,60 (80x25)
[4] [list] "Results" @ 200,100 (1400x600)
  ├── [5] [click] "Item A - $19.99" @ 200,120
  ├── [6] [click] "Item B - $29.99" @ 200,170
  └── [7] [click] "Item C - $39.99" @ 200,220

目标: 找到价格低于 $25 的商品并加入购物车

请回复格式: action: [click|type|scroll], target: [编号]
```

这个 Prompt 约 200 tokens。同等信息的截图方案需要 3,000+ tokens。

---

## 六、工程实践建议：如何选择感知架构

### 6.1 决策矩阵

```
你的场景是什么？
│
├─ 需要操作任意桌面应用（包括非标准 GUI）？
│  ├─ 是 → 截图方案是唯一选择
│  │       但注意: 成功率上限 ~66%，成本高
│  │
│  └─ 否 → 目标应用是否支持无障碍 API？
│     ├─ 是（大多数标准应用：Office, Slack, VS Code, 浏览器）
│     │  └─ 无障碍方案 → 最佳选择
│     │
│     └─ 不确定/混合场景
│        └─ Hybrid 方案 → 无障碍优先 + 截图 fallback
```

### 6.2 实际部署建议

**对于 Web 自动化场景：**

```python
# 推荐: Playwright MCP + 无障碍树
# 浏览器天然暴露完整的 DOM + ARIA 树
# 比截图方案快 10x，准确率高 3x

from playwright.async_api import async_playwright

async def automate_with_accessibility():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")
        
        # 通过 ARIA 角色和名称定位，而非坐标
        search_box = page.get_by_role("textbox", name="Search")
        await search_box.fill("query")
        
        submit_btn = page.get_by_role("button", name="Submit")
        await submit_btn.click()
```

**对于桌面应用场景：**

```python
# 推荐: DirectShell 风格的无障碍 + SQL 方案
# 适用于: Office, SAP, 财务软件, 任何标准桌面应用

import sqlite3

class DesktopAgent:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
    
    def find_and_click(self, name: str, role: str = "button"):
        """通过语义查找元素并点击"""
        result = self.db.execute(
            "SELECT id FROM elements WHERE name LIKE ? AND role = ? LIMIT 1",
            (f"%{name}%", role)
        ).fetchone()
        if result:
            self.db.execute(
                "INSERT INTO action_queue (action, target_id) VALUES ('click', ?)",
                (result[0],)
            )
            self.db.commit()
```

### 6.3 成本对比（10 步任务）

| 指标 | 截图方案 | 无障碍方案 | 差距 |
|------|----------|-----------|------|
| Token 消耗（感知） | 35,000 | 1,500 | **23x** |
| 任务完成时间 | 12 分钟 | 1.5 分钟 | **8x** |
| API 调用成本（GPT-4o） | ~$0.35 | ~$0.015 | **23x** |
| 成功率 | ~45% | ~70% | **1.5x** |
| 上下文保留步数 | ~10 步 | ~200 步 | **20x** |

---

## 七、总结与展望

### 7.1 核心结论

1. **截图 + 视觉方案是过渡态，不是终态。** 它的通用性优势正在被无障碍方案的快速进化所抵消。当 90% 的桌面应用都正确暴露无障碍树时，截图方案唯一的"不可替代"场景只剩下游戏和自定义绘制应用。

2. **Token 效率是 Agent 系统的第一性原理。** 省下的 token 意味着更长的上下文、更多的推理步骤、更低的成本。无障碍方案的 10–30x token 优势不是渐进改进，而是量级差异。

3. **DirectShell 揭示了一个被忽视 29 年的基础设施层。** 无障碍 API 自 1997 年存在，但直到 2026 年才有人将其系统化地转化为 Agent 可用的基础设施。这提醒我们：**最好的技术方案可能就在你身边，只是你一直在用更复杂的方式解决同一个问题。**

### 7.2 行业趋势预测

| 时间线 | 预测 |
|--------|------|
| 2026 Q2 | 更多 MCP 服务器基于无障碍 API 而非截图 |
| 2026 Q3 | 主流 Agent 框架内置 Hybrid 感知路由器 |
| 2026 Q4 | Web 端无障碍 Agent 成功率突破 80% |
| 2027 H1 | 截图方案退化为 fallback 角色，不再是主路径 |

### 7.3 给开发者的建议

- **如果你正在构建 Agent 系统**：优先实现无障碍 API 支持，截图作为 fallback
- **如果你在选型 Agent 平台**：关注其感知架构，而非仅看营销文案中的"Computer Use"
- **如果你在评估 Agent 性能**：用 OSWorld 等基准测试，而非 demo 视频
- **如果你在开发桌面应用**：确保你的应用正确实现无障碍支持——这正在成为 Agent 时代的基本功

> "Photographing a JSON response and running OCR on the photo — instead of parsing the JSON. That is, architecturally, what the entire AI industry is doing."
> 
> — Martin Gehrken, DirectShell 作者

---

**参考资料：**

1. [DirectShell: I Turned the Accessibility Layer Into a Universal App Interface](https://dev.to/tlrag/-directshell-i-turned-the-accessibility-layer-into-a-universal-app-interface-no-screenshots-no-2457)
2. [OSWorld Benchmark](https://os-world.github.io/)
3. [Anthropic Computer Use Tool Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool)
4. [OpenAI Codex Desktop Announcement (April 2026)](https://openai.com)
5. [Fazm: How AI Agents Actually See Your Screen](https://fazm.ai/blog/how-ai-agents-see-your-screen-dom-vs-screenshots)
6. [VILA-Lab: Dive into Claude Code (arXiv 2604.14228)](https://github.com/VILA-Lab/Dive-into-Claude-Code)
7. [Agent-Browser Protocol (theredsix)](https://github.com/theredsix/agent-browser-protocol)
8. [Fazm: Open Source Computer Use Agent GitHub Repos 2026](https://fazm.ai/blog/open-source-computer-use-agent-github-2026)
