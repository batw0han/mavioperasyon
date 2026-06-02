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

# --- 🔒 GÜVENLİK FİLTRESİ VE SAYFA YÖNLENDİRME ---
# Kullanıcı giriş yapmadıysa ne seçerse seçsin sistem "Hesaplama Araçları" sayfasına kilitlenir!
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
        st.info("ℹ️ Giriş yapmadan sadece sağ taraftaki hesaplama araçlarını kullanabilirsiniz. Sipariş ve gümrük yönetimi için giriş yapınız.")
    else:
        st.info(f"Aktif Kullanıcı: **{st.session_state.user_name}**")
        st.divider()

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
            st.session_state.init_done = False
            st.session_state.sayfa_yonetimi = "Hesaplama Araçları"
            st.rerun()

# --- VERİTABANI YAZMA VE GÜNCELLEME FONKSİYONLARI ---
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
        id_index = 0
        
        row_num = -1
        for i, r in enumerate(all_rows):
            if len(r) > 0 and r[id_index] == invoice_no:
                row_num = i + 1
                break
                
        if row_num != -1:
            for key, val in guncel_data_dict.items():
                eslesen_header = next((h for h in headers if h.lower().strip() == key.lower().strip()), None)
                if eslesen_header:
                    col_num = headers.index(eslesen_header) + 1
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

# --- LOGO VE BAŞLIK ---
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

# --- 🧮 1. SEÇENEK: HESAPLAMA ARAÇLARI (💡 HIERARSIDE EN USTE ALINDI - GİRİŞSİZ AÇIK) ---
if st.session_state.sayfa_yonetimi == "Hesaplama Araçları":
    st.markdown("### Hesaplama Araçları")
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
            with col2: st.number_input("Yoğunluk (Density)", value=0.00, format="%.4f", disabled=True)

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
                st.warning("🔒 Bu hesaplamayı arşive kalıcı olarak kaydetmek için lütfen sol panelden giriş yapınız.")
            else:
                with st.expander("Bu İşlemi Arşive Kaydet"):
                    with st.form("kayit_formu", clear_on_submit=True):
                        kayit_ismi = st.text_input("İşlem adı:", placeholder="Örn: 10 Araç Metanol")
                        submit_button = st.form_submit_button("KAYDI ONAYLA", use_container_width=True)

                        if submit_button:
                            if not kayit_ismi: st.warning("⚠️ Lütfen işlem için bir isim giriniz.")
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
                st.warning("🔒 Bu reçeteyi bulut arşına kaydetmek için lütfen sol panelden giriş yapınız.")
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

