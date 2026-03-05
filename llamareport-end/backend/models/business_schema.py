from __future__ import annotations

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

# =========
# Enums / Types
# =========

IndustryCode = Literal[
    # Financial
    "banking", "insurance", "securities",
    # Non-financial (example set)
    "manufacturing", "internet_platform", "service",
    # Fallback
    "general_corporate",
    # Unknown
    "unknown"
]

MetricType = Literal["scale", "profitability", "risk", "efficiency"]

# 你可以扩展成更细的“指标ID”，这里只先用 string 做可扩展设计
MetricKey = str


# =========
# Core Models
# =========

class MetricGroup(BaseModel):
    """指标分组：四类指标清单"""
    scale: List[MetricKey] = Field(default_factory=list, description="规模类指标 keys")
    profitability: List[MetricKey] = Field(default_factory=list, description="盈利类指标 keys")
    risk: List[MetricKey] = Field(default_factory=list, description="风险类指标 keys")
    efficiency: List[MetricKey] = Field(default_factory=list, description="效率/运营类指标 keys")


class SegmentTemplate(BaseModel):
    """
    单个业务板块模板（可复用）
    - segment_id：稳定ID（用于代码/映射/版本兼容）
    - segment_name：展示名（中文）
    - business_scope：业务边界解释（给 LLM / 用户看的）
    """
    segment_id: str = Field(..., description="稳定、唯一的板块ID，如 retail_banking")
    segment_name: str = Field(..., description="板块中文名，如 零售银行业务")
    business_scope: str = Field(..., description="业务边界/定义")
    typical_products_or_services: List[str] = Field(default_factory=list, description="典型产品/服务清单")

    core_financial_metrics: MetricGroup = Field(default_factory=MetricGroup, description="该板块关注的核心指标组")
    strategic_signals: List[str] = Field(default_factory=list, description="战略信号/行为线索（可从年报文本中识别）")
    common_risks: List[str] = Field(default_factory=list, description="常见风险清单")
    long_term_role: str = Field("", description="该板块长期角色（增长引擎/现金牛/对冲器等）")

    # 可选：映射建议（帮助系统把“年报字段”映射到“指标key”）
    metric_alias_map: Dict[MetricKey, List[str]] = Field(
        default_factory=dict,
        description="指标key -> 年报常见写法/别名，用于检索与抽取"
    )


class IndustryTemplate(BaseModel):
    """一个行业的业务拆分模板集合"""
    industry: IndustryCode = Field(..., description="行业代码")
    template_version: str = Field("1.0.0", description="模板版本号，便于迭代与回溯")
    template_name: str = Field(..., description="模板名称，如 银行业-三板块拆分")
    description: str = Field("", description="模板说明")
    segments: List[SegmentTemplate] = Field(..., min_length=1, description="该行业的业务板块模板列表")

    # 可选：行业识别线索（供 LLM / 规则使用）
    industry_clues: List[str] = Field(default_factory=list, description="识别该行业的关键线索关键词/短语")


class TemplateLibrary(BaseModel):
    """
    全部模板库
    - 用于：系统启动加载、版本管理、LLM 选择行业模板等
    """
    model_config = ConfigDict(extra="forbid")

    library_version: str = Field("1.0.0", description="模板库版本")
    templates: List[IndustryTemplate] = Field(..., min_length=1)

    @model_validator(mode="after")
    def check_unique_ids(self):
        # 1) 行业唯一
        industries = [t.industry for t in self.templates]
        if len(industries) != len(set(industries)):
            raise ValueError("Duplicate industry code in templates")

        # 2) segment_id 在同一行业内唯一
        for template in self.templates:
            seg_ids = [s.segment_id for s in template.segments]
            if len(seg_ids) != len(set(seg_ids)):
                raise ValueError(f"Duplicate segment_id in industry={template.industry}")
        return self


# =========
# LLM Output Schemas (for “识别 / 生成”)
# =========

class IndustryClassificationResult(BaseModel):
    industry: IndustryCode
    confidence: float = Field(..., ge=0, le=1)
    evidence: List[str] = Field(default_factory=list, description="用于支撑判断的证据（来自年报文本的短句）")


class SegmentSelectionResult(BaseModel):
    """
    识别出的业务板块 + 与模板的对应关系
    """
    industry: IndustryCode
    selected_segments: List[str] = Field(..., description="segment_id list")
    reasoning: List[str] = Field(default_factory=list, description="选择理由（短句）")
    evidence: List[str] = Field(default_factory=list, description="年报证据（短句）")


class ExtractedSegmentMetrics(BaseModel):
    """
    单板块抽取出来的指标（先结构化到 key-value，后续可做数值校验/单位统一）
    """
    segment_id: str
    metrics: Dict[MetricKey, Any] = Field(default_factory=dict, description="指标key -> 数值或结构化对象")
    sources: Dict[MetricKey, List[str]] = Field(
        default_factory=dict,
        description="指标key -> 证据来源（页码/原文片段/表格行）"
    )


class SegmentAnalysisInsight(BaseModel):
    """
    第四部分输出：每个板块的“财务表现与战略联动”结论结构
    """
    segment_id: str
    headline: str = Field(..., description="一句话定性结论（增长/承压/修复/转型）")
    contribution: List[str] = Field(default_factory=list, description="对全行/全公司关键指标的贡献与拖累点")
    drivers: List[str] = Field(default_factory=list, description="变化驱动（因果链）")
    strategy_link: List[str] = Field(default_factory=list, description="战略动作与财务表现的对应关系")
    risks_and_watchlist: List[str] = Field(default_factory=list, description="风险点与建议跟踪指标")


class BusinessPerformanceReport(BaseModel):
    """
    第四部分总输出（含总览 + 分板块）
    """
    company_name: str
    fiscal_year: str
    industry: IndustryCode
    overall_summary: str = Field(..., description="第四部分总览：结构变化一句话总结")
    segment_insights: List[SegmentAnalysisInsight] = Field(..., min_length=1)

