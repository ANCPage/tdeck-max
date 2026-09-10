# Render the demo app's screens to PNGs on the Pi — the same state->frame code
# the device will run, with framebuf swapped for the PIL stand-in.
#
# Usage:  python3 sim/preview.py            (writes to ~/tdeck-max/preview)
#         PREVIEW_DIR=out python3 ...       (CI: writes to ./out)
#
# It also prints, per step, what the refresh planner decided and the dirty
# rectangle — the windowed-partial-refresh groundwork, made visible.

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tdeckmax import WIDTH, HEIGHT                      # noqa: E402
from tdeckmax.planner import Planner, diff_rect         # noqa: E402
from tdeckmax.screen import App                         # noqa: E402
from apps.demo_menu import MenuScreen                   # noqa: E402
from sim.pil_fb import PilFrameBuffer                   # noqa: E402

OUT = os.environ.get("PREVIEW_DIR", os.path.expanduser("~/tdeck-max/preview"))
os.makedirs(OUT, exist_ok=True)

fb = PilFrameBuffer(WIDTH, HEIGHT)
planner = Planner(epd=None)          # host: no panel, frames stay in the buffer
app = App(planner, fb)
app.push(MenuScreen())

prev_bytes = None


def shot(name, *keys):
    """Apply keys in order, paint once (coalesced), save PNG, report the plan."""
    global prev_bytes
    for key in keys:
        app.handle(key)
    policy = planner.paint(fb, fb, app.top(), app, full=app.full)
    app.full = False
    frame = fb.tobytes_msb()
    rect = diff_rect(prev_bytes, frame) if prev_bytes else None
    prev_bytes = frame
    fb.save(os.path.join(OUT, name + ".png"))
    print("%-24s %-28s refresh=%-4s dirty_rect=%s" % (
        name, str(keys), policy, rect))


# menu: selection starts on item 0 (Greenhouse)
shot("01_menu")
shot("02_menu_feeder", ("char", "j"))          # selection -> Feeder log
shot("03_menu_wiki", ("char", "j"))            # selection -> Pocket wiki
shot("04_menu_wrap", ("char", "j"))            # wraps back to Greenhouse

# open the greenhouse dashboard, then refresh the sensor reading
shot("05_greenhouse", ("ctl", "enter"))
shot("06_greenhouse_refresh", ("char", "r"))   # only the meter moves

# back to the menu, into the feeder log, and log a feed
shot("07_feeder", ("ctl", "back"), ("char", "j"), ("ctl", "enter"))
shot("08_feeder_logged", ("ctl", "enter"))

# back out, into the wiki page, scroll down
shot("09_wiki", ("ctl", "back"), ("char", "j"), ("ctl", "enter"), ("char", "j"))
print("done ->", OUT)
