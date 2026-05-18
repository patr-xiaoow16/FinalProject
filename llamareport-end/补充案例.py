"""
苏宁易购 2024 年度财务分析可视化
对应 FinDecipher 论文案例 7.1.4 节
运行环境：Python 3.8+，需安装 matplotlib / numpy
    pip install matplotlib numpy
"""

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as FancyBboxPatch
import numpy as np

# ── 全局字体设置（优先使用系统中文字体）─────────────────────────────────────
import matplotlib.font_manager as fm

def _find_cjk_font():
    """尝试找到系统中可用的中文字体。"""
    candidates = [
        "PingFang SC", "Heiti TC", "Hiragino Sans GB",
        "Microsoft YaHei", "SimHei", "WenQuanYi Micro Hei",
        "Noto Sans CJK SC", "Source Han Sans CN",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            return name
    return None

_cjk = _find_cjk_font()
if _cjk:
    plt.rcParams["font.family"] = _cjk
else:
    # 找不到中文字体时退回英文，并给出提示
    print("[WARNING] 未检测到中文字体，图表文字将显示为方框。")
    print("          请安装 fonts-noto-cjk 或 matplotlib-backend-agg 后重试。")

plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 150

# ── 配色 ──────────────────────────────────────────────────────────────────────
C_BLUE       = "#378ADD"
C_BLUE_LIGHT = "#B5D4F4"
C_BLUE_DARK  = "#185FA5"
C_GREEN      = "#1D9E75"
C_GREEN_LT   = "#9FE1CB"
C_RED        = "#E24B4A"
C_RED_LT     = "#F7C1C1"
C_RED_DK     = "#A32D2D"
C_AMBER      = "#BA7517"
C_AMBER_LT   = "#faeeda"
C_GRAY       = "#888780"
C_GRAY_LT    = "#f7f7f7"
C_BG         = "#ffffff"
C_GRID       = "#eeeeee"
C_TEXT       = "#1a1a1a"
C_TEXT2      = "#888888"

def _ax_style(ax, ylabel=None, xlabel=None, ylim=None):
    """统一坐标轴样式。"""
    ax.set_facecolor(C_BG)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(C_GRID)
    ax.tick_params(colors=C_TEXT2, labelsize=9)
    ax.grid(axis="y", color=C_GRID, linewidth=0.6, zorder=0)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9, color=C_TEXT2)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9, color=C_TEXT2)
    if ylim:
        ax.set_ylim(*ylim)


