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
            "The current prompt has issues with its clarification mechanism."
        ]
        
        if unnecessary_rate > missing_rate:
            instruction_parts.append(
                "It asks for clarification too often (Unnecessary Clarification). "
                "Please relax the constraints and allow the model to infer intent from context "
                "unless the ambiguity is critical."
            )
        else:
            instruction_parts.append(
                "It fails to ask for clarification when needed (Missing Clarification). "
                "Please add rules to explicitly request clarification when crucial information "
                "(like account type, specific product) is missing."
            )
            
        optimization_instruction = "\n".join(instruction_parts)
        sample_cases = clar_analysis.get("sample_cases", errors[:3])
        
        return self._meta_optimize(
            prompt, sample_cases, optimization_instruction, diagnosis=diagnosis
        )
