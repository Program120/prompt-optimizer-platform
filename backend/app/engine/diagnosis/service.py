"""
诊断分析模块 - 服务入口
负责协调各诊断子模块（检测器、指标分析）并生成综合报告
"""
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter, defaultdict
from loguru import logger
from openai import AsyncOpenAI

from .hard_cases import HardCaseDetector
from .metrics import (
    build_confusion_matrix_data,
    cluster_error_patterns,
    analyze_decision_boundaries,
    extract_text_features,
    extract_confusion_pairs,
    identify_hard_cases,
    get_error_category_distribution
)
from .detectors import (
    detect_examples_in_prompt,
    detect_constraints_in_prompt,
    detect_cot_in_prompt,
    detect_format_errors,
    detect_terminology_errors,
    detect_ambiguous_queries,
    detect_boundary_violations,
    analyze_instruction_clarity,
    analyze_constraint_clarity,
    detect_format_issues,
    analyze_output_consistency,
    detect_role_definition,
    analyze_scene_coverage
)

def diagnose_prompt_performance(
    prompt: str, 
    errors: List[Dict[str, Any]], 
    total_count: Optional[int] = None,
    llm_client: Optional[AsyncOpenAI] = None,
    model_config: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    综合诊断提示词性能
    
    Args:
        prompt: 当前提示词
        errors: 错误样例列表
        total_count: 总样例数（用于计算准确率，可选）
        project_id: 项目ID（可选，用于查询历史错误）
        
    Returns:
    """
    error_count = len(errors)
    logger.info(f"[诊断分析] 开始诊断，错误样例数: {error_count}, 项目ID: {project_id}")

    total = total_count or max(error_count * 2, 100)  # 估算总数
    accuracy = 1 - (error_count / total) if total > 0 else 0
    
    # 基础分析
    confusion_pairs = extract_confusion_pairs(errors)
    
    # 困难案例探测
    detector = HardCaseDetector(llm_client, model_config)
    hard_cases = detector.detect_hard_cases(errors, top_k=50, project_id=project_id)
    if not hard_cases: 
         hard_cases = identify_hard_cases(errors)

    category_dist = get_error_category_distribution(errors)
    
    # 深度分析
    deep_analysis = {
        "confusion_matrix": build_confusion_matrix_data(errors),
        "pattern_clusters": cluster_error_patterns(errors),
        "decision_boundaries": analyze_decision_boundaries(errors),
        "text_features": extract_text_features(errors)
    }
    
    # 自动生成建议
    suggestions = generate_optimization_suggestions(
        accuracy, 
        confusion_pairs, 
        deep_analysis,
        prompt
    )
    

    
    logger.info(f"[诊断分析] 诊断完成，准确率: {accuracy:.2f}, 生成建议数: {len(suggestions)}")
    return {
        "overall_metrics": {
            "accuracy": accuracy,
            "error_count": error_count,
            "total_count": total
        },
        "error_patterns": {
            "confusion_pairs": confusion_pairs,
            "hard_cases": hard_cases,
            "category_distribution": category_dist,
            "clusters": deep_analysis["pattern_clusters"],
            "format_errors": detect_format_errors(errors),
            "terminology_errors": detect_terminology_errors(errors),
            "ambiguous_queries": detect_ambiguous_queries(errors),
            "boundary_violations": detect_boundary_violations(errors)
        },
        "prompt_analysis": {
            "instruction_clarity": analyze_instruction_clarity(prompt),
            "has_examples": detect_examples_in_prompt(prompt),
            "has_constraints": detect_constraints_in_prompt(prompt),
            "has_cot": detect_cot_in_prompt(prompt),
            "constraint_clarity": analyze_constraint_clarity(prompt),
            "format_issues": detect_format_issues(prompt),
            "output_consistency": analyze_output_consistency(prompt),
            "has_role_definition": detect_role_definition(prompt),
            "scene_coverage": analyze_scene_coverage(prompt)
        },
        "deep_analysis": deep_analysis,
        "suggestions": suggestions
    }


def generate_optimization_suggestions(
    accuracy: float,
    confusion_pairs: List[Tuple],
    deep_analysis: Dict,
    prompt: str
) -> List[str]:
    """自动生成优化建议"""
    suggestions = []
    
    # 基于准确率的建议
    if accuracy < 0.6:
        suggestions.append("instruction_refinement")  # 准确率低，优先优化指令
        suggestions.append("meta_optimization")      # 尝试元优化
        
    # 基于混淆的建议
    matrix_info = deep_analysis.get("confusion_matrix", {})
    if matrix_info.get("top_confusion_rate", 0) > 0.2:
        suggestions.append("boundary_clarification")  # 混淆严重，添加边界澄清
        
    if confusion_pairs:
        suggestions.append("boundary_clarification")
        
    # 基于错误模式的建议
    clusters = deep_analysis.get("pattern_clusters", [])
    if clusters and clusters[0]['count'] > 5:
        # 存在明显的错误聚集，可能需要特定案例注入
        suggestions.append("difficult_example_injection")
        
    # 基于特征的建议
    features = deep_analysis.get("text_features", {})
    if features.get("avg_query_length", 0) < 10:
        suggestions.append("add_context_clarification") # 查询太短，可能需要补充上下文说明
        
    # 去重
    return list(set(suggestions))
