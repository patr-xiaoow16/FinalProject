"""
视图联动功能核心模块
实现视图之间的智能联动分析和新视图生成
"""

import logging
import json
import re
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.view_linkage_models import (
    ChartSummary,
    ViewLinkageRequest,
    ViewLinkageResponse,
    MultiCardLinkageRequest,
    MultiCardLinkageResponse,
    NewViewInfo
)
from models.visualization_models import (
    ChartType,
    PlotlyChartConfig,
    ChartTrace,
    ChartLayout,
    VisualizationResponse,
    VisualizationInsight
)

from domain_knowledge_retriever import retrieve_domain_knowledge

logger = logging.getLogger(__name__)


class ChartSummaryGenerator:
    """视图摘要生成器"""
    
    def generate_summary(self, view_config: Optional[PlotlyChartConfig], view_id: str = "", title: str = "", question: str = "") -> ChartSummary:
        """
        从视图配置生成摘要
        
        Args:
            view_config: Plotly图表配置
            view_id: 视图ID
            title: 视图标题
            question: 原始问题
        
        Returns:
            ChartSummary: 视图摘要
        """
        try:
            # 提取基础信息
            chart_type = view_config.chart_type if view_config else ChartType.BAR
            chart_title = title or (view_config.layout.title if view_config and view_config.layout else "未知视图")
            
            # 提取时间范围和关键指标
            time_range = self._extract_time_range(view_config)
            key_metrics = self._extract_key_metrics(view_config, chart_title, question)
            data_dimensions = self._extract_data_dimensions(view_config)
            
            # 分析数据模式
            patterns = self._analyze_patterns(view_config)
            
            # 构建摘要
            summary = ChartSummary(
                view_id=view_id,
                chart_type=chart_type,
                title=chart_title,
                original_question=question,
                time_range=time_range,
                data_dimensions=data_dimensions,
                key_metrics=key_metrics,
                patterns=patterns,
                raw_data=self._extract_raw_data(view_config) if view_config else None
            )
            
            return summary
            
        except Exception as e:
            logger.error(f"生成视图摘要失败: {str(e)}")
            # 返回基础摘要
            return ChartSummary(
                view_id=view_id,
                chart_type=ChartType.BAR,
                title=title or "未知视图",
                original_question=question
            )
    
    def _extract_time_range(self, view_config: Optional[PlotlyChartConfig]) -> Optional[Dict[str, str]]:
        """提取时间范围"""
        if not view_config or not view_config.traces:
            return None
        
        try:
            # 从X轴数据中提取时间
            x_data = view_config.traces[0].x if view_config.traces else []
            if not x_data:
                return None
            
            # 尝试提取年份
            years = []
            for x in x_data:
                x_str = str(x)
                # 匹配年份（4位数字）
                year_match = re.search(r'20\d{2}', x_str)
                if year_match:
                    years.append(int(year_match.group()))
            
            if years:
                return {"start": str(min(years)), "end": str(max(years))}
        except:
            pass
        
        return None
    
    def _extract_key_metrics(self, view_config: Optional[PlotlyChartConfig], title: str, question: str) -> List[str]:
        """提取关键指标"""
        metrics = []
        
        # 从标题中提取
        financial_keywords = [
            '营业收入', '营收', '收入', '净利润', '利润', '资产', '负债',
            'ROE', 'ROA', '毛利率', '净利率', '总资产', '净资产', '股东权益',
            '现金流', '经营活动现金流', '投资活动现金流', '筹资活动现金流'
        ]
        
        text = f"{title} {question}".lower()
        for keyword in financial_keywords:
            if keyword.lower() in text:
                metrics.append(keyword)
        
        # 从Y轴标题中提取
        if view_config and view_config.layout and view_config.layout.yaxis_title:
            y_title = view_config.layout.yaxis_title.lower()
            for keyword in financial_keywords:
                if keyword.lower() in y_title and keyword not in metrics:
                    metrics.append(keyword)
        
        return list(set(metrics))  # 去重
    
    def _extract_data_dimensions(self, view_config: Optional[PlotlyChartConfig]) -> List[str]:
        """提取数据维度"""
        dimensions = []
        
        if view_config:
            if view_config.layout:
                if view_config.layout.xaxis_title:
                    dimensions.append(view_config.layout.xaxis_title)
                if view_config.layout.yaxis_title:
                    dimensions.append(view_config.layout.yaxis_title)
        
        return dimensions
    
    def _analyze_patterns(self, view_config: Optional[PlotlyChartConfig]) -> Dict[str, Any]:
        """分析数据模式"""
        patterns = {
            "trend": "未知",
            "turning_points": [],
            "anomalies": [],
            "distribution": "未知",
            "correlation_hints": []
        }
        
        if not view_config or not view_config.traces:
            return patterns
        
        try:
            # 提取Y轴数据
            y_data = []
            for trace in view_config.traces:
                if trace.y:
                    y_data.extend([float(y) for y in trace.y if y is not None])
            
            if len(y_data) >= 2:
                # 识别趋势
                patterns["trend"] = self._detect_trend(y_data)
                
                # 识别拐点
                if len(y_data) >= 3:
                    patterns["turning_points"] = self._detect_turning_points(y_data)
        except:
            pass
        
        return patterns
    
    def _detect_trend(self, values: List[float]) -> str:
        """识别趋势"""
        if len(values) < 2:
            return "数据不足"
        
        slopes = [values[i+1] - values[i] for i in range(len(values)-1)]
        avg_slope = sum(slopes) / len(slopes)
        
        threshold = (max(values) - min(values)) * 0.1  # 10%的变化阈值
        
        if avg_slope > threshold:
            return "上升"
        elif avg_slope < -threshold:
            return "下降"
        else:
            return "震荡"
    
    def _detect_turning_points(self, values: List[float]) -> List[Dict[str, Any]]:
        """识别拐点"""
        turning_points = []
        
        for i in range(1, len(values) - 1):
            if (values[i] > values[i-1] and values[i] > values[i+1]):
                turning_points.append({
                    "index": i,
                    "value": values[i],
                    "type": "peak"
                })
            elif (values[i] < values[i-1] and values[i] < values[i+1]):
                turning_points.append({
                    "index": i,
                    "value": values[i],
                    "type": "trough"
                })
        
        return turning_points
    
    def _extract_raw_data(self, view_config: PlotlyChartConfig) -> Dict[str, Any]:
        """提取原始数据"""
        return {
            "chart_type": view_config.chart_type.value,
            "traces_count": len(view_config.traces),
            "has_layout": view_config.layout is not None
        }


