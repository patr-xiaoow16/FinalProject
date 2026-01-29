# 文档与数据处理技术文档

## 一、系统概述

本系统是一个基于RAG（Retrieval-Augmented Generation）架构的财务报告智能分析系统，支持PDF和Excel格式的财务文档处理、结构化数据提取、向量索引构建和智能问答。

### 1.1 技术架构

```
用户上传文档
    ↓
文档处理层 (DocumentProcessor)
    ├─ PDF文档解析 (PDFReader + pdfplumber)
    └─ Excel文档解析 (ExcelProcessor)
    ↓
数据提取层 (TableExtractor)
    ├─ 表格识别与提取
    ├─ 财务表格分类
    └─ 表格重要性评分
    ↓
向量索引层 (RAGEngine + HybridRetriever)
    ├─ 文本向量化 (OpenAI Embedding)
    ├─ 向量存储 (ChromaDB)
    └─ 混合检索 (语义检索 + 指标匹配 + 年份过滤)
    ↓
智能问答层 (Query Engine)
    ├─ 查询增强
    ├─ 上下文过滤
    └─ LLM生成回答 (DeepSeek)
```

---

## 二、文档处理流程

### 2.1 文档上传与验证

**入口**：`/upload/file` API接口

**处理步骤**：

1. **文件验证**
   - 文件类型检查：支持 `.pdf`, `.xlsx`, `.xls`
   - 文件大小检查：最大50MB
   - 文件格式验证：尝试打开文件验证完整性

2. **文件存储**
   - 存储路径：`uploads/` 目录
   - 文件名处理：移除不安全字符，保留原始文件名
   - 文件元数据：记录文件名、大小、类型、创建时间

**代码位置**：`api/upload.py` (第22-83行)

### 2.2 PDF文档处理

**入口**：`DocumentProcessor.process_file()`

**处理流程**：

#### 步骤1：文档解析
- **工具1**：LlamaIndex PDFReader
  - 功能：提取PDF文本内容
  - 输出：Document对象列表（每个Document对应一页或一个文本块）
  - 元数据：文件名、页码、来源

- **工具2**：pdfplumber
  - 功能：提取详细内容（文本、表格、图片）
  - 输出：结构化页面数据
    ```python
    {
        'pages': [
            {
                'page_number': int,
                'text': str,           # 页面文本
                'tables': List[Dict],  # 表格数据
                'images': int,         # 图片数量
                'width': float,       # 页面宽度
                'height': float       # 页面高度
            }
        ],
        'metadata': Dict,             # PDF元数据
        'total_pages': int
    }
    ```

#### 步骤2：文档分块
- **方法**：TokenTextSplitter
- **参数**：
  - `chunk_size`: 1024 tokens（默认）
  - `chunk_overlap`: 200 tokens（默认，保证上下文连续性）
- **输出**：分块后的Document列表，每个块包含：
  - 文本内容
  - 元数据（chunk_id, total_chunks, page_number等）

**代码位置**：`core/document_processor.py` (第23-112行, 第173-207行)

### 2.3 Excel文档处理

**入口**：`ExcelProcessor.process_excel_file()`

**处理流程**：

#### 步骤1：工作表识别
- 读取所有工作表
- 识别财务报表类型（利润表、资产负债表、现金流量表）
- 识别方法：基于工作表名称和内容关键词匹配

#### 步骤2：表格数据提取
- 将每个工作表转换为Document对象
- 表格数据格式化为Markdown表格（使用 `|` 分隔符）
- 添加元数据：
  - `file_type`: 'excel'
  - `sheet_name`: 工作表名称
  - `is_financial_statement`: 是否为财务报表
  - `financial_statement_type`: 财务报表类型

**代码位置**：`core/excel_processor.py`（如果存在）

---

## 三、数据提取流程

### 3.1 表格提取

**入口**：`TableExtractor.extract_tables()`

**处理流程**：

#### 步骤1：表格识别
- **PDF表格**：从 `detailed_content['pages']` 中提取
  - 使用pdfplumber的 `extract_tables()` 方法
  - 每个表格包含：table_id, data（二维列表）, rows, cols

