import streamlit as st
import pandas as pd
import math
import time
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Avcısı", page_icon="🛍️", layout="wide")

# --- CSS (KART TASARIMI) ---
st.markdown("""
<style>
    /* Genel */
    .block-container { padding-top: 1rem; padding-bottom: 5rem; }
    
    /* Ürün Kartı */
    .product-card {
        background-color: white;
        border: 1px solid #eee;
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        transition: all 0.2s ease;
        height: 380px; /* Sabit yükseklik, düzen bozulmasın */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .product-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        border-color: #ff6000;
    }
    
    /* Resim Alanı */
    .img-container {
        height: 180px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        margin-bottom: 10px;
    }
    .product-img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain;
    }
    
    /* Metinler */
    .product-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
        line-height: 1.4;
        height: 40px; /* 2 satırla sınırla */
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 5px;
    }
    .product-meta {
        font-size: 12px;
        color: #888;
        margin-bottom: 5px;
    }
    
    /* Fiyatlar */
    .price-box { margin-top: auto; }
    .old-price {
        font-size: 13px;
        color: #999;
        text-decoration: line-through;
    }
    .new-price {
        font-size: 22px;
        font-weight: 700;
        color: #ff6000;
    }
    
    /* Buton */
    .buy-btn {
        display: block;
        width: 100%;
        padding: 8px 0;
        background-color: #fff0e6;
        color: #ff6000 !important;
        text-align: center;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 600;
        margin-top: 10px;
        border: 1px solid #ff6000;
        transition: 0.2s;
    }
    .buy-btn:hover {
        background-color: #ff6000;
        color: white !important;
    }
    
    /* Rozetler */
    .badge-discount {
        position: absolute;
        top: 10px;
        right: 10px;
        background-color: #ff4b4b;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: bold;
        z-index: 2;
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
        
        # Sayısal çeviri
        for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
            if c in df.columns:
                df[c] = df[c].apply(temizle_ve_cevir)
                
        # Tarih
        if "Tarih" in df.columns:
            df["Tarih"] = pd.to_datetime(df["Tarih"], errors='coerce')
            
        return df
    except:
        return pd.DataFrame()

# --- KENAR ÇUBUĞU ---
with st.sidebar:
    st.header("🔍 Filtrele & Ara")
    
    # Veri Yükle
    df_raw = veri_getir()
    
    if st.button("🔄 Verileri Güncelle"):
        with st.spinner("Market taranıyor..."):
            calistir()
            st.success("Bitti!")
            st.cache_data.clear()
            time.sleep(1)
            st.rerun()

    if df_raw.empty:
        st.warning("Veri yok.")
        st.stop()

    # Filtreler
    arama = st.text_input("Ürün Ara", placeholder="Örn: Nutella")
    
    kat_list = ["Tümü"] + sorted(df_raw["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_raw.columns else ["Tümü"]
    kategori = st.selectbox("Kategori", kat_list)
    
    mod = st.radio("Sıralama", ["Akıllı Sıralama (Önce Fırsatlar)", "Fiyata Göre Artan", "Fiyata Göre Azalan"])
    sadece_indirim = st.toggle("Sadece İndirimli Ürünler", value=True)

# --- VERİ İŞLEME ---
df = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# Filtre Uygula
if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
if kategori != "Tümü": df = df[df["Kategori"] == kategori]
if sadece_indirim: df = df[df["İndirim %"] > 0]

# Sıralama
if mod == "Fiyata Göre Artan":
    df = df.sort_values("Satış Fiyatı")
elif mod == "Fiyata Göre Azalan":
    df = df.sort_values("Satış Fiyatı", ascending=False)
else:
    # Akıllı sıralama: Önce yüksek indirim, sonra isim
    df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

# --- SAYFALAMA (PAGINATION) - HIZ İÇİN ---
URUN_SAYISI = len(df)
SAYFA_BASI_URUN = 40  # Her sayfada 40 ürün göster (Kasmayı engeller)

if "page" not in st.session_state:
    st.session_state.page = 0

# Sayfa sayısı hesapla
total_pages = math.ceil(URUN_SAYISI / SAYFA_BASI_URUN)
# Sayfa sınırlarını kontrol et
if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)

start_idx = st.session_state.page * SAYFA_BASI_URUN
end_idx = start_idx + SAYFA_BASI_URUN
current_page_data = df.iloc[start_idx:end_idx]

# --- ÜST BİLGİ VE NAVİGASYON ---
col1, col2 = st.columns([3, 1])
col1.subheader(f"Toplam {URUN_SAYISI} ürün bulundu")

# Sayfa Değiştirme Butonları (Üst)
c_prev, c_info, c_next = col2.columns([1, 2, 1])
if c_prev.button("◀", key="prev_top") and st.session_state.page > 0:
    st.session_state.page -= 1
    st.rerun()
if c_next.button("▶", key="next_top") and st.session_state.page < total_pages - 1:
    st.session_state.page += 1
    st.rerun()
c_info.caption(f"Sayfa {st.session_state.page + 1} / {max(1, total_pages)}")

st.divider()

# --- ÜRÜN KARTLARI (GRID) ---
if current_page_data.empty:
    st.info("Kriterlere uygun ürün bulunamadı.")
else:
    # 4'lü kolonlar oluştur
    cols = st.columns(4)
    for index, row in enumerate(current_page_data.to_dict('records')):
        with cols[index % 4]:
            # Kart HTML Hazırlığı
            indirim_html = f'<div class="badge-discount">%{row["İndirim %"]:.0f}</div>' if row['İndirim %'] > 0 else ""
            
            eski_fiyat_html = ""
            if row['Etiket Fiyatı'] > row['Satış Fiyatı']:
                eski_fiyat_html = f'<div class="old-price">{row["Etiket Fiyatı"]:.2f} ₺</div>'
            
            # Kartı Çiz
            st.markdown(f"""
            <div class="product-card" style="position: relative;">
                {indirim_html}
                <div class="img-container">
                    <img src="{row['Resim']}" class="product-img" loading="lazy">
                </div>
                <div class="product-title" title="{row['Ürün Adı']}">{row['Ürün Adı']}</div>
                <div class="product-meta">{row['Kategori'].split('-c-')[0].replace('-', ' ').title()}</div>
                <div class="price-box">
                    {eski_fiyat_html}
                    <div class="new-price">{row['Satış Fiyatı']:.2f} ₺</div>
                </div>
                <a href="{row['Link']}" target="_blank" class="buy-btn">Migros'a Git</a>
            </div>
            """, unsafe_allow_html=True)

st.divider()

# Sayfa Değiştirme Butonları (Alt)
_, c_prev, c_info, c_next, _ = st.columns([4, 1, 2, 1, 4])
if c_prev.button("◀ Önceki", key="prev_bot") and st.session_state.page > 0:
    st.session_state.page -= 1
    st.rerun()
c_info.markdown(f"<div style='text-align:center; padding-top:5px;'><b>Sayfa {st.session_state.page + 1}</b></div>", unsafe_allow_html=True)
if c_next.button("Sonraki ▶", key="next_bot") and st.session_state.page < total_pages - 1:
    st.session_state.page += 1
    st.rerun()
