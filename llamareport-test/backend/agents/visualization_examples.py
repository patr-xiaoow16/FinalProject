"""
可视化视图代码示例库

这个文件包含了所有可视化视图的代码示例，用于指导LLM生成视图配置。
当需要添加新的视图示例时，只需在此文件中添加即可。

示例结构：
- type: 视图类型（'timeline', 'plotly'等）
- description: 示例描述
- example: 示例代码/配置
- usage: 适用场景
"""

from models.visualization_models import ChartType

# 可视化视图代码示例库
VISUALIZATION_EXAMPLES = {
    # 时间轴示例（用于过程与变化类）
    'timeline': {
        'type': 'timeline',
        'description': '时间轴（年度大事记）',
        'example': [
            {'time': '2024 Q1', 'content': '渠道调整启动', 'color': 'blue'},
            {'time': '2024 Q2', 'content': '新产品上线', 'color': 'green'},
            {'time': '2024 Q3', 'content': '成本优化见效', 'color': 'blue'},
            {'time': '2024 Q4', 'content': '盈利能力修复', 'color': 'green'}
        ],
        'usage': '适用于过程与变化类问题，展示关键事件的时间序列'
    },
    
    # 风险矩阵示例（Plotly散点图）
    'risk_matrix': {
        'type': 'plotly',
        'description': '风险矩阵（概率 × 影响）',
        'example': {
            'chart_type': 'scatter',
            'xaxis': {'title': '发生概率', 'range': [0, 5]},
            'yaxis': {'title': '影响程度', 'range': [0, 5]},
            'data': [
                {'x': 4, 'y': 5, 'text': '宏观政策风险'},
                {'x': 2, 'y': 3, 'text': '客户集中度风险'}
            ],
            'marker': {'size': 20}
        },
        'usage': '适用于风险与不确定性类问题'
    },
    
    # 业务结构图示例（Plotly Treemap）
    'treemap': {
        'type': 'plotly',
        'description': '业务结构图（Treemap）',
        'example': {
            'chart_type': 'treemap',
            'data': [
                {'name': '零售业务', 'value': 60},
                {'name': '对公业务', 'value': 30},
                {'name': '其他', 'value': 10}
            ]
        },
        'usage': '适用于结构描述类问题，展示业务组成'
    },
    
    # 桑基图示例（Plotly格式，用于展示数据流动和结构关系）
    'sankey': {
        'type': 'plotly',
        'description': '桑基图（Sankey Diagram）',
        'example': {
            'chart_type': 'sankey',
            'nodes': {
                'label': ['业务收入', '零售业务', '对公业务', '其他业务', '成本', '利润'],
                'color': ['#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6', '#ffffcc']
            },
            'links': {
                'source': [0, 0, 0, 1, 2, 3],  # 源节点索引
                'target': [1, 2, 3, 4, 4, 4],  # 目标节点索引
                'value': [60, 30, 10, 40, 20, 5]  # 流量值
            },
            'layout': {
                'title': '业务结构流动图',
                'height': 600,
                'font': {'size': 12}
            }
        },
        'usage': '适用于结构描述类问题，展示数据流动、业务结构、价值链、资金流向等。例如：公司靠什么赚钱、业务收入如何分配、资金流向、供应链结构等场景'
    },
    
    # 折线图示例（Plotly格式，带标记点）
    'line_with_markers': {
        'type': 'plotly',
        'description': '折线图（带峰值标记）',
        'example': {
            'chart_type': 'scatter',
            'mode': 'lines+markers',
            'x': ['2020', '2021', '2022', '2023', '2024'],
            'y': [100, 120, 90, 130, 160],
            'marker': {'size': 8},
            'annotations': [
                {'x': '2024', 'y': 160, 'text': '峰值', 'showarrow': True}
            ]
        },
        'usage': '适用于数据类问题，展示趋势和异常点'
    },
    
    # 柱状图示例
    'bar_chart': {
        'type': 'plotly',
        'description': '柱状图（对比分析）',
        'example': {
            'chart_type': 'bar',
            'x': ['2020', '2021', '2022', '2023', '2024'],
            'y': [100, 120, 90, 130, 160],
            'marker': {'color': 'rgb(55, 83, 109)'},
            'textposition': 'auto'
        },
        'usage': '适用于数据类和对比类问题'
    },
    
    # 折线图标记线示例（Plotly格式，使用shapes和annotations实现标记线）
    'line_with_markline': {
        'type': 'plotly',
        'description': '折线图（带标记线/阈值线）',
        'example': {
            'chart_type': 'scatter',
            'mode': 'lines+markers',
            'x': ['2020', '2021', '2022', '2023', '2024'],
            'y': [100, 120, 90, 130, 160],
            'marker': {'size': 8},
            'layout': {
                'shapes': [
                    # 水平标记线（如平均值、目标值、警戒线）
                    {
                        'type': 'line',
                        'x0': 0,
                        'x1': 1,
                        'xref': 'paper',
                        'y0': 110,  # 标记线数值（如平均值）
                        'y1': 110,
                        'line': {
                            'color': 'red',
                            'width': 2,
                            'dash': 'dash'
                        }
                    },
                    # 垂直标记线（如关键时间点）
                    {
                        'type': 'line',
                        'x0': '2022',
                        'x1': '2022',
                        'y0': 0,
                        'y1': 1,
                        'yref': 'paper',
                        'line': {
                            'color': 'blue',
                            'width': 1,
                            'dash': 'dot'
                        }
                    }
                ],
                'annotations': [
                    # 标记线标签
                    {
                        'x': '2024',
                        'y': 110,
                        'text': '平均值: 110',
                        'showarrow': True,
                        'arrowhead': 2,
                        'ax': 0,
                        'ay': -30,
                        'bgcolor': 'rgba(255, 255, 255, 0.8)',
                        'bordercolor': 'red',
                        'borderwidth': 1
                    },
                    # 关键点标记
                    {
                        'x': '2022',
                        'y': 90,
                        'text': '最低点',
                        'showarrow': True,
                        'arrowhead': 2,
                        'bgcolor': 'rgba(255, 255, 255, 0.8)'
                    }
                ]
            }
        },
        'usage': '适用于需要标记阈值、目标值、平均值、警戒线或关键时间点的数据类问题。例如：指标是否达到目标、是否超过警戒线、与平均值对比、关键事件时间点等场景'
    },
    
    # 桑基图示例（Plotly格式，用于展示数据流动和结构关系）
    'sankey': {
        'type': 'plotly',
        'description': '桑基图（Sankey Diagram）',
        'example': {
            'chart_type': 'sankey',
            'nodes': {
                'label': ['业务收入', '零售业务', '对公业务', '其他业务', '成本', '利润'],
                'color': ['#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6', '#ffffcc']
            },
            'links': {
                'source': [0, 0, 0, 1, 2, 3],  # 源节点索引
                'target': [1, 2, 3, 4, 4, 4],  # 目标节点索引
                'value': [60, 30, 10, 40, 20, 5]  # 流量值
            },
            'layout': {
                'title': '业务结构流动图',
                'height': 600,
                'font': {'size': 12}
            }
        },
        'usage': '适用于结构描述类问题，展示数据流动、业务结构、价值链、资金流向等。例如：公司靠什么赚钱、业务收入如何分配、资金流向、供应链结构、价值链分解等场景'
    }
}

