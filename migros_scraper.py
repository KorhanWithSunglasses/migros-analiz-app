import requests
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import os

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
            # Fiyatları string olarak alıyoruz (nokta ile)
            reg_price_val = item.get("regularPrice", 0) / 100
            shown_price_val = item.get("shownPrice", 0) / 100
            
            # Google Sheets karıştırmasın diye string yapıyoruz
            regular_price = str(reg_price_val)
            shown_price = str(shown_price_val)

            exhausted = item.get("exhausted", False)
            stok = "Yok" if exhausted else "Var"
            
            badges = item.get("badges", [])
            kampanya = ", ".join([b.get("value", "") for b in badges]) if badges else ""

            images = item.get("images", [])
            image_url = images[0]["urls"]["PRODUCT_DETAIL"] if images else ""
            urun_linki = f"https://www.migros.com.tr/{item.get('prettyName', '')}-{item.get('id')}"

            birim_fiyat = "0"
            if "KG" in name or " L" in name: # Basit birim kontrolü
                birim_fiyat = shown_price # Detaylı hesaplama yerine şimdilik fiyatı koyalım

            # İndirim Hesabı
            indirim_orani = 0
            durum = "Normal"
            if reg_price_val > 0:
                indirim_orani = ((reg_price_val - shown_price_val) / reg_price_val) * 100
                if indirim_orani > 80: durum = "OLASI HATA"
                elif indirim_orani >= 25: durum = "FIRSAT"
                elif indirim_orani > 50: durum = "SÜPER FIRSAT"

            urunler.append([
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                name,
                shown_price,      # String olarak gönderiyoruz
                regular_price,    # String olarak gönderiyoruz
                str(indirim_orani), # String olarak gönderiyoruz
                durum,
                stok,
                kampanya,
                birim_fiyat,
                "Adet",
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
        # Verileri string olarak girmeye zorluyoruz (value_input_option='USER_ENTERED' değil RAW kullanabiliriz ama bu daha güvenli)
        data_to_send = df.values.tolist()
        sheet.append_rows(data_to_send, value_input_option='RAW')
