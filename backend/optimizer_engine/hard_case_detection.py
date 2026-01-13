"""
困难案例检测模块
实现用于在提示词优化中识别困难案例的高级策略。
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict, Counter
import numpy as np
import networkx as nx
import networkx as nx
from sklearn.neighbors import NearestNeighbors
from openai import AsyncOpenAI, OpenAI

# 如果需要，可以尝试导入用于文本分析的其他可选依赖项
# 目前我们坚持使用标准库和 sklearn

class HardCaseDetector:
    """
    使用多维分析识别困难案例的高级检测器。
    """
    
    def __init__(
        self, 
        llm_client: Any = None, 
        model_config: Dict[str, Any] = None, 
        weights: Dict[str, float] = None
    ):
        """
        初始化困难案例检测器。
        
        参数:
            llm_client: 用于生成向量嵌入的 OpenAI 兼容客户端
            model_config: 模型/客户端的配置
            weights: 不同检测策略的权重
        """
        self.llm_client: Any = llm_client
        self.model_config: Dict[str, Any] = model_config or {}
        self.logger: logging.Logger = logging.getLogger(__name__)
        
        self.weights: Dict[str, float] = weights or {
            "confidence": 0.25,
            "boundary": 0.25,
            "ambiguity": 0.20,
            "confusion": 0.15,
            "diversity": 0.15
        }
    
    def detect_hard_cases(
        self, 
        predictions: List[Dict[str, Any]], 
        dataset: List[Dict[str, Any]] = None, 
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        使用所有可用策略检测困难案例的主入口。
        
        参数:
            predictions: 预测对象列表（包含查询、目标、输出以及可选的概率）
                         注意：从诊断传递的 'errors' 是 predictions 的子集，其中 target != output。
                         为了获得最佳结果，理想情况下应该是所有预测，但如果仅传递错误，
                         像 'boundary'（使用邻居）这样的策略可能效果较差，但仍然可用。
            dataset: 完整数据集（可选，可用于提供上下文）
            top_k: 返回的困难案例数量
            
        返回:
            包含原因和得分的困难案例对象列表。
        """
        if not predictions:
            return []

        all_scores: List[Dict[str, Any]] = []
        
        # 1. 基于置信度的检测
        try:
            conf_cases: List[Dict[str, Any]] = self._confidence_based(predictions)
            self._add_weighted_scores(all_scores, conf_cases, "confidence")
        except Exception as e:
            self.logger.warning(f"基于置信度的检测失败: {e}")

        # 2. 基于混淆的检测
        try:
            # 从预测中可用的目标标签推导意图
            intents: List[str] = list(set([str(p.get("target", "")) for p in predictions]))
            conf_net_cases: List[Dict[str, Any]] = self._confusion_based(predictions, intents)
            self._add_weighted_scores(all_scores, conf_net_cases, "confusion")
        except Exception as e:
            self.logger.warning(f"基于混淆矩阵的检测失败: {e}")

        # 3. 基于向量嵌入的检测（边界与多样性）
        # 仅当我们有 LLM 客户端来生成向量嵌入时才运行
        if self.llm_client:
            try:
                # 批量生成向量嵌入
                queries: List[str] = [str(p.get("query", "")) for p in predictions]
                embeddings: List[List[float]] = self._extract_embeddings(queries)
                
                if embeddings and len(embeddings) == len(predictions):
                    # 边界检测
                    boundary_cases: List[Dict[str, Any]] = self._boundary_based(predictions, embeddings)
                    self._add_weighted_scores(all_scores, boundary_cases, "boundary")
                    
                    # 多样性检测
                    diversity_cases: List[Dict[str, Any]] = self._diversity_based(predictions, embeddings)
                    self._add_weighted_scores(all_scores, diversity_cases, "diversity")
            except Exception as e:
                self.logger.warning(f"基于向量嵌入的检测失败: {e}")
        
        # 4. 歧义检测（目前在没有外部 NLP 工具的情况下简化）
        # 我们可以实现一个基本版本，或者如果过于复杂且没有重型 NLP 库则跳过
        # 目前，让我们跳过复杂的歧义检测，以避免像 spacy 这样的依赖
        
        # 按综合得分排序
        all_scores.sort(key=lambda x: x["composite_score"], reverse=True)
        
        # 去重（一个案例可能被多个探测器标记）
        # 我们合并同一个案例的分数
        merged_cases: List[Dict[str, Any]] = self._merge_and_deduplicate(all_scores)
        
        # 限制在 top_k，可能平衡分布
        return merged_cases[:top_k]

    def _add_weighted_scores(
        self, 
        all_scores: List[Dict[str, Any]], 
        cases: List[Dict[str, Any]], 
        dim_name: str
    ) -> None:
        """
        为检测结果添加加权分数。
        """
        weight: float = self.weights.get(dim_name, 0.2)
        for case in cases:
            case["composite_score"] = case.get("score", 0) * weight
            case["dimension"] = dim_name
            all_scores.append(case)

    def _merge_and_deduplicate(
        self, 
        scored_cases: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        合并同一基础预测案例的分数并去重。
        """
        merged: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"case": None, "reasons": [], "composite_score": 0, "dimensions": []}
        )
        
        for item in scored_cases:
            # 如果可用，我们使用案例的唯一标识符，否则使用查询内容
            # 假设 'case' 是原始预测字典对象。
            # 使用查询 + 目标作为键
            p: Dict[str, Any] = item["case"]
            key: Tuple[str, str] = (str(p.get("query", "")), str(p.get("target", "")))
            
            entry: Dict[str, Any] = merged[key]
            if entry["case"] is None:
                entry["case"] = p
            
            entry["composite_score"] += item["composite_score"]
            entry["reasons"].append(f"{item.get('reason', '')} ({item.get('dimension')})")
            if item.get('dimension') not in entry["dimensions"]:
                entry["dimensions"].append(item.get('dimension'))
        
        result: List[Dict[str, Any]] = []
        for v in merged.values():
            result.append({
                "case": v["case"],
                "reason": "; ".join(v["reasons"]),
                "score": v["composite_score"],
                "dimensions": v["dimensions"],
                # 为了与现有的注入逻辑兼容而展平
                "query": v["case"].get("query"),
                "target": v["case"].get("target"),
                "output": v["case"].get("output"),
                "analysis": "; ".join(v["reasons"])
            })
            
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    def _confidence_based(
        self, 
        predictions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        识别置信度低或存在竞争意图的案例。
        """
        hard_cases: List[Dict[str, Any]] = []
        threshold: float = 0.7
        
        for pred in predictions:
            # 检查是否存在概率分布
            probs: Optional[Dict[str, float]] = pred.get("probability_distribution") or pred.get("probs")
            if not probs or not isinstance(probs, dict):
                continue
                
            try:
                values: List[float] = list(probs.values())
                if not values:
                    continue
                    
                max_prob: float = max(values)
                # 获取第二大值
                sorted_probs: List[float] = sorted(values)
                second_max: float = sorted_probs[-2] if len(sorted_probs) > 1 else 0
                
                if max_prob < threshold:
                    hard_cases.append({
                        "case": pred,
                        "reason": f"低置信度({max_prob:.2f})",
                        "score": 1 - max_prob
                    })
                elif max_prob - second_max < 0.2:
                    hard_cases.append({
                        "case": pred,
                        "reason": f"多意图竞争(差距{max_prob-second_max:.2f})",
                        "score": 0.5 * (1 - (max_prob - second_max))
                    })
            except Exception:
                continue
                
        return hard_cases

    def _confusion_based(
        self, 
        predictions: List[Dict[str, Any]], 
        intents: List[str]
    ) -> List[Dict[str, Any]]:
        """
        识别处于关键混淆路径上的案例。
        """
        confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
        # 从预测构建混淆矩阵
        # 注意：如果传递的 'predictions' 仅包含错误，则此图仅代表错误。
        for pred in predictions:
            actual: str = str(pred.get("target", "")).strip()
            predicted: str = str(pred.get("output", "")).strip()
            if actual != predicted:
                confusion[actual][predicted] += 1
                
        G: nx.DiGraph = nx.DiGraph()
        for actual in confusion:
            for predicted, count in confusion[actual].items():
                if count >= 1: # 即便在数据集很小时也包含单个错误
                    G.add_edge(actual, predicted, weight=count)
        
        hard_cases: List[Dict[str, Any]] = []
        total_preds: int = len(predictions) if predictions else 1
        
        # 计算介数中心性以识别作为混淆意图的“桥梁”节点
        try:
            centrality: Dict[str, float] = nx.betweenness_centrality(G)
        except:
            centrality = {}

        for pred in predictions:
            actual: str = str(pred.get("target", "")).strip()
            predicted: str = str(pred.get("output", "")).strip()
            
            if actual != predicted and G.has_edge(actual, predicted):
                weight: int = G[actual][predicted]["weight"]
                path_importance: float = weight / total_preds
                
                # 如果预测类是混淆图中的中心节点，则提高分数
                node_importance: float = centrality.get(predicted, 0)
                
                if path_importance > 0.05 or weight > 2:
                    hard_cases.append({
                        "case": pred,
                        "reason": f"核心混淆路径({actual}→{predicted})",
                        "score": min(1.0, path_importance * 5 + node_importance),
                        "network_role": "bridge" if node_importance > 0.1 else "edge"
                    })
                    
        return hard_cases

    def _boundary_based(
        self, 
        predictions: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ) -> List[Dict[str, Any]]:
        """
        使用 KNN 识别边界案例。
        """
        if len(predictions) < 5:
            return []
            
        n_neighbors: int = min(5, len(predictions) - 1)
        knn: NearestNeighbors = NearestNeighbors(n_neighbors=n_neighbors)
        knn.fit(embeddings)
        
        boundary_cases: List[Dict[str, Any]] = []
        
        for i, pred in enumerate(predictions):
            distances, indices = knn.kneighbors([embeddings[i]], n_neighbors)
            
            # 获取邻居的真实标签
            neighbor_labels: List[str] = [str(predictions[j].get("target", "")) for j in indices[0]]
            current_label: str = str(pred.get("target", ""))
            
            # 计算一致性
            same_class_count: int = neighbor_labels.count(current_label)
            same_class_ratio: float = same_class_count / n_neighbors
            
            # 如果比例是混合的（例如 0.3-0.7），则它是边界案例
            # 如果比例非常低（例如 0），它可能是一个离群点或标签错误
            if 0.2 <= same_class_ratio <= 0.8:
                boundary_cases.append({
                    "case": pred,
                    "reason": f"边界区域(邻居一致性{same_class_ratio:.2f})",
                    "score": 1.0 - abs(0.5 - same_class_ratio) * 2
                })
                
        return boundary_cases

    def _diversity_based(
        self, 
        predictions: List[Dict[str, Any]], 
        embeddings: List[List[float]]
    ) -> List[Dict[str, Any]]:
        """
        识别特征空间中的孤立案例（离群点）。
        """
        if len(predictions) < 3:
            return []
            
        knn: NearestNeighbors = NearestNeighbors(n_neighbors=2) # 包含点自身，所以为 2
        knn.fit(embeddings)
        distances, _ = knn.kneighbors(embeddings)
        
        # distances[:, 1] 是到最近邻居（不包括自身）的距离
        nearest_dists: List[float] = [d[1] for d in distances]
        
        # 确定“孤立”的阈值（例如 90 百分位）
        threshold: float = np.percentile(nearest_dists, 90) if nearest_dists else 0
        
        hard_cases: List[Dict[str, Any]] = []
        for i, (pred, dist) in enumerate(zip(predictions, nearest_dists)):
            if dist > threshold and threshold > 0:
                hard_cases.append({
                    "case": pred,
                    "reason": f"特征孤立点(距离{dist:.2f})",
                    "score": min(1.0, (dist / threshold) * 0.5) 
                })
                
        return hard_cases

    def _extract_embeddings(
        self, 
        texts: List[str]
    ) -> List[List[float]]:
        """
        使用 LLM 客户端批量提取嵌入。
        
        :param texts: 需要提取嵌入的文本列表
        :return: 嵌入向量列表
        """
        if not self.llm_client:
            self.logger.warning("[嵌入向量-困难案例] 未配置 LLM 客户端，跳过嵌入提取")
            return []
        
        # 记录嵌入请求输入日志
        self.logger.info(f"[嵌入向量请求-困难案例] 输入文本数量: {len(texts)}")
        if texts:
            self.logger.debug(f"[嵌入向量请求-困难案例] 首个文本预览: {texts[0][:100]}...")
            
        try:
            # 检查客户端是否支持向量嵌入
            if hasattr(self.llm_client, 'embeddings'):
                 model_name: Optional[str] = self.model_config.get("embedding_model")
                 
                 # 智能默认逻辑
                 if not model_name:
                     # 根据 base_url 或模型名称判断是否使用火山引擎/豆包
                     base_url: str = self.model_config.get("base_url", "").lower()
                     chat_model: str = self.model_config.get("model_name", "").lower()
                     
                     if "volces.com" in base_url:
                         # 对于火山引擎，默认使用通用的嵌入端点
                         # 注意：如果用户没有部署这个特定的端点，这可能仍会失败，
                         # 但总比肯定不存在的 ada-002 要好。
                         model_name = "doubao-embedding-pro-0.8"
                     elif "openai" in base_url or not base_url:
                         # 默认为 OpenAI 标准
                         model_name = "text-embedding-ada-002"
                     else:
                         # 对于其他提供商，我们可能没有安全的默认值。
                         # 记录警告并跳过比在 ada-002 上崩溃或报 404 更好
                         self.logger.warning("[嵌入向量请求-困难案例] 未配置 embedding_model，且无法推断默认模型。跳过困难案例检测。")
                         return []

                 self.logger.info(f"[嵌入向量请求-困难案例] 使用嵌入模型: {model_name}")
                 
                 self.logger.info(f"[嵌入向量请求-困难案例] 使用嵌入模型: {model_name}")
                 
                 # 异步客户端支持
                 if isinstance(self.llm_client, AsyncOpenAI):
                     # AsyncOpenAI 需要 await
                     # 注意：HardCaseDetector 的方法目前大多是同步调用的 (detector.detect_hard_cases)
                     # 但 multi_strategy.py 中调用 detector 是在一个 lambda 里 run_in_executor 的:
                     # diagnosis = await loop.run_in_executor(None, lambda: diagnose_prompt_performance(...))
                     # 而 diagnose_prompt_performance 内部同步调用 detector.detect_hard_cases
                     # 这导致我们在一个同步上下文中，无法直接 await 一个 async client。
                     # 必须权衡：
                     # 1. 改造 diagnose_prompt_performance 为 async。 (这会引起连锁反应，涉及 diagnosis.py)
                     # 2. 在这里临时创建一个 loop 运行 async (不推荐，nested loop)
                     # 3. 如果是 AsyncClient，在这里回退到 httpx 或者 manual request? 不行。
                     # 
                     # 最佳方案：既然 diagnose_prompt_performance 已经在 run_in_executor 中运行（即在独立线程中），
                     # 我们可以使用 asyncio.run() 来运行这个 async 调用，前提是这线程里没有 running loop。
                     # 但 run_in_executor 的线程通常是没有 loop 的。
                     # 不过，如果 llm_client 是 AsyncOpenAI，它本身绑定了主线程的 loop 吗？
                     # 通常 AsyncOpenAI 可以在任何 loop 中使用，只要 session 没绑定死。
                     
                     # 让我们尝试使用 asyncio.run()。
                     import asyncio
                     try:
                         loop = asyncio.get_event_loop()
                     except RuntimeError:
                         loop = asyncio.new_event_loop()
                         asyncio.set_event_loop(loop)
                         
                     response = loop.run_until_complete(
                         self.llm_client.embeddings.create(
                            input=texts,
                            model=model_name,
                            timeout=int(self.model_config.get("timeout", 180))
                         )
                     )
                 else:
                     # 同步客户端
                     response: Any = self.llm_client.embeddings.create(
                         input=texts,
                         model=model_name,
                         timeout=int(self.model_config.get("timeout", 180))
                     )
                 
                 embeddings: List[List[float]] = [data.embedding for data in response.data]
                 
                 # 记录嵌入响应输出日志
                 self.logger.info(f"[嵌入向量响应-困难案例] 生成向量数量: {len(embeddings)}")
                 if embeddings:
                     self.logger.debug(f"[嵌入向量响应-困难案例] 向量维度: {len(embeddings[0])}")
                 
                 return embeddings
        except Exception as e:
            # 捕获所有向量嵌入错误（404, 400 等）以防止整个优化过程崩溃
            # 尤其是对于提供商不兼容的情况（例如阿里云与 OpenAI 的模型名称）
            self.logger.warning(f"[嵌入向量请求-困难案例] 生成向量嵌入失败: {e}。跳过基于向量的困难案例检测。")
            return []
        
        return []
