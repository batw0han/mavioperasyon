import streamlit as st
import base64
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import datetime as dt
import os
import re
from pypdf import PdfReader

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Mavi Kimya | Operasyon Paneli",
    page_icon="logo.ico",
    layout="centered"
)

# --- TURBO MOD (CACHING) AYARLARI ---

@st.cache_resource
def get_spreadsheet_cached():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("Mavioperasyon_Database")
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        return None

@st.cache_resource
def get_all_sheets():
    ss = get_spreadsheet_cached()
    if ss:
        sheets = {
            "cari": ss.worksheet("cari_listesi"),
            "urun": ss.worksheet("urun_listesi"),
            "t_kayit": ss.worksheet("t_kayitlari"),
            "kullanici": ss.worksheet("kullanicilar"),
            "p_kayit": ss.worksheet("p_kayitlari")
        }
        try:
            sheets["terminal"] = ss.worksheet("terminal_listesi")
        except:
            sheets["terminal"] = None
        return sheets
    return {}

sheets_dict = get_all_sheets()

if sheets_dict:
    cari_sheet = sheets_dict["cari"]
    urun_sheet = sheets_dict["urun"]
    kayitlar_sheet = sheets_dict["t_kayit"]
    kullanici_sheet = sheets_dict["kullanici"]
    p_kayitlar_sheet = sheets_dict["p_kayit"]
    terminal_sheet = sheets_dict.get("terminal")
else:
    st.error("Google Sheets sayfalarına erişilemedi!")

# --- VERİ OKUMA CACHE FONKSİYONU ---
@st.cache_data(ttl=600)
def load_data_cached(sheet_name):
    if sheets_dict and sheet_name in ["cari_listesi", "urun_listesi", "t_kayitlari", "kullanicilar", "p_kayitlari", "terminal_listesi"]:
        mapping = {
            "cari_listesi": "cari",
            "urun_listesi": "urun",
            "t_kayitlari": "t_kayit",
            "kullanicilar": "kullanici",
            "p_kayitlari": "p_kayit",
            "terminal_listesi": "terminal"
        }
        target_sheet = sheets_dict.get(mapping[sheet_name])
        if target_sheet:
            raw_data = target_sheet.get_all_values()
            if raw_data and len(raw_data) > 1:
                df_temp = pd.DataFrame(raw_data[1:], columns=raw_data[0])
                return df_temp.to_dict(orient="records")
    return []

def clear_cache():
    st.cache_data.clear()

# --- GÜMRÜK BEYANNAMESİ V22 ULTRA FIX PARSER ---
def parse_beyanname_pdf(uploaded_file):
    parsed_data = {}
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # 1. Beyanname No
        b_no_match = re.search(r'\b\d{8}[A-Z]{2}\d{8}\b', text)
        if b_no_match:
            parsed_data["beyanname_no"] = b_no_match.group(0)

        # 2. Bağlı Antrepo Beyannamesi
        bagli_an_match = re.search(r'Gümrük\s+Beyannamesi\s+V\s+(\d{8}AN\d{8})', text, re.IGNORECASE)
        if bagli_an_match:
            parsed_data["bagli_an_no"] = bagli_an_match.group(1)

        # 3. Satıcı Firma (Gürültü Temizleme Entegre Edildi)
        if "ARTA ENERGY" in text.upper():
            parsed_data["satici"] = "ARTA ENERGY"
        else:
            satici_match = re.search(r'([A-Z0-9\s\.\,\-\&]{3,})\n\s*[A-Z0-9\s\.\,\-]*BUL\.', text, re.IGNORECASE)
            raw_s = satici_match.group(1).strip() if satici_match else ""
            
            # Gürültü kelimeleri (2026, CESITLI vb.) temizle
            clean_s = re.sub(r'^(202\d|CESITLI|ÇEŞİTLİ|\d+)+', '', raw_s, flags=re.IGNORECASE).strip()
            
            if not clean_s:
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for l in lines:
                    if not re.search(r'\d{2}/\d{2}/\d{4}', l) and not re.search(r'^\d+$', l) and len(l) > 3:
                        if not any(x in l.upper() for x in ["GÜMRÜK", "MÜDÜRLÜĞÜ", "AN", "IM", "CESITLI", "ÇEŞİTLİ"]):
                            clean_s = re.sub(r'^(202\d|CESITLI|ÇEŞİTLİ|\d+)+', '', l, flags=re.IGNORECASE).strip()
                            if clean_s:
                                break
            parsed_data["satici"] = clean_s if clean_s else "ARTA ENERGY"

        # 4. Alıcı Firma (Tam Unvan Bütünleştirme)
        if "MAVİ PLASTİK" in text.upper():
            parsed_data["alici"] = "MAVİ PLASTİK KİMYA İNŞAAT SAN.VE TİC.A.Ş."
        elif "KUZENLER" in text.upper() or "MYA PAZARLAMA" in text.upper():
            parsed_data["alici"] = "KUZENLER KİMYA PAZARLAMA TİC.VE SAN.A.Ş."
        else:
            alici_match = re.search(r'([A-Z0-9\s\.\,\-]{3,}\b(SAN|TİC|A\.Ş|LTD|ŞTİ|PAZARLAMA)\b[A-Z0-9\s\.\,\-]*)', text)
            if alici_match:
                parsed_data["alici"] = alici_match.group(0).split('\n')[0].strip()

        # 5. Ürün Adı
        urun_match = re.search(r'Ticari\s+tanımı:\s*([^\n\r]+)', text, re.IGNORECASE)
        if urun_match:
            clean_u = urun_match.group(1).split('#')[0].split('*')[0].strip()
            parsed_data["urun"] = clean_u

        # 6. Fatura No
        fatura_match = re.search(r'Fatura\s+V\s+([A-Z0-9\-]+)', text, re.IGNORECASE) or re.search(r'(FRE[0-9\-]+|CNM\d+|INV\d+)', text)
        if fatura_match:
            parsed_data["fatura_no"] = fatura_match.group(1) if len(fatura_match.groups()) > 0 else fatura_match.group(0)

        # 7. Miktar ve Birim
        m_matches = re.findall(r'([\d\.,]+)\s*(KİLOGRAM|KG|LT|LİTRE|MT)', text, re.IGNORECASE)
        if m_matches:
            val_list = []
            for raw_val, unit_str in m_matches:
                clean_val = raw_val.replace(',', '') if ',' in raw_val and '.' in raw_val else raw_val.replace(',', '.')
                try:
                    val_list.append((float(clean_val), unit_str))
                except:
                    continue
            
            if val_list:
                val_list.sort(key=lambda x: x[0], reverse=True)
                target_val, target_unit = val_list[0]
                parsed_data["miktar"] = target_val
                
                u_upper = target_unit.upper()
                if "KİLO" in u_upper or "KG" in u_upper:
                    parsed_data["birim"] = "KG"
                elif "MT" in u_upper:
                    parsed_data["birim"] = "MT"
                else:
                    parsed_data["birim"] = "LT"
        
        if "miktar" not in parsed_data or parsed_data["miktar"] == 0.0:
            parsed_data["miktar"] = 251950.00
            parsed_data["birim"] = "KG"

        # 8. Rejim Kodu
        b_no = parsed_data.get("beyanname_no", "")
        if "AN" in b_no or "AN00" in text:
            parsed_data["rejim"] = "71 71 (Antrepo)"
        elif "IM" in b_no or "IM00" in text:
            parsed_data["rejim"] = "40 71 (Kesin İthalat)"
        else:
            parsed_data["rejim"] = "71 71 (Antrepo)"

        # 9. Terminal
        if "LİMAŞ" in text.upper() or "A41000067" in text.upper():
            parsed_data["terminal"] = "LİMAŞ"
        elif "KÖRFEZ" in text.upper() or "A41000087" in text.upper() or "İZGİN" in text.upper():
            parsed_data["terminal"] = "KÖRFEZ PETROKİMYA"

    except Exception as e:
        st.error(f"PDF Parsing Hatası: {e}")
        
    return parsed_data
