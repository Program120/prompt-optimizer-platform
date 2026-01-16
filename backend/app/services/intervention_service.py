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

def get_interventions_by_project(project_id: str, file_id: Optional[str] = None) -> List[IntentIntervention]:
    """
    获取项目下所有已标注的意图干预数据
    
    :param project_id: 项目唯一标识
    :param file_id: 可选，文件版本 ID，用于筛选特定版本
    :return: IntentIntervention 对象列表
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            
            # 如果指定了 file_id，仅返回该版本的数据
            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)
            
            results: List[IntentIntervention] = list(session.exec(statement).all())
            return results
    except Exception as e:
        logger.error(f"Failed to get interventions for project {project_id}: {e}")
        return []

def get_interventions_paginated(
    project_id: str, 
    page: int = 1, 
    page_size: int = 50,
    search: Optional[str] = None,
    filter_type: Optional[str] = None, # 'all', 'modified', 'reason_added'
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    分页获取意图干预数据
    """
    try:
        with get_db_session() as session:
            offset = (page - 1) * page_size
            
            # Base query
            query = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            
            # File ID Filter (Strict)
            if file_id:
                query = query.where(IntentIntervention.file_id == file_id)
            
            # Filter Type
            if filter_type == "modified":
                query = query.where(IntentIntervention.is_target_modified == True)
            elif filter_type == "reason_added":
                query = query.where(IntentIntervention.reason != "")
            
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
    reason_col: Optional[str] = None,
    file_id: str = ""
) -> int:
    """
    批量导入数据集到意图干预库 (优化版: 批量提交)
    """
    try:
        from datetime import datetime
        
        # 1. 获取现有数据映射 {query: intervention}
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id
            )
            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)
            
            existing_records = session.exec(statement).all()
            existing_map = {r.query: r for r in existing_records}
            
            new_objects = []
            updated_count = 0
            
            # 2. 遍历 DataFrame
            for _, row in df.iterrows():
                q = row.get(query_col)
                if pd.isna(q):
                    continue
                
                query_str = str(q)
                t = row.get(target_col)
                target_val = str(t) if pd.notna(t) else ""
                
                r = None
                if reason_col and reason_col in df.columns:
                    r_val = row.get(reason_col)
                    r = str(r_val) if pd.notna(r_val) else ""
                else:
                    r = ""
                
                # 3. 检查是否存在
                if query_str in existing_map:
                    # Update existing
                    existing_obj = existing_map[query_str]
                    
                    # 仅当内容有变化时才更新 (这里简化逻辑，直接赋值，SQLAlchemy 会处理脏检查)
                    existing_obj.target = target_val
                    existing_obj.reason = r
                    existing_obj.updated_at = datetime.now().isoformat()
                    
                    # Target Modification Check
                    if existing_obj.original_target is not None:
                        existing_obj.is_target_modified = (existing_obj.target != existing_obj.original_target)
                    
                    # Import default logic: if original is None, fill it
                    if existing_obj.original_target is None:
                        existing_obj.original_target = target_val
                        existing_obj.is_target_modified = False
                        
                    session.add(existing_obj)
                    updated_count += 1
                else:
                    # Create new
                    new_obj = IntentIntervention(
                        project_id=project_id,
                        query=query_str,
                        target=target_val,
                        reason=r,
                        original_target=target_val,
                        is_target_modified=False,
                        file_id=file_id
                    )
                    new_objects.append(new_obj)
            
            # 4. 批量提交
            if new_objects:
                session.add_all(new_objects)
            
            total_affected = len(new_objects) + updated_count
            session.commit()
            
            logger.info(f"Batch imported {total_affected} interventions (New: {len(new_objects)}, Updated: {updated_count}) for project {project_id}")
            return total_affected
            
    except Exception as e:
        logger.error(f"Failed to batch import dataset: {e}")
        return 0


def get_intervention_map(project_id: str, file_id: Optional[str] = None) -> Dict[str, str]:
    """
    获取项目下 Query -> Reason 的映射字典 (仅返回已有原因的项)
    
    :param project_id: 项目 ID
    :param file_id: 可选，文件版本 ID，用于筛选特定版本
    :return: 字典 {query: reason}
    """
    interventions = get_interventions_by_project(project_id, file_id=file_id)
    return {r.query: r.reason for r in interventions if r.reason}


def upsert_intervention(project_id: str, query: str, reason: str, target: str = "", is_import: bool = False, file_id: str = "") -> Optional[IntentIntervention]:
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
            
            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)

            existing = session.exec(statement).first()
            
            if existing:
                existing.reason = reason
                existing.target = target
                
                # Check target modification
                if existing.original_target is not None:
                    existing.is_target_modified = (existing.target != existing.original_target)
                
                # 如果是导入模式，且 original_target 为空，则补充 original_target
                if is_import and existing.original_target is None:
                    existing.original_target = target
                    existing.is_target_modified = False

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
                    target=target,
                    original_target=target, # 新建时，原始值即为当前值
                    is_target_modified=False,
                    file_id=file_id
                )
                session.add(new_intervention)
                session.commit()
                session.refresh(new_intervention)
                logger.info(f"Created new intervention for query: {query[:20]}... in project {project_id}")
                return new_intervention
    except Exception as e:
        logger.error(f"Failed to upsert intervention for project {project_id}, query {query[:20]}...: {e}")
        return None


def reset_intervention(project_id: str, query: str) -> bool:
    """
    重置单条干预记录：恢复 Target 为 Original Target，清空 Reason
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            existing = session.exec(statement).first()
            if existing:
                # 恢复原始 Target (如果有)
                if existing.original_target is not None:
                    existing.target = existing.original_target
                
                # 清空 Reason
                existing.reason = ""
                existing.is_target_modified = False
                
                session.add(existing)
                session.commit()
                logger.info(f"Reset intervention for query: {query[:20]}... in project {project_id}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to reset intervention: {e}")
        return False


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


def get_unique_targets(project_id: str, file_id: Optional[str] = None) -> List[str]:
    """
    获取项目下所有唯一的 Target
    """
    try:
        with get_db_session() as session:
            query = select(IntentIntervention.target).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.target != ""
            )
            
            if file_id:
                query = query.where(IntentIntervention.file_id == file_id)
                
            statement = query.distinct()
            results = session.exec(statement).all()
            return [str(r) for r in results if r]
    except Exception as e:
        logger.error(f"Failed to get unique targets: {e}")
        return []
