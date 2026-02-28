"""
查询API接口
"""

from typing import Dict, Any, Optional, List, Tuple
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import logging
from decimal import Decimal
from datetime import datetime

from core.rag_engine import RAGEngine
from agents.visualization_agent import VisualizationAgent
from models.report_models import FinancialSnapshot, KeyFinancialMetric
from agents.report_common import retrieve_financial_data
from agents.dupont_tools import parse_financial_data_response, extract_financial_data_for_dupont, generate_dupont_analysis
import re
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["query"])

# 全局RAG引擎实例（延迟初始化）
rag_engine = None

def get_rag_engine():
    """获取RAG引擎实例（延迟初始化）"""
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
    return rag_engine

class QueryRequest(BaseModel):
    question: str
    context_filter: Optional[Dict[str, Any]] = None
    enable_visualization: bool = True  # 是否启用可视化

class BatchQueryRequest(BaseModel):
    questions: List[str]
    context_filter: Optional[Dict[str, Any]] = None
    enable_visualization: bool = True  # 是否启用可视化

class SimilarContentRequest(BaseModel):
    query: str
    top_k: int = 5

class QuickOverviewRequest(BaseModel):
    """财务概况请求，可选按文件名限定检索范围"""
    filename: Optional[str] = None  # 选中的文件名，只从该文件（含 Excel 表格）检索

