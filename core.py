"""
core.py — logik tulen RadarBajet.
Tiada Streamlit di sini, jadi semua fungsi boleh diuji secara berasingan.

Fokus: kepercayaan data.
  * normalize_item()  — "Beras 10 KG" dan "beras 10kg" ialah item yang sama.
  * robust_flags()    — tanda harga yang tersasar tanpa buang data.
  * ringkas_harga()   — median + bilangan laporan + umur data + label keyakinan.
  * cari_kedai_serupa() — halang kedai pendua didaftarkan dua kali.
"""

from __future__ import annotations

import difflib
import math
import re
import statistics
import unicodedata
from datetime import datetime, timezone

import pandas as pd

# "10 kg" -> "10kg", "1 L" -> "1l"
_UNIT_GAP = re.compile(r"(\d)\s+(kg|kgs|g|gram|gramme|l|liter|litre|ml|pcs|biji|biji)\b")
_SUFFIX_SYARIKAT = re.compile(r"\b(sdn|bhd|sendirian|berhad|enterprise|trading|co)\b")


# ---------------------------------------------------------------------------
# Normalisasi
# ---------------------------------------------------------------------------
def _ascii_lower(nilai) -> str:
    teks = unicodedata.normalize("NFKD", str(nilai))
    teks = "".join(ch for ch in teks if not unicodedata.combining(ch))
    return teks.lower()


def normalize_item(nilai) -> str:
    """Kunci padanan untuk nama barang. 'Beras 10 KG' -> 'beras 10kg'."""
    if nilai is None or (isinstance(nilai, float) and math.isnan(nilai)):
        return ""
    teks = _ascii_lower(nilai)
    teks = re.sub(r"[^a-z0-9]+", " ", teks)
    teks = _UNIT_GAP.sub(r"\1\2", teks)
    return " ".join(teks.split())


def normalize_nama(nilai) -> str:
    """Kunci padanan untuk nama kedai. Buang sdn bhd dsb."""
    teks = normalize_item(nilai)
    teks = _SUFFIX_SYARIKAT.sub(" ", teks)
    return " ".join(teks.split())


def kira_jarak_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Jarak garis lurus (Haversine), km."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


# ---------------------------------------------------------------------------
# Pengesanan outlier
# ---------------------------------------------------------------------------
def robust_flags(values: list[float]) -> list[bool]:
    """
    Tanda nilai yang tersasar. True = outlier.

    Kaedah: pagar Tukey (IQR). Pagar dilebarkan kepada 3.0 x IQR apabila
    sampel kecil (n < 8), kerana IQR sangat tidak stabil dengan 4-7 titik.
    Ditambah pagar nisbah kasar (3x median) untuk kesilapan besar seperti
    RM1.00 atau RM999.00.

    Reka bentuk sengaja konservatif: lebih baik biarkan harga sah
    kelihatan sedikit ekstrem daripada buang laporan orang.
    """
    vals = [float(v) for v in values]
    n = len(vals)
    if n < 3:
        return [False] * n

    med = statistics.median(vals)
    flags = [False] * n

    if n >= 4:
        q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
        iqr = q3 - q1
        k = 3.0 if n < 8 else 1.5
        lo = q1 - k * iqr
        hi = q3 + k * iqr
        flags = [(v < lo or v > hi) for v in vals]

    if med > 0:
        flags = [f or v > med * 3 or v < med / 3 for f, v in zip(flags, vals)]

    return flags


def label_keyakinan(n_sah: int, umur_hari: float | None) -> str:
    """Label ringkas untuk pengguna — berapa boleh percaya nombor ini."""
    if umur_hari is None:
        return "Rendah"
    if n_sah >= 5 and umur_hari <= 7:
        return "Tinggi"
    if n_sah >= 3 and umur_hari <= 21:
        return "Sederhana"
    return "Rendah"


def ringkas_harga(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ringkasan per (kedai_id, item). df perlu ada: kedai_id, item, harga, created_at.
    Outlier dikecualikan daripada median, tetapi bilangannya dilaporkan.
    """
    kolum = [
        "kedai_id", "item_key", "item", "sumber", "n", "n_outlier", "median",
        "min", "max", "terakhir", "umur_hari", "keyakinan",
    ]
    if df is None or df.empty:
        return pd.DataFrame(columns=kolum)

    d = df.copy()
    d["item_key"] = d["item"].map(normalize_item)
    d["_ts"] = pd.to_datetime(d.get("created_at"), errors="coerce", utc=True)

    sekarang = datetime.now(timezone.utc)
    baris = []
    for (kedai_id, item_key), g in d.groupby(["kedai_id", "item_key"], dropna=False):
        vals = [float(v) for v in g["harga"].tolist()]
        bendera = robust_flags(vals)
        bersih = [v for v, f in zip(vals, bendera) if not f] or vals
        ts = g["_ts"].dropna()
        terakhir = ts.max().to_pydatetime() if len(ts) else None
        umur = (sekarang - terakhir).days if terakhir else None

        # Bentuk item yang paling kerap dilaporkan (untuk paparan)
        mod = g["item"].astype(str).mode()
        contoh_item = mod.iloc[0] if len(mod) else item_key
        sumber = (
            "peniaga"
            if "sumber" in g.columns and (g["sumber"].astype(str) == "peniaga").any()
            else "resit"
        )

        baris.append(
            {
                "kedai_id": kedai_id,
                "item_key": item_key,
                "item": contoh_item,
                "sumber": sumber,
                "n": len(bersih),
                "n_outlier": sum(bendera),
                "median": round(statistics.median(bersih), 2),
                "min": round(min(bersih), 2),
                "max": round(max(bersih), 2),
                "terakhir": terakhir.date().isoformat() if terakhir else None,
                "umur_hari": umur,
                "keyakinan": label_keyakinan(len(bersih), umur),
            }
        )

    return pd.DataFrame(baris, columns=kolum).sort_values(["item_key", "median"])


# ---------------------------------------------------------------------------
# Deduplikasi kedai
# ---------------------------------------------------------------------------
def cari_kedai_serupa(
    df_kedai: pd.DataFrame,
    nama: str,
    lat: float,
    lon: float,
    radius_m: float = 250,
    ambang: float = 0.85,
) -> list[dict]:
    """
    Cari kedai yang mungkin sama: nama hampir serupa DAN dalam radius.
    Dipanggil sebelum daftar kedai baharu supaya peta tak penuh dengan
    'Kedai Pak Ali' x3.
    """
    if df_kedai is None or df_kedai.empty or not str(nama).strip():
        return []

    sasaran = normalize_nama(nama)
    if not sasaran:
        return []

    hasil = []
    for _, r in df_kedai.iterrows():
        try:
            jarak_m = kira_jarak_km(lat, lon, float(r["lat"]), float(r["lon"])) * 1000
        except (TypeError, ValueError, KeyError):
            continue
        if jarak_m > radius_m:
            continue

        lain = normalize_nama(r.get("nama", ""))
        if not lain:
            continue

        skor = difflib.SequenceMatcher(None, sasaran, lain).ratio()
        # Satu nama terkandung dalam yang lain -> hampir pasti sama
        if sasaran in lain or lain in sasaran:
            skor = max(skor, 0.90)
        if skor < ambang:
            continue

        hasil.append(
            {
                "id": int(r["id"]) if pd.notna(r.get("id")) else None,
                "nama": r.get("nama"),
                "jarak_m": round(jarak_m),
                "similarity": round(skor, 2),
            }
        )

    return sorted(hasil, key=lambda x: -x["similarity"])
