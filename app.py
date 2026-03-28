import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from textblob import TextBlob
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURASI SUPER-APP & UI STYLING
# ==========================================
st.set_page_config(page_title="BTC Pro-Quant Master", layout="wide", page_icon="₿", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1, h2, h3 {color: #f1c40f !important;}
    .stProgress .st-bo {background-color: #f1c40f;}
    </style>
""", unsafe_allow_html=True)

TICKER = "BTC-USD"

# ==========================================
# 2. ENGINE PENGAMBIL DATA
# ==========================================
@st.cache_data(ttl=900)
def fetch_btc_data():
    try:
        tkr = yf.Ticker(TICKER)
        df = tkr.history(period="10y")
        if df.empty: return pd.DataFrame()
        df.reset_index(inplace=True)
        if df['Date'].dt.tz is not None:
            df['Date'] = df['Date'].dt.tz_convert(None)
        return df
    except Exception as e:
        st.error(f"Koneksi API Gagal: {e}")
        return pd.DataFrame()

# ==========================================
# MODUL A: TIME-PRICE MATRIX & DCA ZONES
# ==========================================
def render_time_cycle(df, current_price):
    st.markdown("### ⏳ Matrix Siklus & Sinkronisasi Harga")
    
    col1, col2 = st.columns(2)
    with col1:
        st.success("📈 Parameter Dasar (Fase Akumulasi)")
        atl_date = st.date_input("Tanggal Dasar (ATL)", value=datetime(2022, 11, 21))
        atl_price = st.number_input("Harga Dasar (ATL) $", value=15476, step=500, help="Harga terendah di siklus sebelumnya.")
        bull_target = st.number_input("Target Durasi Bull (Hari)", value=1064, min_value=1)
        
    with col2:
        st.error("📉 Parameter Puncak (Fase Distribusi)")
        ath_date = st.date_input("Tanggal Puncak (ATH)", value=datetime(2024, 3, 14)) # Default diubah ke puncak nyata 2024
        ath_price = st.number_input("Harga Puncak (ATH) $", value=73750, step=500, help="Harga tertinggi yang dicapai baru-baru ini.")
        bear_target = st.number_input("Target Durasi Bear (Hari)", value=364, min_value=1)

    # Kalkulasi Waktu
    today = datetime.today().date()
    days_from_atl = (today - atl_date).days
    bull_progress = min(max(days_from_atl / bull_target, 0.0), 1.0)
    
    days_from_ath = (today - ath_date).days
    bear_progress = min(max(days_from_ath / bear_target, 0.0), 1.0)

    # Kalkulasi Persentase Harga Live
    live_gain_atl = ((current_price - atl_price) / atl_price) * 100
    live_drop_ath = ((current_price - ath_price) / ath_price) * 100

    st.markdown("---")
    
    if bull_progress >= 1.0: st.warning(f"🚨 **ALARM BULL SELESAI:** Target {bull_target} hari telah tercapai.")
    if bear_progress >= 1.0: st.success(f"🔥 **ALARM BEAR SELESAI:** Target {bear_target} hari tercapai. Bersiap untuk reversal!")

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Timeline Fase Bull", f"{days_from_atl} / {bull_target} Hari", f"Live Gain dari ATL: +{live_gain_atl:.1f}%")
        st.progress(bull_progress)
        st.caption(f"Proyeksi ATH Berikutnya: **{(atl_date + timedelta(days=bull_target)).strftime('%d %B %Y')}**")
        
    with c2:
        st.metric("Timeline Fase Bear", f"{days_from_ath} / {bear_target} Hari", f"Live Drop dari ATH: {live_drop_ath:.1f}%", delta_color="inverse")
        st.progress(bear_progress)
        st.caption(f"Proyeksi Dasar Berikutnya: **{(ath_date + timedelta(days=bear_target)).strftime('%d %B %Y')}**")

    # 🌟 FITUR DCA (MENGAMBIL DATA DARI INPUT DI ATAS) 🌟
    st.markdown("---")
    st.markdown("### 🎯 Kalkulator Auto-DCA & Proyeksi Siklus")
    
    p1, p2, p3 = st.columns(3)
    
    with p1:
        st.markdown("**1. Parameter Penurunan & Kenaikan**")
        st.info(f"Menggunakan acuan Puncak: **${ath_price:,.0f}**")
        drop_estimation = st.slider("Estimasi Penurunan ke Dasar (%)", min_value=40, max_value=90, value=75)
        bull_multiplier = st.slider("Estimasi Kenaikan Siklus Depan (x)", min_value=1.5, max_value=10.0, value=2.5, step=0.1)

    projected_bottom = ath_price * (1 - (drop_estimation / 100))
    buy_zone_max = projected_bottom * 1.25 
    projected_next_ath = ath_price * bull_multiplier
    
    with p2:
        st.markdown("**2. Zona Beli Aman (Buy Zone)**")
        st.metric("Proyeksi Harga Dasar (Bottom)", f"${projected_bottom:,.0f}", f"-{drop_estimation}% dari Puncak")
        st.success(f"🛒 **ZONA AKUMULASI (DCA):**\n\n**${projected_bottom:,.0f} s/d ${buy_zone_max:,.0f}**")
        
    with p3:
        st.markdown("**3. Target Jual (Take Profit)**")
        st.metric("Proyeksi Puncak Berikutnya", f"${projected_next_ath:,.0f}", f"{bull_multiplier}x lipat dari ATH", delta_color="normal")
        
        if current_price <= buy_zone_max: status_beli = "🟢 SANGAT MURAH (Waktunya Beli)"
        elif current_price >= (projected_next_ath * 0.7): status_beli = "🔴 SANGAT MAHAL (Waktunya Jual)"
        else: status_beli = "⚪ AREA NETRAL (Hold/Tunggu)"
            
        st.info(f"**Status Harga Live Saat Ini:**\n\n**{status_beli}**")

# ==========================================
# MODUL B: FRACTAL OVERLAY ENGINE
# ==========================================
def render_fractal_matcher(df):
    st.markdown("### 🔍 AI Fractal Matcher")
    
    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        hist_dates = st.date_input("Jendela Masa Lalu (Hist)", [datetime(2021, 1, 1), datetime(2021, 12, 31)])
    with c2:
        curr_dates = st.date_input("Jendela Masa Kini (Curr)", [datetime(2024, 1, 1), datetime.today().date()])
    with c3:
        smoothing = st.slider("Filter Noise (SMA)", 1, 30, 7)

    if len(hist_dates) != 2 or len(curr_dates) != 2: return st.warning("Pilih rentang tanggal lengkap.")

    df_hist = df[(df['Date'].dt.date >= hist_dates[0]) & (df['Date'].dt.date <= hist_dates[1])].copy()
    df_curr = df[(df['Date'].dt.date >= curr_dates[0]) & (df['Date'].dt.date <= curr_dates[1])].copy()

    if df_hist.empty or df_curr.empty: return st.error("Data tidak ditemukan.")

    hist_norm = (df_hist['Close'] / df_hist['Close'].iloc[0] * 100).rolling(window=smoothing).mean().dropna().reset_index(drop=True)
    curr_norm = (df_curr['Close'] / df_curr['Close'].iloc[0] * 100).rolling(window=smoothing).mean().dropna().reset_index(drop=True)

    min_len = min(len(hist_norm), len(curr_norm))
    if min_len > 15:
        hist_plot, curr_plot = hist_norm.iloc[:min_len], curr_norm.iloc[:min_len]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=hist_plot, mode='lines', name='Masa Lalu (Pattern)', line=dict(color='#7f8c8d', width=2)))
        fig.add_trace(go.Scatter(y=curr_plot, mode='lines', name='Masa Kini (Live)', line=dict(color='#f1c40f', width=3)))
        
        fig.update_layout(title="Perbandingan Aksi Harga (Normalized %)", xaxis_title="Trading Days", yaxis_title="Pertumbuhan (%)", template="plotly_dark", height=450)
        st.plotly_chart(fig, use_container_width=True)

        corr_val = hist_plot.corr(curr_plot) * 100
        if pd.isna(corr_val): st.warning("**Skor Korelasi: NaN%**")
        else: st.info(f"**Tingkat Kemiripan Pola (Korelasi Pearson): {corr_val:.2f}%**")
    else: st.warning("Rentang waktu terlalu pendek.")

# ==========================================
# MODUL C: NLP SENTIMENT SCORING
# ==========================================
def render_sentiment_analyzer():
    st.markdown("### 📰 Live Macro Sentiment")
    tkr = yf.Ticker(TICKER)
    with st.spinner("Scraping berita finansial terbaru..."):
        try: news_data = tkr.news
        except Exception: news_data = []

    if not news_data: return st.info("Tidak ada rilis berita signifikan hari ini.")

    news_list, sentiments = [], []
    for item in news_data[:6]: 
        title = item.get('title')
        if not title and 'content' in item: title = item['content'].get('title', '')
        if not title: continue
            
        link = item.get('link', '#')
        polarity = TextBlob(title).sentiment.polarity
        sentiments.append(polarity)
        
        if polarity > 0.05: badge, color = "BULLISH", "#27ae60"
        elif polarity < -0.05: badge, color = "BEARISH", "#c0392b"
        else: badge, color = "NEUTRAL", "#7f8c8d" 
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
        if not news_list: st.write("- Berita sedang diproses...")
        for n in news_list: st.markdown(f"- {n}")

# ==========================================
# MAIN EXECUTION & LIVE PRICE TRAY
# ==========================================
def main():
    st.sidebar.title("₿ Pro-Quant Master")
    st.sidebar.markdown("Sistem Analitik Siklus Bitcoin.")
    
    with st.spinner("Menghubungkan ke node market..."):
        df = fetch_btc_data()
        
    if df.empty: return st.error("Gagal memuat data.")

    current_price = df['Close'].iloc[-1]
    prev_price = df['Close'].iloc[-2]
    price_change = current_price - prev_price
    pct_change = (price_change / prev_price) * 100

    st.sidebar.markdown("---")
    st.sidebar.markdown("### LIVE MARKET")
    st.sidebar.metric(label="BTC/USD", value=f"${current_price:,.2f}", delta=f"{price_change:,.2f} ({pct_change:.2f}%)")
    st.sidebar.markdown("---")
    st.sidebar.caption("Data diperbarui setiap 15 menit.\nBuilt exclusively for Bitcoin.")

    st.title("Bitcoin (BTC) Cycle Tracker")
    t1, t2, t3 = st.tabs(["⏳ Matrix & Target", "🔍 Fractal Overlay", "📰 Macro Sentiment"])
    
    with t1: render_time_cycle(df, current_price)
    with t2: render_fractal_matcher(df)
    with t3: render_sentiment_analyzer()

if __name__ == '__main__':
    main()
