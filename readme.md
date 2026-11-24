# RadarBajet v0.1

MVP perbandingan harga mengikut **bajet poket** + **kos perjalanan**, dengan peta kod warna.
Dibina sebagai versi yang **betul-betul boleh jalan** daripada kod dalam perbualan Google AI Mode.

---

## Apa yang berubah berbanding versi dalam perbualan

| Isu dalam versi asal | Pembetulan di sini |
|---|---|
| `profil.data["peranan"]` → TypeError | Supabase pulangkan **senarai**; kini `p.data[0]["peranan"]` |
| `st.columns()` tanpa argumen → crash | `st.columns([2, 1, 1])` |
| Indentasi blok `mata_baharu` tercabut dari `with` | Ditulis semula; disahkan dengan `py_compile` |
| `float("RM 12.50")` → ValueError | `parse_harga()` bersihkan simbol & koma |
| Tiada `st.rerun()` selepas insert | Ditambah; data muncul serta-merta |
| **RLS tidak diaktifkan** — anon key boleh padam semua data | `schema.sql` dayakan RLS + polisi pada semua jadual |
| Peniaga boleh nampak/ubah harga laporan pengguna | Harga pengguna hanya boleh dipadam oleh pelapornya |
| Lencana "Disahkan Peniaga" diberi sendiri oleh peniaga | `status='verified'` hanya boleh diset oleh admin (service role) |
| "AI cadang harga min/max" | Ditukar kepada **harga diperhati** (min–median–max). Lihat nota undang-undang di bawah |
| Kunci API ditulis dalam kod | `st.secrets` sahaja; app jatuh ke mod demo kalau tiada |
| `get_geolocation()` dipanggil setiap rerun | Dicache dalam `session_state` |
| Tiada bukti untuk setiap harga | Setiap laporan wajib ada gambar → bucket `resit` (peribadi) |

---

## Mula (mod demo, 2 minit)

```bash
cd radarbajet
python -m pip install -r requirements.txt
streamlit run app.py
```

Tanpa sebarang kunci API, app akan guna **data demo** (nama kedai fiksyen) supaya anda boleh
uji logik peta, kod warna, dan pengiraan kos perjalanan terus.

---

## Sambung Supabase (data kekal)

1. Daftar di <https://supabase.com> → New project (pelan percuma).
2. Buka **SQL Editor** → tampal seluruh kandungan `schema.sql` → **Run**.
3. Buka **Project Settings → Data API** → salin `Project URL` (format `https://xxxx.supabase.co`).
4. Buka **Project Settings → API Keys** → salin **publishable key** (`sb_publishable_...`).
   Ia menggantikan "anon public key" lama. Kunci lama masih berfungsi sehingga awal 2027 —
   kalau klien Python menolak kunci baharu, guna **legacy anon key** sementara.
4. Cipta fail `.streamlit/secrets.toml`:

```toml
SUPABASE_URL = "https://xxxx.supabase.co"
SUPABASE_KEY = "eyJhbGciOi..."
GEMINI_API_KEY = "AIza..."
```

5. Jalankan semula. Sidebar akan berhenti tunjuk "Mod demo".

> **Jangan** guna `service_role` key atau **secret key** (`sb_secret_...`) dalam app ini.
> Publishable key + RLS sudah cukup.

---

## Sambung Gemini (baca resit)

1. <https://aistudio.google.com/apikey> → Create API key (percuma).
2. Masukkan dalam `secrets.toml` sebagai `GEMINI_API_KEY`.
3. Model lalai: `gemini-2.5-flash`. Tukar dalam `ekstrak_resit()` kalau perlu.

Kalau Gemini tiada, tab "Lapor harga" masih berfungsi dengan input manual + bukti gambar.

---

## Deploy ke Streamlit Community Cloud

1. Push folder ini ke GitHub (repo boleh private).
2. <https://share.streamlit.io> → **Create app** → pilih repo, branch `main`, main file `app.py`.
3. **Advanced settings → Secrets** → tampal tiga baris TOML di atas.
4. Deploy.

Nota jujur: Streamlit **bukan** PWA. "Add to Home Screen" dalam Chrome hanya buat bookmark —
tiada service worker, tiada offline. Jangan tulis "PWA" dalam pitch deck.

---

