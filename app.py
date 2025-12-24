import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
import plotly.graph_objects as go
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Analiz", page_icon="🛒", layout="wide")

# --- CSS TASARIMI (AKAKÇE/CİMRİ TARZI) ---
st.markdown("""
<style>
    /* Sayfa Yapısı */
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    
    /* VİTRİN KARTI (Grid View) */
    .product-card {
        background-color: #fff;
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 10px;
        transition: 0.2s;
        height: 340px; /* Kompakt Yükseklik */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        cursor: pointer;
        position: relative;
    }
    .product-card:hover {
        border-color: #f70;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    
    /* Resim Alanı */
    .img-wrapper {
        height: 140px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 8px;
        background: #fff;
    }
    .product-img {
        max-height: 100%;
        max-width: 100%;
        object-fit: contain; /* Resmi kutuya sığdır */
    }
    
    /* Metinler */
    .p-title {
        font-size: 13px;
        color: #333;
        line-height: 1.3;
        height: 34px;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 4px;
    }
    .p-cat { font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
    
    /* Fiyatlar */
    .price-area { margin-top: auto; }
    .price-old { font-size: 11px; text-decoration: line-through; color: #999; }
    .price-current { font-size: 18px; font-weight: 700; color: #333; }
    .price-discount { color: #d00; font-size: 18px; font-weight: 700; }
    
    /* İndirim Rozeti */
    .badge-sale {
        position: absolute; top: 8px; right: 8px;
        background: #d00; color: #fff;
        font-size: 10px; font-weight: bold;
        padding: 2px 6px; border-radius: 4px;
    }

    /* DETAY SAYFASI TASARIMI */
    .detail-header { font-size: 24px; font-weight: 700; color: #222; margin-bottom: 20px; }
    .stat-box {
        background: #f8f9fa; border: 1px solid #e9ecef;
        border-radius: 8px; padding: 15px; text-align: center;
    }
    .stat-label { font-size: 12px; color: #666; text-transform: uppercase; }
    .stat-val { font-size: 18px; font-weight: bold; color: #333; }
    
    /* Butonlar */
    .btn-back {
        display: inline-block; padding: 8px 16px; 
        background: #eee; color: #333; border-radius: 20px; 
        text-decoration: none; font-weight: 600; margin-bottom: 20px; cursor: pointer;
    }
    .btn-market {
        display: block; width: 100%; padding: 12px;
        background: #f70; color: white !important;
        text-align: center; border-radius: 8px;
        font-size: 16px; font-weight: bold; text-decoration: none;
        transition: 0.2s;
    }
    .btn-market:hover { background: #e65c00; }

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

# --- STATE YÖNETİMİ (SAYFA GEÇİŞLERİ İÇİN) ---
if 'selected_product' not in st.session_state:
    st.session_state.selected_product = None # Hiçbir ürün seçili değil (Ana Sayfa)

def urun_sec(urun_adi):
    st.session_state.selected_product = urun_adi

def ana_sayfaya_don():
    st.session_state.selected_product = None

# --- VERİ HAZIRLIĞI ---
df_raw = veri_getir()

# Eğer veri yoksa uyarı ver
if df_raw.empty:
    with st.sidebar:
        if st.button("🚀 Verileri Güncelle"):
            calistir()
            st.rerun()
    st.warning("Veritabanı boş. Lütfen sol menüden güncelleyin.")
    st.stop()

# Son güncel veri (VİTRİN İÇİN)
df_vitrin = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# --- 1. SENARYO: ÜRÜN DETAY SAYFASI ---
if st.session_state.selected_product:
    urun_adi = st.session_state.selected_product
    # O ürünün tüm geçmişini bul
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    son_hal = gecmis.iloc[-1]
    
    # Geri Dön Butonu (Native Button Kullanıyoruz)
    if st.button("⬅ Listeye Dön"):
        ana_sayfaya_don()
        st.rerun()

    col_img, col_info = st.columns([1, 2])
    
    with col_img:
        st.image(son_hal['Resim'], use_container_width=True)
    
    with col_info:
        st.markdown(f"<div class='detail-header'>{son_hal['Ürün Adı']}</div>", unsafe_allow_html=True)
        
        # İstatistik Kutuları
        s1, s2, s3 = st.columns(3)
        s1.markdown(f"<div class='stat-box'><div class='stat-label'>Şu An</div><div class='stat-val'>{son_hal['Satış Fiyatı']:.2f} ₺</div></div>", unsafe_allow_html=True)
        s2.markdown(f"<div class='stat-box'><div class='stat-label'>Ortalama</div><div class='stat-val'>{gecmis['Satış Fiyatı'].mean():.2f} ₺</div></div>", unsafe_allow_html=True)
        s3.markdown(f"<div class='stat-box'><div class='stat-label'>En Düşük</div><div class='stat-val' style='color:green'>{gecmis['Satış Fiyatı'].min():.2f} ₺</div></div>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Market Butonu
        st.markdown(f"""<a href="{son_hal['Link']}" target="_blank" class="btn-market">Migros'ta İncele</a>""", unsafe_allow_html=True)
        
        if son_hal['İndirim %'] > 0:
            st.info(f"🔥 Bu üründe şu an %{son_hal['İndirim %']:.0f} indirim var!")
            if son_hal.get('İndirim Tipi'):
                st.success(f"Kampanya: {son_hal['İndirim Tipi']}")

    st.divider()
    st.subheader("📉 Fiyat Geçmişi Analizi")
    
    # Gelişmiş Grafik
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color='#ff7700', line_width=3)
    # Normal fiyatı da ekle
    if "Etiket Fiyatı" in gecmis.columns:
        fig.add_scatter(x=gecmis["Tarih"], y=gecmis["Etiket Fiyatı"], name="Normal Fiyat", line=dict(dash='dash', color='gray'))
    
    fig.update_layout(xaxis_title="", yaxis_title="Fiyat (TL)", height=400, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

# --- 2. SENARYO: VİTRİN (ANA SAYFA) ---
else:
    # --- KENAR ÇUBUĞU ---
    with st.sidebar:
        st.title("Filtreler")
        if st.button("🔄 Verileri Güncelle"):
            with st.spinner("Taranıyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()
        
        arama = st.text_input("🔍 Ürün Ara")
        
        kat_list = ["Tümü"] + sorted(df_vitrin["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_vitrin.columns else ["Tümü"]
        kategori = st.selectbox("📂 Kategori", kat_list)
        
        sirala = st.selectbox("🔃 Sıralama", ["Akıllı Sıralama", "Fiyat: Artan", "Fiyat: Azalan", "İndirim Oranı"])
        sadece_indirim = st.toggle("Sadece İndirimli", value=False) # Varsayılan KAPALI

    # --- FİLTRELEME MANTIĞI ---
    df = df_vitrin.copy()
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]
    if sadece_indirim: df = df[df["İndirim %"] > 0]
    
    # Sıralama
    if sirala == "Fiyat: Artan": df = df.sort_values("Satış Fiyatı")
    elif sirala == "Fiyat: Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
    elif sirala == "İndirim Oranı": df = df.sort_values("İndirim %", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True]) # Akıllı

    # --- ÜST BİLGİ ---
    col_top1, col_top2 = st.columns([3, 1])
    col_top1.subheader(f"🛒 {len(df)} Ürün Listeleniyor")

    # --- SAYFALAMA ---
    SAYFA_BASI = 40 # 5 sütun x 8 satır
    if "page" not in st.session_state: st.session_state.page = 0
    total_pages = math.ceil(len(df) / SAYFA_BASI)
    
    # Sayfa sınır kontrolü
    if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)
    
    start = st.session_state.page * SAYFA_BASI
    end = start + SAYFA_BASI
    page_data = df.iloc[start:end]

    # --- ÜRÜN IZGARASI (GRID) ---
    if page_data.empty:
        st.warning("Aradığınız kriterde ürün bulunamadı.")
    else:
        # 5 Sütunlu Profesyonel Izgara
        cols = st.columns(5)
        for i, row in enumerate(page_data.to_dict('records')):
            with cols[i % 5]:
                # Fiyat CSS sınıfı belirle
                fiyat_class = "price-discount" if row['İndirim %'] > 0 else "price-current"
                
                # Kart HTML
                html_code = f"""
                <div class="product-card">
                    {'<div class="badge-sale">%' + str(int(row['İndirim %'])) + '</div>' if row['İndirim %'] > 0 else ''}
                    <div class="img-wrapper">
                        <img src="{row['Resim']}" class="product-img" loading="lazy">
                    </div>
                    <div>
                        <div class="p-title" title="{row['Ürün Adı']}">{row['Ürün Adı']}</div>
                        <div class="p-cat">{str(row['Kategori']).split('-c-')[0].replace('-', ' ')}</div>
                    </div>
                    <div class="price-area">
                        {'<div class="price-old">' + "{:.2f}".format(row['Etiket Fiyatı']) + ' ₺</div>' if row['Etiket Fiyatı'] > row['Satış Fiyatı'] else ''}
                        <div class="{fiyat_class}">{row['Satış Fiyatı']:.2f} ₺</div>
                    </div>
                </div>
                """
                st.markdown(html_code, unsafe_allow_html=True)
                
                # GİZLİ TETİKLEYİCİ BUTON (Kartın hemen altına)
                # Streamlit'te tüm karta tıklama özelliği zor olduğu için şık bir "İncele" butonu ekliyoruz
                if st.button("🔍 İncele", key=f"btn_{i}_{row['Link']}", use_container_width=True):
                    urun_sec(row['Ürün Adı'])
                    st.rerun()

    st.divider()
    
    # --- SAYFALAMA BUTONLARI ---
    c1, c2, c3 = st.columns([1, 2, 1])
    if c1.button("◀ Önceki Sayfa", disabled=(st.session_state.page == 0)):
        st.session_state.page -= 1
        st.rerun()
    
    c2.markdown(f"<div style='text-align:center; font-weight:bold; padding-top:10px;'>Sayfa {st.session_state.page + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True, )
    
    if c3.button("Sonraki Sayfa ▶", disabled=(st.session_state.page >= total_pages - 1)):
        st.session_state.page += 1
        st.rerun()
