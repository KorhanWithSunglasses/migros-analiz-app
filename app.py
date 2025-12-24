import streamlit as st
import pandas as pd
import time
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Avcısı", page_icon="🛍️", layout="wide")

# --- MODERN CSS TASARIMI (ÜRÜN KARTLARI İÇİN) ---
st.markdown("""
<style>
    /* Genel Sayfa */
    .main { background-color: #f8f9fa; }
    h1 { color: #ff6000; font-weight: 800; }
    
    /* Ürün Kartı */
    .product-card {
        background-color: white;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transition: transform 0.2s;
        text-align: center;
        height: 100%;
    }
    .product-card:hover { transform: translateY(-5px); }
    
    /* Ürün Resmi */
    .product-img {
        width: 100%;
        height: 180px;
        object-fit: contain;
        margin-bottom: 10px;
    }
    
    /* Ürün Adı */
    .product-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
        height: 40px;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 10px;
    }
    
    /* Fiyatlar */
    .old-price {
        text-decoration: line-through;
        color: #999;
        font-size: 13px;
    }
    .new-price {
        color: #ff6000;
        font-size: 20px;
        font-weight: 800;
    }
    
    /* İndirim Rozeti */
    .discount-badge {
        background-color: #ff4b4b;
        color: white;
        padding: 4px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: bold;
        position: absolute;
        top: 10px;
        right: 10px;
    }
    
    /* Satın Al Butonu */
    .buy-button {
        display: block;
        width: 100%;
        padding: 8px;
        background-color: #ff6000;
        color: white !important;
        text-align: center;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        margin-top: 10px;
    }
    .buy-button:hover { background-color: #e55700; }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Migros Fiyat Avcısı")
st.markdown("---")

# --- YARDIMCI FONKSİYONLAR ---
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
        return df
    except:
        return pd.DataFrame()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    if st.button("🚀 Verileri Şimdi Güncelle"):
        st.warning("⚠️ Tüm market taranıyor, 3-5 dakika sürebilir...")
        with st.spinner("Robot rafları geziyor..."):
            calistir()
            st.success("Güncelleme tamamlandı! Sayfa yenileniyor...")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()
    
    st.divider()
    st.header("🔍 Filtrele & Ara")
    df_raw = veri_getir()
    
    arama = st.text_input("Ürün Ara", placeholder="Örn: Nutella")
    
    kategori_listesi = ["Tümü"]
    if not df_raw.empty and "Kategori" in df_raw.columns:
        katlar = sorted(df_raw["Kategori"].astype(str).unique().tolist())
        kategori_listesi += katlar
    secilen_kategori = st.selectbox("Kategori", kategori_listesi)
    
    # Fırsat filtresi artık daha detaylı
    firsat_tipi = st.radio("Gösterim Modu", ["Tüm Ürünler", "Sadece İndirimdekiler", "Büyük Fırsatlar (%20+)"])

# --- ANA EKRAN ---
if df_raw.empty:
    st.info("Veri bekleniyor... Sol menüden güncelleme yapın.")
    st.stop()

# Veri İşleme
df_son = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")
for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
    if c in df_son.columns:
        df_son[c] = df_son[c].apply(temizle_ve_cevir)

# Filtreleme
if arama: df_son = df_son[df_son["Ürün Adı"].str.contains(arama, case=False)]
if secilen_kategori != "Tümü": df_son = df_son[df_son["Kategori"] == secilen_kategori]

if firsat_tipi == "Sadece İndirimdekiler":
    df_son = df_son[df_son["İndirim %"] > 0]
elif firsat_tipi == "Büyük Fırsatlar (%20+)":
    df_son = df_son[df_son["İndirim %"] >= 20]

# --- ÜRÜN KARTLARI GÖRÜNÜMÜ ---
st.subheader(f"Toplam {len(df_son)} ürün listeleniyor")
st.divider()

# Ürünleri 4'lü kolonlar halinde göster
kolon_sayisi = 4
urunler = df_son.to_dict('records')

for i in range(0, len(urunler), kolon_sayisi):
    cols = st.columns(kolon_sayisi)
    for j in range(kolon_sayisi):
        if i + j < len(urunler):
            urun = urunler[i + j]
            with cols[j]:
                # İndirim Rozeti
                rozet_html = ""
                if urun['İndirim %'] > 0:
                    rozet_html = f"""<div class="discount-badge">%{urun['İndirim %']:.0f} İndirim</div>"""
                
                # Fiyat Gösterimi
                fiyat_html = f"""<div class="new-price">{urun['Satış Fiyatı']:.2f} ₺</div>"""
                if urun['Etiket Fiyatı'] > urun['Satış Fiyatı']:
                    fiyat_html = f"""
                        <div class="old-price">{urun['Etiket Fiyatı']:.2f} ₺</div>
                        {fiyat_html}
                    """
                
                # Kampanya Bilgisi
                kampanya_html = ""
                if urun.get('İndirim Tipi'):
                     kampanya_html = f"""<p style="font-size: 12px; color: #28a745; margin: 5px 0;">⚡ {urun['İndirim Tipi']}</p>"""

                # KART HTML
                st.markdown(f"""
                <div class="product-card" style="position: relative;">
                    {rozet_html}
                    <img src="{urun['Resim']}" class="product-img" onerror="this.src='https://via.placeholder.com/150?text=No+Image'">
                    <div class="product-title" title="{urun['Ürün Adı']}">{urun['Ürün Adı']}</div>
                    {fiyat_html}
                    {kampanya_html}
                    <a href="{urun['Link']}" target="_blank" class="buy-button">Migros'a Git</a>
                </div>
                """, unsafe_allow_html=True)
