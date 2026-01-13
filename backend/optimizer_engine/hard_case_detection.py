"""
Difficult Case Detection Module
Implements advanced strategies for identifying hard cases in prompt optimization.
"""
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter
import numpy as np
import networkx as nx
from sklearn.neighbors import NearestNeighbors

# Try to import extra optional dependencies for text analysis if needed
# For now we stick to standard libraries and sklearn

class HardCaseDetector:
    """
    Advanced detector for hard cases using multi-dimensional analysis.
    """
    
    def __init__(self, llm_client=None, model_config: Dict[str, Any] = None, weights: Dict[str, float] = None):
        """
        Initialize the HardCaseDetector.
        
        Args:
            llm_client: OpenAI-compatible client for embedding generation
            model_config: Configuration for the model/client
            weights: Weights for different detection strategies
        """
        self.llm_client = llm_client
        self.model_config = model_config or {}
        self.logger = logging.getLogger(__name__)
        
        self.weights = weights or {
            "confidence": 0.25,
            "boundary": 0.25,
            "ambiguity": 0.20,
            "confusion": 0.15,
            "diversity": 0.15
        }
    
    def detect_hard_cases(self, predictions: List[Dict[str, Any]], dataset: List[Dict[str, Any]] = None, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        Main entry point to detect hard cases using all available strategies.
        
        Args:
            predictions: List of prediction objects (containing query, target, output, and optionally probs)
                         Note: 'errors' passed from diagnosis are a subset of predictions where target != output.
                         For best results, this should ideally be all predictions, but if only errors are passed,
                         strategies like 'boundary' (using neighbors) might be less effective but still usable.
            dataset: The full dataset (optional, can be used for context)
            top_k: Number of hard cases to return
            
        Returns:
            List of hard case objects with reasons and scores.
        """
        if not predictions:
            return []

        all_scores = []
        
        # 1. Confidence-based detection
        try:
            conf_cases = self._confidence_based(predictions)
            self._add_weighted_scores(all_scores, conf_cases, "confidence")
        except Exception as e:
            self.logger.warning(f"基于置信度的检测失败: {e}")

        # 2. Confusion-based detection
        try:
            # We derive intents from target labels available in predictions
            intents = list(set([str(p.get("target", "")) for p in predictions]))
            conf_net_cases = self._confusion_based(predictions, intents)
            self._add_weighted_scores(all_scores, conf_net_cases, "confusion")
        except Exception as e:
            self.logger.warning(f"基于混淆矩阵的检测失败: {e}")

        # 3. Embedding-based detection (Boundary & Diversity)
        # Only run if we have an LLM client to generate embeddings
        if self.llm_client:
            try:
                # Batch generate embeddings
                queries = [str(p.get("query", "")) for p in predictions]
                embeddings = self._extract_embeddings(queries)
                
                if embeddings and len(embeddings) == len(predictions):
                    # Boundary detection
                    boundary_cases = self._boundary_based(predictions, embeddings)
                    self._add_weighted_scores(all_scores, boundary_cases, "boundary")
                    
                    # Diversity detection
                    diversity_cases = self._diversity_based(predictions, embeddings)
                    self._add_weighted_scores(all_scores, diversity_cases, "diversity")
            except Exception as e:
                self.logger.warning(f"基于向量嵌入的检测失败: {e}")
        
        # 4. Ambiguity detection (Simplified for now without external NLP tools)
        # We can implement a basic version or skip if too complex without heavy NLP libs
        # For now, let's skip complex ambiguity to avoid dependencies like spacy
        
        # Sort by composite score
        all_scores.sort(key=lambda x: x["composite_score"], reverse=True)
        
        # Deduplicate (a case might be flagged by multiple detectors)
        # We merge scores for the same case
        merged_cases = self._merge_and_deduplicate(all_scores)
        
        # Limit to top_k, potentially balancing distribution
        return merged_cases[:top_k]

    def _add_weighted_scores(self, all_scores: List[Dict], cases: List[Dict], dim_name: str):
        weight = self.weights.get(dim_name, 0.2)
        for case in cases:
            case["composite_score"] = case.get("score", 0) * weight
            case["dimension"] = dim_name
            all_scores.append(case)

    def _merge_and_deduplicate(self, scored_cases: List[Dict]) -> List[Dict]:
        """Merge scores for the same underlying prediction case."""
        merged = defaultdict(lambda: {"case": None, "reasons": [], "composite_score": 0, "dimensions": []})
        
        for item in scored_cases:
            # We use a unique identifier for the case if available, else use query content
            # Assuming 'case' is the original prediction dict object.
            # Using query + target as key
            p = item["case"]
            key = (str(p.get("query", "")), str(p.get("target", "")))
            
            entry = merged[key]
            if entry["case"] is None:
                entry["case"] = p
            
            entry["composite_score"] += item["composite_score"]
            entry["reasons"].append(f"{item.get('reason', '')} ({item.get('dimension')})")
            if item.get('dimension') not in entry["dimensions"]:
                entry["dimensions"].append(item.get('dimension'))
        
        result = []
        for v in merged.values():
            result.append({
                "case": v["case"],
                "reason": "; ".join(v["reasons"]),
                "score": v["composite_score"],
                "dimensions": v["dimensions"],
                # Flattens for compatibility with existing injection logic
                "query": v["case"].get("query"),
                "target": v["case"].get("target"),
                "output": v["case"].get("output"),
                "analysis": "; ".join(v["reasons"])
            })
            
        result.sort(key=lambda x: x["score"], reverse=True)
        return result

    def _confidence_based(self, predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify cases with low confidence or competing intents."""
        hard_cases = []
        threshold = 0.7
        
        for pred in predictions:
            # Check if probability distribution exists
            probs = pred.get("probability_distribution") or pred.get("probs")
            if not probs or not isinstance(probs, dict):
                continue
                
            try:
                values = list(probs.values())
                if not values:
                    continue
                    
                max_prob = max(values)
                # Get second max
                sorted_probs = sorted(values)
                second_max = sorted_probs[-2] if len(sorted_probs) > 1 else 0
                
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

    def _confusion_based(self, predictions: List[Dict[str, Any]], intents: List[str]) -> List[Dict[str, Any]]:
        """Identify cases on critical confusion paths."""
        confusion = defaultdict(lambda: defaultdict(int))
        
        # Build confusion matrix from predictions
        # Note: If 'predictions' passed are only errors, this graph only represents errors.
        for pred in predictions:
            actual = str(pred.get("target", "")).strip()
            predicted = str(pred.get("output", "")).strip()
            if actual != predicted:
                confusion[actual][predicted] += 1
                
        G = nx.DiGraph()
        for actual in confusion:
            for predicted, count in confusion[actual].items():
                if count >= 1: # Include even single errors if dataset is small
                    G.add_edge(actual, predicted, weight=count)
        
        hard_cases = []
        total_preds = len(predictions) if predictions else 1
        
        # Calculate betweenness centrality to identify "bridge" nodes (confusing intents)
        try:
            centrality = nx.betweenness_centrality(G)
        except:
            centrality = {}

        for pred in predictions:
            actual = str(pred.get("target", "")).strip()
            predicted = str(pred.get("output", "")).strip()
            
            if actual != predicted and G.has_edge(actual, predicted):
                weight = G[actual][predicted]["weight"]
                path_importance = weight / total_preds
                
                # Boost score if the predicted class is a central node in confusion graph
                node_importance = centrality.get(predicted, 0)
                
                if path_importance > 0.05 or weight > 2:
                    hard_cases.append({
                        "case": pred,
                        "reason": f"核心混淆路径({actual}→{predicted})",
                        "score": min(1.0, path_importance * 5 + node_importance),
                        "network_role": "bridge" if node_importance > 0.1 else "edge"
                    })
                    
        return hard_cases

    def _boundary_based(self, predictions: List[Dict[str, Any]], embeddings: List[List[float]]) -> List[Dict[str, Any]]:
        """Identify boundary cases using KNN."""
        if len(predictions) < 5:
            return []
            
        n_neighbors = min(5, len(predictions) - 1)
        knn = NearestNeighbors(n_neighbors=n_neighbors)
        knn.fit(embeddings)
        
        boundary_cases = []
        
        for i, pred in enumerate(predictions):
            distances, indices = knn.kneighbors([embeddings[i]], n_neighbors)
            
            # Get neighbors' true labels
            neighbor_labels = [str(predictions[j].get("target", "")) for j in indices[0]]
            current_label = str(pred.get("target", ""))
            
            # Calculate consistency
            same_class_count = neighbor_labels.count(current_label)
            same_class_ratio = same_class_count / n_neighbors
            
            # If ratio is mixed (e.g., 0.3-0.7), it's a boundary case
            # If ratio is very low (e.g. 0), it might be an outlier or label error
            if 0.2 <= same_class_ratio <= 0.8:
                boundary_cases.append({
                    "case": pred,
                    "reason": f"边界区域(邻居一致性{same_class_ratio:.2f})",
                    "score": 1.0 - abs(0.5 - same_class_ratio) * 2
                })
                
        return boundary_cases

    def _diversity_based(self, predictions: List[Dict[str, Any]], embeddings: List[List[float]]) -> List[Dict[str, Any]]:
        """Identify isolated cases (outliers) in feature space."""
        if len(predictions) < 3:
            return []
            
        knn = NearestNeighbors(n_neighbors=2) # 2 because the point itself is included
        knn.fit(embeddings)
        distances, _ = knn.kneighbors(embeddings)
        
        # distances[:, 1] is the distance to the nearest neighbor (excluding self)
        nearest_dists = [d[1] for d in distances]
        
        # Determine threshold for "isolated" (e.g., 90th percentile)
        threshold = np.percentile(nearest_dists, 90) if nearest_dists else 0
        
        hard_cases = []
        for i, (pred, dist) in enumerate(zip(predictions, nearest_dists)):
            if dist > threshold and threshold > 0:
                hard_cases.append({
                    "case": pred,
                    "reason": f"特征孤立点(距离{dist:.2f})",
                    "score": min(1.0, (dist / threshold) * 0.5) 
                })
                
        return hard_cases

    def _extract_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Batch extract embeddings using LLM client."""
        if not self.llm_client:
            return []
            
        try:
            # Check if client supports embeddings
            if hasattr(self.llm_client, 'embeddings'):
                 model_name = self.model_config.get("embedding_model")
                 # Fallback logic: if no specific embedding model is set, 
                 # and we are NOT using openai default base_url, we might need a hint.
                 # But sticking to default or config is best.
                 if not model_name:
                     model_name = "text-embedding-ada-002"
                 
                 response = self.llm_client.embeddings.create(
                     input=texts,
                     model=model_name,
                     timeout=int(self.model_config.get("timeout", 180))
                 )
                 return [data.embedding for data in response.data]
        except Exception as e:
            # Catch all embedding errors (404, 400, etc) to prevent crashing the whole optimization
            # especially for provider incompatibility (e.g. Aliyun vs OpenAI model names)
            self.logger.warning(f"生成向量嵌入失败: {e}。跳过基于向量的困难案例检测。")
            return []
        
        return []

