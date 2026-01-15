import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime
import tempfile
import shutil
from loguru import logger

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")

def init_storage():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(PROJECTS_FILE):
        _atomic_save_json(PROJECTS_FILE, [])

def _atomic_save_json(file_path: str, data: Any):
    """
    Atomically save JSON data to a file using a temporary file.
    This prevents data corruption (e.g. 'Extra data') if the process crashes or concurrent writes happen.
    """
    dir_name = os.path.dirname(file_path)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    
    # Create temp file
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, dir=dir_name, encoding="utf-8", suffix=".tmp") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=False)
            temp_path = tmp.name
        
        # Atomically replace
        os.replace(temp_path, file_path)
    except Exception as e:
        logger.error(f"Failed to save JSON to {file_path}: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def _safe_load_json(file_path: str) -> Any:
    """
    Safely load JSON from file, identifying and recovering from 'Extra data' corruption.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            logger.warning(f"Detected corrupted JSON in {file_path} (Extra data). Attempting recovery.")
            try:
                # Attempt to recover by taking the valid part up to the extra data
                recovered_data = json.loads(content[:e.pos])
                logger.info(f"Successfully recovered JSON data from {file_path}")
                
                # Optionally auto-fix the file on disk? 
                # Better to just return valid data for now, the next save will fix it.
                return recovered_data
            except Exception as recovery_error:
                logger.error(f"Failed to recover JSON from {file_path}: {recovery_error}")
                raise e
        else:
            logger.error(f"JSON decode error in {file_path}: {e}")
            raise e

def get_projects() -> List[Dict[str, Any]]:
    return _safe_load_json(PROJECTS_FILE)

def save_projects(projects: List[Dict[str, Any]]):
    _atomic_save_json(PROJECTS_FILE, projects)

def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    projects = get_projects()
    for p in projects:
        if p["id"] == project_id:
            return p
    return None

def create_project(name: str, prompt: str) -> Dict[str, Any]:
    projects = get_projects()
    new_project = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "name": name,
        "current_prompt": prompt,
        "iterations": [],
        "model_config": {}, # 初始化为空配置
        "created_at": datetime.now().isoformat()
    }
    projects.append(new_project)
    save_projects(projects)
    return new_project

def delete_project(project_id: str) -> bool:
    """删除项目"""
    projects = get_projects()
    initial_len = len(projects)
    projects = [p for p in projects if p["id"] != project_id]
    
    if len(projects) < initial_len:
        save_projects(projects)
        return True
    return False

def save_task_status(project_id: str, task_id: str, status: Dict[str, Any]):
    task_file = os.path.join(DATA_DIR, f"task_{task_id}.json")
    _atomic_save_json(task_file, status)

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    task_file = os.path.join(DATA_DIR, f"task_{task_id}.json")
    if os.path.exists(task_file):
        return _safe_load_json(task_file)
    return None

MODEL_CONFIG_FILE = os.path.join(DATA_DIR, "model_config.json")

def get_model_config() -> Dict[str, str]:
    if os.path.exists(MODEL_CONFIG_FILE):
        return _safe_load_json(MODEL_CONFIG_FILE)
    return {
        "base_url": "https://api.openai.com/v1", 
        "api_key": "",
        "max_tokens": 2000,
        "timeout": 60,
        "model_name": "gpt-3.5-turbo",
        "temperature": 0.0
    }

def save_model_config(config: Dict[str, str]):
    _atomic_save_json(MODEL_CONFIG_FILE, config)

def update_project(project_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新项目信息"""
    projects = get_projects()
    for idx, p in enumerate(projects):
        if p["id"] == project_id:
            # 更新允许的字段
            if "name" in updates:
                p["name"] = updates["name"]
            if "current_prompt" in updates:
                p["current_prompt"] = updates["current_prompt"]
            if "last_task_id" in updates:
                p["last_task_id"] = updates["last_task_id"]
            if "config" in updates:
                p["config"] = updates["config"]
            if "iterations" in updates:
                p["iterations"] = updates["iterations"]
            if "model_config" in updates:
                p["model_config"] = updates["model_config"]
            if "optimization_model_config" in updates:
                p["optimization_model_config"] = updates["optimization_model_config"]
            if "optimization_prompt" in updates:
                p["optimization_prompt"] = updates["optimization_prompt"]
            p["updated_at"] = datetime.now().isoformat()
            projects[idx] = p
            save_projects(projects)
            return p
    return None

def get_project_tasks(project_id: str) -> List[Dict[str, Any]]:
    """获取项目关联的所有任务（完整的运行历史）"""
    tasks = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("task_") and filename.endswith(".json"):
            task_path = os.path.join(DATA_DIR, filename)
            try:
                task_data = _safe_load_json(task_path)
            except Exception as e:
                logger.error(f"Error loading task file {filename}: {e}")
                continue
                
            if task_data.get("project_id") == project_id:
                    # 从文件路径提取数据集名称
                    file_path = task_data.get("file_path", "")
                    original_filename = task_data.get("original_filename")
                    dataset_name = original_filename if original_filename else (os.path.basename(file_path) if file_path else "未知")
                    
                    # 计算准确率
                    results = task_data.get("results", [])
                    errors = task_data.get("errors", [])
                    accuracy = (len(results) - len(errors)) / len(results) if results else 0
                    
                    # 从任务ID提取时间戳 (格式: task_1234567890)
                    task_id = task_data.get("id", "")
                    timestamp = task_id.replace("task_", "") if task_id.startswith("task_") else ""
                    
                    tasks.append({
                        "id": task_id,
                        "status": task_data.get("status"),
                        "current_index": task_data.get("current_index", 0),
                        "total_count": task_data.get("total_count", 0),
                        "results_count": len(results),
                        "errors_count": len(errors),
                        "accuracy": accuracy,
                        "prompt": task_data.get("prompt", ""),
                        "dataset_name": dataset_name,
                        "created_at": timestamp,
                        "note": task_data.get("note", "")
                    })
    # 按任务ID排序（最新的在前）
    tasks.sort(key=lambda x: x["id"], reverse=True)
    return tasks

def save_auto_iterate_status(project_id: str, status: Dict[str, Any]):
    file_path = os.path.join(DATA_DIR, f"auto_iterate_{project_id}.json")
    _atomic_save_json(file_path, status)

def get_auto_iterate_status(project_id: str) -> Optional[Dict[str, Any]]:
    file_path = os.path.join(DATA_DIR, f"auto_iterate_{project_id}.json")
    if os.path.exists(file_path):
        try:
            return _safe_load_json(file_path)
        except:
            return None
    return None


def get_all_project_errors(project_id: str) -> List[Dict[str, Any]]:
    """
    获取项目所有历史任务中的错误案例
    :param project_id: 项目ID
    :return: 错误案例列表（包含 query, target, output 等信息）
    """
    if not project_id:
        return []
        
    all_errors = []
    
    # 遍历所有任务文件
    if not os.path.exists(DATA_DIR):
        return []
        
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("task_") and filename.endswith(".json"):
            try:
                task_path = os.path.join(DATA_DIR, filename)
                task_data = _safe_load_json(task_path)
                    
                # 检查是否属于该项目
                if task_data.get("project_id") == project_id:
                    # 提取错误案例
                    errors = task_data.get("errors", [])
                    if errors:
                        all_errors.extend(errors)
            except Exception as e:
                logger.error(f"Error reading task file {filename}: {e}")
                continue
                
    return all_errors


# 公共模型配置文件路径
GLOBAL_MODELS_FILE: str = os.path.join(DATA_DIR, "global_models.json")


def get_global_models() -> List[Dict[str, Any]]:
    """
    获取所有公共模型配置
    @return: 公共模型配置列表
    """
    if os.path.exists(GLOBAL_MODELS_FILE):
        return _safe_load_json(GLOBAL_MODELS_FILE)
    return []


def _save_global_models(models: List[Dict[str, Any]]) -> None:
    """
    保存公共模型配置列表到文件
    @param models: 公共模型配置列表
    """
    _atomic_save_json(GLOBAL_MODELS_FILE, models)



def delete_task(task_id: str) -> bool:
    """
    删除任务及相关文件
    :param task_id: 任务ID
    :return: 是否成功
    """
    success = False
    # 删除任务文件
    task_file = os.path.join(DATA_DIR, f"task_{task_id}.json")
    if os.path.exists(task_file):
        try:
            os.remove(task_file)
            success = True
        except Exception as e:
            logger.error(f"Error deleting task file {task_file}: {e}")
            
    # 删除结果文件 (可能有多个，包括带进度的)
    # results_{task_id}.xlsx 或 results_{task_id}_*.xlsx
    for f in os.listdir(DATA_DIR):
        if f.startswith(f"results_{task_id}") and f.endswith(".xlsx"):
            try:
                os.remove(os.path.join(DATA_DIR, f))
            except Exception as e:
                logger.error(f"Error deleting result file {f}: {e}")
                
    return success

def delete_project_iteration(project_id: str, timestamp: str) -> bool:
    """
    删除项目迭代记录
    :param project_id: 项目ID
    :param timestamp: 迭代创建时间 (created_at) 用于匹配
    :return: 是否成功
    """
    projects = get_projects()
    for i, p in enumerate(projects):
        if p["id"] == project_id:
            iterations = p.get("iterations", [])
            initial_len = len(iterations)
            # 过滤掉匹配的迭代
            p["iterations"] = [it for it in iterations if it.get("created_at") != timestamp]
            
            if len(p["iterations"]) < initial_len:
                p["updated_at"] = datetime.now().isoformat()
                projects[i] = p
                save_projects(projects)
                return True
    return False

def create_global_model(model_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    创建新的公共模型配置
    @param model_data: 模型配置数据
    @return: 创建的模型配置（包含生成的ID）
    """
    models: List[Dict[str, Any]] = get_global_models()
    
    # 生成唯一ID
    new_model: Dict[str, Any] = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "name": model_data.get("name", "未命名模型"),
        "base_url": model_data.get("base_url", ""),
        "api_key": model_data.get("api_key", ""),
        "model_name": model_data.get("model_name", "gpt-3.5-turbo"),
        "max_tokens": model_data.get("max_tokens", 2000),
        "temperature": model_data.get("temperature", 0.0),
        "timeout": model_data.get("timeout", 60),
        "concurrency": model_data.get("concurrency", 5),
        "extra_body": model_data.get("extra_body", None),
        "default_headers": model_data.get("default_headers", None),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    models.append(new_model)
    _save_global_models(models)
    return new_model


def update_task_note(task_id: str, note: str) -> bool:
    """
    更新任务备注
    :param task_id: 任务ID
    :param note: 备注内容
    :return: 是否成功
    """
    task_status = get_task_status(task_id)
    if task_status:
        task_status["note"] = note
        save_task_status(task_status.get("project_id", ""), task_id, task_status)
        return True
    return False


def update_project_iteration_note(project_id: str, timestamp: str, note: str) -> bool:
    """
    更新项目迭代记录备注
    :param project_id: 项目ID
    :param timestamp: 迭代创建时间 (created_at) 用于匹配
    :param note: 备注内容
    :return: 是否成功
    """
    projects = get_projects()
    for i, p in enumerate(projects):
        if p["id"] == project_id:
            iterations = p.get("iterations", [])
            updated = False
            for it in iterations:
                if it.get("created_at") == timestamp:
                    it["note"] = note
                    updated = True
                    break
            
            if updated:
                p["updated_at"] = datetime.now().isoformat()
                projects[i] = p
                save_projects(projects)
                return True
    return False


def update_global_model(model_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    更新公共模型配置
    @param model_id: 模型配置ID
    @param updates: 要更新的字段
    @return: 更新后的模型配置，如果未找到则返回None
    """
    models: List[Dict[str, Any]] = get_global_models()
    
    for idx, model in enumerate(models):
        if model["id"] == model_id:
            # 更新允许的字段
            allowed_fields: List[str] = [
                "name", "base_url", "api_key", "model_name", 
                "max_tokens", "temperature", "timeout", "concurrency",
                "extra_body", "default_headers"
            ]
            for field in allowed_fields:
                if field in updates:
                    model[field] = updates[field]
            model["updated_at"] = datetime.now().isoformat()
            models[idx] = model
            _save_global_models(models)
            return model
    
    return None


def delete_global_model(model_id: str) -> bool:
    """
    删除公共模型配置
    @param model_id: 模型配置ID
    @return: 是否删除成功
    """
    models: List[Dict[str, Any]] = get_global_models()
    initial_len: int = len(models)
    models = [m for m in models if m["id"] != model_id]
    
    if len(models) < initial_len:
        _save_global_models(models)
        return True
    return False


def get_global_model(model_id: str) -> Optional[Dict[str, Any]]:
    """
    根据ID获取单个公共模型配置
    @param model_id: 模型配置ID
    @return: 模型配置，如果未找到则返回None
    """
    models: List[Dict[str, Any]] = get_global_models()
    for model in models:
        if model["id"] == model_id:
            return model
    return None
