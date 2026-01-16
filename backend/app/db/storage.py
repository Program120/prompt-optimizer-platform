"""
数据存储模块（SQLModel 版本）
提供项目、任务、模型配置等数据的 CRUD 操作
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from loguru import logger
from sqlmodel import Session, select

from app.db.database import get_db_session, DATA_DIR
from app.models import (
    Project, ProjectIteration, Task, TaskResult, TaskError,
    GlobalModel, ModelConfig, AutoIterateStatus
)


def init_storage() -> None:
    """
    初始化存储层
    确保数据目录存在，并初始化数据库
    """
    from app.db.database import init_db
    init_db()
    logger.info("存储层初始化完成")


# ============== 项目相关操作 ==============

def get_projects() -> List[Dict[str, Any]]:
    """
    获取所有项目列表
    
    :return: 项目字典列表
    """
    with get_db_session() as session:
        statement = select(Project)
        projects: List[Project] = list(session.exec(statement))
        return [p.to_dict() for p in projects]


def save_projects(projects: List[Dict[str, Any]]) -> None:
    """
    保存项目列表（批量更新）
    注意：此函数保留用于兼容性，推荐使用单独的 create/update 函数
    
    :param projects: 项目字典列表
    """
    with get_db_session() as session:
        for proj_dict in projects:
            existing = session.get(Project, proj_dict.get("id"))
            if existing:
                # 传递 session 以便同步迭代记录
                _update_project_from_dict(session, existing, proj_dict)
            else:
                new_project = _create_project_from_dict(proj_dict)
                session.add(new_project)
        session.commit()


def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取单个项目
    
    :param project_id: 项目 ID
    :return: 项目字典，未找到返回 None
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project:
            return project.to_dict()
        return None


def create_project(name: str, prompt: str) -> Dict[str, Any]:
    """
    创建新项目
    
    :param name: 项目名称
    :param prompt: 初始提示词
    :return: 创建的项目字典
    """
    project_id: str = datetime.now().strftime("%Y%m%d%H%M%S")
    
    new_project = Project(
        id=project_id,
        name=name,
        current_prompt=prompt,
        # 保存初始提示词，用于重置功能
        initial_prompt=prompt,
        config="{}",
        model_config_data="{}",
        optimization_model_config="{}",
        created_at=datetime.now().isoformat()
    )
    
    with get_db_session() as session:
        session.add(new_project)
        session.commit()
        session.refresh(new_project)
        logger.info(f"创建项目: {project_id} - {name}")
        return new_project.to_dict()


def delete_project(project_id: str) -> bool:
    """
    删除项目
    
    :param project_id: 项目 ID
    :return: 是否成功删除
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if project:
            # 同时删除关联的迭代记录
            for iteration in project.iterations:
                session.delete(iteration)
            session.delete(project)
            session.commit()
            logger.info(f"删除项目: {project_id}")
            return True
        return False


