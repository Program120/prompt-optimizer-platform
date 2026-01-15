"""
错误历史管理模块

提供错误样本追踪、顽固错误识别、澄清样本过滤等功能
"""
import hashlib
from loguru import logger
import hashlib
from typing import List, Dict, Any, Tuple


def update_error_optimization_history(
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
            if updated_history[hash_key]["optimization_count"] >= 5:
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


def identify_persistent_errors(
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
        logger.info(
            f"[顽固错误] 发现 {len(persistent_samples)} 个顽固错误样本 "
            f"（连续优化>=3次仍错误）"
        )
    
    return persistent_samples


def filter_clarification_samples(
    errors: List[Dict[str, Any]],
    clarification_analysis: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
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
    
    logger.info(
        f"[澄清过滤] 主要优化样本: {len(main_errors)}, "
        f"低优先级澄清类样本: {len(low_priority_errors)}"
    )
    
    return main_errors, low_priority_errors


def inject_persistent_errors_to_hard_cases(
    diagnosis: Dict[str, Any],
    persistent_samples: List[Dict[str, Any]]
) -> None:
    """
    将顽固错误样本注入到 diagnosis 的 hard_cases 中
    
    :param diagnosis: 诊断结果字典（将被修改）
    :param persistent_samples: 顽固错误样本列表
    """
    if not persistent_samples:
        return
    
    # 确保 error_patterns 存在
    if "error_patterns" not in diagnosis:
        diagnosis["error_patterns"] = {}
    
    existing_hard_cases: List[Dict[str, Any]] = diagnosis["error_patterns"].get(
        "hard_cases", []
    )
    
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
    
    logger.info(
        f"[顽固错误] 已注入 {len(persistent_samples)} 个顽固错误样本到 hard_cases"
    )


def prepare_persistent_errors_for_knowledge_base(
    errors: List[Dict[str, Any]],
    error_history: Dict[str, Any],
    optimized_intents: List[str]
) -> List[Dict[str, Any]]:
    """
    准备用于知识库记录的顽固错误列表
    
    :param errors: 当前错误列表
    :param error_history: 错误历史
    :param optimized_intents: 被优化的意图列表
    :return: 排序后的顽固错误列表
    """
    try:
        # 更新历史
        temp_updated_history = update_error_optimization_history(
            errors, 
            error_history, 
            optimized_intents
        )
        
        # 转换为列表
        persistent_errors_list: List[Dict[str, Any]] = []
        for hash_key, val in temp_updated_history.items():
            val_copy = val.copy()
            val_copy['hash_key'] = hash_key
            persistent_errors_list.append(val_copy)
        
        # 按 optimization_count 倒序排序
        persistent_errors_list.sort(
            key=lambda x: x.get("optimization_count", 0), 
            reverse=True
        )
        
        return persistent_errors_list
        
    except Exception as e:
        logger.warning(f"准备错误历史数据失败: {e}")
        return []
