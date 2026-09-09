#pragma once
#include <Arduino.h>
#include "keyboard.hpp"

// App state: two tabs, each a tiny A op B form.
//   Tab 0 = ADD       (a + b)
//   Tab 1 = SUBTRACT  (a - b)
// Numbers are kept as text (digit entry is per-key append/backspace) and parsed
// when the result is needed. No floats, no malloc, no String objects.

class App {
public:
    static const int  kTabCount  = 2;
    static const int  kFieldLen  = 8;   // 6 digits + NUL + slack
    static const int  kMaxDigits = 6;   // caps entry at 999999

    struct TabState {
        char  a[kFieldLen];
        char  b[kFieldLen];
        bool  focusB;                   // false = editing A, true = editing B
    };

    App();

    // Feed one key in. Returns true when the visible state changed (render).
    // Sets wantFull when a full (not partial) e-paper refresh is warranted.
    bool handle(const Key& key, bool& wantFull);

    int  currentTab() const { return m_tab; }
    bool isAddTab()   const { return m_tab == 0; }

    const TabState& cur() const { return m_tabs[m_tab]; }

    int  valueA() const { return atoi(cur().a); }
    int  valueB() const { return atoi(cur().b); }
    int  result() const { return isAddTab() ? valueA() + valueB() : valueA() - valueB(); }

private:
    TabState m_tabs[kTabCount];
    int      m_tab = 0;

    static void resetText(char* buf);
    static void appendDigit(char* buf, char d);
    static void backspace(char* buf);
    void        changeTab(int delta, bool& wantFull);
};
