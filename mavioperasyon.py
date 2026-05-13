import streamlit as st
import base64
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image
import pandas as pd
from datetime import datetime
import os

# --- GOOGLE SHEETS BAĞLANTI AYARLARI ---
def get_gsheet_client():
    # Streamlit Secrets
    creds_dict = st.secrets["gcp_service_account"]
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

client = get_gsheet_client()
SHEET_NAME = "Mavioperasyon_Database"
spreadsheet = client.open(SHEET_NAME)

cari_sheet = spreadsheet.worksheet("cari_listesi")
urun_sheet = spreadsheet.worksheet("urun_listesi")
kayitlar_sheet = spreadsheet.worksheet("t_kayitlari")

# --- SESSION STATE BAŞLATMA ---
# Cari Listesi Yükleme
if "cari_listesi" not in st.session_state:
    # Google Sheets'ten tüm veriyi çek ve sözlüğe çevir
    st.session_state.cari_listesi = cari_sheet.get_all_records()

# Ürün Listesi Yükleme
if "urun_listesi" not in st.session_state:
    # Ürün listesini sütun olarak çek (ilk satır başlık olduğu için [1:] yapıyoruz)
    # Eğer sayfada sadece 'urun_adi' sütunu varsa col_values(1) yeterli
    st.session_state.urun_listesi = sorted(urun_sheet.col_values(1)[1:])

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "sayfa_yonetimi" not in st.session_state:
    st.session_state.sayfa_yonetimi = "Ana Sayfa"

# --- ŞİFRE VE KULLANICI EŞLEŞTİRMESİ ---
SIFRE_REHBERI = {
    "Mavi2026": "Batuhan",
    "ErcanMavi26": "Ercan",
    "MustiMavi26": "Mustafa"
}

# --- GİRİŞ PANELİ ---
kullanici_sheet = spreadsheet.worksheet("kullanicilar")

