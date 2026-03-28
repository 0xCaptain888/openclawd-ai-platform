"""
AI分析模块
负责将技术指标数据格式化为LLM提示词，调用LLM获取市场分析，
并将LLM响应解析为结构化交易信号。
"""

import os
import json
import httpx
from typing import Dict, List, Any, Optional


LLM_API_URL = os.getenv("LLM_API_URL", "http://localhost:11434/v1/chat/completions")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))


# =============================================================================
# LLM调用
# =============================================================================

async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> str:
    """
    调用本地LLM API（兼容OpenAI格式）。

    参数:
        messages: 对话消息列表
        temperature: 生成温度
        max_tokens: 最大生成token数

    返回:
        LLM生成的文本
    """
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
        resp = await client.post(LLM_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data["choices"][0]["message"]["content"]


# =============================================================================
# 提示词模板
# =============================================================================

SYSTEM_PROMPT = """你是一个专业的量化交易分析师。你的任务是基于技术指标数据，提供客观、准确的市场分析。
请注意：
1. 基于数据说话，不做无根据的猜测
2. 明确给出方向判断（看多/看空/中性）和置信度
3. 指出关键的支撑位和阻力位
4. 给出风险提示
5. 使用中文回答"""


def _format_latest_indicators(indicators: Dict) -> str:
    """将指标数据格式化为LLM可读的文本摘要（只取最新值）。"""
    lines = []

    def _last(arr):
        """获取列表中最后一个非None值"""
        if not arr:
            return "N/A"
        for v in reversed(arr):
            if v is not None:
                return round(v, 4) if isinstance(v, float) else v
        return "N/A"

    lines.append(f"SMA(20): {_last(indicators.get('sma_20', []))}")
    lines.append(f"SMA(50): {_last(indicators.get('sma_50', []))}")
    lines.append(f"SMA(200): {_last(indicators.get('sma_200', []))}")
    lines.append(f"EMA(12): {_last(indicators.get('ema_12', []))}")
    lines.append(f"EMA(26): {_last(indicators.get('ema_26', []))}")
    lines.append(f"RSI(14): {_last(indicators.get('rsi_14', []))}")
    lines.append(f"MACD线: {_last(indicators.get('macd_line', []))}")
    lines.append(f"MACD信号线: {_last(indicators.get('macd_signal', []))}")
    lines.append(f"MACD柱状图: {_last(indicators.get('macd_histogram', []))}")
    lines.append(f"布林上轨: {_last(indicators.get('bb_upper', []))}")
    lines.append(f"布林中轨: {_last(indicators.get('bb_middle', []))}")
    lines.append(f"布林下轨: {_last(indicators.get('bb_lower', []))}")
    lines.append(f"ATR(14): {_last(indicators.get('atr_14', []))}")
    lines.append(f"随机指标 %K: {_last(indicators.get('stoch_k', []))}")
    lines.append(f"随机指标 %D: {_last(indicators.get('stoch_d', []))}")

    sr = indicators.get("support_resistance", {})
    if sr:
        lines.append(f"支撑位: {sr.get('support', [])}")
        lines.append(f"阻力位: {sr.get('resistance', [])}")

    return "\n".join(lines)


def build_analysis_prompt(
    symbol: str,
    timeframe: str,
    indicators: Dict,
    current_price: float,
    extra_context: str = "",
) -> List[Dict[str, str]]:
    """
    构建市场分析提示词。

    参数:
        symbol: 交易对/股票代码
        timeframe: 时间周期
        indicators: 技术指标数据
        current_price: 当前价格
        extra_context: 额外上下文信息

    返回:
        消息列表（OpenAI格式）
    """
    indicator_text = _format_latest_indicators(indicators)
    user_msg = f"""请分析以下市场数据并给出交易建议：

## 基本信息
- 交易标的: {symbol}
- 时间周期: {timeframe}
- 当前价格: {current_price}

## 技术指标
{indicator_text}

{f"## 补充信息" + chr(10) + extra_context if extra_context else ""}

请按以下格式输出分析结果：
1. **趋势判断**: 当前趋势方向和强度
2. **关键价位**: 重要的支撑位和阻力位
3. **信号汇总**: 各指标给出的信号（看多/看空/中性）
4. **交易建议**: 具体的操作建议（入场价、止损位、目标价）
5. **风险提示**: 需要关注的风险因素
6. **置信度**: 对本次分析的置信度评分（1-10）"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def build_risk_assessment_prompt(
    symbol: str,
    position_size: float,
    entry_price: float,
    current_price: float,
    indicators: Dict,
) -> List[Dict[str, str]]:
    """
    构建风险评估提示词。

    参数:
        symbol: 交易标的
        position_size: 持仓大小
        entry_price: 入场价
        current_price: 当前价格
        indicators: 技术指标数据

    返回:
        消息列表
    """
    pnl_pct = (current_price - entry_price) / entry_price * 100
    indicator_text = _format_latest_indicators(indicators)

    user_msg = f"""请评估以下持仓的风险状况：

## 持仓信息
- 交易标的: {symbol}
- 持仓大小: {position_size}
- 入场价: {entry_price}
- 当前价格: {current_price}
- 当前盈亏: {pnl_pct:.2f}%

## 技术指标
{indicator_text}

请评估：
1. 当前持仓的风险等级（低/中/高/极高）
2. 建议的止损调整
3. 是否建议减仓/加仓
4. 关键的风险事件/价位"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def build_report_prompt(
    symbol: str,
    timeframes: Dict[str, Dict],
    current_price: float,
) -> List[Dict[str, str]]:
    """
    构建多时间周期综合报告提示词。

    参数:
        symbol: 交易标的
        timeframes: {timeframe_name: indicators_dict} 多时间周期指标数据
        current_price: 当前价格

    返回:
        消息列表
    """
    sections = []
    for tf_name, tf_indicators in timeframes.items():
        sections.append(f"### {tf_name}\n{_format_latest_indicators(tf_indicators)}")
    all_tf_text = "\n\n".join(sections)

    user_msg = f"""请生成一份完整的市场分析报告：

## 基本信息
- 交易标的: {symbol}
- 当前价格: {current_price}

## 多时间周期技术指标
{all_tf_text}

请输出完整的分析报告，包含：
1. **市场概览**: 整体市场状态描述
2. **多周期分析**: 各时间周期的趋势一致性分析
3. **关键指标解读**: 重要指标的当前状态和含义
4. **支撑阻力分析**: 关键价位标注
5. **交易策略建议**: 短线和中线的具体操作建议
6. **风险管理**: 仓位建议和止损设置
7. **总结评分**: 看多/看空评分（-10到+10）"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


# =============================================================================
# 信号生成（基于规则，无需LLM）
# =============================================================================

def generate_signals(indicators: Dict, current_price: float) -> Dict[str, Any]:
    """
    基于技术指标生成交易信号（纯规则引擎，不依赖LLM）。

    返回每个指标的信号方向和综合评分。
    评分范围: -100（极度看空）到 +100（极度看多）
    """

    def _last(arr):
        if not arr:
            return None
        for v in reversed(arr):
            if v is not None:
                return v
        return None

    signals = {}
    score = 0
    signal_count = 0

    # --- 均线信号 ---
    sma20 = _last(indicators.get("sma_20", []))
    sma50 = _last(indicators.get("sma_50", []))
    sma200 = _last(indicators.get("sma_200", []))

    if sma20 is not None:
        if current_price > sma20:
            signals["sma_20"] = {"signal": "看多", "detail": f"价格在SMA20({sma20:.2f})上方"}
            score += 10
        else:
            signals["sma_20"] = {"signal": "看空", "detail": f"价格在SMA20({sma20:.2f})下方"}
            score -= 10
        signal_count += 1

    if sma50 is not None:
        if current_price > sma50:
            signals["sma_50"] = {"signal": "看多", "detail": f"价格在SMA50({sma50:.2f})上方"}
            score += 10
        else:
            signals["sma_50"] = {"signal": "看空", "detail": f"价格在SMA50({sma50:.2f})下方"}
            score -= 10
        signal_count += 1

    if sma50 is not None and sma200 is not None:
        if sma50 > sma200:
            signals["golden_cross"] = {"signal": "看多", "detail": "SMA50 > SMA200（黄金交叉形态）"}
            score += 15
        else:
            signals["death_cross"] = {"signal": "看空", "detail": "SMA50 < SMA200（死亡交叉形态）"}
            score -= 15
        signal_count += 1

    # --- RSI信号 ---
    rsi_val = _last(indicators.get("rsi_14", []))
    if rsi_val is not None:
        if rsi_val > 70:
            signals["rsi"] = {"signal": "看空", "detail": f"RSI({rsi_val:.1f})处于超买区域"}
            score -= 15
        elif rsi_val < 30:
            signals["rsi"] = {"signal": "看多", "detail": f"RSI({rsi_val:.1f})处于超卖区域"}
            score += 15
        elif rsi_val > 50:
            signals["rsi"] = {"signal": "偏多", "detail": f"RSI({rsi_val:.1f})在50上方"}
            score += 5
        else:
            signals["rsi"] = {"signal": "偏空", "detail": f"RSI({rsi_val:.1f})在50下方"}
            score -= 5
        signal_count += 1

    # --- MACD信号 ---
    macd_val = _last(indicators.get("macd_line", []))
    macd_sig = _last(indicators.get("macd_signal", []))
    macd_hist = _last(indicators.get("macd_histogram", []))
    if macd_val is not None and macd_sig is not None:
        if macd_val > macd_sig:
            signals["macd"] = {"signal": "看多", "detail": "MACD线在信号线上方"}
            score += 10
        else:
            signals["macd"] = {"signal": "看空", "detail": "MACD线在信号线下方"}
            score -= 10
        signal_count += 1

    if macd_hist is not None:
        # 柱状图的变化方向
        hist_list = indicators.get("macd_histogram", [])
        valid_hist = [v for v in hist_list if v is not None]
        if len(valid_hist) >= 2:
            if valid_hist[-1] > valid_hist[-2]:
                signals["macd_momentum"] = {"signal": "偏多", "detail": "MACD柱状图递增"}
                score += 5
            else:
                signals["macd_momentum"] = {"signal": "偏空", "detail": "MACD柱状图递减"}
                score -= 5
            signal_count += 1

    # --- 布林带信号 ---
    bb_u = _last(indicators.get("bb_upper", []))
    bb_l = _last(indicators.get("bb_lower", []))
    bb_m = _last(indicators.get("bb_middle", []))
    if bb_u is not None and bb_l is not None:
        bb_width = (bb_u - bb_l) / bb_m * 100 if bb_m else 0
        if current_price > bb_u:
            signals["bollinger"] = {"signal": "看空", "detail": f"价格突破布林上轨({bb_u:.2f})，可能回调"}
            score -= 10
        elif current_price < bb_l:
            signals["bollinger"] = {"signal": "看多", "detail": f"价格跌破布林下轨({bb_l:.2f})，可能反弹"}
            score += 10
        elif current_price > bb_m:
            signals["bollinger"] = {"signal": "偏多", "detail": "价格在布林中轨上方"}
            score += 5
        else:
            signals["bollinger"] = {"signal": "偏空", "detail": "价格在布林中轨下方"}
            score -= 5
        signal_count += 1

    # --- 随机指标信号 ---
    stoch_k = _last(indicators.get("stoch_k", []))
    stoch_d = _last(indicators.get("stoch_d", []))
    if stoch_k is not None:
        if stoch_k > 80:
            signals["stochastic"] = {"signal": "看空", "detail": f"%K({stoch_k:.1f})处于超买区域"}
            score -= 10
        elif stoch_k < 20:
            signals["stochastic"] = {"signal": "看多", "detail": f"%K({stoch_k:.1f})处于超卖区域"}
            score += 10
        signal_count += 1

    # --- 成交量信号 ---
    vol_ma = _last(indicators.get("volume_ma_20", []))
    obv_list = indicators.get("obv", [])
    if vol_ma and obv_list and len(obv_list) >= 2:
        if obv_list[-1] > obv_list[-2]:
            signals["volume"] = {"signal": "偏多", "detail": "OBV上升，资金流入"}
            score += 5
        else:
            signals["volume"] = {"signal": "偏空", "detail": "OBV下降，资金流出"}
            score -= 5
        signal_count += 1

    # --- 综合评分 ---
    max_possible = signal_count * 15 if signal_count else 1
    normalized_score = int(score / max_possible * 100) if max_possible else 0
    normalized_score = max(-100, min(100, normalized_score))

    if normalized_score > 30:
        overall = "看多"
    elif normalized_score < -30:
        overall = "看空"
    else:
        overall = "中性"

    return {
        "overall_signal": overall,
        "score": normalized_score,
        "signals": signals,
        "signal_count": signal_count,
    }


# =============================================================================
# 完整分析流程
# =============================================================================

async def analyze_market(
    symbol: str,
    timeframe: str,
    indicators: Dict,
    current_price: float,
    extra_context: str = "",
) -> Dict[str, Any]:
    """
    执行完整的市场分析：规则信号 + LLM解读。

    参数:
        symbol: 交易标的
        timeframe: 时间周期
        indicators: 计算好的技术指标
        current_price: 当前价格
        extra_context: 额外上下文

    返回:
        包含规则信号和AI分析的完整结果
    """
    # 规则信号（不依赖LLM，始终可用）
    rule_signals = generate_signals(indicators, current_price)

    # LLM分析
    messages = build_analysis_prompt(symbol, timeframe, indicators, current_price, extra_context)
    try:
        ai_analysis = await call_llm(messages)
    except Exception as e:
        ai_analysis = f"LLM分析暂不可用: {str(e)}"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": current_price,
        "rule_signals": rule_signals,
        "ai_analysis": ai_analysis,
    }


async def generate_report(
    symbol: str,
    timeframes: Dict[str, Dict],
    current_price: float,
) -> str:
    """
    生成多时间周期综合AI报告。

    参数:
        symbol: 交易标的
        timeframes: 多周期指标数据
        current_price: 当前价格

    返回:
        AI生成的报告文本
    """
    messages = build_report_prompt(symbol, timeframes, current_price)
    return await call_llm(messages, max_tokens=4096)
