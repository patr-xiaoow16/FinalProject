"""
年报分析报告的 Pydantic 数据模型
基于模板结构定义
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


# ==================== 财务指标模型 ====================

class FinancialIndicator(BaseModel):
    """单个财务指标"""
    name: str = Field(description="指标名称,如'营业收入'、'净利润'")
    value: str = Field(description="指标值,如'6.73亿元'")
    change_rate: Optional[str] = Field(default=None, description="同比变化率,如'14.53%'")
    change_direction: Optional[str] = Field(default=None, description="变化方向,如'增长'、'下降'")


class FinancialMetrics(BaseModel):
    """财务指标集合"""
    # 利润表指标
    revenue: FinancialIndicator = Field(description="营业收入")
    gross_margin: FinancialIndicator = Field(description="毛利率")
    operating_profit: FinancialIndicator = Field(description="营业利润")
    net_profit: FinancialIndicator = Field(description="净利润")
    non_recurring_net_profit: Optional[FinancialIndicator] = Field(default=None, description="扣非净利润")
    parent_net_profit: FinancialIndicator = Field(description="归母净利润")
    eps: FinancialIndicator = Field(description="摊薄每股收益")
    
    # 现金流量指标
    operating_cash_flow: Optional[FinancialIndicator] = Field(default=None, description="经营活动现金流量净额")
    investing_cash_flow: Optional[FinancialIndicator] = Field(default=None, description="投资活动现金流量净额")
    financing_cash_flow: Optional[FinancialIndicator] = Field(default=None, description="筹资活动现金流量净额")
    
    # 资产负债指标
    total_assets: Optional[FinancialIndicator] = Field(default=None, description="总资产")
    total_liabilities: Optional[FinancialIndicator] = Field(default=None, description="总负债")
    asset_liability_ratio: Optional[FinancialIndicator] = Field(default=None, description="资产负债率")


class SegmentData(BaseModel):
    """分部数据"""
    segment_name: str = Field(description="分部名称,如'房地产类'、'园区产业类'")
    revenue: str = Field(description="收入金额")
    change_rate: Optional[str] = Field(default=None, description="同比变化率")
    description: Optional[str] = Field(default=None, description="补充说明")


class BusinessData(BaseModel):
    """业务数据"""
    item_name: str = Field(description="业务项目名称")
    metrics: Dict[str, str] = Field(description="业务指标,如可出租面积、销售金额等")


# ==================== 财务点评模型 ====================

class FinancialCharts(BaseModel):
    """财务图表描述"""
    charts: List[str] = Field(description="图表描述列表,如'收入和归母净利润增速'、'利润率'等")


class PerformanceSummary(BaseModel):
    """业绩速览"""
    company_name: str = Field(description="公司名称")
    report_year: str = Field(description="报告年份")
    
    # 年初累计数据
    financial_metrics: FinancialMetrics = Field(description="财务指标")
    
    # 分部数据
    segment_data_by_product: Optional[List[SegmentData]] = Field(default=None, description="按产品分部数据")
    segment_data_by_region: Optional[List[SegmentData]] = Field(default=None, description="按地区分部数据")
    
    # 业务数据
    business_data: Optional[List[BusinessData]] = Field(default=None, description="业务数据列表")
    
    # 总结
    summary: str = Field(description="业绩速览总结,分析整体表现")


class PerformanceComparison(BaseModel):
    """业绩和预期的比较"""
    comparison_table: List[Dict[str, str]] = Field(
        description="对比表格,包含项目、实际值、预告值、比较结果"
    )
    summary: str = Field(description="对比总结")


class MetricAttribution(BaseModel):
    """单个指标变动归因"""
    metric_name: str = Field(description="指标名称")
    change_description: str = Field(description="变动情况描述")
    change_reasons: str = Field(description="变动原因分析")


class FinancialStatementTable(BaseModel):
    """财务报表表格视图"""
    title: str = Field(description="表格标题")
    headers: List[str] = Field(description="表头")
    rows: List[List[str]] = Field(description="表格行数据")
    insight: str = Field(description="表格洞察结论")


class FinancialStatementTables(BaseModel):
    """财务报表可视化表格集合"""
    balance_sheet_assets: FinancialStatementTable = Field(description="资产结构表")
    balance_sheet_liabilities: FinancialStatementTable = Field(description="负债结构表")
    income_statement_revenue: FinancialStatementTable = Field(description="营业收入结构表")
    income_statement_expense: FinancialStatementTable = Field(description="营业支出结构表")
    cash_flow: FinancialStatementTable = Field(description="现金流量明细表")


class FinancialReview(BaseModel):
    """财务点评(第一部分)"""
    summary: str = Field(description="财务点评总结")
    visualization_tables: FinancialStatementTables = Field(description="财务报表可视化表格")


# ==================== 业绩指引模型 ====================

class BusinessGuidance(BaseModel):
    """业绩指引(第二部分)"""
    guidance_period: str = Field(description="业绩预告期间")
    expected_performance: str = Field(description="预计的经营业绩描述")
    
    # 整体业绩指引
    parent_net_profit_range: Optional[str] = Field(default=None, description="归母净利润范围")
    parent_net_profit_growth_range: Optional[str] = Field(default=None, description="归母净利润增长率范围")
    non_recurring_profit_range: Optional[str] = Field(default=None, description="扣非净利润范围")
    eps_range: Optional[str] = Field(default=None, description="基本每股收益范围")
    revenue_range: Optional[str] = Field(default=None, description="营业收入范围")

    # 核心指标锚点
    key_metrics: Optional[List[str]] = Field(default=None, description="核心指标锚点")
    
    # 各业务的具体指引
    business_specific_guidance: Optional[List[str]] = Field(default=None, description="各业务具体指引")
    
    # 风险提示
    risk_warnings: Optional[List[str]] = Field(default=None, description="风险提示及其他相关说明")

    # 可视化生成指令（不直接面向用户展示）
    visualization_spec: Optional[Dict[str, Any]] = Field(
        default=None,
        description="业绩指引洞察对应的可视化生成指令"
    )
    visualization_insights: Optional[Dict[str, Any]] = Field(
        default=None,
        description="业绩指引可视化洞察（由大模型生成）"
    )


# ==================== 业务亮点模型 ====================

class BusinessHighlight(BaseModel):
    """单个业务亮点"""
    business_type: str = Field(description="业务类型,如'智慧交通业务'、'未来社区业务'")
    highlights: str = Field(description="业务亮点详细描述")
    achievements: Optional[List[str]] = Field(default=None, description="主要成就列表")


class BusinessHighlights(BaseModel):
    """业务亮点(第三部分)"""
    highlights: List[BusinessHighlight] = Field(description="各业务亮点列表")
    overall_summary: str = Field(description="业务亮点总结")
    key_metrics_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="关键业务指标汇总表"
    )


# ==================== 投资策略模型（相关性分析） ====================

class StrategyIndicator(BaseModel):
    """指标抽取项"""
    name: str = Field(description="指标名称")
    category: str = Field(description="指标分类，如'收益类'、'盈利类'、'风险类'、'业务类'、'估值类'、'风险敞口类'等")
    variable_role: str = Field(description="变量角色：'因变量'或'自变量'")
    value: Optional[str] = Field(default=None, description="指标取值（保留原始格式）")
    unit: Optional[str] = Field(default=None, description="单位，如'%'、'倍'")
    period: Optional[str] = Field(default=None, description="对应期间/年份")
    source_excerpt: Optional[str] = Field(default=None, description="来源片段（用于可追溯）")


class VariableTableRow(BaseModel):
    """输入变量表条目"""
    variable_type: str = Field(description="变量类型，如'收益类（因变量）'、'盈利类（自变量）'")
    metric: str = Field(description="具体指标名称")
    value: Optional[str] = Field(default=None, description="指标取值")
    period: Optional[str] = Field(default=None, description="对应期间/年份")
    unit: Optional[str] = Field(default=None, description="单位")


class CorrelationResult(BaseModel):
    """相关系数矩阵核心结果"""
    target_metric: str = Field(description="关联维度/被解释指标")
    driver_metric: str = Field(description="驱动指标")
    correlation: Optional[float] = Field(default=None, description="Pearson相关系数r，无法计算时为null")
    significance: Optional[str] = Field(default=None, description="显著性解读，如'强正相关'、'强负相关'、'中强相关'")
    interpretation: Optional[str] = Field(default=None, description="解读说明")
    data_points: Optional[int] = Field(default=None, description="样本数/时间点数量")


class StrategyConclusion(BaseModel):
    """核心结论与应用"""
    short_term: str = Field(description="短期配置结论")
    long_term: str = Field(description="长期配置结论")
    risk_control: str = Field(description="风险管控结论")
    key_signals: Optional[List[str]] = Field(default=None, description="关键指标信号列表")


class DataSufficiency(BaseModel):
    """数据充分性说明"""
    is_sufficient: bool = Field(description="是否满足相关性计算的样本要求")
    reason: Optional[str] = Field(default=None, description="不足原因说明")
    sample_description: Optional[str] = Field(default=None, description="样本说明，如'2019-2024年6期年报'")


class ClusteringVariableRow(BaseModel):
    """聚类变量设计表条目"""
    dimension: str = Field(description="聚类维度，如'估值维度'")
    metric: str = Field(description="标的聚类变量，如'市净率（PB）'")
    company_value: Optional[str] = Field(default=None, description="平安银行数据取值")
    industry_benchmark: Optional[str] = Field(default=None, description="行业对标数据（同年）")


class ClusteringGroupResult(BaseModel):
    """聚类结果条目"""
    group_name: str = Field(description="聚类组别名称")
    feature_profile: str = Field(description="标的特征")
    company_assignment: str = Field(description="平安银行归属")
    investor_profile: str = Field(description="适配投资需求特征")
    time_risk_bucket: str = Field(description="时间-风险分层")


class ClusteringConclusion(BaseModel):
    """聚类结论与应用"""
    current_position: str = Field(description="当前分组结论")
    upgrade_conditions: Optional[str] = Field(default=None, description="升级到稳健增长组条件")
    high_growth_conditions: Optional[str] = Field(default=None, description="进入高增长高弹性组条件")


class ClusteringModel(BaseModel):
    """聚类分析模型（客群-标的适配分组）"""
    method: str = Field(description="聚类方法，如'K-means'")
    k: int = Field(description="聚类组数")
    variable_table: List[ClusteringVariableRow] = Field(description="聚类变量设计表")
    group_results: List[ClusteringGroupResult] = Field(description="聚类结果表")
    conclusion: ClusteringConclusion = Field(description="核心结论与应用")


class ProfitForecastAndValuation(BaseModel):
    """投资策略（相关性分析模型，第四部分）"""
    indicator_extraction: List[StrategyIndicator] = Field(description="指标自动识别与抽取结果")
    variable_table: List[VariableTableRow] = Field(description="输入变量表")
    correlation_results: List[CorrelationResult] = Field(description="相关系数矩阵核心结果")
    strategy_conclusion: StrategyConclusion = Field(description="核心结论与应用")
    data_sufficiency: Optional[DataSufficiency] = Field(default=None, description="数据充分性说明")
    clustering_model: Optional[ClusteringModel] = Field(default=None, description="聚类分析模型（客群-标的适配分组）")
    notes: Optional[str] = Field(default=None, description="补充说明")


# ==================== 完整报告模型 ====================

class AnnualReportAnalysis(BaseModel):
    """完整的年报分析报告"""
    # 基本信息
    company_name: str = Field(description="公司名称")
    report_year: str = Field(description="报告年份")
    generation_date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d"),
        description="报告生成日期"
    )
    
    # 五大部分
    financial_review: FinancialReview = Field(description="一、财务点评")
    business_guidance: BusinessGuidance = Field(description="二、业绩指引")
    business_highlights: BusinessHighlights = Field(description="三、业务亮点")
    profit_forecast_and_valuation: ProfitForecastAndValuation = Field(description="四、投资策略（相关性分析）")
    
    # 总结
    overall_summary: str = Field(description="五、总结 - 综合所有部分的总结")
    
    # 参考来源
    references: Optional[List[str]] = Field(default=None, description="参考来源列表")


# ==================== 辅助模型 ====================

class ReportGenerationStatus(BaseModel):
    """报告生成状态"""
    status: str = Field(description="状态: pending, processing, completed, failed")
    progress: int = Field(description="进度百分比 0-100")
    current_step: str = Field(description="当前步骤描述")
    sections_completed: List[str] = Field(default_factory=list, description="已完成的章节")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class ReportSection(BaseModel):
    """单个报告章节"""
    section_name: str = Field(description="章节名称")
    section_content: str = Field(description="章节内容")
    generation_time: float = Field(description="生成耗时(秒)")
    tokens_used: Optional[int] = Field(default=None, description="使用的token数")


# ==================== 财务快照模型 ====================

class KeyFinancialMetric(BaseModel):
    """关键财务指标"""
    name: str = Field(description="指标名称，如'营业收入'、'净利润'、'资产总额'")
    value: Optional[str] = Field(default=None, description="指标值，如'100亿元'、'10亿元'")
    change_rate: Optional[str] = Field(default=None, description="同比变化率，如'+20%'、'-5%'")
    change_direction: Optional[str] = Field(default=None, description="变化方向：'增长'、'下降'、'持平'")
    is_missing: bool = Field(default=False, description="是否缺失该指标")


class FinancialSnapshot(BaseModel):
    """财务快照（用于财务概况）"""
    # 核心指标
    roe: Optional[KeyFinancialMetric] = Field(default=None, description="ROE（加权平均净资产收益率）")
    revenue: Optional[KeyFinancialMetric] = Field(default=None, description="营业收入")
    net_profit: Optional[KeyFinancialMetric] = Field(default=None, description="净利润")
    total_assets: Optional[KeyFinancialMetric] = Field(default=None, description="资产总额")
    net_interest_margin: Optional[KeyFinancialMetric] = Field(default=None, description="净息差")
    cost_income_ratio: Optional[KeyFinancialMetric] = Field(default=None, description="成本收入比")
    
    # 一句话结论
    verdict: str = Field(description="一句话核心结论")
    stage: Optional[str] = Field(default=None, description="公司阶段：增长/稳态/下行")
    profit_quality: Optional[str] = Field(default=None, description="赚钱质量描述")
    risk_level: Optional[str] = Field(default=None, description="风险级别：低/中/高")
    
    # 缺失字段
    missing_fields: List[str] = Field(default_factory=list, description="缺失的字段列表")

