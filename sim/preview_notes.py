# Render the Notes app to a PNG in the host simulator (same code as the device).
#   python3 sim/preview_notes.py [outdir]

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from apps.notes import NotesScreen                      # noqa: E402
from sim.pil_fb import PilFrameBuffer                   # noqa: E402
from tdeckmax import HEIGHT, WIDTH                      # noqa: E402
from tdeckmax.planner import Planner                    # noqa: E402
from tdeckmax.screen import App                         # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/tdeck-max/preview")
os.makedirs(OUT, exist_ok=True)

app = App(Planner(epd=None), PilFrameBuffer(WIDTH, HEIGHT))
s = NotesScreen()
app.push(s)

for line in ("Lilygo T-Deck Max notes", "keys verified 29 Sep", "", "still to do:", "- GPS antenna (IPEX J2)", "- slide-in keyboard test"):
    for ch in line:
        s.handle(("char", ch), app)
    s.handle(("ctl", "enter"), app)

app.paint()
path = os.path.join(OUT, "10_notes.png")
app.fb.save(path)
print("wrote", path)
