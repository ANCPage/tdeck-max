# Launcher: the boot screen. A list of apps; j/k to move, ENT to open, DEL to
# come back. One instance per app is kept so state survives a round trip
# (typing in Notes, going to Device, coming back: the page is still there).

from tdeckmax import CELL, WIDTH
from tdeckmax.screen import Screen, draw_chrome
from apps.chat import ChatScreen
from apps.device import DeviceScreen, LogScreen
from apps.notes import NotesScreen

ITEM_H = 30
LIST_TOP = 44


class LauncherScreen(Screen):
    title = "T-DECK MAX"
    hints = ("j/k move   ENT: open", "DEL: back from an app")

    ITEMS = (
        ("Chat", ChatScreen),
        ("Notes", NotesScreen),
        ("Device", DeviceScreen),
        ("Net log", LogScreen),
    )

    def __init__(self):
        self.sel = 0
        self._screens = {}             # one instance per app, kept alive

    def provide(self, name, screen):
        """Let main.py hand in an instance it also keeps a reference to (it
        updates the Notes header with battery/address, so it needs that object)."""
        self._screens[name] = screen
        return screen

    def handle(self, key, app):
        kind, val = key
        if kind == "char" and val == "j":
            self.sel = (self.sel + 1) % len(self.ITEMS)
            return True
        if kind == "char" and val == "k":
            self.sel = (self.sel - 1) % len(self.ITEMS)
            return True
        if kind == "ctl" and val == "enter":
            name, factory = self.ITEMS[self.sel]
            app.push(self._screens.setdefault(name, factory()))   # keep state
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app, right="%d/%d" % (self.sel + 1, len(self.ITEMS)))
        for i, (name, _) in enumerate(self.ITEMS):
            y = LIST_TOP + i * ITEM_H
            if i == self.sel:
                fb.fill_rect(8, y - 6, WIDTH - 16, 26, 0)
                fb.text("> " + name, 16, y, 1)      # paper text on ink block
            else:
                fb.text("  " + name, 16, y, 0)
        # the launcher is the only place to see the essentials at a glance
        fb.hline(8, 190, WIDTH - 16, 0)
        fb.text("boot screen: pick an app above", 16, 200, 0)
        fb.text("ALT caps  SYM 123  DEL back", 16, 216, 0)
