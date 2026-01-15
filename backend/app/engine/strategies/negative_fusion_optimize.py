"""负向优化融合策略 - 基于错误分析重写并融合提示词"""
import re
import logging
from typing import List, Dict, Any, Optional
from .base import BaseStrategy


# 负向重写提示词模板
PROMPT_NEGATIVE_REWRITE: str = """# 角色：提示词重构专家
你是一位专业的提示词重构专家，擅长基于错误分析从零开始设计高质量的意图分类提示词。

## 任务背景
当前提示词在实际使用中表现不佳，存在较多分类错误。你的任务是**从头重新设计**一份全新的提示词，以彻底解决这些问题。

## 核心约束（必须遵守）
1. **保留原输出结构**：新提示词必须使用与原提示词完全相同的输出格式（JSON 结构、字段名称等）
2. **保留模板变量**：必须保留所有 `{{}}` 包裹的变量（如 `{{input}}`、`{{context}}`）
3. **其他内容全部重写**：除输出结构外，角色定义、意图说明、约束规则、示例等全部重新设计

## 输入信息

### 原始提示词
```
{original_prompt}
```

### 错误样例分析
{error_samples}

### 意图错误分布
{intent_error_analysis}

### 深度根因分析
{deep_analysis}

### 需要包含的标准模块
请确保新提示词包含以下模块结构（根据最佳实践组织）：
{standard_modules}

## 输出格式
请直接输出重写后的完整提示词内容，无需任何额外解释或包装。
确保：
- 输出结构与原提示词完全一致
- 所有模板变量原样保留
- 其他内容基于错误分析全新设计
"""


# 融合提示词模板
PROMPT_FUSION_MERGE: str = """# 角色：提示词融合专家
你是一位专业的提示词融合专家，擅长将两份提示词的优点合并为一份最优的提示词。

## 任务背景
我们有两份提示词：
1. **原始提示词**：经过多轮迭代优化，保留了历史经验
2. **重写提示词**：基于错误分析从零设计，针对性解决了当前问题

你的任务是**智能融合**这两份提示词，取两者之长，生成一份最终的高质量提示词。

## 融合原则
1. **优先采用重写版的结构**：因为它是针对当前错误专门设计的
2. **保留原始版的精华**：
   - 历史积累的边界条件说明
   - 经验证有效的示例
   - 特殊场景的处理规则
3. **消除冗余**：去除重复的内容，保持简洁高效
4. **保持一致性**：确保融合后的提示词逻辑自洽、无矛盾

## 输入信息

### 原始提示词
```
{original_prompt}
```

### 重写提示词
```
{rewritten_prompt}
```

## 输出格式
请直接输出融合后的完整提示词内容，无需任何额外解释或包装。
确保：
- 输出格式与原始提示词一致
- 所有模板变量（`{{}}`）完整保留
- 内容简洁高效，无冗余重复
"""


# 标准模块定义（与前端 STANDARD_MODULES 保持一致）
STANDARD_MODULES: Dict[int, str] = {
    1: "角色与任务定义 (Role & Task Definition)",
    2: "全局约束规则 (Global Constraints)",
    3: "Query 预处理规则 (Query Preprocessing)",
    4: "意图分类定义 (Intent Definition)",
    5: "边界条件与消歧规则 (Boundary Clarification)",
    6: "业务专属数据 (Domain Data)",
    7: "思维链推理步骤 (CoT Reasoning)",
    8: "Few-Shot 示例 (Examples)",
    9: "标准化输出格式 (Output Format)",
}


