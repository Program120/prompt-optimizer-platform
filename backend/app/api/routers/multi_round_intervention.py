"""
多轮意图干预 API 路由

提供多轮验证场景下的意图干预 CRUD 操作
"""
from fastapi import APIRouter, HTTPException, Query, Form
from fastapi.responses import StreamingResponse
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from loguru import logger
import json
import io
import pandas as pd

from app.services import multi_round_intervention_service as service
from app.db import storage

router = APIRouter()


# ==================== 请求/响应模型 ====================

class RoundInterventionData(BaseModel):
    """单轮干预数据"""
    target: str = ""
    original_target: Optional[str] = None
    query_rewrite: str = ""
    reason: str = ""
    original_query: Optional[str] = None


class MultiRoundInterventionUpsertRequest(BaseModel):
    """多轮干预更新请求"""
    id: Optional[int] = None
    row_index: int
    original_query: str = ""
    rounds_data: Dict[str, RoundInterventionData]
    file_id: str = ""


class SyncRequest(BaseModel):
    """同步请求"""
    file_id: str
    rounds_config: list  # [{"round": 1, "query_col": "...", "target_col": "..."}, ...]
    validation_limit: Optional[int] = None


# ==================== API 端点 ====================

@router.get("/projects/{project_id}/multi-round-interventions")
async def list_multi_round_interventions(
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
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
    :return: 分页结果
    """
    logger.info(f"获取多轮干预列表: project={project_id}, page={page}, search={search}")
    return service.get_interventions_paginated(
        project_id=project_id,
        page=page,
        page_size=page_size,
        search=search,
        filter_type=filter_type,
        file_id=file_id
    )


@router.get("/projects/{project_id}/multi-round-interventions/count")
async def get_intervention_count(
    project_id: str,
    file_id: Optional[str] = None
) -> Dict[str, int]:
    """
    获取干预记录总数

    :param project_id: 项目 ID
    :param file_id: 文件版本 ID
    :return: 记录总数
    """
    count = service.get_intervention_count(project_id, file_id)
    return {"count": count}


@router.get("/projects/{project_id}/multi-round-interventions/by-row/{row_index}")
async def get_intervention_by_row(
    project_id: str,
    row_index: int,
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取指定行的干预数据

    :param project_id: 项目 ID
    :param row_index: 行索引
    :param file_id: 文件版本 ID
    :return: 干预数据
    """
    record = service.get_by_row_index(project_id, row_index, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="干预记录不存在")
    return record.to_dict()


@router.post("/projects/{project_id}/multi-round-interventions")
async def upsert_multi_round_intervention(
    project_id: str,
    request: MultiRoundInterventionUpsertRequest
) -> Dict[str, Any]:
    """
    添加或更新多轮干预数据

    :param project_id: 项目 ID
    :param request: 干预数据
    :return: 更新后的干预记录
    """
    logger.info(f"更新多轮干预: project={project_id}, row={request.row_index}")

    # 转换 rounds_data 为普通字典
    rounds_data = {
        k: v.model_dump() for k, v in request.rounds_data.items()
    }

    result = service.upsert_intervention(
        project_id=project_id,
        row_index=request.row_index,
        rounds_data=rounds_data,
        original_query=request.original_query,
        file_id=request.file_id,
        intervention_id=request.id
    )

    if not result:
        raise HTTPException(status_code=500, detail="保存干预数据失败")

    return result


@router.delete("/projects/{project_id}/multi-round-interventions/clear")
async def clear_interventions(
    project_id: str,
    file_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    清空项目下所有多轮干预数据

    :param project_id: 项目 ID
    :param file_id: 文件版本 ID（可选）
    :return: 删除结果
    """
    logger.info(f"清空多轮干预数据: project={project_id}")
    count = service.clear_interventions(project_id, file_id)
    return {"deleted": count, "message": f"已删除 {count} 条记录"}


@router.delete("/projects/{project_id}/multi-round-interventions/{intervention_id}")
async def delete_intervention(
    project_id: str,
    intervention_id: int
) -> Dict[str, str]:
    """
    删除干预记录

    :param project_id: 项目 ID
    :param intervention_id: 干预记录 ID
    :return: 删除结果
    """
    success = service.delete_intervention(intervention_id, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="干预记录不存在或删除失败")
    return {"message": "删除成功"}


@router.post("/projects/{project_id}/multi-round-interventions/{intervention_id}/reset")
async def reset_intervention(
    project_id: str,
    intervention_id: int
) -> Dict[str, Any]:
    """
    重置干预记录（恢复原始 target，清空 query_rewrite 和 reason）

    :param project_id: 项目 ID
    :param intervention_id: 干预记录 ID
    :return: 重置后的记录
    """
    result = service.reset_intervention(intervention_id, project_id)
    if not result:
        raise HTTPException(status_code=404, detail="干预记录不存在或重置失败")
    return result


@router.post("/projects/{project_id}/multi-round-interventions/sync")
async def sync_from_data_file(
    project_id: str,
    request: SyncRequest
) -> Dict[str, Any]:
    """
    从数据文件同步干预数据

    读取上传的 Excel/CSV 文件，根据轮次配置初始化干预记录

    :param project_id: 项目 ID
    :param request: 同步请求（包含 file_id、rounds_config、validation_limit）
    :return: 同步结果统计
    """
    logger.info(f"从数据文件同步多轮干预数据: project={project_id}, file={request.file_id}")
    result = service.sync_from_data_file(
        project_id=project_id,
        file_id=request.file_id,
        rounds_config=request.rounds_config,
        validation_limit=request.validation_limit
    )

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/projects/{project_id}/multi-round-interventions/export")
async def export_interventions(
    project_id: str,
    file_id: Optional[str] = None
) -> StreamingResponse:
    """
    导出多轮干预数据为 Excel

    格式：每行一条数据，列包含各轮次的 target、query_rewrite、reason

    :param project_id: 项目 ID
    :param file_id: 文件版本 ID
    :return: Excel 文件流
    """
    logger.info(f"导出多轮干预数据: project={project_id}")

    # 获取所有数据
    result = service.get_interventions_paginated(
        project_id=project_id,
        page=1,
        page_size=10000,
        file_id=file_id
    )
    items = result.get("items", [])

    if not items:
        raise HTTPException(status_code=404, detail="没有可导出的数据")

    # 确定最大轮数
    max_rounds = 0
    for item in items:
        rounds_data = item.get("rounds_data", {})
        if rounds_data:
            max_round = max(int(k) for k in rounds_data.keys())
            max_rounds = max(max_rounds, max_round)

    # 构建 DataFrame - 只导出最新数据
    rows = []
    for item in items:
        row = {}

        rounds_data = item.get("rounds_data", {})
        for r in range(1, max_rounds + 1):
            rd = rounds_data.get(str(r), {})
            row[f"第{r}轮_Query"] = rd.get("original_query", "")
            row[f"第{r}轮_期望意图"] = rd.get("target", "")
            row[f"第{r}轮_Query改写"] = rd.get("query_rewrite", "")
            row[f"第{r}轮_备注"] = rd.get("reason", "")

        rows.append(row)

    df = pd.DataFrame(rows)

    # 生成 Excel
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="多轮干预数据")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=multi_round_interventions_{project_id}.xlsx"
        }
    )


# ==================== 单条数据测试验证 ====================

class SingleTestRequest(BaseModel):
    """单条数据测试请求"""
    rounds_data: Dict[str, RoundInterventionData]  # 各轮次数据
    intent_extract_field: str = ""  # 意图提取路径
    response_extract_field: str = ""  # 回复提取路径


@router.post("/projects/{project_id}/multi-round-interventions/{intervention_id}/test")
async def test_single_intervention(
    project_id: str,
    intervention_id: int,
    request: SingleTestRequest
) -> Dict[str, Any]:
    """
    测试单条多轮干预数据

    使用项目配置的 API 接口，对单条数据执行多轮验证

    :param project_id: 项目 ID
    :param intervention_id: 干预记录 ID
    :param request: 测试请求（包含各轮次数据和提取配置）
    :return: 各轮次验证结果
    """
    from app.engine.helpers.verifier import Verifier
    from app.engine.helpers.history_formatter import HistoryFormatter

    logger.info(f"测试单条多轮干预: project={project_id}, intervention_id={intervention_id}")

    # 获取干预记录
    record = service.get_by_id(intervention_id)
    if not record or record.project_id != project_id:
        raise HTTPException(status_code=404, detail="干预记录不存在")

    # 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    model_config = project.get("model_config", {})
    project_config = project.get("config", {})
    multi_round_config = project_config.get("multi_round_config", {})

    # 获取提示词
    prompt = project.get("current_prompt", "")

    # 构建 API 配置
    api_config = {
        "api_url": model_config.get("base_url", ""),
        "api_headers": model_config.get("api_headers", "{}"),
        "api_timeout": model_config.get("timeout", 60),
        "request_template": model_config.get("interface_code", "{}")
    }

    if not api_config["api_url"]:
        raise HTTPException(status_code=400, detail="请先配置 API 地址")

    # 提取配置 - 优先从请求获取，其次从项目配置，最后从最近任务获取
    intent_extract_field = (
        request.intent_extract_field or
        multi_round_config.get("intentExtractField") or
        multi_round_config.get("intent_extract_field") or
        ""
    )
    response_extract_field = (
        request.response_extract_field or
        multi_round_config.get("responseExtractField") or
        multi_round_config.get("response_extract_field") or
        ""
    )

    # 如果仍然为空，尝试从最近的任务配置中获取
    if not intent_extract_field or not response_extract_field:
        latest_task = storage.get_latest_task_by_project(project_id)
        if latest_task and latest_task.get("extra_config"):
            import json
            try:
                extra_config = json.loads(latest_task["extra_config"]) if isinstance(latest_task["extra_config"], str) else latest_task["extra_config"]
                if not intent_extract_field:
                    intent_extract_field = extra_config.get("intent_extract_field", "")
                if not response_extract_field:
                    response_extract_field = extra_config.get("response_extract_field", "")
            except:
                pass

    # 转换 rounds_data
    rounds_data = {k: v.model_dump() for k, v in request.rounds_data.items()}

    # 按轮次排序
    round_nums = sorted(rounds_data.keys(), key=lambda x: int(x))

    # 生成 session_id
    session_id = HistoryFormatter.generate_session_id()

    # 历史消息
    history_messages: List[Dict[str, str]] = []

    # 各轮结果
    round_results: List[Dict[str, Any]] = []

    for round_num in round_nums:
        rd = rounds_data[round_num]
        # 使用改写后的 query，如果没有则使用原始 query
        query = rd.get("query_rewrite") or rd.get("original_query") or ""
        target = rd.get("target") or ""

        if not query:
            # 跳过空 query
            continue

        try:
            result = Verifier.verify_single_with_history(
                index=int(round_num),
                row_index=record.row_index,
                round_number=int(round_num),
                session_id=session_id,
                query=query,
                target=target,
                prompt=prompt,
                model_config=model_config,
                history_messages=history_messages.copy(),
                extract_field=intent_extract_field,
                reason_col_value=rd.get("reason", ""),
                api_config=api_config,
                response_extract_path=response_extract_field
            )

            round_results.append({
                "round": int(round_num),
                "query": query,
                "target": target,
                "output": result.get("output", ""),
                "extracted_intent": result.get("extracted_intent"),
                "extracted_response": result.get("extracted_response"),
                "is_correct": result.get("is_correct", False),
                "latency_ms": result.get("latency_ms", 0),
                "request_params": result.get("request_params"),  # 完整入参
            })

            # 更新历史消息
            history_messages.append({"role": "user", "content": query})
            extracted_response = result.get("extracted_response", "")
            if extracted_response:
                history_messages.append({"role": "assistant", "content": extracted_response})

        except Exception as e:
            logger.error(f"第 {round_num} 轮验证失败: {e}")
            round_results.append({
                "round": int(round_num),
                "query": query,
                "target": target,
                "output": f"ERROR: {str(e)}",
                "is_correct": False,
                "latency_ms": 0
            })
            break  # 出错后停止后续轮次

    # 计算总体结果
    total_rounds = len(round_results)
    correct_rounds = sum(1 for r in round_results if r.get("is_correct"))

    return {
        "intervention_id": intervention_id,
        "row_index": record.row_index,
        "session_id": session_id,
        "total_rounds": total_rounds,
        "correct_rounds": correct_rounds,
        "accuracy": round(correct_rounds / total_rounds * 100, 1) if total_rounds > 0 else 0,
        "round_results": round_results
    }