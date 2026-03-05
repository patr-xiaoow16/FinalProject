"""
文件上传API接口
"""

import os
import shutil
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response
import logging
import urllib.parse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# 支持的文件类型
ALLOWED_EXTENSIONS = {'.pdf', '.xlsx', '.xls'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

@router.post("/file")
async def upload_file(file: UploadFile = File(...)):
    """
    上传单个文件
    
    Args:
        file: 上传的文件
        
    Returns:
        上传结果
    """
    try:
        # 验证文件
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        
        # 检查文件扩展名
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # 检查文件大小
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件过大: {len(file_content)} bytes。最大允许: {MAX_FILE_SIZE} bytes"
            )
        
        # 确保上传目录存在
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # 生成安全的文件名
        safe_filename = _generate_safe_filename(file.filename)
        file_path = upload_dir / safe_filename
        
        # 保存文件
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        logger.info(f"文件上传成功: {safe_filename}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "文件上传成功",
                "filename": safe_filename,
                "file_path": str(file_path),
                "file_size": len(file_content),
                "file_type": file_ext
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.post("/files")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    上传多个文件
    
    Args:
        files: 上传的文件列表
        
    Returns:
        上传结果列表
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="没有选择文件")
        
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="一次最多上传10个文件")
        
        results = []
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        for file in files:
            try:
                # 验证单个文件
                if not file.filename:
                    results.append({
                        "filename": "unknown",
                        "status": "error",
                        "message": "文件名不能为空"
                    })
                    continue
                
                file_ext = Path(file.filename).suffix.lower()
                if file_ext not in ALLOWED_EXTENSIONS:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "message": f"不支持的文件类型: {file_ext}"
                    })
                    continue
                
                # 读取文件内容
                file_content = await file.read()
                if len(file_content) > MAX_FILE_SIZE:
                    results.append({
                        "filename": file.filename,
                        "status": "error",
                        "message": f"文件过大: {len(file_content)} bytes"
                    })
                    continue
                
                # 保存文件
                safe_filename = _generate_safe_filename(file.filename)
                file_path = upload_dir / safe_filename
                
                with open(file_path, "wb") as f:
                    f.write(file_content)
                
                results.append({
                    "filename": safe_filename,
                    "original_filename": file.filename,
                    "status": "success",
                    "file_path": str(file_path),
                    "file_size": len(file_content),
                    "file_type": file_ext
                })
                
                logger.info(f"文件上传成功: {safe_filename}")
                
            except Exception as e:
                results.append({
                    "filename": file.filename if file.filename else "unknown",
                    "status": "error",
                    "message": str(e)
                })
                logger.error(f"文件 {file.filename} 上传失败: {str(e)}")
        
        # 统计结果
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"批量上传完成: {success_count} 成功, {error_count} 失败",
                "total_files": len(results),
                "success_count": success_count,
                "error_count": error_count,
                "results": results
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量文件上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量文件上传失败: {str(e)}")

