"""
意图定义优化策略 - 优化意图的定义描述使其更清晰准确

功能:
1. 分析并优化意图的定义描述
2. 添加意图的典型示例和边界说明
3. 强化意图之间的区分规则
"""
from loguru import logger
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
    module_name: str = "意图体系定义"
    
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
        logger.info(f"策略 {self.name} 开始执行...")
        # 分析意图问题
        intent_analysis_text: str = self._analyze_intent_issues(diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词中的意图体系定义不够完善，需要给出意图识别的「字典」作为核心匹配标准。

## 意图问题分析

{intent_analysis_text}

## 优化要求

请按照以下要点完善提示词的意图体系定义部分：

### 1. 明确位置（Module Order: 4）
- **先识别**原提示词中意图体系定义的具体位置。
- 本模块必须位于**Query 预处理规则之后**（第4个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 完整识别现有意图（CRITICAL - 必须首先执行）
**在进行任何格式化之前，必须先完整识别原提示词中的所有意图：**
1. 仔细阅读原提示词，**逐个列出**其中定义的所有意图名称
2. 确认意图数量，避免遗漏任何一个
3. 如果原提示词使用的是非 JSON 格式（如表格、列表等），转换时**必须100%保留**所有意图

> ⚠️ **严禁丢失意图**：格式化后的意图数量必须 >= 原提示词中的意图数量

### 3. 意图定义 JSON 结构
用 JSON 格式定义所有意图标签，必须包含以下几要素：
- **意图名称要严格遵循原提示词中的意图，不要新增意图**
- **除意图名称以外的所有字段每次仅允许最小幅改动（不超过2个新增/删改/调整），稳步迭代！**

JSON 结构要求：
```json
{{
  "intents": [
    {{
      "name": "意图名称",
      "desc": "意图描述（一句话说明该意图的用途）",
      "scope": "详细职责（从原提示词中的意图定义抽取，说明该意图的具体职责边界）",
      "typical_queries": ["典型Query1", "典型Query2"],
      "exclusions": ["排除场景1", "排除场景2"],
      "trigger_words": {{
        "positive": ["正向触发词1", "正向触发词2"],
        "negative": ["负向排除词1", "负向排除词2"]
      }}
    }}
  ]
}}
```

> **重要提示**：请基于原提示词中已有的意图定义来完善 JSON，不要使用通用示例。

### 4. 意图完整性要求
- **无重叠**: 确保任意两个意图之间没有交集
- **无遗漏**: 覆盖目标业务的全部场景
- **明确边界**: 每个意图的核心判断标准清晰无歧义

### 5. 排除场景说明
在每个意图的 `exclusions` 字段中明确「不属于本意图」的典型情况：
- 边界 case 的归属说明
- 容易混淆的情况及区分方法

### 6. 关键触发词
在每个意图的 `trigger_words` 字段中列出：
- `positive`: 正向触发词（强关联）
- `negative`: 负向排除词（明确不属于该意图）

"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis,
            module_name=self.module_name
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
