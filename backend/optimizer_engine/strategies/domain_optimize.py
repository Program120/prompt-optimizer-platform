from typing import List, Dict, Any
from .base import BaseStrategy

class DomainDistinctionStrategy(BaseStrategy):
    """
    领域区分策略
    针对领域混淆问题，明确领域边界和特征。
    """
    
    @property
    def name(self) -> str:
        return "domain_distinction"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        dom_analysis = adv_diag.get("domain_analysis", {})
        return bool(dom_analysis.get("domain_confusion"))

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        return 80 # 高优先级

    def apply(self, prompt: str, errors: List[Dict[str, Any]], diagnosis: Dict[str, Any]) -> str:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        dom_analysis = adv_diag.get("domain_analysis", {})
        
        confusions = dom_analysis.get("domain_confusion", [])
        
        instruction_parts = [
            "The current prompt exhibits confusion between specific business domains.",
            "Please optimize the prompt by clearly defining the boundaries and unique characteristics of the following domains:"
        ]
        
        if confusions:
            instruction_parts.append("\nIdentified Confusion Patterns:")
            for c in confusions[:3]:
                instruction_parts.append(
                    f"- Confusion between '{c.get('from')}' and '{c.get('to')}' (Reason: {c.get('reason', 'N/A')})"
                )
                
        instruction_parts.append(
            "\nAdd explicit rules to distinguish these domains based on keywords or user intent context."
        )
        
        optimization_instruction = "\n".join(instruction_parts)
        # 这里可以使用 errors，或者如果 analysis 里有 sample cases 更好
        # 目前 domain analysis 没返回 sample cases，所以用 errors
        return self._meta_optimize(prompt, errors[:5], optimization_instruction)
