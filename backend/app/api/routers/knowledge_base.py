"""
知识库 API 路由模块

提供知识库记录的 CRUD 操作接口
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys
import os

# 添加父目录到路径以便导入 (已废弃，使用绝对导入)
# sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.engine.knowledge_base import OptimizationKnowledgeBase
from loguru import logger

router = APIRouter(prefix="/projects", tags=["knowledge_base"])


class KnowledgeBaseUpdateRequest(BaseModel):
    """
    知识库记录更新请求体
    """
    # 优化总结
    analysis_summary: Optional[str] = None
    # 应用的策略列表
    applied_strategies: Optional[List[str]] = None
    # 优化后准确率
    accuracy_after: Optional[float] = None
    # 手动标记
    note: Optional[str] = None


@router.get("/{project_id}/knowledge-base")
async def get_knowledge_base(
    project_id: str,
    limit: int = 20
) -> Dict[str, Any]:
    """
    获取项目的知识库历史记录
    
    :param project_id: 项目ID
    :param limit: 返回记录数量限制
    :return: 知识库记录列表和统计信息
    """
    logger.info(f"获取项目 {project_id} 的知识库, 限制 {limit} 条")
    
    try:
        kb = OptimizationKnowledgeBase(project_id)
        history = kb.get_history(limit=limit)
        trends = kb.get_optimization_trends()
        
        return {
            "records": history,
            "total_versions": trends.get("total_versions", 0),
            "accuracy_trend": trends.get("accuracy_trend", [])
        }
    except Exception as e:
        logger.error(f"获取知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取知识库失败: {str(e)}")


@router.get("/{project_id}/knowledge-base/{version}")
async def get_knowledge_base_record(
    project_id: str,
    version: int
) -> Dict[str, Any]:
    """
    获取特定版本的知识库记录详情
    
    :param project_id: 项目ID
    :param version: 版本号
    :return: 知识库记录详情
    """
    logger.info(f"获取项目 {project_id} 知识库版本 {version}")
    
    try:
        kb = OptimizationKnowledgeBase(project_id)
        history = kb._load_history()
        
        # 查找指定版本
        for record in history:
            if record.get("version") == version:
                return record
                
        raise HTTPException(status_code=404, detail=f"未找到版本 {version}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取知识库记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取记录失败: {str(e)}")


@router.put("/{project_id}/knowledge-base/{version}")
async def update_knowledge_base_record(
    project_id: str,
    version: int,
    update_data: KnowledgeBaseUpdateRequest
) -> Dict[str, Any]:
    """
    更新特定版本的知识库记录
    
    :param project_id: 项目ID
    :param version: 版本号
    :param update_data: 更新数据
    :return: 更新后的记录
    """
    logger.info(f"更新项目 {project_id} 知识库版本 {version}")
    
    try:
        kb = OptimizationKnowledgeBase(project_id)
        history = kb._load_history()
        
        # 查找并更新指定版本
        updated_record = None
        for record in history:
            if record.get("version") == version:
                # 更新非空字段
                if update_data.analysis_summary is not None:
                    record["analysis_summary"] = update_data.analysis_summary
                if update_data.applied_strategies is not None:
                    record["applied_strategies"] = update_data.applied_strategies
                if update_data.accuracy_after is not None:
                    record["accuracy_after"] = update_data.accuracy_after
                if update_data.note is not None:
                    record["note"] = update_data.note
                    
                # 添加更新时间戳
                from datetime import datetime
                record["updated_at"] = datetime.now().isoformat()
                updated_record = record
                break
                
        if updated_record is None:
            raise HTTPException(status_code=404, detail=f"未找到版本 {version}")
            
        # 保存更新
        kb._save_history(history)
        logger.info(f"知识库版本 {version} 已更新")
        
        return updated_record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新知识库记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/{project_id}/knowledge-base/{version}")
async def delete_knowledge_base_record(
    project_id: str,
    version: int
) -> Dict[str, Any]:
    """
    删除特定版本的知识库记录
    
    :param project_id: 项目ID
    :param version: 版本号
    :return: 删除结果
    """
    logger.info(f"删除项目 {project_id} 知识库版本 {version}")
    
    try:
        kb = OptimizationKnowledgeBase(project_id)
        history = kb._load_history()
        
        # 查找并删除指定版本
        original_length = len(history)
        history = [r for r in history if r.get("version") != version]
        
        if len(history) == original_length:
            raise HTTPException(status_code=404, detail=f"未找到版本 {version}")
            
        # 保存更新
        kb._save_history(history)
        logger.info(f"知识库版本 {version} 已删除")
        
        return {"success": True, "message": f"版本 {version} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除知识库记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
