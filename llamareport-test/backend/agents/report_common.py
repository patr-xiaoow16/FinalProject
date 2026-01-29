"""
Report shared helpers for data retrieval and validation.
"""

import logging
from typing import Dict, Any, List, Optional, Annotated

from llama_index.core.tools import QueryEngineTool

logger = logging.getLogger(__name__)


def _validate_and_clean_data(data: Dict[str, Any], model_class) -> Dict[str, Any]:
    """
    验证和清理数据，确保符合模型要求
    
    Args:
        data: 原始数据字典
        model_class: Pydantic模型类
    
    Returns:
        清理后的数据字典
    """
    if not isinstance(data, dict):
        return data
    
    try:
        # 尝试用模型验证数据
        validated = model_class(**data)
        return validated.model_dump()
    except Exception as e:
        logger.warning(f"数据验证失败，尝试清理: {str(e)}")
        # 如果验证失败，尝试清理常见问题
        cleaned = {}
        for key, value in data.items():
            # 跳过错误字段
            if key == "error":
                continue
            # 清理空值
            if value is None or value == "":
                continue
            # 清理无效的字符串
            if isinstance(value, str) and value.strip() == "":
                continue
            cleaned[key] = value
        return cleaned


def create_query_engine_tool(query_engine, name: str, description: str) -> QueryEngineTool:
    """
    创建查询引擎工具
    
    Args:
        query_engine: LlamaIndex 查询引擎
        name: 工具名称
        description: 工具描述
    
    Returns:
        QueryEngineTool 实例
    """
    return QueryEngineTool.from_defaults(
        query_engine=query_engine,
        name=name,
        description=description
    )


def retrieve_financial_data(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份,如'2023'"],
    metric_type: Annotated[str, "指标类型: balance_sheet_detailed, income_statement_detailed, cash_flow_detailed 等"],
    query_engine: Any
) -> str:
    """
    检索财务数据
    
    从年报中检索特定的财务指标数据
    
    Args:
        company_name: 公司名称
        year: 年份
        metric_type: 指标类型
        query_engine: 查询引擎
    
    Returns:
        财务数据的文本描述
    """
    import time
    retrieval_start = time.time()
    try:
        logger.debug(f"🔍 [retrieve_financial_data] 开始检索: {company_name} {year}年 {metric_type}")
        # 构建查询
        query_map = {
            "balance_sheet_detailed": (
                f"{company_name} {year}年 资产负债表 "
                "资产总额 发放贷款及垫款 个人贷款 企业贷款 投资类金融资产 "
                "现金及存放央行款项 存放同业款项 "
                "负债总额 吸收存款 个人存款 企业存款 向央行借款 同业负债 "
                "已发行债务证券 卖出回购金融资产"
            ),
            "income_statement_detailed": (
                f"{company_name} {year}年 利润表 "
                "营业收入合计 利息净收入 非利息净收入 手续费及佣金净收入 "
                "其他非利息净收入 投资收益 公允价值变动损益 "
                "营业支出合计 业务及管理费 信用及其他资产减值损失 税金及附加"
            ),
            "cash_flow_detailed": (
                f"{company_name} {year}年 现金流量表 "
                "经营活动现金流 投资活动现金流 筹资活动现金流 现金净变动额"
            )
        }
        
        query = query_map.get(metric_type, f"{company_name} {year}年 {metric_type}")
        
        # 执行查询 - 处理同步和异步两种情况
        try:
            # 尝试同步查询
            if hasattr(query_engine, 'query'):
                response = query_engine.query(query)
            else:
                # 如果query_engine是RAGEngine，使用其query方法
                if hasattr(query_engine, 'query'):
                    response = query_engine.query(query)
                else:
                    raise ValueError("query_engine 不支持 query 方法")
            
            # 提取响应内容
            if hasattr(response, 'response'):
                # Response对象，提取response属性
                content = str(response.response)
            elif hasattr(response, 'message'):
                # 有message属性
                if hasattr(response.message, 'content'):
                    content = str(response.message.content)
                else:
                    content = str(response.message)
            elif hasattr(response, 'content'):
                # 直接有content属性
                content = str(response.content)
            elif isinstance(response, dict):
                # 字典类型，提取answer或content
                content = response.get('answer', response.get('content', str(response)))
            else:
                # 其他类型，直接转换为字符串
                content = str(response)
            
            retrieval_time = time.time() - retrieval_start
            if retrieval_time > 30.0:
                logger.warning(f"⚠️ [retrieve_financial_data] {metric_type} 检索耗时过长: {retrieval_time:.2f}秒")
            else:
                logger.info(f"✅ [retrieve_financial_data] 检索财务数据成功: {metric_type}，耗时: {retrieval_time:.2f}秒")
            return content if content else f"未找到{metric_type}相关数据"
            
        except Exception as query_error:
            retrieval_time = time.time() - retrieval_start
            logger.error(f"❌ [retrieve_financial_data] 查询执行失败（耗时: {retrieval_time:.2f}秒）: {str(query_error)}")
            logger.error(f"[retrieve_financial_data] 错误类型: {type(query_error).__name__}")
            import traceback
            logger.error(f"[retrieve_financial_data] 错误堆栈:\n{traceback.format_exc()}")
            return f"检索失败（{metric_type}）: {str(query_error)}"
        
    except Exception as e:
        retrieval_time = time.time() - retrieval_start if 'retrieval_start' in locals() else 0
        logger.error(f"❌ [retrieve_financial_data] 检索财务数据异常（耗时: {retrieval_time:.2f}秒）: {str(e)}")
        logger.error(f"[retrieve_financial_data] 错误类型: {type(e).__name__}")
        import traceback
        logger.error(f"[retrieve_financial_data] 错误堆栈:\n{traceback.format_exc()}")(f"❌ 检索财务数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"检索失败: {str(e)}"


def retrieve_business_data(
    company_name: Annotated[str, "公司名称"],
    year: Annotated[str, "年份"],
    business_type: Annotated[str, "业务类型,如'主营业务'、'分部业务'、'产品业务'"],
    query_engine: Any
) -> str:
    """
    检索业务数据
    
    从年报中检索业务相关信息
    
    Args:
        company_name: 公司名称
        year: 年份
        business_type: 业务类型
        query_engine: 查询引擎
    
    Returns:
        业务数据的文本描述
    """
    try:
        query = f"{company_name} {year}年 {business_type} 业务收入 业务增长 市场份额"
        
        # 执行查询 - 处理同步和异步两种情况
        try:
            if hasattr(query_engine, 'query'):
                response = query_engine.query(query)
            else:
                raise ValueError("query_engine 不支持 query 方法")
            
            # 提取响应内容
            if hasattr(response, 'response'):
                content = str(response.response)
            elif hasattr(response, 'message'):
                if hasattr(response.message, 'content'):
                    content = str(response.message.content)
                else:
                    content = str(response.message)
            elif hasattr(response, 'content'):
                content = str(response.content)
            elif isinstance(response, dict):
                content = response.get('answer', response.get('content', str(response)))
            else:
                content = str(response)
            
            logger.info(f"✅ 检索业务数据成功: {business_type}")
            return content if content else f"未找到{business_type}相关数据"
            
        except Exception as query_error:
            logger.error(f"❌ 查询执行失败: {str(query_error)}")
            import traceback
            logger.error(traceback.format_exc())
            return f"检索失败: {str(query_error)}"
        
    except Exception as e:
        logger.error(f"❌ 检索业务数据失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return f"检索失败: {str(e)}"

