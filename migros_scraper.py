import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- KATEGORİ LİSTESİ ---
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
    # Limit: 50 sayfa
    while page <= 50:
        url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page={page}"
        headers = {"User-Agent": "Mozilla/5.0", "X-PWA": "true"}
        try:
            time.sleep(0.5) 
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200: break
            
            data = response.json()
            raw_products = []
            try: raw_products = data["data"]["searchInfo"]["storeProductInfos"]
            except: 
                try: raw_products = data["data"]["products"]
                except: pass
            
            if not raw_products: break
            print(f"Kategori: {slug} | Sayfa: {page} | Ürün: {len(raw_products)}")

            for item in raw_products:
                try:
                    name = item.get("name", "")
                    reg_p = item.get("regularPrice", 0) / 100
                    shown_p = item.get("shownPrice", 0) / 100
                    if reg_p == 0: reg_p = shown_p

                    badges = item.get("badges", [])
                    indirim_tipi = kampanya_temizle(badges)

                    indirim_orani = 0
                    durum = "Normal"
                    if reg_p > shown_p:
                        indirim_orani = ((reg_p - shown_p) / reg_p) * 100
                        if indirim_orani > 50: durum = "SÜPER FIRSAT"
                        elif indirim_orani >= 20: durum = "FIRSAT"
                        
                    if "Öde" in indirim_tipi or "Hediye" in indirim_tipi: durum = "ÇOKLU ALIM"

                    images = item.get("images", [])
                    img_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
                    
                    # Link Düzeltme
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
        except: break
    return tum_urunler

def calistir():
    print("Tarama başlıyor...")
    
    spreadsheet = google_sheets_baglan()
    if not spreadsheet:
        print("Sheets bağlanamadı!")
        return

    # 1. HEDEF: ANA VERİTABANI (GEÇMİŞ TUTULAN YER)
    try:
        ana_sheet = spreadsheet.worksheet("Ana_Veritabani")
    except:
        ana_sheet = spreadsheet.add_worksheet(title="Ana_Veritabani", rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        ana_sheet.append_row(basliklar)

    # 2. HEDEF: GÜNLÜK YEDEK SAYFASI (YENİ SEKME)
    gunluk_sheet = None
    try:
        sayfa_ismi = datetime.now().strftime("%d.%m.%Y - %H:%M")
        gunluk_sheet = spreadsheet.add_worksheet(title=sayfa_ismi, rows="1000", cols="20")
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        gunluk_sheet.append_row(basliklar)
        print(f"✅ Yeni yedek sayfası oluşturuldu: {sayfa_ismi}")
    except Exception as e:
        print(f"⚠️ Yedek sayfası oluşturulamadı (İsim çakışması olabilir): {e}")

    # TARAMA VE KAYDETME (Parça Parça)
    toplam_eklenen = 0
    
    for kat in KATEGORILER:
        print(f"--- {kat} taranıyor ---")
        try:
            kategori_verisi = veri_cek(kat)
            
            if kategori_verisi:
                # 1. Ana veritabanına EKLE (Silmeden altına yazar)
                ana_sheet.append_rows(kategori_verisi, value_input_option='RAW')
                
                # 2. Günlük sayfaya EKLE (Varsa)
                if gunluk_sheet:
                    gunluk_sheet.append_rows(kategori_verisi, value_input_option='RAW')
                    
                print(f"✅ {kat}: {len(kategori_verisi)} ürün iki sayfaya da işlendi.")
                toplam_eklenen += len(kategori_verisi)
            else:
                print(f"⚠️ {kat} kategorisinden veri gelmedi.")
                
        except Exception as e:
            print(f"❌ Hata ({kat}): {e}")
            continue
            
    print(f"🎉 İşlem Tamam! Toplam {toplam_eklenen} ürün güvenle kaydedildi.")
