"""多策略优化引擎模块"""
from .diagnosis import diagnose_prompt_performance
from .strategy_matcher import StrategyMatcher, STRATEGY_PRESETS, STRATEGY_CLASSES
from .multi_strategy import MultiStrategyOptimizer
from .prompt_rewriter import PromptRewriter
from .fewshot_selector import FewShotSelector
from .strategies import (
    BaseStrategy,
    BoundaryClarificationStrategy,
    InstructionRefinementStrategy,
    DifficultExampleInjectionStrategy,
    MetaOptimizationStrategy
)

__all__ = [
    # 主要类
    "MultiStrategyOptimizer",
    "StrategyMatcher",
    "PromptRewriter",
    "FewShotSelector",
    
    # 诊断
    "diagnose_prompt_performance",
    
    # 策略
    "BaseStrategy",
    "BoundaryClarificationStrategy",
    "InstructionRefinementStrategy",
    "DifficultExampleInjectionStrategy",
    "MetaOptimizationStrategy",
    
    # 常量
    "STRATEGY_PRESETS",
    "STRATEGY_CLASSES"
]
