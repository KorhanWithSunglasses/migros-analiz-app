import streamlit as st
import pandas as pd
import math
import time
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Analiz", page_icon="🛒", layout="wide")

# --- STATE (DURUM) YÖNETİMİ ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'selected_product' not in st.session_state: st.session_state.selected_product = None
if 'pagination_idx' not in st.session_state: st.session_state.pagination_idx = 0

# --- TEMA DEĞİŞTİRME FONKSİYONU ---
def toggle_theme():
    st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'

def go_to_detail(urun_adi):
    st.session_state.selected_product = urun_adi
    st.session_state.page = 'detail'

def go_home():
    st.session_state.selected_product = None
    st.session_state.page = 'home'

# --- CSS (DİNAMİK TEMA) ---
# Temaya göre renkleri belirle
is_dark = st.session_state.theme == 'dark'
bg_color = "#121212" if is_dark else "#f8f9fa"
card_bg = "#1e1e1e" if is_dark else "#ffffff"
text_color = "#e0e0e0" if is_dark else "#333333"
border_color = "#333333" if is_dark else "#eaeaea"
shadow = "0 4px 20px rgba(0,0,0,0.5)" if is_dark else "0 4px 20px rgba(0,0,0,0.05)"

st.markdown(f"""
<style>
    /* GENEL SAYFA AYARLARI */
    .stApp {{
        background-color: {bg_color};
    }}
    .block-container {{ padding-top: 2rem; padding-bottom: 5rem; }}

    /* YUMUŞAK KART TASARIMI */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 20px; /* Daha yumuşak köşeler */
        padding: 15px;
        box-shadow: {shadow};
        transition: transform 0.2s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: #ff6000;
        transform: translateY(-5px);
    }}

    /* RESİM ALANI */
    div[data-testid="stImage"] {{
        display: flex;
        justify-content: center;
        align-items: center;
        height: 180px; /* Sabit yükseklik */
        background-color: #fff; /* Resim arkası hep beyaz kalsın ki ürün görünsün */
        border-radius: 15px;
        margin-bottom: 12px;
        padding: 10px;
    }}
    img {{
        object-fit: contain !important;
        max-height: 160px !important;
    }}

    /* METİN STİLLERİ */
    .soft-title {{
        font-size: 14px;
        font-weight: 600;
        color: {text_color};
        line-height: 1.4;
        height: 40px;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        margin-bottom: 8px;
    }}
    .price-tag {{
        font-size: 20px;
        font-weight: 800;
        color: #ff6000; /* Migros Turuncusu */
    }}
    .old-price {{
        font-size: 13px;
        text-decoration: line-through;
        color: #888;
        margin-right: 8px;
    }}
    
    /* BUTONLARIN GÖRÜNÜMÜ */
    .stButton button {{
        width: 100%;
        border-radius: 12px;
        font-weight: 600;
        border: 1px solid {border_color};
        transition: 0.2s;
    }}
    /* Geri Butonu Özelleştirme */
    .back-btn-area button {{
        background-color: transparent;
        border: 2px solid #ff6000;
        color: #ff6000;
    }}
    .back-btn-area button:hover {{
        background-color: #ff6000;
        color: white !important;
    }}

    /* DETAY SAYFASI */
    .detail-header {{
        font-size: 28px;
        font-weight: 800;
        color: {text_color};
        margin-bottom: 20px;
    }}
    .stat-box {{
        background-color: {bg_color};
        border-radius: 15px;
        padding: 15px;
        text-align: center;
        border: 1px solid {border_color};
    }}
    .stat-val {{ font-size: 18px; font-weight: bold; color: {text_color}; }}
    .stat-lbl {{ font-size: 12px; color: #888; text-transform: uppercase; }}

</style>
""", unsafe_allow_html=True)

# --- VERİ İŞLEMLERİ ---
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
        if "Tarih" in df.columns: df["Tarih"] = pd.to_datetime(df["Tarih"], errors='coerce')
        return df
    except: return pd.DataFrame()

# --- VERİ HAZIRLIĞI ---
df_raw = veri_getir()
if df_raw.empty:
    st.error("Veri bağlantısı kurulamadı.")
    if st.button("Tekrar Dene"): st.rerun()
    st.stop()

