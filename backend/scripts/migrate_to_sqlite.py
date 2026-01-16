"""
数据迁移脚本
将现有 JSON 文件数据迁移到 SQLite 数据库
"""
import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any
from loguru import logger

# 添加 backend 到路径
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.database import init_db, get_db_session, DATA_DIR
    Project, ProjectIteration, Task, TaskResult, TaskError,
    GlobalModel, ModelConfig, AutoIterateStatus, ProjectReason
)


def backup_json_files() -> None:
    """
    备份原有 JSON 文件到 backup 目录
    """
    backup_dir: str = os.path.join(DATA_DIR, "backup_json")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 需要备份的文件模式
    patterns: List[str] = [
        "projects.json",
        "model_config.json", 
        "global_models.json"
    ]
    
    for filename in os.listdir(DATA_DIR):
        if filename in patterns or filename.startswith("task_") or filename.startswith("auto_iterate_"):
            src: str = os.path.join(DATA_DIR, filename)
            dst: str = os.path.join(backup_dir, filename)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                logger.info(f"备份文件: {filename}")


def load_json_file(filepath: str) -> Any:
    """
    安全加载 JSON 文件
    """
    if not os.path.exists(filepath):
        return None
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return json.loads(content)
    except json.JSONDecodeError as e:
        # 尝试修复 "Extra data" 错误
        if "Extra data" in str(e):
            logger.warning(f"检测到损坏的 JSON 文件 {filepath}，尝试修复...")
            try:
                return json.loads(content[:e.pos])
            except Exception:
                pass
        logger.error(f"无法加载 JSON 文件 {filepath}: {e}")
        return None


def migrate_projects() -> int:
    """
    迁移项目数据
    
    :return: 迁移的项目数量
    """
    projects_file: str = os.path.join(DATA_DIR, "projects.json")
    projects_data: List[Dict[str, Any]] = load_json_file(projects_file) or []
    
    if not projects_data:
        logger.info("没有找到项目数据，跳过迁移")
        return 0
    
    count: int = 0
    with get_db_session() as session:
        for proj_dict in projects_data:
            # 检查是否已存在
            existing = session.get(Project, proj_dict.get("id"))
            if existing:
                logger.debug(f"项目已存在，跳过: {proj_dict.get('id')}")
                continue
            
            # 创建项目
            project = Project(
                id=proj_dict.get("id", datetime.now().strftime("%Y%m%d%H%M%S")),
                name=proj_dict.get("name", ""),
                current_prompt=proj_dict.get("current_prompt", ""),
                last_task_id=proj_dict.get("last_task_id"),
                config=json.dumps(proj_dict.get("config", {}), ensure_ascii=False),
                model_config_data=json.dumps(proj_dict.get("model_config", {}), ensure_ascii=False),
                optimization_model_config=json.dumps(proj_dict.get("optimization_model_config", {}), ensure_ascii=False),
                optimization_prompt=proj_dict.get("optimization_prompt", ""),
                created_at=proj_dict.get("created_at", datetime.now().isoformat()),
                updated_at=proj_dict.get("updated_at")
            )
            session.add(project)
            
            # 迁移迭代记录
            iterations: List[Dict[str, Any]] = proj_dict.get("iterations", [])
            for idx, iter_data in enumerate(iterations):
                iteration = ProjectIteration(
                    project_id=project.id,
                    version=iter_data.get("version", idx + 1),
                    previous_prompt=iter_data.get("previous_prompt", ""),
                    optimized_prompt=iter_data.get("optimized_prompt", ""),
                    strategy=iter_data.get("strategy", ""),
                    accuracy_before=iter_data.get("accuracy_before", 0.0),
                    accuracy_after=iter_data.get("accuracy_after"),
                    task_id=iter_data.get("task_id"),
                    analysis=json.dumps(iter_data.get("analysis", {}), ensure_ascii=False),
                    note=iter_data.get("note", ""),
                    created_at=iter_data.get("created_at", datetime.now().isoformat())
                )
                session.add(iteration)
            
            count += 1
            logger.info(f"迁移项目: {project.id} - {project.name}")
        
        session.commit()
    
    return count


