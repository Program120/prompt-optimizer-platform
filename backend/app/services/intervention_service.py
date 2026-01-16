"""
原因库服务层

意图干预服务层

处理 IntentIntervention 相关的数据库操作，包括查询、新增、修改和删除。
提供给 API 层和 Optimization Engine 使用。
"""
from typing import List, Optional, Dict, Any, Union
from sqlmodel import select, Session, col, delete, func
from loguru import logger
import pandas as pd

from app.models import IntentIntervention
from app.db.database import get_db_session
from datetime import datetime

def get_interventions_by_project(project_id: str) -> List[IntentIntervention]:
    """
    获取项目下所有已标注的意图干预数据
    
    :param project_id: 项目唯一标识
    :return: IntentIntervention 对象列表
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            results: List[IntentIntervention] = list(session.exec(statement).all())
            # logger.debug(f"Fetched {len(results)} interventions for project {project_id}")
            return results
    except Exception as e:
        logger.error(f"Failed to get interventions for project {project_id}: {e}")
        return []

def get_interventions_paginated(
    project_id: str, 
    page: int = 1, 
    page_size: int = 50,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    分页获取意图干预数据
    """
    try:
        with get_db_session() as session:
            offset = (page - 1) * page_size
            
            # Base query
            query = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            
            # Search
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    col(IntentIntervention.query).like(search_term) | 
                    col(IntentIntervention.target).like(search_term) |
                    col(IntentIntervention.reason).like(search_term)
                )
            
            # Total count
            total_statement = select(func.count()).select_from(query.subquery())
            total = session.exec(total_statement).one()
            
            # Pagination
            statement = query.offset(offset).limit(page_size).order_by(IntentIntervention.id.desc())
            results: List[IntentIntervention] = list(session.exec(statement).all())
            
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": results
            }
    except Exception as e:
        logger.error(f"Failed to get interventions paginated: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

def import_dataset_to_interventions(
    project_id: str, 
    df: Any, 
    query_col: str, 
    target_col: str, 
    reason_col: Optional[str] = None
) -> int:
    """
    批量导入数据集到意图干预库
    """
    count = 0
    try:
        for _, row in df.iterrows():
            q = row.get(query_col)
            t = row.get(target_col)
            r = None
            if reason_col and reason_col in df.columns:
                r = row.get(reason_col)
            
            if pd.notna(q):
                upsert_intervention(
                    project_id=project_id,
                    query=str(q),
                    target=str(t) if pd.notna(t) else "",
                    reason=str(r) if pd.notna(r) else ""
                )
                count += 1
        logger.info(f"Imported {count} interventions for project {project_id}")
        return count
    except Exception as e:
        logger.error(f"Failed to import dataset: {e}")
        return 0


def get_intervention_map(project_id: str) -> Dict[str, str]:
    """
    获取项目下 Query -> Reason 的映射字典 (仅返回已有原因的项)
    
    :param project_id: 项目 ID
    :return: 字典 {query: reason}
    """
    interventions = get_interventions_by_project(project_id)
    return {r.query: r.reason for r in interventions if r.reason}


def upsert_intervention(project_id: str, query: str, reason: str, target: str = "") -> Optional[IntentIntervention]:
    """
    添加或更新意图干预项
    
    :param project_id: 项目 ID
    :param query: 用户查询 (Identify key)
    :param reason: 失败原因 / 意图说明
    :param target: 预期输出
    :return: 更新后的 IntentIntervention 对象
    """
    if not query:
        return None
        
    try:
        with get_db_session() as session:
            # 查找是否存在
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            existing = session.exec(statement).first()
            
            if existing:
                existing.reason = reason
                existing.target = target
                # existing.updated_at = datetime.now(...) # SQLModel usually handles defaults, but good to update
                session.add(existing)
                session.commit()
                session.refresh(existing)
                logger.info(f"Updated intervention for query: {query[:20]}... in project {project_id}")
                return existing
            else:
                new_intervention = IntentIntervention(
                    project_id=project_id,
                    query=query,
                    reason=reason,
                    target=target
                )
                session.add(new_intervention)
                session.commit()
                session.refresh(new_intervention)
                logger.info(f"Created new intervention for query: {query[:20]}... in project {project_id}")
                return new_intervention
    except Exception as e:
        logger.error(f"Failed to upsert intervention for project {project_id}, query {query[:20]}...: {e}")
        return None


def delete_intervention(project_id: str, query: str) -> bool:
    """
    删除单条干预记录
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            existing = session.exec(statement).first()
            if existing:
                session.delete(existing)
                session.commit()
                logger.info(f"Deleted intervention for query: {query[:20]}... in project {project_id}")
                return True
            logger.warning(f"Intervention not found for deletion: project {project_id}, query {query[:20]}...")
            return False
    except Exception as e:
        logger.error(f"Failed to delete intervention for project {project_id}, query {query[:20]}...: {e}")
        return False
