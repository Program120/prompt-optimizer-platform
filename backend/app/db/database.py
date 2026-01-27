"""
数据库连接与会话管理模块
使用 SQLModel + SQLite 进行数据持久化
"""
import os
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import event
from loguru import logger

# 数据库文件路径
DATA_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'app.db')}"

# 创建数据库引擎
# check_same_thread=False 允许在多线程环境下使用（FastAPI 需要）
# timeout=30 设置 30 秒超时，避免长时间锁等待
engine = create_engine(
    DATABASE_URL, 
    echo=False,  # 设置为 True 可以打印 SQL 语句用于调试
    connect_args={
        "check_same_thread": False,
        "timeout": 30  # 30秒超时，避免长时间锁等待
    }
)


def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """
    设置 SQLite 连接参数
    在每个连接建立时自动调用，启用 WAL 模式和超时设置
    
    :param dbapi_connection: 数据库 API 连接
    :param connection_record: 连接记录
    """
    cursor = dbapi_connection.cursor()
    # 启用 WAL 模式：提升并发读写性能，减少锁冲突
    cursor.execute("PRAGMA journal_mode=WAL")
    # 设置 30 秒的忙等待超时
    cursor.execute("PRAGMA busy_timeout=30000")
    # 启用外键约束
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# 注册连接事件监听器
event.listen(engine, "connect", _set_sqlite_pragma)


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
    from app.models import (
        Project, ProjectIteration, Task, TaskResult, TaskError,
        GlobalModel, ModelConfig, AutoIterateStatus, IntentIntervention,
        PlaygroundHistory
    )
    
    # 创建所有表
    SQLModel.metadata.create_all(engine)
    logger.info("数据库表初始化完成")
    
    # 执行数据库迁移（添加新字段）
    _migrate_database()


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


def _migrate_database() -> None:
    """
    执行数据库迁移
    检查并添加新字段到已存在的表中
    """
    from sqlalchemy import text, inspect
    
    with Session(engine) as session:
        inspector = inspect(engine)
        
        # 迁移 global_models 表：添加 do_sample 字段
        if "global_models" in inspector.get_table_names():
            columns: list = [col["name"] for col in inspector.get_columns("global_models")]
            if "do_sample" not in columns:
                try:
                    session.execute(text("ALTER TABLE global_models ADD COLUMN do_sample INTEGER DEFAULT 0"))
                    session.commit()
                    logger.info("[迁移] global_models 表添加 do_sample 字段成功")
                except Exception as e:
                    logger.warning(f"[迁移] global_models 表添加 do_sample 字段失败（可能已存在）: {e}")
        
        # 迁移 model_config 表：添加 do_sample 字段
        if "model_config" in inspector.get_table_names():
            columns: list = [col["name"] for col in inspector.get_columns("model_config")]
            if "do_sample" not in columns:
                try:
                    session.execute(text("ALTER TABLE model_config ADD COLUMN do_sample INTEGER DEFAULT 0"))
                    session.commit()
                    logger.info("[迁移] model_config 表添加 do_sample 字段成功")
                except Exception as e:
                    logger.warning(f"[迁移] model_config 表添加 do_sample 字段失败（可能已存在）: {e}")
        
        # 迁移 playground_history 表：添加 is_favorite 字段
        if "playground_history" in inspector.get_table_names():
            columns: list = [col["name"] for col in inspector.get_columns("playground_history")]
            if "is_favorite" not in columns:
                try:
                    session.execute(text("ALTER TABLE playground_history ADD COLUMN is_favorite INTEGER DEFAULT 0"))
                    session.commit()
                    logger.info("[迁移] playground_history 表添加 is_favorite 字段成功")
                except Exception as e:
                    logger.warning(f"[迁移] playground_history 表添加 is_favorite 字段失败（可能已存在）: {e}")