def reset_project(project_id: str) -> Optional[Dict[str, Any]]:
    """
    重置项目
    将提示词恢复到初始状态，清空所有运行记录、迭代记录和知识库
    
    :param project_id: 项目 ID
    :return: 重置后的项目字典，未找到返回 None
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return None
        
        # 1. 将当前提示词重置为初始提示词
        if project.initial_prompt:
            project.current_prompt = project.initial_prompt
        
        # 2. 删除所有迭代记录
        for iteration in project.iterations:
            session.delete(iteration)
        
        # 3. 清空 last_task_id
        project.last_task_id = None
        
        project.updated_at = datetime.now().isoformat()
        session.commit()
        session.refresh(project)
        
        logger.info(f"重置项目提示词和迭代记录: {project_id}")
    
    # 4. 删除所有关联的任务
    project_tasks: List[Dict[str, Any]] = get_project_tasks(project_id)
    deleted_task_count: int = 0
    for task in project_tasks:
        if delete_task(task["id"]):
            deleted_task_count += 1
    logger.info(f"删除项目任务 {deleted_task_count} 个: {project_id}")
    
    # 5. 清空知识库文件
    knowledge_base_dir: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "knowledge_base"
    )
    kb_file_path: str = os.path.join(knowledge_base_dir, f"kb_{project_id}.json")
    if os.path.exists(kb_file_path):
        try:
            os.remove(kb_file_path)
            logger.info(f"删除知识库文件: {kb_file_path}")
        except Exception as e:
            logger.warning(f"删除知识库文件失败: {e}")
    
    # 返回重置后的项目
    return get_project(project_id)


def update_project(project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    更新项目信息
    
    :param project_id: 项目 ID
    :param updates: 要更新的字段字典
    :return: 更新后的项目字典，未找到返回 None
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return None
        
        # 更新允许的字段
        if "name" in updates:
            project.name = updates["name"] or ""
        if "current_prompt" in updates:
            project.current_prompt = updates["current_prompt"] or ""
        if "last_task_id" in updates:
            project.last_task_id = updates["last_task_id"]
        if "config" in updates:
            project.config = json.dumps(updates["config"] or {}, ensure_ascii=False)
        if "model_config" in updates:
            project.model_config_data = json.dumps(updates["model_config"] or {}, ensure_ascii=False)
        if "optimization_model_config" in updates:
            project.optimization_model_config = json.dumps(updates["optimization_model_config"] or {}, ensure_ascii=False)
        if "optimization_prompt" in updates:
            project.optimization_prompt = updates["optimization_prompt"] or ""
        
        # 处理迭代记录更新
        if "iterations" in updates:
            _sync_project_iterations(session, project, updates["iterations"])
        
        project.updated_at = datetime.now().isoformat()
        session.commit()
        session.refresh(project)
        logger.info(f"更新项目: {project_id}")
        return project.to_dict()


def _sync_project_iterations(session: Session, project: Project, iterations_data: List[Dict[str, Any]]) -> None:
    """
    同步项目迭代记录
    
    :param session: 数据库会话
    :param project: 项目对象
    :param iterations_data: 迭代记录数据列表
    """
    # 删除现有迭代
    for existing_iter in project.iterations:
        session.delete(existing_iter)
    
    # 添加新迭代
    for idx, iter_data in enumerate(iterations_data):
        new_iter = ProjectIteration(
            project_id=project.id,
            version=iter_data.get("version", idx + 1),
            previous_prompt=iter_data.get("previous_prompt") or "",
            optimized_prompt=iter_data.get("optimized_prompt") or "",
            strategy=iter_data.get("strategy") or "",
            accuracy_before=iter_data.get("accuracy_before", 0.0),
            accuracy_after=iter_data.get("accuracy_after"),
            task_id=iter_data.get("task_id"),
            analysis=json.dumps(iter_data.get("analysis") or {}, ensure_ascii=False),
            note=iter_data.get("note") or "",
            created_at=iter_data.get("created_at", datetime.now().isoformat())
        )
        session.add(new_iter)


def _sync_project_iterations_from_legacy(session: Session, project: Project, iterations_data: List[Dict[str, Any]]) -> None:
    """
    同步项目迭代记录（处理旧格式的迭代数据）
    旧格式使用 old_prompt/new_prompt，新格式使用 previous_prompt/optimized_prompt
    
    :param session: 数据库会话
    :param project: 项目对象
    :param iterations_data: 迭代记录数据列表（旧格式）
    """
    # 删除现有迭代
    for existing_iter in project.iterations:
        session.delete(existing_iter)
    
    # 添加新迭代（将旧格式字段映射到新格式）
    for idx, iter_data in enumerate(iterations_data):
        # 兼容旧格式字段映射
        previous_prompt: str = iter_data.get("previous_prompt") or iter_data.get("old_prompt") or ""
        optimized_prompt: str = iter_data.get("optimized_prompt") or iter_data.get("new_prompt") or ""
        
        # 获取准确率（旧格式可能是单个 accuracy 字段）
        accuracy_before: float = iter_data.get("accuracy_before", 0.0)
        accuracy_after = iter_data.get("accuracy_after")
        # 如果只有单个 accuracy 字段，将其视为 accuracy_before
        if "accuracy" in iter_data and accuracy_before == 0.0:
            accuracy_before = iter_data.get("accuracy", 0.0)
        
        # 获取策略信息
        strategy: str = iter_data.get("strategy") or ""
        applied_strategies = iter_data.get("applied_strategies", [])
        if applied_strategies and not strategy:
            # 将策略列表转换为字符串
            strategy = ", ".join([str(s) for s in applied_strategies]) if applied_strategies else ""
        
        new_iter = ProjectIteration(
            project_id=project.id,
            version=iter_data.get("version", idx + 1),
            previous_prompt=previous_prompt,
            optimized_prompt=optimized_prompt,
            strategy=strategy,
            accuracy_before=accuracy_before,
            accuracy_after=accuracy_after,
            task_id=iter_data.get("task_id"),
            analysis=json.dumps(iter_data.get("analysis") or {}, ensure_ascii=False),
            note=iter_data.get("note") or "",
            created_at=iter_data.get("created_at", datetime.now().isoformat())
        )
        session.add(new_iter)
    
    logger.info(f"同步项目迭代记录: {project.id}, 数量: {len(iterations_data)}")


def delete_project_iteration(project_id: str, timestamp: str) -> bool:
    """
    删除项目迭代记录
    
    :param project_id: 项目 ID
    :param timestamp: 迭代创建时间（用于匹配）
    :return: 是否成功删除
    """
    with get_db_session() as session:
        statement = select(ProjectIteration).where(
            ProjectIteration.project_id == project_id,
            ProjectIteration.created_at == timestamp
        )
        iteration = session.exec(statement).first()
        if iteration:
            session.delete(iteration)
            session.commit()
            logger.info(f"删除项目迭代: {project_id} - {timestamp}")
            return True
        return False


def update_project_iteration_note(project_id: str, timestamp: str, note: str) -> bool:
    """
    更新项目迭代记录备注
    
    :param project_id: 项目 ID
    :param timestamp: 迭代创建时间（用于匹配）
    :param note: 备注内容
    :return: 是否成功更新
    """
    with get_db_session() as session:
        statement = select(ProjectIteration).where(
            ProjectIteration.project_id == project_id,
            ProjectIteration.created_at == timestamp
        )
        iteration = session.exec(statement).first()
        if iteration:
            iteration.note = note
            session.commit()
            logger.info(f"更新项目迭代备注: {project_id} - {timestamp}")
            return True
        return False


def get_error_optimization_history(project_id: str) -> Dict[str, Any]:
    """
    获取项目的错误样本优化历史
    
    :param project_id: 项目 ID
    :return: 错误优化历史字典
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if not project:
            return {}
        
        try:
            history_str: str = project.error_optimization_history or "{}"
            return json.loads(history_str)
        except json.JSONDecodeError:
            return {}


