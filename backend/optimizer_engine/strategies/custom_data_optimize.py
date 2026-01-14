"""
自定义数据优化策略 - 基于用户自定义的训练数据优化提示词

功能:
1. 利用用户提供的自定义数据（如特定领域知识、术语映射等）来优化提示词
2. 支持在提示词中注入领域特定的规则和约束
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class CustomDataOptimizationStrategy(BaseStrategy):
    """
    自定义数据优化策略 - 基于用户自定义数据优化提示词
    
    适用场景:
    - 用户有特定的领域知识需要注入
    - 需要添加自定义的术语映射规则
    - 需要根据业务数据调整提示词
    """
    
    name: str = "custom_data_optimization"
    priority: int = 75
    description: str = "自定义数据优化策略：基于用户自定义数据优化提示词结构"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当诊断结果中包含自定义数据或领域知识时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查是否有自定义数据或领域知识
        custom_data: Dict[str, Any] = diagnosis.get("custom_data", {})
        domain_knowledge: Dict[str, Any] = diagnosis.get("domain_knowledge", {})
        
        return bool(custom_data) or bool(domain_knowledge)
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        自定义数据越丰富，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        custom_data: Dict[str, Any] = diagnosis.get("custom_data", {})
        
        # 自定义数据越多，优先级越高
        data_count: int = len(custom_data)
        if data_count >= 10:
            return int(self.priority * 1.3)
        elif data_count >= 5:
            return int(self.priority * 1.2)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用自定义数据优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 提取自定义数据
        custom_data: Dict[str, Any] = diagnosis.get("custom_data", {})
        domain_knowledge: Dict[str, Any] = diagnosis.get("domain_knowledge", {})
        
        # 构建自定义数据文本
        custom_data_text: str = self._build_custom_data_text(custom_data, domain_knowledge)
        
        # 构造优化指令
        instruction: str = f"""当前提示词需要融入用户提供的自定义数据和领域知识。

## 自定义数据

{custom_data_text}

## 优化要求

1. **术语映射**: 在提示词中添加必要的术语解释和映射规则
2. **领域规则**: 注入领域特定的判断规则和约束
3. **示例更新**: 根据自定义数据更新或添加相关示例
4. **保持结构**: 保留原有提示词的核心结构和模板变量

请使用 SEARCH/REPLACE 格式输出修改内容。
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _build_custom_data_text(
        self, 
        custom_data: Dict[str, Any], 
        domain_knowledge: Dict[str, Any]
    ) -> str:
        """
        构建自定义数据文本
        
        :param custom_data: 用户自定义数据
        :param domain_knowledge: 领域知识
        :return: 格式化的文本
        """
        lines: List[str] = []
        
        # 处理自定义数据
        if custom_data:
            lines.append("### 用户自定义数据")
            for key, value in list(custom_data.items())[:10]:
                lines.append(f"- {key}: {value}")
            lines.append("")
        
        # 处理领域知识
        if domain_knowledge:
            lines.append("### 领域知识")
            for key, value in list(domain_knowledge.items())[:10]:
                lines.append(f"- {key}: {value}")
            lines.append("")
        
        if not lines:
            return "暂无自定义数据"
            
        return "\n".join(lines)
