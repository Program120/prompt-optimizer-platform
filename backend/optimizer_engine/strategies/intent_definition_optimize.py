"""
意图定义优化策略 - 优化意图的定义描述使其更清晰准确

功能:
1. 分析并优化意图的定义描述
2. 添加意图的典型示例和边界说明
3. 强化意图之间的区分规则
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class IntentDefinitionOptimizationStrategy(BaseStrategy):
    """
    意图定义优化策略 - 优化意图的定义描述
    
    适用场景:
    - 意图描述不够清晰导致混淆
    - 缺少意图的典型示例
    - 意图之间的边界模糊
    """
    
    name: str = "intent_definition_optimization"
    priority: int = 88
    description: str = "意图定义优化策略：优化意图的定义描述使其更清晰准确"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当存在意图混淆或意图定义不清时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查是否有意图分析结果
        intent_analysis: Dict[str, Any] = diagnosis.get("intent_analysis", {})
        top_failing_intents: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )
        
        # 存在失败意图时适用
        if len(top_failing_intents) > 0:
            return True
        
        # 检查混淆对
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        confusion_pairs: List = error_patterns.get("confusion_pairs", [])
        
        return len(confusion_pairs) >= 2
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        意图混淆越严重，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        intent_analysis: Dict[str, Any] = diagnosis.get("intent_analysis", {})
        top_failing_intents: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )
        
        # 根据失败意图数量调整优先级
        failing_count: int = len(top_failing_intents)
        if failing_count >= 5:
            return int(self.priority * 1.2)
        elif failing_count >= 3:
            return int(self.priority * 1.1)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用意图定义优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析意图问题
        intent_analysis_text: str = self._analyze_intent_issues(diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词中的意图定义不够清晰，导致模型混淆。

## 意图问题分析

{intent_analysis_text}

## 优化要求

1. **清晰定义**: 为每个意图提供简洁明确的定义描述
2. **典型示例**: 为高混淆意图添加典型的查询示例
3. **区分规则**: 明确说明容易混淆的意图之间的区别
4. **边界说明**: 说明每个意图的适用边界和不适用场景
5. **关键词提示**: 列出每个意图的关键触发词

请使用 SEARCH/REPLACE 格式输出修改内容。
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _analyze_intent_issues(self, diagnosis: Dict[str, Any]) -> str:
        """
        分析意图相关问题
        
        :param diagnosis: 诊断分析结果
        :return: 意图问题分析文本
        """
        lines: List[str] = []
        
        # 获取意图分析结果
        intent_analysis: Dict[str, Any] = diagnosis.get("intent_analysis", {})
        top_failing_intents: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )[:5]
        
        if top_failing_intents:
            lines.append("### 高失败率意图")
            for intent_info in top_failing_intents:
                intent: str = intent_info.get("intent", "")
                error_count: int = intent_info.get("error_count", 0)
                error_rate: float = intent_info.get("error_rate", 0)
                confusion_targets: List[Dict[str, Any]] = intent_info.get(
                    "confusion_targets", []
                )
                
                lines.append(f"- **{intent}**: {error_count}个错误 ({error_rate:.1%})")
                
                if confusion_targets:
                    confused_with: str = ", ".join([
                        ct["target"] for ct in confusion_targets[:2]
                    ])
                    lines.append(f"  常与以下意图混淆: {confused_with}")
            lines.append("")
        
        # 获取混淆对信息
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        confusion_pairs: List = error_patterns.get("confusion_pairs", [])[:5]
        
        if confusion_pairs:
            lines.append("### 主要混淆对")
            for intent_a, intent_b, rate in confusion_pairs:
                lines.append(f"- {intent_a} ↔ {intent_b} (混淆率: {rate:.1%})")
        
        # 获取深度分析结果
        deep_analysis: Dict[str, Any] = diagnosis.get("deep_analysis", {})
        analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])[:3]
        
        if analyses:
            lines.append("")
            lines.append("### 根因分析摘要")
            for analysis in analyses:
                intent: str = analysis.get("intent", "")
                analysis_text: str = analysis.get("analysis", "")[:200]
                lines.append(f"- **{intent}**: {analysis_text}...")
        
        return "\n".join(lines) if lines else "暂无明显的意图定义问题"
