# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Prompt Optimizer Platform - 一个通过多阶段流水线优化 LLM 提示词的全栈应用。后端基于 FastAPI，前端使用 Next.js。

## 开发命令

### 后端 (Python 3.11)
```bash
cd backend
.\venv\Scripts\activate   # Windows
source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
python -m app.main                    # 启动服务 (端口 8000)
python -m app.main --port 8080        # 指定端口
python -m app.main --log-level DEBUG  # 调试日志

uvicorn app.main:app --reload
```

### 前端 (Node.js 20+)
```bash
cd frontend
npm install
npm run dev    # 开发服务器 (端口 3000)
npm run build  # 生产构建
npm run lint   # ESLint 检查
```

### API 文档
- Swagger UI: http://localhost:8000/docs

## 架构设计

### 后端分层 (`backend/app/`)

```
api/routers/     → HTTP 路由（仅参数校验，禁止业务逻辑）
services/        → 业务服务层（TaskManager 单例管理后台任务）
engine/          → 优化引擎核心（纯逻辑，无 HTTP 依赖）
db/              → SQLite + SQLModel（WAL 模式）
models.py        → 数据库表 + Pydantic 模型
core/            → LLM 工厂、HTTP 客户端、提示词模板
```

### 优化引擎流水线 (`engine/`)

`MultiStrategyOptimizer` 协调以下阶段（定义在 `engine/core/phases/`）：

1. **诊断分析** (`diagnosis/`) - 分析提示词问题，检测意图混淆
2. **策略匹配** (`core/matcher.py`) - 根据诊断结果选择优化策略
3. **候选生成** (`core/candidate_generator.py`) - 并发生成多个优化候选
4. **评估选择** (`helpers/evaluator.py`) - 评估并选择最佳候选
5. **验证** (`helpers/validator.py`) - 验证优化结果

策略实现在 `engine/strategies/`，继承 `BaseStrategy` 并实现 `apply()` 方法。

### 前端 (`frontend/app/`)
- Next.js 14 App Router + TypeScript
- Tailwind CSS + Framer Motion
- `api/[...path]/route.ts` - 代理后端 API
- `project/[id]/` - 项目详情页（执行面板、历史记录、意图干预）

## 代码规范

### 后端 (Python)
- **语言**: 所有注释、文档和日志使用中文
- **类型提示**: 所有函数入参、出参必须标注类型
- **文档字符串**: Google Style，包含功能描述、参数说明、返回值
- **日志**: 只使用 `loguru`（禁止 `print`）
- **异步**: 所有 I/O 操作必须使用 `async/await`
- **数据库迁移**: 新增字段时，必须在 `db/database.py` 的 `_migrate_database()` 中添加迁移逻辑

### 前端 (TypeScript/React)
- 禁止显式 `any` 类型
- 所有 API 响应数据必须定义 Interface
- 使用函数式组件，逻辑抽离到 Custom Hooks
- 使用 Tailwind CSS 编写样式

## 关键模式

### 添加新优化策略
1. 在 `engine/strategies/` 创建新文件，继承 `BaseStrategy`
2. 实现 `name`、`priority`、`description` 属性和 `apply()` 方法
3. 在 `engine/strategies/__init__.py` 注册策略
4. 在 `engine/core/matcher.py` 的 `STRATEGY_CLASSES` 中添加映射

### TaskManager 任务生命周期
`services/task_service.py` 中的 `TaskManager` 是单例，管理后台验证任务：
- `create_task()` → 创建任务并启动后台线程
- 任务状态存储在内存 `self.tasks` 字典中
- 支持暂停/恢复/停止操作
