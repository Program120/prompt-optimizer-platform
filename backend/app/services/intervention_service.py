"""
原因库服务层

意图干预服务层

处理 IntentIntervention 相关的数据库操作，包括查询、新增、修改和删除。
提供给 API 层和 Optimization Engine 使用。
"""
from typing import List, Optional, Dict, Any, Union
from sqlmodel import select, Session, col, delete, func
from loguru import logger
import pandas as pd
import json
import re

from app.models import IntentIntervention
from app.db.database import get_db_session
from datetime import datetime

def get_interventions_by_project(project_id: str, file_id: Optional[str] = None) -> List[IntentIntervention]:
    """
    获取项目下所有已标注的意图干预数据
    
    :param project_id: 项目唯一标识
    :param file_id: 可选，文件版本 ID，用于筛选特定版本
    :return: IntentIntervention 对象列表
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            
            # 如果指定了 file_id，仅返回该版本的数据
            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)
            
            results: List[IntentIntervention] = list(session.exec(statement).all())
            return results
    except Exception as e:
        logger.error(f"Failed to get interventions for project {project_id}: {e}")
        return []

def get_interventions_paginated(
    project_id: str, 
    page: int = 1, 
    page_size: int = 50,
    search: Optional[str] = None,
    filter_type: Optional[str] = None, # 'all', 'modified', 'reason_added'
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    分页获取意图干预数据
    """
    try:
        with get_db_session() as session:
            offset = (page - 1) * page_size
            
            # Base query
            query = select(IntentIntervention).where(IntentIntervention.project_id == project_id)
            
            # File ID Filter (Strict)
            if file_id:
                query = query.where(IntentIntervention.file_id == file_id)
            
            # Filter Type
            if filter_type == "modified":
                query = query.where(IntentIntervention.is_target_modified == True)
            elif filter_type == "reason_added":
                query = query.where(IntentIntervention.reason != "")
            
            # Search
            if search:
                search_term = f"%{search}%"
                query = query.where(
                    col(IntentIntervention.query).like(search_term) | 
                    col(IntentIntervention.target).like(search_term) |
                    col(IntentIntervention.reason).like(search_term)
                )
            
            # Total count
            total_statement = select(func.count()).select_from(query.subquery())
            total = session.exec(total_statement).one()
            
            # Pagination
            statement = query.offset(offset).limit(page_size).order_by(IntentIntervention.id.desc())
            results: List[IntentIntervention] = list(session.exec(statement).all())
            
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": results
            }
    except Exception as e:
        logger.error(f"Failed to get interventions paginated: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "items": []}

def import_dataset_to_interventions(
    project_id: str, 
    df: Any, 
    query_col: str, 
    target_col: str, 
    reason_col: Optional[str] = None,
    file_id: str = ""
) -> int:
    """
    批量导入数据集到意图干预库 (优化版: 批量提交)
    """
    try:
        from datetime import datetime
        
        # 1. 获取现有数据映射 {query: intervention}
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id
            )
            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)
            
            existing_records = session.exec(statement).all()
            existing_map = {r.query: r for r in existing_records}
            
            new_objects = []
            updated_count = 0
            
            # 2. 遍历 DataFrame
            for _, row in df.iterrows():
                q = row.get(query_col)
                if pd.isna(q):
                    continue
                
                query_str = str(q)
                t = row.get(target_col)
                target_val = str(t) if pd.notna(t) else ""
                
                r = None
                if reason_col and reason_col in df.columns:
                    r_val = row.get(reason_col)
                    r = str(r_val) if pd.notna(r_val) else ""
                else:
                    r = ""
                
                # 3. 检查是否存在
                if query_str in existing_map:
                    # Update existing
                    existing_obj = existing_map[query_str]
                    
                    # 仅当内容有变化时才更新 (这里简化逻辑，直接赋值，SQLAlchemy 会处理脏检查)
                    existing_obj.target = target_val
                    existing_obj.reason = r
                    existing_obj.updated_at = datetime.now().isoformat()
                    
                    # Target Modification Check
                    if existing_obj.original_target is not None:
                        existing_obj.is_target_modified = (existing_obj.target != existing_obj.original_target)
                    
                    # Import default logic: if original is None, fill it
                    if existing_obj.original_target is None:
                        existing_obj.original_target = target_val
                        existing_obj.is_target_modified = False
                        
                    session.add(existing_obj)
                    updated_count += 1
                else:
                    # Create new
                    new_obj = IntentIntervention(
                        project_id=project_id,
                        query=query_str,
                        target=target_val,
                        reason=r,
                        original_target=target_val,
                        is_target_modified=False,
                        file_id=file_id
                    )
                    new_objects.append(new_obj)
            
            # 4. 批量提交
            if new_objects:
                session.add_all(new_objects)
            
            total_affected = len(new_objects) + updated_count
            session.commit()
            
            logger.info(f"Batch imported {total_affected} interventions (New: {len(new_objects)}, Updated: {updated_count}) for project {project_id}")
            return total_affected
            
    except Exception as e:
        logger.error(f"Failed to batch import dataset: {e}")
        return 0