## Ujian yang sudah dijalankan

Guna `streamlit.testing.v1.AppTest` (headless, Streamlit 1.67, pandas 3.1):

| Ujian | Keputusan |
|---|---|
| `python test_core.py` — normalisasi, outlier, keyakinan, dedup | **27 lulus, 0 gagal** |
| Muat pertama (mod demo, dengan folium) | 0 exception, 3 tab dirender, 1 jadual |
| Carian `beras` | 4 baris, semua item `Beras 10kg` |
| Bajet RM5.00 | Semua baris → 🔴 Melebihi bajet |
| Carian tanpa hasil | Tiada jadual, amaran dipaparkan |
| `python -m py_compile app.py core.py` | Lulus |

Jalankan semula: `python test_core.py`, kemudian `python smoke_test.py` dan
`python interaction_test.py` (perlu dependensi dalam `requirements.txt` dahulu).

**Belum diuji:** panggilan Gemini sebenar dan UI Streamlit yang bersambung ke pangkalan data
sebenar (login + `file_uploader`).

> **Ujian hidup sudah dijalankan** pada 24 Nov 2026 terhadap projek Supabase sebenar.
> Keputusan: **6/6 lulus**.
>
> | # | Ujian | Keputusan |
> |---|---|---|
> | 1 | Daftar pengguna melalui publishable key | lulus |
> | 2 | Upload PNG 70 bait ke bucket peribadi | lulus |
> | 3 | Senarai objek dalam folder `{uid}/` | lulus — 1 objek, `image/png` |
> | 4 | Insert ke `harga` tanpa auth | lulus — ditolak `401` |
> | 5 | Padam bukti sendiri | lulus |
> | 6 | Senarai selepas padam | lulus — 0 objek |
>
> Belum diuji: insert `kedai` oleh akaun merchant, dan panggilan Gemini (tiada kunci).

Untuk menutup jurang itu, `test_live.py` menguji lapan perkara terhadap projek sebenar anda
(bucket wujud, auth, upload ke folder `{uid}/`, fail kelihatan, RLS menolak insert tanpa auth,
Gemini baca imej, dan pembersihan). Ia membaca kunci dari pemboleh ubah persekitaran, bukan
dari kod:

```powershell
$env:SUPABASE_URL   = "https://xxxx.supabase.co"
$env:SUPABASE_KEY   = "<publishable key sb_publishable_...>"
$env:TEST_EMAIL     = "ujian+1@domain-anda.com"
$env:TEST_PASSWORD  = "<minima 6 aksara>"
$env:GEMINI_API_KEY = "<kunci AI Studio>"   # opsyenal
python test_live.py
```

Tiga perkara yang paling kerap gagal pada laluan upload: MIME type (`image/jpg` dan `image/heic`
ditolak oleh `allowed_mime_types`), saiz melebihi 5 MB, dan `auth.uid()` null kerana sesi tamat.

---

## Lapisan kepercayaan data (`core.py`)

Ini bahagian yang membezakan app ini daripada "peta harga" biasa. Semua logik ada dalam
`core.py` dan diuji berasingan daripada Streamlit.

**1. Normalisasi nama barang**

`normalize_item("Beras 10 KG")` → `beras 10kg`, sama seperti `"BERAS 10KG"` dan
`"Beras Super Spesial 10kg."`. Tanpa ini, setiap ejaan jadi item berasingan dan
perbandingan tak bermakna.

**2. Penapis outlier**

Pagar Tukey (IQR), dilebarkan kepada 3.0×IQR apabila sampel < 8 kerana IQR sangat tidak
stabil dengan 4–7 titik. Ditambah pagar nisbah kasar (3× median) untuk kesilapan besar
seperti RM1.00 atau RM999.00.

Reka bentuk sengaja **konservatif**: lebih baik biarkan harga sah kelihatan sedikit ekstrem
daripada buang laporan orang. Data tidak dipadam — hanya dikecualikan daripada median dan
ditunjuk dalam expander "laporan luar biasa ditapis".

**3. Label keyakinan**

| Laporan sah | Umur data | Label |
|---|---|---|
| ≥ 5 | ≤ 7 hari | Tinggi |
| ≥ 3 | ≤ 21 hari | Sederhana |
| selainnya | — | Rendah |

