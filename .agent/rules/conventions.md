---
trigger: always_on
---

# 项目开发规约

## 1. 核心原则
- **语言**: 全项目强制使用 **中文** 进行注释、文档和日志记录。
- **美学**: 前端界面追求 "Rich Aesthetics"，拒绝平庸设计。
- **异步**: 后端 I/O 密集型操作必须使用 `async/await`。
- **类型安全**: 所有数据交互优先使用 Pydantic Model 定义结构。

## 2. 编码规范

### 🐍 后端 (Python)
- **类型提示 (Type Hints)**: 
    - 所有函数入参、出参必须明确标注类型。
    - 复杂字典结构应定义 Pydantic Model。
- **文档字符串 (Docstrings)**: 
    - 遵循 Google Style。
    - 必须包含：功能描述、参数说明、返回值说明。
    - 示例：
      ```python
      async def optimize_prompt(ctx: OptimizationContext) -> OptimizationResult:
          """
          执行提示词优化流水线的主逻辑
          
          :param ctx: 包含当前优化任务上下文（提示词、错误样例、配置等）
          :return: 优化结果对象，包含新提示词及诊断信息
          """
          pass
      ```
- **日志 (Logging)**: 
    - 使用 `loguru`。
    - **禁止**使用 `print`。
    - 关键业务节点（流水线启动、策略匹配、LLM 调用失败）必须 Log。
- **异常处理**:
    - 捕获具体异常而非通用 `Exception`。
    - 必须对外抛出标准化的 HTTP 异常 (FastAPI HTTPException)。

### ⚛️ 前端 (TypeScript/React)
- **类型安全**: 
    - 严禁显式 `any`。
    - API 响应数据必须定义 Interface。
- **组件设计**: 
    - 逻辑与视图分离 (Custom Hooks)。
    - 优先使用 Functional Components。
- **UI/UX**:
    - 使用 Tailwind CSS 实现原子化样式。
    - 组件间交互增加过渡动画 (Framer Motion)。

## 3. 提示词工程原则
- **精简性**: 剔除冗余修饰词，直接陈述意图。
- **结构化**: 利用 Markdown 符号 (`#`, `-`, `[]`) 分隔语义块。
- **示例驱动 (Few-Shot)**: 复杂任务必须包含 1-3 个正反示例。
- **防御性指令**: 明确告知模型"不知道时如何回答"，防止幻觉。

## 4. 目录结构约定
| 路径 | 说明 | 核心职责 |
| :--- | :--- | :--- |
| `backend/app/engine` | 优化引擎核心 | 存放 Pipeline、策略 (Strategies)、诊断 (Diagnosis)。**纯逻辑，无 HTTP 依赖**。 |
| `backend/app/services` | 业务服务层 | 串联 Engine 与 DB，处理任务状态流转、数据持久化。 |
| `backend/app/api` | 接口层 | 参数校验 (Pydantic)、路由分发、权限控制。**禁止包含复杂业务逻辑**。 |
| `backend/app/models.py` | 数据模型 | 定义通用的 SQLModel 数据库表结构及 Pydantic 交互模型。 |
