"""
上下文与指代处理优化策略

针对指代消解错误和上下文依赖丢失，增加显式指令和示例。
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class ContextEnhancementStrategy(BaseStrategy):
    """
    上下文增强策略
    
    针对指代消解错误和上下文依赖丢失，增加显式指令和示例。
    对应模块5：上下文与指代处理规则
    """
    
    name: str = "context_enhancement"
    priority: int = 85
    description: str = "上下文增强策略：解决多轮对话中的语义断裂和指代消解问题"
        
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        return adv_diag.get("context_analysis", {}).get("has_issue", False)

    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        获取策略优先级
        
        :param diagnosis: 诊断分析结果
        :return: 优先级分数
        """
        return 85

    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用上下文增强策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 获取高级诊断结果
        adv_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        ctx_analysis: Dict[str, Any] = adv_diag.get("context_analysis", {})
        
        # 获取指代相关的错误案例
        referential_cases: List[Dict[str, Any]] = ctx_analysis.get("sample_cases", [])
        if not referential_cases:
            # 如果没有找到特定的指代案例，使用通用错误案例
            referential_cases = errors[:3]
            
        # 构建优化指令
        optimization_instruction: str = """当前提示词在处理上下文依赖和指代消解方面存在不足，需要完善多轮对话的语义补全能力。

## 优化要求

请按照以下要点完善提示词的上下文与指代处理规则部分：

### 1. 明确位置（Module Order: 5）
- **先识别**原提示词中上下文与指代处理规则的具体位置。
- 本模块必须位于**意图体系定义之后**（第5个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 上下文补全规则
当预处理后的 query 仍不完整时，需结合历史对话补全语义：
- **补全时机**: 当前 query 缺少主语/宾语/关键信息时
- **补全来源**: 优先从最近 3 轮对话中寻找相关信息
- **补全示例**:
  - 历史: "我买的那个蓝牙耳机" → 当前: "能退吗" → 补全后: "我买的蓝牙耳机能退吗"

### 3. 指代解析规则
针对代词（它/这个/那个/上面说的），明确指代对象的判断方法：
- **指代词列表**: 它、这个、那个、这件、那件、刚才说的、上面的、前面提到的
- **解析优先级**: 
  1. 最近一轮提到的实体
  2. 对话主题相关的核心实体
  3. 无法确定时请求澄清

### 4. 示例佐证
添加具体案例强化模型对规则的理解：

**案例 1 - 指代消解**:
- 用户轮1: "我想看看那个199的充电宝"
- 用户轮2: "这个有货吗"
- 解析: "这个" 指代 "199的充电宝"
- 输出意图: 【查询库存】

**案例 2 - 上下文补全**:
- 用户轮1: "帮我查下订单"
- 系统: "您有3个订单，请问查哪个？"
- 用户轮2: "第二个"
- 补全后: "查询第二个订单的详情"

### 5. 格式要求 (Strict Mode)
- **严禁修改其他模块**: 你只能修改"上下文与指代处理规则"相关的内容。绝对禁止修改前面的意图定义或后面的自定义数据等其他模块的内容。
- **允许新增模块**: 如果当前提示词中缺失本模块，请按照要求在规定的位置进行**新增**。
- 必须严格使用 `SEARCH/REPLACE` 格式输出修改内容。

- **重要限制**: SEARCH 块中的内容必须与原提示词**完全一致**（精确到空格和换行）。
- **禁止**: 不要修改 SEARCH 块中的任何字符，否则会导致匹配失败。

示例：
```text
<<<<<<< SEARCH
(原有的上下文规则内容 - 必须逐字复制原文)
=======
(优化后的上下文规则内容)
>>>>>>> REPLACE
```
"""
        
        return self._meta_optimize(
            prompt, referential_cases, optimization_instruction, diagnosis=diagnosis
        )
