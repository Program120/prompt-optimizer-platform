from fastapi import APIRouter, Form, HTTPException
from typing import Optional
from datetime import datetime
import storage
from task_manager import TaskManager
from optimizer import optimize_prompt, generate_optimize_context, multi_strategy_optimize

router = APIRouter(prefix="/projects", tags=["projects"])
tm = TaskManager()


@router.get("")
async def list_projects():
    return storage.get_projects()

@router.post("")
async def create_project(name: str = Form(...), prompt: str = Form("...")):
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(storage.create_project, name, prompt)

@router.delete("/{project_id}")
async def delete_project(project_id: str, password: str = Form(...)):
    """
    删除项目
    需要校验密码
    """
    import os
    from dotenv import load_dotenv
    
    # 重新加载环境变量以确保获取最新值
    load_dotenv(override=True)
    expected_password = os.getenv("PROJECT_DELETE_PASSWORD")
    
    if not expected_password:
        raise HTTPException(status_code=500, detail="Server configuration error: Delete password not set")
        
    if password != expected_password:
        raise HTTPException(status_code=403, detail="Invalid password")
        
    success = storage.delete_project(project_id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return {"success": True, "message": "Project deleted"}

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
    optimization_prompt: Optional[str] = Form(None),
    validation_limit: Optional[str] = Form(None)
):
    """保存/更新项目配置"""
    import json as json_lib
    from loguru import logger
    
    logger.info(f"Update project {project_id} - Prompt len: {len(current_prompt) if current_prompt else 0}")
    
    # 获取现有项目以进行增量更新
    existing_project = storage.get_project(project_id)
    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 获取现有 config，如果没有则为空字典
    config = existing_project.get("config", {})
    
    # 仅当参数不为 None 时才更新 config
    if query_col is not None:
        config["query_col"] = query_col
    if target_col is not None:
        config["target_col"] = target_col
    if extract_field is not None:
        config["extract_field"] = extract_field
    if validation_limit is not None:
        # 如果是空字符串，表示清除
        config["validation_limit"] = validation_limit if validation_limit != "" else None

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


# 优化任务状态存储
# 格式: {project_id: {"status": "running"|"completed"|"failed", "message": "...", "result": {...}}}
optimization_status = {}

def background_optimize_task(project_id: str, task_id: str, strategy: str, model_config: dict, optimization_prompt: str, project: dict, task_status: dict):
    """后台优化任务"""
    import asyncio
    try:
        # 更新状态为运行中
        optimization_status[project_id] = {
            "status": "running",
            "message": "正在优化中...",
            "start_time": datetime.now().isoformat()
        }
        
        # 计算总样本数
        total_count = len(task_status.get("results", []))
        errors = task_status.get("errors", [])
        
        diagnosis = None
        applied_strategies = []
        new_prompt = project["current_prompt"]
        
        if strategy == "simple":
            # 简单优化
            # optimize_prompt 是同步函数
            new_prompt = optimize_prompt(
                project["current_prompt"],
                errors,
                model_config,
                optimization_prompt
            )
            applied_strategies = [{"name": "Simple Optimization", "success": True}]
        else:
            # 多策略优化 (需要 async 运行)
            dataset = task_status.get("results", [])
            # 在后台线程中运行 async 函数需要 new loop 或者 asyncio.run
            result = asyncio.run(multi_strategy_optimize(
                project["current_prompt"], 
                errors, 
                model_config,
                dataset=dataset,
                total_count=total_count,
                strategy_mode="auto",
                max_strategies=1,
                project_id=project_id
            ))
            new_prompt = result.get("optimized_prompt", project["current_prompt"])
            applied_strategies = result.get("applied_strategies", [])
            diagnosis = result.get("diagnosis")
            
        # 检查是否被停止
        if optimization_status.get(project_id, {}).get("should_stop"):
             optimization_status[project_id] = {
                "status": "stopped",
                "message": "优化已手动停止"
            }
             return

        # 保存一轮迭代
        dataset_path = task_status.get("file_path")
        dataset_name = None
        if dataset_path:
            import os
            dataset_name = os.path.basename(dataset_path)

        iteration_record = {
            "old_prompt": project["current_prompt"],
            "new_prompt": new_prompt,
            "task_id": task_id,
            "dataset_path": dataset_path,
            "dataset_name": dataset_name,
            "accuracy": (len(task_status["results"]) - len(task_status["errors"])) / len(task_status["results"]) if task_status.get("results") else 0,
            "applied_strategies": [s.get("name") for s in applied_strategies if s.get("success")],
            "created_at": datetime.now().isoformat()
        }
        
        # 重新获取项目以避免并发覆盖 (虽然这里还是有风险，但比直接用旧对象好)
        curr_project = storage.get_project(project_id)
        if curr_project:
            curr_project["iterations"].append(iteration_record)
            curr_project["current_prompt"] = new_prompt
            
            projects = storage.get_projects()
            for idx, p in enumerate(projects):
                if p["id"] == project_id:
                    projects[idx] = curr_project
                    break
            storage.save_projects(projects)
            
        # 更新状态为完成
        optimization_status[project_id] = {
            "status": "completed",
            "message": "优化完成",
            "result": {
                "new_prompt": new_prompt,
                "applied_strategies": applied_strategies,
                "diagnosis": diagnosis
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        optimization_status[project_id] = {
            "status": "failed",
            "message": f"优化失败: {str(e)}"
        }

@router.post("/{project_id}/optimize/stop")
async def stop_optimization(project_id: str):
    """停止优化任务"""
    if project_id in optimization_status and optimization_status[project_id]["status"] == "running":
        optimization_status[project_id]["should_stop"] = True
        optimization_status[project_id]["status"] = "stopped"
        optimization_status[project_id]["message"] = "正在停止..."
        return {"status": "stopping"}
    return {"status": "not_running"}

@router.post("/{project_id}/optimize")
async def optimize_project_prompt(project_id: str, task_id: str, strategy: str = "multi"):
    """
    启动异步优化任务
    """
    import threading
    
    project = storage.get_project(project_id)
    task_status = tm.get_task_status(task_id)
    
    if not project or not task_status:
        raise HTTPException(status_code=404, detail="Project or Task not found")
    
    # 检查是否已有正在运行的任务
    current_status = optimization_status.get(project_id)
    if current_status and current_status.get("status") == "running":
        # 如果已经运行很久了(比如超过10分钟)，允许强制重新开始？暂时不处理
        return {"status": "running", "message": "已有优化任务正在进行中"}
    
    # 获取优化模型配置
    model_config = project.get("optimization_model_config")
    if not model_config:
        model_config = project.get("model_config")
    
    if not model_config or not model_config.get("api_key"):
        raise HTTPException(status_code=400, detail="请先在项目设置中配置提示词优化模型参数(API Key)")
    
    # 兼容性处理
    if not strategy:
        strategy = "multi"
        
    optimization_prompt = project.get("optimization_prompt")
    
    # 启动后台线程
    thread = threading.Thread(
        target=background_optimize_task,
        args=(project_id, task_id, strategy, model_config, optimization_prompt, project, task_status)
    )
    thread.daemon = True
    thread.start()
    
    # 立即返回状态
    return {"status": "started", "message": "优化任务已启动"}

@router.get("/{project_id}/optimize/status")
async def get_optimization_status(project_id: str):
    """获取优化任务状态"""
    status = optimization_status.get(project_id)
    if not status:
        return {"status": "idle"}
    return status


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
