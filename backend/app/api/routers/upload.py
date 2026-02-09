from fastapi import APIRouter, UploadFile, File, HTTPException, Form
import os
import shutil
import pandas as pd
import uuid
import re
import json
import requests
from loguru import logger
from typing import Dict, Any, List, Optional

from app.db import storage

router = APIRouter(tags=["upload"])

# 中文数字映射
CN_NUM_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15,
}

def cn_to_num(s: str) -> Optional[int]:
    """将中文数字或阿拉伯数字字符串转换为整数"""
    s = s.strip()
    if s.isdigit():
        return int(s)
    return CN_NUM_MAP.get(s)

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


@router.post("/upload/detect-multi-round")
async def detect_multi_round_columns(
    file_id: str = Form(...)
) -> Dict[str, Any]:
    """
    自动检测文件中的多轮对话列配置

    扫描文件列名，识别 query1/answer1/query2/answer2 等模式，
    自动生成轮次配置。

    支持的列名模式：
    - query1, answer1, query2, answer2, ..., queryN, target
    - q1, a1, q2, a2, ..., qN, target
    - 问题1, 回答1, 问题2, 回答2, ..., 问题N, 预期结果/target

    :param file_id: 文件ID
    :return: 检测结果，包含是否检测到多轮配置、最大轮数、轮次配置列表
    :raises HTTPException: 如果文件未找到
    """
    logger.info(f"检测多轮列配置: file_id={file_id}")

    # 查找文件路径
    file_path: Optional[str] = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break

    if not file_path:
        logger.error(f"文件未找到: file_id={file_id}")
        raise HTTPException(status_code=404, detail="文件未找到")

    # 读取文件获取列名
    try:
        if file_path.endswith(".csv"):
            try:
                df = pd.read_csv(file_path, encoding='utf-8', nrows=0)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk', nrows=0)
        else:
            df = pd.read_excel(file_path, nrows=0)

        columns: List[str] = df.columns.tolist()
        logger.info(f"文件列名: {columns}")
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    # 定义列名匹配模式（支持阿拉伯数字和中文数字）
    query_patterns = [
        (r'^query(\d+)$', 'query'),           # query1, query2, ...
        (r'^q(\d+)$', 'q'),                    # q1, q2, ...
        (r'^问题(\d+)$', '问题'),              # 问题1, 问题2, ...
        (r'^user(\d+)$', 'user'),              # user1, user2, ...
        (r'^input(\d+)$', 'input'),            # input1, input2, ...
        (r'^第(.+)轮问题$', '轮问题'),          # 第一轮问题, 第1轮问题, ...
        (r'^第(.+)轮query$', '轮query'),        # 第一轮query, 第1轮query, ...
    ]

    answer_patterns = [
        (r'^answer(\d+)$', 'answer'),          # answer1, answer2, ...
        (r'^a(\d+)$', 'a'),                    # a1, a2, ...
        (r'^回答(\d+)$', '回答'),              # 回答1, 回答2, ...
        (r'^assistant(\d+)$', 'assistant'),    # assistant1, assistant2, ...
        (r'^output(\d+)$', 'output'),          # output1, output2, ...
        (r'^response(\d+)$', 'response'),      # response1, response2, ...
    ]

    target_patterns = [
        (r'^target(\d+)$', 'target'),          # target1, target2, ...
        (r'^t(\d+)$', 't'),                    # t1, t2, ...
        (r'^预期(\d+)$', '预期'),              # 预期1, 预期2, ...
        (r'^意图(\d+)$', '意图'),              # 意图1, 意图2, ...
        (r'^intent(\d+)$', 'intent'),          # intent1, intent2, ...
        (r'^expected(\d+)$', 'expected'),      # expected1, expected2, ...
        (r'^label(\d+)$', 'label'),            # label1, label2, ...
        (r'^第(.+)轮.*(?:期望)?意图$', '轮意图'),  # 第一轮期望意图, 第1轮意图, ...
        (r'^第(.+)轮.*target$', '轮target'),    # 第一轮target, ...
    ]

    rewrite_patterns = [
        (r'^rewrite(\d+)$', 'rewrite'),        # rewrite1, rewrite2, ...
        (r'^改写(\d+)$', '改写'),              # 改写1, 改写2, ...
        (r'^query_rewrite(\d+)$', 'query_rewrite'),  # query_rewrite1, ...
        (r'^rw(\d+)$', 'rw'),                  # rw1, rw2, ...
        (r'^第(.+)轮.*(?:query)?重写$', '轮重写'),  # 第一轮期望query重写, 第1轮重写, ...
        (r'^第(.+)轮.*改写$', '轮改写'),        # 第一轮改写, 第1轮query改写, ...
    ]

    reason_patterns = [
        (r'^reason(\d+)$', 'reason'),          # reason1, reason2, ...
        (r'^原因(\d+)$', '原因'),              # 原因1, 原因2, ...
        (r'^备注(\d+)$', '备注'),              # 备注1, 备注2, ...
        (r'^note(\d+)$', 'note'),              # note1, note2, ...
        (r'^comment(\d+)$', 'comment'),        # comment1, comment2, ...
        (r'^第(.+)轮.*原因$', '轮原因'),        # 第一轮原因, ...
        (r'^第(.+)轮.*备注$', '轮备注'),        # 第一轮备注, ...
    ]

    # 检测 query 列
    query_cols: Dict[int, str] = {}
    query_prefix: Optional[str] = None

    for col in columns:
        for pattern, prefix in query_patterns:
            match = re.match(pattern, col, re.IGNORECASE)
            if match:
                round_num = cn_to_num(match.group(1))
                if round_num:
                    query_cols[round_num] = col
                    query_prefix = prefix
                break

    # 检测 target 列（每轮都有）
    target_cols: Dict[int, str] = {}
    target_prefix: Optional[str] = None

    for col in columns:
        for pattern, prefix in target_patterns:
            match = re.match(pattern, col, re.IGNORECASE)
            if match:
                round_num = cn_to_num(match.group(1))
                if round_num:
                    target_cols[round_num] = col
                    target_prefix = prefix
                break

    # 检测 rewrite 列（可选）
    rewrite_cols: Dict[int, str] = {}
    rewrite_prefix: Optional[str] = None

    for col in columns:
        for pattern, prefix in rewrite_patterns:
            match = re.match(pattern, col, re.IGNORECASE)
            if match:
                round_num = cn_to_num(match.group(1))
                if round_num:
                    rewrite_cols[round_num] = col
                    rewrite_prefix = prefix
                break

    # 检测 reason 列（可选）
    reason_cols: Dict[int, str] = {}
    reason_prefix: Optional[str] = None

    for col in columns:
        for pattern, prefix in reason_patterns:
            match = re.match(pattern, col, re.IGNORECASE)
            if match:
                round_num = cn_to_num(match.group(1))
                if round_num:
                    reason_cols[round_num] = col
                    reason_prefix = prefix
                break

    # 如果没有检测到 query 列，返回未检测到
    if not query_cols:
        logger.info("未检测到多轮列配置")
        return {
            "detected": False,
            "max_rounds": 0,
            "rounds_config": [],
            "columns": columns
        }

    # 构建轮次配置（每轮都有 query_col 和 target_col，rewrite_col 和 reason_col 可选）
    max_round = max(query_cols.keys())
    rounds_config: List[Dict[str, Any]] = []

    for round_num in range(1, max_round + 1):
        config: Dict[str, Any] = {
            "round": round_num,
            "query_col": query_cols.get(round_num, ""),
            "target_col": target_cols.get(round_num, ""),
            "rewrite_col": rewrite_cols.get(round_num, ""),
            "reason_col": reason_cols.get(round_num, ""),
        }
        rounds_config.append(config)

    logger.info(f"检测到多轮配置: max_rounds={max_round}, config={rounds_config}")

    return {
        "detected": True,
        "max_rounds": max_round,
        "rounds_config": rounds_config,
        "columns": columns,
        "detected_patterns": {
            "query_prefix": query_prefix,
            "target_prefix": target_prefix,
            "rewrite_prefix": rewrite_prefix,
            "reason_prefix": reason_prefix
        }
    }


