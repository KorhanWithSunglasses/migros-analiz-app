import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import time

# --- TAKİP EDİLECEK KATEGORİLER ---
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
    # Dosyayı aç
    return client.open("Migros_Takip_DB")

def tr_format(sayi):
    """Sayıları Excel/Sheets formatına (virgüllü) çevirir"""
    if sayi is None: return "0"
    return f"{float(sayi):.2f}".replace('.', ',')

def kampanya_temizle(badges):
    """Anlamsız kampanya yazılarını temizler"""
    temiz = []
    for b in badges:
        val = b.get("value", "")
        if not val: continue
        # Sadece rakam veya TL içerenleri filtrele (Örn: '120 TL' kampanya ismi olamaz)
        if "TL" in val or re.match(r'^[\d.,]+$', val.strip()): continue
        temiz.append(val)
    return ", ".join(temiz) if temiz else ""

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
            time.sleep(0.3) # Migros sunucusunu yormamak için bekleme
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200: break
            
            data = response.json()
            raw_products = []
            
            # Ürün verisi farklı yerlerde olabilir, hepsini dene
            try: raw_products = data["data"]["searchInfo"]["storeProductInfos"]
            except: 
                try: raw_products = data["data"]["products"]
                except: pass
            
            if not raw_products: break
            
            print(f"Kategori: {slug} | Sayfa: {page} | Ürün: {len(raw_products)}")

            for item in raw_products:
                try:
                    name = item.get("name", "")
                    # Fiyatları al (Kuruş cinsinden geliyor, 100'e bölüyoruz)
                    reg_p = item.get("regularPrice", 0) / 100
                    shown_p = item.get("shownPrice", 0) / 100
                    if reg_p == 0: reg_p = shown_p

                    # Kampanya Rozetleri
                    badges = item.get("badges", [])
                    indirim_tipi = kampanya_temizle(badges)

                    # İndirim Oranı Hesapla
                    indirim_orani = 0
                    durum = "Normal"
                    if reg_p > shown_p:
                        indirim_orani = ((reg_p - shown_p) / reg_p) * 100
                        if indirim_orani > 50: durum = "SÜPER FIRSAT"
                        elif indirim_orani >= 20: durum = "FIRSAT"
                        
                    if "Öde" in indirim_tipi or "Hediye" in indirim_tipi: durum = "ÇOKLU ALIM"

                    # Resim ve Link
                    images = item.get("images", [])
                    img_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
                    
                    # --- LİNK DÜZELTME (404 HATASI ÇÖZÜMÜ) ---
                    # Eskiden sonuna ID ekliyorduk, artık sadece prettyName kullanıyoruz.
                    urun_linki = f"https://www.migros.com.tr/{item.get('prettyName', '')}"

                    # Birim (KG, LT, Adet)
                    birim_fiyat = "0"
                    birim = "Adet"
                    match = re.search(r"(\d+)\s*(KG|L|Litre|Lt|Gr|Gram)", name, re.IGNORECASE)
                    if match: birim = match.group(2).upper()

                    tum_urunler.append([
                        datetime.now().strftime("%Y-%m-%d %H:%M"), # Tarih
                        name,
                        tr_format(reg_p),    # Etiket Fiyatı
                        tr_format(shown_p),  # Satış Fiyatı
                        indirim_tipi,
                        tr_format(indirim_orani),
                        durum,
                        "Var",               # Stok
                        tr_format(birim_fiyat),
                        birim,
                        slug,                # Kategori
                        img_url,
                        urun_linki
                    ])
                except: continue
            page += 1
        except: break
    return tum_urunler

def calistir():
    print("Tarama başlıyor...")
    nihai_liste = []
    eklenen_idler = set()
    
    # Tüm kategorileri gez
    for kat in KATEGORILER:
        veriler = veri_cek(kat)
        for v in veriler:
            # Aynı tarama içinde çift ürün olmasın
            if v[1] not in eklenen_idler:
                nihai_liste.append(v)
                eklenen_idler.add(v[1])
    
    if not nihai_liste:
        print("Veri bulunamadı veya siteye erişilemedi!")
        return

    # Google Sheets'e Bağlan
    spreadsheet = google_sheets_baglan()
    if not spreadsheet: return

    # --- 1. ANA VERİTABANINA EKLE (GEÇMİŞ TUTMAK İÇİN) ---
    try:
        try:
            ana_sheet = spreadsheet.worksheet("Ana_Veritabani")
        except:
            # Eğer yoksa oluştur
            ana_sheet = spreadsheet.add_worksheet(title="Ana_Veritabani", rows="1000", cols="20")
            basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
            ana_sheet.append_row(basliklar)
            
        ana_sheet.append_rows(nihai_liste, value_input_option='RAW')
        print("✅ Ana veritabanı güncellendi.")
    except Exception as e:
        print(f"❌ Ana DB Hatası: {e}")

    # --- 2. YENİ GÜNLÜK SAYFA OLUŞTUR (KOLAY TAKİP İÇİN) ---
    try:
        # Sayfa İsmi: "24.12.2025 - 19:30" gibi
        sayfa_ismi = datetime.now().strftime("%d.%m.%Y - %H:%M")
        
        # Çakışma olursa saniye ekle
        try:
            new_sheet = spreadsheet.add_worksheet(title=sayfa_ismi, rows=len(nihai_liste)+20, cols="15")
        except:
            sayfa_ismi = datetime.now().strftime("%d.%m.%Y - %H:%M:%S")
            new_sheet = spreadsheet.add_worksheet(title=sayfa_ismi, rows=len(nihai_liste)+20, cols="15")
        
        # Başlıkları Yaz
        basliklar = ["Tarih", "Ürün Adı", "Etiket Fiyatı", "Satış Fiyatı", "İndirim Tipi", "İndirim %", "Durum", "Stok", "Birim Fiyat", "Birim", "Kategori", "Resim", "Link"]
        new_sheet.append_row(basliklar)
        
        # Verileri Yaz
        new_sheet.append_rows(nihai_liste, value_input_option='RAW')
        print(f"✅ Yeni rapor sayfası oluşturuldu: {sayfa_ismi}")
        
    except Exception as e:
        print(f"❌ Rapor Sayfası Oluşturma Hatası: {e}")

    print(f"🎉 İşlem Tamam! Toplam {len(nihai_liste)} ürün kaydedildi.")
