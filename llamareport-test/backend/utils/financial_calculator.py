"""
Financial calculation helpers for DuPont analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Any, Tuple, List

from models.dupont_models import (
    DupontAnalysis,
    DupontLevel1,
    DupontLevel2,
    DupontLevel3,
    DupontMetric,
    DupontTreeNode,
)


@dataclass
class _ParsedFinancials:
    net_profit: Optional[float] = None
    revenue: Optional[float] = None
    total_assets: Optional[float] = None
    equity: Optional[float] = None
    current_assets: Optional[float] = None
    non_current_assets: Optional[float] = None
    operating_profit: Optional[float] = None
    total_liabilities: Optional[float] = None
    roe: Optional[float] = None  # percent (e.g. 10.08)
    roa: Optional[float] = None  # percent
    net_profit_margin: Optional[float] = None  # percent
    asset_turnover: Optional[float] = None  # times
    equity_multiplier: Optional[float] = None  # times


class DupontAnalyzer:
    """Compute DuPont analysis from extracted financial data."""

    def calculate_dupont_analysis(
        self,
        financial_data: Dict[str, Any],
        company_name: str,
        report_year: str,
    ) -> DupontAnalysis:
        parsed = self._parse_financials(financial_data)
        self._derive_missing_metrics(parsed)

        level1 = DupontLevel1(
            roe=self._metric_percent(
                "净资产收益率",
                parsed.roe,
                level=1,
                formula="ROE = 资产净利率 × 权益乘数",
                parent_metric=None,
            ),
            roa=self._metric_percent(
                "资产净利率",
                parsed.roa,
                level=1,
                formula="ROA = 净利润 / 总资产",
                parent_metric="净资产收益率",
            ),
            equity_multiplier=self._metric_times(
                "权益乘数",
                parsed.equity_multiplier,
                level=1,
                formula="权益乘数 = 总资产 / 股东权益",
                parent_metric="净资产收益率",
            ),
        )

        level2 = DupontLevel2(
            net_profit_margin=self._metric_percent(
                "营业净利润率",
                parsed.net_profit_margin,
                level=2,
                formula="净利率 = 净利润 / 营业收入",
                parent_metric="资产净利率",
            ),
            asset_turnover=self._metric_times(
                "资产周转率",
                parsed.asset_turnover,
                level=2,
                formula="资产周转率 = 营业收入 / 总资产",
                parent_metric="资产净利率",
            ),
            total_assets=self._metric_amount(
                "总资产",
                parsed.total_assets,
                level=2,
                formula="总资产",
                parent_metric="权益乘数",
            ),
            shareholders_equity=self._metric_amount(
                "股东权益",
                parsed.equity,
                level=2,
                formula="股东权益",
                parent_metric="权益乘数",
            ),
        )

        level3 = DupontLevel3(
            net_income=self._metric_amount(
                "净利润",
                parsed.net_profit,
                level=3,
                formula="净利润",
                parent_metric="营业净利润率",
            ),
            revenue=self._metric_amount(
                "营业收入",
                parsed.revenue,
                level=3,
                formula="营业收入",
                parent_metric="营业净利润率",
            ),
            current_assets=self._metric_amount(
                "流动资产",
                parsed.current_assets,
                level=3,
                formula="流动资产",
                parent_metric="总资产",
            ),
            non_current_assets=self._metric_amount(
                "非流动资产",
                parsed.non_current_assets,
                level=3,
                formula="非流动资产",
                parent_metric="总资产",
            ),
            operating_profit=self._metric_amount(
                "营业利润",
                parsed.operating_profit,
                level=3,
                formula="营业利润",
                parent_metric="净利润",
            )
            if parsed.operating_profit is not None
            else None,
            total_liabilities=self._metric_amount(
                "总负债",
                parsed.total_liabilities,
                level=3,
                formula="总负债",
                parent_metric="总资产",
            )
            if parsed.total_liabilities is not None
            else None,
        )

        tree_structure = self._build_tree(level1, level2, level3)
        insights, strengths, weaknesses, recommendations = self._build_insights(parsed)

        return DupontAnalysis(
            company_name=company_name,
            report_year=str(report_year),
            report_period=f"{report_year}年度",
            level1=level1,
            level2=level2,
            level3=level3,
            tree_structure=tree_structure,
            insights=insights,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            data_source="extracted_financial_data",
            extraction_method="rag_query",
            confidence_score=0.8 if parsed.net_profit else 0.6,
            yoy_comparison=None,
        )

    @staticmethod
    def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
        if numerator is None or denominator in (None, 0):
            return None
        try:
            return numerator / denominator
        except ZeroDivisionError:
            return None

    def _parse_financials(self, data: Dict[str, Any]) -> _ParsedFinancials:
        def pick(keys: List[str]) -> Optional[float]:
            for key in keys:
                if key in data and data[key] is not None:
                    try:
                        return float(data[key])
                    except (ValueError, TypeError):
                        continue
            return None

        return _ParsedFinancials(
            net_profit=pick(["净利润", "归母净利润", "归属于母公司所有者的净利润"]),
            revenue=pick(["营业收入", "营业总收入", "主营业务收入"]),
            total_assets=pick(["总资产", "资产总计", "资产合计"]),
            equity=pick(["股东权益", "所有者权益", "归属于母公司所有者权益"]),
            current_assets=pick(["流动资产", "流动资产合计"]),
            non_current_assets=pick(["非流动资产", "非流动资产合计"]),
            operating_profit=pick(["营业利润"]),
            total_liabilities=pick(["总负债", "负债合计"]),
            roe=pick(["加权平均净资产收益率", "ROE", "净资产收益率"]),
            roa=pick(["总资产收益率", "ROA", "资产净利率", "平均总资产收益率"]),
            net_profit_margin=pick(["营业净利润率", "净利率"]),
            asset_turnover=pick(["资产周转率", "总资产周转率"]),
            equity_multiplier=pick(["权益乘数"]),
        )

    def _derive_missing_metrics(self, parsed: _ParsedFinancials) -> None:
        if parsed.roe is None:
            ratio = self._safe_divide(parsed.net_profit, parsed.equity)
            parsed.roe = ratio * 100 if ratio is not None else None

        if parsed.roa is None:
            ratio = self._safe_divide(parsed.net_profit, parsed.total_assets)
            parsed.roa = ratio * 100 if ratio is not None else None

        if parsed.net_profit_margin is None:
            ratio = self._safe_divide(parsed.net_profit, parsed.revenue)
            parsed.net_profit_margin = ratio * 100 if ratio is not None else None

        if parsed.asset_turnover is None:
            turnover = self._safe_divide(parsed.revenue, parsed.total_assets)
            if turnover is None and parsed.roa is not None and parsed.net_profit_margin:
                turnover = self._safe_divide(parsed.roa, parsed.net_profit_margin)
            parsed.asset_turnover = turnover

        if parsed.equity_multiplier is None:
            multiplier = self._safe_divide(parsed.total_assets, parsed.equity)
            if multiplier is None and parsed.roe is not None and parsed.roa:
                multiplier = self._safe_divide(parsed.roe, parsed.roa)
            parsed.equity_multiplier = multiplier

    def _metric_percent(
        self,
        name: str,
        value: Optional[float],
        level: int,
        formula: str,
        parent_metric: Optional[str],
    ) -> DupontMetric:
        return DupontMetric(
            name=name,
            value=Decimal(str(value)) if value is not None else None,
            formatted_value=f"{value:.2f}%" if value is not None else "—",
            level=level,
            formula=formula,
            parent_metric=parent_metric,
            unit="%",
        )

    def _metric_times(
        self,
        name: str,
        value: Optional[float],
        level: int,
        formula: str,
        parent_metric: Optional[str],
    ) -> DupontMetric:
        return DupontMetric(
            name=name,
            value=Decimal(str(value)) if value is not None else None,
            formatted_value=f"{value:.2f}" if value is not None else "—",
            level=level,
            formula=formula,
            parent_metric=parent_metric,
            unit="倍",
        )

    def _metric_amount(
        self,
        name: str,
        value: Optional[float],
        level: int,
        formula: str,
        parent_metric: Optional[str],
    ) -> DupontMetric:
        return DupontMetric(
            name=name,
            value=Decimal(str(value)) if value is not None else None,
            formatted_value=self._format_amount(value),
            level=level,
            formula=formula,
            parent_metric=parent_metric,
            unit="元",
        )

    @staticmethod
    def _format_amount(value: Optional[float]) -> str:
        if value is None:
            return "—"
        abs_value = abs(value)
        if abs_value >= 1e8:
            return f"{value / 1e8:.2f}亿元"
        if abs_value >= 1e4:
            return f"{value / 1e4:.2f}万元"
        return f"{value:,.2f}元"

    @staticmethod
    def _build_tree(
        level1: DupontLevel1,
        level2: DupontLevel2,
        level3: DupontLevel3,
    ) -> DupontTreeNode:
        return DupontTreeNode(
            id="roe",
            name=level1.roe.name,
            value=level1.roe.value,
            formatted_value=level1.roe.formatted_value,
            level=1,
            formula=level1.roe.formula,
            children=[
                DupontTreeNode(
                    id="roa",
                    name=level1.roa.name,
                    value=level1.roa.value,
                    formatted_value=level1.roa.formatted_value,
                    level=1,
                    formula=level1.roa.formula,
                    children=[
                        DupontTreeNode(
                            id="net_profit_margin",
                            name=level2.net_profit_margin.name,
                            value=level2.net_profit_margin.value,
                            formatted_value=level2.net_profit_margin.formatted_value,
                            level=2,
                            formula=level2.net_profit_margin.formula,
                            children=[
                                DupontTreeNode(
                                    id="net_income",
                                    name=level3.net_income.name,
                                    value=level3.net_income.value,
                                    formatted_value=level3.net_income.formatted_value,
                                    level=3,
                                    formula=level3.net_income.formula,
                                    children=[],
                                ),
                                DupontTreeNode(
                                    id="revenue",
                                    name=level3.revenue.name,
                                    value=level3.revenue.value,
                                    formatted_value=level3.revenue.formatted_value,
                                    level=3,
                                    formula=level3.revenue.formula,
                                    children=[],
                                ),
                            ],
                        ),
                        DupontTreeNode(
                            id="asset_turnover",
                            name=level2.asset_turnover.name,
                            value=level2.asset_turnover.value,
                            formatted_value=level2.asset_turnover.formatted_value,
                            level=2,
                            formula=level2.asset_turnover.formula,
                            children=[],
                        ),
                    ],
                ),
                DupontTreeNode(
                    id="equity_multiplier",
                    name=level1.equity_multiplier.name,
                    value=level1.equity_multiplier.value,
                    formatted_value=level1.equity_multiplier.formatted_value,
                    level=1,
                    formula=level1.equity_multiplier.formula,
                    children=[
                        DupontTreeNode(
                            id="total_assets",
                            name=level2.total_assets.name,
                            value=level2.total_assets.value,
                            formatted_value=level2.total_assets.formatted_value,
                            level=2,
                            formula=level2.total_assets.formula,
                            children=[],
                        ),
                        DupontTreeNode(
                            id="shareholders_equity",
                            name=level2.shareholders_equity.name,
                            value=level2.shareholders_equity.value,
                            formatted_value=level2.shareholders_equity.formatted_value,
                            level=2,
                            formula=level2.shareholders_equity.formula,
                            children=[],
                        ),
                    ],
                ),
            ],
        )

    def _build_insights(
        self,
        parsed: _ParsedFinancials,
    ) -> Tuple[List[str], List[str], List[str], List[str]]:
        insights: List[str] = []
        strengths: List[str] = []
        weaknesses: List[str] = []
        recommendations: List[str] = []

        def dedupe(items: List[str]) -> List[str]:
            seen = set()
            result = []
            for item in items:
                if item in seen:
                    continue
                seen.add(item)
                result.append(item)
            return result

        def safe_ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
            if numerator is None or denominator in (None, 0):
                return None
            return numerator / denominator

        if parsed.roe is not None and parsed.roa is not None and parsed.equity_multiplier is not None:
            insights.append("ROE由资产净利率与权益乘数共同驱动。")
            if parsed.roa >= 8 and parsed.equity_multiplier <= 2:
                insights.append("ROE主要由盈利能力驱动，杠杆水平相对稳健。")
            if parsed.roa <= 3 and parsed.equity_multiplier >= 2.5:
                insights.append("ROE更多依赖杠杆贡献，经营回报偏弱。")
            if parsed.roa >= 6 and parsed.equity_multiplier >= 3:
                insights.append("ROE受盈利能力和杠杆双重推动，需关注杠杆风险。")
            if parsed.roe >= 15:
                strengths.append("净资产收益率处于较高水平。")
            elif parsed.roe <= 5:
                weaknesses.append("净资产收益率偏低，回报能力不足。")
                recommendations.append("关注提升利润率或改善资产周转效率。")
            if parsed.roa >= 6:
                strengths.append("资产净利率表现良好。")
            elif parsed.roa <= 2:
                weaknesses.append("资产净利率偏低。")
                recommendations.append("优化资产配置并提升盈利能力。")

        if parsed.net_profit_margin is not None:
            if parsed.net_profit_margin >= 15:
                strengths.append("净利润率较高，成本控制能力强。")
            elif parsed.net_profit_margin >= 10:
                strengths.append("净利润率表现较好。")
            elif parsed.net_profit_margin <= 3:
                weaknesses.append("净利润率偏低。")
                recommendations.append("关注成本控制与收入结构优化。")
            elif parsed.net_profit_margin <= 6:
                weaknesses.append("净利润率偏弱。")
                recommendations.append("评估毛利结构与费用率水平。")

        if parsed.asset_turnover is not None:
            if parsed.asset_turnover >= 1.5:
                strengths.append("资产周转率较高，资产使用效率强。")
            elif parsed.asset_turnover >= 1:
                strengths.append("资产周转率较高。")
            elif parsed.asset_turnover <= 0.3:
                weaknesses.append("资产周转率偏低。")
                recommendations.append("提升资产使用效率或优化资产结构。")
            elif parsed.asset_turnover <= 0.6:
                weaknesses.append("资产周转率偏弱。")
                recommendations.append("改善销售效率或压缩低效资产。")

        if parsed.equity_multiplier is not None:
            if parsed.equity_multiplier >= 4:
                insights.append("权益乘数很高，财务杠杆风险较大。")
                weaknesses.append("杠杆水平偏高。")
                recommendations.append("关注负债结构与偿债能力。")
            elif parsed.equity_multiplier >= 3:
                insights.append("权益乘数较高，财务杠杆水平偏高。")
            elif parsed.equity_multiplier <= 1.5:
                strengths.append("杠杆水平较低，财务结构稳健。")

        if parsed.net_profit_margin is not None and parsed.asset_turnover is not None:
            if parsed.net_profit_margin >= 10 and parsed.asset_turnover >= 1:
                insights.append("盈利能力与周转效率均较好，ROA表现具备支撑。")
            elif parsed.net_profit_margin < 6 and parsed.asset_turnover < 0.6:
                weaknesses.append("盈利能力与周转效率均偏弱。")
                recommendations.append("优先优化产品盈利性并提升资产周转。")
            elif parsed.net_profit_margin >= 10 and parsed.asset_turnover < 0.6:
                insights.append("盈利能力较强但周转偏慢，ROA提升空间在周转效率。")
                recommendations.append("加快存货与应收账款周转，释放资金占用。")
            elif parsed.net_profit_margin < 6 and parsed.asset_turnover >= 1:
                insights.append("周转效率尚可但盈利能力偏弱，ROA受利润率拖累。")
                recommendations.append("提升产品毛利或优化费用结构。")

        if parsed.net_profit is not None and parsed.revenue is not None:
            profit_margin = safe_ratio(parsed.net_profit, parsed.revenue)
            if profit_margin is not None and profit_margin < 0:
                weaknesses.append("净利润为负或明显承压。")
                recommendations.append("关注收入质量与期间费用控制。")

        if parsed.total_assets is not None and parsed.equity is not None:
            if parsed.total_assets > 0:
                leverage = safe_ratio(parsed.total_assets, parsed.equity)
                if leverage is not None and leverage >= 3.5:
                    insights.append("资产负债结构偏激进，需关注资本结构安全边际。")
                elif leverage is not None and leverage <= 1.8:
                    strengths.append("资产负债结构较稳健。")

        if parsed.total_liabilities is not None and parsed.total_assets is not None:
            liability_ratio = safe_ratio(parsed.total_liabilities, parsed.total_assets)
            if liability_ratio is not None:
                if liability_ratio >= 0.7:
                    weaknesses.append("资产负债率较高。")
                    recommendations.append("控制负债增速并优化融资结构。")
                elif liability_ratio <= 0.4:
                    strengths.append("资产负债率较低，风险承受能力较强。")

        if parsed.current_assets is not None and parsed.non_current_assets is not None:
            total_assets = parsed.current_assets + parsed.non_current_assets
            if total_assets > 0:
                current_ratio = parsed.current_assets / total_assets
                if current_ratio >= 0.7:
                    insights.append("资产结构偏流动化，资产弹性较高。")
                elif current_ratio <= 0.3:
                    insights.append("资产结构偏非流动化，资产周转可能受影响。")

        if parsed.operating_profit is not None and parsed.net_profit is not None:
            op_ratio = safe_ratio(parsed.operating_profit, parsed.net_profit)
            if op_ratio is not None:
                if op_ratio < 0:
                    weaknesses.append("营业利润与净利润背离，存在非经常性波动。")
                    recommendations.append("关注非经常性损益对利润的影响。")
                elif op_ratio < 0.6:
                    insights.append("净利润中非主营贡献较高，主营盈利质量需关注。")
                elif op_ratio >= 1:
                    strengths.append("主营盈利对净利润贡献较大。")

        return (
            dedupe(insights),
            dedupe(strengths),
            dedupe(weaknesses),
            dedupe(recommendations),
        )