def get_intervention_map(project_id: str, file_id: Optional[str] = None) -> Dict[str, str]:
    """
    获取项目下 Query -> Reason 的映射字典 (仅返回已有原因的项)
    
    :param project_id: 项目 ID
    :param file_id: 可选，文件版本 ID，用于筛选特定版本
    :return: 字典 {query: reason}
    """
    interventions = get_interventions_by_project(project_id, file_id=file_id)
    return {r.query: r.reason for r in interventions if r.reason}


def upsert_intervention(project_id: str, query: str, reason: str, target: str = "", is_import: bool = False, file_id: str = "") -> Optional[IntentIntervention]:
    """
    添加或更新意图干预项
    
    查找逻辑：
    1. 首先按 project_id + query 查找（不限制 file_id）
    2. 如果找到多条记录，优先更新 is_target_modified=True 的记录
    3. 如果找不到，则创建新记录
    
    这确保了用户在运行日志中保存的原因能正确更新到已有的意图干预记录，
    而不会因为 file_id 不匹配而创建重复记录。
    
    :param project_id: 项目 ID
    :param query: 用户查询 (Identify key)
    :param reason: 失败原因 / 意图说明
    :param target: 预期输出
    :param is_import: 是否为导入模式
    :param file_id: 文件版本 ID
    :return: 更新后的 IntentIntervention 对象
    """
    if not query:
        return None
        
    try:
        with get_db_session() as session:
            # [修复] 查找时不限制 file_id，确保能找到已有记录
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            
            all_matches = list(session.exec(statement).all())
            existing: Optional[IntentIntervention] = None
            
            if all_matches:
                # 如果有多条记录，优先使用 is_target_modified=True 的
                for m in all_matches:
                    if m.is_target_modified:
                        existing = m
                        break
                # 如果没有修正过的记录，使用第一条
                if existing is None:
                    existing = all_matches[0]
            
            if existing:
                # 更新已有记录
                existing.reason = reason
                existing.target = target
                
                # 更新 file_id（如果传入了新的 file_id）
                if file_id:
                    existing.file_id = file_id
                
                # Check target modification
                if existing.original_target is not None:
                    existing.is_target_modified = (existing.target != existing.original_target)
                
                # 如果是导入模式，且 original_target 为空，则补充 original_target
                if is_import and existing.original_target is None:
                    existing.original_target = target
                    existing.is_target_modified = False

                existing.updated_at = datetime.now().isoformat()
                session.add(existing)
                session.commit()
                session.refresh(existing)
                logger.info(f"Updated intervention for query: {query[:20]}... in project {project_id}")
                return existing
            else:
                # 创建新记录
                new_intervention = IntentIntervention(
                    project_id=project_id,
                    query=query,
                    reason=reason,
                    target=target,
                    original_target=target,  # 新建时，原始值即为当前值
                    is_target_modified=False,
                    file_id=file_id
                )
                session.add(new_intervention)
                session.commit()
                session.refresh(new_intervention)
                logger.info(f"Created new intervention for query: {query[:20]}... in project {project_id}")
                return new_intervention
    except Exception as e:
        logger.error(f"Failed to upsert intervention for project {project_id}, query {query[:20]}...: {e}")
        return None


