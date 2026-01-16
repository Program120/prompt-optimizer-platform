import threading
import time
import json
import os
import pandas as pd
from typing import Dict, Any, Optional, List, Union
from loguru import logger
from app.db import storage
from app.core.llm_factory import LLMFactory
from app.engine.helpers.verifier import Verifier

class TaskManager:
    """
    任务管理器单例类
    
    负责创建、管理、暂停、恢复和停止后台任务。
    维护内存中的任务状态，并与磁盘存储同步。
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "TaskManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TaskManager, cls).__new__(cls)
                    cls._instance.tasks = {} # task_id -> {status, thread, stop_event, pause_event}
        return cls._instance

    def create_task(
        self, 
        project_id: str, 
        file_path: str, 
        query_col: str, 
        target_col: str, 
        prompt: str, 
        model_config: Dict[str, Any], 
        extract_field: Optional[str] = None, 
        original_filename: Optional[str] = None, 
        validation_limit: Optional[int] = None, 
        reason_col: Optional[str] = None
    ) -> str:
        """
        创建一个新的后台验证任务
        
        :param project_id: 项目 ID
        :param file_path: 数据文件绝对路径
        :param query_col: 问题列名
        :param target_col: 目标列名
        :param prompt: 提示词模板
        :param model_config: 模型配置字典
        :param extract_field: 提取字段 (可选)
        :param original_filename: 原始文件名 (可选)
        :param validation_limit: 验证数量限制 (可选)
        :param reason_col: 原因列名 (可选)
        :return: 任务 ID
        """
        task_id = f"task_{int(time.time())}"
        
        # 加载数据以校验
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        # [新增] 意图干预数据自动导入逻辑
        # 如果该项目的 IntentIntervention 为空，则认为这是一个新项目（或未初始化的项目），自动将文件中的数据导入到数据库
        # 这样后续的验证流程将统一使用 IntentIntervention 作为数据源
        try:
            from app.services import intervention_service
            existing_reasons = intervention_service.get_interventions_by_project(project_id)
            if not existing_reasons:
                logger.info(f"IntentIntervention is empty for {project_id}. Auto-importing from file...")
                intervention_service.import_dataset_to_interventions(
                    project_id=project_id,
                    df=df,
                    query_col=query_col,
                    target_col=target_col,
                    reason_col=reason_col
                )
        except Exception as e:
            logger.warning(f"Auto-import to IntentIntervention failed: {e}")

            
        task_info = {
            "id": task_id,
            "project_id": project_id,
            "file_path": file_path, # 保存文件路径
            "status": "running",
            "current_index": 0,
            "total_count": len(df),
            "query_col": query_col,
            "target_col": target_col,
            "reason_col": reason_col,
            "prompt": prompt,
            "extract_field": extract_field, # 保存需要提取的字段名
            "model_config": model_config,   # 保存模型配置
            "original_filename": original_filename if original_filename is not None else "", # 保存原始文件名
            "validation_limit": validation_limit,
            "results": [],
            "errors": []
        }
        
        stop_event = threading.Event()
        pause_event = threading.Event()
        pause_event.set()
        
        thread = threading.Thread(
            target=self._run_task, 
            args=(task_id, stop_event, pause_event)
        )
        
        self.tasks[task_id] = {
            "info": task_info,
            "thread": thread,
            "stop_event": stop_event,
            "pause_event": pause_event
        }
        
        # 立即保存初始状态，以便在历史记录中可见
        storage.save_task_status(project_id, task_id, task_info)
        
        thread.start()
        return task_id

    def _run_task(
        self, 
        task_id: str, 
        stop_event: threading.Event, 
        pause_event: threading.Event, 
        info_override: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        后台任务执行逻辑 (在独立线程中运行)
        
        :param task_id: 任务 ID
        :param stop_event: 停止信号
        :param pause_event: 暂停信号 (用于暂停/恢复)
        :param info_override: 任务信息覆盖 (用于恢复已存在任务)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        task = self.tasks[task_id]
        info = info_override or task["info"]
        
        project_id = info["project_id"]
        
        # [修改] 数据加载逻辑: 优先从意图干预数据库加载
        from app.services import intervention_service
        reasons = intervention_service.get_interventions_by_project(project_id)
        
        df = None
        used_source = "file"
        
        if reasons:
            logger.info(f"[Task {task_id}] Using {len(reasons)} rows from Intent Intervention (DB)")
            # 转换为 DataFrame
            reasons_data = [r.to_dict() for r in reasons]
            df = pd.DataFrame(reasons_data)
            
            # 映射列名以匹配 Task 配置 (IntentIntervention 只有 query, target, reason 固定列)
            # 我们需要构造一个符合 info["query_col"] 等配置的 DF
            
            # 1. 映射 Query 列
            q_col = info["query_col"]
            if "query" in df.columns and q_col != "query":
                df[q_col] = df["query"]
                
            # 2. 映射 Target 列
            t_col = info["target_col"]
            if "target" in df.columns and t_col != "target":
                 df[t_col] = df["target"]
                 
            # 3. 映射 Reason 列
            # 如果任务配置了 reason_col，则映射；如果没有，则更新 info 添加 reason_col
            r_col = info.get("reason_col")
            if not r_col:
                r_col = "reason"
                info["reason_col"] = r_col # 动态更新任务配置以使用 reason
            
            if "reason" in df.columns and r_col != "reason":
                df[r_col] = df["reason"]
                
            used_source = "db"
        else:
            # Fallback to file
            logger.info(f"[Task {task_id}] Using file source: {info['file_path']}")
            file_path = info["file_path"]
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
        
        query_col = info["query_col"]
        target_col = info["target_col"]
        reason_col = info.get("reason_col")
        prompt = info["prompt"]
        extract_field = info.get("extract_field")
        model_config = info.get("model_config", {"base_url": "https://api.openai.com/v1", "api_key": ""})

        concurrency = int(model_config.get("concurrency", 1))

        # Apply validation limit if set
        validation_limit = info.get("validation_limit")
        if validation_limit and isinstance(validation_limit, int) and validation_limit > 0:
            # We only change the effective total for processing loop
            # BUT we should probably also update info["total_count"] so frontend progress bar is correct
            # However, info["total_count"] was set to len(df) in create_task.
            # Let's adjust it here or rely on the loop limit.
            # Better to adjust existing total_count in info if not started? 
            # Or just use min here.
            # To make frontend progress bar correct (e.g. 0/5 instead of 0/1000), we should update info["total_count"].
            # But create_task already set it. 
            pass 
        
        # Re-calculate total based on limit
        full_df_len = len(df)
        limit = info.get("validation_limit")
        if limit and isinstance(limit, int) and limit > 0:
            total = min(full_df_len, limit)
        else:
            total = full_df_len
            
        # Update info total_count to reflect the limit (important for frontend progress)
        info["total_count"] = total

        # 初始化 client
        validation_mode = model_config.get("validation_mode", "llm")
        logger.info(f"[Task {task_id}] Starting | Mode: {validation_mode} | Concurrency: {concurrency}")
        
        task_client = None
        if validation_mode != "interface":
            task_client = LLMFactory.create_client(model_config)
        
        # 线程安全锁
        results_lock = threading.Lock()
        index_lock = threading.Lock()
        
        def process_single_query(i: int) -> Optional[Dict[str, Any]]:
            """
            处理单个查询
            
            :param i: 数据行索引
            :return: 查询结果字典或 None
            """
            if stop_event.is_set():
                return None
            pause_event.wait()
            
            # 获取原始值
            raw_query = df.iloc[i][query_col]
            raw_target = df.iloc[i][target_col]
            # 获取原因列的值 (如果配置了)
            raw_reason = None
            if reason_col and reason_col in df.columns:
                raw_reason = df.iloc[i][reason_col]

            # 处理 NaN 值：Pandas 读取空单元格时会产生 float('nan')
            # 使用 pd.isna() 检测并转换为空字符串，避免 str(nan) 产生 "nan" 字符串
            query = "" if pd.isna(raw_query) else str(raw_query)
            target = "" if pd.isna(raw_target) else str(raw_target)
            reason = "" if pd.isna(raw_reason) else str(raw_reason)
            
            result = Verifier.verify_single(
                index=i,
                query=query,
                target=target,
                prompt=prompt,
                model_config=model_config,
                extract_field=extract_field,
                reason_col_value=reason
            )
            return result
        
        # 使用线程池并发执行
        start_index = info["current_index"]
        total = info["total_count"]
        pending_indices = list(range(start_index, total))
        completed_count = start_index
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(process_single_query, i): i for i in pending_indices}
            
            for future in as_completed(futures):
                if stop_event.is_set():
                    info["status"] = "stopped"
                    # Python 3.8 doesn't support cancel_futures=True
                    executor.shutdown(wait=False)
                    break
                
                result = future.result()
                if result:
                    with results_lock:
                        info["results"].append(result)
                        if not result["is_correct"]:
                            info["errors"].append(result)
                        completed_count += 1
                        info["current_index"] = completed_count
                        
                        if completed_count % 10 == 0:
                            logger.info(f"[Task {task_id}] Progress: {completed_count}/{total}")
                        
                        # 每10条保存一次状态
                        if completed_count % 10 == 0:
                            storage.save_task_status(info["project_id"], task_id, info)
        
        if info["current_index"] == info["total_count"]:
            info["status"] = "completed"
            
            # --- 回填知识库准确率 ---
            # 当任务完成后，用当前准确率更新上一条优化分析记录的 accuracy_after
            try:
                results = info.get("results", [])
                errors = info.get("errors", [])
                if results:
                    accuracy = (len(results) - len(errors)) / len(results)
                    
                    # 导入知识库模块并更新
                    from app.engine.knowledge_base import OptimizationKnowledgeBase
                    project_id = info.get("project_id")
                    if project_id:
                        kb = OptimizationKnowledgeBase(project_id)
                        if kb.update_latest_accuracy_after(accuracy):
                            logger.info(f"[Task {task_id}] 已回填知识库的 accuracy_after: {accuracy*100:.1f}%")
            except Exception as kb_err:
                logger.warning(f"[Task {task_id}] 回填知识库准确率失败: {kb_err}")
        
        storage.save_task_status(info["project_id"], task_id, info)



    def pause_task(self, task_id: str) -> bool:
        """
        暂停任务
        
        :param task_id: 任务 ID
        :return: 是否暂停成功
        """
        if task_id in self.tasks:
            self.tasks[task_id]["pause_event"].clear()
            self.tasks[task_id]["info"]["status"] = "paused"
            # 保存状态变更到磁盘，以便前端获取历史时能看到最新状态
            storage.save_task_status(self.tasks[task_id]["info"]["project_id"], task_id, self.tasks[task_id]["info"])
            return True
        else:
            # 尝试从磁盘加载并暂停 (使用非破坏性更新)
            return storage.update_task_status_only(task_id, "paused")

    def resume_task(self, task_id: str) -> bool:
        """
        恢复任务
        
        :param task_id: 任务 ID
        :return: 是否恢复成功
        """
        if task_id in self.tasks:
            self.tasks[task_id]["pause_event"].set()
            self.tasks[task_id]["info"]["status"] = "running"
            # 保存状态变更到磁盘
            storage.save_task_status(self.tasks[task_id]["info"]["project_id"], task_id, self.tasks[task_id]["info"])
            return True
        else:
            # 尝试从磁盘加载并启动（关键修复：必须加载完整的 results/errors 才能追加）
            info = storage.get_task_status(task_id, include_results=True)
            if info and info["status"] != "completed":
                # 重新查找文件路径并启动
                project_id = info["project_id"]
                file_path = None
                # 这里简单处理，查找匹配 file_id 的文件
                # 实际可能需要更可靠的任务-文件关联
                # 为了简单，我们假设任务信息里存了足够的信息（虽然之前没存，现在补上）
                
                stop_event = threading.Event()
                pause_event = threading.Event()
                pause_event.set()
                
                # 需要从 info 中提取 df 等信息，或者重读文件
                # 这里我们假设文件还在 data 目录下且以 task 相关的某些方式命名
                # 实际上 _run_task 需要 df。
                # 由于这是演示，我们假设用户在同一会话中操作，或者我们把 df 加载逻辑放进 _run_task
                
                # 改进：让 _run_task 自己加载文件
                thread = threading.Thread(
                    target=self._run_task, 
                    args=(task_id, stop_event, pause_event, info)
                )
                self.tasks[task_id] = {
                    "info": info,
                    "thread": thread,
                    "stop_event": stop_event,
                    "pause_event": pause_event
                }
                thread.start()
                return True
        return False

    def stop_task(self, task_id: str) -> bool:
        """
        停止任务
        
        :param task_id: 任务 ID
        :return: 是否停止成功
        """
        if task_id in self.tasks:
            self.tasks[task_id]["stop_event"].set()
            self.tasks[task_id]["pause_event"].set() # 确保不被卡在暂停
            self.tasks[task_id]["info"]["status"] = "stopped"
            # 保存状态变更到磁盘
            storage.save_task_status(self.tasks[task_id]["info"]["project_id"], task_id, self.tasks[task_id]["info"])
            return True
        else:
            # 尝试从磁盘加载并标记为 stopped（使用非破坏性更新，防止清空 results）
            return storage.update_task_status_only(task_id, "stopped")

    def get_task_status(self, task_id: str, include_results: bool = True) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        :param task_id: 任务 ID
        :param include_results: 是否包含完整的 results 和 errors 数据
                               对于内存中的任务始终返回完整数据
                               从数据库加载时按此参数决定
        :return: 任务状态字典
        """
        # 优先从内存拿实时数据
        if task_id in self.tasks:
            # 内存中的任务包含了 results，如果不需要，我们可以过滤掉以减少传输
            task_info = self.tasks[task_id]["info"]
            if not include_results:
                # 返回副本并去除 heavy 字段
                info_copy = task_info.copy()
                info_copy.pop("results", None)
                info_copy.pop("errors", None)
                return info_copy
            return task_info
            
        # 从数据库加载，按需包含 results/errors
        return storage.get_task_status(task_id, include_results=include_results)

    def get_task_results(
        self, 
        task_id: str, 
        page: int = 1, 
        page_size: int = 50,
        result_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取分页的任务结果
        
        :param task_id: 任务 ID
        :param page: 页码
        :param page_size: 每页数量
        :param result_type: 结果类型 'success' | 'error' | None
        :param search: 搜索关键字
        :return: 分页结果
        """
        # 1. 如果任务在内存中，从内存分页
        if task_id in self.tasks:
            info = self.tasks[task_id]["info"]
            all_results = info.get("results", [])
            
            # 过滤
            filtered = all_results
            if result_type == 'success':
                filtered = [r for r in filtered if r.get('is_correct')]
            elif result_type == 'error':
                filtered = [r for r in filtered if not r.get('is_correct')]
                
            # 搜索过滤
            if search:
                search_lower = search.lower()
                filtered = [
                    r for r in filtered 
                    if (r.get('query') and search_lower in str(r.get('query')).lower()) or
                       (r.get('reason') and search_lower in str(r.get('reason')).lower())
                ]
                
            total = len(filtered)
            start = (page - 1) * page_size
            end = start + page_size
            page_results = filtered[start:end]
            
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "results": page_results
            }
            
        # 2. 如果任务不在内存中，从数据库查询
        return storage.get_task_results_paginated(task_id, page, page_size, result_type, search)