df_vitrin = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# =======================================================
# EKRAN: DETAY SAYFASI
# =======================================================
if st.session_state.page == 'detail':
    urun_adi = st.session_state.selected_product
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    son = gecmis.iloc[-1]

    # ÜST NAVİGASYON (GERİ BUTONU)
    c1, c2 = st.columns([1, 6])
    with c1:
        st.markdown('<div class="back-btn-area">', unsafe_allow_html=True)
        if st.button("⬅ Geri Dön", use_container_width=True):
            go_home()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")

    # İÇERİK (SOL: RESİM, SAĞ: BİLGİ)
    col_img, col_info = st.columns([4, 6], gap="large")
    
    with col_img:
        st.image(son['Resim'], use_container_width=True)
        st.link_button("🛒 Migros'ta Görüntüle", son['Link'], type="primary", use_container_width=True)

    with col_info:
        st.markdown(f"<div class='detail-header'>{son['Ürün Adı']}</div>", unsafe_allow_html=True)
        
        # Fiyat Alanı
        st.caption(f"Kategori: {son['Kategori']}")
        fiyat_html = f"<span class='price-tag' style='font-size:36px;'>{son['Satış Fiyatı']:.2f} ₺</span>"
        if son['İndirim %'] > 0:
            fiyat_html = f"<span class='old-price' style='font-size:20px;'>{son['Etiket Fiyatı']:.2f} ₺</span>" + fiyat_html
            st.warning(f"🔥 %{son['İndirim %']:.0f} İndirim Fırsatı")
        
        st.markdown(f"<div style='margin: 20px 0;'>{fiyat_html}</div>", unsafe_allow_html=True)

        # İstatistikler (Yan Yana)
        s1, s2, s3 = st.columns(3)
        avg = gecmis['Satış Fiyatı'].mean()
        low = gecmis['Satış Fiyatı'].min()
        high = gecmis['Satış Fiyatı'].max()
        
        s1.markdown(f"<div class='stat-box'><div class='stat-val'>{avg:.1f} ₺</div><div class='stat-lbl'>Ortalama</div></div>", unsafe_allow_html=True)
        s2.markdown(f"<div class='stat-box'><div class='stat-val' style='color:#2ecc71'>{low:.1f} ₺</div><div class='stat-lbl'>En Düşük</div></div>", unsafe_allow_html=True)
        s3.markdown(f"<div class='stat-box'><div class='stat-val' style='color:#e74c3c'>{high:.1f} ₺</div><div class='stat-lbl'>En Yüksek</div></div>", unsafe_allow_html=True)

    # GRAFİK
    st.markdown("### 📉 Fiyat Geçmişi Analizi")
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color="#ff6000", line_width=4, marker_size=10, marker_color="white", marker_line_width=2)
    # Tema uyumlu grafik arka planı
    layout_bg = "#1e1e1e" if is_dark else "white"
    grid_color = "#333" if is_dark else "#eee"
    text_c = "#eee" if is_dark else "#333"
    
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=text_c,
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor=grid_color)
    )
    st.plotly_chart(fig, use_container_width=True)


# =======================================================
# EKRAN: ANA SAYFA (VİTRİN)
# =======================================================
else:
    # --- YAN MENÜ ---
    with st.sidebar:
        st.title("🛒 Migros Avcısı")
        
        # TEMA BUTONU
        icon = "🌞" if is_dark else "🌙"
        label = "Aydınlık Mod" if is_dark else "Karanlık Mod"
        if st.button(f"{icon} {label}a Geç"):
            toggle_theme()
            st.rerun()
            
        st.divider()
        
        arama = st.text_input("🔍 Ürün Ara", placeholder="Örn: Nutella")
        
        kat_list = ["Tümü"] + sorted(df_vitrin["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_vitrin.columns else ["Tümü"]
        kategori = st.selectbox("📂 Kategori", kat_list)
        
        sirala = st.selectbox("🔃 Sıralama", ["Akıllı (Fırsatlar)", "Fiyat Artan", "Fiyat Azalan"])
        
        st.divider()
        if st.button("🚀 Verileri Güncelle"):
            with st.spinner("Güncelleniyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()

    # --- FİLTRELEME ---
    df = df_vitrin.copy()
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]

    if sirala == "Fiyat Artan": df = df.sort_values("Satış Fiyatı")
    elif sirala == "Fiyat Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

    # --- ÜST BİLGİ ---
    c1, c2 = st.columns([2, 1])
    c1.markdown(f"### 📦 {len(df)} Ürün Listeleniyor")

    # --- SAYFALAMA ---
    SAYFA_BASI = 24 # 4 Sütun x 6 Satır
    total_pages = math.ceil(len(df) / SAYFA_BASI)
    
    # State'i güvenli hale getir
    if st.session_state.pagination_idx >= total_pages: st.session_state.pagination_idx = 0
    
    start = st.session_state.pagination_idx * SAYFA_BASI
    end = start + SAYFA_BASI
    page_data = df.iloc[start:end]

    if page_data.empty:
        st.info("Kriterlere uygun ürün bulunamadı.")
    else:
        # 4 Sütunlu Grid
        cols = st.columns(4)
        for i, row in enumerate(page_data.to_dict('records')):
            with cols[i % 4]:
                # Streamlit KUTUSU (Yumuşak Köşeli)
                with st.container(border=True):
                    # 1. Resim
                    st.image(row['Resim'])
                    
                    # 2. Başlık (2 satır sınırlı)
                    st.markdown(f"<div class='soft-title' title='{row['Ürün Adı']}'>{row['Ürün Adı']}</div>", unsafe_allow_html=True)
                    
                    # 3. Fiyat
                    price_html = f"<span class='price-tag'>{row['Satış Fiyatı']:.2f} ₺</span>"
                    if row['İndirim %'] > 0:
                        st.markdown(f"""
                        <div>
                            <span class='old-price'>{row['Etiket Fiyatı']:.0f}</span>
                            {price_html}
                            <span style='color:#d00; font-size:12px; font-weight:bold; margin-left:5px;'>%{row['İndirim %']:.0f}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div>{price_html}</div>", unsafe_allow_html=True)
                    
                    st.markdown("<div style='margin-bottom:10px'></div>", unsafe_allow_html=True)
                    
                    # 4. İNCELE BUTONU
                    if st.button("İncele", key=f"btn_{i}_{row['Link']}", use_container_width=True):
                        go_to_detail(row['Ürün Adı'])
                        st.rerun()

    st.divider()
    
    # --- SAYFALAMA BUTONLARI (ORTALI) ---
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    
    if col_p1.button("◀ Önceki Sayfa", disabled=(st.session_state.pagination_idx == 0), use_container_width=True):
        st.session_state.pagination_idx -= 1
        st.rerun()
        
    col_p2.markdown(f"<div style='text-align:center; padding-top:10px; font-weight:bold; color:{text_color}'>Sayfa {st.session_state.pagination_idx + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True)
    
    if col_p3.button("Sonraki Sayfa ▶", disabled=(st.session_state.pagination_idx >= total_pages - 1), use_container_width=True):
        st.session_state.pagination_idx += 1
        st.rerun()
