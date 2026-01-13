"""元提示词优化策略 - 使用LLM自我优化提示词"""
import re
from typing import List, Dict, Any, Optional
from .base import BaseStrategy


META_OPTIMIZATION_PROMPT: str = """你是一个提示词优化专家。请优化以下意图分类提示词：

## 当前提示词
{prompt}

## 性能诊断结果
1. 整体准确率：{accuracy:.1%}
2. 主要混淆类别对：{confusion_pairs}
3. 指令清晰度评分：{instruction_clarity}/1.0
4. 困难案例数量：{hard_cases_count}

## 按意图错误率分析
{intent_error_analysis}

## Top 失败意图深度分析
{top_failures_analysis}

## 历史优化经验
{optimization_history}

## 典型错误案例
{error_samples}

## 优化要求
请提供一个优化版本，综合解决以下问题：
1. 解决意图混淆问题（添加区分规则）
2. 提高指令清晰度和可执行性
3. 优化示例选择和格式
4. 添加边界条件说明
5. 针对高失败率意图进行重点优化
6. 参考历史优化经验，避免重复错误
7. **强化 CoT (思维链)**: 确保提示词引导模型进行 Step-by-Step 的推理分析

## 重要约束 (稳步迭代模式)
- 必须保留原有的 {{}} 模板变量（如 {{input}}, {{context}}）
- 禁止翻译或修改变量名
- **严禁重写整个提示词**：仅针对上述问题点进行增量修改
- **保持结构一致性**：保留原有的格式、语气和示例（除非示例显然错误）
- **Use Diff Format**: Output strictly in Search/Replace block format.

## Output Format
1. **Step-by-Step Analysis**:
   - Analyze the confusion pairs and error patterns.
   - Identify which sections of the prompt need modification.
   - Plan the specific text changes.

2. **Git Diff Blocks**:
<<<<<<< SEARCH
[Exact text to be replaced]
=======
[New text]
>>>>>>>

Do NOT output the full prompt. Only the modified sections.

**IMPORTANT - To Avoid Duplication**:
- If you want to modify an existing section (e.g. Reasoning Step), you MUST copy the ENTIRE existing section into the SEARCH block.
- Do NOT just Search for a nearby header and Insert the new section next to it. That will cause duplicates.
- ALWAYS check if the section you want to add already exists in the prompt.
"""


