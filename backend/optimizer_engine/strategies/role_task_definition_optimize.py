"""
角色与任务定义优化策略 - 明确模型身份与任务边界

功能:
1. 明确模型的专家身份定位（如 "电商售后意图识别专家"）
2. 划定任务边界（仅识别意图，不回答业务问题）
3. 点明支持的场景（单意图/多意图/澄清/无意图）
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class RoleTaskDefinitionStrategy(BaseStrategy):
    """
    角色与任务定义优化策略 - 明确模型身份与任务边界
    
    适用场景:
    - 提示词缺乏明确的角色定位
    - 模型输出超出意图识别边界（如直接回答业务问题）
    - 支持场景定义不清晰
    """
    
    name: str = "role_task_definition"
    priority: int = 95
    description: str = "角色与任务定义优化策略：明确模型身份、识别边界与场景范围"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当提示词缺乏角色定义或任务边界不清时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查提示词分析中是否缺乏角色定义
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_role_definition: bool = prompt_analysis.get("has_role_definition", True)
        
        if not has_role_definition:
            return True
        
        # 检查是否有任务边界问题（模型输出超范围）
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        # boundary_violations 现在是 List[Dict]
        boundary_violations: List[Dict] = error_patterns.get("boundary_violations", [])
        
        if len(boundary_violations) > 0:
            return True
        
        # 检查是否有场景覆盖不全的问题
        # scene_coverage 现在是 Dict
        scene_coverage: Dict[str, Any] = prompt_analysis.get("scene_coverage", {})
        coverage_score: float = scene_coverage.get("score", 1.0)
        
        return coverage_score < 0.8
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        角色定义是提示词的基础，优先级最高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        prompt_analysis: Dict[str, Any] = diagnosis.get("prompt_analysis", {})
        has_role_definition: bool = prompt_analysis.get("has_role_definition", True)
        
        # 如果完全没有角色定义，给予最高优先级
        if not has_role_definition:
            return 100
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用角色与任务定义优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析当前角色定义问题
        role_analysis: str = self._analyze_role_issues(prompt, diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词的角色定义和任务边界不够清晰，需要进行优化。

## 角色定义问题分析

{role_analysis}

## 优化要求

请按照以下要点优化提示词的角色与任务定义部分：

### 1. 明确位置（Module Order: 1）
- **先识别**原提示词中角色与任务定义的具体位置。
- 本模块必须位于提示词的**最开头**（第1个模块）。如果不在此位置，请将其移动到开头。

### 2. 明确专家身份
- 定义模型的专业角色（例如："你是一个电商售后意图识别专家"）
- 说明该角色的专业能力和知识范围
- 强调角色的专注领域

### 3. 划定任务边界
- 明确核心任务：**仅负责识别用户意图**
- 明确禁止行为：**不直接回答业务问题、不提供解决方案建议**
- 说明输出范围：意图标签、置信度、必要时的澄清请求

### 4. 定义支持场景
- **单意图场景**: 用户表达清晰，仅有一个明确意图
- **多意图场景**: 用户一句话包含多个独立意图，需全部识别
- **澄清场景**: 用户表达模糊或信息不足，需要请求澄清
- **无意图场景**: 问候、闲聊、恶意内容等不属于业务意图的情况

### 5. 要求 (Strict Mode)
- **严禁修改其他模块**: 你只能修改"角色与任务定义"模块的内容。绝对禁止修改其他任何部分。
- **允许新增模块**: 如果当前提示词中缺失本模块，请按照要求在规定的位置进行**新增**。
- **禁止重复添加**: 输出前必须检查当前提示词是否已包含本模块内容，若已存在则只能修改，不能重复添加。

"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
        )
    
    def _analyze_role_issues(
        self, 
        prompt: str, 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        分析当前角色定义问题
        
        :param prompt: 当前提示词
        :param diagnosis: 诊断分析结果
        :return: 问题分析文本
        """
        lines: List[str] = []
        
        # 检查提示词中是否包含角色相关关键词
        role_keywords: List[str] = [
            "你是", "作为", "扮演", "你的角色", "专家", "助手",
            "You are", "As a", "Your role"
        ]
        has_role_keyword: bool = any(kw in prompt for kw in role_keywords)
        
        if not has_role_keyword:
            lines.append("- 提示词**缺少明确的角色定义**，未指定模型的身份和专业领域")
        
        # 检查是否包含任务边界关键词
        boundary_keywords: List[str] = [
            "仅", "只", "不要", "禁止", "不得", "边界",
            "only", "do not", "never", "boundary"
        ]
        has_boundary: bool = any(kw in prompt for kw in boundary_keywords)
        
        if not has_boundary:
            lines.append("- 提示词**缺少任务边界说明**，可能导致模型输出超出预期范围")
        
        # 检查是否定义了场景
        scene_keywords: List[str] = [
            "单意图", "多意图", "澄清", "无意图", "场景",
            "single intent", "multi intent", "clarification"
        ]
        has_scenes: bool = any(kw in prompt for kw in scene_keywords)
        
        if not has_scenes:
            lines.append("- 提示词**未明确定义支持的场景类型**（单意图/多意图/澄清/无意图）")
        
        # 从诊断结果中获取额外信息
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        # boundary_violations 现在是 List[Dict]
        boundary_violations: List[Dict] = error_patterns.get("boundary_violations", [])
        
        if len(boundary_violations) > 0:
            lines.append(f"- 检测到 **{len(boundary_violations)} 个任务边界违规案例**，模型输出超出了意图识别范围")
        
        if not lines:
            lines.append("- 当前角色定义基本完整，但可进一步清晰化和标准化")
        
        return "\n".join(lines)
