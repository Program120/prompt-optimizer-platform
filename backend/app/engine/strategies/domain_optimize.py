from loguru import logger
from typing import List, Dict, Any
from .base import BaseStrategy

class DomainDistinctionStrategy(BaseStrategy):
    """
    领域区分策略
    针对领域混淆问题，明确领域边界和特征。
    """
    
    name: str = "domain_distinction"
    priority: int = 80
    description: str = "领域区分策略：明确领域边界和特征"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        dom_analysis = adv_diag.get("domain_analysis", {})
        return bool(dom_analysis.get("domain_confusion"))

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        return self.priority # 高优先级

    def apply(self, prompt: str, errors: List[Dict[str, Any]], diagnosis: Dict[str, Any]) -> str:
        """应用领域区分策略"""
        logger.info(f"策略 {self.name} 开始执行...")
        adv_diag = diagnosis.get("advanced_diagnosis", {})
        dom_analysis = adv_diag.get("domain_analysis", {})
        
        confusions = dom_analysis.get("domain_confusion", [])
        
        instruction_parts = [
            "当前提示词在特定业务领域之间存在混淆。",
            "请通过明确定义以下领域的边界和独特特征来优化提示词："
        ]
        
        if confusions:
            instruction_parts.append("\n已识别的混淆模式：")
            for c in confusions[:3]:
                instruction_parts.append(
                    f"- '{c.get('from', '')}' 和 '{c.get('to', '')}' 之间的混淆 (原因: {c.get('reason', '未知')})"
                )
                
        instruction_parts.append(
            "\n添加明确的规则，基于关键词或用户意图上下文来区分这些领域。"
        )
        
        optimization_instruction = "\n".join(instruction_parts)
        # 这里可以使用 errors，或者如果 analysis 里有 sample cases 更好
        # 目前 domain analysis 没返回 sample cases，所以用 errors
        return self._meta_optimize(
            prompt, errors[:5], optimization_instruction, diagnosis=diagnosis
        )
