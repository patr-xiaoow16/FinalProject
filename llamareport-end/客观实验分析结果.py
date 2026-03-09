# from pathlib import Path
# import matplotlib.pyplot as plt
# import numpy as np
# from matplotlib import font_manager as fm

# # =========================
# # 输出路径
# # =========================
# out = Path(".")
# out.mkdir(parents=True, exist_ok=True)

# # =========================
# # 中文字体设置
# # =========================
# candidate_fonts = [
#     "PingFang SC",
#     "Heiti SC",
#     "STHeiti",
#     "SimHei",
#     "Microsoft YaHei",
#     "Noto Sans CJK SC",
#     "Arial Unicode MS"
# ]

# available_fonts = {f.name for f in fm.fontManager.ttflist}

# chosen_font = None
# for f in candidate_fonts:
#     if f in available_fonts:
#         chosen_font = f
#         break

# if chosen_font:
#     plt.rcParams["font.sans-serif"] = [chosen_font]
# else:
#     print("⚠ 未找到中文字体，可能出现乱码")

# plt.rcParams["axes.unicode_minus"] = False


# # =========================
# # 数据
# # =========================

# questions = ["Q1", "Q2", "Q3", "Q4"]
# exp = [90, 60, 70, 70]
# ctrl = [60, 40, 60, 40]

# groups = ["实验组", "对照组"]
# avg_scores = [72.5, 50.0]

# indicators = ["ROE变化", "净息差", "同时选择两者"]
# exp_q5 = [80, 80, 70]
# ctrl_q5 = [50, 20, 10]


# # =========================
# # 配色
# # =========================

# # 图1 蓝绿
# c1_exp = "#4C78A8"
# c1_ctrl = "#72B7B2"

# # 图2 紫红
# c2 = ["#B279A2", "#E45756"]

# # 图3 橙黄
# c3_exp = "#F28E2B"
# c3_ctrl = "#EDC948"


# # =========================
# # 创建画布
# # =========================

# fig, axes = plt.subplots(
#     1,
#     3,
#     figsize=(18, 4.2),   # 高度缩小
#     dpi=150
# )

# fig.patch.set_facecolor("white")


# # =========================
# # 通用样式函数
# # =========================

# def beautify_axis(ax):

#     ax.set_facecolor("#FAFAFA")

#     ax.grid(
#         axis="y",
#         linestyle="--",
#         linewidth=0.7,
#         alpha=0.35
#     )

#     ax.spines["top"].set_visible(False)
#     ax.spines["right"].set_visible(False)

#     ax.spines["left"].set_color("#BBBBBB")
#     ax.spines["bottom"].set_color("#BBBBBB")

#     ax.tick_params(labelsize=10)


# def add_labels(ax, bars, fmt="{:.0f}%"):

#     for b in bars:

#         h = b.get_height()

#         ax.text(
#             b.get_x() + b.get_width()/2,
#             h + 2,
#             fmt.format(h),
#             ha="center",
#             va="bottom",
#             fontsize=9,
#             color="#333333"
#         )


# # =========================
# # 子图1：Q1-Q4 正确率
# # =========================

# ax = axes[0]

# x = np.arange(len(questions))
# width = 0.36

# bars1 = ax.bar(
#     x - width/2,
#     exp,
#     width,
#     label="实验组（FinDecipher）",
#     color=c1_exp
# )

# bars2 = ax.bar(
#     x + width/2,
#     ctrl,
#     width,
#     label="对照组（DeepSeek）",
#     color=c1_ctrl
# )

# ax.set_xticks(x)
# ax.set_xticklabels(questions)

# ax.set_ylim(0, 100)

# ax.set_ylabel("正确率（%）", fontsize=11)

# ax.set_title(
#     "（a）客观题 Q1–Q4 正确率对比",
#     fontsize=12,
#     pad=10
# )

# ax.legend(
#     frameon=True,
#     facecolor="white",
#     edgecolor="#DDDDDD",
#     fontsize=9
# )

# beautify_axis(ax)

# add_labels(ax, bars1)
# add_labels(ax, bars2)


# # =========================
# # 子图2：平均正确率
# # =========================

# ax = axes[1]

# x2 = np.arange(len(groups))

# bars = ax.bar(
#     x2,
#     avg_scores,
#     width=0.55,
#     color=c2
# )

# ax.set_xticks(x2)
# ax.set_xticklabels(groups)

# ax.set_ylim(0, 100)

# ax.set_ylabel("平均正确率（%）", fontsize=11)

