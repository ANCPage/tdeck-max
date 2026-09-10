# Pure-python key decoding — no hardware imports, so this module is host-testable.
# Mirrors LILYGO factory firmware exactly:
#   * event FIFO codes: raw >= 129 = press, raw in 1..35 = release (see README
#     "PRESS_IS_BIT7" caveat — verify on device, one-constant fix if reversed)
#   * (row, col) split with the same mirrored column math as peri_keypad.cpp
#   * digits via the factory phone dialer's T9 convention (UP=1, 0=0, letters 2..9)

ROWS, COLS = 4, 10

# Physical grid. Tokens (non-letters): back, alt, ent, up, space, sym.
# '0' is the real bottom-row zero key; '$' is unassigned; '?' = no key.
KEYMAP = [
    list("qwertyuiop"),
    list("asdfghjkl") + ["back"],           # col 9 = DEL
    ["alt"] + list("zxcvbnm") + ["$", "ent"],
    ["?"] * 5 + ["up", "0", "space", "sym", "up"],
]

# T9 digit groups, straight from phone_keypad_to_digit() in ui_deckpro.cpp.
T9 = {
    "a": "2", "b": "2", "c": "2",
    "d": "3", "e": "3", "f": "3",
    "g": "4", "h": "4", "i": "4",
    "j": "5", "k": "5", "l": "5",
    "m": "6", "n": "6", "o": "6",
    "p": "7", "q": "7", "r": "7", "s": "7",
    "t": "8", "u": "8", "v": "8",
    "w": "9", "x": "9", "y": "9", "z": "9",
}

# Control tokens produced by special keys. (kind, value) keys:
#   ("digit", "0".."9")   append this digit to the focused field
#   ("ctl", token)        token in CONTROLS below
# Control tokens are deliberately generic — the decoder knows nothing about apps.
# tabs_calc maps "sym"/"alt" to tab switching and "enter" to field swap; a menu
# maps "enter" to "open" and "back" to "pop". Keep app semantics out of here.
CONTROLS = {
    "alt":   "alt",      # LILYGO's dialer used ALT='*'
    "sym":   "sym",      #                       SYM='#'
    "ent":   "enter",
    "back":  "back",
    "space": "space",
}

PRESS_MIN, PRESS_MAX = 129, 163   # raw FIFO codes for key presses (LILYGO)
RELEASE_MIN, RELEASE_MAX = 1, 35

# VERIFY-on-device knob: if presses arrive as 1..35 and releases as 129..163
# (Adafruit's datasheet notes say bit7 = release), swap these two ranges.
PRESS_IS_HIGH = True


def rowcol_from_code(code):
    """FIFO key code (0-based index) -> (row, col).

    Column math copied byte-for-byte from LILYGO's peri_keypad.cpp:
    ``col = (COLS-1) - code % COLS``. KEYMAP is written in the mirrored
    convention that their firmware uses, so keep this exactly as-is — do not
    "fix" the mirror or every key will land one key to the side.
    """
    return (code // COLS, (COLS - 1) - (code % COLS))


def decode_raw(raw, letters=False):
    """Decode one raw FIFO byte -> (kind, value) for a press, or None.

    kind is one of:
      ("char",  "j")        a printable character
      ("digit", "7")        numeric entry  (letters=False: T9 groups, UP=1, 0=0)
      ("ctl",   "enter")    control token (see CONTROLS)
      ("nav",   "up")       navigation key  (letters=True only)

    letters=False (default) = the factory dialer convention: letters act as T9
    digit groups, for number-entry apps. letters=True = the physical keycaps:
    letters are letters; UP becomes a navigation key. Release events -> None.
    """
    if PRESS_IS_HIGH and PRESS_MIN <= raw <= PRESS_MAX:
        code = raw - PRESS_MIN
    elif (not PRESS_IS_HIGH) and RELEASE_MIN <= raw <= RELEASE_MAX:
        code = raw - RELEASE_MIN
    else:
        return None

    row, col = rowcol_from_code(code)
    if not (0 <= row < ROWS and 0 <= col < COLS):
        return None

    key = KEYMAP[row][col]
    if key == "?" or key == "$":
        return None
    if key in CONTROLS:
        return ("ctl", CONTROLS[key])
    if key == "up":
        return ("nav", "up") if letters else ("digit", "1")
    if key == "0":
        return ("char", "0") if letters else ("digit", "0")
    if letters:
        return ("char", key)           # the letter printed on the keycap
    if key in T9:
        return ("digit", T9[key])
    return None
