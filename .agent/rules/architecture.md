---
trigger: always_on
---

# 系统架构设计

## 🏗️ 架构概览

本平台采用 **前后端分离** 架构，后端基于 FastAPI 构建高性能 API 服务，前端使用 Next.js 提供现代化交互体验。

```mermaid
graph TD
    User[用户] --> |HTTP/WebSocket| FE[前端 (Next.js)]
    FE --> |API Requests| BE[后端 (FastAPI)]
    
    subgraph Backend Core
        BE --> |Route| Router[API 路由层]
        Router --> |Call| Service[服务层 (Task/Project)]
        Service --> |Invoke| Engine[优化引擎 Orchestrator]
    end
    
    subgraph Engine Pipeline
        Engine --> Phase1[1. 诊断与意图分析]
        Phase1 --> Phase2[2. 策略匹配 (Matcher)]
        Phase2 --> Phase3[3. 候选生成 (Generator)]
        Phase3 --> Phase4[4. 最优选择 (Selector)]
        Phase4 --> Phase5[5. 验证与迭代 (Validator)]
    end
    
    subgraph Infrastructure
        Service --> |ORM| DB[(SQLite)]
        Engine --> |LLM API| OpenAI[OpenAI/LLM]
        Engine --> |Logs| Log[Loguru Files]
    end
```

## 🧩 核心模块详解

### 1. 优化引擎 (Engine Core) - `backend/app/engine`
这是系统的核心大脑，采用**流水线 (Pipeline)** 设计模式。核心类 `MultiStrategyOptimizer` 负责协调各个组件。

#### 核心优化链路 (Pipeline Flow)
1.  **初始化 (Initialization)**:
    - 构建 `OptimizationContext`，封装当前提示词、错误样例、历史记录等上下文信息。
2.  **诊断与分析 (Diagnosis & Analysis)**:
    - **意图分析 (`IntentAnalyzer`)**: 识别 Prompt 的核心指令意图。
    - **高级诊断 (`AdvancedDiagnoser`)**: 分析错误样例的共性模式 (Pattern Recognition)。
    - **多意图检测**: 若发现 Prompt 包含冲突意图，自动切换至 `MultiIntentOptimizer` 分流处理。
3.  **策略匹配 (Strategy Matching)**:
    - `StrategyMatcher` 依据诊断结果，动态从策略库 (`strategies/`) 中匹配最合适的优化策略（如：Few-Shot 注入、COT 推理增强、结构化重写等）。
4.  **候选生成 (Candidate Generation)**:
    - `CandidateGenerator` 并发执行匹配到的策略，通过 LLM 生成多个优化后的 Prompt 候选版本。
5.  **评估与选择 (Evaluation & Selection)**:
    - `PromptEvaluator` 对生成的候选版本进行评分（维度：准确性、鲁棒性、简洁性）。
    - 选出综合得分最高的 Top-1 版本。
6.  **验证 (Validation)**:
    - `PromptValidator` 使用独立的验证集或 LLM 模拟测试，确保新 Prompt 未引入新的 Regression。

### 2. 业务服务层 (Services) - `backend/app/services`
负责将 Engine 的能力封装为业务逻辑。
- **`task_service.py`**: 管理优化任务的生命周期（创建、排队、执行中、完成/失败）。负责调用 Engine 并更新数据库状态。
- **`project_service.py`**: 管理项目维度的配置、数据集和历史版本。

### 3. 数据层 (Data Persistence)
- **Database**: 使用 `SQLModel` (基于 SQLAlchemy) 操作 SQLite 数据库。
- **Artifacts**: 优化过程中的中间产物、日志文件存储在本地文件系统。

### 4. 前端 (Frontend)
- **状态管理**: 使用 React Hooks + Context 管理全局状态。
- **实时反馈**: 轮询或 WebSocket 获取后端任务日志，在 UI 上实时展示优化进度条 (Progress Bar) 和当前阶段 (Current Phase)。
