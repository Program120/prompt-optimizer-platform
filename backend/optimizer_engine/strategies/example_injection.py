"""困难案例注入策略 - 将困难案例注入到few-shot示例中"""
import re
from typing import List, Dict, Any
from .base import BaseStrategy


EXAMPLE_INJECTION_PROMPT = """你是提示词优化专家。当前提示词在处理一些困难案例时表现不佳。

## 当前提示词
{prompt}

## 困难案例分析
以下是模型难以正确处理的典型案例：
{hard_cases}

## 优化任务
请在提示词中注入这些困难案例作为示例，帮助模型学会正确处理类似情况：

1. **选择性注入**: 选择最具代表性的困难案例作为 few-shot 示例
2. **格式统一**: 确保新增示例与原有示例格式一致
3. **添加解释**: 可适当添加为什么这样分类的简短说明
4. **保持模板变量**: 必须保留原有的 {{}} 模板变量

请直接输出优化后的完整提示词："""


class DifficultExampleInjectionStrategy(BaseStrategy):
    """困难案例注入策略 - 将困难案例注入到few-shot示例中"""
    
    name = "difficult_example_injection"
    priority = 70
    description = "困难案例注入策略：将难处理的案例作为示例注入提示词"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """当存在较多困难案例时适用"""
        hard_cases = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        return len(hard_cases) >= 5
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """困难案例越多，优先级越高"""
        hard_cases = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if len(hard_cases) >= 10:
            return int(self.priority * 1.3)
        elif len(hard_cases) >= 5:
            return int(self.priority * 1.1)
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """应用困难案例注入策略"""
        hard_cases = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if not hard_cases:
            hard_cases = errors[:10]  # 如果没有识别到 hard_cases，使用前10个错误
        
        # 构建困难案例分析
        hard_cases_text = self._build_hard_cases_text(hard_cases[:10])
        
        # 构建优化提示
        optimize_prompt = EXAMPLE_INJECTION_PROMPT.format(
            prompt=prompt,
            hard_cases=hard_cases_text
        )
        
        # 调用 LLM 优化
        return self._call_llm(optimize_prompt)
    
    def _build_hard_cases_text(self, hard_cases: List[Dict[str, Any]]) -> str:
        """构建困难案例文本"""
        lines = []
        for i, case in enumerate(hard_cases, 1):
            lines.append(f"\n### 案例 {i}")
            lines.append(f"输入: {str(case.get('query', ''))[:150]}")
            lines.append(f"正确分类: {case.get('target', '')}")
            lines.append(f"模型错误输出: {case.get('output', '')}")
        
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
