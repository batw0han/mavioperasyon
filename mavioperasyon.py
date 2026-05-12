import streamlit as st
import base64
from PIL import Image
import pandas as pd
from datetime import datetime
import os

# --- SESSION STATE BAŞLATMA ---
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
with st.sidebar:
    st.markdown("### 🔐 Personel Girişi")
    if not st.session_state.authenticated:
        sifre_giris = st.text_input("Giriş Şifresi:", type="password") 
        
        if st.button("Giriş Yap"):
            if sifre_giris:
                if sifre_giris in SIFRE_REHBERI:
                    st.session_state.authenticated = True
                    st.session_state.user_name = SIFRE_REHBERI[sifre_giris]
                    st.success(f"Hoş geldin, {st.session_state.user_name}!")
                    st.rerun()
                else:
                    st.error("Hatalı veya Geçersiz Şifre!")
            else:
                st.warning("Lütfen şifrenizi giriniz.")
    else:
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}**")
        st.divider()

        if st.sidebar.button("Kayıtlı İşlemleri Görüntüle", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Kaydedilen İşlemler"
            st.rerun()
        
        if st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler":
            if st.sidebar.button("Ana Menüye Dön", use_container_width=True):
                st.session_state.sayfa_yonetimi = "Ana Sayfa"
                st.rerun()

        if st.sidebar.button("Yeni Sipariş Oluştur", use_container_width=True):
            st.session_state.sayfa_yonetimi = "Yeni Sipariş"
            st.rerun()
        
        if st.button("Güvenli Çıkış"):
            st.session_state.authenticated = False
            st.session_state.user_name = ""
            st.session_state.sayfa_yonetimi = "Ana Sayfa"
            st.rerun()

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Mavi Kimya | Operasyon Paneli",
    page_icon="logo.ico",
    layout="centered"
)

DB_FILE = "operasyon_kayitlari.csv"

def kaydet(islem_adi, kategori, girdiler, sonuc, personel_adi):
    yeni_kayit = {
        "Kaydedilen Ad": islem_adi,
        "İşlem Kategorisi": kategori,
        "Girdiler": girdiler,
        "Sonuç": sonuc,
        "Tarih": datetime.now().strftime("%d.%m.%Y"),
        "Saat": datetime.now().strftime("%H:%M"),
        "İşlemi Yapan": personel_adi
    }
    
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        df = pd.concat([df, pd.DataFrame([yeni_kayit])], ignore_index=True)
    else:
        df = pd.DataFrame([yeni_kayit])
    
    df.to_csv(DB_FILE, index=False)

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
    col1, col2 = st.columns(2)
    with col1:
        tedarikci = st.text_input("Satın Alınan / Satış Yapılan Firma:")
    with col2:
        islem_ana_tipi = st.selectbox("İşlem Türü:", ["İthalat", "İhracat"])

    # --- 2. DETAYLI İŞLEM TİPİ SEÇİMİ ---
    st.divider()
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
    
    # Ürün listesi (önceki koddan gelen session_state kullanılıyor)
    if "urun_listesi" not in st.session_state:
        st.session_state.urun_listesi = ["Metanol", "Etil Asetat", "Glikol"]

    col_u1, col_u2 = st.columns([3, 1])
    with col_u2:
        yeni_urun_check = st.checkbox("Yeni Ürün")
    with col_u1:
        if yeni_urun_check:
            urun_adi = st.text_input("Ürün Adını Ekleyin:")
            if st.button("Listeye Ekle"):
                st.session_state.urun_listesi.append(urun_adi)
                st.rerun()
        else:
            urun_secimi = st.selectbox("Ürün Seçiniz:", st.session_state.urun_listesi)

    # --- 5. TAŞIMA VE LİMAN ---
    col_t1, col_t2, col_t3 = st.columns(3)
    with col_t1:
        tasima_sekli = st.selectbox("Taşıma Şekli:", ["Deniz", "Kara", "Hava"])
    with col_t2:
        incoterm = st.selectbox("Incoterm:", ["EXW", "FCA", "FOB", "CFR", "CIF", "DAP", "DDP"])
    with col_t3:
        liman = st.selectbox("Liman/Gümrük:", ["Ambarlı", "Körfez", "Derince", "Zeytinburnu", "Mersin", "İzmir"])

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
            kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: 10 Araç Metanol")
            btn_col1, btn_col2, btn_col3 = st.columns([1, 2, 1])
            with btn_col2:
                if st.button("KAYDI ONAYLA", use_container_width=True):
                    if not st.session_state.authenticated:
                        st.error("❌ Yetkisiz İşlem! Lütfen önce personel şifrenizle giriş yapınız.")
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
                            st.success(f"İşlem {st.session_state.user_name} adına başarıyla kaydedildi!")
                            del st.session_state.son_hesaplama
                            st.rerun()
                        else:
                            st.warning("Lütfen işlem için bir isim giriniz.")

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
        if os.path.exists(DB_FILE):
            df = pd.read_csv(DB_FILE)
            st.dataframe(df, use_container_width=True)

            st.divider()

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
                if st.button("🔴 Arşivi Temizle", use_container_width=True):
                    os.remove(DB_FILE)
                    st.warning("Arşiv başarıyla temizlendi.")
                    st.rerun()
        else:
            st.info("Henüz kaydedilmiş bir işlem bulunmuyor.")

st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
