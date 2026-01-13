"""策略基类定义"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStrategy(ABC):
    """优化策略基类"""
    
    name: str = "base"
    priority: int = 0
    description: str = ""
    
    def __init__(self, llm_client=None, model_config: Dict[str, Any] = None):
        self.llm_client = llm_client
        self.model_config = model_config or {}
    
    @abstractmethod
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用策略优化提示词
        
        Args:
            prompt: 当前提示词
            errors: 错误样例列表
            diagnosis: 诊断分析结果
            
        Returns:
            优化后的提示词
        """
        pass
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断该策略是否适用于当前诊断结果
        
        Args:
            diagnosis: 诊断分析结果
            
        Returns:
            是否适用
        """
        return True
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """根据诊断结果动态计算优先级"""
        return self.priority

    def _meta_optimize(
        self,
        prompt: str,
        error_cases: List[Dict[str, Any]],
        instruction: str,
        conservative: bool = True
    ) -> str:
        """
        基于特定指令进行元优化的通用方法
        
        :param conservative: 是否开启保守模式（默认 True，稳步迭代）
        """
        error_text = self._build_error_samples(error_cases)
        
        constraint_text = ""
        if conservative:
            constraint_text = """
## Constraints (Conservative Optimization)
1. You MUST maintain the original structure, tone, and formatting of the prompt.
2. Do NOT rewrite the entire prompt. Only modify specific sections to address the issues.
3. Keep all existing few-shot examples unless explicitly asked to replace them.
4. The goal is incremental improvement, avoiding radical scale changes that might break existing capabilities.
"""
        
        optimization_prompt = f"""You are a prompt engineering expert.
Please optimize the following prompt based on the specific instruction and error cases provided.

## Current Prompt
{prompt}

## Error Cases
{error_text}

## Optimization Instruction
{instruction}
{constraint_text}
## Output Format
Output ONLY the optimized prompt content. Do not include any explanations.
"""
        return self._call_llm(optimization_prompt)

    def _build_error_samples(self, errors: List[Dict[str, Any]]) -> str:
        """构建错误样例文本"""
        if not errors:
            return "暂无错误案例"
        
        lines = []
        for e in errors[:5]:
            query = str(e.get('query', ''))[:200]
            lines.append(f"- Input: {query}")
            lines.append(f"  Expected: {e.get('target', '')} | Actual: {e.get('output', '')}\n")
        return "\n".join(lines)

    def _call_llm(self, prompt: str) -> str:
        """
        调用 LLM
        """
        import re
        if not self.llm_client:
            # Fallback for testing or if client not provided
            return prompt
        
        try:
            response = self.llm_client.chat.completions.create(
                model=self.model_config.get("model_name", "gpt-3.5-turbo"),
                messages=[
                    # {"role": "system", "content": "You are a prompt optimization expert."}, # System prompt optional
                    {"role": "user", "content": prompt}
                ],
                temperature=float(self.model_config.get("temperature", 0.7)),
                max_tokens=int(self.model_config.get("max_tokens", 4000)),
                timeout=int(self.model_config.get("timeout", 180)),
                extra_body=self.model_config.get("extra_body")
            )

            
            content = response.choices[0].message.content.strip()
            # 清理可能的 <think> 标签 (DeepSeek R1 等)
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            # 清理可能的 markdown 代码块标记 (如果 LLM 包裹了代码块)
            if content.startswith("```") and content.endswith("```"):
                lines = content.split('\n')
                if len(lines) >= 2:
                    content = '\n'.join(lines[1:-1])
            return content.strip()
        except Exception as e:
            # Log error separately if possible, here we just return original prompt or re-raise
            print(f"LLM call failed in strategy: {e}")
            raise e