# ax.set_title(
#     "（b）客观题平均正确率",
#     fontsize=12,
#     pad=10
# )

# beautify_axis(ax)

# for b in bars:

#     h = b.get_height()

#     ax.text(
#         b.get_x() + b.get_width()/2,
#         h + 2,
#         f"{h:.1f}%",
#         ha="center",
#         va="bottom",
#         fontsize=10
#     )


# # =========================
# # 子图3：关键依据选择
# # =========================

# ax = axes[2]

# x3 = np.arange(len(indicators))

# bars3 = ax.bar(
#     x3 - width/2,
#     exp_q5,
#     width,
#     label="实验组",
#     color=c3_exp
# )

# bars4 = ax.bar(
#     x3 + width/2,
#     ctrl_q5,
#     width,
#     label="对照组",
#     color=c3_ctrl
# )

# ax.set_xticks(x3)
# ax.set_xticklabels(indicators)

# ax.set_ylim(0, 100)

# ax.set_ylabel("选择比例（%）", fontsize=11)

# ax.set_title(
#     "（c）关键分析依据选择情况",
#     fontsize=12,
#     pad=10
# )

# ax.legend(
#     frameon=True,
#     facecolor="white",
#     edgecolor="#DDDDDD",
#     fontsize=9
# )

# beautify_axis(ax)

# add_labels(ax, bars3)
# add_labels(ax, bars4)


# # =========================
# # 总标题
# # =========================

# # fig.suptitle(
# #     "实验组与对照组在客观实验任务中的表现对比",
# #     fontsize=14,
# #     y=0.98
# # )


# # =========================
# # 子图间距
# # =========================

# plt.subplots_adjust(
#     left=0.05,
#     right=0.98,
#     top=0.90,
#     bottom=0.12,
#     wspace=0.30
# )


# # =========================
# # 保存
# # =========================

# plt.savefig(
#     "user_study_results_advanced.png",
#     dpi=300,
#     bbox_inches="tight"
# )

# plt.show()



from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager as fm

# =========================
# 输出路径
# =========================
out = Path(".")
out.mkdir(parents=True, exist_ok=True)

# =========================
# 中文字体设置
# =========================
candidate_fonts = [
    "PingFang SC",
    "Heiti SC",
    "STHeiti",
    "SimHei",
    "Microsoft YaHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS"
]

available_fonts = {f.name for f in fm.fontManager.ttflist}
chosen_font = None
for f in candidate_fonts:
    if f in available_fonts:
        chosen_font = f
        break

if chosen_font:
    plt.rcParams["font.sans-serif"] = [chosen_font]
else:
    print("⚠ 未找到中文字体，可能出现乱码")

plt.rcParams["axes.unicode_minus"] = False

# =========================
# 数据
# =========================
questions = ["Q1", "Q2", "Q3", "Q4"]
exp = [90, 60, 70, 70]
ctrl = [60, 40, 60, 40]

groups = ["实验组", "对照组"]
avg_scores = [72.5, 50.0]

indicators = ["ROE变化", "净息差", "同时选择两者"]
exp_q5 = [80, 80, 70]
ctrl_q5 = [50, 20, 10]

# 已知显著性结果
p_avg = 0.089
p_q5_nim = 0.023
p_q5_both = 0.020

# =========================
# 配色
# =========================
c1_exp = "#4C78A8"
c1_ctrl = "#72B7B2"

c2 = ["#B279A2", "#E45756"]

c3_exp = "#F28E2B"
c3_ctrl = "#EDC948"

# =========================
# 创建画布
# =========================
fig, axes = plt.subplots(
    1, 3,
    figsize=(18, 4.4),
    dpi=150
)
fig.patch.set_facecolor("white")

