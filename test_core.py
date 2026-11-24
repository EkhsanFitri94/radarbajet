"""Ujian logik teras. Jalankan: python test_core.py"""

import os
import sys

# Sokongan folder dependensi tempatan (opsyenal)
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_DEPS = os.path.join(_HERE, ".deps")
if os.path.isdir(_DEPS):
    sys.path.insert(0, _DEPS)

import pandas as pd

from core import (
    cari_kedai_serupa,
    kira_jarak_km,
    label_keyakinan,
    normalize_item,
    normalize_nama,
    ringkas_harga,
    robust_flags,
)

lulus = 0
gagal = 0


def semak(nama, dapat, jangka):
    global lulus, gagal
    if dapat == jangka:
        lulus += 1
        print(f"  OK   {nama}")
    else:
        gagal += 1
        print(f"  GAGAL {nama}\n        dapat : {dapat!r}\n        jangka: {jangka!r}")


print("\n== normalisasi item ==")
semak("spasi + huruf besar", normalize_item("Beras 10 KG"), "beras 10kg")
semak("tanpa spasi", normalize_item("BERAS 10KG"), "beras 10kg")
semak("tanda baca", normalize_item("Beras Super Spesial 10kg."), "beras super spesial 10kg")
semak("unit liter", normalize_item("Minyak Masak 5 L"), "minyak masak 5l")
semak("kosong", normalize_item(None), "")

print("\n== normalisasi nama kedai ==")
semak("buang sdn bhd", normalize_nama("Kedai Pak Ali Sdn. Bhd."), "kedai pak ali")
semak("huruf besar", normalize_nama("KEDAI PAK ALI"), "kedai pak ali")

print("\n== jarak ==")
# KLCC ke Bukit Bintang ~ 1.2 km
jarak = kira_jarak_km(3.1578, 101.7116, 3.1478, 101.6953)
semak("KLCC-Bukit Bintang antara 1.5-2.2km", 1.5 <= jarak <= 2.2, True)

print("\n== outlier ==")
semak("sampel kecil: tiada bendera", robust_flags([8.5, 9.0]), [False, False])
semak("RM1.00 dikesan", robust_flags([8.5, 9.2, 8.8, 1.0, 11.0]), [False, False, False, True, False])
semak("semua sama: tiada bendera", robust_flags([10, 10, 10, 10]), [False] * 4)
semak("satu ekstrem besar dikesan", robust_flags([10, 10, 10, 10, 50]), [False, False, False, False, True])
semak("variasi biasa tidak dikesan", robust_flags([26.0, 26.5, 28.0, 32.0]), [False] * 4)

print("\n== keyakinan ==")
semak("banyak + baru", label_keyakinan(6, 2), "Tinggi")
semak("sederhana", label_keyakinan(3, 10), "Sederhana")
semak("lama", label_keyakinan(9, 40), "Rendah")
semak("tiada tarikh", label_keyakinan(9, None), "Rendah")

print("\n== ringkasan harga ==")
df = pd.DataFrame(
    [
        {"kedai_id": 1, "item": "Beras 10kg", "harga": 26.0, "created_at": "2026-11-23T02:00:00Z"},
        {"kedai_id": 1, "item": "Beras 10kg", "harga": 27.0, "created_at": "2026-11-22T02:00:00Z"},
        {"kedai_id": 1, "item": "BERAS 10 KG", "harga": 1.0, "created_at": "2026-11-21T02:00:00Z"},
        {"kedai_id": 2, "item": "Beras 10kg", "harga": 32.0, "created_at": "2026-10-01T02:00:00Z"},
    ]
)
r = ringkas_harga(df)
semak("dua kumpulan", len(r), 2)
k1 = r[r["kedai_id"] == 1].iloc[0]
semak("item sama digabung", k1["item_key"], "beras 10kg")
semak("outlier RM1 dibuang", k1["n"], 2)
semak("outlier dikira", k1["n_outlier"], 1)
semak("median betul", k1["median"], 26.5)
k2 = r[r["kedai_id"] == 2].iloc[0]
semak("data lama -> keyakinan rendah", k2["keyakinan"], "Rendah")

print("\n== deduplikasi kedai ==")
kedai = pd.DataFrame(
    [
        {"id": 1, "nama": "Kedai Pak Ali", "lat": 3.1478, "lon": 101.6953},
        {"id": 2, "nama": "Restoran Siti", "lat": 3.1479, "lon": 101.6954},
        {"id": 3, "nama": "Kedai Pak Ali", "lat": 5.9804, "lon": 116.0735},  # Kota Kinabalu
    ]
)
serupa = cari_kedai_serupa(kedai, "Kedai Pak Ali Sdn Bhd", 3.14785, 101.69535)
semak("jumpa 1 pendua dekat", len(serupa), 1)
semak("id pendua betul", serupa[0]["id"], 1)
semak("nama berbeza tidak disalah anggap", cari_kedai_serupa(kedai, "Pasaraya Mewah", 3.1478, 101.6953), [])
semak("nama sama tapi jauh tidak match", [x["id"] for x in cari_kedai_serupa(kedai, "Kedai Pak Ali", 5.9804, 116.0735)], [3])

print(f"\n{lulus} lulus, {gagal} gagal")
sys.exit(1 if gagal else 0)