class NegativeFusionOptimizationStrategy(BaseStrategy):
    """
    负向优化融合策略
    
    该策略采用"推倒重来 + 融合优化"的激进优化方式：
    1. 基于错误分析，保留原输出结构，其他部分全部重写
    2. 将原提示词与重写后的提示词进行智能融合
    
    适用场景：
    - 准确率持续较低，常规增量优化效果不佳
    - 提示词结构混乱，需要整体重构
    """
    
    # 策略名称
    name: str = "negative_fusion_optimization"
    # 策略优先级（较低，作为备选策略）
    priority: int = 40
    # 策略描述
    description: str = "负向优化融合策略：基于错误分析重写提示词并与原版融合"
    
    def __init__(
        self, 
        llm_client=None, 
        model_config: Dict[str, Any] = None,
        semaphore=None
    ):
        """
        初始化负向优化融合策略
        
        :param llm_client: LLM 客户端实例
        :param model_config: 模型配置
        :param semaphore: 并发控制信号量
        """
        super().__init__(llm_client, model_config, semaphore)
        self.logger: logging.Logger = logging.getLogger(__name__)
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用
        
        当满足以下条件时适用：
        1. 存在错误样例
        2. 准确率低于 0.85
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 获取准确率
        accuracy: float = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        
        # 获取错误数量
        error_count: int = diagnosis.get("overall_metrics", {}).get("error_count", 0)
        
        # 准确率低于 0.85 且有错误样例时适用
        is_applicable: bool = accuracy < 0.85 and error_count > 0
        
        if is_applicable:
            self.logger.info(
                f"[负向融合策略] 策略适用条件满足: "
                f"准确率={accuracy:.2%}, 错误数={error_count}"
            )
        
        return is_applicable
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        准确率越低，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态优先级
        """
        accuracy: float = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        
        # 准确率低于 0.5 时大幅提升优先级
        if accuracy < 0.5:
            return int(self.priority * 2.0)
        # 准确率低于 0.7 时中等提升
        elif accuracy < 0.7:
            return int(self.priority * 1.5)
        
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用负向优化融合策略
        
        执行两阶段优化：
        1. 阶段一：基于错误分析重写提示词（保留输出结构）
        2. 阶段二：融合原提示词与重写后的提示词
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        self.logger.info("[负向融合策略] 开始执行两阶段优化...")
        
        # 阶段一：负向重写
        self.logger.info("[负向融合策略] 阶段一：基于错误分析重写提示词...")
        rewritten_prompt: str = self._rewrite_prompt(prompt, errors, diagnosis)
        
        if not rewritten_prompt or rewritten_prompt == prompt:
            self.logger.warning("[负向融合策略] 重写阶段未产生有效输出，返回原提示词")
            return prompt
        
        self.logger.info(
            f"[负向融合策略] 重写完成，长度变化: {len(prompt)} -> {len(rewritten_prompt)}"
        )
        
        # 阶段二：融合优化
        self.logger.info("[负向融合策略] 阶段二：融合原提示词与重写版本...")
        fused_prompt: str = self._fuse_prompts(prompt, rewritten_prompt)
        
        if not fused_prompt:
            self.logger.warning("[负向融合策略] 融合阶段失败，返回重写后的提示词")
            return rewritten_prompt
        
        self.logger.info(
            f"[负向融合策略] 融合完成，最终长度: {len(fused_prompt)}"
        )
        
        return fused_prompt
    
    def _rewrite_prompt(
        self, 
        original_prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        阶段一：基于错误分析重写提示词
        
        :param original_prompt: 原始提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 重写后的提示词
        """
        # 构建错误样例文本
        error_samples: str = self._build_error_samples(errors[:15])
        
        # 构建意图错误分析文本
        intent_analysis: Optional[Dict[str, Any]] = diagnosis.get("intent_analysis")
        intent_error_analysis: str = self._build_intent_analysis(intent_analysis)
        
        # 构建深度分析文本
        deep_analysis: Optional[Dict[str, Any]] = diagnosis.get("deep_analysis")
        deep_analysis_text: str = self._build_deep_analysis(deep_analysis)
        
        # 构建标准模块列表
        standard_modules_text: str = self._build_standard_modules()
        
        # 构建重写提示
        rewrite_input: str = PROMPT_NEGATIVE_REWRITE.format(
            original_prompt=original_prompt,
            error_samples=error_samples,
            intent_error_analysis=intent_error_analysis,
            deep_analysis=deep_analysis_text,
            standard_modules=standard_modules_text
        )
        
        # 调用 LLM 进行重写
        try:
            response: str = self._call_llm(rewrite_input)
            
            # 清理可能的 markdown 包装
            cleaned_response: str = self._clean_markdown_wrapper(response)
            
            return cleaned_response
            
        except Exception as e:
            self.logger.error(f"[负向融合策略] 重写阶段失败: {e}")
            return ""
    
    def _fuse_prompts(
        self, 
        original_prompt: str, 
        rewritten_prompt: str
    ) -> str:
        """
        阶段二：融合原提示词与重写后的提示词
        
        :param original_prompt: 原始提示词
        :param rewritten_prompt: 重写后的提示词
        :return: 融合后的提示词
        """
        # 构建融合提示
        fusion_input: str = PROMPT_FUSION_MERGE.format(
            original_prompt=original_prompt,
            rewritten_prompt=rewritten_prompt
        )
        
        # 调用 LLM 进行融合
        try:
            response: str = self._call_llm(fusion_input)
            
            # 清理可能的 markdown 包装
            cleaned_response: str = self._clean_markdown_wrapper(response)
            
            return cleaned_response
            
        except Exception as e:
            self.logger.error(f"[负向融合策略] 融合阶段失败: {e}")
            return ""
    
    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """
        构建错误样例文本
        
        :param errors: 错误样例列表
        :return: 格式化的错误样例文本
        """
        if not errors:
            return "暂无错误案例"
        
        lines: List[str] = []
        for idx, e in enumerate(errors, 1):
            query: str = str(e.get('query', ''))[:150]
            target: str = str(e.get('target', ''))
            output: str = str(e.get('output', ''))
            reason: str = str(e.get('reason', ''))
            
            lines.append(f"### 案例 {idx}")
            lines.append(f"- **输入**: {query}")
            lines.append(f"- **期望输出**: {target}")
            lines.append(f"- **实际输出**: {output}")
            if reason:
                lines.append(f"- **错误原因**: {reason}")
            lines.append("")
        
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
        
        lines: List[str] = ["| 意图 | 错误数 | 错误率 | 主要混淆目标 |"]
        lines.append("| :--- | :---: | :---: | :--- |")
        
        for failure in top_failures:
            intent: str = failure.get("intent", "")
            error_count: int = failure.get("error_count", 0)
            error_rate: float = failure.get("error_rate", 0)
            confusion_targets: List[Dict[str, Any]] = failure.get(
                "confusion_targets", []
            )
            confusion_str: str = ", ".join([
                ct["target"] for ct in confusion_targets[:2]
            ]) if confusion_targets else "-"
            
            lines.append(
                f"| {intent} | {error_count} | {error_rate:.1%} | {confusion_str} |"
            )
        
        return "\n".join(lines)
    
    def _build_deep_analysis(
        self, 
        deep_analysis: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建深度根因分析文本
        
        :param deep_analysis: 深度分析数据
        :return: 格式化的分析文本
        """
        if not deep_analysis:
            return "暂无深度分析"
        
        analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])
        
        if not analyses:
            return "暂无深度分析"
        
        lines: List[str] = []
        for analysis in analyses[:5]:
            intent: str = analysis.get("intent", "")
            analysis_text: str = analysis.get("analysis", "")
            
            lines.append(f"### {intent}")
            # 截断过长的分析
            if len(analysis_text) > 400:
                analysis_text = analysis_text[:400] + "..."
            lines.append(analysis_text)
            lines.append("")
        
        return "\n".join(lines) if lines else "暂无深度分析"
    
    def _build_standard_modules(self) -> str:
        """
        构建标准模块列表文本
        
        :return: 格式化的模块列表
        """
        lines: List[str] = []
        for module_id, module_name in STANDARD_MODULES.items():
            lines.append(f"{module_id}. {module_name}")
        
        return "\n".join(lines)
    
    def _clean_markdown_wrapper(self, text: str) -> str:
        """
        清理可能的 markdown 代码块包装
        
        :param text: 原始文本
        :return: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除开头的 ```markdown 或 ```
        cleaned: str = re.sub(r'^```(?:markdown)?\s*\n?', '', text.strip())
        # 移除结尾的 ```
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)
        
        return cleaned.strip()