if not st.session_state.authenticated:
    with st.sidebar:
        st.markdown("### 🔐 Personel Girişi")
        giris_ad = st.text_input("Kullanıcı Adı:")
        sifre_giris = st.text_input("Şifre:", type="password")
        
        if st.button("Giriş Yap"):
            if giris_ad and sifre_giris: # Önce alanlar dolu mu diye bakıyoruz
                user_data = kullanici_sheet.get_all_records()
                # Kullanıcıyı bulalım
                user = next((item for item in user_data if str(item["kullanici_adi"]) == giris_ad and str(item["sifre"]) == sifre_giris), None)
                
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
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}** ({st.session_state.user_role})")
        st.divider()

        if st.button("Kayıtlı İşlemleri Görüntüle", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Kaydedilen İşlemler"
            st.rerun()
        
        if st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler":
            if st.button("Ana Menüye Dön", use_container_width=True):
                st.session_state.sayfa_yonetimi = "Ana Sayfa"
                st.rerun()

        if st.button("Yeni Sipariş Oluştur", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Yeni Sipariş"
            st.rerun()
        
        st.divider()
        if st.button("Güvenli Çıkış", type="primary", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user_name = ""
            st.session_state.user_role = ""
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Mavi Kimya | Operasyon Paneli",
    page_icon="logo.ico",
    layout="centered"
)

def kaydet(islem_adi, kategori, girdiler, sonuc, personel_adi):
    try:
        yeni_kayit_satiri = [
            islem_adi, 
            kategori, 
            girdiler, 
            sonuc, 
            datetime.now().strftime("%d.%m.%Y"), 
            datetime.now().strftime("%H:%M"), 
            personel_adi
        ]
        # Veriyi Google Sheets'e basıyoruz
        kayitlar_sheet.append_row(yeni_kayit_satiri)
        st.toast("Veri başarıyla iletildi! ✅")
    except Exception as e:
        st.error(f"Veri yazılamadı: {e}")
# --- LOGO VE GÖRSEL HAZIRLIK ---
def get_image_base64(file_path):
    with open(file_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


try:
    if os.path.exists("logo.png"):
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="data:image/x-icon;base64,{get_image_base64('logo.png')}" width="250">
            </div>
            """, unsafe_allow_html=True
        )
except:
    pass

st.markdown(
    """
    <div style="text-align: center;">
        <h1 style='color: #2596BE; margin-bottom: 0;'>MAVİ KİMYA</h1>
        <p style='color: #64748B; font-size: 1.1em;'>Operasyonel Analiz ve Hesaplama Paneli</p>
    </div>
    """, unsafe_allow_html=True
)
st.divider()


# --- YARDIMCI FONKSİYONLAR ---
def birim_duzenle(deger, ana_birim):
    if ana_birim.lower() == "gr" and deger >= 1000:
        return f"{deger / 1000:.2f} kg"
    return f"{deger:.2f} {ana_birim}"


def sonuc_karti_bas(durum, baslik, icerik_listesi):
    bg_renk = "#d1fae5" if "UYGUN" in durum else "#fee2e2"
    border_renk = "#059669" if "UYGUN" in durum else "#dc2626"
    yazi_renk = "#065f46" if "UYGUN" in durum else "#991b1b"
    
    tolerans_notu = ""
    if "UYGUN" in durum:
        tolerans_notu = f"""
        <div style='margin-top: 15px; border-top: 1px dashed {border_renk}; padding-top: 10px;'>
            <p style='color: {yazi_renk}; font-size: 0.75em; font-weight: bold; font-style: italic; margin: 0;'>
             Girilen değer +/- %10 yasal tolerans sınırları içerisindedir.
            </p>
        </div>
        """

    html = f"""
    <div style="background-color: {bg_renk}; padding: 20px; border-radius: 12px; border-left: 8px solid {border_renk}; margin-top: 20px;">
        <h3 style="color: {yazi_renk}; margin-top: 0;">{durum} - {baslik}</h3>
        <ul style="list-style-type: none; padding-left: 0;">
    """
    for item in icerik_listesi:
        html += f"<li style='color: #1f2937; margin-bottom: 5px;'><b>{item['label']}:</b> {item['value']}</li>"

    html += f"</ul>{tolerans_notu}</div>"
    st.markdown(html, unsafe_allow_html=True)


def to_excel(df):
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='log')
    processed_data = output.getvalue()
    return processed_data


# --- ANA MENÜ ---
islem = None
if st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler":
    islem = "Kaydedilen İşlemler"
    # Arşivdeyken en üste bir geri dönüş bilgisi
    st.info("Şu an Arşiv kayıtlarını görüntülüyorsunuz. Menüye dönmek için sol taraftaki 'Ana Menüye Dön' butonuna basabilirsiniz.")
    pass
elif st.session_state.sayfa_yonetimi == "Yeni Sipariş":
    st.markdown("### 🏛️ Sipariş ve Gümrük İşlemleri Yönetimi")

    
    
    # --- 1. TEMEL FİRMA VE İŞLEM BİLGİSİ ---
    st.subheader("🏢 Firma Bilgileri")
    
    firmalar = [c["cari_adi"] for c in st.session_state.cari_listesi]
    
    # Akıllı Arama ve Seçim Kutusu
    secilen_cari_adi = st.selectbox(
        "Cari Adı Ara / Seç:", 
        options=[""] + sorted(firmalar), 
        format_func=lambda x: "Firma seçmek için yazmaya başlayın..." if x == "" else x,
        key="akilli_cari_secim"
    )

    # Seçilen carinin detaylarını gösteren ERP tipi Alt Panel
    if secilen_cari_adi != "":
        cari_detay = next((item for item in st.session_state.cari_listesi if item["cari_adi"] == secilen_cari_adi), None)
        
        if cari_detay:
            tedarikci = secilen_cari_adi # Veritabanına kayıt
            
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

    # --- YENİ CARİ EKLEME (Expander içinde gizledik ki ekran kalabalık olmasın) ---
    with st.expander("➕ Yeni Cari Kaydet"):
        y_cari = st.text_input("Yeni Cari Adı:", key="y_cari_input")
        y_adres = st.text_area("Cari Adresi:", key="y_cari_adres")
        if st.button("Cariyi Rehbere İşle", use_container_width=True):
            if y_cari and y_adres:
                yeni_satir = [y_cari, y_adres]
                # Google Sheets'e yeni satır ekle
                cari_sheet.append_row(yeni_satir) 
        
                # Session state'i tazele (ekrandaki liste de güncellensin)
                st.session_state.cari_listesi = cari_sheet.get_all_records()
                st.success(f"{y_cari} Google Sheets'e kaydedildi!")
                st.rerun()
    st.divider()

    col_islem1, col_islem2 = st.columns(2)
    with col_islem1:
        islem_ana_tipi = st.selectbox("İşlem Türü:", ["İthalat", "İhracat"], key="islem_ana_tip")

    # --- 2. DETAYLI İŞLEM TİPİ SEÇİMİ ---
    with col_islem2:
        if islem_ana_tipi == "İthalat":
            islem_sekli = st.selectbox("İthalat Şekli:", ["Kesin İthalat", "Devir (Antrepo)", "Geçici İthalat"])
            beyanname_var_mi = st.checkbox("Beyannamesi Var mı?")
        else:
            islem_sekli = st.selectbox("İhracat Şekli:", ["İhracat", "Transit Ticaret", "Devir"])
            beyanname_var_mi = False # İhracat için şimdilik kapalı tutalım dedin

    # --- 3. BEYANNAME ALANI (SADECE SEÇİLİRSE AÇILIR) ---
    if beyanname_var_mi:
        st.info("📑 Beyanname Detayları")
        b_col1, b_col2, b_col3 = st.columns(3)
        with b_col1:
            beyanname_no = st.text_input("Beyanname No:", placeholder="Örn: 2606...")
        with b_col2:
            rejim = st.selectbox("Beyanname Rejimi:", ["40 71 (Antrepodan İthalat)", "71 71 (Antrepodan Antrepoya)", "71 00 (Özet Beyan Giriş)", "10 00 (Kesin İhracat)"])
        with b_col3:
            kapanis_tarihi = st.date_input("Beyanname Kapanış Tarihi")
            # --- 30 GÜN SAYMA MANTIĞI ---
            import datetime
            vade_tarihi = kapanis_tarihi + datetime.timedelta(days=30)
            st.warning(f"🏦 Vergi Son Ödeme Tarihi: {vade_tarihi.strftime('%d.%m.%Y')}")

    # --- 4. ÜRÜN VE LOJİSTİK (HER İKİ DURUMDA DA GÖZÜKECEK) ---
    st.divider()
    st.markdown("#### 📦 Ürün ve Sevkiyat Detayları")
    

    col_u1, col_u2 = st.columns([3, 1])
    with col_u2:
        yeni_urun_check = st.checkbox("Yeni Ürün")
    with col_u1:
        if yeni_urun_check:
            urun_adi = st.text_input("Ürün Adını Ekleyin:", key="yeni_urun_input")
            if st.button("Listeye Ekle"):
                if urun_adi and urun_adi not in st.session_state.urun_listesi:
                    # Google Sheets'e ekle
                    urun_sheet.append_row([urun_adi])
        
                    # Session state'i güncelle
                    st.session_state.urun_listesi.append(urun_adi)
                    st.session_state.urun_listesi.sort()
                    st.success(f"{urun_adi} ürün listesine eklendi!")
                    st.rerun()
        else:
            urun_secimi = st.selectbox("Ürün Seçiniz:", st.session_state.urun_listesi)

    # --- 5. TAŞIMA VE LİMAN ---
    incoterm_aktif = st.checkbox("Siparişte Incoterm belirtmek istiyorum", value=True, key="inc_chk_top")
    st.divider()
    col_t1, col_t2, col_t3 = st.columns(3)
# 1. TAŞIMA ŞEKLİ (Sadece ithalat ve ihracatta gözükür, devirlerde gizlenir)
    devir_mi = "Devir" in islem_sekli
    tasima_sekli = None
    
    with col_t1:
        if not devir_mi:
            tasima_sekli = st.selectbox("Taşıma Şekli:", ["Deniz", "Kara", "Hava", "Demiryolu"], key="siparis_tasima")
        else:
            st.info("Devir işleminde taşıma şekli sorulmaz.")

    # 2. INCOTERM (Checkbox ile kilit açma/kapama)
    
    with col_t2:
        if incoterm_aktif:
            incoterm = st.selectbox("Incoterm / Teslim Şekli", ["EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"], key="sip_inc")
        else:
            st.text_input("Incoterm", value="Belirtilmedi", disabled=True, key="inc_dis")
            incoterm = ""

    # 3. LİMAN / GÜMRÜK (Taşıma şekline göre değişen liste)
    with col_t3:
        if devir_mi:
            liman = st.selectbox("İşlem Yapılan Gümrük:", ["Erenköy Gümrük", "Muratbey Gümrük", "Ambarlı Gümrük"], key="devir_gumruk")
        elif tasima_sekli == "Kara":
            # Kara seçildiyse kara gümrükleri
            liman = st.selectbox("Kara Gümrüğü:", ["Muratbey", "Erenköy", "Dereköy", "Çerkezköy", "Kapıkule"], key="kara_gumruk")
        elif tasima_sekli == "Deniz":
            # Deniz seçildiyse limanlar
            liman = st.selectbox("Liman/Gümrük:", ["Ambarlı", "Körfez", "Derince", "Zeytinburnu", "Mersin", "İzmir"], key="deniz_liman")
            #Demiryolu seçildiyse garlar
        elif tasima_sekli == "Demiryolu":
            liman = st.selectbox("Gar gümrüğü:", ["Halkalı", "Küçükçekmece", "Çerkezköy", "Lüleburgaz"], key="demiryolu_gar")
        else:
            liman = st.text_input("Gümrük/Liman:", value="HAVA/DİĞER", key="diger_liman_input")

    # --- 6. MİKTAR VE TUTAR ---
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        miktar = st.number_input("Miktar:", min_value=0.0)
        birim = st.radio("Birim:", ["KG", "LT"], horizontal=True)
    with col_f2:
        toplam_tutar = st.number_input("Toplam Fatura Tutarı ($):", min_value=0.0)

    # --- 7. KAYIT ---
    if st.button("KAYDET", use_container_width=True):
        # Burada her şeyi CSV'ye kaydedeceğiz kanka
        st.success("Kayıt başarıyla oluşturuldu. Dashboard'da analiz edilmeye hazır!")
else:
    islem = st.selectbox(
        "📂 MENÜ",
        [
            "Ardiye Hesaplama",
            "KG -> LT Çevirme",
            "LT -> KG Çevirme",
            "Yoğunluk Hesaplama",
            "Denatürasyon Hesaplama (Yeni Sipariş)",
            "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)"
        ]
    )

# --- İŞLEM MANTIKLARI ---
if islem == "Ardiye Hesaplama":
    antrepo = st.radio("Antrepo Seçin:", ["İzgin Antrepo", "Koruma Antrepo"], horizontal=True)
    giris_tipi = st.segmented_control("Hesaplama Bazı:", ["Kilogram (KG)", "Litre (LT)"], default="Kilogram (KG)")
    
    col1, col2 = st.columns(2)
    
    # Değişkenlerin başlangıç değerleri
    hacim_lt = 0.0
    kg_input = 0.0
    lt_input = 0.0
    d_input = 0.8124

    if giris_tipi == "Kilogram (KG)":
        with col1:
            kg_input = st.number_input("Net Miktar (KG)", min_value=0.0, step=100.0)
        with col2:
            d_input = st.number_input("Yoğunluk (Density)", min_value=0.01, value=0.8124, format="%.4f")
        hacim_lt = kg_input / d_input if d_input > 0 else 0
    else:
        with col1:
            lt_input = st.number_input("Toplam Hacim (Litre)", min_value=0.0, step=100.0)
            hacim_lt = lt_input
        with col2:
            st.number_input("Yoğunluk (Density)", value=0.00, format="%.4f", disabled=True)

    if st.button("HESAPLA", use_container_width=True):
        m3 = hacim_lt / 1000
        carpan = 13 if antrepo == "İzgin Antrepo" else 9
        toplam = m3 * carpan

        st.markdown("### 📊 İşlem Sonucu")
        res_c1, res_c2 = st.columns(2)
        res_c1.metric("Toplam Hacim", f"{m3:.3f} m³")
        res_c2.metric("Toplam Bedel", f"{toplam:.2f} $", delta=f"{antrepo} Tarifesi")

        #---KAYIT BÖLÜMÜ---
        if giris_tipi == "Kilogram (KG)":
            girdi_notu = f"{kg_input} KG"
        else:
            girdi_notu = f"{lt_input} LT"

        st.session_state.son_hesaplama = {
            "kategori": "Ardiye Hesaplama",
            "girdi": girdi_notu,
            "sonuc": f"{m3:.3f} m³ / {toplam:.2f} $"
        }

    # Kayıt Formu Yerleşimi
    if "son_hesaplama" in st.session_state and islem == "Ardiye Hesaplama":
        st.divider()
        with st.expander("💾 Bu İşlemi Arşive Kaydet"):
            # Form kullanarak girişleri paketliyoruz
            with st.form("kayit_formu", clear_on_submit=True):
                kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: 10 Araç Metanol")
                submit_button = st.form_submit_button("KAYDI ONAYLA", use_container_width=True)

                if submit_button:
                    if not st.session_state.authenticated:
                        st.error("❌ Yetkisiz İşlem! Önce giriş yapın.")
                    elif not kayit_ismi:
                        st.warning("⚠️ Lütfen işlem için bir isim giriniz.")
                    else:
                        # Veriyi çek
                        data = st.session_state.son_hesaplama
                        
                        # Google Sheets'e yazma işlemi
                        # Buraya bir 'wait' iconu ekleyelim ki gittiğini anlayalım
                        with st.status("Veri buluta işleniyor...", expanded=False) as status:
                            kaydet(
                                kayit_ismi, 
                                data['kategori'], 
                                data['girdi'], 
                                data['sonuc'], 
                                st.session_state.user_name
                            )
                            status.update(label="Kayıt Başarılı!", state="complete", expanded=False)
                        
                        st.success(f"İşlem {st.session_state.user_name} adına kaydedildi!")
                        
                        # Temizlik
                        del st.session_state.son_hesaplama
                        # Rerun yapmadan önce verinin gittiğinden emin olmak için kısa bir bekletme
                        st.balloons()
                        # st.rerun() # Form içinde rerun bazen sorun çıkarabilir, gerekirse açarsın

elif islem and "Çevirme" in islem:
    col1, col2 = st.columns(2)
    with col1:
        miktar = st.number_input("Miktar", min_value=0.0)
    with col2:
        d = st.number_input("Yoğunluk", min_value=0.01, value=0.7930, format="%.4f")

    if st.button("HIZLI ÇEVİR", use_container_width=True):
        sonuc = miktar / d if "KG -> LT" in islem else miktar * d
        birim = "LT" if "KG -> LT" in islem else "KG"
        st.metric(label="Dönüştürülen Miktar", value=f"{sonuc:.2f} {birim}")

elif islem == "Yoğunluk Hesaplama":
    col1, col2 = st.columns(2)
    with col1:
        kg_deger = st.number_input("Toplam Ağırlık (KG)", min_value=0.0, step=1.0)
    with col2:
        lt_deger = st.number_input("Toplam Hacim (LT)", min_value=0.01, step=1.0)

    if st.button("YOĞUNLUĞU HESAPLA", use_container_width=True):
        if lt_deger > 0:
            yogunluk = kg_deger / lt_deger
            st.markdown("---")
            st.metric(label="Hesaplanan Yoğunluk (g/cm³)", value=f"{yogunluk:.4f}")
            
            if 0.70 <= yogunluk <= 1.20:
                st.success(f"ℹ️ Standart sıvı kimyasal aralığında bir değer tespit edildi.")
            else:
                st.warning(f"⚠️ Dikkat: Bu yoğunluk değeri alışılmışın dışında (Çok ağır veya çok hafif).")
        else:
            st.error("Hacim (LT) değeri 0 olamaz!")

elif islem == "Denatürasyon Hesaplama (Yeni Sipariş)":
    tip = st.selectbox("Reçete Tipi:", ["K Tipi", "D Tipi", "Metanol Denatürasyonu"])
    miktar = st.number_input("Saf Ürün Hacmi (LT):", min_value=0.0)

    detay = ""

    if st.button("REÇETEYİ HAZIRLA", use_container_width=True):
        carpan = miktar / 100
        st.markdown("### 📝 Hazırlanacak Reçete")
        if tip == "K Tipi":
            detay = f"D. Benzoat: {0.8 * carpan:.2f} gr | TBA: {78 * carpan:.2f} gr"
        elif tip == "D Tipi":
            detay = f"IPA: {5 * carpan:.2f} kg | TBA: {78 * carpan:.2f} gr"
        else:
            detay = f"D. Benzoat: {3 * carpan:.2f} gr"

        st.warning(detay)

        # --- KAYIT HAZIRLIĞI ---
        st.session_state.son_hesaplama = {
            "kategori": "Denatürasyon Hesabı",
            "girdi": f"{miktar} LT {tip}",
            "sonuc": detay
        }

    # KAYIT FORMU
    if "son_hesaplama" in st.session_state and islem == "Denatürasyon Hesaplama (Yeni Sipariş)":
        st.divider()
        with st.expander("💾 Bu Reçeteyi Arşive Kaydet"):
            kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: Farmed 20 Tonluk Tank Hazırlığı")
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            with btn_col2:
                if st.button("REÇETEYİ ONAYLA", use_container_width=True):
                    if not st.session_state.authenticated:
                        st.error("❌ Yetkisiz İşlem! Lütfen önce giriş yapınız.")
                    else:
                        if kayit_ismi:
                            data = st.session_state.son_hesaplama
                            kaydet(
                                kayit_ismi, 
                                data['kategori'], 
                                data['girdi'], 
                                data['sonuc'], 
                                st.session_state.user_name
                            )
                            st.success(f"Reçete {st.session_state.user_name} adına kaydedildi!")
                            del st.session_state.son_hesaplama
                            st.rerun()
                        else:
                            st.warning("Lütfen bir isim giriniz.")

elif islem == "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)":
    tip = st.selectbox("Kontrol Edilecek Ürün:", ["K Tipi", "D Tipi", "Metanol"])
    toplam_h = st.number_input("Toplam Karışım Hacmi (LT)", min_value=0.0)
    carpan = toplam_h / 100

    if "K Tipi" in tip:
        db = st.number_input("Eklenen D. Benzoat (gr)", min_value=0.0)
        tba = st.number_input("Eklenen TBA (gr)", min_value=0.0)
        if st.button("UYGUNLUK DENETLE", use_container_width=True):
            # Analizler
            db_res = (toplam_h / 100) * 0.8
            tba_res = (toplam_h / 100) * 78

            # DB Kartı
            db_durum = "UYGUN ✅" if abs(db - db_res) <= (db_res * 0.1) else "HATALI ❌"
            sonuc_karti_bas(db_durum, "Denatonyum Benzoat", [
                {"label": "Gereken", "value": f"{db_res:.2f} gr"},
                {"label": "Girdiğiniz", "value": f"{db:.2f} gr"}
            ])
            # TBA Kartı
            tba_durum = "UYGUN ✅" if abs(tba - tba_res) <= (tba_res * 0.1) else "HATALI ❌"
            sonuc_karti_bas(tba_durum, "Tersiyer Butanol", [
                {"label": "Gereken", "value": f"{tba_res:.2f} gr"},
                {"label": "Girdiğiniz", "value": f"{tba:.2f} gr"}
            ])

elif islem == "Kaydedilen İşlemler":
    if not st.session_state.authenticated:
        st.error("🚫 Bu alanı görüntülemek için yetkiniz yok. Lütfen sol panelden giriş yapınız.")
    else:
        st.markdown("### 📜 Kaydedilen İşlemler")
        # Sayfadaki tüm verileri çek ve DataFrame yap
        data = kayitlar_sheet.get_all_records()
        if data:
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True)
            # Excel indirme butonu aynı kalabilir, df'i zaten yukarıda oluşturduk.
                    # --- BUTON YERLEŞİMLERİ ---

            col_ex1, col_ex2 = st.columns([1, 1])
            
            with col_ex1:
                excel_data = to_excel(df)
                st.download_button(
                    label="📥 Excel'e Aktar (İndir)",
                    data=excel_data,
                    file_name=f"Mavi_Kimya_Arsiv_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            
            with col_ex2:
                if st.session_state.get("user_role") == "admin":
                    if st.button("🔴 Arşivi Temizle", use_container_width=True):
                        os.remove(DB_FILE)
                        st.warning("Arşiv başarıyla temizlendi.")
                        st.rerun()
                else:
                    st.warning("⚠️ Arşivi temizleme yetkiniz bulunmamaktadır. Lütfen yönetici ile görüşün.")
        else:
            st.info("Henüz kaydedilmiş bir işlem bulunmuyor.")



st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
