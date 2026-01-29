"""
可视化图表的 Pydantic 数据模型
用于定义图表配置和数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


# ==================== 图表类型枚举 ====================

class ChartType(str, Enum):
    """图表类型"""
    BAR = "bar"  # 柱状图
    LINE = "line"  # 折线图
    PIE = "pie"  # 饼图
    SCATTER = "scatter"  # 散点图
    AREA = "area"  # 面积图
    HISTOGRAM = "histogram"  # 直方图
    BOX = "box"  # 箱线图
    HEATMAP = "heatmap"  # 热力图
    WATERFALL = "waterfall"  # 瀑布图
    FUNNEL = "funnel"  # 漏斗图
    GAUGE = "gauge"  # 仪表盘
    TABLE = "table"  # 表格
    MULTI_LINE = "multi_line"  # 多折线图
    GROUPED_BAR = "grouped_bar"  # 分组柱状图
    STACKED_BAR = "stacked_bar"  # 堆叠柱状图
    COMBO = "combo"  # 组合图


# ==================== 图表数据模型 ====================

class ChartTrace(BaseModel):
    """单个图表轨迹/系列"""
    name: str = Field(description="系列名称")
    x: List[Any] = Field(description="X轴数据")
    y: List[Any] = Field(description="Y轴数据")
    type: Optional[str] = Field(default=None, description="轨迹类型")
    mode: Optional[str] = Field(default=None, description="显示模式，如'lines+markers'")
    marker: Optional[Dict[str, Any]] = Field(default=None, description="标记样式")
    line: Optional[Dict[str, Any]] = Field(default=None, description="线条样式")
    fill: Optional[str] = Field(default=None, description="填充方式")
    text: Optional[List[str]] = Field(default=None, description="文本标签")
    hovertemplate: Optional[str] = Field(default=None, description="悬停模板")


class ChartLayout(BaseModel):
    """图表布局配置"""
    title: str = Field(description="图表标题")
    xaxis_title: Optional[str] = Field(default=None, description="X轴标题")
    yaxis_title: Optional[str] = Field(default=None, description="Y轴标题")
    height: Optional[int] = Field(default=500, description="图表高度")
    width: Optional[int] = Field(default=None, description="图表宽度")
    showlegend: Optional[bool] = Field(default=True, description="是否显示图例")
    template: Optional[str] = Field(default="plotly_white", description="图表模板")
    hovermode: Optional[str] = Field(default="closest", description="悬停模式")
    annotations: Optional[List[Dict[str, Any]]] = Field(default=None, description="注释")


class PlotlyChartConfig(BaseModel):
    """Plotly图表完整配置"""
    chart_type: ChartType = Field(description="图表类型")
    traces: List[ChartTrace] = Field(description="图表数据轨迹列表")
    layout: ChartLayout = Field(description="图表布局配置")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Plotly配置选项")


# ==================== 简化的图表配置模型 ====================

class SimpleBarChart(BaseModel):
    """简单柱状图配置"""
    title: str = Field(description="图表标题")
    x_labels: List[str] = Field(description="X轴标签")
    y_values: List[float] = Field(description="Y轴数值")
    x_title: Optional[str] = Field(default="", description="X轴标题")
    y_title: Optional[str] = Field(default="", description="Y轴标题")
    color: Optional[str] = Field(default="blue", description="柱状图颜色")


class SimpleLineChart(BaseModel):
    """简单折线图配置"""
    title: str = Field(description="图表标题")
    x_values: List[Any] = Field(description="X轴数据（可以是日期、数字等）")
    y_values: List[float] = Field(description="Y轴数值")
    x_title: Optional[str] = Field(default="", description="X轴标题")
    y_title: Optional[str] = Field(default="", description="Y轴标题")
    line_color: Optional[str] = Field(default="blue", description="线条颜色")
    show_markers: Optional[bool] = Field(default=True, description="是否显示标记点")


class SimplePieChart(BaseModel):
    """简单饼图配置"""
    title: str = Field(description="图表标题")
    labels: List[str] = Field(description="标签")
    values: List[float] = Field(description="数值")
    hole: Optional[float] = Field(default=0, description="中心空洞大小（0-1），0为饼图，>0为环形图")


class MultiLineChart(BaseModel):
    """多折线图配置"""
    title: str = Field(description="图表标题")
    x_values: List[Any] = Field(description="共享的X轴数据")
    series: List[Dict[str, Any]] = Field(
        description="多个系列数据，每个包含name和y_values"
    )
    x_title: Optional[str] = Field(default="", description="X轴标题")
    y_title: Optional[str] = Field(default="", description="Y轴标题")


class GroupedBarChart(BaseModel):
    """分组柱状图配置"""
    title: str = Field(description="图表标题")
    x_labels: List[str] = Field(description="X轴标签（分组）")
    series: List[Dict[str, Any]] = Field(
        description="多个系列数据，每个包含name和values"
    )
    x_title: Optional[str] = Field(default="", description="X轴标题")
    y_title: Optional[str] = Field(default="", description="Y轴标题")


class TableChart(BaseModel):
    """表格配置"""
    title: str = Field(description="表格标题")
    headers: List[str] = Field(description="表头")
    rows: List[List[Any]] = Field(description="行数据")
    column_widths: Optional[List[int]] = Field(default=None, description="列宽")


# ==================== 智能图表推荐模型 ====================

class ChartRecommendation(BaseModel):
    """图表推荐"""
    recommended_chart_type: ChartType = Field(description="推荐的图表类型")
    reason: str = Field(description="推荐理由")
    data_characteristics: str = Field(description="数据特征描述")
    alternative_charts: Optional[List[ChartType]] = Field(
        default=None, 
        description="备选图表类型"
    )


# ==================== 可视化洞察模型 ====================

class VisualizationInsight(BaseModel):
    """可视化洞察"""
    insight_type: Literal["trend", "comparison", "distribution", "correlation", "anomaly"] = Field(
        description="洞察类型"
    )
    description: str = Field(description="洞察描述")
    key_findings: List[str] = Field(description="关键发现")
    data_points: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="相关数据点"
    )


# ==================== 完整的可视化响应模型 ====================

class VisualizationResponse(BaseModel):
    """完整的可视化响应"""
    # 基本信息
    query: str = Field(description="原始查询")
    answer: str = Field(description="文本回答")
    
    # 图表配置
    has_visualization: bool = Field(description="是否包含可视化")
    chart_config: Optional[PlotlyChartConfig] = Field(
        default=None,
        description="Plotly图表配置"
    )
    
    # Timeline数据（用于Timeline组件）
    timeline_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="时间轴数据（用于Timeline组件）"
    )
    
    # 可视化类型（plotly或timeline）
    visualization_type: Optional[str] = Field(
        default="plotly",
        description="可视化类型：plotly或timeline"
    )
    
    # 简化配置（用于快速生成）
    simple_chart: Optional[Dict[str, Any]] = Field(
        default=None,
        description="简化的图表配置"
    )
    
    # 洞察
    insights: Optional[List[VisualizationInsight]] = Field(
        default=None,
        description="可视化洞察列表"
    )
    
    # 推荐
    recommendation: Optional[ChartRecommendation] = Field(
        default=None,
        description="图表推荐"
    )
    
    # 元数据
    data_source: Optional[str] = Field(default=None, description="数据来源")
    confidence_score: Optional[float] = Field(default=None, description="置信度分数")


# ==================== 图表生成请求模型 ====================

class ChartGenerationRequest(BaseModel):
    """图表生成请求"""
    query: str = Field(description="用户查询")
    data: Optional[Dict[str, Any]] = Field(default=None, description="原始数据")
    answer: Optional[str] = Field(default=None, description="文本回答")
    preferred_chart_type: Optional[ChartType] = Field(
        default=None,
        description="首选图表类型"
    )
    auto_detect: bool = Field(
        default=True,
        description="是否自动检测最佳图表类型"
    )


# ==================== 批量可视化模型 ====================

class BatchVisualizationResponse(BaseModel):
    """批量可视化响应"""
    total_queries: int = Field(description="总查询数")
    visualizations: List[VisualizationResponse] = Field(description="可视化列表")
    summary: str = Field(description="批量可视化摘要")

