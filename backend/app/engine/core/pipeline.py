"""
多策略优化器 - 主逻辑

精简版协调器，通过 phases 模块执行各阶段逻辑
"""
from loguru import logger
import asyncio
from typing import List, Dict, Any, Optional, Callable
from openai import AsyncOpenAI

from ..diagnosis.service import diagnose_prompt_performance
from .matcher import StrategyMatcher, STRATEGY_PRESETS, STRATEGY_CLASSES
from ..helpers.rewriter import PromptRewriter
from ..helpers.fewshot import FewShotSelector
from ..helpers.knowledge import OptimizationKnowledgeBase
from ..diagnosis.intent import IntentAnalyzer
from ..helpers.llm import LLMHelper
from ..diagnosis.advanced import AdvancedDiagnoser
from ..helpers.validator import PromptValidator
from ..helpers.multi_intent import MultiIntentOptimizer
from .candidate_generator import CandidateGenerator
from ..helpers.evaluator import PromptEvaluator

from .models import OptimizationContext
from .phases import (
    init_knowledge_base,
    parallel_analysis,
    advanced_diagnosis,
    deep_intent_analysis,
    filter_and_prepare,
    load_error_history,
    match_strategies,
    generate_candidates,
    select_best,
    inject_persistent_knowledge,
    record_knowledge,
    validate_result,
    update_history,
    build_final_result,
    generate_optimization_summary
)


