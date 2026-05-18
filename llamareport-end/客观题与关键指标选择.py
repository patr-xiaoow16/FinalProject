import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from scipy.stats import fisher_exact


# =========================
# 1. 自动查找中文字体
# =========================

def get_chinese_font():
    """
    自动寻找系统中的中文字体。
    适配 macOS / Windows / Linux。
    """
    preferred_fonts = [
        # macOS
        "PingFang SC",
        "Heiti SC",
        "Songti SC",
        "STHeiti",
        "Arial Unicode MS",

        # Windows
        "Microsoft YaHei",
        "SimHei",
        "SimSun",
        "KaiTi",

        # Linux / 常见开源中文字体
        "Noto Sans CJK SC",
        "Noto Serif CJK SC",
        "Source Han Sans SC",
        "Source Han Serif SC",
        "WenQuanYi Micro Hei",
        "WenQuanYi Zen Hei",
    ]

    available_fonts = {f.name: f.fname for f in fm.fontManager.ttflist}

    for font_name in preferred_fonts:
        if font_name in available_fonts:
            return available_fonts[font_name], font_name

    return None, None


font_path, font_name = get_chinese_font()

if font_path:
    chinese_font = fm.FontProperties(fname=font_path)
    plt.rcParams["font.family"] = font_name
    print(f"已使用中文字体：{font_name}")
else:
    chinese_font = None
    print("未找到中文字体。请安装 Noto Sans CJK SC、微软雅黑或苹方字体。")

plt.rcParams["axes.unicode_minus"] = False


# =========================
# 2. 统计检验函数
# =========================

def cohens_h(p1, p2):
    return 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))


def phi_coefficient(a, b, c, d):
    numerator = a * d - b * c
    denominator = np.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if denominator == 0:
        return np.nan
    return numerator / denominator


def interpret_cohens_h(h):
    abs_h = abs(h)
    if abs_h < 0.20:
        return "小效应以下"
    elif abs_h < 0.50:
        return "小效应"
    elif abs_h < 0.80:
        return "中等效应"
    else:
        return "大效应"


def run_binary_test(items, n_exp=10, n_ctrl=10):
    rows = []

    for item in items:
        name = item["name"]
        exp_success = item["exp_success"]
        ctrl_success = item["ctrl_success"]

        exp_failure = n_exp - exp_success
        ctrl_failure = n_ctrl - ctrl_success

        table = np.array([
            [exp_success, exp_failure],
            [ctrl_success, ctrl_failure]
        ])

        _, p_value = fisher_exact(table, alternative="two-sided")

        p_exp = exp_success / n_exp
        p_ctrl = ctrl_success / n_ctrl

        h = cohens_h(p_exp, p_ctrl)
        phi = phi_coefficient(exp_success, exp_failure, ctrl_success, ctrl_failure)

        rows.append({
            "指标": name,
            "实验组": f"{exp_success}/{n_exp} ({p_exp:.1%})",
            "对照组": f"{ctrl_success}/{n_ctrl} ({p_ctrl:.1%})",
            "检验方法": "Fisher精确检验",
            "p值": f"{p_value:.3f}",
            "Cohen's h": f"{h:.3f}",
            "Phi": f"{phi:.3f}",
            "效应量解释": interpret_cohens_h(h)
        })

    return pd.DataFrame(rows)


# =========================
# 3. 导出优化后的论文表格视图
# =========================

def export_table_view(df, png_path, pdf_path, svg_path=None):
    """
    导出适合论文使用的表格视图。
    中文字体自动适配。
    """

    fig_width = 14
    fig_height = 0.62 * len(df) + 1.35

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")

    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        colLoc="center",
        loc="center"
    )

    table.auto_set_font_size(False)
    table.set_fontsize(10.5)
    table.scale(1, 1.55)

    n_rows = len(df) + 1
    n_cols = len(df.columns)

    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#333333")
        cell.set_linewidth(0.8)

        if chinese_font is not None:
            cell.get_text().set_fontproperties(chinese_font)

        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_facecolor("#F2F2F2")
            cell.set_linewidth(1.0)

        if row > 0:
            cell.set_facecolor("#FFFFFF")

    # 适当加宽“指标”和“检验方法”两列，避免文字挤压
    col_widths = {
        0: 0.18,   # 指标
        1: 0.13,   # 实验组
        2: 0.13,   # 对照组
        3: 0.15,   # 检验方法
        4: 0.07,   # p值
        5: 0.10,   # Cohen's h
        6: 0.08,   # Phi
        7: 0.11    # 效应量解释
    }

    for col, width in col_widths.items():
        for row in range(n_rows):
            table[(row, col)].set_width(width)

    plt.tight_layout()

    plt.savefig(png_path, dpi=300, bbox_inches="tight", pad_inches=0.08)
    plt.savefig(pdf_path, bbox_inches="tight", pad_inches=0.08)

    if svg_path:
        plt.savefig(svg_path, bbox_inches="tight", pad_inches=0.08)

    plt.close()


# =========================
# 4. 你的论文数据
# =========================

items = [
    {"name": "Q1 正确率", "exp_success": 9, "ctrl_success": 6},
    {"name": "Q2 正确率", "exp_success": 6, "ctrl_success": 4},
    {"name": "Q3 正确率", "exp_success": 7, "ctrl_success": 6},
    {"name": "Q4 正确率", "exp_success": 7, "ctrl_success": 4},
    {"name": "选择净息差", "exp_success": 8, "ctrl_success": 2},
    {"name": "同时选择ROE变化和净息差", "exp_success": 7, "ctrl_success": 1},
]

binary_result = run_binary_test(items, n_exp=10, n_ctrl=10)

binary_result.to_excel("binary_statistical_tests.xlsx", index=False)

export_table_view(
    binary_result,
    png_path="binary_statistical_tests_table.png",
    pdf_path="binary_statistical_tests_table.pdf",
    svg_path="binary_statistical_tests_table.svg"
)

print(binary_result)
print("已导出：binary_statistical_tests.xlsx")
print("已导出：binary_statistical_tests_table.png")
print("已导出：binary_statistical_tests_table.pdf")
print("已导出：binary_statistical_tests_table.svg")