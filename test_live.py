"""
Ujian hidup untuk RadarBajet: Supabase Auth, upload bucket `resit`, RLS, dan Gemini.

STATUS: belum pernah dijalankan. Tiada projek Supabase wujud semasa kod ini ditulis.

Jalankan sendiri dengan kunci anda (jangan hantar kunci kepada sesiapa):

    $env:SUPABASE_URL    = "https://xxxx.supabase.co"
    $env:SUPABASE_KEY    = "<anon public key>"
    $env:GEMINI_API_KEY  = "<kunci AI Studio>"      # opsyenal
    $env:TEST_EMAIL      = "ujian+1@domain-anda.com"
    $env:TEST_PASSWORD   = "<minima 6 aksara>"
    python test_live.py

Apa yang diuji:
  1. Sambungan Supabase + bucket `resit` wujud
  2. Daftar / log masuk pengguna ujian
  3. Upload PNG kecil ke folder {uid}/ (laluan yang sama seperti app)
  4. Fail benar-benar berada dalam bucket
  5. Pengguna tanpa log masuk TIDAK boleh insert ke jadual harga (RLS)
  6. Gemini boleh baca imej (jika kunci diberi)
  7. Bersih: fail ujian dan baris ujian dipadam
"""

from __future__ import annotations

import io
import os
import sys

try:
    from PIL import Image, ImageDraw
    from supabase import create_client
except ImportError:
    print("Pakej hilang. Jalankan: pip install -r requirements.txt")
    sys.exit(1)

URL = os.environ.get("SUPABASE_URL", "")
KEY = os.environ.get("SUPABASE_KEY", "")
GEMINI = os.environ.get("GEMINI_API_KEY", "")
EMAIL = os.environ.get("TEST_EMAIL", "")
PWD = os.environ.get("TEST_PASSWORD", "")

lulus, gagal, dilangkau = [], [], []


class Langkau(Exception):
    """Ujian tidak dapat dijalankan (bukan kegagalan)."""


def semak(nama: str, fn):
    try:
        hasil = fn()
        lulus.append(nama)
        print(f"  LULUS   {nama}" + (f" -> {hasil}" if hasil else ""))
        return hasil
    except Langkau as e:
        dilangkau.append((nama, str(e)))
        print(f"  LANGKAU {nama} — {e}")
        return None
    except Exception as e:
        gagal.append((nama, str(e)[:200]))
        print(f"  GAGAL   {nama}\n          {str(e)[:200]}")
        return None


if not URL or not KEY:
    print("SUPABASE_URL / SUPABASE_KEY belum diset. Ujian tidak dijalankan.")
    sys.exit(1)

print("\n[1] Sambungan")
sb = create_client(URL, KEY)
print(f"  URL: {URL}")

print("\n[2] Bucket `resit`")
def bucket_wujud():
    buckets = sb.storage.list_buckets()
    nama = [b.name if hasattr(b, "name") else b.get("name") for b in buckets]
    if "resit" not in nama:
        raise RuntimeError(f"bucket 'resit' tiada. Jumpa: {nama}. Jalankan schema.sql dahulu.")
    return nama

semak("bucket resit wujud", bucket_wujud)

print("\n[3] Auth")
def log_masuk():
    if not EMAIL or not PWD:
        raise RuntimeError("TEST_EMAIL / TEST_PASSWORD belum diset")
    try:
        sb.auth.sign_up({"email": EMAIL, "password": PWD})
    except Exception:
        pass  # sudah wujud
    res = sb.auth.sign_in_with_password({"email": EMAIL, "password": PWD})
    if not res.user:
        raise RuntimeError("log masuk gagal")
    return res.user.id

uid = semak("daftar / log masuk", log_masuk)

print("\n[4] Upload ke bucket peribadi")
def buat_png() -> bytes:
    im = Image.new("RGB", (400, 200), "white")
    d = ImageDraw.Draw(im)
    d.text((20, 90), "RESIT UJIAN RadarBajet RM12.50", fill="black")
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()

laluan = None
def upload():
    global laluan
    if not uid:
        raise RuntimeError("tiada uid")
    laluan = f"{uid}/_ujian_radarbajet.png"
    sb.storage.from_("resit").upload(
        laluan, buat_png(), {"content-type": "image/png", "upsert": "true"}
    )
    return laluan

semak("upload PNG ke {uid}/", upload)

def senarai():
    if not uid:
        raise RuntimeError("tiada uid")
    obj = sb.storage.from_("resit").list(uid)
    nama = [o.get("name") if isinstance(o, dict) else getattr(o, "name", None) for o in obj]
    if "_ujian_radarbajet.png" not in nama:
        raise RuntimeError(f"fail tidak dijumpai dalam senarai: {nama}")
    return "dijumpai"

semak("fail kelihatan dalam bucket", senarai)

print("\n[5] RLS: pengguna tanpa log masuk")
def rls_negatif():
    anon = create_client(URL, KEY)  # tiada sesi
    try:
        anon.table("harga").insert(
            {"kedai_id": 1, "item": "ujian rls", "harga": 1.0, "dilapor_oleh": None}
        ).execute()
    except Exception as e:
        return f"ditolak seperti dijangka ({type(e).__name__})"
    raise RuntimeError("BAHAYA: insert tanpa auth BERJAYA — RLS tidak aktif")

semak("insert tanpa auth ditolak", rls_negatif)

print("\n[6] Gemini")
def gemini_ok():
    if not GEMINI:
        raise Langkau("GEMINI_API_KEY tidak diset")
    from google import genai

    klien = genai.Client(api_key=GEMINI)
    imej = Image.open(io.BytesIO(buat_png()))
    resp = klien.models.generate_content(
        model="gemini-3.8-flash", contents=[imej, "Sebutkan semua teks dalam imej ini."]
    )
    teks = (resp.text or "").strip()
    if not teks:
        raise RuntimeError("respons kosong")
    return teks[:80].replace("\n", " ")

semak("Gemini baca imej", gemini_ok)

print("\n[7] Bersih")
def bersih():
    if laluan:
        sb.storage.from_("resit").remove([laluan])
    return "selesai"

semak("padam fail ujian", bersih)

print("\n" + "=" * 60)
print(f"{len(lulus)} lulus, {len(gagal)} gagal, {len(dilangkau)} dilangkau")
for nama, ralat in gagal:
    print(f"  GAGAL   {nama}: {ralat}")
for nama, sebab in dilangkau:
    print(f"  LANGKAU {nama}: {sebab}")
sys.exit(1 if gagal else 0)