# 问题类型关键词映射（基于可视化匹配.md文档）
QUESTION_TYPE_KEYWORDS = {
    'data': [  # 数据类
        '指标', '数值', '数据', '金额', '收入', '利润', '资产', '负债',
        '增长率', '同比', '环比', '趋势', '水平', '多少', '多大'
    ],
    'conclusion': [  # 核心结论类
        '整体', '经营', '业绩', '表现', '好坏', '判断', '评价', '结论',
        '管理层', '重要', '关键', '核心'
    ],
    'structure': [  # 结构描述类
        '结构', '组成', '占比', '分布', '业务', '产品', '区域', '渠道',
        '靠什么', '核心', '主要', '次要'
    ],
    'process': [  # 过程与变化类
        '过程', '变化', '推进', '实施', '执行', '发生', '时间', '阶段',
        '事件', '关键事件', '里程碑', '影响', '未来', '投资', '计划',
        '时间轴', '时间线', '什么时候', '何时', '推进', '进展'
    ],
    'risk': [  # 风险与不确定性类
        '风险', '不确定性', '挑战', '困难', '问题', '隐患', '威胁',
        '新增', '强调', '反复'
    ],
    'attitude': [  # 态度与语气类
        '态度', '语气', '乐观', '谨慎', '悲观', '信心', '预期', '展望',
        '模糊', '回避', '承诺'
    ],
    'comparison': [  # 跨年度对比类
        '对比', '比较', '变化', '差异', '新增强调', '弱化', '历年',
        '去年', '今年', '往年'
    ],
    'compliance': [  # 纯合规/事实类
        '合规', '法规', '制度', '规定', '标准', '要求', '必须', '应当'
    ]
}

