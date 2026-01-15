"""多策略优化器 - 主逻辑"""
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from .diagnosis import diagnose_prompt_performance
from .strategy_matcher import StrategyMatcher
from .prompt_rewriter import PromptRewriter
from .fewshot_selector import FewShotSelector
from .knowledge_base import OptimizationKnowledgeBase
from .intent_analyzer import IntentAnalyzer
from .advanced_diagnosis import AdvancedDiagnoser
# 新增模块导入
from .llm_helper import LLMHelper
from .validation import PromptValidator
from .multi_intent_optimizer import MultiIntentOptimizer
from .candidate_generator import CandidateGenerator
from .prompt_evaluator import PromptEvaluator
from openai import AsyncOpenAI


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
        llm_client=None, 
        model_config: Dict[str, Any] = None,
        verification_llm_client=None,
        verification_model_config: Dict[str, Any] = None
    ):
        """
        初始化多策略优化器
        
        :param llm_client: LLM 客户端实例 (支持 AsyncOpenAI 或 OpenAI)
        :param model_config: 模型配置
        :param verification_llm_client: 验证专用 LLM 客户端 (可选)
        :param verification_model_config: 验证专用模型配置 (可选)
        """
        self.llm_client = llm_client
        self.model_config: Dict[str, Any] = model_config or {}
        
        # 验证专用配置
        self.verification_llm_client = verification_llm_client
        self.verification_model_config = verification_model_config
        
        # 初始化并发控制信号量
        # 默认并发度为 5，可通过 model_config['concurrency'] 配置
        max_concurrency = int(self.model_config.get("concurrency", 5))
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.logger: logging.Logger = logging.getLogger(__name__)
        
        self.logger.info(f"[并发优化] 初始化信号量，最大并发数: {max_concurrency}")
        
        # 传递信号量给策略匹配器，使策略中的 LLM 调用也遵循并发限制
        self.matcher: StrategyMatcher = StrategyMatcher(
            llm_client, 
            model_config,
            semaphore=self.semaphore
        )
        self.rewriter: PromptRewriter = PromptRewriter()
        self.selector: FewShotSelector = FewShotSelector()
        
        # 初始化意图分析器 (传入信号量以共享并发限制)
        self.intent_analyzer: IntentAnalyzer = IntentAnalyzer(
            llm_client, 
            model_config,
            semaphore=self.semaphore
        )
        
        # 初始化高级诊断器
        # 注意: AdvancedDiagnoser 目前可能还需要适配 semaphore，暂时仅传入 config
        self.advanced_diagnoser: AdvancedDiagnoser = AdvancedDiagnoser(
            llm_client,
            model_config
        )
        
        # 初始化 LLM 辅助类
        self.llm_helper: LLMHelper = LLMHelper(
            llm_client=llm_client,
            model_config=model_config,
            semaphore=self.semaphore
        )
        
        # 初始化验证模块（使用验证专用配置）
        verification_helper: LLMHelper = LLMHelper(
            llm_client=verification_llm_client or llm_client,
            model_config=verification_model_config or model_config,
            semaphore=self.semaphore
        )
        self.validator: PromptValidator = PromptValidator(verification_helper)
        
        # 初始化多意图优化器
        self.multi_intent_optimizer: MultiIntentOptimizer = MultiIntentOptimizer(
            llm_helper=self.llm_helper
        )
        
        # 初始化候选生成器
        self.candidate_generator: CandidateGenerator = CandidateGenerator(
            selector=self.selector,
            semaphore=self.semaphore
        )
        
        # 初始化提示词评估器
        self.prompt_evaluator: PromptEvaluator = PromptEvaluator(
            llm_helper=self.llm_helper,
            verification_llm_client=verification_llm_client,
            verification_model_config=verification_model_config
        )
        
        # 知识库延迟初始化（需要 project_id）
        self.knowledge_base: Optional[OptimizationKnowledgeBase] = None
        
        # 停止回调函数（在 optimize 方法中设置）
        self._should_stop: Optional[Callable[[], bool]] = None
    
    def _is_stopped(self, should_stop: Any, step_name: str = None) -> bool:
        """
        检查是否应该停止优化
        
        :param should_stop: 停止回调函数
        :param step_name: 当前步骤名称（用于日志）
        :return: 是否应停止
        """
        if should_stop and should_stop():
            if step_name:
                self.logger.info(f"优化在 {step_name} 被中止")
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
        """
        执行多策略优化（增强版七阶段工作流）
        
        1. 初始化知识库（如有 project_id）
        2. 诊断分析
        3. 意图详细分析 & 高级定向分析 (NEW)
        4. Top 失败意图深度分析
        5. 策略匹配
        6. 候选生成与评估
        7. 记录到知识库
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param dataset: 完整数据集（用于 few-shot 选择）
        :param total_count: 总样本数（用于计算准确率）
        :param strategy_mode: 策略模式（auto/initial/precision_focus 等）
        :param max_strategies: 最多应用的策略数量
        :param project_id: 项目ID（用于知识库）
        :param newly_failed_cases: 新增的失败案例（上一轮成功，本轮失败）
        :param selected_modules: 用户选择的标准模块ID列表（对应前端 STANDARD_MODULES 的 id）
        :param on_progress: 进度回调函数，接收进度消息字符串
        :return: 优化结果字典
        """
        if not errors:
            return {"optimized_prompt": prompt, "message": "无错误样例，无需优化"}
            
        dataset = dataset or errors
        
        # 保存停止回调到实例变量，以便子方法可以访问
        self._should_stop = should_stop
        
        # 检查停止信号
        if self._is_stopped(should_stop): 
            return {"optimized_prompt": prompt, "message": "Stopped"}

        # 阶段 0：初始化知识库
        if project_id:
            self.knowledge_base = OptimizationKnowledgeBase(project_id)
            self.logger.info(f"步骤 0: 初始化知识库 (项目ID: {project_id})")
        
        # 阶段 1 & 2：并行执行诊断分析和意图分析（性能优化）
        if on_progress:
            on_progress("正在执行诊断与意图分析...")
        self.logger.info(f"步骤 1&2: 并行执行诊断分析和意图分析... (错误样本数: {len(errors)})")
        self.logger.info(f"提示词上下文: {prompt[:100]}... (总长度: {len(prompt)})")
        
        loop = asyncio.get_running_loop()
        
        # 定义诊断分析任务
        async def run_diagnosis() -> Dict[str, Any]:
            """
            执行诊断分析
            
            :return: 诊断结果
            """
            return await loop.run_in_executor(
                None,
                lambda: diagnose_prompt_performance(
                    prompt, 
                    errors, 
                    total_count,
                    llm_client=self.llm_client,
                    model_config=self.model_config,
                    project_id=project_id
                )
            )
        
        # 定义意图分析任务
        async def run_intent_analysis() -> Dict[str, Any]:
            """
            执行意图分析
            
            :return: 意图分析结果
            """
            return await loop.run_in_executor(
                None,
                lambda: self.intent_analyzer.analyze_errors_by_intent(
                    errors, 
                    total_count
                )
            )
        
        # 并行执行诊断分析和意图分析
        self.logger.info("[并发优化] 并行启动诊断分析和意图分析...")
        diagnosis, intent_analysis = await asyncio.gather(
            run_diagnosis(),
            run_intent_analysis()
        )

        # logging.info(f"诊断分析结果: {diagnosis}")
        # 记录诊断结果
        metrics = diagnosis.get('overall_metrics', {})
        error_patterns = diagnosis.get('error_patterns', {})
        self.logger.info(
            f"诊断完成: 准确率={metrics.get('accuracy'):.4f} "
            f"({metrics.get('error_count')}/{metrics.get('total_count')} 错误/总数)"
        )
        self.logger.info(f"主要错误模式: {list(error_patterns.keys())}")
        if error_patterns.get('confusion_pairs'):
            self.logger.info(f"Top 混淆对: {error_patterns['confusion_pairs'][:3]}")
        if error_patterns.get('category_distribution'):
             self.logger.info(f"错误分布 Top 3: {dict(list(error_patterns['category_distribution'].items())[:3])}")
        
        # 检查停止信号
        if self._is_stopped(should_stop, "步骤 1&2 完成后"): 
            return {"optimized_prompt": prompt, "message": "Stopped"}

        # 立即启动高级诊断（与后续步骤并行）
        if on_progress:
            on_progress("正在执行高级定向分析...")
        self.logger.info("步骤 2.5: 启动高级定向分析...")
        all_intents = [
            i["intent"] for i in intent_analysis.get("top_failing_intents", [])
        ]
        advanced_diagnosis: Dict[str, Any] = await self.advanced_diagnoser.run_all_diagnoses(
            errors,
            all_intents,
            should_stop=should_stop
        )
        
        # 记录高级诊断摘要
        for diag_key, res in advanced_diagnosis.items():
            if isinstance(res, dict) and res.get("has_issue"):
                self.logger.info(f"高级诊断报告 - {diag_key}: 发现潜在问题")
                if "referential_error_ratio" in res:
                    self.logger.info(f"  - 指代错误率: {res['referential_error_ratio']:.2%}")
                if "false_negative_rate" in res:
                    self.logger.info(f"  - 多意图漏判率: {res['false_negative_rate']:.2%}")
                if "summary" in res:
                    self.logger.info(f"  - 领域分析总结: {res['summary']}")
                if "missing_rate" in res:
                    self.logger.info(f"  - 缺失澄清率: {res['missing_rate']:.2%}")
        
        # 检查停止信号
        if self._is_stopped(should_stop, "步骤 2 完成后"): 
            return {"optimized_prompt": prompt, "message": "Stopped"}
        
        # 阶段 3：Top 失败意图深度分析
        # 选取错误数最多的 top 3 个意图，每个意图最多 50 个错误案例
        if on_progress:
            on_progress("正在执行深度意图分析...")
        self.logger.info("步骤 3: Top 失败意图深度分析...")
        self.logger.info(f"开始分析 Top 3 失败意图，错误样本数: {len(errors)}")
        deep_analysis: Dict[str, Any] = await self.intent_analyzer.deep_analyze_top_failures(
            errors, 
            top_n=3,
            should_stop=should_stop
        )
        
        # 记录深度分析结果详情
        analyzed_count: int = deep_analysis.get("analyzed_count", 0)
        self.logger.info(f"深度分析完成，共分析 {analyzed_count} 个意图")
        
        if deep_analysis.get("analyses"):
            for intent_res in deep_analysis["analyses"]:
                intent_name: str = intent_res.get('intent', '未知')
                analysis_text: str = intent_res.get('analysis', '')
                error_rate: float = intent_res.get('error_rate', 0)
                
                # 检查分析内容是否为空或异常
                if not analysis_text or analysis_text.strip() == '':
                    self.logger.warning(f"意图 '{intent_name}' 根因分析结果为空！")
                elif analysis_text.startswith('分析失败'):
                    self.logger.warning(f"意图 '{intent_name}' 根因分析失败: {analysis_text[:100]}...")
                else:
                    self.logger.info(
                        f"意图 '{intent_name}' (错误率: {error_rate:.1%}) 根因分析: {analysis_text[:150]}..."
                    )
        else:
            self.logger.warning("深度分析未返回任何分析结果！请检查 LLM 调用是否正常。")
        
        # 将分析结果注入 diagnosis
        diagnosis["intent_analysis"] = intent_analysis
        diagnosis["deep_analysis"] = deep_analysis
        diagnosis["advanced_diagnosis"] = advanced_diagnosis
        
        # 阶段 3.5：澄清意图过滤与顽固错误识别
        # 获取澄清分析结果
        clarification_analysis: Dict[str, Any] = advanced_diagnosis.get(
            "clarification_analysis", {}
        )
        
        # 过滤澄清类样本（降低优先级）
        main_errors, low_priority_errors = self._filter_clarification_samples(
            errors, clarification_analysis
        )
        
        # 如果过滤后主要错误为空，使用原始错误列表
        if not main_errors and errors:
            self.logger.warning("[澄清过滤] 主要优化样本为空，使用原始错误列表")
            main_errors = errors
        
        # 将过滤结果注入 diagnosis
        diagnosis["main_errors"] = main_errors
        diagnosis["low_priority_clarification_errors"] = low_priority_errors
        
        # 识别顽固错误样本（需要从项目获取历史记录）
        # 提取本轮被优化的意图列表
        optimized_intents: List[str] = [
            i.get("intent", "") for i in intent_analysis.get("top_failing_intents", [])[:3]
        ]
        diagnosis["optimized_intents"] = optimized_intents

        # 检查停止信号
        if self._is_stopped(should_stop, "步骤 3 完成后"): 
            return {"optimized_prompt": prompt, "message": "Stopped"}

        # 检查是否触发多意图优化模式
        # 触发条件: 
        # 1. 显式指定 strategy_mode="multi_intent"
        # 2. auto 模式下，高级诊断发现 "multi_intent_analysis" 有问题且准确率低于 0.6
        is_multi_intent = False
        if strategy_mode == "multi_intent":
            is_multi_intent = True
        elif strategy_mode == "auto":
            multi_intent_issue = advanced_diagnosis.get("multi_intent_analysis", {}).get("has_issue", False)
            accuracy = metrics.get('accuracy', 0)
            if multi_intent_issue and accuracy < 0.6:
                is_multi_intent = True
                self.logger.info("自动检测到多意图混淆严重，切换至多意图优化模式")

        # 如果触发多意图优化，执行独立流程
        if is_multi_intent:
            # 设置优化回调函数（防止递归死循环）
            self.multi_intent_optimizer.set_optimizer_callback(self.optimize)
            return await self.multi_intent_optimizer.optimize_multi_intent_flow(
                prompt, errors, dataset, diagnosis
            )

        
        # 获取历史优化经验（如有知识库）- 获取完整历史
        if self.knowledge_base:
            # 获取格式化的完整历史文本（V1 ~ 最新版本）
            diagnosis["optimization_history_text"] = (
                self.knowledge_base.get_all_history_for_prompt()
            )
            # 保留原有字段以兼容 MetaOptimizationStrategy
            diagnosis["optimization_history"] = self.knowledge_base.get_latest_analysis()
            self.logger.info(
                f"从知识库获取历史优化记录: "
                f"{'有' if diagnosis['optimization_history'] else '无'}"
            )
        
        # 将 newly_failed_cases 注入 diagnosis（供策略使用）
        if newly_failed_cases:
            diagnosis["newly_failed_cases"] = newly_failed_cases
            self.logger.info(f"注入新增失败案例到 diagnosis，数量: {len(newly_failed_cases)}")
        
        # 阶段 3.6：获取错误优化历史并识别顽固错误
        error_history: Dict[str, Any] = {}
        persistent_samples: List[Dict[str, Any]] = []
        
        if project_id:
            # 从存储获取错误优化历史
            from app.db.storage import get_error_optimization_history
            error_history = get_error_optimization_history(project_id)
            
            if error_history:
                # 识别顽固错误样本
                persistent_samples = self._identify_persistent_errors(error_history)
                
                if persistent_samples:
                    # 将顽固错误样本注入 diagnosis，供策略匹配使用
                    diagnosis["persistent_error_samples"] = persistent_samples
                    
                    # 同时将顽固错误添加到 error_patterns.hard_cases（触发 difficult 策略）
                    if "error_patterns" not in diagnosis:
                        diagnosis["error_patterns"] = {}
                    existing_hard_cases: List[Dict[str, Any]] = diagnosis["error_patterns"].get("hard_cases", [])
                    
                    # 合并顽固错误到 hard_cases
                    for ps in persistent_samples:
                        existing_hard_cases.append({
                            "query": ps.get("query", ""),
                            "target": ps.get("target", ""),
                            "output": "",
                            "_persistent": True,
                            "_optimization_count": ps.get("optimization_count", 0)
                        })
                    diagnosis["error_patterns"]["hard_cases"] = existing_hard_cases
                    
                    self.logger.info(
                        f"[顽固错误] 已注入 {len(persistent_samples)} 个顽固错误样本到 hard_cases"
                    )
        
        # 阶段 4：策略匹配
        if on_progress:
            on_progress("正在匹配优化策略...")
        self.logger.info("步骤 4: 策略匹配...")
        
        # 检查是否应该强制使用负向优化融合策略
        # 条件：auto 模式 + 有深度分析结果 + 准确率低于 0.8
        use_negative_fusion: bool = False
        # if strategy_mode == 'auto' and deep_analysis.get("analyses"):
        #     accuracy: float = metrics.get('accuracy', 0)
        #     if accuracy < 0.8:
        #         use_negative_fusion = True
        #         self.logger.info(
        #             f"[负向融合策略] 深度分析完成，准确率 {accuracy:.2%} < 80%，"
        #             f"强制启用负向优化融合策略"
        #         )
        
        # 策略匹配：将 selected_modules 传递给 match_strategies
        # match_strategies 会自动过滤：
        # - 9个模块策略中只有选中的才会参与评估
        # - 其他非模块策略照常参与评估
        self.logger.info("正在匹配优化策略...")
        
        if use_negative_fusion:
            # 强制使用负向优化融合策略
            from .strategy_matcher import STRATEGY_CLASSES
            negative_fusion_class = STRATEGY_CLASSES.get("negative_fusion_optimization")
            if negative_fusion_class:
                strategies = [negative_fusion_class(
                    llm_client=self.llm_client,
                    model_config=self.model_config,
                    semaphore=self.semaphore
                )]
                self.logger.info(f"[负向融合策略] 已强制选中: {[s.name for s in strategies]}")
            else:
                self.logger.warning("[负向融合策略] 未找到负向优化融合策略类，回退到自动匹配")
                strategies = await self.matcher.match_strategies(
                    diagnosis=diagnosis,
                    max_strategies=max_strategies,
                    selected_modules=selected_modules,
                    should_stop=self._should_stop
                )
        elif hasattr(self.matcher, 'get_preset_strategies') and strategy_mode != 'auto':
            strategies = self.matcher.get_preset_strategies(strategy_mode)[:max_strategies]
            self.logger.info(f"根据预设模式 '{strategy_mode}' 匹配策略: {[s.name for s in strategies]}")
        else:
            strategies = await self.matcher.match_strategies(
                diagnosis=diagnosis,
                max_strategies=max_strategies,
                selected_modules=selected_modules,
                should_stop=self._should_stop
            )
            if selected_modules and len(selected_modules) > 0:
                self.logger.info(f"自动匹配策略（已过滤模块 {selected_modules}）: {[s.name for s in strategies]}")
            else:
                self.logger.info(f"自动匹配策略: {[s.name for s in strategies]}")
        
        # 检查停止信号
        if self._is_stopped(should_stop, "步骤 4 完成后"): 
            return {"optimized_prompt": prompt, "message": "Stopped"}
             
        if not strategies:
             return {
                 "optimized_prompt": prompt, 
                 "diagnosis": diagnosis, 
                 "message": "无匹配策略"
             }

        # 阶段 5：候选生成 (并行优化)
        if on_progress:
            on_progress(f"正在生成优化候选方案 (应用策略数: {len(strategies)})...")
        self.logger.info(f"步骤 5: 候选生成... (应用策略数: {len(strategies)})")
        candidates = await self.candidate_generator.generate_candidates(
            prompt, strategies, errors, diagnosis, dataset, should_stop
        )
        
        # 阶段 5.1：构建混合验证集并快速筛选
        # 验证集由正确案例和错误案例组成，比例为 3:2
        validation_set: List[Dict[str, Any]] = self.prompt_evaluator.build_validation_set(
            errors=errors,
            dataset=dataset,
            target_error_count=40,
            correct_error_ratio=1.5
        )
        if on_progress:
            on_progress("正在快速评估候选方案...")
        self.logger.info(f"步骤 5.1: 快速筛选... (候选方案数: {len(candidates)}, 验证集大小: {len(validation_set)})")
        filtered_candidates = await self.prompt_evaluator.rapid_evaluation(candidates, validation_set, should_stop)
        if filtered_candidates:
            self.logger.info(f"筛选后的候选方案及其评分: {[(c['strategy'], round(c.get('score', 0), 4)) for c in filtered_candidates]}")
        
        # 阶段 6：选择最佳方案
        if on_progress:
            on_progress("正在选择最佳方案...")
        self.logger.info("步骤 6: 选择最佳方案...")
        
        # 优化：检查是否可以跳过选择步骤
        skip_selection: bool = False
        skip_reason: str = ""
        
        if len(filtered_candidates) == 1:
            skip_selection = True
            skip_reason = f"仅 1 个候选方案 ({filtered_candidates[0]['strategy']})"
        elif use_negative_fusion and filtered_candidates:
            skip_selection = True
            skip_reason = f"负向优化融合策略模式 ({filtered_candidates[0]['strategy']})"
        
        if skip_selection and filtered_candidates:
            self.logger.info(f"[选择最佳方案] {skip_reason}，跳过选择步骤，直接使用")
            best_result: Dict[str, Any] = filtered_candidates[0]
        else:
            best_result: Dict[str, Any] = self.prompt_evaluator.select_best_candidate(
                filtered_candidates, prompt
            )
        
        # 阶段 7：记录到知识库
        if self.knowledge_base and best_result.get("prompt") != prompt:
            if on_progress:
                on_progress("正在保存知识库记录...")
            self.logger.info("步骤 7: 记录优化结果到知识库...")
            accuracy: float = diagnosis.get("overall_metrics", {}).get("accuracy", 0)
            
            # 生成优化总结
            analysis_summary: str = self._generate_optimization_summary(
                intent_analysis, 
                deep_analysis,
                best_result.get("strategy", "unknown"),
                advanced_diagnosis
            )

            
            applied_strategies: List[str] = [
                c["strategy"] for c in filtered_candidates
            ]
            
            # 阶段 9（提前计算）：计算并准备错误优化历史
            # 这里的目的是能在 Knowledge Base 中记录最新的错误统计
            # 但实际的 DB 更新仍保留在最后（或在此处更新也可以，但为了逻辑清晰，我们先计算）
            current_persistent_errors_list: List[Dict[str, Any]] = []
            
            if project_id and optimized_intents:
                try:
                    # 如果还没有 loading updated_history，这里先计算
                    # 注意：为了避免重复计算，我们在这里计算一次，后续 Stage 9 直接使用
                    # 但考虑到 Stage 9 的现有逻辑比较独立，我们这里先复用 _update_error_optimization_history 逻辑用于展示
                    # 真正的 DB 更新留给 Stage 9 防止副作用（虽然副作用只是 DB 写）
                    
                    # 暂时为了数据一致性，我们在这里就生成 "即将在 Stage 9 保存的数据预览"
                    temp_updated_history = self._update_error_optimization_history(
                        errors, 
                        error_history, 
                        optimized_intents
                    )
                    
                    # 转换为列表并排序
                    for hash_key, val in temp_updated_history.items():
                         val_copy = val.copy()
                         val_copy['hash_key'] = hash_key # 保留 key 方便调试
                         current_persistent_errors_list.append(val_copy)
                    
                    # 按 optimization_count 倒序排序
                    current_persistent_errors_list.sort(
                        key=lambda x: x.get("optimization_count", 0), 
                        reverse=True
                    )
                    
                except Exception as e:
                    self.logger.warning(f"准备错误历史数据失败: {e}")

            # 提取困难样本 (hard_cases)
            difficult_cases = diagnosis.get("error_patterns", {}).get("hard_cases", [])

            self.knowledge_base.record_optimization(
                original_prompt=prompt,
                optimized_prompt=best_result.get("prompt", prompt),
                analysis_summary=analysis_summary,
                intent_analysis=intent_analysis,
                applied_strategies=applied_strategies,
                accuracy_before=accuracy,
                deep_analysis=deep_analysis,
                newly_failed_cases=newly_failed_cases,
                difficult_cases=difficult_cases,
                persistent_errors=current_persistent_errors_list,
                # 新增：传递被过滤的澄清类和多意图类意图
                clarification_intents=intent_analysis.get("clarification_intents", []),
                multi_intent_intents=intent_analysis.get("multi_intent_intents", [])
            )
        
        self.logger.info(f"优化任务结束。最终胜出策略: {best_result.get('strategy')}, 预估提升分数: {best_result.get('score', 0):.4f}")
        self.logger.info(f"最终提示词摘要: {best_result['prompt'][:100]}... (总长度: {len(best_result['prompt'])})")
        
        # 阶段 8: 验证优化后的提示词
        if on_progress:
            on_progress("正在验证优化后的提示词...")
        self.logger.info("步骤 8: 验证优化后的提示词...")
        # 使用优化配置的模型进行验证 (用户要求)
        temp_validator = PromptValidator(self.llm_helper)
        validation_result: Dict[str, Any] = await temp_validator.validate_optimized_prompt(
            prompt,
            best_result["prompt"],
            should_stop
        )
        
        # 构建返回结果
        result: Dict[str, Any] = {
            "optimized_prompt": best_result["prompt"],
            "diagnosis": diagnosis,
            "intent_analysis": intent_analysis,
            "deep_analysis": deep_analysis,
            "applied_strategies": [
                {"name": c["strategy"], "success": True} 
                for c in filtered_candidates
            ],
            "best_strategy": best_result.get("strategy", "none"),
            "improvement": best_result.get("score", 0),
            "candidates": [
                {"strategy": c["strategy"], "score": c.get("score", 0)} 
                for c in filtered_candidates
            ]
        }
        
        # 如果验证失败，添加失败标记
        if not validation_result.get("is_valid", True):
            self.logger.warning(f"优化结果验证失败: {validation_result.get('failure_reason')}")
            result["validation_failed"] = True
            result["failure_reason"] = validation_result.get("failure_reason", "优化失败, 模型输出格式异常")
            result["validation_issues"] = validation_result.get("issues", [])
            
            # 标记所有策略为验证失败
            for strategy_result in result["applied_strategies"]:
                strategy_result["validation_failed"] = True
        else:
            result["validation_failed"] = False
            result["failure_reason"] = ""
        
        # 阶段 9：更新错误优化历史（优化完成后追踪）
        if project_id and optimized_intents:
            try:
                from app.db.storage import update_error_optimization_history
                
                # 更新错误优化历史
                updated_history: Dict[str, Any] = self._update_error_optimization_history(
                    errors, 
                    error_history, 
                    optimized_intents
                )
                
                # 保存更新后的历史
                update_error_optimization_history(project_id, updated_history)
                self.logger.info(
                    f"[错误追踪] 已更新错误优化历史，记录数: {len(updated_history)}"
                )
            except Exception as e:
                self.logger.warning(f"更新错误优化历史失败: {e}")
        
        return result


    def diagnose(
        self, 
        prompt: str, 
        errors: List[Dict[str, Any]],
        total_count: int = None,
        project_id: str = None
    ) -> Dict[str, Any]:
        """
        仅执行诊断分析
        
        :param prompt: 当前提示词
        :param errors: 错误样例列表
        :param total_count: 总样本数
        :param project_id: 项目ID
        :return: 诊断结果
        """
        return diagnose_prompt_performance(
            prompt, 
            errors, 
            total_count,
            llm_client=self.llm_client,
            model_config=self.model_config,
            project_id=project_id
        )
        
    def _generate_optimization_summary(
        self,
        intent_analysis: Dict[str, Any],
        deep_analysis: Dict[str, Any],
        best_strategy: str,
        advanced_diagnosis: Dict[str, Any] = None
    ) -> str:
        """
        生成优化总结文本
        
        :param intent_analysis: 意图分析结果
        :param deep_analysis: 深度分析结果
        :param best_strategy: 最佳策略名称
        :param advanced_diagnosis: 高级诊断结果 (NEW)
        :return: 优化总结文本
        """
        lines: List[str] = []
        
        # 总错误数
        total_errors: int = intent_analysis.get("total_errors", 0)
        lines.append(f"本次优化处理了 {total_errors} 个错误样例。")
        
        # Top 失败意图
        top_failures: List[Dict[str, Any]] = intent_analysis.get(
            "top_failing_intents", []
        )[:3]
        if top_failures:
            failure_names: List[str] = [f.get("intent", "") for f in top_failures]
            lines.append(f"主要失败意图: {', '.join(failure_names)}。")
            
        # 高级诊断结果
        if advanced_diagnosis:
            issues = []
            if advanced_diagnosis.get("context_analysis", {}).get("has_issue"):
                issues.append("上下文指代不明")
            if advanced_diagnosis.get("multi_intent_analysis", {}).get("has_issue"):
                issues.append("多意图混淆")
            if advanced_diagnosis.get("domain_analysis", {}).get("domain_confusion"):
                issues.append("领域界限模糊")
            if advanced_diagnosis.get("clarification_analysis", {}).get("has_issue"):
                issues.append("澄清机制异常")
                
            if issues:
                lines.append(f"发现以下定向问题: {', '.join(issues)}。")
            
        # 深度分析结果
        analyses: List[Dict[str, Any]] = deep_analysis.get("analyses", [])
        if analyses:
            lines.append(f"对 {len(analyses)} 个高失败率意图进行了深度分析。")
            
        # 应用的策略
        lines.append(f"采用了 {best_strategy} 策略进行优化。")
        
        
        return " ".join(lines)

    def _filter_clarification_samples(
        self,
        errors: List[Dict[str, Any]],
        clarification_analysis: Dict[str, Any]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        过滤澄清类样本，将错误分为主要优化样本和低优先级样本
        
        澄清类样本（target 是澄清意图的）优先级较低，主要优化确定的单意图
        
        :param errors: 原始错误列表
        :param clarification_analysis: 澄清分析结果
        :return: (主要优化样本, 低优先级澄清类样本)
        """
        # 获取澄清类样本列表
        clarification_targets: List[Dict[str, Any]] = clarification_analysis.get(
            "clarification_target_samples", []
        )
        
        if not clarification_targets:
            # 无澄清类样本，全部为主要优化目标
            return errors, []
        
        # 构建澄清类样本的 query 集合（用于快速查找）
        clarification_queries: set = {
            err.get("query", "") for err in clarification_targets
        }
        
        main_errors: List[Dict[str, Any]] = []
        low_priority_errors: List[Dict[str, Any]] = []
        
        for err in errors:
            if err.get("query", "") in clarification_queries:
                low_priority_errors.append(err)
            else:
                main_errors.append(err)
        
        self.logger.info(
            f"[澄清过滤] 主要优化样本: {len(main_errors)}, 低优先级澄清类样本: {len(low_priority_errors)}"
        )
        
        return main_errors, low_priority_errors

    def _update_error_optimization_history(
        self,
        errors: List[Dict[str, Any]],
        history: Dict[str, Any],
        optimized_intents: List[str]
    ) -> Dict[str, Any]:
        """
        更新错误样本的优化次数历史
        
        只追踪被当前优化策略针对的意图相关的错误样本
        
        :param errors: 当前轮次的错误样本列表
        :param history: 现有的优化历史记录
        :param optimized_intents: 本轮被优化的意图列表
        :return: 更新后的历史记录
        """
        import hashlib
        
        updated_history: Dict[str, Any] = history.copy() if history else {}
        
        for err in errors:
            target: str = str(err.get("target", ""))
            
            # 只追踪被优化意图相关的错误
            if target not in optimized_intents:
                continue
            
            query: str = str(err.get("query", ""))
            
            # 使用 query + target 生成唯一标识
            hash_key: str = hashlib.md5(
                f"{query}:{target}".encode()
            ).hexdigest()[:16]
            
            if hash_key in updated_history:
                # 已存在，增加优化次数
                updated_history[hash_key]["optimization_count"] += 1
                updated_history[hash_key]["last_output"] = str(err.get("output", ""))
                
                # 检查是否为顽固错误
                if updated_history[hash_key]["optimization_count"] >= 3:
                    updated_history[hash_key]["is_persistent"] = True
            else:
                # 新增记录
                updated_history[hash_key] = {
                    "query": query[:200],
                    # 限制长度
                    "target": target,
                    "optimization_count": 1,
                    "last_output": str(err.get("output", "")),
                    "is_persistent": False
                }
        
        return updated_history

    def _identify_persistent_errors(
        self,
        history: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        识别顽固错误样本（连续错误>=3次）
        
        :param history: 错误优化历史记录
        :return: 顽固错误样本列表
        """
        persistent_samples: List[Dict[str, Any]] = []
        
        for hash_key, record in history.items():
            if record.get("is_persistent", False):
                persistent_samples.append({
                    "query": record.get("query", ""),
                    "target": record.get("target", ""),
                    "optimization_count": record.get("optimization_count", 0)
                })
        
        if persistent_samples:
            self.logger.info(
                f"[顽固错误] 发现 {len(persistent_samples)} 个顽固错误样本 "
                f"（连续优化>=3次仍错误）"
            )
        
        return persistent_samples
