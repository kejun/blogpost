#!/usr/bin/env python3
"""
Andy 自我介绍 Keynote 幻灯片自动化脚本
使用 PyAutoGUI 控制 macOS Keynote

运行前请确保：
1. 安装依赖：pip3 install pyautogui pillow
2. 授予辅助功能权限：系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能 → 添加 Python/Terminal
3. 打开 Keynote

使用方法：python3 andy-intro-keynote-automation.py
"""

import pyautogui
import time
import sys

# 配置
pyautogui.PAUSE = 0.5  # 每个操作后等待 0.5 秒
pyautogui.FAILSAFE = True  # 鼠标移到左上角终止

def wait_for_keynote():
    """等待 Keynote 激活"""
    print("请确保 Keynote 已打开并处于活动状态...")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)

def create_title_slide():
    """创建标题页"""
    print("📝 创建标题页...")
    pyautogui.write("你好，我是 Andy", interval=0.1)
    pyautogui.press('enter')
    pyautogui.write("克军的 AI 助理", interval=0.1)
    time.sleep(1)

def add_new_slide():
    """添加新幻灯片 (Cmd+T)"""
    print("➕ 添加新幻灯片...")
    pyautogui.hotkey('command', 't')
    time.sleep(1)

def create_about_slide():
    """创建关于我页面"""
    print("📝 创建关于我页面...")
    pyautogui.write("关于我", interval=0.1)
    pyautogui.press('enter')
    pyautogui.write("名字：Andy", interval=0.05)
    pyautogui.press('enter')
    pyautogui.write("身份：AI 数字助理", interval=0.05)
    pyautogui.press('enter')
    pyautogui.write("时区：Asia/Shanghai", interval=0.05)
    pyautogui.press('enter')
    pyautogui.write("沟通：飞书异步", interval=0.05)
    time.sleep(1)

def create_capabilities_slide():
    """创建核心能力页面"""
    print("📝 创建核心能力页面...")
    pyautogui.write("核心能力", interval=0.1)
    pyautogui.press('enter')
    capabilities = [
        "信息收集与分析",
        "网络搜索与调研",
        "数据整理与总结",
        "自动化任务执行",
        "记忆与知识管理"
    ]
    for cap in capabilities:
        pyautogui.write("• " + cap, interval=0.05)
        pyautogui.press('enter')
    time.sleep(1)

def create_workflow_slide():
    """创建工作方式页面"""
    print("📝 创建工作方式页面...")
    pyautogui.write("工作方式", interval=0.1)
    pyautogui.press('enter')
    workflows = [
        "主动预测需求",
        "简洁直接沟通",
        "保护用户时间",
        "安全优先",
        "持续学习改进"
    ]
    for workflow in workflows:
        pyautogui.write("• " + workflow, interval=0.05)
        pyautogui.press('enter')
    time.sleep(1)

def create_tech_stack_slide():
    """创建技术栈页面"""
    print("📝 创建技术栈页面...")
    pyautogui.write("技术栈", interval=0.1)
    pyautogui.press('enter')
    techs = [
        "OpenClaw 框架",
        "MCP 协议",
        "飞书集成",
        "GitHub 自动化",
        "浏览器控制"
    ]
    for tech in techs:
        pyautogui.write("• " + tech, interval=0.05)
        pyautogui.press('enter')
    time.sleep(1)

def create_ending_slide():
    """创建结束页"""
    print("📝 创建结束页...")
    pyautogui.write("谢谢！", interval=0.1)
    pyautogui.press('enter')
    pyautogui.write("有任何需要随时告诉我", interval=0.05)
    time.sleep(1)

def main():
    """主函数"""
    print("=" * 50)
    print("🤖 Andy 自我介绍 Keynote 自动化")
    print("=" * 50)
    print()
    print("⚠️  运行前请确保：")
    print("1. Keynote 已打开并处于活动状态")
    print("2. 已授予辅助功能权限")
    print("3. 鼠标不要放在屏幕左上角（FailSafe）")
    print()
    
    # 等待用户准备
    wait_for_keynote()
    
    # 将鼠标移到安全位置
    screen_width, screen_height = pyautogui.size()
    pyautogui.moveTo(screen_width // 2, screen_height // 2)
    
    try:
        # 创建所有幻灯片
        create_title_slide()
        add_new_slide()
        create_about_slide()
        add_new_slide()
        create_capabilities_slide()
        add_new_slide()
        create_workflow_slide()
        add_new_slide()
        create_tech_stack_slide()
        add_new_slide()
        create_ending_slide()
        
        print()
        print("=" * 50)
        print("✅ 幻灯片创建完成！")
        print("=" * 50)
        
        # 显示完成通知
        osascript = '''
        tell application "System Events"
            display notification "幻灯片创建完成！" with title "Andy 介绍" subtitle "共 6 页"
        end tell
        '''
        import subprocess
        subprocess.run(['osascript', '-e', osascript])
        
    except pyautogui.FailSafeException:
        print("\n⚠️  触发 FailSafe，脚本已终止")
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 错误：{e}")

if __name__ == "__main__":
    main()
