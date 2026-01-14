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
# 新增策略导入
from .strategies.custom_data_optimize import CustomDataOptimizationStrategy
from .strategies.global_constraint_optimize import GlobalConstraintOptimizationStrategy
from .strategies.intent_definition_optimize import IntentDefinitionOptimizationStrategy
from .strategies.query_rewrite_optimize import QueryRewriteOptimizationStrategy
from .strategies.role_task_definition_optimize import RoleTaskDefinitionStrategy
from .strategies.output_format_optimize import OutputFormatOptimizationStrategy


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
    "auto_directed": [  # 自动定向优化 (新模式)
        {"type": "context_enhancement", "priority": 1},
        {"type": "multi_intent_optimization", "priority": 1},
        {"type": "domain_distinction", "priority": 1},
        {"type": "clarification_mechanism", "priority": 1},
        {"type": "cot_reasoning", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ],
    "full_strategy": [  # 全策略模式 (包含所有策略)
        {"type": "intent_definition_optimization", "priority": 1},
        {"type": "global_constraint_optimization", "priority": 1},
        {"type": "boundary_clarification", "priority": 1},
        {"type": "query_rewrite_optimization", "priority": 2},
        {"type": "cot_reasoning", "priority": 2},
        {"type": "difficult_example_injection", "priority": 3},
        {"type": "custom_data_optimization", "priority": 3},
        {"type": "meta_optimization", "priority": 4}
    ]
}

# 策略类型映射
STRATEGY_CLASSES: Dict[str, Type[BaseStrategy]] = {
    # 原有策略
    "boundary_clarification": BoundaryClarificationStrategy,
    "instruction_refinement": InstructionRefinementStrategy,
    "difficult_example_injection": DifficultExampleInjectionStrategy,
    "meta_optimization": MetaOptimizationStrategy,
    "context_enhancement": ContextEnhancementStrategy,
    "multi_intent_optimization": MultiIntentStrategy,
    "domain_distinction": DomainDistinctionStrategy,
    "clarification_mechanism": ClarificationMechanismStrategy,
    "cot_reasoning": CoTReasoningStrategy,
    # 新增策略
    "custom_data_optimization": CustomDataOptimizationStrategy,
    "global_constraint_optimization": GlobalConstraintOptimizationStrategy,
    "intent_definition_optimization": IntentDefinitionOptimizationStrategy,
    "query_rewrite_optimization": QueryRewriteOptimizationStrategy,
    "role_task_definition": RoleTaskDefinitionStrategy,
    "output_format_optimization": OutputFormatOptimizationStrategy
}

# 模块ID到策略类型的映射
# 这个映射对应前端 ModelConfig.tsx 中 STANDARD_MODULES 的定义
MODULE_STRATEGY_MAP: Dict[int, str] = {
    1: "role_task_definition",           # 角色与任务定义
    2: "global_constraint_optimization", # 全局约束规则
    3: "query_rewrite_optimization",     # Query 预处理
    4: "intent_definition_optimization", # 意图体系定义
    5: "context_enhancement",            # 上下文与指代
    6: "custom_data_optimization",       # 业务专属数据
    7: "cot_reasoning",                  # CoT 思维链
    8: "difficult_example_injection",    # Few-Shot 示例
    9: "output_format_optimization"      # 标准化输出
}



class StrategyMatcher:
    """策略匹配器 - 基于诊断结果选择最适合的优化策略"""
    
    def __init__(
        self, 
        llm_client=None, 
        model_config: Dict[str, Any] = None,
        semaphore: Any = None
    ):
        """
        初始化策略匹配器
        
        :param llm_client: LLM 客户端实例
        :param model_config: 模型配置
        :param semaphore: 并发控制信号量（传递给策略使用）
        """
        self.llm_client = llm_client
        self.model_config = model_config or {}
        self.semaphore = semaphore
    
    def match_strategies(
        self, 
        diagnosis: Dict[str, Any],
        max_strategies: int = 1,
        selected_modules: List[int] = None
    ) -> List[BaseStrategy]:
        """
        基于诊断结果匹配合适的优化策略
        
        Args:
            diagnosis: 诊断分析结果
            max_strategies: 最多返回的策略数量
            selected_modules: 用户选择的模块ID列表。
                              如果指定，则9个模块策略中只有选中的才会参与评估，
                              其他非模块策略（如 meta_optimization）照常参与。
            
        Returns:
            策略实例列表（按优先级排序）
        """
        candidates = []
        
        # 获取所有模块策略的类型名称集合
        all_module_strategy_types: set = set(MODULE_STRATEGY_MAP.values())
        
        # 如果用户指定了 selected_modules，则计算允许参与评估的模块策略类型
        allowed_module_types: set = set()
        if selected_modules and len(selected_modules) > 0:
            for module_id in selected_modules:
                strategy_type = MODULE_STRATEGY_MAP.get(module_id)
                if strategy_type:
                    allowed_module_types.add(strategy_type)
        
        # 获取所有策略类并评估适用性
        for name, strategy_class in STRATEGY_CLASSES.items():
            # 过滤逻辑：
            # 如果当前策略是模块策略（属于9个模块之一）
            if name in all_module_strategy_types:
                # 如果用户指定了 selected_modules, 则只允许选中的模块策略参与
                if selected_modules and len(selected_modules) > 0:
                    if name not in allowed_module_types:
                        # 未选中的模块策略，跳过
                        continue
            # 非模块策略（如 meta_optimization）照常参与
            
            strategy = strategy_class(
                llm_client=self.llm_client,
                model_config=self.model_config,
                semaphore=self.semaphore
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
                    model_config=self.model_config,
                    semaphore=self.semaphore
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
    
    def get_module_strategies(
        self, 
        selected_modules: List[int]
    ) -> List[BaseStrategy]:
        """
        根据用户选择的模块ID列表返回对应的策略实例
        
        用于「标准意图识别模块优化」模式，只执行用户勾选的模块对应的策略
        
        :param selected_modules: 用户选择的模块ID列表（对应前端 STANDARD_MODULES 的 id）
        :return: 策略实例列表（按模块ID顺序排列）
        """
        strategies: List[BaseStrategy] = []
        
        for module_id in selected_modules:
            strategy_type: str = MODULE_STRATEGY_MAP.get(module_id)
            if strategy_type and strategy_type in STRATEGY_CLASSES:
                strategy = STRATEGY_CLASSES[strategy_type](
                    llm_client=self.llm_client,
                    model_config=self.model_config,
                    semaphore=self.semaphore
                )
                strategies.append(strategy)
        
        return strategies

