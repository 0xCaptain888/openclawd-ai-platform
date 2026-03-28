# OpenClawd AI Platform

A unified AI platform that orchestrates three business services — **Social Bot**, **Website**, and **Trading** — behind a single API Gateway, powered by a local LLM backend (vLLM / Ollama / LocalAI).

## Architecture

```
Client
  │
  ▼
┌─────────────────────────────────────┐
│  API Gateway (:80)                  │
│  Auth → Rate Limit → Route → Audit │
└──┬────────┬────────┬────────┬──────┘
   │        │        │        │
   ▼        ▼        ▼        ▼
 vLLM    Social    Website  Trading
(外部)   Bot       Backend   Service
         :8010     :4000     :8020
                     │
                  Frontend
                   :3000
          ┌──────────────────┐
          │  Redis (:6379)   │
          └──────────────────┘
```

All services share a single LLM endpoint via the OpenAI-compatible API, so you can swap models without changing any application code.

## Features

### API Gateway
- Bearer token authentication with configurable API keys
- Per-key rate limiting (RPM + daily quota)
- Request proxying to all backend services
- JSONL audit logging for every request

### Social Bot
- Content generation for **10 platforms**: Xiaohongshu, Douyin, Weibo, Twitter/X, Instagram, Zhihu, Bilibili, TikTok, LinkedIn, YouTube
- Content rewriting with style/tone control
- Video script generation
- Batch generation across multiple platforms
- APScheduler-based task scheduling with Redis queue

### Website
- AI-powered chat assistant with RAG knowledge base
- SEO content & meta tag generation
- Product description generation
- FAQ generation
- Multi-language translation
- Dark/light theme frontend with embedded chat widget

### Trading
- 14 technical indicators: SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic, OBV, VWAP, Williams %R, CCI, ADX, Ichimoku Cloud, Support/Resistance
- AI-driven market analysis with structured prompts
- Rule-based signal engine (score -100 to +100)
- Backtesting engine with Sharpe ratio, max drawdown, win rate, profit factor
- Interactive candlestick dashboard with ECharts

## Quick Start

```bash
# Clone the repository
git clone https://github.com/0xCaptain888/openclawd-ai-platform.git
cd openclawd-ai-platform

# Option A: Automated setup
bash scripts/setup.sh

# Option B: Manual setup
cp .env.example .env
# Edit .env — set LLM_API_URL to your local LLM endpoint
docker compose up -d
```

### Prerequisites

- **Docker** >= 24.0 with Compose v2 plugin
- **A running LLM backend** providing an OpenAI-compatible API (e.g., vLLM, Ollama, LocalAI)
- **4 GB RAM** minimum (excluding LLM resource requirements)

## Configuration

Edit `.env` to configure the platform:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_URL` | LLM backend URL | `http://host.docker.internal:8000/v1` |
| `MODEL_NAME` | Model identifier | `Qwen2-72B-Instruct-GPTQ-Int4` |
| `API_KEYS` | Gateway API keys | See `.env.example` |
| `GATEWAY_PORT` | Gateway external port | `80` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `LOG_LEVEL` | Logging level | `INFO` |

### API Key Format

`API_KEYS` is comma-separated, each entry: `key:name:rpm:daily_quota`

```
sk-admin-001:admin:120:50000,sk-readonly:viewer:30:5000
```

## API Endpoints

All requests go through the Gateway (default port 80).

| Method | Path | Service | Auth | Description |
|--------|------|---------|------|-------------|
| GET | `/health` | Gateway | No | Health check |
| GET | `/stats` | Gateway | Yes | Usage statistics |
| * | `/v1/*` | vLLM | Yes | LLM inference (OpenAI-compatible) |
| POST | `/social/generate` | Social Bot | Yes | Generate social content |
| POST | `/social/rewrite` | Social Bot | Yes | Rewrite content |
| POST | `/social/video-script` | Social Bot | Yes | Generate video script |
| POST | `/social/batch` | Social Bot | Yes | Batch generate for multiple platforms |
| GET | `/social/platforms` | Social Bot | Yes | List supported platforms |
| POST | `/website/api/chat` | Website | Yes | AI chat with RAG |
| POST | `/website/api/seo/generate` | Website | Yes | Generate SEO content |
| POST | `/website/api/seo/meta` | Website | Yes | Generate meta tags |
| POST | `/website/api/content/product-description` | Website | Yes | Product descriptions |
| POST | `/website/api/content/faq` | Website | Yes | FAQ generation |
| POST | `/website/api/translate` | Website | Yes | Translation |
| POST | `/trading/api/analyze` | Trading | Yes | AI market analysis |
| POST | `/trading/api/indicators` | Trading | Yes | Compute technical indicators |
| POST | `/trading/api/strategy/backtest` | Trading | Yes | Run backtest |
| POST | `/trading/api/signal` | Trading | Yes | Generate trading signal |
| POST | `/trading/api/report` | Trading | Yes | Full analysis report |

### Example Request

```bash
# Health check
curl http://localhost/health

# Generate social media content
curl http://localhost/social/generate \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{"platform": "xiaohongshu", "topic": "咖啡拉花技巧", "style": "活泼"}'

# Chat with AI assistant
curl http://localhost/website/api/chat \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{"message": "你们的退货政策是什么？"}'

# Get trading signal
curl http://localhost/trading/api/signal \
  -H "Authorization: Bearer sk-admin-001" \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTC/USDT", "data": [...]}'
```

## Project Structure

```
ai-platform/
├── gateway/                  # API Gateway service
│   ├── app.py               # Auth, rate limiting, routing, audit
│   ├── Dockerfile
│   └── requirements.txt
├── social-bot/              # Social media content service
│   ├── app.py               # 16 API endpoints for 10 platforms
│   ├── scheduler.py         # Task scheduling with Redis
│   ├── prompts/             # Platform-specific prompt templates
│   ├── Dockerfile
│   └── requirements.txt
├── website/
│   ├── frontend/            # Static site with AI chat widget
│   │   ├── index.html
│   │   ├── static/chat.js
│   │   ├── nginx.conf
│   │   └── Dockerfile
│   └── backend/             # Website API with RAG
│       ├── app.py
│       ├── knowledge_base.py
│       ├── knowledge/       # RAG knowledge documents
│       ├── Dockerfile
│       └── requirements.txt
├── trading/                 # Trading analysis service
│   ├── app.py               # Trading API endpoints
│   ├── indicators.py        # 14 technical indicators
│   ├── analyzer.py          # AI analysis + signal engine
│   ├── backtester.py        # Backtesting engine
│   ├── dashboard.html       # Interactive trading dashboard
│   ├── sample_data.py
│   ├── Dockerfile
│   └── requirements.txt
├── scripts/
│   ├── setup.sh             # Automated setup script
│   └── test_all.sh          # Integration test script
├── docker-compose.yml       # Service orchestration
├── .env.example             # Configuration template
└── README_DEPLOY.md         # Detailed deployment & ops guide
```

## Operations

```bash
# View all service status
docker compose ps

# Follow logs
docker compose logs -f

# Follow a specific service
docker compose logs -f gateway

# Restart a single service
docker compose restart trading

# Stop all services
docker compose down

# Rebuild and restart a service
docker compose build gateway && docker compose up -d gateway

# Run integration tests
bash scripts/test_all.sh
```

## Documentation

- **[README_DEPLOY.md](./README_DEPLOY.md)** — Detailed deployment guide with troubleshooting

## License

MIT
