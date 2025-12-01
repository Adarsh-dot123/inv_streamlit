import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from typing import Optional

# ----------------------------
# Page config + theme CSS
# ----------------------------
st.set_page_config(page_title="Investment Simulator", layout="wide")

st.markdown(
    """
<style>
/* Base app background & text */
html, body, [class*="css"] {
    background: linear-gradient(135deg, #000000 0%, #120800 100%) !important;
    color: #FFD700 !important;
}

/* Container spacing */
.block-container { padding-top: 1.2rem; }

/* Input style */
.stTextInput>div>div>input, .stNumberInput>div>input, .stSelectbox>div>div {
    background: #0b0b0b !important;
    color: #FFD700 !important;
    border-radius: 8px;
}

/* Buttons */
.stButton>button {
    background: linear-gradient(135deg, #b8860b, #ffd700) !important;
    color: #000 !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    box-shadow: 0 6px 22px rgba(255,215,0,0.12) !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#0b0b0b,#120800) !important;
    color: #FFD700 !important;
}

/* Cards */
.gold-card {
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
    border-radius: 12px;
    padding: 14px;
    border: 1px solid rgba(255,215,0,0.08);
    box-shadow: 0 8px 30px rgba(0,0,0,0.6);
    margin-bottom: 18px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Session-state defaults
# ----------------------------
if "user" not in st.session_state:
    st.session_state.user = None

if "cash" not in st.session_state:
    st.session_state.cash = 10000.0

if "holdings" not in st.session_state:
    # holdings: { "AAPL": {"qty":5, "avg_price": 132.5} }
    st.session_state.holdings = {}

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

# ----------------------------
# Helper: caching data fetches
# ----------------------------
@st.cache_data(ttl=60 * 5)
def fetch_history(symbol: str, period: str = "1y", interval: str = "1d") -> Optional[pd.DataFrame]:
    """Fetch OHLCV history for a symbol using yfinance. Returns DataFrame with Date column."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        df = df.reset_index()
        # Ensure required columns
        if not all(col in df.columns for col in ["Open", "High", "Low", "Close", "Volume", "Date"]):
            return None
        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return None

@st.cache_data(ttl=60 * 5)
def fetch_quote(symbol: str) -> Optional[dict]:
    """Fetch a simple quote (price, change, name)"""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d", interval="1d")
        if hist.empty:
            return None
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
        change = round(price - prev, 2)
        pct = round((change / prev) * 100, 2) if prev else 0.0
        try:
            name = ticker.info.get("shortName") or ticker.info.get("longName") or ""
        except Exception:
            name = ""
        return {"symbol": symbol.upper(), "price": round(price, 2), "change": change, "pct": pct, "name": name}
    except Exception:
        return None

# ----------------------------
# Plotly candlestick plotting (uses RGBA colors)
# ----------------------------
def plot_candlestick(df: pd.DataFrame, symbol: str, ma_windows: list = [20, 50]) -> go.Figure:
    """
    Create a Plotly candlestick chart with moving averages and volume.
    Expects df with Date, Open, High, Low, Close, Volume columns.
    """
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            increasing_line_color="#FFD700",
            decreasing_line_color="#6b4f00",
            increasing_fillcolor="rgba(255,215,0,0.12)",
            decreasing_fillcolor="rgba(80,60,20,0.12)",
            name="Price",
            showlegend=False,
        )
    )

    # moving averages
    for w in ma_windows:
        if len(df) >= w:
            ma = df["Close"].rolling(w).mean()
            color = "#ffd700" if w == 20 else "#c59f23"
            fig.add_trace(
                go.Scatter(
                    x=df["Date"],
                    y=ma,
                    mode="lines",
                    name=f"MA{w}",
                    line=dict(color=color, width=1.6, dash="dash"),
                )
            )

    # volume bars on secondary y-axis
    fig.add_trace(
        go.Bar(
            x=df["Date"],
            y=df["Volume"],
            name="Volume",
            marker_color="rgba(255,215,0,0.18)",
            opacity=0.6,
            yaxis="y2",
            showlegend=False,
        )
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=30, b=20),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Volume", overlaying="y", side="right", position=0.15, showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(color="#FFD700"),
    )

    return fig

# ----------------------------
# Sidebar navigation + login/logout
# ----------------------------
st.sidebar.title("Investment Simulator")
st.sidebar.write("Black · Gold edition")

