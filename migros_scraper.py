import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- TAM KATEGORİ LİSTESİ (SİTEDEKİ MENÜYE GÖRE) ---
KATEGORILER = [
    "meyve-sebze-c-2",                  # Meyve, Sebze
    "et-tavuk-balik-c-3",               # Et, Tavuk, Balık
    "sut-kahvaltilik-c-4",              # Süt, Kahvaltılık
    "temel-gida-c-5",                   # Temel Gıda
    "icecek-c-c",                       # İçecek
    "atistirmalik-c-b",                 # Atıştırmalık
    "dondurma-c-41b",                   # Dondurma
    "firin-pastane-c-6",                # Fırın, Pastane
    "meze-hazir-yemek-donuk-c-7d",      # Meze, Hazır Yemek, Donuk
    "deterjan-temizlik-c-d",            # Deterjan, Temizlik
    "kisisel-bakim-kozmetik-c-e",       # Kişisel Bakım, Kozmetik, Sağlık
    "bebek-c-8",                        # Bebek
    "ev-yasam-c-9",                     # Ev, Yaşam
    "kitap-kirtasiye-oyuncak-c-a",      # Kitap, Kırtasiye, Oyuncak
    "evcil-dostlar-c-10d",              # Evcil Hayvan
    "elektronik-c-11"                   # Elektronik
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
    return client.open("Migros_Takip_DB")

def tr_format(sayi):
    if sayi is None: return "0"
    return f"{float(sayi):.2f}".replace('.', ',')

def kampanya_temizle(badges):
    temiz = []
    for b in badges:
        val = b.get("value", "")
        if not val: continue
        if "TL" in val or re.match(r'^[\d.,]+$', val.strip()): continue
        temiz.append(val)
    return ", ".join(temiz) if temiz else ""

def veri_cek(slug):
    tum_urunler = []
    page = 1
    max_sayfa = 50 
    
    while page <= max_sayfa:
        # Migros API Adresi
        url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "X-PWA": "true"
        }
        
        try:
            time.sleep(0.5) 
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"⚠️ {slug} | Sayfa {page} yanıt vermedi. Kod: {response.status_code}")
                break
            
            data = response.json()
            raw_products = []
            
            # API yapısı bazen değişiyor, tüm ihtimalleri dene
            keys_to_check = [
                ["data", "searchInfo", "storeProductInfos"],
                ["data", "products"],
                ["data", "storeProductInfos"]
            ]
            
            for key_path in keys_to_check:
                try:
                    temp_data = data
                    for key in key_path:
                        temp_data = temp_data[key]
                    raw_products = temp_data
                    if raw_products: break
                except:
                    continue
            
            if not raw_products:
                break
            
            print(f"✅ {slug} | Sayfa: {page} | Ürün: {len(raw_products)}")

            for item in raw_products:
                try:
                    name = item.get("name", "")
                    reg_p = item.get("regularPrice", 0) / 100
                    shown_p = item.get("shownPrice", 0) / 100
                    if reg_p == 0: reg_p = shown_p

                    indirim_tipi = kampanya_temizle(item.get("badges", []))
                    
                    indirim_orani = 0
                    durum = "Normal"
                    if reg_p > shown_p:
                        indirim_orani = ((reg_p - shown_p) / reg_p) * 100
                        if indirim_orani > 50: durum = "SÜPER FIRSAT"
                        elif indirim_orani >= 20: durum = "FIRSAT"
                        
                    if "Öde" in indirim_tipi or "Hediye" in indirim_tipi: durum = "ÇOKLU ALIM"

                    images = item.get("images", [])
                    img_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
                    
                    # LİNK DÜZELTME
                    urun_linki = f"https://www.migros.com.tr/{item.get('prettyName', '')}"

                    birim_fiyat = "0"
                    birim = "Adet"
                    match = re.search(r"(\d+)\s*(KG|L|Litre|Lt|Gr|Gram)", name, re.IGNORECASE)
                    if match: birim = match.group(2).upper()

                    tum_urunler.append([
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        name,
                        tr_format(reg_p),
                        tr_format(shown_p),
                        indirim_tipi,
                        tr_format(indirim_orani),
                        durum,
                        "Var",
                        tr_format(birim_fiyat),
                        birim,
                        slug,
                        img_url,
                        urun_linki
                    ])
                except: continue
            page += 1
        except Exception as e:
            print(f"⚠️ Hata ({slug}): {e}")
            break
            
    return tum_urunler

def calistir():
    print("🚀 Tarama başlatılıyor...")
    spreadsheet = google_sheets_baglan()
    if not spreadsheet:
        print("❌ Google Sheets bağlantısı başarısız!")
        return

    # 1. Ana Veritabanı
    try:
        ana_sheet = spreadsheet.worksheet("Ana_Veritabani")
    except:
        ana_sheet = spreadsheet.add_worksheet(title="Ana_Veritabani", rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        ana_sheet.append_row(basliklar)

    # 2. Günlük Yedek
    gunluk_sheet = None
    try:
        sayfa_ismi = datetime.now().strftime("%d.%m.%Y - %H:%M")
        gunluk_sheet = spreadsheet.add_worksheet(title=sayfa_ismi, rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        gunluk_sheet.append_row(basliklar)
        print(f"📅 Yeni sayfa açıldı: {sayfa_ismi}")
    except:
        print("⚠️ Günlük sayfa oluşturulamadı.")

    toplam_kayit = 0
    
    for kat in KATEGORILER:
        print(f"⏳ {kat} taranıyor...")
        veriler = veri_cek(kat)
        
        if veriler:
            try:
                # Ana veritabanına ekle
                ana_sheet.append_rows(veriler, value_input_option='RAW')
                # Günlük sayfaya ekle
                if gunluk_sheet:
                    gunluk_sheet.append_rows(veriler, value_input_option='RAW')
                
                print(f"💾 {kat} kaydedildi. ({len(veriler)} ürün)")
                toplam_kayit += len(veriler)
            except Exception as e:
                print(f"❌ Yazma hatası ({kat}): {e}")
        else:
            print(f"⚠️ {kat} boş döndü.")

    print(f"🏁 İŞLEM TAMAMLANDI! Toplam {toplam_kayit} ürün güncellendi.")