- **Excel表格**：从Document文本中解析
  - 解析Markdown格式的表格文本（`|` 分隔符）
  - 识别表头和数据行

#### 步骤2：表格清理
- **数据清理**（`_clean_table_data()`）：
  - 移除空行和空列
  - 清理单元格内容（移除多余空白）
  - 统一数据类型

- **转换为DataFrame**：
  - 第一行作为列名
  - 后续行作为数据
  - 处理列名缺失的情况

#### 步骤3：表格分析
- **财务表格识别**（`_is_financial_table()`）：
  - 检查列名中的财务关键词（营业收入、净利润、资产等）
  - 检查数据中的货币符号、百分比、数字模式
  - 计算财务特征分数（关键词匹配度 + 数据模式匹配度）

- **重要性评分**（`_calculate_importance_score()`）：
  - 表格大小（行数 × 列数）：权重 30%
  - 数据密度（非空单元格比例）：权重 30%
  - 数值列比例：权重 20%
  - 财务特征：权重 20%
  - 总分范围：0.0 - 1.0

- **表格摘要生成**（`_generate_table_summary()`）：
  - 基本信息：行数、列数
  - 数据类型：数值列数量
  - 财务特征：是否为财务表格
  - 列名示例：前3个列名

**输出格式**：
```python
{
    'table_id': str,              # 表格唯一标识
    'document': str,               # 来源文档
    'page_number': int,           # 页码
    'table_data': {
        'columns': List[str],      # 列名列表
        'data': List[List],       # 数据行（二维列表）
        'shape': Tuple[int, int]  # (行数, 列数)
    },
    'is_financial': bool,         # 是否为财务表格
    'importance_score': float,   # 重要性分数
    'summary': str                # 表格摘要
}
```

**代码位置**：`core/table_extractor.py` (第37-131行, 第176-236行)

---

## 四、向量索引构建流程

### 4.1 索引架构

系统采用**双通道索引架构**：

1. **主索引**（RAGEngine）：
   - 存储位置：ChromaDB (`storage/chroma/`)
   - 集合名称：`documents`
   - 内容：文本文档 + 表格文档（统一索引）

2. **混合检索索引**（HybridRetriever）：
   - 存储位置：ChromaDB (`storage/chroma_hybrid/`)
   - 集合1：`text_index`（文本文档）
   - 集合2：`table_index`（表格文档）

### 4.2 文档向量化

**嵌入模型**：OpenAI `text-embedding-3-small`
- 维度：1536维
- 特点：多语言支持，对中文财务术语理解良好

**向量化对象**：

1. **文本文档**：
   - 来源：PDF文本块、Excel工作表文本
   - 元数据：
     ```python
     {
         'source_file': str,           # 文件名
         'document_type': 'text_content',
         'page_number': int,           # 页码（PDF）或工作表编号（Excel）
         'is_financial_statement': bool, # 是否为财务报表
         'financial_statement_type': str # 财务报表类型
     }
     ```

2. **表格文档**：
   - 来源：提取的表格数据
   - 转换方法：`_table_to_text()`（将表格转换为Markdown格式文本）
   - 元数据：
     ```python
     {
         'source_file': str,
         'document_type': 'table_data',
         'table_id': str,
         'page_number': int,
         'is_financial': bool,
         'importance_score': float
     }
     ```

**表格转文本格式**：
```
================================================================================
📊 表格数据 - {table_id}
📄 来源页码: 第{page_number}页
💰 类型: 财务数据表格（如果是财务表格）
📝 表格摘要: {summary}

💰 **包含的财务指标**: {indicators}

**表格内容（Markdown格式）：**

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |
...

**表格维度**: {rows} 行 × {cols} 列
================================================================================
```

**代码位置**：`core/rag_engine.py` (第195-410行, 第412-501行)

### 4.3 索引构建策略

