"""
领域知识检索：在视图联动步骤3.5中，根据关键指标和用户查询从领域知识文档中检索相关段落。
"""

import os
import re
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# 领域知识目录（相对于本文件所在目录的 backend 根）
_DOMAIN_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "domain_knowledge"
_MAX_SNIPPET_CHARS = 1500


def retrieve_domain_knowledge(
    key_metrics: Optional[List[str]] = None,
    original_query: Optional[str] = None,
    max_chars: int = _MAX_SNIPPET_CHARS,
) -> str:
    """
    从 domain_knowledge 目录下的 Markdown 文件中，按关键词匹配检索相关段落。

    :param key_metrics: 视图关键指标列表，如 ["营收结构"]
    :param original_query: 用户原始查询，如 "营收结构三年演变"
    :param max_chars: 返回片段最大字符数
    :return: 拼接后的领域知识片段，无匹配时返回空字符串
    """
    key_metrics = key_metrics or []
    original_query = (original_query or "").strip()

    # 构建关键词列表：指标 + 查询中的可能词组（2字及以上）
    keywords = list(key_metrics)
    if original_query:
        # 简单分词：连续中文 2~8 字、英文/数字保留
        for part in re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z0-9]+", original_query):
            if part and part not in keywords:
                keywords.append(part)

    if not keywords:
        return ""

    if not _DOMAIN_KNOWLEDGE_DIR.exists() or not _DOMAIN_KNOWLEDGE_DIR.is_dir():
        logger.debug("领域知识目录不存在: %s", _DOMAIN_KNOWLEDGE_DIR)
        return ""

    collected: List[str] = []
    total_len = 0

    for md_path in sorted(_DOMAIN_KNOWLEDGE_DIR.glob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning("读取领域知识文件失败 %s: %s", md_path, e)
            continue

        # 按 ## 或 ### 拆成小节（保留标题行）
        sections = re.split(r"\n(?=#{2,3}\s)", text.strip())
        for section in sections:
            section = section.strip()
            if not section:
                continue
            if any(kw in section for kw in keywords if kw):
                if section not in collected and (total_len + len(section)) <= max_chars:
                    collected.append(section)
                    total_len += len(section)
                if total_len >= max_chars:
                    break
        if total_len >= max_chars:
            break

    if not collected:
        return ""

    snippet = "\n\n".join(collected)
    if len(snippet) > max_chars:
        snippet = snippet[: max_chars - 3] + "..."
    logger.info("领域知识检索命中 %d 段，共 %d 字符", len(collected), len(snippet))
    return snippet
