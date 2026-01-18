"""策略匹配器 - 基于诊断结果匹配优化策略"""
from typing import List, Dict, Any, Type, Optional
import json
import asyncio
from openai import AsyncOpenAI
from loguru import logger
from ..strategies.base import BaseStrategy
from ..strategies.boundary import BoundaryClarificationStrategy
from ..strategies.instruction import InstructionRefinementStrategy
from ..strategies.difficult_example_injection import DifficultExampleInjectionStrategy
from ..strategies.meta_optimize import MetaOptimizationStrategy
from ..strategies.context_optimize import ContextEnhancementStrategy
from ..strategies.multi_intent_optimize import MultiIntentStrategy
from ..strategies.domain_optimize import DomainDistinctionStrategy
from ..strategies.clarification_optimize import ClarificationMechanismStrategy
from ..strategies.cot_optimize import CoTReasoningStrategy
# 新增策略导入
from ..strategies.custom_data_optimize import CustomDataOptimizationStrategy
from ..strategies.global_constraint_optimize import GlobalConstraintOptimizationStrategy
from ..strategies.intent_definition_optimize import IntentDefinitionOptimizationStrategy
from ..strategies.query_rewrite_optimize import QueryRewriteOptimizationStrategy
from ..strategies.role_task_definition_optimize import RoleTaskDefinitionStrategy
from ..strategies.output_format_optimize import OutputFormatOptimizationStrategy
from ..strategies.negative_fusion_optimize import NegativeFusionOptimizationStrategy
from ..strategies.agent_routing_boundary_optimize import AgentRoutingBoundaryStrategy


