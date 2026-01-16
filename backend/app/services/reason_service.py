"""
原因库服务层

处理 ProjectReason 相关的数据库操作，包括查询、新增、修改和删除。
提供给 API 层和 Optimization Engine 使用。
"""
from typing import List, Optional, Dict, Any
from sqlmodel import select, Session
from loguru import logger
from app.models import ProjectReason
from app.db.database import get_db_session
from datetime import datetime

def get_reasons_by_project(project_id: str) -> List[ProjectReason]:
    """
    获取项目下所有已标注的原因
    
    :param project_id: 项目唯一标识
    :return: ProjectReason 对象列表
    """
    try:
        with get_db_session() as session:
            statement = select(ProjectReason).where(ProjectReason.project_id == project_id)
            results: List[ProjectReason] = list(session.exec(statement).all())
            logger.debug(f"Fetched {len(results)} reasons for project {project_id}")
            return results
    except Exception as e:
        logger.error(f"Failed to get reasons for project {project_id}: {e}")
        return []

def get_reason_map(project_id: str) -> Dict[str, str]:
    """
    获取项目下 Reason 映射 {query: reason}
    用于优化流程中快速查找
    
    :param project_id: 项目唯一标识
    :return: 字典映射 {query_text: reason_text}
    """
    reasons: List[ProjectReason] = get_reasons_by_project(project_id)
    return {r.query: r.reason for r in reasons}

def upsert_reason(
    project_id: str, 
    query: str, 
    reason: str, 
    target: str = ""
) -> Optional[ProjectReason]:
    """
    更新或插入原因 (Upsert 逻辑)
    如果 Query 已存在，则更新 Reason 和 UpdatedAt；否则创建新记录。
    
    :param project_id: 项目唯一标识
    :param query: 查询文本 (Query)
    :param reason: 原因文本 (Reason)
    :param target: 预期输出 (Optional)
    :return: 更新或创建后的 ProjectReason 对象
    """
    try:
        with get_db_session() as session:
            # 查找是否存在
            statement = select(ProjectReason).where(
                ProjectReason.project_id == project_id,
                ProjectReason.query == query
            )
            existing: Optional[ProjectReason] = session.exec(statement).first()
            
            if existing:
                existing.reason = reason
                if target:
                    existing.target = target
                existing.updated_at = datetime.now().isoformat()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                logger.info(f"Updated reason for query: {query[:20]}... in project {project_id}")
                return existing
            else:
                new_reason = ProjectReason(
                    project_id=project_id,
                    query=query,
                    reason=reason,
                    target=target,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session.add(new_reason)
                session.commit()
                session.refresh(new_reason)
                logger.info(f"Created new reason for query: {query[:20]}... in project {project_id}")
                return new_reason
    except Exception as e:
        logger.error(f"Failed to upsert reason for project {project_id}, query {query[:20]}...: {e}")
        return None

def delete_reason(project_id: str, query: str) -> bool:
    """
    删除指定 Query 的原因
    
    :param project_id: 项目唯一标识
    :param query: 查询文本
    :return: 是否删除成功 (True/False)
    """
    try:
        with get_db_session() as session:
            statement = select(ProjectReason).where(
                ProjectReason.project_id == project_id,
                ProjectReason.query == query
            )
            existing: Optional[ProjectReason] = session.exec(statement).first()
            if existing:
                session.delete(existing)
                session.commit()
                logger.info(f"Deleted reason for query: {query[:20]}... in project {project_id}")
                return True
            logger.warning(f"Reason not found for deletion: project {project_id}, query {query[:20]}...")
            return False
    except Exception as e:
        logger.error(f"Failed to delete reason for project {project_id}, query {query[:20]}...: {e}")
        return False
