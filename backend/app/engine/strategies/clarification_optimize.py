from loguru import logger
from typing import List, Dict, Any, Optional
from .base import BaseStrategy


class ClarificationMechanismStrategy(BaseStrategy):
    """
    澄清机制优化策略类。

    该策略负责检测和优化提示词中的澄清触发条件。
    它根据诊断结果判断提示词是否过度请求澄清或在需要时未能请求澄清，
    并据此调整提示词中的指令，以平衡交互的效率和准确性。
    """
    
    name: str = "clarification_mechanism"
    priority: int = 75
    description: str = "澄清机制策略：优化澄清触发条件"

    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果。

        :param diagnosis: 包含高级诊断信息的字典。
        :return: 如果诊断结果显示存在澄清机制问题，则返回 True，否则返回 False。
        """
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        clar_analysis: Dict[str, Any] = adv_diag.get("clarification_analysis", {})
        result: bool = clar_analysis.get("has_issue", False)
        
        if result:
             logger.info(f"策略 {self.name} 适用检测通过: 发现澄清机制问题")
        return result

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        获取当前策略的优先级。

        :param diagnosis: 诊断结果（此处未使用，但保持接口一致）。
        :return: 策略的优先级数值。
        """
        return self.priority

    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用澄清机制优化策略对提示词进行调整。

        根据诊断出的过度澄清或缺失澄清问题，构建相应的优化指令，
        并调用元优化方法生成新的提示词版本。

        :param prompt: 当前待优化的提示词文本。
        :param errors: 错误样例列表。
        :param diagnosis: 详细的诊断分析结果。
        :return: 优化后的提示词文本。
        """
        logger.info(f"策略 {self.name} 开始执行优化流程...")
        
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        clar_analysis: Dict[str, Any] = adv_diag.get("clarification_analysis", {})
        
        unnecessary_rate: float = clar_analysis.get("unnecessary_rate", 0.0)
        missing_rate: float = clar_analysis.get("missing_rate", 0.0)
        
        logger.debug(f"澄清分析数据 - 过度澄清率: {unnecessary_rate}, 缺失澄清率: {missing_rate}")
        
        instruction_parts: List[str] = [
            "当前提示词的澄清触发机制存在问题。"
        ]
        
        if unnecessary_rate > missing_rate:
            logger.info("检测为由于过度澄清导致的问题，准备放宽约束。")
            instruction_parts.append(
                "它过于频繁地请求澄清（过度澄清）。"
                "请放宽约束，允许模型从上下文推断意图，"
                "除非歧义性非常关键。"
            )
        else:
            logger.info("检测为由于缺失澄清导致的问题，准备加强约束。")
            instruction_parts.append(
                "它在需要时未能请求澄清（缺失澄清）。"
                "请添加规则，在关键信息（如账户类型、具体产品）缺失时，明确要求请求澄清。"
            )
            
        optimization_instruction: str = "\n".join(instruction_parts)
        sample_cases: List[Dict[str, Any]] = clar_analysis.get("sample_cases", errors[:3])
        
        logger.info(f"生成的优化指令长度: {len(optimization_instruction)} 字符")
        
        return self._meta_optimize(
            prompt, sample_cases, optimization_instruction, diagnosis=diagnosis
        )
