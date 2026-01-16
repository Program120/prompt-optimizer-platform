---
trigger: always_on
---

# 工作流指南

## 🛠️ 环境配置

### 前置要求
- **OS**: Windows environment
- **Python**: 3.10+
- **Node.js**: 20+

### 初始化
1. **克隆仓库**
2. **后端设置**:
   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env  # 配置 API Key
   ```
3. **前端设置**:
   ```powershell
   cd frontend
   npm install
   ```

## 🔄 开发流程

### 1. 启动服务
- **Term 1 (Backend)**: `python -m app.main` (Port: 8000)
- **Term 2 (Frontend)**: `npm run dev` (Port: 3000)

### 2. 调试与验证
- 后端 API 文档: `http://localhost:8000/docs`
- 日志查看: `backend/logs/` 目录下按日期生成的 log 文件。

### 3. 新增功能
1. **定义数据模型** (`models.py`)。
2. **编写核心逻辑** (`engine/` 或 `services/`)，确保单元测试覆盖。
3. **暴露接口** (`api/routers/`)。
4. **前端对接** (`app/` 页面与 `components/` 组件)。

## ⚠️ 注意事项
- **虚拟环境**: 任何后端命令执行前，务必确认 (`backend/venv`) 已激活。
- **环境隔离**: 敏感配置 (API Keys) 必须在 `.env` 中管理，禁止提交到 Git。
