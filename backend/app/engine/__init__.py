"""多策略优化引擎模块"""

# Core Components
from .core.pipeline import MultiStrategyOptimizer
from .core.matcher import StrategyMatcher, STRATEGY_PRESETS, STRATEGY_CLASSES
from .core.models import (
    OptimizationContext,
    OptimizationResult,
    DiagnosisResult,
    OverallMetrics,
    ErrorPatterns,
    CandidateResult,
    IntentAnalysisResult,
    DeepAnalysisResult,
    AdvancedDiagnosisResult
)

# Diagnosis Components
from .diagnosis.service import diagnose_prompt_performance
from .diagnosis.intent import IntentAnalyzer
from .diagnosis.advanced import AdvancedDiagnoser
from .diagnosis.detectors import (
    detect_examples_in_prompt,
    detect_constraints_in_prompt,
    detect_cot_in_prompt
)

# Helper Components
from .helpers.rewriter import PromptRewriter
from .helpers.fewshot import FewShotSelector
from .helpers.knowledge import OptimizationKnowledgeBase
from .helpers.error_history import (
    update_error_optimization_history,
    identify_persistent_errors,
    filter_clarification_samples,
    inject_persistent_errors_to_hard_cases,
    prepare_persistent_errors_for_knowledge_base
)

# Strategies
from .strategies.base import BaseStrategy
from .strategies.boundary import BoundaryClarificationStrategy
from .strategies.instruction import InstructionRefinementStrategy
from .strategies.difficult_example_injection import DifficultExampleInjectionStrategy
from .strategies.meta_optimize import MetaOptimizationStrategy
from .strategies.context_optimize import ContextEnhancementStrategy
from .strategies.multi_intent_optimize import MultiIntentStrategy
from .strategies.domain_optimize import DomainDistinctionStrategy
from .strategies.clarification_optimize import ClarificationMechanismStrategy

__all__ = [
    # Core
    "MultiStrategyOptimizer",
    "StrategyMatcher",
    
    # Helpers
    "PromptRewriter",
    "FewShotSelector",
    "OptimizationKnowledgeBase",
    
    # Diagnosis
    "IntentAnalyzer",
    "AdvancedDiagnoser",
    "diagnose_prompt_performance",
    "detect_examples_in_prompt",
    "detect_constraints_in_prompt",
    "detect_cot_in_prompt",
    
    # Models
    "OptimizationContext",
    "OptimizationResult",
    "DiagnosisResult",
    "OverallMetrics",
    "ErrorPatterns",
    "CandidateResult",
    "IntentAnalysisResult",
    "DeepAnalysisResult",
    "AdvancedDiagnosisResult",
    
    # Error History
    "update_error_optimization_history",
    "identify_persistent_errors",
    "filter_clarification_samples",
    "inject_persistent_errors_to_hard_cases",
    "prepare_persistent_errors_for_knowledge_base",
    
    # Strategies
    "BaseStrategy",
    "BoundaryClarificationStrategy",
    "InstructionRefinementStrategy",
    "DifficultExampleInjectionStrategy",
    "MetaOptimizationStrategy",
    "ContextEnhancementStrategy",
    "MultiIntentStrategy",
    "DomainDistinctionStrategy",
    "ClarificationMechanismStrategy",
    
    # Constants
    "STRATEGY_PRESETS",
    "STRATEGY_CLASSES"
]
