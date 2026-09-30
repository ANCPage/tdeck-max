# Exercise the launcher in the host simulator: render it, open each app, come
# back, and type into Notes through the menu. Same code the device runs.
#   python3 sim/preview_launcher.py [outdir]

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from apps.launcher import LauncherScreen                # noqa: E402
from apps.notes import NotesScreen                      # noqa: E402
from sim.pil_fb import PilFrameBuffer                   # noqa: E402
from tdeckmax import HEIGHT, WIDTH                      # noqa: E402
from tdeckmax.planner import Planner                    # noqa: E402
from tdeckmax.screen import App                         # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/tdeck-max/preview")
os.makedirs(OUT, exist_ok=True)

app = App(Planner(epd=None), PilFrameBuffer(WIDTH, HEIGHT))
notes = NotesScreen(path="/tmp/sim_notes.txt")
try:
    os.remove("/tmp/sim_notes.txt")
except OSError:
    pass
notes.text = ""
launcher = LauncherScreen()
launcher.provide("Notes", notes)
app.push(launcher)

# 1. the launcher itself
app.paint()
app.fb.save(os.path.join(OUT, "11_launcher.png"))

# 2. open the highlighted app (Notes), type, and check it is reachable
launcher.handle(("ctl", "enter"), app)                 # Screen.handle(key, app)
assert app.top() is notes, "ENT should open Notes"
for line in ("Notes via the launcher", "navigation test"):
    for ch in line:
        app.handle(("char", ch))                       # App.handle(key)
    app.handle(("ctl", "enter"))
app.paint()
app.fb.save(os.path.join(OUT, "12_notes_via_launcher.png"))

# 3. DEL on an empty page returns to the launcher; k/j move the selection
for _ in range(len(notes.text) + 2):
    app.handle(("ctl", "back"))
assert app.top() is launcher, "DEL on an empty page should return to the launcher"
app.handle(("char", "j"))
assert launcher.sel == 1, "j should move the selection"
app.handle(("ctl", "enter"))
assert app.top().__class__.__name__ == "DeviceScreen", "ENT should open the Device screen"
app.paint()
app.fb.save(os.path.join(OUT, "13_device.png"))

# 4. back, then into the log screen
app.handle(("ctl", "back"))
app.handle(("char", "j"))
app.handle(("ctl", "enter"))
app.paint()
app.fb.save(os.path.join(OUT, "14_netlog.png"))

print("wrote 11_launcher.png, 12_notes_via_launcher.png, 13_device.png, 14_netlog.png")
print("navigation: PASS (launcher -> notes -> back -> device -> log)")
