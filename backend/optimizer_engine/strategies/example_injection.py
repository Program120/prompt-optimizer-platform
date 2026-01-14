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
        
        # 构建优化指令（替代原来直接调用 _call_llm）
        optimization_instruction: str = f"""当前提示词的 Few-Shot 示例不够完善，需要覆盖全部识别场景。

## 困难案例分析
以下是模型难以正确处理的典型案例：
{hard_cases_text}

## 优化要求

请按照以下要点完善提示词的 Few-Shot 场景示例部分：

### 1. 明确位置（Module Order: 8）
- **先识别**原提示词中 Few-Shot 场景示例的具体位置。
- 本模块必须位于**CoT 思维链引导之后**（第8个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 示例类型覆盖
必须包含以下四类场景的示例，缺一不可：

**单意图示例**:
- Query: "我想查一下昨天买的手机壳到哪了"
- 上下文: 无
- 预处理: 补全 → "查询昨天购买的手机壳的物流状态"
- 判断依据: 包含"查"+"到哪了"，明确为物流查询
- 输出: {{"intent": ["查询物流"], "confidence": 0.95}}

**多意图示例**:
- Query: "我要退货，顺便问下运费险怎么用"
- 预处理: 无需预处理
- 判断依据: 包含"退货"和"运费险"两个独立诉求
- 输出: {{"intent": ["申请退货", "咨询运费险"], "confidence": 0.88}}

**需要澄清示例**:
- Query: "那个东西能退吗"
- 上下文: 无
- 预处理: 无法补全，缺少指代对象
- 判断依据: "那个东西"指代不明，需要澄清
- 输出: {{"intent": [], "confidence": 0.0, "clarify": "请问您说的是哪个商品呢？"}}

**无意图示例**:
- Query: "你好呀"
- 判断依据: 问候语，不属于业务意图
- 输出: {{"intent": ["无意图"], "confidence": 0.99}}

### 3. 示例结构要求
每个示例必须包含：
- Query（用户输入）
- 上下文（如有）
- 预处理结果（如有变化）
- 判断依据（简要说明）
- 输出结果（标准JSON格式）

### 4. 示例质量要求
- 示例需贴合实际业务场景
- 避免极端或罕见场景
- 优先选择边界案例作为示例

### 5. 格式要求
- 必须严格使用 `SEARCH/REPLACE` 格式输出修改内容。

示例：
```text
<<<<<<< SEARCH
(原有的示例内容)
=======
(优化后的示例内容)
>>>>>>> REPLACE
```
"""
        
        # 使用通用元优化方法（获得知识库历史支持）
        return self._meta_optimize(
            prompt, hard_cases[:10], optimization_instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _build_hard_cases_text(self, hard_cases: List[Dict[str, Any]]) -> str:
        """构建困难案例文本"""
        lines = []
        for i, case in enumerate(hard_cases, 1):
            lines.append(f"\n### 案例 {i}")
            lines.append(f"输入: {str(case.get('query', ''))[:150]}")
            lines.append(f"正确分类: {case.get('target', '')}")
            lines.append(f"模型错误输出: {case.get('output', '')}")
        
        return "\n".join(lines)
    

