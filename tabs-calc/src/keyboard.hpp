#pragma once
#include <Arduino.h>

// One decoded key press, translated to something the app understands.
struct Key {
    enum Ctl {
        CtlNone = 0,
        CtlTabNext,    // SYM : switch to the next tab
        CtlTabPrev,    // ALT : switch to the previous tab
        CtlFieldNext,  // ENT : move editing between field A and field B
        CtlBack,       // DEL : backspace
        CtlClear,      // SPACE : clear the focused field
    };
    bool    digit;     // true  -> digitVal is a digit to append
    char    digitVal;  // '0'..'9' when digit == true
    Ctl     ctl;       // valid when digit == false

    static Key makeDigit(char d) { Key k{}; k.digit = true; k.digitVal = d; return k; }
    static Key makeCtl(Ctl c)    { Key k{}; k.ctl = c; return k; }
};

// Thin wrapper over Adafruit_TCA8418 that:
//   * drains press events only (release events are consumed and dropped)
//   * converts raw matrix positions to physical (row, col) exactly like LILYGO's
//     factory example (peri_keypad.cpp), so the letter grid matches the keycaps
//   * maps keys to digits using the SAME convention as the factory phone dialer
//     (phone_keypad_to_digit in ui_deckpro.cpp):
//         bottom-row '0' key  -> 0
//         UP keys             -> 1
//         a b c -> 2   d e f -> 3   g h i -> 4   j k l -> 5
//         m n o -> 6   p q r s -> 7   t u v -> 8   w x y z -> 9
//     (ALT -> prev tab, SYM -> next tab in this app instead of * and #)
class Keyboard {
public:
    bool init();            // Wire must already be started; returns false on failure
    bool poll(Key& out);    // true when a press was decoded; out is filled

private:
    static Key  decodeAt(int row, int col);   // row/col are "visual" (see README)
    static char digitForLetter(char c);       // T9 group digit, or 0 if not a letter
};
