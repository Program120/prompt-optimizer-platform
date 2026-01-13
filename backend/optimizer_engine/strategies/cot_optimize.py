"""CoT 推理优化策略 - 增强提示词的思维链逻辑"""
from typing import List, Dict, Any
from .base import BaseStrategy


class CoTReasoningStrategy(BaseStrategy):
    """思维链(CoT)优化策略 - 强化推理过程"""
    
    name = "cot_reasoning"
    priority = 85
    description = "CoT优化策略：添加或修复思维链推理步骤"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        适用于:
        1. 尚未包含 CoT 关键词 (step-by-step, thinking, etc.)
        2. 或者是复杂任务 (prompt_complexity > 0.7) 且准确率不高
        """
        prompt_analysis = diagnosis.get("prompt_analysis", {})
        has_cot = prompt_analysis.get("has_cot", False)
        
        # 如果没有 CoT，强烈建议应用
        if not has_cot:
            return True
            
        # 如果有 CoT 但效果不好 (accuracy < 0.8)，可能需要修复逻辑
        accuracy = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        return accuracy < 0.8
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        prompt_analysis = diagnosis.get("prompt_analysis", {})
        has_cot = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            return 95  # 缺失 CoT 时优先级极高
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """应用 CoT 优化"""
        
        # 构造优化指令
        prompt_analysis = diagnosis.get("prompt_analysis", {})
        has_cot = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            instruction = """
The current prompt lacks a clear Chain-of-Thought (CoT) reasoning process.
Please ADD a dedicated "Step-by-Step Reasoning" section before the final output.
- Explicitly guide the model to think before answering.
- Use structured steps (Step 1, Step 2...).
- Ensure the reasoning logic aligns with the ground truth of the error cases.
"""
        else:
            instruction = """
The current prompt has CoT but still produces errors. The reasoning logic might be flawed or skipped.
Please REWRITE the reasoning steps to be more robust.
- Analyze why the model failed on the provided Error Cases.
- Adjust the reasoning steps to cover these edge cases.
- Enforce stricter adherence to the logic steps.
"""
            
        return self._meta_optimize(prompt, errors, instruction, conservative=True)
