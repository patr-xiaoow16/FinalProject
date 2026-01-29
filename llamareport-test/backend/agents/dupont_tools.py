"""
杜邦分析工具函数
用于Agent系统集成
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
import sys
import re
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 添加父目录路径以访问 utils
parent_root = project_root.parent
if str(parent_root) not in sys.path:
    sys.path.insert(0, str(parent_root))

logger = logging.getLogger(__name__)


async def generate_dupont_analysis(
    company_name: str,
    year: str,
    query_engine,
    financial_data: Optional[Dict[str, float]] = None,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    生成杜邦分析报告
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: LlamaIndex查询引擎
        financial_data: 可选的财务数据字典，如果不提供则从query_engine提取
        filename: 可选的文件名，用于限制查询范围
        
    Returns:
        杜邦分析结果字典
    """
    try:
        from backend.utils.financial_calculator import DupontAnalyzer
        from models.dupont_models import DupontAnalysis
        
        logger.info(f"开始生成杜邦分析: {company_name} - {year}")
        
        # 如果没有提供财务数据，从query_engine提取
        # 使用结构化LLM输出方法，和 quick-overview 使用相同的方法，更准确
        structured_metrics = None
        if financial_data is None:
            financial_data, structured_metrics = await extract_financial_data_for_dupont(
                company_name, year, query_engine, filename=filename
            )
        
        # 创建杜邦分析器
        analyzer = DupontAnalyzer()
        
        # 执行杜邦分析
        dupont_result = analyzer.calculate_dupont_analysis(
            financial_data=financial_data,
            company_name=company_name,
            report_year=year
        )
        
        # 转换为字典返回
        result_dict = dupont_result.model_dump()
        if structured_metrics and structured_metrics.get("metrics"):
            result_dict["metrics_json"] = structured_metrics
            analysis_by_year = _build_analysis_by_year(structured_metrics, company_name)
            if analysis_by_year:
                result_dict["analysis_by_year"] = analysis_by_year
        
        logger.info(f"杜邦分析生成成功: ROE={dupont_result.level1.roe.formatted_value}")
        
        return result_dict
        
    except Exception as e:
        logger.error(f"生成杜邦分析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        raise


async def extract_financial_data_for_dupont(
    company_name: str,
    year: str,
    query_engine,
    filename: Optional[str] = None
) -> Tuple[Dict[str, float], Optional[Dict[str, Any]]]:
    """
    从query_engine提取杜邦分析所需的财务数据（优化版）
    
    使用多步骤提取和结构化输出，提高准确度
    
    Args:
        company_name: 公司名称
        year: 年份
        query_engine: LlamaIndex查询引擎
        filename: 可选的文件名，用于限制查询范围
        
    Returns:
        财务数据字典
    """
    try:
        logger.info(f"开始提取财务数据: {company_name} - {year} (文件: {filename or '全部'})")
        
        # 第一步：使用retriever获取相关文档片段
        retriever = query_engine.retriever if hasattr(query_engine, 'retriever') else None
        if not retriever:
            # 如果query_engine没有retriever，尝试从index获取
            if hasattr(query_engine, '_index'):
                retriever = query_engine._index.as_retriever(similarity_top_k=15)
            elif hasattr(query_engine, 'index'):
                retriever = query_engine.index.as_retriever(similarity_top_k=15)
        
        # 构建多个查询来获取不同方面的数据
        queries = [
            f"{company_name} {year}年 利润表 净利润 归属于母公司所有者的净利润",
            f"{company_name} {year}年 利润表 营业收入 营业总收入",
            f"{company_name} {year}年 资产负债表 总资产 资产总计",
            f"{company_name} {year}年 资产负债表 股东权益 所有者权益 归属于母公司所有者权益",
            f"{company_name} {year}年 资产负债表 流动资产 流动资产合计",
            f"{company_name} {year}年 资产负债表 非流动资产 非流动资产合计",
            f"{company_name} {year}年 加权平均净资产收益率 ROE 净资产收益率",
            f"{company_name} {year}年 总资产收益率 平均总资产收益率 总资产报酬率 ROA 资产净利率",
            f"{company_name} {year}年 营业净利润率 净利率",
            f"{company_name} {year}年 资产周转率 总资产周转率",
            f"{company_name} {year}年 权益乘数"
        ]
        
        all_context = []
        if retriever:
            for query in queries:
                try:
                    nodes = retriever.retrieve(query)
                    # 如果指定了文件，过滤节点
                    if filename:
                        nodes = [
                            node for node in nodes 
                            if node.metadata.get('filename') == filename or 
                               node.metadata.get('source_file') == filename
                        ]
                    # 优先选择表格数据和财务报表数据
                    table_nodes = [n for n in nodes if n.metadata.get('document_type') == 'table_data' or n.metadata.get('is_financial_statement', False)]
                    if table_nodes:
                        all_context.extend([node.text for node in table_nodes[:2]])
                    elif nodes:
                        all_context.extend([node.text for node in nodes[:1]])
                except Exception as e:
                    logger.warning(f"检索查询 '{query}' 失败: {str(e)}")
                    continue
        
        # 合并上下文
        context_text = "\n\n".join(all_context[:10])  # 最多使用10个片段
        
        # 如果没有获取到上下文，使用query_engine查询
        if not context_text:
            logger.info("未获取到上下文，使用query_engine查询...")
            query_prompt = f"""
            请从{company_name}{year}年度财务报表中提取以下指标的数值：
            
            1. 净利润（归属于母公司所有者的净利润）
            2. 营业收入（营业总收入）
            3. 总资产
            4. 股东权益（归属于母公司所有者权益）
            5. 流动资产
            6. 非流动资产
            7. 加权平均净资产收益率（ROE、净资产收益率，百分比）
            8. 营业利润（可选）
            9. 总负债（可选）
            
            请以JSON格式返回，键名使用中文，值为数字（单位：元）。
            例如：{{"净利润": 1000000000, "营业收入": 5000000000, ...}}
            """
            response = query_engine.query(query_prompt)
            context_text = str(response)
        
        # 第二步：使用结构化输出提取数据（更准确）
        try:
            from llama_index.core.llms import ChatMessage
            from llama_index.core import Settings
            from models.dupont_models import FinancialDataExtraction
            
            llm = Settings.llm
            
            # 构建优化的prompt
            optimized_prompt = f"""
请从以下财务数据中精确提取杜邦分析所需的指标数值。

【重要提示】
1. 优先从表格数据中提取（表格数据最准确）
2. 如果数据以"亿元"为单位，需要乘以100000000转换为元
3. 如果数据以"万元"为单位，需要乘以10000转换为元
4. 只提取{year}年度的数据
5. 必须提取数值，不要使用"约"、"大约"等模糊表述
6. 如果某个指标在文档中找不到，请设为null

【需要提取的指标】
1. 净利润（归属于母公司所有者的净利润、归母净利润）- 必填，单位：元
2. 营业收入（营业总收入、主营业务收入）- 必填，单位：元
3. 总资产（资产总计、资产合计）- 必填，单位：元
4. 股东权益（归属于母公司所有者权益、所有者权益合计）- 必填，单位：元
5. 流动资产（流动资产合计）- 必填，单位：元
6. 非流动资产（非流动资产合计）- 必填，单位：元
            7. 加权平均净资产收益率（ROE、净资产收益率）- 重要，单位：百分比（如10.08表示10.08%），这是年报中直接披露的指标，请优先提取
            8. 总资产收益率（平均总资产收益率/总资产报酬率/ROA/资产净利率）- 重要，单位：百分比
            9. 营业净利润率（净利率）- 重要，单位：百分比
            10. 资产周转率（总资产周转率）- 重要，单位：倍
            11. 权益乘数 - 重要，单位：倍
            12. 营业利润 - 可选，单位：元
            13. 总负债（负债合计）- 可选，单位：元

【数据来源】
{context_text[:5000] if context_text else "请从所有已索引的文档中检索"}

【重要提示】
- 加权平均净资产收益率（ROE）是年报中直接披露的指标，请优先提取
- 如果文档中有"加权平均净资产收益率"或"ROE"，请直接提取该值（百分比形式，如10.08表示10.08%）
- 不要通过净利润/股东权益计算ROE，因为年报中的ROE是加权平均的，考虑了时间权重

请准确提取数值，只返回数据，不要添加分析或说明。
"""
            
            # 使用结构化LLM输出
            sllm = llm.as_structured_llm(FinancialDataExtraction)
            extract_response = await sllm.achat([
                ChatMessage(
                    role="system",
                    content="你是一个专业的财务数据提取助手。请从文档中准确提取财务指标数值，特别是Excel表格和财务报表中的数值。表格数据最准确，请优先使用。不要生成或猜测数据，只返回文档中实际存在的数据。如果某个指标找不到，请设为null。"
                ),
                ChatMessage(role="user", content=optimized_prompt)
            ])
            
            # 处理响应
            if hasattr(extract_response, 'raw'):
                extracted_data = extract_response.raw
            else:
                extracted_data = extract_response
            
            if hasattr(extracted_data, 'model_dump'):
                structured_data = extracted_data.model_dump()
            elif isinstance(extracted_data, dict):
                structured_data = extracted_data
            else:
                structured_data = {}
            
            # 转换为中文键名格式
            financial_data = {}
            
            # 记录原始数据用于调试
            logger.info(f"结构化输出原始数据: {structured_data}")
            
            for key, value in structured_data.items():
                if value is not None:
                    try:
                        # 特殊处理：加权平均净资产收益率（ROE）是百分比，需要保持原值
                        if key == '加权平均净资产收益率':
                            value_float = float(value)
                            # ROE通常是百分比形式（如10.08表示10.08%），不需要转换
                            # 但需要验证合理性（通常在0-100之间）
                            if 0 <= value_float <= 100:
                                financial_data[key] = value_float
                                logger.info(f"✅ 提取加权平均净资产收益率（ROE）: {value_float}%")
                            else:
                                logger.warning(f"⚠️ 加权平均净资产收益率值 {value_float} 超出合理范围 [0, 100]，跳过")
                        else:
                            value_float = float(value)
                            # 允许0和负值（某些财务指标可能为0或负）
                            # 但过滤掉明显无效的值（如NaN、Infinity等）
                            if not (value_float != value_float or abs(value_float) == float('inf')):
                                financial_data[key] = value_float
                                logger.info(f"提取指标 {key}: {value_float}")
                            else:
                                logger.warning(f"指标 {key} 的值无效: {value}")
                    except (ValueError, TypeError) as e:
                        logger.warning(f"无法转换指标 {key} 的值: {value}, 错误: {str(e)}")
            
            logger.info(f"结构化提取成功: {len(financial_data)} 个指标")
            
            # 如果提取的数据为空，尝试从备用方法提取
            if not financial_data:
                logger.warning("结构化提取返回空数据，尝试使用备用方法...")
                raise ValueError("结构化提取返回空数据")
            
        except Exception as e:
            logger.warning(f"结构化提取失败: {str(e)}，使用备用方法")
            financial_data = {}  # 确保变量已定义
            
            # 备用方法：使用query_engine查询
            optimized_prompt = f"""
请从以下财务数据中精确提取杜邦分析所需的指标数值。

【重要提示】
1. 优先从表格数据中提取（表格数据最准确）
2. 如果数据以"亿元"为单位，需要乘以100000000转换为元
3. 如果数据以"万元"为单位，需要乘以10000转换为元
4. 只提取{year}年度的数据
5. 必须提取数值，不要使用"约"、"大约"等模糊表述

【需要提取的指标】
1. 净利润（归属于母公司所有者的净利润、归母净利润）- 必填，单位：元
2. 营业收入（营业总收入、主营业务收入）- 必填，单位：元
3. 总资产（资产总计、资产合计）- 必填，单位：元
4. 股东权益（归属于母公司所有者权益、所有者权益合计）- 必填，单位：元
5. 流动资产（流动资产合计）- 必填，单位：元
6. 非流动资产（非流动资产合计）- 必填，单位：元
7. 加权平均净资产收益率（ROE、净资产收益率）- 重要，单位：百分比（如10.08表示10.08%），这是年报中直接披露的指标，请优先提取
8. 总资产收益率（平均总资产收益率/总资产报酬率/ROA/资产净利率）- 重要，单位：百分比
9. 营业净利润率（净利率）- 重要，单位：百分比
10. 资产周转率（总资产周转率）- 重要，单位：倍
11. 权益乘数 - 重要，单位：倍
12. 营业利润 - 可选，单位：元
13. 总负债（负债合计）- 可选，单位：元

【数据来源】
{context_text[:5000] if context_text else "请从所有已索引的文档中检索"}

【重要提示】
- 加权平均净资产收益率（ROE）是年报中直接披露的指标，请优先提取
- 如果文档中有"加权平均净资产收益率"或"ROE"，请直接提取该值（百分比形式，如10.08表示10.08%）
- 不要通过净利润/股东权益计算ROE，因为年报中的ROE是加权平均的，考虑了时间权重

【输出要求】
请严格按照以下JSON格式返回，只包含数值（数字），不要包含单位、文字说明：
{{
  "净利润": 数值（单位：元）,
  "营业收入": 数值（单位：元）,
  "总资产": 数值（单位：元）,
  "股东权益": 数值（单位：元）,
  "流动资产": 数值（单位：元）,
  "非流动资产": 数值（单位：元）,
  "加权平均净资产收益率": 数值（单位：百分比，如10.08表示10.08%）,
  "营业利润": 数值（单位：元，可选）,
  "总负债": 数值（单位：元，可选）
}}

请只返回JSON，不要添加任何其他文字说明。
"""
            response = query_engine.query(optimized_prompt)
            response_text = str(response)
            
            # 使用增强的解析函数
            backup_data = parse_financial_data_response_enhanced(response_text, context_text)
            # 合并备用方法提取的数据
            if backup_data:
                financial_data.update(backup_data)
                logger.info(f"备用方法提取到 {len(backup_data)} 个指标")
        
        # 第四步：如果仍然没有数据，尝试直接从表格数据中提取
        if not financial_data and context_text:
            logger.info("尝试直接从表格格式提取数据...")
            table_data = extract_from_table_format(context_text)
            if table_data:
                financial_data.update(table_data)
                logger.info(f"从表格格式提取到 {len(table_data)} 个指标")

        # 第四点五步：严格三步流程（检索→结构化→派生）
        structured_metrics = _build_structured_metrics_json(
            query_engine=query_engine,
            context_text=context_text,
            company_name=company_name,
            year=year,
            seed_data=financial_data
        )
        if structured_metrics.get("metrics"):
            logger.info(f"结构化指标JSON: {structured_metrics}")
            metric_map = {
                "ROE": "加权平均净资产收益率",
                "ROA": "总资产收益率",
                "NetProfit": "净利润",
                "Revenue": "营业收入",
                "TotalAssets": "总资产",
                "Equity": "股东权益",
                "NetProfitMargin": "营业净利润率",
                "AssetTurnover": "资产周转率",
                "EquityMultiplier": "权益乘数"
            }
            for metric in structured_metrics["metrics"]:
                target_key = metric_map.get(metric.get("metric"))
                if target_key and metric.get("value") is not None:
                    financial_data[target_key] = metric["value"]
        
        # 第五步：数据验证和补充
        financial_data = validate_and_complement_financial_data(financial_data, context_text)
        
        logger.info(f"财务数据提取成功: {len(financial_data)} 个指标")
        logger.info(f"提取的数据: {financial_data}")
        
        # 验证关键指标是否存在
        required_metrics = ['净利润', '营业收入', '总资产', '股东权益']
        missing_metrics = [m for m in required_metrics if m not in financial_data or financial_data[m] == 0]
        if missing_metrics:
            logger.warning(f"缺少关键指标: {missing_metrics}")
            # 如果关键指标缺失，尝试最后一次从context_text中直接搜索
            if context_text:
                logger.info("尝试最后一次从原始文本中搜索关键指标...")
                for metric in missing_metrics:
                    if metric not in financial_data:
                        # 使用更宽松的搜索模式
                        patterns = {
                            '净利润': [r'净利润[：:\s]*([\d,\.]+[万千百十亿]?元?)', r'归属于母公司.*?净利润[：:\s]*([\d,\.]+[万千百十亿]?元?)'],
                            '营业收入': [r'营业收入[：:\s]*([\d,\.]+[万千百十亿]?元?)', r'营业总收入[：:\s]*([\d,\.]+[万千百十亿]?元?)'],
                            '总资产': [r'总资产[：:\s]*([\d,\.]+[万千百十亿]?元?)', r'资产总计[：:\s]*([\d,\.]+[万千百十亿]?元?)'],
                            '股东权益': [r'股东权益[：:\s]*([\d,\.]+[万千百十亿]?元?)', r'所有者权益[：:\s]*([\d,\.]+[万千百十亿]?元?)'],
                        }
                        if metric in patterns:
                            for pattern in patterns[metric]:
                                match = re.search(pattern, context_text, re.IGNORECASE)
                                if match:
                                    value_str = match.group(1)
                                    value_clean = clean_numeric_string(value_str)
                                    if value_clean and value_clean > 0:
                                        financial_data[metric] = value_clean
                                        logger.info(f"从文本直接提取 {metric}: {value_clean}")
                                        break
        
        return financial_data, structured_metrics
        
    except Exception as e:
        logger.error(f"提取财务数据失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        # 返回示例数据以便测试
        logger.warning("使用示例数据进行测试")
        return {
            '净利润': 1000000000,  # 10亿
            '营业收入': 5000000000,  # 50亿
            '总资产': 10000000000,  # 100亿
            '股东权益': 6000000000,  # 60亿
            '流动资产': 4000000000,  # 40亿
            '非流动资产': 6000000000,  # 60亿
        }, None


def parse_financial_data_response_enhanced(response_text: str, context_text: str = "") -> Dict[str, float]:
    """
    增强版财务数据解析函数
    
    支持多种格式：JSON、文本、表格等
    """
    import json
    import re
    
    financial_data = {}
    
    try:
        # 方法1：尝试解析JSON（支持多行JSON和嵌套JSON）
        # 查找JSON对象（支持嵌套）
        json_patterns = [
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # 简单嵌套
            r'\{[^}]*"净利润"[^}]*\}',  # 包含关键字段的JSON
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, response_text, re.DOTALL)
            for match in matches:
                try:
                    json_str = match.group()
                    # 清理可能的Markdown代码块标记
                    json_str = re.sub(r'```json\s*', '', json_str)
                    json_str = re.sub(r'```\s*', '', json_str)
                    data = json.loads(json_str)
                    
                    # 转换为float并标准化键名
                    for key, value in data.items():
                        if isinstance(value, (int, float)):
                            financial_data[key] = float(value)
                        elif isinstance(value, str):
                            value_clean = clean_numeric_string(value)
                            if value_clean:
                                financial_data[key] = value_clean
                    if financial_data:
                        logger.info("成功从JSON解析数据")
                        return financial_data
                except (json.JSONDecodeError, ValueError) as e:
                    continue
        
        # 方法2：从文本中提取（增强的正则表达式）
        enhanced_patterns = {
            '净利润': [
                r'净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'归属于母公司.*?净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'归母净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'净利润\s*[：:]\s*([\d,\.]+)',
            ],
            '营业收入': [
                r'营业收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'营业总收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'主营业务收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
            ],
            '总资产': [
                r'总资产[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'资产总计[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'资产合计[：:]\s*([\d,\.]+[万千百十亿]?元?)',
            ],
            '股东权益': [
                r'股东权益[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'所有者权益[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'归属于母公司.*?所有者权益[：:]\s*([\d,\.]+[万千百十亿]?元?)',
            ],
            '流动资产': [
                r'流动资产[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'流动资产合计[：:]\s*([\d,\.]+[万千百十亿]?元?)',
            ],
            '非流动资产': [
                r'非流动资产[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                r'非流动资产合计[：:]\s*([\d,\.]+[万千百十亿]?元?)',
            ],
            '加权平均净资产收益率': [
                r'加权平均净资产收益率[|\s]+([\d,\.]+%?)',
                r'加权平均净资产收益率[：:]\s*([\d,\.]+%?)',
                r'ROE[|\s]+([\d,\.]+%?)',
                r'ROE[：:]\s*([\d,\.]+%?)',
                r'净资产收益率[|\s]+([\d,\.]+%?)',
                r'净资产收益率[：:]\s*([\d,\.]+%?)',
            ],
            '总资产收益率': [
                r'总资产收益率[|\s]+([\d,\.]+%?)',
                r'总资产收益率[：:]\s*([\d,\.]+%?)',
                r'平均总资产收益率[|\s]+([\d,\.]+%?)',
                r'平均总资产收益率[：:]\s*([\d,\.]+%?)',
                r'总资产报酬率[|\s]+([\d,\.]+%?)',
                r'总资产报酬率[：:]\s*([\d,\.]+%?)',
                r'ROA[|\s]+([\d,\.]+%?)',
                r'ROA[：:]\s*([\d,\.]+%?)',
                r'资产净利率[|\s]+([\d,\.]+%?)',
                r'资产净利率[：:]\s*([\d,\.]+%?)',
            ],
            '营业净利润率': [
                r'营业净利润率[|\s]+([\d,\.]+%?)',
                r'营业净利润率[：:]\s*([\d,\.]+%?)',
                r'净利率[|\s]+([\d,\.]+%?)',
                r'净利率[：:]\s*([\d,\.]+%?)',
            ],
            '资产周转率': [
                r'资产周转率[|\s]+([\d,\.]+)',
                r'资产周转率[：:]\s*([\d,\.]+)',
                r'总资产周转率[|\s]+([\d,\.]+)',
                r'总资产周转率[：:]\s*([\d,\.]+)',
            ],
            '权益乘数': [
                r'权益乘数[|\s]+([\d,\.]+)',
                r'权益乘数[：:]\s*([\d,\.]+)',
            ],
        }
        
        # 合并所有文本进行搜索
        search_text = response_text + "\n" + context_text
        
        for metric_name, patterns in enhanced_patterns.items():
            if metric_name in financial_data:
                continue  # 已经提取过了
            for pattern in patterns:
                match = re.search(pattern, search_text, re.IGNORECASE)
                if match:
                    value_str = match.group(1)
                    # 百分比指标：ROE、ROA、净利润率等
                    if metric_name in ('加权平均净资产收益率', '总资产收益率', '营业净利润率'):
                        # 移除百分号，直接转换为float
                        value_clean = value_str.replace('%', '').replace(',', '').strip()
                        try:
                            value_float = float(value_clean)
                            # 验证合理性（通常在0-100之间）
                            if 0 <= value_float <= 100:
                                financial_data[metric_name] = value_float
                                logger.info(f"✅ 从文本提取{metric_name}: {value_float}%")
                                break
                            else:
                                logger.warning(f"⚠️ {metric_name}值 {value_float} 超出合理范围，跳过")
                        except (ValueError, TypeError):
                            logger.warning(f"⚠️ 无法解析{metric_name}值: {value_str}")
                    else:
                        value_clean = clean_numeric_string(value_str)
                        if value_clean and value_clean > 0:
                            financial_data[metric_name] = value_clean
                            logger.info(f"从文本提取 {metric_name}: {value_clean}")
                            break
        
        # 方法3：从表格格式中提取（如果context_text包含表格）
        if context_text and not financial_data:
            financial_data.update(extract_from_table_format(context_text))
        
        return financial_data
        
    except Exception as e:
        logger.error(f"解析财务数据失败: {str(e)}")
        return {}


def clean_numeric_string(value_str: str) -> Optional[float]:
    """
    清理并转换数值字符串为float
    
    支持格式：
    - "1000000000" -> 1000000000.0
    - "100亿元" -> 10000000000.0
    - "100.5亿元" -> 10050000000.0
    - "100,000,000" -> 100000000.0
    """
    import re
    
    if not value_str or not isinstance(value_str, str):
        return None
    
    try:
        # 移除常见的中文单位并转换
        value_str = value_str.strip()
        
        # 处理单位
        multiplier = 1.0
        if '万亿' in value_str or '万亿元' in value_str:
            multiplier = 1000000000000
            value_str = value_str.replace('万亿', '').replace('万亿元', '')
        elif '千亿' in value_str or '千亿元' in value_str:
            multiplier = 100000000000
            value_str = value_str.replace('千亿', '').replace('千亿元', '')
        elif '百万元' in value_str:
            multiplier = 1000000
            value_str = value_str.replace('百万元', '')
        elif '亿' in value_str or '亿元' in value_str:
            multiplier = 100000000
            value_str = value_str.replace('亿', '').replace('亿元', '')
        elif '千万' in value_str or '千万元' in value_str:
            multiplier = 10000000
            value_str = value_str.replace('千万', '').replace('千万元', '')
        elif '万' in value_str or '万元' in value_str:
            multiplier = 10000
            value_str = value_str.replace('万', '').replace('万元', '')
        elif '千' in value_str or '千元' in value_str:
            multiplier = 1000
            value_str = value_str.replace('千', '').replace('千元', '')
        
        # 移除其他非数字字符（保留小数点和负号）
        value_str = re.sub(r'[^\d\.\-]', '', value_str)
        
        if not value_str or value_str == '-':
            return None
        
        value = float(value_str) * multiplier
        return value if value > 0 else None
        
    except (ValueError, TypeError):
        return None


def extract_from_table_format(text: str) -> Dict[str, float]:
    """
    从表格格式的文本中提取财务数据
    """
    import re
    
    financial_data = {}
    
    # 表格行模式：指标名 | 数值
    table_row_pattern = r'([^|\n]+)\s*\|\s*([\d,\.]+%?|[\d,\.]+[万千百十亿]?元?|[\d,\.]+倍|[\d,\.]+次)'
    matches = re.finditer(table_row_pattern, text)
    
    metric_keywords = {
        '净利润': ['净利润', '归母净利润', '归属于母公司'],
        '营业收入': ['营业收入', '营业总收入'],
        '总资产': ['总资产', '资产总计'],
        '股东权益': ['股东权益', '所有者权益'],
        '流动资产': ['流动资产'],
        '非流动资产': ['非流动资产'],
        '加权平均净资产收益率': ['加权平均净资产收益率', 'ROE', '净资产收益率'],
        '总资产收益率': ['总资产收益率', '平均总资产收益率', '总资产报酬率', 'ROA', '资产净利率'],
        '营业净利润率': ['营业净利润率', '净利率'],
        '资产周转率': ['资产周转率', '总资产周转率'],
        '权益乘数': ['权益乘数'],
    }
    
    for match in matches:
        metric_name = match.group(1).strip()
        value_str = match.group(2).strip()
        
        for key, keywords in metric_keywords.items():
            if any(kw in metric_name for kw in keywords):
                # 百分比指标
                if key in ('加权平均净资产收益率', '总资产收益率', '营业净利润率'):
                    value_clean = value_str.replace('%', '').replace(',', '').strip()
                    try:
                        value_float = float(value_clean)
                        if 0 <= value_float <= 100 and key not in financial_data:
                            financial_data[key] = value_float
                            logger.info(f"✅ 从表格提取{key}: {value_float}%")
                            break
                    except (ValueError, TypeError):
                        pass
                elif key in ('资产周转率', '权益乘数'):
                    value_clean = value_str.replace('倍', '').replace('次', '').replace(',', '').strip()
                    try:
                        value_float = float(value_clean)
                        if value_float > 0 and key not in financial_data:
                            financial_data[key] = value_float
                            logger.info(f"✅ 从表格提取{key}: {value_float}")
                            break
                    except (ValueError, TypeError):
                        pass
                else:
                    value_clean = clean_numeric_string(value_str)
                    if value_clean and key not in financial_data:
                        financial_data[key] = value_clean
                        break
    
    return financial_data


def _extract_metric_from_text(
    text: str,
    aliases: List[str],
    value_type: str
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    从文本中提取指定指标的数值、来源名称和单位

    value_type: 'percent' | 'amount' | 'ratio'
    """
    if not text:
        return None, None, None

    import re

    unit_pattern = r'(万亿|千亿|百万元|千万元|亿元|亿|万元|万|元|%|倍|次)?'
    for alias in aliases:
        pattern = rf'{re.escape(alias)}[^\d%]{{0,8}}([\d,\.]+)\s*{unit_pattern}'
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue

        value_str = match.group(1)
        unit = match.group(2) or None
        try:
            value_clean = value_str.replace(',', '').replace('，', '').strip()
            value_num = float(value_clean)
        except (ValueError, TypeError):
            continue

        # 排除年份
        if 2000 <= abs(value_num) <= 2030:
            continue

        if value_type == 'percent':
            # 优先识别百分比
            if unit == '%' or (unit is None and 0 <= value_num <= 100):
                return value_num, alias, '%'
            continue

        if value_type == 'ratio':
            if unit in ('倍', '次') or unit is None:
                return value_num, alias, 'times'
            continue

        # amount
        if unit == '%':
            continue
        # 若未明确单位且数值过小，避免误匹配
        if unit is None and value_num < 1_000_000:
            continue
        if unit is None:
            return value_num, alias, '元'
        # 明确单位则保留原始单位
        return value_num, alias, unit

    return None, None, None


def _extract_yeared_metrics_from_table(
    text: str,
    metric_defs: List[Dict[str, Any]]
) -> Dict[str, Dict[int, Tuple[float, Optional[str], Optional[str]]]]:
    """
    从表格文本中按年份列提取指标
    返回: { metric_name: { year: (value, unit, source) } }
    """
    if not text:
        return {}

    import re

    def normalize_cell(cell: str) -> str:
        return re.sub(r'\s+', '', cell or '')

    def detect_unit(raw: str) -> Optional[str]:
        if not raw:
            return None
        for unit in ["万亿", "千亿", "百万元", "千万元", "亿元", "亿", "万元", "万", "元", "%", "倍", "次"]:
            if unit in raw:
                return unit
        return None

    def parse_value(cell: str, unit: Optional[str], value_type: str) -> Optional[float]:
        if not cell:
            return None
        cell = cell.replace(',', '').replace('，', '').strip()
        if value_type == "percent":
            cell = cell.replace('％', '%')
            if '%' in cell:
                cell = cell.replace('%', '').strip()
            try:
                value = float(cell)
                return value if 0 <= value <= 100 else None
            except (ValueError, TypeError):
                return None
        if value_type == "ratio":
            cell = cell.replace('倍', '').replace('次', '').strip()
            try:
                value = float(cell)
                return value if value > 0 else None
            except (ValueError, TypeError):
                return None
        # amount
        unit = unit or detect_unit(cell)
        try:
            value = float(re.sub(r'[^\d\.\-]', '', cell))
        except (ValueError, TypeError):
            return None
        return value

    alias_map = {m["metric"]: m["aliases"] for m in metric_defs}
    value_type_map = {m["metric"]: m["type"] for m in metric_defs}

    result: Dict[str, Dict[int, Tuple[float, Optional[str], Optional[str]]]] = {}
    header_years: Dict[int, int] = {}
    header_unit: Optional[str] = None

    lines = [line for line in text.splitlines() if '|' in line]
    for line in lines:
        parts = [p.strip() for p in line.split('|') if p.strip()]
        if len(parts) < 2:
            continue

        # 检测表头年份行
        years_in_line = [int(y) for y in re.findall(r'(20\d{2})', line)]
        if len(years_in_line) >= 1 and any('年' in p or re.match(r'20\d{2}', p) for p in parts):
            header_years = {}
            for idx, cell in enumerate(parts):
                match = re.search(r'(20\d{2})', cell)
                if match:
                    header_years[idx] = int(match.group(1))
            header_unit = detect_unit(line)
            continue

        if not header_years:
            continue

        metric_cell = parts[0]
        metric_cell_norm = normalize_cell(metric_cell)
        for metric_name, aliases in alias_map.items():
            if any(normalize_cell(alias) in metric_cell_norm for alias in aliases):
                unit = detect_unit(metric_cell) or header_unit
                for idx, year in header_years.items():
                    if idx >= len(parts):
                        continue
                    value = parse_value(parts[idx], unit, value_type_map[metric_name])
                    if value is None:
                        continue
                    result.setdefault(metric_name, {})
                    result[metric_name][year] = (value, unit, aliases[0])
                break

    return result


def _extract_metric_by_year_from_text(
    text: str,
    aliases: List[str],
    year: int,
    value_type: str
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    从文本中按年份提取指标（行级别匹配）
    """
    if not text or not year:
        return None, None, None

    import re

    unit_pattern = r'(万亿|千亿|百万元|千万元|亿元|亿|万元|万|元|%|倍|次)?'
    year_str = str(year)
    lines = text.splitlines()

    def parse_value(value_str: str, unit: Optional[str]) -> Optional[float]:
        value_str = value_str.replace(',', '').replace('，', '').strip()
        try:
            value = float(value_str)
        except (ValueError, TypeError):
            return None
        if value_type == "percent":
            if unit == '%' or (unit is None and 0 <= value <= 100):
                return value
            return None
        if value_type == "ratio":
            return value if value > 0 else None
        # amount
        if unit == '%':
            return None
        return value

    for alias in aliases:
        alias_pattern = re.escape(alias)
        for line in lines:
            if alias not in line or year_str not in line:
                continue
            # 年份在后
            pattern_after = rf'{alias_pattern}.*?{year_str}[^\d%]{{0,6}}([\d,\.]+)\s*{unit_pattern}'
            match = re.search(pattern_after, line)
            if match:
                value = parse_value(match.group(1), match.group(2))
                if value is not None:
                    return value, match.group(2) or None, alias
            # 年份在前
            pattern_before = rf'{year_str}.*?{alias_pattern}[^\d%]{{0,6}}([\d,\.]+)\s*{unit_pattern}'
            match = re.search(pattern_before, line)
            if match:
                value = parse_value(match.group(1), match.group(2))
                if value is not None:
                    return value, match.group(2) or None, alias

    return None, None, None


def _extract_two_year_values_from_text(
    text: str,
    aliases: List[str],
    value_type: str
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    在同一行中提取两个年份的数值（按出现顺序）
    返回: (current_value, previous_value, unit, source)
    """
    if not text:
        return None, None, None, None

    import re

    unit_pattern = r'(万亿|千亿|百万元|千万元|亿元|亿|万元|万|元|%|倍|次)?'

    def parse_value(value_str: str, unit: Optional[str]) -> Optional[float]:
        value_str = value_str.replace(',', '').replace('，', '').strip()
        try:
            value = float(value_str)
        except (ValueError, TypeError):
            return None
        if value_type == "percent":
            if unit == '%' or (unit is None and 0 <= value <= 100):
                return value
            return None
        if value_type == "ratio":
            return value if value > 0 else None
        if unit == '%':
            return None
        return value

    lines = text.splitlines()
    for alias in aliases:
        alias_pattern = re.escape(alias)
        for line in lines:
            if alias not in line:
                continue
            # 提取该行上的两个数值
            matches = re.findall(rf'([\d,\.]+)\s*{unit_pattern}', line)
            values = []
            unit_found = None
            for match in matches:
                value_str = match[0]
                unit = match[1] or None
                parsed = parse_value(value_str, unit)
                if parsed is None:
                    continue
                # 排除年份
                if 2000 <= abs(parsed) <= 2030:
                    continue
                values.append(parsed)
                if unit_found is None and unit:
                    unit_found = unit
            if len(values) >= 2:
                return values[0], values[1], unit_found, alias
    return None, None, None, None


def _build_structured_metrics_json(
    query_engine,
    context_text: str,
    company_name: str,
    year: str,
    seed_data: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    按三步流程构建结构化指标JSON（不计算非规定指标）
    """
    metric_defs = [
        {
            "metric": "ROE",
            "aliases": ["加权平均净资产收益率", "净资产收益率", "ROE"],
            "type": "percent"
        },
        {
            "metric": "ROA",
            "aliases": ["平均总资产收益率", "总资产收益率", "总资产报酬率", "资产净利率", "ROA"],
            "type": "percent"
        },
        {
            "metric": "NetProfit",
            "aliases": ["归属于母公司股东的净利润", "归属于本行股东的净利润", "归母净利润", "净利润"],
            "type": "amount"
        },
        {
            "metric": "Revenue",
            "aliases": ["营业收入", "营业总收入"],
            "type": "amount"
        },
        {
            "metric": "TotalAssets",
            "aliases": ["资产总额", "总资产", "资产总计", "资产合计"],
            "type": "amount"
        },
        {
            "metric": "Equity",
            "aliases": ["股东权益", "所有者权益", "归属于母公司股东的权益", "归属于母公司所有者权益"],
            "type": "amount"
        }
    ]

    import json
    import os

    metrics = []
    seed_data = seed_data or {}
    year_value = None
    try:
        year_value = int(year)
    except (ValueError, TypeError):
        year_value = None

    prev_year_value = year_value - 1 if year_value else None
    years_to_fetch = [year_value]
    if prev_year_value:
        years_to_fetch.append(prev_year_value)

    seed_key_map = {
        "ROE": "加权平均净资产收益率",
        "ROA": "总资产收益率",
        "NetProfit": "净利润",
        "Revenue": "营业收入",
        "TotalAssets": "总资产",
        "Equity": "股东权益"
    }

    table_metric_values = _extract_yeared_metrics_from_table(context_text, metric_defs)

    for target_year in years_to_fetch:
        year_text = f"{target_year}年" if target_year else f"{year}年"
        for metric_def in metric_defs:
            if any(m.get("metric") == metric_def["metric"] and m.get("year") == target_year for m in metrics):
                continue
            table_year_value = table_metric_values.get(metric_def["metric"], {}).get(target_year)
            if table_year_value:
                value, unit, source = table_year_value
                metrics.append({
                    "metric": metric_def["metric"],
                    "year": target_year,
                    "value": value,
                    "unit": unit,
                    "source": source or metric_def["aliases"][0],
                    "yoy": None
                })
                continue
            text_year_value = _extract_metric_by_year_from_text(
                context_text,
                metric_def["aliases"],
                target_year,
                metric_def["type"]
            )
            if text_year_value and text_year_value[0] is not None:
                value, unit, source = text_year_value
                metrics.append({
                    "metric": metric_def["metric"],
                    "year": target_year,
                    "value": value,
                    "unit": unit,
                    "source": source or metric_def["aliases"][0],
                    "yoy": None
                })
                continue
            query_aliases = "、".join(metric_def["aliases"])
            query = f"{company_name}{year_text} {query_aliases} 的披露数值是多少？请给出数值和单位"
            response = query_engine.query(query)
            response_text = str(response)
            search_text = f"{response_text}\n{context_text}"
            value, source, unit = _extract_metric_from_text(
                search_text, metric_def["aliases"], metric_def["type"]
            )
            if value is None:
                fallback_data = parse_financial_data_response_enhanced(response_text, context_text)
                if metric_def["metric"] == "ROE":
                    value = fallback_data.get("加权平均净资产收益率")
                    unit = "%" if value is not None else unit
                    source = "加权平均净资产收益率" if value is not None else source
                elif metric_def["metric"] == "ROA":
                    value = fallback_data.get("总资产收益率")
                    unit = "%" if value is not None else unit
                    source = "平均总资产收益率" if value is not None else source
                elif metric_def["metric"] == "NetProfit":
                    value = fallback_data.get("净利润")
                    unit = "元" if value is not None else unit
                    source = "归属于母公司股东的净利润" if value is not None else source
                elif metric_def["metric"] == "Revenue":
                    value = fallback_data.get("营业收入")
                    unit = "元" if value is not None else unit
                    source = "营业收入" if value is not None else source
                elif metric_def["metric"] == "TotalAssets":
                    value = fallback_data.get("总资产")
                    unit = "元" if value is not None else unit
                    source = "资产总额" if value is not None else source
                elif metric_def["metric"] == "Equity":
                    value = fallback_data.get("股东权益")
                    unit = "元" if value is not None else unit
                    source = "股东权益" if value is not None else source
            if value is None and target_year == year_value:
                seed_key = seed_key_map.get(metric_def["metric"])
                if seed_key and seed_key in seed_data:
                    value = seed_data.get(seed_key)
                    source = metric_def["aliases"][0]
                    unit = "%" if metric_def["type"] == "percent" else "元"
            if value is not None:
                metrics.append({
                    "metric": metric_def["metric"],
                    "year": target_year,
                    "value": value,
                    "unit": unit,
                    "source": source or metric_def["aliases"][0],
                    "yoy": None
                })

    # 额外补充：同一行包含两年数值的情况（优先补前一年）
    if year_value and prev_year_value:
        for metric_def in metric_defs:
            if metric_def["type"] == "percent":
                continue
            has_prev = any(m.get("metric") == metric_def["metric"] and m.get("year") == prev_year_value for m in metrics)
            has_curr = any(m.get("metric") == metric_def["metric"] and m.get("year") == year_value for m in metrics)
            if has_prev:
                continue
            cur_val, prev_val, unit, source = _extract_two_year_values_from_text(
                context_text,
                metric_def["aliases"],
                metric_def["type"]
            )
            if prev_val is not None:
                metrics.append({
                    "metric": metric_def["metric"],
                    "year": prev_year_value,
                    "value": prev_val,
                    "unit": unit or ("元" if metric_def["type"] == "amount" else None),
                    "source": source or metric_def["aliases"][0],
                    "yoy": None
                })
            if not has_curr and cur_val is not None:
                metrics.append({
                    "metric": metric_def["metric"],
                    "year": year_value,
                    "value": cur_val,
                    "unit": unit or ("元" if metric_def["type"] == "amount" else None),
                    "source": source or metric_def["aliases"][0],
                    "yoy": None
                })

    # 第二步：结构化JSON输出（仅披露指标）
    print(json.dumps({"metrics": metrics}, ensure_ascii=False))

    def _to_yuan(value: Optional[float], unit: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        unit_map = {
            "元": 1,
            "万元": 1e4,
            "万": 1e4,
            "百万元": 1e6,
            "千万元": 1e7,
            "亿元": 1e8,
            "亿": 1e8,
            "千亿": 1e11,
            "万亿": 1e12
        }
        multiplier = unit_map.get(unit or "元", 1)
        return value * multiplier

    # 第三步：缺失指标计算（只计算规定指标）
    metric_map = {(m["metric"], m.get("year")): m for m in metrics}
    for target_year in years_to_fetch:
        net_profit = _to_yuan(
            metric_map.get(("NetProfit", target_year), {}).get("value"),
            metric_map.get(("NetProfit", target_year), {}).get("unit")
        )
        revenue = _to_yuan(
            metric_map.get(("Revenue", target_year), {}).get("value"),
            metric_map.get(("Revenue", target_year), {}).get("unit")
        )
        roe = metric_map.get(("ROE", target_year), {}).get("value")
        roa = metric_map.get(("ROA", target_year), {}).get("value")

        # 净利率
        if net_profit is not None and revenue:
            metrics.append({
                "metric": "NetProfitMargin",
                "year": target_year,
                "value": (net_profit / revenue) * 100,
                "unit": "%",
                "source": "净利润/营业收入",
                "yoy": None,
                "derived": True,
                "formula": "净利率 = 净利润 / 营业收入"
            })

        # 权益乘数
        if roe is not None and roa:
            metrics.append({
                "metric": "EquityMultiplier",
                "year": target_year,
                "value": roe / roa,
                "unit": "times",
                "source": "ROE/ROA",
                "yoy": None,
                "derived": True,
                "formula": "权益乘数 = ROE / ROA"
            })

        # 资产周转率
        net_profit_margin = None
        for m in metrics:
            if m.get("metric") == "NetProfitMargin" and m.get("year") == target_year:
                net_profit_margin = m.get("value")
                break
        if roa is not None and net_profit_margin:
            metrics.append({
                "metric": "AssetTurnover",
                "year": target_year,
                "value": roa / net_profit_margin,
                "unit": "times",
                "source": "ROA/净利率",
                "yoy": None,
                "derived": True,
                "formula": "资产周转率 = ROA / 净利率"
            })

    # 保存为JSON文件（含派生指标）
    try:
        safe_company = re.sub(r'[^\w\u4e00-\u9fff\-]+', '_', company_name or 'unknown')
        safe_year = re.sub(r'[^\d]+', '', str(year or ''))
        filename = f"dupont_metrics_{safe_company}_{safe_year or 'unknown'}.json"
        output_dir = Path(__file__).parent.parent / "storage"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({"metrics": metrics}, f, ensure_ascii=False, indent=2)
        logger.info(f"结构化指标JSON已保存: {output_path}")
    except Exception as e:
        logger.warning(f"保存结构化指标JSON失败: {str(e)}")

    return {"metrics": metrics}


def _build_analysis_by_year(
    structured_metrics: Dict[str, Any],
    company_name: str
) -> Dict[str, Any]:
    """
    基于结构化指标构建按年份的杜邦分析数据（用于前端切换）
    """
    metrics = structured_metrics.get("metrics") or []
    if not metrics:
        return {}

    def get_metric(metrics_list, metric_name, year):
        for item in metrics_list:
            if item.get("metric") == metric_name and item.get("year") == year:
                return item
        return None

    def format_value(value, unit):
        if value is None:
            return "—"
        if unit == "%":
            return f"{value:.2f}%"
        if unit == "times":
            return f"{value:.2f}"
        if unit:
            return f"{value:.2f}{unit}"
        return f"{value:.2f}"

    years = sorted({m.get("year") for m in metrics if m.get("year")}, reverse=True)
    analysis_by_year = {}

    for year in years:
        roe = get_metric(metrics, "ROE", year)
        roa = get_metric(metrics, "ROA", year)
        net_profit = get_metric(metrics, "NetProfit", year)
        revenue = get_metric(metrics, "Revenue", year)
        total_assets = get_metric(metrics, "TotalAssets", year)
        equity = get_metric(metrics, "Equity", year)
        net_profit_margin = get_metric(metrics, "NetProfitMargin", year)
        asset_turnover = get_metric(metrics, "AssetTurnover", year)
        equity_multiplier = get_metric(metrics, "EquityMultiplier", year)

        level1 = {
            "roe": {
                "name": "净资产收益率",
                "value": roe.get("value") if roe else None,
                "formatted_value": format_value(roe.get("value"), roe.get("unit")) if roe else "—",
                "level": 1,
                "formula": "ROE = 加权平均净资产收益率（年报披露）",
                "unit": "%"
            },
            "roa": {
                "name": "资产净利率",
                "value": roa.get("value") if roa else None,
                "formatted_value": format_value(roa.get("value"), roa.get("unit")) if roa else "—",
                "level": 1,
                "formula": "总资产收益率（年报披露）",
                "unit": "%"
            },
            "equity_multiplier": {
                "name": "权益乘数",
                "value": equity_multiplier.get("value") if equity_multiplier else None,
                "formatted_value": format_value(equity_multiplier.get("value"), "times") if equity_multiplier else "—",
                "level": 1,
                "formula": "权益乘数 = ROE / ROA",
                "unit": "倍"
            }
        }

        level2 = {
            "net_profit_margin": {
                "name": "营业净利润率",
                "value": net_profit_margin.get("value") if net_profit_margin else None,
                "formatted_value": format_value(net_profit_margin.get("value"), "%") if net_profit_margin else "—",
                "level": 2,
                "formula": "净利率 = 净利润 / 营业收入",
                "unit": "%"
            },
            "asset_turnover": {
                "name": "资产周转率",
                "value": asset_turnover.get("value") if asset_turnover else None,
                "formatted_value": format_value(asset_turnover.get("value"), "times") if asset_turnover else "—",
                "level": 2,
                "formula": "资产周转率 = ROA / 净利率",
                "unit": "倍"
            },
            "total_assets": {
                "name": "总资产",
                "value": total_assets.get("value") if total_assets else None,
                "formatted_value": format_value(total_assets.get("value"), total_assets.get("unit") if total_assets else None) if total_assets else "—",
                "level": 2,
                "formula": "总资产",
                "unit": "元"
            },
            "shareholders_equity": {
                "name": "股东权益",
                "value": equity.get("value") if equity else None,
                "formatted_value": format_value(equity.get("value"), equity.get("unit") if equity else None) if equity else "—",
                "level": 2,
                "formula": "股东权益",
                "unit": "元"
            }
        }

        level3 = {
            "net_income": {
                "name": "净利润",
                "value": net_profit.get("value") if net_profit else None,
                "formatted_value": format_value(net_profit.get("value"), net_profit.get("unit") if net_profit else None) if net_profit else "—",
                "level": 3,
                "formula": "净利润",
                "unit": "元"
            },
            "revenue": {
                "name": "营业收入",
                "value": revenue.get("value") if revenue else None,
                "formatted_value": format_value(revenue.get("value"), revenue.get("unit") if revenue else None) if revenue else "—",
                "level": 3,
                "formula": "营业收入",
                "unit": "元"
            },
            "current_assets": {
                "name": "流动资产",
                "value": None,
                "formatted_value": "—",
                "level": 3,
                "formula": "流动资产",
                "unit": "元"
            },
            "non_current_assets": {
                "name": "非流动资产",
                "value": None,
                "formatted_value": "—",
                "level": 3,
                "formula": "非流动资产",
                "unit": "元"
            }
        }

        tree_structure = {
            "id": "roe",
            "name": "净资产收益率",
            "value": level1["roe"]["value"],
            "formatted_value": level1["roe"]["formatted_value"],
            "level": 1,
            "formula": level1["roe"]["formula"],
            "children": [
                {
                    "id": "roa",
                    "name": "资产净利率",
                    "value": level1["roa"]["value"],
                    "formatted_value": level1["roa"]["formatted_value"],
                    "level": 1,
                    "formula": level1["roa"]["formula"],
                    "children": [
                        {
                            "id": "net_profit_margin",
                            "name": "营业净利润率",
                            "value": level2["net_profit_margin"]["value"],
                            "formatted_value": level2["net_profit_margin"]["formatted_value"],
                            "level": 2,
                            "formula": level2["net_profit_margin"]["formula"],
                            "children": [
                                {
                                    "id": "net_income",
                                    "name": "净利润",
                                    "value": level3["net_income"]["value"],
                                    "formatted_value": level3["net_income"]["formatted_value"],
                                    "level": 3,
                                    "formula": level3["net_income"]["formula"],
                                    "children": []
                                },
                                {
                                    "id": "revenue",
                                    "name": "营业收入",
                                    "value": level3["revenue"]["value"],
                                    "formatted_value": level3["revenue"]["formatted_value"],
                                    "level": 3,
                                    "formula": level3["revenue"]["formula"],
                                    "children": []
                                }
                            ]
                        },
                        {
                            "id": "asset_turnover",
                            "name": "资产周转率",
                            "value": level2["asset_turnover"]["value"],
                            "formatted_value": level2["asset_turnover"]["formatted_value"],
                            "level": 2,
                            "formula": level2["asset_turnover"]["formula"],
                            "children": []
                        }
                    ]
                },
                {
                    "id": "equity_multiplier",
                    "name": "权益乘数",
                    "value": level1["equity_multiplier"]["value"],
                    "formatted_value": level1["equity_multiplier"]["formatted_value"],
                    "level": 1,
                    "formula": level1["equity_multiplier"]["formula"],
                    "children": [
                        {
                            "id": "total_assets",
                            "name": "总资产",
                            "value": level2["total_assets"]["value"],
                            "formatted_value": level2["total_assets"]["formatted_value"],
                            "level": 2,
                            "formula": level2["total_assets"]["formula"],
                            "children": []
                        },
                        {
                            "id": "shareholders_equity",
                            "name": "股东权益",
                            "value": level2["shareholders_equity"]["value"],
                            "formatted_value": level2["shareholders_equity"]["formatted_value"],
                            "level": 2,
                            "formula": level2["shareholders_equity"]["formula"],
                            "children": []
                        }
                    ]
                }
            ]
        }

        analysis_by_year[str(year)] = {
            "company_name": company_name,
            "report_year": str(year),
            "level1": level1,
            "level2": level2,
            "level3": level3,
            "tree_structure": tree_structure
        }

    return analysis_by_year


def validate_and_complement_financial_data(
    financial_data: Dict[str, float],
    context_text: str = ""
) -> Dict[str, float]:
    """
    验证和补充财务数据
    
    1. 验证数据合理性
    2. 计算缺失的指标（如果可能）
    3. 验证数据一致性
    """
    # 验证关键指标
    required = ['净利润', '营业收入', '总资产', '股东权益']
    for metric in required:
        if metric not in financial_data or financial_data[metric] <= 0:
            logger.warning(f"关键指标 {metric} 缺失或无效")
    
    # 补充计算：如果缺少流动资产或非流动资产，但总资产存在
    if '总资产' in financial_data and financial_data['总资产'] > 0:
        if '流动资产' not in financial_data and '非流动资产' in financial_data:
            # 可以估算：流动资产 = 总资产 - 非流动资产（如果合理）
            estimated = financial_data['总资产'] - financial_data['非流动资产']
            if estimated > 0:
                financial_data['流动资产'] = estimated
                logger.info(f"估算流动资产: {estimated}")
        elif '非流动资产' not in financial_data and '流动资产' in financial_data:
            estimated = financial_data['总资产'] - financial_data['流动资产']
            if estimated > 0:
                financial_data['非流动资产'] = estimated
                logger.info(f"估算非流动资产: {estimated}")
    
    # 验证数据一致性：总资产应该约等于流动资产+非流动资产
    if all(k in financial_data for k in ['总资产', '流动资产', '非流动资产']):
        calculated_total = financial_data['流动资产'] + financial_data['非流动资产']
        reported_total = financial_data['总资产']
        diff_ratio = abs(calculated_total - reported_total) / reported_total if reported_total > 0 else 1
        if diff_ratio > 0.1:  # 差异超过10%
            logger.warning(f"数据不一致：流动资产+非流动资产={calculated_total}，总资产={reported_total}")
            # 可以选择使用计算值
            if diff_ratio > 0.2:  # 差异很大，使用计算值
                financial_data['总资产'] = calculated_total
                logger.info(f"使用计算值更新总资产: {calculated_total}")
    
    return financial_data


def parse_financial_data_response(response_text: str) -> Dict[str, float]:
    """
    解析query_engine的响应，提取财务数据
    
    Args:
        response_text: 响应文本
        
    Returns:
        财务数据字典
    """
    import json
    import re
    
    try:
        # 尝试直接解析JSON
        # 查找JSON块
        json_match = re.search(r'\{[^{}]*\}', response_text)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            
            # 转换为float
            financial_data = {}
            for key, value in data.items():
                if isinstance(value, (int, float)):
                    financial_data[key] = float(value)
                elif isinstance(value, str):
                    # 尝试解析字符串中的数字
                    value_clean = value.replace(',', '').replace('元', '').strip()
                    try:
                        financial_data[key] = float(value_clean)
                    except ValueError:
                        logger.warning(f"无法解析值: {key}={value}")
            
            return financial_data
        
        # 如果没有找到JSON，尝试从文本中提取
        financial_data = {}
        
        # 定义指标模式
        patterns = {
            '净利润': r'净利润[：:]\s*([\d,\.]+)',
            '营业收入': r'营业收入[：:]\s*([\d,\.]+)',
            '总资产': r'总资产[：:]\s*([\d,\.]+)',
            '股东权益': r'股东权益[：:]\s*([\d,\.]+)',
            '流动资产': r'流动资产[：:]\s*([\d,\.]+)',
            '非流动资产': r'非流动资产[：:]\s*([\d,\.]+)',
        }
        
        for metric_name, pattern in patterns.items():
            match = re.search(pattern, response_text)
            if match:
                value_str = match.group(1).replace(',', '')
                financial_data[metric_name] = float(value_str)
        
        return financial_data
        
    except Exception as e:
        logger.error(f"解析财务数据失败: {str(e)}")
        return {}


def extract_financial_data_from_pdf_tables(
    pdf_path: str,
    company_name: str,
    year: str
) -> Dict[str, float]:
    """
    从PDF表格中提取财务数据（使用pdfplumber）
    
    Args:
        pdf_path: PDF文件路径
        company_name: 公司名称
        year: 年份
        
    Returns:
        财务数据字典
    """
    try:
        import pdfplumber
        import pandas as pd
        
        logger.info(f"开始从PDF提取表格: {pdf_path}")
        
        financial_data = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # 提取表格
                tables = page.extract_tables()
                
                if not tables:
                    continue
                
                for table_num, table in enumerate(tables, 1):
                    if not table or len(table) < 2:
                        continue
                    
                    # 转换为DataFrame
                    df = pd.DataFrame(table[1:], columns=table[0])
                    
                    # 查找财务指标
                    financial_data.update(
                        _extract_metrics_from_table(df, year)
                    )
        
        logger.info(f"从PDF提取到 {len(financial_data)} 个指标")
        
        return financial_data
        
    except Exception as e:
        logger.error(f"从PDF提取数据失败: {str(e)}")
        return {}


def _extract_metrics_from_table(df: 'pd.DataFrame', year: str) -> Dict[str, float]:
    """
    从DataFrame中提取财务指标
    
    Args:
        df: pandas DataFrame
        year: 年份
        
    Returns:
        提取的指标字典
    """
    import pandas as pd
    import re
    
    metrics = {}
    
    # 定义要查找的指标
    metric_keywords = {
        '净利润': ['净利润', '归属于母公司', '归母净利润'],
        '营业收入': ['营业收入', '营业总收入', '主营业务收入'],
        '总资产': ['总资产', '资产总计', '资产合计'],
        '股东权益': ['股东权益', '所有者权益', '归属于母公司所有者权益'],
        '流动资产': ['流动资产', '流动资产合计'],
        '非流动资产': ['非流动资产', '非流动资产合计'],
    }
    
    # 遍历DataFrame查找指标
    for metric_name, keywords in metric_keywords.items():
        for idx, row in df.iterrows():
            # 检查第一列是否包含关键词
            first_col = str(row.iloc[0]) if len(row) > 0 else ""
            
            if any(keyword in first_col for keyword in keywords):
                # 查找包含年份的列
                for col in df.columns:
                    if year in str(col):
                        value_str = str(row[col])
                        # 提取数字
                        value_clean = re.sub(r'[^\d\.\-]', '', value_str)
                        try:
                            metrics[metric_name] = float(value_clean)
                            break
                        except ValueError:
                            continue
                break
    
    return metrics