class MetaOptimizationStrategy(BaseStrategy):
    """元提示词优化策略 - 使用LLM综合自我优化"""
    
    name = "meta_optimization"
    priority = 60
    description = "元优化策略：使用LLM综合分析和优化提示词"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """始终适用，作为通用优化策略"""
        return True
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """作为通用策略，优先级较低"""
        accuracy = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        # 准确率越低，优先级越高
        if accuracy < 0.5:
            return int(self.priority * 1.5)
        elif accuracy < 0.7:
            return int(self.priority * 1.2)
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用元优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断结果（包含意图分析和深度分析数据）
        :return: 优化后的提示词
        """
        overall: Dict[str, Any] = diagnosis.get("overall_metrics", {})
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        
        # 获取新增的分析数据
        intent_analysis: Optional[Dict[str, Any]] = diagnosis.get("intent_analysis")
        deep_analysis: Optional[Dict[str, Any]] = diagnosis.get("deep_analysis")
        optimization_history: Optional[Dict[str, Any]] = diagnosis.get(
            "optimization_history"
        )
        
        # 格式化混淆对
        confusion_pairs: List = error_patterns.get("confusion_pairs", [])
        confusion_str: str = ", ".join([
            f"{p[0]} vs {p[1]}" for p in confusion_pairs[:3]
        ]) if confusion_pairs else "无明显混淆"
        
        # 构建错误样例
        error_samples: str = self._build_error_samples(errors[:10])
        
        # 构建意图错误分析文本
        intent_error_analysis: str = self._build_intent_analysis(intent_analysis)
        
        # 构建 Top 失败意图深度分析文本
        top_failures_analysis: str = self._build_deep_analysis(deep_analysis)
        
        # 构建历史优化经验文本 (优先使用通过 knowledge.get_all_history_for_prompt() 获取的完整文本)
        history_text: str = diagnosis.get("optimization_history_text") or self._build_history_text(optimization_history)
        
        # 构建元优化提示
        optimize_prompt: str = META_OPTIMIZATION_PROMPT.format(
            prompt=prompt,
            accuracy=overall.get("accuracy", 0),
            confusion_pairs=confusion_str,
            instruction_clarity=prompt_analysis.get("instruction_clarity", 0.5),
            hard_cases_count=len(error_patterns.get("hard_cases", [])),
            intent_error_analysis=intent_error_analysis,
            top_failures_analysis=top_failures_analysis,
            optimization_history=history_text,
            error_samples=error_samples
        )
        
        # 调用 LLM 优化
        response_content = self._call_llm(optimize_prompt)
        # Log raw output
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"元优化策略 - 原始模型输出:\n{response_content}")
        
        # 应用 Diff
        try:
            return self._apply_diff(prompt, response_content)
        except Exception as e:
            print(f"Meta optimization diff failed: {e}. Return original.")
            return prompt
    
    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """构建错误样例文本"""
        if not errors:
            return "暂无错误案例"
        
        lines = []
        for e in errors[:8]:
            query = str(e.get('query', ''))[:100]
            lines.append(f"- 输入: {query}")
            lines.append(f"  预期: {e.get('target', '')} | 实际: {e.get('output', '')}")
        return "\n".join(lines)
    

        
    def _build_intent_analysis(
        self, 
        intent_analysis: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建意图错误分析文本
        
        :param intent_analysis: 意图分析数据
        :return: 格式化的分析文本
        """
        if not intent_analysis:
            return "暂无意图分析数据"
            
        top_failures: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )[:5]
        
        if not top_failures:
            return "无明显失败意图"
            
        lines: List[str] = ["| 意图 | 错误数 | 主要混淆目标 |"]
        lines.append("| :--- | :---: | :--- |")
        
        for failure in top_failures:
            intent: str = failure.get("intent", "")
            error_count: int = failure.get("error_count", 0)
            confusion_targets: List[Dict[str, Any]] = failure.get(
                "confusion_targets", []
            )
            confusion_str: str = ", ".join([
                ct["target"] for ct in confusion_targets[:2]
            ]) if confusion_targets else "-"
            
            lines.append(f"| {intent} | {error_count} | {confusion_str} |")
            
        return "\n".join(lines)
        
    def _build_deep_analysis(
        self, 
        deep_analysis: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建 Top 失败意图深度分析文本
        
        :param deep_analysis: 深度分析数据
        :return: 格式化的分析文本
        """
        if not deep_analysis:
            return "暂无深度分析"
            
        analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])
        
        if not analyses:
            return "暂无深度分析"
            
        lines: List[str] = []
        for analysis in analyses[:3]:
            intent: str = analysis.get("intent", "")
            analysis_text: str = analysis.get("analysis", "")
            
            lines.append(f"### {intent}")
            # 截断过长的分析
            if len(analysis_text) > 300:
                analysis_text = analysis_text[:300] + "..."
            lines.append(analysis_text)
            lines.append("")
            
        return "\n".join(lines) if lines else "暂无深度分析"
        
    def _build_history_text(
        self, 
        optimization_history: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建历史优化经验文本
        
        :param optimization_history: 历史优化数据
        :return: 格式化的历史文本
        """
        if not optimization_history:
            return "暂无历史优化记录"
            
        version: int = optimization_history.get("version", 0)
        summary: str = optimization_history.get("analysis_summary", "")
        strategies: List[str] = optimization_history.get("applied_strategies", [])
        acc_before: float = optimization_history.get("accuracy_before", 0)
        acc_after: Optional[float] = optimization_history.get("accuracy_after")
        
        lines: List[str] = [f"### 上次优化 (版本 {version})"]
        lines.append(f"- 优化前准确率: {acc_before:.1%}")
        if acc_after is not None:
            lines.append(f"- 优化后准确率: {acc_after:.1%}")
        lines.append(f"- 应用策略: {', '.join(strategies)}")
        
        if summary:
            # 截断过长的总结
            if len(summary) > 200:
                summary = summary[:200] + "..."
            lines.append(f"- 优化总结: {summary}")
            
        return "\n".join(lines)

