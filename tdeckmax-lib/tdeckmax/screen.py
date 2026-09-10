# Screen framework: every screen is "state -> one frame", plus a key handler.
# The same code runs on the device (MicroPython framebuf) and under the host
# simulator (PIL-backed stand-in) — screens never know which one they draw into.

from tdeckmax import WIDTH, HEIGHT, CELL

HEADER_H = 24
FOOTER_H = 24


class Screen:
    title = ""                 # drawn inverted in the header bar
    hints = ("", "")           # two footer lines — on a keyboard device the
                               # footer IS the list of things you can do here

    def enter(self, app):
        """Called when the screen is pushed (fresh state, full refresh)."""

    def handle(self, key, app):
        """key = (kind, value) from keys.decode_raw(). True -> needs repaint."""
        return False

    def render(self, fb, app):
        raise NotImplementedError


def draw_chrome(fb, screen, app, right=""):
    """White page + inverted header + footer hints. Every screen starts here."""
    fb.fill(1)                                   # 1 = white paper
    fb.fill_rect(0, 0, WIDTH, HEADER_H, 0)
    fb.text(screen.title, 8, 6, 1)               # paper text on the ink bar
    if right:
        fb.text(right, WIDTH - 8 - len(right) * CELL, 6, 1)
    foot = HEIGHT - FOOTER_H
    fb.hline(0, foot - 4, WIDTH, 0)
    fb.text(screen.hints[0], 8, foot, 0)
    fb.text(screen.hints[1], 8, foot + 12, 0)


def bar(fb, x, y, w, h, frac, label="", value=""):
    """Labelled meter — the e-ink way to show a number (outline + filled part)."""
    if label:
        fb.text(label, x, y - 14, 0)          # clear gap above the track
    if value:
        fb.text(value, x + w - len(value) * CELL, y - 14, 0)
    fb.rect(x, y, w, h, 0)
    inner = int((w - 4) * max(0.0, min(1.0, frac)))
    if inner > 0:
        fb.fill_rect(x + 2, y + 2, inner, h - 4, 0)


class App:
    """Owns the screen stack + the framebuffer. Screens stay pure."""

    def __init__(self, planner, fb, buf=None):
        self.planner = planner
        self.fb = fb                                  # drawing surface
        self.buf = fb if buf is None else buf         # raw bytes for the panel
        self.stack = []
        self.full = True                              # next paint = full refresh

    def push(self, screen):
        self.stack.append(screen)
        screen.enter(self)
        self.full = True
        return screen

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()
            self.full = True

    def top(self):
        return self.stack[-1]

    def handle(self, key):
        if key is None:
            return False
        return self.top().handle(key, self)

    def paint(self):
        self.planner.paint(self.fb, self.buf, self.top(), self, full=self.full)
        self.full = False
