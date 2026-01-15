from loguru import logger
import re
from typing import List, Dict, Any, Optional

class PromptRewriter:
    """基于规则和模板的提示词改写器"""
    
    def __init__(self):
        self.templates = {
            "add_cot": self._template_cot,
            "clarify_boundary": self._template_boundary,
            "add_constraints": self._template_constraints,
            "add_examples": self._template_examples
        }

    def rewrite(self, prompt: str, strategy: str, **kwargs) -> str:
        """
        基于策略重写提示词
        
        :param prompt: 原始提示词
        :param strategy: 改写策略名称
        :param kwargs: 策略所需的额外参数
        :return: 改写后的提示词
        """
        if strategy not in self.templates:
            logger.warning(f"未知改写策略: {strategy}，忽略")
            return prompt
            
        logger.debug(f"应用提示词改写策略: {strategy}")
        return self.templates[strategy](prompt, **kwargs)

    def _template_cot(self, prompt: str, **kwargs) -> str:
        """添加思维链(CoT)引导"""
        cot_instruction = """
请按以下步骤思考：
1. 分析输入中的关键信息和意图特征
2. 回忆各分类的定义和边界条件
3. Step-by-step 检查当前输入是否符合某类别的特征
4. 对比相似类别，排除干扰选项
5. 最终给出确定的分类结果
"""
        # 尝试插入到指令部分之后
        if "## 指令" in prompt or "## Instruction" in prompt:
             # 简单地附加到末尾，或者智能插入。这里选择附加到 prompt 末尾但在输出要求之前
             # 为避免破坏由于复杂结构，这里选择追加模式，或者替换原有的思维步骤
             pass
        
        # 简单策略：如果 prompt 看起来像只有指令，直接追加
        return f"{prompt}\n\n{cot_instruction}"

    def _template_boundary(self, prompt: str, boundaries:List[Dict] = None, **kwargs) -> str:
        """添加边界澄清规则"""
        if not boundaries:
            return prompt
            
        rules = []
        for b in boundaries:
            c1 = b.get('class_a')
            c2 = b.get('class_b')
            if c1 and c2:
                rules.append(f"- 区分 {c1} 和 {c2}：注意检查是否包含特征[特定关键词]，若包含则倾向于 {c1}")
        
        rules_text = "\n".join(rules)
        boundary_section = f"""
## 边界判断规则
针对易混淆类别，请注意：
{rules_text}
"""
        return f"{prompt}\n{boundary_section}"

    def _template_constraints(self, prompt: str, constraints: List[str] = None, **kwargs) -> str:
        """添加约束条件"""
        if not constraints:
            return prompt
            
        constraint_text = "\n".join([f"- {c}" for c in constraints])
        section = f"\n## 约束条件\n{constraint_text}\n"
        
        return f"{prompt}{section}"
        
    def _template_examples(self, prompt: str, examples: str = "", **kwargs) -> str:
        """添加示例"""
        if not examples:
            return prompt
            
        return f"{prompt}\n\n## 参考示例\n{examples}"

    def apply_optimization_suggestion(self, prompt: str, suggestions: List[str]) -> str:
        """应用一组优化建议"""
        current_prompt = prompt
        
        if "add_distinction_rules" in suggestions or "boundary_clarification" in suggestions:
            # 注意：这通常需要具体的 boundary info，这里作为示例如果只是标签的话
            pass 
            
        # 这里仅处理不需要额外动态数据的通用改写，或者调用者需要提供数据
        # 既然是 "PromptRewriter"，它应该是一个工具类。
        # 实际逻辑可能在 Strategy 类中调用它。
        
        return current_prompt
