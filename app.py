"""
RadarBajet v0.1 — MVP yang benar-benar boleh jalan
==================================================
Perbezaan utama berbanding versi dalam perbualan Google AI Mode:
  1. Tiada kunci API ditulis dalam kod. Guna .streamlit/secrets.toml atau Streamlit Cloud Secrets.
  2. Semua panggilan rangkaian dibalut try/except — app tak mati kalau Supabase/Gemini tak dikonfigurasi.
  3. Data demo terbina dalam (nama kedai fiksyen) supaya app boleh diuji serta-merta tanpa akaun.
  4. "Julat harga" dipaparkan sebagai HARGA DIPERHATI (min/median/max), BUKAN cadangan harga.
     Ini penting: platform yang "mencadangkan" harga kepada peniaga boleh dianggap memudahkan
     penyelarasan harga di bawah Akta Persaingan 2010. Kita lapor apa yang diperhati, bukan arahan.
  5. Setiap harga mesti ada bukti (gambar resit/tanda harga) — lapisan kepercayaan asas.

Jalan:  streamlit run app.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

# Pastikan folder projek ada dalam sys.path (penting untuk Streamlit Cloud juga)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from core import (  # noqa: E402
    cari_kedai_serupa,
    kira_jarak_km,
    normalize_item,
    ringkas_harga,
    robust_flags,
)

# ---------------------------------------------------------------------------
# 1. DEPENDENSI PILIHAN — kalau tiada, app tetap jalan dalam mod demo
# ---------------------------------------------------------------------------
try:
    import folium
    from streamlit_folium import st_folium

    FOLIUM_OK = True
except Exception:
    FOLIUM_OK = False

try:
    from supabase import create_client

    SUPA_OK = True
except Exception:
    SUPA_OK = False

try:
    from google import genai

    GENAI_OK = True
except Exception:
    GENAI_OK = False

try:
    from PIL import Image

    PIL_OK = True
except Exception:
    PIL_OK = False

try:
    from streamlit_js_eval import get_geolocation

    GEO_OK = True
except Exception:
    GEO_OK = False

st.set_page_config(page_title="RadarBajet", page_icon="📡", layout="wide")


def secret(key: str, default: str | None = None) -> str | None:
    """Baca dari st.secrets tanpa crash kalau fail secrets tiada."""
    try:
        return st.secrets[key]
    except Exception:
        return default


SUPABASE_URL = secret("SUPABASE_URL")
SUPABASE_KEY = secret("SUPABASE_KEY")
GEMINI_API_KEY = secret("GEMINI_API_KEY")

# ---------------------------------------------------------------------------
# 2. SAMBUNGAN
# ---------------------------------------------------------------------------
supabase = None
if SUPA_OK and SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.sidebar.error(f"Supabase gagal disambung: {e}")

ai_client = None
if GENAI_OK and GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception:
        ai_client = None

LIVE = supabase is not None


# ---------------------------------------------------------------------------
# 3. DATA DEMO (nama fiksyen — sengaja, supaya tiada pihak yang tercemar)
# ---------------------------------------------------------------------------
DEMO_KEDAI = [
    {"id": 1, "nama": "Pasar Raya Borong Demo", "kategori": "Runcit", "lat": 3.1420, "lon": 101.6910, "status": "unclaimed", "konteks": "Premis borong, pusingan stok tinggi"},
    {"id": 2, "nama": "Kedai Runcit Kejiranan Demo", "kategori": "Runcit", "lat": 3.1510, "lon": 101.6980, "status": "verified", "konteks": "Kedai kejiranan, jarak dekat"},
    {"id": 3, "nama": "Pasaraya Mall Demo", "kategori": "Runcit", "lat": 3.1579, "lon": 101.7116, "status": "unclaimed", "konteks": "Dalam pusat beli-belah, sewa premis tinggi"},
    {"id": 4, "nama": "Pasar Segar Komuniti Demo", "kategori": "Runcit", "lat": 3.1350, "lon": 101.6850, "status": "verified", "konteks": "Pasar awam, bekalan terus"},
    {"id": 5, "nama": "Bengkel Pak Din Demo", "kategori": "Automotif", "lat": 3.1440, "lon": 101.6920, "status": "verified", "konteks": "Bengkel kejiranan, alat ganti OEM"},
    {"id": 6, "nama": "Pusat Servis Tayar Demo", "kategori": "Automotif", "lat": 3.1550, "lon": 101.7050, "status": "unclaimed", "konteks": "Premis berhawa dingin, ruang menunggu"},
    {"id": 7, "nama": "Warung Kak Tim Demo", "kategori": "Makanan", "lat": 3.1490, "lon": 101.6960, "status": "verified", "konteks": "Gerai tepi jalan, hidangan besar"},
    {"id": 8, "nama": "Restoran Signature Demo", "kategori": "Makanan", "lat": 3.1579, "lon": 101.7116, "status": "unclaimed", "konteks": "Dalam mall, ada SST & caj servis"},
]

DEMO_HARGA = [
    # Beras 10kg — sengaja ada beberapa laporan per kedai supaya label keyakinan bermakna
    {"kedai_id": 1, "item": "Beras 10kg", "kategori": "Runcit", "harga": 26.00, "sumber": "resit", "created_at": "2026-11-20"},
    {"kedai_id": 1, "item": "Beras 10kg", "kategori": "Runcit", "harga": 25.80, "sumber": "resit", "created_at": "2026-11-22"},
    {"kedai_id": 1, "item": "Beras 10kg", "kategori": "Runcit", "harga": 26.20, "sumber": "resit", "created_at": "2026-11-23"},
    {"kedai_id": 1, "item": "Beras 10kg", "kategori": "Runcit", "harga": 26.40, "sumber": "peniaga", "created_at": "2026-11-24"},
    # Baris ini SENGAJA salah taip — untuk tunjuk penapis outlier berfungsi
    {"kedai_id": 1, "item": "Beras 10kg", "kategori": "Runcit", "harga": 2.50, "sumber": "resit", "created_at": "2026-11-19"},
    {"kedai_id": 2, "item": "Beras 10kg", "kategori": "Runcit", "harga": 28.00, "sumber": "resit", "created_at": "2026-11-21"},
    {"kedai_id": 2, "item": "Beras 10kg", "kategori": "Runcit", "harga": 27.90, "sumber": "resit", "created_at": "2026-11-23"},
    {"kedai_id": 3, "item": "Beras 10kg", "kategori": "Runcit", "harga": 32.00, "sumber": "peniaga", "created_at": "2026-11-22"},
    {"kedai_id": 4, "item": "Beras 10kg", "kategori": "Runcit", "harga": 26.50, "sumber": "resit", "created_at": "2026-11-22"},
    {"kedai_id": 4, "item": "Beras 10kg", "kategori": "Runcit", "harga": 26.30, "sumber": "resit", "created_at": "2026-11-24"},

    # Ayam
    {"kedai_id": 1, "item": "Ayam 1kg", "kategori": "Runcit", "harga": 8.50, "sumber": "resit", "created_at": "2026-11-23"},
    {"kedai_id": 2, "item": "Ayam 1kg", "kategori": "Runcit", "harga": 9.20, "sumber": "resit", "created_at": "2026-11-23"},
    {"kedai_id": 3, "item": "Ayam 1kg", "kategori": "Runcit", "harga": 11.50, "sumber": "peniaga", "created_at": "2026-11-23"},
    {"kedai_id": 4, "item": "Ayam 1kg", "kategori": "Runcit", "harga": 8.20, "sumber": "resit", "created_at": "2026-11-23"},

    # Servis
    {"kedai_id": 5, "item": "Servis tukar minyak hitam", "kategori": "Automotif", "harga": 115.00, "sumber": "peniaga", "created_at": "2026-11-19"},
    {"kedai_id": 6, "item": "Servis tukar minyak hitam", "kategori": "Automotif", "harga": 165.00, "sumber": "resit", "created_at": "2026-11-20"},

    # Makanan
    {"kedai_id": 7, "item": "Nasi ayam gepuk", "kategori": "Makanan", "harga": 10.50, "sumber": "peniaga", "created_at": "2026-11-18"},
    {"kedai_id": 8, "item": "Nasi ayam gepuk", "kategori": "Makanan", "harga": 18.90, "sumber": "resit", "created_at": "2026-11-21"},
]


# ---------------------------------------------------------------------------
# 4. LOGIK
# ---------------------------------------------------------------------------
def parse_harga(nilai) -> float | None:
    """Gemini kadang pulangkan 'RM 12.50' atau '12,50'. Jangan terus float()."""
    if nilai is None:
        return None
    if isinstance(nilai, (int, float)):
        return float(nilai)
    s = str(nilai).strip()
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    if s.count(",") == 1 and s.count(".") == 0:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def kod_warna(kos_sebenar: float, bajet: float) -> tuple[str, str]:
    if kos_sebenar <= bajet:
        return "🟢 Dalam bajet", "green"
    if kos_sebenar <= bajet * 1.10:
        return "🟡 Hampir bajet", "orange"
    return "🔴 Melebihi bajet", "red"


def muat_data() -> tuple[pd.DataFrame, pd.DataFrame, bool]:
    """Pulangkan (kedai_df, harga_df, is_live)."""
    if LIVE:
        try:
            kedai = pd.DataFrame(supabase.table("kedai").select("*").execute().data)
            harga = pd.DataFrame(supabase.table("harga").select("*").execute().data)
            if not kedai.empty and not harga.empty:
                return kedai, harga, True
        except Exception as e:
            st.sidebar.warning(f"Gagal baca Supabase ({e}). Guna data demo.")
    return pd.DataFrame(DEMO_KEDAI), pd.DataFrame(DEMO_HARGA), False


def ekstrak_resit(imej) -> dict:
    if ai_client is None:
        raise RuntimeError("GEMINI_API_KEY belum diset. Isi dalam Secrets dahulu.")
    prompt = """Baca gambar resit / tanda harga ini. Pulangkan JSON SAHAJA, tiada teks lain:
{"kedai": "nama kedai atau 'Kedai Tidak Dikenali'", "kategori": "Makanan|Runcit|Automotif|Perkakasan|Farmasi|Lain-lain", "item": "nama barang paling jelas", "harga": 0.00}
Nilai 'harga' mesti nombor perpuluhan tanpa simbol RM."""
    resp = ai_client.models.generate_content(model="gemini-2.5-flash", contents=[imej, prompt])
    teks = (resp.text or "").replace("```json", "").replace("```", "").strip()
    data = json.loads(teks)
    data["harga"] = parse_harga(data.get("harga"))
    return data


# ---------------------------------------------------------------------------
# 5. SESI
# ---------------------------------------------------------------------------
for _k, _v in {"user": None, "peranan": "guest", "mata": 0, "geo": None}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ---------------------------------------------------------------------------
# 6. SIDEBAR — LOKASI + AKAUN
# ---------------------------------------------------------------------------
st.sidebar.title("📡 RadarBajet")
st.sidebar.caption("Harga diperhati oleh komuniti · bukan harga rasmi")

with st.sidebar.expander("📍 Lokasi anda", expanded=True):
    if GEO_OK and st.session_state.geo is None:
        loc = get_geolocation()
        if loc and loc.get("coords"):
            st.session_state.geo = (loc["coords"]["latitude"], loc["coords"]["longitude"])
    if st.session_state.geo:
        lat0, lon0 = st.session_state.geo
        st.success(f"GPS aktif · {lat0:.4f}, {lon0:.4f}")
        if st.button("Lupakan lokasi", use_container_width=True):
            st.session_state.geo = None
            st.rerun()
    else:
        st.info("GPS belum dibenarkan. Masukkan lokasi manual:")
        c1, c2 = st.columns(2)
        lat0 = c1.number_input("Lat", value=3.1478, format="%.4f")
        lon0 = c2.number_input("Lon", value=101.6953, format="%.4f")
        st.caption("Lalai: Kuala Lumpur")

st.sidebar.divider()

if not LIVE:
    st.sidebar.warning("Mod demo — data fiksyen. Sambung Supabase untuk data sebenar.")

if st.session_state.user is None:
    st.sidebar.subheader("🔐 Akaun")
    if not LIVE:
        st.sidebar.caption("Log masuk dilumpuhkan dalam mod demo.")
    else:
        mod = st.sidebar.radio("Tindakan", ["Log masuk", "Daftar"], horizontal=True)
        emel = st.sidebar.text_input("Emel")
        pwd = st.sidebar.text_input("Kata laluan", type="password")
        if mod == "Daftar":
            peranan = st.sidebar.selectbox("Daftar sebagai", ["consumer", "merchant"])
            if st.sidebar.button("Daftar", use_container_width=True):
                if not emel or len(pwd) < 6:
                    st.sidebar.error("Emel wajib, kata laluan minima 6 aksara.")
                else:
                    try:
                        res = supabase.auth.sign_up({"email": emel, "password": pwd})
                        if res.user:
                            # Profil dicipta oleh trigger handle_new_user() dalam schema.sql
                            st.sidebar.success("Akaun dicipta. Sila log masuk.")
                    except Exception as e:
                        st.sidebar.error(f"Ralat daftar: {e}")
        else:
            if st.sidebar.button("Log masuk", use_container_width=True):
                try:
                    res = supabase.auth.sign_in_with_password({"email": emel, "password": pwd})
                    if res.user:
                        st.session_state.user = res.user
                        p = supabase.table("profil").select("*").eq("id", res.user.id).execute()
                        if p.data:
                            st.session_state.peranan = p.data[0].get("peranan", "consumer")
                            st.session_state.mata = p.data[0].get("mata", 0)
                        st.rerun()
                except Exception:
                    st.sidebar.error("Emel atau kata laluan tidak tepat.")
else:
    u = st.session_state.user
    st.sidebar.success(f"👤 {getattr(u, 'email', 'pengguna')}")
    st.sidebar.write(f"Peranan: **{st.session_state.peranan}**")
    if st.session_state.peranan == "consumer":
        st.sidebar.metric("Mata", f"{st.session_state.mata}")
    if st.sidebar.button("Log keluar", use_container_width=True):
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
        st.session_state.user = None
        st.session_state.peranan = "guest"
        st.rerun()


# ---------------------------------------------------------------------------
# 7. TAJUK
# ---------------------------------------------------------------------------
st.title("📡 RadarBajet")
st.caption(
    "Bandingkan harga mengikut **bajet poket anda** + **kos perjalanan sebenar**. "
    "Semua harga adalah laporan komuniti, bukan harga rasmi kedai."
)

df_kedai, df_harga, is_live = muat_data()
df = df_harga.merge(df_kedai, left_on="kedai_id", right_on="id", suffixes=("", "_kedai"))

tab_peta, tab_lapor, tab_peniaga = st.tabs(
    ["🗺️ Cari & banding", "📸 Lapor harga", "🏪 Peniaga"]
)


# ---------------------------------------------------------------------------
# 8. TAB 1 — CARI & BANDING
# ---------------------------------------------------------------------------
with tab_peta:
    c1, c2, c3 = st.columns([2, 1, 1])
    carian = c1.text_input("Cari barang atau servis", placeholder="cth: beras, ayam, minyak hitam")
    bajet = c2.number_input("Bajet (RM)", min_value=1.0, value=60.0, step=5.0)
    kos_km = c3.number_input("Kos perjalanan (RM/km)", min_value=0.0, value=0.35, step=0.05)

    if df.empty:
        st.info("Tiada data lagi. Pergi ke tab **Lapor harga** untuk jadi penyumbang pertama.")
    else:
        # 1. Tanda outlier sekali gus untuk seluruh set (per kedai + item)
        df = df.copy()
        df["item_key"] = df["item"].map(normalize_item)
        df["_outlier"] = False
        for _kunci, _idx in df.groupby(["kedai_id", "item_key"], dropna=False).groups.items():
            df.loc[_idx, "_outlier"] = robust_flags(df.loc[_idx, "harga"].astype(float).tolist())

        # 2. Satu baris per kedai + item. Harga dipaparkan = median laporan sah.
        ringkas = ringkas_harga(df)
        ringkas = ringkas.merge(
            df_kedai[["id", "nama", "kategori", "lat", "lon", "konteks"]],
            left_on="kedai_id",
            right_on="id",
            how="left",
        )

        # 3. Carian guna kunci ternormal: 'Beras 10 KG' padan 'beras 10kg'
        q = normalize_item(carian)
        if q:
            tapis = ringkas[
                ringkas["item_key"].str.contains(q, regex=False, na=False)
                | ringkas["kategori"].astype(str).str.lower().str.contains(q, regex=False, na=False)
            ].copy()
        else:
            tapis = ringkas.copy()

        dibuang = df[df["_outlier"]].copy()

        if tapis.empty:
            st.warning(f"Tiada rekod untuk **'{carian}'**. Carian ini tetap berguna — ia tanda permintaan.")
        else:
            baris = []
            for _, r in tapis.iterrows():
                jarak = kira_jarak_km(lat0, lon0, float(r["lat"]), float(r["lon"])) * 1.25
                kos_jalan = jarak * 2 * kos_km
                harga = float(r["median"])
                total = harga + kos_jalan
                label, pin = kod_warna(total, bajet)
                umur = int(r["umur_hari"]) if pd.notna(r["umur_hari"]) else None

                baris.append(
                    {
                        "Status": label,
                        "Kedai": r["nama"],
                        "Item": r["item"],
                        "Harga (RM)": round(harga, 2),
                        "Kos sebenar (RM)": round(total, 2),
                        "Laporan": int(r["n"]),
                        "Umur (hari)": umur,
                        "Keyakinan": r["keyakinan"],
                        "Sumber": "Peniaga" if str(r.get("sumber")) == "peniaga" else "Resit",
                        "Konteks": r.get("konteks", ""),
                        "lat": float(r["lat"]),
                        "lon": float(r["lon"]),
                        "pin": pin,
                    }
                )
            hasil = pd.DataFrame(baris).sort_values("Kos sebenar (RM)")

            # Julat diperhati — bukan cadangan harga
            lo, med, hi = (
                hasil["Harga (RM)"].min(),
                hasil["Harga (RM)"].median(),
                hasil["Harga (RM)"].max(),
            )
            st.caption(
                f"Harga diperhati: **RM{lo:.2f} – RM{hi:.2f}** (median RM{med:.2f}) "
                f"dari {len(hasil)} kedai. Ini laporan komuniti, bukan harga yang dicadangkan "
                "kepada sesiapa."
            )

            kiri, kanan = st.columns([1.1, 1])
            with kiri:
                if FOLIUM_OK:
                    peta = folium.Map(location=[lat0, lon0], zoom_start=14, tiles="OpenStreetMap")
                    folium.Marker(
                        [lat0, lon0],
                        popup="Lokasi anda",
                        icon=folium.Icon(color="blue", icon="user", prefix="fa"),
                    ).add_to(peta)
                    for _, k in hasil.iterrows():
                        folium.Marker(
                            [k["lat"], k["lon"]],
                            popup=f"{k['Kedai']}<br>RM{k['Harga (RM)']:.2f} · {k['Status']}",
                            icon=folium.Icon(color=k["pin"], icon="store", prefix="fa"),
                        ).add_to(peta)
                    st_folium(peta, width=700, height=430, returned_objects=[])
                else:
                    st.info("folium tidak dipasang — peta dilangkau. `pip install folium streamlit-folium`")
                    st.map(hasil[["lat", "lon"]])

            with kanan:
                st.dataframe(
                    hasil[
                        [
                            "Status",
                            "Kedai",
                            "Harga (RM)",
                            "Kos sebenar (RM)",
                            "Laporan",
                            "Keyakinan",
                            "Konteks",
                        ]
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
                terbaik = hasil.iloc[0]
                if terbaik["Kos sebenar (RM)"] <= bajet:
                    st.success(
                        f"💡 Paling murah selepas kos jalan: **{terbaik['Kedai']}** — "
                        f"RM{terbaik['Kos sebenar (RM)']:.2f}, baki RM{bajet - terbaik['Kos sebenar (RM)']:.2f}."
                    )
                else:
                    st.warning(
                        f"Semua pilihan melebihi bajet. Paling hampir: **{terbaik['Kedai']}** "
                        f"(+RM{terbaik['Kos sebenar (RM)'] - bajet:.2f})."
                    )

        if len(dibuang):
            with st.expander(f"⚠️ {len(dibuang)} laporan luar biasa ditapis"):
                st.dataframe(
                    dibuang[["nama", "item", "harga", "created_at"]],
                    hide_index=True,
                    use_container_width=True,
                )
                st.caption(
                    "Data ini tidak dipadam — hanya tidak dimasukkan dalam median supaya "
                    "satu silap baca tidak merosakkan harga lain."
                )

        st.caption(
            "Jarak = garis lurus × 1.25 (anggaran jalan sebenar). Kos perjalanan ialah tekaan anda "
            "sendiri, bukan data rasmi. Keyakinan = bilangan laporan + kesegaran data."
        )


# ---------------------------------------------------------------------------
# 9. TAB 2 — LAPOR HARGA
# ---------------------------------------------------------------------------
with tab_lapor:
    if st.session_state.user is None:
        st.warning("🔒 Log masuk diperlukan untuk melapor harga. Ini menghalang spam dan membolehkan anda dapat mata.")
    else:
        st.subheader("Lapor harga")
        st.caption("Setiap laporan mesti ada bukti gambar. Tanpa bukti, data jadi sampah dan semua orang berhenti percaya.")

        if df_kedai.empty:
            st.error("Tiada senarai kedai. Sila isi jadual `kedai` dahulu.")
            st.stop()

        pilihan_kedai = {f"{r['nama']} ({r['kategori']})": int(r["id"]) for _, r in df_kedai.iterrows()}
        pilih = st.selectbox("Kedai", list(pilihan_kedai.keys()))
        item = st.text_input("Barang / servis", placeholder="cth: Beras 10kg")
        harga_manual = st.number_input("Harga (RM)", min_value=0.10, value=10.00, step=0.10)

        guna_ai = ai_client is not None
        gambar = st.file_uploader("Gambar resit / tanda harga", type=["jpg", "jpeg", "png"])
        if gambar and not PIL_OK:
            st.error("Pillow tidak dipasang. `pip install pillow`")
        elif gambar and not guna_ai:
            st.info("GEMINI_API_KEY tiada — isi harga secara manual di atas. Gambar tetap disimpan sebagai bukti.")

        if st.button("Hantar laporan", type="primary"):
            if not item.strip():
                st.error("Nama barang wajib diisi.")
            elif gambar is None:
                st.error("Bukti gambar wajib. Ambil gambar resit atau tanda harga.")
            else:
                with st.spinner("Memproses…"):
                    data_ai = {}
                    if guna_ai and PIL_OK:
                        try:
                            data_ai = ekstrak_resit(Image.open(gambar))
                            st.json(data_ai)
                        except Exception as e:
                            st.warning(f"AI gagal baca gambar ({e}). Guna nilai manual.")

                    harga_final = data_ai.get("harga") or harga_manual
                    item_final = (data_ai.get("item") or item).strip()

                    # Semak kewajaran sebelum simpan: bacaan AI boleh tersilap
                    _kid = pilihan_kedai[pilih]
                    _kunci = normalize_item(item_final)
                    _sedia = df[
                        (df["kedai_id"] == _kid)
                        & (df["item"].map(normalize_item) == _kunci)
                    ]
                    _median = (
                        float(_sedia["harga"].astype(float).median()) if len(_sedia) >= 2 else None
                    )
                    if _median is not None and robust_flags(
                        _sedia["harga"].astype(float).tolist() + [float(harga_final)]
                    )[-1]:
                        st.warning(
                            f"⚠️ RM{harga_final:.2f} jauh berbeza daripada median sedia ada "
                            f"(RM{_median:.2f}). Semak semula gambar sebelum percaya. "
                            "Laporan tetap disimpan, tetapi akan ditapis daripada perbandingan."
                        )

                    if not LIVE:
                        st.success(
                            f"Mod demo: laporan **{item_final} — RM{harga_final:.2f}** diterima "
                            "(tidak disimpan sebab tiada pangkalan data)."
                        )
                    else:
                        try:
                            bukti_path = None
                            try:
                                ext = (gambar.name.rsplit(".", 1)[-1] or "jpg").lower()
                                bukti_path = f"{st.session_state.user.id}/{datetime.now():%Y%m%d%H%M%S}.{ext}"
                                supabase.storage.from_("resit").upload(
                                    bukti_path,
                                    gambar.getvalue(),
                                    {"content-type": gambar.type or "image/jpeg"},
                                )
                            except Exception as e:
                                st.warning(f"Gambar gagal dimuat naik ({e}). Laporan tetap disimpan tanpa bukti.")

                            supabase.table("harga").insert(
                                {
                                    "kedai_id": pilihan_kedai[pilih],
                                    "item": item_final,
                                    "kategori": data_ai.get("kategori", "Lain-lain"),
                                    "harga": float(harga_final),
                                    "bukti_path": bukti_path,
                                    "dilapor_oleh": st.session_state.user.id,
                                    "sumber": "resit",
                                }
                            ).execute()

                            mata_baru = st.session_state.mata + 20
                            supabase.table("profil").update({"mata": mata_baru}).eq(
                                "id", st.session_state.user.id
                            ).execute()
                            st.session_state.mata = mata_baru
                            st.success(f"Disimpan. +20 mata (jumlah {mata_baru}).")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal simpan: {e}")

        st.divider()
        st.caption(
            "Nota privasi: gambar resit mungkin mengandungi maklumat peribadi. "
            "Jangan muat naik resit yang memaparkan nombor kad atau alamat penuh."
        )


# ---------------------------------------------------------------------------
# 10. TAB 3 — PENIAGA
# ---------------------------------------------------------------------------
with tab_peniaga:
    if st.session_state.peranan != "merchant":
        st.warning(
            "🔒 Tab ini untuk akaun **merchant**. Daftar akaun baharu dan pilih peranan 'merchant' di sidebar."
        )
        st.markdown(
            """
