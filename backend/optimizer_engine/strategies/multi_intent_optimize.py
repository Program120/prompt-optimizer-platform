from typing import List, Dict, Any
from .base import BaseStrategy

class MultiIntentStrategy(BaseStrategy):
    """
    多意图优化策略
    针对多意图误判、漏判和排序问题。
    """
    
    @property
    def name(self) -> str:
        return "multi_intent_optimization"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        return adv_diag.get("multi_intent_analysis", {}).get("has_issue", False)

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        return 90 # 很高优先级

    def apply(self, prompt: str, errors: List[Dict[str, Any]], diagnosis: Dict[str, Any]) -> str:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        mi_analysis = adv_diag.get("multi_intent_analysis", {})
        
        # 根据具体错误类型定制指令
        fp_rate = mi_analysis.get("false_positive_rate", 0)
        fn_rate = mi_analysis.get("false_negative_rate", 0)
        
        instruction_parts = [
            "The current prompt struggles with multi-intent recognition."
        ]
        
        if fn_rate > fp_rate:
            instruction_parts.append(
                "It tends to miss multiple intents (False Negative). "
                "Please strengthen the instructions to detect ALL distinct intents in the user query."
            )
        else:
            instruction_parts.append(
                "It tends to hallucinate multiple intents (False Positive). "
                "Please clarify that multiple intents should ONLY be predicted when distinct actions are explicitly requested."
            )
            
        instruction_parts.append(
            "Ensure the output format clearly separates intents using the specified delimiter."
        )
        
        optimization_instruction = "\n".join(instruction_parts)
        sample_cases = mi_analysis.get("sample_cases", errors[:3])
        
        return self._meta_optimize(prompt, sample_cases, optimization_instruction)
