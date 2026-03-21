# PyAutoGUI 完整用法与生态工具指南

---

## 📦 安装与配置

### 基础安装
```bash
pip install pyautogui
```

### 依赖安装
```bash
# macOS
brew install python-tk

# Ubuntu/Debian
sudo apt-get install python3-tk python3-dev

# Windows
# 无需额外依赖
```

### 完整生态安装
```bash
# 核心库
pip install pyautogui pillow pyscreeze

# 图像识别增强
pip install opencv-python opencv-contrib-python

# OCR 支持
pip install pytesseract

# 键盘底层控制
pip install keyboard

# 鼠标底层控制
pip install mouse
```

---

## 🔧 核心 API 详解

### 1. 鼠标控制

```python
import pyautogui

# === 移动 ===
# 绝对移动（屏幕左上角为 0,0）
pyautogui.moveTo(100, 100)           # 直接移动
pyautogui.moveTo(100, 100, duration=2)  # 2 秒内移动（动画效果）

# 相对移动
pyautogui.moveRel(0, 100)            # 向下移动 100 像素
pyautogui.moveRel(50, 0, duration=1) # 向右移动 50 像素

# === 点击 ===
pyautogui.click()                    # 左键单击（当前位置）
pyautogui.click(x=100, y=100)        # 指定位置点击
pyautogui.rightClick()               # 右键
pyautogui.doubleClick()              # 双击
pyautogui.tripleClick()              # 三击

# === 拖拽 ===
pyautogui.dragTo(200, 200, duration=2)      # 拖拽到指定位置
pyautogui.dragRel(50, 0, duration=1)        # 相对拖拽
pyautogui.drag(50, 0, button='left')        # 简写

# === 滚动 ===
pyautogui.scroll(10)                 # 向上滚动 10 个单位
pyautogui.scroll(-10)                # 向下滚动
pyautogui.hscroll(10)                # 水平滚动

# === 鼠标状态 ===
x, y = pyautogui.position()          # 获取当前位置
width, height = pyautogui.size()     # 获取屏幕分辨率
```

### 2. 键盘控制

```python
import pyautogui

# === 文本输入 ===
pyautogui.typewrite('Hello World')           # 输入文本
pyautogui.typewrite('Hello', interval=0.1)   # 每字符间隔 0.1 秒

# === 单键按下 ===
pyautogui.press('enter')             # 回车键
pyautogui.press('space')             # 空格
pyautogui.press(['left', 'left'])    # 连续按两次左箭头

# === 组合键 ===
pyautogui.hotkey('ctrl', 'c')        # Ctrl+C
pyautogui.hotkey('ctrl', 'shift', 'esc')  # Ctrl+Shift+Esc

# === 特殊键 ===
# 完整键名列表：https://pyautogui.readthedocs.io/en/latest/keyboard.html
pyautogui.press('win')               # Windows 键
pyautogui.press('command')           # Mac Command 键
pyautogui.press('f1')                # F1-F12
pyautogui.press('volumeup')          # 音量键

# === 按键按下/释放 ===
pyautogui.keyDown('shift')           # 按住 Shift
pyautogui.typewrite('ABC')           # 输入大写字母
pyautogui.keyUp('shift')             # 释放 Shift
```

### 3. 截图与图像识别

```python
import pyautogui

# === 截图 ===
# 全屏截图
screenshot = pyautogui.screenshot()
screenshot.save('screen.png')

# 区域截图
region_shot = pyautogui.screenshot(region=(0, 0, 300, 400))
region_shot.save('region.png')

# === 图像定位 ===
# 在屏幕上查找图片
location = pyautogui.locateOnScreen('button.png')
if location:
    print(f'找到位置：{location}')
    # location 包含：left, top, width, height

# 获取中心点
center = pyautogui.center(location)
x, y = center
pyautogui.click(x, y)

# 所有匹配位置（可能有多个）
locations = pyautogui.locateAllOnScreen('icon.png')
for loc in locations:
    print(f'找到：{loc}')

# 指定置信度（需要 opencv）
location = pyautogui.locateOnScreen('button.png', confidence=0.8)

# 指定区域搜索
location = pyautogui.locateOnScreen('button.png', region=(100, 100, 500, 500))
```

### 4. 等待与超时

```python
import pyautogui

# 基本等待
pyautogui.sleep(2)                   # 等待 2 秒

# 等待图像出现（最多 10 秒）
try:
    location = pyautogui.waitForImage('start.png', timeout=10)
    print('图像出现！')
except pyautogui.ImageNotFoundException:
    print('超时未找到图像')

# 等待图像消失
pyautogui.waitUntilGone('loading.png', timeout=30)

# 全局暂停时间（每个命令后自动等待）
pyautogui.PAUSE = 0.5                # 每个命令后等待 0.5 秒
```

### 5. 安全机制

```python
import pyautogui

# FailSafe：鼠标移到左上角强制终止（默认开启）
pyautogui.FAILSAFE = True

# 自定义触发点
pyautogui.FAILSAFE_POINTS = [(0, 0), (100, 100), (0, 100)]

# 异常处理
try:
    pyautogui.moveTo(1000, 1000, duration=5)
except pyautogui.FailSafeException:
    print('触发 FailSafe，脚本已终止')
```

