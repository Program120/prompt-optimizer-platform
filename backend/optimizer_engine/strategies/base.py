"""策略基类定义"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStrategy(ABC):
    """优化策略基类"""
    
    name: str = "base"
    priority: int = 0
    description: str = ""
    
    def __init__(self, llm_client=None, model_config: Dict[str, Any] = None):
        self.llm_client = llm_client
        self.model_config = model_config or {}
    
    @abstractmethod
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用策略优化提示词
        
        Args:
            prompt: 当前提示词
            errors: 错误样例列表
            diagnosis: 诊断分析结果
            
        Returns:
            优化后的提示词
        """
        pass
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果
        
        Args:
            diagnosis: 诊断分析结果
            
        Returns:
            是否适用
        """
        return True
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """根据诊断结果动态计算优先级"""
        return self.priority
