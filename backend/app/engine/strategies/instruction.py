from loguru import logger
from typing import List, Dict, Any
from .base import BaseStrategy


class InstructionRefinementStrategy(BaseStrategy):
    """
    指令优化策略
    
    用于提升指令的清晰度和可执行性。
    当诊断结果显示指令清晰度较低或存在歧义时，该策略会被激活，
    通过将模糊指令转化为具体步骤、明确边界条件等方式进行优化。
    """
    
    name: str = "instruction_refinement"
    priority: int = 80
    description: str = "指令优化策略：提升指令清晰度，添加步骤引导"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果
        此策略在指令清晰度不足时适用 (< 0.7)
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用 (True/False)
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        clarity: float = float(prompt_analysis.get("instruction_clarity", 1.0))
        return clarity < 0.7
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据清晰度动态计算优先级
        清晰度越低，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 优先级整数值
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        clarity: float = float(prompt_analysis.get("instruction_clarity", 1.0))
        if clarity < 0.7:
            # 清晰度越低，优先级越高，稍微提升权重
            return int(self.priority * (1 + (0.7 - clarity)))
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用指令优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        logger.info(f"策略 {self.name} 开始执行...")
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        
        # 构建指令问题分析
        instruction_issues: str = self._build_instruction_issues(prompt_analysis)
        
        # 构造优化指令
        instruction_text: str = f"""
请优化提示词的指令部分，使其更加清晰、明确、易于执行。

# 指令问题分析
{instruction_issues}

# 优化具体要求
1. **增加明确性**: 将模糊的指令改为具体的操作步骤
2. **添加步骤引导**: 如"请按以下步骤分析..."
3. **明确边界条件**: 清晰定义什么情况属于什么类别
4. **保持模板变量**: 必须保留原有的 {{}} 模板变量
"""
        
        logger.info(f"生成的优化指令长度: {len(instruction_text)} 字符")

        # 使用通用的元优化方法 (支持 Diff 模式)
        return self._meta_optimize(
            prompt, 
            errors, 
            instruction_text, 
            conservative=True,
            diagnosis=diagnosis
        )
    
    def _build_instruction_issues(self, prompt_analysis: Dict[str, Any]) -> str:
        """
        构建指令问题分析文本
        
        :param prompt_analysis: 提示词分析结果
        :return: 格式化后的问题描述
        """
        issues: List[str] = []
        
        clarity: float = float(prompt_analysis.get("instruction_clarity", 1.0))
        if clarity < 0.5:
            issues.append("- 指令整体模糊，缺乏具体操作指引")
        elif clarity < 0.7:
            issues.append("- 指令存在歧义，部分场景定义不清")
        
        # format_issues 现在是 Dict (包含 issues 列表)
        format_issues_data: Dict[str, Any] = prompt_analysis.get("format_issues", {})
        format_issues_list: List[str] = format_issues_data.get("issues", [])
        
        if format_issues_list:
            issues.append(f"- 输出格式问题: {', '.join(format_issues_list[:3])}")
        
        if not issues:
            issues.append("- 指令可进一步明确化")
        
        return "\n".join(issues)
    
    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """
        构建错误样例文本 (当前未被显式调用，但作为辅助方法保留)
        
        :param errors: 错误样例列表
        :return: 格式化后的错误样例文本
        """
        if not errors:
            return "暂无典型错误案例"
        
        lines: List[str] = []
        for e in errors[:5]:
            lines.append(f"- 输入: {str(e.get('query', ''))[:100]}")
            lines.append(f"  预期: {e.get('target', '')} | 实际: {e.get('output', '')}")
        return "\n".join(lines)
