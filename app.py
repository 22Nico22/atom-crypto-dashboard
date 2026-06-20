"""
╔══════════════════════════════════════════════════════════════════╗
║          ATOM CRYPTO TRADING DASHBOARD  v1.0                     ║
║          100% Free  •  No API Keys  •  Discord Alerts            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import time
import datetime
import requests
import ccxt
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta

# ─────────────────────────────────────────────────────────────────
#  PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚡ ATOM Crypto Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
#  CUSTOM CSS  — dark neon-accent theme
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── root ── */
:root {
    --neon:  #00ffe7;
    --green: #00ff88;
    --red:   #ff4d6d;
    --gold:  #ffd700;
    --bg:    #0d0f14;
    --card:  #141720;
    --border:#1e2330;
}

/* FIX NYITÓ GOMB STÍLUSA A BAL FELSŐ SAROKBA */
#custom-sidebar-open-btn {
    position: fixed;
    top: 60px;
    left: 10px;
    z-index: 999999;
    background-color: var(--card);
    color: var(--neon);
    border: 1px solid var(--neon);
    border-radius: 8px;
    padding: 8px 14px;
    font-family: monospace;
    font-size: 0.85rem;
    cursor: pointer;
    box-shadow: 0 0 10px rgba(0,255,231,0.3);
    transition: all 0.2s ease;
}
#custom-sidebar-open-btn:hover {
    background-color: var(--neon);
    color: var(--bg);
    box-shadow: 0 0 15px rgba(0,255,231,0.6);
}

/* full-page background */
.stApp { background-color: var(--bg); }

/* hide hamburger / footer */
#MainMenu, footer, header { visibility: hidden; }

/* metric cards */
div[data-testid="metric-container"] {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 0 18px rgba(0,255,231,.06);
}
div[data-testid="metric-container"] label {
    color: #6b7280 !important;
    font-size: .75rem;
    letter-spacing: .08em;
    text-transform: uppercase;
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: var(--neon) !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
}

/* sidebar */
section[data-testid="stSidebar"] {
    background: var(--card) !important;
    border-right: 1px solid var(--border);
}

/* plotly chart container */
.js-plotly-plot { border-radius: 12px; overflow: hidden; }

/* section title */
.section-title {
    font-size: .7rem;
    letter-spacing: .12em;
    text-transform: uppercase;
    color: var(--neon);
    margin-bottom: 6px;
    margin-top: 4px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
}

/* signal badge */
.signal-buy  { color: var(--green); font-weight: 800; font-size: 1.2rem; }
.signal-sell { color: var(--red);   font-weight: 800; font-size: 1.2rem; }
.signal-hold { color: var(--gold);  font-weight: 800; font-size: 1.2rem; }

/* trade log table */
.trade-table { width: 100%; border-collapse: collapse; font-size: .82rem; }
.trade-table th { color: #6b7280; text-transform: uppercase;
                  font-size:.65rem; letter-spacing:.08em;
                  border-bottom:1px solid var(--border); padding:6px 8px; text-align:left; }
.trade-table td { padding:6px 8px; color:#c9d1d9;
                  border-bottom:1px solid var(--border); }
.trade-table tr:last-child td { border-bottom: none; }
</style>

<!-- EZ A JAVASCRIPT GOMB KÉNYSZERÍTI KI A NYITÁST -->
<button id="custom-sidebar-open-btn" onclick="openSidebar()">▶ MENÜ NYITÁSA</button>

<script>
function openSidebar() {
    const streamlitArrow = parent.document.querySelector('button[data-testid="collapsedControl"]');
    if (streamlitArrow) {
        streamlitArrow.click();
    } else {
        const event = new KeyboardEvent('keydown', { key: 'x', keyCode: 88, bubbles: true });
        parent.document.dispatchEvent(event);
    }
}
</script>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1517682020732375156/If-5BCf3TjD741en5MyTX4TvLu_QgMcug48f3aVgKeYzZBNHK6c2sJ5rCXf2g_0Ldp3M"
COINS = {
    "BTC/USDT": "₿ Bitcoin",
    "SOL/USDT": "◎ Solana",
    "LTC/USDT": "Ł Litecoin",
    "DOGE/USDT": "Ð Dogecoin",
}

TIMEFRAMES = {"15m": "15 minutes", "1h": "1 hour"}

STARTING_BALANCE = 10_000.0

# ─────────────────────────────────────────────────────────────────
#  SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "portfolio": {
            "cash": STARTING_BALANCE,
            "positions": {},   # symbol -> {"qty": float, "entry": float}
        },
        "trade_log": [],       # list of trade dicts
        "last_signals": {},    # symbol -> last signal string
        "last_fetch": {},      # symbol+tf -> timestamp
        "cache": {},           # symbol+tf -> DataFrame
        "auto_refresh": True,        # <-- Ezt állítottam True-ra
        "refresh_interval": 30,      # <-- Ezt állítottam 30-ra
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ─────────────────────────────────────────────────────────────────
#  DISCORD NOTIFICATION
# ─────────────────────────────────────────────────────────────────
def send_discord_alert(symbol: str, signal: str, price: float,
                       rsi: float, macd_hist: float,
                       bb_lower: float, bb_upper: float) -> bool:
    """Fire a rich embed to Discord with an @everyone ping. Returns True on success."""
    is_buy  = signal == "BUY"
    color   = 0x00FF88 if is_buy else 0xFF4D6D
    emoji   = "🟢" if is_buy else "🔴"
    action  = "BUY   📈" if is_buy else "SELL 📉"
    ts      = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    embed = {
        "title": f"{emoji}   ATOM SIGNAL  |  {symbol}  →  {action}",
        "color": color,
        "description": (
            f"**Confluence strategy triggered a `{signal}` signal.**\n"
            f"All three conditions met simultaneously."
        ),
        "fields": [
            {"name": "💰 Live Price",     "value": f"`${price:,.4f}`",       "inline": True},
            {"name": "📊 RSI (14)",       "value": f"`{rsi:.2f}`",           "inline": True},
            {"name": "📉 MACD Hist",      "value": f"`{macd_hist:.6f}`",     "inline": True},
            {"name": "🔻 BB Lower",       "value": f"`${bb_lower:,.4f}`",    "inline": True},
            {"name": "🔺 BB Upper",       "value": f"`${bb_upper:,.4f}`",    "inline": True},
            {"name": "🕐 Time (UTC)",     "value": f"`{ts}`",                "inline": False},
        ],
        "footer": {"text": "ATOM Crypto Dashboard  •  Simulated paper trading only"},
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }

    payload = {
        "content": f"@everyone 🚨 **ÚJ JELZÉS:** {symbol} → **{signal}**! 🚨",
        "embeds": [embed]
    }
    
    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=8)
        return r.status_code in (200, 204)
    except Exception:
        return False
    
# ─────────────────────────────────────────────────────────────────
#  DATA FETCHING (Binance REPLACED WITH Kraken)
# ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_exchange():
    return ccxt.kraken({"enableRateLimit": True})

def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """Fetch OHLCV from Kraken public endpoint via ccxt."""
    cache_key = f"{symbol}_{timeframe}"
    now = time.time()

    if (
        cache_key in st.session_state["cache"]
        and cache_key in st.session_state["last_fetch"]
        and now - st.session_state["last_fetch"][cache_key] < 45
    ):
        return st.session_state["cache"][cache_key]

    exchange = get_exchange()
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        df["dt"] = pd.to_datetime(df["ts"], unit="ms")
        df = df.set_index("dt")
        st.session_state["cache"][cache_key] = df
        st.session_state["last_fetch"][cache_key] = now
        return df
    except Exception as e:
        st.error(f"Data fetch error for {symbol} ({timeframe}) via Kraken: {e}")
        return pd.DataFrame()

# ─────────────────────────────────────────────────────────────────
#  TECHNICAL INDICATORS
# ─────────────────────────────────────────────────────────────────
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 35:
        return df

    close = df["close"]

    df["rsi"] = ta.momentum.RSIIndicator(close=close, window=14).rsi()

    macd_obj = ta.trend.MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    df["macd"]      = macd_obj.macd()
    df["macd_sig"]  = macd_obj.macd_signal()
    df["macd_hist"] = macd_obj.macd_diff()

    bb_obj = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"]  = bb_obj.bollinger_hband()
    df["bb_mid"]    = bb_obj.bollinger_mavg()
    df["bb_lower"]  = bb_obj.bollinger_lband()

    return df

# ─────────────────────────────────────────────────────────────────
#  SIGNAL ENGINE
# ─────────────────────────────────────────────────────────────────
def generate_signal(df: pd.DataFrame) -> dict:
    """Return the latest signal dict."""
    null_result = {
        "signal": "HOLD", "price": None,
        "rsi": None, "macd_hist": None,
        "bb_lower": None, "bb_upper": None,
    }
    if df.empty or "rsi" not in df.columns:
        return null_result

    row = df.dropna(subset=["rsi", "macd_hist", "bb_lower", "bb_upper"]).iloc[-1]
    price     = row["close"]
    rsi       = row["rsi"]
    macd_hist = row["macd_hist"]
    bb_lower  = row["bb_lower"]
    bb_upper  = row["bb_upper"]

    prev_rows = df.dropna(subset=["macd_hist"])
    if len(prev_rows) >= 2:
        prev_hist = prev_rows.iloc[-2]["macd_hist"]
    else:
        prev_hist = macd_hist

    buy_cond  = (price <= bb_lower) and (rsi < 35)  and (macd_hist > prev_hist)
    sell_cond = (price >= bb_upper) and (rsi > 65)  and (macd_hist < prev_hist)

    signal = "BUY" if buy_cond else "SELL" if sell_cond else "HOLD"

    return {
        "signal": signal, "price": price,
        "rsi": rsi, "macd_hist": macd_hist,
        "bb_lower": bb_lower, "bb_upper": bb_upper,
    }

# ─────────────────────────────────────────────────────────────────
#  PAPER TRADING ENGINE
# ─────────────────────────────────────────────────────────────────
def execute_paper_trade(symbol: str, signal: str, price: float):
    port = st.session_state["portfolio"]

    if signal == "BUY" and symbol not in port["positions"] and port["cash"] > 10:
        qty   = (port["cash"] * 0.95) / price 
        cost  = qty * price
        port["cash"] -= cost
        port["positions"][symbol] = {"qty": qty, "entry": price}
        st.session_state["trade_log"].append({
            "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
            "symbol": symbol, "action": "BUY",
            "price": price, "qty": qty, "pnl": None,
        })

    elif signal == "SELL" and symbol in port["positions"]:
        pos    = port["positions"].pop(symbol)
        qty    = pos["qty"]
        entry  = pos["entry"]
        revenue = qty * price
        pnl     = revenue - qty * entry
        port["cash"] += revenue
        st.session_state["trade_log"].append({
            "time": datetime.datetime.utcnow().strftime("%H:%M:%S"),
            "symbol": symbol, "action": "SELL",
            "price": price, "qty": qty, "pnl": pnl,
        })

def portfolio_value(live_prices: dict) -> float:
    port  = st.session_state["portfolio"]
    total = port["cash"]
    for sym, pos in port["positions"].items():
        p = live_prices.get(sym, pos["entry"])
        total += pos["qty"] * p
    return total

# ─────────────────────────────────────────────────────────────────
#  CHART KEYS
# ─────────────────────────────────────────────────────────────────
CHART_BG   = "#0d0f14"
CHART_GRID = "#1e2330"
NEON       = "#00ffe7"
GREEN_C    = "#00ff88"
RED_C      = "#ff4d6d"
GOLD_C     = "#ffd700"

def build_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.70, 0.30],
        vertical_spacing=0.04,
        subplot_titles=[f"{symbol}  —  Price & Bollinger Bands", "RSI (14)"],
    )

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color=GREEN_C,
        decreasing_line_color=RED_C,
        name="Price",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_upper"],
        line=dict(color="rgba(0,255,231,0.45)", width=1.2, dash="dot"),
        name="BB Upper",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_mid"],
        line=dict(color="rgba(0,255,231,0.25)", width=1),
        name="BB Mid",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["bb_lower"],
        line=dict(color="rgba(0,255,231,0.45)", width=1.2, dash="dot"),
        fill="tonexty",
        fillcolor="rgba(0,255,231,0.03)",
        name="BB Lower",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=df.index, y=df["rsi"],
        line=dict(color=NEON, width=1.6),
        name="RSI",
    ), row=2, col=1)
    fig.add_hline(y=65,  line=dict(color=RED_C,   width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=35,  line=dict(color=GREEN_C, width=1, dash="dash"), row=2, col=1)
    fig.add_hline(y=50,  line=dict(color=CHART_GRID, width=1), row=2, col=1)

    fig.update_layout(
        paper_bgcolor=CHART_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color="#c9d1d9", family="monospace"),
        xaxis_rangeslider_visible=False,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            bordercolor=CHART_GRID,
            font=dict(size=11),
        ),
        margin=dict(l=0, r=0, t=36, b=0),
        height=560,
    )
    for axis in ["xaxis", "yaxis", "xaxis2", "yaxis2"]:
        fig.update_layout(**{
            axis: dict(
                gridcolor=CHART_GRID,
                zerolinecolor=CHART_GRID,
                showgrid=True,
            )
        })
    fig.update_yaxes(range=[10, 90], row=2, col=1)

    return fig

# ─────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ ATOM Dashboard")
    st.markdown("---")

    selected_symbol = st.selectbox(
        "Select Asset",
        list(COINS.keys()),
        format_func=lambda s: COINS[s],
    )
    selected_tf = st.selectbox(
        "Timeframe",
        list(TIMEFRAMES.keys()),
        format_func=lambda t: TIMEFRAMES[t],
    )

    st.markdown("---")
    st.markdown("### 🔄 Auto Refresh")
    auto_ref = st.toggle("Enable Auto Refresh", value=st.session_state["auto_refresh"])
    st.session_state["auto_refresh"] = auto_ref
    if auto_ref:
        interval = st.slider("Interval (seconds)", 30, 300,
                             st.session_state["refresh_interval"], step=15)
        st.session_state["refresh_interval"] = interval

    st.markdown("---")
    st.markdown("### 💼 Portfolio")
    port = st.session_state["portfolio"]
    st.metric("Cash Balance", f"${port['cash']:,.2f}")
    if port["positions"]:
        st.markdown("**Open Positions**")
        for sym, pos in port["positions"].items():
            st.caption(f"{sym}   qty={pos['qty']:.6f}  @${pos['entry']:.4f}")

    st.markdown("---")
    if st.button("🗑️ Reset Portfolio", use_container_width=True):
        st.session_state["portfolio"] = {
            "cash": STARTING_BALANCE,
            "positions": {},
        }
        st.session_state["trade_log"] = []
        st.session_state["last_signals"] = {}
        st.rerun()

    st.markdown("---")
    st.caption("📡 Data: Kraken public API via ccxt")
    st.caption("🔔 Alerts: Discord Webhooks")
    st.caption("📊 Indicators: ta library")

# ─────────────────────────────────────────────────────────────────
#  AUTO-REFRESH TRIGGER
# ─────────────────────────────────────────────────────────────────
if st.session_state["auto_refresh"]:
    time.sleep(0.1)   
    st.markdown(
        f"<p style='color:#6b7280;font-size:.72rem;'> "
        f"⏱ Auto-refresh every {st.session_state['refresh_interval']}s — "
        f"next at {(datetime.datetime.now() + datetime.timedelta(seconds=st.session_state['refresh_interval'])).strftime('%H:%M:%S')}"
        f"</p>",
        unsafe_allow_html=True,
    )
    st.session_state["_refresh_counter"] = st.session_state.get("_refresh_counter", 0) + 1

# ─────────────────────────────────────────────────────────────────
#  MAIN  — HEADER
# ─────────────────────────────────────────────────────────────────
st.markdown(
    "<h1 style='font-family:monospace;color:#00ffe7;letter-spacing:.06em;margin-bottom:2px;'>"
    "⚡ ATOM CRYPTO DASHBOARD</h1>"
    "<p style='color:#6b7280;font-size:.8rem;margin-top:0;'>"
    "Paper trading  •  Confluence strategy (BB + RSI + MACD)  •  100 % free  •  no API keys (Kraken Network)</p>",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────
#  FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────
with st.spinner(f"Fetching {selected_symbol} data from Kraken…"):
    df_15 = fetch_ohlcv(selected_symbol, selected_tf)
    df_1h = fetch_ohlcv(selected_symbol, "1h")

df_main = compute_indicators(df_15.copy()) if not df_15.empty else pd.DataFrame()

sig_data = generate_signal(df_main)
signal   = sig_data["signal"]
price    = sig_data["price"] or 0.0
rsi_val  = sig_data["rsi"]
macd_h   = sig_data["macd_hist"]
bb_lo    = sig_data["bb_lower"]
bb_hi    = sig_data["bb_upper"]

prev_signal = st.session_state["last_signals"].get(selected_symbol, "HOLD")
if prev_signal == "HOLD" and signal in ("BUY", "SELL"):
    sent = send_discord_alert(
        symbol=selected_symbol, signal=signal,
        price=price, rsi=rsi_val or 0,
        macd_hist=macd_h or 0,
        bb_lower=bb_lo or 0, bb_upper=bb_hi or 0,
    )
    if sent:
        st.toast(f"📲 Discord alert sent: {signal} on {selected_symbol}", icon="✅")
    else:
        st.toast("⚠️ Discord webhook failed — check URL", icon="⚠️")

st.session_state["last_signals"][selected_symbol] = signal

if price:
    execute_paper_trade(selected_symbol, signal, price)

live_prices: dict = {}
for sym in COINS:
    cached = st.session_state["cache"].get(f"{sym}_{selected_tf}")
    if cached is not None and not cached.empty:
        live_prices[sym] = cached["close"].iloc[-1]
    elif sym == selected_symbol and price:
        live_prices[sym] = price

port_val = portfolio_value(live_prices)
pnl_pct  = (port_val / STARTING_BALANCE - 1) * 100

# ─────────────────────────────────────────────────────────────────
#  METRIC ROW
# ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)

signal_icons = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}

with c1:
    st.metric(
        label="💰 LIVE PRICE",
        value=f"${price:,.4f}" if price else "—",
        delta=None,
    )
with c2:
    sig_icon = signal_icons.get(signal, "⬜")
    st.metric(
        label="📡 SIGNAL",
        value=f"{sig_icon} {signal}",
    )
with c3:
    rsi_disp = f"{rsi_val:.1f}" if rsi_val else "—"
    st.metric(label="📊 RSI (14)", value=rsi_disp)

with c4:
    st.metric(
        label="💼 PORTFOLIO VALUE",
        value=f"${port_val:,.2f}",
        delta=f"${port_val - STARTING_BALANCE:+,.2f}",
        delta_color="normal",
    )
with c5:
    pnl_color = "normal" if pnl_pct >= 0 else "inverse"
    st.metric(
        label="📈 TOTAL PnL",
        value=f"{pnl_pct:+.2f}%",
        delta=f"from ${STARTING_BALANCE:,.0f} start",
        delta_color="off",
    )

st.markdown("<br>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
#  CHART SECTION
# ─────────────────────────────────────────────────────────────────
st.markdown(f"<div class='section-title'>📈 {selected_symbol} — {TIMEFRAMES[selected_tf]} chart</div>",
            unsafe_allow_html=True)

if not df_main.empty:
    fig = build_chart(df_main, selected_symbol)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
else:
    st.warning("No chart data available — retrying next refresh.")

# ─────────────────────────────────────────────────────────────────
#  SIGNAL DETAIL
# ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🔬 Signal & Indicator Snapshot</div>",
            unsafe_allow_html=True)

col_a, col_b, col_c = st.columns(3)

with col_a:
    css_cls = f"signal-{signal.lower()}"
    st.markdown(
        f"<p style='color:#6b7280;font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;'>Active Signal</p>"
        f"<p class='{css_cls}'>{signal_icons.get(signal,'')} {signal}</p>",
        unsafe_allow_html=True,
    )

with col_b:
    if rsi_val is not None:
        rsi_color = GREEN_C if rsi_val < 35 else (RED_C if rsi_val > 65 else GOLD_C)
        st.markdown(
            f"<p style='color:#6b7280;font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;'>RSI (14)</p>"
            f"<p style='color:{rsi_color};font-size:1.4rem;font-weight:700;'>{rsi_val:.2f}</p>",
            unsafe_allow_html=True,
        )

with col_c:
    if bb_lo and bb_hi:
        st.markdown(
            f"<p style='color:#6b7280;font-size:.72rem;text-transform:uppercase;letter-spacing:.1em;margin-bottom:4px;'>Bollinger Bands</p>"
            f"<p style='color:{NEON};font-size:.9rem;'>Lower: <b>${bb_lo:,.4f}</b></p>"
            f"<p style='color:{NEON};font-size:.9rem;'>Upper: <b>${bb_hi:,.4f}</b></p>",
            unsafe_allow_html=True,
        )

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<div class='section-title'>✅ Confluence Conditions</div>",
            unsafe_allow_html=True)

if price and rsi_val and bb_lo and bb_hi and macd_h is not None:
    prev_hist = df_main["macd_hist"].dropna().iloc[-2] if len(df_main.dropna(subset=["macd_hist"])) >= 2 else macd_h
    b1 = price <= bb_lo
    b2 = rsi_val < 35
    b3 = macd_h > prev_hist
    s1 = price >= bb_hi
    s2 = rsi_val > 65
    s3 = macd_h < prev_hist

    cols = st.columns(6)
    labels = [
        (f"{'✅' if b1 else '⬜'} Price ≤ BB Lower",  b1),
        (f"{'✅' if b2 else '⬜'} RSI < 35",           b2),
        (f"{'✅' if b3 else '⬜'} MACD Hist ↑",        b3),
        (f"{'✅' if s1 else '⬜'} Price ≥ BB Upper",   s1),
        (f"{'✅' if s2 else '⬜'} RSI > 65",           s2),
        (f"{'✅' if s3 else '⬜'} MACD Hist ↓",        s3),
    ]
    for col, (label, _) in zip(cols, labels):
        col.markdown(
            f"<p style='font-size:.8rem;color:#c9d1d9;'>{label}</p>",
            unsafe_allow_html=True,
        )
    st.caption("Left 3 = BUY conditions  |  Right 3 = SELL conditions  |  All three in a group must be ✅ for a signal")

# ─────────────────────────────────────────────────────────────────
#  TRADE LOG
# ─────────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>📋 Paper Trade Log</div>",
            unsafe_allow_html=True)

log = st.session_state["trade_log"]
if not log:
    st.caption("No trades executed yet — waiting for confluence signals.")
else:
    rows = list(reversed(log[-50:]))
    html = """<table class='trade-table'>
