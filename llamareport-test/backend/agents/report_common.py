"""
Report shared helpers for data retrieval and validation.
"""

import logging
from typing import Dict, Any, List, Optional, Annotated, Tuple

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


def _parse_numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    if text in {"/", "-", "—"}:
        return None
    # 提取数字
    import re
    match = re.search(r"-?\d+(\.\d+)?", text)
    if not match:
        return None
    num = float(match.group(0))
    # 单位处理
    if "万亿" in text:
        num *= 1e12
    elif "亿" in text:
        num *= 1e8
    elif "万" in text:
        num *= 1e4
    return num


def _infer_role_from_variable_type(variable_type: Optional[str]) -> Optional[str]:
    if not variable_type:
        return None
    if "因变量" in variable_type:
        return "因变量"
    if "自变量" in variable_type:
        return "自变量"
    return None


def _build_metric_series(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    default_period: Optional[str]
) -> Dict[str, Dict[str, Any]]:
    series_map: Dict[str, Dict[str, Any]] = {}

    def _ensure_metric(name: str) -> Dict[str, Any]:
        if name not in series_map:
            series_map[name] = {
                "role": None,
                "category": None,
                "series": {}
            }
        return series_map[name]

    for item in indicator_extraction or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("metric")
        if not name:
            continue
        record = _ensure_metric(name)
        if item.get("variable_role"):
            record["role"] = item.get("variable_role")
        if item.get("category"):
            record["category"] = item.get("category")
        period = item.get("period") or default_period
        value = _parse_numeric_value(item.get("value"))
        if period and value is not None:
            record["series"][str(period)] = value

    for row in variable_table or []:
        if not isinstance(row, dict):
            continue
        name = row.get("metric")
        if not name:
            continue
        record = _ensure_metric(name)
        role = _infer_role_from_variable_type(row.get("variable_type"))
        if role:
            record["role"] = role
        period = row.get("period") or default_period
        value = _parse_numeric_value(row.get("value"))
        if period and value is not None:
            record["series"][str(period)] = value

    return series_map


