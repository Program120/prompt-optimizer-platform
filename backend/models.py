"""
SQLModel 数据模型定义
定义所有数据库表结构
"""
from datetime import datetime
from typing import Optional, List, Any, Dict
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON, Text
import json


class ProjectIteration(SQLModel, table=True):
    """
    项目迭代记录表
    记录每次优化迭代的详情
    """
    __tablename__ = "project_iterations"
    
    # 主键 ID
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 外键：关联项目
    project_id: str = Field(foreign_key="projects.id", index=True)
    
    # 迭代版本
    version: int = Field(default=1)
    
    # 优化前的提示词
    previous_prompt: str = Field(default="", sa_column=Column(Text))
    
    # 优化后的提示词
    optimized_prompt: str = Field(default="", sa_column=Column(Text))
    
    # 使用的策略
    strategy: str = Field(default="")
    
    # 优化前准确率
    accuracy_before: float = Field(default=0.0)
    
    # 优化后准确率
    accuracy_after: Optional[float] = Field(default=None)
    
    # 关联的任务 ID
    task_id: Optional[str] = Field(default=None)
    
    # 分析内容（JSON 格式存储）
    analysis: str = Field(default="{}", sa_column=Column(Text))
    
    # 备注
    note: str = Field(default="")
    
    # 创建时间
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 关联的项目对象
    project: Optional["Project"] = Relationship(back_populates="iterations")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容旧 API）
        """
        result: Dict[str, Any] = {
            "version": self.version,
            "previous_prompt": self.previous_prompt,
            "optimized_prompt": self.optimized_prompt,
            "strategy": self.strategy,
            "accuracy_before": self.accuracy_before,
            "accuracy_after": self.accuracy_after,
            "task_id": self.task_id,
            "note": self.note,
            "created_at": self.created_at,
        }
        
        # 解析 analysis JSON
        try:
            result["analysis"] = json.loads(self.analysis) if self.analysis else {}
        except json.JSONDecodeError:
            result["analysis"] = {}
            
        return result


class Project(SQLModel, table=True):
    """
    项目表
    存储优化项目的核心信息
    """
    __tablename__ = "projects"
    
    # 项目 ID（时间戳格式）
    id: str = Field(primary_key=True)
    
    # 项目名称
    name: str = Field(default="")
    
    # 当前提示词
    current_prompt: str = Field(default="", sa_column=Column(Text))
    
    # 最后一次任务 ID
    last_task_id: Optional[str] = Field(default=None)
    
    # 项目配置（JSON 格式）
    config: str = Field(default="{}", sa_column=Column(Text))
    
    # 模型配置（JSON 格式）
    model_config_data: str = Field(default="{}", sa_column=Column(Text))
    
    # 优化模型配置（JSON 格式）
    optimization_model_config: str = Field(default="{}", sa_column=Column(Text))
    
    # 优化提示词
    optimization_prompt: str = Field(default="", sa_column=Column(Text))
    
    # 创建时间
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 更新时间
    updated_at: Optional[str] = Field(default=None)
    
    # 关联的迭代记录
    iterations: List[ProjectIteration] = Relationship(back_populates="project")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容旧 API）
        """
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "current_prompt": self.current_prompt,
            "last_task_id": self.last_task_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        
        # 解析 JSON 字段
        try:
            result["config"] = json.loads(self.config) if self.config else {}
        except json.JSONDecodeError:
            result["config"] = {}
            
        try:
            result["model_config"] = json.loads(self.model_config_data) if self.model_config_data else {}
        except json.JSONDecodeError:
            result["model_config"] = {}
            
        try:
            result["optimization_model_config"] = json.loads(self.optimization_model_config) if self.optimization_model_config else {}
        except json.JSONDecodeError:
            result["optimization_model_config"] = {}
            
        result["optimization_prompt"] = self.optimization_prompt
        
        # 添加迭代记录
        result["iterations"] = [it.to_dict() for it in self.iterations] if self.iterations else []
        
        return result


