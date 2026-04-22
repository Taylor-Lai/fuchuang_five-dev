# 智汇文枢 · DocNexus

基于 FastAPI 的文档智能处理平台，提供三大核心能力：

| 模块 | 接口 | 功能 |
|---|---|---|
| 模块一 | `POST /doc-chat/upload` | 自然语言驱动的 Word 文档格式化 |
| 模块二 | `POST /doc-extract/upload` | 从文档中提取结构化字段信息 |
| 模块三 | `POST /table-fill/upload` | 多智能体跨文档自动填表（xlsx / docx）|

---

## 环境要求

- Python 3.11+
- 需要一个 **OpenAI 兼容的 LLM API**（模块三必需）
  - 推荐：阿里云百炼（`qwen-max`）、智谱 GLM-4、OpenAI
  - 申请地址：https://dashscope.console.aliyun.com（阿里云，免费额度）

---

## 本地部署步骤

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd ai_core && pip install -e . && cd ..
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# LLM 提供商选择：openai 或 zhipu
LLM_PROVIDER=openai

# 模块一、二（使用智谱时填写）
ZHIPU_API_KEY=your_zhipu_api_key

# 模块三 AI 核心（填写任意 OpenAI 兼容接口）
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-max

# JWT 密钥（随意填写一个字符串）
SECRET_KEY=any_random_string
```

> 注：模块三的规则提取能力**不调用 LLM**，无需 API Key 即可验证基础填表效果。
> 只有 LLM Skill 增强路径才需要有效 API Key。

### 3. 启动服务

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动成功后访问：`http://localhost:8000/docs`（Swagger UI，可直接操作所有接口），但Swagger UI系统存在bug，推荐测试时使用下面具体的测试方法进行。

### 4. Docker 部署（可选）

```bash
docker build -t docnexus .
docker run -p 8000:8000 --env-file .env docnexus
```

---

## 测试方法一：Postman（推荐）

使用 Postman 测试所有核心接口，步骤如下：

### 模块一：智能操作文档(自然语言)

**接口：** `POST /doc-chat/upload`

1. 方法：`POST`
2. URL：`http://localhost:8000/doc-chat/upload`
3. `Body` → `form-data`
4. 添加参数：
   - `command`：自然语言格式指令
   - `document`：选择 `File` 类型，上传任意 `.docx` 文件

**指令示例：**
- "把第一段文字加粗并设置为红色"
- "将所有标题字号改为16号"
- "把第二段文字居中对齐"

返回：格式修改后的 Word 文件（自动下载）

---

### 模块二：信息提取

**接口：** `POST /doc-extract/upload`

1. 方法：`POST`
2. URL：`http://localhost:8000/doc-extract/upload`
3. `Body` → `form-data`
4. 添加参数：
   - `file`：选择 `File` 类型，上传文档（docx / txt）
   - `target_entities`：要提取的字段，逗号分隔，如 `姓名,年龄,职位`

返回：JSON 格式的提取结果

---

### 模块三：多智能体填表（核心功能）

**接口：** `POST /table-fill/upload`

1. 方法：`POST`
2. URL：`http://localhost:8000/table-fill/upload`
3. `Body` → `form-data`
4. 添加参数：
   - `template`：选择 `File` 类型，上传模板文件
   - `documents`：选择 `File` 类型，上传源文档（可多次添加）
   - `user_request`：用户要求（可选）

#### 场景 A：COVID-19 数据集（xlsx → xlsx）

```
模板文件（template）：  COVID-19 模板.xlsx
源文件（documents）：   COVID-19全球数据集（节选）.xlsx
                        中国COVID-19新冠疫情情况.docx
用户要求（user_request）：复制 用户要求.txt 的内容粘贴
```

预期结果：返回填好的 Excel，包含 2000+ 条国家数据记录。

#### 场景 B：山东环境监测（xlsx → docx 模板）

```
模板文件（template）：  2025山东省环境空气质量监测数据信息-模板.docx
源文件（documents）：   山东省环境空气质量监测数据信息202512171921_0.xlsx
用户要求（user_request）：复制 用户要求.txt 的内容粘贴
```

预期结果：返回填好的 Word 文档，含三张监测站数据表（德州市/潍坊市/临沂市，共 79 条）。

#### 场景 C：城市经济百强（docx → xlsx）

```
模板文件（template）：  2025年中国城市经济百强全景报告-模板.xlsx
源文件（documents）：   2025年中国城市经济百强全景报告.docx（纯叙述型文档）
用户要求（user_request）：复制 用户要求.txt 的内容粘贴
```

预期结果：返回填好的 Excel，含 90+ 个城市的 GDP、人口、人均 GDP、预算收入。

---

## 测试方法二：curl 命令行

```bash
# 1. 模块一：格式化
curl -X POST http://localhost:8000/doc-chat/upload \
  -F "command=把第一段文字加粗并设置为红色" \
  -F "document=@your_document.docx" \
  --output formatted.docx

# 2. 模块三：填表（山东场景）
curl -X POST http://localhost:8000/table-fill/upload \
  -F "template=@2025山东省环境空气质量监测数据信息-模板.docx" \
  -F "documents=@山东省环境空气质量监测数据信息202512171921_0.xlsx" \
  -F "user_request=完成填表工作，要求提取表格中对应数据" \
  --output result.docx
```

---

## 测试方法三：CLI 本地测试（无需启动服务，无需 API Key）

直接调用 ai_core 流水线，验证核心填表逻辑：

```bash
cd ai_core

# 场景 A：COVID-19
python -m any2table.cli run \
  --path "../测试集/测试集/包含模板文件/COVID-19数据集"

# 场景 B：山东环境监测
python -m any2table.cli run \
  --path "../测试集/测试集/包含模板文件/2025山东省环境空气质量监测数据信息"

# 场景 C：城市经济百强
python -m any2table.cli run \
  --path "../测试集/测试集/包含模板文件/2025年中国城市经济百强全景报告"
```

输出文件保存在各测试集目录的 `outputs/` 子文件夹中。

### 运行单元测试

```bash
cd ai_core
python -m unittest discover -s tests -v
# 预期：44 个测试全部通过
```

---

## 目录结构

```
智汇文枢/
├── main.py                  # FastAPI 路由入口
├── database.py              # 数据库模型与初始化
├── requirements.txt
├── Dockerfile
├── .env                     # 环境变量（需自行创建）
├── services/                # 业务服务层
├── ai_core/                 # 模块三 AI 核心
    ├── engine/              # FastAPI 接入层
    └── src/any2table/       # Any2table 流水线

```

---

## 技术栈

- **后端：** FastAPI + Uvicorn + SQLAlchemy (SQLite)
- **认证：** JWT (python-jose)
- **模块一、二 LLM：** LangChain + Zhipu GLM-4 / OpenAI
- **模块三 AI 核心：** Any2table 多智能体流水线
  - 规则提取：模糊列名匹配（Bigram Jaccard）+ 段落 KV 提取 + 城市经济叙述型提取
  - LLM Skill：paragraph-structuring / table-row-extraction（语义级字段映射）
  - 编排模式：SequentialOrchestrator / MultiAgentOrchestrator（LangGraph）