#### 增量索引模式（默认）
- **特点**：只索引新文件，保留已有索引
- **实现**：
  1. 检查已索引的文件列表（从ChromaDB元数据中提取 `source_file`）
  2. 过滤出需要索引的新文件
  3. 如果所有文件都已索引，跳过索引构建
  4. 如果有新文件，只对新文件进行向量化和索引

#### 重建索引模式
- **特点**：清空现有索引，重新构建
- **使用场景**：文档内容更新、索引损坏、需要重新优化

**代码位置**：`core/rag_engine.py` (第195-410行)

### 4.4 混合检索索引构建

**入口**：`HybridRetriever.build_hybrid_index()`

**处理流程**：

1. **文本索引构建**：
   - 从 `processed_documents` 中提取所有文本文档
   - 添加元数据：`doc_type='text'`, `channel='text_index'`
   - 构建向量索引并存储到 `text_index` 集合

2. **表格索引构建**：
   - 从 `extracted_tables` 中提取所有表格
   - 将表格转换为文本（`_table_to_text()`）
   - 添加元数据：
     - `doc_type='table'`
     - `channel='table_index'`
     - `indicator`: 表格摘要
     - `year`: 从表格中提取的年份
     - `is_financial`: 是否为财务表格
   - 构建向量索引并存储到 `table_index` 集合

**代码位置**：`core/hybrid_retriever.py` (第244-304行)

---

## 五、数据检索流程

### 5.1 查询处理

**入口**：`/query/ask` API接口

**处理流程**：

#### 步骤1：查询增强（`_enhance_query()`）
- **功能**：优化查询，提高检索精度
- **增强内容**：
  1. 添加明确指令：要求使用检索到的数据
  2. 提取财务关键词：识别查询中的财务指标
  3. 添加上下文过滤条件：公司名、年份、文档类型
  4. 添加回答要求：使用具体数据、提供来源、对比分析

**增强后查询格式**：
```
【重要指令】请仔细阅读下面检索到的文档内容，特别是表格数据，并基于这些具体数据来回答问题。
如果检索到的内容中包含表格，请务必分析表格中的数值数据。

【关键指标】本次查询重点关注以下财务指标: {keywords}
请优先检索和回答与这些指标相关的数据。

【用户问题】{original_question}

【查询条件】
- 公司: {company}
- 年份: {year} 年
- 文档类型: {document_type}

【回答要求】
1. 必须使用检索到的具体数据（特别是表格中的数值）
2. 如果数据不足，明确说明缺少哪些信息
3. 提供数据来源（页码、表格ID等）
4. 对于趋势分析，需要对比不同时期的数据
```

**代码位置**：`core/rag_engine.py` (第734-780行)

#### 步骤2：检索策略选择

**混合检索器**（HybridRetriever）自动选择策略：

1. **表格优先策略**（`table_first`）：
   - 触发条件：查询包含财务指标关键词（营业收入、净利润、资产等）
   - 或包含数值类关键词（增长率、数据、金额等）
   - 检索范围：仅 `table_index` 集合

2. **文本优先策略**（`text_first`）：
   - 触发条件：查询包含语义分析类关键词（表现如何、趋势说明、分析等）
   - 检索范围：仅 `text_index` 集合

3. **混合策略**（`hybrid`）：
   - 默认策略
   - 检索范围：`text_index` 和 `table_index` 各检索 top_k/2 个结果

**代码位置**：`core/hybrid_retriever.py` (第427-451行)

#### 步骤3：向量检索

**检索参数**：
- `similarity_top_k`: 20（扩大检索范围，后续会过滤和排序）
- 检索方法：余弦相似度（ChromaDB默认）

**检索结果**：
```python
[
    {
        'document': Document,      # 文档对象
        'semantic_score': float    # 语义相似度分数（0.0-1.0）
    }
]
```

**代码位置**：`core/rag_engine.py` (第503-732行)

#### 步骤4：综合评分与排序

**评分器**：`HybridRetrievalScorer`

**评分维度**：

1. **语义相似度**（权重：60%）：
   - 来源：向量检索的相似度分数
   - 范围：0.0 - 1.0

