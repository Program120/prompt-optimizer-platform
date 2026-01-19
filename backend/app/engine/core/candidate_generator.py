from loguru import logger
from typing import List, Dict, Any, Callable, Optional, Union
import asyncio

from ..helpers.fewshot import FewShotSelector
from ..helpers.cancellation import gather_with_cancellation
from ..strategies.base import BaseStrategy


class CandidateGenerator:
    """
    候选方案生成器类。

    该类负责并行调度和执行多种优化策略，生成一组优化后的提示词候选方案。
    支持异步执行、并发控制以及通过回调函数进行任务取消。
    """
    
    def __init__(
        self, 
        selector: Optional[FewShotSelector] = None,
        semaphore: Optional[asyncio.Semaphore] = None
    ):
        """
        初始化候选方案生成器。

        Args:
            selector (Optional[FewShotSelector]): 用于选择示例的 Few-shot 选择器实例。
            semaphore (Optional[asyncio.Semaphore]): 用于并发控制的信号量，默认最大并发数为 5。
        """
        self.selector: FewShotSelector = selector or FewShotSelector()
        self.semaphore: asyncio.Semaphore = semaphore or asyncio.Semaphore(5)
    
    async def generate_candidates(
        self, 
        prompt: str, 
        strategies: List[Any], 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any],
        dataset: List[Dict[str, Any]],
        should_stop: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        并发执行优化策略以生成候选方案集合，支持并在任务中取消。

        Args:
            prompt (str): 待优化的原始提示词。
            strategies (List[Any]): 要应用的优化策略列表。
            errors (List[Dict[str, Any]]): 错误样例列表，用于策略分析。
            diagnosis (Dict[str, Any]): 包含意图分析等信息的诊断结果。
            dataset (List[Dict[str, Any]]): 完整数据集，用于检索更多示例。
            should_stop (Optional[Callable[[], bool]]): 停止信号回调函数，返回 True 表示需要中止任务。

        Returns:
            List[Dict[str, Any]]: 包含优化结果的候选方案列表，每个元素包含策略名、新提示词等信息。
        """
        candidates: List[Dict[str, Any]] = []
        
        # 检查停止信号
        if should_stop and should_stop():
            logger.info("候选生成阶段开始前检测到停止信号，已手动中止。")
            return candidates
        
        # 创建策略应用任务列表
        tasks: List[asyncio.Task] = []
        for strategy in strategies:
            tasks.append(
                self._apply_strategy_wrapper(
                    strategy, prompt, errors, diagnosis, dataset
                )
            )
        
        # 使用可取消的 gather 执行所有策略
        # 如果收到停止信号，会自动取消所有未完成的任务
        results: List[Union[Dict[str, Any], Exception]] = await gather_with_cancellation(
            *tasks,
            should_stop=should_stop,
            check_interval=0.5,
            return_exceptions=True
        )
        
        for res in results:
            if isinstance(res, dict) and res.get("prompt"):
                candidates.append(res)
            elif isinstance(res, asyncio.CancelledError):
                logger.info("策略执行被取消。")
            elif isinstance(res, Exception):
                logger.error(f"策略执行过程中发生异常: {res}")
        
        logger.info(
            f"成功生成 {len(candidates)} 个候选方案: "
            f"{[c.get('strategy') for c in candidates]}"
        )
        return candidates

    async def generate_candidates_serial(
        self, 
        prompt: str, 
        strategies: List[Any], 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any],
        dataset: List[Dict[str, Any]],
        should_stop: Optional[Callable[[], bool]] = None,
        llm_client: Any = None,
        model_config: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        串行执行优化策略以生成候选方案（每个策略依次应用到前一个策略的输出上）

        与 generate_candidates 不同，此方法采用链式应用模式：
        原始 prompt → [评估是否需要策略1] → 策略1 → 结果1 → [评估是否需要策略2] → ...

        在应用每个策略前，会调用 LLM 评估当前提示词是否需要该策略提升。

        Args:
            prompt (str): 待优化的原始提示词。
            strategies (List[Any]): 要应用的优化策略列表。
            errors (List[Dict[str, Any]]): 错误样例列表，用于策略分析。
            diagnosis (Dict[str, Any]): 包含意图分析等信息的诊断结果。
            dataset (List[Dict[str, Any]]): 完整数据集，用于检索更多示例。
            should_stop (Optional[Callable[[], bool]]): 停止信号回调函数。
            llm_client (Any): LLM 客户端实例，用于评估策略必要性。
            model_config (Optional[Dict[str, Any]]): 模型配置。

        Returns:
            List[Dict[str, Any]]: 包含每个策略应用结果的候选方案列表。
        """
        candidates: List[Dict[str, Any]] = []
        
        # 检查停止信号
        if should_stop and should_stop():
            logger.info("候选生成阶段开始前检测到停止信号，已手动中止。")
            return candidates
        
        # 串行应用所有策略
        # 每个策略的输入是前一个策略的输出
        current_prompt: str = prompt
        applied_strategies: List[str] = []
        skipped_strategies: List[str] = []
        
        for strategy in strategies:
            # 检查停止信号
            if should_stop and should_stop():
                logger.info("候选生成过程中检测到停止信号，已手动中止。")
                break
            
            try:
                # 评估是否需要应用该策略
                if llm_client:
                    score, reason = await self._evaluate_strategy_necessity(
                        current_prompt=current_prompt,
                        strategy=strategy,
                        errors=errors,
                        diagnosis=diagnosis,
                        llm_client=llm_client,
                        model_config=model_config or {}
                    )
                    
                    # 阈值：只执行 0.7 分以上的策略
                    score_threshold: float = 0.7
                    
                    if score < score_threshold:
                        logger.info(
                            f"策略 {strategy.name} 被跳过，评分: {score:.2f} < {score_threshold}，原因: {reason}"
                        )
                        skipped_strategies.append(strategy.name)
                        continue
                    else:
                        logger.info(
                            f"策略 {strategy.name} 通过评估，评分: {score:.2f}，原因: {reason}"
                        )
                
                # 应用策略
                result: Dict[str, Any] = await self._apply_strategy_wrapper(
                    strategy, current_prompt, errors, diagnosis, dataset
                )
                
                if result.get("prompt") and result["prompt"] != current_prompt:
                    # 更新当前提示词为该策略的输出
                    current_prompt = result["prompt"]
                    applied_strategies.append(strategy.name)
                    
                    # 记录每个策略的中间结果
                    candidates.append(result)
                    logger.info(
                        f"策略 {strategy.name} 已串行应用，当前累计策略: {applied_strategies}"
                    )
                else:
                    logger.info(f"策略 {strategy.name} 未产生变化，跳过。")
                    
            except asyncio.CancelledError:
                logger.info(f"策略 {strategy.name} 执行被取消。")
                break
            except Exception as e:
                logger.error(f"策略 {strategy.name} 执行过程中发生异常: {e}")
                # 继续执行下一个策略
                continue
        
        logger.info(
            f"串行生成完成，应用 {len(applied_strategies)} 个策略: {applied_strategies}，"
            f"跳过 {len(skipped_strategies)} 个策略: {skipped_strategies}"
        )
        return candidates

    async def _evaluate_strategy_necessity(
        self,
        current_prompt: str,
        strategy: Any,
        errors: List[Dict[str, Any]],
        diagnosis: Dict[str, Any],
        llm_client: Any,
        model_config: Dict[str, Any]
    ) -> tuple[float, str]:
        """
        使用 LLM 评估当前提示词应用指定策略的必要性分数

        Args:
            current_prompt (str): 当前的提示词（可能已经被之前的策略优化过）。
            strategy (Any): 待评估的策略实例。
            errors (List[Dict[str, Any]]): 错误样例列表。
            diagnosis (Dict[str, Any]): 诊断结果。
            llm_client (Any): LLM 客户端。
            model_config (Dict[str, Any]): 模型配置。

        Returns:
            tuple[float, str]: (必要性分数 0.0-1.0, 评估理由)
        """
        import json
        
        # 获取策略描述
        strategy_name: str = getattr(strategy, "name", strategy.__class__.__name__)
        strategy_doc: str = strategy.__class__.__doc__ or "无描述"
        
        # 构建评估 Prompt
        # 只取前 5 个错误样例避免 Prompt 过长
        error_samples: List[Dict[str, Any]] = errors[:5]
        error_samples_text: str = "\n".join([
            f"- 查询: {e.get('query', '')[:50]}... 期望: {e.get('target', '')} 实际: {e.get('output', '')}"
            for e in error_samples
        ])
        
        eval_prompt: str = f"""你是一个提示词优化专家。请分析当前提示词应用以下优化策略的必要性。

【当前提示词摘要】
{current_prompt[:1500]}...

【待评估策略】
- 策略名称: {strategy_name}
- 策略描述: {strategy_doc[:500]}

【当前错误样例（示例）】
{error_samples_text}

【评估任务】
请分析当前提示词是否存在该策略所针对的问题，并给出该策略的必要性评分。

请以 JSON 格式返回评估结果：
{{
    "necessity_score": 0.0-1.0,
    "reason": "评估理由（简洁明了，30字以内）"
}}

【评分标准】
- 0.9-1.0: 策略直接解决核心问题，强烈建议应用
- 0.7-0.8: 策略与问题高度相关，建议应用
- 0.5-0.6: 策略可能有一定效果
- 0.3-0.4: 策略关联度较低
- 0.0-0.2: 提示词已覆盖该能力或策略不适用

【注意】
- 如果提示词已经很好地覆盖了该策略的优化方向，给低分
- 如果错误样例反映出的问题与该策略直接相关，给高分"""

        try:
            model_name: str = model_config.get("model_name", "gpt-3.5-turbo")
            
            response = await llm_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a prompt engineering expert."},
                    {"role": "user", "content": eval_prompt}
                ],
                temperature=0.2,
                max_tokens=200,
                response_format={"type": "json_object"}
            )
            
            content: str = response.choices[0].message.content
            result: Dict[str, Any] = json.loads(content)
            
            # 获取必要性分数
            necessity_score: float = result.get("necessity_score", 0.5)
            reason: str = result.get("reason", "无理由")
            
            # 确保分数在 0-1 范围内
            necessity_score = max(0.0, min(1.0, float(necessity_score)))
            
            logger.debug(
                f"[策略评估] {strategy_name}: score={necessity_score:.2f}, reason={reason}"
            )
            
            return necessity_score, reason
            
        except Exception as e:
            logger.warning(f"[策略评估] 评估 {strategy_name} 失败: {e}，默认应用该策略")
            # 评估失败时返回高分，确保策略被应用
            return 1.0, f"评估失败: {str(e)[:30]}"

    async def _apply_strategy_wrapper(
        self, 
        strategy: BaseStrategy, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any], 
        dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        包装单个策略的执行逻辑，处理异常并记录日志。

        Args:
            strategy (BaseStrategy): 要执行的策略实例。
            prompt (str): 待优化的原始提示词。
            errors (List[Dict[str, Any]]): 错误样例列表。
            diagnosis (Dict[str, Any]): 诊断结果。
            dataset (List[Dict[str, Any]]): 数据集。

        Returns:
            Dict[str, Any]: 包含策略执行结果的字典，包括策略名、新旧提示词等。
        
        Raises:
            Exception: 如果策略执行失败，将抛出异常。
        """
        logger.info(f"正在应用策略: {strategy.name}")
        try:
            # 策略应用可能涉及 LLM 调用，也可能涉及 Rewriter/Selector
            # 为了兼容现有 Strategy 类，我们先尝试调用其 apply 方法
            # 同时注入 rewriter/selector 的能力（如果 Strategy 支持）
            
            # 扩展：如果 Strategy 是 DifficultExampleInjectionStrategy，使用 Selector
            if strategy.name == "difficult_example_injection":
                # 使用 Selector 选择困难案例
                hard_cases: List[Dict[str, Any]] = self.selector.select(dataset, "difficulty", n=3)
                diagnosis_copy: Dict[str, Any] = diagnosis.copy()
                # 浅拷贝 error_patterns 防止修改原始引用
                diagnosis_copy["error_patterns"] = diagnosis.get(
                    "error_patterns", {}
                ).copy()
                diagnosis_copy["error_patterns"]["hard_cases"] = hard_cases
                diagnosis = diagnosis_copy
            
            loop = asyncio.get_running_loop()
            
            # 在执行器中运行同步的 strategy.apply 方法，避免阻塞事件循环
            new_prompt: str = await loop.run_in_executor(
                None,
                lambda: strategy.apply(prompt, errors, diagnosis)
            )
            
            if new_prompt != prompt:
                logger.info(
                    f"策略 {strategy.name} 成功更新了提示词。"
                    f"长度变化: {len(prompt)} -> {len(new_prompt)}"
                )
                logger.debug(
                    f"策略 {strategy.name} Diff 预览: {new_prompt[:50]}... (已应用变更)"
                )
            else:
                logger.info(f"策略 {strategy.name} 未产生任何实质性变更。")
            
            # 提取策略选择元数据
            selection_score = getattr(strategy, "selection_score", 0)
            selection_reason = getattr(strategy, "selection_reason", "")
            
            return {
                "strategy": strategy.name,
                "prompt": new_prompt,
                "original_prompt": prompt,
                "selection_score": selection_score,
                "selection_reason": selection_reason
            }
        except Exception as e:
            logger.error(f"应用策略 {strategy.name} 时发生错误: {e}")
            raise e
