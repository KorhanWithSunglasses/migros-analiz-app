import streamlit as st
import pandas as pd
import math
import time
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

# --- CSS (SOFT UI & DEĞİŞİM ETİKETLERİ) ---
is_dark = st.session_state.theme == 'dark'
bg_color = "#121212" if is_dark else "#f8f9fa"
card_bg = "#1e1e1e" if is_dark else "#ffffff"
text_color = "#e0e0e0" if is_dark else "#333333"
border_color = "#333333" if is_dark else "#eaeaea"
shadow = "0 4px 20px rgba(0,0,0,0.5)" if is_dark else "0 4px 20px rgba(0,0,0,0.05)"

st.markdown(f"""
<style>
    .stApp {{ background-color: {bg_color}; }}
    .block-container {{ padding-top: 2rem; padding-bottom: 5rem; }}
    
    /* KART TASARIMI */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {card_bg};
        border: 1px solid {border_color};
        border-radius: 20px;
        padding: 15px;
        box-shadow: {shadow};
        transition: transform 0.2s ease;
        position: relative;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: #ff6000;
        transform: translateY(-5px);
    }}
    
    div[data-testid="stImage"] {{
        display: flex; justify-content: center; align-items: center;
        height: 180px; background-color: #fff; border-radius: 15px;
        margin-bottom: 12px; padding: 10px;
    }}
    img {{ object-fit: contain !important; max-height: 160px !important; }}
    
    .soft-title {{
        font-size: 14px; font-weight: 600; color: {text_color};
        line-height: 1.4; height: 40px; overflow: hidden;
        display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
        margin-bottom: 8px;
    }}
    .price-tag {{ font-size: 20px; font-weight: 800; color: #ff6000; }}
    .old-price {{ font-size: 13px; text-decoration: line-through; color: #888; margin-right: 8px; }}
    
    /* FİYAT DEĞİŞİM ETİKETLERİ */
    .change-badge-down {{
        background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0;
        font-size: 11px; font-weight: bold; padding: 4px 8px; border-radius: 6px;
        display: inline-block; margin-top: 5px; width: 100%; text-align: center;
    }}
    .change-badge-up {{
        background-color: #fee2e2; color: #991b1b; border: 1px solid #fecaca;
        font-size: 11px; font-weight: bold; padding: 4px 8px; border-radius: 6px;
        display: inline-block; margin-top: 5px; width: 100%; text-align: center;
    }}

    .stButton button {{ width: 100%; border-radius: 12px; font-weight: 600; border: 1px solid {border_color}; transition: 0.2s; }}
    .back-btn-area button {{ background-color: transparent; border: 2px solid #ff6000; color: #ff6000; }}
    .back-btn-area button:hover {{ background-color: #ff6000; color: white !important; }}
    
    .detail-header {{ font-size: 28px; font-weight: 800; color: {text_color}; margin-bottom: 20px; }}
    .stat-box {{ background-color: {bg_color}; border-radius: 15px; padding: 15px; text-align: center; border: 1px solid {border_color}; }}
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
    except: return 0.0

def linki_duzelt(link):
    """Linklerin sonundaki boşlukları ve hataları temizler"""
    if not link or pd.isna(link): return "#"
    link = str(link).strip()
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
        if "Link" in df.columns: df["Link"] = df["Link"].apply(linki_duzelt) # Linkleri temizle
            
        return df
    except: return pd.DataFrame()

# --- VERİ HAZIRLIĞI VE DEĞİŞİM HESABI ---
df_raw = veri_getir()
if df_raw.empty:
    st.error("Veri bağlantısı kurulamadı.")
    if st.button("Tekrar Dene"): st.rerun()
    st.stop()

# 1. Önce Veriyi Tarih ve Ürün Adına Göre Sırala
df_sorted = df_raw.sort_values(["Ürün Adı", "Tarih"])

# 2. Önceki Fiyatı Hesapla (Shift Yöntemi) - SADECE "SATIŞ FİYATI" (SON FİYAT) ÜZERİNDEN
df_sorted['Önceki Fiyat'] = df_sorted.groupby("Ürün Adı")["Satış Fiyatı"].shift(1)

# 3. Son Güncel Durumu Al
df_vitrin = df_sorted.drop_duplicates("Ürün Adı", keep='last')

# 4. Değişim Miktarını Hesapla
df_vitrin['Fiyat Farkı'] = df_vitrin['Satış Fiyatı'] - df_vitrin['Önceki Fiyat']

# =======================================================
# EKRAN: DETAY SAYFASI
# =======================================================
if st.session_state.page == 'detail':
    urun_adi = st.session_state.selected_product
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    son = gecmis.iloc[-1]

    c1, c2 = st.columns([1, 6])
    with c1:
        st.markdown('<div class="back-btn-area">', unsafe_allow_html=True)
        if st.button("⬅ Geri Dön"): go_home(); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    col_img, col_info = st.columns([4, 6], gap="large")
    
    with col_img:
        st.image(son['Resim'], use_container_width=True)
        st.link_button("🛒 Migros'ta Görüntüle", son['Link'], type="primary", use_container_width=True)

    with col_info:
        st.markdown(f"<div class='detail-header'>{son['Ürün Adı']}</div>", unsafe_allow_html=True)
        st.caption(f"Kategori: {son['Kategori']}")
        
        fiyat_html = f"<span class='price-tag' style='font-size:36px;'>{son['Satış Fiyatı']:.2f} ₺</span>"
        if son['İndirim %'] > 0:
            fiyat_html = f"<span class='old-price' style='font-size:20px;'>{son['Etiket Fiyatı']:.2f} ₺</span>" + fiyat_html
            st.warning(f"🔥 %{son['İndirim %']:.0f} İndirim Fırsatı")
        
        st.markdown(f"<div style='margin: 20px 0;'>{fiyat_html}</div>", unsafe_allow_html=True)

        s1, s2, s3 = st.columns(3)
        s1.markdown(f"<div class='stat-box'><div class='stat-val'>{gecmis['Satış Fiyatı'].mean():.1f} ₺</div><div class='stat-lbl'>Ortalama</div></div>", unsafe_allow_html=True)
        s2.markdown(f"<div class='stat-box'><div class='stat-val' style='color:#2ecc71'>{gecmis['Satış Fiyatı'].min():.1f} ₺</div><div class='stat-lbl'>En Düşük</div></div>", unsafe_allow_html=True)
        s3.markdown(f"<div class='stat-box'><div class='stat-val' style='color:#e74c3c'>{gecmis['Satış Fiyatı'].max():.1f} ₺</div><div class='stat-lbl'>En Yüksek</div></div>", unsafe_allow_html=True)

    st.markdown("### 📉 Fiyat Geçmişi Analizi")
    # Grafik Çizerken de "Satış Fiyatı"nı (Son Fiyatı) baz alıyoruz
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", markers=True)
    fig.update_traces(line_color="#ff6000", line_width=4, marker_size=10, marker_color="white", marker_line_width=2)
    
    grid_color = "#333" if is_dark else "#eee"
    text_c = "#eee" if is_dark else "#333"
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=text_c, xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor=grid_color))
    st.plotly_chart(fig, use_container_width=True)

# =======================================================
# EKRAN: ANA SAYFA (VİTRİN)
# =======================================================
else:
    with st.sidebar:
        st.title("🛒 Migros Avcısı")
        icon = "🌞" if is_dark else "🌙"
        if st.button(f"{icon} Tema Değiştir"): toggle_theme(); st.rerun()
        st.divider()
        arama = st.text_input("🔍 Ürün Ara")
        kat_list = ["Tümü"] + sorted(df_vitrin["Kategori"].astype(str).unique().tolist()) if "Kategori" in df_vitrin.columns else ["Tümü"]
        kategori = st.selectbox("📂 Kategori", kat_list)
        sirala = st.selectbox("🔃 Sıralama", ["Akıllı (Fırsatlar)", "Fiyat Artan", "Fiyat Azalan"])
        
        st.markdown("---")
        # YENİ BUTON: FİYATI DEĞİŞENLER
        sadece_degisenler = st.toggle("🔔 Fiyatı Değişenler", value=False)
        
        st.divider()
        if st.button("🚀 Verileri Güncelle"):
            with st.spinner("Güncelleniyor..."):
                calistir()
                st.cache_data.clear()
                st.rerun()

    # --- FİLTRELEME MANTIĞI ---
    df = df_vitrin.copy()
    
    # 1. Değişenler Filtresi (En Önemlisi)
    if sadece_degisenler:
        # Önceki fiyatı olup da (yeni ürün değil), şimdiki fiyatı farklı olanları getir
        # "Satış Fiyatı" (Son Fiyat) değişmişse değişim var demektir.
        df = df[df['Önceki Fiyat'].notna() & (df['Satış Fiyatı'] != df['Önceki Fiyat'])]
        if df.empty:
            st.info("Son güncellemede fiyatı değişen ürün bulunamadı.")
            
    if arama: df = df[df["Ürün Adı"].str.contains(arama, case=False)]
    if kategori != "Tümü": df = df[df["Kategori"] == kategori]
    
    # Sıralama
    if sirala == "Fiyat Artan": df = df.sort_values("Satış Fiyatı")
    elif sirala == "Fiyat Azalan": df = df.sort_values("Satış Fiyatı", ascending=False)
    else: df = df.sort_values(["İndirim %", "Ürün Adı"], ascending=[False, True])

    c1, c2 = st.columns([2, 1])
    baslik = "🔔 Fiyatı Değişenler" if sadece_degisenler else "📦 Tüm Ürünler"
    c1.markdown(f"### {baslik} ({len(df)})")

    # --- KART GÖSTERİMİ ---
    SAYFA_BASI = 24
    total_pages = math.ceil(len(df) / SAYFA_BASI)
    if st.session_state.pagination_idx >= total_pages: st.session_state.pagination_idx = 0
    start = st.session_state.pagination_idx * SAYFA_BASI
    end = start + SAYFA_BASI
    page_data = df.iloc[start:end]

    cols = st.columns(4)
    for i, row in enumerate(page_data.to_dict('records')):
        with cols[i % 4]:
            with st.container(border=True):
                st.image(row['Resim'])
                st.markdown(f"<div class='soft-title' title='{row['Ürün Adı']}'>{row['Ürün Adı']}</div>", unsafe_allow_html=True)
                
                # Fiyat Alanı
                price_html = f"<span class='price-tag'>{row['Satış Fiyatı']:.2f} ₺</span>"
                if row['İndirim %'] > 0:
                    st.markdown(f"<div><span class='old-price'>{row['Etiket Fiyatı']:.0f}</span>{price_html}</div>", unsafe_allow_html=True)
                else: st.markdown(f"<div>{price_html}</div>", unsafe_allow_html=True)
                
                # --- FİYAT DEĞİŞİM ETİKETLERİ ---
                # "Satış Fiyatı" (Son Fiyat) baz alınarak değişim hesabı
                if pd.notna(row['Önceki Fiyat']) and row['Önceki Fiyat'] != 0:
                    fark = row['Satış Fiyatı'] - row['Önceki Fiyat']
                    if fark < 0: # Fiyat Düşmüş
                        st.markdown(f"<div class='change-badge-down'>⬇ {abs(fark):.2f} TL Düştü</div>", unsafe_allow_html=True)
                    elif fark > 0: # Fiyat Artmış
                        st.markdown(f"<div class='change-badge-up'>⬆ {fark:.2f} TL Arttı</div>", unsafe_allow_html=True)
                
                st.markdown("<div style='margin-bottom:10px'></div>", unsafe_allow_html=True)
                if st.button("İncele", key=f"btn_{i}_{row['Link']}", use_container_width=True):
                    go_to_detail(row['Ürün Adı'])
                    st.rerun()
    
    st.divider()
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    if col_p1.button("◀ Önceki", disabled=(st.session_state.pagination_idx == 0), use_container_width=True):
        st.session_state.pagination_idx -= 1
        st.rerun()
    col_p2.markdown(f"<div style='text-align:center; padding-top:10px; font-weight:bold; color:{text_color}'>Sayfa {st.session_state.pagination_idx + 1} / {max(1, total_pages)}</div>", unsafe_allow_html=True)
    if col_p3.button("Sonraki ▶", disabled=(st.session_state.pagination_idx >= total_pages - 1), use_container_width=True):
        st.session_state.pagination_idx += 1
        st.rerun()
