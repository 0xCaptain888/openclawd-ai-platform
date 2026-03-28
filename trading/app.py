"""
AI交易助手 - FastAPI主应用
提供技术分析、AI市场解读、回测和信号生成等API端点。
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import indicators as ind
import analyzer
import backtester
import sample_data


# =============================================================================
# Pydantic 数据模型
# =============================================================================

class Candle(BaseModel):
    """单根K线数据"""
    timestamp: str = ""
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class AnalyzeRequest(BaseModel):
    """完整分析请求"""
    symbol: str = Field(default="UNKNOWN", description="交易标的代码")
    timeframe: str = Field(default="1h", description="时间周期")
    candles: List[Candle] = Field(description="OHLCV蜡烛数据")
    extra_context: str = Field(default="", description="额外上下文信息")


class IndicatorRequest(BaseModel):
    """技术指标计算请求"""
    candles: List[Candle] = Field(description="OHLCV蜡烛数据")


class SignalRequest(BaseModel):
    """交易信号请求"""
    candles: List[Candle] = Field(description="OHLCV蜡烛数据")
    symbol: str = Field(default="UNKNOWN")


class Condition(BaseModel):
    """策略条件"""
    left: Any = Field(description="左操作数（指标名或数字）")
    op: str = Field(description="比较运算符: >, <, >=, <=, ==, cross_above, cross_below")
    right: Any = Field(description="右操作数（指标名或数字）")


class BacktestRequest(BaseModel):
    """回测请求"""
    candles: List[Candle] = Field(description="历史OHLCV数据")
    entry_conditions: List[Condition] = Field(description="入场条件")
    exit_conditions: List[Condition] = Field(description="出场条件")
    entry_logic: str = Field(default="and", description="入场条件逻辑: and/or")
    exit_logic: str = Field(default="and", description="出场条件逻辑: and/or")
    initial_capital: float = Field(default=100000.0, description="初始资金")
    position_pct: float = Field(default=1.0, description="仓位比例 (0-1)")
    stop_loss_pct: Optional[float] = Field(default=None, description="止损百分比")
    take_profit_pct: Optional[float] = Field(default=None, description="止盈百分比")
    commission_pct: float = Field(default=0.001, description="手续费率")


class ReportRequest(BaseModel):
    """市场报告请求"""
    symbol: str = Field(default="UNKNOWN")
    candles: List[Candle] = Field(description="主时间周期数据")
    candles_higher_tf: Optional[List[Candle]] = Field(default=None, description="更高时间周期数据")
    timeframe: str = Field(default="1h")
    higher_timeframe: str = Field(default="4h")


# =============================================================================
# FastAPI应用
# =============================================================================

app = FastAPI(
    title="AI交易助手",
    description="技术分析 + AI驱动的市场分析系统",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_ohlcv(candles: List[Candle]):
    """从Candle列表提取OHLCV数组。"""
    opens = [c.open for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    closes = [c.close for c in candles]
    volumes = [c.volume for c in candles]
    return opens, highs, lows, closes, volumes


# =============================================================================
# API端点
# =============================================================================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "service": "AI交易助手",
        "llm_api": os.getenv("LLM_API_URL", "http://localhost:11434/v1/chat/completions"),
        "model": os.getenv("MODEL_NAME", "qwen2.5"),
    }


@app.post("/api/indicators")
async def compute_indicators(req: IndicatorRequest):
    """
    计算技术指标（纯计算，不调用AI）。
    返回所有技术指标的计算结果。
    """
    if len(req.candles) < 2:
        raise HTTPException(status_code=400, detail="至少需要2根K线数据")

    opens, highs, lows, closes, volumes = _extract_ohlcv(req.candles)
    result = ind.compute_all(opens, highs, lows, closes, volumes)

    # 将None转换为null友好格式，并只返回最近200个数据点避免响应过大
    limit = min(200, len(closes))

    def _trim(arr):
        return arr[-limit:] if len(arr) > limit else arr

    trimmed = {}
    for key, val in result.items():
        if isinstance(val, list):
            trimmed[key] = _trim(val)
        else:
            trimmed[key] = val

    return {
        "total_candles": len(closes),
        "returned_points": limit,
        "current_price": closes[-1],
        "indicators": trimmed,
    }


@app.post("/api/analyze")
async def analyze_market(req: AnalyzeRequest):
    """
    完整市场分析：计算指标 + 规则信号 + AI解读。
    """
    if len(req.candles) < 30:
        raise HTTPException(status_code=400, detail="至少需要30根K线才能进行有效分析")

    opens, highs, lows, closes, volumes = _extract_ohlcv(req.candles)
    all_indicators = ind.compute_all(opens, highs, lows, closes, volumes)
    current_price = closes[-1]

    result = await analyzer.analyze_market(
        symbol=req.symbol,
        timeframe=req.timeframe,
        indicators=all_indicators,
        current_price=current_price,
        extra_context=req.extra_context,
    )
    return result


@app.post("/api/signal")
async def get_signals(req: SignalRequest):
    """
    获取当前交易信号（基于多指标规则引擎，不依赖AI）。
    """
    if len(req.candles) < 30:
        raise HTTPException(status_code=400, detail="至少需要30根K线数据")

    opens, highs, lows, closes, volumes = _extract_ohlcv(req.candles)
    all_indicators = ind.compute_all(opens, highs, lows, closes, volumes)
    current_price = closes[-1]

    signals = analyzer.generate_signals(all_indicators, current_price)
    signals["symbol"] = req.symbol
    signals["current_price"] = current_price
    return signals


@app.post("/api/strategy/backtest")
async def run_backtest(req: BacktestRequest):
    """
    策略回测：基于指标条件的入场/出场规则回测。
    """
    if len(req.candles) < 50:
        raise HTTPException(status_code=400, detail="至少需要50根K线进行回测")

    candles_dicts = [c.model_dump() for c in req.candles]
    entry_conds = [c.model_dump() for c in req.entry_conditions]
    exit_conds = [c.model_dump() for c in req.exit_conditions]

    result = backtester.backtest(
        candles=candles_dicts,
        entry_conditions=entry_conds,
        exit_conditions=exit_conds,
        entry_logic=req.entry_logic,
        exit_logic=req.exit_logic,
        initial_capital=req.initial_capital,
        position_pct=req.position_pct,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        commission_pct=req.commission_pct,
    )

    # 限制返回的equity_curve数据量
    ec = result.get("equity_curve", [])
    if len(ec) > 500:
        step = len(ec) // 500
        result["equity_curve"] = ec[::step]

    return result


@app.post("/api/report")
async def generate_report(req: ReportRequest):
    """
    生成AI综合市场报告（支持多时间周期）。
    """
    if len(req.candles) < 30:
        raise HTTPException(status_code=400, detail="至少需要30根K线数据")

    opens, highs, lows, closes, volumes = _extract_ohlcv(req.candles)
    main_indicators = ind.compute_all(opens, highs, lows, closes, volumes)

    timeframes = {req.timeframe: main_indicators}

    # 如果提供了更高时间周期的数据
    if req.candles_higher_tf and len(req.candles_higher_tf) >= 30:
        ho, hh, hl, hc, hv = _extract_ohlcv(req.candles_higher_tf)
        higher_indicators = ind.compute_all(ho, hh, hl, hc, hv)
        timeframes[req.higher_timeframe] = higher_indicators

    current_price = closes[-1]

    try:
        report = await analyzer.generate_report(req.symbol, timeframes, current_price)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM服务调用失败: {str(e)}")

    return {
        "symbol": req.symbol,
        "current_price": current_price,
        "report": report,
    }


# =============================================================================
# 示例数据端点（方便前端测试）
# =============================================================================

@app.get("/api/sample-data")
async def get_sample_data(
    scenario: str = "bullish",
    num_candles: int = 300,
):
    """
    获取示例OHLCV数据用于测试。
    scenario: bullish, bearish, sideways, volatile
    """
    generators = {
        "bullish": sample_data.bullish_trend,
        "bearish": sample_data.bearish_trend,
        "sideways": sample_data.sideways_market,
        "volatile": sample_data.high_volatility,
    }
    gen = generators.get(scenario, sample_data.bullish_trend)
    candles = gen(num_candles)
    return {"scenario": scenario, "num_candles": len(candles), "candles": candles}


# =============================================================================
# 前端页面
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """提供交易仪表盘页面"""
    html_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
