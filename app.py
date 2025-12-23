import streamlit as st
import pandas as pd
import plotly.express as px
from migros_scraper import google_sheets_baglan

# --- SAYFA AYARLARI (Modern Görünüm İçin) ---
st.set_page_config(
    page_title="Migros Fiyat Analiz",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS (Daha şık görünmesi için makyaj)
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        color: #ff4b4b;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛒 Migros Akıllı Fiyat Takip Sistemi")
st.markdown("---")

# --- VERİ ÇEKME FONKSİYONU ---
@st.cache_data(ttl=600) # Veriyi 10 dakikada bir hatırla, siteyi hızlandırır
def veri_getir():
    sheet = google_sheets_baglan()
    if not sheet:
        return pd.DataFrame()
    
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Sayı düzeltmeleri
        if not df.empty:
            df["Fiyat"] = pd.to_numeric(df["Fiyat"], errors='coerce')
            df["Normal Fiyat"] = pd.to_numeric(df["Normal Fiyat"], errors='coerce')
            df["İndirim %"] = pd.to_numeric(df["İndirim %"], errors='coerce')
            df["Tarih"] = pd.to_datetime(df["Tarih"])
        return df
    except:
        return pd.DataFrame() # Boşsa hata verme, boş tablo dön

df = veri_getir()

# --- EĞER VERİ YOKSA UYARI ---
if df.empty:
    st.info("👋 Hoşgeldin! Sistem kurulumu tamamlandı.")
    st.warning("⚠️ Henüz veritabanında veri yok. Robot henüz çalışmadı. Veriler gelince burası otomatik dolacak.")
    st.stop()

# --- SOL MENÜ (FİLTRELER) ---
with st.sidebar:
    st.header("🔍 Filtreleme")
    
    # İsim Arama
    arama = st.text_input("Ürün Ara", placeholder="Örn: Ayçiçek Yağı")
    
    # Kategori (Durum) Seçimi
    secilen_durum = st.multiselect(
        "Fırsat Durumu",
        options=["FIRSAT", "SÜPER FIRSAT", "OLASI HATA", "Normal"],
        default=["FIRSAT", "SÜPER FIRSAT", "OLASI HATA"] # Varsayılan olarak fırsatları göster
    )
    
    st.caption("Veriler otomatik olarak güncellenir.")

# --- VERİYİ FİLTRELEME ---
# En son çekilen verileri al (Her ürünün son halini)
df_son = df.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

if arama:
    df_son = df_son[df_son["Ürün Adı"].str.contains(arama, case=False)]

if secilen_durum:
    df_son = df_son[df_son["Durum"].isin(secilen_durum)]

# --- ÜST BİLGİ KARTLARI (METRICS) ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Takip Edilen", f"{len(df_son)} Ürün")
col2.metric("Fırsat Sayısı", f"{len(df_son[df_son['Durum'].str.contains('FIRSAT')])} Adet")
col3.metric("Olası Hata", f"{len(df_son[df_son['Durum'] == 'OLASI HATA'])} Adet")
col4.metric("Ortalama İndirim", f"%{df_son['İndirim %'].mean():.1f}")

st.markdown("---")

# --- ANA İÇERİK (SEKMELER) ---
tab_liste, tab_grafik = st.tabs(["📋 Ürün Listesi", "📈 Fiyat Analizi"])

with tab_liste:
    st.dataframe(
        df_son[["Resim", "Ürün Adı", "Fiyat", "Normal Fiyat", "İndirim %", "Durum", "Birim Fiyat", "Link"]],
        column_config={
            "Resim": st.column_config.ImageColumn("Görsel", width="small"),
            "Ürün Adı": st.column_config.TextColumn("Ürün İsmi", width="large"),
            "Fiyat": st.column_config.NumberColumn("Fiyat", format="%.2f ₺"),
            "Normal Fiyat": st.column_config.NumberColumn("Normal", format="%.2f ₺"),
            "İndirim %": st.column_config.ProgressColumn("İndirim", format="%.0f%%", min_value=0, max_value=100),
            "Link": st.column_config.LinkColumn("Git", display_text="Satın Al")
        },
        use_container_width=True,
        hide_index=True,
        height=600
    )

with tab_grafik:
    st.subheader("Ürün Fiyat Geçmişi")
    grafik_urun = st.selectbox("İncelemek istediğin ürünü seç:", df_son["Ürün Adı"].unique())
    
    if grafik_urun:
        # Seçilen ürünün tüm tarihçesini al
        gecmis_veri = df[df["Ürün Adı"] == grafik_urun].sort_values("Tarih")
        
        fig = px.line(gecmis_veri, x="Tarih", y="Fiyat", 
                     title=f"{grafik_urun} - Fiyat Değişimi",
                     markers=True)
        fig.update_layout(xaxis_title="Tarih", yaxis_title="Fiyat (TL)")
        st.plotly_chart(fig, use_container_width=True)