---

## 🛠️ 生态工具

### 1. 图像识别增强

#### OpenCV 集成
```python
import cv2
import numpy as np
import pyautogui

# 模板匹配（更精确）
def find_image_on_screen(template_path, threshold=0.9):
    screenshot = pyautogui.screenshot()
    screen_array = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    template = cv2.imread(template_path)
    
    result = cv2.matchTemplate(screen_array, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    if max_val >= threshold:
        return max_loc  # 返回左上角坐标
    return None

# 使用示例
location = find_image_on_screen('button.png')
if location:
    pyautogui.click(location)
```

#### OCR 文字识别
```python
import pytesseract
import pyautogui
from PIL import Image

# 截取区域并识别文字
def read_screen_text(region=None):
    if region:
        screenshot = pyautogui.screenshot(region=region)
    else:
        screenshot = pyautogui.screenshot()
    
    text = pytesseract.image_to_string(screenshot, lang='chi_sim+eng')
    return text

# 使用示例
text = read_screen_text(region=(100, 100, 500, 200))
print(f'识别文字：{text}')
```

### 2. 窗口管理

#### PyGetWindow（PyAutoGUI 配套）
```python
import pygetwindow as gw

# 获取所有窗口
all_windows = gw.getAllTitles()
print(all_windows)

# 获取活动窗口
active = gw.getActiveWindow()
print(f'活动窗口：{active.title}')

# 查找窗口
notepad = gw.getWindowsWithTitle('记事本')[0]

# 窗口操作
notepad.activate()           # 激活窗口
notepad.maximize()           # 最大化
notepad.minimize()           # 最小化
notepad.restore()            # 恢复
notepad.move(100, 100)       # 移动位置
notepad.resizeTo(800, 600)   # 调整大小
notepad.close()              # 关闭窗口
```

### 3. 系统信息

#### PyScreenInfo
```python
import pyscreeninfo

# 获取多显示器信息
from screeninfo import get_monitors
for m in get_monitors():
    print(f'显示器：{m.name}, 分辨率：{m.width}x{m.height}')
```

### 4. 颜色识别

```python
import pyautogui

# 获取像素颜色
pixel = pyautogui.pixel(100, 200)
print(f'RGB: {pixel}')

# 获取 RGB 值
r, g, b = pyautogui.pixel(100, 200)

# 颜色匹配
def find_color_on_screen(target_color, tolerance=10):
    width, height = pyautogui.size()
    for x in range(0, width, 5):  # 每 5 像素采样
        for y in range(0, height, 5):
            pixel = pyautogui.pixel(x, y)
            if all(abs(pixel[i] - target_color[i]) <= tolerance for i in range(3)):
                return (x, y)
    return None

# 使用示例
red_point = find_color_on_screen((255, 0, 0))
if red_point:
    pyautogui.click(red_point)
```

---

## 📚 实战示例

### 1. 自动登录脚本
```python
import pyautogui
import time

def auto_login(username, password, url):
    # 打开浏览器
    pyautogui.press('win')
    time.sleep(1)
    pyautogui.typewrite('chrome')
    pyautogui.press('enter')
    time.sleep(3)
    
    # 导航到 URL
    pyautogui.hotkey('ctrl', 'l')
    pyautogui.typewrite(url)
    pyautogui.press('enter')
    time.sleep(3)
    
    # 查找并填写表单
    username_field = pyautogui.locateOnScreen('username_field.png')
    if username_field:
        pyautogui.click(pyautogui.center(username_field))
        pyautogui.typewrite(username)
    
    password_field = pyautogui.locateOnScreen('password_field.png')
    if password_field:
        pyautogui.click(pyautogui.center(password_field))
        pyautogui.typewrite(password)
    
    # 点击登录按钮
    login_button = pyautogui.locateOnScreen('login_button.png')
    if login_button:
        pyautogui.click(pyautogui.center(login_button))

# 使用
auto_login('user@example.com', 'password123', 'https://example.com/login')
```

### 2. 批量文件处理
```python
import pyautogui
import time
import os

def batch_rename_files(folder_path, prefix):
    os.startfile(folder_path)
    time.sleep(2)
    
    # Ctrl+A 全选
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.5)
    
    # F2 重命名
    pyautogui.press('f2')
    time.sleep(0.5)
    
    # 输入新名称
    pyautogui.typewrite(f'{prefix}_')
    pyautogui.press('enter')
    
    print(f'批量重命名完成：{folder_path}')

# 使用
batch_rename_files(r'C:\Users\Photos', 'vacation')
```

