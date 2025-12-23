import streamlit as st
import pandas as pd
import plotly.express as px
import time
from migros_scraper import google_sheets_baglan, calistir

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Migros Tam Analiz", page_icon="🛒", layout="wide")

# CSS (Görünüm İyileştirmeleri)
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
    """Metin olarak gelen '1.250,50' gibi sayıları Python'un anlayacağı sayıya çevirir."""
    try:
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('TL', '').replace('₺', '').strip()
        # Binlik ayracı olan noktayı sil (1.500 -> 1500)
        s = s.replace('.', '')
        # Ondalık ayracı olan virgülü noktaya çevir (1500,50 -> 1500.50)
        s = s.replace(',', '.')
        return float(s)
    except:
        return 0.0

@st.cache_data(ttl=600)
def veri_getir():
    sheet = google_sheets_baglan()
    if not sheet: return pd.DataFrame()
    
    try:
        # get_all_records yerine get_all_values kullanıyoruz (Daha sağlam)
        data = sheet.get_all_values()
        
        if not data:
            return pd.DataFrame()

        # İlk satırı başlık olarak al
        headers = data.pop(0)
        df = pd.DataFrame(data, columns=headers)
        
        if not df.empty:
            # Sayısal dönüşümler (Hata almamak için sütun var mı diye kontrol ediyoruz)
            for c in ["Etiket Fiyatı", "Satış Fiyatı", "İndirim %"]:
                if c in df.columns:
                    df[c] = df[c].apply(temizle_ve_cevir)
            
            if "Tarih" in df.columns:
                df["Tarih"] = pd.to_datetime(df["Tarih"], errors='coerce')
                
        return df
    except Exception as e:
        st.error(f"Veri okunurken hata oluştu: {e}")
        return pd.DataFrame()

# --- SOL MENÜ (FİLTRELER VE BUTON) ---
with st.sidebar:
    st.header("⚙️ İşlemler")
    
    # Güncelleme Butonu
    if st.button("🚀 Tüm Market Verisini Güncelle"):
        st.warning("⚠️ Bu işlem tüm kategorileri taradığı için uzun sürebilir.")
        with st.spinner("Robot marketi geziyor..."):
            try:
                calistir()
                st.success("Tarama Bitti! Sayfa yenileniyor...")
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Hata: {e}")

    st.divider()
    st.header("🔍 Filtreler")
    
    # Veriyi Çek
    df_raw = veri_getir()
    
    # Arama Kutusu
    arama = st.text_input("Ürün Ara", placeholder="Örn: Kıyma")
    
    # Kategori Filtresi
    kategori_listesi = ["Tümü"]
    if not df_raw.empty and "Kategori" in df_raw.columns:
        # Kategorileri alfabetik sırala
        katlar = sorted(df_raw["Kategori"].astype(str).unique().tolist())
        kategori_listesi += katlar
        
    secilen_kategori = st.selectbox("Kategori Seç", kategori_listesi)
    
    # "Sadece Fırsatlar" kutusunu varsayılan olarak KAPALI yaptım ki tüm ürünler görünsün
    firsat_filtresi = st.checkbox("Sadece Fırsatları Göster", value=False)

# --- ANA EKRAN MANTIĞI ---
if df_raw.empty:
    st.info("⚠️ Veri şu an yükleniyor veya veritabanı boş. Lütfen sol menüden güncelleme yapın veya biraz bekleyin.")
    st.stop()

# Veriyi Hazırla (Her ürünün en son tarihli halini al)
df_son = df_raw.sort_values("Tarih", ascending=False).drop_duplicates("Ürün Adı")

# 1. Filtre: Arama
if arama:
    df_son = df_son[df_son["Ürün Adı"].str.contains(arama, case=False)]

# 2. Filtre: Kategori
if secilen_kategori != "Tümü":
    df_son = df_son[df_son["Kategori"] == secilen_kategori]

# 3. Filtre: Fırsat Durumu
if firsat_filtresi:
    if "Durum" in df_son.columns:
        df_son = df_son[df_son["Durum"] != "Normal"]

# --- ÖZET KARTLAR ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Toplam Ürün", len(df_son))

indirimli_sayisi = len(df_son[df_son["İndirim %"] > 0])
col2.metric("İndirimli Ürün", indirimli_sayisi)

ortalama_indirim = 0
if indirimli_sayisi > 0:
    ortalama_indirim = df_son[df_son["İndirim %"] > 0]["İndirim %"].mean()
col3.metric("Ortalama İndirim", f"%{ortalama_indirim:.1f}")

# En yüksek indirim
max_indirim_urun = None
if not df_son.empty:
    max_indirim_urun = df_son.sort_values("İndirim %", ascending=False).iloc[0]
    
if max_indirim_urun is not None and max_indirim_urun['İndirim %'] > 0:
    col4.metric("Günün Yıldızı", f"%{max_indirim_urun['İndirim %']:.0f} İndirim")
else:
    col4.metric("Günün Yıldızı", "-")

st.markdown("### 📋 Ürün Listesi (Grafik için satıra tıkla)")

# --- TABLO ---
# Hangi sütunları göstereceğimizi belirleyelim
gosterilecek_sutunlar = ["Resim", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Link"]
# Eğer veride olmayan sütun varsa hata vermesin diye filtreleyelim
mevcut_sutunlar = [col for col in gosterilecek_sutunlar if col in df_son.columns]

event = st.dataframe(
    df_son[mevcut_sutunlar],
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

# --- GRAFİK ---
st.divider()

secilen_satir = event.selection.rows
if secilen_satir:
    index = secilen_satir[0]
    # Tablodaki sıraya göre ürün adını bul
    secilen_urun_adi = df_son.iloc[index]["Ürün Adı"]
    
    st.subheader(f"📈 Fiyat Analizi: {secilen_urun_adi}")
    
    # O ürünün tüm geçmişini bul
    gecmis_veri = df_raw[df_raw["Ürün Adı"] == secilen_urun_adi].sort_values("Tarih")
    
    if not gecmis_veri.empty:
        fig = px.line(gecmis_veri, x="Tarih", y="Satış Fiyatı", 
                      title="Zaman İçinde Fiyat Değişimi", markers=True)
        
        # Etiket fiyatını referans çizgi olarak ekle
        fig.add_scatter(x=gecmis_veri["Tarih"], y=gecmis_veri["Etiket Fiyatı"], 
                        mode='lines', name='Etiket Fiyatı', line=dict(dash='dash', color='gray'))
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Varsa ekstra bilgi göster
        son_durum = gecmis_veri.iloc[-1]
        if "İndirim Tipi" in son_durum and son_durum["İndirim Tipi"]:
            st.info(f"💡 **Kampanya Notu:** {son_durum['İndirim Tipi']}")
    else:
        st.warning("Bu ürün için yeterli geçmiş veri yok.")

else:
    st.info("👆 Grafiğini görmek istediğiniz ürünün üzerine tıklayın.")
