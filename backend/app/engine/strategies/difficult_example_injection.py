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
        """
        应用困难案例注入策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        logger.info(f"策略 {self.name} 开始执行...")
        hard_cases: List[Dict[str, Any]] = diagnosis.get("error_patterns", {}).get("hard_cases", [])
        if not hard_cases:
            # 如果没有识别到 hard_cases，使用前 5 个错误（减少数量避免膨胀）
            hard_cases = errors[:5]
        
        # 限制困难案例数量为 5 个，避免上下文过长和 few-shot 膨胀
        limited_hard_cases: List[Dict[str, Any]] = hard_cases[:3]
        
        # 构建困难案例分析（供 LLM 分析问题模式）
        hard_cases_text: str = self._build_hard_cases_text(limited_hard_cases)
        
        # 从困难案例中提取示例（最多 3 个，用于动态生成 Few-Shot）
        # 注意：这里直接使用 hard_cases 的前 3 个作为参考，避免重复数据
        example_cases_text: str = self._build_example_cases_from_errors(limited_hard_cases[:1])
        
        # 构建优化指令（基于实际业务案例动态生成）
        # 关键：明确限制新增示例数量为 1-3 个，防止膨胀
        optimization_instruction: str = f"""当前提示词的 Few-Shot 示例需要优化，重点是**保留现有示例，并精选添加新的困难案例示例**。

## 困难案例分析
以下是模型难以正确处理的典型案例（仅供分析，不要全部添加）：
{hard_cases_text}

## 优化要求

请按照以下**严格流程**完善提示词的 Few-Shot 场景示例部分：

### 第一步：识别并保留现有示例 (CRITICAL - 必须执行)
1. 仔细阅读原提示词，**完整识别**其中已有的所有 Few-Shot 示例
2. **必须100%保留**原有示例，不得删除或遗漏任何一个
3. 如原提示词没有示例部分，则跳过此步骤

### 第二步：精选添加困难案例示例
> **[核心约束]** 仅从困难案例中**精选 1-3 个最具代表性的案例**添加为 Few-Shot 示例
> **严禁**为每个困难案例都添加示例！选择最能覆盖核心错误模式的案例即可

选择标准：
- 优先选择能代表一类错误模式的案例（而非个例）
- 优先选择与现有示例互补的案例（避免重复覆盖同类场景）
- **直接使用原始 Query**，不做泛化

### 整合原则 (严禁重复)
- **严禁**删除原有的任何示例
- **严禁**新增独立的 "## Few-Shot 场景示例" 标题，必须**整合**到原提示词中已有的该部分
- **严禁**重复添加 "单意图示例"、"多意图示例" 等类型标签，如已有则在其下优化示例
- 如原提示词中没有该部分，则在正确位置**新增一个**（仅此一个）

### 格式一致性要求
- 新增的示例**必须**与原提示词中现有的示例或输出要求保持**完全一致**的格式

### 参考业务案例
以下是可供选择添加的业务案例（精选 1-3 个添加即可）：
{example_cases_text}

### 示例结构要求
生成的示例**必须**采用 **JSON 格式**：
```json
{{
  "examples": [
    {{
      "query": "原始用户输入",
      "intent": "意图名称",
      "reason": "简要原因（为什么是这个意图）"
    }}
  ]
}}
```

"""
        
        # 使用通用元优化方法（获得知识库历史支持）
        # 注意：传递 limited_hard_cases 而非原始 hard_cases，避免数据冗余
        return self._meta_optimize(
            prompt, limited_hard_cases, optimization_instruction, 
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
        构建困难案例 JSON 文本
        
        :param hard_cases: 困难案例列表
        :return: JSON 格式的案例文本
        """
        import json
        
        # 先进行去重
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(hard_cases)
        
        if not unique_cases:
            return "暂无困难案例"
        
        # 构建 JSON 格式案例列表
        cases_list: List[Dict[str, str]] = []
        
        for case in unique_cases:
            cases_list.append({
                "query": str(case.get('query', ''))[:100],
                "correct_intent": str(case.get('target', '')),
                "model_output": str(case.get('output', ''))[:50]
            })
        
        return json.dumps({"hard_cases": cases_list}, ensure_ascii=False, indent=2)
    
    def _build_example_cases_from_errors(self, cases: List[Dict[str, Any]]) -> str:
        """
        从实际错误案例中构建示例 JSON，供 LLM 参考生成业务相关的 Few-Shot 示例
        
        :param cases: 错误案例列表
        :return: JSON 格式的示例文本
        """
        import json
        
        # 先进行去重
        unique_cases: List[Dict[str, Any]] = self._deduplicate_cases(cases)
        
        if not unique_cases:
            return "暂无实际业务案例可供参考"
        
        # 构建 JSON 格式示例列表
        examples_list: List[Dict[str, str]] = []
        
        for case in unique_cases:
            examples_list.append({
                "query": str(case.get('query', ''))[:100],
                "correct_intent": str(case.get('target', '')),
                "wrong_output": str(case.get('output', ''))[:50]
            })
        
        return json.dumps({"reference_cases": examples_list}, ensure_ascii=False, indent=2)

