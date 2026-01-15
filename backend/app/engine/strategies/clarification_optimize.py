from typing import List, Dict, Any
from .base import BaseStrategy

class ClarificationMechanismStrategy(BaseStrategy):
    """
    澄清机制策略
    优化澄清触发条件，防止过度或缺失澄清。
    """
    
    @property
    def name(self) -> str:
        return "clarification_mechanism"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        return adv_diag.get("clarification_analysis", {}).get("has_issue", False)

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        return 75 # 中高优先级

    def apply(self, prompt: str, errors: List[Dict[str, Any]], diagnosis: Dict[str, Any]) -> str:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        clar_analysis = adv_diag.get("clarification_analysis", {})
        
        unnecessary_rate = clar_analysis.get("unnecessary_rate", 0)
        missing_rate = clar_analysis.get("missing_rate", 0)
        
        instruction_parts = [
            "当前提示词的澄清触发机制存在问题。"
        ]
        
        if unnecessary_rate > missing_rate:
            instruction_parts.append(
                "它过于频繁地请求澄清（过度澄清）。"
                "请放宽约束，允许模型从上下文推断意图，"
                "除非歧义性非常关键。"
            )
        else:
            instruction_parts.append(
                "它在需要时未能请求澄清（缺失澄清）。"
                "请添加规则，在关键信息（如账户类型、具体产品）缺失时，明确要求请求澄清。"
            )
            
        optimization_instruction = "\n".join(instruction_parts)
        sample_cases = clar_analysis.get("sample_cases", errors[:3])
        
        return self._meta_optimize(
            prompt, sample_cases, optimization_instruction, diagnosis=diagnosis
        )
