# 智汇文枢

智汇文枢是一个基于 FastAPI 的文档智能处理平台，提供文档格式化、信息提取和多智能体表格自动填写三大核心能力。

## 功能模块

### 模块一：文档智能格式化（`/doc-chat/upload`）

通过自然语言指令对 Word 文档进行格式调整、排版操作，底层由 LangChain + LLM 驱动。

**接口：** `POST /doc-chat/upload`
- `command`：自然语言指令（如"把第一段变成红色字体并加粗"）
- `document`：`.docx` 文件
- 返回处理后的文件（文件流下载）

### 模块二：文档信息提取（`/doc-extract/upload`）

从文档中按指定字段提取结构化信息，结果入库并支持查询。

**接口：**
- `POST /doc-extract/upload`：上传文档并提取
- `GET /doc-extract`：获取提取历史
- `GET /doc-extract/{record_id}`：获取单条记录
- `DELETE /doc-extract/{record_id}`：删除记录

### 模块三：多智能体表格填写（`/table-fill/upload`）

核心模块。将多份源文档中的信息自动填入目标模板（xlsx / docx），由 `ai_core` Any2table 流水线驱动。

**接口：**
- `POST /table-fill/upload`：上传源文档 + 模板 + 用户要求，启动填表任务
- `POST /table-fill/simple`：简化版，仅上传源文档和字段列表，自动生成 Excel

### 其他接口

| 接口 | 说明 |
|---|---|
| `POST /auth/register` | 用户注册 |
| `POST /auth/login` | 用户登录，返回 JWT Token |
| `POST /auth/logout` | 登出 |
| `GET /user/profile` | 获取个人资料 |
| `PUT /user/profile` | 修改个人资料 |
| `GET /admin/user/page` | 管理员：分页查询用户 |
| `GET /admin/statistics` | 管理员：系统统计数据 |

API 完整文档见运行后的 `/docs`（Swagger UI）。

## 技术栈

- **后端框架：** FastAPI + Uvicorn
- **数据库：** SQLAlchemy（默认 SQLite，可切换）
- **认证：** JWT（python-jose）
- **LLM（模块一二）：** LangChain + Zhipu GLM-4 / OpenAI（由 `LLM_PROVIDER` 环境变量控制）
- **AI 核心（模块三）：** `ai_core` Any2table 多智能体流水线（通用规则提取 + LLM Skill 提取 + HybridRAG 证据重排序）

## 安装与运行

### 1. 安装依赖

```bash
pip install -r requirements.txt

# 安装 ai_core
cd ai_core && pip install -e . && cd ..
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# 选择 LLM 提供商：zhipu 或 openai
LLM_PROVIDER=zhipu

# 智谱 AI（模块一、二）
ZHIPU_API_KEY=your_zhipu_api_key

# OpenAI 兼容接口（模块三 / ai_core）
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint
OPENAI_MODEL=gpt-4o-mini

# JWT 密钥
SECRET_KEY=your_secret_key
```

### 3. 启动服务

```bash
uvicorn main:app --reload --port 8000
```

访问 `http://localhost:8000/docs` 查看完整接口文档。

### 4. Docker 部署

```bash
docker build -t zhihui .
docker run -p 8000:8000 --env-file .env zhihui
```

## 目录结构

```
智汇文枢/
├── main.py              # FastAPI 入口，所有路由
├── database.py          # SQLAlchemy 模型与数据库初始化
├── requirements.txt     # Python 依赖
├── Dockerfile
├── services/
│   ├── auth.py          # JWT 认证服务
│   ├── db_service.py    # 数据库操作封装
│   ├── document_parser.py   # 文档解析（上传预处理）
│   ├── llm_extractor.py     # 模块二 LLM 提取器
│   ├── table_filler.py      # 简化版表格填写
│   └── nlp_command_parser.py
└── ai_core/             # 模块三：Any2table 多智能体核心
    ├── engine/          # FastAPI 接入层
    │   ├── engine.py    # handle_module_1/2/3 入口函数
    │   └── schemas.py   # Pydantic 输入模型
    └── src/any2table/   # Any2table 流水线（详见 ai_core/README.md）
```

## ai_core 架构简介

模块三的核心是 `ai_core/src/any2table/` 下的 Any2table 流水线，提供两种编排模式：

- **SequentialOrchestrator**：确定性规则链（默认，稳定）
- **MultiAgentOrchestrator**：7 Agent LangGraph 工作流（可选，语义增强）

主要能力：
- 通用规则提取：模糊列名匹配（子串 + Bigram Jaccard）、段落 KV 提取，适配任意领域数据
- LLM Skill 提取：docx → `paragraph-structuring`，xlsx → `table-row-extraction`，语义级字段映射
- HybridRAG：全量证据按字段相关性重排序，默认启用，复杂任务（3+ 文档 / 5+ 字段）自动激活

详细架构说明见 [ai_core/README.md](ai_core/README.md)。

## 开发说明

- 新增接口：在 `main.py` 中添加路由，复杂业务逻辑放到 `services/` 下
- 扩展 AI 能力：在 `ai_core/src/any2table/` 中添加新的 Agent、Skill（新增 `SKILL.md` 文件即自动注册）或 RAG backend
- 运行 ai_core 单元测试：`cd ai_core && python -m unittest discover -s tests -v`
