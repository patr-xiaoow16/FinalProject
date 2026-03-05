# llamareport-end

重构版项目（与 `llamareport-test` 同层级），目录仅保留：
- `backend/`
- `frontend/`

## 架构改造（已落地）
- 共享检索入口：`backend/core/retrieval_hub.py`
- 仅检索缓存（不缓存最终回答/可视化JSON）：`backend/core/rag_engine.py`
- 四场景 Runner 边界：`backend/core/scene_runners.py`
- QueryEngine 兼容适配层：`backend/core/query_engine_adapter.py`
- 统一契约：`backend/core/contracts.py`

## 已接入接口
- `/query/ask`：接入共享检索预热 + `chat_fast` 检索缓存
- `/query/comprehensive-analysis`：接入 `linkage_multi` 检索预热
- `/agent/*`：ReportAgent 初始化改为使用缓存适配 QueryEngine（章节工具内部复用共享检索池）

## 清理项
- 删除 `frontend/node_modules`、`frontend/dist`
- 删除 `backend/__pycache__`
- 清空 `backend/storage/*`、`backend/uploads/*`
- 删除 backend 根目录下非运行必需 markdown 文档

## 运行
后端：
```bash
cd backend
pip install -r requirements.txt
python main.py
```

前端：
```bash
cd frontend
npm install
npm run dev
```

## 缓存说明
- 仅缓存检索证据（context/sources）
- 不缓存最终回答与可视化 JSON
- 缓存 TTL 可通过 `RETRIEVAL_CACHE_TTL_SECONDS` 调整（默认 900 秒）
