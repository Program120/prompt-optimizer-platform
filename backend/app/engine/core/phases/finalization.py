"""
优化流程收尾阶段

包含知识库记录、验证、历史更新、结果构建等收尾相关的阶段方法
"""
from typing import Dict, Any, List, Callable

from loguru import logger

from ..models import OptimizationContext
from ...helpers.validator import PromptValidator
from ...helpers.error_history import update_error_optimization_history


async def record_knowledge(
    ctx: OptimizationContext,
    knowledge_base: Any,
    generate_summary_func: Callable[..., str]
) -> None:
    """
    阶段 7：记录到知识库
    
    :param ctx: 优化上下文
    :param knowledge_base: 知识库实例
    :param generate_summary_func: 生成优化总结的函数
    """
    if not knowledge_base:
        return

    if ctx.on_progress:
        ctx.on_progress("正在保存知识库记录...")
    logger.info("步骤 7: 记录优化结果到知识库...")
    
    accuracy: float = ctx.get_diagnosis_dict().get("overall_metrics", {}).get("accuracy", 0.0)
    
    analysis_summary: str = generate_summary_func(
        ctx.intent_analysis, 
        ctx.deep_analysis,
        ctx.best_result.get("strategy", "unknown"),
        ctx.advanced_diagnosis
    )

    applied_strategies: List[str] = [
        c.get("strategy", "unknown") for c in ctx.filtered_candidates
    ]
    
    current_persistent_errors_list: List[Dict[str, Any]] = []
    
    if ctx.project_id and ctx.optimized_intents:
        try:
            temp_updated_history = update_error_optimization_history(
                ctx.errors, 
                ctx.error_history, 
                ctx.optimized_intents
            )
            
            for hash_key, val in temp_updated_history.items():
                val_copy = val.copy()
                val_copy['hash_key'] = hash_key
                current_persistent_errors_list.append(val_copy)
            
            current_persistent_errors_list.sort(
                key=lambda x: x.get("optimization_count", 0), 
                reverse=True
            )
            
        except Exception as e:
            logger.warning(f"准备错误历史数据失败: {e}")

    difficult_cases: List[Dict[str, Any]] = ctx.diagnosis_raw.get("error_patterns", {}).get("hard_cases", [])

    try:
        knowledge_base.record_optimization(
            original_prompt=ctx.prompt,
            optimized_prompt=ctx.best_result.get("prompt", ctx.prompt),
            analysis_summary=analysis_summary,
            intent_analysis=ctx.intent_analysis,
            applied_strategies=applied_strategies,
            accuracy_before=accuracy,
            deep_analysis=ctx.deep_analysis,
            newly_failed_cases=ctx.newly_failed_cases,
            difficult_cases=difficult_cases,
            persistent_errors=current_persistent_errors_list,
            clarification_intents=ctx.intent_analysis.get("clarification_intents", []),
            multi_intent_intents=ctx.intent_analysis.get("multi_intent_intents", []),
            best_strategy=ctx.best_result.get("strategy"),
            strategy_selection_reason=ctx.strategy_selection_reason,
            validation_set=ctx.validation_set,
            # 提取候选中关于策略和分数的关键信息
            strategy_evaluations=[
                {
                    "strategy": c.get("strategy"),
                    "score": c.get("score"),
                    "prompt_len": len(c.get("prompt", "")),
                    "prompt_preview": c.get("prompt", "")[:500] + "..." if c.get("prompt") else ""
                }
                for c in ctx.filtered_candidates
            ]
        )
    except Exception as e:
        logger.error(f"记录知识库时发生异常: {e}")


async def validate_result(
    ctx: OptimizationContext,
    llm_helper: Any
) -> None:
    """
    阶段 8：验证优化后的提示词
    
    :param ctx: 优化上下文
    :param llm_helper: LLM 辅助类实例
    """
    if ctx.on_progress:
        ctx.on_progress("正在验证优化后的提示词...")
    logger.info("步骤 8: 验证优化后的提示词...")
    
    try:
        temp_validator = PromptValidator(llm_helper)
        ctx.validation_result = await temp_validator.validate_optimized_prompt(
            ctx.prompt,
            ctx.best_result.get("prompt", ctx.prompt),
            ctx.should_stop
        )
    except Exception as e:
        logger.error(f"验证提示词时发生异常: {e}")
        ctx.validation_result = {
            "is_valid": False, 
            "failure_reason": f"验证过程异常: {str(e)}", 
            "issues": []
        }