def reset_intervention(project_id: str, query: str) -> bool:
    """
    重置单条干预记录：恢复 Target 为 Original Target，清空 Reason
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            existing = session.exec(statement).first()
            if existing:
                # 恢复原始 Target (如果有)
                if existing.original_target is not None:
                    existing.target = existing.original_target
                
                # 清空 Reason
                existing.reason = ""
                existing.is_target_modified = False
                
                session.add(existing)
                session.commit()
                logger.info(f"Reset intervention for query: {query[:20]}... in project {project_id}")
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to reset intervention: {e}")
        return False


def delete_intervention(project_id: str, query: str) -> bool:
    """
    删除单条干预记录
    """
    try:
        with get_db_session() as session:
            statement = select(IntentIntervention).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.query == query
            )
            existing = session.exec(statement).first()
            if existing:
                session.delete(existing)
                session.commit()
                logger.info(f"Deleted intervention for query: {query[:20]}... in project {project_id}")
                return True
            logger.warning(f"Intervention not found for deletion: project {project_id}, query {query[:20]}...")
            return False
    except Exception as e:
        logger.error(f"Failed to delete intervention for project {project_id}, query {query[:20]}...: {e}")
        return False


def get_unique_targets(project_id: str, file_id: Optional[str] = None) -> List[str]:
    """
    获取项目下所有唯一的 Target
    """
    try:
        with get_db_session() as session:
            query = select(IntentIntervention.target).where(
                IntentIntervention.project_id == project_id,
                IntentIntervention.target != ""
            )
            
            if file_id:
                query = query.where(IntentIntervention.file_id == file_id)
                
            statement = query.distinct()
            results = session.exec(statement).all()
            return [str(r) for r in results if r]
    except Exception as e:
        logger.error(f"Failed to get unique targets: {e}")
        return []


def clear_interventions(project_id: str, file_id: Optional[str] = None) -> int:
    """
    清空项目下所有意图干预数据

    :param project_id: 项目 ID
    :param file_id: 可选，文件版本 ID
    :return: 删除的记录数
    """
    try:
        with get_db_session() as session:
            statement = delete(IntentIntervention).where(IntentIntervention.project_id == project_id)

            if file_id:
                statement = statement.where(IntentIntervention.file_id == file_id)

            result = session.exec(statement)
            deleted_count = result.rowcount
            session.commit()

            logger.info(f"Cleared {deleted_count} interventions for project {project_id}, file_id={file_id}")
            return deleted_count

    except Exception as e:
        logger.error(f"Failed to clear interventions: {e}")
        return 0


async def generate_similar_queries(
    original_query: str,
    target: str,
    count: int,
    model_config: Dict[str, Any]
) -> List[str]:
    """
    调用 LLM 生成相似 Query（举一反三）

    :param original_query: 原始查询
    :param target: 预期的意图分类
    :param count: 要生成的数量
    :param model_config: 模型配置
    :return: 生成的相似 Query 列表
    """
    from openai import AsyncOpenAI

    prompt = f"""你是一个用户意图分析专家。请根据以下示例，生成 {count} 个语义相似但表达方式不同的用户查询。

**示例查询**: {original_query}
**意图分类**: {target}

**要求**:
1. 生成的查询必须与示例属于同一意图分类（{target}）
2. 使用不同的表达方式、语气、用词
3. 可以包含口语化、正式、简洁、详细等多种风格
4. 保持语义一致，但措辞多样化
5. 每个查询应该是独立的、自然的用户表达

请直接返回 JSON 数组格式，例如：
["查询1", "查询2", "查询3"]

只返回 JSON 数组，不要其他任何解释或文字。"""

    try:
        # 创建异步 OpenAI 客户端
        client = AsyncOpenAI(
            api_key=model_config.get("api_key"),
            base_url=model_config.get("base_url")
        )

        model_name = model_config.get("model_name", "gpt-3.5-turbo")
        temperature = float(model_config.get("temperature", 0.8))
        max_tokens = int(model_config.get("max_tokens", 2000))
        timeout = int(model_config.get("timeout", 60))

        logger.info(f"[举一反三] 开始生成 {count} 个相似 Query，原始: {original_query[:30]}...")

        response = await client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

        result_text = response.choices[0].message.content.strip()

        # 处理推理模型的 <think> 标签
        result_text = re.sub(r'<think>.*?</think>', '', result_text, flags=re.DOTALL).strip()

        logger.debug(f"[举一反三] LLM 返回: {result_text[:200]}...")

        # 解析 JSON
        # 尝试提取 JSON 数组（处理可能的 markdown 代码块）
        json_match = re.search(r'\[.*?\]', result_text, re.DOTALL)
        if json_match:
            result_text = json_match.group()

        queries = json.loads(result_text)

        if isinstance(queries, list):
            # 过滤空字符串和重复项
            unique_queries = []
            seen = {original_query.strip().lower()}
            for q in queries:
                if isinstance(q, str) and q.strip():
                    q_lower = q.strip().lower()
                    if q_lower not in seen:
                        unique_queries.append(q.strip())
                        seen.add(q_lower)

            logger.success(f"[举一反三] 成功生成 {len(unique_queries)} 个相似 Query")
            return unique_queries[:count]

        logger.warning("[举一反三] LLM 返回格式不正确，返回空列表")
        return []

    except json.JSONDecodeError as e:
        logger.error(f"[举一反三] JSON 解析失败: {e}, 原始内容: {result_text[:100]}...")
        return []
    except Exception as e:
        logger.error(f"[举一反三] 生成失败: {e}")
        raise

