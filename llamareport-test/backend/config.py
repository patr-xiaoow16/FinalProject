"""
配置管理模块
集中管理所有配置项和环境变量
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # 基础配置
    APP_NAME = "LlamaReport Backend API"
    APP_VERSION = "1.0.0"
    APP_DESCRIPTION = "简化的年报分析后端API系统"
    
    # 服务器配置
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # API配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # 用于 Embedding
    LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

    # DeepSeek 配置 (用于对话模型)
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    
    # 文件配置
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50 * 1024 * 1024))  # 50MB
    ALLOWED_EXTENSIONS = {".pdf"}
    
    # 目录配置
    BASE_DIR = Path(__file__).parent
    UPLOADS_DIR = BASE_DIR / "uploads"
    STORAGE_DIR = BASE_DIR / "storage"
    
    # 确保目录存在
    UPLOADS_DIR.mkdir(exist_ok=True)
    STORAGE_DIR.mkdir(exist_ok=True)
    
    # ChromaDB配置
    CHROMA_PERSIST_DIR = str(STORAGE_DIR / "chroma")
    CHROMA_COLLECTION_NAME = "documents"
    
    # 处理配置
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1024))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
    
    # 查询配置
    SIMILARITY_TOP_K = int(os.getenv("SIMILARITY_TOP_K", 5))
    
    @classmethod
    def validate(cls):
        """验证必要的配置项"""
        errors = []
        warnings = []

        # OpenAI API Key (用于 Embedding)
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required for embeddings")

        # DeepSeek API Key (用于对话模型)
        if not cls.DEEPSEEK_API_KEY:
            errors.append("DEEPSEEK_API_KEY is required for chat completions")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        if warnings:
            print(f"⚠️ Configuration warnings: {', '.join(warnings)}")

        return True
    
    @classmethod
    def get_info(cls):
        """获取配置信息（不包含敏感信息）"""
        return {
            "app_name": cls.APP_NAME,
            "app_version": cls.APP_VERSION,
            "debug": cls.DEBUG,
            "max_file_size": cls.MAX_FILE_SIZE,
            "allowed_extensions": list(cls.ALLOWED_EXTENSIONS),
            "llm_provider": "DeepSeek",
            "llm_model": cls.DEEPSEEK_MODEL,
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "deepseek_configured": bool(cls.DEEPSEEK_API_KEY),
            "openai_configured": bool(cls.OPENAI_API_KEY),
            "llama_cloud_configured": bool(cls.LLAMA_CLOUD_API_KEY),
            "uploads_dir": str(cls.UPLOADS_DIR),
            "storage_dir": str(cls.STORAGE_DIR)
        }

# 创建配置实例
settings = Config()

# 在导入时验证配置（仅警告，不抛出异常）
try:
    Config.validate()
    print("[OK] Config validation passed")
except ValueError as e:
    print(f"[WARNING] Config validation warning: {e}")
    # 不抛出异常，允许应用继续运行