2. **指标匹配度**（权重：30%）：
   - 计算：检查查询中的财务指标是否在文档中出现
   - 公式：`matched_metrics / total_metrics`
   - 加分：如果文档是表格类型且包含财务指标，额外加分0.2

3. **年份一致性**（权重：10%）：
   - 计算：从查询中提取年份，与文档元数据中的年份匹配
   - 匹配：1.0，不匹配：0.0

4. **财务报表加分**（额外）：
   - 如果文档是财务报表：基础加分0.2
   - 如果财务报表类型与查询匹配：额外加分0.3

**综合评分公式**：
```python
base_score = (
    sim_score * 0.6 +
    metric_score * 0.3 +
    year_score * 0.1
)
comprehensive_score = min(1.0, base_score + financial_statement_bonus)
```

**代码位置**：`core/hybrid_retriever.py` (第46-100行)

#### 步骤5：上下文过滤

**过滤条件**：
- `filename`: 文件名（严格匹配）
- `company`: 公司名（从文件名或文档文本中匹配）
- `year`: 年份（精确匹配）
- `source_file`: 源文件（文件名别名）

**过滤逻辑**：

1. **文件名过滤**：
   - 标准化文件名（移除路径、统一大小写）
   - 完全匹配或关键部分匹配（至少前3个字符）

2. **公司名过滤**：
   - 优先从文件名中提取公司名（移除报表类型关键词和年份）
   - 检查文件名前3个字符是否匹配
   - 如果文件名匹配失败，检查文档文本中是否包含公司名
   - 最后检查元数据中的公司名

3. **年份过滤**：
   - 从文档元数据中提取年份
   - 与过滤条件中的年份精确匹配

**代码位置**：`core/hybrid_retriever.py` (第587-740行)

#### 步骤6：LLM生成回答

**输入**：
- 增强后的查询
- 检索到的文档上下文（Top-K结果）
- 系统提示词（强调使用表格数据）

**系统提示词**：
```
你是一个专业的财务分析助手。下面是从文档中检索到的相关内容：

{context_str}

请仔细阅读上述内容，特别注意其中的表格数据。如果内容中包含Markdown格式的表格，请务必分析表格中的具体数值。

用户问题：{query_str}

回答要求：
1. 必须基于检索到的具体数据回答，特别是表格中的数值
2. 如果找到相关数据，请引用具体数字和来源
3. 如果数据不足，明确说明缺少哪些信息
4. 对于趋势分析，需要对比不同时期的数据

请提供详细、准确的回答：
```

**LLM模型**：DeepSeek Chat
- 温度参数：0.1（保证回答的确定性和准确性）

**输出格式**：
```python
{
    'answer': str,                    # LLM生成的回答
    'sources': List[Dict],            # 来源信息列表
    'error': bool,                    # 是否有错误
    'original_question': str,         # 原始问题
    'enhanced_query': str             # 增强后的查询
}
```

**来源信息格式**：
```python
{
    'text': str,                      # 文档文本片段（前200字符）
    'metadata': Dict,                # 文档元数据
    'score': float,                   # 综合评分
    'sim_score': float,              # 语义相似度
    'metric_score': float,           # 指标匹配度
    'year_score': float              # 年份一致性
}
```

**代码位置**：`core/rag_engine.py` (第503-732行)

---

## 六、数据存储结构

### 6.1 文件存储

**目录结构**：
```
backend/
├── uploads/              # 上传的原始文件
│   ├── file1.pdf
│   └── file2.xlsx
└── storage/              # 处理后的数据
    ├── chroma/           # 主索引（ChromaDB）
    │   └── documents/    # 向量集合
    └── chroma_hybrid/    # 混合检索索引（ChromaDB）
        ├── text_index/   # 文本向量集合
        └── table_index/  # 表格向量集合
```

### 6.2 向量存储格式

