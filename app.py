import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from textblob import TextBlob
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURASI SUPER-APP & UI STYLING
# ==========================================
st.set_page_config(page_title="Pro-Quant Master Dashboard", layout="wide", page_icon="🏦", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1, h2, h3 {color: #f1c40f !important;}
    .stProgress .st-bo {background-color: #f1c40f;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DICTIONARY ASET UNTUK MULTI-MARKET
# ==========================================
ASSETS = {
    "Bitcoin (BTC/USD)": "BTC-USD",
    "Gold Spot (XAU/USD)": "XAUUSD=X",
    "S&P 500 Index": "^GSPC"
}

# ==========================================
# 3. ENGINE PENGAMBIL DATA (HANYA CACHE DATAFRAME)
# ==========================================
@st.cache_data(ttl=1800) # Cache 30 menit
def fetch_market_engine(ticker_symbol):
    try:
        tkr = yf.Ticker(ticker_symbol)
        df = tkr.history(period="10y")
        if df.empty:
            return pd.DataFrame()
            
        df.reset_index(inplace=True)
        # Handle timezone (hapus tz info agar aman diproses)
        if df['Date'].dt.tz is not None:
            df['Date'] = df['Date'].dt.tz_convert(None)
            
        return df # HANYA RETURN DF, JANGAN RETURN MESIN TKR
    except Exception as e:
        st.error(f"Engine Error (Data Fetch): {e}")
        return pd.DataFrame()

# ==========================================
# MODUL A: TIME-CYCLE MATRIX
# ==========================================
def render_time_cycle(df, asset_name):
    st.markdown(f"### ⏳ Matrix Siklus - {asset_name}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.success("📈 Bullish Cycle Parameters")
        atl_date = st.date_input("Titik Terendah (ATL)", value=datetime(2022, 11, 21))
        bull_target = st.number_input("Target Durasi Bull (Hari)", value=1064, min_value=1)
        
    with col2:
        st.error("📉 Bearish Cycle Parameters")
        ath_date = st.date_input("Titik Tertinggi (ATH)", value=datetime(2025, 10, 6))
        bear_target = st.number_input("Target Durasi Bear (Hari)", value=364, min_value=1)

    today = datetime.today().date()
    
    # Kalkulasi Matematika
    days_from_atl = (today - atl_date).days
    bull_progress = min(max(days_from_atl / bull_target, 0.0), 1.0)
    
    days_from_ath = (today - ath_date).days
    bear_progress = min(max(days_from_ath / bear_target, 0.0), 1.0)

    st.markdown("---")
    c1, c2 = st.columns(2)
    
    with c1:
        st.metric("Progress Siklus Bull (Naik)", f"{days_from_atl} Hari", f"Target: {bull_target} Hari")
        st.progress(bull_progress)
        st.caption(f"Proyeksi ATH Berikutnya: **{(atl_date + timedelta(days=bull_target)).strftime('%d %B %Y')}**")
        
    with c2:
        st.metric("Progress Siklus Bear (Turun)", f"{days_from_ath} Hari", f"Target: {bear_target} Hari", delta_color="inverse")
        st.progress(bear_progress)
        st.caption(f"Proyeksi Dasar Berikutnya: **{(ath_date + timedelta(days=bear_target)).strftime('%d %B %Y')}**")

# ==========================================
# MODUL B: FRACTAL OVERLAY ENGINE
# ==========================================
def render_fractal_matcher(df, asset_name):
    st.markdown(f"### 🔍 AI Fractal Matcher - {asset_name}")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        hist_dates = st.date_input("Jendela Masa Lalu (Hist)", [datetime(2021, 1, 1), datetime(2021, 12, 31)])
    with c2:
        curr_dates = st.date_input("Jendela Masa Kini (Curr)", [datetime(2024, 1, 1), datetime.today().date()])
    with c3:
        smoothing = st.slider("Filter Noise (SMA)", 1, 30, 7)

    if len(hist_dates) != 2 or len(curr_dates) != 2:
        st.warning("Mohon pilih rentang tanggal awal dan akhir dengan lengkap.")
        return

    df_hist = df[(df['Date'].dt.date >= hist_dates[0]) & (df['Date'].dt.date <= hist_dates[1])].copy()
    df_curr = df[(df['Date'].dt.date >= curr_dates[0]) & (df['Date'].dt.date <= curr_dates[1])].copy()

    if df_hist.empty or df_curr.empty:
        st.error("Data rentang tanggal tidak ditemukan. Coba rentang waktu lain.")
        return

    # Base-100 Normalization & Smoothing
    hist_norm = (df_hist['Close'] / df_hist['Close'].iloc[0] * 100).rolling(window=smoothing).mean().dropna()
    curr_norm = (df_curr['Close'] / df_curr['Close'].iloc[0] * 100).rolling(window=smoothing).mean().dropna()

    fig = go.Figure()
    fig.add_trace(go.Scatter(y=hist_norm, mode='lines', name='Masa Lalu (Pattern)', line=dict(color='rgba(255,255,255,0.3)', width=2)))
    fig.add_trace(go.Scatter(y=curr_norm, mode='lines', name='Masa Kini (Live)', line=dict(color='#f1c40f', width=3)))
    
    fig.update_layout(title="Perbandingan Aksi Harga (Normalized %)", xaxis_title="Trading Days", yaxis_title="Pertumbuhan (%)", template="plotly_dark", height=450)
    st.plotly_chart(fig, use_container_width=True)

    min_len = min(len(hist_norm), len(curr_norm))
    if min_len > 15:
        corr_val = hist_norm.iloc[:min_len].corr(curr_norm.iloc[:min_len]) * 100
        st.info(f"**Tingkat Kemiripan Pola (Korelasi Pearson): {corr_val:.2f}%**")

# ==========================================
# MODUL C: NLP SENTIMENT SCORING
# ==========================================
def render_sentiment_analyzer(ticker_symbol, asset_name):
    st.markdown(f"### 📰 Live Macro Sentiment - {asset_name}")
    
    # Panggil ticker di dalam fungsi ini agar tidak crash di cache
    tkr = yf.Ticker(ticker_symbol)
    
    with st.spinner("Scraping berita finansial terbaru..."):
        try:
            news_data = tkr.news
        except Exception:
            news_data = []

    if not news_data: return st.info("Tidak ada rilis berita signifikan hari ini.")

    news_list, sentiments = [], []

    for item in news_data[:6]: 
        title = item.get('title', '')
        link = item.get('link', '#')
        
        # NLP Scoring
        polarity = TextBlob(title).sentiment.polarity
        sentiments.append(polarity)
        
        # Kategorisasi
        if polarity > 0.05: badge, color = "BULLISH", "#27ae60"
        elif polarity < -0.05: badge, color = "BEARISH", "#c0392b"
        else: badge, color = "#7f8c8d", "NEUTRAL"
            
        news_list.append(f"**[{badge}]** [{title}]({link})")

    avg_score = sum(sentiments) / len(sentiments) if sentiments else 0
    
    c1, c2 = st.columns([1, 1.5])
    with c1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=avg_score, title={'text': "Indeks Sentimen"},
            gauge={'axis': {'range': [-1, 1]}, 'bar': {'color': "#ffffff"},
                   'steps': [{'range': [-1, -0.1], 'color': "#c0392b"}, 
                             {'range': [-0.1, 0.1], 'color': "#34495e"}, 
                             {'range': [0.1, 1], 'color': "#27ae60"}]}
        ))
        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.markdown("#### Radar Berita Terkini:")
        for n in news_list:
            st.markdown(f"- {n}")

# ==========================================
# MAIN EXECUTION & SIDEBAR
# ==========================================
def main():
    st.sidebar.title("🏦 Pro-Quant Master")
    st.sidebar.markdown("Pilih instrumen yang ingin dianalisis:")
    
    selected_asset_name = st.sidebar.selectbox("Market Ticker:", list(ASSETS.keys()))
    selected_ticker = ASSETS[selected_asset_name]
    
    st.sidebar.markdown("---")
    st.sidebar.caption("Data Source: Yahoo Finance API\n\nBuilt for Quantitative Analysis.")

    with st.spinner(f"Memuat dataset untuk {selected_asset_name}..."):
        df = fetch_market_engine(selected_ticker)
        
    if df.empty: return st.error("Gagal memuat data. Periksa koneksi internet Anda.")

    # UI Routing via Tabs
    st.title(f"Visualisasi Analisis: {selected_asset_name}")
    t1, t2, t3 = st.tabs(["⏳ Time-Cycle Matrix", "🔍 Fractal Overlay", "📰 Real-Time Sentiment"])
    
    with t1: render_time_cycle(df, selected_asset_name)
    with t2: render_fractal_matcher(df, selected_asset_name)
    
    # Kirim string Ticker-nya saja ke modul sentiment
    with t3: render_sentiment_analyzer(selected_ticker, selected_asset_name)

if __name__ == '__main__':
    main()
