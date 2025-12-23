import streamlit as st
import pandas as pd
import plotly.express as px
import time
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Tam Analiz", page_icon="🛒", layout="wide")

# CSS
st.markdown("""
<style>
    .stMetric {background-color: #f0f2f6; border-radius: 10px; padding: 10px; text-align: center;}
    div[data-testid="stDataFrame"] {width: 100%;}
</style>
""", unsafe_allow_html=True)

st.title("🛒 Migros Geniş Kapsamlı Fiyat Takip")
st.markdown("---")

# --- YARDIMCI FONKSİYONLAR ---
def temizle_ve_cevir(val):
    try:
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('TL', '').replace('₺', '').strip()
        s = s.replace('.', '') # Binlik ayracı sil
        s = s.replace(',', '.') # Ondalık virgülü noktaya çevir
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

        # İlk satırı başlık yap
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        
        # Sütun isimlerindeki boşlukları temizle (Garanti olsun)
        df.columns = df.columns.str.strip()
        
        return df
    except Exception as e:
        st.error(f"Veri okuma hatası: {e}")
        return pd.DataFrame()

# --- SOL MENÜ ---
with st.sidebar:
    st.header("⚙️ İşlemler")
    
    if st.button("🚀 Tüm Market Verisini Güncelle"):
        st.warning("⚠️ Tüm kategoriler taranıyor, lütfen bekleyin...")
        with st.spinner("Robot marketi geziyor..."):
            try:
                calistir()
                st.success("İşlem Tamam! Sayfa yenileniyor...")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")

    st.divider()
    st.header("🔍 Filtreler")
    
    # Veriyi Çek
    df_raw = veri_getir()

    # --- HATA KONTROLÜ ---
    # Eğer başlıklar eksikse işlem yapma
    gerekli_sutunlar = ["Tarih", "Ürün Adı", "Kategori", "Durum"]
    eksik_var_mi = False
    if not df_raw.empty:
        for col in gerekli_sutunlar:
            if col not in df_raw.columns:
                eksik_var_mi = True
                break
    
    if df_raw.empty or eksik_var_mi:
        st.warning("⚠️ Veritabanı boş veya başlıklar hatalı.")
        st.info("Lütfen yukarıdaki 'Tüm Market Verisini Güncelle' butonuna basın.")
        st.stop() # Kodun geri kalanını çalıştırma, burada dur.

    # --- VERİ İŞLEME (Sadece veri varsa buraya gelir) ---
    # Sayısal Çeviri
    for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
        if c in df_raw.columns:
            df_raw[c] = df_raw[c].apply(temizle_ve_cevir)
            
    if "Tarih" in df_raw.columns:
        df_raw["Tarih"] = pd.to_datetime(df_raw["Tarih"], errors='coerce')

    # Filtreleme Arayüzü
    arama = st.text_input("Ürün Ara", placeholder="Örn: Kıyma")
    
    kategori_listesi = ["Tümü"]
    if "Kategori" in df_raw.columns:
        katlar = sorted(df_raw["Kategori"].astype(str).unique().tolist())
        kategori_listesi += katlar
        
    secilen_kategori = st.selectbox("Kategori Seç", kategori_listesi)
    firsat_filtresi = st.checkbox("Sadece Fırsatları Göster", value=False)

# --- ANA EKRAN ---
df_son = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# Filtreleri Uygula
if arama:
    df_son = df_son[df_son["Ürün Adı"].str.contains(arama, case=False)]
if secilen_kategori != "Tümü":
    df_son = df_son[df_son["Kategori"] == secilen_kategori]
if firsat_filtresi:
    df_son = df_son[df_son["Durum"] != "Normal"]

# Özet Kartlar
c1, c2, c3, c4 = st.columns(4)
c1.metric("Toplam Ürün", len(df_son))
indirimli = df_son[df_son["İndirim %"] > 0]
c2.metric("İndirimli Ürün", len(indirimli))

ort = indirimli["İndirim %"].mean() if not indirimli.empty else 0
c3.metric("Ortalama İndirim", f"%{ort:.1f}")

yildiz = indirimli.sort_values("İndirim %", ascending=False).iloc[0] if not indirimli.empty else None
if yildiz is not None:
    c4.metric("Günün Yıldızı", f"%{yildiz['İndirim %']:.0f}")
else:
    c4.metric("Günün Yıldızı", "-")

st.markdown("### 📋 Ürün Listesi")

# Tablo
gosterilecek = ["Resim", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Link"]
cols = [c for c in gosterilecek if c in df_son.columns]

event = st.dataframe(
    df_son[cols],
    column_config={
        "Resim": st.column_config.ImageColumn("Görsel", width="small"),
        "Etiket Fiyatı": st.column_config.NumberColumn(format="%.2f ₺"),
        "Satış Fiyatı": st.column_config.NumberColumn(format="%.2f ₺"),
        "İndirim %": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "Link": st.column_config.LinkColumn("Git", display_text="Satın Al")
    },
    use_container_width=True,
    hide_index=True,
    selection_mode="single-row",
    on_select="rerun",
    height=600
)

# Grafik
st.divider()
secilen = event.selection.rows
if secilen:
    idx = secilen[0]
    urun_adi = df_son.iloc[idx]["Ürün Adı"]
    st.subheader(f"📈 {urun_adi} - Fiyat Analizi")
    
    gecmis = df_raw[df_raw["Ürün Adı"] == urun_adi].sort_values("Tarih")
    
    fig = px.line(gecmis, x="Tarih", y="Satış Fiyatı", title="Fiyat Değişimi", markers=True)
    if "Etiket Fiyatı" in gecmis.columns:
        fig.add_scatter(x=gecmis["Tarih"], y=gecmis["Etiket Fiyatı"], mode='lines', 
                       name='Etiket Fiyatı', line=dict(dash='dash', color='gray'))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Grafik görmek için listeden bir ürüne tıklayın.")
