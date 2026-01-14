"""策略匹配器 - 基于诊断结果匹配优化策略"""
from typing import List, Dict, Any, Type
import json
import asyncio
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
    

    async def score_strategies(
        self,
        diagnosis: Dict[str, Any],
        candidates: List[Any],
        should_stop: Any = None
    ) -> List[tuple[float, BaseStrategy]]:
        """
        使用 LLM 对候选策略进行评分
        
        :param diagnosis: 诊断报告
        :param candidates: 候选策略列表 (priority, strategy)
        :param should_stop: 停止回调函数
        :return: 评分后的策略列表 [(score, strategy), ...]
        """
        if should_stop and should_stop():
            return candidates

        if not self.llm_client or not candidates:
            return candidates

        # 1. 准备 Prompt
        strategy_descriptions = []
        for _, strategy in candidates:
            desc = strategy.__class__.__doc__ or strategy.__class__.__name__
            strategy_descriptions.append(f"- {strategy.strategy_name} ({strategy.__class__.__name__}): {desc.strip()}")
        
        strategies_text = "\n".join(strategy_descriptions)
        
        # 简化诊断报告，只提供关键信息
        diagnosis_summary = {
            "overall_metrics": diagnosis.get("overall_metrics", {}),
            "error_patterns": diagnosis.get("error_patterns", {}),
            "root_cause_analysis": diagnosis.get("root_cause_analysis", {}),
            "prompt_analysis": diagnosis.get("prompt_analysis", {})
        }
        
        prompt = f"""
        你是一个提示词优化策略专家。请根据以下诊断报告和可用策略列表，为每个策略的适用性打分（0-10分）。
        
        【诊断报告摘要】
        {json.dumps(diagnosis_summary, ensure_ascii=False, indent=2)}
        
        【可用策略列表】
        {strategies_text}
        
        【评分标准】
        - 10分：该策略直接解决核心问题，是最佳选择。
        - 7-9分：该策略由于主要问题高度相关，建议采纳。
        - 4-6分：该策略可能有效，但不是最优先的。
        - 0-3分：该策略与当前问题关联度低。
        
        请以 JSON 格式返回评分结果，格式如下：
        {{
            "scores": [
                {{
                    "strategy_name": "策略名称(英文ID)",
                    "score": 8.5,
                    "reason": "评分理由"
                }}
            ]
        }}
        """

        try:
            # 再次检查停止信号
            if should_stop and should_stop():
                return candidates

            # 2. 调用 LLM
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in prompt engineering."},
                {"role": "user", "content": prompt}
            ]
            
            # 使用 openai 库调用，需处理并发
            if hasattr(self.llm_client, "chat"): # 兼容 AsyncOpenAI
                 response = await self.llm_client.chat.completions.create(
                    model=self.model_config.get("model", "gpt-3.5-turbo"),
                    messages=messages,
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                 content = response.choices[0].message.content
            else:
                 # 可能是同步 client 或其他封装
                 # 这里假设是标准 pattern，如果不是需调整
                 return candidates

            # 3. 解析结果
            result = json.loads(content)
            scores_map = {item["strategy_name"]: item["score"] for item in result.get("scores", [])}
            
            # 4. 重新排序
            scored_candidates = []
            for _, strategy in candidates:
                # 尝试用 strategy_name 或 class name 匹配
                score = scores_map.get(strategy.strategy_name, 0)
                # 如果没匹配到，尝试用 type name (需要策略类有 type 属性或类似)
                # 这里暂时只用 strategy_name，需确保 LLM 返回的一致
                
                # 记录原来的优先级作为辅助参考
                # new_score = score (LLM) vs priority (Hardcoded)
                # 优先使用 LLM 分数
                scored_candidates.append((float(score), strategy))
                
            return scored_candidates
            
        except Exception as e:
            print(f"Warning: Strategy scoring failed: {e}")
            return candidates # 降级回原优先级

    async def match_strategies(
        self, 
        diagnosis: Dict[str, Any],
        max_strategies: int = 1,
        selected_modules: List[int] = None,
        should_stop: Any = None
    ) -> List[BaseStrategy]:
        """
        基于诊断结果匹配合适的优化策略 (支持 LLM 动态评分)
        
        Args:
            diagnosis: 诊断分析结果
            max_strategies: 最多返回的策略数量
            selected_modules: 用户选择的模块ID列表。
            should_stop: 停止回调函数
            
        Returns:
            策略实例列表（按推荐优先级排序）
        """
        candidates = []
        
        # ... (原有过滤逻辑保持不变)
        all_module_strategy_types: set = set(MODULE_STRATEGY_MAP.values())
        allowed_module_types: set = set()
        if selected_modules and len(selected_modules) > 0:
            for module_id in selected_modules:
                strategy_type = MODULE_STRATEGY_MAP.get(module_id)
                if strategy_type:
                    allowed_module_types.add(strategy_type)
        
        for name, strategy_class in STRATEGY_CLASSES.items():
            if name in all_module_strategy_types:
                if selected_modules and len(selected_modules) > 0:
                    if name not in allowed_module_types:
                        continue
            
            strategy = strategy_class(
                llm_client=self.llm_client,
                model_config=self.model_config,
                semaphore=self.semaphore
            )
            
            if strategy.is_applicable(diagnosis):
                priority = strategy.get_priority(diagnosis)
                candidates.append((priority, strategy))
        
        # --- 动态评分逻辑 ---
        # 如果有 LLM 客户端，且候选策略超过1个（否则不需要排序），则使用 LLM 评分
        # 注意: match_strategies 现在是 async
        if self.llm_client and len(candidates) > 1:
            try:
                # 调用 LLM 评分 (替换原有的优先级)
                candidates = await self.score_strategies(diagnosis, candidates, should_stop=should_stop)
            except Exception as e:
                print(f"Error in dynamic scoring: {e}")
                # 出错时保持原有优先级
        
        # 按分数/优先级降序排序
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

