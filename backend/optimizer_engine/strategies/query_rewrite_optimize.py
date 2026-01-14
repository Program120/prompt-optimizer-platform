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
        terminology_errors: int = error_patterns.get("terminology_errors", 0)
        if terminology_errors > 0:
            return True
        
        # 检查是否有模糊查询问题
        ambiguous_queries: int = error_patterns.get("ambiguous_queries", 0)
        if ambiguous_queries > 3:
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
        terminology_errors: int = error_patterns.get("terminology_errors", 0)
        ambiguous_queries: int = error_patterns.get("ambiguous_queries", 0)
        
        total_issues: int = terminology_errors + ambiguous_queries
        
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
        instruction: str = f"""当前提示词在处理用户查询的改写和标准化方面存在不足。

## Query 改写问题分析

{query_analysis}

## 优化要求

1. **术语映射**: 添加常见的口语化表达到标准术语的映射规则
   - 例如："米" → "资金/钱"
   - 例如："白条" → "京东白条"
   
2. **模糊查询处理**: 明确模糊查询（如只有时间词"今年"、"最近"等）的处理策略
   - 缺少业务关键词时应如何路由
   - 是否需要澄清

3. **标准化流程**: 在提示词中添加清晰的 Query 预处理步骤
   - 第一步：识别口语化表达
   - 第二步：转换为标准术语
   - 第三步：检查是否有歧义

4. **示例补充**: 添加典型的改写示例

请使用 SEARCH/REPLACE 格式输出修改内容。
"""
        
        return self._meta_optimize(
            prompt, errors, instruction, 
            conservative=True, diagnosis=diagnosis
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
