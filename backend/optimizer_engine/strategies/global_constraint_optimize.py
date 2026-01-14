"""
全局约束优化策略 - 强化提示词中的全局约束和限制条件

功能:
1. 分析并强化提示词中的全局约束条件
2. 添加缺失的边界条件和限制规则
3. 优化负面约束（Negative Constraints）的表述
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class GlobalConstraintOptimizationStrategy(BaseStrategy):
    """
    全局约束优化策略 - 强化提示词中的全局约束
    
    适用场景:
    - 提示词缺乏明确的约束条件
    - 模型频繁违反隐含的规则
    - 需要强化负面约束（禁止做什么）
    """
    
    name: str = "global_constraint_optimization"
    priority: int = 82
    description: str = "全局约束优化策略：强化提示词中的全局约束和限制条件"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当存在约束违反或规则不清晰时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查是否有约束相关的错误模式
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        
        # 检查是否存在规则违反类错误
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        if constraint_violations > 0:
            return True
        
        # 检查提示词分析中是否缺乏约束
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        constraint_clarity: float = prompt_analysis.get("constraint_clarity", 1.0)
        
        return constraint_clarity < 0.7
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        约束问题越严重，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        
        # 约束违反越多，优先级越高
        if constraint_violations >= 10:
            return int(self.priority * 1.3)
        elif constraint_violations >= 5:
            return int(self.priority * 1.2)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用全局约束优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析当前约束问题
        constraint_analysis: str = self._analyze_constraints(errors, diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词的全局约束条件不够清晰或完整，导致模型频繁违反规则。

## 约束问题分析

{constraint_analysis}

## 优化要求

1. **显式约束**: 将隐含的约束条件显式化，使用明确的语言描述
2. **负面约束**: 添加或强化"禁止做什么"的规则（例如：绝对不要...、禁止...）
3. **优先级规则**: 当多个规则冲突时，明确优先级顺序
4. **边界条件**: 为模糊的边界条件添加明确的判断标准
5. **示例强化**: 用示例说明约束的正确应用

请使用 SEARCH/REPLACE 格式输出修改内容。
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _analyze_constraints(
        self, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        分析当前约束问题
        
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 约束问题分析文本
        """
        lines: List[str] = []
        
        # 分析错误模式中的约束问题
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        
        if constraint_violations > 0:
            lines.append(f"- 检测到 {constraint_violations} 个约束违反案例")
        
        # 从错误案例中提取约束相关问题
        lines.append("")
        lines.append("### 典型约束违反案例")
        
        for e in errors[:5]:
            query: str = str(e.get('query', ''))[:100]
            target: str = e.get('target', '')
            output: str = e.get('output', '')
            lines.append(f"- 输入: {query}")
            lines.append(f"  预期: {target} | 实际: {output}")
        
        # 检查提示词中的约束清晰度
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        constraint_clarity: float = prompt_analysis.get("constraint_clarity", 1.0)
        
        if constraint_clarity < 0.7:
            lines.append("")
            lines.append(f"- 约束清晰度评分: {constraint_clarity:.2f} (低于阈值 0.7)")
        
        return "\n".join(lines) if lines else "暂无明显的约束问题"
