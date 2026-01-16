from loguru import logger
from typing import List, Dict, Any
from .base import BaseStrategy

class DomainDistinctionStrategy(BaseStrategy):
    """
    领域区分策略
    
    针对领域混淆问题，明确领域边界和特征。
    当诊断结果显示模型混淆了不同的业务领域或概念时，该策略会被激活，
    通过注入明确的领域定义和区分规则来优化提示词。
    """
    
    name: str = "domain_distinction"
    priority: int = 80
    description: str = "领域区分策略：明确领域边界和特征"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用 (True/False)
        """
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        dom_analysis: Dict[str, Any] = adv_diag.get("domain_analysis", {})
        # bool conversion handles None or empty list
        return bool(dom_analysis.get("domain_confusion"))

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        获取当前策略的优先级
        
        :param diagnosis: 诊断分析结果
        :return: 优先级整数值
        """
        return self.priority

    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用领域区分策略优化提示词
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        logger.info(f"策略 {self.name} 开始执行...")
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        dom_analysis: Dict[str, Any] = adv_diag.get("domain_analysis", {})
        
        confusions: List[Dict[str, Any]] = dom_analysis.get("domain_confusion", [])
        
        instruction_parts: List[str] = [
            "当前提示词在特定业务领域之间存在混淆。",
            "请通过明确定义以下领域的边界和独特特征来优化提示词："
        ]
        
        if confusions:
            instruction_parts.append("\n已识别的混淆模式：")
            for c in confusions[:3]:
                from_domain: str = str(c.get('from', ''))
                to_domain: str = str(c.get('to', ''))
                reason: str = str(c.get('reason', '未知'))
                instruction_parts.append(
                    f"- '{from_domain}' 和 '{to_domain}' 之间的混淆 (原因: {reason})"
                )
                
        instruction_parts.append(
            "\n添加明确的规则，基于关键词或用户意图上下文来区分这些领域。"
        )
        
        optimization_instruction: str = "\n".join(instruction_parts)
        
        logger.info(f"生成的优化指令长度: {len(optimization_instruction)} 字符")
        
        # 使用 errors 作为样例，因为 domain analysis 目前没有返回专用样例
        return self._meta_optimize(
            prompt, errors[:5], optimization_instruction, diagnosis=diagnosis
        )
