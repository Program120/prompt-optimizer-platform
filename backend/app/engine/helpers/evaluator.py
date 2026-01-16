"""提示词评估模块 - 封装验证集构建和快速评估逻辑"""
import asyncio
from loguru import logger
import asyncio
import random
from typing import List, Dict, Any, Callable, Optional

from .cancellation import gather_with_cancellation
from .cancellation import gather_with_cancellation
from .llm import LLMHelper
from .verifier import Verifier


class PromptEvaluator:
    """
    提示词评估器
    
    负责构建验证集并对优化候选方案进行快速评估
    """
    
    def __init__(
        self, 
        llm_helper: LLMHelper = None,
        verification_llm_client: Any = None,
        verification_model_config: Dict[str, Any] = None
    ):
        """
        初始化提示词评估器
        
        :param llm_helper: LLM 辅助类实例
        :param verification_llm_client: 验证专用 LLM 客户端
        :param verification_model_config: 验证专用模型配置
        """
        self.llm_helper: LLMHelper = llm_helper
        self.verification_llm_client = verification_llm_client
        self.verification_model_config = verification_model_config
    
    def build_validation_set(
        self,
        errors: List[Dict[str, Any]],
        dataset: List[Dict[str, Any]],
        target_error_count: int = 20,
        correct_error_ratio: float = 1.5
    ) -> List[Dict[str, Any]]:
        """
        构建混合验证集，包含正确案例和错误案例
        
        验证集设计原则：
        - 正确案例与错误案例比例为 3:2 (correct_error_ratio=1.5)
        - 当数据不足时，按实际可用数量构建
        - 确保验证集不会包含重复数据
        
        :param errors: 错误案例列表
        :param dataset: 完整数据集（包含正确和错误案例）
        :param target_error_count: 目标错误案例数量（默认20）
        :param correct_error_ratio: 正确案例与错误案例的比例（默认1.5，即3:2）
        :return: 混合验证集
        """
        validation_set: List[Dict[str, Any]] = []
        
        # 1. 获取错误集合
        # 获取错误案例的唯一标识（使用 query 字段作为 key）
        error_queries: set = {e.get('query', '') for e in errors}
        
        # 2. 从 dataset 中筛选出正确案例
        # 正确案例 = 完整数据集中不在错误集合里的案例
        correct_cases: List[Dict[str, Any]] = [
            item for item in dataset 
            if item.get('query', '') not in error_queries
        ]
        
        # 3. 计算实际可用的案例数量
        available_errors: int = len(errors)
        available_correct: int = len(correct_cases)
        
        # 4. 计算目标数量（考虑数据不足的情况）
        # 期望的错误案例数
        actual_error_count: int = min(target_error_count, available_errors)
        
        # 期望的正确案例数 = 错误案例数 * 比例
        target_correct_count: int = int(actual_error_count * correct_error_ratio)
        actual_correct_count: int = min(target_correct_count, available_correct)
        
        # 5. 如果正确案例不足，重新调整错误案例数量以保持比例
        if actual_correct_count < target_correct_count and actual_correct_count > 0:
            # 根据实际正确案例反推错误案例数量
            adjusted_error_count: int = int(actual_correct_count / correct_error_ratio)
            actual_error_count = max(1, min(adjusted_error_count, actual_error_count))
            logger.info(
                f"[验证集构建] 正确案例不足，调整比例: "
                f"正确={actual_correct_count}, 错误={actual_error_count}"
            )
        
        # 6. 随机采样
        # 采样错误案例
        if actual_error_count > 0 and available_errors > 0:
            sampled_errors: List[Dict[str, Any]] = random.sample(
                errors, 
                min(actual_error_count, available_errors)
            )
            # 使用浅拷贝避免污染原始数据，并标记为错误案例
            for case in sampled_errors:
                case_copy: Dict[str, Any] = case.copy()
                case_copy['_is_error_case'] = True
                validation_set.append(case_copy)
        
        # 采样正确案例
        if actual_correct_count > 0 and available_correct > 0:
            sampled_correct: List[Dict[str, Any]] = random.sample(
                correct_cases,
                min(actual_correct_count, available_correct)
            )
            # 使用浅拷贝避免污染原始数据，并标记为正确案例
            for case in sampled_correct:
                case_copy: Dict[str, Any] = case.copy()
                case_copy['_is_error_case'] = False
                validation_set.append(case_copy)
        
        # 7. 打乱验证集顺序
        random.shuffle(validation_set)
        
        # 8. 记录日志
        error_count: int = sum(
            1 for c in validation_set if c.get('_is_error_case', False)
        )
        correct_count: int = len(validation_set) - error_count
        ratio_str: str = (
            f"{correct_count / error_count:.2f}" if error_count > 0 else "N/A"
        )
        logger.info(
            f"[验证集构建] 完成: 总计={len(validation_set)} "
            f"(正确={correct_count}, 错误={error_count}, 比例={ratio_str})"
        )
        
        return validation_set

    async def rapid_evaluation(
        self, 
        candidates: List[Dict[str, Any]], 
        validation_set: List[Dict[str, Any]],
        should_stop: Optional[Callable[[], bool]] = None,
        extraction_rule: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        快速评估候选效果（支持取消）
        
        :param candidates: 候选方案列表
        :param validation_set: 验证集
        :param should_stop: 停止回调函数
        :return: 评估后的候选方案列表（按分数排序）
        """
        # 优化：无候选时直接返回
        if not candidates:
            logger.info("[快速筛选] 无候选方案，跳过筛选")
            return candidates
        
        # 优化：仅一个候选时无须筛选，直接返回
        if len(candidates) == 1:
            logger.info(
                f"[快速筛选] 仅有 1 个候选方案 ({candidates[0]['strategy']})，"
                f"跳过筛选步骤"
            )
            # 给单个候选设置默认分数
            candidates[0]["score"] = 1.0
            return candidates
        
        # 优化：无验证集时直接返回
        if not validation_set:
            logger.info("[快速筛选] 无验证集，跳过筛选")
            return candidates
        
        logger.info(
            f"[快速筛选] 开始评估 {len(candidates)} 个候选方案，"
            f"验证集大小: {len(validation_set)}"
        )
            
        evaluated: List[Dict[str, Any]] = []
        for cand in candidates:
            # 每次评估前检查停止信号
            if should_stop and should_stop():
                logger.info("[快速筛选] 评估阶段被手动中止")
                break
                
            score: float = await self.evaluate_prompt(
                cand["prompt"], validation_set, should_stop, extraction_rule
            )
            logger.info(
                f"[快速筛选] 策略 '{cand['strategy']}' 评估完毕: 得分 = {score:.4f}"
            )
            cand["score"] = score
            evaluated.append(cand)
            
        # 按分数排序
        evaluated.sort(key=lambda x: x["score"], reverse=True)
        return evaluated
        
    async def evaluate_prompt(
        self, 
        prompt: str, 
        test_cases: List[Dict[str, Any]],
        should_stop: Optional[Callable[[], bool]] = None,
        extraction_rule: Optional[str] = None
    ) -> float:
        """
        评估 Prompt 在测试集上的表现 (0-1)（支持取消）
        
        :param prompt: 待评估的提示词
        :param test_cases: 测试用例列表
        :param should_stop: 停止回调函数
        :return: 评估得分 (0-1)
        """
        # 使用验证专用的 client，如果未提供则回退到主 client
        if not self.llm_helper:
            return 0.5
        
        # 检查停止信号
        if should_stop and should_stop():
            return 0.0
            
        total: int = len(test_cases)
        logger.info(
            f"正在对提示词进行快速评估 (长度={len(prompt)})，测试案例数: {total}..."
        )
        
        # 限制并发
        sem: asyncio.Semaphore = asyncio.Semaphore(3)
        
        async def run_case(case: Dict[str, Any]) -> int:
            """
            评估单个测试用例
            
            :param case: 测试用例
            :return: 1 表示正确，0 表示错误
            """
            async with sem:
                # 检查停止信号
                if should_stop and should_stop():
                    return 0
                    
                try:
                    query: str = case.get('query', '')
                    target: str = case.get('target', '')
                    
                    # 使用 Verifier 执行验证 (使用 run_in_executor 封装同步调用)
                    # 注意: Verifier 这里是 CPU binding 操作为主 (exec)，但也包含 I/O (Interface / LLM)
                    # 我们希望保持并发，所以 run_in_executor 是必须的
                    loop = asyncio.get_running_loop()
                    
                    # 确定使用的配置 (验证配置或模型配置)
                    config = self.verification_model_config or {}
                    
                    result = await loop.run_in_executor(
                        None,
                        lambda: Verifier.verify_single(
                            index=0, 
                            query=query,
                            target=target,
                            prompt=prompt,
                            model_config=config,
                            extract_field=extraction_rule
                        )
                    )
                    
                    return 1 if result["is_correct"] else 0

                except asyncio.CancelledError:
                    return 0
                except Exception as e:
                    logger.error(f"Evaluating prompt error: {e}")
                    return 0

        tasks: list = [run_case(case) for case in test_cases]
        
        # 使用可取消的 gather
        results = await gather_with_cancellation(
            *tasks,
            should_stop=should_stop,
            check_interval=0.5,
            return_exceptions=True
        )
        
        # 处理结果，忽略异常
        valid_results: list = [r for r in results if isinstance(r, int)]
        
        return sum(valid_results) / total if total > 0 else 0

    def select_best_candidate(
        self, 
        candidates: List[Dict[str, Any]], 
        original_prompt: str
    ) -> Dict[str, Any]:
        """
        选择最佳候选方案
        
        :param candidates: 候选方案列表（已按分数排序）
        :param original_prompt: 原始提示词（用于回退）
        :return: 最佳候选方案
        """
        if not candidates:
            logger.info("[选择最佳方案] 无候选方案，返回原始提示词")
            return {"prompt": original_prompt, "strategy": "none", "score": 0}
        
        best: Dict[str, Any] = candidates[0]
        logger.info(
            f"[选择最佳方案] 最终选定: '{best['strategy']}' "
            f"(评估得分: {best.get('score', 0):.4f})"
        )
        return best
