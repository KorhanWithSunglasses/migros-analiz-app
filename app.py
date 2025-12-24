import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Avcısı", page_icon="🛍️", layout="wide")

# --- PROFESYONEL CSS TASARIMI ---
st.markdown("""
<style>
    /* Genel Ayarlar */
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    
    /* Ürün Kartı - Sabit Boyut ve Simetri */
    .product-card {
        background-color: #ffffff;
        border: 1px solid #e6e6e6;
        border-radius: 10px;
        padding: 12px;
        margin-bottom: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        transition: transform 0.2s, box-shadow 0.2s;
        height: 400px; /* Sabit yükseklik - Simetri için şart */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        position: relative;
    }
    .product-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.1);
        border-color: #ff6000;
    }

    /* İndirim Rozeti */
    .badge-discount {
        position: absolute;
        top: 10px;
        left: 10px;
        background-color: #d32f2f;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        z-index: 10;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    /* Resim Alanı */
    .img-container {
        height: 160px; /* Resim alanı sabit */
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 10px;
        background-color: #fff;
        border-radius: 8px;
        padding: 5px;
    }
    .product-img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain; /* Resmi kutuya sığdır ama kesme */
    }

    /* Ürün Başlığı */
    .product-title {
        font-size: 13px;
        font-weight: 600;
        color: #333;
        line-height: 1.4;
        height: 38px; /* Tam 2 satır */
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 5px;
    }
    
    /* Kategori Bilgisi */
    .product-cat {
        font-size: 11px;
        color: #888;
        margin-bottom: auto; /* Boşluğu doldur */
    }

    /* Fiyat Alanı */
    .price-container {
        margin-top: 10px;
        text-align: left;
    }
    .old-price {
        font-size: 12px;
        text-decoration: line-through;
        color: #999;
        margin-right: 5px;
    }
    .new-price {
        font-size: 20px;
        font-weight: 800;
        color: #ff6000;
    }

    /* Butonlar Alanı */
    .btn-container {
        display: flex;
        gap: 5px;
        margin-top: 10px;
    }
    
    /* Migros'a Git Butonu */
    .btn-go {
        flex: 1;
        background-color: #ff6000;
        color: white !important;
        text-align: center;
        padding: 8px 0;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        text-decoration: none;
        border: 1px solid #ff6000;
        transition: 0.2s;
    }
    .btn-go:hover { background-color: #e55700; }

    /* Analiz Butonu */
    .btn-analyze {
        flex: 1;
        background-color: #f8f9fa;
        color: #333 !important;
        text-align: center;
        padding: 8px 0;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        text-decoration: none;
        border: 1px solid #ddd;
        cursor: pointer;
        transition: 0.2s;
    }
    .btn-analyze:hover { background-color: #e2e6ea; border-color: #ccc; }

    /* Sayfalama Butonları */
    .pagination-btn {
        background-color: white;
        border: 1px solid #ddd;
        color: #333;
        padding: 8px 20px;
        border-radius: 20px;
        cursor: pointer;
        font-weight: 600;
        text-decoration: none;
        display: inline-block;
        margin: 0 10px;
    }
    .pagination-btn:hover {
        background-color: #f0f0f0;
        border-color: #bbb;
    }
    .page-info {
        font-weight: bold;
        color: #555;
        padding: 0 15px;
    }
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

# GRAFİK POP-UP
@st.dialog("Fiyat Geçmişi & Analiz")
def grafik_goster(urun_adi, df_tum):
    st.subheader(urun_adi)
    df_gecmis = df_tum[df_tum["Ürün Adı"] == urun_adi].sort_values("Tarih")
    
    if not df_gecmis.empty:
        fig = px.line(df_gecmis, x="Tarih", y="Satış Fiyatı", markers=True, title="Fiyat Değişim Grafiği")
        if "Etiket Fiyatı" in df_gecmis.columns:
            fig.add_scatter(x=df_gecmis["Tarih"], y=df_gecmis["Etiket Fiyatı"], 
                            mode='lines', name='Normal Fiyat', line=dict(dash='dash', color='gray'))
        st.plotly_chart(fig, use_container_width=True)
        
        # Son Durum Bilgisi
        son = df_gecmis.iloc[-1]
        st.info(f"📅 Son Güncelleme: {son['Tarih'].strftime('%d-%m-%Y')}")
        if son.get("İndirim Tipi"):
            st.success(f"🔥 Kampanya: {son['İndirim Tipi']}")
    else:
        st.warning("Geçmiş veri bulunamadı.")

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.title("🛒 Migros Avcısı")
    df_raw = veri_getir()
    
    if st.button("🔄 Verileri Güncelle", type="primary"):
        with st.spinner("Market taranıyor, bu işlem biraz sürebilir..."):
            calistir()
            st.success("Güncellendi!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

    if df_raw.empty:
        st.warning("Veritabanı boş. Lütfen güncelleyin.")
        st.stop()

    st.markdown("---")
    st.header("🔍 Filtreler")
    
    arama = st.text_input("Ürün Ara", placeholder="Örn: Nutella")
    
    kat_list = ["Tümü"] + sorted(df_raw["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_raw.columns else ["Tümü"]
    kategori = st.selectbox("Kategori", kat_list)
    
    sirala = st.selectbox("Sıralama", ["Akıllı (Fırsatlar)", "Fiyat Artan", "Fiyat Azalan"])
    
    # VARSAYILAN OLARAK KAPALI (Tüm ürünleri görsünler diye)
    sadece_indirim = st.toggle("Sadece İndirimli Ürünler", value=False)

# --- VERİ HAZIRLAMA ---
# Tarihe göre sırala ve her ürünün SADECE EN SON halini al
df = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# Filtreler
if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
if kategori != "Tümü": df = df[df["Kategori"] == kategori]
if sadece_indirim: df = df[df["İndirim %"] > 0]

# Sıralama
if sirala == "Fiyat Artan": df = df.sort_values("Satış Fiyatı")
elif sirala == "Fiyat Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

# --- SAYFALAMA MANTIĞI ---
SAYFA_BASI = 40
if "page" not in st.session_state: st.session_state.page = 0

total_pages = math.ceil(len(df) / SAYFA_BASI)
if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)

start = st.session_state.page * SAYFA_BASI
end = start + SAYFA_BASI
page_data = df.iloc[start:end]

# --- SAYFA İÇERİĞİ ---
st.markdown(f"### 📦 Toplam {len(df)} Ürün Listeleniyor")

# ÜST SAYFALAMA (Ortalanmış)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    sub_c1, sub_c2, sub_c3 = st.columns([1, 2, 1])
    if sub_c1.button("◀ Geri", key="top_prev", disabled=(st.session_state.page == 0)):
        st.session_state.page -= 1
        st.rerun()
    sub_c2.markdown(f"<div style='text-align:center; padding-top:10px;'><b>Sayfa {st.session_state.page + 1} / {max(1, total_pages)}</b></div>", unsafe_allow_html=True)
    if sub_c3.button("İleri ▶", key="top_next", disabled=(st.session_state.page >= total_pages - 1)):
        st.session_state.page += 1
        st.rerun()

st.divider()

# ÜRÜN KARTLARI (GRID)
if page_data.empty:
    st.info("Kriterlere uygun ürün bulunamadı.")
else:
    cols = st.columns(4) # 4 Sütun
    for i, row in enumerate(page_data.to_dict('records')):
        with cols[i % 4]:
            # İndirim varsa eski fiyatı göster
            fiyat_html = f'<div class="new-price">{row["Satış Fiyatı"]:.2f} ₺</div>'
            if row['Etiket Fiyatı'] > row['Satış Fiyatı']:
                fiyat_html = f'<div class="old-price">{row["Etiket Fiyatı"]:.2f} ₺</div>' + fiyat_html
            
            # İndirim Rozeti
            rozet = f'<div class="badge-discount">%{row["İndirim %"]:.0f}</div>' if row['İndirim %'] > 0 else ""

            # HTML KART
            st.markdown(f"""
            <div class="product-card">
                {rozet}
                <div class="img-container">
                    <img src="{row['Resim']}" class="product-img" loading="lazy">
                </div>
                <div>
                    <div class="product-title" title="{row['Ürün Adı']}">{row['Ürün Adı']}</div>
                    <div class="product-cat">{str(row['Kategori']).split('-c-')[0].replace('-', ' ').title()}</div>
                </div>
                <div class="price-container">
                    {fiyat_html}
                </div>
                <div class="btn-container">
                    <a href="{row['Link']}" target="_blank" class="btn-go">Migros'a Git</a>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # ANALİZ BUTONU (HTML DIŞINA, STREAMLIT NATIVE OLARAK)
            # Kartın hemen altına yerleşir
            if st.button("📊 Fiyat Analizi", key=f"analiz_{i}", use_container_width=True):
                grafik_goster(row['Ürün Adı'], df_raw)

st.divider()

# ALT SAYFALAMA (Ortalanmış)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    sub_c1, sub_c2, sub_c3 = st.columns([1, 2, 1])
    if sub_c1.button("◀ Geri", key="bot_prev", disabled=(st.session_state.page == 0)):
        st.session_state.page -= 1
        st.rerun()
    sub_c2.markdown(f"<div style='text-align:center; padding-top:10px;'><b>Sayfa {st.session_state.page + 1} / {max(1, total_pages)}</b></div>", unsafe_allow_html=True)
    if sub_c3.button("İleri ▶", key="bot_next", disabled=(st.session_state.page >= total_pages - 1)):
        st.session_state.page += 1
        st.rerun()
