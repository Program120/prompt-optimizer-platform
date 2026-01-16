"""
优化引擎数据模型

提供类型安全的数据结构定义，用于优化流程中的数据传递
"""
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field


class OverallMetrics(BaseModel):
    """整体性能指标"""
    accuracy: float = 0.0
    error_count: int = 0
    total_count: int = 0


class ErrorPatterns(BaseModel):
    """错误模式分析结果"""
    confusion_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    category_distribution: Dict[str, int] = Field(default_factory=dict)
    hard_cases: List[Dict[str, Any]] = Field(default_factory=list)


class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    total_errors: int = 0
    top_failing_intents: List[Dict[str, Any]] = Field(default_factory=list)
    clarification_intents: List[str] = Field(default_factory=list)
    multi_intent_intents: List[str] = Field(default_factory=list)


class DeepAnalysisResult(BaseModel):
    """深度分析结果"""
    analyzed_count: int = 0
    analyses: List[Dict[str, Any]] = Field(default_factory=list)


class AdvancedDiagnosisResult(BaseModel):
    """高级诊断结果"""
    context_analysis: Dict[str, Any] = Field(default_factory=dict)
    multi_intent_analysis: Dict[str, Any] = Field(default_factory=dict)
    domain_analysis: Dict[str, Any] = Field(default_factory=dict)
    clarification_analysis: Dict[str, Any] = Field(default_factory=dict)


class DiagnosisResult(BaseModel):
    """
    诊断结果数据模型
    
    包含所有诊断阶段的结果
    """
    overall_metrics: OverallMetrics = Field(default_factory=OverallMetrics)
    error_patterns: ErrorPatterns = Field(default_factory=ErrorPatterns)
    intent_analysis: Optional[IntentAnalysisResult] = None
    deep_analysis: Optional[DeepAnalysisResult] = None
    advanced_diagnosis: Optional[AdvancedDiagnosisResult] = None
    
    # 额外字段
    main_errors: List[Dict[str, Any]] = Field(default_factory=list)
    low_priority_clarification_errors: List[Dict[str, Any]] = Field(default_factory=list)
    optimized_intents: List[str] = Field(default_factory=list)
    optimization_history: Optional[Dict[str, Any]] = None
    optimization_history_text: Optional[str] = None
    newly_failed_cases: Optional[List[Dict[str, Any]]] = None
    persistent_error_samples: List[Dict[str, Any]] = Field(default_factory=list)
    
    class Config:
        """Pydantic 配置"""
        extra = "allow"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        保持与旧代码的兼容性
        
        :return: 字典格式的诊断结果
        """
        result = self.model_dump(exclude_none=True)
        
        # 确保嵌套对象也转换为字典
        if self.overall_metrics:
            result["overall_metrics"] = self.overall_metrics.model_dump()
        if self.error_patterns:
            result["error_patterns"] = self.error_patterns.model_dump()
        
        return result


class CandidateResult(BaseModel):
    """候选方案结果"""
    strategy: str
    prompt: str
    score: float = 0.0
    injected_difficult_cases: bool = False


class OptimizationResult(BaseModel):
    """
    优化结果数据模型
    
    作为 optimize 方法的返回值
    """
    optimized_prompt: str
    message: str = ""
    diagnosis: Optional[Dict[str, Any]] = None
    intent_analysis: Optional[Dict[str, Any]] = None
    deep_analysis: Optional[Dict[str, Any]] = None
    applied_strategies: List[Dict[str, Any]] = Field(default_factory=list)
    best_strategy: str = "none"
    improvement: float = 0.0
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    validation_failed: bool = False
    failure_reason: str = ""
    validation_issues: List[str] = Field(default_factory=list)
    
    class Config:
        """Pydantic 配置"""
        extra = "allow"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式
        
        :return: 字典格式的优化结果
        """
        return self.model_dump(exclude_none=True)


class OptimizationContext(BaseModel):
    """
    优化上下文
    
    贯穿整个优化流程，传递各阶段数据
    """
    # 输入参数
    prompt: str
    errors: List[Dict[str, Any]]
    dataset: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: Optional[int] = None
    strategy_mode: str = "auto"
    max_strategies: int = 1
    project_id: Optional[str] = None
    selected_modules: Optional[List[int]] = None
    extraction_rule: Optional[str] = None
    strategy_selection_reason: Optional[str] = None
    
    # 阶段结果
    diagnosis_raw: Dict[str, Any] = Field(default_factory=dict)
    intent_analysis: Dict[str, Any] = Field(default_factory=dict)
    deep_analysis: Dict[str, Any] = Field(default_factory=dict)
    advanced_diagnosis: Dict[str, Any] = Field(default_factory=dict)
    
    # 中间数据
    main_errors: List[Dict[str, Any]] = Field(default_factory=list)
    low_priority_errors: List[Dict[str, Any]] = Field(default_factory=list)
    optimized_intents: List[str] = Field(default_factory=list)
    error_history: Dict[str, Any] = Field(default_factory=dict)
    persistent_samples: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 策略与候选
    strategies: List[Any] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    filtered_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    best_result: Dict[str, Any] = Field(default_factory=dict)
    
    # 验证结果
    validation_result: Dict[str, Any] = Field(default_factory=dict)
    validation_set: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 回调函数（不序列化）
    should_stop: Optional[Callable[[], bool]] = None
    on_progress: Optional[Callable[[str], None]] = None
    newly_failed_cases: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        """Pydantic 配置"""
        arbitrary_types_allowed = True
        extra = "allow"
    
    def get_diagnosis_dict(self) -> Dict[str, Any]:
        """
        获取诊断结果字典
        
        合并所有诊断相关数据
        
        :return: 合并后的诊断字典
        """
        diagnosis = self.diagnosis_raw.copy()
        diagnosis["intent_analysis"] = self.intent_analysis
        diagnosis["deep_analysis"] = self.deep_analysis
        diagnosis["advanced_diagnosis"] = self.advanced_diagnosis
        diagnosis["main_errors"] = self.main_errors
        diagnosis["low_priority_clarification_errors"] = self.low_priority_errors
        diagnosis["optimized_intents"] = self.optimized_intents
        diagnosis["persistent_error_samples"] = self.persistent_samples
        
        if self.newly_failed_cases:
            diagnosis["newly_failed_cases"] = self.newly_failed_cases
        
        return diagnosis
    
    def to_stopped_result(self) -> Dict[str, Any]:
        """
        生成停止时的返回结果
        
        :return: 停止结果字典
        """
        return {
            "optimized_prompt": self.prompt,
            "message": "Stopped"
        }
    
    def to_no_error_result(self) -> Dict[str, Any]:
        """
        生成无错误时的返回结果
        
        :return: 无错误结果字典
        """
        return {
            "optimized_prompt": self.prompt,
            "message": "无错误样例，无需优化"
        }
    
    def to_no_strategy_result(self) -> Dict[str, Any]:
        """
        生成无匹配策略时的返回结果
        
        :return: 无策略结果字典
        """
        return {
            "optimized_prompt": self.prompt,
            "diagnosis": self.get_diagnosis_dict(),
            "message": "无匹配策略"
        }
