from datetime import datetime
import threading
import os
import time
import asyncio
from typing import Optional, Dict, Any, List, Set, Union

from fastapi import APIRouter, Form, HTTPException
from loguru import logger

from app.db import storage
from app.services.task_service import TaskManager
from app.services.optimizer_service import optimize_prompt, multi_strategy_optimize

router = APIRouter(prefix="/projects", tags=["auto-iterate"])
tm = TaskManager()

# 自动迭代状态存储
# 移到本模块内作为全局变量
auto_iterate_status: Dict[str, Any] = {}

@router.post("/{project_id}/auto-iterate")
async def start_auto_iterate(
    project_id: str,
    file_id: str = Form(...),
    query_col: str = Form(...),
    target_col: str = Form(...),
    reason_col: Optional[str] = Form(None),
    prompt: str = Form(...),
    max_rounds: int = Form(5),
    target_accuracy: float = Form(0.95),
    extract_field: str = Form(""),
    strategy: str = Form("multi"),
    validation_limit: Optional[int] = Form(None)
) -> Dict[str, Any]:
    """
    启动自动迭代优化任务
    
    :param project_id: 项目唯一标识
    :param file_id: 数据集文件ID
    :param query_col: 问题列名
    :param target_col: 目标答案列名
    :param reason_col: 推理过程列名 (可选)
    :param prompt: 初始提示词
    :param max_rounds: 最大迭代轮数
    :param target_accuracy: 目标准确率 (0-1)
    :param extract_field: 提取字段名 (可选)
    :param strategy: 优化策略 ('multi' 或 'simple')
    :param validation_limit: 验证数据量限制 (可选)
    :return: 任务启动状态与项目ID
    """
    
    # 查找文件路径
    file_path = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break
            
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    # 初始化状态
    status_data = {
        "status": "running",
        "current_round": 0,
        "max_rounds": max_rounds,
        "target_accuracy": target_accuracy,
        "current_accuracy": 0,
        "message": "正在启动...",
        "task_id": None,
        "should_stop": False,
        "project_id": project_id,
        "file_id": file_id,
        "query_col": query_col,
        "target_col": target_col,
        "reason_col": reason_col,
        "prompt": prompt,
        "extract_field": extract_field,
        "file_path": file_path,
        "strategy": strategy,
        "validation_limit": validation_limit
    }
    auto_iterate_status[project_id] = status_data
    # 持久化状态
    storage.save_auto_iterate_status(project_id, status_data)
    
    def run_auto_iterate():
        # 从全局状态获取最新配置 (防止闭包引用旧数据)
        nonlocal project_id
        # 重新加载文件路径和其他配置，防止闭包失效
        path = file_path 
        current_prompt = prompt
        
        # 记录上一轮成功的索引集合，用于检测新增失败案例 (regression)
        previous_success_indices = set()
        
        task_id = None  # 初始化 task_id，确保异常块可以访问
        
        try:
            for round_num in range(1, max_rounds + 1):
                # 重新读取状态，检查是否被停止
                status = auto_iterate_status.get(project_id)
                if not status or status["should_stop"]:
                    if status:
                        status["status"] = "stopped"
                        status["message"] = f"已在第 {round_num} 轮停止"
                        storage.save_auto_iterate_status(project_id, status)
                    return
                
                status["current_round"] = round_num
                status["message"] = f"第 {round_num}/{max_rounds} 轮: 正在执行任务..."
                storage.save_auto_iterate_status(project_id, status)
                logger.info(f"[AutoIterate {project_id}] Starting round {round_num}/{max_rounds}")
                
                # 启动任务
                # 获取模型配置 (优先使用项目配置)
                project = storage.get_project(project_id)
                model_config = project.get("model_config") if project else None
                if not model_config:
                    model_config = storage.get_model_config()
                    
                task_id = tm.create_task(project_id, path, query_col, status.get("target_col"), current_prompt, model_config, extract_field, validation_limit=validation_limit, reason_col=status.get("reason_col"))
                
                status["task_id"] = task_id
                storage.save_auto_iterate_status(project_id, status)
                logger.info(f"[AutoIterate {project_id}] Task {task_id} started")
                
                # 等待任务完成
                while True:
                    # 重新读取全局状态，检查是否收到停止信号
                    curr_status = auto_iterate_status.get(project_id)
                    if not curr_status: # 状态可能被删除了
                        # 状态丢失，停止任务
                        if task_id:
                            tm.stop_task(task_id)
                        return
                    if curr_status["should_stop"]:
                        tm.stop_task(task_id)
                        curr_status["status"] = "stopped"
                        curr_status["message"] = f"已在第 {round_num} 轮停止"
                        storage.save_auto_iterate_status(project_id, curr_status)
                        return

                    task_status = tm.get_task_status(task_id)
                    if not task_status:
                        logger.warning(f"[AutoIterate {project_id}] Task {task_id} status not found, waiting...")
                        time.sleep(1)
                        continue
                        
                    if task_status["status"] in ["completed", "stopped"]:
                        logger.info(f"[AutoIterate {project_id}] Task {task_id} finished with status: {task_status['status']}")
                        break
                    
                    time.sleep(1)
                
                # 计算准确率
                task_status = tm.get_task_status(task_id)
                current_results = task_status.get("results", [])
                current_errors = task_status.get("errors", [])
                
                if current_results:
                    accuracy = (len(current_results) - len(current_errors)) / len(current_results)
                else:
                    accuracy = 0
                
                # 注意：知识库准确率回填已在 task_manager.py 中统一处理
                
                # --- 新增失败案例检测逻辑 START ---
                # 1. 计算当前成功的索引集合
                current_error_indices = {e["index"] for e in current_errors}
                current_success_indices = {r["index"] for r in current_results if r["index"] not in current_error_indices}
                
                # 2. 找出那些"上一轮成功，但这一轮失败"的案例 (Regression)
                # 注意：第一轮时 previous_success_indices 为空，不会检测出 regression，这是符合预期的
                regression_indices = previous_success_indices.intersection(current_error_indices)
                
                regression_cases = []
                if regression_indices:
                    # 从 errors 中提取详情
                    for err in current_errors:
                        if err["index"] in regression_indices:
                            regression_cases.append(err)
                    
                    logger.info(f"[AutoIterate {project_id}] Round {round_num}: Found {len(regression_cases)} regression cases (indices: {regression_indices})")
                else:
                    logger.info(f"[AutoIterate {project_id}] Round {round_num}: No regression cases found.")

                # 3. 更新 previous_success_indices 为本轮的，供下一轮使用
                previous_success_indices = current_success_indices
                # --- 新增失败案例检测逻辑 END ---

                status["current_accuracy"] = accuracy
                status["message"] = f"第 {round_num}/{max_rounds} 轮: 准确率 {accuracy*100:.1f}%"
                storage.save_auto_iterate_status(project_id, status)
                
                # 检查是否达到目标准确率
                if accuracy >= target_accuracy:
                    status["status"] = "completed"
                    status["message"] = f"已达到目标准确率 {accuracy*100:.1f}% >= {target_accuracy*100:.1f}%，共 {round_num} 轮"
                    storage.save_auto_iterate_status(project_id, status)
                    logger.info(f"[AutoIterate {project_id}] Target accuracy reached! {accuracy*100:.1f}%")
                    return
                
                # 如果还有下一轮，优化提示词
                if round_num < max_rounds:
                    # 在开始优化之前再次检查停止信号 (重要: 优化过程可能很耗时)
                    curr_status = auto_iterate_status.get(project_id)
                    if curr_status and curr_status["should_stop"]:
                        logger.info(f"[AutoIterate {project_id}] Stop signal received before optimization")
                        tm.stop_task(task_id)
                        curr_status["status"] = "stopped"
                        curr_status["message"] = f"已在第 {round_num} 轮停止 (优化前)"
                        storage.save_auto_iterate_status(project_id, curr_status)
                        return
                    
                    if not task_status.get("errors"):
                         status["message"] = f"第 {round_num} 轮无错误，但未达标？停止优化。"
                         status["status"] = "completed"
                         storage.save_auto_iterate_status(project_id, status)
                         return

                    status["message"] = f"第 {round_num}/{max_rounds} 轮: 正在优化提示词..."
                    storage.save_auto_iterate_status(project_id, status)
                    logger.info(f"[AutoIterate {project_id}] Optimizing prompt with {len(task_status['errors'])} errors...")
                    

                    try:
                        # 获取策略
                        strategy = status.get("strategy", "multi")
                        
                        # 获取优化专用模型配置
                        # 优先使用 optimization_model_config，如果没有则回退到 model_config
                        opt_model_config = project.get("optimization_model_config")
                        if not opt_model_config or not opt_model_config.get("api_key"):
                            opt_model_config = model_config
                        
                        # 定义停止回调
                        def check_stop():
                            # 重新读取全局状态，检查是否收到停止信号
                            status = auto_iterate_status.get(project_id, {})
                            return status.get("should_stop", False) or status.get("status") == "stopped"

                        def _update_progress(pid, r_num, max_r, current_status, msg):
                            """更新进度回调 - 同时更新内存和数据库"""
                            full_msg = f"第 {r_num}/{max_r} 轮: {msg}"
                            
                            # 1. 更新内存状态 (关键修复)
                            if pid in auto_iterate_status:
                                auto_iterate_status[pid]["message"] = full_msg
                            
                            # 2. 更新传入的 status 对象
                            current_status["message"] = full_msg
                            
                            # 3. 持久化
                            storage.save_auto_iterate_status(pid, current_status)

                        if strategy == "simple":
                            # 简单优化
                            # 注意: optimize_prompt 是同步函数，但在线程中可直接调用
                            # optimize_prompt 返回字符串
                            opt_prompt = optimize_prompt(
                                current_prompt,
                                task_status["errors"],
                                opt_model_config,
                                project.get("optimization_prompt")
                            )
                            result = {
                                "optimized_prompt": opt_prompt,
                                "applied_strategies": [{"name": "Simple Optimization (Auto)", "success": True}],
                                "diagnosis": None
                            }
                        else:
                            # 多策略优化器
                            total_count = len(task_status.get("results", []))
                            dataset = task_status.get("results", [])
                            
                            # 提取 selected_modules (如果启用了标准模块优化)
                            selected_modules = None
                            if opt_model_config.get("enable_standard_module", False):
                                selected_modules = opt_model_config.get("selected_modules", [])
                            
                            result = asyncio.run(multi_strategy_optimize(
                                current_prompt, 
                                task_status["errors"], 
                                opt_model_config,
                                dataset=dataset,
                                total_count=total_count,
                                strategy_mode="auto",
                                max_strategies=opt_model_config.get("max_strategy_count", 3),
                                project_id=project_id,
                                newly_failed_cases=regression_cases,
                                should_stop=check_stop,
                                verification_config=model_config,
                                selected_modules=selected_modules,
                                on_progress=lambda msg: _update_progress(project_id, round_num, max_rounds, status, msg)
                            ))
                        
                        # 优化完成后再次检查停止信号
                        curr_status = auto_iterate_status.get(project_id)
                        if curr_status and curr_status["should_stop"]:
                            logger.info(f"[AutoIterate {project_id}] Stop signal received after optimization")
                            curr_status["status"] = "stopped"
                            curr_status["message"] = f"已在第 {round_num} 轮停止 (优化后)"
                            storage.save_auto_iterate_status(project_id, curr_status)
                            return
                        
                        new_prompt = result.get("optimized_prompt", current_prompt)
                        applied_strategies = result.get("applied_strategies", [])
                        
                        # 检查优化结果是否验证失败
                        validation_failed = result.get("validation_failed", False)
                        failure_reason = result.get("failure_reason", "")
                        
                        if validation_failed:
                            # 验证失败：记录失败的迭代记录，但不更新提示词
                            logger.warning(f"[AutoIterate {project_id}] 优化验证失败: {failure_reason}")
                            status["message"] = f"第 {round_num}/{max_rounds} 轮: {failure_reason}"
                            
                            # 保存失败的迭代记录（包含备注说明）
                            project = storage.get_project(project_id)
                            if project:
                                # 构建备注内容：未应用提示词及原因
                                not_applied_note = f"未应用提示词, 原因: {failure_reason}"
                                
                                project["iterations"].append({
                                    "previous_prompt": current_prompt,
                                    "optimized_prompt": new_prompt,
                                    "task_id": task_id,
                                    "accuracy_before": accuracy,
                                    "version": round_num,
                                    "created_at": datetime.now().isoformat(),
                                    "is_failed": True,
                                    "failure_reason": failure_reason,
                                    "not_applied": True,
                                    "note": not_applied_note,
                                    "strategy": ", ".join([s.get("name") for s in applied_strategies if s.get("success")])
                                })
                                # 不更新 current_prompt，保持原提示词
                                storage.update_project(project_id, project)
                            
                            storage.save_auto_iterate_status(project_id, status)
                            # 继续下一轮迭代
                            continue
                        
                        logger.info(f"[AutoIterate {project_id}] Prompt optimized successfully, strategies: {[s.get('name') for s in applied_strategies if s.get('success')]}")
                        
                        # 保存迭代记录
                        project = storage.get_project(project_id)
                        if project:
                            project["iterations"].append({
                                "previous_prompt": current_prompt,
                                "optimized_prompt": new_prompt,
                                "task_id": task_id,
                                "accuracy_before": accuracy,
                                "version": round_num,
                                "created_at": datetime.now().isoformat()
                            })
                            project["current_prompt"] = new_prompt
                            storage.update_project(project_id, project)
                        
                        # 重要：更新 prompt 用于下一轮
                        current_prompt = new_prompt
                        # 更新状态中的 prompt 记录
                        status["prompt"] = new_prompt
                        storage.save_auto_iterate_status(project_id, status)
                        
                    except Exception as e:
                        status["status"] = "error"
                        status["message"] = f"第 {round_num} 轮优化失败: {str(e)}"
                        storage.save_auto_iterate_status(project_id, status)
                        logger.error(f"[AutoIterate {project_id}] Optimization failed: {str(e)}")
                        # 优化失败也应该停止任务（如果还在运行? 此时task已经跑完）
                        return
            
            status["status"] = "completed"
            status["message"] = f"已完成 {max_rounds} 轮迭代，最终准确率 {status['current_accuracy']*100:.1f}%"
            storage.save_auto_iterate_status(project_id, status)
            
        except Exception as e:
            logger.error(f"Auto iterate run error: {e}")
            if project_id in auto_iterate_status:
                auto_iterate_status[project_id]["status"] = "error"
                auto_iterate_status[project_id]["message"] = f"系统错误: {str(e)}"
                storage.save_auto_iterate_status(project_id, auto_iterate_status[project_id])
            
            # 关键修复：发生异常时，如果底层任务仍在运行，强制停止
            if task_id:
                try:
                    logger.info(f"[AutoIterate {project_id}] Emergency stopping task {task_id} due to exception")
                    tm.stop_task(task_id)
                except Exception as stop_err:
                     logger.error(f"[AutoIterate {project_id}] Failed to emergency stop task: {stop_err}")
    
    # 后台线程执行
    thread = threading.Thread(target=run_auto_iterate)
    thread.daemon = True # 设置为守护线程
    thread.start()
    
    return {"status": "started", "project_id": project_id}

