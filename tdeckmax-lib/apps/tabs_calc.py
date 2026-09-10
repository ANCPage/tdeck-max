# tabs_calc.py — the two-tab calculator, pure Python.
# Direct port of the C++ tabs-calc app (same state rules, same key mapping):
#   Tab 0 ADD, Tab 1 SUB; ENT switches field A/B; digits append; DEL backspace;
#   SPACE clears; SYM/ALT cycle tabs. Live result in the banner.
#
# First boot also draws a test frame and prints every decoded key to the REPL —
# use that to verify panel orientation and the key map before trusting the UI.

import time
from tdeckmax.board import Board
from tdeckmax.epd import UC8253
from tdeckmax.ui import EPaperUI, CELL
from tdeckmax.tca8418 import TCA8418

# --- constants (same layout idea as the C++ app) ------------------------------
XM = 12
FIELD_W = 256
FIELD_X = XM + 36 + 4            # label column, then the value box
ROW_H = 24

FULL = True
FAST = False

# --- state machine (ported from app.cpp) --------------------------------------
class Field:
    MAX_DIGITS = 6

    def __init__(self):
        self.text = "0"

    def digit(self, d: str) -> None:
        if self.text == "0":
            self.text = d
        elif len(self.text) < self.MAX_DIGITS:
            self.text += d

    def backspace(self) -> None:
        self.text = "0" if len(self.text) <= 1 else self.text[:-1]

    def clear(self) -> None:
        self.text = "0"

    def value(self) -> int:
        return int(self.text) if self.text.isdigit() else 0


class Tab:
    def __init__(self, subtract: bool):
        self.subtract = subtract
        self.a = Field()
        self.b = Field()
        self.focus_b = False

    def result(self) -> int:
        return (self.a.value() - self.b.value()) if self.subtract \
            else (self.a.value() + self.b.value())


class App:
    def __init__(self):
        self.tabs = [Tab(False), Tab(True)]   # ADD, SUB
        self.tab = 0
        self.want_full = True                 # first frame is full

    def cur(self) -> Tab:
        return self.tabs[self.tab]

    def _field(self) -> Field:
        t = self.cur()
        return t.b if t.focus_b else t.a

    def handle(self, key) -> bool:
        """key from TCA8418.read_key(); True if the screen changed."""
        if key is None:
            return False
        kind, value = key
        if kind == "digit":
            self._field().digit(value)
            return True
        # control (tokens are generic; this app decides what they mean)
        if value == "sym":                       # SYM = next tab
            self.tab = (self.tab + 1) % len(self.tabs)
            self.want_full = True
        elif value == "alt":                     # ALT = previous tab
            self.tab = (self.tab - 1) % len(self.tabs)
            self.want_full = True
        elif value == "enter":                   # ENT = swap A/B
            self.cur().focus_b = not self.cur().focus_b
        elif value == "back":                    # DEL = backspace
            self._field().backspace()
        elif value == "space":                   # SPACE = clear field
            self._field().clear()
        else:
            return False
        return True

# --- drawing ------------------------------------------------------------------
CHIP_LABELS = ("1 ADD", "2 SUB")
FOOT1 = "ENT field | DEL back | SPACE clear | SYM/ALT = tab"
FOOT2 = "digits: UP=1, key 0 = 0, letters abc=2 ... wxyz=9"


def draw(app: App, ui: EPaperUI) -> None:
    ui.clear()

    # header chips (active = filled black)
    chip_w = (320 - 2 * XM - 8) // 2
    for i, label in enumerate(CHIP_LABELS):
        x = XM + i * (chip_w + 8)
        if app.tab == i:
            ui.paper_text_in_ink_box(label, x, 4, chip_w, 24)
        else:
            ui.ink_text_in_box(label, x, 4, chip_w, 24)

    # field rows
    t = app.cur()
    for row_y, label, field, active in (
        (36, "A", t.a, not t.focus_b),
        (64, "B", t.b, t.focus_b),
    ):
        ui.ink_text(label, XM + 8, row_y + 8)
        if active:
            ui.paper_text_in_ink_box(field.text, FIELD_X, row_y, FIELD_W, ROW_H)
        else:
            ui.ink_box(FIELD_X, row_y, FIELD_W, ROW_H, filled=False)
            ui.ink_text(field.text, FIELD_X + 10, row_y + 8)

    # result banner
    ui.paper_text_in_ink_box(str(t.result()), XM, 100, 320 - 2 * XM, 96)

    # footer hints
    ui.ink_text(FOOT1, XM, 208)
    ui.ink_text(FOOT2, XM, 224)

# --- boot ----------------------------------------------------------------------
def main() -> None:
    board = Board()
    board.release_resets()                  # touch + keyboard out of reset
    print("board: i2c+spi up")

    kb = TCA8418(board.i2c)
    if not kb.begin():
        print("FATAL: no TCA8418 at 0x34")
        raise SystemExit(1)
    print("keyboard: 4x10 matrix ready")

    epd = UC8253(board.spi, board.epd_cs, board.epd_dc,
                 board.epd_rst, board.epd_busy)
    ui = EPaperUI(epd)
    app = App()

    # test frame: solid black band + white text -> check orientation/contrast
    draw(app, ui)
    ui.epd.full_refresh(ui.buf)             # boot = full refresh always
    app.want_full = False
    print("tabs_calc ready — type digits, ENT to switch field")

    while True:
        key = kb.read_key()
        if key is not None:
            print("key:", key)
            if app.handle(key):
                ui.render(app.want_full)
                app.want_full = False
        time.sleep_ms(20)


main()
