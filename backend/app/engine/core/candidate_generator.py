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
            
            return {
                "strategy": strategy.name,
                "prompt": new_prompt,
                "original_prompt": prompt
            }
        except Exception as e:
            logger.error(f"应用策略 {strategy.name} 时发生错误: {e}")
            raise e
