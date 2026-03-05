"""
杜邦分析模型 - Pydantic v2
基于LlamaIndex文档和DeepSeek API最佳实践
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any
from decimal import Decimal
from datetime import datetime


# ==================== 财务数据提取模型 ====================

class FinancialDataExtraction(BaseModel):
    """财务数据提取模型（用于结构化输出）"""
    净利润: Optional[float] = Field(default=None, description="净利润（归属于母公司所有者的净利润），单位：元")
    营业收入: Optional[float] = Field(default=None, description="营业收入（营业总收入），单位：元")
    总资产: Optional[float] = Field(default=None, description="总资产（资产总计），单位：元")
    股东权益: Optional[float] = Field(default=None, description="股东权益（归属于母公司所有者权益），单位：元")
    流动资产: Optional[float] = Field(default=None, description="流动资产（流动资产合计），单位：元")
    非流动资产: Optional[float] = Field(default=None, description="非流动资产（非流动资产合计），单位：元")
    营业利润: Optional[float] = Field(default=None, description="营业利润，单位：元（可选）")
    总负债: Optional[float] = Field(default=None, description="总负债（负债合计），单位：元（可选）")
    加权平均净资产收益率: Optional[float] = Field(default=None, description="加权平均净资产收益率（ROE），单位：百分比（如10.08表示10.08%），这是年报中直接披露的指标，优先使用")
    总资产收益率: Optional[float] = Field(default=None, description="总资产收益率/总资产报酬率/ROA，单位：百分比（如1.23表示1.23%）")
    营业净利润率: Optional[float] = Field(default=None, description="营业净利润率/净利率，单位：百分比（如5.20表示5.20%）")
    资产周转率: Optional[float] = Field(default=None, description="资产周转率/总资产周转率，单位：倍（如0.85）")
    权益乘数: Optional[float] = Field(default=None, description="权益乘数，单位：倍（如2.10）")
    
    @field_validator('*', mode='before')
    @classmethod
    def convert_numeric_strings(cls, v):
        """将字符串数值转换为float"""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # 移除单位并转换
            v = v.replace(',', '').replace('元', '').replace('%', '').replace('倍', '').replace('次', '').strip()
            # 处理单位
            if '万亿' in v or '万亿元' in v:
                multiplier = 1000000000000
                v = v.replace('万亿', '').replace('万亿元', '')
            elif '千亿' in v or '千亿元' in v:
                multiplier = 100000000000
                v = v.replace('千亿', '').replace('千亿元', '')
            elif '亿' in v or '亿元' in v:
                multiplier = 100000000
                v = v.replace('亿', '').replace('亿元', '')
            elif '千万' in v or '千万元' in v:
                multiplier = 10000000
                v = v.replace('千万', '').replace('千万元', '')
            elif '万' in v or '万元' in v:
                multiplier = 10000
                v = v.replace('万', '').replace('万元', '')
            else:
                multiplier = 1
            
            try:
                return float(v) * multiplier
            except ValueError:
                return None
        return v


# ==================== 杜邦分析核心模型 ====================

class DupontMetric(BaseModel):
    """杜邦分析单个指标"""
    name: str = Field(description="指标名称，如'净资产收益率'、'资产净利率'")
    value: Optional[Decimal] = Field(description="指标值（小数形式），如0.1523表示15.23%")
    formatted_value: str = Field(description="格式化显示值，如'15.23%'或'1.52'")
    level: int = Field(description="层级：1=顶层ROE, 2=二级分解, 3=三级分解, 4=底层数据", ge=1, le=4)
    formula: str = Field(description="计算公式，如'ROE = ROA × 权益乘数'")
    parent_metric: Optional[str] = Field(default=None, description="父指标名称，用于构建树状结构")
    unit: str = Field(default="%", description="单位：%、倍、元等")
    
    @field_validator('value', mode='before')
    @classmethod
    def convert_to_decimal(cls, v):
        """自动转换为Decimal类型"""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str):
            # 移除百分号和逗号
            v = v.replace('%', '').replace(',', '').strip()
            return Decimal(v)
        if isinstance(v, Decimal):
            return v
        raise ValueError(f"无法转换为Decimal: {v}")
    
    @field_validator('value')
    @classmethod
    def validate_range(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """验证数值合理性（允许负值和大值）"""
        # 只做基本检查，不限制范围（因为某些指标可能很大）
        if v is None:
            return None
        if v < -1000 or v > 10000:
            # 只记录警告，不抛出异常
            import logging
            logging.warning(f"指标值 {v} 超出常见范围 [-1000, 10000]")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "净资产收益率",
                "value": "0.1523",
                "formatted_value": "15.23%",
                "level": 1,
                "formula": "ROE = 净利润 / 股东权益",
                "parent_metric": None,
                "unit": "%"
            }
        }


class DupontLevel1(BaseModel):
    """第一层：ROE顶层分解"""
    roe: DupontMetric = Field(description="净资产收益率 (ROE) = 资产净利率 × 权益乘数")
    roa: DupontMetric = Field(description="资产净利率 (ROA) = 净利润 / 总资产")
    equity_multiplier: DupontMetric = Field(description="权益乘数 = 总资产 / 股东权益")


class DupontLevel2(BaseModel):
    """第二层：ROA和权益乘数的进一步分解"""
    # ROA分解
    net_profit_margin: DupontMetric = Field(description="营业净利润率 = 净利润 / 营业收入")
    asset_turnover: DupontMetric = Field(description="资产周转率 = 营业收入 / 总资产")
    
    # 权益乘数分解
    total_assets: DupontMetric = Field(description="总资产（单位：元）")
    shareholders_equity: DupontMetric = Field(description="股东权益（单位：元）")


class DupontLevel3(BaseModel):
    """第三层：底层财务数据"""
    # 利润表数据
    net_income: DupontMetric = Field(description="净利润（单位：元）")
    revenue: DupontMetric = Field(description="营业总收入（单位：元）")
    
    # 资产负债表数据
    current_assets: DupontMetric = Field(description="流动资产（单位：元）")
    non_current_assets: DupontMetric = Field(description="非流动资产（单位：元）")
    
    # 可选的详细数据
    operating_profit: Optional[DupontMetric] = Field(default=None, description="营业利润（单位：元）")
    total_liabilities: Optional[DupontMetric] = Field(default=None, description="总负债（单位：元）")


class DupontTreeNode(BaseModel):
    """杜邦分析树状结构节点"""
    id: str = Field(description="节点ID")
    name: str = Field(description="节点名称")
    value: Optional[Decimal] = Field(description="节点值")
    formatted_value: str = Field(description="格式化值")
    level: int = Field(description="层级")
    children: List['DupontTreeNode'] = Field(default_factory=list, description="子节点列表")
    formula: Optional[str] = Field(default=None, description="计算公式")


class DupontAnalysis(BaseModel):
    """完整杜邦分析结果"""
    # 基本信息
    company_name: str = Field(description="公司名称")
    report_year: str = Field(description="报告年份，如'2023'")
    report_period: str = Field(description="报告期间，如'2023年度'、'2023年第三季度'")
    
    # 层级数据
    level1: DupontLevel1 = Field(description="第一层：ROE顶层分解")
    level2: DupontLevel2 = Field(description="第二层：ROA和权益乘数分解")
    level3: DupontLevel3 = Field(description="第三层：底层财务数据")
    
    # 树状结构（用于可视化）
    tree_structure: DupontTreeNode = Field(description="完整的树状结构数据")
    
    # AI分析洞察
    insights: List[str] = Field(
        default_factory=list,
        description="AI生成的分析洞察，如'ROE主要由资产周转率驱动'"
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="优势指标列表，如'净利润率高于行业平均'"
    )
    weaknesses: List[str] = Field(
        default_factory=list,
        description="劣势指标列表，如'资产周转率偏低'"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="改进建议，如'提高资产使用效率'"
    )
    
    # 元数据
    data_source: str = Field(description="数据来源，如'PDF第15页资产负债表'")
    extraction_method: str = Field(
        description="提取方法：'table_extraction'（表格提取）或'rag_query'（RAG查询）"
    )
    confidence_score: float = Field(
        default=1.0,
        description="数据置信度 [0-1]，1.0表示完全可信",
        ge=0.0,
        le=1.0
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="分析创建时间"
    )
    
    # 同比数据（可选）
    yoy_comparison: Optional[Dict[str, Any]] = Field(
        default=None,
        description="同比对比数据，包含上一年度的杜邦分析结果"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "某科技股份有限公司",
                "report_year": "2023",
                "report_period": "2023年度",
                "level1": {
                    "roe": {
                        "name": "净资产收益率",
                        "value": "0.1523",
                        "formatted_value": "15.23%",
                        "level": 1,
                        "formula": "ROE = ROA × 权益乘数",
                        "unit": "%"
                    }
                },
                "data_source": "PDF第15页财务报表",
                "extraction_method": "table_extraction",
                "confidence_score": 0.95
            }
        }


class DupontComparisonResult(BaseModel):
    """杜邦分析对比结果（多公司或多年度）"""
    comparison_type: str = Field(description="对比类型：'multi_company'（多公司）或'multi_year'（多年度）")
    analyses: List[DupontAnalysis] = Field(description="多个杜邦分析结果")
    comparison_insights: List[str] = Field(
        default_factory=list,
        description="对比分析洞察"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "comparison_type": "multi_year",
                "analyses": [],
                "comparison_insights": [
                    "2023年ROE较2022年提升3.2个百分点",
                    "主要驱动因素是净利润率的提升"
                ]
            }
        }


# 更新DupontTreeNode的forward reference
DupontTreeNode.model_rebuild()

