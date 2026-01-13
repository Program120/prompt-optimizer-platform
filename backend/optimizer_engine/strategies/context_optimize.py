from typing import List, Dict, Any
from .base import BaseStrategy

class ContextEnhancementStrategy(BaseStrategy):
    """
    上下文增强策略
    针对指代消解错误和上下文依赖丢失，增加显式指令和示例。
    """
    
    @property
    def name(self) -> str:
        return "context_enhancement"
        
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        return adv_diag.get("context_analysis", {}).get("has_issue", False)

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        return 85 # 高优先级

    def apply(self, prompt: str, errors: List[Dict[str, Any]], diagnosis: Dict[str, Any]) -> str:
        # 获取高级诊断结果
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        ctx_analysis = adv_diag.get("context_analysis", {})
        
        # 如果没有显著的上下文问题，直接返回原 Prompt 或仅做轻微优化
        # 但为保证策略有效性，我们假设既然被选中了，就强制执行优化
        
        referential_cases = ctx_analysis.get("sample_cases", [])
        if not referential_cases:
            # Fallback to general errors if no specific referential cases found in analysis
            referential_cases = errors[:3]
            
        # 构建 Meta-Prompt
        optimization_instruction = (
            "The current prompt fails to correctly handle context-dependent queries, specifically those using "
            "referential terms (e.g., 'this', 'that', 'it'). \n"
            "Please optimize the prompt by:\n"
            "1. Adding explicit instructions to resolve coreferences using conversation history.\n"
            "2. Emphasizing that the latest query should be interpreted in the context of previous turns.\n"
            "3. Adding a few-shot example that demonstrates correct coreference resolution."
        )
        
        return self._meta_optimize(
            prompt, referential_cases, optimization_instruction, diagnosis=diagnosis
        )
