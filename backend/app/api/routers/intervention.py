"""
意图干预 API 路由

定义对意图干预库 (IntentIntervention) 的增删改查接口。
包括："""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
import io
import pandas as pd
from pydantic import BaseModel
from loguru import logger
from app.services import intervention_service
from app.models import IntentIntervention
from app.engine.helpers.verifier import Verifier
from app.db import storage

router = APIRouter()

class InterventionUpsertRequest(BaseModel):
    """意图干预更新请求模型"""
    query: str
    reason: str = ""
    target: str = ""
    file_id: str = ""

class InterventionResponse(BaseModel):
    """意图干预响应模型"""
    id: int
    project_id: str
    query: str
    reason: str
    target: str
    original_target: Optional[str] = None
    is_target_modified: bool = False
    file_id: str = ""
    updated_at: str

@router.get("/projects/{project_id}/interventions", response_model=Dict[str, Any])
async def list_interventions(
    project_id: str, 
    page: int = 1, 
    page_size: int = 50,
    search: Optional[str] = None,
    filter_type: Optional[str] = None,
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取项目下所有意图干预数据 (分页)
    """
    # logger.info(f"Fetching interventions for project: {project_id}, page: {page}")
    try:
        # 使用分页获取
        result = intervention_service.get_interventions_paginated(project_id, page, page_size, search, filter_type, file_id)
        # Convert items to dict
        result["items"] = [r.to_dict() for r in result["items"]]
        return result
    except Exception as e:
        logger.error(f"Error fetching interventions for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/interventions", response_model=InterventionResponse)
async def upsert_intervention(project_id: str, request: InterventionUpsertRequest) -> Dict[str, Any]:
    """
    添加或更新干预项
    """
    logger.info(f"Upserting intervention for project {project_id}, query: {request.query[:20]}...")
    if not request.query:
        logger.warning("Upsert failed: Query is required")
        raise HTTPException(status_code=400, detail="Query is required")
    
    try:
        result: Optional[IntentIntervention] = intervention_service.upsert_intervention(
            project_id=project_id,
            query=request.query,
            reason=request.reason,
            target=request.target,
            file_id=request.file_id
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save intervention")
            
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upserting intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/interventions")
async def delete_intervention(project_id: str, query: str) -> Dict[str, str]:
    """
    删除干预项
    """
    logger.info(f"Deleting intervention for project {project_id}, query: {query[:20]}...")
    try:
        success: bool = intervention_service.delete_intervention(project_id, query)
        if not success:
            logger.warning(f"Delete failed: Intervention not found for query {query[:20]}...")
            raise HTTPException(status_code=404, detail="Intervention not found")
        return {"message": "Deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class InterventionResetRequest(BaseModel):
    query: str

@router.post("/projects/{project_id}/interventions/reset")
async def reset_intervention(project_id: str, request: InterventionResetRequest) -> Dict[str, Any]:
    """
    重置干预项
    """
    logger.info(f"Resetting intervention for project {project_id}, query: {request.query[:20]}...")
    try:
        success = intervention_service.reset_intervention(project_id, request.query)
        if not success:
             raise HTTPException(status_code=404, detail="Intervention not found")
        return {"message": "Reset successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting intervention: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class InterventionImportRequest(BaseModel):
    """干预导入请求模型"""
    file_id: str
    query_col: str
    reason_col: Optional[str] = None
    target_col: str

@router.post("/projects/{project_id}/interventions/sync")
async def sync_interventions(project_id: str, request: InterventionImportRequest) -> Dict[str, Any]:
    """
    同步文件数据到意图干预库 (同 import)
    """
    return await import_interventions(project_id, request)


class InterventionTestRequest(BaseModel):
    """干预测试请求模型"""
    query: str
    target: str
    reason: Optional[str] = None


class QueryExpandRequest(BaseModel):
    """Query 举一反三请求模型"""
    query: str           # 原始 query
    target: str          # 预期结果
    count: int = 5       # 生成数量，默认 5 个


class QueryExpandImportRequest(BaseModel):
    """Query 举一反三导入请求模型"""
    queries: list[str]   # 要导入的 query 列表
    target: str          # 预期结果
    file_id: str = ""    # 文件版本 ID


@router.post("/projects/{project_id}/interventions/expand")
async def expand_query(project_id: str, request: QueryExpandRequest) -> Dict[str, Any]:
    """
    Query 举一反三：根据一个 Query 生成多个相似 Query（仅生成，不导入）

    :param project_id: 项目 ID
    :param request: 包含原始 query、target、生成数量
    :return: 生成的 Query 列表
    """
    logger.info(f"[举一反三] 项目 {project_id}, 原始 Query: {request.query[:30]}...")

    # 1. 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    model_config = project.get("model_config")
    if not model_config or not model_config.get("api_key"):
        raise HTTPException(status_code=400, detail="项目未配置模型 API Key，请先在项目设置中配置")

    try:
        # 2. 调用 LLM 生成相似 Query
        expanded_queries = await intervention_service.generate_similar_queries(
            original_query=request.query,
            target=request.target,
            count=request.count,
            model_config=model_config
        )

        logger.success(f"[举一反三] 成功生成 {len(expanded_queries)} 个相似 Query")

        return {
            "original_query": request.query,
            "expanded_queries": expanded_queries,
            "message": f"成功生成 {len(expanded_queries)} 条相似查询"
        }

    except Exception as e:
        logger.error(f"[举一反三] 失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.post("/projects/{project_id}/interventions/expand/import")
async def import_expanded_queries(project_id: str, request: QueryExpandImportRequest) -> Dict[str, Any]:
    """
    导入举一反三生成的 Query 列表

    :param project_id: 项目 ID
    :param request: 包含要导入的 query 列表、target、file_id
    :return: 导入结果
    """
    logger.info(f"[举一反三导入] 项目 {project_id}, 导入 {len(request.queries)} 条")

    if not request.queries:
        raise HTTPException(status_code=400, detail="导入列表不能为空")

    try:
        imported_count = 0
        for q in request.queries:
            if q.strip():
                result = intervention_service.upsert_intervention(
                    project_id=project_id,
                    query=q.strip(),
                    target=request.target,
                    reason="",
                    file_id=request.file_id
                )
                if result:
                    imported_count += 1

        logger.success(f"[举一反三导入] 成功导入 {imported_count} 条")

        return {
            "imported_count": imported_count,
            "message": f"成功导入 {imported_count} 条数据"
        }

    except Exception as e:
        logger.error(f"[举一反三导入] 失败: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.post("/projects/{project_id}/interventions/test")
async def test_intervention(project_id: str, request: InterventionTestRequest) -> Dict[str, Any]:
    """
    对单条干预数据进行单元测试
    """
    logger.info(f"Testing intervention for project {project_id}, query: {request.query[:20]}...")
    
    # 1. 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    model_config = project.get("model_config")
    if not model_config or not model_config.get("api_key"):
        if model_config.get("validation_mode") != "interface":
            raise HTTPException(status_code=400, detail="Missing API Key in project model config")

    # 2. 获取其他配置
    prompt = project.get("current_prompt", "")
    config = project.get("config", {})
    extract_field = config.get("extract_field")
    
    # 3. 执行验证
    try:
        # 使用 Verifier 执行单条验证
        # index 设为 -1 表示这是测试请求
        result = Verifier.verify_single(
            index=-1,
            query=request.query,
            target=request.target,
            prompt=prompt,
            model_config=model_config,
            extract_field=extract_field,
            reason_col_value=request.reason
        )
        
        return result
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.post("/projects/{project_id}/interventions/import")
async def import_interventions(project_id: str, request: InterventionImportRequest) -> Dict[str, Any]:
    """
    从文件导入干预数据
    """
    from app.db import storage
    import os
    import pandas as pd
    
    logger.info(f"Importing interventions for project {project_id} from file {request.file_id}")
    
    # 查找文件路径
    file_path = None
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
            
        if request.reason_col and request.reason_col not in df.columns:
             logger.warning(f"Reason column '{request.reason_col}' not found in file, ignoring reason import.")
             request.reason_col = None

        imported_count = intervention_service.import_dataset_to_interventions(
            project_id=project_id,
            df=df,
            query_col=request.query_col,
            target_col=request.target_col,
            reason_col=request.reason_col,
            file_id=request.file_id
        )
                
        logger.success(f"Imported {imported_count} interventions for project {project_id}")
        return {"imported_count": imported_count, "message": "Import successful"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to import interventions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/interventions/batch")
async def batch_delete_interventions(project_id: str, request: List[str]) -> Dict[str, Any]:
    """
    批量删除干预项
    """
    logger.info(f"Batch deleting {len(request)} interventions for project {project_id}")
    try:
        deleted_count = 0
        for query in request:
            if intervention_service.delete_intervention(project_id, query):
                deleted_count += 1
        return {"message": "Batch delete successful", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error batch deleting interventions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/interventions/export")
async def export_interventions_endpoint(project_id: str, file_id: str = None) -> Any:
    """
    导出项目下意图干预数据
    
    :param project_id: 项目 ID
    :param file_id: 可选，文件版本 ID，如果指定则仅导出该版本的数据
    :return: Excel 文件流
    """
    logger.info(f"Exporting interventions for project {project_id}, file_id={file_id}")
    try:
        interventions = intervention_service.get_interventions_by_project(project_id, file_id=file_id)
        if not interventions:
             # Return empty df
             df = pd.DataFrame(columns=["query", "target", "reason"])
        else:
             df = pd.DataFrame([r.to_dict() for r in interventions])
             
        cols_to_export = ["query", "target", "reason"]
        existing_cols = [c for c in cols_to_export if c in df.columns]
        export_df = df[existing_cols] if not df.empty else df
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='Interventions')
        
        output.seek(0)
        
        # 生成带有版本信息的文件名
        filename_suffix = f"_{file_id}" if file_id else ""
        response = StreamingResponse(
            output, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response.headers["Content-Disposition"] = f"attachment; filename=intent_intervention_{project_id}{filename_suffix}.xlsx"
        return response
        
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/interventions/clear")
async def clear_interventions_endpoint(project_id: str, file_id: Optional[str] = None) -> Dict[str, Any]:
    """
    清空项目下所有意图干预数据
    """
    logger.info(f"Clearing all interventions for project {project_id}, file_id={file_id}")
    try:
        deleted_count = intervention_service.clear_interventions(project_id, file_id)
        return {"message": "Clear successful", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Error clearing interventions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
