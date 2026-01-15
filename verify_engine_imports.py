
import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from loguru import logger

logger.info("Starting verification...")

try:
    from app.engine.core.pipeline import MultiStrategyOptimizer
    from app.engine.core.models import OptimizationContext
    from app.engine.strategies import (
        BaseStrategy,
        MetaOptimizationStrategy,
        NegativeFusionOptimizationStrategy,
        OutputFormatOptimizationStrategy,
        RoleTaskDefinitionStrategy,
        BoundaryClarificationStrategy,
        InstructionRefinementStrategy,
        DifficultExampleInjectionStrategy,
        ContextEnhancementStrategy,
        MultiIntentStrategy,
        DomainDistinctionStrategy,
        ClarificationMechanismStrategy,
        CoTReasoningStrategy,
        CustomDataOptimizationStrategy,
        GlobalConstraintOptimizationStrategy,
        IntentDefinitionOptimizationStrategy,
        QueryRewriteOptimizationStrategy
    )
    from app.engine.diagnosis.service import diagnose_prompt_performance
    from app.engine.helpers.llm import LLMHelper
    
    logger.info("All modules imported successfully!")
    
    # Check if we can instantiate optional components
    optimizer = MultiStrategyOptimizer()
    logger.info("MultiStrategyOptimizer instantiated successfully!")

except ImportError as e:
    logger.error(f"Import Error: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Unexpected Error: {e}")
    sys.exit(1)
