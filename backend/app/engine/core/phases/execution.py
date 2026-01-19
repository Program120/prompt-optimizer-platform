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
    prompt_evaluator: Any,
    llm_client: Any = None,
    model_config: Optional[Dict[str, Any]] = None
) -> None:
    """
    阶段 5：候选生成与快速筛选
    
    :param ctx: 优化上下文
    :param candidate_generator: 候选生成器实例
    :param prompt_evaluator: 提示词评估器实例
    :param llm_client: LLM 客户端（用于评估策略必要性）
    :param model_config: 模型配置
    """
    if not ctx.strategies:
        logger.warning("未匹配到任何策略，跳过候选生成。")
        return

    if ctx.on_progress:
        ctx.on_progress(f"正在生成优化候选方案 (应用策略数: {len(ctx.strategies)})...")
    logger.info(f"步骤 5: 候选生成... (应用策略数: {len(ctx.strategies)})")
    
    try:
        # 使用串行模式：每个策略依次应用到前一个策略的输出上
        # 传入 llm_client 和 model_config 用于评估每个策略的必要性
        ctx.candidates = await candidate_generator.generate_candidates_serial(
            ctx.prompt, 
            ctx.strategies, 
            ctx.errors, 
            ctx.get_diagnosis_dict(), 
            ctx.dataset or ctx.errors, 
            ctx.should_stop,
            llm_client=llm_client,
            model_config=model_config
        )
    except Exception as e:
        logger.error(f"候选生成失败: {e}")
        ctx.candidates = []
        return

    # [临时注释] 阶段 5.1：构建混合验证集并快速筛选 - 跳过策略打分验证
    # try:
    #     validation_set: List[Dict[str, Any]] = prompt_evaluator.build_validation_set(
    #         errors=ctx.errors,
    #         dataset=ctx.dataset or ctx.errors,
    #         target_error_count=40,
    #         correct_error_ratio=1.5
    #     )
    #     ctx.validation_set = validation_set
    # 
    #     if ctx.on_progress:
    #         ctx.on_progress("正在快速评估候选方案...")
    #     logger.info(
    #         f"步骤 5.1: 快速筛选... "
    #         f"(候选方案数: {len(ctx.candidates)}, 验证集大小: {len(validation_set)})"
    #     )
    #     
    #     ctx.filtered_candidates = await prompt_evaluator.rapid_evaluation(
    #         ctx.candidates, validation_set, ctx.should_stop, ctx.extraction_rule
    #     )
    # except Exception as e:
    #     logger.error(f"快速评估筛选候选方案失败: {e}")
    #     ctx.filtered_candidates = ctx.candidates
    
    # 临时逻辑：跳过筛选，直接使用所有候选方案
    ctx.filtered_candidates = ctx.candidates
    
    if ctx.filtered_candidates:
        logger.info(
            f"候选方案（跳过评分）: "
            f"{[c.get('strategy', 'unknown') for c in ctx.filtered_candidates]}"
        )


async def select_best(
    ctx: OptimizationContext,
    prompt_evaluator: Any
) -> None:
    """
    阶段 6：合并所有策略方案（临时修改：应用所有选中策略，不做评分选择）
    
    :param ctx: 优化上下文
    :param prompt_evaluator: 提示词评估器实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在合并所有策略方案...")
    logger.info("步骤 6: 合并所有策略方案（临时：应用所有选中策略）...")
    
    if not ctx.filtered_candidates:
        logger.warning("没有可供合并的候选方案。")
        return
    
    # 临时逻辑：合并所有候选方案的提示词
    # 以第一个候选方案为基础，依次合并其他方案的优化内容
    if len(ctx.filtered_candidates) == 1:
        # 只有一个候选，直接使用
        ctx.best_result = ctx.filtered_candidates[0]
        ctx.strategy_selection_reason = f"仅 1 个策略: {ctx.filtered_candidates[0].get('strategy')}"
    else:
        # 多个候选，依次应用所有策略
        # 策略名称列表
        strategy_names: List[str] = [c.get('strategy', 'unknown') for c in ctx.filtered_candidates]
        
        # 使用最后一个候选的提示词作为最终结果（因为策略是串行应用的）
        # 注意：这里假设 candidate_generator 已经按顺序串行应用了所有策略
        # 如果实际是并行生成的，需要实现真正的合并逻辑
        final_candidate: Dict[str, Any] = ctx.filtered_candidates[-1].copy()
        final_candidate["strategy"] = " + ".join(strategy_names)
        final_candidate["applied_strategies"] = strategy_names
        
        ctx.best_result = final_candidate
        ctx.strategy_selection_reason = f"合并应用了 {len(strategy_names)} 个策略: {', '.join(strategy_names)}"
        
        logger.info(f"[策略合并] 合并了 {len(strategy_names)} 个策略: {strategy_names}")


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
    
    # [DEBUG-START] 添加调试日志 - 检查顽固案例注入流程
    logger.debug(
        f"[DEBUG] inject_persistent_knowledge 检查: hard_cases数={len(hard_cases)}, "
        f"has_persistent={has_persistent}, current_strategy={current_strategy_name}"
    )
    persistent_cases: List[Dict[str, Any]] = [c for c in hard_cases if c.get("_persistent")]
    if persistent_cases:
        logger.debug(f"[DEBUG] 顽固案例详情: {[c.get('query', '')[:30] for c in persistent_cases[:3]]}")
    # [DEBUG-END]
    
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
                
                if ctx.strategy_selection_reason:
                    ctx.strategy_selection_reason += " (已追加顽固困难样本注入增强)"
            else:
                logger.info("[顽固样本处理] 二次注入未产生变化")
                 
        except Exception as e:
            logger.error(f"[顽固样本处理] 二次注入执行失败: {e}")
