"""
可视化生成 Agent
智能分析数据并生成合适的图表配置
"""

import logging
import json
import re
from typing import Dict, Any, List, Optional, Annotated
from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from models.visualization_models import (
    ChartType,
    ChartRecommendation,
    VisualizationResponse,
    PlotlyChartConfig,
    ChartTrace,
    ChartLayout,
    SimpleBarChart,
    SimpleLineChart,
    SimplePieChart,
    MultiLineChart,
    GroupedBarChart,
    TableChart,
    VisualizationInsight
)
from agents.visualization_examples import (
    VISUALIZATION_EXAMPLES,
    QUESTION_TYPE_KEYWORDS,
    VIEW_RECOMMENDATION_MAP
)

logger = logging.getLogger(__name__)


class VisualizationAgent:
    """
    可视化生成 Agent
    智能分析数据并生成合适的图表配置
    
    注意：可视化示例、问题类型关键词和视图推荐映射已移至 visualization_examples.py 文件
    如需添加新示例，请编辑 visualization_examples.py
    """
    
    def __init__(self, llm=None):
        """
        初始化可视化Agent
        
        Args:
            llm: LLM实例，如果为None则使用Settings.llm
        """
        self.llm = llm or Settings.llm
    
    async def generate_visualization(
        self,
        query: str,
        answer: str,
        data: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict]] = None
    ) -> VisualizationResponse:
        """
        生成可视化配置
        
        Args:
            query: 用户查询
            answer: 文本回答
            data: 原始数据（可选）
            sources: 数据来源（可选）
        
        Returns:
            VisualizationResponse: 包含图表配置的响应
        """
        try:
            logger.info(f"开始生成可视化: {query[:50]}...")
            
            # 1. 分析查询和回答，判断是否需要可视化
            needs_viz = await self._analyze_visualization_need(query, answer)
            
            if not needs_viz:
                return VisualizationResponse(
                    query=query,
                    answer=answer,
                    has_visualization=False
                )
            
            # 2. 分类问题类型（需要在提取数据之前完成）
            question_type = self._classify_question_type(query, answer)
            logger.warning(f"🔍 [DEBUG] 问题类型分类结果: {question_type}")
            
            # 3. 提取数据（传递问题类型以优化提取）
            extracted_data = await self._extract_data_from_answer(query, answer, sources, question_type=question_type)
            logger.warning(f"🔍 [DEBUG] 数据提取结果: has_data={extracted_data.get('has_data') if extracted_data else None}, data_type={extracted_data.get('data_type') if extracted_data else None}")
            
            if not extracted_data or not extracted_data.get('has_data'):
                logger.warning(f"⚠️ [DEBUG] 数据提取失败，extracted_data: {extracted_data}")
                logger.info("未能从回答中提取到可视化数据")
                return VisualizationResponse(
                    query=query,
                    answer=answer,
                    has_visualization=False
                )
            
            # 4. 推荐图表类型（增强版：同时考量问题和回答）
            recommendation = await self._recommend_chart_type(
                query, 
                extracted_data,
                answer=answer,  # 传入回答内容
                question_type=question_type
            )
            
            # 5. 检查是否需要生成时间轴
            timeline_data = None
            visualization_type = "plotly"
            
            # 如果是过程与变化类问题，且检测到时间轴示例，生成Timeline数据
            if question_type == 'process':
                logger.info(f"🔍 检测到过程类问题，尝试获取时间轴示例...")
                example = self._get_visualization_example(question_type, recommendation.recommended_chart_type, query)
                logger.info(f"📋 获取到的示例: {example.get('type') if example else 'None'}, {example.get('description') if example else 'None'}")
                if example and example.get('type') == 'timeline':
                    logger.info(f"✅ 检测到时间轴示例，开始生成Timeline数据...")
                    from agents.timeline_generator import generate_timeline_data
                    timeline_data = await generate_timeline_data(self.llm, query, answer, extracted_data, sources)
                    if timeline_data:
                        visualization_type = "timeline"
                        # 更新推荐信息，说明是时间轴
                        recommendation = ChartRecommendation(
                            recommended_chart_type=ChartType.LINE,  # 保持LINE类型以兼容，但reason会说明是时间轴
                            reason="过程与变化类问题，使用时间轴展示关键事件的时间序列",
                            data_characteristics=recommendation.data_characteristics,
                            alternative_charts=recommendation.alternative_charts
                        )
                        logger.info(f"✅ 生成时间轴数据成功，包含{len(timeline_data)}个事件")
                        logger.info(f"时间轴数据: {timeline_data}")
                    else:
                        logger.warning(f"⚠️ 时间轴数据生成失败，将使用Plotly折线图")
                else:
                    logger.info(f"ℹ️ 未检测到时间轴示例或示例类型不匹配，将使用Plotly图表")
            
            # 6. 生成图表配置（传递问题类型以使用示例）
            # 重要：如果是Timeline类型，chart_config必须为None，避免前端同时渲染Plotly图表
            chart_config = None
            if visualization_type == "plotly":
                chart_config = await self._generate_chart_config(
                    recommendation.recommended_chart_type,
                    extracted_data,
                    query,
                    question_type=question_type
            )
            else:
                # 确保Timeline类型时chart_config为None
                chart_config = None
                logger.info(f"✅ {visualization_type}类型，chart_config已设置为None，避免渲染Plotly图表")
            
            # 7. 生成洞察
            insights = await self._generate_insights(
                extracted_data,
                recommendation.recommended_chart_type
            )
            
            logger.info(f"✅ 可视化生成成功: {visualization_type} (推荐类型: {recommendation.recommended_chart_type.value})")
            
            return VisualizationResponse(
                query=query,
                answer=answer,
                has_visualization=True,
                chart_config=chart_config,  # Timeline类型时为None
                timeline_data=timeline_data,
                visualization_type=visualization_type,
                recommendation=recommendation,
                insights=insights,
                confidence_score=0.85
            )
            
        except Exception as e:
            logger.error(f"❌ 生成可视化失败: {str(e)}")
            return VisualizationResponse(
                query=query,
                answer=answer,
                has_visualization=False
            )
    
    def _classify_question_type(self, query: str, answer: str) -> str:
        """
        分类问题类型（基于可视化匹配.md文档）
        
        Args:
            query: 用户查询
            answer: 文本回答
        
        Returns:
            str: 问题类型 ('data', 'conclusion', 'structure', 'process', 'risk', 'attitude', 'comparison', 'compliance')
        """
        try:
            query_lower = query.lower()
            answer_lower = answer.lower()
            combined_text = query_lower + " " + answer_lower
            
            # 第一步：检查特定的问题模式（优先级最高）
            # 过程与变化类的特定模式
            process_patterns = [
                '关键事件', '哪些事件', '什么事件', '事件影响', '影响未来',
                '时间轴', '时间线', '什么时候', '何时发生', '推进过程'
            ]
            if any(pattern in query_lower for pattern in process_patterns):
                logger.info(f"问题类型分类: process (匹配特定模式)")
                return 'process'
            
            # 风险类的特定模式
            risk_patterns = ['哪些风险', '什么风险', '风险影响', '存在风险', '面临风险']
            if any(pattern in query_lower for pattern in risk_patterns):
                logger.info(f"问题类型分类: risk (匹配特定模式)")
                return 'risk'
            
            # 结构类的特定模式
            structure_patterns = ['什么结构', '哪些业务', '业务组成', '靠什么', '主要业务']
            if any(pattern in query_lower for pattern in structure_patterns):
                logger.info(f"问题类型分类: structure (匹配特定模式)")
                return 'structure'
            
            # 第二步：计算每种类型的匹配分数（基于关键词和示例问题）
            type_scores = {}
            for q_type, keywords in QUESTION_TYPE_KEYWORDS.items():
                score = 0
                # 关键词匹配
                for keyword in keywords:
                    # 在query中匹配的权重更高
                    if keyword in query_lower:
                        score += 2  # query中的关键词权重更高
                    elif keyword in answer_lower:
                        score += 1  # answer中的关键词权重较低
                
                # 示例问题相似度匹配（如果VIEW_RECOMMENDATION_MAP中有示例问题）
                if q_type in VIEW_RECOMMENDATION_MAP:
                    example_questions = VIEW_RECOMMENDATION_MAP[q_type].get('example_questions', [])
                    for example_q in example_questions:
                        # 计算示例问题与用户查询的相似度（简单关键词匹配）
                        example_keywords = set(example_q.lower().split())
                        query_keywords = set(query_lower.split())
                        # 计算共同关键词数量
                        common_keywords = example_keywords.intersection(query_keywords)
                        if len(common_keywords) > 0:
                            # 如果有共同关键词，增加分数
                            similarity_score = len(common_keywords) / max(len(example_keywords), len(query_keywords))
                            score += similarity_score * 3  # 示例问题匹配权重较高
                
                type_scores[q_type] = score
            
            # 第三步：找到得分最高的类型
            if type_scores:
                max_type = max(type_scores, key=type_scores.get)
                max_score = type_scores[max_type]
                
                # 记录所有类型的得分（用于调试）
                scores_str = ", ".join([f"{k}:{v}" for k, v in sorted(type_scores.items(), key=lambda x: x[1], reverse=True)[:3]])
                logger.info(f"问题类型分类: {max_type} (得分: {max_score}, 所有得分: {scores_str})")
                
                # 如果最高分大于0，返回该类型；否则默认为data类
                if max_score > 0:
                    return max_type
            
            # 默认返回data类
            logger.info(f"问题类型分类: data (默认)")
            return 'data'
            
        except Exception as e:
            logger.warning(f"问题类型分类失败: {str(e)}")
            return 'data'
    
    async def _analyze_visualization_need(
        self,
        query: str,
        answer: str
    ) -> bool:
        """
        分析是否需要可视化（增强版，基于可视化匹配.md文档）
        
        核心原则：是否可视化 = 是否能帮助年报读者形成判断
        
        Args:
            query: 用户查询
            answer: 文本回答
        
        Returns:
            bool: 是否需要可视化
        """
        try:
            # 第一步：分类问题类型
            question_type = self._classify_question_type(query, answer)
            
            # 规则1：如果是纯合规/事实类，不生成视图
            if question_type == 'compliance':
                logger.info(f"问题类型为合规/事实类，不生成视图")
                return False
            
            # 规则2：非数据文字也允许生成视图（关键规则）
            # 只要不是合规类，都允许生成视图
            
            # 原有的关键词检测（保持向后兼容）
            viz_keywords = [
                '趋势', '对比', '比较', '增长', '下降', '变化',
                '分布', '占比', '份额', '排名', '图表', '可视化',
                '多少', '如何', '怎样', '数据', '指标', '财务',
                '收入', '利润', '资产', '负债', '资产总额'
            ]
            
            query_lower = query.lower()
            has_viz_keyword = any(keyword in query for keyword in viz_keywords)
            
            # 检查回答中是否包含数字
            has_numbers = bool(re.search(r'\d+\.?\d*', answer))
            
            # 检查回答长度
            answer_length = len(answer)
            
            # 对于非数据类问题，即使没有数字也可以生成视图
            if question_type in ['conclusion', 'structure', 'process', 'risk', 'attitude', 'comparison']:
                # 非数据类：只要回答有足够内容，就允许可视化
                needs_viz = answer_length > 30  # 降低长度要求
                logger.info(f"非数据类问题({question_type})，允许生成视图: {needs_viz} (长度:{answer_length})")
                return needs_viz
            
            # 数据类：保持原有逻辑
            needs_viz = (has_viz_keyword or has_numbers) and answer_length > 50
            
            logger.info(f"可视化需求分析: {needs_viz} (类型:{question_type}, 关键词:{has_viz_keyword}, 数字:{has_numbers}, 长度:{answer_length})")
            
            return needs_viz
            
        except Exception as e:
            logger.error(f"分析可视化需求失败: {str(e)}")
            # 出错时回退到原有逻辑
            has_numbers = bool(re.search(r'\d+\.?\d*', answer))
            return has_numbers and len(answer) > 50
    
    async def _extract_data_from_answer(
        self,
        query: str,
        answer: str,
        sources: Optional[List[Dict]] = None,
        question_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        从回答和来源中提取数据（优先从sources中的表格数据提取）
        
        Args:
            query: 用户查询
            answer: 文本回答
            sources: 数据来源
        
        Returns:
            Dict: 提取的数据
        """
        try:
            # 1. 优先从sources中提取表格数据
            if sources:
                table_sources = [s for s in sources if s.get('metadata', {}).get('document_type') == 'table_data']
                if table_sources:
                    logger.info(f"📊 发现 {len(table_sources)} 个表格来源，尝试从中提取数据")
                    table_data = await self._extract_data_from_table_sources(query, table_sources, answer)
                    if table_data and table_data.get('has_data'):
                        logger.info(f"✅ 从表格来源成功提取数据: {table_data.get('data_type', 'unknown')}")
                        return table_data
            
            # 2. 如果sources中没有表格数据，或提取失败，从answer文本中提取
            logger.info("📝 从文本回答中提取数据...")
            
            # 构建数据来源信息（避免在f-string中使用反斜杠）
            sources_info = ""
            if sources:
                sources_texts = "\n".join([f"- {s.get('text', '')[:200]}..." for s in sources[:3]])
                sources_info = f"数据来源信息（包含表格数据）:\n{sources_texts}\n"
            
            # 根据问题类型获取可视化示例，作为提取数据的参考
            example_guidance = ""
            risk_data_format = ""
            if question_type:
                example = self._get_visualization_example(question_type, ChartType.LINE, query)
                if example:
                    example_guidance = f"\n【可视化示例参考】\n"
                    example_guidance += f"问题类型: {example.get('description', '')}\n"
                    example_guidance += f"适用场景: {example.get('usage', '')}\n"
                    if example.get('type') == 'timeline':
                        example_guidance += "提示：如果是时间轴类型，需要提取时间点和对应的事件描述，生成JSON格式的时间轴数据\n"
                    elif example.get('type') == 'plotly':
                        example_config = example.get('example', {})
                        if example_config.get('chart_type') == 'scatter' and question_type == 'risk':
                            example_guidance += "提示：风险矩阵需要提取风险名称、发生概率、影响程度\n"
                            # 为风险类问题提供专门的数据格式
                            risk_data_format = """
【风险类问题专用数据格式】
如果查询涉及"风险"，请提取以下格式的数据：
{
    "has_data": true,
    "data_type": "risk_matrix",
    "risks": [
        {
            "name": "风险名称",
            "probability": 概率值（1-5的整数，1=低概率，5=高概率）,
            "impact": 影响程度（1-5的整数，1=低影响，5=高影响）,
            "description": "风险描述（可选）"
        }
    ]
}

如果无法量化概率和影响，可以：
1. 根据风险描述中的关键词推断（如"重大"、"严重"、"可能"等）
2. 使用文本描述，但尽量提供数值以便可视化
3. 如果只有风险名称列表，可以设置默认值（probability: 3, impact: 3）

示例：
{
    "has_data": true,
    "data_type": "risk_matrix",
    "risks": [
        {"name": "信用风险", "probability": 4, "impact": 5, "description": "借款人违约风险"},
        {"name": "市场风险", "probability": 3, "impact": 4, "description": "利率波动风险"},
        {"name": "操作风险", "probability": 2, "impact": 3, "description": "内部流程风险"}
    ]
}
"""
                        elif example_config.get('chart_type') == 'treemap':
                            example_guidance += "提示：业务结构图需要提取业务名称和对应的占比/数值\n"
                        elif example_config.get('chart_type') == 'sankey':
                            example_guidance += """
提示：桑基图需要提取节点（nodes）和连接（links）数据，格式如下：
{
    "has_data": true,
    "data_type": "sankey",
    "nodes": {
        "label": ["节点1", "节点2", "节点3", ...],
        "color": ["#fbb4ae", "#b3cde3", "#ccebc5", ...]  // 可选
    },
    "links": {
        "source": [0, 0, 1, ...],  // 源节点索引（从0开始）
        "target": [1, 2, 3, ...],  // 目标节点索引
        "value": [10, 20, 15, ...]  // 流量值
    }
}
例如：业务收入 -> 零售业务(60) -> 成本(40)
     业务收入 -> 对公业务(30) -> 成本(20)
     业务收入 -> 其他业务(10) -> 成本(5)
应提取为：
nodes: ["业务收入", "零售业务", "对公业务", "其他业务", "成本"]
links: source=[0,0,0,1,2,3], target=[1,2,3,4,4,4], value=[60,30,10,40,20,5]
"""
            
            prompt = f"""
分析以下查询和回答，提取可用于可视化的数据。

查询: {query}

回答: {answer}

{sources_info}
{example_guidance}
{risk_data_format}
【重要提示】
1. 如果查询涉及"营业收入"、"收入"等指标，必须从回答和来源中提取具体的历史数据
2. 如果回答中只提到单个数值，尝试从sources中查找历史数据（如最近3-5年的数据）
3. 如果查询要求"趋势"、"变化"、"增长"，必须提取时间序列数据
4. 如果查询涉及"关键事件"、"时间轴"，需要提取时间点和事件描述的对应关系
5. 如果查询涉及"风险"，必须提取风险名称列表，并尽量量化概率和影响程度（1-5分）
6. 如果查询涉及"业务结构"，需要提取业务名称和对应的占比/数值
7. 数值单位要准确识别（元、万元、亿元、%等）

请提取以下信息（以JSON格式返回）：
1. has_data: 是否包含可视化数据（true/false）
2. data_type: 数据类型（time_series/comparison/distribution/single_value/table/risk_matrix）
3. labels: 标签列表（如果适用，如年份、风险名称等）
4. values: 数值列表（如果适用，必须是具体数字）
5. series: 多系列数据（如果适用）
6. unit: 数值单位（如元、%、万、亿元等）
7. time_period: 时间周期（如果是时间序列）
8. risks: 风险数据列表（如果是风险类问题，包含name、probability、impact等字段）

示例输出（普通数据）：
{{
    "has_data": true,
    "data_type": "time_series",
    "labels": ["2021年", "2022年", "2023年"],
    "values": [100, 120, 150],
    "unit": "亿元",
    "time_period": "年度"
}}

示例输出（风险数据）：
{{
    "has_data": true,
    "data_type": "risk_matrix",
    "risks": [
        {{"name": "信用风险", "probability": 4, "impact": 5}},
        {{"name": "市场风险", "probability": 3, "impact": 4}},
        {{"name": "操作风险", "probability": 2, "impact": 3}}
    ]
}}

如果无法提取数据，返回：
{{
    "has_data": false
}}
"""
            
            response = await self.llm.acomplete(prompt)
            response_text = str(response).strip()
            
            # 记录LLM原始响应（用于调试）
            logger.info(f"📋 LLM数据提取响应（前500字符）: {response_text[:500]}")
            
            # 尝试解析JSON
            try:
                # 提取JSON部分
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    data_type = data.get('data_type', 'unknown')
                    has_data = data.get('has_data', False)
                    
                    logger.info(f"📊 解析后的数据: data_type={data_type}, has_data={has_data}, keys={list(data.keys())}")
                    logger.info(f"🔍 问题类型: {question_type}, data_type: {data_type}, has_data: {has_data}")
                    logger.warning(f"🔍 [DEBUG] 问题类型检查: question_type='{question_type}', type={type(question_type)}")
                    
                    # 特殊处理：风险类问题
                    if question_type == 'risk' and has_data:
                        # 如果有risks字段，确保data_type正确
                        if data.get('risks') and data_type != 'risk_matrix':
                            data['data_type'] = 'risk_matrix'
                            logger.info("✅ 检测到风险数据，设置data_type为risk_matrix")
                        # 如果没有risks字段但有问题类型，尝试从labels和values构建
                        elif not data.get('risks') and data.get('labels') and data.get('values'):
                            # 尝试将labels作为风险名称，values作为影响程度
                            risks = []
                            labels = data.get('labels', [])
                            values = data.get('values', [])
                            for i, label in enumerate(labels):
                                if i < len(values):
                                    # 将数值映射到1-5的影响程度
                                    impact_value = values[i]
                                    if isinstance(impact_value, (int, float)):
                                        # 如果值在合理范围内，直接使用；否则映射到1-5
                                        if 1 <= impact_value <= 5:
                                            impact = int(impact_value)
                                        else:
                                            # 简单映射：大值->高影响，小值->低影响
                                            impact = min(5, max(1, int(impact_value / 20) + 1))
                                    else:
                                        impact = 3  # 默认值
                                    risks.append({
                                        "name": str(label),
                                        "probability": 3,  # 默认概率
                                        "impact": impact
                                    })
                            if risks:
                                data['risks'] = risks
                                data['data_type'] = 'risk_matrix'
                                logger.info(f"✅ 从labels和values构建风险数据: {len(risks)}个风险")
                    
                    # 关键修复：对于风险类问题，如果data_type是unknown或has_data是false，尝试fallback
                    if question_type == 'risk':
                        if not has_data:
                            logger.warning(f"⚠️ LLM返回has_data=false，尝试从回答文本中直接提取风险名称")
                            logger.info(f"📝 回答文本前300字符: {answer[:300]}")
                            fallback_result = self._extract_risks_fallback(answer, query)
                            logger.info(f"📊 Fallback结果: has_data={fallback_result.get('has_data')}, risks数量={len(fallback_result.get('risks', []))}")
                            return fallback_result
                        elif data_type == 'unknown' and not data.get('risks'):
                            # 如果data_type是unknown且没有risks字段，也尝试fallback
                            logger.warning(f"⚠️ LLM返回data_type=unknown且无risks字段，尝试从回答文本中直接提取风险名称")
                            fallback_result = self._extract_risks_fallback(answer, query)
                            if fallback_result.get('has_data'):
                                logger.info(f"📊 Fallback成功提取到风险数据: {len(fallback_result.get('risks', []))}个风险")
                                return fallback_result
                    
                    # 对于结构类问题，如果data_type是unknown或has_data是false，尝试fallback
                    if question_type == 'structure':
                        logger.info(f"🔍 检查结构类问题fallback条件: has_data={has_data}, data_type={data_type}, labels={data.get('labels')}")
                        # 修复条件：只要has_data是false，或者data_type是unknown且没有labels，就触发fallback
                        should_fallback = not has_data or (data_type == 'unknown' and not data.get('labels'))
                        logger.info(f"🔍 Fallback条件判断: should_fallback={should_fallback}")
                        if should_fallback:
                            logger.warning(f"⚠️ LLM返回has_data=false或data_type=unknown，尝试从回答文本中直接提取业务名称")
                            logger.info(f"📝 回答文本前300字符: {answer[:300]}")
                            fallback_result = self._extract_structure_fallback(answer, query)
                            logger.info(f"📊 Fallback结果: has_data={fallback_result.get('has_data')}, labels数量={len(fallback_result.get('labels', []))}")
                            if fallback_result.get('has_data'):
                                logger.info(f"✅ Fallback成功，返回提取的业务数据")
                                return fallback_result
                            else:
                                logger.warning(f"⚠️ Fallback也未能提取到业务数据")
                    
                    if data_type == 'unknown' and has_data:
                        # 如果data_type是unknown但has_data是true，尝试推断类型
                        if data.get('risks'):
                            data['data_type'] = 'risk_matrix'
                        elif data.get('values') and len(data.get('values', [])) > 1:
                            if '年' in str(data.get('labels', [])) or '月' in str(data.get('labels', [])):
                                data['data_type'] = 'time_series'
                            else:
                                data['data_type'] = 'comparison'
                        logger.info(f"✅ 推断数据类型: {data['data_type']}")
                    
                    logger.info(f"成功提取数据: {data_type}, has_data: {has_data}")
                    return data
                else:
                    # 如果无法解析JSON，对于风险类和结构类问题，尝试fallback提取
                    if question_type == 'risk':
                        logger.warning("⚠️ LLM未返回有效JSON，尝试从回答文本中直接提取风险名称")
                        return self._extract_risks_fallback(answer, query)
                    elif question_type == 'structure':
                        logger.warning("⚠️ LLM未返回有效JSON，尝试从回答文本中直接提取业务名称")
                        return self._extract_structure_fallback(answer, query)
                    return {"has_data": False}
            except json.JSONDecodeError as e:
                logger.warning(f"无法解析LLM返回的JSON: {str(e)}")
                # 对于风险类和结构类问题，尝试fallback提取
                if question_type == 'risk':
                    logger.warning("⚠️ JSON解析失败，尝试从回答文本中直接提取风险名称")
                    return self._extract_risks_fallback(answer, query)
                elif question_type == 'structure':
                    logger.warning("⚠️ JSON解析失败，尝试从回答文本中直接提取业务名称")
                    return self._extract_structure_fallback(answer, query)
                return {"has_data": False}
                
        except Exception as e:
            logger.error(f"提取数据失败: {str(e)}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            # 对于风险类和结构类问题，尝试fallback提取
            if question_type == 'risk':
                logger.warning("⚠️ 数据提取异常，尝试从回答文本中直接提取风险名称")
                return self._extract_risks_fallback(answer, query)
            elif question_type == 'structure':
                logger.warning("⚠️ 数据提取异常，尝试从回答文本中直接提取业务名称")
                return self._extract_structure_fallback(answer, query)
            return {"has_data": False}
    
    def _extract_risks_fallback(self, answer: str, query: str) -> Dict[str, Any]:
        """
        Fallback方法：从回答文本中直接提取风险名称列表
        
        Args:
            answer: 文本回答
            query: 用户查询
        
        Returns:
            Dict: 包含风险数据的字典
        """
        try:
            import re
            risks = []
            
            logger.info(f"🔍 开始Fallback提取风险数据，回答长度: {len(answer)}")
            logger.info(f"📝 回答文本前500字符: {answer[:500]}")
            
            # 从回答中提取风险名称（匹配常见的风险列表格式）
            # 模式1: "**1. 信用风险**" (Markdown加粗格式，最常见)
            # 模式2: "### 1. 信用风险" (Markdown标题格式，从日志看是这个格式)
            # 模式3: "1. 信用风险" (普通编号)
            risk_patterns = [
                r'\*\*\s*\d+\.\s*([^*\n]+?风险)\s*\*\*',  # Markdown加粗格式: **1. 信用风险**
                r'###\s*\d+\.\s*([^#\n]+?)(?:\n|$)',      # Markdown标题格式: ### 1. 信用风险
                r'\d+\.\s*([^#\n*]+?风险)(?:\n|$)',       # 编号列表格式: 1. 信用风险
                r'[（(](\d+)[）)]\s*([^#\n]+?风险)(?:\n|$)',  # 括号编号格式: (1) 信用风险
            ]
            
            for i, pattern in enumerate(risk_patterns):
                matches = re.findall(pattern, answer)
                logger.info(f"🔍 模式{i+1}匹配结果: {len(matches)}个")
                if matches:
                    logger.info(f"  匹配示例: {matches[:3]}")
                for match in matches:
                    if isinstance(match, tuple):
                        risk_name = match[-1].strip()  # 取最后一个元素
                    else:
                        risk_name = match.strip()
                    
                    # 清理风险名称（移除多余符号，但保留"风险"）
                    risk_name = re.sub(r'[：:：\*]', '', risk_name).strip()
                    
                    # 检查是否包含"风险"关键词
                    if '风险' in risk_name and len(risk_name) < 20:
                        # 避免重复
                        if not any(r.get('name') == risk_name for r in risks):
                            risks.append({
                                "name": risk_name,
                                "probability": 3,  # 默认值
                                "impact": 3       # 默认值
                            })
            
            # 如果通过模式匹配没有找到，尝试从常见风险关键词中提取
            if not risks:
                common_risks = ['信用风险', '市场风险', '操作风险', '流动性风险', '法律风险', '声誉风险', '战略风险']
                for risk_name in common_risks:
                    if risk_name in answer:
                        risks.append({
                            "name": risk_name,
                            "probability": 3,
                            "impact": 3
                        })
            
            if risks:
                logger.info(f"✅ Fallback提取到 {len(risks)} 个风险: {[r['name'] for r in risks]}")
                return {
                    "has_data": True,
                    "data_type": "risk_matrix",
                    "risks": risks
                }
            else:
                logger.warning("⚠️ Fallback方法也未提取到风险数据")
                return {"has_data": False}
                
        except Exception as e:
            logger.error(f"Fallback提取风险数据失败: {str(e)}")
            return {"has_data": False}
    
    def _extract_structure_fallback(self, answer: str, query: str) -> Dict[str, Any]:
        """
        Fallback方法：从回答文本中直接提取业务名称列表（用于结构类问题）
        
        Args:
            answer: 文本回答
            query: 用户查询
        
        Returns:
            Dict: 包含业务结构数据的字典
        """
        try:
            import re
            businesses = []
            
            logger.info(f"🔍 开始Fallback提取业务结构数据，回答长度: {len(answer)}")
            logger.info(f"📝 回答文本前500字符: {answer[:500]}")
            
            # 从回答中提取业务名称（匹配常见的业务列表格式）
            # 模式1: "1.  **批发金融业务**" (编号+Markdown加粗格式，从日志看是这个格式)
            # 模式2: "**批发金融业务**" (Markdown加粗格式)
            # 模式3: "*   **批发金融业务**" (列表中的加粗)
            # 模式4: "1. 批发金融业务" (编号列表)
            # 模式5: "批发金融业务：" (冒号格式)
            business_patterns = [
                r'\d+\.\s+\*\*([^*\n]+?业务)\s*\*\*',  # 编号+Markdown加粗: 1.  **批发金融业务**
                r'\*\*([^*\n]+?业务)\s*\*\*',  # Markdown加粗格式: **批发金融业务**
                r'\*\s+\*\*([^*\n]+?业务)\s*\*\*',  # 列表中的加粗: *   **批发金融业务**
                r'\d+\.\s+([^#\n*]+?业务)(?:\s*[：:：]|$)',  # 编号列表格式: 1. 批发金融业务
                r'([^#\n*]+?业务)\s*[：:：]',  # 冒号格式: 批发金融业务：
                r'([^#\n*]+?金融)(?:\s*[：:：]|$)',  # 金融相关: 批发金融
                r'([^#\n*]+?分部)(?:\s*[：:：]|$)',  # 分部: 批发金融分部
            ]
            
            # 业务关键词（用于识别业务名称）
            business_keywords = ['业务', '金融', '分部', '板块', '部门']
            
            for i, pattern in enumerate(business_patterns):
                matches = re.findall(pattern, answer)
                logger.info(f"🔍 模式{i+1}匹配结果: {len(matches)}个")
                if matches:
                    logger.info(f"  匹配示例: {matches[:3]}")
                for match in matches:
                    if isinstance(match, tuple):
                        business_name = match[-1].strip()  # 取最后一个元素
                    else:
                        business_name = match.strip()
                    
                    # 清理业务名称（移除多余符号）
                    business_name = re.sub(r'[：:：\*]', '', business_name).strip()
                    
                    # 检查是否包含业务关键词
                    if any(keyword in business_name for keyword in business_keywords) and len(business_name) < 30:
                        # 避免重复
                        if not any(b == business_name for b in businesses):
                            businesses.append(business_name)
            
            # 如果通过模式匹配没有找到，尝试从常见业务关键词中提取
            if not businesses:
                # 查找包含"业务"、"金融"、"分部"的短语
                fallback_patterns = [
                    r'([^。，\n]+?[业务金融分部板块])',
                ]
                for pattern in fallback_patterns:
                    matches = re.findall(pattern, answer)
                    for match in matches:
                        match = match.strip()
                        if any(keyword in match for keyword in business_keywords) and 2 < len(match) < 30:
                            if not any(b == match for b in businesses):
                                businesses.append(match)
            
            # 如果还是没有找到，尝试从回答中提取所有包含"业务"的短语
            if not businesses:
                all_business_matches = re.findall(r'[^。，\n]{0,20}[业务金融分部板块][^。，\n]{0,10}', answer)
                for match in all_business_matches[:10]:  # 限制最多10个
                    match = match.strip()
                    if 2 < len(match) < 30:
                        if not any(b == match for b in businesses):
                            businesses.append(match)
            
            logger.info(f"✅ Fallback提取到 {len(businesses)} 个业务: {businesses}")
            
            if businesses:
                # 为每个业务分配默认值（如果没有数值，使用相等权重）
                values = [100 / len(businesses)] * len(businesses)
                
                return {
                    "has_data": True,
                    "data_type": "comparison",  # 使用comparison类型，可以生成柱状图或饼图
                    "labels": businesses,
                    "values": values,
                    "unit": "%"
                }
            else:
                return {"has_data": False}
        except Exception as e:
            logger.error(f"Fallback提取业务结构数据失败: {str(e)}")
            return {"has_data": False}
    
    async def _extract_data_from_table_sources(
        self,
        query: str,
        table_sources: List[Dict],
        answer: str
    ) -> Dict[str, Any]:
        """
        从表格来源中提取数据
        
        Args:
            query: 用户查询
            table_sources: 表格来源列表
            answer: 文本回答
        
        Returns:
            Dict: 提取的数据
        """
        try:
            # 合并所有表格文本
            table_texts = []
            for source in table_sources:
                text = source.get('text', '')
                if text:
                    table_texts.append(text)
            
            if not table_texts:
                return {"has_data": False}
            
            combined_table_text = "\n\n".join(table_texts[:3])  # 最多使用前3个表格
            
            # 记录表格数据预览，便于调试
            logger.info(f"📊 表格数据预览: {combined_table_text[:500]}...")
            
            prompt = f"""
分析以下查询和表格数据，提取可用于可视化的数据。

查询: {query}

文本回答: {answer}

表格数据:
    {combined_table_text}

【特别重要 - 营业收入数据提取】
- 如果查询涉及"营业收入"，必须在表格中查找包含"营业收入"、"营业总收入"、"收入"等关键词的行
- 仔细检查表格的列标题，找到包含年份或时间周期的列
- 提取该行对应的所有年份的数值
- 如果表格格式是：| 营业收入 | 2021年 | 2022年 | 2023年 |，则提取所有年份的数值

请从表格数据中提取以下信息（以JSON格式返回）：
1. has_data: 是否包含可视化数据（true/false）
2. data_type: 数据类型（time_series/comparison/distribution/single_value/table）
3. labels: 标签列表（如年份、类别等）
4. values: 数值列表
5. series: 多系列数据（如果有多个指标）
6. unit: 数值单位（如元、%、万等）
7. time_period: 时间周期（如果是时间序列）

重要提示：
- 如果查询涉及"趋势"、"变化"、"增长"等，data_type应该是time_series
- 如果查询涉及"对比"、"比较"，data_type应该是comparison
- 必须从表格中提取具体的数值，不要使用占位符
- 如果表格中有多列数据，提取所有相关列

示例输出：
{{
    "has_data": true,
    "data_type": "time_series",
    "labels": ["2021年", "2022年", "2023年"],
    "values": [1000000, 1200000, 1500000],
    "unit": "元",
    "time_period": "年度"
}}

如果无法从表格中提取数据，返回：
{{
    "has_data": false
}}
"""
            
            response = await self.llm.acomplete(prompt)
            response_text = str(response).strip()
            
            # 尝试解析JSON
            try:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    # 验证数据有效性
                    if data.get('has_data') and data.get('values') and len(data.get('values', [])) > 0:
                        return data
                    else:
                        logger.warning("提取的数据无效（缺少values或values为空）")
                        return {"has_data": False}
                else:
                    return {"has_data": False}
            except json.JSONDecodeError as e:
                logger.warning(f"无法解析LLM返回的JSON: {str(e)}")
                logger.debug(f"响应文本: {response_text[:500]}")
                return {"has_data": False}
                
        except Exception as e:
            logger.error(f"从表格来源提取数据失败: {str(e)}")
            return {"has_data": False}
    
    async def _recommend_chart_type(
        self,
        query: str,
        data: Dict[str, Any],
        answer: Optional[str] = None,
        question_type: Optional[str] = None
    ) -> ChartRecommendation:
        """
        推荐图表类型（增强版：同时考量问题和回答的综合策略）
        
        推荐策略：
        1. 问题类型分析（权重：40%）：基于查询的问题类型（data/conclusion/structure/process/risk等）
        2. 回答内容分析（权重：35%）：分析回答中的内容特征（时间序列、对比、占比、趋势等）
        3. 数据类型分析（权重：25%）：基于提取的数据结构（time_series/comparison/distribution等）
        
        Args:
            query: 用户查询
            data: 提取的数据
            answer: 文本回答（新增，用于分析回答内容特征）
            question_type: 问题类型（可选，如果不提供会自动分类）
        
        Returns:
            ChartRecommendation: 图表推荐
        """
        try:
            # 如果没有提供问题类型，自动分类
            if question_type is None:
                # 需要answer，但这里没有，所以用query和data来推断
                question_type = 'data'  # 默认
            
            data_type = data.get('data_type', 'unknown')
            
            # ========== 第一步：分析回答内容特征 ==========
            answer_features = self._analyze_answer_features(answer, query) if answer else {}
            logger.info(f"📊 回答内容特征: {answer_features}")
            
            # 特殊处理：风险矩阵数据
            if data_type == 'risk_matrix' and question_type == 'risk':
                logger.info("检测到风险矩阵数据，推荐散点图")
                return ChartRecommendation(
                    recommended_chart_type=ChartType.SCATTER,
                    reason="风险与不确定性类：风险矩阵（概率 × 影响）",
                    data_characteristics=f"数据类型: risk_matrix, 风险数量: {len(data.get('risks', []))}",
                    alternative_charts=[ChartType.HEATMAP]
                )
            
            # 第一步：基于问题类型推荐（优先）
            question_based_type = None
            if question_type in VIEW_RECOMMENDATION_MAP:
                view_config = VIEW_RECOMMENDATION_MAP[question_type]
                chart_types = view_config['chart_types']
                if chart_types:
                    # 对于过程与变化类，优先推荐LINE图（可用于时间轴）
                    if question_type == 'process':
                        # 过程类问题优先使用LINE图表示时间轴
                        if ChartType.LINE in chart_types:
                            question_based_type = ChartType.LINE
                        else:
                            question_based_type = chart_types[0]
                    # 对于风险类，优先推荐SCATTER图（风险矩阵）
                    elif question_type == 'risk':
                        if ChartType.SCATTER in chart_types:
                            question_based_type = ChartType.SCATTER
                        else:
                            question_based_type = chart_types[0]
                    # 根据数据特征选择最合适的图表类型
                    elif data_type == 'time_series' and ChartType.LINE in chart_types:
                        question_based_type = ChartType.LINE
                    elif data_type == 'comparison' and ChartType.BAR in chart_types:
                        question_based_type = ChartType.BAR
                    elif data_type == 'distribution' and ChartType.PIE in chart_types:
                        question_based_type = ChartType.PIE
                    else:
                        # 默认选择第一个推荐的图表类型
                        question_based_type = chart_types[0]
            
            # 第二步：基于数据类型的规则（保持向后兼容）
            type_mapping = {
                'time_series': ChartType.LINE,
                'comparison': ChartType.BAR,
                'distribution': ChartType.PIE,
                'single_value': ChartType.GAUGE,
                'table': ChartType.TABLE
            }
            
            data_based_type = type_mapping.get(data_type, ChartType.BAR)
            
            # 第三步：综合推荐（优先使用问题类型推荐，如果没有则使用数据类型推荐）
            recommended_type = question_based_type if question_based_type else data_based_type
            
            # 生成推荐理由
            reason_parts = []
            if question_type in VIEW_RECOMMENDATION_MAP:
                view_config = VIEW_RECOMMENDATION_MAP[question_type]
                reason_parts.append(f"问题类型：{view_config['description']}")
            reason_parts.append(f"数据类型：{data_type}")
            reason = "；".join(reason_parts) if reason_parts else f"基于数据类型'{data_type}'推荐"
            
            # 备选图表（结合问题类型和数据类型的备选）
            alternatives = []
            if question_type in VIEW_RECOMMENDATION_MAP:
                view_config = VIEW_RECOMMENDATION_MAP[question_type]
                alternatives.extend(view_config['chart_types'])
            
            # 添加基于数据类型的备选
            data_alternatives = {
                'time_series': [ChartType.AREA, ChartType.MULTI_LINE],
                'comparison': [ChartType.GROUPED_BAR, ChartType.LINE],
                'distribution': [ChartType.BAR, ChartType.FUNNEL],
                'table': [ChartType.HEATMAP]
            }
            alternatives.extend(data_alternatives.get(data_type, []))
            
            # 去重并移除已推荐的类型
            alternatives = [alt for alt in set(alternatives) if alt != recommended_type]
            
            logger.info(f"图表推荐: {recommended_type.value} (问题类型: {question_type}, 数据类型: {data_type})")
            
            return ChartRecommendation(
                recommended_chart_type=recommended_type,
                reason=reason,
                data_characteristics=f"问题类型: {question_type}, 数据类型: {data_type}, 数据点数: {len(data.get('values', []))}",
                alternative_charts=alternatives[:3]  # 最多返回3个备选
            )
            
        except Exception as e:
            logger.error(f"推荐图表类型失败: {str(e)}")
            # 出错时回退到原有逻辑
            data_type = data.get('data_type', 'unknown')
            type_mapping = {
                'time_series': ChartType.LINE,
                'comparison': ChartType.BAR,
                'distribution': ChartType.PIE,
                'single_value': ChartType.GAUGE,
                'table': ChartType.TABLE
            }
            return ChartRecommendation(
                recommended_chart_type=type_mapping.get(data_type, ChartType.BAR),
                reason="默认推荐（出错回退）",
                data_characteristics=f"数据类型: {data_type}"
            )

    def _get_visualization_example(self, question_type: str, chart_type: ChartType, query: str) -> Optional[Dict]:
        """
        根据问题类型和图表类型获取可视化示例
        
        Args:
            question_type: 问题类型
            chart_type: 图表类型
            query: 查询内容
        
        Returns:
            Dict: 示例配置或None
        """
        try:
            # 过程与变化类：优先使用时间轴示例
            if question_type == 'process':
                if '事件' in query or '时间' in query or '关键' in query:
                    return VISUALIZATION_EXAMPLES.get('timeline')
            
            # 风险类：使用风险矩阵示例
            elif question_type == 'risk':
                return VISUALIZATION_EXAMPLES.get('risk_matrix')
            
            # 结构类：根据查询内容选择示例
            elif question_type == 'structure':
                # 如果查询涉及流动、流向、价值链、业务结构、核心业务等，使用桑基图
                flow_keywords = [
                    '流动', '流向', '价值链', '供应链', '资金流', '业务流', '分配', '流转',
                    '核心', '业务结构', '业务关系', '业务组成', '业务分布', '业务关联',
                    '业务构成', '业务构成', '业务组成',  # 添加"业务构成"
                    '哪块业务', '什么业务', '业务占比', '业务贡献', '有哪些业务', '业务有哪些'
                ]
                if any(keyword in query.lower() for keyword in flow_keywords):
                    logger.info(f"🔍 查询包含桑基图关键词，选择桑基图示例")
                    return VISUALIZATION_EXAMPLES.get('sankey')
                else:
                    logger.info(f"🔍 查询不包含桑基图关键词，选择Treemap示例")
                    return VISUALIZATION_EXAMPLES.get('treemap')
            
            # 数据类：根据图表类型和查询内容选择
            elif question_type == 'data':
                if chart_type == ChartType.LINE:
                    # 如果查询中包含阈值、目标、平均值等关键词，使用标记线示例
                    threshold_keywords = ['阈值', '目标', '警戒', '平均值', '标准', '基准', '达到', '超过', '低于']
                    if any(keyword in query.lower() for keyword in threshold_keywords):
                        return VISUALIZATION_EXAMPLES.get('line_with_markline')
                    else:
                        return VISUALIZATION_EXAMPLES.get('line_with_markers')
                elif chart_type == ChartType.BAR:
                    return VISUALIZATION_EXAMPLES.get('bar_chart')
            
            return None
        except Exception as e:
            logger.warning(f"获取可视化示例失败: {str(e)}")
            return None
    
    def _adapt_view_size_to_card(self, chart_config: PlotlyChartConfig) -> PlotlyChartConfig:
        """
        步骤7: 视图大小适配视图卡片
        
        调整视图尺寸以适配前端视图卡片：
        - 视图卡片宽度：约800-1000px
        - 视图卡片高度：约400-600px
        - 确保视图在卡片中完整显示，不溢出
        
        Args:
            chart_config: 图表配置
        
        Returns:
            PlotlyChartConfig: 调整后的图表配置
        """
        try:
            # 视图卡片尺寸约束
            CARD_MAX_WIDTH = 1000
            CARD_MAX_HEIGHT = 500
            CARD_PADDING = 40  # 卡片内边距
            
            # 计算合适的视图尺寸
            view_width = min(CARD_MAX_WIDTH - CARD_PADDING, 900)
            view_height = min(CARD_MAX_HEIGHT - CARD_PADDING, 450)
            
            # 更新布局尺寸
            if chart_config.layout:
                chart_config.layout.height = view_height
                # 如果layout有width属性，也更新
                if hasattr(chart_config.layout, 'width'):
                    chart_config.layout.width = view_width
                # 调整边距以确保视图在卡片中居中显示
                if hasattr(chart_config.layout, 'margin'):
                    if chart_config.layout.margin:
                        chart_config.layout.margin = {
                            'l': 60,
                            'r': 40,
                            't': 50,
                            'b': 60
                        }
                    else:
                        chart_config.layout.margin = {
                            'l': 60,
                            'r': 40,
                            't': 50,
                            'b': 60
                        }
            
            logger.info(f"视图尺寸已调整为: {view_width}x{view_height}px (适配视图卡片)")
            return chart_config
            
        except Exception as e:
            logger.warning(f"视图大小适配失败: {str(e)}")
            return chart_config
    
    async def _generate_chart_config_with_example(
        self,
        chart_type: ChartType,
        data: Dict[str, Any],
        query: str,
        question_type: Optional[str] = None,
        example: Optional[Dict] = None
    ) -> PlotlyChartConfig:
        """
        使用视图示例代码作为prompt学习，生成图表配置
        
        Args:
            chart_type: 图表类型
            data: 数据
            query: 查询
            question_type: 问题类型
            example: 视图示例代码（作为prompt学习）
        
        Returns:
            PlotlyChartConfig: Plotly图表配置
        """
        # 如果提供了示例，使用示例指导生成
        if example:
            return await self._generate_chart_config(chart_type, data, query, question_type, example)
        else:
            return await self._generate_chart_config(chart_type, data, query, question_type)

    async def _generate_chart_config(
        self,
        chart_type: ChartType,
        data: Dict[str, Any],
        query: str,
        question_type: Optional[str] = None,
        example: Optional[Dict] = None
    ) -> PlotlyChartConfig:
        """
        生成图表配置

        Args:
            chart_type: 图表类型
            data: 数据
            query: 查询

        Returns:
            PlotlyChartConfig: Plotly图表配置
        """
        try:
            data_type = data.get('data_type', 'unknown')
            labels = data.get('labels', [])
            values = data.get('values', [])
            unit = data.get('unit', '')
            risks = data.get('risks', [])  # 风险数据
            
            # 特殊处理：风险矩阵数据
            if data_type == 'risk_matrix' and risks:
                logger.info(f"生成风险矩阵图表，包含 {len(risks)} 个风险")
                # 获取风险矩阵示例
                risk_example = self._get_visualization_example('risk', ChartType.SCATTER, query)
                example_config = risk_example.get('example', {}) if risk_example else {}
                
                # 提取风险数据
                x_data = [r.get('probability', 3) for r in risks]
                y_data = [r.get('impact', 3) for r in risks]
                text_data = [r.get('name', '未知风险') for r in risks]
                
                # 创建散点图轨迹
                trace = ChartTrace(
                    name="风险",
                    x=x_data,
                    y=y_data,
                    type="scatter",
                    mode="markers+text",
                    marker=example_config.get('marker', {"size": 20, "color": "rgb(255, 0, 0)"}),
                    text=text_data,
                    textposition="top center",
                    hovertemplate="<b>%{text}</b><br>概率: %{x}<br>影响: %{y}<extra></extra>"
                )
                
                # 创建布局
                layout = ChartLayout(
                    title=f"风险矩阵分析",
                    xaxis={
                        "title": example_config.get('xaxis', {}).get('title', '发生概率'),
                        "range": example_config.get('xaxis', {}).get('range', [0, 5])
                    },
                    yaxis={
                        "title": example_config.get('yaxis', {}).get('title', '影响程度'),
                        "range": example_config.get('yaxis', {}).get('range', [0, 5])
                    },
                    margin={'l': 80, 'r': 40, 't': 60, 'b': 60}
                )
                
                return PlotlyChartConfig(
                    traces=[trace],
                    layout=layout
                )
            
            # 获取可视化示例（用于指导生成）
            example = None
            if question_type:
                example = self._get_visualization_example(question_type, chart_type, query)
                if example:
                    logger.info(f"使用可视化示例: {example.get('description', '未知')}")

            # 生成标题
            title = self._generate_chart_title(query, chart_type)

            # 特殊处理：如果示例是桑基图，无论图表推荐是什么，都优先生成桑基图
            if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'sankey':
                logger.info("检测到桑基图示例，优先生成Sankey图表（忽略图表推荐）")
                example_config = example['example']
                
                # 从数据中提取节点和连接信息
                nodes_data = data.get('nodes', {})
                links_data = data.get('links', {})
                
                if not nodes_data or not links_data:
                    # 从labels和values构建简单的Sankey结构
                    # 对于业务构成类问题，可以构建：总业务收入 -> 各业务
                    logger.warning("数据中缺少nodes和links，尝试从labels和values构建桑基图结构")
                    labels = data.get('labels', [])
                    values = data.get('values', [])
                    
                    if labels and values:
                        # 构建简单的桑基图：假设有一个总业务收入，然后分配到各个业务
                        # 节点：总业务收入 + 各业务名称
                        node_labels = ['总业务收入'] + labels
                        node_colors = ['#fbb4ae'] + ['#b3cde3', '#ccebc5', '#decbe4', '#fed9a6', '#ffffcc'][:len(labels)]
                        
                        # 连接：总业务收入 -> 各业务（使用values作为流量）
                        source_indices = [0] * len(labels)  # 所有连接都从总业务收入（索引0）开始
                        target_indices = list(range(1, len(labels) + 1))  # 连接到各业务
                        link_values = values  # 使用values作为流量值
                        
                        nodes_data = {
                            'label': node_labels,
                            'color': node_colors[:len(node_labels)]
                        }
                        links_data = {
                            'source': source_indices,
                            'target': target_indices,
                            'value': link_values
                        }
                        logger.info(f"✅ 从labels和values构建桑基图: {len(node_labels)}个节点, {len(source_indices)}个连接")
                    else:
                        # 如果无法构建，使用示例数据作为模板
                        nodes_data = example_config.get('nodes', {})
                        links_data = example_config.get('links', {})
                
                # 创建Sankey trace
                trace = ChartTrace(
                    name="Sankey",
                    x=[],
                    y=[],
                    type="sankey"
                )
                
                # 将Sankey的特殊数据存储在config中
                sankey_data = {
                    'nodes': nodes_data,
                    'links': links_data
                }
                
                # 创建布局（优化大小以适配视图卡片）
                example_layout = example_config.get('layout', {})
                layout = ChartLayout(
                    title=title,
                    height=280,  # 减小高度以适配视图卡片（与普通图表一致）
                    showlegend=False,
                    template="plotly_white"
                )
                
                # 创建配置，包含Sankey的特殊数据
                config = {
                    'sankey_data': sankey_data,
                    'responsive': True,
                    'displayModeBar': True
                }
                
                return PlotlyChartConfig(
                    chart_type=ChartType.BAR,  # 使用BAR作为占位符，实际渲染时使用sankey
                    traces=[trace],
                    layout=layout,
                    config=config
                )

            # 根据图表类型和示例生成配置
            if chart_type == ChartType.BAR:
                # 如果示例是bar_chart，使用示例中的配置风格
                if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'bar':
                    example_config = example['example']
                    trace = ChartTrace(
                        name="数据",
                        x=labels,
                        y=values,
                        type="bar",
                        marker=example_config.get('marker', {"color": "rgb(55, 83, 109)"}),
                        text=[f"{v}{unit}" for v in values],
                        textposition=example_config.get('textposition', 'auto')
                    )
                else:
                    trace = ChartTrace(
                    name="数据",
                    x=labels,
                    y=values,
                    type="bar",
                    marker={"color": "rgb(55, 83, 109)"},
                    text=[f"{v}{unit}" for v in values],
                    textposition="auto"
                )

            elif chart_type == ChartType.LINE:
                # 如果示例是line_with_markers，使用示例中的配置风格（带标记点）
                if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'scatter':
                    example_config = example['example']
                    trace = ChartTrace(
                        name="趋势",
                        x=labels,
                        y=values,
                        type="scatter",
                        mode=example_config.get('mode', 'lines+markers'),
                        line={"color": "rgb(55, 128, 191)", "width": 3},
                        marker=example_config.get('marker', {"size": 8}),
                        text=[f"{v}{unit}" for v in values],
                        hovertemplate="%{x}: %{y}" + unit + "<extra></extra>"
                    )
                    # 如果有峰值标记示例，添加标记点
                    if example_config.get('annotations'):
                        # 找到最大值位置
                        if values:
                            max_idx = values.index(max(values))
                            max_value = max(values)
                            # 注意：Plotly的annotations需要在layout中设置，这里先记录
                            logger.info(f"检测到峰值: {labels[max_idx]} = {max_value}")
                else:
                    trace = ChartTrace(
                    name="趋势",
                    x=labels,
                    y=values,
                    type="scatter",
                    mode="lines+markers",
                    line={"color": "rgb(55, 128, 191)", "width": 3},
                    marker={"size": 8},
                    text=[f"{v}{unit}" for v in values],
                    hovertemplate="%{x}: %{y}" + unit + "<extra></extra>"
                )

            elif chart_type == ChartType.PIE:
                # 如果示例是treemap（业务结构图），可以考虑使用类似的结构
                if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'treemap':
                    # 注意：Plotly支持treemap，但当前ChartType可能没有，先使用PIE
                    logger.info("检测到业务结构图示例，使用饼图展示结构")
                
                trace = ChartTrace(
                    name="分布",
                    x=[],  # PIE图不需要x
                    y=values,
                    type="pie",
                    text=labels,
                    hovertemplate="%{label}: %{value}" + unit + " (%{percent})<extra></extra>"
                )

            # 处理风险矩阵（散点图）
            elif chart_type == ChartType.HEATMAP or (example and example.get('example', {}).get('chart_type') == 'scatter' and question_type == 'risk'):
                # 风险矩阵使用散点图
                if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'scatter':
                    example_config = example['example']
                    risk_data = example_config.get('data', [])
                    # 从实际数据中提取风险点，如果没有则使用示例格式
                    if risk_data and len(labels) > 0 and len(values) > 0:
                        # 假设labels是风险名称，values是概率或影响
                        scatter_x = values  # 概率
                        scatter_y = values  # 影响（这里简化，实际应该有两个维度）
                        scatter_text = labels
                    else:
                        scatter_x = values
                        scatter_y = values
                        scatter_text = labels
                    
                    trace = ChartTrace(
                        name="风险点",
                        x=scatter_x,
                        y=scatter_y,
                        type="scatter",
                        mode="markers+text",
                        marker=example_config.get('marker', {'size': 20}),
                        text=scatter_text,
                        textposition="top center"
                    )
                else:
                    # 默认散点图
                    trace = ChartTrace(
                        name="数据点",
                        x=labels,
                        y=values,
                        type="scatter",
                        mode="markers"
                    )

            # 特殊处理：桑基图（Sankey Diagram）
            elif example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'sankey':
                logger.info("检测到桑基图示例，生成Sankey图表")
                example_config = example['example']
                
                # 从数据中提取节点和连接信息
                # 如果数据中有nodes和links，直接使用；否则从labels和values构建
                nodes_data = data.get('nodes', {})
                links_data = data.get('links', {})
                
                if not nodes_data or not links_data:
                    # 从labels和values构建简单的Sankey结构
                    # 这里需要LLM在数据提取时提供nodes和links结构
                    logger.warning("数据中缺少nodes和links，尝试从labels和values构建")
                    # 如果无法构建，使用示例数据作为模板
                    nodes_data = example_config.get('nodes', {})
                    links_data = example_config.get('links', {})
                
                # 创建Sankey trace（使用config字段存储特殊配置）
                trace = ChartTrace(
                    name="Sankey",
                    x=[],  # Sankey不需要x
                    y=[],  # Sankey不需要y
                    type="sankey"
                )
                
                # 将Sankey的特殊数据存储在trace的额外字段中
                # 注意：ChartTrace模型可能不支持这些字段，我们需要使用config字段
                sankey_data = {
                    'nodes': nodes_data,
                    'links': links_data
                }
                
                # 创建布局（优化大小以适配视图卡片）
                example_layout = example_config.get('layout', {})
                layout = ChartLayout(
                    title=title,
                    height=280,  # 减小高度以适配视图卡片（与普通图表一致）
                    showlegend=False,  # Sankey图通常不显示图例
                    template="plotly_white"
                )
                
                # 创建配置，包含Sankey的特殊数据
                config = {
                    'sankey_data': sankey_data,
                    'responsive': True,
                    'displayModeBar': True
                }
                
                return PlotlyChartConfig(
                    chart_type=ChartType.BAR,  # 使用BAR作为占位符，实际渲染时使用sankey
                    traces=[trace],
                    layout=layout,
                    config=config
                )

            else:
                # 默认使用柱状图
                trace = ChartTrace(
                    name="数据",
                    x=labels,
                    y=values,
                    type="bar"
                )

            # 创建布局（根据示例调整）
            xaxis_title = data.get('x_title', '')
            # 处理y_title可能是列表的情况，取第一个或转换为字符串
            y_title_raw = data.get('y_title', unit)
            if isinstance(y_title_raw, list):
                yaxis_title = y_title_raw[0] if y_title_raw else unit
            elif isinstance(y_title_raw, str):
                yaxis_title = y_title_raw
            else:
                yaxis_title = unit
            
            # 如果示例是风险矩阵，使用示例中的轴标题
            if example and example.get('type') == 'plotly' and example.get('example', {}).get('chart_type') == 'scatter' and question_type == 'risk':
                example_config = example['example']
                if example_config.get('xaxis'):
                    xaxis_title = example_config['xaxis'].get('title', xaxis_title)
                if example_config.get('yaxis'):
                    yaxis_title = example_config['yaxis'].get('title', yaxis_title)
            
            layout = ChartLayout(
                title=title,
                xaxis_title=xaxis_title,
                yaxis_title=yaxis_title,
                height=500,
                showlegend=True,
                template="plotly_white",
                hovermode="closest"
            )
            
            # 如果示例中有轴范围设置，应用到布局中
            if example and example.get('type') == 'plotly':
                example_config = example.get('example', {})
                if example_config.get('xaxis', {}).get('range'):
                    # 注意：ChartLayout可能需要扩展支持range，这里先记录
                    logger.info(f"示例建议X轴范围: {example_config['xaxis']['range']}")
                if example_config.get('yaxis', {}).get('range'):
                    logger.info(f"示例建议Y轴范围: {example_config['yaxis']['range']}")

            return PlotlyChartConfig(
                chart_type=chart_type,
                traces=[trace],
                layout=layout
            )

        except Exception as e:
            logger.error(f"生成图表配置失败: {str(e)}")
            # 返回一个基本的配置
            return PlotlyChartConfig(
                chart_type=ChartType.BAR,
                traces=[ChartTrace(name="数据", x=[], y=[])],
                layout=ChartLayout(title="图表生成失败")
            )

    def _generate_chart_title(self, query: str, chart_type: ChartType) -> str:
        """
        生成图表标题

        Args:
            query: 查询
            chart_type: 图表类型

        Returns:
            str: 图表标题
        """
        # 简化查询作为标题
        title = query[:50] + "..." if len(query) > 50 else query

        # 添加图表类型后缀
        type_suffix = {
            ChartType.BAR: "对比图",
            ChartType.LINE: "趋势图",
            ChartType.PIE: "分布图",
            ChartType.AREA: "面积图",
            ChartType.SCATTER: "散点图"
        }

        suffix = type_suffix.get(chart_type, "")
        if suffix and suffix not in title:
            title = f"{title} - {suffix}"

        return title

    async def _generate_insights(
        self,
        data: Dict[str, Any],
        chart_type: ChartType
    ) -> List[VisualizationInsight]:
        """
        生成可视化洞察

        Args:
            data: 数据
            chart_type: 图表类型

        Returns:
            List[VisualizationInsight]: 洞察列表
        """
        try:
            insights = []
            values = data.get('values', [])
            labels = data.get('labels', [])

            if not values:
                return insights

            # 趋势洞察
            if len(values) >= 2:
                if values[-1] > values[0]:
                    trend = "上升"
                    change = ((values[-1] - values[0]) / values[0]) * 100
                elif values[-1] < values[0]:
                    trend = "下降"
                    change = ((values[0] - values[-1]) / values[0]) * 100
                else:
                    trend = "持平"
                    change = 0

                insights.append(VisualizationInsight(
                    insight_type="trend",
                    description=f"整体呈现{trend}趋势",
                    key_findings=[
                        f"从{labels[0] if labels else '起始'}到{labels[-1] if labels else '结束'}，变化幅度为{change:.1f}%"
                    ]
                ))

            # 极值洞察
            if len(values) > 0:
                max_val = max(values)
                min_val = min(values)
                max_idx = values.index(max_val)
                min_idx = values.index(min_val)

                insights.append(VisualizationInsight(
                    insight_type="comparison",
                    description="极值分析",
                    key_findings=[
                        f"最大值: {max_val} ({labels[max_idx] if labels and max_idx < len(labels) else ''})",
                        f"最小值: {min_val} ({labels[min_idx] if labels and min_idx < len(labels) else ''})",
                        f"差值: {max_val - min_val}"
                    ]
                ))

            return insights

        except Exception as e:
            logger.error(f"生成洞察失败: {str(e)}")
            return []


# ==================== 工具函数 ====================

async def generate_visualization_for_query(
    query: Annotated[str, "用户查询"],
    answer: Annotated[str, "文本回答"],
    data: Annotated[Optional[Dict[str, Any]], "原始数据"] = None,
    sources: Annotated[Optional[List[Dict]], "数据来源"] = None
) -> Dict[str, Any]:
    """
    为查询生成可视化

    这是一个可以被Agent调用的工具函数

    Args:
        query: 用户查询
        answer: 文本回答
        data: 原始数据（可选）
        sources: 数据来源（可选）

    Returns:
        Dict: 可视化响应
    """
    try:
        logger.info(f"工具调用: 生成可视化 - {query[:50]}...")

        viz_agent = VisualizationAgent()
        result = await viz_agent.generate_visualization(
            query=query,
            answer=answer,
            data=data,
            sources=sources
        )

        # 使用 model_dump() 而不是 dict() (Pydantic v2)
        return result.model_dump()

    except Exception as e:
        logger.error(f"❌ 可视化工具调用失败: {str(e)}")
        return {
            "query": query,
            "answer": answer,
            "has_visualization": False,
            "error": str(e)
        }

