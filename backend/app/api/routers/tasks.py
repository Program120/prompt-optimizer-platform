from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
import os
import pandas as pd
from app.db import storage
from app.services.task_service import TaskManager

router = APIRouter(prefix="/tasks", tags=["tasks"])
tm = TaskManager()

@router.post("/start")
async def start_task(
    project_id: str = Form(...),
    file_id: str = Form(...),
    query_col: str = Form(...),
    target_col: str = Form(...),
    reason_col: Optional[str] = Form(None),
    prompt: str = Form(...),
    extract_field: Optional[str] = Form(None),
    original_filename: Optional[str] = Form(None),
    validation_limit: Optional[int] = Form(None)
):
    # 查找文件路径
    file_path = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
        
    # 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    model_config = project.get("model_config")
    # 检查是否为接口验证模式
    is_interface_mode = model_config and model_config.get("validation_mode") == "interface"
    
    # 只有非接口验证模式才强制要求 api_key
    if not is_interface_mode and (not model_config or not model_config.get("api_key")):
        raise HTTPException(status_code=400, detail="请先在项目设置中配置模型参数(API Key)")

    task_id = tm.create_task(project_id, file_path, query_col, target_col, prompt, model_config, extract_field, original_filename, validation_limit, reason_col=reason_col)
    return {"task_id": task_id}

@router.get("/{task_id}")
async def get_task_status(task_id: str):
    # 获取任务状态时需要包含完整的 results 和 errors 数据
    status = tm.get_task_status(task_id, include_results=True)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status

@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    if tm.pause_task(task_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    if tm.resume_task(task_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.post("/{task_id}/stop")
async def stop_task(task_id: str):
    if tm.stop_task(task_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.delete("/{task_id}")
async def delete_task_endpoint(task_id: str):
    if storage.delete_task(task_id):
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="Task not found")

@router.get("/{task_id}/export")
async def export_task_results(task_id: str):
    # 导出时需要包含完整的 results 数据
    status = tm.get_task_status(task_id, include_results=True)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 获取所有结果
    results = status.get("results", [])
    # 允许导出空结果或正在运行的任务（可能已有部分结果）
    
    # 分离成功和失败的数据
    success_data = [r for r in results if r.get("is_correct")]
    failed_data = [r for r in results if not r.get("is_correct")]
    
    # 文件名包含进度信息
    current = len(results)
    total = status.get("total_count", "?")
    task_status = status.get("status", "unknown")
    export_path = os.path.join(storage.DATA_DIR, f"results_{task_id}.xlsx")
    
    # 使用 ExcelWriter 写入多个 sheet
    with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
        if success_data:
            df_success = pd.DataFrame(success_data)
            df_success.to_excel(writer, sheet_name='Success', index=False)
        else:
            # 如果没有成功数据，创建一个空的 DataFrame 并带有列头（如果有之前的结果作为参考，否则只有空sheet）
            pd.DataFrame(columns=["index", "query", "target", "output", "is_correct"]).to_excel(writer, sheet_name='Success', index=False)
            
        if failed_data:
            df_failed = pd.DataFrame(failed_data)
            df_failed.to_excel(writer, sheet_name='Failed', index=False)
        else:
            pd.DataFrame(columns=["index", "query", "target", "output", "is_correct"]).to_excel(writer, sheet_name='Failed', index=False)
    
    # 返回文件，文件名中包含进度信息
    filename = f"results_{task_id}_{current}of{total}.xlsx"
    return FileResponse(
        export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename
    )

@router.get("/{task_id}/download_dataset")
async def download_task_dataset(task_id: str):
    status = tm.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    file_path = status.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")
        
    original_filename = status.get("original_filename")
    if not original_filename:
        # 如果没有保存原始文件名，尝试从路径提取 UUID 或回退
        original_filename = os.path.basename(file_path)
    
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=original_filename
    )
