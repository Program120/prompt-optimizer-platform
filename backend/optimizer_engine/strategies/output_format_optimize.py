"""
标准化输出优化策略 - 统一输出格式与字段定义

功能:
1. 明确输出载体（如 JSON 格式），禁止额外文字说明
2. 定义输出字段（intent：意图数组；confidence：置信度；clarify：澄清话术）
3. 给出各类场景的输出模板，要求模型严格遵循
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class OutputFormatOptimizationStrategy(BaseStrategy):
    """
    标准化输出优化策略 - 统一输出格式与字段定义
    
    适用场景:
    - 模型输出格式不稳定或不规范
    - 缺少明确的输出字段定义
    - 输出格式难以被下游系统解析
    """
    
    name: str = "output_format_optimization"
    priority: int = 80
    description: str = "标准化输出优化策略：统一 JSON 格式与字段定义"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当存在输出格式问题或需要标准化输出时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查提示词分析中的格式问题
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        format_issues: List[str] = prompt_analysis.get("format_issues", [])
        
        if format_issues:
            return True
        
        # 检查是否有输出格式相关的错误
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        format_errors: int = error_patterns.get("format_errors", 0)
        
        if format_errors > 0:
            return True
        
        # 检查输出一致性评分
        output_consistency: float = prompt_analysis.get("output_consistency", 1.0)
        
        return output_consistency < 0.8
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        格式问题越严重，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        format_issues: List[str] = prompt_analysis.get("format_issues", [])
        
        # 格式问题越多，优先级越高
        issue_count: int = len(format_issues)
        if issue_count >= 5:
            return int(self.priority * 1.3)
        elif issue_count >= 2:
            return int(self.priority * 1.1)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用标准化输出优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析当前输出格式问题
        format_analysis: str = self._analyze_format_issues(prompt, errors, diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词的输出格式定义不够规范，需要进行标准化。

## 输出格式问题分析

{format_analysis}

## 优化要求

请按照以下要点优化提示词的输出格式定义部分：

### 1. 明确输出载体
- 强制使用 **JSON 格式** 作为输出载体
- **禁止** 在 JSON 之外输出任何额外的文字说明、解释或前缀
- 确保输出可以被直接解析为合法的 JSON 对象

### 2. 定义标准输出字段
```json
{{
    "intent": ["意图1", "意图2"],  // 必填，意图标签数组，单意图时为单元素数组
    "confidence": 0.95,           // 必填，置信度，范围 0.0-1.0
    "clarify": null,              // 可选，澄清话术，无需澄清时为 null
    "reasoning": "判断依据..."     // 可选，简要说明判断逻辑
}}
```

### 3. 各场景输出模板

**单意图场景**:
```json
{{"intent": ["查询订单状态"], "confidence": 0.92, "clarify": null}}
```

**多意图场景**:
```json
{{"intent": ["退款申请", "查询物流"], "confidence": 0.88, "clarify": null}}
```

**需要澄清场景**:
```json
{{"intent": [], "confidence": 0.0, "clarify": "请问您是想查询哪个订单的状态？"}}
```

**无意图场景**（问候/闲聊/恶意内容）:
```json
{{"intent": ["无意图"], "confidence": 0.95, "clarify": null}}
```

### 4. 格式要求
- 输出格式定义应放在提示词的结尾部分
- 使用代码块展示 JSON 模板
- 明确说明每个字段的含义、类型和取值范围

请使用 SEARCH/REPLACE 格式输出修改内容。
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _analyze_format_issues(
        self, 
        prompt: str,
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        分析当前输出格式问题
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 问题分析文本
        """
        lines: List[str] = []
        
        # 检查提示词中是否包含 JSON 格式定义
        json_keywords: List[str] = [
            "json", "JSON", "格式", "format", "输出格式"
        ]
        has_json_format: bool = any(kw in prompt for kw in json_keywords)
        
        if not has_json_format:
            lines.append("- 提示词**缺少明确的 JSON 输出格式定义**")
        
        # 检查是否定义了输出字段
        field_keywords: List[str] = [
            "intent", "confidence", "置信度", "clarify", "澄清"
        ]
        defined_fields: List[str] = [kw for kw in field_keywords if kw in prompt]
        
        if len(defined_fields) < 2:
            lines.append("- 提示词**未完整定义输出字段**（如 intent、confidence、clarify）")
        
        # 检查是否有输出模板示例
        template_markers: List[str] = ["{", "```"]
        has_template: bool = any(marker in prompt for marker in template_markers)
        
        if not has_template:
            lines.append("- 提示词**缺少输出模板示例**，可能导致输出格式不稳定")
        
        # 从诊断结果中获取格式问题
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        format_issues: List[str] = prompt_analysis.get("format_issues", [])
        
        if format_issues:
            for issue in format_issues[:3]:
                lines.append(f"- {issue}")
        
        # 检查错误案例中的格式问题
        format_error_count: int = 0
        for e in errors[:10]:
            output: str = str(e.get("output", ""))
            # 简单检查是否为非 JSON 格式
            if output and not output.strip().startswith("{"):
                format_error_count += 1
        
        if format_error_count > 0:
            lines.append(f"- 在错误案例中发现 **{format_error_count} 个非标准格式输出**")
        
        if not lines:
            lines.append("- 当前输出格式定义基本完整，但可进一步标准化和细化")
        
        return "\n".join(lines)
