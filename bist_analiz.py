import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="BIST İşlem Öncesi Analiz", page_icon="📈", layout="centered")

st.title("📈 BIST Akıllı Zamanlama ve 3'lü Onay Motoru")
st.write("İşlem yapmadan önce giriş yerini, olası tuzakları ve hedef süreni test et.")

# Kullanıcı Girişleri
hisse_girdi = st.text_input("Hisse Kodunu Gir (Örn: ASELS)", "ASELS").strip().upper()
col1, col2 = st.columns(2)
with col1:
    planlanan_giris = st.number_input("Planlanan Alış Fiyatı (TL)", value=380.0, step=1.0)
with col2:
    hedef_fiyat = st.number_input("Hedeflenen Fiyat (TL)", value=405.0, step=1.0)

if st.button("🚀 Analizi Çalıştır", type="primary"):
    if not hisse_girdi.endswith(".IS") and not hisse_girdi.endswith(".IST"):
        hisse_kodu = hisse_girdi + ".IS"
    else:
        hisse_kodu = hisse_girdi

    with st.spinner(f"[{hisse_kodu}] verileri taranıyor..."):
        try:
            data = yf.download(hisse_kodu, period="3mo", interval="1d", progress=False)
            if data.empty or len(data) < 50:
                st.error("Yeterli veri alınamadı veya hisse kodu hatalı!")
                st.stop()
            # FIX: MultiIndex kolonlarını düzleştirirken doğru metod kullanılmalı
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
        except Exception as e:
            st.error(f"Bağlantı hatası: {e}")
            st.stop()

    guncel_fiyat = float(data['Close'].iloc[-1])

    # 1. Kural: EMA 50 Trend Filtresi
    data['EMA_50'] = data['Close'].ewm(span=50, adjust=False).mean()
    guncel_ema = float(data['EMA_50'].iloc[-1])
    trend_onayi = guncel_fiyat > guncel_ema

    # 2. Kural: Hacim Yoğunluğu
    ortalama_hacim = float(data['Volume'].rolling(window=14).mean().iloc[-1])
    son_hacim = float(data['Volume'].iloc[-1])
    hacim_onayi = son_hacim > ortalama_hacim

    # 3. Kural: RSI (14) Momentum
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    # FIX: loss=0 durumunda bölme hatasını (inf/NaN) önlemek için güvenli bölme
    rs = gain / loss.replace(0, np.nan)
    data['RSI'] = 100 - (100 / (1 + rs))
    data['RSI'] = data['RSI'].fillna(100)  # loss=0 ise RSI 100 kabul edilir (saf yükseliş)
    guncel_rsi = float(data['RSI'].iloc[-1])

    # FIX: Gerçek ATR hesabı (True Range = önceki kapanışı da hesaba katar)
    prev_close = data['Close'].shift(1)
    tr1 = data['High'] - data['Low']
    tr2 = (data['High'] - prev_close).abs()
    tr3 = (data['Low'] - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = float(true_range.rolling(window=14).mean().iloc[-1])

    mesafe = abs(hedef_fiyat - planlanan_giris)
    tahmini_gun = mesafe / atr if atr > 0 else 0
    tuzak_destek = planlanan_giris - (atr * 1.0)
    derin_tuzak = planlanan_giris - (atr * 2.0)

    # Sonuçları Göster
    st.success(f"Rapor Başarıyla Oluşturuldu: {hisse_kodu}")

    m1, m2, m3 = st.columns(3)
    m1.metric("Anlık Fiyat", f"{guncel_fiyat:.2f} TL")
    m2.metric("Günlük Marj (ATR)", f"{atr:.2f} TL")
    m3.metric("Tahmini Süre", f"~{tahmini_gun:.1f} Gün")

    st.markdown("---")
    st.subheader("🔍 3'lü Onay Durumu")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if trend_onayi:
            st.metric("1. Trend (EMA 50)", "ONAYLI", "Yukarı Yönlü")
        else:
            st.metric("1. Trend (EMA 50)", "ONAYSIZ", "Düşüş Trendi")
    with col_b:
        if hacim_onayi:
            st.metric("2. Hacim", "GÜÇLÜ", "Ortalama Üstü")
        else:
            st.metric("2. Hacim", "DÜŞÜK", "Zayıf İlgi")
    with col_c:
        st.metric("3. Momentum (RSI)", f"{guncel_rsi:.1f}", "İdeal: 30-70")

    st.markdown("---")
    st.subheader("⏱️ Risk ve Tuzak Analizi")
    st.info(f"👉 **1. Seviye Tuzak/İğne Sınırı:** `{tuzak_destek:.2f} TL`")
    st.warning(f"👉 **2. Seviye Derin Düzeltme:** `{derin_tuzak:.2f} TL`")

    if planlanan_giris < guncel_fiyat:
        st.write("💡 **Strateji Tavsiyesi:** Geri çekilme senaryosu aktif. Fiyat yukarıdaki tuzak sınırına iğne atıp stop patlatabilir. Tüm bütçeyle tek seferde girme, alt kademeler için nakit ayır!")
