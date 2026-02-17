# Showboat & Rodney Skill

> 用于 AI Agent 测试和演示工作成果的工具组合
> 来源: https://simonwillison.net/2026/Feb/10/showboat-and-rodney/

---

## Showboat - 构建演示文档

让 Agent 创建 Markdown 文档来展示代码功能，包含执行结果和截图。

### 安装
```bash
uvx showboat --help
# 或
pip install showboat
```

### 核心命令

```bash
# 初始化文档
showboat init demo.md "文档标题"

# 添加说明文字
showboat note demo.md "这里是说明..."

# 执行命令并捕获输出
showboat exec demo.md bash "curl -s https://api.github.com/users/simonw"

# 捕获截图（自动识别图片路径）
showboat image demo.md "shot-scraper https://example.com -o screenshot.png"

# 撤销最后一节
showboat pop demo.md

# 验证文档（重新运行所有命令检查输出是否一致）
showboat verify demo.md

# 反向解析文档生成命令
showboat extract demo.md
```

### 使用示例

```bash
showboat init demo.md "My Project Demo"
showboat note demo.md "This project provides a CLI tool for X"
showboat exec demo.md python "python -c 'print(\"Hello World\")'"
showboat note demo.md "Here's a screenshot of the tool in action:"
showboat image demo.md "shot-scraper https://mysite.com -o demo.png"
```

### 提示词模板

给 Agent 的指令：
```
Run "uvx showboat --help" and then use showboat to create a demo.md 
document describing the feature you just built.
```

---

## Rodney - 浏览器自动化 CLI

基于 Chrome DevTools Protocol 的 CLI 浏览器控制工具，可与 Showboat 配合截图。

### 安装
```bash
uvx rodney --help
# 或
pip install rodney
```

### 核心命令

```bash
# 启动 Chrome（后台）
rodney start

# 打开网页
rodney open https://datasette.io/

# 执行 JavaScript
rodney js 'document.title'
rodney js 'Array.from(document.links).map(el => el.href).slice(0, 5)'

# 点击元素（CSS 选择器）
rodney click 'a[href="/for"]'

# 获取当前 URL
rodney js 'location.href'

# 截图
rodney screenshot output.png

# 停止 Chrome
rodney stop
```

### 高级功能

**无障碍测试：**
```bash
# 运行无障碍审计
rodney axe https://mysite.com
```

### 与 Showboat 配合使用

```bash
showboat init browser-demo.md "Web App Demo"
showboat note browser-demo.md "Starting browser automation demo"
showboat exec browser-demo.md bash "rodney start"
showboat exec browser-demo.md bash "rodney open https://mysite.com"
showboat image browser-demo.md "rodney screenshot homepage.png"
showboat exec browser-demo.md bash "rodney click 'button.login'"
showboat image browser-demo.md "rodney screenshot login-page.png"
showboat exec browser-demo.md bash "rodney stop"
```

---

## 应用场景

### 1. Agent 工作验证
让 Agent 在完成任务后自动生成演示文档：
```
你完成了新功能的开发。请：
1. 运行测试确保功能正常
2. 使用 Showboat 创建 demo.md 文档展示功能
3. 如果涉及网页，使用 Rodney 截取关键页面截图
```

### 2. 自动化测试报告
```bash
showboat init test-report.md "Test Results"
showboat note test-report.md "Running test suite..."
showboat exec test-report.md bash "pytest -v"
showboat note test-report.md "Test coverage report:"
showboat exec test-report.md bash "coverage report"
```

### 3. 网页功能演示
```bash
showboat init web-demo.md "New Feature Demo"
rodney start
rodney open http://localhost:3000
showboat image web-demo.md "rodney screenshot homepage.png"
rodney click 'button.new-feature'
showboat image web-demo.md "rodney screenshot feature-page.png"
rodney stop
```

---

## 快速参考

| 需求 | 工具 | 命令 |
|------|------|------|
| 记录命令输出 | Showboat | `showboat exec doc.md bash "cmd"` |
| 捕获截图 | Showboat + Rodney | `showboat image doc.md "rodney screenshot x.png"` |
| 浏览器自动化 | Rodney | `rodney start/open/click/js/stop` |
| 验证文档 | Showboat | `showboat verify doc.md` |

---

## 注意事项

1. **Agent 可能作弊** - Agent 可能直接编辑 Markdown 文件而非使用 Showboat 命令，导致输出不真实。需要提示词约束。

2. **Rodney 需要 Chrome** - 确保系统已安装 Chrome 或 Chromium

3. **异步环境** - 这两个工具都设计用于异步 Agent 环境（如 Claude Code for web）

---

## 相关链接

- Showboat GitHub: https://github.com/simonw/showboat
- Rodney GitHub: https://github.com/simonw/rodney
- 原文: https://simonwillison.net/2026/Feb/10/showboat-and-rodney/
