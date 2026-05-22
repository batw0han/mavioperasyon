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
    """Verileri gspread ile ham liste olarak çeker, ilk satırı başlık yapar."""
    if sheets_dict and sheet_name in ["cari_listesi", "urun_listesi", "t_kayitlari", "kullanicilar", "p_kayitlari"]:
        mapping = {
            "cari_listesi": "cari",
            "urun_listesi": "urun",
            "t_kayitlari": "t_kayit",
            "kullanicilar": "kullanici",
            "p_kayitlari": "p_kayit"
        }
        raw_data = sheets_dict[mapping[sheet_name]].get_all_values()
        
        if raw_data:
            # İlk satırı sütun başlıkları yap, kalanını veri satırı yap
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
        st.markdown("### Giriş Paneli")
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
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}**")
        st.divider()

        # --- NAVİGASYON ---
        if st.button("Ana Sayfa", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()
            
        st.divider()

        if st.button("Yeni Sipariş Oluştur", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Yeni Sipariş"
            st.rerun()

        if st.button("Kayıtlı Siparişleri Görüntüle", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Kayıtlı Siparişler"
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
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()

# --- MERKEZİ KAYDET VE GÜNCELLE FONKSİYONLARI ---
def kaydet_yeni_siparis(data_dict):
    try:
        headers = p_kayitlar_sheet.row_values(1)
        row_to_append = [data_dict.get(h, "") for h in headers]
        p_kayitlar_sheet.append_row(row_to_append)
        clear_cache()
        st.toast("Yeni sipariş veritabanına işlendi! ✅")
    except Exception as e:
        st.error(f"Ekleme Hatası: {e}")

def guncelle_mevcut_siparis(invoice_no, guncel_data_dict):
    try:
        all_rows = p_kayitlar_sheet.get_all_values()
        headers = all_rows[0]
        
        # Anahtar sütun indeksini bul (Sipariş ID / Invoice No)
        id_index = headers.index("Sipariş ID / Invoice No")
        
        row_num = -1
        for i, r in enumerate(all_rows):
            if r[id_index] == invoice_no:
                row_num = i + 1
                break
                
        if row_num != -1:
            for key, val in guncel_data_dict.items():
                if key in headers:
                    col_num = headers.index(key) + 1
                    p_kayitlar_sheet.update_cell(row_num, col_num, str(val))
            clear_cache()
            st.toast("Sipariş başarıyla güncellendi! 🔄")
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

# --- LOGO ENJEKSİYONU ---
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
# --- 🏛️ MERKEZİ SAYFA GÖSTERİM YÖNETİMİ ---
# =====================================================================

# --- SEÇENEK: ANA SAYFA ---
if st.session_state.sayfa_yonetimi == "Ana Sayfa":
    st.markdown("### Mavi Kimya Yönetim Panel")
    st.caption("Şirket genel operasyonel durumunu gösteren ana kontrol merkezi.")
    
    siparis_listesi = load_data_cached("p_kayitlari")
    df_siparisler = pd.DataFrame(siparis_listesi) if siparis_listesi else pd.DataFrame()
    
    # 📊 KPI Hesaplamaları
    acik_beyanname_sayisi = 0
    kritik_beyannameler = []
    
    if not df_siparisler.empty:
        # "Beyanname Durumu" sütununa göre sayım
        if "Beyanname Durumu" in df_siparisler.columns:
            acik_beyanname_sayisi = len(df_siparisler[df_siparisler["Beyanname Durumu"].str.lower() == "açık"])
            
        # 📅 Vergi Son Ödeme Günü Yaklaşanları Analiz Etme
        if "Vergi Son Ödeme Tarihi" in df_siparisler.columns and "Beyanname Durumu" in df_siparisler.columns:
            bugun = datetime.now().date()
            for idx, row in df_siparisler.iterrows():
                if row["Beyanname Durumu"].lower() == "açık" and row["Vergi Son Ödeme Tarihi"]:
                    try:
                        vade_tarihi = datetime.strptime(row["Vergi Son Ödeme Tarihi"], "%d.%m.%Y").date()
                        kalan_gun = (vade_tarihi - bugun).days
                        if kalan_gun <= 7:
                            kritik_beyannameler.append({
                                "Sipariş / Invoice": row.get("Sipariş ID / Invoice No", "Belirtilmedi"),
                                "Beyanname No": row.get("Beyanname No", "-"),
                                "Son Ödeme Tarihi": row["Vergi Son Ödeme Tarihi"],
                                "Kalan Gün": f"{kalan_gun} Gün Kaldı" if kalan_gun >= 0 else f"SÜRESİ GEÇMİŞ ({abs(kalan_gun)} Gün)"
                            })
                    except:
                        pass

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric(label="Açık Beyanname Sayısı", value=str(acik_beyanname_sayisi), delta="Aktif Dosya", delta_color="inverse")
    with kpi2:
        st.metric(label="Aylık Toplam Hacim", value=f"{len(df_siparisler)} Sipariş", delta="Toplam Kayıt")
    with kpi3:
        st.metric(label="Sistem Hızı (Turbo)", value="Işık Hızı", delta="100% Aktif")
        
    st.divider()
    
    # 🚨 KRİTİK VERGİ ALARMI TABLOSU
    if kritik_beyannameler:
        st.markdown("<h4 style='color: #EF4444;'>⚠️ Vergi Son Ödeme Günü Yaklaşan Beyannameler</h4>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(kritik_beyannameler), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Önümüzdeki 7 gün içinde ödeme vadesi dolan açık beyanname bulunmuyor.")

# --- SEÇENEK: YENİ SİPARİŞ OLUŞTURMA EKRANI ---
elif st.session_state.sayfa_yonetimi == "Yeni Sipariş":
    st.markdown("### Sipariş ve Gümrük İşlemleri Yönetimi")
    
    firmalar = [c.get("cari_adi") for c in st.session_state.cari_listesi if "cari_adi" in c]
    secilen_cari_adi = st.selectbox("Cari Adı Ara / Seç:", options=[""] + sorted(firmalar))

    if secilen_cari_adi:
        cari_detay = next((item for item in st.session_state.cari_listesi if item.get("cari_adi") == secilen_cari_adi), None)
        tedarikci = secilen_cari_adi
        if cari_detay:
            with st.container(border=True):
                st.markdown(f"**Adres:** {cari_detay.get('adres', 'Adres Bilgisi Yok')}")
    else:
        tedarikci = ""
        st.info("İşlem yapmak için lütfen listeden bir firma seçin.")

    st.divider()

    col_ust1, col_ust2 = st.columns(2)
    with col_ust1:
        islem_ana_tipi = st.selectbox("İşlem Türü:", ["İthalat", "İhracat"])
    with col_ust2:
        islem_sekli = st.selectbox("İşlem Şekli:", ["Kesin İthalat", "Devir (Antrepo)", "Geçici İthalat"] if islem_ana_tipi == "İthalat" else ["İhracat", "Transit Ticaret", "Devir"])
        beyanname_var_mi = st.checkbox("Beyannamesi Var mı?") if islem_ana_tipi == "İthalat" else False

    col_alt1, col_alt2 = st.columns(2)
    with col_alt1:
        fatura_tarihi = st.date_input("Fatura Tarihi:", value=datetime.now())
    with col_alt2:
        invoice_no = st.text_input("Invoice No:", placeholder="Örn: MAVI-2026-001")

    # Beyanname Değişkenleri İlklendirme
    b_no, b_tarih_str, b_durum, v_tarih_str = "", "", "Açık", ""
    
    if beyanname_var_mi:
        st.info("Beyanname Detayları")
        b_col1, b_col2 = st.columns(2)
        with b_col1:
            b_no = st.text_input("Beyanname No:", placeholder="Örn: 2606...")
        with b_col2:
            b_tarih = st.date_input("Beyanname Tescil Tarihi")
            b_tarih_str = b_tarih.strftime("%d.%m.%Y")
            vade_tarihi = b_tarih + dt.timedelta(days=30)
            v_tarih_str = vade_tarihi.strftime("%d.%m.%Y")
            st.warning(f"🏦 Vergi Son Ödeme Tarihi: {v_tarih_str}")

    st.divider()
    st.markdown("#### Sipariş ve Sevkiyat Detayları")
    urun_secimi = st.selectbox("Ürün Seçiniz:", st.session_state.urun_listesi)
    
    col_t1, col_t2, col_t3 = st.columns(3)
    devir_mi = "Devir" in islem_sekli
    tasima_sekli = "Kara"
    
    with col_t1:
        tasima_sekli = st.selectbox("Taşıma Şekli:", ["Deniz", "Kara", "Hava", "Demiryolu"]) if not devir_mi else "Devir"
    with col_t2:
        incoterm = st.selectbox("Incoterm / Teslim Şekli", ["EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"])
    with col_t3:
        liman = st.text_input("Gümrük / Liman:", value="Muratbey")

    # 🌊 DENİZYOLU DİNAMİK ALANLARI
    bl_no, konteyner_no = "", ""
    if tasima_sekli == "Deniz":
        st.markdown("##### ⚓ Denizyolu Konteyner Bilgileri")
        bl_c1, bl_c2 = st.columns(2)
        with bl_c1: bl_no = st.text_input("B/L (Bill of Lading) No:")
        with bl_c2: konteyner_no = st.text_input("Konteyner No:")

    st.divider()
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        miktar = st.number_input("Miktar:", min_value=0.0)
        birim = st.radio("Birim:", ["KG", "LT"], horizontal=True)
    with col_f2:
        toplam_tutar = st.number_input("Toplam Fatura Tutarı:", min_value=0.0)
    with col_f3:
        para_birimi = st.selectbox("Para Birimi:", ["$", "€", "₺", "£"])

    if st.button("SİPARİŞİ KAYDET VE ARŞİVLE", use_container_width=True):
        if not tedarikci or miktar == 0 or not invoice_no:
            st.error("Lütfen Firma Seçimi, Miktar ve Invoice No alanlarını boş bırakmayın!")
        else:
            yeni_siparis_verisi = {
                "Sipariş ID / Invoice No": invoice_no,
                "Kategori / İşlem Türü": f"{islem_ana_tipi} - {islem_sekli}",
                "Miktar": str(miktar),
                "Birim": birim,
                "Ürün Adı": urun_secimi,
                "Toplam Tutar": str(toplam_tutar),
                "Para Birimi": para_birimi,
                "Taşıma Şekli": tasima_sekli,
                "Liman / Gümrük": liman,
                "Personel": st.session_state.user_name,
                "Kayıt Tarihi": fatura_tarihi.strftime("%d.%m.%Y"),
                "Beyanname No": b_no,
                "Beyanname Tarihi": b_tarih_str,
                "Beyanname Durumu": "Açık" if b_no else "",
                "Vergi Son Ödeme Tarihi": v_tarih_str,
                "B/L No": bl_no,
                "Konteyner No": konteyner_no,
                "Vitsan Rapor No": "",
                "Ardiye Ödendi mi": "Hayır",
                "Depozito Ödendi mi": "Hayır",
                "Depozito İade Edildi mi": "Hayır"
            }
            kaydet_yeni_siparis(yeni_siparis_verisi)
            st.success(f"Sipariş {invoice_no} başarıyla kaydedildi!")
            st.rerun()

# --- SEÇENEK: KAYITLI SİPARİŞLERİ GÖRÜNTÜLEME VE DÜZENLEME EKRANI ---
elif st.session_state.sayfa_yonetimi == "Kayıtlı Siparişler":
    if not st.session_state.authenticated:
        st.error("Bu alanı görüntülemek için yetkiniz yok. Lütfen giriş yapınız.")
    else:
        st.markdown("### Kayıtlı Sipariş Takip Otomasyonu")
        
        siparis_data = load_data_cached("p_kayitlari")
        if siparis_data:
            df_siparis = pd.DataFrame(siparis_data)
            st.dataframe(df_siparis, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # 🛠️ SİPARİŞ DÜZENLEME MODÜLÜ
            st.markdown("#### 🔄 Sipariş Detaylarını Düzenle ve Güncelle")
            ilk_kolon_adi = df_siparis.columns[0] 
            inv_listesi = df_siparis[ilk_kolon_adi].unique().tolist()
            secilen_inv = st.selectbox("Düzenlemek İstediğiniz Siparişi Seçin (Invoice No):", options=[""] + inv_listesi)
            
            if secilen_inv:
                # Seçilen satırın verilerini çek
                s_satir = df_siparis[df_siparis[ilk_kolon_adi] == secilen_inv].iloc[0].to_dict()
                
                with st.form("duzenleme_formu"):
                    st.markdown(f"**📄 Düzenlenen Sipariş:** {secilen_inv}")
                    
                    d_col1, d_col2 = st.columns(2)
                    with d_col1:
                        guncel_miktar = st.number_input("Miktar:", value=float(s_satir.get("Miktar", 0.0) or 0.0))
                        guncel_b_no = st.text_input("Beyanname No:", value=s_satir.get("Beyanname No", ""))
                    with d_col2:
                        guncel_vitsan = st.text_input("Vitsan Rapor No:", value=s_satir.get("Vitsan Rapor No", ""))
                        
                        # Tarih alanını güvenli pars etme
                        b_tar_obj = datetime.now().date()
                        if s_satir.get("Beyanname Tarihi"):
                            try: b_tar_obj = datetime.strptime(s_satir["Beyanname Tarihi"], "%d.%m.%Y").date()
                            except: pass
                        guncel_b_tarih = st.date_input("Beyanname Tescil Tarihi:", value=b_tar_obj)

                    # ⚓ Denizyolu ek alanları kontrolü
                    guncel_bl, guncel_kont = s_satir.get("B/L No", ""), s_satir.get("Konteyner No", "")
                    if s_satir.get("Taşıma Şekli") == "Deniz":
                        st.markdown("##### ⚓ Denizyolu Sevkiyat Güncelleme")
                        bl_c1, bl_c2 = st.columns(2)
                        with bl_c1: guncel_bl = st.text_input("B/L No:", value=s_satir.get("B/L No", ""))
                        with bl_c2: guncel_kont = st.text_input("Konteyner No:", value=s_satir.get("Konteyner No", ""))

                    st.markdown("##### 🏦 Finansal ve Operasyonel Durumlar")
                    f_c1, f_c2, f_c3 = st.columns(3)
                    with f_c1:
                        chk_ardiye = st.checkbox("Ardiye Ödendi", value=(s_satir.get("Ardiye Ödendi mi") == "Evet"))
                    with f_c2:
                        chk_depozito = st.checkbox("Depozito Ödendi", value=(s_satir.get("Depozito Ödendi mi") == "Evet"))
                    with f_c3:
                        chk_iade = st.checkbox("Depozito İade Edildi", value=(s_satir.get("Depozito İade Edildi mi") == "Evet"))
                    
                    # 🔴 BEYANNAME KAPATMA SEÇENEĞİ
                    eski_durum = s_satir.get("Beyanname Durumu", "Açık")
                    chk_kapanis = st.checkbox("🚨 BEYANNAME KAPANDI (Operasyonu Tamamla)", value=(eski_durum.lower() == "kapandı"))

                    submit_guncelle = st.form_submit_button("DEĞİŞİKLİKLERİ GOOGLE SHEETS'E KAYDET", use_container_width=True)
                    
                    if submit_guncelle:
                        v_tarih_guncel = (guncel_b_tarih + dt.timedelta(days=30)).strftime("%d.%m.%Y") if guncel_b_no else ""
                        yeni_durum_str = "Kapandı" if chk_kapanis else ("Açık" if guncel_b_no else "")
                        
                        guncel_paket = {
                            "Miktar": str(guncel_miktar),
                            "Beyanname No": guncel_b_no,
                            "Beyanname Tarihi": guncel_b_tarih.strftime("%d.%m.%Y") if guncel_b_no else "",
                            "Vergi Son Ödeme Tarihi": v_tarih_guncel,
                            "Vitsan Rapor No": guncel_vitsan,
                            "B/L No": guncel_bl,
                            "Konteyner No": guncel_kont,
                            "Ardiye Ödendi mi": "Evet" if chk_ardiye else "Hayır",
                            "Depozito Ödendi mi": "Evet" if chk_depozito else "Hayır",
                            "Depozito İade Edildi mi": "Evet" if chk_iade else "Hayır",
                            "Beyanname Durumu": yeni_durum_str
                        }
                        
                        if guncelle_mevcut_siparis(secilen_inv, guncel_paket):
                            # Eğer beyanname yeni kapandıysa loglara özel kayıt atalım
                            if chk_kapanis and eski_durum.lower() != "kapandı":
                                kaydet(
                                    islem_adi=f"INV: {secilen_inv} Kapandı",
                                    kategori="Operasyon Kapanış",
                                    girdiler=f"{secilen_inv} nolu sipariş arşive çekildi.",
                                    sonuc="siparişin tüm operasyonları tamamlandı",
                                    personel_adi=st.session_state.user_name,
                                    hedef_sheet=kayitlar_sheet
                                )
                            st.success("Veritabanı başarıyla güncellendi! Sayfa yenileniyor...")
                            st.rerun()

            st.divider()
            excel_sip = to_excel(df_siparis)
            st.download_button(label="Sipariş Listesini Excel'e Aktar (İndir)", data=excel_sip, file_name=f"Mavi_Kimya_Siparisler_{datetime.now().strftime('%d_%m_%Y')}.xlsx", use_container_width=True)
        else:
            st.info("Henüz kaydedilmiş bir sipariş operasyonu bulunmuyor.")

# --- SEÇENEK: HESAPLAMA ARAÇLARI ---
elif st.session_state.sayfa_yonetimi == "Hesaplama Araçları":
    st.markdown("### Hızlı Hesaplama ve Operasyon Araçları")
    islem = st.selectbox("Lütfen Yapmak İstediğiniz İşlemi Seçin:", ["Ardiye Hesaplama", "KG -> LT Çevirme", "LT -> KG Çevirme", "Yoğunluk Hesaplama", "Denatürasyon Hesaplama (Yeni Sipariş)", "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)"])

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
            res_c2.metric("Toplam Bedel", f"{toplam:.2f} $")

# --- SEÇENEK: HESAPLAMA ARŞİVİ ---
elif st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler":
    st.markdown("### Kaydedilen Hesaplama İşlemleri")
    data = load_data_cached("t_kayitlari")
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz kaydedilmiş bir işlem bulunmuyor.")

st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
