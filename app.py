import streamlit as st
import pandas as pd
import math
import time
import re
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Fiyat Analiz", page_icon="🛒", layout="wide")

# --- STATE YÖNETİMİ ---
if 'theme' not in st.session_state: st.session_state.theme = 'light'
if 'page' not in st.session_state: st.session_state.page = 'home'
if 'selected_product' not in st.session_state: st.session_state.selected_product = None
if 'pagination_idx' not in st.session_state: st.session_state.pagination_idx = 0

# --- NAVİGASYON ---
def toggle_theme(): st.session_state.theme = 'dark' if st.session_state.theme == 'light' else 'light'
def go_to_detail(urun_adi):
    st.session_state.selected_product = urun_adi
    st.session_state.page = 'detail'
def go_home():
    st.session_state.selected_product = None
    st.session_state.page = 'home'
    # Sayfa indeksini sıfırlama ki kullanıcı kaldığı yerden devam edebilsin istersen burayı silebilirsin
    # st.session_state.pagination_idx = 0 

# --- CSS (MODERN HEADER & SOFT UI) ---
is_dark = st.session_state.theme == 'dark'
bg_color = "#121212" if is_dark else "#f4f6f9"
card_bg = "#1e1e1e" if is_dark else "#ffffff"
text_color = "#e0e0e0" if is_dark else "#333333"
border_color = "#333333" if is_dark else "#e0e0e0"
header_bg = "#1e1e1e" if is_dark else "#ffffff"

st.markdown(f"""
<style>
    /* GENEL */
    .stApp {{ background-color: {bg_color}; }}
    .block-container {{ padding-top: 1rem; padding-bottom: 5rem; }}
    
    /* ÜST PANEL (HEADER) STİLİ */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 12px;
    }}
    
    /* RADYO BUTONLARINI TAB GİBİ GÖSTERME (Filtreler İçin) */
    div[role="radiogroup"] > label > div:first-child {{
        display: none;
    }}
    div[role="radiogroup"] {{
        flex-direction: row;
        gap: 10px;
        justify-content: center;
    }}
    div[role="radiogroup"] label {{
        background-color: {bg_color};
        padding: 8px 16px;
        border-radius: 20px;
        border: 1px solid {border_color};
        cursor: pointer;
        transition: 0.3s;
    }}
    div[role="radiogroup"] label:hover {{
        border-color: #ff6000;
        color: #ff6000;
    }}
    div[role="radiogroup"] label[data-checked="true"] {{
        background-color: #ff6000;
        color: white !important;
        border-color: #ff6000;
    }}
    div[role="radiogroup"] label[data-checked="true"] p {{
        color: white !important;
    }}

    /* ÜRÜN KARTLARI */
    .product-card-container {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 16px;
        padding: 12px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        height: 100%;
    }}
    .product-card-container:hover {{
        transform: translateY(-4px);
        border-color: #ff6000;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }}
    
    /* RESİM */
    .img-box {{
        height: 160px;
        display: flex; align-items: center; justify-content: center;
        background: #fff; border-radius: 10px; margin-bottom: 10px; padding: 5px;
    }}
    .img-box img {{ object-fit: contain; max-height: 100%; max-width: 100%; }}
    
    /* METİNLER */
    .p-title {{
        font-size: 13px; font-weight: 600; color: {text_color};
        height: 38px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        margin-bottom: 5px; line-height: 1.3;
    }}
    .p-price {{ font-size: 18px; font-weight: 800; color: #ff6000; }}
    .p-old {{ font-size: 12px; text-decoration: line-through; color: #999; margin-right: 5px; }}
    
    /* DEĞİŞİM ETİKETLERİ */
    .badge-down {{ background: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display: block; text-align: center; margin-top: 5px; }}
    .badge-up {{ background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; display: block; text-align: center; margin-top: 5px; }}

    /* BUTONLAR */
    .stButton button {{ border-radius: 8px; font-weight: 600; border: 1px solid {border_color}; }}
    
    /* TEMA BUTONU */
    .theme-btn button {{ background: transparent; border: none; font-size: 20px; }}
</style>
""", unsafe_allow_html=True)

# --- FONKSİYONLAR ---
def temizle_ve_cevir(val):
    try:
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('TL', '').replace('₺', '').strip()
        s = s.replace('.', '').replace(',', '.')
        return float(s)
    except: return 0.0

