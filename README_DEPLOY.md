# AI 统一平台 - 部署指南

## 概述

本平台通过一个 API Gateway 统一管理三个 AI 服务（社交机器人、网站、交易），共享同一个 LLM 后端（vLLM）。

## 前置条件

- **Docker** >= 24.0（含 Docker Compose v2 插件）
- **vLLM 服务**：已在宿主机或可访问的服务器上运行，提供 OpenAI 兼容 API
- **系统资源**：建议最低 4GB 内存（不含 LLM 本身的资源需求）
- **网络**：所有容器需能访问 LLM 服务地址

## 快速启动（3 步）

```bash
# 第一步：进入项目目录
cd ai-platform

# 第二步：运行部署脚本（自动复制配置、构建、启动）
bash scripts/setup.sh

# 第三步：编辑 .env 文件，确认 LLM 地址和 API 密钥配置正确
# 如有修改，重启服务使配置生效：
docker compose restart
```

或者手动操作：

```bash
cp .env.example .env
# 编辑 .env 文件
docker compose up -d
```

## 配置说明

### .env 核心配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_URL` | vLLM 服务地址 | `http://host.docker.internal:8000/v1` |
| `MODEL_NAME` | 模型名称 | `Qwen2-72B-Instruct-GPTQ-Int4` |
| `API_KEYS` | 网关 API 密钥配置 | 见 .env.example |
| `GATEWAY_PORT` | 网关对外端口 | `80` |
| `REDIS_URL` | Redis 连接地址 | `redis://redis:6379/0` |

### API 密钥格式

`API_KEYS` 使用逗号分隔，每个密钥格式为 `key:name:rpm:daily_quota`：

- `key` - 密钥字符串
- `name` - 标识名称
- `rpm` - 每分钟最大请求数
- `daily_quota` - 每日最大请求总数

示例：`sk-admin-001:admin:120:50000,sk-readonly:viewer:30:5000`

## 服务端点列表

所有请求通过 Gateway 统一入口（默认端口 80）：

| 路径 | 目标服务 | 说明 |
|------|----------|------|
| `GET /health` | Gateway | 网关健康检查（无需认证） |
| `GET /stats` | Gateway | 使用统计（需认证） |
| `/v1/*` | vLLM | LLM 推理接口（OpenAI 兼容） |
| `/social/*` | social-bot:8010 | 社交机器人服务 |
| `/website/*` | website-backend:4000 | 网站后端服务 |
| `/trading/*` | trading:8020 | 交易服务 |

### 请求示例

```bash
# 健康检查
curl http://localhost/health

# 调用 LLM（通过网关代理到 vLLM）
curl http://localhost/v1/chat/completions \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-72B-Instruct-GPTQ-Int4",
    "messages": [{"role": "user", "content": "你好"}]
  }'

# 查看使用统计
curl -H "Authorization: Bearer sk-admin-001" http://localhost/stats
```

## 架构图

```
客户端
  │
  ▼
┌────────────────────────────┐
│  API Gateway (:80)         │
│  认证 → 限流 → 路由 → 日志 │
└──┬──────┬──────┬──────┬────┘
   │      │      │      │
   ▼      ▼      ▼      ▼
 vLLM  social  website trading
(外部)  :8010   :4000   :8020
                  │
               frontend
                :3000
         ┌────────────────┐
         │  Redis (:6379) │
         └────────────────┘
```

## 常用运维命令

```bash
# 查看所有服务状态
docker compose ps

# 查看实时日志
docker compose logs -f

# 查看某个服务的日志
docker compose logs -f gateway

# 重启单个服务
docker compose restart trading

# 停止所有服务
docker compose down

# 停止并清除数据卷（慎用）
docker compose down -v

# 重新构建某个服务
docker compose build gateway && docker compose up -d gateway
```

## 常见问题排查

### 1. Gateway 无法连接 vLLM

**症状**：`/v1/*` 请求返回 502

**排查**：
- 确认 vLLM 服务正在运行：`curl http://localhost:8000/v1/models`
- 确认 `.env` 中 `LLM_API_URL` 地址正确
- 如果 vLLM 在宿主机运行，确保使用 `http://host.docker.internal:8000/v1`
- Linux 下 `host.docker.internal` 需要 Docker 20.10+，且 compose 文件已配置 `extra_hosts`

### 2. 服务启动后健康检查失败

**症状**：`docker compose ps` 显示 unhealthy

**排查**：
- 查看服务日志：`docker compose logs <service-name>`
- 确认服务的 Dockerfile 和启动命令正确
- 检查端口是否被占用：`ss -tlnp | grep <port>`

### 3. API 返回 401 Unauthorized

**排查**：
- 确认请求头包含 `Authorization: Bearer <your-key>`
- 确认密钥在 `.env` 的 `API_KEYS` 中已配置
- 重启网关使新密钥生效：`docker compose restart gateway`

### 4. API 返回 429 Rate Limit

**排查**：
- 通过 `/stats` 端点查看当前用量
- 在 `API_KEYS` 中调整对应密钥的 rpm 和 daily_quota 值
- 重启网关生效

### 5. Redis 连接失败

**排查**：
- 确认 Redis 容器正常运行：`docker compose ps redis`
- 确认各服务的 `REDIS_URL` 使用的是容器名 `redis` 而非 `localhost`

## 运行集成测试

```bash
bash scripts/test_all.sh
```

测试脚本会依次检查各服务的健康端点，并报告结果。
