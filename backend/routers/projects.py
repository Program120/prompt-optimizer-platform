from fastapi import APIRouter, Form, HTTPException
from typing import Optional
from datetime import datetime
import storage
from task_manager import TaskManager
from optimizer import optimize_prompt, generate_optimize_context

router = APIRouter(prefix="/projects", tags=["projects"])
tm = TaskManager()


@router.get("")
async def list_projects():
    return storage.get_projects()

@router.post("")
async def create_project(name: str = Form(...), prompt: str = Form(...)):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(storage.create_project, name, prompt)

@router.get("/{project_id}")
async def get_project(project_id: str):
    p = storage.get_project(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    return p

@router.put("/{project_id}")
async def update_project(
    project_id: str,
    current_prompt: str = Form(...),
    name: Optional[str] = Form(None),
    query_col: Optional[str] = Form(None),
    target_col: Optional[str] = Form(None),
    extract_field: Optional[str] = Form(None),
    file_info: Optional[str] = Form(None),
    auto_iterate_config: Optional[str] = Form(None),
    iterations: Optional[str] = Form(None),
    model_cfg: Optional[str] = Form(None),
    optimization_model_config: Optional[str] = Form(None),
    optimization_prompt: Optional[str] = Form(None)
):
    """保存/更新项目配置"""
    import json as json_lib
    config = {
        "query_col": query_col,
        "target_col": target_col,
        "extract_field": extract_field
    }
    # 解析文件信息 JSON
    if file_info:
        try:
            config["file_info"] = json_lib.loads(file_info)
        except:
            pass
    # 解析自动迭代配置 JSON
    if auto_iterate_config:
        try:
            config["auto_iterate_config"] = json_lib.loads(auto_iterate_config)
        except:
            pass
    
    # 解析迭代历史 JSON
    iterations_list = None
    if iterations:
        try:
            iterations_list = json_lib.loads(iterations)
        except:
            pass
    
    updates = {
        "current_prompt": current_prompt,
        "config": config
    }
    if iterations_list is not None:
        updates["iterations"] = iterations_list
    
    # 解析模型配置 JSON (校验模型)
    if model_cfg:
        try:
            updates["model_config"] = json_lib.loads(model_cfg)
        except:
            pass
            
    # 解析优化模型配置 JSON
    if optimization_model_config:
        try:
            updates["optimization_model_config"] = json_lib.loads(optimization_model_config)
        except:
            pass
            
    # 优化提示词
    if optimization_prompt is not None:
        updates["optimization_prompt"] = optimization_prompt

    if name:
        updates["name"] = name
    
    from starlette.concurrency import run_in_threadpool
    result = await run_in_threadpool(storage.update_project, project_id, updates)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "success", "project": result}

@router.get("/{project_id}/tasks")
async def get_project_tasks(project_id: str):
    """获取项目的任务历史列表"""
    tasks = storage.get_project_tasks(project_id)
    return {"tasks": tasks}

@router.post("/{project_id}/optimize")
async def optimize_project_prompt(project_id: str, task_id: str):
    project = storage.get_project(project_id)
    task_status = tm.get_task_status(task_id)
    
    if not project or not task_status:
        raise HTTPException(status_code=404, detail="Project or Task not found")
    
    # 获取优化模型配置
    # 如果项目有 optimization_model_config 则使用，否则回退到 model_config
    model_config = project.get("optimization_model_config")
    
    # 如果没有专门的优化配置，使用通用配置
    if not model_config:
        model_config = project.get("model_config")
    
    if not model_config or not model_config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在项目设置中配置提示词优化模型参数(API Key)")
    
    # 获取优化提示词
    # 优先使用项目自定义的 optimization_prompt，否则使用 None (optimizer.py 会使用默认值)
    optimization_prompt = project.get("optimization_prompt")

    # 调用优化函数（可能抛出异常）
    try:
        from starlette.concurrency import run_in_threadpool
        new_prompt = await run_in_threadpool(
            optimize_prompt,
            project["current_prompt"], 
            task_status["errors"], 
            model_config,
            system_prompt_template=optimization_prompt
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")
    
    # 保存一轮迭代
    dataset_path = task_status.get("file_path")
    dataset_name = None
    if dataset_path:
        import os
        dataset_name = os.path.basename(dataset_path)

    project["iterations"].append({
        "old_prompt": project["current_prompt"],
        "new_prompt": new_prompt,
        "task_id": task_id,
        "dataset_path": dataset_path,
        "dataset_name": dataset_name,
        "accuracy": (len(task_status["results"]) - len(task_status["errors"])) / len(task_status["results"]) if task_status["results"] else 0,
        "created_at": datetime.now().isoformat()
    })
    project["current_prompt"] = new_prompt
    
    projects = storage.get_projects()
    for idx, p in enumerate(projects):
        if p["id"] == project_id:
            projects[idx] = project
            break
    storage.save_projects(projects)
    
    return {"new_prompt": new_prompt}


@router.get("/tasks/{task_id}/dataset")
async def download_task_dataset(task_id: str):
    """
    下载任务使用的数据集
    :param task_id: 任务ID
    :return: 文件流
    """
    from fastapi.responses import FileResponse
    import os
    
    task_status = tm.get_task_status(task_id)
    if not task_status:
        # 尝试直接从 storage 获取，防止内存中没有
        task_status = storage.get_task_status(task_id)
        
    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found")
        
    file_path = task_status.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found")
        
    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.get("/{project_id}/optimize-context")
async def get_optimize_context(project_id: str, task_id: str):
    """
    获取优化上下文，用于外部优化功能
    :param project_id: 项目ID
    :param task_id: 任务ID
    :return: 格式化后的优化上下文
    """
    project = storage.get_project(project_id)
    task_status = tm.get_task_status(task_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    errors: list = task_status.get("errors", [])
    if not errors:
        raise HTTPException(status_code=400, detail="没有错误样例，无法生成优化上下文")
    
    # 获取优化提示词模板
    optimization_prompt: str = project.get("optimization_prompt", "")
    
    # 生成优化上下文
    context: str = generate_optimize_context(
        old_prompt=project["current_prompt"],
        errors=errors,
        system_prompt_template=optimization_prompt if optimization_prompt else None
    )
    
    return {"context": context, "error_count": len(errors)}
