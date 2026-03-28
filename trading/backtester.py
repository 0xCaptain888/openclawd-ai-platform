"""
简易回测引擎
支持基于技术指标的策略定义、历史数据回测和绩效统计。
"""

import math
from typing import List, Dict, Any, Optional
from indicators import (
    sma, ema, rsi, macd, bollinger_bands, atr, stochastic, obv, volume_ma,
)


# =============================================================================
# 策略规则定义
# =============================================================================

def _get_indicator_value(
    indicator_cache: Dict[str, List], name: str, index: int
) -> Optional[float]:
    """安全获取指标在指定索引处的值。"""
    arr = indicator_cache.get(name)
    if arr is None or index >= len(arr):
        return None
    return arr[index]


def evaluate_condition(
    condition: Dict[str, Any],
    indicator_cache: Dict[str, List],
    index: int,
    closes: List[float],
) -> bool:
    """
    评估单个条件是否满足。

    条件格式示例:
        {"left": "rsi_14", "op": "<", "right": 30}
        {"left": "close", "op": ">", "right": "sma_20"}
        {"left": "macd_histogram", "op": ">", "right": 0}

    left/right 可以是:
        - 字符串: 指标名称（从indicator_cache获取）或 "close"
        - 数字: 常量值
    """
    def _resolve(val):
        if isinstance(val, (int, float)):
            return val
        if val == "close":
            return closes[index] if index < len(closes) else None
        return _get_indicator_value(indicator_cache, val, index)

    left_val = _resolve(condition["left"])
    right_val = _resolve(condition["right"])
    op = condition["op"]

    if left_val is None or right_val is None:
        return False

    if op == ">":
        return left_val > right_val
    elif op == "<":
        return left_val < right_val
    elif op == ">=":
        return left_val >= right_val
    elif op == "<=":
        return left_val <= right_val
    elif op == "==":
        return left_val == right_val
    elif op == "cross_above":
        # 交叉上穿: 当前 left > right 且上一根 left <= right
        prev_left = _resolve(condition["left"]) if index == 0 else None
        if index > 0:
            prev_left = _resolve_at(condition["left"], indicator_cache, index - 1, closes)
            prev_right = _resolve_at(condition["right"], indicator_cache, index - 1, closes)
            if prev_left is None or prev_right is None:
                return False
            return left_val > right_val and prev_left <= prev_right
        return False
    elif op == "cross_below":
        if index > 0:
            prev_left = _resolve_at(condition["left"], indicator_cache, index - 1, closes)
            prev_right = _resolve_at(condition["right"], indicator_cache, index - 1, closes)
            if prev_left is None or prev_right is None:
                return False
            return left_val < right_val and prev_left >= prev_right
        return False
    return False


def _resolve_at(val, indicator_cache, index, closes):
    """在指定索引处解析值。"""
    if isinstance(val, (int, float)):
        return val
    if val == "close":
        return closes[index] if index < len(closes) else None
    return _get_indicator_value(indicator_cache, val, index)


def evaluate_conditions(
    conditions: List[Dict],
    indicator_cache: Dict[str, List],
    index: int,
    closes: List[float],
    logic: str = "and",
) -> bool:
    """
    评估一组条件。

    参数:
        conditions: 条件列表
        logic: "and" 或 "or"
    """
    if logic == "and":
        return all(
            evaluate_condition(c, indicator_cache, index, closes)
            for c in conditions
        )
    else:
        return any(
            evaluate_condition(c, indicator_cache, index, closes)
            for c in conditions
        )


# =============================================================================
# 指标预计算
# =============================================================================

def precompute_indicators(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
) -> Dict[str, List]:
    """预计算所有常用指标并放入缓存字典。"""
    macd_line, macd_signal, macd_hist = macd(closes)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes)
    stoch_k, stoch_d = stochastic(highs, lows, closes)

    return {
        "sma_10": sma(closes, 10),
        "sma_20": sma(closes, 20),
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
        "ema_12": ema(closes, 12),
        "ema_26": ema(closes, 26),
        "ema_50": ema(closes, 50),
        "rsi_14": rsi(closes, 14),
        "macd_line": macd_line,
        "macd_signal": macd_signal,
        "macd_histogram": macd_hist,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,
        "atr_14": atr(highs, lows, closes, 14),
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "obv": obv(closes, volumes),
        "volume_ma_20": volume_ma(volumes, 20),
    }


# =============================================================================
# 回测引擎
# =============================================================================

