"""
优化流程执行阶段

包含策略匹配、候选生成、最佳方案选择等执行相关的阶段方法
"""
import asyncio
from typing import Dict, Any, List, Optional

from loguru import logger

from ..models import OptimizationContext


async def match_strategies(
    ctx: OptimizationContext,
    matcher: Any,
    llm_client: Any,
    model_config: Dict[str, Any],
    semaphore: asyncio.Semaphore
) -> None:
    """
    阶段 4：策略匹配
    
    :param ctx: 优化上下文
    :param matcher: 策略匹配器实例
    :param llm_client: LLM 客户端
    :param model_config: 模型配置
    :param semaphore: 并发控制信号量
    """
    if ctx.on_progress:
        ctx.on_progress("正在匹配优化策略...")
    logger.info("步骤 4: 策略匹配...")
    
    use_negative_fusion: bool = False
    
    if use_negative_fusion:
        from ..matcher import STRATEGY_CLASSES
        negative_fusion_class = STRATEGY_CLASSES.get("negative_fusion_optimization")
        if negative_fusion_class:
            ctx.strategies = [negative_fusion_class(
                llm_client=llm_client,
                model_config=model_config,
                semaphore=semaphore
            )]
            logger.info(f"[负向融合策略] 已强制选中: {[s.name for s in ctx.strategies]}")
        else:
            logger.warning("[负向融合策略] 未找到负向优化融合策略类，回退到自动匹配")
            # 递归或回退
            ctx.strategies = await matcher.match_strategies(
                diagnosis=ctx.get_diagnosis_dict(),
                max_strategies=ctx.max_strategies,
                selected_modules=ctx.selected_modules,
                should_stop=ctx.should_stop
            )
    elif hasattr(matcher, 'get_preset_strategies') and ctx.strategy_mode != 'auto':
        # 预设模式
        ctx.strategies = matcher.get_preset_strategies(ctx.strategy_mode)[:ctx.max_strategies]
        logger.info(f"根据预设模式 '{ctx.strategy_mode}' 匹配策略: {[s.name for s in ctx.strategies]}")
    else:
        # 自动匹配
        try:
            ctx.strategies = await matcher.match_strategies(
                diagnosis=ctx.get_diagnosis_dict(),
                max_strategies=ctx.max_strategies,
                selected_modules=ctx.selected_modules,
                should_stop=ctx.should_stop
            )
        except Exception as e:
            logger.error(f"策略匹配过程发生异常: {e}")
            ctx.strategies = []
            
        if ctx.selected_modules and len(ctx.selected_modules) > 0:
            logger.info(f"自动匹配策略（已过滤模块 {ctx.selected_modules}）: {[s.name for s in ctx.strategies]}")
        else:
            logger.info(f"自动匹配策略: {[s.name for s in ctx.strategies]}")


async def generate_candidates(
    ctx: OptimizationContext,
    candidate_generator: Any,
    prompt_evaluator: Any
) -> None:
    """
    阶段 5：候选生成与快速筛选
    
    :param ctx: 优化上下文
    :param candidate_generator: 候选生成器实例
    :param prompt_evaluator: 提示词评估器实例
    """
    if not ctx.strategies:
        logger.warning("未匹配到任何策略，跳过候选生成。")
        return

    if ctx.on_progress:
        ctx.on_progress(f"正在生成优化候选方案 (应用策略数: {len(ctx.strategies)})...")
    logger.info(f"步骤 5: 候选生成... (应用策略数: {len(ctx.strategies)})")
    
    try:
        ctx.candidates = await candidate_generator.generate_candidates(
            ctx.prompt, 
            ctx.strategies, 
            ctx.errors, 
            ctx.get_diagnosis_dict(), 
            ctx.dataset or ctx.errors, 
            ctx.should_stop
        )
    except Exception as e:
        logger.error(f"候选生成失败: {e}")
        ctx.candidates = []
        return

    # 阶段 5.1：构建混合验证集并快速筛选
    try:
        validation_set: List[Dict[str, Any]] = prompt_evaluator.build_validation_set(
            errors=ctx.errors,
            dataset=ctx.dataset or ctx.errors,
            target_error_count=40,
            correct_error_ratio=1.5
        )
        
        if ctx.on_progress:
            ctx.on_progress("正在快速评估候选方案...")
        logger.info(
            f"步骤 5.1: 快速筛选... "
            f"(候选方案数: {len(ctx.candidates)}, 验证集大小: {len(validation_set)})"
        )
        
        ctx.filtered_candidates = await prompt_evaluator.rapid_evaluation(
            ctx.candidates, validation_set, ctx.should_stop
        )
    except Exception as e:
        logger.error(f"快速评估筛选候选方案失败: {e}")
        ctx.filtered_candidates = ctx.candidates # 回退策略
    
    if ctx.filtered_candidates:
        logger.info(
            f"筛选后的候选方案及其评分: "
            f"{[(c.get('strategy', 'unknown'), round(c.get('score', 0), 4)) for c in ctx.filtered_candidates]}"
        )