**Apa peniaga dapat (dan tak dapat) di sini**

| Dapat | Tak dapat |
|---|---|
| Terbitkan harga sendiri, bertanda "Peniaga" | Padam atau ubah harga laporan pengguna |
| Lihat item apa yang paling banyak dicari sekitar kedai | Lihat identiti pengguna yang melapor |
| Betulkan konteks kedai (contoh: "termasuk pemasangan") | Naikkan kedai pesaing |

Harga laporan pengguna **tidak boleh** dipadam oleh peniaga. Itu bukan bug — itu janji kepada pengguna.
            """
        )
    else:
        st.subheader("Urus kedai anda")
        kedai_saya = df_kedai[df_kedai.get("pemilik_id").notna()] if "pemilik_id" in df_kedai else pd.DataFrame()

        if LIVE:
            kedai_saya = kedai_saya[kedai_saya["pemilik_id"] == st.session_state.user.id]

        if kedai_saya.empty:
            st.info("Anda belum ada kedai berdaftar. Daftar di bawah.")
            with st.form("daftar_kedai"):
                nama = st.text_input("Nama kedai")
                kategori = st.selectbox("Kategori", ["Runcit", "Makanan", "Automotif", "Perkakasan", "Farmasi", "Lain-lain"])
                konteks = st.text_input("Kelebihan kedai", placeholder="cth: termasuk pemasangan, bahan segar harian")
                paksa = st.checkbox("Saya sahkan ini kedai BAHARU, bukan pendua")
                hantar = st.form_submit_button("Daftar kedai")

            if not LIVE:
                st.caption("Mod demo: pendaftaran dilumpuhkan.")

            if hantar and LIVE:
                if not nama.strip():
                    st.error("Nama kedai wajib.")
                else:
                    serupa = cari_kedai_serupa(df_kedai, nama, lat0, lon0)
                    if serupa and not paksa:
                        st.warning("Kedai serupa sudah ada dalam radius 250 m:")
                        st.dataframe(
                            pd.DataFrame(serupa), hide_index=True, use_container_width=True
                        )
                        st.info(
                            "Guna kedai sedia ada supaya peta tak penuh dengan pendua. "
                            "Kalau ini memang cawangan berasingan, tandakan kotak pengesahan dan hantar semula."
                        )
                    else:
                        try:
                            supabase.table("kedai").insert(
                                {
                                    "nama": nama.strip(),
                                    "kategori": kategori,
                                    "lat": lat0,
                                    "lon": lon0,
                                    "konteks": konteks,
                                    "status": "unclaimed",
                                    "pemilik_id": st.session_state.user.id,
                                }
                            ).execute()
                            st.success("Kedai didaftarkan. Lencana 'disahkan' diberikan oleh admin selepas semakan SSM/PBT.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Gagal: {e}")
        else:
            for _, k in kedai_saya.iterrows():
                st.markdown(f"**{k['nama']}** · {k['kategori']} · status `{k['status']}`")
            st.divider()
            with st.form("terbit_harga"):
                pilih_nama = st.selectbox("Kedai", kedai_saya["nama"].tolist())
                item = st.text_input("Barang / servis")
                harga = st.number_input("Harga (RM)", min_value=0.10, value=10.00)
                if st.form_submit_button("Terbitkan harga") and LIVE:
                    kid = int(kedai_saya[kedai_saya["nama"] == pilih_nama].iloc[0]["id"])
                    try:
                        supabase.table("harga").insert(
                            {
                                "kedai_id": kid,
                                "item": item.strip(),
                                "kategori": kedai_saya.iloc[0]["kategori"],
                                "harga": float(harga),
                                "dilapor_oleh": st.session_state.user.id,
                                "sumber": "peniaga",
                            }
                        ).execute()
                        st.success("Harga diterbitkan dan ditanda sebagai harga peniaga.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal: {e}")

        st.divider()
        st.subheader("Isyarat permintaan")
        if df.empty:
            st.caption("Belum ada data.")
        else:
            permintaan = (
                df.groupby("item")
                .agg(laporan=("harga", "count"), median=("harga", "median"))
                .sort_values("laporan", ascending=False)
                .head(10)
            )
            st.caption("Item paling banyak dilaporkan. Ini proksi kasar permintaan — bukan data carian sebenar.")
            st.dataframe(permintaan, use_container_width=True)

st.divider()
st.caption(
    "RadarBajet v0.1 · data komuniti · bukan pengganti harga rasmi kedai. "
    "Harga boleh berubah bila-bila masa; sahkan di kaunter sebelum membayar."
)
