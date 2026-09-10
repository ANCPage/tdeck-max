# The e-ink brain: decides WHEN a finished frame is allowed onto the panel.
#
#   device      : Planner(epd)  -> full_refresh / fast_refresh on the UC8253
#   simulator   : Planner()     -> frames just stay in the buffer for capture
#
# Policy: full refresh on boot / screen change / every FAST_BUDGET fast ones.
# The budget mirrors what Meshtastic settled on in the field for this panel
# (EINK_LIMIT_FASTREFRESH=10), and full refreshes are the cure for ghosting.
#
# diff_rect() is the groundwork for the prize: windowed partial refresh. Today we
# still push the whole canvas; once windowed partial works on this panel, the same
# rect tells the driver how small a box it can send.

FAST_BUDGET = 10


class Planner:
    def __init__(self, epd=None, fast_budget=FAST_BUDGET):
        self.epd = epd
        self.fast_budget = fast_budget
        self.fast_count = 0

    def force_full(self):
        """Next paint does a clean full refresh (user 'force refresh' gesture)."""
        self.fast_count = self.fast_budget

    def paint(self, fb, buf, screen, app, full=False):
        screen.render(fb, app)
        if self.epd is None:
            return "sim"                      # host: caller captures the frame
        if full or self.fast_count >= self.fast_budget:
            self.epd.full_refresh(buf)
            self.fast_count = 0
            return "full"
        self.epd.fast_refresh(buf)
        self.fast_count += 1
        return "fast"


def diff_rect(old, new, width=320, height=240):
    """Smallest (x, y, w, h) covering every changed pixel, or None if identical.

    Frames are 1 bit per pixel, row-major, MSB first (same order the panel wants).
    """
    row_bytes = width // 8
    min_x, min_y = width, height
    max_x, max_y = -1, -1
    for i in range(len(new)):
        a, b = old[i], new[i]
        if a == b:
            continue
        y, xb = divmod(i, row_bytes)
        d = a ^ b
        for bit in range(8):
            if d & (0x80 >> bit):
                x = xb * 8 + bit
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
        if y < min_y:
            min_y = y
        if y > max_y:
            max_y = y
    if max_x < 0:
        return None
    return (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
