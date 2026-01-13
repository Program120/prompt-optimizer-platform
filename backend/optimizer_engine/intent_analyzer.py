"""
意图分析器模块 - 分析失败意图及其错误模式

功能：
1. 按意图统计错误率
2. 识别 Top N 失败意图
3. 对失败意图进行 LLM 深度分析
4. 生成可注入优化提示词的分析上下文
"""
import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict


class IntentAnalyzer:
    """
    意图分析器 - 分析失败意图及其错误模式
    
    提供：
    - 按意图统计错误率
    - Top N 失败意图识别
    - LLM 深度分析失败意图
    - 格式化分析结果用于优化提示词
    """
    
    # 深度分析提示词模板
    DEEP_ANALYSIS_PROMPT: str = """你是一个意图分类错误分析专家。请分析以下失败意图的错误模式。

## 失败意图: {intent_name}
- 总错误数: {error_count}
- 错误率: {error_rate:.1%}

## 典型错误案例
{error_samples}

## 主要混淆目标
{confusion_targets}

请分析：
1. 这些错误的共同特征是什么？
2. 为什么模型会将这些输入错误分类？
3. 提供 2-3 条针对性的改进建议

请用简洁的文字回答，不要超过 200 字。"""

    def __init__(
        self, 
        llm_client: Any = None, 
        model_config: Dict[str, Any] = None
    ):
        """
        初始化意图分析器
        
        :param llm_client: LLM 客户端实例
        :param model_config: 模型配置
        """
        self.llm_client = llm_client
        self.model_config: Dict[str, Any] = model_config or {}
        self.logger: logging.Logger = logging.getLogger(__name__)
        
    def analyze_errors_by_intent(
        self,
        errors: List[Dict[str, Any]],
        total_count: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        按意图统计错误
        
        :param errors: 错误样例列表，每个样例包含 query, target, output
        :param total_count: 总样本数（用于计算错误率）
        :return: 按意图分组的错误分析
        """
        if not errors:
            return {
                "total_errors": 0,
                "intent_errors": {},
                "top_failing_intents": [],
                "error_rate_by_intent": {}
            }
            
        # 统计每个意图的错误数量
        intent_error_counts: Counter = Counter()
        intent_errors: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        
        # 统计每个意图的混淆目标
        intent_confusion: Dict[str, Counter] = defaultdict(Counter)
        
        for err in errors:
            target: str = str(err.get("target", "")).strip()
            output: str = str(err.get("output", "")).strip()
            
            if target:
                intent_error_counts[target] += 1
                intent_errors[target].append(err)
                
                # 记录混淆目标
                if output and output != target:
                    intent_confusion[target][output] += 1
                    
        # 计算每个意图的错误率
        # 如果没有提供总数，使用错误数的两倍作为估算
        total: int = total_count or len(errors) * 2
        
        error_rate_by_intent: Dict[str, float] = {}
        for intent, count in intent_error_counts.items():
            # 这里假设每个意图的样本数大致相等
            # 更准确的做法需要知道每个意图的总样本数
            error_rate_by_intent[intent] = count / total
            
        # 按错误数量排序，获取 Top 失败意图
        top_failing: List[Tuple[str, int]] = intent_error_counts.most_common(10)
        
        # 构建 Top 失败意图详情
        top_failing_intents: List[Dict[str, Any]] = []
        for intent, count in top_failing:
            # 获取该意图的主要混淆目标
            confusion_targets: List[Tuple[str, int]] = (
                intent_confusion[intent].most_common(3)
            )
            
            top_failing_intents.append({
                "intent": intent,
                "error_count": count,
                "error_rate": error_rate_by_intent.get(intent, 0),
                "confusion_targets": [
                    {"target": t, "count": c} for t, c in confusion_targets
                ],
                "sample_errors": intent_errors[intent][:5]
            })
            
        return {
            "total_errors": len(errors),
            "total_count": total,
            "intent_errors": {
                k: len(v) for k, v in intent_errors.items()
            },
            "top_failing_intents": top_failing_intents,
            "error_rate_by_intent": error_rate_by_intent
        }
        
    async def deep_analyze_top_failures(
        self,
        errors: List[Dict[str, Any]],
        top_n: int = 3
    ) -> Dict[str, Any]:
        """
        对 Top N 失败意图进行 LLM 深度分析
        
        :param errors: 错误样例列表
        :param top_n: 分析的失败意图数量
        :return: 深度分析结果
        """
        if not errors:
            return {"analyses": [], "summary": "无错误数据"}
            
        if not self.llm_client:
            self.logger.warning("未配置 LLM 客户端，跳过深度分析")
            return {"analyses": [], "summary": "未配置 LLM 客户端"}
            
        # 先进行基础分析
        intent_analysis: Dict[str, Any] = self.analyze_errors_by_intent(errors)
        top_failures: List[Dict[str, Any]] = (
            intent_analysis.get("top_failing_intents", [])[:top_n]
        )
        
        if not top_failures:
            return {"analyses": [], "summary": "无失败意图"}
            
        # 并行分析每个 Top 失败意图
        analyses: List[Dict[str, Any]] = []
        total_count: int = intent_analysis.get("total_count", len(errors))
        
        for failure in top_failures:
            intent: str = failure.get("intent", "")
            error_count: int = failure.get("error_count", 0)
            sample_errors: List[Dict[str, Any]] = failure.get("sample_errors", [])
            confusion_targets: List[Dict[str, Any]] = failure.get(
                "confusion_targets", []
            )
            
            # 构建错误样例文本
            error_samples_text: str = self._format_error_samples(sample_errors)
            
            # 构建混淆目标文本
            confusion_text: str = ", ".join([
                f"{ct['target']}({ct['count']}次)" 
                for ct in confusion_targets
            ]) if confusion_targets else "无明显混淆目标"
            
            # 计算错误率
            error_rate: float = error_count / total_count if total_count > 0 else 0
            
            # 构建分析提示词
            prompt: str = self.DEEP_ANALYSIS_PROMPT.format(
                intent_name=intent,
                error_count=error_count,
                error_rate=error_rate,
                error_samples=error_samples_text,
                confusion_targets=confusion_text
            )
            
            # 调用 LLM 分析
            try:
                analysis_result: str = await self._call_llm_async(prompt)
                analyses.append({
                    "intent": intent,
                    "error_count": error_count,
                    "error_rate": error_rate,
                    "confusion_targets": confusion_targets,
                    "analysis": analysis_result
                })
            except Exception as e:
                self.logger.error(f"深度分析意图 {intent} 失败: {e}")
                analyses.append({
                    "intent": intent,
                    "error_count": error_count,
                    "error_rate": error_rate,
                    "confusion_targets": confusion_targets,
                    "analysis": f"分析失败: {str(e)}"
                })
                
        # 生成整体总结
        summary: str = self._generate_overall_summary(analyses)
        
        return {
            "analyses": analyses,
            "summary": summary,
            "analyzed_count": len(analyses)
        }
        
    def _format_error_samples(
        self, 
        errors: List[Dict[str, Any]], 
        max_samples: int = 5
    ) -> str:
        """
        格式化错误样例
        
        :param errors: 错误样例列表
        :param max_samples: 最大样例数
        :return: 格式化的错误样例文本
        """
        lines: List[str] = []
        for err in errors[:max_samples]:
            query: str = str(err.get("query", ""))[:80]
            target: str = str(err.get("target", ""))
            output: str = str(err.get("output", ""))
            lines.append(f"- 输入: {query}")
            lines.append(f"  预期: {target} | 实际: {output}")
        return "\n".join(lines) if lines else "无错误样例"
        
    def _generate_overall_summary(
        self, 
        analyses: List[Dict[str, Any]]
    ) -> str:
        """
        生成整体分析总结
        
        :param analyses: 各意图的分析结果
        :return: 整体总结文本
        """
        if not analyses:
            return "无分析数据"
            
        lines: List[str] = [f"共分析了 {len(analyses)} 个高失败率意图："]
        
        for idx, analysis in enumerate(analyses, 1):
            intent: str = analysis.get("intent", "")
            error_count: int = analysis.get("error_count", 0)
            error_rate: float = analysis.get("error_rate", 0)
            lines.append(
                f"{idx}. {intent}: {error_count}个错误 ({error_rate:.1%})"
            )
            
        return "\n".join(lines)
        
    async def _call_llm_async(self, prompt: str) -> str:
        """
        异步调用 LLM
        
        :param prompt: 提示词
        :return: LLM 响应内容
        """
        loop = asyncio.get_event_loop()
        
        def run_sync() -> str:
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model_config.get("model_name", "gpt-3.5-turbo"),
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are an intent classification error analyst."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500,
                    timeout=int(self.model_config.get("timeout", 60)),
                    extra_body=self.model_config.get("extra_body")
                )
                content: str = response.choices[0].message.content.strip()
                # 处理思考模型的 <think> 标签
                content = re.sub(
                    r'<think>.*?</think>', 
                    '', 
                    content, 
                    flags=re.DOTALL
                ).strip()
                return content
            except Exception as e:
                self.logger.error(f"LLM 调用失败: {e}")
                raise e
                
        return await loop.run_in_executor(None, run_sync)
        
    def generate_analysis_context(
        self,
        intent_analysis: Dict[str, Any],
        deep_analysis: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成可注入优化提示词的分析上下文
        
        :param intent_analysis: 意图分析结果
        :param deep_analysis: 深度分析结果（可选）
        :return: 格式化的分析上下文文本
        """
        lines: List[str] = []
        
        # 意图错误率分析
        lines.append("### 按意图错误分布")
        top_failures: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )[:5]
        
        if top_failures:
            lines.append("| 意图 | 错误数 | 错误率 | 主要混淆目标 |")
            lines.append("| :--- | :---: | :---: | :--- |")
            
            for failure in top_failures:
                intent: str = failure.get("intent", "")
                error_count: int = failure.get("error_count", 0)
                error_rate: float = failure.get("error_rate", 0)
                confusion_targets: List[Dict[str, Any]] = failure.get(
                    "confusion_targets", []
                )
                confusion_str: str = ", ".join([
                    ct["target"] for ct in confusion_targets[:2]
                ]) if confusion_targets else "-"
                
                lines.append(
                    f"| {intent} | {error_count} | {error_rate:.1%} | {confusion_str} |"
                )
        else:
            lines.append("无明显失败意图")
            
        lines.append("")
        
        # 深度分析结果
        if deep_analysis and deep_analysis.get("analyses"):
            lines.append("### Top 失败意图深度分析")
            
            for analysis in deep_analysis.get("analyses", []):
                intent: str = analysis.get("intent", "")
                analysis_text: str = analysis.get("analysis", "")
                
                lines.append(f"#### {intent}")
                # 截断过长的分析
                if len(analysis_text) > 300:
                    analysis_text = analysis_text[:300] + "..."
                lines.append(analysis_text)
                lines.append("")
                
        return "\n".join(lines)
