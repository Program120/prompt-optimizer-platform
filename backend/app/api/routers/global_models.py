
"""
公共模型配置API路由
提供公共模型配置的增删改查接口
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.db import storage
from loguru import logger

router = APIRouter(prefix="/global-models", tags=["global-models"])


class GlobalModelCreate(BaseModel):
    """
    创建公共模型配置的请求体
    """
    name: str
    base_url: str
    api_key: str
    model_name: str = "gpt-3.5-turbo"
    protocol: str = "openai"
    max_tokens: int = 2000
    temperature: float = 0.0
    timeout: int = 60
    extra_body: Optional[Dict[str, Any]] = None
    default_headers: Optional[Dict[str, Any]] = None


class GlobalModelUpdate(BaseModel):
    """
    更新公共模型配置的请求体
    """
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None
    protocol: Optional[str] = None
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    timeout: Optional[int] = None
    extra_body: Optional[Dict[str, Any]] = None
    default_headers: Optional[Dict[str, Any]] = None


@router.get("")
async def get_global_models() -> List[Dict[str, Any]]:
    """
    获取所有公共模型配置
    :return: 公共模型配置列表
    """
    logger.info("获取所有公共模型配置")
    models = storage.get_global_models()
    return models


@router.get("/{model_id}")
async def get_global_model(model_id: str) -> Dict[str, Any]:
    """
    获取单个公共模型配置
    :param model_id: 模型配置ID
    :return: 模型配置详情
    """
    logger.info(f"获取公共模型配置: {model_id}")
    model = storage.get_global_model(model_id)
    if not model:
        logger.warning(f"获取失败: 模型配置 {model_id} 不存在")
        raise HTTPException(status_code=404, detail="模型配置不存在")
    return model


@router.post("")
async def create_global_model(model_data: GlobalModelCreate) -> Dict[str, Any]:
    """
    创建新的公共模型配置
    :param model_data: 模型配置数据
    :return: 创建的模型配置
    """
    logger.info(f"创建公共模型配置: {model_data.name}")
    new_model = storage.create_global_model(model_data.model_dump())
    logger.info(f"公共模型配置创建成功: {new_model.get('id')}")
    return new_model


@router.put("/{model_id}")
async def update_global_model(model_id: str, updates: GlobalModelUpdate) -> Dict[str, Any]:
    """
    更新公共模型配置
    :param model_id: 模型配置ID
    :param updates: 要更新的字段
    :return: 更新后的模型配置
    """
    logger.info(f"更新公共模型配置: {model_id}")
    # 只传递非None的字段
    update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}
    updated_model = storage.update_global_model(model_id, update_dict)
    if not updated_model:
        logger.warning(f"更新失败: 模型配置 {model_id} 不存在")
        raise HTTPException(status_code=404, detail="模型配置不存在")
    logger.info(f"公共模型配置更新成功: {model_id}")
    return updated_model


@router.delete("/{model_id}")
async def delete_global_model(model_id: str) -> Dict[str, str]:
    """
    删除公共模型配置
    :param model_id: 模型配置ID
    :return: 删除结果
    """
    logger.info(f"删除公共模型配置: {model_id}")
    success = storage.delete_global_model(model_id)
    if not success:
        logger.warning(f"删除失败: 模型配置 {model_id} 不存在")
        raise HTTPException(status_code=404, detail="模型配置不存在")
    logger.info(f"公共模型配置删除成功: {model_id}")
    return {"status": "success", "message": "模型配置已删除"}
