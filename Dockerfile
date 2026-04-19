# 使用 Python 3.11 镜像
FROM python:3.11-slim as backend

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖（使用国内镜像源加速）
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 安装 ai_core
RUN pip install -e ai_core -i https://pypi.tuna.tsinghua.edu.cn/simple

# 构建前端
FROM node:20 as frontend
WORKDIR /app/FE/FE
COPY FE/FE/package.json .
COPY FE/FE/package-lock.json .
RUN npm install --registry=https://registry.npmmirror.com
COPY FE/FE .
RUN npm run build

# 最终镜像
FROM python:3.11-slim
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 从后端阶段复制项目代码
COPY --from=backend /app /app

# 安装 ai_core
RUN pip install -e ai_core -i https://pypi.tuna.tsinghua.edu.cn/simple

# 从前端阶段复制构建产物
COPY --from=frontend /app/FE/FE/dist /app/static

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]