# 视图推荐映射（基于可视化匹配.md文档）
VIEW_RECOMMENDATION_MAP = {
    'data': {
        'chart_types': [ChartType.LINE, ChartType.BAR, ChartType.GAUGE],
        'keywords': ['趋势', '水平', '异常', '拐点'],
        'description': '数据类：折线图、柱状图、KPI指标卡',
        'example_questions': [
            '指标现在处于什么水平？',
            '趋势是上升还是下降？',
            '是否存在异常或拐点？',
            '数值是多少？'
        ]
    },
    'conclusion': {
        'chart_types': [ChartType.GAUGE, ChartType.PIE],
        'keywords': ['整体', '经营', '业绩', '表现'],
        'description': '核心结论类：Insight Card、状态标签',
        'example_questions': [
            '这一年整体经营是好是坏？',
            '管理层最重要的判断是什么？',
            '与去年相比是否变化？'
        ]
    },
    'structure': {
        'chart_types': [ChartType.PIE, ChartType.BAR],
        'keywords': ['结构', '组成', '占比', '分布'],
        'description': '结构描述类：业务结构图、价值链示意图',
        'example_questions': [
            '公司靠什么赚钱？',
            '哪块业务最核心？',
            '是否存在结构性风险？'
        ]
    },
    'process': {
        'chart_types': [ChartType.LINE, ChartType.BAR],
        'keywords': ['过程', '变化', '事件', '时间'],
        'description': '过程与变化类：时间轴、阶段流程图',
        'example_questions': [
            '这一年发生了哪些关键事件？',
            '事情发生在什么时候？',
            '推进是否连续？'
        ]
    },
    'risk': {
        'chart_types': [ChartType.SCATTER, ChartType.HEATMAP],
        'keywords': ['风险', '不确定性', '挑战'],
        'description': '风险与不确定性类：风险矩阵、风险趋势标签',
        'example_questions': [
            '哪些风险是新增的？',
            '哪些被反复强调？',
            '风险若发生先影响哪里？'
        ]
    },
    'attitude': {
        'chart_types': [ChartType.LINE, ChartType.BAR],
        'keywords': ['态度', '语气', '乐观', '谨慎'],
        'description': '态度与语气类：情绪/语气趋势图、承诺强度标签',
        'example_questions': [
            '管理层对未来偏乐观还是谨慎？',
            '是否出现模糊或回避？',
            '管理层的态度如何？'
        ]
    },
    'comparison': {
        'chart_types': [ChartType.BAR, ChartType.LINE],
        'keywords': ['对比', '比较', '变化', '差异'],
        'description': '跨年度对比类：文本Diff视图、关键词变化热度',
        'example_questions': [
            '今年新增强调了什么？',
            '去年内容是否被弱化？',
            '与去年相比有什么变化？'
        ]
    },
    'compliance': {
        'chart_types': [],
        'keywords': ['合规', '法规', '制度'],
        'description': '纯合规/事实类：不生成可视化',
        'example_questions': []
    }
}

