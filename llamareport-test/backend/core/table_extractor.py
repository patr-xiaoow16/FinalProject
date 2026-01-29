"""
简化的表格提取器
专注于从文档中提取和分析表格数据
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)

class TableExtractor:
    """简化的表格提取器"""
    
    def __init__(self):
        # 财务关键词
        self.financial_keywords = [
            'revenue', 'sales', 'income', 'profit', 'loss', 'earnings',
            'assets', 'liabilities', 'equity', 'cash', 'debt',
            'margin', 'ratio', 'percentage', 'growth', 'year'
        ]
        
        # 货币和数字模式
        self.currency_patterns = [
            r'[\$¥€£]\s*[\d,.]+'  # 货币符号
        ]
        self.percentage_patterns = [
            r'\d+\.?\d*\s*%'      # 百分比
        ]
        self.number_patterns = [
            r'\b\d{1,3}(?:,\d{3})+\b',  # 逗号分隔的数字
            r'\b\d+\.?\d*[万千百十亿]\b'   # 中文数字单位
        ]
    
    def extract_tables(self, processed_documents: Dict[str, Any]) -> Dict[str, List[Dict]]:
        """
        从处理过的文档中提取表格（支持PDF和Excel）
        
        Args:
            processed_documents: 处理过的文档字典
            
        Returns:
            提取的表格字典
        """
        all_tables = {}
        
        for doc_name, doc_data in processed_documents.items():
            try:
                doc_tables = []
                
                # 检查是否是Excel文件
                # 方法1: 检查processing_method
                file_type = doc_data.get('processing_method', '')
                # 方法2: 检查documents中的metadata
                is_excel_file = False
                documents = doc_data.get('documents', [])
                if documents:
                    first_doc = documents[0]
                    if hasattr(first_doc, 'metadata'):
                        is_excel_file = first_doc.metadata.get('file_type') == 'excel'
                    elif isinstance(first_doc, dict):
                        is_excel_file = first_doc.get('metadata', {}).get('file_type') == 'excel'
                
                if 'excel' in file_type.lower() or is_excel_file:
                    # Excel文件：从documents中提取表格
                    # Excel文件的每个工作表已经转换为Document，我们需要将其转换为表格格式
                    logger.info(f"检测到Excel文件: {doc_name}，开始提取表格...")
                    for idx, doc in enumerate(documents):
                        try:
                            # 处理Document对象或字典
                            if hasattr(doc, 'metadata'):
                                metadata = doc.metadata
                                text = doc.text
                            elif isinstance(doc, dict):
                                metadata = doc.get('metadata', {})
                                text = doc.get('text', '')
                            else:
                                continue
                            
                            if metadata.get('file_type') == 'excel':
                                sheet_name = metadata.get('sheet_name', f'Sheet{idx+1}')
                                sheet_num = idx + 1
                                
                                # 将Document文本解析为表格数据
                                table_data = self._parse_excel_sheet_to_table(text, sheet_name)
                                if table_data and len(table_data) > 1:
                                    processed_table = self._process_table(
                                        table_data,
                                        doc_name,
                                        sheet_num,  # 使用工作表编号作为page_number
                                        f"sheet_{sheet_num}_{sheet_name.replace(' ', '_')}"
                                    )
                                    if processed_table:
                                        # 添加Excel特有的元数据
                                        processed_table['sheet_name'] = sheet_name
                                        processed_table['is_excel_table'] = True
                                        if metadata.get('is_financial_statement'):
                                            processed_table['is_financial'] = True
                                            processed_table['financial_statement_type'] = metadata.get('financial_statement_type')
                                        doc_tables.append(processed_table)
                                        logger.info(f"  ✅ 从工作表 {sheet_name} 提取了1个表格")
                        except Exception as e:
                            logger.warning(f"处理Excel工作表失败: {str(e)}")
                            continue
                
                # PDF文件：从详细内容中提取表格
                elif 'detailed_content' in doc_data:
                    for page in doc_data['detailed_content']['pages']:
                        if 'tables' in page and isinstance(page['tables'], list):
                            for table_info in page['tables']:
                                processed_table = self._process_table(
                                    table_info['data'],
                                    doc_name,
                                    page['page_number'],
                                    table_info['table_id']
                                )
                                if processed_table:
                                    doc_tables.append(processed_table)
                
                all_tables[doc_name] = doc_tables
                logger.info(f"从 {doc_name} 提取了 {len(doc_tables)} 个表格")
                
            except Exception as e:
                logger.error(f"从 {doc_name} 提取表格失败: {str(e)}")
                import traceback
                logger.error(f"详细错误: {traceback.format_exc()}")
                all_tables[doc_name] = []
        
        return all_tables
    
    def _parse_excel_sheet_to_table(self, text: str, sheet_name: str) -> Optional[List[List]]:
        """
        将Excel工作表的文本格式解析为表格数据
        
        Args:
            text: 工作表文本内容（包含 | 分隔的表格行）
            sheet_name: 工作表名称
            
        Returns:
            表格数据（二维列表）或None
        """
        try:
            lines = text.split('\n')
            table_rows = []
            
            for line in lines:
                line = line.strip()
                # 跳过标题和空行
                if not line or line.startswith('【') or line.startswith('工作表:') or line.startswith('表格内容') or line.startswith('-'):
                    continue
                
                # 检查是否是表格行（包含 | 分隔符）
                if '|' in line:
                    # 分割单元格
                    cells = [cell.strip() for cell in line.split('|')]
                    # 移除首尾空元素
                    if len(cells) > 2:
                        cells = cells[1:-1]
                    elif len(cells) == 2:
                        cells = [cells[0] if cells[0] else cells[1]]
                    
                    if cells and any(cell for cell in cells):
                        table_rows.append(cells)
            
            if len(table_rows) > 1:  # 至少需要表头和数据行
                return table_rows
            
            return None
            
        except Exception as e:
            logger.warning(f"解析Excel工作表 {sheet_name} 失败: {str(e)}")
            return None
    
    def _process_table(self, raw_table: List[List], doc_name: str, page_num: int, table_id: str) -> Optional[Dict]:
        """
        处理原始表格数据
        """
        try:
            if not raw_table or len(raw_table) < 2:
                return None
            
            # 清理表格数据
            cleaned_table = self._clean_table_data(raw_table)
            if not cleaned_table:
                return None
            
            # 转换为DataFrame
            try:
                if len(cleaned_table) > 1 and len(cleaned_table[0]) > 0:
                    columns = [str(col) if col is not None else f'Column_{i}' 
                              for i, col in enumerate(cleaned_table[0])]
                    df = pd.DataFrame(data=cleaned_table[1:], columns=columns)
                else:
                    df = pd.DataFrame(cleaned_table[1:])
            except Exception:
                df = pd.DataFrame(cleaned_table[1:])
                df.columns = [f'Column_{i}' for i in range(len(df.columns))]
            
            if df.empty:
                return None
            
            # 分析表格
            is_financial = self._is_financial_table(df)
            importance_score = self._calculate_importance_score(df)
            summary = self._generate_table_summary(df)
            
            # 将DataFrame转换为可序列化的格式
            table_data = {
                'columns': list(df.columns),
                'data': df.values.tolist(),
                'shape': df.shape
            }

            table_info = {
                'table_id': table_id,
                'document': doc_name,
                'page_number': page_num,
                'table_data': table_data,  # 使用可序列化的数据而不是DataFrame
                'is_financial': is_financial,
                'importance_score': importance_score,
                'summary': summary,
                'metadata': {
                    'rows': len(df),
                    'columns': len(df.columns),
                    'data_type': 'table'
                }
            }
            
            return table_info
            
        except Exception as e:
            logger.error(f"处理表格 {table_id} 失败: {str(e)}")
            return None
    
    def _clean_table_data(self, raw_table: List[List]) -> List[List]:
        """清理原始表格数据"""
        cleaned = []
        
        for row in raw_table:
            if row is None:
                continue
                
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append('')
                else:
                    # 清理单元格内容
                    cell_str = str(cell).strip()
                    # 移除多余空白
                    cell_str = re.sub(r'\s+', ' ', cell_str)
                    cleaned_row.append(cell_str)
            
            # 只添加非空行
            if any(cell.strip() for cell in cleaned_row):
                cleaned.append(cleaned_row)
        
        return cleaned
    
    def _is_financial_table(self, df: pd.DataFrame) -> bool:
        """判断是否为财务表格"""
        try:
            if df.empty:
                return False
            
            # 检查列名中的财务关键词
            column_text = ' '.join([str(col).lower() for col in df.columns])
            financial_keyword_count = sum(1 for keyword in self.financial_keywords 
                                        if keyword in column_text)
            
            # 检查数据中的数字和货币模式
            sample_text = ''
            for col in df.columns[:3]:  # 检查前3列
                try:
                    sample_data = df[col].astype(str).head(5).values
                    sample_text += ' '.join(sample_data) + ' '
                except:
                    continue
            
            # 计算数字模式匹配
            currency_matches = sum(len(re.findall(pattern, sample_text)) 
                                 for pattern in self.currency_patterns)
            percentage_matches = sum(len(re.findall(pattern, sample_text)) 
                                   for pattern in self.percentage_patterns)
            number_matches = sum(len(re.findall(pattern, sample_text)) 
                               for pattern in self.number_patterns)
            
            # 综合判断
            financial_score = (
                financial_keyword_count * 0.4 +
                currency_matches * 0.3 +
                percentage_matches * 0.2 +
                number_matches * 0.1
            )
            
            return financial_score > 1.0
            
        except Exception as e:
            logger.error(f"判断财务表格失败: {str(e)}")
            return False
    
    def _calculate_importance_score(self, df: pd.DataFrame) -> float:
        """计算表格重要性分数"""
        try:
            if df.empty:
                return 0.0
            
            score = 0.0
            
            # 基于表格大小
            size_score = min(len(df) * len(df.columns) / 100, 0.3)
            score += size_score
            
            # 基于数据密度
            total_cells = len(df) * len(df.columns)
            non_empty_cells = df.count().sum()
            density = non_empty_cells / total_cells if total_cells > 0 else 0
            score += density * 0.3
            
            # 基于数字内容
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            numeric_ratio = len(numeric_cols) / len(df.columns) if len(df.columns) > 0 else 0
            score += numeric_ratio * 0.2
            
            # 基于财务特征
            if self._is_financial_table(df):
                score += 0.2
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"计算重要性分数失败: {str(e)}")
            return 0.5
    
    def _generate_table_summary(self, df: pd.DataFrame) -> str:
        """生成表格摘要"""
        try:
            if df.empty:
                return "空表格"
            
            summary_parts = []
            
            # 基本信息
            summary_parts.append(f"{len(df)}行 x {len(df.columns)}列的表格")
            
            # 数据类型
            numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
            if numeric_cols > 0:
                summary_parts.append(f"包含{numeric_cols}个数值列")
            
            # 财务特征
            if self._is_financial_table(df):
                summary_parts.append("疑似财务数据表格")
            
            # 列名示例
            if len(df.columns) > 0:
                col_sample = list(df.columns)[:3]
                summary_parts.append(f"主要列: {', '.join(col_sample)}")
            
            return "，".join(summary_parts)
            
        except Exception as e:
            logger.error(f"生成表格摘要失败: {str(e)}")
            return "表格摘要生成失败"
    
    def get_financial_tables(self, tables: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """获取财务相关的表格"""
        financial_tables = {}
        
        for doc_name, doc_tables in tables.items():
            financial_doc_tables = [
                table for table in doc_tables 
                if table.get('is_financial', False)
            ]
            if financial_doc_tables:
                financial_tables[doc_name] = financial_doc_tables
        
        return financial_tables
    
    def get_table_statistics(self, tables: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """获取表格统计信息"""
        stats = {
            'total_documents': len(tables),
            'total_tables': sum(len(doc_tables) for doc_tables in tables.values()),
            'financial_tables': 0,
            'average_importance': 0.0,
            'documents_with_tables': 0
        }
        
        all_scores = []
        for doc_name, doc_tables in tables.items():
            if doc_tables:
                stats['documents_with_tables'] += 1
                for table in doc_tables:
                    if table.get('is_financial', False):
                        stats['financial_tables'] += 1
                    all_scores.append(table.get('importance_score', 0.0))
        
        if all_scores:
            stats['average_importance'] = sum(all_scores) / len(all_scores)
        
        return stats
