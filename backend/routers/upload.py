from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
import pandas as pd
import uuid
import storage

router = APIRouter(tags=["upload"])

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(storage.DATA_DIR, f"{file_id}{file_ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 获取列名以便前端选择
    try:
        if file_ext == ".csv":
            df = pd.read_csv(file_path, nrows=5)
        else:
            df = pd.read_excel(file_path, nrows=5)
        columns = df.columns.tolist()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")
        
    return {"file_id": file_id, "columns": columns, "filename": file.filename}
