"""
高级诊断模块 - 提供定向的深度分析能力
包括：上下文处理、多意图识别、领域混淆矩阵、澄清机制分析
"""
import asyncio
import logging
import re
import json
from typing import List, Dict, Any, Optional, Tuple, Callable
from collections import Counter, defaultdict
from .cancellation import run_with_cancellation

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
        intents: Optional[List[str]] = None,
        should_stop: Any = None
    ) -> Dict[str, Any]:
        """
        并行运行所有高级诊断（支持中途取消）
        
        :param errors: 错误样例列表
        :param intents: 意图列表
        :param should_stop: 停止回调函数
        :return: 诊断结果
        """
        if not errors:
            return {}
            
        # 检查停止信号
        if should_stop and should_stop():
             self.logger.info("高级诊断被手动中止")
             return {}
            
        dataset_intents = intents or self._extract_intents(errors)
        
        # 使用 create_task 创建任务，以便后续可取消
        tasks = [
            asyncio.create_task(self.analyze_context_capabilities(errors)),
            asyncio.create_task(self.analyze_multi_intent(errors)),
            asyncio.create_task(self.analyze_domain_confusion(errors, dataset_intents, should_stop)),
            asyncio.create_task(self.analyze_clarification(errors)),
        ]
        
        # 等待所有任务完成，但定期检查停止信号
        results = []
        keys = ["context_analysis", "multi_intent_analysis", "domain_analysis", "clarification_analysis"]
        
        for idx, task in enumerate(tasks):
            # 在等待每个任务前检查停止信号
            if should_stop and should_stop():
                self.logger.info(f"高级诊断在等待任务 {keys[idx]} 时被中止，取消剩余任务...")
                # 取消未完成的任务
                for t in tasks:
                    if not t.done():
                        t.cancel()
                break
            
            try:
                result = await task
                results.append(result)
            except asyncio.CancelledError:
                self.logger.info(f"任务 {keys[idx]} 已取消")
                results.append({"cancelled": True})
            except Exception as e:
                self.logger.error(f"高级诊断 {keys[idx]} 失败: {e}")
                results.append({"error": str(e)})
        
        # 构建最终结果
        final_results = {}
        for k, res in zip(keys[:len(results)], results):
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
        all_intents: List[str],
        should_stop: Any = None
    ) -> Dict[str, Any]:
        """
        分析领域级混淆 (需要 LLM 辅助将意图归类为领域)
        
        :param errors: 错误样例列表
        :param all_intents: 所有意图列表
        :param should_stop: 停止回调函数
        :return: 分析结果
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

        # 在 LLM 调用前检查停止信号
        if should_stop and should_stop():
            self.logger.info("领域混淆分析在 LLM 调用前被中止")
            return {"cancelled": True, "message": "已中止"}

        try:
             # 使用可取消的 LLM 调用
             response: str = await self._call_llm_with_cancellation(prompt, should_stop, "领域混淆分析")
             if not response:
                 return {"cancelled": True, "message": "调用已取消或失败"}
             
             # 尝试解析 JSON
             if "```json" in response:
                 response = response.split("```json")[1].split("```")[0]
             elif "```" in response:
                 response = response.split("```")[1].split("```")[0]
                 
             analysis = json.loads(response.strip())
             return analysis
        except asyncio.CancelledError:
            self.logger.info("领域混淆分析 LLM 调用被取消")
            return {"cancelled": True, "message": "已取消"}
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
        异步调用 LLM (支持 AsyncOpenAI)
        
        :param prompt: 输入提示词
        :return: LLM 响应内容
        """
        from openai import AsyncOpenAI
        
        model_name: str = self.model_config.get("model_name", "gpt-3.5-turbo")
        temperature: float = float(self.model_config.get("temperature", 0.1))
        max_tokens: int = int(self.model_config.get("max_tokens", 4000))
        
        self.logger.info(f"[LLM请求-高级诊断] 输入提示词长度: {len(prompt)} 字符")
        
        try:
            # 区分 AsyncOpenAI 和 OpenAI
            if isinstance(self.llm_client, AsyncOpenAI):
                response = await self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_body={"response_format": {"type": "json_object"}}
                )
                result: str = response.choices[0].message.content.strip()
            else:
                # 同步客户端，必须在 Executor 中运行
                loop = asyncio.get_running_loop()
                def run_sync() -> str:
                    resp = self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens,
                        extra_body={"response_format": {"type": "json_object"}}
                    )
                    return resp.choices[0].message.content.strip()
                
                result = await loop.run_in_executor(None, run_sync)
            
            return result
            
        except Exception as e:
            self.logger.warning(f"[LLM请求-高级诊断] JSON模式调用失败: {e}，尝试普通模式...")
            try:
                if isinstance(self.llm_client, AsyncOpenAI):
                    response = await self.llm_client.chat.completions.create(
                        model=model_name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    result = response.choices[0].message.content.strip()
                else:
                    loop = asyncio.get_running_loop()
                    def run_sync_retry() -> str:
                        resp = self.llm_client.chat.completions.create(
                            model=model_name,
                            messages=[{"role": "user", "content": prompt}],
                            temperature=temperature,
                            max_tokens=max_tokens
                        )
                        return resp.choices[0].message.content.strip()
                    result = await loop.run_in_executor(None, run_sync_retry)
                    
                return result
            except Exception as e2:
                self.logger.error(f"[LLM请求-高级诊断] 重试后仍失败: {e2}")
                raise e2

    async def _call_llm_with_cancellation(
        self, 
        prompt: str,
        should_stop: Callable[[], bool] = None,
        task_name: str = "高级诊断LLM调用"
    ) -> str:
        """
        可取消的 LLM 调用
        
        使用 run_with_cancellation 包装 LLM 调用，使其能够在收到停止信号后立即响应
        
        :param prompt: 输入提示词
        :param should_stop: 停止回调函数
        :param task_name: 任务名称（用于日志）
        :return: LLM 响应内容
        """
        if should_stop is None:
            # 没有停止回调，直接调用原始方法
            return await self._call_llm_async(prompt)
        
        try:
            result: str = await run_with_cancellation(
                self._call_llm_async(prompt),
                should_stop=should_stop,
                check_interval=0.5,
                task_name=task_name
            )
            return result
        except asyncio.CancelledError:
            self.logger.info(f"[高级诊断] {task_name} 被用户取消")
            return ""
        except Exception as e:
            self.logger.error(f"[高级诊断] {task_name} 失败: {e}")
            return ""