**ChromaDB存储结构**：
- **ID**：文档唯一标识符
- **Embedding**：1536维向量（OpenAI embedding）
- **Metadata**：
  ```python
  {
      'source_file': str,              # 文件名
      'document_type': str,            # 'text_content' 或 'table_data'
      'page_number': int,              # 页码
      'table_id': str,                  # 表格ID（仅表格文档）
      'is_financial': bool,             # 是否为财务数据
      'importance_score': float,        # 重要性分数（仅表格）
      'is_financial_statement': bool,   # 是否为财务报表
      'financial_statement_type': str   # 财务报表类型
  }
  ```

### 6.3 索引统计信息

**获取方法**：`RAGEngine.get_index_stats()`

**返回格式**：
```python
{
    'status': str,              # 'ready' | 'not_initialized' | 'error'
    'document_count': int,      # 文档数量
    'vector_count': int,        # 向量数量
    'storage_dir': str,         # 存储目录
    'collection_name': str      # 集合名称
}
```

**代码位置**：`core/rag_engine.py` (第1002-1024行)

---

## 七、关键技术特点

### 7.1 混合检索机制

**优势**：
1. **双通道索引**：文本和表格分别索引，提高检索精度
2. **智能策略选择**：根据查询类型自动选择检索策略
3. **综合评分**：结合语义相似度、指标匹配度、年份一致性
4. **财务报表优先**：财务报表文档获得额外加分

### 7.2 增量索引机制

**优势**：
1. **性能优化**：只处理新文件，避免重复索引
2. **存储效率**：保留已有索引，节省存储空间
3. **灵活性**：支持单文件索引和批量索引

### 7.3 上下文过滤机制

**优势**：
1. **精确匹配**：支持文件名、公司名、年份多维度过滤
2. **智能匹配**：公司名匹配支持文件名提取和文本匹配
3. **灵活扩展**：易于添加新的过滤条件

### 7.4 表格数据优化

**优势**：
1. **Markdown格式**：表格转换为Markdown，便于LLM理解
2. **元数据丰富**：包含财务指标、重要性评分等信息
3. **结构化存储**：表格数据以结构化格式存储，便于后续分析

---

## 八、性能指标

### 8.1 处理性能

- **PDF处理速度**：约 1-2 页/秒（取决于页面复杂度）
- **Excel处理速度**：约 1-2 工作表/秒
- **表格提取速度**：约 10-20 表格/秒
- **向量化速度**：约 100-200 文档/分钟（取决于API限制）

### 8.2 检索性能

- **向量检索延迟**：< 100ms（ChromaDB本地检索）
- **混合检索延迟**：< 200ms（包含评分和排序）
- **LLM生成延迟**：2-10秒（取决于回答长度和API响应时间）

### 8.3 存储容量

- **向量存储**：每个向量约 6KB（1536维 × 4字节）
- **元数据存储**：每个文档约 1-2KB
- **总存储**：1000个文档约 7-8MB

---

## 九、错误处理与容错机制

### 9.1 文档处理错误

- **文件格式错误**：返回明确的错误信息，不中断处理流程
- **解析失败**：记录警告日志，跳过失败页面，继续处理其他页面
- **表格提取失败**：使用Fallback方法，尝试其他提取策略

### 9.2 索引构建错误

- **向量化失败**：记录错误，跳过失败文档，继续处理其他文档
- **存储失败**：回滚操作，清空部分索引，记录详细错误日志
- **索引损坏**：提供重建索引接口，支持完全重建

### 9.3 检索错误

- **索引未初始化**：自动尝试加载现有索引
- **检索结果为空**：返回友好的提示信息，建议用户检查查询条件
- **LLM生成失败**：返回检索到的原始文档片段，不中断流程

---

## 十、总结

本系统实现了从文档上传到智能问答的完整流程，核心特点包括：

1. **多格式支持**：PDF和Excel文档的统一处理
2. **结构化提取**：表格数据的精确识别和提取
3. **混合检索**：语义检索 + 指标匹配 + 年份过滤的综合检索机制
4. **增量索引**：高效的索引更新机制
5. **上下文过滤**：精确的文档过滤能力
6. **智能问答**：基于RAG架构的准确回答生成

整个系统设计注重**可扩展性**、**可维护性**和**性能优化**，为财务报告分析提供了强大的技术支撑。