<thead><tr>
  <th>Time</th><th>Symbol</th><th>Action</th>
  <th>Price</th><th>Qty</th><th>PnL</th>
</tr></thead><tbody>"""
    for t in rows:
        action_color = GREEN_C if t["action"] == "BUY" else RED_C
        pnl_str = f"${t['pnl']:+.2f}" if t["pnl"] is not None else "—"
        pnl_color = (GREEN_C if (t["pnl"] or 0) >= 0 else RED_C) if t["pnl"] else "#6b7280"
        html += (
            f"<tr>"
            f"<td style='color:#6b7280'>{t['time']}</td>"
            f"<td>{t['symbol']}</td>"
            f"<td style='color:{action_color};font-weight:700'>{t['action']}</td>"
            f"<td>${t['price']:,.4f}</td>"
            f"<td>{t['qty']:.6f}</td>"
            f"<td style='color:{pnl_color}'>{pnl_str}</td>"
            f"</tr>"
        )
    html += "</tbody></table>"
    st.markdown(html, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────
#  1H OHLCV
# ─────────────────────────────────────────────────────────────────
st.markdown("<br><div class='section-title'>📊 1H Recent OHLCV — {}</div>".format(selected_symbol),
            unsafe_allow_html=True)

if not df_1h.empty:
    snap = df_1h[["open", "high", "low", "close", "volume"]].tail(8).copy()
    snap.index = snap.index.strftime("%Y-%m-%d %H:%M")
    snap.columns = ["Open", "High", "Low", "Close", "Volume"]
    st.dataframe(
        snap.style.format({
            "Open":  "${:.4f}",
            "High":  "${:.4f}",
            "Low":   "${:.4f}",
            "Close": "${:.4f}",
            "Volume": "{:,.2f}",
        }),
        use_container_width=True,
        height=280,
    )

# ─────────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#6b7280;font-size:.7rem;text-align:center;letter-spacing:.06em;'> "
    "⚡ ATOM Crypto Dashboard  •  For educational / paper trading purposes only  "
    "•  Not financial advice  •  Data: Kraken public API  •  No API keys required"
    "</p>",
    unsafe_allow_html=True,
)

if st.session_state["auto_refresh"]:
    time.sleep(st.session_state["refresh_interval"])
    st.rerun()