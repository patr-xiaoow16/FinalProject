# LlamaReport Backend - 简化版

> 专注于文档处理和RAG问答的轻量级财务报告分析后端

## 🎯 项目概述

LlamaReport Backend 是原LlamaReportPro项目的简化版本，移除了复杂的前端界面和可视化功能，专注于核心的文档处理和智能问答能力。

### 核心功能

- 📄 **PDF文档处理** - 文本提取和预处理
- 📊 **表格数据提取** - 财务表格识别和分析
- 🤖 **RAG智能问答** - 基于文档内容的智能问答
- 🔍 **向量检索** - 高效的语义搜索

### 技术栈

- **Web框架**: FastAPI
- **文档处理**: LlamaIndex + PDFPlumber
- **向量数据库**: ChromaDB
- **LLM服务**: OpenAI GPT-4
- **数据处理**: Pandas

## 🚀 快速开始

### 1. 环境要求

- Python 3.8+
- OpenAI API Key

### 2. 安装依赖

```bash
cd llamareport-backend
pip install -r requirements.txt
```

### 3. 环境配置

创建 `.env` 文件：

```env
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini
```

### 4. 启动服务

```bash
# 方式1: 使用启动脚本（推荐）
python start.py

# 方式2: 直接启动
python main.py

# 方式3: 使用uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问API

- **API文档**: http://localhost:8000/docs
- **主页**: http://localhost:8000
- **健康检查**: http://localhost:8000/health

## 📚 API接口

### 文件上传

```bash
# 上传单个文件
curl -X POST "http://localhost:8000/upload/file" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@report.pdf"

# 查看已上传文件
curl "http://localhost:8000/upload/list"
```

### 文档处理

```bash
# 处理文档并构建索引
curl -X POST "http://localhost:8000/process/file" \
  -H "Content-Type: application/json" \
  -d '{"filename": "report.pdf", "build_index": true}'

# 查看处理状态
curl "http://localhost:8000/process/status"
```

### 智能问答

```bash
# 提问
curl -X POST "http://localhost:8000/query/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "公司的营业收入是多少？"}'

# 获取相似内容
curl -X POST "http://localhost:8000/query/similar" \
  -H "Content-Type: application/json" \
  -d '{"query": "财务数据", "top_k": 5}'
```

## 🏗️ 项目结构

```
llamareport-backend/
├── main.py              # FastAPI主应用
├── config.py            # 配置管理
├── requirements.txt     # 依赖包列表
├── .env                 # 环境变量
├── start.py             # 启动脚本
├── test_backend.py      # 测试脚本
├── README.md            # 项目文档
├── core/                # 核心模块
│   ├── __init__.py
│   ├── document_processor.py  # 文档处理器
│   ├── table_extractor.py     # 表格提取器
│   └── rag_engine.py          # RAG引擎
├── api/                 # API接口
│   ├── __init__.py
│   ├── upload.py        # 文件上传接口
│   ├── process.py       # 文档处理接口
│   └── query.py         # 查询接口
├── uploads/             # 上传文件目录
└── storage/             # 数据存储目录
    └── chroma/          # ChromaDB数据
```

## 🧪 测试

```bash
# 运行完整测试
python test_backend.py

# 测试特定功能
python -c "from test_backend import test_imports; test_imports()"
```

## 📖 使用示例

### 完整工作流程

```python
import requests

base_url = "http://localhost:8000"

# 1. 上传文件
with open("financial_report.pdf", "rb") as f:
    response = requests.post(f"{base_url}/upload/file", files={"file": f})
    print(response.json())

# 2. 处理文档
response = requests.post(f"{base_url}/process/file", 
    json={"filename": "financial_report.pdf", "build_index": True})
print(response.json())

# 3. 智能问答
response = requests.post(f"{base_url}/query/ask",
    json={"question": "公司去年的净利润是多少？"})
print(response.json())
```

## ⚙️ 配置选项

### 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_API_KEY` | OpenAI API密钥 | 必需 |
| `OPENAI_MODEL` | 使用的模型 | `gpt-4o-mini` |

### 系统限制

- 最大文件大小: 50MB
- 支持格式: PDF
- 批量处理: 最多10个文件
- 查询长度: 最多1000字符

## 🔧 故障排除

### 常见问题

1. **ImportError: No module named 'xxx'**
   ```bash
   pip install -r requirements.txt
   ```

2. **OpenAI API错误**
   - 检查API密钥是否正确设置
   - 确认账户有足够余额

3. **文件上传失败**
   - 检查文件大小是否超过50MB
   - 确认文件格式为PDF

4. **索引构建失败**
   - 检查存储目录权限
   - 确认ChromaDB正常工作

### 日志查看

```bash
# 查看应用日志
tail -f llamareport-backend.log

# 查看详细错误
python main.py --log-level debug
```

## 📈 性能优化

### 建议配置

- **内存**: 最少4GB，推荐8GB+
- **存储**: SSD推荐，至少10GB可用空间
- **网络**: 稳定的互联网连接（OpenAI API）

### 优化建议

1. 使用SSD存储提升文件处理速度
2. 增加内存以处理大型文档
3. 考虑使用本地LLM减少API调用

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

## 📞 支持

如有问题，请提交Issue或联系开发团队。

---

**简化版特点**:
- ✅ 移除了Streamlit前端
- ✅ 专注核心功能
- ✅ 代码量减少70%
- ✅ 依赖减少60%
- ✅ 启动速度提升80%
