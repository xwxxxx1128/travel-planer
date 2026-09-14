# 聚焦智能多景点旅行规划 Agent 系统

> 一个面向复杂旅行规划场景的 **LLM Agent 应用**：基于 LangGraph 编排多子 Agent，完成多景点行程排序与规划、酒店/餐饮推荐、航班/游览预订（数据库模拟）、地图路线规划、景点评价/攻略实时检索，并提供 Vue3 + FastAPI 全栈实现与 Docker 一键部署。

![行程规划演示](docs/demo.gif)

---

## 目录

- [1. 项目亮点（适合 AI 应用 / Agent 开发岗位）](#1-项目亮点适合-ai-应用--agent-开发岗位)
- [2. 功能特性](#2-功能特性)
- [3. 技术栈](#3-技术栈)
- [4. 目录结构](#4-目录结构)
- [5. 环境要求](#5-环境要求)
- [6. 快速开始](#6-快速开始)
  - [6.1 配置服务密钥](#61-配置服务密钥)
  - [6.2 启动后端](#62-启动后端)
  - [6.3 启动前端](#63-启动前端)
  - [6.4 后端直接托管前端页面](#64-后端直接托管前端页面)
- [7. Docker Compose 一键部署](#7-docker-compose-一键部署)
- [8. 环境变量说明](#8-环境变量说明)
- [9. 核心架构](#9-核心架构)
- [10. 常用接口](#10-常用接口)
- [11. 测试](#11-测试)
- [12. 后续规划](#12-后续规划)
- [13. License](#13-license)

---

## 1. 项目亮点（适合 AI 应用 / Agent 开发岗位）

| 亮点 | 说明 |
| --- | --- |
| **多 Agent 协作编排** | 基于 LangGraph 构建主助理 + 航班改签、酒店预订、游览预订子图，支持工具调用、状态共享与子 Agent 委托。 |
| **ReAct + Tool Calling** | 主助理通过 `bind_tools` 动态调用搜索、地图、航班、酒店、评价等工具，实现“思考 → 行动 → 观察”闭环。 |
| **实时联网检索（Tavily）** | 景点评价/攻略通过 Tavily MCP 实时联网检索，命中评价意图时确定性预检索，避免大模型凭记忆编造。 |
| **RAG 向量检索** | 政策 FAQ 基于 OpenAI Embeddings + Chroma 向量库检索；POI/评论类知识通过 Chroma 集合增量补充。 |
| **MCP 协议扩展** | 路线规划、网页搜索等能力以 MCP Server 形态暴露，可被 Claude Desktop / Cursor / 自研 Agent 复用。 |
| **Human-in-the-Loop** | 航班预订/取消等敏感操作触发中断，前端二次确认后继续执行，确保关键写操作可控。 |
| **流式交互体验** | 对话采用 SSE 节点级流式输出，首字秒级出现；地图页支持实时路线规划与可视化。 |
| **运行时配置中心** | 大模型 Key / 模型名 / Temperature、高德 Key、Tavily Key 等均可在前端「个人信息 / 服务配置」页维护，持久化到服务端，无需每次登录重填。 |
| **全栈工程化** | FastAPI + SQLAlchemy + Vue3 + Vite + Element Plus + Pinia，支持 Docker Compose 一键部署。 |

---

## 2. 功能特性

- **智能行程规划**：输入目的地与偏好，Agent 自动完成多景点排序、分天规划、时间窗与交通方式权衡。
- **酒店 / 餐饮 / POI 推荐**：结合高德地图实时 POI 与向量知识库，给出目的地周边住宿、餐饮、景点建议。
- **航班数据查询与操作**：内置航班/机场本地数据库，支持查询、改签、取消等操作（敏感操作需人工确认）。
- **地图与路线规划**：集成高德地图 API，提供地理编码、路径规划、TSP 多目的地优化与可视化展示。
- **景点攻略 / 评价检索**：基于 Tavily 联网搜索 + 本地 30 天缓存，支持“数据库优先、未命中再联网”的评价查询。
- **对话式交互前端**：Vue3 单页应用，支持历史记录持久化、流式输出、敏感操作二次确认。
- **可观测性**：统一日志、健康检查、结构化运行期配置管理。

---

## 3. 技术栈

| 层 | 技术 |
| --- | --- |
| 后端框架 | FastAPI + Uvicorn |
| Agent 编排 | LangGraph / LangChain / LangChain-OpenAI |
| 向量检索 | Chroma + OpenAI Embeddings |
| 网页搜索 | Tavily MCP |
| 地图服务 | 高德地图 Web API / JS API |
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Vue Router |
| 数据持久化 | SQLAlchemy（SQLite / PostgreSQL） |
| 部署 | Docker / Docker Compose |

---

## 4. 目录结构

```text
trip_assistant_L/
├─ app/                      # 后端主工程
│  ├─ api/                   # 接口层（routers 与各路由实现）
│  ├─ core/                  # 配置（config / runtime_config）
│  ├─ db/                    # 数据库连接与初始化
│  ├─ graph/                 # LangGraph 编排入口
│  ├─ models/                # ORM 模型
│  ├─ schemas/               # Pydantic 请求/响应模型
│  ├─ services/              # 业务服务（聊天、调度、知识库）
│  └─ tools/                 # 图状态等辅助
├─ graph_chat/               # LangGraph 子图 / Agent 定义
├─ tools/                    # 外部工具封装
│  ├─ amap_tools.py          # 高德地图
│  ├─ flights_tools.py       # 航班查询
│  ├─ hotels_tools.py        # 酒店推荐
│  ├─ reviews_tools.py       # 评论检索（含本地缓存）
│  ├─ route_planner.py       # 路线规划
│  ├─ weather_tools.py       # 天气查询
│  ├─ mcp_tavily_client.py   # Tavily MCP 客户端
│  ├─ mcp_route_server.py    # 路线规划 MCP Server
│  └─ retriever_vector.py    # 向量检索
├─ frontend/                 # Vue3 + Vite + Element Plus 前端
├─ tests/                    # pytest 测试
├─ main.py                   # 后端启动入口
├─ docker-compose.yml        # 容器编排
├─ requirements.txt          # Python 依赖
└─ .env.example              # 环境变量模板
```

---

## 5. 环境要求

- Python 3.11+
- Node.js 20+
- Docker / Docker Compose（可选，用于容器化部署）

---

## 6. 快速开始

### 6.1 配置服务密钥

项目支持两种配置方式（优先级：前端运行时配置 > 根目录 `.env`）：

1. **推荐**：启动后访问 `http://127.0.0.1:8000/ui`，进入「个人信息 / 服务配置」页面填写并保存。
2. **备用**：复制 `.env.example` 为 `.env` 并填入密钥：

```bash
cp .env.example .env
# 编辑 .env 填入 OPENAI_API_KEY / 高德 Key / Tavily Key 等
```

### 6.2 启动后端

```bash
pip install -r requirements.txt
python main.py
```

后端启动后：

- 接口文档（Swagger）：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/health`
- 前端页面（若已构建）：`http://127.0.0.1:8000/ui`

> `main.py` 启动时会自动检测 `frontend/dist`，若不存在会尝试执行一次 `npm run build`。

### 6.3 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务默认访问：`http://127.0.0.1:5173`。

### 6.4 后端直接托管前端页面

```bash
cd frontend
npm run build
cd ..
python main.py
```

存在 `dist` 时，根路径 `/` 会重定向到 `/ui` 返回前端页面。

---

## 7. Docker Compose 一键部署

```bash
docker compose up --build
```

启动后：

- 后端：`http://127.0.0.1:8000`
- 前端：`http://127.0.0.1:3000`
- Chroma：`http://127.0.0.1:8001`

> 容器通过 `env_file: .env` 读取环境变量；数据库与向量库持久化目录已被 `.gitignore` 忽略。

---

## 8. 环境变量说明

根目录 `.env` 支持的变量（详见 `.env.example`）：

```env
# OpenAI 兼容大模型
OPENAI_API_KEY=你的Key
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
OPENAI_MODEL=deepseek-ai/DeepSeek-V3
OPENAI_TEMPERATURE=0.2

# 高德地图
AMAP_WEB_KEY=你的Web服务Key
AMAP_JS_KEY=你的JS地图Key
VITE_AMAP_JS_API_KEY=你的JS地图Key

# Tavily 网页搜索
TAVILY_API_KEY=你的TavilyKey
TAVILY_MCP_COMMAND=tavily-mcp

# 数据库 / 向量库
DATABASE_URL=sqlite:///./system.db
CHROMA_PERSIST_DIR=./chroma_db

# JWT 密钥
SECRET_KEY=随机字符串
```

> 上述配置均可在前端「个人信息 / 服务配置」页维护，保存后写入 `.env` 并立即更新 `os.environ`，无需手动改文件。

---

## 9. 核心架构

```text
用户提问
   │
   ▼
[ 入口意图识别 ] ── 评价/攻略类问题 ──► [ 确定性预检索：DB → Tavily → 写库 ]
   │                                          │
   │                                          ▼
   ▼                                [ 材料注入对话上下文 ]
[ LangGraph 主助理 ]
   │
   ├── 工具调用 ──► search_reviews / amap_search_poi / search_flights ...
   │
   ├── 子 Agent 委托 ──► 航班改签 / 酒店预订 / 游览预订子图
   │
   └── 敏感操作 ──► 中断等待前端二次确认（Human-in-the-Loop）
   │
   ▼
[ SSE 流式输出 ] ──► 前端展示
```

---

## 10. 常用接口

所有接口前缀为 `/api`：

- `POST /api/auth/register`：注册
- `POST /api/auth/login`：登录
- `GET /api/auth/me`：当前用户信息
- `GET /api/config/runtime`：读取运行时配置
- `POST /api/config/runtime`：保存运行时配置
- `POST /api/chat/stream`：流式对话
- `POST /api/travel/plan`：生成行程
- `GET /api/maps/search`：POI 搜索
- `POST /api/maps/route`：路线规划

完整接口列表见运行后的 `http://127.0.0.1:8000/docs`。

---

## 11. 测试

```bash
pytest -q tests
```

---

## 12. 后续规划

- 按目的地触发自动爬取并同步向量库。
- 更细粒度的多子 Agent 工具路由与降级策略。
- 前端地图可视化与对话体验增强。
- 引入 Agent 执行轨迹记录与可观测性面板。

---

## 13. License

本项目仅供学习与研究使用。
