from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import FileResponse
from typing import Optional, Dict, Any, List
import os
import json
import pandas as pd
from loguru import logger

from app.db import storage
from app.services.task_service import TaskManager

router = APIRouter(prefix="/tasks", tags=["tasks"])
tm = TaskManager()

@router.post("/start")
async def start_task(
    project_id: str = Form(...),
    file_id: str = Form(...),
    query_col: str = Form(...),
    target_col: str = Form(...),
    reason_col: Optional[str] = Form(None),
    prompt: str = Form(...),
    extract_field: Optional[str] = Form(None),
    original_filename: Optional[str] = Form(None),
    validation_limit: Optional[int] = Form(None)
) -> Dict[str, str]:
    """
    启动一个新的优化任务
    
    验证文件和项目配置，根据指定参数启动 Prompt 优化任务。
    
    :param project_id: 项目ID
    :param file_id: 文件ID
    :param query_col: 问题/输入列名
    :param target_col: 目标/期望输出列名
    :param reason_col: 推理步骤列名（可选）
    :param prompt: 初始Prompt
    :param extract_field: 提取字段（可选）
    :param original_filename: 原始文件名（可选）
    :param validation_limit: 验证集数量限制（可选）
    :return: 包含任务ID的字典
    :raises HTTPException: 如果文件或项目不存在，或配置不正确
    """
    logger.info(f"收到启动任务请求: project_id={project_id}, file_id={file_id}")
    
    # 查找文件路径
    file_path = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break
    
    if not file_path:
        logger.error(f"文件未找到: file_id={file_id}")
        raise HTTPException(status_code=404, detail="文件未找到")
        
    # 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        logger.error(f"项目未找到: project_id={project_id}")
        raise HTTPException(status_code=404, detail="项目未找到")
        
    model_config = project.get("model_config")
    # 检查是否为接口验证模式
    is_interface_mode = model_config and model_config.get("validation_mode") == "interface"
    
    # 只有非接口验证模式才强制要求 api_key
    if not is_interface_mode and (not model_config or not model_config.get("api_key")):
        logger.warning(f"缺少API Key配置: project_id={project_id}")
        raise HTTPException(status_code=400, detail="请先在项目设置中配置模型参数(API Key)")

    try:
        task_id = tm.create_task(
            project_id, 
            file_path, 
            query_col, 
            target_col, 
            prompt, 
            model_config, 
            extract_field, 
            original_filename, 
            validation_limit, 
            reason_col=reason_col
        )
        logger.info(f"任务启动成功: task_id={task_id}")
        return {"task_id": task_id}
    except Exception as e:
        logger.exception(f"启动任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


@router.post("/start-multi-round")
async def start_multi_round_task(
    project_id: str = Form(...),
    file_id: str = Form(...),
    prompt: str = Form(...),
    rounds_config: str = Form(...),
    intent_extract_field: str = Form(...),
    response_extract_field: str = Form(...),
    original_filename: Optional[str] = Form(None),
    validation_limit: Optional[int] = Form(None),
    api_config: Optional[str] = Form(None)
) -> Dict[str, str]:
    """
    启动多轮验证任务

    :param project_id: 项目ID
    :param file_id: 文件ID
    :param prompt: 提示词
    :param rounds_config: 轮次配置 JSON 字符串
        格式: [{"round": 1, "query_col": "query1", "target_col": "target1"},
               {"round": 2, "query_col": "query2", "target_col": "target2"}]
    :param intent_extract_field: 意图提取路径（用于从响应中提取识别的意图，如 data.intent）
    :param response_extract_field: 回复内容提取路径（用于构建下一轮历史，如 data.response）
    :param original_filename: 原始文件名（可选）
    :param validation_limit: 验证数量限制（可选）
    :param api_config: 自定义 API 配置 JSON 字符串（可选）
        格式: {"api_url": "...", "api_headers": "{}", "api_timeout": 60, "request_template": "...", "concurrency": 5}
    :return: 包含任务ID的字典
    :raises HTTPException: 如果文件或项目不存在，或配置不正确
    """
    logger.info(f"收到多轮验证任务请求: project_id={project_id}, file_id={file_id}")

    # 解析轮次配置
    try:
        parsed_rounds_config: List[Dict[str, Any]] = json.loads(rounds_config)
        if not isinstance(parsed_rounds_config, list) or len(parsed_rounds_config) == 0:
            raise ValueError("rounds_config 必须是非空列表")
    except json.JSONDecodeError as e:
        logger.error(f"解析 rounds_config 失败: {e}")
        raise HTTPException(status_code=400, detail=f"rounds_config JSON 格式错误: {e}")

    # 验证轮次配置：每轮都需要 query_col 和 target_col
    for idx, cfg in enumerate(parsed_rounds_config):
        if "round" not in cfg or "query_col" not in cfg or "target_col" not in cfg:
            raise HTTPException(
                status_code=400,
                detail=f"轮次配置[{idx}]缺少必需字段 (round, query_col, target_col)"
            )

    # 解析 API 配置
    parsed_api_config: Optional[Dict[str, Any]] = None
    if api_config:
        try:
            parsed_api_config = json.loads(api_config)
            if not isinstance(parsed_api_config, dict):
                raise ValueError("api_config 必须是对象")
            # 验证必需字段
            if not parsed_api_config.get("api_url"):
                raise ValueError("api_config.api_url 不能为空")
        except json.JSONDecodeError as e:
            logger.error(f"解析 api_config 失败: {e}")
            raise HTTPException(status_code=400, detail=f"api_config JSON 格式错误: {e}")

    # 查找文件路径
    file_path = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break

    if not file_path:
        logger.error(f"文件未找到: file_id={file_id}")
        raise HTTPException(status_code=404, detail="文件未找到")

    # 获取项目配置
    project = storage.get_project(project_id)
    if not project:
        logger.error(f"项目未找到: project_id={project_id}")
        raise HTTPException(status_code=404, detail="项目未找到")

    model_config = project.get("model_config", {})

    # 如果没有提供自定义 API 配置，则需要检查项目的模型配置
    if not parsed_api_config:
        # 检查是否配置了接口验证模式
        if model_config.get("validation_mode") != "interface":
            logger.warning(f"多轮验证需要配置 API: project_id={project_id}")
            raise HTTPException(
                status_code=400,
                detail="多轮验证需要配置 API 接口信息"
            )

    try:
        task_id = tm.create_multi_round_task(
            project_id=project_id,
            file_path=file_path,
            prompt=prompt,
            model_config=model_config,
            rounds_config=parsed_rounds_config,
            intent_extract_field=intent_extract_field,
            response_extract_field=response_extract_field,
            original_filename=original_filename,
            validation_limit=validation_limit,
            api_config=parsed_api_config
        )
        logger.info(f"多轮验证任务启动成功: task_id={task_id}")
        return {"task_id": task_id}
    except Exception as e:
        logger.exception(f"启动多轮验证任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")

@router.get("/{task_id}")
async def get_task_status(
    task_id: str,
    include_results: bool = True
) -> Dict[str, Any]:
    """
    获取任务状态
    
    :param task_id: 任务ID
    :param include_results: 是否包含完整的 results 和 errors 数据 (默认 True 以保持兼容)
    :return: 任务状态详情
    :raises HTTPException: 如果任务未找到
    """
    # 获取任务状态
    status = tm.get_task_status(task_id, include_results=include_results)
    if not status:
        logger.warning(f"获取任务状态失败（未找到）: task_id={task_id}")
        raise HTTPException(status_code=404, detail="任务未找到")
    return status

@router.get("/{task_id}/results")
async def get_task_results(
    task_id: str,
    page: int = 1,
    page_size: int = 50,
    type: Optional[str] = None,
    search: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取分页的任务结果
    
    :param task_id: 任务ID
    :param page: 页码
    :param page_size: 每页数量
    :param type: 结果类型过滤 'success' | 'error' | None
    :param search: 搜索关键字
    :return: 分页结果
    """
    # 验证任务是否存在
    status = tm.get_task_status(task_id, include_results=False)
    if not status:
        raise HTTPException(status_code=404, detail="任务未找到")

    return tm.get_task_results(task_id, page, page_size, type, search)

@router.post("/{task_id}/pause")
async def pause_task(task_id: str) -> Dict[str, str]:
    """
    暂停任务
    
    :param task_id: 任务ID
    :return: 操作状态
    :raises HTTPException: 如果任务未找到
    """
    logger.info(f"请求暂停任务: task_id={task_id}")
    if tm.pause_task(task_id):
        return {"status": "success"}
    
    logger.warning(f"暂停任务失败（未找到）: task_id={task_id}")
    raise HTTPException(status_code=404, detail="任务未找到")

@router.post("/{task_id}/resume")
async def resume_task(task_id: str) -> Dict[str, str]:
    """
    恢复任务
    
    :param task_id: 任务ID
    :return: 操作状态
    :raises HTTPException: 如果任务未找到
    """
    logger.info(f"请求恢复任务: task_id={task_id}")
    if tm.resume_task(task_id):
        return {"status": "success"}
        
    logger.warning(f"恢复任务失败（未找到）: task_id={task_id}")
    raise HTTPException(status_code=404, detail="任务未找到")

@router.post("/{task_id}/stop")
async def stop_task(task_id: str) -> Dict[str, str]:
    """
    停止任务
    
    :param task_id: 任务ID
    :return: 操作状态
    :raises HTTPException: 如果任务未找到
    """
    logger.info(f"请求停止任务: task_id={task_id}")
    if tm.stop_task(task_id):
        return {"status": "success"}
        
    logger.warning(f"停止任务失败（未找到）: task_id={task_id}")
    raise HTTPException(status_code=404, detail="任务未找到")

@router.delete("/{task_id}")
async def delete_task_endpoint(task_id: str) -> Dict[str, str]:
    """
    删除任务
    
    从存储中删除任务记录。
    
    :param task_id: 任务ID
    :return: 操作状态
    :raises HTTPException: 如果任务未找到
    """
    logger.info(f"请求删除任务: task_id={task_id}")
    if storage.delete_task(task_id):
        return {"status": "success"}
        
    logger.warning(f"删除任务失败（未找到）: task_id={task_id}")
    raise HTTPException(status_code=404, detail="任务未找到")

@router.get("/{task_id}/export")
async def export_task_results(task_id: str) -> FileResponse:
    """
    导出任务结果
    
    将任务的成功和失败结果导出为 Excel 文件。
    
    :param task_id: 任务ID
    :return: Excel 文件响应
    :raises HTTPException: 如果任务未找到或导出失败
    """
    logger.info(f"请求导出任务结果: task_id={task_id}")
    
    # 导出时需要包含完整的 results 数据
    status = tm.get_task_status(task_id, include_results=True)
    if not status:
        logger.warning(f"导出失败（未找到任务）: task_id={task_id}")
        raise HTTPException(status_code=404, detail="任务未找到")
    
    try:
        # 获取所有结果
        original_results = status.get("results", [])
        
        # --- 增强原因数据 (优先使用 Reason 库, 按 file_id 版本筛选) ---
        project_id = status.get("project_id")
        file_id = status.get("file_id")  # 获取任务关联的文件版本
        results = []
        if project_id:
            try:
                # 获取原因映射 (按 file_id 版本筛选)
                from app.services import intervention_service
                reason_map = intervention_service.get_intervention_map(project_id, file_id=file_id)
                
                # 复制并增强结果
                for r in original_results:
                    new_r = r.copy()
                    # 如果库中有原因，优先使用库中的
                    if new_r.get("query") in reason_map:
                        new_r["reason"] = reason_map[new_r["query"]]
                    results.append(new_r)
                    
                logger.debug(f"Enriched results with {len(reason_map)} reasons from file_id={file_id}")
            except Exception as e:
                logger.error(f"Failed to enrich results with reasons: {e}")
                results = original_results
        else:
            results = original_results
        # --------------------------------------
        
        # 分离成功和失败的数据
        success_data = [r for r in results if r.get("is_correct")]
        failed_data = [r for r in results if not r.get("is_correct")]
        
        # 文件名包含进度信息
        current = len(results)
        total = status.get("total_count", "?")
        export_path = os.path.join(storage.DATA_DIR, f"results_{task_id}.xlsx")
        
        # 使用 ExcelWriter 写入多个 sheet
        with pd.ExcelWriter(export_path, engine='openpyxl') as writer:
            if success_data:
                df_success = pd.DataFrame(success_data)
                # 确保 reason 列在最后或者合适的位置，这里不强制排序，但确保包含 reason
                df_success.to_excel(writer, sheet_name='Success', index=False)
            else:
                # 如果没有成功数据，创建一个空的 DataFrame 并带有列头
                pd.DataFrame(columns=["index", "query", "target", "output", "is_correct", "reason"]).to_excel(writer, sheet_name='Success', index=False)
                
            if failed_data:
                df_failed = pd.DataFrame(failed_data)
                df_failed.to_excel(writer, sheet_name='Failed', index=False)
            else:
                pd.DataFrame(columns=["index", "query", "target", "output", "is_correct", "reason"]).to_excel(writer, sheet_name='Failed', index=False)
        
        logger.info(f"结果已导出至: {export_path}")
        
        # 返回文件，文件名中包含进度信息
        filename = f"results_{task_id}_{current}of{total}.xlsx"
        return FileResponse(
            export_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=filename
        )
    except Exception as e:
        logger.exception(f"导出过程发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

@router.get("/{task_id}/download_dataset")
async def download_task_dataset(task_id: str) -> FileResponse:
    """
    下载任务数据集
    
    下载与任务关联的原始数据集文件。
    
    :param task_id: 任务ID
    :return: 文件流响应
    :raises HTTPException: 如果任务或文件未找到
    """
    logger.info(f"请求下载数据集: task_id={task_id}")
    status = tm.get_task_status(task_id)
    if not status:
        logger.warning(f"下载数据集失败（未找到任务）: task_id={task_id}")
        raise HTTPException(status_code=404, detail="任务未找到")
    
    file_path = status.get("file_path")
    if not file_path or not os.path.exists(file_path):
        logger.error(f"数据集文件不存在: path={file_path}")
        raise HTTPException(status_code=404, detail="数据集文件未找到")
        
    original_filename = status.get("original_filename")
    if not original_filename:
        # 如果没有保存原始文件名，尝试从路径提取 UUID 或回退
        original_filename = os.path.basename(file_path)
    
    logger.info(f"开始下载文件: {file_path}, save_as: {original_filename}")
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=original_filename
    )
