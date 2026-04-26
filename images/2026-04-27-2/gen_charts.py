import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Chart 1: 1.6% vs 98.4% pie chart
fig, ax = plt.subplots(figsize=(10, 8))
sizes = [1.6, 98.4]
labels = ['AI Decision Logic (1.6%)', 'Infrastructure (98.4%)']
colors = ['#e74c3c', '#3498db']
explode = (0.05, 0)
ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
       shadow=False, startangle=90, textprops={'fontsize': 14})
ax.set_title('Claude Code Codebase Composition', fontsize=18, fontweight='bold', pad=20)
plt.tight_layout()
plt.savefig('pie_1_6_vs_98_4.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 2: 7 safety layers
fig, ax = plt.subplots(figsize=(12, 8))
layers = ['Tool Pre-filtering', 'Deny-first Rules', 'Permission Modes',
          'ML Classifier', 'Shell Sandboxing', 'Non-restoration on Resume',
          'Hook Interception']
y = np.arange(len(layers))
colors = plt.cm.RdYlGn(np.linspace(0.15, 0.85, 7))
bars = ax.barh(y, [7,6,5,4,3,2,1], color=colors, edgecolor='white', linewidth=2, height=0.7)
ax.set_yticks(y)
ax.set_yticklabels(layers, fontsize=11)
ax.set_xlim(0, 8)
for i, layer in enumerate(layers):
    ax.text(7.2, i, f'Layer {7-i}', va='center', fontsize=10, fontweight='bold')
ax.set_xlabel('Defense Depth', fontsize=12)
ax.set_title('7 Independent Safety Layers in Claude Code', fontsize=16, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig('seven_safety_layers.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 3: 5-stage compaction pipeline
fig, ax = plt.subplots(figsize=(14, 7))
stages = ['Budget\nReduction', 'Snip\n(History Trim)', 'Microcompact\n(Cache-aware)', 'Context\nCollapse', 'Auto-Compact\n(Full Summary)']
costs = [1, 2, 3, 4, 5]
disruptions = [0.1, 0.3, 0.5, 0.7, 1.0]
x = np.arange(len(stages))
width = 0.35
bars1 = ax.bar(x - width/2, costs, width, label='Implementation Cost', color='#3498db', alpha=0.8)
bars2 = ax.bar(x + width/2, [d*5 for d in disruptions], width, label='Context Disruption', color='#e74c3c', alpha=0.8)
ax.set_xticks(x)
ax.set_xticklabels(stages, fontsize=10)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('5-Stage Graduated Compaction Pipeline', fontsize=16, fontweight='bold', pad=15)
ax.legend(fontsize=12)
for i, stage in enumerate(stages):
    ax.text(i, -0.2, f'Stage {i+1}', ha='center', fontsize=9, color='#666')
ax.set_ylim(0, 6)
plt.tight_layout()
plt.savefig('five_stage_compaction.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 4: Architecture layers
fig, ax = plt.subplots(figsize=(12, 8))
layers = [
    ('Surface', 'CLI, Headless, SDK, IDE\n(React + Ink terminal UI)', '#2c3e50'),
    ('Core', 'queryLoop, 5-stage Compaction\nSubagent Spawning', '#2980b9'),
    ('Safety/Action', '7 Perm Modes, ML Classifier\n27 Hooks, Tool Pool, Shell Sandbox', '#27ae60'),
    ('State', 'JSONL Transcripts, CLAUDE.md\nAuto-memory, Sidechain Files', '#8e44ad'),
    ('Backend', 'Shell Execution, MCP (7 transports)\n42 Tool Subdirectories', '#c0392b'),
]
for i, (name, desc, color) in enumerate(layers):
    y = 4 - i
    ax.add_patch(plt.Rectangle((0.1, y - 0.35), 0.6, 0.7, facecolor=color, edgecolor='white', linewidth=2, alpha=0.9, zorder=2))
    ax.text(0.4, y, name, ha='center', va='center', fontsize=14, fontweight='bold', color='white')
    ax.text(0.8, y, desc, ha='left', va='center', fontsize=10, color='#333')
    if i < len(layers) - 1:
        ax.annotate('', xy=(0.4, y - 0.35), xytext=(0.4, y - 1.35),
                    arrowprops=dict(arrowstyle='->', color='#999', lw=2))
ax.set_xlim(0, 1.3)
ax.set_ylim(-1, 5)
ax.axis('off')
ax.set_title('Claude Code 5-Layer Architecture', fontsize=16, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig('five_layer_architecture.png', dpi=200, bbox_inches='tight')
plt.close()

# Chart 5: 4 extension mechanisms by context cost
fig, ax = plt.subplots(figsize=(12, 7))
mechanisms = ['Hooks', 'Skills', 'Plugins', 'MCP Servers']
costs = [0, 1, 2, 3]
descriptions = ['27 events, 4 exec types\nZero context cost', 'SKILL.md, 15+ YAML fields\nLow context cost', '10 component types\nMedium context cost', '7 transport types\nHigh context cost']
colors = ['#27ae60', '#2ecc71', '#f39c12', '#e74c3c']
bars = ax.bar(mechanisms, costs, color=colors, width=0.5, edgecolor='white', linewidth=2)
for i, (m, d) in enumerate(zip(mechanisms, descriptions)):
    ax.text(i, costs[i] + 0.15, d, ha='center', fontsize=9, color='#333')
ax.set_ylabel('Context Cost (relative)', fontsize=12)
ax.set_title('4 Extension Mechanisms at Graduated Context Costs', fontsize=16, fontweight='bold', pad=15)
ax.set_ylim(0, 5)
plt.tight_layout()
plt.savefig('four_extension_mechanisms.png', dpi=200, bbox_inches='tight')
plt.close()

print("All charts generated!")
