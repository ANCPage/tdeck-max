#pragma once
#include "app.hpp"

// E-paper renderer. Draws the full 320x240 frame into GxEPD2 and picks the
// refresh path:
//   * Full refresh  : boot, tab change, every kPartialMax partial updates
//     (UC8253 panels ghost if you only ever do partial refreshes)
//   * Partial       : whole-canvas fast partial refresh for key feedback
// All geometry constants live at the top of ui.cpp — move boxes/rows freely
// without touching drawing logic.

class Ui {
public:
    enum Refresh { RefreshFull, RefreshPartial };

    explicit Ui(App& app) : m_app(app) {}

    void init();             // e-paper setup + first (full) frame
    void render(Refresh r);  // redraw now, using full or partial update

private:
    App& m_app;
    int  m_partialSinceFull = 0;

    void drawScreen();       // draws the complete frame from app state
    void drawHeader();
    void drawFieldRow(char label, const char* value, bool active, int y);
    void drawBanner();
    void drawFooter();
    void textInBox(int x, int y, int w, int h, const char* s,
                   const void* font, bool invert);  // horizontally+vertically centered
};
