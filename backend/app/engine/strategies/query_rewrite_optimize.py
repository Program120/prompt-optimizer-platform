"""
Query 改写优化策略 - 优化用户查询的改写逻辑

功能:
1. 分析并优化提示词中的 Query 改写规则
2. 添加口语化表达到标准术语的映射
3. 强化模糊查询的处理逻辑
"""
from typing import List, Dict, Any
from .base import BaseStrategy


class QueryRewriteOptimizationStrategy(BaseStrategy):
    """
    Query 改写优化策略 - 优化用户查询的改写逻辑
    
    适用场景:
    - 用户使用口语化表达导致误分类
    - 需要添加术语映射规则
    - 模糊查询处理不当
    """
    
    name: str = "query_rewrite_optimization"
    priority: int = 78
    description: str = "Query改写优化策略：优化用户查询的改写和标准化逻辑"
    module_name: str = "Query 预处理"
    
    def is_applicable(self, diagnosis: Dict[str, Any]) -> bool:
        """
        判断策略是否适用
        
        当存在查询改写相关问题时适用
        
        :param diagnosis: 诊断分析结果
        :return: 是否适用
        """
        # 检查是否有口语化表达导致的错误
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        
        # 检查是否存在术语相关错误
        # terminology_errors 现在是 List[Dict]
        terminology_errors: List[Dict] = error_patterns.get("terminology_errors", [])
        if len(terminology_errors) > 0:
            return True
        
        # 检查是否有模糊查询问题
        # ambiguous_queries 现在是 List[Dict]
        ambiguous_queries: List[Dict] = error_patterns.get("ambiguous_queries", [])
        if len(ambiguous_queries) > 3:
            return True
        
        # 检查高级诊断中的上下文分析
        advanced_diagnosis: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        context_analysis: Dict[str, Any] = advanced_diagnosis.get("context_analysis", {})
        
        return context_analysis.get("has_issue", False)
    
    def get_priority(self, diagnosis: Dict[str, Any]) -> int:
        """
        根据诊断结果动态计算优先级
        
        查询改写问题越严重，优先级越高
        
        :param diagnosis: 诊断分析结果
        :return: 动态计算的优先级
        """
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        terminology_errors: List[Dict] = error_patterns.get("terminology_errors", [])
        ambiguous_queries: List[Dict] = error_patterns.get("ambiguous_queries", [])
        
        total_issues: int = len(terminology_errors) + len(ambiguous_queries)
        
        if total_issues >= 10:
            return int(self.priority * 1.3)
        elif total_issues >= 5:
            return int(self.priority * 1.2)
            
        return self.priority
    
    def apply(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        应用 Query 改写优化策略
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 优化后的提示词
        """
        # 分析查询改写问题
        query_analysis: str = self._analyze_query_issues(errors, diagnosis)
        
        # 构造优化指令
        instruction: str = f"""当前提示词在 Query 改写方面存在不足，需要统一输入口径，消除口语化和黑话干扰。

## Query 改写问题分析

{query_analysis}

## 优化要求

请按照以下要点完善提示词的 Query 改写规则部分：

### 1. 明确位置（Module Order: 3）
- **先识别**原提示词中 Query 改写规则的具体位置。
- 本模块必须位于**全局约束规则之后**（第3个模块）。如果不在此位置，请将其移动到正确位置。

### 2. 黑话标准化转换
在提示词中嵌入行业黑话对照表，将黑话转为通用表述：
- **电商示例**:
  - "炸单" → "订单超售"
  - "砍一刀" → "邀请好友助力减免"
  - "白嫖" → "免费获取/薅羊毛"
  - "上车" → "参与团购/拼单"
- **金融示例**:
  - "米" → "资金/钱"
  - "白条" → "信用支付产品"
  - "花呗" → "蚂蚁花呗"

### 3. 错别字修正
识别并修正常见的输入错误：
- "推款" → "退款"
- "帐号" → "账号"
- "登陆" → "登录"
- "取消订阅" → 判断是"取消订单"还是"取消订阅服务"

### 4. 省略句补全
补充口语中缺失的成分，使语义完整：
- "能退吗" → "能对我购买的商品申请退款吗"
- "多久到" → "我的订单物流预计多久能到达"
- "怎么改" → "如何修改我的[订单/地址/信息]"

### 5. 预处理流程
明确 Query 改写的标准流程：
1. **Step 1**: 检测并转换黑话/俚语
2. **Step 2**: 修正明显的错别字
3. **Step 3**: 补全省略的主语/宾语
4. **Step 4**: 输出标准化后的 Query 用于后续意图识别

"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis,
            module_name=self.module_name
        )
    
    def _analyze_query_issues(
        self, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any]
    ) -> str:
        """
        分析查询改写相关问题
        
        :param errors: 错误样例列表
        :param diagnosis: 诊断分析结果
        :return: 查询问题分析文本
        """
        lines: List[str] = []
        
        # 分析错误案例中的查询问题
        lines.append("### 查询相关错误案例")
        
        query_issues: List[Dict[str, Any]] = []
        
        for e in errors:
            query: str = str(e.get('query', ''))
            target: str = e.get('target', '')
            output: str = e.get('output', '')
            
            # 检测可能的口语化问题
            if self._is_colloquial_query(query):
                query_issues.append({
                    "query": query,
                    "target": target,
                    "output": output,
                    "issue_type": "口语化表达"
                })
            # 检测模糊查询
            elif self._is_ambiguous_query(query):
                query_issues.append({
                    "query": query,
                    "target": target,
                    "output": output,
                    "issue_type": "模糊查询"
                })
        
        # 输出问题案例
        for issue in query_issues[:10]:
            lines.append(f"- **{issue['issue_type']}**")
            lines.append(f"  输入: {issue['query'][:80]}")
            lines.append(f"  预期: {issue['target']} | 实际: {issue['output']}")
        
        if not query_issues:
            # 如果没有明确识别到问题，输出所有错误案例供分析
            lines.append("以下错误案例可能涉及查询改写问题：")
            for e in errors[:5]:
                query: str = str(e.get('query', ''))[:100]
                target: str = e.get('target', '')
                output: str = e.get('output', '')
                lines.append(f"- 输入: {query}")
                lines.append(f"  预期: {target} | 实际: {output}")
        
        # 添加上下文分析结果
        advanced_diagnosis: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        context_analysis: Dict[str, Any] = advanced_diagnosis.get("context_analysis", {})
        
        if context_analysis.get("has_issue"):
            lines.append("")
            lines.append("### 上下文指代问题")
            ref_error_ratio: float = context_analysis.get("referential_error_ratio", 0)
            lines.append(f"- 指代错误率: {ref_error_ratio:.1%}")
        
        return "\n".join(lines) if lines else "暂无明显的查询改写问题"
    
    def _is_colloquial_query(self, query: str) -> bool:
        """
        检测查询是否为口语化表达
        
        :param query: 用户查询
        :return: 是否为口语化
        """
        # 常见的口语化标记
        colloquial_markers: List[str] = [
            "米", "块", "咋", "啥", "咋样", "咋办", "搞", "弄",
            "行不行", "能不能", "可以不", "好使"
        ]
        
        for marker in colloquial_markers:
            if marker in query:
                return True
        return False
    
    def _is_ambiguous_query(self, query: str) -> bool:
        """
        检测查询是否为模糊查询
        
        :param query: 用户查询
        :return: 是否为模糊查询
        """
        # 仅包含时间词但缺少业务关键词
        time_words: List[str] = [
            "今年", "去年", "最近", "这个月", "上个月", "这周",
            "明天", "昨天", "现在"
        ]
        
        # 检查是否仅有时间词
        has_time_word: bool = any(tw in query for tw in time_words)
        
        # 如果查询很短且只有时间词，认为是模糊查询
        if has_time_word and len(query) < 10:
            return True
            
        return False
