#!/usr/bin/env python3
"""
自动生成 blogpost README.md 目录
用法: python3 scripts/update_readme.py
"""

import os
import re
from datetime import datetime
from pathlib import Path

def extract_title(filepath):
    """从 Markdown 文件提取标题"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(2000)  # 只读前2000字符
            
        # 匹配第一个 # 标题
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            title = match.group(1).strip()
            # 截断长标题
            if len(title) > 50:
                title = title[:47] + "..."
            return title
    except:
        pass
    
    # 回退到文件名
    filename = Path(filepath).stem
    return filename.replace('-', ' ').replace('_', ' ')

def extract_date(filepath):
    """从文件名提取日期"""
    filename = Path(filepath).name
    
    # 尝试匹配 YYYY-MM-DD 格式
    match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
    if match:
        return match.group(1)
    
    # 尝试匹配 YYYY年MM月 格式
    match = re.search(r'(\d{4}年\d{2}月)', filename)
    if match:
        return match.group(1)
    
    # 从 git log 获取最后修改日期
    try:
        result = os.popen(f'git log -1 --format=%cd --date=short -- "{filepath}" 2>/dev/null').read().strip()
        if result:
            return result
    except:
        pass
    
    return "2026-02"

def categorize_file(filename):
    """根据文件名分类文章"""
    cats = []
    f = filename.lower()
    
    if any(k in f for k in ['memory', '记忆', 'mem']):
        cats.append("记忆系统")
    if any(k in f for k in ['agent', 'ai', 'carson', 'steinberger']):
        cats.append("AI技术")
    if any(k in f for k in ['seekdb', 'eywa', 'zvec', 'mongodb']):
        cats.append("数据库")
    if any(k in f for k in ['interview', '访谈', '翻译']):
        cats.append("访谈翻译")
    
    return cats[0] if cats else "其他"

GITHUB_REPO_URL = "https://github.com/kejun/blogpost/blob/main"

def main():
    os.chdir(Path(__file__).parent.parent)
    
    # 收集所有 Markdown 文件
    articles = []
    for file in sorted(os.listdir('.')):
        if file.endswith('.md') and file != 'README.md':
            title = extract_title(file)
            date = extract_date(file)
            category = categorize_file(file)
            articles.append({
                'file': file,
                'file_link': f"[{file}]({GITHUB_REPO_URL}/{file})",
                'title': title,
                'date': date,
                'category': category
            })
    
    # 按日期排序
    articles.sort(key=lambda x: x['date'], reverse=True)
    
    # 生成 README
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    readme = f"""# Blog Posts

技术文章仓库，由 OpenClaw Agent 自动维护。

## 📊 统计

- **总文章数**: {len(articles)} 篇
- **最后更新**: {now}

---

## 🗂️ 按类别浏览

| 类别 | 文章数 |
|------|--------|
| 记忆系统 | {len([a for a in articles if a['category'] == '记忆系统'])} 篇 |
| AI技术 | {len([a for a in articles if a['category'] == 'AI技术'])} 篇 |
| 数据库 | {len([a for a in articles if a['category'] == '数据库'])} 篇 |
| 访谈翻译 | {len([a for a in articles if a['category'] == '访谈翻译'])} 篇 |

---

## 📑 文章列表

| 文件名 | 标题 | 日期 | 分类 |
|--------|------|------|------|
"""
    
    for a in articles:
        readme += f"| {a['file_link']} | {a['title']} | {a['date']} | {a['category']} |\n"
    
    readme += f"""
---

## 📁 资源目录

| 目录 | 内容 |
|------|------|
| `assets/` | 图片资源 (Ryan Carson 工作照等) |
| `scripts/` | 自动化脚本 (更新目录、同步文章等) |
| `showboat-rodney/` | Showboat & Rodney Agent 工具文档 |

---

## 🔄 自动同步

添加新文章后，运行以下命令更新目录：

```bash
python3 scripts/update_readme.py
git add README.md && git commit -m "Update: 文章目录" && git push
```

---

*由 OpenClaw Agent 自动生成于 {now}*
"""
    
    with open('README.md', 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print(f"✅ README.md 已更新 - 共 {len(articles)} 篇文章")

if __name__ == '__main__':
    main()
