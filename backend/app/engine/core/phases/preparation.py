"""
优化准备阶段模块

负责优化前的准备工作，如加载原因库、格式化数据等。
"""
from typing import List, Dict, Any, Optional
from loguru import logger
from app.services import reason_service

def enrich_with_reasons(
    project_id: str, 
    errors: List[Dict[str, Any]], 
    dataset: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    从知识库中获取已标注的原因，并合并到 errors 和 dataset 中
    
    :param project_id: 项目 ID
    :param errors: 错误样本列表 (将被原地修改)
    :param dataset: 完整数据集 (将被原地修改)
    """
    if not project_id:
        return

    try:
        reason_map = reason_service.get_reason_map(project_id)
        if not reason_map:
            return

        # 更新 errors
        count_err = 0
        for err in errors:
            q = err.get("query")
            if q and q in reason_map:
                err["reason"] = reason_map[q]
                count_err += 1
        
        # 更新 dataset (如果存在且不等于 errors)
        count_data = 0
        if dataset and dataset is not errors:
            for d in dataset:
                q = d.get("query")
                if q and q in reason_map:
                    d["reason"] = reason_map[q]
                    count_data += 1
                    
        logger.info(f"已从原因库合并标注: Errors={count_err}, Dataset={count_data}")
        
        
    except Exception as e:
        logger.warning(f"合并原因库失败: {e}")

def load_extraction_rule(project_id: Optional[str], ctx: Any) -> None:
    """
    加载项目配置中的提取规则 (支持标准字段或 Python 代码)
    
    :param project_id: 项目 ID
    :param ctx: 优化上下文对象 (将直接修改其 extraction_rule 属性)
    """
    if not project_id:
        return
        
    try:
        # 延迟导入以避免循环依赖
        from app.db.storage import get_project
        import json
        
        project = get_project(project_id)
        if project and project.get("config"):
            config = project.get("config")
            if isinstance(config, str):
                try:
                    config = json.loads(config)
                except:
                    config = {}
                    
            # 查找提取规则: extract_field (兼容 val_config)
            extract_rule = config.get("extract_field")
            if not extract_rule:
                val_config = config.get("validation_config", {})
                extract_rule = val_config.get("extract_field")
                
            if extract_rule:
                ctx.extraction_rule = str(extract_rule)
                logger.info(f"已加载意图提取规则 (长度: {len(ctx.extraction_rule)})")
    except Exception as e:
        logger.warning(f"加载项目提取规则失败: {e}")
