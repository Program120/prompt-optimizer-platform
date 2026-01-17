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
        example_cases_text = self._build_example_cases_from_errors(hard_cases[:2])
        
        # 构建优化指令（基于实际业务案例动态生成）
        optimization_instruction: str = f"""当前提示词的 Few-Shot 示例需要优化，重点是**提升示例质量和泛化能力，而非增加数量**。

## 困难案例分析
以下是模型难以正确处理的典型案例：
{hard_cases_text}

## 优化要求

请按照以下要点完善提示词的 Few-Shot 场景示例部分：

### 1. 核心原则：质量 > 数量 (CRITICAL)
- **优先泛化整合**：如果新案例与现有示例场景相似，应**合并或替换**现有示例，使其更具代表性，而非新增示例。
- **避免无限膨胀**：新增示例前，先检查现有示例是否已覆盖类似场景，能复用则复用。
- **提升而非堆砌**：通过优化示例的表述和覆盖面来增强模型理解力，不要靠数量取胜。

### 2. 整合原则 (严禁重复)
- **严禁**新增独立的 "## Few-Shot 场景示例" 标题，必须**整合**到原提示词中已有的该部分。
- **严禁**重复添加 "单意图示例"、"多意图示例" 等类型标签，如已有则在其下优化示例。
- 如原提示词中没有该部分，则在正确位置**新增一个**（仅此一个）。

### 3. 泛化策略
- 分析困难案例的**共性特征**，将多个相似案例**抽象为一个泛化示例**。
- 示例的Query应具有**代表性**，能覆盖一类场景而非单一case。
- 如现有示例已能覆盖新案例的场景，可选择**不新增**，仅微调现有示例的表述。

### 4. 格式一致性要求
- **严禁**使用通用示例（如"查快递到哪了"等与业务无关的示例）。
- 新增的示例**必须**与原提示词中现有的示例或输出要求保持**完全一致**的格式。

### 5. 参考业务案例
以下是需要覆盖的实际业务场景（用于生成或优化示例）：
{example_cases_text}

### 6. 示例结构要求
每个示例只需包含：**泛化Query**（具有代表性，能覆盖一类场景） → 对应意图(**简短几个词语**) + 简要原因

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

