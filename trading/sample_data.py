"""
样本数据生成模块
生成逼真的OHLCV蜡烛图数据，用于测试和演示。
使用带有趋势、波动率聚集和成交量相关性的随机游走模型。
"""

import random
import math
from typing import List, Dict
from datetime import datetime, timedelta


def generate_ohlcv(
    num_candles: int = 500,
    start_price: float = 100.0,
    volatility: float = 0.02,
    trend: float = 0.0001,
    start_date: str = "2025-01-01",
    interval_minutes: int = 60,
    seed: int | None = None,
) -> List[Dict]:
    """
    生成逼真的OHLCV数据。

    参数:
        num_candles: 生成的蜡烛数量
        start_price: 起始价格
        volatility: 基础波动率 (日内百分比标准差)
        trend: 每根蜡烛的趋势偏移量
        start_date: 起始日期字符串 (YYYY-MM-DD)
        interval_minutes: 每根蜡烛的时间间隔（分钟）
        seed: 随机种子（可选，用于可重复性）

    返回:
        OHLCV字典列表，每个包含 timestamp, open, high, low, close, volume
    """
    if seed is not None:
        random.seed(seed)

    candles: List[Dict] = []
    dt = datetime.strptime(start_date, "%Y-%m-%d")
    delta = timedelta(minutes=interval_minutes)
    price = start_price
    # 波动率聚集状态
    current_vol = volatility

    for i in range(num_candles):
        # --- 波动率聚集 (GARCH-like) ---
        # 让波动率缓慢变化，模拟真实市场的波动率聚集效应
        vol_shock = random.gauss(0, 0.1)
        current_vol = max(
            volatility * 0.3,
            min(volatility * 3.0, current_vol * (1 + vol_shock * 0.1)),
        )

        # --- 蜡烛内部价格路径 ---
        open_price = price
        # 模拟蜡烛内的多步随机游走
        steps = 10
        step_vol = current_vol / math.sqrt(steps)
        intra_prices = [open_price]
        p = open_price
        for _ in range(steps):
            ret = random.gauss(trend / steps, step_vol)
            p = p * (1 + ret)
            intra_prices.append(p)

        close_price = intra_prices[-1]
        high_price = max(intra_prices)
        low_price = min(intra_prices)

        # 确保 high >= max(open, close), low <= min(open, close)
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        # 添加额外的影线（模拟盘中极值）
        wick_factor = random.uniform(0, current_vol * 0.5)
        high_price *= 1 + wick_factor
        low_price *= 1 - wick_factor

        # --- 成交量（与波动率正相关）---
        base_volume = 1000000
        vol_multiplier = current_vol / volatility
        # 价格变动越大，成交量越大
        price_change_ratio = abs(close_price - open_price) / open_price
        volume_boost = 1 + price_change_ratio * 20
        volume = base_volume * vol_multiplier * volume_boost * random.uniform(0.5, 1.5)

        candles.append(
            {
                "timestamp": dt.isoformat(),
                "open": round(open_price, 4),
                "high": round(high_price, 4),
                "low": round(low_price, 4),
                "close": round(close_price, 4),
                "volume": round(volume, 2),
            }
        )

        # 下一根蜡烛的开盘价 = 本根收盘价
        price = close_price
        dt += delta

    return candles


def generate_multi_timeframe(
    base_candles: List[Dict], factor: int = 4
) -> List[Dict]:
    """
    将低时间周期的蜡烛合并为高时间周期。
    例如将1小时蜡烛合并为4小时蜡烛。

    参数:
        base_candles: 基础OHLCV数据
        factor: 合并因子（每N根合并为1根）

    返回:
        合并后的OHLCV数据
    """
    merged: List[Dict] = []
    for i in range(0, len(base_candles) - factor + 1, factor):
        group = base_candles[i : i + factor]
        merged.append(
            {
                "timestamp": group[0]["timestamp"],
                "open": group[0]["open"],
                "high": max(c["high"] for c in group),
                "low": min(c["low"] for c in group),
                "close": group[-1]["close"],
                "volume": sum(c["volume"] for c in group),
            }
        )
    return merged


# 预设场景
def bullish_trend(num_candles: int = 300) -> List[Dict]:
    """生成上升趋势数据"""
    return generate_ohlcv(
        num_candles=num_candles, start_price=50.0, trend=0.001, volatility=0.015, seed=42
    )


def bearish_trend(num_candles: int = 300) -> List[Dict]:
    """生成下降趋势数据"""
    return generate_ohlcv(
        num_candles=num_candles, start_price=150.0, trend=-0.001, volatility=0.015, seed=42
    )


def sideways_market(num_candles: int = 300) -> List[Dict]:
    """生成震荡行情数据"""
    return generate_ohlcv(
        num_candles=num_candles, start_price=100.0, trend=0.0, volatility=0.01, seed=42
    )


def high_volatility(num_candles: int = 300) -> List[Dict]:
    """生成高波动行情数据"""
    return generate_ohlcv(
        num_candles=num_candles, start_price=100.0, trend=0.0002, volatility=0.04, seed=42
    )
