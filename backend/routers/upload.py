from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import pandas as pd
import uuid
import storage

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
        
        # 获取列名以便前端选择
        if file_ext == ".csv":
            try:
                # Try reading with utf-8 first
                df = pd.read_csv(file_path, nrows=5, encoding='utf-8')
            except UnicodeDecodeError:
                # If utf-8 fails, try gbk (common for Chinese excel/csv)
                logger.warning(f"UTF-8 decode failed for {file.filename}, trying GBK")
                df = pd.read_csv(file_path, nrows=5, encoding='gbk')
        elif file_ext in [".xls", ".xlsx"]:
            df = pd.read_excel(file_path, nrows=5)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: {file_ext}")

        columns = df.columns.tolist()
        logger.info(f"Successfully parsed columns: {columns}")
        return {"file_id": file_id, "columns": columns, "filename": file.filename}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload/parse interrupted: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=400, detail=f"File processing error: {str(e)}")
