"""元提示词优化策略 - 使用LLM自我优化提示词"""
import re
from typing import List, Dict, Any
from .base import BaseStrategy


META_OPTIMIZATION_PROMPT = """你是一个提示词优化专家。请优化以下意图分类提示词：

## 当前提示词
{prompt}

## 性能诊断结果
1. 整体准确率：{accuracy:.1%}
2. 主要混淆类别对：{confusion_pairs}
3. 指令清晰度评分：{instruction_clarity}/1.0
4. 困难案例数量：{hard_cases_count}

## 典型错误案例
{error_samples}

## 优化要求
请提供一个优化版本，综合解决以下问题：
1. 解决意图混淆问题（添加区分规则）
2. 提高指令清晰度和可执行性
3. 优化示例选择和格式
4. 添加边界条件说明

## 重要约束
- 必须保留原有的 {{}} 模板变量（如 {{input}}, {{context}}）
- 禁止翻译或修改变量名
- 直接输出优化后的完整提示词，不要包含任何解释

请直接输出优化后的提示词："""


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
        """应用元优化策略"""
        overall = diagnosis.get("overall_metrics", {})
        error_patterns = diagnosis.get("error_patterns", {})
        prompt_analysis = diagnosis.get("prompt_analysis", {})
        
        # 格式化混淆对
        confusion_pairs = error_patterns.get("confusion_pairs", [])
        confusion_str = ", ".join([
            f"{p[0]} vs {p[1]}" for p in confusion_pairs[:3]
        ]) if confusion_pairs else "无明显混淆"
        
        # 构建错误样例
        error_samples = self._build_error_samples(errors[:10])
        
        # 构建元优化提示
        optimize_prompt = META_OPTIMIZATION_PROMPT.format(
            prompt=prompt,
            accuracy=overall.get("accuracy", 0),
            confusion_pairs=confusion_str,
            instruction_clarity=prompt_analysis.get("instruction_clarity", 0.5),
            hard_cases_count=len(error_patterns.get("hard_cases", [])),
            error_samples=error_samples
        )
        
        # 调用 LLM 优化
        return self._call_llm(optimize_prompt)
    
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
    
    def _call_llm(self, prompt: str) -> str:
        """调用 LLM"""
        if not self.llm_client:
            raise ValueError("LLM client not configured")
        
        response = self.llm_client.chat.completions.create(
            model=self.model_config.get("model_name", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "You are a prompt optimization expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=float(self.model_config.get("temperature", 0.7)),
            max_tokens=min(int(self.model_config.get("max_tokens", 2000)), 4096),
            timeout=int(self.model_config.get("timeout", 120)),
            extra_body=self.model_config.get("extra_body")
        )
        
        content = response.choices[0].message.content.strip()
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content