# ══════════════════════════════════════════════════════════════════════════════
# 视图一：核心指标概览
# ══════════════════════════════════════════════════════════════════════════════
def plot_view1_overview(save_path="suning_view1_overview.png"):
    fig = plt.figure(figsize=(14, 9), facecolor=C_BG)
    fig.suptitle("苏宁易购集团 · 2024年度财务核心指标分析",
                 fontsize=14, fontweight="bold", color=C_TEXT, y=0.98)
    fig.text(0.5, 0.955, "数据来源：苏宁易购集团 2024年年度报告（2025年3月披露）· 零售行业",
             ha="center", fontsize=9, color=C_TEXT2)

    # ── 指标卡 ─────────────────────────────────────────────────────────────
    metrics = [
        ("营业收入（亿元）", "567.9", "▼ 9.32% 同比", C_RED),
        ("归母净利润（亿元）", "6.1", "扭亏为盈（2023: −40.9亿）", C_GREEN),
        ("综合毛利率", "15.84%", "▲ 3.44pct 同比", C_GREEN),
        ("经营现金流（亿元）", "45.9", "▲ 57.56% 同比", C_GREEN),
    ]
    card_y, card_h = 0.86, 0.09
    for i, (label, value, change, chg_color) in enumerate(metrics):
        x = 0.03 + i * 0.245
        ax_c = fig.add_axes([x, card_y, 0.22, card_h])
        ax_c.set_facecolor(C_GRAY_LT)
        ax_c.axis("off")
        ax_c.text(0.08, 0.82, label, transform=ax_c.transAxes,
                  fontsize=9, color=C_TEXT2, va="top")
        ax_c.text(0.08, 0.48, value, transform=ax_c.transAxes,
                  fontsize=20, fontweight="bold", color=C_TEXT, va="center")
        ax_c.text(0.08, 0.10, change, transform=ax_c.transAxes,
                  fontsize=9, color=chg_color, va="bottom")
        for spine in ax_c.spines.values():
            spine.set_visible(False)

    # ── 趋势图（折线+柱）──────────────────────────────────────────────────
    ax1 = fig.add_axes([0.05, 0.52, 0.55, 0.30])
    years = ["2022", "2023", "2024"]
    revenue = [1399, 626, 568]
    profit  = [-162, -40.9, 6.1]
    bars = ax1.bar(years, revenue, color=[C_BLUE_LIGHT, C_BLUE_LIGHT, C_BLUE],
                   width=0.5, zorder=3, label="营业收入（亿元）")
    ax1.set_title("营业收入与净利润趋势（2022–2024）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax1, ylabel="营业收入（亿元）")

    ax1r = ax1.twinx()
    ax1r.plot(years, profit, color=C_GREEN, marker="o", linewidth=2,
              markersize=6, zorder=4, label="净利润（亿元）")
    ax1r.set_ylabel("净利润（亿元）", fontsize=9, color=C_GREEN)
    ax1r.tick_params(colors=C_GREEN, labelsize=9)
    ax1r.spines[["top"]].set_visible(False)
    # 数值标注
    for y, v in zip(years, revenue):
        ax1.text(y, v + 15, f"{v}", ha="center", fontsize=8, color=C_TEXT2)
    for y, v in zip(years, profit):
        ax1r.text(y, v + 6, f"{v}", ha="center", fontsize=8, color=C_GREEN)

    handles = [
        mpatches.Patch(color=C_BLUE, label="营业收入（亿元）"),
        plt.Line2D([0], [0], color=C_GREEN, marker="o", linewidth=2, label="净利润（亿元）"),
    ]
    ax1.legend(handles=handles, fontsize=8, loc="upper right", framealpha=0.8)

    # ── 收入结构（分组柱）────────────────────────────────────────────────
    ax2 = fig.add_axes([0.05, 0.10, 0.38, 0.35])
    cats = ["家用电器/3C", "日用百货", "服务及其他"]
    rev24 = [467.2, 32.2, 20.0]
    rev23 = [504.1, 49.6, 21.3]
    x = np.arange(len(cats))
    w = 0.35
    ax2.bar(x - w/2, rev24, w, color=C_BLUE,       label="2024", zorder=3)
    ax2.bar(x + w/2, rev23, w, color=C_BLUE_LIGHT, label="2023", zorder=3)
    ax2.set_xticks(x); ax2.set_xticklabels(cats, fontsize=9)
    ax2.set_title("收入结构对比（亿元）", fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax2, ylabel="金额（亿元）")
    ax2.legend(fontsize=8, framealpha=0.8)

    # ── 地区收入（横向柱）────────────────────────────────────────────────
    ax3 = fig.add_axes([0.55, 0.10, 0.42, 0.35])
    regions = ["华东一区","华东二区","华北","华南","西南","华中","西北","东北"]
    vals    = [169.5, 78.8, 74.7, 63.4, 58.4, 37.8, 25.2, 11.6]
    colors  = [C_BLUE, C_BLUE, C_BLUE_DARK, C_BLUE_DARK,
               C_BLUE_DARK, C_BLUE_LIGHT, C_BLUE_LIGHT, C_BLUE_LIGHT]
    y_pos = np.arange(len(regions))
    ax3.barh(y_pos, vals, color=colors, zorder=3)
    ax3.set_yticks(y_pos); ax3.set_yticklabels(regions, fontsize=9)
    ax3.invert_yaxis()
    ax3.set_title("各地区收入分布（2024，亿元）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax3, xlabel="金额（亿元）")
    for i, v in enumerate(vals):
        ax3.text(v + 1.5, i, f"{v}", va="center", fontsize=8, color=C_TEXT2)

    # ── 右侧趋势图留白补充文字 ─────────────────────────────────────────
    fig.add_axes([0.62, 0.52, 0.35, 0.30]).axis("off")

    plt.savefig(save_path, bbox_inches="tight", facecolor=C_BG, dpi=150)
    plt.close(fig)
    print(f"✅ 视图一已保存：{save_path}")


# ══════════════════════════════════════════════════════════════════════════════
# 视图二：盈利结构与费用分析
# ══════════════════════════════════════════════════════════════════════════════
def plot_view2_profit(save_path="suning_view2_profit.png"):
    fig = plt.figure(figsize=(14, 9), facecolor=C_BG)
    fig.suptitle("苏宁易购集团 · 盈利能力与费用结构深度分析",
                 fontsize=14, fontweight="bold", color=C_TEXT, y=0.98)
    fig.text(0.5, 0.955, "对应 FinDecipher 财务点评模块 · 利润表深度分析 · 现金流分析",
             ha="center", fontsize=9, color=C_TEXT2)

    # ── 毛利率地区对比 ───────────────────────────────────────────────────
    ax1 = fig.add_axes([0.05, 0.56, 0.42, 0.34])
    regions = ["整体", "华东一", "华东二", "华北", "华南", "西南"]
    gm24 = [15.84, 16.39, 15.39, 14.83, 17.13, 17.52]
    gm23 = [12.40, 15.99, 10.96,  9.79, 14.97,  9.64]
    x = np.arange(len(regions))
    w = 0.35
    ax1.bar(x - w/2, gm24, w, color=C_GREEN,    label="2024", zorder=3)
    ax1.bar(x + w/2, gm23, w, color=C_GREEN_LT, label="2023", zorder=3)
    ax1.set_xticks(x); ax1.set_xticklabels(regions, fontsize=9)
    ax1.set_title("毛利率趋势（按地区，%）", fontsize=11, color=C_TEXT, pad=8, loc="left")
    ax1.set_ylabel("毛利率（%）", fontsize=9, color=C_TEXT2)
    _ax_style(ax1, ylim=(0, 22))
    ax1.legend(fontsize=8, framealpha=0.8)
    for i, (v24, v23) in enumerate(zip(gm24, gm23)):
        ax1.text(i - w/2, v24 + 0.3, f"{v24:.1f}", ha="center", fontsize=7, color=C_GREEN)
        ax1.text(i + w/2, v23 + 0.3, f"{v23:.1f}", ha="center", fontsize=7, color=C_TEXT2)

    # ── 费用降幅（横向柱）────────────────────────────────────────────────
    ax2 = fig.add_axes([0.55, 0.56, 0.42, 0.34])
    cost_labels = ["销售费用", "管理费用", "研发费用", "总费用合计"]
    cost_vals   = [-17.02, -24.96, -54.17, -16.79]
    cost_colors = [C_RED, C_RED, C_RED_DK, C_RED]
    y_pos = np.arange(len(cost_labels))
    ax2.barh(y_pos, cost_vals, color=cost_colors, zorder=3)
    ax2.set_yticks(y_pos); ax2.set_yticklabels(cost_labels, fontsize=9)
    ax2.invert_yaxis()
    ax2.set_title("三大费用同比变动（%）", fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax2, xlabel="同比变动（%）")
    ax2.axvline(0, color=C_GRAY, linewidth=0.8)
    for i, v in enumerate(cost_vals):
        ax2.text(v - 0.8, i, f"{v:.2f}%", va="center", ha="right",
                 fontsize=8, color=C_RED)

    # ── 现金流对比（分组柱）──────────────────────────────────────────────
    ax3 = fig.add_axes([0.05, 0.16, 0.55, 0.33])
    cash_cats = ["经营活动", "投资活动", "筹资活动"]
    cash24 = [45.9,  10.0, -62.3]
    cash23 = [29.1,  10.3, -40.2]
    x = np.arange(len(cash_cats))
    w = 0.35
    bars24 = ax3.bar(x - w/2, cash24, w, label="2024",
                     color=[C_BLUE, C_BLUE, C_RED], zorder=3)
    bars23 = ax3.bar(x + w/2, cash23, w, label="2023",
                     color=[C_BLUE_LIGHT, C_BLUE_LIGHT, C_RED_LT], zorder=3)
    ax3.set_xticks(x); ax3.set_xticklabels(cash_cats, fontsize=10)
    ax3.set_title("三大活动现金流对比（2023 vs 2024，亿元）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax3, ylabel="金额（亿元）")
    ax3.axhline(0, color=C_GRAY, linewidth=0.8)
    ax3.legend(fontsize=8, framealpha=0.8)
    for bar in list(bars24) + list(bars23):
        h = bar.get_height()
        offset = 1.5 if h >= 0 else -3.5
        ax3.text(bar.get_x() + bar.get_width()/2, h + offset,
                 f"{h:.1f}", ha="center", fontsize=8, color=C_TEXT2)

    # ── 洞察文本框 ─────────────────────────────────────────────────────
    insight = (
        "系统洞察（FinDecipher 分析结论）\n\n"
        "苏宁易购2024年实现以量换质的阶段性转变：营收虽同比下滑9.32%，\n"
        "但毛利率逆势提升3.44pct至15.84%，系专供商品占比提升（JSAV专供品\n"
        "占比22.6%）及日用百货等低利润品类结构性收缩所致。费用端总费用降\n"
        "幅（-16.79%）超过营收降幅，叠加债务重组收益（12.44亿元），共同\n"
        "推动净利润扭亏为盈（+6.1亿元）。然而扣非净利润仍亏损10.25亿元，\n"
        "盈利可持续性存疑，需持续关注主营业务造血能力。"
    )
    ax4 = fig.add_axes([0.62, 0.05, 0.35, 0.44])
    ax4.set_facecolor("#e6f1fb")
    ax4.axis("off")
    ax4.text(0.05, 0.95, insight, transform=ax4.transAxes,
             fontsize=9, color="#185FA5", va="top", linespacing=1.6,
             wrap=True)

    plt.savefig(save_path, bbox_inches="tight", facecolor=C_BG, dpi=150)
    plt.close(fig)
    print(f"✅ 视图二已保存：{save_path}")


# ══════════════════════════════════════════════════════════════════════════════
# 视图三：运营效率与业务亮点
# ══════════════════════════════════════════════════════════════════════════════
def plot_view3_operations(save_path="suning_view3_operations.png"):
    fig = plt.figure(figsize=(14, 10), facecolor=C_BG)
    fig.suptitle("苏宁易购集团 · 运营效率与业务亮点分析",
                 fontsize=14, fontweight="bold", color=C_TEXT, y=0.98)
    fig.text(0.5, 0.955, "对应 FinDecipher 业务亮点模块 · 季度趋势 · 门店运营效率",
             ha="center", fontsize=9, color=C_TEXT2)

    # ── KPI 卡片 ─────────────────────────────────────────────────────────
    kpis = [
        ("流动比率", "0.55", "低于1，短期偿付承压", C_RED),
        ("资产负债率", "90.63%", "同比改善 −1.04pct", C_RED),
        ("存货周转天数", "49.2天", "同比优化 −6.78天", C_GREEN),
    ]
    for i, (label, value, note, color) in enumerate(kpis):
        x = 0.03 + i * 0.325
        ax_c = fig.add_axes([x, 0.875, 0.30, 0.08])
        ax_c.set_facecolor(C_GRAY_LT); ax_c.axis("off")
        ax_c.text(0.07, 0.82, label, transform=ax_c.transAxes,
                  fontsize=9, color=C_TEXT2, va="top")
        ax_c.text(0.07, 0.45, value, transform=ax_c.transAxes,
                  fontsize=19, fontweight="bold", color=color, va="center")
        ax_c.text(0.07, 0.08, note, transform=ax_c.transAxes,
                  fontsize=8, color=C_TEXT2, va="bottom")

    # ── 季度营收趋势 ──────────────────────────────────────────────────────
    ax1 = fig.add_axes([0.05, 0.52, 0.46, 0.32])
    quarters = ["Q1", "Q2", "Q3", "Q4"]
    qrev  = [125.8, 132.0, 122.4, 187.7]
    qpro  = [-1.0, 1.11, 5.84, 0.11]
    bar_colors = [C_BLUE_LIGHT, C_BLUE_LIGHT, C_BLUE_LIGHT, C_BLUE]
    ax1.bar(quarters, qrev, color=bar_colors, width=0.5, zorder=3)
    ax1.set_title("季度营收趋势（2024，亿元）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax1, ylabel="营业收入（亿元）")

    ax1r = ax1.twinx()
    ax1r.plot(quarters, qpro, color=C_GREEN, marker="o", linewidth=2,
              markersize=6, zorder=4)
    ax1r.set_ylabel("净利润（亿元）", fontsize=9, color=C_GREEN)
    ax1r.tick_params(colors=C_GREEN, labelsize=9)
    ax1r.spines[["top"]].set_visible(False)
    ax1r.axhline(0, color=C_GRAY, linewidth=0.6, linestyle="--")
    for q, v in zip(quarters, qrev):
        ax1.text(q, v + 2, f"{v}", ha="center", fontsize=8, color=C_TEXT2)
    for q, v in zip(quarters, qpro):
        offset = 0.3 if v >= 0 else -0.6
        ax1r.text(q, v + offset, f"{v:.2f}", ha="center", fontsize=8, color=C_GREEN)
    # Q4 政策标注
    ax1.annotate("以旧换新政策\n同比+34.35%",
                 xy=("Q4", 187.7), xytext=("Q3", 175),
                 fontsize=8, color=C_BLUE_DARK,
                 arrowprops=dict(arrowstyle="->", color=C_BLUE_DARK, lw=0.8),
                 ha="center")

    # ── 门店坪效变动 ──────────────────────────────────────────────────────
    ax2 = fig.add_axes([0.57, 0.52, 0.40, 0.32])
    store_labels = ["华东一区","华南","华中","华东二区","西南","华北","西北","东北"]
    store_vals   = [11.99, 4.75, 0.76, 0.29, -1.29, -2.20, -14.24, -16.29]
    s_colors     = [C_GREEN if v >= 0 else C_RED for v in store_vals]
    y_pos = np.arange(len(store_labels))
    ax2.barh(y_pos, store_vals, color=s_colors, zorder=3)
    ax2.set_yticks(y_pos); ax2.set_yticklabels(store_labels, fontsize=9)
    ax2.invert_yaxis()
    ax2.axvline(0, color=C_GRAY, linewidth=0.8)
    ax2.set_title("门店坪效同比变动（%）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax2, xlabel="坪效同比变动（%）")
    for i, v in enumerate(store_vals):
        offset = 0.3 if v >= 0 else -0.3
        ha = "left" if v >= 0 else "right"
        ax2.text(v + offset, i, f"{v:.2f}%", va="center", ha=ha,
                 fontsize=8, color=C_TEXT2)

    # ── 业务战略层次图（matplotlib patches 绘制）───────────────────────
    ax3 = fig.add_axes([0.03, 0.04, 0.94, 0.42])
    ax3.set_xlim(0, 10); ax3.set_ylim(0, 4.5)
    ax3.axis("off")
    ax3.set_title("业务亮点结构：三大战略支柱与财务映射（系统自动识别行业并加载模板）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")

    def draw_box(ax, x, y, w, h, text, subtext, facecolor, edgecolor, textcolor, subtextcolor):
        box = mpatches.FancyBboxPatch((x - w/2, y - h/2), w, h,
                                      boxstyle="round,pad=0.05",
                                      facecolor=facecolor, edgecolor=edgecolor,
                                      linewidth=1.0, zorder=3)
        ax.add_patch(box)
        ax.text(x, y + 0.08, text, ha="center", va="center",
                fontsize=10, fontweight="bold", color=textcolor, zorder=4)
        ax.text(x, y - 0.22, subtext, ha="center", va="center",
                fontsize=8.5, color=subtextcolor, zorder=4)

    def arrow(ax, x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", color="#cccccc",
                                   lw=0.8, mutation_scale=10), zorder=2)

    # 顶层
    draw_box(ax3, 5, 4.0, 3.0, 0.7, "苏宁易购零售服务商战略", "聚焦家电3C · 全渠道运营",
             "#e6f1fb", C_BLUE_DARK, C_BLUE_DARK, C_BLUE)
    # 连线
    arrow(ax3, 3.5, 3.65, 1.8, 3.05)
    arrow(ax3, 5.0, 3.65, 5.0, 3.05)
    arrow(ax3, 6.5, 3.65, 8.2, 3.05)
    # 第二层
    draw_box(ax3, 1.8, 2.7, 2.8, 0.65, "全渠道网络拓展", "零售云加盟店 10,168家",
             "#e1f5ee", "#0F6E56", "#0F6E56", C_GREEN)
    draw_box(ax3, 5.0, 2.7, 2.8, 0.65, "专供商品差异化", "JSAV专供品占比 22.6%",
             "#faeeda", "#854F0B", "#854F0B", C_AMBER)
    draw_box(ax3, 8.2, 2.7, 2.8, 0.65, "服务能力提升", "2小时即送即装·以旧换新",
             "#faece7", "#993C1D", "#993C1D", "#D85A30")
    # 连线
    arrow(ax3, 1.8, 2.37, 1.8, 1.85)
    arrow(ax3, 5.0, 2.37, 5.0, 1.85)
    arrow(ax3, 8.2, 2.37, 8.2, 1.85)
    # 第三层（财务映射）
    for xpos, lines in [
        (1.8,  ["Q4门店坪效 +62%", "新开/重装大店75家"]),
        (5.0,  ["毛利率提升 3.44pct", "家电品类毛利率15.06%"]),
        (8.2,  ["可比门店坪效 +1.17%", "存货周转优化6.78天"]),
    ]:
        box = mpatches.FancyBboxPatch((xpos - 1.4, 1.2), 2.8, 0.65,
                                      boxstyle="round,pad=0.05",
                                      facecolor=C_BG, edgecolor="#cccccc",
                                      linewidth=0.8, zorder=3)
        ax3.add_patch(box)
        ax3.text(xpos, 1.62, lines[0], ha="center", fontsize=9,
                 color=C_TEXT, zorder=4, fontweight="500")
        ax3.text(xpos, 1.38, lines[1], ha="center", fontsize=8.5,
                 color=C_TEXT2, zorder=4)

    plt.savefig(save_path, bbox_inches="tight", facecolor=C_BG, dpi=150)
    plt.close(fig)
    print(f"✅ 视图三已保存：{save_path}")


# ══════════════════════════════════════════════════════════════════════════════
# 视图四：投资策略四维评估
# ══════════════════════════════════════════════════════════════════════════════
def plot_view4_investment(save_path="suning_view4_investment.png"):
    fig = plt.figure(figsize=(14, 10), facecolor=C_BG)
    fig.suptitle("苏宁易购集团 · 投资策略四维评估分析",
                 fontsize=14, fontweight="bold", color=C_TEXT, y=0.98)
    fig.text(0.5, 0.955, "对应 FinDecipher 投资策略模块 · 盈利预测 · SWOT框架 · 综合评分",
             ha="center", fontsize=9, color=C_TEXT2)

    # ── 四维评分卡 ─────────────────────────────────────────────────────
    dims = [
        ("安全边际", 2, "持续经营不确定\n审计含重大不确定段落", "#fcebeb", "#a32d2d"),
        ("盈利趋势", 3, "净利润扭亏\n扣非仍负，主业未验证", "#eaf3de", "#3B6D11"),
        ("催化因素", 4, "以旧换新扩围\n至12品类+数码产品", "#eaf3de", "#3B6D11"),
        ("风险暴露", 2, "流动比率0.55\n应付款偿付压力大", "#fcebeb", "#a32d2d"),
    ]
    for i, (label, score, note, bg, fg) in enumerate(dims):
        x = 0.03 + i * 0.245
        ax_c = fig.add_axes([x, 0.855, 0.22, 0.10])
        ax_c.set_facecolor(bg); ax_c.axis("off")
        ax_c.text(0.5, 0.88, label, transform=ax_c.transAxes,
                  fontsize=10, fontweight="bold", color=fg, ha="center", va="top")
        ax_c.text(0.5, 0.55, str(score) + "分", transform=ax_c.transAxes,
                  fontsize=22, fontweight="bold", color=fg, ha="center", va="center")
        ax_c.text(0.5, 0.08, note, transform=ax_c.transAxes,
                  fontsize=8, color=fg, ha="center", va="bottom", linespacing=1.4)

    # 综合评分横幅
    ax_s = fig.add_axes([0.03, 0.795, 0.94, 0.055])
    ax_s.set_facecolor(C_GRAY_LT); ax_s.axis("off")
    ax_s.text(0.03, 0.5, "综合评分：2.75 / 5.0  ·  谨慎观察区间",
              transform=ax_s.transAxes, fontsize=12, fontweight="bold",
              color=C_AMBER, va="center")
    ax_s.text(0.75, 0.5, "（加权：安全边际×0.3 + 盈利趋势×0.25 + 催化因素×0.25 + 风险暴露×0.20）",
              transform=ax_s.transAxes, fontsize=8.5, color=C_TEXT2, va="center")

    # ── 三情景预测柱 ──────────────────────────────────────────────────────
    ax1 = fig.add_axes([0.05, 0.44, 0.46, 0.32])
    cats   = ["2024实际\n(扣非)", "悲观情景\n2025E", "中性情景\n2025E", "乐观情景\n2025E"]
    vals   = [-10.25, -15, -8, -3]
    colors = [C_GRAY, C_RED_LT, C_BLUE_LIGHT, C_GREEN_LT]
    bars = ax1.bar(cats, vals, color=colors, width=0.5, zorder=3)
    ax1.set_title("三情景盈利预测：扣非净利润（亿元）",
                  fontsize=11, color=C_TEXT, pad=8, loc="left")
    _ax_style(ax1, ylabel="扣非净利润（亿元）")
    ax1.axhline(0, color=C_GRAY, linewidth=0.8)
    for bar, v in zip(bars, vals):
        offset = 0.4 if v >= 0 else -1.0
        ax1.text(bar.get_x() + bar.get_width()/2, v + offset,
                 f"{v:.2f}亿", ha="center", fontsize=9, color=C_TEXT2)
    ax1.set_facecolor(C_BG)

    # ── SWOT 雷达 ─────────────────────────────────────────────────────────
    ax2 = fig.add_axes([0.55, 0.44, 0.42, 0.34], polar=True)
    categories = ["优势\n(全渠道+专供品)", "劣势\n(流动性不足)",
                  "机会\n(政策驱动)", "威胁\n(竞争+债务)"]
    N = len(categories)
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]
    values = [3, 1, 4, 2]
    values += values[:1]

    ax2.plot(angles, values, color=C_BLUE, linewidth=1.5)
    ax2.fill(angles, values, color=C_BLUE, alpha=0.12)
    ax2.scatter(angles[:-1], values[:-1], color=C_BLUE, s=30, zorder=4)
    ax2.set_xticks(angles[:-1])
    ax2.set_xticklabels(categories, fontsize=9, color=C_TEXT)
    ax2.set_yticks([1, 2, 3, 4, 5])
    ax2.set_yticklabels(["1", "2", "3", "4", "5"], fontsize=7, color=C_TEXT2)
    ax2.set_ylim(0, 5)
    ax2.set_facecolor(C_BG)
    ax2.grid(color=C_GRID, linewidth=0.6)
    ax2.set_title("SWOT四维雷达评估", fontsize=11, color=C_TEXT, pad=20)
    # 数值标注
    for angle, val, cat in zip(angles[:-1], values[:-1], categories):
        ax2.text(angle, val + 0.25, str(val) + "分",
                 ha="center", va="center", fontsize=8.5, color=C_BLUE,
                 fontweight="bold")

    # ── 投资策略建议文本 ──────────────────────────────────────────────────
    strategy_text = (
        "综合投资策略建议：谨慎观察\n\n"
        "苏宁易购当前处于深度重组阶段，2024年净利润扭亏（+6.1亿元）主要依赖\n"
        "非经常性损益（含债务重组收益12.44亿元），主营业务扣非净利润仍亏损\n"
        "10.25亿元，可持续盈利能力尚未得到验证。\n\n"
        "正向催化因素：以旧换新政策2025年进一步扩围，品类增至12类并纳入手\n"
        "机、平板等数码产品；Q4门店坪效同比+62%，政策驱动效果显著。\n\n"
        "核心风险：流动比率仅0.55，应付款项偿付压力大；审计报告显示持续\n"
        "经营存在重大不确定性；西北/东北地区坪效持续下滑。\n\n"
        "跟踪信号：Q1 2025营收能否延续Q4增势、扣非盈利连续转正、供应商库\n"
        "存恢复进程。待主营业务造血能力验证后再行积极评估。"
    )
    ax3 = fig.add_axes([0.03, 0.04, 0.94, 0.36])
    ax3.set_facecolor(C_AMBER_LT); ax3.axis("off")
    ax3.text(0.025, 0.95, strategy_text, transform=ax3.transAxes,
             fontsize=9.5, color="#633806", va="top", linespacing=1.65)

    plt.savefig(save_path, bbox_inches="tight", facecolor=C_BG, dpi=150)
    plt.close(fig)
    print(f"✅ 视图四已保存：{save_path}")


# ══════════════════════════════════════════════════════════════════════════════
# 主程序入口
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    plot_view1_overview("suning_view1_overview.png")
    plot_view2_profit("suning_view2_profit.png")
    plot_view3_operations("suning_view3_operations.png")
    plot_view4_investment("suning_view4_investment.png")
    print("\n全部完成。请在当前目录查看四张 PNG 图片。")