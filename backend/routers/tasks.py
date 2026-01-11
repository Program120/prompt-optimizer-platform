from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
import os
import pandas as pd
import storage
from task_manager import TaskManager

router = APIRouter(prefix="/tasks", tags=["tasks"])
tm = TaskManager()

@router.post("/start")
async def start_task(
    project_id: str = Form(...),
    file_id: str = Form(...),
    query_col: str = Form(...),
    target_col: str = Form(...),
    prompt: str = Form(...),
    extract_field: Optional[str] = Form(None)
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
    if not model_config or not model_config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在项目设置中配置模型参数(API Key)")

    task_id = tm.create_task(project_id, file_path, query_col, target_col, prompt, model_config, extract_field)
    return {"task_id": task_id}

@router.get("/{task_id}")
async def get_task_status(task_id: str):
    status = tm.get_task_status(task_id)
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

@router.get("/{task_id}/export")
async def export_task_errors(task_id: str):
    status = tm.get_task_status(task_id)
    if not status or not status.get("errors"):
        raise HTTPException(status_code=404, detail="Errors not found")
    
    df = pd.DataFrame(status["errors"])
    export_path = os.path.join(storage.DATA_DIR, f"errors_{task_id}.xlsx")
    df.to_excel(export_path, index=False)
    
    # 直接返回文件下载
    return FileResponse(
        export_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"errors_{task_id}.xlsx"
    )
