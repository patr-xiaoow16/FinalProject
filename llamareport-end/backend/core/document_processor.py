"""
简化的文档处理器
专注于PDF文档的文本提取和预处理
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from llama_index.core import Document
from llama_index.readers.file import PDFReader
import pdfplumber

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """简化的文档处理器"""
    
    def __init__(self):
        self.pdf_reader = PDFReader()
    
    def process_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        处理文件并提取内容（支持PDF和Excel）
        
        Args:
            file_path: 文件路径
            filename: 文件名
            
        Returns:
            处理结果字典
        """
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            file_ext = Path(filename).suffix.lower()
            
            # 处理Excel文件
            if file_ext in {'.xlsx', '.xls'}:
                from core.excel_processor import ExcelProcessor
                excel_processor = ExcelProcessor()
                return excel_processor.process_excel_file(file_path, filename)
            
            # 处理PDF文件
            if file_ext == '.pdf':
                # 使用LlamaIndex提取文档
                documents = self.pdf_reader.load_data(Path(file_path))
                
                # 使用pdfplumber提取详细内容
                detailed_content = self._extract_detailed_content(file_path)
                
                # 添加元数据
                for i, doc in enumerate(documents):
                    doc.metadata.update({
                        'filename': filename,
                        'page_number': i + 1,
                        'source': 'pdf_processor',
                        'file_type': 'pdf'
                    })
                
                result = {
                    'filename': filename,
                    'documents': documents,
                    'detailed_content': detailed_content,
                    'page_count': len(detailed_content['pages']),
                    'total_text_length': sum(len(doc.text) for doc in documents),
                    'processing_method': 'simple_pdf_processor'
                }
            else:
                raise ValueError(f"不支持的文件类型: {file_ext}")
            
            # 🔍 打印处理结果的JSON结构
            import json
            print("=" * 80)
            print(f"📄 文档处理完成: {filename}")
            print("=" * 80)
            
            # 打印主要结构信息
            print("📊 主要结构:")
            print(f"  - 文件名: {result['filename']}")
            print(f"  - 页数: {result['page_count']}")
            print(f"  - 文档数量: {len(result['documents'])}")
            print(f"  - 总文本长度: {result['total_text_length']}")
            print(f"  - 处理方式: {result['processing_method']}")
            
            # 打印详细内容结构
            print("\n📋 详细内容结构:")
            print(f"  - 页面数量: {len(detailed_content['pages'])}")
            print(f"  - 元数据: {list(detailed_content['metadata'].keys()) if detailed_content['metadata'] else '无'}")
            
            # 打印每页的表格信息
            print("\n📊 表格信息:")
            for i, page in enumerate(detailed_content['pages'][:3]):  # 只显示前3页
                print(f"  第{i+1}页: {len(page['tables'])}个表格, {len(page['text'])}个字符")
                if page['tables']:
                    for j, table in enumerate(page['tables'][:2]):  # 每页最多显示2个表格
                        print(f"    表格{j+1}: {table['rows']}行 x {table['cols']}列")
            
            # 打印完整的JSON结构（可选，注释掉避免输出过长）
            # print("\n🔍 完整JSON结构:")
            # print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            
            print("=" * 80)
            
            logger.info(f"成功处理文档: {filename}, 页数: {result['page_count']}")
            return result
            
        except Exception as e:
            logger.error(f"处理文档失败 {filename}: {str(e)}")
            raise
    
    def _extract_detailed_content(self, pdf_path: str) -> Dict[str, Any]:
        """
        使用pdfplumber提取详细内容
        """
        content = {
            'pages': [],
            'metadata': {},
            'total_pages': 0
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                content['metadata'] = pdf.metadata or {}
                content['total_pages'] = len(pdf.pages)
                
                for i, page in enumerate(pdf.pages):
                    page_content = {
                        'page_number': i + 1,
                        'text': page.extract_text() or '',
                        'tables': [],
                        'images': len(page.images),
                        'width': page.width,
                        'height': page.height
                    }
                    
                    # 提取表格
                    tables = page.extract_tables()
                    if tables:
                        for j, table in enumerate(tables):
                            if table and len(table) > 0:
                                page_content['tables'].append({
                                    'table_id': f"page_{i+1}_table_{j+1}",
                                    'data': table,
                                    'rows': len(table),
                                    'cols': len(table[0]) if table[0] else 0
                                })
                    
                    content['pages'].append(page_content)
            
            # 🔍 打印详细内容提取结果
            print(f"\n📄 详细内容提取完成:")
            print(f"  - 总页数: {content['total_pages']}")
            print(f"  - 提取页面数: {len(content['pages'])}")
            print(f"  - PDF元数据: {len(content['metadata'])}个字段")
            
            # 统计表格总数
            total_tables = sum(len(page['tables']) for page in content['pages'])
            print(f"  - 总表格数: {total_tables}")
            
            # 显示前几页的详细信息
            for i, page in enumerate(content['pages'][:2]):  # 只显示前2页
                print(f"  第{i+1}页: {len(page['text'])}字符, {len(page['tables'])}表格, {page['images']}图片")
                    
        except Exception as e:
            logger.error(f"提取详细内容失败: {str(e)}")
            raise
        
        return content
    
    def extract_text_chunks(self, documents: List[Document], chunk_size: int = 1024, chunk_overlap: int = 200) -> List[Document]:
        """
        将文档分块处理
        
        Args:
            documents: 文档列表
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            分块后的文档列表
        """
        from llama_index.core.text_splitter import TokenTextSplitter
        
        text_splitter = TokenTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        chunked_docs = []
        for doc in documents:
            chunks = text_splitter.split_text(doc.text)
            for i, chunk in enumerate(chunks):
                chunk_doc = Document(
                    text=chunk,
                    metadata={
                        **doc.metadata,
                        'chunk_id': i,
                        'total_chunks': len(chunks)
                    }
                )
                chunked_docs.append(chunk_doc)
        
        logger.info(f"文档分块完成: {len(documents)} -> {len(chunked_docs)} 块")
        return chunked_docs
    
    def validate_file(self, file_path: str, max_size: int = 50 * 1024 * 1024) -> bool:
        """
        验证文件是否有效（支持PDF和Excel）
        
        Args:
            file_path: 文件路径
            max_size: 最大文件大小（字节）
            
        Returns:
            是否有效
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            
            file_ext = path.suffix.lower()
            # 支持PDF和Excel文件
            if file_ext not in {'.pdf', '.xlsx', '.xls'}:
                logger.warning(f"不支持的文件类型: {file_ext}")
                return False
            
            # 检查文件大小
            if path.stat().st_size > max_size:
                logger.warning(f"文件过大: {path.stat().st_size} bytes")
                return False
            
            # 对于Excel文件，尝试打开验证
            if file_ext in {'.xlsx', '.xls'}:
                try:
                    from core.excel_processor import ExcelProcessor
                    excel_processor = ExcelProcessor()
                    if excel_processor.validate_file(str(path)):
                        return True
                except Exception as e:
                    logger.warning(f"Excel文件验证失败: {str(e)}")
                    return False
            
            # 对于PDF文件，检查是否是有效的PDF
            if file_ext == '.pdf':
                try:
                    import pdfplumber
                    with pdfplumber.open(str(path)) as pdf:
                        if len(pdf.pages) == 0:
                            return False
                except Exception as e:
                    logger.warning(f"PDF文件验证失败: {str(e)}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"文件验证异常: {str(e)}")
            return False
        """
        验证文件
        
        Args:
            file_path: 文件路径
            max_size: 最大文件大小（字节）
            
        Returns:
            是否有效
        """
        try:
            path = Path(file_path)
            
            # 检查文件是否存在
            if not path.exists():
                logger.error(f"文件不存在: {file_path}")
                return False
            
            # 检查文件大小
            file_size = path.stat().st_size
            if file_size > max_size:
                logger.error(f"文件过大: {file_size} > {max_size}")
                return False
            
            # 检查文件扩展名（支持PDF和Excel）
            file_ext = path.suffix.lower()
            if file_ext not in {'.pdf', '.xlsx', '.xls'}:
                logger.error(f"不支持的文件类型: {file_ext}")
                return False
            
            # 对于Excel文件，尝试打开验证
            if file_ext in {'.xlsx', '.xls'}:
                try:
                    from core.excel_processor import ExcelProcessor
                    excel_processor = ExcelProcessor()
                    if excel_processor.validate_file(str(path)):
                        return True
                except Exception as e:
                    logger.warning(f"Excel文件验证失败: {str(e)}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"文件验证失败: {str(e)}")
            return False
    
    def get_document_summary(self, documents: List[Document]) -> Dict[str, Any]:
        """
        获取文档摘要信息
        """
        if not documents:
            return {}
        
        total_text = ' '.join([doc.text for doc in documents])
        
        summary = {
            'document_count': len(documents),
            'total_characters': len(total_text),
            'total_words': len(total_text.split()),
            'average_doc_length': sum(len(doc.text) for doc in documents) / len(documents),
            'metadata_keys': list(documents[0].metadata.keys()) if documents else []
        }
        
        return summary
