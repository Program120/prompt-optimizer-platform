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
## 约束条件 (保守优化模式)
1. 必须保留提示词原有的结构、语气和格式。
2. 目标是渐进式改进，而非重写。
3. 除非明确要求替换，否则保留所有现有的 few-shot 示例。
"""
        
        optimization_prompt = f"""你是一个提示词工程专家。
请根据提供的具体指令和错误案例优化以下提示词。

## 当前提示词
{prompt}

## 错误案例
{error_text}

## 优化指令
{instruction}
{constraint_text}

## 输出格式
1. **分析**：首先，逐步分析当前提示词和错误模式。识别根本原因并规划具体的改进措施。
2. **优化**：然后，输出用于应用更改的 Git Diff 块。

你必须使用 Search/Replace 块格式来修改提示词。
**严禁输出完整提示词**。仅输出修改的部分。

请严格遵守以下格式：
<<<<<<< SEARCH
[要从原始提示词中替换的确切文本]
=======
[用于替换的新文本]
>>>>>>>

SEARCH/REPLACE 规则：
1. SEARCH 块必须包含与“当前提示词”完全一致的文本，包括空格和换行符。
2. 如果要插入文本，请 SEARCH 相邻的行，并在 REPLACE 中包含它以及你的新文本。
3. 要删除文本，请将 REPLACE 块留空（但保留行结构以便于定位）。
"""
        response_content = self._call_llm(optimization_prompt)
        # Log raw output for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"策略元优化 - 原始模型输出:\n{response_content}")
        
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

