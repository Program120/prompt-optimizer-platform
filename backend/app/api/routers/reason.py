"""
原因库 API 路由

定义对原因库 (ProjectReason) 的增删改查接口。
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from loguru import logger
from app.services import reason_service
from app.models import ProjectReason

router = APIRouter()

class ReasonUpsertRequest(BaseModel):
    """原因库更新请求模型"""
    query: str
    reason: str
    target: str = ""

class ReasonResponse(BaseModel):
    """原因库响应模型"""
    id: int
    project_id: str
    query: str
    reason: str
    target: str
    updated_at: str

@router.get("/projects/{project_id}/reasons", response_model=Dict[str, List[ReasonResponse]])
async def list_reasons(project_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取项目下所有标注的原因
    
    :param project_id: 项目 ID
    :return: 包含 reasons 列表的字典
    """
    logger.info(f"Fetching reasons for project: {project_id}")
    try:
        reasons: List[ProjectReason] = reason_service.get_reasons_by_project(project_id)
        return {"reasons": [r.to_dict() for r in reasons]}
    except Exception as e:
        logger.error(f"Error fetching reasons for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/reasons", response_model=ReasonResponse)
async def upsert_reason(project_id: str, request: ReasonUpsertRequest) -> Dict[str, Any]:
    """
    添加或更新原因
    
    :param project_id: 项目 ID
    :param request: 更新请求体 (query, reason, target)
    :return: 更新后的原因对象字典
    """
    logger.info(f"Upserting reason for project {project_id}, query: {request.query[:20]}...")
    if not request.query or not request.reason:
        logger.warning("Upsert failed: Query and Reason are required")
        raise HTTPException(status_code=400, detail="Query and Reason are required")
    
    try:
        result: Optional[ProjectReason] = reason_service.upsert_reason(
            project_id=project_id,
            query=request.query,
            reason=request.reason,
            target=request.target
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save reason")
            
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upserting reason: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/reasons")
async def delete_reason(project_id: str, query: str) -> Dict[str, str]:
    """
    删除原因
    
    :param project_id: 项目 ID
    :param query: 要删除的 Query
    :return: 操作结果消息
    """
    logger.info(f"Deleting reason for project {project_id}, query: {query[:20]}...")
    try:
        success: bool = reason_service.delete_reason(project_id, query)
        if not success:
            logger.warning(f"Delete failed: Reason not found for query {query[:20]}...")
            raise HTTPException(status_code=404, detail="Reason not found")
        return {"message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting reason: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ReasonImportRequest(BaseModel):
    """原因导入请求模型"""
    file_id: str
    query_col: str
    reason_col: str
    target_col: str

@router.post("/projects/{project_id}/reasons/import")
async def import_reasons(project_id: str, request: ReasonImportRequest) -> Dict[str, Any]:
    """
    从文件导入原因
    
    :param project_id: 项目 ID
    :param request: 导入请求 (file_id, columns)
    :return: 导入结果统计
    """
    from app.db import storage
    import os
    import pandas as pd
    
    logger.info(f"Importing reasons for project {project_id} from file {request.file_id}")
    
    # 查找文件路径
    file_path = None
    # 假设 storage.DATA_DIR 可访问，如果不一致需调整 import
    # storage module 应该有 DATA_DIR
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(request.file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break
            
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
        
    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        if request.reason_col not in df.columns:
             raise HTTPException(status_code=400, detail=f"Reason column '{request.reason_col}' not found in file")
             
        imported_count = 0
        for _, row in df.iterrows():
            q = row.get(request.query_col)
            r = row.get(request.reason_col)
            t = row.get(request.target_col)

            if pd.notna(q) and pd.notna(r) and str(r).strip():
                reason_service.upsert_reason(
                    project_id=project_id,
                    query=str(q),
                    reason=str(r),
                    target=str(t) if pd.notna(t) else ""
                )
                imported_count += 1
                
        logger.success(f"Imported {imported_count} reasons for project {project_id}")
        return {"imported_count": imported_count, "message": "Import successful"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import reasons: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/reasons/batch")
async def batch_delete_reasons(project_id: str, request: List[str]) -> Dict[str, Any]:
    """
    批量删除原因
    
    :param project_id: 项目 ID
    :param request: 要删除的 Query 列表
    :return: 删除结果
    """
    logger.info(f"Batch deleting {len(request)} reasons for project {project_id}")
    try:
        deleted_count = 0
        for query in request:
            if reason_service.delete_reason(project_id, query):
                deleted_count += 1
        return {"message": "Batch delete successful", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error batch deleting reasons: {e}")
        raise HTTPException(status_code=500, detail=str(e))