class TaskResult(SQLModel, table=True):
    """
    任务执行结果表
    存储每条数据的执行结果
    """
    __tablename__ = "task_results"
    
    # 主键 ID
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 外键：关联任务
    task_id: str = Field(foreign_key="tasks.id", index=True)
    
    # 查询内容
    query: str = Field(default="", sa_column=Column(Text))
    
    # 预期输出
    target: str = Field(default="", sa_column=Column(Text))
    
    # 实际输出
    output: str = Field(default="", sa_column=Column(Text))
    
    # 是否正确
    is_correct: bool = Field(default=False)
    
    # 原因说明
    reason: str = Field(default="", sa_column=Column(Text))
    
    # 其他数据（JSON 格式）
    extra_data: str = Field(default="{}", sa_column=Column(Text))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {
            "query": self.query,
            "target": self.target,
            "output": self.output,
            "is_correct": self.is_correct,
            "reason": self.reason,
        }
        try:
            extra: Dict[str, Any] = json.loads(self.extra_data) if self.extra_data else {}
            result.update(extra)
        except json.JSONDecodeError:
            pass
        return result


class TaskError(SQLModel, table=True):
    """
    任务错误记录表
    存储执行失败的记录
    """
    __tablename__ = "task_errors"
    
    # 主键 ID
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 外键：关联任务
    task_id: str = Field(foreign_key="tasks.id", index=True)
    
    # 查询内容
    query: str = Field(default="", sa_column=Column(Text))
    
    # 预期输出
    target: str = Field(default="", sa_column=Column(Text))
    
    # 实际输出
    output: str = Field(default="", sa_column=Column(Text))
    
    # 错误原因
    reason: str = Field(default="", sa_column=Column(Text))
    
    # 其他数据（JSON 格式）
    extra_data: str = Field(default="{}", sa_column=Column(Text))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {
            "query": self.query,
            "target": self.target,
            "output": self.output,
            "reason": self.reason,
        }
        try:
            extra: Dict[str, Any] = json.loads(self.extra_data) if self.extra_data else {}
            result.update(extra)
        except json.JSONDecodeError:
            pass
        return result


