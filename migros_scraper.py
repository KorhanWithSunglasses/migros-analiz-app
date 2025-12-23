import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- KATEGORİLER ---
KATEGORILER = [
    "meyve-sebze-c-2", "et-tavuk-balik-c-3", "sut-kahvaltilik-c-4",
    "temel-gida-c-5", "meze-hazir-yemek-donuk-c-7d", "firin-pastane-c-6",
    "dondurma-c-41b", "atistirmalik-c-b", "icecek-c-c",
    "deterjan-temizlik-c-d", "kisisel-bakim-kozmetik-c-e", "bebek-c-8",
    "ev-yasam-c-9", "kitap-kirtasiye-oyuncak-c-a", "evcil-dostlar-c-10d",
    "elektronik-c-11"
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
    if sayi is None: return "0"
    return f"{float(sayi):.2f}".replace('.', ',')

# --- YENİ: KAMPANYA TEMİZLEYİCİ ---
def kampanya_temizle(badges):
    """Badges listesindeki anlamsız fiyatları ve kodları temizler."""
    temiz_kampanyalar = []
    for b in badges:
        val = b.get("value", "")
        if not val: continue
        
        # İçinde "TL" geçen veya sadece rakam/nokta/virgülden oluşanları at
        # Örn: "249,95 TL" veya "59.90" gibi değerleri filtrele
        if "TL" in val or re.match(r'^[\d.,]+$', val.strip()):
            continue
            
        # Kalan anlamlı metinleri (Örn: "2 Al 1 Öde") listeye ekle
        temiz_kampanyalar.append(val)
        
    return ", ".join(temiz_kampanyalar) if temiz_kampanyalar else ""

def veri_cek(slug):
    tum_urunler = []
    page = 1
    # Güvenlik Limiti: Max 80 sayfa (Migros genelde 50-60 sayfa oluyor)
    while page <= 80:
        url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page={page}"
        headers = {"User-Agent": "Mozilla/5.0", "X-PWA": "true"}
        
        try:
            time.sleep(0.4) # Biraz daha yavaşlayalım, banlanmayalım
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200: break
            
            data = response.json()
            raw_products = []
            try:
                raw_products = data["data"]["searchInfo"]["storeProductInfos"]
            except:
                try:
                    raw_products = data["data"]["products"]
                except:
                    pass
            
            if not raw_products: break

            print(f"Kategori: {slug} | Sayfa: {page} | Ürün: {len(raw_products)}")

            for item in raw_products:
                try:
                    name = item.get("name", "")
                    regular_price = item.get("regularPrice", 0) / 100
                    shown_price = item.get("shownPrice", 0) / 100
                    if regular_price == 0: regular_price = shown_price

                    exhausted = item.get("exhausted", False)
                    stok = "Yok" if exhausted else "Var"
                    
                    # YENİ FONKSİYONU KULLAN
                    badges = item.get("badges", [])
                    indirim_tipi = kampanya_temizle(badges)

                    indirim_orani = 0
                    durum = "Normal"
                    if regular_price > shown_price:
                        indirim_orani = ((regular_price - shown_price) / regular_price) * 100
                        if indirim_orani > 50: durum = "SÜPER FIRSAT"
                        elif indirim_orani >= 20: durum = "FIRSAT"
                        
                    if "Öde" in indirim_tipi or "Hediye" in indirim_tipi or "İkincisi" in indirim_tipi:
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
        except:
            break
    return tum_urunler

def calistir():
    print("Tarama başlıyor...")
    eklenen_urunler = set()
    sheet = google_sheets_baglan()
    
    if not sheet: return

    for kat in KATEGORILER:
        print(f"{kat} taranıyor...")
        kategori_verisi = veri_cek(kat)
        yazilacak_liste = []
        
        for satir in kategori_verisi:
            urun_adi = satir[1]
            if urun_adi not in eklenen_urunler:
                yazilacak_liste.append(satir)
                eklenen_urunler.add(urun_adi)
        
        if yazilacak_liste:
            try:
                sheet.append_rows(yazilacak_liste, value_input_option='RAW')
                print(f"✅ {kat}: {len(yazilacak_liste)} ürün yazıldı.")
            except:
                time.sleep(5) # Hata olursa 5sn bekle
                try: sheet.append_rows(yazilacak_liste, value_input_option='RAW')
                except: pass
        
        time.sleep(3) # Kategori arası bekleme

    print("🎉 Tüm işlem tamamlandı.")
