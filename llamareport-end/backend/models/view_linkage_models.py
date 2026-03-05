"""
视图联动相关的数据模型
用于定义视图摘要、联动请求和响应等数据结构
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from models.visualization_models import ChartType, VisualizationResponse


class LinkageRelationshipType(str, Enum):
    """联动关系类型"""
    DRILL_DOWN = "drill_down"  # 下钻关系
    COMPARISON = "comparison"  # 平行对比关系
    EXPLANATION = "explanation"  # 因果解释关系
    ROLL_UP = "roll_up"  # 上卷关系
    CORRELATION = "correlation"  # 关联关系
    EVOLUTION = "evolution"  # 时序演变关系
    VALIDATION = "validation"  # 验证关系


class ChartSummary(BaseModel):
    """视图摘要 - 机器可读的视图特征描述"""
    view_id: str = Field(description="视图唯一标识")
    chart_type: ChartType = Field(description="图表类型")
    title: str = Field(description="视图标题")
    original_question: Optional[str] = Field(default=None, description="原始查询问题")
    
    # 数据特征
    time_range: Optional[Dict[str, str]] = Field(
        default=None,
        description="时间范围，如 {'start': '2022', 'end': '2024'}"
    )
    data_dimensions: List[str] = Field(
        default_factory=list,
        description="数据维度，如 ['年份', '营业收入']"
    )
    key_metrics: List[str] = Field(
        default_factory=list,
        description="关键指标，如 ['营业收入', '净利润']"
    )
    
    # 模式特征（从数据中提取）
    patterns: Dict[str, Any] = Field(
        default_factory=lambda: {
            "trend": "未知",
            "turning_points": [],
            "anomalies": [],
            "distribution": "未知",
            "correlation_hints": []
        },
        description="数据模式特征"
    )
    
    # 原始数据引用
    raw_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="原始图表数据（traces, layout等）"
    )
    data_source: Optional[str] = Field(default=None, description="数据来源")


class ViewLinkageRequest(BaseModel):
    """视图联动请求"""
    source_view_id: str = Field(description="源视图ID")
    source_view_summary: ChartSummary = Field(description="源视图摘要")
    click_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="点击上下文，包含点击的元素、数据点、区域等"
    )
    original_query: str = Field(description="原始查询")
    original_answer: str = Field(description="原始回答")
    related_text: Optional[str] = Field(default=None, description="相关文本（如果有）")
    linkage_type: Optional[str] = Field(default="auto", description="联动类型：auto/verify/explain/navigate")


class NewViewInfo(BaseModel):
    """新视图信息"""
    view_id: str = Field(description="视图ID")
    view_type: str = Field(description="视图类型：verify/explain/navigate/comprehensive")
    visualization_response: VisualizationResponse = Field(description="可视化响应")
    data_validation: Dict[str, Any] = Field(
        default_factory=lambda: {
            "data_available": False,
            "data_quality": "unknown",
            "data_sources": [],
            "missing_fields": [],
            "validation_status": "pending"
        },
        description="数据验证信息"
    )
    description: str = Field(description="视图描述")
    related_cards: List[str] = Field(
        default_factory=list,
        description="关联的源卡片ID列表"
    )


class ViewLinkageResponse(BaseModel):
    """视图联动响应"""
    source_view_id: str = Field(description="源视图ID")
    
    # 对齐分析结果
    alignment_result: Dict[str, Any] = Field(
        default_factory=lambda: {
            "status": "unknown",
            "aligned_points": [],
            "unaligned_points": [],
            "missing_evidence": []
        },
        description="对齐分析结果"
    )
    
    # 综合洞察
    synthesis_insight: Dict[str, Any] = Field(
        default_factory=lambda: {
            "conclusion": "",
            "evidence_chain": [],
            "confidence": "unknown",
            "confidence_reason": ""
        },
        description="综合洞察"
    )
    
    # 新视图列表
    new_views: List[NewViewInfo] = Field(
        default_factory=list,
        description="新生成的视图列表"
    )
    
    # 视图关联关系
    view_relationships: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="视图关联关系"
    )
    
    # 推荐操作
    recommended_actions: List[str] = Field(
        default_factory=list,
        description="推荐的操作提示"
    )


class MultiCardLinkageRequest(BaseModel):
    """多卡片视图联动请求"""
    selected_cards: List[Dict[str, Any]] = Field(
        description="选中的可视化卡片列表，每个卡片包含：id, question, data"
    )
    overview_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="财务概况数据（可选）"
    )
    context_filter: Optional[Dict[str, Any]] = Field(
        default=None,
        description="上下文过滤（公司、年份等）"
    )
    linkage_mode: Optional[str] = Field(
        default="comprehensive",
        description="联动模式：comprehensive（综合分析）/ verify（验证型）/ explain（解释型）"
    )


class MultiCardLinkageResponse(BaseModel):
    """多卡片视图联动响应"""
    source_cards: List[str] = Field(description="源卡片ID列表")
    
    # 多卡片分析结果
    card_analysis: Dict[str, Any] = Field(
        default_factory=lambda: {
            "card_relationships": [],
            "key_insights": [],
            "data_gaps": []
        },
        description="多卡片分析结果"
    )
    
    # 综合洞察
    synthesis_insight: Dict[str, Any] = Field(
        default_factory=lambda: {
            "conclusion": "",
            "evidence_chain": [],
            "confidence": "unknown",
            "key_findings": []
        },
        description="综合洞察"
    )
    
    # 新视图列表
    new_views: List[NewViewInfo] = Field(
        default_factory=list,
        description="新生成的视图列表"
    )
    
    # 视图关系网络
    view_network: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="视图关系网络"
    )
    
    # 数据验证摘要（可选）
    data_validation_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="数据验证摘要"
    )

