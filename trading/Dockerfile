FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 环境变量默认值
ENV LLM_API_URL=http://localhost:11434/v1/chat/completions
ENV MODEL_NAME=qwen2.5
ENV HOST=0.0.0.0
ENV PORT=8000

EXPOSE 8000

# 启动服务（同时提供API和前端页面）
CMD ["sh", "-c", "uvicorn app:app --host ${HOST} --port ${PORT}"]
