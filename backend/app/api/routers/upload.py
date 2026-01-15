from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import pandas as pd
import uuid
from loguru import logger
from typing import Dict, Any, List

from app.db import storage

router = APIRouter(tags=["upload"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    处理文件上传接口
    
    接收上传的文件（支持 CSV, XLS, XLSX），保存到服务器，并解析列名和行数。
    
    :param file: 上传的文件对象
    :return: 包含文件ID、列名列表、文件名和总行数的字典
    :raises HTTPException: 如果文件类型不支持或处理过程中发生错误
    """
    logger.info(f"接收到文件上传请求: {file.filename}, content_type: {file.content_type}")
    
    file_id = str(uuid.uuid4())
    # 确保扩展名小写
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    file_path = os.path.join(storage.DATA_DIR, f"{file_id}{file_ext}")
    
    try:
        # 保存文件到本地存储
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"文件已保存至: {file_path}")
        
        # 获取列名和总行数以便前端选择和配置
        row_count: int = 0
        df_full: pd.DataFrame
        
        if file_ext == ".csv":
            try:
                # 尝试使用 utf-8 编码读取
                df_full = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                # 如果 utf-8 失败，尝试 gbk 编码（常见于中文 Excel/CSV）
                logger.warning(f"UTF-8 解码失败: {file.filename}，尝试 GBK 编码")
                df_full = pd.read_csv(file_path, encoding='gbk')
            row_count = len(df_full)
        elif file_ext in [".xls", ".xlsx"]:
            df_full = pd.read_excel(file_path)
            row_count = len(df_full)
        else:
            logger.warning(f"不支持的文件扩展名: {file_ext}")
            raise HTTPException(status_code=400, detail=f"不支持的文件扩展名: {file_ext}")

        columns: List[str] = df_full.columns.tolist()
        logger.info(f"成功解析列名: {columns}，总行数: {row_count}")
        
        return {
            "file_id": file_id, 
            "columns": columns, 
            "filename": file.filename, 
            "row_count": row_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传/解析中断: {str(e)}")
        logger.exception("完整堆栈信息:")
        raise HTTPException(status_code=400, detail=f"文件处理错误: {str(e)}")
