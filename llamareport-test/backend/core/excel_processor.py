"""
Excel文件处理器
专注于Excel表格的解析和财务报表识别
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from llama_index.core import Document
import re

logger = logging.getLogger(__name__)

class ExcelProcessor:
    """Excel文件处理器"""
    
    # 财务报表识别关键词
    FINANCIAL_STATEMENT_KEYWORDS = {
        '利润表': ['利润表', '损益表', '综合收益表', 'income statement', 'profit and loss', 'P&L'],
        '资产负债表': ['资产负债表', '财务状况表', 'balance sheet', 'statement of financial position'],
        '现金流量表': ['现金流量表', 'cash flow', 'statement of cash flows', '现金流']
    }
    
    def __init__(self):
        pass
    
    def identify_financial_statement_type(self, df: pd.DataFrame, sheet_name: str = '') -> Optional[str]:
        """
        识别财务报表类型
        
        Args:
            df: DataFrame对象
            sheet_name: 工作表名称
            
        Returns:
            财务报表类型：'利润表'、'资产负债表'、'现金流量表' 或 None
        """
        # 检查工作表名称
        sheet_name_lower = sheet_name.lower()
        for statement_type, keywords in self.FINANCIAL_STATEMENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in sheet_name_lower:
                    return statement_type
        
        # 检查DataFrame内容（第一行和列名）
        if df.empty:
            return None
        
        # 合并所有文本内容用于检查
        all_text = ' '.join([
            str(sheet_name),
            ' '.join([str(val) for val in df.iloc[0].values if pd.notna(val)]),
            ' '.join([str(col) for col in df.columns if pd.notna(col)])
        ]).lower()
        
        # 检查关键词
        for statement_type, keywords in self.FINANCIAL_STATEMENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in all_text:
                    return statement_type
        
        # 检查特定列名（更精确的识别）
        columns_text = ' '.join([str(col).lower() for col in df.columns if pd.notna(col)])
        
        # 利润表特征：营业收入、净利润、营业成本等
        if any(keyword in columns_text for keyword in ['营业收入', '净利润', '营业成本', 'revenue', 'net income', 'net profit']):
            if '利润' in columns_text or 'profit' in columns_text or 'income' in columns_text:
                return '利润表'
        
        # 资产负债表特征：资产、负债、所有者权益
        if any(keyword in columns_text for keyword in ['资产', '负债', '所有者权益', 'asset', 'liability', 'equity']):
            if ('资产' in columns_text and '负债' in columns_text) or ('asset' in columns_text and 'liability' in columns_text):
                return '资产负债表'
        
        # 现金流量表特征：经营活动、投资活动、筹资活动
        if any(keyword in columns_text for keyword in ['经营活动', '投资活动', '筹资活动', 'operating', 'investing', 'financing']):
            if '现金流' in columns_text or 'cash flow' in columns_text:
                return '现金流量表'
        
        return None
    
    def process_excel_file(self, file_path: str, filename: str) -> Dict[str, Any]:
        """
        处理Excel文件并提取内容
        
        Args:
            file_path: 文件路径
            filename: 文件名
            
        Returns:
            处理结果字典
        """
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 读取Excel文件的所有工作表
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            all_documents = []
            sheet_info = []
            financial_statements = []
            
            logger.info(f"处理Excel文件: {filename}, 工作表数: {len(sheet_names)}")
            
            for sheet_name in sheet_names:
                try:
                    # 读取工作表，保留所有列（包括空列）
                    # 使用header=None确保所有行都被读取，不跳过任何列
                    # 使用engine='openpyxl'确保正确读取所有列
                    try:
                        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, keep_default_na=False, engine='openpyxl')
                    except Exception as e:
                        logger.warning(f"使用openpyxl读取失败，尝试默认引擎: {str(e)}")
                        df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, keep_default_na=False)
                    
                    if df.empty:
                        logger.warning(f"工作表 {sheet_name} 为空，跳过")
                        continue
                    
                    # 记录原始列数和前几行数据用于调试
                    logger.info(f"工作表 {sheet_name}: {len(df)} 行 × {len(df.columns)} 列")
                    # 打印前3行的所有列数据用于调试
                    if len(df) > 0:
                        logger.info(f"前3行数据预览:")
                        for i in range(min(3, len(df))):
                            row_data = df.iloc[i].tolist()
                            logger.info(f"  第{i+1}行 ({len(row_data)}列): {row_data}")
                            # 检查这一行是否包含241231或250930
                            row_text = ' '.join([str(val) for val in row_data if pd.notna(val)])
                            if '241231' in row_text:
                                logger.info(f"    ✅ 第{i+1}行包含241231")
                            if '250930' in row_text:
                                logger.info(f"    ✅ 第{i+1}行包含250930")
                        # 检查是否包含241231
                        all_text = ' '.join([str(val) for row in df.head(5).values for val in row if pd.notna(val)])
                        if '241231' in all_text:
                            logger.info(f"✅ 找到241231列")
                        else:
                            logger.warning(f"⚠️ 未在前5行中找到241231")
                        if '250930' in all_text:
                            logger.info(f"✅ 找到250930列")
                        else:
                            logger.warning(f"⚠️ 未在前5行中找到250930")
                        
                        # 检查DataFrame的实际列数
                        logger.info(f"DataFrame列名: {list(df.columns)}")
                        logger.info(f"DataFrame形状: {df.shape}")
                    
                    # 识别财务报表类型
                    statement_type = self.identify_financial_statement_type(df, sheet_name)
                    
                    # 转换为文本格式
                    sheet_text = self._dataframe_to_text(df, sheet_name, statement_type)
                    
                    # 创建Document对象
                    metadata = {
                        'filename': filename,
                        'sheet_name': sheet_name,
                        'source': 'excel_processor',
                        'file_type': 'excel',
                        'row_count': len(df),
                        'column_count': len(df.columns)
                    }
                    
                    # 如果是财务报表，添加特殊标记
                    if statement_type:
                        metadata['financial_statement_type'] = statement_type
                        metadata['is_financial_statement'] = True
                        financial_statements.append({
                            'sheet_name': sheet_name,
                            'type': statement_type,
                            'row_count': len(df),
                            'column_count': len(df.columns)
                        })
                    else:
                        metadata['is_financial_statement'] = False
                    
                    doc = Document(
                        text=sheet_text,
                        metadata=metadata
                    )
                    all_documents.append(doc)
                    
                    sheet_info.append({
                        'sheet_name': sheet_name,
                        'statement_type': statement_type,
                        'row_count': len(df),
                        'column_count': len(df.columns),
                        'is_financial_statement': statement_type is not None
                    })
                    
                    logger.info(f"  工作表 {sheet_name}: {len(df)}行 x {len(df.columns)}列, 类型: {statement_type or '普通表格'}")
                    
                except Exception as e:
                    logger.warning(f"处理工作表 {sheet_name} 失败: {str(e)}")
                    continue
            
            result = {
                'filename': filename,
                'documents': all_documents,
                'sheet_count': len(sheet_names),
                'sheet_info': sheet_info,
                'financial_statements': financial_statements,
                'total_text_length': sum(len(doc.text) for doc in all_documents),
                'processing_method': 'excel_processor'
            }
            
            logger.info(f"Excel文件处理完成: {filename}, 文档数: {len(all_documents)}, 财务报表数: {len(financial_statements)}")
            
            return result
            
        except Exception as e:
            logger.error(f"处理Excel文件失败 {filename}: {str(e)}")
            raise
    
    def _dataframe_to_text(self, df: pd.DataFrame, sheet_name: str, statement_type: Optional[str] = None) -> str:
        """
        将DataFrame转换为文本格式
        
        Args:
            df: DataFrame对象
            sheet_name: 工作表名称
            statement_type: 财务报表类型
            
        Returns:
            文本内容
        """
        text_parts = []
        
        # 添加工作表名称和类型
        if statement_type:
            text_parts.append(f"【{statement_type}】工作表: {sheet_name}")
        else:
            text_parts.append(f"工作表: {sheet_name}")
        
        # 尝试识别表头（通常第一行或前几行）
        # 财务报表可能有2行表头：第一行是项目名，第二行是日期/期间
        header_rows = []
        if len(df) > 0:
            # 检查第一行是否包含列名特征
            first_row = df.iloc[0].astype(str).tolist()
            if any('项目' in str(val) or '科目' in str(val) or 'item' in str(val).lower() for val in first_row):
                header_rows.append(0)
                # 检查第二行是否是日期/期间行（通常包含数字日期格式，如250930, 241231等）
                if len(df) > 1:
                    second_row = df.iloc[1].astype(str).tolist()
                    # 检查是否包含日期格式（6位数字，如250930）或常见的日期关键词
                    has_date_format = any(
                        (str(val).isdigit() and len(str(val)) == 6) or  # 6位数字日期
                        '年' in str(val) or '月' in str(val) or '日' in str(val) or
                        '期末' in str(val) or '期初' in str(val) or
                        '期末余额' in str(val) or '期初余额' in str(val)
                        for val in second_row if pd.notna(val) and str(val).strip()
                    )
                    if has_date_format:
                        header_rows.append(1)
            elif len(df) > 1:
                # 检查第二行
                second_row = df.iloc[1].astype(str).tolist()
                if any('项目' in str(val) or '科目' in str(val) or 'item' in str(val).lower() for val in second_row):
                    header_rows.append(1)
        
        # 如果没有识别到表头，默认第一行为表头
        if not header_rows:
            header_rows = [0]
        
        # 构建表格文本
        text_parts.append("\n表格内容：")
        
        # 添加表头（可能有多行）
        # 确保使用所有列，即使某些列是空的
        max_cols = len(df.columns)
        logger.info(f"表头处理: max_cols={max_cols}, header_rows={header_rows}")
        for header_row_idx in header_rows:
            if header_row_idx < len(df):
                header = df.iloc[header_row_idx].astype(str).tolist()
                logger.info(f"  表头行{header_row_idx}: 原始列数={len(header)}, 内容前10列={header[:10]}")
                # 确保header包含所有列（如果某些列缺失，补充空字符串）
                while len(header) < max_cols:
                    header.append("")
                # 只取前max_cols个元素，确保不会超出
                header = header[:max_cols]
                # 检查是否包含241231和250930
                header_text = ' '.join(header)
                if '241231' in header_text:
                    logger.info(f"  ✅ 表头行{header_row_idx}包含241231")
                if '250930' in header_text:
                    logger.info(f"  ✅ 表头行{header_row_idx}包含250930")
                # 使用 | 分隔符，确保每列都被正确分隔
                header_str = " | ".join([str(val) if pd.notna(val) and str(val) != 'nan' and str(val).strip() else "" for val in header])
                logger.info(f"表头行{header_row_idx}生成的文本 (列数={len(header)}, 文本长度={len(header_str)}): {header_str[:300]}...")
                # 检查生成的文本中 | 的数量
                pipe_count = header_str.count('|')
                logger.info(f"  文本中 | 分隔符数量: {pipe_count}, 期望数量: {len(header)-1}")
                text_parts.append(header_str)
        
        # 添加分隔线
        if header_rows:
            text_parts.append("-" * 80)
        
        # 添加数据行（从最后一行表头的下一行开始，最多显示100行，避免过长）
        max_rows = min(100, len(df))
        start_row = max(header_rows) + 1 if header_rows else 1
        logger.info(f"数据行处理: start_row={start_row}, max_rows={max_rows}, max_cols={max_cols}")
        
        # 检查前几行数据是否包含241231和250930
        for i in range(start_row, min(start_row + 3, len(df))):
            row = df.iloc[i].astype(str).tolist()
            row_text = ' '.join([str(val) for val in row if pd.notna(val)])
            if '241231' in row_text:
                logger.info(f"  ✅ 数据行{i}包含241231")
            if '250930' in row_text:
                logger.info(f"  ✅ 数据行{i}包含250930")
        
        for i in range(start_row, min(start_row + max_rows, len(df))):
            row = df.iloc[i].astype(str).tolist()
            # 确保row包含所有列（如果某些列缺失，补充空字符串）
            while len(row) < max_cols:
                row.append("")
            # 只取前max_cols个元素，确保不会超出
            row = row[:max_cols]
            if i == start_row:
                logger.info(f"  第一行数据: 列数={len(row)}, 前10列={row[:10]}")
            # 使用 | 分隔符，确保每列都被正确分隔
            row_str = " | ".join([str(val) if pd.notna(val) and str(val) != 'nan' and str(val).strip() else "" for val in row])
            if i == start_row:
                logger.debug(f"第一行数据文本: {row_str[:200]}...")  # 只记录前200字符
            text_parts.append(row_str)
        
        if len(df) > max_rows:
            text_parts.append(f"\n... (共{len(df)}行，仅显示前{max_rows}行)")
        
        return "\n".join(text_parts)
    
    def validate_file(self, file_path: str) -> bool:
        """
        验证Excel文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            是否有效
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            
            if path.suffix.lower() not in {'.xlsx', '.xls'}:
                return False
            
            # 尝试打开文件验证
            pd.ExcelFile(file_path)
            return True
            
        except Exception as e:
            logger.warning(f"Excel文件验证失败: {str(e)}")
            return False