def linki_duzelt(link):
    if not isinstance(link, str): return "#"
    link = link.strip()
    if "-p-" in link:
        match = re.search(r"(.*-p-[a-z0-9]+)(-\d+)$", link)
        if match: return match.group(1) 
    return link

@st.cache_data(ttl=600)
def veri_getir():
    client = google_sheets_baglan()
    if not client: return pd.DataFrame()
    try:
        try: sheet = client.worksheet("Ana_Veritabani")
        except: sheet = client.sheet1
        data = sheet.get_all_values()
        if not data: return pd.DataFrame()
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        df.columns = df.columns.str.strip()
        
        for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
            if c in df.columns: df[c] = df[c].apply(temizle_ve_cevir)
        if "Tarih" in df.columns: df["Tarih"] = pd.to_datetime(df["Tarih"], errors='coerce')
        if "Link" in df.columns: df["Link"] = df["Link"].apply(linki_duzelt)
        return df
    except: return pd.DataFrame()

# --- VERİ HAZIRLIĞI ---
df_raw = veri_getir()

# Veri Kontrolü
if df_raw.empty:
    st.error("Veritabanı boş veya okunamadı. Lütfen 'Verileri Güncelle' butonunu kullanın.")
    if st.button("🚀 Verileri Güncelle"):
        calistir()
        st.rerun()
    st.stop()

# Analiz (Fiyat Değişim Hesabı)
df_sorted = df_raw.sort_values(["Ürün Adı", "Tarih"])
df_sorted['Önceki Fiyat'] = df_sorted.groupby("Ürün Adı")["Satış Fiyatı"].shift(1)
df_vitrin = df_sorted.drop_duplicates("Ürün Adı", keep='last')
df_vitrin['Fiyat Farkı'] = df_vitrin['Satış Fiyatı'] - df_vitrin['Önceki Fiyat']

# =======================================================
# EKRAN: DETAY SAYFASI
# =======================================================
if st.session_state.page == 'detail':
    urun_adi = st.session_state.selected_product
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    
    if gecmis.empty: go_home(); st.rerun()
    son = gecmis.iloc[-1]

    # Üst Bar
    c1, c2 = st.columns([1, 10])
    with c1:
        if st.button("⬅ Geri", use_container_width=True): go_home(); st.rerun()

    st.markdown("---")
    
    col_img, col_info = st.columns([4, 6], gap="large")
    with col_img:
        st.image(son['Resim'], use_container_width=True)
    with col_info:
        st.markdown(f"## {son['Ürün Adı']}")
        st.caption(f"📂 {son['Kategori']}")
        
        # Fiyat
        if son['İndirim %'] > 0:
            st.markdown(f"<span style='text-decoration:line-through; color:#999; font-size:20px'>{son['Etiket Fiyatı']:.2f} TL</span>", unsafe_allow_html=True)
        st.markdown(f"<span style='color:#ff6000; font-size:40px; font-weight:800'>{son['Satış Fiyatı']:.2f} TL</span>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.link_button("🛒 Migros Sitesine Git", son['Link'], type="primary", use_container_width=True)
        
        # İstatistik
        st.info(f"📊 Ortalama: {gecmis['Satış Fiyatı'].mean():.2f} TL | En Düşük: {gecmis['Satış Fiyatı'].min():.2f} TL")

    # Grafik
    st.divider()
    st.markdown("### 📉 Fiyat Geçmişi")
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color="#ff6000", line_width=4)
    grid_c = "#333" if is_dark else "#eee"
    text_c = "#eee" if is_dark else "#333"
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color=text_c, yaxis=dict(gridcolor=grid_c))
    st.plotly_chart(fig, use_container_width=True)

