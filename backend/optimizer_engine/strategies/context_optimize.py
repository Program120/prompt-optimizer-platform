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
            "当前提示词无法正确处理具有上下文依赖的查询，特别是在使用 "
            "指代词（如‘这个’、‘那个’、‘它’）时。 \n"
            "请通过以下方式优化提示词：\n"
            "1. 添加显式指令，要求利用对话历史解决指代消解问题。\n"
            "2. 强调应结合前序轮次的内容来理解最新的查询。\n"
            "3. 添加一个演示正确指代消解的 few-shot 示例。"
        )
        
        return self._meta_optimize(
            prompt, referential_cases, optimization_instruction, diagnosis=diagnosis
        )
