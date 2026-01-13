"""策略匹配器 - 基于诊断结果匹配优化策略"""
from typing import List, Dict, Any, Type
from .strategies.base import BaseStrategy
from .strategies.boundary import BoundaryClarificationStrategy
from .strategies.instruction import InstructionRefinementStrategy
from .strategies.example_injection import DifficultExampleInjectionStrategy
from .strategies.meta_optimize import MetaOptimizationStrategy
from .strategies.context_optimize import ContextEnhancementStrategy
from .strategies.multi_intent_optimize import MultiIntentStrategy
from .strategies.domain_optimize import DomainDistinctionStrategy
from .strategies.clarification_optimize import ClarificationMechanismStrategy
from .strategies.cot_optimize import CoTReasoningStrategy


# 策略组合预设
STRATEGY_PRESETS = {
    "initial": [  # 初始优化
        {"type": "instruction_refinement", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ],
    "precision_focus": [  # 精确率优先
        {"type": "boundary_clarification", "priority": 1},
        {"type": "instruction_refinement", "priority": 2}
    ],
    "recall_focus": [  # 召回率优先
        {"type": "difficult_example_injection", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ],
    "advanced": [  # 高级优化
        {"type": "boundary_clarification", "priority": 1},
        {"type": "difficult_example_injection", "priority": 2},
        {"type": "meta_optimization", "priority": 3}
    ],
    "auto_directed": [ # 自动定向优化 (新模式)
        {"type": "context_enhancement", "priority": 1},
        {"type": "multi_intent_optimization", "priority": 1},
        {"type": "domain_distinction", "priority": 1},
        {"type": "clarification_mechanism", "priority": 1},
        {"type": "cot_reasoning", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ]
}

# 策略类型映射
STRATEGY_CLASSES: Dict[str, Type[BaseStrategy]] = {
    "boundary_clarification": BoundaryClarificationStrategy,
    "instruction_refinement": InstructionRefinementStrategy,
    "difficult_example_injection": DifficultExampleInjectionStrategy,
    "meta_optimization": MetaOptimizationStrategy,
    "context_enhancement": ContextEnhancementStrategy,
    "multi_intent_optimization": MultiIntentStrategy,
    "domain_distinction": DomainDistinctionStrategy,
    "clarification_mechanism": ClarificationMechanismStrategy,
    "cot_reasoning": CoTReasoningStrategy
}



class StrategyMatcher:
    """策略匹配器 - 基于诊断结果选择最适合的优化策略"""
    
    def __init__(self, llm_client=None, model_config: Dict[str, Any] = None):
        self.llm_client = llm_client
        self.model_config = model_config or {}
    
    def match_strategies(
        self, 
        diagnosis: Dict[str, Any],
        max_strategies: int = 1
    ) -> List[BaseStrategy]:
        """
        基于诊断结果匹配合适的优化策略
        
        Args:
            diagnosis: 诊断分析结果
            max_strategies: 最多返回的策略数量
            
        Returns:
            策略实例列表（按优先级排序）
        """
        candidates = []
        
        # 获取所有策略类并评估适用性
        for name, strategy_class in STRATEGY_CLASSES.items():
            strategy = strategy_class(
                llm_client=self.llm_client,
                model_config=self.model_config
            )
            
            if strategy.is_applicable(diagnosis):
                priority = strategy.get_priority(diagnosis)
                candidates.append((priority, strategy))
        
        # 按优先级降序排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 返回前 N 个策略
        return [strategy for _, strategy in candidates[:max_strategies]]
    
    def get_preset_strategies(
        self, 
        preset: str
    ) -> List[BaseStrategy]:
        """
        获取预设策略组合
        
        Args:
            preset: 预设名称 (initial, precision_focus, recall_focus, advanced)
            
        Returns:
            策略实例列表
        """
        preset_config = STRATEGY_PRESETS.get(preset, STRATEGY_PRESETS["initial"])
        strategies = []
        
        for config in preset_config:
            strategy_type = config["type"]
            if strategy_type in STRATEGY_CLASSES:
                strategy = STRATEGY_CLASSES[strategy_type](
                    llm_client=self.llm_client,
                    model_config=self.model_config
                )
                strategies.append(strategy)
        
        return strategies
    
    def auto_select_preset(self, diagnosis: Dict[str, Any]) -> str:
        """根据诊断结果自动选择预设"""
        accuracy = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
        confusion_pairs = diagnosis.get("error_patterns", {}).get("confusion_pairs", [])
        instruction_clarity = diagnosis.get("prompt_analysis", {}).get("instruction_clarity", 1.0)
        
        # 决策逻辑
        if accuracy < 0.5:
            return "initial"  # 准确率太低，从基础开始
        elif len(confusion_pairs) >= 3:
            return "precision_focus"  # 混淆严重，提高精确率
        elif instruction_clarity < 0.6:
            return "initial"  # 指令不清晰
        else:
            return "advanced"  # 高级优化
