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
        基于特定指令进行元优化的通用方法 (Git Diff Mode)
        """
        error_text = self._build_error_samples(error_cases)
        
        constraint_text = ""
        if conservative:
            constraint_text = """
## Constraints (Conservative Optimization)
1. You MUST maintain the original structure, tone, and formatting of the prompt.
2. The goal is incremental improvement.
3. Keep all existing few-shot examples unless explicitly asked to replace them.
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
1. **Analysis**: First, analyze the current prompt and error patterns step-by-step. Identify the root causes and plan specific improvements.
2. **Optimization**: Then, output the Git Diff blocks to apply the changes.

You MUST use the Search/Replace block format to modify the prompt. 
Do NOT output the full prompt. Only output the modified sections.

Use this format:
<<<<<<< SEARCH
[Exact text to be replaced from the original prompt]
=======
[New text to replace with]
>>>>>>>

Rules for SEARCH/REPLACE:
1. The SEARCH block must obtain EXACTLY the text from the "Current Prompt", including whitespace and newlines.
2. If you want to insert text, SEARCH for the adjacent line and include it in REPLACE with your new text.
3. To delete text, leave the REPLACE block empty (but keep the line structure).
"""
        response_content = self._call_llm(optimization_prompt)
        
        # 应用 Diff
        try:
            new_prompt = self._apply_diff(prompt, response_content)
            # 如果没有检测到任何 Diff 块但内容很长，可能是模型回退到了全量输出
            if new_prompt == prompt and len(response_content) > len(prompt) * 0.8:
                # 简单的启发式检查：如果 Output 也是一个完整 Prompt
                return response_content
            return new_prompt
        except Exception as e:
            print(f"Diff 应用失败: {e}。回退到原始提示词。")
            # 可以在这里做 retry logic，请求全量输出
            # 暂时返回原 Prompt (或者我们可以考虑抛出异常让上层处理)
            return prompt

    def _apply_diff(self, original_text: str, diff_text: str) -> str:
        """应用 SEARCH/REPLACE Diff"""
        import re
        
        # 正则匹配 SEARCH/REPLACE 块
        pattern = re.compile(
            r'<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>>',
            re.DOTALL
        )
        
        blocks = pattern.findall(diff_text)
        if not blocks:
            # 尝试宽松匹配 (允许 SEARCH 后没有换行等)
            pattern_loose = re.compile(
                r'<<<<<<< SEARCH\s*(.*?)\s*=======\s*(.*?)\s*>>>>>>>',
                re.DOTALL
            )
            blocks = pattern_loose.findall(diff_text)
            
        current_text = original_text
        applied_count = 0
        
        for search_block, replace_block in blocks:
            # 尝试定位 search_block
            # 1. 精确匹配
            if search_block in current_text:
                current_text = current_text.replace(search_block, replace_block, 1)
                applied_count += 1
                continue
                
            # 2. 尝试去除首尾空白匹配
            s_stripped = search_block.strip()
            if s_stripped and s_stripped in current_text:
                 current_text = current_text.replace(s_stripped, replace_block.strip(), 1)
                 applied_count += 1
                 continue
                 
            # 3. 失败，记录日志 (实际生产中应该更鲁棒，这里简化)
            print(f"警告：找不到匹配的文本块：{s_stripped[:20]}...")
            
        return current_text

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
            print(f"策略中的 LLM 调用失败：{e}")
            raise e