def update_error_optimization_history(
    project_id: str, 
    history: Dict[str, Any]
) -> bool:
    """
    更新项目的错误样本优化历史
    
    :param project_id: 项目 ID
    :param history: 更新后的历史记录
    :return: 是否成功更新
    """
    with get_db_session() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning(f"更新错误优化历史失败: 项目 {project_id} 不存在")
            return False
        
        project.error_optimization_history = json.dumps(history, ensure_ascii=False)
        project.updated_at = datetime.now().isoformat()
        session.commit()
        logger.info(f"更新错误优化历史: {project_id}, 记录数: {len(history)}")
        return True


# ============== 任务相关操作 ==============

def update_task_status_only(task_id: str, status: str) -> bool:
    """
    仅更新任务状态，不修改其他字段（如结果列表）
    防止因 results 为空覆盖导致数据丢失
    
    :param task_id: 任务 ID
    :param status: 新状态
    :return: 是否成功更新
    """
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        task = session.get(Task, normalized_id)
        if task:
            task.status = status
            session.commit()
            logger.info(f"仅更新任务状态: {normalized_id} -> {status}")
            return True
        return False


def save_task_status(project_id: str, task_id: str, status: Dict[str, Any]) -> None:
    """
    保存任务状态
    
    :param project_id: 项目 ID
    :param task_id: 任务 ID
    :param status: 任务状态字典
    """
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        existing_task = session.get(Task, normalized_id)
        
        if existing_task:
            # 更新现有任务
            existing_task.status = status.get("status") or existing_task.status
            existing_task.current_index = status.get("current_index", existing_task.current_index)
            existing_task.total_count = status.get("total_count", existing_task.total_count)
            existing_task.prompt = status.get("prompt") or existing_task.prompt or ""
            existing_task.file_path = status.get("file_path") or existing_task.file_path or ""
            existing_task.original_filename = status.get("original_filename") or existing_task.original_filename or ""
            existing_task.note = status.get("note") or existing_task.note or ""
            
            # 保存额外配置
            extra_fields = {k: v for k, v in status.items() if k not in [
                "id", "project_id", "status", "current_index", "total_count",
                "prompt", "file_path", "original_filename", "note", "results", "errors"
            ]}
            existing_task.extra_config = json.dumps(extra_fields, ensure_ascii=False)
            
            # 同步结果和错误
            _sync_task_results(session, normalized_id, status.get("results", []))
            _sync_task_errors(session, normalized_id, status.get("errors", []))
        else:
            # 创建新任务
            new_task = Task(
                id=normalized_id,
                project_id=project_id,
                status=status.get("status", "pending"),
                current_index=status.get("current_index", 0),
                total_count=status.get("total_count", 0),
                prompt=status.get("prompt") or "",
                file_path=status.get("file_path") or "",
                original_filename=status.get("original_filename") or "",
                note=status.get("note") or "",
                created_at=datetime.now().isoformat()
            )
            
            # 保存额外配置
            extra_fields = {k: v for k, v in status.items() if k not in [
                "id", "project_id", "status", "current_index", "total_count",
                "prompt", "file_path", "original_filename", "note", "results", "errors"
            ]}
            new_task.extra_config = json.dumps(extra_fields, ensure_ascii=False)
            session.add(new_task)
            
            # 添加结果和错误
            for result_data in status.get("results", []):
                result = _create_task_result(normalized_id, result_data)
                session.add(result)
            
            for error_data in status.get("errors", []):
                error = _create_task_error(normalized_id, error_data)
                session.add(error)
        
        session.commit()
        logger.debug(f"保存任务状态: {normalized_id}")