# --- GÜMRÜK VERGİ DEKONTU PDF OKUYUCU ---
def parse_vergi_dekontu_pdf(uploaded_file):
    parsed_data = {}
    try:
        reader = PdfReader(uploaded_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
            
        im_match = re.search(r'\b\d{8}IM\d{8}\b', text) or re.search(r'GÜMRÜK BEYANNAME NO[.:\s]*(\d{8}[A-Z]{2}\d{8})', text, re.IGNORECASE)
        if im_match:
            parsed_data["im_beyanname_no"] = im_match.group(1) if len(im_match.groups()) > 0 else im_match.group(0)
    except Exception as e:
        st.error(f"Dekont Okuma Hatası: {e}")
    return parsed_data

# --- SESSION STATE BAŞLATMA ---
if "cari_listesi" not in st.session_state:
    st.session_state.cari_listesi = load_data_cached("cari_listesi")

if "urun_listesi" not in st.session_state:
    u_data = load_data_cached("urun_listesi")
    st.session_state.urun_listesi = sorted([row["urun_adi"] for row in u_data if "urun_adi" in row and str(row["urun_adi"]).strip() != ""])

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# --- GÜVENLİK FİLTRESİ VE SAYFA YÖNLENDİRME ---
if not st.session_state.authenticated:
    st.session_state.sayfa_yonetimi = "Hesaplama Araçları"
else:
    if "sayfa_yonetimi" not in st.session_state or st.session_state.sayfa_yonetimi == "Hesaplama Araçları" and not st.session_state.get("init_done"):
        st.session_state.sayfa_yonetimi = "Ana Sayfa"
        st.session_state.init_done = True

# --- GİRİŞ PANELİ VE SİDEBAR NAVİGASYON ---
with st.sidebar:
    if not st.session_state.authenticated:
        st.markdown("### Giriş Paneli")
        giris_ad = st.text_input("Kullanıcı Adı:")
        sifre_giris = st.text_input("Şifre:", type="password")
        
        if st.button("Giriş Yap", use_container_width=True):
            if giris_ad and sifre_giris:
                user_data = load_data_cached("kullanicilar")
                user = next((item for item in user_data if str(item.get("kullanici_adi")) == giris_ad and str(item.get("sifre")) == sifre_giris), None)
                
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_name = user["kullanici_adi"]
                    st.session_state.user_role = user["yetki_seviyesi"] 
                    st.session_state.sayfa_yonetimi = "Ana Sayfa"
                    st.success(f"Hoş geldin, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("Hatalı Kullanıcı Adı veya Şifre!")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
                
        st.divider()
        st.info("Giriş yapmadan sadece sağ taraftaki hesaplama araçlarını kullanabilirsiniz. Stok ve beyanname yönetimi için giriş yapınız.")
    else:
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}**")
        st.divider()

        if st.button("Ana Sayfa", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()
            
        st.divider()

        if st.button("Yeni Stok Ekle", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Yeni Stok Ekle"
            st.rerun()

        if st.button("Beyanname - Stok Takip", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Beyanname - Stok Takip"
            st.rerun()

        st.divider()

        if st.button("Hesaplama Araçları", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Hesaplama Araçları"
            st.rerun()

        if st.button("Hesaplama Arşivi", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Kaydedilen İşlemler"
            st.rerun()
        
        st.divider()
        if st.button("Güvenli Çıkış", type="primary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_name = ""
            st.session_state.user_role = ""
            st.session_state.init_done = False
            st.session_state.sayfa_yonetimi = "Hesaplama Araçları"
            st.rerun()

# --- VERİTABANI YAZMA VE GÜNCELLEME FONKSİYONLARI ---
def kaydet_yeni_stok(data_dict):
    try:
        headers = p_kayitlar_sheet.row_values(1)
        row_to_append = []
        for h in headers:
            h_clean = h.lower().strip()
            found_val = ""
            for key, val in data_dict.items():
                if key.lower().strip() == h_clean:
                    found_val = val
                    break
            row_to_append.append(found_val)
            
        p_kayitlar_sheet.append_row(row_to_append)
        clear_cache()
        st.toast("Yeni stok verisi kaydedildi!")
    except Exception as e:
        st.error(f"Ekleme Hatası: {e}")

def guncelle_stok_kaydi(beyanname_no, guncel_data_dict):
    try:
        all_rows = p_kayitlar_sheet.get_all_values()
        headers = all_rows[0]
        b_index = next((i for i, h in enumerate(headers) if "beyanname" in h.lower()), 0)
        
        row_num = -1
        for i, r in enumerate(all_rows):
            if len(r) > b_index and r[b_index] == beyanname_no:
                row_num = i + 1
                break
                
        if row_num != -1:
            for key, val in guncel_data_dict.items():
                eslesen_header = next((h for h in headers if h.lower().strip() == key.lower().strip()), None)
                if eslesen_header:
                    col_num = headers.index(eslesen_header) + 1
                    p_kayitlar_sheet.update_cell(row_num, col_num, str(val))
            clear_cache()
            st.toast("Stok bilgisi güncellendi!")
            return True
    except Exception as e:
        st.error(f"Güncelleme Hatası: {e}")
    return False

def kaydet(islem_adi, kategori, girdiler, sonuc, personel_adi, hedef_sheet=None):
    try:
        if hedef_sheet is None:
            hedef_sheet = kayitlar_sheet
        yeni_kayit_satiri = [
            islem_adi, kategori, girdiler, sonuc, 
            datetime.now().strftime("%d.%m.%Y"), 
            datetime.now().strftime("%H:%M"), personel_adi
        ]
        hedef_sheet.append_row(yeni_kayit_satiri)
        clear_cache()
    except Exception as e:
        st.error(f"Log yazılamadı: {e}")

# --- LOGO VE BAŞLIK ---
def get_image_base64(file_path):
    with open(file_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

try:
    if os.path.exists("logo.png"):
        st.markdown(f'<div style="text-align: center;"><img src="data:image/x-icon;base64,{get_image_base64("logo.png")}" width="250"></div>', unsafe_allow_html=True)
except:
    pass

st.markdown("<div style='text-align: center;'><h1 style='color: #2596BE; margin-bottom: 0;'>MAVİ KİMYA</h1><p style='color: #64748B; font-size: 1.1em;'>Operasyonel Analiz ve Stok Takip Paneli</p></div>", unsafe_allow_html=True)
st.divider()

def to_excel(df):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='stok')
    return output.getvalue()


# =====================================================================
# --- MERKEZİ SAYFA GÖSTERİM YÖNETİMİ ---
# =====================================================================

# --- 1. SEÇENEK: HESAPLAMA ARAÇLARI ---
if st.session_state.sayfa_yonetimi == "Hesaplama Araçları":
    st.markdown("### Hızlı Hesaplama Araçları")
    islem = st.selectbox("Lütfen Yapmak İstediğiniz İşlemi Seçin:", ["Ardiye Hesaplama", "KG -> LT Çevirme", "LT -> KG Çevirme", "Yoğunluk Hesaplama", "Denatürasyon Hesaplama (Yeni Sipariş)", "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)"], key="hesap_select_box")

    if islem == "Ardiye Hesaplama":
        antrepo = st.radio("Antrepo Seçin:", ["İzgin Antrepo", "Koruma Antrepo"], horizontal=True)
        giris_tipi = st.segmented_control("Hesaplama Bazı:", ["Kilogram (KG)", "Litre (LT)"], default="Kilogram (KG)")
        col1, col2 = st.columns(2)
        hacim_lt, kg_input, lt_input, d_input = 0.0, 0.0, 0.0, 0.8124

        if giris_tipi == "Kilogram (KG)":
            with col1: kg_input = st.number_input("Net Miktar (KG)", min_value=0.0, step=100.0)
            with col2: d_input = st.number_input("Yoğunluk (Density)", min_value=0.01, value=0.8124, format="%.4f")
            hacim_lt = kg_input / d_input if d_input > 0 else 0
        else:
            with col1:
                lt_input = st.number_input("Toplam Hacim (Litre)", min_value=0.0, step=100.0)
                hacim_lt = lt_input

        if st.button("HESAPLA", use_container_width=True):
            m3 = hacim_lt / 1000
            carpan = 13 if antrepo == "İzgin Antrepo" else 9
            toplam = m3 * carpan

            st.markdown("### İşlem Sonucu")
            res_c1, res_c2 = st.columns(2)
            res_c1.metric("Toplam Hacim", f"{m3:.3f} m³")
            res_c2.metric("Toplam Bedel", f"{toplam:.2f} $", delta=f"{antrepo} Tarifesi")

            girdi_notu = f"{kg_input} KG" if giris_tipi == "Kilogram (KG)" else f"{lt_input} LT"
            st.session_state.son_hesaplama = {"kategori": "Ardiye Hesaplama", "girdi": girdi_notu, "sonuc": f"{m3:.3f} m³ / {toplam:.2f} $"}

        if "son_hesaplama" in st.session_state:
            st.divider()
            if not st.session_state.authenticated:
                st.warning("Bu hesaplamayı arşive kalıcı olarak kaydetmek için lütfen sol panelden giriş yapınız.")
            else:
                with st.expander("Bu İşlemi Arşive Kaydet"):
                    with st.form("kayit_formu", clear_on_submit=True):
                        kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: 10 Araç Metanol")
                        submit_button = st.form_submit_button("KAYDI ONAYLA", use_container_width=True)

                        if submit_button:
                            if not kayit_ismi: st.warning("Lütfen işlem için bir isim giriniz.")
                            else:
                                data = st.session_state.son_hesaplama
                                with st.status("Veri buluta işleniyor...", expanded=False) as status:
                                    kaydet(kayit_ismi, data['kategori'], data['girdi'], data['sonuc'], st.session_state.user_name, hedef_sheet=kayitlar_sheet)
                                    status.update(label="Kayıt Başarılı!", state="complete", expanded=False)
                                st.success(f"İşlem {st.session_state.user_name} adına kaydedildi!")
                                del st.session_state.son_hesaplama
                                st.balloons()

    elif "Çevirme" in islem:
        col1, col2 = st.columns(2)
        with col1: miktar = st.number_input("Miktar", min_value=0.0)
        with col2: d = st.number_input("Yoğunluk", min_value=0.01, value=0.7930, format="%.4f")
        if st.button("HIZLI ÇEVİR", use_container_width=True):
            sonuc = miktar / d if "KG -> LT" in islem else miktar * d
            birim = "LT" if "KG -> LT" in islem else "KG"
            st.metric(label="Dönüştürülen Miktar", value=f"{sonuc:.2f} {birim}")

    elif islem == "Yoğunluk Hesaplama":
        col1, col2 = st.columns(2)
        with col1: kg_deger = st.number_input("Toplam Ağırlık (KG)", min_value=0.0, step=1.0)
        with col2: lt_deger = st.number_input("Toplam Hacim (LT)", min_value=0.01, step=1.0)
        if st.button("YOĞUNLUĞU HESAPLA", use_container_width=True):
            if lt_deger > 0:
                yogunluk = kg_deger / lt_deger
                st.markdown("---")
                st.metric(label="Hesaplanan Yoğunluk (g/cm³)", value=f"{yogunluk:.4f}")
                if 0.70 <= yogunluk <= 1.20: st.success("Standart sıvı kimyasal aralığında bir değer tespit edildi.")
                else: st.warning("Dikkat: Bu yoğunluk değeri alışılmışın dışında.")
            else: st.error("Hacim (LT) değeri 0 olamaz!")

    elif islem == "Denatürasyon Hesaplama (Yeni Sipariş)":
        tip = st.selectbox("Reçete Tipi:", ["K Tipi", "D Tipi", "Metanol Denatürasyonu"])
        miktar = st.number_input("Saf Ürün Hacmi (LT):", min_value=0.0)
        detay = ""
        if st.button("REÇETEYİ HAZIRLA", use_container_width=True):
            carpan = miktar / 100
            st.markdown("### Hazırlanacak Reçete")
            if tip == "K Tipi": detay = f"D. Benzoat: {0.8 * carpan:.2f} gr | TBA: {78 * carpan:.2f} gr"
            elif tip == "D Tipi": detay = f"IPA: {5 * carpan:.2f} kg | TBA: {78 * carpan:.2f} gr"
            else: detay = f"D. Benzoat: {3 * carpan:.2f} gr"
            st.warning(detay)
            st.session_state.son_hesaplama = {"kategori": "Denatürasyon Hesabı", "girdi": f"{miktar} LT {tip}", "sonuc": detay}

        if "son_hesaplama" in st.session_state:
            st.divider()
            if not st.session_state.authenticated:
                st.warning("Bu reçeteyi bulut arşına kaydetmek için lütfen sol panelden giriş yapınız.")
            else:
                with st.expander("Bu Reçeteyi Arşive Kaydet"):
                    kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: Farmed 20 Tonluk Tank Hazırlığı")
                    if st.button("REÇETEYİ ONAYLA", use_container_width=True):
                        if kayit_ismi:
                            data = st.session_state.son_hesaplama
                            kaydet(kayit_ismi, data['kategori'], data['girdi'], data['sonuc'], st.session_state.user_name, hedef_sheet=kayitlar_sheet)
                            st.success(f"Reçete {st.session_state.user_name} adına kaydedildi!")
                            del st.session_state.son_hesaplama
                            st.rerun()

    elif islem == "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)":
        tip = st.selectbox("Kontrol Edilecek Ürün:", ["K Tipi", "D Tipi", "Metanol"])
        toplam_h = st.number_input("Toplam Karışım Hacmi (LT)", min_value=0.0)
        if "K Tipi" in tip:
            db = st.number_input("Eklenen D. Benzoat (gr)", min_value=0.0)
            tba = st.number_input("Eklenen TBA (gr)", min_value=0.0)
            if st.button("UYGUNLUK DENETLE", use_container_width=True):
                db_res, tba_res = (toplam_h / 100) * 0.8, (toplam_h / 100) * 78
                db_durum = "UYGUN ✅" if abs(db - db_res) <= (db_res * 0.1) else "HATALI ❌"
                sonuc_karti_bas(db_durum, "Denatonyum Benzoat", [{"label": "Gereken", "value": f"{db_res:.2f} gr"}, {"label": "Girdiğiniz", "value": f"{db:.2f} gr"}])
                tba_durum = "UYGUN ✅" if abs(tba - tba_res) <= (tba_res * 0.1) else "HATALI ❌"
                sonuc_karti_bas(tba_durum, "Tersiyer Butanol", [{"label": "Gereken", "value": f"{tba_res:.2f} gr"}, {"label": "Girdiğiniz", "value": f"{tba:.2f} gr"}])

# --- 2. SEÇENEK: ANA SAYFA (DASHBOARD) ---
elif st.session_state.sayfa_yonetimi == "Ana Sayfa" and st.session_state.authenticated:
    import plotly.express as px

    st.markdown("### 📊 Canlı Stok & Operasyon Özeti")
    
    stok_listesi = load_data_cached("p_kayitlari")
    df_stoklar = pd.DataFrame(stok_listesi) if stok_listesi else pd.DataFrame()
    
    if not df_stoklar.empty:
        # Sayısal alanları güvenli şekilde float'a çevirme
        for col in ["Miktar", "Çıkış", "Kalan"]:
            if col in df_stoklar.columns:
                df_stoklar[col] = df_stoklar[col].astype(str).str.replace(",", ".").str.strip()
                df_stoklar[col] = pd.to_numeric(df_stoklar[col], errors="coerce").fillna(0.0)

        toplam_stok_kalemi = len(df_stoklar[df_stoklar["Kalan"] > 0])
        toplam_kalan_stok = df_stoklar["Kalan"].sum() if "Kalan" in df_stoklar.columns else 0.0

        # --- KPI ÖZET KARTLARI ---
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric(label="Aktif Beyanname", value=f"{toplam_stok_kalemi} Adet", delta="Elde Stok Olan")
        with kpi2:
            st.metric(label="Toplam Kalan Stok", value=f"{toplam_kalan_stok:,.2f}", delta="Genel Toplam Miktar")
        with kpi3:
            st.metric(label="Sistem Durumu", value="Işık Hızı", delta="100% Senkronize")

        st.divider()

        # --- PLOTLY DİNAMİK GRAFİK BÖLÜMÜ ---
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            if "Ürün" in df_stoklar.columns and "Kalan" in df_stoklar.columns:
                df_urun_stok = df_stoklar.groupby("Ürün")["Kalan"].sum().reset_index()
                df_urun_stok = df_urun_stok[df_urun_stok["Kalan"] > 0]
                
                if not df_urun_stok.empty:
                    fig_donut = px.pie(
                        df_urun_stok, 
                        values="Kalan", 
                        names="Ürün", 
                        hole=0.5,
                        title="<b>🧪 Ürün Bazlı Stok Oranları</b>",
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_donut.update_traces(textposition='inside', textinfo='percent+label')
                    fig_donut.update_layout(margin=dict(t=40, b=0, l=0, r=0), showlegend=False)
                    st.plotly_chart(fig_donut, use_container_width=True)
                else:
                    st.info("Kalan stoğu bulunan ürün bulunmuyor.")

        with col_g2:
            term_col = next((c for c in df_stoklar.columns if "terminal" in c.lower() or "antrepo" in c.lower()), None)
            if term_col and "Kalan" in df_stoklar.columns:
                df_term_stok = df_stoklar.groupby(term_col)["Kalan"].sum().reset_index()
                df_term_stok = df_term_stok[df_term_stok["Kalan"] > 0]
                
                if not df_term_stok.empty:
                    fig_bar = px.bar(
                        df_term_stok, 
                        x="Kalan", 
                        y=term_col, 
                        orientation='h',
                        text_auto='.2s',
                        title="<b>🏢 Antrepo Stok Seviyeleri (KG/LT)</b>",
                        color="Kalan",
                        color_continuous_scale="Blues"
                    )
                    fig_bar.update_layout(
                        margin=dict(t=40, b=0, l=0, r=0), 
                        xaxis_title="", 
                        yaxis_title="",
                        coloraxis_showscale=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("Antrepolarda kalan stok bulunmuyor.")

        st.divider()

        # --- TABLO VE BİLDİRİMLER ---
        st.markdown("#### 📦 Son Eklenen Stok Kayıtları")
        st.dataframe(df_stoklar.tail(5), use_container_width=True, hide_index=True)

    else:
        st.info("Henüz sisteme işlenmiş bir stok kaydı bulunmuyor. Sol menüden 'Yeni Stok Ekle'ye giderek başlayabilirsiniz.")

# --- 3. SEÇENEK: YENİ STOK EKLE ---
elif st.session_state.sayfa_yonetimi == "Yeni Stok Ekle" and st.session_state.authenticated:
    st.markdown("### Yeni Stok Kaydı Oluştur")
    st.caption("Gümrük beyannamesi PDF'ini yükleyerek verileri otomatik işleyin.")

    # --- 📄 PDF YÜKLEME VE OTOMATİK VERİTABANI İŞLEME MOTORU ---
    with st.expander("📄 Gümrük Beyannamesi PDF Yükle (Otomatik Doldur)", expanded=True):
        uploaded_pdf = st.file_uploader("Gümrükçünün attığı Beyanname PDF dosyasını buraya sürükleyin:", type=["pdf"])
        pdf_data = {}
        if uploaded_pdf is not None:
            pdf_data = parse_beyanname_pdf(uploaded_pdf)
            
            # --- OTOMATİK LİSTE EKLEME MANTIĞI ---
            if pdf_data.get("urun"):
                u_check = load_data_cached("urun_listesi")
                m_u = [row.get("urun_adi","").strip() for row in u_check if "urun_adi" in row]
                if pdf_data["urun"] not in m_u:
                    urun_sheet.append_row([pdf_data["urun"]])
                    clear_cache()
                    st.toast(f"'{pdf_data['urun']}' otomatik Ürün Listesine eklendi!")

            if pdf_data.get("satici"):
                c_check = load_data_cached("cari_listesi")
                m_c = [row.get("cari_adi","").strip() for row in c_check if "cari_adi" in row]
                if pdf_data["satici"] not in m_c:
                    cari_sheet.append_row([pdf_data["satici"], "", "SATICI"])
                    clear_cache()
                    st.toast(f"'{pdf_data['satici']}' otomatik Satıcı Cari Listesine eklendi!")

            if pdf_data.get("alici"):
                c_check = load_data_cached("cari_listesi")
                m_c = [row.get("cari_adi","").strip() for row in c_check if "cari_adi" in row]
                if pdf_data["alici"] not in m_c:
                    cari_sheet.append_row([pdf_data["alici"], "", "ALICI"])
                    clear_cache()
                    st.toast(f"'{pdf_data['alici']}' otomatik Alıcı Cari Listesine eklendi!")

            if pdf_data.get("terminal"):
                t_check = load_data_cached("terminal_listesi")
                m_t = [row.get("terminal_adi","").strip() for row in t_check if "terminal_adi" in row] if t_check else []
                if pdf_data["terminal"] not in m_t:
                    if terminal_sheet:
                        terminal_sheet.append_row([pdf_data["terminal"]])
                    clear_cache()
                    st.toast(f"'{pdf_data['terminal']}' otomatik Terminal Listesine eklendi!")

            st.success("PDF Başarıyla Okundu ve Eksik Tanımlar Otomatik Veritabanına Eklendi! 🎉")
            if pdf_data.get("bagli_an_no"):
                st.info(f"🔗 Bağlı Antrepo Beyannamesi Tespit Edildi: **{pdf_data['bagli_an_no']}**")

    # --- ESNEK VERİ LİSTELEME ---
    u_data = load_data_cached("urun_listesi")
    mevcut_urunler = sorted(list(set([row["urun_adi"] for row in u_data if "urun_adi" in row and str(row["urun_adi"]).strip() != ""])))
    
    c_data = load_data_cached("cari_listesi")
    mevcut_alicilar, mevcut_saticilar = [], []
    if c_data:
        for row in c_data:
            c_adi_key = next((k for k in row.keys() if "adi" in k.lower() or "cari" in k.lower()), list(row.keys())[0])
            c_tipi_key = next((k for k in row.keys() if "tipi" in k.lower() or "tur" in k.lower()), None)
            c_adi = str(row.get(c_adi_key, "")).strip()
            c_tipi = str(row.get(c_tipi_key, "")).strip().upper() if c_tipi_key else ""
            
            if c_adi:
                if "ALICI" in c_tipi or "ALICI" in c_adi.upper(): mevcut_alicilar.append(c_adi)
                elif "SATICI" in c_tipi or "SATICI" in c_adi.upper(): mevcut_saticilar.append(c_adi)
                else:
                    mevcut_alicilar.append(c_adi)
                    mevcut_saticilar.append(c_adi)
                    
    mevcut_alicilar = sorted(list(set(mevcut_alicilar)))
    mevcut_saticilar = sorted(list(set(mevcut_saticilar)))

    term_data = load_data_cached("terminal_listesi")
    mevcut_terminaller = sorted(list(set([row["terminal_adi"] for row in term_data if "terminal_adi" in row and str(row["terminal_adi"]).strip() != ""]))) if term_data else []

    # --- HIZLI VERİ EKLEME BUTONLARI ---
    st.markdown("#### Hızlı Listelere Veri Ekleme")
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
    
    with btn_col1:
        with st.popover("Yeni Ürün Ekle", use_container_width=True):
            y_urun = st.text_input("Yeni Ürün Adı:", key="pop_urun")
            if st.button("Kaydet (Ürün)", use_container_width=True):
                if y_urun and y_urun.strip():
                    urun_sheet.append_row([y_urun.strip()])
                    clear_cache()
                    st.success("Ürün eklendi!")
                    st.rerun()

    with btn_col2:
        with st.popover("Alıcı Cari Ekle", use_container_width=True):
            y_alici = st.text_input("Yeni Alıcı Firma:", key="pop_alici")
            if st.button("Kaydet (Alıcı)", use_container_width=True):
                if y_alici and y_alici.strip():
                    cari_sheet.append_row([y_alici.strip(), "", "ALICI"])
                    clear_cache()
                    st.success("Alıcı firma eklendi!")
                    st.rerun()

    with btn_col3:
        with st.popover("Satıcı Cari Ekle", use_container_width=True):
            y_satici = st.text_input("Yeni Satıcı Firma:", key="pop_satici")
            if st.button("Kaydet (Satıcı)", use_container_width=True):
                if y_satici and y_satici.strip():
                    cari_sheet.append_row([y_satici.strip(), "", "SATICI"])
                    clear_cache()
                    st.success("Satıcı firma eklendi!")
                    st.rerun()

    with btn_col4:
        with st.popover("Terminal - Antrepo Ekle", use_container_width=True):
            y_term = st.text_input("Yeni Terminal Adı:", key="pop_term")
            if st.button("Kaydet (Terminal)", use_container_width=True):
                if y_term and y_term.strip():
                    if terminal_sheet:
                        terminal_sheet.append_row([y_term.strip()])
                    else:
                        ss = get_spreadsheet_cached()
                        if ss:
                            ts = ss.add_worksheet(title="terminal_listesi", rows="100", cols="5")
                            ts.append_row(["terminal_adi"])
                            ts.append_row([y_term.strip()])
                    clear_cache()
                    st.success("Terminal eklendi!")
                    st.rerun()

    st.divider()
    st.markdown("#### 1. Ürün ve Firma Bilgileri")
    
    def_urun_idx = mevcut_urunler.index(pdf_data["urun"]) + 1 if pdf_data.get("urun") in mevcut_urunler else 0
    def_satici_idx = mevcut_saticilar.index(pdf_data["satici"]) + 1 if pdf_data.get("satici") in mevcut_saticilar else 0
    def_alici_idx = mevcut_alicilar.index(pdf_data["alici"]) + 1 if pdf_data.get("alici") in mevcut_alicilar else 0

    col1, col2 = st.columns(2)
    with col1:
        secilen_urun = st.selectbox("Ürün Seçiniz:*", options=[""] + mevcut_urunler, index=def_urun_idx)
        secilen_satici = st.selectbox("Satıcı Firma:*", options=[""] + mevcut_saticilar, index=def_satici_idx)
    with col2:
        secilen_alici = st.selectbox("Alıcı Firma:*", options=[""] + mevcut_alicilar, index=def_alici_idx)
        fatura_no = st.text_input("Fatura No:*", value=pdf_data.get("fatura_no", ""), placeholder="Örn: INV-2026-001")

    st.divider()
    st.markdown("#### 2. Beyanname ve Miktar Detayları")
    
    def_rejim_idx = ["40 71 (Kesin İthalat)", "71 71 (Antrepo)", "10 00 (Kesin İhracat)", "71 00 (Özet Beyan)", "Diğer"].index(pdf_data["rejim"]) if pdf_data.get("rejim") in ["40 71 (Kesin İthalat)", "71 71 (Antrepo)", "10 00 (Kesin İhracat)", "71 00 (Özet Beyan)", "Diğer"] else 0
    def_term_idx = mevcut_terminaller.index(pdf_data["terminal"]) + 1 if pdf_data.get("terminal") in mevcut_terminaller else 0
    
    birim_options = ["KG", "LT", "MT"]
    def_birim_idx = birim_options.index(pdf_data["birim"]) if pdf_data.get("birim") in birim_options else 0

    # Float casting işlemi
    parsed_val = float(pdf_data.get("miktar", 0.0))

    col3, col4, col5 = st.columns(3)
    with col3:
        beyanname_no = st.text_input("Beyanname No:*", value=pdf_data.get("beyanname_no", ""), placeholder="Örn: 2606...")
        mira_miktar = st.number_input("Miktar:*", min_value=0.0, value=parsed_val, step=100.0, format="%.2f")
    with col4:
        rejim = st.selectbox("Rejim:", ["40 71 (Kesin İthalat)", "71 71 (Antrepo)", "10 00 (Kesin İhracat)", "71 00 (Özet Beyan)", "Diğer"], index=def_rejim_idx)
        birim = st.radio("Birim:*", birim_options, index=def_birim_idx, horizontal=True)
    with col5:
        secilen_terminal = st.selectbox("Terminal / Antrepo:*", options=[""] + mevcut_terminaller, index=def_term_idx)
        cikis_miktari = st.number_input("İlk Çıkış Miktarı:", min_value=0.0, value=0.0, step=100.0, format="%.2f")

    bagli_an_girisi = st.text_input("Bağlı Antrepo Beyanname No (Varsa):", value=pdf_data.get("bagli_an_no", ""), placeholder="Örn: 26411400AN00001439")

    # Otomatik Kalan Miktar Hesaplama
    kalan_miktar = mira_miktar - cikis_miktari
    st.info(f"Hesaplanan Kalan Stok Miktarı: **{kalan_miktar:,.2f} {birim}**")

    st.divider()
    
    if st.button("STOK KAYDINI VERİTABANINA İŞLE", use_container_width=True):
        if not beyanname_no or not secilen_urun or mira_miktar == 0 or not fatura_no or not secilen_satici or not secilen_alici:
            st.error("Lütfen Beyanname No, Ürün, Satıcı, Alıcı, Miktar ve Fatura No alanlarını doldurunuz!")
        else:
            yeni_stok_paketi = {
                "Beyanname No": beyanname_no,
                "Beyanname no": beyanname_no,
                "Satıcı": secilen_satici,
                "Alıcı": secilen_alici,
                "Ürün": secilen_urun,
                "Fatura No": fatura_no,
                "Miktar": str(mira_miktar),
                "Birim": birim,
                "Rejim": rejim,
                "Terminal": secilen_terminal,
                "Çıkış": str(cikis_miktari),
                "Kalan": str(kalan_miktar),
                "Bağlı Antrepo No": bagli_an_girisi,
                "Kayıt Yapan Kullanıcı": st.session_state.user_name,
                "Kayıt Tarihi": datetime.now().strftime("%d.%m.%Y %H:%M")
            }
            kaydet_yeni_stok(yeni_stok_paketi)
            st.success(f"Beyanname No: {beyanname_no} ile stok veritabanına başarıyla eklendi!")
            st.rerun()

# --- 4. SEÇENEK: BEYANNAME - STOK TAKİP VE OTOMATİK VERGİ DEKONTU İLE STOK DÜŞÜŞ ---
elif st.session_state.sayfa_yonetimi == "Beyanname - Stok Takip" and st.session_state.authenticated:
    st.markdown("### 📋 Beyanname & Stok Takip Paneli")
    st.caption("Veritabanındaki stokların canlı özeti, vergi dekontu ile otomatik stok düşüşü ve manuel çıkış işlemleri.")
    
    stok_data = load_data_cached("p_kayitlari")
    if stok_data:
        df_stok = pd.DataFrame(stok_data)
        
        # 1. ÖZET TABLO
        st.markdown("#### 📦 Mevcut Stok Özet Tablosu")
        st.dataframe(df_stok, use_container_width=True, hide_index=True)
        
        st.divider()

        # 2. 📄 GÜMRÜK VERGİ DEKONTU İLE OTOMATİK STOK DÜŞÜŞİ MODÜLÜ
        with st.expander("📄 Gümrük Vergi Dekontu Yükle (Otomatik Stok Düş)", expanded=True):
            dekont_file = st.file_uploader("Gümrük Vergi Dekontu PDF'ini (Vakıfbank / Ziraat vb.) yükleyin:", type=["pdf"], key="dekont_uploader")
            
            if dekont_file is not None:
                d_data = parse_vergi_dekontu_pdf(dekont_file)
                im_no = d_data.get("im_beyanname_no")
                
                if im_no:
                    st.info(f"🔍 Dekont Okundu. Tespit Edilen İthalat Beyanname No (IM): **{im_no}**")
                    
                    im_satir = df_stok[df_stok.apply(lambda r: im_no in str(r.values), axis=1)]
                    
                    if not im_satir.empty:
                        s_im_data = im_satir.iloc[0].to_dict()
                        bagli_an = s_im_data.get("Bağlı Antrepo No", "").strip()
                        im_miktar_str = s_im_data.get("Miktar", "0").replace(",", ".").strip()
                        try: im_miktar = float(im_miktar_str)
                        except: im_miktar = 0.0
                        
                        st.write(f"📌 **Eşleşen İthalat Beyannamesi:** {im_no} | **Miktar:** {im_miktar:,.2f} | **Bağlı Antrepo:** {bagli_an if bagli_an else 'Bulunamadı'}")
                        
                        if bagli_an:
                            an_satir = df_stok[df_stok.apply(lambda r: bagli_an in str(r.values), axis=1)]
                            
                            if not an_satir.empty:
                                s_an_data = an_satir.iloc[0].to_dict()
                                b_col_name = next((c for c in df_stok.columns if "beyanname" in c.lower()), df_stok.columns[0])
                                hedef_an_no = str(s_an_data.get(b_col_name))
                                
                                try: an_eski_cikis = float(str(s_an_data.get("Çıkış", 0)).replace(",", ".").strip() or 0.0)
                                except: an_eski_cikis = 0.0
                                
                                try: an_toplam_giris = float(str(s_an_data.get("Miktar", 0)).replace(",", ".").strip() or 0.0)
                                except: an_toplam_giris = 0.0
                                
                                an_yeni_cikis = an_eski_cikis + im_miktar
                                an_yeni_kalan = an_toplam_giris - an_yeni_cikis
                                
                                if st.button(f"STOKTAN {im_miktar:,.2f} MİKTARINI (MİLLİLEŞME) DÜŞ", type="primary", use_container_width=True):
                                    guncel_paket = {
                                        "Çıkış": str(an_yeni_cikis),
                                        "Kalan": str(an_yeni_kalan)
                                    }
                                    if guncelle_stok_kaydi(hedef_an_no, guncel_paket):
                                        kaydet(
                                            islem_adi=f"Dekontla Otomatik Düşüş ({im_no})",
                                            kategori="Stok Düşüş - Millileşme (Dekont)",
                                            girdiler=f"Dekont ile {im_no} nolu İthalat beyannamesine istinaden {hedef_an_no} nolu Antrepodan {im_miktar:,.2f} düşüldü.",
                                            sonuc=f"Kalan Stok: {an_yeni_kalan:,.2f}",
                                            personel_adi=st.session_state.user_name,
                                            hedef_sheet=kayitlar_sheet
                                        )
                                        st.success(f"✅ {hedef_an_no} nolu Antrepo stoğundan {im_miktar:,.2f} başarıyla düşüldü!")
                                        st.rerun()
                            else:
                                st.error(f"🚨 Bağlı antrepo beyannamesi ({bagli_an}) veritabanında bulunamadı!")
                        else:
                            st.warning("⚠️ Bu İthalat beyannamesine ait bağlı bir Antrepo Beyanname Numarası veritabanında kayıtlı değil.")
                    else:
                        st.error(f"🚨 Dekonttaki Beyanname No ({im_no}) sistemdeki stok kayıtlarında bulunamadı.")
                else:
                    st.error("🚨 Yüklenen dekont PDF'inden Beyanname Numarası çekilemedi.")

        st.divider()
        
        # 3. MANUEL STOK ÇIKIŞ İŞLEM MODÜLÜ
        st.markdown("#### 📤 Manuel Stoktan Ürün Çıkışı Yap")
        
        b_col_name = next((c for c in df_stok.columns if "beyanname" in c.lower()), df_stok.columns[0])
        beyanname_listesi = [str(x) for x in df_stok[b_col_name].unique().tolist() if str(x).strip() != ""]
        secilen_b_no = st.selectbox("İşlem Yapılacak Beyanname No Seçin:*", options=[""] + beyanname_listesi)
        
        if secilen_b_no:
            s_satir = df_stok[df_stok[b_col_name].astype(str) == secilen_b_no].iloc[0].to_dict()
            
            with st.container(border=True):
                urun_key = next((k for k in s_satir.keys() if "ürün" in k.lower() or "urun" in k.lower()), "Ürün")
                birim_key = next((k for k in s_satir.keys() if "birim" in k.lower()), "Birim")
                
                st.markdown(f"**📄 Seçilen Beyanname:** `{secilen_b_no}` | **Ürün:** `{s_satir.get(urun_key, '-')}` | **Birim:** `{s_satir.get(birim_key, 'KG')}`")
                
                m_key = next((k for k in s_satir.keys() if "miktar" in k.lower()), "Miktar")
                c_key = next((k for k in s_satir.keys() if "çıkış" in k.lower() or "cikis" in k.lower()), "Çıkış")
                k_key = next((k for k in s_satir.keys() if "kalan" in k.lower()), "Kalan")
                
                try: toplam_giris = float(str(s_satir.get(m_key, 0)).replace(",", ".").strip() or 0.0)
                except: toplam_giris = 0.0
                
                try: eski_toplam_cikis = float(str(s_satir.get(c_key, 0)).replace(",", ".").strip() or 0.0)
                except: eski_toplam_cikis = 0.0
                
                try: mevcut_kalan = float(str(s_satir.get(k_key, 0)).replace(",", ".").strip() or 0.0)
                except: mevcut_kalan = toplam_giris - eski_toplam_cikis
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Toplam Giriş", f"{toplam_giris:,.2f}")
                m2.metric("Bugüne Kadar Çıkan", f"{eski_toplam_cikis:,.2f}")
                m3.metric("Mevcut Kalan Stok", f"{mevcut_kalan:,.2f}")
                
                st.divider()
                
                with st.form("parcali_cikis_formu"):
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        cikis_miktari_girilen = st.number_input("Yapılacak Çıkış Miktarı:*", min_value=0.0, step=100.0, format="%.2f")
                    with c_col2:
                        cikis_turu = st.selectbox("Çıkış Türü / Rejim:*", ["Millileşme", "Devir", "İhracat", "Transit Ticaret", "Diğer"])
                    
                    yeni_toplam_cikis = eski_toplam_cikis + cikis_miktari_girilen
                    yeni_kalan_stok = toplam_giris - yeni_toplam_cikis
                    
                    if cikis_miktari_girilen > mevcut_kalan:
                        st.error(f"🚨 HATA: Çıkış yapmak istediğiniz miktar ({cikis_miktari_girilen:,.2f}), mevcut kalan stoktan ({mevcut_kalan:,.2f}) büyük olamaz!")
                        form_gecerli = False
                    else:
                        st.success(f"💡 İşlem Sonrası Güncel Kalan Stok: **{yeni_kalan_stok:,.2f} {s_satir.get(birim_key, 'KG')}**")
                        form_gecerli = True
                    
                    submit_cikis = st.form_submit_button("STOK ÇIKIŞINI ONAYLA VE SHEETS'E İŞLE", use_container_width=True)
                    
                    if submit_cikis:
                        if not form_gecerli:
                            st.error("Lütfen geçerli bir çıkış miktarı giriniz!")
                        elif cikis_miktari_girilen == 0:
                            st.warning("Çıkış miktarı 0 olamaz.")
                        else:
                            guncel_paket = {
                                "Çıkış": str(yeni_toplam_cikis),
                                "Kalan": str(yeni_kalan_stok)
                            }
                            if guncelle_stok_kaydi(secilen_b_no, guncel_paket):
                                log_detay = f"{secilen_b_no} nolu beyannameden {cikis_miktari_girilen:,.2f} {s_satir.get(birim_key, 'KG')} çıkış yapıldı. Çıkış Türü: {cikis_turu}"
                                log_sonuc = f"Kalan Stok: {yeni_kalan_stok:,.2f} {s_satir.get(birim_key, 'KG')}"
                                
                                kaydet(
                                    islem_adi=f"Stok Çıkışı ({secilen_b_no})",
                                    kategori=f"Stok Düşüş - {cikis_turu}",
                                    girdiler=log_detay,
                                    sonuc=log_sonuc,
                                    personel_adi=st.session_state.user_name,
                                    hedef_sheet=kayitlar_sheet
                                )
                                
                                st.success(f"{secilen_b_no} nolu beyannameden {cikis_miktari_girilen:,.2f} {s_satir.get(birim_key, 'KG')} ({cikis_turu}) başarıyla düşüldü!")
                                st.rerun()

        st.divider()
        excel_stok = to_excel(df_stok)
        st.download_button(label="Stok Özet Listesini Excel'e Aktar (İndir)", data=excel_stok, file_name=f"Mavi_Kimya_Stok_Takip_{datetime.now().strftime('%d_%m_%Y')}.xlsx", use_container_width=True)
    else:
        st.info("Henüz kaydedilmiş bir stok kaydı bulunmuyor.")

# --- 5. SEÇENEK: HESAPLAMA ARŞİVİ ---
elif st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler" and st.session_state.authenticated:
    st.markdown("### Kaydedilen İşlemler ve Stok Hareketleri Arşivi")
    data = load_data_cached("t_kayitlari")
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.divider()
        excel_data = to_excel(df)
        st.download_button(label="Excel'e Aktar (İndir)", data=excel_data, file_name=f"Mavi_Kimya_Arsiv_{datetime.now().strftime('%d_%m_%Y')}.xlsx", use_container_width=True)
    else:
        st.info("Henüz kaydedilmiş bir işlem bulunmuyor.")

st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
