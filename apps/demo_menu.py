# Demo: a custom menu, and custom UI screens behind it — three archetypes:
#   MenuScreen       list + inverted selection (j/k move, ENT open, DEL back)
#   GreenhouseScreen dashboard with meter bars (the "custom UI")
#   FeederScreen     log list (ENT appends an entry)
#   WikiScreen       scrolled text page (j/k scroll)
#
# Keys here are LETTERS: decode_raw(raw, letters=True). The same file runs on the
# device and in the simulator.

from tdeckmax import WIDTH, HEIGHT, CELL
from tdeckmax.screen import Screen, draw_chrome, bar

ITEM_H = 30
LIST_TOP = 44


class GreenhouseScreen(Screen):
    title = "GREENHOUSE"
    hints = ("r: refresh   DEL: back to menu", "link: LoRa sensor node (planned)")

    def __init__(self):
        self.moisture = 0.62
        self.temp = 0.41

    def handle(self, key, app):
        kind, val = key
        if kind == "ctl" and val in ("back", "space"):
            app.pop()
            return True
        if kind == "char" and val == "r":
            self.moisture = min(1.0, self.moisture + 0.06)
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app, right="LIVE")
        pct = "%d%%" % round(self.moisture * 100)
        bar(fb, 16, 66, WIDTH - 32, 16, self.moisture, "SOIL MOISTURE", pct)
        bar(fb, 16, 122, WIDTH - 32, 16, self.temp, "TEMPERATURE", "24.1C")
        fb.text("battery 87%    last sync 6m ago", 16, 158, 0)
        fb.text("no mains: solar + LoRa node", 16, 174, 0)


class FeederScreen(Screen):
    title = "FEEDER LOG"
    hints = ("ENT: log a feed   DEL: back", "newest first")

    def __init__(self):
        self.entries = ["20:10  bottle 90ml", "23:40  bottle 60ml",
                        "03:15  nappy (wet)"]
        self.count = 3

    def handle(self, key, app):
        kind, val = key
        if kind == "ctl" and val in ("back", "space"):
            app.pop()
            return True
        if kind == "ctl" and val == "enter":
            self.count += 1
            self.entries.insert(0, "--:--  feed #%d" % self.count)
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app, right="%d today" % self.count)
        for i, line in enumerate(self.entries[:5]):
            fb.text(line, 16, LIST_TOP + i * 22, 0)


class WikiScreen(Screen):
    title = "POCKET WIKI"
    hints = ("j/k scroll   DEL: back", "source: ~/wiki (synced over WiFi)")

    LINES = [
        "GREENHOUSE / MISTING",
        "daily misting, no mains power.",
        "check soil before 9am; skip if",
        "rain forecast > 3mm.",
        "",
        "FILM / KODAK i60",
        "fixed 1.2m, no macro. meter for",
        "the shadows, not the highlights.",
        "",
        "D&D / HOUSE RULES",
        "death saves in the open, dice on",
        "the table, no takebacks.",
    ]

    def __init__(self):
        self.offset = 0

    def handle(self, key, app):
        kind, val = key
        if kind == "ctl" and val in ("back", "space"):
            app.pop()
            return True
        if kind == "char" and val == "j":
            self.offset = min(max(0, len(self.LINES) - 13), self.offset + 1)
            return True
        if kind == "char" and val == "k":
            self.offset = max(0, self.offset - 1)
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app, right="%d/%d" % (self.offset + 1, len(self.LINES)))
        for row, line in enumerate(self.LINES[self.offset:self.offset + 12]):
            fb.text(line, 16, LIST_TOP + row * 14, 0)


class MenuScreen(Screen):
    title = "T-DECK MAX"
    hints = ("j/k move   ENT: open", "DEL: back   r: refresh")

    ITEMS = (
        ("Greenhouse", GreenhouseScreen),
        ("Feeder log", FeederScreen),
        ("Pocket wiki", WikiScreen),
    )

    def __init__(self):
        self.sel = 0
        # keep one instance per app so state survives menu round-trips
        self._screens = {}

    def handle(self, key, app):
        kind, val = key
        if kind == "char" and val == "j":
            self.sel = (self.sel + 1) % len(self.ITEMS)
            return True
        if kind == "char" and val == "k":
            self.sel = (self.sel - 1) % len(self.ITEMS)
            return True
        if kind == "ctl" and val == "enter":
            name, cls = self.ITEMS[self.sel]
            app.push(self._screens.setdefault(name, cls()))
            return True
        return False

    def render(self, fb, app):
        draw_chrome(fb, self, app, right="%d/%d" % (self.sel + 1, len(self.ITEMS)))
        for i, (name, _) in enumerate(self.ITEMS):
            y = LIST_TOP + i * ITEM_H
            if i == self.sel:
                fb.fill_rect(8, y - 6, WIDTH - 16, 26, 0)
                fb.text("> " + name, 16, y, 1)        # paper text on ink block
            else:
                fb.text("  " + name, 16, y, 0)