async def select_best(
    ctx: OptimizationContext,
    prompt_evaluator: Any
) -> None:
    """
    阶段 6：选择最佳方案
    
    :param ctx: 优化上下文
    :param prompt_evaluator: 提示词评估器实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在选择最佳方案...")
    logger.info("步骤 6: 选择最佳方案...")
    
    skip_selection: bool = False
    skip_reason: str = ""
    
    if len(ctx.filtered_candidates) == 1:
        skip_selection = True
        skip_reason = f"仅 1 个候选方案 ({ctx.filtered_candidates[0].get('strategy')})"
    elif not ctx.filtered_candidates:
        logger.warning("没有可供选择的候选方案。")
        return
    
    if skip_selection and ctx.filtered_candidates:
        logger.info(f"[选择最佳方案] {skip_reason}，跳过选择步骤，直接使用")
        ctx.best_result = ctx.filtered_candidates[0]
    else:
        try:
            ctx.best_result = prompt_evaluator.select_best_candidate(
                ctx.filtered_candidates, ctx.prompt
            )
        except Exception as e:
            logger.error(f"选择最佳方案时发生异常: {e}, 默认选择第一个。")
            ctx.best_result = ctx.filtered_candidates[0]


async def inject_persistent_knowledge(
    ctx: OptimizationContext,
    llm_client: Any,
    model_config: Dict[str, Any],
    semaphore: asyncio.Semaphore
) -> None:
    """
    阶段 6.5：顽固困难样本二次注入
    
    :param ctx: 优化上下文
    :param llm_client: LLM 客户端
    :param model_config: 模型配置
    :param semaphore: 并发控制信号量
    """
    from ...strategies.difficult_example_injection import DifficultExampleInjectionStrategy
    
    hard_cases: List[Dict[str, Any]] = ctx.diagnosis_raw.get("error_patterns", {}).get("hard_cases", [])
    has_persistent: bool = any(c.get("_persistent") for c in hard_cases)
    current_strategy_name: str = str(ctx.best_result.get("strategy", ""))
    
    if has_persistent and current_strategy_name != "difficult_example_injection":
        if ctx.on_progress:
            ctx.on_progress("正在执行困难样本注入...")
        logger.info(
            f"[顽固样本处理] 检测到顽固困难样本，且当前策略({current_strategy_name})非注入策略，"
            f"尝试二次优化..."
        )
        
        try:
            injection_strategy = DifficultExampleInjectionStrategy(
                llm_client=llm_client,
                model_config=model_config,
                semaphore=semaphore
            )
            
            current_best_prompt: str = ctx.best_result.get("prompt", ctx.prompt)
            
            injected_prompt: str = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: injection_strategy.apply(
                    current_best_prompt, 
                    ctx.errors, 
                    ctx.get_diagnosis_dict()
                )
            )
            
            if injected_prompt != current_best_prompt:
                logger.info("[顽固样本处理] 二次注入成功，更新最佳提示词")
                ctx.best_result["prompt"] = injected_prompt
                ctx.best_result["strategy"] = f"{current_strategy_name} + difficult_injection"
                ctx.best_result["injected_difficult_cases"] = True
            else:
                logger.info("[顽固样本处理] 二次注入未产生变化")
                 
        except Exception as e:
            logger.error(f"[顽固样本处理] 二次注入执行失败: {e}")
