# Exercise the launcher, the chat screen and the navigation in the host
# simulator. Same screen code the device runs. No network: the chat's send() is
# deliberately NOT triggered here (that would post a real message to the agent).
#   python3 sim/preview_launcher.py [outdir]

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from apps.chat import ChatScreen                          # noqa: E402
from apps.launcher import LauncherScreen                  # noqa: E402
from apps.notes import NotesScreen                        # noqa: E402
from sim.pil_fb import PilFrameBuffer                     # noqa: E402
from tdeckmax import HEIGHT, WIDTH                        # noqa: E402
from tdeckmax.planner import Planner                      # noqa: E402
from tdeckmax.screen import App                           # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/tdeck-max/preview")
os.makedirs(OUT, exist_ok=True)

app = App(Planner(epd=None), PilFrameBuffer(WIDTH, HEIGHT))
notes = NotesScreen(path="/tmp/sim_notes.txt")
launcher = LauncherScreen()
launcher.provide("Notes", notes)

# a chat transcript, so the render can be checked without touching the network
chat = ChatScreen()
chat.messages = [
    ("you", "what is a t-deck max?"),
    ("hermes", "A LilyGO handheld: ESP32-S3, keyboard, small e-paper screen and LoRa."),
    ("you", "can you read my notes?"),
]
launcher.provide("Chat", chat)

app.push(launcher)

# 1. the launcher
app.paint()
app.fb.save(os.path.join(OUT, "11_launcher.png"))

# 2. ENT on sel 0 opens Chat; type (no send) and back out
launcher.handle(("ctl", "enter"), app)
assert app.top() is chat, "ENT should open Chat"
for ch in "hello hermes":
    app.handle(("char", ch))
app.handle(("ctl", "back"))                     # erase one char
assert chat.text == "hello herme", "backspace should erase one character"
chat.text = "hello hermes"
app.paint()
app.fb.save(os.path.join(OUT, "12_chat.png"))
for _ in range(len(chat.text)):
    app.handle(("ctl", "back"))
app.handle(("ctl", "back"))                     # empty input: back to launcher
assert app.top() is launcher, "DEL on an empty input should return to the launcher"

# 3. Notes through the menu
app.handle(("char", "j"))
app.handle(("ctl", "enter"))
assert app.top() is notes, "second item should be Notes"
for ch in "typed through the launcher":
    app.handle(("char", ch))
app.paint()
app.fb.save(os.path.join(OUT, "13_notes_via_launcher.png"))
for _ in range(len(notes.text) + 2):
    app.handle(("ctl", "back"))
assert app.top() is launcher, "DEL on an empty page should return to the launcher"

# 4. Device, then Net log
app.handle(("char", "j"))
app.handle(("ctl", "enter"))
assert app.top().__class__.__name__ == "DeviceScreen"
app.paint()
app.fb.save(os.path.join(OUT, "14_device.png"))
app.handle(("ctl", "back"))
app.handle(("char", "j"))
app.handle(("ctl", "enter"))
assert app.top().__class__.__name__ == "LogScreen"
app.paint()
app.fb.save(os.path.join(OUT, "15_netlog.png"))

print("wrote 11_launcher, 12_chat, 13_notes_via_launcher, 14_device, 15_netlog")
print("navigation: PASS (launcher -> chat -> notes -> device -> log, with back)")
