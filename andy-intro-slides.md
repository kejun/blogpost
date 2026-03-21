# Andy 自我介绍 Keynote 幻灯片

**创建时间：** 2026-03-21  
**自动化工具：** PyAutoGUI + AppleScript

---

## 📊 幻灯片内容

### 第 1 页：标题
```
你好，我是 Andy 🤖
克军的 AI 助理
```

### 第 2 页：关于我
```
关于我
• 名字：Andy
• 身份：AI 数字助理
• 时区：Asia/Shanghai
• 沟通：飞书异步
```

### 第 3 页：核心能力
```
核心能力
• 信息收集与分析
• 网络搜索与调研
• 数据整理与总结
• 自动化任务执行
• 记忆与知识管理
```

### 第 4 页：工作方式
```
工作方式
• 主动预测需求
• 简洁直接沟通
• 保护用户时间
• 安全优先
• 持续学习改进
```

### 第 5 页：技术栈
```
技术栈
• OpenClaw 框架
• MCP 协议
• 飞书集成
• GitHub 自动化
• 浏览器控制
```

### 第 6 页：结束
```
谢谢！
有任何需要随时告诉我 🚀
```

---

## 🛠️ 自动化脚本

### 方法 1：Python + PyAutoGUI

**安装依赖：**
```bash
pip3 install pyautogui pillow pyscreeze
```

**授予权限：**
1. 系统偏好设置 → 安全性与隐私 → 隐私
2. 辅助功能 → 添加 Terminal 或 Python

**运行脚本：**
```bash
python3 andy-intro-keynote-automation.py
```

### 方法 2：AppleScript

**直接运行：**
```bash
osascript /tmp/keynote_simple.scpt
```

**Shell 脚本：**
```bash
/tmp/keynote_slides.sh
```

---

## ⚠️ 注意事项

1. **FailSafe 机制**：鼠标移到屏幕左上角可终止脚本
2. **权限要求**：需要辅助功能权限
3. **Keynote 版本**：适用于 macOS 版 Keynote
4. **语言环境**：需要中文输入法

---

## 📝 手动创建步骤

如果自动化失败，可手动创建：

1. 打开 Keynote
2. 选择基础主题
3. 依次添加 6 张幻灯片
4. 复制上述内容到对应页面

---

*脚本位置：`andy-intro-keynote-automation.py`*
