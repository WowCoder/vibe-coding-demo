# Talk2Code 架构文档

## 重构后的目录结构

```
backend/
├── app.py                      # Flask 应用入口（精简到 ~400 行）
├── config.py                   # 配置管理
├── models.py                   # 数据库模型
├── requirements.txt            # Python 依赖
├── prompts.py                  # AI Prompt 模板 + Fallback 代码生成
├── diff_utils.py               # Diff 解析工具
├── routes/                     # 路由模块（预留）
│   └── __init__.py
├── services/                   # 业务服务层
│   ├── __init__.py
│   ├── sse_manager.py          # SSE 连接管理器（线程安全）
│   ├── task_queue.py           # 任务队列管理器（控制并发）
│   └── requirement_service.py  # 需求处理服务
├── agents/                     # AI 智能体层
│   ├── __init__.py
│   ├── base_agent.py           # 智能体基类
│   ├── researcher.py           # 研究员智能体
│   ├── product_manager.py      # 产品经理智能体
│   ├── architect.py            # 架构师智能体
│   └── engineer.py             # 工程师智能体
├── llm/                        # LLM 客户端层
│   ├── __init__.py
│   └── client.py               # 统一 LLM 客户端
└── utils/                      # 工具函数层
    ├── __init__.py
    ├── logger.py               # 日志配置
    ├── security.py             # 密码加密
    ├── sse.py                  # SSE 消息格式化
    └── time_utils.py           # 时间工具
```

## 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                      Flask App (app.py)                      │
│                    路由 + 应用初始化                          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Services 业务服务层                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │  SSE Manager    │  │   Task Queue    │  │ Requirement │  │
│  │  (线程安全)      │  │  (并发控制)      │  │   Service   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Agents AI 智能体层                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Researcher  │  │ Product Mgr  │  │  Architect   │       │
│  │   研究员      │  │   产品经理    │  │   架构师      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│  ┌──────────────┐                                           │
│  │   Engineer   │                                           │
│  │   工程师      │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     LLM 客户端层                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  LLMClient (统一客户端，支持流式/非流式/重试/记忆)   │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Utils 工具函数层                           │
│  logger.py  │  security.py  │  sse.py  │  time_utils.py     │
└─────────────────────────────────────────────────────────────┘
```

## 核心改进

### 1. 模块化架构
- **原问题**: `app.py` 单文件 800+ 行，职责混乱
- **改进后**: 按职责拆分到不同模块，每个模块 ~100-200 行

### 2. 线程安全的 SSE 管理
- **原问题**: 全局字典无锁保护，可能竞态条件
- **改进后**: `SSEManager` 单例模式，`RLock` 保护，后台清理线程

### 3. 任务队列控制并发
- **原问题**: 直接 `thread.start()`，无并发限制
- **改进后**: `TaskQueue` 线程池，最多 3 个并发任务

### 4. 统一 LLM 客户端
- **原问题**: `llm_client.py` 和 `langchain_client.py` 功能重叠
- **改进后**: 统一 `LLMClient`，支持流式/非流式/自动重试/会话记忆

### 5. 智能体抽象
- **原问题**: 智能体逻辑分散在函数中
- **改进后**: `BaseAgent` 基类，4 个子类，统一接口

### 6. 日志系统
- **原问题**: 使用 `print()` 记录日志
- **改进后**: 统一 `logging` 模块，结构化日志

## 数据流

### 需求处理流程

```
用户提交需求
    │
    ▼
POST /api/requirements
    │
    ▼
创建 Requirement 记录 (status='pending')
    │
    ▼
提交到 TaskQueue
    │
    ▼
TaskQueue.submit(requirement_id, process_requirement_async)
    │
    ▼
┌─────────────────────────────────────────────────┐
│           RequirementService.process()          │
│                                                 │
│  1. Researcher → 输出市场分析                   │
│  2. ProductManager → 输出功能清单               │
│  3. Architect → 输出技术架构                    │
│  4. Engineer → 输出代码 (JSON)                  │
│                                                 │
│  每一步通过 SSE Manager 推送进度/对话消息        │
└─────────────────────────────────────────────────┘
    │
    ▼
更新 Requirement (status='finished')
    │
    ▼
SSE 发送 complete 事件
```

### SSE 推送流程

```
前端 EventSource 连接 /api/sse/<req_id>
    │
    ▼
SSEManager.add_client(client_id, queue)
    │
    ▼
后台线程监听队列
    │
    ▼
智能体调用 → SSEManager.broadcast() → 队列.put()
    │
    ▼
前端接收 event: dialogue/code/progress/complete
    │
    ▼
前端渲染对话/代码/进度
```

## 配置说明

### 环境变量 (.env)

```bash
# 阿里云百炼 API Key（必需）
DASHSCOPE_API_KEY=your_api_key

# 模型选择（可选）
DASHSCOPE_MODEL=qwen-plus

# JWT 密钥（生产环境必须修改）
JWT_SECRET_KEY=your-secret-key
```

### 日志级别

```python
# 设置全局日志级别
from utils.logger import set_global_level, INFO, DEBUG
set_global_level(DEBUG)
```

## 扩展指南

### 添加新的智能体

1. 在 `agents/` 目录创建新文件，如 `agents/tester.py`
2. 继承 `BaseAgent` 类
3. 实现 `system_prompt()`、`build_user_prompt()`、`_call_llm()`、`get_fallback_response()`

```python
from agents.base_agent import BaseAgent, AgentContext

class TesterAgent(BaseAgent):
    name = "测试工程师"
    agent_type = "tester"

    def system_prompt(self) -> str:
        return "你是一位测试工程师..."

    def build_user_prompt(self, context: AgentContext) -> str:
        return f"请为以下需求生成测试用例：{context.requirement_content}"

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        # 调用 LLM
        pass

    def get_fallback_response(self, context: AgentContext) -> str:
        return "测试用例fallback..."
```

### 添加新的路由

推荐在 `routes/` 目录创建独立路由文件：

```python
# routes/api.py
from flask import Blueprint

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/health')
def health():
    return {'status': 'ok'}
```

然后在 `app.py` 注册：

```python
from routes.api import api
app.register_blueprint(api)
```

## 待改进事项

### 阶段二（稳定性提升）
- [ ] 添加 Pydantic 配置验证
- [ ] 实现指数退避重试
- [ ] 添加代码生成 Schema 校验

### 阶段三（功能增强）
- [ ] API 限流（flask-limiter）
- [ ] 前端重构（Vue.js/React）
- [ ] 单元测试覆盖

## 版本历史

### v2.0 (重构版)
- ✅ 模块化架构
- ✅ 线程安全 SSE 管理
- ✅ 任务队列并发控制
- ✅ 统一 LLM 客户端
- ✅ 智能体抽象
- ✅ 日志系统

### v1.0 (原始版)
- 单文件 Flask 应用
- 基础 SSE 推送
- 简单 AI 智能体
