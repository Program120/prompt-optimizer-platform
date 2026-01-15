"""
优化流程分析阶段

包含诊断、意图分析、高级诊断等分析相关的阶段方法
"""
import asyncio
from typing import Dict, Any, List

from loguru import logger

from ..models import OptimizationContext
from ...diagnosis.service import diagnose_prompt_performance
from ...helpers.knowledge import OptimizationKnowledgeBase
from ...helpers.error_history import (
    filter_clarification_samples,
    identify_persistent_errors
)


async def init_knowledge_base(
    ctx: OptimizationContext,
    knowledge_base_ref: List[Any]
) -> None:
    """
    阶段 0：初始化知识库
    
    :param ctx: 优化上下文
    :param knowledge_base_ref: 知识库引用列表（用于保存实例）
    """
    if ctx.project_id:
        kb = OptimizationKnowledgeBase(ctx.project_id)
        knowledge_base_ref.append(kb)
        logger.info(f"步骤 0: 初始化知识库 (项目ID: {ctx.project_id})")


async def parallel_analysis(
    ctx: OptimizationContext,
    llm_client: Any,
    model_config: Dict[str, Any],
    intent_analyzer: Any
) -> None:
    """
    阶段 1&2：并行执行诊断分析和意图分析
    
    :param ctx: 优化上下文
    :param llm_client: LLM 客户端
    :param model_config: 模型配置
    :param intent_analyzer: 意图分析器实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在执行诊断与意图分析...")
    
    logger.info(
        f"步骤 1&2: 并行执行诊断分析和意图分析... "
        f"(错误样本数: {len(ctx.errors)})"
    )
    logger.debug(
        f"提示词上下文: {ctx.prompt[:100]}... "
        f"(总长度: {len(ctx.prompt)})"
    )
    
    loop = asyncio.get_running_loop()
    
    async def run_diagnosis() -> Dict[str, Any]:
        return await loop.run_in_executor(
            None,
            lambda: diagnose_prompt_performance(
                ctx.prompt, 
                ctx.errors, 
                ctx.total_count,
                llm_client=llm_client,
                model_config=model_config,
                project_id=ctx.project_id
            )
        )
    
    async def run_intent_analysis() -> Dict[str, Any]:
        return await loop.run_in_executor(
            None,
            lambda: intent_analyzer.analyze_errors_by_intent(
                ctx.errors, 
                ctx.total_count
            )
        )
    
    logger.info("[并发优化] 并行启动诊断分析和意图分析...")
    try:
        ctx.diagnosis_raw, ctx.intent_analysis = await asyncio.gather(
            run_diagnosis(),
            run_intent_analysis()
        )
    except Exception as e:
        logger.error(f"[并发优化] 诊断或意图分析失败: {e}")
        raise
    
    # 记录诊断结果
    metrics: Dict[str, Any] = ctx.diagnosis_raw.get('overall_metrics', {})
    error_patterns: Dict[str, Any] = ctx.diagnosis_raw.get('error_patterns', {})
    
    logger.info(
        f"诊断完成: 准确率={metrics.get('accuracy', 0):.4f} "
        f"({metrics.get('error_count', 0)}/{metrics.get('total_count', 0)} 错误/总数)"
    )
    logger.info(f"主要错误模式: {list(error_patterns.keys())}")
    
    if error_patterns.get('confusion_pairs'):
        logger.debug(f"Top 混淆对: {error_patterns['confusion_pairs'][:3]}")
    if error_patterns.get('category_distribution'):
        logger.debug(
            f"错误分布 Top 3: "
            f"{dict(list(error_patterns['category_distribution'].items())[:3])}"
        )


async def advanced_diagnosis(
    ctx: OptimizationContext,
    advanced_diagnoser: Any
) -> None:
    """
    阶段 2.5：高级定向分析
    
    :param ctx: 优化上下文
    :param advanced_diagnoser: 高级诊断器实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在执行高级定向分析...")
    
    logger.info("步骤 2.5: 启动高级定向分析...")
    
    all_intents: List[str] = [
        i["intent"] for i in ctx.intent_analysis.get("top_failing_intents", [])
    ]
    
    try:
        ctx.advanced_diagnosis = await advanced_diagnoser.run_all_diagnoses(
            ctx.errors,
            all_intents,
            should_stop=ctx.should_stop
        )
    except Exception as e:
        logger.error(f"高级定向分析执行失败: {e}")
        # 不阻断流程，赋予空字典
        ctx.advanced_diagnosis = {}
    
    # 记录高级诊断摘要
    for diag_key, res in ctx.advanced_diagnosis.items():
        if isinstance(res, dict) and res.get("has_issue"):
            logger.info(f"高级诊断报告 - {diag_key}: 发现潜在问题")
            if "referential_error_ratio" in res:
                logger.debug(f"  - 指代错误率: {res['referential_error_ratio']:.2%}")
            if "false_negative_rate" in res:
                logger.debug(f"  - 多意图漏判率: {res['false_negative_rate']:.2%}")
            if "summary" in res:
                logger.debug(f"  - 领域分析总结: {res['summary']}")
            if "missing_rate" in res:
                logger.debug(f"  - 缺失澄清率: {res['missing_rate']:.2%}")


