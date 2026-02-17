#!/usr/bin/env python3
"""
Showboat & Rodney 包装器
用于在 Python 代码中方便地调用这些工具
"""

import subprocess
import os
import tempfile
from pathlib import Path
from typing import Optional, List

class Showboat:
    """Showboat 文档生成器包装"""
    
    def __init__(self, doc_path: str):
        self.doc_path = doc_path
        self.sections = []
    
    def _run(self, *args) -> str:
        """运行 showboat 命令"""
        cmd = ["uvx", "showboat"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.path.dirname(self.doc_path) or "."
        )
        return result.stdout + result.stderr
    
    def init(self, title: str) -> str:
        """初始化文档"""
        return self._run("init", self.doc_path, title)
    
    def note(self, text: str) -> str:
        """添加说明文字"""
        self.sections.append(("note", text))
        return self._run("note", self.doc_path, text)
    
    def exec(self, language: str, code: str) -> str:
        """执行代码并捕获输出"""
        self.sections.append(("exec", language, code))
        return self._run("exec", self.doc_path, language, code)
    
    def image(self, command: str) -> str:
        """捕获截图"""
        self.sections.append(("image", command))
        return self._run("image", self.doc_path, command)
    
    def pop(self) -> str:
        """撤销最后一节"""
        if self.sections:
            self.sections.pop()
        return self._run("pop", self.doc_path)
    
    def verify(self) -> str:
        """验证文档"""
        return self._run("verify", self.doc_path)
    
    def read(self) -> str:
        """读取文档内容"""
        if os.path.exists(self.doc_path):
            with open(self.doc_path, 'r') as f:
                return f.read()
        return ""


class Rodney:
    """Rodney 浏览器自动化包装"""
    
    def __init__(self):
        self._started = False
    
    def _run(self, *args) -> str:
        """运行 rodney 命令"""
        cmd = ["uvx", "rodney"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout + result.stderr
    
    def start(self) -> str:
        """启动 Chrome"""
        result = self._run("start")
        self._started = True
        return result
    
    def stop(self) -> str:
        """停止 Chrome"""
        result = self._run("stop")
        self._started = False
        return result
    
    def open(self, url: str) -> str:
        """打开网页"""
        return self._run("open", url)
    
    def click(self, selector: str) -> str:
        """点击元素"""
        return self._run("click", selector)
    
    def js(self, script: str) -> str:
        """执行 JavaScript"""
        return self._run("js", script)
    
    def screenshot(self, output_path: str) -> str:
        """截图"""
        return self._run("screenshot", output_path)
    
    def axe(self, url: Optional[str] = None) -> str:
        """无障碍审计"""
        if url:
            return self._run("axe", url)
        return self._run("axe")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        if self._started:
            self.stop()


def create_demo(doc_path: str, title: str, steps: List[dict]) -> str:
    """
    快速创建演示文档
    
    Args:
        doc_path: 文档路径
        title: 文档标题
        steps: 步骤列表，每项是 dict: {type: 'note'|'exec'|'image', ...}
    
    Returns:
        文档内容
    """
    showboat = Showboat(doc_path)
    showboat.init(title)
    
    for step in steps:
        step_type = step.get('type')
        if step_type == 'note':
            showboat.note(step['text'])
        elif step_type == 'exec':
            showboat.exec(step.get('lang', 'bash'), step['code'])
        elif step_type == 'image':
            showboat.image(step['command'])
    
    return showboat.read()


def demo_with_browser(doc_path: str, url: str, actions: List[dict]) -> str:
    """
    使用 Rodney 浏览器自动化创建演示
    
    Args:
        doc_path: 文档路径
        url: 起始 URL
        actions: 浏览器操作列表
    
    Returns:
        文档内容
    """
    showboat = Showboat(doc_path)
    showboat.init(f"Browser Demo: {url}")
    showboat.note(f"演示网页: {url}")
    
    with Rodney() as rodney:
        rodney.open(url)
        showboat.note("打开首页")
        
        for i, action in enumerate(actions, 1):
            action_type = action.get('type')
            
            if action_type == 'click':
                rodney.click(action['selector'])
                showboat.note(f"点击: {action.get('desc', action['selector'])}")
            
            elif action_type == 'screenshot':
                path = action.get('path', f'/tmp/screenshot_{i}.png')
                rodney.screenshot(path)
                showboat.image(f"echo {path}")
                showboat.note(f"截图: {action.get('desc', f'第{i}张截图')}")
            
            elif action_type == 'js':
                result = rodney.js(action['script'])
                showboat.note(f"执行 JS: {action.get('desc', action['script'])}")
                showboat.exec('javascript', f"// Result: {result[:100]}")
    
    return showboat.read()


if __name__ == "__main__":
    # 测试示例
    print("🧪 测试 Showboat & Rodney 包装器")
    
    # 测试 Showboat
    print("\n1. 测试 Showboat:")
    showboat = Showboat("/tmp/test_demo.md")
    print(showboat.init("测试文档"))
    print(showboat.note("这是一个测试"))
    print(showboat.exec("bash", "echo 'Hello from Showboat'"))
    
    content = showboat.read()
    print(f"\n生成的文档 ({len(content)} 字符):")
    print(content[:500])
    
    print("\n✅ 测试完成")
    print("\n使用示例:")
    print("  from demo_tools import Showboat, Rodney, create_demo")
    print("  showboat = Showboat('demo.md')")
    print("  showboat.init('My Project')")
    print("  showboat.exec('bash', 'ls -la')")
