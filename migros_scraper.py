import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- GÜNCELLENMİŞ GENİŞ KATEGORİ LİSTESİ ---
KATEGORILER = [
    "meyve-sebze-c-2",              # Meyve, Sebze
    "et-tavuk-balik-c-3",           # Et, Tavuk, Balık
    "sut-kahvaltilik-c-4",          # Süt, Kahvaltılık
    "temel-gida-c-5",               # Temel Gıda (Yağ, Bakliyat vb.)
    "meze-hazir-yemek-donuk-c-7d",  # Meze, Hazır Yemek
    "firin-pastane-c-6",            # Fırın, Pastane
    "dondurma-c-41b",               # Dondurma
    "atistirmalik-c-b",             # Atıştırmalık (Cips, Çikolata vb.)
    "icecek-c-c",                   # İçecek (Su, Kola, Meyve Suyu)
    "deterjan-temizlik-c-d",        # Deterjan, Temizlik, Kağıt Ürünleri
    "kisisel-bakim-kozmetik-c-e",   # Kişisel Bakım, Kozmetik
    "bebek-c-8",                    # Bebek Ürünleri
    "ev-yasam-c-9",                 # Ev, Yaşam
    "kitap-kirtasiye-oyuncak-c-a",  # Kitap, Kırtasiye, Oyuncak
    "evcil-dostlar-c-10d",          # Evcil Hayvan (Kedi, Köpek Maması vb.)
    "elektronik-c-11"               # Elektronik
]

def google_sheets_baglan():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        import streamlit as st
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    except:
        if os.path.exists("secrets.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
        else:
            return None

    client = gspread.authorize(creds)
    sheet = client.open("Migros_Takip_DB").sheet1
    return sheet

def tr_format(sayi):
    """Sayıyı nokta yerine virgüllü metne çevirir"""
    if sayi is None: return "0"
    return f"{float(sayi):.2f}".replace('.', ',')

def veri_cek(slug):
    tum_urunler = []
    page = 1
    
    # Güvenlik Limiti: Sonsuz döngüye girmesin diye max 100 sayfa
    while page <= 100:
        url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "X-PWA": "true"
        }
        
        try:
            # Migros'a yüklenmemek için bekleme
            time.sleep(0.3)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                break
            
            data = response.json()
            
            raw_products = []
            try:
                raw_products = data["data"]["searchInfo"]["storeProductInfos"]
            except:
                try:
                    raw_products = data["data"]["products"]
                except:
                    pass
            
            if not raw_products:
                break

            print(f"Kategori: {slug} | Sayfa: {page} | Ürün: {len(raw_products)}")

            for item in raw_products:
                try:
                    name = item.get("name", "")
                    
                    # Fiyatları al
                    regular_price = item.get("regularPrice", 0) / 100
                    shown_price = item.get("shownPrice", 0) / 100
                    
                    if regular_price == 0:
                        regular_price = shown_price

                    exhausted = item.get("exhausted", False)
                    stok = "Yok" if exhausted else "Var"
                    
                    # İndirim Tipi (2 Al 1 Öde vb.)
                    badges = item.get("badges", [])
                    indirim_tipi = ""
                    if badges:
                        indirim_tipi = ", ".join([b.get("value", "") for b in badges])

                    # İndirim Oranı Hesapla
                    indirim_orani = 0
                    durum = "Normal"
                    
                    if regular_price > shown_price:
                        indirim_orani = ((regular_price - shown_price) / regular_price) * 100
                        if indirim_orani > 50: durum = "SÜPER FIRSAT"
                        elif indirim_orani >= 20: durum = "FIRSAT"
                        
                    if "Öde" in indirim_tipi or "Hediye" in indirim_tipi:
                        durum = "ÇOKLU ALIM FIRSATI"

                    images = item.get("images", [])
                    image_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
                    urun_linki = f"https://www.migros.com.tr/{item.get('prettyName', '')}-{item.get('id')}"

                    birim_fiyat = "0"
                    birim = "Adet"
                    match = re.search(r"(\d+)\s*(KG|L|Litre|Lt|Gr|Gram)", name, re.IGNORECASE)
                    if match:
                        birim = match.group(2).upper()

                    tum_urunler.append([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        name,
                        tr_format(regular_price),
                        tr_format(shown_price),
                        indirim_tipi,
                        tr_format(indirim_orani),
                        durum,
                        stok,
                        tr_format(birim_fiyat),
                        birim,
                        slug,
                        image_url,
                        urun_linki
                    ])
                except:
                    continue
            
            page += 1
            
        except Exception as e:
            print(f"Hata: {e}")
            break
            
    return tum_urunler

def calistir():
    tum_veriler = []
    print("Tarama başlıyor...")
    
    # Tekrarlayan ürünleri engellemek için kontrol listesi
    eklenen_urunler = set()
    nihai_liste = []

    for kat in KATEGORILER:
        gelen_veri = veri_cek(kat)
        for satir in gelen_veri:
            urun_adi = satir[1]
            # Eğer ürün daha önce eklenmediyse listeye al
            if urun_adi not in eklenen_urunler:
                nihai_liste.append(satir)
                eklenen_urunler.add(urun_adi)
    
    df = pd.DataFrame(nihai_liste, columns=[
        "Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi",
        "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"
    ])
    
    sheet = google_sheets_baglan()
    if sheet:
        # RAW formatında yazıyoruz ki Google sayıları değiştirmesin
        sheet.append_rows(df.values.tolist(), value_input_option='RAW')
        print(f"İşlem tamam. Toplam {len(nihai_liste)} ürün veritabanına eklendi.")
