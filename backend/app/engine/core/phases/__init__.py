"""
优化流程阶段模块

将优化流程分解为独立的阶段函数
"""

from .analysis import (
    init_knowledge_base,
    parallel_analysis,
    advanced_diagnosis,
    deep_intent_analysis,
    filter_and_prepare,
    load_error_history,
)

from .preparation import enrich_with_reasons, load_extraction_rule

from .execution import (
    match_strategies,
    generate_candidates,
    select_best,
    inject_persistent_knowledge
)

from .finalization import (
    record_knowledge,
    validate_result,
    update_history,
    build_final_result,
    generate_optimization_summary
)

__all__ = [
    # 分析阶段
    "init_knowledge_base",
    "parallel_analysis",
    "advanced_diagnosis",
    "deep_intent_analysis",
    "filter_and_prepare",
    "load_error_history",
    
    # 执行阶段
    "match_strategies",
    "generate_candidates",
    "select_best",
    "inject_persistent_knowledge",
    
    # 收尾阶段
    "record_knowledge",
    "validate_result",
    "update_history",
    "build_final_result",
    "generate_optimization_summary",
    "enrich_with_reasons",
    "load_extraction_rule"
]
