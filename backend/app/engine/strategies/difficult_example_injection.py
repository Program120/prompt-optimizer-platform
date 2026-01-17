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
每个示例只需包含：Query → 对应意图(**简短几个词语的总结**) + 简要原因

### 6. 示例质量要求
优先使用上述困难案例作为示例素材，确保示例能帮助模型理解正确的映射逻辑

"""
        
        # 使用通用元优化方法（获得知识库历史支持）
        return self._meta_optimize(
            prompt, hard_cases[:10], optimization_instruction, 
            conservative=True, diagnosis=diagnosis,
            module_name=self.module_name
        )
    
    def _deduplicate_cases(self, cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对案例列表进行去重，基于query字段
        
        :param cases: 原始案例列表
        :return: 去重后的案例列表
        """
        seen_queries: set = set()
        unique_cases: List[Dict[str, Any]] = []
        
        for case in cases:
            # 获取query并标准化（去除首尾空格）
            query: str = str(case.get('query', '')).strip()
            if query and query not in seen_queries:
                seen_queries.add(query)
                unique_cases.append(case)
        
        logger.debug(f"案例去重: 原始 {len(cases)} 个, 去重后 {len(unique_cases)} 个")
        return unique_cases
    
    def _build_hard_cases_text(self, hard_cases: List[Dict[str, Any]]) -> str:
        """
        构建困难案例表格文本
        
        :param hard_cases: 困难案例列表
        :return: Markdown表格格式的案例文本
        """
        # 先进行去重
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(hard_cases)
        
        if not unique_cases:
            return "暂无困难案例"
        
        # 构建Markdown表格
        lines: List[str] = [
            "| Query | 正确意图 | 模型误判 |",
            "|-------|---------|---------|"  
        ]
        
        for case in unique_cases:
            # 截断过长的query，保持表格可读性
            query: str = str(case.get('query', ''))[:100].replace('|', '\\|').replace('\n', ' ')
            target: str = str(case.get('target', '')).replace('|', '\\|')
            output: str = str(case.get('output', ''))[:50].replace('|', '\\|')
            lines.append(f"| {query} | {target} | {output} |")
        
        return "\n".join(lines)
    
    def _build_example_cases_from_errors(self, cases: List[Dict[str, Any]]) -> str:
        """
        从实际错误案例中构建示例表格，供 LLM 参考生成业务相关的 Few-Shot 示例
        
        :param cases: 错误案例列表
        :return: Markdown表格格式的示例文本
        """
        # 先进行去重
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(cases)
        
        if not unique_cases:
            return "暂无实际业务案例可供参考"
        
        # 构建Markdown表格
        lines: List[str] = [
            "| Query | 正确意图 | 误判原因 |",
            "|-------|---------|---------|"  
        ]
        
        for case in unique_cases:
            # 截断过长的query，保持表格可读性
            query: str = str(case.get('query', ''))[:100].replace('|', '\\|').replace('\n', ' ')
            target: str = str(case.get('target', '')).replace('|', '\\|')
            output: str = str(case.get('output', ''))[:50].replace('|', '\\|')
            lines.append(f"| {query} | {target} | 误判为: {output} |")
        
        return "\n".join(lines)