class Task(SQLModel, table=True):
    """
    任务表
    存储执行任务的状态和结果
    """
    __tablename__ = "tasks"
    
    # 任务 ID
    id: str = Field(primary_key=True)
    
    # 关联项目 ID
    project_id: str = Field(index=True)
    
    # 任务状态
    status: str = Field(default="pending")
    
    # 当前处理索引
    current_index: int = Field(default=0)
    
    # 总数据量
    total_count: int = Field(default=0)
    
    # 使用的提示词
    prompt: str = Field(default="", sa_column=Column(Text))
    
    # 数据文件路径
    file_path: str = Field(default="")
    
    # 原始文件名
    original_filename: str = Field(default="")
    
    # 备注
    note: str = Field(default="")
    
    # 创建时间
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 其他配置数据（JSON 格式）
    extra_config: str = Field(default="{}", sa_column=Column(Text))
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（兼容旧 API）"""
        from database import get_db_session
        from sqlmodel import select
        
        result: Dict[str, Any] = {
            "id": self.id,
            "project_id": self.project_id,
            "status": self.status,
            "current_index": self.current_index,
            "total_count": self.total_count,
            "prompt": self.prompt,
            "file_path": self.file_path,
            "original_filename": self.original_filename,
            "note": self.note,
            "created_at": self.created_at,
        }
        
        # 解析额外配置
        try:
            extra: Dict[str, Any] = json.loads(self.extra_config) if self.extra_config else {}
            result.update(extra)
        except json.JSONDecodeError:
            pass
        
        # 加载结果和错误（延迟加载）
        with get_db_session() as session:
            results_stmt = select(TaskResult).where(TaskResult.task_id == self.id)
            results: List[TaskResult] = list(session.exec(results_stmt))
            result["results"] = [r.to_dict() for r in results]
            
            errors_stmt = select(TaskError).where(TaskError.task_id == self.id)
            errors: List[TaskError] = list(session.exec(errors_stmt))
            result["errors"] = [e.to_dict() for e in errors]
        
        return result


class GlobalModel(SQLModel, table=True):
    """
    公共模型配置表
    存储可复用的 LLM 模型配置
    """
    __tablename__ = "global_models"
    
    # 模型配置 ID
    id: str = Field(primary_key=True)
    
    # 配置名称
    name: str = Field(default="未命名模型")
    
    # API 基础 URL
    base_url: str = Field(default="")
    
    # API 密钥
    api_key: str = Field(default="")
    
    # 模型名称
    model_name: str = Field(default="gpt-3.5-turbo")
    
    # 最大 Token 数
    max_tokens: int = Field(default=2000)
    
    # 温度参数
    temperature: float = Field(default=0.0)
    
    # 超时时间（秒）
    timeout: int = Field(default=60)
    
    # 并发数
    concurrency: int = Field(default=5)
    
    # 额外请求体（JSON 格式）
    extra_body: str = Field(default="", sa_column=Column(Text))
    
    # 默认请求头（JSON 格式）
    default_headers: str = Field(default="", sa_column=Column(Text))
    
    # 创建时间
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # 更新时间
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "concurrency": self.concurrency,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        
        # 解析 JSON 字段
        try:
            result["extra_body"] = json.loads(self.extra_body) if self.extra_body else None
        except json.JSONDecodeError:
            result["extra_body"] = None
            
        try:
            result["default_headers"] = json.loads(self.default_headers) if self.default_headers else None
        except json.JSONDecodeError:
            result["default_headers"] = None
            
        return result


class ModelConfig(SQLModel, table=True):
    """
    系统模型配置表（单例）
    存储系统默认的模型配置
    """
    __tablename__ = "model_config"
    
    # 固定 ID（单例模式）
    id: int = Field(default=1, primary_key=True)
    
    # API 基础 URL
    base_url: str = Field(default="https://api.openai.com/v1")
    
    # API 密钥
    api_key: str = Field(default="")
    
    # 最大 Token 数
    max_tokens: int = Field(default=2000)
    
    # 超时时间（秒）
    timeout: int = Field(default=60)
    
    # 模型名称
    model_name: str = Field(default="gpt-3.5-turbo")
    
    # 温度参数
    temperature: float = Field(default=0.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "base_url": self.base_url,
            "api_key": self.api_key,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "model_name": self.model_name,
            "temperature": self.temperature,
        }


class AutoIterateStatus(SQLModel, table=True):
    """
    自动迭代状态表
    存储自动迭代优化的运行状态
    """
    __tablename__ = "auto_iterate_status"
    
    # 项目 ID（作为主键）
    project_id: str = Field(primary_key=True)
    
    # 运行状态
    status: str = Field(default="idle")
    
    # 当前轮次
    current_round: int = Field(default=0)
    
    # 最大轮次
    max_rounds: int = Field(default=5)
    
    # 目标准确率
    target_accuracy: float = Field(default=95.0)
    
    # 当前准确率
    current_accuracy: float = Field(default=0.0)
    
    # 错误信息
    error_message: str = Field(default="")
    
    # 额外数据（JSON 格式）
    extra_data: str = Field(default="{}", sa_column=Column(Text))
    
    # 更新时间
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result: Dict[str, Any] = {
            "project_id": self.project_id,
            "status": self.status,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "target_accuracy": self.target_accuracy,
            "current_accuracy": self.current_accuracy,
            "error_message": self.error_message,
            "updated_at": self.updated_at,
        }
        
        # 解析额外数据
        try:
            extra: Dict[str, Any] = json.loads(self.extra_data) if self.extra_data else {}
            result.update(extra)
        except json.JSONDecodeError:
            pass
            
        return result
