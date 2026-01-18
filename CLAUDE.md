# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Prompt Optimizer Platform - 一个通过多阶段流水线优化 LLM 提示词的全栈应用。后端基于 FastAPI，前端使用 Next.js。

## 开发命令

### 后端 (Python 3.11)
```bash
cd backend
# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 启动服务 (端口 8000)
python -m app.main
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
- 后端 Swagger UI: http://localhost:8000/docs

## 架构设计

### 后端 (`backend/app/`)
- **`engine/`** - 优化引擎核心（纯逻辑，无 HTTP 依赖）
  - 流水线阶段：诊断分析 → 策略匹配 → 候选生成 → 评估选择 → 验证
  - `MultiStrategyOptimizer` 负责协调整个流程
- **`services/`** - 业务服务层，连接 Engine 与数据库（任务生命周期、项目管理）
- **`api/`** - 路由处理层，使用 Pydantic 校验（禁止包含复杂业务逻辑）
- **`models.py`** - SQLModel 数据库表结构和 Pydantic 交互模型
- **`db/`** - 数据库工具（SQLite，基于 SQLModel/aiosqlite）

### 前端 (`frontend/app/`)
- Next.js 14 App Router + TypeScript
- Tailwind CSS + Framer Motion 实现 UI
- `components/` - 可复用 UI 组件
- `api/` - API 路由处理
- `project/` - 项目相关页面

## 代码规范

### 后端 (Python)
- **语言**: 所有注释、文档和日志使用中文
- **类型提示**: 所有函数入参、出参必须标注类型
- **文档字符串**: Google Style，包含功能描述、参数说明、返回值
- **日志**: 只使用 `loguru`（禁止 `print`）
- **异步**: 所有 I/O 操作必须使用 `async/await`
- **数据库迁移**: 新增字段时，必须在 `migrate_to_sqlite` 中添加迁移逻辑

### 前端 (TypeScript/React)
- 禁止显式 `any` 类型
- 所有 API 响应数据必须定义 Interface
- 使用函数式组件，逻辑抽离到 Custom Hooks
- 使用 Tailwind CSS 编写样式