if st.session_state.user is None:
    st.sidebar.info("Not logged in")
    page = st.sidebar.radio("Navigate", ["Login"])
else:
    st.sidebar.success(f"User: {st.session_state.user}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        # rerun after logout to refresh UI
        st.rerun()
    page = st.sidebar.radio("Navigate", ["Dashboard", "Buy", "Sell", "Search", "Watchlist"])

# ----------------------------
# Login page
# ----------------------------
if page == "Login":
    st.title("🔐 Login")
    username = st.text_input("Enter a username to start")
    if st.button("Login"):
        if username and username.strip():
            st.session_state.user = username.strip()
            st.success(f"Welcome, {st.session_state.user}!")
            st.rerun()
        else:
            st.error("Please enter a valid username.")

# small helper to require login
def require_login():
    if st.session_state.user is None:
        st.warning("Please log in to access this page.")
        st.stop()

# ----------------------------
# Dashboard page
# ----------------------------
if page == "Dashboard":
    require_login()
    st.title("📈 Dashboard")

    # account summary card
    st.markdown('<div class="gold-card">', unsafe_allow_html=True)
    st.subheader("Account Summary")
    st.write(f"**Cash balance:** ${st.session_state.cash:,.2f}")
    st.markdown("</div>", unsafe_allow_html=True)

    # holdings table
    holding_rows = []
    total_value = st.session_state.cash
    for sym, info in st.session_state.holdings.items():
        qty = info.get("qty", 0)
        avg = info.get("avg_price", 0.0)
        quote = fetch_quote(sym)
        cur_price = quote["price"] if quote else None
        value = round((cur_price * qty) if cur_price else 0.0, 2)
        total_value += value
        holding_rows.append({"Symbol": sym, "Qty": qty, "Avg Price": avg, "Cur Price": cur_price if cur_price else "-", "Value": value})

    st.markdown('<div class="gold-card">', unsafe_allow_html=True)
    st.subheader("Portfolio")
    if holding_rows:
        df_hold = pd.DataFrame(holding_rows)
        st.table(df_hold)
    else:
        st.info("No holdings yet. Buy some stocks to start.")
    st.subheader(f"Total Net Worth: **${total_value:,.2f}**")
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Buy page
# ----------------------------
elif page == "Buy":
    require_login()
    st.title("🟢 Buy Stocks")

    c1, c2 = st.columns([2, 1])
    with c1:
        buy_sym = st.text_input("Symbol (e.g., AAPL)").upper()
    with c2:
        buy_qty = st.number_input("Quantity", min_value=1, step=1, value=1)

    if st.button("Buy"):
        if not buy_sym:
            st.error("Enter a symbol.")
        else:
            hist = fetch_history(buy_sym, period="5d", interval="1d")
            if hist is None:
                st.error("Symbol not found.")
            else:
                price = float(hist["Close"].iloc[-1])
                cost = price * buy_qty
                if st.session_state.cash < cost:
                    st.error("Insufficient funds.")
                else:
                    cur = st.session_state.holdings.get(buy_sym)
                    if cur:
                        total_shares = cur["qty"] + buy_qty
                        avg_price = (cur["avg_price"] * cur["qty"] + price * buy_qty) / total_shares
                        cur["qty"] = total_shares
                        cur["avg_price"] = round(avg_price, 2)
                    else:
                        st.session_state.holdings[buy_sym] = {"qty": buy_qty, "avg_price": round(price, 2)}
                    st.session_state.cash -= cost
                    st.success(f"Bought {buy_qty} {buy_sym} @ ${price:.2f} (cost ${cost:.2f})")

# ----------------------------
# Sell page
# ----------------------------
elif page == "Sell":
    require_login()
    st.title("🔻 Sell Stocks")

    if not st.session_state.holdings:
        st.info("No holdings to sell.")
    else:
        sel = st.selectbox("Select a stock to sell", list(st.session_state.holdings.keys()))
        max_qty = st.session_state.holdings[sel]["qty"]
        sell_qty = st.number_input("Quantity", min_value=1, max_value=max_qty, value=1)
        if st.button("Sell"):
            hist = fetch_history(sel, period="5d", interval="1d")
            if hist is None:
                st.error("Could not fetch price.")
            else:
                price = float(hist["Close"].iloc[-1])
                proceeds = price * sell_qty
                st.session_state.cash += proceeds
                st.session_state.holdings[sel]["qty"] -= sell_qty
                if st.session_state.holdings[sel]["qty"] == 0:
                    del st.session_state.holdings[sel]
                st.success(f"Sold {sell_qty} {sel} @ ${price:.2f} (received ${proceeds:.2f})")

# ----------------------------
# Search page (candlestick + add to watchlist)
# ----------------------------
elif page == "Search":
    require_login()
    st.title("🔍 Search & Chart")

    search_sym = st.text_input("Enter symbol (e.g. AAPL)").upper()
    c1, c2 = st.columns([1, 1])
    with c1:
        period = st.selectbox("Period", ["1y", "6mo", "3mo", "1mo", "5d"], index=0)
    with c2:
        # choose safe intervals based on period
        if period == "5d":
            interval = st.selectbox("Interval", ["1m", "5m", "15m", "1h"], index=1)
        else:
            interval = st.selectbox("Interval", ["1d", "1wk"], index=0)

    if st.button("Lookup"):
        if not search_sym:
            st.error("Enter a symbol.")
        else:
            df = fetch_history(search_sym, period=period, interval=interval)
            if df is None or df.empty:
                st.error("Symbol not found or no data available.")
            else:
                quote = fetch_quote(search_sym)
                if quote:
                    st.markdown(f"**{quote['symbol']} — {quote['name']}**")
                    st.markdown(f"**Price:** ${quote['price']:.2f}   **Change:** {quote['change']} ({quote['pct']}%)")

                fig = plot_candlestick(df, search_sym, ma_windows=[20, 50])
                st.plotly_chart(fig, use_container_width=True)

                # quick actions: add to watchlist, buy button
                ca, cb = st.columns(2)
                with ca:
                    if st.button("Add to Watchlist"):
                        s = search_sym.upper()
                        if s not in st.session_state.watchlist:
                            st.session_state.watchlist.append(s)
                            st.success(f"Added {s} to watchlist.")
                        else:
                            st.info("Already in watchlist.")
                with cb:
                    buy_q = st.number_input("Buy quantity", min_value=1, step=1, value=1, key=f"buy_{search_sym}")
                    if st.button("Buy from Search"):
                        hist = fetch_history(search_sym, period="5d", interval="1d")
                        if hist is None:
                            st.error("Cannot fetch price to buy.")
                        else:
                            price = float(hist["Close"].iloc[-1])
                            cost = price * buy_q
                            if st.session_state.cash < cost:
                                st.error("Insufficient cash.")
                            else:
                                cur = st.session_state.holdings.get(search_sym)
                                if cur:
                                    total_shares = cur["qty"] + buy_q
                                    avg_price = (cur["avg_price"] * cur["qty"] + price * buy_q) / total_shares
                                    cur["qty"] = total_shares
                                    cur["avg_price"] = round(avg_price, 2)
                                else:
                                    st.session_state.holdings[search_sym] = {"qty": buy_q, "avg_price": round(price, 2)}
                                st.session_state.cash -= cost
                                st.success(f"Bought {buy_q} {search_sym} @ ${price:.2f}")

# ----------------------------
# Watchlist page
# ----------------------------
elif nav_choice == "Watchlist":
    require_login()
    st.title("⭐ Watchlist")

    add_sym = st.text_input("Add symbol to watchlist").upper()
    if st.button("Add to Watchlist"):
        if add_sym and add_sym not in st.session_state.watchlist:
            st.session_state.watchlist.append(add_sym)
            st.success(f"Added {add_sym} to watchlist.")
        elif add_sym in st.session_state.watchlist:
            st.info("Already in watchlist.")

    st.markdown("---")
    if not st.session_state.watchlist:
        st.info("Your watchlist is empty.")
    else:
        rows = []
        for s in st.session_state.watchlist:
            q = fetch_quote(s)
            if q:
                rows.append({"Symbol": q["symbol"], "Name": q["name"], "Price": q["price"], "Change": f"{q['change']} ({q['pct']}%)"})
            else:
                rows.append({"Symbol": s, "Name": "-", "Price": "-", "Change": "-"})

        df_watch = pd.DataFrame(rows)
        st.table(df_watch)

        # Remove buttons (one per symbol)
        for s in st.session_state.watchlist.copy():
            if st.button(f"Remove {s}", key=f"rm_{s}"):
                st.session_state.watchlist.remove(s)
                st.success(f"Removed {s}")
                st.rerun()