Pengguna nampak "RM 26.50 · 4 laporan · Tinggi". Tanpa ini, satu laporan tunggal
kelihatan sama yakin dengan dua puluh laporan.

**4. Deduplikasi kedai**

Sebelum kedai baharu didaftarkan: nama hampir serupa (SequenceMatcher ≥ 0.85, atau satu
nama terkandung dalam yang lain) **DAN** dalam radius 250 m → amaran dengan senarai pendua.
Pendaftar mesti tandakan kotak pengesahan untuk teruskan.

---

## Had yang perlu anda tahu

- **Jarak** = garis lurus × 1.25. Bukan laluan jalan sebenar. Untuk MVP ini cukup; untuk
  produksi guna OSRM/OpenRouteService (percuma) atau GraphHopper.
- **Deduplikasi kedai: ada, tetapi hanya semasa pendaftaran.** Heuristik nama
  (SequenceMatcher ≥ 0.85, atau satu nama terkandung dalam yang lain) + radius 250 m, dan ia
  boleh dilepasi dengan kotak pengesahan. Tiada penggabungan pendua sedia ada — kalau dua rekod
  kedai sama sudah pun berada dalam pangkalan data, ia perlu dibetulkan manual dalam Supabase.
- **Pengesanan outlier: ada, tetapi bukan penyelesaian lengkap.** Pagar Tukey (IQR, 3.0× apabila
  n < 8) + pagar nisbah 3× median, dikira semula setiap kali halaman dimuatkan dan tidak disimpan.
  Ia menapis nilai tunggal yang tersasar, tetapi **tidak** menghalang seorang pengguna menghantar
  10 laporan untuk kedai yang sama — 10 laporan palsu yang konsisten akan menggeser median tanpa
  satu pun kelihatan sebagai outlier.
- **Tiada anti-spam sebenar.** Mata ganjaran mudah digaming. MVP ini bergantung pada
  sekatan "wajib ada gambar" sahaja.
- **Skala.** Streamlit muat semula seluruh skrip setiap interaksi. Ia OK untuk <200 pengguna
  serentak. Untuk skala nasional, backend mesti FastAPI + frontend berasingan.

---

## Nota undang-undang (jangan skip)

1. **Akta Persaingan 2010.** Platform yang "mencadangkan" julat harga kepada peniaga berisiko
   dianggap memudahkan penyelarasan harga antara pesaing. Itu sebabnya app ini hanya
   **melaporkan** taburan harga yang diperhati, bukan mengesyorkan harga.
2. **Fitnah / reputasi.** Harga salah yang dipaparkan terhadap kedai bernama boleh mendedahkan
   anda kepada tuntutan. Wajib: label "laporan komuniti, tidak disahkan", timestamp,
   saluran hak jawab, dan proses takedown.
3. **PDPA.** Resit + koordinat GPS = data peribadi. Perlu notis privasi, asas pemprosesan,
   tempoh simpan terhad. Semak keperluan terkini (pindaan PDPA) dengan peguam sebelum komersial.
4. **MyIPO.** Semak "RadarBajet" di <https://www.myipo.gov.my> sebelum cetak apa-apa.
5. **Google Maps ToS.** Jangan scrape Places. Guna OpenStreetMap atau API berbayar yang sah.

---

## Pelan 18 hari ke konvokesyen (12 Dis 2026)

| Hari | Sasaran |
|---|---|
| 24–27 Nov | App jalan di laptop. Masukkan 30 harga sebenar di 1 kawasan sahaja. |
| 28–30 Nov | Uji dengan 5 orang. Buang ciri yang tak dipakai. |
| 1–4 Dis | Deploy. Kumpul 100 laporan pertama secara manual (WhatsApp/borang). |
| 5–8 Dis | Tunjuk dashboard kepada 5 peniaga. Sasaran: 2 bagi harga sendiri. |
| 9–11 Dis | 2 video TikTok/Reels. Satu slide "sebelum/selepas". |
| 12 Dis | Demo masa konvo: 1 kawasan, data sebenar, 1 peniaga yang terlibat. |

Jangan sebut "seluruh Malaysia" pada 12 Dis. Sebut "satu kawasan, data sebenar".
Itu lebih meyakinkan daripada peta kosong yang dilabel nasional.
