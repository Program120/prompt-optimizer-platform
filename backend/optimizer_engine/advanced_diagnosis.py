"""
高级诊断模块 - 提供定向的深度分析能力
包括：上下文处理、多意图识别、领域混淆矩阵、澄清机制分析
"""
import asyncio
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict

class AdvancedDiagnoser:
    """高级诊断器 - 执行深度定向分析"""
    
    def __init__(
        self, 
        llm_client: Any = None, 
        model_config: Dict[str, Any] = None
    ):
        self.llm_client = llm_client
        self.model_config = model_config or {}
        self.logger = logging.getLogger(__name__)

    async def run_all_diagnoses(
        self, 
        errors: List[Dict[str, Any]],
        intents: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """并行运行所有高级诊断"""
        if not errors:
            return {}
            
        dataset_intents = intents or self._extract_intents(errors)
        
        results = await asyncio.gather(
            self.analyze_context_capabilities(errors),
            self.analyze_multi_intent(errors),
            self.analyze_domain_confusion(errors, dataset_intents),
            self.analyze_clarification(errors),
            return_exceptions=True
        )
        
        # 处理异常结果
        final_results = {}
        keys = ["context_analysis", "multi_intent_analysis", "domain_analysis", "clarification_analysis"]
        
        for k, res in zip(keys, results):
            if isinstance(res, Exception):
                self.logger.error(f"高级诊断 {k} 失败: {res}")
                final_results[k] = {"error": str(res)}
            else:
                final_results[k] = res
                
        return final_results

    def _extract_intents(self, errors: List[Dict]) -> List[str]:
        """从错误集中提取所有出现的意图"""
        intents = set()
        for e in errors:
            val = str(e.get('target', '')).split(',') # 假设逗号分隔
            intents.update([v.strip() for v in val if v.strip()])
            
            val_out = str(e.get('output', '')).split(',')
            intents.update([v.strip() for v in val_out if v.strip()])
        return list(intents)

    # -------------------------------------------------------------------------
    # A. 上下文处理能力分析
    # -------------------------------------------------------------------------
    async def analyze_context_capabilities(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析上下文依赖导致的错误
        """
        # 1. 关键词过滤：包含指代词的 Query
        referential_keywords = ["这个", "那个", "它", "其", "这", "那", "these", "those", "it", "that", "this"]
        
        context_errors = []
        for err in errors:
            query = str(err.get('query', '')).lower()
            if any(k in query for k in referential_keywords):
                context_errors.append(err)
        
        if not context_errors:
            return {"has_issue": False, "message": "未发现明显的上下文指代错误"}
            
        # 2. 计算指代相关错误率 (相对于总错误)
        ratio = len(context_errors) / len(errors)
        
        # 3. 简单的 LLM 校验 (可选，如果只有少量)
        # 识别是否因为忽略上下文（如历史对话）而导致
        # 这里仅做统计，假设如果包含指代词且错了，很大可能是上下文问题
        
        return {
            "has_issue": ratio > 0.1, # 阈值：10% 的错误涉及指代
            "referential_error_count": len(context_errors),
            "referential_error_ratio": ratio,
            "sample_cases": context_errors[:3]
        }

    # -------------------------------------------------------------------------
    # B. 多意图识别能力分析
    # -------------------------------------------------------------------------
    async def analyze_multi_intent(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析多意图识别问题: 漏判、误判、排序错误
        """
        multi_intent_sep = [",", "，", "|", "&"] # 常见分隔符
        
        false_positive = 0 # 单意图 -> 多意图
        false_negative = 0 # 多意图 -> 单意图
        order_error = 0    # 意图正确但顺序错误
        
        mixed_errors = []
        
        for err in errors:
            target = str(err.get('target', ''))
            output = str(err.get('output', ''))
            
            # 判断是否包含分隔符
            is_target_multi = any(s in target for s in multi_intent_sep)
            is_output_multi = any(s in output for s in multi_intent_sep)
            
            # 标准化意图集合（忽略顺序）
            def parse_intents(text):
                for s in multi_intent_sep:
                    text = text.replace(s, ",")
                return [t.strip() for t in text.split(",") if t.strip()]
                
            target_set = parse_intents(target)
            output_set = parse_intents(output)
            
            if not is_target_multi and is_output_multi:
                false_positive += 1
                mixed_errors.append(err)
            elif is_target_multi and not is_output_multi:
                false_negative += 1
                mixed_errors.append(err)
            elif is_target_multi and is_output_multi:
                # 检查集合是否相同但顺序不同
                if set(target_set) == set(output_set) and target_set != output_set:
                    order_error += 1
                    mixed_errors.append(err)
                    
        total = len(errors)
        return {
            "false_positive_rate": false_positive / total if total else 0,
            "false_negative_rate": false_negative / total if total else 0,
            "order_error_rate": order_error / total if total else 0,
            "false_positive_count": false_positive,
            "false_negative_count": false_negative,
            "order_error_count": order_error,
            "has_issue": (false_positive + false_negative + order_error) / total > 0.15,
            "sample_cases": mixed_errors[:3]
        }

    # -------------------------------------------------------------------------
    # C. 领域混淆矩阵分析
    # -------------------------------------------------------------------------
    async def analyze_domain_confusion(
        self, 
        errors: List[Dict[str, Any]], 
        all_intents: List[str]
    ) -> Dict[str, Any]:
        """
        分析领域级混淆 (需要 LLM 辅助将意图归类为领域)
        """
        if not self.llm_client or not all_intents:
            return {"message": "由于缺少 LLM 客户端或意图列表，已跳过领域分析"}
            
        # 1. 意图聚类/领域识别 (使用 Cache 避免重复调用?)
        # 简化版：直接让 LLM 分析错误中的混淆模式并归纳领域
        
        # 提取 top 混淆对
        confusion_pairs = Counter()
        for err in errors:
            t = str(err.get('target', '')).strip()
            o = str(err.get('output', '')).strip()
            if t and o and t != o:
                confusion_pairs[(t, o)] += 1
                
        top_pairs = confusion_pairs.most_common(5)
        if not top_pairs:
            return {"message": "未发现明显的混淆意图对"}
            
        # 构建 Prompt 让 LLM 分析领域关系
        pairs_text = "\n".join([f"{t} -> {o} ({c}次)" for (t, o), c in top_pairs])
        
        prompt = f"""分析以下意图混淆对，识别是否存在跨领域的系统性错误。
如果存在，请定义涉及的"领域"(Domain)并指出哪些领域容易混淆。

混淆对:
{pairs_text}

请返回 JSON 格式结果：
{{
    "domains": ["领域A", "领域B"],
    "domain_confusion": [
        {{"from": "领域A", "to": "领域B", "reason": "名称相似/功能重叠", "count": 10}}
    ],
    "summary": "简短分析"
}}"""

        try:
             response = await self._call_llm_async(prompt)
             # 尝试解析 JSON
             if "```json" in response:
                 response = response.split("```json")[1].split("```")[0]
             elif "```" in response:
                 response = response.split("```")[1].split("```")[0]
                 
             analysis = json.loads(response.strip())
             return analysis
        except Exception as e:
            self.logger.warning(f"领域混淆分析失败: {e}")
            return {"error": str(e)}

    # -------------------------------------------------------------------------
    # D. 澄清机制分析
    # -------------------------------------------------------------------------
    async def analyze_clarification(self, errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析澄清机制：过度澄清 vs 缺失澄清
        """
        clarification_keywords = ["澄清", "clarify", "哪个", "which", "provide more info", "请问"]
        
        unnecessary_clarification = 0 # 预期是具体意图，输出了澄清
        missing_clarification = 0     # 预期是澄清，输出了具体意图
        
        clarification_errors = []
        
        for err in errors:
            target = str(err.get('target', '')).lower()
            output = str(err.get('output', '')).lower()
            
            target_is_clarify = any(k in target for k in clarification_keywords) or target == "clarification"
            output_is_clarify = any(k in output for k in clarification_keywords) or output == "clarification"
            
            if not target_is_clarify and output_is_clarify:
                unnecessary_clarification += 1
                clarification_errors.append(err)
            elif target_is_clarify and not output_is_clarify:
                missing_clarification += 1
                clarification_errors.append(err)
                
        total = len(errors)
        return {
            "unnecessary_rate": unnecessary_clarification / total if total else 0,
            "missing_rate": missing_clarification / total if total else 0,
            "has_issue": (unnecessary_clarification + missing_clarification) / total > 0.05,
            "sample_cases": clarification_errors[:3]
        }

    async def _call_llm_async(self, prompt: str) -> str:
        """
        异步调用 LLM
        
        :param prompt: 输入提示词
        :return: LLM 响应内容
        """
        loop = asyncio.get_event_loop()
        
        # 记录 LLM 请求输入日志
        self.logger.info(f"[LLM请求-高级诊断] 输入提示词长度: {len(prompt)} 字符")
        self.logger.debug(f"[LLM请求-高级诊断] 输入内容:\n{prompt[:600]}...")
        
        def run_sync() -> str:
            model_name: str = self.model_config.get("model_name", "gpt-3.5-turbo")
            self.logger.info(f"[LLM请求-高级诊断] 使用模型: {model_name}")
            
            try:
                response = self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=600,
                    # 强制 JSON
                    extra_body={"response_format": {"type": "json_object"}}
                )
                result: str = response.choices[0].message.content.strip()
                
                # 记录 LLM 响应输出日志
                self.logger.info(f"[LLM响应-高级诊断] 输出长度: {len(result)} 字符")
                self.logger.debug(f"[LLM响应-高级诊断] 输出内容:\n{result[:600]}...")
                
                return result
            except Exception as e:
                self.logger.warning(f"[LLM请求-高级诊断] JSON模式调用失败: {e}，尝试普通模式...")
                # Retry without json enforcement if failed
                try:
                    response = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=600
                    )
                    result: str = response.choices[0].message.content.strip()
                    
                    # 记录重试后的响应
                    self.logger.info(f"[LLM响应-高级诊断(重试)] 输出长度: {len(result)} 字符")
                    self.logger.debug(f"[LLM响应-高级诊断(重试)] 输出内容:\n{result[:600]}...")
                    
                    return result
                except Exception as e2:
                    self.logger.error(f"[LLM请求-高级诊断] 重试后仍失败: {e2}")
                    raise e2
                    
        return await loop.run_in_executor(None, run_sync)
