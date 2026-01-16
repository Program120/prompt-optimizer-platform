---
trigger: always_on
---

# Prompt Optimizer Platform 文档索引

## 📖 文档导航

- **[项目架构 (Architecture)](./architecture.md)**
  - 核心模块及其交互链路
  - 技术栈全景图

- **[开发规约 (Conventions)](./conventions.md)**
  - 命名与代码风格
  - 日志与可观测性
  - 提示词工程原则

- **[工作流指南 (Workflow)](./workflow.md)**
  - 环境搭建与启动
  - 依赖管理
  - 目录结构说明

## 🚀 快速开始

### 后端 (Backend)
```bash
cd backend
# 激活虚拟环境
.\venv\Scripts\activate
# 安装依赖
pip install -r requirements.txt
# 启动服务
python -m app.main
```

### 前端 (Frontend)
```bash
cd frontend
# 安装依赖
npm install
# 启动开发服务器
npm run dev
```
