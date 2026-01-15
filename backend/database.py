"""
数据库连接与会话管理模块
使用 SQLModel + SQLite 进行数据持久化
"""
import os
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from loguru import logger

# 数据库文件路径
DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"

# 创建数据库引擎
# check_same_thread=False 允许在多线程环境下使用（FastAPI 需要）
engine = create_engine(
    DATABASE_URL, 
    echo=False,  # 设置为 True 可以打印 SQL 语句用于调试
    connect_args={"check_same_thread": False}
)


def init_db() -> None:
    """
    初始化数据库，创建所有表
    应在应用启动时调用
    """
    # 确保数据目录存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"创建数据目录: {DATA_DIR}")
    
    # 导入所有模型以确保它们被注册
    from models import (
        Project, ProjectIteration, Task, TaskResult, TaskError,
        GlobalModel, ModelConfig, AutoIterateStatus
    )
    
    # 创建所有表
    SQLModel.metadata.create_all(engine)
    logger.info("数据库表初始化完成")


def get_session() -> Generator[Session, None, None]:
    """
    获取数据库会话的依赖注入函数
    用于 FastAPI 的 Depends
    
    :yield: 数据库会话对象
    """
    with Session(engine) as session:
        yield session


def get_db_session() -> Session:
    """
    获取数据库会话（用于非依赖注入场景）
    
    :return: 数据库会话对象
    """
    return Session(engine)
