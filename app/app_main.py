import sys
import os
from pathlib import Path

# 以项目根目录作为导入根目录，保证 ``app.xxx`` 和 ``agent.xxx`` 都能被解析。
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.router import chat
from app.service import chat_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Agent、模型与向量库在第一个聊天请求到来时才初始化，避免服务启动
    # 被 Milvus/Redis 连接和大规模依赖导入阻塞。
    yield
    if chat_service.memory is not None:
        await chat_service.memory.close()

app = FastAPI(title="Multi-Agent Cloud Service API", lifespan=lifespan)

# 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    # 默认不启用 reload，避免 Windows 上启动一个监控进程和一个服务进程，
    # 从而重复导入体积较大的 LangChain/Milvus 依赖。
    reload_enabled = os.getenv("APP_RELOAD", "false").lower() in {"1", "true", "yes"}
    uvicorn.run(
        "app.app_main:app" if reload_enabled else app,
        host="0.0.0.0",
        port=5000,
        reload=reload_enabled,
    )
