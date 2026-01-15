from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import pandas as pd
import uuid
from app.db import storage

router = APIRouter(tags=["upload"])

import logging

logger = logging.getLogger(__name__)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    logger.info(f"Receiving file upload: {file.filename}, content_type: {file.content_type}")
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1].lower() # ensure lowercase extension
    file_path = os.path.join(storage.DATA_DIR, f"{file_id}{file_ext}")
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"File saved to {file_path}")
        
        # 获取列名和总行数以便前端选择和配置
        row_count: int = 0
        if file_ext == ".csv":
            try:
                # 尝试使用 utf-8 编码读取
                df_full: pd.DataFrame = pd.read_csv(file_path, encoding='utf-8')
            except UnicodeDecodeError:
                # 如果 utf-8 失败，尝试 gbk 编码（常见于中文 Excel/CSV）
                logger.warning(f"UTF-8 解码失败: {file.filename}，尝试 GBK 编码")
                df_full = pd.read_csv(file_path, encoding='gbk')
            row_count = len(df_full)
        elif file_ext in [".xls", ".xlsx"]:
            df_full = pd.read_excel(file_path)
            row_count = len(df_full)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件扩展名: {file_ext}")

        columns: list = df_full.columns.tolist()
        logger.info(f"成功解析列名: {columns}，总行数: {row_count}")
        return {"file_id": file_id, "columns": columns, "filename": file.filename, "row_count": row_count}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload/parse interrupted: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=400, detail=f"File processing error: {str(e)}")