# =========================
# 通用样式
# =========================
def beautify_axis(ax):
    ax.set_facecolor("#FAFAFA")
    ax.grid(axis="y", linestyle="--", linewidth=0.7, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#BBBBBB")
    ax.spines["bottom"].set_color("#BBBBBB")
    ax.tick_params(labelsize=10)

def add_labels(ax, bars, fmt="{:.0f}%"):
    for b in bars:
        h = b.get_height()
        ax.text(
            b.get_x() + b.get_width() / 2,
            h + 1.5,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=9,
            color="#333333"
        )

def p_to_text(p):
    if p < 0.001:
        return "***"
    elif p < 0.01:
        return "**"
    elif p < 0.05:
        return "*"
    elif p < 0.10:
        return "†"
    else:
        return "n.s."

def add_sig_bracket(ax, x1, x2, y, h, p, show_p=True, fontsize=9):
    """
    在两个柱子之间添加显著性括号
    x1, x2: 两个柱子的中心位置
    y: 括号底部高度
    h: 括号高度
    p: p值
    """
    ax.plot([x1, x1, x2, x2], [y, y+h, y+h, y], lw=1.2, c="#444444")
    label = p_to_text(p)
    if show_p:
        label = f"{label}  p={p:.3f}"
    ax.text(
        (x1 + x2) / 2,
        y + h + 1.0,
        label,
        ha="center",
        va="bottom",
        fontsize=fontsize,
        color="#333333"
    )

# =========================
# 子图1：Q1-Q4 正确率
# =========================
ax = axes[0]
x = np.arange(len(questions))
width = 0.36

bars1 = ax.bar(
    x - width/2, exp, width,
    label="实验组（FinDecipher）",
    color=c1_exp
)
bars2 = ax.bar(
    x + width/2, ctrl, width,
    label="对照组（DeepSeek）",
    color=c1_ctrl
)

ax.set_xticks(x)
ax.set_xticklabels(questions)
ax.set_ylim(0, 105)
ax.set_ylabel("正确率（%）", fontsize=11)
ax.set_title("（a）客观题 Q1–Q4 正确率对比", fontsize=12, pad=10)
ax.legend(frameon=True, facecolor="white", edgecolor="#DDDDDD", fontsize=9)

beautify_axis(ax)
add_labels(ax, bars1)
add_labels(ax, bars2)

# 如果你后续有每道题的p值，可以在这里继续加
# 例如：
# add_sig_bracket(ax, x[0]-width/2, x[0]+width/2, y=94, h=2, p=0.12)

# =========================
# 子图2：平均正确率
# =========================
ax = axes[1]
x2 = np.arange(len(groups))

bars = ax.bar(
    x2, avg_scores, width=0.55,
    color=c2
)

ax.set_xticks(x2)
ax.set_xticklabels(groups)
ax.set_ylim(0, 105)
ax.set_ylabel("平均正确率（%）", fontsize=11)
ax.set_title("（b）客观题平均正确率", fontsize=12, pad=10)

beautify_axis(ax)

for b in bars:
    h = b.get_height()
    ax.text(
        b.get_x() + b.get_width()/2,
        h + 1.5,
        f"{h:.1f}%",
        ha="center",
        va="bottom",
        fontsize=10,
        color="#333333"
    )

# 平均正确率显著性
add_sig_bracket(
    ax,
    x1=x2[0],
    x2=x2[1],
    y=max(avg_scores) + 6,
    h=2.0,
    p=p_avg,
    show_p=True
)

# =========================
# 子图3：Q5关键依据选择
# =========================
ax = axes[2]
x3 = np.arange(len(indicators))

bars3 = ax.bar(
    x3 - width/2, exp_q5, width,
    label="实验组",
    color=c3_exp
)
bars4 = ax.bar(
    x3 + width/2, ctrl_q5, width,
    label="对照组",
    color=c3_ctrl
)

ax.set_xticks(x3)
ax.set_xticklabels(indicators)
ax.set_ylim(0, 110)
ax.set_ylabel("选择比例（%）", fontsize=11)
ax.set_title("（c）关键分析依据选择情况", fontsize=12, pad=10)
ax.legend(frameon=True, facecolor="white", edgecolor="#DDDDDD", fontsize=9)

beautify_axis(ax)
add_labels(ax, bars3)
add_labels(ax, bars4)

# Q5：净息差
add_sig_bracket(
    ax,
    x1=x3[1] - width/2,
    x2=x3[1] + width/2,
    y=max(exp_q5[1], ctrl_q5[1]) + 6,
    h=2.0,
    p=p_q5_nim,
    show_p=True
)

# Q5：同时选择两者
add_sig_bracket(
    ax,
    x1=x3[2] - width/2,
    x2=x3[2] + width/2,
    y=max(exp_q5[2], ctrl_q5[2]) + 12,
    h=2.0,
    p=p_q5_both,
    show_p=True
)

# =========================
# 总标题
# =========================
# fig.suptitle(
#     "实验组与对照组在客观实验任务中的表现对比",
#     fontsize=14,
#     y=0.98
# )

# =========================
# 子图间距
# =========================
plt.subplots_adjust(
    left=0.05,
    right=0.98,
    top=0.88,
    bottom=0.14,
    wspace=0.30
)

# =========================
# 保存与显示
# =========================
plt.savefig(
    "user_study_results_with_significance.png",
    dpi=300,
    bbox_inches="tight"
)
plt.show()