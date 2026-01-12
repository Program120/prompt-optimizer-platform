from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
import storage
from routers import config, upload, projects, tasks, auto_iterate

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 设置代理 (根据用户提供的信息)
os.environ["HTTP_PROXY"] = "http://192.168.91.1:7890"
os.environ["HTTPS_PROXY"] = "http://192.168.91.1:7890"

app = FastAPI(title="Prompt Optimizer API")

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

# 挂载静态文件
app.mount("/data", StaticFiles(directory=storage.DATA_DIR), name="data")

if __name__ == "__main__":
    import uvicorn
    import argparse
    
    # 创建参数解析器
    parser = argparse.ArgumentParser(description="运行 Prompt Optimizer API 服务")
    # 添加端口参数，默认 8000
    parser.add_argument("--port", type=int, default=8000, help="服务监听端口 (默认: 8000)")
    # 解析参数
    args = parser.parse_args()
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
