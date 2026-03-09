from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm
from matplotlib.patches import Patch

# =========================
# 0. 输出目录
# =========================
out = Path(".")
out.mkdir(parents=True, exist_ok=True)

# =========================
# 1. 中文字体设置
# =========================
candidate_fonts = [
    "PingFang SC",         # macOS
    "Heiti SC",            # macOS
    "STHeiti",             # macOS
    "Microsoft YaHei",     # Windows
    "SimHei",              # Windows
    "Noto Sans CJK SC",    # Linux 常见
    "WenQuanYi Zen Hei",   # Linux 常见
    "Arial Unicode MS"
]

available_fonts = {f.name for f in fm.fontManager.ttflist}
chosen_font = None

for font_name in candidate_fonts:
    if font_name in available_fonts:
        chosen_font = font_name
        break

if chosen_font:
    plt.rcParams["font.sans-serif"] = [chosen_font]
    print(f"当前使用中文字体: {chosen_font}")
else:
    print("未检测到常见中文字体，请在本机安装 PingFang SC / 微软雅黑 / Noto Sans CJK SC")
    # 不强制报错，避免程序中断

plt.rcParams["axes.unicode_minus"] = False

# =========================
# 2. 数据
# =========================
questions = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
scores = [8.4, 8.7, 8.7, 8.1, 8.7, 8.0, 8.9]
# item_labels = [
#     "界面设计满意度",
#     "交互易用性",
#     "理解财务数据支持",
#     "完成分析过程支持",
#     "分析效率提升",
#     "推荐分析",
#     "视图联动"
# ]

# 维度分组
groups = {
    "系统可用性": [0, 1],
    "决策支持": [2, 3, 4],
    "分析流程": [5, 6]
}

# 配色
bar_colors = [
    "#4C78A8", "#4C78A8",      # 系统可用性
    "#72B7B2", "#72B7B2", "#72B7B2",   # 决策支持
    "#F28E2B", "#F28E2B"       # 分析流程
]

# 背景色（淡色分组区）
bg_colors = {
    "系统可用性": "#EDF3FA",
    "决策支持": "#EEF8F7",
    "分析流程": "#FFF4E8"
}

# =========================
# 3. 创建画布
# =========================
fig, ax = plt.subplots(figsize=(11.5, 5.2), dpi=180)
fig.patch.set_facecolor("white")
ax.set_facecolor("#FCFCFC")

x = np.arange(len(questions))

# =========================
# 4. 分组背景区块
# =========================
for group_name, idxs in groups.items():
    left = min(idxs) - 0.5
    right = max(idxs) + 0.5
    ax.axvspan(left, right, color=bg_colors[group_name], alpha=0.8, zorder=0)

# =========================
# 5. 柱状图
# =========================
bars = ax.bar(
    x,
    scores,
    width=0.62,
    color=bar_colors,
    edgecolor="white",
    linewidth=1.0,
    zorder=3
)

# =========================
# 6. 网格与边框样式
# =========================
ax.grid(axis="y", linestyle="--", linewidth=0.8, alpha=0.30, zorder=1)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.spines["left"].set_color("#BBBBBB")
ax.spines["bottom"].set_color("#BBBBBB")
ax.tick_params(labelsize=11)

# =========================
# 7. 坐标轴与标题
# =========================
ax.set_xticks(x)
ax.set_xticklabels(questions, fontsize=12)
ax.set_ylim(0, 10)
ax.set_ylabel("平均得分（10分制）", fontsize=12)
# ax.set_title("FinDecipher 主观实验结果", fontsize=17, pad=14)

# =========================
# 8. 柱顶数值
# =========================
for rect, score in zip(bars, scores):
    ax.text(
        rect.get_x() + rect.get_width() / 2,
        rect.get_height() + 0.10,
        f"{score:.1f}",
        ha="center",
        va="bottom",
        fontsize=11,
        color="#333333"
    )

# =========================
# 9. 每个Q下方补充描述
# =========================
# for i, label in enumerate(item_labels):
#     ax.text(
#         i,
#         -0.58,
#         label,
#         ha="center",
#         va="top",
#         fontsize=9.5,
#         color="#555555",
#         rotation=18
#     )

# =========================
# 10. 分组标题
# =========================
for group_name, idxs in groups.items():
    center = np.mean(idxs)
    ax.text(
        center,
        9.72,
        group_name,
        ha="center",
        va="center",
        fontsize=11,
        color="#444444",
        fontweight="bold"
    )

# =========================
# 11. 高亮最高分和较低项
# =========================
imax = int(np.argmax(scores))
imin = int(np.argmin(scores))

ax.annotate(
    "最高分",
    xy=(imax, scores[imax]),
    xytext=(imax, 9.35),
    ha="center",
    fontsize=10,
    color="#444444",
    arrowprops=dict(arrowstyle="->", lw=1.0, color="#666666")
)

ax.annotate(
    "相对较低",
    xy=(imin, scores[imin]),
    xytext=(imin - 0.1, 8.95),
    ha="center",
    fontsize=10,
    color="#444444",
    arrowprops=dict(arrowstyle="->", lw=1.0, color="#666666")
)

# =========================
# 12. 图例
# =========================
legend_handles = [
    Patch(facecolor="#4C78A8", label="系统可用性"),
    Patch(facecolor="#72B7B2", label="决策支持"),
    Patch(facecolor="#F28E2B", label="分析流程")
]
ax.legend(
    handles=legend_handles,
    loc="upper left",
    frameon=True,
    facecolor="white",
    edgecolor="#DDDDDD",
    fontsize=10
)

# =========================
# 13. 版式调整与保存
# =========================
plt.subplots_adjust(left=0.08, right=0.98, top=0.87, bottom=0.28)

plt.savefig("subjective_results_advanced_cn.png", dpi=300, bbox_inches="tight")
plt.show()