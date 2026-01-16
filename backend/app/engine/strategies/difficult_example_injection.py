"""困难案例注入策略 - 将困难案例注入到few-shot示例中"""

from loguru import logger
from typing import List, Dict, Any
from .base import BaseStrategy




class DifficultExampleInjectionStrategy(BaseStrategy):
    """困难案例注入策略 - 将困难案例注入到few-shot示例中"""
    
    name: str = "difficult_example_injection"
    priority: int = 70
    description: str = "困难案例注入策略：将难处理的案例作为示例注入提示词"
    module_name: str = "Few-Shot 场景示例"
    
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
        logger.info(f"策略 {self.name} 开始执行...")
        hard_cases = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if not hard_cases:
            hard_cases = errors[:10]  # 如果没有识别到 hard_cases，使用前10个错误
        
        # 构建困难案例分析
        hard_cases_text = self._build_hard_cases_text(hard_cases[:10])
        
        # 从困难案例中提取示例（用于动态生成）
        example_cases_text = self._build_example_cases_from_errors(hard_cases[:4])
        
        # 构建优化指令（基于实际业务案例动态生成）
        optimization_instruction: str = f"""当前提示词的 Few-Shot 示例不够完善，需要覆盖全部识别场景。

## 困难案例分析
以下是模型难以正确处理的典型案例：
{hard_cases_text}

## 优化要求

请按照以下要点完善提示词的 Few-Shot 场景示例部分：

### 1. 明确位置（Module Order: 8）
- **先识别**原提示词中 Few-Shot 场景示例的具体位置（通常在「最终输出格式」之前）。
- 本模块必须位于**CoT 思维链引导之后、最终输出格式之前**。如果不在此位置，请将其移动到正确位置。

### 2. 格式一致性要求 (CRITICAL)
- **严禁**使用通用示例（如"查快递到哪了"、"我要退货"等与业务无关的示例）。
- **必须**分析"当前提示词"中定义的输出格式（例如：是 JSON 还是 XML？Key 是 "intent" 还是 "category"？是用 list 还是 string？）。
- 新增的示例**必须**与原提示词中现有的示例或输出要求保持**完全一致**的格式。

### 3. 基于实际业务场景生成示例
**必须参考以下实际业务案例来生成示例**（这些是从错误案例中提取的真实业务场景）：
{example_cases_text}

### 4. 示例类型覆盖要求
必须包含以下四类场景的示例：
1. **单意图示例**: 从上述业务案例中选择一个典型的单意图场景
2. **多意图示例**: 从上述业务案例中选择或构造一个多意图场景
3. **需要澄清示例**: 从上述业务案例中选择一个语义模糊需要澄清的场景
4. **无意图示例**: 构造一个与当前业务相关的闲聊/问候场景

### 5. 示例结构要求
每个示例必须包含（字段名称需适配原提示词）：
- Query（用户输入）
- 上下文（如有）
- 预处理结果（如有变化）
- 判断依据（简要说明分类逻辑）
- 输出结果（**必须符合原提示词定义的格式**）

### 6. 示例质量要求
- 示例必须贴合当前提示词的实际业务场景
- 优先使用上述困难案例作为示例素材
- 确保示例能够帮助模型理解正确的分类逻辑

"""
        
        # 使用通用元优化方法（获得知识库历史支持）
        return self._meta_optimize(
            prompt, hard_cases[:10], optimization_instruction, 
            conservative=True, diagnosis=diagnosis,
            module_name=self.module_name
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
    
    def _build_example_cases_from_errors(self, cases: List[Dict[str, Any]]) -> str:
        """
        从实际错误案例中构建示例文本，供 LLM 参考生成业务相关的 Few-Shot 示例
        
        :param cases: 错误案例列表
        :return: 格式化的示例文本
        """
        if not cases:
            return "暂无实际业务案例可供参考"
        
        lines = []
        for i, case in enumerate(cases, 1):
            query = str(case.get('query', ''))[:200]
            target = case.get('target', '')
            output = case.get('output', '')
            
            lines.append(f"#### 业务案例 {i}")
            lines.append(f"- **用户输入**: {query}")
            lines.append(f"- **正确意图**: {target}")
            lines.append(f"- **模型误判**: {output}")
            lines.append("")
        
        return "\n".join(lines)