def migrate_tasks() -> int:
    """
    迁移任务数据
    
    :return: 迁移的任务数量
    """
    count: int = 0
    
    for filename in os.listdir(DATA_DIR):
        if not (filename.startswith("task_") and filename.endswith(".json")):
            continue
        
        filepath: str = os.path.join(DATA_DIR, filename)
        task_data: Dict[str, Any] = load_json_file(filepath)
        
        if not task_data:
            continue
        
        task_id: str = task_data.get("id", filename.replace(".json", ""))
        
        with get_db_session() as session:
            # 检查是否已存在
            existing = session.get(Task, task_id)
            if existing:
                logger.debug(f"任务已存在，跳过: {task_id}")
                continue
            
            # 创建任务
            extra_fields = {k: v for k, v in task_data.items() if k not in [
                "id", "project_id", "status", "current_index", "total_count",
                "prompt", "file_path", "original_filename", "note", "results", "errors", "created_at"
            ]}
            
            task = Task(
                id=task_id,
                project_id=task_data.get("project_id", ""),
                status=task_data.get("status", "completed"),
                current_index=task_data.get("current_index", 0),
                total_count=task_data.get("total_count", 0),
                prompt=task_data.get("prompt", ""),
                file_path=task_data.get("file_path", ""),
                original_filename=task_data.get("original_filename", ""),
                note=task_data.get("note", ""),
                created_at=task_data.get("created_at", datetime.now().isoformat()),
                extra_config=json.dumps(extra_fields, ensure_ascii=False)
            )
            session.add(task)
            
            # 迁移结果
            for result_data in task_data.get("results", []):
                extra_data = {k: v for k, v in result_data.items() if k not in ["query", "target", "output", "is_correct", "reason"]}
                result = TaskResult(
                    task_id=task_id,
                    query=result_data.get("query", ""),
                    target=result_data.get("target", ""),
                    output=result_data.get("output", ""),
                    is_correct=result_data.get("is_correct", False),
                    reason=result_data.get("reason", ""),
                    extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"
                )
                session.add(result)
            
            # 迁移错误
            for error_data in task_data.get("errors", []):
                extra_data = {k: v for k, v in error_data.items() if k not in ["query", "target", "output", "reason"]}
                error = TaskError(
                    task_id=task_id,
                    query=error_data.get("query", ""),
                    target=error_data.get("target", ""),
                    output=error_data.get("output", ""),
                    reason=error_data.get("reason", ""),
                    extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"
                )
                session.add(error)
            
            session.commit()
            count += 1
            logger.info(f"迁移任务: {task_id}")
    
    return count


def migrate_global_models() -> int:
    """
    迁移公共模型配置
    
    :return: 迁移的模型数量
    """
    models_file: str = os.path.join(DATA_DIR, "global_models.json")
    models_data: List[Dict[str, Any]] = load_json_file(models_file) or []
    
    if not models_data:
        logger.info("没有找到公共模型配置数据，跳过迁移")
        return 0
    
    count: int = 0
    with get_db_session() as session:
        for model_dict in models_data:
            model_id: str = model_dict.get("id", datetime.now().strftime("%Y%m%d%H%M%S%f"))
            
            # 检查是否已存在
            existing = session.get(GlobalModel, model_id)
            if existing:
                logger.debug(f"模型配置已存在，跳过: {model_id}")
                continue
            
            model = GlobalModel(
                id=model_id,
                name=model_dict.get("name", "未命名模型"),
                base_url=model_dict.get("base_url", ""),
                api_key=model_dict.get("api_key", ""),
                model_name=model_dict.get("model_name", "gpt-3.5-turbo"),
                max_tokens=model_dict.get("max_tokens", 2000),
                temperature=model_dict.get("temperature", 0.0),
                timeout=model_dict.get("timeout", 60),
                concurrency=model_dict.get("concurrency", 5),
                extra_body=json.dumps(model_dict.get("extra_body")) if model_dict.get("extra_body") else "",
                default_headers=json.dumps(model_dict.get("default_headers")) if model_dict.get("default_headers") else "",
                created_at=model_dict.get("created_at", datetime.now().isoformat()),
                updated_at=model_dict.get("updated_at", datetime.now().isoformat())
            )
            session.add(model)
            count += 1
            logger.info(f"迁移模型配置: {model_id} - {model.name}")
        
        session.commit()
    
    return count