@router.post("/ask")
async def ask_question(request: QueryRequest):
    """
    提问接口（支持可视化）

    Args:
        request: 查询请求

    Returns:
        查询结果（可能包含可视化配置）
    """
    try:
        question = request.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")

        if len(question) > 1000:
            raise HTTPException(status_code=400, detail="问题过长，请控制在1000字符以内")

        logger.info(f"收到查询: {question[:50]}...")

        # 获取RAG引擎并执行查询
        rag_engine = get_rag_engine()
        result = rag_engine.query(question, request.context_filter)

        if result.get('error'):
            # 统一错误响应格式
            return JSONResponse(
                status_code=500,
                content={
                    "error": result.get('answer', '查询失败'),
                    "question": question,
                    "answer": result.get('answer', '查询失败'),
                    "sources": [],
                    "visualization": None
                }
            )

        # 基础响应 - 确保所有字段都存在
        response = {
            "question": question,
            "answer": result.get('answer', ''),
            "sources": result.get('sources', []),
            "context_filter": request.context_filter,
            "enhanced_query": result.get('enhanced_query', question),
            "visualization": None  # 初始化为None，后续可能被填充
        }

        # 如果启用可视化，尝试生成图表
        if request.enable_visualization:
            try:
                viz_agent = VisualizationAgent()
                
                # 记录查询和回答信息，便于调试
                logger.info(f"📊 开始生成可视化 - 查询: {question[:100]}...")
                logger.info(f"📊 回答长度: {len(result.get('answer', ''))} 字符")
                logger.info(f"📊 来源数量: {len(result.get('sources', []))}")
                
                viz_result = await viz_agent.generate_visualization(
                    query=question,
                    answer=result['answer'],
                    sources=result.get('sources', [])
                )

                # 添加可视化数据到响应
                response['visualization'] = viz_result.model_dump()
                logger.info(f"✅ 可视化生成成功: {viz_result.has_visualization}")
                
                # 如果可视化生成失败，记录详细信息
                if not viz_result.has_visualization:
                    logger.warning(f"⚠️ 可视化生成失败 - 查询: {question}")
                    logger.warning(f"⚠️ 回答预览: {result.get('answer', '')[:200]}...")
                    logger.warning(f"⚠️ 来源预览: {[s.get('text', '')[:100] for s in result.get('sources', [])[:3]]}")

            except Exception as viz_error:
                logger.warning(f"可视化生成失败: {str(viz_error)}")
                import traceback
                logger.warning(f"详细错误: {traceback.format_exc()}")
                response['visualization'] = {
                    "has_visualization": False,
                    "error": str(viz_error)
                }

        logger.info(f"查询完成: {question[:50]}...")
        
        # 确保响应格式统一
        response_data = {
            "question": response.get("question", question),
            "answer": response.get("answer", ""),
            "sources": response.get("sources", []),
            "context_filter": response.get("context_filter"),
            "enhanced_query": response.get("enhanced_query", question),
            "visualization": response.get("visualization")
        }
        
        return JSONResponse(status_code=200, content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.post("/batch")
async def batch_query(request: BatchQueryRequest):
    """
    批量查询接口
    
    Args:
        request: 批量查询请求
        
    Returns:
        批量查询结果
    """
    try:
        questions = request.questions
        if not questions:
            raise HTTPException(status_code=400, detail="问题列表不能为空")
        
        if len(questions) > 10:
            raise HTTPException(status_code=400, detail="一次最多查询10个问题")
        
        # 验证每个问题
        for i, question in enumerate(questions):
            if not question or not question.strip():
                raise HTTPException(status_code=400, detail=f"第{i+1}个问题不能为空")
            if len(question) > 1000:
                raise HTTPException(status_code=400, detail=f"第{i+1}个问题过长")
        
        logger.info(f"收到批量查询: {len(questions)} 个问题")
        
        results = []
        for i, question in enumerate(questions):
            try:
                question = question.strip()
                result = rag_engine.query(question, request.context_filter)
                
                if result.get('error'):
                    results.append({
                        "question_index": i,
                        "question": question,
                        "status": "error",
                        "error": result.get('answer', '查询失败')
                    })
                else:
                    results.append({
                        "question_index": i,
                        "question": question,
                        "status": "success",
                        "answer": result['answer'],
                        "sources": result.get('sources', []),
                        "enhanced_query": result.get('enhanced_query', question)
                    })
                
            except Exception as e:
                results.append({
                    "question_index": i,
                    "question": question,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"批量查询中第{i+1}个问题失败: {str(e)}")
        
        # 统计结果
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        
        response = {
            "total_questions": len(questions),
            "success_count": success_count,
            "error_count": error_count,
            "context_filter": request.context_filter,
            "results": results
        }
        
        logger.info(f"批量查询完成: {success_count}/{len(questions)} 成功")
        return JSONResponse(status_code=200, content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量查询失败: {str(e)}")

@router.post("/similar")
async def get_similar_content(request: SimilarContentRequest):
    """
    获取相似内容
    
    Args:
        request: 相似内容请求
        
    Returns:
        相似内容列表
    """
    try:
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="查询内容不能为空")
        
        if request.top_k < 1 or request.top_k > 20:
            raise HTTPException(status_code=400, detail="top_k必须在1-20之间")
        
        logger.info(f"获取相似内容: {query[:50]}...")
        
        # 获取相似内容
        similar_content = rag_engine.get_similar_content(query, request.top_k)
        
        response = {
            "query": query,
            "top_k": request.top_k,
            "total_results": len(similar_content),
            "similar_content": similar_content
        }
        
        logger.info(f"相似内容查询完成: 找到 {len(similar_content)} 个结果")
        return JSONResponse(status_code=200, content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取相似内容失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取相似内容失败: {str(e)}")

@router.get("/suggestions")
async def get_query_suggestions():
    """
    获取查询建议
    
    Returns:
        查询建议列表
    """
    try:
        suggestions = [
            {
                "category": "财务数据",
                "questions": [
                    "公司的营业收入是多少？",
                    "净利润增长率如何？",
                    "资产负债率是多少？",
                    "资产总额是多少？"
                ]
            },
            {
                "category": "业务分析",
                "questions": [
                    "主要业务板块有哪些？",
                    "市场份额如何？",
                    "竞争优势是什么？",
                    "风险因素有哪些？"
                ]
            },
            {
                "category": "发展趋势",
                "questions": [
                    "未来发展战略是什么？",
                    "投资计划有哪些？",
                    "预期增长率如何？",
                    "行业前景如何？"
                ]
            }
        ]
        
        return JSONResponse(status_code=200, content={
            "message": "查询建议",
            "suggestions": suggestions
        })
        
    except Exception as e:
        logger.error(f"获取查询建议失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取查询建议失败: {str(e)}")

@router.get("/history")
async def get_query_history():
    """
    获取查询历史（简化版本，实际应该从数据库获取）
    
    Returns:
        查询历史
    """
    try:
        # 这里是简化版本，实际应该从数据库或缓存中获取
        history = {
            "message": "查询历史功能暂未实现",
            "note": "在生产环境中，这里应该返回用户的查询历史记录",
            "recent_queries": []
        }
        
        return JSONResponse(status_code=200, content=history)
        
    except Exception as e:
        logger.error(f"获取查询历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取查询历史失败: {str(e)}")

@router.get("/stats")
async def get_query_stats():
    """
    获取查询统计信息
    
    Returns:
        查询统计
    """
    try:
        # 获取索引统计
        rag_engine = get_rag_engine()
        index_stats = rag_engine.get_index_stats()
        
        stats = {
            "index_status": index_stats,
            "query_capabilities": {
                "max_question_length": 1000,
                "max_batch_size": 10,
                "max_similar_results": 20,
                "supported_filters": ["company", "year", "document_type"]
            },
            "performance_info": {
                "average_response_time": "1-3秒",
                "supported_languages": ["中文", "英文"],
                "context_window": "4000 tokens"
            }
        }
        
        return JSONResponse(status_code=200, content=stats)
        
    except Exception as e:
        logger.error(f"获取查询统计失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取查询统计失败: {str(e)}")

@router.get("/index-documents")
async def list_index_documents():
    """
    列出索引中的所有文档及其元数据
    
    Returns:
        索引中的所有文档列表
    """
    try:
        rag_engine = get_rag_engine()
        
        if not rag_engine.query_engine:
            if not rag_engine.load_existing_index():
                raise HTTPException(
                    status_code=400,
                    detail="索引未构建，请先处理文档"
                )
        
        if not rag_engine.index:
            return JSONResponse(status_code=200, content={
                "message": "索引未初始化",
                "documents": [],
                "files": []
            })
        
        # 获取所有文档
        all_docs = rag_engine.index.docstore.docs
        
        # 统计文件
        files_dict = {}
        documents_list = []
        
        for doc_id, doc in all_docs.items():
            metadata = doc.metadata or {}
            filename = metadata.get('filename') or metadata.get('source_file', 'unknown')
            doc_type = metadata.get('document_type', 'text')
            
            # 添加到文档列表
            documents_list.append({
                "doc_id": doc_id,
                "filename": filename,
                "document_type": doc_type,
                "page_number": metadata.get('page_number'),
                "table_id": metadata.get('table_id'),
                "text_preview": doc.text[:200] if doc.text else "",
                "text_length": len(doc.text) if doc.text else 0,
                "metadata": metadata
            })
            
            # 统计文件
            if filename not in files_dict:
                files_dict[filename] = {
                    'count': 0,
                    'types': set(),
                    'sample_text': doc.text[:100] if doc.text else ''
                }
            files_dict[filename]['count'] += 1
            files_dict[filename]['types'].add(doc_type)
        
        # 转换为列表格式
        files_list = []
        for filename, info in sorted(files_dict.items()):
            files_list.append({
                "filename": filename,
                "document_count": info['count'],
                "document_types": list(info['types']),
                "sample_text": info['sample_text']
            })
        
        # 检查ChromaDB集合
        chroma_info = {}
        if rag_engine.chroma_collection:
            try:
                all_data = rag_engine.chroma_collection.get()
                if all_data and 'ids' in all_data:
                    chroma_info = {
                        "vector_count": len(all_data['ids']),
                        "metadata_count": len(all_data.get('metadatas', []))
                    }
                    
                    # 统计ChromaDB中的文件名
                    metadatas = all_data.get('metadatas', [])
                    chroma_files = {}
                    for metadata in metadatas:
                        if metadata:
                            filename = metadata.get('filename') or metadata.get('source_file', 'unknown')
                            if filename not in chroma_files:
                                chroma_files[filename] = 0
                            chroma_files[filename] += 1
                    
                    chroma_info["files"] = chroma_files
            except Exception as e:
                chroma_info = {"error": str(e)}
        
        return JSONResponse(status_code=200, content={
            "message": f"索引中共有 {len(all_docs)} 个文档",
            "total_documents": len(all_docs),
            "total_files": len(files_dict),
            "files": files_list,
            "documents": documents_list[:100],  # 限制返回前100个文档，避免响应过大
            "chroma_info": chroma_info
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"列出索引文档失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"列出索引文档失败: {str(e)}")

@router.post("/feedback")
async def submit_feedback(feedback_data: Dict[str, Any]):
    """
    提交查询反馈（简化版本）
    
    Args:
        feedback_data: 反馈数据
        
    Returns:
        反馈提交结果
    """
    try:
        # 这里是简化版本，实际应该保存到数据库
        logger.info(f"收到查询反馈: {feedback_data}")
        
        return JSONResponse(status_code=200, content={
            "message": "反馈提交成功",
            "note": "感谢您的反馈，我们会持续改进服务质量"
        })
        
    except Exception as e:
        logger.error(f"提交反馈失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")

class DupontAnalysisRequest(BaseModel):
    """杜邦分析请求"""
    company_name: Optional[str] = None  # 可选，如果不提供则从文档中提取
    year: Optional[str] = None  # 可选，如果不提供则从文档中提取
    filename: Optional[str] = None  # 选中的文件名，用于限制查询范围

@router.post("/dupont-analysis")
async def generate_dupont_analysis_api(request: DupontAnalysisRequest):
    """
    生成杜邦分析报告
    
    自动从文档中提取财务数据，生成完整的杜邦分析报告
    如果未提供公司名称和年份，将尝试从文档中自动提取
    
    Returns:
        杜邦分析结果，包含：
        - level1: ROE顶层分解
        - level2: ROA和权益乘数分解
        - level3: 底层财务数据
        - tree_structure: 树状结构
        - insights: AI分析洞察
    """
    try:
        logger.info("收到杜邦分析请求")
        
        # 获取RAG引擎
        rag_engine = get_rag_engine()
        
        if not rag_engine.query_engine:
            if not rag_engine.load_existing_index():
                raise HTTPException(
                    status_code=400,
                    detail="索引未构建，请先处理文档"
                )
        
        query_engine = rag_engine.query_engine
        
        # 提取公司名称和年份
        company_name = request.company_name
        year = request.year
        filename = request.filename
        
        # 构建上下文过滤器，限制查询范围到选中的文件
        context_filter = None
        if filename:
            context_filter = {"filename": filename}
            logger.info(f"限制查询范围到文件: {filename}")
        
        # 如果未提供，尝试从文档中提取
        if not company_name or not year:
            logger.info(f"尝试从文档中提取公司名称和年份... (文件: {filename or '全部'})")
            
            import re
            
            # 第一步：优先从文件名中提取公司名称和年份
            if filename:
                # 从文件名提取公司名称（更智能的匹配）
                # 匹配模式：公司名 + 报表类型 + 年份（可选）
                # 例如："平安银行利润表.xlsx" -> "平安银行"
                # 例如："平安银行2024年年报.pdf" -> "平安银行"
                if not company_name:
                    # 移除文件扩展名
                    name_without_ext = re.sub(r'\.[^.]+$', '', filename)
                    # 移除常见的报表类型关键词
                    name_clean = re.sub(r'(利润表|资产负债表|现金流量表|年报|报告|财务报表|财务报告)', '', name_without_ext, flags=re.IGNORECASE)
                    # 移除年份
                    name_clean = re.sub(r'\d{4}年?', '', name_clean)
                    # 移除多余的空格和特殊字符
                    name_clean = re.sub(r'[_\-\s]+', '', name_clean).strip()
                    if name_clean and len(name_clean) >= 2:
                        company_name = name_clean
                        logger.info(f"从文件名提取公司名称: {company_name}")
                
                # 从文件名提取年份（与上传 PDF 报告年对齐：优先“年报/报告”前的年份，否则取最后一个4位数）
                if not year:
                    # 优先：xxx2024年年报.pdf / xxx2024年报告.pdf → 2024
                    report_year_match = re.search(r'(\d{4})年?(?:报|年报|报告|度)?(?:\.|$)', filename)
                    if report_year_match:
                        year = report_year_match.group(1)
                        logger.info(f"从文件名提取报告年份（年报/报告）: {year}")
                    else:
                        all_years = re.findall(r'\d{4}', filename)
                        if all_years:
                            year = all_years[-1]  # 取最后一个4位数，通常对应报告年
                            logger.info(f"从文件名提取年份: {year}")
            
            # 第二步：如果还没有，从文档内容中提取
            if not company_name or not year:
                try:
                    # 从索引中检索该文件的文档
                    retriever = rag_engine.index.as_retriever(similarity_top_k=20)  # 增加检索数量
                    
                    # 如果指定了文件，先尝试从该文件提取；如果没有，从所有文件提取
                    if filename:
                        # 先尝试从指定文件提取
                        nodes = retriever.retrieve("公司名称 年份 报告年度")
                        matching_nodes = [
                            node for node in nodes 
                            if node.metadata.get('filename') == filename or 
                               node.metadata.get('source_file') == filename
                        ]
                        # 指定文件时只使用该文件的节点，避免混入其他文件年份导致洞察与 PDF 不一致
                        if not matching_nodes:
                            # 再试一次：仅用“报告年度/年份”检索，提高命中该文件的概率
                            nodes_year = retriever.retrieve("报告年度 报告年份 本报告 年度")
                            matching_nodes = [
                                n for n in nodes_year
                                if n.metadata.get('filename') == filename or n.metadata.get('source_file') == filename
                            ][:10]
                    else:
                        # 从所有文件提取
                        nodes = retriever.retrieve("公司名称 年份 报告年度")
                        matching_nodes = nodes[:10]
                    
                    if matching_nodes:
                        # 合并所有匹配节点的文本
                        all_text = "\n".join([node.text for node in matching_nodes[:10]])  # 增加文本量
                        
                        if not company_name:
                            # 从文本中提取公司名称（多种模式）
                            patterns = [
                                r'([^，,。\n]{2,30}(?:股份|有限|公司|集团|银行|证券|保险))',
                                r'公司名称[：:]\s*([^，,。\n]{2,30})',
                                r'([A-Za-z0-9\u4e00-\u9fa5]{2,20}(?:股份|有限|公司|集团))',
                            ]
                            for pattern in patterns:
                                company_match = re.search(pattern, all_text)
                                if company_match:
                                    candidate = company_match.group(1).strip()
                                    # 过滤掉明显不是公司名的内容
                                    if len(candidate) >= 2 and len(candidate) <= 30:
                                        company_name = candidate
                                        logger.info(f"从文档内容提取公司名称: {company_name}")
                                        break
                        
                        if not year:
                            # 从文本中提取年份：优先“报告年度/本报告”等明确的主报告年，避免选成对比年（如2023）
                            report_year_patterns = [
                                r'报告年度[：:]\s*(\d{4})',
                                r'本报告[期]?\s*[（(]?\s*(\d{4})\s*年',
                                r'(\d{4})年[度]?报告',
                                r'(\d{4})年度报告',
                            ]
                            for pattern in report_year_patterns:
                                m = re.search(pattern, all_text)
                                if m:
                                    candidate_year = m.group(1)
                                    if 2000 <= int(candidate_year) <= 2030:
                                        year = candidate_year
                                        logger.info(f"从文档内容提取报告年份（优先）: {year}")
                                        break
                            if not year:
                                year_patterns = [
                                    r'(\d{4})年度',
                                    r'(\d{4})年[度]?',
                                    r'截至(\d{4})年',
                                ]
                                from collections import Counter
                                for pattern in year_patterns:
                                    year_matches = re.findall(pattern, all_text)
                                    if year_matches:
                                        year_counts = Counter(year_matches)
                                        candidate_year = year_counts.most_common(1)[0][0]
                                        if 2000 <= int(candidate_year) <= 2030:
                                            year = candidate_year
                                            logger.info(f"从文档内容提取年份: {year} (出现 {year_counts[candidate_year]} 次)")
                                        break
                        
                        logger.info(f"从文档内容提取: {company_name or '未找到'} - {year or '未找到'}")
                except Exception as e:
                    logger.warning(f"从文档内容提取失败: {str(e)}")
            
            # 如果仍然没有，使用query_engine查询
            if not company_name or not year:
                extract_query = """
                请从文档中提取以下信息：
                1. 公司名称（完整的公司全称）
                2. 报告年份（如2023、2022等）
                
                请以JSON格式返回，格式：{"company_name": "公司名称", "year": "年份"}
                """
                
                try:
                    # 如果有context_filter，使用retriever限制范围
                    if context_filter and filename:
                        retriever = rag_engine.index.as_retriever(similarity_top_k=10)
                        nodes = retriever.retrieve(extract_query)
                        # 过滤出匹配的文件（检查filename和source_file）
                        matching_nodes = [
                            node for node in nodes 
                            if node.metadata.get('filename') == filename or 
                               node.metadata.get('source_file') == filename
                        ]
                        if matching_nodes:
                            response_text = "\n".join([node.text for node in matching_nodes[:3]])
                        else:
                            response_text = ""
                    else:
                        response = query_engine.query(extract_query)
                        response_text = str(response)
                    
                    # 尝试解析JSON
                    import json
                    import re
                    json_match = re.search(r'\{[^{}]*"company_name"[^{}]*"year"[^{}]*\}', response_text)
                    if json_match:
                        extracted_data = json.loads(json_match.group())
                        if not company_name:
                            company_name = extracted_data.get('company_name', '')
                        if not year:
                            year = extracted_data.get('year', '')
                    
                    # 如果JSON解析失败，尝试正则提取
                    if not company_name:
                        company_match = re.search(r'公司名称[：:]\s*([^\n，,。]+)', response_text)
                        if company_match:
                            company_name = company_match.group(1).strip()
                    
                    if not year:
                        year_match = re.search(r'(\d{4})年', response_text)
                        if year_match:
                            year = year_match.group(1)
                        else:
                            # 尝试从文档元数据中获取
                            year_match = re.search(r'(\d{4})', response_text)
                            if year_match:
                                year = year_match.group(1)
                
                except Exception as e:
                    logger.warning(f"从文档提取公司信息失败: {str(e)}")
        
        # 如果仍然没有，使用默认值
        if not company_name:
            company_name = "未知公司"
            logger.warning("未找到公司名称，使用默认值")
        
        year_from_document = bool(year)
        if not year:
            from datetime import datetime
            year = str(datetime.now().year - 1)
            if filename:
                logger.warning(
                    f"指定文件 {filename} 中未识别到报告年份，已使用默认年份 {year}，"
                    "洞察可能与 PDF 报告年份不一致，请核对文档或确保文件名/内容包含年份"
                )
            else:
                logger.warning(f"未找到年份，使用默认值: {year}")
        
        logger.info(f"开始生成杜邦分析: {company_name} - {year} (年份来自文档: {year_from_document})")
        
        # 注意：不再在这里预先提取数据，让 generate_dupont_analysis 内部的 extract_financial_data_for_dupont 
        # 使用结构化LLM输出方法提取数据，这样更准确（和 quick-overview 使用相同的方法）
        # 如果指定了文件，传递给 generate_dupont_analysis，让它内部限制查询范围
        
        # 调用杜邦分析函数（现在是async）
        # generate_dupont_analysis 内部会调用 extract_financial_data_for_dupont
        # 该方法使用结构化LLM输出（as_structured_llm），比正则表达式提取更准确
        # 和 quick-overview 使用相同的数据提取方法
        dupont_result = await generate_dupont_analysis(
            company_name=company_name,
            year=year,
            query_engine=query_engine,
            financial_data=None,  # 让函数内部使用结构化LLM方法提取，更准确
            filename=filename  # 传递文件名，用于限制查询范围
        )
        
        logger.info(f"✅ 杜邦分析生成成功")
        
        # 将Decimal类型转换为float，确保JSON可序列化
        def convert_decimal_to_float(obj):
            """递归地将Decimal转换为float"""
            from decimal import Decimal
            from datetime import datetime
            if isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, dict):
                return {k: convert_decimal_to_float(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_decimal_to_float(item) for item in obj]
            elif isinstance(obj, datetime):
                return obj.isoformat()
            else:
                return obj
        
        # 转换结果
        serializable_result = convert_decimal_to_float(dupont_result)

        # 读取结构化指标JSON：按年分读（2024 一个 json、2023 一个 json），与上传 PDF 年份对齐
        metrics_json = None
        metrics_by_year = {}
        try:
            import json
            import re
            from pathlib import Path

            safe_company = re.sub(r'[^\w\u4e00-\u9fff\-]+', '_', company_name or 'unknown')
            safe_year = re.sub(r'[^\d]+', '', str(year or ''))
            storage_dir = Path("storage")
            if storage_dir.exists():
                # 主分析年单文件（兼容前端）
                metrics_path = storage_dir / f"dupont_metrics_{safe_company}_{safe_year or 'unknown'}.json"
                if metrics_path.exists():
                    with open(metrics_path, "r", encoding="utf-8") as f:
                        metrics_json = json.load(f)
                # 按年分读所有该公司的 json
                prefix = f"dupont_metrics_{safe_company}_"
                for p in storage_dir.glob(prefix + "*.json"):
                    try:
                        stem = p.stem
                        y = stem.replace(prefix, "").strip()
                        if y.isdigit() and 2000 <= int(y) <= 2030:
                            with open(p, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            metrics_by_year[y] = data.get("metrics", data) if isinstance(data, dict) else data
                    except Exception as e:
                        logger.warning(f"读取按年杜邦JSON失败 {p}: {e}")
        except Exception as e:
            logger.warning(f"读取结构化指标JSON失败: {str(e)}")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "company_name": company_name,
                "year": year,
                "year_from_document": year_from_document,  # True=从文档/文件名识别，False=使用默认年
                "analysis": serializable_result,
                "metrics": metrics_json,
                "metrics_by_year": metrics_by_year if metrics_by_year else None,
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成杜邦分析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"生成杜邦分析失败: {str(e)}"
        )

@router.post("/quick-overview")
async def get_quick_overview(request: Optional[QuickOverviewRequest] = None):
    """
    快速生成财务概况接口（结构化财务快照）
    
    两阶段生成：
    1. 第一阶段：提取关键财务指标（ROE、营收、净利润、资产总额、净息差、成本收入比等）
    2. 第二阶段：基于指标生成一句话结论
    
    请求体可传 {"filename": "xxx.xlsx"}，只从该文件检索（先 Excel 表格再 PDF）。
    
    Returns:
        财务快照数据，包含关键指标、verdict、stage、profit_quality、risk_level
    """
    try:
        from llama_index.core.llms import ChatMessage
        from llama_index.core import Settings
        import re
        
        logger.info("开始生成财务快照（两阶段生成）...")
        
        # 获取RAG引擎
        rag_engine = get_rag_engine()
        
        if not rag_engine.query_engine:
            if not rag_engine.load_existing_index():
                raise HTTPException(
                    status_code=400,
                    detail="索引未构建，请先处理文档"
                )
        
        llm = Settings.llm
        
        # ========== 第零阶段：从上传的文档中提取公司名称和年份（若请求指定 filename 则优先只检索该文件）==========
        logger.info("第零阶段：从上传的文档中提取公司名称和年份...")
        
        company_name = None
        year = None
        context_filter = {}
        uploaded_filenames = set()  # 保存上传的文件名列表，用于更严格的过滤
        
        # 财务概况检索：使用所有已上传并处理过的表格/文件，不按选中文件限定，以便命中年度指标、资产负债表等
        if request and getattr(request, 'filename', None):
            logger.info(f"📋 当前选中文件: {request.filename}（检索范围：所有已处理文件）")
        
        try:
            # 方法1：直接从uploads目录的文件名中提取公司名称（最准确）
            from pathlib import Path
            upload_dir = Path("uploads")
            
            if upload_dir.exists():
                seen_companies = set()
                seen_years = set()
                # 遍历所有上传的文件
                for file_path in upload_dir.iterdir():
                    if file_path.is_file():
                        filename = file_path.name
                        uploaded_filenames.add(filename)  # 保存文件名
                        # 移除文件扩展名
                        name_without_ext = re.sub(r'\.[^.]+$', '', filename)
                        # 移除常见的报表类型关键词
                        name_clean = re.sub(r'(利润表|资产负债表|现金流量表|年报|报告|财务报表|财务报告)', '', name_without_ext, flags=re.IGNORECASE)
                        
                        # 从文件名提取年份（在移除年份之前）
                        if not year:
                            year_match = re.search(r'(\d{4})', filename)
                            if year_match:
                                candidate_year = year_match.group(1)
                                # 验证年份合理性
                                if 2000 <= int(candidate_year) <= 2030:
                                    year = candidate_year
                                    seen_years.add(year)
                                    logger.info(f"  从文件 '{filename}' 提取到年份: {year}")
                        
                        # 移除年份（4位数字）
                        name_clean = re.sub(r'\d{4}年?', '', name_clean)
                        # 移除"年度"和后面的数字（如"年度60"）
                        name_clean = re.sub(r'年度\d+', '', name_clean)
                        # 移除多余的空格和特殊字符
                        name_clean = re.sub(r'[_\-\s\.]+', '', name_clean).strip()
                        
                        if name_clean and len(name_clean) >= 2 and len(name_clean) <= 30:
                            seen_companies.add(name_clean)
                            logger.info(f"  从文件 '{filename}' 提取到公司名: {name_clean}")
                
                # 如果找到多个可能的公司名，选择最常见的
                if seen_companies:
                    from collections import Counter
                    company_counts = Counter(seen_companies)
                    # 选择出现次数最多的
                    company_name = company_counts.most_common(1)[0][0]
                    logger.info(f"✅ 从上传文件提取公司名称: {company_name} (出现 {company_counts[company_name]} 次)")
                    logger.info(f"✅ 上传的文件列表: {list(uploaded_filenames)}")
            
                # 如果找到多个年份，选择最常见的（通常应该只有一个）
                if seen_years:
                    from collections import Counter
                    year_counts = Counter(seen_years)
                    year = year_counts.most_common(1)[0][0]
                    logger.info(f"✅ 从上传文件提取年份: {year} (出现 {year_counts[year]} 次)")
            
            # 方法2：如果还没找到年份，从文档内容中提取
            if not year:
                try:
                    if upload_dir.exists():
                        uploaded_files = [f.name for f in upload_dir.iterdir() if f.is_file()]
                        if uploaded_files:
                            # 尝试从文档内容中提取年份
                            year_query = "报告年度 年份 年度报告 报告年份"
                            try:
                                retriever = rag_engine.index.as_retriever(similarity_top_k=20)
                                nodes = retriever.retrieve(year_query)
                                
                                # 只从当前上传的文件中提取
                                for node in nodes:
                                    filename = node.metadata.get('filename') or node.metadata.get('source_file', '')
                                    if filename in uploaded_filenames:
                                        # 从文本中提取年份
                                        node_text = node.text
                                        year_patterns = [
                                            r'报告年度[：:]\s*(\d{4})',
                                            r'(\d{4})年度',
                                            r'(\d{4})年[度]?报告',
                                        ]
                                        for pattern in year_patterns:
                                            year_match = re.search(pattern, node_text)
                                            if year_match:
                                                candidate_year = year_match.group(1)
                                                # 验证年份合理性
                                                if 2000 <= int(candidate_year) <= 2030:
                                                    year = candidate_year
                                                    logger.info(f"✅ 从文档内容提取年份: {year}")
                                                    break
                                        if year:
                                            break
                            except Exception as e:
                                logger.warning(f"从文档内容提取年份失败: {str(e)}")
                except Exception as e:
                    logger.warning(f"提取年份失败: {str(e)}")
            
            # 方法3：如果还没找到，从索引中的文档元数据中提取（只从当前上传的文件）
            if not company_name and rag_engine.index:
                try:
                    # 获取所有上传的文件名
                    uploaded_filenames = set()
                    if upload_dir.exists():
                        uploaded_filenames = {f.name for f in upload_dir.iterdir() if f.is_file()}
                    
                    if uploaded_filenames:
                        retriever = rag_engine.index.as_retriever(similarity_top_k=50)
                        nodes = retriever.retrieve("公司名称")
                        
                        # 只从当前上传的文件中提取
                        seen_companies = set()
                        for node in nodes:
                            filename = node.metadata.get('filename') or node.metadata.get('source_file', '')
                            # 只处理当前上传的文件
                            if filename in uploaded_filenames:
                                # 移除文件扩展名
                                name_without_ext = re.sub(r'\.[^.]+$', '', filename)
                                # 移除常见的报表类型关键词
                                name_clean = re.sub(r'(利润表|资产负债表|现金流量表|年报|报告|财务报表|财务报告)', '', name_without_ext, flags=re.IGNORECASE)
                                # 移除年份
                                name_clean = re.sub(r'\d{4}年?', '', name_clean)
                                # 移除"年度"和后面的数字
                                name_clean = re.sub(r'年度\d+', '', name_clean)
                                # 移除多余的空格和特殊字符
                                name_clean = re.sub(r'[_\-\s\.]+', '', name_clean).strip()
                                if name_clean and len(name_clean) >= 2 and len(name_clean) <= 30:
                                    seen_companies.add(name_clean)
                        
                        if seen_companies:
                            from collections import Counter
                            company_counts = Counter(seen_companies)
                            company_name = company_counts.most_common(1)[0][0]
                            logger.info(f"✅ 从索引元数据提取公司名称: {company_name}")
                except Exception as e:
                    logger.warning(f"从索引元数据提取公司名称失败: {str(e)}")
            
            # 方法3：如果还没找到，从文档内容中提取（但限制在当前上传的文件）
            if not company_name:
                try:
                    # 如果有上传的文件，使用文件名作为上下文
                    if upload_dir.exists():
                        uploaded_files = [f.name for f in upload_dir.iterdir() if f.is_file()]
                        if uploaded_files:
                            files_context = "、".join(uploaded_files[:5])  # 最多5个文件名
                            extract_query = f"请从以下文件名的文档中提取公司名称（完整的公司全称）：{files_context}。只返回公司名称，不要其他内容。"
                        else:
                            extract_query = "请从文档中提取公司名称（完整的公司全称），只返回公司名称，不要其他内容"
                    else:
                        extract_query = "请从文档中提取公司名称（完整的公司全称），只返回公司名称，不要其他内容"
                    
                    response = rag_engine.query_engine.query(extract_query)
                    response_text = str(response).strip()
                    
                    # 尝试提取公司名称
                    patterns = [
                        r'([^，,。\n]{2,30}(?:股份|有限|公司|集团|银行|证券|保险))',
                        r'公司名称[：:]\s*([^，,。\n]{2,30})',
                        r'([A-Za-z0-9\u4e00-\u9fa5]{2,20}(?:股份|有限|公司|集团))',
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, response_text)
                        if match:
                            candidate = match.group(1).strip()
                            # 移除"年度"和后面的数字
                            candidate = re.sub(r'年度\d+', '', candidate).strip()
                            if len(candidate) >= 2 and len(candidate) <= 30:
                                company_name = candidate
                                logger.info(f"✅ 从文档内容提取公司名称: {company_name}")
                                break
                except Exception as e:
                    logger.warning(f"从文档内容提取公司名称失败: {str(e)}")
            
            # 财务概况检索：只按年份过滤，不按公司名/文件名，以命中所有已上传并处理的表格（年度指标、资产负债表、利润表等）
            if company_name:
                logger.info(f"✅ 识别到公司: {company_name}（检索不按公司名过滤）")
            if year:
                context_filter['year'] = year
                logger.info(f"✅ 设置年份过滤条件: {year}，检索该年度所有已处理文件")
                if uploaded_filenames:
                    logger.info(f"✅ 上传的文件数量: {len(uploaded_filenames)}")
            else:
                logger.warning("⚠️ 未找到公司名称，将检索所有文档")
                # 不按单文件限定，检索所有已上传并处理的表格文件
            
        except Exception as e:
            logger.warning(f"提取公司名称失败: {str(e)}，将检索所有文档")
            import traceback
            logger.warning(f"详细错误: {traceback.format_exc()}")
        
        # 记录使用的过滤条件
        if context_filter:
            logger.info(f"📋 检索过滤条件: {context_filter}")
        
        # ========== 第一阶段：快速提取关键财务指标（优先从Excel表格）==========
        logger.info("第一阶段：快速提取关键财务指标（优先从Excel表格）...")
        
        snapshot_dict = {
            "roe": None,
            "revenue": None,
            "net_profit": None,
            "total_assets": None,
            "net_interest_margin": None,
            "cost_income_ratio": None,
            "npl_ratio": None,
            "provision_coverage_ratio": None,
            "capital_adequacy_ratio": None
        }
        
        import re
        
        # 优化：先使用RAG检索所有文档（PDF和Excel）的表格数据，然后使用结构化输出提取
        try:
            # 使用HybridRetriever检索（与普通查询相同的方法）
            logger.info("🔍 使用HybridRetriever检索财务数据（与普通查询相同的方法）...")
            
            # 检查HybridRetriever是否可用
            use_hybrid = (rag_engine.use_hybrid_retriever and 
                         rag_engine.hybrid_retriever and 
                         rag_engine.hybrid_retriever.text_index and 
                         rag_engine.hybrid_retriever.table_index)
            
            if use_hybrid:
                logger.info("✅ 使用HybridRetriever进行混合检索（多指标分别检索）")
                
                # 定义9个关键指标及其查询关键词（含总资产、不良率、拨备覆盖率、资本充足率，便于命中“年度指标”等汇总表）
                indicators = {
                    "roe": ["加权平均净资产收益率", "ROE", "净资产收益率"],
                    "revenue": ["营业收入", "营业总收入", "收入"],
                    "net_profit": ["净利润", "归属于母公司所有者的净利润", "归属于本行股东的净利润"],
                    "total_assets": ["资产总额", "总资产", "资产合计", "资产总计"],
                    "net_interest_margin": ["净息差"],
                    "cost_income_ratio": ["成本收入比"],
                    "npl_ratio": ["不良率", "不良贷款率", "不良贷款比例"],
                    "provision_coverage_ratio": ["拨备覆盖率", "贷款拨备覆盖率"],
                    "capital_adequacy_ratio": ["资本充足率", "资本充足率指标"]
                }
                
                # 为每个指标单独检索，确保都能找到
                all_hybrid_results = []
                all_table_results = []
                found_indicators = set()
                
                year_prefix = f"{year}年 " if year else ""
                company_prefix = f"{company_name} " if company_name else ""
                
                for indicator_key, keywords in indicators.items():
                    # 为每个指标构建查询
                    query_keywords = " ".join(keywords)
                    if year and company_name:
                        query_text = f"{company_prefix}{year_prefix}{query_keywords} {year}年度数值"
                    elif year:
                        query_text = f"{year_prefix}{query_keywords} {year}年度数值"
                    elif company_name:
                        query_text = f"{company_prefix}{query_keywords} 最新年度数值"
                    else:
                        query_text = f"{query_keywords} 最新年度数值"
                    
                    logger.info(f"  🔍 检索指标: {indicator_key} ({keywords[0]})")
                    indicator_results = rag_engine.hybrid_retriever.retrieve(
                        query_text,
                        top_k=30,  # 每个指标检索30个结果
                        strategy='table_first',  # 先检索表格再检索 PDF
                        context_filter=context_filter if context_filter else None
                    )
                    
                    if indicator_results:
                        logger.info(f"    ✅ {indicator_key} 检索到 {len(indicator_results)} 个结果")
                        all_hybrid_results.extend(indicator_results)
                        
                        # 检查是否包含表格数据
                        for r in indicator_results:
                            doc = r.get('document')
                            if not doc:
                                continue
                            # 检查metadata
                            is_table = (
                                'table' in str(doc.metadata).lower() or 
                                doc.metadata.get('document_type') == 'table_data' or
                                doc.metadata.get('is_financial', False)
                            )
                            # 检查文本内容
                            text_preview = str(doc.text)[:500] if hasattr(doc, 'text') else ''
                            is_table_by_text = (
                                any(kw in text_preview for kw in keywords) or
                                '资产负债表' in text_preview or
                                '利润表' in text_preview or
                                '|' in text_preview or
                                ('项 目' in text_preview and (year in text_preview if year else True))
                            )
                            if is_table or is_table_by_text:
                                all_table_results.append(r)
                                found_indicators.add(indicator_key)
                    else:
                        logger.warning(f"    ⚠️ {indicator_key} 未检索到结果")
                
                # 额外检索一次「年度指标/主要指标」类汇总表，提高命中“平安银行2024年度指标”等表格的概率
                summary_query = f"{company_prefix}{year_prefix}年度指标 主要指标 总资产 不良率 拨备覆盖率 资本充足率".strip()
                if summary_query:
                    logger.info(f"  🔍 检索汇总表: 年度指标/主要指标")
                    summary_results = rag_engine.hybrid_retriever.retrieve(
                        summary_query,
                        top_k=15,
                        strategy='table_first',
                        context_filter=context_filter if context_filter else None
                    )
                    if summary_results:
                        all_hybrid_results.extend(summary_results)
                
                # 去重（基于文档ID或文本内容）
                seen_docs = set()
                unique_hybrid_results = []
                unique_table_results = []
                
                # 去重时区分同一文件内的不同表格/片段，避免只保留 1 条 per 文件导致年度指标表被合并掉
                def _doc_id(doc):
                    meta = doc.metadata
                    tid = meta.get('table_id') or meta.get('source')
                    if tid:
                        return str(tid)
                    return (meta.get('filename') or meta.get('source_file') or '') + '|' + (str(doc.text)[:120].replace('\n', ' '))
                for r in all_hybrid_results:
                    doc = r.get('document')
                    if not doc:
                        continue
                    doc_id = _doc_id(doc)
                    if doc_id not in seen_docs:
                        seen_docs.add(doc_id)
                        unique_hybrid_results.append(r)
                
                seen_table_ids = set()
                for r in all_table_results:
                    doc = r.get('document')
                    if not doc:
                        continue
                    doc_id = _doc_id(doc)
                    if doc_id not in seen_table_ids:
                        seen_table_ids.add(doc_id)
                        unique_table_results.append(r)
                
                logger.info(f"✅ 去重后共检索到 {len(unique_hybrid_results)} 个结果，其中 {len(unique_table_results)} 个是表格数据")
                logger.info(f"✅ 找到的指标: {', '.join(found_indicators) if found_indicators else '无'}")
                
                # 优先使用表格数据，若不足则用全部检索结果拼上下文，确保总资产等不因只取前20条而被截掉
                if unique_table_results:
                    logger.info(f"  ✅ 优先使用 {len(unique_table_results)} 个表格数据")
                    table_text = "\n\n".join([r['document'].text for r in unique_table_results[:25]])
                    # 若表格条数多或可能缺总资产等，再拼上非表格结果，避免总资产在后面的表里被截断
                    non_table_results = [r for r in unique_hybrid_results if r not in unique_table_results]
                    if non_table_results:
                        table_text += "\n\n" + "\n\n".join([r['document'].text for r in non_table_results[:20]])
                    all_context_text = table_text
                    
                    # 检查是否包含所有指标
                    missing_indicators = []
                    for indicator_key, keywords in indicators.items():
                        if not any(kw in all_context_text for kw in keywords):
                            missing_indicators.append(indicator_key)
                    
                    if missing_indicators:
                        logger.warning(f"  ⚠️ 表格数据中缺少以下指标: {', '.join(missing_indicators)}")
                    else:
                        logger.info(f"  ✅ 表格数据中包含所有指标")
                else:
                    logger.info(f"  ⚠️ 未识别出表格数据，使用所有结果")
                    all_context_text = "\n\n".join([r['document'].text for r in unique_hybrid_results[:35]])
                
                logger.info(f"✅ 构建上下文，长度: {len(all_context_text)}字符")
                
                # 最终检查所有指标
                final_missing = []
                for indicator_key, keywords in indicators.items():
                    if not any(kw in all_context_text for kw in keywords):
                        final_missing.append(indicator_key)
                
                if final_missing:
                    logger.warning(f"  ⚠️ 最终上下文中仍缺少以下指标: {', '.join(final_missing)}")
                    # 若当前限定在单文件（如利润表）且缺少总资产等，这些指标在「年度指标」或「资产负债表」里，补充检索不按 filename 只按 company+year
                    if context_filter and context_filter.get('filename') and use_hybrid:
                        need_total_assets = 'total_assets' in final_missing
                        need_others = any(k in final_missing for k in ['npl_ratio', 'provision_coverage_ratio', 'capital_adequacy_ratio'])
                        if need_total_assets or need_others:
                            # 只按年份过滤，避免公司名（如「平安银行主营业务表」）把「年度指标.xlsx」等表误过滤
                            supplement_filter = {'year': year} if year else None
                            year_prefix = f"{year}年 " if year else ""
                            company_prefix = f"{company_name} " if company_name else ""
                            sup_query = f"{company_prefix}{year_prefix}年度指标 总资产 资产总额 不良率 拨备覆盖率 资本充足率 {year or ''}年度数值".strip()
                            logger.info(f"  🔍 补充检索（不限定文件名，命中年度指标/资产负债表）: {sup_query[:60]}...")
                            try:
                                sup_results = rag_engine.hybrid_retriever.retrieve(
                                    sup_query,
                                    top_k=20,
                                    strategy='table_first',
                                    context_filter=supplement_filter
                                )
                                if sup_results:
                                    sup_text = "\n\n".join([r['document'].text for r in sup_results[:15]])
                                    all_context_text = all_context_text + "\n\n【以下来自年度指标/资产负债表等】\n\n" + sup_text
                                    logger.info(f"  ✅ 补充上下文 {len(sup_text)} 字符，用于提取总资产等")
                            except Exception as e:
                                logger.warning(f"  补充检索失败: {e}")
                else:
                    logger.info(f"  ✅ 最终上下文中包含所有指标")
                
                if not all_context_text:
                    logger.warning("⚠️ HybridRetriever未找到结果，使用query_engine")
                    use_hybrid = False
            
            if not use_hybrid:
                # 回退到使用query_engine查询（与普通查询相同）
                logger.info("🔍 使用query_engine查询财务数据...")
                
                # 使用多个查询，每个查询一个指标（这样更准确）
                # 如果有公司名称和年份，在查询中加入公司名称和年份限制
                if company_name and year:
                    queries = [
                        f"{company_name}{year}年的加权平均净资产收益率（ROE）是多少？请给出{year}年度的加权平均净资产收益率百分比",
                        f"{company_name}{year}年的营业收入是多少？请给出{year}年度的营业收入数值，包括单位（元、万元或亿元）",
                        f"{company_name}{year}年的净利润是多少？请给出{year}年度的归属于母公司所有者的净利润数值，包括单位",
                        f"{company_name}{year}年的资产总额是多少？请给出{year}年度的资产总额数值，包括单位（元、万元或亿元）",
                        f"{company_name}{year}年的净息差是多少？请给出{year}年度的净息差百分比",
                        f"{company_name}{year}年的成本收入比是多少？请给出{year}年度的成本收入比百分比"
                    ]
                elif company_name:
                    queries = [
                        f"{company_name}的加权平均净资产收益率（ROE）是多少？请给出最新年度的加权平均净资产收益率百分比",
                        f"{company_name}的营业收入是多少？请给出最新年度的营业收入数值，包括单位（元、万元或亿元）",
                        f"{company_name}的净利润是多少？请给出最新年度的归属于母公司所有者的净利润数值，包括单位",
                        f"{company_name}的资产总额是多少？请给出最新年度的资产总额数值，包括单位（元、万元或亿元）",
                        f"{company_name}的净息差是多少？请给出最新年度的净息差百分比",
                        f"{company_name}的成本收入比是多少？请给出最新年度的成本收入比百分比"
                    ]
                elif year:
                    queries = [
                        f"{year}年的加权平均净资产收益率（ROE）是多少？请给出{year}年度的加权平均净资产收益率百分比",
                        f"{year}年的营业收入是多少？请给出{year}年度的营业收入数值，包括单位（元、万元或亿元）",
                        f"{year}年的净利润是多少？请给出{year}年度的归属于母公司所有者的净利润数值，包括单位",
                        f"{year}年的资产总额是多少？请给出{year}年度的资产总额数值，包括单位（元、万元或亿元）",
                        f"{year}年的净息差是多少？请给出{year}年度的净息差百分比",
                        f"{year}年的成本收入比是多少？请给出{year}年度的成本收入比百分比"
                    ]
                else:
                    queries = [
                        "加权平均净资产收益率（ROE）是多少？请给出最新年度的加权平均净资产收益率百分比",
                        "营业收入是多少？请给出最新年度的营业收入数值，包括单位（元、万元或亿元）",
                        "净利润是多少？请给出最新年度的归属于母公司所有者的净利润数值，包括单位",
                        "资产总额是多少？请给出最新年度的资产总额数值，包括单位（元、万元或亿元）",
                        "净息差是多少？请给出最新年度的净息差百分比",
                        "成本收入比是多少？请给出最新年度的成本收入比百分比"
                    ]
                
                all_context_parts = []
                for query in queries:
                    try:
                        # 如果有context_filter，使用rag_engine.query方法（它会应用过滤）
                        if context_filter:
                            result = rag_engine.query(query, context_filter)
                            response_text = result.get('answer', '')
                        else:
                            response = rag_engine.query_engine.query(query)
                            response_text = str(response).strip()
                        
                        if response_text and len(response_text) > 20:
                            all_context_parts.append(response_text)
                            logger.info(f"  ✅ 查询成功: {query[:30]}...")
                    except Exception as e:
                        logger.warning(f"查询失败: {query[:30]}... - {str(e)}")
                
                # 合并所有查询结果
                all_context_text = "\n\n".join(all_context_parts) if all_context_parts else ""
                
                if not all_context_text:
                    # 如果还是没数据，使用一个综合查询
                    logger.info("🔄 使用综合查询...")
                    try:
                        if company_name and year:
                            comprehensive_query = f"请从{company_name}{year}年的文档中提取以下财务指标的具体数值：1.{year}年加权平均净资产收益率（ROE） 2.{year}年营业收入 3.{year}年净利润 4.{year}年资产总额 5.{year}年净息差 6.{year}年成本收入比。请给出{year}年度的数值和单位。"
                        elif company_name:
                            comprehensive_query = f"请从{company_name}的文档中提取以下财务指标的具体数值：1.加权平均净资产收益率（ROE） 2.营业收入 3.净利润 4.资产总额 5.净息差 6.成本收入比。请给出最新年度的数值和单位。"
                        elif year:
                            comprehensive_query = f"请从{year}年的文档中提取以下财务指标的具体数值：1.{year}年加权平均净资产收益率（ROE） 2.{year}年营业收入 3.{year}年净利润 4.{year}年资产总额 5.{year}年净息差 6.{year}年成本收入比。请给出{year}年度的数值和单位。"
                        else:
                            comprehensive_query = "请从所有文档中提取以下财务指标的具体数值：1.加权平均净资产收益率（ROE） 2.营业收入 3.净利润 4.资产总额 5.净息差 6.成本收入比。请给出最新年度的数值和单位。"
                        
                        # 如果有context_filter，使用rag_engine.query方法
                        if context_filter:
                            result = rag_engine.query(comprehensive_query, context_filter)
                            all_context_text = result.get('answer', '')
                        else:
                            response = rag_engine.query_engine.query(comprehensive_query)
                            all_context_text = str(response).strip()
                        logger.info(f"  ✅ 综合查询成功，长度: {len(all_context_text)}字符")
                    except Exception as e:
                        logger.warning(f"综合查询也失败: {str(e)}")
                        all_context_text = ""
            
            # 如果上下文太短，尝试直接检索表格数据（包括PDF和Excel）
            if len(all_context_text) < 500:
                logger.info("⚠️ 上下文太短，尝试直接检索表格数据（PDF和Excel）...")
                try:
                    retriever = rag_engine.index.as_retriever(similarity_top_k=50)
                    # 构建查询，明确包含资产总额
                    table_query = f"{year}年 资产负债表 资产总额 总资产 资产合计 加权平均净资产收益率 ROE 营业收入 净利润 净息差 成本收入比 {year}年度数值" if year else "资产负债表 资产总额 总资产 资产合计 加权平均净资产收益率 ROE 营业收入 净利润 净息差 成本收入比 最新年度数值"
                    nodes = retriever.retrieve(table_query)
                    
                    # 应用公司过滤
                    if context_filter and 'company' in context_filter:
                        nodes = rag_engine._filter_nodes(nodes, context_filter)
                        logger.info(f"  ✅ 应用公司过滤后，剩余 {len(nodes)} 个节点")
                    
                    # 手动过滤表格数据（包括PDF和Excel表格）
                    table_nodes = [n for n in nodes if (
                        n.metadata.get('document_type') == 'table_data' or 
                        n.metadata.get('is_financial', False) or
                        'table' in str(n.metadata).lower() or
                        '资产负债表' in str(n.text)[:200] or  # 检查文本内容
                        '资产总额' in str(n.text)[:200] or
                        '总资产' in str(n.text)[:200]
                    )]
                    
                    if table_nodes:
                        table_text = "\n\n".join([node.text for node in table_nodes[:15]])  # 增加数量
                        if len(table_text) > len(all_context_text):
                            all_context_text = table_text
                            logger.info(f"  ✅ 从表格数据获取到 {len(table_text)} 字符的上下文")
                            # 检查是否包含资产总额
                            if '资产总额' in table_text or '总资产' in table_text or '资产合计' in table_text:
                                logger.info(f"  ✅ 表格数据中包含资产总额相关信息")
                            else:
                                logger.warning(f"  ⚠️ 表格数据中未找到资产总额相关信息")
                    else:
                        logger.warning(f"  ⚠️ 未找到表格数据节点")
                except Exception as e:
                    logger.warning(f"检索表格数据失败: {str(e)}")
            
            # ========== 趋势数据三步：1.当前年份=上传文件/文档年份 2.先检索「{year}年同比」 3.检索不到再当年+上年公式计算 ==========
            retrieved_trends = {}  # indicator_key -> (change_rate, change_direction)
            if year and year.isdigit():
                logger.info(f"📅 步骤1：当前年份（来自上传文件/文档）: {year}年")
                try:
                    trend_query = f"{year}年同比 本年同比增减 同比增减 营业收入 净利润 资产总额 ROE 净息差 成本收入比"
                    if use_hybrid and rag_engine.hybrid_retriever:
                        trend_results = rag_engine.hybrid_retriever.retrieve(
                            trend_query, top_k=25, strategy='table_first',
                            context_filter=context_filter if context_filter else None
                        )
                    else:
                        retriever = rag_engine.index.as_retriever(similarity_top_k=25)
                        nodes = retriever.retrieve(trend_query)
                        trend_results = [{'document': n} for n in nodes]
                    if trend_results:
                        trend_context = "\n\n".join([r['document'].text for r in trend_results[:20]])
                        trend_names = [
                            ("revenue", ["营业收入", "营业总收入"]),
                            ("net_profit", ["净利润", "归属于母公司所有者的净利润", "归属于本行股东的净利润"]),
                            ("total_assets", ["资产总额", "总资产", "资产合计"]),
                            ("roe", ["加权平均净资产收益率", "ROE", "净资产收益率"]),
                            ("net_interest_margin", ["净息差"]),
                            ("cost_income_ratio", ["成本收入比"]),
                            ("npl_ratio", ["不良率", "不良贷款率"]),
                        ]
                        # 不良率/拨备覆盖率/资本充足率：表格中同比列多为「X个百分点」，同行中的 % 常为指标值(如1.06%、250%)，不能当同比
                        value_like_pct_keys = ("npl_ratio",)  # 不良率约 0.5%~5%，仅接受「个百分点」为同比
                        for key, names in trend_names:
                            if key in retrieved_trends:
                                continue
                            for line in trend_context.replace('\r', '\n').split('\n'):
                                if not any(n in line for n in names):
                                    continue
                                # 优先匹配「X个百分点」（同比列常见写法）
                                m_pt = re.search(r'([+\-]?\d+\.?\d*)\s*个百分点', line)
                                if m_pt:
                                    try:
                                        num = float(m_pt.group(1).strip())
                                        change_rate = f"{num:+.2f}个百分点"
                                        change_direction = '下降' if num < 0 else ('增长' if num > 0 else '持平')
                                        retrieved_trends[key] = (change_rate, change_direction)
                                        logger.info(f"  📈 步骤2 检索到{year}年同比: {key} -> {change_rate}")
                                        break
                                    except ValueError:
                                        pass
                                if key in retrieved_trends:
                                    continue
                                m_pct = re.search(r'[(\（]?([+\-]?\d+\.?\d*)\s*%[)\）]?', line)
                                if m_pct:
                                    g = m_pct.group(1)
                                    if g:
                                        try:
                                            num = float(g.strip())
                                            # 不良率：同行 % 多为指标值(1.06%等)，不作为同比，避免误用
                                            if key in value_like_pct_keys and 0.3 <= abs(num) <= 6:
                                                continue
                                            change_rate = f"{num:+.1f}%"
                                            change_direction = '下降' if num < 0 else ('增长' if num > 0 else '持平')
                                            retrieved_trends[key] = (change_rate, change_direction)
                                            logger.info(f"  📈 步骤2 检索到{year}年同比: {key} -> {change_rate}")
                                            break
                                        except ValueError:
                                            pass
                        if retrieved_trends:
                            logger.info(f"✅ 步骤2：共检索到 {len(retrieved_trends)} 个指标的{year}年同比")
                        else:
                            logger.info(f"⚠️ 步骤2：未解析出{year}年同比，步骤3将用当年+上年数据公式计算趋势")
                    else:
                        logger.info(f"⚠️ 步骤2：未检索到{year}年同比内容，步骤3将用当年+上年数据公式计算趋势")
                except Exception as e:
                    logger.warning(f"检索{year}年同比失败: {e}")
            
            # 构建一次性提取所有指标的提示词
            year_emphasis = f"{year}年" if year else "最新年度"
            extract_prompt = f"""请从以下检索到的文档内容中提取关键财务指标的具体数值。

【重要提示】
1. 这些内容是从PDF和Excel文件中检索到的，已经包含了最相关的数据
2. **特别注意：如果内容中包含表格（Markdown格式或文本表格），请仔细从表格中提取数据**
3. 营业收入可能有多种表述：营业收入、营业总收入、主营业务收入、收入等
4. **重要：请只提取{year_emphasis}的数据，不要使用其他年度的数据**
5. 如果文档中有多个年度数据，请优先使用{year_emphasis}的数据
6. 请仔细查找所有相关数据，特别是表格中的数据

【表格数据示例格式】
如果看到类似这样的表格：
| 项 目 | {year_emphasis} | 2023年 | 本年同比增减 |
|---|---|---|---|
| 营业收入 | 146,695 | 164,699 | (10.9%) |
| 加权平均净资产收益率 | 10.08% | 11.38% | -1.30个百分点 |

请从{year_emphasis}列中提取对应的数值。

【需要提取的指标】
1. 加权平均净资产收益率（ROE，{year_emphasis}，百分比）
   - 可能的表述：加权平均净资产收益率、ROE、净资产收益率等
   - **必须确保是{year_emphasis}的数据，使用年报披露的加权平均净资产收益率**
   - 示例：10.08% 或 10.08
2. 营业收入（{year_emphasis}，单位：元、万元或亿元）
   - 可能的表述：营业收入、营业总收入、主营业务收入、收入总额等
   - **必须确保是{year_emphasis}的数据**
   - 示例：146,695（万元）或 146,695万元
3. 净利润（{year_emphasis}，归属于母公司所有者的净利润，单位：元、万元或亿元）
   - 可能的表述：净利润、归属于母公司所有者的净利润、归母净利润、归属于本行股东的净利润等
   - **必须确保是{year_emphasis}的数据**
   - 示例：44,508（万元）或 44,508万元
4. 资产总额（{year_emphasis}，单位：元、万元或亿元）
   - 可能的表述：资产总额、总资产、资产合计等
   - **必须确保是{year_emphasis}的数据**
5. 净息差（{year_emphasis}，百分比）
   - 可能的表述：净息差、净利息收益率等
   - **必须确保是{year_emphasis}的数据**
   - 示例：1.87% 或 1.87
6. 成本收入比（{year_emphasis}，百分比）
   - 可能的表述：成本收入比、成本收入比率等
   - **必须确保是{year_emphasis}的数据**
   - 示例：27.66% 或 27.66

【提取要求】
- **优先从表格中提取数据**，表格数据最准确
- 仔细查找文档中的所有数据，不要遗漏
- **严格只提取{year_emphasis}的数据，忽略其他年度的数据**
- 只提取数值，不要分析
- 如果有同比变化率，请一并提取（如"+20%"、"-5%"、"下降"、"增长"等）
- 如果某个指标缺失，is_missing设为true
- 数值格式：如"100亿元"、"10.5亿元"、"30.5%"、"146,695万元"、"44,508万元"
- 必须从提供的文档内容中提取，不要编造数据

【检索到的文档内容】
{all_context_text if all_context_text else "未检索到相关文档内容"}

请仔细查找并提取所有能找到的{year_emphasis}财务数据。特别注意表格中的数据！"""
            
            # ========== 优先：LLM 单次生成结构化 JSON（当年+上年），趋势全部由计算得出 ==========
            use_llm_snapshot = False
            if all_context_text and year and year.isdigit() and len(all_context_text) >= 500:
                prev_year = str(int(year) - 1)
                llm_json_prompt = f"""从以下文档内容中提取 {year} 年与 {prev_year} 年两年的财务指标数值，只返回一个 JSON 对象，不要其他文字。

要求：
1. 返回格式（严格按此键名）：
{{"year":"{year}","prev_year":"{prev_year}","metrics":{{"roe":{{"value_{year}":10.08,"value_{prev_year}":11.38}},"revenue":{{"value_{year}":146695,"value_{prev_year}":164699,"unit":"万元"}},"net_profit":{{"value_{year}":44508,"value_{prev_year}":46140,"unit":"万元"}},"total_assets":{{"value_{year}":5769270,"value_{prev_year}":5520000,"unit":"万元"}},"net_interest_margin":{{"value_{year}":1.87,"value_{prev_year}":2.38}},"cost_income_ratio":{{"value_{year}":27.66,"value_{prev_year}":27.9}},"npl_ratio":{{"value_{year}":1.06,"value_{prev_year}":1.06}},"provision_coverage_ratio":{{"value_{year}":250.71,"value_{prev_year}":277.63}},"capital_adequacy_ratio":{{"value_{year}":9.12,"value_{prev_year}":9.22}}}}}}

2. 百分比类用数值；金额类带 unit（万元/亿元）。找不到的指标可省略。只返回 JSON。
3. 不良率(npl_ratio)必须从表格「不良率%」列读取，通常为1%左右(如1.06)，勿与ROA(0.78等)混淆。

文档内容：
{all_context_text[:12000] if len(all_context_text) > 12000 else all_context_text}

请返回 JSON："""
                try:
                    json_resp = await llm.acomplete(llm_json_prompt)
                    json_str = str(json_resp).strip()
                    json_match = re.search(r'\{[\s\S]*\}', json_str)
                    if json_match:
                        import json as _json
                        data = _json.loads(json_match.group(0))
                        metrics = data.get("metrics") or {}
                        cur_key, prev_key = f"value_{year}", f"value_{prev_year}"
                        amount_keys_llm = {"revenue", "net_profit", "total_assets"}
                        name_map_llm = {"roe": "ROE", "revenue": "营业收入", "net_profit": "净利润", "total_assets": "资产总额", "net_interest_margin": "净息差", "cost_income_ratio": "成本收入比", "npl_ratio": "不良率", "provision_coverage_ratio": "拨备覆盖率", "capital_adequacy_ratio": "资本充足率"}
                        filled = 0
                        for k, m in metrics.items():
                            cur_val, prev_val = m.get(cur_key), m.get(prev_key)
                            if cur_val is None:
                                continue
                            try:
                                v_cur = float(cur_val)
                            except (TypeError, ValueError):
                                continue
                            try:
                                v_prev = float(prev_val) if prev_val is not None else None
                            except (TypeError, ValueError):
                                v_prev = None
                            if k in amount_keys_llm:
                                unit = (m.get("unit") or "万元").strip()
                                if "亿" in unit:
                                    disp = f"{v_cur:,.2f}".rstrip('0').rstrip('.') if v_cur < 1000 else f"{v_cur:,.0f}"
                                else:
                                    disp = f"{v_cur/10000:,.2f}".rstrip('0').rstrip('.') if v_cur/10000 < 1000 else f"{v_cur/10000:,.0f}"
                                if v_prev is not None and v_prev != 0:
                                    pct = (v_cur - v_prev) / v_prev * 100
                                    if abs(v_cur - v_prev) < 1e-9:
                                        change_rate, change_direction = None, '持平'
                                    else:
                                        change_rate, change_direction = f"{pct:+.1f}%", '增长' if v_cur >= v_prev else '下降'
                                else:
                                    change_rate, change_direction = None, None
                            else:
                                disp = f"{v_cur}%"
                                if v_prev is not None and v_prev != 0:
                                    diff = v_cur - v_prev
                                    if abs(diff) < 1e-9:
                                        change_rate, change_direction = None, '持平'
                                    else:
                                        change_rate = f"{diff:+.2f}个百分点" if abs(v_prev) > 1 else f"{(v_cur-v_prev)/v_prev*100:+.1f}%"
                                        change_direction = '增长' if v_cur >= v_prev else '下降'
                                else:
                                    change_rate, change_direction = None, None
                            snapshot_dict[k] = {"name": name_map_llm.get(k, k), "value": disp, "change_rate": change_rate, "change_direction": change_direction, "is_missing": False}
                            filled += 1
                        if filled >= 6:
                            use_llm_snapshot = True
                            logger.info(f"✅ LLM 结构化 JSON 提取成功，共 {filled} 个指标，趋势已全部由当年/上年数值计算")
                            # 步骤2已检索到「{year}年同比」时，优先用检索到的趋势覆盖 LLM 计算值，保证前端与检索一致
                            for tk, (tr, td) in retrieved_trends.items():
                                if snapshot_dict.get(tk) and isinstance(snapshot_dict[tk], dict):
                                    snapshot_dict[tk]["change_rate"] = tr
                                    snapshot_dict[tk]["change_direction"] = td
                                    logger.info(f"  📈 已用步骤2检索同比覆盖: {tk} -> {tr}")
                except Exception as e:
                    logger.warning(f"LLM 结构化 JSON 提取失败: {str(e)}，将使用正则提取")
            
            if not use_llm_snapshot:
                # 优化：优先使用正则表达式从表格中直接提取（最可靠）
                logger.info("🔍 开始提取财务指标（优先使用正则表达式）...")
                logger.info(f"🔍 上下文文本长度: {len(all_context_text)}字符")
                
                # 第一步：使用正则表达式从表格文本中直接提取
                import re
                patterns = {
                    "roe": [
                        r'加权平均净资产收益率[|\s]+([\d,\.]+%?)',
                        r'加权平均净资产收益率[：:]\s*([\d,\.]+%?)',
                        r'ROE[|\s]+([\d,\.]+%?)',
                        r'ROE[：:]\s*([\d,\.]+%?)',
                    ],
                    "revenue": [
                        r'营业收入[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'营业收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                        r'营业总收入[|\s]+([\d,\.]+[万千百十亿]?元?)',
                    ],
                    "net_profit": [
                        r'归属于本行股东的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'归属于母公司所有者的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                    ],
                    "total_assets": [
                        r'资产总额[（(]?[万元亿元]*[）)]?[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'资产总额[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                        r'总资产[（(]?[万元亿元]*[）)]?[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'总资产[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'总资产[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                        r'资产合计[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'资产总计[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        r'资产总额\s+([\d,\.]+)',
                        r'总资产\s+([\d,\.]+)',
                    ],
                    "net_interest_margin": [
                        r'净息差[|\s]+([\d,\.]+%?)',
                        r'净息差[：:]\s*([\d,\.]+%?)',
                    ],
                    "cost_income_ratio": [
                        r'成本收入比[|\s]+([\d,\.]+%?)',
                        r'成本收入比[：:]\s*([\d,\.]+%?)',
                    ],
                    "npl_ratio": [
                        r'不良率[|\s]+([\d,\.]+%?)',
                        r'不良贷款率[|\s]+([\d,\.]+%?)',
                        r'不良率[：:]\s*([\d,\.]+%?)',
                    ],
                    "provision_coverage_ratio": [
                        r'拨备覆盖率[|\s]+([\d,\.]+%?)',
                        r'贷款拨备覆盖率[|\s]+([\d,\.]+%?)',
                        r'拨备覆盖率[：:]\s*([\d,\.]+%?)',
                    ],
                    "capital_adequacy_ratio": [
                        r'资本充足率[|\s]+([\d,\.]+%?)',
                        r'资本充足率[：:]\s*([\d,\.]+%?)',
                    ]
                }
                
                # 从上下文中提取年份列的数据（如果指定了年份）
                regex_extracted = {}
                for key, pattern_list in patterns.items():
                    for pattern in pattern_list:
                        matches = list(re.finditer(pattern, all_context_text, re.IGNORECASE | re.MULTILINE))
                        if matches:
                            # 如果有年份，优先选择年份列的数据
                            best_match = None
                            if year:
                                prev_year_str = str(int(year) - 1)
                                # 查找表格格式：| 指标名 | 2024年 | 2023年 | 或 | 2023年 | 2024年 |
                                # 优先选「紧挨当年列」的数值，避免把上年列当成本年
                                for match in matches:
                                    match_start = match.start()
                                    before_match = all_context_text[max(0, match_start - 35):match_start]
                                    # 要求：数值紧前方是当年列（如 "| 2024年 |" 或 "2024年 |"），而不是上年
                                    is_after_current_year = (
                                        re.search(rf'\|\s*{re.escape(year)}年?\s*\|', before_match) is not None
                                        or re.search(rf'{re.escape(year)}年?\s*\|', before_match) is not None
                                    )
                                    # 排除：数值紧前方是上年列（则说明这是上年数据）
                                    is_after_prev_year = (
                                        re.search(rf'\|\s*{re.escape(prev_year_str)}年?\s*\|', before_match) is not None
                                        or re.search(rf'{re.escape(prev_year_str)}年?\s*\|', before_match) is not None
                                    )
                                    if is_after_current_year and not is_after_prev_year:
                                        best_match = match
                                        logger.info(f"  ✅ 找到{year}年列的数据: {key}")
                                        break
                                if not best_match:
                                    for match in matches:
                                        start = max(0, match.start() - 200)
                                        end = min(len(all_context_text), match.end() + 200)
                                        context_around = all_context_text[start:end]
                                        year_in_context = f"{year}年" in context_around or str(year) in context_around
                                        match_start = match.start()
                                        before_match = all_context_text[max(0, match_start - 50):match_start]
                                        if year_in_context or (str(year) in before_match and '|' in before_match):
                                            best_match = match
                                            logger.info(f"  ✅ 找到{year}年的数据: {key}")
                                            break
                            
                            if not best_match:
                                best_match = matches[0]  # 使用第一个匹配
                            
                            value = best_match.group(1).strip()
                            # 为百分比指标添加%符号
                            pct_keys = ["roe", "net_interest_margin", "cost_income_ratio", "npl_ratio", "provision_coverage_ratio", "capital_adequacy_ratio"]
                            if key in pct_keys and not value.endswith('%'):
                                value = value + '%'
                            
                            # 趋势：优先用步骤2检索到的「{year}年同比」；否则同行同比；否则步骤3当年+上年公式计算
                            change_rate = None
                            change_direction = None
                            if key in retrieved_trends:
                                change_rate, change_direction = retrieved_trends[key]
                            match_start = best_match.start()
                            match_end = best_match.end()
                            after_match = all_context_text[match_end:match_end+200]
                            
                            if change_rate is None and change_direction is None:
                                # 查找同比增减模式（在表格的"本年同比增减"列中）
                                # 查找表格格式：| 指标 | 2024年 | 2023年 | 同比增减 |
                                change_patterns = [
                                    r'([\+\-]?\d+\.?\d*%?)',  # 如 +10.9%、-5.2%
                                    r'\(([\+\-]?\d+\.?\d*%?)\)',  # 如 (10.9%)、(-5.2%)
                                    r'([\+\-]?\d+\.?\d*)\s*个百分点',  # 如 -1.30个百分点
                                    r'(增长|下降|持平)',  # 文字描述
                                ]
                                for change_pattern in change_patterns:
                                    change_match = re.search(change_pattern, after_match)
                                    if change_match:
                                        change_text = change_match.group(1).strip()
                                        if any(c in change_text for c in ['+', '-', '%', '百分点']):
                                            change_rate = change_text
                                            if change_text.startswith('+') or ('%' in change_text and not change_text.startswith('-')):
                                                change_direction = '增长'
                                            elif change_text.startswith('-') or ('-' in change_text):
                                                change_direction = '下降'
                                            else:
                                                change_direction = '持平'
                                        elif change_text in ['增长', '下降', '持平']:
                                            change_direction = change_text
                                        if change_rate or change_direction:
                                            break
                                # 步骤3：仍无趋势则用当年+上年数值公式计算
                                if change_rate is None and change_direction is None:
                                    # 取 after_match 中「上年」列数值，需排除同比列（如 -3.5%、+10.9%）
                                    prev_num = None
                                    for num_match in re.finditer(r'[\s|]*([-+]?\d+[,，]?\d*\.?\d*)\s*([%万千百十亿]?)', after_match):
                                        prev_value_str = num_match.group(1).strip().replace(',', '').replace('，', '')
                                        unit_suffix = (num_match.group(2) or '').strip()
                                        n = _parse_metric_value(prev_value_str) if prev_value_str else None
                                        if n is None:
                                            continue
                                        amount_keys = ["revenue", "net_profit", "total_assets"]
                                        if key in amount_keys:
                                            if n > 10 and (unit_suffix in ('万', '亿', '元', '') or not unit_suffix):
                                                prev_num = n
                                                break
                                            if unit_suffix in ('万', '亿', '元') and n > 0:
                                                prev_num = n
                                                break
                                        else:
                                            if unit_suffix == '%' and -50 <= n <= 50 and n != 0:
                                                continue
                                            if abs(n) > 1e-9:
                                                prev_num = n
                                                break
                                    cur_num = _parse_metric_value(value)
                                    if cur_num is not None and prev_num is not None and abs(prev_num) > 1e-9:
                                        amount_keys = ["revenue", "net_profit", "total_assets"]
                                        if key in amount_keys:
                                            pct = (cur_num - prev_num) / prev_num * 100
                                            if abs(cur_num - prev_num) < 1e-9:
                                                change_rate, change_direction = None, '持平'
                                            else:
                                                change_rate, change_direction = f"{pct:+.1f}%", '增长' if cur_num >= prev_num else '下降'
                                        else:
                                            diff = cur_num - prev_num
                                            if abs(diff) < 1e-9:
                                                change_rate, change_direction = None, '持平'
                                            else:
                                                change_rate = f"{diff:+.2f}个百分点" if abs(prev_num) > 1 else f"{(cur_num - prev_num) / prev_num * 100:+.1f}%"
                                                change_direction = '增长' if cur_num >= prev_num else '下降'
                                        if change_rate:
                                            logger.info(f"  📐 步骤3 趋势公式计算: {key} cur={cur_num} prev={prev_num} change_rate={change_rate}")
                            
                        regex_extracted[key] = {
                            "name": {
                                "roe": "加权平均净资产收益率（ROE）",
                                "revenue": "营业收入",
                                "net_profit": "净利润",
                                "total_assets": "资产总额",
                                "net_interest_margin": "净息差",
                                "cost_income_ratio": "成本收入比",
                                "npl_ratio": "不良率",
                                "provision_coverage_ratio": "拨备覆盖率",
                                "capital_adequacy_ratio": "资本充足率"
                            }.get(key, key),
                            "value": value,
                            "change_rate": change_rate,
                            "change_direction": change_direction,
                            "is_missing": False
                        }
                        logger.info(f"  ✅ 正则提取到 {key}: {value}" + (f", 同比(检索): {change_rate}" if change_rate else ""))
                        break
                
                # 更新snapshot_dict
                snapshot_dict.update(regex_extracted)
                logger.info(f"✅ 正则表达式提取完成，提取到 {len(regex_extracted)} 个指标")
                
                # 第二步：如果正则提取不完整，使用JSON格式的LLM提取补充
                missing_keys = [k for k in ["roe", "revenue", "net_profit", "total_assets", "net_interest_margin", "cost_income_ratio"] 
                              if snapshot_dict.get(k) is None]
                
                if missing_keys:
                    logger.info(f"⚠️ 以下指标未通过正则提取，使用JSON格式LLM提取: {missing_keys}")
                    
                    # 使用简化的JSON格式提取
                    json_prompt = f"""请从以下文档内容中提取财务指标，以JSON格式返回。
    
    要求：
    1. 只提取{year_emphasis}的数据
    2. 返回格式必须是有效的JSON，格式如下（必须包含change_rate和change_direction字段）：
    {{
      "roe": {{"name": "加权平均净资产收益率（ROE）", "value": "10.08%", "change_rate": "-1.30个百分点", "change_direction": "下降", "is_missing": false}},
      "revenue": {{"name": "营业收入", "value": "146,695万元", "change_rate": "-10.9%", "change_direction": "下降", "is_missing": false}},
      "net_profit": {{"name": "净利润", "value": "44,508万元", "change_rate": "-4.2%", "change_direction": "下降", "is_missing": false}},
      "total_assets": {{"name": "资产总额", "value": "5,000,000万元", "change_rate": "+3.7%", "change_direction": "增长", "is_missing": false}},
      "net_interest_margin": {{"name": "净息差", "value": "1.87%", "change_rate": "-0.51个百分点", "change_direction": "下降", "is_missing": false}},
      "cost_income_ratio": {{"name": "成本收入比", "value": "27.66%", "change_rate": "-0.24个百分点", "change_direction": "下降", "is_missing": false}}
    }}
    
    3. 如果找不到某个指标，设置 "is_missing": true, "value": null
    4. 如果找不到同比增减数据，change_rate和change_direction可以设为null
    5. 只返回JSON，不要其他文字说明
    6. 优先从表格中提取数据，特别注意"本年同比增减"或"同比增减"列
    
    文档内容：
    {all_context_text[:3000] if len(all_context_text) > 3000 else all_context_text}
    
    请返回JSON格式的数据："""
                    
                    try:
                        json_response = await llm.acomplete(json_prompt)
                        json_text = str(json_response).strip()
                        
                        # 提取JSON部分
                        json_match = re.search(r'\{[\s\S]*\}', json_text)
                        if json_match:
                            import json
                            json_data = json.loads(json_match.group(0))
                            
                            # 更新缺失的指标
                            for key in missing_keys:
                                if key in json_data and json_data[key]:
                                    metric_data = json_data[key]
                                    if isinstance(metric_data, dict) and not metric_data.get('is_missing'):
                                        snapshot_dict[key] = metric_data
                                        logger.info(f"  ✅ JSON提取到 {key}: {metric_data.get('value')}")
                    except Exception as e:
                        logger.warning(f"  ❌ JSON提取失败: {str(e)}")
                
                # 第三步：如果还有缺失的指标，进行补充检索
                still_missing = [k for k in ["roe", "revenue", "net_profit", "total_assets", "net_interest_margin", "cost_income_ratio", "npl_ratio", "provision_coverage_ratio", "capital_adequacy_ratio"] 
                               if snapshot_dict.get(k) is None]
                
                if still_missing and use_hybrid:
                    logger.info(f"⚠️ 以下指标仍未提取到，进行补充检索: {still_missing}")
                    
                    # 为每个缺失的指标单独进行补充检索
                    indicator_keywords = {
                        "roe": ["加权平均净资产收益率", "ROE"],
                        "revenue": ["营业收入", "营业总收入"],
                        "net_profit": ["净利润", "归属于母公司所有者的净利润"],
                        "total_assets": ["资产总额", "总资产", "资产合计", "资产总计"],
                        "net_interest_margin": ["净息差"],
                        "cost_income_ratio": ["成本收入比"],
                        "npl_ratio": ["不良率", "不良贷款率"],
                        "provision_coverage_ratio": ["拨备覆盖率", "贷款拨备覆盖率"],
                        "capital_adequacy_ratio": ["资本充足率"]
                    }
                    
                    supplement_contexts = []
                    for missing_key in still_missing:
                        keywords = indicator_keywords.get(missing_key, [missing_key])
                        if year and company_name:
                            supplement_query = f"{company_name} {year}年 {' '.join(keywords)} {year}年度数值"
                        elif year:
                            supplement_query = f"{year}年 {' '.join(keywords)} {year}年度数值"
                        elif company_name:
                            supplement_query = f"{company_name} {' '.join(keywords)} 最新年度数值"
                        else:
                            supplement_query = f"{' '.join(keywords)} 最新年度数值"
                        
                        logger.info(f"  🔍 补充检索: {missing_key} ({keywords[0]})")
                        try:
                            supplement_results = rag_engine.hybrid_retriever.retrieve(
                                supplement_query,
                                top_k=20,
                                strategy='table_first',
                                context_filter=context_filter if context_filter else None
                            )
                            
                            if supplement_results:
                                supplement_text = "\n\n".join([r['document'].text for r in supplement_results[:10]])
                                supplement_contexts.append(supplement_text)
                                logger.info(f"    ✅ {missing_key} 补充检索到 {len(supplement_results)} 个结果")
                            else:
                                logger.warning(f"    ⚠️ {missing_key} 补充检索未找到结果")
                        except Exception as e:
                            logger.warning(f"    ❌ {missing_key} 补充检索失败: {str(e)}")
                    
                    # 将补充的上下文添加到all_context_text
                    if supplement_contexts:
                        all_context_text = all_context_text + "\n\n" + "\n\n".join(supplement_contexts)
                        logger.info(f"✅ 补充检索后，上下文长度: {len(all_context_text)}字符")
                        
                        # 对补充的上下文再次进行正则提取
                        for missing_key in still_missing:
                            keywords = indicator_keywords.get(missing_key, [missing_key])
                            patterns = {
                                "roe": [r'加权平均净资产收益率[|\s]+([\d,\.]+%?)', r'ROE[|\s]+([\d,\.]+%?)'],
                                "revenue": [r'营业收入[|\s]+([\d,\.]+[万千百十亿]?元?)', r'营业总收入[|\s]+([\d,\.]+[万千百十亿]?元?)'],
                                "net_profit": [r'归属于本行股东的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)', r'归属于母公司所有者的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)', r'净利润[|\s]+([\d,\.]+[万千百十亿]?元?)'],
                                "total_assets": [r'资产总额[|\s]+([\d,\.]+[万千百十亿]?元?)', r'总资产[|\s]+([\d,\.]+[万千百十亿]?元?)', r'资产合计[|\s]+([\d,\.]+[万千百十亿]?元?)'],
                                "net_interest_margin": [r'净息差[|\s]+([\d,\.]+%?)'],
                                "cost_income_ratio": [r'成本收入比[|\s]+([\d,\.]+%?)']
                            }
                            
                            key_patterns = patterns.get(missing_key, [])
                            for pattern in key_patterns:
                                matches = list(re.finditer(pattern, all_context_text, re.IGNORECASE | re.MULTILINE))
                                if matches:
                                    best_match = matches[0]
                                    value = best_match.group(1).strip()
                                    if missing_key in ["roe", "net_interest_margin", "cost_income_ratio"] and not value.endswith('%'):
                                        value = value + '%'
                                    
                                    snapshot_dict[missing_key] = {
                                        "name": {
                                            "roe": "加权平均净资产收益率（ROE）",
                                            "revenue": "营业收入",
                                            "net_profit": "净利润",
                                            "total_assets": "资产总额",
                                            "net_interest_margin": "净息差",
                                            "cost_income_ratio": "成本收入比"
                                        }.get(missing_key, missing_key),
                                        "value": value,
                                        "change_rate": None,
                                        "change_direction": None,
                                        "is_missing": False
                                    }
                                    logger.info(f"  ✅ 补充检索后正则提取到 {missing_key}: {value}")
                                    break
                
                logger.info(f"✅ 提取完成，最终提取到的指标: {[k for k, v in snapshot_dict.items() if v is not None and (not isinstance(v, dict) or not v.get('is_missing'))]}")
        
        except Exception as e:
            logger.warning(f"结构化提取失败: {str(e)}，使用备用方案")
            import traceback
            logger.warning(f"详细错误: {traceback.format_exc()}")
            
            # 备用方案：优先从Excel表格查询，然后使用正则提取
            try:
                    logger.info("🔄 使用备用方案：优先检索Excel表格...")
                    
                    # 优先查询Excel表格，强调年份
                    if year:
                        excel_query = f"Excel表格 Excel文件 利润表 资产负债表 现金流量表 {year}年 加权平均净资产收益率 ROE 营业收入 净利润 资产总额 净息差 成本收入比 {year}年度数值"
                    else:
                        excel_query = "Excel表格 Excel文件 利润表 资产负债表 现金流量表 加权平均净资产收益率 ROE 营业收入 净利润 资产总额 净息差 成本收入比 最新年度数值"
                    
                    # 尝试从表格数据中检索（应用公司过滤）
                    try:
                        retriever = rag_engine.index.as_retriever(similarity_top_k=30)  # 扩大检索范围以便过滤
                        nodes = retriever.retrieve(excel_query)
                        
                        # 应用公司过滤
                        if context_filter and 'company' in context_filter:
                            nodes = rag_engine._filter_nodes(nodes, context_filter)
                            logger.info(f"  ✅ 应用公司过滤后，剩余 {len(nodes)} 个节点")
                        
                        # 手动过滤表格数据
                        table_nodes = [n for n in nodes if n.metadata.get('document_type') == 'table_data' or n.metadata.get('is_financial', False)]
                        
                        if table_nodes:
                            response_text = "\n".join([node.text for node in table_nodes[:10]])  # 增加表格数量，确保包含资产负债表
                            logger.info(f"  ✅ 从Excel表格检索到 {len(table_nodes)} 个表格数据（已应用公司过滤）")
                            logger.info(f"  📊 表格文本长度: {len(response_text)}字符")
                            # 检查是否包含资产总额相关关键词
                            if '资产总额' in response_text or '总资产' in response_text or '资产合计' in response_text:
                                logger.info(f"  ✅ 表格中包含资产总额相关数据")
                            else:
                                logger.warning(f"  ⚠️ 表格中未找到资产总额相关关键词")
                        elif nodes:
                            # 如果没有表格，使用所有检索到的数据
                            response_text = "\n".join([node.text for node in nodes[:3]])
                            logger.info(f"  ✅ 从文档检索到数据（已应用公司过滤）")
                        else:
                            # 回退到普通查询（应用公司过滤）
                            if context_filter:
                                result = rag_engine.query(excel_query, context_filter)
                                response_text = result.get('answer', '').strip()
                            else:
                                response = rag_engine.query_engine.query(excel_query)
                                response_text = str(response).strip()
                    except Exception as e:
                        logger.warning(f"表格检索失败: {str(e)}，使用普通查询")
                        # 如果表格检索失败，使用普通查询（应用公司过滤）
                        if context_filter:
                            result = rag_engine.query(excel_query, context_filter)
                            response_text = result.get('answer', '').strip()
                        else:
                            response = rag_engine.query_engine.query(excel_query)
                            response_text = str(response).strip()
                    
                    # 使用正则表达式快速提取（增加更多模式，包括表格格式）
                    patterns = {
                        "roe": [
                            # 表格格式：| 加权平均净资产收益率 | 10.08% | 11.38% |
                            r'加权平均净资产收益率[|\s]+([\d,\.]+%?)',
                            r'加权平均净资产收益率[：:]\s*([\d,\.]+%?)',
                            r'加权平均净资产收益率\s+([\d,\.]+%?)',
                            r'ROE[|\s]+([\d,\.]+%?)',
                            r'ROE[：:]\s*([\d,\.]+%?)',
                            r'ROE\s+([\d,\.]+%?)',
                            r'净资产收益率[|\s]+([\d,\.]+%?)',
                            r'净资产收益率[：:]\s*([\d,\.]+%?)',
                            r'净资产收益率\s+([\d,\.]+%?)',
                        ],
                        "revenue": [
                            # 表格格式：| 营业收入 | 146,695 | 164,699 |
                            r'营业收入[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'营业收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'营收[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'营业总收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'主营业务收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'收入[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'营业收入\s+([\d,\.]+[万千百十亿]?元?)',
                            r'营业总收入\s+([\d,\.]+[万千百十亿]?元?)',
                            # 表格格式：营业收入 | 数值
                            r'营业收入[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'营业总收入[|\s]+([\d,\.]+[万千百十亿]?元?)',
                        ],
                        "net_profit": [
                            # 表格格式：| 归属于本行股东的净利润 | 44,508 | 46,455 |
                            r'归属于本行股东的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'归属于母公司所有者的净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'归母净利润[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'归母净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'归属于母公司所有者的净利润[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'净利润\s+([\d,\.]+[万千百十亿]?元?)',
                            r'归母净利润\s+([\d,\.]+[万千百十亿]?元?)',
                        ],
                        "total_assets": [
                            # 表格格式：| 资产总额 | 5,000,000 | 4,800,000 |
                            r'资产总额[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'总资产[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'资产合计[|\s]+([\d,\.]+[万千百十亿]?元?)',
                            r'资产总额[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'总资产[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'资产合计[：:]\s*([\d,\.]+[万千百十亿]?元?)',
                            r'资产总额\s+([\d,\.]+[万千百十亿]?元?)',
                            r'总资产\s+([\d,\.]+[万千百十亿]?元?)',
                            r'资产合计\s+([\d,\.]+[万千百十亿]?元?)',
                        ],
                        "net_interest_margin": [
                            # 表格格式：| 净息差 | 1.87% | 2.38% |
                            r'净息差[|\s]+([\d,\.]+%?)',
                            r'净息差[：:]\s*([\d,\.]+%?)',
                            r'净息差\s+([\d,\.]+%?)',
                            r'净利息收益率[|\s]+([\d,\.]+%?)',
                            r'净利息收益率[：:]\s*([\d,\.]+%?)',
                            r'净利息收益率\s+([\d,\.]+%?)',
                        ],
                        "cost_income_ratio": [
                            # 表格格式：| 成本收入比 | 27.66% | 27.90% |
                            r'成本收入比[|\s]+([\d,\.]+%?)',
                            r'成本收入比[：:]\s*([\d,\.]+%?)',
                            r'成本收入比\s+([\d,\.]+%?)',
                            r'成本收入比率[|\s]+([\d,\.]+%?)',
                            r'成本收入比率[：:]\s*([\d,\.]+%?)',
                            r'成本收入比率\s+([\d,\.]+%?)',
                        ]
                    }
                    
                    for key, pattern_list in patterns.items():
                        found = False
                        for pattern in pattern_list:
                            match = re.search(pattern, response_text, re.IGNORECASE | re.MULTILINE)
                            if match:
                                value = match.group(1).strip()
                                # 为百分比指标添加%符号（如果没有）
                                if key in ["roe", "net_interest_margin", "cost_income_ratio"] and not value.endswith('%'):
                                    value = value + '%'
                                # 为金额类指标添加单位（如果没有）
                                if key in ["revenue", "net_profit", "total_assets"] and not any(unit in value for unit in ['元', '万元', '亿元', '千元']):
                                    # 如果数值很大（超过1000），可能是万元或亿元
                                    num_value = value.replace(',', '').replace('，', '')
                                    try:
                                        num = float(num_value)
                                        if num >= 100000000:
                                            value = value + '亿元'
                                        elif num >= 10000:
                                            value = value + '万元'
                                        else:
                                            value = value + '元'
                                    except:
                                        pass
                                snapshot_dict[key] = {
                                    "name": {
                                        "roe": "加权平均净资产收益率（ROE）",
                                        "revenue": "营业收入",
                                        "net_profit": "净利润",
                                        "total_assets": "资产总额",
                                        "net_interest_margin": "净息差",
                                        "cost_income_ratio": "成本收入比"
                                    }.get(key, key),
                                    "value": value,
                                    "is_missing": False
                                }
                                logger.info(f"  ✅ 正则提取到 {key}: {value} (模式: {pattern[:50]}...)")
                                found = True
                                break
                        if not found:
                            logger.warning(f"  ⚠️ 未找到 {key} 的数据")
                    
                    logger.info(f"✅ 备用方案提取完成")
            
            except Exception as e2:
                logger.warning(f"备用方案也失败: {str(e2)}")
        
        # ========== 第二阶段：快速生成结论（基于已提取的指标）==========
        logger.info("第二阶段：快速生成结论...")
        
        # 构建简化的指标摘要（不计算比率，加快速度）
        metrics_summary = []
        if snapshot_dict.get("roe"):
            roe = snapshot_dict["roe"]
            if isinstance(roe, dict) and not roe.get("is_missing"):
                metrics_summary.append(f"ROE: {roe.get('value', 'N/A')}")
        if snapshot_dict.get("revenue"):
            rev = snapshot_dict["revenue"]
            if isinstance(rev, dict) and not rev.get("is_missing"):
                metrics_summary.append(f"营业收入: {rev.get('value', 'N/A')}")
        if snapshot_dict.get("net_profit"):
            profit = snapshot_dict["net_profit"]
            if isinstance(profit, dict) and not profit.get("is_missing"):
                metrics_summary.append(f"净利润: {profit.get('value', 'N/A')}")
        if snapshot_dict.get("total_assets"):
            assets = snapshot_dict["total_assets"]
            if isinstance(assets, dict) and not assets.get("is_missing"):
                metrics_summary.append(f"资产总额: {assets.get('value', 'N/A')}")
        if snapshot_dict.get("net_interest_margin"):
            nim = snapshot_dict["net_interest_margin"]
            if isinstance(nim, dict) and not nim.get("is_missing"):
                metrics_summary.append(f"净息差: {nim.get('value', 'N/A')}")
        if snapshot_dict.get("cost_income_ratio"):
            cir = snapshot_dict["cost_income_ratio"]
            if isinstance(cir, dict) and not cir.get("is_missing"):
                metrics_summary.append(f"成本收入比: {cir.get('value', 'N/A')}")
        
        metrics_text = "\n".join(metrics_summary) if metrics_summary else "财务数据不足"
        year_info = f"{year}年" if year else "最新年度"
        
        # 构建优化的提示词（强调使用Excel表格数据和年份）
        verdict_prompt = f"""基于以下{year_info}财务指标，快速生成一句话核心结论：

{metrics_text}

【重要提示】
- 这些数据来自Excel表格，是准确的财务数据
- **这些数据是{year_info}的数据，请基于{year_info}的数值进行分析**
- 请基于这些具体数值进行分析，不要猜测

要求：
1. 只输出一句话核心结论，不要详细分析
2. 必须包含三个维度：
   - 公司阶段（增长/稳态/下行）- 根据{year_info}营收和净利润数值判断
   - 赚钱质量（利润质量/资产质量）- 根据{year_info}净利润和资产总额判断
   - 风险级别（低/中/高）- 根据{year_info}财务指标综合判断
3. 格式：公司处于[阶段]阶段，[赚钱质量描述]，风险级别[级别]
4. 不超过60字
5. 如果数据不足，明确说明
6. 快速判断，基于Excel表格中{year_info}的具体数值

示例：公司处于增长阶段，利润质量良好但现金质量一般，风险级别中等。"""
        
        try:
            # 优先从Excel表格检索相关数据来生成结论
            logger.info("🔍 检索Excel表格数据用于生成结论...")
            
            # 先尝试从表格中检索相关数据（应用公司过滤）
            try:
                conclusion_retriever = rag_engine.index.as_retriever(similarity_top_k=30)  # 扩大检索范围以便过滤
                if year:
                    conclusion_query = f"{year}年 财务指标 ROE 加权平均净资产收益率 营业收入 净利润 资产总额 净息差 成本收入比 趋势 变化 {year}年度"
                else:
                    conclusion_query = "财务指标 ROE 加权平均净资产收益率 营业收入 净利润 资产总额 净息差 成本收入比 趋势 变化"
                all_conclusion_nodes = conclusion_retriever.retrieve(conclusion_query)
                
                # 应用公司过滤
                if context_filter and 'company' in context_filter:
                    all_conclusion_nodes = rag_engine._filter_nodes(all_conclusion_nodes, context_filter)
                    logger.info(f"  ✅ 应用公司过滤后，剩余 {len(all_conclusion_nodes)} 个节点")
                
                # 手动过滤表格数据
                conclusion_nodes = [n for n in all_conclusion_nodes if n.metadata.get('document_type') == 'table_data' or n.metadata.get('is_financial', False)]
                
                if conclusion_nodes:
                    conclusion_context = "\n\n".join([node.text for node in conclusion_nodes[:3]])
                    verdict_prompt = f"""{verdict_prompt}

【补充的Excel表格数据】
{conclusion_context}

请结合上述Excel表格数据和财务指标，生成更准确的结论。"""
                    logger.info(f"  ✅ 已添加 {len(conclusion_nodes)} 个Excel表格上下文")
            except Exception as e:
                logger.warning(f"检索Excel表格数据失败: {str(e)}")
            
            # 使用rag_engine.query生成结论（它会应用公司过滤）
            if context_filter:
                result = rag_engine.query(verdict_prompt, context_filter)
                verdict_text = result.get('answer', '').strip()
            else:
                response_obj = rag_engine.query_engine.query(verdict_prompt)
                verdict_text = str(response_obj).strip()
            
            # 清理结论文本
            verdict_text = re.sub(r'^(?:核心结论[：:]|核心结论\*\*[：:])\s*\*?\*?', '', verdict_text)
            verdict_text = re.sub(r'\*\*', '', verdict_text)
            
            # 只取第一句话
            if len(verdict_text) > 150:
                sentences = re.split(r'[。！？\n]', verdict_text)
                if sentences and len(sentences[0]) > 15:
                    verdict_text = sentences[0].strip() + '。'
                else:
                    verdict_text = verdict_text[:100] + '...'
            
            if not verdict_text or len(verdict_text) < 15:
                verdict_text = "数据不足，无法生成完整结论。"
            
            # 解析结论，提取三个维度
            stage = None
            profit_quality = None
            risk_level = None
            
            if '增长' in verdict_text:
                stage = '增长'
            elif '稳态' in verdict_text or '稳定' in verdict_text:
                stage = '稳态'
            elif '下行' in verdict_text or '下降' in verdict_text:
                stage = '下行'
            
            # 提取赚钱质量
            profit_match = re.search(r'利润质量[^，,。、]+', verdict_text)
            cash_match = re.search(r'现金质量[^，,。、]+', verdict_text)
            if profit_match and cash_match:
                profit_quality = profit_match.group(0) + '、' + cash_match.group(0)
            elif profit_match:
                profit_quality = profit_match.group(0)
            elif cash_match:
                profit_quality = cash_match.group(0)
            elif '利润质量差' in verdict_text:
                profit_quality = '利润质量差'
            elif '利润质量良好' in verdict_text:
                profit_quality = '利润质量良好'
            elif '现金质量无法评估' in verdict_text:
                profit_quality = '现金质量无法评估'
            
            # 提取风险级别
            if '风险级别低' in verdict_text or '风险低' in verdict_text:
                risk_level = '低'
            elif '风险级别中' in verdict_text or '风险中等' in verdict_text or '风险级别中等' in verdict_text:
                risk_level = '中'
            elif '风险级别高' in verdict_text or '风险高' in verdict_text:
                risk_level = '高'
            
        except Exception as e:
            logger.warning(f"生成结论失败: {str(e)}")
            verdict_text = "数据不足，无法生成完整结论。"
            stage = None
            profit_quality = None
            risk_level = None
        
        # 构建最终返回数据
        overview_data = {
            "roe": snapshot_dict.get("roe"),
            "revenue": snapshot_dict.get("revenue"),
            "net_profit": snapshot_dict.get("net_profit"),
            "total_assets": snapshot_dict.get("total_assets"),
            "net_interest_margin": snapshot_dict.get("net_interest_margin"),
            "cost_income_ratio": snapshot_dict.get("cost_income_ratio"),
            "npl_ratio": snapshot_dict.get("npl_ratio"),
            "provision_coverage_ratio": snapshot_dict.get("provision_coverage_ratio"),
            "capital_adequacy_ratio": snapshot_dict.get("capital_adequacy_ratio"),
            "verdict": verdict_text,
            "stage": stage,
            "profit_quality": profit_quality,
            "risk_level": risk_level,
            "missing_fields": []
        }
        
        # 添加调试日志：检查每个指标的状态
        logger.info(f"🔍 最终返回数据检查:")
        for key in ["roe", "revenue", "net_profit", "total_assets", "net_interest_margin", "cost_income_ratio", "npl_ratio", "provision_coverage_ratio", "capital_adequacy_ratio"]:
            value = overview_data.get(key)
            if value:
                if isinstance(value, dict):
                    logger.info(f"  {key}: value={value.get('value')}, is_missing={value.get('is_missing')}")
                else:
                    logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {key}: None")
        
        # 检查缺失字段
        if not overview_data.get("revenue") or (isinstance(overview_data["revenue"], dict) and overview_data["revenue"].get("is_missing")):
            overview_data['missing_fields'].append('营业收入')
        if not overview_data.get("net_profit") or (isinstance(overview_data["net_profit"], dict) and overview_data["net_profit"].get("is_missing")):
            overview_data['missing_fields'].append('净利润')
        if not overview_data.get("total_assets") or (isinstance(overview_data["total_assets"], dict) and overview_data["total_assets"].get("is_missing")):
            overview_data['missing_fields'].append('资产总额')
        if not stage:
            overview_data['missing_fields'].append('公司阶段')
        if not profit_quality:
            overview_data['missing_fields'].append('赚钱质量')
        if not risk_level:
            overview_data['missing_fields'].append('风险级别')
        
        logger.info(f"✅ 财务快照生成成功")
        
        return JSONResponse(status_code=200, content={
            "status": "success",
            "overview": overview_data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成财务快照失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return JSONResponse(status_code=200, content={
            "status": "success",
            "overview": {
                "roe": None,
                "revenue": None,
                "net_profit": None,
                "total_assets": None,
                "verdict": "数据不足，无法生成完整结论。",
                "stage": None,
                "profit_quality": None,
                "risk_level": None,
                "missing_fields": ["所有字段"]
            }
        })

class ComprehensiveAnalysisRequest(BaseModel):
    """综合能力分析请求"""
    selected_cards: List[Dict[str, Any]] = Field(description="选中的可视化卡片列表")
    overview_data: Optional[Dict[str, Any]] = Field(default=None, description="财务概况数据")
    context_filter: Optional[Dict[str, Any]] = None
    exploration_question: Optional[str] = Field(
        default=None,
        description="用户输入的深入探索问题（可选，如果为空则进行综合分析）"
    )
    interaction_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="交互上下文（如数据点钻取），用于生成更精准的联动分析"
    )


def _build_drill_exploration_question(interaction_context: Dict[str, Any]) -> Optional[str]:
    """
    从前端数据点钻取上下文生成探索问题（用于复用现有联动分析链路）
    """
    if not interaction_context:
        return None

    if interaction_context.get("interaction_type") != "data_point_drill":
        return None

    clicked_point = interaction_context.get("clicked_point", {}) or {}
    drill_type = interaction_context.get("drill_type", "general_drill")
    chart_info = interaction_context.get("chart_info", {}) or {}

    x_value = clicked_point.get("x")
    y_value = clicked_point.get("y")
    label = clicked_point.get("label") or clicked_point.get("series_name") or "该数据点"
    metric_hint = "、".join(chart_info.get("key_metrics", [])[:2]) if chart_info.get("key_metrics") else "相关指标"

    if drill_type == "time_drill":
        return f"请围绕时间点 {x_value} 深入分析 {metric_hint} 的变化原因，并给出该时点前后对比。"
    if drill_type == "category_drill":
        return f"请对分类「{label}」做下钻分析，说明其构成、驱动因素及与其他分类的差异。"
    if drill_type == "anomaly_analysis":
        return f"数据点 {x_value}/{label}（值为 {y_value}）疑似异常，请分析异常成因、影响与验证路径。"
    return f"请对数据点 {x_value}/{label}（值为 {y_value}）做下钻分析，给出关键发现和验证结论。"

def _extract_company_and_year_from_filename(filename: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从文件名中提取公司名和年份
    
    Args:
        filename: 文件名，如"平安银行2024年年报.PDF"
    
    Returns:
        (company_name, year) 元组
    """
    if not filename:
        return None, None
    
    # 提取年份（4位数字）
    year_match = re.search(r'20\d{2}', filename)
    year = year_match.group() if year_match else None
    
    # 提取公司名（移除年份、文件扩展名、常见后缀）
    company_name = filename
    if year:
        company_name = company_name.replace(year, '')
    # 移除文件扩展名
    company_name = re.sub(r'\.[^.]+$', '', company_name)
    # 移除常见后缀
    company_name = re.sub(r'(年报|报告|财务报表|财务报告|年度)', '', company_name)
    company_name = company_name.strip()
    
    return company_name if company_name else None, year


@router.post("/comprehensive-analysis")
async def generate_comprehensive_analysis(request: ComprehensiveAnalysisRequest):
    """
    生成综合视图分析（基于视图联动方案，支持探索问题）
    
    支持两种模式：
    1. 单卡片模式：选中1个卡片，生成关联视图
    2. 多卡片模式：选中多个卡片，生成综合分析和关联视图
    
    探索问题：
    - 如果提供了exploration_question，将聚焦回答用户问题（focused模式）
    - 如果没有提供，将进行综合分析（comprehensive模式）
    
    Returns:
        包含新视图列表的响应（兼容原有格式）
    """
    try:
        # 处理探索问题
        exploration_question = request.exploration_question if hasattr(request, 'exploration_question') else None
        if exploration_question:
            exploration_question = exploration_question.strip()
            if not exploration_question:
                exploration_question = None

        # 处理交互上下文（交互形式3：数据点钻取）
        interaction_context = request.interaction_context if hasattr(request, 'interaction_context') else None
        if interaction_context and not exploration_question:
            drill_question = _build_drill_exploration_question(interaction_context)
            if drill_question:
                exploration_question = drill_question
                logger.info(f"识别到数据点钻取交互，自动生成探索问题: {exploration_question}")
        
        # 确定探索模式
        if exploration_question:
            exploration_mode = "focused"  # 聚焦模式：优先回答用户问题
            logger.info(f"收到综合视图分析请求，选中{len(request.selected_cards)}个卡片，探索问题：{exploration_question[:50]}...")
        else:
            exploration_mode = "comprehensive"  # 综合分析模式
            logger.info(f"收到综合视图分析请求，选中{len(request.selected_cards)}个卡片，将进行综合分析")
        
        # 获取RAG引擎
        rag_engine = get_rag_engine()
        
        if not rag_engine.query_engine:
            if not rag_engine.load_existing_index():
                raise HTTPException(
                    status_code=400,
                    detail="索引未构建，请先处理文档"
                )
        
        # 从context_filter中提取公司名和年份
        company_name = None
        year = None
        if request.context_filter:
            filename = request.context_filter.get('filename', '')
            company_name, year = _extract_company_and_year_from_filename(filename)
        
        # 如果没有，尝试从overview_data中获取
        if not company_name and request.overview_data:
            company_name = request.overview_data.get('company_name')
            year = request.overview_data.get('year')
        
        # 如果还是没有，使用默认值或从卡片中提取
        if not company_name:
            company_name = "未知公司"
        if not year:
            year = "2024"  # 默认年份
        
        logger.info(f"使用公司名: {company_name}, 年份: {year}")
        
        # 根据卡片数量选择处理方式
        if len(request.selected_cards) == 1:
            # 单卡片模式：使用单卡片视图联动
            from agents.view_linkage import SingleCardLinkageEngine
            linkage_engine = SingleCardLinkageEngine(
                query_engine=rag_engine.query_engine,
                rag_engine=rag_engine
            )
            
            card = request.selected_cards[0]
            result = await linkage_engine.generate_linkage_from_card(
                card=card,
                company_name=company_name,
                year=year,
                context_filter=request.context_filter,
                exploration_question=exploration_question,  # ⭐新增参数
                exploration_mode=exploration_mode  # ⭐新增参数
            )
        else:
            # 多卡片模式：使用多卡片视图联动
            from agents.view_linkage import MultiCardLinkageEngine
            linkage_engine = MultiCardLinkageEngine(
                query_engine=rag_engine.query_engine,
                rag_engine=rag_engine
            )
            
            result = await linkage_engine.generate_linkage_from_cards(
                selected_cards=request.selected_cards,
                company_name=company_name,
                year=year,
                context_filter=request.context_filter,
                exploration_question=exploration_question,  # ⭐新增参数
                exploration_mode=exploration_mode  # ⭐新增参数
            )
        
        # 辅助函数：递归序列化Pydantic模型
        def serialize_pydantic(obj):
            """递归序列化Pydantic模型和嵌套对象"""
            # 处理None
            if obj is None:
                return None
            
            # 处理基本类型
            if isinstance(obj, (str, int, float, bool)):
                return obj
            
            # 处理枚举类型
            if hasattr(obj, 'value'):
                return obj.value
            
            # 处理Pydantic模型
            if hasattr(obj, 'model_dump'):
                try:
                    return obj.model_dump()
                except:
                    pass
            if hasattr(obj, 'dict'):
                try:
                    return obj.dict()
                except:
                    pass
            
            # 处理字典
            if isinstance(obj, dict):
                return {k: serialize_pydantic(v) for k, v in obj.items()}
            
            # 处理列表
            if isinstance(obj, list):
                return [serialize_pydantic(item) for item in obj]
            
            # 处理元组
            if isinstance(obj, tuple):
                return tuple(serialize_pydantic(item) for item in obj)
            
            # 对于其他类型，尝试转换为字符串
            try:
                return str(obj)
            except:
                return None
        
        # 构建响应（兼容原有格式，同时支持新格式）
        # 先序列化result，确保所有Pydantic对象都被转换
        try:
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump()
            elif hasattr(result, 'dict'):
                result_dict = result.dict()
            else:
                result_dict = serialize_pydantic(result)
        except Exception as e:
            logger.warning(f"序列化result失败，使用备用方法: {str(e)}")
            result_dict = {
                "source_cards": result.source_cards if hasattr(result, 'source_cards') else [],
                "synthesis_insight": serialize_pydantic(result.synthesis_insight) if hasattr(result, 'synthesis_insight') else {},
                "new_views": [],
                "card_analysis": serialize_pydantic(result.card_analysis) if hasattr(result, 'card_analysis') else {}
            }
        
        # 构建new_views列表，确保数据格式正确
        logger.info(f"📊 开始处理 {len(result.new_views)} 个新视图")
        new_views_list = []
        for view in result.new_views:
            try:
                # 序列化visualization_response
                viz_data = serialize_pydantic(view.visualization_response) if hasattr(view, 'visualization_response') else {}
                
                # 确保viz_data有正确的结构
                if not isinstance(viz_data, dict):
                    viz_data = {}
                
                # 设置has_visualization标志
                if viz_data:
                    viz_data['has_visualization'] = True
                    # 确定visualization_type
                    if 'chart_config' in viz_data and viz_data['chart_config']:
                        viz_data['visualization_type'] = 'plotly'
                    elif 'timeline_data' in viz_data:
                        viz_data['visualization_type'] = 'timeline'
                    elif 'table' in viz_data:
                        viz_data['visualization_type'] = 'table'
                    else:
                        viz_data['visualization_type'] = 'plotly'  # 默认
                else:
                    viz_data['has_visualization'] = False
                
                # 确保chart_config被正确序列化
                if isinstance(viz_data, dict) and 'chart_config' in viz_data:
                    if viz_data['chart_config'] and not isinstance(viz_data['chart_config'], dict):
                        viz_data['chart_config'] = serialize_pydantic(viz_data['chart_config'])
                
                # 提取洞察信息（从synthesis_insight或view中）
                insight_data = None
                if hasattr(result, 'synthesis_insight') and result.synthesis_insight:
                    synthesis_insight = serialize_pydantic(result.synthesis_insight)
                    insight_data = {
                        "conclusion": synthesis_insight.get("conclusion", ""),
                        "key_findings": synthesis_insight.get("key_findings", []),
                        "confidence": synthesis_insight.get("confidence", "medium")
                    }
                # 如果综合洞察为空，尝试从视图洞察中提取一句结论
                if (not insight_data or not insight_data.get("conclusion")) and isinstance(viz_data, dict):
                    viz_insights = viz_data.get("insights", [])
                    if isinstance(viz_insights, list) and viz_insights:
                        first_desc = str(viz_insights[0].get("description", "")).strip() if isinstance(viz_insights[0], dict) else ""
                        if first_desc:
                            insight_data = {
                                "conclusion": first_desc,
                                "key_findings": [],
                                "confidence": "medium"
                            }
                
                new_views_list.append({
                    "view_id": view.view_id if hasattr(view, 'view_id') else f"view_{len(new_views_list)}",
                    "view_type": view.view_type if hasattr(view, 'view_type') else "verify",
                    "visualization": viz_data,
                    "description": view.description if hasattr(view, 'description') else "",
                    "data_quality": view.data_validation.get("data_quality") if hasattr(view, 'data_validation') and isinstance(view.data_validation, dict) else "unknown",
                    "related_cards": view.related_cards if hasattr(view, 'related_cards') else [],
                    "insight": insight_data  # ⭐新增：洞察信息
                })
                logger.info(f"✅ 成功添加视图: {view.view_id if hasattr(view, 'view_id') else 'unknown'}, has_visualization={viz_data.get('has_visualization', False)}")
            except Exception as e:
                logger.warning(f"序列化视图失败，跳过: {str(e)}")
                import traceback
                logger.warning(f"详细错误: {traceback.format_exc()}")
                continue
        
        logger.info(f"📊 最终生成 {len(new_views_list)} 个新视图（原始: {len(result.new_views)}）")
        
        response_data = {
            "status": "success",
            "linkage_result": result_dict,
            "new_views": new_views_list,
            "synthesis_insight": serialize_pydantic(result.synthesis_insight) if hasattr(result, 'synthesis_insight') else {},
            "card_analysis": serialize_pydantic(result.card_analysis) if hasattr(result, 'card_analysis') else {}
        }
        
        # 兼容原有格式：如果只有一个视图，可以作为visualization返回
        if len(result.new_views) == 1:
            view = result.new_views[0]
            if view.visualization_response and view.visualization_response.chart_config:
                chart_config_dict = serialize_pydantic(view.visualization_response.chart_config) if view.visualization_response.chart_config else None
                response_data["visualization"] = {
                    "has_visualization": True,
                    "chart_config": chart_config_dict,
                    "analysis_text": view.visualization_response.answer if hasattr(view.visualization_response, 'answer') else ""
                }
        
        logger.info(f"✅ 综合视图分析生成成功，生成了{len(result.new_views)}个新视图")
        
        return JSONResponse(
            status_code=200,
            content=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成综合视图分析失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        
        # 降级：尝试使用原有的雷达图生成（如果可能）
        try:
            logger.info("尝试使用原有方法生成雷达图作为降级方案...")
            # 这里可以调用原有的逻辑作为降级
            raise HTTPException(
                status_code=500,
                detail=f"生成综合视图分析失败: {str(e)}"
            )
        except:
            raise HTTPException(
                status_code=500,
                detail=f"生成综合视图分析失败: {str(e)}"
            )


# ==================== 综合能力分析辅助函数 ====================

async def _extract_core_metrics(rag_engine, existing_metrics: Dict, context_filter: Optional[Dict] = None, overview_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    提取4个核心指标（已取消偿债能力）
    
    Returns:
        {
            'roe': {'value': 10.5, 'unit': '%', 'source': 'existing'},
            'asset_turnover': {'value': 0.8, 'unit': '', 'source': 'retrieved'},
            'revenue_growth': {'value': 15.2, 'unit': '%', 'source': 'retrieved'},
            'cash_profit_ratio': {'value': 1.1, 'unit': '', 'source': 'retrieved'}
        }
    """
    metrics = {}
    
    # 1. ROE - 盈利能力（优先使用文档披露值，缺失则计算）
    roe_value = None
    roe_source = None
    
    # 优先级1: 从文档检索（加权平均净资产收益率/ROE/净资产收益率）
    roe_value = await _retrieve_metric(rag_engine, "加权平均净资产收益率 ROE 净资产收益率", context_filter)
    if roe_value is not None:
        roe_source = 'document'
        logger.info(f"✅ 从文档检索ROE: {roe_value}%")
    else:
        logger.info("❌ 未从文档检索到ROE，尝试计算ROE")
    
    # 优先级2: 文档缺失时尝试计算（净利润 / 股东权益）
    if roe_value is None:
        net_profit_for_roe = await _retrieve_metric(
            rag_engine,
            "净利润 归属于母公司所有者的净利润 归母净利润",
            context_filter
        )
        equity_for_roe = await _retrieve_metric(
            rag_engine,
            "股东权益 所有者权益 归属于母公司所有者权益",
            context_filter
        )
        
        if net_profit_for_roe is not None and equity_for_roe is not None and equity_for_roe != 0:
            roe_value = (net_profit_for_roe / equity_for_roe) * 100
            roe_source = 'calculated'
            logger.info(
                f"✅ 计算ROE: {roe_value:.2f}% (净利润: {net_profit_for_roe}, 股东权益: {equity_for_roe})"
            )
        else:
            logger.warning(
                f"❌ 无法计算ROE（净利润: {net_profit_for_roe}, 股东权益: {equity_for_roe}）"
            )
    
    # 兜底：如果仍缺失，尝试财务概况或已有卡片
    if roe_value is None and overview_data and overview_data.get('roe'):
        roe_obj = overview_data['roe']
        if isinstance(roe_obj, dict) and not roe_obj.get('is_missing'):
            roe_value_str = roe_obj.get('value', '')
            if roe_value_str and roe_value_str != '—':
                roe_value = _parse_metric_value(roe_value_str)
                roe_source = 'overview'
                logger.info(f"✅ 从财务概况获取ROE: {roe_value}%")
    
    if roe_value is None and 'roe' in existing_metrics:
        roe_value = _extract_value_from_card(existing_metrics['roe'], ['ROE', '净资产收益率', '加权平均净资产收益率'])
        if roe_value is not None:
            roe_source = 'existing_card'
            logger.info(f"✅ 从已有卡片获取ROE: {roe_value}%")
    
    metrics['roe'] = {'value': roe_value, 'unit': '%', 'source': roe_source}
    print(f"📊 [指标提取] ROE: {roe_value}% (来源: {roe_source})")
    
    # 2. 总资产周转率 - 运营能力
    asset_turnover = await _retrieve_metric(rag_engine, "总资产周转率 资产周转率", context_filter)
    metrics['asset_turnover'] = {'value': asset_turnover, 'unit': '', 'source': 'retrieved'}
    print(f"📊 [指标提取] 总资产周转率: {asset_turnover} (来源: retrieved)")
    
    # 3. 营业收入同比增长率 - 成长能力
    revenue_growth = None
    revenue_growth_source = None
    
    # 优先级1: 直接检索同比增长率
    revenue_growth = await _retrieve_metric(rag_engine, "营业收入同比增长率 营业收入增长率 同比 增长", context_filter)
    if revenue_growth is not None:
        revenue_growth_source = 'retrieved_direct'
        logger.info(f"✅ 直接检索到营业收入同比增长率: {revenue_growth}%")
        print(f"📊 [指标提取] 营业收入同比增长率: {revenue_growth}% (来源: 直接检索)")
    else:
        # 优先级2: 从财务概况获取当前年营业收入，然后检索上一年营业收入计算增长率
        current_revenue = None
        previous_revenue = None
        
        # 从财务概况获取当前年营业收入
        if overview_data and overview_data.get('revenue'):
            revenue_obj = overview_data['revenue']
            if isinstance(revenue_obj, dict) and not revenue_obj.get('is_missing'):
                revenue_value_str = revenue_obj.get('value', '')
                if revenue_value_str and revenue_value_str != '—':
                    current_revenue = _parse_metric_value(revenue_value_str)
                    logger.info(f"✅ 从财务概况获取当前年营业收入: {current_revenue}")
                    print(f"   📊 当前年营业收入: {current_revenue}")
        
        # 如果还没有当前年数据，检索当前年营业收入
        if current_revenue is None:
            current_revenue = await _retrieve_metric(rag_engine, "营业收入 营业总收入 最新年度 本年", context_filter)
            if current_revenue:
                logger.info(f"✅ 检索到当前年营业收入: {current_revenue}")
                print(f"   📊 当前年营业收入: {current_revenue}")
        
        # 检索上一年营业收入
        if current_revenue is not None:
            # 尝试多种方式检索上一年数据
            previous_revenue = None
            
            # 方式1: 直接检索上一年
            previous_revenue = await _retrieve_metric(rag_engine, "营业收入 营业总收入 上一年 去年 前一年 上年", context_filter)
            
            # 方式2: 如果方式1失败，尝试从表格中提取（通常利润表会有多列数据）
            if previous_revenue is None:
                # 构建查询，要求返回两年的数据
                growth_query = "营业收入 营业总收入 利润表 最近两年 历史数据"
                if context_filter:
                    growth_result = rag_engine.query(growth_query, context_filter)
                    growth_answer = growth_result.get('answer', '')
                    growth_sources = growth_result.get('sources', [])
                else:
                    growth_response = rag_engine.query_engine.query(growth_query)
                    growth_answer = str(growth_response)
                    growth_sources = []
                
                # 从回答或来源中提取两年的数据
                # 查找所有营业收入数值，取第二大的作为上一年（假设最大的当前年）
                import re
                all_revenue_values = []
                
                # 从sources中提取
                for source in growth_sources:
                    if isinstance(source, dict):
                        source_text = source.get('text', '')
                        # 查找包含营业收入的行
                        for line in source_text.split('\n'):
                            if '营业收入' in line or '营业总收入' in line:
                                # 提取所有数值
                                numbers = re.findall(r'([-+]?\d+[,，]?\d*\.?\d*)', line)
                                for num_str in numbers:
                                    try:
                                        num = float(num_str.replace(',', '').replace('，', ''))
                                        if not (2000 <= abs(num) <= 2030) and abs(num) > 0.01:
                                            all_revenue_values.append(num)
                                    except:
                                        pass
                
                # 从回答中提取
                numbers = re.findall(r'([-+]?\d+[,，]?\d*\.?\d*)\s*[万千百十亿]?元', growth_answer)
                for num_str in numbers:
                    try:
                        num = float(num_str.replace(',', '').replace('，', ''))
                        if not (2000 <= abs(num) <= 2030) and abs(num) > 0.01:
                            all_revenue_values.append(num)
                    except:
                        pass
                
                if len(all_revenue_values) >= 2:
                    # 排序，取第二大的作为上一年
                    all_revenue_values = sorted([abs(v) for v in all_revenue_values], reverse=True)
                    # 假设当前年营业收入是最大的，上一年是第二大的
                    if abs(current_revenue) == all_revenue_values[0]:
                        previous_revenue = all_revenue_values[1] if len(all_revenue_values) > 1 else None
                    else:
                        # 如果当前年不是最大的，取第二大的
                        previous_revenue = all_revenue_values[1] if len(all_revenue_values) > 1 else all_revenue_values[0]
                    
                    if previous_revenue:
                        logger.info(f"✅ 从历史数据中提取到上一年营业收入: {previous_revenue}")
                        print(f"   📊 上一年营业收入: {previous_revenue} (从历史数据提取)")
            
            if previous_revenue is not None and previous_revenue != 0:
                # 计算同比增长率
                revenue_growth = ((current_revenue - previous_revenue) / previous_revenue) * 100
                revenue_growth_source = 'calculated'
                logger.info(f"✅ 计算营业收入同比增长率: {revenue_growth:.2f}% (当前: {current_revenue}, 上年: {previous_revenue})")
                print(f"📊 [指标提取] 营业收入同比增长率: {revenue_growth:.2f}% (来源: 计算)")
                print(f"   详细: 当前年={current_revenue}, 上一年={previous_revenue}, 增长率={revenue_growth:.2f}%")
            else:
                logger.warning(f"❌ 无法获取上一年营业收入，无法计算增长率")
                print(f"   ⚠️ 无法获取上一年营业收入，无法计算增长率")
        else:
            logger.warning(f"❌ 无法获取当前年营业收入")
            print(f"   ⚠️ 无法获取当前年营业收入")
    
    metrics['revenue_growth'] = {'value': revenue_growth, 'unit': '%', 'source': revenue_growth_source or 'missing'}
    if revenue_growth is None:
        print(f"📊 [指标提取] 营业收入同比增长率: 缺失")
    
    # 4. 经营活动现金流/净利润 - 现金能力
    # 优先从财务概况获取净利润
    net_profit = None
    net_profit_source = None
    
    if overview_data and overview_data.get('net_profit'):
        net_profit_obj = overview_data['net_profit']
        if isinstance(net_profit_obj, dict) and not net_profit_obj.get('is_missing'):
            net_profit_str = net_profit_obj.get('value', '')
            if net_profit_str and net_profit_str != '—':
                net_profit = _parse_metric_value(net_profit_str)
                net_profit_source = 'overview'
                logger.info(f"✅ 从财务概况获取净利润: {net_profit}")
                print(f"   📊 净利润: {net_profit} (来源: 财务概况)")
    
    if net_profit is None:
        net_profit = await _retrieve_metric(rag_engine, "净利润 归属于母公司所有者的净利润 归母净利润", context_filter)
        net_profit_source = 'retrieved'
        logger.info(f"{'✅' if net_profit else '❌'} 从文档检索净利润: {net_profit}")
        if net_profit:
            print(f"   📊 净利润: {net_profit} (来源: 文档检索)")
        else:
            print(f"   ❌ 净利润检索失败")
    
    # 经营活动现金流 - 使用多个关键词组合检索
    cash_flow = None
    cash_flow_source = None
    
    # 尝试多个查询策略
    cash_flow_queries = [
        "经营活动产生的现金流量净额",
        "经营活动现金流 经营活动产生的现金流量",
        "现金流量表 经营活动 现金流量净额",
        "现金流量净额 经营活动"
    ]
    
    for query in cash_flow_queries:
        cash_flow = await _retrieve_metric(rag_engine, query, context_filter)
        if cash_flow is not None:
            cash_flow_source = 'retrieved'
            logger.info(f"✅ 检索到经营活动现金流: {cash_flow} (查询: {query})")
            print(f"📊 [指标提取] 经营活动现金流: {cash_flow} (来源: 文档检索, 查询: {query})")
            break
    
    if cash_flow is None:
        logger.warning(f"❌ 所有查询策略都未能检索到经营活动现金流")
        print(f"📊 [指标提取] 经营活动现金流: 缺失 (所有查询策略都失败)")
        print(f"   ⚠️ 请检查文档中是否包含以下关键词之一:")
        print(f"      - 经营活动产生的现金流量净额")
        print(f"      - 经营活动现金流")
        print(f"      - 经营活动产生的现金流量")
    
    # 计算现金流/净利润比率
    if cash_flow is not None and net_profit is not None and net_profit != 0:
        # 注意：这里假设现金流和净利润的单位已经一致（都是元）
        # 如果单位不一致，需要转换
        cash_ratio = cash_flow / net_profit
        metrics['cash_profit_ratio'] = {'value': cash_ratio, 'unit': '', 'source': 'calculated'}
        print(f"📊 [指标提取] 现金流/净利润: {cash_ratio:.2f} (来源: 计算)")
        print(f"   详细: 现金流={cash_flow}, 净利润={net_profit}, 比率={cash_ratio:.2f}")
    else:
        metrics['cash_profit_ratio'] = {'value': None, 'unit': '', 'source': 'missing'}
        print(f"📊 [指标提取] 现金流/净利润: 缺失")
        if cash_flow is None:
            print(f"   原因: 经营活动现金流检索失败")
        if net_profit is None:
            print(f"   原因: 净利润检索失败")
        elif net_profit == 0:
            print(f"   原因: 净利润为0，无法计算比率")
    
    # 注意：已取消偿债能力维度（资产负债率）
    
    print(f"\n📋 [指标提取汇总]")
    print(f"  - ROE: {metrics['roe']['value']}% (来源: {metrics['roe']['source']})")
    print(f"  - 总资产周转率: {metrics['asset_turnover']['value']} (来源: {metrics['asset_turnover']['source']})")
    print(f"  - 营业收入同比增长率: {metrics['revenue_growth']['value']}% (来源: {metrics['revenue_growth']['source']})")
    print(f"  - 现金流/净利润: {metrics['cash_profit_ratio']['value']} (来源: {metrics['cash_profit_ratio']['source']})")
    
    return metrics


def _parse_metric_value(value_str: str) -> Optional[float]:
    """解析指标值字符串，提取数值"""
    try:
        if not value_str or value_str == '—':
            return None
        # 移除所有非数字字符（保留小数点和负号）
        import re
        # 匹配数字（包括小数和百分比）
        match = re.search(r'([-+]?\d+\.?\d*)', str(value_str).replace(',', '').replace('，', ''))
        if match:
            return float(match.group(1))
        return None
    except Exception as e:
        logger.warning(f"解析指标值失败 {value_str}: {str(e)}")
        return None


def _extract_value_from_card(card: Dict, keywords: List[str]) -> Optional[float]:
    """从已有卡片中提取指标值"""
    try:
        # 检查卡片数据
        card_data = card.get('data', {})
        question = card.get('question', '')
        
        # 尝试从图表配置中提取
        if card_data.get('chart_config'):
            chart_config = card_data['chart_config']
            # 从traces中提取数值
            for trace in chart_config.get('traces', []):
                if trace.get('y'):
                    values = trace['y']
                    if values and len(values) > 0:
                        # 取第一个值
                        return float(values[0])
        
        # 尝试从问题文本中提取
        for keyword in keywords:
            if keyword in question:
                # 在问题中查找数值
                percent_match = re.search(r'([\d,\.]+)\s*%', question)
                if percent_match:
                    return float(percent_match.group(1).replace(',', ''))
                number_match = re.search(r'([\d,\.]+)', question)
                if number_match:
                    return float(number_match.group(1).replace(',', ''))
        
        return None
    except Exception as e:
        logger.warning(f"从卡片提取值失败: {str(e)}")
        return None


async def _retrieve_metric(rag_engine, query_keywords: str, context_filter: Optional[Dict] = None) -> Optional[float]:
    """从文档中检索指标值（优化版，支持从表格和文本中提取）"""
    try:
        # 构建更明确的查询问题
        query_question = f"{query_keywords}的具体数值是多少？请给出准确的数值和单位"
        
        if context_filter:
            result = rag_engine.query(query_question, context_filter)
            answer = result.get('answer', '')
            sources = result.get('sources', [])
        else:
            response = rag_engine.query_engine.query(query_question)
            answer = str(response)
            sources = []
        
        logger.info(f"🔍 检索指标 '{query_keywords}' - 回答长度: {len(answer)} 字符")
        print(f"🔍 [检索指标] {query_keywords}")
        print(f"   回答预览: {answer[:300]}...")
        
        if sources:
            logger.info(f"🔍 来源数量: {len(sources)}")
            print(f"   来源数量: {len(sources)}")
            # 记录来源预览
            for i, source in enumerate(sources[:2]):
                if isinstance(source, dict):
                    source_text = source.get('text', '')[:200]
                    metadata = source.get('metadata', {})
                    doc_type = metadata.get('document_type', 'unknown')
                    print(f"   来源{i+1} ({doc_type}): {source_text}...")
        
        # 优先从sources中提取（特别是表格数据）
        if sources:
            for source in sources:
                if isinstance(source, dict):
                    source_text = source.get('text', '')
                    metadata = source.get('metadata', {})
                    # 检查是否是表格数据
                    is_table = metadata.get('document_type') == 'table_data' or 'table' in str(metadata).lower()
                    
                    # 对于经营现金流，特别关注包含相关关键词的来源
                    keywords_in_text = any(kw in source_text for kw in ['经营活动', '现金流量', '现金流', '现金流量净额'])
                    
                    # 检查是否包含查询关键词
                    query_keywords_list = query_keywords.split()
                    has_query_keywords = any(kw in source_text for kw in query_keywords_list)
                    
                    if is_table or keywords_in_text or has_query_keywords:
                        # 从表格文本中提取数值
                        # 查找包含关键词的行
                        lines = source_text.split('\n')
                        for line in lines:
                            # 检查这一行是否包含查询关键词
                            line_has_keywords = any(kw in line for kw in query_keywords_list) or \
                                               any(kw in line for kw in ['经营活动', '现金流量', '现金流', '营业收入', '收入', '同比', '增长'])
                            
                            if line_has_keywords:
                                # 尝试从这一行提取数值
                                # 匹配各种格式：数字、带单位的数字等
                                
                                # 对于表格格式：| 指标名 | 2024年 | 2023年 | 数值 |
                                # 提取所有数值，选择最大的（通常是主要指标值）
                                table_patterns = [
                                    r'[|]\s*([-+]?\d+[,，]?\d*\.?\d*)\s*[|]',  # 表格格式：| 数值 |
                                    r'[|]\s*([-+]?\d+[,，]?\d*\.?\d*)\s*[万千百十亿]?元',  # 表格格式：| 数值元 |
                                ]
                                
                                # 对于文本格式
                                text_patterns = [
                                    r'([-+]?\d+[,，]?\d*\.?\d*)\s*[万千百十亿]元',  # 带单位的金额
                                    r'([-+]?\d+[,，]?\d*\.?\d*)\s*%',  # 百分比
                                    r'([-+]?\d+[,，]?\d*\.?\d*)',  # 纯数字
                                ]
                                
                                all_patterns = table_patterns + text_patterns
                                
                                for pattern in all_patterns:
                                    matches = re.findall(pattern, line)
                                    if matches:
                                        # 提取所有数值
                                        values = []
                                        for m in matches:
                                            try:
                                                v_str = m.replace(',', '').replace('，', '')
                                                v = float(v_str)
                                                # 排除年份、页码等
                                                if not (2000 <= abs(v) <= 2030) and abs(v) > 0.01:
                                                    values.append(v)
                                            except:
                                                pass
                                        
                                        if values:
                                            # 取绝对值最大的数值（通常是主要指标值）
                                            max_value = max([abs(v) for v in values])
                                            # 恢复符号
                                            for v in values:
                                                if abs(v) == max_value:
                                                    logger.info(f"✅ 从表格来源提取到数值: {v} (行: {line[:100]}...)")
                                                    print(f"   ✅ 从表格提取: {v} (匹配行: {line[:80]}...)")
                                                    return v
        
        # 从回答中提取数值
        # 匹配带单位的金额：如 "1,234,567万元"、"123.45亿元"
        amount_patterns = [
            r'([-+]?\d+[,，]?\d*\.?\d*)\s*([万千百十亿]元)',  # 带单位的金额
            r'([-+]?\d+[,，]?\d*\.?\d*)\s*元',  # 带"元"的金额
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, answer)
            if match:
                value_str = match.group(1).replace(',', '').replace('，', '')
                unit = match.group(2) if len(match.groups()) > 1 else ''
                value = float(value_str)
                # 单位转换
                if '亿' in unit:
                    value = value * 100000000
                elif '万' in unit:
                    value = value * 10000
                elif '千' in unit:
                    value = value * 1000
                logger.info(f"✅ 从回答中提取到数值（带单位）: {value} ({unit})")
                print(f"   ✅ 从回答提取（带单位）: {value} ({unit})")
                return value
        
        # 匹配百分比：10.5%、10.5
        percent_match = re.search(r'([-+]?\d+[,，]?\.?\d*)\s*%', answer)
        if percent_match:
            value_str = percent_match.group(1).replace(',', '').replace('，', '')
            logger.info(f"✅ 从回答中提取到百分比: {value_str}%")
            print(f"   ✅ 从回答提取（百分比）: {value_str}%")
            return float(value_str)
        
        # 匹配普通数值（取最大的数值，通常是主要指标值）
        number_matches = re.findall(r'([-+]?\d+[,，]?\d*\.?\d*)', answer)
        if number_matches:
            # 过滤掉明显不是指标值的数字（如年份、页码等）
            values = []
            for match in number_matches:
                value_str = match.replace(',', '').replace('，', '')
                try:
                    v = float(value_str)
                    # 排除年份（2000-2030）、页码等
                    if not (2000 <= abs(v) <= 2030) and abs(v) > 0.01:
                        values.append(v)
                except:
                    pass
            
            if values:
                # 取绝对值最大的（通常是主要指标值）
                max_value = max([abs(v) for v in values])
                for v in values:
                    if abs(v) == max_value:
                        logger.info(f"✅ 从回答中提取到数值: {v}")
                        print(f"   ✅ 从回答提取: {v}")
                        return v
        
        logger.warning(f"❌ 未能从回答中提取到数值: {answer[:200]}...")
        print(f"   ❌ 未能提取数值")
        return None
    except Exception as e:
        logger.warning(f"检索指标失败 {query_keywords}: {str(e)}")
        import traceback
        logger.warning(f"详细错误: {traceback.format_exc()}")
        print(f"   ❌ 检索失败: {str(e)}")
        return None


def _calculate_ability_scores(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据指标值计算能力评分（0-100分）
    
    Returns:
        {
            'profitability': {'score': 75, 'level': '中高'},
            'operation': {'score': 60, 'level': '正常'},
            'growth': {'score': 80, 'level': '高成长'},
            'cash': {'score': 70, 'level': '基本匹配'},
            'debt': {'score': 65, 'level': '合理'}
        }
    """
    scores = {}
    
    # 1. 盈利能力 - ROE
    roe_value = metrics.get('roe', {}).get('value')
    if roe_value is not None:
        if roe_value >= 15:
            score = 80 + min(20, (roe_value - 15) * 2)  # 15-25% 映射到 80-100
        elif roe_value >= 10:
            score = 60 + (roe_value - 10) * 4  # 10-15% 映射到 60-80
        elif roe_value >= 5:
            score = 40 + (roe_value - 5) * 4  # 5-10% 映射到 40-60
        else:
            score = max(0, 40 * (roe_value / 5))  # 0-5% 映射到 0-40
        scores['profitability'] = {'score': min(100, max(0, score)), 'value': roe_value}
    else:
        scores['profitability'] = {'score': 50, 'value': None}  # 缺失数据设为中性值
    
    # 2. 运营能力 - 总资产周转率
    turnover_value = metrics.get('asset_turnover', {}).get('value')
    if turnover_value is not None:
        if turnover_value >= 1.2:
            score = 80 + min(20, (turnover_value - 1.2) * 25)  # ≥1.2 映射到 80-100
        elif turnover_value >= 0.8:
            score = 60 + (turnover_value - 0.8) * 50  # 0.8-1.2 映射到 60-80
        elif turnover_value >= 0.5:
            score = 40 + (turnover_value - 0.5) * 66.67  # 0.5-0.8 映射到 40-60
        else:
            score = max(0, 40 * (turnover_value / 0.5))  # <0.5 映射到 0-40
        scores['operation'] = {'score': min(100, max(0, score)), 'value': turnover_value}
    else:
        scores['operation'] = {'score': 50, 'value': None}
    
    # 3. 成长能力 - 营业收入同比增长率
    growth_value = metrics.get('revenue_growth', {}).get('value')
    if growth_value is not None:
        if growth_value >= 20:
            score = 80 + min(20, (growth_value - 20) * 1)  # ≥20% 映射到 80-100
        elif growth_value >= 10:
            score = 60 + (growth_value - 10) * 2  # 10-20% 映射到 60-80
        elif growth_value >= 0:
            score = 40 + growth_value * 2  # 0-10% 映射到 40-60
        else:
            score = max(0, 40 + growth_value * 4)  # 负增长 映射到 0-40
        scores['growth'] = {'score': min(100, max(0, score)), 'value': growth_value}
    else:
        scores['growth'] = {'score': 50, 'value': None}
    
    # 4. 现金能力 - 经营活动现金流/净利润
    cash_ratio_value = metrics.get('cash_profit_ratio', {}).get('value')
    if cash_ratio_value is not None:
        if cash_ratio_value >= 1.2:
            score = 80 + min(20, (cash_ratio_value - 1.2) * 50)  # ≥1.2 映射到 80-100
        elif cash_ratio_value >= 0.8:
            score = 60 + (cash_ratio_value - 0.8) * 50  # 0.8-1.2 映射到 60-80
        elif cash_ratio_value >= 0.5:
            score = 40 + (cash_ratio_value - 0.5) * 66.67  # 0.5-0.8 映射到 40-60
        else:
            score = max(0, 40 * (cash_ratio_value / 0.5))  # <0.5 映射到 0-40
        scores['cash'] = {'score': min(100, max(0, score)), 'value': cash_ratio_value}
    else:
        scores['cash'] = {'score': 50, 'value': None}
    
    # 注意：已取消偿债能力维度
    
    return scores


def _generate_radar_chart(scores: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    生成雷达图配置（Plotly格式）
    """
    # 能力维度标签（已取消偿债能力）
    categories = ['盈利能力', '运营能力', '成长能力', '现金能力']
    
    # 获取各维度分数
    values = [
        scores.get('profitability', {}).get('score', 50),
        scores.get('operation', {}).get('score', 50),
        scores.get('growth', {}).get('score', 50),
        scores.get('cash', {}).get('score', 50)
    ]
    
    # 为了闭合雷达图，需要重复第一个值
    categories_closed = categories + [categories[0]]
    values_closed = values + [values[0]]
    
    # 构建Plotly雷达图配置
    chart_config = {
        "chart_type": "radar",
        "traces": [
            {
                "name": "综合能力",
                "type": "scatterpolar",
                "r": values_closed,
                "theta": categories_closed,
                "fill": "toself",
                "mode": "lines+markers",
                "line": {"color": "rgb(55, 128, 191)", "width": 2},
                "marker": {"size": 8, "color": "rgb(55, 128, 191)"}
            }
        ],
        "layout": {
            "title": "综合能力分析雷达图",
            "polar": {
                "radialaxis": {
                    "visible": True,
                    "range": [0, 100],
                    "tickmode": "linear",
                    "tick0": 0,
                    "dtick": 20,
                    "tickvals": [0, 20, 40, 60, 80, 100],
                    "ticktext": ["0", "20", "40", "60", "80", "100"],
                    "gridcolor": "#e0e0e0",
                    "linecolor": "#999"
                },
                "angularaxis": {
                    "rotation": 90,
                    "direction": "counterclockwise"
                }
            },
            "height": 500,
            "showlegend": False,
            "template": "plotly_white"
        }
    }
    
    return chart_config


def _generate_ability_analysis(scores: Dict[str, Any], metrics: Dict[str, Any]) -> str:
    """
    生成能力分析文本
    """
    # 计算平均分（已取消偿债能力）
    avg_score = sum([
        scores.get('profitability', {}).get('score', 50),
        scores.get('operation', {}).get('score', 50),
        scores.get('growth', {}).get('score', 50),
        scores.get('cash', {}).get('score', 50)
    ]) / 4
    
    # 根据平均分确定整体评价
    if avg_score >= 80:
        overall = "能力表现较强"
    elif avg_score >= 60:
        overall = "能力保持稳定"
    elif avg_score >= 40:
        overall = "能力承压"
    else:
        overall = "能力风险较高"
    
    analysis = f"**综合能力评价：{overall}**\n\n"
    
    # 各维度一句话分析
    profitability_score = scores.get('profitability', {}).get('score', 50)
    if profitability_score >= 80:
        profitability_desc = "盈利能力突出"
    elif profitability_score >= 60:
        profitability_desc = "盈利能力良好"
    elif profitability_score >= 40:
        profitability_desc = "盈利能力一般"
    else:
        profitability_desc = "盈利能力偏弱"
    analysis += f"- **盈利能力**：{profitability_desc}\n"
    
    operation_score = scores.get('operation', {}).get('score', 50)
    if operation_score >= 80:
        operation_desc = "运营效率较高"
    elif operation_score >= 60:
        operation_desc = "运营效率正常"
    elif operation_score >= 40:
        operation_desc = "运营效率偏低"
    else:
        operation_desc = "运营效率较弱"
    analysis += f"- **运营能力**：{operation_desc}\n"
    
    growth_score = scores.get('growth', {}).get('score', 50)
    if growth_score >= 80:
        growth_desc = "成长能力强劲"
    elif growth_score >= 60:
        growth_desc = "成长能力稳健"
    elif growth_score >= 40:
        growth_desc = "成长能力放缓"
    else:
        growth_desc = "成长能力承压"
    analysis += f"- **成长能力**：{growth_desc}\n"
    
    cash_score = scores.get('cash', {}).get('score', 50)
    if cash_score >= 80:
        cash_desc = "现金质量优秀"
    elif cash_score >= 60:
        cash_desc = "现金质量良好"
    elif cash_score >= 40:
        cash_desc = "现金质量一般"
    else:
        cash_desc = "现金质量存在风险"
    analysis += f"- **现金能力**：{cash_desc}\n"
    
    return analysis
