import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Avcısı", page_icon="🛍️", layout="wide")

# --- CSS (DAHA KÜÇÜK VE DÜZGÜN KARTLAR) ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    
    /* Kart Tasarımı */
    .product-card {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        height: 300px; /* Kart yüksekliğini azalttık */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    /* Resim */
    .img-container {
        height: 120px; /* Resim alanı küçüldü */
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-bottom: 8px;
    }
    .product-img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
    }
    
    /* Yazılar */
    .product-title {
        font-size: 13px; /* Yazı küçüldü */
        font-weight: 600;
        color: #333;
        line-height: 1.3;
        height: 34px; /* 2 satır */
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 4px;
    }
    
    /* Fiyatlar */
    .price-box { margin-top: auto; }
    .old-price { font-size: 11px; text-decoration: line-through; color: #999; }
    .new-price { font-size: 18px; font-weight: 700; color: #ff6000; }
    
    /* Link Butonu */
    .go-btn {
        display: block;
        width: 100%;
        background-color: #f8f9fa;
        color: #333 !important;
        text-align: center;
        border: 1px solid #ddd;
        border-radius: 4px;
        padding: 4px;
        font-size: 11px;
        text-decoration: none;
        margin-top: 5px;
    }
    .go-btn:hover { background-color: #eee; }
    
    /* İndirim Rozeti */
    .badge-discount {
        position: absolute;
        top: 5px; right: 5px;
        background-color: #d32f2f;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛍️ Migros Fiyat Avcısı")

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

# --- GRAFİK PENCERESİ (POP-UP) ---
@st.dialog("Fiyat Geçmişi Analizi")
def grafik_goster(urun_adi, df_raw):
    st.caption(f"Ürün: {urun_adi}")
    
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    
    if not gecmis.empty:
        fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", title="Fiyat Değişimi", markers=True)
        # Etiket fiyatını da ekle
        if "Etiket Fiyatı" in gecmis.columns:
             fig.add_scatter(x=gecmis["Tarih"], y=gecmis["Etiket Fiyatı"], 
                             mode='lines', name='Etiket Fiyatı', line=dict(dash='dash', color='gray'))
        st.plotly_chart(fig, use_container_width=True)
        
        son_veri = gecmis.iloc[-1]
        if son_veri.get("İndirim Tipi"):
             st.info(f"💡 Kampanya: {son_veri['İndirim Tipi']}")
    else:
        st.warning("Bu ürün için yeterli geçmiş veri yok.")

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.header("Filtreler")
    df_raw = veri_getir()
    
    if st.button("🔄 Verileri Güncelle"):
        with st.spinner("Market taranıyor..."):
            calistir()
            st.success("Tamam!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

    if df_raw.empty:
        st.warning("Veri yok.")
        st.stop()

    arama = st.text_input("Ürün Ara", placeholder="Örn: Nutella")
    
    kat_list = ["Tümü"] + sorted(df_raw["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_raw.columns else ["Tümü"]
    kategori = st.selectbox("Kategori", kat_list)
    
    sirala = st.selectbox("Sıralama", ["Akıllı (Fırsatlar)", "Artan Fiyat", "Azalan Fiyat"])
    sadece_indirim = st.checkbox("Sadece İndirimli", value=True)

# --- VERİ HAZIRLIĞI ---
df = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
if kategori != "Tümü": df = df[df["Kategori"] == kategori]
if sadece_indirim: df = df[df["İndirim %"] > 0]

if sirala == "Artan Fiyat": df = df.sort_values("Satış Fiyatı")
elif sirala == "Azalan Fiyat": df = df.sort_values("Satış Fiyatı", ascending=False)
else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

# --- SAYFALAMA ---
SAYFA_BASI = 40
if "page" not in st.session_state: st.session_state.page = 0

total_pages = math.ceil(len(df) / SAYFA_BASI)
if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)

start = st.session_state.page * SAYFA_BASI
end = start + SAYFA_BASI
page_data = df.iloc[start:end]

# --- ÜST PANEL ---
c1, c2, c3 = st.columns([2, 1, 1])
c1.subheader(f"{len(df)} Ürün Bulundu")
c2.button("◀", key="prev", on_click=lambda: st.session_state.update(page=max(0, st.session_state.page-1)))
c3.button("▶", key="next", on_click=lambda: st.session_state.update(page=min(total_pages-1, st.session_state.page+1)))

# --- KARTLAR (GRID) ---
st.divider()

if page_data.empty:
    st.info("Ürün bulunamadı.")
else:
    cols = st.columns(4) # 4 Sütunlu Izgara
    for i, row in enumerate(page_data.to_dict('records')):
        with cols[i % 4]:
            # HTML KODU (GİRİNTİSİZ - HATA VERMEMESİ İÇİN)
            indirim_badge = f'<div class="badge-discount">%{row["İndirim %"]:.0f}</div>' if row['İndirim %'] > 0 else ""
            eski_fiyat = f'<div class="old-price">{row["Etiket Fiyatı"]:.2f} ₺</div>' if row['Etiket Fiyatı'] > row['Satış Fiyatı'] else ""
            
            html_card = f"""
<div class="product-card" style="position: relative;">
    {indirim_badge}
    <div class="img-container">
        <img src="{row['Resim']}" class="product-img" loading="lazy">
    </div>
    <div class="product-title" title="{row['Ürün Adı']}">{row['Ürün Adı']}</div>
    <div class="price-box">
        {eski_fiyat}
        <div class="new-price">{row['Satış Fiyatı']:.2f} ₺</div>
    </div>
    <a href="{row['Link']}" target="_blank" class="go-btn">Migros'a Git</a>
</div>
"""
            st.markdown(html_card, unsafe_allow_html=True)
            
            # GRAFİK BUTONU
            if st.button("📉 Analiz", key=f"btn_{row['Link']}_{i}"):
                grafik_goster(row['Ürün Adı'], df_raw)

# --- SAYFA BİLGİSİ ALT ---
st.caption(f"Sayfa {st.session_state.page + 1} / {max(1, total_pages)}")