def _pearson_correlation(x: List[float], y: List[float]) -> Optional[float]:
    if len(x) < 3 or len(y) < 3:
        return None
    import math
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    cov = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)
    if var_x == 0 or var_y == 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def _correlation_label(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    abs_value = abs(value)
    if abs_value >= 0.85:
        strength = "强"
    elif abs_value >= 0.7:
        strength = "中强"
    elif abs_value >= 0.5:
        strength = "中等"
    else:
        strength = "弱"
    direction = "正" if value >= 0 else "负"
    return f"{strength}{direction}相关"


def build_correlation_results(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    default_period: Optional[str]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    series_map = _build_metric_series(indicator_extraction, variable_table, default_period)
    targets = [name for name, info in series_map.items() if info.get("role") == "因变量"]
    drivers = [name for name, info in series_map.items() if info.get("role") == "自变量"]

    results: List[Dict[str, Any]] = []
    max_samples = 0

    for target in targets:
        target_series = series_map[target]["series"]
        for driver in drivers:
            if driver == target:
                continue
            driver_series = series_map[driver]["series"]
            shared_periods = sorted(set(target_series.keys()) & set(driver_series.keys()))
            if len(shared_periods) < 3:
                max_samples = max(max_samples, len(shared_periods))
                continue
            x = [target_series[p] for p in shared_periods]
            y = [driver_series[p] for p in shared_periods]
            corr = _pearson_correlation(x, y)
            max_samples = max(max_samples, len(shared_periods))
            results.append({
                "target_metric": target,
                "driver_metric": driver,
                "correlation": corr,
                "significance": _correlation_label(corr),
                "interpretation": None,
                "data_points": len(shared_periods)
            })

    data_sufficiency = {
        "is_sufficient": bool(results),
        "reason": None,
        "sample_description": None
    }
    if not results:
        reason = "可用于相关性计算的共同样本不足（至少需要3个时间点）"
        if not targets or not drivers:
            reason = "缺少因变量或自变量指标，无法计算相关性"
        data_sufficiency["is_sufficient"] = False
        data_sufficiency["reason"] = reason
        if max_samples:
            data_sufficiency["sample_description"] = f"最大可用样本数：{max_samples}"

    return results, data_sufficiency


def build_multiple_linear_regression(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    default_period: Optional[str]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    构建多元线性回归分析结果
    
    Args:
        indicator_extraction: 指标提取列表
        variable_table: 变量表
        default_period: 默认期间
    
    Returns:
        (回归结果字典, 数据充分性字典)
    """
    series_map = _build_metric_series(indicator_extraction, variable_table, default_period)
    targets = [name for name, info in series_map.items() if info.get("role") == "因变量"]
    drivers = [name for name, info in series_map.items() if info.get("role") == "自变量"]
    
    if not targets or not drivers or len(drivers) < 2:
        return {
            "target_metric": targets[0] if targets else None,
            "independent_variables": drivers,
            "coefficients": {},
            "r_squared": None,
            "interpretation": "自变量数量不足，无法进行多元线性回归分析"
        }, {
            "is_sufficient": False,
            "reason": "自变量数量不足（至少需要2个自变量）",
            "sample_description": None
        }
    
    # 找到共同的时间点
    target = targets[0]
    target_series = series_map[target]["series"]
    shared_periods = set(target_series.keys())
    
    for driver in drivers:
        driver_series = series_map[driver]["series"]
        shared_periods = shared_periods & set(driver_series.keys())
    
    shared_periods = sorted(shared_periods)
    
    if len(shared_periods) < 3:
        return {
            "target_metric": target,
            "independent_variables": drivers,
            "coefficients": {},
            "r_squared": None,
            "interpretation": "样本数量不足，无法进行多元线性回归分析"
        }, {
            "is_sufficient": False,
            "reason": f"共同样本数量不足（当前{len(shared_periods)}个，至少需要3个）",
            "sample_description": f"可用样本数：{len(shared_periods)}"
        }
    
    # 构建回归数据
    y = [target_series[p] for p in shared_periods]
    X = []
    for driver in drivers:
        driver_series = series_map[driver]["series"]
        X.append([driver_series[p] for p in shared_periods])
    
    # 简单的多元线性回归（使用最小二乘法）
    try:
        import numpy as np
        X_matrix = np.array(X).T
        y_vector = np.array(y)
        
        # 添加截距项
        X_with_intercept = np.column_stack([np.ones(len(y_vector)), X_matrix])
        
        # 计算回归系数
        coefficients = np.linalg.lstsq(X_with_intercept, y_vector, rcond=None)[0]
        
        # 计算R²
        y_pred = X_with_intercept @ coefficients
        ss_res = np.sum((y_vector - y_pred) ** 2)
        ss_tot = np.sum((y_vector - np.mean(y_vector)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else None
        
        # 构建系数字典
        coef_dict = {"intercept": float(coefficients[0])}
        for i, driver in enumerate(drivers):
            coef_dict[driver] = float(coefficients[i + 1])
        
        interpretation = f"多元线性回归模型R²为{r_squared:.3f}" if r_squared else "无法计算R²"
        
        return {
            "target_metric": target,
            "independent_variables": drivers,
            "coefficients": coef_dict,
            "r_squared": float(r_squared) if r_squared is not None else None,
            "interpretation": interpretation,
            "data_points": len(shared_periods)
        }, {
            "is_sufficient": True,
            "reason": None,
            "sample_description": f"使用{len(shared_periods)}个样本进行回归分析"
        }
    except Exception as e:
        logger.warning(f"多元线性回归计算失败: {str(e)}")
        return {
            "target_metric": target,
            "independent_variables": drivers,
            "coefficients": {},
            "r_squared": None,
            "interpretation": f"回归分析计算失败: {str(e)}"
        }, {
            "is_sufficient": False,
            "reason": f"回归计算失败: {str(e)}",
            "sample_description": None
        }


def build_factor_analysis(
    indicator_extraction: List[Dict[str, Any]],
    variable_table: List[Dict[str, Any]],
    default_period: Optional[str]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    构建因子分析结果
    
    Args:
        indicator_extraction: 指标提取列表
        variable_table: 变量表
        default_period: 默认期间
    
    Returns:
        (因子分析结果字典, 数据充分性字典)
    """
    series_map = _build_metric_series(indicator_extraction, variable_table, default_period)
    all_metrics = [name for name, info in series_map.items() if info.get("role") == "自变量"]
    
    if len(all_metrics) < 3:
        return {
            "factors": [],
            "factor_loadings": {},
            "variance_explained": {},
            "interpretation": "指标数量不足，无法进行因子分析"
        }, {
            "is_sufficient": False,
            "reason": "自变量数量不足（至少需要3个指标）",
            "sample_description": None
        }
    
    # 找到共同的时间点
    shared_periods = None
    for metric in all_metrics:
        metric_series = series_map[metric]["series"]
        if shared_periods is None:
            shared_periods = set(metric_series.keys())
        else:
            shared_periods = shared_periods & set(metric_series.keys())
    
    shared_periods = sorted(shared_periods) if shared_periods else []
    
    if len(shared_periods) < 3:
        return {
            "factors": [],
            "factor_loadings": {},
            "variance_explained": {},
            "interpretation": "样本数量不足，无法进行因子分析"
        }, {
            "is_sufficient": False,
            "reason": f"共同样本数量不足（当前{len(shared_periods)}个，至少需要3个）",
            "sample_description": f"可用样本数：{len(shared_periods)}"
        }
    
    # 构建数据矩阵
    try:
        import numpy as np
        data_matrix = []
        for metric in all_metrics:
            metric_series = series_map[metric]["series"]
            data_matrix.append([metric_series[p] for p in shared_periods])
        
        data_array = np.array(data_matrix)
        
        # 标准化数据
        data_std = (data_array - np.mean(data_array, axis=1, keepdims=True)) / (np.std(data_array, axis=1, keepdims=True) + 1e-8)
        
        # 计算相关系数矩阵
        corr_matrix = np.corrcoef(data_std)
        
        # 简单的因子分析（主成分分析）
        eigenvalues, eigenvectors = np.linalg.eig(corr_matrix)
        
        # 选择特征值大于1的因子
        significant_factors = [i for i, val in enumerate(eigenvalues) if val > 1.0]
        
        if not significant_factors:
            # 如果没有特征值>1的因子，选择前2个
            significant_factors = [0, 1] if len(eigenvalues) >= 2 else [0]
        
        factors = []
        factor_loadings = {}
        variance_explained = {}
        
        total_variance = np.sum(eigenvalues)
        
        for i, factor_idx in enumerate(significant_factors[:3]):  # 最多3个因子
            factor_name = f"因子{i+1}"
            factors.append(factor_name)
            
            # 因子载荷
            loadings = {}
            for j, metric in enumerate(all_metrics):
                loadings[metric] = float(eigenvectors[j, factor_idx])
            factor_loadings[factor_name] = loadings
            
            # 解释的方差比例
            variance_explained[factor_name] = float(eigenvalues[factor_idx] / total_variance) if total_variance > 0 else 0.0
        
        interpretation = f"提取了{len(factors)}个主要因子，累计解释方差{sum(variance_explained.values()):.1%}"
        
        return {
            "factors": factors,
            "factor_loadings": factor_loadings,
            "variance_explained": variance_explained,
            "interpretation": interpretation,
            "data_points": len(shared_periods)
        }, {
            "is_sufficient": True,
            "reason": None,
            "sample_description": f"使用{len(shared_periods)}个样本进行因子分析"
        }
    except Exception as e:
        logger.warning(f"因子分析计算失败: {str(e)}")
        return {
            "factors": [],
            "factor_loadings": {},
            "variance_explained": {},
            "interpretation": f"因子分析计算失败: {str(e)}"
        }, {
            "is_sufficient": False,
            "reason": f"因子分析计算失败: {str(e)}",
            "sample_description": None
        }


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