def _sync_task_results(session: Session, task_id: str, results_data: List[Dict[str, Any]]) -> None:
    """同步任务结果"""
    # 删除现有结果
    statement = select(TaskResult).where(TaskResult.task_id == task_id)
    existing_results = session.exec(statement).all()
    for r in existing_results:
        session.delete(r)
    
    # 添加新结果
    for result_data in results_data:
        result = _create_task_result(task_id, result_data)
        session.add(result)


def _sync_task_errors(session: Session, task_id: str, errors_data: List[Dict[str, Any]]) -> None:
    """同步任务错误"""
    # 删除现有错误
    statement = select(TaskError).where(TaskError.task_id == task_id)
    existing_errors = session.exec(statement).all()
    for e in existing_errors:
        session.delete(e)
    
    # 添加新错误
    for error_data in errors_data:
        error = _create_task_error(task_id, error_data)
        session.add(error)


def _create_task_result(task_id: str, data: Dict[str, Any]) -> TaskResult:
    """从字典创建任务结果对象"""
    extra_data = {k: v for k, v in data.items() if k not in ["query", "target", "output", "is_correct", "reason"]}
    return TaskResult(
        task_id=task_id,
        query=data.get("query", ""),
        target=data.get("target", ""),
        output=data.get("output", ""),
        is_correct=data.get("is_correct", False),
        reason=data.get("reason", ""),
        extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"
    )


