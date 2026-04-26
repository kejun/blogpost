import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# Chart 1: Model Performance vs Cost scatter
fig, ax = plt.subplots(figsize=(14, 9))

models = [
    ('GPT-5.5', 82.7, 35.0, '#1a73e8'),
    ('Claude Opus 4.7', 69.4, 30.0, '#d63384'),
    ('DeepSeek V4-Pro', 67.9, 5.22, '#e74c3c'),
    ('Gemini 3.1 Pro', 68.5, 14.0, '#0d6efd'),
    ('MiniMax M2.7', 57.0, 1.50, '#27ae60'),
    ('Grok 4.1 Fast', 55.0, 0.70, '#2c3e50'),
    ('Gemini 3 Flash', 52.0, 3.50, '#3498db'),
    ('DeepSeek V4-Flash', 45.0, 0.42, '#e67e22'),
]

x = [m[2] for m in models]
y = [m[1] for m in models]
labels = [m[0] for m in models]
colors = [m[3] for m in models]

scatter = ax.scatter(x, y, s=[v*8 for v in x], c=colors, alpha=0.75, edgecolors='white', linewidth=1.5, zorder=5)

for i, label in enumerate(labels):
    ax.annotate(label, (x[i], y[i]), textcoords="offset points", xytext=(8, 5), fontsize=9, fontweight='bold')

ax.set_xscale('log')
ax.set_xlabel('单次调用成本 (USD, 对数刻度)', fontsize=13, fontweight='bold')
ax.set_ylabel('Terminal-Bench 2.0 得分 (%)', fontsize=13, fontweight='bold')
ax.set_title('2026年4月前沿模型：性能 vs 成本对比', fontsize=16, fontweight='bold', pad=15)
ax.grid(True, alpha=0.3, linestyle='--')

# Add "性价比之王" annotation
ax.annotate('💰 性价比之王', (5.22, 67.9), fontsize=10, fontweight='bold',
            xytext=(-80, -30), textcoords="offset points",
            arrowprops=dict(arrowstyle='->', color='red', lw=2), color='red')

plt.tight_layout()
plt.savefig('chart_perf_cost.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 2: Timeline of model releases in April 2026
fig, ax = plt.subplots(figsize=(16, 6))

events = [
    ('4月9日', 'MiniMax M2.7\n开源发布', '#27ae60', 0.08),
    ('4月16日', 'Claude Opus 4.7\nSWE-bench 64.3%', '#d63384', 0.22),
    ('4月17日', 'Claude Design\n发布', '#d63384', 0.28),
    ('4月19日', 'Cursor $2B融资\n$500B估值', '#f39c12', 0.33),
    ('4月20日', 'Amazon $5B投资\nAnthropic', '#ff9900', 0.38),
    ('4月24日', 'GPT-5.5 发布\nTerminal-Bench 82.7%', '#1a73e8', 0.55),
    ('4月24日', 'DeepSeek V4 预览\n1.6T MoE 开源', '#e74c3c', 0.62),
    ('4月24日', 'Google $40B投资\nAnthropic', '#4285f4', 0.68),
    ('4月25日', 'Anthropic Project Deal\nAgent电商实验', '#9b59b6', 0.75),
    ('4月30日', 'StrictlyVC 2026\nSF举办', '#34495e', 0.88),
]

y_pos = 0.5
for date, desc, color, x_pos in events:
    ax.plot(x_pos, y_pos, 'o', color=color, markersize=14, zorder=5)
    ax.plot([0.05, x_pos], [y_pos, y_pos], color=color, alpha=0.3, linewidth=1)
    ax.text(x_pos, y_pos + 0.12, date, ha='center', fontsize=8, fontweight='bold', color=color)
    ax.text(x_pos, y_pos - 0.12, desc, ha='center', fontsize=7.5, color='#333')

ax.set_xlim(0, 1)
ax.set_ylim(0.2, 0.8)
ax.axis('off')
ax.set_title('2026年4月 AI 模型"雪崩"：9天5款前沿模型密集发布', fontsize=16, fontweight='bold', pad=15)

# Add timeline line
ax.plot([0.05, 0.95], [0.5, 0.5], '#333', linewidth=2, alpha=0.4)

plt.tight_layout()
plt.savefig('timeline_april_2026.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 3: Investment flow diagram
fig, ax = plt.subplots(figsize=(14, 8))

investors = ['Google', 'Amazon', 'SpaceX/Cursor', 'Visa', 'Cloudflare']
amounts = [400, 50, 600, 0, 0]
targets = ['Anthropic', 'Anthropic', 'Anysphere', '基础设施', 'Agent Cloud']
colors_i = ['#4285f4', '#ff9900', '#e74c3c', '#1a73e8', '#f48120']

y_pos = np.arange(len(investors))
bars = ax.barh(y_pos, amounts, color=colors_i, alpha=0.8, edgecolor='white', linewidth=2, height=0.6)

for i, (inv, amt, tgt, c) in enumerate(zip(investors, amounts, targets, colors_i)):
    ax.text(amt + 15, i, f'${amt}B → {tgt}', va='center', fontsize=11, fontweight='bold')
    ax.text(-20, i, inv, va='center', ha='right', fontsize=12, fontweight='bold')

ax.set_xlim(-100, 750)
ax.set_yticks([])
ax.axis('off')
ax.set_title('2026年4月 AI 基础设施投资流向', fontsize=16, fontweight='bold', pad=15)

# Add annotation
ax.text(0.5, -0.15, '数据来源：公开报道 | 单位：十亿美元', transform=ax.transAxes, 
        ha='center', fontsize=9, color='#666', style='italic')

plt.tight_layout()
plt.savefig('investment_flow.png', dpi=200, bbox_inches='tight')
plt.close()

print("All charts generated!")