def migrate_model_config() -> bool:
    """
    迁移系统模型配置
    
    :return: 是否成功迁移
    """
    config_file: str = os.path.join(DATA_DIR, "model_config.json")
    config_data: Dict[str, Any] = load_json_file(config_file)
    
    if not config_data:
        logger.info("没有找到系统模型配置数据，跳过迁移")
        return False
    
    with get_db_session() as session:
        # 检查是否已存在
        existing = session.get(ModelConfig, 1)
        if existing:
            logger.debug("系统模型配置已存在，跳过迁移")
            return False
        
        config = ModelConfig(
            id=1,
            base_url=config_data.get("base_url", "https://api.openai.com/v1"),
            api_key=config_data.get("api_key", ""),
            max_tokens=config_data.get("max_tokens", 2000),
            timeout=config_data.get("timeout", 60),
            model_name=config_data.get("model_name", "gpt-3.5-turbo"),
            temperature=config_data.get("temperature", 0.0)
        )
        session.add(config)
        session.commit()
        logger.info("迁移系统模型配置完成")
    
    return True


def migrate_auto_iterate_status() -> int:
    """
    迁移自动迭代状态
    
    :return: 迁移的状态数量
    """
    count: int = 0
    
    for filename in os.listdir(DATA_DIR):
        if not (filename.startswith("auto_iterate_") and filename.endswith(".json")):
            continue
        
        filepath: str = os.path.join(DATA_DIR, filename)
        status_data: Dict[str, Any] = load_json_file(filepath)
        
        if not status_data:
            continue
        
        # 从文件名提取项目 ID
        project_id: str = filename.replace("auto_iterate_", "").replace(".json", "")
        
        with get_db_session() as session:
            # 检查是否已存在
            existing = session.get(AutoIterateStatus, project_id)
            if existing:
                logger.debug(f"自动迭代状态已存在，跳过: {project_id}")
                continue
            
            extra_fields = {k: v for k, v in status_data.items() if k not in [
                "project_id", "status", "current_round", "max_rounds",
                "target_accuracy", "current_accuracy", "error_message"
            ]}
            
            status = AutoIterateStatus(
                project_id=project_id,
                status=status_data.get("status", "idle"),
                current_round=status_data.get("current_round", 0),
                max_rounds=status_data.get("max_rounds", 5),
                target_accuracy=status_data.get("target_accuracy", 95.0),
                current_accuracy=status_data.get("current_accuracy", 0.0),
                error_message=status_data.get("error_message", ""),
                extra_data=json.dumps(extra_fields, ensure_ascii=False),
                updated_at=datetime.now().isoformat()
            )
            session.add(status)
            session.commit()
            count += 1
            logger.info(f"迁移自动迭代状态: {project_id}")
    
    return count


