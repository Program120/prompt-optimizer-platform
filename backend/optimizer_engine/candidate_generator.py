"""候选方案生成模块 - 封装策略应用和候选生成逻辑"""
import asyncio
import logging
from typing import List, Dict, Any, Callable, Optional

from .fewshot_selector import FewShotSelector
from .cancellation import gather_with_cancellation


class CandidateGenerator:
    """
    候选方案生成器
    
    负责并行执行多个优化策略，生成优化候选方案集合
    """
    
    def __init__(
        self, 
        selector: FewShotSelector = None,
        semaphore: asyncio.Semaphore = None
    ):
        """
        初始化候选方案生成器
        
        :param selector: Few-shot 选择器实例
        :param semaphore: 并发控制信号量
        """
        self.selector: FewShotSelector = selector or FewShotSelector()
        self.semaphore: asyncio.Semaphore = semaphore or asyncio.Semaphore(5)
        self.logger: logging.Logger = logging.getLogger(__name__)
    
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
        生成优化候选集（支持取消）
        
        :param prompt: 当前提示词
        :param strategies: 策略列表
        :param errors: 错误样例
        :param diagnosis: 诊断结果
        :param dataset: 数据集
        :param should_stop: 停止回调函数
        :return: 候选方案列表
        """
        candidates: List[Dict[str, Any]] = []
        
        # 检查停止信号
        if should_stop and should_stop():
            self.logger.info("候选生成阶段开始前即被手动中止")
            return candidates
        
        # 创建策略应用任务列表
        tasks: list = []
        for strategy in strategies:
            tasks.append(
                self._apply_strategy_wrapper(
                    strategy, prompt, errors, diagnosis, dataset
                )
            )
        
        # 使用可取消的 gather 执行所有策略
        # 如果收到停止信号，会自动取消所有未完成的任务
        results = await gather_with_cancellation(
            *tasks,
            should_stop=should_stop,
            check_interval=0.5,
            return_exceptions=True
        )
        
        for res in results:
            if isinstance(res, dict) and res.get("prompt"):
                candidates.append(res)
            elif isinstance(res, asyncio.CancelledError):
                self.logger.info("策略执行被取消")
            elif isinstance(res, Exception):
                self.logger.error(f"策略执行失败: {res}")
        
        self.logger.info(
            f"成功生成 {len(candidates)} 个候选方案: "
            f"{[c.get('strategy') for c in candidates]}"
        )
        return candidates

    async def _apply_strategy_wrapper(
        self, 
        strategy: Any, 
        prompt: str, 
        errors: List[Dict[str, Any]], 
        diagnosis: Dict[str, Any], 
        dataset: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        包装策略执行逻辑
        
        :param strategy: 策略实例
        :param prompt: 当前提示词
        :param errors: 错误样例
        :param diagnosis: 诊断结果
        :param dataset: 数据集
        :return: 候选方案字典
        """
        self.logger.info(f"正在应用策略: {strategy.name}")
        try:
            # 策略应用可能涉及 LLM 调用，也可能涉及 Rewriter/Selector
            # 为了兼容现有 Strategy 类，我们先尝试调用其 apply 方法
            # 同时注入 rewriter/selector 的能力（如果 Strategy 支持）
            
            # 扩展：如果 Strategy 是 DifficultExampleInjectionStrategy，使用 Selector
            if strategy.name == "difficult_example_injection":
                # 使用 Selector 选择困难案例
                hard_cases = self.selector.select(dataset, "difficulty", n=3)
                diagnosis_copy = diagnosis.copy()
                diagnosis_copy["error_patterns"] = diagnosis.get(
                    "error_patterns", {}
                ).copy()
                diagnosis_copy["error_patterns"]["hard_cases"] = hard_cases
                diagnosis = diagnosis_copy
            
            loop = asyncio.get_running_loop()
            new_prompt = await loop.run_in_executor(
                None,
                lambda: strategy.apply(prompt, errors, diagnosis)
            )
            
            if new_prompt != prompt:
                self.logger.info(
                    f"策略 {strategy.name} 成功更新了提示词。"
                    f"长度变化: {len(prompt)} -> {len(new_prompt)}"
                )
                self.logger.debug(
                    f"Diff 预览: {new_prompt[:50]}... (已应用变更)"
                )
            else:
                self.logger.info(f"策略 {strategy.name} 未产生任何实质性变更。")
            
            return {
                "strategy": strategy.name,
                "prompt": new_prompt,
                "original_prompt": prompt
            }
        except Exception as e:
            self.logger.error(f"应用策略 {strategy.name} 时发生错误: {e}")
            raise e
