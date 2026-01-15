from loguru import logger
import re
from typing import List, Dict, Any
from .base import BaseStrategy


INSTRUCTION_REFINEMENT_PROMPT = """你是提示词优化专家。当前提示词的指令部分不够清晰，导致模型执行时产生歧义。

## 当前提示词
{prompt}

## 指令问题分析
{instruction_issues}

## 典型错误案例
{error_samples}

## 优化任务
请优化提示词的指令部分，使其更加清晰、明确、易于执行：

1. **增加明确性**: 将模糊的指令改为具体的操作步骤
2. **添加步骤引导**: 如"请按以下步骤分析..."
3. **明确边界条件**: 清晰定义什么情况属于什么类别
4. **保持模板变量**: 必须保留原有的 {{}} 模板变量

请直接输出优化后的完整提示词："""


class InstructionRefinementStrategy(BaseStrategy):
    """指令优化策略 - 提升指令的清晰度和可执行性"""
    
    name: str = "instruction_refinement"
    priority: int = 80
    description: str = "指令优化策略：提升指令清晰度，添加步骤引导"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """当指令清晰度不足时适用"""
        clarity = diagnosis.get("prompt_analysis", {}).get("instruction_clarity", 1.0)
        return clarity < 0.7
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """清晰度越低，优先级越高"""
        clarity = diagnosis.get("prompt_analysis", {}).get("instruction_clarity", 1.0)
        if clarity < 0.7:
            # 清晰度越低，优先级越高
            return int(self.priority * (1 + (0.7 - clarity)))
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """应用指令优化策略"""
        logger.info(f"策略 {self.name} 开始执行...")
        prompt_analysis = diagnosis.get("prompt_analysis", {})
        
        # 构建指令问题分析
        instruction_issues = self._build_instruction_issues(prompt_analysis)
        
        # 构造优化指令
        instruction_text = f"""
请优化提示词的指令部分，使其更加清晰、明确、易于执行。

# 指令问题分析
{instruction_issues}

# 优化具体要求
1. **增加明确性**: 将模糊的指令改为具体的操作步骤
2. **添加步骤引导**: 如"请按以下步骤分析..."
3. **明确边界条件**: 清晰定义什么情况属于什么类别
4. **保持模板变量**: 必须保留原有的 {{}} 模板变量
"""
        
        # 使用通用的元优化方法 (支持 Diff 模式)
        return self._meta_optimize(
            prompt, 
            errors, 
            instruction_text, 
            conservative=True,
            diagnosis=diagnosis
        )
    
    def _build_instruction_issues(self, prompt_analysis: Dict[str, Any]) -> str:
        """构建指令问题分析"""
        issues = []
        
        clarity = prompt_analysis.get("instruction_clarity", 1.0)
        if clarity < 0.5:
            issues.append("- 指令整体模糊，缺乏具体操作指引")
        elif clarity < 0.7:
            issues.append("- 指令存在歧义，部分场景定义不清")
        
        # format_issues 现在是 Dict (包含 issues 列表)
        format_issues_data = prompt_analysis.get("format_issues", {})
        format_issues = format_issues_data.get("issues", [])
        
        if format_issues:
            issues.append(f"- 输出格式问题: {', '.join(format_issues[:3])}")
        
        if not issues:
            issues.append("- 指令可进一步明确化")
        
        return "\n".join(issues)
    
    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """构建错误样例文本"""
        if not errors:
            return "暂无典型错误案例"
        
        lines = []
        for e in errors[:5]:
            lines.append(f"- 输入: {str(e.get('query', ''))[:100]}")
            lines.append(f"  预期: {e.get('target', '')} | 实际: {e.get('output', '')}")
        return "\n".join(lines)
    

