"""
LlamaReport Test - Backend
简化版财务报告分析后端
主要功能：文档处理、表格提取、RAG问答
"""

import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# 导入API路由
from api.upload import router as upload_router
from api.process import router as process_router
from api.query import router as query_router
from api.agent import router as agent_router
from config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('llamareport-backend.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    logger.info("🚀 LlamaReport Backend 启动中...")
    
    # 确保必要的目录存在
    directories = ["uploads", "storage", "storage/chroma"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        logger.info(f"✅ 目录已创建: {directory}")
    
    # 检查环境变量
    required_env_vars = {
        "OPENAI_API_KEY": "用于 Embedding 模型",
        "DEEPSEEK_API_KEY": "用于对话模型"
    }
    missing_vars = []
    for var, purpose in required_env_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({purpose})")

    if missing_vars:
        logger.warning(f"⚠️ 缺少环境变量: {', '.join(missing_vars)}")
        logger.warning("⚠️ 某些功能可能无法正常工作")
    else:
        logger.info("✅ 环境变量检查通过")
        logger.info(f"✅ 对话模型: DeepSeek ({os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')})")
        logger.info(f"✅ 嵌入模型: OpenAI (text-embedding-3-small)")
    
    logger.info("✅ LlamaReport Backend 启动完成")
    
    yield
    
    # 关闭时执行
    logger.info("🛑 LlamaReport Backend 正在关闭...")
    logger.info("✅ LlamaReport Backend 已关闭")

# 创建FastAPI应用
app = FastAPI(
    title="LlamaReport Backend",
    description="简化版财务报告分析后端API",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载前端静态文件（从父目录的frontend文件夹）
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
    logger.info(f"✅ 前端静态文件目录已挂载: {frontend_dir}")
else:
    logger.warning(f"⚠️ 前端目录不存在: {frontend_dir}")

# 注册路由
app.include_router(upload_router)
app.include_router(process_router)
app.include_router(query_router)
app.include_router(agent_router)

@app.get("/")
async def root():
    """根路径 - 返回前端页面"""
    try:
        index_path = frontend_dir / "index.html"
        if not index_path.exists():
            logger.error(f"index.html 文件不存在: {index_path.absolute()}")
            raise HTTPException(status_code=404, detail="index.html 文件不存在")
        logger.info(f"返回 index.html: {index_path.absolute()}")
        return FileResponse(str(index_path))
    except Exception as e:
        logger.error(f"返回 index.html 失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"返回页面失败: {str(e)}")

@app.get("/api")
async def api_info():
    """API信息"""
    return JSONResponse(
        status_code=200,
        content={
            "message": "LlamaReport Backend API",
            "version": "1.0.0",
            "description": "简化版财务报告分析后端",
            "features": [
                "PDF文档上传",
                "文档内容提取",
                "表格数据分析",
                "RAG智能问答"
            ],
            "endpoints": {
                "upload": "/upload - 文件上传相关接口",
                "process": "/process - 文档处理相关接口",
                "query": "/query - 查询问答相关接口",
                "docs": "/docs - API文档",
                "health": "/health - 健康检查"
            }
        }
    )

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查基本系统状态
        health_status = {
            "status": "healthy",
            "timestamp": str(Path().cwd()),
            "system_info": {
                "python_version": "3.x",
                "fastapi_running": True,
                "directories": {}
            }
        }
        
        # 检查目录状态
        directories = ["uploads", "storage", "storage/chroma"]
        for directory in directories:
            dir_path = Path(directory)
            health_status["system_info"]["directories"][directory] = {
                "exists": dir_path.exists(),
                "is_directory": dir_path.is_dir() if dir_path.exists() else False
            }
        
        # 检查环境变量
        env_status = {}
        required_env_vars = ["OPENAI_API_KEY"]
        for var in required_env_vars:
            env_status[var] = "configured" if os.getenv(var) else "missing"
        
        health_status["environment"] = env_status
        
        # 检查是否有任何问题
        has_issues = False
        issues = []
        
        # 检查目录问题
        for directory, info in health_status["system_info"]["directories"].items():
            if not info["exists"] or not info["is_directory"]:
                has_issues = True
                issues.append(f"目录问题: {directory}")
        
        # 检查环境变量问题
        for var, status in env_status.items():
            if status == "missing":
                has_issues = True
                issues.append(f"环境变量缺失: {var}")
        
        if has_issues:
            health_status["status"] = "degraded"
            health_status["issues"] = issues
        
        return JSONResponse(
            status_code=200 if not has_issues else 206,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.get("/info")
async def get_system_info():
    """获取系统信息"""
    try:
        # 获取上传文件信息
        upload_dir = Path("uploads")
        uploaded_files = 0
        total_size = 0
        
        if upload_dir.exists():
            for file_path in upload_dir.iterdir():
                if file_path.is_file():
                    uploaded_files += 1
                    total_size += file_path.stat().st_size
        
        # 获取存储信息
        storage_dir = Path("storage")
        storage_size = 0
        
        if storage_dir.exists():
            for file_path in storage_dir.rglob("*"):
                if file_path.is_file():
                    storage_size += file_path.stat().st_size
        
        system_info = {
            "application": {
                "name": "LlamaReport Backend",
                "version": "1.0.0",
                "description": "简化版财务报告分析后端"
            },
            "capabilities": {
                "supported_formats": [".pdf"],
                "max_file_size": "50MB",
                "max_batch_size": 10,
                "features": [
                    "PDF文档解析",
                    "表格数据提取",
                    "向量索引构建",
                    "智能问答查询"
                ]
            },
            "storage": {
                "uploaded_files": uploaded_files,
                "total_upload_size": f"{total_size / (1024*1024):.2f} MB",
                "storage_size": f"{storage_size / (1024*1024):.2f} MB"
            },
            "configuration": {
                "llm_provider": "DeepSeek",
                "llm_model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
                "llm_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
                "embedding_provider": "OpenAI",
                "embedding_model": "text-embedding-3-small",
                "embedding_configured": bool(os.getenv("OPENAI_API_KEY"))
            }
        }
        
        return JSONResponse(status_code=200, content=system_info)
        
    except Exception as e:
        logger.error(f"获取系统信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取系统信息失败: {str(e)}")

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """404错误处理"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "接口不存在",
            "message": f"请求的路径 {request.url.path} 不存在",
            "available_endpoints": [
                "/",
                "/health",
                "/info",
                "/upload/*",
                "/process/*", 
                "/query/*",
                "/docs"
            ]
        }
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    """500错误处理"""
    logger.error(f"内部服务器错误: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "message": "服务器遇到了一个错误，请稍后重试"
        }
    )

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 开发环境运行配置
    # 可以通过环境变量 RELOAD=false 来禁用自动重载（避免中断长时间运行的Agent查询）
    reload_enabled = os.getenv("RELOAD", "true").lower() != "false"
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload_enabled,
        log_level="info",
        # 排除某些目录，减少不必要的重载
        reload_excludes=["*.pyc", "__pycache__", "*.log", "*.tmp"]
    )