def check_migration_needed() -> bool:
    """
    检查是否需要执行迁移
    使用原生 sqlite3 查询，避免 SQLModel 模型与数据库表结构不匹配时报错
    
    :return: 是否需要迁移
    """
    import sqlite3
    
    projects_file: str = os.path.join(DATA_DIR, "projects.json")
    db_file: str = os.path.join(DATA_DIR, "app.db")
    
    # 如果存在 JSON 文件但数据库为空，则需要迁移
    if os.path.exists(projects_file) and os.path.exists(db_file):
        try:
            conn: sqlite3.Connection = sqlite3.connect(db_file)
            cursor: sqlite3.Cursor = conn.cursor()
            # 使用原生 SQL 查询，只查询 id 列，避免列不存在的问题
            cursor.execute("SELECT id FROM projects LIMIT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            # 如果表中没有数据，则需要迁移
            if result is None:
                return True
        except sqlite3.OperationalError as e:
            # 如果表不存在，说明数据库刚创建，不需要迁移
            logger.debug(f"检查迁移需求时出错: {e}")
            return False
    elif os.path.exists(projects_file) and not os.path.exists(db_file):
        # JSON 文件存在但数据库不存在，需要迁移
        return True
    
    return False


def check_and_migrate_schema() -> None:
    """
    检查并迁移数据库模式
    确保所有必需的列都存在，如果缺失则自动添加
    此函数应在每次系统启动时调用
    """
    import sqlite3
    
    db_path: str = os.path.join(DATA_DIR, "app.db")
    
    # 如果数据库文件不存在，跳过模式迁移（init_db 会创建完整的表）
    if not os.path.exists(db_path):
        logger.debug("数据库文件不存在，跳过模式迁移")
        return
    
    logger.info("检查数据库模式...")
    
    # 定义需要检查的列迁移配置
    # 格式: (表名, 列名, 列类型, 默认值, 数据同步SQL)
    schema_migrations: List[tuple] = [
        (
            "projects",
            "initial_prompt",
            "TEXT",
            "''",
            "UPDATE projects SET initial_prompt = current_prompt WHERE initial_prompt IS NULL OR initial_prompt = ''"
        ),
        (
            "projects",
            "error_optimization_history",
            "TEXT",
            "'{}'",
            None
        ),
        # 新增：TaskResult reason 字段
        (
            "task_results",
            "reason",
            "TEXT",
            "''",
            None
        ),
        # 新增：TaskError reason 字段
        (
            "task_errors",
            "reason",
            "TEXT",
            "''",
            None
        ),
    ]
    
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    cursor: sqlite3.Cursor = conn.cursor()
    
    try:
        for table_name, column_name, column_type, default_value, sync_sql in schema_migrations:
            # 检查列是否已存在
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            if column_name not in column_names:
                logger.info(f"发现缺失列: {table_name}.{column_name}，正在添加...")
                
                # 添加列
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
                cursor.execute(alter_sql)
                
                # 执行数据同步
                if sync_sql:
                    cursor.execute(sync_sql)
                
                conn.commit()
                logger.info(f"成功添加列: {table_name}.{column_name}")
            else:
                logger.debug(f"列已存在: {table_name}.{column_name}")
                
    except Exception as e:
        logger.error(f"模式迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
    
    logger.info("数据库模式检查完成")


def run_migration() -> None:
    """
    执行完整的数据迁移
    包含：1. 模式迁移（添加缺失列） 2. 数据迁移（JSON 转 SQLite）
    """
    logger.info("=" * 50)
    logger.info("开始数据迁移...")
    logger.info("=" * 50)
    
    # 初始化数据库
    init_db()
    
    # 先执行模式迁移，确保所有列都存在
    # 必须在任何 SQLModel 查询之前执行，避免模型与数据库不匹配
    check_and_migrate_schema()
    
    # 检查是否需要迁移
    if not check_migration_needed():
        logger.info("数据库已有数据或无 JSON 文件，无需迁移")
        return
    
    # 备份 JSON 文件
    backup_json_files()
    
    # 执行迁移
    projects_count: int = migrate_projects()
    tasks_count: int = migrate_tasks()
    models_count: int = migrate_global_models()
    config_migrated: bool = migrate_model_config()
    status_count: int = migrate_auto_iterate_status()
    
    # 输出统计
    logger.info("=" * 50)
    logger.info("数据迁移完成!")
    logger.info(f"  - 项目: {projects_count} 个")
    logger.info(f"  - 任务: {tasks_count} 个")
    logger.info(f"  - 公共模型配置: {models_count} 个")
    logger.info(f"  - 系统模型配置: {'已迁移' if config_migrated else '跳过'}")
    logger.info(f"  - 自动迭代状态: {status_count} 个")
    logger.info("=" * 50)


if __name__ == "__main__":
    run_migration()
