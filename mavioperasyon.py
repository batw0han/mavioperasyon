import streamlit as st
import base64
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import datetime as dt
import os

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
        row_to_append = [data_dict.get(h, "") for h in headers]
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
    st.markdown("### Genel Özet")
    
    stok_listesi = load_data_cached("p_kayitlari")
    df_stoklar = pd.DataFrame(stok_listesi) if stok_listesi else pd.DataFrame()
    
    toplam_stok_kalemi = len(df_stoklar)
    
    kpi1, kpi2 = st.columns(2)
    with kpi1:
        st.metric(label="Aktif Stok Kalemi", value=str(toplam_stok_kalemi), delta="Toplam Kayıt")
    with kpi2:
        st.metric(label="Sistem Hızı (Turbo)", value="Işık Hızı", delta="100% Aktif")
        
    st.divider()
    if not df_stoklar.empty:
        st.markdown("#### Son Eklenen Stok Kayıtları")
        st.dataframe(df_stoklar.tail(5), use_container_width=True, hide_index=True)

# --- 3. SEÇENEK: YENİ STOK EKLE ---
elif st.session_state.sayfa_yonetimi == "Yeni Stok Ekle" and st.session_state.authenticated:
    st.markdown("### Yeni Stok Kaydı Oluştur")
    st.caption("Gümrük ve stok bilgilerinizi girerek Google Sheets veritabanına işleyin.")

    # --- ESNEK VERİ LİSTELEME ---
    u_data = load_data_cached("urun_listesi")
    mevcut_urunler = []
    if u_data:
        for r in u_data:
            val = list(r.values())[0] if r else ""
            if str(val).strip(): mevcut_urunler.append(str(val).strip())
    mevcut_urunler = sorted(list(set(mevcut_urunler)))
    
    c_data = load_data_cached("cari_listesi")
    mevcut_alicilar, mevcut_saticilar = [], []
    if c_data:
        for row in c_data:
            c_adi_key = next((k for k in row.keys() if "adi" in k.lower() or "cari" in k.lower()), list(row.keys())[0])
            c_tipi_key = next((k for k in row.keys() if "tipi" in k.lower() or "tur" in k.lower()), None)
            
            c_adi = str(row.get(c_adi_key, "")).strip()
            c_tipi = str(row.get(c_tipi_key, "")).strip().upper() if c_tipi_key else ""
            
            if c_adi:
                if "ALICI" in c_tipi or "ALICI" in c_adi.upper():
                    mevcut_alicilar.append(c_adi)
                elif "SATICI" in c_tipi or "SATICI" in c_adi.upper():
                    mevcut_saticilar.append(c_adi)
                else:
                    mevcut_alicilar.append(c_adi)
                    mevcut_saticilar.append(c_adi)
                    
    mevcut_alicilar = sorted(list(set(mevcut_alicilar)))
    mevcut_saticilar = sorted(list(set(mevcut_saticilar)))

    term_data = load_data_cached("terminal_listesi")
    mevcut_terminaller = []
    if term_data:
        for r in term_data:
            val = list(r.values())[0] if r else ""
            if str(val).strip(): mevcut_terminaller.append(str(val).strip())
    mevcut_terminaller = sorted(list(set(mevcut_terminaller)))

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
    
    col1, col2 = st.columns(2)
    with col1:
        secilen_urun = st.selectbox("Ürün Seçiniz:*", options=[""] + mevcut_urunler)
        secilen_satici = st.selectbox("Satıcı Firma:*", options=[""] + mevcut_saticilar)
    with col2:
        secilen_alici = st.selectbox("Alıcı Firma:*", options=[""] + mevcut_alicilar)
        fatura_no = st.text_input("Fatura No:*", placeholder="Örn: INV-2026-001")

    st.divider()
    st.markdown("#### 2. Beyanname ve Miktar Detayları")
    
    col3, col4, col5 = st.columns(3)
    with col3:
        beyanname_no = st.text_input("Beyanname No:*", placeholder="Örn: 2606...")
        mira_miktar = st.number_input("Miktar:*", min_value=0.0, step=100.0)
    with col4:
        rejim = st.selectbox("Rejim:", ["40 71 (Kesin İthalat)", "71 71 (Antrepo)", "10 00 (Kesin İhracat)", "71 00 (Özet Beyan)", "Diğer"])
        birim = st.radio("Birim:*", ["KG", "LT"], horizontal=True)
    with col5:
        secilen_terminal = st.selectbox("Terminal / Antrepo:*", options=[""] + mevcut_terminaller)
        cikis_miktari = st.number_input("İlk Çıkış Miktarı:", min_value=0.0, value=0.0, step=100.0)

    # Otomatik Kalan Miktar Hesaplama
    kalan_miktar = mira_miktar - cikis_miktari
    st.info(f"Hesaplanan Kalan Stok Miktarı: **{kalan_miktar:.2f} {birim}**")

    st.divider()
    
    if st.button("STOK KAYDINI VERİTABANINA İŞLE", use_container_width=True):
        if not beyanname_no or not secilen_urun or mira_miktar == 0 or not fatura_no or not secilen_satici or not secilen_alici:
            st.error("Lütfen Beyanname No, Ürün, Satıcı, Alıcı, Miktar ve Fatura No alanlarını doldurunuz!")
        else:
            yeni_stok_paketi = {
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
                "Kayıt Yapan Kullanıcı": st.session_state.user_name,
                "Kayıt Tarihi": datetime.now().strftime("%d.%m.%Y %H:%M")
            }
            kaydet_yeni_stok(yeni_stok_paketi)
            st.success(f"Beyanname No: {beyanname_no} ile stok veritabanına başarıyla eklendi!")
            st.rerun()