# --- 📊 2. SEÇENEK: ANA SAYFA (DASHBOARD - YALNIZCA GİRİŞLİ PERSONEL GÖRÜR) ---
elif st.session_state.sayfa_yonetimi == "Ana Sayfa" and st.session_state.authenticated:
    st.markdown("### Genel Özet")
    st.caption("Şirket genel operasyonel durumunu gösteren ana kontrol merkezi.")
    
    siparis_listesi = load_data_cached("p_kayitlari")
    df_siparisler = pd.DataFrame(siparis_listesi) if siparis_listesi else pd.DataFrame()
    
    acik_beyanname_sayisi = 0
    kritik_beyannameler = []
    
    if not df_siparisler.empty:
        durum_col = next((c for c in df_siparisler.columns if "durum" in c.lower()), None)
        vade_col = next((c for c in df_siparisler.columns if "vergi" in c.lower() or "vade" in c.lower()), None)
        inv_col = df_siparisler.columns[0]
        b_no_col = next((c for c in df_siparisler.columns if "beyanname no" in c.lower()), None)
        
        if durum_col:
            acik_beyanname_sayisi = len(df_siparisler[df_siparisler[durum_col].str.lower().str.strip() == "açık"])
            
        if vade_col and durum_col:
            bugun = datetime.now().date()
            for idx, row in df_siparisler.iterrows():
                if str(row[durum_col]).lower().strip() == "açık" and row[vade_col]:
                    try:
                        vade_tarihi = datetime.strptime(str(row[vade_col]).strip(), "%d.%m.%Y").date()
                        kalan_gun = (vade_tarihi - bugun).days
                        if kalan_gun <= 7:
                            kritik_beyannameler.append({
                                "Sipariş / Invoice": row[inv_col],
                                "Beyanname No": row[b_no_col] if b_no_col else "-",
                                "Son Ödeme Tarihi": row[vade_col],
                                "Durum": f"{kalan_gun} Gün Kaldı" if kalan_gun >= 0 else f"SÜRESİ GEÇMİŞ ({abs(kalan_gun)} Gün)"
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
    
    if kritik_beyannameler:
        st.markdown("<h4 style='color: #EF4444;'>⚠️ Vergi Son Ödeme Günü Yaklaşan Beyannameler</h4>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(kritik_beyannameler), use_container_width=True, hide_index=True)
    else:
        st.success("✅ Önümüzdeki 7 gün içinde ödeme vadesi dolan açık beyanname bulunmuyor.")

# --- 🛒 3. SEÇENEK: YENİ SİPARİŞ OLUŞTURMA ---
elif st.session_state.sayfa_yonetimi == "Yeni Sipariş" and st.session_state.authenticated:
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
        islem_sekli = st.selectbox("İşlem Şli:", ["Kesin İthalat", "Devir (Antrepo)", "Geçici İthalat"] if islem_ana_tipi == "İthalat" else ["İhracat", "Transit Ticaret", "Devir"])
        beyanname_var_mi = st.checkbox("Beyannamesi Var mı?") if islem_ana_tipi == "İthalat" else False

    col_alt1, col_alt2 = st.columns(2)
    with col_alt1:
        fatura_tarihi = st.date_input("Fatura Tarihi:", value=datetime.now())
    with col_alt2:
        invoice_no = st.text_input("Invoice No:", placeholder="Örn: MAVI-2026-001")

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

# --- 📦 4. SEÇENEK: SİPARİŞ LİSTELEME VE DÜZENLEME ---
elif st.session_state.sayfa_yonetimi == "Kayıtlı Siparişler" and st.session_state.authenticated:
    st.markdown("### Kayıtlı Sipariş Takip Otomasyonu")
    st.caption("Yeni Sipariş ekranından girilen tüm gerçek operasyon kayıtları burada listelenir.")
    
    siparis_data = load_data_cached("p_kayitlari")
    if siparis_data:
        df_siparis = pd.DataFrame(siparis_data)
        st.dataframe(df_siparis, use_container_width=True, hide_index=True)
        
        st.divider()
        st.markdown("#### 🔄 Sipariş Detaylarını Düzenle ve Güncelle")
        
        ilk_kolon_adi = df_siparis.columns[0] 
        inv_listesi = df_siparis[ilk_kolon_adi].unique().tolist()
        secilen_inv = st.selectbox("Düzenlemek İstediğiniz Siparişi Seçin (Invoice No):", options=[""] + inv_listesi)
        
        if secilen_inv:
            s_satir = df_siparis[df_siparis[ilk_kolon_adi] == secilen_inv].iloc[0].to_dict()
            
            with st.form("duzenleme_formu"):
                st.markdown(f"**📄 Düzenlenen Sipariş:** {secilen_inv}")
                
                miktar_anahtari = next((k for k in s_satir.keys() if k.lower().strip() == "miktar"), "Miktar")
                ham_miktar_verisi = s_satir.get(miktar_anahtari, 0.0)
                
                try: varsayilan_miktar = float(str(ham_miktar_verisi).replace(",", ".").strip() or 0.0)
                except ValueError: varsayilan_miktar = 0.0
                
                d_col1, d_col2 = st.columns(2)
                with d_col1:
                    guncel_miktar = st.number_input("Miktar:", value=varsayilan_miktar)
                    b_no_key = next((k for k in s_satir.keys() if "beyanname no" in k.lower()), "Beyanname No")
                    guncel_b_no = st.text_input("Beyanname No:", value=s_satir.get(b_no_key, ""))
                with d_col2:
                    vitsan_key = next((k for k in s_satir.keys() if "vitsan" in k.lower()), "Vitsan Rapor No")
                    guncel_vitsan = st.text_input("Vitsan Rapor No:", value=s_satir.get(vitsan_key, ""))
                    
                    b_tarih_key = next((k for k in s_satir.keys() if "beyanname tarih" in k.lower()), "Beyanname Tarihi")
                    b_tar_obj = datetime.now().date()
                    if s_satir.get(b_tarih_key):
                        try: b_tar_obj = datetime.strptime(str(s_satir[b_tarih_key]).strip(), "%d.%m.%Y").date()
                        except: pass
                    guncel_b_tarih = st.date_input("Beyanname Tescil Tarihi:", value=b_tar_obj)

                tasima_key = next((k for k in s_satir.keys() if "taşıma" in k.lower() or "tasima" in k.lower()), "Taşıma Şekli")
                guncel_bl, guncel_kont = "", ""
                if str(s_satir.get(tasima_key)).lower().strip() == "deniz":
                    st.markdown("##### ⚓ Denizyolu Sevkiyat Güncelleme")
                    bl_c1, bl_c2 = st.columns(2)
                    bl_key = next((k for k in s_satir.keys() if "b/l" in k.lower()), "B/L No")
                    kont_key = next((k for k in s_satir.keys() if "konteyner" in k.lower()), "Konteyner No")
                    with bl_c1: guncel_bl = st.text_input("B/L No:", value=s_satir.get(bl_key, ""))
                    with bl_c2: guncel_kont = st.text_input("Konteyner No:", value=s_satir.get(kont_key, ""))

                st.markdown("##### 🏦 Finansal ve Operasyonel Durumlar")
                f_c1, f_c2, f_c3 = st.columns(3)
                
                ardiye_key = next((k for k in s_satir.keys() if "ardiye" in k.lower()), "Ardiye Ödendi mi")
                depozito_key = next((k for k in s_satir.keys() if "depozito ödendi" in k.lower()), "Depozito Ödendi mi")
                iade_key = next((k for k in s_satir.keys() if "iade" in k.lower()), "Depozito İade Edildi mi")
                durum_key = next((k for k in s_satir.keys() if "durum" in k.lower()), "Beyanname Durumu")
                
                with f_c1: chk_ardiye = st.checkbox("Ardiye Ödendi", value=(str(s_satir.get(ardiye_key)).strip().lower() == "evet"))
                with f_c2: chk_depozito = st.checkbox("Depozito Ödendi", value=(str(s_satir.get(depozito_key)).strip().lower() == "evet"))
                with f_c3: chk_iade = st.checkbox("Depozito İade Edildi", value=(str(s_satir.get(iade_key)).strip().lower() == "evet"))
                
                eski_durum = str(s_satir.get(durum_key, "Açık")).strip()
                chk_kapanis = st.checkbox("🚨 BEYANNAME KAPANDI (Operasyonu Tamamla)", value=(eski_durum.lower() == "kapandı"))

                st.form_submit_button("DEĞİŞİKLİKLERİ GOOGLE SHEETS'E KAYDET", use_container_width=True)
                
                if st.session_state.get("FormSubmitter:duzenleme_formu-DEĞİŞİKLİKLERİ GOOGLE SHEETS'E KAYDET"):
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
                        if chk_kapanis and eski_durum.lower() != "kapandı":
                            kaydet(
                                islem_adi=f"INV: {secilen_inv} Kapandı",
                                kategori="Operasyon Kapanış",
                                girdiler=f"{secilen_inv} nolu sipariş arşive çekildi.",
                                sonuc=f"siparişin tüm operasyonları tamamlandı",
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

# --- 📜 5. SEÇENEK: HESAPLAMA ARŞİVİ ---
elif st.session_state.sayfa_yonetimi == "Kaydedilen İşlemler" and st.session_state.authenticated:
    st.markdown("### Kaydedilen Hesaplama İşlemleri")
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
