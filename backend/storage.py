import os
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")

def init_storage():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

def get_projects() -> List[Dict[str, Any]]:
    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_projects(projects: List[Dict[str, Any]]):
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, indent=2, ensure_ascii=False)

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

def save_task_status(project_id: str, task_id: str, status: Dict[str, Any]):
    task_file = os.path.join(DATA_DIR, f"task_{task_id}.json")
    with open(task_file, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    task_file = os.path.join(DATA_DIR, f"task_{task_id}.json")
    if os.path.exists(task_file):
        with open(task_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

MODEL_CONFIG_FILE = os.path.join(DATA_DIR, "model_config.json")

def get_model_config() -> Dict[str, str]:
    if os.path.exists(MODEL_CONFIG_FILE):
        with open(MODEL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "base_url": "https://api.openai.com/v1", 
        "api_key": "",
        "max_tokens": 2000,
        "timeout": 60,
        "model_name": "gpt-3.5-turbo",
        "temperature": 0.0
    }

def save_model_config(config: Dict[str, str]):
    with open(MODEL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

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
    """获取项目关联的所有任务"""
    tasks = []
    for filename in os.listdir(DATA_DIR):
        if filename.startswith("task_") and filename.endswith(".json"):
            task_path = os.path.join(DATA_DIR, filename)
            with open(task_path, "r", encoding="utf-8") as f:
                task_data = json.load(f)
                if task_data.get("project_id") == project_id:
                    # 返回简化的任务信息用于列表展示
                    tasks.append({
                        "id": task_data.get("id"),
                        "status": task_data.get("status"),
                        "current_index": task_data.get("current_index"),
                        "total_count": task_data.get("total_count"),
                        "results_count": len(task_data.get("results", [])),
                        "errors_count": len(task_data.get("errors", []))
                    })
    # 按任务ID排序（最新的在前）
    tasks.sort(key=lambda x: x["id"], reverse=True)
    return tasks

def save_auto_iterate_status(project_id: str, status: Dict[str, Any]):
    file_path = os.path.join(DATA_DIR, f"auto_iterate_{project_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)

def get_auto_iterate_status(project_id: str) -> Optional[Dict[str, Any]]:
    file_path = os.path.join(DATA_DIR, f"auto_iterate_{project_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return None
    return None