# --- 4. SEÇENEK: BEYANNAME - STOK TAKİP VE STOK DÜŞÜŞ MODÜLÜ ---
elif st.session_state.sayfa_yonetimi == "Beyanname - Stok Takip" and st.session_state.authenticated:
    st.markdown("### 📋 Beyanname & Stok Takip Paneli")
    st.caption("Veritabanındaki stokların canlı özeti ve dinamik ürün çıkış işlemleri.")
    
    stok_data = load_data_cached("p_kayitlari")
    if stok_data:
        df_stok = pd.DataFrame(stok_data)
        
        # 1. ÖZET TABLO
        st.markdown("#### 📦 Mevcut Stok Özet Tablosu")
        st.dataframe(df_stok, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # 2. STOK ÇIKIŞ İŞLEM MODÜLÜ
        st.markdown("#### 📤 Stoktan Ürün Çıkışı Yap")
        
        b_col_name = df_stok.columns[0]
        beyanname_listesi = df_stok[b_col_name].unique().tolist()
        secilen_b_no = st.selectbox("İşlem Yapılacak Beyanname No Seçin:*", options=[""] + beyanname_listesi)
        
        if secilen_b_no:
            s_satir = df_stok[df_stok[b_col_name] == secilen_b_no].iloc[0].to_dict()
            
            with st.container(border=True):
                st.markdown(f"**📄 Seçilen Beyanname:** `{secilen_b_no}` | **Ürün:** `{s_satir.get('Ürün', '-')}` | **Birim:** `{s_satir.get('Birim', 'KG')}`")
                
                # Sayısal Değerleri Güvenli Çekme
                try: toplam_giris = float(str(s_satir.get("Miktar", 0)).replace(",", ".").strip() or 0.0)
                except: toplam_giris = 0.0
                
                try: eski_toplam_cikis = float(str(s_satir.get("Çıkış", 0)).replace(",", ".").strip() or 0.0)
                except: eski_toplam_cikis = 0.0
                
                try: mevcut_kalan = float(str(s_satir.get("Kalan", 0)).replace(",", ".").strip() or 0.0)
                except: mevcut_kalan = toplam_giris - eski_toplam_cikis
                
                # Canlı Metrik Gösterimi
                m1, m2, m3 = st.columns(3)
                m1.metric("Toplam Giriş", f"{toplam_giris:,.2f}")
                m2.metric("Bugüne Kadar Çıkan", f"{eski_toplam_cikis:,.2f}")
                m3.metric("Mevcut Kalan Stok", f"{mevcut_kalan:,.2f}")
                
                st.divider()
                
                with st.form("parcali_cikis_formu"):
                    c_col1, c_col2 = st.columns(2)
                    with c_col1:
                        cikis_miktari_girilen = st.number_input("Yapılacak Çıkış Miktarı:*", min_value=0.0, step=100.0)
                    with c_col2:
                        cikis_turu = st.selectbox("Çıkış Türü / Rejim:*", ["Millileşme", "Devir", "İhracat", "Transit Ticaret", "Diğer"])
                    
                    # Hesaplanan Yeni Değerler
                    yeni_toplam_cikis = eski_toplam_cikis + cikis_miktari_girilen
                    yeni_kalan_stok = toplam_giris - yeni_toplam_cikis
                    
                    if cikis_miktari_girilen > mevcut_kalan:
                        st.error(f"🚨 HATA: Çıkış yapmak istediğiniz miktar ({cikis_miktari_girilen:,.2f}), mevcut kalan stoktan ({mevcut_kalan:,.2f}) büyük olamaz!")
                        form_gecerli = False
                    else:
                        st.success(f"💡 İşlem Sonrası Güncel Kalan Stok: **{yeni_kalan_stok:,.2f} {s_satir.get('Birim', 'KG')}**")
                        form_gecerli = True
                    
                    submit_cikis = st.form_submit_button("STOK ÇIKIŞINI ONAYLA VE SHEETS'E İŞLE", use_container_width=True)
                    
                    if submit_cikis:
                        if not form_gecerli:
                            st.error("Lütfen geçerli bir çıkış miktarı giriniz!")
                        elif cikis_miktari_girilen == 0:
                            st.warning("Çıkış miktarı 0 olamaz.")
                        else:
                            # 1. Stok tablosunu güncelle
                            guncel_paket = {
                                "Çıkış": str(yeni_toplam_cikis),
                                "Kalan": str(yeni_kalan_stok)
                            }
                            if guncelle_stok_kaydi(secilen_b_no, guncel_paket):
                                # 2. İşlem Logunu t_kayitlari (Hesaplama Arşivi) sayfasına otomatik yaz
                                log_detay = f"{secilen_b_no} nolu beyannameden {cikis_miktari_girilen:,.2f} {s_satir.get('Birim', 'KG')} çıkış yapıldı. Çıkış Türü: {cikis_turu}"
                                log_sonuc = f"Kalan Stok: {yeni_kalan_stok:,.2f} {s_satir.get('Birim', 'KG')}"
                                
                                kaydet(
                                    islem_adi=f"Stok Çıkışı ({secilen_b_no})",
                                    kategori=f"Stok Düşüş - {cikis_turu}",
                                    girdiler=log_detay,
                                    sonuc=log_sonuc,
                                    personel_adi=st.session_state.user_name,
                                    hedef_sheet=kayitlar_sheet
                                )
                                
                                st.success(f"{secilen_b_no} nolu beyannameden {cikis_miktari_girilen:,.2f} {s_satir.get('Birim', 'KG')} ({cikis_turu}) başarıyla düşüldü! Sayfa yenileniyor...")
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
