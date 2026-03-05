"""
重建索引脚本
清空现有索引并重新处理文档
"""
import sys
import os
import io

# 设置UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加父目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.rag_engine import RAGEngine
from core.document_processor import DocumentProcessor
from core.table_extractor import TableExtractor
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def rebuild_index(upload_dir: str = "./uploads"):
    """
    重建索引
    
    Args:
        upload_dir: 上传文件目录
    """
    try:
        print("\n" + "="*100)
        print("开始重建索引...")
        print("="*100 + "\n")
        
        # 1. 初始化组件
        logger.info("1️⃣ 初始化RAG引擎...")
        rag_engine = RAGEngine()
        
        if not rag_engine.llama_index_ready:
            logger.error("❌ RAG引擎未就绪，请检查API密钥配置")
            return False
        
        # 2. 清空现有索引
        logger.info("2️⃣ 清空现有索引...")
        if rag_engine.clear_index():
            logger.info("✅ 索引已清空")
        else:
            logger.warning("⚠️ 清空索引失败，继续执行...")
        
        # 3. 检查上传目录
        upload_path = Path(upload_dir)
        if not upload_path.exists():
            logger.error(f"❌ 上传目录不存在: {upload_dir}")
            return False
        
        # 4. 查找PDF文件
        pdf_files = list(upload_path.glob("*.pdf"))
        if not pdf_files:
            logger.warning(f"⚠️ 在 {upload_dir} 中没有找到PDF文件")
            logger.info("请先上传PDF文件到该目录")
            return False
        
        logger.info(f"3️⃣ 找到 {len(pdf_files)} 个PDF文件")
        for pdf_file in pdf_files:
            logger.info(f"   - {pdf_file.name}")
        
        # 5. 处理文档
        logger.info("4️⃣ 开始处理文档...")
        doc_processor = DocumentProcessor()
        table_extractor = TableExtractor()
        
        processed_documents = {}
        
        for pdf_file in pdf_files:
            try:
                logger.info(f"\n处理文件: {pdf_file.name}")
                
                # 处理文档
                result = doc_processor.process_file(str(pdf_file), pdf_file.name)
                processed_documents[pdf_file.name] = result
                
                logger.info(f"✅ 文档处理完成: {result['page_count']} 页")
                
            except Exception as e:
                logger.error(f"❌ 处理文件失败 {pdf_file.name}: {str(e)}")
                continue
        
        if not processed_documents:
            logger.error("❌ 没有成功处理任何文档")
            return False
        
        # 6. 提取表格
        logger.info("\n5️⃣ 提取表格数据...")
        extracted_tables = table_extractor.extract_tables(processed_documents)
        
        total_tables = sum(len(tables) for tables in extracted_tables.values())
        logger.info(f"✅ 共提取 {total_tables} 个表格")
        
        # 7. 构建索引
        logger.info("\n6️⃣ 构建向量索引...")
        if rag_engine.build_index(processed_documents, extracted_tables):
            logger.info("✅ 索引构建成功")
        else:
            logger.error("❌ 索引构建失败")
            return False
        
        # 8. 获取索引统计
        stats = rag_engine.get_index_stats()
        
        print("\n" + "="*100)
        print("📊 索引统计信息")
        print("="*100)
        print(f"状态: {stats.get('status', 'unknown')}")
        print(f"文档数量: {stats.get('document_count', 0)}")
        print(f"向量数量: {stats.get('vector_count', 0)}")
        print(f"存储目录: {stats.get('storage_dir', 'unknown')}")
        print("="*100 + "\n")
        
        # 9. 测试查询
        logger.info("7️⃣ 测试查询功能...")
        test_query = "营业收入"
        result = rag_engine.query(test_query)
        
        if not result.get('error'):
            logger.info("✅ 查询测试成功")
            logger.info(f"找到 {len(result.get('sources', []))} 个相关来源")
        else:
            logger.warning(f"⚠️ 查询测试失败: {result.get('answer')}")
        
        print("\n" + "="*100)
        print("🎉 索引重建完成！")
        print("="*100 + "\n")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 重建索引失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='重建RAG索引')
    parser.add_argument(
        '--upload-dir',
        type=str,
        default='./uploads',
        help='上传文件目录 (默认: ./uploads)'
    )
    
    args = parser.parse_args()
    
    success = rebuild_index(args.upload_dir)
    
    if success:
        print("\n✅ 重建成功！现在可以重新启动服务并测试查询功能。")
    else:
        print("\n❌ 重建失败！请检查错误日志。")
        sys.exit(1)

