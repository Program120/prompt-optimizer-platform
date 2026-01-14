"""
CoT 推理优化策略 - 增强提示词的思维链逻辑
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class CoTReasoningStrategy(BaseStrategy):
    """思维链(CoT)优化策略 - 强化推理过程"""
    
    name: str = "cot_reasoning"
    priority: int = 85
    description: str = "CoT优化策略：添加或修复思维链推理步骤"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用。
        
        适用于:
        1. 尚未包含 CoT 关键词 (step-by-step, thinking, etc.)
        2. 或者是复杂任务 (prompt_complexity > 0.7) 且准确率不高
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        # 如果没有 CoT，强烈建议应用
        if not has_cot:
            return True
            
        # 如果有 CoT 但效果不好 (accuracy < 0.8)，可能需要修复逻辑
        accuracy: float = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        return accuracy < 0.8
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级。
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            return 95  # 缺失 CoT 时优先级极高
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用 CoT 优化。
        
        参数:
            prompt: 当前提示词内容
            errors: 错误样例列表
            diagnosis: 诊断结果字典
            
        返回:
            优化后的提示词
        """
        
        # 构造优化指令
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_cot: bool = prompt_analysis.get("has_cot", False)
        
        if not has_cot:
            instruction: str = """当前提示词缺乏 CoT 思维链引导，需要强制模型输出判断依据以提升可解释性。

## 优化要求

请按照以下要点添加 CoT 思维链引导部分：

### 1. 明确位置（Module Order: 7）
- **先识别**原提示词中 CoT 思维链引导的具体位置。
- 本模块必须位于**业务专属辅助数据之后**（第7个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 思维链结构
- **若当前提示词中无 `reason` ** 相关输出要求，直接按照第3点的推理步骤模板执行即可。

- **若当前提示词中包含 `reason`字段 ** 相关输出要求，在输出意图时，要求模型简短说明判断逻辑放入reason字段中：

### 3. 推理步骤模板
```
Step 1: 提取关键词 - 从用户query中识别核心业务词汇
Step 2: 上下文关联 - 结合对话历史补全语义
Step 3: 意图匹配 - 与意图体系定义进行比对
Step 4: 置信度评估 - 根据匹配程度给出置信度
Step 5: 输出结果 - 生成标准化JSON输出, (如果当前提示词是json字段, 允许可以修改当前提示词输出中json字段顺序, 不允许修改输出结构) 
```

### 4. 简洁原则
- 思维链描述需简洁，核心是「依据 → 结论」的关联
- 与意图体系的定义强关联，避免脱离业务场景
- 便于人工排查误判原因，后续优化意图规则

### 5. 格式要求 (Strict Mode)
- **严禁修改其他模块**: 你只能修改"CoT 思维链引导"相关的内容。绝对禁止修改前面的辅助数据或后面的Few-Shot示例等其他模块的内容。
- **允许新增模块**: 如果当前提示词中缺失本模块，请按照要求在规定的位置进行**新增**。
- 必须严格使用 `SEARCH/REPLACE` 格式输出修改内容。

- **重要限制**: SEARCH 块中的内容必须与原提示词**完全一致**（精确到空格和换行）。
- **禁止**: 不要修改 SEARCH 块中的任何字符，否则会导致匹配失败。

示例：
```text
<<<<<<< SEARCH
(原有的思维链内容 - 必须逐字复制原文)
=======
(优化后的思维链内容)
>>>>>>> REPLACE
```
"""
        else:
            instruction: str = """
当前提示词已有 CoT 但仍产生错误。推理逻辑可能存在缺陷或被跳过。
请找到现有的 "# Reasoning Steps" (或类似思维链章节)，并对其内容进行重写以增强稳健性。

具体要求：
1. 使用 SEARCH 块精确定位现有的思维链章节内容。
2. 在 REPLACE 块中提供改进后的推理步骤。
3. 改进方向：
   - 分析模型为何在提供的错误案例上失败。
   - 调整推理步骤以覆盖这些边缘情况。
   - 强制要求更严格地遵守逻辑步骤。
"""
            
        return self._meta_optimize(
            prompt, errors, instruction, conservative=True, diagnosis=diagnosis
        )