async def deep_intent_analysis(
    ctx: OptimizationContext,
    intent_analyzer: Any
) -> None:
    """
    阶段 3：Top 失败意图深度分析
    
    :param ctx: 优化上下文
    :param intent_analyzer: 意图分析器实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在执行深度意图分析...")
    
    logger.info("步骤 3: Top 失败意图深度分析...")
    logger.debug(f"开始分析 Top 3 失败意图，错误样本数: {len(ctx.errors)}")
    
    try:
        ctx.deep_analysis = await intent_analyzer.deep_analyze_top_failures(
            ctx.errors, 
            top_n=3,
            should_stop=ctx.should_stop
        )
    except Exception as e:
        logger.error(f"深度意图分析失败: {e}")
        ctx.deep_analysis = {}
        return
    
    # 记录深度分析结果
    analyzed_count: int = ctx.deep_analysis.get("analyzed_count", 0)
    logger.info(f"深度分析完成，共分析 {analyzed_count} 个意图")
    
    if ctx.deep_analysis.get("analyses"):
        for intent_res in ctx.deep_analysis["analyses"]:
            intent_name: str = intent_res.get('intent', '未知')
            analysis_text: str = intent_res.get('analysis', '')
            error_rate: float = intent_res.get('error_rate', 0)
            
            if not analysis_text or analysis_text.strip() == '':
                logger.warning(f"意图 '{intent_name}' 根因分析结果为空！")
            elif analysis_text.startswith('分析失败'):
                logger.warning(
                    f"意图 '{intent_name}' 根因分析失败: {analysis_text[:100]}..."
                )
            else:
                logger.debug(
                    f"意图 '{intent_name}' (错误率: {error_rate:.1%}) "
                    f"根因分析: {analysis_text[:150]}..."
                )
    else:
        logger.warning("深度分析未返回任何分析结果！请检查 LLM 调用是否正常。")


def filter_and_prepare(ctx: OptimizationContext) -> None:
    """
    阶段 3.5：澄清意图过滤与顽固错误识别
    
    :param ctx: 优化上下文
    """
    clarification_analysis: Dict[str, Any] = ctx.advanced_diagnosis.get(
        "clarification_analysis", {}
    )
    
    # 显式类型转换或断言，确保存储的是符合预期的列表
    filtered: tuple[List[Any], List[Any]] = filter_clarification_samples(
        ctx.errors, clarification_analysis
    )
    ctx.main_errors, ctx.low_priority_errors = filtered
    
    if not ctx.main_errors and ctx.errors:
        logger.warning("[澄清过滤] 主要优化样本为空，使用原始错误列表")
        ctx.main_errors = ctx.errors
    
    ctx.optimized_intents = [
        i.get("intent", "") 
        for i in ctx.intent_analysis.get("top_failing_intents", [])[:3]
    ]
    logger.info(f"已选定需要优化的意图: {ctx.optimized_intents}")


async def load_error_history(
    ctx: OptimizationContext
) -> None:
    """
    阶段 3.6：加载错误历史并识别顽固错误
    
    :param ctx: 优化上下文
    """
    if not ctx.project_id:
        logger.debug("未提供项目ID，跳过错误历史加载。")
        return
    
    try:
        from app.db.storage import get_error_optimization_history
        ctx.error_history = get_error_optimization_history(ctx.project_id)
        
        if ctx.error_history:
            ctx.persistent_samples = identify_persistent_errors(ctx.error_history)
            logger.info(f"已加载错误历史，识别出 {len(ctx.persistent_samples)} 个顽固错误样本。")
    except ImportError:
        logger.error("无法导入 storage 模块，跳过错误历史加载。")
    except Exception as e:
        logger.error(f"加载错误历史时发生异常: {e}")