def backtest(
    candles: List[Dict],
    entry_conditions: List[Dict],
    exit_conditions: List[Dict],
    entry_logic: str = "and",
    exit_logic: str = "and",
    initial_capital: float = 100000.0,
    position_pct: float = 1.0,
    stop_loss_pct: Optional[float] = None,
    take_profit_pct: Optional[float] = None,
    commission_pct: float = 0.001,
) -> Dict[str, Any]:
    """
    执行策略回测。

    参数:
        candles: OHLCV蜡烛数据列表
        entry_conditions: 入场条件列表
        exit_conditions: 出场条件列表
        entry_logic: 入场条件逻辑（"and"/"or"）
        exit_logic: 出场条件逻辑
        initial_capital: 初始资金
        position_pct: 每次开仓使用资金的百分比（0-1）
        stop_loss_pct: 止损百分比（可选）
        take_profit_pct: 止盈百分比（可选）
        commission_pct: 手续费率

    返回:
        包含绩效指标和交易日志的字典
    """
    # 提取OHLCV数组
    opens = [c["open"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    volumes = [c["volume"] for c in candles]
    timestamps = [c.get("timestamp", str(i)) for i, c in enumerate(candles)]

    # 预计算指标
    cache = precompute_indicators(opens, highs, lows, closes, volumes)

    # 回测状态
    capital = initial_capital
    position = 0.0  # 持有数量
    entry_price = 0.0
    trades: List[Dict] = []
    equity_curve: List[float] = []
    in_position = False

    for i in range(len(candles)):
        current_price = closes[i]

        # 计算当前净值
        if in_position:
            current_equity = capital + position * current_price
        else:
            current_equity = capital
        equity_curve.append(current_equity)

        if not in_position:
            # --- 检查入场条件 ---
            if evaluate_conditions(entry_conditions, cache, i, closes, entry_logic):
                # 开仓
                invest = capital * position_pct
                commission = invest * commission_pct
                invest_after = invest - commission
                position = invest_after / current_price
                entry_price = current_price
                capital -= invest
                in_position = True
                trades.append({
                    "type": "entry",
                    "index": i,
                    "timestamp": timestamps[i],
                    "price": current_price,
                    "quantity": position,
                    "commission": commission,
                })
        else:
            # --- 检查出场条件 ---
            should_exit = False
            exit_reason = "signal"

            # 止损检查
            if stop_loss_pct is not None:
                if current_price <= entry_price * (1 - stop_loss_pct):
                    should_exit = True
                    exit_reason = "stop_loss"

            # 止盈检查
            if take_profit_pct is not None:
                if current_price >= entry_price * (1 + take_profit_pct):
                    should_exit = True
                    exit_reason = "take_profit"

            # 信号出场
            if not should_exit:
                if evaluate_conditions(exit_conditions, cache, i, closes, exit_logic):
                    should_exit = True
                    exit_reason = "signal"

            if should_exit:
                # 平仓
                proceeds = position * current_price
                commission = proceeds * commission_pct
                capital += proceeds - commission
                pnl = (current_price - entry_price) / entry_price * 100

                trades.append({
                    "type": "exit",
                    "reason": exit_reason,
                    "index": i,
                    "timestamp": timestamps[i],
                    "price": current_price,
                    "quantity": position,
                    "commission": commission,
                    "pnl_pct": round(pnl, 4),
                })
                position = 0.0
                in_position = False

    # 如果回测结束时仍持仓，按最后价格平仓
    if in_position:
        final_price = closes[-1]
        proceeds = position * final_price
        commission = proceeds * commission_pct
        capital += proceeds - commission
        pnl = (final_price - entry_price) / entry_price * 100
        trades.append({
            "type": "exit",
            "reason": "end_of_data",
            "index": len(candles) - 1,
            "timestamp": timestamps[-1],
            "price": final_price,
            "quantity": position,
            "commission": commission,
            "pnl_pct": round(pnl, 4),
        })
        position = 0.0
        in_position = False
        equity_curve[-1] = capital

    # --- 绩效计算 ---
    metrics = _calculate_metrics(equity_curve, trades, initial_capital)

    return {
        "metrics": metrics,
        "trades": trades,
        "equity_curve": equity_curve,
        "total_candles": len(candles),
    }


def _calculate_metrics(
    equity_curve: List[float],
    trades: List[Dict],
    initial_capital: float,
) -> Dict[str, Any]:
    """计算回测绩效指标。"""

    final_equity = equity_curve[-1] if equity_curve else initial_capital

    # 总收益率
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100

    # 交易统计
    exit_trades = [t for t in trades if t["type"] == "exit"]
    num_trades = len(exit_trades)
    winning = [t for t in exit_trades if t["pnl_pct"] > 0]
    losing = [t for t in exit_trades if t["pnl_pct"] <= 0]
    win_rate = len(winning) / num_trades * 100 if num_trades > 0 else 0

    # 平均盈亏
    avg_win = sum(t["pnl_pct"] for t in winning) / len(winning) if winning else 0
    avg_loss = sum(t["pnl_pct"] for t in losing) / len(losing) if losing else 0

    # 利润因子 (Profit Factor) = 总盈利 / 总亏损
    gross_profit = sum(t["pnl_pct"] for t in winning)
    gross_loss = abs(sum(t["pnl_pct"] for t in losing))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

    # 最大回撤
    max_drawdown_pct = 0.0
    peak = equity_curve[0] if equity_curve else initial_capital
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

    # 夏普比率 (Sharpe Ratio)
    # 使用每根蜡烛的收益率计算，假设无风险利率为0
    if len(equity_curve) > 1:
        returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
        ]
        mean_return = sum(returns) / len(returns)
        if len(returns) > 1:
            variance = sum((r - mean_return) ** 2 for r in returns) / (len(returns) - 1)
            std_return = math.sqrt(variance)
            # 年化（假设每天一根蜡烛，约252个交易日）
            sharpe = (mean_return / std_return) * math.sqrt(252) if std_return > 0 else 0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # 总手续费
    total_commission = sum(t.get("commission", 0) for t in trades)

    return {
        "initial_capital": initial_capital,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 4),
        "num_trades": num_trades,
        "win_rate_pct": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 4),
        "avg_loss_pct": round(avg_loss, 4),
        "profit_factor": round(profit_factor, 4) if profit_factor != float("inf") else "Inf",
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "sharpe_ratio": round(sharpe, 4),
        "total_commission": round(total_commission, 2),
    }
