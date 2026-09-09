#include "app.hpp"

App::App()
{
    for (int t = 0; t < kTabCount; t++) {
        resetText(m_tabs[t].a);
        resetText(m_tabs[t].b);
        m_tabs[t].focusB = false;
    }
}

bool App::handle(const Key& key, bool& wantFull)
{
    if (key.digit) {
        TabState& s = m_tabs[m_tab];
        appendDigit(s.focusB ? s.b : s.a, key.digitVal);
        return true;
    }
    switch (key.ctl) {
        case Key::CtlNone:      return false;
        case Key::CtlTabNext:   changeTab(+1, wantFull); return true;
        case Key::CtlTabPrev:   changeTab(-1, wantFull); return true;
        case Key::CtlFieldNext: m_tabs[m_tab].focusB = !m_tabs[m_tab].focusB; return true;
        case Key::CtlBack: {
            TabState& s = m_tabs[m_tab];
            backspace(s.focusB ? s.b : s.a);
            return true;
        }
        case Key::CtlClear: {
            TabState& s = m_tabs[m_tab];
            resetText(s.focusB ? s.b : s.a);
            return true;
        }
    }
    return false;
}

void App::changeTab(int delta, bool& wantFull)
{
    m_tab = (m_tab + delta + kTabCount) % kTabCount;
    wantFull = true;  // fresh tab -> full refresh clears any ghosting
}

void App::resetText(char* buf)
{
    buf[0] = '0';
    buf[1] = '\0';
}

void App::appendDigit(char* buf, char d)
{
    const int len = (int)strlen(buf);
    if (len == 1 && buf[0] == '0') {
        buf[0] = d;             // replace a lone leading zero
    } else if (len < kMaxDigits) {
        buf[len]     = d;
        buf[len + 1] = '\0';
    }
    // digits beyond kMaxDigits are dropped silently
}

void App::backspace(char* buf)
{
    const int len = (int)strlen(buf);
    if (len > 1) {
        buf[len - 1] = '\0';
    } else {
        buf[0] = '0';           // never leave the field empty
        buf[1] = '\0';
    }
}