def _create_task_error(task_id: str, data: Dict[str, Any]) -> TaskError:
    """从字典创建任务错误对象"""
    extra_data = {k: v for k, v in data.items() if k not in ["query", "target", "output", "reason"]}
    return TaskError(
        task_id=task_id,
        query=data.get("query", ""),
        target=data.get("target", ""),
        output=data.get("output", ""),
        reason=data.get("reason", ""),
        extra_data=json.dumps(extra_data, ensure_ascii=False) if extra_data else "{}"
    )


def get_task_status(task_id: str, include_results: bool = False) -> Optional[Dict[str, Any]]:
    """
    获取任务状态
    
    :param task_id: 任务 ID
    :param include_results: 是否包含完整的 results 和 errors 数据
                           默认 False 以提升性能
    :return: 任务状态字典，未找到返回 None
    """
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        task = session.get(Task, normalized_id)
        if task:
            return task.to_dict(include_results=include_results)
        return None


def get_task_results_paginated(
    task_id: str, 
    page: int = 1, 
    page_size: int = 50,
    result_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取分页的任务结果
    
    :param task_id: 任务 ID
    :param page: 页码 (1-based)
    :param page_size: 每页数量
    :param result_type: 结果类型过滤 'success' | 'error' | None
    :return: 包含 results 列表和 total 总数的字典
    """
    from sqlalchemy import func
    
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        # 构建基础查询
        statement = select(TaskResult).where(TaskResult.task_id == normalized_id)
        
        # 应用类型过滤
        if result_type == 'success':
            statement = statement.where(TaskResult.is_correct == True)
        elif result_type == 'error':
            statement = statement.where(TaskResult.is_correct == False)
            
        # 获取总数
        count_stmt = select(func.count()).select_from(statement.subquery())
        total = session.exec(count_stmt).one()
        
        # 分页查询
        offset = (page - 1) * page_size
        statement = statement.offset(offset).limit(page_size)
        
        # 执行查询
        results = session.exec(statement).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": [r.to_dict() for r in results]
        }



def get_project_tasks(project_id: str) -> List[Dict[str, Any]]:
    """
    获取项目关联的所有任务（仅返回摘要信息，不包含完整的 results/errors）
    
    :param project_id: 项目 ID
    :return: 任务信息列表
    """
    from sqlalchemy import func
    
    with get_db_session() as session:
        statement = select(Task).where(Task.project_id == project_id)
        tasks: List[Task] = list(session.exec(statement))
        
        result: List[Dict[str, Any]] = []
        for task in tasks:
            # 使用 COUNT 查询获取数量，避免加载所有数据（性能优化）
            results_count_stmt = select(func.count(TaskResult.id)).where(TaskResult.task_id == task.id)
            results_count: int = session.exec(results_count_stmt).one()
            
            # 使用 TaskResult 计算错误数 (is_correct=False)，确保数据一致性
            # 不再查询 TaskError 表，因为它可能与 TaskResult 不一致
            errors_count_stmt = select(func.count(TaskResult.id)).where(
                TaskResult.task_id == task.id, 
                TaskResult.is_correct == False
            )
            errors_count: int = session.exec(errors_count_stmt).one()
            
            # 计算准确率
            accuracy: float = (results_count - errors_count) / results_count if results_count > 0 else 0
            
            # 提取时间戳
            timestamp: str = task.id.replace("task_", "") if task.id.startswith("task_") else ""
            
            # 数据集名称
            dataset_name: str = task.original_filename if task.original_filename else (
                os.path.basename(task.file_path) if task.file_path else "未知"
            )
            
            result.append({
                "id": task.id,
                "status": task.status,
                "current_index": task.current_index,
                "total_count": task.total_count,
                "results_count": results_count,
                "errors_count": errors_count,
                "accuracy": accuracy,
                "prompt": task.prompt,
                "dataset_name": dataset_name,
                "created_at": timestamp,
                "note": task.note
            })
        
        # 按任务 ID 排序（最新的在前）
        result.sort(key=lambda x: x["id"], reverse=True)
        return result


def delete_task(task_id: str) -> bool:
    """
    删除任务及相关数据
    
    :param task_id: 任务 ID
    :return: 是否成功删除
    """
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        task = session.get(Task, normalized_id)
        if task:
            # 删除关联的结果和错误
            results_stmt = select(TaskResult).where(TaskResult.task_id == normalized_id)
            for result in session.exec(results_stmt):
                session.delete(result)
            
            errors_stmt = select(TaskError).where(TaskError.task_id == normalized_id)
            for error in session.exec(errors_stmt):
                session.delete(error)
            
            session.delete(task)
            session.commit()
            logger.info(f"删除任务: {normalized_id}")
            return True
        return False


def update_task_note(task_id: str, note: str) -> bool:
    """
    更新任务备注
    
    :param task_id: 任务 ID
    :param note: 备注内容
    :return: 是否成功更新
    """
    with get_db_session() as session:
        # 规范化任务 ID
        normalized_id: str = task_id if task_id.startswith("task_") else f"task_{task_id}"
        
        task = session.get(Task, normalized_id)
        if task:
            task.note = note
            session.commit()
            logger.info(f"更新任务备注: {normalized_id}")
            return True
        return False


def get_all_project_errors(project_id: str) -> List[Dict[str, Any]]:
    """
    获取项目所有历史任务中的错误案例
    通过查询 TaskResult 中 is_correct=False 的记录，确保与准确率计算一致
    
    :param project_id: 项目 ID
    :return: 错误案例列表
    """
    if not project_id:
        return []
    
    with get_db_session() as session:
        # 获取项目的所有任务
        tasks_stmt = select(Task).where(Task.project_id == project_id)
        tasks: List[Task] = list(session.exec(tasks_stmt))
        
        all_errors: List[Dict[str, Any]] = []
        for task in tasks:
            # 修改：从 TaskResult 获取错误 (is_correct=False)，不再使用 TaskError 表
            errors_stmt = select(TaskResult).where(
                TaskResult.task_id == task.id,
                TaskResult.is_correct == False
            )
            errors: List[TaskResult] = list(session.exec(errors_stmt))
            all_errors.extend([e.to_dict() for e in errors])
        
        return all_errors


# ============== 模型配置相关操作 ==============

def get_model_config() -> Dict[str, Any]:
    """
    获取系统模型配置
    
    :return: 模型配置字典
    """
    with get_db_session() as session:
        config = session.get(ModelConfig, 1)
        if config:
            return config.to_dict()
        
        # 返回默认配置
        return {
            "base_url": "https://api.openai.com/v1",
            "api_key": "",
            "max_tokens": 2000,
            "timeout": 60,
            "model_name": "gpt-3.5-turbo",
            "temperature": 0.0
        }


def save_model_config(config: Dict[str, Any]) -> None:
    """
    保存系统模型配置
    
    :param config: 模型配置字典
    """
    with get_db_session() as session:
        existing = session.get(ModelConfig, 1)
        
        if existing:
            existing.base_url = config.get("base_url", existing.base_url)
            existing.api_key = config.get("api_key", existing.api_key)
            existing.max_tokens = config.get("max_tokens", existing.max_tokens)
            existing.timeout = config.get("timeout", existing.timeout)
            existing.model_name = config.get("model_name", existing.model_name)
            existing.temperature = config.get("temperature", existing.temperature)
        else:
            new_config = ModelConfig(
                id=1,
                base_url=config.get("base_url", "https://api.openai.com/v1"),
                api_key=config.get("api_key", ""),
                max_tokens=config.get("max_tokens", 2000),
                timeout=config.get("timeout", 60),
                model_name=config.get("model_name", "gpt-3.5-turbo"),
                temperature=config.get("temperature", 0.0)
            )
            session.add(new_config)
        
        session.commit()
        logger.info("保存系统模型配置")


# ============== 公共模型配置相关操作 ==============

def get_global_models() -> List[Dict[str, Any]]:
    """
    获取所有公共模型配置
    
    :return: 公共模型配置列表
    """
    with get_db_session() as session:
        statement = select(GlobalModel)
        models: List[GlobalModel] = list(session.exec(statement))
        return [m.to_dict() for m in models]


def get_global_model(model_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 ID 获取单个公共模型配置
    
    :param model_id: 模型配置 ID
    :return: 模型配置字典，未找到返回 None
    """
    with get_db_session() as session:
        model = session.get(GlobalModel, model_id)
        if model:
            return model.to_dict()
        return None


def create_global_model(model_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建新的公共模型配置
    
    :param model_data: 模型配置数据
    :return: 创建的模型配置字典
    """
    model_id: str = datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    new_model = GlobalModel(
        id=model_id,
        name=model_data.get("name", "未命名模型"),
        base_url=model_data.get("base_url", ""),
        api_key=model_data.get("api_key", ""),
        model_name=model_data.get("model_name", "gpt-3.5-turbo"),
        max_tokens=model_data.get("max_tokens", 2000),
        temperature=model_data.get("temperature", 0.0),
        timeout=model_data.get("timeout", 60),
        concurrency=model_data.get("concurrency", 5),
        extra_body=json.dumps(model_data.get("extra_body")) if model_data.get("extra_body") else "",
        default_headers=json.dumps(model_data.get("default_headers")) if model_data.get("default_headers") else "",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    with get_db_session() as session:
        session.add(new_model)
        session.commit()
        session.refresh(new_model)
        logger.info(f"创建公共模型配置: {model_id}")
        return new_model.to_dict()


def update_global_model(model_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    更新公共模型配置
    
    :param model_id: 模型配置 ID
    :param updates: 要更新的字段
    :return: 更新后的模型配置，未找到返回 None
    """
    with get_db_session() as session:
        model = session.get(GlobalModel, model_id)
        if not model:
            return None
        
        # 更新允许的字段
        allowed_fields: List[str] = [
            "name", "base_url", "api_key", "model_name",
            "max_tokens", "temperature", "timeout", "concurrency"
        ]
        for field in allowed_fields:
            if field in updates:
                val = updates[field]
                if val is None and field in ["name", "base_url", "api_key", "model_name"]:
                    val = ""
                setattr(model, field, val)
        
        # 处理 JSON 字段
        if "extra_body" in updates:
            model.extra_body = json.dumps(updates["extra_body"]) if updates["extra_body"] else ""
        if "default_headers" in updates:
            model.default_headers = json.dumps(updates["default_headers"]) if updates["default_headers"] else ""
        
        model.updated_at = datetime.now().isoformat()
        session.commit()
        session.refresh(model)
        logger.info(f"更新公共模型配置: {model_id}")
        return model.to_dict()


def delete_global_model(model_id: str) -> bool:
    """
    删除公共模型配置
    
    :param model_id: 模型配置 ID
    :return: 是否成功删除
    """
    with get_db_session() as session:
        model = session.get(GlobalModel, model_id)
        if model:
            session.delete(model)
            session.commit()
            logger.info(f"删除公共模型配置: {model_id}")
            return True
        return False


# ============== 自动迭代状态相关操作 ==============

def save_auto_iterate_status(project_id: str, status: Dict[str, Any]) -> None:
    """
    保存自动迭代状态
    
    :param project_id: 项目 ID
    :param status: 状态字典
    """
    with get_db_session() as session:
        existing = session.get(AutoIterateStatus, project_id)
        
        if existing:
            existing.status = status.get("status") or existing.status
            existing.current_round = status.get("current_round", existing.current_round)
            existing.max_rounds = status.get("max_rounds", existing.max_rounds)
            existing.target_accuracy = status.get("target_accuracy", existing.target_accuracy)
            existing.current_accuracy = status.get("current_accuracy", existing.current_accuracy)
            existing.error_message = status.get("error_message") or existing.error_message or ""
            
            # 保存额外数据
            extra_fields = {k: v for k, v in status.items() if k not in [
                "project_id", "status", "current_round", "max_rounds",
                "target_accuracy", "current_accuracy", "error_message"
            ]}
            existing.extra_data = json.dumps(extra_fields, ensure_ascii=False)
            existing.updated_at = datetime.now().isoformat()
        else:
            extra_fields = {k: v for k, v in status.items() if k not in [
                "project_id", "status", "current_round", "max_rounds",
                "target_accuracy", "current_accuracy", "error_message"
            ]}
            new_status = AutoIterateStatus(
                project_id=project_id,
                status=status.get("status") or "idle",
                current_round=status.get("current_round", 0),
                max_rounds=status.get("max_rounds", 5),
                target_accuracy=status.get("target_accuracy", 95.0),
                current_accuracy=status.get("current_accuracy", 0.0),
                error_message=status.get("error_message") or "",
                extra_data=json.dumps(extra_fields, ensure_ascii=False),
                updated_at=datetime.now().isoformat()
            )
            session.add(new_status)
        
        session.commit()
        logger.debug(f"保存自动迭代状态: {project_id}")


def get_auto_iterate_status(project_id: str) -> Optional[Dict[str, Any]]:
    """
    获取自动迭代状态
    
    :param project_id: 项目 ID
    :return: 状态字典，未找到返回 None
    """
    with get_db_session() as session:
        status = session.get(AutoIterateStatus, project_id)
        if status:
            return status.to_dict()
        return None


# ============== 辅助函数 ==============

def _create_project_from_dict(data: Dict[str, Any]) -> Project:
    """从字典创建项目对象"""
    prompt: str = data.get("current_prompt", "")
    return Project(
        id=data.get("id", datetime.now().strftime("%Y%m%d%H%M%S")),
        name=data.get("name", ""),
        current_prompt=prompt,
        # 如果没有 initial_prompt，则使用 current_prompt
        initial_prompt=data.get("initial_prompt", prompt),
        last_task_id=data.get("last_task_id"),
        config=json.dumps(data.get("config", {}), ensure_ascii=False),
        model_config_data=json.dumps(data.get("model_config", {}), ensure_ascii=False),
        optimization_model_config=json.dumps(data.get("optimization_model_config", {}), ensure_ascii=False),
        optimization_prompt=data.get("optimization_prompt", ""),
        created_at=data.get("created_at", datetime.now().isoformat()),
        updated_at=data.get("updated_at")
    )


def _update_project_from_dict(session: Session, project: Project, data: Dict[str, Any]) -> None:
    """
    从字典更新项目对象
    
    :param session: 数据库会话
    :param project: 项目对象
    :param data: 更新数据字典
    """
    if "name" in data:
        project.name = data["name"]
    if "current_prompt" in data:
        project.current_prompt = data["current_prompt"]
    if "last_task_id" in data:
        project.last_task_id = data["last_task_id"]
    if "config" in data:
        project.config = json.dumps(data["config"], ensure_ascii=False)
    if "model_config" in data:
        project.model_config_data = json.dumps(data["model_config"], ensure_ascii=False)
    if "optimization_model_config" in data:
        project.optimization_model_config = json.dumps(data["optimization_model_config"], ensure_ascii=False)
    if "optimization_prompt" in data:
        project.optimization_prompt = data["optimization_prompt"]
    if "updated_at" in data:
        project.updated_at = data["updated_at"]
    
    # 处理迭代记录更新（关键修复：确保 iterations 被正确同步）
    if "iterations" in data:
        _sync_project_iterations_from_legacy(session, project, data["iterations"])
