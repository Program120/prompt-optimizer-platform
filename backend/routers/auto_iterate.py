from fastapi import APIRouter, Form, HTTPException
from typing import Optional, Dict, Any
from datetime import datetime
import threading
import os
import logging
import time
import asyncio

import storage
from task_manager import TaskManager
from optimizer import optimize_prompt, multi_strategy_optimize

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
    prompt: str = Form(...),
    max_rounds: int = Form(5),
    target_accuracy: float = Form(0.95),
    extract_field: str = Form(""),
    strategy: str = Form("multi")
):
    """启动自动迭代优化"""
    
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
        "prompt": prompt,
        "extract_field": extract_field,
        "file_path": file_path,
        "strategy": strategy
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
                logging.info(f"[AutoIterate {project_id}] Starting round {round_num}/{max_rounds}")
                
                # 启动任务
                # 获取模型配置 (优先使用项目配置)
                project = storage.get_project(project_id)
                model_config = project.get("model_config") if project else None
                if not model_config:
                    model_config = storage.get_model_config()
                    
                task_id = tm.create_task(project_id, path, query_col, target_col, current_prompt, model_config, extract_field)
                
                status["task_id"] = task_id
                storage.save_auto_iterate_status(project_id, status)
                logging.info(f"[AutoIterate {project_id}] Task {task_id} started")
                
                # 等待任务完成
                while True:
                    # 重新读取全局状态，检查是否收到停止信号
                    curr_status = auto_iterate_status.get(project_id)
                    if not curr_status: # 状态可能被删除了
                        return
                    if curr_status["should_stop"]:
                        tm.stop_task(task_id)
                        curr_status["status"] = "stopped"
                        curr_status["message"] = f"已在第 {round_num} 轮停止"
                        storage.save_auto_iterate_status(project_id, curr_status)
                        return

                    task_status = tm.get_task_status(task_id)
                    if not task_status:
                        logging.warning(f"[AutoIterate {project_id}] Task {task_id} status not found, waiting...")
                        time.sleep(1)
                        continue
                        
                    if task_status["status"] in ["completed", "stopped"]:
                        logging.info(f"[AutoIterate {project_id}] Task {task_id} finished with status: {task_status['status']}")
                        break
                    
                    time.sleep(1)
                
                # 计算准确率
                task_status = tm.get_task_status(task_id)
                if task_status and task_status["results"]:
                    accuracy = (len(task_status["results"]) - len(task_status.get("errors", []))) / len(task_status["results"])
                else:
                    accuracy = 0
                
                status["current_accuracy"] = accuracy
                status["message"] = f"第 {round_num}/{max_rounds} 轮: 准确率 {accuracy*100:.1f}%"
                storage.save_auto_iterate_status(project_id, status)
                
                # 检查是否达到目标准确率
                if accuracy >= target_accuracy:
                    status["status"] = "completed"
                    status["message"] = f"已达到目标准确率 {accuracy*100:.1f}% >= {target_accuracy*100:.1f}%，共 {round_num} 轮"
                    storage.save_auto_iterate_status(project_id, status)
                    logging.info(f"[AutoIterate {project_id}] Target accuracy reached! {accuracy*100:.1f}%")
                    return
                
                # 如果还有下一轮，优化提示词
                if round_num < max_rounds:
                    # 在开始优化之前再次检查停止信号 (重要: 优化过程可能很耗时)
                    curr_status = auto_iterate_status.get(project_id)
                    if curr_status and curr_status["should_stop"]:
                        logging.info(f"[AutoIterate {project_id}] Stop signal received before optimization")
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
                    logging.info(f"[AutoIterate {project_id}] Optimizing prompt with {len(task_status['errors'])} errors...")
                    

                    try:
                        # 获取策略
                        strategy = status.get("strategy", "multi")
                        
                        # 获取优化专用模型配置
                        # 优先使用 optimization_model_config，如果没有则回退到 model_config
                        opt_model_config = project.get("optimization_model_config")
                        if not opt_model_config or not opt_model_config.get("api_key"):
                            opt_model_config = model_config
                        
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
                            
                            result = asyncio.run(multi_strategy_optimize(
                                current_prompt, 
                                task_status["errors"], 
                                opt_model_config,
                                dataset=dataset,
                                total_count=total_count,
                                strategy_mode="auto",
                                max_strategies=1
                            ))
                        
                        # 优化完成后再次检查停止信号
                        curr_status = auto_iterate_status.get(project_id)
                        if curr_status and curr_status["should_stop"]:
                            logging.info(f"[AutoIterate {project_id}] Stop signal received after optimization")
                            curr_status["status"] = "stopped"
                            curr_status["message"] = f"已在第 {round_num} 轮停止 (优化后)"
                            storage.save_auto_iterate_status(project_id, curr_status)
                            return
                        
                        new_prompt = result.get("optimized_prompt", current_prompt)
                        applied_strategies = result.get("applied_strategies", [])
                        logging.info(f"[AutoIterate {project_id}] Prompt optimized successfully, strategies: {[s.get('name') for s in applied_strategies if s.get('success')]}")
                        
                        # 保存迭代记录
                        project = storage.get_project(project_id)
                        if project:
                            project["iterations"].append({
                                "old_prompt": current_prompt,
                                "new_prompt": new_prompt,
                                "task_id": task_id,
                                "accuracy": accuracy,
                                "round": round_num,
                                "created_at": datetime.now().isoformat()
                            })
                            project["current_prompt"] = new_prompt
                            projects = storage.get_projects()
                            for idx, p in enumerate(projects):
                                if p["id"] == project_id:
                                    projects[idx] = project
                                    break
                            storage.save_projects(projects)
                        
                        # 重要：更新 prompt 用于下一轮
                        current_prompt = new_prompt
                        # 更新状态中的 prompt 记录
                        status["prompt"] = new_prompt
                        storage.save_auto_iterate_status(project_id, status)
                        
                    except Exception as e:
                        status["status"] = "error"
                        status["message"] = f"第 {round_num} 轮优化失败: {str(e)}"
                        storage.save_auto_iterate_status(project_id, status)
                        logging.error(f"[AutoIterate {project_id}] Optimization failed: {str(e)}")
                        return
            
            status["status"] = "completed"
            status["message"] = f"已完成 {max_rounds} 轮迭代，最终准确率 {status['current_accuracy']*100:.1f}%"
            storage.save_auto_iterate_status(project_id, status)
            
        except Exception as e:
            logging.error(f"Auto iterate run error: {e}")
            if project_id in auto_iterate_status:
                auto_iterate_status[project_id]["status"] = "error"
                auto_iterate_status[project_id]["message"] = f"系统错误: {str(e)}"
                storage.save_auto_iterate_status(project_id, auto_iterate_status[project_id])
    
    # 后台线程执行
    thread = threading.Thread(target=run_auto_iterate)
    thread.daemon = True # 设置为守护线程
    thread.start()
    
    return {"status": "started", "project_id": project_id}