### 3. 游戏自动化
```python
import pyautogui
import time
import random

def auto_clicker(interval=1.0, duration=60):
    """自动点击器"""
    print('按 Ctrl+C 停止')
    start_time = time.time()
    
    try:
        while time.time() - start_time < duration:
            pyautogui.click()
            # 随机间隔避免检测
            time.sleep(interval + random.uniform(-0.1, 0.1))
    except KeyboardInterrupt:
        print('\n停止点击器')

def auto_fish():
    """钓鱼游戏自动化"""
    print('开始自动钓鱼...')
    
    while True:
        # 等待浮标下沉（检测特定区域颜色变化）
        bobber_region = (500, 300, 100, 100)
        expected_color = (100, 150, 200)
        
        # 检测并提竿
        if detect_bite(bobber_region, expected_color):
            pyautogui.click()
            time.sleep(2)  # 等待收线

# 使用
auto_clicker(interval=0.5, duration=300)
```

### 4. 数据录入自动化
```python
import pyautogui
import time
import pandas as pd

def auto_data_entry(excel_file, web_form_image):
    """从 Excel 读取数据并填入网页表单"""
    df = pd.read_excel(excel_file)
    
    for index, row in df.iterrows():
        # 打开表单
        pyautogui.hotkey('ctrl', 'l')
        pyautogui.typewrite('https://example.com/form')
        pyautogui.press('enter')
        time.sleep(3)
        
        # 填写表单
        locate_and_type('name_field.png', str(row['Name']))
        locate_and_type('email_field.png', str(row['Email']))
        locate_and_type('phone_field.png', str(row['Phone']))
        
        # 提交
        submit_button = pyautogui.locateOnScreen('submit_button.png')
        if submit_button:
            pyautogui.click(pyautogui.center(submit_button))
        
        time.sleep(2)  # 等待提交完成
        
        print(f'完成第 {index + 1} 条记录')

def locate_and_type(image_path, text):
    field = pyautogui.locateOnScreen(image_path)
    if field:
        pyautogui.click(pyautogui.center(field))
        pyautogui.typewrite(text)

# 使用
auto_data_entry('data.xlsx', 'form_fields/')
```

### 5. 监控与告警
```python
import pyautogui
import time
from datetime import datetime

def monitor_screen_for_change(check_interval=5):
    """监控屏幕变化"""
    print('开始监控屏幕...')
    last_screenshot = pyautogui.screenshot()
    
    while True:
        time.sleep(check_interval)
        current_screenshot = pyautogui.screenshot()
        
        # 比较截图
        if screenshots_differ(last_screenshot, current_screenshot):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            current_screenshot.save(f'change_detected_{timestamp}.png')
            print(f'[{timestamp}] 检测到屏幕变化！')
            # 发送告警
            send_alert('屏幕发生变化')
        
        last_screenshot = current_screenshot

def screenshots_differ(img1, img2, threshold=10):
    """简单的截图差异检测"""
    import numpy as np
    arr1 = np.array(img1)
    arr2 = np.array(img2)
    diff = np.abs(arr1.astype(int) - arr2.astype(int))
    return np.mean(diff) > threshold

# 使用
monitor_screen_for_change()
```

---

## ⚠️ 最佳实践与注意事项

### 1. 错误处理
```python
import pyautogui
import logging

logging.basicConfig(level=logging.INFO)

def safe_click(image_path, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=0.8)
            if location:
                pyautogui.click(pyautogui.center(location))
                logging.info(f'成功点击：{image_path}')
                return True
        except Exception as e:
            logging.warning(f'尝试 {attempt + 1} 失败：{e}')
        time.sleep(1)
    
    logging.error(f'无法找到：{image_path}')
    return False
```

### 2. 性能优化
```python
# 设置全局暂停时间
pyautogui.PAUSE = 0.1

# 关闭 FailSafe（生产环境谨慎使用）
pyautogui.FAILSAFE = False

# 使用 region 参数缩小搜索范围
location = pyautogui.locateOnScreen('button.png', region=(100, 100, 500, 500))

# 降低截图质量提高速度
screenshot = pyautogui.screenshot()
screenshot.thumbnail((screenshot.width // 2, screenshot.height // 2))
```

### 3. 跨平台兼容
```python
import platform

system = platform.system()

if system == 'Darwin':  # macOS
    cmd_key = 'command'
    cancel_pos = (100, 100)
elif system == 'Windows':
    cmd_key = 'win'
    cancel_pos = (0, 0)
else:  # Linux
    cmd_key = 'super'
    cancel_pos = (0, 0)

# 使用
pyautogui.hotkey(cmd_key, 'c')
```

---

## 🔗 相关资源

### 官方文档
- [PyAutoGUI Docs](https://pyautogui.readthedocs.io/)
- [GitHub Repo](https://github.com/asweigart/pyautogui)

### 生态库
- [PyGetWindow](https://pypi.org/project/pygetwindow/) - 窗口管理
- [PyScreenInfo](https://pypi.org/project/screeninfo/) - 屏幕信息
- [PyScreeze](https://pypi.org/project/pyscreeze/) - 截图核心
- [MouseInfo](https://pypi.org/project/mouseinfo/) - 鼠标信息

### 教程
- [Automate the Boring Stuff](https://automatetheboringstuff.com/) - 免费书籍
- [Real Python PyAutoGUI](https://realpython.com/lessons/python-gui-automation-pyautogui/)

---

*最后更新：2026-03-21*
