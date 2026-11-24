import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (HERE, os.path.join(HERE, ".deps")):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
os.chdir(HERE)

from streamlit.testing.v1 import AppTest


def cari_widget(koleksi, label):
    for w in koleksi:
        if w.label == label:
            return w
    raise LookupError(f"widget '{label}' tidak dijumpai: {[x.label for x in koleksi]}")


at = AppTest.from_file("app.py", default_timeout=90)
at.run()

print("== baseline ==")
print("exceptions:", len(at.exception))
print("semua number_input:", [w.label for w in at.number_input])
print("semua text_input:", [w.label for w in at.text_input])
df = at.dataframe[0].value
print("baris:", len(df))
print("kolum:", list(df.columns))
print("label keyakinan:", sorted(set(df["Keyakinan"])))

print("\n== carian 'beras' ==")
cari_widget(at.text_input, "Cari barang atau servis").set_value("beras").run()
print("exceptions:", len(at.exception))
df = at.dataframe[0].value
print("baris:", len(df), "| kedai:", sorted(set(df["Kedai"])))
print("n laporan:", list(df["Laporan"]))

print("\n== carian 'BERAS 10 KG' (normalisasi) ==")
cari_widget(at.text_input, "Cari barang atau servis").set_value("BERAS 10 KG").run()
df = at.dataframe[0].value
print("baris:", len(df), "| exceptions:", len(at.exception))

print("\n== bajet RM5 (widget betul) ==")
cari_widget(at.number_input, "Bajet (RM)").set_value(5.0).run()
df = at.dataframe[0].value
print("status:", sorted(set(df["Status"])))
print("exceptions:", len(at.exception))

print("\n== carian kosong ==")
cari_widget(at.text_input, "Cari barang atau servis").set_value("zzz tidak wujud").run()
print("exceptions:", len(at.exception))
print("dataframes:", len(at.dataframe))
print("amaran dijumpai:", any("zzz" in w.value for w in at.warning))
