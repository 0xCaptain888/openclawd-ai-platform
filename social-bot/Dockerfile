FROM python:3.11-slim

LABEL maintainer="social-bot" \
      description="社交媒体内容生成机器人"

WORKDIR /app

# 系统依赖（精简层）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 环境变量默认值
ENV LLM_API_URL=http://localhost:8000/v1 \
    MODEL_NAME=auto \
    LLM_TIMEOUT=120

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2", "--log-level", "info"]
