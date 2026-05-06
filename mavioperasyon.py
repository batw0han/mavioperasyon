import streamlit as st
import base64
from PIL import Image
import os

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Mavi Kimya | Operasyon Paneli",
    page_icon="logo.ico",
    layout="centered"
)


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


# --- ANA MENÜ ---
islem = st.selectbox(
    "YAPILACAK İŞLEM SEÇİNİZ:",
    [
        "Ardiye Hesaplama",
        "KG -> LT Çevirme",
        "LT -> KG Çevirme",
        "Denatürasyon Hesaplama (Yeni Sipariş)",
        "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)"
    ]
)

# --- İŞLEM MANTIKLARI ---
if islem == "Ardiye Hesaplama":
    antrepo = st.radio("Antrepo Seçin:", ["İzgin Antrepo", "Koruma Antrepo"], horizontal=True)
    # LT VEYA KG. SEÇİMİ:
    giris_tipi = st.segmented_control("Hesaplama Bazı:", ["Kilogram (KG)", "Litre (LT)"], default="Kilogram (KG)")
    col1, col2 = st.columns(2)
    hacim_lt = 0.0
    if giris_tipi == "Kilogram (KG)":
        with col1:
            kg = st.number_input("Net Miktar (KG)", min_value=0.0, step=100.0)
        with col2:
            d = st.number_input("Yoğunluk (Density)", min_value=0.01, value=0.8124, format="%.4f")
        hacim_lt = kg / d if d > 0 else 0
    else:
        with col1:
            hacim_lt = st.number_input("Toplam Hacim (Litre)", min_value=0.0, step=100.0)
        # Litre seçilirse yoğunluğa gerek kalmıyor, col2 boş kalabilir veya bilgi notu yazılabilir.
        with col2:
            st.number_input("Yoğunluk (Density)", min_value=0.00, value=0.00, format="%.4f", disabled=True, help="Litre girişinde yoğunluk hesaplamaya dahil edilmez.")

    if st.button("HESAPLA", use_container_width=True):
        m3 = hacim_lt / 1000
        carpan = 13 if antrepo == "İzgin Antrepo" else 9
        toplam = m3 * carpan

        st.markdown("### 📊 İşlem Sonucu")
        c1, c2 = st.columns(2)
        c1.metric("Toplam Hacim", f"{m3:.3f} m³")
        c2.metric("Toplam Bedel", f"{toplam:.2f} $", delta=f"{antrepo} Tarifesi")

elif "Çevirme" in islem:
    col1, col2 = st.columns(2)
    with col1:
        miktar = st.number_input("Miktar", min_value=0.0)
    with col2:
        d = st.number_input("Yoğunluk", min_value=0.01, value=0.80)

    if st.button("HIZLI ÇEVİR", use_container_width=True):
        sonuc = miktar / d if "KG -> LT" in islem else miktar * d
        birim = "LT" if "KG -> LT" in islem else "KG"
        st.metric(label="Dönüştürülen Miktar", value=f"{sonuc:.2f} {birim}")

elif islem == "Denatürasyon Hesaplama (Yeni Sipariş)":
    tip = st.selectbox("Reçete Tipi:", ["K Tipi", "D Tipi", "Metanol Denatürasyonu"])
    miktar = st.number_input("Saf Ürün Hacmi (LT):", min_value=0.0)

    if st.button("REÇETEYİ HAZIRLA", use_container_width=True):
        carpan = miktar / 100
        st.markdown("### 📝 Hazırlanacak Reçete")
        if tip == "K Tipi":
            st.warning(f"D. Benzoat: {0.8 * carpan:.2f} gr | TBA: {78 * carpan:.2f} gr")
        elif tip == "D Tipi":
            st.warning(f"IPA: {5 * carpan:.2f} kg | TBA: {78 * carpan:.2f} gr")
        else:
            st.warning(f"D. Benzoat: {3 * carpan:.2f} gr")

elif islem == "Denatürasyon Sağlama (Mevcut Ürün Kontrolü)":
    tip = st.selectbox("Kontrol Edilecek Ürün:", ["K Tipi Sağlama", "D Tipi Sağlama", "Metanol Sağlama"])
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

st.write("")
st.caption("© 2026 Mavi Plastik Kimya San ve Tic. A.Ş. | Batuhan KILIÇ")
