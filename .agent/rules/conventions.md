---
trigger: always_on
---

# 项目开发规约文档 (Prompt Optimizer Platform)

## 1. 项目概述
本项目是一个提示词优化平台，旨在通过多策略优化引擎提升大语言模型（LLM）提示词的质量和准确率。

## 2. 技术栈
- **后端**: Python 3.x, FastAPI, Loguru (日志管理), OpenAI SDK (LLM 交互), Pydantic (数据校验)。
- **前端**: React, Next.js, TypeScript, Tailwind CSS, Lucide React (图标)。
- **运行环境**: Windows 操作系统。

## 3. 目录结构
- `backend/`: 后端核心代码。
    - `optimizer_engine/`: 多策略优化引擎核心逻辑。
    - `routers/`: API 路由定义。
    - `logs/`: 自动生成的各个级别日志文件。
- `frontend/`: 前端代码。
    - `app/`: Next.js 页面与路由。
    - `components/`: UI 组件。
- `data/`: 存储项目、任务等持久化数据。
- `docs/`: 项目文档（本规约文件存放处）。

## 4. 编码规范

### 4.1 通用规范
- **语言**: 所有的代码注释、提示信息、文档必须使用**标准中文**。
- **注释**: 
    - 严禁行尾注释；
    - 关键逻辑、方法、类必须有标准的中文文档字符串（Docstrings）或上方注释；
    - 代码的关键位置必须打印日志（Loguru）。

### 4.2 后端 Python 规范
- **变量与函数**:
    - 必须指明入参和出参的变量类型（Type Hints）；
    - 函数名应具有描述性，采用 `snake_case`；
    - 必须使用异步编程方式（`async`/`await`）处理 API 请求和 LLM 调用。
- **示例**:
    ```python
    async def process_task(task_id: str, data: dict) -> bool:
        """
        处理指定任务的逻辑
        :param task_id: 任务唯一标识
        :param data: 任务具体数据
        :return: 是否处理成功
        """
        loguru_logger.info(f"开始处理任务: {task_id}")
        # 执行逻辑...
        return True
    ```

### 4.3 前端 TypeScript 规范
- **组件**: 优先使用函数式组件。
- **类型**: 严禁滥用 `any`，必须定义明确的接口（Interface）或类型（Type）。
- **设计**: UI 界面必须追求“Rich Aesthetics”（丰富的美感），使用渐变、阴影、微动画等提升用户体验。

## 5. 日志与可观测性
- **日志框架**: 使用 `Loguru` 进行日志管理。
- **日志分级**:
    - `debug`: 记录详细的执行过程（开发调试用）；
    - `info`: 记录正常的业务流转；
    - `warn`: 记录非致命性错误或潜在问题；
    - `error`: 记录程序崩溃或严重逻辑错误。
- **存储方案**: 日志按级别存放在 `backend/logs/` 目录下，按天滚动存储。

## 6. 提示词优化原则
在编写和优化 LLM 提示词时，必须遵循以下原则：
- **精简**: 去除冗余描述，直击核心意图；
- **高效**: 减少模型思考负担，提高响应质量；
- **易理解**: 结构清晰，便于人类阅读和二次调整。

## 7. 环境要求
- **操作系统**: Windows。
- **虚拟环境**: 运行后端代码前必须确认是否在虚拟环境中。
- **依赖管理**: 后端使用 `pip` (requirements.txt)，前端使用 `npm`。
