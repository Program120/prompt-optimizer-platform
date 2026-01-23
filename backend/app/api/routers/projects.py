from fastapi import APIRouter, Form, HTTPException, BackgroundTasks, Request
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.db import storage
from app.services.task_service import TaskManager
from app.services.optimizer_service import optimize_prompt, generate_optimize_context, multi_strategy_optimize
from pydantic import BaseModel
from loguru import logger
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/projects", tags=["projects"])
tm = TaskManager()


@router.get("")
async def list_projects() -> List[Dict[str, Any]]:
    """
    获取项目列表
    :return: 项目列表
    """
    projects = storage.get_projects()
    logger.debug(f"Fetched {len(projects)} projects")
    return projects

@router.post("")
async def create_project(name: str = Form(...), prompt: str = Form("...")) -> Dict[str, Any]:
    """
    创建新项目
    :param name: 项目名称
    :param prompt: 初始提示词
    :return: 创建的项目对象
    """
    logger.info(f"Creating new project: {name}")
    try:
        project = await run_in_threadpool(storage.create_project, name, prompt)
        logger.info(f"Project created successfully: {project.get('id')}")
        return project
    except Exception as e:
        logger.exception(f"Failed to create project {name}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@router.delete("/{project_id}")
async def delete_project(project_id: str, password: str = Form(...)) -> Dict[str, Any]:
    """
    删除项目
    :param project_id: 项目ID
    :param password: 删除确认密码
    :return: 操作结果
    """
    import os
    from dotenv import load_dotenv
    
    logger.warning(f"Attempting to delete project: {project_id}")

    # 重新加载环境变量以确保获取最新值
    load_dotenv(override=True)
    expected_password = os.getenv("PROJECT_DELETE_PASSWORD")
    
    if not expected_password:
        logger.error("Project delete password not configured")
        raise HTTPException(status_code=500, detail="Server configuration error: Delete password not set")
        
    if password != expected_password:
        logger.warning(f"Delete project failed: Invalid password for {project_id}")
        raise HTTPException(status_code=403, detail="Invalid password")
        
    success = storage.delete_project(project_id)
    if not success:
        logger.warning(f"Delete project failed: Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
        
    logger.info(f"Project deleted successfully: {project_id}")
    return {"success": True, "message": "Project deleted"}


@router.post("/{project_id}/reset")
async def reset_project(project_id: str) -> Dict[str, Any]:
    """
    重置项目
    将提示词恢复到初始状态，清空运行记录、迭代记录和优化分析
    :param project_id: 项目ID
    :return: 重置后的项目信息
    """
    logger.info(f"Resetting project: {project_id}")
    
    result = await run_in_threadpool(storage.reset_project, project_id)
    if not result:
        logger.error(f"Reset failed: Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    
    logger.info(f"Project reset successfully: {project_id}")
    return {"success": True, "message": "项目已重置", "project": result}

@router.get("/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    """
    获取单个项目详情
    :param project_id: 项目ID
    :return: 项目详情
    """
    p = storage.get_project(project_id)
    if not p:
        logger.warning(f"Get project failed: {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    return p

@router.delete("/{project_id}/iterations")
async def delete_iteration(project_id: str, timestamp: str) -> Dict[str, str]:
    """
    删除迭代记录 (不影响对应任务数据，只删除记录)
    :param project_id: 项目ID
    :param timestamp: 迭代记录的时间戳
    :return: 操作状态
    """
    logger.info(f"Deleting iteration for project {project_id}, timestamp: {timestamp}")
    success = storage.delete_project_iteration(project_id, timestamp)
    if not success:
        logger.warning(f"Delete iteration failed: {timestamp} not found in project {project_id}")
        raise HTTPException(status_code=404, detail="Iteration not found")
    return {"status": "success"}


class ProjectUpdateRequest(BaseModel):
    """
    项目更新请求体模型
    使用 JSON body 替代 Form data 以绕过 1MB multipart 限制
    """
    current_prompt: str
    name: Optional[str] = None
    query_col: Optional[str] = None
    target_col: Optional[str] = None
    reason_col: Optional[str] = None
    extract_field: Optional[str] = None
    file_info: Optional[Dict[str, Any]] = None
    auto_iterate_config: Optional[Dict[str, Any]] = None
    iterations: Optional[List[Dict[str, Any]]] = None
    model_cfg: Optional[Dict[str, Any]] = None
    optimization_model_config: Optional[Dict[str, Any]] = None
    optimization_prompt: Optional[str] = None
    validation_limit: Optional[str] = None


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdateRequest
) -> Dict[str, Any]:
    """
    保存/更新项目配置 (JSON Body 版本)
    
    :param project_id: 项目ID
    :param body: 项目更新请求体（JSON）
    :return: 更新后的项目信息
    """
    logger.info(f"Update project {project_id} - Prompt len: {len(body.current_prompt) if body.current_prompt else 0}")
    
    # 获取现有项目以进行增量更新
    existing_project = storage.get_project(project_id)
    if not existing_project:
        logger.warning(f"Update failed: Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 获取现有 config，如果没有则为空字典
    config = existing_project.get("config", {})
    
    # 仅当参数不为 None 时才更新 config
    if body.query_col is not None:
        config["query_col"] = body.query_col
    if body.target_col is not None:
        config["target_col"] = body.target_col
    if body.reason_col is not None:
        # 如果是空字符串，表示清除
        config["reason_col"] = body.reason_col if body.reason_col != "" else None
    if body.extract_field is not None:
        config["extract_field"] = body.extract_field

    # 处理 validation_limit
    if body.validation_limit is not None:
        config["validation_limit"] = body.validation_limit if body.validation_limit != "" else None

    # 文件信息 (已经是 dict，无需解析)
    if body.file_info is not None:
        config["file_info"] = body.file_info
            
    # 自动迭代配置 (已经是 dict)
    if body.auto_iterate_config is not None:
        config["auto_iterate_config"] = body.auto_iterate_config
    
    updates: Dict[str, Any] = {
        "current_prompt": body.current_prompt,
        "config": config
    }
    
    # 迭代历史 (已经是 list)
    if body.iterations is not None:
        updates["iterations"] = body.iterations
    
    # 模型配置 (校验模型)
    if body.model_cfg is not None:
        updates["model_config"] = body.model_cfg
            
    # 优化模型配置
    if body.optimization_model_config is not None:
        updates["optimization_model_config"] = body.optimization_model_config
            
    # 优化提示词
    if body.optimization_prompt is not None:
        updates["optimization_prompt"] = body.optimization_prompt

    if body.name:
        updates["name"] = body.name
    
    result = await run_in_threadpool(storage.update_project, project_id, updates)
    if not result:
        logger.error(f"Update failed: Storage returned None for project {project_id}")
        raise HTTPException(status_code=404, detail="Project not found")
        
    logger.info(f"Project updated successfully: {project_id}")
    return {"status": "success", "project": result}

@router.get("/{project_id}/tasks")
async def get_project_tasks(project_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    获取项目的任务历史列表
    :param project_id: 项目ID
    :return: 任务列表
    """
    tasks = storage.get_project_tasks(project_id)
    logger.debug(f"Fetched {len(tasks)} tasks for project {project_id}")
    return {"tasks": tasks}


# 优化任务状态存储
# 格式: {project_id: {"status": "running"|"completed"|"failed", "message": "...", "result": {...}}}
optimization_status: Dict[str, Dict[str, Any]] = {}

def background_optimize_task(
    project_id: str, 
    task_id: str, 
    strategy: str, 
    model_config: Dict[str, Any], 
    optimization_prompt: str, 
    project: Dict[str, Any], 
    task_status: Dict[str, Any], 
    verification_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    后台优化任务
    :param project_id: 项目ID
    :param task_id: 任务ID
    :param strategy: 优化策略
    :param model_config: 模型配置
    :param optimization_prompt: 优化提示词
    :param project: 项目信息
    :param task_status: 任务状态(包含errors)
    :param verification_config: 验证配置
    """
    import asyncio
    import traceback

    try:
        # 更新状态为运行中
        optimization_status[project_id] = {
            "status": "running",
            "message": "正在优化中...",
            "start_time": datetime.now().isoformat()
        }
        
        # 初始化验证状态变量
        validation_failed = False
        failure_reason = ""
        
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
            applied_strategies = [{"name": "Simple Optimization (Quick Mode)", "success": True}]
        else:
            # 多策略优化 (需要 async 运行)
            dataset = task_status.get("results", [])
            
            # 定义停止回调
            def check_stop():
                status = optimization_status.get(project_id, {})
                return status.get("should_stop", False) or status.get("status") == "stopped"

            # 提取 selected_modules (如果启用了标准模块优化)
            selected_modules = None
            if model_config.get("enable_standard_module", False):
                selected_modules = model_config.get("selected_modules", [])

            # 创建独立的事件循环，避免与 uvicorn 主循环冲突
            # 注意：asyncio.run() 会创建新循环并在完成后关闭，但在后台线程中可能导致死锁
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(multi_strategy_optimize(
                    project["current_prompt"], 
                    errors, 
                    model_config,
                    dataset=dataset,
                    total_count=total_count,
                    strategy_mode="auto",
                    max_strategies=model_config.get("max_strategy_count", 3),
                    project_id=project_id,
                    should_stop=check_stop,
                    verification_config=verification_config,
                    selected_modules=selected_modules,
                    on_progress=lambda msg: optimization_status[project_id].update({"message": msg})
                ))
            finally:
                loop.close()
            new_prompt = result.get("optimized_prompt", project["current_prompt"])
            applied_strategies = result.get("applied_strategies", [])
            diagnosis = result.get("diagnosis")
            
            # 检查优化结果是否验证失败
            validation_failed = result.get("validation_failed", False)
            failure_reason = result.get("failure_reason", "")
            
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

        # 计算当前准确率
        current_accuracy = (len(task_status["results"]) - len(task_status["errors"])) / len(task_status["results"]) if task_status.get("results") else 0

        iteration_record = {
            # 兼容旧字段
            "old_prompt": project["current_prompt"],
            "new_prompt": new_prompt,
            # 用于 IterationHistoryTab 显示
            "previous_prompt": project["current_prompt"],
            "optimized_prompt": new_prompt,
            "task_id": task_id,
            "dataset_path": dataset_path,
            "dataset_name": dataset_name,
            # 准确率字段
            "accuracy": current_accuracy,
            "accuracy_before": current_accuracy,
            "accuracy_after": None,  # 待下一次验证后回填
            "applied_strategies": [s.get("name") for s in applied_strategies if s.get("success")],
            "created_at": datetime.now().isoformat()
        }
        
        # 如果验证失败，标记迭代记录
        if validation_failed:
            iteration_record["is_failed"] = True
            iteration_record["failure_reason"] = failure_reason
            iteration_record["not_applied"] = True
            # 添加备注说明未应用提示词及原因
            iteration_record["note"] = f"未应用提示词, 原因: {failure_reason}"

        # from loguru import logger
        logger.info(f"Preparing to save iteration for project {project_id}, Task ID: {task_id}")

        # 重新获取项目以避免并发覆盖 (虽然这里还是有风险，但比直接用旧对象好)
        curr_project = storage.get_project(project_id)
        if curr_project:
            # 确保 iterations 字段存在
            if "iterations" not in curr_project:
                curr_project["iterations"] = []
            
            # 回填上一个迭代记录的 accuracy_after
            if len(curr_project["iterations"]) > 0:
                last_iteration = curr_project["iterations"][-1]
                # 只有当上一轮的 accuracy_after 为 None 时才回填
                if last_iteration.get("accuracy_after") is None:
                    last_iteration["accuracy_after"] = current_accuracy
                    logger.info(f"Backfilled accuracy_after={current_accuracy:.2%} to previous iteration")
            
            # 设置版本号
            iteration_record["version"] = len(curr_project["iterations"]) + 1
                
            curr_project["iterations"].append(iteration_record)
            
            # 只有验证通过时才更新 current_prompt
            if not validation_failed:
                curr_project["current_prompt"] = new_prompt
                logger.info(f"Validation passed, updating current_prompt to: {new_prompt[:50]}...")
            else:
                logger.warning(f"Validation failed (reason: {failure_reason}), NOT updating current_prompt.")
            
            projects = storage.get_projects()
            project_found = False
            for idx, p in enumerate(projects):
                if p["id"] == project_id:
                    projects[idx] = curr_project
                    project_found = True
                    break
            
            if project_found:
                storage.save_projects(projects)
                logger.info(f"Successfully saved projects with new iteration. Iteration count: {len(curr_project['iterations'])}")
            else:
                logger.error(f"Project {project_id} not found in projects list during save!")
        else:
            logger.error(f"Could not retrieve project {project_id} from storage for saving iteration.")
        
        # 如果验证失败，返回失败状态
        if validation_failed:
            optimization_status[project_id] = {
                "status": "failed",
                "message": failure_reason,
                "result": {
                    "new_prompt": new_prompt,
                    "applied_strategies": applied_strategies,
                    "diagnosis": diagnosis,
                    "validation_failed": True,
                    "failure_reason": failure_reason
                }
            }
            return
            
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
        logger.exception(f"Optimization task failed for project {project_id}")
        optimization_status[project_id] = {
            "status": "failed",
            "message": f"优化失败: {str(e)}"
        }

@router.post("/{project_id}/optimize/stop")
async def stop_optimization(project_id: str) -> Dict[str, str]:
    """
    停止优化任务
    :param project_id: 项目ID
    :return: 操作状态
    """
    if project_id in optimization_status and optimization_status[project_id]["status"] == "running":
        optimization_status[project_id]["should_stop"] = True
        optimization_status[project_id]["status"] = "stopped"
        optimization_status[project_id]["message"] = "正在停止..."
        logger.info(f"Stopping optimization for project {project_id}")
        return {"status": "stopping"}
    return {"status": "not_running"}

@router.post("/{project_id}/optimize")
async def optimize_project_prompt(
    project_id: str, 
    task_id: str, 
    strategy: str = "multi"
) -> Dict[str, str]:
    """
    启动异步优化任务
    :param project_id: 项目ID
    :param task_id: 任务ID
    :param strategy: 策略名称 (默认: multi)
    :return: 启动状态
    """
    import threading
    
    logger.info(f"Starting optimization for project {project_id}, task {task_id}, strategy {strategy}")

    project = storage.get_project(project_id)
    # 优化任务需要 errors 数据
    task_status = tm.get_task_status(task_id, include_results=True)
    
    if not project or not task_status:
        logger.error(f"Start optimization failed: Project {project_id} or Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Project or Task not found")
    
    # 检查是否已有正在运行的任务
    current_status = optimization_status.get(project_id)
    if current_status and current_status.get("status") == "running":
        # 如果已经运行很久了(比如超过10分钟)，允许强制重新开始？暂时不处理
        logger.warning(f"Optimization already running for project {project_id}")
        return {"status": "running", "message": "已有优化任务正在进行中"}
    
    # 获取优化模型配置
    model_config = project.get("optimization_model_config")
    if not model_config:
        model_config = project.get("model_config")
    
    # 获取验证配置 (项目默认配置)
    verification_config = project.get("model_config")
    
    if not model_config or not model_config.get("api_key"):
        logger.error(f"Optimization failed: Missing API Key for project {project_id}")
        raise HTTPException(status_code=400, detail="请先在项目设置中配置提示词优化模型参数(API Key)")
    
    # 兼容性处理
    if not strategy:
        strategy = "multi"
        
    optimization_prompt_text = project.get("optimization_prompt", "")
    
    # 启动后台线程
    thread = threading.Thread(
        target=background_optimize_task,
        args=(project_id, task_id, strategy, model_config, optimization_prompt_text, project, task_status, verification_config)
    )
    thread.daemon = True
    thread.start()
    
    logger.info(f"Optimization task thread started for project {project_id}")
    
    # 立即返回状态
    return {"status": "started", "message": "优化任务已启动"}

@router.get("/{project_id}/optimize/status")
async def get_optimization_status(project_id: str) -> Dict[str, Any]:
    """
    获取优化任务状态
    :param project_id: 项目ID
    :return: 任务状态
    """
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
    
    logger.debug(f"Dataset download requested for task {task_id}")

    # 下载数据集不需要 results/errors，优化性能
    task_status = tm.get_task_status(task_id, include_results=False)
    if not task_status:
        # 尝试直接从 storage 获取，防止内存中没有
        task_status = storage.get_task_status(task_id, include_results=False)
        
    if not task_status:
        logger.warning(f"Download dataset failed: Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")
        
    file_path = task_status.get("file_path")
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"Download dataset failed: File not found for task {task_id}")
        raise HTTPException(status_code=404, detail="Dataset file not found")
        
    return FileResponse(file_path, filename=os.path.basename(file_path))


@router.get("/{project_id}/optimize-context")
async def get_optimize_context(project_id: str, task_id: str) -> Dict[str, Any]:
    """
    获取优化上下文，用于外部优化功能
    :param project_id: 项目ID
    :param task_id: 任务ID
    :return: 格式化后的优化上下文
    """
    project = storage.get_project(project_id)
    # 获取优化上下文需要 errors 数据
    task_status = tm.get_task_status(task_id, include_results=True)
    
    if not project:
        logger.warning(f"Get optimize context failed: Project {project_id} not found")
        raise HTTPException(status_code=404, detail="Project not found")
    if not task_status:
        logger.warning(f"Get optimize context failed: Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")
    
    errors: list = task_status.get("errors", [])
    if not errors:
        logger.info(f"Get optimize context: No errors found for task {task_id}")
        raise HTTPException(status_code=400, detail="没有错误样例，无法生成优化上下文")
    
    # 获取优化提示词模板
    optimization_prompt: str = project.get("optimization_prompt", "")
    
    # 生成优化上下文
    context: str = generate_optimize_context(
        old_prompt=project["current_prompt"],
        errors=errors,
        system_prompt_template=optimization_prompt if optimization_prompt else None
    )
    
    logger.debug(f"Generated optimize context for project {project_id}, error count: {len(errors)}")
    return {"context": context, "error_count": len(errors)}


class NoteUpdate(BaseModel):
    note: str

@router.put("/{project_id}/tasks/{task_id}/note")
async def update_task_note(project_id: str, task_id: str, update: NoteUpdate) -> Dict[str, str]:
    """
    更新任务备注
    :param project_id: 项目ID
    :param task_id: 任务ID
    :param update: 备注信息
    :return: 更新后的备注
    """
    logger.info(f"Updating note for task {task_id}")
    success = storage.update_task_note(task_id, update.note)
    if not success:
        logger.warning(f"Update task note failed: Task {task_id} not found")
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "success", "note": update.note}


@router.put("/{project_id}/iterations/{timestamp}/note")
async def update_iteration_note(project_id: str, timestamp: str, update: NoteUpdate) -> Dict[str, str]:
    """
    更新迭代记录备注
    :param project_id: 项目ID
    :param timestamp: 时间戳
    :param update: 备注信息
    :return: 更新后的备注
    """
    logger.info(f"Updating note for iteration {timestamp} in project {project_id}")
    success = storage.update_project_iteration_note(project_id, timestamp, update.note)
    if not success:
        logger.warning(f"Update iteration note failed: {timestamp} not found in project {project_id}")
        raise HTTPException(status_code=404, detail="Iteration not found")
    return {"status": "success", "note": update.note}