class MultiStrategyOptimizer:
    """
    多策略优化器 - 协调多种策略进行提示词优化
    
    增强功能：
    - 集成意图分析器，对失败意图进行深度分析
    - 集成知识库，记录每次优化的版本信息
    - 集成高级诊断器，提供定向分析能力
    """
    
    def __init__(
        self, 
        llm_client: Optional[AsyncOpenAI] = None, 
        model_config: Optional[Dict[str, Any]] = None,
        verification_llm_client: Optional[AsyncOpenAI] = None,
        verification_model_config: Optional[Dict[str, Any]] = None
    ):
        """
        初始化多策略优化器
        
        :param llm_client: LLM 客户端实例
        :param model_config: 模型配置
        :param verification_llm_client: 验证专用 LLM 客户端
        :param verification_model_config: 验证专用模型配置
        """
        self.llm_client = llm_client
        self.model_config: Dict[str, Any] = model_config or {}
        self.verification_llm_client = verification_llm_client
        self.verification_model_config = verification_model_config
        
        # 并发控制
        max_concurrency = int(self.model_config.get("concurrency", 5))
        self.semaphore = asyncio.Semaphore(max_concurrency)
        logger.info(f"[并发优化] 初始化信号量，最大并发数: {max_concurrency}")
        
        # 初始化组件
        self.matcher: StrategyMatcher = StrategyMatcher(
            llm_client, model_config, semaphore=self.semaphore
        )
        self.rewriter: PromptRewriter = PromptRewriter()
        self.selector: FewShotSelector = FewShotSelector()
        self.intent_analyzer: IntentAnalyzer = IntentAnalyzer(
            llm_client, model_config, semaphore=self.semaphore
        )
        self.advanced_diagnoser: AdvancedDiagnoser = AdvancedDiagnoser(
            llm_client, model_config
        )
        
        # LLM 辅助类
        self.llm_helper: LLMHelper = LLMHelper(
            llm_client=llm_client,
            model_config=model_config,
            semaphore=self.semaphore
        )
        
        # 验证模块
        verification_helper: LLMHelper = LLMHelper(
            llm_client=verification_llm_client or llm_client,
            model_config=verification_model_config or model_config,
            semaphore=self.semaphore
        )
        self.validator: PromptValidator = PromptValidator(verification_helper)
        
        # 多意图优化器
        self.multi_intent_optimizer: MultiIntentOptimizer = MultiIntentOptimizer(
            llm_helper=self.llm_helper
        )
        
        # 候选生成器与评估器
        self.candidate_generator: CandidateGenerator = CandidateGenerator(
            selector=self.selector, semaphore=self.semaphore
        )
        self.prompt_evaluator: PromptEvaluator = PromptEvaluator(
            llm_helper=self.llm_helper,
            verification_llm_client=verification_llm_client,
            verification_model_config=verification_model_config
        )
        
        # 知识库（延迟初始化）
        self.knowledge_base: Optional[OptimizationKnowledgeBase] = None
        self._should_stop: Optional[Callable[[], bool]] = None
    
    def _is_stopped(self, should_stop: Any, step_name: str = None) -> bool:
        """检查是否应该停止优化"""
        if should_stop and should_stop():
            if step_name:
                logger.info(f"优化在 {step_name} 被中止")
            return True
        return False

    async def optimize(
        self,
        prompt: str,
        errors: List[Dict[str, Any]],
        dataset: List[Dict[str, Any]] = None,
        total_count: int = None,
        strategy_mode: str = "auto",
        max_strategies: int = 1,
        project_id: Optional[str] = None,
        should_stop: Any = None,
        newly_failed_cases: Optional[List[Dict[str, Any]]] = None,
        selected_modules: Optional[List[int]] = None,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """执行多策略优化 - 流水线模式"""
        # 创建上下文
        ctx = OptimizationContext(
            prompt=prompt, 
            errors=errors, 
            dataset=dataset or errors,
            total_count=total_count,
            strategy_mode=strategy_mode,
            max_strategies=max_strategies,
            project_id=project_id,
            should_stop=should_stop,
            newly_failed_cases=newly_failed_cases,
            selected_modules=selected_modules,
            on_progress=on_progress
        )
        
        # 尝试从项目配置中获取自定义提取代码
        if project_id:
            try:
                # 延迟导入以避免循环依赖
                from app.db.storage import get_project
                project = get_project(project_id)
                if project and project.get("config"):
                    import json
                    config = project.get("config")
                    if isinstance(config, str):
                        try:
                            config = json.loads(config)
                        except:
                            config = {}
                            
                    # 查找提取规则: extract_field (兼容 val_config)
                    extract_code = config.get("extract_field")
                    if not extract_code:
                        val_config = config.get("validation_config", {})
                        extract_code = val_config.get("extract_field")
                        
                    # 仅当规则以 py: 开头时才视为代码
                    if extract_code and str(extract_code).startswith("py:"):
                        ctx.custom_extraction_code = str(extract_code)[3:].strip()
                        logger.info(f"已加载自定义意图提取逻辑 (长度: {len(ctx.custom_extraction_code)})")
            except Exception as e:
                logger.warning(f"加载项目自定义提取逻辑失败: {e}")
        
        if not errors:
            return {"optimized_prompt": prompt, "message": "无错误样例，无需优化"}
        
        self._should_stop = should_stop
        if self._is_stopped(should_stop):
            return {"optimized_prompt": prompt, "message": "Stopped"}
        
        # ===== 阶段 0-3: 诊断与分析 =====
        kb_ref = []
        await init_knowledge_base(ctx, kb_ref)
        if kb_ref:
            self.knowledge_base = kb_ref[0]
        
        await parallel_analysis(
            ctx, self.llm_client, self.model_config, self.intent_analyzer
        )
        
        if self._is_stopped(should_stop):
            return {"optimized_prompt": prompt, "message": "Stopped"}
        
        await advanced_diagnosis(ctx, self.advanced_diagnoser)
        await deep_intent_analysis(ctx, self.intent_analyzer)
        filter_and_prepare(ctx)
        
        if self._is_stopped(should_stop):
            return {"optimized_prompt": prompt, "message": "Stopped"}
        
        # ===== 多意图模式检测 =====
        is_multi_intent = strategy_mode == "multi_intent"
        if strategy_mode == "auto":
            mi_issue = ctx.advanced_diagnosis.get("multi_intent_analysis", {}).get("has_issue", False)
            accuracy = ctx.diagnosis_raw.get('overall_metrics', {}).get('accuracy', 0)
            if mi_issue and accuracy < 0.6:
                is_multi_intent = True
                logger.info("自动检测到多意图混淆严重，切换至多意图优化模式")
        
        if is_multi_intent:
            self.multi_intent_optimizer.set_optimizer_callback(self.optimize)
            return await self.multi_intent_optimizer.optimize_multi_intent_flow(
                prompt, errors, dataset, ctx.get_diagnosis_dict()
            )
        
        # ===== 阶段 3.6-4: 加载历史与策略匹配 =====
        if self.knowledge_base:
            ctx.diagnosis_raw["optimization_history_text"] = self.knowledge_base.get_all_history_for_prompt()
            ctx.diagnosis_raw["optimization_history"] = self.knowledge_base.get_latest_analysis()
        
        if newly_failed_cases:
            ctx.diagnosis_raw["newly_failed_cases"] = newly_failed_cases
        
        await load_error_history(ctx)
        await match_strategies(
            ctx, self.matcher, self.llm_client, self.model_config, self.semaphore
        )
        
        if self._is_stopped(should_stop):
            return {"optimized_prompt": prompt, "message": "Stopped"}
        
        if not ctx.strategies:
            return {
                "optimized_prompt": prompt, 
                "diagnosis": ctx.get_diagnosis_dict(), 
                "message": "无匹配策略"
            }
        
        # ===== 阶段 5-6: 候选生成与选择 =====
        await generate_candidates(ctx, self.candidate_generator, self.prompt_evaluator)
        await select_best(ctx, self.prompt_evaluator)
        await inject_persistent_knowledge(
            ctx, self.llm_client, self.model_config, self.semaphore
        )
        
        # ===== 阶段 7-9: 记录与验证 =====
        await record_knowledge(ctx, self.knowledge_base, generate_optimization_summary)
        await validate_result(ctx, self.llm_helper)
        await update_history(ctx)
        
        return build_final_result(ctx)

    def diagnose(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]],
        total_count: int = None,
        project_id: str = None
    ) -> Dict[str, Any]:
        """仅执行诊断分析"""
        return diagnose_prompt_performance(
            prompt, errors, total_count,
            llm_client=self.llm_client,
            model_config=self.model_config,
            project_id=project_id
        )