async def update_history(ctx: OptimizationContext) -> None:
    """
    阶段 9：更新错误优化历史
    
    :param ctx: 优化上下文
    """
    if not (ctx.project_id and ctx.optimized_intents):
        return

    try:
        from app.db.storage import (
            update_error_optimization_history as save_history_to_db
        )
        
        updated_history: Dict[str, Any] = update_error_optimization_history(
            ctx.errors, 
            ctx.error_history, 
            ctx.optimized_intents
        )
        
        save_history_to_db(ctx.project_id, updated_history)
        logger.info(f"[错误追踪] 已更新错误优化历史，记录数: {len(updated_history)}")
    except ImportError:
        logger.error("无法导入 storage 模块，跳过历史更新。")
    except Exception as e:
        logger.warning(f"更新错误优化历史失败: {e}")


def build_final_result(ctx: OptimizationContext) -> Dict[str, Any]:
    """
    构建最终返回结果
    
    :param ctx: 优化上下文
    :return: 优化结果字典
    """
    logger.info(
        f"优化任务结束。最终胜出策略: {ctx.best_result.get('strategy')}, "
        f"打分: {ctx.best_result.get('score', 0):.4f}"
    )
    
    optimized_prompt: str = ctx.best_result.get("prompt", ctx.prompt)
    logger.info(
        f"最终提示词摘要: {optimized_prompt[:100]}... "
        f"(总长度: {len(optimized_prompt)})"
    )
    
    result: Dict[str, Any] = {
        "optimized_prompt": optimized_prompt,
        "diagnosis": ctx.get_diagnosis_dict(),
        "intent_analysis": ctx.intent_analysis,
        "deep_analysis": ctx.deep_analysis,
        "applied_strategies": [
            {"name": c.get("strategy"), "success": True} 
            for c in ctx.filtered_candidates
        ],
        "best_strategy": ctx.best_result.get("strategy", "none"),
        "improvement": ctx.best_result.get("score", 0),
        "candidates": [
            {"strategy": c.get("strategy"), "score": c.get("score", 0)} 
            for c in ctx.filtered_candidates
        ]
    }
    
    if not ctx.validation_result.get("is_valid", True):
        logger.warning(
            f"优化结果验证失败: {ctx.validation_result.get('failure_reason')}"
        )
        result["validation_failed"] = True
        result["failure_reason"] = ctx.validation_result.get("failure_reason", "优化失败")
        result["validation_issues"] = ctx.validation_result.get("issues", [])
        
        for strategy_result in result["applied_strategies"]:
            strategy_result["validation_failed"] = True
    else:
        result["validation_failed"] = False
        result["failure_reason"] = ""
        
    return result


def generate_optimization_summary(
    intent_analysis: Dict[str, Any],
    deep_analysis: Dict[str, Any],
    best_strategy: str,
    advanced_diagnosis: Dict[str, Any] = None
) -> str:
    """
    生成优化总结文本
    
    :param intent_analysis: 意图分析结果
    :param deep_analysis: 深度分析结果
    :param best_strategy: 最佳策略名称
    :param advanced_diagnosis: 高级诊断结果
    :return: 优化总结文本
    """
    lines: List[str] = []
    
    total_errors: int = intent_analysis.get("total_errors", 0)
    lines.append(f"本次优化处理了 {total_errors} 个错误样例。")
    
    top_failures: List[Dict[str, Any]] = intent_analysis.get(
        "top_failing_intents", []
    )[:3]
    if top_failures:
        failure_names: List[str] = [f.get("intent", "") for f in top_failures]
        lines.append(f"主要失败意图: {', '.join(failure_names)}。")
        
    if advanced_diagnosis:
        issues: List[str] = []
        if advanced_diagnosis.get("context_analysis", {}).get("has_issue"):
            issues.append("上下文指代不明")
        if advanced_diagnosis.get("multi_intent_analysis", {}).get("has_issue"):
            issues.append("多意图混淆")
        if advanced_diagnosis.get("domain_analysis", {}).get("domain_confusion"):
            issues.append("领域界限模糊")
        if advanced_diagnosis.get("clarification_analysis", {}).get("has_issue"):
            issues.append("澄清机制异常")
            
        if issues:
            lines.append(f"发现以下定向问题: {', '.join(issues)}。")
        
    analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])
    if analyses:
        lines.append(f"对 {len(analyses)} 个高失败率意图进行了深度分析。")
        
    lines.append(f"采用了 {best_strategy} 策略进行优化。")
    
    return " ".join(lines)
