"""
时间轴数据生成器 - 生成Timeline格式的数据
使用代码示例作为先验知识，让LLM学习生成
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# 时间轴代码示例（作为先验知识，让LLM学习）
TIMELINE_CODE_EXAMPLE = """
<template>
  <a-timeline mode="alternate">
    <a-timeline-item>Create a services site 2015-09-01</a-timeline-item>
    <a-timeline-item color="green">Solve initial network problems 2015-09-01</a-timeline-item>
    <a-timeline-item>
      <template #dot><ClockCircleOutlined style="font-size: 16px" /></template>
      Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque
      laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto
      beatae vitae dicta sunt explicabo.
    </a-timeline-item>
    <a-timeline-item color="red">Network problems being solved 2015-09-01</a-timeline-item>
    <a-timeline-item>Create a services site 2015-09-01</a-timeline-item>
    <a-timeline-item>
      <template #dot><ClockCircleOutlined style="font-size: 16px" /></template>
      Technical testing 2015-09-01
    </a-timeline-item>
  </a-timeline>
</template>
"""


async def generate_timeline_data(
    llm,
    query: str,
    answer: str,
    data: Dict[str, Any],
    sources: Optional[List[Dict]] = None
) -> Optional[List[Dict[str, Any]]]:
    """
    生成Timeline数据
    使用代码示例作为先验知识，让LLM学习生成符合前端组件要求的数据格式
    
    Args:
        llm: LLM实例
        query: 用户查询
        answer: 文本回答
        data: 提取的数据
        sources: 数据来源
    
    Returns:
        List[Dict]: Timeline数据列表，每个元素包含time、content、color等字段
    """
    try:
        # 使用LLM从answer中提取关键事件的时间轴信息
        # 将代码示例作为先验知识，让LLM学习生成
        prompt = f"""
你是一个专业的数据可视化助手。请从以下文本中提取关键事件的时间轴信息，生成JSON格式的时间轴数据。

【先验知识 - 时间轴组件代码示例】
以下是前端时间轴组件的代码示例，请学习其数据结构和格式要求：

{TIMELINE_CODE_EXAMPLE}

从代码示例中可以看出：
1. 时间轴使用 mode="alternate" 模式（左右交替显示）
2. 每个时间轴项包含：时间点、内容描述、可选的颜色
3. 数据结构应该简洁明了，便于前端渲染

【用户查询】
{query}

【文本回答】
{answer}

【任务要求】
请从上述文本中提取所有关键事件及其发生时间，生成JSON格式的时间轴数据。

【输出格式要求】
JSON数组格式，每个元素包含：
- time: 时间点（字符串，使用简化格式）
  - 年份：如 "2024"（不要写"2024年"）
  - 年月日：如 "2024.2.5"（不要写"2024年2月5日"）
  - 年月：如 "2024.2"（不要写"2024年2月"）
  - 季度：如 "2024 Q1"（保持原样）
- content: 事件描述（字符串，简洁明了）
- color: 颜色（可选，blue/green/red/gray/orange/purple，根据事件重要性或类型选择）

【输出示例】
[
  {{"time": "2025", "content": "国内生产总值累计同比增长率平均预测值约为4.86%（基准情景）", "color": "blue"}},
  {{"time": "2026", "content": "国内生产总值累计同比增长率平均预测值约为4.74%（基准情景）", "color": "blue"}},
  {{"time": "2024.12.31", "content": "债权投资总额为人民币800,034百万元", "color": "gray"}},
  {{"time": "2024.2.5", "content": "某项重要事件发生", "color": "green"}}
]

【重要提示】
1. 只提取真正关键的事件，避免冗余
2. 时间点要准确，尽量使用原文中的时间表述
3. 内容描述要简洁，但包含关键信息
4. 颜色选择要有意义（如：重要事件用blue/green，一般事件用gray）
5. 如果无法提取时间信息，返回空数组[]

