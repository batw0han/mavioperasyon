import streamlit as st
import base64
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image
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

# --- 🚀 TURBO MOD (CACHING) AYARLARI ---

@st.cache_resource
def get_spreadsheet_cached():
    """Bağlantıyı ve Spreadsheet dosyasını bir kez açar, hafızada tutar."""
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
    """Tüm sayfaları tek seferde hafızaya alır. 429'u tarihe gömer!"""
    ss = get_spreadsheet_cached()
    if ss:
        return {
            "cari": ss.worksheet("cari_listesi"),
            "urun": ss.worksheet("urun_listesi"),
            "t_kayit": ss.worksheet("t_kayitlari"),
            "kullanici": ss.worksheet("kullanicilar"),
            "p_kayit": ss.worksheet("p_kayitlari")
        }
    return {}

sheets_dict = get_all_sheets()

if sheets_dict:
    cari_sheet = sheets_dict["cari"]
    urun_sheet = sheets_dict["urun"]
    kayitlar_sheet = sheets_dict["t_kayit"]
    kullanici_sheet = sheets_dict["kullanici"]
    p_kayitlar_sheet = sheets_dict["p_kayit"]
else:
    st.error("🚨 Google Sheets sayfalarına erişilemedi!")

# --- VERİ OKUMA CACHE FONKSİYONU ---
@st.cache_data(ttl=600)
def load_data_cached(sheet_name):
    """Verileri 10 dakika RAM'de tutar, Google'ı yormaz."""
    if sheets_dict and sheet_name in ["cari_listesi", "urun_listesi", "t_kayitlari", "kullanicilar", "p_kayitlari"]:
        mapping = {
            "cari_listesi": "cari",
            "urun_listesi": "urun",
            "t_kayitlari": "t_kayit",
            "kullanicilar": "kullanici",
            "p_kayitlari": "p_kayit"
        }
        return sheets_dict[mapping[sheet_name]].get_all_records()
    return []

def clear_cache():
    st.cache_data.clear()

# --- SESSION STATE BAŞLATMA ---
if "cari_listesi" not in st.session_state:
    st.session_state.cari_listesi = load_data_cached("cari_listesi")

if "urun_listesi" not in st.session_state:
    u_data = load_data_cached("urun_listesi")
    st.session_state.urun_listesi = sorted([row["urun_adi"] for row in u_data if "urun_adi" in row])

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "sayfa_yonetimi" not in st.session_state:
    st.session_state.sayfa_yonetimi = "Ana Sayfa"

