import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os
import json

# --- AYARLAR ---
KATEGORILER = [
    "yag-c-7a",
    "cay-c-6e",
    "seker-c-7be",
    "sut-c-6c",
    "bakliyat-c-79"
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

# --- TÜRKÇE FORMAT DÜZELTİCİ ---
def tr_format(sayi):
    """Sayıyı nokta yerine virgüllü metne çevirir (Google Sheets TR için)"""
    if sayi is None: return "0"
    # Sayıyı 2 basamaklı string yap ve noktayı virgüle çevir
    return f"{float(sayi):.2f}".replace('.', ',')

def veri_cek(slug):
    url = f"https://www.migros.com.tr/rest/search/screens/{slug}?page=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "X-PWA": "true"
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200: return []
        data = response.json()
    except:
        return []
    
    urunler = []
    
    try:
        raw_products = data["data"]["searchInfo"]["storeProductInfos"]
    except:
        try:
            raw_products = data["data"]["products"]
        except:
            return []

    for item in raw_products:
        try:
            name = item.get("name", "")
            regular_price = item.get("regularPrice", 0) / 100
            shown_price = item.get("shownPrice", 0) / 100
            exhausted = item.get("exhausted", False)
            stok = "Yok" if exhausted else "Var"
            
            badges = item.get("badges", [])
            kampanya = ", ".join([b.get("value", "") for b in badges]) if badges else ""

            images = item.get("images", [])
            image_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
            urun_linki = f"https://www.migros.com.tr/{item.get('prettyName', '')}-{item.get('id')}"

            birim_fiyat = 0
            birim_tip = ""
            match = re.search(r"(\d+)\s*(KG|L|Litre|Lt|Gr|Gram|'li|Adet)", name, re.IGNORECASE)
            if match:
                miktar = float(match.group(1))
                birim = match.group(2).lower()
                if "gr" in birim or "gram" in birim:
                    miktar = miktar / 1000
                    birim = "kg"
                if miktar > 0:
                    birim_fiyat = shown_price / miktar
                    birim_tip = f"TL/{birim.upper()}"

            indirim_orani = 0
            durum = "Normal"
            if regular_price > 0:
                indirim_orani = ((regular_price - shown_price) / regular_price) * 100
                if indirim_orani > 80: durum = "OLASI HATA"
                elif indirim_orani >= 30: durum = "FIRSAT"
                elif indirim_orani > 50: durum = "SÜPER FIRSAT"

            # VERİLERİ LİSTEYE EKLERKEN tr_format KULLANIYORUZ
            urunler.append([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                name,
                tr_format(shown_price),   # Fiyatı virgüllü yap
                tr_format(regular_price), # Normal fiyatı virgüllü yap
                tr_format(indirim_orani), # İndirimi virgüllü yap
                durum,
                stok,
                kampanya,
                tr_format(birim_fiyat),   # Birim fiyatı virgüllü yap
                birim_tip,
                image_url,
                urun_linki
            ])
            
        except:
            continue
            
    return urunler

def calistir():
    tum_veriler = []
    for kat in KATEGORILER:
        tum_veriler.extend(veri_cek(kat))
        
    df = pd.DataFrame(tum_veriler, columns=[
        "Tarih", "Ürün Adı", "Fiyat", "Normal Fiyat", "İndirim %", 
        "Durum", "Stok", "Kampanya", "Birim Fiyat", "Birim", "Resim", "Link"
    ])
    
    sheet = google_sheets_baglan()
    if sheet:
        # Eski bozuk verileri temizlemek için mevcut veriyi kontrol et
        # Ama başlıkları silmemeye dikkat etmeliyiz.
        # Bu kod sadece ekleme yapar (append). 
        # Kullanıcı manuel temizlese daha iyi olur.
        sheet.append_rows(df.values.tolist(), value_input_option='USER_ENTERED')
