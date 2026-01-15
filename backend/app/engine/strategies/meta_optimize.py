from loguru import logger
import re
from typing import List, Dict, Any, Optional
from .base import BaseStrategy


META_OPTIMIZATION_PROMPT: str = """# 角色：提示词优化架构师
你专门优化意图分类提示词，采用**增量、精准、非重复**的优化策略。

# 当前待优化提示词
{prompt}

# 性能诊断报告
## 核心指标
- 整体准确率：{accuracy:.1%}
- 主要混淆对：{confusion_pairs}
- 指令清晰度：{instruction_clarity}/1.0
- 困难案例：{hard_cases_count}个

## 按意图错误分析
{intent_error_analysis}

## Top失败案例深度分析
{top_failures_analysis}

## 历史优化记录
{optimization_history}

## 典型错误样本
{error_samples}

# 优化目标（优先级排序）
1. **首要目标**：解决{confusion_pairs}的混淆问题
2. **次要目标**：针对高错误率意图（{intent_error_analysis}）添加区分规则
3. **架构目标**：提升指令的清晰度和可执行性
4. **预防目标**：避免重复添加已存在的模块

# 严格约束（避免重复的核心规则）
## 结构完整性约束
- **禁止重写整个提示词**：每次只修改1-3个具体问题点
- **禁止重复添加模块**：如果"思维链"已存在，只能优化现有内容，不能新增
- **保留所有{{}}变量**：不得修改或删除任何变量占位符
- **格式一致性**：保持原有的章节标题和缩进风格

## 模块检查清单（优化前必须核对）
检查当前提示词是否已包含以下模块，避免重复：
- [ ] 角色定义
- [ ] 意图定义列表
- [ ] 输出格式规范
- [ ] 思维链/CoT指令
- [ ] Few-shot示例
- [ ] 边界条件说明
- [ ] 实体抽取规则
- [ ] 澄清策略

# 优化策略指导
## 针对混淆问题
- 在意图定义中增加**对比说明**："意图A vs 意图B: 当出现[X]时属于A，出现[Y]时属于B"
- 在示例中添加**混淆边界案例**

## 针对思维链优化
如果已存在CoT模块：
- 细化推理步骤（如：实体识别→意图匹配→置信度评估）
- 添加**检查步骤**："最后检查是否有意图冲突"
如果不存在CoT模块：
- 在合适位置添加**单次**的CoT指令

## 针对指令清晰度
- 将长段落拆分为带编号的步骤
- 使用**动作动词开头**："首先提取实体"，"然后匹配意图"
- 添加**正例和反例**说明

# 输出规范（防止错误的关键）
## 第一步：变更分析报告
用以下格式分析需要修改的部分：

**变更分析**
1. 问题定位：{混淆对/错误模式的具体描述}
2. 影响范围：{会影响哪些意图/模块}
3. 修改策略：{具体如何修改}
4. 重复检查：{确认要修改的模块是否已存在}

## 第二步：精准Git Diff
**格式要求**
- **严格限制**: SEARCH块中的内容必须与原提示词**完全一致**（精确到空格和换行）。
- SEARCH块必须包含**完整的原段落**（从标题到内容结束），严禁随意截断或修改SEARCH内容。
- REPLACE块必须是**完整的替换段落**
- 如果添加新内容，SEARCH块必须是**空段落**或**明确位置标记**

**正确示例：**
<<<<<<< SEARCH
# 思维链要求
请逐步推理。
=======
# 思维链要求
请按以下步骤推理：
1. 识别query中的关键实体
2. 匹配最可能的意图标签
3. 检查是否有混淆意图
4. 输出最终判断
>>>>>>>

**错误示例（会导致重复）：**
<<<<<<< SEARCH
# 输出格式
{
  "intent": ""
}
=======
# 输出格式
{
  "intent": ""
}

# 思维链要求  ← 错误！在另一个模块旁添加新模块
请逐步推理。
>>>>>>>

## 第三步：变更影响评估
- 预期准确率提升：{估计值}
- 可能引入的新风险：{风险评估}
- 是否需要后续优化：{是/否}

# 最后检查清单
在输出前确认：
- [ ] SEARCH块的内容在当前提示词中**逐字逐句精确存在**（如果不一致，Diff将失败）
- [ ] 没有重复添加已存在的模块
- [ ] 所有{{}}变量保持不变
- [ ] 修改点不超过3个
- [ ] 变更针对具体诊断问题

**重要提醒**：如果你发现当前提示词已包含清晰的思维链模块，请优化它而不是新增。重复的CoT指令会降低模型性能。
"""


class MetaOptimizationStrategy(BaseStrategy):
    """元提示词优化策略 - 使用LLM综合自我优化"""
    
    name: str = "meta_optimization"
    priority: int = 60
    description: str = "元优化策略：使用LLM综合分析和优化提示词"
    
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
        logger.info(f"元优化策略 - 原始模型输出:\n{response_content}")
        
        # 应用 Diff
        try:
            return self._apply_diff(prompt, response_content)
        except Exception as e:
            logger.error(f"Meta optimization diff failed: {e}. Return original.")
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

