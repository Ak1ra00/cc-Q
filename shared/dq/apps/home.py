# (c) 2026 cc-Q. The home screen. It reads the registry and contains zero
# app-specific logic -- adding an app must never mean editing this file.
#
from dq import theme
from dq.apps import APPS, find
from charcodes import KEY_CANCEL, KEY_HOME, KEY_UP, KEY_DOWN


_themed = False


async def run():
    from glob import dis
    from ux import ux_wait_keydown
    from dq.session import today_or_none

    # Recolour once, here rather than at import: the palette swap is global and
    # should not happen as a side effect of a module being frozen into the image.
    global _themed
    if not _themed:
        theme.apply()
        _themed = True

    top = 0
    while True:
        dis.clear()
        theme.header(dis, 'cc-Q', _power())

        today = today_or_none()
        theme.body(dis, 0, today or 'date not set', x=2)

        # Seven rows of apps at a time, and the list scrolls. It used to show
        # the first seven and silently drop the rest, which was fine at seven
        # apps and a bug at eight.
        rows = theme.BODY_ROWS - 1
        if top > max(0, len(APPS) - rows):
            top = max(0, len(APPS) - rows)
        for n, app in enumerate(APPS[top:top + rows]):
            try:
                status, alert = app.home_line()
            except Exception:
                status, alert = ('?', True)
            dis.text(2, theme.BODY_TOP + 1 + n,
                     theme.pad('%s  %s' % (app.hotkey, app.title), status,
                               theme.CHARS_W - 2))
        if len(APPS) > rows:
            dis.text(-1, theme.BODY_TOP + 1, '\u25b2' if top else ' ', dark=True)
            dis.text(-1, theme.BODY_TOP + rows, '\u25bc'
                     if top + rows < len(APPS) else ' ', dark=True)

        theme.footer(dis, _storage(), 'X exit')
        dis.show()

        ch = await ux_wait_keydown()
        if ch in (KEY_CANCEL, KEY_HOME):
            return                          # back to the upstream menu
        if ch == KEY_UP:
            top = max(0, top - 1)
            continue
        if ch == KEY_DOWN:
            top = min(max(0, len(APPS) - (theme.BODY_ROWS - 1)), top + 1)
            continue
        app = find(ch)
        if app:
            try:
                await app.start()
            except Exception as exc:
                from dq.ui import show_error
                await show_error(app.title, exc)


def _storage():
    try:
        from files import CardSlot
        if not CardSlot.is_inserted():
            return 'no card - nothing will save'
        return 'card A ok  •  B mirrored' if CardSlot.both_inserted() else 'card A ok'
    except Exception:
        return ''


def _power():
    try:
        from battery import get_batt_level
        pct = get_batt_level()
        return '%d%%' % pct if pct is not None else 'usb'
    except Exception:
        return ''
