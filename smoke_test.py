import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".deps"))
os.chdir(HERE)

from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=90)
at.run()

print("exceptions:", len(at.exception))
for e in at.exception:
    print("  EXC:", type(e.value).__name__, "->", e.value)

print("errors:", [x.value for x in at.error])
print("warnings:", [x.value for x in at.warning])
print("titles:", [t.value for t in at.title])
try:
    print("tabs:", [t.label for t in at.tabs])
except Exception as e:
    print("tabs: n/a", e)
print("dataframes:", len(at.dataframe))
print("markdown:", len(at.markdown))
print("sidebar success:", [x.value for x in at.sidebar.success])
print("sidebar info:", [x.value for x in at.sidebar.info])
