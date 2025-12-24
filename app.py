import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Analiz", page_icon="🛒", layout="wide")

# --- CSS İLE BOŞLUKLARI SIFIRLAMA ---
st.markdown("""
<style>
    /* Sayfa kenar boşluklarını daralt */
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    
    /* Kartların içindeki gereksiz boşlukları sil */
    div[data-testid="stVerticalBlock"] > div {
        gap: 0.2rem;
    }
    
    /* Konteyner (Kart) Kenarlığı ve Gölgelendirme */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px;
        background-color: white;
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
        border: 1px solid #eee;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #f70;
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.1);
    }
    
    /* Resim Hizalama */
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 5px;
    }
    img {
        object-fit: contain;
        max-height: 150px !important;
    }

    /* Metin Stilleri */
    .card-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
        line-height: 1.3;
        height: 38px; /* 2 satır sabit yükseklik */
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 4px;
    }
    .card-price-box {
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin-top: 5px;
        margin-bottom: 10px;
    }
    .price-current { font-size: 18px; font-weight: 800; color: #ff6000; }
    .price-old { font-size: 12px; text-decoration: line-through; color: #999; }
    .discount-tag {
        background-color: #d32f2f; color: white;
        padding: 2px 6px; border-radius: 4px;
        font-size: 11px; font-weight: bold;
    }

    /* Detay Sayfası Başlık */
    .detail-title { font-size: 26px; font-weight: 800; color: #222; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FONKSİYONLAR ---
def temizle_ve_cevir(val):
    try:
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('TL', '').replace('₺', '').strip()
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except:
        return 0.0

@st.cache_data(ttl=600)
def veri_getir():
    sheet = google_sheets_baglan()
    if not sheet: return pd.DataFrame()
    try:
        data = sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        df.columns = df.columns.str.strip()
        
        for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
            if c in df.columns: df[c] = df[c].apply(temizle_ve_cevir)
        
        if "Tarih" in df.columns:
            df["Tarih"] = pd.to_datetime(df["Tarih"], errors='coerce')
        return df
    except:
        return pd.DataFrame()

# --- STATE YÖNETİMİ ---
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = None

# Geri Dönme Fonksiyonu
def geri_don():
    st.session_state.selected_product = None

# Ürün Seçme Fonksiyonu
def urune_git(isim):
    st.session_state.selected_product = isim

# --- UYGULAMA BAŞLANGICI ---
df_raw = veri_getir()

# Veri Yoksa Güncelleme Ekranı
if df_raw.empty:
    st.warning("⚠️ Veri bulunamadı. Lütfen güncelleme yapın.")
    if st.button("🚀 Verileri Şimdi Güncelle"):
        calistir()
        st.rerun()
    st.stop()

# Vitrin Verisi (Tekil Ürünler)
df_vitrin = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# ==========================================
# SAYFA 1: ÜRÜN DETAY SAYFASI
# ==========================================
if st.session_state.selected_product:
    urun_adi = st.session_state.selected_product
    # Geçmiş veriyi filtrele
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    
    if gecmis.empty:
        st.error("Ürün verisi bulunamadı.")
        if st.button("Geri Dön"): geri_don()
        st.stop()
        
    son_hal = gecmis.iloc[-1]

    # Üst Bar (Geri Butonu)
    st.button("⬅ Geri Dön", on_click=geri_don)

    # İki Kolonlu Yapı
    c1, c2 = st.columns([1, 2], gap="large")
    
    with c1:
        st.image(son_hal['Resim'], use_container_width=True)
        # Market Butonu
        st.link_button("🛒 Migros Sitesine Git", son_hal['Link'], use_container_width=True, type="primary")

    with c2:
        st.markdown(f"<div class='detail-title'>{son_hal['Ürün Adı']}</div>", unsafe_allow_html=True)
        st.caption(f"Kategori: {son_hal['Kategori']}")
        
        # Fiyat Bilgisi
        fiyat = son_hal['Satış Fiyatı']
        etiket = son_hal['Etiket Fiyatı']
        
        col_f1, col_f2, col_f3 = st.columns(3)
        col_f1.metric("Şu Anki Fiyat", f"{fiyat:.2f} ₺", delta=None)
        if etiket > fiyat:
            col_f2.metric("Normal Fiyat", f"{etiket:.2f} ₺")
            col_f3.metric("İndirim Oranı", f"%{son_hal['İndirim %']:.0f}", delta_color="normal")
            
        st.divider()
        
        # İstatistikler
        min_fiyat = gecmis['Satış Fiyatı'].min()
        max_fiyat = gecmis['Satış Fiyatı'].max()
        avg_fiyat = gecmis['Satış Fiyatı'].mean()
        
        st.info(f"📊 **İstatistik:** Bu ürün en düşük **{min_fiyat:.2f} ₺**, en yüksek **{max_fiyat:.2f} ₺** görmüş. Ortalama fiyatı: **{avg_fiyat:.2f} ₺**")

    # Grafik
    st.subheader("📉 Fiyat Geçmişi Grafiği")
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color="#ff6000", line_width=3)
    if "Etiket Fiyatı" in gecmis.columns:
        fig.add_scatter(x=gecmis["Tarih"], y=gecmis["Etiket Fiyatı"], name="Normal Fiyat", line=dict(dash='dash', color='gray'))
    st.plotly_chart(fig, use_container_width=True)


# ==========================================
# SAYFA 2: VİTRİN (ANA SAYFA)
# ==========================================
else:
    # --- KENAR ÇUBUĞU ---
    with st.sidebar:
        st.title("🛒 Migros Avcısı")
        arama = st.text_input("🔍 Ürün Ara", placeholder="Örn: Yağ")
        
        kat_list = ["Tümü"] + sorted(df_vitrin["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_vitrin.columns else ["Tümü"]
        kategori = st.selectbox("Kategori", kat_list)
        
        sirala = st.selectbox("Sıralama", ["Akıllı (Fırsatlar)", "Fiyat Artan", "Fiyat Azalan"])
        sadece_indirim = st.toggle("Sadece İndirimli", value=False)
        
        st.divider()
        if st.button("🔄 Verileri Güncelle"):
            with st.spinner("Güncelleniyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()

    # --- FİLTRELEME ---
    df = df_vitrin.copy()
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]
    if sadece_indirim: df = df[df["İndirim %"] > 0]
    
    # Sıralama
    if sirala == "Fiyat Artan": df = df.sort_values("Satış Fiyatı")
    elif sirala == "Fiyat Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

    # --- ÜST BİLGİ ---
    c1, c2 = st.columns([3, 1])
    c1.markdown(f"### 📦 Toplam {len(df)} Ürün")

    # --- SAYFALAMA ---
    SAYFA_BASI = 40 # Her sayfada 40 ürün (8 satır x 5 sütun)
    if "page" not in st.session_state: st.session_state.page = 0
    
    total_pages = math.ceil(len(df) / SAYFA_BASI)
    if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)
    
    start = st.session_state.page * SAYFA_BASI
    end = start + SAYFA_BASI
    page_data = df.iloc[start:end]

    # --- ÜRÜN KARTLARI (CONTAINER YAPISI) ---
    if page_data.empty:
        st.warning("Ürün bulunamadı.")
    else:
        # 5 Sütunlu Grid
        cols = st.columns(5)
        for i, row in enumerate(page_data.to_dict('records')):
            with cols[i % 5]:
                # KART ÇERÇEVESİ
                with st.container(border=True):
                    # 1. Resim (Görseli büyüttük)
                    st.image(row['Resim'])
                    
                    # 2. Ürün Başlığı (Sabit yükseklik)
                    st.markdown(f"<div class='card-title' title='{row['Ürün Adı']}'>{row['Ürün Adı']}</div>", unsafe_allow_html=True)
                    
                    # 3. Fiyat Alanı
                    if row['İndirim %'] > 0:
                        st.markdown(f"""
                        <div class="card-price-box">
                            <span class="price-current">{row['Satış Fiyatı']:.2f}₺</span>
                            <span class="price-old">{row['Etiket Fiyatı']:.0f}</span>
                            <span class="discount-tag">%{row['İndirim %']:.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                         st.markdown(f"""
                        <div class="card-price-box">
                            <span class="price-current">{row['Satış Fiyatı']:.2f}₺</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # 4. BUTON (KARTIN İÇİNDE)
                    # Unique key veriyoruz ki karışmasın
                    st.button("İncele", key=f"btn_{i}_{row['Link']}", on_click=urune_git, args=(row['Ürün Adı'],), use_container_width=True)

    st.divider()
    
    # --- SAYFALAMA BUTONLARI ---
    c_prev, c_txt, c_next = st.columns([1, 2, 1])
    if c_prev.button("◀ Önceki Sayfa", disabled=(st.session_state.page == 0)):
        st.session_state.page -= 1
        st.rerun()
    c_txt.markdown(f"<div style='text-align:center; padding-top:10px;'><b>Sayfa {st.session_state.page + 1} / {max(1, total_pages)}</b></div>", unsafe_allow_html=True)
    if c_next.button("Sonraki Sayfa ▶", disabled=(st.session_state.page >= total_pages - 1)):
        st.session_state.page += 1
        st.rerun()
