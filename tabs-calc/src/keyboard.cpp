#include "keyboard.hpp"
#include "pins.h"
#include <Adafruit_TCA8418.h>

namespace {
Adafruit_TCA8418 s_keypad;

// Physical key grid, identical to LILYGO's factory/keypad examples.
// Rows top->bottom, col 0 = leftmost. Only letters and control keys are listed;
// anything else decodes to nothing. Control positions:
//   r1c9 DEL   r2c0 ALT   r2c9 ENT   r3c5 UP   r3c6 '0'   r3c7 SPACE   r3c8 SYM   r3c9 UP
const char kRows = 4;
const char kCols = 10;
const char kKeyLetter[kRows][kCols] = {
    {'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'},
    {'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l', '!'},   // '!' = DEL
    {'@', 'z', 'x', 'c', 'v', 'b', 'n', 'm', '$', '#'},   // '@' = ALT, '#' = ENT
    {'?', '?', '?', '?', '?', '^', '0', ' ', '~', '^'},   // '^' = UP, '~' = SYM
};
}  // namespace

bool Keyboard::init()
{
    if (!s_keypad.begin(PIN_KB_ADDR, &Wire)) {
        return false;
    }
    s_keypad.matrix(kRows, kCols);  // 4 rows x 10 cols; remaining pins stay inputs
    s_keypad.flush();
    return true;
}

bool Keyboard::poll(Key& out)
{
    if (s_keypad.available() <= 0) {
        return false;
    }
    const int raw = s_keypad.getEvent();
    if ((raw & 0x80) == 0) {
        return false;  // release event: consume and ignore
    }
    // Press code -> 0-based matrix index, then the same (row, col) split LILYGO
    // uses (col is mirrored, which their keymap table is written for).
    int idx = (raw & 0x7F) - 1;
    int row = idx / kCols;
    int col = (kCols - 1) - (idx % kCols);
    if (row < 0 || row >= kRows || col < 0 || col >= kCols) {
        return false;
    }
    out = decodeAt(row, col);
    return out.digit || out.ctl != Key::CtlNone;
}

Key Keyboard::decodeAt(int row, int col)
{
    const char c = kKeyLetter[row][col];
    switch (c) {
        case '!':  return Key::makeCtl(Key::CtlBack);        // DEL
        case '@':  return Key::makeCtl(Key::CtlTabPrev);     // ALT
        case '#':  return Key::makeCtl(Key::CtlFieldNext);   // ENT
        case '~':  return Key::makeCtl(Key::CtlTabNext);     // SYM
        case ' ':  return Key::makeCtl(Key::CtlClear);       // SPACE
        case '^':  return Key::makeDigit('1');               // UP keys dial "1"
        case '$':  return Key{};                             // unused symbol key
        case '?':  return Key{};                             // no key there
        case '0':  return Key::makeDigit('0');               // bottom-row 0 key
        default: {
            if (c >= 'a' && c <= 'z') {
                const char d = digitForLetter(c);
                return d ? Key::makeDigit(d) : Key{};
            }
            return Key{};
        }
    }
}

char Keyboard::digitForLetter(char c)
{
    switch (c) {
        case 'a': case 'b': case 'c': return '2';
        case 'd': case 'e': case 'f': return '3';
        case 'g': case 'h': case 'i': return '4';
        case 'j': case 'k': case 'l': return '5';
        case 'm': case 'n': case 'o': return '6';
        case 'p': case 'q': case 'r': case 's': return '7';
        case 't': case 'u': case 'v': return '8';
        case 'w': case 'x': case 'y': case 'z': return '9';
        default:  return '\0';
    }
}
