import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Chart 1: 98.4% vs 1.6% pie chart
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

labels = ['Infrastructure (98.4%)', 'AI Logic (1.6%)']
sizes = [98.4, 1.6]
colors = ['#3498db', '#e74c3c']
explode = (0.05, 0.1)

ax1.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
        startangle=90, textprops={'fontsize': 12})
ax1.set_title('Claude Code Codebase Composition', fontsize=15, fontweight='bold')

# Chart 2: 7 safety layers
layers = ['1. Tool Pre-filtering', '2. Deny-first Rules', '3. Permission Modes',
          '4. ML Classifier', '5. Shell Sandbox', '6. No Resume Restore', '7. Hook Interception']
depths = list(range(7, 0, -1))
bars = ax2.barh(layers, depths, color=plt.cm.RdYlGn(np.linspace(0.1, 0.9, 7)), edgecolor='white', linewidth=2)
ax2.set_xlim(0, 8)
for i, d in enumerate(depths):
    ax2.text(d + 0.1, i, str(d), va='center', fontsize=11, fontweight='bold')
ax2.set_title('7 Independent Safety Layers', fontsize=15, fontweight='bold')
ax2.set_xlabel('Layer Depth')

plt.tight_layout()
plt.savefig('claude_code_1_6.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 3: 5-stage compaction pipeline
fig, ax = plt.subplots(figsize=(14, 6))

stages = ['Budget\nReduction', 'Snip\n(History Trim)', 'Microcompact\n(Cache-aware)', 'Context\nCollapse', 'Auto-Compact\n(Full Summary)']
costs = [1, 2, 3, 4, 5]
disruptions = [0.1, 0.3, 0.5, 0.7, 1.0]

x = np.arange(len(stages))
bar1 = ax.bar(x - 0.2, costs, 0.4, label='Implementation Cost', color='#3498db', alpha=0.8)
bar2 = ax.bar(x + 0.2, [d * 5 for d in disruptions], 0.4, label='Context Disruption', color='#e74c3c', alpha=0.8)

ax.set_xticks(x)
ax.set_xticklabels(stages, fontsize=9)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('5-Stage Graduated Compaction Pipeline', fontsize=15, fontweight='bold')
ax.legend()
ax.set_ylim(0, 6)

for i, s in enumerate(stages):
    ax.text(i, -0.3, f'Cheapest → Most Expensive', ha='center', fontsize=8, color='#666')

plt.tight_layout()
plt.savefig('compaction_pipeline.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 4: Architecture layers
fig, ax = plt.subplots(figsize=(14, 8))

layer_data = [
    ('Surface', 'CLI, Headless, SDK, IDE\n(React + Ink)', '#2c3e50'),
    ('Core', 'queryLoop, 5-stage Compaction,\nSubagent Spawning', '#2980b9'),
    ('Safety/Action', '7 Perm Modes, ML Classifier,\n27 Hooks, Tool Pool', '#27ae60'),
    ('State', 'JSONL Transcripts, CLAUDE.md,\nAuto-memory, Sidechains', '#8e44ad'),
    ('Backend', 'Shell, MCP (7 transports),\n42 Tool Subdirs', '#c0392b'),
]

for i, (name, desc, color) in enumerate(layer_data):
    y = 4 - i
    rect = mpatches.FancyBboxPatch((0.1, y - 0.3), 0.7, 0.6, boxstyle="round,pad=0.05",
                                     facecolor=color, edgecolor='white', alpha=0.9)
    ax.add_patch(rect)
    ax.text(0.45, y, name, ha='center', va='center', fontsize=13, fontweight='bold', color='white')
    ax.text(0.85, y, desc, ha='left', va='center', fontsize=10, color='#333')
    if i < len(layer_data) - 1:
        ax.annotate('', (0.45, y - 0.3), (0.45, y - 1.3),
                    arrowprops=dict(arrowstyle='->', color='#999', lw=2))

ax.set_xlim(0, 1.2)
ax.set_ylim(-1, 5)
ax.axis('off')
ax.set_title('Claude Code 5-Layer Architecture', fontsize=15, fontweight='bold', pad=15)

plt.tight_layout()
plt.savefig('architecture_layers.png', dpi=200, bbox_inches='tight')
plt.close()

print("All Claude Code charts generated!")
