#include "ui.hpp"
#include "pins.h"

#include <SPI.h>
#include <GxEPD2_BW.h>
#include <Fonts/FreeMonoBold12pt7b.h>
#include <Fonts/FreeMonoBold18pt7b.h>
#include <Fonts/FreeMonoBold24pt7b.h>

// ---------------------------------------------------------------------------
// Layout (320x240 landscape). Tweak freely — every box/row is a constant here.
// ---------------------------------------------------------------------------
namespace {
const int kScreenW = 320;
const int kScreenH = 240;

const int kXMargin  = 12;   // outer margin
const int kBoxW     = kScreenW - 2 * kXMargin;   // full-width content box
const int kLabelW   = 36;   // width of the "A:" / "B:" label column
const int kValueX   = kXMargin + kLabelW + 4;    // value box left edge
const int kValueW   = kBoxW - kLabelW - 4;       // value box width

const int kHeaderY  = 4;    // tab chips
const int kHeaderH  = 22;

const int kRowAY    = 40;   // field A box (y, h)
const int kRowBY    = 76;   // field B box starts 4px below A
const int kRowH     = 32;

const int kBannerY  = 116;  // result banner
const int kBannerH  = 88;

const int kFootY1   = 212;  // classic 5x7 footer lines (top-left origin)
const int kFootY2   = 224;

const int kPartialMax = 10; // full refresh after this many partial updates

// The panel instance. Class/template line copied from LILYGO's display example.
GxEPD2_BW<GxEPD2_310_GDEQ031T10, GxEPD2_310_GDEQ031T10::HEIGHT> epd(
    GxEPD2_310_GDEQ031T10(PIN_EPD_CS, PIN_EPD_DC, PIN_EPD_RST, PIN_EPD_BUSY));
}  // namespace

// ---------------------------------------------------------------------------
void Ui::init()
{
    // Shared SPI bus rule (from LILYGO display.ino): every CS parked high before
    // the e-paper is allowed on the bus.
    pinMode(PIN_LORA_CS, OUTPUT);  digitalWrite(PIN_LORA_CS, HIGH);
    pinMode(PIN_LORA_RST, OUTPUT); digitalWrite(PIN_LORA_RST, HIGH);
    pinMode(PIN_SD_CS, OUTPUT);    digitalWrite(PIN_SD_CS, HIGH);
    pinMode(PIN_EPD_CS, OUTPUT);   digitalWrite(PIN_EPD_CS, HIGH);

    SPI.begin(PIN_EPD_SCK, -1, PIN_EPD_MOSI, PIN_EPD_CS);
    // init(baud, initial_full_refresh, reset_duration_ms, pulldown_rst) — same
    // call LILYGO ships for this panel.
    epd.init(115200, true, 2, false);
    epd.setRotation(1);            // native 240x320 portrait -> 320x240 landscape

    m_partialSinceFull = 0;
    render(RefreshFull);
}

void Ui::render(Refresh r)
{
    bool doPartial = (r == RefreshPartial);
    if (doPartial) {
        if (!epd.epd2.hasPartialUpdate || ++m_partialSinceFull >= kPartialMax) {
            doPartial = false;     // time for a clean full refresh
        }
    }
    if (doPartial) {
        epd.setPartialWindow(0, 0, kScreenW, kScreenH);
    } else {
        epd.setFullWindow();
        m_partialSinceFull = 0;
    }
    epd.firstPage();
    do {
        drawScreen();
    } while (epd.nextPage());
}

// ---------------------------------------------------------------------------
void Ui::drawScreen()
{
    epd.fillScreen(GxEPD_WHITE);
    drawHeader();
    const App::TabState& s = m_app.cur();
    drawFieldRow('A', s.a, !s.focusB, kRowAY);
    drawFieldRow('B', s.b,  s.focusB, kRowBY);
    drawBanner();
    drawFooter();
}

void Ui::drawHeader()
{
    static const char* kChips[App::kTabCount] = {"1 ADD", "2 SUB"};
    for (int t = 0; t < App::kTabCount; t++) {
        const int gap  = 8;
        const int w    = (kBoxW - gap) / 2;
        const int x    = kXMargin + t * (w + gap);
        textInBox(x, kHeaderY, w, kHeaderH, kChips[t],
                  &FreeMonoBold12pt7b, m_app.currentTab() == t);
    }
}

void Ui::drawFieldRow(char label, const char* value, bool active, int y)
{
    // Label ("A" / "B") centred in its own column.
    char lab[2] = {label, '\0'};
    textInBox(kXMargin, y, kLabelW, kRowH, lab, &FreeMonoBold18pt7b, false);

    // Value box: inverted when it is the one being edited.
    const int x = kValueX, w = kValueW, h = kRowH;
    if (active) {
        epd.fillRect(x, y, w, h, GxEPD_BLACK);
    } else {
        epd.drawRect(x, y, w, h, GxEPD_BLACK);
    }
    epd.setFont(&FreeMonoBold18pt7b);
    epd.setTextColor(active ? GxEPD_WHITE : GxEPD_BLACK);
    int16_t tx, ty; uint16_t tw, th;
    epd.getTextBounds(value, 0, 0, &tx, &ty, &tw, &th);
    const int pad  = 10;
    const int txx  = x + pad - tx;
    const int top  = y + (h - th) / 2;
    epd.setCursor(txx, top - ty);
    epd.print(value);
}

void Ui::drawBanner()
{
    char text[12];
    snprintf(text, sizeof(text), "%d", m_app.result());
    textInBox(kXMargin, kBannerY, kBoxW, kBannerH, text,
              &FreeMonoBold24pt7b, true);   // black banner, white digits
}

void Ui::drawFooter()
{
    epd.setFont(NULL);                       // classic 5x7 bitmap font
    epd.setTextColor(GxEPD_BLACK);
    epd.setCursor(kXMargin, kFootY1);
    epd.print("ENT field | DEL back | SPACE clear | SYM/ALT = tab");
    epd.setCursor(kXMargin, kFootY2);
    epd.print("digits: UP=1, key 0 = 0, letters abc=2 ... wxyz=9");
}

void Ui::textInBox(int x, int y, int w, int h, const char* s,
                   const void* font, bool invert)
{
    epd.setFont(static_cast<const GFXfont*>(font));
    int16_t tx, ty; uint16_t tw, th;
    epd.getTextBounds(s, 0, 0, &tx, &ty, &tw, &th);
    if (invert) {
        epd.fillRect(x, y, w, h, GxEPD_BLACK);
        epd.setTextColor(GxEPD_WHITE);
    } else {
        epd.setTextColor(GxEPD_BLACK);
    }
    const int cx = x + (w - tw) / 2 - tx;
    const int cy = y + (h - th) / 2 - ty;   // ty is negative: this lands the baseline
    epd.setCursor(cx, cy);
    epd.print(s);
}
