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
        
        # 从文件路径提取 file_id
        # file_path 格式通常是: DATA_DIR/uuid_filename.ext
        file_basename = os.path.basename(file_path)
        file_id = file_basename.split("_")[0] if "_" in file_basename else file_basename.rsplit(".", 1)[0]
        
        # 加载数据以校验
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        # [新增] 意图干预数据自动导入逻辑 (按 file_id 版本检查)
        # 如果该项目的当前 file_id 对应的 IntentIntervention 为空，则自动将文件中的数据导入到数据库
        try:
            from app.services import intervention_service
            existing_reasons = intervention_service.get_interventions_by_project(project_id, file_id=file_id)
            if not existing_reasons:
                logger.info(f"IntentIntervention is empty for project {project_id}, file_id={file_id}. Auto-importing from file...")
                intervention_service.import_dataset_to_interventions(
                    project_id=project_id,
                    df=df,
                    query_col=query_col,
                    target_col=target_col,
                    reason_col=reason_col,
                    file_id=file_id
                )
                logger.success(f"Auto-imported {len(df)} rows to IntentIntervention for file_id={file_id}")
        except Exception as e:
            logger.warning(f"Auto-import to IntentIntervention failed: {e}")

            
        task_info = {
            "id": task_id,
            "project_id": project_id,
            "file_path": file_path,
            "file_id": file_id,  # 新增：保存文件版本 ID
            "status": "running",
            "current_index": 0,
            "total_count": len(df),
            "query_col": query_col,
            "target_col": target_col,
            "reason_col": reason_col,
            "prompt": prompt,
            "extract_field": extract_field,
            "model_config": model_config,
            "original_filename": original_filename if original_filename is not None else "",
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
        file_id = info.get("file_id", "")  # 获取文件版本 ID
        
        # [关键修复] 数据加载逻辑: 确保使用最新的意图修正
        # 策略：
        # 1. 获取项目下所有干预数据（不筛选 file_id）
        # 2. 创建 query -> 干预记录 的映射
        # 3. 如果同一 query 有多条记录，优先使用 is_target_modified=True 的记录
        # 这确保了无论 file_id 如何，都能使用最新的意图修正
        from app.services import intervention_service
        
        # 获取项目下所有干预数据
        all_reasons = intervention_service.get_interventions_by_project(project_id, file_id=None)
        logger.info(f"[Task {task_id}] Loaded {len(all_reasons)} total interventions for project {project_id}")
        
        # 创建 query -> 干预记录 的映射，优先使用修正过的记录
        query_to_intervention: Dict[str, Any] = {}
        for r in all_reasons:
            existing = query_to_intervention.get(r.query)
            if existing is None:
                # 第一次遇到此 query，直接保存
                query_to_intervention[r.query] = r
            elif r.is_target_modified and not existing.is_target_modified:
                # 新记录被修正过，而旧记录没有，使用新记录
                query_to_intervention[r.query] = r
            elif r.file_id == file_id and existing.file_id != file_id:
                # 新记录的 file_id 匹配当前任务，优先使用
                # 但如果旧记录被修正过，仍然优先使用旧记录
                if not existing.is_target_modified:
                    query_to_intervention[r.query] = r
        
        # 转换为列表，并按 created_at 倒序排序（新增数据优先执行）
        reasons = sorted(
            query_to_intervention.values(), 
            key=lambda r: r.created_at if r.created_at else "", 
            reverse=True
        )
        
        # 统计修正记录数量
        modified_count: int = sum(1 for r in reasons if r.is_target_modified)
        logger.info(f"[Task {task_id}] After deduplication: {len(reasons)} unique queries, {modified_count} modified (sorted by created_at desc)")
        
        df = None
        used_source = "file"
        
        if reasons:
            logger.info(f"[Task {task_id}] Using {len(reasons)} rows from Intent Intervention (DB)")
            # 转换为 DataFrame
            reasons_data = [r.to_dict() for r in reasons]
            df = pd.DataFrame(reasons_data)
            
            # 从数据库加载时，使用固定的列名 (IntentIntervention 表结构固定)
            query_col = "query"
            target_col = "target"
            reason_col = "reason"
            
            # 更新 info 以反映实际使用的列名
            info["_actual_query_col"] = query_col
            info["_actual_target_col"] = target_col
            info["_actual_reason_col"] = reason_col
                
            used_source = "db"
        else:
            # Fallback to file - 使用用户配置的列名
            logger.info(f"[Task {task_id}] Using file source: {info['file_path']}")
            file_path = info["file_path"]
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # 从文件加载时，使用用户配置的列名
            query_col = info["query_col"]
            target_col = info["target_col"]
            reason_col = info.get("reason_col")
        
        # 公共变量（从上面的分支中获取）
        prompt = info["prompt"]
        extract_field = info.get("extract_field")
        model_config = info.get("model_config", {"base_url": "https://api.openai.com/v1", "api_key": ""})

        # 调试日志：打印 DataFrame 信息和使用的列名
        logger.info(f"[Task {task_id}] DataFrame columns: {list(df.columns)}")
        logger.info(f"[Task {task_id}] Using columns - query: '{query_col}', target: '{target_col}', reason: '{reason_col}'")
        if len(df) > 0:
            sample_row = df.iloc[0]
            logger.info(f"[Task {task_id}] Sample row[0] - query: '{sample_row.get(query_col, 'N/A')}', target: '{sample_row.get(target_col, 'N/A')}'")

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
                            
                            # 同时更新 SQLite 中的项目迭代记录，确保一致性
                            try:
                                if storage.update_latest_project_iteration_accuracy(project_id, accuracy):
                                    logger.info(f"[Task {task_id}] 已同步项目迭代记录的 accuracy_after")
                            except Exception as db_err:
                                logger.warning(f"[Task {task_id}] 同步项目迭代记录失败: {db_err}")
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
                # 返回副本并去除 heavy 字段，但保留计数信息用于前端显示准确率
                info_copy = task_info.copy()
                results = info_copy.pop("results", [])
                errors = info_copy.pop("errors", [])
                # 添加计数信息
                info_copy["results_count"] = len(results)
                info_copy["errors_count"] = len(errors)
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
        
        动态合并意图干预数据，根据最新的 target 重新计算 is_correct。
        
        :param task_id: 任务 ID
        :param page: 页码
        :param page_size: 每页数量
        :param result_type: 结果类型 'success' | 'error' | None
        :param search: 搜索关键字
        :return: 分页结果
        """
        from app.engine.helpers.verifier import Verifier
        from app.services import intervention_service

        # 1. 如果任务在内存中，从内存分页
        if task_id in self.tasks:
            info = self.tasks[task_id]["info"]
            all_results = info.get("results", [])
            project_id = info.get("project_id")
            extract_field = info.get("extract_field")
            
            # 获取意图干预数据映射
            intervention_map: Dict[str, Any] = {}
            if project_id:
                try:
                    interventions = intervention_service.get_interventions_by_project(project_id, file_id=None)
                    # 创建 query -> intervention 映射，优先使用修正过的记录
                    for intervention in interventions:
                        existing = intervention_map.get(intervention.query)
                        if existing is None:
                            intervention_map[intervention.query] = intervention
                        elif intervention.is_target_modified and not existing.is_target_modified:
                            intervention_map[intervention.query] = intervention
                except Exception as e:
                    logger.warning(f"加载意图干预数据失败: {e}")
            
            # 处理结果：合并意图干预数据并重新计算 is_correct
            processed_results: List[Dict[str, Any]] = []
            for r in all_results:
                result_dict: Dict[str, Any] = r.copy() if isinstance(r, dict) else dict(r)
                query: str = result_dict.get("query", "")
                
                # 检查是否有意图干预数据
                if query in intervention_map:
                    intervention = intervention_map[query]
                    # 使用最新的 target 和 reason
                    result_dict["target"] = intervention.target
                    result_dict["reason"] = intervention.reason or result_dict.get("reason", "")
                    
                    # 重新计算 is_correct
                    output: str = result_dict.get("output", "")
                    new_target: str = intervention.target
                    result_dict["is_correct"] = Verifier.check_match(output, new_target, extract_field)
                
                processed_results.append(result_dict)

            # 应用类型过滤
            filtered = processed_results
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

    def create_multi_round_task(
        self,
        project_id: str,
        file_path: str,
        prompt: str,
        model_config: Dict[str, Any],
        rounds_config: List[Dict[str, Any]],
        intent_extract_field: str,
        response_extract_field: str,
        original_filename: Optional[str] = None,
        validation_limit: Optional[int] = None,
        api_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        创建多轮验证任务

        新执行逻辑：
        - 同一轮的所有数据并发请求
        - 不同轮之间串行执行
        - 每轮都验证意图，每轮都有 target

        :param project_id: 项目 ID
        :param file_path: 数据文件绝对路径
        :param prompt: 提示词模板
        :param model_config: 模型配置字典
        :param rounds_config: 轮次配置列表
            格式: [{"round": 1, "query_col": "query1", "target_col": "target1"}, ...]
        :param intent_extract_field: 意图提取路径（用于验证，如 data.intent）
        :param response_extract_field: 回复内容提取路径（用于构建历史，如 data.response）
        :param original_filename: 原始文件名 (可选)
        :param validation_limit: 验证数量限制 (可选)
        :param api_config: 自定义 API 配置 (可选)，包含 api_url, api_headers, api_timeout, request_template
        :return: 任务 ID
        """
        task_id = f"task_{int(time.time())}"

        # 从文件路径提取 file_id
        file_basename = os.path.basename(file_path)
        file_id = file_basename.split("_")[0] if "_" in file_basename else file_basename.rsplit(".", 1)[0]

        # 加载数据
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # 计算数据行数
        row_count = len(df)
        if validation_limit and isinstance(validation_limit, int) and validation_limit > 0:
            row_count = min(row_count, validation_limit)

        # 获取轮数
        max_rounds = len(rounds_config)

        # 总验证次数 = 数据行数 × 轮数
        total_count = row_count * max_rounds

        task_info = {
            "id": task_id,
            "project_id": project_id,
            "file_path": file_path,
            "file_id": file_id,
            "status": "running",
            "current_index": 0,
            "total_count": total_count,
            "current_round": 1,
            "total_rounds": max_rounds,
            "row_count": row_count,
            "prompt": prompt,
            "intent_extract_field": intent_extract_field,
            "response_extract_field": response_extract_field,
            "model_config": model_config,
            "api_config": api_config,  # 新增：自定义 API 配置
            "original_filename": original_filename if original_filename is not None else "",
            "validation_limit": validation_limit,
            "multi_round_enabled": True,
            "rounds_config": rounds_config,
            "round_results": [],  # 每轮的结果汇总
            "results": [],
            "errors": []
        }

        stop_event = threading.Event()
        pause_event = threading.Event()
        pause_event.set()

        thread = threading.Thread(
            target=self._run_multi_round_task,
            args=(task_id, stop_event, pause_event)
        )

        self.tasks[task_id] = {
            "info": task_info,
            "thread": thread,
            "stop_event": stop_event,
            "pause_event": pause_event
        }

        # 立即保存初始状态
        storage.save_task_status(project_id, task_id, task_info)

        thread.start()
        logger.info(f"[Task {task_id}] 多轮验证任务已创建 | 数据行数: {row_count} | 轮数: {max_rounds} | 总验证次数: {total_count}")
        return task_id

    def _run_multi_round_task(
        self,
        task_id: str,
        stop_event: threading.Event,
        pause_event: threading.Event,
        info_override: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        多轮验证任务执行逻辑

        新执行逻辑：
        1. 同一轮的所有数据并发请求接口
        2. 等待当前轮全部完成后，再执行下一轮
        3. 每轮都验证意图（与 target 比对）
        4. 从响应中提取 assistant 回复，用于构建下一轮的历史消息

        :param task_id: 任务 ID
        :param stop_event: 停止信号
        :param pause_event: 暂停信号
        :param info_override: 任务信息覆盖（用于恢复任务）
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from app.engine.helpers.history_formatter import HistoryFormatter
        from app.engine.helpers.extractor import ResultExtractor

        task = self.tasks[task_id]
        info = info_override or task["info"]

        project_id = info["project_id"]
        file_path = info["file_path"]
        prompt = info["prompt"]
        model_config = info.get("model_config", {})
        api_config = info.get("api_config")  # 获取自定义 API 配置
        intent_extract_field = info.get("intent_extract_field", "")
        response_extract_field = info.get("response_extract_field", "")
        rounds_config = info.get("rounds_config", [])
        validation_limit = info.get("validation_limit")

        # 并发数：优先从 api_config 获取，否则从 model_config 获取
        concurrency = int((api_config or {}).get("concurrency") or model_config.get("concurrency", 1))

        # 加载数据
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # 应用验证数量限制
        if validation_limit and isinstance(validation_limit, int) and validation_limit > 0:
            df = df.head(validation_limit)

        total_rows = len(df)
        total_rounds = len(rounds_config)

        logger.info(f"[Task {task_id}] 多轮验证任务开始 | 数据行数: {total_rows} | 轮数: {total_rounds} | 并发: {concurrency}")

        # 为每行数据维护历史消息和 session_id
        # row_contexts[row_idx] = {"session_id": "...", "history": [...]}
        row_contexts: Dict[int, Dict[str, Any]] = {}
        for i in range(total_rows):
            row_contexts[i] = {
                "session_id": HistoryFormatter.generate_session_id(),
                "history": []
            }

        # 线程安全锁
        results_lock = threading.Lock()
        global_index = [info["current_index"]]

        # 逐轮执行
        for round_idx, round_cfg in enumerate(rounds_config):
            if stop_event.is_set():
                info["status"] = "stopped"
                break

            round_num = round_cfg.get("round", round_idx + 1)
            query_col = round_cfg.get("query_col", "")
            target_col = round_cfg.get("target_col", "")

            info["current_round"] = round_num
            logger.info(f"[Task {task_id}] 开始第 {round_num} 轮验证")

            # 当前轮的结果
            round_results: List[Dict[str, Any]] = []
            round_correct = 0

            def process_row_for_round(row_idx: int) -> Optional[Dict[str, Any]]:
                """处理单行数据的当前轮次"""
                if stop_event.is_set():
                    return None
                pause_event.wait()

                row_data = df.iloc[row_idx].to_dict()
                ctx = row_contexts[row_idx]
                session_id = ctx["session_id"]
                history = ctx["history"].copy()  # 复制历史，避免并发修改

                # 获取当前轮的 query 和 target
                query = ""
                target = ""

                if query_col and query_col in row_data:
                    val = row_data.get(query_col)
                    if val is not None and not pd.isna(val):
                        query = str(val).strip()

                if target_col and target_col in row_data:
                    val = row_data.get(target_col)
                    if val is not None and not pd.isna(val):
                        target = str(val).strip()

                # 跳过空 query
                if not query:
                    return None

                # 调用验证器（支持自定义 API 配置）
                result = Verifier.verify_single_with_history(
                    index=global_index[0],
                    row_index=row_idx,
                    round_number=round_num,
                    session_id=session_id,
                    query=query,
                    target=target,
                    prompt=prompt,
                    model_config=model_config,
                    history_messages=history,
                    extract_field=intent_extract_field,  # 意图提取路径
                    api_config=api_config,  # 自定义 API 配置
                    response_extract_path=response_extract_field  # 回复内容提取路径
                )

                # 从结果中获取提取的回复和意图（如果使用自定义 API，Verifier 已经提取）
                raw_output = result.get("output", "")
                extracted_response = result.get("extracted_response", "")
                extracted_intent = result.get("extracted_intent", "")

                # 如果没有使用自定义 API，需要手动提取
                if not api_config or not api_config.get("api_url"):
                    try:
                        # 提取意图
                        extracted_intent = ResultExtractor.extract(raw_output, intent_extract_field)
                        if extracted_intent is None:
                            extracted_intent = ""
                        elif isinstance(extracted_intent, dict):
                            extracted_intent = str(extracted_intent)
                        else:
                            extracted_intent = str(extracted_intent)

                        # 提取回复内容
                        extracted_response = ResultExtractor.extract(raw_output, response_extract_field)
                        if extracted_response is None:
                            extracted_response = ""
                        elif isinstance(extracted_response, dict):
                            extracted_response = json.dumps(extracted_response, ensure_ascii=False)
                        else:
                            extracted_response = str(extracted_response)
                    except Exception as e:
                        logger.warning(f"[Task {task_id}] Row {row_idx} Round {round_num}: 提取失败 - {e}")

                # 添加提取结果到 result
                result["extracted_intent"] = extracted_intent
                if extracted_response:
                    result["extracted_response"] = extracted_response

                return result

            # 并发处理当前轮的所有数据行
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = {executor.submit(process_row_for_round, i): i for i in range(total_rows)}

                for future in as_completed(futures):
                    if stop_event.is_set():
                        info["status"] = "stopped"
                        executor.shutdown(wait=False)
                        break

                    row_idx = futures[future]
                    result = future.result()

                    if result:
                        with results_lock:
                            # 更新全局索引
                            global_index[0] += 1
                            info["current_index"] = global_index[0]

                            # 添加到结果
                            info["results"].append(result)
                            round_results.append(result)

                            if result["is_correct"]:
                                round_correct += 1
                            else:
                                info["errors"].append(result)

                            # 更新该行的历史消息（用于下一轮）
                            query = result.get("query", "")
                            extracted_response = result.get("extracted_response", "")

                            if query:
                                row_contexts[row_idx]["history"].append({
                                    "role": "user",
                                    "content": query
                                })
                            if extracted_response:
                                row_contexts[row_idx]["history"].append({
                                    "role": "assistant",
                                    "content": extracted_response
                                })

                            # 定期保存
                            if global_index[0] % 10 == 0:
                                logger.info(f"[Task {task_id}] 进度: {global_index[0]}/{info['total_count']} (第 {round_num} 轮)")
                                storage.save_task_status(project_id, task_id, info)

            # 当前轮完成，计算准确率并保存
            round_total = len(round_results)
            round_accuracy = (round_correct / round_total * 100) if round_total > 0 else 0

            # 只保存错误的结果，减少数据量
            round_errors = [r for r in round_results if not r.get("is_correct", True)]

            round_summary = {
                "round": round_num,
                "total": round_total,
                "correct": round_correct,
                "accuracy": round_accuracy,
                "results": round_errors  # 只保存错误结果
            }
            info["round_results"].append(round_summary)

            logger.info(f"[Task {task_id}] 第 {round_num} 轮完成 | 准确率: {round_accuracy:.1f}% ({round_correct}/{round_total})")
            storage.save_task_status(project_id, task_id, info)

        # 任务完成
        if info["current_index"] >= info["total_count"]:
            info["status"] = "completed"
            logger.info(f"[Task {task_id}] 多轮验证任务完成")

        storage.save_task_status(project_id, task_id, info)
