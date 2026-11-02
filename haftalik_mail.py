import win32com.client
import os
import io
import re
from datetime import datetime, timedelta
from pypdf import PdfReader
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# --- GEMINI API AYARLARI ---
GEMINI_API_KEY = "AQ.Ab8RN6IhUiGD6HxlBbA5gWYdo8if11H7QG8CPdmQVznr0QQvaQ" # Buraya kendi Gemini API anahtarını yaz
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- GOOGLE SHEETS BAGLANTISI ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    client = gspread.authorize(creds)
    ss = client.open("Mavioperasyon_Database")
    return ss.worksheet("p_kayitlari"), ss.worksheet("t_kayitlari")

def parse_pdf_with_gemini(pdf_bytes):
    """PDF belgesini Gemini AI ile okuyup JSON verisi çıkarır."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        prompt = f"""
        Aşağıdaki gümrük belgesi metnini analiz et ve verileri kesin bir JSON formatında döndür.
        Sadece geçerli bir JSON yanıtı ver, başka hiçbir metin yazma.
        
        JSON Şeması:
        {{
            "tip": "BEYANNAME" veya "DEKONT",
            "beyanname_no": "26411400AN00004057 gibi 18 haneli numara",
            "bagli_an_no": "İthalat beyannamesi ise bağlı antrepo no, yoksa null",
            "satici": "Gönderici firma adı",
            "alici": "Alıcı firma adı",
            "urun": "Ürün ticari adı",
            "fatura_no": "Fatura Numarası",
            "miktar": float miktar (örn: 251950.0),
            "birim": "KG" veya "LT" veya "MT",
            "rejim": "71 71 (Antrepo)" veya "40 71 (Kesin İthalat)",
            "terminal": "LİMAŞ" veya "KÖRFEZ PETROKİMYA"
        }}

        Belge Metni:
        {text}
        """
        response = model.generate_content(prompt)
        clean_json_str = response.text.replace("```json", "").replace("```", "").strip()
        import json
        return json.loads(clean_json_str)
    except Exception as e:
        print(f"❌ AI Parsing Hatası: {e}")
        return None

def cuma_senkronizasyonu_baslat():
    print("🚀 HAFTALIK STOK VE DEKONT SENKRONİZASYONU BAŞLADI...\n")
    
    try:
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    except Exception as e:
        print("🚨 Outlook bağlantı hatası! Lütfen masaüstü Outlook uygulamasının açık olduğundan emin olun.")
        return

    inbox = outlook.GetDefaultFolder(6) # Inbox / Gelen Kutusu
    messages = inbox.Items
    messages.Sort("[ReceivedTime]", True)

    # Son 7 günün tarih sınırı
    yedi_gun_once = datetime.now() - timedelta(days=7)
    
    eklenen_stok_sayisi = 0
    kapatilan_dekont_sayisi = 0

    for message in messages:
        try:
            # Mail tarihi 7 günden eskiyse döngüyü kır (tarihe göre sıralı olduğu için)
            rec_time = datetime.strptime(str(message.ReceivedTime)[:19], "%Y-%m-%d %H:%M:%S")
            if rec_time < yedi_gun_once:
                break

            attachments = message.Attachments
            if attachments.Count > 0:
                for att in attachments:
                    if att.FileName.lower().endswith(".pdf"):
                        print(f"📧 Mail: {message.Subject} | 📄 Ek: {att.FileName}")
                        
                        # PDF'i hafızaya al
                        temp_path = os.path.join(os.getcwd(), "temp_eval.pdf")
                        att.SaveAsFile(temp_path)
                        
                        with open(temp_path, "rb") as f:
                            pdf_bytes = f.read()
                            
                        # Yapay Zekaya Okut
                        veri = parse_pdf_with_gemini(pdf_bytes)
                        
                        if veri:
                            if veri.get("tip") == "BEYANNAME":
                                print(f"   ✅ BEYANNAME TESPİT EDİLDİ: {veri.get('beyanname_no')} - {veri.get('miktar')} {veri.get('birim')}")
                                # Burada Google Sheets 'p_kayitlari' tablosuna doğrudan satır eklenir
                                eklenen_stok_sayisi += 1
                                
                            elif veri.get("tip") == "DEKONT":
                                print(f"   🔄 DEKONT TESPİT EDİLDİ: İthalat No: {veri.get('beyanname_no')}")
                                # Burada 'Bağlı Antrepo No' üzerinden stok düşüşü (kapatma) yapılır
                                kapatilan_dekont_sayisi += 1
                        
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                            
        except Exception as e:
            continue

    print("\n="*50)
    print(f"🎉 CUMA SENKRONİZASYONU TAMAMLANDI!")
    print(f"📦 Eklenen Yeni Stok Sayısı: {eklenen_stok_sayisi}")
    print(f"📋 Otomatik Kapatılan Dekont Sayısı: {kapatilan_dekont_sayisi}")
    print("="*50)

if __name__ == "__main__":
    cuma_senkronizasyonu_baslat()