@router.get("/{project_id}/auto-iterate/status")
async def get_auto_iterate_status(project_id: str) -> Dict[str, Any]:
    """
    获取自动迭代状态
    
    :param project_id: 项目ID
    :return: 迭代状态详情
    """
    # 优先从内存获取
    if project_id in auto_iterate_status:
        return auto_iterate_status[project_id]
    
    # 尝试从磁盘恢复
    status = storage.get_auto_iterate_status(project_id)
    if status:
        # 如果是 running 状态但内存里没有（说明服务重启了），则标记为 interrupted 或 error
        if status["status"] == "running":
             status["status"] = "error"
             status["message"] = "服务重启，任务已中断"
             storage.save_auto_iterate_status(project_id, status)
             # 同步更新关联任务状态，防止前端状态不一致
             task_id = status.get("task_id")
             if task_id:
                 storage.update_task_status_only(task_id, "stopped")
                 logger.info(f"[AutoIterate {project_id}] 服务重启检测: 已将任务 {task_id} 标记为 stopped")
        auto_iterate_status[project_id] = status
        return status
        
    return {"status": "idle"}

@router.post("/{project_id}/auto-iterate/stop")
async def stop_auto_iterate(project_id: str) -> Dict[str, str]:
    """
    停止自动迭代任务
    
    设置停止标志后，迭代会在下一个检查点停止（如每轮开始前、优化前后等）。
    
    :param project_id: 项目ID
    :return: 停止请求的处理状态
    """
    logger.info(f"[AutoIterate {project_id}] Received STOP request")
    
    if project_id in auto_iterate_status:
        status = auto_iterate_status[project_id]
        status["should_stop"] = True
        # 立即保存状态
        storage.save_auto_iterate_status(project_id, status)
        
        # 同时尝试停止当前正在执行的任务
        task_id = status.get("task_id")
        if task_id:
            logger.info(f"[AutoIterate {project_id}] Stopping current task: {task_id}")
            tm.stop_task(task_id)
        
        return {"status": "stopping"}
    
    # 尝试从磁盘加载状态
    status = storage.get_auto_iterate_status(project_id)
    if status:
        status["should_stop"] = True
        status["status"] = "stopped"
        status["message"] = "已手动停止"
        # 停止关联任务，确保任务状态一致
        task_id = status.get("task_id")
        if task_id:
            storage.update_task_status_only(task_id, "stopped")
            logger.info(f"[AutoIterate {project_id}] 从磁盘停止: 已将任务 {task_id} 标记为 stopped")
        storage.save_auto_iterate_status(project_id, status)
        auto_iterate_status[project_id] = status
        return {"status": "stopping"}
    
    return {"status": "not_found"}
