"""
全局约束优化策略 - 强化提示词中的全局约束和限制条件

功能:
1. 分析并强化提示词中的全局约束条件
2. 添加缺失的边界条件和限制规则
3. 优化负面约束（Negative Constraints）的表述
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class GlobalConstraintOptimizationStrategy(BaseStrategy):
    """
    全局约束优化策略 - 强化提示词中的全局约束
    
    适用场景:
    - 提示词缺乏明确的约束条件
    - 模型频繁违反隐含的规则
    - 需要强化负面约束（禁止做什么）
    """
    
    name: str = "global_constraint_optimization"
    priority: int = 82
    description: str = "全局约束优化策略：强化提示词中的全局约束和限制条件"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当存在约束违反或规则不清晰时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查是否有约束相关的错误模式
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        
        # 检查是否存在规则违反类错误
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        if constraint_violations > 0:
            return True
        
        # 检查提示词分析中是否缺乏约束
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        constraint_clarity: float = prompt_analysis.get("constraint_clarity", 1.0)
        
        return constraint_clarity < 0.7
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        约束问题越严重，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        
        # 约束违反越多，优先级越高
        if constraint_violations >= 10:
            return int(self.priority * 1.3)
        elif constraint_violations >= 5:
            return int(self.priority * 1.2)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用全局约束优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析当前约束问题
        constraint_analysis: str = self._analyze_constraints(errors, diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词的全局约束规则不够清晰或完整，需要设定通用识别红线和统一判断标准。

## 约束问题分析

{constraint_analysis}

## 优化要求

请按照以下要点完善提示词的全局约束规则部分：

### 1. 明确位置（Module Order: 2）
- **先识别**原提示词中全局约束规则的具体位置。
- 本模块必须位于**角色与任务定义之后**（第2个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 上下文使用要求
- **必须结合历史对话补全语义**
- 不能仅依赖当前单条 query，需关联上下文理解完整意图
- 明确何时需要引用历史记录

### 3. 多意图处理规则
- **一句话含多个独立意图时需全部标注**
- 定义多意图的识别标准（如：包含"和"、"还有"等连接词）
- 说明多意图输出的优先级排序规则

### 4. 歧义处理规则
- **语义模糊时优先请求澄清，不强制归类**
- 定义触发澄清的条件（如：置信度低于阈值、关键信息缺失）
- 明确澄清话术的生成规范

### 5. 排除规则（无意图场景）
明确以下不属于业务意图的场景处理方式：
- **问候语**: "你好"、"在吗"等 → 标记为【无意图-问候】
- **闲聊**: "今天天气不错"等 → 标记为【无意图-闲聊】
- **恶意内容**: 辱骂、敏感信息 → 标记为【无意图-违规】
- **无效输入**: 乱码、纯符号 → 标记为【无意图-无效】

### 6. 格式要求 (Strict Mode)
- **严禁修改其他模块**: 你只能修改"全局约束规则"相关的内容。绝对禁止修改前面的角色定义或后面的Query预处理、意图定义等其他模块的内容。
- **允许新增模块**: 如果当前提示词中缺失本模块，请按照要求在规定的位置进行**新增**。
- 必须严格使用 `SEARCH/REPLACE` 格式输出修改内容。

- **重要限制**: SEARCH 块中的内容必须与原提示词**完全一致**（精确到空格和换行）。
- **禁止**: 不要修改 SEARCH 块中的任何字符，否则会导致匹配失败。

示例：
```text
<<<<<<< SEARCH
(原有的约束规则内容 - 必须逐字复制原文)
=======
(优化后的约束规则内容)
>>>>>>> REPLACE
```
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _analyze_constraints(
        self, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        分析当前约束问题
        
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 约束问题分析文本
        """
        lines: List[str] = []
        
        # 分析错误模式中的约束问题
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        constraint_violations: int = error_patterns.get("constraint_violations", 0)
        
        if constraint_violations > 0:
            lines.append(f"- 检测到 {constraint_violations} 个约束违反案例")
        
        # 从错误案例中提取约束相关问题
        lines.append("")
        lines.append("### 典型约束违反案例")
        
        for e in errors[:5]:
            query: str = str(e.get('query', ''))[:100]
            target: str = e.get('target', '')
            output: str = e.get('output', '')
            lines.append(f"- 输入: {query}")
            lines.append(f"  预期: {target} | 实际: {output}")
        
        # 检查提示词中的约束清晰度
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        constraint_clarity: float = prompt_analysis.get("constraint_clarity", 1.0)
        
        if constraint_clarity < 0.7:
            lines.append("")
            lines.append(f"- 约束清晰度评分: {constraint_clarity:.2f} (低于阈值 0.7)")
        
        return "\n".join(lines) if lines else "暂无明显的约束问题"