# 策略组合预设
STRATEGY_PRESETS = {
    "initial": [  # 初始优化
        {"type": "instruction_refinement", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ],
    "simple": [  # 快速优化（对应前端"快速"按钮）
        {"type": "instruction_refinement", "priority": 1},
        {"type": "meta_optimization", "priority": 2}
    ],
    "multi": [  # 多策略深度优化（对应前端"深度"按钮）
        {"type": "agent_routing_boundary", "priority": 1},
        {"type": "boundary_clarification", "priority": 2},
        {"type": "difficult_example_injection", "priority": 3},
        {"type": "meta_optimization", "priority": 4}
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
    "output_format_optimization": OutputFormatOptimizationStrategy,
    # 负向优化融合策略
    "negative_fusion_optimization": NegativeFusionOptimizationStrategy,
    # Agent 路由边界优化策略
    "agent_routing_boundary": AgentRoutingBoundaryStrategy,
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
        llm_client: Optional[AsyncOpenAI] = None, 
        model_config: Optional[Dict[str, Any]] = None,
        semaphore: Optional[asyncio.Semaphore] = None
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
        logger.info(f"[StrategyMatcher] 开始策略评分，候选策略数量: {len(candidates)}")
        
        if should_stop and should_stop():
            logger.debug("[StrategyMatcher] 收到停止信号，跳过策略评分")
            return candidates

        if not self.llm_client or not candidates:
            logger.warning(f"[StrategyMatcher] 跳过策略评分: llm_client={bool(self.llm_client)}, candidates={len(candidates)}")
            return candidates

        # 1. 准备 Prompt
        strategy_descriptions = []
        for _, strategy in candidates:
            desc = strategy.__class__.__doc__ or strategy.__class__.__name__
            strategy_descriptions.append(f"- {strategy.strategy_name} ({strategy.__class__.__name__}): {desc.strip()}")
        
        strategies_text = "\n".join(strategy_descriptions)
        
        # 构建诊断报告摘要（完善版 - 包含更多关键信息）
        # 1. 基础指标
        overall_metrics: Dict[str, Any] = diagnosis.get("overall_metrics", {})
        error_patterns: Dict[str, Any] = diagnosis.get("error_patterns", {})
        
        # 2. 意图分析摘要
        intent_analysis: Dict[str, Any] = diagnosis.get("intent_analysis", {})
        # 提取 Top 失败意图信息
        top_failing_intents: List[Dict[str, Any]] = intent_analysis.get("top_failing_intents", [])
        intent_analysis_summary: Dict[str, Any] = {
            "top_failing_intents": [
                {"intent": i.get("intent", ""), "error_rate": i.get("error_rate", 0)} 
                for i in top_failing_intents[:5]
            ],
            "total_intent_count": intent_analysis.get("total_intents", 0),
            # 判断错误是否集中在少数意图
            "concentrated_failure": (
                len(top_failing_intents) > 0 and 
                top_failing_intents[0].get("error_rate", 0) > 0.3
            )
        }
        
        # 3. 深度分析摘要
        deep_analysis: Dict[str, Any] = diagnosis.get("deep_analysis", {})
        analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])
        deep_analysis_summary: str = ""
        if analyses:
            # 提取每个意图的分析摘要（限制长度）
            summaries: List[str] = [
                f"{a.get('intent', '未知')}: {a.get('analysis', '')[:100]}" 
                for a in analyses[:3]
            ]
            deep_analysis_summary = "; ".join(summaries)
        
        # 4. 高级诊断摘要
        advanced_diag: Dict[str, Any] = diagnosis.get("advanced_diagnosis", {})
        advanced_diagnosis_summary: Dict[str, Any] = {
            "has_context_issue": advanced_diag.get("context_analysis", {}).get("has_issue", False),
            "has_multi_intent_issue": advanced_diag.get("multi_intent_analysis", {}).get("has_issue", False),
            "has_domain_confusion": advanced_diag.get("domain_analysis", {}).get("domain_confusion", False),
            "has_clarification_issue": advanced_diag.get("clarification_analysis", {}).get("has_issue", False),
            # 澄清类样本数量（用于判断是否需要降低某些优化的优先级）
            "clarification_target_count": advanced_diag.get("clarification_analysis", {}).get("clarification_target_count", 0)
        }
        
        # 5. 新增失败案例标记
        has_newly_failed: bool = bool(diagnosis.get("newly_failed_cases"))
        
        # 6. 顽固错误标记
        has_persistent_errors: bool = bool(diagnosis.get("persistent_error_samples"))
        
        # 组装完整诊断摘要
        diagnosis_summary: Dict[str, Any] = {
            "overall_metrics": overall_metrics,
            "error_patterns": {
                # 只保留关键信息
                "confusion_pairs": error_patterns.get("confusion_pairs", [])[:5],
                "hard_cases_count": len(error_patterns.get("hard_cases", []))
            },
            "root_cause_analysis": diagnosis.get("root_cause_analysis", {}),
            "prompt_analysis": diagnosis.get("prompt_analysis", {}),
            # 新增字段
            "intent_analysis_summary": intent_analysis_summary,
            "deep_analysis_summary": deep_analysis_summary,
            "advanced_diagnosis": advanced_diagnosis_summary,
            "has_newly_failed_cases": has_newly_failed,
            "has_persistent_errors": has_persistent_errors
        }
        
        prompt = f"""
        你是一个提示词优化策略专家。请根据以下诊断报告和可用策略列表，为每个策略的适用性打分（0-10分）。
        
        【诊断报告摘要】
        {json.dumps(diagnosis_summary, ensure_ascii=False, indent=2)}
        
        【可用策略列表】
        {strategies_text}
        
        【评分标准】
        - 10分：该策略直接解决核心问题，是最佳选择。
        - 7-9分：该策略与主要问题高度相关，建议采纳。
        - 4-6分：该策略可能有效，但不是最优先的。
        - 0-3分：该策略与当前问题关联度低。
        
        【特别注意】
        - 如果 has_persistent_errors 为 true，说明存在顽固错误，difficult_example_injection 策略应获得较高分数。
        - 如果 has_context_issue 为 true，context_enhancement 策略应优先考虑。
        - 如果 has_clarification_issue 为 true 且 clarification_target_count 较高，澄清类问题暂时优先级较低。
        
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
                logger.debug("[StrategyMatcher] 收到停止信号，跳过策略评分")
                return candidates

            # 2. 调用 LLM
            messages = [
                {"role": "system", "content": "You are a helpful assistant specialized in prompt engineering."},
                {"role": "user", "content": prompt}
            ]
            
            # 获取模型名称 - 注意：正确的字段名是 model_name 而不是 model
            model_name: str = self.model_config.get("model_name", "gpt-3.5-turbo")
            logger.info(f"[StrategyMatcher] 准备调用 LLM 进行策略评分，模型: {model_name}")
            logger.debug(f"[StrategyMatcher] model_config 完整内容: {json.dumps(self.model_config, ensure_ascii=False, default=str)}")
            
            # 使用 openai 库调用，需处理并发
            if hasattr(self.llm_client, "chat"):
                # 兼容 AsyncOpenAI
                logger.debug(f"[StrategyMatcher] 使用 AsyncOpenAI 客户端调用，消息长度: {len(prompt)} 字符")
                response = await self.llm_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                logger.debug(f"[StrategyMatcher] LLM 返回内容长度: {len(content) if content else 0} 字符")
            else:
                # 可能是同步 client 或其他封装
                # 这里假设是标准 pattern，如果不是需调整
                logger.warning("[StrategyMatcher] LLM 客户端不支持 chat 属性，跳过策略评分")
                return candidates

            # 3. 解析结果
            result = json.loads(content)
            scores_list = result.get("scores", [])
            # Map strategy_name -> (score, reason)
            scores_map = {item["strategy_name"]: (item["score"], item.get("reason", "")) for item in scores_list}
            
            logger.info(f"[StrategyMatcher] LLM 评分结果解析成功，共 {len(scores_list)} 个策略评分")
            for item in scores_list:
                logger.debug(f"[StrategyMatcher] 策略评分 - {item.get('strategy_name')}: {item.get('score')} 分, 理由: {item.get('reason', '无')[:50]}...")
            
            # 4. 重新排序
            scored_candidates = []
            for _, strategy in candidates:
                # 尝试用 strategy_name 或 class name 匹配
                score_info = scores_map.get(strategy.strategy_name, (0, ""))
                score = score_info[0]
                reason = score_info[1]
                
                # 记录原来的优先级作为辅助参考
                # new_score = score (LLM) vs priority (Hardcoded)
                # 优先使用 LLM 分数
                
                # 将元数据附加到策略对象上(临时)
                strategy.selection_score = float(score)
                strategy.selection_reason = reason
                
                scored_candidates.append((float(score), strategy))
                logger.debug(f"[StrategyMatcher] 策略 {strategy.strategy_name} 最终评分: {score}")
                
            logger.info(f"[StrategyMatcher] 策略评分完成，共 {len(scored_candidates)} 个候选策略")
            return scored_candidates
            
        except json.JSONDecodeError as e:
            logger.error(f"[StrategyMatcher] 解析 LLM 返回的 JSON 失败: {e}, 返回内容: {content[:200] if content else '空'}...")
            return candidates
        except Exception as e:
            logger.error(f"[StrategyMatcher] 策略评分过程发生异常: {type(e).__name__}: {e}")
            return candidates  # 降级回原优先级

    async def match_strategies(
        self, 
        diagnosis: Dict[str, Any],
        max_strategies: int = 1,
        selected_modules: List[int] = None,
        should_stop: Any = None
    ) -> List[BaseStrategy]:
        """
        基于诊断结果匹配合适的优化策略 (支持 LLM 动态评分)
        
        逻辑简化说明：
        - 当 selected_modules 有值时，只处理 selected_modules 对应的模块策略
        - 当 selected_modules 为 None 时，跳过所有模块策略，仅处理非模块策略
        
        :param diagnosis: 诊断分析结果
        :param max_strategies: 最多返回的策略数量
        :param selected_modules: 用户选择的模块ID列表
        :param should_stop: 停止回调函数
        :return: 策略实例列表（按推荐优先级排序）
        """
        logger.info(f"[StrategyMatcher] ========== 开始匹配策略 ==========")
        logger.info(f"[StrategyMatcher] 参数: max_strategies={max_strategies}, selected_modules={selected_modules}")
        logger.info(f"[StrategyMatcher] 所有已注册策略: {list(STRATEGY_CLASSES.keys())}")

        candidates: List[tuple[float, BaseStrategy]] = []

        # 获取所有模块策略类型的集合（用于快速判断）
        all_module_strategy_types: set = set(MODULE_STRATEGY_MAP.values())
        logger.info(f"[StrategyMatcher] 模块策略类型: {all_module_strategy_types}")
        
        # 当 selected_modules 有值时，只处理选中的模块策略
        if selected_modules and len(selected_modules) > 0:
            logger.info(f"[StrategyMatcher] 模块策略模式：处理选中的 {len(selected_modules)} 个模块")
            for module_id in selected_modules:
                strategy_type: str = MODULE_STRATEGY_MAP.get(module_id)
                if strategy_type and strategy_type in STRATEGY_CLASSES:
                    strategy_class = STRATEGY_CLASSES[strategy_type]
                    strategy = strategy_class(
                        llm_client=self.llm_client,
                        model_config=self.model_config,
                        semaphore=self.semaphore
                    )
                    priority = strategy.get_priority(diagnosis)
                    candidates.append((priority, strategy))
                    logger.debug(f"[StrategyMatcher] 添加模块策略: module_id={module_id}, type={strategy_type}, priority={priority}")
                else:
                    logger.warning(f"[StrategyMatcher] 未找到模块策略: module_id={module_id}, strategy_type={strategy_type}")
        else:
            # 未指定模块时，遍历所有非模块策略
            logger.info("[StrategyMatcher] 非模块策略模式：遍历所有非模块策略")
            for name, strategy_class in STRATEGY_CLASSES.items():
                # 跳过所有模块策略
                if name in all_module_strategy_types:
                    logger.info(f"[StrategyMatcher] 跳过模块策略: {name}")
                    continue

                strategy = strategy_class(
                    llm_client=self.llm_client,
                    model_config=self.model_config,
                    semaphore=self.semaphore
                )

                is_applicable = strategy.is_applicable(diagnosis)
                logger.info(f"[StrategyMatcher] 检查策略 [{name}] 是否适用: {is_applicable}")

                if is_applicable:
                    priority: float = strategy.get_priority(diagnosis)
                    candidates.append((priority, strategy))
                    logger.info(f"[StrategyMatcher] ✅ 添加策略: {name}, 优先级={priority}")
                else:
                    logger.info(f"[StrategyMatcher] ❌ 策略不适用: {name}")
        
        logger.info(f"[StrategyMatcher] 候选策略收集完成，共 {len(candidates)} 个")
        
        # --- 动态评分逻辑 ---
        # 如果有 LLM 客户端，且候选策略超过1个，则使用 LLM 评分
        if self.llm_client and len(candidates) > 1:
            logger.info(f"[StrategyMatcher] 启用 LLM 动态评分，候选策略数量: {len(candidates)}")
            try:
                candidates = await self.score_strategies(diagnosis, candidates, should_stop=should_stop)
            except Exception as e:
                logger.error(f"[StrategyMatcher] LLM 动态评分失败: {type(e).__name__}: {e}")
                # 出错时保持原有优先级
        else:
            logger.debug(f"[StrategyMatcher] 跳过 LLM 动态评分: llm_client={bool(self.llm_client)}, candidates={len(candidates)}")
        
        # 按分数/优先级降序排序
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # 返回前 N 个策略
        result_strategies = [strategy for _, strategy in candidates[:max_strategies]]
        logger.info(f"[StrategyMatcher] 策略匹配完成，返回 {len(result_strategies)} 个策略: {[s.strategy_name for s in result_strategies]}")
        
        return result_strategies

    
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