class LinkageGenerationEngine:
    """联动生成引擎（LLM驱动）"""
    
    def __init__(self, llm=None):
        self.llm = llm or Settings.llm
    
    async def generate_linkage_analysis(
        self,
        chart_summary: ChartSummary,
        original_query: str,
        original_answer: str,
        related_text: Optional[str] = None,
        exploration_question: Optional[str] = None,  # ⭐新增参数
        rag_engine=None,  # ⭐新增：RAG引擎，用于检索文档
        company_name: Optional[str] = None,  # ⭐新增：公司名，用于上下文过滤
        year: Optional[str] = None  # ⭐新增：年份，用于上下文过滤
    ) -> Dict[str, Any]:
        """
        使用LLM生成完整的联动分析（增强版：主动检索文档数据）
        
        Returns:
            包含对齐分析、综合推理、数据需求、视图生成策略的字典
        """
        try:
            # ⭐新增：主动检索相关文档数据
            retrieved_documents = ""
            if rag_engine and rag_engine.query_engine:
                try:
                    # 构建检索查询：结合视图信息和探索问题
                    retrieval_query = original_query
                    if exploration_question:
                        retrieval_query = f"{original_query} {exploration_question}"
                    
                    # 添加关键指标到检索查询
                    if chart_summary.key_metrics:
                        metrics_str = " ".join(chart_summary.key_metrics[:3])
                        retrieval_query = f"{retrieval_query} {metrics_str}"
                    
                    # 构建上下文过滤器
                    context_filter = {}
                    if company_name:
                        context_filter['company'] = company_name
                    if year:
                        context_filter['year'] = year
                    
                    # 执行RAG检索
                    logger.info(f"📚 检索相关文档数据: {retrieval_query[:100]}...")
                    rag_result = rag_engine.query(retrieval_query, context_filter=context_filter if context_filter else None)
                    
                    # 提取检索到的文档内容
                    if rag_result and rag_result.get('answer'):
                        retrieved_documents = rag_result['answer']
                        sources = rag_result.get('sources', [])
                        logger.info(f"✅ 检索到 {len(sources)} 个相关文档片段")
                        
                        # 如果文档内容太长，截取前3000字符
                        if len(retrieved_documents) > 3000:
                            retrieved_documents = retrieved_documents[:3000] + "..."
                    else:
                        logger.warning("⚠️ RAG检索未返回结果")
                except Exception as e:
                    logger.warning(f"⚠️ RAG检索失败，继续使用现有信息: {str(e)}")
                    retrieved_documents = ""
            
            # ⭐步骤3.5：检索领域知识（在生成联动查询之前）
            domain_knowledge_snippet = retrieve_domain_knowledge(
                key_metrics=chart_summary.key_metrics,
                original_query=original_query,
            )

            prompt = self._build_linkage_analysis_prompt(
                chart_summary, original_query, original_answer, related_text,
                exploration_question, retrieved_documents,
                domain_knowledge_snippet=domain_knowledge_snippet,
            )
            
            response = await self._call_llm(prompt)
            return self._parse_llm_response(response, domain_knowledge_snippet=domain_knowledge_snippet)
        except Exception as e:
            logger.error(f"联动分析失败: {str(e)}")
            return {
                "error": str(e),
                "alignment_result": {},
                "synthesis_insight": {},
                "data_requirements": [],
                "view_generation_strategy": []
            }
    
    def _build_linkage_analysis_prompt(
        self,
        chart_summary: ChartSummary,
        original_query: str,
        original_answer: str,
        related_text: Optional[str],
        exploration_question: Optional[str] = None,  # ⭐新增参数
        retrieved_documents: Optional[str] = None,  # ⭐新增：检索到的文档数据
        domain_knowledge_snippet: Optional[str] = None,  # ⭐步骤3.5：领域知识片段
    ) -> str:
        """构建联动分析的完整Prompt（整合探索问题、检索文档与领域知识）"""
        exploration_section = ""
        if exploration_question:
            exploration_section = f"""
### 5. 用户探索问题 ⭐新增
用户提出了以下探索问题，请重点关注：
"{exploration_question}"

**要求**：
- 在生成洞察时，优先回答用户的探索问题
- 推荐的新视图应该有助于回答用户的探索问题
- 如果用户的探索问题与视图内容相关，请重点分析
"""
        
        # ⭐新增：检索到的文档数据部分
        retrieved_docs_section = ""
        if retrieved_documents:
            retrieved_docs_section = f"""
### 6. 检索到的原始文档数据 ⭐新增（重要）
以下是从PDF和Excel文件中检索到的相关数据，请充分利用这些数据进行分析：

{retrieved_documents}

**重要提示**：
- 这些数据来自原始文档（PDF/Excel），是分析的基础
- 请结合视图数据和这些文档数据进行综合分析
- 如果文档数据与视图数据有差异，请指出并分析原因
- 在生成洞察时，优先使用文档中的具体数据
"""

        # ⭐步骤3.5：领域知识片段（在步骤4生成联动查询之前供参考）
        domain_knowledge_section = ""
        if domain_knowledge_snippet:
            domain_knowledge_section = f"""
### 【步骤3.5】领域知识（系统已检索，供步骤4参考）
以下为根据当前视图指标/查询检索到的领域知识，请在「生成联动查询」时优先使用其中的组成项作为检索维度，并参考建议图表类型。

{domain_knowledge_snippet}
"""

        return f"""
你是一个专业的财务分析专家，擅长分析图表与文本的关联，并生成深度洞察。

## 任务
分析以下视图和文本内容，生成联动分析结果。

## 输入信息

### 1. 源视图摘要
视图类型：{chart_summary.chart_type.value}
视图标题：{chart_summary.title}
时间范围：{chart_summary.time_range}
关键指标：{', '.join(chart_summary.key_metrics) if chart_summary.key_metrics else '未知'}
数据模式：
- 趋势：{chart_summary.patterns.get('trend', '未知')}
- 拐点：{chart_summary.patterns.get('turning_points', [])}
- 异常：{chart_summary.patterns.get('anomalies', [])}

### 2. 原始查询
{original_query}

### 3. 原始回答
{original_answer[:1000]}...

### 4. 相关文本（可选）
{related_text if related_text else '无'}
{exploration_section}
{retrieved_docs_section}

## ⭐联动规则：6步联动流程

### 【步骤1】提取交互上下文
当前上下文：
- 源视图：{chart_summary.title}（{chart_summary.chart_type.value}）
- 关键指标：{', '.join(chart_summary.key_metrics) if chart_summary.key_metrics else '未知'}
- 时间范围：{chart_summary.time_range}
- 数据模式：{chart_summary.patterns.get('trend', '未知')}，拐点：{chart_summary.patterns.get('turning_points', [])}
{f'- 用户探索问题：{exploration_question}' if exploration_question else ''}

### 【步骤2】识别联动意图
请分析用户的联动意图：
- 用户想要什么？（下钻明细、对比分析、解释原因、查看汇总、关联分析、演变过程、验证结论）
- 触发特征是什么？（点击的数据点、问题关键词、视图特征等）

### 【步骤3】确定联动关系类型（重要！）
根据联动意图，确定属于以下哪种关系类型：

**类型1：下钻关系（Drill-Down）**
- 触发特征：汇总类数据点、问题包含"明细/具体/拆分"、当前数据可进一步细分
- 典型路径：年度→季度→月度、总收入→业务板块→产品线、资产总额→资产分类→具体资产项
- 生成要求：保持指标一致，改变粒度，确保数据一致性（细分之和=汇总）

**类型2：平行对比关系（Comparison）**
- 触发特征：点击某一维度数据点、问题包含"对比/比较/差异"
- 典型路径：当期vs同期、实际vs预算、公司vs行业、A产品vsB产品、不同地区对比
- 生成要求：对比型图表（分组柱状图、双轴图），明确对比基准，突出差异

**类型3：因果解释关系（Explanation）**
- 触发特征：点击异常点/峰值/谷值/拐点、问题包含"为什么/原因/驱动因素"、明显趋势变化
- 典型路径：营收峰值→关键业务事件、利润下降→成本结构变化+收入下滑原因、现金流异常→回款周期+投资活动
- 生成要求：Timeline（事件时间轴）、因素拆解图（桑基图、堆叠柱状图）、驱动因素分析图

**类型4：上卷关系（Roll-Up）**
- 触发特征：问题包含"总体/整体/汇总"、需要宏观视角
- 典型路径：月度明细→季度汇总→年度总览、产品线收入→业务板块收入→总收入
- 生成要求：反向聚合数据，提供宏观视角，保持与下钻路径一致性

**类型5：关联关系（Correlation）**
- 触发特征：问题包含"关系/影响/相关性"、需要验证假设
- 典型路径：收入↔利润、成本↔费用率、ROE↔各驱动因素、客户数↔营收
- 生成要求：散点图（显示相关性）、双轴图（趋势对比）、相关性矩阵热力图

**类型6：时序演变关系（Evolution）**
- 触发特征：问题包含"演变/变化过程/历史/发展"、需要完整时间序列
- 典型路径：业务结构演变、风险演变过程、战略推进时间线、财务指标长期趋势
- 生成要求：Timeline（关键事件时间轴）、动态面积图（结构占比演变）、长期趋势折线图

**类型7：验证关系（Validation）**
- 触发特征：问题包含"是否真的/验证/证明"、需要多角度验证
- 典型路径：从多个维度验证同一结论（下钻验证、关联验证、对比验证）
- 生成要求：可能生成多个相互印证的视图，从不同维度验证，明确标注验证逻辑

**请选择最符合的关系类型，并说明理由。**

{domain_knowledge_section}

### 【步骤4】生成联动查询
根据确定的关系类型，生成数据检索查询：
- 需要检索什么数据？（指标、维度、时间范围）
- 数据来源建议？（从哪些文档/表格中检索）
- **若【步骤3.5】提供了该指标的组成项，则必须严格遵守：**
  - required_data.dimensions 与 required_data.required_fields **必须完整列出全部组成项**，每项单独一个元素，不得合并（如不得将"手续费及佣金净收入"与"其他非利息收入"合并为"非利息净收入"）、不得省略、不得改写名称。
  - 若提供了建议图表，chart_type 须采用建议图表（如堆叠柱状图、堆叠面积图）。
  - 示例：组成项为"利息净收入、手续费及佣金净收入、其他非利息收入"时，dimensions 应为 ["利息净收入", "手续费及佣金净收入", "其他非利息收入"]，required_fields 同上。

### 【步骤5】检索相关数据
（此步骤由系统自动执行，检索结果已包含在"检索到的原始文档数据"部分）

### 【步骤6】生成新视图和洞察
根据关系类型和数据检索结果，生成新视图和洞察。

### 第二步：执行分析（基于判断的流程）

#### 阶段一：对齐分析（Align）
根据判断的流程，分析视图特征与文本内容的对齐关系：
1. 时间匹配：图表中的时间点（拐点、异常点）是否与文本中的事件时间匹配？
2. 逻辑对齐：文本中的断言是否能解释图表中的变化？
3. 证据评估：现有证据是否充分？缺少哪些证据？

#### 阶段二：综合推理（Synthesize）
基于对齐结果和判断的流程，生成综合洞察：
1. 一句话结论（不超过80字，{f'优先回答探索问题：{exploration_question}' if exploration_question else '综合总结'}）
2. 证据链（列出图表特征和文本断言的对应关系）
3. 置信度评估（高/中/低）及原因
4. 关键发现（3-5条，{f'重点围绕探索问题' if exploration_question else '全面分析'}）

#### 阶段三：数据需求分析（基于判断的流程）
根据判断的流程，分析需要生成什么新视图：
1. **只推荐1个最关键的视图**（验证型/解释型/导航型）
2. 这个视图的数据需求：
   - 需要什么数据（指标、维度、时间范围）
   - 数据来源建议（从哪些文档/表格中检索）
   - 数据完整性要求（最少需要多少数据点）

#### 阶段四：视图生成策略（基于判断的流程）
根据数据可用性，确定视图生成策略：
1. 如果数据充足，如何生成完整视图？
2. 如果数据部分可用，如何生成带警告的视图？
3. 如果数据不足，如何生成数据请求视图或替代方案？

## 输出格式（JSON）

{{
    "alignment_result": {{
        "time_match": {{
            "status": "match/partial/no_match",
            "matched_points": [
                {{"chart_time": "2024Q2", "text_event": "渠道整合", "confidence": "high"}}
            ],
            "unmatched_points": []
        }},
        "logic_match": {{
            "status": "support/partial/no_support",
            "aligned_assertions": [
                {{"text_assertion": "...", "chart_feature": "...", "confidence": "high"}}
            ],
            "unaligned_assertions": []
        }},
        "evidence_assessment": {{
            "sufficiency": "sufficient/partial/insufficient",
            "missing_evidence": ["需要渠道拆分数据", "需要事件时间节点"],
            "confidence": "high/medium/low"
        }}
    }},
    "linkage_intent": {{
        "user_intent": "用户想要什么（下钻明细/对比分析/解释原因/查看汇总/关联分析/演变过程/验证结论）",
        "trigger_features": ["触发特征1", "触发特征2"],
        "intent_confidence": "high/medium/low"
    }},
    "relationship_type": "drill_down/comparison/explanation/roll_up/correlation/evolution/validation",
    "relationship_reasoning": "为什么选择这个关系类型，基于什么触发特征",
    "analysis_workflow": {{
        "analysis_type": "verify/explain/navigate",
        "focus_areas": ["重点1", "重点2"],
        "data_needs": ["需要的数据1", "需要的数据2"],
        "view_type_needed": "bar/line/scatter/pie",
        "reasoning": "为什么选择这个分析流程"
    }},
    "synthesis_insight": {{
        "conclusion": "一句话结论（{f'优先回答探索问题' if exploration_question else '综合总结'}）",
        "evidence_chain": [
            {{
                "source": "chart/text",
                "content": "...",
                "supports": "..."
            }}
        ],
        "confidence": "high/medium/low",
        "confidence_reason": "置信度原因",
        "key_findings": ["发现1", "发现2", "发现3"]
    }},
    "data_requirements": [
        {{
            "view_type": "verify/explain/navigate",
            "view_description": "视图描述（只生成1个视图）",
            "view_reason": "为什么需要这个视图（基于关系类型和分析流程判断）",
            "relationship_type": "drill_down/comparison/explanation/roll_up/correlation/evolution/validation",
            "relationship_specific_requirements": {{
                "drill_down": "下钻层级、细分维度、数据一致性要求",
                "comparison": "对比基准、对比维度、差异分析重点",
                "explanation": "需要解释的现象、关键事件、驱动因素",
                "roll_up": "汇总层级、聚合方式、宏观视角重点",
                "correlation": "关联指标、相关性分析重点、假设验证",
                "evolution": "演变时间范围、关键阶段、演变重点",
                "validation": "验证结论、验证维度、验证逻辑"
            }},
            "required_data": {{
                "data_type": "breakdown/time_series/events/comparison",
                "main_metric": "主要指标",
                "dimensions": ["维度1", "维度2"],
                "time_range": {{"start": "2022", "end": "2024"}},
                "required_fields": ["字段1", "字段2"],
                "min_data_points": 3,
                "data_source_hints": ["从利润表检索", "从业务描述中提取"]
            }}
注意：若步骤3.5给出了组成项（如利息净收入、手续费及佣金净收入、其他非利息收入），dimensions 与 required_fields 必须按组成项逐项填写，与步骤3.5完全一致，series 的 name 将使用这些名称。
        }}
    ],
    "view_generation_strategy": [
        {{
            "view_index": 0,
            "strategy": {{
                "if_data_sufficient": {{
                    "chart_type": "grouped_bar/line/scatter/pie/timeline",
                    "description": "根据关系类型生成相应图表：下钻用细分图、对比用分组柱状图、解释用时间轴、关联用散点图等",
                    "relationship_specific_config": {{
                        "drill_down": "细分柱状图/堆叠图，标注下钻层级",
                        "comparison": "分组柱状图/双轴图，突出差异",
                        "explanation": "Timeline/因素拆解图，标注关键事件",
                        "roll_up": "汇总柱状图，标注汇总层级",
                        "correlation": "散点图/双轴图，标注相关系数",
                        "evolution": "Timeline/动态面积图，标注关键阶段",
                        "validation": "多维度视图，标注验证逻辑"
                    }},
                    "key_points": ["重点展示零售渠道增长", "标注2024Q2拐点"]
                }},
                "if_data_partial": {{
                    "chart_type": "line",
                    "description": "生成折线图，但添加数据质量警告",
                    "warning_message": "数据不完整，仅显示2023-2024年数据",
                    "key_points": ["标注数据缺失"]
                }},
                "if_data_insufficient": {{
                    "view_type": "data_request",
                    "description": "生成数据请求视图",
                    "missing_data_description": "缺少渠道拆分数据",
                    "suggested_queries": [
                        "查询：营业收入 按渠道拆分",
                        "查询：营业收入 业务结构"
                    ],
                    "alternative_views": [
                        "如果无法获取拆分数据，可以生成总体营收趋势对比图"
                    ]
                }}
            }}
        }}
    ]
}}

请仔细分析，确保输出格式正确。
"""
    
    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        messages = [
            ChatMessage(
                role="system",
                content="你是一个专业的财务分析专家，擅长分析图表与文本的关联，并生成深度洞察。请严格按照JSON格式输出。"
            ),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = self.llm.chat(messages)
        return response.message.content
    
    def _extract_domain_preferred_charts(self, domain_knowledge_snippet: Optional[str]) -> List[str]:
        """从步骤3.5的领域知识片段中提取建议图表（按出现顺序）。"""
        if not domain_knowledge_snippet:
            return []
        text = str(domain_knowledge_snippet)
        matches = re.findall(r"建议图表[：:]\s*([^\n。]+)", text)
        charts: List[str] = []
        for m in matches:
            parts = re.split(r"[、,，/；;]|及", m)
            for p in parts:
                p = p.strip(" .。")
                if p and p not in charts:
                    charts.append(p)
        return charts[:5]

    def _apply_domain_chart_priority(self, parsed: Dict[str, Any], preferred_charts: List[str]) -> Dict[str, Any]:
        """若领域知识给出推荐图表，则优先注入/覆盖到联动策略。"""
        if not preferred_charts:
            return parsed

        workflow = parsed.get("analysis_workflow", {}) or {}
        workflow["preferred_chart_types"] = preferred_charts
        parsed["analysis_workflow"] = workflow

        if not isinstance(parsed.get("view_generation_strategy"), list) or not parsed.get("view_generation_strategy"):
            parsed["view_generation_strategy"] = [{"view_index": 0, "strategy": {}}]

        for view_strategy in parsed.get("view_generation_strategy", []):
            strategy = view_strategy.setdefault("strategy", {})
            if_sufficient = strategy.setdefault("if_data_sufficient", {})
            if_partial = strategy.setdefault("if_data_partial", {})
            if_sufficient["chart_type"] = preferred_charts[0]
            if_partial["chart_type"] = preferred_charts[0]
        return parsed

    def _parse_llm_response(self, response: str, domain_knowledge_snippet: Optional[str] = None) -> Dict[str, Any]:
        """解析LLM响应（改进：更好的JSON解析容错）"""
        preferred_charts = self._extract_domain_preferred_charts(domain_knowledge_snippet)
        try:
            # ⭐改进：尝试多种JSON提取方式
            content = response.strip()
            
            # 方式1：尝试提取JSON代码块
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(1))
                    parsed = self._ensure_required_fields(parsed)
                    return self._apply_domain_chart_priority(parsed, preferred_charts)
                except json.JSONDecodeError:
                    pass
            
            # 方式2：尝试提取JSON对象（更精确的匹配）
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    parsed = self._ensure_required_fields(parsed)
                    return self._apply_domain_chart_priority(parsed, preferred_charts)
                except json.JSONDecodeError:
                    pass
            
            # 方式3：尝试直接解析整个响应
            try:
                parsed = json.loads(content)
                parsed = self._ensure_required_fields(parsed)
                return self._apply_domain_chart_priority(parsed, preferred_charts)
            except json.JSONDecodeError:
                pass
            
            # 方式4：尝试修复常见的JSON错误（如单引号、尾随逗号等）
            fixed_content = content.replace("'", '"')  # 单引号转双引号
            fixed_content = re.sub(r',\s*}', '}', fixed_content)  # 移除尾随逗号
            fixed_content = re.sub(r',\s*]', ']', fixed_content)  # 移除数组尾随逗号
            try:
                parsed = json.loads(fixed_content)
                parsed = self._ensure_required_fields(parsed)
                return self._apply_domain_chart_priority(parsed, preferred_charts)
            except json.JSONDecodeError:
                pass
            
            # 所有方式都失败，返回降级结果
            raise ValueError("所有JSON解析方式都失败")
            
        except Exception as e:
            logger.error(f"无法解析LLM响应: {str(e)}")
            logger.debug(f"原始响应（前1000字符）: {response[:1000]}")
            # ⭐改进：即使解析失败，也创建一个基本的data_requirements，确保能生成视图
            parsed = {
                "error": "LLM响应解析失败",
                "raw_response": response[:500],
                "analysis_workflow": {
                    "analysis_type": "explain",
                    "focus_areas": ["综合分析"],
                    "data_needs": ["综合数据"],
                    "view_type_needed": "bar",
                    "reasoning": "解析失败，使用默认分析流程"
                },
                "alignment_result": {},
                "synthesis_insight": {
                    "conclusion": "基于选中视图的综合分析",
                    "key_findings": ["综合分析中"],
                    "confidence": "medium"
                },
                # ⭐关键：即使解析失败，也创建一个默认的data_requirements
                "data_requirements": [{
                    "view_type": "explain",
                    "view_description": "基于选中视图的综合分析视图",
                    "view_reason": "综合分析选中的视图",
                    "required_data": {
                        "data_type": "comparison",
                        "main_metric": "综合指标",
                        "dimensions": [],
                        "time_range": {"start": "2024", "end": "2024"},
                        "required_fields": [],
                        "min_data_points": 1,
                        "data_source_hints": ["从选中视图的数据中提取"]
                    }
                }],
                "view_generation_strategy": [{
                    "view_index": 0,
                    "strategy": {
                        "if_data_sufficient": {
                            "chart_type": "bar",
                            "description": "生成综合分析视图"
                        },
                        "if_data_partial": {
                            "chart_type": "bar",
                            "description": "生成综合分析视图（数据部分可用）"
                        },
                        "if_data_insufficient": {
                            "chart_type": "bar",
                            "description": "生成综合分析视图（数据不足）"
                        }
                    }
                }]
            }
            return self._apply_domain_chart_priority(parsed, preferred_charts)
    
    def _ensure_required_fields(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        """确保解析结果包含所有必需字段"""
        # 确保analysis_workflow存在
        if "analysis_workflow" not in parsed:
            parsed["analysis_workflow"] = {
                "analysis_type": "unknown",
                "focus_areas": [],
                "data_needs": [],
                "view_type_needed": "unknown",
                "reasoning": "LLM未返回分析流程判断"
            }
        
        # 确保data_requirements存在（即使为空列表）
        if "data_requirements" not in parsed:
            parsed["data_requirements"] = []
        
        # 确保view_generation_strategy存在
        if "view_generation_strategy" not in parsed:
            parsed["view_generation_strategy"] = []
        
        # 确保synthesis_insight存在
        if "synthesis_insight" not in parsed:
            parsed["synthesis_insight"] = {
                "conclusion": "综合分析中",
                "key_findings": [],
                "confidence": "medium"
            }
        
        return parsed


class DataRetriever:
    """数据检索与验证器"""
    
    def __init__(self, query_engine, rag_engine):
        self.query_engine = query_engine
        self.rag_engine = rag_engine
    
    async def retrieve_and_validate_data(
        self,
        view_requirement: Dict[str, Any],
        chart_summary: ChartSummary,
        company_name: str,
        year: str
    ) -> Dict[str, Any]:
        """
        检索并验证数据
        
        Returns:
            包含数据可用性、质量、检索结果等的字典
        """
        try:
            # 构建查询
            query = self._build_data_query(view_requirement, chart_summary, company_name, year)
            
            # 执行检索
            context_filter = {
                "company": company_name,
                "year": year
            }
            
            # 视图联动数据检索：多取文档，且 RAG 内部分先表格后 PDF
            result = self.rag_engine.query(query, context_filter=context_filter, top_k=28)
            
            # 【调试】打印 RAG 检索到的原始回答
            rag_answer = result.get("answer", "")
            print("\n" + "=" * 80)
            print("[调试] RAG 检索到的原始回答（用于数据提取）")
            print("=" * 80)
            print(rag_answer[:4000] + ("..." if len(rag_answer) > 4000 else ""))
            print("=" * 80 + "\n")
            
            # 提取结构化数据
            extracted_data = await self._extract_structured_data(
                result.get("answer", ""),
                view_requirement.get("required_data", {})
            )
            
            # 验证数据
            validation = self._validate_data_completeness(
                extracted_data,
                view_requirement.get("required_data", {}).get("required_fields", [])
            )
            
            # 评估质量
            quality = self._assess_data_quality(extracted_data, validation)
            
            # 【调试】打印提取后的结构化数据（base 检索）
            print("\n" + "=" * 80)
            print("[调试] 提取后的结构化数据（retrieve_and_validate_data）")
            print("=" * 80)
            print(json.dumps({k: v for k, v in extracted_data.items()}, ensure_ascii=False, indent=2)[:3000] + ("..." if len(json.dumps(extracted_data)) > 3000 else ""))
            print("=" * 80 + "\n")
            
            # 将 RAG 原始回答写入 retrieved_data.raw_text，供生成新视图时使用
            retrieved_data = dict(extracted_data)
            retrieved_data["raw_text"] = result.get("answer", "")
            
            return {
                "data_available": validation.get("is_complete", False) or quality != "low",
                "data_quality": quality,
                "retrieved_data": retrieved_data,
                "missing_fields": validation.get("missing_fields", []),
                "data_sources": result.get("sources", []),
                "validation_result": validation,
                "suggested_queries": self._generate_suggested_queries(
                    view_requirement, validation.get("missing_fields", [])
                ) if not validation.get("is_complete", False) else []
            }
        except Exception as e:
            logger.error(f"数据检索失败: {str(e)}")
            return {
                "data_available": False,
                "data_quality": "low",
                "retrieved_data": {},
                "missing_fields": [],
                "data_sources": [],
                "error": str(e)
            }
    
    def _build_data_query(
        self,
        view_requirement: Dict[str, Any],
        chart_summary: ChartSummary,
        company_name: str,
        year: str
    ) -> str:
        """构建数据检索查询"""
        required_data = view_requirement.get("required_data", {})
        data_type = required_data.get("data_type", "time_series")
        main_metric = required_data.get("main_metric", chart_summary.key_metrics[0] if chart_summary.key_metrics else "相关指标")
        
        if data_type == "breakdown":
            dimensions = required_data.get("dimensions") or required_data.get("required_fields") or []
            if dimensions:
                # 使用全部组成项构建查询，便于 RAG 检索到各系列数据（与领域知识一致）
                dim_str = "、".join(dimensions) if isinstance(dimensions[0], str) else str(dimensions[0])
                if len(dimensions) > 1:
                    dim_str = "、".join(str(d) for d in dimensions)
                return f"{company_name} {year}年 {main_metric} 按（{dim_str}）拆分 历史数据"
            dimension = "维度"
            return f"{company_name} {year}年 {main_metric} 按{dimension}拆分 历史数据"
        elif data_type == "events":
            time_range = required_data.get("time_range", {})
            start = time_range.get("start", year)
            end = time_range.get("end", year)
            return f"{company_name} {start}-{end}年 关键事件 时间节点 事件描述"
        elif data_type == "time_series":
            time_range = required_data.get("time_range", {})
            start = time_range.get("start", year)
            end = time_range.get("end", year)
            return f"{company_name} {start}-{end}年 {main_metric} 历史数据 时间序列"
        else:
            return f"{company_name} {year}年 {main_metric} 相关数据"
    
    async def _extract_structured_data(
        self,
        answer: str,
        required_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从LLM回答中提取结构化数据"""
        try:
            # 期望的系列名称（来自领域知识/联动分析，必须用于 series[].name）
            expected_series_names = required_data.get("dimensions") or required_data.get("required_fields") or []
            series_names_instruction = ""
            if expected_series_names and len(expected_series_names) >= 2:
                series_names_instruction = f"""
**重要**：以下系列名称必须原样用于 series[].name，不得增删改：{expected_series_names}
若有拆分/多系列数据，series 必须为与上述名称一一对应的 {len(expected_series_names)} 个系列，name 依次为上述各项。
"""

            # 使用LLM进行二次提取
            prompt = f"""
请从以下文本中提取结构化数据，用于生成图表。

文本内容：
{answer[:2000]}

数据类型：{required_data.get('data_type', 'time_series')}
期望维度/系列名称：{required_data.get('dimensions', []) or required_data.get('required_fields', [])}
{series_names_instruction}

请提取以下信息（JSON格式）：
1. labels: 时间标签列表（如["2022", "2023", "2024"]），一般为年份或时间点，不要用"点1、点2"等
2. series: 系列数据列表，每个系列包含 name 和 values（若是拆分数据，name 必须使用上面给出的系列名称）
3. values: 数值列表（仅当单一系列时使用）
4. unit: 数值单位（如"亿元"、"%"等）

示例输出（拆分数据）：
{{
    "labels": ["2022", "2023", "2024"],
    "series": [
        {{"name": "零售渠道", "values": [50, 55, 70]}},
        {{"name": "对公渠道", "values": [30, 28, 35]}}
    ],
    "unit": "亿元"
}}

示例输出（时间序列数据）：
{{
    "labels": ["2022", "2023", "2024"],
    "values": [100, 120, 150],
    "unit": "亿元"
}}
"""
            messages = [
                ChatMessage(role="system", content="你是一个数据提取专家，擅长从文本中提取结构化数据。"),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = Settings.llm.chat(messages)
            content = (response.message.content or "").strip()
            # 容错：先尝试整段解析，再尝试从 markdown 代码块或首段 JSON 提取
            data = None
            try:
                data = json.loads(content)
            except Exception:
                pass
            if data is None:
                json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', content)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                    except Exception:
                        pass
            if data is None:
                brace = re.search(r'\{[\s\S]*?"labels"[\s\S]*?"series"[\s\S]*?\}', content)
                if brace:
                    try:
                        data = json.loads(brace.group(0))
                    except Exception:
                        pass
            if data is None:
                raise ValueError("无法从响应中解析 JSON")
            return data
        except Exception as e:
            logger.warning(f"LLM数据提取失败，尝试正则提取: {str(e)}")
            # 降级：使用正则表达式提取（传入 required_data 以便使用期望的系列名称）
            return self._extract_data_with_regex(answer, required_data)
    
    def _extract_data_with_regex(self, text: str, required_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """使用正则表达式提取数据（降级方案）；若 required_data 含 dimensions/required_fields，则按该列表生成 series 名称。"""
        required_data = required_data or {}
        expected_series = required_data.get("dimensions") or required_data.get("required_fields") or []
        data = {"labels": [], "values": [], "series": [], "unit": ""}

        # ⭐优先：若已知期望的系列名称，先尝试按「指标名所在行」提取表格中的金额，避免把年份/占比当数值
        if expected_series and len(expected_series) >= 2:
            years = re.findall(r'20\d{2}', text)
            if years:
                data["labels"] = sorted(list(set(years)))[:10]
            n_labels = len(data["labels"]) or 3
            n_series = len(expected_series)
            # 表格感知：若文本含 | 且含指标名，按行提取每行后的金额（>50 视为金额，过滤占比）
            if '|' in text and any(n in text for n in expected_series):
                for name in expected_series:
                    row_vals = []
                    for line in text.split('\n'):
                        if name not in line:
                            continue
                        # 该行中的数字，过滤掉年份(2000-2030)和过小的占比
                        nums = re.findall(r'[\d,]+\.?\d*', line)
                        for n in nums:
                            try:
                                v = float(n.replace(',', ''))
                                if 2000 <= v <= 2030:
                                    continue
                                if v > 1e12:
                                    continue
                                # 单位亿元时只保留金额级(>=80)，过滤占比(如63.7%、10.9%)
                                if "亿元" in text and v < 80:
                                    continue
                                if v < 20:
                                    continue
                                row_vals.append(v)
                            except ValueError:
                                continue
                        if row_vals:
                            break
                    if row_vals and len(row_vals) >= n_labels:
                        row_vals = row_vals[:n_labels]
                    elif row_vals:
                        row_vals = row_vals[:n_labels]
                    data["series"].append({"name": name, "values": row_vals})
                if all(s.get("values") for s in data["series"]):
                    if not data["unit"] and "亿元" in text:
                        data["unit"] = "亿元"
                    return data
                data["series"] = []
            # 非表格或按行提取不足时：收集数值并过滤年份/占比后再均分
            numbers = re.findall(r'[\d,]+\.?\d*', text)
            num_list = []
            for n in numbers[:80]:
                try:
                    v = float(n.replace(',', ''))
                    if 2000 <= v <= 2030:
                        continue
                    if v < 20 and v != int(v):
                        continue
                    if abs(v) >= 1e12:
                        continue
                    num_list.append(v)
                except ValueError:
                    continue
            n_per_series = n_labels
            if num_list and len(num_list) >= n_series * n_per_series:
                for i, name in enumerate(expected_series):
                    start = i * n_per_series
                    data["series"].append({"name": name, "values": num_list[start: start + n_per_series]})
            elif num_list:
                for name in expected_series:
                    data["series"].append({"name": name, "values": num_list[:n_per_series]})
            else:
                for name in expected_series:
                    data["series"].append({"name": name, "values": []})
            if not data["labels"] and data["series"] and data["series"][0].get("values"):
                data["labels"] = [f"期{i+1}" for i in range(len(data["series"][0]["values"]))]
            for u in ['亿元', '万元', '%', '倍']:
                if u in text:
                    data["unit"] = u
                    break
            if data["series"]:
                return data
            data["series"] = []

        # 原有逻辑：无期望系列时按时间/数值提取
        years = re.findall(r'20\d{2}', text)
        if years:
            data["labels"] = sorted(list(set(years)))[:10]  # 去重并排序，最多10个
        
        # 提取季度：Q1、Q2、Q3、Q4或第一季度、第二季度等
        if not data["labels"]:
            quarters = re.findall(r'(?:第[一二三四]季度|Q[1-4]|第[1-4]季度)', text)
            if quarters:
                data["labels"] = quarters[:10]
        
        # 提取月份：1月、2月等
        if not data["labels"]:
            months = re.findall(r'\d+月', text)
            if months:
                data["labels"] = months[:12]
        
        # 提取指标名称（如果文本中有明确的指标列表）
        if not data["labels"]:
            # 尝试提取表格中的第一列（通常是标签）
            lines = text.split('\n')
            for line in lines[:20]:  # 只检查前20行
                # 如果行中包含数字，前面的部分可能是标签
                parts = line.split()
                if len(parts) >= 2:
                    # 检查是否有数字
                    has_number = any(re.search(r'\d', p) for p in parts)
                    if has_number:
                        # 第一个非数字部分可能是标签
                        for part in parts:
                            if not re.search(r'\d', part) and len(part) > 1:
                                if part not in data["labels"]:
                                    data["labels"].append(part)
                                if len(data["labels"]) >= 10:
                                    break
                        if len(data["labels"]) >= 10:
                            break
        
        # 提取数值
        numbers = re.findall(r'[\d,]+\.?\d*', text)
        if numbers:
            try:
                data["values"] = [float(n.replace(',', '')) for n in numbers[:10]]  # 最多10个
            except:
                pass
        
        # 如果labels和values数量不匹配，调整labels
        if data["labels"] and data["values"]:
            if len(data["labels"]) != len(data["values"]):
                # 如果labels多于values，截取labels
                if len(data["labels"]) > len(data["values"]):
                    data["labels"] = data["labels"][:len(data["values"])]
                # 如果values多于labels，生成默认labels
                elif len(data["values"]) > len(data["labels"]):
                    # 尝试从文本中提取更多labels，或者使用默认的
                    pass
        
        # 提取单位
        units = ['亿元', '万元', '元', '%', '倍']
        for unit in units:
            if unit in text:
                data["unit"] = unit
                break
        
        return data
    
    def _validate_data_completeness(
        self,
        retrieved_data: Dict[str, Any],
        required_fields: List[str]
    ) -> Dict[str, Any]:
        """验证数据完整性"""
        missing = []
        for field in required_fields:
            if field == "values" and not retrieved_data.get("values") and not retrieved_data.get("series"):
                missing.append("values")
            elif field == "labels" and not retrieved_data.get("labels"):
                missing.append("labels")
            elif field not in retrieved_data and field not in ["values", "labels"]:
                missing.append(field)
        
        completeness = 1.0 - (len(missing) / len(required_fields)) if required_fields else 1.0
        
        # 检查数据点数量
        values = retrieved_data.get("values", [])
        series = retrieved_data.get("series", [])
        point_count = len(values) if values else (len(series[0]["values"]) if series and series[0].get("values") else 0)
        
        return {
            "is_complete": len(missing) == 0,
            "missing_fields": missing,
            "completeness_score": completeness,
            "data_point_count": point_count
        }
    
    def _assess_data_quality(
        self,
        retrieved_data: Dict[str, Any],
        validation: Dict[str, Any]
    ) -> str:
        """评估数据质量"""
        completeness = validation.get("completeness_score", 0)
        point_count = validation.get("data_point_count", 0)
        
        if completeness >= 0.9 and point_count >= 3:
            return "high"
        elif completeness >= 0.7 and point_count >= 2:
            return "medium"
        else:
            return "low"
    
    def _generate_suggested_queries(
        self,
        view_requirement: Dict[str, Any],
        missing_fields: List[str]
    ) -> List[str]:
        """根据缺失字段生成建议查询"""
        suggestions = []
        main_metric = view_requirement.get("required_data", {}).get("main_metric", "相关指标")
        
        for field in missing_fields:
            if "时间" in field or "历史" in field:
                suggestions.append(f"查询历史数据：{main_metric} 历史数据")
            elif "拆分" in field or "维度" in field:
                suggestions.append(f"查询拆分数据：{main_metric} 按维度拆分")
            elif "对比" in field:
                suggestions.append(f"查询对比数据：{main_metric} 对比分析")
        
        return suggestions


class NewViewGenerator:
    """新视图生成器（LLM驱动）"""
    
    def __init__(self, query_engine, rag_engine, data_retriever, llm=None):
        self.query_engine = query_engine
        self.rag_engine = rag_engine
        self.data_retriever = data_retriever
        self.llm = llm or Settings.llm
        self._view_selection_doc_cache: Optional[str] = None

    def _load_view_selection_doc(self) -> str:
        """
        读取视图选择文档（可由业务持续维护）。
        优先读取 backend/视图选择.md，其次 domain_knowledge/视图选择.md。
        """
        if self._view_selection_doc_cache is not None:
            return self._view_selection_doc_cache
        candidate_paths = [
            Path(__file__).resolve().parent.parent / "视图选择.md",
            Path(__file__).resolve().parent.parent / "domain_knowledge" / "视图选择.md",
        ]
        for p in candidate_paths:
            try:
                if p.exists() and p.is_file():
                    self._view_selection_doc_cache = p.read_text(encoding="utf-8")
                    return self._view_selection_doc_cache
            except Exception:
                continue
        self._view_selection_doc_cache = ""
        return ""
    
    async def generate_views(
        self,
        linkage_analysis: Dict[str, Any],
        chart_summary: ChartSummary,
        company_name: str,
        year: str,
        max_views: int = 1,  # ⭐新增：限制生成视图数量，默认只生成1个
        synthesis_insight: Optional[Dict[str, Any]] = None,  # ⭐新增：综合洞察
        card_analysis: Optional[Dict[str, Any]] = None  # ⭐新增：多视图分析结果
    ) -> List[NewViewInfo]:
        """
        生成新视图（LLM驱动）
        
        Args:
            max_views: 最大生成视图数量，默认1
        
        Returns:
            新视图信息列表（最多max_views个）
        """
        data_requirements = linkage_analysis.get("data_requirements", [])
        view_strategies = linkage_analysis.get("view_generation_strategy", [])
        
        # ⭐限制：只处理第一个需求，生成1个视图
        if data_requirements:
            data_requirements = data_requirements[:max_views]
            view_strategies = view_strategies[:max_views] if view_strategies else []
        else:
            # ⭐如果没有数据需求，创建一个默认需求
            logger.warning("没有数据需求，创建默认视图需求")
            data_requirements = [{
                "view_type": "explain",
                "view_description": "基于选中视图的综合分析",
                "view_reason": "综合分析选中的视图",
                "required_data": {
                    "data_type": "comparison",
                    "main_metric": chart_summary.key_metrics[0] if chart_summary.key_metrics else "综合指标",
                    "dimensions": chart_summary.data_dimensions[:2] if chart_summary.data_dimensions else [],
                    "time_range": chart_summary.time_range or {"start": year, "end": year},
                    "required_fields": chart_summary.key_metrics[:3] if chart_summary.key_metrics else [],
                    "min_data_points": 1,
                    "data_source_hints": ["从选中视图的数据中提取"]
                }
            }]
            view_strategies = [{}]
        
        new_views = []
        
        for i, requirement in enumerate(data_requirements):
            try:
                strategy = view_strategies[i] if i < len(view_strategies) else {}
                
                # ⭐传递分析流程判断到requirement中
                if "analysis_workflow" in linkage_analysis:
                    requirement["analysis_workflow"] = linkage_analysis["analysis_workflow"]
                
                # ⭐优化：增强数据检索，主动从所有文档中检索相关数据
                data_result = await self._enhanced_data_retrieval(
                    requirement, chart_summary, company_name, year,
                    synthesis_insight, card_analysis
                )
                # 单位换算：元/万元 -> 亿元，便于绘图时数值更易读
                if data_result.get("retrieved_data"):
                    data_result["retrieved_data"] = self._convert_retrieved_data_units(data_result["retrieved_data"])
                
                # 根据数据验证结果，使用LLM生成视图
                if data_result["data_available"] and data_result["data_quality"] in ["high", "medium"]:
                    strategy_config = strategy.get("strategy", {}).get("if_data_sufficient", {})
                elif data_result["data_available"] and data_result["data_quality"] == "low":
                    strategy_config = strategy.get("strategy", {}).get("if_data_partial", {})
                else:
                    strategy_config = strategy.get("strategy", {}).get("if_data_insufficient", {})
                
                view = await self._generate_view_with_llm(
                    requirement, strategy_config, data_result, chart_summary,
                    synthesis_insight=synthesis_insight,  # ⭐传递综合洞察
                    card_analysis=card_analysis  # ⭐传递多视图分析结果
                )
                
                # 构建NewViewInfo
                view_info = NewViewInfo(
                    view_id=f"linkage_{chart_summary.view_id}_{i}",
                    view_type=requirement.get("view_type", "verify"),
                    visualization_response=view,
                    data_validation={
                        "data_available": data_result["data_available"],
                        "data_quality": data_result["data_quality"],
                        "data_sources": data_result.get("data_sources", []),
                        "missing_fields": data_result.get("missing_fields", []),
                        "validation_status": "passed" if data_result["data_available"] else "failed"
                    },
                    description=requirement.get("view_description", ""),
                    related_cards=[chart_summary.view_id]
                )
                
                new_views.append(view_info)
            except Exception as e:
                logger.error(f"生成视图失败: {str(e)}")
                logger.debug(f"错误详情: {traceback.format_exc()}")
                # 生成降级视图
                try:
                    data_result_local = data_result if 'data_result' in locals() else {}
                    view_info = self._create_fallback_view(requirement, data_result_local)
                    new_views.append(view_info)
                except Exception as fallback_error:
                    logger.error(f"生成降级视图也失败: {str(fallback_error)}")
                    # 最后的降级：创建一个最基本的视图
                    from models.visualization_models import VisualizationResponse, PlotlyChartConfig, ChartType, ChartTrace, ChartLayout
                    fallback_viz = VisualizationResponse(
                        chart_config=PlotlyChartConfig(
                            chart_type=ChartType.BAR,
                            traces=[ChartTrace(name="数据", x=["数据"], y=[0], type="bar")],
                            layout=ChartLayout(title="视图生成中，请稍候...", height=300)
                        ),
                        answer="视图生成遇到问题，正在尝试重新生成..."
                    )
                    view_info = NewViewInfo(
                        view_id=f"linkage_fallback_{chart_summary.view_id}_{i}",
                        view_type="explain",
                        visualization_response=fallback_viz,
                        data_validation={"data_available": False, "data_quality": "unknown"},
                        description="视图生成中...",
                        related_cards=[chart_summary.view_id]
                    )
                    new_views.append(view_info)
        
        # ⭐确保至少返回一个视图
        if not new_views:
            logger.warning("没有生成任何视图，创建默认视图")
            from models.visualization_models import VisualizationResponse, PlotlyChartConfig, ChartType, ChartTrace, ChartLayout
            default_viz = VisualizationResponse(
                chart_config=PlotlyChartConfig(
                    chart_type=ChartType.BAR,
                    traces=[ChartTrace(name="数据", x=["数据"], y=[0], type="bar")],
                    layout=ChartLayout(title="综合分析视图", height=300)
                ),
                answer="基于选中视图的综合分析"
            )
            default_view = NewViewInfo(
                view_id=f"linkage_default_{chart_summary.view_id}",
                view_type="explain",
                visualization_response=default_viz,
                data_validation={"data_available": False, "data_quality": "unknown"},
                description="综合分析视图",
                related_cards=[chart_summary.view_id]
            )
            new_views.append(default_view)
        
        return new_views
    
    async def _enhanced_data_retrieval(
        self,
        requirement: Dict[str, Any],
        chart_summary: ChartSummary,
        company_name: str,
        year: str,
        synthesis_insight: Optional[Dict[str, Any]] = None,
        card_analysis: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ⭐增强数据检索：主动从所有PDF和Excel文档中检索相关数据
        
        1. 基于视图需求检索数据
        2. 基于综合洞察检索补充数据
        3. 基于多视图分析结果检索关联数据
        4. 合并所有检索结果，提供完整的数据上下文
        """
        try:
            # 1. 基础数据检索（基于视图需求）
            base_result = await self.data_retriever.retrieve_and_validate_data(
                requirement, chart_summary, company_name, year
            )
            
            # 2. ⭐新增：基于综合洞察检索补充数据
            insight_data = {}
            insight_documents = ""
            if synthesis_insight and self.rag_engine:
                try:
                    # 构建基于洞察的检索查询
                    conclusion = synthesis_insight.get('conclusion', '')
                    key_findings = synthesis_insight.get('key_findings', [])
                    
                    if conclusion or key_findings:
                        insight_query = f"{company_name} {year}年"
                        if conclusion:
                            insight_query += f" {conclusion[:100]}"
                        if key_findings:
                            insight_query += f" {' '.join(key_findings[:3])}"
                        
                        logger.info(f"📚 基于综合洞察检索数据: {insight_query[:100]}...")
                        context_filter = {"company": company_name, "year": year}
                        insight_result = self.rag_engine.query(insight_query, context_filter=context_filter, top_k=20)
                        
                        if insight_result and insight_result.get('answer'):
                            insight_documents = insight_result['answer']
                            if len(insight_documents) > 2000:
                                insight_documents = insight_documents[:2000] + "..."
                            
                            # 提取结构化数据
                            insight_data = await self.data_retriever._extract_structured_data(
                                insight_documents,
                                requirement.get("required_data", {})
                            )
                            logger.info(f"✅ 基于洞察检索到 {len(insight_result.get('sources', []))} 个文档片段")
                except Exception as e:
                    logger.warning(f"基于洞察的数据检索失败: {str(e)}")
            
            # 3. ⭐新增：基于多视图分析结果检索关联数据
            relationship_data = {}
            relationship_documents = ""
            if card_analysis and self.rag_engine:
                try:
                    key_insights = card_analysis.get('key_insights', [])
                    card_relationships = card_analysis.get('card_relationships', [])
                    
                    if key_insights or card_relationships:
                        relationship_query = f"{company_name} {year}年"
                        if key_insights:
                            relationship_query += f" {' '.join(key_insights[:3])}"
                        if card_relationships:
                            rel_descriptions = [r.get('description', '')[:50] for r in card_relationships[:2]]
                            relationship_query += f" {' '.join(rel_descriptions)}"
                        
                        logger.info(f"📚 基于多视图关系检索数据: {relationship_query[:100]}...")
                        context_filter = {"company": company_name, "year": year}
                        relationship_result = self.rag_engine.query(relationship_query, context_filter=context_filter, top_k=20)
                        
                        if relationship_result and relationship_result.get('answer'):
                            relationship_documents = relationship_result['answer']
                            if len(relationship_documents) > 2000:
                                relationship_documents = relationship_documents[:2000] + "..."
                            
                            # 提取结构化数据
                            relationship_data = await self.data_retriever._extract_structured_data(
                                relationship_documents,
                                requirement.get("required_data", {})
                            )
                            logger.info(f"✅ 基于关系检索到 {len(relationship_result.get('sources', []))} 个文档片段")
                except Exception as e:
                    logger.warning(f"基于关系的数据检索失败: {str(e)}")
            
            # 4. ⭐合并所有检索结果
            merged_data = base_result.get("retrieved_data", {}).copy()
            
            # 合并洞察数据
            if insight_data:
                if "labels" in insight_data and not merged_data.get("labels"):
                    merged_data["labels"] = insight_data.get("labels", [])
                if "values" in insight_data:
                    if "values" in merged_data:
                        # 合并数值（去重）
                        merged_values = list(set(merged_data["values"] + insight_data["values"]))
                        merged_data["values"] = merged_values[:20]  # 限制最多20个数据点
                    else:
                        merged_data["values"] = insight_data.get("values", [])
                if "series" in insight_data:
                    if "series" in merged_data:
                        merged_data["series"].extend(insight_data["series"])
                    else:
                        merged_data["series"] = insight_data.get("series", [])
            
            # 合并关系数据
            if relationship_data:
                if "labels" in relationship_data and not merged_data.get("labels"):
                    merged_data["labels"] = relationship_data.get("labels", [])
                if "values" in relationship_data:
                    if "values" in merged_data:
                        merged_values = list(set(merged_data["values"] + relationship_data["values"]))
                        merged_data["values"] = merged_values[:20]
                    else:
                        merged_data["values"] = relationship_data.get("values", [])
                if "series" in relationship_data:
                    if "series" in merged_data:
                        merged_data["series"].extend(relationship_data["series"])
                    else:
                        merged_data["series"] = relationship_data.get("series", [])
            
            # 5. 合并文档内容（用于LLM理解上下文）
            all_documents = base_result.get("retrieved_data", {}).get("raw_text", "")
            if insight_documents:
                all_documents += f"\n\n【基于综合洞察的补充数据】\n{insight_documents}"
            if relationship_documents:
                all_documents += f"\n\n【基于多视图关系的补充数据】\n{relationship_documents}"
            
            # 6. 更新数据结果
            merged_result = base_result.copy()
            merged_result["retrieved_data"] = merged_data
            merged_result["retrieved_data"]["raw_text"] = all_documents  # ⭐保存完整文档内容
            merged_result["retrieved_data"]["insight_documents"] = insight_documents
            merged_result["retrieved_data"]["relationship_documents"] = relationship_documents
            
            # 重新评估数据质量
            if merged_data.get("values") or merged_data.get("series"):
                merged_result["data_available"] = True
                data_point_count = len(merged_data.get("values", [])) + sum(len(s.get("values", [])) for s in merged_data.get("series", []))
                if data_point_count >= 5:
                    merged_result["data_quality"] = "high"
                elif data_point_count >= 3:
                    merged_result["data_quality"] = "medium"
                else:
                    merged_result["data_quality"] = "low"
            
            logger.info(f"✅ 增强数据检索完成: 数据点={len(merged_data.get('values', []))}, 系列数={len(merged_data.get('series', []))}, 文档长度={len(all_documents)}")
            # 便于排查：输出检索到的结构化数据摘要（不含 raw_text）
            _summary = self._retrieved_data_summary(merged_data)
            logger.info(f"📊 检索数据摘要: {_summary}")
            # 【调试】打印最终用于生成视图的 retrieved_data（合并后）
            _detail = {k: v for k, v in merged_data.items() if k not in ("raw_text", "insight_documents", "relationship_documents")}
            print("\n" + "=" * 80)
            print("[调试] 最终用于生成视图的 retrieved_data（合并后，不含 raw_text）")
            print("=" * 80)
            print(json.dumps(_detail, ensure_ascii=False, indent=2)[:3500] + ("..." if len(json.dumps(_detail)) > 3500 else ""))
            print("=" * 80 + "\n")
            # 需要查看完整检索数据时，可将日志级别设为 DEBUG；此处不输出 raw_text 以免刷屏
            _detail = {k: v for k, v in merged_data.items() if k not in ("raw_text", "insight_documents", "relationship_documents")}
            logger.debug("📊 检索数据详情: %s", json.dumps(_detail, ensure_ascii=False, indent=2)[:3000])
            
            return merged_result
            
        except Exception as e:
            logger.error(f"增强数据检索失败: {str(e)}")
            # 降级到基础检索
            return await self.data_retriever.retrieve_and_validate_data(
                requirement, chart_summary, company_name, year
            )
    
    def _retrieved_data_summary(self, retrieved_data: Dict[str, Any]) -> str:
        """生成检索数据的可读摘要，便于在日志中查看（不含 raw_text）。"""
        labels = retrieved_data.get("labels", [])
        # 清理误提取的“年份”数值系列，避免干扰图表类型判断
        cleaned_series = []
        for s in (retrieved_data.get("series", []) or []):
            s_name = str(s.get("name", "")).strip().lower()
            if s_name in {"年份", "year"}:
                continue
            cleaned_series.append(s)
        retrieved_data["series"] = cleaned_series
        values = retrieved_data.get("values", [])
        series = retrieved_data.get("series", [])
        unit = retrieved_data.get("unit", "")
        parts = [f"labels={labels[:8]}{'...' if len(labels) > 8 else ''}", f"unit={unit!r}"]
        if series:
            parts.append("series=[" + ", ".join(f"{s.get('name', '?')}({len(s.get('values', []))}点)" for s in series[:5]) + ("]..." if len(series) > 5 else "]"))
        else:
            parts.append(f"values(len={len(values)})")
        return " | ".join(parts)
    
    def _convert_retrieved_data_units(self, retrieved_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        对检索数据做单位换算，使绘图时数值更易读（如 元/万元 -> 亿元）。
        返回新字典，不修改入参。换算后写入 display_unit（用于 Y 轴标题）。
        """
        out = dict(retrieved_data)
        unit = (out.get("unit") or "").strip()
        if not unit:
            return out
        scale = 1.0
        display_unit = unit
        if "元" in unit and "亿" not in unit and "万" not in unit:
            scale = 1e-8  # 元 -> 亿元
            display_unit = "亿元"
        elif "万元" in unit:
            scale = 1e-4  # 万元 -> 亿元
            display_unit = "亿元"
        elif "亿" in unit:
            display_unit = "亿元"
        if scale == 1.0 and unit == display_unit:
            out["display_unit"] = display_unit
            return out
        try:
            values = out.get("values", [])
            if values:
                out["values"] = [float(x) * scale for x in values]
            for s in out.get("series", []):
                v = s.get("values", [])
                if v:
                    s["values"] = [float(x) * scale for x in v]
            out["unit"] = display_unit
            out["display_unit"] = display_unit
        except (TypeError, ValueError):
            pass
        return out
    
    async def _generate_view_with_llm(
        self,
        requirement: Dict[str, Any],
        strategy: Dict[str, Any],
        data_result: Dict[str, Any],
        chart_summary: ChartSummary,
        synthesis_insight: Optional[Dict[str, Any]] = None,  # ⭐新增：综合洞察
        card_analysis: Optional[Dict[str, Any]] = None  # ⭐新增：多视图分析结果
    ) -> VisualizationResponse:
        """使用LLM生成视图配置"""
        try:
            prompt = self._build_view_generation_prompt(
                requirement, strategy, data_result, chart_summary,
                synthesis_insight=synthesis_insight,  # ⭐传递综合洞察
                card_analysis=card_analysis  # ⭐传递多视图分析结果
            )
            
            # 【调试】打印生成新视图的 prompt
            print("\n" + "=" * 80)
            print("[调试] 生成新视图的 Prompt（输入给 LLM）")
            print("=" * 80)
            print(prompt[:6000] + ("\n... [已截断]" if len(prompt) > 6000 else ""))
            print("=" * 80 + "\n")
            
            response = await self._call_llm_for_view(prompt)
            return self._parse_view_response(response, requirement, data_result, chart_summary)
        except Exception as e:
            logger.error(f"LLM生成视图失败: {str(e)}")
            return self._create_fallback_visualization_response(requirement, data_result)
    
    def _build_view_generation_prompt(
        self,
        requirement: Dict[str, Any],
        strategy: Dict[str, Any],
        data_result: Dict[str, Any],
        chart_summary: ChartSummary,
        synthesis_insight: Optional[Dict[str, Any]] = None,  # ⭐新增：综合洞察
        card_analysis: Optional[Dict[str, Any]] = None  # ⭐新增：多视图分析结果
    ) -> str:
        """构建视图生成的Prompt（优化：充分利用多视图综合分析结果）"""
        view_selection_doc = self._load_view_selection_doc()
        preferred_charts = requirement.get("analysis_workflow", {}).get("preferred_chart_types", [])
        preferred_chart_section = ""
        if preferred_charts:
            preferred_chart_section = f"""
### ⭐ 图表优先级规则（必须遵守）
步骤3.5（indicators.md）已推荐图表：{", ".join(preferred_charts)}
**你必须优先使用上述推荐图表类型。**
只有当该图表与数据结构完全不匹配时，才可降级到其他类型，并在description说明原因。
"""
        view_selection_section = ""
        if view_selection_doc:
            view_selection_section = f"""
### ⭐ 视图选择规范（来自视图选择.md）
以下文档给出了可选视图类型、示例代码和适用场景。请在**未命中步骤3.5推荐图表**时，按该规范选择最合适的图表：

{view_selection_doc[:2200]}
"""

        # 获取分析流程判断（如果有）
        analysis_workflow = requirement.get('analysis_workflow', {})
        workflow_section = ""
        if analysis_workflow:
            workflow_section = f"""
### 0. 分析流程判断（已确定）
分析类型：{analysis_workflow.get('analysis_type', 'unknown')}
分析重点：{', '.join(analysis_workflow.get('focus_areas', []))}
需要的数据：{', '.join(analysis_workflow.get('data_needs', []))}
视图类型：{analysis_workflow.get('view_type_needed', 'unknown')}
判断理由：{analysis_workflow.get('reasoning', '')}
"""
        
        # ⭐新增：综合洞察部分
        insight_section = ""
        if synthesis_insight:
            conclusion = synthesis_insight.get('conclusion', '')
            key_findings = synthesis_insight.get('key_findings', [])
            evidence_chain = synthesis_insight.get('evidence_chain', [])
            
            insight_section = f"""
### ⭐ 综合洞察（基于多个视图的分析结果）
**核心结论**：{conclusion}

**关键发现**：
{chr(10).join([f"- {finding}" for finding in key_findings[:5]])}

**证据链**（图表与文本的对应关系）：
{chr(10).join([f"- {ev.get('source', 'unknown')}: {ev.get('content', '')[:100]}..." for ev in evidence_chain[:3]]) if evidence_chain else "无"}

**置信度**：{synthesis_insight.get('confidence', 'medium')}
"""
        
        # ⭐新增：多视图关系部分
        relationship_section = ""
        if card_analysis:
            card_relationships = card_analysis.get('card_relationships', [])
            key_insights = card_analysis.get('key_insights', [])
            
            if card_relationships or key_insights:
                relationship_section = f"""
### ⭐ 多视图关系分析
**视图间关系**：
{chr(10).join([f"- {rel.get('type', 'unknown')}: {rel.get('description', '')[:100]}..." for rel in card_relationships[:3]]) if card_relationships else "无"}

**跨视图关键洞察**：
{chr(10).join([f"- {insight}" for insight in key_insights[:3]]) if key_insights else "无"}
"""
        
        return f"""
你是一个专业的可视化专家，擅长根据**多个视图的综合分析结果**生成最能体现关键发现的图表配置。

## ⭐ 重要背景
这是一个**基于多个视图的综合分析**任务。你需要生成一个视图，这个视图应该：
1. **体现综合多个视图的关键发现**（参考下面的"综合洞察"部分）
2. **展示跨视图的关系和模式**（参考下面的"多视图关系分析"部分）
3. **回答综合分析的核心问题**（参考下面的"视图需求"部分）

## 输入信息
{workflow_section}
{insight_section}
{relationship_section}
{preferred_chart_section}
{view_selection_section}
### 1. 视图需求
视图类型：{requirement.get('view_type', 'verify')}
视图描述：{requirement.get('view_description', '')}
生成原因：{requirement.get('view_reason', '')}

### 2. 生成策略
{json.dumps(strategy, ensure_ascii=False, indent=2)}

### 3. 可用数据
数据可用性：{data_result.get('data_available', False)}
数据质量：{data_result.get('data_quality', 'unknown')}
检索到的结构化数据：
{json.dumps({k: v for k, v in data_result.get('retrieved_data', {}).items() if k != 'raw_text' and k != 'insight_documents' and k != 'relationship_documents'}, ensure_ascii=False, indent=2)}

### ⭐ 4. 检索到的原始文档数据（来自所有PDF和Excel文件）
**重要**：以下是从上传的所有文档（PDF、Excel）中检索到的原始数据。请仔细分析这些数据，特别是表格中的数值，用于生成视图。

{data_result.get('retrieved_data', {}).get('raw_text', '暂无原始文档数据')}

{f'''
### ⭐ 5. 基于综合洞察的补充数据
{data_result.get('retrieved_data', {}).get('insight_documents', '')}
''' if data_result.get('retrieved_data', {}).get('insight_documents') else ''}

{f'''
### ⭐ 6. 基于多视图关系的补充数据
{data_result.get('retrieved_data', {}).get('relationship_documents', '')}
''' if data_result.get('retrieved_data', {}).get('relationship_documents') else ''}

缺失字段：{data_result.get('missing_fields', [])}

### 7. 源视图信息（参考）
源视图类型：{chart_summary.chart_type.value}
源视图标题：{chart_summary.title}
关键指标：{', '.join(chart_summary.key_metrics) if chart_summary.key_metrics else '未知'}

## ⭐ 视图生成要求（重要！）

**核心目标**：生成一个视图，这个视图应该**综合体现多个视图的关键发现**，而不仅仅是单个视图的简单展示。

### 生成原则：
1. **优先体现综合洞察**：
   - 如果综合洞察中有明确的结论和关键发现，视图应该**直接展示这些发现**
   - 例如：如果综合洞察发现"季度收入下降但年度指标上升"，视图应该展示这种对比关系
   - 例如：如果综合洞察发现"不同业务板块的差异化趋势"，视图应该展示这种差异

2. **展示跨视图关系**：
   - 如果多视图关系分析发现了视图间的关联（如因果关系、对比关系），视图应该体现这种关联
   - 例如：如果发现两个视图存在时间上的关联，视图应该展示时间序列的对比

3. **回答综合分析的核心问题**：
   - 视图应该能够回答"综合分析这些视图，我们发现了什么？"
   - 视图标题和描述应该清晰说明这是基于多个视图的综合发现

### ⭐ 数据使用策略（重要！）：

**核心原则**：必须基于检索到的原始文档数据（特别是PDF和Excel中的表格数据）生成视图，而不是凭空生成。

1. **如果数据充足**：
   - **优先使用检索到的原始文档数据**：仔细分析"检索到的原始文档数据"部分，特别是其中的表格数据
   - **提取具体数值**：从文档中提取具体的数值、时间序列、分类数据等
   - **基于真实数据生成视图**：使用提取的真实数据生成图表配置，确保x轴、y轴的数据都来自文档
   - 根据综合洞察和跨视图关系，生成最能体现关键发现的图表配置
   - 使用策略中建议的图表类型，或根据综合发现的特点选择最合适的类型
   - **重点**：图表应该能够直观展示综合洞察中的关键发现，且数据必须来自文档

2. **如果数据部分可用**：
   - 尽可能从文档中提取可用的数据
   - 生成图表配置，但添加数据质量警告
   - 在标题或描述中说明数据限制
   - 尽可能利用现有数据生成能体现综合发现的视图

3. **如果数据不足**：
   - 生成数据请求视图（表格或文本视图）
   - 清晰说明缺少什么数据
   - 提供建议的查询方式
   - 如果有替代方案，也可以生成替代视图

### ⭐ 数据提取要求：

1. **必须从文档中提取数据**：
   - 仔细阅读"检索到的原始文档数据"部分
   - 识别其中的表格、数值、时间序列等
   - 提取具体的数值用于生成图表

2. **数据格式要求**：
   - **x轴数据（labels）**：**必须**从文档中提取准确的时间、分类、指标名称等，例如：
     - 时间序列：["2022年", "2023年", "2024年"] 或 ["Q1", "Q2", "Q3", "Q4"]
     - 分类数据：["零售业务", "对公业务", "其他业务"] 或 ["利息收入", "手续费收入", "其他收入"]
     - **绝对不要使用** "点1"、"点2"、"点3" 这样的默认标签
   - y轴数据（values）：从文档中提取的具体数值
   - 多系列数据（series）：如果文档中有多个系列的数据，分别提取

3. **标签提取示例**：
   - 如果文档中有"2022年营业收入100亿元，2023年营业收入120亿元"，labels应该是["2022年", "2023年"]
   - 如果文档中有"零售业务收入50亿元，对公业务收入30亿元"，labels应该是["零售业务", "对公业务"]
   - 如果文档中有表格，第一列通常是labels，第二列及以后是values

3. **数据验证**：
   - 确保提取的数据是合理的（数值范围、时间顺序等）
   - 如果文档中没有足够的数据，明确说明并生成数据请求视图

## 输出格式（JSON）

{{
    "has_visualization": true/false,
    "chart_type": "bar/line/pie/scatter/area/grouped_bar/stacked_bar/heatmap/table",
    "title": "图表标题",
    "description": "图表描述（包含数据质量说明）",
    "traces": [
        {{
            "name": "系列名称",
            "x": ["x轴标签数据 - 必须从文档中提取准确的时间、分类、指标名称，例如：['2022年', '2023年', '2024年'] 或 ['零售业务', '对公业务', '其他业务']，绝对不要使用'点1'、'点2'等默认标签"],
            "y": [y轴数值数据 - 从文档中提取的具体数值],
            "type": "bar/line/scatter",
            "mode": "lines+markers"（如果是折线图）
        }}
    ],
    "layout": {{
        "title": "图表标题",
        "xaxis_title": "X轴标题",
        "yaxis_title": "Y轴标题",
        "height": 500,
        "showlegend": true
    }},
    "data_quality_note": "数据质量说明（如果有）",
    "missing_data_note": "缺失数据说明（如果有）",
    "suggested_queries": ["建议查询1", "建议查询2"]（如果数据不足）,
    "insights": [
        {{
            "insight_type": "trend/comparison/distribution/correlation/anomaly",
            "description": "一句洞察描述",
            "key_findings": ["发现1", "发现2"]
        }}
    ]
}}

## ⭐ 关键要求（必须遵守）：

1. **x轴标签（labels）必须准确**：
   - **必须**从"检索到的原始文档数据"中提取准确的x轴标签
   - 如果是时间序列，提取具体的时间：["2022年", "2023年", "2024年"] 或 ["Q1", "Q2", "Q3", "Q4"]
   - 如果是分类数据，提取具体的分类名称：["零售业务", "对公业务", "其他业务"] 或 ["利息收入", "手续费收入", "其他收入"]
   - **绝对禁止**使用 "点1"、"点2"、"点3"、"数据点1"、"数据点2" 等默认标签
   - 如果文档中没有明确的标签，尝试从表格第一列、时间描述、分类描述中提取

2. **y轴数值必须准确**：
   - 从文档中提取具体的数值
   - 确保数值与x轴标签一一对应

3. **数据验证**：
   - x轴标签和y轴数值的数量必须一致
   - 如果数量不一致，调整到一致的数量

请根据实际数据情况，生成最合适的视图配置。**特别注意：x轴标签必须从文档中提取，不能使用默认标签！**
"""
    
    async def _call_llm_for_view(self, prompt: str) -> str:
        """调用LLM生成视图配置"""
        messages = [
            ChatMessage(
                role="system",
                content="你是一个专业的可视化专家，擅长根据数据生成合适的图表配置。请严格按照JSON格式输出。"
            ),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = self.llm.chat(messages)
        return response.message.content

    def _normalize_chart_type(self, chart_type_raw: Any) -> ChartType:
        """将LLM输出的图表类型归一化为ChartType，避免无效值回退成bar。"""
        raw = str(chart_type_raw or "").strip().lower()
        alias_map = {
            "柱状图": "bar",
            "条形图": "bar",
            "折线图": "line",
            "曲线图": "line",
            "面积图": "area",
            "饼图": "pie",
            "散点图": "scatter",
            "热力图": "heatmap",
            "分组柱状图": "grouped_bar",
            "堆叠柱状图": "stacked_bar",
            "组合图": "combo",
            "multi-line": "multi_line",
            "multiline": "multi_line",
            "stackedbar": "stacked_bar",
            "groupbar": "grouped_bar",
        }
        raw = alias_map.get(raw, raw)
        if raw in {"scatter_line", "line_scatter"}:
            raw = "line"
        try:
            return ChartType(raw)
        except Exception:
            return ChartType.BAR

    def _default_trace_spec_for_chart(self, chart_type: ChartType) -> Tuple[str, Optional[str]]:
        """根据图表类型给出默认trace.type和mode。"""
        if chart_type in {ChartType.LINE, ChartType.MULTI_LINE, ChartType.AREA}:
            return "scatter", "lines+markers"
        if chart_type == ChartType.SCATTER:
            return "scatter", "markers"
        if chart_type == ChartType.PIE:
            return "pie", None
        return "bar", None
    
    def _parse_view_response(
        self,
        response: str,
        requirement: Dict[str, Any],
        data_result: Dict[str, Any],
        chart_summary: ChartSummary  # ⭐新增：用于提取labels
    ) -> VisualizationResponse:
        """解析LLM生成的视图配置"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                view_config = json.loads(json_match.group())
            else:
                raise ValueError("无法提取JSON")
        except Exception as e:
            logger.error(f"无法解析视图配置JSON: {str(e)}")
            logger.debug(f"原始响应（前500字符）: {response[:500]}")
            # ⭐修复：返回VisualizationResponse而不是NewViewInfo
            return self._create_fallback_visualization_response(requirement, data_result)
        
        preferred_chart_types = requirement.get("analysis_workflow", {}).get("preferred_chart_types", [])
        preferred_chart = preferred_chart_types[0] if preferred_chart_types else None
        normalized_chart_type = self._normalize_chart_type(preferred_chart or view_config.get("chart_type", "bar"))
        default_trace_type, default_mode = self._default_trace_spec_for_chart(normalized_chart_type)

        # ⭐改进：如果traces为空，使用data_result中的数据
        traces = []
        retrieved_data = data_result.get("retrieved_data", {})
        labels = retrieved_data.get("labels", [])
        
        if view_config.get("traces"):
            for trace_data in view_config.get("traces", []):
                # ⭐改进：如果LLM生成的trace没有x轴数据或x轴数据是默认值，使用检索到的labels
                trace_x = trace_data.get("x", [])
                trace_y = trace_data.get("y", [])
                
                # ⭐改进：检查x轴是否是默认值（点1、点2等），如果是则替换
                is_default_label = False
                if not trace_x:
                    is_default_label = True
                elif len(trace_x) > 0:
                    # 检查是否包含默认标签模式
                    default_patterns = ["点", "数据点", "point", "Point", "点1", "点2", "点3"]
                    is_default_label = any(any(pattern in str(x) for pattern in default_patterns) for x in trace_x[:3])
                
                if is_default_label or not trace_x:
                    # ⭐优先使用检索到的labels
                    if labels and len(labels) > 0:
                        if len(labels) == len(trace_y):
                            trace_x = labels
                        elif len(labels) > len(trace_y):
                            trace_x = labels[:len(trace_y)]
                        else:
                            # labels不足，尝试从原始文档中提取更多
                            raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                            if raw_text:
                                additional_labels = self._extract_labels_from_text(raw_text, len(trace_y) - len(labels))
                                if additional_labels:
                                    trace_x = labels + additional_labels[:len(trace_y) - len(labels)]
                                else:
                                    # 如果还是不够，使用源视图的指标名称或时间范围
                                    if chart_summary.key_metrics:
                                        trace_x = labels + chart_summary.key_metrics[:len(trace_y) - len(labels)]
                                    elif chart_summary.time_range:
                                        start = chart_summary.time_range.get("start", "")
                                        end = chart_summary.time_range.get("end", "")
                                        if start and end:
                                            trace_x = labels + [f"{start}年", f"{end}年"][:len(trace_y) - len(labels)]
                                    else:
                                        # 最后才使用默认标签，但至少尝试使用有意义的标签
                                        trace_x = labels + [f"指标{i+1}" for i in range(len(labels), len(trace_y))]
                            else:
                                # 没有原始文档，尝试使用源视图信息
                                if chart_summary.key_metrics:
                                    trace_x = labels + chart_summary.key_metrics[:len(trace_y) - len(labels)]
                                else:
                                    trace_x = labels + [f"指标{i+1}" for i in range(len(labels), len(trace_y))]
                    else:
                        # 没有labels，尝试从原始文档中提取
                        raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                        if raw_text:
                            extracted_labels = self._extract_labels_from_text(raw_text, len(trace_y))
                            if extracted_labels and len(extracted_labels) == len(trace_y):
                                trace_x = extracted_labels
                            else:
                                # 尝试使用源视图信息
                                if chart_summary.key_metrics and len(chart_summary.key_metrics) >= len(trace_y):
                                    trace_x = chart_summary.key_metrics[:len(trace_y)]
                                elif chart_summary.time_range:
                                    start = chart_summary.time_range.get("start", "")
                                    end = chart_summary.time_range.get("end", "")
                                    if start and end:
                                        trace_x = [f"{start}年", f"{end}年"][:len(trace_y)]
                                else:
                                    # 最后才使用默认标签
                                    trace_x = [f"指标{i+1}" for i in range(len(trace_y))]
                        else:
                            # 没有原始文档，使用源视图信息
                            if chart_summary.key_metrics and len(chart_summary.key_metrics) >= len(trace_y):
                                trace_x = chart_summary.key_metrics[:len(trace_y)]
                            else:
                                trace_x = [f"指标{i+1}" for i in range(len(trace_y))]
                
                trace_type = str(trace_data.get("type", "")).strip().lower() if trace_data.get("type") else ""
                # LLM返回line时，转为plotly可用的scatter+mode
                if trace_type in {"line", "折线图"}:
                    trace_type = "scatter"
                if trace_type in {"柱状图", "bar"}:
                    trace_type = "bar"
                if trace_type not in {"bar", "scatter", "pie", "heatmap"}:
                    trace_type = default_trace_type

                trace_mode = trace_data.get("mode")
                if not trace_mode and trace_type == "scatter":
                    trace_mode = default_mode or "lines+markers"

                trace = ChartTrace(
                    name=trace_data.get("name", "数据"),
                    x=trace_x,
                    y=trace_y,
                    type=trace_type,
                    mode=trace_mode,
                    text=trace_data.get("text"),
                    marker=trace_data.get("marker"),
                    line=trace_data.get("line"),
                    hovertemplate=trace_data.get("hovertemplate")
                )
                traces.append(trace)
        else:
            # ⭐如果没有traces，尝试从data_result中提取数据
            values = retrieved_data.get("values", [])
            series = retrieved_data.get("series", [])
            
            # ⭐改进：如果没有labels，尝试从原始文档中提取
            if not labels:
                raw_text = retrieved_data.get("raw_text", "")
                if raw_text:
                    # 尝试从原始文档中提取labels
                    labels = self._extract_labels_from_text(raw_text, len(values) if values else (len(series[0]["values"]) if series and series[0].get("values") else 0))
            
            if series:
                # 多系列数据
                for s in series[:3]:
                    series_labels = labels if labels else []
                    series_values = s.get("values", [])
                    
                    # 如果labels数量不匹配，调整
                    if series_labels and len(series_labels) != len(series_values):
                        if len(series_labels) > len(series_values):
                            series_labels = series_labels[:len(series_values)]
                        else:
                            # ⭐改进：尝试从原始文档中提取更多labels
                            raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                            if raw_text:
                                additional_labels = self._extract_labels_from_text(raw_text, len(series_values) - len(series_labels))
                                if additional_labels:
                                    series_labels = series_labels + additional_labels[:len(series_values) - len(series_labels)]
                                else:
                                    series_labels = series_labels + [f"指标{i+1}" for i in range(len(series_labels), len(series_values))]
                            else:
                                series_labels = series_labels + [f"指标{i+1}" for i in range(len(series_labels), len(series_values))]
                    
                    # ⭐如果没有labels，尝试从原始文档中提取
                    if not series_labels:
                        raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                        if raw_text:
                            series_labels = self._extract_labels_from_text(raw_text, len(series_values))
                        if not series_labels:
                            series_labels = [f"指标{i+1}" for i in range(len(series_values))]
                    
                    traces.append(ChartTrace(
                        name=s.get("name", "系列"),
                        x=series_labels,
                        y=series_values,
                        type=default_trace_type,
                        mode=default_mode
                    ))
            elif values:
                # 单系列数据
                # 如果labels数量不匹配，调整
                final_labels = labels if labels else []
                if final_labels and len(final_labels) != len(values):
                    if len(final_labels) > len(values):
                        final_labels = final_labels[:len(values)]
                    else:
                        # ⭐改进：尝试从原始文档中提取更多labels
                        raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                        if raw_text:
                            additional_labels = self._extract_labels_from_text(raw_text, len(values) - len(final_labels))
                            if additional_labels:
                                final_labels = final_labels + additional_labels[:len(values) - len(final_labels)]
                            else:
                                final_labels = final_labels + [f"指标{i+1}" for i in range(len(final_labels), len(values))]
                        else:
                            final_labels = final_labels + [f"指标{i+1}" for i in range(len(final_labels), len(values))]
                
                # ⭐如果没有labels，尝试从原始文档中提取
                if not final_labels:
                    raw_text = data_result.get("retrieved_data", {}).get("raw_text", "")
                    if raw_text:
                        final_labels = self._extract_labels_from_text(raw_text, len(values))
                    if not final_labels:
                        final_labels = [f"指标{i+1}" for i in range(len(values))]
                
                traces.append(ChartTrace(
                    name="数据",
                    x=final_labels,
                    y=values,
                    type=default_trace_type,
                    mode=default_mode
                ))
            else:
                # 完全没有数据，创建空视图
                traces.append(ChartTrace(
                    name="数据",
                    x=["暂无数据"],
                    y=[0],
                    type=default_trace_type,
                    mode=default_mode
                ))
        
        # 构建ChartLayout（Y 轴带单位、图例显示）
        layout_data = view_config.get("layout", {})
        yaxis_title = layout_data.get("yaxis_title", "数值")
        if yaxis_title == "数值":
            du = data_result.get("retrieved_data", {}).get("display_unit") or data_result.get("retrieved_data", {}).get("unit")
            if du:
                yaxis_title = f"数值({du})"
        layout = ChartLayout(
            title=layout_data.get("title", view_config.get("title", requirement.get("view_description", "综合分析视图"))),
            xaxis_title=layout_data.get("xaxis_title", "维度"),
            yaxis_title=yaxis_title,
            height=layout_data.get("height", 500),
            showlegend=layout_data.get("showlegend", True)
        )
        
        # 构建PlotlyChartConfig
        chart_type = normalized_chart_type
        
        chart_config = PlotlyChartConfig(
            chart_type=chart_type,
            traces=traces,
            layout=layout
        )
        
        # 构建描述
        description = view_config.get("description", requirement.get("view_description", "综合分析视图"))
        if view_config.get("data_quality_note"):
            description += f"\n\n⚠️ {view_config['data_quality_note']}"
        if view_config.get("missing_data_note"):
            description += f"\n\n📋 缺失数据：{view_config['missing_data_note']}"

        # 透传LLM洞察到前端
        parsed_insights: List[VisualizationInsight] = []
        raw_insights = view_config.get("insights", []) if isinstance(view_config.get("insights", []), list) else []
        for insight_item in raw_insights[:5]:
            if not isinstance(insight_item, dict):
                continue
            try:
                insight_type = str(insight_item.get("insight_type", "trend")).lower()
                if insight_type not in {"trend", "comparison", "distribution", "correlation", "anomaly"}:
                    insight_type = "trend"
                parsed_insights.append(
                    VisualizationInsight(
                        insight_type=insight_type,
                        description=str(insight_item.get("description", "")).strip() or "基于当前视图生成的洞察",
                        key_findings=[
                            str(x).strip()
                            for x in insight_item.get("key_findings", [])
                            if str(x).strip()
                        ][:5] or ["待补充关键发现"]
                    )
                )
            except Exception:
                continue
        
        return VisualizationResponse(
            query=requirement.get("view_description", ""),
            answer=description,
            has_visualization=True,  # ⭐确保has_visualization为True
            chart_config=chart_config,
            insights=parsed_insights or None,
            data_source="view_linkage"
        )
    
    def _extract_labels_from_text(self, text: str, expected_count: int = 0) -> List[str]:
        """
        ⭐从文本中提取labels（时间、指标名等）- 增强版
        
        Args:
            text: 原始文本
            expected_count: 期望的labels数量
        
        Returns:
            labels列表
        """
        labels = []
        
        # 1. 提取年份（带"年"字）
        years_with_suffix = re.findall(r'20\d{2}年', text)
        if years_with_suffix:
            unique_years = list(dict.fromkeys(years_with_suffix))  # 保持顺序去重
            if expected_count == 0 or len(unique_years) == expected_count:
                return unique_years[:expected_count] if expected_count > 0 else unique_years
        
        # 2. 提取年份（不带"年"字）
        years = re.findall(r'20\d{2}', text)
        if years:
            unique_years = sorted(list(set(years)))
            # 添加"年"后缀
            unique_years = [f"{y}年" for y in unique_years]
            if expected_count == 0 or len(unique_years) == expected_count:
                return unique_years[:expected_count] if expected_count > 0 else unique_years
        
        # 3. 提取季度
        quarters = re.findall(r'(?:第[一二三四]季度|Q[1-4]|第[1-4]季度)', text)
        if quarters:
            unique_quarters = list(dict.fromkeys(quarters))  # 保持顺序去重
            if expected_count == 0 or len(unique_quarters) == expected_count:
                return unique_quarters[:expected_count] if expected_count > 0 else unique_quarters
        
        # 4. 提取月份
        months = re.findall(r'\d+月', text)
        if months:
            unique_months = list(dict.fromkeys(months))
            if expected_count == 0 or len(unique_months) == expected_count:
                return unique_months[:expected_count] if expected_count > 0 else unique_months
        
        # 5. ⭐改进：提取业务分类（零售业务、对公业务等）
        business_types = re.findall(r'(?:零售|对公|个人|公司|企业|其他)[业务|收入|支出|利润]*', text)
        if business_types:
            unique_business = list(dict.fromkeys(business_types))
            if expected_count == 0 or len(unique_business) == expected_count:
                return unique_business[:expected_count] if expected_count > 0 else unique_business
        
        # 6. ⭐改进：提取收入类型（利息收入、手续费收入等）
        income_types = re.findall(r'(?:利息|手续费|佣金|其他)[收入|支出|净收入]*', text)
        if income_types:
            unique_income = list(dict.fromkeys(income_types))
            if expected_count == 0 or len(unique_income) == expected_count:
                return unique_income[:expected_count] if expected_count > 0 else unique_income
        
        # 7. ⭐改进：从表格中提取第一列（标签列）- 更智能的提取
        lines = text.split('\n')
        for line in lines[:50]:  # 检查前50行
            # 跳过空行和纯数字行
            if not line.strip() or re.match(r'^\s*[\d,.\s]+\s*$', line):
                continue
            
            # 尝试按制表符或空格分割
            parts = [p.strip() for p in re.split(r'[\t\s]+', line) if p.strip()]
            if len(parts) >= 2:
                # 检查是否有数字（在后面的列中）
                has_number_after = False
                for i in range(1, min(len(parts), 4)):  # 检查前4列
                    if re.search(r'\d', parts[i]):
                        has_number_after = True
                        break
                
                if has_number_after:
                    # 第一列可能是标签
                    first_part = parts[0]
                    # 过滤掉纯数字、纯符号等
                    if (not re.match(r'^\d+[.,]?\d*$', first_part) and 
                        len(first_part) > 1 and 
                        first_part not in ['年', '月', '季度', 'Q', '指标', '项目'] and
                        first_part not in labels):
                        labels.append(first_part)
                        if expected_count > 0 and len(labels) >= expected_count:
                            break
        
        # 8. ⭐改进：如果还没有找到足够的labels，尝试提取指标名称
        if (expected_count > 0 and len(labels) < expected_count) or (expected_count == 0 and not labels):
            # 查找常见的财务指标模式
            metric_patterns = [
                r'([^，。\n]+(?:收入|支出|利润|成本|费用|资产|负债|权益))',
                r'([^，。\n]+(?:率|比|额|量))',
            ]
            for pattern in metric_patterns:
                matches = re.findall(pattern, text)
                for match in matches[:10]:  # 最多10个
                    match = match.strip()
                    if len(match) > 2 and match not in labels:
                        labels.append(match)
                        if expected_count > 0 and len(labels) >= expected_count:
                            break
                if expected_count > 0 and len(labels) >= expected_count:
                    break
        
        return labels[:expected_count] if expected_count > 0 else labels
    
    def _create_fallback_visualization_response(
        self,
        requirement: Dict[str, Any],
        data_result: Dict[str, Any]
    ) -> VisualizationResponse:
        """创建降级视图响应（返回VisualizationResponse）；注意图例与 Y 轴单位。"""
        # 尝试从data_result中提取数据（已做过单位换算）
        retrieved_data = data_result.get("retrieved_data", {})
        labels = retrieved_data.get("labels", [])
        values = retrieved_data.get("values", [])
        series = []
        for s in (retrieved_data.get("series", []) or []):
            s_name = str(s.get("name", "")).strip().lower()
            if s_name in {"年份", "year"}:
                continue
            series.append(s)
        display_unit = retrieved_data.get("display_unit") or retrieved_data.get("unit", "")
        y_title = f"数值({display_unit})" if display_unit else "数值"
        
        # 如果没有数据，创建空视图
        if not labels and not values and not series:
            labels = ["暂无数据"]
            values = [0]
        
        # 构建traces（图例使用系列名称）并尽量按数据特征选择图表类型
        preferred_chart_types = requirement.get("analysis_workflow", {}).get("preferred_chart_types", [])
        if preferred_chart_types:
            fallback_chart_type = self._normalize_chart_type(preferred_chart_types[0])
        else:
            is_time_axis = any(re.search(r'20\d{2}|Q[1-4]|第[一二三四1-4]季度', str(lb)) for lb in labels[:4])
            if is_time_axis:
                fallback_chart_type = ChartType.LINE
            elif series and len(series) > 1:
                fallback_chart_type = ChartType.GROUPED_BAR
            else:
                fallback_chart_type = ChartType.BAR
        fallback_trace_type, fallback_mode = self._default_trace_spec_for_chart(fallback_chart_type)

        traces = []
        if series:
            # 多系列数据，每个系列名称作为图例项
            for s in series[:5]:  # 最多5个系列，保证图例可读
                name = s.get("name") or "系列"
                traces.append(ChartTrace(
                    name=name,
                    x=labels if labels else [f"点{i+1}" for i in range(len(s.get("values", [])))],
                    y=s.get("values", []),
                    type=fallback_trace_type,
                    mode=fallback_mode
                ))
        else:
            # 单系列数据
            traces.append(ChartTrace(
                name="数据",
                x=labels if labels else [f"点{i+1}" for i in range(len(values))],
                y=values if values else [0],
                type=fallback_trace_type,
                mode=fallback_mode
            ))
        
        layout = ChartLayout(
            title=requirement.get('view_description', '综合分析视图') or "综合分析视图",
            height=400,
            xaxis_title="维度",
            yaxis_title=y_title,
            showlegend=True
        )
        
        chart_config = PlotlyChartConfig(
            chart_type=fallback_chart_type,
            traces=traces,
            layout=layout
        )
        
        missing = data_result.get("missing_fields", [])
        description = requirement.get("view_description", "综合分析视图")
        if missing:
            description += f"\n\n⚠️ 注意：部分数据缺失（{', '.join(missing[:3])}）"
        
        return VisualizationResponse(
            query=requirement.get("view_description", ""),
            answer=description,
            has_visualization=True,
            chart_config=chart_config,
            data_source="view_linkage"
        )
    
    def _create_fallback_view(
        self,
        requirement: Dict[str, Any],
        data_result: Dict[str, Any]
    ) -> NewViewInfo:
        """创建降级视图（返回NewViewInfo）"""
        # 使用_create_fallback_visualization_response创建视图响应
        viz_response = self._create_fallback_visualization_response(requirement, data_result)
        
        missing = data_result.get("missing_fields", [])
        
        return NewViewInfo(
            view_id=f"fallback_{requirement.get('view_type', 'verify')}",
            view_type=requirement.get("view_type", "verify"),
            visualization_response=viz_response,
            data_validation={
                "data_available": data_result.get("data_available", False),
                "data_quality": data_result.get("data_quality", "low"),
                "missing_fields": missing,
                "validation_status": "failed" if not data_result.get("data_available", False) else "partial"
            },
            description=requirement.get("view_description", "综合分析视图")
        )


class MultiCardAnalysisEngine:
    """多卡片分析引擎"""
    
    def __init__(self, llm=None):
        self.llm = llm or Settings.llm
        self.chart_summary_generator = ChartSummaryGenerator()
    
    async def analyze_multiple_cards(
        self,
        selected_cards: List[Dict[str, Any]],
        context_filter: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """分析多个卡片之间的关系"""
        try:
            # 提取视图摘要
            card_summaries = []
            for card in selected_cards:
                if card.get('data') and card['data'].get('has_visualization'):
                    chart_config = None
                    if card['data'].get('chart_config'):
                        # 从字典构建PlotlyChartConfig
                        chart_config = self._dict_to_chart_config(card['data']['chart_config'])
                    
                    summary = self.chart_summary_generator.generate_summary(
                        chart_config,
                        view_id=card.get('id', ''),
                        title=card.get('question', ''),
                        question=card.get('question', '')
                    )
                    card_summaries.append(summary)
            
            if not card_summaries:
                return {
                    "card_summaries": [],
                    "card_relationships": [],
                    "key_insights": [],
                    "data_gaps": []
                }
            
            # 使用LLM分析卡片关系
            analysis = await self._analyze_card_relationships(card_summaries)
            
            # 序列化card_summaries为字典，避免JSON序列化错误
            card_summaries_dict = []
            for summary in card_summaries:
                if hasattr(summary, 'model_dump'):
                    card_summaries_dict.append(summary.model_dump())
                elif hasattr(summary, 'dict'):
                    card_summaries_dict.append(summary.dict())
                else:
                    # 手动序列化
                    card_summaries_dict.append({
                        "view_id": summary.view_id,
                        "chart_type": summary.chart_type.value if hasattr(summary.chart_type, 'value') else str(summary.chart_type),
                        "title": summary.title,
                        "original_question": summary.original_question,
                        "time_range": summary.time_range,
                        "data_dimensions": summary.data_dimensions,
                        "key_metrics": summary.key_metrics,
                        "patterns": summary.patterns,
                        "raw_data": summary.raw_data,
                        "data_source": summary.data_source
                    })
            
            return {
                "card_summaries": card_summaries_dict,
                "card_relationships": analysis.get("relationships", []),
                "key_insights": analysis.get("insights", []),
                "data_gaps": analysis.get("gaps", []),
                "recommended_views": analysis.get("recommended_views", [])
            }
        except Exception as e:
            logger.error(f"多卡片分析失败: {str(e)}")
            return {
                "card_summaries": [],
                "card_relationships": [],
                "key_insights": [],
                "data_gaps": []
            }
    
    def _dict_to_chart_config(self, config_dict: Dict) -> Optional[PlotlyChartConfig]:
        """从字典构建PlotlyChartConfig"""
        try:
            from models.visualization_models import PlotlyChartConfig, ChartTrace, ChartLayout
            
            traces = []
            for trace_dict in config_dict.get("traces", []):
                trace = ChartTrace(**trace_dict)
                traces.append(trace)
            
            layout = ChartLayout(**config_dict.get("layout", {}))
            
            chart_type = ChartType(config_dict.get("chart_type", "bar"))
            
            return PlotlyChartConfig(
                chart_type=chart_type,
                traces=traces,
                layout=layout
            )
        except:
            return None
    
    async def _analyze_card_relationships(
        self,
        card_summaries: List[ChartSummary]
    ) -> Dict[str, Any]:
        """使用LLM分析卡片之间的关系"""
        try:
            prompt = self._build_card_relationship_prompt(card_summaries)
            response = await self._call_llm(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"卡片关系分析失败: {str(e)}")
            return {
                "relationships": [],
                "insights": [],
                "gaps": [],
                "recommended_views": []
            }
    
    def _build_card_relationship_prompt(self, card_summaries: List[ChartSummary]) -> str:
        """构建卡片关系分析的Prompt"""
        cards_info = []
        for i, summary in enumerate(card_summaries, 1):
            cards_info.append(f"""
### 卡片{i}
- ID: {summary.view_id}
- 问题: {summary.original_question}
- 视图类型: {summary.chart_type.value}
- 视图标题: {summary.title}
- 关键指标: {', '.join(summary.key_metrics) if summary.key_metrics else '未知'}
- 时间范围: {summary.time_range}
- 数据模式:
  - 趋势: {summary.patterns.get('trend', '未知')}
  - 拐点: {summary.patterns.get('turning_points', [])}
""")
        
        return f"""
你是一个专业的财务分析专家，擅长分析多个视图之间的关系。

## 任务
分析以下{len(card_summaries)}个视图卡片之间的关系，识别关键洞察和数据缺口。

## 视图卡片信息

{''.join(cards_info)}

## 分析任务

1. **关系分析**：
   - 这些视图之间是互补关系、冲突关系还是支持关系？
   - 哪些视图可以相互验证？
   - 哪些视图之间存在因果关系？

2. **关键洞察**：
   - 从这些视图的组合中，能得出什么综合洞察？
   - 有哪些重要的发现？

3. **数据缺口**：
   - 要验证这些洞察，还缺少什么数据？
   - 需要生成哪些新视图来补充？

## 输出格式（JSON）

{{
    "relationships": [
        {{
            "card1_index": 0,
            "card2_index": 1,
            "relationship_type": "complementary/supporting/conflicting",
            "description": "关系描述",
            "confidence": "high/medium/low"
        }}
    ],
    "insights": [
        "洞察1：...",
        "洞察2：..."
    ],
    "gaps": [
        "缺少数据1：...",
        "缺少数据2：..."
    ],
    "recommended_views": [
        {{
            "view_type": "verify/explain/navigate/comprehensive",
            "description": "视图描述",
            "reason": "为什么需要这个视图",
            "related_cards": [0, 1]
        }}
    ]
}}
"""
    
    async def _call_llm(self, prompt: str) -> str:
        """调用LLM"""
        messages = [
            ChatMessage(
                role="system",
                content="你是一个专业的财务分析专家，擅长分析多个视图之间的关系。请严格按照JSON格式输出。"
            ),
            ChatMessage(role="user", content=prompt)
        ]
        
        response = self.llm.chat(messages)
        return response.message.content
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(response)
        except Exception as e:
            logger.error(f"无法解析LLM响应: {str(e)}")
            return {
                "relationships": [],
                "insights": [],
                "gaps": [],
                "recommended_views": []
            }


class MultiCardLinkageEngine:
    """多卡片联动生成引擎"""
    
    def __init__(self, query_engine, rag_engine, llm=None):
        self.query_engine = query_engine
        self.rag_engine = rag_engine
        self.llm = llm or Settings.llm
        self.multi_card_analyzer = MultiCardAnalysisEngine(llm)
        self.linkage_engine = LinkageGenerationEngine(llm)
        self.data_retriever = DataRetriever(query_engine, rag_engine)
        self.view_generator = NewViewGenerator(query_engine, rag_engine, self.data_retriever, llm)
    
    async def generate_linkage_from_cards(
        self,
        selected_cards: List[Dict[str, Any]],
        company_name: str,
        year: str,
        context_filter: Optional[Dict] = None,
        exploration_question: Optional[str] = None,  # ⭐新增参数
        exploration_mode: str = "comprehensive"  # ⭐新增参数
    ) -> MultiCardLinkageResponse:
        """
        从选中的卡片生成视图联动（支持探索问题）
        
        Args:
            exploration_question: 用户输入的探索问题（如果为None，则进行综合分析）
            exploration_mode: "focused"（聚焦探索问题）或 "comprehensive"（综合分析）
        """
        try:
            # 1. 多卡片分析
            card_analysis = await self.multi_card_analyzer.analyze_multiple_cards(
                selected_cards, context_filter
            )
            
            card_summaries = card_analysis.get("card_summaries", [])
            if not card_summaries:
                return MultiCardLinkageResponse(
                    source_cards=[card.get('id', '') for card in selected_cards],
                    card_analysis=card_analysis,
                    synthesis_insight={"conclusion": "无法分析：选中的卡片没有有效的视图数据"},
                    new_views=[]
                )
            
            # 2. 选择关键卡片进行深度联动分析
            key_card_pairs = self._select_key_card_pairs(
                card_analysis.get("card_relationships", [])
            )
            
            # ⭐新增：如果有探索问题，进行聚焦分析
            exploration_focus = None
            if exploration_question and exploration_question.strip() and exploration_mode == "focused":
                exploration_focus = await self._analyze_exploration_question(
                    exploration_question,
                    card_analysis
                )
                logger.info(f"探索问题分析完成，聚焦领域: {exploration_focus.get('focus_areas', [])}")
            
            # 3. 对每个关键卡片对进行联动分析
            linkage_results = []
            for pair in key_card_pairs:
                card1_idx, card2_idx = pair
                if card1_idx < len(card_summaries) and card2_idx < len(card_summaries):
                    card1_summary_dict = card_summaries[card1_idx]
                    card2_summary_dict = card_summaries[card2_idx]
                    
                    # 将字典转换回ChartSummary对象（用于generate_linkage_analysis）
                    from models.view_linkage_models import ChartSummary
                    from models.visualization_models import ChartType
                    card1_summary = ChartSummary(
                        view_id=card1_summary_dict.get('view_id', ''),
                        chart_type=ChartType(card1_summary_dict.get('chart_type', 'bar')),
                        title=card1_summary_dict.get('title', ''),
                        time_range=card1_summary_dict.get('time_range'),
                        data_dimensions=card1_summary_dict.get('data_dimensions', []),
                        key_metrics=card1_summary_dict.get('key_metrics', []),
                        patterns=card1_summary_dict.get('patterns', {}),
                        raw_data=card1_summary_dict.get('raw_data', {}),
                        data_source=card1_summary_dict.get('data_source'),
                        original_question=card1_summary_dict.get('original_question', '')
                    )
                    
                    linkage = await self.linkage_engine.generate_linkage_analysis(
                        chart_summary=card1_summary,
                        original_query=card1_summary_dict.get('original_question', '') or "",
                        original_answer=f"基于视图：{card1_summary_dict.get('title', '')}",
                        related_text=f"相关视图：{card2_summary_dict.get('title', '')}\n{card2_summary_dict.get('original_question', '')}",
                        exploration_question=exploration_question,  # ⭐新增参数
                        rag_engine=self.rag_engine,  # ⭐新增：传递RAG引擎
                        company_name=company_name,  # ⭐新增：传递公司名
                        year=year  # ⭐新增：传递年份
                    )
                    linkage_results.append({
                        "source_cards": [card1_summary_dict.get('view_id', ''), card2_summary_dict.get('view_id', '')],
                        "linkage_analysis": linkage
                    })
            
            # 如果没有关键卡片对，使用第一个卡片进行单卡片联动
            if not linkage_results and card_summaries:
                card1_summary_dict = card_summaries[0]
                
                # 将字典转换回ChartSummary对象
                from models.view_linkage_models import ChartSummary
                from models.visualization_models import ChartType
                card1_summary = ChartSummary(
                    view_id=card1_summary_dict.get('view_id', ''),
                    chart_type=ChartType(card1_summary_dict.get('chart_type', 'bar')),
                    title=card1_summary_dict.get('title', ''),
                    time_range=card1_summary_dict.get('time_range'),
                    data_dimensions=card1_summary_dict.get('data_dimensions', []),
                    key_metrics=card1_summary_dict.get('key_metrics', []),
                    patterns=card1_summary_dict.get('patterns', {}),
                    raw_data=card1_summary_dict.get('raw_data', {}),
                    data_source=card1_summary_dict.get('data_source'),
                    original_question=card1_summary_dict.get('original_question', '')
                )
                
                linkage = await self.linkage_engine.generate_linkage_analysis(
                    chart_summary=card1_summary,
                    original_query=card1_summary_dict.get('original_question', '') or "",
                    original_answer=f"基于视图：{card1_summary_dict.get('title', '')}",
                    related_text=None,
                    exploration_question=exploration_question,  # ⭐新增参数
                    rag_engine=self.rag_engine,  # ⭐新增：传递RAG引擎
                    company_name=company_name,  # ⭐新增：传递公司名
                    year=year  # ⭐新增：传递年份
                )
                linkage_results.append({
                    "source_cards": [card1_summary_dict.get('view_id', '')],
                    "linkage_analysis": linkage
                })
            
            # 4. 生成洞察（根据模式选择）
            if exploration_question and exploration_mode == "focused":
                # 聚焦模式：优先回答用户的探索问题
                synthesis_insight = await self._generate_focused_insight(
                    exploration_question,
                    card_analysis,
                    linkage_results,
                    exploration_focus,
                    rag_engine=self.rag_engine,  # ⭐新增：传递RAG引擎
                    company_name=company_name,  # ⭐新增：传递公司名
                    year=year  # ⭐新增：传递年份
                )
            else:
                # 综合分析模式：生成综合洞察
                synthesis_insight = await self._generate_comprehensive_insight(
                    card_analysis, linkage_results,
                    rag_engine=self.rag_engine,  # ⭐新增：传递RAG引擎
                    company_name=company_name,  # ⭐新增：传递公司名
                    year=year  # ⭐新增：传递年份
                )
            
            # 5. 生成新视图（根据是否有探索问题）
            new_views = []
            if linkage_results:
                first_linkage = linkage_results[0]["linkage_analysis"]
                first_card_summary_dict = card_summaries[0]
                
                # 将字典转换回ChartSummary对象
                from models.view_linkage_models import ChartSummary
                from models.visualization_models import ChartType
                first_card_summary = ChartSummary(
                    view_id=first_card_summary_dict.get('view_id', ''),
                    chart_type=ChartType(first_card_summary_dict.get('chart_type', 'bar')),
                    title=first_card_summary_dict.get('title', ''),
                    time_range=first_card_summary_dict.get('time_range'),
                    data_dimensions=first_card_summary_dict.get('data_dimensions', []),
                    key_metrics=first_card_summary_dict.get('key_metrics', []),
                    patterns=first_card_summary_dict.get('patterns', {}),
                    raw_data=first_card_summary_dict.get('raw_data', {}),
                    data_source=first_card_summary_dict.get('data_source'),
                    original_question=first_card_summary_dict.get('original_question', '')
                )
                
                if exploration_question and exploration_mode == "focused":
                    # 聚焦模式：生成有助于回答探索问题的视图（只生成1个）
                    new_views = await self._generate_views_with_exploration_focus(
                        exploration_question,
                        first_linkage,
                        first_card_summary,
                        company_name,
                        year,
                        exploration_focus
                    )
                    # ⭐限制：只保留第一个视图
                    if new_views:
                        new_views = new_views[:1]
                else:
                    # 综合分析模式：使用原有的视图生成逻辑（只生成1个）
                    # ⭐改进：传递综合洞察和多视图分析结果，让视图生成充分利用综合分析结果
                    new_views = await self.view_generator.generate_views(
                        first_linkage, first_card_summary, company_name, year, max_views=1,  # ⭐限制为1个
                        synthesis_insight=synthesis_insight,  # ⭐传递综合洞察
                        card_analysis=card_analysis  # ⭐传递多视图分析结果
                    )
            
            # 6. 构建视图关系网络
            view_network = self._build_view_network(selected_cards, new_views)
            
            return MultiCardLinkageResponse(
                source_cards=[card.get('id', '') for card in selected_cards],
                card_analysis=card_analysis,
                synthesis_insight=synthesis_insight,
                new_views=new_views,
                view_network=view_network
            )
        except Exception as e:
            logger.error(f"多卡片联动生成失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return MultiCardLinkageResponse(
                source_cards=[card.get('id', '') for card in selected_cards],
                card_analysis={},
                synthesis_insight={"conclusion": f"生成失败: {str(e)}"},
                new_views=[]
            )
    
    def _select_key_card_pairs(
        self,
        relationships: List[Dict]
    ) -> List[Tuple[int, int]]:
        """选择关键卡片对进行深度联动分析"""
        # 过滤出互补和支持关系
        key_relationships = [
            r for r in relationships 
            if r.get("relationship_type") in ["complementary", "supporting"]
        ]
        
        # 按置信度排序
        key_relationships.sort(
            key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.get("confidence", "low"), 1),
            reverse=True
        )
        
        # 返回前3对的索引
        pairs = []
        for r in key_relationships[:3]:
            card1_idx = r.get("card1_index", -1)
            card2_idx = r.get("card2_index", -1)
            if card1_idx >= 0 and card2_idx >= 0:
                pairs.append((card1_idx, card2_idx))
        
        return pairs
    
    async def _analyze_exploration_question(
        self,
        question: str,
        card_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析探索问题，提取关键信息
        
        Returns:
            {
                "question_type": "why/what/how/relationship/trend",
                "key_concepts": ["营收", "利润"],
                "focus_areas": ["盈利能力", "成本结构"],
                "suggested_views": ["验证型", "解释型"],
                "analysis_priority": "high/medium/low"
            }
        """
        try:
            prompt = f"""
你是一个财务分析专家。用户选择了多个视图卡片后，提出了以下探索问题：

探索问题：{question}

已选卡片分析：
{json.dumps(card_analysis.get('card_relationships', [])[:3], ensure_ascii=False)}
关键指标：{card_analysis.get('key_insights', [])[:5]}

请分析这个探索问题，提取关键信息：

1. 问题类型：why（为什么）/ what（是什么）/ how（如何）/ relationship（关系）/ trend（趋势）
2. 关键概念：问题中涉及的关键财务概念
3. 聚焦领域：需要重点分析的领域
4. 建议视图类型：需要生成哪些类型的视图来回答这个问题
5. 分析优先级：这个问题的分析优先级

输出格式（JSON）：
{{
    "question_type": "why/what/how/relationship/trend",
    "key_concepts": ["概念1", "概念2"],
    "focus_areas": ["领域1", "领域2"],
    "suggested_views": ["verify", "explain"],
    "analysis_priority": "high/medium/low",
    "question_intent": "用户想要了解..."
}}
"""
            messages = [
                ChatMessage(
                    role="system",
                    content="你是一个专业的财务分析专家，擅长分析用户的探索问题。请严格按照JSON格式输出。"
                ),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = self.llm.chat(messages)
            content = response.message.content.strip()
            
            # ⭐改进JSON解析：尝试提取JSON部分
            try:
                # 尝试提取JSON代码块
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试提取JSON对象
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        # 直接解析
                        result = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(f"探索问题分析JSON解析失败: {str(je)}")
                logger.debug(f"原始响应内容（前500字符）: {content[:500]}")
                raise
            
            return result
        except Exception as e:
            logger.error(f"探索问题分析失败: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return {
                "question_type": "unknown",
                "key_concepts": [],
                "focus_areas": [],
                "suggested_views": [],
                "analysis_priority": "medium",
                "question_intent": "无法解析探索问题"
            }
    
    async def _generate_focused_insight(
        self,
        exploration_question: str,
        card_analysis: Dict[str, Any],
        linkage_results: List[Dict],
        exploration_focus: Optional[Dict[str, Any]] = None,
        rag_engine=None,  # ⭐新增：RAG引擎
        company_name: Optional[str] = None,  # ⭐新增：公司名
        year: Optional[str] = None  # ⭐新增：年份
    ) -> Dict[str, Any]:
        """
        生成聚焦洞察（优先回答用户的探索问题）
        """
        try:
            # ⭐新增：检索相关文档数据
            retrieved_documents = ""
            if rag_engine and rag_engine.query_engine:
                try:
                    # 构建检索查询：基于探索问题和关键洞察
                    retrieval_query = exploration_question
                    key_insights = card_analysis.get('key_insights', [])
                    if key_insights:
                        retrieval_query += f" {' '.join(key_insights[:3])}"
                    
                    # 构建上下文过滤器
                    context_filter = {}
                    if company_name:
                        context_filter['company'] = company_name
                    if year:
                        context_filter['year'] = year
                    
                    # 执行RAG检索
                    logger.info(f"📚 为聚焦洞察检索文档数据: {retrieval_query[:100]}...")
                    rag_result = rag_engine.query(retrieval_query, context_filter=context_filter if context_filter else None)
                    
                    if rag_result and rag_result.get('answer'):
                        retrieved_documents = rag_result['answer']
                        if len(retrieved_documents) > 2000:
                            retrieved_documents = retrieved_documents[:2000] + "..."
                        logger.info(f"✅ 为聚焦洞察检索到文档数据（{len(retrieved_documents)}字符）")
                except Exception as e:
                    logger.warning(f"⚠️ 聚焦洞察RAG检索失败: {str(e)}")
            
            prompt = f"""
你是一个专业的财务分析专家。用户选择了多个视图卡片后，提出了以下探索问题：

**用户探索问题**：{exploration_question}

## 已选卡片分析
卡片关系：{json.dumps(card_analysis.get('card_relationships', [])[:3], ensure_ascii=False)}
关键洞察：{card_analysis.get('key_insights', [])[:5]}

## 联动分析结果
{json.dumps([r['linkage_analysis'].get('synthesis_insight', {}) for r in linkage_results[:2]], ensure_ascii=False, indent=2)}

{f'''
## 探索问题分析
聚焦领域：{exploration_focus.get('focus_areas', []) if exploration_focus else []}
建议视图类型：{exploration_focus.get('suggested_views', []) if exploration_focus else []}
''' if exploration_focus else ''}
{f'''
## 检索到的原始文档数据 ⭐新增（重要）
以下是从PDF和Excel文件中检索到的相关数据，请充分利用这些数据生成综合洞察：

{retrieved_documents}
''' if retrieved_documents else ''}

## 任务
**请优先回答用户的探索问题**，生成聚焦洞察：

1. **直接回答**：直接回答用户的探索问题（不超过100字）
2. **证据链**：列出支持回答的证据（来自卡片和联动分析）
3. **置信度**：评估回答的置信度（高/中/低）及原因
4. **关键发现**：3-5条关键发现，重点围绕用户的探索问题

## 输出格式（JSON）
{{
    "conclusion": "直接回答用户的探索问题",
    "evidence_chain": [
        {{"source": "card/view", "content": "...", "supports": "..."}}
    ],
    "confidence": "high/medium/low",
    "confidence_reason": "原因",
    "key_findings": ["发现1（与探索问题相关）", "发现2", ...],
    "answers_question": true
}}
"""
            messages = [
                ChatMessage(
                    role="system",
                    content="你是一个专业的财务分析专家，擅长回答用户的探索问题。请优先直接回答用户的问题。"
                ),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = self.llm.chat(messages)
            content = response.message.content.strip()
            
            # ⭐改进JSON解析：尝试提取JSON部分
            try:
                # 尝试提取JSON代码块
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试提取JSON对象
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        # 直接解析
                        result = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(f"生成聚焦洞察JSON解析失败: {str(je)}")
                logger.debug(f"原始响应内容（前500字符）: {content[:500]}")
                # 降级到综合分析
                return await self._generate_comprehensive_insight_fallback(card_analysis, linkage_results, exploration_question)
            
            return result
        except Exception as e:
            logger.error(f"生成聚焦洞察失败: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
            # 降级到综合分析
            return await self._generate_comprehensive_insight_fallback(card_analysis, linkage_results, exploration_question)
    
    async def _generate_views_with_exploration_focus(
        self,
        exploration_question: str,
        linkage_analysis: Dict[str, Any],
        card_summary: ChartSummary,
        company_name: str,
        year: str,
        exploration_focus: Optional[Dict[str, Any]] = None
    ) -> List[NewViewInfo]:
        """
        生成新视图（聚焦回答用户的探索问题）
        """
        # 修改数据需求，整合探索问题
        modified_linkage = self._modify_linkage_for_exploration(
            linkage_analysis,
            exploration_question,
            exploration_focus
        )
        
        # 生成视图
        new_views = await self.view_generator.generate_views(
            modified_linkage,
            card_summary,
            company_name,
            year
        )
        
        # 在视图描述中添加探索问题信息
        for view in new_views:
            if view.description:
                view.description = f"回答：{exploration_question}\n\n{view.description}"
        
        return new_views
    
    def _modify_linkage_for_exploration(
        self,
        linkage_analysis: Dict[str, Any],
        exploration_question: str,
        exploration_focus: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        修改联动分析结果，整合探索问题
        """
        modified = linkage_analysis.copy()
        
        # 修改数据需求
        data_requirements = modified.get("data_requirements", [])
        if exploration_focus:
            suggested_views = exploration_focus.get("suggested_views", [])
            focus_areas = exploration_focus.get("focus_areas", [])
            
            # 调整数据需求，优先检索聚焦领域的数据
            for req in data_requirements:
                # 在数据需求中添加探索问题的上下文
                req["exploration_context"] = {
                    "question": exploration_question,
                    "focus_areas": focus_areas,
                    "suggested_view_types": suggested_views
                }
        
        # 修改综合洞察提示
        synthesis_insight = modified.get("synthesis_insight", {})
        synthesis_insight["exploration_question"] = exploration_question
        synthesis_insight["priority"] = "answer_user_question"
        modified["synthesis_insight"] = synthesis_insight
        
        return modified
    
    async def _generate_comprehensive_insight(
        self,
        card_analysis: Dict[str, Any],
        linkage_results: List[Dict],
        rag_engine=None,  # ⭐新增：RAG引擎
        company_name: Optional[str] = None,  # ⭐新增：公司名
        year: Optional[str] = None  # ⭐新增：年份
    ) -> Dict[str, Any]:
        """生成综合洞察（增强版：检索文档数据）"""
        # ⭐新增：检索相关文档数据
        retrieved_documents = ""
        if rag_engine and rag_engine.query_engine:
            try:
                # 构建检索查询：基于关键洞察
                key_insights = card_analysis.get('key_insights', [])
                retrieval_query = " ".join(key_insights[:3]) if key_insights else "综合分析"
                
                # 构建上下文过滤器
                context_filter = {}
                if company_name:
                    context_filter['company'] = company_name
                if year:
                    context_filter['year'] = year
                
                logger.info(f"📚 为综合洞察检索文档数据: {retrieval_query[:100]}...")
                rag_result = rag_engine.query(retrieval_query, context_filter=context_filter if context_filter else None)
                
                if rag_result and rag_result.get('answer'):
                    retrieved_documents = rag_result['answer']
                    if len(retrieved_documents) > 2000:
                        retrieved_documents = retrieved_documents[:2000] + "..."
                    logger.info(f"✅ 为综合洞察检索到文档数据（{len(retrieved_documents)}字符）")
            except Exception as e:
                logger.warning(f"⚠️ 综合洞察RAG检索失败: {str(e)}")
        
        retrieved_docs_section = ""
        if retrieved_documents:
            retrieved_docs_section = f"""
## 检索到的原始文档数据 ⭐新增（重要）
以下是从PDF和Excel文件中检索到的相关数据，请充分利用这些数据生成综合洞察：

{retrieved_documents}

**重要提示**：
- 这些数据来自原始文档（PDF/Excel），是综合分析的基础
- 请结合视图数据和这些文档数据进行综合分析
- 优先使用文档中的具体数据来支撑洞察
"""
        
        try:
            prompt = f"""
你是一个专业的财务分析专家。基于以下多卡片分析和联动分析结果，生成综合洞察。

## 多卡片分析结果
卡片关系：{json.dumps(card_analysis.get('card_relationships', [])[:3], ensure_ascii=False)}
关键洞察：{card_analysis.get('key_insights', [])[:5]}
数据缺口：{card_analysis.get('data_gaps', [])[:3]}

## 联动分析结果
{json.dumps([r['linkage_analysis'].get('synthesis_insight', {}) for r in linkage_results[:2]], ensure_ascii=False, indent=2)}
{retrieved_docs_section}
## 任务
生成综合洞察，包括：
1. 一句话综合结论（不超过80字）
2. 证据链（整合所有卡片的证据）
3. 置信度评估
4. 关键发现（5-8条）

## 输出格式（JSON）
{{
    "conclusion": "综合结论",
    "evidence_chain": [
        {{"source": "card/view", "content": "...", "supports": "..."}}
    ],
    "confidence": "high/medium/low",
    "confidence_reason": "原因",
    "key_findings": ["发现1", "发现2", ...]
}}
"""
            messages = [
                ChatMessage(
                    role="system",
                    content="你是一个专业的财务分析专家，擅长生成综合洞察。请严格按照JSON格式输出。"
                ),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = self.llm.chat(messages)
            content = response.message.content.strip()
            
            # ⭐改进JSON解析：尝试提取JSON部分
            try:
                # 尝试提取JSON代码块
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试提取JSON对象
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        # 直接解析
                        result = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(f"生成综合洞察JSON解析失败: {str(je)}")
                logger.debug(f"原始响应内容（前500字符）: {content[:500]}")
                # 使用降级方法
                return self._generate_comprehensive_insight_fallback(card_analysis, linkage_results)
            
            return result
        except Exception as e:
            logger.error(f"生成综合洞察失败: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
            # 使用降级方法
            return self._generate_comprehensive_insight_fallback(card_analysis, linkage_results)
    
    def _generate_comprehensive_insight_fallback(
        self,
        card_analysis: Dict[str, Any],
        linkage_results: List[Dict],
        exploration_question: Optional[str] = None
    ) -> Dict[str, Any]:
        """生成综合洞察的降级方法（当LLM调用失败时使用）"""
        # 从联动分析结果中提取洞察
        insights = []
        for result in linkage_results[:2]:
            linkage = result.get('linkage_analysis', {})
            synthesis = linkage.get('synthesis_insight', {})
            if synthesis.get('conclusion'):
                insights.append(synthesis.get('conclusion'))
        
        # 从卡片分析中提取关键发现
        key_findings = card_analysis.get("key_insights", [])[:5]
        if not key_findings:
            key_findings = [f"基于选中的视图卡片进行分析"]
        
        # 构建降级洞察
        conclusion = ""
        if exploration_question:
            conclusion = f"基于选中的视图卡片，针对问题「{exploration_question}」的分析："
        else:
            conclusion = "基于选中的视图卡片，综合分析："
        
        if insights:
            conclusion += " " + "；".join(insights[:2])
        else:
            conclusion += " 已对选中的视图进行了综合分析。"
        
        return {
            "conclusion": conclusion,
            "evidence_chain": [
                {"source": "card_analysis", "content": "基于选中的视图卡片", "supports": "综合分析"}
            ],
            "confidence": "medium",
            "confidence_reason": "基于选中的视图卡片和联动分析结果",
            "key_findings": key_findings
        }
    
    def _build_view_network(
        self,
        selected_cards: List[Dict],
        new_views: List[NewViewInfo]
    ) -> List[Dict[str, Any]]:
        """构建视图关系网络"""
        network = []
        
        for view in new_views:
            for card_id in view.related_cards:
                network.append({
                    "from_card_id": card_id,
                    "to_view_id": view.view_id,
                    "relationship_type": view.view_type,
                    "description": view.description
                })
        
        return network


class SingleCardLinkageEngine:
    """单卡片联动引擎"""
    
    def __init__(self, query_engine, rag_engine, llm=None):
        self.query_engine = query_engine
        self.rag_engine = rag_engine
        self.llm = llm or Settings.llm
        self.chart_summary_generator = ChartSummaryGenerator()
        self.multi_card_analyzer = MultiCardAnalysisEngine(llm)  # ⭐新增：用于_dict_to_chart_config方法
        self.linkage_engine = LinkageGenerationEngine(llm)
        self.data_retriever = DataRetriever(query_engine, rag_engine)
        self.view_generator = NewViewGenerator(query_engine, rag_engine, self.data_retriever, llm)
    
    async def generate_linkage_from_card(
        self,
        card: Dict[str, Any],
        company_name: str,
        year: str,
        context_filter: Optional[Dict] = None,
        exploration_question: Optional[str] = None,  # ⭐新增参数
        exploration_mode: str = "comprehensive"  # ⭐新增参数
    ) -> MultiCardLinkageResponse:
        """
        从单个卡片生成视图联动（支持探索问题）
        
        Args:
            exploration_question: 用户输入的探索问题（如果为None，则进行综合分析）
            exploration_mode: "focused"（聚焦探索问题）或 "comprehensive"（综合分析）
        """
        try:
            # 提取视图摘要
            chart_config = None
            if card.get('data') and card['data'].get('chart_config'):
                # ⭐修复：使用MultiCardAnalysisEngine的_dict_to_chart_config方法
                chart_config = self.multi_card_analyzer._dict_to_chart_config(
                    card['data']['chart_config']
                )
            
            chart_summary = self.chart_summary_generator.generate_summary(
                chart_config,
                view_id=card.get('id', ''),
                title=card.get('question', ''),
                question=card.get('question', '')
            )
            
            # 获取原始回答（如果有）
            original_answer = ""
            if card.get('data') and card['data'].get('answer'):
                original_answer = card['data']['answer']
            elif card.get('data') and card['data'].get('analysis_text'):
                original_answer = card['data']['analysis_text']
            
            # 确定探索模式
            if exploration_question:
                exploration_mode = "focused"
            else:
                exploration_mode = "comprehensive"
            
            # 执行联动分析
            linkage_analysis = await self.linkage_engine.generate_linkage_analysis(
                chart_summary=chart_summary,
                original_query=card.get('question', ''),
                original_answer=original_answer or f"基于视图：{chart_summary.title}",
                related_text=None,
                exploration_question=exploration_question,  # ⭐新增参数
                rag_engine=self.rag_engine,  # ⭐新增：传递RAG引擎
                company_name=company_name,  # ⭐新增：传递公司名
                year=year  # ⭐新增：传递年份
            )
            
            # 生成新视图（根据是否有探索问题）
            if exploration_question and exploration_mode == "focused":
                # 聚焦模式：生成有助于回答探索问题的视图
                exploration_focus = await self._analyze_exploration_question(
                    exploration_question,
                    {"card_relationships": [], "key_insights": []}
                )
                new_views = await self._generate_views_with_exploration_focus(
                    exploration_question,
                    linkage_analysis,
                    chart_summary,
                    company_name,
                    year,
                    exploration_focus
                )
            else:
                # 综合分析模式：使用原有的视图生成逻辑
                # ⭐改进：传递综合洞察，让视图生成充分利用综合分析结果
                synthesis_insight = linkage_analysis.get("synthesis_insight", {})
                new_views = await self.view_generator.generate_views(
                    linkage_analysis, chart_summary, company_name, year,
                    synthesis_insight=synthesis_insight  # ⭐传递综合洞察
                )
            
            # 构建响应
            return MultiCardLinkageResponse(
                source_cards=[card.get('id', '')],
                card_analysis={
                    "card_summaries": [chart_summary],
                    "card_relationships": [],
                    "key_insights": linkage_analysis.get("synthesis_insight", {}).get("key_findings", []),
                    "data_gaps": linkage_analysis.get("alignment_result", {}).get("evidence_assessment", {}).get("missing_evidence", [])
                },
                synthesis_insight=linkage_analysis.get("synthesis_insight", {}),
                new_views=new_views,
                view_network=self._build_view_network(card, new_views)  # ⭐修复：传递card而不是[card]
            )
        except Exception as e:
            logger.error(f"单卡片联动生成失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return MultiCardLinkageResponse(
                source_cards=[card.get('id', '')],
                card_analysis={},
                synthesis_insight={"conclusion": f"生成失败: {str(e)}"},
                new_views=[]
            )
    
    async def _analyze_exploration_question(
        self,
        question: str,
        card_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        分析探索问题，提取关键信息（与MultiCardLinkageEngine相同的方法）
        """
        try:
            prompt = f"""
你是一个财务分析专家。用户选择了视图卡片后，提出了以下探索问题：

探索问题：{question}

已选卡片分析：
{json.dumps(card_analysis.get('card_relationships', [])[:3], ensure_ascii=False)}
关键指标：{card_analysis.get('key_insights', [])[:5]}

请分析这个探索问题，提取关键信息：

1. 问题类型：why（为什么）/ what（是什么）/ how（如何）/ relationship（关系）/ trend（趋势）
2. 关键概念：问题中涉及的关键财务概念
3. 聚焦领域：需要重点分析的领域
4. 建议视图类型：需要生成哪些类型的视图来回答这个问题
5. 分析优先级：这个问题的分析优先级

输出格式（JSON）：
{{
    "question_type": "why/what/how/relationship/trend",
    "key_concepts": ["概念1", "概念2"],
    "focus_areas": ["领域1", "领域2"],
    "suggested_views": ["verify", "explain"],
    "analysis_priority": "high/medium/low",
    "question_intent": "用户想要了解..."
}}
"""
            messages = [
                ChatMessage(
                    role="system",
                    content="你是一个专业的财务分析专家，擅长分析用户的探索问题。请严格按照JSON格式输出。"
                ),
                ChatMessage(role="user", content=prompt)
            ]
            
            response = self.llm.chat(messages)
            content = response.message.content.strip()
            
            # ⭐改进JSON解析：尝试提取JSON部分
            try:
                # 尝试提取JSON代码块
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试提取JSON对象
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group())
                    else:
                        # 直接解析
                        result = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(f"探索问题分析JSON解析失败: {str(je)}")
                logger.debug(f"原始响应内容（前500字符）: {content[:500]}")
                raise
            
            return result
        except Exception as e:
            logger.error(f"探索问题分析失败: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
            return {
                "question_type": "unknown",
                "key_concepts": [],
                "focus_areas": [],
                "suggested_views": [],
                "analysis_priority": "medium",
                "question_intent": "无法解析探索问题"
            }
    
    def _modify_linkage_for_exploration(
        self,
        linkage_analysis: Dict[str, Any],
        exploration_question: str,
        exploration_focus: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        修改联动分析结果，整合探索问题（与MultiCardLinkageEngine相同的方法）
        """
        modified = linkage_analysis.copy()
        
        # 修改数据需求，整合探索问题
        if "data_requirements" in modified:
            for req in modified["data_requirements"]:
                if exploration_focus:
                    focus_areas = exploration_focus.get("focus_areas", [])
                    if focus_areas:
                        req["view_description"] = f"回答：{exploration_question}\n{req.get('view_description', '')}"
                        req["view_reason"] = f"聚焦分析：{', '.join(focus_areas[:2])}"
        
        # 修改分析流程判断
        if "analysis_workflow" in modified and exploration_focus:
            workflow = modified["analysis_workflow"]
            workflow["focus_areas"] = exploration_focus.get("focus_areas", workflow.get("focus_areas", []))
            workflow["reasoning"] = f"基于探索问题：{exploration_question}\n{workflow.get('reasoning', '')}"
        
        return modified
    
    async def _generate_views_with_exploration_focus(
        self,
        exploration_question: str,
        linkage_analysis: Dict[str, Any],
        card_summary: ChartSummary,
        company_name: str,
        year: str,
        exploration_focus: Optional[Dict[str, Any]] = None
    ) -> List[NewViewInfo]:
        """
        生成新视图（聚焦回答用户的探索问题）（与MultiCardLinkageEngine相同的方法）
        """
        # 修改数据需求，整合探索问题
        modified_linkage = self._modify_linkage_for_exploration(
            linkage_analysis,
            exploration_question,
            exploration_focus
        )
        
        # 生成视图（只生成1个）
        new_views = await self.view_generator.generate_views(
            modified_linkage,
            card_summary,
            company_name,
            year,
            max_views=1  # ⭐限制为1个
        )
        
        # 在视图描述中添加探索问题信息
        for view in new_views:
            if view.description:
                view.description = f"回答：{exploration_question}\n\n{view.description}"
        
        return new_views
    
    def _build_view_network(
        self,
        card: Dict,
        new_views: List[NewViewInfo]
    ) -> List[Dict[str, Any]]:
        """构建视图关系网络"""
        network = []
        card_id = card.get('id', '')
        
        for view in new_views:
            network.append({
                "from_card_id": card_id,
                "to_view_id": view.view_id,
                "relationship_type": view.view_type,
                "description": view.description
            })
        
        return network
