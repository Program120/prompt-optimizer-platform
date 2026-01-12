"""边界澄清策略 - 解决易混淆意图对"""
import re
from typing import List, Dict, Any
from .base import BaseStrategy


BOUNDARY_CLARIFICATION_PROMPT = """你是提示词优化专家。当前提示词在处理某些相似类别时存在混淆问题。

## 当前提示词
{prompt}

## 混淆分析
以下是模型容易混淆的类别对及典型错误案例：
{confusion_analysis}

## 优化任务
请针对上述混淆问题，在提示词中添加明确的区分规则和边界说明，帮助模型准确区分这些相似类别。

优化要点：
1. 为每对混淆类别添加明确的区分标准
2. 可添加"如果...则属于A类，如果...则属于B类"的判断规则
3. 可添加典型的对比示例
4. 保持原有提示词的结构和模板变量不变

请直接输出优化后的完整提示词："""


class BoundaryClarificationStrategy(BaseStrategy):
    """边界澄清策略 - 为易混淆的意图对添加区分规则"""
    
    name = "boundary_clarification"
    priority = 90
    description = "边界澄清策略：针对易混淆的类别添加明确的区分规则"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """当存在混淆对时适用"""
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        return len(confusion_pairs) > 0
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """混淆对越多，优先级越高"""
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        if confusion_pairs:
            # 基于最高混淆率调整优先级
            max_rate = max(pair[2] for pair in confusion_pairs) if confusion_pairs else 0
            return int(self.priority * (1 + max_rate))
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """应用边界澄清策略"""
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        if not confusion_pairs:
            return prompt
        
        # 构建混淆分析文本
        confusion_analysis = self._build_confusion_analysis(confusion_pairs, errors)
        
        # 构建优化提示
        optimize_prompt = BOUNDARY_CLARIFICATION_PROMPT.format(
            prompt=prompt,
            confusion_analysis=confusion_analysis
        )
        
        # 调用 LLM 优化
        return self._call_llm(optimize_prompt)
    
    def _build_confusion_analysis(
        self, 
        confusion_pairs: List[tuple], 
        errors: List[Dict[str, Any]]
    ) -> str:
        """构建混淆分析文本"""
        lines = []
        for intent_a, intent_b, rate in confusion_pairs[:5]:  # 最多处理5对
            lines.append(f"\n### {intent_a} vs {intent_b} (混淆率: {rate:.1%})")
            
            # 找出相关错误示例
            related_errors = [
                e for e in errors 
                if (e.get('target') == intent_a and e.get('output') == intent_b) or
                   (e.get('target') == intent_b and e.get('output') == intent_a)
            ][:3]
            
            if related_errors:
                lines.append("典型错误案例：")
                for e in related_errors:
                    lines.append(f"- 输入: {e.get('query', '')[:100]}")
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
        # 清理 <think> 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content
