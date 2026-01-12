import logging
import threading
import time
import json
import os
import pandas as pd
from typing import Dict, Any, Optional
import storage
from openai import OpenAI

# 模拟或真实的 LLM 调用
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-xxx"))
BASE_URL = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
client.base_url = BASE_URL

class TaskManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TaskManager, cls).__new__(cls)
                    cls._instance.tasks = {} # task_id -> {status, thread, stop_event, pause_event}
        return cls._instance

    def create_task(self, project_id: str, file_path: str, query_col: str, target_col: str, prompt: str, model_config: Dict[str, str], extract_field: Optional[str] = None):
        task_id = f"task_{int(time.time())}"
        
        # 加载数据以校验
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
            
        task_info = {
            "id": task_id,
            "project_id": project_id,
            "file_path": file_path, # 保存文件路径
            "status": "running",
            "current_index": 0,
            "total_count": len(df),
            "query_col": query_col,
            "target_col": target_col,
            "prompt": prompt,
            "extract_field": extract_field, # 保存需要提取的字段名
            "model_config": model_config,   # 保存模型配置
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
        
        thread.start()
        return task_id

    def _run_task(self, task_id, stop_event, pause_event, info_override=None):
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        task = self.tasks[task_id]
        info = info_override or task["info"]
        
        # 加载数据
        file_path = info["file_path"]
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)
        
        query_col = info["query_col"]
        target_col = info["target_col"]
        prompt = info["prompt"]
        extract_field = info.get("extract_field")
        model_config = info.get("model_config", {"base_url": "https://api.openai.com/v1", "api_key": ""})
        concurrency = int(model_config.get("concurrency", 1))

        # 初始化 client
        logging.info(f"[Task {task_id}] Starting with BaseURL: {model_config.get('base_url')} | Model: {model_config.get('model_name')} | Concurrency: {concurrency}")
        task_client = OpenAI(api_key=model_config["api_key"], base_url=model_config["base_url"])
        
        # 线程安全锁
        results_lock = threading.Lock()
        index_lock = threading.Lock()
        
        def process_single_query(i):
            """处理单个查询"""
            if stop_event.is_set():
                return None
            pause_event.wait()
            
            query = str(df.iloc[i][query_col])
            target = str(df.iloc[i][target_col])
            
            try:
                response = task_client.chat.completions.create(
                    model=model_config.get("model_name", "gpt-3.5-turbo"),
                    messages=[
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": query}
                    ],
                    temperature=float(model_config.get("temperature", 0)),
                    max_tokens=int(model_config.get("max_tokens", 2000)),
                    timeout=int(model_config.get("timeout", 60))
                )
                output = response.choices[0].message.content
                
                return {
                    "index": i,
                    "query": query,
                    "target": target,
                    "output": output,
                    "is_correct": self._check_match(output, target, extract_field)
                }
            except Exception as e:
                logging.error(f"[Task {task_id}] Error ind={i} URL={model_config.get('base_url')}: {str(e)}")
                return {
                    "index": i,
                    "query": query,
                    "target": target,
                    "output": f"ERROR: {str(e)}",
                    "is_correct": False
                }
        
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
                    executor.shutdown(wait=False, cancel_futures=True)
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
                            logging.info(f"[Task {task_id}] Progress: {completed_count}/{total}")
                        
                        # 每10条保存一次状态
                        if completed_count % 10 == 0:
                            storage.save_task_status(info["project_id"], task_id, info)
        
        if info["current_index"] == info["total_count"]:
            info["status"] = "completed"
        
        storage.save_task_status(info["project_id"], task_id, info)

    def _check_match(self, output: str, target: str, extract_field: Optional[str] = None) -> bool:
        output = output.strip().lower()
        target = target.strip().lower()
        
        # 尝试提取 JSON
        try:
            if "{" in output and "}" in output:
                json_str = output[output.find("{"):output.rfind("}")+1]
                data = json.loads(json_str)
                
                # 如果指定了提取字段
                if extract_field:
                    # 支持 Python 表达式 extraction (以 py: 开头)
                    if extract_field.startswith("py:"):
                        expression = extract_field[3:].strip()
                        try:
                            # 允许在表达式中使用 data 变量
                            # 注意：eval 有安全风险，但在内部工具场景下通常可接受
                            val = eval(expression, {"__builtins__": None}, {"data": data})
                            
                            # 如果表达式返回 True (比如也可以直接由表达式做判断)
                            if isinstance(val, bool):
                                return val
                                
                            return str(val).lower() == target
                        except Exception as e:
                            logging.warning(f"Expression eval failed: {e}")
                            return False

                    if extract_field in data:
                       val = str(data[extract_field]).lower()
                       return val == target
                
                # 未指定字段，遍历所有值
                for val in data.values():
                    if str(val).lower() == target:
                        return True
        except:
            pass

        if target == output:
            return True
            
        return target in output

    def pause_task(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id]["pause_event"].clear()
            self.tasks[task_id]["info"]["status"] = "paused"
            return True
        return False

    def resume_task(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id]["pause_event"].set()
            self.tasks[task_id]["info"]["status"] = "running"
            return True
        else:
            # 尝试从磁盘加载并启动
            info = storage.get_task_status(task_id)
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

    def stop_task(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id]["stop_event"].set()
            self.tasks[task_id]["pause_event"].set() # 确保不被卡在暂停
            self.tasks[task_id]["info"]["status"] = "stopped"
            return True
        else:
            # 尝试从磁盘加载并标记为stopped
            info = storage.get_task_status(task_id)
            if info:
                info["status"] = "stopped"
                storage.save_task_status(info.get("project_id", ""), task_id, info)
                return True
        return False

    def get_task_status(self, task_id: str):
        # 优先从内存拿实时数据，拿不到去文件拿
        if task_id in self.tasks:
            return self.tasks[task_id]["info"]
        return storage.get_task_status(task_id)
