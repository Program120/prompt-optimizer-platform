"""
Few-Shot 样本管理器

基于 text2vec 向量化计算样本难区分程度，管理 Few-Shot 样本的注入、配额和替换策略。

核心功能：
1. 使用 text2vec 计算样本的"难区分程度"
2. 按意图分组的数量限制（每个意图 ≤ 10%，澄清/多意图 ≤ 5%）
3. 基于评分的低分样本替换策略
"""
import hashlib
from loguru import logger
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class FewShotSampleManager:
    """
    Few-Shot 样本管理器
    
    管理 Few-Shot 难例样本的评分、注入、配额检查和替换。
    样本存储在 IntentIntervention 表中，通过 is_fewshot_sample 标记。
    """
    
    # 难度评分阈值（只有 ≥ 该阈值的样本才会被考虑注入）
    DIFFICULTY_THRESHOLD: float = 7.0
    
    # 意图类型配额限制
    # 普通意图：该意图样本总数的 10%
    NORMAL_INTENT_QUOTA_RATIO: float = 0.10
    # 澄清意图：总样本数的 5%
    CLARIFICATION_QUOTA_RATIO: float = 0.05
    # 多意图：总样本数的 5%
    MULTI_INTENT_QUOTA_RATIO: float = 0.05
    
    # 向量模型单例（延迟加载）
    _similarity_model: Optional[Any] = None
    
    def __init__(self, project_id: str, file_id: str = ""):
        """
        初始化样本管理器
        
        :param project_id: 项目 ID
        :param file_id: 文件 ID（可选）
        """
        self.project_id: str = project_id
        self.file_id: str = file_id
        
        logger.info(f"[FewShotSampleManager] 初始化，项目ID: {project_id}, 文件ID: {file_id}")
    
    @classmethod
    def _get_similarity_model(cls) -> Any:
        """
        获取 text2vec 相似度模型（单例模式，延迟加载）
        
        :return: Similarity 模型实例
        """
        if cls._similarity_model is None:
            try:
                from text2vec import Similarity
                cls._similarity_model = Similarity()
                logger.info("[FewShotSampleManager] text2vec Similarity 模型加载成功")
            except ImportError:
                logger.warning("[FewShotSampleManager] text2vec 未安装，将使用简化评分逻辑")
                cls._similarity_model = None
            except Exception as e:
                logger.error(f"[FewShotSampleManager] 加载 text2vec 模型失败: {e}")
                cls._similarity_model = None
        return cls._similarity_model
    
    def calculate_difficulty_score(
        self, 
        sample: Dict[str, Any], 
        all_samples: List[Dict[str, Any]]
    ) -> float:
        """
        计算样本的难区分程度评分
        
        评分算法：
        1. 计算当前样本 query 与【不同意图】样本的最高相似度（跨意图相似度）
        2. 计算当前样本 query 与【同意图】样本的最高相似度（同意图相似度）
        3. 难区分度 = 跨意图相似度 * 10（映射到 0-10 分）
        
        高分意味着：该样本 query 与其他意图的样本非常相似，容易混淆
        
        :param sample: 当前样本 {"query": ..., "target": ..., ...}
        :param all_samples: 所有样本列表
        :return: 难度评分 0-10
        """
        query: str = str(sample.get("query", "")).strip()
        target: str = str(sample.get("target", "")).strip()
        
        if not query or not all_samples:
            return 0.0
        
        sim_model = self._get_similarity_model()
        
        if sim_model is None:
            # 无 text2vec，使用简化评分：基于字符串相似度
            return self._calculate_simple_difficulty(sample, all_samples)
        
        # 收集不同意图和同意图的样本
        cross_intent_queries: List[str] = []
        same_intent_queries: List[str] = []
        
        for s in all_samples:
            s_query: str = str(s.get("query", "")).strip()
            s_target: str = str(s.get("target", "")).strip()
            
            # 跳过自身
            if s_query == query:
                continue
            
            if s_target == target:
                same_intent_queries.append(s_query)
            else:
                cross_intent_queries.append(s_query)
        
        # 计算跨意图最高相似度
        max_cross_similarity: float = 0.0
        for cq in cross_intent_queries[:50]:
            # 限制计算数量避免性能问题
            try:
                score: float = sim_model.get_score(query, cq)
                if score > max_cross_similarity:
                    max_cross_similarity = score
            except Exception as e:
                logger.debug(f"[FewShotSampleManager] 相似度计算失败: {e}")
                continue
        
        # 难度评分：跨意图相似度映射到 0-10
        # 相似度范围 [-1, 1]，通常正常样本在 0.0-0.5，混淆样本在 0.5-1.0
        # 映射公式：(相似度 + 1) / 2 * 10，然后调整为只关注高相似度
        difficulty_score: float = max(0.0, max_cross_similarity) * 10.0
        
        logger.debug(
            f"[FewShotSampleManager] 样本评分: query='{query[:30]}...', "
            f"target={target}, 跨意图最高相似度={max_cross_similarity:.3f}, "
            f"难度评分={difficulty_score:.1f}"
        )
        
        return round(difficulty_score, 2)
    
    def _calculate_simple_difficulty(
        self, 
        sample: Dict[str, Any], 
        all_samples: List[Dict[str, Any]]
    ) -> float:
        """
        简化版难度评分（无 text2vec 时使用）
        
        基于字符串包含关系和长度相似度
        
        :param sample: 当前样本
        :param all_samples: 所有样本
        :return: 难度评分 0-10
        """
        query: str = str(sample.get("query", "")).strip().lower()
        target: str = str(sample.get("target", "")).strip()
        
        if not query:
            return 0.0
        
        similar_count: int = 0
        
        for s in all_samples:
            s_query: str = str(s.get("query", "")).strip().lower()
            s_target: str = str(s.get("target", "")).strip()
            
            # 只考虑不同意图的样本
            if s_target == target or s_query == query:
                continue
            
            # 检查字符串相似度（简单的包含关系）
            common_chars: int = sum(1 for c in query if c in s_query)
            similarity: float = common_chars / max(len(query), 1)
            
            if similarity > 0.5:
                similar_count += 1
        
        # 相似样本越多，难度越高
        difficulty: float = min(10.0, similar_count * 2.0)
        
        logger.debug(
            f"[FewShotSampleManager] 简化评分: query='{query[:30]}...', "
            f"相似样本数={similar_count}, 难度={difficulty:.1f}"
        )
        
        return difficulty
    
    def check_quota(
        self, 
        intent: str, 
        intent_type: str,
        intent_sample_counts: Dict[str, int],
        total_sample_count: int,
        current_fewshot_counts: Dict[str, int]
    ) -> Tuple[bool, int, int]:
        """
        检查指定意图的 Few-Shot 配额
        
        :param intent: 意图名称
        :param intent_type: 意图类型 ("normal", "clarification", "multi_intent")
        :param intent_sample_counts: 各意图的样本总数 {"意图A": 100, ...}
        :param total_sample_count: 数据集总样本数
        :param current_fewshot_counts: 当前各意图的 Few-Shot 数量
        :return: (是否还有配额, 当前数量, 配额上限)
        """
        current_count: int = current_fewshot_counts.get(intent, 0)
        
        if intent_type == "clarification":
            # 澄清意图：总样本 * 5%
            quota_limit: int = max(1, int(total_sample_count * self.CLARIFICATION_QUOTA_RATIO))
            # 统计所有澄清意图的总数
            total_clarification: int = sum(
                v for k, v in current_fewshot_counts.items() 
                if self._is_clarification_intent(k)
            )
            has_quota: bool = total_clarification < quota_limit
            logger.debug(
                f"[FewShotSampleManager] 澄清意图配额检查: "
                f"当前总数={total_clarification}, 上限={quota_limit}"
            )
            return has_quota, total_clarification, quota_limit
            
        elif intent_type == "multi_intent":
            # 多意图：总样本 * 5%
            quota_limit = max(1, int(total_sample_count * self.MULTI_INTENT_QUOTA_RATIO))
            total_multi: int = sum(
                v for k, v in current_fewshot_counts.items() 
                if self._is_multi_intent(k)
            )
            has_quota = total_multi < quota_limit
            logger.debug(
                f"[FewShotSampleManager] 多意图配额检查: "
                f"当前总数={total_multi}, 上限={quota_limit}"
            )
            return has_quota, total_multi, quota_limit
        else:
            # 普通意图：该意图样本 * 10%
            intent_total: int = intent_sample_counts.get(intent, 100)
            quota_limit = max(1, int(intent_total * self.NORMAL_INTENT_QUOTA_RATIO))
            has_quota = current_count < quota_limit
            logger.debug(
                f"[FewShotSampleManager] 意图 '{intent}' 配额检查: "
                f"当前={current_count}, 上限={quota_limit} (总样本={intent_total})"
            )
            return has_quota, current_count, quota_limit
    
    def _is_clarification_intent(self, intent: str) -> bool:
        """
        判断是否为澄清类意图
        
        :param intent: 意图名称
        :return: 是否为澄清类
        """
        clarification_keywords: List[str] = [
            "澄清", "clarification", "clarify", "unclear", 
            "需要更多信息", "需要澄清", "追问"
        ]
        intent_lower: str = intent.lower()
        return any(kw in intent_lower for kw in clarification_keywords)
    
    def _is_multi_intent(self, intent: str) -> bool:
        """
        判断是否为多意图
        
        :param intent: 意图名称
        :return: 是否为多意图
        """
        # 多意图通常包含 + 或 , 分隔
        multi_indicators: List[str] = ["+", ",", "和", "且", "multi", "multiple"]
        intent_lower: str = intent.lower()
        return any(ind in intent_lower for ind in multi_indicators)
    
    def classify_intent_type(self, intent: str) -> str:
        """
        对意图进行分类
        
        :param intent: 意图名称
        :return: 意图类型 ("normal", "clarification", "multi_intent")
        """
        if self._is_clarification_intent(intent):
            return "clarification"
        elif self._is_multi_intent(intent):
            return "multi_intent"
        else:
            return "normal"
    
    def add_fewshot_sample(
        self,
        sample: Dict[str, Any],
        difficulty_score: float,
        intent_sample_counts: Dict[str, int],
        total_sample_count: int,
        current_fewshot_samples: List[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        尝试添加 Few-Shot 样本
        
        如果配额已满，会尝试替换最低分样本。
        
        :param sample: 待添加的样本
        :param difficulty_score: 该样本的难度评分
        :param intent_sample_counts: 各意图的样本总数
        :param total_sample_count: 数据集总样本数
        :param current_fewshot_samples: 当前所有 Few-Shot 样本
        :return: (是否添加成功, 被替换的样本（如有）)
        """
        intent: str = str(sample.get("target", "")).strip()
        intent_type: str = self.classify_intent_type(intent)
        
        # 低于阈值不添加
        if difficulty_score < self.DIFFICULTY_THRESHOLD:
            logger.debug(
                f"[FewShotSampleManager] 样本难度评分 {difficulty_score:.1f} 低于阈值 "
                f"{self.DIFFICULTY_THRESHOLD}，不添加"
            )
            return False, None
        
        # 构建当前 Few-Shot 计数
        current_fewshot_counts: Dict[str, int] = {}
        for fs in current_fewshot_samples:
            fs_intent: str = str(fs.get("target", ""))
            current_fewshot_counts[fs_intent] = current_fewshot_counts.get(fs_intent, 0) + 1
        
        # 检查配额
        has_quota, current_count, quota_limit = self.check_quota(
            intent, intent_type, intent_sample_counts, 
            total_sample_count, current_fewshot_counts
        )
        
        if has_quota:
            # 有配额，直接添加
            logger.info(
                f"[FewShotSampleManager] 添加 Few-Shot 样本: "
                f"intent={intent}, score={difficulty_score:.1f}, "
                f"配额={current_count + 1}/{quota_limit}"
            )
            return True, None
        
        # 无配额，尝试替换最低分样本
        # 筛选同意图类型的现有样本
        same_type_samples: List[Dict[str, Any]] = []
        for fs in current_fewshot_samples:
            fs_intent: str = str(fs.get("target", ""))
            fs_type: str = self.classify_intent_type(fs_intent)
            
            # 对于普通意图，只考虑同一意图下的样本
            # 对于澄清/多意图，考虑所有同类型样本
            if intent_type == "normal":
                if fs_intent == intent:
                    same_type_samples.append(fs)
            else:
                if fs_type == intent_type:
                    same_type_samples.append(fs)
        
        if not same_type_samples:
            logger.debug(
                f"[FewShotSampleManager] 无可替换样本，配额已满"
            )
            return False, None
        
        # 找到最低分样本
        min_score_sample: Optional[Dict[str, Any]] = None
        min_score: float = float('inf')
        
        for fs in same_type_samples:
            fs_score: float = float(fs.get("difficulty_score", 0))
            if fs_score < min_score:
                min_score = fs_score
                min_score_sample = fs
        
        # 如果新样本分数更高，替换
        if min_score_sample and difficulty_score > min_score:
            logger.info(
                f"[FewShotSampleManager] 替换低分样本: "
                f"旧样本分数={min_score:.1f}, 新样本分数={difficulty_score:.1f}, "
                f"intent={intent}"
            )
            return True, min_score_sample
        
        logger.debug(
            f"[FewShotSampleManager] 新样本分数 {difficulty_score:.1f} 不高于现有最低分 "
            f"{min_score:.1f}，不替换"
        )
        return False, None
    
    def get_fewshot_samples_for_injection(
        self, 
        fewshot_samples: List[Dict[str, Any]],
        max_per_intent: int = 3
    ) -> List[Dict[str, Any]]:
        """
        获取用于注入的 Few-Shot 样本
        
        按意图分组，每个意图最多返回 max_per_intent 个最高分样本
        
        :param fewshot_samples: 所有 Few-Shot 样本
        :param max_per_intent: 每个意图最多返回的样本数
        :return: 用于注入的样本列表
        """
        if not fewshot_samples:
            return []
        
        # 按意图分组
        intent_groups: Dict[str, List[Dict[str, Any]]] = {}
        for sample in fewshot_samples:
            intent: str = str(sample.get("target", "unknown"))
            if intent not in intent_groups:
                intent_groups[intent] = []
            intent_groups[intent].append(sample)
        
        # 每个意图取 top N
        result: List[Dict[str, Any]] = []
        for intent, samples in intent_groups.items():
            # 按分数降序排序
            sorted_samples: List[Dict[str, Any]] = sorted(
                samples,
                key=lambda x: float(x.get("difficulty_score", 0)),
                reverse=True
            )
            result.extend(sorted_samples[:max_per_intent])
        
        logger.info(
            f"[FewShotSampleManager] 已选取 {len(result)} 个 Few-Shot 样本用于注入 "
            f"(来自 {len(intent_groups)} 个意图)"
        )
        
        return result
    
    def compute_sample_hash(self, query: str, target: str) -> str:
        """
        计算样本的唯一哈希值
        
        :param query: 查询文本
        :param target: 目标意图
        :return: 16 位哈希字符串
        """
        content: str = f"{query.strip()}:{target.strip()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