@router.get("/{project_id}/auto-iterate/status")
async def get_auto_iterate_status(project_id: str):
    """获取自动迭代状态"""
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
        auto_iterate_status[project_id] = status
        return status
        
    return {"status": "idle"}

@router.post("/{project_id}/auto-iterate/stop")
async def stop_auto_iterate(project_id: str):
    """
    停止自动迭代
    
    设置停止标志后，迭代会在下一个检查点停止：
    - 每轮开始前
    - 任务执行中每秒检查
    - 优化前后
    """
    logging.info(f"[AutoIterate {project_id}] Received STOP request")
    
    if project_id in auto_iterate_status:
        status = auto_iterate_status[project_id]
        status["should_stop"] = True
        # 立即保存状态
        storage.save_auto_iterate_status(project_id, status)
        
        # 同时尝试停止当前正在执行的任务
        task_id = status.get("task_id")
        if task_id:
            logging.info(f"[AutoIterate {project_id}] Stopping current task: {task_id}")
            tm.stop_task(task_id)
        
        return {"status": "stopping"}
    
    # 尝试从磁盘加载状态
    status = storage.get_auto_iterate_status(project_id)
    if status:
        status["should_stop"] = True
        status["status"] = "stopped"
        status["message"] = "已手动停止"
        storage.save_auto_iterate_status(project_id, status)
        auto_iterate_status[project_id] = status
        return {"status": "stopping"}
    
    return {"status": "not_found"}
