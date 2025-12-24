import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI (Geniş Ekran) ---
st.set_page_config(page_title="Migros Fiyat Analiz", page_icon="🛒", layout="wide")

# --- CSS (CİMRİ/AKAKÇE PROFESYONEL TASARIM) ---
st.markdown("""
<style>
    /* Genel Arkaplan ve Fontlar */
    .stApp {
        background-color: #f4f6f9; /* Hafif gri profesyonel zemin */
    }
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }

    /* 1. VİTRİN KARTI (GRID) */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: white;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 10px;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: #3874ff; /* Cimri Mavisi Hover */
        transform: translateY(-3px);
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }

    /* Resim Alanı Düzenleme */
    div[data-testid="stImage"] {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 160px; /* Sabit resim alanı */
        background-color: #fff;
        margin-bottom: 10px;
    }
    
    img {
        object-fit: contain !important; /* Resmi kutuya sığdır */
        max-height: 150px !important;
    }

    /* Kart Metinleri */
    .card-brand { font-size: 11px; color: #888; text-transform: uppercase; margin-bottom: 2px; }
    .card-title {
        font-size: 14px;
        font-weight: 600;
        color: #333;
        line-height: 1.3;
        height: 38px; /* 2 satır sabit */
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 8px;
    }

    /* Fiyat Alanı */
    .price-wrapper {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        margin-top: auto;
    }
    .price-old {
        font-size: 12px;
        color: #999;
        text-decoration: line-through;
    }
    .price-current {
        font-size: 20px;
        font-weight: 800;
        color: #333;
    }
    .discount-badge {
        font-size: 12px;
        font-weight: 700;
        color: #d00;
        background-color: #ffe6e6;
        padding: 2px 6px;
        border-radius: 4px;
        margin-top: 2px;
    }

    /* 2. DETAY SAYFASI */
    .detail-container {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    .detail-title {
        font-size: 28px;
        font-weight: 700;
        color: #222;
        margin-bottom: 15px;
    }
    .detail-price {
        font-size: 32px;
        font-weight: 800;
        color: #222;
    }
    
    /* Mağaza Butonu */
    .btn-store {
        display: inline-block;
        background-color: #ff6000; /* Migros Turuncusu */
        color: white !important;
        font-size: 16px;
        font-weight: bold;
        padding: 12px 40px;
        border-radius: 8px;
        text-decoration: none;
        margin-top: 20px;
        transition: 0.2s;
        text-align: center;
        width: 100%;
    }
    .btn-store:hover { background-color: #e55700; }

    /* Geri Butonu */
    .stButton button {
        border-radius: 6px;
        font-weight: 600;
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

# --- STATE YÖNETİMİ (SAYFA GEÇİŞ SİSTEMİ) ---
# Bu kısım "Geri Dön" butonunun çalışmasını sağlar
if 'page_mode' not in st.session_state:
    st.session_state.page_mode = 'liste' # Başlangıç modu
if 'selected_product_name' not in st.session_state:
    st.session_state.selected_product_name = None

def detaya_git(urun_adi):
    st.session_state.selected_product_name = urun_adi
    st.session_state.page_mode = 'detay'

def listeye_don():
    st.session_state.selected_product_name = None
    st.session_state.page_mode = 'liste'

# --- UYGULAMA BAŞLANGICI ---
df_raw = veri_getir()

# Veri Yoksa Uyarı
if df_raw.empty:
    st.error("Veri bulunamadı. Lütfen sol menüden 'Verileri Güncelle' butonuna basın.")
    if st.sidebar.button("Verileri Güncelle"):
        calistir()
        st.rerun()
    st.stop()

# Tekil Ürün Listesi (Vitrin İçin)
df_vitrin = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# =======================================================
# EKRAN 1: ÜRÜN DETAY SAYFASI (Cimri Tarzı)
# =======================================================
if st.session_state.page_mode == 'detay':
    urun_adi = st.session_state.selected_product_name
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    son_hal = gecmis.iloc[-1]

    # Üst Navigasyon
    c_back, c_space = st.columns([1, 10])
    c_back.button("⬅ Geri", on_click=listeye_don)

    # Detay Konteyneri
    with st.container():
        col_img, col_info = st.columns([4, 6], gap="large")
        
        # SOL: Büyük Resim
        with col_img:
            st.image(son_hal['Resim'], use_container_width=True)
        
        # SAĞ: Bilgiler
        with col_info:
            st.markdown(f"<div class='detail-title'>{son_hal['Ürün Adı']}</div>", unsafe_allow_html=True)
            st.caption(f"Kategori: {son_hal['Kategori']}")
            
            st.markdown("---")
            
            # Fiyat Bloğu
            if son_hal['İndirim %'] > 0:
                st.markdown(f"<div style='color:#999; text-decoration:line-through; font-size:18px;'>{son_hal['Etiket Fiyatı']:.2f} ₺</div>", unsafe_allow_html=True)
                st.markdown(f"<div class='detail-price'>{son_hal['Satış Fiyatı']:.2f} ₺ <span style='font-size:16px; color:#d00; font-weight:normal;'>(%{son_hal['İndirim %']:.0f} İndirim)</span></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='detail-price'>{son_hal['Satış Fiyatı']:.2f} ₺</div>", unsafe_allow_html=True)
            
            # Mağaza Butonu
            st.markdown(f"""<a href="{son_hal['Link']}" target="_blank" class="btn-store">Mağazaya Git (Migros)</a>""", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Minik İstatistikler
            avg_price = gecmis['Satış Fiyatı'].mean()
            min_price = gecmis['Satış Fiyatı'].min()
            st.info(f"💡 **Analiz:** Bu ürün son dönemde ortalama **{avg_price:.2f} ₺** fiyatla satıldı. En düşük **{min_price:.2f} ₺** seviyesini gördü.")

    # GRAFİK ALANI (Alt Kısım)
    st.divider()
    st.subheader("📉 Fiyat Değişim Grafiği")
    
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color="#3874ff", line_width=3, marker_size=8) # Cimri Mavisi
    fig.update_layout(
        plot_bgcolor="white",
        hovermode="x unified",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='#eee')
    )
    if "Etiket Fiyatı" in gecmis.columns:
         fig.add_scatter(x=gecmis["Tarih"], y=gecmis["Etiket Fiyatı"], name="Normal Fiyat", line=dict(dash='dash', color='gray'))
         
    st.plotly_chart(fig, use_container_width=True)


# =======================================================
# EKRAN 2: VİTRİN / LİSTELEME SAYFASI
# =======================================================
else:
    # --- YAN MENÜ ---
    with st.sidebar:
        st.header("🔍 Filtreler")
        arama = st.text_input("Ürün Ara", placeholder="Örn: iPhone, Süt...")
        
        kat_list = ["Tümü"] + sorted(df_vitrin["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_vitrin.columns else ["Tümü"]
        kategori = st.selectbox("Kategori", kat_list)
        
        sirala = st.selectbox("Sıralama", ["Önerilen", "En Düşük Fiyat", "En Yüksek Fiyat", "En Büyük İndirim"])
        
        st.divider()
        if st.button("🔄 Verileri Güncelle"):
            with st.spinner("Market taranıyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()

    # --- VERİ FİLTRELEME ---
    df = df_vitrin.copy()
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]
    
    # Sıralama Mantığı
    if sirala == "En Düşük Fiyat": df = df.sort_values("Satış Fiyatı")
    elif sirala == "En Yüksek Fiyat": df = df.sort_values("Satış Fiyatı", ascending=False)
    elif sirala == "En Büyük İndirim": df = df.sort_values("İndirim %", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True]) # Önerilen

    # --- ÜST BİLGİ ---
    st.markdown(f"### 📦 {len(df)} Ürün Listeleniyor")

    # --- SAYFALAMA ---
    SAYFA_BASI = 20 # Cimri tarzı büyük kartlar için 20 ideal
    if "page" not in st.session_state: st.session_state.page = 0
    total_pages = math.ceil(len(df) / SAYFA_BASI)
    
    if st.session_state.page >= total_pages: st.session_state.page = max(0, total_pages - 1)
    
    start = st.session_state.page * SAYFA_BASI
    end = start + SAYFA_BASI
    page_data = df.iloc[start:end]

    # --- ÜRÜN IZGARASI (GRID) ---
    if page_data.empty:
        st.warning("Aradığınız kriterlere uygun ürün bulunamadı.")
    else:
        # 4 Sütunlu Grid (Geniş ve okunaklı)
        cols = st.columns(4)
        for i, row in enumerate(page_data.to_dict('records')):
            with cols[i % 4]:
                # Streamlit KUTUSU (Border=True ile çerçeve)
                with st.container(border=True):
                    # 1. Resim
                    st.image(row['Resim'])
                    
                    # 2. Marka/Kategori (Opsiyonel küçük gri yazı)
                    kategori_kisa = str(row['Kategori']).split('-c-')[0].replace('-', ' ').title()
                    st.markdown(f"<div class='card-brand'>{kategori_kisa}</div>", unsafe_allow_html=True)

                    # 3. Başlık
                    st.markdown(f"<div class='card-title' title='{row['Ürün Adı']}'>{row['Ürün Adı']}</div>", unsafe_allow_html=True)
                    
                    # 4. Fiyat Bloğu
                    if row['İndirim %'] > 0:
                        st.markdown(f"""
                        <div class="price-wrapper">
                            <span class="price-old">{row['Etiket Fiyatı']:.0f} TL</span>
                            <span class="price-current">{row['Satış Fiyatı']:.2f} TL</span>
                            <span class="discount-badge">%{row['İndirim %']:.0f} İndirim</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                        <div class="price-wrapper">
                             <div style="height:17px"></div> <span class="price-current">{row['Satış Fiyatı']:.2f} TL</span>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    st.markdown("<div style='margin-bottom:10px;'></div>", unsafe_allow_html=True)
                    
                    # 5. İNCELE BUTONU (Tam Genişlik)
                    # Unique key önemli!
                    st.button("İncele", key=f"btn_{i}_{row['Link']}", on_click=detaya_git, args=(row['Ürün Adı'],), use_container_width=True)

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