只返回JSON数组，不要其他解释，不要包含代码块标记（```）。
"""
        response = await llm.acomplete(prompt)
        response_text = str(response).strip()
        
        # 清理响应文本，提取JSON
        # 移除代码块标记
        if '```' in response_text:
            lines = response_text.split('\n')
            json_lines = []
            in_json = False
            for line in lines:
                if '```json' in line.lower() or '```' in line:
                    if not in_json:
                        in_json = True
                        continue
                    else:
                        break
                if in_json:
                    json_lines.append(line)
            response_text = '\n'.join(json_lines)
        
        # 尝试解析JSON
        try:
            timeline_data = json.loads(response_text)
            if isinstance(timeline_data, list) and len(timeline_data) > 0:
                # 验证数据格式
                valid_items = []
                colors = ['blue', 'green', 'red', 'gray', 'orange', 'purple']
                for i, item in enumerate(timeline_data):
                    if isinstance(item, dict) and 'time' in item and 'content' in item:
                        # 确保有color字段
                        if 'color' not in item:
                            item['color'] = colors[i % len(colors)]
                        valid_items.append(item)
                
                if len(valid_items) > 0:
                    # 步骤1: 格式化时间显示（统一格式）
                    formatted_items = _format_timeline_time(valid_items)
                    logger.info(f"✅ 步骤1完成: 时间格式已统一，包含{len(formatted_items)}个事件")
                    
                    # 步骤2: 按时间排序
                    sorted_items = _sort_timeline_by_time(formatted_items)
                    logger.info(f"✅ 步骤2完成: 时间轴已按时间排序")
                    
                    # 步骤3: 验证排序结果
                    if len(sorted_items) > 1:
                        times = [item.get('time', '') for item in sorted_items]
                        logger.info(f"✅ 步骤3完成: 排序后的时间序列: {times}")
                    
                    logger.info(f"✅ 生成时间轴数据完成，包含{len(sorted_items)}个事件")
                    return sorted_items
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {str(e)}")
            logger.warning(f"响应文本: {response_text[:200]}")
        
        logger.warning("无法从回答中提取时间轴信息")
        return None
        
    except Exception as e:
        logger.error(f"生成时间轴数据失败: {str(e)}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        return None


def _format_timeline_time(timeline_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    格式化时间轴时间显示
    
    将时间格式统一为简化格式：
    - "2024年" -> "2024"
    - "2024年2月5日" -> "2024.2.5"
    - "2024年2月" -> "2024.2"
    - "2024 Q1" -> "2024 Q1"（保持不变）
    
    Args:
        timeline_items: 时间轴事件列表
    
    Returns:
        格式化后的时间轴事件列表
    """
    import re
    
    formatted_items = []
    for item in timeline_items:
        formatted_item = item.copy()
        time_str = item.get('time', '')
        
        if not time_str:
            formatted_items.append(formatted_item)
            continue
        
        # 处理 "2024年" -> "2024"
        time_str = re.sub(r'(\d{4})年$', r'\1', time_str)
        
        # 处理 "2024年2月5日" -> "2024.2.5"
        date_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', time_str)
        if date_match:
            year = date_match.group(1)
            month = date_match.group(2).lstrip('0') or '0'
            day = date_match.group(3).lstrip('0') or '0'
            time_str = f"{year}.{month}.{day}"
        
        # 处理 "2024年2月" -> "2024.2"
        month_match = re.match(r'(\d{4})年(\d{1,2})月$', time_str)
        if month_match:
            year = month_match.group(1)
            month = month_match.group(2).lstrip('0') or '0'
            time_str = f"{year}.{month}"
        
        formatted_item['time'] = time_str
        formatted_items.append(formatted_item)
    
    return formatted_items


def _parse_time_string(time_str: str) -> Optional[datetime]:
    """
    解析时间字符串，转换为datetime对象用于排序
    
    支持的时间格式（简化格式）：
    - "2024"（年份）
    - "2024.2.5"（年月日）
    - "2024.2"（年月）
    - "2024 Q1"（季度）
    - "2024-12-31"（ISO格式）
    
    也兼容旧格式：
    - "2024年"
    - "2024年12月31日"
    - "2024年12月"
    
    Args:
        time_str: 时间字符串
    
    Returns:
        datetime对象，如果解析失败返回None
    """
    if not time_str:
        return None
    
    try:
        # 尝试解析简化格式 "2024"（年份）
        year_match = re.match(r'^(\d{4})$', time_str)
        if year_match:
            year = int(year_match.group(1))
            return datetime(year, 1, 1)
        
        # 尝试解析简化格式 "2024.2.5"（年月日）
        dot_date_match = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})$', time_str)
        if dot_date_match:
            year = int(dot_date_match.group(1))
            month = int(dot_date_match.group(2))
            day = int(dot_date_match.group(3))
            return datetime(year, month, day)
        
        # 尝试解析简化格式 "2024.2"（年月）
        dot_month_match = re.match(r'^(\d{4})\.(\d{1,2})$', time_str)
        if dot_month_match:
            year = int(dot_month_match.group(1))
            month = int(dot_month_match.group(2))
            return datetime(year, month, 1)
        
        # 尝试解析 "2024 Q1" 或 "2024Q1"（季度）
        quarter_match = re.match(r'(\d{4})\s*Q(\d)', time_str, re.IGNORECASE)
        if quarter_match:
            year = int(quarter_match.group(1))
            quarter = int(quarter_match.group(2))
            month = (quarter - 1) * 3 + 1
            return datetime(year, month, 1)
        
        # 尝试解析 "2024-12-31"（ISO格式）
        iso_match = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', time_str)
        if iso_match:
            year = int(iso_match.group(1))
            month = int(iso_match.group(2))
            day = int(iso_match.group(3))
            return datetime(year, month, day)
        
        # 兼容旧格式：尝试解析 "2024年"
        old_year_match = re.match(r'(\d{4})年', time_str)
        if old_year_match:
            year = int(old_year_match.group(1))
            return datetime(year, 1, 1)
        
        # 兼容旧格式：尝试解析 "2024年12月31日"
        old_date_match = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', time_str)
        if old_date_match:
            year = int(old_date_match.group(1))
            month = int(old_date_match.group(2))
            day = int(old_date_match.group(3))
            return datetime(year, month, day)
        
        # 兼容旧格式：尝试解析 "2024年12月"
        old_month_match = re.match(r'(\d{4})年(\d{1,2})月', time_str)
        if old_month_match:
            year = int(old_month_match.group(1))
            month = int(old_month_match.group(2))
            return datetime(year, month, 1)
        
        # 如果都解析失败，返回None
        return None
        
    except Exception as e:
        logger.warning(f"解析时间字符串失败: {time_str}, 错误: {str(e)}")
        return None


def _sort_timeline_by_time(timeline_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按时间顺序对时间轴事件进行排序
    
    Args:
        timeline_items: 时间轴事件列表
    
    Returns:
        排序后的时间轴事件列表
    """
    try:
        # 为每个事件添加排序键
        items_with_sort_key = []
        for item in timeline_items:
            time_str = item.get('time', '')
            parsed_time = _parse_time_string(time_str)
            
            if parsed_time:
                # 如果成功解析时间，使用解析后的datetime作为排序键
                items_with_sort_key.append((parsed_time, item))
            else:
                # 如果无法解析时间，尝试提取年份作为排序键
                year_match = re.search(r'(\d{4})', time_str)
                if year_match:
                    year = int(year_match.group(1))
                    # 使用年份的第一天作为排序键
                    items_with_sort_key.append((datetime(year, 1, 1), item))
                else:
                    # 如果完全无法解析，放在最后
                    items_with_sort_key.append((datetime(2099, 12, 31), item))
        
        # 按时间排序
        items_with_sort_key.sort(key=lambda x: x[0])
        
        # 提取排序后的事件
        sorted_items = [item for _, item in items_with_sort_key]
        
        logger.info(f"时间轴排序完成: {len(sorted_items)}个事件")
        if len(sorted_items) > 0:
            logger.info(f"最早事件: {sorted_items[0].get('time', '未知')}")
            logger.info(f"最晚事件: {sorted_items[-1].get('time', '未知')}")
        
        return sorted_items
        
    except Exception as e:
        logger.warning(f"时间轴排序失败: {str(e)}，返回原始顺序")
        return timeline_items

