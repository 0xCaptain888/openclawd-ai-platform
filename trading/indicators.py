"""
技术指标计算模块
纯Python实现，无需TA-Lib依赖。
所有函数接收价格列表，返回计算结果列表。
"""

from typing import List, Tuple, Dict
import math


# =============================================================================
# 移动平均线
# =============================================================================

def sma(prices: List[float], period: int) -> List[float | None]:
    """
    简单移动平均线 (Simple Moving Average)
    公式: SMA(n) = (P1 + P2 + ... + Pn) / n

    参数:
        prices: 价格序列
        period: 计算周期

    返回:
        与prices等长的列表，前 period-1 个值为 None
    """
    result: List[float | None] = [None] * (period - 1)
    # 使用滑动窗口求和，避免每次重新加总
    window_sum = sum(prices[:period])
    result.append(window_sum / period)
    for i in range(period, len(prices)):
        window_sum += prices[i] - prices[i - period]
        result.append(window_sum / period)
    return result


def ema(prices: List[float], period: int) -> List[float | None]:
    """
    指数移动平均线 (Exponential Moving Average)
    公式: EMA_t = price_t * k + EMA_{t-1} * (1 - k)
           其中 k = 2 / (period + 1)

    初始值使用前 period 个价格的 SMA。

    参数:
        prices: 价格序列
        period: 计算周期

    返回:
        与prices等长的列表，前 period-1 个值为 None
    """
    if len(prices) < period:
        return [None] * len(prices)
    k = 2.0 / (period + 1)
    result: List[float | None] = [None] * (period - 1)
    # 初始EMA = 前period个价格的SMA
    initial = sum(prices[:period]) / period
    result.append(initial)
    prev = initial
    for i in range(period, len(prices)):
        val = prices[i] * k + prev * (1 - k)
        result.append(val)
        prev = val
    return result


# =============================================================================
# 动量指标
# =============================================================================

def rsi(prices: List[float], period: int = 14) -> List[float | None]:
    """
    相对强弱指数 (Relative Strength Index)
    公式:
        RS = 平均上涨幅度 / 平均下跌幅度
        RSI = 100 - 100 / (1 + RS)

    使用Wilder平滑法（指数移动平均）计算平均涨跌幅。

    参数:
        prices: 价格序列（通常为收盘价）
        period: 计算周期，默认14

    返回:
        与prices等长的列表
    """
    if len(prices) < period + 1:
        return [None] * len(prices)

    # 计算价格变动
    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # 分离上涨和下跌
    gains = [max(d, 0) for d in deltas]
    losses = [max(-d, 0) for d in deltas]

    # 初始平均值（前period个变动的简单平均）
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    result: List[float | None] = [None] * period  # 前period个无法计算

    # 第一个RSI值
    if avg_loss == 0:
        result.append(100.0)
    else:
        rs = avg_gain / avg_loss
        result.append(100.0 - 100.0 / (1.0 + rs))

    # Wilder平滑法计算后续值
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100.0 - 100.0 / (1.0 + rs))

    return result


def stochastic(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    k_period: int = 14,
    d_period: int = 3,
) -> Tuple[List[float | None], List[float | None]]:
    """
    随机震荡指标 (Stochastic Oscillator)
    公式:
        %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA(%K, d_period)

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        k_period: %K计算周期，默认14
        d_period: %D平滑周期，默认3

    返回:
        (%K列表, %D列表) 元组
    """
    n = len(closes)
    k_values: List[float | None] = [None] * (k_period - 1)

    for i in range(k_period - 1, n):
        highest = max(highs[i - k_period + 1 : i + 1])
        lowest = min(lows[i - k_period + 1 : i + 1])
        if highest == lowest:
            k_values.append(50.0)  # 避免除零
        else:
            k_values.append((closes[i] - lowest) / (highest - lowest) * 100.0)

    # %D = %K的SMA
    valid_k = [v for v in k_values if v is not None]
    d_sma = sma(valid_k, d_period)
    # 对齐到原始长度
    d_values: List[float | None] = [None] * (k_period - 1)
    d_values.extend(d_sma)

    return k_values, d_values


# =============================================================================
# MACD
# =============================================================================

def macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    """
    移动平均收敛/发散指标 (MACD)
    公式:
        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal_period)
        Histogram = MACD Line - Signal Line

    参数:
        prices: 价格序列
        fast_period: 快线周期，默认12
        slow_period: 慢线周期，默认26
        signal_period: 信号线周期，默认9

    返回:
        (macd_line, signal_line, histogram) 元组
    """
    ema_fast = ema(prices, fast_period)
    ema_slow = ema(prices, slow_period)

    # MACD线 = 快线EMA - 慢线EMA
    macd_line: List[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is not None and s is not None:
            macd_line.append(f - s)
        else:
            macd_line.append(None)

    # 信号线 = MACD线的EMA
    valid_macd = [v for v in macd_line if v is not None]
    if len(valid_macd) < signal_period:
        signal_line: List[float | None] = [None] * len(prices)
        histogram: List[float | None] = [None] * len(prices)
        return macd_line, signal_line, histogram

    signal_ema = ema(valid_macd, signal_period)

    # 对齐信号线到原始长度
    none_count = len(macd_line) - len(valid_macd)
    signal_line = [None] * none_count + signal_ema

    # 柱状图 = MACD线 - 信号线
    histogram = []
    for m, s in zip(macd_line, signal_line):
        if m is not None and s is not None:
            histogram.append(m - s)
        else:
            histogram.append(None)

    return macd_line, signal_line, histogram


# =============================================================================
# 布林带
# =============================================================================

def bollinger_bands(
    prices: List[float], period: int = 20, num_std: float = 2.0
) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    """
    布林带 (Bollinger Bands)
    公式:
        中轨 = SMA(price, period)
        上轨 = 中轨 + num_std * σ
        下轨 = 中轨 - num_std * σ
        其中 σ 为价格的标准差

    参数:
        prices: 价格序列
        period: 计算周期，默认20
        num_std: 标准差倍数，默认2.0

    返回:
        (upper, middle, lower) 元组
    """
    middle = sma(prices, period)
    upper: List[float | None] = []
    lower: List[float | None] = []

    for i in range(len(prices)):
        if middle[i] is None:
            upper.append(None)
            lower.append(None)
        else:
            # 计算窗口内的标准差
            window = prices[i - period + 1 : i + 1]
            mean = middle[i]
            variance = sum((p - mean) ** 2 for p in window) / period
            std = math.sqrt(variance)
            upper.append(mean + num_std * std)
            lower.append(mean - num_std * std)

    return upper, middle, lower


# =============================================================================
# 波动率指标
# =============================================================================

def atr(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[float | None]:
    """
    平均真实波幅 (Average True Range)
    公式:
        True Range = max(
            High - Low,
            |High - Previous Close|,
            |Low - Previous Close|
        )
        ATR = Wilder平滑(TR, period)

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: 计算周期，默认14

    返回:
        ATR值列表
    """
    n = len(closes)
    if n < 2:
        return [None] * n

    # 计算True Range序列
    tr_values: List[float] = [highs[0] - lows[0]]  # 第一个TR只能用 High-Low
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    # Wilder平滑法计算ATR
    result: List[float | None] = [None] * (period - 1)
    # 初始ATR = 前period个TR的简单平均
    first_atr = sum(tr_values[:period]) / period
    result.append(first_atr)
    prev_atr = first_atr
    for i in range(period, n):
        current_atr = (prev_atr * (period - 1) + tr_values[i]) / period
        result.append(current_atr)
        prev_atr = current_atr

    return result


# =============================================================================
# 成交量指标
# =============================================================================

def obv(closes: List[float], volumes: List[float]) -> List[float]:
    """
    能量潮指标 (On-Balance Volume)
    公式:
        如果 close > prev_close: OBV = prev_OBV + volume
        如果 close < prev_close: OBV = prev_OBV - volume
        如果 close == prev_close: OBV = prev_OBV

    参数:
        closes: 收盘价序列
        volumes: 成交量序列

    返回:
        OBV值列表
    """
    result = [volumes[0]]
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            result.append(result[-1] + volumes[i])
        elif closes[i] < closes[i - 1]:
            result.append(result[-1] - volumes[i])
        else:
            result.append(result[-1])
    return result


def volume_ma(volumes: List[float], period: int = 20) -> List[float | None]:
    """
    成交量移动平均线
    用于判断当前成交量相对于历史平均的活跃程度。

    参数:
        volumes: 成交量序列
        period: 计算周期

    返回:
        成交量SMA列表
    """
    return sma(volumes, period)


# =============================================================================
# 支撑/阻力位检测
# =============================================================================

def support_resistance(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    window: int = 10,
    num_levels: int = 5,
) -> Dict[str, List[float]]:
    """
    支撑/阻力位检测
    方法: 寻找局部极值点（波峰和波谷），然后聚类合并相近的价位。

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        window: 局部极值的检测窗口大小
        num_levels: 返回的支撑/阻力位数量

    返回:
        {"support": [...], "resistance": [...]}
    """
    n = len(closes)
    if n < window * 2 + 1:
        return {"support": [], "resistance": []}

    pivot_highs: List[float] = []
    pivot_lows: List[float] = []

    # 检测局部极值
    for i in range(window, n - window):
        # 局部最高点：当前high大于左右window范围内的所有high
        if highs[i] == max(highs[i - window : i + window + 1]):
            pivot_highs.append(highs[i])
        # 局部最低点
        if lows[i] == min(lows[i - window : i + window + 1]):
            pivot_lows.append(lows[i])

    # 聚类合并相近价位（使用简单的阈值聚类）
    def cluster_levels(levels: List[float], threshold_pct: float = 0.005) -> List[float]:
        """将相近的价位合并为一个（取平均值）"""
        if not levels:
            return []
        sorted_levels = sorted(levels)
        clusters: List[List[float]] = [[sorted_levels[0]]]
        for level in sorted_levels[1:]:
            # 如果与当前簇的均值相差不超过阈值，归入同一簇
            cluster_mean = sum(clusters[-1]) / len(clusters[-1])
            if abs(level - cluster_mean) / cluster_mean < threshold_pct:
                clusters[-1].append(level)
            else:
                clusters.append([level])
        # 按簇内元素数量排序（出现次数越多越重要），取前num_levels个
        clusters.sort(key=lambda c: len(c), reverse=True)
        return [round(sum(c) / len(c), 4) for c in clusters[:num_levels]]

    current_price = closes[-1]
    resistance = cluster_levels([p for p in pivot_highs if p > current_price])
    support = cluster_levels([p for p in pivot_lows if p < current_price])

    # 按距离当前价格从近到远排序
    resistance.sort()
    support.sort(reverse=True)

    return {"support": support[:num_levels], "resistance": resistance[:num_levels]}


# =============================================================================
# VWAP (Volume Weighted Average Price)
# =============================================================================

def vwap(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
) -> List[float]:
    """
    成交量加权平均价 (Volume Weighted Average Price)
    公式:
        Typical Price = (High + Low + Close) / 3
        VWAP = cumsum(TP * Volume) / cumsum(Volume)

    通常按日内数据计算，此处对整个输入序列做累积计算。

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        volumes: 成交量序列

    返回:
        VWAP值列表（与输入等长）
    """
    result: List[float] = []
    cum_tp_vol = 0.0
    cum_vol = 0.0
    for i in range(len(closes)):
        tp = (highs[i] + lows[i] + closes[i]) / 3.0
        cum_tp_vol += tp * volumes[i]
        cum_vol += volumes[i]
        if cum_vol == 0:
            result.append(0.0)
        else:
            result.append(cum_tp_vol / cum_vol)
    return result


# =============================================================================
# Williams %R
# =============================================================================

def williams_r(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> List[float | None]:
    """
    威廉指标 (Williams %R)
    公式:
        %R = (Highest High - Close) / (Highest High - Lowest Low) * (-100)

    取值范围: -100 到 0
        -80 以下为超卖区域
        -20 以上为超买区域

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: 计算周期，默认14

    返回:
        Williams %R 值列表
    """
    n = len(closes)
    result: List[float | None] = [None] * (period - 1)

    for i in range(period - 1, n):
        highest = max(highs[i - period + 1 : i + 1])
        lowest = min(lows[i - period + 1 : i + 1])
        if highest == lowest:
            result.append(0.0)
        else:
            result.append((highest - closes[i]) / (highest - lowest) * -100.0)
    return result


# =============================================================================
# CCI (Commodity Channel Index)
# =============================================================================

def cci(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 20,
) -> List[float | None]:
    """
    商品通道指数 (Commodity Channel Index)
    公式:
        TP = (High + Low + Close) / 3
        CCI = (TP - SMA(TP, period)) / (0.015 * Mean Deviation)

    取值参考:
        +100 以上: 超买/强势
        -100 以下: 超卖/弱势

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: 计算周期，默认20

    返回:
        CCI值列表
    """
    n = len(closes)
    # 计算 Typical Price
    tp_values = [(highs[i] + lows[i] + closes[i]) / 3.0 for i in range(n)]

    result: List[float | None] = [None] * (period - 1)

    for i in range(period - 1, n):
        window = tp_values[i - period + 1 : i + 1]
        tp_sma = sum(window) / period
        # 计算平均绝对偏差 (Mean Deviation)
        mean_dev = sum(abs(tp - tp_sma) for tp in window) / period
        if mean_dev == 0:
            result.append(0.0)
        else:
            result.append((tp_values[i] - tp_sma) / (0.015 * mean_dev))
    return result


# =============================================================================
# ADX (Average Directional Index)
# =============================================================================

def adx(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    period: int = 14,
) -> Tuple[List[float | None], List[float | None], List[float | None]]:
    """
    平均趋向指数 (Average Directional Index)
    公式:
        +DM = max(High_t - High_{t-1}, 0)  (当 +DM > -DM)
        -DM = max(Low_{t-1} - Low_t, 0)    (当 -DM > +DM)
        +DI = 100 * Smooth(+DM) / ATR
        -DI = 100 * Smooth(-DM) / ATR
        DX = 100 * |+DI - -DI| / (+DI + -DI)
        ADX = Wilder平滑(DX, period)

    取值参考:
        ADX > 25: 趋势明显
        ADX < 20: 无明显趋势

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        period: 计算周期，默认14

    返回:
        (adx_values, plus_di, minus_di) 元组
    """
    n = len(closes)
    if n < period + 1:
        none_list: List[float | None] = [None] * n
        return none_list[:], none_list[:], none_list[:]

    # 计算 True Range, +DM, -DM
    tr_list: List[float] = []
    plus_dm_list: List[float] = []
    minus_dm_list: List[float] = []

    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]

        if up_move > down_move and up_move > 0:
            plus_dm_list.append(up_move)
        else:
            plus_dm_list.append(0.0)

        if down_move > up_move and down_move > 0:
            minus_dm_list.append(down_move)
        else:
            minus_dm_list.append(0.0)

    # Wilder 平滑
    smooth_tr = sum(tr_list[:period])
    smooth_plus_dm = sum(plus_dm_list[:period])
    smooth_minus_dm = sum(minus_dm_list[:period])

    plus_di_list: List[float | None] = [None] * period
    minus_di_list: List[float | None] = [None] * period
    dx_list: List[float] = []

    # 第一个 DI 值
    pdi = 100.0 * smooth_plus_dm / smooth_tr if smooth_tr != 0 else 0.0
    mdi = 100.0 * smooth_minus_dm / smooth_tr if smooth_tr != 0 else 0.0
    plus_di_list.append(pdi)
    minus_di_list.append(mdi)
    if (pdi + mdi) == 0:
        dx_list.append(0.0)
    else:
        dx_list.append(100.0 * abs(pdi - mdi) / (pdi + mdi))

    for i in range(period, len(tr_list)):
        smooth_tr = smooth_tr - smooth_tr / period + tr_list[i]
        smooth_plus_dm = smooth_plus_dm - smooth_plus_dm / period + plus_dm_list[i]
        smooth_minus_dm = smooth_minus_dm - smooth_minus_dm / period + minus_dm_list[i]

        pdi = 100.0 * smooth_plus_dm / smooth_tr if smooth_tr != 0 else 0.0
        mdi = 100.0 * smooth_minus_dm / smooth_tr if smooth_tr != 0 else 0.0
        plus_di_list.append(pdi)
        minus_di_list.append(mdi)

        if (pdi + mdi) == 0:
            dx_list.append(0.0)
        else:
            dx_list.append(100.0 * abs(pdi - mdi) / (pdi + mdi))

    # 计算 ADX (DX 的 Wilder 平滑)
    adx_values: List[float | None] = [None] * (period * 2 - 1)
    if len(dx_list) >= period:
        first_adx = sum(dx_list[:period]) / period
        adx_values.append(first_adx)
        prev_adx = first_adx
        for i in range(period, len(dx_list)):
            current_adx = (prev_adx * (period - 1) + dx_list[i]) / period
            adx_values.append(current_adx)
            prev_adx = current_adx

    # 补齐长度到 n
    while len(adx_values) < n:
        adx_values.append(None)
    while len(plus_di_list) < n:
        plus_di_list.append(None)
    while len(minus_di_list) < n:
        minus_di_list.append(None)

    return adx_values[:n], plus_di_list[:n], minus_di_list[:n]


# =============================================================================
# Ichimoku Cloud (一目均衡表)
# =============================================================================

def ichimoku(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> Dict[str, List[float | None]]:
    """
    一目均衡表 (Ichimoku Cloud)
    公式:
        Tenkan-sen (转换线) = (period最高 + period最低) / 2  (period=9)
        Kijun-sen (基准线) = (period最高 + period最低) / 2   (period=26)
        Senkou Span A (先行上线) = (Tenkan + Kijun) / 2，前移26期
        Senkou Span B (先行下线) = (52期最高 + 52期最低) / 2，前移26期
        Chikou Span (迟行线) = 当前收盘价，后移26期

    参数:
        highs: 最高价序列
        lows: 最低价序列
        closes: 收盘价序列
        tenkan_period: 转换线周期，默认9
        kijun_period: 基准线周期，默认26
        senkou_b_period: 先行下线周期，默认52
        displacement: 位移量，默认26

    返回:
        包含各线数据的字典:
        {
            "tenkan_sen": [...],
            "kijun_sen": [...],
            "senkou_span_a": [...],
            "senkou_span_b": [...],
            "chikou_span": [...]
        }
    """
    n = len(closes)

    def midpoint(data: List[float], period: int) -> List[float | None]:
        """计算指定周期内 (最高 + 最低) / 2"""
        result: List[float | None] = [None] * (period - 1)
        for i in range(period - 1, len(data)):
            window = data[i - period + 1 : i + 1]
            # 此处 data 可能是 highs 或 lows，需要同时看 highs 和 lows
            result.append(None)  # placeholder
        return result

    # Tenkan-sen
    tenkan: List[float | None] = [None] * (tenkan_period - 1)
    for i in range(tenkan_period - 1, n):
        high_max = max(highs[i - tenkan_period + 1 : i + 1])
        low_min = min(lows[i - tenkan_period + 1 : i + 1])
        tenkan.append((high_max + low_min) / 2.0)

    # Kijun-sen
    kijun: List[float | None] = [None] * (kijun_period - 1)
    for i in range(kijun_period - 1, n):
        high_max = max(highs[i - kijun_period + 1 : i + 1])
        low_min = min(lows[i - kijun_period + 1 : i + 1])
        kijun.append((high_max + low_min) / 2.0)

    # Senkou Span A = (Tenkan + Kijun) / 2, shifted forward by displacement
    senkou_a: List[float | None] = [None] * displacement
    for i in range(n):
        if tenkan[i] is not None and kijun[i] is not None:
            senkou_a.append((tenkan[i] + kijun[i]) / 2.0)
        else:
            senkou_a.append(None)

    # Senkou Span B = (52-period high + 52-period low) / 2, shifted forward
    senkou_b_raw: List[float | None] = [None] * (senkou_b_period - 1)
    for i in range(senkou_b_period - 1, n):
        high_max = max(highs[i - senkou_b_period + 1 : i + 1])
        low_min = min(lows[i - senkou_b_period + 1 : i + 1])
        senkou_b_raw.append((high_max + low_min) / 2.0)

    senkou_b: List[float | None] = [None] * displacement + list(senkou_b_raw)

    # Chikou Span = Close shifted backward by displacement
    chikou: List[float | None] = list(closes[displacement:]) + [None] * displacement

    return {
        "tenkan_sen": tenkan,
        "kijun_sen": kijun,
        "senkou_span_a": senkou_a[:n + displacement],
        "senkou_span_b": senkou_b[:n + displacement],
        "chikou_span": chikou[:n],
    }


# =============================================================================
# 综合指标计算
# =============================================================================

def compute_all(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
) -> Dict:
    """
    计算所有技术指标并返回结构化结果。
    用于一次性获取完整的技术分析数据。

    参数:
        opens, highs, lows, closes, volumes: OHLCV数据序列

    返回:
        包含所有指标值的字典
    """
    macd_line, signal_line, hist = macd(closes)
    bb_upper, bb_middle, bb_lower = bollinger_bands(closes)
    stoch_k, stoch_d = stochastic(highs, lows, closes)

    adx_values, plus_di, minus_di = adx(highs, lows, closes)
    ichimoku_data = ichimoku(highs, lows, closes)

    return {
        "sma_20": sma(closes, 20),
        "sma_50": sma(closes, 50),
        "sma_200": sma(closes, 200),
        "ema_12": ema(closes, 12),
        "ema_26": ema(closes, 26),
        "rsi_14": rsi(closes, 14),
        "macd_line": macd_line,
        "macd_signal": signal_line,
        "macd_histogram": hist,
        "bb_upper": bb_upper,
        "bb_middle": bb_middle,
        "bb_lower": bb_lower,
        "atr_14": atr(highs, lows, closes, 14),
        "stoch_k": stoch_k,
        "stoch_d": stoch_d,
        "obv": obv(closes, volumes),
        "volume_ma_20": volume_ma(volumes, 20),
        "support_resistance": support_resistance(highs, lows, closes),
        "vwap": vwap(highs, lows, closes, volumes),
        "williams_r_14": williams_r(highs, lows, closes, 14),
        "cci_20": cci(highs, lows, closes, 20),
        "adx_14": adx_values,
        "plus_di_14": plus_di,
        "minus_di_14": minus_di,
        "ichimoku": ichimoku_data,
    }
