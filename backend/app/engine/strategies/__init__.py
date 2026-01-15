"""优化策略模块"""
from .base import BaseStrategy
from .boundary import BoundaryClarificationStrategy
from .instruction import InstructionRefinementStrategy
from .difficult_example_injection import DifficultExampleInjectionStrategy
from .meta_optimize import MetaOptimizationStrategy
from .context_optimize import ContextEnhancementStrategy
from .multi_intent_optimize import MultiIntentStrategy
from .domain_optimize import DomainDistinctionStrategy
from .clarification_optimize import ClarificationMechanismStrategy
from .cot_optimize import CoTReasoningStrategy
# 新增策略
from .custom_data_optimize import CustomDataOptimizationStrategy
from .global_constraint_optimize import GlobalConstraintOptimizationStrategy
from .intent_definition_optimize import IntentDefinitionOptimizationStrategy
from .query_rewrite_optimize import QueryRewriteOptimizationStrategy
from .negative_fusion_optimize import NegativeFusionOptimizationStrategy
from .output_format_optimize import OutputFormatOptimizationStrategy
from .role_task_definition_optimize import RoleTaskDefinitionStrategy

__all__ = [
    "BaseStrategy",
    "BoundaryClarificationStrategy",
    "InstructionRefinementStrategy",
    "DifficultExampleInjectionStrategy",
    "MetaOptimizationStrategy",
    "ContextEnhancementStrategy",
    "MultiIntentStrategy",
    "DomainDistinctionStrategy",
    "ClarificationMechanismStrategy",
    "CoTReasoningStrategy",
    # 新增策略
    "CustomDataOptimizationStrategy",
    "GlobalConstraintOptimizationStrategy",
    "IntentDefinitionOptimizationStrategy",
    "QueryRewriteOptimizationStrategy",
    "NegativeFusionOptimizationStrategy",
    "OutputFormatOptimizationStrategy",
    "RoleTaskDefinitionStrategy",
]

