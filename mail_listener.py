import poplib
import email
from email.header import decode_header
import os
import io
import time
import re
from pypdf import PdfReader
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# --- POP3 SUNUCU BİLGİLERİ ---
POP3_SERVER = "mail.mavikimya.net"
POP3_PORT = 110
POP3_USER = "batuhan.kilic@mavikimya.net"
POP3_PASSWORD = "MAIL_SIFRENIZI_BURAYA_YAZIN"  # E-posta şifreni buraya yazmalısın

# --- GEMINI API AYARLARI ---
# Gemini API anahtarını buraya eklemelisin
genai.configure(api_key="GEMINI_API_KEY_BURAYA")
model = genai.GenerativeModel('gemini-1.5-flash')


# --- GOOGLE SHEETS BAGLANTISI ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # service_account.json dosyanın yolunu kontrol et
    creds = Credentials.from_service_account_file("service_account.json", scopes=scope)
    client = gspread.authorize(creds)
    ss = client.open("Mavioperasyon_Database")
    return ss.worksheet("p_kayitlari"), ss.worksheet("t_kayitlari")


def decode_str(header_val):
    if not header_val:
        return ""
    decoded, encoding = decode_header(header_val)[0]
    if isinstance(decoded, bytes):
        return decoded.decode(encoding or "utf-8", errors="ignore")
    return str(decoded)


def parse_pdf_with_gemini(pdf_bytes):
    """PDF içeriğini yapay zeka ile okuyarak yapılandırılmış veri çıkarır."""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"

        prompt = f"""
        Aşağıdaki gümrük belgesi metnini analiz et ve verileri kesin bir JSON formatında döndür.

        Sadece geçerli bir JSON yanıtı ver, başka açıklama yazma.
        JSON Alanları:
        - "tip": ("BEYANNAME" veya "DEKONT")
        - "beyanname_no": (8 hane + 2 harf + 8 hane formatındaki numara, örn: 26411400AN00004057)
        - "bagli_an_no": (İthalat beyannamesi ise bağlı olduğu antrepo numarası, yoksa "")
        - "satici": (Gönderici/Satıcı firma adı)
        - "alici": (İthalatçı/Alıcı firma adı)
        - "urun": (Ticari tanım / Ürün adı)
        - "fatura_no": (Fatura numarası)
        - "miktar": (Sayısal miktar float örn: 251950.0)
        - "birim": ("KG", "LT", veya "MT")
        - "rejim": ("71 71 (Antrepo)" veya "40 71 (Kesin İthalat)")
        - "terminal": ("LİMAŞ" veya "KÖRFEZ PETROKİMYA")

        Belge Metni:
        {text}
        """

        response = model.generate_content(prompt)
        raw_json = response.text.replace("```json", "").replace("```", "").strip()
        import json
        return json.loads(raw_json)
    except Exception as e:
        print(f"AI Parsing Hatası: {e}")
        return None


def check_mailbox_and_process():
    print("📬 Mail sunucusuna bağlanılıyor...")
    try:
        mailbox = poplib.POP3(POP3_SERVER, POP3_PORT)
        mailbox.user(POP3_USER)
        mailbox.pass_(POP3_PASSWORD)

        num_messages = len(mailbox.list()[1])
        print(f"📥 Gelen Kutusu Mesaj Sayısı: {num_messages}")

        # Son gelen maillerden başlayarak kontrol et (Son 10 mail)
        start_idx = max(1, num_messages - 10)

        for i in range(num_messages, start_idx - 1, -1):
            raw_email = b"\r\n".join(mailbox.retr(i)[1])
            msg = email.message_from_bytes(raw_email)
            subject = decode_str(msg.get("Subject"))
            sender = decode_str(msg.get("From"))

            print(f"🔍 İnceleniyor [{i}]: {subject} ({sender})")

            # Mail eklerini tara
            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue

                filename = part.get_filename()
                if filename and filename.lower().endswith('.pdf'):
                    filename = decode_str(filename)
                    print(f"📄 PDF Tespit Edildi: {filename}")
                    pdf_bytes = part.get_payload(decode=True)

                    # Gemini AI ile Analiz Et
                    ai_result = parse_pdf_with_gemini(pdf_bytes)

                    if ai_result:
                        print("✨ AI Analiz Sonucu:", ai_result)
                        # Burada veritabanına otomatik işleme mantığı tetiklenir

        mailbox.quit()
        print("✅ Mail taraması tamamlandı.")

    except Exception as e:
        print(f"❌ Mail Okuma Hatası: {e}")


if __name__ == "__main__":
    # Test çalıştırması
    check_mailbox_and_process()


# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.


def print_hi(name):
    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    print_hi('PyCharm')

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