# =======================================================
# EKRAN: VİTRİN (ANA SAYFA)
# =======================================================
else:
    # --- ÜST SABİT PANEL (HEADER) ---
    with st.container(border=True):
        # 1. Satır: Başlık ve Tema
        c_logo, c_space, c_theme = st.columns([2, 5, 0.5])
        c_logo.title("🛒 Migros Avcısı")
        
        icon = "🌞" if is_dark else "🌙"
        if c_theme.button(icon, key="theme_toggle"):
            toggle_theme()
            st.rerun()
            
        # 2. Satır: Kontroller (Arama | Kategori | Filtreler | Sıralama)
        c_search, c_cat, c_filter, c_sort = st.columns([2, 1.5, 2.5, 1.5])
        
        arama = c_search.text_input("🔍 Ürün Ara", placeholder="Ne aramıştınız?")
        
        # Kategoriler
        tum_kategoriler = sorted(df_raw["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_raw.columns else []
        kategori = c_cat.selectbox("Kategori", ["Tümü"] + tum_kategoriler)
        
        # Filtreler (Yatay Radyo Butonu - CSS ile Tab gibi görünür)
        filtre_modu = c_filter.radio("Filtrele:", ["Tümü", "📉 Fiyatı Düşenler", "📈 Fiyatı Artanlar"], horizontal=True, label_visibility="collapsed")
        
        # Sıralama
        sirala = c_sort.selectbox("Sıralama", ["Akıllı", "Fiyat Artan", "Fiyat Azalan"], label_visibility="collapsed")

    # --- FİLTRELEME MANTIĞI ---
    df = df_vitrin.copy()
    
    # Filtre Modu
    if "Düşenler" in filtre_modu:
        df = df[df['Önceki Fiyat'].notna() & (df['Fiyat Farkı'] < -0.01)]
    elif "Artanlar" in filtre_modu:
        df = df[df['Önceki Fiyat'].notna() & (df['Fiyat Farkı'] > 0.01)]
        
    # Arama & Kategori
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]
    
    # Sıralama
    if sirala == "Fiyat Artan": df = df.sort_values("Satış Fiyatı")
    elif sirala == "Fiyat Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

    # --- LİSTELEME ---
    st.write("") # Boşluk
    st.markdown(f"**📦 {len(df)} Ürün Bulundu**")
    
    if df.empty:
        st.info("Bu kriterlere uygun ürün bulunamadı.")
    else:
        # Sayfalama
        SAYFA_BASI = 24
        total_pages = math.ceil(len(df) / SAYFA_BASI)
        
        # Sayfa güvenliği
        if st.session_state.pagination_idx >= total_pages: st.session_state.pagination_idx = 0
        if st.session_state.pagination_idx < 0: st.session_state.pagination_idx = 0
        
        start = st.session_state.pagination_idx * SAYFA_BASI
        end = start + SAYFA_BASI
        page_data = df.iloc[start:end]

        cols = st.columns(4)
        for i, row in enumerate(page_data.to_dict('records')):
            with cols[i % 4]:
                # HTML KART YAPISI (CSS ile şekillenir)
                with st.container():
                    st.markdown(f"""
                    <div class="product-card-container">
                        <div class="img-box">
                            <img src="{row['Resim']}">
                        </div>
                        <div class="p-title" title="{row['Ürün Adı']}">{row['Ürün Adı']}</div>
                        <div>
                            {'<span class="p-old">' + str(int(row['Etiket Fiyatı'])) + '</span>' if row['İndirim %'] > 0 else ''}
                            <span class="p-price">{row['Satış Fiyatı']:.2f} ₺</span>
                        </div>
                        {f'<div class="badge-down">⬇ {abs(row["Fiyat Farkı"]):.2f} TL Düştü</div>' if (pd.notna(row['Önceki Fiyat']) and row['Fiyat Farkı'] < -0.01) else ''}
                        {f'<div class="badge-up">⬆ {row["Fiyat Farkı"]:.2f} TL Arttı</div>' if (pd.notna(row['Önceki Fiyat']) and row['Fiyat Farkı'] > 0.01) else ''}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button("İncele", key=f"btn_{i}_{row['Link']}", use_container_width=True):
                        go_to_detail(row['Ürün Adı'])
                        st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

        # --- ALT SAYFALAMA BUTONLARI ---
        st.divider()
        c_prev, c_info, c_next = st.columns([1, 2, 1])
        
        if c_prev.button("◀ Önceki Sayfa", disabled=(st.session_state.pagination_idx == 0), use_container_width=True):
            st.session_state.pagination_idx -= 1
            st.rerun()
            
        c_info.markdown(f"<div style='text-align:center; padding-top:10px; font-weight:bold; color:{text_color}'>Sayfa {st.session_state.pagination_idx + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True)
        
        if c_next.button("Sonraki Sayfa ▶", disabled=(st.session_state.pagination_idx >= total_pages - 1), use_container_width=True):
            st.session_state.pagination_idx += 1
            st.rerun()

    # --- FOOTER: GÜNCELLEME BUTONU ---
    st.divider()
    with st.expander("⚙️ Yönetici Ayarları (Veri Güncelleme)"):
        if st.button("🚀 Verileri Şimdi Güncelle (Bu işlem 3-5 dk sürebilir)"):
            with st.spinner("Robot çalışıyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()
