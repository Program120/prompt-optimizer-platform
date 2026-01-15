"""多策略优化引擎模块"""
from .diagnosis import diagnose_prompt_performance
from .strategy_matcher import StrategyMatcher, STRATEGY_PRESETS, STRATEGY_CLASSES
from .multi_strategy import MultiStrategyOptimizer
from .prompt_rewriter import PromptRewriter
from .fewshot_selector import FewShotSelector
from .knowledge_base import OptimizationKnowledgeBase
from .intent_analyzer import IntentAnalyzer
from .advanced_diagnosis import AdvancedDiagnoser
from .strategies import (
    BaseStrategy,
    BoundaryClarificationStrategy,
    InstructionRefinementStrategy,
    DifficultExampleInjectionStrategy,
    MetaOptimizationStrategy,
    ContextEnhancementStrategy,
    MultiIntentStrategy,
    DomainDistinctionStrategy,
    ClarificationMechanismStrategy
)

__all__ = [
    # 主要类
    "MultiStrategyOptimizer",
    "StrategyMatcher",
    "PromptRewriter",
    "FewShotSelector",
    "OptimizationKnowledgeBase",
    "IntentAnalyzer",
    "AdvancedDiagnoser",
    
    # 诊断
    "diagnose_prompt_performance",
    
    # 策略
    "BaseStrategy",
    "BoundaryClarificationStrategy",
    "InstructionRefinementStrategy",
    "DifficultExampleInjectionStrategy",
    "MetaOptimizationStrategy",
    "ContextEnhancementStrategy",
    "MultiIntentStrategy",
    "DomainDistinctionStrategy",
    "ClarificationMechanismStrategy",
    
    # 常量
    "STRATEGY_PRESETS",
    "STRATEGY_CLASSES"
]

