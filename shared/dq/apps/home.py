# (c) 2026 cc-Q. The home screen. It reads the registry and contains zero
# app-specific logic -- adding an app must never mean editing this file.
#
from dq import theme
from dq.apps import APPS, find
from charcodes import KEY_CANCEL, KEY_HOME


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

    while True:
        dis.clear()
        theme.header(dis, 'cc-Q', _power())

        today = today_or_none()
        theme.body(dis, 0, today or 'date not set', x=2)

        # Seven rows for apps, which is what is left after the header, the date
        # and the footer. More than that and the extras are reachable by hotkey
        # but not listed -- the day that happens, this wants paging.
        for n, app in enumerate(APPS[:7]):
            try:
                status, alert = app.home_line()
            except Exception:
                status, alert = ('?', True)
            dis.text(2, theme.BODY_TOP + 1 + n,
                     theme.pad('%s  %s' % (app.hotkey, app.title), status,
                               theme.CHARS_W - 2))

        theme.footer(dis, _storage(), 'X exit')
        dis.show()

        ch = await ux_wait_keydown()
        if ch in (KEY_CANCEL, KEY_HOME):
            return                          # back to the upstream menu
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