@router.get("/list")
async def list_uploaded_files():
    """
    列出已上传的文件
    
    Returns:
        文件列表
    """
    try:
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "message": "上传目录不存在",
                    "files": []
                }
            )
        
        files = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                file_info = {
                    "filename": file_path.name,
                    "file_path": str(file_path),
                    "file_size": file_path.stat().st_size,
                    "file_type": file_path.suffix.lower(),
                    "created_time": file_path.stat().st_ctime
                }
                files.append(file_info)
        
        # 按创建时间排序
        files.sort(key=lambda x: x["created_time"], reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"找到 {len(files)} 个文件",
                "total_files": len(files),
                "files": files
            }
        )
        
    except Exception as e:
        logger.error(f"列出文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"列出文件失败: {str(e)}")

@router.delete("/file/{filename}")
async def delete_file(filename: str):
    """
    删除指定文件
    
    Args:
        filename: 文件名
        
    Returns:
        删除结果
    """
    try:
        upload_dir = Path("uploads")
        file_path = upload_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="不是有效的文件")
        
        # 删除文件
        file_path.unlink()
        
        # 从索引中删除该文件的文档
        try:
            from core.rag_engine import RAGEngine
            rag_engine = RAGEngine()
            rag_engine.remove_file_from_index(filename)
        except Exception as e:
            logger.warning(f"⚠️ 从索引中删除文件失败: {str(e)}")
            # 不阻止文件删除，只记录警告
        
        logger.info(f"文件删除成功: {filename}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "文件删除成功",
                "filename": filename
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

@router.get("/file/{filename}")
async def get_file(filename: str):
    """
    获取上传的文件（用于预览）
    
    Args:
        filename: 文件名
    
    Returns:
        文件内容
    """
    try:
        upload_dir = Path("uploads")
        file_path = upload_dir / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="不是有效的文件")
        
        # 检查文件扩展名
        file_ext = file_path.suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型预览: {file_ext}")
        
        # 读取文件内容
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # 处理中文文件名
        try:
            encoded_filename = urllib.parse.quote(filename, safe='')
            content_disposition = f"inline; filename*=UTF-8''{encoded_filename}"
        except Exception:
            content_disposition = f'inline; filename="{filename}"'
        
        # 根据文件类型设置媒体类型
        if file_ext == '.pdf':
            media_type = 'application/pdf'
        elif file_ext in {'.xlsx', '.xls'}:
            # Excel文件返回HTML预览页面
            return await get_excel_preview(file_path, filename)
        else:
            media_type = 'application/octet-stream'
        
        # 返回文件（设置为inline，在浏览器中预览而不是下载）
        return Response(
            content=file_content,
            media_type=media_type,
            headers={
                'Content-Disposition': content_disposition,
                'Content-Length': str(len(file_content))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文件失败: {str(e)}")

async def get_excel_preview(file_path: Path, filename: str):
    """
    获取Excel文件的HTML预览
    
    Args:
        file_path: 文件路径
        filename: 文件名
    
    Returns:
        HTML预览页面
    """
    try:
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_ext = file_path.suffix.lower()
        if file_ext not in {'.xlsx', '.xls'}:
            raise HTTPException(status_code=400, detail="只支持Excel文件预览")
        
        # 读取Excel文件并转换为HTML表格
        from core.excel_processor import ExcelProcessor
        
        excel_processor = ExcelProcessor()
        excel_data = excel_processor.process_excel_file(str(file_path), filename)
        
        # 生成HTML预览页面
        html_content = generate_excel_preview_html(excel_data, filename)
        
        # 将HTML内容编码为UTF-8字节
        html_bytes = html_content.encode('utf-8')
        
        # 处理中文文件名编码
        try:
            encoded_filename = urllib.parse.quote(filename, safe='')
            content_disposition = f'inline; filename*=UTF-8\'\'{encoded_filename}.html'
        except Exception:
            content_disposition = f'inline; filename="{filename}.html"'
        
        return Response(
            content=html_bytes,
            media_type='text/html; charset=utf-8',
            headers={
                'Content-Disposition': content_disposition,
                'Content-Length': str(len(html_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"生成Excel预览失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成Excel预览失败: {str(e)}")

def generate_excel_preview_html(excel_data: Dict[str, Any], filename: str) -> str:
    """
    生成Excel文件的HTML预览页面
    
    Args:
        excel_data: Excel处理结果
        filename: 文件名
    
    Returns:
        HTML内容
    """
    html_parts = [
        '<!DOCTYPE html>',
        '<html lang="zh-CN">',
        '<head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f'<title>预览 - {filename}</title>',
        '<style>',
        'body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }',
        '.container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }',
        '.header { padding: 20px; border-bottom: 1px solid #e5e7eb; }',
        '.header h1 { margin: 0; font-size: 1.5rem; color: #111827; }',
        '.header .file-info { margin-top: 8px; color: #6b7280; font-size: 0.875rem; }',
        '.sheets-tabs { display: flex; gap: 8px; padding: 16px 20px; border-bottom: 1px solid #e5e7eb; background: #f9fafb; flex-wrap: wrap; }',
        '.sheet-tab { padding: 8px 16px; border: 1px solid #e5e7eb; border-radius: 6px; background: white; cursor: pointer; font-size: 0.875rem; transition: all 0.2s; }',
        '.sheet-tab:hover { border-color: #4facfe; background: #f0f9ff; }',
        '.sheet-tab.active { background: #4facfe; color: white; border-color: #4facfe; }',
        '.sheet-tab.has-statement { border-left: 3px solid #10b981; }',
        '.sheet-content { padding: 20px; display: none; }',
        '.sheet-content.active { display: block; }',
        '.statement-badge { display: inline-block; padding: 4px 8px; background: #dcfce7; color: #166534; border-radius: 4px; font-size: 0.75rem; font-weight: 500; margin-left: 8px; }',
        'table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 0.875rem; table-layout: auto; }',
        'th, td { padding: 8px 12px; text-align: left; border: 1px solid #e5e7eb; white-space: nowrap; }',
        'th { background: #f9fafb; font-weight: 600; color: #374151; position: sticky; top: 0; z-index: 10; }',
        'tbody tr:nth-child(even) { background: #f9fafb; }',
        'tbody tr:hover { background: #f0f9ff; }',
        'td { white-space: normal; word-wrap: break-word; max-width: 200px; }',
        '.empty-sheet { text-align: center; padding: 40px; color: #9ca3af; }',
        '</style>',
        '</head>',
        '<body>',
        '<div class="container">',
        f'<div class="header">',
        f'<h1>📊 {filename}</h1>',
        f'<div class="file-info">工作表数: {excel_data.get("sheet_count", 0)} | 财务报表: {len(excel_data.get("financial_statements", []))}个</div>',
        '</div>',
        '<div class="sheets-tabs">'
    ]
    
    # 生成工作表标签
    sheet_info = excel_data.get('sheet_info', [])
    for i, sheet in enumerate(sheet_info):
        is_statement = sheet.get('is_financial_statement', False)
        statement_type = sheet.get('statement_type', '')
        statement_badge = f'<span class="statement-badge">{statement_type}</span>' if statement_type else ''
        tab_class = 'sheet-tab' + (' active' if i == 0 else '') + (' has-statement' if is_statement else '')
        html_parts.append(
            f'<div class="{tab_class}" onclick="showSheet({i})">'
            f'📋 {sheet.get("sheet_name", "Sheet")}{statement_badge}'
            '</div>'
        )
    
    html_parts.append('</div>')
    
    # 生成工作表内容
    documents = excel_data.get('documents', [])
    if not documents:
        html_parts.append('<div class="sheet-content active"><div class="empty-sheet">没有可显示的工作表</div></div>')
    else:
        for i, doc in enumerate(documents):
            # 处理Document对象或字典
            if hasattr(doc, 'metadata'):
                metadata = doc.metadata
                text = doc.text
            elif isinstance(doc, dict):
                metadata = doc.get('metadata', {})
                text = doc.get('text', '')
            else:
                continue
            
            sheet_name = metadata.get('sheet_name', f'Sheet{i+1}')
            statement_type = metadata.get('financial_statement_type', '')
            content_class = 'sheet-content' + (' active' if i == 0 else '')
            
            html_parts.append(f'<div class="{content_class}" id="sheet-{i}">')
            
            if statement_type:
                html_parts.append(f'<div style="margin-bottom: 16px;"><span class="statement-badge">财务报表类型: {statement_type}</span></div>')
            
            # 解析文本内容为表格
            table_html = parse_text_to_table(text)
            html_parts.append(table_html)
            
            html_parts.append('</div>')
    
    html_parts.extend([
        '</div>',
        '<script>',
        'function showSheet(index) {',
        '  document.querySelectorAll(".sheet-tab").forEach((tab, i) => {',
        '    tab.classList.toggle("active", i === index);',
        '  });',
        '  document.querySelectorAll(".sheet-content").forEach((content, i) => {',
        '    content.classList.toggle("active", i === index);',
        '  });',
        '}',
        '</script>',
        '</body>',
        '</html>'
    ])
    
    return '\n'.join(html_parts)

def parse_text_to_table(text: str) -> str:
    """
    将文本内容解析为HTML表格
    从ExcelProcessor生成的文本格式中提取表格数据
    支持多行表头（如第一行是项目名，第二行是日期）
    
    Args:
        text: 文档文本内容（包含 | 分隔的表格行）
    
    Returns:
        HTML表格字符串
    """
    import html as html_escape
    
    lines = text.split('\n')
    table_rows = []
    in_table = False
    separator_found = False
    
    logger.info(f"解析表格文本: 总行数={len(lines)}")
    
    for line in lines:
        line = line.strip()
        # 跳过标题和空行
        if not line or line.startswith('【') or line.startswith('工作表:') or line.startswith('表格内容'):
            continue
        
        # 检查是否是表格行（包含 | 分隔符）
        if '|' in line:
            in_table = True
            # 分割单元格 - 使用 | 作为分隔符
            # 注意：如果文本是 "col1 | col2 | col3"，split('|') 会得到 ['col1 ', ' col2 ', ' col3']
            cells = [cell.strip() for cell in line.split('|')]
            
            # 调试：记录原始分割结果
            if len(table_rows) < 3:
                logger.info(f"  原始行分割: 分隔符数量={line.count('|')}, 分割后单元格数={len(cells)}")
                logger.info(f"  原始行内容: {line[:200]}")
            
            # 移除首尾空元素（通常第一个和最后一个是空的，因为 | 在开头和结尾）
            # 但保留中间的所有单元格，包括空单元格
            if len(cells) > 2:
                cells = cells[1:-1]  # 移除首尾空元素
            elif len(cells) == 2:
                # 如果只有2个元素，可能是 |cell| 或 | | 的情况
                # 保留两个元素，即使其中一个为空
                cells = [cells[0], cells[1]]
            elif len(cells) == 1:
                # 如果只有1个元素，可能是整行没有分隔符，或者格式异常
                # 但仍然保留这一行，不要跳过
                if line.count('|') > 0:
                    logger.warning(f"  警告：行包含{line.count('|')}个'|'但分割后只有1个元素: {line[:100]}")
                # 保留这个单元格
                pass
            
            # 保留所有行，即使某些单元格为空（因为空单元格也可能代表列）
            # 只要cells不为空列表，就添加
            if cells is not None and len(cells) > 0:
                table_rows.append(cells)
                # 调试：检查前几行是否包含241231和250930
                if len(table_rows) <= 3:
                    row_text = ' '.join([str(cell) for cell in cells if cell])
                    logger.info(f"  解析行{len(table_rows)}: 列数={len(cells)}, 前5列={cells[:5]}")
                    if '241231' in row_text:
                        logger.info(f"  ✅ 解析行{len(table_rows)}包含241231: {cells[:10]}")
                    if '250930' in row_text:
                        logger.info(f"  ✅ 解析行{len(table_rows)}包含250930: {cells[:10]}")
        elif in_table and ('---' in line or line.startswith('-')):
            # 分隔线，标记表头结束
            separator_found = True
            continue
        elif in_table and not ('|' in line):
            # 表格结束（如果遇到非表格行且已有数据）
            if len(table_rows) > 0:
                break
    
    if not table_rows:
        return '<div class="empty-sheet">此工作表为空或无法解析为表格</div>'
    
    logger.info(f"解析完成: 表格行数={len(table_rows)}")
    if table_rows:
        logger.info(f"  第一行列数={len(table_rows[0])}, 内容前10列={table_rows[0][:10]}")
        if len(table_rows) > 1:
            logger.info(f"  第二行列数={len(table_rows[1])}, 内容前10列={table_rows[1][:10]}")
    
    # 确定表头行数
    # 检查前两行：如果第二行看起来像日期行（包含6位数字），则两行都是表头
    header_row_count = 1
    if len(table_rows) > 1:
        second_row = table_rows[1]
        # 检查是否包含日期格式（6位数字，如250930、241231）
        has_date_format = any(
            (str(cell).isdigit() and len(str(cell)) == 6) or
            '年' in str(cell) or '月' in str(cell) or '日' in str(cell) or
            '期末' in str(cell) or '期初' in str(cell) or
            '余额' in str(cell)
            for cell in second_row if cell and str(cell).strip()
        )
        # 检查第二行是否与第一行列数相同（通常是表头的特征）
        # 并且第一行通常包含"项目"、"科目"等关键词
        first_row_has_header_keywords = any(
            '项目' in str(cell) or '科目' in str(cell) or 'item' in str(cell).lower()
            for cell in table_rows[0] if cell and str(cell).strip()
        )
        if has_date_format and len(second_row) == len(table_rows[0]) and first_row_has_header_keywords:
            header_row_count = 2
    
    # 生成HTML表格
    html = ['<div style="overflow-x: auto; max-height: 600px; overflow-y: auto;">', '<table style="width: 100%; border-collapse: collapse;">']
    
    # 确定最大列数（用于对齐）- 使用所有行的最大列数
    max_cols = max(len(row) for row in table_rows) if table_rows else 0
    logger.info(f"HTML生成: header_row_count={header_row_count}, max_cols={max_cols}")
    
    # 检查表头是否包含241231和250930
    if table_rows and len(table_rows) > 0:
        for i in range(min(header_row_count, len(table_rows))):
            header_text = ' '.join([str(cell) for cell in table_rows[i] if cell])
            if '241231' in header_text:
                logger.info(f"  ✅ HTML表头行{i}包含241231")
            if '250930' in header_text:
                logger.info(f"  ✅ HTML表头行{i}包含250930")
    
    # 生成表头（可能有多行）
    if table_rows:
        html.append('<thead>')
        for i in range(min(header_row_count, len(table_rows))):
            html.append('<tr>')
            header_row = table_rows[i]
            # 确保表头行包含所有列
            while len(header_row) < max_cols:
                header_row.append('')
            # 只取前max_cols个元素
            header_row = header_row[:max_cols]
            for cell in header_row:
                # 转义HTML特殊字符
                cell_escaped = html_escape.escape(str(cell))
                html.append(f'<th style="padding: 8px 12px; text-align: left; border: 1px solid #e5e7eb; background: #f9fafb; font-weight: 600; position: sticky; top: 0;">{cell_escaped}</th>')
            html.append('</tr>')
        html.append('</thead>')
        html.append('<tbody>')
        
        # 数据行从表头之后开始
        data_start = header_row_count
        max_rows = min(100, len(table_rows) - data_start)
        
        for i in range(data_start, min(data_start + max_rows, len(table_rows))):
            row = table_rows[i]
            html.append('<tr>')
            # 确保列数一致，使用最大列数
            while len(row) < max_cols:
                row.append('')
            # 只取前max_cols个元素
            row = row[:max_cols]
            for cell in row:
                # 转义HTML特殊字符
                cell_escaped = html_escape.escape(str(cell))
                html.append(f'<td style="padding: 8px 12px; text-align: left; border: 1px solid #e5e7eb;">{cell_escaped}</td>')
            html.append('</tr>')
        
        if len(table_rows) > data_start + max_rows:
            html.append(f'<tr><td colspan="{max_cols}" style="text-align: center; color: #9ca3af; padding: 16px; border: 1px solid #e5e7eb;">... (共{len(table_rows)-header_row_count}行数据，仅显示前{max_rows}行)</td></tr>')
        
        html.append('</tbody>')
    
    html.append('</table></div>')
    return '\n'.join(html)

@router.delete("/clear")
async def clear_uploads():
    """
    清空上传目录
    
    Returns:
        清空结果
    """
    try:
        upload_dir = Path("uploads")
        if not upload_dir.exists():
            return JSONResponse(
                status_code=200,
                content={
                    "message": "上传目录不存在",
                    "deleted_count": 0
                }
            )
        
        deleted_count = 0
        deleted_files = []
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                deleted_files.append(file_path.name)
                file_path.unlink()
                deleted_count += 1
        
        # 从索引中删除所有已删除文件的文档
        if deleted_files:
            try:
                from core.rag_engine import RAGEngine
                rag_engine = RAGEngine()
                for filename in deleted_files:
                    rag_engine.remove_file_from_index(filename)
            except Exception as e:
                logger.warning(f"⚠️ 从索引中删除文件失败: {str(e)}")
        
        logger.info(f"清空上传目录: 删除了 {deleted_count} 个文件")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": f"清空完成，删除了 {deleted_count} 个文件",
                "deleted_count": deleted_count
            }
        )
        
    except Exception as e:
        logger.error(f"清空上传目录失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"清空上传目录失败: {str(e)}")

def _generate_safe_filename(filename: str) -> str:
    """生成安全的文件名（保留原始文件名，同名时覆盖）"""
    import os
    import re
    
    # 获取文件名（去除路径）
    safe_name = os.path.basename(filename)
    
    # 移除不安全的字符，保留中文字符、数字、字母、连字符、下划线、点和空格
    # Windows 不允许的字符: < > : " / \ | ? *
    # 控制字符: \x00-\x1f
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', safe_name)
    
    # 移除首尾空格和点
    safe_name = safe_name.strip(' .')
    
    # 如果文件名为空或只有特殊字符，使用默认名称
    if not safe_name or safe_name.strip() == '':
        safe_name = 'uploaded_file.pdf'
    
    # 确保文件名不为空且有效
    if not safe_name:
        safe_name = 'uploaded_file.pdf'
    
    return safe_name