# --- GİRİŞ PANELİ ---
if not st.session_state.authenticated:
    with st.sidebar:
        st.markdown("### 🔐 Personel Girişi")
        giris_ad = st.text_input("Kullanıcı Adı:")
        sifre_giris = st.text_input("Şifre:", type="password")
        
        if st.button("Giriş Yap"):
            if giris_ad and sifre_giris:
                user_data = load_data_cached("kullanicilar")
                user = next((item for item in user_data if str(item.get("kullanici_adi")) == giris_ad and str(item.get("sifre")) == sifre_giris), None)
                
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_name = user["kullanici_adi"]
                    st.session_state.user_role = user["yetki_seviyesi"] 
                    st.success(f"Hoş geldin, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("Hatalı Kullanıcı Adı veya Şifre!")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
else:
    with st.sidebar:
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}**})")
        st.divider()

        # --- YENİ NAVİGASYON DÜZENİ ---
        if st.button("Ana Sayfa)", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()
            
        st.divider()

        if st.button(" Yeni Sipariş Oluştur", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Yeni Sipariş"
            st.rerun()

        if st.button(" Kayıtlı Siparişleri Görüntüle", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Kayıtlı Siparişler"
            st.rerun()

        st.divider()

        # İşte yeni butonlarımız kanka, her şeyi ayırdık!
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
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()

# --- KAYDET FONKSİYONU ---
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
        st.toast("Veri başarıyla kaydedildi ✅")
    except Exception as e:
        st.error(f"Veri yazılamadı: {e}")

# --- LOGO VE GÖRSEL HAZIRLIK ---
def get_image_base64(file_path):
    with open(file_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

try:
    if os.path.exists("logo.png"):
        st.markdown(f'<div style="text-align: center;"><img src="data:image/x-icon;base64,{get_image_base64("logo.png")}" width="250"></div>', unsafe_allow_html=True)
except:
    pass

st.markdown("<div style='text-align: center;'><h1 style='color: #2596BE; margin-bottom: 0;'>MAVİ KİMYA</h1><p style='color: #64748B; font-size: 1.1em;'>Operasyonel Analiz ve Hesaplama Paneli</p></div>", unsafe_allow_html=True)
st.divider()

def to_excel(df):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='log')
    return output.getvalue()

# =====================================================================
# --- 🏛️ MERKEZİ SAYFA GÖSTERİM YÖNETİMİ (V4 BEZOS EDITION) ---
# =====================================================================

# --- 🌟 YENİ SEÇENEK: SADE VE TASLAK DASHBOARD (ANA SAYFA) ---
if st.session_state.sayfa_yonetimi == "Ana Sayfa":
    st.markdown("### Genel özet")
    st.caption("Şirket genel operasyonel durumunu gösteren ana kontrol merkezi.")
    
    # Taslak KPI Kartları (Sade ve yormayan cinsten kanka)
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric(label="Aktif Sipariş Takibi", value="Taslak", delta="ERP Hazırlık")
    with kpi2:
        st.metric(label="Aylık Toplam Hacim", value="0.00 m³", delta="Veri Bekleniyor")
    with kpi3:
        st.metric(label="Sistem Hızı (Turbo)", value="Işık Hızı", delta="100% Aktif")
        
    st.divider()
    st.info("💡 **Gelecek Güncelleme Notu:** Bu alanda dairesel grafikler (Pie Chart) ile ithalat/ihracat oranları ve gümrükteki araçların durum yüzdeleri canlı olarak listelenecektir.")

# ---  YENİ SİPARİŞ OLUŞTURMA EKRANI ---
elif st.session_state.sayfa_yonetimi == "Yeni Sipariş":
    st.markdown("### 🏛️ Sipariş ve Gümrük İşlemleri Yönetimi")
    
    firmalar = [c.get("cari_adi") for c in st.session_state.cari_listesi if "cari_adi" in c]
    secilen_cari_adi = st.selectbox("Cari Adı Ara / Seç:", options=[""] + sorted(firmalar), format_func=lambda x: "Firma seçmek için yazmaya başlayın..." if x == "" else x, key="akilli_cari_secim")

    if secilen_cari_adi != "":
        cari_detay = next((item for item in st.session_state.cari_listesi if item.get("cari_adi") == secilen_cari_adi), None)
        if cari_detay:
            tedarikci = secilen_cari_adi
            with st.container(border=True):
                c_detay1, c_detay2 = st.columns([3, 1])
                with c_detay1:
                    st.markdown(f"**Adres:**\n{cari_detay.get('adres', 'Adres Bilgisi Yok')}")
                with c_detay2:
                    st.caption("✅ Veritabanı Onaylı")
        else:
            tedarikci = ""
    else:
        tedarikci = ""
        st.info("İşlem yapmak için lütfen listeden bir firma seçin.")

    with st.expander(" Yeni Cari Kaydet"):
        y_cari = st.text_input("Yeni Cari Adı:", key="y_cari_input")
        y_adres = st.text_area("Cari Adresi:", key="y_cari_adres")
        if st.button("Cariyi Rehbere İşle", use_container_width=True):
            if y_cari and y_adres:
                cari_sheet.append_row([y_cari, y_adres]) 
                clear_cache()
                st.session_state.cari_listesi = cari_sheet.get_all_records()
                st.success(f"{y_cari} Google Sheets'e kaydedildi!")
                st.rerun()

    st.divider()

    col_ust1, col_ust2 = st.columns(2)
    with col_ust1:
        islem_ana_tipi = st.selectbox("İşlem Türü:", ["İthalat", "İhracat"], key="islem_ana_tip")
    with col_ust2:
        if islem_ana_tipi == "İthalat":
            islem_sekli = st.selectbox("İthalat Şekli:", ["Kesin İthalat", "Devir (Antrepo)", "Geçici İthalat"])
            beyanname_var_mi = st.checkbox("Beyannamesi Var mı?")
        else:
            islem_sekli = st.selectbox("İhracat Şekli:", ["İhracat", "Transit Ticaret", "Devir"])
            beyanname_var_mi = False

    col_alt1, col_alt2 = st.columns(2)
    with col_alt1:
        fatura_tarihi = st.date_input("📅 Fatura Tarihi:", value=datetime.now())
    with col_alt2:
        invoice_no = st.text_input("📄 Invoice No:", placeholder="Örn: MAVI-2026-001")

    if beyanname_var_mi:
        st.info("📑 Beyanname Detayları")
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            beyanname_no = st.text_input("Beyanname No:", placeholder="Örn: 2606...")
        with b_col2:
            rejim = st.selectbox("Beyanname Rejimi:", ["40 71 (Antrepodan İthalat)", "71 71 (Antrepodan Antrepoya)", "71 00 (Özet Beyan Giriş)", "10 00 (Kesin İhracat)"])
        with b_col3:
            kapanis_tarihi = st.date_input("Beyanname Kapanış Tarihi")
            vade_tarihi = kapanis_tarihi + dt.timedelta(days=30)
            st.warning(f"🏦 Vergi Son Ödeme Tarihi: {vade_tarihi.strftime('%d.%m.%Y')}")

    st.divider()
    st.markdown("####  Ürün ve Sevkiyat Detayları")
    
    col_u1, col_u2 = st.columns([3, 1])
    with col_u2:
        yeni_urun_check = st.checkbox("Yeni Ürün")
    with col_u1:
        if yeni_urun_check:
            urun_adi = st.text_input("Ürün Adını Ekleyin:", key="yeni_urun_input")
            if st.button("Listeye Ekle"):
                if urun_adi and urun_adi not in st.session_state.urun_listesi:
                    urun_sheet.append_row([urun_adi])
                    clear_cache()
                    st.session_state.urun_listesi.append(urun_adi)
                    st.session_state.urun_listesi.sort()
                    st.success(f"{urun_adi} ürün listesine eklendi!")
                    st.rerun()
        else:
            urun_secimi = st.selectbox("Ürün Seçiniz:", st.session_state.urun_listesi)

    incoterm_aktif = st.checkbox("Siparişte Incoterm belirtmek istiyorum", value=True, key="inc_chk_top")
    st.divider()
    col_t1, col_t2, col_t3 = st.columns(3)
    devir_mi = "Devir" in islem_sekli
    tasima_sekli = None
    
    with col_t1:
        if not devir_mi:
            tasima_sekli = st.selectbox("Taşıma Şekli:", ["Deniz", "Kara", "Hava", "Demiryolu"], key="siparis_tasima")
        else:
            st.info("Devir işleminde taşıma şekli sorulmaz.")

    with col_t2:
        if incoterm_aktif:
            incoterm = st.selectbox("Incoterm / Teslim Şekli", ["EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"], key="sip_inc")
        else:
            st.text_input("Incoterm", value="Belirtilmedi", disabled=True, key="inc_dis")
            incoterm = ""

    with col_t3:
        if devir_mi:
            liman = st.selectbox("İşlem Yapılan Gümrük:", ["Erenköy Gümrük", "Muratbey Gümrük", "Ambarlı Gümrük"], key="devir_gumruk")
        elif tasima_sekli == "Kara":
            liman = st.selectbox("Kara Gümrüğü:", ["Muratbey", "Erenköy", "Dereköy", "Çerkezköy", "Kapıkule"], key="kara_gumruk")
        elif tasima_sekli == "Deniz":
            liman = st.selectbox("Liman/Gümrük:", ["Ambarlı", "Körfez", "Derince", "Zeytinburnu", "Mersin", "İzmir"], key="deniz_liman")
        elif tasima_sekli == "Demiryolu":
            liman = st.selectbox("Gar gümrüğü:", ["Halkalı", "Küçükçekmece", "Çerkezköy", "Lüleburgaz"], key="demiryolu_gar")
        else:
            liman = st.text_input("Gümrük/Liman:", value="HAVA/DİĞER", key="diger_liman_input")

    st.divider()
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        miktar = st.number_input("Miktar:", min_value=0.0)
        birim = st.radio("Birim:", ["KG", "LT"], horizontal=True)
    with col_f2:
        toplam_tutar = st.number_input("Toplam Fatura Tutarı:", min_value=0.0)
    with col_f3:
        para_birimi = st.selectbox("Para Birimi:", ["$", "€", "₺", "£"], key="para_birimi_sec")

    if st.button("💾 SİPARİŞİ KAYDET VE ARŞİVLE", use_container_width=True):
        if tedarikci == "" or miktar == 0 or invoice_no == "":
            st.error("Lütfen Firma Seçimi, Miktar ve Invoice No alanlarını boş bırakmayın!")
        else:
            f_tarih_str = fatura_tarihi.strftime("%d.%m.%Y")
            kaydet(
                islem_adi=f"INV: {invoice_no} | {tedarikci}",
                kategori=f"{islem_ana_tipi} - {islem_sekli}",
                girdiler=f"F.Tarihi: {f_tarih_str} | {miktar} {birim} {urun_secimi}",
                sonuc=f"{toplam_tutar} {para_birimi}",
                personel_adi=st.session_state.user_name,
                hedef_sheet=p_kayitlar_sheet
            )
            st.success(f"Sipariş, Invoice No: {invoice_no} ile p_kayitlari sayfasına başarıyla işlendi! 🚀")

# --- 📦 SEÇENEK: KAYITLI SİPARİŞLERİ GÖRÜNTÜLEME EKRANI (p_kayitlari) ---
elif st.session_state.sayfa_yonetimi == "Kayıtlı Siparişler":
    if not st.session_state.authenticated:
        st.error("🚫 Bu alanı görüntülemek için yetkiniz yok. Lütfen sol panelden giriş yapınız.")
    else:
        st.markdown("###  Kaydedilen Siparişler")
        st.caption("Yeni Sipariş ekranından girilen tüm gerçek operasyon kayıtları burada listelenir.")
        
        siparis_data = load_data_cached("p_kayitlari")
        if siparis_data:
            df_siparis = pd.DataFrame(siparis_data)
            st.dataframe(df_siparis, use_container_width=True, hide_index=True)
            
            st.divider()
            col_sip1, col_sip2 = st.columns(2)
            with col_sip1:
                excel_sip = to_excel(df_siparis)
                st.download_button(label="📥 Sipariş Listesini Excel'e Aktar", data=excel_sip, file_name=f"Mavi_Kimya_Siparisler_{datetime.now().strftime('%d_%m_%Y')}.xlsx", use_container_width=True)
            with col_sip2:
                if st.session_state.get("user_role") == "admin":
                    if st.button("🔴 Sipariş Arşivini Sıfırla", use_container_width=True):
                        rows_to_del = len(p_kayitlar_sheet.get_all_values())
                        if rows_to_del > 1:
                            p_kayitlar_sheet.delete_rows(2, rows_to_del)
                            clear_cache()
                            st.warning("Gerçek sipariş arşivi başarıyla temizlendi.")
                            st.rerun()
                else:
                    st.info("ℹ️ Sipariş silme/düzenleme yetkileri sadece Yönetici (Admin) hesabına tanımlıdır.")
        else:
            st.info("📭 Henüz kaydedilmiş bir sipariş operasyonu bulunmuyor.")

# --- 🧮 YENİ SEÇENEK: HESAPLAMA ARAÇLARI (ESKİ ANA SAYFA BURADA!) ---
elif st.session_state.sayfa_yonetimi == "Hesaplama Araçları":
    st.markdown("###  Hesaplama ve Operasyon Araçları")
    
    islem = st.selectbox(
        "🛠️ Lütfen Yapmak İstediğiniz İşlemi Seçin:",
        [
            "Ardiye Hesaplama",
            "KG -> LT Çevirme",
            "LT -> KG Çevirme",
            "Yoğunluk Hesaplama",
            "Denatürasyon Hesaplama (Yeni Sipariş)",
            "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)"
        ],
        key="hesaplama_araclari_select"
    )

    # --- İŞLEM MANTIKLARI ---
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
            with col2: st.number_input("Yoğunluk (Density)", value=0.00, format="%.4f", disabled=True)

        if st.button("HESAPLA", use_container_width=True):
            m3 = hacim_lt / 1000
            carpan = 13 if antrepo == "İzgin Antrepo" else 9
            toplam = m3 * carpan

            st.markdown("### 📊 İşlem Sonucu")
            res_c1, res_c2 = st.columns(2)
            res_c1.metric("Toplam Hacim", f"{m3:.3f} m³")
            res_c2.metric("Toplam Bedel", f"{toplam:.2f} $", delta=f"{antrepo} Tarifesi")

            girdi_notu = f"{kg_input} KG" if giris_tipi == "Kilogram (KG)" else f"{lt_input} LT"
            st.session_state.son_hesaplama = {"kategori": "Ardiye Hesaplama", "girdi": girdi_notu, "sonuc": f"{m3:.3f} m³ / {toplam:.2f} $"}

        if "son_hesaplama" in st.session_state:
            st.divider()
            with st.expander("💾 Bu İşlemi Arşive Kaydet"):
                with st.form("kayit_formu", clear_on_submit=True):
                    kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: 10 Araç Metanol")
                    submit_button = st.form_submit_button("KAYDI ONAYLA", use_container_width=True)

                    if submit_button:
                        if not st.session_state.authenticated: st.error("❌ Yetkisiz İşlem! Önce giriş yapın.")
                        elif not kayit_ismi: st.warning("⚠️ Lütfen işlem için bir isim giriniz.")
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
                if 0.70 <= yogunluk <= 1.20: st.success("ℹ️ Standart sıvı kimyasal aralığında bir değer tespit edildi.")
                else: st.warning("⚠️ Dikkat: Bu yoğunluk değeri alışılmışın dışında.")
            else: st.error("Hacim (LT) değeri 0 olamaz!")

    elif islem == "Denatürasyon Hesaplama (Yeni Sipariş)":
        tip = st.selectbox("Reçete Tipi:", ["K Tipi", "D Tipi", "Metanol Denatürasyonu"])
        miktar = st.number_input("Saf Ürün Hacmi (LT):", min_value=0.0)
        detay = ""
        if st.button("REÇETEYİ HAZIRLA", use_container_width=True):
            carpan = miktar / 100
            st.markdown("### 📝 Hazırlanacak Reçete")
            if tip == "K Tipi": detay = f"D. Benzoat: {0.8 * carpan:.2f} gr | TBA: {78 * carpan:.2f} gr"
            elif tip == "D Tipi": detay = f"IPA: {5 * carpan:.2f} kg | TBA: {78 * carpan:.2f} gr"
            else: detay = f"D. Benzoat: {3 * carpan:.2f} gr"
            st.warning(detay)
            st.session_state.son_hesaplama = {"kategori": "Denatürasyon Hesabı", "girdi": f"{miktar} LT {tip}", "sonuc": detay}

        if "son_hesaplama" in st.session_state:
            st.divider()
            with st.expander("💾 Bu Reçeteyi Arşive Kaydet"):
                kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: Farmed 20 Tonluk Tank Hazırlığı")
                if st.button("REÇETEYİ ONAYLA", use_container_width=True):
                    if not st.session_state.authenticated: st.error("❌ Yetkisiz İşlem! Lütfen önce giriş yapınız.")
                    else:
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

# --- SEÇENEK: HESAPLAMA ARŞİVİ (t_kayitlari) ---
elif st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler":
    st.markdown("### Kaydedilen Hesaplama İşlemleri")
    data = load_data_cached("t_kayitlari")
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            excel_data = to_excel(df)
            st.download_button(label="📥 Excel'e Aktar (İndir)", data=excel_data, file_name=f"Mavi_Kimya_Arsiv_{datetime.now().strftime('%d_%m_%Y')}.xlsx", use_container_width=True)
        with col_ex2:
            if st.session_state.user_role == "admin":
                if st.button("🔴 Arşivi Temizle", use_container_width=True):
                    rows_to_del = len(kayitlar_sheet.get_all_values())
                    if rows_to_del > 1:
                        kayitlar_sheet.delete_rows(2, rows_to_del)
                        clear_cache()
                        st.rerun()
            else:
                st.warning("⚠️ Arşivi temizleme yetkiniz bulunmamaktadır.")
    else:
        st.info("Henüz kaydedilmiş bir işlem bulunmuyor.")

st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
