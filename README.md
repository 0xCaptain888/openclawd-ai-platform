# OpenClawd AI 统一平台

> **在线文档**：[https://0xcaptain888.github.io/openclawd-ai-platform/](https://0xcaptain888.github.io/openclawd-ai-platform/)
>
> 包含 [部署与运维指南](https://0xcaptain888.github.io/openclawd-ai-platform/deployment-guide.html) 和 [API 使用手册](https://0xcaptain888.github.io/openclawd-ai-platform/api-manual.html)

一站式 AI 服务平台，通过统一的 API 网关管理三大业务服务 —— **社交媒体机器人**、**智能网站**、**交易助手** —— 共享同一个本地 LLM 后端（vLLM / Ollama / LocalAI），无需任何外部 API 依赖。

---

## 目录

- [平台概述](#平台概述)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [前置条件](#前置条件)
- [快速启动](#快速启动)
- [环境配置详解](#环境配置详解)
- [服务详细说明](#服务详细说明)
  - [API 网关](#1-api-网关-gateway)
  - [社交媒体机器人](#2-社交媒体机器人-social-bot)
  - [智能网站](#3-智能网站-website)
  - [交易助手](#4-交易助手-trading)
  - [Redis](#5-redis-缓存与队列)
- [API 端点完整列表](#api-端点完整列表)
- [请求示例](#请求示例)
- [项目目录结构](#项目目录结构)
- [运维命令速查](#运维命令速查)
- [集成测试](#集成测试)
- [自定义与扩展](#自定义与扩展)
- [常见问题排查](#常见问题排查)
- [相关文档](#相关文档)

---

## 平台概述

本平台专为 **本地化 AI 部署** 设计。核心理念：

- **一个 LLM，多个业务**：所有服务共享同一个本地大模型后端，通过 OpenAI 兼容 API 通信，更换模型无需修改任何业务代码
- **统一入口**：所有外部请求经由 API 网关，统一认证、限流、路由、审计
- **即插即用**：只需配置 `LLM_API_URL` 指向你的本地模型服务，一条命令启动全部服务
- **完全本地化**：不依赖任何外部云 API，数据完全留在本地

### 核心能力一览

| 服务 | 能力 |
|------|------|
| 社交机器人 | 10 个平台的内容生成、改写、视频脚本、批量发布、定时调度 |
| 智能网站 | AI 客服聊天（RAG 知识库）、SEO 文章生成、Meta 标签生成、产品描述、FAQ 生成、多语言翻译 |
| 交易助手 | 14 种技术指标、AI 市场分析、多指标信号引擎、策略回测、K线仪表盘 |
| API 网关 | Bearer 认证、每密钥限流（RPM + 每日配额）、请求代理、JSONL 审计日志 |

---

## 系统架构

```
                         ┌──────────────┐
                         │    客户端     │
                         └──────┬───────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │        API Gateway (:80)             │
              │                                     │
              │  Bearer 认证 → 限流 → 路由 → 审计日志 │
              └──┬────────┬────────┬────────┬───────┘
                 │        │        │        │
          /v1/*  │ /social│/website│/trading│
                 │        │        │        │
                 ▼        ▼        ▼        ▼
              ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐
              │ vLLM │ │Social│ │Web   │ │Trade │
              │(外部) │ │ Bot  │ │Back  │ │ Svc  │
              │      │ │:8010 │ │:4000 │ │:8020 │
              └──────┘ └──────┘ └──┬───┘ └──────┘
                                   │
                                   ▼
                              ┌──────────┐
                              │  Web     │
                              │ Frontend │
                              │  :3000   │
                              └──────────┘

              ┌─────────────────────────────────────┐
              │          Redis (:6379)               │
              │  任务队列 · 调度器 · 缓存 · 限流计数   │
              └─────────────────────────────────────┘
```

**数据流说明**：
1. 客户端发送请求到网关（默认端口 80）
2. 网关验证 API 密钥，检查速率限制
3. 根据路径前缀路由到对应后端服务
4. 后端服务处理业务逻辑，需要时调用 LLM API
5. 响应原路返回，网关记录审计日志

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.11+) |
| 前端 | HTML5 + TailwindCSS + 原生 JS |
| 容器化 | Docker + Docker Compose |
| 缓存/队列 | Redis 7 (Alpine) |
| HTTP 客户端 | httpx (异步) |
| 数据验证 | Pydantic v2 |
| 任务调度 | APScheduler |
| 前端服务器 | Nginx |
| LLM 接口 | OpenAI 兼容 API (chat/completions) |

---

## 前置条件

- **Docker** >= 24.0（含 Docker Compose v2 插件）
- **本地 LLM 服务**：已在宿主机或可访问的服务器上运行，提供 OpenAI 兼容 API
  - 推荐: [vLLM](https://github.com/vllm-project/vllm)、[Ollama](https://ollama.ai)、[LocalAI](https://localai.io)
- **系统资源**：建议最低 4GB 内存（不含 LLM 本身的资源需求）
- **网络**：所有容器需能访问 LLM 服务地址

---

## 快速启动

### 方式一：自动化脚本（推荐）

```bash
# 克隆仓库
git clone https://github.com/0xCaptain888/openclawd-ai-platform.git
cd openclawd-ai-platform

# 运行部署脚本（自动复制配置、构建镜像、启动服务、健康检查）
bash scripts/setup.sh

# 编辑 .env，确认 LLM 地址正确后重启
vim .env
docker compose restart
```

### 方式二：手动操作

```bash
git clone https://github.com/0xCaptain888/openclawd-ai-platform.git
cd openclawd-ai-platform

# 1. 创建配置文件
cp .env.example .env

# 2. 修改关键配置
# - LLM_API_URL: 指向你的本地 LLM 服务
# - API_KEYS: 设置你的 API 密钥
vim .env

# 3. 构建并启动所有服务
docker compose up -d

# 4. 检查服务状态
docker compose ps

# 5. 验证网关健康
curl http://localhost/health
```

---

## 环境配置详解

所有配置通过 `.env` 文件管理，参考 `.env.example`。

### 核心配置项

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_URL` | 本地 LLM 服务地址（OpenAI 兼容） | `http://host.docker.internal:8000/v1` |
| `MODEL_NAME` | 模型名称标识符 | `Qwen2-72B-Instruct-GPTQ-Int4` |
| `GATEWAY_PORT` | 网关对外映射端口 | `80` |
| `REDIS_URL` | Redis 连接地址 | `redis://redis:6379/0` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### API 密钥配置

`API_KEYS` 使用逗号分隔多个密钥，每个密钥格式为：

```
key:name:rpm:daily_quota
```

| 字段 | 说明 |
|------|------|
| `key` | 密钥字符串（用于 Bearer 认证） |
| `name` | 密钥标识名称（用于日志和统计） |
| `rpm` | 每分钟最大请求数 (Requests Per Minute) |
| `daily_quota` | 每日最大请求总数 |

示例：
```bash
API_KEYS=sk-admin-001:admin:120:50000,sk-social-001:social-bot:60:20000,sk-web-001:website:60:20000,sk-trade-001:trading:30:10000
```

### 服务间认证密钥

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SOCIAL_BOT_API_KEY` | 社交机器人内部密钥 | `sk-social-internal-001` |
| `WEBSITE_BACKEND_API_KEY` | 网站后端内部密钥 | `sk-web-internal-001` |
| `TRADING_API_KEY` | 交易服务内部密钥 | `sk-trade-internal-001` |

---

## 服务详细说明

### 1. API 网关 (Gateway)

**端口**: 80（对外）
**代码**: `gateway/app.py` (287 行)

统一请求入口，所有外部流量必须经过网关。

**核心功能**：

| 功能 | 实现方式 |
|------|---------|
| **认证** | Bearer Token，支持 Header (`Authorization: Bearer <key>`) 和 Query (`?api_key=<key>`) 两种方式 |
| **限流** | 内存计数器，每密钥独立的 RPM 限制和每日配额，UTC 午夜自动重置 |
| **路由** | 基于路径前缀匹配：`/v1` → LLM, `/social` → 社交机器人, `/website` → 网站后端, `/trading` → 交易服务 |
| **审计** | 每次请求写入 JSONL 日志文件，记录时间戳、密钥名、方法、路径、上游地址、状态码、耗时、IP |
| **统计** | `/stats` 端点实时查看每个密钥的用量：总请求数、错误数、RPM 使用量、日配额使用量 |
| **跨域** | CORS 全开放（生产环境建议限制 `allow_origins`） |
| **超时** | 上游请求超时 120 秒，连接超时 10 秒 |

**路由映射表**：

| 路径前缀 | 目标服务 | 上游地址 |
|---------|---------|---------|
| `/v1` | 本地 LLM (vLLM) | `LLM_API_URL` 环境变量 |
| `/social` | 社交机器人 | `http://social-bot:8010` |
| `/website` | 网站后端 | `http://website-backend:4000` |
| `/trading` | 交易服务 | `http://trading:8020` |

---

### 2. 社交媒体机器人 (Social Bot)

**端口**: 8010（内部）
**代码**: `social-bot/app.py` (399 行) + `social-bot/scheduler.py` (336 行)

基于 LLM 的多平台社交媒体内容自动生成系统。

#### 支持平台（10 个）

| 平台 | 标识符 | 内容特点 |
|------|--------|---------|
| 小红书 | `xiaohongshu` | 种草文案、生活分享、标题党 |
| 抖音 | `douyin` | 短视频脚本文案、口播稿 |
| 微博 | `weibo` | 话题热点、短文案、评论互动 |
| Twitter/X | `twitter` | 推文、Thread 长文 |
| Instagram | `instagram` | 图文配文、Reel 文案、标签 |
| 知乎 | `zhihu` | 专业深度长文、问答体 |
| B站 | `bilibili` | 年轻化视频文案、弹幕互动风格 |
| TikTok | `tiktok` | 国际版短视频、英文 trending |
| LinkedIn | `linkedin` | 职场思想领袖、行业洞察 |
| YouTube | `youtube` | SEO 优化视频脚本、描述和标签 |

#### 提示词工程

每个平台都有独立的系统提示词文件（位于 `social-bot/prompts/` 目录），包含：
- 平台特有的写作风格和格式要求
- 字数限制和排版规范
- 标签/话题策略
- 互动引导技巧

额外提供 `rewrite.txt`（内容改写）和 `video_script.txt`（视频分镜脚本）两个通用提示词。

#### 任务调度器

`scheduler.py` 基于 APScheduler 实现：
- 支持 Cron 表达式、固定间隔、一次性定时三种触发方式
- 优先使用 Redis 队列存储任务（自动降级到内存队列）
- 任务状态追踪（待执行、执行中、已完成、失败）

---

### 3. 智能网站 (Website)

#### 前端

**端口**: 3000（内部）
**代码**: `website/frontend/index.html` (248 行) + `website/frontend/static/chat.js` (217 行)

- TailwindCSS 响应式布局
- 深色/浅色主题切换
- 内嵌 AI 聊天组件（右下角浮窗）
- 打字机动画效果
- Nginx 静态资源服务，`/api/` 路径代理到后端

#### 后端

**端口**: 4000（内部）
**代码**: `website/backend/app.py` (376 行) + `website/backend/knowledge_base.py`

| 功能 | 端点 | 说明 |
|------|------|------|
| AI 聊天 | `POST /api/chat` | 支持对话历史（最近 10 轮）、自动 RAG 上下文注入 |
| SEO 文章 | `POST /api/seo/generate` | 指定主题、关键词、语气、长度（300/600/1200 词） |
| Meta 标签 | `POST /api/seo/meta` | 生成 title（<60 字符）和 description（<160 字符） |
| 产品描述 | `POST /api/content/product-description` | 面向转化的产品文案，可指定受众和语气 |
| FAQ 生成 | `POST /api/content/faq` | 自动生成 1-20 组 Q&A |
| 多语言翻译 | `POST /api/translate` | 支持自动语言检测，低温度精确翻译 |

#### RAG 知识库

`knowledge_base.py` 提供简单但有效的检索增强生成：
- 加载 `knowledge/` 目录下的 `.txt` / `.md` 文件
- 基于关键词匹配的文档检索（中英文支持）
- 检索结果自动注入到 LLM 系统提示词中
- 预置知识文件：公司信息、产品目录、物流政策、示例文档
- API 设计兼容升级到向量数据库（ChromaDB / FAISS / Pinecone），无需改动接口

---

### 4. 交易助手 (Trading)

**端口**: 8020（内部）
**代码**: `trading/app.py` (298 行) + `trading/indicators.py` (842 行) + `trading/analyzer.py` (463 行) + `trading/backtester.py` (392 行)

#### 技术指标（14 种，纯 Python 实现，无需 TA-Lib）

| 类别 | 指标 | 说明 |
|------|------|------|
| **趋势** | SMA (20/50/200) | 简单移动平均线，滑动窗口优化 |
| **趋势** | EMA (12/26) | 指数移动平均线，Wilder 平滑法 |
| **趋势** | ADX (14) | 平均趋向指数 + ±DI 方向指标 |
| **趋势** | Ichimoku Cloud | 一目均衡表（转换线、基准线、先行线A/B、迟行线） |
| **动量** | RSI (14) | 相对强弱指数，Wilder 平滑 |
| **动量** | MACD (12/26/9) | 异同移动平均线 + 信号线 + 柱状图 |
| **动量** | Stochastic (14/3) | 随机震荡指标（%K 和 %D） |
| **动量** | Williams %R (14) | 威廉指标，超买/超卖识别 |
| **动量** | CCI (20) | 商品通道指数 |
| **波动率** | Bollinger Bands (20/2σ) | 布林带，动态支撑阻力 |
| **波动率** | ATR (14) | 平均真实波幅 |
| **成交量** | OBV | 能量潮指标 |
| **成交量** | VWAP | 成交量加权平均价 |
| **价格结构** | Support/Resistance | 局部极值聚类法支撑阻力位检测 |

#### AI 分析引擎

`analyzer.py` 包含两个分析层：

**规则信号引擎**（不依赖 AI，纯规则）：
- 多指标综合评分系统，分值范围 -100 到 +100
- 评分维度：均线趋势、RSI 超买超卖、MACD 交叉、布林带位置、成交量异动
- 输出信号强度和明确的多/空/观望建议

**AI 分析层**（调用 LLM）：
- 将所有指标数据格式化为结构化提示词
- LLM 生成市场综述、趋势判断、关键价位、操作建议
- 支持多时间周期分析报告

#### 策略回测引擎

`backtester.py` 功能：
- 基于技术指标条件的灵活策略定义（支持 `>`, `<`, `cross_above`, `cross_below` 等运算符）
- 入场/出场条件支持 AND/OR 逻辑组合
- 可配置仓位比例、止损、止盈、手续费
- 绩效指标：总收益率、最大回撤、胜率、盈亏比、Sharpe 比率、利润因子
- 输出权益曲线数据（限制 500 点避免响应过大）

#### 交互式仪表盘

`dashboard.html` 提供完整的交易分析 UI：
- ECharts K 线图（支持缩放、拖拽）
- 技术指标叠加显示
- 信号面板和分析结果展示
- 深色主题，专业交易界面风格

#### 示例数据生成

`sample_data.py` 提供 4 种市场场景的模拟数据，方便前端测试：
- `bullish` — 上涨趋势
- `bearish` — 下跌趋势
- `sideways` — 横盘震荡
- `volatile` — 高波动

---

### 5. Redis（缓存与队列）

**端口**: 6379（内部）
**镜像**: `redis:7-alpine`

- 内存限制 256MB，使用 LRU 淘汰策略
- 开启 AOF 持久化
- 各服务共享同一 Redis 实例
- 用途：社交机器人任务队列、调度器状态存储、网关限流计数（未来扩展）

---

## API 端点完整列表

所有请求通过 API 网关，默认端口 80。除 `/health` 外均需认证。

### 网关端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | 否 | 网关健康检查 |
| GET | `/stats` | 是 | 各密钥使用量统计 |

### LLM 代理

| 方法 | 路径 | 说明 |
|------|------|------|
| * | `/v1/*` | 透传到本地 LLM 服务（如 `/v1/chat/completions`、`/v1/models`） |

### 社交机器人端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/social/generate` | 单平台内容生成 |
| POST | `/social/rewrite` | 内容改写（支持风格和平台指定） |
| POST | `/social/video-script` | 视频分镜脚本生成 |
| POST | `/social/batch` | 一个主题批量生成多平台内容 |
| GET | `/social/platforms` | 获取支持的平台列表及描述 |
| GET | `/social/health` | 社交机器人健康检查 |

### 网站端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/website/api/chat` | AI 聊天（支持对话历史和 RAG） |
| POST | `/website/api/seo/generate` | SEO 优化文章生成 |
| POST | `/website/api/seo/meta` | 页面 Meta 标签生成 |
| POST | `/website/api/content/product-description` | 产品描述生成 |
| POST | `/website/api/content/faq` | FAQ 问答生成 |
| POST | `/website/api/translate` | 多语言翻译 |
| GET | `/website/api/health` | 网站后端健康检查 |

### 交易助手端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/trading/api/analyze` | 完整市场分析（指标 + 规则信号 + AI 解读） |
| POST | `/trading/api/indicators` | 计算全部技术指标（纯计算，不调用 AI） |
| POST | `/trading/api/signal` | 获取交易信号（基于规则引擎，不调用 AI） |
| POST | `/trading/api/strategy/backtest` | 策略回测 |
| POST | `/trading/api/report` | AI 综合市场报告（支持多时间周期） |
| GET | `/trading/api/sample-data` | 获取示例 OHLCV 数据 |
| GET | `/trading/api/health` | 交易服务健康检查 |
| GET | `/trading/` | 交易仪表盘页面 |

---

## 请求示例

### 健康检查（无需认证）

```bash
curl http://localhost/health
# 响应: {"status": "ok", "timestamp": "2024-01-01T00:00:00+00:00"}
```

### 查看使用统计

```bash
curl -H "Authorization: Bearer sk-admin-001" http://localhost/stats
```

### 调用本地 LLM（通过网关代理到 vLLM）

```bash
curl http://localhost/v1/chat/completions \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen2-72B-Instruct-GPTQ-Int4",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

### 生成小红书文案

```bash
curl http://localhost/social/generate \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "xiaohongshu",
    "topic": "秋天的第一杯奶茶",
    "language": "zh",
    "temperature": 0.9
  }'
```

### 批量生成多平台内容

```bash
curl http://localhost/social/batch \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "2024年最值得入手的机械键盘",
    "platforms": ["xiaohongshu", "douyin", "weibo", "zhihu", "bilibili"],
    "language": "zh"
  }'
```

### 改写内容

```bash
curl http://localhost/social/rewrite \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "original_content": "今天天气真好，适合出去走走。",
    "target_platform": "xiaohongshu",
    "style": "活泼可爱"
  }'
```

### 生成视频脚本

```bash
curl http://localhost/social/video-script \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "一分钟学会拉花咖啡",
    "duration": "60s",
    "target_platform": "douyin"
  }'
```

### AI 聊天（带知识库检索）

```bash
curl http://localhost/website/api/chat \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你们的退货政策是什么？",
    "history": []
  }'
```

### 生成 SEO 文章

```bash
curl http://localhost/website/api/seo/generate \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "2024年最佳Python学习路径",
    "keywords": ["Python入门", "编程学习", "自学编程"],
    "tone": "friendly",
    "length": "long"
  }'
```

### 生成产品描述

```bash
curl http://localhost/website/api/content/product-description \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "智能降噪耳机 Pro Max",
    "features": ["40dB主动降噪", "36小时续航", "蓝牙5.3", "Hi-Res认证"],
    "tone": "premium",
    "target_audience": "科技爱好者"
  }'
```

### 多语言翻译

```bash
curl http://localhost/website/api/translate \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "人工智能正在改变世界",
    "source_language": "zh",
    "target_language": "en"
  }'
```

### 计算技术指标（不调用 AI）

```bash
# 先获取示例数据
curl http://localhost/trading/api/sample-data?scenario=bullish&num_candles=100 \
  -H "Authorization: Bearer sk-admin-001" \
  -o /tmp/sample.json

# 提取 candles 字段后请求指标计算
curl http://localhost/trading/api/indicators \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{"candles": [...]}'
```

### 获取交易信号（基于规则，不调用 AI）

```bash
curl http://localhost/trading/api/signal \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTC/USDT",
    "candles": [...]
  }'
```

### AI 完整市场分析

```bash
curl http://localhost/trading/api/analyze \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETH/USDT",
    "timeframe": "4h",
    "candles": [...],
    "extra_context": "近期以太坊ETF获批"
  }'
```

### 策略回测

```bash
curl http://localhost/trading/api/strategy/backtest \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{
    "candles": [...],
    "entry_conditions": [
      {"left": "rsi_14", "op": "<", "right": 30},
      {"left": "macd_histogram", "op": "cross_above", "right": 0}
    ],
    "exit_conditions": [
      {"left": "rsi_14", "op": ">", "right": 70}
    ],
    "entry_logic": "and",
    "exit_logic": "or",
    "initial_capital": 100000,
    "stop_loss_pct": 0.03,
    "take_profit_pct": 0.08,
    "commission_pct": 0.001
  }'
```

---

## 项目目录结构

```
openclawd-ai-platform/
│
├── gateway/                          # API 网关服务
│   ├── app.py                       # 认证、限流、路由、审计（287 行）
│   ├── Dockerfile                   # Python 3.11-slim 镜像
│   └── requirements.txt             # fastapi, uvicorn, httpx
│
├── social-bot/                       # 社交媒体机器人服务
│   ├── app.py                       # 主应用，5 个 API 端点（399 行）
│   ├── scheduler.py                 # APScheduler 任务调度器（336 行）
│   ├── prompts/                     # 平台提示词模板目录
│   │   ├── xiaohongshu.txt          # 小红书专用提示词
│   │   ├── douyin.txt               # 抖音专用提示词
│   │   ├── weibo.txt                # 微博专用提示词
│   │   ├── twitter.txt              # Twitter/X 专用提示词
│   │   ├── instagram.txt            # Instagram 专用提示词
│   │   ├── zhihu.txt                # 知乎专用提示词
│   │   ├── bilibili.txt             # B站专用提示词
│   │   ├── tiktok.txt               # TikTok 专用提示词
│   │   ├── linkedin.txt             # LinkedIn 专用提示词
│   │   ├── youtube.txt              # YouTube 专用提示词
│   │   ├── rewrite.txt              # 内容改写通用提示词
│   │   ├── video_script.txt         # 视频脚本通用提示词
│   │   └── README_PROMPTS.md        # 提示词工程指南
│   ├── Dockerfile
│   └── requirements.txt
│
├── website/
│   ├── frontend/                     # 网站前端
│   │   ├── index.html               # 单页应用（248 行）
│   │   ├── static/
│   │   │   └── chat.js              # AI 聊天组件 IIFE（217 行）
│   │   ├── nginx.conf               # Nginx 配置（静态资源 + API 反代）
│   │   └── Dockerfile               # Nginx 1.25-alpine 镜像
│   │
│   └── backend/                      # 网站后端
│       ├── app.py                   # 主应用，7 个 API 端点（376 行）
│       ├── knowledge_base.py        # RAG 知识库模块（关键词检索）
│       ├── knowledge/               # 知识库文档目录
│       │   ├── sample.txt           # 示例文档
│       │   ├── product_catalog.txt  # 产品目录
│       │   ├── shipping_policy.txt  # 物流退换货政策
│       │   └── company_info.txt     # 公司信息
│       ├── Dockerfile
│       └── requirements.txt
│
├── trading/                          # 交易助手服务
│   ├── app.py                       # 主应用，8 个 API 端点（298 行）
│   ├── indicators.py                # 14 种技术指标实现（842 行）
│   ├── analyzer.py                  # AI 分析 + 规则信号引擎（463 行）
│   ├── backtester.py                # 策略回测引擎（392 行）
│   ├── dashboard.html               # 交易仪表盘 UI（409 行）
│   ├── sample_data.py               # 4 种场景模拟数据生成
│   ├── Dockerfile
│   └── requirements.txt
│
├── scripts/
│   ├── setup.sh                     # 一键部署脚本
│   └── test_all.sh                  # 集成测试脚本
│
├── docker-compose.yml                # 6 个服务编排配置（216 行）
├── .env.example                      # 环境变量模板
├── .gitignore                        # Git 忽略规则
├── README.md                         # 本文件
└── README_DEPLOY.md                  # 详细部署运维指南
```

**代码统计**: 约 46 个文件，6,300+ 行代码

---

## 运维命令速查

### 服务管理

```bash
# 查看所有服务状态
docker compose ps

# 启动所有服务
docker compose up -d

# 停止所有服务
docker compose down

# 重启所有服务
docker compose restart

# 重启单个服务
docker compose restart gateway

# 重新构建并启动某个服务
docker compose build trading && docker compose up -d trading

# 强制重新构建所有服务（不使用缓存）
docker compose build --no-cache && docker compose up -d
```

### 日志查看

```bash
# 查看所有服务实时日志
docker compose logs -f

# 查看某个服务的日志
docker compose logs -f gateway

# 查看最近 100 行日志
docker compose logs --tail=100 social-bot

# 查看审计日志文件
docker exec ai-gateway cat /var/log/ai-gateway/audit-$(date +%Y%m%d).jsonl
```

### 数据管理

```bash
# 停止并清除所有数据卷（慎用！会删除 Redis 数据和日志）
docker compose down -v

# 查看数据卷
docker volume ls | grep ai-

# 备份 Redis 数据
docker exec ai-redis redis-cli BGSAVE
docker cp ai-redis:/data/dump.rdb ./backup/redis-dump.rdb
```

---

## 集成测试

```bash
# 运行自动化测试（检查所有服务健康端点）
bash scripts/test_all.sh
```

测试脚本会：
1. 检查 Docker Compose 服务是否全部运行
2. 依次请求各服务的 `/health` 端点
3. 通过网关验证路由是否正常
4. 输出每个服务的测试结果

---

## 自定义与扩展

### 更换 LLM 模型

只需修改 `.env` 中的两个变量，无需改动任何代码：

```bash
LLM_API_URL=http://your-llm-server:8000/v1
MODEL_NAME=your-model-name
```

然后重启服务：`docker compose restart`

### 添加新的社交平台

1. 在 `social-bot/prompts/` 下创建 `platform_name.txt` 提示词文件
2. 在 `social-bot/app.py` 的 `SUPPORTED_PLATFORMS` 列表中添加平台标识符
3. 重新构建：`docker compose build social-bot && docker compose up -d social-bot`

### 扩展知识库

将 `.txt` 或 `.md` 文件放入 `website/backend/knowledge/` 目录，重启网站后端即可自动加载。

### 升级到向量数据库

`knowledge_base.py` 的公共 API（`retrieve()` 和 `format_context()`）保持不变，只需替换内部实现：

```python
# 当前: 关键词匹配
# 升级: ChromaDB / FAISS / Pinecone
# 接口不变，业务代码零改动
```

### 添加新的 API 密钥

在 `.env` 的 `API_KEYS` 中追加新条目：

```bash
API_KEYS=sk-admin-001:admin:120:50000,sk-new-user:newuser:30:5000
```

重启网关生效：`docker compose restart gateway`

---

## 常见问题排查

### 1. 网关无法连接 LLM 服务（502 Bad Gateway）

```bash
# 确认 LLM 服务正在运行
curl http://localhost:8000/v1/models

# 确认 .env 中 LLM_API_URL 正确
grep LLM_API_URL .env

# 如果 LLM 在宿主机运行，确保使用 host.docker.internal
# Linux 需要 Docker 20.10+，docker-compose.yml 已配置 extra_hosts
```

### 2. 服务健康检查失败（unhealthy）

```bash
# 查看具体服务日志
docker compose logs <service-name>

# 检查端口是否被占用
ss -tlnp | grep <port>

# 确认 Dockerfile 和启动命令正确
docker compose exec <service-name> ps aux
```

### 3. API 返回 401 Unauthorized

```bash
# 确认请求头格式正确
curl -H "Authorization: Bearer sk-admin-001" http://localhost/stats

# 确认密钥在 .env 的 API_KEYS 中已配置
grep API_KEYS .env

# 重启网关使新密钥生效
docker compose restart gateway
```

### 4. API 返回 429 Rate Limit

```bash
# 查看当前用量
curl -H "Authorization: Bearer sk-admin-001" http://localhost/stats

# 调整 API_KEYS 中对应密钥的 rpm 和 daily_quota 值
# 重启网关生效
docker compose restart gateway
```

### 5. Redis 连接失败

```bash
# 确认 Redis 容器正常
docker compose ps redis

# 测试 Redis 连通性
docker exec ai-redis redis-cli ping

# 确认各服务使用容器名 redis 而非 localhost
grep REDIS_URL .env
```

### 6. 社交机器人提示词加载失败

```bash
# 确认提示词文件存在
docker exec ai-social-bot ls /app/prompts/

# 查看具体错误
docker compose logs social-bot | grep "提示词"
```

### 7. 交易服务要求最少 K 线数量

各端点的最低数据要求：
- `/api/indicators` — 至少 2 根 K 线
- `/api/analyze` — 至少 30 根 K 线
- `/api/signal` — 至少 30 根 K 线
- `/api/strategy/backtest` — 至少 50 根 K 线

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [在线文档中心](https://0xcaptain888.github.io/openclawd-ai-platform/) | GitHub Pages 托管的永久在线文档入口 |
| [部署与运维指南（在线）](https://0xcaptain888.github.io/openclawd-ai-platform/deployment-guide.html) | 12 模块完全教程：硬件选型、驱动安装、Docker、监控、集群管理、故障处理 |
| [API 使用手册（在线）](https://0xcaptain888.github.io/openclawd-ai-platform/api-manual.html) | 全部 API 端点的详细参数、响应格式和 curl 示例 |
| [README_DEPLOY.md](./README_DEPLOY.md) | 快速部署指南，含架构图、端点列表、运维命令、故障排查 |
| [social-bot/prompts/README_PROMPTS.md](./social-bot/prompts/README_PROMPTS.md) | 提示词工程指南，如何优化和自定义平台提示词 |
| [.env.example](./.env.example) | 完整的环境变量配置模板及说明 |

---

## License

MIT
