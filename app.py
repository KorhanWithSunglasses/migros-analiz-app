import streamlit as st
import pandas as pd
import plotly.express as px
from migros_scraper import google_sheets_baglan, calistir  # calistir fonksiyonunu ekledik

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Migros Fiyat Analiz",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Özel CSS
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛒 Migros Akıllı Fiyat Takip Sistemi")
st.markdown("---")

# --- SOL MENÜ ---
with st.sidebar:
    st.header("⚙️ Kontrol Paneli")
    
    # --- ROBOTU ÇALIŞTIRMA BUTONU ---
    if st.button("🚀 Verileri Şimdi Güncelle"):
        with st.spinner("Robot Migros'a gidiyor, fiyatlar toplanıyor... Lütfen bekleyin."):
            try:
                calistir() # Robotu çalıştır
                st.success("Veriler başarıyla güncellendi!")
                st.cache_data.clear() # Eski önbelleği temizle
            except Exception as e:
                st.error(f"Bir hata oluştu: {e}")
    
    st.divider()
    
    st.header("🔍 Filtreleme")
    arama = st.text_input("Ürün Ara", placeholder="Örn: Ayçiçek Yağı")
    secilen_durum = st.multiselect(
        "Fırsat Durumu",
        options=["FIRSAT", "SÜPER FIRSAT", "OLASI HATA", "Normal"],
        default=["FIRSAT", "SÜPER FIRSAT", "OLASI HATA"]
    )

# --- VERİ ÇEKME FONKSİYONU ---
@st.cache_data(ttl=600)
def veri_getir():
    sheet = google_sheets_baglan()
    if not sheet:
        return pd.DataFrame()
    
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df["Fiyat"] = pd.to_numeric(df["Fiyat"], errors='coerce')
            df["Normal Fiyat"] = pd.to_numeric(df["Normal Fiyat"], errors='coerce')
            df["İndirim %"] = pd.to_numeric(df["İndirim %"], errors='coerce')
            df["Tarih"] = pd.to_datetime(df["Tarih"])
        return df
    except:
        return pd.DataFrame()

df = veri_getir()

# --- EĞER VERİ YOKSA ---
if df.empty:
    st.info("👋 Sistem hazır!")
    st.warning("⚠️ Veritabanı boş. Lütfen sol menüdeki **'Verileri Şimdi Güncelle'** butonuna bas.")
    st.stop()

# --- VERİ VARSA DEVAM ET ---
df_son = df.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

if arama:
    df_son = df_son[df_son["Ürün Adı"].str.contains(arama, case=False)]

if secilen_durum:
    df_son = df_son[df_son["Durum"].isin(secilen_durum)]

# --- METRICS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Takip Edilen", f"{len(df_son)} Ürün")
col2.metric("Fırsat Sayısı", f"{len(df_son[df_son['Durum'].str.contains('FIRSAT')])} Adet")
col3.metric("Olası Hata", f"{len(df_son[df_son['Durum'] == 'OLASI HATA'])} Adet")
col4.metric("Ortalama İndirim", f"%{df_son['İndirim %'].mean():.1f}")

st.markdown("---")

# --- SEKMELER ---
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
        gecmis_veri = df[df["Ürün Adı"] == grafik_urun].sort_values("Tarih")
        fig = px.line(gecmis_veri, x="Tarih", y="Fiyat", title=f"{grafik_urun} Fiyat Değişimi", markers=True)
        st.plotly_chart(fig, use_container_width=True)