@router.post("/upload/detect-multi-round-llm")
async def detect_multi_round_columns_with_llm(
    file_id: str = Form(...),
    project_id: str = Form(...)
) -> Dict[str, Any]:
    """
    使用 LLM 智能检测文件中的多轮对话列配置

    当正则匹配无法识别列名时，使用 LLM 分析列名语义，
    智能识别哪些列是 query（用户问题）、哪些是 target（期望意图）。

    :param file_id: 文件ID
    :param project_id: 项目ID（用于获取模型配置）
    :return: 检测结果，包含是否检测到多轮配置、轮次配置列表
    :raises HTTPException: 如果文件未找到或 LLM 调用失败
    """
    logger.info(f"使用 LLM 检测多轮列配置: file_id={file_id}, project_id={project_id}")

    # 查找文件路径
    file_path: Optional[str] = None
    for f in os.listdir(storage.DATA_DIR):
        if f.startswith(file_id):
            file_path = os.path.join(storage.DATA_DIR, f)
            break

    if not file_path:
        logger.error(f"文件未找到: file_id={file_id}")
        raise HTTPException(status_code=404, detail="文件未找到")

    # 读取文件获取列名和样本数据
    try:
        if file_path.endswith(".csv"):
            try:
                df = pd.read_csv(file_path, encoding='utf-8', nrows=3)
            except UnicodeDecodeError:
                df = pd.read_csv(file_path, encoding='gbk', nrows=3)
        else:
            df = pd.read_excel(file_path, nrows=3)

        columns: List[str] = df.columns.tolist()

        # 获取样本数据（前3行）用于帮助 LLM 理解
        sample_data: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            row_dict = {}
            for col in columns:
                val = row[col]
                if pd.isna(val):
                    row_dict[col] = ""
                else:
                    # 截断过长的内容
                    str_val = str(val)
                    row_dict[col] = str_val[:100] + "..." if len(str_val) > 100 else str_val
            sample_data.append(row_dict)

        logger.info(f"文件列名: {columns}")
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}")

    # 从全局模型中获取默认模型配置（名称包含 qwen3-30b-a3b 的模型）
    # 自动检测功能使用全局默认模型，而非项目的验证配置
    global_models = storage.get_global_models()
    default_model = None

    # 优先查找名称包含 qwen3-30b-a3b 的模型
    for model in global_models:
        model_name_lower = (model.get("name") or "").lower()
        model_model_name_lower = (model.get("model_name") or "").lower()
        if "qwen3-30b-a3b" in model_name_lower or "qwen3-30b-a3b" in model_model_name_lower:
            default_model = model
            logger.info(f"使用全局默认模型: {model.get('name')} ({model.get('model_name')})")
            break

    # 如果没找到指定模型，使用第一个全局模型
    if not default_model and global_models:
        default_model = global_models[0]
        logger.info(f"未找到 qwen3-30b-a3b 模型，使用第一个全局模型: {default_model.get('name')}")

    # 如果没有全局模型，使用硬编码的默认值
    if default_model:
        base_url = default_model.get("base_url") or ""
        api_key = default_model.get("api_key") or ""
        model_name = default_model.get("model_name") or "gpt-3.5-turbo"
    else:
        logger.warning("未配置全局模型，使用硬编码默认值")
        base_url = "https://inference-jdaip-cn-north-1.jdcloud.com/queue-6336e32dcffa96fb2f52b063809c1cc1/api/predict/qwen3-30b-a3b-instruct-yace-v5/v1"
        api_key = "aac97926e76f49f9bd3d4c5e4f5ed3fe"
        model_name = "qwen3-30b-a3b-instruct-2507-yace"

    # 构建 LLM 提示词
    prompt = f"""你是一个数据分析专家。请分析以下 Excel/CSV 文件的列名和样本数据，识别出多轮对话的列配置。

## 任务说明
这是一个多轮对话验证数据集，每一行代表一个完整的多轮对话场景。
- **Query 列**：用户在每一轮提出的问题/输入（如：第一轮问题、query1、问题1）
- **Target 列**：每一轮期望的意图/标签/分类结果（如：第一轮期望意图、target1、意图1）
- **Rewrite 列**（可选）：Query 的改写版本，用于替代原始 Query 进行验证（如：第一轮期望query重写、rewrite1、改写1）
- **Reason 列**（可选）：原因/备注说明（如：第一轮原因、reason1、备注1）

数据集可能包含任意数量的轮次（1轮、2轮、3轮、4轮或更多），请识别出所有轮次。

## 文件列名
{json.dumps(columns, ensure_ascii=False, indent=2)}

## 样本数据（前3行）
{json.dumps(sample_data, ensure_ascii=False, indent=2)}

## 输出要求
请分析列名和数据内容，识别出：
1. 哪些列是第1轮、第2轮、第3轮...的 Query（用户问题）
2. 哪些列是第1轮、第2轮、第3轮...的 Target（期望意图/标签）
3. 哪些列是第1轮、第2轮、第3轮...的 Rewrite（Query改写）- 列名中包含"重写"、"改写"、"rewrite"等关键词
4. 哪些列是第1轮、第2轮、第3轮...的 Reason（原因/备注）- 列名中包含"原因"、"备注"、"reason"、"note"等关键词

**重要提示：**
- 请识别文件中的所有轮次，不要遗漏任何一轮！
- 仔细检查每个列名，特别注意包含"重写"、"改写"的列应该映射到 rewrite_col
- 中文列名如"第一轮期望query重写"应该识别为第1轮的 rewrite_col

请严格按照以下 JSON 格式输出，不要输出其他内容：
```json
{{
  "detected": true,
  "max_rounds": N,
  "rounds_config": [
    {{"round": 1, "query_col": "第1轮的Query列名", "target_col": "第1轮的Target列名", "rewrite_col": "第1轮的Rewrite列名或空字符串", "reason_col": "第1轮的Reason列名或空字符串"}},
    {{"round": 2, "query_col": "第2轮的Query列名", "target_col": "第2轮的Target列名", "rewrite_col": "第2轮的Rewrite列名或空字符串", "reason_col": "第2轮的Reason列名或空字符串"}},
    ... (根据实际轮次数量继续添加)
  ],
  "reasoning": "简要说明识别逻辑，包括识别到的轮次数量"
}}
```

如果无法识别出多轮对话结构，请输出：
```json
{{
  "detected": false,
  "max_rounds": 0,
  "rounds_config": [],
  "reasoning": "无法识别的原因"
}}
```

注意：
- query_col 和 target_col 必须是文件中实际存在的列名（完全匹配，包括中文字符）
- rewrite_col 和 reason_col 是可选的，如果没有对应列，设为空字符串 ""
- 如果某一轮没有对应的 target 列，target_col 可以为空字符串
- 轮次从 1 开始编号
- max_rounds 应该等于 rounds_config 数组的长度"""

    # 调用 LLM
    try:
        # 确保 base_url 以 /chat/completions 结尾
        if not base_url.endswith("/chat/completions"):
            if base_url.endswith("/"):
                base_url = base_url + "chat/completions"
            else:
                base_url = base_url + "/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "api-key": api_key
        }

        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0,
            "max_tokens": 2000
        }

        logger.info(f"调用 LLM 分析列名: {base_url}")
        resp = requests.post(base_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()

        # 确保响应使用正确的编码
        resp.encoding = 'utf-8'
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

        logger.info(f"LLM 响应: {content[:500]}")

        # 解析 LLM 返回的 JSON
        # 尝试从响应中提取 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # 尝试直接解析整个响应
            json_str = content

        parsed_result = json.loads(json_str)

        # 辅助函数：模糊匹配列名
        def find_matching_column(col_name: str, available_columns: List[str]) -> str:
            """
            在可用列名中查找匹配的列名
            支持精确匹配、忽略大小写匹配、去除空格匹配
            """
            if not col_name:
                return ""

            # 1. 精确匹配
            if col_name in available_columns:
                return col_name

            # 2. 忽略大小写匹配
            col_lower = col_name.lower().strip()
            for col in available_columns:
                if col.lower().strip() == col_lower:
                    logger.info(f"列名模糊匹配: '{col_name}' -> '{col}'")
                    return col

            # 3. 去除所有空格后匹配
            col_no_space = col_name.replace(" ", "").replace("\t", "").lower()
            for col in available_columns:
                if col.replace(" ", "").replace("\t", "").lower() == col_no_space:
                    logger.info(f"列名模糊匹配(去空格): '{col_name}' -> '{col}'")
                    return col

            # 4. 包含匹配（列名包含目标字符串或目标字符串包含列名）
            for col in available_columns:
                if col_lower in col.lower() or col.lower() in col_lower:
                    logger.info(f"列名模糊匹配(包含): '{col_name}' -> '{col}'")
                    return col

            return ""

        # 验证返回的列名是否存在于文件中
        if parsed_result.get("detected"):
            valid_config = []
            logger.info(f"LLM 返回的原始配置: {parsed_result.get('rounds_config')}")
            logger.info(f"文件实际列名: {columns}")

            for cfg in parsed_result.get("rounds_config", []):
                query_col = cfg.get("query_col", "")
                target_col = cfg.get("target_col", "")

                # 使用模糊匹配查找列名
                matched_query = find_matching_column(query_col, columns)
                matched_target = find_matching_column(target_col, columns)

                if query_col and not matched_query:
                    logger.warning(f"LLM 返回的 query_col '{query_col}' 无法匹配到文件中的任何列")
                if target_col and not matched_target:
                    logger.warning(f"LLM 返回的 target_col '{target_col}' 无法匹配到文件中的任何列")

                valid_config.append({
                    "round": cfg.get("round", len(valid_config) + 1),
                    "query_col": matched_query,
                    "target_col": matched_target
                })

            logger.info(f"验证后的配置: {valid_config}")

            parsed_result["rounds_config"] = valid_config
            parsed_result["max_rounds"] = len(valid_config)

        # 添加列名信息
        parsed_result["columns"] = columns
        parsed_result["detection_method"] = "llm"

        logger.info(f"LLM 检测结果: detected={parsed_result.get('detected')}, rounds={parsed_result.get('max_rounds')}")

        return parsed_result

    except json.JSONDecodeError as e:
        logger.error(f"解析 LLM 响应失败: {e}, content={content[:200]}")
        return {
            "detected": False,
            "max_rounds": 0,
            "rounds_config": [],
            "columns": columns,
            "error": f"LLM 响应解析失败: {str(e)}",
            "detection_method": "llm"
        }
    except requests.RequestException as e:
        logger.error(f"调用 LLM 失败: {e}")
        raise HTTPException(status_code=500, detail=f"调用 LLM 失败: {str(e)}")
    except Exception as e:
        logger.error(f"LLM 检测过程出错: {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")
