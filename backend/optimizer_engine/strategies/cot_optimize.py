"""
CoT 推理优化策略 - 增强提示词的思维链逻辑
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class CoTReasoningStrategy(BaseStrategy):
    """思维链(CoT)优化策略 - 强化推理过程"""
    
    name: str = "cot_reasoning"
    priority: int = 85
    description: str = "CoT优化策略：添加或修复思维链推理步骤"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用。
        
        适用于:
        1. 尚未包含 CoT 关键词 (step-by-step, thinking, etc.)
        2. 或者是复杂任务 (prompt_complexity > 0.7) 且准确率不高
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        # 如果没有 CoT，强烈建议应用
        if not has_cot:
            return True
            
        # 如果有 CoT 但效果不好 (accuracy < 0.8)，可能需要修复逻辑
        accuracy: float = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        return accuracy < 0.8
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级。
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            return 95  # 缺失 CoT 时优先级极高
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用 CoT 优化。
        
        参数:
            prompt: 当前提示词内容
            errors: 错误样例列表
            diagnosis: 诊断结果字典
            
        返回:
            优化后的提示词
        """
        
        # 构造优化指令
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            instruction: str = """
当前提示词缺乏清晰的思维链 (CoT) 推理过程。
请在提示词的 **"Output Format" (输出格式)** 相关章节之前，插入一个新的 **"# Reasoning Steps" (逐步推理)** 章节。

具体要求：
1. 寻找提示词中关于输出格式的描述（例如 "# Output Format Guidelines" 或类似标题）。
2. 使用 SEARCH 块包含该标题及其上方的一行作为定位锚点。
3. 在 REPLACE 块中，在锚点之前插入思维链引导。
4. 内容要求：
   - 明确引导模型在回答前进行思考。
   - 使用结构化的步骤（步骤 1，步骤 2...）。
   - 确保推理逻辑与错误案例的事实相符。
"""
        else:
            instruction: str = """
当前提示词已有 CoT 但仍产生错误。推理逻辑可能存在缺陷或被跳过。
请找到现有的 "# Reasoning Steps" (或类似思维链章节)，并对其内容进行重写以增强稳健性。

具体要求：
1. 使用 SEARCH 块精确定位现有的思维链章节内容。
2. 在 REPLACE 块中提供改进后的推理步骤。
3. 改进方向：
   - 分析模型为何在提供的错误案例上失败。
   - 调整推理步骤以覆盖这些边缘情况。
   - 强制要求更严格地遵守逻辑步骤。
"""
            
        return self._meta_optimize(
            prompt, errors, instruction, conservative=True, diagnosis=diagnosis
        )
