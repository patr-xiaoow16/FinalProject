"""
文档处理API接口
"""

from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

from core.document_processor import DocumentProcessor
from core.table_extractor import TableExtractor
from core.rag_engine import RAGEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/process", tags=["process"])

# 全局处理器实例（延迟初始化）
document_processor = None
table_extractor = None
rag_engine = None

def get_processors():
    """获取处理器实例（延迟初始化）"""
    global document_processor, table_extractor, rag_engine

    if document_processor is None:
        document_processor = DocumentProcessor()
    if table_extractor is None:
        table_extractor = TableExtractor()
    if rag_engine is None:
        rag_engine = RAGEngine()

    return document_processor, table_extractor, rag_engine

class ProcessRequest(BaseModel):
    filename: str
    build_index: bool = True

class ProcessMultipleRequest(BaseModel):
    filenames: list[str]
    build_index: bool = True

@router.post("/file")
async def process_file(request: ProcessRequest):
    """
    处理单个文件
    
    Args:
        request: 处理请求
        
    Returns:
        处理结果
    """
    try:
        # 获取处理器实例
        document_processor, table_extractor, rag_engine = get_processors()

        filename = request.filename
        build_index = request.build_index

        # 检查文件是否存在
        file_path = Path("uploads") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")

        # 验证文件
        if not document_processor.validate_file(str(file_path)):
            raise HTTPException(status_code=400, detail=f"文件验证失败: {filename}")

        logger.info(f"开始处理文件: {filename}")

        # 处理文档
        doc_result = document_processor.process_file(str(file_path), filename)

        # 提取表格
        processed_docs = {filename: doc_result}
        extracted_tables = table_extractor.extract_tables(processed_docs)
        
        # 构建索引（如果需要，默认使用增量模式）
        index_built = False
        if build_index:
            try:
                logger.info("🔨 开始构建索引（增量模式）...")
                logger.info(f"   文档数: {len(processed_docs)}")
                logger.info(f"   表格数: {sum(len(tables) for tables in extracted_tables.values())}")
                
                # 默认使用增量模式，只索引新文件，保留已有索引
                index_built = rag_engine.build_index(processed_docs, extracted_tables, incremental=True)
                
                if index_built:
                    index_stats = rag_engine.get_index_stats()
                    logger.info(f"✅ 索引构建成功!")
                    logger.info(f"   状态: {index_stats.get('status', 'unknown')}")
                    logger.info(f"   文档数: {index_stats.get('document_count', 0)}")
                    logger.info(f"   向量数: {index_stats.get('vector_count', 0)}")
                    logger.info(f"   存储目录: {index_stats.get('storage_dir', 'unknown')}")
                else:
                    logger.error("❌ 索引构建失败: build_index 返回 False")
                    logger.error("   请检查日志以获取详细信息")
            except Exception as e:
                logger.error(f"❌ 索引构建异常: {str(e)}", exc_info=True)
                # 不抛出异常，但记录详细错误
        
        # 生成处理摘要
        doc_summary = document_processor.get_document_summary(doc_result.get('documents', []))
        table_stats = table_extractor.get_table_statistics(extracted_tables)

        # 将Document对象转换为可序列化的字典
        serializable_doc_result = {
            'filename': doc_result['filename'],
            'documents': [
                {
                    'doc_id': doc.doc_id if hasattr(doc, 'doc_id') else None,
                    'text': doc.text[:500] + "..." if len(doc.text) > 500 else doc.text,  # 截断长文本
                    'metadata': doc.metadata if hasattr(doc, 'metadata') else {},
                    'text_length': len(doc.text) if hasattr(doc, 'text') else 0
                } for doc in doc_result.get('documents', [])
            ],
            'page_count': doc_result.get('page_count', 0),
            'total_text_length': doc_result.get('total_text_length', 0),
            'processing_method': doc_result.get('processing_method', 'unknown')
        }
        
        # 只有PDF文件才有detailed_content
        if 'detailed_content' in doc_result:
            serializable_doc_result['detailed_content'] = doc_result['detailed_content']
        
        # Excel文件可能有sheet_count
        if 'sheet_count' in doc_result:
            serializable_doc_result['sheet_count'] = doc_result['sheet_count']

        # 确定page_count（Excel文件使用sheet_count）
        page_count = doc_result.get('page_count', 0)
        if 'sheet_count' in doc_result:
            page_count = doc_result.get('sheet_count', 0)
        
        result = {
            "message": "文件处理完成",
            "filename": filename,
            "processing_summary": {
                "document_info": {
                    "page_count": page_count,
                    "total_text_length": doc_result.get('total_text_length', 0),
                    "processing_method": doc_result.get('processing_method', 'unknown')
                },
                "document_summary": doc_summary,
                "table_info": {
                    "total_tables": table_stats['total_tables'],
                    "financial_tables": table_stats['financial_tables'],
                    "average_importance": table_stats['average_importance']
                },
                "index_info": {
                    "index_built": index_built,
                    "index_stats": rag_engine.get_index_stats() if (index_built and rag_engine) else None
                }
            },
            "detailed_results": {
                "document_data": serializable_doc_result,
                "extracted_tables": extracted_tables[filename] if filename in extracted_tables else []
            }
        }
        
        logger.info(f"文件处理完成: {filename}")
        return JSONResponse(status_code=200, content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理文件失败 {request.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理文件失败: {str(e)}")

@router.post("/files")
async def process_multiple_files(request: ProcessMultipleRequest):
    """
    处理多个文件（支持PDF和Excel）
    
    Args:
        request: 批量处理请求
        
    Returns:
        批量处理结果
    """
    try:
        # 获取处理器实例
        document_processor, table_extractor, rag_engine = get_processors()
        
        filenames = request.filenames
        build_index = request.build_index
        
        if not filenames:
            raise HTTPException(status_code=400, detail="没有指定文件")
        
        if len(filenames) > 10:
            raise HTTPException(status_code=400, detail="一次最多处理10个文件")
        
        logger.info(f"开始批量处理 {len(filenames)} 个文件")
        
        results = []
        all_processed_docs = {}
        all_extracted_tables = {}
        failed_files = []
        
        # 处理每个文件
        for filename in filenames:
            try:
                file_path = Path("uploads") / filename
                if not file_path.exists():
                    error_msg = f"文件不存在: {filename}"
                    results.append({
                        "filename": filename,
                        "status": "error",
                        "message": error_msg
                    })
                    failed_files.append({"filename": filename, "error": error_msg})
                    logger.error(f"文件不存在: {filename}")
                    continue
                
                # 检查文件扩展名
                file_ext = file_path.suffix.lower()
                if file_ext not in {'.pdf', '.xlsx', '.xls'}:
                    error_msg = f"不支持的文件类型: {file_ext}"
                    results.append({
                        "filename": filename,
                        "status": "error",
                        "message": error_msg
                    })
                    failed_files.append({"filename": filename, "error": error_msg})
                    logger.error(f"不支持的文件类型: {file_ext}")
                    continue
                
                # 验证文件（对于PDF和Excel都支持）
                if not document_processor.validate_file(str(file_path)):
                    error_msg = f"文件验证失败: {filename}"
                    results.append({
                        "filename": filename,
                        "status": "error",
                        "message": error_msg
                    })
                    failed_files.append({"filename": filename, "error": error_msg})
                    logger.error(f"文件验证失败: {filename}")
                    continue
                
                logger.info(f"开始处理文件: {filename} (类型: {file_ext})")
                
                # 处理文档（支持PDF和Excel）
                doc_result = document_processor.process_file(str(file_path), filename)
                all_processed_docs[filename] = doc_result
                
                # 提取表格（Excel文件可能已经包含表格数据）
                processed_docs = {filename: doc_result}
                extracted_tables = table_extractor.extract_tables(processed_docs)
                all_extracted_tables.update(extracted_tables)
                
                # 生成摘要
                doc_summary = document_processor.get_document_summary(doc_result.get('documents', []))
                table_stats = table_extractor.get_table_statistics(extracted_tables)
                
                # 对于Excel文件，page_count可能是sheet_count
                page_count = doc_result.get('page_count', 0)
                if file_ext in {'.xlsx', '.xls'}:
                    # Excel文件使用sheet_count
                    page_count = doc_result.get('sheet_count', 0)
                
                results.append({
                    "filename": filename,
                    "status": "success",
                    "summary": {
                        "page_count": page_count,
                        "total_text_length": doc_result.get('total_text_length', 0),
                        "table_count": table_stats['total_tables'],
                        "financial_tables": table_stats['financial_tables']
                    }
                })
                
                logger.info(f"文件处理成功: {filename}")
                
            except Exception as e:
                error_msg = str(e)
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": error_msg
                })
                failed_files.append({"filename": filename, "error": error_msg})
                logger.error(f"处理文件失败 {filename}: {error_msg}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
        
        # 构建统一索引（如果需要，使用增量模式）
        index_built = False
        if build_index and all_processed_docs:
            try:
                logger.info("🔨 开始构建统一索引（增量模式）...")
                logger.info(f"   文档数: {len(all_processed_docs)}")
                logger.info(f"   表格数: {sum(len(tables) for tables in all_extracted_tables.values())}")
                
                # 使用增量模式，只索引新文件，保留已有索引
                index_built = rag_engine.build_index(all_processed_docs, all_extracted_tables, incremental=True)
                
                if index_built:
                    index_stats = rag_engine.get_index_stats()
                    logger.info(f"✅ 统一索引构建成功!")
                    logger.info(f"   状态: {index_stats.get('status', 'unknown')}")
                    logger.info(f"   文档数: {index_stats.get('document_count', 0)}")
                    logger.info(f"   向量数: {index_stats.get('vector_count', 0)}")
                else:
                    logger.warning("⚠️ 统一索引构建失败")
            except Exception as e:
                logger.error(f"统一索引构建失败: {str(e)}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
        
        # 统计结果
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        
        # 生成总体统计
        total_table_stats = table_extractor.get_table_statistics(all_extracted_tables)
        
        # 计算总页数/工作表数
        total_pages = sum(
            r.get("summary", {}).get("page_count", 0) 
            for r in results 
            if r["status"] == "success"
        )
        
        result = {
            "message": f"批量处理完成: {success_count} 成功, {error_count} 失败",
            "total_files": len(results),
            "success_count": success_count,
            "error_count": error_count,
            "processing_summary": {
                "document_info": {
                    "page_count": total_pages,
                    "total_documents": len(all_processed_docs)
                },
                "table_info": {
                    "total_tables": total_table_stats['total_tables'],
                    "financial_tables": total_table_stats['financial_tables']
                },
                "index_info": {
                    "index_built": index_built,
                    "index_stats": rag_engine.get_index_stats() if (index_built and rag_engine) else None
                }
            },
            "file_results": results,
            "failed_files": failed_files
        }
        
        logger.info(f"批量处理完成: {success_count}/{len(filenames)} 成功")
        return JSONResponse(status_code=200, content=result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量处理失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量处理失败: {str(e)}")

@router.get("/status")
async def get_processing_status():
    """
    获取处理状态
    
    Returns:
        当前处理状态
    """
    try:
        # 获取上传文件数量
        upload_dir = Path("uploads")
        uploaded_files = 0
        if upload_dir.exists():
            uploaded_files = len([f for f in upload_dir.iterdir() if f.is_file()])
        
        # 获取索引状态 - 先获取处理器实例
        index_stats = {
            "index_built": False,
            "status": "not_initialized",
            "message": "索引未初始化，请先处理文档"
        }
        try:
            _, _, rag_engine_instance = get_processors()
            if rag_engine_instance:
                stats = rag_engine_instance.get_index_stats()
                if stats:
                    # 统一返回格式
                    if stats.get('status') == 'ready':
                        index_stats = {
                            "index_built": True,
                            "status": "ready",
                            "document_count": stats.get('document_count', 0),
                            "vector_count": stats.get('vector_count', 0),
                            "storage_dir": stats.get('storage_dir', ''),
                            "collection_name": stats.get('collection_name', '')
                        }
                    elif stats.get('status') == 'not_initialized':
                        index_stats = {
                            "index_built": False,
                            "status": "not_initialized",
                            "message": "索引未初始化，请先处理文档"
                        }
                    else:
                        # 兼容旧格式，如果有 index_built 字段
                        index_stats = {
                            "index_built": stats.get('index_built', False),
                            "status": stats.get('status', 'unknown'),
                            **stats
                        }
        except Exception as e:
            logger.warning(f"获取索引状态失败: {str(e)}")
            index_stats = {
                "index_built": False,
                "status": "error",
                "message": f"获取索引状态失败: {str(e)}"
            }
        
        status = {
            "system_status": "ready",
            "uploaded_files": uploaded_files,
            "index_status": index_stats,
            "supported_formats": [".pdf", ".xlsx", ".xls"],
            "max_file_size": "50MB",
            "max_batch_size": 10
        }
        
        return JSONResponse(status_code=200, content=status)
        
    except Exception as e:
        logger.error(f"获取处理状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取处理状态失败: {str(e)}")

@router.post("/rebuild-index")
async def rebuild_index():
    """
    重建索引
    
    Returns:
        重建结果
    """
    try:
        # 获取处理器实例
        document_processor, table_extractor, rag_engine = get_processors()
        
        # 清空现有索引
        if rag_engine:
            rag_engine.clear_index()
        
        # 获取所有已处理的文档（这里简化处理，实际应该从存储中恢复）
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            raise HTTPException(status_code=400, detail="没有找到上传的文件")
        
        # 重新处理所有文件并构建索引
        pdf_files = [f.name for f in upload_dir.iterdir() if f.suffix.lower() == '.pdf']
        
        if not pdf_files:
            raise HTTPException(status_code=400, detail="没有找到PDF文件")
        
        all_processed_docs = {}
        all_extracted_tables = {}
        
        for filename in pdf_files:
            try:
                file_path = upload_dir / filename
                
                # 处理文档
                doc_result = document_processor.process_file(str(file_path), filename)
                all_processed_docs[filename] = doc_result
                
                # 提取表格
                processed_docs = {filename: doc_result}
                extracted_tables = table_extractor.extract_tables(processed_docs)
                all_extracted_tables.update(extracted_tables)
                
            except Exception as e:
                logger.warning(f"重建索引时处理文件失败 {filename}: {str(e)}")
        
        # 构建索引
        if all_processed_docs and rag_engine:
            index_built = rag_engine.build_index(all_processed_docs, all_extracted_tables)
            
            if index_built:
                try:
                    index_stats = rag_engine.get_index_stats()
                except Exception as e:
                    logger.warning(f"获取索引统计失败: {str(e)}")
                    index_stats = None
                    
                return JSONResponse(
                    status_code=200,
                    content={
                        "message": "索引重建成功",
                        "processed_files": len(all_processed_docs),
                        "index_stats": index_stats
                    }
                )
            else:
                raise HTTPException(status_code=500, detail="索引重建失败")
        else:
            raise HTTPException(status_code=400, detail="没有可处理的文档或RAG引擎未初始化")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重建索引失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"重建索引失败: {str(e)}")
