"""
多轮意图干预服务层

处理 MultiRoundIntervention 相关的数据库操作
"""
from typing import List, Optional, Dict, Any
from sqlmodel import select, col, func
from sqlalchemy import or_
from loguru import logger
import json
from datetime import datetime

from app.models import MultiRoundIntervention, TaskResult
from app.db.database import get_db_session


def get_interventions_paginated(
    project_id: str,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    filter_type: Optional[str] = None,
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    分页获取多轮干预数据

    :param project_id: 项目 ID
    :param page: 页码（1-based）
    :param page_size: 每页数量
    :param search: 搜索关键字（搜索 original_query）
    :param filter_type: 筛选类型 ('all', 'modified')
    :param file_id: 文件版本 ID
    :return: 分页结果字典
    """
    try:
        with get_db_session() as session:
            offset = (page - 1) * page_size

            # 构建基础查询
            query = select(MultiRoundIntervention).where(
                MultiRoundIntervention.project_id == project_id
            )

            if file_id:
                query = query.where(MultiRoundIntervention.file_id == file_id)

            if filter_type == "modified":
                query = query.where(MultiRoundIntervention.is_modified == True)

            if search:
                search_term = f"%{search}%"
                # 搜索 original_query 或 rounds_data 中的内容
                query = query.where(
                    or_(
                        col(MultiRoundIntervention.original_query).like(search_term),
                        col(MultiRoundIntervention.rounds_data).like(search_term)
                    )
                )

            # 计算总数
            count_query = select(func.count()).select_from(query.subquery())
            total = session.exec(count_query).one()

            # 分页查询
            stmt = query.offset(offset).limit(page_size).order_by(
                MultiRoundIntervention.row_index.asc()
            )
            results = list(session.exec(stmt).all())

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [r.to_dict() for r in results]
            }
    except Exception as e:
        logger.error(f"获取多轮干预数据失败: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "items": []}


def get_by_row_index(
    project_id: str,
    row_index: int,
    file_id: Optional[str] = None
) -> Optional[MultiRoundIntervention]:
    """
    根据行索引获取干预记录

    :param project_id: 项目 ID
    :param row_index: 行索引
    :param file_id: 文件版本 ID
    :return: 干预记录或 None
    """
    try:
        with get_db_session() as session:
            query = select(MultiRoundIntervention).where(
                MultiRoundIntervention.project_id == project_id,
                MultiRoundIntervention.row_index == row_index
            )
            if file_id:
                query = query.where(MultiRoundIntervention.file_id == file_id)

            return session.exec(query).first()
    except Exception as e:
        logger.error(f"根据行索引获取干预记录失败: {e}")
        return None


def get_by_id(intervention_id: int) -> Optional[MultiRoundIntervention]:
    """
    根据 ID 获取干预记录

    :param intervention_id: 干预记录 ID
    :return: 干预记录或 None
    """
    try:
        with get_db_session() as session:
            return session.get(MultiRoundIntervention, intervention_id)
    except Exception as e:
        logger.error(f"根据 ID 获取干预记录失败: {e}")
        return None


def upsert_intervention(
    project_id: str,
    row_index: int,
    rounds_data: Dict[str, Dict[str, Any]],
    original_query: str = "",
    file_id: str = "",
    intervention_id: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    添加或更新多轮干预数据

    :param project_id: 项目 ID
    :param row_index: 行索引
    :param rounds_data: 各轮次干预数据
    :param original_query: 原始第一轮 Query
    :param file_id: 文件版本 ID
    :param intervention_id: 干预记录 ID（可选，用于精确更新）
    :return: 更新后的干预记录字典
    """
    try:
        with get_db_session() as session:
            existing: Optional[MultiRoundIntervention] = None

            # 优先按 ID 查找
            if intervention_id:
                existing = session.get(MultiRoundIntervention, intervention_id)
                if existing and existing.project_id != project_id:
                    existing = None

            # 按 row_index + file_id 查找
            if not existing:
                query = select(MultiRoundIntervention).where(
                    MultiRoundIntervention.project_id == project_id,
                    MultiRoundIntervention.row_index == row_index
                )
                if file_id:
                    query = query.where(MultiRoundIntervention.file_id == file_id)
                existing = session.exec(query).first()

            if existing:
                # 更新现有记录
                current_rounds = {}
                try:
                    current_rounds = json.loads(existing.rounds_data) if existing.rounds_data else {}
                except json.JSONDecodeError:
                    current_rounds = {}

                # 合并轮次数据
                for round_num, data in rounds_data.items():
                    if round_num not in current_rounds:
                        # 新轮次，设置 original_target
                        current_rounds[round_num] = {
                            "original_target": data.get("original_target") or data.get("target", "")
                        }

                    current_rounds[round_num].update({
                        "target": data.get("target", ""),
                        "query_rewrite": data.get("query_rewrite", ""),
                        "reason": data.get("reason", "")
                    })

                existing.rounds_data = json.dumps(current_rounds, ensure_ascii=False)
                existing.original_query = original_query or existing.original_query
                existing.updated_at = datetime.now().isoformat()

                # 检查是否有修改
                existing.is_modified = any(
                    rd.get("target") != rd.get("original_target") or
                    rd.get("query_rewrite") or
                    rd.get("reason")
                    for rd in current_rounds.values()
                )

                session.add(existing)
                session.commit()
                session.refresh(existing)
                logger.info(f"更新多轮干预记录: project={project_id}, row={row_index}")
                return existing.to_dict()
            else:
                # 创建新记录
                processed_rounds = {}
                for round_num, data in rounds_data.items():
                    processed_rounds[round_num] = {
                        "target": data.get("target", ""),
                        "original_target": data.get("original_target") or data.get("target", ""),
                        "query_rewrite": data.get("query_rewrite", ""),
                        "reason": data.get("reason", "")
                    }

                new_record = MultiRoundIntervention(
                    project_id=project_id,
                    file_id=file_id,
                    row_index=row_index,
                    original_query=original_query,
                    rounds_data=json.dumps(processed_rounds, ensure_ascii=False),
                    is_modified=False,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session.add(new_record)
                session.commit()
                session.refresh(new_record)
                logger.info(f"创建多轮干预记录: project={project_id}, row={row_index}")
                return new_record.to_dict()

    except Exception as e:
        logger.error(f"添加/更新多轮干预数据失败: {e}")
        return None


def delete_intervention(intervention_id: int, project_id: str) -> bool:
    """
    删除干预记录

    :param intervention_id: 干预记录 ID
    :param project_id: 项目 ID（用于验证）
    :return: 是否删除成功
    """
    try:
        with get_db_session() as session:
            record = session.get(MultiRoundIntervention, intervention_id)
            if record and record.project_id == project_id:
                session.delete(record)
                session.commit()
                logger.info(f"删除多轮干预记录: id={intervention_id}")
                return True
            return False
    except Exception as e:
        logger.error(f"删除多轮干预记录失败: {e}")
        return False


def clear_interventions(project_id: str, file_id: Optional[str] = None) -> int:
    """
    清空项目下所有多轮干预数据

    :param project_id: 项目 ID
    :param file_id: 文件版本 ID（可选）
    :return: 删除的记录数
    """
    try:
        with get_db_session() as session:
            query = select(MultiRoundIntervention).where(
                MultiRoundIntervention.project_id == project_id
            )
            if file_id:
                query = query.where(MultiRoundIntervention.file_id == file_id)

            records = list(session.exec(query).all())
            count = len(records)

            for record in records:
                session.delete(record)

            session.commit()
            logger.info(f"清空多轮干预数据: project={project_id}, count={count}")
            return count
    except Exception as e:
        logger.error(f"清空多轮干预数据失败: {e}")
        return 0


def sync_from_task_results(
    project_id: str,
    task_id: str,
    file_id: str
) -> Dict[str, int]:
    """
    从任务结果同步干预数据

    读取 TaskResult 中的多轮验证结果，为每个 row_index 创建干预记录

    :param project_id: 项目 ID
    :param task_id: 任务 ID
    :param file_id: 文件版本 ID
    :return: 同步结果统计 {"synced": N, "skipped": M}
    """
    try:
        with get_db_session() as session:
            # 获取任务的所有结果
            stmt = select(TaskResult).where(TaskResult.task_id == task_id)
            results = list(session.exec(stmt).all())

            if not results:
                logger.warning(f"任务 {task_id} 没有结果数据")
                return {"synced": 0, "skipped": 0}

            # 按 row_index 分组
            row_data: Dict[int, Dict[int, TaskResult]] = {}
            for r in results:
                if r.row_index not in row_data:
                    row_data[r.row_index] = {}
                row_data[r.row_index][r.round_number] = r

            synced = 0
            skipped = 0

            for row_idx, rounds in row_data.items():
                # 检查是否已存在
                existing_query = select(MultiRoundIntervention).where(
                    MultiRoundIntervention.project_id == project_id,
                    MultiRoundIntervention.row_index == row_idx,
                    MultiRoundIntervention.file_id == file_id
                )
                existing = session.exec(existing_query).first()

                if existing:
                    skipped += 1
                    continue

                # 构建轮次数据
                rounds_data = {}
                original_query = ""

                for round_num, result in sorted(rounds.items()):
                    if round_num == 1:
                        original_query = result.query

                    rounds_data[str(round_num)] = {
                        "target": result.target,
                        "original_target": result.target,
                        "query_rewrite": "",
                        "reason": "",
                        "original_query": result.query  # 保存每轮的原始 Query
                    }

                # 创建记录
                new_record = MultiRoundIntervention(
                    project_id=project_id,
                    file_id=file_id,
                    row_index=row_idx,
                    original_query=original_query,
                    rounds_data=json.dumps(rounds_data, ensure_ascii=False),
                    is_modified=False,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session.add(new_record)
                synced += 1

            session.commit()
            logger.info(f"同步多轮干预数据: project={project_id}, synced={synced}, skipped={skipped}")
            return {"synced": synced, "skipped": skipped}

    except Exception as e:
        logger.error(f"从任务结果同步干预数据失败: {e}")
        return {"synced": 0, "skipped": 0, "error": str(e)}


def sync_from_data_file(
    project_id: str,
    file_id: str,
    rounds_config: list,
    validation_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    从数据文件同步干预数据

    读取上传的 Excel/CSV 文件，根据轮次配置初始化干预记录

    :param project_id: 项目 ID
    :param file_id: 文件 ID
    :param rounds_config: 轮次配置列表 [{"round": 1, "query_col": "...", "target_col": "..."}, ...]
    :param validation_limit: 数据行数限制（可选）
    :return: 同步结果统计 {"synced": N, "skipped": M, "total_rows": T}
    """
    import pandas as pd
    from app.db import storage
    import os
    import glob

    try:
        # 在 DATA_DIR 中查找匹配 file_id 的文件
        data_dir = storage.DATA_DIR
        matching_files = glob.glob(os.path.join(data_dir, f"{file_id}.*"))

        if not matching_files:
            logger.error(f"找不到文件: file_id={file_id}")
            return {"synced": 0, "skipped": 0, "error": f"文件不存在: {file_id}"}

        file_path = matching_files[0]
        logger.info(f"找到文件: {file_path}")

        # 读取文件
        if file_path.endswith(".csv"):
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk')
        else:
            df = pd.read_excel(file_path)

        total_rows = len(df)
        if validation_limit and validation_limit > 0:
            df = df.head(validation_limit)
            total_rows = len(df)

        synced = 0
        skipped = 0

        with get_db_session() as session:
            for row_idx in range(len(df)):
                # 检查是否已存在
                existing_query = select(MultiRoundIntervention).where(
                    MultiRoundIntervention.project_id == project_id,
                    MultiRoundIntervention.row_index == row_idx,
                    MultiRoundIntervention.file_id == file_id
                )
                existing = session.exec(existing_query).first()

                if existing:
                    skipped += 1
                    continue

                # 构建轮次数据
                rounds_data = {}
                original_query = ""

                for cfg in rounds_config:
                    round_num = cfg.get("round", 1)
                    query_col = cfg.get("query_col", "")
                    target_col = cfg.get("target_col", "")
                    rewrite_col = cfg.get("rewrite_col", "")
                    reason_col = cfg.get("reason_col", "")

                    # 获取 Query
                    query_val = ""
                    if query_col and query_col in df.columns:
                        raw_val = df.iloc[row_idx][query_col]
                        if pd.notna(raw_val):
                            query_val = str(raw_val).strip()

                    # 获取 Target
                    target_val = ""
                    if target_col and target_col in df.columns:
                        raw_val = df.iloc[row_idx][target_col]
                        if pd.notna(raw_val):
                            target_val = str(raw_val).strip()

                    # 获取 Rewrite（可选）
                    rewrite_val = ""
                    if rewrite_col and rewrite_col in df.columns:
                        raw_val = df.iloc[row_idx][rewrite_col]
                        if pd.notna(raw_val):
                            rewrite_val = str(raw_val).strip()

                    # 获取 Reason（可选）
                    reason_val = ""
                    if reason_col and reason_col in df.columns:
                        raw_val = df.iloc[row_idx][reason_col]
                        if pd.notna(raw_val):
                            reason_val = str(raw_val).strip()

                    # 第一轮的 Query 作为 original_query
                    if round_num == 1:
                        original_query = query_val

                    rounds_data[str(round_num)] = {
                        "target": target_val,
                        "original_target": target_val,
                        "query_rewrite": rewrite_val,
                        "reason": reason_val,
                        "original_query": query_val
                    }

                # 创建记录
                new_record = MultiRoundIntervention(
                    project_id=project_id,
                    file_id=file_id,
                    row_index=row_idx,
                    original_query=original_query,
                    rounds_data=json.dumps(rounds_data, ensure_ascii=False),
                    is_modified=False,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat()
                )
                session.add(new_record)
                synced += 1

            session.commit()

        logger.info(f"从数据文件同步干预数据: project={project_id}, synced={synced}, skipped={skipped}")
        return {"synced": synced, "skipped": skipped, "total_rows": total_rows}

    except Exception as e:
        logger.error(f"从数据文件同步干预数据失败: {e}")
        return {"synced": 0, "skipped": 0, "error": str(e)}


def get_intervention_count(project_id: str, file_id: Optional[str] = None) -> int:
    """
    获取干预记录总数

    :param project_id: 项目 ID
    :param file_id: 文件版本 ID（可选）
    :return: 记录总数
    """
    try:
        with get_db_session() as session:
            query = select(func.count(MultiRoundIntervention.id)).where(
                MultiRoundIntervention.project_id == project_id
            )
            if file_id:
                query = query.where(MultiRoundIntervention.file_id == file_id)

            return session.exec(query).one()
    except Exception as e:
        logger.error(f"获取干预记录总数失败: {e}")
        return 0


def reset_intervention(intervention_id: int, project_id: str) -> Optional[Dict[str, Any]]:
    """
    重置干预记录（恢复所有轮次的原始 target，清空 query_rewrite 和 reason）

    :param intervention_id: 干预记录 ID
    :param project_id: 项目 ID
    :return: 重置后的记录字典
    """
    try:
        with get_db_session() as session:
            record = session.get(MultiRoundIntervention, intervention_id)
            if not record or record.project_id != project_id:
                return None

            # 解析轮次数据
            rounds = {}
            try:
                rounds = json.loads(record.rounds_data) if record.rounds_data else {}
            except json.JSONDecodeError:
                rounds = {}

            # 重置每轮数据
            for round_num, data in rounds.items():
                data["target"] = data.get("original_target", "")
                data["query_rewrite"] = ""
                data["reason"] = ""

            record.rounds_data = json.dumps(rounds, ensure_ascii=False)
            record.is_modified = False
            record.updated_at = datetime.now().isoformat()

            session.add(record)
            session.commit()
            session.refresh(record)

            logger.info(f"重置多轮干预记录: id={intervention_id}")
            return record.to_dict()
    except Exception as e:
        logger.error(f"重置多轮干预记录失败: {e}")
        return None
