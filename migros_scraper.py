import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- TAKİP EDİLECEK TÜM KATEGORİLER ---
# Robot bu listeyi sırasıyla gezecek.
KATEGORILER = [
    "elektronik-c-11",              # Önce Elektronik (Telefon vb.)
    "meyve-sebze-c-2",
    "et-tavuk-balik-c-3",
    "sut-kahvaltilik-c-4",
    "temel-gida-c-5",
    "meze-hazir-yemek-donuk-c-7d",
    "firin-pastane-c-6",
    "dondurma-c-41b",
    "atistirmalik-c-b",
    "icecek-c-c",
    "deterjan-temizlik-c-d",
    "kisisel-bakim-kozmetik-c-e",
    "bebek-c-8",
    "ev-yasam-c-9",
    "kitap-kirtasiye-oyuncak-c-a",
    "evcil-dostlar-c-10d"
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
    max_sayfa = 50 # Her kategori için güvenlik limiti
    
    while page <= max_sayfa:
        url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page={page}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "X-PWA": "true"
        }
        
        try:
            time.sleep(0.5) # Migros'u yormamak için bekleme süresi
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200: break
            
            data = response.json()
            raw_products = []
            
            # Ürün verisi farklı yollarda olabilir
            try: raw_products = data["data"]["searchInfo"]["storeProductInfos"]
            except: 
                try: raw_products = data["data"]["products"]
                except: pass
            
            if not raw_products: break
            
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
                    
                    # LİNK DÜZELTME (Sadece prettyName kullanıyoruz, ID yok)
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
            print(f"⚠️ Sayfa hatası ({slug}): {e}")
            break
            
    return tum_urunler

def calistir():
    print("🚀 Tarama başlatılıyor...")
    spreadsheet = google_sheets_baglan()
    if not spreadsheet:
        print("❌ Google Sheets bağlantısı başarısız!")
        return

    # 1. Ana Veritabanı Sayfası
    try:
        ana_sheet = spreadsheet.worksheet("Ana_Veritabani")
    except:
        ana_sheet = spreadsheet.add_worksheet(title="Ana_Veritabani", rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        ana_sheet.append_row(basliklar)

    # 2. Günlük Yedek Sayfası
    gunluk_sheet = None
    try:
        sayfa_ismi = datetime.now().strftime("%d.%m.%Y - %H:%M")
        gunluk_sheet = spreadsheet.add_worksheet(title=sayfa_ismi, rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        gunluk_sheet.append_row(basliklar)
        print(f"📅 Yeni sayfa açıldı: {sayfa_ismi}")
    except:
        print("⚠️ Günlük sayfa zaten var veya oluşturulamadı.")

    toplam_kayit = 0
    
    # PARÇA PARÇA KAYDETME (Veri Kaybını Önler)
    for kat in KATEGORILER:
        print(f"⏳ {kat} taranıyor...")
        veriler = veri_cek(kat)
        
        if veriler:
            try:
                # Ana veritabanına ekle
                ana_sheet.append_rows(veriler, value_input_option='RAW')
                # Günlük sayfaya ekle (varsa)
                if gunluk_sheet:
                    gunluk_sheet.append_rows(veriler, value_input_option='RAW')
                
                print(f"💾 {kat} kaydedildi. ({len(veriler)} ürün)")
                toplam_kayit += len(veriler)
            except Exception as e:
                print(f"❌ Yazma hatası ({kat}): {e}")
        else:
            print(f"⚠️ {kat} kategorisinden ürün gelmedi.")

    print(f"🏁 İŞLEM TAMAMLANDI! Toplam {toplam_kayit} ürün güncellendi.")
