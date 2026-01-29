# LlamaReport Test

智能文档分析与问答系统

## 项目结构

```
llamareport-test/
├── backend/          # 后端代码
│   ├── api/         # API路由
│   ├── agents/      # Agent相关
│   ├── core/        # 核心功能
│   ├── models/      # 数据模型
│   ├── templates/   # 模板文件
│   ├── scripts/     # 脚本文件
│   ├── uploads/     # 上传文件目录
│   ├── storage/     # 存储目录
│   ├── main.py      # 主入口
│   ├── config.py    # 配置文件
│   └── requirements.txt
│
└── frontend/        # 前端代码
    ├── index.html
    ├── app.js
    └── style.css
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

在 `backend` 目录创建 `.env` 文件：

```env
OPENAI_API_KEY=your_openai_key
DEEPSEEK_API_KEY=your_deepseek_key
```

### 3. 启动后端

```bash
cd backend
python main.py
```

后端将在 `http://localhost:8000` 启动

### 4. 访问前端

浏览器访问: http://localhost:8000

## 功能特性

- ✅ PDF文档上传和处理
- ✅ 智能问答系统（RAG）
- ✅ Agent自动分析
- ✅ 数据可视化
- ✅ 杜邦分析
- ✅ 财务概况生成
- ✅ 财务点评生成

## API文档

启动后端后，访问 http://localhost:8000/docs 查看完整的API文档

## 技术栈

### 后端
- FastAPI
- LlamaIndex
- ChromaDB
- DeepSeek LLM
- OpenAI Embedding

### 前端
- Vue.js 3
- Marked.js (Markdown渲染)
- Plotly.js (数据可视化)

## 开发说明

### 后端开发

```bash
cd backend
python main.py
```

### 前端开发

前端文件位于 `frontend/` 目录：
- `index.html` - 主页面
- `app.js` - Vue应用主文件
- `style.css` - 样式文件

修改前端文件后，刷新浏览器即可看到更改（后端会自动重新加载）。

## 注意事项

1. 确保已安装 Python 3.11+
2. 确保已配置环境变量
3. 首次使用需要上传并处理PDF文档
4. 处理文档后会自动构建索引，可能需要几分钟
