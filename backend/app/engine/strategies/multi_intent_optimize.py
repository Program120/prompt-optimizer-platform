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
            "当前提示词在多意图识别方面存在困难。"
        ]
        
        if fn_rate > fp_rate:
            instruction_parts.append(
                "它倾向于遗漏多个意图（漏判）。"
                "请加强指令，识别用户查询中所有独立且明确的意图。"
            )
        else:
            instruction_parts.append(
                "它倾向于虚构多个意图（误判）。"
                "请明确指示，仅在显式请求了多个独立操作时才应预测多意图。"
            )
            
        instruction_parts.append(
            "确保输出格式使用指定的分隔符清晰地分离各个意图。"
        )
        
        optimization_instruction = "\n".join(instruction_parts)
        sample_cases = mi_analysis.get("sample_cases", errors[:3])
        
        return self._meta_optimize(prompt, sample_cases, optimization_instruction)
