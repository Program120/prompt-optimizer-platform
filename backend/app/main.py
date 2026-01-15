from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys
from loguru import logger as loguru_logger
import logging
from app.db import storage
from app.api.routers import config, upload, projects, tasks, auto_iterate, global_models, knowledge_base, playground

# 创建 logs 目录
if not os.path.exists("logs"):
    os.makedirs("logs")

# 移除默认 handler
loguru_logger.remove()

# 统一日志格式
LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"

# 添加控制台输出 (默认为 INFO)
console_handler_id = loguru_logger.add(sys.stderr, level="INFO", format=LOG_FORMAT)

# 统一配置参数
LOG_CONFIG = {
    "rotation": "100 MB",
    "retention": "3 days",
    "encoding": "utf-8",
    "format": LOG_FORMAT
}

# 添加文件 Handler (按级别分文件)
# debug 包含所有级别, enqueue=True 确保线程安全
loguru_logger.add("logs/debug-{time:YYYY-MM-DD}.log", level="DEBUG", enqueue=True, **LOG_CONFIG)
# info 包含 INFO 及以上
loguru_logger.add("logs/info-{time:YYYY-MM-DD}.log", level="INFO", enqueue=True, **LOG_CONFIG)
# warn 包含 WARNING 及以上
loguru_logger.add("logs/warn-{time:YYYY-MM-DD}.log", level="WARNING", enqueue=True, **LOG_CONFIG)
# error 包含 ERROR 及以上
loguru_logger.add("logs/error-{time:YYYY-MM-DD}.log", level="ERROR", enqueue=True, **LOG_CONFIG)

class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = sys._getframe(3), 3
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

# 配置标准 logging 使用 Loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0)
logging.getLogger("uvicorn.access").handlers = [InterceptHandler()]
logging.getLogger("uvicorn.error").handlers = [InterceptHandler()]
logging.getLogger("fastapi").handlers = [InterceptHandler()]

# 重新赋值 logger 以兼容原有代码
logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置代理 (如果环境变量中存在)
if os.getenv("HTTP_PROXY"):
    os.environ["HTTP_PROXY"] = os.getenv("HTTP_PROXY")
if os.getenv("HTTPS_PROXY"):
    os.environ["HTTPS_PROXY"] = os.getenv("HTTPS_PROXY")

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """服务的生命周期管理 (替代 startup/shutdown 事件)"""
    loguru_logger.info("Service is starting... Checking dependencies...")
    try:
        import python_multipart
        loguru_logger.info("python-multipart is installed.")
    except ImportError:
        loguru_logger.error("Create: python-multipart module is missing! Form data parsing will fail.")
    
    # 执行数据迁移（从 JSON 到 SQLite）
    try:
        from scripts.migrate_to_sqlite import run_migration
        run_migration()
    except Exception as e:
        loguru_logger.warning(f"数据迁移检查失败（可能已完成或无需迁移）: {e}")
    
    yield
    loguru_logger.info("Service is shutting down...")

app = FastAPI(title="Prompt Optimizer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化存储
storage.init_storage()

# 注册路由
app.include_router(config.router)
app.include_router(upload.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(auto_iterate.router)
app.include_router(global_models.router)
app.include_router(knowledge_base.router)
app.include_router(playground.router)

# 挂载静态文件
app.mount("/data", StaticFiles(directory=storage.DATA_DIR), name="data")

from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """处理请求参数验证异常"""
    loguru_logger.error(f"Validation error: {exc.errors()} - Body: {exc.body}")
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    """处理 Starlette HTTP 异常 (如 400 Bad Request)"""
    loguru_logger.error(f"HTTP error: {exc.detail} - Request: {request.method} {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    """处理所有未捕获的异常"""
    loguru_logger.error(f"Unhandled exception: {exc} - Request: {request.method} {request.url}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)},
    )

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="运行 Prompt Optimizer API 服务")
    # 添加端口参数，默认 8000
    parser.add_argument("--port", type=int, default=8000, help="服务监听端口 (默认: 8000)")
    # 添加日志级别参数
    parser.add_argument("--log-level", type=str, default="INFO", help="控制台日志级别 (默认: INFO)")
    
    # 解析参数
    args = parser.parse_args()
    
    # 如果指定了非 INFO 级别，更新控制台日志配置
    if args.log_level.upper() != "INFO":
        loguru_logger.remove(console_handler_id)
        loguru_logger.add(sys.stderr, level=args.log_level.upper(), format=LOG_FORMAT)
        loguru_logger.info(f"Console log level set to: {args.log_level.upper()}")
    
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level=args.log_level.lower())
